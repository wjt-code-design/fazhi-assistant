"""范围对账器：把「应用运行时 / 开发工具 / 未审计」三条范围轴对着扫描读数现算一遍。

为什么要有这个文件：登记表那 26 行只覆盖**候选 requirements 解析集**，而 Owner 要签的是"这台机器上这套环境"。
只数条数会把两个轴混成一个分母（本仓踩过：`47/8` 与 `57/10` 不可相加）。这里把
「报中有什么 → 登记表覆盖了什么 → 剩下谁没管」逐条算出来，并给每条一个**版本适用性**判定，
免得把"扫描器报了"读成"适用"、或把"没报"读成"零风险"。

用法（在证据目录里，用候选解释器）：
    python b_scope_recount.py            # 只打印
    python b_scope_recount.py --write    # 同时写 scope-recount-20260929.md

判据口径（三条都要，缺一会假绿）：
  * 版本适用性 = 实装/解析版本 与公告 `fix_versions` 比较；`fix_versions` 为空 ⇒ 判「无修复版本(未给)」，
    **不等于**不适用。
  * `pip-audit` 只比**本包**版本，**不评估公告里的跨包前提**（如某条要求 torch<2.6）
    ⇒ 「报告里有」≠「该缺陷对本环境适用」；反过来"报告里没有"也不能当已排除。
  * 探针覆盖只认入库读数里**真的打了桩**的 CVE；未打桩的**不得**折进"已答"。
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

try:
    from packaging.version import InvalidVersion, Version
except ImportError:  # packaging 是 pip-audit 的依赖，正常必在；缺它只影响"版本适用性"那一列
    InvalidVersion = ValueError  # type: ignore[misc,assignment]
    Version = None  # type: ignore[assignment]

EVIDENCE = Path(__file__).resolve().parent
REG = EVIDENCE / "residual-risk-review.md"
PROBE_READINGS = ("b-probe-readings-pytest-*.json", "b-probe-readings-app-*.json")
SCAN_RESOLVED = "B-candidate-requirements-pip-audit-refresh-*.json"
SCAN_INSTALLED = "B-installed-pip-audit-refresh-*.json"
OUT = EVIDENCE / "scope-recount-20260929.md"
CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}")


def latest(pattern: str) -> Path | None:
    cands = sorted(glob.glob(str(EVIDENCE / pattern)))
    return Path(cands[-1]) if cands else None


def load_scan(path: Path) -> dict:
    """扫描件头部混着 pip-audit 的 stderr 横幅，真正的 JSON 从第一个 '{' 起。"""
    raw = path.read_text(encoding="utf-8", errors="replace")
    return json.loads(raw[raw.index("{") :])


def advisory_index(data: dict) -> dict[str, dict]:
    """按 CVE 归并（一条通报可能同时以 PYSEC/GHSA 与 CVE 别名出现，也可能一个 CVE 有多行）。"""
    out: dict[str, dict] = {}
    versions = {d["name"]: d.get("version") for d in data["dependencies"]}
    for dep in data["dependencies"]:
        for v in dep.get("vulns", []):
            names = {v["id"]} | set(v.get("aliases") or [])
            for cve in sorted(n for n in names if CVE_RE.fullmatch(n)):
                rec = out.setdefault(cve, {"pkgs": set(), "fix": set(), "ids": set()})
                rec["pkgs"].add(dep["name"])
                rec["fix"].update(v.get("fix_versions") or [])
                rec["ids"].add(v["id"])
    return {"cves": out, "versions": versions}


def _ver(text: str | None):
    """解析不了一定回 None，不用宽 except 往外冒。"""
    if text is None or Version is None:
        return None
    try:
        return Version(text)
    except (InvalidVersion, TypeError, ValueError):
        return None


def version_applicable(current: str | None, fixes: set[str]) -> str:
    if not fixes:
        return "无修复版本(未给)⇒不能判不适用"
    if Version is None:
        return "缺 packaging，未算版本"
    cur = _ver(current)
    if cur is None:
        return "版本串无法解析"
    for f in sorted(fixes):
        m = re.search(r"\d", f)
        if not m:
            continue
        cand = _ver(f[m.start() :])
        if cand is not None and cur < cand:
            return f"在受影响区间(<{f[m.start() :]}])"
    return "不在版本区间"


def covered_by_probe() -> set[str]:
    """只认两场读数里真打了桩的 CVE；任何一只桩缺席都不算覆盖。"""
    cov: set[str] = set()
    for pat in PROBE_READINGS:
        for p in sorted(glob.glob(str(EVIDENCE / pat))):
            if ".INVALID" in p:
                continue
            data = json.loads(Path(p).read_text(encoding="utf-8"))
            for rec in data.get("targets", []):
                cov.update(c for c in CVE_RE.findall(str(rec.get("cves", ""))))
    return cov


def build() -> tuple[str, int]:
    reg_text = REG.read_text(encoding="utf-8") if REG.is_file() else ""
    reg_cves = set(CVE_RE.findall(reg_text))
    reg_dates = set(re.findall(r"复审最迟日期\s*(?:为)?\s*\*{0,2}\s*(\d{4}-\d{2}-\d{2})", reg_text))
    p_res, p_inst = latest(SCAN_RESOLVED), latest(SCAN_INSTALLED)
    if p_res is None or p_inst is None:
        return ("缺扫描件：需要 " + SCAN_RESOLVED + " 与 " + SCAN_INSTALLED + "，先复扫。\n"), 1
    res = load_scan(p_res)
    inst = load_scan(p_inst)
    ri, ii = advisory_index(res), advisory_index(inst)
    cov = covered_by_probe()

    rows = sorted(set(ri["cves"]) | set(ii["cves"]))
    in_reg = [c for c in rows if c in reg_cves]
    dev = [c for c in rows if c not in reg_cves]
    stale = sorted(reg_cves - set(rows))
    hit_pkgs_res = {x["name"] for x in res["dependencies"] if x.get("vulns")}
    hit_pkgs_inst = {x["name"] for x in inst["dependencies"] if x.get("vulns")}
    version_drift = sorted(
        f"{p}: 解析 {ri['versions'].get(p)} / 实装 {ii['versions'].get(p)}"
        for p in hit_pkgs_res & hit_pkgs_inst
        if ri["versions"].get(p) != ii["versions"].get(p)
    )
    only_inst = sorted(hit_pkgs_inst - hit_pkgs_res)

    L: list[str] = []
    A = L.append
    A("# 依赖通报的范围对账（由 `b_scope_recount.py` 现生，勿手抄）")
    A("")
    A(f"- 解析集扫描件：`{p_res.name}` —— 命中 **{len(ri['cves'])}** 条通报 / "
      f"**{sum(len(x.get('vulns', [])) for x in res['dependencies'])}** 行 / "
      f"**{len([x for x in res['dependencies'] if x.get('vulns')])}** 个包")
    A(f"- 实装集扫描件：`{p_inst.name}` —— 命中 **{len(ii['cves'])}** 条通报 / "
      f"**{sum(len(x.get('vulns', [])) for x in inst['dependencies'])}** 行 / "
      f"**{len([x for x in inst['dependencies'] if x.get('vulns')])}** 个包")
    A(f"- 两集 CVE 并集 **{len(rows)}** 条；登记表（`residual-risk-review.md`）在册 **{len(reg_cves)}** 条，"
      f"其中与扫描对上的 **{len(in_reg)}** 条")
    A(f"- 闭合检查：`{len(in_reg)} + {len(dev)} == {len(rows)}` -> "
      f"{'PASS' if len(in_reg) + len(dev) == len(rows) else 'FAIL'}")
    A(f"- 登记表里有、今天扫描里**没有**的（须逐条归因，不许当「已修好」）：{stale or '无'}")
    A(f"- 同一包在两集里版本不一致的（不一致 ⇒ 解析集读数不能替实装集说话）：{version_drift or '无'}")
    A(f"- 只在实装集命中、`requirements.txt` 解析集里没有的包：{only_inst or '无'}"
      " ⇒ 这些是**构建/开发期面**，D2 那笔「应用运行时依赖」的签字射程不含它们。")
    A("")
    A("> **两个方向的误读都要挡**：`pip-audit` 只比**本包**版本，公告里的跨包前提（例："
      "某条要求 `torch<2.6`）它**不看** ⇒ 「报告里有」不等于「对本环境适用」；"
      "而 `fix_versions` 为空也**不等于**永久无补丁或不适用。")
    A("")
    A("## 一、逐条对账（分母 = 今天两集并集，不固定为登记表的 26）")
    A("")
    A("| CVE | 命中包 | 解析集版本 | 实装集版本 | 公告修复版本 | 版本适用性(按实装优先) | 探针 | 范围轴 |")
    A("|---|---|---|---|---|---|---|---|")
    for c in rows:
        rec = ri["cves"].get(c) or ii["cves"][c]
        pkgs = sorted(rec["pkgs"])
        rv = "/".join(str(ri["versions"].get(p, "—")) for p in pkgs)
        iv = "/".join(str(ii["versions"].get(p, "—")) for p in pkgs)
        fix = sorted(rec["fix"]) or ["—"]
        # 开发工具只装在实装环境里（requirements 不声明），所以按「实装优先、否则解析」取版本判区间
        verdicts = []
        for p in pkgs:
            use = ii["versions"].get(p) or ri["versions"].get(p)
            src = "实装" if ii["versions"].get(p) else "解析"
            verdicts.append(f"{p}:{version_applicable(use, rec['fix'])}（按{src} {use}）")
        probe = "有桩" if c in cov else "**无桩**"
        axis = "应用运行时(登记表在册)" if c in reg_cves else "**开发工具(登记表外)**"
        A(f"| {c} | {'/'.join(pkgs)} | {rv} | {iv} | {', '.join(fix)} | {'；'.join(verdicts)} | {probe} | {axis} |")
    A("")
    A("## 二、三条范围轴的处置归属")
    A("")
    A(f"1. **应用运行时依赖**（{len(in_reg)} 条在册）：处置与逐项证据在 `residual-risk-review.md`，"
      f"探针覆盖 {len([c for c in in_reg if c in cov])} 条有桩 / {len([c for c in in_reg if c not in cov])} 条无桩；"
      "**无桩那批不是“已排除”**，签字时仍按在册待办处理。")
    A(f"2. **开发/构建工具**（{len(dev)} 条，登记表外：{', '.join(dev) or '无'}）：属于本机与 CI 的构建期面，"
      "**不在 D2「应用运行时依赖」那笔签字的射程内**，既未判定适用、也未判定不适用，保持待处置。")
    A("3. **未被审计的包**（扫描器直接跳过，读数里根本没有它）：")
    skipped = [x for x in inst["dependencies"] if x.get("skip_reason")]
    if not skipped:
        A("   - 本次实装集读数里没有 `skip_reason` 条目 —— **这本身要复核**，别读成“全部已审计”。")
    for x in skipped:
        A(f"   - `{x['name']}`：`{x['skip_reason']}` ⇒ 扫描器**没有**给出任何漏洞读数。"
          "这是**盲区不是零风险**：本地版本要另查官方通报，且不得用解析集里同名包的那个版本替代它。")
    A("")
    A(f"复审期限沿用登记表：{sorted(reg_dates) or '未解析出'}（本页不自行另定日期）。")
    A("")
    A("## 三、本页的自证（防自己变成又一份手抄件）")
    A("")
    A(f"- 本页由 `{Path(__file__).name}` 从上面两份扫描件现生；重跑命令：`python {Path(__file__).name} --write`。")
    ok = len(in_reg) + len(dev) == len(rows) and not stale
    A(f"- 生成时闭合判定：**{'PASS' if ok else 'FAIL'}**"
      f"（在册 {len(in_reg)} + 表外 {len(dev)} = 并集 {len(rows)}；登记表陈旧项 {len(stale)} 条）。")
    return "\n".join(L) + "\n", 0 if ok else 1


def main() -> int:
    text, rc = build()
    print(text, end="")
    if "--write" in sys.argv:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"[written] {OUT}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
