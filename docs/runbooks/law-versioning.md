# 法律版本与时效维护

## 数据规则

- 一条法律版本由 `title + article_number + effective_from` 唯一识别；修改生效日即产生新版本。
- 同版本的文本勘误会替换旧片段，并更新 `source_document_sha256`，不会制造重叠版本。
- `effective_from` 晚于咨询基准日，或 `effective_to` 早于咨询基准日的版本不得进入回答。
- `已废止` 版本在其历史有效期内仍可用于历史问题；缺少 `effective_to` 时按不可用处理。
- `即将施行`、`未生效` 缺少 `effective_from` 时按不可用处理。

## 更新流程

1. 只从权威发布页取得正文，记录 HTTPS `source_url`、公布日、生效日及复核日。
2. 复制 `data/laws_extra.example.json` 为 `data/laws_extra.json`，填写新版本；旧版本补上 `effective_to` 和 `supersedes_version_id`。
3. 在 `backend` 目录运行 `python scripts/import_laws.py --dry-run`，确认替换数量与版本边界。
4. 去掉 `--dry-run` 导入，并用一个生效日前日期和一个生效后日期各做一次检索验收。
5. 保留旧版本，不直接覆盖或删除；仅同一版本的录入勘误允许替换。

建议每月检查一次全国人大、国务院及目标业务主管部门的官方更新；发现修法公告时立即执行上述流程。系统只能保证“按已入库版本正确选取”，不能凭模型自动证明法律库已经是最新，因此回答应展示来源与版本信息，未完成来源复核的内容不得宣称为最新法律依据。
