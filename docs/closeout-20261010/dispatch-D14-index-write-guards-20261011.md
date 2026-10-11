# 票 D-14：给四只能写知识库的 CLI 补 `chroma_dir_guard`（2026-10-11 派发）

> 台账出处：`reports/decisions-needed-20261010.md` §B 的 **D-14**（Owner 2026-10-11 裁「登记下一轮」，并授权由本会话把票写出来）。
> 执行书：`docs/superpowers/plans/2026-10-10-non-deployment-release-closeout-execution-plan.md` 的 **B 单只点名了 B-45**，本票是 B-45 的**同族扩面**，不是重开 B-45。
> 落盘约定：候选树 = `C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`；运行根（证据/报告）= `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`。

## §0 三行汇总

1. **现状**：`scripts/chroma_dir_guard.py` 的消费方只有 **4 只**（`backup_data` / `import_laws` / `rebuild_embeddings` / `switch_embedding`，现量见 §1.1）；另有 **4 只能改生产向量库的 CLI 一只守卫都没有**，合计 **13 个写/删站点**（`import_docs` 2、`verify_new_law` 7、`eval_chunking` 3、`backfill_time_meta` 1）。
2. **要做的（10-11 复核后重写——原写法机制不成立）**：这四只**没有自己的固定目标**，它们的目标是 `rag_chain.py:125` 的 `CHROMA_DIR = os.environ.get("CHROMA_DIR") or DEFAULT_CHROMA_DIR` ⇒ 对它们调 `assert_matches` 是**恒等式**，永远不咬红（独立复核 B 抓出，我第一版照 `import_laws` 抄守卫是抄错了对象）。改成三件事：① 新腿 `require_explicit_target(caller, writes)`——**未设 CHROMA_DIR 且要写/删** ⇒ 拒绝（此时默认落生产目录，操作者从未选择过）；② `eval_chunking.py` / `verify_new_law.py` 是评测与验证脚本，却真的 add_documents + delete 生产 collection ⇒ 改成在临时目录上跑（播种它们需要的条文），而不是给它加一道必然绿的门；③ `import_docs.py` / `backfill_time_meta.py` 的破坏性子命令改**默认 dry-run + 显式 --write**。
3. **判据形状**：每只都要"不设 env 就跑破坏性写 ⇒ 退出码非 0"与"设 env 指到临时目录 ⇒ 放行并写在临时库"两条腿，且断言里点名是哪一个守卫抛的。**只断言守卫函数被调用＝假绿**（本票第一版就是这个形状）。

## §1 现场事实（每条都带复算命令，开工前先自己重跑一遍）

### 1.1 守卫消费方现量

```bash
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
git -C "$C" grep -n "chroma_dir_guard" -- backend | grep -v tests/
```

2026-10-11 读数：`backup_data.py:129,130`、`import_laws.py:275`、`rebuild_embeddings.py:108`、`switch_embedding.py:143`（`backend/` 前缀省略）。

### 1.2 四只无守卫的写/删站点

```bash
S="$C/backend/scripts"
for f in import_docs.py verify_new_law.py eval_chunking.py backfill_time_meta.py; do
  printf '%-22s add_text=%s col_delete=%s col_update=%s add_documents=%s\n' "$f" \
    "$(grep -c 'add_text(' "$S/$f")" "$(grep -c '\.delete(' "$S/$f")" \
    "$(grep -c '\.update(' "$S/$f")" "$(grep -c 'add_documents(' "$S/$f")"
done
```

2026-10-11 读数：

| 脚本 | 站点 | 打在哪个对象上 |
|---|---|---|
| `import_docs.py` | `:70` `:100` 两处 `_col().delete(...)` | `_col()` = `vectorstore._collection`（`:58`）⇒ **生产向量库** |
| `verify_new_law.py` | 6 处 `add_text(...)` + `:50` `col.delete(...)` | 经 `knowledge_service` 写生产库；且该文件 **`load_dotenv` 在模块级第 26 行**（import 该脚本就会装载真实 `.env`，比 CLI 里装更危险；另第 24 行是 import 语句） |
| `eval_chunking.py` | `:51` `_collection.delete(...)` + `:71,72` `vectorstore.add_documents(...)` | 生产库（评测用完就删，删的就是生产里的条目） |
| `backfill_time_meta.py` | `:42` `col.update(...)` | 生产库元数据回写 |

> ⚠️ 站点数会随这些脚本自身改动而漂 ⇒ **以你重跑的命令为准**，别引用本表数字进你的回报。

### 1.3 守卫为什么存在（判例，别绕过它的理由）

`chroma_dir_guard.py` 的模块 docstring + `backup_data.py:66` 那句：环境里 `CHROMA_DIR` 与脚本固定目标分歧时，脚本会**静默作用在另一个库上**（本机有 `backend/chroma_db` 与 `backend/.ptmp-*` 并存的历史），所以守卫的选择是拒绝执行而不是"提醒一句"。

## §2 任务范围（含明确的不做什么）

做：
1. 加 `require_explicit_target(caller, writes: bool)`（放 `chroma_dir_guard.py` 旁边或同模块），语义是"**没选过目标就不许写生产默认目录**"，与既有 `assert_matches` 的"选了 A 却打到 B"是**两根不同的轴**，别混成一个函数。
2. `verify_new_law.py` 还要按在册纪律处理 `load_dotenv`：**不要**改成"顺手把真实 `.env` 装进测试进程"——见 §3 的红线。
3. 每只脚本配一只"守卫会咬红"的用例（放 `backend/tests/`，命名跟 `test_import_laws_guard.py` 同族）。

不做：
- 不改这四只的**业务语义**（purge 条件、add_text 参数、评测流程一律不动）。
- 不扩到 `scripts/` 之外的写入口（`main.py` 的运行时写入是另一条面，见 §6 停止条件 3）。
- 不动 `chroma_dir_guard.py` 本体，除非你要加的轴确实无处安放（那要先回报）。
- 不 commit / 不 push / 不部署 / 不跑那两只会装真实配置的 smoke 脚本。

## §3 硬约束（红线，逐条照抄执行书，违一条即停手回报）

- **禁读禁打**：`backend/.env`、任何 `.env*`、`backend/app.db`、`backend/data/`、`backend/chroma_db/`、`backend/media/`、`backend/backups/`、`C:/Users/33393/.cache/huggingface/`。不 print 任何凭据值（键名/长度/计数可以）。
- **真实库零读写**：不碰生产 `backend/chroma_db`、不碰配额库、不跑 `smoke_citation_fast.py` / `smoke_*.py`（它们 `os.chdir` + `load_dotenv` 会装真实配置与真实配额库，见 `reports/gates.md`）。
- **部署面**：不部署、不重启 compose 栈、不占/不重起端口 3021/8088、不 commit/push/改 ref。
- **并行会话纪律**：动手前 `git -C "$C" status --porcelain` 现量并核对归属；候选树里 `backend/main.py`、`backend/agent/controller.py`、`backend/llm_registry.py` 等本会话正在改的文件**不要碰**，若要碰先回报。
- 测试一律在**副本树**或树内 gitignored 临时目录里写库；`conftest.py:23,32,40` 已把 `QUOTA_DB` / `DATABASE_URL` / `CHROMA_DIR` 三个出口重定向到进程私有临时位置，沿用它的形状，不要自己造第二条隔离路径。

## §4 判据（每条都要能红，且要说清"红的是哪一条"）

1. **守卫在场**：`grep -n "chroma_dir_guard" backend/scripts/<四只>.py` 每只至少 1 处 import + 1 处 `assert_matches`。
2. **会咬红**（核心）：新用例必须证明"未设 `CHROMA_DIR` 且执行写/删 ⇒ 拒绝"，以及"设 `CHROMA_DIR` 指向临时目录 ⇒ 放行且**只动临时库**"；两条都要断言到具体守卫名与退出码。
3. **不进 import 路径**：`python -c "import scripts.<name>"` 在正常环境下不应触发守卫（判例见 `import_laws.py:270` 那句"位置是硬约束"）⇒ 用例里要有一只"仅 `__main__` 才检查"的腿。
4. **回归**：全量 `pytest -m "not slow" --cov=. --cov-fail-under=70` 与 `ruff check` / `ruff format --check` / `mypy .` 四腿 rc=0，读数与在册基线**同数**（`--collect-only` 单取 collected，junit 用例数配平；见 `reports/gates.md` 的轴纪律）。基线本身会随别的提交漂 ⇒ 你开工时先记一次基线读数再动。
5. **真实库零改动证明**：`find` 目录级 + 文件级两轴（口径见 `reports/gates.md` §2.3 那条更正：文件轴 0 命中 + 唯一目录级命中要归因），外加跑前跑后各一次指纹。

## §5 交付物

- 代码：4 只脚本 + 4 只（或更多）用例，改动面 `git diff --stat` 随报告给出。
- 报告：`<运行根>/reports/d14-index-guards-20261011.md`，结构照 `reports/d3-langchain-migration.md`（§0 三行 → §1 读数 → §4 我自己犯的错 → §5 已知限制 → §6 待裁台账（每条一词可答 + 推荐）→ §7 证据指针）。
- 证据：`<运行根>/evidence/d14-*.log`（四腿门禁、变异/负向自证、find 双轴）。
- **落 LF**：所有你新写的文件要 `newline="\n"`，并自量 `tr -dc '\r' | wc -c` = 0。

## §6 停止条件（回报，不要自己扩大范围）

1. 若在实现②时发现 `eval_chunking` / `verify_new_law` 离了生产 collection 就跑不了（依赖真实语料）⇒ **停**：这说明"评测脚本必须能离线跑"是另一条产品债，要另计一条，不能拿"给它加恒等守卫"交差。
2. `chroma_dir_guard` 现有 API 放不下这条轴（比如脚本压根不读 `CHROMA_DIR`）⇒ 停，回报要改本体。
3. 你发现 `main.py` 运行时也有无守卫写入口 ⇒ **另计一条**，别顺手改（那是产品路径，风险面不同）。
4. 全量回归里出现**开工前没有**的红 ⇒ 先归因（单变量隔离到"我这几处改动"），归因不清就停。

## §7 回报格式

一句话结论 + 四条读数（collected/passed/skipped/deselected + cov、ruff、format、mypy）+ 站点表现量 + 负向自证"红的是哪条断言" + 已知限制 + 待裁台账（每条一词可答带推荐）+ 全部证据绝对路径。
