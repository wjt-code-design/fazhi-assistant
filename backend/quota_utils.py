"""工具配额统一实现（ADR-011 阶段E + code-review 收敛，2026-08-04）。

叶子模块：仅依赖 settings + quota_store，**不 import llm_registry**——后者模块级
`registry = LLMRegistry()` 需 LLM key，离线脚本（eval/rebuild）无 key 会崩，故扣减
一律经本模块。token 估算唯一实现在此（retrieval/llm_registry/rebuild 均改引此）。

口径：真实已用 = 配置 initial_used + 运行期 quota_store 累计（restart 不丢）。
"""

from __future__ import annotations

import quota_store
from settings import settings


def estimate_tokens(text: str) -> int:
    """中文 token 近似（云端 embedding/rerank 无真实 usage）：约 1.5 字符 / token。"""
    return max(1, int(len(text or "") / 1.5))


def _split_csv(v: str) -> list[str]:
    return [s.strip() for s in v.split(",") if s.strip()]


def rerank_model_list() -> list[str]:
    """rerank 轮换序列（settings.rerank_models，逗号分隔；空则回落单模型 rerank_model）。"""
    models = _split_csv(settings.rerank_models)
    return models or ([settings.rerank_model] if settings.rerank_model else [])


def utility_quota_total_for(key: str) -> int:
    """某配额 key 的总量：embedding → embedding_quota_total；rerank 模型 → 按
    rerank_quota_totals 对齐（缺失项回落 rerank_quota_total）；未知名 → rerank_quota_total。"""
    if key == "embedding":
        return settings.embedding_quota_total
    models = rerank_model_list()
    if key in models:
        totals = _split_csv(settings.rerank_quota_totals)
        i = models.index(key)
        if i < len(totals):
            try:
                return int(totals[i])
            except ValueError:
                pass
    return settings.rerank_quota_total


def _quota_total(name: str) -> int:
    return utility_quota_total_for(name)


def _quota_initial(name: str) -> int:
    return settings.embedding_quota_initial if name == "embedding" else settings.rerank_quota_initial


def deduct_utility(name: str, tokens: int) -> None:
    """按 key 累计扣减并持久化（key = embedding / rerank 模型名）。tokens<=0 / 空 key /
    未启用配额（total<=0）→ no-op。"""
    if tokens <= 0 or not name:
        return
    if utility_quota_total_for(name) <= 0:
        return  # 未启用配额监控，不积累
    quota_store.record_delta(name, int(tokens))


def utility_pct_left(name: str) -> float:
    """剩余比例 0..1；未启用（total<=0）→ 1.0（视为充足）。"""
    total = utility_quota_total_for(name)
    if total <= 0:
        return 1.0
    used = _quota_initial(name) + quota_store.get_used(name)
    return max(0.0, min(1.0, (total - used) / total))


def utility_quota_ok(name: str, hard: float) -> bool:
    """剩余比例 >= hard 视为可用（hard 传 settings.*_hard_threshold；0 表示必须未耗尽）。"""
    return utility_pct_left(name) >= hard


def utility_depleted(name: str) -> bool:
    """真实耗尽（剩余 <= 0）；未启用配额（total<=0）→ False（不限制）。"""
    total = utility_quota_total_for(name)
    if total <= 0:
        return False
    used = _quota_initial(name) + quota_store.get_used(name)
    return used >= total


class UtilityQuotaExhausted(Exception):
    """embedding 配额耗尽（provider=aliyun 且剩余<=0）：明确报错而非静默降级/放任 429。

    main.py 捕获转 409，提示换班或切回本地。包装对象 embed 前检查并抛出。
    """
