# E｜四份交付后的集成、复验与精确提交

你是集成助手。**只执行本文件**；等 A、B、C、D 四名助手全部交付后再开始，不能与它们并行做全量测试、真实 rerank 或提交。仓库绝对路径：`C:\Users\33393\Desktop\ai-legal-helper`。本机服务器尚未选定，本任务没有部署、真实库入库、推送或历史改写授权。

## 输入与目标

读取四份交付报告及其实际工作区差异：

- `docs/process-archive/assistant-briefs/next-phase-A-docs-t7-20260927.md`
- `docs/process-archive/assistant-briefs/next-phase-B-citation-checks-20260927.md`
- `docs/process-archive/assistant-briefs/next-phase-C-version-write-20260927.md`
- `docs/process-archive/assistant-briefs/next-phase-D-import-types-20260927.md`

你是唯一可在四名助手交付后追加 `docs/process-archive/progress-handoff-report-20260925.md` 阶段验收段落、运行综合门禁并提交的助手。先用 `git status --short`、`git diff --name-only` 和每名助手的文件清单对账；当前工作树含至少五个既有 `dispatch-output/` 跟踪文件修改和大量未跟踪产物，不得批量暂存或清理。某助手说“已通过”只是待核结论。

## 集成步骤

1. 审阅 A–D 的差异、测试和文件归属。重复文件或未报告差异先追问对应助手；只接纳有现量证据的修改。B 的新 `(法名, 条号)` 判据执行后再评估召回，历史 23/24 与离线 24/24 分别保留原判据/配置标签。
2. 在 `backend/` 对 `data/laws_extra.candidate-20260925.json` 用绝对路径运行 `scripts/import_laws.py --validate-only`。在新建 `%TEMP%` 目录复制 `backend/chroma_db/`，将 `CHROMA_DIR`、`QUOTA_DB`、`DATABASE_URL` 均指向私有临时路径，`EMBEDDING_PROVIDER=local`、`RERANK_ENABLED=false`，在副本上 `--dry-run`。记录候选文件 SHA-256、替换/新增/跳过/警告与退出码。不得实跑导入到真实库；E7 五组多片段旧块不自动拼接或删除。
3. 用户已允许**真实 rerank** 调用。用同一隔离库副本及固定 24 项快速门禁，先只核对有效模型、端点、是否有 key（不打印 key）；确认一次成功的远端重排响应，再运行一次完整题集。设置私有 `QUOTA_DB`，记录每题实际 `(source, article)`、模型、成功/降级和退出码。若走本地 embedding 或其他配置与历史 23/24 不同，只报告本次结果；回退余弦排序不能算真实 rerank 成功。不要调用答案生成模型或 `smoke_citation_full.py`。
4. 根据 `.github/workflows/ci.yml` 运行后端 `ruff check .`、`ruff format --check .`、`mypy .`、`pytest --cov=. --cov-fail-under=70 -q -m 'not slow'`、`dispatch-output/agent-quality-20260911` 守卫，以及 `pip-audit -r requirements.txt`；前端运行 `npm run check` 和 `npm run build`。T5 还需直接检查 `scripts/import_laws.py`。保存每条命令的退出码；失败不能涂绿，只有新改动或失败风险才补跑。
5. 对比真实 `backend/chroma_db/chroma.sqlite3`、`backend/app.db`、配额库的前后路径与指纹，确认未被本阶段改动；只读取必要元数据，不回显敏感值。把本次 HEAD、候选哈希、门禁成绩、T7 仍存风险、真实 rerank 作用范围、剩余未提交内容归属写入 `docs/process-archive/progress-handoff-report-20260925.md` 的新阶段段落。
6. 用户已授权**精确文件分批提交**。逐文件或逐修改块审查 `git diff` 与 `git diff --cached`，必要时 `git add -p`；绝不使用 `git add -A`。提交只含已验收的同一任务文件及必要文档。每次提交后记 SHA、文件清单和剩余 `git status --short`；若提交树与测试工作树不同，补做受影响的验证。不推送。

## 最终判定与回报

给出以下一种结果并附证据：①本地候选就绪，但外部发布门未开；②阶段任务完成、候选仍被具体风险阻断；③门禁失败、候选未就绪。依赖审计、独立法律复核、凭据、真实入库、远端历史和服务器部署逐项写状态；测试绿不等于法律正确或可发布。回报 `E / 接收的 A–D 文件与证据 / 隔离语料和真实 rerank 结果 / 综合门禁 / 提交 SHA / 剩余阻断与未提交归属`。
