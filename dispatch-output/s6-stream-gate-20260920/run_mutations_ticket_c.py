"""票 C/S6 的变异审计执行器：**复用** S5 后续票那台全量差分执行器，只换变异表。

为什么复用而不是重写（`dispatch-output/s5-followup-20260920/run_mutations_full.py`）：那台执行器
已经被票 G 修过三个假绿口子，本票一条都不想丢掉 ——
  · 每个变异跑**整套 `tests/`**（票 G F5：S5 四个变异各只跑一个定向文件 ⇒ 一条 load-bearing 闸被删
    后全量 21→21 零反应，却被记成 KILLED）；
  · 比分母：`tests>0 且 errors=0`，且变异体 `tests` 必须与基线**相等**，否则记 `denominator-drift`
    而不是 KILLED；
  · anchor 不唯一 ⇒ 记 `anchor-error`，且"非 KILLED 即坏"（不是只把 SURVIVED 当坏消息）；
  · CRLF 感知 + 跑完字节级还原并自证 `main_py_restored_byte_exact`。
S5 的**老**执行器 `run_mutations.py` 只跑定向文件，票面 §6-④ 明令别照搬那一点 ⇒ 本脚本不引它。

锚点**不硬抄字面**：本票改动过的行在被 `ruff format` 排过之后缩进/换行会变（本仓行号已漂过五次，
`ruff-format` 一次挪 12 行），所以每条锚点都在运行时从**当前** `backend/main.py` 的字节里现取
（`one_line` 取整行、`gate_block` 取"注释行 + 紧跟的那一次门调用"）。取不到或取到多份就直接抛，
不给"anchor 悄悄不匹配 ⇒ 变异根本没执行 ⇒ 末行照样 ALL_KILLED"留路。

用法（cwd 任意）：
    backend/venv/Scripts/python.exe dispatch-output/s6-stream-gate-20260920/run_mutations_ticket_c.py \
        <改后副本树> <输出目录>
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
S5_EXECUTOR = REPO / "dispatch-output/s5-followup-20260920/run_mutations_full.py"
MAIN_PY = REPO / "backend" / "main.py"

M1_COMMENT = (
    "# 由变异 C-M1（删本行）+ test_fallback_answer_also_passes_the_gate 对偶钉住。"
)
M2_COMMENT = "# 删本行 = 主路径没门（变异 C-M2）。"


def lf_text() -> str:
    """读 main.py 并归一到 LF —— 本机 `core.autocrlf=true`，工作树是 CRLF 而执行器按 LF 比对。"""
    return MAIN_PY.read_bytes().decode("utf-8").replace("\r\n", "\n")


def one_line(text: str, needle: str) -> str:
    """含 `needle` 的那**一**行（原缩进）。0 条或 ≥2 条直接抛 —— 不静默。"""
    hits = [ln for ln in text.split("\n") if needle in ln]
    if len(hits) != 1:
        raise SystemExit(f"锚点 {needle!r} 命中 {len(hits)} 行，必须恰好 1 行")
    return hits[0]


def gate_block(text: str, marker: str) -> str:
    """`marker` 那一行 + 紧跟其后的那一次 `_law_version_gate(...)` 调用（到闭合括号那行的换行为止）。

    ⚠️ `+ 2` 不是笔误、也不许"顺手对齐缩进"改成 `+ 3`：`tail.index(")\\n")` 指向的是那个 `)` 本身，
    `+2` 正好吃到换行符为止。本脚本第一版写了 `+3`，于是块尾**多吃掉下一行的一个前导空格**，
    替换后 `except Exception:` 少一格缩进 ⇒ 变异体直接 `IndentationError`、整套收集期炸
    （表现为 `DENOMINATOR-DRIFT tests=5`，而不是"这个缺陷没被测试杀掉"）。这类坑只能前置拦。
    """
    head = one_line(text, marker)
    i = text.index(head) + len(head) + 1
    tail = text[i:]
    j = tail.index(")\n") + 2
    block = text[i - len(head) - 1 : i + j]
    if "_law_version_gate(" not in block:
        raise SystemExit(f"{marker!r} 之后没找到门调用：{block!r}")
    return block


def comment_only(block: str) -> str:
    """把门调用块削成"只剩那行注释"（缩进原样保留，免得产出一段语法上怪异的代码）。"""
    return block.split("\n")[0] + "\n"


def build_mutants() -> dict[str, tuple[str, str]]:
    t = lf_text()
    b1 = gate_block(t, M1_COMMENT)
    b2 = gate_block(t, M2_COMMENT)
    cache_line = one_line(t, "and not law_version_hit")
    return {
        # ---- 本票四条正题 ----
        # C-M1 票 §5-3/§6-④ 点名：只接流式、不接 `_invoke_llm` 兜底。
        # 应当红在 `test_fallback_answer_also_passes_the_gate`。
        "C-M1_fallback_source_ungated": (b1, comment_only(b1)),
        # C-M2 主路径（流式 join）没门 ⇒ 承流量那条出口整个裸奔。
        # 应当红在 `test_streaming_join_hits_gate_and_appends_note_frame` + 独立期望表 + 缓存两腿。
        "C-M2_streaming_source_ungated": (b2, comment_only(b2)),
        # C-M3 票 §5-6 第五条件被删（票 G F5 的前科：这道闸曾经全量零敏感）。
        # 应当红在 `test_hit_answer_does_not_enter_cache`。
        "C-M3_cache_fifth_condition_removed": (cache_line + "\n", ""),
        # C-M4 票 §2d/§6-④ 点名：把检索到的**法条文本**当成本案事实。
        # 应当红在 `test_law_text_dates_are_not_facts_on_stream_exit` 与 S5 的同名轻量用例。
        "C-M4_context_used_as_facts": (
            one_line(t, 'texts = [pre.get("user_text")'),
            one_line(t, 'texts = [pre.get("user_text")').replace(
                'pre.get("rewritten") or ""]',
                'pre.get("rewritten") or "", pre.get("context") or ""]',
            ),
        ),
        # C-M5 票 §5-4：基准日退回 `body.law_as_of`（生产不传 ⇒ None ⇒ 门当成接线丢失 ⇒
        # 开关一开每条答复都降级、缓存全停写）。应当红在
        # `test_default_client_shape_never_reports_tripwire_not_wired`。
        "C-M5_stream_callsite_half1_removed": (
            b2,
            b2.replace("_fast_path_law_as_of(body)", "body.law_as_of"),
        ),
        # ---- 两条 S5 变异在本票被**改写**的分支上的回归（老执行器里那两条锚点指向的是改前字面，
        #      在本树已命中 0 次 ⇒ 会判 anchor-error，正是"非 KILLED 即坏"该报的东西） ----
        # C-M6 空答也追加注记（S5 M3 换了形状）：红在 S5 的 `test_empty_answer_still_returns_empty`。
        "C-M6_empty_answer_note_appended": (
            one_line(t, 'return ((answer + NOTE_LAW_VERSION) if answer else "")'),
            one_line(
                t, 'return ((answer + NOTE_LAW_VERSION) if answer else "")'
            ).replace(
                '((answer + NOTE_LAW_VERSION) if answer else "")',
                "answer + NOTE_LAW_VERSION",
            ),
        ),
        # C-M7 缺基准日改成放行（S5 M4 换了形状，fail-open）：红在 S5 的
        # `test_failclosed_when_switch_on_but_law_as_of_missing`。
        "C-M7_missing_date_passes": (
            one_line(t, 'reason = "LAW_TRIPWIRE_NOT_WIRED"'),
            one_line(t, 'reason = "LAW_TRIPWIRE_NOT_WIRED"').replace(
                'reason = "LAW_TRIPWIRE_NOT_WIRED"', "return answer, False"
            ),
        ),
    }


def prevalidate(mutants: dict[str, tuple[str, str]]) -> None:
    """跑之前先把每个变异在内存里应用一遍并 `ast.parse`。

    为什么必须前置（本轮实付学费）：锚点错位产出的不是"测试没杀掉这个缺陷"，而是一段
    **语法都不通**的 main.py ⇒ 整套收集期炸 ⇒ 分母从 1396 掉到 5 ⇒ 执行器只能记
    `DENOMINATOR-DRIFT`。三条变异各烧一次全量收集才看清这件事。语法预检把代价从 3 分钟降到 0。
    """
    import ast

    text = lf_text()
    broken: list[str] = []
    for name, (old, new) in mutants.items():
        n = text.count(old)
        if n != 1:
            broken.append(f"{name}: 锚点命中 {n} 次（须恰好 1）")
            continue
        if old == new:
            broken.append(f"{name}: old==new，这条变异根本没改动任何东西")
            continue
        try:
            ast.parse(text.replace(old, new, 1))
        except SyntaxError as e:
            broken.append(
                f"{name}: 变异后 main.py 语法不通（line {e.lineno}: {e.msg}）"
            )
    if broken:
        raise SystemExit("变异表预检未通过：\n  " + "\n  ".join(broken))
    print(
        f"预检：{len(mutants)} 条变异全部锚点唯一、有实际改动、且变异后语法可解析",
        flush=True,
    )


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    spec = importlib.util.spec_from_file_location("s5_mutation_executor", S5_EXECUTOR)
    assert spec and spec.loader, f"读不到 S5 执行器：{S5_EXECUTOR}"
    rmf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rmf)
    rmf.MUTANTS = build_mutants()  # 只换变异表，执行逻辑一字不改（复用即判据）
    # 主会话接手时补的一条（票 C r3）：副本树里 conftest 把 CHROMA_DIR 无条件指到**空的**进程私有临时库
    # ⇒ `pytestmark = slow` 那 18 条（要真实知识库才能过）在基线里恒红，r1/r2 的 `baseline_failed=19`
    # 就是 14 条缺 `.env` 的 gate2 + 5 条 slow。排掉 slow **不是藏红**，是让"基线红 0 条"变成可读判据；
    # slow 那 18 条本来由 run_gate_full 那条 lane 负责（§6-⑥）。gate2 那 14 条改用**假值 `.env`** 补齐
    # （副本树里只放 dummy，不放真 key），实测该文件从 14 红变 19 绿。
    rmf.PYTEST_EXTRA = ["-m", "not slow"]
    for name, (old, _new) in rmf.MUTANTS.items():
        print(f"{name}: anchor 首行={old.splitlines()[0][:78]}")
    prevalidate(rmf.MUTANTS)
    print(
        f"复用执行器={S5_EXECUTOR}\n变异数={len(rmf.MUTANTS)}（全部跑整套 tests/ + junit 差分 + 比分母）",
        flush=True,
    )
    sys.argv = [sys.argv[0], *sys.argv[1:]]
    return rmf.main()


if __name__ == "__main__":
    sys.exit(main())
