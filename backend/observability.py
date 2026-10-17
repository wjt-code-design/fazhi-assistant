"""可观测：request_id（contextvar + 响应头）+ 结构化 JSON 日志 + 问答调用记账。

注意：中间件用纯 ASGI 实现（只包装 send，不缓冲 body），以免破坏 SSE 流式响应
（BaseHTTPMiddleware 会缓冲 StreamingResponse，导致流式失效/内存暴涨）。
"""

import contextvars
import hashlib
import json
import logging
import time
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# token_est/tier/cache/escalated/verdict：log_account 实际传入的记账字段——此前遗漏被
# JSON formatter 静默丢弃（每问成本算不出、eval_latency_log 的 rule 剔除恒为 0），
# 2026-08-03 交付级验收修复。追加尾部，不动既有字段顺序。
# llm_adapter_stage/llm_invoke_mode/llm_error_class/llm_error_status_code/llm_invoke_duration_ms：
# T4（2026-09-09）adapter 降级观测字段，同规则追加尾部（否则被 formatter 静默丢弃）。
# agent_repair_stage/agent_issue_count/agent_coverage_gap_count/agent_non_verbatim_count：
#   V2-T8（2026-09-10）分解「事实缺陷修复环」观测字段。
# agent_pre_run_reason/agent_conversation_id/agent_failure_detail：V2-T8（2026-09-10）修复——
#   `_log_pre_run_failure`（agent/service.py）一直在传这三个字段，但从未登记在此，
#   导致**预运行失败的唯一诊断点整体失明**：ISSUE_DECOMPOSITION_INVALID 的 7 种抛错文案
#   （runtime.py 的 IssueDecompositionError）在日志里坍缩成一个"未知"。
#   实测代价见 handoff §12.3；修复后已于 §12.11 验证轮拿到确切死因。
# agent_run_id/agent_planner_raw_tail/agent_actual_route/agent_fallback_reason：V2-T8 **自审**用
#   AST 哨兵（`tests/test_log_field_whitelist.py`）扫出的**同族**静默丢弃，一并登记：
#     - agent_run_id（service.py 崩溃诊断）：**连哪个 run 崩了都记不到**，且该行未传 request_id ⇒ 零标识；
#     - agent_planner_raw_tail（controller.py）：PLANNER_PARSE_ERROR 事后复盘丢掉原始输出；
#     - agent_actual_route / agent_fallback_reason（main.py）：无法审计"是否真的走了 agent 路径"
#       —— 而 §6.2 警告的"漏设 AGENT_ENABLED 会静默走 RAG"正靠这两个字段发现。
_ACCOUNT_FIELDS = (
    "method",
    "path",
    "status",
    "ms",
    "first_ms",
    "model",
    "ok",
    "conv_id",
    "user_id",
    "q_len",
    "token_est",
    "tier",
    "cache",
    "escalated",
    "verdict",
    "degraded",
    "kind",
    "detail",
    "agent_correlation_id",
    "agent_gate_mode",
    "agent_gate_reason_codes",
    "llm_adapter_stage",
    "llm_invoke_attempt",
    "llm_invoke_mode",
    "llm_error_class",
    "llm_error_status_code",
    "llm_invoke_duration_ms",
    "agent_repair_stage",
    "agent_issue_count",
    "agent_coverage_gap_count",
    "agent_non_verbatim_count",
    "agent_pre_run_reason",
    "agent_conversation_id",
    "agent_failure_detail",
    "agent_run_id",
    "agent_planner_raw_tail",
    "agent_actual_route",
    "agent_fallback_reason",
    # agent_coverage_issues：2026-09-12 覆盖率闸门终态失败的逐争点归因字段
    # （claim 数 / 绑定生效成文法的 claim 数 / 是否判缺绑定）。只含 issue_id 与计数，
    # 不含任何用户文本。未登记会被 JSON formatter 静默丢弃 → 失败重新变得不可归因。
    "agent_coverage_issues",
    # agent_writer_summary：2026-09-12 writer 侧归因字段（每次渲染的 reason /
    # 是否回喂 / 提出·接受·丢弃的 claim 计数 / 逐争点明细 / 失败的争点）。
    # 用于区分「模型没产出 claim」与「产出后因 evidence_ids 为空被静默丢弃」。
    # 同样只含标识与计数，不含草稿文本。
    "agent_writer_summary",
    # agent_claim_checks：2026-09-18 verifier **失败路径**的逐 claim 归因字段
    # （此前 claim_checks 仅 PASS 填充 ⇒ OVERCONFIDENT_WORDING 等误伤无法事后定位，
    # E04 根因只能靠猜）。含被判定 claim 的**草稿**文本截断 120（非用户输入原文），
    # 依据同 `agent_planner_raw_tail` 的"原始输出入日志"先例。未登记会被静默丢弃。
    # ⚠️ PII 考量（R15 安全观察，2026-09-21 Owner 通道裁定**维持现状**）：草稿由用户输入
    # 生成 ⇒ 可能复述姓名/案情；本应用当前为**本地单租户**（日志与用户数据同机同主），
    # 暴露面可控 ⇒ 暂不改截断/哈希。**多租户/云端部署前必须重估**（改脱敏或限访问/保留期）。
    "agent_claim_checks",
    # R1/R1b 部门法守卫（2026-09-14，预注册 dept-law-filter-r1）：
    #   dept_filter_removed（R1 证据池剔除）与 proc_misroute_detected / proc_misroute_flag
    #   （R1b 终稿串台红线）的可观测字段。争点问句可能含案情和个人信息，只留哈希与长度。
    "proc_misroute_citations",
    "agent_domain",
    "query_sha256",
    "query_len",
    "domain",
    "removed",
    # rerank_transient_failure（2026-09-14，retrieval._rerank_docs）：限速 429 / 5xx / 连接抖动
    # 走"只降级本次、不标记模型耗尽"分支时的可观测字段。
    # 未登记会被 JSON formatter 静默丢弃 → "rerank 是否在被限速"重新变得不可归因
    # （实测动机：一次偶发失败曾导致同进程内后续 35 次全部静默降级，且日志里看不到原因）。
    # 只含模型名与异常类名/摘要（截断 160 字符），不含任何用户文本或密钥。
    "rerank_model",
    "rerank_error",
    # agent_resume_conflict（2026-10-09，DB-15 / 审查报告 B-47）：409 恢复冲突的**成因码**。
    # 同一句对外文案「Agent 任务已变化，无法恢复」背后原本是几类完全不同的成因（版本冲突 /
    # 持久状态读不出 / 用户这次输入不合式 / 步数预算打满）——不带码就只能知道"拒了"而不知道"为什么拒"，
    # 而 B-47 那 16/47 只卡死的 run 正是靠最后这一类才能被发现。未登记会被 JSON formatter 静默丢弃。
    # 值只含成因字面量与 run/conversation 标识，不含用户文本。
    "agent_resume_reason",
    # retrieval_category_filter_miss（2026-10-09，DB-16 / 审查报告 B-05）：带 `category` 过滤却取零
    # ⇒ 回落无过滤并落此条。现网两个条文集合的 metadata **没有 `category` 键**（实测各 10,266 行、
    # 每行 8 键），而 Chroma 0.4.24 对缺失键的 `$eq`/`$ne` 一律排除该行（实测报告 §12.3）
    # ⇒ 非空 category 会把向量池与 BM25 池同时清零，改前**零日志**、Agent 只记"证据缺失"。
    # 未登记会被 JSON formatter 静默丢弃 ⇒ "回落发生了多少次、被哪个值触发"又变回不可归因。
    # 值只含调用方给的分类字面值与内部阶段名，不含用户文本。
    "category_filter_value",
    "category_filter_stage",
    "category_filter_outcome",
    # llm_request_rejected / llm_model_depleted（2026-10-09，DB-17 / 审查报告 B-48）：
    # 把"这个模型没额度了"与"这一发请求被拒（400 超长/审核、401/403 key 失效、404 端点错、422）"
    # 拆成两条通道之后，必须让拆分本身可见——`model_failure_channel` 只有 exhausted/rejected 两个值，
    # `model_failure_reason` 是调用方给的原因字面量（此前 `mark_depleted(key, reason)` 的 reason
    # 被**整个丢弃**，连日志都不落，所以"为什么这个模型在管理台上变红了"事后无从查）。
    # 两个字段都不含用户文本与密钥。
    "model_failure_channel",
    "model_failure_reason",
    # D-9 拒答分档（2026-10-11，审查报告 B-48 后续）：401/403/404（key/端点配置错）冷却 3600s、
    # 400/422（请求形状被拒）沿用 300s。不落这两个字段就只知道"拒了、冷却了一会儿"，
    # 分不清是配置错还是超长——而前者反复重试永远不会自愈，后者换请求体就能过。
    # 值只有秒数与档位字面量，不含用户文本与密钥。
    "llm_reject_cooldown_s",
    "llm_reject_kind",
    # S5 快车道版本绊线（2026-09-19，settings.fast_path_law_version_check）：命中/保守分支落日志的
    # 归因四字段。`fast_path_law_version_detail` = **被判定原文**（模型答案，截断 200），
    # `fast_path_law_version_reason` = 命中口径（沿用 agent 路径的 LAW_VERSION_WATERSHED_MISMATCH /
    # LAW_TRIPWIRE_NOT_WIRED 两个字面，让两条路径在同一张日志里可并列 grep），
    # `law_as_of` = 本次判定用的基准日 —— 缺了这几项就只知道"拦了"而不知道"按哪版法拦的哪句"
    # （动机同 5afc8d0 的可归因教训、`agent_claim_checks` 的先例：失败路径不带原文 ⇒ 事后只能猜）。
    # 未登记会被 JSON formatter 静默丢弃。detail 为模型输出文本，不含用户输入原文与密钥。
    "fast_path_law_version_hit",
    "fast_path_law_version_reason",
    "fast_path_law_version_detail",
    "law_as_of",
    # QA 语料来源守卫（2026-09-25，票 AUTH-A 第五道的可观测补口，Owner 裁 AUTH-A-2 同批）：
    # `request_bootstrap.prepare_fast_path` 拒一条命中的 QA 记录时落这一个布尔。这道门关掉的是
    # **零 token 直返**，不留痕的话"语料在衰减"在线上没有痕迹。刻意只有归因键、没有判据分解
    # （把"缺 basis 还是缺引用"抄进日志等于放第二份判据），也没有题干/答案（AUTH-3 日志不落原文）。
    # 未登记会被 JSON formatter 静默丢弃 ⇒ 这个键本身白写（本仓哨兵抓到过一次）。
    "qa_provenance_refused",
    # 票 W1（2026-09-25，同批 Owner 裁决"对称收口"）：第二道门——引用**给得出但核验不过**
    # （条文不在库/已失效/库读不动）。与上面那键**分键不分门**：两个读数才能回答"是哪道门在衰减"，
    # 合成一键就只剩"语料被拦了"。同样只有归因键、没有判据分解、没有题干原文。
    "qa_citation_refused",
    # 法版本判定降级（2026-09-27，版本安全复核低-2）：`knowledge_service.add_text` 的替换判据整段
    # 包在 `except Exception: stale_ids = []` 里 ⇒ "判据哪天整体崩溃"与"判定后决定不替换"在库侧
    # 结果完全相同（旧块都留着），崩溃这条路今天零信号。留这一个布尔（键本身只承载真/假）；
    # 配套那条 warning 的正文**只含法名、条号、异常类名**三样，且**刻意不传 `exc_info`**——
    # 这里不再声明"不含条文正文"这类推断，只记事实：本 formatter 会把 `exc_info` 的异常原文 +
    # 完整 traceback 整体写进内置键 `exc`（内置键，不占 `_ACCOUNT_FIELDS`，登记与否都拦不住），
    # 而该处被捕获异常的入参含条文正文 ⇒ 传 `exc_info=True` 就等于给正文开一条通道。
    # 举证：tests/test_knowledge_service.py::test_version_judgment_crash_is_visible_in_structured_log
    # 用合成标记实测——传 `exc_info` 时标记出现在 payload["exc"]，移除后 `exc` 键不再出现、
    # 标记与条文正文记号均不进 JSON。formatter 本体的这行行为见本文件 `_JsonFormatter.format`。
    # 未登记会被 JSON formatter 静默丢弃 ⇒ 这个键本身白写。
    "law_version_judgment_failed",
    # W06-IMPL（2026-10-17，C03=形状 P）：撤回/隔离在**读侧**被拒时的两个字段。
    # `qa_eligibility_reason` 沿用上面两键的**分键不分门**口径（state|provenance|citation），
    # 这样"状态轴在衰减"与"来源/引用在衰减"是两个读数而不是一个"语料被拦了"；
    # 只落归因键与候选行 id（int），既没有判据分解也没有题干/答案原文（AUTH-3 日志不落原文）。
    # 未登记会被 JSON formatter 静默丢弃 ⇒ 两键白写——这一族由 `tests/test_log_field_whitelist.py`
    # 的 AST 哨兵守着，本轮就是它在全量门上抓出来的（纯树门 warm_rc=1，见 W12-GATES-FROM-COMMIT-06da7cc.log）。
    "qa_eligibility_reason",
    "qa_candidate_id",
    # W07-IMPL（2026-10-17，C04＝甲 已裁）：识图「失败」与「空内容」分家之后的两个归因键。
    # 改前 `multimodal.describe_image` 把四类异常与「模型返回空内容」收敛成同一个空串，
    # 所以**没有任何键可落**（读数也分不清「没字」和「没读到」）；甲把可分性建起来之后，
    # 两个出口各一个布尔键（`request_bootstrap.bootstrap_request` 是唯一落点）：
    #   image_describe_failed＝识图调用抛异常（该轮在 HTTP/SSE 层 502 中止），
    #   image_content_empty＝模型正常返回但内容为空（该轮继续，契约上留 image_failure 位）。
    # 合一键就只剩「图没读出来」——同 QA 语料「分键不分门」的口径。
    # 未登记会被 JSON formatter 静默丢弃 ⇒ 两键白写（上一票正是漏这格被全量纯树门打回）。
    # 只有归因布尔，没有题干、没有图片内容、没有 base64（AUTH-3 日志不落原文）。
    "image_describe_failed",
    "image_content_empty",
    # W07-IMPL §1 ②：模型 entry（DEFAULT_ROLES／LLM_MODELS_JSON）里 `_load` 不认识的键——
    # 改前这类拼错的键（如 transpor）走到 cfg 白名单就无声消失，正是票面「设置不丢」要防的失效。
    # 值只有**键名列表**（不含值，所以不会把 api_key 的值带进日志）与模型名。
    "llm_cfg_unknown_keys",
)

_TEST_REQUEST_ID_FALLBACK = "unit-test-no-middleware-request-id"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "req": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
        }
        for k in _ACCOUNT_FIELDS:
            v = getattr(record, k, None)
            if v is not None:
                rec[k] = v
        if record.exc_info and record.exc_info[1] is not None:
            rec["exc"] = self.formatException(record.exc_info)
        return json.dumps(rec, ensure_ascii=False)


def setup_logging(level: str) -> None:
    """配置应用结构化日志；用我们的结构化访问日志替代 uvicorn 的明文 access 日志。"""
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    for name in ("legal", "legal.access", "legal.chat"):
        lg = logging.getLogger(name)
        lg.handlers = [handler]
        lg.propagate = False
        lg.setLevel(level or "INFO")
    # 关闭 uvicorn 自带的明文 access 日志，避免与结构化访问日志重复
    logging.getLogger("uvicorn.access").disabled = True


class RequestIdMiddleware:
    """纯 ASGI 中间件：注入 request_id、记录结构化访问日志、回写响应头。不缓冲流式 body。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = None
        for k, v in scope.get("headers", []):
            if k.lower() == b"x-request-id":
                rid = v.decode("latin-1")
                break
        if not rid:
            rid = uuid.uuid4().hex[:12]

        token = request_id_var.set(rid)
        t0 = time.perf_counter()
        status = {"code": 0}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message.get("status", 0)
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", rid.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            logging.getLogger("legal.access").info(
                "req",
                extra={
                    "request_id": rid,
                    "method": scope.get("method", ""),
                    "path": scope.get("path", ""),
                    "status": status["code"],
                    "ms": ms,
                },
            )
            request_id_var.reset(token)


def log_account(**kw) -> None:
    """记录一次问答的调用记账（模型/耗时/成功/会话/用户/问句长度）。"""
    extra = {"request_id": request_id_var.get()}
    extra.update(kw)
    logging.getLogger("legal.chat").info("chat", extra=extra)


def make_agent_correlation_id(conversation_id: int | str | None, request_id: str | None = None) -> str:
    """Return a privacy-safe correlation id for one Shadow Gate observation.

    Production uses the middleware request id from ``request_id_var``. Direct unit
    calls have no middleware context, so ``-`` maps to a documented deterministic
    fallback. Only the hash is exposed to logs and metric calls.
    """
    current_request_id = request_id if request_id is not None else request_id_var.get()
    if not current_request_id or current_request_id == "-":
        current_request_id = _TEST_REQUEST_ID_FALLBACK
    material = f"agent-gate-v1\x00{current_request_id}\x00{conversation_id if conversation_id is not None else '-'}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
