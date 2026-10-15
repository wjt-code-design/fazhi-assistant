"""存量回填：为缺时效三键（status/effective_from/effective_to）的 chunk 补默认值。

背景（阶段5）：Chroma where 对缺失键的 $eq/$ne 语义不可靠，时效过滤依赖三键恒存在。
- 种子（knowledge_base.build）与新版 add_text 已保证三键存在；
- 本脚本只处理历史存量（上传/手动添加的旧 chunk），幂等可重跑。
- 自检断言：回填后缺键 chunk 数 == 0。

用法：显式设置 CHROMA_DIR 后 python scripts/backfill_time_meta.py 预览；--write 才回填。
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import chroma_dir_guard  # noqa: E402

BATCH = 100
KEYS = ("status", "effective_from", "effective_to")
DEFAULTS = {"status": "未验证", "effective_from": "", "effective_to": ""}


def main():
    ap = argparse.ArgumentParser(description="预览或回填知识库时效元数据")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只预览（默认）")
    mode.add_argument("--write", action="store_true", help="显式允许回填")
    args = ap.parse_args()
    chroma_dir_guard.require_explicit_target("backfill_time_meta")
    from rag_chain import vectorstore

    col = vectorstore._collection
    data = col.get(include=["metadatas"])
    ids, metas = data["ids"], data["metadatas"]
    fix_ids, fix_metas = [], []
    for i, m in enumerate(metas):
        meta = m or {}
        if all(k in meta for k in KEYS):
            continue
        patched = dict(meta)
        for k in KEYS:
            if patched.get(k) is None or patched[k] == "":
                patched[k] = DEFAULTS[k]
        fix_ids.append(ids[i])
        fix_metas.append(patched)
    if not fix_ids:
        print(f"无需回填：{len(ids)} 个 chunk 三键齐全")
        print("自检通过：缺键 chunk 数 = 0")
        return
    if not args.write:
        print(f"dry-run：将回填 {len(fix_ids)}/{len(ids)} 个 chunk，未执行业务写入")
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
