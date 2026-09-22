"""纠正 R15-C-0 盘点里我写错的一条：管线**不需要改造**（写侧+读侧都已实现）。

原文（proposal.md 的 R15-C-0 补充节）说：
  「3. `effective_from` / `effective_to`——字段存在但全空 ⇒ **导入管线必须改造后才能填**」
— 这是**错的**：机制早已存在（见下），缺的只有数据。按防幻觉纪律必须改，不能留着一句
会让人去做无用工的结论。
"""

from __future__ import annotations

import pathlib

P = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/r15-proposal-20260921/proposal.md")
s = P.read_text(encoding="utf-8")

old = "3. **`effective_from` / `effective_to`**——字段存在但全空 ⇒ 导入管线必须改造后才能填。"
new = (
    "3. **`effective_from` / `effective_to`**——字段存在但全空。\n"
    "   ⚠️ **勘误（2026-09-22 复核）**：本行原写「导入管线必须改造后才能填」，**这是错的**——"
    "机制早已实现，缺的只有**数据**：\n"
    "   · **写侧**：`knowledge_service` 的 `extra_meta` 会把 `effective_from/effective_to/status` "
    "归一化落 metadata（:152-156，status 缺省「现行」），版本号/指纹由 `law_versions` 派生；\n"
    "   · **读侧**：`retrieval_core.is_valid_by_time(meta, cutoff)` 是向量池/BM25/grounded **唯一共用**的"
    "时效谓词（`retrieval._valid_docs` 调用；`exact_article_lookup` 等入口 `cutoff or today`）；\n"
    "   · **各有测试**：`tests/test_phase5.py`（谓词矩阵）、`tests/test_law_versions.py`（版本元数据）。\n"
    "   ⇒ 2026-09-22 新增**写↔读贯通契约测试** `tests/test_effective_window_roundtrip.py`"
    "（写两条不同效力期记录 → 按 2019-06-01 / 2020-12-31 / 2021-01-01 / 今日 四个 cutoff 取舍，"
    "含边界语义与 status 可见性；已用「去掉 effective_to」的变异体验过会红）。\n"
    "   **结论修正**：R15-C 的唯一阻塞项是 **(1) 历史法文本**，不是管线。"
)
assert s.count(old) == 1, f"锚点未命中（count={s.count(old)}）"
P.write_text(s.replace(old, new, 1), encoding="utf-8", newline="")
print("R15-C-0 盘点已纠正（管线不需要改造）")
