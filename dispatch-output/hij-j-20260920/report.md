# 票 J · 把轻量出口的闸门对齐到流式出口（E7 两格 + 新增 E16）

**开工基线**：`b6f0fcc`（票 H 的最后一个提交 —— 票面 §0.5.3 要求「每票开工前确认上一票已合入」）
**本票提交**：`1ddeaf0`
**票面**：`docs/handoff-gap-tickets-h-i-j-20260920.md` §票 J
**射程**：`_light_buffered_locked` 的答复出口（登记表 E7）与它的写缓存闸。别的不动。

---

## P0 边界自查

```
P0 边界自查：开关默认值=保持 False（preflight 生效值读数全部 false）  agent/=未动  evals/=未动
            gate2_runner sha=ae2e412059ed68ac1514c62727cee61c50b8a2d6fe7e38a77c7e05631847e295 ✓
HEAD=b6f0fcc（开工时，含 1c05599）  开工前脏项=无
```

六条自查读数落盘：`00-pre-flight.json`（含一条与票面 J-3 互相印证的读数：
`has_role_text_light=false` ⇒ **本出口今天零流量**）。
⚠️ 副作用已还原：`preflight_p9.py` 会就地重写它自己的 `00-pre-flight-readings.json`（只差行尾换行）
⇒ 已 `git checkout --`，本票不带该文件。

---

## J-2 三项交付（逐条）

### (a) 多选完整性：症状检测 + 注记 + 拦缓存

- **复用**流式那份纯函数 `quality.multi_incomplete`（票面 J-2 明令「不许重写规则」）——
  改后全仓仍只有这一处**规则**；本票加的是**第二个调用点**，不是第二份判定。
- 症状命中 ⇒ `answer += NOTE_MULTI_INCOMPLETE` + 追加注记帧（**新出口 E16**）+ 落
  `kind="multi_incomplete"` 日志 + `not multi_bad` 拦缓存（与流式 E11 同形状）。
- 注记措辞顺手收成**唯一真源** `main.NOTE_MULTI_INCOMPLETE`：流式 E11 原来内联字面量，
  现在两处共读同一个常量 —— 否则「同一症状两句话」会漂移（这正是 code-review 训练出来的姿势）。

### (b) `_cache_write_ok` 对轻量路径同样生效

轻量那条闸由三条件改为**六**条件，与流式 E8 逐条对齐：

```
cache_key · not res.degraded · _cache_write_ok(pre, answer) · res.verdict == "pass"
         · not multi_bad · not res.law_version_hit
```

### (c) 独立降级信号（不复用 verdict）

- `_LightResult` 补 `degraded: bool = False`；**只有** `_light_buffered_locked` 里
  `except QuotaExhausted` 那一支点亮（= 升级旗舰时配额耗尽、退回轻量产物 + NOTE_QUOTA）。
  刻意**不含**「轻量即旗舰、无更强者可升」那一支：那是能力上限不是降级。
- `observability._ACCOUNT_FIELDS` 登记 `degraded`，并记进 account 日志
  ⇒ 「自检 FAIL」(verdict) 与「配额降级」(degraded) 两条原因能**同时出现在一张日志里**。

---

## 判据：端点级 7 条（4 先红 + 3 控制腿）

为什么必须端点级（票面 J-3 第二条）：本票三处改动都在**调用点**上，单元级直调
`_light_buffered` 看不见它们 —— 上一轮 `capture_light_baseline.py` 就是这么给过一次"平凡相同"的 sha。

**先红在「改前副本树」上取得**（不是语义回滚：`git archive b6f0fcc` + **只把这一个测试文件**放进去
⇒ 真正的"老源码 + 新测试"）：`04-red-pretree.stdout.txt`

```
4 failed, 3 passed
FAILED …::test_light_path_flags_multi_incomplete_and_blocks_cache
FAILED …::test_light_path_cache_write_ok_blocks_foreign_citation
FAILED …::test_light_path_degraded_signal_is_independent_from_verdict
FAILED …::test_control_light_path_non_degraded_records_false_and_caches
```

红因原文（逐条都是**功能缺失**，不是 TypeError/笔误）：

| 用例 | 红因原文 |
|---|---|
| 多选漏答 | `AssertionError: 多选漏答的答复进了缓存：[{… 'answer': '**A. 试用期…正确…本题正确答案为 A。', 'model': ''}]` |
| 库外引用 | `AssertionError: 引用不在检索条文内的答案进了缓存：[{… 'answer': '根据《民法典》第五百七十七条…'}]` |
| 降级信号 | `AssertionError: 降级信号未独立落盘：{… 'verdict': 'vague' …}` / `assert None is True` |

改后同一文件在同一条命令下 **7 passed**（`02-green-new-source.stdout.txt`）。

**控制腿（3 条）**——每一条都断言「**同一请求形状照常写一次缓存**」，因此它们同时是上面先红用例的
**分辨率证明**（证明 `sink == []` 是被闸拦下，而不是「压根没有 cache_key」）：

| 控制腿 | 断言 |
|---|---|
| `test_control_light_path_does_not_flag_full_multi_answer` | 同题但三项全给 ⇒ `joined == _ANS_FULL` 且写缓存 **1** 次 |
| `test_control_light_path_plain_question_still_cached` | 非多选题 ⇒ 照常写 **1** 次 |
| `test_control_light_path_cache_write_ok_allows_retrieved_citation` | 引用 ⊆ 检索条文 ⇒ 写 **1** 次 |

---

## ⚠️ 自捉的一条空枪（必须留痕）

第一版 study_aid 那两条用例只桩了 `classify_intent`，但 `prepare_fast_path` 在
`feature_study_retrieval` 为假时把 `docs` **硬置为 `[]`** ⇒ `sources` 为空 ⇒ `_cacheable` 判假 ⇒
**`cache_key` 为 None** ⇒ 写缓存闸根本不会被求值 ⇒ `assert sink == []` **恒真**
（为错的原因绿：它测的不是 `_cache_write_ok`）。

**修法**：把该 route 造到「检索有命中」（`feature_study_retrieval=True` + 桩 `retrieve_exam` 返回一条
命中 + `scenario_supplement_docs` 返回空），并在控制腿里证明**同一请求形状确实写得进缓存**。
这条已写进测试文件的 docstring，免得下任再踩。

另一条同类修法：`main.NOTE_MULTI_INCOMPLETE` 在改前树上不存在 ⇒ 若测试直接读它，
红因会是 `AttributeError`（票面 §0 判据 1 明确不接受）。改成经 `_multi_note()` 显式断言取用
⇒ 红因是 `AssertionError: main 里没有 NOTE_MULTI_INCOMPLETE 常量（注记无唯一真源）`；
同时不给 `getattr(..., "")` 兜底留路（那会让「常量被删」变成恒真）。

---

## 回表

E7×「多选完整性」/ E7×「写缓存闸」两格 `GAP-TODO` → `PASS`；新增 **E16** 行
（轻量出口的多选漏答注记帧，`traffic=零流量（随 E7 不可达）`）。
引号口径 `grep -c '"GAP-TODO"'`：**5 → 3**（= 8 − 票 H 的 3 − 本票的 2）。
`gen_gate_exit_registry.py` 已跑；`tests/test_gate_exit_registry.py` + 本票新用例合计 **21 passed**。

---

## 门禁与零流量声明

- 静态门：`ruff check` rc=0 / `ruff format --check` rc=0 / `mypy .` rc=0（73 files）/ pre-commit（暂存集）rc=0。
- **本票线上效果为零**（票面 J-3 第一条）：`llm_registry` 实配只有 `('text','flag')` ⇒ `use_light` 恒假。
  **不拿「评测有提升」当交付证据**，也没有为了让门好看去改 `.env` 的角色配置
  （那是 P9 要读、不许读改的东西）。本票的价值是"票 C 之后两条出口的闸门形状对称"。
- E7/E16 两格在表里都写着「代码正确、**不是**线上生效」。

---

## 如实登记未覆盖

1. **E7/E16 今天零流量** ⇒ 所有判据都是端点级替身模型，没有线上读数。
2. `not res.degraded` 这一条与 `res.verdict == "pass"` **在当下实现里冗余**
   （`degraded` 只在 verdict != "pass" 的那一支点亮）⇒ 见「变异」节 J-M3：
   **预期 SURVIVED**，它的价值是**归因**（日志可分开读）与防御性，不是拦截。
3. 票 I（E1/E2 版本判定）**未开**：范围外，且 I-2(a) 要花钱、I-6 要先报选型。

---

## 变异（全量 + junit 差分 + 比分母）

跑在 `dispatch-output/hij-j-20260920/copytree`（`git archive 805ad78` + 假 `backend/.env`）。
每个跑次**唯一 basetemp**（票 H 的教训：共用 basetemp 会撞 safe-delete 批量守卫）。
**基线**：`tests=1390 failures=8 errors=0`；**五个变异体 tests 都等于 1390、errors 都等于 0** ⇒ 无分母漂移。

| 变异 | 对准哪个语义点 | 结果 | `newly_red`（本票判据） |
|---|---|---|---|
| **J-M1** `multibad_cond_removed` | 写闸少 `not multi_bad` | **KILLED** | `test_light_path_flags_multi_incomplete_and_blocks_cache` |
| **J-M2** `cache_write_ok_removed` | 写闸少 `_cache_write_ok(pre, answer)` | **KILLED** | `test_light_path_cache_write_ok_blocks_foreign_citation` |
| **J-M3** `degraded_cond_removed` | 写闸少 `not res.degraded` | **SURVIVED**（预期！） | 无 |
| **J-M4** `log_degraded_removed` | account 日志少 `degraded=` | **KILLED** | `test_light_path_degraded_signal_is_independent_from_verdict` + `test_control_light_path_non_degraded_records_false_and_caches` |
| **J-M5** `signal_never_set` | 降级点少 `degraded=True` | **KILLED** | `test_light_path_degraded_signal_is_independent_from_verdict` |

五个变异体的 `main_py_restored_byte_exact` 全为 `true`。

### J-M3 SURVIVED 是**预期读数**，不是漏网（如实登记）

`not res.degraded` 与 `res.verdict == "pass"` 在当下实现里**冗余**：`degraded` 只在
`except QuotaExhausted` 那一支点亮，而那一支把 verdict 写成 `v.reason or "low_quota"`（≠ `"pass"`）
⇒ 拿掉 `not res.degraded`，写闸仍被 `verdict` 拦住。它的价值是**归因**（日志里两条降级原因能分开读）
与**防御性**（将来若有人改 verdict 的取值域，拦截仍在），**不是拦截** —— 拦截由 J-M1/J-M2 负责杀，
两条都 KILLED。⇒ 本格登记为「条件保留、理由已写明」，**不写成"已受保护"**。

### 基线的 8 条红与本票无关

基线的 8 条红与本报告「未覆盖」节提到的 flaky 簇**逐字相同**（`test_backup_data`×4、
`test_capture_eval`×1、`test_request_bootstrap::test_persisted_image_files_are_cleaned_after_later_failure`×3），
**本票新增的 7 条一条都不在其中**。同一条命令在不同跑次给出 **0 红 / 3 红 / 8 红**（票 H 段已留痕）
⇒ 既有 flaky 簇，与票 J 无关。（已列为可派发的独立任务 **T1**：
`dispatch-output/hij-h-20260920/16-dispatch-plan.md`。）

---

## ⚠️ 本轮自捉的第二个假绿：模块级缓存跨测试文件污染（提交 `805ad78` 修）

第一次全量跑时，基线里出现 **本票自己的 3 条用例红**（而定向单跑全绿）。根因已复现：

`answer_cache` 是**模块级** LRU，而 `test_light_exit_gates.py` 与 `test_flagship_quality.py`
用的是**同一个问题 + 同一份单条命中检索**（都来自 `_sse_harness._one_hit_retrieval`）
⇒ `_cache_key(pre)` **逐字相同**。全量 lane 里旗舰那个文件先跑并写入该 key ⇒ 分支0（缓存命中）
在本文件之前直返 ⇒ 请求**根本走不到分支1（轻量）**。

症状极具误导性（`10-pollution-repro.stdout.txt`）：

```
E  assert '根据《劳动合同法》第十九条，试用期最长六个月。' == '本案诉讼时效为三年，自 2022 年 6 月 1 日起算。'
```

返回的是**旗舰那份答案** —— 看着像"轻量分支坏了"，其实是"根本没进轻量分支"。
**修法**：`_focus_route()` 里 `answer_cache.clear()`（与 `test_flagship_quality.py` 同款卫生）。
**两条读数**：复现命令 `pytest tests/test_flagship_quality.py tests/test_light_exit_gates.py`
改前 FAILED → 改后 **8 passed**；定向 `pytest tests/test_light_exit_gates.py` 两侧都 7 passed
⇒ **定向单跑看不见这个问题**，这正是"定向绿 ≠ 全量绿"的实例。

---

## 回报（照票面格式逐条填数）

```
P0 边界自查：开关默认值=False  agent/=未动  evals/=未动  gate2_runner sha=ae2e4120…47e295
HEAD=b6f0fcc（开工）→ 1ddeaf0（本票）  开工前脏项=无
逐条：J-2(a) → 复用 quality.multi_incomplete + E16 注记帧 + 拦缓存 + kind=multi_incomplete 日志
      J-2(b) → _cache_write_ok 进轻量写闸（条件集三 → 六）
      J-2(c) → _LightResult.degraded 独立信号 + 登记进 _ACCOUNT_FIELDS 并落日志
      J-3     → 未改 .env、未改角色配置；判据全端点级（sse_client(route="light_buffered")）
先红：见「判据」节表格，红因原文逐条为 AssertionError（不是 TypeError）—— 在改前副本树上取得
可达性：打桩方法=夹具造真 use_light（tier/准入/has_role）+ spy answer_cache.put/log_account；
      命中次数=端点级各 1 次；桩已删=是（全在 monkeypatch 作用域内自动还原）
变异：J-M1 KILLED / J-M2 KILLED / **J-M3 SURVIVED（预期，冗余条件，理由见「变异」节）** /
      J-M4 KILLED / J-M5 KILLED；分母 基线 tests=1390 errors=0，每个变异体 tests=1390 errors=0；
      跑在哪棵树=copytree（git archive 805ad78 + 假 .env）
回表：E7×多选完整性 / E7×写缓存闸 → PASS；新增 E16；gen 已跑=是；哨兵+新用例=21 passed
静态门：ruff=0  ruff format --check=0  mypy=0（73 files）  pre-commit(暂存集全跑)=0
车道/门禁：定向 7 passed；本票未在 live 树跑全量（§0 边界）⇒ 无 RUN_VALID 读数
如实登记未覆盖：E7/E16 零流量；not res.degraded 当下冗余（归因用）；票 I 未开
需要 Owner 决策或放行=无（本票不含花钱项；也未改任何开关默认值）
```
