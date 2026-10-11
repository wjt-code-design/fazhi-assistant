# 非部署收尾：Owner 会话复核与后续建议（2026-10-11）

> D-3 当前候选后续复核：双栈隔离副本补齐测试后均 2016 passed / 10 skipped / 18 deselected、cov 86.55%，前端 lint/tsc/vitest 83 项及 CI 额外预算守卫 9 项通过。原样当前源码在两栈都有两处旧测试接线红，迁移另发现 variant_of 判据假绿；修订仅在副本，候选没有变。NumPy 干净安装边界、私有接口版本范围、严格审计 CPU torch 未识别及 Chroma/setuptools 残余风险仍待处理。当前对象和最新下一步以 [D-3 当前候选复核报告](C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/reports/d3-current-candidate-review-20261011.md) 为准，D-29 不落地裁定与其他授权边界未被本轮改变。不是整体安全、发布或阶段完成声明。

> D-14 后续限定范围更新：Owner 选择 A 后，本会话已完成四只 CLI 的默认预览/显式目标与写入、评测临时库/工作目录隔离、异常清理与定向反证；两轴复核无未关闭的确定问题。当前结果见同目录 `d14-index-guards-20261011.md`（208 项综合隔离回归、24 项既有邻域通过）。候选代码未提交，完整项目门未重跑，真实模型/检索质量未因此通过；本页原始只读状态及“D-14 仅开票”属于更新前历史，不代表当前状态。D-3、凭据/真实数据、历史整合、CI 与部署仍未由该更新改变。

> D-34 后续限定范围更新：Owner 此后批准 A 及响应归属收敛修复，当前本地验收通过；最终证据见同目录 `d34-response-owner-closeout-20261011.md`。本页 R6 的“待复现/待修复”、§4 第 1 项的“先对齐”及当时无产品修改状态是原复核时历史，不代表 D-34 当前状态；不能把本次局部关闭推导成其他门通过。除 D-34 本地修复/测试与报告外，依赖、真实库/凭据、历史整合、远端 CI 与部署状态未由该更新改变。

## 1. 结论与适用范围

**本轮工程成果可以继续接收复验，但非部署发布阶段尚未完成，暂不按旧推送卡执行。** “工作记录已整理”“已开后续票”“风险已登记”不是相应验收门通过；正式版报告也不等于阶段完成。

本次输入是 `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/reports/decisions-needed-20261010.md`，对照原执行书、相关报告、候选源码和原始日志。只修改运行根中的复核/指导文档；未修改候选或主仓产品、测试、依赖、Git 索引及 refs；未运行完整测试、浏览器、模型或容器；未接触真实业务库和凭据值。

旧报告登记的 Owner 裁定只作追溯记录。本次没有获取那些对话的原始裁定，不能因此新增风险接受、部署或实库操作授权。

- 主仓：`C:/Users/33393/Desktop/ai-legal-helper`。
- 候选：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`。
- 运行根：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`。
- 本次观测候选 HEAD：`19e296e879ac2ffbb0a862c2c9e595d3c81c8ded`，分支 `codex/nondeploy-closeout-20261010`；tracked 状态干净。未另行枚举全部未跟踪文件。
- 原执行书：`C:/Users/33393/Desktop/ai-legal-helper/docs/superpowers/plans/2026-10-10-non-deployment-release-closeout-execution-plan.md`。

本文优先于上述运行根旧报告中与之冲突的完成声明和执行建议。历史日志保持原样；未同步到候选 `docs/closeout-20261010/`，执行者以后接收本文时必须登记新的文档差异，不能继续声称两处镜像完全相同。

## 2. 发现及处置

### R1 高：阶段口径仍被“已派单”与“已闭合”混用

原执行书要求全部必需非部署门通过，且明确风险登记不能变绿。决策清单 §G 却将 C 称为闭合，将 H 称为闭合，将 I 称为只差推送；§H 同时列有依赖迁移、远端历史整合、真实模型、真实数据与浏览器补证等未完成事项。

纠正：C 的风险处置方案已登记，不等于 13 个 LangChain 风险已修复；F 是未运行/前置阻塞，不是 PASS；G 是因现役形态与授权边界不满足而 BLOCKED；H 只能按子项记账；I 尚包括历史整合、PR、当前对象 CI、审查及合并。J 文档已交付，但阶段结论仍 BLOCKED。

工程 PR 可以独立交付不依赖缺失证据的安全改动，但不能据此宣称阶段完成或可上线。

### R2 高：推送卡不宜直接执行，D-20 的依赖有环

旧卡 §1 保留了“TLS 不通、远端未知”，§2 A4 保留错误形状 `origin/<远端真实头>` 和旧 dirty 数；A6/A7 又允许本地合并后直接推 master。D-20 要求“PR 已合或已批准”作为前置，而同一文件负责解决无共同祖先的历史整合，PR 可合并性反而依赖它。

纠正顺序：

1. 固定候选并核查当前远端默认分支、SHA、保护规则；核查待发布源码/工作流无部署触发器及凭据问题。
2. 在私有整合候选处理 D-20：取回明确远端对象、逐项保留/裁定两侧差异；不得操作主仓、强推或批量选一侧。
3. 复验整合后对象；凭据处置、公开内容审阅、当前对象独立审查完成后，才普通推独立分支。
4. 对已建立共同祖先的整合分支开 PR；验证实际 head/base、mergeability 和当前检查。
5. 必需检查/审查/保护全部满足才正常合并；不以直接推 master 绕过 PR。合并后的 CI 另记。

若希望先发布工程候选供查看，须单独确认公开范围，且不得承诺无共同祖先的分支可直接开正常 PR。无父快照会改变历史保留和整合路线，不是本次默认备选；当前树无某个旧值也不能证明整个公开集合不含其他敏感信息。

### R3 高：管理员凭据轮换方案缺少真正的失效目标

候选 `backend/seed_admin.py` 在管理员已存在时直接返回；`backend/auth.py` 的登录校验使用数据库 `password_hash`。因此只改 `ADMIN_PASSWORD`、重新运行 seed 或去“供应商控制台”都不能证明已有管理员口令已失效。

此外 JWT 由 `JWT_SECRET` 签名，认证不检查密码版本。即使改了密码，已签发令牌也不因该动作自动失效。

处理要求：先确定历史裸值的实际用途及复用范围，不展示该值；Owner 在正确账户/环境完成失效或证明不再使用。若确为管理员密码，需要更新实际账号密码，而不是只改配置，并评估已签发会话的失效方式。触及实际 DB、JWT 或现役服务的动作仍须具体授权，本次不执行。不要用 `--password <秘密>` 命令行传值，避免进 shell 历史或进程参数。

凭据失效与同意公开含失效值的历史是两个问题。轮换不会删除历史；公开前必须核全部待推 refs，而不是仅比较两支命中同一旧值就称“不新增泄露”。[GitHub 官方处置说明](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)

### R4 中高：CI 既有调度误解，也有可预见的审计阻塞

候选 `.github/workflows/ci.yml` 对独立 `codex/*` push 不触发，但 `pull_request` 可在合并前运行；有冲突的 PR 不运行该事件的工作流。因此“合并前拿不到远端 CI”是错误的一般化结论，不应以先合并代替验收。

`workflow_dispatch` 的默认分支注册条件，不等于每次只检出默认分支；实际执行对象应核 run 的 ref/SHA 和 checkout。未实测不能承诺 dispatch 可用，也不能声称一定量不到候选。[GitHub 事件与执行对象说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)

当前工作流直接执行 runtime/dev 两轴 `pip-audit`。在册 JSON 仍有 15 个主 ID，工作流未配置经批准的例外策略。因此“接受 Chroma 两项”不会自动使 CI 绿；13 项迁移未落地也可能阻断当前 CI。保留原始审计红，不使用 `continue-on-error` 或缩范围凑绿。先落实安全修复；确需受限例外时须单独裁定范围、依据、到期/失效条件和门禁实现。

本次远端 API 查询未得到可用结果；`refs/closing/remote-master=985d53e4ee81efc066cc6915abcba98954e7d408` 只是本地保存的远端快照，不称当前远端真值或保护规则已核实。

### R5 中：D-33 不是可直接删除的死代码

`WAITING_USER→PLANNING` 免计步，但 `transition()` 仍执行 `_limit(next_steps, max_steps)`；schema 没有强制 steps 不超过 budgets。边界复现确认：steps 等于上限时可恢复，超过上限时仍抛 `BudgetExceeded`，两个恢复 catch 将其转为 `step_budget`。

推荐保留越界防御，文案指处理步骤、不指澄清次数；补恢复 API 的旧状态/预算下降负例。不要为了让某档“可达”把 `max_clarifications` 耗尽改成 409，也不删安全 catch。两者是不同业务计数器。此处本次只核验、修正文档，未改产品。

### R6 高、运行复现待补：D-34 应独立处理，不并入索引写守卫

源码确认 Agent 返回使用裸 `StreamingResponse`，快车道的占位补偿没有覆盖该路径；成功终稿的持久化发生在 Agent 服务执行阶段，早于返回 SSE。故取消/失败/追问与成功后的传输断开必须分开分析，不能只给该响应套一个关闭回调就称修复。

下一步先在合成库建立以下验收矩阵，再改共同最终化边界：

- 已提交用户输入后，Agent FAILED/STOPPED 或执行中断开：是否留下应有的结果/状态记录。
- WAITING_USER：这是合法追问，不得写“生成失败”占位；核追问展示与恢复历史。
- COMPLETED 已落终稿后，SSE 断开：不得再插占位、重复累计 message_count 或改写终稿。
- 技术 fallback：快车道最终化与 Agent 补偿不得双写。
- 拒绝/校验失败与 stale resume 409：未接受的新输入不得凭空落补偿。
- 清理重入、重发与恢复：按一次被接受的用户输入识别幂等，不只按 run_id（同一 run 可有多轮）。

这是公开行为与持久化一致性问题；不能自动放进“不阻塞质量”的列表。本次未在运行层复现所有分支，不声称已修复。建议独立 D-34 票，保护现有取消修复，避免与 D-14 数据写边界混改。

### R7 中：结果文件引用、时间和格式门记录不一致

逐文件读取得到：

| 原始文件（运行根 evidence 下） | 本次读取结果 |
|---|---|
| `final-gates-junit-20261011.xml` | tests 1942、skipped 10、failures/errors 0；timestamp `2026-10-11T05:39:17.609570+08:00` |
| `final-gates-backend-20261011.log` | 1932 passed、10 skipped、18 deselected；cov 86.37% |
| `final-gates2-junit-20261011.xml` | tests 1943、skipped 10、failures/errors 0；timestamp `2026-10-11T12:55:29.533041+08:00` |
| `final-gates2-backend-20261011.log` | 1933 passed、10 skipped、18 deselected；cov 86.38% |
| `final-gates2-static-20261011.log` | Ruff lint rc=0、format rc=1（test_cancel_boundaries.py）、mypy rc=0 |

1933/86.38 不能指向第一组文件，“07:3x”也不能无转换说明就代替 XML 的带时区时间。第二组格式红保留为历史事实；本次另行对当前候选做完整 Ruff lint/format 只读检查，均 rc=0（283 files），不能倒写旧日志。

10 条跳过逐项来源已读出：8 条因候选真实语料不可用，2 条未启用帧采集（FZ_DUMP_FRAMES、S6_DUMP_FRAMES）。空库读数来自原 XML，不是本次读取实际库。跳过不算通过，亦不把本轮测试称为所有能力均已覆盖。

### R8 中：整合票的数字与验收要求需改

本次静态树对照：候选 2712 路径，保存的远端快照 2136 路径，交集 2136，异 blob 99，快照独有 0，merge-base rc=1。未重新执行 merge-tree，不称本次复现了 99 个真实冲突。

D-20 的标题/出口不能要求固定 96 行；分组表 72+15+5+4+2=98，不能用于排工。裁决清单应覆盖本次实际差异、模式/路径变化和整合中发生的真实冲突，执行命令失败必须停止，不能把空 stdout 当“零差异”。

“最终门禁同数”也不能作为机械要求：合法新增测试会改变分母。应保持原必需病例不丢失，新增/删除/跳过有解释且语义门通过；计数是对账，不是验收目标。

## 3. 本次直接核验范围

使用 `candidate-envB/Scripts/ruff.exe` 对候选 backend 执行 `check --no-cache .`、`format --check --no-cache .`：rc=0。使用同环境 `python.exe -m pip check`：rc=0。不外推到宿主 `backend/venv`、Docker 或 CI。

使用同解释器 `-B -I -c` 仅导入纯状态合同与状态机，设置 max_steps=2，分别构造 WAITING_USER steps=2/3：输出 `AT_CAP_RESUME_ALLOWED`、`OVER_CAP_RESUME_REJECTED`，rc=0。未导入 main/rag_chain/数据库，也未读模型缓存。

XML/审计 JSON 使用 PowerShell 直接解析，报告的是既有运行结果，不是本次重跑 pytest。审计包内 distinct ID：core 6、openai 1、splitters 2、langsmith 4、chromadb 2；这是留存审计件的计数，不是最新漏洞数据库扫描。

未复跑：全量 pytest/mypy、前端构建/浏览器、模型、容器构建、依赖在线审计、凭据扫描、真实数据恢复、远端 CI。未读取真实库、历史裸值或现役配置值，未执行 reset_admin_password。

## 4. 推荐后续顺序（未自动授权执行）

1. **先对齐 D-34 独立修复范围**，在隔离候选补上述失败/恢复矩阵；D-33 保留越界防御，不改变澄清耗尽语义。
2. 已派发 D-3 迁移若仍在执行，先确认文件归属，禁止同时改 requirements、registry、retrieval、rag_chain；接收迁移结果后补双轴风险和共同集成测试，不能仅落两个 diff。
3. D-14 保持独立数据写入口票；D-6 仅私有开发环境/可回退范围，不伪装现役升级。F 在有效模型配置、公开 gold 与独立审查前置满足后再裁定开跑。
4. 更正后的 D-20 顺序用于私有整合准备；凭据失效、公开范围及所有推送前门禁满足后，才普通推独立分支、PR、CI、正常合并。
5. 真实库/专业审签/生产平台等仍不可替代的证据保持 BLOCKED；不执行部署，亦不把本报告当作这些动作的许可。

后续每项报告只写：对象 SHA/环境、实际命令与退出码、判据来源、遗漏/跳过、待裁项。不要新增通用验收平台，不重复编造一套台账；业务选择按纯文本 grilling 一次一个问题对齐。
