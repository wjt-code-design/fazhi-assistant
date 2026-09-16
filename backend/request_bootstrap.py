from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

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


@dataclass(frozen=True)
class FastPathDependencies:
    feature_study_retrieval: bool
    is_meta_study: Callable[[str], bool]
    rewrite_for_retrieval: Callable[[str, list[dict[str, str]], list[Any], bool], str]
    scenario_supplement_docs: Callable[[str], list[Any]]
    retrieve_exam: Callable[[str], list[Any]]
    cheating_docs: Callable[[], list[Any]]
    build_contract_data: Callable[[str], dict[str, Any]]
    retrieve: Callable[..., list[Any]]
    search_qa: Callable[[str], Any]
    is_consumer_clause_scenario: Callable[[str], bool]
    consumer_clause_docs: Callable[[], list[Any]]
    is_consumer_fraud_scenario: Callable[[str], bool]
    consumer_fraud_docs: Callable[[], list[Any]]
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


CONTRACT_EXIT_MARKS = (
    "退出合同",
    "不审合同",
    "不用审了",
    "不再审合同",
    "结束合同",
    "结束评估",
    "换个话题",
    "换一个问题",
    "暂停",
    "结束",
)


def is_contract_exit(text: str) -> bool:
    normalized = (text or "").strip().lower()
    return any(mark in normalized for mark in CONTRACT_EXIT_MARKS)


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
        exiting_contract = conv_id in deps.contract_conversations and deps.is_contract_exit(contract_query)
        active_contract = conv_id in deps.contract_conversations and not exiting_contract
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
        elif state_action == "exit":
            deps.contract_conversations.discard(conv_id)
            deps.contract_reviewed_conversations.discard(conv_id)

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

    if bootstrap.intent == "study_aid":
        if deps.feature_study_retrieval and not deps.is_meta_study(bootstrap.user_text or raw_query):
            rewritten = deps.rewrite_for_retrieval(
                raw_query, bootstrap.recent, bootstrap.recent_messages, bootstrap.has_options
            )
            docs = deps.scenario_supplement_docs(bootstrap.supplement_text) + deps.retrieve_exam(rewritten)
        else:
            rewritten = raw_query
            docs = []
        qa_hit = None
    elif bootstrap.intent == "cheating_request":
        rewritten = raw_query
        docs = deps.cheating_docs()
        qa_hit = None
    elif bootstrap.intent == "chitchat":
        rewritten = raw_query
        docs = []
        qa_hit = None
    elif bootstrap.contract_mode:
        rewritten = raw_query
        contract_data = deps.build_contract_data(bootstrap.contract_text or raw_query)
        if bootstrap.client_truncated:
            contract_data["truncated"] = True
        docs = contract_data["docs"]
        qa_hit = None
    else:
        rewritten = deps.rewrite_for_retrieval(
            raw_query, bootstrap.recent, bootstrap.recent_messages, bootstrap.has_options
        )
        if bootstrap.is_exam:
            docs = deps.scenario_supplement_docs(bootstrap.supplement_text) + deps.retrieve_exam(rewritten)
        else:
            docs = deps.retrieve(rewritten, k=10)
        qa_hit = deps.search_qa(rewritten)
        if not bootstrap.is_exam:
            docs = deps.scenario_supplement_docs(bootstrap.supplement_text) + docs
            query = bootstrap.user_text or raw_query
            if deps.is_consumer_clause_scenario(query):
                docs = deps.consumer_clause_docs() + docs
            if deps.is_consumer_fraud_scenario(query):
                docs = deps.consumer_fraud_docs() + docs

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
    return {
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
