"""AUTH-C：用户级端点的归属核验探针（双用户实测，票面见
`docs/auth-review-followup-guidance-20260924.md` §4 AUTH-C）。

**这张票的性质**：静态审计（AST 扫 `main.py` 全部路由）的结论是"没有按 id 直取却不过滤归属的用户级
端点"。本文件把那条结论**钉成实测**——它的价值是防回归，不是预期查出漏洞。

票面第一版有两条会让探针跑空，这里按**真实契约**写（均已核过代码）：
1. "导出/下载端点""独立 messages 端点"**不存在**（全仓路由都挂在 `main.py`，无 `APIRouter`；
   唯一的 `FileResponse` 是 `get_media`；消息只嵌在 `GET /api/conversations/{id}` 的响应里）⇒ 不给
   不存在的东西造探针。
2. `/api/chat` 收到**别人的** `conversation_id` 时**不是 404**：`request_bootstrap` 那一支的行为是
   **静默新建一条自己的会话并返 200** ⇒ 探针断言的是 200 + 新建，把它写成 404 就是把正确行为判成缺陷。

非泄露性也在射程内：`get_conversation` / `get_media` 的拒绝形状是 404（与"不存在"同语义），
所以除了状态码，还断言**响应体里不含他人内容的任何片段**——状态码对了但把标题/正文漏出去，
仍然是同一条 BOLA。
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def client(monkeypatch):
    """内存 sqlite + 关掉限流/多模型路由；不碰宿主 `app.db`（与 test_phase3 同法）。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database
    import main
    import settings as _settings
    from models import Base

    monkeypatch.setattr(_settings.settings, "feature_router", False)
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "SessionLocal", sm)
    monkeypatch.setattr(main, "SessionLocal", sm)
    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        yield c


def _token(client, username: str) -> str:
    client.post("/api/auth/register", json={"username": username, "password": "password123"})
    return client.post("/api/auth/login", json={"username": username, "password": "password123"}).json()["token"]


@pytest.fixture
def two_users(client):
    """返回 (client, A 的 headers, B 的 headers)。B 是资源所有者，A 是攻击者。"""
    a = {"Authorization": f"Bearer {_token(client, 'authc_victim_a')}"}
    b = {"Authorization": f"Bearer {_token(client, 'authc_owner_b')}"}
    return client, a, b


def _new_conv(client, headers, title="借款纠纷咨询") -> int:
    """建一条会话并命名。⚠️ `PATCH /api/conversations/{id}` 的 `title` 是**查询参数**
    （FastAPI 对标量 `title: str` 的默认解释），发 JSON 体会得到 422——本票第一版就踩了这个。
    """
    conv_id = client.post("/api/conversations", headers=headers).json()["id"]
    assert client.patch(f"/api/conversations/{conv_id}", headers=headers, params={"title": title}).status_code == 200
    return conv_id


def test_foreign_conversation_read_is_404_and_leaks_no_title(two_users):
    """GET /api/conversations/{id}：他人会话 ⇒ 404，且响应体里不许出现他人标题。"""
    client, a, b = two_users
    secret = "工程款结算争议-勿泄露"
    conv_id = _new_conv(client, b, title=secret)

    mine = client.get(f"/api/conversations/{conv_id}", headers=b)
    assert mine.status_code == 200 and secret in mine.text, "夹具没建好：所有者读不到自己的会话"

    foreign = client.get(f"/api/conversations/{conv_id}", headers=a)
    assert foreign.status_code == 404
    assert secret not in foreign.text, "404 但把他人标题带出去了，仍是同一条 BOLA"


def test_foreign_conversation_rename_is_404_and_title_unchanged(two_users):
    """PATCH 改名：他人 ⇒ 404，且**标题必须没被改掉**（只断状态码会放过"先改后拒"）。"""
    client, a, b = two_users
    conv_id = _new_conv(client, b, title="原名-劳动合同解除")

    denied = client.patch(f"/api/conversations/{conv_id}", headers=a, params={"title": "被篡改的标题"})
    assert denied.status_code == 404

    after = client.get(f"/api/conversations/{conv_id}", headers=b)
    assert after.json()["title"] == "原名-劳动合同解除", "越界改写生效了"


def test_foreign_conversation_delete_is_404_and_row_survives(two_users):
    """DELETE：他人 ⇒ 404，且那一行**还在**（越界删除比越界读取更难回滚）。"""
    client, a, b = two_users
    conv_id = _new_conv(client, b)

    assert client.delete(f"/api/conversations/{conv_id}", headers=a).status_code == 404
    assert client.get(f"/api/conversations/{conv_id}", headers=b).status_code == 200, "别人的会话被删了"


def test_conversation_list_only_returns_own_rows(two_users):
    """列表口：A 的 `/api/conversations` 里不许出现 B 的会话 id（这是"按 id 猜"之外的另一条枚举面）。"""
    client, a, b = two_users
    foreign_id = _new_conv(client, b, title="海事赔偿请求时效")
    own_id = _new_conv(client, a, title="我自己的会话")

    listed = client.get("/api/conversations", headers=a).json()
    ids = {row["id"] for row in listed}
    assert own_id in ids and foreign_id not in ids


def test_feedback_on_foreign_conversation_is_404(two_users):
    """POST /api/feedback 带他人 conversation_id ⇒ 404（写侧本来就不再产生沉淀候选，这条只验归属）。"""
    client, a, b = two_users
    conv_id = _new_conv(client, b)
    body = {"question": "试用期最多多长", "answer": "不超过六个月", "rating": "up", "conversation_id": conv_id}

    assert client.post("/api/feedback", headers=a, json=body).status_code == 404


def test_media_of_foreign_conversation_is_404_before_touching_disk(two_users, monkeypatch):
    """GET /api/media：文件归属核验必须**先于**磁盘访问（代码顺序：owned 检查 → isfile）。

    路径形状是真契约的一部分：`MEDIA_DIR = backend/media`，而守卫用的 base 是
    `dirname(MEDIA_DIR)` = `backend/`，`models.py:56` 也写明 `image_ref` 是"相对 backend/ 的存盘
    相对路径"⇒ 引用值必须是 `media/xxx.png`。本票第一版按 `xxx.png` 写，得到的是 400（非法路径分支），
    归属那一段根本没跑到——一个"看起来在测归属"的假探针。

    探针做法：把"他人消息引用了某路径"写进库，但不建任何文件 ⇒ 若实现先查盘再查归属，
    这条会走到 not-a-file 分支仍返 404，**看不出差别**；所以让 `isfile` 在被调用时直接抛，
    从而证明归属分支真的先返回了（钉的是执行顺序，不只是状态码）。
    """
    from database import SessionLocal
    from models import Message

    client, a, b = two_users
    conv_id = _new_conv(client, b)
    db = SessionLocal()
    try:
        msg = Message(conversation_id=conv_id, role="user", content="带图提问", image_ref="media/authc-foreign.png")
        db.add(msg)
        db.commit()
    finally:
        db.close()

    import os

    boom = {"on": True}
    real_isfile = os.path.isfile

    def _guarded(path):
        if boom["on"]:
            raise AssertionError("归属核验未先于磁盘访问 ⇒ 越界请求会去碰他人文件")
        return real_isfile(path)

    monkeypatch.setattr(os.path, "isfile", _guarded)
    r = client.get("/api/media/media/authc-foreign.png", headers=a)
    assert r.status_code == 404, f"越界取他人图片被放行（实测 {r.status_code}）"

    # 路径穿越的形状：**400**（不是 404）——归一化后落在 media 目录外应当在归属核验之前直接拒。
    # 用 %2e%2e 而不是裸 `../`：httpx 会先把点段折叠掉，裸写等于没测穿越（本票第一版就白过了）。
    boom["on"] = False
    trav = client.get("/api/media/media/%2e%2e%2fsecret.txt", headers=a)
    assert trav.status_code == 400, f"穿越路径应显式判非法，实测 {trav.status_code}"


def test_chat_with_foreign_conversation_id_creates_own_conversation_not_404(two_users, monkeypatch):
    """`/api/chat` 的真实契约（票面第一版写错的那条）：带别人的 conv_id ⇒ **200 + 新建自己的会话**。

    静默改判归属在这里是**正确行为**（`request_bootstrap` 那一支：不符归属就当没给 conv_id），
    探针钉的是"别人的会话不许被追加消息"，不是"必须 404"。
    """
    client, a, b = two_users
    foreign_id = _new_conv(client, b, title="他人的历史会话")

    import main
    from database import SessionLocal
    from models import Conversation, Message

    class FakeChain:
        async def astream(self, messages):
            for piece in ["假", "答案"]:
                yield piece

    monkeypatch.setattr(main, "make_chain", lambda llm: FakeChain())
    monkeypatch.setattr(main, "_qa_direct_return", lambda pre, law_as_of=None: None)

    with client.stream(
        "POST", "/api/chat", json={"content": "试用期最长多久", "conversation_id": foreign_id}, headers=a
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    frames = []
    for line in body.splitlines():
        if line.startswith("data: ") and line[6:] != "[DONE]":
            try:
                frames.append(json.loads(line[6:]).get("content") or "")
            except ValueError:
                pass  # 非文本帧（引用/用量等）不参与断言
    assert "".join(frames) == "假答案"

    db = SessionLocal()
    try:
        assert db.query(Message).filter(Message.conversation_id == foreign_id).count() == 0, "越界写进了他人会话"
        convs = {c.id: c.user_id for c in db.query(Conversation).all()}
        assert len(convs) == 2, f"应为『他人原会话 + A 新建一条』，实测 {len(convs)} 条"
        assert convs[foreign_id] != convs[[i for i in convs if i != foreign_id][0]], "两条会话同主 ⇒ 新建支路没走"
    finally:
        db.close()
