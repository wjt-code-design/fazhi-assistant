"""把 `backend/gate_exit_registry.py`（真源 dict）渲染成 `docs/gate-exit-registry.md`（生成物）。

md **不要手改**：`tests/test_gate_exit_registry.py` 会断言"入库 md == 当场生成的输出"（去掉下面两行
机器标记后逐字节比对），手改一个字就红。要改内容请改真源 dict 再重新生成。

用法（cwd 任意）：
    backend/venv/Scripts/python.exe backend/scripts/gen_gate_exit_registry.py
"""

from __future__ import annotations

import datetime
import pathlib
import subprocess
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from gate_exit_registry import (  # noqa: E402
    COLUMNS,
    EXEMPTIONS,
    EXITS,
    NON_TEXT_FRAME_KEYS,
    OUT_OF_SCOPE,
    exits_by_anchor,
)

HEADER_AT = "<!-- generated-at"  # 哨兵比对前会剥掉这两行
HEADER_SHA = "<!-- source-commit"


def _commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _expressions() -> dict[str, str]:
    """出口 ID → 该出口当前吐的正文表达式（如 `ca`、`NOTE_QUOTA`）。

    ⚠️ **刻意不放行号**：R4 定的是"只用符号锚点，行号会漂"，而 md 一旦含行号，
    任何上游加行都会让"md == 生成输出"这条哨兵红 ⇒ 变成逼人反复重新生成的噪声。
    表达式名是稳定的：改了它说明那条出口本身变了，正该红一次、回头复核那一行。
    """
    text = (BACKEND / "main.py").read_bytes().decode("utf-8")
    exprs = exits_by_anchor(text)  # 按锚点 ID 绑，不按行序（见该函数 docstring：按位 zip 会静默错配）
    missing = [row["id"] for row in EXITS if row["id"] not in exprs]
    if missing:
        # 表里有行、源码里没有对应锚点 ⇒ 宁可炸，也不要在 md 里渲染成"看起来对"的空单元格。
        raise SystemExit(f"登记表这些 ID 在源码里找不到锚点：{missing} ⇒ 先补锚点或删行，别改生成器")
    return exprs


def render() -> str:
    exprs = _expressions()
    at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    out: list[str] = [
        f"{HEADER_AT}: {at} -->",
        f"{HEADER_SHA}: {_commit()} -->",
        "",
        "# /api/chat 出口 × 闸门 登记表（生成物，勿手改）",
        "",
        "真源 = `backend/gate_exit_registry.py`；重新生成："
        "`backend/venv/Scripts/python.exe backend/scripts/gen_gate_exit_registry.py`。",
        "存在理由：本仓两次出现「门接在活代码上但那条代码今天没人走到」，第二次比第一次难发现 —— 它过单元测试。",
        "⇒ 每格必须有权威词汇表里的状态 + **取证**；填不出就写 `GAP-ACCEPTED+理由` 或 `GAP-TODO+票号`，不留空。",
        "",
        "状态词表（沿用 `docs/capability-matrix.md`，别造第三套）："
        "`PASS` 已接且判据有效 · `DISABLED` 接了但当前不生效 · `BLOCKED` 有前置未解 · "
        "`NA` 结构上不适用 · `GAP-ACCEPTED` 未覆盖已裁定接受 · `GAP-TODO` 未覆盖待修（带票号）。",
        "",
        "绑定方式：源码里每条正文帧 yield 带一行 `# gate-exit: E<n>` 锚点，"
        "哨兵做双向绑定（无锚点的出口 / 未登记的锚点 / 登记表幽灵行 / 无来源豁免）各一条硬红。",
        "",
        "## 一、速览矩阵",
        "",
        "| 出口 | 位置 | 现在吐什么 | 流量 | " + " | ".join(COLUMNS) + " |",
        "|---|---|---|---|" + "---|" * len(COLUMNS),
    ]
    for row in EXITS:
        cells = " | ".join(row["cells"][c][0] for c in COLUMNS)
        out.append(f"| **{row['id']}** | {row['where']} | `{exprs.get(row['id'], '?')}` | {row['traffic']} | {cells} |")

    gap_rows = [(r["id"], c, r["cells"][c][1]) for r in EXITS for c in COLUMNS if r["cells"][c][0] == "GAP-TODO"]
    out += [
        "",
        f"## 二、缺口清单（GAP-TODO 共 {len(gap_rows)} 格）",
        "",
        "| 出口 × 闸门 | 该格说什么 |",
        "|---|---|",
    ]
    out += [f"| **{e}** × {c} | {ev} |" for e, c, ev in gap_rows]

    out += [
        "",
        "## 三、逐格取证",
        "",
    ]
    for row in EXITS:
        out += [
            f"### {row['id']} — {row['where']}",
            "",
            f"- 流量程度：{row['traffic']}",
            "",
            "| 闸门 | 状态 | 取证 |",
            "|---|---|---|",
        ]
        for col in COLUMNS:
            st, ev = row["cells"][col]
            out.append(f"| {col} | `{st}` | {ev} |")
        out.append("")

    out += [
        "## 四、不归本表的东西（显式登记，免得下任重画一遍）",
        "",
        f"- **非正文帧**：payload 键 {', '.join('`' + k + '`' for k in NON_TEXT_FRAME_KEYS)} 的帧不算"
        "「会吐用户可见正文的出口」，但哨兵会把它们分类计出（不报警也不漏统计）。",
    ]
    out += [f"- **{k}**：{v}" for k, v in OUT_OF_SCOPE.items()]
    out += [
        "",
        "## 五、豁免清单",
        "",
    ]
    if EXEMPTIONS:
        out += ["| 出口 | 豁免理由 | 出处（票号 / Owner 裁决） |", "|---|---|---|"]
        out += [f"| {e['id']} | {e['reason']} | {e['source']} |" for e in EXEMPTIONS]
    else:
        out.append("（空）—— 任何新增豁免都必须带票号或 Owner 裁决，且总数受哨兵里写死的上限约束。")
    out.append("")
    return "\n".join(out)


def main() -> int:
    out_path = ROOT / "docs" / "gate-exit-registry.md"
    out_path.write_bytes(render().encode("utf-8"))  # 写字节：本仓 core.autocrlf=true
    print(f"wrote={out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
