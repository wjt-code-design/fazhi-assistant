#!/usr/bin/env bash
# H1 候选离线验收（隔离环境，复刻第一轮 verify.ps1 的口径；输出到本轮专属目录，不覆盖旧证据）
EX="C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/agent-timeout-h1-20260912"
cd "C:/Users/33393/Desktop/ai-legal-helper/backend" || exit 1

export JWT_SECRET='test-jwt-secret-for-ci-only'
export LLM_API_KEY='test-key-not-for-real-calls'
export ZHIPUAI_API_KEY='test-key-not-for-real-calls'
export DASHSCOPE_API_KEY='test-key-not-for-real-calls'
export LLM_BASE_URL='http://127.0.0.1:9/v1'
export ZHIPU_BASE_URL='http://127.0.0.1:9/v1'
export DASHSCOPE_BASE_URL='http://127.0.0.1:9/v1'
export LLM_MODELS_JSON=' '
export EMBEDDING_PROVIDER='local'
export RERANK_ENABLED='false'
export EMBEDDING_QUOTA_TOTAL='0'
export RERANK_QUOTA_TOTAL='0'
export FEATURE_SELF_REGISTER='true'
export HF_HUB_OFFLINE='1'
export TRANSFORMERS_OFFLINE='1'
export DATABASE_URL="sqlite:///$EX/test-app.sqlite"
export QUOTA_DB="$EX/test-quota.sqlite"
export COVERAGE_FILE="$EX/candidate.coverage"
export PYTEST_ADDOPTS=''

./venv/Scripts/python.exe -m pytest -m 'not slow' --cov=. --cov-fail-under=70 -q \
  --junitxml="$EX/full-junit.xml" > "$EX/full-tests.txt" 2>&1
code=$?
echo "$code" > "$EX/full-tests.exit.txt"
echo "PYTEST_EXIT=$code"
