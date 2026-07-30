import os
import io
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag_chain import vectorstore

# 法律条文多为短文本，400 字切片可让每条基本保持完整
_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=60)


def _collection():
    # langchain_chroma 底层 chromadb 集合，支持 get/delete/count
    return vectorstore._collection


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


def count_docs() -> int:
    return _collection().count()


def add_text(content: str, source: str, article: str = "", origin: str = "manual") -> int:
    """把文本切分后入向量库，返回写入的切片数。"""
    chunks = _splitter.split_text(content)
    docs = [
        Document(
            page_content=c,
            metadata={"source": source, "article": article, "origin": origin},
        )
        for c in chunks
    ]
    vectorstore.add_documents(docs)
    return len(docs)


def delete_doc(doc_id: str):
    _collection().delete(ids=[doc_id])


def parse_uploaded(filename: str, raw: bytes) -> str:
    """从上传文件提取纯文本。txt/md 按编码读取（UTF-8 失败回退 GBK），pdf 用 pypdf。"""
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
