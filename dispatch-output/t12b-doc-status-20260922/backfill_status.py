"""T12-B：把 review-plan §1 的状态列按代码事实回填（只改 docs，不改代码）。

口径：**只有拿到代码事实的才改**；没核的保持 ⬜ 并在顶部说明里标注「未核」——
不允许把"没核实"混进"已核实未修"，那是另一种假象。
"""

from __future__ import annotations

import pathlib
import re

DOC = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper/docs/frontend-review-refactor-plan-20260915.md")
s = DOC.read_text(encoding="utf-8")

# 取得代码事实、状态应改的条目（详见同目录 report.md 的证据表）
TO_FIXED = {
    "A1": "✅（2026-09-22 核：`app/page.tsx` 27 行 / 0 useState；拆出 `components/chat/` 9 文件 + `lib/hooks/` 5 hook）",
    "A2": "✅（2026-09-22 核：`app/admin/page.tsx` 214 行；拆出 `app/admin/sections/` 6 段）",
    "A3": "✅（2026-09-22 核：`components/chat/MessageHtml.tsx`、`ChatImage.tsx` 已成独立组件文件）",
    "A4": "✅（2026-09-22 核：`lib/constants.ts` 存在；chat 页内 `SCENES/DAILY_LAWS/CODEX` 命中 0）",
    "B2": "🟡部分（2026-09-22 核：`lib/format.ts` 已建（T1.7）；`toLocaleString` 由 3 处收敛到 **1 处**残留 —— `admin/sections/AuditSection.tsx:23` 仍内联）",
    "B3": "✅（2026-09-22 核：`lib/api.ts` 382 行，`any` 命中 **0**）",
    "B4": "✅（2026-09-22 核：`app/page.tsx` 0 useState；状态进 `lib/hooks/useChatStream.ts`，**5 个 useState**）",
    "C1": "✅（2026-09-22 核：`public/sw.js` 缓存名 = `fazhi-shell-<BUILD_ID>`（install 时 fetch `/build-id.txt`）；" "硬编码 v1 仅存于**记录该缺陷的注释**里）",
    "D1": "✅（2026-09-22 核：`.eslintrc.json` / `.prettierrc` / `vitest.config.ts` + `test` script 齐备）",
    "D2": "✅（2026-09-22 核：**7 个测试文件 / 54 用例**，本次 `npm run check` 全过）",
    "F1": "✅（2026-09-22 核：`components/chat/MessageBubble.tsx:141` `aria-live={streaming && isLast ? \"polite\" : undefined}`）",
    "F2": "✅（2026-09-22 核：`InputBar.tsx:194` Enter 发送 / Shift+Enter 换行 + 占位符与 title 均有 UI 提示；含中文输入法 isComposing 保护）",
    "F5": "✅（2026-09-22 核：`components/chat/Sidebar.tsx:96` 管理后台入口 `disabled={streaming}`）",
    "F7": "✅（2026-09-22 核：`InputBar.tsx` 发送/上传等按钮为 `h-11 w-11`（44px））",
}

changed: list[str] = []
for item_id, note in TO_FIXED.items():
    # 行锚点：以 `| <ID> |` 开头、以 `| ⬜ |`（或带空格的变体）结尾的表格行
    rx = re.compile(r"^(\| " + re.escape(item_id) + r" \|.*?\| )⬜( \|\s*)$", re.MULTILINE)
    m = rx.search(s)
    if not m:
        print(f"[SKIP] {item_id}: 未找到以 ⬜ 结尾的行（可能已改）")
        continue
    s = s[: m.start()] + m.group(1) + note + m.group(2) + s[m.end() :]
    changed.append(item_id)

# 在状态口径说明下方插入回填说明
anchor = "状态：✅=已修（f0f9cc9）｜⬜=待修（本轮范围）"
note_block = anchor + """

> **状态列回填（2026-09-22，票 T12-B）**：本表原为 **2026-09-15 快照**，其后批次 0/1/2（护栏 + 速赢 + 结构）
> 已落地但未回填。本次按**代码事实**逐条核对：**14 条改判为 ✅/🟡部分**（A1–A4、B2、B3、B4、C1、D1、D2、F1、F2、F5、F7），
> 依据见 `dispatch-output/t12b-doc-status-20260922/report.md`。
> **仍为 ⬜ 的两类必须区分**：①**经核仍未做**——B1（内联 `<svg>` 17 处）、C3（`background-attachment:fixed` 仍在）、
> D4（6 处死样式 + `--stagger`/`--dur-med` 死变量仍在）、E1（`#ff8fa9`×5 / `#f56b8c`×2 / 裸 `rgba` 93 处）、
> E2（圆角仍 4 种）；②**本次未核（需人读或需算）**——C2、C4、E3、F3、F4、F6。**未核 ≠ 未做**，勿混读。"""
assert s.count(anchor) == 1
s = s.replace(anchor, note_block, 1)

DOC.write_text(s, encoding="utf-8", newline="")
print("改判条目:", ", ".join(changed))
print("未找到:", [k for k in TO_FIXED if k not in changed])
