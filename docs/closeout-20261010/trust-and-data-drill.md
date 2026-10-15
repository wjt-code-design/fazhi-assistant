# E 单交付：模型来源、加载信任门与合成数据演练（2026-10-10）

运行根：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`
候选：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`（分支 `codex/nondeploy-closeout-20261010`）
解释器：`candidate-envB/Scripts/python.exe`（Python 3.11.0；闭包见 `evidence/envB-freeze.txt`）

状态：**E.1 PASS / E.2 PASS / E.3 PASS（合成面）**；实库恢复仍按构造 BLOCKED（见 §4）。

---

## 1. E.2 加载信任门

### 1.1 生产路径只有一处构造点

`backend/rag_chain.py:41-47` `_build_embeddings()` → `HuggingFaceEmbeddings(model_name="BAAI/bge-base-zh-v1.5", model_kwargs={"device":"cpu"})` → `sentence_transformers.SentenceTransformer`。
全仓 grep（backend 根 + `agent/` + `scripts/`）**没有任何** `trust_remote_code` 出现 ⇒ 默认落在库的拒绝侧。

### 1.2 行为级现量（`evidence/probe_st_trust.py` → `evidence/e2-trust/probe_st_trust.json`）

合成模型目录 = 本轮私有快照 `f03589ce…`（>50 MB 权重**硬链接**、小文件真复制，理由写在脚本 docstring：
真复制才允许改 `config.json` 而不洗掉在册快照的共享 inode），诱饵 = `auto_map → modeling_marker.py`，
该模块**一被 import 就落 marker 文件**。ST 6.1.0 / transformers 5.19.0：

| 臂 | `trust_remote_code` | 结果 | marker |
|---|---|---|---|
| CTRL | 未给（干净目录，无诱饵） | 加载 + 编码 `[1,768]`、l2=1.0、非零 | 无 |
| A | 未给（带诱饵） | 加载 + 编码同上 | **无** ⇒ 未执行自定义代码 |
| B | `False` | 同上 | **无** |
| C | `"local"` | 构造后抛 TypeError（走了自定义 AutoConfig 那条路） | **有** ⇒ 阳性对照咬住 |
| E | `True` | 抛 TypeError | 【**本行「无」已撤回**＝同进程缓存假阴性：C 臂已把自定义模块灌进 `sys.modules`，E 臂命中缓存没重新执行。逐进程重跑后 E **有 marker** ⇒ `True` 会执行本地自定义代码；见 §1.4】 |

`verdict = GATE_HOLDS`（脚本自带四条件判据：CTRL 必须编码非零、A/B 无 marker、C 必须有 marker）。
**判据名保留、含义改窄**（原句「"警告后仍执行"这一形状不存在」已撤回）：门只在**没人显式给 `True`/`"local"`** 时保护我们；给了就会执行模型目录里的自定义代码（§1.4 的 E/C 两臂已证）。⇒ 我们防的是**配置面**，不是指望库替我们挡。

两台假器官我先踩了自己再修：
1. 第一版探针用 `transformers.AutoModel.from_pretrained` 打在**没有权重文件**的合成目录上，A/B 的
   "拒绝"其实来自 `OSError: no file named model.safetensors` —— 与信任门无关。补了权重后这条假信号消失，
   判据也加了一栏 `exc_says_trust_gate`，只认与 `trust_remote_code` 相关的拒绝理由。
2. 第一版走 ST 时把 `Path` 直接喂给 `SentenceTransformer`（ST 6.1 做 `"..." in model_name_or_path` ⇒
   `TypeError: argument of type 'WindowsPath' is not iterable`），并且把 `trust_remote_code` 塞进
   `model_kwargs` 而不是它的一等形参 ⇒ 四臂全红但红在尺子上。改法是 `str(dir)` + 顶层 kwarg
   （已用 `inspect.signature` 确认 `trust_remote_code` 是 ST 的直接参数）。

### 1.3 入库腿（`backend/tests/test_loader_trust_gate.py`，4 条，可在 CI 跑）

行为级那套要 409 MB 权重、两分钟，不进默认套件；进套件的是**接线与默认值**三腿 + 一条负向自证：
构造点 AST 里没有 `trust_remote_code`；`SentenceTransformer.__init__` 的默认值当场量得 `False`；
生产面无 opting-in 形状【该腿首版是**行文本 grep**，两种写法可穿（键名拼接 / 位置参数）；已由 `3f605de` 换成 `ast.walk` 找 `ast.keyword`+`ast.Constant`，并用 M4 臂证明它能红】；`_refusing_default()` 喂"默认 True"与"形参消失"两只替身都必须判否
（否则第 2 条是恒真哨兵）。

读数：`3 passed`（首版）→ 变异轮 `4 passed`，`evidence/pytest.custom.candidate-envB.20261010T052018Z.log`。
变异仪（`evidence/run_loader_trust_mutants.sh` → `evidence/loader-trust-mutants.log`）：

| 臂 | 改动 | 读数 |
|---|---|---|
| M1 | 构造点顶层加 `trust_remote_code=True` | **4 errors**（非断言红，见下） |
| M2 | 改塞进 `model_kwargs={"device":"cpu","trust_remote_code":True}` | **2 failed / 2 passed** |
| M3 | 不变异基线 | 4 passed |
| 实时源码 | `rag_chain.py` sha `18685348a0fd9fe5` 前后相同 | 变异只发生在副本树 |

M1 的读数要如实读：`HuggingFaceEmbeddings` 是 pydantic v1 且 `extra fields not permitted` ⇒
**顶层传这个键在本项目构造不出来**（`import rag_chain` 期就 ValidationError，因为该模块在 import 期建
embeddings 单例）。所以可达的 opt-in 形状只有 M2 那一种，而 M2 让两条断言真红 —— 判据是承重的。

### 1.4 逐进程重跑（2026-10-10 深夜，复核 B 指出臂 E 是缓存假阴性后我复现）

同一进程里依次加载 A→B→C→E 是错的：**动态模块注册表是进程级的**，C 臂 import 过诱饵模块后，
E 臂只是从 `sys.modules` 取，marker 空是缓存的症状而不是门的功劳。改成每臂独立解释器
（`evidence/probe_st_trust_arm.py`，`PROBE_MARKER` 按臂名单独命名）：

| 臂 | 目录 | kwargs | marker（逐进程） | 判读 |
|---|---|---|---|---|
| A | 被污染 | 不给 | **无** | 默认拒绝 ⇒ 拦住 |
| B | 被污染 | `False` | **无** | 显式拒绝 ⇒ 拦住 |
| C | 被污染 | `"local"` | **有** | 执行本地自定义代码 |
| E | 被污染 | `True` | **有** | **执行**（上一版读成"无"） |
| D | 干净快照 | `True` | **无** | 干净目录不需要自定义代码 ⇒ 不执行 |

真源 HF 缓存目录 mtime 前后相同（探针只写合成副本）。⇒ 本单标题级结论改窄为 §1.2 那句"防的是配置面"。

---

## 2. E.3 备份→恢复演练（合成 SQLite / 配额 / Chroma / media）

入库腿：`backend/tests/test_backup_restore_drill.py`（7 条）。与在册 `test_backup_data.py`（15 条失败关闭契约）
不重叠：那只钉"坏包不发凭证"，本只钉"好包真能把数据取回来并查得动"。

| 腿 | 钉什么 |
|---|---|
| `..._manifest_covers_every_surface` | 包内六件齐（`app.db`/`chroma_db`/`chroma_index.json`/`data_app.db`/`media`/`quota_used.sqlite`）；三条 sqlite 的 `integrity_check=="ok"`；**WAL 源库备份出来是单文件**，包里无 `-wal`/`-shm`/`.verify.tmp` |
| `..._sentinel_row_not_just_a_count` | 恢复库按条号取回**合成条文原文**三列全等（不是数行数） |
| `..._quota_ledger_keeps_its_own_numbers` | 配额账本恢复后 `(model, used, total)` 逐值相等 ⇒ 附属库映射没串位 |
| `..._right_citation` | 恢复向量库按查询向量命回 `doc-1`，`article` 与正文全等，并与包内 `chroma_index.json` 的 `(source×article)` 集合**对得上** |
| `..._repeatable_and_never_touches_the_original_inputs` | 同一包目录第二次 `rc=2` 拒绝覆盖；清单 sha 未变；恢复两次之后源树逐文件 sha 快照与备份前**相同** |
| `..._writes_no_manifest_when_a_mid_way_step_fails` | media 复制半途抛 ⇒ `rc=1` **且清单不存在** |
| `..._guard_refuses_divergent_targets_before_any_work` | `CHROMA_DIR`/`QUOTA_DB` 与固定目标分歧 ⇒ `_check_env_contract()` 在任何读写之前 `SystemExit`；一致/unset 才放行 |

前置自检（防恒绿）：`make_main_db()` 自己 assert 源库 `PRAGMA journal_mode` 真是 `wal`（非 WAL 那条腿 assert `!= wal`）。
第一版把它写成无条件断言，`data/app.db` 那条腿当场红 —— 红的是尺子，已按形状分开。

变异仪（`evidence/backup-drill-mutants.log`，副本树，跑完删）：

| 臂 | 改动 | 读数（红的是哪条，点名） |
|---|---|---|
| M1 | `EXTRA_SQLITE` 两只源互换（把账本备份成容器侧库） | `1 failed / 6 passed` ⇒ 红在 `..._quota_ledger_keeps_its_own_numbers` |
| M2 | media 复制后静默删掉并谎报 `skipped` | `1 failed / 6 passed` ⇒ 红在 `..._manifest_covers_every_surface` |
| M3 | 基线不变异 | `7 passed` |

向量一律显式传入（`embeddings=`/`query_embeddings=`）：chromadb 默认 embedding function 会去下载 mini-lm，
那既违反本轮"不出网"护栏，也让测试依赖网络。演练全程在 `tmp_path`，未读写 `backend/chroma_db`、`app.db`、`data/`。

顺带一条**在册复确认**（不是新发现）：演练日志里出现
`chromadb.telemetry.product.posthog: Failed to send telemetry event ...: capture() takes 1 positional argument but 3 were given`
⇒ 候选闭包（chromadb 0.4.24 + 现装 posthog）下 chroma 的遥测**在参数绑定阶段就失败**，从未走到 socket；
`docker-compose.yml:32-41` 早已把这件事写清（含"该开关不能消除这条报错"的诚实标注）。本轮 socket 守卫读数为
非回环 0 次，与那条在册说明一致。

---

## 3. B-45（随 E/D 同族入口一并做）：`import_laws` 的 CHROMA_DIR 守卫

在册缺口：会改写生产索引的三类动作里，`backup_data`、`rebuild_embeddings`（`switch_embedding` 经 subprocess 复用）
都被 `chroma_dir_guard.assert_matches` 检查过，`import_laws` **默认实写**却没有。

改动：`backend/scripts/import_laws.py` 加 `PROD_CHROMA_DIR` 常量 + `_check_env_contract()`，
挂在 `if __name__ == "__main__"` 上（与同族一致，不进 `main()`、不在 import 期）。

三段闸的第二段例外是**判据推出来的**，不是为了让测试过：`--validate-only` 在 `main()` 里早于
`import knowledge_service / rag_chain` 就 return ⇒ 结构上不可能写库；而 `test_import_laws_validation.py`
正靠"把 `CHROMA_DIR` 指到一只不存在的目录"来证明它不碰库，守卫拦它就是守卫把测试钉红。
第一次实现我没留这个例外，全量当场 **10 failed**（全在 `test_import_laws_validation.py`）—— 这条读数留着，
因为它就是"例外为什么必须存在"的证据。已知粗糙处：按字符串查 `sys.argv`，argparse 前缀缩写 `--validate`
会落到"守卫跑"那一侧 ⇒ 偏保守。

入库腿 `backend/tests/test_import_laws_guard.py`（4 条，全走子进程 = 运维敲的那条路径）：默认与 `--dry-run`
在分歧 env 下于**读输入之前**拒绝（输入路径故意不存在 ⇒ 只能报"拒绝执行"，且拒绝时不建库目录）；
`--validate-only` 放行且 `rag_chain` 不在 `sys.modules`；一致与 unset 都放行；
`main()` 里没有守卫（直接 monkeypatch `sys.argv` 调 `main()` 必须走到缺文件那条 rc=1）。

读数：`32 passed`（新 4 条 + 在册 validation 10 + preflight 18），
`evidence/pytest.custom.candidate-envB.20261010T054349Z.log`。
变异仪（`evidence/import-laws-guard-mutants.log`）：M1 删掉 `__main__` 的守卫调用 ⇒ 恰好红在
`test_write_modes_refuse_divergent_chroma_dir_before_touching_the_input`（1 failed / 3 passed）；M2 基线 3–4 passed。
我自己在这只文件上先交过一次假读数：CHILD 里 `except SystemExit: pass` 把"拒绝执行"那条消息吞了
（SystemExit 的 message 是解释器在退出时打到 stderr 的）⇒ 第一条腿拿到的是"没拦"。改成 re-raise 后才拿到真读数。

**与在册风险册的关系（如实摊开）**：B-45 给生产索引增加了第二个写入口（此前运维脚本面只有备份/换班在读）。
`docs/chroma-risk-triage-20261003.md` 的失效条件是"新增 HttpClient／Chroma server／多 tenant／动态 embedding 配置"
四写，导入批次不属于其中任何一条 ⇒ **在册文本不被本条推翻**。但"两个写入口都开同一个目录"这件事值得进册备忘；
该册是 Owner 的在册文件，我不代改，只登记。

---

## 4. E.1（本轮早先完成，指针）

`BAAI/bge-base-zh-v1.5` commit `f03589ceff5aac7111bd60cfc7d497ca17ecac65`，MIT，12/12 文件对官方哈希
（11 只小文件对 blobId git sha1，409 MB `pytorch_model.bin` 对官方 LFS sha256），落本轮私有缓存；
`huggingface.co` 本机 HTTP 000 ⇒ 走 `hf-mirror.com` 下载 + 官方 API 透传哈希。
证据：`evidence/bge-model-verification.json`、`evidence/hf-bge-meta.json`、`evidence/fetch_bge_model.py`。
未扫描、未哈希现役 `C:/Users/33393/.cache/huggingface`（按本书禁区）。

## 5. 复算入口

```bash
R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
cd "$R"
# E.2 行为级五臂（约 2 分钟，需要私有 BGE 快照）
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 candidate-envB/Scripts/python.exe evidence/probe_st_trust.py \
  "$PWD/evidence/e2-trust" \
  "$PWD/model-cache/hub/models--BAAI--bge-base-zh-v1.5/snapshots/f03589ceff5aac7111bd60cfc7d497ca17ecac65"
# E.2/E.3/B-45 入库腿 + 三台变异仪
TARGET="tests/test_loader_trust_gate.py tests/test_backup_restore_drill.py tests/test_import_laws_guard.py" \
  ./evidence/run_backend_tests.sh "$R" "$C" custom candidate-envB
bash evidence/run_loader_trust_mutants.sh "$R" "$C"
bash evidence/run_category_mutants.sh "$R" "$C"
```
通用变异仪 `evidence/run_mutants.sh`（锚点/替换写在 `evidence/arms/*.txt`，避免 shell 引号折叠改坏文件）：

```bash
bash evidence/run_mutants.sh "$R" "$C" drill-mutants.log tests/test_backup_restore_drill.py --   M1_swap_extra_mapping scripts/backup_data.py evidence/arms/bd_anchor_extra.txt evidence/arms/bd_repl_swap.txt   M2_media_silent_skip  scripts/backup_data.py evidence/arms/bd_anchor_media.txt  evidence/arms/bd_repl_media.txt   M3_baseline           scripts/backup_data.py evidence/arms/bd_anchor_extra.txt  @no-repl
bash evidence/run_mutants.sh "$R" "$C" b45-mutants.log tests/test_import_laws_guard.py --   M1_drop_guard_call scripts/import_laws.py evidence/arms/il_anchor.txt evidence/arms/il_repl_dropguard.txt   M3_baseline        scripts/import_laws.py evidence/arms/il_anchor.txt @no-repl
```
落盘日志：`evidence/drill-mutants.log`、`evidence/b45-mutants.log`、`evidence/loader-trust-mutants.log`、
`evidence/category-mutants.log`。每份日志尾部都有 `live targets ... unchanged=True` 三只 sha —— 变异只发生在副本树。
通用仪本身也是先红后绿来的：第一版 `@no-repl` 分支写 `shift 3`（应为 4），把 `@no-repl` 当成下一条臂的
TAG 读进去，当场 `$2: unbound variable`；已修并复跑。

## 6. 未做 / 射程外

- 真实库恢复、真实语料版本元数据：按本书禁区保持 **BLOCKED**，合成演练不等于实库验收。
- `switch_embedding.py` / `rebuild_embeddings.py` 的 CLI 未被调用（它们会改配置/杀进程/读现有库）。
- E.2 的行为级证据是 evidence 脚本而非套件成员（409 MB 权重 + 两分钟）；套件里是接线/默认值腿 + 负向自证。
- B-44（改密走 argv 且零审计）、B-46（`_cutoff` 钟）不在本书 B 单表内 ⇒ 本轮未动。
