# 法智项目 · 接手启动书（零记忆助手版，2026-09-18）

> 本文是接手者的**第一入口 + 增量说明**。深度内容（判据冻结、任务清单、执行记录、资产索引）全部在
> **`docs/execution-plan-entity-precision-20260917.md`**（自包含交接版，开篇写明"写给没有本会话记忆的助手"）。
> **先读本文 §0–§6 建立心智模型，再按需要查执行书对应小节。** 若本文与执行书冲突，以执行书为准并记录差异。

---

## 0. 30 秒定位

- **仓库**：`C:\Users\33393\Desktop\ai-legal-helper`（master；远端 github.com/wjt-code-design/fazhi-assistant）
- **项目**：法律 AI 助手——用户咨询 → Agent 多轮（澄清→检索→生成→确定性校验）→ 法律回答。
- **技术栈**：FastAPI + Next.js 14 + 本地 BGE 向量库（chromadb）+ SQLite；Docker 部署于腾讯云（宿主 8088/Caddy）。
- **Python**：一律 `backend/venv/Scripts/python.exe`。**禁止系统 python**（`C:\ProgramData\miniconda3\python.exe`）。
- **当前 HEAD**：**`8479a5b`**（chore(freeze): repository.py 解冻留痕 + lint 折叠修复；2026-09-18 晚实测）。
  **接手前先 `git log -8 --oneline` 确认实际 HEAD**——
  并行会话正频繁提交（见 §5），不要假设 HEAD 停在哪个号。
- **工作树**：tracked 文件**干净**（`git status --porcelain --untracked-files=no` 为空）；但有 **170+ 个未跟踪文件**
  （2026-09-18 实测 171，持续增长——以 `git status` 实测为准；`dispatch-output/` 证据、`docs/`、
  `outputs/`、各种 `_*.txt` 临时日志）。**禁止 `git clean` / `git reset --hard` /
  `git stash` / 批量格式化无关文件**——它们是其他助手的证据与产物。

---

## 1. 接手第一步（照做）

1. 确认分支 / HEAD / 工作树状态（§0）。若 HEAD 与我写的不同，**先记录实际 HEAD 与差异，不擅自回退**。
2. **只读核对关键符号**（不要全仓扫描后顺手重构）：
   - 用 **Grep 工具**（ripgrep 后端）搜索以下关键词定位当前生效的开关与模块：
     `agent_writer_corrective_retry_enabled` / `entity_precision_check` / `numeric_matching_v2` /
     `agent_partial_delivery_enabled` / `law_as_of` / `limitation_calc` / `phantom_check`
   - 用 bash 跑 `git status --short` 与 `git log -8 --oneline` 确认状态（git 在 PATH，无需 grep）。
   - ⚠️ 本机 Bash **未必有 `rg`/`grep`**，别在 bash 里写 `rg`/`grep` 管道；搜索一律用 Grep 工具或 Python 脚本。
3. **跑一次全量门禁取当前基线数字**（见 §3）。这是你唯一的权威基线，旧数字全部作废。
4. 只处理执行书定义的票据；每次一个，验收通过再进下一项。
5. 若发现别处助手正在改同一文件，**先停手确认其是否完成**，避免并行覆盖。

---

## 2. 项目当前状态（增量 TL;DR）

### 主线 T-A 系列（实体法适用精度）—— 已收口，结论：T-A6 **不开启**

| 票据 | 状态 | 关键产出 |
|---|---|---|
| T-A0 数字溯源诊断 | ✅ | 全部 NUMERIC 拒绝属匹配缺陷 |
| T-A1 法条库标注 | ✅ | `backend/knowledge_base/law_annotations.json`（69 条） |
| T-A2 verifier 校验 | ✅ | `backend/agent/entity_precision.py` + 开关 `entity_precision_check`（默认关） |
| T-A3 拒答分级 | ✅ | 开关 `numeric_matching_v2`（默认关）+ 受控计算 `fee_calc.py` |
| T-A5 付费批次 + 双轮盲评 | ✅ 数据已取得 | **P1 不可判定 / P2 四条误杀全部不成立 / P3 样本不足 / P5 有缺陷** |
| T-A6 生产开启 | 🔴 **维持不开启** | 见 §4 决策闸 |

### 近期收口（本会话 + 并行会话）

- **P0 收口 `a3ce07b`**：恢复 `over_rounds` 协议口径 + verifier 词表防误伤（`_is_overconfident` 术语优先放行，19→0 误杀）+ 失败路径 claim 落库。**已提交、未推送**（部署按用户要求先不做）。
- **T-H `1f73bb5`（本助手提交）**：修"过度排除/过度保守"——writer 逐争点渲染失败，对**修正性原因码**
  （UNKNOWN_FACT_ID / UNKNOWN_EVIDENCE_ID / UNSUPPORTED_CITATION / UNSUPPORTED_NUMERIC_TOKEN /
  NON_CANONICAL_CITATION）在开关 **`agent_writer_corrective_retry_enabled`**（**默认关**）下**重试至多一次**。
  ⚠️ 推翻了旧注释"同输入同校验重试无意义"——**校验确定性 ≠ 生成确定性**（生成是采样的）。
  验证：watch-it-fail 落盘 + 新增 2 测试 + 边界 9 测试无回归 + 全量 1190 passed（**提交当时**数字，
  已被后续批次刷新，见 §3）。
  **遗留**：机制可用，实际效果需下一批评测实测（开关默认关）。
- **并行会话已提交（本助手之后）**：`9d79389` R15-lite 法律版本基准日（law_as_of）+ `7c7261c` R11/R12 时效确定性 + 伪调用检测（limitation_calc/phantom_check）+ `afd3138` P1 harness 修复 + `777e332` P1-1 归属绊线（曾出现的 `f7d1d63` 同消息提交已被 rebase 丢弃，见 §5）。**这些均为默认关、行为无损特性**。

---

## 3. 门禁与基线（🔴 务必先跑再信）

- **唯一权威基线 = 你本次跑出的数字**。`pytest -m "not slow"` 演进记录：
  - `a3ce07b` 时代 = 1188 passed → T-H 后 = 1190 → **当前权威基线 = 1233 passed / 18 deselected**
    （`_pytest_r15full2.txt`，423.71s，含 R11/R12/R15-lite + P1 新测试）。
  - ⚠️ **旧数字全部作废、禁止引用**：974 / 990 / 992 / 1101 / 1188 / 1190 / 1225。
  - 并行会话仍在高频提交 ⇒ 接手后**跑一次全量取真值**，与最近记录对比看增减。
- **`ruff format --check` 当前全绿**（2026-09-18 实测 228 files already formatted）。
  历史上 `backend/agent/writer.py:665` 曾长期失败（T-A3 多行签名），**已在 R11/R12 批消失**——
  若你再见到 format 失败，**当新问题查**；且**永远不要顺手 `ruff format` 整个 writer.py 或全仓**，
  只动你自己负责的文件（防跨会话写冲突）。
- 评测统计禁用全局共享字典按法条聚合；并列数字先核对口径（探针口径 ≠ 真实记录口径）。

**跑门禁的标准命令（本机坑见 §6）**：
```bash
cd "C:/Users/33393/Desktop/ai-legal-helper/backend"
mkdir -p ../dispatch-output/gate-<日期>
./venv/Scripts/python.exe -m pytest -m "not slow" -q --tb=line \
  --basetemp="C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/gate-<日期>/tp" \
  > "../dispatch-output/gate-<日期>/pytest_out.log" 2>&1 ; echo "rc=$?"
```
⚠️ `--basetemp` **必须每次全新目录**（复用旧目录触发 safe-delete 批删 → SystemExit 集体失败）；父目录须先存在。

---

## 4. 决策闸与待 Owner 拍板（接手必读，别擅动）

### 🔴 T-A6 维持"不开启"—— 四条件齐备才提交 Owner

执行书 §T-I 五条（① P1 有可比分母且拦截率达标；② on 臂不引入新实质缺陷；③ 复核须防锚定有效；
④ P3 ≥2 批重复；**⑤ 下一批评测 on 臂须开开关清单**：`entity_precision_check` / `numeric_matching_v2` /
`agent_partial_delivery_enabled` / **`agent_writer_corrective_retry_enabled`**——**不开则"过度排除"照旧复现，批次白花钱**）。
**off 臂维持全关**保证对照可比。

### 待 Owner 决策的三件事（收敛后只剩这些）

1. **T-J KB 缺《食品安全法》第 148 条**（案例5 十倍路径）。writer 不引 KB 外法条是**防幻觉边界，不应改**；
   待 Owner 提供官方文本 → 入 `laws_raw` → 重建检索索引（与《诉讼费用交纳办法》同例）。**补源前该路径排除是正确行为**，不得按"过度保守"计。
2. **p0 模型额度**：`agent_text_37max0608`（priority 0）`FreeTierOnly` 耗尽。**仅 p0 耗尽，p1–p5 可用**（实测用 `qwen3.7-max`）。评测批用 `seed_quota_override` 机制（每臂独立 `quota.sqlite` 写 `init:<key>` 校准行），**不要改 `.env` / 不要依赖 env 注入**（serve.py 的 `load_dotenv(override=True)` 会吃掉父进程注入）。
3. **人工法律复核**：项目纪律要求 0/1 判定用**确定性金标**、不用 LLM judge（会一起错）。P5 两轮复核人是 **LLM（WorkBuddy AI）** ⇒ 按"**AI 复核意见**"口径使用，**不得写成人工法律意见**；若 T-A6 最终要开，人工复核可能仍是硬要求。

### 负面清单（已决定不做，防范围蔓延——不擅自重开）

- R1-OB 深化投入（5 条跨域引用/主体错配落在词表/域过滤盲区，已判"不再投入"）。**新证据不足以自动重开**；要动须 Owner 显式推翻并说明。
- 检索召回主动重跑、留专门付费重跑、V8 剩余人测等（见执行书 §负面清单）。

---

## 5. Git 现状（🔴 损坏 + 快照机制，别用常规 push）

- **仓库对象损坏**：缺 blob `04463121…`（及父 `0263bd56…`）。后果：**含该 blob 的历史提交**
  `git show --stat <commit>` / `git diff --stat <commit>` **不可用**（会报 unable to read）。
  但 **`git add` / `commit` / `write-tree` 正常**；**工作树 `git diff --stat`（无参）仍可用**。
- 4 条 `refs/replace/` 替换引用是既有机制非损坏；`fsck` 6 个缺失对象中 5 个 dangling 可忽略，`01d9b1b2` 是 replace 虚警。
- **远端直推历史不可用** → 同步走**快照机制**：`commit-tree(HEAD树, parent=远端tip)` → 树一致性 →
  `rev-list --objects --missing=print` 零缺失 → dry-run → push → `ls-remote` 核对。
  **推送前必须 `git ls-remote` 实测远端 tip 作 parent**（本地 `origin/master` 长期过期）。模板见执行书 §3。
- ⚠️ **并行会话可能改写历史（rebase/amend）**：曾出现同消息提交对 `afd3138`/`f7d1d63`，
  2026-09-18 实测 `f7d1d63` 已**不在当前历史**（被 rebase 丢弃，仅剩 `afd3138`）。
  **勿依赖任何短哈希做长期引用**，动手前一律 `git log` 实测。

---

## 6. 本机环境坑（第一小时就会踩，逐条避坑）

1. **Bash 无 `grep`/`head`/`tail`/`ls`/`mkdir`/`cat`/`dirname`**（Git Bash PATH 缺）。一律用 Python 绝对路径脚本；
   `pytest` / `ruff` 输出**一律重定向到文件**（`> log 2>&1`），**不走管道**（无 grep 会 SIGPIPE 杀 pytest）。
2. **内联 `python -c` 含反引号会被 bash 当命令执行** ⇒ 含反引号 / `$` / Markdown 代码块的脚本**一律写成 `.py` 文件执行**，不用 `-c` 内联。
3. **Python 脚本里发联网请求会让整个 bash 进程被杀**（exit 1、零输出）⇒ 联网探测用 `curl`（白名单）或 WebFetch 工具。
4. **探活 localhost 必须 `--noproxy "*`**（clash 7890 会接管请求造成 502 假象）。
5. **沙箱 Bash 收割全部子进程（Job Object）** ⇒ 长驻服务（后端/评测服务）只能**用户侧双击 bat 或 schtasks** 启动，命令结束即被杀。
6. 健康检查路由：`/api/health`（main.py:281）、`/healthz`（main.py:313）；**`/health` 是 404**。
7. 生产运行时 = Docker（宿主 8088/Caddy）；容器 DB = `backend/data/app.db`。镜像重建快，但**改提示词必须 build+up** 才生效。
8. `commit message` **不内嵌英文双引号**（会被 shell 拆成 pathspec）；含反引号/`$` 的内容写文件提交。
9. Python 写文件用 `newline=''` 或显式 `'\n'`（仓库 autocrlf=true，否则 `ruff format --check` 失败且 git 看不见差异）。
10. **回滚类脚本先备份再改**；用 `read_text`/`write_text`（CRLF 致 `read_bytes` 替换失败）；`finally` 还原路径要 sha256 自证。
11. 只杀日志里记录的那个 PID，**不批量杀 python**。

---

## 7. 关键资产索引（详表见执行书 §3）

| 用途 | 位置 |
|---|---|
| **唯一深度执行书（判据/清单/记录）** | `docs/execution-plan-entity-precision-20260917.md` |
| T-A5 批次报告 + 复核处理 | `dispatch-output/ta5-arms-20260917/report-batch3.md` / `p5-review-result-20260918.md` / `p5-round2-result-20260918.md` |
| T-H 修复 + 全量门禁证据 | 提交 `1f73bb5`；`dispatch-output/th-run-20260918/pytest_out.log` |
| P0 收口审查 | `dispatch-output/ta5-arms-20260917/code-review-t1t3-20260918.md` |
| 批次编排 / 判据分析 | `dispatch-output/r1ob-prodform-20260917/`（run_prodform_batch.py / analyze_prodform_batch.py / criteria-report.json / report.md） |
| 网络/健康预检（`--noproxy` 探活模板） | `dispatch-output/ta5-arms-20260917/probe_all_real.py` |
| 冻结回归断言集（12 项"否"） | `dispatch-output/review-package-law-20260917/review-verdicts.json` |
| 探针（k4 合规口径） | `evals/retrieval_probe.py` → `probe-results-k4.json`（勿覆盖冻结资产） |
| 快照推送模板 | `dispatch-output/r1ob-online-20260917/push_snapshot2.py` |

---

## 8. 本会话已写的交接相关改动（留痕）

- 本文 `docs/handoff-takeover-20260918.md`（新建，即本文件）。
- **本文已经过审核（2026-09-18 19:19–19:45）**：37 项对仓库逐条实测 → 修正 6 处（HEAD 快照、
  基线 1233、未跟踪数口径、`f7d1d63` 已被 rebase 丢弃、`net_health.py`→`probe_all_real.py`、
  `review-verdicts.json` 路径前缀）→ 终验 5/5 全绿、文档内 18 条路径全部实测存在。
  **可复跑审计**：`./backend/venv/Scripts/python.exe dispatch-output/_audit_handoff2.py`
  （HEAD 检查为信息项——并行会话推进后该项数字变化属预期；其余 4 项仍有效）。
- 执行书 `docs/execution-plan-entity-precision-20260917.md` 已含 T-H / T-I / T-J / P0 全量记录（§P5–§P0 段）。
- 当日工作日志 `.workbuddy/memory/2026-09-18.md`（追加式，含事故、盲评、修复、本审核全记录）。
- 长期约定 `.workbuddy/memory/MEMORY.md`（跨会话持久）。

> 接手后任何实质性改动，请**追加**到执行书对应票据 + 当日日志，**不要新建互相覆盖的交接文件**（进度唯一入口是执行书）。
