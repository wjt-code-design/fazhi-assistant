#!/usr/bin/env bash
# 全量基准一键复跑（组4 复跑基建）。
# 用法：cd backend && bash scripts/bench_all.sh [--skip-llm]
#   --skip-llm：跳过耗配额的 LLM 评测（只跑离线/轻量的检索、鲁棒、趋势）
# 注意：
#   - 需后端运行（python manage.py start）——chat 类脚本走真实 API
#   - 每脚本独立进程会重复加载 BGE/qwen（一次性基准可接受）
#   - 脚本内部 sleep≥1.0 + 429 递增退避（_client 模块，60/min 限流）
set -euo pipefail
cd "$(dirname "$0")/.."

SKIP_LLM=0
[ "${1:-}" = "--skip-llm" ] && SKIP_LLM=1

echo "=== 检索（离线）==="
./venv/Scripts/python.exe scripts/eval_retrieval.py

echo "=== 措辞鲁棒（离线，零 LLM）==="
./venv/Scripts/python.exe scripts/eval_robustness.py

if [ "$SKIP_LLM" = "0" ]; then
  echo "=== 幻觉/自检（28 例真实 LLM）==="
  ./venv/Scripts/python.exe scripts/eval_hallucination.py
  echo "=== faithfulness（28 例 ×2 调用）==="
  EVAL_LLM_JUDGE=1 ./venv/Scripts/python.exe scripts/eval_quality.py
  echo "=== 相关性（10 例）==="
  ./venv/Scripts/python.exe scripts/eval_relevance.py
  echo "=== 一致性（10 题 ×2）==="
  ./venv/Scripts/python.exe scripts/eval_consistency.py
  echo "=== 红队（10 例）==="
  ./venv/Scripts/python.exe scripts/eval_redteam.py
  echo "=== 弃答率（eval_negative 15 例）==="
  ./venv/Scripts/python.exe scripts/eval_negative_run.py
  echo "=== 限流冒烟（node，落盘物证）==="
  node scripts/bench_rate_429.mjs
  echo "=== 端到端时延（node 口径）==="
  node scripts/bench_latency.mjs
else
  echo "（--skip-llm：跳过 LLM 评测）"
fi

echo "=== 服务端时延（日志统计）==="
./venv/Scripts/python.exe scripts/eval_latency_log.py

echo "=== 趋势对比 ==="
./venv/Scripts/python.exe scripts/benchmark_trend.py

echo "全部完成。结果在 docs/benchmark_results/（趋势见 trend_*.json）"
