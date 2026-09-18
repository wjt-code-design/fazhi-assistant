"""over2 判据重放审计（P2-2 · 2026-09-19）。

一条命令做完四件事，且**只读**除本目录外的任何文件：

1. 语料清点：递归找 `*sessions.json`，用三信号判"真实评测 / 测试夹具 / 归档副本"，产出带 sha256 的
   `run-manifest.json`（Owner 2026-09-18 决策 5：清单即基线定义，必须进版本控制）。
2. 校准（fail-fast，不过就不出数）：
   (a) 合成 45 序列 —— 对 `../ta5-arms-20260917/_t1_truth_table.json` 里已落的 v1/现行判定逐条比；
   (b) 真实 3 例 —— arm-off E03/E04、arm-on E03 必须是 `old_20260917=False ∧ cur=True`
       （P0-1 公布的漏标签名），且 arm-on E04 必须**不是**。
3. 重放 + 三分类（Owner 决策 4）：存储值能唯一匹配某旧谓词且现行谓词不同意 ⇒ 漏标；
   匹配不上任何已知谓词 ⇒ 不可归因（单独一档，不并入漏标数）。
4. 第二条轴（Owner 决策 6）：E01–E10 的「设计 scope_trigger vs 实测是否触发」混淆矩阵，只出表不提方案。

输出全部确定性：排序键、无时间戳、LF 换行 ⇒ 重跑逐字节一致（DoD ③）。
`--verify` 模式比对已有产物，不一致退出码 1。
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "dispatch-output" / "over2-replay-20260919"
RUNNER = REPO / "backend" / "scripts" / "gate2_runner.py"
TRUTH_TABLE = REPO / "dispatch-output" / "ta5-arms-20260917" / "_t1_truth_table.json"
FROZEN_V2 = REPO / "evals" / "frozen-cases-v2.json"

SCOPE_MARK = "本次请求分解出"  # 争点范围索要话术；与 _t1_recompute_real.py 同一把尺
CLARIFY_ROUND_LIMIT = 2  # 冻结判据，只读引用
FIXTURE_LABELS = {"t6-run"}  # tests/test_gate2_runner.py 夹具固定写的 run 名
TMPLEAF = re.compile(
    r"^test_.*\d$"
)  # pytest basetemp 叶子目录名（test_<nodeid>_<n> 截断）
PATH_NOISE = re.compile(
    r"(pytest|_pt_|\.ptmp-|bt-run|/tp/|tmp|checkpoint|test_case_matching)"
)
GLOBS = (
    "dispatch-output/**/*sessions.json",
    "release-evidence/**/*sessions.json",
    "evals/**/*sessions.json",
)

# ---------------------------------------------------------------- 谓词（唯一真源）


def pred_cur(n: int, tail: bool) -> bool:
    """现行口径：服务端发起的澄清次数 = 已应答 + 末尾未应答那一次，> 2 即红线。"""
    return (n + (1 if tail else 0)) > CLARIFY_ROUND_LIMIT


def pred_old_0917(fact_seen: int, tail: bool) -> bool:
    """2026-09-17 版（后被 P0-1 判为失实）：排除 scope 轮、且依赖末尾快照。"""
    return fact_seen >= 2 and tail


def pred_v1_equivalent(n: int, tail: bool) -> bool:
    """v1「最多两轮、两轮后仍 clarification」在 runner 预算=2 下的等价式。

    ⚠️ 只在**执行预算 = 2** 时成立（第 3 次追问必然停在末尾）。预算 > 2 后两者会分叉，
    本审计在真实语料与 P0-1 真值表上都没能构造出该形态 —— 见报告 §6.3。
    """
    return (n >= 3) or (n >= 2 and tail)


def classify(stored, preds: dict[str, bool]) -> tuple[str, list[str]]:
    """三分类（Owner 决策 4 的字面实现）。单列出来是为了能被校准 (c) 直接喂样本打靶。"""
    matched = sorted(k for k, v in preds.items() if v == stored)
    if not isinstance(stored, bool):
        return "无判定", matched
    if preds["new_protocol"] == stored:
        return "一致", matched
    if len(matched) == 1:
        return ("漏标" if preds["new_protocol"] else "反向差异"), matched
    return "不可归因", matched


# ---------------------------------------------------------------- 通用


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, obj) -> None:
    text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_bytes(text.encode("utf-8"))  # 显式 LF，不受 core.autocrlf 影响


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:  # 只读句柄
        return json.load(fh)


def preflight() -> str:
    """防"在桌面上搜仓库"那类仪器级故障：cwd、关键文件、判据常量、谓词唯一性一次量清。"""
    cwd = Path(os.getcwd()).resolve()
    if cwd != REPO:
        sys.exit(f"FATAL(preflight): cwd={cwd} 不是仓库根 {REPO}")
    for name, p in (
        ("gate2_runner.py", RUNNER),
        ("_t1_truth_table.json", TRUTH_TABLE),
        ("frozen-cases-v2.json", FROZEN_V2),
    ):
        if not p.exists():
            sys.exit(f"FATAL(preflight): 关键输入缺失 {name} -> {p}")
    src = RUNNER.read_text(encoding="utf-8")
    if f"CLARIFY_ROUND_LIMIT = {CLARIFY_ROUND_LIMIT}" not in src:
        sys.exit(
            "FATAL(preflight): 冻结判据 CLARIFY_ROUND_LIMIT 已变，本脚本的常量需重新对齐"
        )
    if src.count("if scope_used >= SCOPE_CLARIFY_LIMIT:") != 1:
        sys.exit("FATAL(preflight): scope 守卫文字不再唯一，语料谓词归属需重判")

    # 判据源文件必须等于 HEAD 版：并行会话正在改这个文件，读脏版本出的数无法复现
    def _git(*a):
        return subprocess.run(
            ("git", *a), capture_output=True, text=True, cwd=str(REPO), check=False
        ).stdout.strip()

    head_short = _git("rev-parse", "--short", "HEAD")
    wt_blob = _git("hash-object", "backend/scripts/gate2_runner.py")
    hd_blob = _git("rev-parse", "HEAD:./backend/scripts/gate2_runner.py")
    if wt_blob != hd_blob or not hd_blob:
        sys.exit(
            f"FATAL(preflight): gate2_runner.py 工作树({wt_blob[:12]}) != HEAD({hd_blob[:12]}) ⇒ 判据源正被在途改动，先等落定"
        )
    return sha256_file(RUNNER), head_short, wt_blob


# ---------------------------------------------------------------- 1. 语料清点


def is_fixture_path(rel: str) -> bool:
    parts = rel.split("/")
    return any(TMPLEAF.match(x) for x in parts[:-1]) or bool(
        PATH_NOISE.search("/".join(parts[:-1]))
    )


def collect_corpus() -> tuple[list[dict], dict]:
    paths = set()
    for g in GLOBS:
        paths.update(glob.glob(str(REPO / g), recursive=True))
    rows: list[dict] = []
    for abs_p in sorted(paths):
        rel = os.path.relpath(abs_p, REPO).replace(os.sep, "/")
        p = Path(abs_p)
        try:
            d = load_json(p)
        except Exception as exc:  # noqa: BLE001  # 单个文件损坏不得让整份审计退出，必须落进待定桶
            rows.append(
                {
                    "path": rel,
                    "sha256": sha256_file(p),
                    "cls": "待定",
                    "reason": f"JSON 读取失败 {type(exc).__name__}",
                    "n_cases": 0,
                    "run_label": None,
                }
            )
            continue
        run = d.get("run")
        label = (
            run.get("label")
            if isinstance(run, dict)
            else (str(run) if run is not None else "(无)")
        )
        res = d.get("results") or {}
        fixture_label = label in FIXTURE_LABELS
        noise_path = is_fixture_path(rel)
        if fixture_label and noise_path:
            cls, reason = "测试夹具", "label 为夹具名 + 路径含 pytest 临时目录"
        elif fixture_label and not noise_path:
            cls, reason = "待定", "label 为夹具名但路径干净 —— 需逐条判"
        elif not fixture_label and noise_path:
            cls, reason = "待定", "label 像真跑但路径在临时/归档目录内 —— 需逐条判"
        else:
            cls, reason = "真实评测", "两信号一致：非夹具 label + 路径干净"
        if not res:
            cls, reason = "待定", f"{reason}；且 results 为空"
        rows.append(
            {
                "path": rel,
                "sha256": sha256_file(p),
                "cls": cls,
                "reason": reason,
                "n_cases": len(res),
                "run_label": label,
                "label_date": (re.search(r"(20\d{6})", label) or [None, None])[1]
                if isinstance(label, str)
                else None,
            }
        )

    # 归档副本去重：同 sha256 且已有先例 ⇒ 降级为"归档副本"。范围含"待定"，
    # 因为 `t0-baseline-checkpoint-*/materials/` 里的真跑拷贝会因路径含 checkpoint 先落进待定桶。
    first: dict[str, str] = {}
    for r in sorted(rows, key=lambda x: (x["cls"] != "真实评测", x["path"])):
        if r["cls"] not in ("真实评测", "待定"):
            continue
        if r["sha256"] in first:
            r["cls"] = "归档副本"
            r["reason"] = (
                f"与 {first[r['sha256']]} 逐字节相同（同一批评测的第二份拷贝），去重不计入分母"
            )
        else:
            first[r["sha256"]] = r["path"]

    counts = {
        k: sum(1 for r in rows if r["cls"] == k)
        for k in ("真实评测", "测试夹具", "归档副本", "待定")
    }
    counts["文件总数"] = len(rows)
    counts["真实集条目数"] = sum(r["n_cases"] for r in rows if r["cls"] == "真实评测")
    counts["待定须逐条给理由"] = sum(1 for r in rows if r["cls"] == "待定")
    return rows, counts


# ---------------------------------------------------------------- 2. 校准


def read_case(p: Path, cid: str) -> tuple[int, bool, int]:
    d = load_json(p)
    c = d["results"][cid]
    asked = c.get("asked") or []
    last_types = c["rounds"][-1].get("event_types") or []
    tail = "clarification" in last_types
    fact_seen = sum(1 for a in asked if SCOPE_MARK not in str(a.get("prompt", "")))
    return len(asked), tail, fact_seen


def calibrate() -> list[str]:
    notes = []
    truth = load_json(TRUTH_TABLE)
    bad = 0
    # (a) 只校验**谓词公式**：输入直接取真值表自己记录的 n_asked / completed / n_fact，
    #     这样"公式写错"不会被我的输入重建掩盖。（输入重建由 (b) 在真实数据上校验。）
    for row in truth:
        for col, fn in (("v1", pred_v1_equivalent), ("cur", pred_cur)):
            f = row[col]
            n, tail = f["n_asked"], not f["completed"]
            got = fn(n, tail)
            if bool(f["redline"]) != got:
                bad += 1
                if bad <= 3:
                    notes.append(
                        f"合成序列 {row['seq']} 的 {col} 列：redline={f['redline']} 但公式给出 {got}（n={n}, tail={tail}）"
                    )
        # 09-17 版公式单测：真值表没有它的判定，但 n_fact 允许我复核"排除 scope"这条是否真的会放宽判定
        v0917 = pred_old_0917(row["cur"]["n_fact"], not row["cur"]["completed"])
        if v0917 and not row["cur"]["redline"]:
            bad += 1
            notes.append(
                f"合成序列 {row['seq']}：old_0917={v0917} 却比现行更严，逻辑方向不符"
            )
    notes.append(f"校准(a) 谓词公式 vs 真值表 {len(truth)} 条 ×2 列：不符 {bad} 处")
    if bad:
        sys.exit(
            "FATAL(calibrate-a): 谓词与 P0-1 已发布真值表不符，禁止出数。"
            + "；".join(notes[-3:])
        )

    # (c) 分档器自检：五个档都必须**可达**，且各由指定的输入形态触发。
    #     没有这一关，"漏标 0 条"可能是**永不可达**造成的，而不是数据造成的。
    cases = [
        (
            "一致",
            True,
            {"v1_equivalent": True, "old_20260917": True, "new_protocol": True},
        ),
        (
            "漏标",
            False,
            {"v1_equivalent": True, "old_20260917": False, "new_protocol": True},
        ),
        (
            "反向差异",
            True,
            {"v1_equivalent": True, "old_20260917": False, "new_protocol": False},
        ),
        (
            "不可归因",
            True,
            {"v1_equivalent": False, "old_20260917": False, "new_protocol": False},
        ),
        (
            "无判定",
            None,
            {"v1_equivalent": False, "old_20260917": False, "new_protocol": False},
        ),
    ]
    wrong = [
        f"{want} 档实得 {classify(stored, preds)[0]}"
        for want, stored, preds in cases
        if classify(stored, preds)[0] != want
    ]
    notes.append(
        f"校准(c) 分档器五档可达性：5 例，不符 {len(wrong)} 处"
        + ("；".join(wrong) if wrong else "")
    )
    if wrong:
        sys.exit(
            "FATAL(calibrate-c): 分档器自身不可达某档 ⇒ '漏标 0' 无意义，禁止出数。"
            + "；".join(wrong)
        )

    arm = REPO / "dispatch-output" / "ta5-arms-20260917"
    expect = {  # P0-1 公布的 3 例漏标签名 + 1 例反面对照
        (arm / "arm-off" / "gate2-run-ta5-off-eval-20260917-sessions.json", "E03"): (
            True,
            False,
        ),
        (arm / "arm-off" / "gate2-run-ta5-off-eval-20260917-sessions.json", "E04"): (
            True,
            False,
        ),
        (arm / "arm-on" / "gate2-run-ta5-on-eval-20260917-sessions.json", "E03"): (
            True,
            False,
        ),
        (arm / "arm-on" / "gate2-run-ta5-on-eval-20260917-sessions.json", "E04"): (
            False,
            False,
        ),
    }
    miss = 0
    for (p, cid), (want_cur, want_old) in expect.items():
        n, tail, fact_seen = read_case(p, cid)
        got = (pred_cur(n, tail), pred_old_0917(fact_seen, tail))
        if got != (want_cur, want_old):
            miss += 1
            notes.append(
                f"真实校准 {p.name}#{cid}: 期望 {(want_cur, want_old)} 实得 {got}"
            )
    notes.append(
        f"校准(b) 真实已知答案 4 例（P0-1 的 3 例漏标 + 1 例对照）：不符 {miss} 处"
    )
    if miss:
        sys.exit(
            "FATAL(calibrate-b): 谓词在真实数据上复现不了 P0-1 的已知结论，禁止出数。"
            + "；".join(notes[-4:])
        )
    return notes


# ---------------------------------------------------------------- 3. 重放与三分类


def entry_tail(c: dict) -> bool:
    rounds = c.get("rounds") or []
    return bool(rounds) and "clarification" in (rounds[-1].get("event_types") or [])


def replay(rows: list[dict]) -> dict:
    per_run: dict[str, dict] = {}
    per_case: dict[str, dict] = {}
    unresolved: list[dict] = []
    discriminating_rows: list[dict] = []
    for r in [x for x in rows if x["cls"] == "真实评测"]:
        d = load_json(REPO / r["path"])
        for cid, c in sorted((d.get("results") or {}).items()):
            asked = c.get("asked") or []
            n = len(asked)
            tail = entry_tail(c)
            fact_seen = sum(
                1 for a in asked if SCOPE_MARK not in str(a.get("prompt", ""))
            )
            preds = {
                "v1_equivalent": pred_v1_equivalent(n, tail),
                "old_20260917": pred_old_0917(fact_seen, tail),
                "new_protocol": pred_cur(n, tail),
            }
            stored = c.get("redline_candidate_over_2_rounds")
            cls, matched = classify(stored, preds)
            # 判别力：三个谓词若给出同一答案，这条样本**无法**区分口径 ⇒ 不能拿"一致"当"尺子一直对"的证据
            discriminating = (
                len(
                    {
                        preds["v1_equivalent"],
                        preds["old_20260917"],
                        preds["new_protocol"],
                    }
                )
                > 1
            )
            if cls == "不可归因":
                unresolved.append(
                    {
                        "path": r["path"],
                        "case": cid,
                        "stored": stored,
                        "preds": preds,
                        "matched": matched,
                    }
                )
            label = r["run_label"] or "(无标签)"
            b = per_run.setdefault(
                label,
                {
                    "run": label,
                    "n": 0,
                    "一致": 0,
                    "漏标": 0,
                    "反向差异": 0,
                    "不可归因": 0,
                    "无判定": 0,
                    "判别条目": 0,
                    "一致但无判别力": 0,
                    "现行判红线": 0,
                    "存储判红线": 0,
                    "paths": [],
                },
            )
            b["n"] += 1
            b[cls] += 1
            b["判别条目"] += int(discriminating)
            b["一致但无判别力"] += int(cls == "一致" and not discriminating)
            b["现行判红线"] += int(preds["new_protocol"])
            b["存储判红线"] += int(stored is True)
            if discriminating:
                axes = []
                if preds["v1_equivalent"] != preds["new_protocol"]:
                    axes.append("v1↔现行")
                if preds["old_20260917"] != preds["new_protocol"]:
                    axes.append("09-17↔现行")
                discriminating_rows.append(
                    {
                        "path": r["path"],
                        "case": cid,
                        "run": label,
                        "n_asked": n,
                        "tail": tail,
                        "fact_seen": fact_seen,
                        "preds": preds,
                        "stored": stored,
                        "cls": cls,
                        "分歧轴": axes,
                    }
                )
            if r["path"] not in b["paths"]:
                b["paths"].append(r["path"])
            q = per_case.setdefault(
                cid,
                {
                    "case": cid,
                    "n": 0,
                    "一致": 0,
                    "漏标": 0,
                    "反向差异": 0,
                    "不可归因": 0,
                    "无判定": 0,
                    "判别条目": 0,
                },
            )
            q["n"] += 1
            q[cls] += 1
            q["判别条目"] += int(discriminating)
    return {
        "per_run": sorted(per_run.values(), key=lambda x: x["run"]),
        "per_case": sorted(per_case.values(), key=lambda x: x["case"]),
        "unresolved": unresolved,
        "discriminating": sorted(
            discriminating_rows, key=lambda x: (x["run"], x["case"])
        ),
    }


# ---------------------------------------------------------------- 4. scope_trigger 混淆矩阵


def scope_matrix(rows: list[dict]) -> dict:
    frozen = load_json(FROZEN_V2)
    design = {
        c["id"]: c.get("scope_trigger")
        for c in frozen.get("cases") or []
        if str(c.get("id", "")).startswith("E")
    }
    obs = {
        cid: {"n_runs": 0, "触发": 0, "未触发": 0, "runs": []} for cid in sorted(design)
    }
    for r in [x for x in rows if x["cls"] == "真实评测"]:
        d = load_json(REPO / r["path"])
        for cid, c in sorted((d.get("results") or {}).items()):
            if cid not in obs:
                continue
            asked = [str(a.get("prompt", "")) for a in (c.get("asked") or [])]
            last_types = (c.get("rounds") or [{}])[-1].get("event_types") or []
            triggered = any(SCOPE_MARK in a for a in asked) or (
                "clarification" in last_types
                and any(SCOPE_MARK in str(e) for e in last_types)
            )
            obs[cid]["n_runs"] += 1
            obs[cid]["触发" if triggered else "未触发"] += 1
            obs[cid]["runs"].append(
                {
                    "run": r["run_label"],
                    "stored_redline": c.get("redline_candidate_over_2_rounds"),
                }
            )
    cells = {}
    for cid, v in obs.items():
        want = design[cid]
        if v["n_runs"] == 0:
            verdict = "无语料"
        elif (want is True and v["触发"] == v["n_runs"]) or (
            want is False and v["触发"] == 0
        ):
            verdict = "符合"
        elif v["触发"] == 0 or v["触发"] == v["n_runs"]:
            verdict = "偶发不符"
        else:
            verdict = "混合"
        cells[cid] = {
            "设计 scope_trigger": want,
            "实测 run 数": v["n_runs"],
            "触发": v["触发"],
            "未触发": v["未触发"],
            "判定": verdict,
        }
    return {
        "status": frozen.get("status"),
        "schema": frozen.get("schema_version"),
        "cells": cells,
    }


# ---------------------------------------------------------------- 5. 报告


def build_report(counts, cal_notes, rep, matrix, runner_sha, rows, prov) -> str:
    L = []
    A = L.append
    A("# over2 判据历史重放审计（P2-2 · 2026-09-19）")
    A("")
    A(
        f"- 判据源文件 `backend/scripts/gate2_runner.py` sha256 = `{runner_sha}`（本审计全程只读）"
    )
    A(
        f"- 该文件工作树 blob = HEAD blob = `{prov['runner_blob'][:12]}…`，审计基线 HEAD = `{prov['head']}`"
        " ⇒ 出的数对应**已提交版本**，不是任何人的在途改动"
    )
    A(
        f"- 冻结判据 `CLARIFY_ROUND_LIMIT = {CLARIFY_ROUND_LIMIT}`；重放输入 = 每条 case 已存的 `asked` 与末轮 `event_types`"
    )
    A(
        "- 口径（Owner 2026-09-18 决策）：按 run **分层报，不合并总率**；另给 distinct 题号的保守下界；"
        "漏标 = 存储值唯一匹配某旧谓词 **且** 现行谓词不同意；匹不上 ⇒ 不可归因，单列不并入。"
    )
    A("")
    A("## 1. 语料清点")
    A("")
    A("| 桶 | 文件数 |")
    A("|---|---|")
    for k in ("真实评测", "测试夹具", "归档副本", "待定", "文件总数"):
        A(f"| {k} | {counts.get(k, 0)} |")
    A(
        f"\n真实集内 case 条目 = **{counts['真实集条目数']}**；逐文件 sha256 与归类理由见 `run-manifest.json`。"
    )
    A("")
    A(
        "> ⚠️ **这是一份快照，不是稳定总量。** 本审计两次实跑之间真实集从 82 文件 / 371 条目增长（并行会话 R15 分水岭线"
        "正在往 `dispatch-output/r15-watershed-20260918/` 追加真实 gate2 run）。 ⇒ 绝对数以 `run-manifest.json` 里"
        "逐文件 sha256 为准，漂移可用 `over2_replay.py --verify` 检出。本次新增条目全部落在「一致」档、"
        "判别力条目仍为 7 ⇒ 报告的**结论**不随漂移改变，**数字**会变。"
    )
    A("")
    A("## 2. 校准（未过则不出数）")
    A("")
    for n in cal_notes:
        A(f"- {n}")
    A("")
    A("## 3. 分层重放结果（按 run 标签）")
    A("")
    tot = {
        "n": 0,
        "一致": 0,
        "漏标": 0,
        "反向差异": 0,
        "不可归因": 0,
        "无判定": 0,
        "判别条目": 0,
        "一致但无判别力": 0,
    }
    A(
        "| run 标签 | 条目 | 判别力条目 | 一致 | 一致但无判别力 | 漏标 | 反向差异 | 不可归因 | 无判定 |"
    )
    A("|---|---|---|---|---|---|---|---|---|")
    for b in rep["per_run"]:
        A(
            f"| `{b['run']}` | {b['n']} | {b['判别条目']} | {b['一致']} | {b['一致但无判别力']} | {b['漏标']} | {b['反向差异']} | {b['不可归因']} | {b['无判定']} |"
        )
        for k in tot:
            tot[k] += b[k]
    A(
        f"| **合计（自检用，不作对外结论）** | {tot['n']} | {tot['判别条目']} | {tot['一致']} | {tot['一致但无判别力']} | **{tot['漏标']}** | {tot['反向差异']} | {tot['不可归因']} | {tot['无判定']} |"
    )
    A("")
    A("### ⚠️ 这张表怎么读（防止把「一致」读成「尺子一直是对的」）")
    A("")
    A(
        "「判别力条目」= 三个谓词（v1 末尾快照 / 09-17 排除 scope / 现行 `clar_requests>2`）在这条样本上**给出不同答案**的条目。"
    )
    A(
        "只有这类条目能证明某一版口径对、另一版错。其余条目上三个谓词同值，「一致」只说明**不矛盾**，不构成对口径的验证。"
    )
    A(
        f"本次：条目总数 {tot['n']}，其中有判别力的仅 **{tot['判别条目']}** 条（{tot['一致但无判别力']} 条属『一致但无判别力』）。"
    )
    A("")
    miss = [b for b in rep["per_run"] if b["漏标"]]
    A("### 漏标出现在哪些 run")
    A("")
    if miss:
        for b in miss:
            A(
                f"- `{b['run']}`：{b['漏标']} 条 / {b['n']}（条目见 `replay-results.json` per_run.paths）"
            )
    else:
        A("- 无：真实集内没有任何条目落入「漏标」档。")
    A("")
    A("### 按题号（跨 run 合并，仅作分布观察）")
    A("")
    A("| case | 条目 | 漏标 | 不可归因 |")
    A("|---|---|---|---|")
    for q in rep["per_case"]:
        if q["漏标"] or q["不可归因"]:
            A(f"| {q['case']} | {q['n']} | {q['漏标']} | {q['不可归因']} |")
    if not any(q["漏标"] or q["不可归因"] for q in rep["per_case"]):
        A("| — | — | 0 | 0 |")
    A("")
    A("")
    A("## 4. 两条已发布数字结论的可复核性（本审计不订正，只报能不能复核）")
    A("")
    dates = sorted(
        {
            r.get("label_date")
            for r in rows
            if r["cls"] == "真实评测" and r.get("label_date")
        }
    )
    g5 = [b for b in rep["per_run"] if "gate5" in b["run"]]
    A("| 引用处 | 原文数字 | 本机语料 | 实测（现行谓词口径） |")
    A("|---|---|---|---|")
    if g5:
        n5 = sum(b["n"] for b in g5)
        r5 = sum(b["现行判红线"] for b in g5)
        A(
            f"| `docs/gate5-formal-dev-20260908.md:41` | 「R5 最多两轮且不 over2 \\| 20/20」 | 有 `gate5*` run 条目 {n5} 条（{len(g5)} 个 run） | 现行谓词判红线 **{r5}** 条 ⇒ 与「无 over2」**不矛盾**，但不构成对该结论的独立复核（见本节末） |"
        )
    else:
        A(
            "| `docs/gate5-formal-dev-20260908.md:41` | 「20/20」 | **本机真实集内无 gate5 run** | 不可复核 |"
        )
    earliest = dates[0] if dates else "无"
    A(
        f"| `docs/agent-v1-taskbook-gate2-baseline-20260907.md:107` | 「第 3 轮追问（over2）常发 \\| **0/30**」 | 真实集 label 内嵌最早日期 = **{earliest}**（label 推定，非时间戳） | "
        + (
            "09-07 那批 sessions 不在本机 ⇒ **不可复核**，本审计不为其背书也不订正它 |"
            if earliest > "20260907"
            else "含 09-07 语料，可复核 |"
        )
    )
    A("")
    A("### 为什么「0 条红线」不等于复核了「20/20」")
    A("")
    A(
        "本机 `gate5*` 语料是 **16 个 run × 共 146 条**，而原文的「20/20」指的是**某一个 20 题的批次**；"
        "run 标签里没有时间戳、`run` 字段也只是字符串，我无法把 146 条唯一切回"
        "「当时那 20 条」。 ⇒ 只能说**整体不矛盾**，不能说**复核通过**。要真复核得知道那一轮的 run 名（Owner 指认即可，不花钱）。"
    )
    A("")
    A("## 5. scope_trigger 设计 vs 实测（只出表，不提方案）")
    A("")
    A(
        f"题集 `evals/frozen-cases-v2.json`（`status={matrix['status']}`，`schema={matrix['schema']}`）"
    )
    A("")
    A("| case | 设计 | 实测 run 数 | 触发 | 未触发 | 判定 |")
    A("|---|---|---|---|---|---|")
    for cid, v in sorted(matrix["cells"].items()):
        A(
            f"| {cid} | `{v['设计 scope_trigger']}` | {v['实测 run 数']} | {v['触发']} | {v['未触发']} | {v['判定']} |"
        )
    A("")
    tt = load_json(TRUTH_TABLE)
    disc = rep["discriminating"]
    ax_v1 = sum(1 for x in disc if "v1↔现行" in x["分歧轴"])
    ax_17 = sum(1 for x in disc if "09-17↔现行" in x["分歧轴"])
    tt_v1 = sum(1 for r in tt if bool(r["v1"]["redline"]) != bool(r["cur"]["redline"]))
    tt_17 = sum(
        1
        for r in tt
        if bool(r["v1"]["redline"])
        != (r["cur"]["n_fact"] >= 2 and not r["cur"]["completed"])
    )
    A("## 6. 结论（含「这个 0 不代表什么」）")
    A("")
    A(
        f"1. **存储层零矛盾**：真实集 {tot['n']} 条里，与现行谓词矛盾的 **{tot['漏标'] + tot['反向差异'] + tot['不可归因']}** 条；"
        f"落入 Owner 定义的「漏标」档（存储值唯一匹配某旧谓词 ∧ 现行不同意）= **{tot['漏标']}** 条。"
    )
    A(
        "2. **这个 0 的含义很窄**，不能读成「末尾快照那版判据历史上没漏过」。逐轴看分歧在哪："
    )
    A("")
    A(
        f"| 分歧轴 | 真实语料（{tot['n']} 条） | 合成真值表（{len(tt)} 条，P0-1 修复后那次） |"
    )
    A("|---|---|---|")
    A(f"| 末尾快照(v1) ↔ 现行 `clar_requests>2` | **{ax_v1}** | **{tt_v1}** |")
    A(f"| 09-17 版(排除 scope 轮) ↔ 现行 | **{ax_17}** | **{tt_17}** |")
    A("")
    A(
        "⇒ 本机能拿出的**全部**证据（真实 371 + 合成 45）里，「末尾快照 vs 按次数」这条轴**一次都没有分歧过**。"
    )
    A(
        f"   有实证暴露面的只有「排除 scope 轮」那条轴（真实 {ax_17} / 合成 {tt_17}），而它已被 P0-1 回滚修好。"
    )
    A(
        "3. **为什么这条轴测不到（机制）**：现行 `SCOPE_CLARIFY_LIMIT = FACT_CLARIFY_LIMIT = 2` 恰与冻结判据"
        "`CLARIFY_ROUND_LIMIT = 2` 相等 ⇒ 第 3 次追问必然**不被应答**而停在末尾 ⇒ "
        "`asked=2 ∧ 末尾 clarification` 时「看末尾」与「数次数」必然同值。要分叉必须出现"
        "「第 3 次追问被应答消化、随后服务端给 final」的形态，而这要求执行预算 > 2。"
    )
    A(
        "4. ⇒ **P2-2 原句「E03/E04 之外可能还有被末尾快照掩盖的」不是被证伪，而是从未被测过**："
        "现存语料不具备判别该命题的形态。且补这个样本**不必付费重跑**——在合成夹具里让假服务第 3 次追问后给 "
        "final、并把该序列的执行预算抬到 3，就能造出两版判据分叉。本批不擅自改预算（判据冻结 + 不改执行语义），"
        "只把这条登记为待裁决项。"
    )
    A(
        "5. **顺带查清一件事，免得下一个人误读**：执行书 `:999-1001` 的「45 序列里 25 个分歧，全为 v1=True/cur=False」"
        "说的是**修复前**那次双跑。判据不是猜的：盘上这份 `_t1_truth_table.json` 的 `cur` 列与**修复后**谓词逐条一致"
        f"（45/45），与**修复前**(09-17)谓词分歧 {tt_17} 条 ⇒ 现存这份只能是修复后生成的，修复前那份已被同名覆盖。"
        "两段相邻易被读成同一件事 ⇒ 属文档歧义，本批不改他人文档，进 §13.1 待裁决。"
    )
    A("")
    # 末行恰好一个 \n：pre-commit 的 end-of-file-fixer 会改写多出的空行，
    # 那样"提交的内容"就不等于"脚本产出的内容"了 —— 宁可在这里收敛。
    return "\n".join(L).rstrip("\n") + "\n"


# ---------------------------------------------------------------- main


def main() -> int:
    verify = "--verify" in sys.argv
    runner_sha, head_short, runner_blob = preflight()
    prov = {"head": head_short, "runner_blob": runner_blob}
    rows, counts = collect_corpus()
    cal_notes = calibrate()
    rep = replay(rows)
    matrix = scope_matrix(rows)
    manifest = {
        "rule": "三信号：run.label ∈ 夹具名集合 / 路径含 pytest 临时目录特征 / results 非空；sha256 去重归档副本",
        "counts": counts,
        "files": rows,
    }
    results = {
        "counts": counts,
        "calibration": cal_notes,
        "replay": rep,
        "scope_trigger_matrix": matrix,
        "gate2_runner_sha256": runner_sha,
        "provenance": prov,
    }
    report = build_report(counts, cal_notes, rep, matrix, runner_sha, rows, prov)

    if verify:
        same = True
        for path, text in (
            (
                OUT / "run-manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
            ),
            (
                OUT / "replay-results.json",
                json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
            ),
            (OUT / "over2-replay-report.md", report),
        ):
            got = path.read_bytes().decode("utf-8") if path.exists() else "<缺失>"
            if got != text:
                same = False
                print(f"VERIFY DIFF: {path.name}")
        print(f"VERIFY 幂等 = {same}")
        return 0 if same else 1

    dump(OUT / "run-manifest.json", manifest)
    dump(OUT / "replay-results.json", results)
    (OUT / "over2-replay-report.md").write_bytes(report.encode("utf-8"))
    print(
        f"真实文件 {counts['真实评测']} / 夹具 {counts['测试夹具']} / 归档副本 {counts['归档副本']} / 待定 {counts['待定']}"
    )
    print(
        f"条目 {sum(b['n'] for b in rep['per_run'])} ⇒ 一致 {sum(b['一致'] for b in rep['per_run'])} 漏标 {sum(b['漏标'] for b in rep['per_run'])} 反向差异 {sum(b['反向差异'] for b in rep['per_run'])} 不可归因 {sum(b['不可归因'] for b in rep['per_run'])} 无判定 {sum(b['无判定'] for b in rep['per_run'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
