# 工作进度汇报：对 `handoff-auth-review-followup-20260923.md` 的完成度对照

生成时间：2026-09-24 03:25；末次更新见文末「第 10 节」的落款（本文不再在头部写"末次更新 04:0x"——
那个占位无法核实，正是第 9 节⑪同一族的毛病：写了个自己不认得的坐标）
票源：[`docs/process-archive/handoff-auth-review-followup-20260923.md`](./handoff-auth-review-followup-20260923.md)
接手会话：本会话（第 3 代接手；前两代为 Codex 线程 `01a0a9c7…` 与 09-23 会话）
本票代码终态：`974e3da`（其父 `065038c`，再父 `b7d96f5`）；本文与两处勘误另随其后一笔 `docs:` 提交入库
（刻意不写死该 SHA：写进自己的提交里不可能成立，而引用会随下一笔提交作废）
一句话结论：**票面四项缺口 + 六步执行顺序全部收口；独立评审另查出 1 个真缺陷（出口基准日各算各的，已修）与 2 条过宽陈述（已勘误），并暴露 2 个未闭出口（`/api/feedback` 沉淀入口、`/api/law` 系回查端点）；本票**代码提交 2 笔**（`065038c` + `974e3da`），文档若干笔，未 push、未部署。**
两个未闭出口的处置**不在本节口径里**——第 7 节待办表列了几项待决，本节刻意不写"共几项待 Owner 决策"：
第四轮核对（第 10 节）之后那个数就已经变了，写死它只会让下一个人接到旧结论。

> 本文只报"完成度对照 + 证据口径 + 残余"。实现细节与判据推理仍以
> [`docs/process-archive/code-review-report-02e3851-20260918.md`](./code-review-report-02e3851-20260918.md)
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
| AUTH-3：日志不落原文 | `dept_filter_removed` 改记 `query_sha256` + `query_len` + 域与剔除数，字段白名单同步 | 用变异把"代码没写"与"formatter 挡住"**两层归因分开**，各配一条可归因断言 ⚠️ **第四轮核对补的范围限定**：本行只覆盖 `dept_filter_removed` **这一个字段**。全仓另有 4 处把用户问句原文或模型输出原文写进日志，本会话未处置、上一版陈述也未覆盖，读法见第 10 节④——其中 `agent/runtime.py` 的 `detail` 落的正是**用户问句原文**，与本行标题字面冲突。 |

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

### 其余各笔（文档，无代码影响）

`93b1ebd` 起均为文档修订（报告勘误、交接横幅、本文自身）。**刻意不写"共几笔"**——
记录这个数的那次提交本身会让它过期。核对代码只认 `065038c` 与 `974e3da`：
实测 `git diff --name-only b7d96f5 HEAD -- backend` 与这两笔的并集**完全相同（22 文件）**。

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

1. **两条储存的仓库健康结论已被实测推翻**：`git rev-list --count HEAD` 在**当时那笔提交上**已跑到三位数、
   rc=0（旧记录为"仅 16 个提交可连读、之后断链"——那条已被否证）。⚠️ 本文第一版在这里写死了具体数字，
   而**记录它的那笔提交本身会让它过期**：第四轮核对时同一命令的读数已经变了。按第 4 节自己立的规矩
   （"刻意不写会因记录而作废的计数"），此处只留"可连读且为三位数"这一不随提交漂移的性质，
   要确数请现跑 `git rev-list --count HEAD`。
   另一条：`.git/objects` 的 `tmp_*` 从 09-20 的 15 条 / 648 MB 变为 **0 条 / 0 字节**。E3 重建对象库 +
   那次 owner 批准的 `gc` 把两件事一起解决了。**但"洞没了"不等于"能推了"——push 能力本轮未测。**
2. **`.git/hooks` 只有 Qoder 的 `post-commit`/`post-checkout` 只读埋点**（两条都以 `|| true` 收尾、stderr 丢弃）⇒ 不会改索引、不会让提交失败；**没有 pre-commit** ⇒ ruff / 尾空格 / EOF 三项必须手跑。
3. **提交前 `HEAD` reflog 原本不存在**（`.git/logs/HEAD` 缺失 = 没有 reflog 这层兜底网）；`core.logAllRefUpdates=true` 使它在这次提交时自动重建。外部锚点在 `D:\ai-legal-helper-bundles\2026-09-23\`（3 份 bundle + 多份 `.git` 备份）。
4. **`ruff format --check` 的 9 项告警是行尾混排不是格式问题**：`core.autocrlf=true` 且**无 `.gitattributes`** ⇒ 编辑工具以 LF 追加补丁到 CRLF 文件上。本改动集 3 个文件仅统一行尾即 `already formatted`，且 `git hash-object --path --filters -w` 前后 **blob 哈希逐字节相同**（零内容差异、无整文件噪声）。另有 6 个**本改动集未触及**的文件同因待重排，按"不批量清理他人改动"保留并如实标注。
5. **`tests/test_agent_gate.py::test_logging_failure_is_counted_and_fails_open` 此前是顺序依赖的假绿**：`observability.setup_logging` 把 `legal.chat` 的 `propagate` 设为 False，凡先跑过完整请求链路的用例都会让 `caplog` 收不到。已改为直挂 handler，两种执行顺序都验过。

## 6. 残余限制（不当作已完成）

1. 全量 12 项失败 = **既有失败**（`data/sample_laws`、`/release-evidence`、`/docs/gate-exit-registry.md` 未进镜像；`test_chroma_isolation` 断言临时库不在仓库根下而容器根布局不同）。
   判据不是"看报错像环境问题"，而是第四轮核对补的**基线对照**：同一容器、同一 `--ignore` 口径下，把 22 个
   改动文件回退到父提交 `b7d96f5` 的字节再跑全量，12 条失败 node id 与改动后**逐字节相同**（diff 零字节），
   通过数 1378 → 1409，差值即本次新增用例数。
   ⚠️ 本条上一版写的是"**没有**同批用例在改动前代码上同样失败的对照跑——开新容器超出授权边界"；
   那句话在当时是诚实的，现在作废。读数与命令见第 10 节①。
2. **`_resume_law_as_of` 是有损代理**：`run.law_as_of == date.today()` 时折叠成"未指定"。**跨零点行为未测**。
3. **恢复路径不产生 `historical_law_query` 审计**（只在 run 建立时记一次）。
4. AUTH-3 用**未加密钥的 SHA-256**：只解决"日志静止态含个人信息"，**不等于匿名化**——确定可关联，短/低熵问句可被成员判定。升级触发条件已写在报告里（日志读者扩到运维以外 ⇒ 换服务端密钥 HMAC）。
5. **成本口子未加限额**：显式基准日会退出零 token 直返与共享缓存 ⇒ 客户端可把一个日期把命中打成未命中（有界：单请求、60/分钟、最贵等于一次未命中），但调用者从评测通道变成**任意已认证用户**。`settings.py` 已把该耦合写进注释。
6. `docs`（答案）与 `contract_data["docs"]` 的潜在分叉：本轮靠同源构建规避，未从结构上消除。
7. 未 push、未部署。AgentRun/消息/上传/导出下载与评测参数的**双用户端点全矩阵探针**本轮未做（见报告"动态覆盖"段）。
8. ~~`/api/feedback` 是第二条沉淀入口，未加日期闸~~ **【已闭，方式与本文原推荐不同】**：第四轮核对查出
   原推荐方案（只在 `_qa_direct_return` 读侧拒绝 `feedback:` 来源）**只闭一半**——同一条记录还会被
   `main._build_messages` 以"此前已确认的问答（可优先参考）"注入模型，那条通道既不经 `law_as_of_basis`
   也不经时效校验。最终落地的判据改为**按证据形状整类判定**（有条文引用**且**有版本基准日才可参与生成），
   挂在产生处 ⇒ 两个出口一起关；写侧同时停止为 `feedback:` 创建候选。落地于第 10 节⑤记录的提交。
   原条目说的"需 schema 改动"因此**不成立**：闭它不需要动数据模型。
   ⚠️ 但本条那句"既不经 `law_as_of_basis` 也不经时效校验……两个出口一起关"当时**只兑现了一半**：
   挂在产生处的是**形状**判据，"引用的条文还在不在库"这步时效判定仍只写在直返出口 ⇒
   注入通道对"引用给得出、库里查不到"的记录仍是敞开的。这一半由票 W1（第 11 节）于 09-25 闭掉，
   形态是抽**一个** `retrieval.qa_citations_in_kb` 让两个出口调同一个对象。
9. **`/api/law` 与 `/api/law/search` 恒按当日** ⇒ 历史查询引用的条号在这两个回查端点 404；Agent 路径已有快照回查分支，两条出口契约不对等（第 8 节⑥）。
   **【第四轮核对改判：本项暂缓，且 404 的真因不是"没接日期"】** 生效语料 10266 条实测
   `status` 全为"现行"、`effective_from` 与 `effective_to` **全为空**（第 10 节③）⇒ 给这两个 GET 加
   `law_as_of` 今天换不来任何一个 404 的消失：404 的原因是库里没有已废止法律的文本，而不是没传日期。
   先做的是一张**语料数据票**（补废止/修订版本 + 填日期边界），date 参数等数据到位再加。
10. **【评审纠正的基线认知】** 上一节第 1–5 条里凡说"表现为静默丢证据而非答错版"的框架，只适用于**上一轮未提交的中间态**；已提交的父提交 `b7d96f5` 上快车道**完全没有**日期过滤，即"答错版"风险当时并未被部分缓解。本改动集修的就是这个状态（第 8 节①）。

## 7. 待办

| 项 | 谁定 | 说明 |
|---|---|---|
| ~~独立评审结论回收 + 必要的 fix 提交~~ | ✅ 已完成 | 结论进第 8 节；真缺陷修复 = `974e3da`；两条过宽陈述已勘误 |
| ~~`/api/feedback` 沉淀第二入口是否闭~~ | ✅ 已闭（第四轮核对） | Owner 裁决：判据**按证据形状整类判定**（有条文引用 + 有版本基准日）挂在产生处，两个出口一起关；写侧同时停止为 `feedback:` 创建候选。**不需要 schema 改动**——本文与指导文档原先都把它当成"必须改数据模型"，那是错的判断，依据见第 10 节②⑤ |
| ~~`/api/law`、`/api/law/search` 是否接基准日~~ | ⏸ 暂缓，改开语料数据票 | 生效语料 10266 条无任何日期边界元数据（第 10 节③）⇒ 现在加 `law_as_of` 换不来一个 404 的消失。先补废止/修订版本与日期边界，再评估要不要扩公开 API 面 |
| **语料数据票：废止/修订条文 + `effective_from/to`** | ⏳ 取数**已完成**，卡在两处人工确认 | Owner 已裁：工作源=**已授权的元典 MCP**（flk 出网那条被权限层拦下，不重试）；口径 A/B/D/E 已定（旧法 `effective_to` 按"最后有效日（含）"= **`2020-12-31`**，与 `CIVIL_CODE_EFFECTIVE` 同源不新立分水岭；法释〔2020〕15 号**引文本不改判据**）。本轮 20 次调用把 7 部法的法级全覆盖、条级取到 6 部，并把四处先验知识升级成实测（民法典 1260 条原文=九部同日废止；废止解释的 instrument=**法释〔2020〕16 号**，施行 2021-01-01）。**仍待**：① 该决定**附件清单**里是否含合同法解释（一）（二）——法务逐条核，我不代签；② **Owner 09-25 已裁"补"**（原为待签项）：本仓词表有五值 `已修改` 而 `is_valid_by_time` 的 fail-closed **不覆盖它** ⇒ 已定"被修正版替代的旧版必须补 `effective_to`"，执行形状落在数据票 §3-G（**校验在批处理层、读侧谓词零改动**）。裁之后为把 §4b 落成可执行值补测 1 次调用（经济合同法 `(1993修正)` 施行日 = **1993-09-02** ⇒ 1982 原文 `effective_to=1993-09-01`），取数累计 **21** 次（上面那 20 次是 09-25 那笔的读数，不含这次）；③ §3-F 溯源键（含 `status_src`）。**本轮仍未写任何库**（收尾复量 `app.db`/`chroma`/`quota` mtime 与开工前一致）。读数与勘误见 `docs/process-archive/corpus-time-meta-ticket-20260925.md` §1b–§1e、§4a–§4e、§6 |
| ~~AUTH-C 授权与已知日志路径复核~~ | ✅ 探针已落地（第 10 节⑨） | 静态审计（AST 扫 40 条路由）+ 7 条双用户探针 + 4 处"摘归属检查"变异各打死自己那条。两处票面行为已按实测修正：`PATCH /api/conversations/{id}` 的 `title` 是查询参数；`/api/chat` 带他人 conv_id 的真实契约是 200 + 新建会话而非 404 |
| ~~prompt 注入侧要不要也要求"引用可在库解析"（两出口对称）~~ | ✅ 已落地（第 11 节） | Owner 裁决「对称收口，判据上提到产生处」。形状判据第五道只管"引用给不给得出"，而"引用的条文还在不在库"这步此前**只写在**直返出口 ⇒ 一条引用已删条目的记录照样进 prompt。修法是抽**一个**判据本体 `retrieval.qa_citations_in_kb`，两个出口调同一个对象（不是各抄一份循环）。代价已实测：每条引用约 **80 ms** 元数据读，且**只新增在** 0.7≤score<0.92 的"仅注入"记录上——直返（≥0.92）那条本来就在付这笔钱 |
| **agent 路径 4 处日志原文是否脱敏** | Owner | 本轮不改代码，只在第 3 节那行加了范围限定。要定的是"这些日志谁会读"——`progress §6` 第 4 条已给过 HMAC 的升级触发条件；改法会削人工回看能力，所以不由执行助手代决 |
| `docs/process-archive/superpowers/plans/2026-09-22-git-repair-execution-runbook.md` 是否入库 | ✅ 已入库 | 第四轮核对随文档一笔 add（本轮安全判断的依据全引它，未跟踪状态经不起一次 `git clean`） |
| `law_as_of` 缓存击穿是否加限额 | Owner | 见第 6 节第 5 条。第四轮核对补充事实：真实语料上 cutoff 今天不改变召回，所以这条限额的紧迫性与"取数空转"绑定，先不动 |
| 部署 | Owner | 服务器未选定，票面禁令仍生效。⚠️ 本机现有一组 `fazhi-backend/caddy/frontend` 容器在跑且 bind mount 真实 `chroma_db`——那是别的会话的活动，本轮未触碰 |
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

## 9. 转发前自检：把本文当**交付物**读一遍查出的问题

第 8 节那次评审查的是**代码与陈述**；这一节查的是**这份文档本身能不能给别人读**。
第三方评审抓不到这一面——它的问题域里没有"引用坐标准不准""账算不算得上"。五类，全部实测后才写：

| # | 问题 | 怎么量出来的 | 处置 |
|---|---|---|---|
| ⑩ | **6 处 `file:line` 是从评审 brief 沿用、我没逐个复测**，最多差 **38 行**（`/api/law` 写 1563 实为 1525；`create_candidate` 写 2863 实为 2876；`basis` 判定写 1187 实为 1186；⑨那五个 `cache_key` 坐标在当前树里**根本对不上**；③的两处差 1 行） | `sed -n '<N>p' <file>` 逐行取内容比对；漂移的根因是我自己在 `main.py:1291` 插了 11 行函数，把之后所有坐标整体下移 | 全部改成本仓立过的**符号锚点**纪律（函数名 / 判定式 / `"is_snapshot": True` 那一支 / `grep -n "_exit_law_as_of(pre, body)"`）；确需坐标的两处显式标注"`b7d96f5` 版"，另一处当场复核该行仍在 |
| ⑪ | **一条引用指向不存在的小节**：我写"见报告『沙盒与取证仪器』节" | `grep -c "沙盒与取证仪器" 报告 = 0` | 改指真实出处 `handoff-gap-tickets-h-i-j-20260920.md:51`（"live 工作树跑全量=禁止、副本树内允许"）。**这条最该记**：本仓记忆里明明写着"引用未来的/不存在的证据＝与引用不存在的文件同一件事"，我在写下它之后的同一轮踩了自己这条 |
| ⑫ | **两笔算不上的账**："24 文件（21 改 + 2 新增）"（21+2≠24）；"已本地提交两笔"（实为多笔） | `git show --name-status 065038c` → 22 改 + 2 新增；`git rev-list --count b7d96f5..HEAD` | 改成 22 改 + 2 新增；并把"文档共几笔"这种**会因记录而作废**的计数整体删除，改为不依赖计数的写法：核对代码只认两笔，且实测 `git diff --name-only b7d96f5 HEAD -- backend` 与那两笔的并集**完全相同（22 文件）** |
| ⑬ | **两处只读对照表就会接错结论**：第 2 节"失效模式＝静默丢证据"、第 2 节缺口 3"降级沿用 run 日期"，都已被第 8 节推翻但正文原样留着 | 通读时按"审核人只看表格"这个动作模拟了一遍 | 就地加 ⚠️ 标注并指向第 6 节第 8–9 条与第 8 节①②③④⑥。**这正是你上一轮问"全都写进去了吗"时逼出来的一类**：结论写在末尾不等于前文被修正 |
| ⑭ | **提交信息被 shell 截断污染**：用 `-m` 传提交信息、正文里以反引号包住提交号 ⇒ shell 把反引号当命令替换执行，两个 SHA 消失、混进 22 行文件列表 | `git log -1 --format=%B` 读回来发现 | **文件内容完好，只有 commit message 坏**（`git show --stat` 显示该笔仅 1 文件 5+/4−）。修它要 `--amend`，按规矩需你点头 ⇒ 当前**待定**；纪律侧的修法已生效：提交信息一律走 `-F <heredoc 文件>` |

另两处**为转发而补**的内容（不是缺陷）：开头的"给审核人的三句话"声明本文性质（执行者自述；独立复核由
另一名 AI 评审 agent 做，**非人类签认**；最易误读的两处看哪里），以及附录里"没有那台容器怎么复现"
（宿主 `backend/venv` 依赖齐全，同一 15 文件集宿主 **243 passed / 2 skipped** vs 容器 **235 / 10**，
总数都是 **245**，差在 skip 归属）。转发前对整份文档重跑了一遍按值反查扫密（189 条 `.env` 值 +
AKIA / sk- / JWT / PRIVATE KEY / 带密码连接串五类形状，**全零命中**）。

**一句结论**：代码要过第三方评审才算"复核过"，**文档要过一遍"别人第一次读"才算交付**。
这一轮的五类问题里，只有⑬是你上一轮追问逼出来的，其余四处（含最严重的⑪——引用了个不存在的章节）
都是我写完就以为完事、没有把成品当外发物读过。

## 10. 第四轮核对（接手会话，2026-09-24 夜 → 09-25 凌晨）

第 8 节那次评审查的是**代码与陈述**，第 9 节查的是**文档能不能被外发**。这一轮不同：
它是**下一任执行者带着两份文档回来对账**的结果——先核本文说的每一条，再核指导文档
[`auth-review-followup-guidance-20260924.md`](./auth-review-followup-guidance-20260924.md) 说的每一条，
凡能本机实测的一律实测后才采信。四条**新事实**改变了后续路线，其中两条把指导文档自己的推荐推翻了一半天。

| # | 新读数 | 怎么量出来的 | 改变了什么 |
|---|---|---|---|
| ① | 全量 12 项失败是**既有失败** | 容器内把 22 个改动文件回退到 `b7d96f5` 的字节（21 改 + 删 1 个新增测试文件）跑全量 = `12 failed / 1378 passed / 25 skipped / exit 1`；改动后 = `12 failed / 1409 passed / 25 skipped / exit 1`；两份失败 node id 排序后 `diff` **零字节**、rc=0 | 本文第 6 节第 1 条的"尚无基线对照"作废；指导文档 §2.3 要求的那一步已做掉。跑完已还原并逐文件复量 md5（容器无 bind mount） |
| ② | 生效 QA 语料里 `feedback:` 来源 **0 条** | `chroma.sqlite3` 以 `mode=ro` 打开，按 metadata key 分组计数：`qa_pairs` 279 条全有 `evidence`、`qa_pairs_te4` 21 条全有，`evidence LIKE 'feedback%'` 均为 0；`backend/app.db` 的 `qa_candidates` 759 行同形状亦 0 | 指导文档 §3 推荐方案 B 的理由里"覆盖**已采纳**条目"是**潜在**覆盖面而非既成事实 ⇒ 写侧关闭与读侧关闭今天等价，才使"整类按形状判定"成为更便宜且更稳的选择 |
| ③ | 真实语料**没有日期轴** | 同一库 `legal_provisions_cos` 10266 条：`status` 全部为"现行"、`effective_from` 全空、`effective_to` 全空（string/int/float 三列都查过，排除键名猜错）；谓词侧确认 `is_valid_by_time` 是唯一日期判据（`request_bootstrap.py` 末尾复筛 + `retrieval.py` 向量池/BM25 + grounded 三处），无按日期的 chroma `where` 过滤 | 本票"把 cutoff 贯穿取数口"这条主交付**今天不改变任何一个召回结果**（空日期在谓词里=无限制）。⇒ 指导文档留给 R15-3 的"真实历史法文本覆盖率未核"有了答案：**0**。也据此把 AUTH-B 从"加参数"改判为"先补语料" |
| ④ | 端点与日志底账 | 全仓无 `APIRouter`/`include_router`，路由都在 `main.py`；唯一的 `FileResponse` 是 `get_media`；消息只嵌在 `GET /api/conversations/{id}`。日志原文命中（除本文已记的 `fast_path_law_version_detail`）：`agent/runtime.py` 的 `detail`（**用户问句原文** `[:300]`）、`agent/controller.py` 的 `agent_planner_raw_tail`（`[:500]`）、`agent/service.py` 的 `agent_claim_checks.claim`（`[:120]`）与 **`rationale` 无截断** | 指导文档 §4 AUTH-C 票面列的"导出/下载端点""messages 端点"**不存在** ⇒ 照票面跑就是造测试；第 3 节"AUTH-3 日志不落原文"那行的射程已被就地限定 |

**另有两条要单独记，因为它们关系到别人能不能接着干：**

⑤ **AUTH-A 已落地**（不是"待决"了）。判据：`retrieval_core.qa_provenance_verifiable` ⇒
`evidence` 含至少一条 `source` 与 `article` 都非空的引用，**且** `law_as_of_basis` 非空，才允许参与生成；
挂在产生处 `request_bootstrap.prepare_fast_path` ⇒ 直返与 prompt 注入两个出口一起关，
出口侧另自带一份（有评测探针直接构造 `pre` 调 `_qa_direct_return`，那条路径绕过产生处）。
写侧 `/api/feedback` 不再创建沉淀候选。判据形状解析 `cited_articles` 与时效护栏共用，不留第二份。
被取代的旧口径写在 `_qa_direct_return` 的 docstring 里（"缺字段⇒不拦"），对应控制腿已改名成反转断言。
真库判据读数：`qa_pairs` 279 → **277**（新剔 2 条 `evidence='[]'`；那 1 条"部分空 article"的记录仍有可用引用，
按规则应当放行——我在校准阶段把它错算成 276，以真判据扫库的结果为准），`qa_pairs_te4` 21 → **0**。
验收证据（红→绿 7 条、两次变异各打死对应用例、容器 19 文件定向 `261 passed / 10 skipped / exit 0`、
全量 `12 failed / 1418 passed / 25 skipped` 且失败集与基线仍逐字节相同、`ruff`/`mypy` 干净、扫密零命中）
在提交信息里，核对代码只认该笔 + 本票前两笔。

⑥ **两个仪器级教训**（都属于"复核手段自己造假证据"这一族）：
(a) 变异跑者第一版用文本锚点还原，而 M2 的目标行 `    return True` 在 `retrieval_core.py` 里出现两次
（`is_valid_by_time` 的收尾与之同形）⇒ 还原锚点不唯一，跑者按纪律拒绝还原并把文件**留在变异态**。
第二版改成"变异前抓原始字节快照、还原走 `write_bytes`"，两次还原后 sha256 与基线一致才算过。
(b) 指导文档 §8 的 R15-2 反例**字面不可复现**：`extract_dates` 解析不了"1980年"（要 `年月日` 或 ISO/斜杠），
照原文跑 `law_version_crosses_watershed` 得 **False**。缺陷本体为真（该函数取 `dates[0]`，与 claim 句段无绑定），
但反例必须写成完整日期（如"1980年3月5日出生" + "2023年4月1日到期"）才成立 ⇒ 已在指导文档就地更正；
下一个人若照旧字面复现，会误判成"不复现"而放走一个真缺陷。

⑦ **本轮自查出并提交后修正的一条数字（勘误，不改写历史）**：AUTH-A 那笔提交的"证据"小节里，
扫密一条写成了"49 个 `.env*` 的 **269** 条非平凡值零命中"。真值是 **64** 条——269 来自同一次输出里
`269998 chars`（diff 字节数）被我读成了条数。两点要分清：
① 该条的**结论成立**（49 文件 / 64 值 / 值反查零命中 / AWS·sk-·JWT·PRIVATE KEY·连接串内嵌密码五类形状读数均为 0，
对本笔与本轮文档笔各复量一次同口径），错的只是覆盖面数字；
② 我在核对过程中还犯过一次同族的错——把截断输出读成"连接串形状命中 2 处"并当场说出来，
随后的复量证明是 0 处。**教训与第 9 节⑪同形**：截断的输出不足以支撑任何计数结论，
凡要报数就必须让那次命令**一次把全部读数打全**（本轮的最终形态就是单条脚本同时输出两个对象 × 五类形状 × 值反查）。
提交信息不 amend（本笔未被他人引用是事实，但改写历史需 Owner 点头），以本条勘误为准。

⑧ **AUTH-A-2（Owner 裁 A 案"补写入口径"）已落地**，顺带把三条"写的时候就不对"的陈述改对。
缺口本体：第 ⑤ 条那道"缺 `law_as_of_basis` ⇒ 来源不可校验"上线后，**全仓没有任何生产者写这个键**
（存量 279 条的值来自 09-20 一次性回填，运行时四条写路径一条都不写）⇒ 新沉淀的语料**永久**过不了
第五道，零模型直返会静默衰减到存量。修法是 `add_qa_pair` 在调用方未给基准日时自己落**当日**
（与票 T6 同一形状：单一闸口堵整类，不逐点补），唯一例外是人工采纳——`decide_candidate`
传候选 `created_at` 的日期（**采纳≠产生**）。
**时钟取 UTC 不是本地当日，这条是被撞出来的不是想出来的**：写判据那晚本机恰跨过本地午夜
（本地 09-25 / UTC 09-24），首版拿 `date.today()` 当期望值，实现按 UTC 落 ⇒ 两条腿当场红。
UTC 与 `QaCandidate.created_at`（`datetime.utcnow`）同一个钟，默认路径与采纳路径的"当日"不会互差一天；
判据改用**钉钟**（`_PinnedDatetime`，并断言实现确实传了 UTC）替掉读宿主时钟，换成本地钟就撞不上期望值。

改对的三条陈述（都属第 9 节那一族"读数与代码不一致"）：
· `main.py` 沉淀闸注释原写"`law_as_of_basis` 只由 seeds/生成脚本写"——那两个文件里**一次都没出现过**，
  是幽灵注释（正是它让第 ⑤ 条那道门上线时没人发现没有生产者）；
· `_qa_direct_return` 的 `if law_as_of is not None and basis_raw:` 里 `and basis_raw` 是**死条件**
  （上面第五道已保证非空），摘掉；
· 两处计数错：`cited_articles` docstring 写"279 条 = 200 JSON + 76 管道符 + 3 其它"，只读复量真值
  **203 JSON（含那 2 条 `'[]'`）+ 76 管道符 + 0 其它**、判据实际放行 277；
  `tests/test_request_bootstrap.py` 一条注释写 `evidence='[]'`"实测存量 5 条"，真值是**生效集合 2 条**
  （另一 lane `qa_pairs_te4` 另 2 条）。复量口径：`chroma.sqlite3` 以 `mode=ro` 打开，
  按 `segments.collection` 关联取 `evidence` / `law_as_of_basis` 的 `string_value` 分组计数。

**新拦截从此可观测**：产生处每拒一条记录落 `qa_provenance_refused` 结构化告警。刻意只落一个归因键，
不落"缺 basis 还是缺引用"的分解（那等于在日志里放第二份判据，改门时它会开始说谎），也不落题干
（AUTH-3）。**这一条差点自己造假**：字段没登记进 `observability._ACCOUNT_FIELDS` 时，本仓哨兵
`test_log_fields_are_all_registered_in_whitelist` 直接报"会被 JSON formatter **静默丢弃**"
⇒ 若不跑宽套件，这个"可观测"补丁在机器日志里根本不存在。补登记后加了一条腿把被拒记录过一遍
真 `_JsonFormatter`，断言 JSON 里看得见这个键（哨兵只验注册，不验输出）。

判据与证据：`tests/test_qa_basis_write_side.py` 5 条 = 1 先红 + 3 控制 + 1 生产路径（先红改前红在
`TypeError: unexpected keyword 'basis'` 与落库空串，不红在 import）；接线腿 1 条钉在
`test_qa_invalidate.py`（那里的替身吞掉参数 ⇒ 结果侧判据看不见"采纳路径到底传没传产生日"这条线，
替身同时补上 `created_at` 以对齐真行）；留痕腿 1 条 3 判（拒必留痕、放行不留痕、JSON 里可见）。
变异 6 案：删默认基准日 / 采纳不传产生日 / 时钟丢 UTC / 整块删日志 / 日志去归因键 / 撤白名单登记，
各打死对应用例（前 3 案各打死 3 条腿、后 3 案打死留痕与哨兵），还原逐文件复量 sha256 一致。
`ruff check` + `format --check` 对改动文件干净、`mypy` 5 文件零问题、登记表 E2 三格文字随票更新后
重新生成 `docs/gate-exit-registry.md`（哨兵 15 passed）。

**宽套件这一轮又立了一功，也暴露了我自己一处假绿**：撤白名单登记那一案打死的是
`test_log_fields_are_all_registered_in_whitelist`——**这个字段是本票新加的，我按"定向 96 passed"
就想收口，而哨兵只跑在宽套件里**。若不跑它，`qa_provenance_refused` 会被 JSON formatter
静默丢弃 ⇒ "新拦截可观测"这个交付在机器日志里根本不存在（第 9 节那一族：**验了注册不等于验了输出**，
补的那条真 `_JsonFormatter` 腿才是把这一格钉死的东西）。
副本树全量（只搬 `backend/` + 真库副本，`CHROMA_DIR`/`DATABASE_URL` 显式钉在副本内）
= `12 failed / 1470 passed / 2 skipped / exit 1`，另排除 3 个 import 期就要仓库根
`release-evidence/` 的 runner 文件；那 12 项**未逐个定因**，定性证据是同 12 项 node id 在宿主
定向复跑 **12 passed** ⇒ 属副本树缺件而非代码失败。补白名单登记前后各跑一次，失败集差**恰好只有**
`test_log_fields_are_all_registered_in_whitelist` 这一条（`diff` 只有 `13d12`）。

⑨ **AUTH-C（授权探针）已落地**：判据不是"预期查出漏洞"，而是把静态审计结论钉成实测。
AST 扫 `main.py` 全部路由（含 `AsyncFunctionDef`——第一版只扫同步函数，`/api/chat`、`/api/law`
整批漏在结果外面，那种"零可疑"是仪器漏了不是代码干净）：**40 条路由**，用户级且带 id 的
（`conv_id` / `run_id` / `filepath`）**全部**有归属引用 ⇒ 与票面结论一致。
探针 7 条落在 `tests/test_auth_c_ownership_probes.py`，契约按**真实行为**写：
GET/PATCH/DELETE `/api/conversations/{id}`、`/api/feedback` 带他人 conv、`/api/media/...` ⇒ **404**
（非枚举形状，并断言响应体不含他人标题）；列表口只含自己的行；
`/api/chat` 带他人 `conversation_id` ⇒ **200 + 静默新建自己的会话**（不是 404，票面第一版写错了这条）。
可失败性是逐条摘检查验的：摘 GET 归属 / 摘 DELETE 归属 / 摘 media 归属 / 把 `request_bootstrap`
的越界支路改成"照用他人 conv_id"，四个变异**各只打死自己那一条**探针，还原逐文件复量 sha 一致。

两条**探针自己写错**的契约（不记下来，下一个人会以为代码有问题）：
· `PATCH /api/conversations/{id}` 的 `title` 是 **查询参数**（FastAPI 对标量 `title: str` 的默认解释），
  发 JSON body 得 **422** ⇒ 夹具没建好时那两条用例是**假绿**；修法是在夹具里断言 200，
  让"夹具坏了"当场红而不是静默通过。
· `image_ref` 是**相对 `backend/`** 的存盘路径（`models.py:56` 的注释 + `get_media` 用
  `dirname(MEDIA_DIR)` 作 base）⇒ 值必须形如 `media/xxx.png`。探针写成裸 `xxx.png` 得到的是
  **400（非法路径分支）**，归属那一段根本没跑到。
media 那条钉的是**执行顺序**（owned → isfile）：让 `os.path.isfile` 一被调用就抛，
证明越界请求不会去碰磁盘——只断 404 的话，"先查盘查不到所以 404"与"归属挡住了"长得一模一样。

**本轮的元结论**：第 8 节证明了"把中间态当成已证明的事实"会被第三方抓出；第 9 节证明了"把成品当交付物读"
能抓出引用与算账错误；这一轮多暴露一类——**陈述在其写下时刻是真的，但依赖一个会消失的前提**。
①②③三条没有一条是"写错了"，全是"写的时候对、说完前提就变了或本就没人核过"。
对应的动作不是更谨慎，而是像本表这样：**把每条结论依赖的那个读数、和读数的产生命令一起留在原地**。

落款：本节由接手会话于 2026-09-25 00:1x 撰写（`date` 实取值 00:18），当时 `HEAD` 为本票 AUTH-A
那笔代码提交、`git rev-list --count HEAD` = 122。这两个数都会随下一笔提交作废，需要现值请现跑。

---

## 11. 票 W1：QA 时效判据上提到产生处（两出口对称收口，2026-09-25）

票面来源：Owner 在 grilling 对齐里裁"**对称收口，判据上提到产生处**"，并在我复核后把执行形状
改成"**抽一个函数、两处调同一个对象**"——原话的风险是我把循环抄成第二份，那等于制造下一个漂移源。

### ① 补的是哪一半漏口

第 10 节② 那轮（票 AUTH-A）把"来源可校验"挂在产生处，闭掉的是**形状**判据：引用给不给得出。
但一条语料命中有**两条**出路，而"引用的那条文今天还在不在库"这步时效判定**只写在**
`main._qa_direct_return`（直返）里，产生处从不查库 ⇒

| 出路 | 改前 | 改后 |
|---|---|---|
| ① 零模型直返 `main._qa_direct_return` | score + 形状 + 分水岭 + 指纹 + **时效** | 同一判据对象 |
| ② prompt 注入 `main._build_messages` 的"此前已确认的问答" | score + 形状（**无时效**） | 由产生处统一拒 ⇒ 一起关 |

漏口的形状值得记一句：**两条出路共用同一个 `pre["qa_hit"]`**，所以只在其中一条出口加护栏的
修法，下一轮一定会被"另一条为什么没测"追问回来（第 8 节② 犯过一次，这次是它的另一半）。

改动：`retrieval.qa_citations_in_kb`（判据本体，解析复用 `retrieval_core.cited_articles`、
命中复用 `exact_article_lookup`，两侧 fail-closed：解析不出任何引用 ⇒ 拒、库读不动 ⇒ 拒）；
`main._qa_direct_return` 改调它；`request_bootstrap.prepare_fast_path` 在形状门**之后**接同一对象；
`observability._ACCOUNT_FIELDS` 新增 `qa_citation_refused`（与 `qa_provenance_refused` **分键不分门**）。
判据本体住在 `retrieval` 而不是 `retrieval_core`：后者是全仓唯一的**纯谓词层**（不碰库），
且方向上只有 `retrieval → retrieval_core` 无环（`retrieval.py:24`）。

### ② 判据与先红读数（改前树上实跑）

`tests/test_request_bootstrap.py` 新增 **6 条**，改前跑 `-k` 同一条命令的实测读数是
**4 failed / 2 passed**：
· 红在判据点的 4 条：`test_fast_path_drops_qa_hit_whose_citation_is_not_in_kb`、
`test_prompt_omits_stale_citation_qa_from_the_producer_result`（喂进 `_build_messages` 的是
产生处**实际返回**的 `pre`，不自造）、`test_fast_path_drops_qa_hit_when_article_lookup_raises`、
`test_citation_refused_qa_hit_leaves_a_log_trace`。
· 两侧都绿的 2 条控制腿：`test_fast_path_keeps_qa_hit_whose_citation_is_in_kb`、
`test_shape_gate_runs_before_the_kb_and_skips_the_lookup`。
`tests/test_qa_citation_gate_symmetry.py` **7 条**（本体 2 + 共享性 3 + 直返对偶 2）——
这一份在改前树上是 collection 期 `AttributeError: module 'retrieval' has no attribute
'qa_citations_in_kb'`，**所以它不是先红证据**，它钉的是"共享"这个形状本身。
定向：本批改动落地后 **6 个套件 69 passed**（那是变异跑者的控制轮读数），格式化两次之后按**最终字节**
复量 **7 个套件 76 passed**（多带 `test_auth_c_ownership_probes.py` 7 条，因同批修了它的格式）；
`test_gate_exit_registry.py` **14 passed**（生成物 `docs/gate-exit-registry.md` 已用
`scripts/gen_gate_exit_registry.py` 重生成，手改会红）。

### ③ 变异 7 条，各自打死指名腿（全部还原后 sha 与基线逐字节相同）

| 变异 | 打死的腿（实测） |
|---|---|
| M1 产生处删判据 | `drops_..._not_in_kb` + `citation_refused_..._log_trace`（本轮另见 `prompt_omits_stale`、`when_article_lookup_raises` 一起红） |
| M2 直返出口删判据 | `direct_return_follows_the_shared_predicate[article-missing]` + `test_direct_return_evidence_invalid_misses` + `test_direct_return_still_refuses_dead_article` + 反把"内联"哨兵也踢红 |
| M3 读库失败改放行 | `predicate_is_fail_closed_...` + `when_article_lookup_raises` |
| M4 只核验第一条引用 | `predicate_verifies_every_cited_article` |
| M5 在直返出口内联第二份循环 | `no_exit_keeps_its_own_copy_of_the_lookup_loop[exit-direct]` + `[article-present]` |
| M6 两道门换序（先查库再看形状） | `shape_gate_runs_before_the_kb_and_skips_the_lookup` + 两条留痕腿 |
| M7 归因键不登记白名单 | `test_log_fields_are_all_registered_in_whitelist`（1 failed / 1 passed） |

三条**仪器自己出错**的记录（不记下来，下一个人会把仪器故障读成判据失效）：
1. **顺序腿的见证记录一开始是错的**。我先用 `evidence="[]"` 当见证，M6 换序变异**打不死它**——
   因为那种记录在判据内部因解析不出成对引用**根本不产生查库调用**。换成"引用给得出但缺
   `law_as_of_basis`"才有牙。教训与第 9 节⑪同形：**断言的对象必须真的落在被检性质上**。
2. **变异跑者的失败名正则会吞换行**。`^FAILED ([^ ]+)` 里 `[^ ]` 把换行也吃进去，两条 node id
   粘成一条 ⇒ 首轮误报 M6 "killed=0/1"。单独复量（`-rf` + 只跑那三条）证明 M6 实际打死 3 条。
   把正则改成 `^FAILED (\S+)` 后 7/7 全检出。**仪器报错时先验仪器，再下结论**。
3. **`_patch_kb` 的锚点与位置**：`request_bootstrap.py` 是 CRLF，脚本内按 `\n` 拼锚点会 0 命中
   （第 10 节⑧已记过一次，本轮同族复发一次）；另外我一度把桩定义删了却没补回，
   `NameError` 才暴露——**删定义与加调用必须在同一次改动里核对齐**（`grep -c "^def _patch_kb"` 复量）。

### ④ 这次收口的代价（实测，别用"应该不多"顶替）

真实 KB 只读探针（`CHROMA_DIR` 指向宿主 `backend/chroma_db`，主集合 **10266** 条、
`qa_pairs` **279** 条，本地 embedder，n=9 取中位数）：
· 一次 `exact_article_lookup` **命中** = median **80–95 ms**（min 74.85，max 913.49 那次是首调用冷启动）；
· **查不到**（走 I-6 回退腿 = 两次 `get`）= median **84.74 ms**；
· 判据本体带**两条**引用 = **170 ms**（≈ 线性于引用条数）。

口径要说清：这笔钱**不是新加在直返上的**——score ≥ 0.92 的直返本来每次都在付（旧循环就在
`_qa_direct_return` 里）。W1 新增的射程是 **0.7 ≤ score < 0.92 的"仅注入"记录**
（`knowledge_service.search_qa` 默认阈值 0.7），它们此前不查库。
**本轮未量**：这类请求在生产上的占比、以及 `qa_citation_refused` 的实际触发率——
两个数都要等带流量的日子现跑，别把"命中率本轮未量"（第 10 节的老账）再念一遍了事。

### ⑥ 全量回归（活树禁跑 ⇒ 同一棵副本树跑两遍做差分）

树：`git -c gc.auto=0 archive HEAD | tar -x` 得 `base`，复制得 `patched` 后**只**把本批 11 个文件按名
overlay 进去；两棵树各跑一遍 `pytest tests -q -rf --ignore=`（那 4 个在收集期 `FileNotFoundError` 的
评测 runner，见第 10 节的环境记录）。读数：

| 树 | failed | passed | skipped |
|---|---|---|---|
| base（=HEAD，未含本批） | **2** | 1460 | 25 |
| patched（含本批） | **2** | 1473 | 25 |

失败集合 `comm -13` 差集**为空**，两条既有失败都是 `tests/test_eval_agent.py`（与容器侧记录的
`eval_agent×2` 同名单）；`+13` = 本批新增用例数。静态检查同 CI 口径：`ruff check .` 0、
`mypy .` **Success: no issues found in 73 source files**、`ruff format --check` 对本批文件 0。

**这台仪器自己也错了一次**：首轮 `patched` 报 3 failed，多出来的那条是
`test_gate_exit_registry.py::test_committed_md_is_the_generated_artifact` —— 因为 overlay 循环的
过滤条件是 `^backend/`，把生成物 `docs/gate-exit-registry.md` 漏在了树外。补 `cp` 那一个文件后
该文件 **14 passed**，差集归空。⇒ "回归候选"先查仪器覆盖，再怀疑被测对象（第 5 节的老规矩）。

### ⑦ 边界：本轮没做的

· 判据仍**不复判答案对不对**（登记表 `引用校验` 那格的状态因此仍记 GAP-ACCEPTED，理由原文未改）。
· 没加缓存。若 ④ 那笔开销日后被证明打在热路径上，形状是"给 `(source, article)` 命中结果加 LRU +
  `invalidate()` 挂钩"，而不是把判据从产生处摘掉。
· 真实库、`app.db`、`release-evidence` 一律未写；服务器未选定 ⇒ 无部署动作。

落款：本节由接手会话于 2026-09-25 撰写（`date` 实取值 18:27），当时 `HEAD` = `a6026bc`
（票 AUTH-C 那笔探针提交）、`git rev-list --count HEAD` = 129。这两个数随下一笔提交作废，需要现值请现跑。

---

## 附录：复现命令

```bash
# 容器无 bind mount ⇒ 必须先逐文件 md5 对齐（宿主 backend/X → 容器 /app/X）
# ⚠️ 本清单第一版用 `git show --numstat HEAD` 取文件——那是在**当时代码就落在 HEAD** 的前提下。
# 本文入库后 HEAD 变成 docs-only 提交，那条命令返回 **0 个文件** ⇒ 循环一次都不跑、
# 看起来"无差异"，是一台会产出假"已对齐"读数的空转仪器（第四轮核对第 9 节⑩的同族复发）。
# 现在按**明确的代码提交范围**取文件，并且清单为空即失败。
export MSYS_NO_PATHCONV=1                     # 否则 docker exec -w /app 报 "Cwd must be an absolute path"
cd C:/Users/33393/Desktop/ai-legal-helper
CODE_BASE=b7d96f5                             # 本票代码的父提交；核对代码只认 065038c + 974e3da
git diff --name-only "$CODE_BASE" HEAD -- backend | grep '^backend/' > /tmp/f22.txt
test -s /tmp/f22.txt || { echo "FAIL: 代码文件清单为空，不要继续"; exit 1; }
echo "files=$(wc -l < /tmp/f22.txt)"          # 当前应为 22
while read -r f; do
  [ -f "$f" ] || { echo "FAIL 本地缺文件 $f"; exit 1; }
  h=$(md5sum "$f" | cut -c1-32)
  ch=$(docker exec codex-auth-review-test md5sum "/app/${f#backend/}" | cut -c1-32)
  [ "$h" = "$ch" ] || echo "DIFF $f"
done < /tmp/f22.txt

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
