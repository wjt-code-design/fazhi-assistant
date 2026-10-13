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
        load_context=memory.load_context,
        validate_image=multimodal.validate_image,
        persist_image=multimodal.persist_image,
        cleanup_persisted_image=cleanup_persisted_images,
        describe_image=_describe_image_with_configured_capability,
        classify_intent=intent.classify_intent,
        is_exam_question=query_understand._is_exam_question,
        has_exam_options=query_understand.has_exam_options,
        is_contract_review=domain_rules.is_contract_review,
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
        search_qa=knowledge_service.search_qa,
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
        if image:
            deps.validate_image(image)
            image_rel, thumb_rel = deps.persist_image(image)
            image_description = deps.describe_image(image, text or "")

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
        contract_mode = (
            deps.feature_multi_analyze
            and intent == "legal_query"
            and (deps.is_contract_review(contract_query) or active_contract)
        )

        contract_text = None
        if contract_mode:
            if deps.is_contract_review(contract_query):
                state_action = "enter"
                if image and image_description and deps.is_contract_review(image_description):
                    contract_text = image_description
                else:
                    contract_text = text or raw_query
            else:
                previous_contract = ""
                for message in reversed(recent):
                    content = message["content"]
                    description = message["image_desc"]
                    is_contract_message = deps.is_contract_review(content) or (
                        content == "[图片]" and deps.is_contract_review(description)
                    )
                    if message["role"] == "user" and is_contract_message:
                        previous_contract = description if deps.is_contract_review(description) else content
                        break
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
            client_truncated=client_truncated,
            case_domain=case_domain,
            law_as_of=law_as_of,
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
        from retrieval import qa_citations_in_kb
        from retrieval_core import qa_provenance_verifiable

        qa_hit = None if cutoff else deps.search_qa(rewritten)
        if qa_hit is not None and not qa_provenance_verifiable(qa_hit):
            # 拦了要留痕：这道门关掉的是**零 token 直返**，静默拒绝的话"语料在衰减"线上没有任何痕迹
            # （形状同 `main._law_version_gate` 的绊线日志）。刻意只落一个归因键、不落判据分解——
            # 把"缺 basis 还是缺引用"抄进日志等于放第二份判据，改那道门时它会开始说谎。
            # 也不落问题原文（AUTH-3）：语料题干可能就是用户问句。
            logging.getLogger("legal.chat").warning(
                "QA 语料命中但来源不可校验 ⇒ 不参与生成",
                extra={"qa_provenance_refused": True},
            )
            # 来源校验不了的记录不给它进 `pre["qa_hit"]`：直返（main._qa_direct_return）与
            # prompt 注入（main._build_messages 的"此前已确认的问答"）两个出口共用这一处判定。
            qa_hit = None
        if qa_hit is not None and not qa_citations_in_kb(qa_hit):
            # 票 W1（2026-09-25，Owner 裁决"对称收口，判据上提到产生处"）：上面那道只问"引用给不给得出"，
            # 这一道问"引用核验不核验得了"。此前时效判定**只写在** `main._qa_direct_return` 里，于是引用了
            # 已删条目的记录照样进 `pre["qa_hit"]`，被 `_build_messages` 以"此前已确认的问答（可优先参考）"
            # 递给模型——那是第 8 节② 漏口的后一半。判据本体住在 `retrieval.qa_citations_in_kb`，
            # 两个出口调**同一个对象**（不许各抄一份循环；`tests/test_qa_citation_gate_symmetry.py` 钉这条同一性）。
            # 刻意放在形状判据**之后**：无效形状不付读库成本（`test_shape_gate_runs_before_the_kb_and_skips_the_lookup`）。
            # 归因**分键不分门**：这是第二道门，与 `qa_provenance_refused` 各一个读数——
            # 合成一键就只知道"语料被拦了"而不知道是哪道门在衰减。
            logging.getLogger("legal.chat").warning(
                "QA 语料引用的条文不在库 ⇒ 不参与生成",
                extra={"qa_citation_refused": True},
            )
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
