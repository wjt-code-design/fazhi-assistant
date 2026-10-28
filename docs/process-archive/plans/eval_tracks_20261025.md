# 评测题库分轨方案（2026-10-25 对齐结论）

> 本文件是 grilling 对齐后的执行契约。核心：**一个题库、两种 track、一条优先级**。

## 决定

1. 评测用途是 C：先做内部防回归（A），再做对外可信度（B）。
2. 不建物理两套题库，改为**单库 + `track` 字段**，避免权威冲突与双份维护。
3. **回归集只管门禁，对外集只管汇报；两者冲突时以回归集为准。**

## 题库 schema

```json
{
  "id": 101,
  "track": "regression",
  "gold_provenance": "corpus_derived",
  "capability": "retrieval",
  "question": "朋友答应送我的东西还没到手就反悔了，这种情况法律上怎么算？",
  "expected_sources": ["民法典"],
  "expected_articles": ["第六百五十八条"],
  "reviewed_by": ""
}
```

字段规则：

| 字段 | 取值 | 说明 |
|---|---|---|
| `track` | `regression` / `external` | 缺省按 `regression` 处理 |
| `gold_provenance` | `corpus_derived` / `expert_annotated` / `unreviewed` | 金标来源 |
| `capability` | `retrieval` / `application` / `reasoning` / `procedure` | 对外集**必填**，回归集可选 |
| `reviewed_by` | 姓名/机构/匿名编号 | 对外集必须非空 |

## 准入与权威规则

- **回归集**：允许 `corpus_derived`（从库内条文反向出题），要求小、稳定、可复现；只用于门禁。
- **对外集**：必须 `gold_provenance = expert_annotated` 且 `reviewed_by` 非空；只用于对外汇报，不参与门禁。
- **冲突**：同一版本回归集跌、对外集涨 → 以回归集为准，禁止对外披露「综合提升」这类混合口径。
- **禁止**：把两集合并算一个总分对外发布。

## 运行方式

```powershell
# 回归门禁（默认 eval_set.json）
$env:EVAL_SET="data\eval_set_gen_all.json"; $env:EVAL_TRACK="regression"
backend\venv\Scripts\python.exe backend\scripts\eval_retrieval.py

# 对外汇报（external 集建立后）
$env:EVAL_SET="data\eval_external_v1.json"; $env:EVAL_TRACK="external"
backend\venv\Scripts\python.exe backend\scripts\eval_retrieval.py
```

`eval_retrieval.py` / `eval_quality.py` 已支持 `EVAL_TRACK` 过滤；未设置时跑全部。

## 迁移记录

| 文件 | 题数 | track | gold_provenance |
|---|---|---|---|
| `data/eval_set.json` | 28 | regression | unreviewed |
| `data/eval_set_gen_all.json` | 59 | regression | 20 题 expert_annotated / 39 题 corpus_derived |
| `data/eval_set_gen_v1.json` | 29 | regression | 10 题 expert_annotated / 19 题 corpus_derived |
| `data/eval_set_gen_v2.json` | 30 | regression | 10 题 expert_annotated / 20 题 corpus_derived |
| `data/eval_external_v1.json` | 20 | external | expert_annotated（AI-LEX-01，`review_level=ai_third_party`） |

`eval_external_v1.json` 由 `backend/scripts/build_external_set.py` 从 `eval_set_gen_all.json`
派生，**不要手工编辑**；源头变更后重跑脚本即可。

## 对外集的两条披露红线

1. 复核人是**第三方 AI 法律研究系统（AI-LEX-01）**，不是执业律师。对外不得称「律师复核」。
2. 这 20 题是**刻意选出的难例**（检索失败、引用越界、判不忠实），
   recall@4=0.650 不能当作整体准确率。若要对客户承诺，需再抽随机样本并由人类律师复核。

## 与开源项目的对照

| 做法 | 来源 | 本方案对应 |
|---|---|---|
| 检索与生成分开评 | LegalBench-RAG / Legal RAG Bench | 已有 `eval_retrieval` 与 `citation_check` 分离 |
| 金标由法律专家标注 | LegalBench-RAG / Bar Exam QA | 对外集强制 `expert_annotated` |
| 小规模专家题集可用 | Legal RAG Bench（100 题） | 回归集维持 59 题，不盲目扩 |
| 按能力分类 | LexEval（23 任务）/ LawBench（3 层认知） | 对外集强制 `capability` |
| 逐 claim 核验 | RAGAS faithfulness | 已有机械引用 + grounding 三分类，逐 claim 留待后续 |

## 尚未做（需要外部输入或另行排期）

- **人类律师复核**：当前只有 AI-LEX-01 复核；对外承诺前必须补。
- **随机样本对外集**：external_v1 是难例子集；需另抽 50–100 题随机样本复核，才能报整体准确率。
- 多轮咨询评测（参考 LexRAG）未立项。

## 验收

- [x] 现有 146 条题记录全部带 `track`、`gold_provenance`
- [x] 两个 runner 支持 `EVAL_TRACK`
- [x] 回归基线冻结：`docs/benchmark_results/citation_gen59_20261025b.json`
  （n=59，precision 0.6240，leak 0.3760，hallucination 0.0000，recall 0.2644）
- [x] 对外集建立：20 题，准入字段齐全（`expert_annotated` + `reviewed_by` + `capability`）
- [ ] 人类律师复核与随机样本（对外承诺前置条件）
