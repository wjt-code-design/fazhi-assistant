"""W10 / D-45 / C08：把「只支持已测闭包」变成**机器判据**，且追踪名单**从文件导出**。

Owner 2026-10-17 裁 C08＝固定闭包（plan:204：精确可复现闭包与诚实支持边界；兼容性未证不称全窗支持）。
plan:408 同时禁两件事：不许把「其他合规版本属边界外」这种**注释**当契约，
也不许用 `except ImportError`/`skip` 把私有面失效遮成绿。

四条判据，每条都能红，且互相不遮蔽：

1. `test_every_direct_requirement_is_an_exact_pin`——每一条直接依赖必须 `==`。
2. `test_parser_claims_every_substantive_line`——**覆盖率钉子**：解析器认领的行数必须等于文件里
   真实的有效行数。这条存在的理由是防一类具体事故：名单若手抄或解析器漏了一种形状（extras、marker、
   续行），被漏掉的包会**静默逃过判据**，于是"闭包已被钉住"变成假话（第 1 条照样绿）。
3. `test_installed_matches_the_declared_closure`——声明必须等于当前解释器的装机版本。
   含一条**显式的 local 版本段规则**：`torch` 在 CPU 索引下装机是 `2.13.0+cpu`，
   声明 `2.13.0` 才是对的形状（PEP 440 的 local 段由安装源决定）。
   这不是例外通道——走这条路必须**点名是哪个包**，且不许把"版本不同"混进来。
4. `test_private_sdk_symbols_are_reachable_and_not_guarded`——私有 SDK 面失效要硬显现。
"""

from __future__ import annotations

import importlib
import importlib.metadata
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REQ = BACKEND / "requirements.txt"

# `name[extras] ==version`；比较符这里只接受 `==`（其余一律算未固定）
ENTRY = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)(?P<extras>\[[^\]]+\])?\s*==\s*(?P<version>[A-Za-z0-9_.+!-]+)\s*$")
ANY_NAME = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)(?P<extras>\[[^\]]+\])?\s*(?P<spec>.*)$")


def _lines():
    """产出 (行号, 原文, 是否有效依赖行)。注释与 `-r`/`--flag` 行不算有效。"""
    out = []
    for no, raw in enumerate(REQ.read_text(encoding="utf-8").splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith("#") or s.startswith("-"):
            continue
        out.append((no, s))
    return out


def _parsed():
    parsed = {}
    for no, s in _lines():
        m = ANY_NAME.match(s)
        if not m:
            continue
        parsed[m.group("name").lower()] = (no, s, m.group("spec") or "")
    return parsed


def test_every_direct_requirement_is_an_exact_pin():
    bad = {n: s for n, (_no, s, spec) in _parsed().items() if not ENTRY.match(s)}
    assert not bad, f"这些直接依赖不是精确 pin（C08 已裁固定闭包）：{bad}"


def test_parser_claims_every_substantive_line():
    """覆盖率钉子：漏一个包就等于给判据开了一个静默后门。

    这里刻意用**两条独立路径**数同一件事：`_lines()`/`_parsed()` 是判据自己的解析器，
    而 oracle 直接对着原始字节走一条**不同的**正则。只用解析器自证的话，
    它少认一行时两边同时变少，比较照样相等——那种"钉子"是恒绿的废尺（M4 变异就是打这个）。
    """
    raw = REQ.read_bytes().decode("utf-8")
    oracle = set()
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)", s)
        if m:
            oracle.add(m.group(1).lower())
    claimed = set(_parsed())
    assert claimed == oracle, (
        f"判据的解析器只认领了 {sorted(claimed)[:3]}…共 {len(claimed)} 个，文件里实际有 {len(oracle)} 个；"
        f"漏网＝{sorted(oracle - claimed)}，多余＝{sorted(claimed - oracle)} ⇒ 漏掉的那些没有任何判据在管"
    )
    # extras 必须原样保留：CI 与本机都靠 `[standard]` 装到同一组 uvicorn 可选依赖
    assert any("[standard]" in s for _n, (_no, s, _spec) in _parsed().items()), (
        "`uvicorn[standard]` 的 extras 丢了——丢 extras 会让声明与实际安装面不一致"
    )


def test_installed_matches_the_declared_closure():
    """声明＝装机；local 版本段（`+cpu`）走显式点名规则，不当通用后门。"""
    local_segment_packages = {"torch"}
    bad, via_local = [], []
    for name, (_no, _s, _spec) in _parsed().items():
        m = ENTRY.match(_s)
        if not m:
            continue
        want = m.group("version")
        try:
            got = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            bad.append((name, want, "MISSING"))
            continue
        if got == want:
            continue
        base, plus, local = got.partition("+")
        if plus and base == want and name in local_segment_packages and local:
            via_local.append((name, want, got))
            continue
        bad.append((name, want, got))
    assert not bad, (
        f"当前解释器与在册闭包不一致：{bad}；"
        f"（走 local 版本段的只有这些：{sorted(x[0] for x in via_local)}——"
        "名单外的一律算不一致，这条不是例外通道）"
    )
    assert sorted(x[0] for x in via_local) == sorted(local_segment_packages), (
        f"local 版本段的包名单变了：{via_local}——变了就要改这条测试，别让它悄悄扩大"
    )


def test_private_sdk_symbols_are_reachable_and_not_guarded():
    """私有面失效要硬显现：直接导入、直接断言，不 catch、不 skip。"""
    mod = importlib.import_module("langchain_openai.chat_models._client_utils")
    for attr in ("_cached_sync_httpx_client", "_cached_async_httpx_client"):
        assert callable(getattr(mod, attr)), f"私有 SDK 符号 {attr} 不在或不可调用 ⇒ 依赖闭包变了"

    src = (BACKEND / "tests" / "test_llm_lifecycle.py").read_text(encoding="utf-8")
    head = src.split("import pytest", 1)[-1][:400]
    assert "try:" not in head, "私有 import 被包进了 try ⇒ D-45 要求的『硬显现』被破坏"
