"""W07-FIX V-B1/V-B2（2026-10-17）：**一个拼错的 transport 值不许打死启动**。

元教训（票 §2 末）：`14febe6` 的全量纯树门可以**全绿而服务起不来**——因为没有任何测试覆盖
「配置里有坏 transport 值时的启动路径」：`_build` 对未知 transport 抛 `ValueError`
（`llm_registry.py:434-436`），而 `_load` 的降级口子只 `except RuntimeError: continue`（:550-556），
且 `registry = LLMRegistry()` 跑在**模块作用域**（:944）⇒ `LLM_MODELS_JSON` 写一个
`"transport":"transcription"` 整个后端 import 就炸。

所以本文件的**第一条是导入期判据**（子进程 `import llm_registry`，票 §3 V-B1 的「修之前必须是红的」
就是这一条），其余几条把它拆成可断言的三件事：坏 entry 被跳过、其余 entry 照常可用、
跳过落一条**已登记**的归因读数。

零外发（票 §5）：所有 entry 的 `base_url` 指 `http://127.0.0.1:9`（discard 端口，回环立即拒连）、
`api_key` 是假值；`ChatOpenAI` 构造期不发请求，子进程也只 import 不调用。
"""

import ast
import inspect
import json
import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import llm_registry  # noqa: E402
import quota_store  # noqa: E402
from observability import _ACCOUNT_FIELDS, _JsonFormatter  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
_SENTINEL = "BOOT_OK"
_FAKE_CFG = {"api_key": "fake-value-not-a-secret", "base_url": "http://127.0.0.1:9/v1"}


def _role(key: str, **extra) -> dict:
    base = {
        "key": key,
        "model": f"Fake/{key}",
        "modality": "voice",
        "tier": "flag",
        "priority": 0,
        "capabilities": ["speech", "asr"],
        **_FAKE_CFG,
    }
    base.update(extra)
    return base


def _bad_roles() -> list[dict]:
    """一条坏 transport 值夹在两条好 entry 中间：跳过它，两边都得活。"""
    return [
        _role("voice_chat"),
        _role("voice_typo", transport="transcription"),
        _role("voice_multipart", transport="audio_transcriptions"),
    ]


def _registry_from(monkeypatch, roles) -> llm_registry.LLMRegistry:
    import settings as _s

    monkeypatch.setattr(_s.settings, "llm_models_json", json.dumps(roles))
    monkeypatch.setattr(quota_store, "get_used", lambda key: 0)
    monkeypatch.setattr(quota_store, "record_delta", lambda key, delta: 0)
    monkeypatch.setattr(quota_store, "initial_override", lambda key: None)
    return llm_registry.LLMRegistry()


class _Capture:
    """直挂 logger 抓记录（`setup_logging` 关 propagate，caplog 收不到）。"""

    def __init__(self, logger: logging.Logger, level: int = logging.WARNING):
        self.logger = logger
        self.level = level
        self.items: list[logging.LogRecord] = []

        class _Handler(logging.Handler):
            def __init__(self, owner):
                super().__init__(level=owner.level)
                self._owner = owner

            def emit(self, record):
                self._owner.items.append(record)

        self._handler = _Handler(self)

    def __enter__(self):
        self._previous = self.logger.level
        self.logger.addHandler(self._handler)
        self.logger.setLevel(self.level)
        return self

    def __exit__(self, *exc_info):
        self.logger.removeHandler(self._handler)
        self.logger.setLevel(self._previous)

    def field(self, key: str) -> list:
        """某个归因字段亮了就返回它的值（顺带把「亮了但没登记」当红——未登记会被 formatter 丢掉）。"""
        out = []
        for record in self.items:
            v = getattr(record, key, None)
            if v:
                assert key in _ACCOUNT_FIELDS, f"键 {key} 亮了但没登记进 _ACCOUNT_FIELDS ⇒ formatter 会丢掉它"
                out.append(v)
        return out


# ---------------------------------------------------------------- V-B1 导入期那一腿


def test_import_time_bad_transport_value_does_not_kill_the_backend():
    """V-B1（红就红在这里）：坏 transport 值的 `LLM_MODELS_JSON` 下 `import llm_registry` 仍要成功。

    这条必须是**子进程 import**：`registry = LLMRegistry()` 就跑在模块作用域（`llm_registry.py:944`），
    而 `main.py` 一 import 它就把整只后端带走。进程内再构造一次 registry 证不了「服务能起」。
    """
    code = (
        "import llm_registry as m\n"
        f"print({_SENTINEL!r})\n"
        "print('ENTRIES=' + ','.join(sorted(m.registry._entries)))\n"
        "print('TRANSPORT=' + m.registry.transport_of('voice_multipart'))\n"
    )
    env = dict(os.environ)
    env["LLM_MODELS_JSON"] = json.dumps(_bad_roles())
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(BACKEND),
        env=env,
        timeout=600,
    )
    assert proc.returncode == 0, f"import 期就炸 ⇒ 后端起不来：rc={proc.returncode} stderr={proc.stderr[-900:]}"
    out = proc.stdout
    assert _SENTINEL in out, out
    # 坏 entry 不起，另外两条照常可用：`voice_multipart` 的 transport 仍读得到（=分派真源没被跳过带崩）
    entries = [ln for ln in out.splitlines() if ln.startswith("ENTRIES=")][0].split("=", 1)[1]
    assert "voice_typo" not in entries.split(","), f"坏 transport 的 entry 竟然还在册：{entries}"
    assert {"voice_chat", "voice_multipart"} <= set(entries.split(",")), entries
    assert "TRANSPORT=audio_transcriptions" in out, out


# ---------------------------------------------------------------- V-B1 拆开的三件事


def test_bad_transport_entry_is_skipped_and_the_others_stay_usable(monkeypatch):
    """构造成功＋坏 entry 跳过＋其余 entry 可用（票 §2 W7-B1 的「必须加一条判据」）。"""
    with _Capture(logging.getLogger("legal.llm")) as records:
        reg = _registry_from(monkeypatch, _bad_roles())

    keys = sorted(reg._entries)
    assert keys == ["voice_chat", "voice_multipart"], f"entry 面不对：{keys}"
    assert reg.transport_of("voice_multipart") == "audio_transcriptions"
    assert reg.transport_of("voice_chat") == "chat"
    assert reg.transport_of("voice_typo") == "chat", "被跳过的 entry 不许把调用方拖进另一条路"
    key, llm = reg.pick("voice", "flag")
    assert key in {"voice_chat", "voice_multipart"} and llm is not None, "活着的 entry 必须仍能被选中"
    assert reg.has_modality("voice") is True, "坏 entry 被跳过不许把整只模态判成没配"
    assert records.field("llm_cfg_entry_rejected"), "坏 entry 被静默跳过 ⇒ 没有任何归因读数"


def test_skipped_bad_transport_lights_a_registered_attribution_key(monkeypatch):
    """跳过不是「无声消失」：落一条**已登记**的归因读数，且 JSON 里真读得到。"""
    with _Capture(logging.getLogger("legal.llm")) as records:
        _registry_from(monkeypatch, _bad_roles())
    hits = records.field("llm_cfg_entry_rejected")
    assert len(hits) == 1, hits
    text = json.dumps({"llm_cfg_entry_rejected": hits[0]}, ensure_ascii=False)
    assert "voice_typo" in text, text
    fmt = _JsonFormatter()
    rec = next(r for r in records.items if getattr(r, "llm_cfg_entry_rejected", None))
    assert json.loads(fmt.format(rec)).get("llm_cfg_entry_rejected") == hits[0]


def test_unconfigured_provider_is_still_skipped_and_now_also_attributed(monkeypatch):
    """2026-08-08 那条「没配 key 的 provider 跳过」不许被本轮改坏：仍跳过，但也不再无声。

    复核指出的顺序 bug：缺 key 的 `RuntimeError` 检查排在 transport 校验**之后**，
    所以一个坏 transport 值会连「本来会被跳过的未配置 provider」一起炸死。
    """
    roles = [_role("voice_nokey", api_key="", base_url=""), _role("voice_badvalue", transport="whisper")]
    import settings as _s

    # 把「所有可能的兜底凭据」清空（属性是只读 property，只能改它读的字段），
    # 否则 .env 里的真凭据会给这条 entry 兜底 ⇒ 这条腿变成空跑。
    monkeypatch.setattr(_s.settings, "llm_api_key", "")
    monkeypatch.setattr(_s.settings, "zhipuai_api_key", "")
    monkeypatch.setattr(_s.settings, "llm_base_url", "")
    with _Capture(logging.getLogger("legal.llm")) as records:
        reg = _registry_from(monkeypatch, roles)
    assert sorted(reg._entries) == [], "两条 entry 都该被跳过：缺 key 的那条走老路，坏值的那条走本轮新腿"
    hits = [str(x) for hit in records.field("llm_cfg_entry_rejected") for x in hit]
    assert len(hits) == 2, hits
    assert any("voice_badvalue" in x for x in hits), hits
    assert any("voice_nokey" in x for x in hits), hits


# ---------------------------------------------------------------- V-B2：拼错的键是可见信号


def test_typo_entry_key_is_a_visible_signal_on_the_raw_entry_dict(monkeypatch):
    """V-B2：`_build` 的 cfg 白名单 raise 在真实配置路径上**不可达**（`_load` 用八个写死的键重建 cfg），
    所以未知键检查必须作用到 entry 原始 dict 上——拼错的键要「看得见」，而不是「值静默消失」。
    """
    roles = [_role("voice_ok"), _role("voice_typo", transpor="audio_transcriptions")]
    with _Capture(logging.getLogger("legal.llm")) as records:
        reg = _registry_from(monkeypatch, roles)
    hits = records.field("llm_cfg_unknown_keys")
    assert hits == [["transpor"]], f"拼错的键没有留痕：{hits}"
    # 值不会被静默采信（拼错的键≠生效的键），也不会静默消失（读数点名了那个键）
    assert reg.transport_of("voice_typo") == "chat"
    entry = reg._entries["voice_typo"]
    assert "transpor" not in entry.cfg and "transport" not in entry.cfg, sorted(entry.cfg)
    # 归因必须能落到「哪一条 entry」——只报键名等于让运维去猜是哪条配置
    assert any("voice_typo" in r.getMessage() for r in records.items), [r.getMessage() for r in records.items]


def test_unknown_key_check_is_one_ruler_shared_by_build_and_load():
    """W7-B2 的结构性那一半：cfg 与 entry 两面用**同一把尺**，两处不许各写一遍减法。"""
    source = inspect.getsource(llm_registry)
    assert "- CFG_KEYS" not in source and "- ROLE_KEYS" not in source, (
        "白名单减法被抄成两处 ⇒ entry 面那份会跟着 cfg 面一起漂"
    )
    helpers = [n for n, o in vars(llm_registry).items() if callable(o) and "unknown" in n]
    assert len(helpers) == 1, helpers
    fn = getattr(llm_registry, helpers[0])
    assert fn({"model": "x", "transpor": "chat"}, llm_registry.CFG_KEYS) == ["transpor"]
    # 正对照：干净 dict 数不出东西，否则这条判据是恒真的
    assert fn({"model": "x", "api_key": "k"}, llm_registry.CFG_KEYS) == []


def test_llm_entry_rejected_key_is_registered_for_the_formatter():
    """新键必须与发射它的改动同批登记（上一票就是漏这格被全量门打回）。"""
    assert "llm_cfg_entry_rejected" in _ACCOUNT_FIELDS
    assert "llm_cfg_unknown_keys" in _ACCOUNT_FIELDS


# ================================================================ R2（复核第二轮）F1/F2/F3
#
# 复核第二轮打穿的**不是** B1 那个字段，而是 B1 那个**类**：
# `int(timeout)`／`int(priority)`／`int(quota_total)`／`int(initial_used)`／`r["model"]`／
# `json.loads(LLM_MODELS_JSON)` 全都排在 per-entry try（原 `:588`）**之外**，而
# `registry = LLMRegistry()` 跑在模块作用域 ⇒ 任何一个写错的数值/整段坏 JSON 仍然把后端在 import 期炸掉，
# 而九腿纯树门当时全绿（上一轮的判据只咬住 transport 一格）。
# F3 是同一条链的另一头：`_load` 开心地把 `_entries` 留成空 dict，`main.py:health()` 照旧回 "ok"。


def _no_model_role(key: str) -> dict:
    r = _role(key)
    r.pop("model")
    return r


def _r2_bad_entry_cases() -> list[tuple[str, Any, str | None]]:
    """(用例名, 坏 entry, 期望**不在册**的 key)：坏 entry 夹在两条好 entry 中间。"""
    return [
        ("bad-timeout", _role("voice_timeout", timeout="abc"), "voice_timeout"),
        ("bad-priority", _role("voice_priority", priority=None), "voice_priority"),
        ("bad-quota-total", _role("voice_quota", quota_total="x"), "voice_quota"),
        ("bad-initial-used", _role("voice_used", initial_used="many"), "voice_used"),
        ("missing-model", _no_model_role("voice_nomodel"), "voice_nomodel"),
        ("entry-is-list", ["voice_list", "我不是对象"], None),
        ("entry-is-string", "voice_str 我不是对象", None),
    ]


def _r2_roles(bad: Any) -> list[Any]:
    return [_role("voice_chat"), bad, _role("voice_multipart", transport="audio_transcriptions")]


def _r2_all_bad_roles() -> list[Any]:
    """**每一条**都坏：用来钉「0 条可用 entry 不许看起来健康」（R2-F3）。

    刻意只用形状类坏值（数值写错／缺 model／非对象），不靠「没配凭据」——后者会随 `.env`
    有没有真 key 而变，判据不能建在环境上。
    """
    return [
        _role("voice_timeout", timeout="abc"),
        _role("voice_priority", priority=None),
        _role("voice_quota", quota_total="x"),
        _role("voice_used", initial_used="many"),
        _no_model_role("voice_nomodel"),
        ["voice_list", "我不是对象"],
    ]


@pytest.mark.parametrize(
    "case_id,bad_entry,absent_key",
    _r2_bad_entry_cases(),
    ids=[c[0] for c in _r2_bad_entry_cases()],
)
def test_r2_import_time_bad_entry_shape_does_not_kill_the_backend(case_id, bad_entry, absent_key):
    """R2-F1（修前必红就红在这里）：entry 构造全程任一形状写错都不许炸 import。

    与上面那条 B1 判据的分工：B1 只钉 transport 一个字段；本条把同一判据**参数化**到
    timeout/priority/quota_total/initial_used/model/整条 entry 的形状上——复核说的
    「moved, not closed」就是这一格：改动落到了一个字段，类还在。
    """
    code = (
        "import llm_registry as m\n"
        f"print({_SENTINEL!r})\n"
        "print('ENTRIES=' + ','.join(sorted(m.registry._entries)))\n"
        "print('SKIPPED=' + str(m.registry.skipped_count()))\n"
    )
    env = dict(os.environ)
    env["LLM_MODELS_JSON"] = json.dumps(_r2_roles(bad_entry))
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(BACKEND),
        env=env,
        timeout=600,
    )
    assert proc.returncode == 0, (
        f"{case_id}：import 期就炸 ⇒ 后端起不来：rc={proc.returncode} stderr={proc.stderr[-900:]}"
    )
    out = proc.stdout
    assert _SENTINEL in out, out
    entries = [ln for ln in out.splitlines() if ln.startswith("ENTRIES=")][0].split("=", 1)[1].split(",")
    assert {"voice_chat", "voice_multipart"} <= set(entries), f"{case_id}：其余 entry 被一条坏配置带走了：{entries}"
    if absent_key is not None:
        assert absent_key not in entries, f"{case_id}：坏 entry 竟然还在册：{entries}"
    else:
        assert len(entries) == 2, f"{case_id}：非对象 entry 没被跳过：{entries}"


def test_r2_malformed_json_falls_back_to_default_roles_without_killing_the_import():
    """R2-F1 的另一半：`LLM_MODELS_JSON` **整段**不可解析（少个逗号）过去直接死在 import。

    现钉：import 成功，且在册 entry 与「不设 LLM_MODELS_JSON 时的 DEFAULT_ROLES 路」**逐字相同**
    ——回退到默认表，而不是清空、也不是抛。参照系在同一进程里现算，所以判据与 `.env` 里
    有没有真凭据无关（纯树门的跑法可能带空 `.env`，那时两边都该是空）。
    """
    code = (
        "import llm_registry as m\n"
        f"print({_SENTINEL!r})\n"
        "print('BROKEN=' + ','.join(sorted(m.registry._entries)))\n"
        "m.settings.llm_models_json = ''\n"
        "print('REFERENCE=' + ','.join(sorted(m.LLMRegistry()._entries)))\n"
    )
    env = dict(os.environ)
    env["LLM_MODELS_JSON"] = '[{"key": "voice_chat", "model": "Fake/voice_chat"'  # 截断的 JSON
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(BACKEND),
        env=env,
        timeout=600,
    )
    assert proc.returncode == 0, f"坏 JSON 打死 import：rc={proc.returncode} stderr={proc.stderr[-900:]}"
    out = proc.stdout
    assert _SENTINEL in out, out
    line = {ln.split("=", 1)[0]: ln.split("=", 1)[1] for ln in out.splitlines() if "=" in ln}
    assert line["BROKEN"] == line["REFERENCE"], (
        f"坏 JSON 没有回退到 DEFAULT_ROLES 那一条路：broken={line['BROKEN']!r} reference={line['REFERENCE']!r}"
    )


def test_r2_malformed_json_lights_a_registered_attribution_key(monkeypatch):
    """回退不是「无声按默认值跑」：必须亮一只**已登记**的归因键（未登记会被 formatter 丢掉）。"""
    import settings as _s

    monkeypatch.setattr(_s.settings, "llm_models_json", '[{"key": "voice_chat", ')
    monkeypatch.setattr(quota_store, "get_used", lambda key: 0)
    monkeypatch.setattr(quota_store, "record_delta", lambda key, delta: 0)
    monkeypatch.setattr(quota_store, "initial_override", lambda key: None)
    with _Capture(logging.getLogger("legal.llm")) as records:
        broken = llm_registry.LLMRegistry()

    hits = records.field("llm_cfg_malformed")
    assert hits, "整段 JSON 不可解析却零读数 ⇒ 运维只知道「模型变少了」，不知道为什么"
    # 正对照：同一把尺子在干净 JSON 上不许亮（否则这条判据是恒真的）
    monkeypatch.setattr(_s.settings, "llm_models_json", json.dumps([_role("voice_chat")]))
    with _Capture(logging.getLogger("legal.llm")) as clean:
        llm_registry.LLMRegistry()
    assert clean.field("llm_cfg_malformed") == [], "干净配置也亮 malformed ⇒ 这只键不再能指向病因"
    assert "llm_cfg_malformed" in _ACCOUNT_FIELDS

    # 回退形状：与「不设 LLM_MODELS_JSON」的 DEFAULT_ROLES 路**同一条**（关系式判据，不依赖凭据）
    monkeypatch.setattr(_s.settings, "llm_models_json", "")
    with _Capture(logging.getLogger("legal.llm")):
        reference = llm_registry.LLMRegistry()
    assert sorted(broken._entries) == sorted(reference._entries)


def test_r2_bad_numeric_entries_skip_only_their_own_row(monkeypatch):
    """进程内同一格：每条坏形状**只**带走自己那一行，其余照常在册，且逐条有归因。"""
    with _Capture(logging.getLogger("legal.llm")) as records:
        reg = _registry_from(monkeypatch, _r2_all_bad_roles()[:5] + [_role("voice_chat")])

    assert sorted(reg._entries) == ["voice_chat"], f"坏形状越权了：{sorted(reg._entries)}"
    hits = [str(x) for hit in records.field("llm_cfg_entry_rejected") for x in hit]
    assert len(hits) == 5, hits
    for key in ("voice_timeout", "voice_priority", "voice_quota", "voice_used", "voice_nomodel"):
        assert any(key in h for h in hits), f"{key} 被跳过却没人说出是谁：{hits}"


def test_r2_non_dict_entry_is_skipped_not_crashed(monkeypatch):
    """entry 写成数组/字符串：`r["key"]` 的 TypeError 过去直接打死构造，现在只跳过这一条。"""
    roles: list[Any] = ["我不是对象", {"key": 123, "model": "Fake/x"}, _role("voice_chat")]
    with _Capture(logging.getLogger("legal.llm")) as records:
        reg = _registry_from(monkeypatch, roles)
    assert sorted(reg._entries) == ["voice_chat"], sorted(reg._entries)
    hits = [str(x) for hit in records.field("llm_cfg_entry_rejected") for x in hit]
    assert len(hits) == 2, hits


# ------------------------------------------------------------------ R2-F2：ValueError 腿要真能到达


def test_r2_valueerror_leg_is_reachable_from_a_bad_model_type(monkeypatch):
    """R2-F2：`_build` 的 ValueError 腿在真实配置路径上原本**够不着**（cfg 由固定键名重建、
    transport 不再进 cfg），而 `_load` 的注释把它写成「这条 entry 的 cfg 本身写错」——
    复核的结论是「The credited mechanism is inert」。

    注释与判据**都要**动：
    ① 现钉一条真能走到 ValueError 的坏形状（`model` 键在但值为 null ⇒ pydantic ValidationError，
       它是 ValueError 的子类），只跳过这一条；
    ② 那句被击穿的话从源码里消失（留着比删掉更坏）。
    """
    roles = [_role("voice_chat"), _role("voice_nullmodel", model=None)]
    with _Capture(logging.getLogger("legal.llm")) as records:
        reg = _registry_from(monkeypatch, roles)

    assert sorted(reg._entries) == ["voice_chat"], f"model=null 的 entry 没被降级掉：{sorted(reg._entries)}"
    hits = [str(x) for hit in records.field("llm_cfg_entry_rejected") for x in hit]
    assert len(hits) == 1, hits
    assert "voice_nullmodel" in hits[0], hits

    src = textwrap.dedent(inspect.getsource(llm_registry.LLMRegistry._load))
    assert "cfg 本身写错" not in src, "注释仍把 ValueError 说成「cfg 白名单命中」⇒ 那条腿在真实配置路径上够不着"


# ------------------------------------------------------------------ R2-F3：0 条可用不许像健康


def test_r2_zero_usable_entries_does_not_raise_at_construction(monkeypatch):
    """方向约束：R2-F3 要的是「0 条要**报出来**」，不是「0 条就 raise」——后者正是 W7-B1 刚修掉的
    坏形状（服务起不来），两格方向相反，谁也不许把对方打回。这里先把「不抛」钉住。"""
    reg = _registry_from(monkeypatch, _r2_all_bad_roles())
    assert reg.entry_count() == 0
    assert reg.skipped_count() == len(_r2_all_bad_roles())


def test_r2_zero_usable_entries_is_not_reported_as_healthy(monkeypatch):
    """R2-F3(a)：全部 entry 都坏 ⇒ `/api/health` 不许再回 `status="ok"`，且两个计数要带出来。"""
    from fastapi.testclient import TestClient

    import main

    reg = _registry_from(monkeypatch, _r2_all_bad_roles())
    monkeypatch.setattr(main, "registry", reg)
    with TestClient(main.app) as client:
        resp = client.get("/api/health")
    assert resp.status_code == 200, "健康检查不该改成 5xx（本票只要它别声称健康）"
    body = resp.json()
    assert body["status"] != "ok", f"0 条可用 entry 仍被报成健康：{body}"
    assert body["llm_entry_count"] == 0, body
    assert body["llm_entry_rejected"] == len(_r2_all_bad_roles()), body


def test_r2_one_usable_entry_is_healthy_with_matching_counts(monkeypatch):
    """R2-F3(b) 成对的那一半：至少一条好 ⇒ 仍是 `ok`，且计数**对得上**（不是恒 0 的摆设）。"""
    from fastapi.testclient import TestClient

    import main

    roles = [_role("voice_chat"), _role("voice_timeout", timeout="abc"), _role("voice_priority", priority=None)]
    reg = _registry_from(monkeypatch, roles)
    monkeypatch.setattr(main, "registry", reg)
    with TestClient(main.app) as client:
        body = client.get("/api/health").json()
    assert body["status"] == "ok", body
    assert body["llm_entry_count"] == 1, body
    assert body["llm_entry_rejected"] == 2, body
    assert body["llm_entry_count"] == reg.entry_count(), "DTO 与 registry 不是同一份读数 ⇒ 计数会变成第二处真源"


def test_r2_entry_and_skipped_counts_survive_a_reload(monkeypatch):
    """计数读数不许是构造期快照：`_load` 重跑（reload/热切换）后必须跟着变，
    否则「0 条」会在某一次重载之后被旧数字盖掉。"""
    reg = _registry_from(monkeypatch, [_role("voice_chat"), _role("voice_timeout", timeout="abc")])
    assert (reg.entry_count(), reg.skipped_count()) == (1, 1)
    import settings as _s

    monkeypatch.setattr(_s.settings, "llm_models_json", json.dumps(_r2_all_bad_roles()))
    reg._load()
    assert (reg.entry_count(), reg.skipped_count()) == (0, len(_r2_all_bad_roles()))


def test_load_does_not_swallow_the_real_failure_shapes():
    """尺子的反向腿：`_load` 只降级**配置类**异常（RuntimeError/ValueError），
    别的异常（例如 entry 结构写错成 `KeyError` 之外的人为 bug）不许被一起吞掉。
    """
    src = textwrap.dedent(inspect.getsource(llm_registry.LLMRegistry._load))
    source = ast.unparse(ast.parse(src))
    caught = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Tuple):
            caught |= {e.id for e in node.type.elts if isinstance(e, ast.Name)}
        elif isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name):
            caught.add(node.type.id)
    assert {"RuntimeError", "ValueError"} <= caught, (source, caught)
    assert "Exception" not in caught, "`except Exception` 会把真 bug 也一起降级 ⇒ 本条不许出现"
