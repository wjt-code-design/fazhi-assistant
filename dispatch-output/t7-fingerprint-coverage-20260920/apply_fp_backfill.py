"""T7 补采：给真实 `qa_pairs` 语料回填现算的 `options_fingerprint`（Owner 已点头）。

**计算口径 = T7 的 `_recompute_probe.py`，一字不差**：
  取文本 = 记录的 **document**（`page_content`，即题面）；函数 = `query_understand._options_fingerprint`。
  （不另写第二份"选项提取"——那正是本票要消灭的东西。）

**只补缺口（T7 交叉表的 B + E 两类），其余一律不碰**：
  - B：键存在但值为空、现算非空；
  - E：键不存在、现算非空。
  - A（双方非空）：**即使现算与存量不同也不改**——存量是生成器写的，改它是另一个决定；
    dry-run 会把 A 类不一致的条数报出来交给 Owner。
  - C（存量非空但现算空）：异常态，只报不改。
  - D/F（现算空）：无指纹可补，不写空串（写空串等于伪造"算过了"）。

**安全闸**（沿用票 I-2(a) 的写法，那次靠它们躲过了"取错集合"）：
  ① `_qa_corpus.get_qa_collection()`（集合名含 qa_pairs 且条数==279）；
  ② 写前**全量 279 条** metadata 备份（回滚路径）；
  ③ 逐条断言「合并结果 == 原 metadata + 我的这一个键」；
  ④ **默认 dry-run**，`--apply` 才真写；写后复核计数（60 → 期望 168）。

用法：
  dry-run：backend/venv/Scripts/python.exe dispatch-output/t7-fingerprint-coverage-20260920/apply_fp_backfill.py
  真写  ：backend/venv/Scripts/python.exe dispatch-output/t7-fingerprint-coverage-20260920/apply_fp_backfill.py --apply
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

REPO = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper")
OUT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "dispatch-output" / "hij-i-20260920"))

from dotenv import load_dotenv

load_dotenv(REPO / "backend" / ".env")

import _qa_corpus
import query_understand as qu


def main() -> int:
    apply = "--apply" in sys.argv
    col = _qa_corpus.get_qa_collection()
    data = col.get(include=["metadatas", "documents"])
    ids = list(data.get("ids") or [])
    metas = [dict(m or {}) for m in (data.get("metadatas") or [])]
    docs = list(data.get("documents") or [])

    # 写前全量备份（回滚路径；与票 I-2(a) 的备份分开命名，两笔写各自可独立回滚）
    backup_path = OUT / "fp-backfill-backup.json"
    backup_path.write_text(
        json.dumps(
            {
                "records": [
                    {"id": i, "metadata": m} for i, m in zip(ids, metas, strict=False)
                ]
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
        newline="",
    )

    cat = {
        "A_both": 0,
        "A_diff": 0,
        "B_fill": 0,
        "C_anomaly": 0,
        "D": 0,
        "E_fill": 0,
        "F": 0,
    }
    todo_ids: list[str] = []
    todo_metas: list[dict] = []
    # ⚠️ 必须按下标遍历：ids 里是 chroma 的 **id 字符串**，zip 出来当 `docs[i]` 的下标会
    # TypeError（list indices must be integers...）—— 第一版就是这么炸的。
    for idx in range(len(ids)):
        i = ids[idx]
        m = metas[idx]
        rfp = qu._options_fingerprint(docs[idx] or "")
        sval = m.get("options_fingerprint")
        s_ne = bool(sval)
        r_ne = bool(rfp)
        if s_ne and r_ne:
            cat["A_both"] += 1
            if sval != rfp:
                cat["A_diff"] += 1  # 只报不改：改存量是另一个决定
        elif (not s_ne) and r_ne:
            cat["B_fill" if "options_fingerprint" in m else "E_fill"] += 1
            merged = dict(m)
            merged["options_fingerprint"] = rfp
            # 逐条自证：合并结果 == 原 metadata **只多这一个键**（其余键一个没动）
            assert merged == {**m, "options_fingerprint": rfp}
            todo_ids.append(i)
            todo_metas.append(merged)
        elif s_ne and not r_ne:
            cat["C_anomaly"] += 1
        elif "options_fingerprint" in m:
            cat["D"] += 1
        else:
            cat["F"] += 1

    stored_nonempty_before = sum(1 for m in metas if m.get("options_fingerprint"))
    print(f"备份条数={len(ids)}（{backup_path.name}）")
    print(f"交叉表={cat}")
    print(
        f"存量非空(改前)={stored_nonempty_before}  待回填={len(todo_ids)}"
        f"（期望 = T7 的缺口 108；A_diff 不一致 {cat['A_diff']} 条只报不改）"
    )
    if not apply:
        print("（dry-run：未写库。加 --apply 才真正写入）")
        return 0
    if todo_ids:
        col.update(ids=todo_ids, metadatas=todo_metas)
    after = [dict(m or {}) for m in (col.get(include=["metadatas"])["metadatas"] or [])]
    n_after = sum(1 for m in after if (m.get("options_fingerprint") or "").strip())
    keys = sorted({k for m in after for k in m})
    print(f"写后条数={len(after)}  非空指纹={n_after}（期望 168）  全部键={keys}")
    (OUT / "fp-backfill-result.json").write_text(
        json.dumps(
            {
                "crosstab": cat,
                "n_total": len(after),
                "n_nonempty_after": n_after,
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
