"""P3 harness env plumbing. Owner-authorized 2026-10-12: read ONLY the named keys from
backend/.env, inject into the child process env, never print values (names/lengths only).

Task book F1: config must come from the process environment; if absent, report the names.
The Owner explicitly authorized this read as an exception; it is recorded in the report.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

RUN_ROOT = Path(__file__).resolve().parents[2]
PRIVATE = RUN_ROOT / "model-validation" / "p3-20261012"
MAIN_REPO = Path("C:/Users/33393/Desktop/ai-legal-helper")
ENV_FILE = MAIN_REPO / "backend" / ".env"

# 只取这些键（值不进日志/不进上下文）
WANTED = (
    "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_MODELS_JSON",
    "RERANK_API_KEY", "RERANK_BASE_URL", "RERANK_ENABLED", "RERANK_MODEL", "RERANK_MODELS",
    "EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "EMBEDDING_API_KEY",
    "DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "ZHIPUAI_API_KEY", "SILICONFLOW_API_KEY",
)


def read_env(path: Path = ENV_FILE) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k in WANTED:
            out[k] = v.strip().strip('"').strip("'")
    return out


BIG_ROOT = Path(os.environ.get("P3_BIG_ROOT", "D:/fazhi-big/p3-20261012"))
# Owner 10-12: 别让 C 盘爆（现量 C 剩 15G / 97% used），781MB 的 BGE 缓存放 D 盘私有根。
MODEL_CACHE = Path(os.environ.get("P3_MODEL_CACHE", str(BIG_ROOT / "model-cache")))

def _frozen_hosts() -> dict[str, tuple[str, ...]]:
    """单一真源：白名单从冻结配置推导，不在第二处重抄。"""
    cfg = json.loads((PRIVATE / "p3_models_frozen.json").read_text(encoding="utf-8"))
    out: dict[str, set[str]] = {}
    for block in cfg.values():
        if not isinstance(block, dict):
            continue
        url = block.get("base_url") or block.get("rerank_base_url")
        if not url or not url.startswith("https://"):
            continue
        rest = url[len("https://"):]
        host, _, path = rest.partition("/")
        out.setdefault(host, set()).add("/" + path.strip("/"))
    return {host: tuple(sorted(paths)) for host, paths in sorted(out.items())}


MODEL_HOSTS = _frozen_hosts()


def bind_private_root(env: dict[str, str] | None = None, *, embedding_offline: bool = True) -> dict[str, str]:
    """五个私有出口 + HF 三个缓存全指本轮私有根（Task book F1 第二 bullet）。"""
    target = dict(env or {})
    data = PRIVATE / "data"
    data.mkdir(parents=True, exist_ok=True)
    (PRIVATE / "logs").mkdir(parents=True, exist_ok=True)
    MODEL_CACHE.mkdir(parents=True, exist_ok=True)
    target.update({
        "DATABASE_URL": "sqlite:///" + str(data / "app.db").replace("\\", "/"),
        "QUOTA_DB": str(data / "quota.sqlite"),
        "CHROMA_DIR": str(PRIVATE / "chroma-public"),
        "HF_HOME": str(MODEL_CACHE),
        "HF_HUB_CACHE": str(MODEL_CACHE / "hub"),
        "HF_MODULES_CACHE": str(MODEL_CACHE / "modules"),
        # rag_chain 默认离线；knowledge_base 会显式改成 0 走 hf-mirror 校验。
        # 本轮先把 rag_chain 导在前面（模型已加载），再导 knowledge_base，取零出网。
        "HF_HUB_OFFLINE": "1" if embedding_offline else "0",
        "TRANSFORMERS_OFFLINE": "1" if embedding_offline else "0",
        # chromadb 的埋点在 rag_chain import 期就发生（早于 socket 守卫），
        # 所以把"不外发"做成构造性质而不是靠测量那段窗口。
        "ANONYMIZED_TELEMETRY": "False",
        "CHROMA_TELEMETRY_IMPL": "chromadb.telemetry.product.posthog.NoopTelemetry",
    })
    return target


def describe(env: dict[str, str]) -> list[str]:
    """只报键名与长度；绝不返回值。"""
    return ["%-22s %s" % (k, ("len=%d" % len(v)) if v else "EMPTY") for k, v in sorted(env.items())]


if __name__ == "__main__":
    e = read_env()
    print("keys found (name only):")
    for line in describe(e):
        print("  " + line)
    b = bind_private_root()
    print("private outlets:")
    for k in ("DATABASE_URL", "QUOTA_DB", "CHROMA_DIR", "HF_HOME", "HF_HUB_OFFLINE"):
        print("  %-16s %s" % (k, b.get(k)))
    print("frozen allow-list (host + path prefix, no secrets):")
    for host, paths in MODEL_HOSTS.items():
        print("  %s -> %s" % (host, ", ".join(paths)))
