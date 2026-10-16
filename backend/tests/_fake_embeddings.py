"""确定性固定向量嵌入（测试隔离，ADR-011）：测 Chroma 写入/检索链路，不加载真实 BGE/不联网。

768 维伪随机向量，供测试造临时库。独立模块（非 conftest）以便 test_import_docs 等直接 import。

两个必须成立的性质（2026-10-16 独立复核 B 路把它打出来后修在这里）：

1. **跨进程确定**：旧实现用内置 `hash()`，而 CPython 的 `str.__hash__` 按进程加盐
   ⇒ 同一文本每次运行得到不同向量，docstring 里写的"确定性"是假的，复算无从对齐。
   现在用 sha256 摘要做种子。
2. **无关文本必须真的"不像"**：旧实现在 `[0,1)` 取均匀正值，任意两段文本的余弦落在 0.72–0.77，
   既高于产品自己的 QA 直返/注入阈值（`knowledge_service.search_qa` threshold=0.7、
   `main._qa_direct_return` 0.92），也高于 `retrieval.vector_top` 无任何分数下限的现实——
   于是替身文档会**排到真实条文前面**，而"QA 命中"这类断言会靠替身自证通过（构造性假绿）。
   现在取 `[-1,1]` 并归一化：768 维下无关文本余弦≈0（±0.04），同文本仍恒等。
"""

import hashlib
import math
import random


class FakeEmbeddings:
    def __init__(self, dim: int = 768):
        self._dim = dim

    def _vec(self, text: str) -> list[float]:
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        rng = random.Random(seed)
        raw = [rng.uniform(-1.0, 1.0) for _ in range(self._dim)]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]


def embeddings_double():
    """把伪向量装进 `rag_chain` 的惰性资源壳，供函数级与模块级 fixture 共用（C15 分流）。

    只有一处实现：两处各写一遍就会漂移，而漂移的后果是"某条腿以为换了替身、其实还在加载 BGE"。
    延迟 import rag_chain，使本模块在不依赖 backend 路径的场景下仍可被读。
    """
    import rag_chain  # noqa: PLC0415

    return rag_chain._LazyResource("double 嵌入模型", FakeEmbeddings)
