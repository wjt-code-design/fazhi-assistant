# 票 H / I / J · 出口×闸门登记表掉出的三簇缺口（2026-09-20 开票）

**起票人**：执行 S5 后续 + 立「出口×闸门」登记表的会话。
**开票依据**：`docs/gate-exit-registry.md` 里 9 格 `GAP-TODO` —— 表一立起来就读出来的东西，
不是推测，每格的取证都在那张表里（真源 `backend/gate_exit_registry.py`）。

> **本文件同时是交给执行会话的唯一交接文件**：§0 边界与判据口径 → §0.5 执行手册（环境/车道/轮次预算）
> → 三张票的射程 → §9 主会话怎么验收。别再另开一份 handoff。
>
> **现值（读这一段就够，别去数）**：票 C 已收口在 `1c05599`（E8/E9 两格改判 `PASS`），
> 登记表剩 **7 格** `GAP-TODO` = E1/E2 版本绊线（票 I）· E5 配额降级注记 + E5/E6 写缓存闸（票 H）·
> E7 多选完整性 + 写缓存闸（票 J）。**三票的开工基线 = `1c05599`。**

**归属一览**（谁管哪几格）：

| 出口 × 闸门 | 归 | 为什么这么分 |
|---|---|---|
| E5 配额降级注记 / E5 写缓存闸 / E6 写缓存闸 | **票 H** | 都是合同分支那一个 `if` 块里的事，一次改完 |
| E1 版本绊线 / E2 版本绊线 | **票 I** | 同属"缓存复用型答复不受保护"，且真正的存量面是 E2 的持久语料 |
| E7 多选完整性 / E7 写缓存闸 | **票 J** | 同一句话：**把轻量出口的闸门对齐到流式出口** |
| E8 版本绊线 / E9 版本绊线 | 票 C（`docs/handoff-s6-stream-exit-version-gate-20260920.md`） | ✅ **已收口 `1c05599`**，不在本文件射程内 |

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

## 0.5 执行手册（给执行会话：照着跑，再动手）

§0 是"判据口径"，这一节是"怎么在这台机器上不被环境咬"。每条都是本轮或上轮**实测踩过**的，
不是预防性啰嗦。

### 0.5.1 开工 6 条自查（读数落盘成 `dispatch-output/hij-<票>/00-pre-flight.json`，缺一不许动源码）

| # | 查什么 | 命令 | 期望 |
|---|---|---|---|
| 1 | 基线 | `git rev-parse HEAD` | 以 `1c05599` 开头（或它的后代，见 §0.5.3） |
| 2 | 车道干净 | `git status --porcelain backend/main.py backend/gate_exit_registry.py docs/gate-exit-registry.md` | **空**。有 ` M` = 别人在途，立刻停手回报，别在它下游改码 |
| 3 | 解释器 | `backend/venv/Scripts/python.exe -c "import chromadb, main; print('ok')"` | `ok`。**只有 venv 这一个解释器可用**（见 0.5.2-a） |
| 4 | 开关生效值 | `backend/venv/Scripts/python.exe dispatch-output/s6-stream-gate-20260920/preflight_p9.py` | `fast_path_law_version_check_effective: false`。它读 settings 的**已加载值**，不 grep `.env` —— 这也是"不碰 .env 却要真实配置读数"的标准做法 |
| 5 | 冻结件 | `sha256sum backend/scripts/gate2_runner.py` | `ae2e4120…47e295` |
| 6 | 只读资产 | `git status --porcelain evals/ backend/agent/` | **空**（两棵树都不许出现你的改动） |

### 0.5.2 环境陷阱（左列是症状，右列是处置）

- **a) 用错解释器**：miniconda 的 python 缺 `chromadb` ⇒ `ModuleNotFoundError`，长得像"哨兵红了/源码坏了"。
  ⇒ 一律 `backend/venv/Scripts/python.exe`。
- **b) `tests/conftest.py` 无条件把 `DATABASE_URL`/`QUOTA_DB`/`CHROMA_DIR` 指到 `%TEMP%` 进程私有路径**：
  好处是定向测试永不碰真实库；代价是**任何要"真实配置/真实语料"读数的探针必须在 live 树跑且严格只读**，
  而**任何写语料的演练只能在副本 `CHROMA_DIR` 或新 collection**（票 I 注意：`qa_pairs` 是真实资产，
  `qa_pairs_te4` 是另一会话的 cosine 新库，**别往这两个里写**，自己的实验自己起名字）。
- **c) `--basetemp` 不得设在 `backend/` 内**：`tests/test_log_field_whitelist.py` 递归扫 `backend/` 全树找
  未登记日志字段，它自己的"故意未登记"样本就在 `tmp_path` 里，而 pytest 对失败用例保留 temp
  ⇒ 连红三轮的自反馈。用 `%TEMP%\fazhi_<票>-<用途>`。
- **d) 副本树缺两样东西**：缺 `dispatch-output/task1/` ⇒ `test_harness_fact_reveal.py` 在**收集期**抛错
  → 变异执行器判 RUN_VOID（`make_copytree.py` 已经处理这条）；缺 `backend/.env` ⇒
  **`tests/test_gate2_runner.py` 整文件 14 条红**（2026-09-20 实测：无 .env 时副本树
  `16 failed, 1352 passed, 10 skipped, 18 deselected` = 那 14 条 + §0.5.2(e) 那 2 条存量红）
  —— **那是环境不是回归**。
- **e) 基线读数长这样，别追影子**（派发前在**干净 `1c05599` 副本树**重量过一次，取证
  `dispatch-output/hij-dispatch-20260920/00-copytree-baseline.json` + 同名 `-junit.xml`）：
  `-m "not slow"` 下副本树 = **`tests=1378 failures=2 errors=0`**。那 2 条的逐字 ID 是
  `tests/test_eval_agent.py::test_report_with_adapter_contains_versioned_recomputable_case_evidence` 与
  `…::test_cli_evaluates_only_same_hash_frozen_artifact_and_records_source_provenance`，
  两条红在**同一句** `assert report["release_eligible"] is True`；**同一对 ID 在 live 树 2 passed**
  ⇒ 这是车道差异不是回归：别去修它，也别把它报成自己的成果或自己的锅。
  副本比 live 多的 **8 条 skip**（副本 10 skip vs live 2 skip）是 conftest 对"真实语料不可用"的
  **主动 skip**，同样不是红。`PYTEST_EXTRA = ["-m", "not slow"]` 必须设（18 条 `slow` 需要已填充的 KB）。
  分母对账：live 门禁轮 `1376 passed + 2 skipped = 1378`；副本轮 `1366 passed + 10 skipped + 2 failed = 1378`
  ⇒ 两条车道同一个分母，不是两处不同口径。
- **e-补) 副本树要自己造一个假 `backend/.env`**（`git archive` 里没有它，而 `import main` 在**模块期**就硬校验
  `JWT_SECRET`/`LLM_API_KEY`/`LLM_BASE_URL`，缺则 RuntimeError；14 条 gate2 测试也读它）。三行够用：
  `JWT_SECRET=<假值>`、`LLM_API_KEY=<假值>`、`LLM_BASE_URL=http://127.0.0.1:9/v1`
  —— 端口 9 是 discard，**万一探针顺路真去调模型会当场失败，而不是静默烧额度**。
  ⚠️ 只往副本里写；live 的 `backend/.env` 不读、不改、不 copy。
- **f) 行号会漂，而且 `ruff format` 就是漂移源**：本仓已漂过五次，最近一次是被 pre-commit 的 ruff-format
  钩子挤掉的（跑钩子**之前**量的行号跑完全部作废）。⇒ 断言与取证串只写"符号 + 该形状全文唯一"；
  `dispatch-output/s5-followup-20260920/verify_doc_claims.py` 对 `` `:NNNN` `` / `.py:NN` 是**机检 FAIL**，不是建议。
- **g) `core.autocrlf=true`**：blob 是 LF、工作树是 CRLF ⇒ 跨侧直接 sha 会"62 个文件全错"。同侧才可比。
- **h) `.gitignore:45` 有 `*.log`**：门禁产物默认名 `gate-<标签>.log` 进不了库 ⇒ 另存 `*-evidence.txt` 交付，
  **别用 `git add -f` 跟仓库级规则较劲**。
- **i) 失败日志会泄密**：`monkeypatch.setattr` 打桩不存在字段时，pytest 把整个 `Settings(...)` dump 进日志，
  里面有真实 API key。⇒ 这类留痕**只写错误类别与行号**，绝不 `git add`，也别为它改日志文件（沙箱会拦）。
- **j) 批量改写工具一律喂文件列表，不喂目录**：上一轮 `ruff format <三个目录>` 实付改了 **245 个文件**，
  绝大多数是别人的未跟踪脚本（没有基线，改了再也比不回来）。格式化完立刻 `git status --porcelain` 数 ` M`。

### 0.5.3 车道与串行：**不许并行派三票**

不是偏好，是指纹层面的冲突：三票都吃 `backend/main.py`；回表都吃真源
`backend/gate_exit_registry.py` **和同一个生成物 `docs/gate-exit-registry.md`**；
而任何门禁轮期间有 `.py` 被改动 = 整轮 RUN_VOID。⇒ 并行不会更快，只会互相作废。

顺序 **H → J → I**，每票 = 一个独立执行会话 = 一次独立提交：
- **H** 最先：含一条近乎免费的写缓存闸修（H-1），先把"错答/丢告警进缓存"这个形状关掉。
- **J** 其次：改动收在 `_light_buffered_locked` 一带，且**线上效果为零**（E7 零流量，见票面 J-3）——
  它的价值是票 C 之后两条出口对称，所以排在花钱之前。
- **I** 最后：它可能触发两次 Owner 决策（I-2(a) 的离线标注要花钱；对真实语料的任何写入），
  把不确定性放最后，前两票已入库不受它牵连。

每票开工前 `git log -1` 确认上一票已合入 ⇒ 你的基线就是那个新 HEAD（**不要**从 `1c05599` 起三份并列）。

### 0.5.4 轮次预算与断点自救（这条是拿真事故换的）

票 C 的 builder 在**变异轮跑到第 4 个（共 7 个）时撞上子代理 150 轮上限**，改动全在未提交的工作树里，
差点整轮丢。预算实测形状：**H ≈ 50–70 轮 · J ≈ 60–80 轮 · I ≈ 90–120 轮（含停下来回报）**
⇒ ① 一票一会话，别指望一个会话做完三票；② 每满足一条判据**立刻落盘 stdout**（证据文件比代码便宜，
是你的续命符）；③ 剩余轮次 ≤ 20 时执行快照协议：
```
mkdir -p dispatch-output/hij-<票>/wip-files
git diff > dispatch-output/hij-<票>/WIP-<UTC时间戳>.patch
cp <本次新增的未跟踪测试/脚本> dispatch-output/hij-<票>/wip-files/
wc -c dispatch-output/hij-<票>/WIP-*.patch
```
把 patch **字节数**写进回报——回报里"我做完了"不算数，"证据在 X、字节数 Y"才算。
④ 快照只止血：`git apply` 之后**必须**重跑被那次快照支撑的判据，别拿打过 patch 的树直接报绿。

### 0.5.5 live 窗口：RUN_VALID 没有副本替代

§0 禁在 live 工作树跑全量。但 `run_gate_full.py` 的隔离指纹读的是**真实**
`backend/app.db` / `data/quota_used.sqlite` / `chroma_db` 整目录 ⇒ **在副本树里那三条"前后未变"退化成恒真**，
所以"副本内全量绿"≠ RUN_VALID。⇒ 需要 RUN_VALID 时：**停下**，向 Owner 要一次 live 放行（一个字），
窗口内**不编辑任何 `.py`**（包括"用完就删"的临时探针），跑完当场撤窗口。
代价低但**不覆盖 chroma 面**的部分替代：只读 `open(path,'rb').read(100)` 取 app.db 的
change_counter（字节 24–27）+ size + mtime，与另一会话独立取过的同组数对账
（现值：app.db cc `10784`、quota cc `2`、`qa_pairs` 集合 `279` 条）。
Windows 细节：导出给 SQLite 的路径必须写 `C:/Users/…`，MSYS 风格 `/c/Users/…` 直接 `unable to open database file`。

### 0.5.6 不得重做的既有取证（重做 = 白烧轮次）

- **I-1 全套**（语料清点 / 直返率三条读数 / 宪法对账）：`dispatch-output/i1-e2-hitrate-20260920/probe_{a..e}.py`
  + 同名 `.json`。读数已进票面 I-1/I-5/I-6 与登记表 E2 格 ⇒ **只在需要更细分布时补采样**，别整套重跑。
- **票 C 的端点级逐帧 + 7/7 变异**：`dispatch-output/s6-stream-gate-20260920/`（含 `mut-out-r3/`）。
- **`answer_cache` 的存储形状**（进程内 `rc.LRU(512)` + TTL 6h、`clear()` 是唯一删除口）：已量，别再调研。
- **付费三臂**（`dispatch-output/agent-baseline-v2-*`）：**不许重跑**。
- **`evals/watershed-cases-r15.json` 是 NOT_FROZEN**：可取形状，**不可当判据**。
- 可复用件：`backend/tests/_sse_harness.py`（注意 `fallback_text` 参数——老写法 `flag_llm = object()`
  会让 `_invoke_llm` 恒抛，E9 在测试里根本走不到）；`dispatch-output/s5-followup-20260920/run_mutations_full.py`
  （已支持 `PYTEST_EXTRA`）；`dispatch-output/s6-stream-gate-20260920/run_mutations_ticket_c.py`
  （7 个变异的表 + `prevalidate` 形状可以直接抄）。

### 0.5.7 提交与回表纪律

- 显式路径、一票一提交：`git add <file>…` → `git diff --cached --name-only` 逐行核对 →
  `git commit -- <同一批显式路径>`（**部分提交形式**，绕开索引里别人 stage 的东西）→ `git show --stat HEAD` 复核。
- 索引里出现别人的文件或不属于本票的 `??`：点名报出来，别静默提交、别"顺手修"。
- 禁止：`git add .`/`git add <目录>`、`--amend`、`push`、`pre-commit install`、`git gc|prune|repack`、
  删 `tmp_obj_*`、改 `.gitignore`。（后三条和 temp 清理是 Owner 的动作。）
- 钩子**没接进 git**：`backend/venv/Scripts/pre-commit.exe run --files <本次改动的文件>`，对**暂存集整体**跑，
  核对 rc=0；`fix end of files` 会就地改写文件，Failed 后要复跑确认。
- 回表固定顺序：改真源 dict → `backend/venv/Scripts/python.exe backend/scripts/gen_gate_exit_registry.py`
  → `pytest backend/tests/test_gate_exit_registry.py`。**不回表哨兵必红**
  （`test_committed_md_is_the_generated_artifact`），这不是 flaky，不许跳。

### 0.5.8 一条待还的措辞债（顺手做，别另开票）

取证里**不要写会随别票变化的计数**（"9 格里"这种）。真源 E2 格我已在派发前改成不计数说法，
并在原处留了作废说明 ⇒ 你新写的格子沿用同一规矩：要表达范围就逐条列名字，别写数字。

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

**I-1 已由主会话量完（2026-09-20，`dispatch-output/i1-e2-hitrate-20260920/`，五台仪器 A/B/C/D/E）
—— 下面是读数，不是待办；执行会话别重做，只在需要更细分布时补采样**：
- 语料**只有 279 条**（`origin` 全为 `qa`），引用的 source 去重 51 个。
- **自问门（仪器有效性）：279/279 全部 ≥0.92、min=1.0** ⇒ 存向量与当前 embedder 同空间，
  `_qa_is_cosine()=False` 那条"重新嵌入再算 cos"的分支下读数可信。
- **覆盖探针**：60 条抽样，**换问法**（"下列说法正确的是？"→"下列哪一选项是正确的？"）**59/60 仍直返**
  （mean 0.9804）；**剥掉选项只剩题干**只有 **22/60**（mean 0.8854）。
  ⇒ 结论：E2 不是"只有逐字重复才命中"，**改写一句就够**；但只要题面形状变了（少掉选项）门就自然关。
- **误命中探针**：24 条用户自述式咨询 + 12 条语料未覆盖部门法题，**直返 0 条**，
  最高分 0.8287 / 0.8350 ⇒ 0.92 不误伤无关问题。
- ⚠️ **这不是线上命中率**：本地没有流量分布。上面三个数各自口径不同，谁引用就带着口径引用，
  不许合并成一句"x%"。**但对票 I 的分岔已经够用**：暴露面真实存在（改写即命中）且不误伤 ⇒
  **(a) 给语料打版本标** 这条路的支持证据比票面当初假设的强。
- 另一条改变严重度排序的事实：语料 metadata 里**没有时间戳**（键只有 `answer/evidence/origin/options_fingerprint`），
  生成日期只能靠 `_qa_direct_return` 的 docstring 那句「8-23 智谱免费 token 预生成语料」——
  按项目时间轴推是 2026-08-23，**这个年份是推断不是读数**。若它成立，里面的答案今天**并不陈旧**，
  E2 的风险就是**前瞻性的**（将来修法时没有任何机制让它失效），而不是"今天就在答旧法"
  ⇒ 别把本格报成"正在发生"，要报成"没有到期日"；要坐实日期就先给语料补一个生成时间戳。

**I-5（顺手抓到，与版本判定无关）选项指纹护栏覆盖面只有 60/279**：题面里带选项的有 **166** 条，
而存了 `options_fingerprint` 的只有 **60** 条；护栏条件是 `q_fp and stored_fp and 不等` ⇒
**219 条（含至少 106 条带选项的题）这道门是空转的**，"同题干换选项"那类误命中只对这些记录不设防。
要么补采指纹，要么在表里把这道护栏登记成 `PARTIAL` 并写清覆盖比例 —— **别继续按"三道护栏"叙述**。

**I-6（一行修，但注意别把版本焊死）证据时效护栏误杀 2 条**：全量对账差集只有一个名字 ——
QA 语料写 `宪法`，而主库把它存成 **`宪法（1982年）`**（138 个 chunk；主库 99 个 source 里**唯一**带年份后缀的就是它）。
`domain_rules.canon_source("宪法")` 原样返回 `宪法`、映射表里没有任何含"宪法"的条目 ⇒ `exact_article_lookup`
取回空 ⇒ 这 2 条**其实有据可查却被判 miss**（用全名重查：第二条、第三十五条各取回 1 条、status=现行）。
修法二选一，**先报你选哪个再动手**：① 给 `canon_source` 加一条"宪法→宪法（1982年）"的别名（把版本写死在别名里，
与本仓 R15 的版本语义相冲）；② 让 `exact_article_lookup` 在 source 精确取空后按"去年份前缀"回退匹配一次
（不加版本承诺，只加一次候选解析）。本仓**推荐 ②**。


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

## 9. 验收：主会话会自己重测什么（执行会话不必等我，先照这份自查）

**我按读数验收，不按解释验收。** 下面 7 件我自己重跑，不看你的结论：

1. **回表**：真源里 `"GAP-TODO"` 字面量的 `grep -c` 结果应 = **8 − 本次修掉的格数**
   （8 = 7 个格子 + `STATUSES` 里那 1 处词表字面量），且生成物与真源一致
   （`test_committed_md_is_the_generated_artifact` 我自己跑）。
2. **判据是不是真判据**：从你新增断言里抽 2 条，**我另造变异**（不用你那张变异表）把实现改坏，看它红不红。
   红不出来的 = 空枪，该票按未完成计。
3. **变异**：我用 `git archive <你的提交>` 重搭副本树（**不用你的工作树**），`PYTEST_EXTRA=["-m","not slow"]`，
   跑你声明的那组变异。分母必须与我的基线相等（`tests=1378 errors=0`，2 条 failures 是 §0.5.2(e) 已归因那两条）。
4. **可达性**：你声称"某分支已受保护"处，我在真实配置下打桩计数复跑（>0 才算），桩我删。
5. **零变化 / 零写入**：默认关下逐帧 sha 前==后（同一棵树、同一条命令）；app.db cc / quota cc /
   chroma 集合清单前==后。
6. **静态门**：`ruff check` / `ruff format --check` / **全仓** `mypy .`（改调用点时单文件 mypy 绿不算绿）/
   pre-commit 对暂存集整体，各给 rc。
7. **双轴 fresh-eyes review**（Standards × Spec）：Owner 已裁"与票 H/I/J 一起做" ⇒ 三票齐了才跑，
   它独立出题、不看你的自述；它的读数与你的回报冲突时以证据文件为准。

**两条例外形状直接判不通过**（先停下来回报，别做成既成事实）：
① 改了任何开关默认值，或读写/挪动过 `.env`；
② 票 I 的 I-2(a) 离线标注（要花钱）、或对真实 `qa_pairs` 语料的任何写入 —— 这两件**必须 Owner 点头**。
（同族：I-6 要求先报"选 ① 加别名 还是 ② 去年份前缀回退"再动手，本仓推荐 ②。）

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
本次消耗轮次≈<n>   快照=<无 / 有：路径 + patch 字节数>
需要 Owner 决策或放行=<live 窗口 | I-2(a) 花费 | 真实语料写入 | I-6 选型 | 无>
证据文件清单=<逐条：路径 + wc -c 字节数>
```
