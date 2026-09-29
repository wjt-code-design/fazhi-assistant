"""B 档运行时探针：把依赖漏洞公告的入口桩成计数器，用运行时读数替代「静态 grep 0 命中」。

每个目标给三态之一：
  NEVER-IMPORTED —— 承载该能力的模块在整个运行里从未被 import（由 import 监视器回答，不靠 grep）；
  ZERO-CALL      —— 模块在场、桩已装上，运行期 0 次调用；
  N-CALLS        —— 有调用，并记录调用方 file:line、次数与实参摘要。

铁律：仪器绝不主动 import 被测模块。一旦自己把它导进来，「从未被导入」这条读数就作废了。
解析只用 sys.modules；未在场的模块交给 meta_path 后置钩子，等它真被 import 时再打桩。

用法：
  python b_runtime_probe.py selfcheck[|--break <tid>]     # 正对照 + 三类负向自证
  PROBE_MODE=pytest python -m pytest -p b_runtime_probe    # 全量测试内挂桩
  python b_runtime_probe.py dump                            # 打印当前进程读数

真实库、共享 venv、凭据都不在本脚本作用域内；调用方负责把环境变量指向副本。
"""

from __future__ import annotations

import functools
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CAND = Path(os.environ.get("PROBE_CAND", r"C:/Users/33393/.codex/worktrees/local-candidate-closeout/ai-legal-helper"))
OUT_PATH = Path(os.environ.get("PROBE_OUT", str(HERE / "b-probe-readings.json")))
SKIP_TARGETS = {s for s in os.environ.get("PROBE_SKIP", "").split(",") if s}

# --------------------------------------------------------------------------- 目标表
# dotted 是属性路径；owner 是**人工声明**的「这个符号住在哪个模块」，因为没被 import 时无法靠解析得知。
# NEVER-IMPORTED 这条读数只问 owner 在不在场，不问包根 —— 包根在场是废话，langchain_community 总在。
TARGETS: list[dict[str, Any]] = [
    dict(
        id="G1a",
        group="G1_Core 反序列化",
        cves="CVE-2025-68664 / CVE-2026-44843",
        dotted="langchain_core.load.load",
        owner="langchain_core.load.load",
        inert=("<not-json>",),
    ),
    dict(
        id="G1b",
        group="G1_Core 反序列化",
        cves="CVE-2025-68664 / CVE-2026-44843",
        dotted="langchain_core.load.loads",
        owner="langchain_core.load.load",
        inert=("<not-json>",),
    ),
    dict(
        id="G1c",
        group="G1_Core 反序列化",
        cves="CVE-2025-65106 / CVE-2026-40087",
        dotted="langchain_core.prompts.load_prompt",
        owner="langchain_core.prompts.loading",
        inert=("__probe_missing_file__",),
    ),
    dict(
        id="G1d",
        group="G1_Core 反序列化",
        cves="CVE-2026-34070",
        dotted="langchain_core.prompts.loading.load_prompt_from_config",
        owner="langchain_core.prompts.loading",
        inert=({"_probe": "not-a-config"},),
    ),
    dict(
        id="G1e",
        group="G1_Core 反序列化",
        cves="CVE-2025-65106（模板暴露面，非漏洞本身）",
        dotted="langchain_core.prompts.PromptTemplate.from_template",
        owner="langchain_core.prompts.prompt",
        inert=(123,),
    ),
    dict(
        id="G1f",
        group="G1_Core 反序列化",
        cves="CVE-2025-65106（模板暴露面，非漏洞本身）",
        dotted="langchain_core.prompts.ChatPromptTemplate.from_messages",
        owner="langchain_core.prompts.chat",
        inert=("<bad>",),
    ),
    dict(
        id="G1g",
        group="G1_Core 反序列化",
        cves="CVE-2026-44843（序列化写出面）",
        dotted="langchain_core.load.dumps",
        owner="langchain_core.load.dump",
        inert=(),
    ),
    # G2 图片 token 计数（SSRF / DNS 重绑定）
    dict(
        id="G2a",
        group="G2_图片 token 计数",
        cves="CVE-2026-26013 / CVE-2026-41488",
        dotted="langchain_openai.chat_models.base.ChatOpenAI.get_num_tokens_from_messages",
        owner="langchain_openai.chat_models.base",
        inert=(),
    ),
    dict(
        id="G2b",
        group="G2_图片 token 计数",
        cves="CVE-2026-26013 / CVE-2026-41488（基类）",
        dotted="langchain_core.language_models.chat_models.BaseChatModel.get_num_tokens_from_messages",
        owner="langchain_core.language_models.base",
        inert=(),
    ),
    dict(
        id="G2c",
        group="G2_图片 token 计数",
        cves="CVE-2026-26013（相邻纯文本计数面）",
        dotted="langchain_core.language_models.base.BaseLanguageModel.get_num_tokens",
        owner="langchain_core.language_models.base",
        inert=(),
    ),
    # G3 Transformers 模型 config（代码执行）
    dict(
        id="G3a",
        group="G3_Transformers 模型加载",
        cves="CVE-2026-4372 / CVE-2026-5241",
        dotted="transformers.PreTrainedModel.from_pretrained",
        owner="transformers.modeling_utils",
        inert=(),
    ),
    dict(
        id="G3b",
        group="G3_Transformers 模型加载",
        cves="CVE-2026-4372",
        dotted="transformers.AutoConfig.from_pretrained",
        owner="transformers.models.auto.configuration_auto",
        inert=(),
    ),
    dict(
        id="G3c",
        group="G3_Transformers 模型加载",
        cves="CVE-2026-4372（config 基类实现）",
        dotted="transformers.configuration_utils.PretrainedConfig.from_pretrained",
        owner="transformers.configuration_utils",
        inert=(),
    ),
    dict(
        id="G3d",
        group="G3_Transformers 模型加载",
        cves="CVE-2025-14929（相邻 tokenizer 面）",
        dotted="transformers.PreTrainedTokenizerFast.from_pretrained",
        owner="transformers.tokenization_utils_fast",
        inert=(),
    ),
    dict(
        id="G3e",
        group="G3_Transformers 模型加载",
        cves="CVE-2026-4372（本项目实际调用者）",
        dotted="sentence_transformers.SentenceTransformer",
        owner="sentence_transformers.SentenceTransformer",
        inert=(),
    ),
    # G4 LangSmith 追踪、外部 prompt 源、未被应用引用的 loader
    dict(
        id="G4a",
        group="G4_LangSmith/外部 prompt/loader",
        cves="CVE-2026-59152",
        dotted="langsmith.middleware.TracingMiddleware",
        owner="langsmith.middleware",
        inert=(),
    ),
    dict(
        id="G4b",
        group="G4_LangSmith/外部 prompt/loader",
        cves="CVE-2026-41182 / CVE-2026-45134",
        dotted="langsmith.client.Client",
        owner="langsmith.client",
        inert=(),
    ),
    dict(
        id="G4c",
        group="G4_LangSmith/外部 prompt/loader",
        cves="CVE-2026-45134",
        dotted="langsmith.client.Client.pull_prompt",
        owner="langsmith.client",
        inert=(),
    ),  # 只 dry-run，实调用会打 Hub
    dict(
        id="G4d",
        group="G4_LangSmith/外部 prompt/loader",
        cves="CVE-2024-2965",
        dotted="langchain_community.document_loaders.sitemap.SitemapLoader",
        owner="langchain_community.document_loaders.sitemap",
        inert=(),
    ),
    dict(
        id="G4e",
        group="G4_LangSmith/外部 prompt/loader",
        cves="CVE-2025-6984",
        dotted="langchain_community.document_loaders.evernote.EverNoteLoader",
        owner="langchain_community.document_loaders.evernote",
        inert=(),
    ),
    dict(
        id="G4f",
        group="G4_LangSmith/外部 prompt/loader",
        cves="CVE-2024-5998",
        dotted="langchain_community.vectorstores.faiss.FAISS",
        owner="langchain_community.vectorstores.faiss",
        inert=(),
    ),
    dict(
        id="G4g",
        group="G4_LangSmith/外部 prompt/loader",
        cves="CVE-2024-8309",
        dotted="langchain.chains.graph_qa.cypher.GraphCypherQAChain",
        owner="langchain.chains.graph_qa.cypher",
        inert=(),
    ),
]

# 额外只问「有没有被 import」的模块，不必有可桩符号。
EXTRA_WATCH = [
    "langchain_community.document_loaders.docusaurus",
    "langchain_community.chat_models.utils",
    "langchain.chains.loading",
    "langsmith.run_logs",
    "transformers.dynamic_module_utils",
    "pickle",
    "requests",
    "urllib3",
    "httpx",
]


def _prefixes(dotted: str) -> list[str]:
    parts = dotted.split(".")
    return [".".join(parts[:cut]) for cut in range(len(parts) - 1, 0, -1)]


WATCH_MODULES = sorted(
    {m for spec in TARGETS for m in _prefixes(str(spec["dotted"]))}
    | {str(spec["owner"]) for spec in TARGETS}
    | set(EXTRA_WATCH),
    key=len,
)

NET_EVENTS = (
    "socket.connect",
    "socket.getaddrinfo",
    "http.client.connect",
    "urllib.Request",
    "subprocess.Popen",
    "os.system",
    "ctypes.dlopen",
    "compile",
)

STATE: dict[str, Any] = {
    "targets": {},
    "imports": {},
    "net": {},
    "alias_repointed": {},
    "installed_at": None,
    "audit_hooked": False,
    "sweeps": 0,
}
_MARK = "__b_probe_target__"
_ORIG_KEY = "__b_probe_orig__"


class _EchoList(list):
    """边跑边打印：进程被外部杀掉时，最后一条打印就是死点。"""

    def append(self, item: object) -> None:  # type: ignore[override]
        super().append(item)
        print(item, flush=True)


# --------------------------------------------------------------------------- 归属与摘要
def app_frame(skip: int = 1) -> str:
    """第一个不属于 site-packages / 本探针 / importlib 的调用方，用于「谁调的」归属。"""
    frame = sys._getframe(skip)
    while frame is not None:
        fn = (frame.f_code.co_filename or "").replace("\\", "/").lower()
        if not any(
            seg in fn for seg in ("site-packages", "/importlib", "b_runtime_probe", "_pytest", "plippy", "pluggy")
        ):
            path = Path(frame.f_code.co_filename or "")
            try:
                rel = path.resolve().relative_to(CAND.resolve()).as_posix()
            except (ValueError, OSError):
                rel = path.name
            return f"{rel}:{frame.f_lineno}"
        frame = frame.f_back
    return "<site-packages-only>"


def brief(value: Any, limit: int = 90) -> str:
    """审计事件/实参摘要：只留标量与短字符串，不落任何像凭据的东西。"""
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, (str, bytes)):
        s = value.decode("utf-8", "replace") if isinstance(value, bytes) else value
        return s[:limit]
    if isinstance(value, (tuple, list)):
        return "(" + ",".join(brief(v, 30) for v in list(value)[:4]) + ")"
    if isinstance(value, dict):
        return "{" + ",".join(sorted(str(k) for k in list(value)[:6])) + "}"
    return type(value).__name__


# --------------------------------------------------------------------------- 审计钩子
def audit_hook(event: str, args: tuple[Any, ...]) -> None:
    try:
        if event == "import":
            name = args[0] if args else ""
            if isinstance(name, str) and name in _WATCH_SET:
                rec = STATE["imports"].setdefault(name, {"count": 0, "first_caller": "", "via": "audit"})
                if rec["count"] == 0:
                    rec["first_caller"] = app_frame(3)
                rec["count"] += 1
        elif event == "urllib.Request":
            # CPython 的审计签名是 (full_url, data, headers, method)。
            # data 是请求体 —— 测试里会带账号口令与用户文本，一律不落读数；
            # headers 只取**键名**（键名不含值），足以判断"有没有带 Authorization"。
            url = brief(args[0]) if args else ""
            method = brief(args[3]) if len(args) > 3 else ""
            hkeys = ""
            if len(args) > 2 and isinstance(args[2], dict):
                hkeys = ",".join(sorted(str(k) for k in list(args[2])[:8]))
            key = f"urllib.Request :: {url} method={method} headers[{hkeys}]"
            STATE["net"][key] = STATE["net"].get(key, 0) + 1
        elif event in _NET_SET:
            if event == "compile":
                # 编译事件每导入一个模块就几十上百条，留在明细里会把真正要看的连接事件挤出截断窗口。
                STATE["compile_total"] = STATE.get("compile_total", 0) + 1
                return
            detail = "|".join(brief(a) for a in args[:3])
            key = f"{event} :: {detail}"
            STATE["net"][key] = STATE["net"].get(key, 0) + 1
    except BaseException:  # 钩子异常绝不能影响被测进程
        pass


_WATCH_SET = set(WATCH_MODULES)
_NET_SET = set(NET_EVENTS)


# --------------------------------------------------------------------------- 后置 import 钩子
class _ProbeLoader:
    def __init__(self, inner: Any, modname: str) -> None:
        self._inner = inner
        self._modname = modname

    def create_module(self, spec: Any) -> Any:
        return self._inner.create_module(spec) if hasattr(self._inner, "create_module") else None

    def exec_module(self, module: Any) -> None:
        self._inner.exec_module(module)
        rec = STATE["imports"].setdefault(self._modname, {"count": 0, "first_caller": "", "via": "finder"})
        if rec["count"] == 0:
            rec["first_caller"] = app_frame(3)
        rec["count"] += 1
        _apply_pending(self._modname)


class _ProbeFinder:
    """只给监视名单套 loader；其余模块一律返回 None 放行，绝不主动 import。"""

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        if fullname not in _WATCH_SET:
            return None
        for finder in list(sys.meta_path):
            if finder is self:
                continue
            try:
                spec = finder.find_spec(fullname, path, target)  # type: ignore[attr-defined]
            except BaseException:
                continue
            if spec is not None and getattr(spec, "loader", None) is not None:
                spec.loader = _ProbeLoader(spec.loader, fullname)
                return spec
        return None


# --------------------------------------------------------------------------- 解析与打桩
def resolve_in_sys_modules(dotted: str) -> tuple[Any, str, str, str]:
    """返回 (owner, attr, owner_module, err)。只用 sys.modules，不触发任何 import。"""
    parts = dotted.split(".")
    errs: list[str] = []
    # 特例：整条点号路径本身就是模块，且模块里有个同名类（sentence_transformers.SentenceTransformer 就是这样）。
    # 不走这条的话，包 __init__ 还在执行时 getattr(package, 'SentenceTransformer') 必然取不到，
    # 等包执行完再取又晚于第一次实例化 —— 上一场 G3e=0 就是这么漏的。
    self_mod = sys.modules.get(dotted)
    if self_mod is not None:
        obj = getattr(self_mod, parts[-1], None)
        if isinstance(obj, type) and obj.__name__ == parts[-1]:
            return self_mod, parts[-1], dotted, ""
    for cut in range(len(parts) - 1, 0, -1):
        mod_name = ".".join(parts[:cut])
        mod = sys.modules.get(mod_name)
        if mod is None:
            errs.append(f"{mod_name} 不在 sys.modules")
            continue
        obj = mod
        chain = parts[cut:-1]
        attr = parts[-1]
        ok = True
        for seg in chain:
            try:
                obj = getattr(obj, seg)
            except (AttributeError, TypeError) as exc:
                errs.append(f"{mod_name}.{seg} -> {type(exc).__name__}: {str(exc)[:60]}")
                ok = False
                break
        if ok and hasattr(obj, attr):
            return obj, attr, mod_name, ""
        errs.append(f"{mod_name}+{chain} 上无属性 {attr}")
    return None, "", "", " | ".join(errs)  # type: ignore[return-value]


def defining_location(owner: Any, attr: str) -> tuple[Any, str]:
    if isinstance(owner, type):
        for klass in owner.__mro__:
            if attr in klass.__dict__:
                return klass, f"class:{klass.__module__}.{klass.__qualname__}"
    if attr in getattr(owner, "__dict__", {}):
        return owner, f"module:{getattr(owner, '__name__', type(owner).__name__)}"
    for klass in getattr(owner, "__mro__", []):
        if attr in klass.__dict__:
            return klass, f"class:{klass.__module__}.{klass.__qualname__}"
    return owner, "unknown"


def make_counter(orig: Callable[..., Any], tid: str) -> Callable[..., Any]:
    @functools.wraps(orig)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        rec = STATE["targets"][tid]
        rec["count"] += 1
        dry = kwargs.pop("__probe_dry_run__", False)
        caller = app_frame(1)
        rec["callers"][caller] = rec["callers"].get(caller, 0) + 1
        if dry:
            rec["dry_runs"] += 1
            return "<<PROBE-DRY-RUN>>"
        if len(rec["arg_samples"]) < 4:
            rec["arg_samples"].append(
                "|".join(brief(a) for a in list(args)[:3]) + " kw=" + ",".join(sorted(kwargs)[:6])
            )
        # 公告 CVE-2026-5241 / CVE-2026-4372 判的是 trust_remote_code 的**取值**，
        # 只记键名等于没记 —— 键在场但值为 None/False 才是「不可信远程代码未放行」的证据。
        if "trust_remote_code" in kwargs:
            rec["trust_remote_code_values"].append(repr(kwargs["trust_remote_code"]))
        return orig(*args, **kwargs)

    setattr(wrapper, _MARK, tid)
    setattr(wrapper, _ORIG_KEY, orig)
    return wrapper


def apply_target(spec: dict[str, Any]) -> dict[str, Any]:
    tid = str(spec["id"])
    dotted = str(spec["dotted"])
    rec: dict[str, Any] = {
        "id": tid,
        "group": spec["group"],
        "cves": spec["cves"],
        "dotted": dotted,
        "count": 0,
        "dry_runs": 0,
        "callers": {},
        "arg_samples": [],
        "trust_remote_code_values": [],
        "install": "PENDING",
        "patched_at": "",
        "patch_shape": "",
        "owner_module": "",
        "owner_hint": str(spec.get("owner", "")),
        "present_at_install": False,
        "control": "",
    }
    STATE["targets"][tid] = rec
    if tid in SKIP_TARGETS:
        rec["install"] = "SKIPPED-BY-ENV"
        return rec
    owner, attr, owner_mod, err = resolve_in_sys_modules(dotted)
    if owner is None:
        rec["install"] = f"PENDING-UNRESOLVED :: {err[:160]}"
        return rec
    rec["owner_module"] = owner_mod
    rec["present_at_install"] = True

    target_obj = getattr(owner, attr, None)
    # 目标是类 -> 桩它的 __init__：保留类身份（不破坏 isinstance），计「有人构造了它」。
    if isinstance(target_obj, type) and target_obj.__name__ == attr:
        defining = target_obj
        for base in target_obj.__mro__:
            if "__init__" in base.__dict__:
                defining = base
                break
        raw_init = defining.__dict__["__init__"]
        if getattr(raw_init, _MARK, None) == tid:
            rec["install"] = "INSTALLED"
            return rec
        try:
            defining.__init__ = make_counter(raw_init, tid)  # type: ignore[method-assign]
        except (TypeError, AttributeError) as exc:
            rec["install"] = f"PATCH-FAILED :: {exc}"
            return rec
        rec["patched_at"] = f"class:{defining.__module__}.{defining.__qualname__}.__init__"
        rec["patch_shape"] = "class-init-counter"
        rec["install"] = "INSTALLED"
        return rec

    holder, where = defining_location(owner, attr)
    name = attr
    raw = holder.__dict__.get(name)
    if raw is None:
        rec["install"] = f"NO-RAW-DESCRIPTOR :: {where}"
        return rec
    if (
        getattr(raw, _MARK, None) == tid
        or getattr(raw, "__func__", None) is not None
        and getattr(raw.__func__, _MARK, None) == tid
    ):
        rec["install"] = "INSTALLED"
        rec["patched_at"] = where
        return rec
    is_cm = isinstance(raw, classmethod)
    is_sm = isinstance(raw, staticmethod)
    inner = raw.__func__ if (is_cm or is_sm) else raw
    if isinstance(raw, property):
        rec["install"] = f"SKIP-PROPERTY :: {where}"
        return rec
    if not callable(inner):
        rec["install"] = f"NOT-CALLABLE :: {type(raw).__name__} at {where}"
        return rec
    payload: Any = make_counter(inner, tid)
    if is_cm:
        payload = classmethod(payload)
    elif is_sm:
        payload = staticmethod(payload)
    try:
        setattr(holder, name, payload)
    except (TypeError, AttributeError) as exc:
        rec["install"] = f"PATCH-FAILED :: {exc} at {where}"
        return rec
    rec["patched_at"] = f"{where}.{name}"
    rec["patch_shape"] = "classmethod-counter" if is_cm else "staticmethod-counter" if is_sm else "func/method-counter"
    rec["install"] = "INSTALLED"
    return rec


def _apply_target_guarded(spec: dict[str, Any]) -> None:
    """仪器绝不能弄坏宿主。上一版就是在别的模块执行中途对 transformers 包做惰性 getattr，
    触发循环 import，把 tests/test_citation.py 的收集打爆 —— 那种「0 调用」读数全是假的。"""
    tid = str(spec["id"])
    try:
        apply_target(spec)
    except BaseException as exc:
        rec = STATE["targets"].get(tid) or {}
        rec["install"] = f"APPLY-THREW :: {type(exc).__name__}: {str(exc)[:120]}"
        STATE.setdefault("apply_errors", []).append(f"{tid}: {type(exc).__name__}: {str(exc)[:120]}")


def _apply_pending(just_imported: str | None = None) -> None:
    """just_imported 给定时只补「刚执行完的那个 owner」，不在任意模块执行中途去 getattr 惰性包；
    给 None（会话收尾）时才逐只重试，且每只都带护栏。"""
    for spec in TARGETS:
        rec = STATE["targets"].get(str(spec["id"])) or {}
        if not str(rec.get("install", "")).startswith("PENDING-UNRESOLVED"):
            continue
        if just_imported is not None and str(spec.get("owner", "")) != just_imported:
            continue
        _apply_target_guarded(spec)


def sweep_aliases() -> dict[str, list[str]]:
    """把「打桩前就绑走原函数引用」的别名改指到计数器。

    按**对象身份**扫模块字典的值，不按属性名 —— `from X import y as z` 会把名字改掉，
    按名字扫就漏（自检的别名 canary 正是这个形状）。类字典是 mappingproxy 不可写，
    且本表目标都桩在定义类上，子类经 MRO 一定走到计数器，故不扫类命名空间。
    """
    found: dict[str, list[str]] = {}
    for spec in TARGETS:
        tid = str(spec["id"])
        rec = STATE["targets"].get(tid) or {}
        if rec.get("install") != "INSTALLED":
            continue
        owner, a, _mod, _err = resolve_in_sys_modules(str(spec["dotted"]))
        if owner is None:
            continue
        current = getattr(owner, a, None)
        while current is not None and getattr(current, "__func__", None) is not None:
            current = current.__func__
        if current is None or getattr(current, _MARK, None) != tid:
            continue
        wrapper = current
        orig = getattr(current, _ORIG_KEY, None)
        if orig is None or orig is wrapper:
            continue
        repointed: list[str] = []
        for mod in list(sys.modules.values()):
            try:
                d = mod.__dict__
            except AttributeError:
                continue
            if not isinstance(d, dict):
                continue
            name = d.get("__name__")
            for key, value in list(d.items()):
                if value is orig:
                    d[key] = wrapper
                    repointed.append(f"{name}.{key}")
        if repointed:
            found[tid] = sorted(set(repointed))[:40]
    STATE["alias_repointed"] = found
    STATE["sweeps"] += 1
    return found


def install(sweep: bool = True) -> None:
    if STATE["installed_at"] is not None:
        _apply_pending()
        if sweep:
            sweep_aliases()
        return
    if not STATE["audit_hooked"]:
        sys.addaudithook(audit_hook)
        STATE["audit_hooked"] = True
    if not any(isinstance(f, _ProbeFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, _ProbeFinder())
    for name in list(sys.modules):
        if name in _WATCH_SET and name not in STATE["imports"]:
            STATE["imports"][name] = {"count": 0, "first_caller": "<pre-installed>", "via": "snapshot"}
    # 装桩时刻的完整性读数：若应用或模型加载器已经起来了，那它们**装桩前**的调用我看不见，
    # 这一场的 ZERO-CALL 就不能当成「运行期 0 调用」的证据。（上一场的 G3e=0 就是这么来的。）
    STATE["preloaded_app"] = sorted(
        m
        for m in (
            "rag_chain",
            "retrieval",
            "knowledge_service",
            "main",
            "sentence_transformers",
            "transformers",
            "langchain_openai",
        )
        if m in sys.modules
    )
    for spec in TARGETS:
        _apply_target_guarded(spec)
    if sweep:
        sweep_aliases()
    STATE["installed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")


# --------------------------------------------------------------------------- 读数
def owner_present(rec: dict[str, Any]) -> bool:
    """owner 模块是否在场。只看人工声明的 owner 与已解析出的 owner，不看包根。"""
    candidates = [rec.get("owner_module") or "", rec.get("owner_hint") or ""]
    return any(c and (c in sys.modules or c in STATE["imports"]) for c in candidates)


def verdict_of(rec: dict[str, Any]) -> str:
    if rec["install"] == "SKIPPED-BY-ENV":
        return "SKIPPED-BY-ENV"
    if str(rec["install"]).startswith("INSTALLED"):
        if rec["count"] > 0:
            real = rec["count"] - rec["dry_runs"]
            return f"{real}-CALLS" if real else "ZERO-CALL(dry-run only)"
        return "ZERO-CALL"
    if owner_present(rec):
        return f"NOT-INSTRUMENTED :: {str(rec['install'])[:70]}"
    return "NEVER-IMPORTED"


def snapshot(mode: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    targets = sorted(STATE["targets"].values(), key=lambda r: r["id"])
    for rec in targets:
        rec["verdict"] = verdict_of(rec)
    payload: dict[str, Any] = {
        "probe": "b_runtime_probe",
        "mode": mode,
        "candidate_tree": str(CAND),
        "interpreter": sys.executable,
        "python": sys.version.split()[0],
        # 读数必须自带"是哪套 pytest 跑出来的"：O-6 那轮在同一棵树上换过框架版本，
        # compile 事件总数随版本变（8.4.2=9826 / 9.1.1=9830）。不落这个字段，两个版本的答案会被读成同一场。
        "pytest_version": getattr(sys.modules.get("pytest"), "__version__", None),
        "targets": targets,
        "imports_watched": STATE["imports"],
        "net_events": dict(sorted(STATE["net"].items(), key=lambda kv: (-kv[1], kv[0]))[:400]),
        "net_event_kinds": len(STATE["net"]),
        "net_event_total": sum(STATE["net"].values()),
        "compile_event_total": STATE.get("compile_total", 0),
        "alias_repointed": STATE["alias_repointed"],
        "apply_errors": STATE.get("apply_errors", []),
        "sweeps": STATE["sweeps"],
        "installed_at": STATE["installed_at"],
        "preloaded_app_at_install": STATE.get("preloaded_app", []),
        "watch_modules": WATCH_MODULES,
    }
    if extra:
        payload.update(extra)
    return payload


def dump(mode: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = snapshot(mode, extra)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(str(OUT_PATH), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return payload


# --------------------------------------------------------------------------- 自检
def control_dry_run(rec: dict[str, Any]) -> str:
    """哨兵关键字走同一条属性路径：证明派发确实命中我的桩，且不执行真实副作用。"""
    owner, attr, _mod, err = resolve_in_sys_modules(rec["dotted"])
    if owner is None:
        return f"DRY-UNRESOLVED :: {err[:60]}"
    before = rec["count"]
    try:
        getattr(owner, attr)(**{"__probe_dry_run__": True})
    except BaseException as exc:
        if rec["count"] > before:
            return "DRY-OK(via raise)"
        return f"DRY-NO-COUNT :: {type(exc).__name__}: {str(exc)[:60]}"
    return "DRY-OK" if rec["count"] > before else "DRY-NO-COUNT"


def control_real_call(rec: dict[str, Any]) -> str:
    spec = next(s for s in TARGETS if s["id"] == rec["id"])
    inert = tuple(spec.get("inert") or ())
    if not inert:
        return "REAL-SKIPPED(no inert argset)"
    owner, attr, _mod, err = resolve_in_sys_modules(rec["dotted"])
    if owner is None:
        return f"REAL-UNRESOLVED :: {err[:60]}"
    before = rec["count"]
    try:
        getattr(owner, attr)(*inert)
    except BaseException:
        pass
    return "REAL-OK" if rec["count"] > before else "REAL-NO-COUNT(死仪器)"


# 自检专用的模块预导入。**只用于自检**：仪器必须先有东西可桩，才谈得上证明它有牙。
# 测量运行（pytest 插件模式、app 模式）绝不引用这份清单，那两种模式只报告现场事实。
SELFCHECK_BOOTSTRAP = [
    "langchain_core.load",
    "langchain_core.load.load",
    "langchain_core.prompts",
    "langchain_core.prompts.loading",
    "langchain_core.language_models.chat_models",
    "langchain_core.language_models.base",
    "langsmith.client",
    "langsmith.middleware",
    "langchain_openai.chat_models.base",
    "sentence_transformers",
    "transformers",
    "transformers.modeling_utils",
    "transformers.configuration_utils",
]
# 自检里「迟到的 import」正对照用（证明 meta_path 后置钩子能装上桩）
LATE_IMPORT_MODULE = "langchain_community.document_loaders.evernote"
# 自检里保持缺席、用来证明 NEVER-IMPORTED 形态读数的模块
DELIBERATELY_ABSENT_MODULE = "langchain_community.vectorstores.faiss"


def selfcheck(break_tid: str = "") -> int:
    global SKIP_TARGETS
    if break_tid:
        SKIP_TARGETS = {break_tid}
    import importlib

    failures: list[str] = []
    lines: list[str] = _EchoList()

    # 别名盲区：在装桩之前就把原函数引用绑走
    import b_probe_alias_canary as canary

    lines.append("== stage: 预导入（仅自检模式，测量模式不做）")
    for name in SELFCHECK_BOOTSTRAP:
        try:
            importlib.import_module(name)
            lines.append(f"  import ok  {name}")
        except BaseException as exc:
            failures.append(f"自检预导入失败 {name}: {type(exc).__name__}: {str(exc)[:80]}")
            lines.append(f"  import FAIL {name}: {type(exc).__name__}")
    lines.append("== stage: install(sweep=False) —— 先只打桩，不给别名补钉，才能量出盲区")
    install(sweep=False)
    installed_n = sum(1 for r in STATE["targets"].values() if str(r["install"]).startswith("INSTALLED"))
    lines.append(f"== stage: installed, 桩 {installed_n}/{len(TARGETS)}")

    # 对照 A：别名遮蔽确实存在（差分左腿），且 sweep 能补上（差分右腿）
    tid_alias = "G1b"
    before = STATE["targets"][tid_alias]["count"]
    try:
        canary.call_via_alias()
    except BaseException:
        pass
    blind = STATE["targets"][tid_alias]["count"] - before
    sweep_aliases()
    try:
        canary.call_via_alias()
    except BaseException:
        pass
    seen = STATE["targets"][tid_alias]["count"] - before
    aliases = STATE["alias_repointed"].get(tid_alias, [])
    lines.append(f"  别名盲区对照 -> 遮蔽期 +{blind}（应为 0），sweep 之后累计 +{seen}（应 >=1）；别名表 {aliases}")
    if blind != 0:
        failures.append(f"别名差分不成立：遮蔽期就有 +{blind} 计数，这条对照没有区分力（读数不能算证）")
    if seen < 1:
        failures.append("别名 sweep 无牙：打桩前绑走的引用仍然看不见")

    # 对照 B：迟到的 import 能被后置钩子装上桩
    try:
        importlib.import_module(LATE_IMPORT_MODULE)
    except BaseException as exc:
        failures.append(f"迟到 import 正对照失败: {type(exc).__name__}: {str(exc)[:80]}")
    late = STATE["targets"].get("G4e") or {}
    lines.append(
        f"  迟到 import 对照 -> {LATE_IMPORT_MODULE} 记录={LATE_IMPORT_MODULE in STATE['imports']} "
        f"G4e install={late.get('install')} shape={late.get('patch_shape')}"
    )
    if not str(late.get("install", "")).startswith("INSTALLED"):
        failures.append("后置钩子没能在迟到 import 后装上桩")

    # 对照 C：故意保持缺席的模块应读成 NEVER-IMPORTED
    absent = STATE["targets"].get("G4f") or {}
    lines.append(f"  缺席形态对照 -> G4f（{DELIBERATELY_ABSENT_MODULE}）verdict={verdict_of(absent)}")
    if verdict_of(absent) != "NEVER-IMPORTED":
        failures.append(f"缺席模块未读成 NEVER-IMPORTED，而是 {verdict_of(absent)}（读数会把仪器缺陷伪装成结论）")

    # 正对照：每只装上的桩，走同一条属性路径必须增量
    lines.append("== stage: 正对照循环")
    for tid, rec in sorted(STATE["targets"].items()):
        if rec["install"] == "SKIPPED-BY-ENV":
            lines.append(f"  {tid} SKIPPED-BY-ENV  <- 负向自证形态：桩被刻意撤走，闸门必须为此变红")
            failures.append(f"{tid}: 桩被 PROBE_SKIP/--break 撤走，该目标不可信（计数={rec['count']}）")
            continue
        if not str(rec["install"]).startswith("INSTALLED"):
            v = verdict_of(rec)
            lines.append(f"  {tid} {v} :: {str(rec['install'])[:70]}")
            if v != "NEVER-IMPORTED":
                failures.append(f"{tid}: owner 模块在场却没桩上 -> {rec['install']}")
            continue
        dry = control_dry_run(rec)
        real = control_real_call(rec)
        rec["control"] = f"{dry} | {real}"
        lines.append(
            f"  {tid} count={rec['count']:3d} dry={rec['dry_runs']:2d} {rec['patch_shape']:22s} {dry:16s} {real}"
        )
        if dry.startswith("DRY-NO-COUNT") or dry.startswith("DRY-UNRESOLVED"):
            failures.append(f"{tid}: 正对照未增量（仪器是死的）-> {dry}")
        if real.startswith("REAL-NO-COUNT"):
            failures.append(f"{tid}: 实调用对照未增量 -> {real}")

    # 归属干净：未被桩化的普通调用不该产生任何目标计数
    base_total = sum(r["count"] for r in STATE["targets"].values())
    import json as _json

    _json.dumps({"x": 1})
    os.getcwd()
    if sum(r["count"] for r in STATE["targets"].values()) != base_total:
        failures.append("未桩化的标准库调用被计进了目标计数（归属不干净）")

    # 网络审计有牙：对环回不可用端口 9 发三种连接，必须被审计到
    import http.client
    import socket
    import urllib.request

    for attempt in (
        lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("127.0.0.1", 9)),
        lambda: http.client.HTTPConnection("127.0.0.1", 9, timeout=0.5).request("GET", "/nope"),
        lambda: urllib.request.urlopen("http://127.0.0.1:9/nope", timeout=0.5),
    ):
        try:
            attempt()
        except BaseException:
            pass
    net_kinds = sorted(
        k.split(" :: ")[0]
        for k in STATE["net"]
        if k.split(" :: ")[0] in ("socket.connect", "http.client.connect", "urllib.Request", "socket.getaddrinfo")
    )
    if not net_kinds:
        failures.append("网络审计层 0 事件：运行时的「无外联」读数不可信")
    lines.append(f"  网络审计负向自证 -> {len(net_kinds)} 类事件被记录（环回端口 9）: {sorted(set(net_kinds))}")

    installed = sum(1 for r in STATE["targets"].values() if str(r["install"]).startswith("INSTALLED"))
    lines.append(f"  桩装上 {installed}/{len(TARGETS)}；import 监视在场 {len(STATE['imports'])} 个模块")

    if break_tid:
        rec = STATE["targets"].get(break_tid) or {}
        if rec.get("count", 0) != 0:
            failures.append(f"PROBE_SKIP={break_tid} 却仍有 {rec['count']} 次计数")
        else:
            lines.append(f"  SKIP 负向自证 -> {break_tid} 计数恒为 0，说明计数不是编出来的")

    lines.append("== stage: 写读数 -> " + str(OUT_PATH))
    dump("selfcheck", extra={"failures": failures, "break_tid": break_tid, "control_lines": list(lines)})
    if failures:
        print(f"\nSELFCHECK FAIL ({len(failures)})")
        for f in failures:
            print("  - " + f)
        return 1
    print("\nSELFCHECK PASS")
    return 0


# --------------------------------------------------------------------------- pytest 插件
def pytest_configure(config: Any) -> None:
    install()


# 最早的装桩时刻：`-p b_runtime_probe` 在 rootdir conftest 之前就把本模块导了进来。
# 等到 pytest_configure 才装会给「装桩前的调用」留盲区 —— 上一场 G3e=0 而同一处的 from_pretrained=1
# 就是这个自相矛盾的信号。装桩后 preloaded_app 读数应为空，非空则本场 ZERO-CALL 不作证据。
if os.environ.get("PROBE_MODE") == "pytest":
    install()


def pytest_sessionfinish(session: Any, exitstatus: Any) -> None:
    _apply_pending()
    sweep_aliases()
    payload = dump(
        "pytest-suite", extra={"pytest_exitstatus": int(exitstatus), "collected": int(session.testscollected or 0)}
    )
    tally = {r["id"]: r["verdict"] for r in payload["targets"]}
    print(
        f"\n[B-PROBE] installed={sum(1 for r in payload['targets'] if str(r['install']).startswith('INSTALLED'))}"
        f"/{len(payload['targets'])} verdicts={tally} watched-imports={len(payload['imports_watched'])}"
        f" net-kinds={payload['net_event_kinds']} total={payload['net_event_total']}"
    )


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "selfcheck":
        tid = ""
        if len(argv) > 2 and argv[1] == "--break":
            tid = argv[2]
        return selfcheck(tid)
    if argv[0] == "dump":
        _apply_pending()
        print(json.dumps(snapshot("dump"), ensure_ascii=False, indent=2, sort_keys=True)[:6000])
        return 0
    print(f"unknown mode: {argv[0]}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
