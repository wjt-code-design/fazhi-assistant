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
