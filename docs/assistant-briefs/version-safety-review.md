# 派单：法律版本替换安全复核

你负责“版本安全复核”这一项。项目根目录：`C:\Users\33393\Desktop\ai-legal-helper`。

## 目标

只读复核当前工作区的 T1/T2 修复，判断还有没有可能误删法律片段、错误允许冲突版本，或把安全历史版本误拦。工作区包含尚未提交的修改；以当前文件和 `git diff` 为准，不把旧报告中的规则当成当前实现。

## 负责文件

- `backend/law_versions.py`
- `backend/knowledge_service.py`
- `backend/scripts/import_laws.py`
- 相关测试：`backend/tests/test_law_versions.py`、`backend/tests/test_import_laws_preflight.py`、`backend/tests/test_knowledge_service.py`
- 为确认可达路径，可只读查看 `backend/chunking.py`、`backend/knowledge_base.py` 和输入校验代码。

重点核对版本 ID 与空日期、`seed` 来源保护、旧正文前缀和完整性、`effective_from/effective_to` 区间边界、同批多条目的预检、长条文切片后的行为。

## 边界

- 只审查并报告，不编辑或还原任何文件；同一工作区有其他助手在处理改动。
- 不写入真实知识库，不调用模型或云服务。需要复现时只用纯函数、临时文件或临时数据库。
- 不扩展到 T3–T8、部署、推送或无关重构。

## 交付格式

按严重程度列出确证问题，每项给出：文件绝对路径和行号、触发条件、实际与预期行为、复现证据、最小修复建议。没有新问题时明确写“未发现新的确证问题”，并列出仍需人工处理的限制。不要重复已由当前测试覆盖且已修复的问题。
