# R15 版本绊线 + git 历史修复 —— 会话进度与待办报告

- 生成时刻：2026-09-19 02:1x（live `master` tip = `4465080`，`rev-list --count HEAD` = **28**）
- 责任会话：R15 主线 + "你来修复git" 的执行方
- 复核口径：本报告每个数字后面标 **（实测）** = 本会话命令直读；**（复算）** = 由实测值推导；**（推断）** = 证据未闭合
- 并行环境：同一工作树被 ≥2 个会话同时编辑，`aaf088b` 之后又落了 **7 个提交，其中 1 个是我的 `5afc8d0`、
  6 个来自并行会话**（`e3c023a` `b61bc08` `fe40b0c` `105907b` `61fbd11` `4465080`），现 tip = `4465080`，
  故本报告全部结论都标注了所属 tip SHA，过期请按 SHA 重测

---

## 一、结论摘要

1. **R15 法律版本绊线已收口**：真源 + 默认关开关 + verifier 门 + service 透传 + runner 注入 + 分水岭对照样本，
   7 个提交，车道测试 **+23**，全量 **1266 passed / 0 failed**（实测 @`aaf088b`）。行为逐字不变（flag 默认 `False`，
   在 HEAD 里复测：`backend/settings.py:88 law_version_tripwire_check: bool = False`）。
2. **对照臂已跑完（真实模型调用）**：病在、治有效、不误伤；同时暴露一个比 R15 更大的洞 ——
   **版本判定只存在于 agent 路径，而线上流量 100% 走快车道**。**（实测）**
3. **git：内容侧全修好、携带侧另建了验证过的完整备份；live 仓库不可 push 是结构性事实，不是待修的 bug。**
   两处洞中只有 blob 那处可修，已修；父提交 `0263bd5` 四处取证均不存在，**（高置信）永久缺失**。

---

## 二、R15 交付明细

### 2.1 提交链（每行都 `git show --stat` 复述，非记忆）

| SHA | 时刻 | 内容 | 规模 |
|---|---|---|---|
| `7d4b2da` | 09-18 22:58 | `limitation_calc.law_version_crosses_watershed()` 真源（纯新增，未接线） | 2 files, +92 |
| `247466b` | 09-18 23:10 | verifier 绊线门 + 基准日随 PASS 结果喂给 `render_verified` 二次验证（默认关） | 3 files, +138/−4 |
| `cf35983` | 09-18 23:12 | `service` 向 verifier 透传 `run.law_as_of` + watch-it-fail 留痕 | 2 files, +39 |
| `5aa9dbd` | 09-18 23:21 | `gate2_runner` 按案例 `as_of_date` 注入 + `_round1_payload` + `--no-as-of-date` + 分水岭样本 | 3 files, +180/−5 |
| `63c5101` | 09-18 23:26 | `repository.create_run` 缺省边界留痕（代码一字未动） | 1 file, +3 |
| `aaf088b` | 09-18 23:30 | 调用点补 `cast(date \| None, …)`（`mypy .` 全仓口径才暴露） | 1 file, +4/−1 |
| `5afc8d0` | 09-19 00:34 | 绊线命中时落**被判定 claim 原文**（对照臂暴露日志不可归因） | 2 files, +12 |

### 2.2 数字

- 车道测试：`test_r15_version_tripwire.py` + `test_r15_runner_injection.py` + `_r15_tripwire_probe.py`
  = **23 tests collected（实测，`--collect-only`）**；文件规模 158 / 89 / 38 行
- 全量：脏树基线 **1240 passed / 4 failed** → 收口 **1266 passed / 0 failed @`aaf088b`（实测）**
- 合并他人提交后重跑（防"全绿过期"）：`test_r15_*` + `test_agent_verifier` + `test_phantom_check` + probe
  = **93 passed / rc=0 @`105907b`（实测）**；`test_log_field_whitelist` 单独 **2 passed（实测）**
- 评测样本：`evals/watershed-cases-r15.json`（67 行，sha256 前缀 **`7cc61193e7cd53ce`（实测，与计划里记录一致）**），
  `schema_version: r15-watershed-v1`，`status: NOT_FROZEN`，W01=2019-03-05 / W02=2023-08-01，`as_of_date` 均 2026-09-18
- 分水岭：2021-01-01《民法典》1260 条；民 188=3 年、20 年上限不中止不中断；劳调 27=1 年；民法通则 135=2 年

### 2.3 计划期被审出来的两个真问题（`vet-plan-new`）

- **F1 `render_verified` 二次验证**：不带 `law_as_of` 会让 flag-on 路径 100% 以 `VERIFIER_NOT_PASS` 失败。
  修法 = `VerificationResult` 携带 `law_as_of`。两次 mutation 分别打红 1 条 / 2 条（实测）。
- **F8 单文件 mypy 盲区**：`mypy agent/verifier.py` 绿、`mypy .` 红，因 `models.py` 用 legacy `Column(Date)`。
  ⇒ 已固化成纪律："改调用点必须跑全仓 `mypy .`"（记忆条目 (l)）。

### 2.4 对照臂三臂读数（真实模型，Owner 指示"你来执行"后才花的钱）

| 臂 | 配置 | 读数 |
|---|---|---|
| A0 | 快车道（`AGENT_ENABLED=False`，即线上现状） | 给出**跨越分水岭的错误期间法条** |
| A | agent 路径，绊线关 | 同样给出错误期间法条 |
| B | agent 路径，绊线**开**（仅运行期 env 注入，代码默认未改） | `FAIL_SAFE` + `LAW_VERSION_WATERSHED_MISMATCH` |

顺带查出：① 快车道**没有任何版本判定**（战略级覆盖缺口）；② 命中日志只有 `verdict=FAIL_SAFE` 不可归因（已由 `5afc8d0` 修）；
③ 案例 `fact_reveal` 关键词需调参；④ 观察到海事法院 / 商业银行法的**跨域语料污染**。**（均实测）**

---

## 三、git 历史修复

### 3.1 损坏定性（推翻两条既有结论）

| 洞 | 位置 | 可修性 |
|---|---|---|
| 缺父提交 `0263bd5`（`76c1eea` 的父） | 断边 `c22236d → 76c1eea → 0263bd5` | **不可修**：live / `.git-backup-20260916` / 远端 204 链 / replace 残骸 四处零命中；仅以 `git fsck` 的 `invalid reflog entry` 形式存在 |
| 缺 blob `04463121`（最旧 3 提交的 `backend/agent/service.py`，26198 字节） | `76c1eea` / `c22236d` / `2412acd` | **已修**（见 3.2②） |

订正记录：
- "只能连读 16 个提交" **不准确**，断点实测在 `76c1eea` 的父。
- "修复方向是 `git fetch origin`" **曾被我一度改口为完全无用，也不准确**：远端确实有那个缺失 blob，
  但 fetch 协商**按 ref 不按对象** ⇒ advertise `have 15562fc` 就整段重传 `15562fc..985d53e`，
  实跑 11 分钟 44MB 后被我自套的 `timeout 600` 杀死（`invalid index-pack output`）。
- "另一会话记的 graft 父 `065981a4`" 来源已查明：**只存在于 reflog 坏条目**，对象从来不在库里 ⇒ 该建议从写下起就不可执行。

### 3.2 执行的动作

**① `git replace --graft 76c1eea`（撤销 = `git replace -d 76c1eea`）—— 只作用于读侧**

| 能力 | 修前 | 修后 |
|---|---|---|
| `git rev-list --count HEAD` | fatal | **28 / rc=0（实测）** |
| `git log -- <path>` | fatal | 可用（`service.py` 现可见 6 条历史） |
| `git status` / `git diff HEAD~1 HEAD` | 部分可用 | rc=0 |
| `git bundle` / `clone` / `push` | fatal | **仍 fatal** —— `pack-objects` 故意忽略 replace refs |

**② 缺失 blob 回填（成本从"几百 MB 历史"降到 390KB）**
`git clone --filter=blob:none --no-checkout --single-branch --branch master <origin>`（**390KB**）
→ 按需 `cat-file blob` 取到 26198 字节 → live 里 `git hash-object -w --stdin`
→ **重算哈希 = `04463121c3aec0cd194dde4314f40e21d813ed00` 全等**（逐字节自校验，不可能补错）
→ 3 个提交 `git archive` rc **255 → 0（实测）**。**绝不在 live 做浅 fetch**（会留 `.git/shallow`，实测侥幸没写）。

**③ 可携带完整备份：`Desktop/fazhi-rescue-4465080-20260919/`**（`repo.git` + `fazhi-master-4465080.bundle` 130MB + README）

- 生成：live 只读 `git fast-export master | git fast-import`（重建成本已降到 ~1 分钟）
- **28/28 提交 tree 哈希逐一对应全等**；tip tree = live master tree = `edd112bd5ff353cb228f2b3ef3aee03ce16fbccd`
- `author|email|date|subject` 28 行 diff 为空；`git ls-files` = 2153 = live
- `git bundle verify` → "The bundle records a complete history"；**从 bundle 克隆 rc=0、克隆内全量 `git fsck` 零输出、
  `git log -- <path>` 可用、`git archive HEAD` rc=0**
- 旧 23 提交版 `fazhi-rescue-20260919/` **已删除**（新版真子集，防两代备份混淆）

### 3.3 明确没做的三件（都是决定，不是遗漏）

| 不做 | 理由 |
|---|---|
| 重写 `master` 使其可 push | 换 28 个 SHA ⇒ 别的会话与全部文档里的提交号悬空，收益又与救援仓库重叠。风险收益不对称 |
| force push 到 origin/master | 会**盖掉远端 204 个 `sync:` 快照**，那是 09-17 之前唯一完整记录 |
| `git gc` | `.git` 里 garbage **306MB（实测）**：5 个约 50MB `objects/15/tmp_obj_*`（09-18 21:33–22:24）+ 2 个 `tmp_pack_*`。中断写入窗口与对象丢失窗口重合，一把清会连线索一起抹 |

---

## 四、推送 / 备份的风险评估（Owner 问"有什么风险和危害"后量出来的）

- 🔴 **origin 是公开可读的**：`git -c credential.helper= ls-remote` 匿名 rc=0 拿到 refs（GitHub 只对公开仓放行匿名读）。
  ⇒ 我先前建议的"推到 origin 新分支并存"**已当场撤回**。推上去会新增公开的增量：**17 个新增 + 30 个修改文件（实测）**
  （`backend/tests` 21、`backend/agent` 6、`backend/scripts` 5、`evals/watershed-cases-r15.json`、`dispatch-output/over2-replay-20260919` 5 …）。
- 🔴 **真正的泄露向量不在仓库里，在未跟踪留痕里**：`git grep` 实测**受跟踪文件里真形态密钥命中 0**；
  而根目录 `_*` 未跟踪条目 **97 个**中有 **1 个** 含 `sk-` + 20 位以上真实形态密钥（就是我那次的红测日志）。
  `.gitignore` **没有任何 `_*` 规则**（`check-ignore` rc=1 无输出、`git status` 显示 `??`）
  ⇒ **任何会话一次 `git add -A` / `commit -a` 就会把真密钥推上公开仓。**
  **已处置**：整文件移动到已忽略的 `.workbuddy/evidence/r15-tripwire-t2-red.txt`（未改写、未删除，红测证据保留，`git status` 已看不见）。
- 🟠 **同盘备份不是备份**：救援 bundle 与被修仓库在同一物理盘，而 Desktop 正是对象丢失的头号嫌疑环境。
  已排除一项：`C:\Users\33393\OneDrive` 存在，但 Desktop 未被重定向进 OneDrive（注册表 `%USERPROFILE%\Desktop`）**（实测）**。
- 🟠 **`diag/` 里有 894 个受跟踪文件、306.6 MB 的 chroma 索引二进制（实测 `ls-tree -l` 汇总）**
  —— 更正我上一条口头答复里的"~283MB/10 文件"（那只统计了 >5MB 的 10 个）。
  它们**在公开远端 tip 里早已存在** ⇒ 不是推送新增暴露面，但推上去会连带，且使 bundle 臃肿。
- 🟡 **既存但已排除的假警**：`dispatch-output/agent-mainline-fix-20260911/verify.ps1` 与 `agent-timeout-h1-20260912/verify-h1.sh`
  硬编码 4 个凭据字样，但判为**合成占位值**：三家厂商共用同一 27 字节值、22 字母 + 5 短横、**0 位数字**、含 `test`/`ci-`。
  两份文件在公开远端 tip 里**已存在且字节相同** ⇒ 非新增暴露面。**（实测）** 属"模板下一步可能被人填真值"的地雷。
- 🟡 **SHA 永久分叉**：救援仓库父链被重建 ⇒ 文档里的 `5afc8d0` 这类引用在其中查不到，须按 subject/日期查。
- 🟡 **graft 不随 bundle 走**：读侧修复是**本机**的，新克隆读到的仍是断的原始历史。
- 🟡 **期望风险**：备份落地后易被理解为"git 修好了"，但 live 依旧推不动 —— 一次 `git checkout -- .` 仍能带走未提交的共享基础设施。

---

## 五、待办项（按谁能推动分级）

### A. 需 Owner 决策 / 授权（我不会自行执行）

| # | 事项 | 完成判据 |
|---|---|---|
| A1 | 把救援 bundle 拷到**另一块物理介质**（唯一对抗磁盘故障的一层） | 异机 `git clone <bundle>` rc=0 |
| A2 | 若仍要远端备份：先确认目标仓 `visibility=private`，再决定推哪条链、是否先剥 `dispatch-output/**` 与 `diag/**` | 目标仓 Settings 截图/`gh repo view` 显示 PRIVATE；推送后 `git rev-list --count` 对得上 |
| A3 | `.gitignore` 增根目录留痕规则 **`/_*`**（防 `git add -A` 带走密钥）——共享文件改动，需点头。**不要写成 `_*`**：实测它会匹配任意层级、命中 9 个已跟踪探针/`__init__` 文件 | `git check-ignore -q _probe.txt` rc=0 **且** `git check-ignore -q backend/tests/_r15_tripwire_probe.py` rc=1 |
| A4 | `_r15tripwire_t2_red.txt` 已移到 `.workbuddy/evidence/`；**是否销毁由你定**（我判定它是不可再生的红测证据，故只移不删） | 你回一句"留/删" |
| A5 | 承认历史分界：09-17 深夜起本地是另一条 curated 链，远端 `sync:` 链作 09-17 之前归档，**不再试图接线** | 文档落笔即完成 |
| A6 | 三条未跟踪 `docs/` 订正是否入快照 | `git ls-files docs/…` 命中 |

### B. 建议作为下一票（我判断价值最高，但未获派票）

| # | 事项 | 为什么排第一 |
|---|---|---|
| B1 | **快车道的版本判定覆盖缺口**：`AGENT_ENABLED=False` 时线上 100% 走快车道，那里没有任何版本判定 | 绊线只在 agent 路径 ⇒ 真实对照臂 A0 直接把错误期间法条放出去了 |
| B2 | `fact_reveal` 关键词调参后再把 `watershed-cases-r15.json` 用于真实评测批 | 现在跑评测会得到假阴性（案例本身喂不进去） |
| B3 | reason-code 落路由日志（可观测性白名单）单独立票 | 现在归因靠 claim 原文，不够结构化 |

### C. 已登记但明确不动手（别撞车道）

- `calc_limitation` 零调用方（清理需全仓引用面确认）
- `CHROMA_DIR` 被 6 个运维脚本忽略 —— **另一会话在做**（`fe40b0c`/`105907b` 就是它）
- `docs/code-review-standard.md:80` 文档漂移
- `state_machine.py` / `prompts.py` / `gate5_judge.py` **仍冻结**，触碰需决策卡

### D. 我下次可自行推进（低风险、不必授权）

- 救援仓库**刷新**到当时 tip（`fast-export` 一条链，~1 分钟），并把报告里的 SHA 一起更新
- 用 `-r` 重跑一次未跟踪留痕的密钥扫描（本次扫描**未覆盖目录内部**，见 §6）
- `.git` 里那 2 个 `tmp_pack_*`（其中 44MB 那个是我自己那次被杀的 fetch 留的）—— 确认无 git 进程后清掉

---

## 六、已知限制（诚实清单）

1. **§4 的密钥扫描范围不完整**：`grep -E "sk-[A-Za-z0-9]{20,}" _*` 未加 `-r`，**目录内的未跟踪文件没吃到** ⇒
   "命中 1 个"是**下界**。后续动作在 D 类。
2. 全量 **1266 passed / 0 failed** 是在 `aaf088b` 时刻；此后又落了 7 个提交（1 个我的 `5afc8d0` + 6 个并行，
   现 tip `4465080`），**未在当前 tip 重跑全量**（只重跑了两线交接面 93 passed @`105907b`）。
   "当前 HEAD 全绿"这句本报告**不作声明**。
3. 对照臂每臂样本量 = 1（W01/W02 各一次），趋势性结论够，**统计性结论不够**。
4. flag-on 的评测批开启**仍是预登记事项**，本会话只在运行期 env 注入翻旗，**没有**改任何默认值。
5. `mypy scripts/` 被仓库配置排除 ⇒ `gate2_runner` 的类型问题只能靠 review + 测试兜（F7）。
6. 救援仓库 SHA 与 live 不一致（§4 最后一条），跨仓库对照只能用 subject/日期。
7. 报告里凡"永久/不可修"的判断，都限定在"当前可获取的对象集合"内 —— 若将来出现可信的第二份历史
   （例如别的机器有 09-17 之前的完整 clone），`0263bd5` 仍可能被带回。

---

## 七、现场状态快照（交接用）

- **生效中的本机配置**：`git replace` 共 5 条（4 条 filter-repo 残骸 + 1 条本会话的 `76c1eea` graft）。
  撤销本会话那条：`git replace -d 76c1eea694f487d36e7016a3f258d6bd2972faa9`
- **磁盘新增**：`Desktop/fazhi-rescue-4465080-20260919/` = 260MB（`repo.git` + bundle + README）
- **仓库内本会话留下的文件**：`_r15_afterhead.txt`、`_wl_afterhead.txt`、`_push_risk_scan.py`、
  `_push_risk_probe2.py`、`_push_risk_shape.py`、`_push_risk_report.txt`、本报告、`.workbuddy/memory/2026-09-19.md`、
  `.workbuddy/evidence/r15-tripwire-t2-red.txt` —— **全部未跟踪，未 stage，其中一个含密钥**
- **后台任务**：3 个网络任务的 shell 均已结束/停止。`--depth=1` 那个已 TaskStop 并删目录；blobless 那个 420KB 临时目录已在 02:4x 删除（blob 已回填，不再需要）
- **R15 计划文档**：`docs/process-archive/superpowers/plans/2026-09-18-r15-law-version-tripwire.md`（含 审核记录 / 收口记录 / 对照臂真实读数 三段）
- **git 修复留痕**：`.workbuddy/memory/2026-09-19.md`（诊断 → graft → fetch 失败 → blobless 回填 → 救援换代 → 风险评估 全程）
