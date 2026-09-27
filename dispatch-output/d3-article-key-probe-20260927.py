"""D3 探针：`article` 带前后空格 vs 不带，是不是两个不同的检索键？

问的是三件事：
  1. 写进 metadata 的 `article` 是原样还是被归一？
  2. 两个变体派生的 `version_id` 相同还是不同？
  3. `knowledge_service.py:210` 那条 where 各查到几块 ⇒ 重传能不能清掉对方？

隔离：三个 env **无条件**指向进程私有 TEMP（抄 tests/conftest.py:23/31-32/39-40），
不碰真实 backend/chroma_db。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

_pid = os.getpid()
os.environ["QUOTA_DB"] = os.path.join(tempfile.gettempdir(), f"d3_quota_{_pid}.sqlite")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    tempfile.gettempdir(), f"d3_app_{_pid}.db"
).replace("\\", "/")
os.environ["CHROMA_DIR"] = os.path.join(tempfile.gettempdir(), f"d3_chroma_{_pid}")

import knowledge_service as ks  # noqa: E402

SRC = "d3_probe_source"
UNPADDED = "第一〇一条"
PADDED = " 第一〇一条 "
DATE = "2026-01-01"


def dump(tag):
    got = ks._collection().get(where={"source": SRC}, include=["metadatas"])
    rows = sorted(
        (m.get("article"), m.get("version_id"), m.get("effective_from"))
        for m in got["metadatas"]
    )
    print(f"[{tag}] blocks={len(rows)}")
    for a, v, e in rows:
        print(f"    article={a!r} version_id={v} effective_from={e!r}")
    return rows


def where_hits(article):
    got = ks._collection().get(
        where={"$and": [{"source": SRC}, {"article": article}]}, include=["metadatas"]
    )
    return [(m.get("article"), m.get("version_id")) for m in got["metadatas"]]


print("=== 0 起点 ===")
dump("start")

print("\n=== 1 写不带空格 ===")
print("add_text(unpadded) ->", ks.add_text("D3 探针正文一。", source=SRC, article=UNPADDED, origin="manual", extra_meta={"effective_from": DATE}))
r1 = dump("after unpadded")

print("\n=== 2 写带前后空格（同条号同日期）===")
print("add_text(padded) ->", ks.add_text("D3 探针正文一。", source=SRC, article=PADDED, origin="manual", extra_meta={"effective_from": DATE}))
r2 = dump("after padded")

print("\n=== 3 复算 :210 的 where 各查到什么 ===")
print("where(article=unpadded) ->", where_hits(UNPADDED))
print("where(article=padded)   ->", where_hits(PADDED))

print("\n=== 4 再重传一次不带空格（看能不能清掉空格块）===")
ks.add_text("D3 探针正文一（修订）。", source=SRC, article=UNPADDED, origin="manual", extra_meta={"effective_from": DATE})
r4 = dump("after re-post unpadded")

print("\n=== 结论读数 ===")
print("step1 blocks =", len(r1), "| step2 blocks =", len(r2), "| step4 blocks =", len(r4))
if r2:
    print("两键是否互认:", "是" if len(where_hits(UNPADDED)) > 1 and len(where_hits(PADDED)) > 1 else "否")
    print("version_id 是否相同:", r2[0][1] == r2[-1][1] if len(r2) > 1 else "N/A")
