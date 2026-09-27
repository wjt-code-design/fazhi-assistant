#!/usr/bin/env bash
# Full-suite differential: HEAD (base) vs working tree (patched), in private copy trees.
# Evidence for the 2026-09-27 version-safety review. Prints real rc (no pipes around rc).
set -u
REPO=/c/Users/33393/Desktop/ai-legal-helper
T=/c/Users/33393/AppData/Local/Temp/vsr-review-20260927
PY=$REPO/backend/venv/Scripts/python.exe
export MSYS_NO_PATHCONV=1

rm -rf "$T/base" "$T/patched"
mkdir -p "$T/base" "$T/patched"

cd "$REPO" || exit 9
git -c gc.auto=0 archive HEAD -- backend | tar -x -C "$T/base" || { echo "ARCHIVE_FAIL"; exit 9; }
cp -r "$T/base/backend" "$T/patched/backend_tmp" && rm -rf "$T/patched/backend" && mv "$T/patched/backend_tmp" "$T/patched/backend"

# overlay only the files the working tree changed
git diff HEAD --name-only -z > "$T/changed.z"
FILES=0
while IFS= read -r -d '' f; do
  case "$f" in
    backend/*)
      if [ -f "$REPO/$f" ]; then
        mkdir -p "$T/patched/$(dirname "$f")"
        cp "$REPO/$f" "$T/patched/$f" && FILES=$((FILES+1))
      fi
      ;;
  esac
done < "$T/changed.z"
# plus untracked new backend files (none expected this round, but list them)
git ls-files --others --exclude-standard -- backend > "$T/untracked.txt"
UT=$(wc -l < "$T/untracked.txt")
while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$f" in
    *chroma_db*|*venv*|*__pycache__*|*.ptmp*|*.coverage*|*.pytest_cache*) continue ;;
  esac
  if [ -f "$REPO/$f" ]; then
    mkdir -p "$T/patched/$(dirname "$f")"
    cp "$REPO/$f" "$T/patched/$f" && UT=$((UT))
  fi
done < "$T/untracked.txt"
echo "OVERLAID=$FILES UNTRACKED_CANDIDATES=$UT"

IGNORES="--ignore=tests/test_gate2_runner.py --ignore=tests/test_harness_fact_reveal.py --ignore=tests/test_r15_runner_injection.py"
for TREE in base patched; do
  echo "=== RUN $TREE ==="
  cd "$T/$TREE/backend" || { echo "CD_FAIL $TREE"; exit 9; }
  "$PY" -B -m pytest tests -q -rf $IGNORES > "$T/$TREE.out" 2>&1
  echo "${TREE}_RC=$?"
  grep -E "^(FAILED|ERROR) " "$T/$TREE.out" | sed 's/ - .*//' | sort > "$T/$TREE.failed"
  tail -3 "$T/$TREE.out" | tr -d '\r'
  wc -l < "$T/$TREE.failed" | tr -d ' ' | sed "s/^/$TREE_FAILED_COUNT=/"
done

cd "$T" || exit 9
echo "=== ONLY IN PATCHED (regressions) ==="
comm -13 "$T/base.failed" "$T/patched.failed"
echo "=== ONLY IN BASE (fixed/no-longer-failing) ==="
comm -23 "$T/base.failed" "$T/patched.failed"
echo "DIFF_DONE"
