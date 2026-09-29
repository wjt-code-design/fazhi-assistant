"""给主张复算器做「这把尺子能不能红」的变异对照。

为什么要有这个文件：`b_probe_claim_check.py` 报 58/58 全绿，本身不构成证据——
一条永远不会红的断言不是复算，是装饰（本轮确实抓出过一条这样的：`claim(..., True, "人工核对")`，已删）。
这里对**每条关键主张各造一个反例**，要求两件事同时成立：
  ① 整体 rc=1；
  ② 红的**正是该钉的那一条**（换成别的规则红了也算失败，那是运气不是覆盖）。

做法：把复算器复制成临时 mutant，只改一个字面量（改一处，用精确唯一锚点，改前先数命中数），
在被测同一份读数上跑；跑完删除。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
TARGET = EVIDENCE / "b_probe_claim_check.py"
PY = Path(r"C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/venv/Scripts/python.exe")

# (名字, 唯一锚点, 替换, 期望红掉的主张名片段)
# 变异一律打在「期望值」这一侧：把常量改成与实测读数不一致的值。
# 为什么不打在数据侧：数据是被测读数，改它就等于换被测对象；这里要证的是
# 「这条主张真的在拿实测值算，不是一句恒真话」，所以动期望、让实测跟不上期望，主张必须红。
MUTANTS = [
    (
        "环回次数期望改 1",
        'hosts.get("127.0.0.1") == 312',
        'hosts.get("127.0.0.1") == 313',
        "环回连接读数=312",
    ),
    (
        "外部目的次数期望改成 2 次",
        'hosts.get("test.invalid") == 1 and "other" not in hosts',
        'hosts.get("test.invalid") == 2 and "other" not in hosts',
        "外部目的只有 test.invalid=1",
    ),
    (
        "urllib 键形要求 method=GET（实测全是 POST）",
        'shape = re.compile(r"^urllib\\.Request :: \\S+ method=\\S+ headers\\[[^\\]]*\\]$")',
        'shape = re.compile(r"^urllib\\.Request :: \\S+ method=GET headers\\[[^\\]]*\\]$")',
        "urllib.Request 键形状只含 URL/方法/头键名",
    ),
    (
        "urllib 键形要求头键名为空（实测带 Content-type/Authorization）",
        'shape = re.compile(r"^urllib\\.Request :: \\S+ method=\\S+ headers\\[[^\\]]*\\]$")',
        'shape = re.compile(r"^urllib\\.Request :: \\S+ method=\\S+ headers\\[\\]$")',
        "urllib.Request 键形状只含 URL/方法/头键名",
    ),
    (
        "两腿零差异期望「必须有差异」",
        "not nd and set(pa) == set(pb),",
        "bool(nd) and set(pa) == set(pb),",
        "两腿复跑逐桩五轴零差异",
    ),
    (
        "两腿完整性字段期望改比 4 个（只有 3 个字段名对不上）",
        "len(same) == 3,",
        "len(same) == 4,",
        "两腿完整性三字段一致",
    ),
    (
        "net 自洽期望 kinds 多 1",
        'len(net) == d.get("net_event_kinds") and sum(net.values()) == d.get("net_event_total"),',
        'len(net) + 1 == d.get("net_event_kinds") and sum(net.values()) == d.get("net_event_total"),',
        "net 自洽",
    ),
    (
        "出处代次期望读数早于代码编辑（实际更晚）",
        "ok = rp is not None and rp.stat().st_mtime > newest_code",
        "ok = rp is not None and rp.stat().st_mtime < newest_code",
        "读数晚于仪器与驱动的最后编辑",
    ),
    (
        "组内桩数 G1 期望改 6（实际 7）",
        'counts = {"G1": 7, "G2": 3, "G3": 5, "G4": 7}',
        'counts = {"G1": 6, "G2": 3, "G3": 5, "G4": 7}',
        "G1 组桩数",
    ),
    (
        "trust_remote_code 期望改成放行 True",
        'trc == ["False"],',
        'trc == ["True"],',
        "trust_remote_code 取值",
    ),
    (
        "装桩前已加载期望变成非空清单",
        'suite.get("preloaded_app_at_install") == [],',
        'suite.get("preloaded_app_at_install") == ["backend.rag_chain"],',
        "装桩前应用未加载",
    ),
    (
        "自检装桩数期望改 20（实际 19）",
        "installed_n == 19",
        "installed_n == 20",
        "自检 桩装上 19/22",
    ),
]


def run_one(name: str, anchor: str, repl: str, expect: str) -> tuple[bool, str]:
    src = TARGET.read_text(encoding="utf-8")
    hits = src.count(anchor)
    if hits != 1:
        return False, f"{name}: 锚点命中 {hits} 次（要恰好 1 次），变异未施加，本场不算覆盖"
    mutated = src.replace(anchor, repl)
    if mutated == src:
        return False, f"{name}: 替换后文本没变（锚点与替换相同），不算覆盖"
    # mutant 必须落在**证据目录里**：复算器用 `Path(__file__).parent` 定位读数，
    # 放临时目录会 glob 不到读数（第一版就是这么错的：12 只变异全 rc=2「缺入库读数」，
    # 那不是"杀掉变异"，是变异根本没跑）。
    mp = EVIDENCE / "_claim_check_mutant_tmp.py"
    try:
        mp.write_text(mutated, encoding="utf-8", newline="\n")
        proc = subprocess.run([str(PY), str(mp)], capture_output=True, text=True, timeout=600)
    finally:
        mp.unlink(missing_ok=True)
    out = proc.stdout + proc.stderr
    failed = [ln.strip() for ln in out.splitlines() if "[FAIL]" in ln]
    if proc.returncode == 0:
        return False, f"{name}: 变异后整体仍 rc=0（该主张杀不掉，是假复算）"
    if not failed:
        return False, f"{name}: rc={proc.returncode} 但没有 [FAIL] 行（红因不可辨）"
    if not any(expect in ln for ln in failed):
        return False, f"{name}: 红的是别的条目 {failed[:2]}，期望「{expect}」"
    total = next((ln.strip() for ln in out.splitlines() if ln.startswith("合计")), "")
    return True, f"{name}: 如期红 -> {failed[0][:96]} | {total}"


def restore_canonical_json() -> str:
    """mutant 会覆写 `b-probe-claim-check.json`，全部跑完必须用现行复算器再跑一次把它取回。

    不做这一步，留在目录里的那份就是"某只变异的红读数"，报告引用它等于引用反例。
    """
    proc = subprocess.run([str(PY), str(TARGET)], capture_output=True, text=True, timeout=600)
    last = [ln.strip() for ln in proc.stdout.splitlines() if ln.startswith("合计")]
    return f"复算器复原跑 rc={proc.returncode} {last[-1] if last else '（无合计行）'}"


def main() -> int:
    results = []
    for m in MUTANTS:
        results.append((m[0], *run_one(*m)))
    print("=== 复算器变异对照（每行都必须「如期红」）")
    ok_all = True
    for _name, ok, detail in results:
        print(f"  {'KILLED' if ok else 'SURVIVED/INVALID'}  {detail}")
        ok_all = ok_all and ok
    killed = sum(1 for _, ok, _ in results if ok)
    (EVIDENCE / "b-probe-claim-check-mutants.json").write_text(
        json.dumps(
            {"mutants": len(results), "killed": killed, "detail": [r[2] for r in results]},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"\n合计 {killed}/{len(results)} 只变异被杀掉")
    if not ok_all:
        print("MUTATION FAIL: 有主张杀不掉，或有变异没真的施加（不算覆盖）")
        return 1
    print("MUTATION PASS: 每条关键主张都能被针对性反例打红")
    print(restore_canonical_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
