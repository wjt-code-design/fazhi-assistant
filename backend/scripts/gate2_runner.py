"""Gate 2 / Gate 5 完整多轮会话执行器：按冻结事实协议驱动 Agent 完整会话（≤2 轮追问）。

流程（每题一次）：
1. chat(force_agent=true, no_cache=true, 初始问题)  → 收集事件
2. 若 clarification：抽取 prompt → 与 frozen-round-protocol 的 fact_units 做关键词命中匹配
     - 命中：resume 携带该事实文本（一次可多个相关问题）
     - 未命中：不给事实（保持 unknown，检查条件化分析）；记录 asked_unknown
3. 达到 2 轮后若再次 clarification → 记为红线候选（超过两轮仍拒绝条件化）
4. 输出：逐请求事件摘要、asked/answered/unknown fact_ids、六段式内容、失败保留

V2-T6（2026-09-09）长跑可靠性（F6）：
- run 占用：启动时独占创建 gate2-run-{run}.claim.json（已存在 → 拒绝，续跑用 --resume）；
- 逐题原子 checkpoint：每题完成写 gate2-run-{run}-checkpoint.json（tmp + fsync + os.replace），
  崩溃/中断保留已完成题；
- 最终产物 gate2-run-{run}-sessions.json 存在即拒绝覆盖（create 与 resume 都不覆盖旧 run）；
- --resume：校验 claim 与案例清单一致后跳过已完成案例；带 unknown_server_state（CLIENT_TIMEOUT）
  标记的题不得自动重跑，须人工确认后加 --retry-unknown；
- 客户端超时 → 记录未知服务端状态并暂停队列（不自动继续下一题、不自动补发）；
- 产物区分 final_chars（有文本）与 agent_completed（final 事件带 run_id=真实持久化成功），
  不得用 final_chars>0 冒充 Agent 完成。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVID = REPO / "release-evidence" / "legal-agent-v1-complex-v1-20260907"

CASES = json.loads((EVID / "frozen-cases-v1.json").read_text(encoding="utf-8"))["cases"]
BY_ID = {c["id"]: c for c in CASES}
# 默认题集快照（2026-09-11 审查修正）：--cases-file 会重绑模块级 CASES/BY_ID；
# 同进程多次 run() 且后续调用不带 --cases-file 时，若不恢复默认会沿用上一次重绑的陈旧题集。
_DEFAULT_CASES, _DEFAULT_BY_ID = CASES, BY_ID
PROTO = json.loads((EVID / "frozen-round-protocol-v1.json").read_text(encoding="utf-8"))
FACT_IDS = json.loads((EVID / "frozen-fact-ids-v1.json").read_text(encoding="utf-8"))["fact_ids"]

STOPWORDS = frozenset("我 的 了 吗 在 有 与 和 公司 用户 信息 是 不 也 曾 后 前 上 下 里 中".split())

# 事实单元同义问法关键词表（执行配置；跨轮匹配，稳定 fact_id；对应 §6.1 同义等价判定）
# 键：<CASE>-r<轮>-f<序号> （与 frozen-fact-ids-v1.json 对齐）
KEYWORDS: dict[str, list[str]] = {
    "C01-r1-f1": ["内网", "制度", "培训"],
    "C01-r1-f2": ["解除通知", "不胜任"],
    "C01-r1-f3": ["工作年限", "工作四年", "工龄", "工作多少年"],
    "C01-r2-f1": ["培训", "调岗"],
    "C01-r2-f2": ["工会"],
    "C01-r2-f3": ["平均工资", "月工资", "工资基数", "12000"],
    "C02-r1-f1": ["标准工时", "工时", "工作制"],
    "C02-r1-f2": ["周六", "每周六", "排班", "加班"],
    "C02-r1-f3": ["调休"],
    "C02-r2-f1": ["月工资", "月薪", "10000"],
    "C02-r2-f2": ["工资结构", "结构"],
    "C03-r1-f1": ["拖延", "未签", "没签"],
    "C03-r1-f2": ["转账", "按月"],
    "C03-r1-f3": ["离职", "离职通知", "辞职", "主动离职"],
    "C03-r2-f1": ["空白合同"],
    "C03-r2-f2": ["补齐条款", "条款"],
    "C04-r1-f1": ["认购书"],
    "C04-r1-f2": ["转账", "支付", "交付"],
    "C04-r1-f3": ["出价更高", "涨价", "微信"],
    "C04-r2-f1": ["七日内", "七天", "正式合同"],
    "C04-r2-f2": ["拒绝", "拒售"],
    "C04-r2-f3": ["总价", "200万", "两百万"],
    "C05-r1-f1": ["每月5日", "付款", "约定"],
    "C05-r1-f2": ["催告"],
    "C05-r1-f3": ["换锁", "锁"],
    "C05-r2-f1": ["退回", "转账"],
    "C05-r2-f2": ["物品", "屋内", "财产"],
    "C05-r2-f3": ["押金"],
    "C06-r1-f1": ["固定总价", "总价", "固定价"],
    "C06-r1-f2": ["材料涨价", "涨价"],
    "C06-r1-f3": ["三个月", "工期", "完工"],
    "C06-r1-f4": ["柜体", "变更", "尺寸"],
    "C06-r2-f1": ["加价单", "顺延", "变更"],
    "C06-r2-f2": ["五十天", "延期", "工期"],
    "C07-r1-f1": ["2021", "6月30", "到期", "还款日期"],
    "C07-r1-f2": ["2023", "催", "5月", "微信"],
    "C07-r1-f3": ["年底还", "承诺", "回复"],
    "C07-r2-f1": ["2024", "12月", "转", "1000"],
    "C07-r2-f2": ["先还", "部分", "备注"],
    "C08-r1-f1": ["主债务", "2023", "8月", "到期"],
    "C08-r1-f2": ["承担保证责任", "担保条款", "保证方式"],
    "C08-r1-f3": ["2024", "微信", "债权人", "主张"],
    "C08-r2-f1": ["起诉", "借款人"],
    "C08-r2-f2": ["展期", "延长", "同意"],
    "C09-r1-f1": ["门店", "停业", "关"],
    "C09-r1-f2": ["二十公里", "换店"],
    "C09-r1-f3": ["电子", "勾选"],
    "C09-r1-f4": ["付款", "8000", "八千"],
    "C09-r1-f5": ["四分之一", "剩余"],
    "C09-r2-f1": ["概不退款", "说明", "提示"],
    "C09-r2-f2": ["换店", "不同意"],
    "C09-r2-f3": ["发票", "主体", "名称"],
    "C10-r1-f1": ["30000", "三万", "个人账户", "支付"],
    "C10-r1-f2": ["虚假", "库存", "视频"],
    "C10-r1-f3": ["承认", "没货", "拉黑"],
    "C10-r2-f1": ["三名", "买家", "其他", "共同"],
    "C10-r2-f2": ["总金额", "总额"],
    "C10-r2-f3": ["姓名", "手机号", "身份"],
    "C10-r2-f4": ["住址", "地址"],
}

FACT_TEXT: dict[str, str] = {}
for _case, _rounds in PROTO["fact_units"].items():
    for _rn, _units in _rounds.items():
        _ids = FACT_IDS.get(_case, {}).get(_rn, [])
        for _i, _u in enumerate(_units[: len(_ids)]):
            FACT_TEXT[_ids[_i]] = _u


def _tokens(text: str) -> set[str]:
    return {w for w in re.split(r"[，。；、：（）\s0-9,.;:()“”\"'…！？]", text) if w and w not in STOPWORDS}


# ---- 评测器共享事实投放（2026-09-08，评测器纠偏任务）----
# 与 dispatch-output/task1/hidden_runner.py 共用 harness_fact_reveal 单一实现（§4.1）。
import sys as _sys

if str(Path(__file__).resolve().parent) not in _sys.path:
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_fact_reveal import FactMatchResult, match_revealable_facts  # noqa: E402


def _build_fact_meta() -> dict[str, dict]:
    import re as _re

    facts: dict[str, dict] = {}
    for fid, kws in KEYWORDS.items():
        m = _re.search(r"-r(\d+)-f", fid)
        rnd = int(m.group(1)) if m else 99
        facts[fid] = {"round": rnd, "keywords": list(kws), "text": FACT_TEXT.get(fid, "")}
    return facts


_FACTS = _build_fact_meta()
# 默认（v1 冻结 KEYWORDS）快照：--cases-file 重绑后不带参数的调用必须恢复它（同 B6 教训）。
_DEFAULT_FACTS = dict(_FACTS)
NO_MATCH_REPLY = "我没有保留这方面的信息。"
# scope 选择澄清（争点数超单次上限时服务端要求输编号）：事实关键词协议答不了它——
# NO_MATCH_REPLY 会被服务端 scope 防御 409 拒绝（28c197e 批次边界，行为正确）。
# 评测端确定性应对：选前 5 个争点（不消耗事实投放、不记 unmatched）。
SCOPE_MARK = "本次请求分解出"
SCOPE_REPLY = "1,2,3,4,5"


def _facts_from_case_set(base: dict[str, dict], cases: list[dict]) -> dict[str, dict]:
    """题集自包含 fact_reveal（新案例）并入事实投放 meta。

    fid 形如 <CASE>-r<轮>-f<序号>，与 v1 冻结协议命名一致；fid 冲突时 base（硬编码
    KEYWORDS）优先——v1 案例行为零变化。无 fact_reveal 的案例不产生任何条目。
    """
    facts = dict(base)
    for c in cases:
        reveal = c.get("fact_reveal") or {}
        for rk, units in reveal.items():
            m = re.fullmatch(r"r(\d+)", str(rk))
            if not m or not isinstance(units, list):
                continue
            rnd = int(m.group(1))
            for i, u in enumerate(units):
                if not isinstance(u, dict):
                    continue
                fid = f"{c['id']}-r{rnd}-f{i + 1}"
                if fid in facts:
                    continue
                facts[fid] = {
                    "round": rnd,
                    "keywords": list(u.get("keywords") or []),
                    "text": str(u.get("text") or ""),
                }
    return facts


def _match_facts(case: str, prompt: str) -> tuple[list[str], list[str]]:
    """兼容旧签名（= 第一轮、无已答）：轮次隔离 + 去重由共享模块保证。"""
    res = match_revealable_facts(case_id=case, prompt=prompt, current_round=1, answered_fact_ids=set(), facts=_FACTS)
    return [m["text"] for m in res.matched_facts], res.answered_fact_ids


def _match_facts_tracked(
    case: str, prompt: str, current_round: int, answered_fact_ids: set[str]
) -> tuple[list[str], list[str], FactMatchResult]:
    res = match_revealable_facts(
        case_id=case,
        prompt=prompt,
        current_round=current_round,
        answered_fact_ids=answered_fact_ids,
        facts=_FACTS,
    )
    return [m["text"] for m in res.matched_facts], res.answered_fact_ids, res


def _atomic_write_json(path: Path, payload: dict) -> None:
    """原子写（同目录 tmp + fsync + os.replace）：checkpoint 与最终产物共用。"""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _exclusive_create_json(path: Path, payload: dict) -> bool:
    """独占创建（O_CREAT|O_EXCL）：run 占用claim 的"先到先得"语义，失败=已被占用。"""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    return True


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run 标识（如 gate2-run-1）")
    ap.add_argument("--case", help="逗号分隔 case 列表，如 C01,C02（断点续跑）")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument(
        "--out-dir",
        help="产物输出目录（claim/checkpoint/sessions；默认 release-evidence/legal-agent-v1-complex-v1-20260907）。"
        "测试/演练用它隔离产物目录，避免写入真实 evidence 树",
    )
    ap.add_argument(
        "--resume", action="store_true", help="续跑已启动的 run：要求 claim 存在且案例清单一致，跳过已完成案例"
    )
    ap.add_argument(
        "--retry-unknown",
        action="store_true",
        help="仅 --resume 下有效：人工确认服务端状态后，允许重跑带 unknown_server_state（CLIENT_TIMEOUT）标记的题",
    )
    ap.add_argument(
        "--cases-file",
        help="覆盖题集文件（默认 frozen-cases-v1.json）。用于留出集 holdout-cases-v1.json 的双集验收；"
        "run 名必须能区分题集（如 *-holdout），禁止复用评测 run 名",
    )
    args = ap.parse_args(argv)
    if args.retry_unknown and not args.resume:
        raise SystemExit("--retry-unknown 仅在 --resume 下有效")
    # V2-writer-axis（2026-09-10）：双集验收 —— 留出集（holdout-cases-v1.json）用独立题集文件跑。
    # 2026-09-11 审查修正（B6）：--cases-file 重绑模块级 CASES/BY_ID 后，**不带该参数的调用必须
    # 回到默认题集**（防同进程内前一次重绑的陈旧题集残留）。global 声明只出现一次（置于分支之前）——
    # 同函数内两次声明同名 global 会触发 SyntaxError（name used prior to global declaration），
    # 且 ruff 不报、仅 pytest 收集期暴露（教训：语法级错误也会漏过 linter）。
    global CASES, BY_ID, _FACTS
    if args.cases_file:
        CASES = json.loads(Path(args.cases_file).read_text(encoding="utf-8"))["cases"]
        BY_ID = {c["id"]: c for c in CASES}
        _FACTS = _facts_from_case_set(_DEFAULT_FACTS, CASES)
    else:
        CASES, BY_ID = _DEFAULT_CASES, _DEFAULT_BY_ID
        _FACTS = dict(_DEFAULT_FACTS)
    if args.all:
        targets = sorted(BY_ID)
    elif args.case:
        targets = [c.strip() for c in args.case.split(",") if c.strip()]
        unknown_case = [c for c in targets if c not in BY_ID]
        assert not unknown_case, f"未知 case: {unknown_case}"
    else:
        raise SystemExit("需 --case 或 --all")

    out_dir = Path(args.out_dir) if args.out_dir else EVID
    out_dir.mkdir(parents=True, exist_ok=True)
    claim_path = out_dir / f"gate2-run-{args.run}.claim.json"
    checkpoint_path = out_dir / f"gate2-run-{args.run}-checkpoint.json"
    out_path = out_dir / f"gate2-run-{args.run}-sessions.json"

    # 最终产物覆盖保护在 pending 计算后统一处理（全部完成 → 幂等补写/无操作；仍有未完成 → 拒绝）。
    results: dict[str, dict] = {}
    if args.resume:
        if not claim_path.exists():
            print(f"REFUSE: --resume 需要已有 claim（{claim_path.name} 不存在，该 run 从未启动）")
            return 4
        saved_claim = json.loads(claim_path.read_text(encoding="utf-8"))
        if saved_claim.get("targets") != targets:
            print("REFUSE: 本次案例清单与原 run 的 claim 不一致（防错跑）")
            return 4
        if checkpoint_path.exists():
            loaded = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if loaded.get("run") != args.run:
                print("REFUSE: checkpoint 的 run 标识不一致")
                return 4
            results = dict(loaded.get("results", {}))
    else:
        claim = {
            "run": args.run,
            "targets": targets,
            "started_at": datetime.now(UTC).isoformat(),
            "pid": os.getpid(),
            "protocol_version": PROTO.get("protocol_version", "v1"),
        }
        if not _exclusive_create_json(claim_path, claim):
            print(f"REFUSE: run 已被占用（{claim_path.name}）；续跑请加 --resume")
            return 4

    # T6：unknown_server_state 的题 = 服务端状态未知（CLIENT_TIMEOUT）——不得自动重跑（重复计费风险）。
    unknown_ids = [cid for cid, r in results.items() if r.get("unknown_server_state")]
    if unknown_ids and not args.retry_unknown:
        print(f"REFUSE: {unknown_ids} 存在未知服务端状态；人工确认后用 --resume --retry-unknown 重跑")
        return 5
    for cid in unknown_ids:
        del results[cid]  # 显式确认后按未完成重跑

    pending = [c for c in targets if c not in results]
    if not pending:
        # run 已全部完成：幂等补写缺失的最终产物（checkpoint → sessions 恢复一致性），不覆盖已有。
        if not out_path.exists():
            _atomic_write_json(out_path, {"run": args.run, "results": results})
            print("all targets already recorded; final sessions backfilled from checkpoint")
        else:
            print("all targets already recorded; nothing to do")
        return 0
    if out_path.exists():
        # 状态矛盾：存在未完成题但最终产物已在——异常状态，拒绝而不是覆盖。
        print(f"REFUSE: {out_path.name} 已存在但仍有未完成案例（{pending}）；禁止部分覆盖旧 run")
        return 4

    env = REPO / "backend" / ".env"
    user = pw = None
    for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("ADMIN_USERNAME="):
            user = line.split("=", 1)[1].strip()
        elif line.startswith("ADMIN_PASSWORD="):
            pw = line.split("=", 1)[1].strip()

    def post(path: str, payload: dict, token: str | None = None, timeout: int = 2400) -> tuple[int, str]:
        # timeout 2400：LongCat 外呼延迟实测可高达 960s/请求（run-4 观测），
        # 错误回喂使单 POST 内最多 3 次 LLM 外呼（planner 2 次重试 + 1 次回喂），1500 可能误杀（run-6 C06 观测）。
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(
            args.base_url + path, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")
        except (TimeoutError, OSError) as exc:
            # 采集侧超时：服务端状态未知（请求可能仍在执行）——返回 (0, "") 由上层
            # 标记 unknown_server_state 并暂停队列（T6：不自动继续下一题/补发旧题）。
            return 0, f"CLIENT_TIMEOUT:{type(exc).__name__}"

    # 登录加**有界重试**（2026-09-16：1e6/1e7 批次首个 run 必现"空响应"——
    # EVALUATION_READY 打印时 uvicorn 可能尚未完成应用初始化，首连拿到空 body）。
    # 终止性：固定 3 次尝试；**只重试"响应不可解析"（时序类）**；拿到合法 JSON 即停
    # （凭据类失败重试不改变结果，不重试）。
    token = None
    retries_used = 0
    for attempt in range(1, 4):
        _, body = post("/api/auth/login", {"username": user, "password": pw})
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = None
        if parsed is None:
            retries_used += 1
            # 可观测（show-your-work 2026-09-16）：重试路径此前无法验证（无日志）——
            # "r1 没崩"可能是首次就成功，不能等同"重试生效"。显式留下重试证据。
            print(f"login retry {attempt}/3 (empty/unparseable response)", flush=True)
            if attempt < 3:
                time.sleep(2)
            continue
        token = parsed.get("token")
        break
    if not token:
        print("login failed")
        return 2
    if retries_used:
        print(f"login succeeded after {retries_used} retry(ies)", flush=True)

    def _events(raw: str) -> list[dict]:
        out = []
        for part in raw.split("\n\n"):
            line = part.strip()
            if line.startswith("data: ") and "[DONE]" not in line:
                try:
                    out.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
        return out

    def _error_codes(events: list[dict]) -> list[str]:
        """失败/降级归因：error(code) 或 restart(reason_code) 事件。"""
        return [
            str(e.get("code") or e.get("reason_code"))
            for e in events
            if e.get("type") in ("error", "restart") and (e.get("code") or e.get("reason_code"))
        ]

    for case_id in pending:
        c = BY_ID[case_id]
        asked, answered, unmatched = [], [], []
        rounds = []
        conv_id = None
        t0 = time.time()
        payload = {"content": c["initial_question"], "no_cache": True, "force_agent": True}
        status, raw = post("/api/chat", payload, token)
        events = _events(raw)
        err_codes = _error_codes(events)
        if status == 0:
            events, err_codes = [], ["CLIENT_TIMEOUT"]
        rounds.append(
            {
                "request": "initial",
                "status": status,
                "event_types": [e.get("type", "content") for e in events]
                or (["CLIENT_TIMEOUT"] if status == 0 else []),
                "error_codes": err_codes,
            }
        )

        for round_no in (1, 2):
            clar = [e for e in events if e.get("type") == "clarification"]
            if not clar:
                break
            prompt = clar[0].get("prompt", "")
            conv_id = clar[0].get("conversation_id") if conv_id is None else conv_id
            asked.append({"round": round_no, "prompt": prompt})
            if SCOPE_MARK in prompt:
                # scope 选择澄清：确定性选前 5 争点（不走事实协议，见 SCOPE_REPLY 注释）
                answered_facts, matched_ids = [], []
                reply = SCOPE_REPLY
            else:
                # 评测器纠偏（2026-09-08）：轮次隔离 + 已答去重，由共享模块执行
                answered_facts, matched_ids, res = _match_facts_tracked(
                    case_id, prompt, current_round=round_no, answered_fact_ids=set(answered)
                )
                if matched_ids:
                    answered += matched_ids
                    reply = "；".join(answered_facts)
                else:
                    unmatched.append({"round": round_no, "prompt": prompt, "reason": "no_rule_match"})
                    reply = NO_MATCH_REPLY
            payload = {
                "content": reply,
                "no_cache": True,
                "conversation_id": clar[0].get("conversation_id"),
                "agent_run_id": clar[0].get("run_id"),
                "agent_state_version": clar[0].get("state_version"),
            }
            status, raw = post("/api/chat", payload, token)
            events = _events(raw)
            err_codes = _error_codes(events)
            if status == 0:
                events, err_codes = [], ["CLIENT_TIMEOUT"]
            rounds.append(
                {
                    "request": f"round{round_no}",
                    "status": status,
                    "answered_facts": answered_facts,
                    "event_types": [e.get("type", "content") for e in events]
                    or (["CLIENT_TIMEOUT"] if status == 0 else []),
                    "error_codes": err_codes,
                    "clar_meta": {
                        "run_id": clar[0].get("run_id"),
                        "state_version": clar[0].get("state_version"),
                        "conv_id": clar[0].get("conversation_id"),
                    },
                    "raw_tail": raw[-300:] if status != 200 else None,
                }
            )

        all_error_codes = [code for r in rounds for code in r.get("error_codes", [])]
        final_text = "".join(str(e.get("content", "")) for e in events if e.get("content"))
        over_rounds = any(e.get("type") == "clarification" for e in events)  # 第3次澄清=红线候选
        # T6：区分"有文本"与"Agent 真实完成"——final 事件带 run_id 才代表终稿已持久化（COMPLETED）。
        agent_completed = any(e.get("type") == "final" and e.get("run_id") for e in events)
        unknown_server_state = any(r.get("status") == 0 for r in rounds)
        results[case_id] = {
            "rounds": rounds,
            "asked": asked,
            "answered_fact_ids": answered,
            "unmatched_questions": unmatched,
            "manual_review_required": [],
            "protocol_violations": [],
            "unknown_fact_ids": [],  # deprecated（评测器纠偏 §4.2）：不再混存 {round,prompt} 对象
            "error_codes": all_error_codes,
            "conv_id": conv_id,
            "final_chars": len(final_text),
            "final_text": final_text,  # Gate 5 逐题判定需要完整输出（六段式/争点/依据/证据绑定）
            "final_excerpt": final_text[:120],
            "agent_completed": agent_completed,
            "redline_candidate_over_2_rounds": over_rounds,
            "elapsed_s": round(time.time() - t0, 1),
        }
        if unknown_server_state:
            results[case_id]["unknown_server_state"] = True
        # 逐题原子 checkpoint：崩溃/中断后已完成题不丢（tmp + fsync + os.replace）。
        _atomic_write_json(checkpoint_path, {"run": args.run, "targets": targets, "results": results})
        print(
            f"[{case_id}] rounds={len(rounds)} clar_rounds={len(asked)} answered={len(answered)} "
            f"unmatched={len(unmatched)} final_chars={len(final_text)} agent_completed={agent_completed} "
            f"over2={over_rounds} errors={all_error_codes}"
        )
        if unknown_server_state:
            print(
                f"PAUSED: [{case_id}] 客户端超时，服务端状态未知——已暂停队列，不发下一题；"
                "人工确认后用 --resume [--retry-unknown] 继续"
            )
            return 3

    _atomic_write_json(out_path, {"run": args.run, "results": results})
    try:
        display = str(out_path.relative_to(REPO))
    except ValueError:  # EVID 被测试重定向到 tmp 时不在 REPO 子树内
        display = str(out_path)
    print("written:", display)
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
