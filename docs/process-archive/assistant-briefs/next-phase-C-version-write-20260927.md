# C｜管理端日期验收与版本判定异常

你是 C 助手。**只执行本文件**，完成后向交办人回报；不要接手 A/B/D/E。仓库绝对路径：`C:\Users\33393\Desktop\ai-legal-helper`。工作树已有大量未提交修改，其他助手可能同时工作；不还原、不清理、不提交、不推送。

## 目标与文件归属

W1 已在当前工作区实现：有条号的管理端条文缺生效日时，`backend/schemas.py` 拒绝，`frontend/app/admin/sections/KnowledgeSection.tsx` 提示；一般知识无条号仍允许不填。你的工作是验证接口确实先拒绝再写库。W2 是 `backend/knowledge_service.py` 版本判断异常被 `except Exception: stale_ids=[]` 静默吞掉，须保留旧块并记录可定位告警。

你独占写入 `backend/knowledge_service.py`、`backend/tests/test_knowledge_service.py`、`backend/tests/test_phase5.py`。`backend/schemas.py`、上述前端文件及 `backend/tests/test_law_versions.py` 只读；如 W1 原实现有缺陷，先报告交办人重新分配文件。

## 执行

1. 阅读 `docs/process-archive/assistant-briefs/version-safety-review-findings-20260927.md` 的 W1/W2 证据和当前代码。现有 W1 schema 单测已覆盖有/无条号；在 `test_phase5.py` 利用其隔离数据库及 Chroma 夹具增加一条管理端 API 回归，断言有条号无日期返回校验错误、没有新增知识块；一般知识边界不变。
2. 在 `test_knowledge_service.py` 注入 `replaceable_version_ids` 或对应判定依赖抛错，先证明现状无告警，再在判定异常处加入一条结构化 `warning`，带有限的错误类型/上下文，不记录条文正文或密钥。原有 `stale_ids=[]` 安全行为要保留：写入成功时旧块仍在，不发生误删。
3. 不顺手改 `file_hash` 查找或删旧时的其他异常分支；若发现同根因，给出证据后由交办人决定范围。
4. 在 `backend/` 运行 `venv\Scripts\python.exe -B -m pytest tests/test_knowledge_service.py tests/test_phase5.py -q -m "not slow"`，以及三个归属 Python 文件的 Ruff lint/format 检查。记录命令与退出码。测试必须用项目隔离夹具，不接触真实库。

## 交付判据

W1 接口拒绝有可运行回归；W2 失败既可见又不会误删旧块。回报 `C / 修改文件 / 前后行为 / 命令与退出码 / 未解决项`。
