# 运行对象归属与收尾补证执行方案 v2（2026-10-09，已按两路评审改过）

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:executing-plans 逐 Task 执行并复核。步骤用 `- [ ]` 记账，**不因文档生成就勾选**。命令按 Git Bash 给出；每条命令都要把 cwd、原始 stdout/stderr 与退出码存进 `<ROOT>/evidence/`。
>
> **v1 被评审判为不可执行，v2 逐条改了。** 评审发现与我自己的复核记录见文末 `## 评审处置`（含一条我判评审错、不采纳的）。


> **执行状态（2026-10-09）**：Task 1–7 共 29 步已全部真跑完并勾选；每步的日志/rc 见 `<ROOT>/evidence/cmd-t*.log`，读数汇总在 `<ROOT>/reports/results.md ## 14`。勾选发生在执行之后，不是因为文档生成。
**Goal:** 证成"哪套解释器真的承载哪个入口面"的矩阵，据此把 R-1/R-5/R-6/R-7 的适用性结论按对象重绑；补上本轮评审未闭合的请求台账；把三处零证据残余换成**对残差敏感**的静态断言；最后把待签事项收成一张可一次裁的审批单。**不改产品字节、不提交、不发布。**

**Architecture:** 保留既有应用边界（单 worker、嵌入式 Chroma、镜像内 requirements 加单独安装的 CPU torch、Caddy 对外 8088）。本方案只做两类动作：只读取证、在独立副本里加测试。一切会改产品字节/环境/数据/出网的动作留给 F0/F1a/F1b/F2/F4/F5 分支另批。

**Tech Stack:** Windows / Git Bash、Python 3.11.0（两套实装 venv 加两套不可离线测的形状）、FastAPI、SQLite/Chroma 嵌入式、Next.js 14.1.0 + React 18.2.0、既有 Vitest 2.1.9 + TypeScript 5.3.3（不新增依赖）。

## Global Constraints

- 主仓 `C:/Users/33393/Desktop/ai-legal-helper`，HEAD 应为 `0b543960c7172ce1ffea57616952e4d5525190c4`，master，暂存区为空，tracked 修改**恰好六处**。任何一步让这四项变形即为失败。
- 交付根固定为 `C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527`（下称 `<ROOT>`）。新产物只写 `<ROOT>` 内；往主仓只允许新增**未跟踪**计划文件本身，且必须登记未跟踪数变化（当前实测 **34158**，含本文件）。
- **不读**真实 `.env`、凭据值/片段/长度/哈希、数据库（`backend/data/app.db`、`quota_used.sqlite`、以及 `backend/backups/app_pre_cleanup.db`，实测 10,326,016 字节，就在备份目录里）、Chroma 真实库内容、私有语料、模型权重载荷。**教训钉死：把路径登记进哈希器就等于读它**（`<ROOT>/evidence/incident-01-db-hash-overreach.json`）。
- **`backend/backups/*/*.json` 一律不打开**（v1 的"大于 200000 字节才跳过"是假保护：`backup_manifest.json` 实测 11,613 字节，而按 `backup_data.py:195-234` 与 `:259` 它的正文含 `app.db` 与附加 sqlite 的 `bytes`+`sha256`，以及 media 逐件相对路径加 sha256 —— 两把库的摘要和私有上传文件名都在里面；`chroma_index.json` 1,317,497 字节由 `export_chroma_json` 从真实集合导出，属禁止对象）。允许的动作只有：列目录、取文件名与字节数、不解析内容。
- **上一轮证据只读**：不回填、不改写 `<ROOT>/evidence/cmd-c1..c5*.log` 与已交付正文；要更正就新增文件并在正文标注"被某日新日志取代"。
- 不 `git add/commit/merge/fetch/push/PR`、不触发 CI、不清理未跟踪文件、不动六处残余、不改产品源码。
- 不启动/重启/停止任何服务或容器；不占 3021/8088 或他人端口；本方案**不含浏览器阶段**（F2 另批）。
- 不安装/升级依赖；不向任何 venv 写包；不下载 wheel/权重。既有 `frontend/node_modules` 只能以 Junction 复用。只许 import `packaging`（实测两处 venv 均有 `packaging-23.2.dist-info`）；**不许 import 后端主入口、`rag_chain` 或任何模型加载器**。
- 网络：本方案 **0 次新请求**。两条候选出口（T12a PyPI 原始件、T12b BGE 官方 revision 元数据）各自单列审批，未批即不跑。
- 数字与断言：每个进正文的读数必须给可复算命令与**分母名**（本轮已因"15,288"翻车；真实口径是 10,266 分片 / 1,528 公开条文）。禁止把一个分母去"对上"另一个分母。
- 判据形状：只警告不算通过；"没命中"必须自带**咬得住那条否定式**的阳性对照（v1 用 `Depends(...)` 命中数去证 `^@app\.` 的完备性，是错的对照）；恒不可能命中的断言标"不可观测支"，不计入证据。
- **每个步骤都要写出"红了怎么办"**。只描述绿灯结果的步骤不合格（v1 有 5 处，见 F-19）。
- 本方案的写入面**不进入** `closeout_check.py` 的在册输入（实测 133 条注册路径里 0 条在 `<ROOT>` 下）：它证明的是约束未违反，不证明质量。任何"GAP 已修"的结论必须由正文 grep 与逐条行号支撑。

---

## Task 1: 运行对象归属矩阵（两套实装 venv 加两套不可离线测的形状）

**背景（已现量，勿重复劳动）：**

- `backend/venv/pyvenv.cfg` = `version = 3.11.0`、`home = C:\Users\33393\AppData\Local\Programs\Python\Python311`、创建命令含 `-m venv --clear`、mtime `2026-07-30 04:06:46 +0800`；site-packages 形状是 **`venv/Lib/site-packages`**（`venv/lib/python3.11/site-packages` 不存在）；分发 **181**。关键版本实测：`sentence_transformers-2.7.0`、`transformers-4.57.6`、`fastapi-0.110.3`、`chromadb-0.4.24`、`torch-2.6.0+cpu`、`langchain_core-0.1.53`、`langsmith-0.1.147`、`openai-1.109.1`、`pillow-12.3.0`，另有 `cfgv-3.5.0`、`git_filter_repo-2.47.0`、`isympy` 的源码与 pyc 同时在（形状像开发/运维工具箱）。
- **但 `backend/venv` 不等于当前依赖声明**：`backend/requirements.txt` 钉 `sentence-transformers>=6.0,<7.0` 与 `fastapi==0.141.1`（实测），而该 venv 是 2.7.0 / 0.110.3 ⇒ 它是**旧的手装环境**，不是按现声明装出来的。矩阵必须把这一条写成独立结论，不能只写版本号。
- `joint/venv` 分发 **163**（同 `Lib/site-packages` 形状），`sentence_transformers-6.0.0`、`transformers-5.17.0`。
- `backend/backups/` 恰有三个时间戳目录 `20260907_200448`、`20260919_163503`、`20260919_192441`；`D:/backups` 不存在。目录内另有 `app_pre_cleanup.db`（禁止打开）。
- `docs/OPS.md:135` 确为 `venv\Scripts\python.exe scripts\backup_data.py --out D:\backups`，但它在 `## 8. 备份排程（建议，未内置）` 的 `schtasks /Create` 建议块里，且 `OPS.md:39-40` 写"目前**手动运行**"，而 `--out` 目标 `D:\backups` 不存在 ⇒ **那行文档是一条没被照做的建议**；实际备份落在默认 `--out`（`backend/backups/`）。
- 嵌入链实测：`main.py:113 from rag_chain import ... embeddings` ⇒ `rag_chain.py:25 from langchain_huggingface import HuggingFaceEmbeddings`、`:44 model_name="BAAI/bge-base-zh-v1.5"`、`:108` 模块级 `embeddings = QuotaTrackingEmbeddings(_build_embeddings())`；`settings.py:192` 默认 `embedding_provider=local`；`langchain_huggingface/embeddings/huggingface.py:53 import sentence_transformers`、`:61 self.client = sentence_transformers.SentenceTransformer(...)`。`scripts/rebuild_embeddings.py` 模块级 `from rag_chain import ... embeddings` ⇒ **运维 CLI 在 `backend_venv` 里真会加载 ST 2.7.0**。

**Files:**
- Create: `<ROOT>/scripts/env_attribution.py`、`<ROOT>/evidence/env-attribution.json`、`<ROOT>/evidence/cmd-t1-*.log`、`<ROOT>/reports/t10-environment-attribution.md`
- Read-only: 两 venv 的 `pyvenv.cfg` 与 `*.dist-info`、`backend/requirements*.txt`、`backend/Dockerfile`、`docker-compose.yml`、`.github/workflows/ci.yml`、`backend/docs/OPS.md`、`backend/main.py`、`backend/rag_chain.py`、`backend/settings.py`、`backend/scripts/backup_data.py`；`backend/backups/` **只列目录**

**Interfaces:**
- Produces: `evidence/env-attribution.json`，结构 `{"schema":"closeout-env-attribution/2","envs":{"<envid>":{"python":str|null,"created":str|null,"distributions":int|null,"site_packages":str,"key_versions":{pkg:ver},"declared_vs_installed":[],"entry_surfaces":[str],"proven_used_by":[{"evidence":"file:line"}],"measurable":bool,"why_not":str|null}}}`；`envid ∈ {joint_venv, backend_venv, image_runtime, ci_runtime}`，Task 2 按同一集合引用。

- [x] **Step 1: 一次扫两套实装 venv 的分发与关键版本（只读元数据）**

写成脚本文件再跑（heredoc 里反斜杠会被折叠，本轮已栽过）：

```bash
cd C:/Users/33393/Desktop/ai-legal-helper/backend
python "C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527/scripts/env_attribution.py" \
  > "C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527/evidence/cmd-t1-distlists.log" 2>&1
echo "rc=$?"
```

脚本要求（v1 有两只仪器自带错，必须避免）：
1. `roots` 含**两只** venv：`backend_venv` 指 `C:/Users/33393/Desktop/ai-legal-helper/backend/venv/Lib/site-packages`，`joint_venv` 指 `C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Lib/site-packages`。
2. 关键字表**每条只写一种拼法**（v1 同时写 `sentence-transformers` 与 `sentence_transformers`，归一化后后者恒 `ABSENT`，会撞上我自己的"任一 ABSENT 就停"规则 ⇒ 纯仪器伪影）。表：`sentence-transformers`、`transformers`、`torch`、`chromadb`、`fastapi`、`starlette`、`langchain-core`、`langchain-huggingface`、`langsmith`、`openai`、`pillow`、`numpy`、`pydantic`、`uvicorn`、`packaging`、`pip-audit`、`pre-commit`。
3. 归一化用 `name.lower().replace("_","-")`，并且**打印 ABSENT 集合本身**；停跑规则只在该集合里的名字确实应存在于服务运行时时才触发，脚本要区分"预期缺席"（如 `pip-audit` 在 venv 里可缺席）与"意外缺席"。
4. 顺带打印 `site-packages` 绝对路径与 dist-info 计数，供正文引用。

预期：`backend_venv distributions=181`、`joint_venv distributions=163`；`packaging 23.2` 两边都在。任一关键版本与上面背景不符 ⇒ 停下重读目录，不许凑数，并在 §14 记不符项。

- [x] **Step 2: `image_runtime` 与 `ci_runtime` 显式判为不可离线测**

```bash
cd C:/Users/33393/Desktop/ai-legal-helper
grep -nE "^FROM|RUN pip install|COPY requirements" backend/Dockerfile | head -12
grep -nE "python-version:|pip install torch|pip install -r|pytest --cov|pip-audit" .github/workflows/ci.yml | head
```

结论必须写死：`image_runtime` 的实装版本只能从 `Dockerfile` 声明**推断**（不是分发元数据读数），`ci_runtime` 的 torch 未钉版（`ci.yml:22` 是 `pip install torch --index-url .../whl/cpu`）⇒ 两只都 `measurable=false`、`why_not` 分别写"禁启容器，未 exec 进镜像"与"禁触 CI，且 torch 无版本钉"。**这两只不得参与 Task 2 的行展开**（v1 会生成无版本行，把"未证"伪装成一行数据）。

- [x] **Step 3: 运维 CLI  import 什么 —— 决定 ST 2.7.0 是活的还是潜伏的**

```bash
cd C:/Users/33393/Desktop/ai-legal-helper/backend/scripts
for f in backup_data.py restore_drill.py rebuild_embeddings.py switch_embedding.py gen_gate1_law_check.py recompute_boundary_manifests.py; do
  echo "### $f"; grep -nE "^(import|from) |SentenceTransformer|HuggingFaceEmbeddings|import chromadb|import torch|sqlalchemy|sqlite3|rag_chain" "$f" | head -16
done
echo "rc=$?"
```

逐脚本记是否 import sentence-transformers / chromadb / torch、以及是否经 `rag_chain` 间接触发嵌入链。已实测的形状：`backup_data.py` 顶层 sqlite3 加 `:109` lazy `import chromadb`；`restore_drill.py:34` lazy chromadb；`rebuild_embeddings.py` 模块级 `from rag_chain import ... embeddings` 且 `:95/:130/:193` lazy chromadb；`switch_embedding.py` 引 rebuild_embeddings 且 `:82` lazy chromadb；`gen_gate1_law_check.py:82` lazy chromadb；`recompute_boundary_manifests.py` 只 sqlite3 直读 `chroma.sqlite3`。
**红路**：若某脚本既不 import 也不经 `rag_chain` ⇒ 该行归"该面不承载嵌入链"，不得凭"它是运维脚本"推断它加载 ST。

- [x] **Step 4: 备份只列目录，不打开任何 JSON（v1 此处会读到库摘要与私有文件名）**

```bash
cd C:/Users/33393/Desktop/ai-legal-helper/backend/backups
python - <<'PY'
import os, json
rows = []
for root, dirs, files in os.walk("."):
    for fn in files:
        p = os.path.join(root, fn)
        rows.append({"path": p.replace(os.sep, "/"), "bytes": os.path.getsize(p),
                     "mtime": round(os.path.getmtime(p), 1)})
rows.sort(key=lambda r: r["path"])
print("files=%d" % len(rows))
for r in rows:
    print("%12d  %s  %s" % (r["bytes"], r["mtime"], r["path"]))
print(json.dumps({"opened_any_json": False, "note": "内容未解析：manifest 含库摘要与私有上传路径，属禁止对象"}, ensure_ascii=False))
PY
echo "rc=$?"
```

判据只允许两种表述：**"备份包存在三个时间戳 ⇒ `backup_data.py` 确实被运行过"**，以及**"运行它的解释器：未证"**，理由写死：**本机没有任何产物记录运行解释器**（`backup_data.py:265-270` 的 payload 只有 `{"version": 1, "created_at": ...}`，其中 `version` 是清单 schema 版本；全目录 grep `sys.version|platform.python_version` 只命中 `eval_agent.py`，不在备份路径上）⇒ 矩阵里"运维 CLI 承载解释器"这一格**结构上取不到 `已证`**，`未证` 是本步的预期结果而不是失败。v1 用 JSON 序列化串里是否含 `version` 子串当判据，是**恒真探针**，删除。
**红路**：若目录列表与背景三条时间戳不符 ⇒ 说明有并行会话写入，立即记 `boundary_breach` 并停止本 Task 的"未被使用"推论。

- [x] **Step 5: 落矩阵与逐面结论**

`reports/t10-environment-attribution.md` 的表必须逐入口面给，每格"承载解释器"只允许 `已证`、`未证（缺什么）`、`不适用` 三值：

| 入口面 | 承载解释器 | 证据 | 严重性 |
|---|---|---|---|
| 服务（HTTP 请求路径） | 未证 —— 禁启容器 ⇒ 容器内实装不可读；仅能引 `Dockerfile:41-45` 声明 | 声明 `sentence-transformers>=6.0,<7.0` 与 `chromadb` 区间；`requirements.txt:8 langchain-huggingface` | 高（嵌入链模块级实例化，ST/TF/torch 都在服务面） |
| 运维 CLI（备份/还原/重建/换嵌入） | **已证（重建/换嵌入两支）**：`backend/venv` + `rebuild_embeddings.py` 模块级 import `rag_chain.embeddings` | Step 3 逐脚本行号 | 高（ST 2.7.0 / TF 4.57.6 落各自公告区间内） |
| 备份/还原 CLI 用哪套 | 未证（无产物记录解释器；OPS.md:135 是未照做的建议行） | Step 4 判据 | 中（不改变上两行结论） |
| CI 门禁 | 不适用（`ci.yml:19` 装 3.11，`:22` torch 未钉版 ⇒ 本轮不可知） | Step 2 读数 | 低-中（T2 待签） |
| 本轮分析所绑 | `joint_venv` | `evidence/distributions-before.json` 163 条 | 参照物 |

`docker-compose` 那格用可反证的话写：**`backend` 服务（`docker-compose.yml:16` 起）无 `ports:` 映射，宿主侧 `8088:80` 由 caddy 发布（`:76-77`）⇒ 对外监听面存在但经反代，嵌入式 Chroma 无直接宿主端口**。复算命令 `grep -n "ports:" docker-compose.yml` 应恰得 1 命中且在 caddy 块内。

---

## Task 2: 把 R-1/R-5/R-6/R-7 按对象重绑（离线，不联网）

**Files:**
- Create: `<ROOT>/scripts/advisory_env_matrix.py`、`<ROOT>/evidence/advisory-env-matrix.json`、`<ROOT>/evidence/cmd-t2-matrix.log`
- Modify: `<ROOT>/reports/b-dependency-route.md`（新增 `## B8 对象重绑`）
- Read-only: `<ROOT>/evidence/advisories/advisory-digest-from-archive.txt`、`<ROOT>/evidence/pypi-vuln-digest-from-archive.txt`、`C:/Users/33393/Desktop/fazhi-release-preflight-20261008-02b95968ef4541858da309bc26aaf703/evidence/advisories/ID_GHSA-*.json`（实测 17 只、25 条 vulnerability 记录）、两 venv 的 dist-info、`<ROOT>/evidence/requires-dist-installed.json`

**Interfaces:**
- Consumes: Task 1 的 `envid`，且**只展开 `measurable=true` 的两只**。
- Produces: 行结构 `{env, package, version, advisory, ecosystem, affected_string, first_patched, in_range:bool, surface_basis, surface_chain, fix_available, label}`。
  - `surface_basis ∈ {实例化链, 声明依赖, 公告函数命中, 不可判}` —— 取代 v1 的 `entry_surface_uses: bool`（v1 那个布尔没有真值来源：实测 25 条记录的 `vulnerable_functions` **全为空**，唯一能落它的字段是空的，于是只能退回 §12.3 已被推翻的"应用不 import torch"）。
  - `surface_chain` 填 `file:line -> file:line`，例：`rag_chain.py:108 -> rag_chain.py:25 -> langchain_huggingface/embeddings/huggingface.py:53`。
  - `fix_available ∈ {released, pre-release-only, none}`（`none` 对应 `first_patched` 空；`pre-release-only` 对应实测 `fixed_in=['2.7.1-rc1']` 那类）。
  - `label` 由下面**写死的优先级表**从三个正交字段派生，不另立新事实：`in_range ∧ surface_basis≠不可判 ∧ fix_available=released` ⇒ "区间内且该面真用它且有修复版"；`in_range ∧ fix_available=none` ⇒ "区间内且该面真用它但无修复版可升"；其余按 `in_range` / `fix_available` 逐级降级。

- [x] **Step 1: 写矩阵生成器（只用 stdlib 加实测存在的 `packaging`）**

```python
# scripts/advisory_env_matrix.py
# 解释器必须点名，不用 PATH 上的 python（本机 PATH python 缺 chromadb，会 rc=4）：
#   JOINT = C:/Users/33393/Desktop/fazhi-next-local-20261004-.../joint/venv/Scripts/python.exe
# 开头先跑一次自检并打印：解释器绝对路径、sys.version_info、packaging.__version__；
# import packaging 失败才退回元组比较器，且把所有含 a/b/rc/dev 的行记 UNPARSED，不得"剥后缀"再比。
```

区间解析规则要覆盖实测存在的四种形状（v1 只写三种，会把 25 条里 5 条以上扔进 UNPARSED）：

| 形状 | 实例（本轮归档原文） | 判定 |
|---|---|---|
| `< X` | `< 5.6.0`、`< 1.2.11` | `ver < X` |
| `<= X` | `<= 0.7.30`、`<= 0.3.79`、`<= 0.3.84`、`<= 0.5.18` | `ver <= X` |
| `>= A, <= B` | `>= 0.4.17, <= 1.5.9` | `A <= ver <= B` |
| `>= A, < B` | `>= 1.0.0a1, < 1.2.28` | `A <= ver < B`（含预发布，必须用 `packaging`） |
| 其他 | —— | 记 `UNPARSED`，正文单列，不猜 |

另有一条 v1 完全没有的规则：**一只 `ID_GHSA-*.json` 里最多有 4 条记录、跨 pip/npm 与不同包名**，所以取行之前必须先过滤 `ecosystem == "pip"` 且 `package ∈ 该 env 实装集`；不写这条就会把 npm 行（如 langsmith `0.5.19`/`0.6.0`）当成本轮 Python 修复依据 —— 那是上一轮明确撤回过的错。
**红路**：任一 UNPARSED ⇒ 逐条进正文"未判清单"，不许手工改成想要的结果；`packaging` 自检失败 ⇒ 记"本轮语义比较降级"，并冻结含预发布的行。

- [x] **Step 2: 跑矩阵并核四处关键翻转**

```bash
cd C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527
"$JOINT" scripts/advisory_env_matrix.py > evidence/cmd-t2-matrix.log 2>&1; echo "rc=$?"
```

预期这些行成立，且逐条回读归档原文：
1. `backend_venv sentence-transformers 2.7.0` ∈ `GHSA-jhr6-gm9c-rqjv` 的 `< 5.6.0`，`fix_available=released`（5.6.0），`surface_basis=实例化链` ⇒ **该面区间内**。
2. `backend_venv transformers 4.57.6` ∈ `GHSA-29pf-2h5f-8g72` 的 `< 5.3.0` ⇒ **该面区间内**。
3. `chromadb 0.4.24` ∈ 两条 Chroma 的 `>= 0.4.17, <= 1.5.9` 且 `first_patched` 空 ⇒ `fix_available=none`。v1 要求这一行同时满足"区间内且该面真用它"和"恒为无修复版可升"，而 `verdict` 是单值 ⇒ 构造上取不到；v2 用正交字段消掉这个矛盾。
4. `joint_venv sentence-transformers 6.0.0` / `transformers 5.17.0` ⇒ `in_range=false`，`label` 必须是"版本在区间外（仅限 joint_venv）"。
**红路**：任一预期行没出现 ⇒ 先怀疑过滤/解析，改匹配器重跑并留两份日志，不手工补行。

- [x] **Step 3: 分母各自钉住，不再"互相配上"**

v1 要求把 §12.3 的"0 闭合 / 2 前置未消 / 20 未评"与矩阵行数对上 —— 做不到，因为它们是三个不同分母（`0+2+20=22` 是 **torch 的 CVE 簇**数；矩阵行是 env × package × advisory 的展开）。v2 改成各自给命令、各自命名：

```bash
cd C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527
echo -n "matrix_rows="; python -c "import json;print(len(json.load(open('evidence/advisory-env-matrix.json',encoding='utf-8'))['rows']))"
echo -n "torch_cve_clusters="; grep -o "CVE-[0-9]*-[0-9]*" evidence/pypi-vuln-digest-from-archive.txt | sort -u | wc -l
echo -n "torch_empty_fixed_in="; grep -c "fixed_in=\[\]" evidence/pypi-vuln-digest-from-archive.txt
echo -n "in_range_and_used_rows="; grep -o '"in_range": true' evidence/advisory-env-matrix.json | wc -l
```

写进正文时必须带轴名（例：`pypi-vuln-digest 全量 27 个 distinct CVE / 其中 fixed_in 空 13 条`），并**回查旧句**：§B3b 与上一轮执行书里"4 簇空补丁"那句若与本轮 `fixed_in=[]` 计数口径不同，要就地按轴改写而不是复制。
**红路**：若 `matrix_rows` 与预期展开数不符 ⇒ 先打印行清单按 env/package 分组核对，禁止用 `head` 截断当全集。

---

## Task 3: 触 chroma 写面的路由到调用图两跳（补 §12.5 的"没穷举"）

**Files:**
- Create: `<ROOT>/scripts/chroma_write_routes.py`、`<ROOT>/evidence/chroma-write-routes.json`、`<ROOT>/evidence/cmd-t3-*.log`
- Modify: `<ROOT>/reports/b-dependency-route.md`（`## B1b` 加第 4 条结论）

**Interfaces:**
- Produces: 每条 `{route, method, route_line, auth_dependency, auth_line, hops:[...], reaches_write_site, untrusted_fields, verdict, covered_by:"两跳"}`。
- **措辞从"穷举"改成"穷举到调用图两跳；三跳以上未覆盖 = 已知限制"**（v1 的"穷举"已被一条真实可达写面否证）。

- [x] **Step 1: 枚举路由与鉴权依赖**

```bash
cd C:/Users/33393/Desktop/ai-legal-helper/backend
grep -nE "^@app\.(post|put|patch|delete)" main.py | tee /dev/stderr | wc -l
grep -nE "^@app\.get" main.py | wc -l
grep -nE "Depends\((require_admin|get_current_user)" main.py | wc -l
grep -rn "APIRouter\|include_router\|add_api_route" *.py | wc -l
```

实测锚点：`post/put/patch/delete` 22 条、含 `get` 共 40 条、`Depends(require_admin` 22、`Depends(get_current_user` 15、`Depends(require_user` **0**（`auth.py` 只定义了前两个；v1 把 `require_user` 放进匹配式是空头一项）。本仓**无 `APIRouter`**，装饰器都在 `main.py` 顶层且无缩进 ⇒ `^@app\.` 锚点在本仓是安全的。
**红路**：`post/put/patch/delete` 不等于 22，或 `APIRouter` 计数大于 0 ⇒ 锚定式失效或有第二路由源，改用不带 `^` 的形态重跑、留两份日志，并把差异记进正文。

- [x] **Step 2: 两跳闭合（v1 的字符串拼接看不见写面）**

写面函数名集合要先由宽匹配取得，再逐个反查调用者：

```bash
cd C:/Users/33393/Desktop/ai-legal-helper/backend
grep -rnE "add_texts?\(|add_documents|_collection\(\)\.(add|upsert|delete)|_qa_store|create_candidate|decide_candidate|add_qa_pair" \
  main.py knowledge_service.py knowledge_base.py retrieval.py rag_chain.py
```

对每个写面名 `NAME` 跑 `grep -n "NAME(" main.py` 与 `grep -n "NAME," main.py`（**两条都要**：`run_in_threadpool(_post, pre, answer)` 里 `_post` 后面是逗号不是括号，v1 用 `_post\(` 只得到 def 行，会漏掉全部 6 个调用点）。
已实测的必须出现的一条链（这是本 Task 的预测，跑不出来就是匹配器坏）：

```
@app.post("/api/chat")  main.py:1791
  -> Depends(get_current_user)  main.py:1793   （非 require_admin）
  -> run_in_threadpool(_post, pre, answer)  main.py:2130 / 2377 / 2596（curate 默认为 True）
  -> ks.create_candidate(...)  main.py:1015
  -> grounded_score >= AUTO_CURATE_THRESHOLD(0.89)  knowledge_service.py:392,398
  -> add_qa_pair  knowledge_service.py:315 -> _qa_store.add_documents  knowledge_service.py:343
```

第二条：`POST /api/admin/qa/{cand_id}/decision`（`main.py:2995` 调 `decide_candidate`）→ `knowledge_service.py:450 add_qa_pair`。第三条：`knowledge_base.py:48 vectorstore.add_documents`（种子重建，v1 的三文件清单里没有它）。
判据要求：每条"不可达"必须指出**哪一行的哪个依赖**挡住；依赖是 `get_current_user` 的路由一律写"**认证用户可达**"，不得写"不可达"。找不到挡住的行就写"未证"。
**红路**：写面链少于 3 条 ⇒ 放宽一跳再跑，把放宽过程记进日志；两跳确实穷尽仍少于 3 ⇒ 说明读的是旧树，停并按 HEAD 复核。

- [x] **Step 3: 三条各自咬住一条否定式的对照（v1 只有一条错靶对照）**

1. 路由匹配器对照：`^@app\.(get|post|put|patch|delete)` 应得 40，`^@app\.(post|put|patch|delete)` 应得 22 ⇒ 差的 18 条 GET 是**设计排除**；随后必须列出"有无 GET 路由的处理函数走到写面"，若有则 GET 排除不成立。
2. 文件清单对照：**必须**命中 `knowledge_base.py:48` 的 `vectorstore.add_documents`；命中不到即证明清单漏文件。
3. 调用图对照：**必须**命中 `POST /api/chat` 那条链（Step 2 预测）。
三条都过才允许写"两跳内已穷举"。任一不过 ⇒ 改匹配器重跑，不得把该行发出去。

---

## Task 4: 评审未闭合请求台账与四项补写（只动 `<ROOT>`）

**先记账再修。** 实测：`apply_patch`、`五问`、`Get-Command`、`ended=` 四个词在本轮所有 `reports/*.md` 里 **0 命中** —— 评审提出的这些请求只活在我与 Owner 的对话里，从没落进交付正文（这正是上一轮被钉过的失误类）。所以 Step 0 不是补装饰，是把请求变成可核的在册条目。

**Files:**
- Modify: `<ROOT>/reports/work-report.md`（新增 `## 7. 评审未闭合请求台账（2026-10-09 方案轮登记）`）
- Modify: `<ROOT>/reports/a-baseline.md`（§A7 补 apply_patch 等价说明）
- Modify: `<ROOT>/reports/c-residual-validation.md`（`## C0` 补原始读数）
- Modify: `<ROOT>/reports/results.md`（新增 `## 13（2026-10-09 方案轮）五问自审`）
- Modify: `<ROOT>/scripts/closeout_check.py`（新增 `ended=` 输出，只影响**今后**运行）
- Create: `<ROOT>/evidence/cmd-t4-toolprobes.log`、`<ROOT>/evidence/incident-02-c5-ended-absence.json`

**Interfaces:** 每项都要能被 `grep` 验证"确已写进正文"，且 Step 3 的 grep 是**内容级**（grep 具体测量值），不是"正文里有这句话"。

- [x] **Step 0: 登记台账**：§7 表格三列 `请求 | 来源轴 | 本轮处置（含行号）`，逐条来自 §6 与本方案；对每条给"我复核了什么"。
- [x] **Step 1: §A7 补等价说明**：本会话主 harness 无 `apply_patch`，人工文件经 Write/Edit 落盘；必须写"**实测** CR 计数 = 0（给命令）"，而不是主张工具等价。命令：`python -c "import sys;d=open(sys.argv[1],'rb').read();print(d.count(b'\r'))" <file>`。
- [x] **Step 2: C0 补工具原始读数**

```bash
cd C:/Users/33393/Desktop/ai-legal-helper/frontend
{ command -v node; node -v; command -v npm; npm -v;
  test -f node_modules/vitest/vitest.mjs && echo vitest_ok;
  test -f node_modules/typescript/bin/tsc && echo tsc_ok; } 2>&1
powershell.exe -NoProfile -Command "(Get-Item 'C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527/frontend/node_modules').LinkType"
```

预期末行 `Junction`。原始输出整体存 `evidence/cmd-t4-toolprobes.log`，正文 `## C0` 改为引用该日志文件名，散文断言撤下。**红路**：`LinkType` 不是 `Junction` ⇒ 停，复核复制脚本，不带可疑链接跑测试。
- [x] **Step 3: `ended=` 的正确处置（v1 这条会改上一轮证据）**：实测 `cmd-c1..c4` 各有 1 个 `ended=`，**只有 `cmd-c5-tsc-ruler-probe.log` 没有**，而 c5 属上一轮在册证据 ⇒ **不回填**。改为 (a) 新增 `evidence/incident-02-c5-ended-absence.json` 写明缺失、原因、以及"按约束不回填"；(b) 在 §13 引用它；(c) 修 `closeout_check.py` 让今后运行打印 `ended=`（其 `rc_from_log` 现仅解析 `EXIT_CODE=`，实测 `ended=` 出现 0 次）。
- [x] **Step 4: 勾稽**：对每条 GAP 跑内容级 grep（例如 `grep -c "CR 计数 = 0"`、`grep -c "cmd-t4-toolprobes.log"`、`grep -c "incident-02"`），命中数与**正文行号**一起写进 §13；复跑 `"$JOINT" scripts/closeout_check.py <ROOT> <iso>` 并明确一句：**该判据不含 `<ROOT>` 内路径（实测注册 133 条中 0 条在此），`true` 只证明残余/HEAD/分发/暂存区未变形，不证明 GAP 已修**。
- [x] **Step 5: 五问自审写成 §13**（范围自然 / 为何先证闭包 / 有无缓存污染或模型自评 / 事实出处可核 / DoD 可复验），每问一段且各带**一条本轮实测**；标题带轮名，并在正文点明"不同于 §9 的自审清单"（§9 已有一份五项自审）。新节物理位置排在 §12 之后、`## 11` 之前，沿用 §11 的"次序说明"句法。

---

## Task 5: 三处零证据残余的**残差敏感**静态断言（不装依赖、不进浏览器）

**Files:**
- Create: `<ROOT>/evidence/fixtures/*.head`、`<ROOT>/frontend/tests/closeout.static-gaps.test.ts`、`<ROOT>/evidence/cmd-t5-*.log`
- Modify: `<ROOT>/reports/c-residual-validation.md`（C1/C3 计数表更新、"零离线断言"改为"仅静态且对残差敏感"）

**为什么 v1 的测试不算证据（我逐条实测）：** `h4` 裸选择器断言**必红** —— `globals.css` 里没有 `h4` 选择器，残差实际写的是类 `.answer-h4`（`:898`、`:910`）；`:focus-visible {` 在 **HEAD 上就有 1 处**（`:157`），`md:!text-base` 在 **HEAD InputBar.tsx:191 就有**，`image_chat` 在 **HEAD page.tsx:37 就有** ⇒ 三条在无残差的树上同样为真，没有区分力。而 `md:!text-base` 恰恰是 results.md §8b 用来**否定**"桌面端字号 bug"的同一事实，再断言一遍是自我循环。负向对照 `:focus-never-written-by-us` 恒不可能命中，属重言式。

**v2 配方**：每条断言绑一对 **HEAD / 工作树**读数，形式为"残差里有 ∧ HEAD 里没有"。打红的方式是**换回 HEAD 夹具**，不是改期望值。

- [x] **Step 1: 先测锚点，再写断言（锚点由测得，不由记忆）**

```bash
cd C:/Users/33393/Desktop/ai-legal-helper
mkdir -p "C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527/evidence/fixtures"
for p in frontend/app/globals.css frontend/components/chat/InputBar.tsx frontend/app/chat/page.tsx frontend/app/admin/sections/UploadSection.tsx; do
  git show "HEAD:$p" > "C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527/evidence/fixtures/$(basename "$p").head"
done
for a in "answer-h4" "upload-zone:focus-visible" "text-\[16px\]" "text-\[15px\]" "caps?.image_chat === false" "role=\"button\"" "aria-label=\"上传法律知识文件（回车选择文件）\""; do
  printf "%-52s HEAD=%s NOW=%s\n" "$a" \
    "$(cat "C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527"/evidence/fixtures/*.head | grep -c "$a")" \
    "$(cat frontend/app/globals.css frontend/components/chat/InputBar.tsx frontend/app/chat/page.tsx frontend/app/admin/sections/UploadSection.tsx | grep -c "$a")"
done
```

只有 **HEAD=0 且 NOW≥1** 的字面量才能进断言；**NOW=0 且 HEAD=1** 的字面量（如被残差删掉的 `!text-[15px]`）进"反向断言"（断言它在 HEAD 有、在现在没有）；两边都有的（如 `md:!text-base`）**一律弃用**并在正文列入"不可观测支"，不计入证据。

- [x] **Step 2: 按 Step 1 的白名单写测试**，每条自带同形反例（把锚点里一个字符改成不存在的形状必须红），禁止重言式对照：

```typescript
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const HEAD_DIR = "../../evidence/fixtures/";
const pairs = [
  { cur: "../app/globals.css", head: HEAD_DIR + "globals.css.head",
    added: [".answer-h4", ".upload-zone:focus-visible"], removed: [] },
  { cur: "../components/chat/InputBar.tsx", head: HEAD_DIR + "InputBar.tsx.head",
    added: ["!text-[16px]", "md:flex-nowrap"], removed: ["!text-[15px]"] },
  { cur: "../app/chat/page.tsx", head: HEAD_DIR + "page.tsx.head",
    added: ["caps?.image_chat === false"], removed: [] },
  { cur: "../app/admin/sections/UploadSection.tsx", head: HEAD_DIR + "UploadSection.tsx.head",
    added: ["role=\"button\"", "aria-label=\"上传法律知识文件（回车选择文件）\""], removed: [] },
];

function read(p: string): string {
  return readFileSync(new URL(p, import.meta.url), "utf-8");
}

describe("each assertion is sensitive to the six-residual diff, not to HEAD", () => {
  for (const c of pairs) {
    const cur = read(c.cur);
    const head = read(c.head);
    for (const token of c.added) {
      it(`adds ${token}`, () => {
        expect(cur).toContain(token);
        expect(head).not.toContain(token);
      });
    }
    for (const token of c.removed) {
      it(`drops ${token}`, () => {
        expect(head).toContain(token);
        expect(cur).not.toContain(token);
      });
    }
  }
});
```

- [x] **Step 3: 跑单文件、跑全量、跑 tsc**

```bash
cd C:/Users/33393/Desktop/fazhi-project-closeout-20261008-7e20048efb4e46068a9ecf1a54c6b527/frontend
node node_modules/vitest/vitest.mjs run --config vitest.closeout.config.ts tests/closeout.static-gaps.test.ts
node node_modules/vitest/vitest.mjs run --config vitest.closeout.config.ts
node node_modules/typescript/bin/tsc --noEmit -p tsconfig.closeout.json
```

**为什么必须跑全量（v1 漏了）**：`vitest.closeout.config.ts:8` 的 include 是 `tests/**/*.test.ts`，新文件会**自动进已交付的全量运行**，而交付正文写着"10 files / 93 tests passed, rc=0"（`cmd-c2-full-suite.log`）。只跑单文件就宣布 rc=0 是让旧读数与新套件并存 —— 自我制造的假绿。新日志 `cmd-t5-full-suite.log` / `cmd-t5-tsc.log` 落地，C1/C3 的计数表按 `83 + 10 + N` 更新，并写明旧两条日志"被某日新日志取代"（**不编辑旧日志**）。
**红路**：全量若非 0 ⇒ 逐条定位是"夹具缺文件"还是"锚点选错"，改锚点必须回 Step 1 重测；改不动就删该断言并在正文列入不可观测支，禁止放宽期望值。

- [x] **Step 4: 逐条打红并留证**：对每条断言把 `cur` 指到 `.head` 夹具跑一次（`expect rc≠0`），记录红的**用例名**；每轮打红前后各取一次测试文件与夹具的 sha256，证明还原到原字节。
- [x] **Step 5: 顺手关掉交付里那条"一又二分之一"尺子债**：`offers all six statuses` 与 `upload exposes keyboard semantics` 两条 oracle 从未被故意打红（c-residual-validation.md:60）。本轮各造一个反向样本（在**副本**里删掉一个 `<option>`、去掉 `role="button"`），跑、记用例名与 rc、还原并比 sha。做不动就在 §13 明确列为残余 —— 二者择一，不许含糊。
- [x] **Step 6: 正文老实写边界**：这些断言证明的是"某字面量只在残差里出现"，**不证明**焦点可见、390px 布局、字体计算样式、外发为零。能力位那条只能主张三件事：门存在、`caps` 的唯一写入者来自 `/api/health` 响应（`page.tsx:84-88`）、比较是 `=== false`（**故意 fail-open**：能力位缺失不拦）。交互面仍归 F2。

---

## Task 6: 提交单元与审批单（准备，绝不提交）

**Files:**
- Modify: `<ROOT>/reports/results.md`（§8b 表格加"证据等级"列：已证 / 静态 / 零）
- Create: `<ROOT>/reports/approval-sheet.md`

- [x] **Step 1:** 逐残余重取 `git diff --unified=0 -- <file>`（行号会漂，用时重取），按**证据等级**重排可批单元。现量依据：只有 KnowledgeSection（离线 9 条断言，且 Step 5 之后其 oracle 反向验证过）与 UploadSection（离线 1 条 + 反向验证）够格进"可另批"；`chat/page.tsx`、`globals.css`、`InputBar.tsx` 三处本轮起为"仅静态"；docs 那条只审不改。
- [x] **Step 2:** `approval-sheet.md` 一页装，每行给"当前对象 / 我要的建议 / 反对代价 / 签了也不解除"四栏：
  1. T1 五要素逐格（当前对象、实际受限用途、未覆盖风险、失效触发、复审时点）—— **空着让 Owner 填，我不代填**。
  2. T2/T3：含 Task 1 新出的 **torch-only 路线**（ST `torch>=2.2`、TF extras `>=2.5` 均无上界）。
  3. T4 文档改句（"trust_remote_code 是库默认，不是项目防护开关"）。
  4. T10 环境归属结论签认、T11 写面两跳结果确认。
  5. **T12a**（PyPI 原始件出口）与 **T12b**（BGE 官方精确 revision 小元数据出口，R-8 仍 PARTIAL 的那条腿）—— 分列，各自超时/失败预算。
  6. **F1a/B6 marker 正控否定实验**：仍只交方案不运行；未批的阻塞点写死"Windows 无 `SIGALRM` ⇒ 交互支不可观测"。
  7. **backend/venv 输入保护登记**（实测 133 条在册路径里 0 条覆盖它）：批不批新增 `evidence/env-input-before.json`。
  8. F2 浏览器票的端口与假 API 范围。
- [x] **Step 3:** 复量 `git diff --cached --name-only` 为空、六处未变形。**不 commit。**
  **红路**：任一项变形 ⇒ 停止出单，在 §14 记哪一项变形，并把审批单标为"未出"。

---

## Task 7: 收口复量与交付

- [x] **Step 1:** `"$JOINT" scripts/closeout_check.py <ROOT> <iso>` ⇒ 期望 `changed=0`、`residual_ok=True`、`dist_pairs_identical=True`、`overall=True`、`boundary_breach_logged` 字段仍在。正文必须写：**它量的是"我没越界"，不是"我做好了"**（`<ROOT>` 内 0 条在册路径）。
  **红路**：`false` ⇒ 停止发 §14，按 `input_files_changed` 列表定位被触碰的在册输入，记成新的边界事件；**不得**重跑覆盖旧 `closure.json`，改存带时刻的新文件。
- [x] **Step 2:** Task 1–6 的产物路径、命令、rc 汇入 `reports/results.md` 新节 `## 14（2026-10-09 方案轮）读数`；每条数字旁给复算命令与分母名。
- [x] **Step 3:** 主仓未跟踪数复量并如实记（当前实测 **34158**，含本计划文件）：

```bash
cd C:/Users/33393/Desktop/ai-legal-helper
git ls-files --others --exclude-standard | wc -l
git ls-files --others --exclude-standard | grep -c "2026-10-09-environment-attribution"
```

**红路**：数量高于 34158 且多出的不是计划文件 ⇒ 逐条与本轮新产物清单做差集，把多出的路径登记进 §14 并撤回"只多一只"的说法；数量减少 ⇒ 有并行会话动过树，立即记 `boundary_breach`。

## Self-Review（写完后自查，已就地改）

1. **覆盖**："审清"落 Task 1–3，"评审请求入账 + 修"落 Task 4，"残差敏感补证"落 Task 5，"可签产物"落 Task 6，"收口"落 Task 7。执行书原 A–E 的剩余缺口（浏览器矩阵、真实模型、入库/发布）**不冒充覆盖**，全部进 Task 6 审批单或 §14 残余清单，每条带"为什么本轮不做"。
2. **占位扫描**：Task 2 给了四种区间形状 + UNPARSED 兜底 + 生态过滤规则；Task 5 给的是完整可跑代码且锚点由 Step 1 现测；无"适当处理/同上/TBD"。
3. **类型一致**：`envid` 在 Task 1 定义为四值但 Task 2 只展开 `measurable=true` 的两值；Task 2 的 `label` 由三个正交字段按写死的优先级派生，Task 3 不复用该语汇；`surface_chain` 只放 `file:line`。
4. **每条否定式都有靶**：Task 3 三条对照分别咬路由式、文件清单、调用图；Task 5 的对照是"同形字符改动能红"。
5. **红路齐**：Task 1 Step 3/4、Task 2 Step 1/2、Task 3 Step 1/2、Task 5 Step 3、Task 6 Step 3、Task 7 Step 1/3 各有一条"红了怎么办"。

## 评审处置（v1 → v2，逐条我自己复跑过才改）

采信（每条附我的实测锚点）：F-1/F-2 备份清单会泄库摘要与私有路径且 `version` 探针恒真（`backup_data.py:195-234/259/265-270`；grep 全目录 `sys.version` 只命中 `eval_agent.py`）；F-3 `ended=` 缺的是上一轮 c5 日志，不改文件（`cmd-c5` 实测 `ended=0 EXIT_CODE=2`）；F-4 `POST /api/chat`（`main.py:1791/1793`）经 `run_in_threadpool(_post,...)`（`:2130/2377/2596`）→ `create_candidate`（`:1015`）→ `knowledge_service.py:398→343` 落 Chroma，v1 的三文件清单看不见；F-5 h4 断言必红且三条无区分力（HEAD `:focus-visible{`=1、HEAD `md:!text-base`=1、HEAD `image_chat`=1、HEAD `answer-h4`=0、NOW `answer-h4`=3）；F-6 `vulnerable_functions` 25 条全空；F-7/F-8/F-9 判据词表冲突、分母不可互配、区间四形状（`<= X` 4 条、`>= A, < B` 含 `1.0.0a1`、`fixed_in=['2.7.1-rc1']`）、`packaging-23.2` 两 venv 均在；F-10 关键版本表重复拼法致假 ABSENT 且只扫一只 venv；F-11 `docker-compose.yml:76` 确有 `ports:`（caddy `8088:80`）；F-12 假绿对照换靶（同式 `require_user`=0、`get_current_user`=15）；F-13 include 是通配 glob、套件会变；F-14 133 条在册路径 0 条在 `<ROOT>`；F-15/F-16/F-17 缺审批行、§13 撞 §9 语义、四 GAP 正文 0 命中；F-19/F-20 红路缺失与重言式对照。

**不采纳一条（评审自己的错，我不改）**：挑战轴称 `ci.yml:46` 是步骤名行、命令在 `:47`。实测 `:45` = `- name: pip-audit`，`:46` = `run: pip-audit -r requirements.txt` ⇒ v1 引用正确，保留；但采纳其附带建议，把 `:19`（`python-version: "3.11"`）、`:22`（torch 未钉版）、`:34`（pytest）补进矩阵证据格。
