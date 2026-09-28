#!/usr/bin/env bash
# 恢复 codex/local-candidate-closeout 的分支指针。
#
# 背景：本仓库存在缺陷 —— git 把 refs/heads/<目录>/<名> 写成功后，约 120 ms 内会被另一个进程
# 删掉（详见 README「仓库 git 缺陷」）。于是提交"成功"但分支指针不落盘，git log 会报
# "your current branch ... does not have any commits yet"。提交对象与 reflog 不会丢。
#
# 两级恢复（先便宜的后兜底）：
#   ① reflog 还在 → 直接按 reflog 最新 SHA 手工写 ref 文件（不要用 git update-ref，会被再次抹除）
#   ② reflog 也没了 → 从 bundle 里把对象取回来，再手工写 ref 文件
#
# 用法： bash restore-candidate-ref.sh [仓库路径] [bundle 路径]
set -u

REPO="${1:-C:/Users/33393/Desktop/ai-legal-helper}"
BUNDLE="${2:-C:/Users/33393/Desktop/ai-legal-helper-bundles/local-candidate-closeout-fbc29e8.bundle}"
BRANCH="codex/local-candidate-closeout"
REFLOG="$REPO/.git/logs/refs/heads/$BRANCH"

write_ref() {  # $1 = sha
  mkdir -p "$REPO/.git/refs/heads/codex"
  printf '%s\n' "$1" > "$REPO/.git/refs/heads/$BRANCH"
  echo "     已手工写入 ref 文件：$1"
}

echo "== repo   : $REPO"
echo "== branch : $BRANCH"

if git -C "$REPO" rev-parse --verify -q "refs/heads/$BRANCH" >/dev/null 2>&1; then
  echo "OK   引用存在（$(git -C "$REPO" rev-parse --short "refs/heads/$BRANCH")），无需恢复。"
else
  echo "WARN 引用缺失，开始恢复。"
  if [ -f "$REFLOG" ]; then
    SHA="$(tail -n 1 "$REFLOG" | awk '{print $2}')"
    echo "     来源 ① reflog → $SHA"
    write_ref "$SHA"
  elif [ -f "$BUNDLE" ]; then
    echo "     reflog 不可用，改用 ② bundle：$BUNDLE"
    git -C "$REPO" fetch -q "$BUNDLE" "refs/heads/$BRANCH" || git -C "$REPO" fetch "$BUNDLE" "refs/heads/$BRANCH"
    SHA="$(git -C "$REPO" rev-parse FETCH_HEAD)"
    echo "     bundle 里的对象已取回 → $SHA"
    write_ref "$SHA"
  else
    echo "FAIL reflog 与 bundle 都不可用；需要人工介入（bundle 默认在 $BUNDLE）。"
    exit 2
  fi
fi

echo "== 三处核对 =="
echo "-- rev-parse : $(git -C "$REPO" rev-parse --verify -q "refs/heads/$BRANCH" || echo '仍缺失 → 恢复失败')"
echo "-- worktree  :"; git -C "$REPO" worktree list | grep -i "local-candidate-closeout" || echo "   （worktree list 未见该分支）"
echo "-- log       :"; git -C "$REPO" --no-pager log --oneline -1 "refs/heads/$BRANCH" || true
