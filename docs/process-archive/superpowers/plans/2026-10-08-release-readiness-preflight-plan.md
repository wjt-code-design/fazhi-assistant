# 下一阶段：发布就绪预检执行书

> **For agentic workers:** 使用 `executing-plans` 按任务执行；需要多助手时先明确只读输入和各自输出责任，不让多个会话同时改主仓。复选框用于执行跟踪，不因文档生成而勾选通过。

**Goal:** 在本地主仓整合验收之后，形成可供用户决策的剩余修改、风险和发布前置材料；本阶段不发布。

**Architecture:** 保留现有应用及单 worker 运行边界，复用已取得的证据；仅做只读核对、轻量官方资料复核和独立目录内的文档准备，不新增框架或提前实施升级。

**Tech Stack:** Windows / PowerShell、Git、Python 3.11、FastAPI、SQLite / Chroma、Next.js；正式部署平台尚未选定。

## Global Constraints

- 主仓：`C:/Users/33393/Desktop/ai-legal-helper`。本轮已批准本地整合与提交，**不代表已接受全部依赖风险或批准发布**。
- 上一阶段隔离根：`C:/Users/33393/Desktop/fazhi-main-integration-20261007`，其源码、工具、清单和证据只读。旧候选 `C:/Users/33393/Desktop/fazhi-closeout-auditfix-20261007` 也只读。
- 只读解释器：`C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe`。不安装、卸载或更新共享 venv，不调用可能加载真实配置的产品导入入口。
- 不 stage/commit/merge/push/PR，不触发远端 CI；不调用真实 LLM、Agent、rerank，不下载权重/wheel，不升依赖，不写真实库，不备份/迁移/部署。后续实际动作逐项另获授权。
- 不读取真实 `.env`、数据库、私有语料或凭据值；只引用既有脱敏扫描结论。当前扫描不证明 Git 历史、编码凭据或其他密钥安全；扩大扫描范围须先说明并确认。
- 不动原有 3021 服务；不启动验收服务，不杀其他会话进程，不清理已有未跟踪产物。执行前确认是否有并行写主仓任务；发现输入漂移，保存差异并暂停依赖该输入的工作。
- 决策不确定时用 `grilling` 和中文纯文本对齐，禁止选择弹窗。重命令失败先分析，不循环重试；同一命令最多原样重试一次，同一 bug 连修三次仍失败即停下。
- 按 Ponytail：先判断是否需要，再复用已有材料和标准工具。没有代码修补任务，不顺手重构或造通用发布平台；不得削减安全、输入校验或数据保护。

## 起点与正确结论

上一阶段起点 HEAD 为 `902e2d161e67100ed6d267a08c393538a0abe109`。最终本地提交编号应从隔离根 `evidence/delivery-closure.json` 的 `commit` 字段读取并用 Git 核对，**不能把旧起点当最终提交，也不能猜编号**。若该封口文件不存在、`local_commit_complete` 不为 true 或提交未完成，停止进入本计划，回报上一阶段尚未闭合。

已取得的技术证据（限定 2026-10-08 本轮输入）：

- `evidence/staged-backend-full-04/`：1852 通过、10 跳过、18 slow 排除，退出 0，综合覆盖率 86.11%。执行集合核对见 `backend-execution-set-check-v3.json`。
- `green-turn-final-01/`：33 项真实 SQLite/事件控制的持久化定向通过；`turn-mechanisms-02/`：42 项取消机制通过；`green-scanner-archive-02.json/.log`：125 项及 3 subtests 通过。
- `evidence/round-11/final-verification.json`：`bounded_integration_pass=true`；380 源文件、53 工具、18 公开种子绑定，两 API/四 Edge 取消、严格消息配对与计数、实际摘要和自然退出通过。
- `evidence/shutdown-control-13/result.json`：原生退出 0、自然停止、无额外 SDK 关闭干预；收尾后 async/sync SDK 打开数均为 0。
- 需求/工程双轴复核为 0 个已确认阻断，范围和限制见 `reports/a-boundary-independent-review-20261008.md`。是同工具链/仓库中的不同子会话只读复核，不是外部认证。

这只证明受限本地稳定性/接线验收；不是法律答案质量、安全风险清零、多 worker 保证或部署包可上线。10 项 skip 和 slow 未验范围保持可见；Windows standalone 复制 EPERM 警告未被构建退出 0 消除。此前真实 rerank 的历史证据存在，但没有迁移为本轮真实模型验收，也不要重新断言“key 未配置”。

## 输出目录与顺序

只在新建的独立目录写四份交付材料。按以下命令生成唯一目录，并把返回的完整路径记进结果；后续命令继续使用同一个 `$nextPrepRoot`（新 shell 中重新赋为已记录的实际路径，不重新生成目录），不得替换系统变量：

```powershell
$nextPrepRoot = 'C:/Users/33393/Desktop/fazhi-release-preflight-' + (Get-Date -Format 'yyyyMMdd') + '-' + [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Path $nextPrepRoot -ErrorAction Stop
New-Item -ItemType Directory -Path ($nextPrepRoot + '/reports') -ErrorAction Stop
```

使用 `apply_patch` 创建该目录下文件，不往主仓回填本执行书或进度。执行顺序 A → B/C → D；默认单助手，B/C 仅在用户要求并行且输出分开时并行。任何候选不复制 `.git`、真实配置、数据库或整份依赖目录。

## A. 核实封口起点

**输入：** 主仓 Git、上一阶段 delivery-closure/final-verification/final-scan/保护及 index 证明。
**输出：** `$nextPrepRoot/reports/baseline-check.md`；D 使用其中已验证提交与限制。

- [ ] 只读查看 HEAD、分支和 tracked 差异，不枚举大量未跟踪产物：

```powershell
git -C C:/Users/33393/Desktop/ai-legal-helper rev-parse HEAD
git -C C:/Users/33393/Desktop/ai-legal-helper branch --show-current
git -C C:/Users/33393/Desktop/ai-legal-helper status --short --untracked-files=no
Get-Content C:/Users/33393/Desktop/fazhi-main-integration-20261007/evidence/delivery-closure.json -Raw
```

- [ ] HEAD 必须等于封口中记录的本地提交，分支为 master，暂存区为空；差异应只有下面六处原有修改。若不是，列出实际差异并停止据旧基线作后续结论；不要 reset/stash/覆盖。
- [ ] 读取 `round-11/final-verification.json`、`delivery-final-scan.json`、`main-index-and-residual-proof-round-10.json`，核对总门、扫描适用范围及六处保护结论。最后一项保留其原文件名；其 380 路径与最终源码清单相同，最终绑定由 delivery-closure 再确认。数字从原始材料转录，缺文件或相互矛盾记未闭合，不补写 true。
- [ ] 不再次调用会写独占标签的 `verify_final.py round-11`、扫描器或 freeze 命令；本任务读已封口结果，不重用运行编号。旧 round-09 存储失败、旧最终扫描归档正控未分类的退出 1 原样保留；最新 scanner 只分类原冻结 bytes/SHA 一致的明确正控，不能忽略未知命中。

**A 门：** 提交/门禁/工作区三者一致，或者准确阻塞报告；没有一致起点不得继续 B/C/D 的候选裁定。

## B. 原有六处修改处置建议（只审不提交）

**输入：** A 的基线与以下六个当前 residual diff。
**输出：** `$nextPrepRoot/reports/residual-changes-review.md`。

1. `docs/process-archive/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md`
2. `frontend/app/admin/sections/KnowledgeSection.tsx`
3. `frontend/app/admin/sections/UploadSection.tsx`
4. `frontend/app/chat/page.tsx`
5. `frontend/app/globals.css`
6. `frontend/components/chat/InputBar.tsx`

- [ ] 用 `git diff -- <这六个明确路径>` 阅读变更，记录每个文件的实际目的、是否影响运行、已有什么验证、还缺哪一项最小验证。文件大时用 rg 定位相关区段，不读历史产物整树。
- [ ] 重叠两文件已整合本轮停止功能；只审剩余图片能力校验及移动布局差异，不能重新把取消接线列成未提交。现有 working-view 83 项测试/类型/构建通过仅作为历史保护证据，不当作本轮新审阅的全功能保证。
- [ ] 每个文件给“建议保留待验证”或“满足哪些具体证据后可另批提交”的建议；不要替用户删除、暂存或提交。没有可确认缺陷不新增重构任务。

**B 门：** 六路径逐一有结论和证据缺口，额外文件不混入；实际处置由用户另作选择。

## C. 当前对象的安全/依赖/模型来源风险复核与分案

**输入：** A 的提交、`backend/requirements.txt`、只读解释器实装元数据，以及主仓以下历史文档：

- `docs/process-archive/local-candidate-decision-20261003.md`
- `docs/process-archive/superpowers/plans/2026-10-03-dependency-risk-followup.md`
- `docs/process-archive/superpowers/plans/2026-10-04-remaining-dependency-preflight.md`
- `docs/process-archive/chroma-risk-triage-20261003.md`

**输出：** `$nextPrepRoot/reports/risk-followup.md`；仅复核和分案，不签署风险接受。

- [ ] 读取实际声明并用纯元数据列出当前解释器分发；不要 import main/模型，不把不同环境的扫描合成“当前已清零”：

```powershell
Get-Content C:/Users/33393/Desktop/ai-legal-helper/backend/requirements.txt
& 'C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe' -I -B -c "import importlib.metadata as m,json;print(json.dumps(sorted([(d.metadata['Name'],d.version) for d in m.distributions()]),ensure_ascii=False))"
```

- [ ] 分开记录每条通报/来源问题的适用包与版本、历史审计对象、当前调用面、已知隔离措施、缺失证据和建议下一步。旧裁定中的 2026-10-05 日期已过去，不能自动续期，也不能把本轮本地提交授权解释为续签。
- [ ] 需要新的安全事实时，只查官方公告、发行记录、精确版本元数据/源码，并保存 URL/取得时间/原始公开响应。历史数字注明日期；不凭空认定最新修复版本，不把 `vulnerabilities=[]`、CPU 运行或扫描跳过等同风险消除。
- [ ] 保留 Chroma ↔ 适配包 ↔ LangChain/SDK 的真实联动、模型链信任门和来源 PARTIAL；禁止只换 core、`--no-deps` 凑兼容、开启未知 `trust_remote_code` 或借升级关闭未补证的来源问题。
- [ ] 每一分案写精确修改责任、必须先满足的版本/来源证据、最小隔离验证及停止条件。没有已证实的目标/闭包，就交付“未关闭及所缺条件”，停止该案安装准备，不无限试版本。

**C 门：** 风险与真实对象一一对应，所有未关闭/未审计项可见，升级或受限风险接受各有独立请求；不产生伪“安全通过”。

## D. 汇总发布前置与下一项授权请求

**输入：** A/B/C 结果、主仓现有 CI/运行/部署说明（先用 `rg --files .github docs` 定位实际文件，不假定不存在的部署配置）。
**输出：** `$nextPrepRoot/reports/results.md`，自包含汇总并引用前三份绝对路径。

- [ ] 写清已完成的本地阶段、仍未提交的原有修改、剩余风险，以及以下下一阶段的验收门：真实模型/法律质量、目标平台构建包、远端历史与凭据复扫/CI、真实库恢复与部署。
- [ ] 真实模型分案列角色/端点、公开样本与独立法律 gold、缓存隔离、调用次数/费用上限、脱敏证据及成功/停止判据；历史 rerank 不重复跑来充进度，真实 LLM 结果不得由同一个模型自评充当独立验证。本计划不执行任何调用。
- [ ] Windows 构建 EPERM 与 Linux/目标平台打包单列，不能让本机退出 0 代替完整依赖复制或目标平台 smoke。平台/服务器未选时记“未进入”，只列必需输入，不虚构 IP、域名或系统。
- [ ] 远端 push/CI、扩大历史凭据扫描、真实库备份及恢复验证、迁移/回滚、TLS/监控均是另批执行分支。本轮不 fetch/push/触发 CI，不读取真实库来补证。
- [ ] 最后只推荐一个下一步动作及其边界，优先最小未闭合风险分案或必要验证，不一次申请所有发布权限。若建议升级，先提供已核查的精确闭包和隔离实验方案；若无可靠安全目标，则提出具体受限用途的 Owner 裁定，不代签。

**D 门：** 四份报告能独立阅读，路径/证据/范围/责任/停止条件明确。结论最多是“预检材料就绪”，不是“项目已可上线”。

## 自审与交付

- [ ] 逐项核对 A/B/C/D，没有借历史通过代替新证据，没有把未执行门勾成通过。
- [ ] 确认主仓源码/暂存区、真实配置/库、共享环境、旧证据、服务未被修改；不把输入保护扩大成全 venv 逐字节证明。
- [ ] 检查报告无凭据值/片段、无猜测版本/预算、无默认发布权限；对未执行项注明原因及推进条件。
- [ ] 向用户交付 `$nextPrepRoot/reports/results.md` 的实际完整路径、主要缺口及一个推荐授权请求。遇到需扩围的行为暂停相关分支，通过纯文本 grilling 对齐。

本执行书已由编写者自复核：当前整合与未来发布边界分开；四任务仅有文档输出、不包含未经定义的代码步骤；旧失败和受限结论没有被新全量覆盖；不要求未选定服务器来完成本地预检。执行助手仍须按实际起点重核，不能凭本文件替用户签署风险。
