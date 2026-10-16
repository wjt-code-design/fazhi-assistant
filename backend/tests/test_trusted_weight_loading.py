"""plan:433 的「**未知权重不加载**」那一半——它与 `test_loader_trust_gate.py` 是两根不同的轴。

分工要说清，否则两只文件会互相冒充：
- `tests/test_loader_trust_gate.py` 钉的是**执行自定义代码**那一侧（`trust_remote_code` 不得为真、
  库默认值当场量、生产面不得出现 opting-in 形状）。
- 本文件钉的是**加载哪份权重**那一侧：本地嵌入只允许在册的那一个 repo，
  名字不在册就在构造**之前**就拒，而不是"先加载再看看像不像"。

四条判据：
1. 未知 repo ⇒ 拒（拒绝控制）。
2. 产品构造点用的那个名字必须在册，且册子里**只有它**（防清单被悄悄加宽）。
3. 接线钉子：构造点必须真的经过这道门（把门换成哨兵，构造时必须撞到哨兵）。
   这一条是本文件的存在理由——判据定义在模块里但没人调用，就是假安全。
4. 哨兵反证：把册子清空，连"平时合法"的那个名字也要被判拒 ⇒
   证明这道门是照着册子判的，而不是写死了某个字符串比较。
"""

from __future__ import annotations

import pytest

import rag_chain as RC


def test_unknown_local_weight_repo_is_refused():
    with pytest.raises(RuntimeError) as exc:
        RC.ensure_trusted_local_embedding_model("somebody-elses/weights-v9")
    msg = str(exc.value)
    assert "未在册" in msg or "不在册" in msg, msg
    assert "somebody-elses/weights-v9" in msg


def test_the_constructed_model_is_in_the_trusted_list_and_is_the_only_one():
    """册子只许有一个名字，且就是构造点用的那个——加宽清单必须改这里，改了就红。"""
    assert RC.TRUSTED_LOCAL_EMBEDDING_MODELS == (RC.LOCAL_EMBEDDING_MODEL,)
    assert RC.ensure_trusted_local_embedding_model(RC.LOCAL_EMBEDDING_MODEL) == RC.LOCAL_EMBEDDING_MODEL


def test_construction_site_goes_through_the_guard(monkeypatch):
    """接线钉子：`_build_embeddings()` 本地分支必须调用这道门，参数就是它要加载的 repo。"""
    seen = []

    def sentinel(model_name: str) -> str:
        # 只记录、原样返回。**不要**在这里再调 `RC.ensure_trusted_local_embedding_model`：
        # 那个属性此刻已被换成 sentinel 自己 ⇒ 无限递归（我第一版就是这么炸的，
        # 那条红是夹具坏，不是产品没接线）。
        seen.append(model_name)
        return model_name

    class StubEmbeddings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(RC.settings, "embedding_provider", "local", raising=False)
    monkeypatch.setattr(RC, "ensure_trusted_local_embedding_model", sentinel)
    monkeypatch.setattr(RC, "HuggingFaceEmbeddings", StubEmbeddings)
    RC._build_embeddings()
    assert seen == [RC.LOCAL_EMBEDDING_MODEL], (
        f"构造点没把要加载的 repo 交给这道门（看到 {seen}）⇒ 判据定义了但没接线，是假安全"
    )


def test_guard_is_list_driven_not_hardcoded(monkeypatch):
    """哨兵反证：清空册子后，平时合法的名字也要被判拒。"""
    monkeypatch.setattr(RC, "TRUSTED_LOCAL_EMBEDDING_MODELS", ())
    with pytest.raises(RuntimeError):
        RC.ensure_trusted_local_embedding_model(RC.LOCAL_EMBEDDING_MODEL)
