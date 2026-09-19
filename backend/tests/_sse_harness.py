"""/api/chat SSE 端点级测试夹具（S5/1b，2026-09-20）。

存在的理由不是"多一层封装"，而是两件事在单元层证不了：

1. `main.py:1914` 传给 `_light_buffered` 的 `law_as_of` 实参值 —— 只在该行被真实执行时才可观测，
   单元层"断言函数收到了参数"只钉传没传、不钉值（票 G §2-2 的教训）。
2. `main.py:1921` 那道"命中不进缓存"闸 —— 它在 `stream()` 里，不在 `_light_buffered` 里；
   且实测四个变异只跑定向文件时它**存活**（票 G F5）。

历史：`test_flagship_quality.py` 早已写出这套 in-memory + 替身 的端点夹具，但只服务旗舰流式那条路。
本模块把它抽成工厂并补 `light_buffered` 路线（E6），使 SSE 出口第一次可被两侧复用。
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
# E6 默认答案：民事时效结论 + 分水岭后事实（配合 date.today() 不跨两侧 ⇒ 门不命中）
LIGHT_ANSWER = "本案诉讼时效为三年，自 2022 年 6 月 1 日起算。"
FACT_2022 = "我 2022年6月1日 借给朋友一笔钱，约定一年内还。"


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


class _FakeLightLLM:
    """轻量缓冲路径的模型：`_light_buffered_locked` 用 `llm.invoke(messages)` 一次拿整答。"""

    def __init__(self, text: str) -> None:
        self._text = text

    def invoke(self, messages):  # noqa: ARG002 - 形参由真实 llm 决定
        return _FakeResp(self._text)


def _one_hit_retrieval(q: str, k: int = 4) -> list[Document]:  # noqa: ARG002
    return [
        Document(page_content="第十九条 试用期…", metadata={"source": "劳动合同法", "article": "第十九条"}),
    ]


@contextlib.contextmanager
def sse_client(
    monkeypatch,
    *,
    route: str = "flagship_stream",
    flagship_parts: tuple[str, ...] = FLAGSHIP_PARTS,
    light_text: str = LIGHT_ANSWER,
    cache_put: Any = None,
) -> Iterator[Any]:
    """起一个隔离到内存库的 TestClient，把请求钉到指定出口。

    route="flagship_stream" ⇒ 桩点集合与抽提前的 `client` fixture 一字不差（`has_role` 恒假 ⇒ 走旗舰流式）。
    route="light_buffered" ⇒ 额外把 tier/准入/`has_role`/模型/自检/反问/扣减全替身化，
    使 `use_light` 为真、真实执行 `main.py:1913-1924` 那段（含 `:1921` 闸）。
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
            main, "_safe_pick", lambda modality, tier, **kw: ("light-test", _FakeLightLLM(light_text), False)
        )
        monkeypatch.setattr(quality, "self_check", lambda answer, context_present: quality.Verdict(True))
        monkeypatch.setattr(main.clarify, "decide", lambda *a, **kw: "direct")
        # 配额扣减与模型名查询是真实 registry 状态，与本题无关 ⇒ 桩掉，保持测试封闭。
        monkeypatch.setattr(main.registry, "deduct", lambda key, tokens: None)
        monkeypatch.setattr(main.registry, "model_of", lambda key: "test-light")
    elif route != "flagship_stream":
        raise ValueError(f"unknown route: {route}")

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
    （`capture_light_baseline.py` 直接调 `_light_buffered`，不经 `:1914` ⇒ 对它不可见）。
    """
    payload = {"content": content}
    payload.update(extra or {})
    with client.stream("POST", "/api/chat", json=payload, headers={"Authorization": f"Bearer {token}"}) as r:
        assert r.status_code == 200, f"HTTP {r.status_code}"
        return [f for f in r.iter_lines()]
