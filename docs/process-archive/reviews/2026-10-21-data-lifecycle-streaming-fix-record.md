# 法智：第 5 轮只读审查修复记录（V5-01～V5-04）

日期：2026-10-21（北京时间）。本文件是**修复记录**，不改写
`2026-10-21-data-lifecycle-and-streaming-readonly-review-round5.md`（下称「原报告」）与任何历史审查报告。

## 1. 基线与复核

| 项 | 读数 |
| --- | --- |
| 修复开始时 HEAD | `e6abf681c0fecc82bbe4869dc0cdda64bfbecdc7`（与原报告一致） |
| 工作区 | 仅 `backend/venv-new/`、`frontend/coverage/` 未跟踪；无他人未提交改动 |
| 六处源码指纹 | `main.py` / `models.py` / `agent/repository.py` / `agent/service.py` / `lib/annotate.ts` / `lib/sse.ts` 的 SHA-256 **逐一与原报告第 7 节相同** |

四条发现均在源码层独立复核成立，未发现误报。执行范围按原报告第 8 节：只做最小修复，不顺带重构、不换依赖、**不部署**。

## 2. V5-01：删除后残留 AgentRun 可随数字 ID 复用恢复

### 复核

- `models.py`：`User → Conversation → Message` 有 ORM 级联；`AgentRun` 只有指向 `users` / `conversations` 的外键，**没有反向级联**。
- `main.delete_conversation` 与 `main.admin_delete_user` 修前均未处理 `AgentRun`（后者明确清理 Feedback / AnalysisRun，唯独漏 Agent 表）。
- `agent/repository.load_owned_run` 只比对 `run_id / user_id / conversation_id`；SQLite 数字主键复用后，旧 run 会被同号新会话重新认领。

### 修复（两层）

1. **删除时同事务清理**（`backend/main.py`）：
   - `delete_conversation`：先逐条 `db.delete(run)`（触发 `steps / evidence / claim_checks` 的 `delete-orphan` 级联），再删会话，同一 `commit`；
   - `admin_delete_user`：在删除用户前逐条删除该用户的 `AgentRun`。
   - 不用 `query.delete()`：批量删除会绕过 ORM 级联，留下子表孤儿。
2. **加载期身份守卫**（`backend/agent/repository.py`）：
   - `load_owned_run` 增加会话核验：会话必须存在、属于同一用户，且 `run.created_at >= conversation.created_at`。
   - 动机：升级**前**已存在于生产库的孤儿 run 不会被新删除逻辑回溯清理；而 run 不可能早于其所属会话创建，`run.created_at < conversation.created_at` 即证明这是被删旧会话的残留，拒绝恢复。该判据不依赖删除逻辑是否跑过。

### 证据（新增 `backend/tests/test_agent_run_delete_lifecycle.py`，4 条）

| 用例 | 判据 |
| --- | --- |
| `test_delete_conversation_removes_agent_run_and_children` | 删除后 conversations / messages / runs / steps / evidence / claims 全为 0；新会话复用同一数字 id；旧 `run_id` 加载为 `None` |
| `test_admin_delete_user_removes_agent_runs` | 账号删除后四类 Agent 记录全为 0 |
| `test_load_owned_run_rejects_pre_fix_orphan_after_id_reuse` | 用 `db.delete(conv)` 复刻修复前状态，留下孤儿 run；同号新会话建立后仍加载为 `None` |
| `test_delete_conversation_keeps_other_conversations_runs` | 只删目标会话，其他会话的 run 原样保留（防修成全局清空） |

### 限制与未做

- 未对生产库做任何清理或迁移：**存量孤儿 run 仍在**，但已无法被新会话恢复（加载守卫拦下）。若后续要求物理清理，需 Owner 授权并单独出对账脚本。
- 未开启 SQLite 外键执行（原报告已指出：现有外键无级联策略，开启可能直接阻断删除）。
- `Message.agent_run_id` 在会话删除时随消息一并删除；SQLite 外键当前未启用，故删除顺序不构成约束。
- 未做浏览器或完整 HTTP 验收；判据来自真实模型定义 + 迁移后的临时 SQLite。

## 3. V5-02：恢复后技术降级遗失已收集事实

### 复核

`main._resume_bootstrap` 修前只拼 `原法律争点：<issues.question>` 与 `用户补充：<answer>`，把 `state.user_question`、各争点 `facts` / `unknown_facts` 全部丢掉；该 bootstrap 在 `fallback_to_fast_path` 后直接进入 `prepare_fast_path → _build_messages`，检索与生成都看不到用户已提供的信息。

### 修复

新增 `main._resume_query_projection(state, answer)`，`_resume_bootstrap` 改为调用它。投影规则：

- `原问题：` 取 `state.user_question`（旧 state_json 无此键则整段省略）；
- `法律争点：` 取各 issue 问句；
- `已确认事实：` 取各 issue 的 `facts.statement`，跨争点去重；
- `仍待确认：` 取各 issue 的 `unknown_facts.statement`，**单独成段、不并入事实**；
- `用户补充：` 取本次回答；
- 不带工具原始载荷、不包含 `source_ref` 等内部字段；`law_as_of` 仍由 `_resume_bootstrap` 原样传递，未改基准日逻辑。

`user_text / raw_query / supplement_text` 三者同源，保证检索与生成输入一致。

### 证据（`backend/tests/test_agent_resume.py` 新增 3 条）

| 用例 | 判据 |
| --- | --- |
| `test_resume_query_projection_keeps_original_question_and_facts` | 输出含原问题、已确认事实、仍待确认项、本次回答；未知事项不出现在事实段 |
| `test_resume_projection_omits_empty_sections` | 旧 state 无 `user_question` / 事实时不产生空标签，输出与最小投影逐字相等 |
| `test_agent_fallback_on_resume_feeds_persisted_facts_into_bootstrap` | 端到端：恢复 → `PLANNER_PARSE_ERROR` 降级 → 捕获的快车道 bootstrap 含原问题与事实，且 `raw_query == user_text == supplement_text` |

### 限制

- 未执行真实 Planner 故障或真实模型回答；降级原因以 `PLANNER_PARSE_ERROR` 模拟（该原因在允许技术降级集合内）。
- 事实的**文本长度**未做截断：`contract_max_chars` 等既有上限在后续 `_build_messages` 不变，本轮未新增裁剪规则。
- O5-02（历史会话切回后不能续跑）属旧 H-03，未在本轮修复。

## 4. V5-03：金额区间单位被替换成 `$3`

### 复核

`lib/annotate.ts` 两处金额区间正则（外层标注与引号内高亮各一处）把单位写成**非捕获组** `(?:万元|万|元)`，替换串却引用 `$3` ⇒ 输出字面 `$3`，原文单位丢失。

### 修复

两处均改为捕获组 `(万元|万|元)`，替换串 `$1`/`$2`/`$3` 与分组数对齐。未动其他高亮规则与 Markdown 排版。

### 证据（`frontend/tests/annotate.test.ts` 新增 1 组）

去掉 HTML 标签后逐字比对：`赔偿100至200万元。→ 赔偿100-200万元。`、`赔偿100-200元。→ 赔偿100-200元。`、`赔偿100~200万。→ 赔偿100-200万。`、`赔偿1.5至2.5万元。→ 赔偿1.5-2.5万元。`、引号内 `「赔偿100-200元」` 保持不变；并断言输出不含 `$3`。

### 限制

- 只覆盖本次发现的「元 / 万元 / 万」与 `- ~ ～ 至 到` 连接符；未穷举所有金额形态。
- 未在浏览器中做视觉验收（渲染器为纯函数，判据是去标签后的文本等义）。

## 5. V5-04：正文中的 `[DONE]` 被当成结束哨兵

### 复核

`lib/sse.ts` 修前条件为 `line.includes("[DONE]")`，任何包含该字面量的整帧都被丢弃。后端把 Agent 完整答案放在单个 `token` 事件里，因此一次误过滤会丢掉整段回答。

### 修复

取出 `data: ` 之后的**帧体**，仅当 `body.trim() === "[DONE]"` 时才视为结束哨兵；正文与 JSON 字段内的同名字面量原样保留。

### 证据（`frontend/tests/sse-frame.test.ts` 新增 2 条）

| 用例 | 判据 |
| --- | --- |
| 正文 JSON 里含 `[DONE]` | 该帧保留，紧随其后的独立 `data: [DONE]` 仍被忽略 |
| 哨兵形态边界 | `data:  [DONE]  ` 与 `data: [DONE]` 忽略；`data: [DONE]x` 保留 |

### 限制

- 输入为合成帧，未跑浏览器与真实模型流；O5-03（无结束帧的干净 EOF）未在本轮处理，仍缺真实入口证据。

## 6. O5-01 / O5-02 / O5-03 处置

| 编号 | 本轮处置 |
| --- | --- |
| O5-01（内部重跑残留旧覆盖状态） | **未修**。仅内部 `execute_agent_request` 可达，公开入口要求 `WAITING_USER`；未借机开放公开重跑入口。如实标为「内部恢复契约缺陷 / P2 候选」。 |
| O5-02（待澄清会话切回后不能续跑） | **未修**，与旧 H-03 同源，不重复建票；原报告复现证据可直接用于 H-03 修复。 |
| O5-03（缺结束帧的干净 EOF） | **未修**，尚无现役代理产生该形态的入口证据，保留为协议专项后续项。 |

## 7. 门禁与回归（新鲜运行）

| 项 | 命令 | 读数 |
| --- | --- | --- |
| 后端目标用例 | `pytest tests/test_agent_run_delete_lifecycle.py tests/test_agent_resume.py tests/test_agent_repository.py tests/test_agent_controller.py -q` | **118 passed**，rc=0 |
| 后端全量非 slow | `pytest -m "not slow" -q`（`backend/venv`，生产同栈） | **1940 passed, 2 skipped, 18 deselected**，rc=0，481.61 s |
| 后端 ruff | `ruff check` + `ruff format --check`（改动文件） | 全部通过 |
| 后端 mypy | `mypy agent/repository.py` | Success: no issues |
| 前端单测 | `npx vitest run` | **9 files / 86 tests passed** |
| 前端 lint | `npm run lint` | 无告警与错误 |
| 前端类型 | `npx tsc --noEmit` | 无输出（通过） |
| 前端格式 | `npx prettier --check`（本次 4 个文件） | 全部符合 |

## 8. 未做与已知限制

1. **本记录落笔时未部署**（按原报告 §8「不部署」）；随后 Owner 以「继续」授权上线，实际执行与核验见 §9。
2. **未做浏览器/真实模型验收**：判据均为针对性行为用例；V5-02 未证明真实模型输出变化，V5-03/V5-04 未做视觉与流式端到端。
3. **`mypy .` 全树既有 4 条错误未修**（`main.py` 媒体清理处的 `image_ref/thumb_ref` 注解缺失），位于本轮未改动行，避免扩大 diff。
4. **`npm run format:check` 全树仍有 4 个既有文件不通过**（`app/admin/sections/StatsSection.tsx`、`UploadSection.tsx`、`UsersSection.tsx`、`lib/coverage.ts`），均为本轮未改动文件；本次改动的 4 个前端文件单独跑 Prettier 全绿。
5. **生产库存量孤儿 run 未物理清理**：加载守卫已阻止其恢复；若要物理删除需 Owner 授权后单独对账。
6. 未修改原报告与任何历史审查报告。

## 9. 上线执行与核验（2026-10-21）

### 执行

1. 清除当前 shell 的机器级 `SILICONFLOW_API_KEY` 旧值（R11），再 `docker compose build backend frontend`。
2. `docker compose up -d backend frontend`，两容器均重建重启；`fazhi-caddy` 未动（沿用 41h 运行实例）。

### 核验（新鲜运行）

| 项 | 命令 / 方式 | 读数 | 判定 |
| --- | --- | --- | --- |
| 凭据未回退旧值 | 容器内 `sha256(SILICONFLOW_API_KEY)[:12]`（不打印值） | `fp=e6e7547bbfa5 set=True` | 与 `.env` 有效值一致 |
| 后端健康 | `GET http://localhost:8088/api/health` | 200 | 通过 |
| 登录页 | `GET http://localhost:8088/login` | 200 | 通过 |
| 分片绝对基址 | 抓取登录页 8 个 `_next/static/*.js` 并匹配 `162.14.81.34` / `localhost:8000` | `chunks=8 bad_chunks=0` | 同源相对路径生效 |
| 镜像内绝对基址 | `grep -rl "162.14.81.34" /app/.next /app/public`（前端镜像） | 无命中（rc=1） | 通过 |
| 转写路由存在 | `POST /api/chat/transcribe`（无凭据） | 401 | 路由存在且受鉴权（非 404） |
| V5-01 代码在镜像内 | `grep -c "V5-01" /app/main.py` | 2 | 已上线 |
| V5-02 代码在镜像内 | `grep -c "_resume_query_projection" /app/main.py` | 2 | 已上线 |
| 孤儿守卫在镜像内 | `grep -c "run.created_at < conversation.created_at" /app/agent/repository.py` | 2 | 已上线 |
| 语音分派 | 容器内 `registry.pick_entry("voice","flag")` | `key=voice_sf`；`model=XingChenAGI/XingChenASR-V3.2-Ultra`；`transport=audio_transcriptions`；`host=api.siliconflow.cn` | R15 修复生效 |

### 限制

- 未做**真实登录后的** `/api/chat/transcribe` 端到端（需 Owner 凭据），仅以前一阶段的应用端点实测 200 为基线，本轮核验到「路由可达 + 分派正确 + 传输通道正确」。
- 未做浏览器视觉验收（V5-03 高亮、V5-04 流式）；前端为静态分片级核验。
- 存量孤儿 run 仍未物理清理，仍由加载守卫拦截。

## 10. 授权后追加核验（2026-10-21）

### 10.1 存量孤儿 run 对账（只读）

判据沿用 §2 的稳定身份守卫三项：所属会话缺失 / 会话与 run 的 `user_id` 不一致 / `run.created_at < conversation.created_at`。

| 项 | 读数 |
| --- | --- |
| `agent_runs` 总数 | 291 |
| `conversations` 总数 | 2237 |
| 孤儿 run | **0**（三项原因均为 0） |
| `agent_steps` / `agent_evidence` / `agent_claim_checks` | 2977 / 1670 / 158 |
| 状态分布 | waiting_user 47、failed 99、stopped 14、planning 3、drafting 83、completed 45（无 `executing`） |

结论：**现网不存在孤儿 run，无删除动作**。此前「存量孤儿 run 未物理清理」是风险假设（编号复用可能造成孤儿），不是现网事实，据实更正。

限制：仅做上述静态判据，未对 `planning` / `drafting` 存量做陈旧度判定；未改动任何一行数据。

### 10.2 语音转写端到端（真实 provider，临时账号）

容器内新建临时用户（随机密码，不打印）→ 签发 JWT → 以 1 秒 440 Hz 合成 WAV 调 `POST /api/chat/transcribe` → 立即删除该用户及其会话/消息。

| 项 | 读数 |
| --- | --- |
| HTTP 状态 | 200 |
| 耗时 | 1.29 s |
| 返回文本长度 | 0（纯音无人声，符合预期） |
| 残留数据 | `created_conversations=0`、`created_messages=0`、`user_removed=true` |

结论：`audio_transcriptions` multipart 通道在真实 provider 上可用，鉴权与限流路径正常，临时数据已按预期清理。

限制：输入为合成音而非真实人声，`text_len=0` 不能证明识别质量；未用真实账号在浏览器录音验证，该人工验收仍归 Owner。
