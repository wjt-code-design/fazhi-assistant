# D-34 A：响应归属修复与本地验收（2026-10-11）

## 结论与权限

Owner 已按推荐批准 A 的响应归属收敛方案。本次 D-34 **限定范围的本地修复通过验收**；此前“准备结束后、响应尚未接管时异常漏记”的 P1 已关闭。非部署阶段整体仍 **BLOCKED**，本报告不等于全项目门禁通过、可发布或可上线。

本次依据：已批准的 `d34-response-ownership-replan-20261011.md`；保留历史的 `d34-execution-and-review-20261011.md`；本轮最终源码、隔离测试及两轴复核。使用 Ponytail 最小可靠实现、先红后绿及独立 Spec/Standards 复核；没有以缩减安全/归属校验换取更小 diff。

- 主仓：`C:/Users/33393/Desktop/ai-legal-helper`。主仓本来存在大量未提交内容，本轮未写入或整理主仓，不能称其干净。
- 候选：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`。
- 分支：`codex/nondeploy-closeout-20261010`；HEAD：`19e296e879ac2ffbb0a862c2c9e595d3c81c8ded`，未变。
- 运行根：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`。
- 候选只有 `backend/main.py` 修改、`backend/tests/test_agent_turn_compensation.py` 新增；索引为空，均未提交。报告与反事实脚本保存在外部运行根，不在候选 diff 中。
- 未提交、合并、推送、改 refs；未读取凭据值/真实库/模型缓存、调用模型、安装或升级依赖、启动应用/容器或部署。

## 修复范围与不变契约

不是在每个异常点加补丁，而是连续明确三个责任段：

1. 首次 bootstrap/恢复 CAS 接受输入、Agent 执行与快车道准备：同一个受保护任务负责，取消必须等待线程与结果清理结束，再关闭 Session。
2. 准备完成但响应还未建立：`_serialized_chat` 的内部请求守卫负责失败/取消结果；守卫只在实际向快车道交接时激活，不因 Agent 终止结果而激活。
3. `_ChatStreamingResponse` 接管后：沿用现有响应清理责任，不新设并行补偿责任人；会话锁保持到持久化结束。

抽出一个 `_join_owned_task` 共用受保护等待逻辑，支持重复 task.cancel 与 AnyIO level cancellation。请求游标、已提交标记和存储核查避免双写；真实会话所属变化/游标之后出现别轮用户记录时拒绝错误补偿。已有成功终稿不被失败占位覆盖，计数与实际记录相符。响应前补偿写入失败保留原请求异常并输出带会话/用户编号及异常类型的日志，不输出敏感异常原文，不伪装成功。

保持旧契约：clarification 不写 assistant Message；恢复补充事实与检查点不写 user Message；未接受、非法/stale resume 不补偿；D-33、依赖、数据库 schema、公开请求与 SSE schema 不改。

不承诺多 worker/跨进程幂等、进程崩溃恢复或刷新后的追问重建。这些不属于本次 A；当前证明针对现有单 worker、进程内会话串行锁。

## 同版最终证据

最终 SHA-256：

```text
backend/main.py
88E035318A0264D1E59B33E2D8402A1A05C3163E6B5ED1901D8632B3F11636D5
backend/tests/test_agent_turn_compensation.py
2CC8A49A42554242ADC8F1E47AFDB4619E0F120EC17C4530BDECECAE0DED8A77
```

下表文件均位于运行根 `evidence/`。通过数不是覆盖率，deselected 不算通过；43 项定向包含在 168 项内，不能相加为 211。

| 检查 | 实际结果 | 证据/口径 |
| --- | --- | --- |
| 响应前边界先红 | 4 failed / 33 deselected，rc=1 | `d34-response-owner-red-20261011.xml`；修复前本轮边界红测，非导入错误 |
| 初步绿测 | 37 passed，rc=0 | `d34-response-owner-green-20261011.xml`；中间版本，不冒充最终 43 |
| 最终定向 | 43 passed，rc=0 | `d34-response-owner-final-targeted-20261011.xml`；最终源码及测试同版，16.33s |
| 最终综合隔离回归 | 168 passed / 4 deselected，rc=0 | `d34-response-owner-final-sameversion-20261011.xml`；最终同版，49.49s |
| 固定旧入口反事实 | 7 failed / 3 passed / 33 deselected，rc=1；errors=0 | `d34-response-owner-baseline-red-20261011.xml`；预期失败，用于归因，不是修复后的门禁失败 |
| Ruff lint | rc=0 | envB，`check --no-cache .`；本轮最终控制台输出 |
| Ruff format | rc=0，284 files already formatted | envB，`format --check --no-cache .`；未运行格式改写 |
| mypy | rc=0，74 source files 无错误 | envB；仍有既有未类型化函数体未检查提示，不是全仓完整类型覆盖 |
| diff check | rc=0 | 候选 `git diff --check`；另核新增文件的 Ruff/format |

综合回归包括定向修复、取消边界、流生命周期、状态机、预算终止和 Agent 服务层隔离测试；原有效病例保留。4 项完整启动导入测试通过 `-k` 明确排除，匹配片段为 `chat_live_agent_selection`、`forbidden_agent_failure`、`fallback_to_fast_path_requires`、`conversation_history_coverage_projection`。本轮没有运行全项目 pytest/coverage、真实 HTTP 启动、前端构建/浏览器、在线审计或真实模型质量门；不得沿用旧版全量数字作为本次同版结果。

最终定向运行有 Starlette TestClient/httpx 与 jieba/pkg_resources 两条依赖弃用警告，未以升级依赖消警告。综合进程预加载测试接缝时已输出 Starlette 提示，不据其末尾无 warnings 表认定依赖提示已解决。

## 两轴独立复核

- **Spec**：前轮 P1 已关闭，无未关闭的确定性规格问题/越界变更。独立复跑 43 项定向与 44 项取消/状态/预算邻域；三种响应构造异常、唯一结果及锁释放时机符合目标。
- **Standards**：无未关闭硬违规或需处理的过度设计/维护问题；共用等待、受限守卫和安全日志可接受，不需新生命周期框架。
- 两位复核初次全套核验所用测试哈希为 `96D675730499B937B29C0E618696FAD711568D64C3F677A507CC7CDE98125EE8`。之后仅将 AnyIO 测试局部 `lock=None` 初始化并断言进入清理，避免反事实因未绑定变量而错误失败；生产哈希未变。两位均核对最终两行及哈希，并各自独立复跑对应单例 1 passed、rc=0，确认原结论仍成立。主执行者在最终版本重跑 43/168。
- 两轴为同工具链下的只读子代理复核，不是外部第三方审计，也未各自重跑全项目门禁；39 项模型隔离服务层的同版综合结果来自主执行者，不能冒充两位各自重跑。

## 测试隔离、反事实与可复现命令

测试从当前 `main.py` AST 提取并执行真实入口、取消清理及持久化逻辑，使用临时 SQLite、实际 ORM/恢复 CAS/线程派发；仅在 Agent 与昂贵检索边界使用确定性替身，不导入 main 启动路径。测试用的默认数据库引擎可以被创建，但没有连接真实数据库；应用 conftest 被排除。它比纯 mock 生命周期更强，仍不能替代完整应用集成验证。

反事实脚本只用固定 HEAD 中的 `chat`/`_serialized_chat` 替换提取命名空间，其他安全协作者保留当前版本；验证采集到的每个测试确实使用该替换。7 红命中响应前漏记/未进入补偿等目标，3 绿是既有终止结果不新增补偿的特征测试。这不是完整旧版基线。早期仪器曾因模块身份不一致无效得到 10 绿，发现后作废；修正采集身份并消除未绑定变量掩盖后才得到上表有效读数。不得引用无效绿作为旧行为证据。

以下先设置候选 backend 为工作目录；如路径、HEAD、文件哈希或工具环境变化，先重新核验，不能盲目照搬本次结果。不删除 `--noconftest`，不要改用主仓或共享 venv。全项目门禁须另设计安全启动环境，不在此命令授权内。

```powershell
Set-Location -LiteralPath 'C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend'
$d34Python = 'C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/candidate-envB/Scripts/python.exe'
$d34Ruff = 'C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/candidate-envB/Scripts/ruff.exe'
& $d34Python -B -m pytest --noconftest -p no:cacheprovider tests/test_agent_turn_compensation.py -q --tb=short
# 综合：测试模块提供隔离接缝；4 项 main 启动导入明确排除。
& $d34Python -B -c "import sys,pytest; sys.path.insert(0,'tests'); raise SystemExit(pytest.main(['--noconftest','-p','no:cacheprovider','-p','test_agent_turn_compensation','tests/test_agent_turn_compensation.py','tests/test_cancel_boundaries.py','tests/test_stream_cancellation.py','tests/test_agent_state_machine.py','tests/test_agent_budget_terminal_edges.py','tests/test_agent_chat_integration.py','-k','not chat_live_agent_selection and not forbidden_agent_failure and not fallback_to_fast_path_requires and not conversation_history_coverage_projection','-q','--tb=short']))"
& $d34Ruff check --no-cache .
& $d34Ruff format --check --no-cache .
& $d34Python -B -m mypy --cache-dir 'C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/evidence/d34-mypy-cache' .
git diff --check
```

逐条检查 `$LASTEXITCODE`；某条失败先分析，不以最后一条成功掩盖前面的失败。命令未带输出路径以防覆盖本轮留存 XML；如需新增证据另用新文件名。

单独复跑归因仪器（**预期退出 1**，会重写其同名反事实 XML；只在需要重新归因时执行，不当作候选绿测）：

```powershell
& $d34Python -B -I 'C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/evidence/d34-response-owner-baseline-check-20261011.py'
```

## 未解决项与建议下一步

1. 本次 D-34 局部 P1 关闭，不把未重跑的全量门、真实模型/语料/专业审签、数据恢复验证或现役形态证据变为 PASS。
2. `owner-review-and-next-actions-20261011.md` 中依赖两轴风险、管理员实际口令与既存 JWT 会话处置、公开历史集合、D-14 索引写入口、D-20 私有历史整合与当前对象 CI 等边界仍有效。其中旧审计 13 个 LangChain / 2 个 Chroma 主 ID 仅为留存证据口径，本次没有在线重扫或落实迁移；在册接受不能自动令 pip-audit 绿。
3. 推荐接收并核实正在外部执行的独立迁移/守卫结果及文件归属，再形成安全的全量集成复验对象。复验该对象后才讨论提交与私有历史整合；禁止把主仓的未提交内容和本候选自动混合。
4. 凭据真实失效、公开范围与推送前门禁满足后才可考虑独立分支/PR/CI/正常合并。不要用直接推 master 或强推代替历史整合和审查。
5. 本轮在已批准范围完成后停止；不因“局部通过”自动执行提交、迁移、真实库操作、轮换、公开推送或部署。候选与未提交 diff 原样保留，等待下一项具体授权。

历史文件中的“暂停/未验收”是当时结论，由本页的限定范围结论更新；旧红测、旧 SHA 与旧日志不回写为绿。外部报告没有同步到主仓或候选 `docs/closeout-20261010/`，两处不能视为自动一致。
