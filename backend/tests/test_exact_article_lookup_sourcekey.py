"""票 I-6：`exact_article_lookup` 的源名容错（先红腿 + 控制腿）。

**为什么判据放在单元级**：本票改的是 `retrieval.exact_article_lookup` 这个纯查询函数，
调用方（`main` 的快车道取证、`agent` 的工具网关）签名与语义都没变 ⇒ 单元级就能把判据钉死。
**真实 KB 的读数另有取证**（不改代码就能复跑）：
`dispatch-output/hij-i-20260920/i6-lookup-before.json`（先红：`short=0`）×
`i6-lookup-after.json`（后绿：`short=1`），blast radius = 99 个源名里唯一带括注的 `宪法（1982年）`（138 行）。

⚠️ 目录里**没有** `i6-lookup-before.json`：第一版探针把输出名写死成 before，改后再跑覆盖了它
⇒ before 的原始证据只存在于 `01-i6-lookup-before.stdout.txt`。已把探针改成必须传标签。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from langchain_core.documents import Document  # noqa: E402

import retrieval as R  # noqa: E402

BRACKETED = "宪法（1982年）"
ARTICLE = "第二条"
OTHER_LAW = "民法典"


def _row(source: str, article: str, text: str) -> dict:
    return {"metadata": {"source": source, "article": article}, "text": text}


class _FakeCollection:
    """只实现 `get(where=...)`：按 `$and` 与"仅 article"两种形状返回预设行，并记录调用。"""

    def __init__(self, exact_rows: list[dict], article_rows: list[dict]) -> None:
        self._exact = exact_rows
        self._article = article_rows
        self.where_calls: list[dict] = []

    def get(self, where=None, include=None, **kw):  # noqa: ARG002 - 形参由 chroma API 决定
        self.where_calls.append(where or {})
        rows = self._exact if (where and "$and" in where) else self._article
        return {
            "ids": [f"id{i}" for i in range(len(rows))],
            "metadatas": [r["metadata"] for r in rows],
            "documents": [r["text"] for r in rows],
        }


class _FakeVS:
    """最小替身：只暴露 `_collection`（被 `exact_article_lookup` 取用的那一个属性）。

    ⚠️ 不能 `monkeypatch.setattr(R.vectorstore, "_collection", fake)`：那在 `Chroma` 上是
    **property 且无 setter**（实测报 `AttributeError: property '_collection' of 'Chroma' object has no setter`）
    ⇒ 必须替换 `retrieval.vectorstore` 这个**模块级名字**本身。
    """

    def __init__(self, collection: _FakeCollection) -> None:
        self._collection = collection


def _install(monkeypatch, exact_rows: list[dict], article_rows: list[dict]) -> _FakeCollection:
    fake = _FakeCollection(exact_rows, article_rows)
    monkeypatch.setattr(R, "vectorstore", _FakeVS(fake))
    return fake


def test_control_exact_hit_needs_no_fallback(monkeypatch):
    """控制腿：源名精确命中时**照常**返回，且**不得**走回退（只应发生一次 `$and` 查询）。

    没有这条腿，"回退里把源名过滤写成恒真"也能让下面那条全绿。
    """
    _install(monkeypatch, [_row(BRACKETED, ARTICLE, "宪法第二条正文")], [])
    docs = R.exact_article_lookup(BRACKETED, ARTICLE)
    assert [d.page_content for d in docs] == ["宪法第二条正文"]
    assert all("$and" in w for w in R.vectorstore._collection.where_calls), "精确命中不该触发回退查询"


def test_short_name_misses_then_falls_back_to_bracketed_source(monkeypatch):
    """先红腿（改前返回 0 条）：简称查不到时，按 `_source_key` 回退一次，取到带年份括注的那条。

    同时钉住"回退**不是**把同条号的其它法条一起端出来"：另有一条同条号的 `民法典` 干扰行，
    断言只返回 1 条且源名是 `宪法（1982年）`。
    """
    _install(
        monkeypatch,
        exact_rows=[],  # 精确匹配取空 —— 就是今天真实 KB 的形态
        article_rows=[
            _row(OTHER_LAW, ARTICLE, "民法典第二条正文"),
            _row(BRACKETED, ARTICLE, "宪法第二条正文"),
        ],
    )
    docs = R.exact_article_lookup("宪法", ARTICLE)
    assert len(docs) == 1, f"应恰好取到 1 条（实得 {len(docs)}）"
    assert docs[0].metadata["source"] == BRACKETED
    assert isinstance(docs[0], Document)


def test_tolerated_but_absent_source_still_returns_empty(monkeypatch):
    """控制腿（防凭空造）：库里**没有**被容忍的源名时，回退也必须返回空。

    这条挡的是"回退写成"忽略源名、只要有这个条号就返回""那种假修。
    """
    _install(monkeypatch, exact_rows=[], article_rows=[_row(OTHER_LAW, ARTICLE, "民法典第二条正文")])
    assert R.exact_article_lookup("宪法", ARTICLE) == []


def test_fallback_still_applies_time_filter(monkeypatch):
    """控制腿：回退路径也走**同一段**取文/时效过滤（`_valid_docs`），不是另一条捷径。"""

    rows = [
        {"metadata": {"source": BRACKETED, "article": ARTICLE, "valid_from": "1982-12-04"}, "text": "有据"},
        {"metadata": {"source": BRACKETED, "article": ARTICLE}, "text": "无日期字段"},
    ]
    _install(monkeypatch, exact_rows=[], article_rows=rows)
    docs = R.exact_article_lookup("宪法", ARTICLE)
    assert {d.page_content for d in docs} == {"有据", "无日期字段"}, "两条都不该被时效过滤掉（无日期=不设限）"
