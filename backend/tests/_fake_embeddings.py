"""确定性固定向量嵌入（测试隔离，ADR-011）：测 Chroma 写入/检索链路，不加载真实 BGE/不联网。

768 维伪随机向量（同一文本 → 同一向量，不同文本 → 可区分），供测试造临时库。
独立模块（非 conftest）以便 test_import_docs 等直接 import。
"""

import random


class FakeEmbeddings:
    def __init__(self, dim: int = 768):
        self._dim = dim

    def _vec(self, text: str) -> list[float]:
        h = hash(text) & 0xFFFFFFFF
        rng = random.Random(h)
        return [rng.random() for _ in range(self._dim)]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]
