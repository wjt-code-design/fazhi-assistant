# T7 · `options_fingerprint` 只有 60/279 的根因 + 补采覆盖测算

> **只读诊断卡。零语料写入、chroma 只读（get/count）、不碰 git、只写本目录。**

## 基线锚定（开工时刻）

| 项 | 值 |
|---|---|
| `git rev-parse HEAD` | `2a48f3ec0f4b906302755504131c5da252e38f77` |
| `sha256(backend/main.py)` | `4807cc9e4b9dd14334b754f63dea53ff9c1b669157647b93de21bab5be4cbe5f` |
| `backend/main.py` 工作树状态 | 干净（`git status` 无修改，与 baseline.json 登记的提交版哈希逐字一致） |
| 数的是哪个集合 | **`qa_pairs`**（279 条）；`qa_pairs_te4`（21 条）单独隔离，**不混入分母/分子** |

> 该 HEAD 即 baseline.json 在 23:41 重锚的 `2a48f3e`；`sha256(main.py)` 与 baseline.json 的 `single_writer_resources.backend/main.py.sha256` **完全相同**，说明开工时语料读取侧代码即为票 I 收工后的提交版，未漂移。

---

## ① 结论（一句话回答任务问题）

`options_fingerprint` 只有 60 条非空，是因为**非空指纹只能由 `backend/scripts/gen_qa_corpus.py` 在「用固定 62 条选项题批量预生成语料」那一步现算并写入**（`_options_fingerprint` + `add_qa_pair(..., fingerprint=...)`）；之后所有其它写库路径（`qa_seeds.py` 种子、`create_candidate` 自动收录、`decide_candidate` 管理员采纳、以及 144 条完全绕过 `add_qa_pair` 的记录）**从没调用过 `_options_fingerprint`**，所以缺指纹。

对当前 `qa_pairs` 全部 279 条用 `_options_fingerprint` 现算：带真实选项、本来就能提出指纹的记录 = **168 条**。其中 60 条已正确存了指纹，**108 条缺**（18 条键在值空 + 90 条连键都没有）。

**补采（回填这 108 条的指纹）能把覆盖从：**
- 对全部 279 条：60/279 = **21.5% → 168/279 = 60.2%**（+108 条）；
- 对「带选项记录」168 条（更公平的分母，指纹只对选项题有意义）：60/168 = **35.7% → 168/168 = 100%**（+108 条）。

即：补采把「同题干换选项」的 C4 护栏从只护 35.7% 的选项题提升到 **100%** 覆盖的选项题。

---

## ② 产物（绝对路径 + 关键读数）

| 产物 | 路径 |
|---|---|
| 本报告 | `dispatch-output/t7-fingerprint-coverage-20260920/report.md` |
| 重算结果（机器可读） | `dispatch-output/t7-fingerprint-coverage-20260920/recompute.json` |
| 只读探针（可复跑） | `dispatch-output/t7-fingerprint-coverage-20260920/_recompute_probe.py` |

**关键读数（来自 recompute.json，探针只读 `collection.get`）：**

```
total_qa_pairs = 279
stored.options_fingerprint 键存在           = 135  (非空 60 + 空串 75)
stored.options_fingerprint 键缺失           = 144
recomputed._options_fingerprint 非空        = 168   ← 带选项、理论上可提取指纹
recomputed 空（确无选项，本就不该有指纹）   = 111   (279-168)
gap（有选项却无可用指纹，补采可补）         = 108   (18 键在值空 + 90 无键)
qa_pairs_te4 集合                           = 21 条，指纹 0 条（隔离，未计入）
```

交叉分类（每条记录 stored vs 现算）：

| 类 | 含义 | 条数 |
|---|---|---|
| A | stored 非空 & 现算非空（已正确指纹） | 60 |
| B | stored 空串 & 现算有选项（缺口，可补） | 18 |
| C | stored 非空 & 现算无选项（异常） | 0 |
| D | 均空 & 确无选项（合理无指纹） | 57 |
| E | 无键 & 现算有选项（缺口，可补） | 90 |
| F | 无键 & 确无选项（合理无指纹） | 54 |

校验：`A+B+C+D = 135` ✓；`E+F = 144` ✓；`A+B+E = 168` ✓；`D+F = 111` ✓。

---

## ③ 判据对照（T7 卡三条判据逐条）

**判据①：60 条指纹是谁在哪一步写进去的（代码出处）**

- **唯一写入非空指纹的代码路径**：`backend/scripts/gen_qa_corpus.py:177-178`
  ```python
  fingerprint = query_understand._options_fingerprint(q)           # 现算
  ks.add_qa_pair(q, answer, evidence=evidence, fingerprint=fingerprint)
  ```
  落库点：`knowledge_service.add_qa_pair`（knowledge_service.py:277）把 `fingerprint` 写进 `metadata["options_fingerprint"]`。这一步**只在「用固定 `QUESTIONS`（62 条 A/B/C/D 选项题）批量预生成语料」时执行**。
- **其余所有写库路径都不传 `fingerprint`**（默认 `""`，故键在值空）：
  - `backend/qa_seeds.py:62` `ks.add_qa_pair(question, answer, evidence=...)`（种子，自然语言、无选项）
  - `knowledge_service.create_candidate`（knowledge_service.py:323）`add_qa_pair(question, answer, evidence or "")`（有据分 ≥0.89 自动收录）
  - `knowledge_service.decide_candidate`（knowledge_service.py:372）`add_qa_pair(r.question, r.answer, r.evidence or "")`（管理员采纳）
- **另有 144 条连 `options_fingerprint` 键都没有** → 完全绕过 `add_qa_pair`（疑似直接 collection 写入 / 早期批量导入），自然更无指纹。
- **结论**：60 条非空指纹 = 当初由 `gen_qa_corpus.py` 现算并写入的那批选项题；其余 219 条从未被任何路径计算过指纹。**根因 = 写侧只在一条生成路径埋了指纹计算，所有后续/旁路写库路径都没埋。**

**判据②：用 `_options_fingerprint` 对当前全部记录现算「理论可提取」条数**

- 现算结果 = **168 条非空**（= 带真实选项、本该有指纹的记录）。
- 该函数与读侧 `_qa_direct_return`（main.py:1136 `q_fp = query_understand._options_fingerprint(q)`）**是同一个函数**，因此 168 就是「若当初每个写库路径都调 `_options_fingerprint`，本应拥有的指纹数」。
- ⚠️ **与 brief 的差异（如实报差量）**：任务书里写「带选项记录 166 条」，本次实测 **168 条**（+2）。60 / 279 / 219 三个数与 brief 完全一致，**仅「带选项」分母需订正为 168**。差量来源：brief 的 166 应来自更早的探针/I-1 读数或近似计数；本次用与读侧完全一致的 `_options_fingerprint` 对 279 条 live 记录全量重算，168 为当前权威值。
- 读侧护栏确认缺指纹=缺护栏：`main.py:1138` `if q_fp and stored_fp and q_fp != stored_fp: return None`——`stored_fp` 为空时该判定恒不触发，故缺指纹的 108 条选项题在「同题干换选项」场景下可被错误直返（C4 漏洞），这正是补采要堵的口子。

**判据③：补采能把覆盖面提到多少（给数，分母口径写明）**

- 补采动作 = 对现算非空的 168 条全部回填 `options_fingerprint`（60 条已正确，108 条待补：18 键在值空 + 90 无键）。
- **两档分母都给，不混：**
  - 分母=全部 279 条：`60/279 = 21.5%` → `168/279 = 60.2%`，绝对值 **+108 条**。
  - 分母=带选项记录 168 条（更公平，指纹只对选项题有意义）：`60/168 = 35.7%` → `168/168 = 100%`，绝对值 **+108 条**。
- **不接受「建议补采而无数」**：已给数——补采净增 **108 条**指纹，把选项题的 C4 护栏覆盖率从 35.7% 拉到 100%。
- **不接受「拿 60 当分子却说覆盖 279」**：分母分两档明示；60 是分子，对 279 是 21.5%、对 168 是 35.7%，均已标注。

---

## ④ 我复跑的命令（可照跑，含路径）

```bash
# 1) 设 PATH（否则 grep/ls 等不存在；本机实测）
export PATH=/c/Users/33393/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH

# 2) 进交付目录，用 venv 解释器跑只读探针（相对脚本名，避免 msys 路径双重前缀）
cd /c/Users/33393/Desktop/ai-legal-helper/dispatch-output/t7-fingerprint-coverage-20260920
/c/Users/33393/Desktop/ai-legal-helper/backend/venv/Scripts/python.exe -u _recompute_probe.py \
  > _probe_run.txt 2>&1; echo "rc=$?" >> _probe_run.txt

# 3) 看结果
cat recompute.json
```

探针内部仅做：`KS._qa_store._collection.get(include=["metadatas","documents"])` 读全部 279 条，
对每条 `query_understand._options_fingerprint(question)` 现算，再写 `recompute.json`。**无任何 add/update/delete。**
`qa_pairs_te4` 用独立 `Chroma(..., collection_name="qa_pairs_te4")` 只读 `.get()`，21 条单独隔离不计入。

---

## ⑤ 诚实登记 + 越界写声明

**诚实登记（未做到/读不到/未证实）：**
1. **108 条缺口的精确来源未逐条溯源到具体写入脚本**：metadata 里 `origin` 全是 `"qa"`，且票 I 已对全部 279 条加了 `law_as_of_basis/law_as_of_basis_src`，无法仅凭 metadata 区分「这 108 条当初经哪条路径进库」。能确定的是：它们都没有 `options_fingerprint`，且读侧函数证明它们带选项。要彻底归因需查 git 历史或导入日志（属后续工作，不在本卡只读射程）。
2. **166→168 的 +2 差量未追到具体原因**：仅确认当前 live 实测为 168，brief 的 166 应为更早读数/近似；不影响结论（补采净增仍是 108）。
3. **补采未实际执行**：按 T7 卡「只读、只算、不写真实语料」+ §4 冲突矩阵③（补采实现须与票 I 语料写入串行），本卡只给数不给写。
4. **`qa_pairs_te4`（21 条，云端 cosine 集合）未混入**：已单独隔离读取并标注，不与 `qa_pairs` 的 279 条相混。

**越界写声明：**
- 本卡**未写 git**（无任何 `git add/commit/...`）。
- 本卡**未写真实语料**（`qa_pairs` / `qa_pairs_te4` 零写入，仅 `.get`/`.count`）。
- 本卡**未改 `backend/**`**（未触碰 `main.py` 等任何产品码；`sha256(main.py)` 开工=收工，已锚定）。
- 唯一写集 = `dispatch-output/t7-fingerprint-coverage-20260920/`：`report.md`、`recompute.json`，外加可复跑的 `_recompute_probe.py` 与过程日志（`_probe_run.txt`、`_probe.log`）。仓库根目录的临时探针文件（`_t7_*.txt`）已在收尾时清理。
