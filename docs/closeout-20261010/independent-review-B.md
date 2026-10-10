# 独立复核 B 路：挑战论点 + 补漏项（2026-10-10）

复核人立场：**未参与本单任何实现**，把 `reports/trust-and-data-drill.md`、`reports/gates.md`、
`reports/h-ci-and-credentials.md`、`reports/owner-decisions-20261010.md`、`reports/decisions-needed-20261010.md`
当成陌生同事交来的材料挑刺。所有结论先做实验/读码再落笔；跑不动的写明"未跑 + 原因"。

- 复核对象：候选 `C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`
  —— **代码面按 `8c179e7`（+`5ca3315`）量**；复核期间该分支又长出一笔 `a934fa7`（只改
  `.github/workflows/ci.yml` 6 行注释，`git show --stat` 已核），不影响任何读数，但说明"两笔提交"的
  口径已经过期。
- 复现根：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`
- 我的实验脚本与日志：`reviewB-scratch/`（未写入 `evidence/`、未改候选树任何字节；变异全部跑在
  `reviewB-scratch/cand-tree*` 副本里）
- 互不干扰：未用浏览器、未占 3021/8088/3178/8777、未读禁区（`.env*`/`app.db`/`data/`/`chroma_db/`/
  `media/`/`backups/`/现役 HF 缓存），未跑会读真实库的 CLI。

---

## §0 一句话结论

**大方向站得住：约 6 成站得住 / 约 3.5 成需要修正措辞或补登记 / 约 0.5 成站不住。**
- 我重跑了本轮三只新测试文件（**15 passed = 4+7+4**）、M1 的"4 errors"、快照小文件哈希、B-45 的拒绝
  行为（含前缀缩写方向），**全部复现**；E.3 演练的做法比我预期更硬（它有真包内容比对与"复制后重开"），
  B-45 相对"什么都不做"确实降低了风险。
- **有一条结论被实验推翻**：`gates.md` §7 与 `trust-and-data-drill.md` §1.2 里"ST 层 `True` 对本地目录
  也不放开（transformers 5.x 语义）"是**假读数**——原探针五臂挤在同一个进程里跑，arm C 先把动态模块
  进了缓存，arm E 复用缓存所以没落 marker。我把每臂单独放一个进程：`True` 与 `"local"` **都会执行**
  自定义代码。这条同时把"可达的 opt-in 形状只有 M2 那一种"打掉。
- **有一条口径太宽**：H 单"按值反查做不到 ⇒ BLOCKED"。在本书授权内，**环境变量里的当前值本来就可以
  当内存比对输入**；我用本进程环境里 5 把现役 key 对"将被 push 的全部对象"做了值级扫描（3021 个 blob，
  0 命中，正/负对照都能指对），并且独立复核了在册 09-30 记录的**路径与祖先事实**（817e7d3/7eda4bb
  都是候选 HEAD 的祖先 ⇒ 普通推会上传那个含明文口令的 blob）。
- **有一条判断偏窄**：B-45 说 `import_laws` 是"三类可改写生产索引的动作里唯一没被检查的"——实测至少
  还有 4 只**未加守卫**的写入口（`import_docs.py`、`verify_new_law.py`、`eval_chunking.py`、
  `backfill_time_meta.py`，其中前三只还会 **delete**）。
- **执行书里 6 条 checkbox 在所有 8 份报告里零次出现**（DB-6/7/8/10/11/12/13 这一族 + E 单的 rerank
  路由实核 + Chroma 切换合成对照），属于"沉默项"。
- **没有"必须立刻改代码"的运行期洞**：我造出的两个"四腿全绿"形状都需要有人主动改项目代码；产品
  当前默认路径（未传 key）经行为级复核确实拒绝执行自定义代码。

---

## §1 逐条挑战表

| # | 我的挑战 | 我做的实验 / 读的代码 | 结论 | 需要的措辞修正 |
|---|---|---|---|---|
| B1-a | "断言 `SentenceTransformer.__init__` 默认 False"这条 canary 在**本项目实装路径**上是否承重？ | 读 `langchain_huggingface/embeddings/huggingface.py`（0.0.3）：`self.client = SentenceTransformer(self.model_name, cache_folder=…, **self.model_kwargs)` —— HF 的 `model_kwargs` 是**展开成 ST 顶层形参**的；读 `rag_chain.py:41-47` 只传 `{"device":"cpu"}`。用 recorder 替换 ST 构造器后 `import rag_chain`：未变异树捕获到 `{cache_folder, device}`（**没有** trust 键 ⇒ 落 ST 默认）；变异树捕获到 `trust_remote_code=true` | **站得住**（canary 的取值就是路径上的实际取值），但**不足**：它只钉"没传 key"这一侧，不钉"传了但绕开静态检查" | 建议写成"默认值腿：证明未传时实际生效值是 False；**不构成**'生产不可能 opt-in'的证明" |
| B1-b | 能不能"不改库默认、只改项目代码"造出**四腿全绿**却真打开信任门的变异？（任务给的三条线索逐个试） | 见 §2：M4（字面量放 helper + 同行有 "False" 字样）→ **4 passed**；S1（运行时拼串）→ **4 passed**；两者都用 recorder 证明真把 `trust_remote_code=True` 交给 ST。字面量 `"local"`（我跑的 M3）与字面量 True（报告自己的 M2，`loader-trust-mutants.log` 记 2 failed/2 passed）都被咬；`encode_kwargs` 走的是 `.encode()`，**加载后才发生**，不是信任通道（实测 ctor 只收到 device） | **推翻"只有 M2 一种可达形状"**（穿透形状见 §2） | `trust-and-data-drill.md` §1.3 应改成"本文件钉住的是两种**字面**形状；运行时拼接/字面量在其他函数里可穿透（已由复核证明）" |
| B1-c | "arm E：ST 层 `True` 不放开本地目录（transformers 5.x 语义）"站得住吗？ | 原探针五臂在一个进程里顺序跑（`probe_st_trust.py:127-133`）。我把每臂放独立进程重跑；又跑了 `seq:local,true`（复刻原顺序）与 `seq:true,local` | **推翻**。独立进程：`true`→marker **有**、`local`→marker **有**；`seq:local,true`→true 臂 marker **无**（与报告一致）；`seq:true,local`→true 臂 marker **有**。⇒ 原 arm E 是**模块缓存造成的假阴性**，不是 transformers 语义 | `trust-and-data-drill.md` §1.2 表 E 行、`gates.md` §7 E 行**必须订正**：`True` 与 `"local"` 都会执行；E 臂读数不可单独引用 |
| B1-d | M1 的"4 errors 而不是断言红"，报告解释（"HuggingFaceEmbeddings 是 pydantic v1，顶层传这个键构造不出来"）站得住吗？ | 现场实测：`E pydantic.v1.error_wrappers.ValidationError: 1 validation error for HuggingFaceEmbeddings / extra fields not permitted`；`langchain_huggingface/.../huggingface.py:4` = `from langchain_core.pydantic_v1 import BaseModel, Extra, Field` ⇒ 类**确实是 v1 语义**（虽然环境里装了 pydantic 2.14）。同形变异复跑：`4 errors in 2.89s` | **站得住**（我先怀疑"pydantic v1 说法不实"，实测后撤回该怀疑） | 无（可补一句"错误类型是 pydantic.v1 的 ValidationError"） |
| B1-e | 探针阳性对照用的是硬链接快照——快照有没有被探针改过？ | 按 `evidence/bge-model-verification.json` 的官方 sha256 重算**全部 11 只小文件**（`torch_model.bin` 是第 12 只，409MB，**按指示跳过**）：**11/11 OK**；`synthetic-pristine` 与快照逐文件同哈希，`synthetic-tainted` 只差 `config.json`（诱饵）与新增 `modeling_marker.py`；三处 `pytorch_model.bin` 是**同一 inode**（nlink=3，无额外字节） | **站得住** | 报告应把"跳过 409MB"写成已知限制（我补：见 §4） |
| B2-a | E.3 的恢复步骤是测试文件自己写的（照 `backup_manifest.json` 的 `dest` 复制回去），算"用实现复算期望"吗？ | 读 `scripts/backup_data.py`：产品里**没有**恢复函数；末行打印就是运维口径——"恢复：停后端 → 照 `backup_manifest.json` 逐条把 dest 放回 source 位置（附属库放回 `DATA_DIR/<包内名对应源>`）→ 启动后验证检索"。`scripts/restore_drill.py` 只是**只读**验证器（`mode=ro` 打开 app.db + chroma 计数），不落文件 | **部分站得住**：被测物（包+清单）是产品的，复制回是**产品文档写明的操作**，不是"实现自证"；但复制循环由测试写 ⇒ 只能证"按这层语义够用" | 建议改口径："演练证明包+清单**足以**把数据取回来（按清单语义）；不证明运维照那一行提示做**一定**成功——提示没写 `chroma_index.json`/`media` 的落点，也没提 `QUOTA_DB`" |
| B2-b | 演练能不能外推到真实 chroma 目录恢复？差异在哪？ | 自己造一只最小持久化 chroma：盘上形状 = `chroma.sqlite3` + `<uuid>/{data_level0.bin,header.bin,length.bin,link_lists.bin}` ⇒ **合成包里同样含 hnsw 二进制**（`copytree` 整目录），"合成没有 hnsw"这个猜法不成立。真实差异是：文档数 2 vs 10266+；集合 1 vs 2（`qa_pairs` 是 L2 空间，演练只覆盖 cosine 主集合）；维度 8 vs 768；生产目录 362MB（脚本注释）且**必须在停写状态下复制**；产品侧重开还会挂上 `embedding_function=embeddings` 与 `QuotaTrackingEmbeddings` 包装，演练用显式向量绕开了这一层 | **部分站得住**：形状级外推**成立**（含 hnsw/sqlite3），尺度/双集合/显式 vs 产品重开这三处**不可外推** | §2 应把"可外推/不可外推"分两栏写，并点明"显式向量"绕开了**产品重开路径**（`langchain_chroma.Chroma` + 配额包装） |
| B2-c | 演练最硬的那条腿"不覆盖原输入"（`test_drill_is_repeatable_and_never_touches_the_original_inputs`）到底证明了什么？ | 读测试：`restore()` 一律写进**全新的** dest_root；`shutil.copytree` 对已存在目录实测 `FileExistsError [WinError 183]` | **需要修正**：真实恢复必须**覆盖现役** `app.db`/`chroma_db`/`media`；演练证的是"备份/恢复不动原输入"，恰恰**没有**覆盖"对已有目标恢复"这一步（也是唯一不可逆的一步），而且照抄 `restore()` 的 copytree 写法对现役目录**根本跑不通** | E.3 结论行应加："未覆盖：对已有目标（现役库）的恢复步骤；该步只能人工按清单逐项替换，本轮未演练" |
| B3-a | 守卫在"env 未设"与"env = 生产默认"两种情况下能不能挡住"写错库"？ | 在副本树实测：`CHROMA_DIR` = 本树默认 → 守卫放行，默认（实写）模式 rc=0，两条合成条文落进 `backend/chroma_db`；`CHROMA_DIR` **未设** → 守卫放行，第三条同样落进同一目录（`legal_provisions_cos` count=3）；分歧值 → 读写前拒绝，`other-chroma_db` 目录始终空 | **部分站得住**：只有"env 被显式导出到别处"这一种形状被挡住；"忘了导出/意图不在默认库"这一类**结构上挡不住**（未设==默认==生产，正是 B-45 自己说的"默认实写"） | 结论行不要写成"不再会写错库"；建议："把'env 被导出过'的静默错库变成显式拒绝；**env 未设时的默认实写语义一律未变**" |
| B3-b | `"--validate-only" not in sys.argv` 的字符串豁免，argparse 前缀缩写会落到哪一侧？实测一条命令。 | 分歧 `CHROMA_DIR` + 不存在的 `--input`，逐条跑：`--validate` → **守卫拒绝（rc=1）**；`--val` → **拒绝**；`--validate-only` → 放行到 main → "未找到导入文件"（rc=1，不碰库）；默认写模式 / `--dry-run` → 拒绝；另一条意外发现：大小写不同的**同一物理目录**也被拒（`CAND-TREE` vs `cand-tree`，Windows 路径不区分大小写而 `abspath` 不归一大小写） | **站得住**（"偏保守"属实，且我找不到反方向的拼写：能进 argparse 又绕过字符串判断的形态都不可达） | 可补一句"另有一类**假阳性**：同一目录的大小写变体也会被拒，属保守侧" |
| B3-c | 这条改动相对"什么都不做"真的降低了不可逆风险吗？ | 读全族：`grep chroma_dir_guard` 只命中 `backup_data/import_laws/rebuild_embeddings/switch_embedding`；而**会写同一索引**的 CLI 还有 `import_docs.py`（`_col().delete` ×2）、`verify_new_law.py`（`col.delete` + `add_text` ×4）、`eval_chunking.py`（`vectorstore._collection.delete` + `add_documents` ×2）、`backfill_time_meta.py`（`col.update`）——**全部无守卫** | **部分站得住**：对 `import_laws` 这一条路径确实降低了风险（我实测挡得住）；但报告那句"三类动作里唯一没被检查的"**低估了写入口数量**，会让人误以为这一类门已关 | 建议改："本单按执行书只给 `import_laws` 上锁，同类**未上锁**的还有 4 只（名单见 §3），另开票" |
| B4-a | H 单"按值反查做不到（禁区）⇒ BLOCKED"是不是在偷懒？ | 读执行书 H 单第 3 条：**"环境变量中的当前值只能在内存作为比对输入"** —— 授权的是值来自进程 env（禁区只是 `.env` 文件）。实测本进程 env 里**有 5 把**（含应用自己读的 `DASHSCOPE_API_KEY`/`SILICONFLOW_API_KEY`/`ZHIPUAI_API_KEY`），`ADMIN_PASSWORD`/`JWT_SECRET`/`LLM_API_KEY` **不在**。随后按值扫"将被 push 的全部对象"（`git rev-list --objects HEAD` → `git cat-file --batch` 流式）：3021 blob、正对照 14 命中、负对照 0、**5 把 key 全部 0 命中** | **需要修正/口径太宽**：值轴对 env 里有的那几把**本来就能做**，我做了；对 `ADMIN_PASSWORD` 才是"缺一个授权输入" | 结论应从"按值反查做不到"改成："`.env` 禁读 ⇒ `ADMIN_PASSWORD` 轴缺比对输入，需 Owner 提供（放进 env 即可）；其余现役 key 已做值级扫描：0 命中（射程=当前 push 对象集合）" |
| B4-b | 报告说 09-30 记录"既不沿用也不推翻"——那份记录真的不可用吗？ | 找原文：报告引的 `…2026-09-29-local-candidate-decision-and-release-prep.md` **只有 §0–§5，没有 §8.7/§8.8**；真正的记录在 `docs/work-report-20260929-d2-signoff-round.md` §8.5/§8.6（O-2 行）：`ADMIN_PASSWORD` 明文在 `dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py:104`，**817e7d3 引入、7eda4bb 删除**。我独立复核了它**不依赖值**的那半：两笔提交**都是候选 HEAD 的祖先**（`git merge-base --is-ancestor` 双 rc=0），⇒ 普通 push 会上传那个 blob（远端 HEAD 更老，本地这几笔必然上传） | **部分站得住（但引用错、且过度保守）**：结论本身不可复现（值轴），但它依据的**路径/祖先/文件**事实完全可核，我已核 | 引用要改成 `docs/work-report-20260929-d2-signoff-round.md` §8.5/§8.6；结论行建议改成"在册记录指出 `817e7d3` 带明文（祖先已核）⇒ 先轮换再普通推；我未能复现的只有'那个明文等于今天的口令'" |
| B5 | 漏项 | 见 §3（8 份报告全文 grep，逐条对照执行书 checkbox） | **确有问题**：≥6 条零次出现 | — |
| B6 | 过度声明/用词说大 | 见下 | 3 处需改 | — |

### B6 具体措辞修正（点名）

1. **"ST 层 `True` 对本地目录也不放开"**（`gates.md` §7 E.2 行；`trust-and-data-drill.md` §1.2 E 行）——**删掉**。改为："`True`/`'local'` 均执行自定义代码（独立进程实测）；原探针 E 臂因同进程模块缓存呈假阴性。"
2. **`E.2 PASS` 的射程**——`gates.md` §0/§7 的 PASS 指的是"接线 + 库默认值 + 行为级五臂"，而行为级是 evidence 脚本。建议在状态列写成 `PASS（接线/默认值 + 脚本级行为证据；套件对运行时拼接的 opt-in 不可见 —— 复核已证 4 passed）`。任务提醒的"GATE_HOLDS"一词本身没错（默认与 False 都不执行），错的是它旁边的**语义解释**与隐含的"穷尽性"。
3. **`H-凭据 BLOCKED（按本书禁区，不是"扫了没扫到"）`**——BLOCKED 的**理由**要换：不是"禁区让值轴不可做"，而是"`ADMIN_PASSWORD` 的值不在授权输入面（进程 env）里"；并且应当写明"其余 5 把现役 key 的值级扫描已完成、0 命中；在册记录指出祖先提交带明文 ⇒ 先轮换是**有证据支撑的前置**，不是'无从判断'"。
4. （较轻）**"三类可改写生产索引的动作"**——按实测改成"四只以上"（§3.3）。
5. （较轻）**"两笔新提交"**——复核期间已有第三笔 `a934fa7`（仅 CI 注释 6 行）；`gates.md` §0 H 行的"对象版本"列还只写了两笔。台账自称"唯一真源"，这类过期会让下游引用错对象。
6. （较轻）**"E.3 PASS（合成面）"**——保留，但要跟一句"未覆盖：对现役目标的恢复步骤"（见 B2-c）。

---

## §2 反例 / 穿透形状清单（全部为我自己实测）

### 2.0 实验前提

- 副本树：`reviewB-scratch/cand-tree`（`git archive HEAD backend | tar -x`，不含 `.env`/数据目录；HEAD=8c179e7）
- 解释器：`candidate-envB/Scripts/python.exe`（3.11.0）；`HF_HOME/HF_HUB_CACHE` 指向运行根 `model-cache/`，
  `HF_MODULES_CACHE` 指向我的 scratch，`HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`
- 未变异基线：`4 passed`（`tests/test_loader_trust_gate.py`）

### 2.1 假绿变异（四腿全绿、生产代码真 opt-in）

| 变异 | 内容 | 四腿读数 | 生产代码实际交出去的 kwargs（recorder 实测） |
|---|---|---|---|
| M4 | 字面量 `"trust_remote_code": True` 放在 **`_build_embeddings` 之外的 helper** 里，且该行含 "False" 字样 | **4 passed** | `{"cache_folder": null, "device": "cpu", "trust_remote_code": true}` |
| S1 | `_k = "trust"+"_"+"remote"+"_"+"code"` 运行时拼键（在构造点内） | **4 passed** | 同上 |
| M3 | 字面量 `"local"` 直接写在 `model_kwargs` | 2 failed / 2 passed | —（被咬） |
| M2（报告已有，**我未重跑**） | 字面量 `True` 直接写在 `model_kwargs` | 2 failed / 2 passed（`evidence/loader-trust-mutants.log`） | — |

两条穿透腿为什么成立（读码）：
- 第 1 条腿只看 `inspect.getsource(rag_chain._build_embeddings)` 的 AST ⇒ helper 里的键**看不见**；
- 第 4 条腿 `if "False" in line: continue` ⇒ 同一行出现 "False" 即豁免（注释即可）；且它只扫
  `backend/`、`backend/agent/`、`backend/scripts/` 的**直接 `*.py`**，不递归子目录；
- 第 2、3 条腿只钉 ST 默认值与"判据自己会不会红"，与项目代码怎么传键无关。

### 2.2 信任门"执行/不执行"矩阵（每臂独立进程）

| 臂 | marker 创建 | 加载成功 | 异常 |
|---|---|---|---|
| 默认（不传） | 否 | 是（编码成功） | — |
| `trust_remote_code=False` | 否 | 是 | — |
| `trust_remote_code=True` | **是** | 否 | TypeError（`return_unused_kwargs` 签名漂移，发生在执行之后） |
| `trust_remote_code="local"` | **是** | 否 | 同上 |
| `model_kwargs={"trust_remote_code": True}`（ST 层嵌套） | **是** | **是** | —（唯一"执行且完全加载"的形状） |
| `config_kwargs={"trust_remote_code": True}` | **是** | **是** | — |
| `processor_kwargs={"trust_remote_code": True}` | **是** | 否 | BertModel 参数错误 |
| `encode_kwargs={"trust_remote_code": True}` | 否 | — | 不进构造（只进 `.encode()`，见 2.4） |

同进程顺序（复刻原探针）：`seq:local,true` → true 臂 marker **无**；`seq:true,local` → true 臂 marker **有**。
⇒ 报告 arm E 的"无"是顺序产物。

### 2.3 B-45 守卫矩阵（真跑 CLI，`CHROMA_DIR` 分歧 + 不存在的 `--input`）

```
A: --validate        -> rc=1 [import_laws] 拒绝执行：CHROMA_DIR=…other-chroma_db 指向与本脚本目标…不同
B: --validate-only   -> rc=1 未找到导入文件 …（不碰库，符合豁免判据）
C: --val             -> rc=1 拒绝执行（同上）
D: (默认写模式)      -> rc=1 拒绝执行
E: --dry-run         -> rc=1 拒绝执行
F: 大小写变体目录     -> rc=1 拒绝执行（同一物理目录，假阳性/保守）
G: env=本树默认       -> rc=0 导入完成，2 条落进 backend/chroma_db
H: env 未设           -> rc=0 导入完成，第 3 条同样落进默认目录（count=3，别的目录始终为空）
```

### 2.4 encode_kwargs 不是信任通道（实测）

```
ctor_kwargs = {"model_name": "x", "cache_folder": null, "device": "cpu"}      # 没有 trust 键
encode_kwargs_seen_by_model = {"show_progress_bar": false, "trust_remote_code": true}
```
⇒ 键只在**加载完成之后**被透传给 `.encode()`，无法影响加载期信任决策。这条**不构成**穿透形状
（任务要求"逐个试"，此为试过后的否定结论）。

### 2.5 快照完整性（复算，跳过大文件）

11 只小文件对官方 sha256 **全部 OK**；`synthetic-pristine` 与快照 11/11 同哈希；
`pytorch_model.bin`（409138989 字节）**未重算**，三处为同一 inode（nlink=3）。

### 2.6 凭据值级扫描（不打印值）

```
env_names_present = [DASHSCOPE_API_KEY, LONGCAT_API_KEY, RERANK_API_KEY, SILICONFLOW_API_KEY, ZHIPUAI_API_KEY]
env_names_absent  = [ADMIN_PASSWORD, JWT_SECRET, LLM_API_KEY]
blobs_scanned = 3021   controls: positive=14（期望>0）, negative=0（期望0）
每把 key：hits = 0
```
辅助路径级读数：`git rev-list --objects HEAD` 里只有 `.env.example`（**没有 `.env`**，0 个 `.env.bak*`）；
`.gitignore:152-154` 自述"`.env.bak-<日期>` 备份里有 13 位明文管理口令、此前只靠 `.git/info/exclude` 兜住"。
⇒ 我**不**据此宣布历史干净：在册 09-30 记录说值曾出现在 `817e7d3`，而该提交是候选祖先（已独立复核）。

---

## §3 漏项清单（对照执行书 checkbox，逐条）

口径：§3.1 = 报告里**一个字都没有**的（沉默项，最可疑）；§3.2 = 做了但口径不符；§3.3 = 附带发现。

### 3.1 沉默项（8 份报告全文 grep "DB-6/7/8/10/11/12/13"、"rerank" 等，命中 0）

| # | 执行书位置 | 要求 | 现状 |
|---|---|---|---|
| 1 | B 单表 `DB-6 / QA 沉淀` | 核普通用户自动沉淀/管理员确认/版本引用门，用合成库证明非法日期/无据条号不能通过免审分支 | **未做、未登记**（报告集里 0 次出现） |
| 2 | B 单表 `DB-7 / 降级` | 既有"不扩大技术降级白名单"保持有效；不得把内容验证失败/TOOL_BUSY 静默改成功 | **未做、未登记**（无任何验证读数） |
| 3 | B 单表 `DB-8 / 换嵌入` | 新索引验证后再切换、维度/来源校验、失败保留旧索引；仅合成库 | **未做、未登记**（只登记了"CLI 未调用"，那是另一件事） |
| 4 | B 单表 `DB-10/11/12 / 安全文档` | 据源码更正令牌吊销、不可按用户清除的 QA 数据、明文公网启动教程 | **未做、未登记** |
| 5 | B 单表 `DB-13 / WAL` | 合成库验证 WAL、**并发**、backup API 恢复；主库启动行为变更先裁定 | **半做**：WAL 形状/backup API 已由 E.3 覆盖；**并发**与"主库启动行为变更裁定"**未做、未登记** |
| 6 | E 单第 1 条后半 | "**rerank 是否云端**看实际非敏感路由，不沿用'rerank 本地'的印象" | **未做、未登记**（全报告 0 处讨论 rerank 路由；F 单 NOT_RUN 不能替代 E 单这条实核） |
| 7 | E 单第 5 条 | 合成旧格式→新候选→查询对照→**切换失败保持旧索引** | **未做、未登记**（与 DB-8 同源；这是 E 单里唯一整条没被承认的实验） |

### 3.2 做了但口径不符 / 只做了半条

| # | 执行书位置 | 要求 | 现状 |
|---|---|---|---|
| 8 | B 单第 2 条 | "统计参数化后的 collected 数……**核对报告的 49 条增量**，差异写明" | 报告只对账了本轮 +24（1901→1925）；**49 条增量没人对**。我量了四只接收测试文件：`48 tests collected in 38.79s` ⇒ 与"49"差 1，未见归因 |
| 9 | B 单第 1 条 | "每个新增判据需以旧源码/同形坏样本为负控" | 本轮新写的三只文件有负控（`test_canary_itself_can_go_red`、`test_legacy_always_fallback_shape_cannot_pass_S2`、`_refusing_default` 替身）；**接收的四票**只有 D-4 侧能指到负控，DB-15/17/18 的负控未见登记 |
| 10 | E 单第 3 条 | "测试 WAL、已有目标拒绝、**损坏备份**、缺额外库、路径分歧、半途失败、不覆盖原输入" | 前六项能指到证据；"损坏备份"两条腿（`test_backup_data.py:42`、`:233`）都是 **monkeypatch 把 `verify_sqlite` 换成返回 `(False,'corrupt')`**，**没有一只真被截断/损坏的备份包**（口径=模拟，非实物） |
| 11 | E 单第 4 条 | 错绑定实验必须"在**首次打开源路径之前**拒绝" | `import_laws` 有子进程级行为证据（输入是故意不存在的路径）；`backup_data` 侧只有 `_check_env_contract()` 的**单元级**直接调用 + `__main__` 顺序，属**结构论证**（可接受，但两族证据强度不同，报告没区分） |
| 12 | H 单第 4 条 | 受限包装要分别验证"无匹配 / **不可读输入** / **异常 stderr** / **路径夹带秘密**" | `shape_scan_staged_set.py` 只有正对照 + 0 命中（射程声明写得很诚实）；后三类**未验**（无读数、也无"未做"登记） |
| 13 | H 单第 6 条 | 本地等价门禁含"dispatch 守卫" | 本轮证据目录无 dispatch 守卫读数（`pytest dispatch-output/agent-quality-20260911/test_budget_guard.py` 未跑）；`ci.yml:42` 里它是 CI 步骤，但"本地等价"这条没闭合（I 单命令清单里有它） |

### 3.3 附带发现（不在上表，但会改变结论强度）

- **未上锁的索引写入口 4 只**：`import_docs.py`（`_col().delete` ×2）、`verify_new_law.py`（`col.delete` + `add_text` ×4）、`eval_chunking.py`（`vectorstore._collection.delete` + `add_documents`）、`backfill_time_meta.py`（`col.update`）。B-45 的"三类动作里唯一没被检查的"应改成"本单一类；同类至少还有这四只"。
- **`loader-trust-mutants.log` 只留到 M2 的读数**：M1 的"4 errors"与 M3 的"4 passed"在该日志里**没有对应行**（脚本 grep 模式 `^([0-9]+ (passed|failed)|FAILED)` 不含 "errors"；M3 行也未落盘）。我用同形变异复算：M1 = `4 errors in 2.89s`（与报告一致）、基线 = 4 passed ⇒ 读数是对的，但**日志不支撑它**，复算入口应补 `-aE "error"` 或直接存原始输出。
- **`chromadb` 遥测报错在所有我的 run 里同样出现**（`capture() takes 1 positional argument but 3 were given`）⇒ 报告"遥测在参数绑定阶段就失败、从未走到 socket"的复确认**成立**。

---

## §4 已知限制（我的复核与"真第三方"差在哪）

1. **未重跑全量 1925**：我只重跑了本次要挑的三只文件（15 passed = 4+7+4）、四腿变异与守卫/臂矩阵。全量那 1925 与 86.35% 覆盖率我**未复核**（时间盒），它们仍只是报告读数。
2. **409MB 权重哈希按指示跳过**：快照大文件完整性依赖报告自己的 JSON。
3. **真实数据对象一律未碰**：真实 chroma 目录"有 sqlite3 + hnsw 二进制"是**我自造最小持久库**量到的形状 + `backup_data.py` 注释（362MB）推的，不是读实库读出来的。
4. **远端不可达**：GitHub/远端 refs 我读不到（沙箱），B4 只核了本地祖先与对象集合；"远端到底有什么"仍未核。
5. **值级扫描的射程**：只覆盖"本进程 env 里存在的那 5 个值"×"当前 push 对象集合"；**不能**推翻"历史里曾有旧明文"（在册记录恰恰说有）。0 命中只等于"这几个现值不在待推对象里"。
6. **候选在动**：复核期间多出 `a934fa7`，且 `reports/` 目录在我工作期间被追加（`decisions-needed-20261010.md`、`local-environment-switch.md`、`gates.md` §8 是后到的）。我的结论绑在"我读到的那一版"上，引用了时间戳的地方都写在正文里。
7. **未做浏览器/前端口径复核**（另一助手在做 D 单，且我被要求不碰端口与浏览器）。
8. **我的实验脚本本身是一台自制仪器**：如 2.1 的穿透腿只是**证明"静态四腿不足以排除 opt-in"**，不代表产品当前有洞；真正要收紧得改测试或在产品侧加运行时断言——那是新票，不是本轮结论。
