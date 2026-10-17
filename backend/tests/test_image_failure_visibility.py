"""W07 特征化判据（票面 `:365`）——**2026-10-17 由 W07-IMPL 逐条改写**：识图失败与"图里没内容"曾同形。

改前：`multimodal.describe_image` 用 `except Exception: return ""` 把所有失败收敛成空串，
而下游 `request_bootstrap.bootstrap_request` 只看字符串是否为空 ⇒ 三种完全不同的事——
① 模型调用炸了（鉴权/额度/端点/形状）、② 模型正常返回但内容为空、③ 用户传的图本来就没字——
**在契约里长成一个样**，且 `RequestBootstrap` 的字段面里没有任何失败位。

C04 裁的是**形状甲（失败可见）**，所以本文件按仓规「**改写旧尺，不许删**」逐条转义：
改前的字节在 head `15e6820`，改前/改后读数在
`reports/execution-runs/fazhi-full-closeout-20261016-*/evidence/W07-IMPL-*-{before,after}.log`，
逐条「原钉 ⇒ 现钉 ⇒ 理由」记在派发票 §6 的回执。新契约的行为判据在 `test_image_failure_impl.py`；
本文件留的是这四把尺的**新闭集/新形态**版本：

- 第 1 条：四类异常现在**各自原样向上抛**（不再被收敛成同一个空串）；
- 第 2 条：失败与空内容现在是**两个不同的返回形态**（抛 vs 返回空串），不再是逐字同形；
- 第 3 条：两个模态的失败纪律由"相反"改成"一致"（都向上抛）；
- 第 4 条：空描述仍继续整轮，但契约上有了失败位；那只 20 字段的**闭集**改写成 21 字段的新闭集
  ——它是「没有失败位」这一现量的唯一测量器具，只许改写不许删。

⚠️ 本文件不调任何真端点、不加载真权重、不写真实库：异常与空内容都用记账假对象注入，
DB 是 in-memory SQLite。票面 `:364` 要的"正常合成条款图端到端可核"属外发腿，本轮 **未测**（无凭据），
不许把这里的"失败形状"读成"视觉能力已验证"。
"""

import dataclasses
import os
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import multimodal  # noqa: E402
from models import Base, User  # noqa: E402
from request_bootstrap import BootstrapDependencies, RequestBootstrap, bootstrap_request  # noqa: E402

_DESCRIPTION = "图片里是一份两页合同，含甲方乙方与违约金条款。"


class _Llm:
    """只回固定内容的假模型。"""

    def __init__(self, content):
        self._content = content

    def invoke(self, messages, **kwargs):
        return SimpleNamespace(content=self._content)


class _BoomLlm:
    """只抛指定异常的假模型（改前 `describe_image` 吞的是 `Exception`，所以异常类型要多种；
    甲之后这些类型必须**各自原样回来**，所以类型清单一个字没减）。"""

    def __init__(self, exc: BaseException):
        self._exc = exc
        self.calls = 0

    def invoke(self, messages, **kwargs):
        self.calls += 1
        raise self._exc


def test_every_exception_kind_propagates_out_of_describe_image():
    """①（改写）鉴权、额度、形状、本地异常四类失败各自原样向上抛。

    原钉「四类异常都被收敛成 `""`」⇒ 现钉「四类异常都穿透 `describe_image`」，
    理由：C04＝甲——「失败与空内容同形」是这一票要拆掉的东西，同一条腿反过来钉才算落地。
    `llm.calls == 1` 这条**没删**：没调到模型就"失败"，判据会在根本没发请求上空转。
    """
    for exc in (
        RuntimeError("401 Unauthorized"),
        ValueError("400 InvalidParameter: model not support"),
        TimeoutError("connect timeout"),
        ZeroDivisionError("无任何关键词的本地异常"),
    ):
        llm = _BoomLlm(exc)
        with pytest.raises(type(exc)):
            multimodal.describe_image(llm, "data:image/png;base64,AAAA")
        assert llm.calls == 1, "没调到模型就抛错 ⇒ 这条判据会在『根本没发请求』上空转"


def test_failure_and_empty_content_are_two_different_returns():
    """②（改写）失败＝抛，空内容＝返回空串：两种事不再有同一个读数。

    原钉「failed == empty_content == whitespace_only == none_content == ""」⇒
    现钉「failed 走异常出口，其余三个仍是空串」，理由：本条是"没有归因通道"的直接证明，
    甲之后它必须改成"归因通道存在"的直接证明——四个输入一个都不减，减了就只剩三条腿在证同一件事。
    正对照（真描述原样回来）**没删**：没有它，这四条会因为"函数恒抛"而全部假绿。
    """
    with pytest.raises(RuntimeError):
        multimodal.describe_image(_BoomLlm(RuntimeError("boom")), "data:image/png;base64,AAAA")
    empty_content = multimodal.describe_image(_Llm(""), "data:image/png;base64,AAAA")
    whitespace_only = multimodal.describe_image(_Llm("   "), "data:image/png;base64,AAAA")
    none_content = multimodal.describe_image(_Llm(None), "data:image/png;base64,AAAA")
    assert empty_content == whitespace_only == none_content == ""

    # 正对照：真描述必须原样回来（否则上面四条会因为"函数恒返回空串"而全部假绿）
    assert multimodal.describe_image(_Llm(_DESCRIPTION), "data:image/png;base64,AAAA") == _DESCRIPTION


def test_both_modalities_now_share_the_raise_discipline():
    """③（改写）语音与视觉的失败纪律由"相反"对齐成"一致：都向上抛"。

    原钉「同一发异常在语音侧不被吞、在视觉侧只得到空串」（对照腿存在的意义是**暴露差异**）⇒
    现钉「同一发异常在两侧都向上抛」，理由：卡 §1 ⑥ 说 C04 要一次性定调、两个模态不能各选一个;
    甲选了"可见"，所以视觉侧对齐到语音侧那条既有纪律，而不是把语音侧拉回降级。
    对照腿**保留**在同一只用例里，只是断言从"不同形"改成"同形"。
    """
    with pytest.raises(RuntimeError):
        multimodal.transcribe_audio(_BoomLlm(RuntimeError("429 rate limited")), "aGVsbG8=", "wav")
    # 对照腿保留在同一只用例里：以前它断言的是"视觉只得到空串"（差异），现在断言"视觉也抛"（一致）
    with pytest.raises(RuntimeError):
        multimodal.describe_image(_BoomLlm(RuntimeError("429 rate limited")), "data:image/png;base64,AAAA")


@pytest.fixture
def store():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = sessions()
    user = User(username="w07", password_hash="x")
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()
    result = SimpleNamespace(sessions=sessions, user_id=user_id)
    return result


def _deps(store, **overrides):
    values = dict(
        session_factory=store.sessions,
        load_context=lambda db, conv: ("", []),
        validate_image=lambda image: image,
        persist_image=lambda image: ("media/image.png", "media/thumb.jpg"),
        cleanup_persisted_image=lambda image_rel, thumb_rel: None,
        describe_image=lambda image, text: _DESCRIPTION,
        classify_intent=lambda query: "legal_query",
        is_exam_question=lambda query: False,
        has_exam_options=lambda query: False,
        is_contract_review=lambda query: False,
        contract_trigger_reason=lambda query: None,
        feature_multi_analyze=False,
        contract_conversations=set(),
        contract_reviewed_conversations=set(),
        is_contract_exit=lambda query: False,
    )
    values.update(overrides)
    return BootstrapDependencies(**values)


def test_empty_description_continues_the_turn_but_leaves_a_failure_bit(store):
    """④（改写）空描述仍继续整轮，但契约上现在**有一位**能表达"这一轮的图没被读出来"。

    原钉「`raw_query` 退化成纯文本，且 `RequestBootstrap` 的 20 字段闭集里没有任何失败位」⇒
    现钉「退化仍是纯文本（甲不改变『图里没字就按文字答』这条既有行为），但 `image_failure`
    亮成 `content_empty`」，理由：卡 §3 甲的附带项明写「`RequestBootstrap` 需要一个失败位
    （§1 ⑦ 穷举证明现在没有）」，而那只闭集是「没有 X」的唯一测量器具——**改写成新闭集，不删**。
    「调用失败」那一支不在这里：它不产出 bootstrap（HTTP/SSE 层 502 中止），
    判据在 `test_image_failure_impl.py::test_injected_exception_lights_key_a_only`。
    """
    got = bootstrap_request(
        store.user_id,
        None,
        "这份合同有效吗",
        "data:image/png;base64,AAAA",
        False,
        _deps=_deps(store, describe_image=lambda image, text: ""),
    )
    assert got.image_description == ""
    assert got.raw_query == "这份合同有效吗"  # 图没字时题干仍是纯文本（这条行为没改）
    assert got.image is not None, "pre 里还带着图 ⇒ 下游仍按「有图」走，只是描述是空的"
    # 原钉「契约上没有任何一位」⇒ 现钉那一位在这一轮亮着具体归因码，不是泛泛一个 bool
    assert got.image_failure == "content_empty"

    # 正对照：描述正常回来时 raw_query 会带上它——所以上面那条退化是真退化，不是恒等式
    ok = bootstrap_request(
        store.user_id, None, "这份合同有效吗", "data:image/png;base64,AAAA", False, _deps=_deps(store)
    )
    assert _DESCRIPTION in ok.raw_query
    assert ok.image_failure is None

    # 契约面上的失败位**只有一个**，字段面仍是**闭集**而不是关键词筛（独立复核打出来的）：
    # 加一个 `no_image_reason: str` 就造出了第二份表达，而 "fail|error|degraded|warn"
    # 这种词表拦不住换个名字的字段——"换个名字就当已经修好"正是票面 :346 禁的形状。
    # 相对改前那 20 个字段，本轮只多 `image_failure` 一个（改前闭集见 head 15e6820 的同名用例）。
    fields = {f.name for f in dataclasses.fields(RequestBootstrap)}
    assert fields == {
        "conv_id",
        "summary",
        "recent",
        "recent_messages",
        "image",
        "user_text",
        "image_rel",
        "thumb_rel",
        "image_description",
        "raw_query",
        "supplement_text",
        "intent",
        "is_exam",
        "has_options",
        "contract_mode",
        "contract_text",
        "client_truncated",
        "case_domain",
        "law_as_of",
        "intent_confirm",
        "image_failure",
    }, sorted(fields)
