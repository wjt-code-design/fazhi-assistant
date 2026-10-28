# 可派发独立会话的任务 · 交接文档（2026-09-19 23:0x）

发起方：正在执行 **S5（快车道版本判定最小可用）** 的会话。
用途：Owner 把下面**任意一节整段复制**给另一个会话即可开工，每节自足、不需要读其它节。

---

## 0. 全局车道规则（每张票都受它约束，先读这段）

**车道状态更新（S5 已提交 `dec7a95`）**：`backend/main.py` 的"单写者车道"**已解除** —— 上面 §0 表里
那组行号（`1155`/`1164`/`1567`/`1761`/`1902`）已经作废。**而且本段第一次订正时又量错了**：
`ruff-format` 在 S5 提交前把 `main.py` 重排过，所以真实坐标是 **`1844`/`1987`**（不是 `1832`/`1975`），
缓冲出口 `def _light_buffered` 在 `:1210`、`_light_buffered_locked` 在 `:1219`、`use_light` 在 `:1650`。
⇒ **本文所有行号一律按符号锚点重测再用**（本项目已因此漂过三次：`1729/1870`→`1761/1902`→`1844/1987`）。

**但有一条新窗口规则（✅ 已于 23:51 解除，下面留作机制说明）**：主会话跑过一轮 `run_gate_full` 全量门禁。
它在跑前/跑后对 `backend/` 下**所有 `.py`** 取 sha256 快照，中途任何一个 `.py` 被新建、删除或改动
⇒ 整轮判 **RUN_VOID**、passed/failed 计数全部作废重来。**该轮已收口并判 RUN_VALID，窗口现在放开**
（读数：`1344 passed, 18 deselected`，rc=0，源码变动 0 个，真实库零写入 ——
见 `dispatch-output/te-chroma-isolation-20260918/gate-s5-fastpath-gate-verdict.txt`）。
今后你若看到主会话另起一轮门禁，同样适用这条：

- 在你看到主会话写明"门禁轮已收口"之前，**不要在 `backend/` 下新建或删除任何 `.py`**（包括临时探针、
  包括"用完就删"的），也不要改 `.py`。
- 只写 `docs/` 与 `dispatch-output/` 下的 markdown/json/txt 不受此限（快照只看 `.py`）。
- 需要跑测试验证什么时，优先跑**你自己的**定向文件；跑全量套件与 `run_gate_full.py` 一律等窗口放开。

除票 C 外，下面所有票都应是**只读取证 / 只写文档**。若你的任务需要改 `main.py`，说明你被派错了票，
停手回报（票 C/D 的"不写码"是设计决定，不是车道限制使然，车道放开后依然适用）。

本会话 **22:3x–22:5x 实测**（你仍须自己复跑，行号会漂）：

| 事实 | 读数 | 复核命令（在仓库根跑） |
|---|---|---|
| S5 基线 HEAD | `103a8df` | `git log --oneline -1` |
| `main.py` 车道 | 空（无未提交改动） | `git status --porcelain backend/main.py` |
| 快车道三出口 | `1155`/`1164` 缓冲、`1761` 与 `1902` 流式、`1831` 调用点 | `grep -n "def _light_buffered\|stream_with_retry(\|run_in_threadpool(_light_buffered" backend/main.py` |
| 默认开关 | `feature_router=True`（`settings.py:43`）、`agent_enabled=False`（`:49`） | `grep -n "feature_router\|agent_enabled" backend/settings.py` |
| 绊线真源 | `agent/limitation_calc.py:225 law_version_crosses_watershed(claim_text, fact_texts, law_as_of) -> bool` | `grep -n "def law_version_crosses_watershed" backend/agent/limitation_calc.py` |
| agent 路径有门、快车道没有 | `verifier.py` 4 行命中（`:296 :338 :434 :438`）、`main.py` 全文 `tripwire` **0 命中** | `grep -c tripwire backend/main.py` |
| 冻结资产完好 | `gate2_runner.py` sha256 = `ae2e4120…47e295`（与票面要求一致，已实测相符） | `sha256sum backend/scripts/gate2_runner.py` |

**环境与纪律五条**（前四条是本会话与上一任为它们返过工的坑，一次坑值 20 分钟；第五条是裁决出的默认要求）：
1. `core.autocrlf=true` ⇒ 落盘**写字节**，`Path.write_text()` 会把 `\n` 变成 `\r\n`；改完复测 CRLF 计数。
2. 含中文 + 反引号 / `$` 的串**不要**塞进 `bash -c` 或 `python -c`，写成临时脚本文件再跑。
3. `pgrep -f <进程名>` 在这台机器会假阴性：等后台任务是等**副作用哨兵**（输出文件非空 / 末行出现 `rc=`）。
4. **全量测试套件 / `run_gate_full.py`：live 树禁止，副本树内允许。**
   禁的是在 live 上跑（花钱、且与并行会话抢 `app.db` / chroma 把隔离判据弄脏）；
   副本树（`git archive <commit> | tar -x -C <目录>`）里 `backend/.env` 不在场，且
   `tests/conftest.py` **无条件**把 `DATABASE_URL` / `QUOTA_DB` / `CHROMA_DIR` 指到 `%TEMP%` 进程私有路径
   ⇒ 副本内跑不出污染。副本需另备 `dispatch-output/task1/`（被 `.gitignore` 排除，缺了 `test_harness_fact_reveal.py`
   收集期就报错）。**本条口径由票 G 复审 §7-P3 与主会话裁决确立（2026-09-20）。**
5. **变异审计必须跑全量 + junit 差分**，不许只跑定向文件。
   教训实据：S5 那轮四个变异**每个只跑 `tests/test_fast_path_law_version_gate.py` 一个文件** ⇒
   `main.py` 里"命中不进缓存"那道 load-bearing 闸被删掉后**全量零反应**（复审 G-M1 存活）。
   判据形状：基线与被审变异体各跑一轮整套，取"基线绿 → 变异红"的**差集**非空才算被杀；
   两份基线口径不同（不同 commit / 不同副本流程）时**不许相减**，要先在同一棵树上重采。
   ⚠️ **还必须比"分母"**（CodeReview/c-4，2026-09-20）：只取 `failure/error` 集合而不读
   `<testsuite tests= errors=>` 的差分器，在"基线整轮崩盘 → xml 空 → ∅"时会把**任何**一次红
   判成 KILLED；而 `anchor-error` / 分母漂移若不计入坏消息，最后一行照样能打出 `ALL_KILLED`。
   判据：基线 `tests>0 且 errors=0`，且每个变异体的 `tests` 与基线**相等**，否则该条记
   `denominator-drift` 而不是 KILLED。本轮实测分母 5 份全是 `tests=1368 / errors=0` ⇒ 结论未受影响，
   但仪器当时**查不到**这件事（已补 `run_mutations_full.py` 与 `recompute_mutation_from_xml.py`）。
6. **凡"跑了整套"的留痕，必须写明跑在哪棵树 + 分母读数。**
   `gate-*-verdict.txt` 只记 `basetemp` 与 passed 数 ⇒ 在本条纪律改成"live 禁止 / 副本允许"之后，
   审阅者**无法判断**那次运行是不是越界（CodeReview 硬违反 3）。合格写法见
   `dispatch-output/s5-followup-20260920/02-mutation-verdicts.txt`：明确写了副本树路径与 `tests=` 分母。

**通用边界**：不推送、不部署、不改任何开关默认值、不动 `backend/agent/**`、不动 `evals/` 冻结集、
pytest 的 basetemp **不要设在 `backend/` 内**（`tests/test_log_field_whitelist.py` 递归扫全树）。
`pre-commit` 钩子**没接进 git**，手工跑要用 `backend/venv/Scripts/pre-commit.exe`。

---

## 票 A · §8 留白：默认态一次真实请求到底走哪条出口 —— **已答，且答案改写了票 C 的优先级**

产物：`dispatch-output/s8-stream-probe-20260919/report.md`（+ `pytest-stdout.log`、`trace.json`）。
探针跑完已自删临时文件，`git status --porcelain backend/` 里它名下无残留。零真实模型调用。

**结论：默认配置下三种法律问句形态全部走第二条 `stream_with_retry(`（本会话现量 `main.py:1975`，
票 A 当时量到的快照里是 `:1902`），缓冲轻量出口零流量。**

主会话已**独立复量**过承重事实（不采信转述）：

```
agent_enabled = False      feature_router = True
registry.has_role('text','light') = False      ← 承重的那一项
registry.has_role('text','flag')  = True
```

机制：`use_light = use_router and tier == "light" and modality == "text" and registry.has_role("text","light")`
（现量 `:1650`）。前三项都成立（问句确实被判成 light-text），**卡在最后一项**。
承重事实已被本会话量化复跑（比"没配 light 档"更硬）：

```
registry 实配的 (modality, tier) 全集 = [('text','flag')]      ← 只有这一个
六个 key 全是 text/flag：agent_text_37max / …0517 / …0520 / …0608 / …pv / 37plus0526
⇒ has_role('text','light') = False（不是"light 模型被禁用"，是**根本没有 light 这一档**）
```

（`.env` 里 grep 到的唯一 "light" 是 `step_preflight` 的子串，不是角色配置。）

⇒ **缓冲轻量出口是活代码、不是死码**：探针做过反事实，把 `has_role` 强置 True 后同一请求立刻进
`_light_buffered`。但它**在当前配置下不可达**。

### 这条对 S5 交付的定性影响（本会话如实登记，不替它遮）
S5 这道版本绊线门加在缓冲轻量出口上，于是：**在当前部署配置下，被这道门保护的分支收不到流量，
而真正承接全部流量的第二条流式出口仍然没有版本判定。** 这不是"门接错了死代码"（票面 §9-1 防的那种），
而是"门接在一条被配置挡住的活代码上"——症状相同：**"快车道已受保护"这句话今天仍然不成立。**
成立的那句是："快车道轻量分支已受保护，且需配置 light 档模型后才有线上效果。"

### 未证（票 A 自陈 + 本会话补认）
① 分支0 / 0.2 的缓存命中会不会把 light-text 抢走（它的观察是假答案过不了写闸、缓存未被填，但未定论）；
② vision 形态；③ `agent_enabled=True` 时的形态。这三条要等后续票一并了结。

---

## 票 B · 绊线期望值独立手算表 —— **已完成，产物可直接引用，但含一条推翻出题假设的发现**

产物：`dispatch-output/s5-independent-expectations-20260919/expected.md` + `expected.json`（16 条：HIT 3 / NO_HIT 11 / AMBIGUOUS 2）。
执行者自证未读 `limitation_calc.py` / `verifier.py` / `main.py`，未跑任何项目代码。本会话已交叉复核，
其中最容易踩的三条，Owner 若要复用这张表**必须知道**：

1. **规则的"分跨两侧"是双向 XOR，不是单向。** 真源实测为
   `return (dates[0] < CIVIL_CODE_EFFECTIVE) != (law_as_of < CIVIL_CODE_EFFECTIVE)`（`limitation_calc.py:255`）。
   ⇒ "事实发生在 2022 年、law_as_of 给 2019 年"同样**命中**。语义上 R15 想防的只有前一种，
   但**本票不许改 `agent/**`**，故这是必须接受并如实登记的既有语义，不是待修 bug。
2. **判定不看"引了哪部法"。** 只看 claim 是否含民事时效关键词 + 事实日期 + 基准日。
   ⇒ 一条**正确地**引用《民法通则》一年时效的回答，只要文本里出现"诉讼时效"，同样命中。
   这道门有**假阳性面**，任何拿它当判据的人都要先知道。
3. **"每个对照 case 出一正一负"不成立。** W02 两个形状按规则都是 NO_HIT。

若 Owner 要让别的会话**扩展**这张表（不是复用），要求它继续遵守"不读实现"这条，否则独立性归零。

---

## 票 C · 快车道两条流式出口的版本判定收口策略（**只出票面与设计，不写码**）

> **优先级已上调。** 票 A 已答且本会话已复量：默认配置下三种法律问句形态**全部**走第二条
> `stream_with_retry(`（现量 `:1975`），缓冲轻量出口零流量。⇒ S5 那道门今天保护不到线上流量，
> **这张票覆盖的才是真正在承接流量的那一条**。它不再是一张"以后再说"的票。

**背景**：S5 只补了缓冲轻量那一条出口。完成后"快车道已受保护"这句话**仍然不成立** ——
两条流式出口没有版本判定。它们难做的地方在于：版本判定要**整段文本**，而流式把答案分片在外，
插一门必须先定"在哪儿收口"= 会改到用户可见的流式行为。所以这张票先要的是**决策**，不是代码。

**目标**：产出一份能直接开工的票面（形状照 `docs/process-archive/handoff-s5-fastpath-version-gate-20260919.md` 抄：
排队条件 / 前置取证表 / 事实底座 / 已定稿的设计决策 / 实现要求 / 测试与证据 / DoD / 回报格式 / 不许动的）。

**本会话已实测、可直接引用的事实**（⚠️ 行号是 **S5 落地之后**重量的，比 §0 那张表整体下移；
你仍须自己 grep 符号复验，别拿本文数字直接改码）：
- 两处调用点同形状：**现量** `main.py:1844` 与 `:1987` 都是 `async for piece in stream_with_retry(`
  （S5 之前的快照里是 `1761`/`1902`；我在本文上一版写的 `1832`/`1975` 也是错的——`ruff-format`
  在 S5 提交前重排过 `main.py`。**别再信任何写死的数字，按符号 grep 复验。**）
- **收口免费（这条推翻 S5 票面 §2 的前提）**：两处循环之后**本来就有** `answer = "".join(chunks)`
  （现量 `:1859` 与 `:2003`），是为落库/写缓存收的 ⇒ 插门不必改流式行为，"必须先定收口策略"是误判。
- `:1987` **不是** `:1844` 的简单兜底。实测其上下文在一个"换模型重答"的环里：
  同一函数体内有 `_on_model_failure`（把 `current["key"]` 加进 `_tried`、`mark_depleted`、
  置 `_restart_pending = True  # 下一 config 将从零重答：前端需清空半截`），
  且 `stream_with_retry` 的第 3 个实参是温度阶梯 `[(False, 0.0), (True, 0.5), (False, 0.5)]`。
  ⇒ **别假设两处的降级口径一致**，这是这张票最大的未知量。
- 流式侧**已有**同款"明说降级"追加惯用法（不是缓冲路径独有）：`main.py:2078` `answer += NOTE_COMPLEX`
  并在 `:2079` 单独 `yield` 一帧、`:2083` `answer += NOTE_QUOTA` 并在 `:2084` 再 yield 一帧。
  注记常量定义在 `:1015`/`:1016`（S5 新加的 `NOTE_LAW_VERSION` 在 `:1018`）。
  ⇒ 收口后的呈现方式有现成先例可抄，不必新造。
- `use_light` 的判定在 `:1650`，合同评估在 `:1652` 强制把 `use_light` 关掉（走旗舰流式）。
- S5 的门在缓冲出口上的落点（可作为你设计流式收口时的对照）：`_fast_path_fact_texts` 在 `:1162`、
  `_law_version_gate` 在 `:1176`，调用点在 `:1914` 的 `run_in_threadpool(_light_buffered, pre, messages, body.law_as_of)`。
- 票 B 第 1、2 条（XOR 双向、不看引哪部法）**同样适用于流式收口后的判定**，票面必须写进去。
  尤其"不看引哪部法"这一条：流式答案是整段文本，一次性把整段喂给判定的**假阳性半径比 agent 路径更大**
  （agent 路径是逐 claim 判，快车道只能整段判）。

**你要新量清楚的**（本会话**未**证，别引用本会话当结论）：
1. ~~默认配置下哪些请求真的落到 `:1832` / `:1975`~~ —— **已由票 A 答毕**：三种法律问句形态全部 `:1975`。
   但你仍须复核票 A 自陈的三条未证（缓存分支会不会把 light-text 抢走 / vision / `agent_enabled=True`）。
2. `:1975` 的重答环里，收口点该放在每次重答之后、还是整个环之后 —— 前者会对同一问题判定多次。
3. 流式已经在往客户端吐字之后再收口判命中，**已经吐出去的怎么算**（这是这张票真正的难点，也是它值钱的理由）。

**边界**：不改任何被跟踪文件（含 `main.py`，S5 占用中）；不改开关默认值；不写实现代码；
产物只允许新建于 `dispatch-output/s5-stream-exit-design-<日期>/` 与 `docs/`（若 Owner 要你把票面入库）。
不跑付费三臂、不跑 `run_gate_full.py`。
**卡住就回报**，别自己把设计定了 —— 设计决策权在 Owner。

---

## 票 D · `_pre()` 旧壳的处置（**取证 + 建议，本会话未动它**）

S5 票面 §11 明令本票不碰 `_pre()`，所以它被留给了独立会话。

**本会话 22:5x 实测**（你须复跑）：
- 定义：`backend/main.py:703 def _pre(user_id: int, conversation_id, text: str, image, client_truncated: bool = False)`，
  docstring 自称 "Compatibility coordinator"。
- **`main.py` 内 0 调用点**（`grep -n "_pre(" backend/main.py` 只命中定义那一行）⇒ 生产路径不走它。
- 唯一调用者是测试：`backend/tests/test_pre_rewrite_order.py:92` 定义了本地 helper
  `_pre(main, conv_id, text)`，`:93` 转发 `main._pre(1, conv_id, text, None)`，该 helper 被 `:99 :106 :113 :122 :132 :140 :149` 共 7 处使用。
  ⇒ **它既不是死码（删了会红那一串测试），也不是可挂门的地方**。

**要回答的问题**：留一个"生产不调、测试在调"的兼容壳，是保护还是负债？给出：
① 它 `:713` 转发到的 `_prepare_fast_path_only` 与端点内真实准备逻辑之间有没有已经分叉的行为差异（**这是重点**：
壳若与真路径漂移，那 7 条测试测的是一个线上不存在的形状）；
② 若删，需要连带处置哪些测试、它们原本各自在钉什么（别把判据一起丢了）；
③ 建议：保留并加"与真路径一致性"断言 / 删除 / 保持现状，三选一给理由。

**边界**：不改任何被跟踪文件；不许为了回答①去改 `main.py`（可以写临时脚本 monkeypatch 观察，用完删）；
产物新建在 `dispatch-output/s5-pre-shell-<日期>/`。

---

## 票 E · 谁在往 `.git/objects/15/` 反复写 `tmp_obj_*`（**只读取证**）

**已登记给"正在审查本项目的另一个会话"，S5 票面 §12 明令本会话不许顺手查。Owner 若要把这条正式交出去，用这节。**

本会话实测读数（**时间点不同，你须现量**）：

| 时点 | 读数 |
|---|---|
| 21:5x（S7 会话记录） | 15 个 / 633 MB，"仍在生成" |
| 22:5x（本会话） | **13 个 / 目录总 697 MB**，单个 48–51 MB，mtime 跨 `09-18 21:33` → `09-19 19:59` |

⇒ 两次读数合起来看：**文件数在减、总体积在增、mtime 不单调** ⇒ 它不是"只增不减地漏"，
更像有进程在**边写边被回收/替换**。这条差异本身就是线索，别把它当噪声。

**取证方向建议**（不强制）：`tmp_obj_*` 是 git 自己写对象时的临时文件名，出现在 `objects/<2hex>/` 下
通常意味着有进程真在跑 `git` 写对象（`add`/`pack-objects`/`gc`/`repack`/克隆），而 48–51 MB 的单个对象
指向**大文件**。可用 `git cat-file -t` / `--batch-header` 在**只读**前提下探一下已定型的同名对象，
或用 `lsof`/`handle.exe` 一类工具看持有者。别猜，量。

**硬边界**：
- **不许删除任何 `tmp_obj_*`、不许跑 `git gc` / `prune` / `repack` / `filter-branch`、不许写 `.git` 下任何文件。**
  仓库磁盘紧张时也不许 —— 那是 Owner 的决策，不是取证的副产品。
- ⚠️ **live 仓库 `.git` 有洞：缺父提交 `0263bd5`** ⇒ 任何"历史里没有 X"这类**负证明只能在救援包里做**。
  救援包索引：`C:/Users/33393/Desktop/fazhi-rescue-INDEX.txt`（22:5x 实测存在）。
  最新一份 = `C:/Users/33393/Desktop/fazhi-rescue-d6077d0-20260919/`（40 提交、tip tree `58c9cd55…`、
  `ls-tree -r` 2164 条、graft 自 `0263bd56` ⇒ **包内 tip SHA 与 live 不同，只能按内容引用，别拿 hash 当基线**）。
- 磁盘：`C:` 上另有 `cloned/` 一份 466 MB 是 7 秒可重建的克隆，若空间真不够，那才是可删项，且须 Owner 点头。

**交付**：写入者归因（哪个进程/哪条命令/为什么这么大）+ 你贴出的原始命令与输出 + 一句"是否仍在增长"的现量结论。

---

## 票 F · `backend/app.db` 最后一次被写（09-19 00:28）是谁（**只读取证**）

同属 S5 票面 §12 登记给外部会话的两问之一。

本会话实测：`backend/app.db` mtime = **2026-09-19 00:28:25.716**，size = **20205568 字节**；
本会话 22:5x 复量 **与 00:28 完全相同** ⇒ 该文件已约 **22 小时未被写入**。
（票面记的 "cc 10784" 是另一种 stat 口径，未与本会话读数对齐，须由你重测确认。）

**要回答**：① 00:28 那次写入是谁发起的（评测批？某次 `gate2_runner`？某个残留进程？）；
② 更值钱的一条：**下次若再发生未知写入，现有证据链能不能归因** —— 如果不能，提一个最小哨兵方案
（属设计建议，不许你实装）。

**硬边界**：对 `app.db` **绝对只读** —— 不许打开写事务、不许 `VACUUM`、不许改 schema、不许删、
不许"为了看内容"而复制到有 sqlite 副作用的地方。查进程/日志/文件 mtime，别碰库本身。
⚠️ 本仓有过真实教训：**在真库上做演练**会把隔离判据搞脏，任何写路径实验只能在**副本**上做。

---

## 票 G · S5 交付的 fresh-eyes 复审（**必须等 S5 提交之后才发**）

触发条件：S5 的 commit 已落地（`git log --oneline -5` 能看到它）。早于此发出去没有意义。

任务：**不看 S5 的报告**，独立回答三问并给出证据：
1. 这道门在**默认配置 + 开开关**下真的会被走到吗？逐条核对 `main.py` 里 `_light_buffered_locked` 的
   每一个 `return` 点是否都过门（先自己数有几个 return，别接受别人给的数字）。
2. 开关关掉时，`main.py` 的行为是否**逐字**不变（自己设计比对方法，别复用它的比对脚本）。
3. 设计一道 **S5 自己没想到的变异**，跑出来并说明红在哪条断言。

边界：不改码，只回报；发现问题由本会话修，你负责复验。不许跑 `run_gate_full.py`（花钱）。

---

## 回报格式（票 C/D/E/F/G 通用，照抄填数）

```
票号=<C|D|E|F|G>   起票时 HEAD=<hash>   现量日期时点=<YYYY-MM-DD HH:MM>
§0 车道复跑：main.py 脏项=<必须"无">   feature_router/agent_enabled=<读数>   三出口行号=<你现量的>
我实际改动过的被跟踪文件=<必须"无">   新建产物=<逐个完整路径>
结论=<一段话，直接给判断，别摆选项>
证据=<命令原文 + 粘贴的真实输出行，不要转述>
未证=<明确点名哪些没答上、卡在哪一步、试过什么替代方案>
边界自证=<有没有删过/写过任何 .git 下文件、开关默认值、agent/**、evals/>   未推送未部署=是
```

诚实优先：**答不上来就写"未证"**。把读码推断写成执行证据，是本项目已登记的两类返工之一（`[PL#14]` 假接线的近亲）。
