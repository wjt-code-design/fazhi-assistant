# 任务工作汇报：B｜引用冒烟判据（2026-09-27）

**派单**：`C:\Users\33393\Desktop\ai-legal-helper\docs\assistant-briefs\next-phase-B-citation-checks-20260927.md`
**负责文件**（派单四件，均已入库）：

- `C:\Users\33393\Desktop\ai-legal-helper\backend\scripts\smoke_citation_fast.py`
- `C:\Users\33393\Desktop\ai-legal-helper\backend\scripts\smoke_citation_full.py`
- `C:\Users\33393\Desktop\ai-legal-helper\backend\tests\test_smoke_citation_assertions.py`（新建）
- `C:\Users\33393\Desktop\ai-legal-helper\CONTRIBUTING.md`

**执行**：本会话（2026-09-27）；读现有用例与生产归一函数 → 先写红测试 → 改两个脚本判据 → 更正文档计数 →
双轴自评审并修复 → 提交。**本汇报文件与 §7 的变异仪器系 Owner 指示补写**（超出派单四文件写区的新建件；
四文件之外的写区纪律未破：未改 `backend/retrieval.py`、语料、模型配置，未碰 A/C/D/E 文件）。
**入库状态（务必先读）**：**本报告与 §7 的变异仪器未入库**——`git status` 下是 `??`
（`dispatch-output/b-citation-checks-report-20260927.md`、`dispatch-output/b-citation-checks-20260927/`），
不随任何提交存在，Owner 2026-09-27 已裁"写进报告即可"。与此相对，**本票四个归属文件均已入库**：
`smoke_citation_fast.py` / `smoke_citation_full.py` / `CONTRIBUTING.md` 随 `ac426c2`（非我所提的那笔快照）、
`backend/tests/test_smoke_citation_assertions.py` 随 `1587478`。**不要把这两件事混起来读成"B 的活没提交"**。

**边界遵守**：两个 smoke 脚本**自始至终未实跑**；未 push、未部署、未动语料/模型/真实库；提交只有一笔且只含
一个新文件（逐次经 Owner 授权）；全程未 `stash`/`clean`/`checkout --`。

## 0. 一页汇总

判据从"条号命中即算召回/引对"收紧为 `(法名, 条号)` **配对**：fast 侧要求**同一条文档**同时满足
法名∈期望集 ∧ 条号∈期望列表（"任中一条"语义保留），full 侧按**显式法名**配对答案里的引用，
且引用形状**先过生产写库时的同一对纯函数**（`output_normalize.expand_law_names` → `expand_citations`）再匹配。
新增回归网 `test_smoke_citation_assertions.py` **23 条**，本机现量 **23 passed / rc=0**；
变异实验 **8 只全 KILLED、SURVIVOR 0**（仪器与读数已落盘，见 §7）；`ruff check` / `ruff format --check` **rc=0**。

**两条必须点名的口径**：

1. **历史那个 23/24 的账不是本票的成绩，也没被本票关闭。** 台账（`docs/assistant-briefs/verification-scope-review-findings-20260927.md`）
   记的是**真实配置下 23/24、rc=1、归因未完成、已归口检索质量票**；§9.11 的 24/24 被限定为"副本 + 离线嵌入"
   口径。我**没有**为凑绿去动 `retrieval.py` 或语料，也**不**把"关掉那条红"写进成果。
2. **旧口径下会转红**：原先靠"别部法律的同名条号"蒙过的正例，收紧后应当转红——那是判据生效，不是回归。
   真实语料上的新判据读数归 **E 助手**统一复验（本汇报只有单测级证据）。

**工作树是活的**：三个已修改文件的**字节**现在躺在一笔**不是我所提**的快照提交 `ac426c2` 里（其提交信息
只把这些文件列在"其他并行会话"名下、没写改了什么）；我的新测试文件当时仍未被跟踪，经 Owner 授权单独提为
`1587478`。详见 §4。**入库状态**：这四个归属文件已入库，而**本报告与 §7 的仪器未入库**（`??` 未跟踪，
Owner 裁"写进报告即可"）——见页首"入库状态"与 §9-4。

## 1. 做了什么（按顺序）

| # | 动作 | 证据 |
|---|---|---|
| 1 | 读两个脚本现有用例/检查逻辑、`retrieval` 的归一函数、`output_normalize` 两个纯函数、`main._post` 与 E5/E8 两个流式出口的时序 | §2 |
| 2 | 先写测试并**亲眼看它红**：首轮 15 failed / 2 passed，红的理由正确（缺 `recall_hit`/`answer_cites`/`citation_pairs`、元组解包 `expected 4, got 3`、`CONTRIBUTING` 写 17 而脚本实际 24）〔红态转录：实现补上后无法事后复现，故此处按当时读数记录〕 | §5 |
| 3 | 改 fast：去掉条号单边判据，改为同条文档 `(source, article)` 联合；法名/条号归一**委托**生产函数（惰性 import，import 期不建 Chroma、不载模型） | §2 |
| 4 | 改 full：12 场景表改成 `(label, question, 法名, [条号写法…])`，两侧循环都走 `answer_cites` | §2 |
| 5 | 更正 `CONTRIBUTING.md` 两条旧计数（24 项 / 12 场景）并写明后者有生成模型调用、有 token 成本 | §3 |
| 6 | 双轴自评审（Standards / Spec 两个子代理）＋逐条本机复验后修复 | §5 |
| 7 | 收口复跑（pytest / ruff / CR 计数 / 邻居用例）＋变异实验 | §3、§7 |
| 8 | 经授权提交**仅**新测试文件一笔 | `1587478`（§4、§8） |

## 2. 新旧判据差异（交付判据项）

**fast（`smoke_citation_fast.py`，非 LLM 门禁，24 项 = 意图 7 + 召回 7 + 引用校验 3 + 复杂度 4 + 自检 3）**

- 旧：召回只看 `metadata["article"]` 是否命中期望条号 ⇒ 别的法律的同名条号也算命中（同一形状的条号在库里被多部法
  共用；评审证据对 7 个样例中的 5 个给出：第四十四条 **87 块/87 部法**、第十九条 97/97、第二十五条 95/95、
  第四十七条 85/85、第八十七条 37/37，见 `docs/assistant-briefs/verification-scope-review-findings-20260927.md`）。
- 新：`recall_hit(docs, expected_sources, expected_articles)` 要求**同一条文档**同时满足两个条件，二者落在
  两条不同文档上不算命中。
- **"任中一条"保留**：期望列表给多条时命中任意一条即算召回；`第X条` 的几种合法写法（中文数字/阿拉伯数字）
  经 `retrieval._normalize_article` 归一。**民法典定金那条（第五百八十六条 / 第五百八十七条）没有被改成
  "必须全中"**。
- 归一不另起一套：法名走 `retrieval._source_key`、条号走 `retrieval._normalize_article`，**惰性 import**
  （否则 import 期就建 Chroma 客户端并加载 BGE，为一次静态检查付模型加载成本）。包装函数特意不叫
  `norm_source`——`retrieval._norm_source` 已有一个同名但更弱的函数（只去前缀、不剥年份括注），同名会误导。

**full（`smoke_citation_full.py`，LLM，12 场景 = 正向 8 + 负向 2 + 轻量 2，有 token 成本）**

- 旧：判答案里有没有出现期望条号 ⇒ 引用别部法律的同号条文照样算过。
- 新：`citation_pairs(answer)` 先跑 `output_normalize.expand_law_names`（补书名号）→ `expand_citations`
  （展开连续省略的续接条号），再按 `《法名》第X条` **邻接**抽取；`answer_cites(answer, 法名, [条号…])`
  要求**法名与条号成对**。散文里隔开、不在续接形状上的裸条号**不补**——与生产同界，门不自己发明"最近书名"
  归属（`output_normalize` 的注释记着那样做会把合同条款号误补成最近的书名）。
- **为什么要自己过那两个函数**：它们在服务器上跑在**流式之后**的写库路径里，而 E5/E8 两个 SSE 出口
  **逐块直发模型原文** ⇒ 门累加到的文本没被补过（*认符号不认行号*：`main._post` 的两个归一调用 vs 两个直发
  出口）。
- 场景法名按派单给定：格式条款/交强险/定金→民法典；违法解除/经济补偿/试用期→劳动合同法；周末加班→劳动法；
  七天退货→消费者权益保护法。**只判断引用组合**，不加主观法律评价、不加新依赖（只依赖 stdlib + 脚本内自带）。
- 条号形状与法名归一各留一份**窄口径自带副本**，并用绊线钉住**不许与生产分叉**（`retrieval._ART_FULL_RE.pattern`
  与 `retrieval._source_key`），而不是去 import 那个会拉模型的模块。

**CONTRIBUTING.md**：第 4 条改 `24 项非 LLM 门禁 = 意图 7 + 召回 7 + 引用校验 3 + 复杂度 4 + 自检 3；召回判据是
法名×条号 配对`；第 5 条改 `12 场景 = 正向 8 + 负向 2 + 轻量 2；含答案生成模型调用，有 token 成本`。
**旧运行成绩一字未改**（派单第 3 条明确要求）。

## 3. 命令与退出码（现量，本机 venv Python 3.11.0）

| # | 命令（`backend/` 下） | 读数 | 退出码 |
|---|---|---|---|
| 1 | `venv/Scripts/python.exe -m pytest tests/test_smoke_citation_assertions.py -q` | 23 passed（12.75s，提交之后复跑） | **0** |
| 2 | 同上 `--collect-only -q` | `23 tests collected in 0.64s` | 0 |
| 3 | `pytest tests/test_qa_citation_gate_symmetry.py tests/test_smoke_citation_assertions.py -q` | 30 passed（13.12s） | **0** |
| 4 | `venv/Scripts/python.exe -m ruff check scripts/smoke_citation_fast.py scripts/smoke_citation_full.py tests/test_smoke_citation_assertions.py` | `All checks passed!` | **0** |
| 5 | `… -m ruff format --check`（同上三文件） | `3 files already formatted` | **0** |
| 6 | 四个文件逐个 `tr -dc '\r' \| wc -c` | 全部 **0**（无 CRLF 污染） | 0 |

**踩坑记录（供下一位复验者）**：`python` 在 PATH 上**不是**项目 venv；用它跑会在 `tests/conftest.py`
报 `ModuleNotFoundError: No module named 'chromadb'`、**rc=4**。复验必须用 `backend/venv/Scripts/python.exe`。
两个 smoke 脚本本身**未跑过**（见页首边界）。

## 4. 归属事实：三个文件的改动躺在一笔不是我所提的提交里

- `ac426c2 chore(工作区快照): 并入并行会话的未提交修改（T1/T2 版本判据 + T5 导入类型门 + 文档/前端/证据）`
  —— 23 files changed, +1187/−173；**在我的汇报过程中**由另一会话生成。它的提交信息把我这三个文件列在
  "其他并行会话"名下（`scripts/smoke_citation_fast.py`、`smoke_citation_full.py`、`CONTRIBUTING.md`），
  但**没写改了什么**：引用门禁/`(法名, 条号)` 配对一个字没提。净改动行数（`git show --numstat`）：
  `smoke_citation_fast.py` +55/−15、`smoke_citation_full.py` +94/−31、`CONTRIBUTING.md` +3/−2。
- 校验过是**同一份字节**：`git show HEAD:<file> | sha256sum` 与工作树 sha256 逐字相等（§8 表）。
- 该提交**未上任何远端**：`git branch -r --contains ac426c2 | wc -l` = **0**（所以技术上能 amend，但为一句提交
  信息去重写别人的历史，爆炸半径远大于收益；本仓做法是**就地标注、不回填**）。
- 我的新测试文件当时**未进任何提交**（一次 `git clean -fd` 即不可恢复）⇒ 经 Owner 授权提为
  `1587478 test(citation): 补上 (法名, 条号) 联合判据的回归网`，1 file changed, +343，未 push。
- 冗余备份（防丢）：`.workbuddy/evidence/test_smoke_citation_assertions.py.bak`（sha256 与原文件相等，
  `.gitignore:85` 忽略）＋ 同目录 `b-citation-untracked-state.txt` 记四个哈希与恢复命令。

## 5. 自评审与修复（`code-review` 双轴，固定点 `HEAD` = 当时的 `7eda4bb`）

Standards 轴（子代理）7 条、Spec 轴（子代理）4 组，**逐条本机复验后才采信**；采纳并修复的要点：

1. **`citation_pairs` 之前漏了前置归一**（真缺陷，已按 §2 修）：先前只按 `《法名》第X条` 找，模型常写的裸法名
   `劳动合同法第八十七条` 会被漏 ⇒ 假红。修后测试 `test_citation_pairs_accepts_bare_law_name_without_book_marks`
   与 `…expand_continuous_article_list` 钉住。
2. **接线零覆盖**（真缺陷，已修）：原测试只测纯函数，`main()` 里判据接没接**测不到** ⇒ 判据可以被整排绕过而全绿。
   加 4 条 AST 绊线（含"两个出口各调一次 `answer_cites`"的计数），并用 §7 的 S7 变异证明它**真的会红**。
3. **与生产的分叉无人钉**（已修）：法名归一与条号形状的自带副本各加一条漂移绊线（对照 `retrieval._source_key`、
   `retrieval._ART_FULL_RE.pattern`），S5/S6 变异证明确实会红。
4. **措辞过宽**（已改写）：注释/文档里凡"生产也这样"的句子改为可核对的具体符号。
5. **一处建议被驳回**：给 fast 侧用例打 `@pytest.mark.slow`——那会把它们移出 CI，而它们正是本票要求的门禁，
   驳回理由当场说明。

**一处我自己的错，就地更正**：我先前口头汇报说测试是"24 passed"，**实际是 23 条**
（作者数 = `--collect-only` 数 = passed 数，三方一致）。根因是把 **fast 脚本的 24 个门禁项**与**测试条数**
串了轴；`CONTRIBUTING.md` 里的 24 是对的（那是脚本项数）。

## 6. 未决事项台账（都不在我写区，需 Owner 裁或派单）

| # | 事项 | 我的建议 | 状态 |
|---|---|---|---|
| D1 | `ac426c2` 的提交信息只把三个文件列在"其他并行会话"名下、没写改了什么，将来查"判据是谁改的"会查不到 | **在台账补一行归属说明**（`ac426c2` 含 B 的 fast/full/CONTRIBUTING 三处改动及其净行数）；**不要 amend** | 待裁 |
| D2 | `docs/ARCHITECTURE.md:107`（`smoke_citation_fast.py`（**17 项**，非 LLM，pre-commit/CI））、`:109`（`smoke_citation_full.py`（**10 场景**…））、`docs/capability-matrix.md:29`（`smoke_citation_fast 17 项`）仍是旧计数 | **三处同批改**（同一个计数事实的三个副本，拆给两个人会再造不一致）；建议派给 A（文档归属）。`ac426c2` 没碰它们 | 待派 |
| D3 | 新判据在**真实语料**上的读数 | 归 **E** 统一复验；并请 E 注意：旧口径靠别部法律同名条号蒙过的正例转红 = 判据生效，不是回归 | 已归 E |
| D4 | `CONTRIBUTING.md` 里"24 项"（脚本项数）与测试文件的"23 条"（用例数）并存，下一位容易串轴（我就是这么错的） | 可在第 4 条那句后面加半句区分（**一行改动**，我方文件）；需要你一个字授权我就改 | 待裁 |

## 7. 变异仪器（可复核）

- 驱动：`C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\b-citation-checks-20260927\run_mutations.py`
- 读数：同目录 `mutation-readings.txt`
- 用法：仓库根下 `backend\venv\Scripts\python.exe dispatch-output\b-citation-checks-20260927\run_mutations.py`

做法：先取字节 → 锚点必须唯一/够数（否则**拒绝执行并计入未杀**，绝不带病继续）→ 跑目标用例文件 →
**还原原始字节并核对 sha256**（不符即非零退出）。

| 变异 | 打红的断言（读数文件里逐条可查） | 结果 |
|---|---|---|
| S1 fast 判据退回只看条号 | **4 failed**：`…rejects_right_article_from_wrong_law`、`…rejects_pair_split_across_two_docs`、`…survives_docs_without_source_or_article`、`…defaults_follow_production_spelling_rules` | KILLED |
| S2 full 判定对法名失明 | 1 failed：`test_answer_cites_rejects_right_article_from_wrong_law` | KILLED |
| S3 去掉 `expand_law_names` | 1 failed：`test_citation_pairs_accepts_bare_law_name_without_book_marks` | KILLED |
| S4 去掉 `expand_citations` | 1 failed：`test_citation_pairs_expands_continuous_article_list` | KILLED |
| S5 fast 法名归一退化为恒等 | **2 failed**：`…defaults_delegate_to_retrieval_instead_of_a_second_copy`、`…defaults_follow_production_spelling_rules` | KILLED |
| S6 full 条号形状收窄（丢 〇○） | 1 failed：`test_full_citation_pattern_cannot_drift_from_retrieval` | KILLED |
| S7 拆掉一处接线 | 1 failed：`test_full_main_is_wired_to_the_pair_judge` | KILLED |
| S8 CONTRIBUTING 计数漂回 17 | 1 failed：`test_gate_item_counts_match_contributing` | KILLED |

汇总 **KILLED 8 / SURVIVED 0 / 共 8**，驱动 rc=0，还原后三个文件 sha256 与改前逐字相符、工作树干净。
（本会话早前还报过一次"13/13 变异被杀"，那个驱动**没落盘**、数字不可复核 ⇒ 已被本节这份可复核读数取代。）

## 8. 哈希（口径：内容 sha256；**不是** git blob 的 sha1，两者不同轴）

| 文件 | 改前（`7eda4bb` 版本） | 改后 = 工作树 = `HEAD:<path>` |
|---|---|---|
| `backend/scripts/smoke_citation_fast.py` | `e24ef82863be…` | `d3735bb6d98a…` |
| `backend/scripts/smoke_citation_full.py` | `243c90a6e2e8…` | `7b10b968f665…` |
| `CONTRIBUTING.md` | `e0d795829029…` | `47d768f53f77…` |
| `backend/tests/test_smoke_citation_assertions.py` | （不存在） | `7b34163d43f8…` |

改前三个哈希的判别命令：`git show 7eda4bb:<path> | sha256sum`（与 Owner 给我的三个"改前"值逐字相同，
⇒ 口径确认、diff 全部出自本会话）。

## 9. 补记（报告落盘后的自查与工作树变动，逐条现量）

1. **读数文件曾以 CRLF 落盘**：驱动用 `Path.write_text` 写 `mutation-readings.txt`，在 Windows 上默认把 LF
   翻成 CRLF（CR=35）。已把驱动三处写入钉成 `newline="\n"` 并字节修回 LF ⇒ 现驱动与读数 **CR=0**。
2. **修上一条时我把驱动改坏过**：用字节级替换插 `newline="\n"` 时转义被折叠成真换行，`ast.parse` 当场报
   `SyntaxError: unterminated string literal`。它已被编辑器修复，并**整跑一遍**复验：`parse OK`、8/8 KILLED、
   还原校验三条 sha256 全对、工作树干净。**教训与 §3 第 6 行同源**：这类改动别用字节级 sed 式替换。
3. **`HEAD` 又前进了一笔**：报告落盘后 `HEAD` = `9557dfb docs+test(T5): 复审结果与"提交/未入库"清单折进
   §9.11a，并随票入库变异仪器与读数`（并行会话）。已核 `git show --stat 9557dfb` **未碰本票四个文件**，
   且四个文件的 sha256 仍与 `HEAD:<path>` 逐字相等（§8 表口径不变）。
4. **本报告与 §7 仪器均未入库，且 Owner 2026-09-27 已裁"写进报告即可"、不单独提交**：
   `git status` 下 `?? dispatch-output/b-citation-checks-report-20260927.md` 与
   `?? dispatch-output/b-citation-checks-20260927/` ⇒ 本报告**自身就是交付载体**（与
   `dispatch-output/a-docs-t7-report-20260927.md` 同态：助手报告在 dispatch-output 下保持未跟踪，
   由 Owner 决定后续是否随台账收纳）。因此本报告的全部证据（含 §7 的仪器与读数）以**本目录就地可读**为准，
   不依赖任何提交。
