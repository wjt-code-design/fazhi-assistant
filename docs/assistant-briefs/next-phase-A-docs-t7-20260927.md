# A｜报告对账与 T7 依赖分案

你是 A 助手。**只执行本文件**，完成后向交办人回报；不要接手 B/C/D/E。仓库绝对路径：`C:\Users\33393\Desktop\ai-legal-helper`。并行助手可能在同一工作树工作，保留所有现有修改，不还原、不清理、不提交、不推送。

## 目标与边界

把 2026-09-27 的报告一致性问题核实并更正；为依赖风险写可执行的升级分案。当前 HEAD 曾为 `7eda4bb`，执行时重新取值。T7 本轮**不升级依赖、不改环境**；服务器未选，不部署。

你独占写入：

- `docs/h1-law-version-collision-tickets-20260926.md`
- `docs/progress-handoff-report-20260925.md` 的历史证据段落；最终阶段验收段落留给 E 助手追加
- 新建 `docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md`

只读证据：`dispatch-output/report-consistency-review-20260927.md`、`dispatch-output/t2-preflight-report-20260926/mutation-verdicts.json`、`docs/assistant-briefs/version-safety-review-findings-20260927.md`、`backend/requirements.txt`、`.github/workflows/ci.yml`。不打开或输出 `.env` 中的值。

## 执行

1. 在仓库根记录 `git rev-parse HEAD`、以上两个旧文档的 `git diff`。复核报告中的八项，不直接照抄结论：M1/M5 产物的 `newly_red=2`；quota 同名库的路径与 mtime；S0 代码块的缺失 `+`；批内重复的历史限制与现状；S0-c 产物 47 与现量 48 的时点；18 个出口；D20 的工作树与历史提交两条轴；漂移行号。旧数字若有历史意义，标时点并保留，不伪装成当前值。
2. 在 `backend/` 下运行 `venv\Scripts\python.exe -m pip_audit -r requirements.txt`（若模块入口不可用，改用已安装的 `pip-audit -r requirements.txt`，先说明原因）。记录退出码、受影响包、声明版本范围和本机实装版本；不要将审计失败改写成通过。
3. 新建 T7 分案，分别覆盖 `pypdf`、FastAPI/Starlette、Chroma：当前风险与证据、最小升级候选、与现有上限的冲突、必须跑的兼容性检查、失败时如何回退。若现量事实无法核实，写“未核”，不要编造安全版本或修改 `requirements*.txt`。
4. 对两份旧文档只改经核实的口径。运行 `git diff --check` 和 `git diff --` 精确文件；确认没有覆盖别的助手新增的最终验收记录。

## 交付判据

八项各有“更正／不成立及证据／未核”结论；T7 三条升级路径能供后续独立任务执行。回报 `A / 修改文件 / 八项结论 / 审计命令与退出码 / 未解决项`。无代码、依赖或真实数据修改。
