# 派单：测试覆盖与验证边界复核

你负责“验证覆盖复核”这一项。项目根目录：`C:\Users\33393\Desktop\ai-legal-helper`。

## 目标

只读检查 T1/T2 与 S0-c 窄修复的测试能否抓住对应回归，并核对引用冒烟结果的适用范围。工作区包含未提交修改；以当前实现、当前测试和最新报告为准。

## 负责文件

- `backend/tests/test_law_versions.py`
- `backend/tests/test_import_laws_preflight.py`
- `backend/tests/test_knowledge_service.py`
- `backend/tests/test_time_unverified_note.py`
- `backend/scripts/smoke_citation_fast.py`
- `CONTRIBUTING.md`

可只读查看相应生产代码和 `backend/tests/conftest.py`，确认隔离边界。重点检查：完整正文误删、空日期/ID、`seed`、日期区间与批内冲突、写入路径是否保留旧块、设置值是否在异常时恢复，以及冒烟脚本是否验证法名和条号。

## 边界

- 不编辑或还原文件；其他助手在同一工作区继续集成。
- 需要运行测试时仅运行相关定向用例，确认数据库和向量库使用临时隔离环境。
- 不调用真实模型、云重排服务，不写真实数据库，不部署或推送。
- 不因一次本地冒烟通过就宣称真实配置问题已解决；区分脚本现有断言与完整验收。

## 交付格式

列出覆盖充分的关键判据、最多三条必要缺口，以及每条缺口的最小测试建议；给出相关文件绝对路径和行号。数字附运行命令、退出码和隔离条件。没有缺口时明确说明验证边界，不扩大到无关测试重构。
