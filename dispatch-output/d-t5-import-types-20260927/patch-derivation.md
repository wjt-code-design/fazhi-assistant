# `t5-my-change-only.patch` 的来历与校验

**用途**：T5 的两个归属文件里混着 T1/T2 的未提交改动，`git add` 是按文件粒度的，没法只提交我这笔。
这份 patch 把"我这笔"单独切出来，供 Owner 打到只有 T1/T2 改动的树上。

## 怎么切出来的

- `backend/pyproject.toml` 段 = `git diff -- backend/pyproject.toml`（该文件的 diff 全属我，无人并行改）。
- 两个 `.py` 段 = 先用**本会话日志**把这两个文件的编辑逐条**逆序回放**，重建出"我的改动之前"那份状态
  （会话日志 `C:\Users\33393\.qoder-cn\projects\c--Users-33393-Desktop-ai-legal-helper\2347bb66-9720-4ae7-a45e-d1c5fc2435a8.jsonl`；
  本会话对该二文件的 Edit 计数：`import_laws.py` **1** 条、`test_import_laws_preflight.py` **9** 条），
  再 `difflib.unified_diff(pre, cur)` 得出。

## 三条校验（都实跑过）

1. **回放闭环**：逆序回放出 pre 后，再按原序前向重放，逐字节等于当前文件（脚本内 `assert`）。
2. **反向**：`git apply --reverse --check t5-my-change-only.patch` 在**真实工作树**上 `rc=0`
   ⇒ 这份 patch 的 post-state 正是工作树里那两个文件，没有多也没有少。
3. **正向**：在只含 pre 状态的临时树里 `git apply -p1` → `rc=0`，两文件 sha256 与工作树**逐字节相等**：
   - `scripts/import_laws.py` pre `746725317cad…` → post `5dc5a76fc899944b0b1afbc03d7a2628e43cc812330ecd2ebb9e3dc2f196616b`
   - `tests/test_import_laws_preflight.py` pre `5d377af20cc3…` → post `1e85b76989232a7b560357d9b0c4b02e3eadb7d43c7eecd0c23172cfd3c2ee2e`

## 应用时的一个坑（实测踩过）

本机 `core.autocrlf=true`。临时树**没带 `.gitattributes`** 时，`git apply` 会把 LF smudge 成 CRLF
（`import_laws.py` 258 处、测试文件 446 处），哈希对不上但**正文一致**——别误判成 patch 坏了。
仓库根 `.gitattributes` 的 `* text=auto eol=lf` 才是本地 LF 的来源；在原仓库里 apply 不受此坑影响。
