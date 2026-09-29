"""主张复算器：把本轮五份文档里写下的每条数字主张，对着入库读数重算一遍。

为什么要这个文件：报告里的数字手抄一次就过期一次，而且没人能复算（本仓已多次踩过）。
这里不做"读一遍觉得没问题"，而是**每条主张独立重算并逐条判 PASS/FAIL**；
任何一条对不上就整体 rc=1，把文档挡在"自以为对"之外。

用法：python b_probe_claim_check.py
"""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path
from typing import Any

EVIDENCE = Path(__file__).resolve().parent
REPO = Path(r"C:/Users/33393/Desktop/ai-legal-helper")
DOCS = [
    REPO / "docs/handoff-local-candidate-closeout-20260929.md",
    REPO / "docs/progress-handoff-report-20260925.md",
    REPO / "docs/assistant-briefs/next-phase-E-integration-report-20260927.md",
    REPO / "docs/superpowers/plans/2026-09-28-local-candidate-closeout-plan.md",
    EVIDENCE / "README.md",
]


def latest(pattern: str) -> dict[str, Any] | None:
    cands = [Path(p) for p in sorted(glob.glob(str(EVIDENCE / pattern))) if not p.endswith(".INVALID")]
    if not cands:
        return None
    return json.loads(cands[-1].read_text(encoding="utf-8"))


def targets(data: dict[str, Any], prefix: str) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in data["targets"] if str(r["id"]).startswith(prefix)}


def verdict_key(rec: dict[str, Any]) -> str:
    return str(rec["verdict"]).split("(")[0].split("::")[0].strip()


RESULTS: list[tuple[str, bool, str]] = []


def claim(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))


def extra_claims(suite: dict[str, Any], app: dict[str, Any]) -> None:
    """本轮新增的主张：复跑一致、脱敏不变量、网络归类、归因件、以及"读数出自现行代码"。

    这几条都是**能红**的：上一版这里曾有一条 `claim(..., True, "人工核对")`，
    一条永远不会红的主张不是复算，是装饰 —— 已删。
    """
    # 1) pytest 自己的摘要行 vs 闸门用的 collected（两个轴必须互相对得上）
    logs = sorted(glob.glob(str(EVIDENCE / "b-probe-pytest-*.log")))
    if logs:
        txt = Path(logs[-1]).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(\d+) passed, (\d+) skipped, (\d+) deselected", txt)
        cm = re.search(r"collected = (\d+)", txt)
        if m and cm:
            passed, skipped, deselected, collected = (int(x) for x in (*m.groups(), cm.group(1)))
            claim(
                "最新测试场日志：passed+skipped == collected",
                passed + skipped == collected,
                f"实得 {passed}+{skipped} vs {collected}",
            )
            claim("最新测试场日志：deselected=18（-m 'not slow'）", deselected == 18, f"实得 {deselected}")
        else:
            claim("最新测试场日志可解析摘要行", False, f"日志 {Path(logs[-1]).name} 缺字段")
    else:
        claim("存在测试场日志", False)

    # 2) 两腿复跑零差异（报告里"逐条一致"这句的机器版）
    cands = [
        Path(p) for p in sorted(glob.glob(str(EVIDENCE / "b-probe-readings-pytest-*.json"))) if ".INVALID" not in p
    ]
    if len(cands) >= 2:
        a, b = (json.loads(p.read_text(encoding="utf-8")) for p in cands[-2:])
        ax = ("verdict", "count", "dry_runs", "callers", "arg_samples")

        def proj(d: dict[str, Any]) -> dict[str, dict[str, Any]]:
            return {
                r["id"]: {k: (sorted(set(r.get(k) or [])) if k in ("callers", "arg_samples") else r[k]) for k in ax}
                for r in d["targets"]
            }

        pa, pb = proj(a), proj(b)
        nd = [f"{t}.{k}" for t in set(pa) & set(pb) for k in ax if pa[t][k] != pb[t][k]]
        claim(
            f"两腿复跑逐桩五轴零差异（{cands[-2].name} vs {cands[-1].name}）",
            not nd and set(pa) == set(pb),
            f"差异 {nd[:5]}",
        )
        same = [f for f in ("collected", "pytest_exitstatus", "compile_event_total") if a.get(f) == b.get(f)]
        claim(
            "两腿完整性三字段一致（collected/exitstatus/compile）",
            len(same) == 3,
            f"一致 {same}",
        )
    else:
        claim("至少两份有效 pytest 读数可复算复跑一致性", False, f"实得 {len(cands)} 份")

    # 3) 网络事件计数自洽（报告引用 kinds/total 两个数，先要读数自己闭合）
    for label, d in (("测试场", suite), ("应用路径场", app)):
        net = d.get("net_events") or {}
        claim(
            f"{label} net 自洽：键数==kinds 且 求和==total",
            len(net) == d.get("net_event_kinds") and sum(net.values()) == d.get("net_event_total"),
            f"实得 键{len(net)}/声明{d.get('net_event_kinds')}，和{sum(net.values())}/声明{d.get('net_event_total')}",
        )

    # 4) 脱敏不变量：urllib.Request 键只允许 URL/方法/头键名，请求体不得进任何读数
    shape = re.compile(r"^urllib\.Request :: \S+ method=\S+ headers\[[^\]]*\]$")
    all_readings = cands + [Path(p) for p in sorted(glob.glob(str(EVIDENCE / "b-probe-readings-app-*.json")))]
    bad_keys: list[str] = []
    body_hits: list[str] = []
    for p in all_readings:
        d = json.loads(p.read_text(encoding="utf-8"))
        for k in d.get("net_events") or {}:
            if not k.startswith("urllib.Request :: "):
                continue
            if not shape.match(k):
                bad_keys.append(f"{p.name}: {k[:70]}")
            if "password" in k.lower() or "|{" in k:
                body_hits.append(f"{p.name}: {k[:70]}")
    claim("urllib.Request 键形状只含 URL/方法/头键名", not bad_keys, f"越形 {len(bad_keys)} 条 {bad_keys[:2]}")
    claim("任何入库读数都不含请求体（口令/JSON 体 0 命中）", not body_hits, f"命中 {body_hits[:2]}")

    # 5) 唯一非环回目的已被归因到用例（不是"反正连不上"就算过）
    tp = EVIDENCE / "b-probe-dns-trace.json"
    if tp.is_file():
        t = json.loads(tp.read_text(encoding="utf-8"))
        hits = t.get("nonloopback_attempts") or []
        claim(
            "归因件：非环回事件恰 1 次且目的是假端点 test.invalid",
            len(hits) == 1 and hits[0].get("host") == "test.invalid",
            f"实得 {len(hits)} 次 {[h.get('host') for h in hits]}",
        )
        claim(
            "归因件：该次来自 /healthz 的模型主机连通探测（用例可指名）",
            bool(hits)
            and "test_healthz" in str(hits[0].get("test"))
            and any("main.py" in f for f in hits[0].get("frames") or []),
            f"实得 {hits[0] if hits else '无'}",
        )
    else:
        claim("存在网络归因件 b-probe-dns-trace.json", False)

    # 6) 出处代次：读数晚于「运行在被测进程里的代码」的最后一次编辑
    code = [EVIDENCE / n for n in ("b_runtime_probe.py", "b_probe_run_suite.py", "b_probe_app_paths.py")]
    newest_code = max((p.stat().st_mtime for p in code if p.is_file()), default=0)
    ap = [Path(p) for p in sorted(glob.glob(str(EVIDENCE / "b-probe-readings-app-*.json")))]
    for label, rp in (("pytest", cands[-1] if cands else None), ("app", ap[-1] if ap else None)):
        ok = rp is not None and rp.stat().st_mtime > newest_code
        claim(
            f"{label} 读数晚于仪器与驱动的最后编辑",
            ok,
            f"读数 {rp.name if rp else '无'} vs 代码 mtime {newest_code:.0f}",
        )
    sp = EVIDENCE / "b-probe-selfcheck.json"
    claim(
        "自检读数同样出自现行仪器",
        sp.is_file() and sp.stat().st_mtime > newest_code,
        f"实得 {'缺件' if not sp.is_file() else format(sp.stat().st_mtime, '.0f')}",
    )


def main() -> int:
    suite = latest("b-probe-readings-pytest-*.json")
    app = latest("b-probe-readings-app-*.json")
    selfchk = None
    sp = EVIDENCE / "b-probe-selfcheck.json"
    if sp.is_file():
        selfchk = json.loads(sp.read_text(encoding="utf-8"))
    if suite is None or app is None:
        print("FATAL: 缺入库读数，无法复算")
        return 2

    # --- 完整性主张 ---
    claim("测试场 collected(selected)=1660", suite.get("collected") == 1660, f"实得 {suite.get('collected')}")
    claim(
        "测试场 pytest exitstatus=0（无失败）",
        suite.get("pytest_exitstatus") == 0,
        f"实得 {suite.get('pytest_exitstatus')}",
    )
    claim(
        "测试场 装桩前应用未加载",
        suite.get("preloaded_app_at_install") == [],
        f"实得 {suite.get('preloaded_app_at_install')}",
    )
    claim(
        "应用路径场 装桩前应用未加载",
        app.get("preloaded_app_at_install") == [],
        f"实得 {app.get('preloaded_app_at_install')}",
    )
    inst = [r for r in (selfchk or {}).get("targets", []) if str(r["install"]).startswith("INSTALLED")]
    installed_n = len(inst)
    claim("自检 桩装上 19/22", installed_n == 19, f"实得 {'无自检读数' if selfchk is None else installed_n}")
    claim(
        "自检 failures 为空",
        selfchk is not None and not selfchk.get("failures"),
        f"实得 {None if selfchk is None else selfchk.get('failures')}",
    )
    claim("打桩异常 apply_errors 两场均空", not suite.get("apply_errors") and not app.get("apply_errors"))

    # --- 组内桩数主张 ---
    counts = {"G1": 7, "G2": 3, "G3": 5, "G4": 7}
    for pref, expect in counts.items():
        got = len(targets(suite, pref))
        claim(f"{pref} 组桩数={expect}", got == expect, f"实得 {got}")
    claim("闭合：总桩数 22 == 四组之和", len(suite["targets"]) == sum(counts.values()), f"实得 {len(suite['targets'])}")

    # --- G1：两场全 ZERO-CALL ---
    for name, data in (("测试场", suite), ("应用路径场", app)):
        recs = targets(data, "G1")
        ks = {verdict_key(r) for r in recs.values()}
        claim(f"G1 {name} 全 ZERO-CALL", ks == {"ZERO-CALL"}, f"实得 {ks}")
        present = all(r["install"] == "INSTALLED" for r in recs.values())
        claim(
            f"G1 {name} 模块在场且已桩住（排除缺席假绿）",
            present
            and all(r["owner_module"] in data["imports_watched"] or r["present_at_install"] for r in recs.values()),
        )

    # --- G2 ---
    claim(
        "G2 测试场 全 ZERO-CALL",
        {verdict_key(r) for r in targets(suite, "G2").values()} == {"ZERO-CALL"},
        f"实得 {sorted(verdict_key(r) for r in targets(suite, 'G2').values())}",
    )
    claim(
        "G2 应用场 只含 NEVER-IMPORTED / ZERO-CALL",
        {verdict_key(r) for r in targets(app, "G2").values()} <= {"NEVER-IMPORTED", "ZERO-CALL"},
    )

    # --- G3：调用次数、归属、模型名、trust_remote_code ---
    for name, data in (("测试场", suite), ("应用路径场", app)):
        recs = targets(data, "G3")
        want = {"G3a": 1, "G3b": 1, "G3c": 0, "G3d": 1, "G3e": 1}
        for tid, expect in want.items():
            rec = recs[tid]
            real = rec["count"] - rec["dry_runs"]
            claim(f"G3 {name} {tid} 真实调用={expect}", real == expect, f"实得 {real}")
        called = [tid for tid, rec in recs.items() if rec["count"] - rec["dry_runs"] > 0]
        callers = {c for tid in called for c in recs[tid]["callers"]}
        claim(
            f"G3 {name} 调用方唯一归到 rag_chain.py:39",
            callers == {"backend/rag_chain.py:39"},
            f"实得 {sorted(callers)}",
        )
        # arg_samples 的形状是 "首位实参|次位... kw=键名表"，取模型名要先截掉 kw= 尾巴
        models = {
            s.split("|")[1].split(" kw=")[0].strip() for tid in called for s in recs[tid]["arg_samples"] if "|" in s
        }
        claim(
            f"G3 {name} 模型名只有 BAAI/bge-base-zh-v1.5", models == {"BAAI/bge-base-zh-v1.5"}, f"实得 {sorted(models)}"
        )
        trc = sorted({v for tid in recs for v in recs[tid].get("trust_remote_code_values", [])})
        if name == "应用路径场":
            claim(
                "G3 应用场 trust_remote_code 取值 = ['False']（只覆盖传该实参的 G3a/G3b；G3d/G3e 实参里没这个键）",
                trc == ["False"],
                f"实得 {trc}",
            )

    # --- G4：缺席面 ---
    g4 = targets(suite, "G4")
    never = sorted(tid for tid, r in g4.items() if verdict_key(r) == "NEVER-IMPORTED")
    zero = sorted(tid for tid, r in g4.items() if verdict_key(r) == "ZERO-CALL")
    claim(
        "G4 测试场 5 只 NEVER-IMPORTED + 2 只 ZERO-CALL", len(never) == 5 and len(zero) == 2, f"实得 {never} / {zero}"
    )
    for mod in ("langchain_community", "langchain.chains", "langsmith.middleware"):
        claim(f"{mod} 两场均从未被导入", mod not in suite["imports_watched"] and mod not in app["imports_watched"])

    # --- 外联分轴 ---
    conn_events = {
        k: v
        for k, v in suite["net_events"].items()
        if k.split(" :: ")[0] in ("socket.connect", "socket.getaddrinfo", "http.client.connect", "urllib.Request")
    }
    hosts: dict[str, int] = {}
    for k, v in conn_events.items():
        m = re.search(r"(127\.0\.0\.1|test\.invalid)", k)
        hosts[m.group(1) if m else "other"] = hosts.get(m.group(1) if m else "other", 0) + v
    claim("测试场 环回连接读数=312", hosts.get("127.0.0.1") == 312, f"实得 {hosts}")
    claim(
        "测试场 外部目的只有 test.invalid=1（故意的不可用假端点）",
        hosts.get("test.invalid") == 1 and "other" not in hosts,
        f"实得 {hosts}",
    )
    app_conn = [
        k
        for k in app["net_events"]
        if k.split(" :: ")[0] in ("socket.connect", "socket.getaddrinfo", "http.client.connect", "urllib.Request")
    ]
    claim("应用路径场 连接类事件=0", not app_conn, f"实得 {len(app_conn)}")
    claim(
        "compile 单独计数（测试场 9826，未混进外联）",
        suite.get("compile_event_total") == 9826,
        f"实得 {suite.get('compile_event_total')}",
    )

    # --- 应用路径两步的结果 ---
    res = app.get("results") or {}
    claim("upload 步骤写入 2 个切片", (res.get("upload") or {}).get("chunks_written") == 2, f"实得 {res.get('upload')}")
    # 这条以前只断言 "retrieved" in qa —— 名字里的"跑通""未调用生成模型"一个字都没测，是名实不符的主张。
    claim(
        "qa 步骤真的跑通（failures 空 + retrieved 字段可读）",
        not (app.get("failures") or []) and isinstance((res.get("qa") or {}).get("retrieved"), int),
        f"实得 failures={app.get('failures')} qa={(res.get('qa') or {}).get('retrieved')}",
    )
    claim(
        "qa 步骤 retrieved==0（空副本集合使然，不是检索质量结论）",
        (res.get("qa") or {}).get("retrieved") == 0,
        f"实得 {(res.get('qa') or {}).get('retrieved')}",
    )
    claim(
        "应用路径场未构造 LLM 客户端 ⇒ G2 在该场是「未测」不是「阴性」"
        "（langchain_openai.chat_models.base 不在该场在场模块里，却在测试场在场）",
        "langchain_openai.chat_models.base" not in (app.get("imports_watched") or {})
        and "langchain_openai.chat_models.base" in (suite.get("imports_watched") or {}),
        f"实得 app={('langchain_openai.chat_models.base' in (app.get('imports_watched') or {}))} "
        f"suite={('langchain_openai.chat_models.base' in (suite.get('imports_watched') or {}))}",
    )

    # --- 文档里不该再出现已被推翻的说法 ---
    # 先钉"五份文档都在"：以前 `if d.is_file()` 会让改名的文档静默跳过整条检查 ⇒ 空过。
    absent = [str(d) for d in DOCS if not d.is_file()]
    claim(f"复算器要扫的 {len(DOCS)} 份文档全部在位", not absent, f"缺 {absent}")
    banned = ["G1 Core 反序列化与模板构造 8 只桩", "8 只桩"]
    text_all = "\n".join(d.read_text(encoding="utf-8") for d in DOCS if d.is_file())
    for b in banned:
        hit = b in text_all
        claim(f"文档中不应残留「{b}」", not hit)

    extra_claims(suite, app)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("=== 主张复算逐条 ===")
    for name, ok, detail in RESULTS:
        mark = "PASS" if ok else "FAIL"
        extra = "" if ok or not detail else f"   [{detail}]"
        print(f"  [{mark}] {name}{extra}")
    print(f"\n合计 {passed}/{len(RESULTS)} 条通过")
    out = EVIDENCE / "b-probe-claim-check.json"
    with open(str(out), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(
            {
                "passed": passed,
                "total": len(RESULTS),
                "results": [{"claim": n, "ok": ok, "detail": d} for n, ok, d in RESULTS],
            },
            fh,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    print(f"读数 -> {out}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
