"""W02 / N01：查询 token 观测必须落到真实分词器，不能恒 None。

修前根因（实测锚点）：`retrieval._query_token_len` 只探 `client`，而现役
langchain_huggingface 把 SentenceTransformer 挂在 `_client`
（venv-new 的 langchain_huggingface/embeddings/huggingface.py:79）。于是
`_warn_if_query_truncates` 拿到的一直是 None，超窗 warning 与计数器一次都没触发——
诊断记录里 18 行 `product_token_values=["None"]` 就是它的读数。

这里全部用可观测替身：不加载权重，只钉"取哪个属性、取不到时怎么说、取的时候抛错怎么留痕"。
"""

from __future__ import annotations

import logging

import retrieval


class _FakeTokenizer:
    """按"每个汉字算 1 token + 2 个 special"独立给长度，方便手工核对期望值。"""

    def __init__(self, *, raise_error: bool = False) -> None:
        self.raise_error = raise_error
        self.calls: list[str] = []

    def __call__(self, text, truncation=False):
        self.calls.append(text)
        if self.raise_error:
            raise RuntimeError("tokenizer blew up")
        assert truncation is False, "观测必须不截断，否则永远量不到超窗"
        return {"input_ids": list(range(len(text) + 2))}


class _FakeClient:
    """只带 `tokenizer` 一个面：不给夹具塞默认值，免得期望值是夹具自己喂出来的（见 X12）。"""

    def __init__(self, tokenizer=None) -> None:
        self.tokenizer = tokenizer


class _WrapperWithPrivateClient:
    """现役真实形状：模型在 `_client`，**没有** 公开的 `client`。"""

    def __init__(self, client) -> None:
        self._client = client


class _WrapperWithPublicClient:
    """旧版本形状：模型在 `client`。两个都得支持，别把版本巧合当契约。"""

    def __init__(self, client) -> None:
        self.client = client


class _CloudShapeEmbeddings:
    """云端嵌入（OpenAIEmbeddings 一类）没有本地分词器：必须诚实返回 None。"""

    def __init__(self, client) -> None:
        self.client = client


class _BrokenInner:
    """读 `_inner` 就抛（例如冷缓存 + 离线下模型构造失败）。"""

    @property
    def _inner(self):
        raise RuntimeError("cannot construct embeddings")


def _use(monkeypatch, embeddings_obj) -> None:
    monkeypatch.setattr(retrieval, "embeddings", embeddings_obj)


def test_private_client_shape_is_measured_not_none(monkeypatch):
    """阳性对照，也是 N01 的钉桩：只有 `_client` 时必须量到整数。

    修前这条恒返回 None（因为只探 `client`），所以它就是能检出目标缺陷的反例。
    """
    tok = _FakeTokenizer()
    _use(monkeypatch, _WrapperWithPrivateClient(_FakeClient(tok)))

    n = retrieval._query_token_len("甲方违约怎么办")

    assert n == 7 + 2, f"期望独立算出的 9（7 字 + 2 special），实际 {n!r}"
    assert tok.calls == ["甲方违约怎么办"]


def test_public_client_shape_still_measured(monkeypatch):
    tok = _FakeTokenizer()
    _use(monkeypatch, _WrapperWithPublicClient(_FakeClient(tok)))

    assert retrieval._query_token_len("短") == 3


def test_no_tokenizer_returns_none_without_faking_a_number(monkeypatch):
    """云端形状取不到分词器 → None；不得用字符数估算冒充真实 token。"""
    _use(monkeypatch, _CloudShapeEmbeddings(_FakeClient(None)))

    assert retrieval._query_token_len("任何文本") is None


def test_tokenizer_error_is_logged_not_swallowed(monkeypatch, caplog):
    """分词器抛错 ≠ 不可测：必须留痕，否则缺陷会伪装成诚实的 None。"""
    tok = _FakeTokenizer(raise_error=True)
    _use(monkeypatch, _WrapperWithPrivateClient(_FakeClient(tok)))

    with caplog.at_level(logging.WARNING, logger="legal.retrieval"):
        n = retrieval._query_token_len("文本")

    assert n is None
    assert any("token 观测失败" in r.getMessage() for r in caplog.records), (
        f"抛错路径没留痕，日志只有：{[r.getMessage() for r in caplog.records]}"
    )


def test_unconstructable_inner_warns_and_returns_none(monkeypatch, caplog):
    """内层构造失败要记 warning（这是失败，不是"这个模型没有分词器"）。"""
    _use(monkeypatch, _BrokenInner())

    with caplog.at_level(logging.WARNING, logger="legal.retrieval"):
        n = retrieval._query_token_len("文本")

    assert n is None
    assert any("未能构造" in r.getMessage() for r in caplog.records)


def test_truncation_boundary_sits_on_the_content_budget(monkeypatch):
    """510 是产品给查询留的内容预算，模型窗口 512 由真实 lane 实测记录在
    `evidence/W02-real-tokenizer-crosscheck.json`（不在产品里养一个没人调的读取函数）。

    期望值是手工算的：每个假分词结果 = 字符数 + 2 special，所以 508 字恰好压在预算线上、
    509 字就超。预算线两侧各钉一条，避免"512 与 510 混用"这种口径事故。
    """
    _use(monkeypatch, _WrapperWithPrivateClient(_FakeClient(_FakeTokenizer())))
    retrieval._TRUNCATION_WARNED_LENS.clear()
    before = retrieval._TRUNCATED_QUERY_COUNT

    assert retrieval._query_token_len("甲" * 508) == 510
    retrieval._warn_if_query_truncates("甲" * 508)
    assert retrieval._TRUNCATED_QUERY_COUNT == before, "恰好等于预算不该记成超窗"

    retrieval._warn_if_query_truncates("甲" * 509)
    assert retrieval._TRUNCATED_QUERY_COUNT == before + 1, "超预算一条就该记一条"


def test_over_window_increments_count_and_warns_once(monkeypatch, caplog):
    tok = _FakeTokenizer()
    _use(monkeypatch, _WrapperWithPrivateClient(_FakeClient(tok)))
    retrieval._TRUNCATION_WARNED_LENS.clear()
    before = retrieval._TRUNCATED_QUERY_COUNT
    long_text = "长" * 600  # 600 + 2 = 602 token > 510

    with caplog.at_level(logging.WARNING, logger="legal.retrieval"):
        n = retrieval._warn_if_query_truncates(long_text)
        again = retrieval._warn_if_query_truncates(long_text)

    assert n == again == 602
    assert retrieval._TRUNCATED_QUERY_COUNT == before + 2, "计数应每次都加"
    warned = [r for r in caplog.records if "超嵌入窗口" in r.getMessage()]
    assert len(warned) == 1, f"同长度应只提示一条，实际 {len(warned)} 条"


def test_warning_path_never_reaches_for_the_model(monkeypatch):
    """告警文案里不许夹任何要读内层模型的动作：那会把惰性构造的内层（≈409 MB）拉起来，
    而 `test_retrieval_rerank.py::test_query_truncation_is_loud` 只替换 `_query_token_len`，
    届时纯单元用例会去建真实模型（慢，且无缓存的 CI 直接红）。这条钉的是那个坑，不是装饰。
    """
    monkeypatch.setattr(retrieval, "_query_token_len", lambda text: 900)

    def explode():
        raise AssertionError("告警路径不该触碰嵌入模型对象")

    monkeypatch.setattr(retrieval, "_embed_client", explode)
    retrieval._TRUNCATION_WARNED_LENS.clear()

    retrieval._warn_if_query_truncates("任何超长文本")  # 不抛即通过；抛了就是回归


def test_under_window_query_does_not_warn(monkeypatch, caplog):
    tok = _FakeTokenizer()
    _use(monkeypatch, _WrapperWithPrivateClient(_FakeClient(tok)))
    before = retrieval._TRUNCATED_QUERY_COUNT

    with caplog.at_level(logging.WARNING, logger="legal.retrieval"):
        n = retrieval._warn_if_query_truncates("很短")

    assert n == 4
    assert retrieval._TRUNCATED_QUERY_COUNT == before
    assert not [r for r in caplog.records if "超嵌入窗口" in r.getMessage()]


def test_installed_embeddings_expose_a_probed_attribute_name():
    """形状契约钉在**安装面**上，而不是只钉在替身上（独立复核 B 路 M5）。

    上面那批用例全用假对象，所以只要 langchain 把模型挂到第三个名字上，10 条都会照样绿，
    而产品又会回到恒 None——正是 N01 这个缺陷本身。这条不加载权重，只读已安装的包源码，
    确认模型仍挂在我们探测的那两个名字上。
    """
    import pathlib
    import re

    import langchain_huggingface

    path = pathlib.Path(langchain_huggingface.__file__).parent / "embeddings" / "huggingface.py"
    src = path.read_text(encoding="utf-8")
    assigned = set(re.findall(r"self\.(_?client)\s*=", src))

    assert assigned & {"client", "_client"}, (
        f"{path.name} 里模型挂在 {sorted(assigned)}，产品只探 client/_client 两个名字；"
        "要么扩展探测面，要么显式声明支持边界——不许让替身测试继续假装看得见"
    )


def test_unmeasurable_query_never_counts_as_truncation(monkeypatch):
    """取不到分词器时不得凭空加计数——否则云端链路会被记成"超窗缺陷"这种假话。"""
    _use(monkeypatch, _CloudShapeEmbeddings(_FakeClient(None)))
    before = retrieval._TRUNCATED_QUERY_COUNT

    assert retrieval._warn_if_query_truncates("任意文本") is None
    assert retrieval._TRUNCATED_QUERY_COUNT == before
