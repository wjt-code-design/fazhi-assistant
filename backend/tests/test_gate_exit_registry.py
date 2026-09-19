"""哨兵：`/api/chat` 的每个正文出口都必须在登记表里，且豁免必须带来源（硬红，不是告警）。

范本是 `tests/test_log_field_whitelist.py` —— 本仓已验证过的形状：**全树/全文静态扫 + 一条 watch-it-fail 自证**。
用静态扫而非运行时断言，才能覆盖**未被测试执行到**的分支（本项目吃过这个亏：E7 零流量但过单元测试）。

四条腿各一次自证（没有自证的哨兵 = 恒真断言）：
  ① 新增一条无锚点的正文出口 ⇒ 红；② 锚点 ID 不在登记表里 ⇒ 红；
  ③ 登记表里有一行源码中不存在 ⇒ 红；④ 豁免项缺来源 / 豁免数超上限 ⇒ 红。
第五条：入库 md 必须等于当场生成的输出（手改 md 即红）。

计划出处：R4（硬红 + 带票号的豁免清单 + 只用符号锚点）、R6（dict 是真源、md 是生成物）、
R7（Owner 批准在 `main.py` 加 13 行机读锚点注释）。
"""

from __future__ import annotations

import itertools
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from gate_exit_registry import (  # noqa: E402
    ANCHOR_RE,
    COLUMNS,
    EXEMPTIONS,
    EXITS,
    NON_TEXT_FRAME_KEYS,
    STATUSES,
    classify_non_text_frames,
    exits_by_anchor,
    scan_content_yields,
)

BACKEND = pathlib.Path(__file__).resolve().parents[1]
MAIN_PY = BACKEND / "main.py"
MD_PATH = BACKEND.parent / "docs" / "gate-exit-registry.md"

# 锚点形状只有一份定义（在真源里），这里不再抄第二份 `[PL#13]`。
MARKER_RE = ANCHOR_RE

# 豁免总数上限。**当前是 0** —— 有豁免就必须改这里，改这里就要在评审里解释。
# 存在的理由：R4 的豁免清单是最容易被"顺手加一条"消音的地方（票 G 复审实测过一条
# 全量零敏感的 load-bearing 闸，就是这么活的）。
MAX_EXEMPTIONS = 0

# GAP-TODO 的"挂上票了没"判据。**旧版写的是 `票|待开票|Owner` —— 单字「票」即过，等于没断**
# （CodeReview/c-2）。只认三种：显式『待开票』、`票 X`/`票X` 形式的票号、`S<n>` 形式的票号。
TICKET_RE = re.compile(r"待开票|票\s*[A-Z]|\bS\d{1,2}\b")


def _markers_by_line(src: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for i, line in enumerate(src.replace("\r\n", "\n").split("\n"), start=1):
        m = MARKER_RE.search(line)
        if m:
            out[i] = m.group(1)
    return out


def find_unregistered_exits(src: str, registered_ids: set[str]) -> list[str]:
    """腿①②：每条正文出口必须有锚点，且锚点 ID 必须在登记表里。"""
    markers = _markers_by_line(src)
    findings: list[str] = []
    for lineno, expr in scan_content_yields(src):
        mid = markers.get(lineno)
        if mid is None:
            findings.append(f"  :{lineno} 出口（正文={expr}）没有 `# gate-exit: E<n>` 锚点 ⇒ 未登记的新出口")
        elif mid not in registered_ids:
            findings.append(f"  :{lineno} 锚点 {mid} 不在登记表里（正文={expr}）")
    return findings


def find_ghost_rows(src: str, registered_ids: set[str]) -> list[str]:
    """腿③：登记表每行都必须在源码里真的存在（否则表在描述一个不存在的出口）。"""
    present = set(_markers_by_line(src).values())
    return [f"  登记表行 {i} 在源码里没有任何 `# gate-exit: {i}` 锚点" for i in sorted(registered_ids - present)]


def find_bad_exemptions(exemptions: list[dict], cap: int) -> list[str]:
    """腿④：豁免必须带来源（票号或 Owner 裁决），且总数不超过上限。"""
    findings = [
        f"  豁免 {e.get('id')} 缺来源（必须写票号或 Owner 裁决，不能空着）"
        for e in exemptions
        if not str(e.get("source", "")).strip()
    ]
    if len(exemptions) > cap:
        findings.append(f"  豁免条目 {len(exemptions)} 条 > 上限 {cap} ⇒ 加豁免要在评审里解释并显式改 MAX_EXEMPTIONS")
    return findings


# ---------------- 自证：这把手真能抓到东西（不是恒真断言） ----------------


def test_leg1_detects_exit_without_anchor(tmp_path):
    p = tmp_path / "fake_stream.py"
    p.write_text(
        "import json\n\n\nasync def stream():\n"
        "    yield f\"data: {json.dumps({'content': '新加的口子'}, ensure_ascii=False)}\\n\\n\"\n",
        encoding="utf-8",
    )
    found = find_unregistered_exits(p.read_text(encoding="utf-8"), {"E1"})
    assert len(found) == 1 and "没有" in found[0], f"哨兵没抓到无锚点出口：{found!r}"


def test_leg2_detects_anchor_id_not_in_registry(tmp_path):
    p = tmp_path / "fake_stream.py"
    p.write_text(
        "import json\n\n\nasync def stream():\n"
        "    yield f\"data: {json.dumps({'content': 'x'}, ensure_ascii=False)}\\n\\n\"  # gate-exit: E99\n",
        encoding="utf-8",
    )
    found = find_unregistered_exits(p.read_text(encoding="utf-8"), {"E1"})
    assert len(found) == 1 and "E99" in found[0], f"哨兵没抓到未登记的锚点 ID：{found!r}"


def test_leg3_detects_ghost_registry_row():
    assert find_ghost_rows("x = 1  # gate-exit: E1\n", {"E1", "E2"}) == [
        "  登记表行 E2 在源码里没有任何 `# gate-exit: E2` 锚点"
    ]


def test_leg4_detects_sourceless_exemption_and_cap():
    assert find_bad_exemptions([{"id": "E5", "source": ""}], cap=9)
    assert find_bad_exemptions([{"id": "E5", "source": "票 X"}], cap=0)
    assert find_bad_exemptions([{"id": "E5", "source": "票 X"}], cap=1) == []


# ---------------- 主断言（跑真实源码与真实登记表） ----------------


def test_main_py_exits_are_all_registered():
    src = MAIN_PY.read_bytes().decode("utf-8")
    n_src = len(scan_content_yields(src))
    assert n_src == len(EXITS), (
        f"源码里正文出口 {n_src} 条，登记表 {len(EXITS)} 行 ⇒ 数量不一致。"
        "（锚点绑定本身可能仍然全过 —— 比如两行表对上了同一条出口，所以这条单独断。）"
    )
    findings = find_unregistered_exits(src, {r["id"] for r in EXITS})
    assert not findings, "以下正文出口未登记（登记前先想清楚它该不该进表）：\n" + "\n".join(findings)


def test_registry_rows_all_exist_in_source():
    src = MAIN_PY.read_bytes().decode("utf-8")
    findings = find_ghost_rows(src, {r["id"] for r in EXITS})
    assert not findings, "登记表里有源码中不存在的出口（幽灵行）：\n" + "\n".join(findings)


def test_binding_is_by_anchor_not_by_position(tmp_path):
    """防"按行序配对"回潮：真源里在文件中间插一条出口时，按位 zip 会把后面每行的
    「现在吐什么」静默错配到别的出口，而 `strict=True` 只在条数不等时才炸 ⇒ md 自洽地假。"""
    p = tmp_path / "fake_stream.py"
    p.write_text(
        "import json\n\n\nasync def stream():\n"
        "    yield f\"data: {json.dumps({'content': 'AAA'}, ensure_ascii=False)}\\n\\n\"  # gate-exit: E2\n"
        "    yield f\"data: {json.dumps({'content': 'BBB'}, ensure_ascii=False)}\\n\\n\"  # gate-exit: E1\n",
        encoding="utf-8",
    )
    src = p.read_text(encoding="utf-8")
    by_anchor = exits_by_anchor(src)
    assert "AAA" in by_anchor["E2"] and "BBB" in by_anchor["E1"], f"按锚点绑却错配了：{by_anchor}"
    # 同一份输入走"按行序"的绑法必须给出**不同**结果，否则这条自证什么都没证
    positional = dict(zip(["E1", "E2"], [e for _ln, e in scan_content_yields(src)], strict=True))
    assert positional["E1"] != by_anchor["E1"], (
        f"按位与按锚点给出同一结果（都是 {positional['E1']!r}）⇒ 本条腿空转，换输入再试"
    )
    # 真码上再钉三个已知配对：将来谁把生成器改回按位，这三条会互换了才炸
    real = exits_by_anchor(MAIN_PY.read_bytes().decode("utf-8"))
    assert real["E1"] == "ca" and real["E8"] == "piece" and real["E13"] == "NOTE_QUOTA", (
        f"真实出口的 ID→表达式 配对了不一样的东西：{real['E1']!r} / {real['E8']!r} / {real['E13']!r}"
    )


def test_duplicate_anchor_rejected(tmp_path):
    """两条 yield 共用一个 ID 时不许静默合并成一条。"""
    p = tmp_path / "fake_stream.py"
    p.write_text(
        "import json\n\n\nasync def stream():\n"
        "    yield f\"data: {json.dumps({'content': 'A'}, ensure_ascii=False)}\\n\\n\"  # gate-exit: E1\n"
        "    yield f\"data: {json.dumps({'content': 'B'}, ensure_ascii=False)}\\n\\n\"  # gate-exit: E1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="重复锚点"):
        exits_by_anchor(p.read_text(encoding="utf-8"))


def test_non_text_frame_keys_are_load_bearing():
    """`NON_TEXT_FRAME_KEYS` 必须真的在管这件事，两头各钉一次。

    md §四 写着"哨兵会把它们分类计出"——这句话在 2026-09-20 之前是**假接线**：那个常量
    只被生成器渲染成文字，没有任何测试消费它（`[PL#14]`，正是这张表立表要防的形态）。
    """
    src = MAIN_PY.read_bytes().decode("utf-8")
    frames = classify_non_text_frames(src)
    assert frames, "一条非正文帧都没扫到 ⇒ 本条腿空转（清单和源码可能都变了）"
    keys_seen = {k for _ln, ks in frames for k in ks}
    unclassified = [ks for _ln, ks in frames if not set(ks) & set(NON_TEXT_FRAME_KEYS)]
    assert not unclassified, f"这些帧无法用清单分类（新帧形状？先判它算不算出口）：{unclassified}"
    unused = set(NON_TEXT_FRAME_KEYS) - keys_seen
    assert not unused, f"清单里这些键在源码里已经用不到了，清单该删这一项：{sorted(unused)}"


def test_leg5_ticket_re_is_not_an_empty_gun():
    """TICKET_RE 自己也得红过：旧版 `票|待开票|Owner` 让"本票面…"这种句子直接过关。"""
    for good in ("待开票（本表新发现）", "见票 C 的 §5-4", "S6 的遗留项", "由票G 复核"):
        assert TICKET_RE.search(good), f"该收的没收：{good!r}"
    for weak in ("本票已经登记", "票号待补", "Owner 已阅", "这张表的某票事项"):
        assert not TICKET_RE.search(weak), f"空枪没修好：{weak!r} 仍然被当成挂了票"


def test_registry_scope_is_whole_backend_not_just_main_py():
    """计划步骤2 写的是"全树扫"，而主断言只喂 `main.py` ⇒ 别处新增正文出口没人看得见（CodeReview/a-4）。

    登记表目前**没有**跨文件登记能力（EXITS 的 ID 只绑 main.py 的锚点），所以这条腿的作用是：
    一旦有第二个文件开始吐正文帧，当场炸，逼下任要么扩表、要么在那文件里显式声明不归本表管，
    而不是让"表 = 全仓答复出口"这句话静默变成假话。
    """
    offenders: dict[str, int] = {}
    for p in sorted(BACKEND.glob("*.py")):
        n = len(scan_content_yields(p.read_bytes().decode("utf-8")))
        if n:
            offenders[p.name] = n
    assert offenders == {"main.py": len(EXITS)}, (
        f"扫描范围与登记表不再吻合：{offenders} ⇒ 出口数应等于 EXITS 行数 {len(EXITS)}，且只应出现在 main.py"
    )


def test_registry_shape_is_complete():
    """每行填满每一列、状态在词表里、取证非空 —— 「不许留空」这条纪律的执行体。"""
    ids = [r["id"] for r in EXITS]
    assert len(ids) == len(set(ids)), f"出口 ID 重复：{ids}"
    bad: list[str] = []
    for r in EXITS:
        for col in COLUMNS:
            cell = r["cells"].get(col)
            if cell is None:
                bad.append(f"  {r['id']} × {col} 缺格（留空=三个月后没人知道是没查还是不必查）")
                continue
            status, evidence = cell
            if status not in STATUSES:
                bad.append(f"  {r['id']} × {col} 状态 {status!r} 不在词表里")
            if not evidence.strip():
                bad.append(f"  {r['id']} × {col} 有状态但没有取证")
            if status == "GAP-TODO" and not TICKET_RE.search(evidence):
                bad.append(f"  {r['id']} × {col} 是 GAP-TODO 却没写票号（也不是显式『待开票』）")
        extra = set(r["cells"]) - set(COLUMNS)
        if extra:
            bad.append(f"  {r['id']} 有不在 COLUMNS 里的列：{sorted(extra)}")
    assert not bad, "登记表结构不合格：\n" + "\n".join(bad)


def test_exemptions_are_legitimate():
    findings = find_bad_exemptions(EXEMPTIONS, MAX_EXEMPTIONS)
    assert not findings, "豁免清单不合格：\n" + "\n".join(findings)


def test_committed_md_is_the_generated_artifact():
    """md 是生成物：手改一个字就红。剥掉表头两行机器标记（时间戳 / commit）后逐行比。"""
    from scripts.gen_gate_exit_registry import render

    def strip(text: str) -> list[str]:
        rows = text.replace("\r\n", "\n").split("\n")
        return [r for r in rows if not r.startswith(("<!-- generated-at", "<!-- source-commit"))]

    a = strip(MD_PATH.read_bytes().decode("utf-8"))
    b = strip(render())
    if a != b:
        i, x, y = next(
            (i, x, y) for i, (x, y) in enumerate(itertools.zip_longest(a, b, fillvalue="<该侧缺失>")) if x != y
        )
        pytest.fail(
            "docs/gate-exit-registry.md 与真源生成结果不一致 ⇒ 要么手改了 md，"
            f"要么改了 main.py/真源没重新生成。第一处差异在第 {i} 行：\n"
            f"  入库: {x!r}\n  生成: {y!r}\n"
            "  重新生成：backend/venv/Scripts/python.exe backend/scripts/gen_gate_exit_registry.py"
        )
