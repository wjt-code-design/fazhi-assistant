"""存量回填：为缺时效三键（status/effective_from/effective_to）的 chunk 补默认值。

背景（阶段5）：Chroma where 对缺失键的 $eq/$ne 语义不可靠，时效过滤依赖三键恒存在。
- 种子（knowledge_base.build）与新版 add_text 已保证三键存在；
- 本脚本只处理历史存量（上传/手动添加的旧 chunk），幂等可重跑。
- 自检断言：回填后缺键 chunk 数 == 0。

用法：cd backend && python scripts/backfill_time_meta.py
"""

import sys

sys.path.insert(0, ".")  # 允许从 backend/ 或任意目录运行

from rag_chain import vectorstore  # noqa: E402

BATCH = 100
KEYS = ("status", "effective_from", "effective_to")
DEFAULTS = {"status": "现行", "effective_from": "", "effective_to": ""}


def main():
    col = vectorstore._collection
    data = col.get(include=["metadatas"])
    ids, metas = data["ids"], data["metadatas"]
    fix_ids, fix_metas = [], []
    for i, m in enumerate(metas):
        meta = m or {}
        if all(k in meta for k in KEYS):
            continue
        patched = {k: meta.get(k) for k in KEYS}
        for k in KEYS:
            if patched[k] is None or patched[k] == "":
                patched[k] = DEFAULTS[k]
        fix_ids.append(ids[i])
        fix_metas.append(patched)
    if not fix_ids:
        print(f"无需回填：{len(ids)} 个 chunk 三键齐全")
        print("自检通过：缺键 chunk 数 = 0")
        return
    for i in range(0, len(fix_ids), BATCH):
        col.update(ids=fix_ids[i : i + BATCH], metadatas=fix_metas[i : i + BATCH])
        print(f"已回填 {min(i + BATCH, len(fix_ids))}/{len(fix_ids)}")
    # 自检：回填后缺键数必须为 0
    again = col.get(include=["metadatas"])
    missing = sum(1 for m in again["metadatas"] if not all(k in (m or {}) for k in KEYS))
    print(f"自检：缺键 chunk 数 = {missing}")
    if missing:
        print("FAIL: 仍存在缺键 chunk", file=sys.stderr)
        sys.exit(1)
    print("自检通过")


if __name__ == "__main__":
    main()
