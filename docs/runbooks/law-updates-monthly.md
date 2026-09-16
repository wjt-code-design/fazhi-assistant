# 法律知识月度治理程序（阶段 I 交付，2026-09-06）

本文档是 `docs/runbooks/law-versioning.md` 的月度运营补充，不另造导入体系。

## 月度定检流程（每月第一个工作日，责任人：知识库管理员）

1. **官方来源巡检**：全国人大（npc.gov.cn）、国务院（gov.cn）及主管部门官网，
   核对题集覆盖法律清单是否有新公布/修订/废止/司法解释。
2. **发现变化时**（事件触发，不等月度）：
   - 用 `backend/scripts/import_laws.py --dry-run` 预检（重复/日期倒置/空正文/来源域名）；
   - 人工审核 dry-run 输出后正式导入；
   - `backend/scripts/verify_new_law.py` 验证新法版本选择（生效日前/后各一题）；
   - 重建索引后用 `backend/scripts/recompute_boundary_manifests.py verify` 核对边界；
   - 记录 `source_url/文号/公布日/生效日/失效日/复核日/批次/内容 hash` 入知识库元数据。
3. **工具运行环境**：`backfill_time_meta.py` / `verify_new_law.py` 依赖完整运行时
   （rag_chain/vectorstore + key），在 backend 运行环境或容器内执行，裸主机直跑会因
   缺运行时上下文报 ImportError——这是预期行为，不是缺陷。
4. **自动化边界**：自动监测只能"发现候选更新并报警"（输出差异报告），任何写入
   生产知识库的动作必须人工审核后执行。

## 已有验收证据

- 版本选择机制：`backend/tests/test_law_versions.py`（全量套件内，2026-09-06 前后
  日期选择路径覆盖，绿色）。
- 生效日前后验收：候选 004/005 评测题 `law-date-conflict-15`（民法典/立法法时间
  效力场景）连续两个采集周期行为一致。
- 索引完整性：`diag/frozen-index-004/`、`diag/frozen-index-005/` 快照与各自
  index-manifest 逐字节一致（2026-09-06 验证）。

## 已知限制

- 自动巡检脚本未建（当前为人工月检 + 事件触发）；若建，仅到"报警"为止。
- `law_as_of=2026-08-01` 的逐条人工复核状态仍以数据所有者确认入库日为准，
  未做全量逐条复核（交接原样保留）。
