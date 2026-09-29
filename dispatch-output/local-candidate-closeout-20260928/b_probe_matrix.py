"""把 B 档探针读数生成成「逐条公告 -> 运行时判定」表，供报告直接引用。

为什么要脚本：报告里的数字手抄一次就会过期一次，而且没人能复算。这张表由读数文件现生，
连命令一起入库，下一轮接手的人重跑就能对账。

用法：python b_probe_matrix.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

EVIDENCE = Path(__file__).resolve().parent
# Windows 的 stdout 文本模式会把 '\n' 翻成 '\r\n'：本表靠 `python b_probe_matrix.py > xxx.md` 落盘，
# 不钉这一行，生成的报告文件就是 CRLF，跟仓库 `.gitattributes: eol=lf` 的视角对不上、也没法按字节复算哈希。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(newline="\n")  # type: ignore[union-attr]
RISK_REVIEW = EVIDENCE / "residual-risk-review.md"
CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}")
LABEL = {
    "NEVER-IMPORTED": "运行期从未被导入",
    "ZERO-CALL": "在场但 0 次调用",
    "NOT-INSTRUMENTED": "未桩住（仪器缺陷）",
    "SKIPPED-BY-ENV": "被跳过（负向自证）",
}
# 每条公告在 B 档里要问的具体问题；判定语由读数推出来，不预设结论。
QUESTIONS = {
    "G1": "应用是否在运行期把外部内容当作序列化对象或模板配置来重建",
    "G2": "token 计数路径是否会在运行期去抓图片 URL（SSRF/重绑定）",
    "G3": "模型与 config 加载发生在哪、用的是不是钉死的模型名、trust_remote_code 是否放行",
    "G4": "未被应用引用的 loader / 追踪中间件 / Hub 拉取是否在场或被实例化",
}


def latest(pattern: str) -> Path | None:
    cands = sorted(p for p in EVIDENCE.glob(pattern) if not p.name.endswith(".INVALID"))
    return cands[-1] if cands else None


def load(path: Path | None) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else None


def summarize(rec: dict[str, Any]) -> tuple[str, str]:
    """返回（判定, 依据）。依据只写读数里有的东西：调用方、模型名、trust_remote_code 取值。"""
    verdict = str(rec["verdict"])
    key = verdict.split("(")[0].split("::")[0].strip()
    bits: list[str] = []
    if rec["callers"]:
        top = sorted(rec["callers"].items(), key=lambda kv: -kv[1])[:2]
        bits.append("调用方 " + ", ".join(f"{c}×{n}" for c, n in top))
    names = [s.split("|")[1] for s in rec["arg_samples"] if "|" in s]
    if names:
        bits.append("实参首项 " + ", ".join(sorted(set(names))[:2]))
    trc = sorted(set(rec.get("trust_remote_code_values") or []))
    if trc:
        bits.append("trust_remote_code=" + "/".join(trc))
    if key in LABEL:
        bits.insert(0, LABEL[key])
    return verdict, "；".join(bits)


def cve_rollup(fields: dict[str, dict[str, Any] | None]) -> None:
    """把「逐桩判定」折回 `residual-risk-review.md` 的公告清单，并显式列出**探针没覆盖**的行。

    为什么必须连未覆盖一起打：只打覆盖到的，读的人会把"这几行运行期为 0"误读成"这批 CVE 都查过了"。
    末尾闭合检查钉两件事：覆盖 + 未覆盖 == 登记表去重数；桩上标了但登记表没有的公告要显式露出来。
    """
    print("### 公告视角（覆盖到 / 没覆盖到，两张清单都要看）\n")
    by_cve: dict[str, list[tuple[str, str, str]]] = {}
    for fname, data in fields.items():
        if not data:
            continue
        for rec in data["targets"]:
            for cve in CVE_RE.findall(str(rec["cves"])):
                by_cve.setdefault(cve, []).append((str(rec["id"]), fname, str(rec["verdict"])))

    listed_set: list[str] = []
    if RISK_REVIEW.is_file():
        listed_set = sorted(set(CVE_RE.findall(RISK_REVIEW.read_text(encoding="utf-8"))))
    covered = [c for c in listed_set if c in by_cve]
    uncovered = [c for c in listed_set if c not in by_cve]
    extra = sorted(set(by_cve) - set(listed_set))

    print(
        f"登记表 `{RISK_REVIEW.name}` 里的公告去重 {len(listed_set)} 条；"
        f"本探针有桩可答的 {len(covered)} 条，**探针答不上的 {len(uncovered)} 条**。"
    )
    print()
    print("| 公告 | 覆盖它的桩 | 各场判定 |")
    print("| --- | --- | --- |")
    for cve in covered:
        hits = by_cve[cve]
        ids = ", ".join(sorted({h[0] for h in hits}))
        per_field = "; ".join(
            f"{f}: {', '.join(sorted({v for i, ff, v in hits if ff == f}))}" for f in dict.fromkeys(h[1] for h in hits)
        )
        print(f"| {cve} | {ids} | {per_field} |")
    print()
    print("**探针答不上的公告（不许把这栏读成「已排除」）**：" + (", ".join(uncovered) if uncovered else "（无）"))
    if extra:
        print(f"\n⚠️ 桩上标了但登记表没有的行（登记表少行，不是判定错）：{', '.join(extra)}")
    closed = len(covered) + len(uncovered) == len(listed_set)
    print(
        f"\n闭合检查：{len(covered)} + {len(uncovered)} == {len(listed_set)} -> "
        f"{'PASS' if closed else 'FAIL（分类没闭合）'}"
    )


def main() -> int:
    fields = {
        "测试场": load(latest("b-probe-readings-pytest-*.json")),
        "应用路径": load(latest("b-probe-readings-app-*.json")),
    }
    missing = [k for k, v in fields.items() if v is None]
    if missing:
        print(f"FATAL: 缺读数文件，无法生成表：{missing}")
        return 2
    # 表里必须自报"我是从哪个读数文件生的"：否则报告引用这张表时，没人知道它出自哪一批运行
    for name, path in (
        ("测试场", latest("b-probe-readings-pytest-*.json")),
        ("应用路径", latest("b-probe-readings-app-*.json")),
    ):
        if fields[name] is not None and path is not None:
            fields[name]["_source_file"] = path.name

    print("## B 档运行时判定（由读数现生，勿手抄）\n")
    for field, data in fields.items():
        print(f"### {field}\n")
        print(
            f"- 读数文件：`{data.get('_source_file', '?')}`（mode=`{data['mode']}`），"
            f"装桩时刻 {data['installed_at']}，装桩前已加载：{data.get('preloaded_app_at_install') or '无'}"
        )
        print(
            f"- 监视模块在场 {len(data['imports_watched'])} 个；"
            f"外联事件 {data['net_event_kinds']} 类 / {data['net_event_total']} 次"
            f"（另有 compile {data.get('compile_event_total')} 次不计入外联）"
        )
        print(f"- 别名补钉：{data.get('alias_repointed') or '无'}；打桩异常：{data.get('apply_errors') or '无'}\n")
        print("| 组 | 目标 | 公告 | 判定 | 依据 |")
        print("| --- | --- | --- | --- | --- |")
        for rec in data["targets"]:
            grp = str(rec["id"])[:2]
            verdict, basis = summarize(rec)
            print(f"| {grp} | `{rec['id']}` {rec['dotted'].split('.')[-1]} | {rec['cves']} | {verdict} | {basis} |")
        print()

    print("### 每组问题与答（「测到 0 次」与「没测到」分栏，绝不合并）")
    print()
    print(
        "  前一版这里把两样东西混在一个判定集合里打出来（`['NEVER-IMPORTED', 'ZERO-CALL']`），"
        "读起来像「这组都答了、都是 0」。"
        "`NEVER-IMPORTED` 的含义是**这场压根没走到那个模块**，它是「未测」，不是「测到 0 次」的阴性证据。"
    )
    print()
    for grp, q in QUESTIONS.items():
        rows = [r for d in fields.values() for r in d["targets"] if str(r["id"]).startswith(grp)]
        bucket: dict[str, set[str]] = {
            "测到有调用": set(),
            "测到 0 次": set(),
            "未测（模块从未导入）": set(),
            "其他": set(),
        }
        for r in rows:
            key = str(r["verdict"]).split("(")[0].split("::")[0].strip()
            label = str(r["id"])
            if key.startswith("NEVER-IMPORTED"):
                bucket["未测（模块从未导入）"].add(label)
            elif key == "ZERO-CALL":
                bucket["测到 0 次"].add(label)
            elif "CALLS" in key and r["count"]:
                bucket["测到有调用"].add(f"{label}×{r['count']}")
            else:
                bucket["其他"].add(f"{label}={key}")
        print(f"- **{grp}** 问：{q}")
        for name in ("测到有调用", "测到 0 次", "未测（模块从未导入）", "其他"):
            if bucket[name]:
                print(f"    {name}：{', '.join(sorted(bucket[name]))}")
        print(
            "    （同一只桩在两档里同时出现 = 两场结论不同，例如测试场测到 0 次而应用场从未导入，那是「分场」不是矛盾）"
        )

    cve_rollup(fields)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
