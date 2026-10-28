# 交接：R15 版本绊线 + git 历史修复 —— 接手必读

- 交接方会话：R15 主线执行方 + Owner 指示"你来执行 / 你来修复git / 把进度写成报告"的同一会话
- 交接时刻：2026-09-19 02:3x；live `master` tip = **`4465080`**，`git rev-list --count HEAD` = **28**
- 接手方：另一个助手会话
- 阅读顺序：§0 自检 → §1 环境事实 → §2 禁令 → §4 你要做的事。**不要跳过 §1/§2 直接动手。**
- 引用纪律：本文所有代码位置**以符号名为准**，行号只是当时的实测快照（本仓库行号会漂，见 §1-8）

---

## 0. 动手前 60 秒自检（把仓库现状重新量一遍，别信本文）

```bash
git log -1 --pretty='%h %ad %s' --date=iso   # tip 是否还是 4465080
git rev-list --count HEAD                     # 28；fatal 说明 graft 被别人删了
git replace -l | wc -l                        # 5（4 条 filter-repo 残骸 + 1 条本会话 graft）
git bundle create /tmp/probe.bundle master 2>&1 | tail -2   # 必 fatal：缺 0263bd5，这是预期，不是新损坏
ls .git/hooks/ | grep -v sample               # 只有 post-checkout / post-commit，无 pre-commit
ls -l /c/Users/33393/Desktop/fazhi-rescue-4465080-20260919/  # 备份是否还在
```

判读：第 4 行**报 fatal 是正确的**。如果你的操作让它变成 rc=0，说明有人重写了 master —— 立即停手上报。

---

## 1. 环境前置事实（8 条，全部实测，会直接导致错误结论）

1. **仓库有洞且补不回来**：`76c1eea` 的父提交 `0263bd5` 在 live、`.git-backup-20260916/`、远端 204 提交链、
   replace 残骸 四处均不存在；只以 `git fsck` 的 `invalid reflog entry` 形式出现。后果：**`push` / `clone` / `bundle`
   从 live 必失败**，报 `Could not read 0263bd5 … pack-objects died`。**这不是你改坏的。**
2. **本机有一条 `git replace --graft 76c1eea`（本会话建的，只作用于读侧）**：它让 `rev-list` / `git log -- <path>`
   恢复可用。但 `pack-objects` 故意忽略 replace refs ⇒ 它救不了打包/推送；而且**它不随 bundle 走**，
   从救援仓库新克隆的树里 `git log -- <path>` 是另一种行为。撤销：`git replace -d 76c1eea`。
3. **提交前门禁没接进 git**：`.git/hooks/` 里只有 `post-checkout` 和 `post-commit`，`core.hooksPath` 未设。
   ⇒ `git commit` 成功 ≠ 门禁过。要显式跑 `backend/venv/Scripts/pre-commit.exe run --files <本次文件>` 并回报 rc。
   注意有 `post-commit` 钩子：**提交后会动东西**。
4. **同一工作树被 ≥2 个助手会话并行编辑，干扰是双向的**。本会话期间 `aaf088b..HEAD` 落了 7 个提交（我 1 个、并行 6 个）。
   曾实测到别人往**共享索引**里 stage 文件（`A dispatch-output/…`）。⇒ 提交必须 `git commit -- <显式路径>`，
   提交后 `git show --stat HEAD` 复核；不属于本会话的文件一律不 stage、不"顺手修"，在报告里点名归属。
5. **`.gitignore` 没有任何 `_*` 规则**（实测 `check-ignore` rc=1），而仓库根有 **97 个** `_*` 未跟踪留痕条目。
   ⇒ **一次 `git add -A` / `commit -a` 就可能把含真密钥的留痕提交上去**（本会话实测确有 1 个文件含 `sk-`+20 位真形态密钥，
   已整文件移到 `.workbuddy/evidence/`）。永远用显式路径 add。
6. **`--basetemp` 绝不能设在 `backend/` 内**：`tests/test_log_field_whitelist.py` 递归扫 `backend/` 全树找未登记日志字段，
   它自己造的哨兵样本落在 `tmp_path` 里 ⇒ basetemp 在 backend 下必红，且 pytest 保留失败用例的 temp 目录 ⇒ **下一轮继续红**。
7. **取证本身的陷阱**（本会话又踩过一次）：
   - 退出码**不能在管道之后取**（`git clone … | head; echo $?` 拿到的是 `head` 的码）。后台任务通知的"exit code 0"
     也常常是**包装命令**的码，不是 git 的（我那次真实是 `rc=124`）。
   - PowerShell 重定向产物是 **UTF-16LE**，按 utf-8 读会静默假阴性。
   - `dir_path` 已定工作目录，命令里再 `cd ..` 会走出仓库，产出"看起来成立"的假证据（否定式判断出现时先看错误行里的路径）。
   - **计数不能在 `| head` 之后做**。
8. **行号会漂**。本仓库已多次实测到交接文档里的行号失效（`:483-485→:496-498` 等）。引用**按符号名/测试名**锚定。

---

## 2. 四条硬红线（越界即停手上报，不要"顺手修好"）

| # | 禁令 | 为什么 |
|---|---|---|
| R1 | **不重写 master**（`filter-repo` / `filter-branch` / `replace --graft` 物化 / 任何改历史） | 换 28 个 SHA 会让别的会话与全部文档里的提交号悬空；收益与救援仓库重叠 |
| R2 | **不 `git push`，尤其不 `--force`**；origin 当前**是公开可读仓**（实测匿名 `ls-remote` rc=0） | force 会盖掉远端 204 个 `sync:` 快照（09-17 之前唯一完整记录）；任何推送都等于公开发布 |
| R3 | **不 `git gc` / 不清 `.git` 里的 garbage**（306MB：5×`objects/15/tmp_obj_*` + 2×`tmp_pack_*`） | 中断写入窗口与对象丢失窗口重合，一把清会连案发现场一起抹 |
| R4 | **不碰冻结文件**：`state_machine.py` / `prompts.py` / `gate5_judge.py`；不改任何 feature flag 的默认值 | 触碰需 Owner 决策卡；flag 开启属评测批预登记事项，不是代码改动 |
| 附 | **严禁**把 `.env`、密钥、用户数据、`chroma_db/`、`*.db` 提交进仓库 | Owner 长期约束 |

---

## 3. 我已经做了什么（三段，每段都给"证据在哪"）

### 3.1 R15 法律版本绊线 —— 已收口，7 个提交

| SHA | 时刻 | 内容 | 规模 |
|---|---|---|---|
| `7d4b2da` | 09-18 22:58 | `limitation_calc.law_version_crosses_watershed()` 真源（纯新增未接线） | +92 |
| `247466b` | 09-18 23:10 | verifier 绊线门 + `VerificationResult.law_as_of` 喂给 `render_verified` 二次验证 | +138/−4 |
| `cf35983` | 09-18 23:12 | `service` 透传 `run.law_as_of` + watch-it-fail 留痕 | +39 |
| `5aa9dbd` | 09-18 23:21 | `gate2_runner._round1_payload` + `--no-as-of-date` + 分水岭对照样本 | +180/−5 |
| `63c5101` | 09-18 23:26 | `repository.create_run` 缺省边界留痕（代码一字未动） | +3 |
| `aaf088b` | 09-18 23:30 | 调用点补 `cast(date \| None, …)` | +4/−1 |
| `5afc8d0` | 09-19 00:34 | 绊线命中时落**被判定 claim 原文**（日志可归因） | +12 |

关键锚点（按符号找）：
- `backend/agent/limitation_calc.py :: law_version_crosses_watershed`（纯函数，分水岭 = `CIVIL_CODE_EFFECTIVE` = 2021-01-01）
- `backend/settings.py :: law_version_tripwire_check`（**默认 `False`**，实测在当前 HEAD 仍是 False）
- `backend/agent/verifier.py :: DeterministicVerifier.verify(law_as_of=…)`、`_result(..., law_as_of=…)`、`render_verified`
- `backend/agent/service.py`：调用点用 `cast(date | None, saved_record.law_as_of)`（因 `models.py` 是 legacy `Column(Date)`）

数字（全部实测）：车道测试 **23 collected**（`test_r15_version_tripwire.py` + `test_r15_runner_injection.py` +
`_r15_tripwire_probe.py`）；全量 **1240/4-failed → 1266 passed / 0 failed @`aaf088b`**；
合并他人提交后重跑交接面（`test_r15_*` + `test_agent_verifier` + `test_phantom_check` + probe）= **93 passed @`105907b`**。
评测样本 `evals/watershed-cases-r15.json`：sha256 前缀 `7cc61193e7cd53ce`，`status: NOT_FROZEN`。

**留痕位置**：`docs/process-archive/superpowers/plans/2026-09-18-r15-law-version-tripwire.md`
（含 `## 审核记录（vet-plan-new 五问）` / `## 收口记录` / `## 对照臂真实读数` 三段，红测原因与 mutation 记录都在里面）。

### 3.2 对照臂三臂真实读数（Owner 指示"你来执行"后才花的钱）

| 臂 | 配置 | 读数 |
|---|---|---|
| A0 | 快车道（`AGENT_ENABLED=False`，**即线上现状**） | 给出**跨越分水岭的错误期间法条** |
| A | agent 路径，绊线关 | 同样给出错误期间法条 |
| B | agent 路径，绊线开（**仅运行期 env 注入**，代码默认未改） | `FAIL_SAFE` + reason `LAW_VERSION_WATERSHED_MISMATCH` |

副产品 4 条：① 快车道**没有版本判定**（→ 本文 T2）；② 日志不可归因（已修 `5afc8d0`）；
③ 案例 `fact_reveal` 关键词需调参；④ 观察到海事法院 / 商业银行法的**跨域语料污染**。
**别重付这三臂** —— 结论已在计划文档里，要复核只需读它。

### 3.3 git 修复：内容侧修完，携带侧另建，push 放弃（三项都是决定）

- 第二处洞**已修**：最旧 3 个提交缺的 blob `04463121`（`backend/agent/service.py`，26198 字节）。
  可复制的招（**390KB**，不是几百 MB）：
  `git clone --filter=blob:none --no-checkout --single-branch --branch master <origin> <temp>`
  → 按需 `git -C <temp> cat-file blob <oid>` → live 里 `git hash-object -w --stdin`
  → **重算哈希必须等于原 oid**（等则逐字节复原）。**绝不在 live 做浅 fetch**（会留 `.git/shallow`）。
  效果：3 个提交 `git archive` rc **255 → 0**，28/28 提交现在全部可读。
- **完整备份已建并验证**：`Desktop/fazhi-rescue-4465080-20260919/`（`repo.git` + `fazhi-master-4465080.bundle` 130MB + README）
  - **28/28 提交 tree 哈希逐一对应全等**、tip tree = live = `edd112bd5ff353cb228f2b3ef3aee03ce16fbccd`、
    `author|email|date|subject` diff 为空、`git ls-files` = 2153 = live
  - `bundle verify` 报 "records a complete history"、**从 bundle 克隆 rc=0、克隆内全量 `git fsck` 零输出**
  - ⚠️ 旧的 23 提交版 `Desktop/fazhi-rescue-20260919/` **已被我删除**，别去找它
  - 刷新很便宜：`git fast-export master | git fast-import` ≈ 1 分钟。live 有新提交就重跑，别攒
- **明确没做的三件**：重写 master、force push、`git gc`（理由见 §2 红线表）。

### 3.4 我顺手排掉/处置的风险（别重复调查）

- `dispatch-output/agent-mainline-fix-20260911/verify.ps1` 与 `agent-timeout-h1-20260912/verify-h1.sh`
  硬编码 4 个凭据字样 —— 判为**合成占位值**（三家厂商共用同一 27 字节值、22 字母 + 5 短横、**0 位数字**、含 `test`/`ci-`），
  且这两份文件在**公开远端 tip 里早已存在且字节相同** ⇒ 非新增暴露面。**但它是地雷**（模板下一步可能被人填真值）。
- 受跟踪文件里真形态密钥 `sk-[A-Za-z0-9]{20,}` 命中 **0**（实测 `git grep`）。
- `diag/` 里有 **894 个受跟踪文件、306.6 MB** chroma 索引二进制（`git ls-tree -r -l` 汇总）—— 推送/克隆前先想到体积。
- 含真密钥的那份红测日志已**整文件移动**到 `.workbuddy/evidence/r15-tripwire-t2-red.txt`（未改写、未删除）。

---

## 4. 你要接手的全部任务

### T1 现场维护（低风险、零对外，可立即做）

| 子项 | 目标 | 完成判据（必须回报实测） |
|---|---|---|
| T1-a | 刷新救援仓库到**当时** tip | 新目录 bundle verify rc=0 + 从 bundle 克隆 rc=0 + 克隆内 `git fsck` 零输出 + tree 逐一对应全等 |
| T1-b | 清理本会话遗留：`.git/objects/pack/tmp_pack_lu4Uc1`（44MB，我那次被杀的 fetch 留的） | 先确认无 git 进程持有（`ls -l --time-style=full-iso` 看 mtime 是否静止 >30 分钟），只删**这一个精确文件名** |
| T1-c | 用 `-r` **重跑一次未跟踪留痕的密钥扫描**（我的原始扫描没加 `-r`，"命中 1 个"是**下界**） | 输出命中文件名 + 形状特征（**只报形状/长度/是否含数字，禁止把值打印到任何文件或终端**） |
| 雷 | T1-b **只删自己名字的东西**；`.ptmp-*` 里 `s4` / `syv` 前缀是别人的，**别动**（实测当前它们没让白名单测试变红，2 passed） |

### T2 快车道版本判定缺口（价值最高，需要 Owner 给一次"允许真实模型调用"）

**问题**：绊线只挂在 agent 路径；`AGENT_ENABLED=False` 时线上流量 100% 走快车道，那里**没有任何版本判定**
（对照臂 A0 实测直接把错误期间法条放出去了）。

**我已量到的有利事实**：基准日**早就在请求对象上了** —— `backend/request_bootstrap.py :: RequestBootstrap.law_as_of`
（默认 `None`，注释写明"缺省 None = `create_run` 落 `date.today()`，行为逐字不变"；构造点在同文件
`law_as_of=law_as_of`）。⇒ 快车道取到基准日的管道成本接近零。

**你需要决策的设计点（我没有替你做，因为它是产品判断）**：快车道**没有** agent 那样结构化的 `claim` 列表，
所以 `law_version_crosses_watershed(claim_text, fact_texts, law_as_of)` **不能逐字照搬**。两条路：
- 方案 P（pre）：在检索侧判 ——  retrieved 文档的适用版本 vs `law_as_of` 是否分跨分水岭。
  注意现状：知识库检索本身是"按 `law_as_of` 做 cutoff 捞的，**必然只捞得到分水岭后的法**"（这句是
  `limitation_calc.py` 里我自己写的注释所描述的现实），所以 P 可能测不到病。
- 方案 Q（post）：对**生成的答案文本**跑判定 —— 更接近 agent 路径的语义（判的是"回答主张的版本"），
  代价是要在流式出口做收口，且快车道答案没有 claim 粒度，误伤面比 agent 大。
- 建议先按 Q 做**最小可用**：新增默认关开关（沿用 `*_check: bool = False` 命名法），
  只在 `clean_answer` 之后、落库之前判，命中就按快车道的降级口径处理，**不改** agent 路径任何行为。
- 入口锚点：`backend/main.py :: fallback_to_fast_path`、两处 `if not settings.agent_enabled:`；
  链路组装在 `backend/rag_chain.py :: format_docs / make_chain / clean_answer`。

**票面要求（B1–B9 口径）**：新判定函数要 TDD（先红后绿，红测原因写进留痕）；mutation 至少 2 处（把门摘掉必须变绿→红）；
对照样本复用 `evals/watershed-cases-r15.json`（**别放进冻结集**）；`AGENT_ENABLED=False` 与 `=True` 两态都要跑；
全量门禁 + 交接面重跑，且**在合并后的 HEAD 上**再跑一次。

### T3 `.gitignore` 加**根目录留痕**规则（一行，但规则形状必须写对）

目的：堵住 §1-5 那条"`git add -A` 就把含密钥的留痕提交上去"的路径。

**规则要写成 `/_*`。** 下面三种写法我在隔离的 scratch 仓库里实测过语义（不是查文档，是跑 `check-ignore`）：

| 写法 | 根 `_probe.txt` | 根 `_r15log.txt` | `backend/tests/_r15_tripwire_probe.py` | `sub_x/_inner.txt` |
|---|---|---|---|---|
| `/_*` | 忽略 | 忽略 | **可见** ✅ | 可见 ✅ |
| `/_*.txt` | 忽略 | 忽略 | 可见 | 可见 |
| `_*` | 忽略 | 忽略 | **被忽略** ❌ | 被忽略 ❌ |

`_*`（无前导斜杠）在 gitignore 里匹配**任意层级**，实测会命中 **9 个已跟踪文件**：
`backend/agent/__init__.py`、`backend/tests/__init__.py`、`backend/tests/_r15_tripwire_probe.py`、
`backend/tests/_fake_embeddings.py`、`backend/tests/_r12_issue_scope_probe.py`、`backend/scripts/_client.py`、
`backend/scripts/_judge.py`、`backend/tools/__init__.py`、`dispatch-output/over2-replay-20260919/_over2_tripwire.py`。
（已跟踪文件不会被 ignore 真正改变行为，但这些探针将来一旦被 `git rm --cached` 就会静默消失 —— 规则意图不该覆盖它们。）
而仓库根**没有任何已跟踪的 `_*` 文件**（实测 `git ls-files "_*"` 为空），所以 `/_*` 不伤存量。

判据（两条都要过）：`git check-ignore -q _probe.txt` → **rc=0**；
`git check-ignore -q backend/tests/_r15_tripwire_probe.py` → **rc=1**。
⚠️ 附加雷点：这条规则会让**别人的未跟踪留痕从 `git status` 视野里消失**（根目录 97 个条目），动手前点名、动完复测。

### T4 顺带可做的两件小票（不阻塞，别扩大）

- `docs/evaluation-harness-*` 里被我的正则误报为 `sk-` 命中的地方（实为文件名 `docs/ta**skbook**-…` 撞规则）——
  若将来做扫描工具，正则要加边界。**（已实测为假警，不用改文档）**
- 计划文档 §收口记录 里"8 条限制"中第 8 条（含密钥日志）状态已变（文件已移到 `.workbuddy/evidence/`），
  可就地更新一句。**注意 `docs/` 会被并行会话同时改，Edit 前看 mtime。**

### 留在 Owner 手上，**不要接手**

| # | 事项 | 为什么不能交给你 |
|---|---|---|
| A1 | 把 bundle 拷到**另一块物理介质** | 需要插盘子的物理动作 |
| A2 | 任何推远端 | origin 当前公开可读；要先由 Owner 确认目标仓 `visibility=private` |
| A4 | 是否**销毁** `.workbuddy/evidence/r15-tripwire-t2-red.txt` | 它是我不可再生的红测证据，删除不可逆 |
| A5/A6 | 承认 09-17 历史分界；三条未跟踪 `docs/` 订正是否入快照 | 判断性决定 |
| C 类 | `calc_limitation` 零调用方、`CHROMA_DIR` 被 6 个运维脚本忽略（**另一会话在做**，见 `fe40b0c`/`105907b`）、`docs/code-review-standard.md` 文档漂移 | 撞车道或需先做全仓引用面确认 |

---

## 5. 回报格式（Owner 明确要"分级置信 + 可复核"）

每条任务交付时给四样，缺一不可：
1. **命令原文 + 退出码**（退出码必须单独取，不能在 `| head` 之后）
2. **数字**（测试条数 / rc / tree 哈希 / 字节数），并标 **实测 / 复算 / 推断**
3. **红测留痕路径**（新增或改动的判定逻辑，必须先见过它红）
4. **不属于本会话的文件清单**（并行环境下，说清哪些改动不是你做的）

不允许的说法：**"已过 pre-commit"**（除非你贴出手跑 rc=0）、**"当前 HEAD 全绿"**（除非你在合并后的 HEAD 上重跑过全量）、
**"push 失败了应该是网络问题"**（§1-1：它必然失败，与网络无关）。

---

## 6. 本文引用点的复核位置

- 我的进度/待办报告：`docs/process-archive/session-report-r15-and-git-repair-20260919.md`（207 行，§5 待办分四级）
- 全过程逐时留痕：`.workbuddy/memory/2026-09-19.md`（诊断 → graft → fetch 失败 → blobless 回填 → 救援换代 → 风险评估）
- R15 计划与审核记录：`docs/process-archive/superpowers/plans/2026-09-18-r15-law-version-tripwire.md`
- 项目记忆（**先读这两条再动手**）：
  `~/.qoder-cn/projects/c--Users-33393-Desktop-ai-legal-helper/memory/project-precommit-and-concurrent-sessions.md`（条目 k 是 git 洞全程）、
  同目录 `shell-and-encoding-verification-traps.md`（取证陷阱）、`r15-version-tripwire-state.md`
- 我留下的扫描脚本（可复用，只报形状不报值）：仓库根 `_push_risk_scan.py`、`_push_risk_probe2.py`、`_push_risk_shape.py`

## 7. 本文档自身的限制

1. §3.2 的三臂每臂样本量 = 1，趋势够、统计不够。
2. "1266 passed / 0 failed" 属 `aaf088b` 时刻；**当前 tip 未重跑全量**，接手后需自取。
3. 救援仓库 SHA 与 live **永久不一致**（父链重建），跨仓库对照只能用 subject/日期。
4. §1-1 的"永久缺失"限定在当前可获取的对象集合内：若将来出现另一台机器上有 09-17 之前的完整 clone，
   `0263bd5` 仍可能被带回，届时 §2-R1 的判断要重估。
5. 本会话对未跟踪留痕的密钥扫描**未覆盖目录内部**（见 T1-c）。
