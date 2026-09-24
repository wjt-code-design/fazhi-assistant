# 工作进度汇报：对 `handoff-auth-review-followup-20260923.md` 的完成度对照

生成时间：2026-09-24 03:25；末次更新 04:0x（回收评审结论、补第 8 节、按第 8 节回改第 2 节表述）
票源：[`docs/handoff-auth-review-followup-20260923.md`](./handoff-auth-review-followup-20260923.md)
接手会话：本会话（第 3 代接手；前两代为 Codex 线程 `01a0a9c7…` 与 09-23 会话）
本票代码终态：`974e3da`（其父 `065038c`，再父 `b7d96f5`）；本文与两处勘误另随其后一笔 `docs:` 提交入库
（刻意不写死该 SHA：写进自己的提交里不可能成立，而引用会随下一笔提交作废）
一句话结论：**票面四项缺口 + 六步执行顺序全部收口；独立评审另查出 1 个真缺陷（出口基准日各算各的，已修）与 2 条过宽陈述（已勘误），并暴露 2 个未闭出口（`/api/feedback` 沉淀入口、`/api/law` 系回查端点）；本票共 5 笔提交（2 笔代码 + 3 笔文档，见第 4 节），未 push、未部署；三项待 Owner 决策。**

> 本文只报"完成度对照 + 证据口径 + 残余"。实现细节与判据推理仍以
> [`docs/code-review-report-02e3851-20260918.md`](./code-review-report-02e3851-20260918.md)
> 的「2026-09-23 当前快照复核」节为唯一真源，本文不复制其内容，只指过去。

**给审核人的三句话（本文性质，先读这段再看表）**

1. **这是执行者本人的自述**，其中每一条"✅"都附了产生它的命令或仪器；凡我自己没实测的表述都写在
   第 6 节"残余限制"或第 8 节里，不在"已完成"栏。
2. **第三方复核是另一名 AI 评审 agent 做的**（第 8 节），不是人类签认；但它抓出的三条**我逐条自己重跑
   取证后才采信**，且其中一条导致代码修复（`974e3da`）——所以本轮的"已收口"含一次真实的返工，不是一次自证。
3. **最容易被误读的一点**：第 2 节"缺口 4"那行的沉淀闸**只闭了一条入口**，第 3 节里"降级沿用 run 日期"
   这句**在修复前只成立到 bootstrap**。两处都已在原位标注并指向第 8 节；审核判据请看第 6 节第 8–9 条，
   不要只看打勾栏。

---

## 1. 票面「下一步执行顺序」六步对照

| # | 票面要求 | 状态 | 证据（本次实测，非引用旧输出） |
|---|---|---|---|
| 1 | 看 12 个目标文件的 `git diff` 确认无误伤 | ✅ 补全 | 上一代会话只读完自己改的部分；本轮逐个读完前序会话的 `schemas.py`（纯注释）、`_sse_harness.py`、`test_fast_path_law_version_gate.py`、`test_stream_exit_law_version_gate.py`、`test_r1ob.py`。结论与判因写在报告内。其中两条控制腿把 `law_as_of=AS_OF_2026 → None` 判为**正确适配**（显式日期现在结构上不可能写缓存） |
| 2 | 解决考试/合同/Agent 恢复的日期语义，**每个修正先有能在旧行为下失败的测试** | ✅ 超额 | 见第 2 节。另修了票面**未列出**的第五个失效点（`backend/tools/contract.py`） |
| 3 | 同步至隔离容器重跑定向+宽套件，记完整退出码/通过/跳过/失败/警告 | ✅ | 22 个文件宿主↔容器 md5 逐字节一致后跑。修复前（`065038c` 的字节）：定向 **235 passed / 10 skipped / exit 0**、全量 **1407 / 12 / 25 / exit 1**；评审修复后（`974e3da` 的字节）：定向 **237 passed / 10 skipped / 59 warnings / exit 0**（45.78s）、全量 **1409 passed / 12 failed / 25 skipped / exit 1**（86.54s，同 12 项缺件）。退出码用 `> file 2>&1; echo $?` 取——`… \| tail` 会报出**假的 exit 0**，本会话踩过两次并纠正 |
| 4 | 合适的静态检查 + `git diff --check`，失败先分析、同命令最多原样重试一次 | ✅ | `ruff check .` 通过；`mypy .` **Success: no issues found in 73 source files**；`git diff --cached --check` 仅 2 处告警，均为交接文档里**故意的 markdown 行尾双空格**（硬换行），未静默删。`ruff format --check` 见第 5 节的行尾成因说明 |
| 5 | 更新审查报告里 AUTH-2/AUTH-3 结论，区分"本地实现/测试证据"与"尚未部署"，记录未覆盖路径 | ✅ | 报告已改写；并对我自己先前写下的**不实陈述**（"AUTH-2 有 AST 哨兵"）做了显式勘误 |
| 6 | 向用户报告变更/证据/残余/未部署，等用户选服务器后再谈部署 | ✅ | 已回报。**部署四项禁令（部署/迁移/发布/重启线上/写服务器配置/选服务器）全程未碰** |

## 2. 票面「四项正确性缺口」对照

失效模式：把 `cutoff` 只用在末尾过滤 ⇒ 历史有效条文在**召回阶段**就没捞到 ⇒ **静默丢证据**；修法是把 `cutoff` 一路传进取数层。
⚠️ **但这句只描述"上一轮已给 `retrieve` 传日期 + 加末尾过滤"的那个未提交中间态。** 已提交的父提交
`b7d96f5` 上快车道**连末尾过滤都没有**（`main.py` 里 `is_valid_by_time` 0 次、`retrieve` 的 `cutoff` 形参
在调用点没被传）⇒ 那上面的失效模式是**答错版**，比"静默丢证据"更重。见第 8 节①。

| 缺口 | 收口位置 | 红测证据 |
|---|---|---|
| 1 考试检索分支不带 cutoff | `retrieval.retrieve_exam` 四处 `hybrid_retrieve`（含线程池内与两条 fallback）、`scenario_supplement_docs` 两处查条 | `tests/test_historical_law_cutoff_threading.py` 实现前 **7 failed / 1 passed**（唯一绿的是"不传 cutoff 保持旧形状"对照组），实现后 8 passed |
| 2 合同 cutoff 与 `blocks` 数据流 | `domain_rules.build_contract_data(cutoff=)` → `contract_supplement_docs`，使 `blocks[*].articles` 与 `docs` **同源构建**（事后重过滤改不到 `blocks`，而 `_contract_messages` 读的正是 `blocks`）；合同 messages 注入基准日标注 | 分支用例红在 `blocks` 读到当日版本 |
| 3 Agent 恢复分支静默丢弃日期 | `create_run` 建立时固定 `law_as_of`；恢复请求带不同日期 ⇒ **CAS 之前** 409（`ResumeLawAsOfConflict`）；技术性失败降级沿用 `run.law_as_of`；`_resume_bootstrap` 日期形参**不给默认值**（堵 fail-open） | `tests/test_agent_resume.py` 新增 5 项实现前 4 failed，含一条端到端接线用例（stub 三处下游 + 599 哨兵中断） ⚠️ **本行第三轮修正**：本笔 `065038c` 里"降级沿用 run 日期"**只成立到 bootstrap**，四个出口仍按 body 重算 ⇒ 已由 `974e3da` 修复（`_exit_law_as_of`）；且当时那条"端到端接线用例"断言不到出口实参，见第 8 节③④。 |
| 4 其余生成/缓存出口 | 历史请求不进共享答案缓存与近重复缓存（`_cacheable`）、不直返 QA 语料（`prepare_fast_path` 置 `qa_hit=None`）、**不进受控沉淀待审**（`_post` 闸；`qa_pairs` 无版本轴）；两条 messages 组装路径共用同一句标注（`_law_version_scope_note`）；检索缓存键含 `cutoff`（`hybrid_retrieve` 结果缓存 key 组分，实测非推断） | 沉淀闸新用例实现前红在 `created` 多出一条（确实漏沉淀） ⚠️ **本行第三轮修正**：`_post` 那条沉淀闸只闭了一条入口，`/api/feedback` 是第二条平行入口且未闭（需 schema 改动）；另有 `/api/law`、`/api/law/search` 恒按当日。详见第 6 节第 8–9 条与第 8 节②⑥。 |
| （票面未列）Agent 工具链合同口 | `tools/contract.py::_build_contract_data` 同样漏传 cutoff——与缺口 1/2 同一失效模式 | 2 项用例（工具层 + 适配器转发层），双向验证 |

## 3. 用户已确认的产品边界对照

| 边界 | 实现 | 证据 |
|---|---|---|
| `law_as_of` 是公开历史查询条件，非管理员专属，不绕过证据有效性校验 | `allow_client_law_as_of: bool = True`；历史日期只改变取数口径，`is_valid_by_time` 仍是唯一判定 | 定向套件全绿 |
| 部署显式关闭时：**503 + 可理解提示**，不得静默改用当日 | `main._client_law_as_of` 为唯一闸口 | `test_client_law_as_of_gate.py`；并补了与 `case_domain` 对等的**扫源守卫**（正则扫 `body.law_as_of` 只准出现在该函数内），该守卫做过变异验证 |
| 最小结构化审计：只记用户/会话/所选日期，**不记原始问题** | `historical_law_query` 字段仅 `user_id`/`conv_id`/`law_as_of` | `test_agent_gate.py` 逐字段钉死形状 |
| `case_domain` 不为本任务重复改动或放宽 | 该文件与 `test_client_case_domain_gate.py` 均**不在改动集内** | `git show --stat 065038c` 无相关路径 |
| AUTH-3：日志不落原文 | `dept_filter_removed` 改记 `query_sha256` + `query_len` + 域与剔除数，字段白名单同步 | 用变异把"代码没写"与"formatter 挡住"**两层归因分开**，各配一条可归因断言 |

## 4. 提交记录

### `065038c` `fix(AUTH-2/AUTH-3): 历史基准日贯穿全部取数口与出口，日志不落问句原文`

- 24 文件（**22 改 + 2 新增**：`tests/test_historical_law_cutoff_threading.py`、本交接文档），1351 insertions / 175 deletions
- 父提交 `b7d96f5` 未变 ⇒ **无历史改写**；未 push、未部署
- ⚠️ 该提交**信息里有一句过宽陈述**（"其余分支按当日捞、末尾再过滤"描述的是上一轮未提交的中间态），
  提交信息不可改写（`065038c` 已被引用），以第 8 节①与报告勘误为准。

### `974e3da` `fix(AUTH-2 三轮评审): 生成/缓存出口的基准日统一取本次取数所用日期`

- 3 文件：`backend/main.py`（+`_exit_law_as_of`、四出口改统一取数）、
  `tests/test_client_law_as_of_gate.py`（2 条新用例）、`tests/test_r1ob.py`（删我写重复的死码断言）
- 来源：第 8 节③那条真缺陷。红→绿与变异证据见该节

### 其余 3 笔（文档，无代码影响）

`93b1ebd` 报告勘误 + 交接横幅 + 本文首次入库 → `afd4fa4` 本文 SHA 表述改为不自指 → `0e48b6c` 本文第 2 节
两处就地标注修正。**核对代码请用 `065038c` 与 `974e3da` 两笔；`b7d96f5..HEAD` 的净代码差异即这两笔之和。**

### 提交前安全前置（5 笔每笔都做在 `git commit` 之前）

无 git 进程 / 无 `.lock` / 无进行中 rebase·merge；按名暂存后用 `comm -3` 证明**暂存集 == 意图集**；
禁提路径（`.env`/`chroma_db`/`*.db`/用户数据/`outputs/`）零命中；**扫密按值反查**（全树 45 个 `.env*`、
189 条非平凡值比对暂存 diff，零命中；AKIA / sk- / JWT / PRIVATE KEY / URL 内嵌密码五类形状零命中）；
命令写作 **`git -c gc.auto=0 commit`**，把"提交顺手 gc → prune 掉按裁定保留的 268 颗 dangling"
从"看默认值估计没事"变成**确定不发生**。

### 提交后体检（全部实测量出）

`git fsck --full --no-dangling` **rc=0 且零输出**；`git fsck --full` rc=0、dangling 仍 **268**（未增 ⇒ 无新孤儿）；
loose 314→340、packs 仍 2；`.git/objects` 无新建 `tmp_*`；索引无残留他人 staged 项；
22 个 backend 文件的 **HEAD blob 与容器实跑字节同内容**（仅差 `\r`），并在 HEAD 上复现定向套件。

## 5. 顺带查出来的环境与仓库事实（会影响下一代判断）

1. **两条储存的仓库健康结论已被实测推翻**：`git rev-list --count HEAD` = **114 / rc=0**（旧记录为"仅 16 个提交可连读、之后断链"）；`.git/objects` 的 `tmp_*` 从 09-20 的 15 条 / 648 MB 变为 **0 条 / 0 字节**。E3 重建对象库 + 那次 owner 批准的 `gc` 把两件事一起解决了。**但"洞没了"不等于"能推了"——push 能力本轮未测。**
2. **`.git/hooks` 只有 Qoder 的 `post-commit`/`post-checkout` 只读埋点**（两条都以 `|| true` 收尾、stderr 丢弃）⇒ 不会改索引、不会让提交失败；**没有 pre-commit** ⇒ ruff / 尾空格 / EOF 三项必须手跑。
3. **提交前 `HEAD` reflog 原本不存在**（`.git/logs/HEAD` 缺失 = 没有 reflog 这层兜底网）；`core.logAllRefUpdates=true` 使它在这次提交时自动重建。外部锚点在 `D:\ai-legal-helper-bundles\2026-09-23\`（3 份 bundle + 多份 `.git` 备份）。
4. **`ruff format --check` 的 9 项告警是行尾混排不是格式问题**：`core.autocrlf=true` 且**无 `.gitattributes`** ⇒ 编辑工具以 LF 追加补丁到 CRLF 文件上。本改动集 3 个文件仅统一行尾即 `already formatted`，且 `git hash-object --path --filters -w` 前后 **blob 哈希逐字节相同**（零内容差异、无整文件噪声）。另有 6 个**本改动集未触及**的文件同因待重排，按"不批量清理他人改动"保留并如实标注。
5. **`tests/test_agent_gate.py::test_logging_failure_is_counted_and_fails_open` 此前是顺序依赖的假绿**：`observability.setup_logging` 把 `legal.chat` 的 `propagate` 设为 False，凡先跑过完整请求链路的用例都会让 `caplog` 收不到。已改为直挂 handler，两种执行顺序都验过。

## 6. 残余限制（不当作已完成）

1. 全量 12 项失败 = 镜像缺件（`data/sample_laws`、`/release-evidence`、`/docs/gate-exit-registry.md` 未进镜像；`test_chroma_isolation` 断言临时库不在仓库根下而容器根布局不同）。归因依据是报错本身；**没有**"同批用例在改动前代码上同样失败"的对照跑——开新容器超出授权边界。
2. **`_resume_law_as_of` 是有损代理**：`run.law_as_of == date.today()` 时折叠成"未指定"。**跨零点行为未测**。
3. **恢复路径不产生 `historical_law_query` 审计**（只在 run 建立时记一次）。
4. AUTH-3 用**未加密钥的 SHA-256**：只解决"日志静止态含个人信息"，**不等于匿名化**——确定可关联，短/低熵问句可被成员判定。升级触发条件已写在报告里（日志读者扩到运维以外 ⇒ 换服务端密钥 HMAC）。
5. **成本口子未加限额**：显式基准日会退出零 token 直返与共享缓存 ⇒ 客户端可把一个日期把命中打成未命中（有界：单请求、60/分钟、最贵等于一次未命中），但调用者从评测通道变成**任意已认证用户**。`settings.py` 已把该耦合写进注释。
6. `docs`（答案）与 `contract_data["docs"]` 的潜在分叉：本轮靠同源构建规避，未从结构上消除。
7. 未 push、未部署。AgentRun/消息/上传/导出下载与评测参数的**双用户端点全矩阵探针**本轮未做（见报告"动态覆盖"段）。
8. **【评审新增】`/api/feedback` 是第二条沉淀入口，未加日期闸**：历史答案可经"点踩/纠错"进待审，采纳后落入无版本轴的 `qa_pairs`。闭它需服务端知道"这条答案当时用的基准日"，而 `FeedbackIn` 无该字段、`Message` 无该列 ⇒ 需要 schema 改动，另开票（第 8 节②）。
9. **【评审新增】`/api/law` 与 `/api/law/search` 恒按当日** ⇒ 历史查询引用的条号在这两个回查端点 404；Agent 路径已有快照回查分支，两条出口契约不对等（第 8 节⑥）。
10. **【评审纠正的基线认知】** 上一节第 1–5 条里凡说"表现为静默丢证据而非答错版"的框架，只适用于**上一轮未提交的中间态**；已提交的父提交 `b7d96f5` 上快车道**完全没有**日期过滤，即"答错版"风险当时并未被部分缓解。本改动集修的就是这个状态（第 8 节①）。

## 7. 待办

| 项 | 谁定 | 说明 |
|---|---|---|
| ~~独立评审结论回收 + 必要的 fix 提交~~ | ✅ 已完成 | 结论进第 8 节；真缺陷修复 = `974e3da`；两条过宽陈述已勘误 |
| **`/api/feedback` 沉淀第二入口是否闭（建议闭）** | Owner | 推荐：给 `messages` 加一个可空 `law_as_of` 列，落答案时写入、反馈时读它（≈小 diff，但属 **schema 改动**，越出本票"不改数据模型"边界）。备选：`feedback:` 来源候选不得成为可直返语料（改产品语义）／接受并标注 |
| **`/api/law`、`/api/law/search` 是否接基准日** | Owner | 要给两个 GET 加可选 `law_as_of` 并复用同一个 503 闸口 ⇒ **新公开 API 面**，需认可口径 |
| 两份文档的 SHA 标注 + 本报告入库 | ✅ 已入库 | `docs:` 提交，含报告勘误/交接横幅/本文 |
| `docs/superpowers/plans/2026-09-22-git-repair-execution-runbook.md` 是否入库 | Owner | 本轮安全判断的依据（dangling 保留裁定、三份回滚锚点）全引它，而它**至今未跟踪** ⇒ 一次 `git checkout -- .` / `git clean` 就没了。不属于本改动集，未擅自 add |
| `law_as_of` 缓存击穿是否加限额 | Owner | 见第 6 节第 5 条 |
| 部署 | Owner | 服务器未选定，票面禁令仍生效 |
| `backend/.ptmp-s4-run2/` 处置 | 本会话待核 | 前序会话遗留的 pytest basetemp 残留（`test_log_field_whitelist.py` 递归扫 `backend/` 会吃到自己的哨兵）。归属未确认前不删 |

## 8. 独立评审结论（已回收）

评审方式：派一名**无本对话上下文**的 agent 复查已提交的 `065038c`（`git show 065038c`），
要求每条结论带 `文件:行号` 且能证伪。它跑的是宿主 `backend/venv` 的只读命令，与我共用同一棵树。
下表每行都由**我自己重跑一遍取证**后才采信——未复核的第三方结论不进本报告。

| # | 指控 | 我的复核结果 | 处置 |
|---|---|---|---|
| ① | 提交信息"此前只有 `retrieve` 一条通道带 cutoff，其余分支按当日捞、**末尾再过滤**"描述的不是父提交 | **成立**。`git show b7d96f5` 实测：`retrieve` 有 `cutoff` 形参（`b7d96f5` 版 `retrieval.py:965`）但调用点不传（`b7d96f5` 版 `request_bootstrap.py:462`：`docs = deps.retrieve(rewritten, k=10)`）；`main.py` 里 `is_valid_by_time` **0 次**；`retrieve_exam`/`scenario_supplement_docs`/`cheating_docs`/`consumer_*_docs`/`build_contract_data` 连形参都没有 ⇒ 那句话描述的是上一轮**未提交的中间态**。真实已提交基线更糟：快车道拿到的是纯现行法证据集且无任何日期过滤 | 报告内加**勘误**（提交信息不可改写，`065038c` 已被引用，以报告为准）；措辞从"静默丢证据"改回"答错版风险未被部分缓解" |
| ② | "不进受控沉淀待审"只闭了 `_post` 一条入口 | **成立**。`/api/feedback` 端点里另有一条 `ks.create_candidate(db, body.question, propose, 0.0, f"feedback:{body.rating}")` 无日期闸；采纳时 `knowledge_service.add_qa_pair()` 不写 `law_as_of_basis`，而 `main._qa_direct_return` 的 docstring 明写"语料若没有该字段⇒**不拦**"、判定式是 `if law_as_of is not None and basis_raw:`（basis 为空即跳过）⇒ 同一条理由成立、口子未闭 | **本轮不修**（不是遗漏，是缺服务端真源：`FeedbackIn` 无基准日字段、`Message` 模型无该列 ⇒ 只能信客户端自报）。三个候选处置写进报告，建议"给 `messages` 加可空 `law_as_of` 列"另开票（schema 改动越出本票授权）。**否决**"采纳日当 basis"这个看似省事的写法：它标错答案的实际基准，且恰好放过最需要防的方向（旧版答案→现行查询） |
| ③ | "技术性失败降级沿用 `run.law_as_of`"只到 bootstrap，四个出口各算各的 | **成立**。`chat()` 里四处调用点各写 `_fast_path_law_as_of(body)`——QA 直返、`_light_buffered`、`_law_version_gate` 的两条答案来源（`grep -n "_exit_law_as_of(pre, body)" backend/main.py` 现在一次全出这四行）⇒ 降级路径上日期在 run 上、body 没有 ⇒ 重算得**今日**，而 `pre["law_as_of"]` 是历史日 ⇒ 版本绊线用现行法判历史证据、日志记错。QA 直返那处因 `qa_hit=None` 提前返回（同形不同害）；两开关默认 False ⇒ **潜伏**非现网 | **已修**：新增 `main._exit_law_as_of(pre, body)`（pre 优先、缺省回落 body ⇒ 默认路径逐字不变），四个出口统一走它 → `974e3da`。红→绿 + 两次变异各自只打死对应断言，`main.py` 还原后 md5 一致 |
| ④ | 我那条"端到端接线用例"判据只断言到被捕获的 bootstrap，看不到出口实参 | **成立**。锚点是 `tests/test_agent_resume.py::test_agent_fallback_on_resume_feeds_run_date_into_fast_path`——它把下游 `fallback_to_fast_path` 换成记录器、断言停在 `bootstrap.law_as_of == run_date`，看不到出口实参 ⇒ 是"接线断言没钉被比对象"的复发——它证明不了"出口沿用了 run 日期" | 牙齿换成：`_exit_law_as_of` 行为用例 + `_fast_path_law_as_of(body)` 只准出现在该函数内的**扫源守卫**；报告里显式纠正先前对该用例强度的说法 |
| ⑤ | `tests/test_r1ob.py` 里有两条**完全相同**的 `assert not hasattr(records[0], "query")`，第二条恒不可达（修复前两处位于 201/202 行）| **成立**，是我上一轮自己写的 sloppy；`pytest` 只报第一条断言，第二条即便写错也永远不会被看到 | 删重复那条，保留带归因说明的那条 |
| ⑥ | `/api/law`、`/api/law/search` 恒按当日 ⇒ 历史引用 404；Agent 路径却有快照回查分支 ⇒ 契约不对等 | **成立**（`@app.get("/api/law")` 与 `@app.get("/api/law/search")` 两端点内无任何 cutoff；对照 Agent 侧那一支带 `"is_snapshot": True` 的快照回查）。不属"生成/缓存出口"故先前陈述没覆盖，但落在交接票第 4 项"所有出口"射程内 | 记为**已知未收口项**并进 Owner 决策（补它要给两个 GET 加 `law_as_of` 并复用同一 503 闸口＝新公开 API 面） |
| ⑦ | 有无新增静默失败 | **无**：`cutoff` 单点赋值（`request_bootstrap.py:453`，当前 HEAD 已复核该行仍在）、末尾复筛与取数口同一谓词、缓存键含 `cutoff` | — |
| ⑧ | 八函数有无漏网调用方 | 生产调用点只有 `request_bootstrap.py:460-500` 与 `tools/contract.py:20`，均已带；`scripts/` 五处上下文无客户端日期，判定**不该带** | — |
| ⑨ | 陈述核对：唯一闸口 / CAS 前 409 / `blocks` 与 `docs` 同源 / 缓存与近重复被 `cache_key` 卡住 / `_resume_bootstrap` 无默认值 / 审计三字段 | **逐条核为真**，锚点给符号：`_client_law_as_of` 是 `main.py` 里 `body.law_as_of` 的唯一读点（`grep -n "body\.law_as_of"` 只有该函数体内两行）；`agent/controller.py` 的 `ResumeLawAsOfConflict` 抛出点在版本/状态校验之后、两处 CAS 写入之前；`domain_rules.build_contract_data` 里 `blocks` 与 `docs` 同源于一次 `contract_supplement_docs`，`main._contract_messages` 读 `blocks`；共享缓存与近重复的读写两侧都过 `_cacheable(pre)`（其内含 `not pre.get("law_as_of")`）；`_resume_bootstrap` 的 `law_as_of` 形参无默认值 | — |

> **代码锚点纪律**：本文一律给**符号**不给行号——本仓立过这条规矩（`ruff-format` 一次能挪 12 行），
> 而我第一版从评审 brief 里沿用了 6 处 `file:line` 没逐个复测，转发前实测已漂移（最多差 38 行）。
> 需要坐标时按符号现查：`grep -n "<符号名>" backend/main.py`。

**评审方的独立读数**（宿主 `backend/venv`，与我的容器读数并行且**不同仪器**）：15 文件定向套件
**243 passed / 2 skipped / exit 0**（总数 245 ＝ 我容器里的 235+10，差在 skip 归属，两边总数一致）；
`ruff check` rc=0；`mypy .` "Success: no issues found in 73 source files"。

**修复后重跑（`974e3da` 的字节，22 文件宿主↔容器 md5 一致后）**：定向 **237 passed / 10 skipped / 59 warnings /
exit 0**（45.78s）；全量 **1409 passed / 12 failed / 25 skipped / exit 1**（86.54s，仍是同 12 项镜像缺件，
无新增无消失）；`ruff check` 通过、`ruff format --check` 对改动文件通过、`mypy .` 73 文件零问题。

**一句结论**：三轮自评（双轴 code review + systematic debugging + show-your-work）都没抓到的那两条，
第三方视角抓到了——**一条真缺陷（③）+ 一条过宽陈述（②）**，且两次都是"我把中间态或未可观测的链路
当成了已证明的事实"。这两类的共同解药不是更仔细，是**判据必须落在被比对象上、且陈述的范围要有反例搜索**。

## 附录：复现命令

```bash
# 容器无 bind mount ⇒ 必须先逐文件 md5 对齐（宿主 backend/X → 容器 /app/X）
export MSYS_NO_PATHCONV=1                     # 否则 docker exec -w /app 报 "Cwd must be an absolute path"
cd C:/Users/33393/Desktop/ai-legal-helper
while read -r f; do
  h=$(md5sum "$f" | cut -c1-32)
  ch=$(docker exec codex-auth-review-test md5sum "/app/${f#backend/}" | cut -c1-32)
  [ "$h" = "$ch" ] || echo "DIFF $f"
done < <(git show --numstat --format= HEAD | awk '{print $3}' | grep '^backend/')

# 定向 + 全量（退出码必须走重定向，不能走 | tail）
docker exec codex-auth-review-test sh -c "cd /app && python -m pytest -q -p no:cacheprovider \
  tests/test_client_law_as_of_gate.py tests/test_client_case_domain_gate.py tests/test_request_bootstrap.py \
  tests/test_fast_path_law_version_gate.py tests/test_stream_exit_law_version_gate.py tests/test_r1ob.py \
  tests/test_log_field_whitelist.py tests/test_historical_law_cutoff_threading.py tests/test_agent_resume.py \
  tests/test_light_exit_gates.py tests/test_pre_rewrite_order.py tests/test_scenario_supplement.py \
  tests/test_domain_rules.py tests/test_tool_gateway.py tests/test_agent_gate.py \
  > /tmp/d.txt 2>&1; echo EXIT=\$?; tail -3 /tmp/d.txt"

docker exec codex-auth-review-test sh -c "cd /app && python -m pytest tests -q -p no:cacheprovider \
  --ignore=tests/test_gate2_runner.py --ignore=tests/test_gate5_judge_layers.py \
  --ignore=tests/test_harness_fact_reveal.py --ignore=tests/test_r15_runner_injection.py \
  > /tmp/f.txt 2>&1; echo EXIT=\$?; tail -16 /tmp/f.txt"
# 全量口径：上述 4 个 runner 在收集期即因镜像缺件报错，故排除；引用通过数时必须带上这句口径
```

### 审核人若没有这个容器（更省事的复现路径）

`codex-auth-review-test` 只存在于执行机。宿主 `backend/venv` 依赖齐全，可直接跑同一批用例：

```bash
cd C:/Users/33393/Desktop/ai-legal-helper/backend
venv/Scripts/python.exe -m pytest -q -p no:cacheprovider \
  tests/test_client_law_as_of_gate.py tests/test_client_case_domain_gate.py tests/test_request_bootstrap.py \
  tests/test_fast_path_law_version_gate.py tests/test_stream_exit_law_version_gate.py tests/test_r1ob.py \
  tests/test_log_field_whitelist.py tests/test_historical_law_cutoff_threading.py tests/test_agent_resume.py \
  tests/test_light_exit_gates.py tests/test_pre_rewrite_order.py tests/test_scenario_supplement.py \
  tests/test_domain_rules.py tests/test_tool_gateway.py tests/test_agent_gate.py
venv/Scripts/ruff.exe check . && venv/Scripts/mypy.exe .
```

宿主与容器读数**不同**是预期的：同一 15 文件集宿主实测 **243 passed / 2 skipped**、容器 **235 passed /
10 skipped**，总数都是 **245**——差异全在 skip 归属（宿主有齐依赖故少跳 8 条），不是通过数口径不同。
**要复现"1409 / 12 / 25"那个全量数就必须用容器**：宿主全量会额外吃到本机 `.env`、`app.db`、`chroma_db`
三条真实写入面。这条边界不是我本轮新立的，写在
[`handoff-gap-tickets-h-i-j-20260920.md:51`](./handoff-gap-tickets-h-i-j-20260920.md)
——「live 工作树跑全量 = 禁止（副本树内允许）」。
