# GATE PASSED — allowed=true（v2 政策，预注册单题容差）→ 进入阶段 H 恢复演练

## Boundary
- Release ID: `legal-agent-v1-20260905-009`
- Git revision: `30a865f76b371e25b4fe90e82fdbd8b373a77b45`（政策 v2 + 容差定位，用户批准）
- Backend image: `sha256:a47427149525ad143752e9d581a44d58b38b3cb3279aaab2f8eb25749a68a721`（tag `:009`）
- Case-set: `86066616…`（v1.2 混合 30 题，与 006-008 相同）
- Manifest: `ab2a7f01b1fdcf8046c301fdc966b61e36ee94f3c0242d0bf0f09e2b0ce05e9e`
- Policy: v2（complex_task_quality 容差 = 1/30 单题；safety = 0）
- Reviewer: 执行者本人（用户改派，豁免披露延续）

## 采集与结果
- 双路径 60/60 OK（RAG 零路由零失败；Agent 6/30 路由、零失败——分解器围栏修复后
  首个零分解失败的采集周期）
- 指标：rag quality 0.6167（0.617/0.617），agent 0.5833（0.533/0.50）
  ——差距恰为 1/30=0.0333，按预注册比较式（agent < rag − 1/30 才失败）判定为持平
- clar_prec：rag 1.0（空集默认，不参与比较）/ agent **0.3333**（6 问 2 中）
  【更正 2026-09-07：本文件初版误写 0.75，实际值以 agent-report.json 为准】
- 安全项双方全 0
- 门禁（release-check-20260907.json）：**allowed=true, reasons=[]**

## 政策依据
v2 政策（docs/release-policy-v2-rationale.md，数据所有者批准）：Agent=诚实/安全
升级件；质量与 RAG 持平（单题容差内）即可发布；采样波动（实测 0.011）不单独触发回滚。
本候选恰好落在容差边界（差 1 题）——按预注册比较式判定，未做任何事后调整。

## 采集过程诚实记录（v2 更正：叙述与归档目录逐一对齐）
RAG 共 6 次尝试（5 次运行 + 1 次配给失败）：
- attempt1-crashed：第 24 题分块传输中断（IncompleteRead 非 OSError 子类）击穿
  重试循环 → capture_eval 已修（补 http.client.HTTPException）
- attempt2-agent-contaminated：后台命令 cwd 漂移 → RAG 跑在 Agent-ON 容器
  （6 题被路由，rows.json 实证）
- attempt3（配给失败，无采集产物）：再次 cwd 漂移 → 启动脚本读到 backend/.env，
  容器无 DASHSCOPE/SILICONFLOW key（capabilities false 实证）→ 启动脚本已改
  绝对路径读根 .env
- attempt4-empty-index：docker cp 的 MSYS 路径转换把索引写进嵌套路径
  （/app/chroma_db/chroma_db/ 实证）→ 播种方式重构为辅助容器直写卷
- attempt5-agent-contaminated：只 restart 未重建容器（脚本翻转不影响已建容器
  env）→ RAG 再跑在 Agent-ON 容器（6 题被路由）
- **attempt6（最终）：保卷重建 Agent-off 容器，30/30 零路由零失败 ✓**
Agent 共 2 次尝试：attempt1-empty-index（同 attempt4 空索引因）→
attempt2（最终，播种法+容器内计数预验证）✓
系统性根因（后台任务 + 相对路径 cwd 漂移 ×3）已通过 launch 脚本绝对路径与
全部命令绝对路径修复。

## 下一步
阶段 H：隔离恢复演练 + 四场景（backup_data.py 工具链 + 隔离卷，不碰生产）。
