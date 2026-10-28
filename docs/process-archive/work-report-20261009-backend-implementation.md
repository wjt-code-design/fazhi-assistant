# 工作汇报：后端四票实施 + 两路独立复核（2026-10-09 ~ 10-10）

> 汇报人：本轮后端主审（同一会话里先做只读审查、后按 Owner 授权实施）。
> 一句话：把只读审查报告里 Owner 批准的四票（DB-15 / DB-16 的①③ / DB-17 / DB-18）在册落地，补了两路正交复核（只读复算 + 挑战论点），并把所有读数复量进同一份审查报告的 §13。**代码未提交**。

## 0. 汇总（30 秒版）

| 项 | 现量 |
|---|---|
| 做了什么 | 四票实施（步数计费豁免、category 静默清零回落、4xx 记账通道拆分、法名归一收真源）＋两路独立复核＋全量门禁复跑 |
| 代码面 | 15 只已跟踪文件（`git diff --numstat` 现量）＋ 4 只新增测试文件（未跟踪），共 49 条新用例 |
| 全量测试 | **1909 passed / 0 failed / 2 skipped / 18 deselected**（改前基线 1860，Δ+49 两轴闭合） |
| 静态门禁 | `ruff check .` 绿；`ruff format --check .` 只剩 `backend/schemas.py`（我没改过它，Windows 换行形状）；`mypy .` 两条红**改前即红**、由别的会话的 `902e2d1` 引入 |
| 真实数据 | `backend/chroma_db`、`backend/app.db`、`backend/data/app.db` 收尾复量零改动（两根轴） |
| 边界 | **未 commit、未 push、未移 ref、未轮换凭据、未真实入库、未签任何字**；HEAD 两端都是 `0b543960c7172ce1ffea57616952e4d5525190c4` |
| 等你 | DB-19…DB-23（5 条，各带推荐）＋"要不要现在提交"＋第一轮台账里 B 组 12 条的派单意见 |

## 1. 四票做了什么（每票"缺陷 → 动作 → 改前/改后读数"）

**DB-15（finding B-01 + B-47）**：停在 `WAITING_USER` 且 `steps` 恰好打满 `max_steps` 的 run **永远恢复不了**（resume 边要 +1 步 ⇒ 409 死锁，文案还是"任务已变化"）；终稿边同理——已验证通过的答案恰在预算终点被静默丢弃。历史上的"修法"是抬 `AGENT_MAX_STEPS` 8→16→20（三步全写在 `settings.py:89-93` 的注释里，是在册物证）。
动作：`agent/state_machine.py` 新增 `FREE_STEP_EDGES`（`DRAFTING→COMPLETED`、`WAITING_USER→PLANNING` 两条边不计步），计费式改为 `charge` 查表；`agent/service.py` 在 `except Exception` **之前**加 `except BudgetExceeded`，把终稿预算炸映射到白名单里的 `AGENT_BUDGET_EXCEEDED`（改前折成不在白名单的 `AGENT_STORAGE_FAILURE` ⇒ 用户拿硬错误）。
读数（同一支探针、两棵树各跑一次）：L2「恰好在 cap 抛 BudgetExceeded」与 L3「答案被丢、run 卡 drafting」**由绿翻红**（红＝缺陷消失）；L1/L4 两条对照腿保持绿（尺子没被放宽）。入库用例 `tests/test_agent_budget_terminal_edges.py`（10 collected）。

**DB-16（finding B-05，只做①③）**：`vector_top` 带 `category` 过滤时，因现网 10,266 条 metadata 根本没有 `category` 键、Chroma 0.4.24 对缺失键的 `$eq`/`$ne` 一律排除该行 ⇒ 向量池与 BM25 池被同时清零，且**零日志**；而 planner 提示词还明写"category 可选"（是被邀请传的）。
动作：①`agent/runtime.py` 删掉那半句邀请；③`retrieval.py` 三处（`vector_top`/`bm25_top`/`grounded_top_score`）在"带过滤却零命中"时回落一次无过滤并落 `retrieval_category_filter_miss` warning（同值每进程一次）。复核轮又补：`invalidate()` 现在清"已告警"集合（否则第一轮之后同类异常永不再出声）。
读数：改后 6 条用例（`tests/test_retrieval_category_fallback.py`），含"先带过滤、再回落一次"的调用序列断言与控制腿（无 category 时**只查一次**）。
**第②处（把 `category` 从 schema 摘掉）我没做**，理由与替代方案见 §6 的 DB-19。

**DB-17（finding B-48）**：`mark_depleted(key, "model_failure")` 的实现是 `runtime_used += quota_left` ⇒ 一次 400/401/403/404 在管理台/配额库读成"这个模型积分用完了"，`reason` 参数被丢弃。
动作：`llm_errors.py` 新增 `is_request_shape_rejection`（**不动** `is_transient_error` 与 `TRANSIENT_STATUS`）；`llm_registry.py` 新增 `mark_rejected` + 300 秒冷却（**配额账一字不动**），`mark_depleted` 开始落结构化日志并保留 `reason`；三个调用点（`main.py` 两处、`agent/runtime.py` 一处）按病因分通道；`observability` 加 5 条字段。
读数：状态码网格 8 格，`transient` 那一列改前改后**逐格相同**（分类口径没动是可核的）；记账面同一只 `quota_total=100` 的模型，`mark_depleted` ⇒ 100→0，`mark_rejected` ⇒ 100→100 且 `pick` 不再自动选它。入库用例 `tests/test_llm_reject_channel.py`（24 collected）。
**复核轮补的洞**：`_safe_pick` 在 `QuotaExhausted` 时直接 `registry.get()` 回落，**绕过冷却过滤**且 `is_unavailable` 不含冷却 ⇒ 整池冷却时每个请求仍会再打一次刚被打回的模型还不标降级。已加 `llm_registry.is_rejected()` 并把降级判定改成"配额不可用 **或** 冷却中"。

**DB-18（finding B-49）**：法名归一只剥**全角**括注，而外部权威源（元典）返回的法规名是 `中华人民共和国劳动合同法(2012修正)` 这种**半角**形状 ⇒ 10 个引用校验消费点把"其实有据可查"判成"库里没有"（假阴性）。
动作：`domain_rules.norm_law_name` 收成**读侧唯一真源**（去前缀 + 剥尾部括注，全/半角都剥，只剥一个且只在尾部），`retrieval._source_key`、`_parse_article_query` 内联、`agent/writer._canonical_law_name`、`scripts/smoke_citation_full.norm_law_name` **四份合一**。
读数：报告 §12.5 那六格输入原样复跑，**4 绿 2 红 → 6 绿 0 红**（红的两格正是元典形状）。入库用例 `tests/test_law_name_normalization.py`（7 collected），含"旧全角正则必须过不了半角样本"的负向自证。
**射程要说清楚**：只并了生产读侧四份；写侧 `scripts/import_docs.py` 等 4 处未并 ⇒ 转 DB-21。

## 2. 复核轮（两路正交，都在只读约束下）

按在册做法补派两路独立 agent，交回后我**逐条回源码自证**才落笔：

* **A 路（只读复算）**：任务只有"复算行号、数字、原句、日志读数"，禁止执行项目代码。交回 6 处对不上 + 6 处核不了。**9 处我来复核跑后改正**（其中 7 处是量法/抄写问题：CRLF 数 919→923、"6 只红"其实是两条不同 `AttributeError`、`chroma_db` 最新文件我写"一只"实为 4 只、`test_llm_failover.py:167-170` 这个指针我在工作树轴上沿用了旧号、"第五份"序号自相矛盾、`agent/runtime.py:390-416` 应窄到 396-416、"改前改后同两只 skip"降级为推断）。
* **B 路（挑战论点）**：交回 11 条。**9 条接受**（其中 1 条要求当场补码，即上面的 `_safe_pick` 洞；2 条把我写过的话钉回去："唯一真源"只覆盖读侧、"唯一一处偏离"其实是两处）、**半条驳回**（它说 `mark_rejected` 每次落一条 WARNING 是洪水、应与检索侧"每进程一次"对齐——我不同意：模型被拒是**事件**要能数频率，且已被 300 秒冷却限流；检索零命中是**状态**，反复问只会淹日志）。

两路结论逐条落在审查报告的 **§13.9**（A 路九处改正表）与 **§13.10**（B 路接受/驳回/补码）。它们抓出的东西里，有两条是我这轮之前**已经写死进正文**的过度声明，见 §4。

## 3. 读数与方法（都能自己复算）

* **同尺两棵树**：改前树 = `%TEMP%/fazhi-audit2-20261009/backend`（源码仍是 `0b54396` 形状）；改后树 = 同目录 `patched/backend`（把 12 只改动源文件 `cp` 进去并清 `__pycache__`）。同一支探针脚本、同一个解释器、两棵树各跑一次，只差"源码是否打了补丁"这一根轴——DB-15 那两红就是这么翻的。
* **基线/终量**：改前 `1860 passed / 2 skipped / 18 deselected / 0 failed, 322.68s`；终趟 `1909 passed / 2 skipped / 18 deselected / 0 failed, 326.20s`。Δ+49 = 新四只文件 45（collected 轴）+ failover 控制腿 1 + 复核轮补的 3。命令：`cd backend && venv/Scripts/python.exe -m pytest -q -m "not slow" -p no:cacheprovider --no-header -rs`。两条 skip 是**设计内采集口**（未设 `FZ_DUMP_FRAMES` / `S6_DUMP_FRAMES`）。
* **mypy 那两条红的归因**（重点，别读成我引入的）：`main.py` 的 `Row[X, Y]` 两处，证据①把 HEAD 的那份 `main.py` 取出来单独跑 mypy，同样两错（不含本轮任何改动）；证据②一个六行、零项目代码的探针（只有 `from sqlalchemy.engine import Row` + `Row[Fake, str]` 注解）复现同一条 `type-arg`。`requirements-dev.txt` 是 `mypy>=1.10` **无上界** ⇒ 这条腿交 CI 定，但任何"CI 全绿"的说法要先看它。
* **真实数据零改动**：`find backend/chroma_db -type f -newermt "-10 hours"` = 0 文件，且目录内最新 mtime 是 `2026-09-22 13:34`；`backend/app.db` mtime `2026-09-19 00:28`、`backend/data/app.db` `2026-09-23 14:51`。测试全程靠 `tests/conftest.py` 把 `DATABASE_URL`/`QUOTA_DB`/`CHROMA_DIR` 重定向到 `%TEMP%`。
* **工作树归属**：`git diff --numstat` 现量 15 只 backend 文件属本轮；同树另有 6 只**不属于本轮**的未提交改动（`frontend/` 5 只 + `docs/process-archive/superpowers/plans/` 1 只，并行会话的），我在报告 §13.1 点了名。

## 4. 我自己犯的错与更正（不藏，全部已就地改正）

1. **量法错**：把 `test_agent_resume.py` 的 CRLF 数写成 919（真值 923）。
2. **head 截断当全集**：`chroma_db` 最新文件我写"一只"（真值同刻 4 只）——正是报告 §9 登记过的那台机器，复核轮 A 路当场抓到。
3. **行号漂移**：`test_llm_failover.py:167-170` 是 HEAD 轴的号，我加了测试腿后工作树已漂到 `:174-177`，报告与**源码注释**都改成了按用例名引。这台机器我在 §11 批评过别人，这轮落在我自己头上。
4. **过度声明一**：把 DB-18 说成"唯一真源"，实际只覆盖生产读侧四份（写侧与 eval 脚本另有 4 处）。
5. **过度声明二**：§13.6 写"本轮唯一一处偏离推荐"，其实 B-47 的"做"列还要求"把 409 文案按成因拆三条"，我只做到判据层（`reason_code` + 结构化日志）⇒ 已改"两处之一"，文案待你授权（DB-23）。
6. **两条写作事故**：①给报告插段落时 Windows 路径里的 `\f` 被折成控制符（formfeed）——用正则定位后改成正斜杠；②用 Edit 插入段落时把下一小节的**粗体小标题**当锚点吃掉、该小节标题静默消失——靠"改完数标记 + 全量结构复查（H2/H3/表块/围栏/CR）"抓回。两条都记进了项目记忆。
7. **一条探针自身写错**：`%TEMP%` 那只 `test_audit2_source_key_shapes.py` 的 `_norm_source` 腿**两棵树都红**——是那只腿的期望抄错了（报告 B-49 行记的是对的事实），不是新代码回归。
8. **第一趟全量 6 红不是产品缺陷**：全是 hand-copied 替身追不上真类（`SimpleNamespace` 漏了 `rejected_now`/`rejected_until` 两个面），已把两只手抄桩改成构造真 `ModelEntry`。

## 5. 边界与未做（明确列出，不拿"未做"当"已完备"）

* **未做=未做**：未 commit、未 push、未建 PR、未移任何 ref、未轮换任何凭据、未真实入库、未签任何字。
* **本轮未跑的门禁腿**：`pip-audit`（在册已知 rc=1，且 CI 只扫 `requirements.txt`，dev 轴永不出现在 CI 读数）、前端 `npm run build`（那 5 只前端改动不是我的）、`dispatch-output` 守卫腿、覆盖率 `--cov` 形状、远端 CI（未 push ⇒ 无远端证据）。**本机所有"绿"都是 Windows 工作树 + `%TEMP%` 副本树读数。**
* **四票各自的残余**：DB-16 的第②处未做（转 DB-19）；DB-18 只并读侧四份（转 DB-21）；DB-17 的 TTL 对 401/403/404 这类配置性拒绝偏短（转 DB-22）；B-47 要求的"409 文案拆分"只做了判据层（转 DB-23）；`rejected_remaining_s` 目前**前端零消费**（只有 API 层看得见）。

## 6. 需要你决策的（每条一词可答，都带我的推荐）

**最要紧的一条**

| 问题 | 我的推荐 |
|---|---|
| 要不要现在提交这批改动？ | **先不提交**：DB-19/20/21/23 都会继续碰同类文件，现在提交等于把半成品落主线；且同树有并行会话的 6 只未提交改动。你要提交，我按 §13.1 那张表**精确提交后端 15 只 tracked + 4 只新测试文件**，不碰前端那 6 只。 |

**A 组：我这条链上，答完就能动手（5 条）**

| 编号 | 一句话 | 推荐 |
|---|---|---|
| DB-19 | `category` 的 schema 要不要摘？ | **先不摘**（等写侧给 10,266 条补上 `category` 再定；且"补齐那天③回落必须删"） |
| DB-20 | `agent/dept_guard.py` 那份弱一档归一并进真源吗？ | **随 DB-3 一起做**，同批补"判域不变"对照腿 |
| DB-21 | 归一未并的 4 处（含写侧 `import_docs.py`）收干净？括注收窄成"年份/修正字样"形状？ | **并，同批改导入测试 + dry-run 比对**；括注**收窄** |
| DB-22 | 401/403/404 这类配置性拒绝与 400 共用 300s TTL？ | **分两档**：401/403/404 → 3600s 且快照单列；400/422 → 300s |
| DB-23 | 409 三条文案拆不拆？ | **拆**，用我给的三条映射；只缺你一句措辞授权 |

**B 组：第一轮台账里仍未做（我核过现量），需要你派单**

* **一行级、推荐顺手做**：DB-13（主库 `journal_mode=WAL` 未设，只有 `quota_store.py` 有；开 WAL 后备份口径要重验）、B-45（`scripts/import_laws.py` 仍未接 `chroma_dir_guard.assert_matches`，现存脚本里只有备份/换班脚本接了）。
* **一段文档级**：DB-10（`token_epoch` 仍不存在 ⇒ 先把"轮换 JWT_SECRET 是唯一全局吊销手段"写进 DEPLOYMENT 事件响应）、DB-12（根目录 `DEPLOYMENT.md:12/14/30` 仍在教 `0.0.0.0:8080` 明文公网剧本 ⇒ 先做文档刀）。
* **要先裁口径**：DB-2（`feature_similar_cache` 默认 **True** ⇒ 你要的是"部署期先关"，属运维值）、DB-7（`TOOL_BUSY` 不在技术降级白名单里 ⇒ 要动需推翻"不扩大白名单"在册口径）、DB-6（沉淀闸 `sv.ok` 硬前置，代码里没有）、DB-11（`qa_candidates` "不可按用户删除"没写进任何已知限制文档）。
* **建议另开票派单**：DB-3（引用真源收口，与 DB-20/21 同根）、DB-8（embedding 换班脚本 + 启动绊线）、DB-9 剩的半条（`.pre-commit-config.yaml` 里仍无 secrets 扫描钩子）。

## 7. 交付物与复算入口

| 件 | 路径 |
|---|---|
| 审查报告（含 §13 实施补记，§13.9/§13.10 是两路复核结论） | `C:/Users/33393/Desktop/ai-legal-helper/docs/backend-readonly-audit-20260929.md` |
| 本汇报 | `C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261009-backend-implementation.md` |
| 新增测试（未跟踪，4 只） | `backend/tests/` 下 `test_agent_budget_terminal_edges.py`（10）、`test_law_name_normalization.py`（7）、`test_retrieval_category_fallback.py`（7）、`test_llm_reject_channel.py`（24） |

复算命令（都在本机跑过，日志留在 `%TEMP%`）：

```bash
# 全量（终趟读数就是这条；基线同命令，日志 pytest_baseline_before.txt）
cd backend && venv/Scripts/python.exe -m pytest -q -m "not slow" -p no:cacheprovider --no-header -rs
# 改动清单与归属
git diff --numstat ; git ls-files --others --exclude-standard backend/tests
# 静态门禁（mypy 的两条红见 §3 的归因）
venv/Scripts/python.exe -m ruff check . ; venv/Scripts/python.exe -m ruff format --check . ; venv/Scripts/python.exe -m mypy .
```

**一句话给你的判断依据**：这轮把四个"看起来是设计选择、实际是缺陷"的点，从"报告里写着的推论"变成了"有改前/改后成对读数、且被两个独立复核者从相反方向戳过"的东西；剩下的 5 条待裁都在上面，最小的一条（DB-23）只缺你一句措辞。
