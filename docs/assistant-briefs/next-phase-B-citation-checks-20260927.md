# B｜引用冒烟判据

你是 B 助手。**只执行本文件**，完成后向交办人回报；不要接手 A/C/D/E。仓库绝对路径：`C:\Users\33393\Desktop\ai-legal-helper`。并行助手可能共享工作树；不要还原他人改动，不提交、不推送。

## 目标与文件归属

旧快速与全量引用冒烟只看条号，会把其他法律的相同条号误判为命中。把判据收紧到 `(法名, 条号)`，并保留历史 23/24 与离线 24/24 的原始口径。你独占写入：

- `backend/scripts/smoke_citation_fast.py`
- `backend/scripts/smoke_citation_full.py`
- 新建 `backend/tests/test_smoke_citation_assertions.py`
- `CONTRIBUTING.md`

证据见 `docs/assistant-briefs/verification-scope-review-findings-20260927.md`。不得改 `backend/retrieval.py`、语料、模型配置或 A/C/D 文件。`smoke_citation_full.py` 会调用答案生成模型，本任务**不实跑该脚本**；用户的模型调用授权仅覆盖后续 E 的 rerank。

## 执行

1. 阅读两个脚本的现有用例和检查逻辑，先用假检索结果/假回答做回归：正确条号配错误法名必须失败；正确法名和条号必须通过。新测试不能连接真实 Chroma 或模型。
2. 快速脚本的七个检索用例按 `(source, article)` 配对检查；用例若有两个可接受条文，保持“任中一条”的现有语义。全量脚本的十二个场景按明确法名配对：格式条款、交强险、定金为民法典；违法解除、经济补偿、试用期为劳动合同法；周末加班为劳动法；七天退货为消费者权益保护法。只判断引用组合，不增加主观法律评价或新依赖。
3. 更正 `CONTRIBUTING.md` 中快速门禁 24 项、全量 12 场景的旧计数，并写明后者有生成模型调用。不要改写旧运行成绩。
4. 在 `backend/` 运行 `venv\Scripts\python.exe -B -m pytest tests/test_smoke_citation_assertions.py -q`、`venv\Scripts\python.exe -m ruff check scripts/smoke_citation_fast.py scripts/smoke_citation_full.py tests/test_smoke_citation_assertions.py`、`venv\Scripts\python.exe -m ruff format --check` 并显式列出这三个文件。记录退出码；真实库上的新判据结果由 E 助手统一复验。

## 交付判据

错法名同条号不再误过，正例仍通过；脚本项数和贡献指南一致。回报 `B / 修改文件 / 新旧判据差异 / 命令与退出码 / 未解决项`。若需碰归属外文件，先报告交办人协调，不自行扩围。
