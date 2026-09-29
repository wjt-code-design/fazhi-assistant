"""给主张复算器做「这把尺子能不能红」的变异对照。

为什么要有这个文件：`b_probe_claim_check.py` 报"全绿"本身不构成证据——
一条永远不会红的断言不是复算，是装饰（本轮确实抓出过一条这样的：`claim(..., True, "人工核对")`，已删）。
这里对**每条关键主张各造一个反例**，要求两件事同时成立：
  ① 整体 rc=1；
  ② 红的**正是该钉的那一条**（换成别的规则红了也算失败，那是运气不是覆盖）。

做法：把复算器复制成临时 mutant，只改一个字面量（改一处，用精确唯一锚点，改前先数命中数），
在被测同一份读数上跑；跑完删除。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
TARGET = EVIDENCE / "b_probe_claim_check.py"
REPO = EVIDENCE.parent.parent
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
    (
        "签字页无桩条数期望改 10（现算 9）",
        "expected_uncovered = 9",
        "expected_uncovered = 10",
        "D2 签字页的「无桩可答」清单",
    ),
    (
        "签字页日期期望改成一个不在册的值",
        'expected_date = "2026-10-05"',
        'expected_date = "2026-12-31"',
        "D2 签字页的复审日期",
    ),
    (
        "签字页公告号『都在登记表内』改成恒不成立（塞一条页外号）",
        "stray = sorted(set(cve_re.findall(block)) - listed)",
        'stray = sorted(set(cve_re.findall(block)) | {"CVE-1970-00001"})',
        "D2 签字页里出现的每条公告号",
    ),
    (
        "手抄条数检查的作用域放宽到每一行（文档里合法存在别处的计数，应立刻命中）",
        'scope = re.compile(r"b_probe_claim_check|b_probe_claim_mutants|主张复算|复算器|变异对照")',
        'scope = re.compile(r".")',
        "文档里指向本复算器的段落不出现手抄条数",
    ),
    (
        "可签文本六栏清单里换成一个不存在的栏名",
        'cols = ("一、接受范围", "二、不写进", "三、随接受", "四、必须一起算进", "五、复审日期", "六、签了也不解除")',
        'cols = ("一、接受范围", "二、不写进", "三、随接受", "四、必须一起算进", "五、复审日期", "七、根本不存在的栏")',
        "D2 可签文本六栏齐备",
    ),
    (
        "第六条的推送顺序串换成一个不存在的写法",
        'chain = "Q4（两条凭据轮换）→ 复扫 → Q6" in six',
        'chain = "Q9（根本不存在的顺序）" in six',
        "第六条把两条凭据分开列",
    ),
]

# 复算器侧的变异只证"这条主张真的在拿现算值算"。但 D2 签字页是**我手抄的文档**，
# 它的失败模式是"抄错"，不是"恒真" ⇒ 还得从文档侧打反例：把签字页改错，主张必须红。
# 本轮就是这么撞上的：我口头把复审日期建议成 2026-12-31，而登记表钉 2026-10-05。
# (名字, 目标文件（相对仓库根）, 唯一锚点, 替换, 期望红掉的主张名片段)
DOC_MUTANTS = [
    (
        "签字页日期抄成 2026-12-31",
        "docs/handoff-local-candidate-closeout-20260929.md",
        "五、复审日期：沿用登记表已有的 2026-10-05",
        "五、复审日期：沿用登记表已有的 2026-12-31",
        "D2 签字页的复审日期",
    ),
    (
        "签字页无桩清单漏抄一条公告",
        "docs/handoff-local-candidate-closeout-20260929.md",
        "、CVE-2026-9856；",
        "；",
        "D2 签字页的「无桩可答」清单",
    ),
    (
        "登记表第二处日期被改（第一处仍是原值 ⇒ 只比第一个 site 的写法会放过）",
        "dispatch-output/local-candidate-closeout-20260928/residual-risk-review.md",
        "复审最迟日期 **2026-10-05** 不变",
        "复审最迟日期 **2026-11-11** 不变",
        "复审日期与登记表**全部**出现处一致",
    ),
]


def run_doc_one(name: str, rel: str, anchor: str, repl: str, expect: str) -> tuple[bool, str]:
    """文档侧反例：把**手抄的那段文档**改错，复算器必须红。

    复算器侧的变异证"主张不是恒真"；这里证"抄错文档会被抓到"。两者不可互相替代。
    原地改同一份可转发交接书（或登记表），所以：字节级 sha 先留底，`finally` 按原字节还原，
    还原后再比一次哈希 —— 哈希不等就判本只变异无效（宁可不算覆盖，也不留一份被改脏的文档）。
    另有并发守卫：窗口内若有别的写入者动过这个文件，"按原字节还原"会静默吞掉别人的改动，
    那种情况同样判无效并如实报。
    """
    target = REPO / rel
    raw = target.read_bytes()
    before = hashlib.sha256(raw).hexdigest()
    src = raw.decode("utf-8")
    if src.count(anchor) != 1:
        return False, f"{name}: 文档锚点命中 {src.count(anchor)} 次（要恰好 1 次），变异未施加，不算覆盖"
    mutated_raw = src.replace(anchor, repl).encode("utf-8")
    _interloper = False
    try:
        target.write_bytes(mutated_raw)
        proc = subprocess.run([str(PY), str(TARGET)], capture_output=True, text=True, timeout=600)
        _interloper = target.read_bytes() != mutated_raw
    finally:
        target.write_bytes(raw)
    after = hashlib.sha256(target.read_bytes()).hexdigest()
    if after != before:
        return False, f"{name}: 🚨 还原后字节哈希变了（{before[:8]}→{after[:8]}），文档可能被改脏，本只不算覆盖"
    # 并发守卫：本仓有多个会话共写同一份交接书（台账 D28 记过两起污染事故）。
    # 窗口内若别人也写了这个文件，"按原字节还原"就会**静默吞掉他们的改动**，
    # 而 sha 复比只证"我还原对了"，不证"没毁别人的东西" ⇒ 这里显式检测并判本只无效。
    if _interloper:
        return False, f"{name}: 🚨 变异窗口内该文件被别的写入者改动过，本只不算覆盖（已按原字节还原）"
    out = proc.stdout + proc.stderr
    failed = [ln.strip() for ln in out.splitlines() if "[FAIL]" in ln]
    if proc.returncode == 0:
        return False, f"{name}: 签字页被改错后复算器仍 rc=0（这条抄错抓不到）"
    if not any(expect in ln for ln in failed):
        return False, f"{name}: 红的是别的条目 {failed[:2]}，期望「{expect}」"
    return True, f"{name}: 如期红且文档已按原字节还原（sha {before[:8]} 不变）-> {failed[0][:90]}"


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
    doc_results = []
    for m in DOC_MUTANTS:
        doc_results.append((m[0], *run_doc_one(*m)))
    print("=== 复算器侧变异对照（每行都必须「如期红」）")
    ok_all = True
    for _name, ok, detail in results:
        print(f"  {'KILLED' if ok else 'SURVIVED/INVALID'}  {detail}")
        ok_all = ok_all and ok
    print("=== 文档侧变异对照（把**手抄的签字页**改错，复算器必须红）")
    for _name, ok, detail in doc_results:
        print(f"  {'KILLED' if ok else 'SURVIVED/INVALID'}  {detail}")
        ok_all = ok_all and ok
    killed = sum(1 for _, ok, _ in results if ok) + sum(1 for _, ok, _ in doc_results if ok)
    n = len(results) + len(doc_results)
    (EVIDENCE / "b-probe-claim-check-mutants.json").write_text(
        json.dumps(
            {
                "mutants": n,
                "killed": killed,
                "checker_side": len(results),
                "doc_side": len(doc_results),
                "detail": [r[2] for r in results] + [r[2] for r in doc_results],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"\n合计 {killed}/{n} 只变异被杀掉")
    if not ok_all:
        print("MUTATION FAIL: 有主张杀不掉，或有变异没真的施加（不算覆盖）")
        return 1
    print("MUTATION PASS: 每条关键主张都能被针对性反例打红")
    print(restore_canonical_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
