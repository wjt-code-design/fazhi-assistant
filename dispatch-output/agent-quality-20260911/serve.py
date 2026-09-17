"""Isolated local evaluation host for the existing gate2_runner, not a deployment.

2026-09-12（H3）：输出目录 / 计费上限 / 端口 / 账本路径改为显式环境变量，缺省值与历史完全
一致，使同一个宿主可复用于后续 run，不必每个 run 复制一套脚本。
- EVAL_EVIDENCE_DIR：新批次证据目录（业务库、quota 库、账本、runtime-manifest 都落这里）。
- EVAL_GUARD_LIMIT：本轮 guard 上限。**必须传「累计授权额度 − 已花费」**——guard 是进程内计数，
  新进程从 0 开始，不显式扣减就等于悄悄把总授权翻倍。
- EVAL_PORT：监听端口（默认 18111）。
- EVAL_LEDGER：账本路径（默认 <EVAL_EVIDENCE_DIR>/cost-ledger.jsonl）。
"""

import hashlib
import json
import os
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BACKEND = ROOT / "backend"
EVIDENCE = Path(os.environ.get("EVAL_EVIDENCE_DIR") or HERE).resolve()
PORT = int(os.environ.get("EVAL_PORT") or 18111)
GUARD_LIMIT = os.environ.get("EVAL_GUARD_LIMIT") or "20"
LEDGER = Path(os.environ.get("EVAL_LEDGER") or (EVIDENCE / "cost-ledger.jsonl"))
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env", override=True)
os.environ.update(
    {
        "DATABASE_URL": "sqlite:///" + (EVIDENCE / "evaluation.sqlite").as_posix(),
        "QUOTA_DB": str(EVIDENCE / "quota.sqlite"),
        "JWT_SECRET": secrets.token_urlsafe(48),
        "AGENT_ENABLED": "true",
        "AGENT_SHADOW_ENABLED": "false",
        "AGENT_TRAFFIC_PERCENT": "100",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "ANONYMIZED_TELEMETRY": "false",
    }
)

from budget_guard import BudgetGuard

guard = BudgetGuard(LEDGER, limit=GUARD_LIMIT)
guard.install()

import main
import retrieval
from auth import hash_password
from database import SessionLocal, init_db
from llm_registry import registry
from models import User
from settings import settings
from tools import gateway as gateway_module

init_db()
entry = registry._default_entry()
# 2026-09-15：模型链已切换（qwen3.8-flash 移除）——断言改为**通用**：默认 entry 与链内
# 每个 text/flag 模型都必须在 budget_guard.PRICING 表内（未定价模型一律拒绝的纪律）。
from budget_guard import PRICING

assert entry and entry.cfg["model"] in PRICING, (
    f"默认模型未定价: {entry and entry.cfg['model']}"
)
for _e in registry._entries.values():
    if _e.modality == "text" and _e.llm is not None:
        assert _e.model in PRICING, f"链内模型未定价: {_e.model}"
assert settings.embedding_provider == "local"
# include_usage 注入**全部** text entry（不只默认）：换模型后仍能拿 usage 做精确结算。
for _e in registry._entries.values():
    if _e.modality == "text" and _e.llm is not None:
        _e.llm.model_kwargs = {
            **_e.llm.model_kwargs,
            "stream_options": {"include_usage": True},
        }
raw_env = {}
for line in (BACKEND / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith(("ADMIN_USERNAME=", "ADMIN_PASSWORD=")):
        key, value = line.split("=", 1)
        raw_env[key] = value.strip()  # Same parsing as the existing runner.
assert raw_env.get("ADMIN_USERNAME") and raw_env.get("ADMIN_PASSWORD")
with SessionLocal() as db:
    assert db.query(User).count() == 0
    db.add(
        User(
            username=raw_env["ADMIN_USERNAME"],
            password_hash=hash_password(raw_env["ADMIN_PASSWORD"]),
            role="admin",
        )
    )
    db.commit()


def _kb_identifier() -> dict:
    """知识库/索引版本标识：不做整库散列，只记录可比较的轻量指纹。"""
    index_dir = BACKEND / "chroma_db"
    files = (
        [p for p in index_dir.rglob("*") if p.is_file()] if index_dir.exists() else []
    )
    return {
        "index_dir": str(index_dir),
        "file_count": len(files),
        "total_bytes": sum(p.stat().st_size for p in files),
        "max_mtime": max((p.stat().st_mtime for p in files), default=None),
    }


_H3_EXTRA_FILES = [
    BACKEND / "tools" / "gateway.py",
    BACKEND / "tools" / "legal_retrieval.py",
    BACKEND / "tools" / "contracts.py",
    BACKEND / "retrieval.py",
    BACKEND / "settings.py",
]

manifest = {
    "model": entry.cfg["model"],
    "role": entry.key,
    "stream_usage": True,
    "max_steps": settings.agent_max_steps,
    "max_tool_calls": settings.agent_max_tool_calls,
    "max_replans": settings.agent_max_replans,
    "max_clarifications": settings.agent_max_clarifications,
    "max_verifier_research_returns": settings.agent_max_verifier_research_returns,
    "sdk_max_retries": entry.llm.max_retries,
    "rerank_enabled": settings.rerank_enabled,
    "rerank_model": settings.rerank_model,
    "embedding_provider": settings.embedding_provider,
    "budget_cny": GUARD_LIMIT,
    "outbound_request_limit": 60,
    "evidence_dir": str(EVIDENCE),
    "port": PORT,
    "ledger": str(LEDGER),
    "retrieval_config": {
        "rerank_enabled": settings.rerank_enabled,
        "rerank_model": settings.rerank_model,
        "rerank_base_url": settings.rerank_base_url,
        "rerank_attempt_timeout_s": retrieval._RERANK_ATTEMPT_TIMEOUT_S,
        "rerank_deadline_margin_s": retrieval._RERANK_DEADLINE_MARGIN_S,
        "gateway_retrieve_laws_timeout_s": gateway_module._POLICIES[
            "retrieve_laws"
        ].timeout_seconds,
    },
    "kb_identifier": _kb_identifier(),
    "files": {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in list((BACKEND / "agent").glob("*.py"))
        + [BACKEND / "llm_registry.py", BACKEND / "main.py"]
        + _H3_EXTRA_FILES
    },
}
(EVIDENCE / "runtime-manifest.json").write_text(
    json.dumps(manifest, indent=2), encoding="utf-8"
)
print(
    "EVALUATION_READY "
    + json.dumps({k: v for k, v in manifest.items() if k != "files"}),
    flush=True,
)

import uvicorn

uvicorn.run(main.app, host="127.0.0.1", port=PORT, access_log=False)
