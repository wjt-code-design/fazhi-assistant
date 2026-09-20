"""/api/chat SSE 端点级测试夹具（S5/1b，2026-09-20）。

存在的理由不是"多一层封装"，而是两件事在单元层证不了：

1. `_light_buffered(pre, messages, _fast_path_law_as_of(body))` 那一行传进去的 `law_as_of` **实参值**
   —— 只在该行被真实执行时才可观测，单元层"断言函数收到了参数"只钉传没传、不钉值（票 G §2-2 的教训）。
   ⚠️ 本模块**不写行号**（ADR-018/R4：只用符号锚点，行号在本仓已漂过四次）。
2. `stream()` 里那道"命中不进缓存"闸（认这个形状：
   `if cache_key and res.verdict == "pass" and not res.law_version_hit:`）—— 它在 `stream()` 里，
   不在 `_light_buffered` 里；且实测四个变异只跑定向文件时它**存活**（票 G F5）。

历史：`test_flagship_quality.py` 早已写出这套 in-memory + 替身 的端点夹具，但只服务旗舰流式那条路。
本模块把它抽成工厂并补 `light_buffered` 路线（登记表里那条叫 **E7**，别和注记帧 E6 混）。
抽提**不改变** `route="flagship_stream"` 的既有桩点集合——判据是抽前后该文件用例逐字同结果。
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

from langchain_core.documents import Document
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 旗舰流式的两块增量（保持与抽出前 _FakeChain 一字相同）
FLAGSHIP_PARTS = ("根据《劳动合同法》第十九条，", "试用期最长六个月。")
# E7（缓冲轻量整答）默认答案：民事时效结论 + 分水岭后事实（配合 date.today() 不跨两侧 ⇒ 门不命中）
LIGHT_ANSWER = "本案诉讼时效为三年，自 2022 年 6 月 1 日起算。"
FACT_2022 = "我 2022年6月1日 借给朋友一笔钱，约定一年内还。"
# E5（合同报告流式增量）默认增量：引用《劳动合同法》第十九条（与 _one_hit_retrieval 命中同一条，
# 便于用例把 `citation_verify` 替身做成"在库/不在库"两态而不必改答案文本）。
CONTRACT_PARTS = ("【风险评估】第一条 试用期约定超过法定上限，", "依据《劳动合同法》第十九条，建议不超过六个月。")
CONTRACT_ANSWER = "".join(CONTRACT_PARTS)


class _FakeChain:
    """旗舰流式：`make_chain(llm).astream(messages)` 逐块产出。"""

    def __init__(self, parts: tuple[str, ...] = FLAGSHIP_PARTS) -> None:
        self._parts = parts

    async def astream(self, messages):  # noqa: ARG002 - 形参由真实链决定
        for p in self._parts:
            yield p


class _FakeResp:
    """langchain 响应的最小形状：`.content`（`_token_charge` 走 `getattr` 容错，无需 usage）。"""

    def __init__(self, content: str) -> None:
        self.content = content


class _FakeInvokableLLM:
    """`llm.invoke(messages)` 一次拿整答的模型替身。

    两个消费者：`_light_buffered_locked`（轻量缓冲整答）与 `main._invoke_llm`（旗舰流式空答后的
    非流式兜底，票 C §5-3 点名的**第二个答案来源**）。形状相同 ⇒ 不另立一份。
    """

    def __init__(self, text: str) -> None:
        self._text = text

    def invoke(self, messages):  # noqa: ARG002 - 形参由真实 llm 决定
        return _FakeResp(self._text)


def _one_hit_retrieval(q: str, k: int = 4) -> list[Document]:  # noqa: ARG002
    return [
        Document(page_content="第十九条 试用期…", metadata={"source": "劳动合同法", "article": "第十九条"}),
    ]


def _contract_data(text: str) -> dict:  # noqa: ARG001 - 形参由 `build_contract_data` 决定
    """`domain_rules.build_contract_data` 的替身（票 H 新增 route 用）。

    形状照 `request_bootstrap.prepare_fast_path` 的消费点给全：`docs`（供 `sources`/`_hit_arts`）、
    `blocks`（供 `_contract_messages` 组装证据段）、`level`（供步骤帧）。
    `need_clarify=False` ⇒ 走**报告生成**那条，不是零 LLM 的信息确认反问（那是 E4）。
    """
    return {
        "docs": _one_hit_retrieval(""),
        "blocks": [
            {
                "n": 1,
                "label": "第一条",
                "articles": ["第十九条"],
                "tags": ["试用期"],
                "text": "试用期为十二个月。",
            }
        ],
        "level": "中",
        "basis": "harness",
        "need_clarify": False,
    }


@contextlib.contextmanager
def sse_client(
    monkeypatch,
    *,
    route: str = "flagship_stream",
    flagship_parts: tuple[str, ...] = FLAGSHIP_PARTS,
    light_text: str = LIGHT_ANSWER,
    cache_put: Any = None,
    fallback_text: str | None = None,
) -> Iterator[Any]:
    """起一个隔离到内存库的 TestClient，把请求钉到指定出口。

    route="flagship_stream" ⇒ 桩点集合与抽提前的 `client` fixture 一字不差（`has_role` 恒假 ⇒ 走旗舰流式）。
    route="light_buffered" ⇒ 额外把 tier/准入/`has_role`/模型/自检/反问/扣减全替身化，
    使 `use_light` 为真、真实执行登记表 **E7** 那条出口整段（含"命中不进缓存"闸，
    认形状 `if cache_key and res.verdict == "pass" and not res.law_version_hit:`）。
    route="contract_review"（票 H 新增）⇒ 把 `is_contract_review`/`build_contract_data`/扣减/模型名
    替身化，使 `pre["contract_data"]` 在场且 `need_clarify` 为假，真实执行登记表 **E5/E6** 那一整段
    （含写缓存闸与引用告警注记帧）。增量文本请传 `flagship_parts=CONTRACT_PARTS`。

    `fallback_text`（票 C/S6 新增）：把旗舰那一档的模型换成**可 `invoke`** 的替身，于是
    `flagship_parts=()`（流式返回空）时 `main._invoke_llm` 真能拿到一份整答 ⇒ 登记表 **E9**
    那条「第二个答案来源」第一次可在端点级被打到。此前 `flag_llm` 是裸 `object()`，
    `_invoke_llm` 必抛 AttributeError 被 `except` 吞掉 ⇒ E9 在测试里恒等于"兜底也失败"，
    任何只接在兜底分支上的代码都测不到（票 C §2c 点名的形状）。
    """
    import answer_cache
    import complexity
    import database
    import main
    import quality
    from models import Base

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "SessionLocal", sm)
    monkeypatch.setattr(main, "SessionLocal", sm)
    # 强制走路由器分支，隔离本机注册模型与配额状态。
    monkeypatch.setattr(main.settings, "feature_router", True)
    monkeypatch.setattr(main, "_safe_pick", lambda modality, tier, **kw: ("flag-test", object(), False))
    monkeypatch.setattr(main, "make_chain", lambda llm: _FakeChain(flagship_parts))
    monkeypatch.setattr(main, "retrieve", _one_hit_retrieval)
    monkeypatch.setattr(main, "classify_intent", lambda t: "legal_query")
    monkeypatch.setattr(main.ks, "search_qa", lambda q: None)
    # 引用校验放行（假答案引用的条文视为在库）
    monkeypatch.setattr(main, "citation_verify", lambda a, in_kb=None: [])
    monkeypatch.setattr(main.registry, "has_role", lambda modality, tier: False)

    if route == "light_buffered":
        # use_light 的四个合取项逐个造真：tier=light + 准入通过 + modality=text + 有 light 角色。
        monkeypatch.setattr(complexity, "assess", lambda *a, **kw: ("text", "light"))
        monkeypatch.setattr(complexity, "admit_light", lambda *a, **kw: True)
        monkeypatch.setattr(main.registry, "has_role", lambda modality, tier: True)
        monkeypatch.setattr(
            main, "_safe_pick", lambda modality, tier, **kw: ("light-test", _FakeInvokableLLM(light_text), False)
        )
        monkeypatch.setattr(quality, "self_check", lambda answer, context_present: quality.Verdict(True))
        monkeypatch.setattr(main.clarify, "decide", lambda *a, **kw: "direct")
        # 配额扣减与模型名查询是真实 registry 状态，与本题无关 ⇒ 桩掉，保持测试封闭。
        monkeypatch.setattr(main.registry, "deduct", lambda key, tokens: None)
        monkeypatch.setattr(main.registry, "model_of", lambda key: "test-light")
    elif route == "contract_review":
        # 票 H 新增：让请求真走到 `pre["contract_data"]` ⇒ 分支0.3（合同报告）整段执行。
        # 两个替身都按 main 模块全局打桩——`_bootstrap_only` / `_prepare_fast_path_only` 是在
        # **调用时**从 main 取这两个名字（不是定义时闭包），所以打桩能生效。
        monkeypatch.setattr(main.settings, "feature_multi_analyze", True)
        monkeypatch.setattr(main, "is_contract_review", lambda t: True)
        monkeypatch.setattr(main, "build_contract_data", _contract_data)
        # ⚠️ **模块级会话集必须隔离**（票 H 实测踩到，症状极具误导性）：`request_bootstrap` 会把
        # 本轮的 `conv_id` 写进 `main._contract_convs`，而每个用例的内存库都从 id=1 重新发号 ⇒
        # 不隔离的话，本 route 跑完后再跑其他文件（实测：`test_stream_exit_law_version_gate.py`
        # 与 `test_fast_path_law_version_gate.py`），它们的 conv_id 也会是 1，于是被判成
        # `active_contract` ⇒ 请求被路由到**合同澄清**（E4）而不是旗舰流式（E8）⇒ 那两个文件
        # 十几条"门没被调用"的红。`monkeypatch` 退出时自动还原，不需要手工清理。
        monkeypatch.setattr(main, "_contract_convs", set())
        monkeypatch.setattr(main, "_contract_reviewed_convs", set())
        # 配额扣减与模型名查询是真实 registry 状态，与本题无关 ⇒ 桩掉（同 route="light_buffered" 的理由）。
        monkeypatch.setattr(main.registry, "deduct", lambda key, tokens: None)
        monkeypatch.setattr(main.registry, "model_of", lambda key: "test-flag")
        # ⚠️ 本 route 的增量文本请传 `flagship_parts=CONTRACT_PARTS`：合同分支与旗舰分支共用
        # 同一个 `make_chain` 桩点（都是 `_FakeChain`），不另开第二条链工厂。
    elif route != "flagship_stream":
        raise ValueError(f"unknown route: {route}")

    if fallback_text is not None:
        if route != "flagship_stream":
            # E9 只存在于旗舰流式分支。允许在 light_buffered 下传这个参数，就会造出一条
            # "参数传了但没人消费"的假断言（票 G §2-2 的同族形状）⇒ 直接炸，不给静默。
            raise ValueError("fallback_text 只对 route='flagship_stream' 有意义（E9 在那条分支上）")
        monkeypatch.setattr(
            main, "_safe_pick", lambda modality, tier, **kw: ("flag-test", _FakeInvokableLLM(fallback_text), False)
        )

    if cache_put is not None:
        monkeypatch.setattr(answer_cache, "put", cache_put)

    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        yield c


def login(client, username: str = "user1") -> str:
    client.post("/api/auth/register", json={"username": username, "password": "password123"})
    return client.post("/api/auth/login", json={"username": username, "password": "password123"}).json()["token"]


def chat_frames(client, token: str, content: str, extra: dict | None = None) -> list[str]:
    """发一次 /api/chat，返回**原始帧序列**（顺序即语义）。

    用途：1a 那类"改在调用点"的修复，其零变化证据只能是逐帧字节比对
    （`capture_light_baseline.py` 直接调 `_light_buffered`，不经 `stream()` 里那行调用点 ⇒ 对它不可见）。
    """
    payload = {"content": content}
    payload.update(extra or {})
    with client.stream("POST", "/api/chat", json=payload, headers={"Authorization": f"Bearer {token}"}) as r:
        assert r.status_code == 200, f"HTTP {r.status_code}"
        return [f for f in r.iter_lines()]
