# 阶段 H 恢复演练记录（候选 009，2026-09-07，操作者=执行者[用户改派豁免披露]）

## H-1 备份
docker cp 候选容器 /data/app.db + /data/quota_used.sqlite + /app/chroma_db
→ diag/drill-h-009/backup/（备份完成）

## H-2 空目录恢复
→ diag/drill-h-009/restore/（恢复完成）

## H-3 三重验证（备份 vs 恢复 逐项一致）
- SQLite 记录数：users 2 / conversations 60 / messages 114 / qa_candidates 8 / analysis_runs 0 = 一致
- chroma 计数：legal_provisions_cos 10266 / qa_pairs 279 / te4 两组 21/10266 = 一致
- 最小功能读取：恢复库会话可读、法条记录可取（id 0024a83b…）

## H-4 回滚演练
009 容器停止 → :007 前一镜像启动 → healthz 全绿 → 恢复 :009 → healthz 全绿
（回滚路径可用，镜像标签切换即回滚）

## H-5 四场景（各自独立容器，全部优雅处理）
| 场景 | 注入 | 结果 |
|---|---|---|
| 正常 | 无 | HTTP 200，326 字回答，零错误 |
| 依赖不可用 | rerank 端点指向不可达地址 | HTTP 200，323 字（降级余弦精排），零错误 |
| 模型失败 | LLM_API_KEY 无效 | HTTP 200 + 明确错误事件（"服务暂时无响应，请稍后重试"），非崩溃非静默 |
| 预算/超时 | AGENT_MAX_STEPS=1 + Agent 100% | HTTP 200，restart 事件 → fast path 接管，590 字完整回答 |

附带发现（非阻塞）：模型失败场景的错误事件为裸 {"error": ...}（无 type 字段），
前端需按裸 error 键处理——已确认前端流式处理兼容；记录为 UX 观察项。
