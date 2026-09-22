"""回表：把 proposal 里 `case_domain` 闸的"登记待办"标为已完成（2026-09-22）。

用 .py 文件而不是 `python -c`：正文含反引号，内联会被 bash 命令替换吞掉（本会话已踩两次）。
"""

from __future__ import annotations

import pathlib

P = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/r15-proposal-20260921/proposal.md")
s = P.read_text(encoding="utf-8")

old = "- **跟进 2（登记待办）**：`case_domain` 的评测通道闸**未做**（Owner 裁定接受：Agent Path 零流量）⇒"
new = (
    "- **跟进 2（✅ 已于 2026-09-22 落地）**：`case_domain` 的评测通道闸**已做**——"
    "`settings.allow_client_case_domain`（默认 False）+ `main._client_case_domain` 闸，"
    "消费点 `main.py:1661` 已改走闸；前端从不传该字段 ⇒ 生产**零行为变化**。"
    "判据 4 条（单元 3 +「闸外不得直读」回归守卫 1）；端点级不可达已在测试文件里如实标注。"
    "原待办措辞："
)
assert s.count(old) == 1, f"锚点未命中（count={s.count(old)}）"
P.write_text(s.replace(old, new, 1), encoding="utf-8", newline="")
print("proposal 跟进 2 已回表为已完成")
