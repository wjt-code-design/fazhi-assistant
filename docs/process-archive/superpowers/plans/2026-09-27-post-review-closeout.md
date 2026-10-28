# 并行复核后的本地候选收口计划

> 执行前提：三份并行复核结果已返回。当前只规划，不执行代码修改、提交、推送、真实库写入或部署。

**Goal:** 结合三份独立复核，核实并收口当前 T1/T2 窄修复，给出可复验的本地候选结论和仍需 Owner 决策的阻断项。

**Architecture:** 先把并行复核当作待核证据而非结论，逐条与当前代码及工作区状态交叉核对；仅对确认且已获授权的缺陷作最小处理；所有改动完成后按当前 CI 形状验收。把凭据处置、法务签署、真实入库、远端推送和部署留在独立授权门外。

**Tech Stack:** Git、PowerShell、Python 3.11、pytest、Ruff、mypy、pip-audit、npm/Vitest。

## 全局约束

- 当前事实以 `docs/process-archive/progress-handoff-report-20260925.md` §9.11 和执行时重新采集的 Git 状态为准；旧计划 `docs/process-archive/superpowers/plans/2026-09-25-next-phase-local-candidate.md` 是过程记录，不把其中旧数字当现状。
- 三份派发简报 `docs/process-archive/assistant-briefs/version-safety-review.md`、`docs/process-archive/assistant-briefs/report-consistency-review.md`、`docs/process-archive/assistant-briefs/verification-scope-review.md` 是审查输入，不是审查结果。不得覆盖、改写或替代其他助手的交付物。
- 保留当前 5 个 `dispatch-output/` 跟踪文件修改及所有未跟踪文件；禁止 `git add -A`、批量清理或顺手格式化。当前已知的本轮修改候选为 9 个文件：
  `backend/knowledge_service.py`、`backend/law_versions.py`、`backend/scripts/import_laws.py`、
  `backend/tests/test_import_laws_preflight.py`、`backend/tests/test_knowledge_service.py`、
  `backend/tests/test_law_versions.py`、`backend/tests/test_time_unverified_note.py`、
  `docs/process-archive/h1-law-version-collision-tickets-20260926.md`、`docs/process-archive/progress-handoff-report-20260925.md`。
  执行时重新核对归属和差异，不以此清单覆盖新发生的并行修改。
- 本计划不授权 T3–T8、依赖升级、凭据轮换、风险接受签署、真实数据库写入、`git push` 或服务器部署。服务器尚未选定。
- 不运行 `backend/scripts/gen_r8_disposition.py`；不读取、回显或改写 `.env` 中的真实凭据。
- 若复核揭示超出 T1/T2 当前授权的代码或数据处置，先记录证据和影响，停在该项等 Owner 决策；同一缺陷连续三次修复失败则停止并重审判据。

---

## Task 1：接收并裁定三份并行复核

**Files:** 只读三份简报及其返回的复核产物；需要订正文档时只改 `docs/process-archive/progress-handoff-report-20260925.md`。

- [ ] 确认三份复核均已交付；未交付的那份标为“待回”，不猜测其结论，也不重复派同范围审查。
- [ ] 对每条实质主张，记录其代码/文档依据、当前 HEAD 下的复核证据、结论（成立 / 不成立 / 口径不同 / 未核）及影响。行号会漂移时以符号名和文件路径定位。
- [ ] 仅将已独立核实的更正写回进度报告；保留原证据边界，区分“本地离线配置”与“实际云端 rerank 调用”，不把 24/24 的离线烟测写成真实配置下召回已解决。

**完成判据：** 三份结果逐项有处置；未核项明确列出；报告不把“复核没提到”写成“已验证无问题”。

## Task 2：复核 T1/T2 工作区差异并处理授权门

**Files:** 上述 9 个候选文件；保留其余修改原样。

- [ ] 重新采集 `git rev-parse HEAD`、`git status --short -uno`、`git diff --name-only`；逐文件看候选差异和 `git diff --check`，确认并行改动没有被覆盖或混入。
- [ ] 对照三份复核及 §9.11，确认同版本识别、旧版区间保留、整批预检、批内冲突和测试开关恢复等行为。只补经复核确认且已授权的窄修复。
- [ ] 将两个已知但未获扩展授权的门单独列给 Owner 决定：`mypy scripts/import_laws.py` 的类型缺口（T5），以及 `pip-audit`/`uvicorn`/`pypdf` 风险及版本范围处置（T7）。未获授权时不改脚本或依赖，并在候选结论中保留阻断/例外。

**完成判据：** 9 个候选文件的来源、目的和差异均清楚；5 个 `dispatch-output/` 修改与所有未跟踪文件保持原样；超范围问题没有被悄悄纳入。

## Task 3：最终回归与隔离语料检查

**Files:** 按当前 `.github/workflows/ci.yml` 执行；候选数据仅读 `data/laws_extra.candidate-20260925.json`，Chroma 只用既有临时副本或新建隔离副本。

- [ ] 最后一处获准改动完成后，使用离线/假服务测试环境，运行后端 CI 同形检查：`ruff check .`、`ruff format --check .`、`mypy .`、`pytest --cov=. --cov-fail-under=70 -q -m 'not slow'`，以及 CI 中 `dispatch-output/agent-quality-20260911` 的 lint/format/守卫测试。
- [ ] 在 `frontend/` 运行 `npm run check` 与 `npm run build`。记录命令、退出码、通过/跳过/失败和警告，不沿用旧轮读数。
- [ ] 重跑 `pip-audit -r requirements.txt` 并如实保留结果；只有审计退出 0，或 Owner 已对当前依赖集合完成有效、未过期的风险处置，才可称依赖门已处理。签署由 Owner 完成，不能由脚本代签。
- [ ] 若复核后改动影响导入、时效或引用路径，在隔离库运行候选 `--validate-only`、`--dry-run` 和 `scripts/smoke_citation_fast.py`；报告中明确写“隔离副本 / 离线 embedding / rerank 关闭”。不向真实 `backend/chroma_db/`、`app.db` 或配额库写入。
- [ ] 若要验证当前启用的 SiliconFlow rerank，先由 Owner 确认允许实际外部模型调用及其成本；未确认就只报告“该路径未验”，不把本地 rerank 关闭时的结果外推。

**完成判据：** 与改动相关的回归和 CI 同形门禁均有本轮新读数；所有失败、跳过和未覆盖作用面均披露；隔离验证未触碰项目真实数据。

## Task 4：给出本地候选结论与后续审批清单

**Files:** 更新 `docs/process-archive/progress-handoff-report-20260925.md` §9.11 后续状态；不改动其他助手的交付物。

- [ ] 对以下外部/发布门逐项标明 Owner、前置证据和当前状态：独立法律复核；整批语料删除面复核及真实入库窗口；凭据轮换和按值反查；T5/T7 决策；远端历史/收益再评估；服务器选择与部署授权。
- [ ] 只有收到三份复核、完成本轮门禁并核清精确变更集后，才向 Owner 提交本地提交建议。暂不提交；如获准提交，只精确暂存审过的文件，不包含五个 `dispatch-output/` 修改或未知文件。
- [ ] 最终结论限于三态：①本地候选就绪但外部发布门未开；②代码已复核但语料/法务/依赖/凭据事项仍阻断；③门禁失败、候选未就绪。不得称为“法律质量获背书”“可推送”“可部署”或“已上线”。

**完成判据：** 汇报能从当前 HEAD 和命令复现；说明哪些工作明确没做；远端推送、真实数据写入及部署仍需单独授权。

## 方案自检

- **边界：** 将复核整合、窄修复、验收和发布授权分开，不把互不依赖的 T5/T7 或法务工作塞进 T1/T2 补丁。
- **替代方案：** 可立即并行改所有已知待办，但会把尚未复核的建议和未授权依赖/数据改动混在一起；本计划选“先收三份独立证据，再只修确认项”，改动面更小且可回滚。
- **历史教训：** 离线烟测不代理云端配置；隔离库预演不代理真实库验收；`mypy .` 不覆盖 `scripts/`；风险审计绿不等于凭据安全；不把旧计数或旧 HEAD 当当前事实。
- **DoD：** 以本轮命令退出码、复核处置覆盖面、精确文件差异和明确审批状态验收，不以测试数量或覆盖率单独代理法律正确性。
