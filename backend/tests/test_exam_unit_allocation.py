"""W05 第 3 条：`retrieve_exam` 的容量分配——题干主锚填满 k 时，选项补充**一条都进不来**。

执行书原话：「先复现 retrieve_exam 主查询满k、补充结果全被 out[:k] 截掉；定义有限容量分配
或统一融合契约，再选最小实现。正反例包含主查询满/不满、重复、单元失败、全部失败」。

为什么这条能在没有 365 MB 语料的验收树上做：测的是**合并分配**这段纯调度逻辑，
把 `hybrid_retrieve` 与 `_split_by_choice` 都换成确定值即可（拆解锁死是故意的——
否则这里测的其实是 `query_understand` 的格式识别，那是 W05 另一条的事）。
recall@6 那根轴要真库，本机测不了 ⇒ 我不在这里声称召回没变；这里只钉一条**可证的**不变量：

- `test_pool_sizes_not_deepened`：每单元请求的 k 不许被这次改动动过。
  `retrieve_exam` 的 docstring 记着 2026-08-05 那次回退：动态加深池（h10/o4/c12）把 recall 提到
  0.9625，却显著加大 Windows onnxruntime 偶发原生 segfault 的窗口，最后为稳定回退 k=6。
  ⇒ "修截断"只允许在**同等容量内重新分配**，任何加深池的做法被这条拦下。
"""

from __future__ import annotations

import pytest
from langchain_core.documents import Document

import retrieval as R

QUESTION = "甲能否解除合同？\nA. 能\nB. 不能\nC. 视情况\nD. 以上都不对"
UNITS = [QUESTION, "A. 能", "B. 不能", "C. 视情况", "D. 以上都不对"]


def _doc(tag: str) -> Document:
    return Document(page_content=f"正文-{tag}", metadata={"source": f"法-{tag}", "article": f"第{tag}条"})


class _Pool:
    """确定值替身：按单元首字符决定返回几条，并记录每次请求的 k。"""

    def __init__(self, sizes: dict[str, int]):
        self.sizes = sizes
        self.calls: list[tuple[str, int]] = []

    def __call__(self, query, k=4, category=None, cutoff=None, **kw):
        self.calls.append((query, k))
        n = self.sizes.get(query[:1], k)
        return [_doc(f"{query[:1]}{i}") for i in range(n)]


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(R.query_understand, "_split_by_choice", lambda q: list(UNITS))

    def build(sizes):
        pool = _Pool(sizes)
        monkeypatch.setattr(R, "hybrid_retrieve", pool)
        return pool

    return build


FULL = {"甲": 6, "A": 2, "B": 2, "C": 2, "D": 2}


def test_head_filling_k_no_longer_evicts_every_option(patched):
    """今天的缺陷：主查询给满 k 条，选项结果全被 `out[:k]` 截掉 ⇒ 本条现在红。"""
    patched(FULL)
    tags = [d.metadata["source"] for d in R.retrieve_exam(QUESTION, k=6)]
    assert any(t.startswith("法-A") or t.startswith("法-B") for t in tags), (
        f"选项补充一条都没进最终结果：{tags} ⇒ 分步检索的补漏作用等于零"
    )


def test_total_is_k_head_keeps_first_slot_and_options_present(patched):
    out = (patched(FULL), R.retrieve_exam(QUESTION, k=6))[1]
    assert len(out) == 6
    assert out[0].metadata["source"].startswith("法-甲"), "主锚首位不能被挤掉"
    assert any(d.metadata["source"].startswith("法-甲") for d in out[1:]), "主锚整体被清零＝反向偏置"


def test_short_head_fills_remaining_slots(patched):
    """主查询不满：空位必须由补充结果填上，不许留洞。"""
    patched({"甲": 2, "A": 3, "B": 3, "C": 3, "D": 3})
    assert len(R.retrieve_exam(QUESTION, k=6)) == 6


def test_duplicate_across_units_deduped_with_head_priority(patched, monkeypatch):
    """跨单元同一条 ⇒ 只留一次且留主锚那份（重复白占名额会让补充更进不来）。"""
    shared = _doc("共用条文")

    def dup(query, k=4, category=None, cutoff=None, **kw):
        head = query.startswith("甲")
        return [shared] * (2 if head else 1) + [_doc(query[:1] + str(i)) for i in range(k)]

    monkeypatch.setattr(R, "hybrid_retrieve", dup)
    out = R.retrieve_exam(QUESTION, k=6)
    texts = [d.page_content for d in out]
    assert len(texts) == len(set(texts)), f"合并后仍有重复：{texts}"
    assert texts.count("正文-共用条文") == 1


def test_pool_sizes_not_deepened(patched):
    """不变量：主锚仍请求 k、每选项仍请求 max(2, k//3)。加深池是回退过的坑。"""
    pool = patched(FULL)
    R.retrieve_exam(QUESTION, k=6)
    assert [k for _q, k in pool.calls] == [6, 2, 2, 2, 2], pool.calls


def test_failed_unit_skipped_without_holes(patched, monkeypatch):
    pool = patched({"甲": 6, "A": 2, "B": 2, "C": 2})

    def flaky(query, k=4, category=None, cutoff=None, **kw):
        if query.startswith("D"):
            raise RuntimeError("嵌入炸了")
        return pool(query, k)

    monkeypatch.setattr(R, "hybrid_retrieve", flaky)
    assert len(R.retrieve_exam(QUESTION, k=6)) == 6


def test_all_units_fail_falls_back_to_whole_question(monkeypatch):
    """全失败 → 整题兜底那条路必须还在（不许返回空）。

    第一版这里写的是 `n == 1 and k == 6`，结果**主锚那一次就成功了**——测试以错误的原因通过，
    兜底路径根本没走到。改成：5 个单元（题干＋4 选项）全挂，第 6 次才是兜底，
    并断言确实调用到第 6 次，否则这条绿灯什么都不证明。
    """
    monkeypatch.setattr(R.query_understand, "_split_by_choice", lambda q: list(UNITS))
    state = {"n": 0}

    def always_fail(query, k=4, category=None, cutoff=None, **kw):
        state["n"] += 1
        if state["n"] > len(UNITS):  # 兜底那次整题检索
            return [_doc("兜底0")]
        raise RuntimeError("全挂")

    monkeypatch.setattr(R, "hybrid_retrieve", always_fail)
    out = R.retrieve_exam(QUESTION, k=6)
    assert state["n"] == len(UNITS) + 1, f"没走到兜底（调用 {state['n']} 次）"
    assert out, "全单元失败时兜底路径没走到，返回了空"
