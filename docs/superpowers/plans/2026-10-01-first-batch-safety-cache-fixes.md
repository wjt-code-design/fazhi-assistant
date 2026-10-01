# 首批安全扫描与缓存修复执行记录

> 执行方式：用户已确认由当前助手执行 A/B/C 修订范围；按 executing-plans 逐项落实，不另外派发实现会话。复核和测试在独立代码副本进行。

> 最新状态（2026-10-02）：A/B/C 补正及最小移入已完成，Owner 另行批准本地提交，提交前复验通过。提交授权、文件清单与证据见末节；整个候选整合及发布条件仍未完成，不推送或部署。

**Goal:** 修复工作区扫描漏检、回答缓存隔离与知识变更后的旧结果回写。

**Architecture:** 复用已装 dotenv、Git NUL 分隔文件枚举及现有 LRU/锁。缓存失效代次在已有 LRU 锁内核验；请求在取证前捕获代次，所有答案写入点沿用该值。相似缓存使用同一意图、日期、检索证据命名空间。

**Tech Stack:** Python 3.11、stdlib、python-dotenv、现有 pytest/unittest、FastAPI。

## 约束与基线

- 用户于本会话确认“按修订范围执行，但后续由你执行”。不提交、不推送、不部署、不写真实库、不调用真实 LLM/云端嵌入/rerank；不安装依赖、不移动已有 Git 引用。既有非 slow 测试在隔离库中使用已缓存的本地 BGE，不将这类测试解释成真实 LLM 验收。
- 初始 HEAD：`d8625e5958cc40751d027a0dd612f179397a8345`。保留现有报告修改；三个冻结业务文件不动。
- 已开始的请求允许完成；知识变更后旧结果不得污染后续缓存。不承诺进行中请求拥有数据库事务快照。
- A 是工作区诊断，不等于全部暂存对象/提交历史扫描，更不自动批准外发。八个在册输入须完整；缺失时拒绝结论，不填假凭据。
- 新代码另跑验收；历史固定 Git 对象的测试/扫描证据仍仅对应历史对象。
- 验证解释器：`C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/venv/Scripts/python.exe`。
- 本轮隔离目录：`C:/Users/33393/AppData/Local/Temp/legal-first-batch-fix-20261001-67e68519228c4225947ba7d2b82f3937/`。

## A：工作区扫描器

文件：`dispatch-output/local-candidate-closeout-20260928/b_worktree_value_scan.py` 与同目录新增 `test_worktree_value_scan.py`。

- [x] 添加并运行假凭据临时 Git 库回归：中文/空格文件名、不同扫描根、八键不完整/空值、dotenv 引号注释、文件/目录读取失败、Git 失败。
- [x] 先记录失败，再修复：

```python
subprocess.run(["git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "-z"], capture_output=True)
```

  NUL 分割后按文件系统解码；凭据仍来自主工作区 `backend/.env`，扫描根明确控制枚举。缺输入、枚举/读取失败返回非零且不打印原始凭据/异常内容。B 的零命中仍判仪器无效。
- [x] 正向控制验证中文/空格路径确实被扫描；输出区分尝试读取与成功读取，不把 tracked 变更计入未跟踪面 A。追加命中文件名脱敏与根目录访问异常回归。
- [x] 运行 `python -B test_worktree_value_scan.py` 与既有 `test_release_gates.py`；不执行真实全盘凭据扫描。

## B：回答缓存隔离

文件：`backend/answer_cache.py`、`backend/main.py`、`backend/tests/test_cache_similar.py`，新增 `backend/tests/test_cache_scope_invalidation.py`。`test_tiering.py` 只复验未修改；`test_light_exit_gates.py` 仅同步私有 helper 桩的签名，不改变断言。

- [x] 添加跨来源/意图/午夜回归及“不同法名同条号”写闸回归，先记录失败。
- [x] 采用现有键的规范化集合，增加轻量命名空间；不提高阈值掩盖缺陷、不关闭相似缓存。

```python
CacheScope = tuple[str, str, tuple[str, ...]]
# make_scope(intent, cutoff, context_ids) -> CacheScope
# put(..., scope: CacheScope | None = None, generation: int | None = None)
# get_similar(..., scope: CacheScope | None = None) -> dict | None
```

  无命名空间的旧条目仅精确命中；不能参与相似复用。日期在本次缓存处理入口固定，写入时不重新取日期。检索标识含源名、条号及已有时效元数据，避免混用版本。
- [x] `_cache_write_ok` 使用已有 `canon_source`、`_source_key`、`_normalize_article` 比较法名与条号；不改变 legal_query 的既有自检政策。
- [x] 对照腿：同命名空间的改写仍命中，全称前缀和中阿条号变体不误拦；no_cache 与历史查询排除项保持。法名简称仍复用现有映射，未新增别名规则。

## C：失效完整性

文件：`backend/retrieval_core.py`、`backend/retrieval.py`、`backend/answer_cache.py`、`backend/main.py`、`backend/knowledge_service.py` 与上述新增测试。

- [x] 添加确定性交错回归：清空后旧检索完成、三种答案出口在取证/模型阶段失效、重传新增后删旧窗口。
- [x] 在现有 LRU 内实现代次：

```python
# generation() -> int
# clear() 在原锁内递增代次并清空
# put(key, value, *, generation: int | None = None)
# 在同一原锁内比较 generation 后写入；过期则不写
```

  检索前捕获代次；请求取证前捕获答案缓存代次；合同、轻量、旗舰三个写入点均传入原值。只在外面比较代次然后普通 put 不算完成。
- [x] 复用索引锁返回 BM25/文档一致快照、源名集合快照；不在远程调用期间加全局请求锁。
- [x] 新增/删旧变更结束后再失效；`add_chunks` 潜在部分写入的异常路径也清空缓存，但保留原异常及先写新再删旧的防丢数据顺序。不把此项扩大成全库事务。
- [x] 对照腿：更新后的新请求可取到新知识并正常缓存；不增加 Redis/分布式协调、知识库事务或持久 QA 重写。

## 集成验收与报告

- [x] 隔离副本运行定向回归及相关旧测试，保存 red/green 日志和退出码。
- [x] 实际运行完整后端非 slow 测试、覆盖率门槛 70、Ruff check/format、mypy、质量守卫。**运行完不等于全部通过，结果如下。** 慢测试、真实 LLM/rerank、Linux/远端 CI 不作通过声明。
- [x] 检查 `git diff --check`、已有引用、三份冻结物与真实数据保护对象；确认未增加依赖或无关业务改动。
- [x] 更新主进度报告的待修状态，引用本记录与新日志；不更改原持久交付证据，不宣布整个候选已经可发布。
- [x] 当前工作区代码的 Windows 隔离后端非 slow 全量与现有 mypy 配置检查全部通过：在 Owner 另行确认最小移入后取得，见末节。不代表未变的 HEAD 或整条候选分支已经通过整合验收。

## 执行结果（2026-10-01 当轮历史；最新结果见末节）

**本轮 A/B/C 修复与定向验收完成；主线整体门禁尚未全绿。** 日志根为上面的隔离目录；各 `<label>.json` 保存完整命令、工作目录、退出码，`.out/.err` 保存原始输出。每一场从固定 HEAD 导出新的代码副本，再仅覆盖本轮文件，不复用上场运行生成的库。

| 检查 | 结果 | 日志 label |
|---|---|---|
| A 修复前 | 9 项中 8 失败；补文件名泄值用例后单项红；根目录两个异常子场景红 | `scanner-red-root`、`scanner-path-red-fresh`、`scanner-root-red` |
| A 最终回归 | 12 tests OK，rc=0 | `scanner-reviewed-green` |
| B/C 修复前 | 22 failed、5 passed；功能缺失与真实 API/并发行为失败均有记录 | `backend-red-confirmed` |
| B/C 及相关旧回归 | 73 passed，包含 27 项新增回归；rc=0 | `backend-reviewed-green` |
| 新代码全量非 slow | 1666 passed、2 failed、10 skipped、18 deselected；coverage 85.08%；**rc=1** | `backend-full` |
| 原 HEAD 对照全量 | 1639 passed、同样 2 failed、10 skipped、18 deselected；rc=1 | `baseline-full` |
| 后端 lint / format | 均 rc=0；后端单独格式检查 267 文件，最终含扫描器/守卫再次通过 | `backend-lint`、`backend-format`、`final-lint`、`final-format` |
| 后端 mypy 与原 HEAD 对照 | 两边均有 main 的 3 项既有 `var-annotated`，检查 74 文件；**rc=1** | `backend-types`、`baseline-types` |
| 质量守卫 | 9 passed，rc=0；lint / format rc=0 | `backend-budget-guard`、`tooling-lint`、`tooling-format` |
| 发布仪器门禁 | 在脚本原位置运行，全部临时 Git/fake fixtures：27 tests OK，rc=0 | `release-live` |
| 保护对象 | 前后 41 对象大小/hash 一致；missing/changed 0；三冻结物和已有 Git 引用未变 | `protected-before.log`、`protected-after.log` |

全量失败均为 `test_request_bootstrap.py` 的两项 caplog 断言：应用设置 `propagate=False` 后，日志实际发出但 root caplog 捕获不到。原 HEAD 同样失败，候选 `fbc29e8…` 已包含直接接入 logger handler 的修复。三处类型注解也已在候选中存在。本轮保留这两根基线差异，不能用候选历史绿灯替当前主线通过。

发布门禁直接依赖历史目录的硬编码默认值，因此在 archive 副本运行时有一项路径断言失败（`backend-guards`，35 passed/1 failed）。未修改断言或改动冻结探针，改在原脚本位置使用其临时库 fixtures 重验通过；质量守卫另在隔离副本独立通过。

独立只读复核提出的根目录异常遗漏和 legacy-entry 测试空挡均已修正；最终 12/73 读数在修正之后取得。完整后端生产文件与全量测试副本逐字绑定；最终只补强了一条已有测试断言，另用定向场覆盖。原快照/签字/远端 CI/依赖审计结论不因本轮修复自动更新。

后续由当前助手处理：先向 Owner 对齐候选与这批工作区改动的整合路线；获准后整合并重跑全量/类型门禁。实际 commit、push、风险签字、凭据轮换、真实 rerank/真实库操作与部署仍分别受既有授权边界约束，不以本执行记录代替批准。

## 2026-10-02：复核后的最小补正

Owner 在复核后要求“继续执行”。本次仅处理复核指出的两项问题，不扩大到候选整合或主线既有失败的修复；由当前助手实现，另一审查者只读核对增量。

- [x] `add_chunks`：写入失败或中断后仍尝试失效；写入与普通失效异常同时发生时，向调用方重新抛出原写入异常，清理失败只记录异常类名，不记录原文/traceback。写入成功而失效失败时仍向上抛出，不返回成功。没有改变先写新再删旧的顺序。
- [x] 扫描器：读取失败输出 A/B 面和脱敏相对路径；枚举失败区分 Git 返回码、Git 启动错误类型、目录错误类型及可取得的脱敏路径。复用原有路径脱敏，不打印异常原文、stdout/stderr 或凭据值；完整性失败 rc=3、B 正控失败 rc=2 不变。
- [x] 先红后绿；验证原异常对象身份、中断清理、实际 JSON 日志脱敏、成功写入后的清理错误传播，以及两面读取与三类枚举失败。故障注入在 autouse 清理前恢复。
- [x] 定向、全量非 slow、lint/format、类型检查与两套仪器守卫重新运行；对真实数据、冻结文件与 Git 引用做保护校验。

日志仍位于前述仓外隔离目录。以下均为 **2026-10-02 本次新运行**；完整命令、cwd、rc 在对应 `<label>.json`，输出在 `.out/.err`。每场代码副本独立，不含真实 `.env` 或项目数据库。

| 检查 | 本次结果 | 日志 label |
|---|---|---|
| 扫描器补正前 | 14 tests，4 failures：安全诊断信息缺失；rc=1 | `scanner-followup-red-20261002` |
| 后端补正前 | 2 failed、2 passed、26 deselected：原异常被替换，两条对照通过；rc=1 | `backend-followup-red-20261002` |
| 扫描器补正后 | 14 tests OK；rc=0 | `scanner-followup-green-20261002` |
| 后端定向补正后 | 76 passed，1 条既有 Starlette 弃用警告；rc=0 | `backend-followup-green-20261002` |
| 全量非 slow | 1669 passed、2 failed、10 skipped、18 deselected；coverage 85.09%，达到 70 门槛；**rc=1** | `backend-followup-full-20261002` |
| 后端＋扫描器 lint / format | 均 rc=0，格式检查 269 文件 | `followup-lint-20261002`、`followup-format-20261002` |
| mypy | 74 文件，main 同样 3 项既有 `var-annotated`；**rc=1** | `followup-types-20261002` |
| 质量/发布仪器守卫 | 9 passed / 27 tests OK；均 rc=0。发布仪器仍在原脚本位置使用临时 Git/fake fixtures | `followup-budget-guard-20261002`、`release-followup-20261002` |
| 保护及代码绑定 | 41 对象前后大小/hash 不变；已有引用和三冻结业务文件同原基线；11 个覆盖文件与本次全量副本逐字一致 | `protected-followup-before-20261002.log`、`protected-followup-after-20261002.log`、`followup-provenance-20261002` |

全量失败仍是 §执行结果中同两项 `test_request_bootstrap.py` 日志捕获断言；三项类型错误也未增加。没有借此次修复合入候选 `fbc29e8…` 的既有修复。只读增量审查未发现新的具体问题，但该审查不代替测试或主线发布门禁。

**限制与下一步：** 双故障时只能证明原异常保留且清理失败可见，不能声称缓存已成功清空。测试未调用真实 LLM/云端嵌入/rerank；未进行真实全盘凭据扫描、pip-audit、前端、Linux/远端 CI 或部署验收。没有提交、合并、推送、安装依赖或写真实库。两项补正已闭环，主线整体收尾仍待候选整合路线确认及既有红灯消除；D2、凭据、真实验收与部署边界不变。

## 2026-10-02：主线既有红灯的最小移入（已完成）

Owner 经 grilling 确认：只移入候选 `fbc29e87c14e8e6a2c0744e98d86d426f6146ade` 的 `backend/main.py` 三处类型注解及必要 Row import，以及 `backend/tests/test_request_bootstrap.py` 两项日志测试的独立 handler 捕获方式。保留既有断言和 A/B/C 工作区改动；不整分支合并，不移入依赖升级、PDF 处理、上传测试或 T7 文档。提交、推送、真实库与部署仍不执行。

- [x] 在实际 `observability.setup_logging('INFO')` 的不向 root 传播设置下，记录旧日志测试的失败；记录当前 mypy 三项失败。
- [x] 通过局部补丁移入上述两个文件的指定改点，不覆盖完整文件，不改变应用日志配置或业务行为。
- [x] 两项日志测试在相同设置下通过，原有拒绝/放行、JSON 留痕、原问句不入日志断言保留；mypy 三项归零。
- [x] 运行隔离全量非 slow、A/B/C 及 bootstrap 定向、扫描器、lint/format、相关仪器守卫；做保护与代码绑定校验。
- [x] 更新本节及主报告，分别说明“工作区最小移入已验证”与“整个候选/发布尚未完成”。

本次 runner 为上述仓外目录的 `run_minimal_checks.py`：仅复用原隔离 runner 并补入 bootstrap 测试文件，旧 runner/旧日志不覆盖。全量、类型、日志反例及守卫使用各自隔离副本；最后 lint/format、扫描器及定向测试串行共用另一个新副本，避免并行解包竞争。开始时均不含真实 env/项目数据；测试新生成的 Chroma/SQLite 文件只位于仓外隔离目录，无真实模型调用。

### 实际修改与独立复核

- `main.py` 只增加 Row import 和三处局部类型注解。只读复核指出审计查询是 outer join、用户名可能为空，因此该注解最终为 `list[Row[AuditLog, str | None]]`，不是候选中的非空版本；查询、接口及业务行为未改。
- 两项日志测试直接挂接 `legal.chat` 的临时 handler，原拒绝/放行、事件计数、JSON 白名单及原问句脱敏断言完整保留；`finally` 移除自己的 handler 并恢复原日志级别，不修改应用的 `propagate`。
- 只读审查对照移入前副本核对后端 Python 文件，内容增量仅在上述两文件。最后一个空值注解意见已关闭，无剩余具体审查项；这不替代测试或发布验收。

### 本次证据

所有 label 仍位于前述仓外日志根；`.json` 保存完整命令、cwd、rc，`.out/.err` 保存输出。旧失败证据不覆盖、不改成成功。

| 检查 | 本次结果 | 日志 label |
|---|---|---|
| 日志测试移入前 | 实际配置下 2 failed；日志已发出但 caplog 捕获不到；rc=1 | `minimal-log-red-confirmed-20261002` |
| 类型注解移入前 | 同样 3 项 `var-annotated`，74 文件；rc=1 | `minimal-types-red-20261002` |
| 日志测试移入后 | 相同实际日志配置下 2 passed；rc=0 | `minimal-log-green-20261002` |
| 日志反向控制 | 仅在隔离测试进程禁用真实 warning 留痕，原两条事件计数断言均失败；**预期 rc=1**，证明测试不是恒绿 | `minimal-log-mutant-20261002` |
| 最终全量非 slow | **1671 passed、10 skipped、18 deselected；coverage 85.09%，门槛 70；rc=0** | `minimal-final-full-20261002` |
| 最终 mypy | **74 source files 无错误，rc=0**；仍受项目既有排除/未标注函数体配置限制 | `minimal-final-types-20261002` |
| 最终 A/B/C＋bootstrap 定向 | 122 passed，1 条既有 Starlette 弃用警告；rc=0 | `minimal-final-targeted-20261002` |
| 最终 lint / format | 均 rc=0；269 文件格式符合要求 | `minimal-final-serial-lint-20261002`、`minimal-final-serial-format-20261002` |
| 最终扫描器回归 | 14 tests OK；临时 Git 库及完整假凭据；rc=0 | `scanner-minimal-final-serial-20261002` |
| 质量/发布仪器守卫 | 9 passed / 27 tests OK；均 rc=0；发布仪器使用原脚本位置和临时 fixtures | `minimal-budget-final-20261002`、`minimal-release-final-confirmed-20261002` |
| 保护及代码绑定 | 41 保护对象大小/hash 一致，missing/changed 0；已有引用和三冻结业务文件未变；12 个覆盖文件与最终全量及静态副本逐字一致 | `protected-minimal-before-20261002.log`、`protected-minimal-after-20261002.log`、`minimal-provenance-final-confirmed-20261002` |
| 后端内容绑定 | 265 个被跟踪 Python 文件与最终全量副本归一化换行后内容全部一致；其中 61 个只有 Git archive 的 LF / 工作区 CRLF 差异，不声称它们原始字节相同 | `minimal-backend-content-bind-20261002` |

准备过程的错误不计作功能红灯：最初日志探针漏传 `setup_logging` 的 level、发布包装器导入路径遗漏，均在分析后修正；另一次并行建副本共用 `baseline-head.tar`，lint/format/扫描器在解包阶段遇到 `unexpected end of data`，未运行到检查。后续停止并行建副本，串行新副本检查通过。已跑全量的副本含测试新生成的隔离 Chroma 文件，因而没有复用它调用“初始无库”准备器。首个代码绑定检查也因未处理本来就不存在的候选 PDF 测试文件而退出；补上存在性比较后取得上表成功结果。没有删除失败副本、弱化断言或改写历史日志。

**结论与未完成项：** 本轮获准的工作区最小移入及 A/B/C 后端验收已闭环；HEAD 仍为 `d8625e5958cc40751d027a0dd612f179397a8345`。依赖声明、候选 PDF/上传测试、T7 文档均未移入，既有 A/B/C 代码未被覆盖。只使用已安装验证解释器，不安装/升级依赖，也不证明全部允许依赖版本组合兼容。慢测试、前端、最新依赖审计、Linux/远端 CI、真实凭据普查及真实 rerank 验收未在本轮执行。整个候选整合、D2 风险签字、凭据轮换与发布条件仍按主报告 §16.4 处理。未提交、整分支合并、推送、移动引用、写真实库或部署；TEMP 证据不是新的持久交付包，原固定快照/签字证据不变。

## 2026-10-02：本地提交收尾（授权与提交前证据）

Owner 在当前助手明确建议“核定清单并本地提交，不推送”后回复“按你的建议执行”。该授权仅解除下列 13 文件的一次正常本地提交限制；前述“未提交、引用未变”保留为各历史修复轮的事实，不是这次禁止正常前进 master 的指令。其他引用、候选整合、push、依赖安装、真实库、模型调用和部署边界不变。

提交清单：

```text
backend/answer_cache.py
backend/knowledge_service.py
backend/main.py
backend/retrieval.py
backend/retrieval_core.py
backend/tests/test_cache_scope_invalidation.py
backend/tests/test_cache_similar.py
backend/tests/test_light_exit_gates.py
backend/tests/test_request_bootstrap.py
dispatch-output/local-candidate-closeout-20260928/b_worktree_value_scan.py
dispatch-output/local-candidate-closeout-20260928/test_worktree_value_scan.py
docs/superpowers/plans/2026-10-01-first-batch-safety-cache-fixes.md
docs/work-report-20260929-d2-signoff-round.md
```

不使用 `git add -A`。旧 `2026-09-29-local-candidate-decision-and-release-prep.md` 的既有修改、其他未跟踪诊断产物、env/数据、仓外工具/日志均不纳入。报告 §16 的既有审核及历史纠偏与本轮修复记录一并保留，不撤销或覆盖。

本次重新从固定前置 HEAD 导出单个隔离副本，串行运行全部门禁，旧 runner 和日志不覆盖。日志根仍为前述仓外目录，各 `<label>.json` 保留完整命令/cwd/rc：

| 提交前检查 | 实际结果 | 日志 label |
|---|---|---|
| 后端非 slow 全量 | 1671 passed、10 skipped、18 deselected；coverage 85.09%，门槛 70；rc=0 | `commit-preflight-full-20261002` |
| mypy | 74 source files 无错误，既有配置限制不变；rc=0 | `commit-preflight-types-20261002` |
| Ruff lint / format | 均 rc=0，269 文件格式符合要求 | `commit-preflight-lint-20261002`、`commit-preflight-format-20261002` |
| 扫描器 / 质量守卫 / 发布仪器 | 14 tests OK / 9 passed / 27 tests OK；均 rc=0；仅隔离库与假凭据 fixtures | `commit-preflight-scanner-20261002`、`commit-preflight-budget-20261002`、`commit-preflight-release-20261002` |

只读需求轴复核为 0 项发现；规范轴为 0 项硬违反、1 项非阻断维护提示：两项日志测试的 handler 设置重复。按明确最小移入边界保留，不因此扩展到 fixture 重构。没有以该提示掩盖功能错误。

仓库当前未安装活动 pre-commit hook，两个活动 post hook 均只有 shebang。未安装或下载 hook 依赖；除上述 Ruff 外，用仓外 `check_commit_contents.py` 检查精确暂存清单、文本文件卫生、常见凭据形状及当前八键值，只允许返回 0 后提交。凭据仅在检查进程内存参与比对，不打印/保存值；该检查不覆盖历史旧值、未知凭据或全工作区，更不批准外发。本批不改 YAML，无需将 check-yaml 扩成全仓扫描。

测试源码另与暂存内容/工作区绑定；41 保护对象提交前后重新核对，只允许 master 因正常提交前进，候选及其他引用不变。完整动作证据由 `commit-index-check-20261002`、`commit-binding-before-20261002`、`commit-closeout-after-20261002` 及 `protected-commit-before-20261002.log` / `protected-commit-after-20261002.log` 给出；这段是检查契约，不能仅凭文档判断命令已成功。

**提交结果的单一事实源是 Git，而不是循环回填本页的 SHA。** 提交说明为 `fix: harden credential scanning and cache invalidation`；核对本批结果使用 `git log --oneline d8625e5958cc40751d027a0dd612f179397a8345..HEAD -- docs/superpowers/plans/2026-10-01-first-batch-safety-cache-fixes.md`，再用 `git show --stat <实际提交号>` 对清单。若本批文件已包含在提交中、没有新的对应差异，不要重复提交或 amend 来“更新自己的提交号”。

本轮未跑依赖真实知识库召回的 `smoke_citation_fast.py` 24 项运行烟测，不以空库或伪造召回代替；其判据测试随隔离全量运行。前端、依赖审计、真实模型、慢测试、Linux/远端 CI、D2 签字及完整发布验收仍不作完成声明。
