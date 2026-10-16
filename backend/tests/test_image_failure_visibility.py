"""W07 特征化（零外发半，票面 `:365`）：**识图失败与"图里没内容"在产品里是同一个返回值**。

`multimodal.describe_image` 用 `except Exception: return ""` 把所有失败收敛成空串
（multimodal.py:149-151），而下游 `request_bootstrap.bootstrap_request` 只看字符串是否为空
（request_bootstrap.py:389-396）⇒ 三种完全不同的事——① 模型调用炸了（鉴权/额度/端点/形状）、
② 模型正常返回但内容为空、③ 用户传的图本来就没字——**在契约里长成一个样**。
本轮 C04（失败可见 vs 明确降级）未裁，所以这里**只钉现状不选边**，但把三件事分开量出来：

- 第 1 条：两类不同异常都被吞成空串（吞的是 `Exception`，不是某一种错误）；
- 第 2 条：空内容与失败**输出逐字相同** ⇒ 上游无法区分（这条是"没有归因通道"的直接证明，
  不是我对注释的解读）；
- 第 3 条：语音侧**不吞**（multimodal.py:126-130 没有 try）⇒ 同一份"失败面"在两个模态上纪律相反，
  这正是 C04 要一次性定调的东西（选哪个都行，但两个模态不能各选一个）；
- 第 4 条：空描述继续走完整个请求——`raw_query` 退化成纯文本、`RequestBootstrap` 的字段集里
  **没有任何一位**能表达"这一轮的图没被读出来"（按 dataclass 字段穷举，见该条）。

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
    """只抛指定异常的假模型（`describe_image` 吞的是 `Exception`，所以异常类型要多种）。"""

    def __init__(self, exc: BaseException):
        self._exc = exc
        self.calls = 0

    def invoke(self, messages, **kwargs):
        self.calls += 1
        raise self._exc


def test_every_exception_kind_becomes_an_empty_string():
    """① 鉴权、额度、形状、本地异常四类失败在 `describe_image` 处被收敛成同一个空串。"""
    for exc in (
        RuntimeError("401 Unauthorized"),
        ValueError("400 InvalidParameter: model not support"),
        TimeoutError("connect timeout"),
        ZeroDivisionError("无任何关键词的本地异常"),
    ):
        llm = _BoomLlm(exc)
        assert multimodal.describe_image(llm, "data:image/png;base64,AAAA") == ""
        assert llm.calls == 1, "没调到模型就返回空串 ⇒ 这条判据会在『根本没发请求』上空转"


def test_failure_and_empty_response_are_byte_identical():
    """② 失败与"模型说没内容"输出逐字相同 ⇒ 契约里没有归因通道（这是"没有 X"的直接证明）。"""
    failed = multimodal.describe_image(_BoomLlm(RuntimeError("boom")), "data:image/png;base64,AAAA")
    empty_content = multimodal.describe_image(_Llm(""), "data:image/png;base64,AAAA")
    whitespace_only = multimodal.describe_image(_Llm("   "), "data:image/png;base64,AAAA")
    none_content = multimodal.describe_image(_Llm(None), "data:image/png;base64,AAAA")
    assert failed == empty_content == whitespace_only == none_content == ""

    # 正对照：真描述必须原样回来（否则上面四条会因为"函数恒返回空串"而全部假绿）
    assert multimodal.describe_image(_Llm(_DESCRIPTION), "data:image/png;base64,AAAA") == _DESCRIPTION


def test_voice_side_raises_instead_of_degrading():
    """③ 同一类异常在语音侧**不被吞**：两个模态的失败纪律现在是相反的。"""
    with pytest.raises(RuntimeError):
        multimodal.transcribe_audio(_BoomLlm(RuntimeError("429 rate limited")), "aGVsbG8=", "wav")
    # 而视觉侧同样这一发异常只得到空串（对照腿放在同一用例里，换班的人一眼能看见差异）
    assert multimodal.describe_image(_BoomLlm(RuntimeError("429 rate limited")), "data:image/png;base64,AAAA") == ""


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


def test_empty_description_continues_the_turn_as_if_the_image_were_read(store):
    """④ 空描述不拦任何东西：题干退化成纯文本，而 `RequestBootstrap` 里没有一个字段能表达"图没读出来"。"""
    got = bootstrap_request(
        store.user_id,
        None,
        "这份合同有效吗",
        "data:image/png;base64,AAAA",
        False,
        _deps=_deps(store, describe_image=lambda image, text: ""),
    )
    assert got.image_description == ""
    assert got.raw_query == "这份合同有效吗"  # 图被静默丢掉，题干一个字没提它
    assert got.image is not None, "pre 里还带着图 ⇒ 下游仍按「有图」走，只是描述是空的"

    # 正对照：描述正常回来时 raw_query 会带上它——所以上面那条退化是真退化，不是恒等式
    ok = bootstrap_request(
        store.user_id, None, "这份合同有效吗", "data:image/png;base64,AAAA", False, _deps=_deps(store)
    )
    assert _DESCRIPTION in ok.raw_query

    # 契约面上没有失败位：按 dataclass 字段**穷举**（"没有 X"的断言不许靠肉眼扫）
    # **闭集**而不是关键词筛（独立复核打出来的）：加一个 `no_image_reason: str` 就造出了失败位，
    # 而 "fail|error|degraded|warn" 这种词表拦不住换个名字的字段——"换个名字就当已经修好"
    # 正是票面 :346 禁的形状。
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
    }, sorted(fields)
