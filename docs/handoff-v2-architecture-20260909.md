# 工作交接文档：Agent V2 架构优化（L1/L2/L3 根因修复）——2026-09-09

> 交接人：本次实施助手（当前工作会话）
> 交接日期：2026-09-09（北京时间）
> 接手前提：请完整阅读本文件 + §7 的必读源文档后再动手。本文件所有路径均为仓库根相对路径（仓库根 = `C:\Users\33393\Desktop\ai-legal-helper`）。
> HEAD 锚点：`ebe82e2`（docs(v1): 结算文档最终更新）。接手后第一步先 `git log --oneline -5` 确认 HEAD 未被他人推进。

---

## 1. 我在做什么任务（一句话定位）

在 **复杂法律咨询 Agent V1** 的验证轮持续 full_closure 0/10 的背景下，执行**架构级修复执行书**（非补丁），逐一消灭三个已固定的根因：

- **L1**：Planner（决策模型）输出结构化 JSON 失败 → 会话在"研究结束→转终稿"决策点死亡（run-8 里 7/10 死因）。
- **L2**：法条级引用召回缺口：L2a 检索偏科（只查一个角度）+ L2b 文章级精度不足。
- **L3**：16 步预算被澄清和回喂重试耗尽（放大器）。

对应对策编号：**G1 确定性终稿门**、**G2 争点强制检索扇出**、**方案A（G6）结构化输出**、G3（可选重排）、G4/G5（Owner 决策项）。

任务的完整定义、根因证据、设计、DoD 全部在 **`docs/v2-optimization-execution-taskbook-20260909.md`**（下称"执行书"）。接手后**以执行书为唯一事实源**，本文件只是给没有记忆的助手讲的进度与上下文。

---

## 2. 做到哪儿了（进度总览）

| 阶段 | 状态 | 证据 |
|---|---|---|
| run-8 取证 + 停损（V1 转 V2 决策） | ✅ 完成 | `docs/v1-candidate-fix-options-20260908.md` §5；提交 `b26b972` |
| 执行书成稿 + 审查修订 | ✅ 完成 | `d2bd227`、`dd57a0e` |
| **G1 确定性终稿门**（打 L1） | ✅ 完成并提交 | `5b4449b`；红证据 `dispatch-output/harness-red-green/g1-red.log` |
| **方案A/G6 planner json_schema**（打 L1） | ✅ 完成并提交 | `fc47bd2`；探测脚本 `dispatch-output/probe_longcat_*.py`（5 个） |
| **G2 争点强制检索扇出**（打 L2a） | ✅ 完成并提交 | `65b000a`；红证据 `dispatch-output/harness-red-green/g2-red.log` |
| run-9（G1 验证轮） | ✅ 已判定 | `gate2-run-gate5-dev-run-9-sessions.json`；结果见执行书附录暂无表（parse 4/10） |
| run-10（方案A 验证轮） | ✅ 已判定 | `gate2-run-gate5-dev-run-10-sessions.json`；**执行书附录 A** |
| run-11（G2 验证轮） | ✅ 已判定 | `gate2-run-gate5-dev-run-11-sessions.json`（2026-09-09 15:47 落盘）；**执行书附录 B** |
| DoD 文档更新 | ✅ 已提交 | `9c902b0`（G1/G2/方案A 完成标记、run-10 判定入附录） |
| V1 结算文档最终更新 | ✅ 已提交 | `ebe82e2` |
| **新失败面（writer→verifier 链路）处置** | ❌ **未做，待 Owner 决策** | 见 §4 |

**当前全部代码改动已提交，`backend/agent/` 目录工作区干净**（`git status` 确认）。

---

## 3. 哪些地方做好了（已交付且有证据）

### 3.1 三个工程项全部落地并回归绿

1. **G1 确定性终稿门**（`backend/agent/controller.py`）
   - 新增 `_deterministic_finish_gate(state)`：评估器判 SUFFICIENT 或（澄清预算耗尽 + 每 issue 至少 1 条证据）时，直接转 DRAFTING，**绕过 planner 决策**。
   - 死循环防护已做（门触发后 `break` 出决策循环）。
   - 测试：`backend/tests/test_agent_controller.py` 新增 G1 红→绿用例。

2. **方案A/G6 planner json_schema**（`backend/agent/runtime.py`）
   - 新增 `_invoke_planner()`：transport 支持 `bind()` 时带 `response_format=json_schema`（strict=False）调用，**构造失败/调用失败一律静默回退普通 invoke**（fail-safe 设计）。
   - 修了 2 个关键实现缺陷（都为第一次上线时未生效，已复现修复）：
     - `PlanDecision.model_json_schema()` 对判别联合抛 AttributeError → 改用 `TypeAdapter(PlanDecision).json_schema()`。
     - `ToolCallDecision.args: SerializeAsAny[BaseModel]` schema 编码为空对象 → 请求层注入具体工具输入联合 schema（RetrieveLawsInput|LookupArticleInput|ContractInput|RetrieveMemoryInput）。

3. **G2 争点强制检索扇出**（`backend/agent/controller.py`）
   - 新增 `_seed_issue_retrievals()`：分解完成后、planner 循环开始前，对每个尚无成功证据的 issue 强制执行一次 `retrieve_laws(query=issue.question, k=4)`，**走 `_execute_tool` 既有路径**（指纹去重/预算/fail-closed 全保留，不绕过 gateway）。
   - 测试：`test_agent_controller.py` +151 行、`test_agent_chat_integration.py` +36 行（RecordingGateway 升级 empty/outputs 模式，15 用例同步适配，全部绿）。

### 3.2 验证轮判定已落盘（多次对照）

- **run-10（方案A 全量）** → 执行书**附录 A**：
  - PLANNER_PARSE_ERROR **7/10 → 0/10** ✅（L1 判据达成）
  - 但 EVIDENCE_COVERAGE_DEFICIENT **8/10** ⚠️（幸存者失败面暴露为 L2）
  - full_closure 仍 0/10 ❌
- **run-11（G2 生效）** → 执行书**附录 B**（本会话刚完成）：
  - PLANNER_PARSE_ERROR 维持 **0/10** ✅
  - EVIDENCE_COVERAGE_DEFICIENT **6/10** ⚠️（略降但仍主失败面）
  - **新失败面 ISSUE_DECOMPOSITION_INVALID 1/10（C07）** ❌（首次出现）
  - GENERATOR_FAILURE **2/10**（C01/C10）⚠️
  - has_final 仅 1/10（C09）；full_closure 仍 0/10 ❌

### 3.3 关键取证（DB 实证，接手助手可直接复查）

C02（run-11）DB 取证：`backend/app.db` → `agent_steps` 表（conv=2308, run=`259c38d5-7f6c-4b83-9c70-19333d363e9e`）：
- state_v2/v7/v11 三个 issue 各一次 `retrieve_laws`，**全部 TOOL_SUCCEEDED**（792ms/1062ms/1035ms）→ **G2 扇出真的生效了**。
- `agent_evidence` 表 10 条证据已物化，**其中已包含金标法条**（劳动法44、劳动争议调解仲裁法27）。
- 但 verifier 仍判 EVIDENCE_COVERAGE_DEFICIENT → final 不落盘。

探查脚本（可复用）：`dispatch-output/inspect_run11_steps.py`、`dispatch-output/inspect_c02_evidence.py`、`dispatch-output/inspect_c07.py`。

---

## 4. 哪些地方还需要做 + 遇到的困难/痛点

### 4.1 尚未完成的决策项（最重要，需 Owner 批复）

**现象**：L1/L2 已基本打掉，但**死点转移到"writer 生成 → verifier 判定"链路**（verifier.py:298-304 EVIDENCE_COVERAGE_DEFICIENT 判定要求每 issue 的 claim 绑定有效成文法证据）。**检索到了 ≠ writer 正确引用**，6/10 的 final 被 verifier fail-safe 拦截不落盘。

**结论（写入执行书附录 B）**：
- G3（文章级重排）→ 数据不支持 L2b 根因 → **NOT_NEEDED**。
- G4（预算 16→24）→ 无 BUDGET_EXCEEDED 大面积触发 → 暂不批。
- G5（≥75% 松绑）→ 维持原口径。

**需要 Owner 做的**：批准形成**新的执行书**，专项打 writer-verifier 链路。这是超越当前执行书范围的架构决策。

### 4.2 细分失败面（接手后可各自立项）

| 失败面 | 题 | 证据/线索 | 建议切入点 |
|---|---|---|---|
| writer-verifier 链路（主） | 6/10（C02/C03/C04/C05/C06/C08 等） | 金标已在证据表但 final 被拒；`final_chars=0` | 读 `backend/agent/writer.py`（EvidenceBoundedWriter.render）+ `verifier.py` 判定；分析 writer 产出的 claim 为什么没绑定 issue 证据 |
| ISSUE_DECOMPOSITION_INVALID | C07 | conv_id=null，elapsed 1081s，服务日志 `agent_pre_run_failure` @15:09:52 | `runtime.py build_initial_agent_state` 五类校验（schema/重复/collision/verbatim/trusted source）；分解模型输出质量 |
| GENERATOR_FAILURE | C01/C10 | writer 侧生成本身失败 | `writer.py` 失败路径；LongCat 调用 |

### 4.3 已知痛点 / 环境约束（接手前必读，防踩坑）

1. **LongCat 外呼极慢**：单请求延迟实测最高 ~960s/请求（run-4 观测）；run-11 里单题耗时 1081s。跑验证轮**必须有耐心，串行跑**，不要并发。
2. **服务必须带环境变量启动**：`AGENT_ENABLED=true` 才走 agent 路径；漏设会**静默走 RAG 快速路径**（run-8 踩过：10 题全 0 tool_calls）。当前服务 PID 22576（Python311，14:06 启动，含 G1/G2/方案A 代码），监听 127.0.0.1:8000，日志正常显示 `agent_gate_mode: agent_path`。
3. **服务重启纪律**：新 run 前记录服务启动时间；服务重启会打断在跑会话。
4. **冻结物纪律（执行书 §1.2）**：不改 frozen-cases / round-protocol / rubric / fact-ids / hidden-* / 历史 sessions（run-1~11 是对照基线）；不改评测器 gate5_judge.py；不改 `_PLANNER_SYSTEM_PROMPT`（F3 已证 prompt 增强是回归）。
5. **测试既有基线失败 23 项**（全仓 5 文件 145+ 全绿之外）：writer 21 + agent_gate 1 + agent_resume 1，**与 G1/G2/方案A 无关**（stash 验证确认）。接手跑全量测试时**不要**把这 23 项当成自己引入的回归。
6. **禁止篡改/伪造证据**：任何判定结论必须有 sessions json / DB / 日志作为可复算证据链（防幻觉纪律）。

---

## 5. 从哪儿接手（Step-by-Step 上手路径）

### 5.1 必读文档（按顺序）

1. **`docs/v2-optimization-execution-taskbook-20260909.md`** —— 执行书（根因、设计、DoD、附录 A/B 判定）【第一优先级】
2. `docs/agent-complex-consultation-v1-taskbook-20260907.md` —— V1 复杂咨询任务书（冻结题集来源 §7，金标口径）
3. `docs/v1-candidate-fix-options-20260908.md` —— V1 停损决策与候选方案溯源
4. `docs/adr-longcat-response-format-20260909.md` —— 方案 A（response_format）可行性 ADR
5. `dispatch-output/` 下的 `probe_longcat_*.py`（5 个）、`root_cause_analysis.py` —— 取证脚本

### 5.2 代码地图（改动的核心文件）

| 文件 | 作用 | 本阶段改动 |
|---|---|---|
| `backend/agent/controller.py` | Agent 决策主循环 + G1 终稿门 + G2 扇出 | `_deterministic_finish_gate`、`_seed_issue_retrievals` |
| `backend/agent/runtime.py` | Planner 适配器（决策模型封装） | `_invoke_planner`（response_format 回退链） |
| `backend/agent/schemas.py` | PlanDecision / ToolCallDecision schema | args schema 注入点 |
| `backend/agent/verifier.py` | 确定性验证（当前主失败面的判定处）| 未改（冻结） |
| `backend/agent/writer.py` | EvidenceBoundedWriter 终稿生成 | 未改（冻结） |
| `backend/tests/test_agent_controller.py` | 主测试 | G1/G2 用例 + fixture 升级 |
| `backend/tests/test_agent_chat_integration.py` | 集成测试 | 15 用例适配扇出 empty 模式 |

### 5.3 复现环境

- 服务启动（必须 AGENT_ENABLED=true 路径）：
  ```
  cd backend
  AGENT_ENABLED=true python -m uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir backend
  ```
  （当前实际服务 PID 22576 已在跑，若已被杀按此重启）
- 模型：LongCat-2.0（text 主模型，`LLM_MODELS_JSON` 里 `key=longcat_text_flag`）；Embedding `qwen3.7-text-embedding`；Rerank `BAAI/bge-reranker-v2-m3`。
- 冻结题集：`release-evidence/legal-agent-v1-complex-v1-20260907/frozen-cases-v1.json`（C01~C10）。
- 数据库：`backend/app.db`（表：agent_runs / agent_steps / agent_evidence / conversations / messages）。

### 5.4 跑验证轮的命令（无歧义可复算）

```powershell
# 1) 跑 run（服务必须先在线；--run 名字自定义，如 gate5-dev-run-12）
cd C:\Users\33393\Desktop\ai-legal-helper\backend
python scripts\gate2_runner.py --run gate5-dev-run-12 --all --base-url http://127.0.0.1:8000
# 产物自动写到：release-evidence\legal-agent-v1-complex-v1-20260907\gate2-run-gate5-dev-run-12-sessions.json

# 2) 两层 judge 判定
python scripts\gate5_judge.py ..\release-evidence\legal-agent-v1-complex-v1-20260907\gate2-run-gate5-dev-run-12-sessions.json
# 输出 mechanical_pass_count / full_closure_pass_count / formal_gate_passed 三行汇总
```

### 5.5 判定对照基线（判据固定在执行书 §5）

| 主轴 | run-8 | run-9(G1) | run-10(A) | run-11(G2) |
|---|---|---|---|---|
| PLANNER_PARSE_ERROR | 7/10 | 4/10 | 0/10 | 0/10 |
| EVIDENCE_COVERAGE_DEFICIENT | 2/10 | 3/10 | 8/10 | 6/10 |
| ISSUE_DECOMPOSITION_INVALID | - | - | 0 | 1/10 |
| GENERATOR_FAILURE | - | 0 | 1/10 | 2/10 |
| has_final | - | 5/10 | 1/10 | 1/10 |
| full_closure | 0/10 | 0/10 | 0/10 | 0/10 |

目标（执行书判据）：L1 parse ≤1/10 ✅ 已达；金标命中 missing<8 且无偏科题；full_closure 实质抬升 ❌ 未达。

---

## 6. 语义防误伤清单（接手时避免误读）

- **"run-N"**：指一次在线验证轮（Gate2 评测器跑 frozen-cases，产物 `gate2-run-gate5-dev-run-N-sessions.json`）。数字 N 是流水号，run-9 是 G1 验证、run-10 是方案A 验证、run-11 是 G2 验证——**每个 run 对应不同代码状态**，不可互易。
- **"PLANNER_PARSE_ERROR"**：Planner 输出无法解析为 PlanDecision（L1 死亡点）。方案 A 后归零。
- **"EVIDENCE_COVERAGE_DEFICIENT"**：verifier 判定某 issue 的 claim 未绑定有效成文法证据（verifier.py:298）。**这是当前主失败面，不是检索失败** —— 检索到了 ≠ writer 引用了。
- **"ISSUE_DECOMPOSITION_INVALID"**：分解阶段输出校验失败（runtime.py:281-314 五类之一），发生在 create_run 之前，DB 无 agent_run 记录，只有服务日志 `agent_pre_run_failure`。C07 conv_id=null 就是它。
- **"GENERATOR_FAILURE"**：Writer 生成失败（非 verifier 拒绝）。
- **"full_closure"**：两层 judge（mechanical + 法律域语义）全部通过的题数 / 分母。**当前永远 0/10 是全局验收卡点。**
- **"方案 A" / "G6"**：同一件事——planner 用 `response_format=json_schema` 强制结构化。执行书里两处称呼都有，指同一个。
- **frozen-***：冻结物（题集/协议/事实ID/判分）。**任何助手不得修改**；需要改要 Owner 下新决策书。
- **AGENT_ENABLED=true**：必须带在 uvicorn 启动环境里；漏设会静默走 RAG 路径，run 数据作废。

---

## 7. 自我校验清单（交接完整性）

- [x] HEAD = `ebe82e2`，backend/agent 工作区干净
- [x] 最近 4 个代码提交（5b4449b / fc47bd2 / 65b000a）含完整根因、设计、测试适配
- [x] run-10/run-11 判定已写入 `docs/v2-optimization-execution-taskbook-20260909.md` 附录 A/B
- [x] DB 取证脚本留存于 `dispatch-output/`（inspect_run11_steps.py 等）
- [x] 冻结物 / 评测器 / prompt 未被本阶段改动（`git diff --check` 干净）
- [x] 未提交的新文件（dispatch-output/*.py、diag/grayscale-*、.workbuddy/ 等）为过程产物，按纪律不入库

**接手助手的第一步建议**：读执行书全文 → 读附录 B（run-11 判定）→ 用 §5.4 命令复查一次 judge 输出一致性 → 向 Owner 提交"writer-verifier 链路专项执行书"草案。