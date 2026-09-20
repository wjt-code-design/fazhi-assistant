# 票 I · 缓存复用型答复的版本判定（E1/E2 两格收口）

**开工基线**：`1e969f2`（票 J 的最后一个提交）→ **本票提交**：`beb4d5c`（I-6/I-3）+ `1fb8ef1`（I-2(a) 与回表）
**票面**：`docs/handoff-gap-tickets-h-i-j-20260920.md` §票 I
**Owner 授权**：语料写入与 I-2(a) 均获口头授权；**实际零花费**（见下）

---

## P0 边界自查

```
P0 边界自查：开关默认值=保持 False（preflight 全部 false）  agent/=未动  evals/=未动
            gate2_runner sha=ae2e412059ed68ac1514c62727cee61c50b8a2d6fe7e38a77c7e05631847e295 ✓
HEAD=1e969f2（开工时，含 1c05599）  开工前脏项=无
```

六条读数落盘：`00-pre-flight.json`（含 side_effect 说明：`preflight_p9.py` 会重写它自己的读数文件，已还原）。

---

## 本票做了什么（四项，按票面的 I-1..I-6 逐条对）

| 票面条目 | 状态 | 交付 |
|---|---|---|
| **I-1** 先量命中率 | **不重做** | 开票人已完成（`dispatch-output/i1-e2-hitrate-20260920/`，五台仪器 A–E）。本票只引用其结论 |
| **I-2** 两条路二选一 | **选 (a) 并已实现** | 给语料标版本基准日 + 运行时护栏。**刻意不选 (b)**：读侧加判定会打穿"零 token 直返"这个特性本身，而票 C §4-Q2 已裁「不判读侧」——本票的做法是给语料补**数据** + 一次**日期比较**，不是加**判定** |
| **I-3** 注释订正 | **已做** | `request_bootstrap.py`：原句只写「缺省 None = `create_run` 落 `date.today()`」，替一个**快车道不存在**的机制背书 ⇒ 改成分清两条路径 + 点明 ADR-018 已知残留④。**只改注释，行为逐字不变** |
| **I-4** 不许动 | **遵守** | `_qa_direct_return` 的三道既有护栏**一字未动**（本票加的是**第四**条）；`record("qa_cache", ...)` 的评测口径未动 |
| **I-5** 指纹覆盖面 | **核对后确认开票人已登记** | E2×版本绊线 格里已有「三道要打折」+ 60/166/219。**不重做**。另补一条实测细节（见下"顺带纠正我自己"） |
| **I-6** 一行修 | **已做（选型 ②）** | 见下节 |

---

## I-6：`exact_article_lookup` 的源名容错（选型 ②）

**选型报告（票面要求"先报你选哪个再动手"）**：**选 ②**（不加版本承诺、只加一次候选解析），
不选 ①（给 `canon_source` 加「宪法→宪法（1982年）」别名）—— 理由：① 是把**一条数据的特殊情况**焊成别名表条目，
② 是**通用**的（任何带年份括注的源名都覆盖），而 ② 的实现可以**复用已有机制**：

**关键发现（改变了实现形状）**：本仓**早就有**源名归一规则 `retrieval._source_key`，
它的 docstring 原文就点名了这个例子（「必须处理「宪法（1982年）」」），且 `article_in_kb` / `source_in_kb` /
引用校验**都在用它** —— `exact_article_lookup` 是**唯一没用**的读侧。
⇒ 实现 = 在精确匹配取空后，按 `article` 取一遍 + 用 `_source_key` 在 Python 侧筛源名
（与 `article_in_kb` **同形态**）。**不另写「去括注」正则**（那就是第二份规则）。

**真实 KB 先红/后绿读数**（只读探针 `probe_i6_sourcekey_lookup.py`）：

| 读数 | 改前 | 改后 |
|---|---|---|
| `exact_article_lookup("宪法", <抽样条号>)` | **全为 0 条**（5/5） | **全为 1 条**（5/5） |
| `exact_article_lookup("宪法（1982年）", 同条号)` | 1 条（数据本来就在） | 1 条 |
| `article_in_kb("宪法", 同条号)` | **True**（同族早已容忍） | True |
| `_source_key("宪法（1982年）")` vs `_source_key("宪法")` | 都是 `宪法` | 同 |

**blast radius（实测）**：主库 **99 个源名里唯一带括注的就是 `宪法（1982年）`**（138 行）。

判据：`tests/test_exact_article_lookup_sourcekey.py` 4 条 = **2 先红 + 2 控制腿**；
先红在**票 J 提交时的副本树**上取得：`AssertionError: 应恰好取到 1 条（实得 0）`；
两条控制腿（精确命中不得走回退 / 回退不得把同条号别的法条端出来）**两侧都绿**。
⚠️ 一处过程留痕：第一版探针把输出名写死成 `before`，改后再跑**覆盖了 before 的 json** ⇒
before 的原始证据只剩 stdout 那一份；已把探针改成**必须传标签**。

---

## I-2(a)：语料版本基准日 + 第四道护栏

### ① 基准日从哪来（**可审计来源**，不是编的）

票面担心的是"要花钱重跑一次离线标注"。本票查清后改成**零花费**路线：

- 语料 metadata 里**没有任何时间戳**（I-1 已量：`{answer, evidence, options_fingerprint, origin}`，无日期字段）；
- 唯一线索是生成脚本 docstring：「智谱免费 token 批量预生成 QA 解析语料（**8-23 到期前消耗**）」
  ⇒ 生成日 **≤ 2026-08-23**；
- 我也试过 git 历史（`--diff-filter=A`），但 `qa_seeds.py` / `gen_qa_corpus.py` 的"首次引入"提交日期是 2026-09-17，
  **与 docstring 不符**，且本仓有 git 对象损坏的前科 ⇒ **git 日期不可作为基准日**。

⇒ 标注值取 `2026-08-23`（**上界**），并**同时写一个出处字段** `law_as_of_basis_src = "inferred-docstring-8-23"`，
让"这是推断"**随数据走**，而不是只活在报告里。

**为什么这条推断是安全的（本设计的承重点）**：运行时护栏只关心「是否跨分水岭」，
而 2026-08-23 与真实生成日（≤ 同一天）**必然同侧**（分水岭 = 2021-01-01）
⇒ **判定对该推断的误差不敏感**。这一点已写进代码 docstring 与登记表，防后人把它改成"精确日期"再当护栏输入。

### ② 语料写入（先备份、后写、再复核）

```
写前：备份 279 条（corpus-backup-qa_pairs.json，回滚路径）
写前：逐条断言「合并结果 == 原 metadata + 我的两个键」
写入：279/279 条 + law_as_of_basis + law_as_of_basis_src
写后：带该字段 = 279；既有键 answer/evidence/options_fingerprint/origin **一个没丢**（6 键齐全）
```

### ③ 运行时护栏（第四条，前三条一字未动）

```
if law_as_of is not None and basis_raw:
    basis = date.fromisoformat(basis_raw)          # 脏值 ⇒ basis=None ⇒ 不拦
    if basis is not None and (basis >= _CIVIL_WATERSHED) != (law_as_of >= _CIVIL_WATERSHED):
        return None                                # 跨分水岭 ⇒ 回落 LLM
```

- `_CIVIL_WATERSHED = limitation_calc.CIVIL_CODE_EFFECTIVE`（**别名到既有常量，不另立分水岭**）；
- `knowledge_service.search_qa` 增带 `law_as_of_basis`（否则护栏没有输入）；
- 调用点传 `_fast_path_law_as_of(body)`；
- **生产默认路径不变**：该函数**缺省落当日** ⇒ 普通流量与语料基准日同侧 ⇒ **仍零 token 直返**。
  只有显式传了分水岭之前的 `law_as_of`（评测通道）才会 miss。

判据：`tests/test_qa_direct_return_version_guard.py` 5 条 = **1 先红 + 4 控制腿**。
先红在**改前树**上红在功能点：`AssertionError: assert '（预生成解析答案）试用期最长六个月。' is None`
（即"用民法典答 2019 年的事"确实发生了）；4 条控制腿（同侧 / 未给基准日 / 未标注记录 / 脏值）**两侧都绿**。
⚠️ 一处自捉的**红因不合格**：第一版 5 条全红成 `TypeError: takes 1 positional argument but 2 were given`
（旧签名只 1 个形参）—— 票面 §0 判据 1 **不接受**这种红因 ⇒ 改成按签名探测调用后，改前树 `1 failed, 4 passed`。

### ④ 一次自捉的**取错对象**（必须留痕，它本来会造成大面积破坏）

第一版盘点脚本用 `retrieval.vectorstore._collection` 取"语料"——**那是法条主库**
（10266 条，metadata 是 `source/chapter/origin`），**不是** QA 语料。若直接 `--apply`，
就会往主库 10266 条法条上挂垃圾字段。

**没出事的原因只有一个：停下来读了条数**（279 vs 10266）。
⇒ 已把"取集合"收成带**双守卫**的唯一入口 `_qa_corpus.py`：集合名须含 `qa_pairs`
**且**条数 == 期望 279，任一不符即停、不写任何东西；两个脚本都改走它。

---

## 顺带纠正我自己的一处口径（不是票面的错）

我先数出"135 条有 `options_fingerprint`"，与票面 I-5 的 60 不符，看着像票面写错。
量清后：**票面的 60 是对的**——那是**非空**指纹的条数；135 是"**键存在**"（其中 **75 条是空串**）。
⇒ 我的计数口径粗，**没有对外报过这个假差异**（只在内部核了一遍）。
这条细节已记进本报告，正好是 T7（指纹覆盖根因）的输入：**"缺指纹"其实分两种：键都没有 vs 键在但值空**。

---

## 回表（本票收口）

| 格子 | 改前 | 改后 | 依据 |
|---|---|---|---|
| **E2×版本绊线** | `GAP-TODO` | **`PASS`** | I-2(a) 语料标注 + 第四道护栏 + 1 先红/4 控制腿 |
| **E1×版本绊线** | `GAP-TODO` | **`GAP-ACCEPTED`** | 票面要求：E1 不同修必须改 GAP-ACCEPTED + 理由（暴露窗 ≤6h，且**开关要生效本来就得重启**故清缓存不需专门动作；结构性走不到） |
| E2×版本绊线 的 I-6 句 | 「第三道也不比它好」 | 「第三道**已修**」+ 读数 | 防取证描述一个已修好的缺陷 |

⇒ `grep -c '"GAP-TODO"'`：**3 → 1**，剩下 1 处是 `STATUSES` 词表字面量 ⇒ **表内已无 `GAP-TODO` 格子**。
`gen_gate_exit_registry.py` 已跑；`test_gate_exit_registry.py` **14 passed**。

---

## 门禁

- `ruff check` rc=0 / `ruff format --check` rc=0 / `mypy .` rc=0（73 files）。
- 受影响面（两队合跑）：第一次 150 passed / 3 warnings；I-2 后 30 passed / 1 deselected / 0 failed。
- 本票**未在 live 树跑全量**（§0 边界）⇒ 无 RUN_VALID 级读数；全量绿证属 T11（已派发，须串行）。

---

## 如实登记未覆盖

1. **语料基准日是推断**（生成日 ≤ 2026-08-23），不是读数；**但护栏对它的误差不敏感**（同侧论证）。
2. **I-2(b) 未做**（读侧加判定）——这是**有意的选择**，不是遗漏。
3. **E1 是 `GAP-ACCEPTED` 而不是 `PASS`**：它的暴露窗 ≤6h 且结构性走不到，属"接受"而非"修好"。
4. **`options_fingerprint` 那 75 条空串**未处理（属 T7 的射程：先搞清根因再谈补采）。
5. 全量变异审计读数见下节。

---

## 变异（全量 + junit 差分 + 比分母）

跑在 `dispatch-output/hij-i-20260920/copytree`（`git archive 1fb8ef1` + 假 `backend/.env`），每跑次唯一 basetemp。
**基线**：`tests=1399 failures=1 errors=0`（1399 = 票 J 后的 1390 + 本票 9 条新用例）。

| 变异 | 对准哪个语义点 | 结果 | `newly_red` |
|---|---|---|---|
| **I-M1** `fallback_returns_empty`（目标 `backend/retrieval.py`） | 回退整体失效 | **KILLED** | `test_short_name_misses_then_falls_back_to_bracketed_source` + `test_fallback_still_applies_time_filter`（+8 频发红） |
| **I-M2** `source_filter_inverted`（目标 `backend/retrieval.py`） | 源名过滤反了 | **KILLED** | 上述 2 条 + `test_tolerated_but_absent_source_still_returns_empty`（共 3 条本票用例 + 8 频发红） |
| **I-M3** `version_guard_disabled` | 版本护栏永不触发（判据行 → `if False:`） | **KILLED** | `test_pre_watershed_request_misses_the_labelled_record` |
| **I-M4** `watershed_compare_inverted` | 分水岭比较取反 | **KILLED** | 上述 + `test_control_same_side_of_watershed_still_direct_returns`（**2 条**，与预测一致） |
| **I-M5** `dirty_value_blocks` | 脏值当成已知基准日 | **KILLED** | `test_control_dirty_basis_value_does_not_widen_blocking`（+6 频发红） |

**五个变异体全部 KILLED**，且每个变异体 `tests=1399=基线`、`errors=0`（无分母漂移）、
目标文件逐字节还原（新字段名 `target_file` / `target_restored_byte_exact` —— 旧名
`main_py_restored_byte_exact` 对非 `main.py` 的变异会说谎，本轮改准；票 H/J 的历史 verdict 不追改）。

### ⚠️ 仪器修正：I-M1/I-M2 第一轮报 `ANCHOR-NOT-UNIQUE count=0`，**不是 SURVIVED**

原因：共用执行器 `run_mutations_full.main()` 只读写 `backend/main.py`，而这两个变异的锚点在
**`backend/retrieval.py`**（本票新加的 `_valid_docs` 回退与源名过滤）⇒ 它在 `main.py` 里找不到锚点，
报 `ANCHOR-NOT-UNIQUE count=0` 就退出。
**这不是"测试没杀住"，是"变异根本没执行"** —— 按判据「不是 KILLED 就是坏消息」，它是**坏消息**，
所以修仪器重跑，**没有**把它记成成活。
修法：给**自己的**执行器（`run_mutations_ticket_h2.py`，票 H 建的那份）加**每个变异各自的目标文件**支持
（三元组首元素 = 相对路径；二元组仍默认 `main.py`，票 H/J 的写法不受影响），并删掉因此变多余的
`main_py` 预读死代码。重跑读数见本节末尾补记。

### 基线那 1 条红：**不是**先前登记的那 8 条之一

> **⚠️ 勘误（2026-09-21，T2 验收时发现）：这一条其实是本票引入的回归，不是 flaky。** 详见下方勘误块。
> 下段原文保留，作为"我当时怎么归因错的"记录。

本轮基线的唯一红是 `tests.test_phase3::test_chat_streams_persists_and_request_id`。
⇒ 与票 H/J 登记的 flaky 簇（`test_backup_data`×4 / `test_capture_eval`×1 / `test_request_bootstrap`×3）
**不重叠**。四条独立基线读数合起来是 **0 / 3 / 8 / 1** 条红，且第 4 轮的受害者是**另一个文件**
⇒ **flaky 面比先前登记的更宽**。已作为新输入补进 T1 的卡（它本来就要 ≥5 次重复并逐条归因）。

**勘误正文**：

- 真红因：`tests/test_phase3.py` 用 `monkeypatch.setattr(main, "_qa_direct_return", lambda pre: None)`
  桩掉 QA 直返；而本票 I-2(a) 把调用点改成 **2 参**（`_qa_direct_return(pre, law_as_of)`）
  ⇒ 桩抛 `TypeError: lambda() takes 1 positional argument but 2 were given`
  ⇒ 被 `stream()` 的 `[chat-stream]` `except` 吞掉 ⇒ 用例收不到任何 content 而失败。
- **回归窗口 = `1fb8ef1`**：票 J 基线（805ad78）无此红、票 I 基线（1fb8ef1）有此红 ⇒ 恰是本票提交。
- 已修（`a97082b`）：桩改为 `lambda pre, law_as_of=None: None` 并注明教训；修后 `test_phase3.py` **5 passed**。
- **两条教训**：① 改函数**签名/调用元数**时，必须全仓清点该名字的**测试桩**——
  monkeypatch 桩不在导入期暴露，只在被调用时炸，且炸了会被 `except` 吞成"没输出"这种**无信息形状**；
  ② "基线红不在已知 flaky 名单"**不等于**"与本票无关"——那恰恰是**优先怀疑自己**的信号。
