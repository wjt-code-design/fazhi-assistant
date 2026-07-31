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
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from rag_chain import vectorstore, embeddings, BASE_DIR
import retrieval
from models import QaCandidate

_ALLOWED_EXT = {".txt", ".md", ".pdf"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024

_seed_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=60)
_upload_splitter = RecursiveCharacterTextSplitter(
    chunk_size=600, chunk_overlap=80, separators=["\n\n", "\n", "。", "；", ". ", " ", ""]
)

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
        raise ValueError(f"不支持的文件类型 {ext or '(无)'}，仅支持 txt/md/pdf")
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise ValueError(f"文件过大（>{_MAX_UPLOAD_BYTES // (1024 * 1024)}MB）")
    if ext == ".pdf":
        if not raw.startswith(b"%PDF"):
            raise ValueError("不是有效的 PDF 文件（魔数校验失败）")
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
    """从上传文件提取纯文本。txt/md 按编码读取，pdf 用 pypdf。"""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("gbk", errors="ignore")
    return text.strip()


def add_text(
    content: str,
    source: str,
    article: str = "",
    origin: str = "manual",
    extra_meta: Optional[dict] = None,
    file_hash_value: Optional[str] = None,
) -> int:
    """切片入库，返回写入切片数。同 file_hash 重传会先替换旧切片。"""
    if file_hash_value:
        try:
            _collection().delete(where={"file_hash": file_hash_value})
        except Exception:
            pass
    splitter = _upload_splitter if origin == "upload" else _seed_splitter
    chunks = splitter.split_text(content)
    meta = {"source": source, "article": article, "origin": origin}
    if file_hash_value:
        meta["file_hash"] = file_hash_value
    if extra_meta:
        meta.update({k: v for k, v in extra_meta.items() if v not in (None, "")})
    # 时效三键归一化（阶段5）：强制存在，空值写 ""，status 缺省"现行"。
    # 理由：Chroma where 对缺失键的 $eq/$ne 语义不可靠，缺键会破坏时效过滤（见计划 D1）。
    meta["effective_from"] = (extra_meta or {}).get("effective_from") or ""
    meta["effective_to"] = (extra_meta or {}).get("effective_to") or ""
    meta["status"] = (extra_meta or {}).get("status") or "现行"
    docs = [Document(page_content=c, metadata=meta) for c in chunks]
    vectorstore.add_documents(docs)
    retrieval.invalidate()
    return len(docs)


def delete_doc(doc_id: str):
    _collection().delete(ids=[doc_id])
    retrieval.invalidate()


def list_docs():
    data = _collection().get(include=["documents", "metadatas"])
    out = []
    for i, doc_id in enumerate(data["ids"]):
        out.append(
            {
                "id": doc_id,
                "content": data["documents"][i],
                "metadata": (data["metadatas"][i] if data["metadatas"] else {}),
            }
        )
    return out


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
