# 独立复核 A 路（只读复算）— 2026-10-10

- 复核人：A 路独立复核。**未参与**原工作；本文每个数字都来自我本轮自己跑出的输出。
- 运行根（只读）：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`
- 候选人（只读）：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`
- 解释器：`candidate-envB/Scripts/python.exe`（Python 3.11.0；ruff 0.16.10；mypy 2.4.0）
- 未读/未哈希任何禁区对象（`.env*`、`app.db`、`data/`、`chroma_db/`、`media/`、`backups/`、`~/.cache/huggingface`）；未运行会读真实库的 CLI；未启动浏览器、未占用 3021/8088/3178/8777。

## 复核快照（重要：被复核报告在复核期间仍被改写）

gates.md 在 13:55 / 14:59 / 15:13 / 15:23 至少 4 次落盘；`h-ci-and-credentials.md` 14:06→15:04；期间还新增了 `reports/local-environment-switch.md`。候选分支 HEAD 也从任务书写的 `8c179e7` 变为 **`a934fa7`**（第三笔提交，内容=CI 注释勘误，见 §1#29）。本文读数对应下列快照（`sha256` 前 8 位）：

| 文件 | sha256（前 8） | 现量 mtime |
|---|---|---|
| reports/gates.md | `bfb15a20` | 15:23 |
| reports/trust-and-data-drill.md | `a5d08882` | 13:54 |
| reports/h-ci-and-credentials.md | `286c6a2b` | 15:04 |
| reports/owner-decisions-20261010.md | `3053bfd7` | 13:10 |
| reports/dependency-decision.md | `ba8815a7` | 03:39 |
| reports/baseline.md | `ed2f1867` | 02:20 |

我的写盘范围（全部在运行根，**未动仓库任何文件**）：`evidence/A-*.{log,json,out,xml}`、`evidence/A-e2-trust/`、`evidence/.mypy_A/`、覆写 `evidence/loader-trust-mutants.log`（脚本硬编码该路径；改前原版已备份为 `evidence/A-before-loader-trust-mutants.log`）、以及本文件。

---

## §0 一句话结论

共复算 **47 项**（含全量 pytest 现场重跑、4 台变异仪现场重跑、5 臂行为探针现场重跑、4 次 pip-audit 现场重跑）：**40 项一致**；**5 项对不上**——3 项是纯数字错（vitest 用例数 50→实测 83；覆盖率未覆盖行 1076→实测 1079；"解冻记录 5 行"→实测 7 行），2 项是"现量"已过期（gates §7 的 25 只/8 只及其复算命令现在吐 5/0；gates §8.1 "两笔本地提交"实为 3 笔）；另 **2 项半真带缺陷**（sha 不变为真但日志印 `equal=False`；category 变异仪 M1/M3 为真但 M2 不可复算——仪器把变异写成了语法错误），**2 处指针漂移**（Dockerfile `:38`/`:41-48` → 现量 `:39`/`:47-55`），**1 份证据 artifact 损坏**（shape-scan 文件 256 个 NUL 字节；其主张我用 git blob 重建为真）。另有 2 项**未复算**（HF 模型 12/12 哈希、前端三腿现场重跑），原因见 §3.3。

---

## §1 复算表

命令列 = 我**真跑过**的那条（`R`=运行根，`C`=候选人，`$PY`=私有解释器；bash 里 `$R/candidate-envB/Scripts/python.exe`）。

### 1.1 全量测试与用例账

| # | 主张（出处） | 我的复算 | 命令 | 一致? |
|---|---|---|---|---|
| 1 | 全量非 slow `1925 passed / 0 failed / 10 skipped / 18 deselected`（gates §7） | `1925 passed, 10 skipped, 18 deselected, 160 warnings in 195.35s`，RC=0 | `cd "$C/backend" && $PY -m pytest -q -m "not slow" -p no:cacheprovider -p egress_guard --junitxml="$R/evidence/A-junit.xml"`（钉死 run_backend_tests.sh 那批 18 只键 + `EMBEDDING_PROVIDER=local`/`RERANK_ENABLED=false`，HF_HOME/HF_HUB_CACHE 指运行根） | ✅（时长 195.35s vs 报告 210.51s——同一命令不同负载，非读数差） |
| 2 | `junit tests=1935`（gates §7） | `junit tests=1935 failures=0 errors=0 skipped=10` | `$PY -c "…ET.parse(r'$R/evidence/A-junit.xml')…"` | ✅ |
| 3 | socket 守卫：321 事件、非回环 0、回环 319、`blocked_targets=[]`（gates §4/§7） | `{"events":321,"blocked_non_loopback":0,"loopback_connects":319,"afunix":0,"blocked_targets":[]}`（与我自跑那趟逐字相同） | 同上（`EGRESS_SUMMARY=$R/evidence/A-egress.full.summary.json`） | ✅ |
| 4 | `test_retrieval_category_narrow_fallback.py` 9 条（gates §6.2） | `9 tests collected in 10.19s` | `cd "$C/backend" && $PY -m pytest --collect-only -q -p no:cacheprovider tests/test_retrieval_category_narrow_fallback.py \| tail -1` | ✅ |
| 5 | `test_loader_trust_gate.py` 4 条（gates §7） | `4 tests collected in 0.11s` | 同形，换文件名 | ✅ |
| 6 | `test_backup_restore_drill.py` 7 条（gates §7） | `7 tests collected in 9.62s` | 同形 | ✅ |
| 7 | `test_import_laws_guard.py` 4 条（gates §7） | `4 tests collected in 0.13s` | 同形 | ✅ |
| 8 | 增量对账 1901+9+4+7+4=1925（gates §7） | 1925（#1）；且中间态日志实测 `1910 passed / junit 1920`（=1901+9，`pytest.full.candidate-envB.20261010T045546Z.log`） | 见 #1；中间态：`grep -aE "^[0-9]+ passed" $R/evidence/pytest.full.candidate-envB.20261010T045546Z.log` | ✅ |
| 9 | 两套环境逐字同读数 `1901 passed / 0 failed / 10 skipped / 18 deselected`（gates §0/§4） | envA（`candidate-env`）与 envB 两份日志各为 `1901 passed, 10 skipped, 18 deselected`，junit tests=1911，RC=0 | `grep -aE "^(python=\|[0-9]+ passed\|RC=\|junit )" $R/evidence/pytest.full.20261009T190925Z.log $R/evidence/pytest.full.candidate-envB.20261009T192337Z.log` | ✅ |
| 10 | B 四票 `48 passed / 0 failed`（gates §0） | envA `48 passed in 25.20s` / envB `48 passed, 1 warning in 26.10s`，两份 junit tests=48 RC=0 | 同上形，`pytest.probe4.*.log` | ✅ |
| 11 | D-4 定向 6 文件 `59 passed / 0 failed / 0 skipped，29.53s`（gates §6.2） | 日志 ARGS=那 6 只；`59 passed, 1 warning in 29.53s`，junit tests=59/0/0/0，RC=0 | `cat $R/evidence/pytest.custom.candidate-envB.20261010T050738Z.log` | ✅ |
| 12 | B-45 三文件 `32 passed`（trust §3） | `32 passed, 1 warning in 44.01s`，junit tests=32，RC=0 | 同上形，`…T054349Z.log` | ✅ |
| 13 | D-4 改后 `18 passed / 0 failed`（owner §D-4） | `18 passed`，ARGS = 恰好那 3 只文件，RC=0 | 同上形，`…T045200Z.log` | ✅ |
| 14 | D-4 先红 `6 failed / 3 passed`（owner §D-4） | `6 failed, 3 passed, 1 warning in 48.48s`，junit tests=9/failures=6；正身那条报 `库里确实没有该类时应返回零，实际拿到了：[…]` | 同上形，`…T044946Z.log` | ✅ |
| 15 | E.2 首版 `3 passed` → 变异轮 `4 passed`（trust §1.3） | 首版日志 `3 passed`（junit tests=3）；4 条来自变异基线 #21 | `cat …T052018Z.log` | ✅ |
| 16 | 演练 WAL 尺子先红（trust §2"第一版…当场红"） | `…T052556Z.log`：`7 errors`，红因 `AssertionError: 演练要求源库开 WAL，实际 delete` | 同上形 | ✅ |
| 17 | B-45 假读数先例（trust §3） | `…T054232Z.log`：`1 failed, 31 passed`，红在 `test_write_modes_refuse_divergent_chroma_dir_before_touching_the_input`，失败信息 `未拦下…：NO_RAG_CHAIN` | 同上形 | ✅ |

### 1.2 静态门（候选树 + 私有环境，全部本轮现跑）

| # | 主张 | 我的复算 | 命令 | 一致? |
|---|---|---|---|---|
| 18 | `ruff check .` = `All checks passed!` rc=0（gates §7） | `All checks passed!` rc=0 | `cd "$C/backend" && $PY -m ruff check . > /tmp/ruff_check.out 2>&1; echo rc=$?` | ✅ |
| 19 | `ruff format --check .` = `283 files already formatted` rc=0（gates §7） | `283 files already formatted` rc=0 | `… -m ruff format --check . > /tmp/ruff_fmt.out 2>&1; echo rc=$?` | ✅ |
| 20 | `mypy .` = `Success: no issues found in 74 source files` rc=0，mypy 2.4.0（gates §7） | mypy 2.4.0 (compiled: yes)；`Success: no issues found in 74 source files` rc=0 | `MYPY_CACHE_DIR="$R/evidence/.mypy_A" $PY -m mypy .` | ✅ |
| 21 | 冻结两只（incidents 表）：`prompts.py` check rc=0、format rc=0；`gate5_judge.py` check `2 errors` | prompts: `All checks passed!` rc=0 / `1 file already formatted`；gate5_judge: `Found 2 errors`（1 fixable） | `$PY -m ruff check prompts.py`；`$PY -m ruff format --check prompts.py`；`$PY -m ruff check scripts/gate5_judge.py` | ✅ |
| 22 | 解冻记录"补了 **5** 行"（gates §6.1） | `diff evidence/pyproject.before 现文件` = **+7 行**（另 −1 为删掉的 exclude 行）；exclude 3 项→2 项 | `diff -u "$R/evidence/pyproject.before" "$C/backend/pyproject.toml"` | ❌ 5≠7 |

### 1.3 sha256 / AST 断言

| # | 主张 | 我的复算 | 命令 | 一致? |
|---|---|---|---|---|
| 23 | state_machine `50fede75…df87beca` → `81d58ce4…e36ecb4b`，5694→5672B，`ast_equal=true`，dump sha `2762f6fa…0cd04aa4` 两侧同，symbols/nodecounts 同（gates §6.1、owner D-1） | 完全一致（脚本现跑 `verdict: PASS`；`state_machine-format-ast.json` 与现量逐字段相同） | `$PY evidence/ast_equal_statemachine.py "$C/backend/agent/state_machine.py"`；`sha256sum evidence/state_machine.received.py "$C/backend/agent/state_machine.py"` | ✅ |
| 24 | `ast_equal_pair.py` 两只：retrieval `922f4dff…2fe9d7f4`→`9a504013…47c664cef`（70146→70116B）；新测试 `196766a7…0c9211c5`→`6ecd6ea8…829e9e96`（9931→9932B）（gates §6.3） | 四只 sha、四个字节数全对；两条 `ast_equal=true` | `$PY evidence/ast_equal_pair.py evidence/retrieval.preformat.py "$C/backend/retrieval.py"`（及 test_narrow 对） | ✅ |
| 25 | `drill-mutants.log`：M1 红 `…_quota_ledger_keeps_its_own_numbers`、M2 红 `…_manifest_covers_every_surface`、M3 基线 7 passed、三只 live sha `unchanged=True`（trust §2） | 现场重跑逐字一致（1 failed/6 passed；1 failed/6 passed；7 passed；三只 unchanged=True） | `bash evidence/run_mutants.sh "$R" "$C" A-drill-mutants.log tests/test_backup_restore_drill.py -- M1_swap_extra_mapping scripts/backup_data.py evidence/arms/bd_anchor_extra.txt evidence/arms/bd_repl_swap.txt M2_media_silent_skip scripts/backup_data.py evidence/arms/bd_anchor_media.txt evidence/arms/bd_repl_media.txt M3_baseline scripts/backup_data.py evidence/arms/bd_anchor_extra.txt @no-repl` | ✅ |
| 26 | `b45-mutants.log`：M1 删守卫 ⇒ 恰好红在 `test_write_modes_refuse_divergent_chroma_dir_before_touching_the_input`（1 failed/3 passed）；基线 4 passed；三只 unchanged=True（trust §3、gates §7） | 现场重跑一致（1 failed/3 passed；4 passed；三只 unchanged=True） | `bash evidence/run_mutants.sh "$R" "$C" A-b45-mutants.log tests/test_import_laws_guard.py -- M1_drop_guard_call scripts/import_laws.py evidence/arms/il_anchor.txt evidence/arms/il_repl_dropguard.txt M3_baseline scripts/import_laws.py evidence/arms/il_anchor.txt @no-repl` | ✅ |
| 27 | `loader-trust-mutants.log`：M1=`4 errors`（"该形状构造不出来"）、M2=`2 failed/2 passed`、M3=4 passed（trust §1.3） | 现场重跑：M2 `2 failed, 2 passed`、M3 `4 passed`；M1 的 `4 errors` 在我重跑的日志里仍**不出现**（脚本 grep 只留 `^FAILED\|^N passed/failed`，会把 `4 errors` 滤掉）——该读数只能从 `evidence/m1-full.log` 复算：`1 warning, 4 errors in 3.19s`，根因 `ValidationError: trust_remote_code extra fields not permitted`（pydantic v1） | `bash evidence/run_loader_trust_mutants.sh "$R" "$C"`；`… \| grep -aE "^(FAILED\|[0-9]+ (passed\|failed))"`；M1 全文 `evidence/m1-full.log` | ✅（M1 另有 artifact 支撑；见 §3.1-c） |
| 28 | "实时源码 sha 前后相同"（trust §1.3）＋"每份日志尾部都有 `live targets…unchanged=True` 三只 sha"（trust §5） | live `rag_chain.py` = `18685348a0fd9fe5…`，与 `evidence/rag_chain.sha-before` 全文相同 ⇒ **"前后相同"为真**；但 loader 日志尾部印的是 `live rag_chain sha= 18685348a0fd9fe5 before= C:/Users/33393/D equal= False` —— `equal=False` 是脚本 bug（把**路径**当第二参比对，`print(…, sys.argv[2][:16], …)`），且该日志**没有**"三只 sha"形状 ⇒ §5 那句"每份日志"不成立 | 见 #27；`cat evidence/rag_chain.sha-before`；`sha256sum "$C/backend/rag_chain.py"` | ⚠️ 主张半真（sha 真、日志文本与 §5 措辞不真） |
| 29 | 我重跑后三只 live sha 未被改动（trust §5、任务书要求） | `rag_chain.py 18685348a0fd9fe5`、`backup_data.py 98a63dd5457de69d`、`import_laws.py 8fb2c528e6d487fd`（与日志登记值逐只相同）；候选工作树 `git status --porcelain` 只有并行会话的 5 只 frontend | `sha256sum` 三只；`git -C "$C" status --porcelain` | ✅ |

### 1.4 行为级探针与变异仪（现场重跑）

| # | 主张 | 我的复算 | 命令 | 一致? |
|---|---|---|---|---|
| 30 | E.2 五臂 `GATE_HOLDS`，CTRL/A/B 加载且编码 `[1,768]` l2=1.0 非零无 marker；C（`"local"`）TypeError 且 **marker 有**；E（`True`）TypeError 无 marker（trust §1.2、gates §7） | 我现场重跑的新 JSON 与该表逐格相同：CTRL/A/B loaded=True marker=False shape=[1,768] l2=1.0 all_zero=False；C marker=True exc=TypeError…`return_unused_kwargs`；E marker=False 同 exc；`verdict=GATE_HOLDS`，四项 checks 全 true；ST 6.1.0 / transformers 5.19.0 / snapshot f03589ce… | `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $PY evidence/probe_st_trust.py "$R/evidence/A-e2-trust" "$R/model-cache/hub/models--BAAI--bge-base-zh-v1.5/snapshots/f03589ceff5aac7111bd60cfc7d497ca17ecac65"` | ✅ |
| 31 | `category-mutants.log`：M1「判定恒 True」→3 只命名用例红；M2「判定恒 False」→S2 两只红；M3→9 passed（owner §D-4） | M1 现场重跑 `3 failed, 6 passed`，红的正是 `test_S1_library_without_the_key_still_falls_back`、`test_presence_verdict_cached_and_cleared_on_invalidate`、`test_probe_unavailable_keeps_the_old_shape`；M3 见日志 `9 passed`；**M2 不可复算**：日志里根本没有 M2 结果行，我按脚本原锚点重跑 ⇒ `SyntaxError: expected 'except' or 'finally' block`、`1 error during collection`（锚点 `    cached = …` 是该行 8 空格缩进的后 4 空格，替换后把 `try:` 体切开）；换成**语义等价但语法正确**的"恒 False"变异后我实测 `4 failed, 5 passed`，其中含报告点名的两只 S2（另两只也红） | M1/M2 手搓同形命令（副本树 `mut-tree-Acat*` + 同锚点/替换）；语义正确版：`sed` 式替换 `        cached = _CATEGORY_ADVERTISED.get(name)\n        if cached is not None:\n            return cached\n` → `        return False\n`，再 `-rf` 跑 9 条 | ⚠️ M1/M3 一致；M2 不可复算且仪器写坏 |
| 32 | 覆盖率趟 `1 failed / 1924 passed`（h §3、gates §8.2） | `1 failed, 1924 passed, 10 skipped, 18 deselected … in 287.28s`，RC=1，红的是 `test_settings_repr_masking::test_repr_masks_every_secret_value` | `grep -aE "^[0-9]+ (passed\|failed)\|^RC=\|^FAILED" $R/evidence/pytest.cov.20261010T055634Z.log` | ✅ |
| 33 | 覆盖率门槛 `TOTAL 8866 语句 1076 未覆盖 → 86.35%`（gates §8.2） | 两份 cov 日志（第一次 T055634Z 与闭合趟 T070646Z）的 TOTAL 行都是 `8866  1079  2726  325  86%`，`Total coverage: 86.35%` | `grep -a "^TOTAL\|^Required" $R/evidence/pytest.cov.*.log` | ❌ 1076≠1079（86.35% 对） |
| 34 | 覆盖率第四趟闭合：`1925 passed`、RC=0（gates §8.2） | `T070646Z.log`：`1925 passed, 10 skipped, 18 deselected … in 222.95s`，RC=0，TOTAL 同 #33 | 同上 | ✅ |
| 35 | h §3 两臂实验：五个 key 各给不同多字符串 ⇒ `3 passed`；全给单字符 `k` ⇒ `1 failed / 2 passed` | 我自构造同样两臂（LLM/DASHSCOPE/SILICONFLOW/EMBEDDING/RERANK 五键）：多字符串 `3 passed, 1 warning in 14.31s`；全 `k` `1 failed, 2 passed`，FAILED 行点名 `test_repr_masks_every_secret_value` | `cd "$C/backend" && LLM_API_KEY=alpha-not-a-real-key-111 … $PY -m pytest -q -p no:cacheprovider tests/test_settings_repr_masking.py`（第二臂同样五键=`k`） | ✅ |
| 36 | socket 守卫自证：回环放过 + 两只非回环被拒 + 2 条记账（gates §4） | `LOOPBACK_RESULT ConnectionRefusedError refused_or_other`；`api.trychroma.com blocked`；`8.8.8.8 blocked`；`log_events=5 blocked_logged=2`；`SELFCHECK PASS` rc=0 | `$PY evidence/selfcheck_egress_guard.py` | ✅ |
| 37 | `--validate-only` 豁免守卫、守卫只在 `__main__`（trust §3） | `import_laws.py`：`PROD_CHROMA_DIR` :35、`def _check_env_contract` :262、`if __name__ == "__main__":` :278、`if "--validate-only" not in sys.argv: _check_env_contract()` :286-287；`backup_data.py` 同形在 :366-367（`rebuild_embeddings.py:108`、`switch_embedding.py:143` 亦被同一守卫覆盖） | `grep -n "PROD_CHROMA_DIR\|_check_env_contract\|__main__\|sys.argv" "$C/backend/scripts/import_laws.py"`；同形 grep 另两只 | ✅ |

### 1.5 依赖/凭据/改动面

| # | 主张 | 我的复算 | 命令 | 一致? |
|---|---|---|---|---|
| 38 | 残余通报"候选 runtime 与 dev 同为 24 记录 / 15 ID / 5 包"，分账 chromadb 2 / core 6 / openai 1 / splitters 2 / langsmith 4（dep §10、gates §0 C、h §2b 勘误） | **两轴都现场重跑**：runtime `Found 24 known vulnerabilities in 5 packages` rc=1；dev 同样 `Found 24 known vulnerabilities in 5 packages` rc=1；两轴各自 24/15/5，逐包分账相同（2/6/1/2/4）⇒ 现行两份 JSON 的 `dev-only: [] runtime-only: []` 复算成立，h 报告把"dev 轴确有独立通报"改成"两轴完全相同"是**正确方向的勘误** | `$PY -m pip_audit -r "$C/backend/requirements.txt" --format=json`；`$PY -m pip_audit -r "$C/backend/requirements-dev.txt" --format=json`；`$PY -c "…set(dv)-set(rt)…"` | ✅ |
| 39 | 单包读数：chromadb==0.4.24 → 2 条/2 ID（fix_versions 空）；torch==2.6.0 → 24/22；torch==2.13.0 → 0/0；langchain-core 0.1.53 → 16 记录/10 ID、1.3.3 → 0；transformers 5.17/5.19 → 0；chromadb 1.5.0 → 5/4（多 PYSEC-2026-311/-3815）（dep §3、owner D-2） | 前三条**现场重跑**：chromadb rc=1 2 条/2 ID；torch 2.6.0 rc=1 24/22；torch 2.13.0 rc=0 0/0。后几条从 `evidence/c-verify/audit-*.json` 复算：core 0.1.53=16/10、1.3.3=0/0、transformers 两只=0/0、chroma 1.5.0=5/4（含 -311/-3815）、chromadb fix_versions=[] | `$PY -m pip_audit --no-deps -r evidence/c-verify/req-chromadb__0.4.24.txt --format=json`（torch 两只同形）；`$PY -c "…glob(c-verify/audit-*.json)…"` | ✅（c-verify 那几只未再打网络，属复算 JSON 非复跑工具） |
| 40 | 候选改动面"tracked 已修改 25 只 / 未跟踪新后端测试 8 只（现量）…复算命令同 §6.4"（gates §7） | 现在跑 §6.4 那两条命令：`git diff --name-only \| wc -l` = **5**（只剩 frontend 5 只）；`git ls-files --others --exclude-standard backend/tests` = **空**。25/8 是**提交前**的状态，已被 §8.1 两笔提交吸收（`git show --stat 5ca3315` = `25 files changed, +2143/-121`；`8c179e7` = `3 files changed, +48/-6`） | `git -C "$C" diff --name-only \| wc -l`；`git -C "$C" ls-files --others --exclude-standard backend/tests`；`git -C "$C" show --stat --oneline 5ca3315` | ❌ 口径过期（数字是旧态真值，但"现量"与所给复算命令现在不再吐它） |
| 41 | 提交面：gates §8.1 记"**两笔**本地提交"（`5ca3315`/`8c179e7`）；h §1/§2b 记勘误落在 `a934fa7` | 分支实为 **3 笔**：`5ca3315`、`8c179e7`、`a934fa7`（HEAD，`1 file changed, +6/-3`，即 ci.yml 注释勘误）；任务书写"最新两笔 8c179e7/5ca3315"也已过期 | `git -C "$C" log --oneline -4`；`git -C "$C" show --stat a934fa7` | ❌ gates §8.1 过期（h 报告一侧是对的） |
| 42 | H §2：候选起点与 master 同头、09-22 那笔是 master 祖先、该 blob 里 `ADMIN_PASSWORD` 2 处皆键名、pickaxe 20+ 笔 | `git rev-parse HEAD~3` = `0b54396…` = 主仓 master HEAD；`merge-base --is-ancestor 817e7d3 master` rc=0；`diff-tree 817e7d3` 含 `dispatch-output/t12-frontend-sweep-20260920/apply_case_domain_gate.py`（该笔共 10+ 文件，报告表格只列 1 只是"筛过"的简写）；`git show 817e7d3:…apply_case_domain_gate.py \| awk '/[Pp]assword/'` 命中 **第 25 行**（`_SECRET_NAME_MARKERS`）与**第 32 行**（docstring），皆键名；`git log -S'ADMIN_PASSWORD' --oneline master` = **25** 笔 | 见左列四条 git 命令 | ✅（pickaxe 25 ∈ "20+"） |
| 43 | 形状普查"28 只待提交文件 / 680,576 字节 / 5 条规则 0 命中 / `control_covers_every_rule=True`"（gates §8.1，证据 `evidence/h/shape-scan-20261010.txt`） | 证据文件是 **256 个 NUL 字节**（`od -c` 全 `\0`），不可用；现态重跑脚本得 `files_scanned=0`（改动面已提交）。我改用自己的重建法复算：取 `5ca3315` 的 25 只 + `8c179e7` 的 3 只 blob，逐只 `git cat-file -s` 求和 = **680,576**，同 5 条正则扫全文 = **0 命中**，正对照 5 条全咬 = `True` | `od -c $R/evidence/h/shape-scan-20261010.txt`；`$PY evidence/shape_scan_staged_set.py "$C"`；自写重建脚本（git show + 同 5 条 RULES） | ✅ 主张为真（但 artifact 损坏、给的方法现在复算不出） |
| 44 | 候选 `backend/.env` 0 字节、`.gitignore:26` 忽略、不进树（gates §5） | `stat` = 0 bytes；`git check-ignore -v backend/.env` ⇒ `.gitignore:26:.env`；`git ls-files backend/.env` = 0 | 见左列 | ✅ |
| 45 | 主仓基线：HEAD `0b54396`、分支 master、tracked 21、暂存 0、未跟踪 34168、分组 dispatch-output 33961 / other_untracked 146 / docs 34 / outputs 23 / 新测试 4（baseline A.1） | 逐项一致：HEAD `0b543960c7172ce1ffea57616952e4d5525190c4`、`master`、21、0、34168；`ownership.json.untracked_counts` 的 by_group 与上述五项逐字相同（我另用 `git ls-files --others` + awk 分组核过总量与 docs/outputs 桶）；tracked 21 只名单 = 后端 15 + 前端 5 + 旧文档残差 1（`evidence/tracked-diff-numstat.txt` 只列 20，缺的那只就是那篇 09-29 计划书——与 baseline "旧文档残差 1" 一致） | `git -C "$M" rev-parse HEAD`；`git -C "$M" diff --name-only \| wc -l`；`git -C "$M" ls-files --others --exclude-standard \| wc -l`；`cat evidence/ownership.json` | ✅ |
| 46 | 接收复验"24 只中 3 只标记，主仓无 MAIN_DRIFT"（gates §6.3） | `recheck generated=2026-10-10T02:17:59 files=24 drift=6` —— 6 是**条目数**（3 只文件 × CAND_DRIFT+CAND_NE_MAIN）；标记文件恰为 `state_machine.py`/`observability.py`/`retrieval.py`，与报告下表三行一致；无任何 `MAIN_DRIFT` | `$PY evidence/verify_received.py "$R" "$C" "$M"` | ✅（"3 只"= 3 个文件，输出里的 6 是条目数，措辞上易误读） |
| 47 | 前端静态门"`npm run lint` rc=0、`tsc --noEmit` rc=0、`vitest run` **9 只文件 50 用例**全过"（gates §5） | 唯一 artifact `evidence/frontend-static.log`：lint rc=0、`rc_tsc=0`、`Test Files 9 passed (9)`、`Tests **83** passed (83)`；9 只测试文件在盘上（我静态数 top-level 用例 = 78，runner 报 83） | `cat $R/evidence/frontend-static.log`（含 ANSI 转义，`grep -a Tests`)；`ls "$C/frontend/tests"`；`grep -cE "^\s*(it\|test)\(" tests/*.test.ts` | ❌ 50≠83（"9 只文件"对） |

---

## §2 指针漂移表

| 原引用（出处） | 现量（我打开的那一行/块） | 判定 |
|---|---|---|
| `rag_chain.py:41-47` `_build_embeddings()`→`HuggingFaceEmbeddings(model_name=…, model_kwargs={"device":"cpu"})`（trust §1.1） | :41 `def _build_embeddings():`；:44 `return HuggingFaceEmbeddings(`；:45 `model_name="BAAI/bge-base-zh-v1.5",`；:46 `model_kwargs={"device": "cpu"},`；:47 `)` | ✅ 对 |
| `rag_chain.py:44` 在 import 期建 embeddings（dep §2） | :44 = `return HuggingFaceEmbeddings(`；模块级单例在 **:109**（`embeddings = QuotaTrackingEmbeddings(_build_embeddings())`，m1-full.log 栈亦指 109） | ✅ 对（:44 是该调用，单例挂在 :109，两处都不冲突） |
| `rag_chain.py:127` `Chroma(persist_directory=CHROMA_DIR, …)`（dep §4、owner D-2） | :126 `vectorstore = Chroma(`；:127 `persist_directory=CHROMA_DIR,`；:128 `embedding_function=embeddings,`；:129 `collection_name=COLLECTION_NAME,` | ✅ 对 |
| `chroma_dir_guard` 模块 docstring 的"调用位置是硬约束"（import_laws docstring 引用） | `scripts/chroma_dir_guard.py:12` = "调用位置是硬约束：只能在 `if __name__ == "__main__"` 路径上调（见各脚本的 `_check_env_contract`）…" | ✅ 对 |
| `import_laws.py`：`PROD_CHROMA_DIR`、`_check_env_contract`、`__main__`（trust §3，无行号） | :35 常量；:262 定义；:278 `if __name__ == "__main__":`；:286-287 例外+调用 | ✅ 对 |
| `docker-compose.yml:32-41`（posthog 遥测注释块，trust §2） | :32 起 "2026-09-04：chromadb 0.4.24 与 posthog 7.45.3 不兼容…"；"本开关 **不能消除该报错**"在 :36；:41 为"保留理由"末行 | ✅ 对 |
| `frontend/next.config.js:4`（`output: "standalone"`、两个 ignore 开关不存在，h §1） | :4 `output: "standalone",`；`grep -n "ignoreDuringBuilds\|ignoreBuildErrors"` = 0 命中 | ✅ 对 |
| `backend/pyproject.toml:8`「unfreeze 必须删掉本 exclude」（gates §6.1） | :8 = `# 若将来 unfreeze，**必须删掉本 exclude** 并接受其 lint 修复。` | ✅ 对 |
| `pyproject.toml:17-21`（3 项 exclude）与 `:16`（状态注释）（baseline A.3） | 指 `evidence/pyproject.before`（解冻前）：:17 `exclude = [`，:18 `"agent/state_machine.py",`，:19 `"prompts.py",`，:20 `"scripts/gate5_judge.py",`，:21 `]`；:16 = "…state_machine/prompts/gate5_judge 仍冻结保留。" 现文件：exclude 移到 **:24-27**（2 项），解冻记录 :12-18 | ✅ 对（历史快照）；现量行号已变，引用时需注明快照 |
| `main.py:2872` / `:3083`（HEAD 的两条 `Row` 注解，dep §10） | `git show HEAD~3:backend/main.py`：:2872 `rows: list[Row[Conversation, str]] = (`、:3083 `rows: list[Row[AuditLog, str \| None]] = (`；候选工作树对应 :2897 / :3108（与本轮 +25 行一致） | ✅ 对 |
| `state_machine.py` "HEAD:37 那条旧语句 `self.state = state.model_copy(...)`"（gates §6.1） | `git show HEAD~3:backend/agent/state_machine.py` :37-39 = `self.state = state.model_copy(` / `update={"status": …}` / `)` | ✅ 对 |
| `manage.py:100` `--host 0.0.0.0` 是 uvicorn 起 app（dep §4） | :99 `proc = subprocess.Popen(`、:100 `[PY, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(port)],` | ✅ 对 |
| `.gitignore:26`（gates §5） | :26 = `.env`；`:26` 行确实忽略 `backend/.env`（`git check-ignore -v` 证实） | ✅ 对 |
| `backend/Dockerfile:34-38` 注释与 `:42` 版本、`:41-48` 防呆断言、`:38`「镜像已同步最新是 2.6.0」（dep §8） | 指**改动前**字节（`evidence/Dockerfile.before`）：:34-38 是"必须钉死版本"那段（对）；「torch 锁在 2.6.0（镜像已同步的最新 cp311+cpu 版，2025-01 发布）」在 **:39**（不是 :38）；`torch==2.6.0+cpu` 在 **:42**（对）；"防呆断言"整块在 **:47-55**（`RUN python -c` 在 :49），不是 :41-48（:41-43 是 install RUN） | ⚠️ `:38`→现量 :39；`:41-48`→现量 :47-55（均只差一行/一块） |
| `observability._ACCOUNT_FIELDS` 加 `category_filter_outcome`（gates §6.2、owner D-4） | `_ACCOUNT_FIELDS` 定义在 observability.py:34；`"category_filter_outcome",` 在 :120（元组内） | ✅ 对 |
| `retrieval.py` 的 `_corpus_advertises_category` / `_CATEGORY_ADVERTISED` / `_docs_advertise_category` / `_note_category_filter_miss(…, outcome=…)`（gates §6.2） | :795 `_CATEGORY_ADVERTISED: dict[str, bool] = {}`；:800 `def _corpus_advertises_category(…):`；:830 `def _docs_advertise_category(…):`；:835 `def _note_category_filter_miss(category, *, stage, outcome):` | ✅ 对 |
| `tests/conftest.py:87`（`import main`；m1-full.log 栈） | m1-full.log 栈显示 `tests\conftest.py:87: import main` | ✅ 对 |
| `test_import_laws_guard.py:95`（断言行，T054232Z 栈） | 栈显示 `tests\test_import_laws_guard.py:95` 即那条 `assert "拒绝执行" in out` | ✅ 对 |

---

## §3 不一致 / 无法复算清单

### 3.1 就是错的（数字/事实）

1. **前端 vitest 用例数 50 ≠ 83**（gates §5）。唯一 artifact 显示 `Tests 83 passed (83)`（9 文件）；9 只文件在盘上可数。50 无处可查，也不能由任何子集复算出来。
2. **覆盖率未覆盖行 1076 ≠ 1079**（gates §8.2 两处引用）。被引的两份日志 TOTAL 行都是 `8866 1079 2726 325 86%`；`86.35%` 与 `Required … reached` 是对的。
3. **"解冻记录 5 行" ≠ 7 行**（gates §6.1）。`diff pyproject.before → 现文件` = +7 行 / −1 行（−1 是删掉的 `"agent/state_machine.py",`）。
4. **`test_backup_data.py`「15 条失败关闭契约」≠ 16**（trust-and-data-drill §2）。`--collect-only` = `16 tests collected`；文件里 `^def test_` 也是 16。这不影响该节结论（不重叠），但数字要改。
5. **`dependency-decision.md` §8 的两处 Dockerfile 行号**（`:38` / `:41-48`）漂到 `:39` / `:47-55`（见 §2）。原文其余数字（2.6.0 注释、assert 块存在）都对。
6. **h §2 表格"那笔新增的文件"**：`git diff-tree --name-only -r 817e7d3` 实际输出 ≥10 只，表格里只写了被 grep 命中的那 1 只；命令形状与结果不并置（§5 的复算行里带 `grep` 才对得上）。属行文不精确，非虚假。

### 3.2 证据不足 / 不可复算（不能说真，也不能说假）

1. **category 变异仪 M2 臂**：`evidence/category-mutants.log` **没有 M2 的结果行**；我按脚本原样重跑该臂 ⇒ 变异后语法错误（`SyntaxError: expected 'except' or 'finally' block`），collection `1 error`，被脚本的 grep 过滤掉。owner-decisions §D-4 的读数「M2 → S2 两只红，红回同一条跨类冒充断言」**用交付的仪器复算不出来**。我用语法正确的同义变异实测是 `4 failed / 5 passed`（含点名两只 S2，另两只也红）⇒ 该判据的方向是真的，但"两只"与交付仪器都要修。
2. **shape-scan 的证据文件损坏**：`evidence/h/shape-scan-20261010.txt` = 256 个 NUL 字节，`.py` 现态重跑 = 0 只文件。主张（28 只 / 680,576B / 0 命中 / 正对照全咬）我用 git blob 重建法独立复算**为真**，但 artifact 与"现量输出"这条引用不可用，需重生成（应把重建口径写进脚本）。
3. **loader-trust 变异仪的两处**：M1 的 `4 errors` 不在 `loader-trust-mutants.log` 里（grep 滤掉非 `N passed/failed` 行），只能靠 `evidence/m1-full.log` 复算为真；日志尾部 `equal=False` 是脚本 bug（把路径当旧 sha 比对）——**基线三只 sha 不变这事我独立复算为真**（`rag_chain.sha-before` 全文 = 现量）。trust §5 "每份日志尾部都有三只 `unchanged=True`"这句对 loader 日志不成立（只有 drill/b45 有）。
4. **HF 模型哈希 12/12**（dep §6、trust §4）：我**未复算**——需要重新出网下载 409 MB 权重才能独立验哈希，超出只读边界与本次时间预算。仅核对 `evidence/bge-model-verification.json`（12 只 status=OK、`all_verified=true`、revision `f03589ce…`、endpoint hf-mirror、`official_host_reachable=false`、`license_tag=mit`）与报告文字一致。
5. **前端三腿（lint/tsc/vitest）我没有现场重跑**：`frontend/` 与 D 单浏览器验收共用树，另一个助手正在其上工作；我只复算了日志与静态计数（见 §1#47）。"tsc 在 Windows 上过"≠"Linux/standalone 过"，报告自己也这么写。
6. **A.4 禁区元数据（app.db 20,205,568B、chroma_db 38 文件等）**：未复算，按任务边界不 touch。

### 3.3 我"没能复算"的项与原因

- HF 模型哈希 12/12（见 §3.2.4）：需重新出网下载 409 MB 权重，超只读边界与时间预算。
- 前端三腿（lint/tsc/vitest）现场重跑（见 §3.2.5）：`frontend/` 与另一个助手的 D 单浏览器验收共用树，避免争用 `.next`/node 资源。
- `reports/local-environment-switch.md`（G 单，15:18 新出现）与 `decisions-needed-20261010.md` 不在本次任务清单，未复核。
- 被复核报告在我复核期间持续改写（见"复核快照"），除上述快照点外的中间版本未逐一复核。

### 3.4 "未做/未跑"清单的诚实性抽查（任务 C）

抽查两条，**均确实没跑过**：

1. `switch_embedding.py` / `rebuild_embeddings.py` 的 CLI 未调用（trust §6、gates §0 E）：全 `evidence/` 里 grep 这两个文件名，0 条运行痕迹；也没有 `导入完成`（import_laws 默认实写模式）字样。
2. `next build` / Linux 镜像 / 容器 smoke 未跑（h §4）：`evidence/` 全域无 `next build` 字样；只有 `frontend-static.log`（lint/tsc/vitest 三腿），没有 build 产物日志。

顺带：gates §0 "D/H/I/J 未跑"里的 **H 已在同一轮内被改成 PASS/BLOCKED**（§0 H 行），§7 尾句"仍开着的：D/H/I/J 未跑"与 §8 已打架——属同一份文档内部两处不同步。

---

## §4 已知限制（我的复核与真第三方差在哪）

1. **同机同人同工具链**：我在同一台机器、用同一个私有解释器（`candidate-envB`）、同一份 `ruff/mypy/pytest/chromadb/sentence-transformers` 版本复算。若"错误"来自工具链本身（例如 pytest 的 `-m "not slow"` 语义、chromadb 0.4.24 的注释行语义），我会得到与他们相同的错误结论——我只是把"同一读数能不能被第二个人重新跑出来"证明到位的水平。
2. **同仓库、只读**：我读的源码/日志/JSON 都是被复核方自己产出的对象；我没有独立实现一个对照版本（例如另写一份 retrieval 去对拍），因此对"实现是否正确"只能复核到"判据会红、sha/AST 不变"这一层。
3. **只读了任务清单列出的 6 份报告 + `evidence/` 对应物**；未读 `docs/` 全量、未读主仓未跟踪的计划书、未读其它轮次报告。
4. **时间快照**：报告在复核中途被继续改写（HEAD 也从 2 笔变 3 笔），我的结论只对"复核快照"表里那几枚 hash 负责；对更晚的版本可能已过期（我文中对 §5 的 50、§8.2 的 1076、§8.1 的"两笔"都标注了现量）。
5. **未出网的项**（HF 哈希、dev 轴完整审计）与**未 touch 的禁区对象**（真实库/缓存）构成"未复算面"，见 §3.3。

---

## 附录：我本轮新增的 A-* 产物（全部在运行根，仓库未被写）

`evidence/A-junit.xml`、`A-pytest.full.log`、`A-egress.full.jsonl/.summary.json`、`A-e2-trust/`（五臂现跑 JSON + markers + 合成目录）、`A-probe_st_trust.out`、`A-drill-mutants.log`、`A-b45-mutants.log`、`A-before-{loader-trust,drill,b45,category}-mutants.log`、`A-audit-runtime.json/.err`、`A-audit-dev.json/.err`、`evidence/.mypy_A/`、`evidence/loader-trust-mutants.log`（我重跑的现版，原文另存 A-before- 备份）。
