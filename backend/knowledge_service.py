"""知识库服务：上传校验 / 切片入库 / 去重·版本 / 受控沉淀 / qa_pairs 集合。

- 服务端文件校验（magic bytes + 大小 + 扩展名白名单），不只靠前端。
- 上传用结构化切片（段落优先），种子/手动用 400/60。
- 重传同 hash 文件 → 替换旧切片（version）。
- 时效字段 effective_from/effective_to/status 经 extra_meta 透传到 metadata（阶段1种子，阶段5治理）。
- 受控沉淀：高有据问答先入 qa_candidates，管理员采纳后才写 qa_pairs 向量集合。
"""

import hashlib
import io
import os
import threading

from langchain_chroma import Chroma
from langchain_core.documents import Document
from sqlalchemy.orm import Session

import chunking
import retrieval
import retrieval_core as rc
from models import QaCandidate
from rag_chain import BASE_DIR, QA_COLLECTION_NAME, embeddings, vectorstore

_ALLOWED_EXT = {".txt", ".md", ".pdf", ".docx"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# 知识写串行锁：add_text 的 delete-then-add 与 delete_doc 非原子（Chroma 无事务），
# FastAPI 线程池下并发管理操作可能交错（互删/重复）。RLock 串行化写路径
#（可重入：add_text 内嵌套 add_chunks 也覆盖）。单 worker 约束下的务实方案——
# 真正的原子替换需 Chroma 事务或多进程协调，超出当前架构（见 ADR-008）。
_WRITE_LOCK = threading.RLock()

# 受控沉淀采纳后的"已确认问答"集合：用 question 做向量，便于问题空间匹配复用。
# collection 名随 embedding provider 派生（与主库同语义空间，见 rag_chain.QA_COLLECTION_NAME）
_qa_store = Chroma(
    persist_directory=os.path.join(BASE_DIR, "chroma_db"),
    embedding_function=embeddings,
    collection_name=QA_COLLECTION_NAME,
)


def _collection():
    return vectorstore._collection


_QA_IS_COSINE: bool | None = None


def _qa_is_cosine() -> bool:
    """qa_pairs collection 是否 cosine 空间（cloud 新库 qa_pairs_te4 是，本地 qa_pairs 是 L2）。"""
    global _QA_IS_COSINE
    if _QA_IS_COSINE is None:
        _QA_IS_COSINE = rc.is_cosine_space(_qa_store._collection)
    return _QA_IS_COSINE


def file_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_upload(filename: str, raw: bytes) -> str:
    """校验扩展名/大小/magic/可解码；通过返回扩展名。失败抛 ValueError。"""
    if not filename:
        raise ValueError("缺少文件名")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXT:
        raise ValueError(f"不支持的文件类型 {ext or '(无)'}，仅支持 txt/md/pdf/docx")
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise ValueError(f"文件过大（>{_MAX_UPLOAD_BYTES // (1024 * 1024)}MB）")
    if ext == ".pdf":
        if not raw.startswith(b"%PDF"):
            raise ValueError("不是有效的 PDF 文件（魔数校验失败）")
    elif ext == ".docx":
        if not raw.startswith(b"PK"):
            raise ValueError("不是有效的 docx（应为 zip 容器，魔数校验失败）")
        try:
            import zipfile

            zf = zipfile.ZipFile(io.BytesIO(raw))
            if "word/document.xml" not in zf.namelist():
                raise ValueError("不是有效的 docx（缺少 word/document.xml）")
            # 解压炸弹防护（对抗审计 v2 #1）：raw 10MB 上限只限压缩体积，DEFLATE 重复 XML 可
            # 100:1 解压到 GB 级，_read_capped 拦不住 → 用中央目录的未压缩大小（不解压）直接拒超限条目
            _MAX_DECOMPRESSED = 30 * 1024 * 1024  # 单条目未压缩上限 30MB
            for info in zf.infolist():
                if info.file_size > _MAX_DECOMPRESSED:
                    raise ValueError(
                        f"docx 内条目解压过大（{info.filename} 未压缩 {info.file_size} 字节），拒绝解析"
                    )
        except zipfile.BadZipFile:
            raise ValueError("docx 容器损坏，无法解析") from None
    else:
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                raw.decode("gbk")
            except UnicodeDecodeError:
                raise ValueError("文本文件编码无法识别（需 UTF-8/GBK）") from None
    return ext


def parse_uploaded(filename: str, raw: bytes) -> str:
    """从上传文件提取纯文本。txt/md 按编码读取，pdf 用 pypdf，docx 用 docx_utils。"""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    elif ext == ".docx":
        from docx_utils import extract

        text, _warnings = extract(raw, filename)
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("gbk", errors="ignore")
    return text.strip()


def parse_upload_or_raise(filename: str, raw: bytes) -> tuple[str, str]:
    """校验并解析上传文件，返回 (ext, text)。校验/空文本失败抛 ValueError（调用方转 400）。

    chat_file（合同评估输入）与 admin_upload（知识库）共用，消除 validate+parse+空检查重复
    （code-review Standards，2026-08-06）。
    """
    ext = validate_upload(filename, raw)
    text = parse_uploaded(filename, raw)
    if not text.strip():
        raise ValueError("未从文件中识别到文字（可能是扫描版或空文件）")
    return ext, text


def add_chunks(
    pairs: list,
    source: str,
    origin: str,
    extra_meta: dict | None = None,
    file_hash_value: str | None = None,
) -> int:
    """写入多 chunk（每 chunk 独立 metadata，如 article/chapter），返回写入数。

    调用方负责幂等（查重/替换）；本函数只负责写库 + 失效缓存。
    时效三键归一化（阶段5）在此统一处理：空值写 ""，status 缺省"现行"
    （Chroma where 对缺失键语义不可靠，缺键会破坏时效过滤）。
    """
    base = {"source": source, "origin": origin}
    if file_hash_value:
        base["file_hash"] = file_hash_value
    if extra_meta:
        base.update({k: v for k, v in extra_meta.items() if v not in (None, "")})
    base["effective_from"] = (extra_meta or {}).get("effective_from") or ""
    base["effective_to"] = (extra_meta or {}).get("effective_to") or ""
    base["status"] = (extra_meta or {}).get("status") or "现行"
    docs = [Document(page_content=c, metadata={**base, **m}) for c, m in pairs if (c or "").strip()]
    if not docs:
        return 0
    vectorstore.add_documents(docs)
    retrieval.invalidate()
    return len(docs)


def add_text(
    content: str,
    source: str,
    article: str = "",
    origin: str = "manual",
    extra_meta: dict | None = None,
    file_hash_value: str | None = None,
) -> int:
    """切片入库，返回写入切片数。

    - upload：走结构化切分（条号边界/章节前缀/目录跳过，见 chunking.split_law_document）；
      同 file_hash 重传先替换旧切片。
    - manual/import：单条条文切分；按 (source, article) 幂等——重复添加=更新而非堆积。
    - seed：knowledge_base.build 直写，不走本函数。
    """
    with _WRITE_LOCK:
        # 先收集旧文档 id，写入成功后再删——避免"先删旧再写"在嵌入/写库失败时
        # 旧知识已被删且无回滚 → 文档/条文静默丢失（对抗审计 2026-08-07）
        stale_ids: list = []
        if file_hash_value:
            try:
                stale_ids = list(_collection().get(where={"file_hash": file_hash_value})["ids"])
            except Exception:
                stale_ids = []
        if origin == "upload":
            chunks = chunking.split_law_document(content)
            pairs = [
                (c.page_content, {"article": c.meta.get("article", ""), "chapter": c.meta.get("chapter", "")})
                for c in chunks
            ]
        else:
            if origin in ("manual", "import") and article:
                try:
                    stale_ids = list(_collection().get(where={"$and": [{"source": source}, {"article": article}]})["ids"])
                except Exception:
                    stale_ids = []
            chunks = chunking.split_article_text(content, article=article)
            pairs = [
                (c.page_content, {"article": c.meta.get("article", ""), "chapter": c.meta.get("chapter", "")})
                for c in chunks
            ]
        n = add_chunks(pairs, source=source, origin=origin, extra_meta=extra_meta, file_hash_value=file_hash_value)
        # 写入成功后再删旧（add_chunks 已失效检索缓存；同一 RLock 内紧凑执行）。
        # 失败仅导致新旧短暂共存，下次重传仍会清理——可接受，优于删旧失败丢知识。
        if n and stale_ids:
            try:
                _collection().delete(ids=stale_ids)
            except Exception:
                pass
        return n


def delete_doc(doc_id: str):
    with _WRITE_LOCK:
        _collection().delete(ids=[doc_id])
    retrieval.invalidate()


def list_docs(limit: int = 50, offset: int = 0, source: str | None = None):
    """分页返回知识片段：{"items": [...], "total": N}。

    用 Chroma 原生 limit/offset（不全量拉取）——千级语料下避免一次序列化全部文档拖垮管理后台。
    source 可选：按法律名精确过滤（管理员按法名筛查 / 测试定位用）。
    """
    col = _collection()
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    where = {"source": source} if source else None
    total = len(col.get(where=where)["ids"]) if where else col.count()
    data = col.get(include=["documents", "metadatas"], limit=limit, offset=offset, where=where)
    items = [
        {
            "id": data["ids"][i],
            "content": data["documents"][i],
            "metadata": (data["metadatas"][i] if data["metadatas"] else {}),
        }
        for i in range(len(data["ids"]))
    ]
    return {"items": items, "total": total}


def count_docs(status: str | None = None) -> int:
    if status:
        return len(_collection().get(where={"status": status})["ids"])
    return _collection().count()


# ==================== qa_pairs（受控沉淀采纳后） ====================
def add_qa_pair(question: str, answer: str, evidence: str = "", fingerprint: str = "") -> None:
    """QA 对入库（answer/evidence/options_fingerprint 存 metadata，question 作向量检索入口）。

    fingerprint（选项内容指纹，审查 C4 护栏）：直返前校验同题干换选项内容必须 miss。
    """
    _qa_store.add_documents(
        [Document(
            page_content=question,
            metadata={"answer": answer, "evidence": evidence, "origin": "qa", "options_fingerprint": fingerprint},
        )]
    )


def search_qa(query: str, threshold: float = 0.7):
    """命中已确认问答则返回 {question,answer,score}，否则 None。

    性能优化（ADR-011 阶段D）：cosine 空间复用 chroma 距离分（1-dist），免重嵌。
    """
    res = _qa_store.similarity_search_with_score(query, k=1)
    if not res:
        return None
    if _qa_is_cosine():
        score = max(0.0, min(1.0, 1.0 - float(res[0][1])))
    else:
        try:
            qv = embeddings.embed_query(query)
            dv = embeddings.embed_documents([res[0][0].page_content])[0]
            score = rc.cos(qv, dv)
        except Exception:
            return None
    if score < threshold:
        return None
    return {
        "question": res[0][0].page_content,
        "answer": res[0][0].metadata.get("answer", ""),
        "score": round(score, 4),
        "evidence": res[0][0].metadata.get("evidence", ""),
        "fingerprint": res[0][0].metadata.get("options_fingerprint", ""),
    }


# ==================== 受控沉淀 CRUD ====================
# 有据分 ≥ 此值自动收录（直接写 qa_pairs，跳过人工待审）——用户要求（2026-08-07）
AUTO_CURATE_THRESHOLD = 0.89


def create_candidate(db: Session, question: str, answer: str, grounded_score: float, evidence: str):
    """入候选。有据分 ≥ 0.89 自动收录（写 qa_pairs + 清缓存 + 标记 approved，不留待审）；
    否则进待审队列（status=pending，人工采纳）。反馈纠错（grounded=0）不受影响仍待审。"""
    if grounded_score >= AUTO_CURATE_THRESHOLD:
        add_qa_pair(question, answer, evidence or "")
        # 收录 = 知识变更：清回答缓存，否则旧答案在 TTL 内继续命中、新 QA 静默失效
        import retrieval

        retrieval.invalidate()
        c = QaCandidate(
            question=question, answer=answer, grounded_score=grounded_score,
            evidence=evidence, status="approved",
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return c
    c = QaCandidate(
        question=question, answer=answer, grounded_score=grounded_score, evidence=evidence, status="pending"
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def list_candidates(db: Session, status: str | None = None):
    q = db.query(QaCandidate)
    if status:
        q = q.filter(QaCandidate.status == status)
    rows = q.order_by(QaCandidate.created_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "question": r.question,
            "answer": r.answer,
            "grounded_score": round(float(r.grounded_score or 0), 4),
            "evidence": r.evidence,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def decide_candidate(db: Session, cand_id: int, decision: str):
    r = db.get(QaCandidate, cand_id)
    if not r:
        return None
    if decision == "approved":
        add_qa_pair(r.question, r.answer, r.evidence or "")
        # 纠错采纳 = 知识变更：清回答缓存，否则旧答案在 TTL 内继续命中、纠错静默失效
        import retrieval

        retrieval.invalidate()
        r.status = "approved"
    elif decision == "rejected":
        r.status = "rejected"
    else:
        raise ValueError("decision 必须为 approved 或 rejected")
    db.commit()
    db.refresh(r)
    return r
