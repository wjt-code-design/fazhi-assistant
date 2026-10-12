"""Freeze what the product's OWN registry says the current routes are (no HTTP).

Reason this exists: my first freeze read .env by hand and inferred provider->endpoint
myself, which made me report the wrong host for the registry models. Here the answer
comes from settings/llm_registry: modality, caps, tier, priority, host, built-or-skipped.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_env  # noqa: E402

CAND = Path(sys.argv[1])


def main() -> int:
    os.environ.update(p3_env.bind_private_root(p3_env.read_env()))
    sys.path.insert(0, str(CAND / "backend"))
    import llm_registry as LR  # noqa: E402
    from settings import settings  # noqa: E402

    reg = LR.LLMRegistry()
    rows = []
    for key, e in reg._entries.items():
        rows.append({
            "key": key, "model": e.model, "modality": e.modality, "tier": e.tier,
            "priority": e.priority, "caps": sorted(e.capabilities),
            "host": urlparse(e.cfg.get("base_url") or "").netloc,
            "built": e.llm is not None, "disable_thinking": bool(e.cfg.get("disable_thinking")),
            "translation_options": bool(e.cfg.get("translation_options")),
            "quota_total": e.quota_total, "initial_used": e.initial_used,
        })
    rows.sort(key=lambda r: (r["modality"], r["priority"]))
    out = {
        "roles_source": "LLM_MODELS_JSON" if (settings.llm_models_json or "").strip() else "DEFAULT_ROLES",
        "entries": rows,
        "DEFAULT_KEY": LR.DEFAULT_KEY,
        "registry_get_model": reg.get().model_name if hasattr(reg.get(), "model_name") else str(reg.get().model),
        "has_modality": {m: reg.has_modality(m) for m in ("vision", "voice", "text")},
        "env_defaults": {"llm_host": urlparse(settings.llm_base_url or "").netloc,
                         "dashscope_host": urlparse(settings.dashscope_base_url or "").netloc,
                         "zhipu_host": urlparse(settings.zhipu_base_url or "").netloc,
                         "rerank_host": urlparse(settings.rerank_base_url or "").netloc,
                         "rerank_model": settings.rerank_model, "rerank_models": list(settings.rerank_models) if isinstance(settings.rerank_models, (list, tuple)) else str(settings.rerank_models),
                         "embedding_provider": settings.embedding_provider},
        "llm_model_is_dead_config": "settings.py:40 明文：LLM_MODEL 无任何代码读取（对抗审计 v2 #12 删的死配置）",
        "thinking_switch_rule": "llm_registry._build 只在 model 名以 qwen 开头时发 thinking:disabled",
    }
    (HERE / "p3_routes_frozen.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
