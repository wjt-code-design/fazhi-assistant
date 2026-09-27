#!/usr/bin/env bash
# Second-pass check: does the T1 replacement change the project's own citation gate?
# Runs scripts/smoke_citation_fast.py against BOTH private copies (pristine vs already-imported).
set -u
REPO=/c/Users/33393/Desktop/ai-legal-helper
PY=$REPO/backend/venv/Scripts/python.exe
T=/c/Users/33393/AppData/Local/Temp/vsr-review-20260927

for STATE in pristine imported; do
  if [ "$STATE" = pristine ]; then DIR="$T/chroma_pristine"; else DIR="$T/chroma_db"; fi
  cd "$REPO/backend" || exit 9
  CHROMA_DIR="$DIR" DATABASE_URL="sqlite:///$T/smoke_$STATE.db" EMBEDDING_PROVIDER=local \
  RERANK_ENABLED=false JWT_SECRET="vsr-ci-only" LLM_API_KEY="not-for-real-calls" \
  LLM_BASE_URL="http://127.0.0.1:9/v1" "$PY" -B scripts/smoke_citation_fast.py > "$T/smoke_$STATE.out" 2>&1
  echo "SMOKE_${STATE}_RC=$?"
  grep -E "^(ALL OK|FAIL|通过|[0-9]+/[0-9]+)" "$T/smoke_$STATE.out" | tr -d '\r' | tail -4
  grep -c "\[FAIL\]" "$T/smoke_$STATE.out" | tr -d '\n' | sed "s/^/ ${STATE}_fail_lines=/"
  echo ""
done
echo "SMOKE_DONE"
