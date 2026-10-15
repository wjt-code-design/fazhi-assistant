# C/E 依赖与模型来源读数（2026-10-10 现量）

所有读数都在本轮私有环境（`candidate-env` / `candidate-envB`）里跑出，未读写主仓 `.env`、真实库、真实配额库、现役 HF 缓存。
每条都附复算命令；`pip-audit --format=json` 的键是 `dependencies[].vulns`（**不是** `vulnerabilities`），我用错过一次并当场产出假 0，见 `evidence/c-verify/` 与下方「尺子事故」。

## 1. 两套候选闭包（差一根轴：torch）

| 腿 | candidate-env（A，已跑完全量） | candidate-envB（B，torch 升轴） |
|---|---|---|
| 基座解释器 | `C:/Users/33393/AppData/Local/Programs/Python/Python311/python.exe` 3.11.0 | 同一只 |
| torch | `2.6.0+cpu`（CPU 官方源） | `2.13.0+cpu`（CPU 官方源） |
| transformers | 我加了 `>=5.0,<5.19` 上界 → 5.17/5.18 | **不加**上界（HEAD 声明形状） |
| `pip check` | rc=0 `No broken requirements found.` | 见 §5 |
| 全量非 slow | **1901 passed / 0 failed / 10 skipped / 18 deselected**，220.96s，RC=0 | 待跑 |
| 收集期 socket | 321 事件，**非回环 0**，回环 319 | 待跑 |

## 2. 实测到的兼容缺陷与它的真根因（不是「transformers 太新」这么简单）

`rag_chain.py:44` 在 **import 期** 建 `HuggingFaceEmbeddings`，所以这条链断在收集期，表现是
`ImportError: Could not import sentence_transformers`（**误导**）。真根因逐层是：
`transformers/modeling_utils.py:82` → `is_torch_flex_attn_available()` → `get_device_type()` →
`torch.accelerator.current_accelerator()` → **torch 2.6.0 在无加速器时抛 `RuntimeError` 而不是返回 None**。

单变量隔离（只换一只包、`pip freeze --all` 前后仅差一行，跑完即还原）：

| transformers | torch 2.6.0+cpu | torch 2.13.0+cpu |
|---|---|---|
| 5.17.0 | import OK | — |
| 5.18.0 | import OK | — |
| 5.19.0 | **import FAIL** | 待量（`current_accelerator()` 实测返回 **None** ⇒ 预期 OK） |

⇒ 两条修法都能治形状。**A 单独用「给 transformers 加 <5.19 上界」是有代价的**：它把 torch 留在 2.6.0，
而 torch 2.6.0 自己带着 22 条通报（§3）。所以 B 案（升 torch）优先，A 案的上界只是「不动 torch 时的止血」。
这不是「升级困难所以接受」——A 案已经建好并跑完全量，B 案正在建。

## 3. 逐对象官方读数（我自己复算，非转抄）

| 对象 | 读数（声明形状 / 本机安装） | 适用性 | 修复线 | 声明窗口能否容纳 |
|---|---|---|---|---|
| torch | 文件里**根本没声明** / 安装 2.6.0+cpu | **24 条记录 / 22 个不同 ID**（req 内容只写 `torch==2.6.0`，`pip-audit --no-deps`） | 修复线含 `2.7.0 / 2.7.1 / 2.10.0 / 2.13.0`；`torch==2.13.0` 同法复算 **0 条 / 0 ID** | **n/a：不在册** ⇒ 必须显式声明，否则 CI（`ci.yml` 装 latest CPU）与本机各装各的 |
| transformers | 5.19.0 / 4.57.6 | 旧安装的 4.57.6 适用 | 5.10.0 以上即清 | **无安全压力**：`transformers==5.17.0` 与 `5.19.0` 同法复算**都是 0 条 / 0 ID** ⇒ `<5.19` 这条上界只为兼容 torch 2.6，**不带来任何安全收益**（这正是 B 案优先的理由） |
| langchain-core | 0.1.53 / 0.1.53 | **适用**：16 条记录 / 10 个不同 ID（该读法把 23 只邻居一起算了，langchain-core 自身至少 5 条 PYSEC-2026-2562/2563/2564/373/1518） | `1.3.3`（`langchain-core==1.3.3` 同法复算 **0 条 / 0 ID**，30 只邻居） | **不能**：`>=0.1,<0.2` 把 1.x 挡在外面 ⇒ 0.1→1.3.3 是跨大版本迁移 |
| chromadb | 0.4.24 / 0.4.24 | 2 条：**PYSEC-2026-3813**（CVE-2026-45830）与 **PYSEC-2026-3814**（CVE-2026-45833），`fix_versions` 为空 | 官方页 affected `>=0.4.17, <=1.5.9`、Patched **None**、High CVSS 8.8 | **无修复线**。而且**升级会把面变大**：`chromadb==1.5.0` 同法复算 **5 条 / 4 个 ID**（多出 PYSEC-2026-311、-3815），`fix_versions` 同样为空 |

## 4. chroma 这两条够不够格谈「接受」：可达性我读到的是「本形状不可达」，但只到形状一层

两条通报的机理都是 **服务端多租户鉴权缺失**（GHSA-2w9 原文：allows any **authenticated users** to read/write/update/delete data in **any tenant's** collection）。
本项目的用法实测是**进程内嵌入式**：`backend/rag_chain.py:127` `Chroma(persist_directory=CHROMA_DIR, embedding_function=..., collection_name=...)`，
`backend/tests/conftest.py` 同形状；全仓 grep `HttpClient|chromadb.Server|chroma run` 在 `backend/` 内 **0 命中**，
`manage.py:100` 那只 `--host 0.0.0.0` 是 uvicorn 起 app，不是 chroma server。
⇒ 没有 tenant、没有 chroma 侧认证主体，攻击前置条件在本形状里不成立。
**射程边界要说死**：这证的是「代码里不启 chroma 服务」，不是「部署后网络面一定封闭」；后者属 J6 生产平台门（用户尚未选服务器），我不能在这里替它签字。

## 5. 尺子事故（我自己的，已就地纠正）

第一版解析脚本把 pip-audit 的 JSON 当 list 读（`n = d if isinstance(d,list) else [d]`），
对 `{"dependencies": [...]}` 结构读出 `None==None ids=0`，同时 `rc=1` —— **rc=1 与 0 条互相矛盾就是信号**。
纠正后的读数就是 §3 那张表；原始 stdout/stderr 留在 `evidence/c-verify/`（`audit-*.json` + `audit-*.err`）。
口径写死：上面每行都是「req 文件里只写这一只包 + `--no-deps`」的单包读法，`pkgs=` 是 pip 顺带代出的邻居数，**不等于**整棵产品依赖树的全量审计；与 §1 两套闭包、与 CI 的 `pip-audit -r requirements.txt` 都不是同一个分母，不能相加也不能互证。

## 6. E.1 模型来源（已闭，附可核证据）

| 项 | 读数 |
|---|---|
| 官方源可达性 | `huggingface.co` 本机 **HTTP 000**（不可达）；`hf-mirror.com` **HTTP 200** ⇒ 只能走镜像 |
| 可核性怎么补 | 用 HF API 透传的两把哈希：11 只小文件比 **git blob sha1 == blobId**，`pytorch_model.bin`(409,138,989B) 比 **内容 sha256 == `731cf5d8…bae044`** ⇒ 12/12 OK |
| revision | commit `f03589ceff5aac7111bd60cfc7d497ca17ecac65`；私有缓存 `refs/main` 现指向同一枚（先前只按 commit 快照 ⇒ 离线按默认修订名查找会 `LocalEntryNotFoundError`，已补 `refs/main`） |
| 许可证 | `license:mit`（HF API cardData + tag 两处一致） |
| 离线实装 | `HF_HUB_OFFLINE=1` 下 `HuggingFaceEmbeddings` 载入成功，`embed_query` 维度 **768** |
| 未做 | 未扫描、未哈希、未复用机器上现役 781M 缓存（那只 `models--BAAI--bge-base-zh-v1.5` 目录 mtime 仍是 2026-07-30） |
| 残留限制 | 镜像的哈希字段是 HF 官方 API 的透传，**我无法从本机再对 huggingface.co 独立复算一次**；这一条按本书 H「旧值缺失不等于历史洁净」的同款口径登记 |

证据：`evidence/hf-bge-meta.json`、`evidence/bge-model-verification.json`、`evidence/fetch_bge_model.py`、`evidence/bge-fetch.log`。

## 7. B 单实测（接收复验，不含任何裁定）

- 四只新增测试文件在候选 + 新闭包：**48 passed / 0 failed**（25.20s，junit tests=48）。
  这与上一轮汇报**自相矛盾**：其 §7 逐只写 10+7+7+24 = **48**，而其 §3 的加账写「新四只文件 **45**（collected 轴）」。我这边现量支持 48。
- 全量非 slow：**1901 passed / 0 failed / 10 skipped**；上一轮在旧栈（`backend/venv`）报 1909 passed / 2 skipped。**总数同为 1911，差的 8 只正是 `real_kb` 腿**：候选树里 `backend/chroma_db` 按构造不存在 ⇒ 它们 skip，不是 pass。
  ⇒ 「全量绿」这句在本轮必须连「8 只 real_kb 走 skip、未覆盖」一起说。
- 未跑/未绿：mypy 两条 `Row` 泛型红（待我在候选复现并归因），`pip-audit` 见 §3（rc=1 未闭），前端门（D），覆盖率腿。

## 8. 升 torch 在三条面上是否可行（逐面实测，不是"应该可以"）

| 面 | 现在的在册说法 | 我实测到的现量 | 结论 |
|---|---|---|---|
| 本机 | `pip install torch==2.6.0+cpu --index-url https://download.pytorch.org/whl/cpu` | `candidate-envB` 用同一条命令换 `2.13.0+cpu` 装成功，`import torch` 通过，`current_accelerator()` 返回 **None**（2.6 抛 RuntimeError 的那处） | 可行 |
| CI | `ci.yml` 是 `pip install torch --index-url .../cpu`（**不钉版本**）⇒ CI 今天装的其实是 latest CPU 版，与本机 2.6.0 不是一根轴 | 官方 CPU 索引列出的可用版本含 `2.13.0+cpu`（`pip index versions` 现量） | 可行，且**必须**改成钉版本，否则"CI 绿"和"本机绿"永远不是同一个 torch |
| Docker 镜像 | `backend/Dockerfile:34-38` 注释写"阿里云 PyPI 上 torch 是 2.14.0（CUDA）与 find-links 上的 **2.6.0+cpu** 并存…必须钉死"，并在 `:41-48` 用断言防呆；`:38` 还写"torch 锁在 2.6.0（**镜像已同步的最新 cp311+cpu 版**，2025-01 发布），若日后需升级：先确认镜像已同步更高 +cpu 版本" | 抓 `https://mirrors.aliyun.com/pytorch-wheels/cpu/` 全目录（1,207,660B，`evidence/aliyun_ptw.html`）解析：`+cpu-cp311` 共 **118 个构建**，最高含 **`2.14.1+cpu`**（win_amd64/manylinux/aarch64/s390x）与 **`2.13.0+cpu`** ⇒ **那句"镜像已同步的最新是 2.6.0"已经过期** | 可行；按它自己写的升级路径改 `:42` 的版本与 `:38` 的注释即可，防呆断言原样保留 【**本行指针已过期，现量按 `git show HEAD:backend/Dockerfile`**：钉版注释 `:35-38`、install 段 `:45-47`、防呆断言 `:51-58`；而它引的那句「torch 锁在 2.6.0（镜像已同步的最新 cp311+cpu 版）」**已被 `8c179e7` 删除**，换成 `:39-44` 的取舍说明 ⇒ 本行描述的是**改动前**的文件，读它请按改动前理解】 |

⇒ 三条面都能走。所以「把 torch 留在 2.6.0」不再有任何外部约束替它背书，它只剩一条代价：22 条通报（§3）。
`requirements.txt` 目前**根本不声明 torch**，所以 CI 的 `pip-audit -r requirements.txt` 对 torch 永久失明（22 条进不了门禁读数）——
这点与 `ci.yml` 的 dev 轴缺失是同一类"门上看不到"的形状。

## 9. 我打算怎么改（等你裁 1/2/3 期间不动产品语义，但这一条属纯依赖声明）

候选 `backend/requirements.txt`：撤掉我加的 `transformers>=5.0,<5.19`（§2：它零安全收益），换成显式 `torch==2.13.0`
（PEP 440 下 `==2.13.0` 被已装的 `2.13.0+cpu` 满足 ⇒ CPU 源、PyPI、Docker find-links 三种装法都不拧）；
`backend/Dockerfile` 的 `torch==2.6.0+cpu` 同步改 `2.13.0+cpu` 并更新其注释；`.github/workflows/ci.yml` 的 `pip install torch` 加同一枚钉版。
三处必须同批改：只改一处会让"本机/CI/镜像"三根轴继续各走各的。

## 10. 收口：候选闭包定稿 + 残余 15 个 ID 的归属（全部现量）

候选已改的依赖声明（三只文件，同一批改、缺一不可对齐）：
`backend/requirements.txt`（加 `torch==2.13.0`、`sqlalchemy` 下限 2.0→2.1、撤掉我中途加的 `transformers<5.19`）、
`backend/Dockerfile`（`torch==2.13.0+cpu` + 更新过期注释）、`.github/workflows/ci.yml`（同钉 `2.13.0+cpu`）。
实装校验：`pip install --dry-run -r requirements.txt` 在 envB 上 `torch==2.13.0` 由已装的 `2.13.0+cpu` 满足、`sqlalchemy>=2.1` 由 2.1.4 满足，rc=0；
`pip check` rc=0；两套候选（A：torch 2.6.0+tf<5.19 / B：torch 2.13.0+tf5.19）全量非 slow **逐字同读数 1901 passed / 0 failed / 10 skipped / 18 deselected**，junit tests=1911。

### 残余通报按包归属（`pip-audit -r` 候选 runtime 与 dev **同为 24 条记录 / 15 个不同 ID / 5 只包**，rc=1）

| 包 | ID 数 | 修复线 | 声明窗口容得下吗 | 归谁 |
|---|---|---|---|---|
| chromadb 0.4.24 | 2（PYSEC-2026-3813/-3814） | **无**（官方页 Patched None，affected `>=0.4.17,<=1.5.9`；升 1.5.0 反成 5 条） | 无从谈 | Owner 裁「在册接受 + 失效条件」（§4 已给可达性读数） |
| langchain-core 0.1.53 | 6 | 0.3.80 起（1.3.3 复算 0 条） | **否**，`>=0.1,<0.2` | 需另开迁移票（0.1→1.x 是跨大版本） |
| langsmith 0.1.147 | 4 | 0.7.31 / 0.8.0 / 0.8.18 | **否**，被 langchain-core 0.1.53 的 `langsmith<0.2` 钉住 | 同上（同一刀的连带面） |
| langchain-openai 0.1.7 | 1 | 1.1.14 | **否**，`>=0.1,<0.2` | 同上 |
| langchain-text-splitters 0.0.2 | 2 | 0.3.9 / 1.1.2 | **否**，`>=0.0.2,<0.1` | 同上 |

⇒ 15 个 ID 里 **2 个上游根本没修**，**13 个全卡在同一族 `>=0.1,<0.2` 的窗**。这两类我都不能替 Owner 决定：前者是「接受残余」，后者是「要不要动产品依赖族」。
本轮把它们写成 BLOCKED 而不是 PASS，也不因为「升级困难」默认接受。

### mypy 的两条红：归因完成，且结论与上一轮不同（同一枚尺子，别抄旧数）

上一轮在册说法是「mypy 两条 `Row` 泛型红、改前即红、由 `902e2d1` 引入」。我在候选实测：
- 注解本体在 **HEAD 就存在**（`main.py:2872` 与 `:3083`，候选工作树轴因本轮 +25 行而显示为 2897/3108）；
- **候选闭包（SQLAlchemy 2.1.4）下 mypy 2.3.0 与 2.4.0 都是 `Success: no issues found in 74 source files`**；
- 单变量隔离：在同一个候选环境里只把 mypy 从 2.4.0 换成 2.3.0（`pip install --no-deps`，`pip freeze --all` 前后仅差一行、跑完还原并复量 IDENTICAL）⇒ 仍 Success；
- 换成两只解释器对比同一棵树：旧 `backend/venv`（SQLAlchemy **2.0.51** + mypy 2.3.0）报 2 条，候选（SQLAlchemy 2.1.4）0 条。

⇒ **红绿由 SQLAlchemy 版本决定，不是 mypy 版本，也不是本轮改动**。SQLAlchemy 2.0 的 `Row` 是 `Generic[_T]`（1 个参数），2.1 才收变分参数。
所以真正该修的是**声明的下限**：`sqlalchemy>=2.0` 允许装出一个 mypy 必红的环境。已按实测把下限提到 `>=2.1,<3.0`（§10 开头），
这同时是 G 单的一条硬事实：**现用 `backend/venv` 的 SQLAlchemy 2.0.51 落在新声明的窗口之外**，属未升级状态，不是「已符合」。

### 尺子事故二则（本轮我自己的，都已纠正并留痕）
1. `pip-audit --format=json` 我按 list 读，把 `{"dependencies": [...]}` 读成 `None==None ids=0`，同时 rc=1 —— rc 与「0 条」互相矛盾就是信号，纠正后才是 §10 的表。
2. `run_backend_tests.sh` 里 `ARGS=(-m not slow)` 被 bash 拆成 `-m not` + 路径 `slow` ⇒ pytest rc=4「file or directory not found: slow」，
   我先把它当成跑过了。改成 `ARGS=(-m "not slow")` 后才是真读数；这条也解释了为什么「退出码非 0」必须逐条看日志而不是只看收尾计数。
