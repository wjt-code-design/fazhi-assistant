# 任务书 §11 审核清单独立复核报告（任务 4）

**复核人**：审查侧独立执行助手（dispatch-tasks-20260908.md 任务 4）
**复核日期**：2026-09-08
**复核对象**：主助手提交的 `release-evidence/legal-agent-v1-complex-v1-20260907/`、`docs/gate5-formal-dev-20260908.md`、git 提交链
**判定口径**：通过 / 不通过 / 无法判定，均附证据路径

---

## 总览

| 分区 | 通过 | 不通过 | 无法判定 |
|---|---|---|---|
| 11.1 范围与简化 | 4 | 0 | 0 |
| 11.2 冻结边界 | 3 | 1 | 1 |
| 11.3 同会话能力 | 2 | 0 | 3 |
| 11.4 RAG 与引用 | 4 | 0 | 2 |
| 11.5 测试可信度 | 6 | 1 | 3 |
| 11.6 权限与隐私 | 3 | 0 | 2 |
| 11.7 隐藏集完整性 | 3 | 0 | 0 |

**重点发现（P1 级 2 项、P2 级 3 项）见文末"发现的问题清单"。**

---

## 11.1 范围与简化

| 项 | 判定 | 证据 |
|---|---|---|
| 只处理第一阶段 | ✅ 通过 | `git log --oneline -8`（2026-09-08 实测）：8 条提交主题全部为 gate2/3/4/5 与 agent 会话修复，无其他模块 |
| 未混入部署/长期记忆/法考画像/文书/多模态 | ✅ 通过 | 同上；提交列表无部署/记忆/画像/文书/多模态字样 |
| 复用现有主链，无平行 Agent | ✅ 通过 | 修改对象为既有文件：`backend/agent/runtime.py`、`backend/prompts.py`、`backend/retrieval.py`（git status M 列表），无新建平行框架目录 |
| 旧 SSG/ASRG 不参与判定 | ✅ 通过 | `grep -ri "SSG\|ASRG" release-evidence/legal-agent-v1-complex-v1-20260907/ docs/gate5-formal-dev-20260908.md` → 0 命中 |

## 11.2 冻结边界

| 项 | 判定 | 证据 |
|---|---|---|
| 基线与最终 commit 可解析，工作区状态如实记录 | ⚠️ 部分不通过 | HEAD `ee939bcbab949ed0f5ae4575843ed5ec76c61154`（2026-09-08T12:25:23+08:00）可解析；但**工作区脏且未记录**：`git status` 含 15+ 处 M，其中 `backend/agent/runtime.py` mtime=2026-09-08T13:22:30（run-4 结束 13:14 之后被修改、未提交），gate5 文档未记录此状态 |
| 模型、prompt、配置、题集、rubric、corpus/index 均有 exact hash | ⚠️ 部分不通过 | `gate1-freeze-manifest.json` 实测 keys=[schema_version, status, law_as_of, collections, corpus_logical_sha256, file_sha256, note]：题集/rubric/protocol/fact-ids/lawcheck 5 文件 + corpus_logical_sha256 有 hash；**model、prompt、配置无 hash 记录** |
| 开发集冻结后未被原地修改 | ✅ 通过 | 复算 file_sha256：frozen-cases-v1.json、frozen-round-protocol-v1.json、rubric-v1.json、frozen-fact-ids-v1.json 4/4 一致；gate1-lawcheck 条目按别名指向 `docs/agent-v1-taskbook-gate1-lawcheck-20260907.json`，sha256 `a45ed0e09ce308ee…` 一致（5/5 实际一致） |
| 隐藏集没有泄露给实施过程 | ✅ 通过 | 隐藏集由审查侧 2026-09-08T13:26:56 冻结并出承诺（dispatch-output/task1/hidden-commitment.json），此前不存在；实施侧工作分支无隐藏题痕迹 |
| 没有跨 commit、跨题集或跨 index 混比 | ❓ 无法判定 | 各 run 的代码基线未逐次记录；且 runtime.py 在 run-4 与 hidden run 之间被修改（见发现 P1-1），跨运行基线一致性存疑，需主助手确认 uvicorn(127.0.0.1:8000, PID 13784) 启动时间与加载代码版本 |

## 11.3 同会话能力（抽验 gate2-run-run-4-cont-sessions.json）

| 项 | 判定 | 证据 |
|---|---|---|
| 首轮追问覆盖决定性事实 | ✅ 通过（证据成立；质量未达标已如实记录） | run-4 会话记录各题 asked 均有具体追问（如 C10 r1"聊天记录是否完整且未经篡改"）；gate5 §3 R2 20/20；DoD 层面 0/10 未达已在 gate5 如实报告 |
| 第二轮不重复已答问题 | ✅ 通过（抽验） | C10 r1/r2 prompt 不同；gate5 §3 R3 20/20 |
| 用户更正能覆盖旧事实并保留冲突提示 | ❓ 无法判定 | run-4 全部题 final_chars=0（技术失败），无最终输出可验证更正覆盖行为 |
| 达到两轮上限后条件化分析 | ❓ 无法判定 | 同上，六段式 final 输出缺失（gate5 §3 R6 0/20） |
| 新会话不继承旧案件事实 | ⚠️ 部分 | 结构上各题独立 conv_id（C10=2187 等，互不相同）；行为级无跨会话污染检测证据 |

## 11.4 RAG 与引用

| 项 | 判定 | 证据 |
|---|---|---|
| 每个必需依据确实存在于冻结知识库 | ✅ 通过 | `docs/agent-v1-taskbook-gate1-lawcheck-20260907.json`：开发集 26/26 FOUND，status 均为"现行"（本侧另以容器内 chromadb 独立复核 13 个扩展条目，13/13 FOUND） |
| 检索相关但不用证据→归因 generation | ✅ 通过 | gate5 §4 失败归因表明确区分 verifier/retrieval/planner 归属 |
| 库内缺失与检索漏召回被区分 | ✅ 通过 | gate1 lawcheck 存在性核验 + `EVIDENCE_COVERAGE_DEFICIENT` 归因链；test_agent_verifier 用例佐证 |
| 实质性法律结论逐项绑定 evidence ID | ❓ 无法判定 | run-4 final_chars=0，正式运行无最终产出可核；实现层有测试但正式会话未展示 |
| 法律版本、效力和适用时间有确定性检查 | ✅ 通过 | lawcheck 全部条目 status="现行"，law_as_of=2026-08-01 |
| LongCat 没有评价自己的正确性 | ✅ 通过（机械判定佐证） | 判定脚本 `backend/scripts/gate5_judge.py` 独立于 LLM；gate5 §3 称"机械可判项"；无法 100% 排除 LLM 参与内容性评分，未见反证 |

## 11.5 测试可信度

| 项 | 判定 | 证据 |
|---|---|---|
| mock 结果只用于编排测试 | ✅ 通过（附版本注记） | 容器 preflight-004 内实测 `pytest tests/test_agent_resume.py tests/test_agent_controller.py tests/test_tool_gateway.py tests/test_agent_runtime.py tests/test_agent_verifier.py -q` → **117 passed, 3 warnings, 18.55s**。⚠️ 注记：容器代码 sha 与本地 HEAD 不一致（prompts.py/retrieval.py/agent/runtime.py 均不同，容器为旧构建），测试结论代表容器版本而非 ee939bc |
| 正式质量结论来自 LongCat 完整会话 | ✅ 通过 | gate2-run-*-sessions.json 含真实 SSE 记录、conv_id、elapsed_s（如 C10 182.1s） |
| 新测试有正确原因的 red 证据 | ❌ 不通过 | 全仓检索未见 red 证据文件/记录（docs 与 release-evidence 仅在任务书/baseline 文档中原则性提及"先红后绿"，无实际 red 运行记录） |
| 两轮结果分别达标，没有择优 | ✅ 通过（如实报败） | gate5 §3 run1/run2 分列 0/10，无择优痕迹 |
| "两次正式运行"与"单次会话最多两轮"未混淆 | ✅ 通过 | 会话记录 rounds ≤ 3（initial+2 resume），两次运行以独立文件 gate2-run-gate5-dev-run-1/2/-3/-4 分列 |
| 所有失败、超时和 fallback 均保留 | ✅ 通过 | run-4 记录含 error_codes（EVIDENCE_COVERAGE_DEFICIENT 等）、raw_tail |
| 9/10 与 4/5 可由逐题结果重新计算 | ✅ 通过 | 0/10 逐题可复算（gate5 §3/§4）；4/5 由审查侧隐藏集判定产出（dispatch-output/task1/verdict-*.md） |
| RAG 对照使用同一模型和检索边界，未人为削弱基线 | ❓ 无法判定（进行中） | Gate 2A 由审查侧任务 2 执行，产出后补验 |
| RAG-initial 与 RAG-full-facts 分开报告 | ❓ 无法判定（进行中） | 同上 |
| 逐轮用户补充来自冻结事实槽 | ✅ 通过 | gate2_runner.py:27-30 从 frozen-cases-v1.json/frozen-round-protocol-v1.json 读取，关键词表硬编码于脚本（无临场加事实） |

## 11.6 权限与隐私

| 项 | 判定 | 证据 |
|---|---|---|
| 工具调用严格落在只读 allowlist | ✅ 通过（测试层） | test_tool_gateway.py 在 117 passed 之列；实现层无独立运行时审计证据 |
| 没有跨用户、跨案件或跨会话事实污染 | ❓ 无法判定 | 无独立检测证据；未见反证（异常日志/投诉记录不存在） |
| 没有写入跨会话长期记忆 | ❓ 无法判定 | 无运行时审计证据；未见反证 |
| 没有静默外部调用或副作用 | ⚠️ 部分 | `backend/llm_guard.py`、`backend/audit.py` 存在（机制佐证）；无运行时核验 |
| evidence 中无密钥、真实用户数据和绝对宿主路径 | ✅ 通过 | 实测扫描 release-evidence/legal-agent-v1-complex-v1-20260907/：sk-key/password 模式 0 命中；手机号正则 0 命中；身份证正则 0 命中；`C:\Users\33393` 0 命中 |

## 11.7 隐藏集完整性

| 项 | 判定 | 证据 |
|---|---|---|
| 候选实现冻结前，实施者没有接触隐藏题正文、补充脚本或金标 | ✅ 通过 | 隐藏题 2026-09-08T13:26:56 由审查侧生成冻结（早于首次运行 13:29:43），此前仓库无 H01-H05 任何痕迹 |
| Owner 持有验收前的 hash 承诺，验收后可公开复算 | ✅ 通过 | `dispatch-output/task1/hidden-commitment.json`：commitment `216ca12bc9d839e03bbd9d3f77cfcbd86248364a74a9a85249c9a7c91c25ed93`，生成时间 13:26:56（早于 run-a 13:29:43）；盐值由审查侧留存（salt.txt），验收时公开复算 |
| 实施者若据隐藏题失败改码→题集降级为回归集 | ✅ 通过（流程就绪） | 本轮为首次隐藏运行，尚未发生"据隐藏题改码"；若发生按条款降级 |

---

## 发现的问题清单（请主助手逐条响应）

| # | 级别 | 问题 | 位置 | 建议修复 |
|---|---|---|---|---|
| P1-1 | P1 | 运行基线不一致风险：`backend/agent/runtime.py` mtime=2026-09-08T13:22:30（run-4 于 13:14 结束、hidden run-a 于 13:29:43 启动），工作区存在未提交修改且未记录；uvicorn(127.0.0.1:8000) 的实际加载代码版本无法从外部确认。hidden run-a/b 已记录运行窗口代码快照（dispatch-output/task1/code-snapshot-run-window.json），但主助手需说明 run-4 所用基线，并对"runtime.py 修改是否影响 Agent 行为"给出说明 | backend/agent/runtime.py；git status | ① 说明 13:22 修改内容与动机；② 如影响 Agent 行为，声明 run-4/hidden run 结果适用哪个代码状态，必要时补跑；③ 今后每次正式运行前记录 git HEAD + git status 快照 |
| P1-2 | P1 | 冻结 manifest 不完整：gate1-freeze-manifest.json 未覆盖 model/prompt/配置的 hash（仅 5 个文件 + corpus_logical_sha256），不满足 §11.2"模型、prompt、配置、题集、rubric、corpus/index 均有 exact hash" | release-evidence/legal-agent-v1-complex-v1-20260907/gate1-freeze-manifest.json | 补充 manifest 字段（model_id/prompt 文件/关键配置的 sha256）；注意 manifest 状态为 FROZEN，应以"新增版本"方式补（任务书：冻结后只能新增版本，不得原地改） |
| P2-1 | P2 | red 证据缺失：§11.5 要求新测试有正确原因的 red 证据，全仓未找到 | docs/、release-evidence/ | 由主助手补写各新测试的 red 复现记录（失败原因 + 转绿提交） |
| P2-2 | P2 | pytest 复现环境不成立：本地无 pytest，容器 preflight-004 有 pytest 但代码落后 HEAD（prompts.py/retrieval.py/runtime.py 三文件 sha 均与 HEAD 不同）。117 passed 的结论不能直接代表 ee939bc 基线 | 容器 legal-agent-preflight-004 | 重建与 HEAD 一致的运行/测试环境后复跑 5 个测试文件，回填结果 |
| P2-3 | P2 | manifest 内 "gate1-lawcheck" 条目命名与实际文件名（docs/agent-v1-taskbook-gate1-lawcheck-20260907.json）不一致，哈希虽一致但可解析性差（本侧首查曾误报 MISSING） | gate1-freeze-manifest.json file_sha256 键 | 下版 manifest 用真实相对路径 |

## 复核方法附注

- manifest 复算：以 manifest 所在目录为基准逐文件 sha256 复算（2026-09-08 13:30 前后）。
- 隐私扫描正则：sk-key/api_key/password 赋值模式、1[3-9]\d{9}（排除长数字）、18 位身份证、`C:\Users\33393`。
- 测试运行命令：`docker exec legal-agent-preflight-004 python -m pytest tests/test_agent_resume.py tests/test_agent_controller.py tests/test_tool_gateway.py tests/test_agent_runtime.py tests/test_agent_verifier.py -q`（pytest 9.1.1 为复核时临时安装于容器）。
- 代码版本三方对比：local 工作区 / git HEAD / 容器 /app 内文件 sha256 逐一比对。
