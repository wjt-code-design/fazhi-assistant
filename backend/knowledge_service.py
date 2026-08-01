"""知识库服务：上传校验 / 切片入库 / 去重·版本 / 受控沉淀 / qa_pairs 集合。

- 服务端文件校验（magic bytes + 大小 + 扩展名白名单），不只靠前端。
- 上传用结构化切片（段落优先），种子/手动用 400/60。
- 重传同 hash 文件 → 替换旧切片（version）。
- 时效字段 effective_from/effective_to/status 经 extra_meta 透传到 metadata（阶段1种子，阶段5治理）。
- 受控沉淀：高有据问答先入 qa_candidates，管理员采纳后才写 qa_pairs 向量集合。
"""
import hashlib
import io
import math
import os
from datetime import datetime
from typing import Optional

from langchain_core.documents import Document
from langchain_chroma import Chroma
from sqlalchemy.orm import Session

from rag_chain import vectorstore, embeddings, BASE_DIR
import chunking
import retrieval
from models import QaCandidate

_ALLOWED_EXT = {".txt", ".md", ".pdf", ".docx"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# 受控沉淀采纳后的"已确认问答"集合：用 question 做向量，便于问题空间匹配复用
_qa_store = Chroma(
    persist_directory=os.path.join(BASE_DIR, "chroma_db"),
    embedding_function=embeddings,
    collection_name="qa_pairs",
)


def _collection():
    return vectorstore._collection


def _cos(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


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

            if "word/document.xml" not in zipfile.ZipFile(io.BytesIO(raw)).namelist():
                raise ValueError("不是有效的 docx（缺少 word/document.xml）")
        except zipfile.BadZipFile:
            raise ValueError("docx 容器损坏，无法解析")
    else:
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                raw.decode("gbk")
            except UnicodeDecodeError:
                raise ValueError("文本文件编码无法识别（需 UTF-8/GBK）")
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


def add_chunks(
    pairs: list,
    source: str,
    origin: str,
    extra_meta: Optional[dict] = None,
    file_hash_value: Optional[str] = None,
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
    extra_meta: Optional[dict] = None,
    file_hash_value: Optional[str] = None,
) -> int:
    """切片入库，返回写入切片数。

    - upload：走结构化切分（条号边界/章节前缀/目录跳过，见 chunking.split_law_document）；
      同 file_hash 重传先替换旧切片。
    - manual/import：单条条文切分；按 (source, article) 幂等——重复添加=更新而非堆积。
    - seed：knowledge_base.build 直写，不走本函数。
    """
    if file_hash_value:
        try:
            _collection().delete(where={"file_hash": file_hash_value})
        except Exception:
            pass
    if origin == "upload":
        chunks = chunking.split_law_document(content)
        pairs = [
            (c.page_content, {"article": c.meta.get("article", ""), "chapter": c.meta.get("chapter", "")})
            for c in chunks
        ]
    else:
        if origin in ("manual", "import") and article:
            try:
                stale = _collection().get(
                    where={"$and": [{"source": source}, {"article": article}]}
                )["ids"]
                if stale:
                    _collection().delete(ids=stale)
            except Exception:
                pass
        chunks = chunking.split_article_text(content, article=article)
        pairs = [
            (c.page_content, {"article": c.meta.get("article", ""), "chapter": c.meta.get("chapter", "")})
            for c in chunks
        ]
    return add_chunks(pairs, source=source, origin=origin, extra_meta=extra_meta, file_hash_value=file_hash_value)


def delete_doc(doc_id: str):
    _collection().delete(ids=[doc_id])
    retrieval.invalidate()


def list_docs(limit: int = 50, offset: int = 0, source: Optional[str] = None):
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


def count_docs(status: Optional[str] = None) -> int:
    if status:
        return len(_collection().get(where={"status": status})["ids"])
    return _collection().count()


# ==================== qa_pairs（受控沉淀采纳后） ====================
def add_qa_pair(question: str, answer: str, evidence: str = "") -> None:
    _qa_store.add_documents(
        [Document(page_content=question, metadata={"answer": answer, "evidence": evidence, "origin": "qa"})]
    )


def search_qa(query: str, threshold: float = 0.7):
    """命中已确认问答则返回 {question,answer,score}，否则 None。"""
    docs = _qa_store.similarity_search(query, k=1)
    if not docs:
        return None
    try:
        qv = embeddings.embed_query(query)
        dv = embeddings.embed_documents([docs[0].page_content])[0]
        score = _cos(qv, dv)
    except Exception:
        return None
    if score < threshold:
        return None
    return {
        "question": docs[0].page_content,
        "answer": docs[0].metadata.get("answer", ""),
        "score": round(score, 4),
    }


# ==================== 受控沉淀 CRUD ====================
def create_candidate(db: Session, question: str, answer: str, grounded_score: float, evidence: str):
    c = QaCandidate(
        question=question, answer=answer, grounded_score=grounded_score, evidence=evidence, status="pending"
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def list_candidates(db: Session, status: Optional[str] = None):
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
        r.status = "approved"
    elif decision == "rejected":
        r.status = "rejected"
    else:
        raise ValueError("decision 必须为 approved 或 rejected")
    db.commit()
    db.refresh(r)
    return r
