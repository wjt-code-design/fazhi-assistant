# S8 只读取证：默认配置下 `/api/chat` 实际命中哪个出口（2026-09-19）

## 0. 一句话结论

**形态 1 / 2 / 3 全部实测命中 (B)——第二处 `stream_with_retry(`（本轮工作树 `main.py:1975`）。
(C) 缓冲轻量出口在默认配置下一律走不到，唯一原因是 `registry.has_role("text","light") == False`
（模型注册表里根本没有 light 档），不是因为分支代码死了。**

⇒ **给 (C) 单独加"法律版本判定门"= 把门加在一条当前零流量的出口上，正是本项目说过的"假接线"形状。**
门必须同时落在 **(B) `:1975`**（≈全部文本流量）和 **(A) `:1832`**（合同评审）上才叫真接线。
（见 §5：截至本报告写作时，工作树里 S5 的在飞改动**已经**把 `law_as_of` 只接到了 `_light_buffered`。）

---

## 1. 行号坐标系（重要：`main.py` 正被 S5 实现 agent 并发改动，行号在漂）

brief 给的 `1761 / 1902 / 1831` 在 **2026-09-19 22:3x 的工作树里复验是对的**（我第一次 grep 原样命中，见下）。
但取证运行期间 `git status` 出现 `M backend/main.py`（S5 在加 `NOTE_LAW_VERSION` / `_law_version_gate`），
同一批锚点在 **23:2x 已漂到 `1832 / 1975 / 1902`**。所以本文件**以分支身份为主，行号双标**。

### 1a. 首跑复验（brief 的原始行号，grep 原文）

```
$ grep -n "stream_with_retry(" main.py
1761:                async for piece in stream_with_retry(
1902:            async for piece in stream_with_retry(
$ grep -n "_light_buffered" main.py
1155:def _light_buffered(pre: dict, messages: list) -> _LightResult:
1161:        return _light_buffered_locked(pre, messages, modality, ctx_present, lkey, llm)
1164:def _light_buffered_locked(...)
1831:                res = await run_in_threadpool(_light_buffered, pre, messages)
$ grep -n "use_light" main.py
1567:    use_light = use_router and tier == "light" and modality == "text" and registry.has_role("text", "light")
1569:        use_light = False  # 合同评估强制旗舰流式（确定性骨架的报告生成）
1591:    if use_router and not use_light:
1830:            if use_light:
```

### 1b. 定稿那次运行的行号（探针进程内 `anchors_snapshot_for_this_process`，与 `exits_hit` 同源，零漂移）

```
"anchors_snapshot_for_this_process": {"main_path": "C:\\...\\backend\\main.py", "main_mtime": 1789830935.569811,
  "stream_with_retry_callsites": [1832, 1975], "light_buffered_callsite": [1902], "use_light_def": [1638]}
```

⇒ **A = 第一处 `stream_with_retry(` = brief:1761 = 本轮:1832**
⇒ **B = 第二处 `stream_with_retry(` = brief:1902 = 本轮:1975**
⇒ **C = `res = await run_in_threadpool(_light_buffered, ...)` = brief:1831 = 本轮:1902**

### 1c. A/B 的身份不是靠读码推断的，是**正向对照实验**证出来的

合同文本请求实测命中**第一处**且 SSE 带分支 0.3 独有的 `{"type": "step"}` 进度事件：

```
@@S8@@ {"scenario": "contract_positive_control", "status": 200, ... "pre": {... "contract_data": true ...}, "exits_hit": [{"exit": "stream_with_retry", "call_lineno": 1832, "caller_func": "stream", "n_messages": 2}], ... "body_head": "data: {\"type\": \"status\", \"msg\": \"正在思考…\"}\n\ndata: {\"type\": \"step\", \"steps\": [{\"label\": \"解析合同\", \"detail\": \"识别 6 个条款\"}, {\"label\": \"匹配法条\", \"detail\": \"定位 12 条法条依据\"}, {\"label\": \"风险初判\", \"detail\": \"总体风险等级：中\"}]}\n\n...", "body_has_step_event": true, ...}
```

### 1d. 配置默认值实测（探针内读 `main.settings`，非读 settings.py）

```
@@S8@@ {"scenario": "zz_anchor_line_map", ..., "config_defaults": {"feature_router": true, "agent_enabled": false}, "registry_roles": ["text/flag"]}
```

---

## 2. 命令原文

探针文件（临时，**已删除**）：`backend/tests/test_zz_probe_s8_exit_forensics.py`

```
cd /c/Users/33393/Desktop/ai-legal-helper/backend && ./venv/Scripts/python.exe \
  -m pytest tests/test_zz_probe_s8_exit_forensics.py -q -s \
  --basetemp="C:/Users/33393/AppData/Local/Temp/s8bt9" -p no:randomly
```

```
8 passed, 8 warnings in 91.66s (0:01:31)
```

（basetemp 全程在 `AppData/Local/Temp`，未落在 `backend/` 内。）
完整 stdout：本目录 `pytest-stdout.log`；结构化 trace：本目录 `trace.json`。

---

## 3. 我 patch 的符号名（模型边界全部打桩 ⇒ 零真实模型调用、零付费网络）

| patch 目标 | 做法 | 判哪个出口 |
|---|---|---|
| `main.stream_with_retry` | 普通函数；进内即 `sys._getframe(1)` 抓 `f_lineno` / `f_code.co_name`；返回记录型 async generator，yield 两个假分片 | **(A)/(B)** |
| `main._light_buffered` | 记录进入 + 返回 `main._LightResult(...)`；签名收 `*rest` 以兼容在飞的 `law_as_of` 新参 | **(C)** |
| `main.run_in_threadpool` | 仅当被包装的 func 带 `_is_light_probe` 标记时抓调用方行号（否则透传）——因为 (C) 的调用点是 `run_in_threadpool(_light_buffered, ...)`，帧不在 `stream()` 里 | **(C) 的行号** |
| `main._prepare_fast_path_only` | 包一层，抓真实 `pre`（intent / `len(sources)` / `contract_data` / `len(recent)` / `conv_id`） | 定位 **(D)** 与路由入参 |
| `clarify.decide` | 包一层，记录 `strategy` | 区分 **(D) 分支 0.5** |
| `main._post` / `main._post_placeholder` / `main.grounded_top_score` | no-op / `-> 0.0` | 掐掉落库后的沉淀与压缩 LLM 调用 |
| `main._contract_convs` / `main._contract_reviewed_convs` / `main._clarified` | 置空 | 用例间会话态隔离（首轮结论曾被它污染，已修并复跑） |
| `langchain_openai.ChatOpenAI._generate/_stream/_astream/_agenerate` | **tripwire：一旦被调即 `raise AssertionError("REAL LLM CALL BLOCKED")` 并记账到 `real_llm_attempts`** | 硬保证零真实模型调用 |
| 鉴权 / DB | `main.app.dependency_overrides[get_current_user]`；`tmp_path` SQLite + conftest 已无条件隔离的 `DATABASE_URL`/`QUOTA_DB`/`CHROMA_DIR` | 端点级真实请求 |
| 检索语料 | conftest 的 `real_kb` fixture（只读重绑 `retrieval.vectorstore` 到真实 `chroma_db`），使 `pre["sources"]` 真非空 | 形态 3 |

零真实调用的证据就是每条 trace 的 `"real_llm_attempts"` 字段：8 个用例里 7 个是 `[]`。唯一非空的那条见 §4 形态 3b——
那是一次**被打桩掐死**的尝试，没有出网。

---

## 4. 逐形态结论

### 形态 1：会被判成 light-text 的普通法律问题 → **(B)**

请求 `{"content": "试用期最长可以约定多久？", "no_cache": true}`

```
@@S8@@ {"scenario": "form1_light_text", "status": 200, ... "pre": {"intent": "legal_query", "n_sources": 21, "contract_data": false, "n_recent": 0, "conv_id": 1}, "clarify_strategy": "direct", "exits_hit": [{"exit": "stream_with_retry", "call_lineno": 1975, "caller_func": "stream", "n_messages": 2}], ... "assess_tier": "light", "assess_modality": "text", "admit_light": true, "registry_has_text_light": false, "registry_has_text_flag": true, "settings_feature_router": true, "settings_agent_enabled": false}
```

**关键**：路由**确实**判 light 且准入通过（`assess_tier="light"`、`admit_light=true`、检索命中 21 条、单轮），
但 `registry_has_text_light=false` ⇒ `use_light`（`main.py` 本轮 `:1638` / brief `:1567`）被短路成 `False` ⇒ 落分支 2。
SSE 尾部还带 `注：该问题较复杂，本回答仅供参考。`（旗舰自检 FAIL 的 `NOTE_COMPLEX`）——它是**被当旗舰答的**。

### 形态 2：旗舰 / 复杂法律问题 → **(B)**

```
@@S8@@ {"scenario": "form2_flag_complex", ... "pre": {"intent": "legal_query", "n_sources": 34, "contract_data": false, "n_recent": 0 ...}, "clarify_strategy": "direct", "exits_hit": [{"exit": "stream_with_retry", "call_lineno": 1975, ...}], ... "assess_tier": "flag", ... "admit_light": false, "registry_has_text_light": false}
```

### 形态 3：带检索命中 / 续聊 → 两个子形态都是 **(B)**

**3a 检索命中（`sources`=19 条，且 tier 判 light）**

```
@@S8@@ {"scenario": "form3a_sources_nonempty", ... "exits_hit": [{"exit": "stream_with_retry", "call_lineno": 1975, ...}], ... "assess_tier": "light", "admit_light": true, "registry_has_text_light": false}
```

（附带事实：`complexity.admit_light` 的硬条件之一就是检索命中 ⇒ 在本项目里"light-text"与"带检索命中"
**是同一个形态**；无命中的短问题在 `main.py` 路由段就被直接升 `flag`。）

**3b 真续聊（第二轮带同一 `conversation_id`，`n_recent=1`）**

```
@@S8@@ {"scenario": "form3b_continuation", ... "pre": {"n_sources": 21, "contract_data": false, "n_recent": 1, "conv_id": 1}, "exits_hit": [{"exit": "stream_with_retry", "call_lineno": 1975, "caller_func": "stream", "n_messages": 3}], "real_llm_attempts": ["qwen3.7-max-2026-06-08"], ... "assess_tier": "flag", "admit_light": false, "turn": "second", "conv_id_reused": 1}
```

多轮 ⇒ `_multi_turn` ⇒ 升 `flag` ⇒ 同样 (B)。
`real_llm_attempts` 非空**不是破口**，它顺手证了另一件有用的事：**续聊在 `_pre` 阶段就会烧一次真实旗舰 LLM 调用**
（`main._rewrite_for_retrieval`，多轮检索改写）。tripwire 把它 raise 掉、`rewrite_query` 自己吞异常回退原 query，
请求仍 200、出口判定不受影响，**且没有任何一次请求真的出网**。

### 反事实（**不是**默认配置，只为回答"(C) 是死代码吗"）

把 `main.registry.has_role` 强行 patch 成恒 `True`，同一句 light-text：

```
@@S8@@ {"scenario": "counterfactual_forced_light_role", ... "exits_hit": [{"exit": "_light_buffered_callsite", "call_lineno": 1902, "caller_func": "stream"}, {"exit": "_light_buffered", "caller_func": "run"}], "real_llm_attempts": [], ... "registry_has_text_light": true, ... "note": "COUNTERFACTUAL: has_role patched True, not default config"}
```

⇒ **(C) 是活代码**：只要注册表里出现 `text/light` 条目，同一条请求立刻改命中 `_light_buffered`，
调用点行号 `1902` 与锚点 `light_buffered_callsite: [1902]` 逐字对上。
所以 (C) 走不到的**唯一**原因是配置，不是分支写死。

注册表实测：`"registry_roles": ["text/flag"]`。
来源：`backend/.env:27 LLM_MODELS_JSON=[...]` 六个条目**全**是 `"tier":"flag"`；
代码兜底 `llm_registry.py:31 DEFAULT_ROLES` 亦无 light
（`grep '"tier":' llm_registry.py` → 27 处全是 `"flag"`，另有 2 处 `"utility"` 是 rerank/embedding，不参与 `has_role("text","light")`）。

### 缓存截胡（(D) 候选）探针

同一句 light-text，`no_cache=False` 连发两次（第二次可能命中分支 0 / 0.2）：

```
@@S8@@ {"scenario": "form1_caches_on", ... "exits_hit": [{"exit": "stream_with_retry", "call_lineno": 1975, ...}], ... "note": "no_cache=False, 2nd identical request (cache-interception probe)", "cache_write_gate": true}
```

⇒ 第二次仍是 (B)。但原因要说清：假分片答案过不了写缓存的自检/确定性写闸，**缓存从未被填**，
所以这**不能**证明生产上缓存不会截胡。见 §6。

---

## 5. 对 S5 的直接含义

1. **(C)（`_light_buffered`）在默认配置下保护不了任何线上流量** —— 除非先往 `LLM_MODELS_JSON` 里加一个
   `"tier":"light"` 的文本模型。截至本报告写作（23:2x）工作树里的在飞改动是
   `main.py:1902  res = await run_in_threadpool(_light_buffered, pre, messages, body.law_as_of)` 与
   `main.py:1174 def _law_version_gate(res, fact_texts, law_as_of)`，两处 `stream_with_retry(` 均未接门
   ——**这就是假接线的形状**：门看着接上了，流量全从 (B) 走。
2. 必须补门的第一优先：**(B) 第二处 `stream_with_retry(`（本轮 `:1975` / brief `:1902`，分支 2 旗舰流式）**——
   三种形态 100% 落这里，≈全部文本流量。
3. 第二：**(A) 第一处 `stream_with_retry(`（本轮 `:1832` / brief `:1761`，分支 0.3 合同评审）**。
   注意 `main.py` 里有 `if pre.get("contract_data") and use_router: use_light = False` ——
   **合同路径无论有没有 light 模型都不会走 (C)**，所以只在 (C) 加门连合同流量也一起漏。
4. 第三类易漏：**在流式出口之前就 `return` 的零 token 分支**（都属 (D)），产出的文本同样可能带法律版本结论。
   本轮工作树 grep 到的 `return` 行号（**除 `:1792` 外均未经执行证明**；会随 S5 改动继续漂）：
   - 分支 0 精确/近重复缓存直返 `return` @ `:1705`（`# 分支0：` 注释在 `:1678`）
   - 分支 0.2 QA 语义缓存直返 `return` @ `:1734`（注释 `:1707`）
   - 分支 0.5 clarify / refuse `return` @ `:1763`（注释 `:1736`）
   - 分支 0.3 合同 `need_clarify` 反问 `return` @ `:1792`（`if cd.get("need_clarify"):` 在 `:1768`）
     ——**这条本探针实测命中过**：
     一次被 `_contract_convs` 污染的运行里，同一句 light-text 的 `exits_hit` 为 `[]`、SSE 直接回了
     `CONTRACT_CLARIFY_PROMPT` 全文（"请补充以下信息，我才能给出准确的合同风险评估…"）。
     隔离修复后该现象消失，说明它是真会被走到的分支，不是理论。
   - 另有分支 0.3 尾部 `return` @ `:1898`、分支 1（轻量）尾部 `return` @ `:1939`。
5. 票的量级建议：**(B) 大票（全部文本流量）/ (A) 中票（合同子集）/ (C) 现为 0 流量，门留着当防御性代码可以，
   但不得据此声称"某路径已受保护"**。

---

## 6. 未证 / 边界（诚实标注）

- **未证：分支 0 / 0.2 缓存命中是否会把 light-text 抢成 (D)。** 探针的假答案进不了缓存（写闸把它拦了），
  "命中"这一态没复现。要证它得预置 `answer_cache` 条目，或让替身返回一条能过 `quality.self_check` 的假答案。本探针没做。
- **未证：vision（图片）形态的归属。** `modality == "text"` 是 `use_light` 的硬条件 ⇒ 图片必不走 (C)；
  但 A/B 归属未测（当前配置下 `registry.has_modality("vision")` 会先返回 501）。
- **未证：`agent_enabled=True` 下的分布。** 本次严格锁默认 `False`。
- **结论的配置面前提**：结论对"注册表无 `text/light`"敏感。该事实来自本机 `backend/.env`（未跟踪、只读、未改动）
  + `DEFAULT_ROLES` 兜底，两者实测都不含 light。**若部署环境加了 light 档，形态 1/3a 会立刻翻成 (C)**
  （反事实用例已证明）。⇒ 任何"(C) 不受保护"的表述都应写成"当前配置下"，而不是"永远"。
- `real_kb` 只读重绑 `retrieval.vectorstore`（conftest 自述的覆盖面）；`knowledge_service` 的 QA 集合仍指向隔离空库，
  故分支 0.2 恒不命中——这也是上一条"未证"的成因之一。
- **行号坐标系风险**：取证期间 `main.py` 被另一 agent 并发修改（`git status` 曾报 `M backend/main.py`，
  锚点从 `1761/1902/1831` 漂到 `1832/1975/1902`）。本报告的 `exits_hit.call_lineno` 与其所在用例的
  `anchors_snapshot_for_this_process` 出自**同一次运行、同一进程**，已消除该风险；
  但**引用本报告行号时请先按锚点文本重新 grep 一次**。

---

## 7. 清理确认

```
$ rm backend/tests/test_zz_probe_s8_exit_forensics.py
$ ls backend/tests/test_zz_probe_*
ls: cannot access 'backend/tests/test_zz_probe_*': No such file or directory
$ cd /c/Users/33393/Desktop/ai-legal-helper && git status --porcelain backend/
 M backend/main.py
 M backend/observability.py
 M backend/settings.py
?? backend/.ptmp-s4-run2/
?? backend/tests/test_fast_path_law_version_gate.py
```

**本任务对 `backend/` 的净改动：零。** 上面 3 个 `M` + 1 个 `??test_fast_path_law_version_gate.py`
**不是本取证任务的产物**：本任务开工时同一条命令的输出**只有一行**
（`?? backend/.ptmp-s4-run2/`，逐字为：`?? backend/.ptmp-s4-run2/`），
其余改动是 S5 实现 agent 在我取证期间并发写入的（`main.py` 里新增 `_law_version_gate` / `NOTE_LAW_VERSION`、
`settings.py` 新增开关、`observability.py` 登记日志字段、以及那条 gate 测试）。
本任务从未写入任何被跟踪文件、未 commit、未 push、未跑全量套件、未跑 `run_gate_full.py`。

本任务留下的全部产物（均在仓库根的 `dispatch-output/` 下，非 `backend/`）：

- `dispatch-output/s8-stream-probe-20260919/report.md`（本文件）
- `dispatch-output/s8-stream-probe-20260919/pytest-stdout.log`（定稿那次运行的完整 `-s` stdout，含 8 条 `@@S8@@` 原始行）
- `dispatch-output/s8-stream-probe-20260919/trace.json`（结构化 trace，同一次运行）
