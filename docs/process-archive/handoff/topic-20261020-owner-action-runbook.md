# Owner 专属动作 runbook（收尾批 A7 · 2026-10-20）

> **本文是「前置物」，不是「已完成项」。** 它只交付"本人不在场也能逐条照做"的操作说明，**不代做**其中任何一项：
> 不代签 / 不代填 / 不代配 / 不代切 / 不代跑 / 不代对账 / 不代裁（B8）/ 不代真机验收（B9）。
> **本文所有命令均为"待执行指令文本"；本轮助手未执行任何读取真实凭据的命令。** 全文未读 `.env`、真实业务库、真实语料库、候选 `chroma_db`、任何凭据值。
> 凡涉及真实值处一律留空并标 `<需 Owner 填>`；**严禁把推测值写进任何交付物**。

- 真源：`<RUN>/task-status.json`（W14=`BLOCKED_OWNER`、W08=`NOT_STARTED`、C13=`BLOCKED_OWNER`；`owner_decisions` 中 C13/C14 原文；`D_index_status` 中 D-55）。
- `<RUN>` ＝ `reports/execution-runs/fazhi-full-closeout-20261018-af101aa9bca543b1a9c21fd0bace9780`。
- 执行书 ＝ `docs/process-archive/superpowers/plans/2026-10-15-full-scope-remediation-and-closeout-execution-plan.md`（§W08）。
- 现状读数取自 2026-10-20 本机**只读**复核（见文末声明）。

## 通用纪律（B1–B10 共用）
1. 每条动作六栏齐全：**目标 / 前置检查 / 精确命令或操作路径 / 判据 / 回滚 / 责任与验收**；缺任一项即不得开工。
2. 涉及真实值的命令一律占位，**禁止臆断**（臆断即把假值写进交付物）。
3. 红线（引自 `task-status.json` `protection_list`）：不读 `.env` / 真库 / 真实会话 / 凭据；不写 M 的 21 个 tracked 改动文件；**不部署 / 不重启在跑服务 / 不公开暴露**；禁 force-push / 禁历史重写 / 禁 merge 到 master。

---

## B1 · W10 独立签核（正本已在位，2026-10-21 已由 haimeng 落笔）

- **指针（正本，唯一）**：`docs/process-archive/reviews/2026-10-19-w10-lock-landing-independent-verification.md`（M 仓 **untracked**，不在 run 根 manifest 扫描范围）。同目录 `2026-10-19-independent-readonly-audit.md` / `…-round2.md` 是**缺陷审计**，体裁不同，**编号 / 结论不可混用**。
- **当前状态（2026-10-21）**：**已签核**。A8 为 `独立审核人签字：haimeng` / `签核日期：2026-10-21`（锚定 `187174f` 快照；C1/C2 为快照读数，非现态）。正本 10229 B / 96 行 / 纯 LF，sha256 `1f239511e1f733186b35c6adf6d4f48c1de65c2c0bf2771828c093548369af0e`；笔迹由 Owner 一侧落下，助手未代签。
- **正文内容**：含 **A3 的 12 项声明表**（C1–C12，逐条"命令 → 读数 → 成立"）。报告净结论：**12/12 成立、0 反证、0 真发现**；红能力差分成立（把 constraints 临时副本的 `langsmith==0.14.11` 改成 `0.0.1` → `ResolutionImpossible` rc=1 / 0 wheels）。
- **为何只能由 `haimeng` 本人签**：A8 明写"指定独立审核人 `haimeng` 专属""他人不得代签"；A2 记录本报告由**本轮主审**整理（属执行方一侧），而"自审 ≠ 独立签核"（执行书 §5 与执行计划 §H1/H2）。**代签 = 伪造签核**，直接违反证据纪律。
- **签署前若要复核（命令抄自报告 A3，勿新造）**：
  - `git rev-parse HEAD` → 期望 `187174f…`；`git status --short` → 期望空；
  - `git ls-remote … refs/heads/nondeploy-closeout-20261018` → 2026-10-21 现量为 `ee5bfef`（≠ `187174f`）；签核锚定 `187174f`，快照读数不得与现态混用；
  - `git show --stat c7a381f` / `b406ab8` / `187174f` → 期望改动面 2 / 1 / 1 文件；
  - `Get-FileHash backend/constraints.txt` 与 python `hashlib` **双算** → 期望 `F13EAFDC…09E0E6B`；`name==version` 计 **136**；`torch==2.13.0`（无 `+cpu`）；
  - `pip download -r <reqs−jieba> -c constraints.txt --no-index --find-links <linux-closure> <交叉平台标签>` → 期望 rc=0 / 135 wheels；
  - `yaml.safe_load(ci.yml)` → install 步含 `-c constraints.txt`；
  - `pytest --noconftest tests/test_llm_lifecycle.py -q`（隔离 venv）→ 期望 11 passed rc=0。
  
  以上命令**只读**、不改仓库、不读凭据。
- **签署后放哪里**：**原地**（`docs/process-archive/reviews/` 内该文件即正本）——填写 A8 两栏（签字 + 日期）即完成签核，**不复制进 run 根**（D-30：主仓 M 文档不自动收编；run 根 manifest 不扫 M）。台账侧同步：在 `<RUN>/task-status.json` 的 W10 `residual` 记入"签核完成 + 日期 + 签署人"。
  - 待 Owner 确认的落点疑点：执行计划 §H1 引用的 `agents/agent-audit.json` 在主仓**不存在**（复核：无 `agents/` 目录；`agent-audit.json` 实际位于 `release-evidence/<release-id>/`）。**本票签核落点以报告 A8 为准**，不用 `agents/agent-audit.json`。
- **责任与验收**：责任 = `haimeng`（本人）；验收 = A8 两栏非空 + 台账 W10 `residual` 记日期。**本助手不代签**。

### B1 执行结果（2026-10-21）

- A8 已由 `haimeng` 落笔：`haimeng` / `2026-10-21`，锚定 `187174f`；正本 10229 B / 96 行 / 纯 LF，sha256 `1f239511e1f733186b35c6adf6d4f48c1de65c2c0bf2771828c093548369af0e`（untracked，未入库）。
- 候选线漂移：候选工作树 HEAD `69577e9`（比 `187174f` 多 31 笔），远端 `nondeploy-closeout-20261018` tip `ee5bfef`；签核仅对 `187174f` 快照成立。
- 台账：`W10.residual` 已记签核；`W10.status` 由 `FIXED_PENDING_REVIEW` 转 **PASS**（沿用本账 W00/W15「PASS + 显式余项」先例）。仍未闭合项只有 **Linux 真装真跑**，不由该状态掩盖。
- 助手未代签；只做独立复跑与措辞建议。

---

## B2 · Docker data-root 迁 D（维护窗口内）

- **目标**：把 Docker 磁盘镜像从 C 迁到 D，回收 C 盘空间，为后续 `docker build` 包体门铺路（解除条件见 `tickets/W12-engineering-gates.md` §4，补跑边界见 §Q3）。
- **现状读数（2026-10-20 只读复核）**：Docker Desktop **4.84.0.234817**；引擎 `docker version` Server **29.6.2**；WSL2 distro `docker-desktop` **Running**；镜像文件 `C:\Users\33393\AppData\Local\Docker\wsl\disk\docker_data.vhdx` = **92.19 GB**；**C 盘余 25.23 GB / D 盘余 848.51 GB**；compose 项目 `ai-legal-helper`（config file `c:\Users\33393\Desktop\ai-legal-helper\docker-compose.yml`）**3 个容器在跑**：`fazhi-backend`（healthy）/ `fazhi-caddy` / `fazhi-frontend`。
  - ⚠️ **与既有记述不符**：执行计划 §A3 写"distro **Stopped**、**0** 容器在跑 ⇒ 窗口安全"，与实测不符（现为 Running + 3 容器）。故 **必须择维护窗口**：迁 disk image location 需重启 daemon，**会打断现役三容器**。
- **前置检查**：① 取得"可停栈 + 可重启 daemon"的**维护窗口授权**；② 先记录并离线留存当前清单；③ 确认 D 盘目标目录可写、余量 ≥ 需用量。
- **精确操作（窗口内逐条）**：
  1. 记录现状（**只读**）：`docker ps --format "{{.Names}}|{{.Status}}|{{.Image}}"`、`docker volume ls`、`docker image ls`、`docker compose ls`；输出粘进维护记录。
  2. 优雅停栈：`docker compose -f c:\Users\33393\Desktop\ai-legal-helper\docker-compose.yml stop`（**保留容器**）。备选 `… down`，但**严禁加 `-v`**（`-v` 会删卷）。
  3. 退出 Docker Desktop（托盘 → Quit），确认 `docker-desktop` distro 已停止。
  4. **Settings → Resources → Advanced → Disk image location** 改为 D 盘目标目录（`<需 Owner 填>`，如 `D:\DockerData`，以 Owner 选定为准）。
  5. Apply & Restart，等 daemon 就绪。
- **判据（迁移后逐条核）**：`docker info` 的 disk location 指向 D；`docker ps -a` 中三容器**健在**（或被 compose 重建）；`docker volume ls` / `docker image ls` 条目数**不少于**步骤 1 记录值；C 盘空间显著回收；`docker compose up -d` 后 `fazhi-backend` 回到 **healthy**。
- **回滚**：把 disk image location **改回原位置**（`C:\Users\33393\AppData\Local\Docker\wsl\disk`）并重启；**禁止删除 vhdx、禁止删除任何卷 / 镜像**。迁移失败 = 原样改回，如实报告。
- **责任与验收**：责任 = Owner（窗口与授权）/ 执行者（照做）；验收 = 判据全过 + 维护记录留档 + 随后按 `tickets/W12-engineering-gates.md` §Q3 补跑 `docker build` 包体门。**本助手不代做任何停 / 迁 / 启动动作**。

---

## B4 · W14 现役切换 / 凭据（Owner 专属）

- **目标**：完成现役环境切换与凭据核验 / 轮换（真源：`task-status.json` W14=`BLOCKED_OWNER`；`owner_decisions` C14 原文）。
- **需 Owner 提供（全部留空）**：目标环境 `<需 Owner 填>`；服务器 / 域名 `<需 Owner 填>`；**切流量授权** `<需 Owner 填>`（含"可切 / 可回退"口径）；**真实备份授权** `<需 Owner 填>`；**C14 遗留"13 字符原始值"的存活性核验结论** `<需 Owner 填>`。
- **前置 / 红线**：轮换 = **改口令**（DB / env 口令变更），**不是 git 操作**；**禁历史重写 / force-push**（C14 已裁"维持存量、不删不改、旧 3 ref 保留"）。任何凭据新值**不得落入本仓任何文件**。
- **C14 核验与轮换口径**：`task-status.json` C14 note 记 `10-10 '13-char raw value' in old history`，liveness UNKNOWN，**唯一动作项** = Owner 核验其现役性，若现役则轮换该凭据。
  - 待 Owner 澄清的不符点：`docs/process-archive/pending-owner-actions-20260926.md` 记一处 **13 位字面值**位于脱敏脚本 `dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py` 的模式串，并称该文件**不在远端历史里**；与 C14 note 的"在 old history"**记述不一致**，**以 Owner 现役核验为准**。
- **判据**：切换后现役入口可用且可回退；凭据核验结论有书面记录；若轮换，旧值确认失效。
- **回滚**：流量切回切换前入口；凭据轮换失败按备份口令回退（备份 / 新值均在 Owner 侧，**不入库**）。
- **责任与验收**：责任 = Owner；验收 = 上述判据 + 记录留档。**本助手不代切、不代填、不读凭据**。

---

## B5 · W08 真实五类 + 终轮 19 题

- **目标**：真实模型路径上的五类真实验收 + 冻结 19 题回归 + 法律专业签核（真源：W08=`NOT_STARTED`）。
- **需 Owner 提供（留空）**：真实模型 **路径 / 入口** `<需 Owner 填>`（含每类模型 / provider / endpoint / schema 取值；**key 值不入库**）；**法律专业签核人** `<需 Owner 填>`（姓名 + 签署日期）。
- **两个数字的出处（均已在执行书定位）**：
  - **「五类」**＝执行书 §W08："五类基础验收沿原B清单：**文本12题、rerank3组、图片2张、语音2段、Agent3 run**"；并见同书 §F 表：**文本 / rerank / Agent / 图 / 音**。
  - **「19 题」**＝同书 §W08 引用的 **`E/19题总账-v1.md`**（三批锚 `4552a9070a9b9774` / `56802fbfa1712f40`，仅作已核历史锚）。**该总账文件本体未在本仓检索到** ⇒ 19 题的**具体题目清单需 Owner 提供该总账或指定其位置**。
- **判据口径（抄执行书 §W08 出口）**：五类**逐项真实 PASS / FAIL / BLOCKED**；费用 / 实际发送边界如实；**合成 / 私有库结论不外推**真实语料或总体答对率；机器复核**不得**写专业审签。
- **前置 / 红线**：**不读 `.env` 找 key**（执行书 §W08 明写"不会把 `.env` 拿来找 key"）；进程启动前绑定私有 `DATABASE_URL` / `QUOTA_DB` / `CHROMA_DIR` / `HF_HOME` 等（真库网络 / 路径双拒绝）。
- **回滚**：真实批为只读式重跑、产物留版本；不改产品默认重试来凑数。
- **责任与验收**：责任 = runner owner（B）/ 图音子集（D）/ 独立判据（H）/ 专业签核（法律人）；验收 = 五类逐项结论 + 19 题回归 + 签核。**本助手不代跑真实模型**。

---

## B6 · C13 前端 API 基址

- **目标**：为前端配置真实 API 基址（真源：C13=`BLOCKED_OWNER`）。
- **需 Owner 提供（留空）**：前端 API 基址真实值 `<需 Owner 填>`。
- **为何不能由助手臆断**：C13 note 原文——"frontend API base address; Owner MUST configure the real value（assistant does not read/write `.env`）…cannot be decided without the target ⇒ stays Owner-only"。**臆断会把假值写进交付物**；且"助手不读 / 不写 `.env`"是硬边界。
- **前置 / 判据 / 回滚 / 责任**：前置 = 选定"新公共 API 地址"或"已验证的 same-origin 代理"（执行书建议以**真实网络 / SSE 测试**定案）；判据 = 前端经该基址连通真实网络 / SSE；回滚 = 改回原基址；责任 = Owner。**本助手不代配**。

---

## B7 · D-55 Chroma 副本对账

- **目标**：对账 Chroma 副本 / hook 基线（真源：`task-status.json` `D_index_status` 中 D-55："Chroma copy/hook authorized, verify object; shared hook install in W12"）。
- **需 Owner 指认（留空）**：**对账对象**——哪一个 Chroma 副本 `<需 Owner 填>`、**哪份 hook 基线** `<需 Owner 填>`。
- **已知基线（供指认参考，勿当唯一）**：`tickets/W12-engineering-gates.md` §4 记——共享 hooks 目录 = common `.git/hooks`（`core.hooksPath` 未设），现存 `pre-commit` / `post-checkout` / `post-commit`；2026-10-19 已验"共享 pre-commit 与 2026-10-17 记录一致"、隔离正负空例 3/3（`<RUN>/sandbox/hooktest`）；**本轮不改共享 hook**（改共享 git 元数据需专项授权）。
- **判据**：被指认副本与指定基线逐项一致（或差异列明）。
- **回滚**：**不删对象**，只记录差异。
- **责任与验收**：责任 = Owner 指认 + 执行者核对。**本助手不代指认、不代对账**。

---

## B8 · C03 三问裁决（QA 撤回契约：审核来源 / 读取资格 / 撤回机制）

- **目标**：对 `docs/ADR.md` 的 **`ADR-020`** 的三问作出裁决，以决定 ④孤儿向量 / ⑤重复向量 / ③QA 侧无删除入口 三项残余的**修法**（真源：`ADR-020` 文本 + 复核文档 §8.2）。
  **2026-10-20 已裁决**（Owner 指令：「按建议裁定，执行 B8 三问结论并推进代码修改」）⇒ 本条转为**「未做项与空位」的登记入口**。
- **为何只能由 Owner 裁决**：三问的答案同时决定**读侧契约**（谁能服务一条 QA、撤回后是否「隔离不删」）与**守卫判据**（是否允许 `_qa_store.delete()`）；助手自行决定＝**替产品定撤回契约**。故本轮只交付「提议态 ADR-020」，**未落一行代码**。
- **已裁决（2026-10-20「按建议裁定」）三问结论**：
  - 问 1（审核来源）＝**按建议裁定**：保留存量、不再新增 `auto_by_score_inferred`；存量按「人工复核后重签 `human`，否则不可服务」处置。
    **2026-10-20 Owner 复裁：不收紧读轴**（维持存量可服务，走人工复核路线）⇒ **无代码改动**。
    该选择已记入 `docs/ADR.md` 的 ADR-020「落地映射 · 问 1」；若日后改主意，须另起一次裁决（会推翻设计卡 §5 并改写 4 处判据）。
    ~~未做项（须再裁一次）~~ → **已复裁为「不收紧」，见上**。
  - 问 2（读取资格）＝**按建议裁定**：允许隔离不删，但必须**可观测** ⇒ 读数已落码（`/api/admin/stats` 的
    `qa_orphan_vector_records` / `qa_duplicate_candidate_ids`）。
    **阈值（2026-10-20 Owner 定）**：**孤儿向量＝非零即异常**（正常应为 0；它只由「先写向量、后提交」失败产生）⇒
    已落码为一条告警日志，归因键 `qa_orphan_vector_detected`（提交 `7f16b59`），每次读管理面统计时检查；
    **重复向量＝只记数、不告警**（当前无观测基线，不拍脑袋定数字）。
    **观测责任人**：Owner 本人（暂兼）。
    **仍缺**：真实告警通道的接收方（本仓只落日志键，未接外部监控；谁消费该键由运维侧定）`<需 Owner 填>`。
  - 问 3（撤回机制）＝**按建议裁定**：**默认不删**；合规 / 法定下架这类人工触发场景才允许删，且须「先 `commit` 再删、删失败**不阻塞**撤回」。
    ⚠ **本轮不实现任何删除路径**（`_qa_store.delete()` 仍不存在 ⇒ ③ 的 AST 守卫原样有效）；该路径只作**规格**保留，失效条件 3 成立时才落码。
  - **裁决人 + 日期**：Owner（指令＝按建议裁定 + 「孤儿非零即告警」）/ **2026-10-20**。姓名栏由 Owner 自填（本助手**不代填姓名**）：`<需 Owner 填>`。
- **前置检查**：① 确认 `ADR-020` 仍为**提议态**（未落代码）；② 确认下方三条失效条件**均未触发**；③ 若已触发（例如检索层已出现按 `cand_id` 去重的消费方），则**必须先重开该条**，不得沿用旧提议。
- **程序（逐条）**：① 读 `ADR-020` 的三问与建议；② 逐问给出结论（可采建议、可改选）；③ 由指定人把「**待裁定三问**」段替换为定稿「**决策**」段并补失效条件；④ 若裁决含「允许删除」，按 `ADR-020` 的「AST 守卫如何改」一节升级守卫（零删点 → 白名单 + 凭据 + **保留阳性对照** + 收口别名盲区）；⑤ 落码后走四门 + not-slow 全量 + 独立复核（沿用本批口径）。
- **判据**：`ADR-020` 状态由「提议（Proposed）」变为「已裁定（Accepted）」；三问各有书面结论；若含删除授权，则守卫的**阳性对照在注入「直写」与「别名/间接」两种 delete 形状时都能咬住**（现守卫对别名四种写法**不咬** ＝ 复核发现 F4）。
- **回滚 / 失效条件（出现任一条即须重开本条，不得沿用旧裁决）**：① 读出口出现「无 SQL 行仍可服务」的路径（孤儿将变成**可服务答案**的隐患，性质改变）；② 检索层出现按 `cand_id` 去重 / 计数的消费方（重复向量会改变召回排序）；③ 出现合规 / 法定删除要求（「默认不删」失效）。
- **责任与验收**：责任 = **Owner**（裁决 + 指派观测责任人）；验收 = 上款判据 + 台账侧登记「裁决人 / 日期 / 三问结论」。**本助手不代裁**。
- **时点（2026-10-20 对齐结论）**：**下一候选版本冻结（下一个 `freeze_hash`）前**必须裁决或**显式延期**；逾期须在收口台账中**显式标为未闭合**，不得沉默通过。

---

## B9 · 前端真机验收（R10 / R13 / R14 的 DOM 行为）

- **目标**：把本批前端三处**源码级接线钉子**升级为**真机行为证据**——这三处用例只证明「接线存在」，**不证明**浏览器里真的这样跑（真源：复核文档 §4 诚实边界第 4 条、§6 待办 4）。
- **为何只能人工**：需真实浏览器 + 真实交互（SW 注册、上传输入框重置、语音统一停止）；助手出任何"真机通过"结论都是**伪造证据**，故本票只交付**可执行清单**。
- **需 Owner 填（一律留空）**：执行人 + 日期 `<需 Owner 填>`；浏览器 / 版本 `<需 Owner 填>`；若失败，缺陷编号 / 处置 `<需 Owner 填>`。
- **前置检查**：① 前端可跑（`next dev` 或已部署入口皆可）；② 打开 devtools 的 Application / Console；③ 按下面每条给的操作步骤**可重复**执行。
- **逐条清单（页面 / 操作 / 期望）**：
  1. **R10（Service Worker 构建 ID 写入）**——页面：任意前端页（后台管理页优先）；操作：首次打开 → Application → Service Workers 确认已注册，并确认该 SW 脚本内含**本次构建**的构建 ID（由构建期 `scripts/write-build-id.mjs` 注入、源模板 `scripts/sw.template.js`）；期望：**构建 ID 与本次构建匹配**（不是上次构建的残留）；二次打开**不重复注册**、Console 无报错。
  2. **R13（上传输入框重置）**——页面：后台管理页上传区（`app/admin/sections/UploadSection.tsx`）；操作：选文件 → 触发上传 → 再点"选择文件"或关闭重开该控件；期望：**输入框已重置**——不会把上一次的文件重复提交，也不显示旧文件名。
  3. **R14（语音统一停止）**——页面：对话页（`app/chat/page.tsx`，`lib/hooks/useVoice.ts`）；操作：开始语音输入（浏览器若需授权先授权）→ 点"停止"或切换到其它输入态；期望：**只有一条停止路径**，停止后麦克风指示消失、无残留录音态，再点开始能正常重新开始。
- **判据**：三条各自「操作 → 观察」与期望一致（截图 / 录屏任一种留档）；任一条不一致 ⇒ 记为**缺陷**并给编号。
- **回滚**：无（只读式人工验收，不改代码）；发现缺陷另开修复票。
- **责任与验收**：责任 = **Owner**（人工执行）；验收 = 三条各有截图 / 录屏 + 结论。

### B9 执行结果（2026-10-20 实测）

| # | 结论 | 证据（新鲜读数） | 执行者 |
|---|---|---|---|
| **R10 Service Worker** | ✅ **通过** | 生产构建（standalone）下连读两次：注册条数 **1 / 1**（不重复）、`active.scriptURL = http://localhost:3100/sw.js`、`caches.keys() = ["fazhi-shell-ub2IHfyD_EFVMbRqttdFp"]`（＝本次构建号）、页面已被 SW 接管、Console 无 `[sw]`/error 消息 | 助手（经 Owner「接管」授权，**只读**取值） |
| **R13 上传输入框重置** | ✅ **通过** | 后端访问日志出现**两条** `POST /api/admin/knowledge/upload`（`15:00:04` 与 `15:01:10`，均 **400** ＝空文件不入库）⇒ 失败后能重选**同一文件**并再次提交，正是原缺陷（只在成功分支清空）的修复点 | Owner（真实交互） |
| **R14 语音统一停止** | ⏳ **待 Owner 执行（环境已满足）** | 2026-10-21：现役后端 `/api/health` 返回 `capabilities.voice_transcribe=true`。**入口用生产镜像 `http://localhost:8088/chat`**（镜像 `fe298901d089`，API 基址已改为**同源相对 `/api/*`**，页面 8 个分片绝对基址命中 0，`POST /api/auth/login` → 401 可达）；dev 入口 `http://localhost:3000/chat` 亦可用（`NEXT_PUBLIC_API_URL=http://localhost:8088`，跨域预检 200）。**旧标签页须硬刷新（Ctrl+Shift+R）或换无痕窗口**：此前 bundle 内联的是不可达的 `http://162.14.81.34:8000`，浏览器控制台会报 `ERR_CONNECTION_TIMEDOUT`（详见部署门禁报告 §8.12 / §8.13） | — |

**口径更正（重要，防误读）**：
1. **Dev 模式不会注册 SW**，这是设计（`app/SWRegister.tsx` 首行即 `if (process.env.NODE_ENV !== "production") return`）⇒
   **在 `next dev` 下看到 0 条注册不算缺陷**，R10 必须在**生产构建**下验。本轮即为此切到 `output: standalone` 的 `node .next/standalone/server.js`。
2. R10 的读数由**助手**读取（不是 Owner 自验），但为**只读**（未点击、未填表、未登录）；
   若需 Owner 亲自复核，可按 B9 清单在独立浏览器里重做一遍，两者不冲突。
3. R14 环境已于 2026-10-21 满足（`voice_transcribe=true`）；待 Owner 在浏览器执行清单并留证据。

**仍缺**：R14 的真机证据（环境前置已于 2026-10-21 满足，待 Owner 执行）；Owner 若要留存 R10/R13 截图，可随时补充到本表。

- **已知基线（已更新，防误读）**：`npm run format:check` 已于 2026-10-20 **修复并在本批转绿**（提交 `0baf189`：只格式化那 2 只文件、**不做全仓格式化**；
  读数 `All matched files use Prettier code style!`；同期 `npm run check` 14 files / 103 tests passed、`npm run build` rc=0）。
  格式门绿 **≠** 真机证据；真机结论见上表（R10 ✅ / R13 ✅ / R14 ⏳ 待执行）。

## B10 · 模型 provider / 能力位核对（**结论前必须先跑这套**）

- **为什么要立这条**：2026-10-20 助手连续两次把"读到的局部信息"当成"现役事实"——
  ① 先说《刑法》第二十四条"库里没有"，实测库里有；② 先说语音缺"阿里云 key"，实际部署覆盖写的是另一套配置。
  两次都是**没做容器内实测就下结论**。本票把正确的取证顺序固定下来，避免复发。
- **取证顺序（固定，不许跳步）**：
  1. **先读部署覆盖** `LLM_MODELS_JSON`（这是实际生效的角色表，不是代码里的 `DEFAULT_ROLES`）；
  2. 再确认 **Owner 指定的 provider 与模型名**（默认表只能当"默认"，不能当"事实"）；
  3. 最后才看 `settings` 默认值与代码分支——它们只解释"为什么没生效"，不定义"生效的是什么"。
- **只读诊断命令（在现役容器内；只打印布尔与域名，禁止打印 key 值）**：
  - 角色表：解析 `LLM_MODELS_JSON` 后逐条打印 `key / model / modality / provider / base_url 域名 / capabilities / api_key 是否存在`
  - 已载入与跳过：`registry` 的 entries 列表 + skipped 归因
  - 能力位：`GET /api/health` 的 `capabilities.image_chat` / `capabilities.voice_transcribe`
  - 凭据传递：确认 `docker-compose.yml` 的环境变量白名单**确实传了**该 provider 的 key 变量（改前 `SILICONFLOW_API_KEY` 与 `DASHSCOPE_API_KEY` **都没传**）
- **判据**：能力位为 `true` **且** 角色表里对应条目处于已载入状态；只看其一不算通过。
- **硬约束（写进纪律）**：凡结论涉及"现役配置 / 能力 / provider"，**必须附容器内实测读数**；
  没有实测的，只能标"**推断**"，不得写成结论。

### B10 附：视觉/语音改走硅基流动的配置（ADR-021，待 Owner 落 .env）

- 模型（Owner 2026-10-20 指定）：视觉 `Qwen/Qwen3.5-4B`、语音 `XingChenAGI/XingChenASR-V3.2-Ultra`，均 `provider: siliconflow`。
- **生成仍由 text 模型承担**（代码侧已加守卫：`_default_entry` 在默认 key 未命中时**先找 text 模态**）。
- 需 Owner 在根 `.env` 里：① 置 `SILICONFLOW_API_KEY=<真实值>`（**不入库、不贴聊天**）；
  ② 把 `LLM_MODELS_JSON` 更新为下面三条（语音必须带 `transport: audio_transcriptions`，因为 ASR 模型走 `/audio/transcriptions`，不是 chat）：

```json
[
  {"key": "longcat_text_flag", "model": "LongCat-2.0", "modality": "text", "tier": "flag", "priority": 0, "capabilities": ["text"]},
  {"key": "vision_sf", "model": "Qwen/Qwen3.5-4B", "modality": "vision", "tier": "flag", "priority": 0, "capabilities": ["text", "vision"], "provider": "siliconflow"},
  {"key": "voice_sf", "model": "XingChenAGI/XingChenASR-V3.2-Ultra", "modality": "voice", "tier": "flag", "priority": 0, "capabilities": ["speech", "asr"], "provider": "siliconflow", "transport": "audio_transcriptions"}
]
```

- **前置未核实的假设（部署后必须冒烟）**：`Qwen/Qwen3.5-4B` 需能接收图片内容块；`XingChenASR` 需提供 `/audio/transcriptions`。
  若上游不接受，会在第一次真实调用时**显式报错**（不静默降级）。
- **部署动作（需 Owner 明确授权）**：重建 `fazhi-backend` 容器（会中断现役服务约 10–60 秒，并会上线候选代码）。

---

## 附：B3 不在本文件范围

- B3（pip-audit 有修复版漏洞三分表，**不升版**）为 A 类可自决项，由执行计划 P5 处理，**不属于**本文 B1–B10。

---

## 需 Owner 填的空位（汇总）

| 项 | 空位 |
| --- | --- |
| B1 | `haimeng` 签名 + 签核日期；并确认签核落点（见 B1 注） |
| B2 | 维护窗口时间；D 盘目标目录取值 |
| B4 | 目标环境；服务器 / 域名；切流量授权；真实备份授权；C14 13 字符值现役结论（+ 若轮换的新口令，**不入库**） |
| B5 | 真实模型路径 / 入口（含 key，**不入库**）；法律专业签核人姓名 + 日期；`E/19题总账-v1.md` 或其位置 |
| B6 | 前端 API 基址真实值 |
| B7 | 对账对象：哪个 Chroma 副本；哪份 hook 基线 |
| B8 | 三问结论**已裁决**（按建议裁定，2026-10-20）；孤儿阈值＝**非零即异常**（已落告警日志 `7f16b59`）、重复＝**只记数**、观测责任人＝**Owner（暂兼）**；**仍缺**：告警键的运维接收方、裁决人姓名 |
| B9 | **R10 ✅ / R13 ✅ / R14 ⏳ 待 Owner 执行**（后端 `voice_transcribe=true`，2026-10-21 已满足；入口 `http://localhost:8088/chat`，旧标签页须硬刷新）；仍缺：R14 的真机证据；截图可选补充 |
| B10 | **需 Owner**：根 `.env` 置 `SILICONFLOW_API_KEY`、把 `LLM_MODELS_JSON` 换成 B10 附的三条；**并授权重建 backend 容器**（会上线候选代码、中断 10–60 秒） |

## 声明

- 本文是**前置物**：只交"清单 + 命令 + 判据 + 回滚 + 责任"，**不代做**（不代签 / 不代配 / 不代切 / 不代跑 / 不代对账 / 不代裁）。
  **B9 的例外已如实标注**：R13 由 Owner 真实交互完成；R10 由助手在 Owner 授权「接管」后**只读**取值（未点击 / 未填表 / 未登录），
  并非助手"代验通过"——表内「执行者」列逐条写明。
- **凭据与真实库边界（含本轮例外，逐条披露）**：本轮助手**未读** `.env`、真实业务库数据、真实会话内容、任何凭据值。
  **例外一（经 Owner 书面同意）**：为核实「《刑法》第二十四条是否在库」，在现役容器内对 Chroma **只读**查询了
  「该条号下各法名计数」与「该记录的 metadata」，**未取用也未输出任何条文正文**；结论为该条**在库**（`source=刑法`）。
  **例外二（经 Owner 授权「接管」）**：在候选前端读取了 `navigator.serviceWorker.getRegistrations()` / `caches.keys()`
  两项**技术状态**（未点击、未填表、未登录、未读任何用户数据）。
  其余**只读**命令仅为：`docker version / ps / info / compose ls`、`docker inspect`（仅取 compose 标签）、WSL 发行版列表、文件大小与盘符余量读数。
- 本文**不含** `:NNNN` / `.py:NN` 形式的行号引用；所有定位使用**文件路径 + 符号名 / 栏目名**。
