"""I-2(a) 第二步：给真实 `qa_pairs` 语料标注**版本基准日**（票 I 已获 Owner 授权）。

**默认 dry-run**（不加 `--apply` 只打印计划，不写库）。写库前必须已经存在逐条备份
（由 `probe_i2_corpus_inventory.py` 产出 `corpus-backup-qa_pairs.json`），本脚本会对它做**前置断言**。

**为什么写日期而不是"epoch 标签"**：票面要求写基准日；而这里的日期是**推断**（语料无时间戳，
`gen_qa_corpus.py` docstring 原文：「智谱免费 token …（8-23 到期前消耗）」⇒ 生成日 **≤ 2026-08-23**）。
所以同时写一个**出处字段** `law_as_of_basis_src`，让"这是推断"随数据走，而不是只活在报告里。

**为什么这个推断是安全的**：运行时护栏只关心"与请求的 `law_as_of` 是否分处分水岭两侧"，
而 2026-08-23 与真实生成日（≤ 同一天）**必然同侧**（分水岭是 2021-01-01）
⇒ **护栏的判定对这条推断的误差不敏感**。这一点是本设计的承重点，别改成"精确日期"再当护栏输入。

只写两个新键，**不动任何既有键**（写入前逐条断言合并结果 == 原 metadata + 我的两个键）。

用法：
  dry-run：backend/venv/Scripts/python.exe dispatch-output/hij-i-20260920/apply_i2_basis_metadata.py
  真写  ：backend/venv/Scripts/python.exe dispatch-output/hij-i-20260920/apply_i2_basis_metadata.py --apply
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(OUT))

from dotenv import load_dotenv

load_dotenv(REPO / "backend" / ".env")

import _qa_corpus

BASIS = "2026-08-23"
BASIS_SRC = "inferred-docstring-8-23"
BACKUP = OUT / "corpus-backup-qa_pairs.json"


def main() -> int:
    apply = "--apply" in sys.argv
    if not BACKUP.exists():
        print(
            f"缺备份：{BACKUP} ⇒ 先跑 probe_i2_corpus_inventory.py（写库前必须有回滚路径）"
        )
        return 2
    backup = json.loads(BACKUP.read_text(encoding="utf-8"))
    backed_ids = [r["id"] for r in backup["records"]]
    print(f"备份条数={len(backed_ids)}（来自 {BACKUP.name}）")

    col = _qa_corpus.get_qa_collection()
    data = col.get(include=["metadatas"])
    ids = list(data.get("ids") or [])
    metas = list(data.get("metadatas") or [])
    print(f"库里当前条数={len(ids)}")
    if set(ids) != set(backed_ids):
        print("⚠️ 库与备份的 id 集合不一致 ⇒ 拒绝写入（先重新盘点并备份）")
        return 2

    have = [m for m in metas if (m or {}).get("law_as_of_basis")]
    todo_ids: list[str] = []
    todo_metas: list[dict] = []
    for i, m in zip(ids, metas, strict=False):
        m = dict(m or {})
        if m.get("law_as_of_basis"):
            continue
        merged = dict(m)
        merged["law_as_of_basis"] = BASIS
        merged["law_as_of_basis_src"] = BASIS_SRC
        # 逐条自证：只多了我这两个键，既有键一个都没动
        assert {
            k: v
            for k, v in merged.items()
            if k not in ("law_as_of_basis", "law_as_of_basis_src")
        } == m
        todo_ids.append(i)
        todo_metas.append(merged)

    print(f"已有该字段={len(have)}  待写={len(todo_ids)}")
    if not apply:
        print("（dry-run：未写库。加 --apply 才真正写入）")
        return 0
    if todo_ids:
        col.update(ids=todo_ids, metadatas=todo_metas)
    after = col.get(include=["metadatas"])["metadatas"] or []
    n_after = sum(1 for m in after if (m or {}).get("law_as_of_basis"))
    print(f"写后条数={len(after)}  带该字段={n_after}")
    (OUT / "11-i2-apply-result.json").write_text(
        json.dumps(
            {
                "basis": BASIS,
                "src": BASIS_SRC,
                "n_total": len(after),
                "n_labelled": n_after,
                "n_written": len(todo_ids),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
        newline="",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
