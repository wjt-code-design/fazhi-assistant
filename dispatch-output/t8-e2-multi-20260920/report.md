# T8 · E2 出口「多选题只给一个正确项却能零 token 直返」缺口调查

> **只读调查卡**。唯一写集：`dispatch-output/t8-e2-multi-20260920/`（`report.md`、`probe.json`）。
> 未改动 `backend/**` 任何文件；未写真实语料；未执行任何 git 写命令。

## 基线锚定（开工实测，非抄文档）

- **开工 HEAD**：`2a48f3ec0f4b906302755504131c5da252e38f77`（与 `baseline.json` 的 `head`=23:41 重锚值一致）
- **`sha256(backend/main.py)`**：`4807cc9e4b9dd14334b754f63dea53ff9c1b669157647b93de21bab5be4cbe5f`
  （与 `baseline.json` 的 `backend/main.py` 哈希**逐字一致** ⇒ 读的是票 I 已收口、含第四道护栏的版本，未漂移）
- **`sha256(backend/gate_exit_registry.py)`**：`a449396853254a4c34a16eba02764120024dff4e73e3cd026ce16b7198f0e4fb`（与 baseline 一致）
- **票 I 第四道护栏已存在（本卡须注明的事实）**：`_qa_direct_return`（`backend/main.py:1127-1134`）确有
  `law_as_of_basis` 分水岭判定；登记表 E2「版本绊线」格 = `PASS`，原文点名「票 I 的 I-2(a) 已修 … 加**第四**道护栏」。
  **它与多选缺口正交**：版本绊线判「旧法当新法答」（时间/版本适用性），多选完整性判「答案是否列全正确项」（内容完整性），
  两个维度互不相干——第四道护栏的存在**不关闭**多选缺口。详见 §结论。

---

## ① 结论（一句话）

E2 出口**确实存在**「多选题只给一个正确项却能零 token 直返」的结构性缺口——`_qa_direct_return` 全程不调用
`quality.multi_incomplete`（已用合成探针实测证明：同一输入 `multi_incomplete` 判 True、E2 仍原样直返）；
但**不建议照搬票 J 在 E2 加 `multi_incomplete` 判定**：它会削弱 E2「零 token 直返」卖点，且对**当前语料零效果**
（`multi_incomplete` 全量 279 条命中 0，因语料题干无「多选/哪些」关键词 ⇒ `question_type`="unknown" 恒 False），
加了等于登记表最忌的「假接线 `[PL#14]`」。要真补，须先扩 `question_type` 召回并修 `_answer_declared_correct` 的
markdown 解析（正交任务、动共享模块），否则是空门。语料侧真实会命中条数**不可靠量化**（现有抽取器双重失敏）。

---

## ② 产物（绝对路径 + 关键读数）

| 产物 | 路径 | 关键读数 |
|---|---|---|
| 探针脚本 | `dispatch-output/t8-e2-multi-20260920/probe_t8.py` | 只读；读 `qa_pairs` 集合 + 调 `_qa_direct_return`/`multi_incomplete` |
| 探针主产物 | `dispatch-output/t8-e2-multi-20260920/probe.json` | 见下「探针读数」 |
| 探针 stdout | `dispatch-output/t8-e2-multi-20260920/probe.stdout.txt` | `PROBE_DONE` |
| 语料抽样核查 | `dispatch-output/t8-e2-multi-20260920/investigate.py` + `investigate.json` | 48 条残留疑似下界（含抽取器漏识） |
| 本报告 | `dispatch-output/t8-e2-multi-20260920/report.md` | — |

**探针读数（probe.json，实测）**
- 代码路径探针：`multi_incomplete_on_same_input=true`；`_qa_direct_return_returned_answer=true`；
  `returned_exactly_single_answer=true` ⇒ **E2 确实不查多选完整性即直返**。
- 语料清点（`qa_pairs`，集合名含 `qa_pairs`、条数=279，守卫通过）：
  - `n_total=279`
  - `n_multi_keyword=38`（题干含 多选/哪些/正确的有/符合的有）
  - `n_has_options=168`（题面带 A–D 选项标号，即选择题；登记表 E2 引的 probe-A 数为 166，口径微差，同量级）
  - `n_declared_one=53`（答案被 `_answer_declared_correct` 判为只声明 1 个正确项）
  - `n_mi_true_keyword=0`（`multi_incomplete(question,answer)` 对**全量 279 条**命中 0）
  - `n_multi_choice_and_single_correct=52`（选择题 且 答案只声明 1 正确项，宽松口径）
- 鲁棒性复核：`strict_one=0`（严格「X项判断：正确」格式全量 0）；`loose_only=52`（52 条全部来自结论/hedge 启发式）。
- 抽样核查（investigate.json）：`n_choice=168`，`n_single_decl=52`，`n_all_option_hit=7`（题目带「以上说法均正确」类全选项），
  `n_all_option_and_declared_it=4`（答案恰点中全选项=声明全对，非缺口），`n_residual_gap_lower_bound=48`。

---

## ③ 判据对照（逐条；满足 / 不满足）

**判据① 实测「多选题 + 语料只声明一个正确项」能不能直返**
- *满足*。合成探针：构造 `pre={"rewritten":多选题,"qa_hit":{score:0.99, law_as_of_basis:"2026-08-23", fingerprint:"", evidence:"", answer:只声明1正确项}}`，
  调 `main._qa_direct_return(pre, law_as_of=None)` ⇒ 返回该答案（`returned_exactly_single_answer=true`），而 `quality.multi_incomplete(同输入)=true`。
  证明 E2 的直返路径**完全不调用** `multi_incomplete`，多选题只给一个正确项可零 token 直返。
  （注：`fingerprint:""`/`evidence:""`/`law_as_of=None` 是让三道既有护栏 + 第四道护栏都不触发，纯测「多选完整性」这一维；三道既有护栏与第四道护栏一个字未动，符合「不许改 E2 三道既有护栏」约束。）

**判据② 量化属「会命中」还是「理论可达」+ 给数**
- *部分满足 / 受工具限制*。给数：**语料选择题 168 条；其中答案只声明 1 个正确项（宽松口径）52 条**；
  但 `multi_incomplete` 对全量 279 条命中 **0**，`strict_one=0`、`loose_only=52`。
- 分类：**代码路径 = 会命中（确定）；语料真实暴露 = 理论可达（真实会命中条数不可量化）**。
  理由：现有 `multi_incomplete`+`_answer_declared_correct` 对**本语料双重失敏**——
  (a) 语料题干用「下列说法正确的是？」措辞，`question_type` 判为 `unknown`（无「多选/哪些」关键词）⇒ `multi_incomplete` 直接 False；
  (b) 抽取器对语料答案的 markdown 逐项判断格式（「### 选项A\n【判断】正确」）漏识，把多正确项答案塌缩成 1（抽样见劳动争议题答案逐项判 A/B/C 正确却只抽到 B、毒品犯罪题 A/B 正确却只抽到 A）。
  故 52 条多为**抽取器漏识**，不能当「真·只给一个正确项」的实计数；真值需人工逐条核验，无法用现有工具可靠给出。
  结论：缺口在语料侧属**理论可达**——代码确定允许直返，但能否「会命中」取决于语料里有多少题是「真多选 + 答案真只给一个正确项」，
  而这无法用复用函数量化；且即便补判定，按当前语料 `multi_incomplete` 也恒 False（见 ③权衡）。

**判据③ 给「要不要补判定」的结论 + 写清权衡**
- *满足（含权衡）*。结论：**不建议在 E2 直接补 `multi_incomplete` 判定**。权衡如下：
  - **卖点权衡**：E2 的卖点恰是「零 token 直返」——其「自检/引用校验/多选完整性」三格在登记表均为 `DISABLED`，
    与票 C/E1 已裁「读侧不加判定」一致。`multi_incomplete` 虽是零 LLM 纯函数（成本极小），但加判定即破坏该特性的定义纯度。
  - **有效性权衡（更关键）**：直接搬票 J 的 `multi_incomplete` 到 E2，**对当前语料零效果**——全量 279 条命中 0
    （关键词缺失 + 抽取器漏识）。加了是一道**假接线**（`[PL#14]` 形态：接了却永远不命中），比维持 `DISABLED` 更危险，
    因为它给人「已防护」的错觉。要让它真生效，须**先**扩 `question_type` 召回（「下列说法正确的是？」也认成多选）并修
    `_answer_declared_correct` 的 markdown 解析——那是正交任务，动 `query_understand`/`multi_extract` 共享模块，
    会波及评测基线与票 J 已对齐的轻量出口 E7/E16，**超本卡射程**。
  - **正交性**：票 I 第四道护栏（版本绊线）与多选完整性正交，不关闭此缺口（见 §基线锚定）。
  - **推荐处置**：维持 E2「多选完整性 = DISABLED」，把「扩 detector 召回 + 评估是否补判定」登记为独立的 `GAP-TODO`
    （正交任务）；若 Owner 坚持要补，最小干净路径是「接受零 token 卖点小幅削弱 + 在 E2 调 `multi_incomplete`」且**必须先修 detector 召回**，否则空门。

---

## ④ 我复跑的命令（照抄可跑）

```bash
export PATH=/c/Users/33393/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH
cd /c/Users/33393/Desktop/ai-legal-helper/dispatch-output/t8-e2-multi-20260920

# 代码路径 + 语料清点探针（只读；读 qa_pairs 集合，不写库）
/c/Users/33393/Desktop/ai-legal-helper/backend/venv/Scripts/python.exe -u probe_t8.py \
  > probe.stdout.txt 2>&1

# 语料抽样核查（只读）
/c/Users/33393/Desktop/ai-legal-helper/backend/venv/Scripts/python.exe -u investigate.py \
  > investigate.stdout.txt 2>&1

# 基线锚定读数
git -C /c/Users/33393/Desktop/ai-legal-helper rev-parse HEAD
/c/Users/33393/Desktop/ai-legal-helper/backend/venv/Scripts/python.exe -c \
  "import hashlib;print(hashlib.sha256(open('backend/main.py','rb').read()).hexdigest())"
```

> 环境坑已踩实：① 必须用 `/c/...` 正斜杠（用 `C:\...` 反斜杠会被 MSYS 双重转义成 `C:\c\...`）；
> ② stdout 在 Bash 工具里被吞，所有读数落盘到 `*.txt`/`*.json` 后回读；
> ③ `sha256sum`/`ls` 不在默认 PATH，须先 `export PATH=.../usr/bin`；④ 全程未跑 pytest（本卡无需）。

---

## ⑤ 诚实登记（没做到的 / 读不到的 / 未证实的 / 越界写）

- **未证实（关键局限）**：语料里「真·只给一个正确项」的**真实条数无法可靠量化**。现有 `multi_incomplete`/`_answer_declared_correct`
  对语料双重失敏（关键词 + markdown 解析），52 条候选经抽样多为漏识；真值需人工逐条核验，本卡未做（超只读探针射程、且非本卡判据硬性要求）。
- **读不到的**：无。E2 段（`gate_exit_registry.py` E2）、`_qa_direct_return`（`main.py`）、`multi_incomplete`（`quality.py`）、
  语料 `qa_pairs`（279 条，经 `_qa_corpus` 守卫只读 `collection.get`）均实读到。
- **没做到的**：未对 279 条做人工逐条多选完整性标注（成本高、非本卡必需；已用抽样 + 严格/宽松双口径说明局限）。
- **越界写声明**：**无越界写**。仅写入本交付目录 `dispatch-output/t8-e2-multi-20260920/`
  （`report.md`、`probe.json`、`probe_t8.py`、`investigate.py`、`*.txt`、`investigate.json`）。
  未改 `backend/**` 任何文件；未写真实 `qa_pairs` 语料（只读 `collection.get`）；未执行任何 git 写命令（无 add/commit/push）。

---

## 附：与票 J / 票 I 的关系（防误解）

- **票 J 只修了 E7（轻量出口）**：在 E7 调 `quality.multi_incomplete` 并加 E16 注记帧 + 拦缓存。E2 未被票 J 触及——本卡确认 E2 仍 `DISABLED`。
- **票 I 第四道护栏 ≠ 多选补判定**：第四道护栏是版本绊线（时间维度），与多选完整性（内容维度）正交；它的存在不改变「E2 不查多选完整性」的事实。
- **E2 三道既有护栏未动**：score≥0.92 / 选项指纹 / 条文时效——探针构造时令其全部不触发，仅隔离测试「多选完整性」这一维，符合「不许改 E2 三道既有护栏」。
