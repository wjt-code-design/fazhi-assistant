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

from gate_exit_registry import COLUMNS, EXEMPTIONS, EXITS, STATUSES, scan_content_yields  # noqa: E402

BACKEND = pathlib.Path(__file__).resolve().parents[1]
MAIN_PY = BACKEND / "main.py"
MD_PATH = BACKEND.parent / "docs" / "gate-exit-registry.md"

MARKER_RE = re.compile(r"#\s*gate-exit:\s*(E\d+)\b")

# 豁免总数上限。**当前是 0** —— 有豁免就必须改这里，改这里就要在评审里解释。
# 存在的理由：R4 的豁免清单是最容易被"顺手加一条"消音的地方（票 G 复审实测过一条
# 全量零敏感的 load-bearing 闸，就是这么活的）。
MAX_EXEMPTIONS = 0


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
            if status == "GAP-TODO" and not re.search(r"票|待开票|Owner", evidence):
                bad.append(f"  {r['id']} × {col} 是 GAP-TODO 却没写票号/待开票/Owner")
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
