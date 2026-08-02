"""memory 多轮上下文测试：纯逻辑 + mock llm/db（不碰真实 DB/LLM）。

覆盖：角色格式化 / 字符计数 / 双阈值压缩触发 / 查询改写回落 / 增量压缩。
"""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import memory as mem  # noqa: E402


class FakeMsg:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class FakeConv:
    def __init__(self, message_count=0, summary="", summary_upto=0):
        self.message_count = message_count
        self.summary = summary
        self.summary_upto = summary_upto


class FakeLlm:
    def __init__(self, content=None, exc=None):
        self.content = content
        self.exc = exc

    def invoke(self, msgs):
        if self.exc:
            raise self.exc
        return SimpleNamespace(content=self.content)


# ---------------- _msg_text：角色格式化 ----------------
def test_msg_text_roles():
    assert mem._msg_text(FakeMsg("user", "你好")) == "用户：你好"
    assert mem._msg_text(FakeMsg("assistant", "根据民法典")) == "助手：根据民法典"
    assert mem._msg_text(FakeMsg("system", "x")) == "系统：x"
    assert mem._msg_text(FakeMsg("user", None)) == "用户："


# ---------------- char_count：字符计数 ----------------
def test_char_count_empty():
    assert mem.char_count("", []) == 0
    assert mem.char_count(None, []) == 0


def test_char_count_sums_summary_and_recent():
    recent = [FakeMsg("user", "问题一二"), FakeMsg("assistant", "回答")]
    assert mem.char_count("摘要", recent) == len("摘要问题一二回答")


# ---------------- needs_compress：双阈值触发 ----------------
def test_needs_compress_below_threshold():
    assert not mem.needs_compress(FakeConv(message_count=5), [])


def test_needs_compress_by_turn_count():
    assert mem.needs_compress(FakeConv(message_count=13), [])


def test_needs_compress_by_char_count():
    conv = FakeConv(message_count=2, summary="x")
    recent = [FakeMsg("user", "长" * mem.CHAR_THRESHOLD)]  # 单条即超限
    assert mem.needs_compress(conv, recent)


def test_needs_compress_summary_only():
    conv = FakeConv(message_count=0, summary="长" * (mem.CHAR_THRESHOLD + 1))
    assert mem.needs_compress(conv, [])


# ---------------- rewrite_query：查询改写（含回落） ----------------
def test_rewrite_query_no_history_returns_same():
    assert mem.rewrite_query(FakeLlm("不该被调用"), [], "试用期最长多久") == "试用期最长多久"


def test_rewrite_query_empty_returns_same():
    assert mem.rewrite_query(FakeLlm("x"), [FakeMsg("user", "h")], "   ") == ""


def test_rewrite_query_success():
    llm = FakeLlm("公司违法解除，赔偿金如何计算？")
    recent = [FakeMsg("user", "公司把我开了"), FakeMsg("assistant", "看劳动合同法")]
    assert mem.rewrite_query(llm, recent, "赔偿金怎么算") == "公司违法解除，赔偿金如何计算？"


def test_rewrite_query_strips_quotes():
    llm = FakeLlm('"去除外层引号"')
    assert mem.rewrite_query(llm, [FakeMsg("user", "h")], "q") == "去除外层引号"


def test_rewrite_query_falls_back_on_llm_error():
    llm = FakeLlm(exc=RuntimeError("网络"))
    recent = [FakeMsg("user", "h")]
    assert mem.rewrite_query(llm, recent, "原问题") == "原问题"


# ---------------- compress：增量压缩 ----------------
def test_compress_no_gap_returns_false(monkeypatch):
    monkeypatch.setattr(mem, "_gap_messages", lambda db, conv: [])
    conv = FakeConv(message_count=6)
    assert mem.compress(None, conv, FakeLlm()) is False


def test_compress_updates_summary_and_upto(monkeypatch):
    gap = [FakeMsg("user", "问题"), FakeMsg("assistant", "回答")]
    monkeypatch.setattr(mem, "_gap_messages", lambda db, conv: gap)
    llm = FakeLlm("合并后的摘要内容")

    class FakeDb:
        committed = False

        def commit(self):
            self.committed = True

    db = FakeDb()
    conv = FakeConv(message_count=20, summary="旧摘要")
    assert mem.compress(db, conv, llm) is True
    assert conv.summary == "合并后的摘要内容"
    assert conv.summary_upto == 20 - mem.RECENT_K
    assert db.committed is True


def test_compress_llm_error_does_not_advance_window(monkeypatch):
    """llm 失败必须返回 False 且不推进 summary_upto——否则旧消息被标记已压缩、摘要永久缺失。"""
    monkeypatch.setattr(mem, "_gap_messages", lambda db, conv: [FakeMsg("user", "x")])
    conv = FakeConv(message_count=20, summary="旧摘要")
    assert mem.compress(None, conv, FakeLlm(exc=RuntimeError())) is False
    assert conv.summary == "旧摘要"
    assert conv.summary_upto == 0
