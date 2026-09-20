# 票 H / I / J · 出口×闸门登记表掉出的三簇缺口（2026-09-20 开票）

**起票人**：执行 S5 后续 + 立「出口×闸门」登记表的会话。
**开票依据**：`docs/gate-exit-registry.md` 里 9 格 `GAP-TODO` —— 表一立起来就读出来的东西，
不是推测，每格的取证都在那张表里（真源 `backend/gate_exit_registry.py`）。

**归属一览**（谁管哪几格）：

| 出口 × 闸门 | 归 | 为什么这么分 |
|---|---|---|
| E5 配额降级注记 / E5 写缓存闸 / E6 写缓存闸 | **票 H** | 都是合同分支那一个 `if` 块里的事，一次改完 |
| E1 版本绊线 / E2 版本绊线 | **票 I** | 同属"缓存复用型答复不受保护"，且真正的存量面是 E2 的持久语料 |
| E7 多选完整性 / E7 写缓存闸 | **票 J** | 同一句话：**把轻量出口的闸门对齐到流式出口** |
| E8 版本绊线 / E9 版本绊线 | 票 C（`docs/handoff-s6-stream-exit-version-gate-20260920.md`） | 已另行派发，不在本文件 |

---

## 0. 三张票共用的边界与判据口径（先读这一节，越界即停手回报）

**边界**：不推送、不部署；**不改任何开关默认值**（`fast_path_law_version_check` 必须保持 `False`，
谁都不许为了验证去改它）；不动 `backend/agent/**`（判定真源只消费）；不动 `evals/` 冻结资产；
`backend/scripts/gate2_runner.py` 的 sha256 须保持 `ae2e412059ed68ac1514c62727cee61c50b8a2d6fe7e38a77c7e05631847e295`；
`backend/app.db` 绝对只读（不写事务、不 VACUUM、不改 schema）；pytest 的 basetemp **不要设在 `backend/` 内**
（`tests/test_log_field_whitelist.py` 递归扫全树）；日志新字段须先登记（同钩子会拦）。

**判据口径**（本轮立过，别再自创）：

1. **先红**：每条新断言都要看过它为**正确的原因**红（功能缺失，不是 TypeError/笔误），红因原文留痕。
2. **可达性优先**：声称"某处已受保护"之前，必须在**真实配置下打桩计数**证明那条分支真被走到 > 0，
   跑完删桩。S5 就是缺这一步，交完才发现那条出口零流量。
   ⇒ 顺带先读既有测试的 docstring 与 fixture（`backend/tests/test_flagship_quality.py` 第 3 行就写着
   "text 无 light 档，use_light=False"）——**别为已有人钉过的事实再起一次付费探针**。
3. **变异审计 = 全量 + junit 差分 + 比"分母"**（口径见
   `docs/handoff-independent-sessions-20260919.md` 环境第 4/5/6 条）。
   判据：基线 `tests>0 且 errors=0`，且每个变异体的 `tests` 与基线**相等**，否则记 `denominator-drift`
   而不是 KILLED；`anchor-error` 一律计入坏消息。**不许**每个变异只跑一个定向文件。
   现成执行器：`dispatch-output/s5-followup-20260920/run_mutations_full.py`（已按此口径改过）。
4. **认形状不认行号**：本仓行号已漂过五次，最近一次是被一次 5 行的 docstring 改动整体挤掉的。
   断言与取证串里都只写"符号 + 该形状全文唯一"。登记表真源与 ADR 节内出现 `` `:NNNN` `` 形式的取证引用
   会被 `dispatch-output/s5-followup-20260920/verify_doc_claims.py` 判 FAIL——那是机检，不是建议。
5. **交付完必须回表**：改完把 `backend/gate_exit_registry.py` 对应格子从 `GAP-TODO` 改成实际状态 + 取证，
   跑 `backend/scripts/gen_gate_exit_registry.py` 重生成 md，再跑 `backend/tests/test_gate_exit_registry.py`。
   ⚠️ 不回表哨兵必红（`test_committed_md_is_the_generated_artifact`），这不是 flaky，不许跳。
6. **门禁留痕要记"跑在哪棵树"+ 分母读数**。live 工作树跑全量 = 禁止（副本树内允许，见 §0 边界）。
7. 静态门：`ruff check` / `ruff format --check` / `mypy` rc=0 + `pre-commit` 手跑
   （`backend/venv/Scripts/pre-commit.exe`，钩子**没接进 git**），且**对暂存集整体跑**不要手挑 `--files`。
8. 端点级设施可直接复用：`backend/tests/_sse_harness.py` 的 `sse_client(route=...)` + `chat_frames()`。

---

## 票 H · 合同出口的写缓存闸与降级注记（3 格）

**射程**：`stream()` 分支0.3 合同报告那一个 `if` 块，加它对应的注记帧出口。别的不动。

**H-1 写缓存闸（近乎免费，先做这条）**
- 事实（取证在登记表 E5/E6）：合同分支在收口后**立刻**算 `bad = citation_verify(answer)`，
  **下一行**就是 `if cache_key:` 的写闸，却没看 `bad`；而 `answer += note` 发生在 `put` **之后** ⇒
  引用未收录的合同报告以"无告警"形态进缓存，被零 token 复播时**丢掉那条告警**。
- 必须交付：写闸改成同时看 `bad`（形如 `if cache_key and not bad:`）。**判定已经有了，不要新造。**
- 判据：①先红——构造 `citation_verify` 返回非空的样本，断"缓存里一次写入都没有"；
  ②控制组——`bad` 为空时**必须**仍写缓存（否则你把特性改没了却报成"修好了"）；
  ③一条能杀"删掉 `and not bad`"的变异用例。
- 代价（必须一起登记）：带告警的报告从此不进缓存 ⇒ 同一份合同重问会重烧 token。
  若 Owner 不接受，替代方案是"照写，但把告警一并写进被缓存的那份"——那是改缓存条目语义，要另裁。

**H-2 配额降级注记**
- 事实：合同分支没有 `NOTE_QUOTA`/降级出口，failover 全灭时只能落到外层 error 帧 ⇒
  用户看到"无响应"而不是"已降级"。
- 必须交付：**先出取证再动手**——量清合同分支的 failover 路径今天到底有几种收场（打桩计数，不许推断），
  然后二选一：接一条与流式同族的降级注记，或**明确判为 NA 并给理由**回表。
  ⚠️ 别接一道恒不命中的空门（`[PL#14]`）。合同事实来自上传文本而非用户自述，
  `_fast_path_fact_texts` 那套取法在这分支不成立——这条票**不含**版本判定，那是票 I 的事。

**H-3 不许顺手做**：不合并合同缓存键的构造逻辑、不改 `_build_contract_data`、不动 `contract_verify.py`。

---

## 票 I · 缓存复用型答复的版本判定（2 格 + 一条注释订正）

**射程**：E1（分支0 精确/近重复直返）与 E2（分支0.2 QA 预生成语料直返）。

**先读三条实测事实（票 C §4b Q2 裁定时量的，别重新调研）**：
- `answer_cache` 是**进程内** `rc.LRU(maxsize=512)` + `TTL=6h`，重启与知识增删（`retrieval.invalidate()`
  → `clear()`）都清空 ⇒ E1 的暴露窗 **≤ 6 小时**，不是一直到库；且 `clear()` 是**唯一删除口**
  （没有按 model 删的能力，全库清会连合同报告一起清掉）。
- **E2 读的完全是另一个存储**：Chroma 持久预生成语料（`main._qa_direct_return` 的 docstring 原话
  "QA 持久语义缓存直返（8-23 智谱免费 token 预生成语料）"）——**无 TTL、重启不清、`answer_cache.clear()` 碰不到**。
  三道护栏是 score ≥0.92 / 选项指纹 / "条文仍在库且有效"，**没有一条是版本判定**。
- ⇒ **本格是全仓唯一真正的存量面**：预生成那天的法版本会被无限期当成今天的法作答。

**I-1 必须先量的一个数**：E2 的**命中率**。它至今未量 ⇒ 严重度排不了序。
量法：真实配置下打桩统计 `_qa_direct_return` 的命中次数 / 请求次数（只读，不写库），
按题集分桶报。**这个数决定后面走 (a) 还是 (b)，不要跳过。**

**I-2 两条路，按命中率取其一（先报数再动手）**
- **(a) 给语料打版本标**（推荐，若命中率可观）：一次性离线给每条 QA 记录写入其作答所依据的法版本基准日；
  运行时按 `law_as_of` 过滤，不匹配即 miss 回落 LLM。
  **好处**：保住"零 token 直返"这个特性本身。代价：要重跑一次离线标注（要花钱，需 Owner 点头）。
- **(b) 读侧补一次判定**：直返前跑一次 `law_version_crosses_watershed`。
  **代价要说清**：读侧从"零成本"变成"每次一次判定"，票 C 裁 Q2 时正是为此**否掉**了这个方案。
  若你选 (b)，必须在回报里写明"这与票 C §4b Q2 的裁定相反，理由是命中率/风险使它划算"。
- E1 那条：若 (a)/(b) 只做 E2，E1 必须回表改成 `GAP-ACCEPTED + 理由（≤6h 窗口 + 开门需重启）`，
  **不许留成"看着像修了"**。

**I-3 顺带一行（同族错误，别另开票）**：`backend/request_bootstrap.py` 里 `law_as_of` 字段上方那句注释
（全文唯一锚点：`缺省 None = create_run 落 date.today()`）在替一个快车道不存在的机制背书——
**快车道不经过 `create_run`** ⇒（本轮已被它误导过一次裁决）。改成"仅 agent 路径如此；
快车道由 `main._fast_path_law_as_of` 落当日"。只改注释，不许动行为。
（本条**故意不写行号**：那个字段在同文件出现两次，行号又漂过五次，注释原文才是稳定锚。）

**I-4 不许动**：`_qa_direct_return` 的三道既有护栏、`record("qa_cache", ...)` 的评测口径
（`[fz]` 有 qa_cache 污染 judge 基线的前科，评测必须继续 `no_cache` 绕它）。

---

## 票 J · 把轻量出口的闸门对齐到流式出口（2 格）

**射程**：`_light_buffered_locked` 的答复出口（登记表 E7）与它的写缓存闸。

**J-1 事实**：`quality.multi_incomplete` 全仓**只有一个调用点，在流式分支** ⇒ 轻量路径的多选漏答零防护；
两条写缓存闸的**字面条件集交集只有 `cache_key`**——轻量侧对 `_cache_write_ok`（确定性写闸）与
`not multi_bad` **无任何对应物**。流式的 `not flag_degraded` 在轻量侧由 `verdict == "pass"` 承担
（`_light_buffered_locked` 里 `except QuotaExhausted` 那一支把 verdict 写成 `v.reason or "low_quota"`）
⇒ 不是漏闸，但**降级与自检 FAIL 两个信号被合进同一个条件**，归因粒度比流式粗。

**J-2 必须交付**
- 轻量分支补多选完整性（症状检测 + 注记 + 拦缓存），**复用**流式那份纯函数，不许重写规则；
- `_cache_write_ok` 对轻量路径同样生效；
- 归因粒度：给 `_LightResult` 补一条独立的降级信号（**别复用 `verdict`**——它的字段注释已明令
  "刻意不复用 verdict 承载该信号"，两条降级原因要能同时出现在一张日志里）。

**J-3 两条硬提醒**
- **E7 今天零流量**（`llm_registry` 实配的 `(modality,tier)` 只有 `('text','flag')` ⇒ `use_light` 恒假）。
  ⇒ 本票改完**线上效果为零**，价值在"票 C 之后两条出口对称"。别拿"评测有提升"当交付证据，
  也别为了让门好看去改 `.env` 的角色配置（那是 P9 要读、不许读改的东西）。
- 判据只能是**端点级**：用 `_sse_harness.sse_client(route="light_buffered")`，
  单元级直调 `_light_buffered` 看不见调用点（这条本轮踩过一次，仪器 `capture_light_baseline.py`
  对调用点改动完全不可见）。

---

## 回报格式（三张票通用，照抄填数）

```
P0 边界自查：开关默认值=<必须 False>  agent/=未动  evals/=未动  gate2_runner sha=<必须 ae2e4120…47e295>
HEAD=<hash>   开工前脏项=<必须"无">
逐条：<H-1/H-2/H-3 | I-1…I-4 | J-1…J-3> → 做了什么 + 证据文件
先红：<用例名> 红在 <断言原文>（不是 TypeError）
可达性：打桩方法=<…>  命中次数=<n>  桩已删=<是>
变异：逐条 <名字> → KILLED/SURVIVED + newly_red=<用例名>；**分母** 基线 tests=<n> errors=<n>，
      每个变异体 tests=<n>（必须与基线相等）；跑在哪棵树=<路径>
回表：改了哪几格 <E? × ?>  → 新状态 ；gen 已跑=<是> ；test_gate_exit_registry=<n passed>
静态门：ruff=<rc>  ruff format --check=<rc>  mypy=<rc>  pre-commit(暂存集全跑)=<rc>
车道/门禁：<passed/skipped/failed> + RUN_VALID 与否 + 真实库零写入读数
如实登记未覆盖=<必须写出"这条改完之后，哪几格仍未受保护">
```
