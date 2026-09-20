# 票 C / S6 · 快车道流式出口的版本判定（S5 那道门今天够不着的那一条）

起票依据：S5（`dec7a95`）把法律版本绊线补在了**缓冲轻量出口**上。S5 交完后的执行取证（票 A）+ 本会话独立复量
证明：**当前部署配置下那条分支零流量** —— `llm_registry` 实配的 `(modality, tier)` 全集只有一个
`('text','flag')` ⇒ `has_role('text','light')=False` ⇒ `use_light` 恒假。默认配置的三种法律问句形态
**全部**走第二条 `stream_with_retry(`。⇒ 快车道真正的裸奔面一点没缩，本票补的就是这一格。

**⚠️ 与 S5 相反的一句话先说：这张票比 S5 票面当初假设的便宜，但比 S5 危险。**
- 便宜：票面 §2 说流式"必须先在流尾收口 = 改用户可见的流式行为"——**这句是错的**。
  两处流式出口在循环结束后**本来就有** `answer = "".join(chunks)`（为落库和写缓存收的口），
  收口免费。真正要定的只是"命中之后怎么呈现"，而这个决定本仓**已经裁过四次**（见 §2 的注记家族）。
- 危险：这条是**线上唯一在承接流量的出口**。接错 = 直接把"已受保护"变成假话第二回。

**你要做的事，三句话**
1. 给主流式出口（符号锚点 `answer = "".join(chunks)` 在主流式分支的那一处）加一道与 S5 同款的版本绊线门，
   判定仍**只**调 `limitation_calc.law_version_crosses_watershed`。
2. 交付的是证据不是代码：亲眼红过的定向测试 + 默认关逐字比对 + ≥3 道变异 + 一次 RUN_VALID 门禁（§6/§7）。
3. 按 §10 回报，且报告里必须保留 §3 登记的未覆盖面（**缓存直返那两条通道不在本票范围内**，见 §4-Q1 为何这么定）。

**起步命令**（venv 在 `backend/` 下，不是仓库根；门禁 cwd 必须是 `backend/`）
```bash
cd /c/Users/33393/Desktop/ai-legal-helper/backend
./venv/Scripts/python.exe -m pytest tests/test_fast_path_law_version_gate.py tests/test_tiering.py -q   # S5 的同族测试，先读它们建立形状
./venv/Scripts/python.exe ../dispatch-output/te-chroma-isolation-20260918/run_gate_full.py <你的标签>
```
⚠️ **本票所有行号一律按符号锚定，不许照抄**：本文件写就之后 `main.py` 只要被动过一次，
S5→本票之间已经实测漂过两次（`1761/1902` → `1832/1975` → **`1844/1987`**，第二次就是 `ruff-format` 干的）。

---

## 0. 授权边界（越界即停手回报）

- **不改任何开关默认值**（`fast_path_law_version_check` 必须保持 `False`，谁都不许为了验证去改它）。
  ⚠️ 2026-09-20 订正：本行原文写"不许复用 S5 开关的语义、等 §4-Q4 答复"，现 Q4 已裁**复用**（见 §4b），
  但复用**附带一条硬性交付**：必须同步改 `settings.py` 的范围注释，见 **§5-8**，不做就是留一条假话在配置文件里。
- **不动 `backend/agent/**`**（判定真源只消费）。
- **不重跑付费三臂**；本票所有断言离线、不调模型。
- **不推送、不部署**。
- 冻结资产勿动：`backend/scripts/gate2_runner.py` sha256 须保持 `ae2e4120…47e295`（S5 收口时实测仍相符）。
- **不许改 `evals/watershed-cases-r15.json`**（标的是 `NOT_FROZEN`：可取形状，不可拿分数当判据）。

## 1. 开工前置取证（任何一条不符就停下报告）

| # | 命令 | 期望 | 为什么 |
|---|---|---|---|
| P1 | `pwd -W` | 以 `\ai-legal-helper` 结尾 | 本仓发生过"在 Desktop 上 grep 然后宣布文件不存在" |
| P2 | `git status --porcelain backend/main.py` | **空** | 单写者车道；非空就是有人在途 |
| P3 | `git diff --numstat HEAD -- backend/main.py` | 空 | 与 P2 双证 |
| P4 | `grep -n "async for piece in stream_with_retry(" backend/main.py` | **恰好 2 处** | 本票的射程 |
| P5 | `grep -n 'answer = "".join(chunks)' backend/main.py` | **恰好 2 处**，各在 P4 之后几行 | 收口点已存在（本文核心事实，必须亲眼复跑） |
| P6 | `grep -n "def _law_version_gate\|def _fast_path_fact_texts" backend/main.py` | 各 1 处（S5 留的） | 复用，别写第二份 |
| P7 | `grep -n "_check: bool = False" backend/settings.py` | ≥5 处（S5 后含 `fast_path_law_version_check`） | 新开关落同族 |
| P8 | `grep -n "def _post(\|_qa_direct_return\|def _cache_write_ok" backend/main.py` | 三符号都在 | §4-Q1 的取舍依赖它们 |
| P9 | `./venv/Scripts/python.exe -c "from llm_registry import registry; print(sorted({(e.modality,e.tier) for e in registry._entries.values()}))"` | 读什么记什么 | 决定"这道门今天有没有流量"。**若这一步量出 `('text','light')` 已存在，S5 那条门就已生效，本票优先级要重排 ⇒ 回报，别自行开工** |

## 2. 事实底座（2026-09-20 00:1x 本会话实测，`file:line` 当时可复跑）

### 2a 流量到底落在哪
| 出口 | 锚点 | 承流量？ | 证据 |
|---|---|---|---|
| 缓冲轻量 | `run_in_threadpool(_light_buffered, pre, messages, body.law_as_of)` | **当前配置下否** | P9 + `use_light` 四合取末项恒假 |
| 合同流式 | 第 1 处 `async for piece in stream_with_retry(`，其后 `answer = "".join(chunks)` | 仅合同评估请求 | 该分支被 `use_light = False` 强制走流式 |
| **主流式** | 第 2 处 `stream_with_retry(` + 其后的 `answer = "".join(chunks)` | **是——三种问句形态实测全走这里** | 票 A 执行取证 + 本会话复量 |

### 2b "流式已发出怎么办"本仓已经裁过四次（这就是 §4-Q1 的答案库，别重新发明）
主流式出口在 `answer` 收口之后，连续存在**同形状**的四段处置：
1. 引用不在库 → `answer += note` + `yield` 一帧 `content` + `log_account(kind="citation_anomaly", detail=…)`；
2. 多选漏答 → 同形状，且把 `multi_bad` 加进**写缓存条件**（注释原话：*"流式已发出，只能追加确定性核对注（不静默）+ 拦缓存（防错答传播）"*）；
3. 自检 FAIL → `answer += NOTE_COMPLEX` + `yield` 一帧；
4. 回退模型也不可用 → `answer += NOTE_QUOTA` + `yield` 一帧。

⇒ **"已经吐出去的帧怎么算"不是未解问题，是已解问题**：不收回、不重放，追加一帧确定性注记 + 拦缓存。
本票的注记叠在既有注记之后即可，无需新机制。

### 2c 收口点的真实形状（本票唯一要动的地方）
第 2 处循环之后依次是：`answer = "".join(chunks)` → 空答时走 `_invoke_llm` 非流式兜底并**另有一次** `answer = clean_answer(fb)` →
否则 `answer = clean_answer(answer)` → §2b 的注记家族 → 自检 → 写缓存 → 落库 `_post(pre, answer)`。

⚠️ **两个容易漏的点（S5 的"漏 return 点"同款，这里换了形状）**：
- **兜底路径**：`_invoke_llm` 那条分支产出的 `answer` 与流式 join 的是**两个不同来源**，门必须都过；
  只接流式那条 = 空答兜底时门消失。
- **空答**：`if not answer:` 会 yield 一帧 error。门**不得**给空答追加注记（否则把"没答上来"伪装成"答了但仅供参考"）——
  S5 用 `(text + NOTE) if text else ""` 处理，本票照抄。

### 2d 判定输入的取法（S5 已经定过，直接复用）
`_fast_path_fact_texts(pre)` = `user_text` + `rewritten` + `recent` 里 **role==user** 的消息。
**刻意不含 `context` / `sources`**（那是法条文本，旧法必然带分水岭前的年份，当事实用会让每条引用都点亮判定）。
S5 的自选变异 M4 专门验过这条不被破。

### 2e 已知但**不归本票**的通道（读 §4-Q1 前先读这条）
`stream()` 里 `answer` 落地前有两条**零模型直返**通道：分支0（`answer_cache` 精确/近重复命中）与
分支0.2（`_qa_direct_return` 持久 QA 语料）。它们在 §2c 的收口点**之前 `return`** ⇒ 任何挂在收口点上的门
都走不到它们。分支0.2 的语料是"8-23 预生成"的，先天不带版本感知。

## 3. 范围
- **做**：主流式出口（§2a 第 3 行）+ 它的 `_invoke_llm` 兜底；它的测试、变异、门禁。
- **不做**（各自另开，别"顺手"）：合同流式出口（§4-Q1 里给理由）、缓存直返两条通道（§2e）、
  `_light_buffered` 之外任何降级口径的统一、`_pre()` 旧壳（另见票 D）。
- 收口定义必须**如实登记**：本票做完，"快车道已受保护"**仍然不成立**——缓存直返那两条通道未覆盖。
  成立的句子是："快车道**生成型**答复已受保护；缓存复用型答复未受保护。"

## 4. 设计决策 —— 四问**全部已定**（2026-09-20），§4a 由本票自定可否决、§4b 由 Owner 授权按推荐裁定

### 4a 本票已定，写在这是为了留痕（否决就改，不否决不必回）
- **Q1 合同流式出口：不接，另计一张。**
  技术理由是硬的：合同报告的事实日期来自**上传的合同文本**而非用户自述，`_fast_path_fact_texts`
  那套取法在合同分支上不成立，硬接只有两种结果——改取法（超出本票射程）或接一道**恒不命中的空门**
  （正是 `[PL#14]`）。所以"不接"不是拖延，是防假接线。
  ⚠️ 但它留下一个真实的未覆盖风险：**按现行法评估一份 2019 年签的合同**，今天没人管。
  你若不接受这个风险，说一声，那是另一张票的量级（要新定合同分支的事实取法）。
- **Q3 判定位置：放在 `clean_answer` 之后、§2b 注记家族之前。**
  理由：判定读的应是模型产出的原始文本，不该把我们自己加的 `NOTE_QUOTA`/引用告警这些**壳**当被判定原文。
  代价是用户一次可能看到 2–3 条注记。我判断可接受（三条注记语义互不覆盖，且本仓已连续四次这么干）；
  若你在意"免责声明墙"，替代方案是命中时只保留版本注记、把其它注记抑制掉——那要改注记家族的既有行为，
  属越界，需你另批。

### 4b **这两件 Owner 已交回本会话按推荐裁定**（2026-09-20 授权"有决策问题按你推荐的执行"）

- **Q2 存量缓存：三个候选一个都不采纳 —— 票面原来那个事实句是错的，问题本身不成立。**
  本票初稿写"一条错版本答复在库一天，分支0 就零 token 直返一天"。**实测不成立**：
  `answer_cache._cache = rc.LRU(maxsize=512)` 是**进程内 `OrderedDict`**（`retrieval_core.py:69-93`，
  无磁盘后端），`TTL = timedelta(hours=6)`，`retrieval.invalidate()` 会调 `clear()`；
  模块 docstring 自己就写着"重启即空…命中是性能/省配额优化**非正确性依赖**"（`answer_cache.py:1-9`）。
  ⇒ 错版本条目的暴露窗 **≤ 6 小时**，不是"一天"。
  更关键的一环：**开这个开关本身就要重启进程**——`settings.py:96` 是启动时从 env 读的字段，
  全仓（`main.py` 及任何非测试文件）**没有任何运行时改写它的代码** ⇒ 切开关的那一刻缓存自动归零。
  ⇒ 候选 (b)「开开关时清一次」是**多余的**，而且有一个我初稿没算到的坏处：
  `answer_cache` 只有 `clear()` 这一个删除口（**没有按 model 删的能力**）⇒ 全库清会连
  `model="contract_review"` 的合同报告一起清掉，白烧一批 token。多余 + 有害 ⇒ **不要做**。
  ⚠️ **但真正的存量面在别处，且本票管不到它**：E2 的 QA 直返读的是 **Chroma 持久语料**
  （`main._qa_direct_return`，docstring 原文"QA 持久语义缓存直返（8-23 智谱免费 token 预生成语料）"），
  它**无 TTL、重启不清**，三道护栏是 score ≥0.92 / 选项指纹 / "条文仍在库且有效"——**没有版本判定**。
  ⇒ 判 **(a) 登记为已知残余**，但残余的所指要换成「**E2 持久语料的存量**」而不是「answer_cache 存量」；
  它的修法也不是清缓存（清不到），是"给 E2 补判定"或"给那份语料打版本标"，**另一张票**。
  登记表 E1/E2 两格已按 `GAP-TODO` 记着，不必在本票里解决。
  **反对 (c) 读侧也判**：除了把"零 token 直返"这个特性本身打穿，它连自己想解决的问题都解决不了
  （QA 持久语料那条路根本不经过 `answer_cache`）。
- **Q4 开关命名：复用 `fast_path_law_version_check`，附一条硬性要求（§5-8）。**
  复用。理由不变：两道门同一个语义，拆两个开关会出现"轻量受保护、主流式不受保护"这种没法向评测解释的状态。
  但代价我初稿估错了，两头都要订正：
  ① **"预登记口径要重述"的真实成本 ≈ 改一段文字**。实测 `dispatch-output/` 全树 39 个提到该开关的文件
     **全部**落在 S5 那三个目录里（本会话两轮 + 票 G fresh-eyes），没有一个出现在
     `agent-baseline-*` / `agent-quality-*` / 任何 gate2 评测产物中，`backend/.env` 里也没有
     `FAST_PATH_LAW_VERSION*` ⇒ **这个开关从未在任何评测批或真实运行里被打开过**，
     复用它不会让任何已登记结果变得不可比。
  ② 复用**必须同时**改掉一句现在正在说谎的话：`settings.py:90-95` 那段注释写着
     "本开关**只覆盖**缓冲轻量出口 `main._light_buffered_locked`；两条 `stream_with_retry` 流式出口
     …尚未受保护（另开票）"。票 C 合入后这句就是假的 ⇒ 列为 §5-8。
     **改配置文件里的范围句和改代码是同一件事**——本项目已经吃过一次"注释在替一个本路径不存在的机制背书"
     （`request_bootstrap.py` 那句"缺省 None = create_run 落 date.today()"，而快车道根本不经过 `create_run`）。

## 5. 实现要求
1. 判定只调 `limitation_calc.law_version_crosses_watershed(answer, fact_texts, law_as_of)`，
   不在 `main.py` 重写任何版本规则（S5 的测试里有一条专门钉这一点，照搬）。
2. 复用 `_fast_path_fact_texts` 与 `_law_version_gate` 的形状；**不要**复制一份新的门函数
   （若签名不合用，改 `_law_version_gate` 的入参形态并回头改 S5 的测试，别开第二份）。
3. 门必须覆盖 §2c 列出的**两个**答案来源（流式 join、`_invoke_llm` 兜底）。逐条点名写进回报。
4. `law_as_of` 在流式分支作用域内够得着（S5 已证 `body.law_as_of` 在 `stream()` 闭包内可用），
   不需要新中转。⚠️ **但必须传 `_fast_path_law_as_of(body)`，不是 `body.law_as_of`**（票 G F3 + 主会话 2026-09-20 订正）：
   生产客户端不传 ⇒ `body.law_as_of` 恒 `None`，而真源 `law_version_crosses_watershed` 在 `None` 时返回 **False**、
   `main.py` 的门却把 `None` 当"接线丢失"**先行命中** ⇒ 开关一开**每条答复都降级**。
   R15-lite 契约的第①半（缺省落 `date.today()`）在 agent 路径由 `repository.create_run` 承担，
   快车道不经它 ⇒ 由 `main._fast_path_law_as_of(body)` 承担（主会话已在 S5 后续票里加好，
   **若你领票时该函数尚不存在**，说明那次提交未合入 ⇒ 自己按此口径补一条并在回报里点名）。
   别在流式出口再写第二份 `or date.today()`。
5. 缺基准日 fail-closed，口径照抄 S5 / `verifier.py:296`。
   ⚠️ 补上第 4 条后，正常请求路径**再也走不到** `LAW_TRIPWIRE_NOT_WIRED` ⇒ 你必须配一条
   "该 reason 在正常路径上不出现"的断言，否则它从"接线检测器"退化成"又一个恒假守卫"（S5 后续票已这么钉）。
6. 命中必须进流式出口那条写缓存闸，否则错版本答复会被后续同题零 token 固化，门再也走不到。
   认锚点不认行号：那条闸的特征是**同一行里同时出现** `_cache_write_ok(pre, answer)` 与 `not multi_bad`
   —— 它在其分支里唯一，别用行号找它（本仓行号已漂过五次）。
   本票要把它从**四条 `and` 变成五条**——别写成"第四闸"，登记表已实测过它是四条件。
   ⚠️ **并且必须连带一条能杀它的测试**（票 G F5 实据：S5 那道同款闸被删掉后**全量 21→21 零反应**，
   因为四个变异每个只跑了同一个测试文件）。判据口径见 §6-④。
   现成仪器可直接复用：`backend/tests/_sse_harness.py` 的 `sse_client(route=...)` + `chat_frames()`
   —— 那是本仓第一套能把 SSE 出口打到端点级断言的夹具（`answer_cache.put` 可换 recorder）。
7. 日志沿用 S5 登记的四个字段，**不要**新造字段名（`tests/test_log_field_whitelist.py` 会递归扫全树；
   basetemp 别设在 `backend/` 内）。
8. **（Q4 复用的代价，必须一并交付）** 改 `settings.py` 里 `fast_path_law_version_check` 那段范围注释：
   它现在写着"本开关**只覆盖**缓冲轻量出口 `main._light_buffered_locked`；两条 `stream_with_retry`
   流式出口…尚未受保护（另开票…）"——本票合入后这句是假的。范围句要改成"快车道的**生成型**答复
   （缓冲轻量出口 + 旗舰流式出口）都过这道门；**缓存复用型直返（E1/E2）不过**，那是另一张票"。
   并把"另开票"那个指向从 `docs/handoff-s5-fastpath-version-gate-20260919.md §3` 换成本票。
   **这条不做的后果不是难看，是下一个人会被配置文件骗一次。**
9. **（新）** 本票合入后必须回头更新登记表：`backend/gate_exit_registry.py` 里 E8/E9 的「版本绊线」两格
   从 `GAP-TODO` 改成实际状态 + 证据，跑 `backend/scripts/gen_gate_exit_registry.py` 重生成
   `docs/gate-exit-registry.md`，再跑 `tests/test_gate_exit_registry.py`。
   ⚠️ **不更新的话哨兵会红**（`test_committed_md_is_the_generated_artifact` 那条腿），别把它当 flaky 跳过。
   ~~顺带：给那 9 格 `GAP-TODO` 补真实票号~~ —— **已完成（`b04853f`），别再找**：那次开票把 E1/E2 → 票 I、
   E5/E6 → 票 H、E7 → 票 J 落进了真源（票面 `docs/handoff-gap-tickets-h-i-j-20260920.md`），
   E8/E9 两格就是本票。**你只改 E8/E9 两格**，其余七格不归你。

## 6. 测试与证据（每张判据都要"亲眼红过"）
- ① **先红**：至少一条在**两参数/现网形状**下红在断言本身（不是 TypeError）的用例；红因写清楚。
- ② **期望独立**：直接复用 `dispatch-output/s5-independent-expectations-20260919/expected.json`
  （独立会话手算，本会话未参与）。**S08 / S10 / S13 / S16 四条不许拿来当断言**（那张表自己判为歧义，
  真源在 `agent/` 不许改 ⇒ 只能登记不能焊死）。
- ③ **默认关零变化**：像 S5 那样做**改前基线**逐字比对（`dump_sha256` 前后相同），并且必须含
  §2c 的兜底路径样本。⚠️ S5 的教训：基线要在动 `main.py` **之前**采，采完立刻存档哈希。
  ⚠️ **但别只靠它**（主会话 2026-09-20 自审 §九-B）：`dispatch-output/s5-fastpath-gate-20260919/capture_light_baseline.py`
  是**直接调 `_light_buffered`** 取样的，凡"改在调用点/端点里"的修复对它**完全不可见**
  （它会平凡地继续给出同一个 sha）。本票动的正是流式调用点 ⇒ 必须**另加**端点级逐帧比对：
  用 `_sse_harness.chat_frames()` 在开关 OFF 下取改前/改后帧序列 sha256，两者须相同。
- ④ **变异 ≥3**，且要含这两条：只接流式不接 `_invoke_llm` 兜底（专门抓 §5-3）；把 `context` 当事实（抓 §2d）。
  每道记"红在哪一条断言"。**跑法有硬要求**（R5，票 G F5 的教训）：每个变异跑**整套 `tests/`**，
  与同树同流程重采的干净基线做 **junit 差分**，取"基线绿→变异红"的差集非空才算被杀；
  **副本树内全量允许、live 树禁止**（见 `docs/handoff-independent-sessions-20260919.md` §0-4）。
  执行器直接复用：`dispatch-output/s5-followup-20260920/run_mutations_full.py <副本树> <输出目录>`
  （CRLF 感知、跑完字节级还原并自证）。⚠️ S5 的老执行器 `run_mutations.py` 只跑定向文件，**别照搬那一点**。
- ⑤ 两态都跑 `agent_enabled` True/False，**并验证 effective 值两边真的不同**（别跑出"两态其实同态"）。
- ⑥ 一次 **RUN_VALID** 门禁。⚠️ 跑门禁期间任何 `backend/**/*.py` 变动（含新建临时探针）⇒ 整轮作废重来。
- ⑦ **额外一条本票特有**：必须在**真实配置**下（不改 `.env`）用执行证明"门所在的那条分支真的被走到"——
  做法是临时打桩计数 `_law_version_gate` 的调用次数 > 0，跑完删桩。S5 缺这一步，才让"走不到"这件事晚了一整轮。

## 7. DoD
①+②+③+④ 全绿留痕 + §6-⑤⑥⑦ + **§5-8**（`settings.py` 范围注释已随复用一起改，贴 diff） +
**§5-9**（登记表 E8/E9 两格更新 + 重生成 md + `tests/test_gate_exit_registry.py` 绿，这条不做哨兵必红） +
`ruff`/`mypy` rc=0 + pre-commit 手跑 rc=0（钩子未接进 git；
⚠️ `ruff-format` 会改行号，**格式化之后重新量一遍本票所有坐标**）+
提交前 `git diff --cached --name-only` 逐行核对没夹带他人文件 + 回报按 §10。

## 8. 必答留白（开工第一天）
`_restart_pending` 那条重答环里，门应该判**最终 `chunks` 拼出来的那一份**还是**每一次重答之后各判一次**？
用执行回答（打桩计数命中次数），别读码推断。这条决定 §6-⑦ 的桩怎么打。

## 9. 会被哪条历史教训击穿（按危险度排）
1. **`[PL#14]` 假接线**——S5 刚刚以"接了活代码但配置挡住了"的形式复发一次。防线 = §6-⑦ + P9。
2. **只接主路径漏兜底**（§2c）——防线 = §5-3 点名 + §6-④ 那两道专门变异。
3. **注记墙**：Q3 没勾就动手，可能把答案刷成三条免责声明。
4. **行号会漂**：本文所有坐标写自 `dec7a95` 之后的树；`ruff-format` 一次就挪 12 行。防线 = 符号锚定 + DoD 重量。
5. **全绿有保质期 / 索引裹他人工作**：并行会话推过相邻文件后，你那次全量通过不再归属当前 HEAD。
   防线 = 收口前在合并后的 HEAD 上重跑定向 + `git commit -- <显式路径>` + `git show --stat HEAD` 复核。
6. **`.gitignore:45` 的 `*.log`**：票面点名要的 `gate-<标签>.log` **默认进不了库**。S5 的处置是另存 `-evidence.txt` 入库。

## 10. 回给 Owner 的格式（照抄填数）
```
P1–P9：<逐条读数 / 是否符合期望>   P9 实配角色全集=<你量到的>
HEAD=<hash>   main.py 开工前脏项=<必须"无">
§4 四问：**四问都已裁**（Q1 不接 / Q2 判 (a) 登记残余且换所指 / Q3 clean_answer 之后 / Q4 复用 + §5-8）
⇒ 这行不再是"选勾"，改成**逐条确认你按裁定的哪一句做的**，特别是 §5-8 那条注释有没有跟着改。
实现：开关=<复用 fast_path_law_version_check，默认值必须仍 False>
      过门的"答案来源"=<流式join:行号 / _invoke_llm兜底:行号>（两个都要）
      写缓存闸改前几条/改后几条=<必须是 4→5>   law_as_of 传法=<必须 _fast_path_law_as_of(body)>
      §5-8 的 settings.py 范围注释=<改了哪几行>
测试：红=<用例名 + 红在哪条断言>   绿=<passed 计数>
      默认关零变化：输入 <n> 条、差异条数=<必须 0>、含兜底样本=是/否
      变异逐条：<名字> → 只红在 <用例名> / 红在 <断言>
§6-⑦ 真实配置下门被走到：命中次数=<n>、打桩方法=<…>、桩已删=是
§8 留白：<判最终一份 / 每次重答各判 / 未证>   证据=<命令 + 输出行>
门禁：标签=<…> verdict=RUN_VALID|RUN_VOID 末行=<计数>   两态=<True 轮>/<False 轮>
产物=<逐个完整路径，注明 .log 是否已另存成可入库扩展名>
本次改动=<文件清单，逐条自证本会话所写>   未推送未部署=是
如实登记未覆盖=<必须含"缓存直返两条通道未覆盖 ⇒ 快车道已受保护仍不成立"这一句>
```

## 11. 不许你动的
`backend/agent/**`、任何开关默认值、`evals/` 冻结资产、`gate2_runner.py`、`_pre()` 旧壳、
缓冲轻量出口（S5 已完成，别"顺手重构"）、`_qa_direct_return` 与分支0/0.2（**§4-Q2 已裁为"不判读侧"，
这两条通道维持原样**，要动请另开票）、
合同流式出口（**§4-Q1 已裁"不接"**，要接是另一张票）、`.env` 里的模型角色配置（P9 要读它，但**不许改它来让门好看**）、
推送与部署。~~§4b 两问未答之前不许动 `main.py`~~ —— **2026-09-20 该阻塞已解除**：Q2/Q4 均已裁（见 §4b），
本票现在可以直接开工，前提是先读 §4b 与 §5-8/§5-9（它们比初稿多出来的东西都在那两条里）。

## 12. 交接地
- 起票人：执行 S5 的会话。S5 的两笔提交 = `dec7a95`（实现+测试+票A/票B产物）、`4ad3ce6`（门禁产物）。
  **别把这两个 hash 当基线**——它们在被引用的那一刻就已过期；基线取你领票那刻的 `git log --oneline -3`。
- 独立会话可用的其它票在 `docs/handoff-independent-sessions-20260919.md`（票 A/票 B 已完成，票 C 就是本票，
  票 D/E/F/G 仍开放）。本票与票 D 都要动 `main.py` 附近 ⇒ **别同时开**。
- 环境四条坑照旧：`core.autocrlf=true` 落盘写字节；中文/反引号串别塞进 `bash -c`；
  `pgrep` 假阴性（等副作用哨兵）；变异窗口内的 sha 无意义，只有还原后自报 `sha==base` 才算证据。
