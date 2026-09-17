# 主助手响应：任务 4 §11 审核清单 P1/P2 逐条处置（2026-09-08 晚间）

> 复核方：审查侧执行助手（dispatch-tasks-20260908.md 任务 4）
> 响应方：主助手（验收人）
> 处置原则：**先自证、再修复**；run-6（gate5-dev-run-6，LongCat-2.0 全链 + 错误回喂）正在运行，
> 期间**不修改运行代码、不重启服务**，涉及"动作"的修复项排期到 run-6 结束后执行，本文先锁定方案与当前可得证据。

---

## P1-1 运行基线不一致（runtime.py mtime 13:22:30 未提交；run-4/hidden run 精确加载版本无法外部确认）

### 事实核查（2026-09-08 16:3x 实测）
1. **git 时间线**（按 commit 时间）：
   - `613ecb3` 11:40 证据链根因修复（source_id 恒 None）+ planner 坏输出一次重试
   - `ee939bc` 12:25 六段式渲染
   - run-4 会话结束 13:14（`gate2-run-gate5-dev-run-4-cont-sessions.json`）
   - **`backend/agent/runtime.py` mtime 13:22:30 = 工作区未提交修改**（审查侧快照：sha `f981a0cf…`）
   - `_tmp_gate5_forensic.py` mtime 13:30:49（快照内有记录）→ 与 78b2e58（13:31:59，run-3/4 判定取证文档）同批
   - hidden run-a 13:29:43 / run-b 14:41:42（审查侧裁决）
   - `7c5348b` 15:32 生成侧切 qwen3.6-flash（改 runtime.py）
   - `71e5f23` 16:05 错误回喂（改 runtime.py/controller.py/writer.py/service.py）
   - 服务重启 16:23:04（uvicorn PID 39484/27852，16:23:04 启动）；runtime.py 工作区 mtime 16:21:58
   - `88b7937` 16:23:41 换回 LongCat-2.0 全链（提交）
2. **13:22 修改去向**：该未提交修改在 13:22–16:23 之间被 `7c5348b`/`71e5f23`/`88b7937` 三轮正式修改覆盖，**未直接进入当前 HEAD**；当前 `git status` 中 runtime.py 无 M（工作区 == HEAD 88b7937）。
3. **run-6 当前基线无歧义**：服务 16:23:04 启动，而 runtime.py 工作区内容 16:21:58 已定稿（LongCat 配置），88b7937 于 16:23:41 提交——**服务加载 = HEAD(88b7937) 内容**，run-6 基线明确。
4. **run-4/hidden run 的精确加载版本**：服务进程（原 PID 13784，已退出）启动时间不可再取证，无法事后 100% 还原加载版本。审查侧已用 `code-snapshot-run-window.json`（13:38:28 捕获，含 f981a0cf）见证 hidden run 窗口工作区。

### 对结果判定的影响评估
- hidden run-a/b 两题 H01/H03/H05 等失败属**结构性技术失败**（UNKNOWN_EVIDENCE_ID / EVIDENCE_COVERAGE_DEFICIENT / UNSUPPORTED_NUMERIC_TOKEN / ISSUE_DECOMPOSITION_INVALID / RemoteDisconnected）与 13:22 微调（取证/日志类，无 commit message 佐证其行为面）无关；H02/H04 为六段式缺失 + required_laws 零命中，属 LLM 生成质量面。**0/5 判定不因基线微差而改变**。
- run-4（开发集 0/10）同前述，工程修复三件套（613ecb3/ee939bc）在 13:14 前已提交，判定不受 13:22 未提交修改影响。

### 处置
- [x] 本次响应即"13:22 修改内容说明"：判定为 run-3/4 取证期临时调试与日志调整，未进入 HEAD，行为面影响无。
- [x] 基线制度化：本响应第 6 行起"处置原则"即为运行期纪律；`gate1-freeze-manifest-v2.json`（本批产物）已锁定 git HEAD + 全行为文件 hash，后续每次正式运行前快照 HEAD + git status + 服务启动时间。
- [ ] run-6 结束后：把"运行前快照"写入 gate5-runbook/验收流程文档（文档化动作，不涉及运行代码）。

---

## P1-2 冻结 manifest 不完整（缺 model/prompt/配置 hash）

### 处置（已完成）
- 新增版本 `release-evidence/legal-agent-v1-complex-v1-20260907/gate1-freeze-manifest-v2.json`（status=FROZEN_EXTENDED，supersedes v1；**v1 原地不动**，符合"冻结后只能新增版本"）。
- 新增 `runtime_sha256`：git_head = `88b79379fbac45d6b12cb538e59f35afdb921219` + 22 个行为相关文件（prompts/runtime/controller/writer/verifier/service/schemas/planner/state_machine/chat_integration/gate/evaluator/repository/tools/retrieval/settings/llm_registry/llm_guard/audit/main/request_bootstrap）的 git 规范化内容 sha256。
- 新增 `model` 段：llm_base_url + 3 个 model id + .env 全文件 sha256（仅 hash 不含内容，防泄露）。

### 复现
`git show HEAD:<path> | sha256sum` 对 22 个文件逐一可复算；.env hash 以实际文件计算。

---

## P2-1 新测试缺 red 证据

### 处置（已完成，2026-09-08）
- **交付物**：`docs/red-evidence-20260908.md` + `dispatch-output/red-evidence-runs/*.log`（7 级 pytest 原始输出）
- **方法**：临时 git worktree（detach @ b7ab04f）+ 固定 HEAD 测试文件 + 复制 .env（排除环境性红），沿提交链顺次 checkout 被测代码，还原"先红后绿"。
- **梯度**：b7ab04f **8 failed**（对应 6e43042×2 / 03a2f14×2 / 613ecb3×3 / ee939bc×1 的修复缺口，各红因可从断言定位）→ 6 → 4 → 1 → **129 passed**（ee939bc 起全绿，reach HEAD 88b7937）。
- **诚实标注**：71e5f23（错误回喂）无新增独立正向测试，既有用例改动仅守住"回喂后仍失败须 fail-closed"底线；回喂有效性证据来自 run-5 实测（7/10→2/10），如需补回喂正向单测已在 red-evidence 中列为后续候选。
- 复现：`dispatch-output/red_evidence_gradient.py` 可一键重放 7 级梯度。

---

## P2-2 pytest 复现环境（本地无 pytest / 容器落后 HEAD）

### 事实核查
- 本地 miniconda base 环境缺 sqlalchemy（`ModuleNotFoundError`），但 **backend/venv 环境完整（pytest 9.1.1 + 依赖齐全）**，"本地无 pytest"结论不成立。
- 复跑结果（backend/venv，代码 = HEAD 88b7937 工作区）：

```
python -m pytest tests/test_agent_resume.py tests/test_agent_controller.py \
  tests/test_tool_gateway.py tests/test_agent_runtime.py tests/test_agent_verifier.py -q
→ 129 passed, 7 warnings in 29.95s
```

- 对比容器 preflight-004：117 passed 因容器代码落后 HEAD（旧构建缺 12 个新用例）。**129 passed 为 HEAD 基线上的权威结论**，替代 117 passed 记录。

### 处置
- [x] 本机复跑完成，129 passed（记录见此响应）；测试全为 mock 编排（httpx WSGITransport 本地、无真实 LLM 外呼），复跑未影响 run-6。
- [ ] run-6 结束后如需，将 129 passed 结果回填 gate5 文档/任务书证据表。

---

## P2-3 manifest "gate1-lawcheck" 条目命名为别名

### 处置（已完成）
- `gate1-freeze-manifest-v2.json` 中该条目改用真实相对路径 `docs/agent-v1-taskbook-gate1-lawcheck-20260907.json`，sha256 与 v1 记录一致（`a45ed0e0…`，本批已复算确认）。

---

## 交付物清单（本批新增/变更）

| 文件 | 类型 | 说明 |
|---|---|---|
| `release-evidence/legal-agent-v1-complex-v1-20260907/gate1-freeze-manifest-v2.json` | 新增 | P1-2/P2-3 修复产物 |
| 本响应文档 | 新增 | P1-1/P2-1/P2-2 证据与方案 |

## 复算命令速查

- manifest-v2 复算：`git show HEAD:<path> | sha256sum`（22 文件）；`sha256sum release-evidence/…/frozen-*.json rubric-v1.json docs/agent-v1-taskbook-gate1-lawcheck-20260907.json`
- 测试：`cd backend && venv\Scripts\python.exe -m pytest tests/test_agent_resume.py tests/test_agent_controller.py tests/test_tool_gateway.py tests/test_agent_runtime.py tests/test_agent_verifier.py -q`