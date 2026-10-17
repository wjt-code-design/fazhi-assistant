"""知识库服务：上传校验 / 切片入库 / 去重·版本 / 受控沉淀 / qa_pairs 集合。

- 服务端文件校验（magic bytes + 大小 + 扩展名白名单），不只靠前端。
- 上传用结构化切片（段落优先），种子/手动用 400/60。
- 重传同 hash 文件 → 替换旧切片（version）。
- 时效字段 effective_from/effective_to/status 经 extra_meta 透传到 metadata（阶段1种子，阶段5治理）。
- 受控沉淀：高有据问答先入 qa_candidates，管理员采纳后才写 qa_pairs 向量集合。
"""

import hashlib
import io
import logging
import os
import threading
import uuid
from datetime import UTC, datetime

from langchain_chroma import Chroma
from langchain_core.documents import Document
from sqlalchemy.orm import Session

import chunking
import retrieval
import retrieval_core as rc
from law_versions import replaceable_version_ids, version_metadata
from models import QaCandidate
from rag_chain import CHROMA_DIR, QA_COLLECTION_NAME, embeddings, lazy_store, vectorstore

logger = logging.getLogger("legal.knowledge")

_ALLOWED_EXT = {".txt", ".md", ".pdf", ".docx"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# 知识写串行锁：add_text 的 delete-then-add 与 delete_doc 非原子（Chroma 无事务），
# FastAPI 线程池下并发管理操作可能交错（互删/重复）。RLock 串行化写路径
# （可重入：add_text 内嵌套 add_chunks 也覆盖）。单 worker 约束下的务实方案——
# 真正的原子替换需 Chroma 事务或多进程协调，超出当前架构（见 ADR-008）。
_WRITE_LOCK = threading.RLock()


# 受控沉淀采纳后的"已确认问答"集合：用 question 做向量，便于问题空间匹配复用。
# collection 名随 embedding provider 派生（与主库同语义空间，见 rag_chain.QA_COLLECTION_NAME）
def _build_qa_store():
    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name=QA_COLLECTION_NAME,
    )


# 与主库共用 rag_chain.lazy_store 这一套惰性机制（D-52，2026-10-16）：
# import knowledge_service 不再建集合，第一次真读写 QA 才构造。
_qa_store = lazy_store(_build_qa_store, "chroma QA 集合")


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
                    raise ValueError(f"docx 内条目解压过大（{info.filename} 未压缩 {info.file_size} 字节），拒绝解析")
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
        from pypdf.errors import PyPdfError

        try:
            reader = PdfReader(io.BytesIO(raw))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except PyPdfError:
            raise ValueError("PDF 文件损坏或无法解析") from None
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
    时效三键归一化（阶段5）在此统一处理：空值写 ""，status 缺省"未验证"
    （Chroma where 对缺失键语义不可靠，缺键会破坏时效过滤）。
    """
    base = {"source": source, "origin": origin}
    if file_hash_value:
        base["file_hash"] = file_hash_value
    if extra_meta:
        base.update({k: v for k, v in extra_meta.items() if v not in (None, "")})
    base["effective_from"] = (extra_meta or {}).get("effective_from") or ""
    base["effective_to"] = (extra_meta or {}).get("effective_to") or ""
    base["status"] = (extra_meta or {}).get("status") or "未验证"
    docs = [Document(page_content=c, metadata={**base, **m}) for c, m in pairs if (c or "").strip()]
    if not docs:
        return 0
    try:
        vectorstore.add_documents(docs)
    except BaseException:
        # 批量写入或中断可能已写部分；尝试失效，但清理故障不能替换原写入异常。
        try:
            retrieval.invalidate()
        except Exception as exc:
            logger.warning("知识写入失败后的缓存失效也失败 (error=%s)", type(exc).__name__)
        raise
    else:
        # 写入成功时失效失败仍须向上抛出，不能报告为成功。
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
    - manual/import：单条条文切分；有明确生效日且同一法名、条号的重传视为同版本，修订版并存。
    - seed：knowledge_base.build 直写，不走本函数。
    """
    if origin in ("manual", "import") and article:
        supplied = extra_meta or {}
        extra_meta = {**supplied, **version_metadata(supplied, title=source, article=article, content=content)}

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
                    version_id = str((extra_meta or {}).get("version_id") or "").strip()
                    effective_from = str((extra_meta or {}).get("effective_from") or "").strip()
                    effective_to = str((extra_meta or {}).get("effective_to") or "").strip()
                    existing = _collection().get(
                        where={"$and": [{"source": source}, {"article": article}]},
                        include=["metadatas", "documents"],  # T1：判"遗留无时效块可否被取代"要看旧正文
                    )
                    # 本路径只消费"可替换"：并存块**不删**是安全侧（宁可留双胞胎，不可误删条文），
                    # "要说出来"落在预检（票 T2 的报警 + rc 分档）—— 写侧这里没有人工裁决的机会。
                    stale_ids = list(
                        replaceable_version_ids(
                            existing["ids"],
                            existing.get("metadatas") or [],
                            version_id=version_id,
                            effective_from=effective_from,
                            effective_to=effective_to,
                            documents=existing.get("documents") or [],
                            new_content=content,
                        ).replaceable
                    )
                except Exception as exc:
                    # 静默降级不可区分：判据整体失效与"判定后决定不替换"结果都是 stale_ids 空，
                    # 只留痕才分得开（version-safety-review-findings-20260927.md 低-2）。
                    stale_ids = []
                    # 刻意**不传 exc_info**（2026-09-27，票 T-A）：`_JsonFormatter` 会把 exc_info 的
                    # 异常原文 + 完整 traceback 整体写进内置键 `exc`（内置键，不占 `_ACCOUNT_FIELDS`
                    # 白名单，登记与否都拦不住），而这里被捕获的 `replaceable_version_ids(...)`
                    # 入参含 `new_content`（条文正文）+ `documents`（旧正文）⇒ 异常消息只要复述了
                    # 入参，正文就随 `exc` 落进 JSON 日志。诊断面保留**异常类名 + 法名 + 条号**
                    # （下面这行的 `error=%s` 与 `source/article`），足以定位是哪一步、对哪一条塌的；
                    # 需要原文时按同一法名/条号在本地复现即可。
                    # 举证：tests/test_knowledge_service.py::
                    # test_version_judgment_crash_is_visible_in_structured_log（合成敏感标记 +
                    # 断言 `exc` 键为空 + 正文记号不落日志）。
                    logger.warning(
                        "法版本判定失败，按不替换处理 (source=%s article=%s error=%s)",
                        source,
                        article,
                        type(exc).__name__,
                        extra={"law_version_judgment_failed": True},
                    )
            chunks = chunking.split_article_text(content, article=article)
            pairs = [
                (c.page_content, {"article": c.meta.get("article", ""), "chapter": c.meta.get("chapter", "")})
                for c in chunks
            ]
        n = add_chunks(pairs, source=source, origin=origin, extra_meta=extra_meta, file_hash_value=file_hash_value)
        # 写入成功后再删旧；读取不持有写锁，删旧结束后还需再次失效。
        # 失败仅导致新旧短暂共存，下次重传仍会清理——可接受，优于删旧失败丢知识。
        if n and stale_ids:
            try:
                _collection().delete(ids=stale_ids)
            except Exception:
                pass
            finally:
                retrieval.invalidate()
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
def add_qa_pair(
    question: str,
    answer: str,
    evidence: str = "",
    fingerprint: str = "",
    basis: str = "",
    cand_id: int | None = None,
    doc_id: str | None = None,
) -> str | None:
    """QA 对入库（answer/evidence/options_fingerprint 存 metadata，question 作向量检索入口）。

    fingerprint（选项内容指纹，审查 C4 护栏）：直返前校验同题干换选项内容必须 miss。

    **票 T6 写侧补口（2026-09-21）**：调用方不给指纹时**自己现算**。此前全仓只有
    `scripts/gen_qa_corpus.py` 传指纹，而两条**生产运行时写路径**（`create_candidate`
    有据分自动收录 / `decide_candidate` 人工采纳）与 `qa_seeds` 都不传 ⇒ 经它们进来的
    新语料对 C4 护栏是**盲的**（T7 补采只覆盖了存量 279 条，没堵写侧）。
    现算复用**读侧同一个** `query_understand._options_fingerprint`——不新增第二份选项提取规则；
    调用方显式传入的值优先（`gen_qa_corpus` 路径逐字不变）。

    **票 AUTH-A-2 写侧补口（2026-09-25，Owner 裁决 A 案）**：同一形状再堵一格——调用方不给
    `law_as_of_basis` 时落**当日**。第四轮核对把"缺 basis ⇒ 来源不可校验 ⇒ 不直返也不注入"
    上线后，全仓**没有任何生产者**写这个键（存量的值来自 09-20 一次性回填），于是新沉淀的语料
    **永久**过不了 `retrieval_core.qa_provenance_verifiable`：零模型直返会静默衰减到那 279 条。
    默认值对四条路径都是**真话**：`_post` 的沉淀闸明令"带历史基准日的请求不沉淀"，种子与生成
    脚本也按当日法律现产出。唯一例外是人工采纳——答案的法律版本身份属于**产生**它的那天，
    隔几天采纳不会让它变成今日的法 ⇒ `decide_candidate` 显式传候选 `created_at` 的日期。
    时钟取 UTC，与 `QaCandidate.created_at`（`datetime.utcnow`）同一个钟——
    若默认值改用本地钟，两条路径的"当日"就会差最多一天。

    **票 W06-IMPL 链接补口（2026-10-17，C03=形状 P）**：候选写路径传 `cand_id`/`doc_id`，
    把 `qa_candidate_id` 落进 metadata、用显式 `doc_id` 写向量并返回它 ⇒ SQL `vector_doc_id`
    与向量 `qa_candidate_id` 从此双向可对。种子/生成脚本不传这两个 ⇒ 记录无链，读侧按
    「来源可校验」判定（`qa_eligibility` 对无链记录放行到 provenance/citation，不是 fail-open）。

    **票 W06-FIX F1/V3（2026-10-17）**：上面那句「记录无链」从今天起不再是隐情——不传 `cand_id`
    时本函数落一只**已登记**的归因键 `qa_write_unlinked`（`observability._ACCOUNT_FIELDS`）并计入
    `qa_write_counts()`，管理面 `/api/admin/stats` 读得到。语义一个字没改（无链仍走来源/引用判定），
    改的是**可见性**：无链＝这批语料**撤不回**，现在这件事有名字、有数、有判据。
    """
    if not fingerprint:
        from query_understand import _options_fingerprint  # 局部导入：不加重模块加载

        fingerprint = _options_fingerprint(question or "")
    if not basis:
        basis = datetime.now(UTC).date().isoformat()
    metadata = {
        "answer": answer,
        "evidence": evidence,
        "origin": "qa",
        "options_fingerprint": fingerprint,
        "law_as_of_basis": basis,
    }
    if cand_id is not None:
        metadata["qa_candidate_id"] = cand_id
    _record_qa_write(cand_id)  # 票 W06-FIX F1/V3：无链写入亮键 + 计数（带链只计不亮）
    doc = Document(page_content=question, metadata=metadata)
    if doc_id:
        _qa_store.add_documents([doc], ids=[doc_id])
        return doc_id
    _qa_store.add_documents([doc])
    return None


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
    from qa_eligibility import QaHit  # 局部导入：只在真有命中时才碰判据模块（同 `_qa_store` 的加载纪律）

    return QaHit(
        {
            "question": res[0][0].page_content,
            "answer": res[0][0].metadata.get("answer", ""),
            "score": round(score, 4),
            "evidence": res[0][0].metadata.get("evidence", ""),
            # 票 I 的 I-2(a)：把语料的**版本基准日**带到调用方（`main._qa_direct_return` 靠它判分水岭），
            # 否则那道护栏没有输入。缺字段时给空串 ⇒ 调用方按"未标注"处理（不拦，保持旧行为）。
            "law_as_of_basis": res[0][0].metadata.get("law_as_of_basis", ""),
            "fingerprint": res[0][0].metadata.get("options_fingerprint", ""),
            # W06-IMPL：把候选链带出给读出口——出口据此装载 SQL 状态判资格。存量无链记录此项为 None
            # ⇒ `qa_eligibility` 走「无链按来源可校验放行」，而非按缺链 fail-closed。
            "qa_candidate_id": res[0][0].metadata.get("qa_candidate_id"),
        }
    )


# ==================== 受控沉淀 CRUD ====================
# 有据分 ≥ 此值自动收录（直接写 qa_pairs，跳过人工待审）——用户要求（2026-08-07）
AUTO_CURATE_THRESHOLD = 0.89

# 票 W06-FIX F1/V3：**「未链」是有名有数的状态，不是一个语义空缺**。
# 全仓两只在册写入者（`qa_seeds.py` 的种子、`scripts/gen_qa_corpus.py` 的离线语料）调
# `add_qa_pair` 时**不传 `cand_id`** ⇒ 写出来的向量记录没有候选链 ⇒ 它永远进不了状态轴、
# 永远撤回不了。本票按票面要求**不发明语义**（不硬把缺链读成 fail-closed，那会打掉
# `test_qa_provenance_guard.py`／`test_qa_citation_gate_symmetry.py` 钉死的放行面），
# 只把它变成**可见**：每写一条无链记录就落一只已登记的归因键 `qa_write_unlinked`
# （未登记会被 JSON formatter 静默丢弃 ⇒ 白写，见 `tests/test_log_field_whitelist.py`），
# 并把进程内计数交给管理面 DTO。
# 计数是**进程内**的（现役单进程，同 F6 的前提）；跨进程的累计看日志键本身。
_write_lock = threading.Lock()
_write_counts = {"linked": 0, "unlinked": 0}


def qa_write_counts() -> dict[str, int]:
    """无链/带链写入的进程内计数（`/api/admin/stats` 的 `qa_write_unlinked` 读它）。

    返回**拷贝**：调用方改不动内部状态（本仓教训：暴露可变共享状态＝把并发单例的第二种坏形状请回来）。
    """
    with _write_lock:
        return dict(_write_counts)


def _record_qa_write(cand_id: int | None) -> None:
    """写侧归因的唯一落点：带链记一笔、无链亮一只键。"""
    with _write_lock:
        _write_counts["linked" if cand_id is not None else "unlinked"] += 1
    if cand_id is not None:
        return
    # 只落标识与计数，不落题干/答案（AUTH-3 日志不落原文；种子题干也可能被用户问到）
    logging.getLogger("legal.chat").warning(
        "QA 语料写入不带候选链 ⇒ 该记录不可撤回（在册：qa_write_unlinked）",
        extra={"qa_write_unlinked": True},
    )


def create_candidate(db: Session, question: str, answer: str, grounded_score: float, evidence: str):
    """入候选。有据分 ≥ 0.89 自动收录（写 qa_pairs + 清缓存 + 标记 approved，不留待审）；
    否则进待审队列（status=pending，人工采纳）。反馈纠错（grounded=0）不受影响仍待审。

    W06-IMPL：自动收录改**先落 SQL 行拿 id**（flush，未提交），再带 `cand_id`/自生成 `doc_id` 写向量
    并把 `vector_doc_id` 记回行 ⇒ 双向链闭合；`approval_source="auto_by_score_inferred"` 让机器批准
    与人工批准**从此可区分**（此前两份拷贝都只写 approved，字节级不可分）。
    """
    if grounded_score >= AUTO_CURATE_THRESHOLD:
        c = QaCandidate(
            question=question,
            answer=answer,
            grounded_score=grounded_score,
            evidence=evidence,
            status="approved",
            approval_source="auto_by_score_inferred",
        )
        db.add(c)
        db.flush()  # 取回自增 id：向量的 qa_candidate_id 要在写入前就知道它
        doc_id = uuid.uuid4().hex
        add_qa_pair(question, answer, evidence or "", cand_id=c.id, doc_id=doc_id)
        c.vector_doc_id = doc_id
        # 票 W06-FIX F5（V1）：**先提交再清缓存**，两件事的顺序就是这条的判据对象。
        # 改前是 `retrieval.invalidate()` 在 `db.commit()` 之前 ⇒ invalidate 之后、commit 之前那一段里，
        # 并发请求仍能从 SQL 读到**旧状态**，把刚被撤掉的答案**写回回答缓存**（TTL 6 小时），
        # 于是「撤回即时生效」在窗口内被反向击穿；SQLite 单写者 + `timeout=30` 还会把窗口拉长。
        # 收录这一支的顺序同样按「提交可见 ⇒ 再清缓存」统一。
        #
        # 票 R2-F7（复核第二轮）：上一轮在这里补的那句旧理由——把「提交没成功」当成「没有变更、
        # 所以没有该清的」——是**错的**，复核照原样打穿了：向量是上面 `add_qa_pair` 在 commit **之前**
        # 就写好的，提交失败时「有变更」这件事已经成立（向量侧那条 QA 活着），而进程缓存与回答缓存
        # 仍留着旧读数——改前（invalidate 排在 commit 之前）本来就无条件清，这条洞是上一轮新挖的。
        # 现在收进 `finally`：提交成功＝提交可见后清；提交炸＝照样清再上抛。
        # 清早了的代价只是让人多查一次，留着旧读数的代价是一条已落进向量的语料被陈旧缓存一直盖着。
        # （判据：tests/test_qa_revocation_lifecycle.py::
        #  test_r2_commit_failure_still_clears_the_cache_on_both_write_branches ＋那条反对照）
        try:
            db.commit()
        finally:
            retrieval.invalidate()
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
    """待审/已决候选列表（管理面 `/api/admin/qa/candidates` 的读数）。

    票 W06-FIX F2①/V4：DTO 补齐**资格六列**（`approval_source`/`reviewed_by`/`reviewed_at`/
    `eligibility`/`eligibility_version`/`vector_doc_id`）。此前只回 7 列旧形状 ⇒
    「隔离」与「撤回」就算真的有生产者，管理面也**看不见**（判据：
    `tests/test_qa_read_eligibility.py::test_list_candidates_exposes_the_six_state_columns`）。
    `vector_doc_id` 为 None 就是**无链**（＝不可撤回）的那一列证据，与 `qa_write_unlinked` 键同源。
    """
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
            # ↓ 资格六列（票 W06-FIX F2①）
            "approval_source": r.approval_source,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "eligibility": r.eligibility,
            "eligibility_version": r.eligibility_version,
            "vector_doc_id": r.vector_doc_id,
        }
        for r in rows
    ]


def decide_candidate(db: Session, cand_id: int, decision: str, reviewed_by: int | None = None):
    """采纳/拒绝一条候选。

    W06-IMPL（C03=形状 B/P）：
    - 采纳：记 `approval_source="human"` + `reviewed_by`/`reviewed_at`（reviewed_by 由管理员端点传入，
      与它随后写的 `audit_logs.qa.approved` 同源）；带 `cand_id`/自生成 `doc_id` 写向量并回记 `vector_doc_id`
      ⇒ 与机器批准可区分、与向量双向闭合。
    - 拒绝：只**置资格**（`eligibility="revoked"`，不删向量、不删行——形状 P「隔离不删」），
      并调 `retrieval.invalidate()` 连带清回答缓存。此前拒绝分支只改 SQL status、两份拷贝照旧在服务，
      是本轮取证的 fail-open 缺陷。
    - 票 W06-FIX F5（V1）：`invalidate()` 挪到 `db.commit()` **之后**。改前顺序是
      invalidate → commit，中间那段里并发请求仍读到旧资格（`ok`），会把已撤回的答案**写回**
      回答缓存（TTL 6 小时）——「撤回即时生效」在窗口内被反向击穿。现在的不变式是
      **「缓存被清的那一刻，撤回在 SQL 里已经可读」**（判据：
      `tests/test_qa_revocation_lifecycle.py::test_revocation_is_visible_in_sql_at_the_moment_of_invalidate`，
      那条用例在 invalidate 的位置注入并发读者，测的是可见性而不是调用顺序）。
    """
    r = db.get(QaCandidate, cand_id)
    if not r:
        return None
    if decision == "approved":
        doc_id = uuid.uuid4().hex
        # 采纳≠产生：基准日取候选**产生**那天（created_at），不是此刻的今天。缺值时传空串，
        # 由 add_qa_pair 落当日——那是它默认的"今天产生"口径，比凭空造一个旧日期诚实。
        add_qa_pair(
            r.question,
            r.answer,
            r.evidence or "",
            basis=r.created_at.date().isoformat() if r.created_at else "",
            cand_id=cand_id,
            doc_id=doc_id,
        )
        r.vector_doc_id = doc_id
        r.status = "approved"
        r.approval_source = "human"
        r.reviewed_by = reviewed_by
        r.reviewed_at = datetime.now(UTC)
        r.eligibility = "ok"  # 重新采纳 = 恢复可服务（此前若被隔离/撤回，回到 ok）
    elif decision == "rejected":
        r.status = "rejected"
        r.eligibility = "revoked"
        r.eligibility_version = (getattr(r, "eligibility_version", 1) or 1) + 1
        # 拒绝必须停三条出口：置资格关语料两出口，invalidate（本函数末尾）关回答缓存出口（形状 B）
    else:
        raise ValueError("decision 必须为 approved 或 rejected")
    # 票 W06-FIX F5（V1）：纠错采纳/撤回都**先提交、再清缓存**（与 `create_candidate` 同一条不变式）。
    # 清早了而状态还没提交＝并发请求能在窗口里读到旧资格并把旧答案写回缓存（TTL 6 小时）。
    # 票 R2-F7：`finally` 补上另一半——提交炸了也**必须**清。采纳这一支的向量在上面就已经落盘，
    # 提交失败时缓存里那条旧答案照样服务它；拒绝这一支虽然没写向量，但资格已改而缓存未清
    # 同样是「旧读数继续在服务一条已撤回的语料」。上一轮那句把「提交没成功」当成「没有该清的」的
    # 旧理由已按现量改写（见 `create_candidate` 那一段的完整说明）。
    try:
        db.commit()
    finally:
        retrieval.invalidate()
    db.refresh(r)
    return r
