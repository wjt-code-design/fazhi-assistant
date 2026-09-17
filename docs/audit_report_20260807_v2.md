# 对抗审计 v2 报告（2026-08-07）

> 深度生成式对抗检查整个项目：6 维度并行 find → 每个 finding 独立对抗性反驳验证。
> 33 agents / 619 工具调用 / 约 15 分钟。上一轮审计（2026-08-07 早，21 条）已修复，
> 本报告为新一轮深度检查。**全部 23 条确认 finding 已修复**（6 笔提交）。

## 审计方法

- **Find**：6 维度并行审查 agent（security / retrieval / concurrency / frontend / config / data_tests），
  每个只报可定位到 file+line+触发场景的问题，先读上次审计报告与 PROBLEM_LOG 防误报。
- **Verify**：每个 finding 独立对抗性验证 agent，要求阅读对应行代码、尝试反驳、检查缓解机制、
  评估严重度是否夸大——默认怀疑态度，证据不足判 isReal=false。

## 结果

| 项目 | 数量 |
|---|---|
| 总 findings | 27 |
| **确认** | **23**（high 3 / medium 13 / low 7） |
| 拒绝 | 4（已被缓解或证据不足） |

## 确认 findings 与修复（按严重度）

### high（3）

| # | 问题 | 修复 |
|---|---|---|
| 1 | **DOCX 解压炸弹**（knowledge_service.py）：raw 10MB 上限只限压缩体积，DEFLATE 重复 XML 可 100:1 解压到 GB 级，任意登录用户可 OOM 打崩服务 | validate_upload 用中央目录 ZipInfo.file_size（不解压）拒绝 >30MB 条目，已验证炸弹（31MB 压缩后 30KB）被拒 |
| 2 | **SSE 流式无超时**（api.ts）：pending reader.read 时 UI 永久卡死（上次审计 #3 只覆盖 reject 路径） | AbortController + 60s 无数据看门狗，超时 abort 走提前退出，doSend finally 必然执行 |
| 3 | **Dockerfile 烘焙 .env**：backend 无 .dockerignore，根 .dockerignore 对子目录构建不生效，COPY . . 把真实 API key 烘进镜像层 | 新增 backend/.dockerignore + Dockerfile 防呆 `RUN test ! -f /app/.env` |

### medium（13）

| # | 问题 | 修复 |
|---|---|---|
| 4 | admin 用户名可在 seed 前被注册抢占，seed 后管理接口全锁死 | register 保留 admin 用户名 + seed 校验 role 非 admin 报错 |
| 5 | SSE 客户端断开留孤立 user 消息（#10 的断开子路径） | stream() 加 `_posted` 标志 + finally 兜底占位 |
| 6 | expand_citations 把合同条款"第X条"错补《最近书名》污染合同答案 | 重写为仅"书名+条号+续接标点+独立条号"展开，"本合同第九条"不再错补 |
| 7 | insurance_law"保险"关键词子串命中所有社保题 | 移除裸"保险"，保留 保险人/被保险人 专属词；社保/商业保险分流验证通过 |
| 8 | GeneratorExit 绕过 except Exception，_post 永不执行 | finally 用后台任务派 _post_placeholder（不 await/yield） |
| 9 | _post 增量压缩 LLM 调用未走 llm_guard，突发长答复并发无界 | compress 包进 `with llm_guard` |
| 10 | mediaCache blob URL 永不 revoke，图片内存无界增长 | Map 上限 40，超限 revoke 最旧 |
| 11 | MessageHtml memo 被 expanded 对象引用击穿，点法条卡全量重标注 | 改字段级 memo 比较（source/article/occurrence），只重渲染命中消息 |
| 12 | 录音中离开页面不停止麦克风 | 卸载清理 stop wavRec |
| 13 | settings.llm_model 死配置却对外宣传 | 删字段 + 移除 .env.example/docker-compose 的 LLM_MODEL |
| 14 | 5 个补充组重点法律缺名于标注清单，无书名号引用不标色 | 著作权/商标/专利/合伙企业/劳动争议调解仲裁法 入前后端两清单 |
| 15 | 跨组关键词重复致交叉领域补充污染 | copyright"发行"→"发行权"消歧；其余故意共享词白名单化（新测试） |
| 16 | 补充组数据测试全 @slow，CI 跳过，数据文件零防护 | 新增非 slow test_scenario_data.py（结构/关键词/跨组重复）+ slow 追加"所有条文在库"校验 |

### low（7）

| # | 问题 | 修复 |
|---|---|---|
| 17 | rerank 失败记忆未接入检索循环，配额关闭时坏模型每请求重试 | 循环体跳过 `_depleted_mem` 模型 |
| 18 | _num_to_cn 万位以上归一错误（100000→"一十"） | 重写为 4 位一节分段算法，已验证 100000→十万/110000→十一万/1亿→一亿 |
| 19 | 锚点保底被 docs[:k] 截断，多锚点后段条文保底失效 | 截断后补回被挤出锚点条文（每锚点前 1 条必现） |
| 20 | async 生成器内 Chroma .get()/SQLite 扣减阻塞事件循环 | _qa_direct_return + 3 处 registry.deduct 改线程池 |
| 21 | message_count 读-改-写竞态，并发 +1 只生效一次 | 三处改为 DB 原子自增（COALESCE+1） |
| 22 | quota DB 路径本地/容器解析到不同宿主目录 | 统一 backend/data + compose 注入 QUOTA_DB，迁移现有库 |
| 23 | ARCHITECTURE.md 仍称"单一 omni 模型"与 27 条路由矛盾 | 更新架构图 + LLM 描述 |

## 验证

- 每批修改后跑针对性验证：DOCX 炸弹脚本、_num_to_cn 边界、expand_citations 句式、保险/社保分流、
  test_scenario_data.py（3 passed）、test_scenario_supplement.py（6 passed 含条文在库）、前端 tsc 0 error。
- 补充组改动后 5 法召回回归：见提交后单独跑（eval_5law.py / qwen 缓存批次）。

## 提交

本次审计修复（6 笔提交）：
- 批1+2（high 3 件 + 前端 4 件）：`a652661`
- 批3（检索/归一 7 件）：`e6faa4d`
- 批4（SSE/并发 4 件）：`91268cc`
- 批5（文档/测试/配置 4 件）：`fcfb285`
（此前 5 法召回补齐等在 705a033 / 6d88f4d / ec00b35 等，与本轮审计无直接关系）
