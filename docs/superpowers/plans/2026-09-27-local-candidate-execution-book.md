# 下一阶段本地候选执行书

> **For agentic workers:** 按分配的任务字母执行；并行阶段各助手只改自己的文件。集成者按本文的 E、F 阶段验收和提交。不要把本文件当作推送、真实库入库或部署授权。

**Goal:** 收口三份复核发现及当前未提交改动，形成可复验的本地候选结论，并准确列出尚未解除的阻断。

**Architecture:** 集成者先登记当前 Git 与工作区基线，然后把文件互不重叠的 A–D 派给四名助手并行完成。各助手仅做定向验证；集成者随后在隔离库复验候选语料和真实 rerank，运行综合门禁，审查差异并按精确文件提交。

**Tech Stack:** Windows PowerShell、Git、Python 3.11、pytest、Ruff、mypy、pip-audit、Next.js/Vitest、Chroma。

## 全局约束与现状

- 仓库：`C:\Users\33393\Desktop\ai-legal-helper`。写本文时分支为 `master`，HEAD 为 `7eda4bb`；**执行时重新取值**，不得沿用此 SHA 断言未漂移。
- 现有 17 个跟踪文件已修改，另有大量未跟踪产物；其中 5 个 `dispatch-output/` 跟踪文件修改属于既有现场。先看差异归属，不清理、不覆盖，不使用 `git add -A`。同一文件内不同任务的修改要按修改块审查和暂存。
- 复核输入：`dispatch-output/report-consistency-review-20260927.md`、`docs/assistant-briefs/verification-scope-review-findings-20260927.md`、`docs/assistant-briefs/version-safety-review-report-20260927.md` 及同目录 `version-safety-review-findings-20260927.md`。报告是待核证据，落笔前与当前代码及原始产物对照。
- 已有 W1 修复在工作区：`backend/schemas.py` 对**有条号**且缺生效日的管理端条文拒绝，`frontend/app/admin/sections/KnowledgeSection.tsx` 提示用户；无条号的一般知识仍可不填。先验收现状，不重写功能或清除历史重复块。
- `data/laws_extra.candidate-20260925.json` 是现有三条候选语料；只在隔离库验证。真实 `backend/chroma_db/`、`backend/app.db`、配额库均不得被本阶段写入。E7 的五组多片段／35 块不能自动拼接或删除。
- 用户允许本阶段受控调用真实 **rerank**；此授权不包含答案生成模型、真实入库、凭据轮换、`git push`、改写远端历史或服务器部署。服务器尚未选定。T7 只复核风险并写升级分案，不改依赖。
- 同一命令失败先分析原因，原样最多重试一次；同一 bug 连修三次仍不过则停止、复核判据。禁止密钥或用户数据进入终端输出、报告和 Git。
- 下文后端命令均从仓库的 `backend/` 目录执行，前端命令从 `frontend/` 执行；使用本仓 `backend/venv/Scripts/python.exe`，若该环境不存在，先报告环境缺失，不擅自重建或升级依赖。
- “阶段任务完成”与“本地候选通过”分别判定。依赖审计、法律复核、凭据及远端门未解除时，不把项目称为可发布或已上线。

## 0. 集成者开工检查（A–D 开始前）

- [ ] 在仓库根运行 `git rev-parse HEAD`、`git status --short`、`git diff --name-only`、`git diff --check`；记录输出时间与变更归属。只记录路径和摘要，不复制 `.env` 内容。
- [ ] 确认 A–D 的文件责任区没有其他会话正在写；如发生重叠，暂停冲突任务并由集成者重新分配，不让两名助手同时改同一文件。
- [ ] 把本执行书的**绝对路径和一个任务字母**交给每名助手。每名助手报告：修改文件、现量证据、测试命令与退出码、未解决问题；不提交、不推送。

## A. 文档对账与 T7 分案（可与 B/C/D 并行）

**独占文件：** `docs/h1-law-version-collision-tickets-20260926.md`、`docs/progress-handoff-report-20260925.md` 的既有历史段落；新建 `docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md`。进度报告在并行期仅 A 可写，A 交付后由集成者单独追加最终验收段落。

- [ ] 对照报告一致性复核的八项，逐项核实原始产物和当前代码。至少纠正 M1/M5 的 `newly_red=2`、quota 库路径与 mtime 口径、S0 代码块缺少的 `+`、批内重复限制的历史/现状区分、S0-c 的 47/48 时点差异、18 个出口、D20 工作树与历史提交轴、漂移行号。保留历史读数的时间戳，不把旧证据硬改成新结果。
- [ ] 复核 T7 当前声明范围、本机安装版本和 `pip-audit -r requirements.txt` 的现量结果；分别给 `pypdf`、FastAPI/Starlette、Chroma 写最小升级路径、兼容性验证、风险与回退条件。输出为**分案**，不修改 `requirements*.txt`、锁文件或环境。
- [ ] 更正文档中已证实的口径；把未核实主张标为未核，不凭复核报告代替原始证据。交付逐项对账表及审计命令/退出码。

**完成判据：** 八项均有“成立并更正／不成立及证据／尚未核实”结论；T7 三条路径各有可执行的后续步骤，依赖门的当前状态写清楚。

## B. 引用验收口径（可与 A/C/D 并行）

**独占文件：** `backend/scripts/smoke_citation_fast.py`、`backend/scripts/smoke_citation_full.py`、新建 `backend/tests/test_smoke_citation_assertions.py`、`CONTRIBUTING.md`。不要改检索实现或法条数据。

- [ ] 快速冒烟的七条检索用例逐条按 `(source, article)` 联合判断，避免“其他法律的同条号”误过；保留原有“多条期望任中一条”的用例语义。先用错法名同条号的受控假结果证明旧判据会误过、新判据会失败。
- [ ] 全量冒烟的正向与轻量案例补上对应法名，判断答案引用的**法名与条号组合**：格式条款/交强险/定金对应民法典，违法解除/经济补偿/试用期对应劳动合同法，周末加班对应劳动法，七天退货对应消费者权益保护法。只修改断言和用例数据，不扩大到法律语义评判；此脚本需要真实生成模型，本阶段**只做静态/模拟验证，不实调**。
- [ ] 更新 `CONTRIBUTING.md` 的当前快速门禁 24 项、全量 12 场景，并说明全量脚本涉及生成模型。不要因为加强断言而改写历史 23/24、24/24 读数。
- [ ] 运行 `venv\Scripts\python.exe -B -m pytest tests/test_smoke_citation_assertions.py -q` 和两脚本的 Ruff 检查；记录旧/新断言差异。真实库召回留给 E 阶段，避免多助手同时使用 Chroma。

**完成判据：** 错法名同条号不能通过；正例仍能通过；文档数量与脚本现量一致，真实生成模型未被本任务调用。

## C. 管理端日期与写侧失败可见性（可与 A/B/D 并行）

**独占文件：** `backend/knowledge_service.py`、`backend/tests/test_knowledge_service.py`、`backend/tests/test_phase5.py`。`backend/schemas.py`、`frontend/app/admin/sections/KnowledgeSection.tsx` 以及现有 W1 单测只读；发现缺陷先报告集成者协调归属。

- [ ] 核对 W1 现有表单、schema 与接口：有条号无生效日的请求应被拒绝，无条号一般知识仍可提交。利用现有隔离数据库测试夹具，在 `test_phase5.py` 增加一条接口回归，证明拒绝发生在写库前。不要重新设计日期字段。
- [ ] 对 `knowledge_service.py` 中版本判定的宽泛异常（当前 `stale_ids=[]` 分支）加一条能识别的结构化告警，保留旧块的安全行为；异常文本不得泄露正文或密钥。在 `test_knowledge_service.py` 注入判定失败，证明写侧仍保留旧块且有告警。
- [ ] 定向运行 `venv\Scripts\python.exe -B -m pytest tests/test_knowledge_service.py tests/test_phase5.py -q -m "not slow"` 及 Ruff。不要修改文件哈希重传或删旧块的其他异常分支，除非测试证明它们与本问题共享同一根因并先经集成者重新划定范围。

**完成判据：** W1 接口拒绝有测试；W2 失败路径不再静默，旧块不被误删。

## D. 导入脚本 T5 与 CI 可见的替换测试（可与 A/B/C 并行）

**独占文件：** `backend/scripts/import_laws.py`、`backend/tests/test_import_laws_preflight.py`。不改 `backend/pyproject.toml` 的全仓 mypy 排除，也不动真实语料。

- [ ] 先运行 `venv\Scripts\python.exe -m mypy --follow-imports=skip scripts/import_laws.py` 记录实际错误；按错误做最小类型修正（已知 `validate_entry` 的空列表推断），再用同一命令通过。若出现其他错误，记录来源，不为通过而整体关闭检查。
- [ ] 复用已有隔离 `tmp_collection` 夹具增加一条非 slow 回归：同一有日期版本重传后旧块被安全替换，且新块在；先验证该断言能抓住“删旧接线断开”的故障。补一条脚本 seed 冲突的 `--dry-run` 回归：报告跳过、无写入。不要用真实库运行。
- [ ] 运行 `test_import_laws_preflight.py -m "not slow"`、Ruff 和上述 mypy 定向门。`mypy .` 仍排除 `scripts/`，报告须把这两个检查分开写。

**完成判据：** T5 有定向绿灯；安全替换与 seed 分支在普通 CI 形状下可见；候选文件和真实库未写入。

## E. 集成者：隔离语料与真实 rerank 复验（A–D 合入工作区后）

- [ ] 审阅 A–D 的文件差异及测试证据；有交叉修改时先处理归属。先运行 B 的加强版引用断言。把旧 23/24、旧离线 24/24 标成**旧判据、旧配置**，新结果另列，不横向冒充。
- [ ] 从仓库根执行以下 PowerShell 预检，记录替换/新增/跳过/警告和候选文件 SHA-256。`$auditRoot` 是新目录；若要实跑导入，必须另建一个隔离副本。此块只做校验与 dry-run：

  ```powershell
  $candidate = (Resolve-Path -LiteralPath 'data/laws_extra.candidate-20260925.json').Path
  $realChroma = (Resolve-Path -LiteralPath 'backend/chroma_db').Path
  $auditRoot = Join-Path $env:TEMP ('ai-legal-candidate-' + [guid]::NewGuid().ToString('N'))
  $copyDir = Join-Path $auditRoot 'chroma'
  New-Item -ItemType Directory -Path $auditRoot | Out-Null
  Copy-Item -LiteralPath $realChroma -Destination $copyDir -Recurse -ErrorAction Stop
  if (!(Test-Path -LiteralPath (Join-Path $copyDir 'chroma.sqlite3'))) { throw 'Chroma 副本不完整' }
  $env:CHROMA_DIR = $copyDir
  $env:QUOTA_DB = Join-Path $auditRoot 'quota.sqlite'
  $env:DATABASE_URL = 'sqlite:///' + (Join-Path $auditRoot 'app.db').Replace('\', '/')
  $env:EMBEDDING_PROVIDER = 'local'
  $env:RERANK_ENABLED = 'false'
  Get-FileHash -Algorithm SHA256 -LiteralPath $candidate
  & .\backend\venv\Scripts\python.exe -B .\backend\scripts\import_laws.py --input $candidate --validate-only
  if ($LASTEXITCODE -ne 0) { throw '候选预检失败，停止 dry-run' }
  & .\backend\venv\Scripts\python.exe -B .\backend\scripts\import_laws.py --input $candidate --dry-run
  if ($LASTEXITCODE -ne 0) { throw '隔离副本 dry-run 失败' }
  ```
- [ ] 真实 rerank 复验只用脚本既有的 24 项快速门禁和固定题集。运行前核对有效的 `RERANK_ENABLED`、模型名、端点、`EMBEDDING_PROVIDER`，**只输出配置名与是否有 key，不输出 key 值**；把 `CHROMA_DIR`、`QUOTA_DB`、`DATABASE_URL` 指向私有临时路径。若使用本地 embedding，明确这与历史原配置是否相同。先单题确认发生了成功的远端 rerank 响应，再跑固定题集；限一次正式批次，失败先查因，不循环刷请求。
- [ ] 记录每题期望 `(source, article)`、实际召回、模型、成功/降级状态、退出码。远端失败后回退余弦排序的结果单列，不能算“真实 rerank 通过”；若历史配置或题集不可复原，结论只针对本次配置，不宣称关闭旧 23/24。

**完成判据：** 隔离库验证读数可复现；真实 rerank 的成功调用与结果分别可核；真实三个数据面前后指纹一致。没有调用 `smoke_citation_full.py` 或答案生成模型。

## F. 集成者：综合验收、提交与交接（E 后）

- [ ] 从当前 `.github/workflows/ci.yml` 逐项运行后端 `ruff check .`、`ruff format --check .`、`mypy .`、`pytest --cov=. --cov-fail-under=70 -q -m 'not slow'`、`dispatch-output/agent-quality-20260911` 的 lint/format/守卫测试、`pip-audit -r requirements.txt`；前端运行 `npm run check`、`npm run build`。统一记录命令、退出码、失败/跳过和环境。不要把 `pip-audit` 的非零结果涂绿。
- [ ] 审查 `git diff --check`、文件归属与精确暂存差异。只提交已验收且彼此依赖的文件；必要时 `git add -p`，不得 `git add -A`。每次提交后记录 SHA、`git show --stat`、剩余 `git status --short`；若提交内容不等于验收的工作区内容，应在提交树上补做相关验证。
- [ ] 由集成者单独在 `docs/progress-handoff-report-20260925.md` 追加本阶段结果：当前 HEAD、候选文件哈希、各门禁现量、T7 未解除风险、真实 rerank 适用范围、未提交文件归属、仍需法务/凭据/远端/真实入库/服务器决策的项目。报告和执行书可作为精确文件提交，但不得裹入未知产物。
- [ ] 给出三态之一：①本地候选就绪（列明外部发布门未开）；②本阶段工作完成，但候选仍被具体风险阻断；③验收失败，候选未就绪。每个结论都附未完成项和下一位负责人，不能以“全部测试绿”代替法律正确性或发布授权。

**完成判据：** 最终结论能绑定本次代码、命令和提交 SHA；工作区剩余改动有归属；未执行的动作明确列出。

## 并行安排与交付协议

0 完成后，A、B、C、D 可同时开始；它们的写入文件没有交集。每名助手只接受自己的字母，不碰其他任务文件，也不改本执行书。全量 pytest、Ruff 全仓、真实 rerank、语料副本导入和 Git 提交由集成者在 E/F 串行执行，以免并行写库、共享配额或把半成品测试成最终结果。

四名助手回报使用同一格式：`任务字母 / 改动文件 / 原问题与证据 / 定向命令及退出码 / 未解决项`。集成者有权因现量代码与报告不符而缩小任务；扩大文件范围或触碰另一个助手的文件前，先重新分配。提交后仍不推送；远端历史衔接、真实语料入库、凭据轮换、独立法律复核及部署均属后续单独决策。
