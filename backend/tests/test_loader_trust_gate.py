"""E.2 加载信任门：默认嵌入加载路径不得执行模型目录里的自定义代码。

生产路径只有一处构造点：`rag_chain._build_embeddings()` → `HuggingFaceEmbeddings`
→ `sentence_transformers.SentenceTransformer`。本文件钉三件**能在 CI 里跑**的事：

1. 构造点没有传 `trust_remote_code`（既不在顶层 kwargs 也不在 `model_kwargs` 里）
   ⇒ 它落在库默认值上，而默认值是"拒绝执行自定义代码"那一侧。
2. 库默认值当场量一次：`SentenceTransformer.__init__.parameters['trust_remote_code'].default is False`
   ⇒ 上游哪天把默认改成 True，本条**先红**，而不是等生产去执行陌生代码。
3. 生产源码里不存在任何 `trust_remote_code=True` / `="local"` 的 opting-in 形状。

行为级证据（阳性对照真的执行了 marker）不在这只文件里——它需要 409 MB 权重，跑一次约两分钟，
不适合进默认套件。现量读数与复算命令见
`reports/trust-and-data-drill.md` §1（脚本 `evidence/probe_st_trust.py`，五臂 A/B/C/E + CTRL）。
本文件的三条是"接线与默认值"腿，那条是"真执行"腿，两根轴分开记，不互相冒充。
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
# 生产面 = backend 根 + agent/ + scripts/；tests/ 里允许出现反例样本，venv 不是本项目源码。
PROD_DIRS = [BACKEND, BACKEND / "agent", BACKEND / "scripts"]


def _build_embeddings_source() -> str:
    import rag_chain

    return inspect.getsource(rag_chain._build_embeddings)


def _embedding_call_kwargs(source: str) -> dict[str, ast.keyword]:
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "HuggingFaceEmbeddings"
    ]
    assert len(calls) == 1, f"构造点应当只有一处，实际 {len(calls)} 处"
    return {kw.arg: kw for kw in calls[0].keywords if kw.arg}


def test_local_embedding_construction_never_opts_into_trust_remote_code():
    """构造点的 AST 里任何一层都不许出现 `trust_remote_code`。"""
    kws = _embedding_call_kwargs(_build_embeddings_source())
    blob = ast.dump(ast.Module(body=list(kws.values()), type_ignores=[]))
    assert "trust_remote_code" not in blob, "构造点显式传了 trust_remote_code ⇒ 默认拒绝路径被绕过"
    assert set(kws) <= {"model_name", "model_kwargs", "encode_kwargs", "filter_to_hf_modules", "show_progress_bar"}


def _refusing_default(target) -> bool:
    """True 只当 `trust_remote_code` 形参存在且默认恰为 False（拒绝执行自定义代码那一侧）。"""
    param = inspect.signature(target.__init__).parameters.get("trust_remote_code")
    return param is not None and param.default is False


def test_sentence_transformers_default_is_the_refusing_value():
    """上游默认值一旦翻侧，这条先红（而不是生产先执行陌生代码）。"""
    sentence_transformers = pytest.importorskip("sentence_transformers")
    assert _refusing_default(sentence_transformers.SentenceTransformer), (
        "ST 的 trust_remote_code 默认值不再是 False ⇒ 默认加载路径可能执行模型目录里的自定义代码"
    )


def test_canary_itself_can_go_red():
    """负向自证：同一个判据喂给"默认 True"的替身必须判否 —— 否则上一条是恒真断言。"""

    class _Stingy:
        def __init__(self, model_name_or_path, trust_remote_code=True):  # noqa: D401
            pass

    class _Missing:
        def __init__(self, model_name_or_path):
            pass

    assert _refusing_default(_Stingy) is False, "判据对默认 True 不红 ⇒ 它是恒真哨兵"
    assert _refusing_default(_Missing) is False, "形参消失也不算门存在"


def test_no_production_site_requests_trusted_custom_code():
    """全生产面用 **AST** 找 `trust_remote_code`，不用行文本 grep。

    为什么不是 grep：grep 腿能被两种写法穿过去 —— ①同一行里出现 `False`（例如
    `{"trust_remote_code": False or True}`）就被"跳过含 False 的行"这条规则放走；②键名在运行期拼出来。
    ①现在由本条堵住（AST 不看行文本，只看有没有这个关键字/这个字符串常量）；
    ②**静态查不到**，那是已知射程外 —— 真行为证据在 `evidence/probe_st_trust*.py`（五臂，独立进程），
    把这条腿当"接线检查"而不是"门"来读。
    """
    hits = []
    for root in PROD_DIRS:
        if not root.is_dir():
            continue
        for py in sorted(root.glob("*.py")):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.keyword) and node.arg == "trust_remote_code":
                    hits.append(f"{py.name}:{node.lineno} keyword")
                elif isinstance(node, ast.Constant) and node.value == "trust_remote_code":
                    hits.append(f"{py.name}:{node.lineno} 字符串键")
    assert hits == [], "生产代码里出现了 trust_remote_code 的传递点：" + " | ".join(hits)
