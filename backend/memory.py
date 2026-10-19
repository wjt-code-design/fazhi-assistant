"""多轮上下文 + 增量滚动压缩 + 条件查询改写。

- 上下文窗口 = summary + 最近 RECENT_K 条原文。
- 压缩触发：message_count > TURN_THRESHOLD 或 (summary+recent) 字符 > CHAR_THRESHOLD。
- 压缩为增量：用 summary_upto 指针，只把"刚滑出窗口的旧消息"合并进摘要，不重复劳动。
- 旧消息不删除（保留历史/审计），窗口仅靠 summary+recent 表达。
- 查询改写仅在"有历史"时做；单轮跳过，省一次调用。
"""

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Conversation, Message

RECENT_K = 6
TURN_THRESHOLD = 12
CHAR_THRESHOLD = 6000
SUMMARY_MAX = 400


def _msg_text(m: Message) -> str:
    role = "用户" if m.role == "user" else ("助手" if m.role == "assistant" else "系统")
    return f"{role}：{m.content or ''}"


def recent_messages(db: Session, conversation_id: int) -> list[Message]:
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(RECENT_K)
        .all()
    )
    return list(reversed(rows))  # 转为时间正序


def char_count(summary: str, recent: list[Message]) -> int:
    return len(summary or "") + sum(len(m.content or "") for m in recent)


def load_context(db: Session, conv: Conversation) -> tuple[str, list[Message]]:
    """原始历史读取接口（UI/审计/管理面）——**原文照旧、不清库、不改写**。

    模型侧要用的安全投影见 `load_model_context`：两者刻意分开，读历史 UI 不得顺手改动来源。
    """
    return (conv.summary or ""), recent_messages(db, conv.id)


# ==================== W06-C：模型上下文投影（§5.2）====================
# 历史原文/UI 保留（`load_context`），模型输入另走投影：已知来源被撤回/隔离的记录不进模型上下文。
# 投影同时携带**每个条目与摘要的真实来源包**，供再沉淀时继承祖先（防撤回经"摘要→改写→回答"回流）。


class ModelMessage:
    """带内部来源的模型上下文条目（duck-typed：role/content/image_desc 与 ORM Message 同形）。

    `state`（W06-C H07 已裁三态）：
    - `user`：用户自述——**一律保留**（不按相同字符串硬删用户输入）；
    - `verified`：来源包完整且依赖复核通过 ⇒ 可作可信既有上下文交给模型；
    - `revoked`：来源包完整但依赖已失效（撤回/隔离/变版/变内容/读不动）⇒ 剔除；
    - `unknown`：来源未知（NULL／坏格式／`complete=False`）⇒ **不作为已确认依据交给模型**（剔除）。
    """

    __slots__ = ("message_id", "role", "content", "image_desc", "provenance", "state", "reusable")

    def __init__(self, message_id, role, content, image_desc, provenance, state, reusable):
        self.message_id = message_id
        self.role = role
        self.content = content
        self.image_desc = image_desc
        self.provenance = provenance
        self.state = state
        self.reusable = reusable


class ModelContext:
    """一次模型上下文投影的结果：可用的 summary/recent 及其完整传递依赖。"""

    __slots__ = (
        "summary",
        "summary_provenance",
        "summary_usable",
        "summary_state",
        "recent",
        "dependencies",
        "unknown_history",
    )

    def __init__(
        self, summary, summary_provenance, summary_usable, summary_state, recent, dependencies, unknown_history
    ):
        self.summary = summary
        self.summary_provenance = summary_provenance
        self.summary_usable = summary_usable
        self.summary_state = summary_state
        self.recent = recent
        self.dependencies = dependencies
        self.unknown_history = unknown_history


def _provenance_of(text):
    import qa_eligibility as qe

    return qe.parse_provenance(text)


def _provenance_state(prov) -> str:
    """把来源包判成 H07 三态之一：`verified` / `revoked` / `unknown`（未知含 NULL/坏格式/不完整）。"""
    import qa_eligibility as qe

    if prov is None or not prov.complete:
        return "unknown"
    return "verified" if qe.provenance_state(prov).allow else "revoked"


def load_model_context(db: Session, conv: Conversation, *, fresh: bool = False) -> ModelContext:
    """模型侧安全投影（票 W06-C §5.2，旧未知来源输入规则按 Owner 已裁 H07 实施）。

    三态（可分辨「未知 vs 已核验 vs 已撤回」）：
    - 用户消息**一律保留**（用户事实不被字符串误删）；
    - `verified`（来源完整且复核通过）⇒ 交模型作可信既有上下文；
    - `revoked`（来源完整但已失效）⇒ 剔除；
    - `unknown`（NULL／坏格式／`complete=False`）⇒ **不作为已确认依据交给模型**（剔除）；原文/UI 仍在库里。
      这不是「全量屏蔽历史」（用户事实与已核验内容仍可用），也不是「默认放行未知」。

    聚合依赖：只要出现未知来源（assistant/摘要）⇒ `dependencies=None`（不把未知当可信空集）；
    被剔除的失效来源不贡献祖先。

    `fresh` 形参保留给阶段边界（本函数每次调用都新读 SQL，天然 fresh）。
    """
    summary_text = conv.summary or ""
    summary_prov = _provenance_of(getattr(conv, "summary_provenance", None))
    unknown_history = False
    ancestors = []

    if not summary_text:
        summary_state = "empty"
    else:
        summary_state = _provenance_state(summary_prov)
    summary_usable = summary_state == "verified"
    if summary_state == "unknown":
        unknown_history = True
    elif summary_state == "verified":
        ancestors.append(summary_prov)

    recent: list[ModelMessage] = []
    for m in recent_messages(db, conv.id):
        prov = _provenance_of(getattr(m, "qa_provenance", None))
        if m.role != "assistant":
            state = "user"  # 用户自述：一律保留，不判来源
        else:
            state = _provenance_state(prov)
        reusable = state in ("user", "verified")
        recent.append(ModelMessage(m.id, m.role, m.content or "", m.image_desc or "", prov, state, reusable))
        if state == "unknown":
            unknown_history = True
        if not reusable:
            continue
        if state == "verified":
            ancestors.append(prov)

    if unknown_history:
        dependencies = None
    else:
        import qa_eligibility as qe

        prov = qe.build_provenance((), ancestors=tuple(ancestors))
        dependencies = None if prov is None else prov.qa_dependencies
    return ModelContext(
        summary=(summary_text if summary_usable else ""),
        summary_provenance=summary_prov,
        summary_usable=summary_usable,
        summary_state=summary_state,
        recent=tuple(recent),
        dependencies=dependencies,
        unknown_history=unknown_history,
    )


def load_model_context_bootstrap(db: Session, conv: Conversation):
    """`BootstrapDependencies.load_context` 的默认绑定：返回兼容旧接口的 `(summary, [可用条目])`。

    投影同时产出安全 summary 与可用 recent；被剔除的失效/未知来源**不进入模型输入**（原文仍在库里）。
    """
    ctx = load_model_context(db, conv)
    return ctx.summary, [m for m in ctx.recent if m.reusable]


def needs_compress(conv: Conversation, recent: list[Message]) -> bool:
    """双阈值触发：轮次超 TURN_THRESHOLD 或 (摘要+近文) 字符超 CHAR_THRESHOLD。

    是否真有可压缩的旧消息，由 compress() 内的 _gap_messages 判定；为空则 no-op，不会空耗 LLM。
    """
    mc = conv.message_count or 0
    return mc > TURN_THRESHOLD or char_count(conv.summary, recent) > CHAR_THRESHOLD


def _gap_messages(db: Session, conv: Conversation) -> list[Message]:
    """尚未被摘要覆盖、且已滑出最近窗口的消息（时间正序）。"""
    window_start = max(0, (conv.message_count or 0) - RECENT_K)
    upto = conv.summary_upto or 0
    if upto >= window_start:
        return []
    # 取第 upto..window_start 条（按时间正序，用 offset/limit）
    return (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
        .offset(upto)
        .limit(window_start - upto)
        .all()
    )


def _extend_summary(llm, existing: str, batch: list[Message]) -> str:
    batch_text = "\n".join(_msg_text(m) for m in batch)
    sys = (
        "你是法律对话摘要器。把'新对话'增量合并进'已有摘要'，保留：涉及的法律主题、"
        "已引用的条文、已给出的结论、用户尚未解决的问题；丢弃寒暄与冗余。"
        f"输出更新后的完整摘要，不超过{SUMMARY_MAX}字，不要加前缀解释。"
    )
    user = f"已有摘要：\n{existing or '（无）'}\n\n新对话：\n{batch_text}"
    try:
        resp = llm.invoke([SystemMessage(content=sys), HumanMessage(content=user)])
        new = (resp.content or "").strip()
        return new[:SUMMARY_MAX] if new else (existing or "")
    except Exception:
        return None  # 失败信号：调用方不推进窗口，避免旧消息永久丢失


def compress(db: Session, conv: Conversation, llm) -> bool:
    """增量压缩；返回是否实际更新了摘要。同步函数，调用方放线程池。

    W06-C §5.3：内容 / `summary_upto` / `summary_provenance` **原子**更新；以读取时的
    摘要+游标+来源快照作乐观并发条件（另一压缩抢先提交/期间撤回 ⇒ 拒绝过时产物，不覆盖较新安全摘要）。
    H09：已失效的旧摘要**不再**作为 `existing` 喂入，从允许材料（本批消息）安全重建。
    """
    import qa_eligibility as qe

    batch = _gap_messages(db, conv)
    if not batch:
        return False
    expected_upto = conv.summary_upto or 0
    expected_summary = conv.summary or ""
    existing = conv.summary or ""
    existing_prov = qe.parse_provenance(getattr(conv, "summary_provenance", None))
    # L9：与 H07「模型侧不复用未知来源结论」及 `load_model_context`（未知摘要 not usable）对齐——
    # 旧摘要来源为 NULL／不完整（未知）时一律按**不可用**处理，不作为 existing 输入喂压缩器；
    # 原文/旧 summary 文本不硬删（被新摘要覆盖属既有压缩语义，不是删除历史）。
    existing_usable = existing_prov is not None and existing_prov.complete and qe.provenance_state(existing_prov).allow

    batch_unknown = False
    batch_prov = []
    for m in batch:
        p = qe.parse_provenance(getattr(m, "qa_provenance", None))
        if p is None or not p.complete:
            if getattr(m, "role", "") == "assistant" or getattr(m, "role", "") == "system":
                batch_unknown = True
        else:
            batch_prov.append(p)

    # 失效旧摘要不进 existing；重建只用本批（已裁规则下可用的用户事实/核验材料）
    prompt_existing = existing if (existing_usable and existing) else ""
    new_summary = _extend_summary(llm, prompt_existing, batch)
    if new_summary is None:
        return False  # llm 失败：不推进 summary_upto，这批旧消息下次仍会重试

    ancestors_known = not batch_unknown
    anc = list(batch_prov)
    if existing_usable and existing_prov is not None:
        anc.append(existing_prov)  # 只有实际喂入的可用旧摘要才作为祖先
    new_prov = qe.build_provenance((), ancestors=tuple(anc)) if ancestors_known else None
    new_prov_text = qe.serialize_provenance(new_prov) if new_prov is not None else None
    new_upto = max(0, (conv.message_count or 0) - RECENT_K)

    if hasattr(db, "query"):
        # 乐观并发：内容/游标与读取时快照逐字相符才提交（CAS），否则拒过时产物、不覆盖较新安全摘要。
        updated = (
            db.query(Conversation)
            .filter(
                Conversation.id == conv.id,
                func.coalesce(Conversation.summary_upto, 0) == expected_upto,
                func.coalesce(Conversation.summary, "") == expected_summary,
            )
            .update(
                {
                    "summary": new_summary,
                    "summary_upto": new_upto,
                    "summary_provenance": new_prov_text,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        if updated != 1:
            db.rollback()  # 过时快照（另一压缩抢先提交 / 期间更新）
            return False
        conv.summary = new_summary
        conv.summary_upto = new_upto
        conv.summary_provenance = new_prov_text
        return True

    # 兼容既有假 db 替身（无 query）：沿用直接赋值 + commit 的旧形状（真实会话走上面的 CAS）
    conv.summary = new_summary
    conv.summary_upto = new_upto
    conv.summary_provenance = new_prov_text
    db.commit()
    return True


def rewrite_query(llm, recent: list[Message], current: str) -> str:
    """有历史时把含指代/省略的最新提问改写为独立检索句；无历史或失败则原样返回。"""
    cur = (current or "").strip()
    if not recent or not cur:
        return cur
    hist = "\n".join(_msg_text(m) for m in recent[-4:])
    sys = (
        "根据对话历史，把用户最新这句可能含指代或省略的提问，改写为一句独立、完整、"
        "适合检索法律条文的提问。只输出改写后的提问本身，不要解释、不要加引号。"
    )
    user = f"历史：\n{hist}\n\n最新提问：{cur}"
    try:
        resp = llm.invoke([SystemMessage(content=sys), HumanMessage(content=user)])
        rw = (resp.content or "").strip().strip('"').strip()
        return rw or cur
    except Exception:
        return cur
