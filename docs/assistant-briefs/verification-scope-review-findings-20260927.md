# 测试覆盖与验证边界复核报告（T1/T2/S0-c）— 2026-09-27

派单：`C:\Users\33393\Desktop\ai-legal-helper\docs\assistant-briefs\verification-scope-review.md`
复核人：ZCode 会话（只读复核）；执行时间 2026-09-27 下午（本机；与同机 Qoder 会话的并行复核
15:58–16:32 时间窗重叠，见 §4 对账）。

## 0. 一页汇总

**结论**：四个负责测试文件对 T1/T2 与 S0-c 窄修复的回归捕获面**充分**——定向两次实跑
`60 passed / 1 deselected / rc=0`；关键判据的 watch-it-fail 由并行评审的旧码副本 20 红闭环（引用，见 §4）。
发现 **3 条必要缺口**（各配最小测试建议）＋ **3 处文档计数漂移**（fast 门禁项数 ×2、full 门禁场景数 ×1）；
引用冒烟结果的适用范围**核对通过**（§9.9/§9.11 引用诚实，无需更正）。
另承认一项复核盲区：并行评审 §2 中-1（无生效日重传静默并存 + 端点层零测试）我未点到——
其行为定性归 Owner，但"端点层零覆盖"属我的检视面，记为漏检。

| # | 严重度 | 一句话 | 最小处置 |
|---|---|---|---|
| 1 | 中 | 两道引用冒烟门**都只验条号不验法名**（fast 召回层、full 答案层）；主集合内 5 个样例条号被 37–97 部法共用 | 断言改 (source, article) 联合匹配；数据已在用例表 |
| 2 | 中 | "安全时删旧块"的端到端覆盖**只有被 CI 排除的 slow 用例**；删旧接线回归则 CI 全绿 | 复用现成夹具补一条非 slow 同版本重传用例 |
| 3 | 低 | `import_laws.py` 的 seed 跳过分支**零测试**（今天死码，未来重建语料可触发） | tmp_collection 种 seed 块 + dry-run 断言跳过与零写入 |

**被复核的快照**（与并行评审 §0 的 mtime 逐分钟一致：law_versions 15:06、两测试 15:07/15:10、
knowledge_service/import_laws 15:09；工作区未提交）。

## 1. 覆盖充分的关键判据（派单七项重点逐项）

| 重点 | 判据本体 | 测试钉点 |
|---|---|---|
| 完整正文误删 | `_same_article_body` 只许元数据已知前缀差异（`law_versions.py:25-38`） | 截断不删 `test_law_versions.py:77`、空日期不绕过 :85、空版本 ID 不绕过 :96、派生 ID+无日期不删不同正文 :108、未知前缀不删 :133、互不包含必须进并存桶 :202、未传正文 fail-safe :233、`chroma:document` 回退 :240；形状不变量 `replaceable == same_version + legacy_undated` :183 |
| 空日期/ID | `same_version` 分支要求生效日非空（`law_versions.py:133-139`） | `test_new_effective_date_creates_new_version` :18 + 上行 :85/:96/:108 |
| seed | 判据层 origin!="seed" 双闸 | 同 version_id 不删 seed `:123`、origin=seed 不进遗留桶 `:209`；脚本层 `_seed_conflict` 无覆盖 ⇒ 缺口 3 |
| 日期区间与批内冲突 | `_periods_do_not_overlap`（`law_versions.py:41-52`，严格 `<`） | 单侧界值即可并存 :144/:158、五种 `old_end` 参数化含非法日期 :171；端点腿两趟先判后写 :235、批内重复/重叠写前阻断（炸桩+数条目双手）preflight:263、放行对照 :282、互不包含整批不写入 :293、防空枪对照 :316 |
| 写入路径保留旧块 | 先写后删（`knowledge_service.py:212-237`） | `test_writer_keeps_complete_legacy_article_when_new_text_is_truncated`（`test_import_laws_preflight.py:207`，断言 :223-225 旧 id 在、共 2 块）；"删旧 happy path"仅 slow ⇒ 缺口 2 |
| 设置值异常恢复 | `_ask` try/finally 恢复 `allow_client_law_as_of`（`test_time_unverified_note.py:139-160`） | 端到端恢复 `:175`；§9.11 窄修复第 3 条已在当前实现落地 |
| S0-c 判据与逐出口 | `_time_unverified_hit` 全仓唯一（`main.py:1089-1102`） | 两条件缺一不可 `:166`；出口清单绑 `gate_exit_registry.EXITS` + PASS 格必有真用例/空格必写理由/假指针四条元测试 :356-396；E1/E2 的"不适用"算出来且各有对照 :300/:326；措辞不撞自检标记 :181 |
| 附加 | 预检不私藏第二份判据 | 符号缺席断言 `test_import_laws_preflight.py:166`；`_load_script` 还原 cwd :40-50（防 `os.chdir` 污染同批） |

## 2. 三条必要缺口

### 缺口 1（中）：两道引用冒烟门都只验条号不验法名

- **fast**：`smoke_citation_fast.py:69` 把 `expected_sources` 解析成 `_es` 后从未使用，:70-73 只断言
  `any(a in arts for a in ea)`——召回错法名的同条号块照样绿。
- **full**：`smoke_citation_full.py:110` 的 POSITIVE 断言 `any(e in c for e in expects)` 同样只看回答文本含条号。
- **竞争面（主集合 `legal_provisions_cos` 口径，2026-09-27 只读实测）**：第四十四条 87 块/87 部法、
  第十九条 97/97、第二十五条 95/95、第四十七条 85/85、第八十七条 37/37——7 个样例中 5 个暴露；
  第五百八十六/八十七条与第一千二百一十三条各 1 块/1 部法（今天结构性安全）。
  与 §9.9 独立读数"87 个 competing"精确收敛。
- **最小建议**：fast 改 `any(d.metadata.get("source") in es and d.metadata.get("article") in ea for d in docs)`；
  full 的期望表补法名并在回答断言中联合匹配。数据已在用例表，各改一处循环。
- **附带文档漂移（三处，同一主题）**：`CONTRIBUTING.md:10`"17 项"→实际 24（7 意图+7 召回+3 引用校验+4 复杂度+3 自检，
  本会话逐段数过）；`CONTRIBUTING.md:11`"10 场景"→实际 12（8 正向+2 负向+2 轻量）；`capability-matrix.md:29`"17 项"→24。

### 缺口 2（中）："安全时删旧块"无 CI 可见覆盖

- 唯一端到端证据是 `@pytest.mark.slow` 的并发用例（`test_knowledge_service.py:31-32`），CI 按
  `CONTRIBUTING.md:16` 以 `-m "not slow"` 排除；CI 可见的只有"不安全时保留"（preflight:207）与
  plan 级 replaceable（`test_law_versions.py:183`）。`add_text` 消费 `.replaceable` 再删除的接线
  （`knowledge_service.py:212-237`，含删除失败吞异常 :234-237）若回归，CI 全绿。
- 本会话两次实跑该 slow 用例 `1 passed / rc=0` ⇒ 行为当前正确，缺的是门禁可见性。
- **最小建议**：复用 preflight 的 `tmp_collection` 夹具补一条非 slow 用例——同
  (source, article, version_id, effective_from) 两次 `add_text` 不同正文，断言旧块 id 消失、块数回到单次写入基线。

### 缺口 3（低）：`import_laws.py` 的 seed 跳过分支零覆盖

- `_seed_conflict` 与跳过打印/计数（`import_laws.py:121-134`、:182-185）在四个负责测试文件里无用例。
- 今天死码（全库 `origin='seed'` 0 条，本会话一手实测；并行评审 §4-6 同读数），但分支可由未来语料重建触发；
  恒 True 会挡掉全部导入、恒 False 静默，均不可见。
- **最小建议**：tmp_collection 种一条 origin="seed" 同法同条块，`--dry-run` 断言输出"跳过（与种子冲突…）"
  且集合条目数不变，约 10 行。

## 3. 引用冒烟结果的适用范围核对

- **核对通过**：§9.9（`progress-handoff-report-20260925.md:656-664`）记录真实配置 23/24、rc=1、归因未完成、
  归口检索质量票；§9.11（:747-753）的 24/24 明确限定"副本+离线嵌入口径，不能关闭原配置的 23/24，
  也不能宣称召回已修复"。`docs/superpowers/plans/2026-09-27-post-review-closeout.md:54` 已把
  "隔离副本/离线 embedding/rerank 关闭"成文为纪律。其余 docs 提及的冒烟均为并发/限流主题，无陈旧引用。
- **新发现**：上节三处计数漂移；其中"10 vs 12 场景"本会话裁定——`smoke_citation_full.py` 三个用例表
  （:65-91）合计 12 项，`BENCHMARK.md:58` 对、`CONTRIBUTING.md:11` 错。
- 本轮**未运行**任何冒烟脚本：fast 无隔离模式（chdir+读真实 .env+读真实索引），有并行会话在场；
  其口径以静态核对 + §9.11 副本读数为准。

## 4. 与并行评审的对账（`version-safety-review-findings-20260927.md`，同快照）

- **互证**：其快照 mtime 与我 `stat` 逐分钟一致；10266 块、seed=0、rerank 边界（本机 `rerank_enabled=True`，
  离线读数不外推）全部吻合；其收口读数（chroma.sqlite3 mtime 2026-09-21 02:06:44）与我一致。
- **它补上了我给不了的**：watch-it-fail——对 HEAD 旧码副本树跑出 `20 failed / 19 passed`，红名单与 §1
  点名的判据用例一一对应，且为断言级红（取数命令在其 §5，入库产物 `redcheck_lines.txt`）。
  **我未复跑**，证据等级标注为"并行评审实测、命令可复现"。
- **它多抓的**：中-1 无生效日重传静默并存（端点层零测试——我的漏检，见 §0）；低-2 写侧 `except Exception`
  无日志；低-3 `ReplacementPlan` 理由注释被换；低-4 批内兼容不播报。
- **我多抓的**：两道冒烟门的法名断言缺口（其 §1.2 是手工 A/B 对照，未列为脚本断言缺口）；
  capability-matrix 第二处"17 项"；语料在索引文件里存 4 份的计数陷阱（§6）；full 门禁 10/12 场景裁定。

## 5. 运行读数与复现路径

| 命令（在 `backend/` 下） | 结果 |
|---|---|
| `venv/Scripts/python.exe -B -m pytest tests/test_law_versions.py tests/test_import_laws_preflight.py tests/test_knowledge_service.py tests/test_time_unverified_note.py -q -m "not slow"` | 两次实跑均 `60 passed, 1 deselected`，`MAIN_PYTEST_RC=0`（35.74s / 36.46s） |
| `venv/Scripts/python.exe -B -m pytest "tests/test_knowledge_service.py::test_concurrent_add_text_idempotent" -q` | 两次实跑均 `1 passed`，`SLOW_PYTEST_RC=0`（18.45s / 23.15s） |
| 语料普查：`sqlite3` 只读打开 `backend/chroma_db/chroma.sqlite3`（`mode=ro`），join `embeddings→segments→collections` 按 `legal_provisions_cos` 界定 | §2 竞争面数字 + §6 全库账目 |

隔离条件：`conftest.py:23/31-32/39-40` 无条件把 `QUOTA_DB`/`DATABASE_URL`/`CHROMA_DIR` 指向按 PID
命名的临时路径（并行会话各得各的）；JWT/LLM 哑值、`RERANK_ENABLED=false`、配额 0（:9-17）；
preflight 用例另自建 tmp_path PersistentClient（:65-80）。运行后实测 `backend/app.db`（mtime 2026-09-19
00:28:25）、`backend/chroma_db/chroma.sqlite3`（2026-09-21 02:06:44）、`backend/data/quota_used.sqlite`
（2026-09-19 00:12:51）均未被触碰。

## 6. 数字更正台账（请勿引用旧数）

第一轮交付曾按"未按集合界定"的查询报过一批语料数字，**全部作废**，原因与更正：

| 旧数（作废） | 更正后（cos 口径） | 原因 |
|---|---|---|
| 第四十四条 348 块/87 法 | **87 块/87 部法** | 该 sqlite 文件内同一语料存了 4 份：现役 cos 10266 + te4 实验 10266 + 20532 个**无 segment 的孤儿向量**（=2 份陈旧全量拷贝，其 (source,article) 对与现役完全相同的 10236 组）。未 join 集合表的块数恰为真值 4 倍（348=87×4、388=97×4、380=95×4、340=85×4、148=37×4） |
| 第十九/二十五/四十七/八十七条 388/380/340/148 | 97/95/85/37 | 同上 |
| "41064 块" | 块数口径无效；41364 = 10266(cos) + 10266(te4) + 279(qa_pairs) + 21(qa_pairs_te4) + 20532(孤儿)，闭合 | 同上 |
| "10236 个 (source,article) 对" | **有效**（作为去重条文对数；并行评审 §4-1 同读数：10266 块 − 10236 对 = 30，与 5 组多片段 35 块闭合） | 保留 |

## 7. 边界自证

- **零文件编辑**：本轮只新增本报告；其余全部为读（Read/grep/stat）、只读 sqlite（`mode=ro`）、
  定向 pytest（PID 私有临时库）。未调真实模型/云重排，未写真实库/索引/配额库，未部署推送。
- 命令清单与原始输出见本会话记录；关键读数均有两次独立实跑或与并行评审互证。

## 8. 限制（诚实标注）

1. "判据能抓回归"的证据等级 = 断言强度分析（本会话全文读）+ 两次全绿实跑 + 并行评审 redcheck 20 红
   （**引用未复跑**）。仓库既有变异仪器绑定旧实现（§9.11:759 自述），本轮未重跑——需要 kill-rate 级证据
   应在集成会话重跑变异驱动，不得引用 §9.9 的旧"全杀"数字。
2. 语料统计为 2026-09-27 时点读数；真实入库窗口开启后必须重测。
3. mypy 对 `scripts/` 的排除、本机依赖越区间（uvicorn/pypdf）等门禁边界沿 §9.11/并行评审自述，本轮未测。
4. 超范围观察（不动手，留给库维护票）：真实 `chroma_db` 文件含 te4 实验集合与 20532 个无 segment 死向量，
   是一切"未按集合界定的统计"的坑；清理需 Owner 单独授权。
