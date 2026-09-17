$ErrorActionPreference = 'Continue'
$evidencePath = $PSScriptRoot
$projectPath = Split-Path (Split-Path $evidencePath -Parent) -Parent
Set-Location (Join-Path $projectPath 'backend')
$env:JWT_SECRET = 'test-jwt-secret-for-ci-only'
$env:LLM_API_KEY = 'test-key-not-for-real-calls'
$env:ZHIPUAI_API_KEY = 'test-key-not-for-real-calls'
$env:DASHSCOPE_API_KEY = 'test-key-not-for-real-calls'
$env:LLM_BASE_URL = 'http://127.0.0.1:9/v1'
$env:ZHIPU_BASE_URL = 'http://127.0.0.1:9/v1'
$env:DASHSCOPE_BASE_URL = 'http://127.0.0.1:9/v1'
$env:LLM_MODELS_JSON = ' '
$env:EMBEDDING_PROVIDER = 'local'
$env:RERANK_ENABLED = 'false'
$env:EMBEDDING_QUOTA_TOTAL = '0'
$env:RERANK_QUOTA_TOTAL = '0'
$env:FEATURE_SELF_REGISTER = 'true'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:DATABASE_URL = 'sqlite:///' + (Join-Path $evidencePath 'test-app.sqlite').Replace('\', '/')
$env:QUOTA_DB = Join-Path $evidencePath 'test-quota.sqlite'
$env:COVERAGE_FILE = Join-Path $evidencePath 'candidate.coverage'
$env:PYTEST_ADDOPTS = ''
& .\venv\Scripts\python.exe -m pytest -m 'not slow' --cov=. --cov-fail-under=70 -q --junitxml="$evidencePath/full-junit.xml" *> "$evidencePath/full-tests.txt"
$testExit = $LASTEXITCODE
Set-Content "$evidencePath/full-tests.exit.txt" $testExit
Get-Content "$evidencePath/full-tests.txt" -Tail 50
exit $testExit
