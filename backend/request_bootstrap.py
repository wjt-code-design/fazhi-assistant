from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator, MutableSet
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

from sqlalchemy import func

from models import Conversation, Message


@dataclass(frozen=True)
class RecentMessageSnapshot:
    role: str
    content: str
    image_desc: str


@dataclass(frozen=True)
class RequestBootstrap:
    conv_id: int
    summary: str
    recent: list[dict[str, str]]
    recent_messages: list[RecentMessageSnapshot]
    image: str | None
    user_text: str
    image_rel: str | None
    thumb_rel: str | None
    image_description: str
    raw_query: str
    supplement_text: str
    intent: str
    is_exam: bool
    has_options: bool
    contract_mode: bool
    contract_text: str | None
    client_truncated: bool
    # R1-OB（2026-09-16 预注册）：评测/灰度通道案例域码（tier-1 判域直判源）。
    # 生产链路缺省 None（代码路径存在但恒不触发）；合法值见 agent/r1ob.VALID_CASE_DOMAINS。
    case_domain: str | None = None
    # 公开历史查询基准日；Agent run 和快车道检索均使用该值。省略时取当日。
    # Agent runtime/gateway 拒收模型自行改写的 server-owned 日期。
    law_as_of: date | None = None
    # 口径③⑥（2026-10-13）：只有「条款自指」支命中时先确认审查意图；True 表示本轮应发确认提示词
    intent_confirm: bool = False
    # 票 W07 §2（C04＝甲）：**失败位**。改前这一份字段面里没有任何一位能表达
    # 「这一轮的图没被读出来」（现量＝那只 20 字段闭集判据，本轮改写成新闭集）。
    # 取值：None＝图被正常读出；`content_empty`＝模型正常返回但内容为空——该轮**继续**，
    # 所以必须有一位可表达。调用本身失败（`describe_failed`）**不落在返回的实例上**：
    # 那一轮在 HTTP/SSE 层就 502 中止（main._describe_image_for_bootstrap），压根不产出 bootstrap
    # ——「失败」与「没字」因此是两个出口而不是一处两个值，这正是本票要建起来的分岔。
    image_failure: str | None = None


@dataclass(frozen=True)
class BootstrapDependencies:
    session_factory: Callable[[], Any]
    load_context: Callable[[Any, Conversation], tuple[str, list[Any]]]
    validate_image: Callable[[str], Any]
    persist_image: Callable[[str], tuple[str, str]]
    cleanup_persisted_image: Callable[[str | None, str | None], None]
    describe_image: Callable[[str, str], str]
    classify_intent: Callable[[str], str]
    is_exam_question: Callable[[str], bool]
    has_exam_options: Callable[[str], bool]
    is_contract_review: Callable[[str], bool]
    contract_trigger_reason: Callable[[str], str | None]
    feature_multi_analyze: bool
    contract_conversations: set[int]
    contract_reviewed_conversations: set[int]
    is_contract_exit: Callable[[str], bool]


class _CutoffTextDocsFn(Protocol):
    """按基准日取条文的接缝形状（text → docs）。`cutoff` 是**必传关键字**。"""

    def __call__(self, text: str, /, *, cutoff: str | None) -> list[Any]: ...


class _CutoffDocsFn(Protocol):
    """无入参的静态条文集（作弊/格式条款/消费欺诈）。`cutoff` 同样必传。"""

    def __call__(self, *, cutoff: str | None) -> list[Any]: ...


class _CutoffQueryKDocsFn(Protocol):
    """语义检索与考试分步检索：query 必给、k 可省（两边默认值不同）、cutoff 必传关键字。"""

    def __call__(self, query: str, /, k: int = ..., *, cutoff: str | None) -> list[Any]: ...


class _CutoffContractFn(Protocol):
    def __call__(self, text: str, /, *, cutoff: str | None) -> dict[str, Any]: ...


@dataclass(frozen=True)
class FastPathDependencies:
    """快车道取数接缝。

    每条"去库里捞条文"的能力都用 `Protocol` 钉成 **cutoff 必传关键字**：新增取数口若忘了带
    基准日，mypy 直接在调用点报错，而不是运行时静默按现行法取数（历史查询因此变成"证据变少"
    这种没人报的错）。缺省语义仍在实现侧（`cutoff=None` 落当日），所以收紧的只是调用点。
    `search_qa` 刻意不带 cutoff：QA 语料按当日沉淀、无版本轴，历史查询靠 `prepare_fast_path`
    显式置 `qa_hit=None` 绕开它。
    """

    feature_study_retrieval: bool
    is_meta_study: Callable[[str], bool]
    rewrite_for_retrieval: Callable[[str, list[dict[str, str]], list[Any], bool], str]
    scenario_supplement_docs: _CutoffTextDocsFn
    retrieve_exam: _CutoffQueryKDocsFn
    cheating_docs: _CutoffDocsFn
    build_contract_data: _CutoffContractFn
    retrieve: _CutoffQueryKDocsFn
    search_qa: Callable[[str], Any]
    is_consumer_clause_scenario: Callable[[str], bool]
    consumer_clause_docs: _CutoffDocsFn
    is_consumer_fraud_scenario: Callable[[str], bool]
    consumer_fraud_docs: _CutoffDocsFn
    format_docs: Callable[[list[Any]], str]


@dataclass(frozen=True)
class ContractConversationState:
    active: set[int]
    reviewed: set[int]


DEFAULT_CONTRACT_STATE = ContractConversationState(active=set(), reviewed=set())

ImageDescriber = Callable[[str, str], str]
_configured_image_describer: ImageDescriber | None = None
_image_describer_config_lock = RLock()
_image_describer_override_lock = RLock()


def configure_default_image_describer(describer: ImageDescriber) -> None:
    """Configure the application-owned image capability used by the public bootstrap API.

    Model/provider selection belongs to the application composition layer.  This module
    stores only the already-composed callable and never resolves a provider itself. Runtime
    replacement by a different coordinator is rejected to prevent cross-application state
    leakage; controlled temporary overrides must use `override_default_image_describer`.
    """
    global _configured_image_describer
    with _image_describer_override_lock:
        with _image_describer_config_lock:
            if _configured_image_describer is not None and _configured_image_describer is not describer:
                raise RuntimeError("image description capability is already configured")
            _configured_image_describer = describer


@contextmanager
def override_default_image_describer(describer: ImageDescriber) -> Iterator[None]:
    """Temporarily replace the capability as one serialized, restoration-safe scope."""
    global _configured_image_describer
    with _image_describer_override_lock:
        with _image_describer_config_lock:
            previous = _configured_image_describer
            _configured_image_describer = describer
        try:
            yield
        finally:
            with _image_describer_config_lock:
                _configured_image_describer = previous


# 口径②（2026-10-13）：退出只认用户**本轮**的明示短命令。
# 旧实现是纯子串匹配、且标记表里带裸词"暂停/结束"——于是贴进来的合同正文自己写着
# "本合同结束后押金不予退还""双方可协商暂停履行"时，会话会被**文档内容**踢出合同模式
# （该退的不退、不该退的退）。现在两条约束：
#   1) 删除裸词，只留带宾语的短语；
#   2) 去空白与结句标点后，只有整条消息本身够短才认标记——长文里嵌着这些词一律不算。
# 含糊的（"先暂停一下""先不聊这份合同了"）不静默退出，交确认路径，见 CONTRACT_CLARIFY_PROMPT。
CONTRACT_EXIT_MARKS = (
    "退出合同",
    "不审合同",
    "不用审了",
    "不再审合同",
    "结束合同",
    "结束评估",
    "换个话题",
    "换一个问题",
)

_CONTRACT_EXIT_MAX_CHARS = 20
# 口径②（2026-10-13 裁定）：换合同重置，**明确比较两份合同除外**——比较轮不得把上一份挤掉。
_CONTRACT_COMPARE_MARKS = ("对比", "比较", "两份", "异同", "两个版本", "各自")


def _previous_contract_text(recent: list[dict[str, str]], deps: BootstrapDependencies) -> str:
    """从历史里回捞最近一条"用户发来的合同/文书"原文——追问轮与比较轮共用同一把尺。"""
    for message in reversed(recent):
        content = message["content"]
        description = message["image_desc"]
        is_contract_message = deps.is_contract_review(content) or (
            content == "[图片]" and deps.is_contract_review(description)
        )
        if message["role"] == "user" and is_contract_message:
            return description if deps.is_contract_review(description) else content
    return ""


_EXIT_PUNCT = "，。！？、；：,.!?　（）"


def is_contract_exit(text: str) -> bool:
    normalized = "".join(ch for ch in (text or "").lower() if not ch.isspace() and ch not in _EXIT_PUNCT)
    if not normalized or len(normalized) > _CONTRACT_EXIT_MAX_CHARS:
        return False
    return any(mark in normalized for mark in CONTRACT_EXIT_MARKS)


# 口径②（2026-10-13）：状态暂不落盘，但**必须有过期边界**——不活跃超过 TTL 即视为未激活。
# 过期要**连着派生状态一起失效**：合同态不只是模板开关，它还牵着"逐条证据集"与上一轮合同文本回捞
# （LangGraph 的 prune 教训：只清一个集合、派生状态会静默重建出旧东西），所以这里摘除时同步清时间戳。
CONTRACT_IDLE_TTL_S = 30 * 60
_contract_touched: dict[int, float] = {}
# 口径③⑥：“先确认”每会话只问一次（二段式澄清的“问两次上限”形状）；问过之后同形输入按普通分析走
_contract_intent_asked: set[int] = set()


def mark_contract_turn(conv_id: int, *, now: float | None = None) -> None:
    _contract_touched[conv_id] = now if now is not None else time.monotonic()


def contract_session_active(conv_id: int, active: MutableSet[int], *, now: float | None = None) -> bool:
    """合同态是否仍激活：在集合里 且 未闲置过期；过期即**摘除**而不是只判 False。"""
    if conv_id not in active:
        return False
    t = now if now is not None else time.monotonic()
    stamp = _contract_touched.get(conv_id)
    if stamp is None:  # 旧路径进来的会话没有时间戳：当活跃并补记，不误杀在途会话
        _contract_touched[conv_id] = t
        return True
    if t - stamp > CONTRACT_IDLE_TTL_S:
        active.discard(conv_id)
        _contract_touched.pop(conv_id, None)
        return False
    _contract_touched[conv_id] = t  # 本轮活跃 ⇒ 续期（闲置 TTL，不是绝对 TTL）
    return True


def cleanup_persisted_images(
    image_rel: str | None,
    thumb_rel: str | None,
    *,
    media_dir: str | Path | None = None,
    backend_dir: str | Path | None = None,
) -> None:
    """Best-effort cleanup restricted to the two files returned for this request."""
    if media_dir is None or backend_dir is None:
        from multimodal import BASE, MEDIA_DIR

        media_root = Path(MEDIA_DIR).resolve()
        backend_root = Path(BASE).resolve()
    else:
        media_root = Path(media_dir).resolve()
        backend_root = Path(backend_dir).resolve()

    for relative_path in (image_rel, thumb_rel):
        if not relative_path:
            continue
        candidate = (backend_root / relative_path).resolve()
        try:
            candidate.relative_to(media_root)
        except ValueError:
            continue
        try:
            if candidate.is_file():
                candidate.unlink()
        except OSError:
            continue


def _describe_image_with_configured_capability(image: str, text: str) -> str:
    with _image_describer_config_lock:
        describer = _configured_image_describer
    if describer is None:
        raise RuntimeError("image description capability is not configured by the application")
    return describer(image, text)


def _default_rewrite_for_retrieval(
    raw_query: str,
    recent_ser: list[dict[str, str]],
    recent: list[Any],
    has_options: bool,
) -> str:
    if not recent_ser or has_options:
        return raw_query
    from llm_guard import llm_guard
    from llm_registry import registry
    from memory import rewrite_query

    with llm_guard:
        return rewrite_query(registry.get(), recent, raw_query)


def _default_bootstrap_dependencies() -> BootstrapDependencies:
    import database
    import domain_rules
    import intent
    import memory
    import multimodal
    import query_understand
    from settings import settings

    return BootstrapDependencies(
        session_factory=database.SessionLocal,
        # W06-C §5.2：request_bootstrap 的历史序列化消费**同一安全投影**（已知失效助手/摘要不进模型输入），
        # 原 `memory.load_context` 保留给 UI/审计；投影返回形状兼容旧的 (summary, [可用条目])。
        load_context=memory.load_model_context_bootstrap,
        validate_image=multimodal.validate_image,
        persist_image=multimodal.persist_image,
        cleanup_persisted_image=cleanup_persisted_images,
        describe_image=_describe_image_with_configured_capability,
        classify_intent=intent.classify_intent,
        is_exam_question=query_understand._is_exam_question,
        has_exam_options=query_understand.has_exam_options,
        is_contract_review=domain_rules.is_contract_review,
        contract_trigger_reason=domain_rules.contract_trigger_reason,
        feature_multi_analyze=settings.feature_multi_analyze,
        contract_conversations=DEFAULT_CONTRACT_STATE.active,
        contract_reviewed_conversations=DEFAULT_CONTRACT_STATE.reviewed,
        is_contract_exit=is_contract_exit,
    )


def _default_fast_path_dependencies() -> FastPathDependencies:
    import domain_rules
    import knowledge_service
    import query_understand
    import rag_chain
    import retrieval
    from settings import settings

    return FastPathDependencies(
        feature_study_retrieval=settings.feature_study_retrieval,
        is_meta_study=query_understand.is_meta_study,
        rewrite_for_retrieval=_default_rewrite_for_retrieval,
        scenario_supplement_docs=retrieval.scenario_supplement_docs,
        retrieve_exam=retrieval.retrieve_exam,
        cheating_docs=domain_rules.cheating_docs,
        build_contract_data=domain_rules.build_contract_data,
        retrieve=retrieval.retrieve,
        # 票 C21-A Task 2：产生处的默认取语料口绑到**有界资格选择**入口（窗口 8+1、资格唯一真源
        # `qa_eligibility`、可验证重复）。raw `knowledge_service.search_qa`（k=1）保留给写侧幂等去重，
        # 不再由默认依赖调用；`prepare_fast_path` 的统一资格复核与显式历史日期绕过 QA 均不变。
        search_qa=knowledge_service.search_eligible_qa,
        is_consumer_clause_scenario=domain_rules.is_consumer_clause_scenario,
        consumer_clause_docs=domain_rules.consumer_clause_docs,
        is_consumer_fraud_scenario=domain_rules.is_consumer_fraud_scenario,
        consumer_fraud_docs=domain_rules.consumer_fraud_docs,
        format_docs=rag_chain.format_docs,
    )


def bootstrap_request(
    user_id: int,
    conversation_id,
    text: str,
    image,
    client_truncated: bool,
    *,
    case_domain: str | None = None,
    law_as_of: date | None = None,
    _deps: BootstrapDependencies | None = None,
) -> RequestBootstrap:
    """Validate and persist an accepted request without invoking retrieval or routing."""
    deps = _deps or _default_bootstrap_dependencies()
    db = deps.session_factory()
    state_action: str | None = None
    image_rel = thumb_rel = None
    try:
        conv = db.get(Conversation, conversation_id) if conversation_id else None
        if conv is None or conv.user_id != user_id:
            conv = Conversation(user_id=user_id, title="", summary="", message_count=0)
            db.add(conv)
            db.flush()
        conv_id = conv.id
        if not isinstance(conv_id, int):
            raise RuntimeError("conversation id was not assigned after flush")

        summary, recent_messages = deps.load_context(db, conv)
        recent = [
            {"role": message.role, "content": message.content or "", "image_desc": message.image_desc or ""}
            for message in recent_messages
        ]
        recent_snapshots = [
            RecentMessageSnapshot(role=message["role"], content=message["content"], image_desc=message["image_desc"])
            for message in recent
        ]

        image_description = ""
        image_failure: str | None = None
        if image:
            deps.validate_image(image)
            image_rel, thumb_rel = deps.persist_image(image)
            # 票 W07（C04＝甲）：这里**不再**有「失败与空内容同形」的通道。
            # 调用失败 ⇒ 落一个归因键后把原异常**逐字**向上抛（不包装、不换类型：
            # `tests/test_request_bootstrap.py::test_bootstrap_rolls_back_and_closes_on_image_failure`
            # 钉的就是原始异常穿过 bootstrap 回滚＋清理那条路）；main 的识图出口再把这一发变成 502。
            # 模型正常返回但内容为空 ⇒ 该轮继续，但契约上留下失败位＋另一个归因键。
            # 两个键**分键不分门**（同 QA 语料那两道门）：合成一键就只知道「图没读出来」而不知道是哪一段。
            # 刻意不落题干、不落图片内容、不落 base64（AUTH-3 日志不落原文）。
            try:
                image_description = deps.describe_image(image, text or "")
            except Exception:
                logging.getLogger("legal.chat").warning(
                    "识图调用失败 ⇒ 本轮在 HTTP/SSE 层明确报错",
                    extra={"image_describe_failed": True},
                )
                raise
            if not image_description:
                image_failure = "content_empty"
                logging.getLogger("legal.chat").warning(
                    "识图返回空内容 ⇒ 本轮仅依据文字",
                    extra={"image_content_empty": True},
                )

        raw_query = " ".join(part for part in [text or "", image_description] if part).strip()
        if not raw_query:
            raw_query = "请描述并分析图片中的法律相关内容"
        supplement_history = " ".join(
            message["content"] for message in recent if message["role"] == "user" and message["content"]
        )
        supplement_text = (text or raw_query) + (" " + supplement_history[-400:] if supplement_history else "")

        intent = deps.classify_intent(text or raw_query)
        is_exam = deps.is_exam_question(text or raw_query)
        has_options = deps.has_exam_options(text or raw_query)
        contract_query = text or raw_query
        in_contract_mode = contract_session_active(conv_id, deps.contract_conversations)
        exiting_contract = in_contract_mode and deps.is_contract_exit(contract_query)
        active_contract = in_contract_mode and not exiting_contract
        # 口径③⑥：只有“条款自指”这一支与案情叙述同形——先确认审查意图，不静默切换。
        # 会话级只问一次；问过之后同形输入按普通分析走（既不反复追问，也不偷偷切换）。
        fresh_reason = None if in_contract_mode else deps.contract_trigger_reason(contract_query)
        ambiguous_fresh = fresh_reason == "clause_labels"
        intent_confirm = ambiguous_fresh and conv_id not in _contract_intent_asked
        if intent_confirm:
            _contract_intent_asked.add(conv_id)
        clause_only_settled = ambiguous_fresh and not intent_confirm
        contract_mode = (
            deps.feature_multi_analyze
            and intent == "legal_query"
            and ((deps.is_contract_review(contract_query) and not clause_only_settled) or active_contract)
        )

        contract_text = None
        if contract_mode:
            if deps.is_contract_review(contract_query):
                state_action = "confirm" if intent_confirm else "enter"
                # 口径②：明确要求"对比两份"时不重置——上一份从历史回捞、与本轮一起带上；
                # 其余情况（换合同）维持覆盖语义（旧合同不回捞）。
                comparing = any(mark in (text or "") for mark in _CONTRACT_COMPARE_MARKS)
                previous_contract = _previous_contract_text(recent, deps) if comparing else ""
                if image and image_description and deps.is_contract_review(image_description):
                    contract_text = image_description
                else:
                    contract_text = text or raw_query
                if previous_contract:
                    contract_text = (previous_contract + chr(10) + contract_text).strip()
            else:
                previous_contract = _previous_contract_text(recent, deps)
                contract_text = (
                    (previous_contract + "\n" + (text or "")) if previous_contract else (text or raw_query)
                ).strip()
        elif exiting_contract:
            state_action = "exit"

        user_content = text if text and text.strip() else ("[图片]" if image else "")
        db.add(
            Message(
                conversation_id=conv_id,
                role="user",
                content=user_content,
                image_ref=image_rel,
                thumb_ref=thumb_rel,
                image_desc=image_description or None,
            )
        )
        db.query(Conversation).filter(Conversation.id == conv_id).update(
            {"message_count": func.coalesce(Conversation.message_count, 0) + 1},
            synchronize_session=False,
        )
        conv.last_active_at = datetime.utcnow()
        if not conv.title:
            image_title = "[图片] " + image_description[:20] if image else ""
            conv.title = ((text or image_title) or "新对话")[:200]
        if not conv.question:
            conv.question = (text or user_content)[:2000]
        db.commit()

        if state_action == "enter":
            deps.contract_conversations.add(conv_id)
            mark_contract_turn(conv_id)
        elif state_action == "exit":
            deps.contract_conversations.discard(conv_id)
            deps.contract_reviewed_conversations.discard(conv_id)
            _contract_touched.pop(conv_id, None)

        return RequestBootstrap(
            conv_id=conv_id,
            summary=summary,
            recent=recent,
            recent_messages=recent_snapshots,
            image=image,
            user_text=text or "",
            image_rel=image_rel,
            thumb_rel=thumb_rel,
            image_description=image_description,
            raw_query=raw_query,
            supplement_text=supplement_text,
            intent=intent,
            is_exam=is_exam,
            has_options=has_options,
            contract_mode=contract_mode,
            contract_text=contract_text,
            intent_confirm=intent_confirm,
            client_truncated=client_truncated,
            case_domain=case_domain,
            law_as_of=law_as_of,
            image_failure=image_failure,
        )
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            deps.cleanup_persisted_image(image_rel, thumb_rel)
        except Exception:
            pass
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass


def article_miss_note(report: dict[str, Any]) -> str:
    """把条号对账结果渲染成递给模型的一句说明；没有未命中就返回空串。

    措辞按 C02 裁定的两半写（plan:198「显式未命中，**允许说明性旁引**」）：
    - 说清"所问条号本轮未被直接命中"，并且**按态分措辞**——`version_uncertain` 不能说成"未收录"
      （plan W04 第 2 条：查不到不证明法律不存在）；
    - 引用别的条文是被允许的，只要求说明它与所问条号的关系。
      这里**刻意不写**「只能引用所问条号」那类禁语：`tests/test_explicit_article_answer_contract.py`
      的 `test_explanatory_side_citation_is_allowed_not_banned` 就是钉这个反向的——把"别旁条冒充"
      修成"禁止任何旁引"恰好撞上裁定明令禁止的方向。

    文案只在这一处生成；出口必须调这个函数，别处不许再抄一份（哨兵用例钉同一性）。
    """
    missing = report.get("missing") or []
    if not missing:
        return ""
    listed = "、".join(f"《{s}》{a}" for s, a in missing)
    state = report.get("state")
    if state == "version_uncertain":
        head = f"以下条文在本库中存在，但按本次查询时点版本不确定：{listed}。"
    elif state == "not_in_library":
        head = f"以下条文未在本知识库中直接命中：{listed}。"
    else:  # mixed：两种同时出现，分开说才不是假陈述
        absent = "、".join(f"《{s}》{a}" for s, a in (report.get("missing_absent") or []))
        unsure = "、".join(f"《{s}》{a}" for s, a in (report.get("missing_version_uncertain") or []))
        head = f"以下条文未在本知识库中直接命中：{absent}；以下条文存在但按查询时点版本不确定：{unsure}。"
    return (
        f"【条号对账】{head}"
        "若你改用其他条文作答，请先向用户说明它与所问条文的关系；不要把替代条文当作对所问条号的直接回答。"
    )


def prepare_fast_path(
    bootstrap: RequestBootstrap,
    *,
    _deps: FastPathDependencies | None = None,
) -> dict[str, Any]:
    """Run the legacy retrieval/cache branches after the request has committed."""
    deps = _deps or _default_fast_path_dependencies()
    raw_query = bootstrap.raw_query
    contract_data = None
    cutoff = bootstrap.law_as_of.isoformat() if bootstrap.law_as_of is not None else None

    if bootstrap.intent == "study_aid":
        if deps.feature_study_retrieval and not deps.is_meta_study(bootstrap.user_text or raw_query):
            rewritten = deps.rewrite_for_retrieval(
                raw_query, bootstrap.recent, bootstrap.recent_messages, bootstrap.has_options
            )
            docs = deps.scenario_supplement_docs(bootstrap.supplement_text, cutoff=cutoff) + deps.retrieve_exam(
                rewritten, cutoff=cutoff
            )
        else:
            rewritten = raw_query
            docs = []
        qa_hit = None
    elif bootstrap.intent == "cheating_request":
        rewritten = raw_query
        docs = deps.cheating_docs(cutoff=cutoff)
        qa_hit = None
    elif bootstrap.intent == "chitchat":
        rewritten = raw_query
        docs = []
        qa_hit = None
    elif bootstrap.contract_mode:
        rewritten = raw_query
        contract_data = deps.build_contract_data(bootstrap.contract_text or raw_query, cutoff=cutoff)
        if bootstrap.client_truncated:
            contract_data["truncated"] = True
        if bootstrap.intent_confirm:
            # 口径③⑥：与 need_clarify 同一条通道（contract_data 内字段）——pre 的键集被用例钉死，不能加新键
            contract_data["confirm_intent"] = True
        docs = contract_data["docs"]
        qa_hit = None
    else:
        rewritten = deps.rewrite_for_retrieval(
            raw_query, bootstrap.recent, bootstrap.recent_messages, bootstrap.has_options
        )
        if bootstrap.is_exam:
            docs = deps.scenario_supplement_docs(bootstrap.supplement_text, cutoff=cutoff) + deps.retrieve_exam(
                rewritten, cutoff=cutoff
            )
        else:
            docs = deps.retrieve(rewritten, k=10, cutoff=cutoff)
        # QA 语料按**当日**沉淀，无版本轴 ⇒ 历史查询不可直返（见 main._qa_direct_return 分水岭守卫）。
        qa_hit = None if cutoff else deps.search_qa(rewritten)
        if qa_hit is not None:
            # 票 W06-FIX F3/V2：产生处**一次判全**——合成判据的唯一真源是
            # `qa_eligibility.qa_read_eligible`（状态轴→来源可校验→引用在库，就这一份排序），
            # 本模块此前自写一遍「来源→引用、不含状态轴」的形状到此为止。
            # 状态装载走 `load_read_state_for`：同一次请求里三个判定点共用一条 session（F9/V8）。
            # 三道门**分键不分门**（在册口径不变）：`qa_provenance_refused` / `qa_citation_refused`
            # 继续各落一个布尔读数，`state` 那一档只落 `qa_eligibility_reason`＋`qa_candidate_id`；
            # 合成一键就只知道"语料被拦了"而不知道是哪道门在衰减，也不许把判据分解抄进日志
            # （那等于放第二份判据，改那道门时它会开始说谎）。题干与答案一律不落（AUTH-3）。
            import qa_eligibility

            verdict = qa_eligibility.qa_read_eligible(qa_hit, qa_eligibility.load_read_state_for(qa_hit))
            if not verdict.allow:
                # 拦了要留痕：这道门关掉的是**零 token 直返**，静默拒绝的话"语料在衰减"线上没有任何痕迹
                # （形状同 `main._law_version_gate` 的绊线日志）。
                # 来源校验不了与引用不在库的记录都不给它们进 `pre["qa_hit"]`：直返（main._qa_direct_return）
                # 与 prompt 注入（main._build_messages 的"此前已确认的问答"）两个出口共用这一处判定。
                # 顺序仍然是**形状判据在时效判据之前**（无效记录不付读库成本，
                # `test_shape_gate_runs_before_the_kb_and_skips_the_lookup`；`qa_read_eligible` 内部同序）。
                qa_eligibility.log_read_denial(qa_hit, verdict.reason, with_gate_boolean=True)
                qa_hit = None
        if not bootstrap.is_exam:
            docs = deps.scenario_supplement_docs(bootstrap.supplement_text, cutoff=cutoff) + docs
            query = bootstrap.user_text or raw_query
            if deps.is_consumer_clause_scenario(query):
                docs = deps.consumer_clause_docs(cutoff=cutoff) + docs
            if deps.is_consumer_fraud_scenario(query):
                docs = deps.consumer_fraud_docs(cutoff=cutoff) + docs

    if cutoff:
        from retrieval_core import is_valid_by_time

        # 各取数口已按同一 cutoff 过滤，这里仍复筛一遍：谓词唯一（`retrieval_core.is_valid_by_time`），
        # 漏传 cutoff 的代价是**把当日版本下发给历史查询**（静默改用现行法），比丢证据更坏。
        docs = [doc for doc in docs if is_valid_by_time(doc.metadata, cutoff)]

    context = deps.format_docs(docs)
    # D-50 / C02：问题里点名的条号若未直接命中，**先明说**再放补充条文——不能丢了标记只剩别的 docs
    # 递给模型（那正是"旁条冒充主条"的成因）。判定与文案都只有一份真源：
    # `retrieval.article_lookup_report` 判态、本模块 `article_miss_note` 出文。
    from retrieval import article_lookup_report, exact_article_lookup

    miss_note = article_miss_note(
        article_lookup_report(
            raw_query,
            docs,
            lookup_with_cutoff=lambda s, a: exact_article_lookup(s, a, cutoff),
            lookup_any_time=exact_article_lookup,
        )
    )
    if miss_note:
        context = f"{miss_note}\n\n{context}" if context else miss_note
    sources = [
        {
            "source": document.metadata.get("source", ""),
            "article": document.metadata.get("article", ""),
            "effective_from": document.metadata.get("effective_from", ""),
            "effective_to": document.metadata.get("effective_to", ""),
            "status": document.metadata.get("status", ""),
        }
        for document in docs
    ]
    prepared = {
        "conv_id": bootstrap.conv_id,
        "summary": bootstrap.summary,
        "recent": bootstrap.recent,
        "context": context,
        "qa_hit": qa_hit,
        "sources": sources,
        "image": bootstrap.image,
        "user_text": bootstrap.user_text,
        "image_rel": bootstrap.image_rel,
        "thumb_rel": bootstrap.thumb_rel,
        "rewritten": rewritten,
        "intent": bootstrap.intent,
        "is_exam": bootstrap.is_exam,
        "has_options": bootstrap.has_options,
        "contract_data": contract_data,
    }
    if cutoff:
        prepared["law_as_of"] = bootstrap.law_as_of
    return prepared
