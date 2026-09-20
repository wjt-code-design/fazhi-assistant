"""取真实 QA 语料集合的**唯一入口**（票 I 的 I-2(a)；两个脚本共用，防再次取错对象）。

**为什么需要这个文件**：2026-09-20 实测踩过一次——`retrieval.vectorstore._collection` 指向的是
**法条主库**（`legal_provisions_*`，10266 条，metadata 是 `source/chapter/origin`），
**不是** QA 语料。第一次盘点把 10266 条法条当成了"279 条 QA"，
若直接写入就会往主库 10266 条法条上挂垃圾字段。**这次没出事，唯一原因是停下来读了条数。**
⇒ 把"取集合 + 守卫"收成一处，两个脚本都调它，别再各自 `vectorstore._collection`。

守卫两条（都不满足就 sys.exit(2)，**不写任何东西**）：
  ① 集合名必须含 `qa_pairs`（本地 `qa_pairs`；云端 `qa_pairs_te4`，见 `_qa_is_cosine` 的注释）；
  ② 条数必须等于 `expect_n`（默认 279 —— 与全仓文档一致的那个数；语料变了就显式传新值，
     让它成为一次**有意识的**决定，而不是静默漂移）。
"""

from __future__ import annotations

import os
import pathlib
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

REPO = pathlib.Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

DEFAULT_EXPECT_N = 279


def get_qa_collection(expect_n: int = DEFAULT_EXPECT_N):
    """返回真实 QA 语料集合对象；名字或条数不符则退出（不返回半个对象）。"""
    from dotenv import load_dotenv

    load_dotenv(REPO / "backend" / ".env")

    import knowledge_service as KS

    col = KS._qa_store._collection
    name = str(getattr(col, "name", "") or "")
    if "qa_pairs" not in name:
        print(f"⚠️ 取到集合 {name!r}，不含 'qa_pairs' ⇒ 取错对象，停手（不写任何东西）")
        sys.exit(2)
    data = col.get(include=["metadatas"])
    n = len(data.get("ids") or [])
    if n != expect_n:
        print(
            f"⚠️ 集合 {name!r} 条数={n}，与期望 {expect_n} 不符 ⇒ 停手（语料变了就显式传新值）"
        )
        sys.exit(2)
    print(f"✅ 目标集合={name!r} 条数={n}（与期望一致）")
    return col
