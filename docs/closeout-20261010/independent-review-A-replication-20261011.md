# 独立复核 A — 证伪式复现（2026-10-11 非部署收尾轮 · 第二批）

复核对象：另一 AI 会话 2026-10-10/11 交付的"非部署发布收尾轮"第二批（候选树头 `176899f`，本轮五笔提交 `176899f ed76192 bffbe1c 91bd53d 8903da1`）。
被审文字：`reports/gates.md` §38–§45、`reports/closeout-final-J-draft.md` §10、`reports/decisions-needed-20261010.md`（§A/§B/§C）、三张票 `dispatch-D14/D6/D20`、`runbook-I`。
本复核全程只读两棵树；解释器为在册 `candidate-envB/Scripts/python.exe`；未 commit/push/改 ref/checkout/restore/stash；未读任何凭据/真实库路径；未跑 `smoke_*.py`；未连/重启 compose 栈、未占端口。
路径：R=`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`；C=`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`。

## §0 三行汇总

- 采纳：**8 条**（N1、N2、N3、N4、N5、N6、N7 的四项枚举检查、N8）——每条均在我本机重跑并复现。
- 驳回：**1 条**（N7 附带）：`gates.md` §41 与台账 D-25 称 source-probe "只挂 schedule + workflow_dispatch，不占每次 PR"，与 `ci.yml` 实态不符（作业无 `if:` 门、`pull_request` 触发无条件）。
- 核不了：**0 条**（清单内枚举项全部可复现；未复跑的旁证见 §9，属"未做"非"核不了"）。
- 报告绝对路径：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/reviews/20261011-round2/independent-review-A-replication-20261011.md`
- 自量 CRLF 读数（本报告）：见 §10 末尾。

## §1 N1 代码位置与内容 —— 采纳

主张：`llm_registry.py` 有 `REJECT_COOLDOWN_BY_STATUS`/`reject_cooldown_s`/`reject_kind`/`ModelEntry.rejected_kind`/`status()` 带 `rejected_kind`；`observability._ACCOUNT_FIELDS` 元组**内**含 `llm_reject_cooldown_s`、`llm_reject_kind`；`routing_metrics.TECHNICAL_FALLBACK_REASON_CODES` 含 `TOOL_BUSY` 且集合大小 = 6。

我的命令与输出：

```
$ grep -nE "REJECT_COOLDOWN_BY_STATUS|def reject_cooldown_s|def reject_kind|rejected_kind" C/backend/llm_registry.py
44:REJECT_COOLDOWN_BY_STATUS = {401: 3600, 403: 3600, 404: 3600}
48:def reject_cooldown_s(status: int | None) -> int:
53:def reject_kind(status: int | None) -> str:
346:    rejected_kind: str | None = None
713:            e.rejected_kind = reject_kind(status)
790:                    "rejected_kind": e.rejected_kind if e.rejected_now else None,
```

AST 现读 `_ACCOUNT_FIELDS`（在元组内而非元组外）：

```
$ candidate-envB/Scripts/python.exe - <<PY   # ast 解析 observability.py
type Tuple len 64
has llm_reject_cooldown_s: True
has llm_reject_kind: True
index cooldown 55 kind 56
```

AST 现读 `TECHNICAL_FALLBACK_REASON_CODES`（frozenset 内 dict 展开）：

```
size 6
['AGENT_BUDGET_EXCEEDED', 'PLANNER_PARSE_ERROR', 'TOOL_BUSY', 'TOOL_TIMEOUT', 'TOOL_UNAVAILABLE', 'VERIFIER_TECHNICAL_FAILURE']
TOOL_BUSY in set: True
$ grep -n "TOOL_BUSY" C/backend/tools/gateway.py
246:                    error_code="TOOL_BUSY",
```

判决：**采纳**。字段/函数/键名齐备，两日志字段确在 `_ACCOUNT_FIELDS` 元组内（index 55/56），降级白名单大小 = 6 且含 `TOOL_BUSY`（唯一产点 `tools/gateway.py:246`）。`status()` 每行带 `rejected_kind`（`llm_registry.py:790`，且仅 `e.rejected_now` 时非 None）。

## §2 N2 409 分档 —— 采纳

主张：`RESUME_CONFLICT_DETAILS` 覆盖 `_resume_reason_codes_in_source()` AST 现读的每个成因码；`resume_conflict_detail()` 未登记码回落旧句；`main.py` 409 用异常携带 detail；`test_agent_resume.py` 三条新用例逐条读。

我**自己**跑了一遍 AST 扫描（不跑测试进程，直接解析 `controller.py`）：

```
$ candidate-envB/Scripts/python.exe - <<PY   # 复刻 _resume_reason_codes_in_source 的扫描逻辑
codes (7): ['answer_invalid', 'cas_conflict', 'issue_missing', 'pending_anchor_mismatch', 'state_stale', 'state_unreadable', 'step_budget']
keys  (7): ['answer_invalid', 'cas_conflict', 'issue_missing', 'pending_anchor_mismatch', 'state_stale', 'state_unreadable', 'step_budget']
unmapped codes-keys: []
extra keys-codes  : []
```

（注：`RESUME_CONFLICT_DETAILS` 是带注解的 `AnnAssign`，我的扫描器需按 AnnAssign 取键；只按 `Assign` 会读成 0 键——这是仪器坑，与被审代码无关，特此标注。）

回落腿 + main.py 出口（直接读源）：

```
controller.py:204   return RESUME_CONFLICT_DETAILS.get(reason_code, RESUME_CONFLICT_DETAIL)   # 未登记→旧那句
controller.py:179   RESUME_CONFLICT_DETAIL = "Agent 任务已变化，无法恢复"
main.py:1917        raise HTTPException(status_code=409, detail=_resume_exc.detail) from None # 用异常携带 detail，不拼第二份
main.py:1901        raise HTTPException(status_code=409, detail=RESUME_LAW_AS_OF_DETAIL)      # law-as-of 另走一支
```

三条新用例断言（`test_agent_resume.py`）逐条读：
- `test_every_resume_reason_code_has_a_copy_bucket`（967）：`assert codes` 非空（仪器失效哨兵）+ `assert not unmapped`（每成因码有档）。
- `test_unregistered_reason_code_falls_back_to_the_generic_copy`（977）：`resume_conflict_detail("a_code_nobody_registered") == CONFLICT_DETAIL` 且 `resume_conflict_detail("") == CONFLICT_DETAIL`（回落不给 500）。
- `test_copy_buckets_are_distinct_and_leak_no_internal_jargon`（985）：`len({ADVANCED,ANSWER_INVALID,STEP_BUDGET,UNRECOVERABLE})==4` + `set(RESUME_CONFLICT_DETAILS.values())==texts` + 每条文案不含 `state_stale/cas_conflict/WAITING_USER/run_id/version/Agent`。

判决：**采纳**。7 个成因码全覆盖、无多无漏；未登记码回落旧句；409 出口取 `_resume_exc.detail`；三用例断言与主张一致。

## §3 N3 取消占位 —— 采纳

我的命令与源读输出：

```
main.py:1038  content = _PLACEHOLDER_STOPPED if reason == "stopped" else _PLACEHOLDER_NO_RESPONSE   # 两档
main.py:1098  _PLACEHOLDER_NO_RESPONSE = _ERROR_NO_RESPONSE + "。"
main.py:1099  _PLACEHOLDER_STOPPED = "本次回答已停止，未生成完整内容。"
main.py:2638 / 2648 / 2659   _delivered = True                                                      # 置真三处
main.py:2667  _reason = "no_response" if _delivered else "stopped"                                  # finally 判定
main.py:2670  await run_in_threadpool(_post_placeholder, pre, _reason)
main.py:2683  await run_in_threadpool(_post_placeholder, pre, "stopped")                             # compensate_unstarted 传 stopped
main.py:738   _post_placeholder({"conv_id": bootstrap.conv_id})                                      # 默认 reason=no_response（未改）
```

finally 仅在 `if not _posted and not pre.get("assistant_committed")` 时进入（2664），`_delivered` 只在自然结尾/LLMBusy/异常三支置真；客户端 GeneratorExit 半途退出时 `_delivered` 保持 False ⇒ `stopped`。

判决：**采纳**。两档、`_reason` 判定、`compensate_unstarted` 传 `stopped`、bootstrap 站点仍 `no_response` 全部对上。

## §4 N4 七枪变异复现（抽两枪，副本树上） —— 采纳

副本：`git -C C archive HEAD | tar -x -C R/reviews/20261011-round2/n4copy`。归档只含 tracked 文件；先跑基线，四只点名用例文件全绿（**未缺** ignored 面即可跑，故本轮无需 `cp -a` 任何 ignored 目录/文件，也无从触红线）：

```
BASELINE_RC=0
115 passed, 1 warning in 67.11s   # tests/test_llm_reject_channel.py + test_stream_cancellation.py + test_cancel_boundaries.py + test_chat_turn_persistence.py
```

**M1**（`REJECT_COOLDOWN_BY_STATUS` 的 3600→300，仅该字面量）：

```
M1_RC=1
2 failed, 25 passed
FAILED test_config_rejections_cool_longer_than_shape_rejections
FAILED test_status_single_columns_the_two_rejection_kinds
>       assert _cooling_left(reg, "k1", clock) == 3600
E       AssertionError: assert 300.0 == 3600
>       assert rows["cfg"]["rejected_remaining_s"] > rows["shp"]["rejected_remaining_s"]
E       assert 300.0 > 300.0
```

（`test_config_rejections…` 另有 `assert [cooldown]==[3600,300]` 亦随长档塌陷而红，同一条用例计一次。）

**M4**（`_reason = "no_response" if _delivered else "stopped"` → 恒 `_reason = "no_response"`）：

```
M4_RC=1
4 failed, 84 passed
FAILED test_cancel_boundaries.py::test_d2_disconnect_before_body_persists_exactly_one_placeholder[disconnect-before-first-iteration]
FAILED test_cancel_boundaries.py::test_d2_disconnect_before_body_persists_exactly_one_placeholder[disconnect-while-prebody-work-in-flight]
FAILED test_chat_turn_persistence.py::test_immediate_reask_waits_for_cancelled_turn_commit[False]
FAILED test_chat_turn_persistence.py::test_immediate_reask_waits_for_cancelled_turn_commit[True]
>       assert contents[1] == PLACEHOLDER_STOPPED, contents
E       AssertionError: ['窗口复现：劳动法第四十四条。', '服务暂时无响应，请稍后重试。']
E       assert '服务暂时无响应，请稍后重试。' == '本次回答已停止，未生成完整内容。'
>       assert rows == [...]
```

位级还原：两文件 `finally` 还原后 sha256 与改前逐字相同，且副本 `main.py` 与被审候选树 tracked `main.py` sha 一致（唯一 sha 计数 = 1）：

```
llm_registry.py restored = edc80c99f1c438fb44199b6a00935ac5726113e6edf9b33a453d0b39e0bbad53
main.py restored         = a746f770d65e619755fcc93aea2f5ea492e377816885bfa7996ec1ea452d5071
```

副本树已 `rm -rf`，只留日志（`n4-*.log`）。跑完候选树 `git status --porcelain` = 0 行，HEAD 仍 `176899f`。

判决：**采纳**。M1 杀 2、M4 杀 4，与 §39/J §10.1 声称一致；红的是"两档必须不同"的判据断言，非形状/恒真断言。

## §5 N5 门禁四轴 —— 采纳

命令（`COVERAGE_FILE` 与 `--junitxml` 均重定向到本复核目录；rc 直接捕获，不走管道）：

```
cd C/backend
COVERAGE_FILE=R/…/n5/.coverage.reviewA candidate-envB/Scripts/python.exe -m pytest -m "not slow" --cov=. --cov-fail-under=70 --junitxml=…/n5-junit.xml -q -p no:cacheprovider
PYTEST_RC=0
TOTAL  8891  1080  2726  325  86%
Required test coverage of 70% reached. Total coverage: 86.37%
1932 passed, 10 skipped, 18 deselected, 160 warnings in 287.09s

pytest --collect-only -q                          → 1960 tests collected
pytest --collect-only -q -m "not slow"            → 1942/1960 tests collected (18 deselected)
junit testsuite attrs: {'tests':'1942','skipped':'10','failures':'0','errors':'0'}   # 1932+10=1942 对平

ruff check .            → RUFF_CHECK_RC=0   All checks passed!
ruff format --check .   → RUFF_FORMAT_RC=0  283 files already formatted
mypy .                  → MYPY_RC=0         Success: no issues found in 74 source files

git -C C status --porcelain | wc -l           → 0
```

判决：**采纳**。被审五数（1932/0/10/18、cov 86.37%、collected 1942/1960、junit tests=1942、283 files、mypy 74 files）逐一复现，rc 全 0，跑后工作树 0 行。

## §6 N6 §44 上传集机理 —— 采纳（数随头动，见注）

三根轴 + 对照（当前头 `176899f`，比 §44 表所用的 `ed76192` 多一笔 docs 提交）：

```
rev-list --objects HEAD                                            → 4472
rev-list --objects refs/closing/remote-master                      → 3803
rev-list --objects refs/closing/remote-master..HEAD                → 4472   # == 全量 ⇒ 一点没省
对照 rev-list --objects HEAD~1..HEAD                               → 8      # 正常祖先 ⇒ 剪到极小
对照 rev-list --objects HEAD~1                                     → 4464
```

决定性取样（`ls-tree -r -z` 两侧按路径比 blob，再回查 `^remote-master HEAD` 输出）：

```
common paths: 2136   same-blob files: 2037   distinct same blobs: 1782
same blobs present in ^remote-master HEAD upload set: 1782 / 1782
NOT in upload set: 0
```

裸值 blob（自取，不采信转述）：

```
$ git -C C rev-parse 817e7d3:dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py
d59a7b614514445d617d55bb9e7dd581e2636805                       # 与声称一致
在上传集 ^remote-master HEAD : 1
在远端可达集 refs/closing/remote-master : 0
在 HEAD 全可达集 : 1（健全性）
```

判决：**采纳**（机理）。无关历史时 `A..B` 确实"一点不省"（range 4472 == full 4472），而正常祖先对照能省到 8——两种机理被这条对照干净区分；2037 只同 blob 文件（去重 1782 枚）全部仍在上传集。裸值 blob 上传集=1、远端可达=0，成立。
**注**：§44 表里的 4464/3803/10/4454/2037 是在头 `ed76192` 上的读数；我在最终头 `176899f` 复跑，remote-master(3803) 与同 blob 文件数(2037) 逐字不变，HEAD 轴与对照值随多出的 docs 提交漂到 4472/8——这正是被审方自己声明的"数随头动、开工与最终头各跑一次"，不推翻机理，只印证纪律。

## §7 N7 交付/文档类主张 —— 采纳（四枚举项），另检出 1 处措辞驳回

**(a) DEPLOYMENT.md §7 三行 vs 代码**（候选根 `DEPLOYMENT.md:176–183`）：
- 端点 `GET /api/admin/llm-status`（`main.py:3082`，`Depends(require_admin)`）✓
- 返回键 `models`/`utility_quota`/`metrics`（`main.py:3090–3092`，另有 `feature_router`）✓
- `models[].quota_left / rejected_remaining_s / rejected_kind / depleted / below_threshold`——均为 `registry.status()` 返回键（`llm_registry.py:786–791`）✓；文案 `kind=config`＝401/403/404 冷却 1 小时（3600）、`kind=shape`＝400/422 短冷却 5 分钟（300），与 `reject_kind`/`REJECT_COOLDOWN_BY_STATUS` 一致 ✓
- `metrics.agent_route.fallback_count` 与 `.fallback_reason_code_counts`（`routing_metrics.py:159–160`），后者每因一 key ⇒ `TOOL_BUSY` 与 `TOOL_UNAVAILABLE` 天然分列 ✓

**(b) backend/Dockerfile 两处 `||` 回落**：torch 步（55–60）与 requirements 步（62–63）各一条 `cmd || fallback`，RUN 默认 `/bin/sh -c`，`||` 为 POSIX 逻辑或——语法合法。引擎在册（Server 29.6.2），用空上下文跑 `--check`（不 build、不读 backend/data 等禁读面）：
```
$ docker build --check -f C/backend/Dockerfile R/…/_emptyctx
Check complete, no warnings found.   DOCKER_CHECK_RC=0
```
✓

**(c) `.github/workflows/ci.yml` source-probe（PyYAML 解析 + jobs 结构完整）**：
```
jobs: ['backend', 'frontend', 'source-probe']       has source-probe: True
source-probe runs-on? True  steps? True  nsteps= 4
jobs missing runs-on/steps: []
triggers: ['push','pull_request','schedule','workflow_dispatch']
```
✓（该枚举项通过；`on` 顶层键在 YAML1.1 下解析为布尔 True，属 PyYAML 已知形状，非缺陷。）

**(d) docs/chroma-risk-triage-20261003.md 候选 vs 主仓**：
```
sha256（两棵树逐字相同）: 0847ba2d6d9043c79b81d0d31d36227c144cef03e9f7234fb896670941994837
size 3252 B   lines 23   mtime(epoch 两侧相同): 1791038299  (cp -a 保留)
候选 tracked 且随提交: git log -1 → bffbe1c …风险册入库（D-11）
```
✓

**驳回一处（§41 line 962 / 台账 D-25 line 53 的措辞）**：声称 source-probe "只挂 schedule + `workflow_dispatch`，不占每次 PR"。现读 `ci.yml` 全文件 **无任何 job 级 `if:`**：

```
$ grep -nE "if:|event_name|needs:" C/.github/workflows/ci.yml   →  (无输出)
on: push: branches:[main,master] / pull_request: / schedule(cron 17 3 * * *) / workflow_dispatch:
```
`pull_request` 触发无条件，作业又无 `if` 门 ⇒ 每个 PR 都会跑 source-probe（以及每次 push 到 main/master）。**正确读数**：source-probe 在 schedule 与手动 dispatch 上按日节奏运行，但结构上**未被排除出 PR/push 运行**；要实现"不占每次 PR"需在作业上加 `if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'`（现无）。该措辞把"意图"写成了"构造性质"，据本仓在册纪律判为夸大。

判决：N7 四项枚举检查 **采纳**；§41/D-25 的"不占每次 PR"子句 **驳回**（附正确读数如上）。

## §8 N8 台账卫生 —— 采纳

```
gates.md：bytes 121789  NUL count 0  CR count 0        # python 逐字节计数（无 NUL）
gates.md '^## ' 节数（命令现读）：45

decisions-needed §A/§B/§C 按段 D 行（台账自带 awk/分段计数，脚本按 D-(\d+) 归段）：
§A: 2  D-rows -> [5, 19]
§B: 0  D-rows -> []
§C: 30 D-rows -> [1,2,3,4,6,7,8,9,10,11,12,13,14,15,16,17,18,20,21,22,23,24,25,26,27,28,29,30,31,32]
A∩B [] A∩C [] B∩C []        # 无同一编号出现在两档
§A rows == {5,19}? True
```

§B 现为空且正文写明为何空（`decisions-needed` 18–20 行的引用块："10-11 06:2x… §A/§B 从 18 条降到 2 条；本批新问出的 D-30/D-31/D-32 也已同批裁完并移进 §C"）。§A/§B 只剩 D-5/D-19；D-5、D-19 只出现在 §A、未与 §C 并存。

判决：**采纳**。（注：§42 曾记 `gates.md` 修 NUL 后 bytes=109120；现值 121789 是其后 §43–§45 追加正文所致，不影响"NUL=0"这一枚举判据；§42 那个字节数是历史读数，非现状。）

## §9 已知限制（哪些我没复跑、为什么）

- 七枪变异只按要求抽两枪（M1/M4）；M2/M3/M5/M6/M7 未复跑（非清单要求，且需改动更多在册文件，只读纪律下不做）。M1/M4 已足以证两批"分档判据能红"的机制。
- 前端三/五条腿（`tsc`、`next lint`、`vitest 83`、`build:check VERDICT=OK`）**未复跑**：N5 清单只点名后端四轴 + collected + junit；前端面本轮字节据 §45 称零改动，非我复核射程。
- D-25 的 pip 双源自检、`ci_yaml_check.py` 结构自检**未复跑**（涉网络/外部索引，红线不鼓励；我只在 N7 用 PyYAML 独立解析 ci.yml 得同源结论）。
- `--cov-fail-under` 我照跑（rc=0）；`error-constant` 那条 CoverageWarning 与被审日志一致（backend 目录有一枚非 py 残留名，两侧同环境），未追。
- N6 计数在最终头 `176899f` 复跑，与被审表 `ed76192` 轴不同，已按"数随头动"逐值标注；未复跑被审 §44 引用的 `push-upload-axis-recheck` 原日志（那是其自证件，我以独立命令重算替代）。
- 未跑任何 `smoke_*.py`、未读 `.env*`/`app.db`/`data/`/`chroma_db/`/`media/`/`backups/`/`~/.cache/huggingface`、未连 compose 栈、未占 3021/8088、未打印任何凭据值。

## §10 复跑索引（本报告每条 → 可重跑命令）

```bash
R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
PY="$R/candidate-envB/Scripts/python.exe"

# N1
grep -nE "REJECT_COOLDOWN_BY_STATUS|def reject_cooldown_s|def reject_kind|rejected_kind" "$C/backend/llm_registry.py"
"$PY" -c "import ast;print([n.targets[0].id for n in ast.parse(open(r'$C/backend/observability.py',encoding='utf-8').read()).body if isinstance(n,ast.Assign)])"  # 见正文 AST 法
# N2 全覆盖（AST 现读成因码，须按 AnnAssign 取键）
"$PY" - <<'EOF'  # 见 §2 正文脚本：codes(7)==keys(7), unmapped=[], extra=[]
# N5
cd "$C/backend" && COVERAGE_FILE="$R/reviews/20261011-round2/.coverage.reviewA" \
  "$PY" -m pytest -m "not slow" --cov=. --cov-fail-under=70 --junitxml="$R/reviews/20261011-round2/n5-junit.xml" -q -p no:cacheprovider
"$PY" -m pytest --collect-only -q -m "not slow" -p no:cacheprovider    # 1942/1960 (18 deselected)
"$PY" -m ruff check . ; "$PY" -m ruff format --check . ; "$PY" -m mypy .
# N6 三轴 + 同 blob 回查（见正文 ls-tree -z / rev-list --objects ^remote-master HEAD）
git -C "$C" rev-list --objects refs/closing/remote-master..HEAD | wc -l   # 4472 == HEAD 全量
git -C "$C" rev-parse 817e7d3:dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py  # d59a7b61…
# N7
grep -nE "if:|event_name" "$C/.github/workflows/ci.yml"                   # 空 ⇒ 无 job 级 if（驳回"不占每次 PR"）
# N8
"$PY" - <<'EOF'  # gates.md: open(...,'rb').read() → NUL count / CR count  （见正文：0 / 0）
grep -cE "^## " "$R/reports/gates.md"                                      # 45（现读）

# 本报告自量（LF 断言）
```

本报告自量 CRLF 读数（实测，已满足 LF）：

```
$ tr -dc '\r' < independent-review-A-replication-20261011.md | wc -c
0
$ wc -c → 20390   wc -l → 311
```
