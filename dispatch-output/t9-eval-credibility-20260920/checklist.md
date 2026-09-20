# T9 · 评测可信度「绕开清单」（E1 / E2 · BLOCKED 的前科复盘）

> 任务：登记表 E1/E2 的「评测可信度」两格是 `BLOCKED`（既有事故：`qa_cache` 污染 judge 基线，
> `multi_ok` 的 0.43 / 0.57 / 0.64 三个数全失真）。本清单回答：**跑评测时必须绕开什么**，才能不再重演。

---

## 基线锚定（T9 必做）

- `git rev-parse HEAD` = `beb4d5c09a7a28e2987488b86031780f6ed7d8c5`
- `sha256(backend/main.py)` = `a31b7b4c34c71692f860e1730fe1e7188e6b49f46790ab8211b328137e50be83`
- `sha256(backend/retrieval.py)` = `59596c826ab11dc7c036242d90545fe2ddd77f387facb52e4f87f25f0dfc0476`

> ⚠️ `main.py` 此刻被**票 I 在途编辑**（baseline.json 标注 `owner=ticket-I`、`drift_alarm=false`、不作判据）。
> 上面这串 sha256 是 T9 开工时的**实测快照**；若结论要对着别版本，先重算 sha256 再读本清单。
> 本清单只引用**形状/符号**（`main.py` 的 `body.no_cache` 短路逻辑），不引用会随票 I 漂移的行号——
> 行号是今天实测值，仅供定位。

---

## 事故机理（一句话）

评测的 **judge** 拿系统返回的 `content` 打分；若某条请求被 **E1 进程内 `answer_cache`** 或
**E2 持久语义缓存 `_qa_direct_return`（Chroma `qa_pairs` 预生成语料）** 直返，judge 打的就是
**语料里的旧答案**，不是当前模型生成的答案。当 judge 与这份语料同源时还会「和 LLM 一起错」
（registry E2 取证原文），于是 0.43/0.57/0.64 三个数全失真——数字失真比没数字更危险。

唯一的硬开关是请求体的 **`no_cache: true`**：它同时把 E1 的 `cache_key` 置 `None`、把 E2 的
`_qa_direct_return` 整体短路，三处缓存（精确 key / 近重复 `feature_similar_cache` / QA 持久语义）一并旁路。

---

## 评测批 checklist（每条：绕开什么 + 代码出处 + 今天是否已被防住 + 命令）

### C1 · 绕开 E2：QA 持久语义缓存直返（Chroma `qa_pairs`）
- **绕开什么**：评测请求落到 `stream()` 分支 0.2，被 `_qa_direct_return` 用预生成语料直接回答案，
  而不是让当前模型生成。
- **代码出处**：
  - `backend/main.py:1793` — `if body.no_cache:` 把整段 `_qa_direct_return` 调用短路为 `None`
    （即 `qa_ans = None if body.no_cache else await run_in_threadpool(_qa_direct_return, ...)`）。
  - `backend/main.py:1107` — `_qa_direct_return` 函数体，docstring 原文「QA 持久语义缓存直返
    （8-23 智谱免费 token 预生成语料）」，命中即返回预生成 `qa.get("answer")`。
  - 字段声明 `backend/schemas.py:55` — `no_cache: bool = False`（**默认 False**，不传就走缓存）。
- **今天是否已被防住**：**否（不自动）—— 且当下就有 7 个既有评测入口（6 个评测脚本 + 1 个 smoke 脚本）处于缓存暴露状态，这才是 E1/E2「评测可信度」至今 `BLOCKED` 的实锤之一**（不是「未来新增入口才会漏」）。
  - 默认不防：字段默认 `False`（`schemas.py:55`）；`_client.chat(..., no_cache=False)` 也是默认
    （`backend/scripts/_client.py:57`），不显式传就会命中 E2。
  - **两个口径并陈（严禁混算同一个分子分母）**：
    - **grep 口径（`_client.chat(` / `chat_stream(` 裸调用）**：`backend/scripts/` 下共 **13 处**调用点，只 4 处传 `no_cache=True`（`capture_eval.py:308`、`eval_contract.py:104`、`eval_exam.py:120`、`eval_exam_professional.py:69`），**漏传 7 处 / 6 个评测脚本**：`eval_consistency.py:67` 与 `:68`（一致性）、`eval_hallucination.py:40`（幻觉）、`eval_negative_run.py:41`（拒答/负向）、`eval_quality.py:60`（质量）、`eval_redteam.py:58`（红队）、`eval_relevance.py:41`（相关性）。这 6 个脚本各有 `if __name__ == "__main__":`，是真入口。
    - **AST 口径（含本地同名 `def chat` wrapper 的调用点）**：实跑得 **22 处**调用点 / **18 报警**，拆三类：
      1. **假阳性 8 处（wrapper 内部已传 `True`，闸按裸名误抓）**：`acceptance.py:19` 本地 `def chat(...)` 内 `body = {"content": content, "no_cache": True}` ⇒ 其 5 处调用（`:65`/`:79`/`:89`/`:152`/`:154`）**不漏**；`smoke_b1b5.py:15` wrapper 同样传 `True` ⇒ 其 3 处调用（`:50`/`:71`/`:80`）**不漏**。
      2. **真漏 3 处（新增，本清单上一版没有）**：`smoke_citation_full.py:42` 本地 `def chat(token, q)` 用**裸 urllib** 构造 body，**根本没有 `no_cache` 字段** ⇒ 其 3 处调用（`:109`/`:117`/`:131`）**真漏**（smoke 类，连 `no_cache` 都没传）。
      3. 上文 grep 口径的 **7 处**（6 评测脚本）维持**真漏**。
    - **真漏合计 = 10 处 / 7 个脚本**：`eval_consistency.py:67,68`、`eval_hallucination.py:40`、`eval_negative_run.py:41`、`eval_quality.py:60`、`eval_redteam.py:58`、`eval_relevance.py:41`（评测类 6 脚本，共 7 处）+ `smoke_citation_full.py:109,117,131`（smoke 类，裸 urllib 构造请求，连 `no_cache` 字段都没有）。这 7 个脚本各有 `if __name__ == "__main__":`，是真入口；**读数按现状不可信，除非跑前手动改**。
  - **直接构造 payload 类（不属上述任何口径）**：`gate2_probe.py:64`、`gate2_runner.py:80` 与 `:542` 确实传 `no_cache=True`，且 `gate2_runner` 的 payload 被 `backend/tests/test_r15_runner_injection.py:40` 单测锁死为 `== {"content": ..., "no_cache": True, "force_agent": True}`。
  - 登记表原文已把要求写进取证：`gate_exit_registry.py:170`「评测必须 `no_cache` 绕本出口，否则测的是缓存不是模型。
    前科 `[fz]`：qa_cache 曾让 multi_ok 0.43/0.57/0.64 三个数全失真」。registry E2 的「评测可信度」**仍 `BLOCKED`**
    （`gate_exit_registry.py:224-225`）—— 正是因为上述 7 个既有入口（含 `smoke_citation_full`）当下就漏传，而非「未来新入口」。
- **命令（绕开动作）**：每条评测请求必须带 `"no_cache": true`。
  - 调库：`backend/scripts/_client.py:57` → `chat(token, q, no_cache=True)`。
  - curl：`curl -s -X POST /api/chat -H 'Content-Type: application/json' -d '{"content":"<问句>","no_cache":true}'`
  - **批前闸（`no_cache` 漏传检查）**：
    - **① 快速 grep（有缺陷，仅辅助）**：先 `grep -rnE "_client\.chat\(|chat_stream\(" backend/scripts evals`
      **枚举调用点全集**，再逐条判；**不要**像「用 `grep no_cache` 找护栏」那样只命中有串的行（那是选择偏差，会漏掉漏传点）。
      局限 a（假阳性）：会把 `capture_eval.py:183` 的方法**定义** `def chat_stream(self, ..., no_cache: bool, ...)`
      当成调用点 ⇒ 需排除 `def ` 行。局限 b（假阴性）：单行 grep **看不见多行调用**
      （`_client.chat(\n  token,\n  q,\n)`）⇒ 见 ②。
    - **② AST 版检查（推荐，补 ① 的假阴性）**：遍历 `ast.Call`，判 `func` 尾名是 `chat`/`chat_stream`
      且 `keywords` 里有无 `no_cache=True`；形态贴合本仓 AST 哨兵先例 `observability._ACCOUNT_FIELDS`。
      写成 `.py` 文件跑（避开 `-c` 内联的展开坑）：
      ```python
      import ast, pathlib
      ROOT = pathlib.Path("backend/scripts")
      for p in ROOT.rglob("*.py"):
          try:
              tree = ast.parse(p.read_text(encoding="utf-8"))
          except SyntaxError:
              continue
          for n in ast.walk(tree):
              if isinstance(n, ast.Call):
                  name = getattr(n.func, "attr", getattr(n.func, "id", ""))
                  if name in ("chat", "chat_stream"):
                      has = any(kw.arg == "no_cache" and isinstance(kw.value, ast.Constant)
                                and kw.value.value is True for kw in n.keywords)
                      if not has:
                          print(f"LEAK {p.relative_to(ROOT)}:{n.lineno} {name}")
      ```
      ⇒ 打印出的行即漏传点，批前打回。这是约定检查、非运行时强制；registry E2 仍 `BLOCKED` 正是因为漏传无法在请求层强制。
    - **③ AST 闸的已知缺陷（裸名匹配的假阳性）**：`func` 尾名只判 `chat`/`chat_stream`，会**把本文件内「本地同名 `def chat(...)` wrapper」的调用点也报成 LEAK**——而该 wrapper 体内可能已传 `no_cache=True`（如 `acceptance.py:19`、`smoke_b1b5.py:15`），其实**不漏**。两个处置选项：
      - **a) 人工解引用**（本次采用）：闸输出 LEAK 行后，逐条打开该文件确认是裸 `_client.chat(` 漏传，还是本地 wrapper 已传 `True`；本清单上文「AST 口径」三类判读（8 假阳性 + 3 真漏 + 7 评测真漏）即示例。
      - **b) 进阶版（建议形态，本次未实现）**：沿 `ast` 在本文件内查找同名 `FunctionDef`，递归检查其函数体是否出现 `no_cache` 字面量（一层间接即可消解 wrapper 假阳性）；写 `.py` 跑，避开 `-c` 内联坑。

### C2 · 绕开 E1：进程内 `answer_cache` 精确命中 + 近重复命中
- **绕开什么**：评测请求被 `stream()` 分支 0 的 `answer_cache.get(cache_key)`（精确）或
  `_similar_cache_hit`（近重复，余弦 ≥0.95）直返——返回的也是之前某次（可能是别的模型/别的题）的答案。
- **代码出处**：
  - `backend/main.py:1740` — `cache_key = None if body.no_cache else (...)`：传 `no_cache` 直接让
    `cache_key=None`。
  - `backend/main.py:1741` — `cache_hit = answer_cache.get(cache_key) if cache_key else None`：`cache_key`
    为 `None` ⇒ 跳过精确命中。
  - `backend/main.py:1761-1762` — `if not hit and cache_key and settings.feature_similar_cache:`：
    `cache_key` 为 `None` ⇒ 跳过近重复命中。
  - 缓存实现 `backend/answer_cache.py:17` — 模块级 `_cache = rc.LRU(maxsize=512)`（**进程内**、TTL=6h、
    重启或 `retrieval.invalidate()` 才清）。
- **今天是否已被防住**：**否（不自动）—— 且当下就有 7 个既有评测入口（6 评测脚本 + 1 smoke 脚本）漏传 `no_cache`，这才是 E1/E2「评测可信度」至今 `BLOCKED` 的实锤之一**（与 C1 同一开关：`no_cache=True` 令 `cache_key=None`，同时旁路 E1 与 E2；漏传即两种缓存都暴露）。
  - 默认不防：字段默认 `False`（`schemas.py:55`）。
  - **真漏合计 = 10 处 / 7 个脚本**（与 C1 同一开关；两个口径并陈见 C1，此处只给合并结论）：`eval_consistency.py:67,68`、`eval_hallucination.py:40`、`eval_negative_run.py:41`（拒答/负向）、`eval_quality.py:60`、`eval_redteam.py:58`、`eval_relevance.py:41`（评测类 6 脚本，共 7 处）+ `smoke_citation_full.py:109,117,131`（smoke 类，用**裸 urllib** 构造请求，连 `no_cache` 字段都没有）。**读数按现状不可信，除非跑前手动改**。详见 C1 的清单与批前闸（AST 版含本地 wrapper 假阳性判读）。
  - registry E1 的「评测可信度」**仍 `BLOCKED`**（`gate_exit_registry.py:167-170`）：口径正是「当下就有既有入口漏传」，
    不是「未来新入口」。
  - 跨请求/跨文件污染实锤（为何 `no_cache` 必须严格）：`backend/tests/test_light_exit_gates.py`
    的 `_focus_route` docstring（约 96-111 行）实测——`answer_cache` 是模块级 LRU，全量 lane 里旗舰用例
    先写某 key，轻量分支再跑同题就**根本进不去分支 1**、直接返回旗舰答案；定向单跑看不见，全量才复现。
- **命令（绕开动作）**：同 C1——每条请求带 `"no_cache": true`（C1 与 C2 是同一个开关的两处旁路）。
  若确需测「带缓存的命中率」，则必须在**全新/独占进程**里跑（见 C3），且**绝不与真实模型质量评测混批**。
  - 批前闸（`no_cache` 漏传检查，含 AST 版）同 C1：枚举 `_client.chat(` / `chat_stream(` 调用点全集后逐条判，
    用 AST 版（`ast.Call` + `keywords` 含 `no_cache=True`）补单行 grep 的假阴性；有漏传点即批前打回。

### C3 · 绕开「评测打到接了生产流量的共享 / 温热 worker」
- **绕开什么**：用同一个 uvicorn worker（且它之前服务过生产流量或上一轮评测）跑评测——其
  进程内 `answer_cache` 仍是温热的；只要漏带 `no_cache`，就会命中前一轮/生产流量的旧答案。
- **代码出处**：`backend/answer_cache.py:17`（进程内 LRU）+ `backend/answer_cache.py:113`（`clear()`）；
  温热污染机理见 `test_light_exit_gates.py` `_focus_route` docstring。
  > 注意：只要 C1/C2 的 `no_cache=true` 严格生效，`cache_key=None` 已彻底跳过读取，温热**不影响**；
  > 本项风险**仅在「漏带 no_cache」时成立**。
- **今天是否已被防住**：**否（无隔离强制）**。
  - 证据：全仓**没有任何代码/配置强制**「评测必须用干净进程」；`answer_cache` 温热机制本身存在，
    依赖人工纪律。
- **命令（绕开动作）**：评测前**重启服务进程**（或起独立评测专用实例）；若只能复用进程，则每次评测批前调
  `answer_cache.clear()`（`backend/answer_cache.py:113`）清空进程内缓存。更稳的是 C1/C2 的 `no_cache=true`
  全程严格开启，使温热无机会被读到。

### C4 · 绕开「judge 用路由 tier / `cache_hit_rate` 当质量分」
- **绕开什么**：judge 不去读系统**实际返回的 `content` 文本**，而是拿 `routing_metrics` 的
  `tier_mix` / `cache_hit_rate` / `verdict` 当「系统质量」——缓存命中被记成 `tier="cache"/"qa_cache"`、
  `verdict="pass"`、`cache="hit"`，会被当成「高质量答对」稀释/扭曲分数。
- **代码出处**：
  - `backend/main.py:1767` — 分支 0 命中：`routing_metrics.record("cache", False, "pass", "hit", checked=False)`
  - `backend/main.py:1799` — 分支 0.2 命中：`routing_metrics.record("qa_cache", False, "pass", "hit", checked=False)`
  - 聚合 `backend/routing_metrics.py:85` `record(...)` 与 `:143` `snapshot()["cache_hit_rate"]`
    （`round(_cache_hit / total, 3)`）。
- **今天是否已被防住**：**否（方法论，无代码强制）**。
  - 证据 1：registry E2 取证（`:226-227`）明写「judge 与语料同源时会『和 LLM 一起错』，一致率 ≥0.7 的
    自评不可信；**0/1 判定必须走确定性金标**」—— 这是写在登记表里的硬约束，但**靠人工判据执行，无代码把关**。
  - 证据 2：`docs/project-quality-guide-20260914.md:137` —「不要新增 LLM judge 或让同一个生成模型
    自我打分作为验收」。
  - 证据 3：`routing_metrics` 把缓存命中记成 `verdict="pass"`（main.py:1767/1799），若 judge 误读聚合数即失真。
- **命令（绕开动作）**：judge 必须基于**返回 `content` 文本**与**确定性金标（0/1）**比对；**禁用**「一致率 ≥0.7」
  的自评 / LLM 自我打分。评测批内可加一条断言：`routing_metrics.snapshot()["cache_hit_rate"] == 0`
  （见 C6 验证），若 >0 说明有缓存漏过、本批作废。

### C5 · 绕开「`qa_pairs` 语料版本 ≠ 当前 `law_as_of`（旧法作答）」
- **绕开什么**：即便不走缓存直返，**语料本身的版本**也可能与本次请求的适用法律时点不一致——预生成语料是
  2026-08-23 前用旧法生成的，直返就是用后法答前事。
- **代码出处**：`backend/main.py:1114-1134` — `_qa_direct_return` 的「版本适用护栏」（票 I 的 I-2(a)），
  仅在**跨民法典分水岭**时 miss；其余版本漂移仍可能直返。
- **今天是否已被防住**：**否（仅部分，票 I 在途、未全量完成）**。
  - 证据 1：registry E2「版本绊线」仍是 `GAP-TODO`（`gate_exit_registry.py:191-221`），取证明写
    「三道护栏**没有一条是版本判定** ⇒ 预生成那天的法版本会被无限期当成今天的法作答」。
  - 证据 2：选项指纹护栏对 **219/279** 条空转（`q_fp and stored_fp` 条件，registry `:202-204`）——
    票 I 的 I-5 尚未全部落地。
  - 证据 3：`dispatch-output/takeover-parallel-20260920/baseline.json` 标注 `backend/main.py`
    为 `owner=ticket-I`、**在途** ⇒ 版本护栏今天仍可能漂移。
  - 结论：版本护栏是「部分缓解」，**不是可靠绕开**；唯一可靠绕开仍是 C1 的 `no_cache=true`。
- **命令（绕开动作）**：评测一律带 `no_cache=true`（C1），让 `_qa_direct_return` 整体短路、根本不读语料；
  不要把「E2 关闭后的命中率」当模型质量。

### C6 · 绕开「评测题集与 `qa_pairs` 279 条语料重叠 → 命中率高但非模型能力」
- **绕开什么**：评测题集若包含/近似 `qa_pairs` 里的 279 条，关掉 `no_cache` 时会大面积命中语义缓存，
  命中率虚高，但那测的是语料覆盖不是模型能力。
- **代码出处**：`backend/main.py:1107` `_qa_direct_return` 依赖 `ks.search_qa`（Chroma `qa_pairs`，279 条）；
  语料在场且可达（registry E2「可达性」`:180-183`）。
- **今天是否已被防住**：**否（无题集重叠检查）**。
  - 证据：全仓**没有脚本**比对「评测题集」与 `qa_pairs` 279 条是否重叠；评测入口见
    `docs/project-quality-guide-20260914.md:189`（`evals/retrieval_probe.py`、`evals/validate_cases.py`、
    `backend/scripts/gate2_runner.py`），均未做重叠校验。`qa_pairs` 条目计数来自
    `dispatch-output/i1-e2-hitrate-20260920/probe-A-corpus-inventory.json`。
- **命令（绕开动作）**：评测前核对题集不与 `qa_pairs` 279 条重叠（或干脆 C1 强制 `no_cache=true`）；
  若必须测「真实命中率」，用与语料**无交**的题集，并在独占干净进程（C3）里跑。

---

## 验证 `no_cache` 是否真的生效（评测批内可加的断言）

1. **缓存命中率断言**：评测批结束时 `routing_metrics.snapshot()["cache_hit_rate"] == 0`
   （聚合在 `backend/routing_metrics.py:143`；命中才 `+1` 在 `main.py:1799`）。若 `>0` ⇒ 有请求漏带
   `no_cache`，**本批作废重跑**。
2. **同题双发比对**：同一问句发两次——第一次带 `no_cache=true`、第二次也带 `no_cache=true`，二者 `content`
   应一致且与「不带 no_cache 的同题」不同（后者可能来自缓存）。用 `backend/scripts/_client.py:57` 的
   `chat(..., no_cache=True)`。
3. **确定性金标对照**：judge 用确定性 0/1 金标比对 `content`（见 C4），不引用 `cache_hit_rate` / `tier_mix`。

> 总结：六条全部指向同一个可被执行的动作——**评测请求严格带 `no_cache=true` + 用干净进程 + judge 读
> `content` 文本而非路由聚合**。今天这六条**均未被自动/强制防住**（registry E1/E2 仍 `BLOCKED`、字段默认
> `False`、无强制护栏），所以它们是「必须人工逐项打勾」的批前 checklist，不是「已经安全」。

---

## §2 五段回报（T9）

① **结论**：跑评测要绕开的是「E1 进程内 `answer_cache` 精确/近重复命中」与「E2 持久语义缓存
`_qa_direct_return`（Chroma `qa_pairs` 预生成语料）」两类缓存直返，以及「judge 误读路由聚合当质量分 /
语料版本≠当前法 / 题集与语料重叠」三类失真源；唯一可执行的硬开关是请求体 `no_cache=true`（同时旁路三处缓存）。
这六条今天**均未被自动/强制防住**（E1/E2 评测可信度仍为 `BLOCKED`、字段默认 `False`、无任何强制护栏），
所以它们是评测批前必须人工逐项打勾的清单，不是「已经安全」。

② **产物**：
- `dispatch-output/t9-eval-credibility-20260920/checklist.md`（本文件，含 6 条 checklist + 验证命令）
- `dispatch-output/t9-eval-credibility-20260920/findings.json`（结构化镜像）
- 关键读数/锚定：`HEAD=beb4d5c…`；`sha256(main.py)=a31b7b4c…`；`sha256(retrieval.py)=59596c82…`；
  registry E1 评测可信度 `BLOCKED`（gate_exit_registry.py:167-170）、E2 `BLOCKED`（:224-227）；
  前科数字 `multi_ok 0.43/0.57/0.64`（:169-170）。

③ **判据对照**（卡要求：逐条「绕开什么 + 代码出处（文件+符号）+ 今天是否已被防住(+证据)」）：
- 满足：C1–C6 每条均给出 绕开什么 / 文件+符号+行号 / 防住与否+证据 / 命令，可直接贴进评测批 checklist。
- 满足：给出「哪一行开关」（`schemas.py:55` `no_cache` 默认 False；`main.py:1740` 令 `cache_key=None`；
  `main.py:1793` 短路 `_qa_direct_return`）与「哪条命令」（`chat(token,q,no_cache=True)` / curl 带
  `"no_cache":true` / `answer_cache.clear()` / `routing_metrics.snapshot()["cache_hit_rate"]==0`）。
- 边界：无任何一条写成「应该已经防住了」；凡无法从代码/registry 证实的（如「某未写脚本做了题集重叠检查」）
  均标注为「否 / 未能证实」。

④ **我复跑的命令**（供 Owner 照跑核验本结论）：
```
# 1) 锚定（本清单首部三值，须与结论同版本）
cd C:/Users/33393/Desktop/ai-legal-helper
git rev-parse HEAD
sha256sum backend/main.py backend/retrieval.py

# 2) 验证 no_cache 开关存在且默认 False（C1/C2 证据）
grep -n "no_cache: bool = False" backend/schemas.py          # 期望 :55
grep -n "cache_key = None if body.no_cache" backend/main.py  # 期望 :1740
grep -n "if body.no_cache" backend/main.py                  # 期望 :1793

# 3) 验证 registry 两格仍 BLOCKED（前科未解除）
grep -n "评测可信度" backend/gate_exit_registry.py | head
#   期望 E1 行 167-170、E2 行 224-227 为 BLOCKED

# 4) 验证官方评测脚本已带 no_cache=True（软保护，非强制）
grep -rn "no_cache=True" backend/scripts/eval_exam.py backend/scripts/capture_eval.py backend/scripts/_client.py

# 5) 评测批内断言（C6 验证）：跑完评测后缓存命中率必须为 0
#   python -c "import routing_metrics; print(routing_metrics.snapshot()['cache_hit_rate'])"
#   期望 0.0；非 0 说明有请求漏带 no_cache，本批作废。
```

⑤ **诚实登记**：
- **读不到/未证实**：本卡为只读整理，未启动任何评测进程，因此「评测批实际 `cache_hit_rate` 是否为 0」
  属未实测，仅给出验证命令，不替 Owner 下结论；未声称「今天已被防住」。
- **越界写声明**：本次**未写**任何 `backend/**`、未触碰 `retrieval.py`/`test_exact_article_lookup_sourcekey.py`/
  `docs/code-review-report-02e3851-20260918.md`，未执行任何 git 写操作；唯一写入为交付目录
  `dispatch-output/t9-eval-credibility-20260920/`（两张产物）。
- **未能证实项**：C5「版本护栏今天是否完整」—— 因 `main.py` 被票 I 在途编辑，仅据 registry `GAP-TODO`
  与 baseline `owner=ticket-I` 判定为「否（部分）」，未实测 I-2(a) 在运行时的实际拦截率。
