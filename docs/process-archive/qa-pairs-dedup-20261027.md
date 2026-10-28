# qa_pairs 存量查重与收敛建议（2026-10-27）

- 状态：**查重完成；删除已执行（Owner 2026-10-27 授权，删 131 留 33）**
- 对象：`qa_pairs_te4`（本地 Chroma），扫描脚本 `dispatch-output/qa-dedup-20261027/scan.py`（只读）
- 证据：`report.json` / `report.md`（全量分组）、`choose_keep.py` / `selection.json` / `selection.md`（拟议保留）

## 1. 查重结果（比原估的“7 份”大得多）

| 指标 | 读数 |
|---|---|
| 文档总数 | **279** |
| 归一题干后唯一题数 | **148** |
| 重复组（同题 ≥2 份） | **33** |
| 涉及文档 | **164** |
| 冗余副本 | **131**（= 47 份答案完全相同的副本 + 84 份同题不同答案的副本） |
| 同指纹但题干不同 | 0 |

- 全部重复都是 `re-*`，`law_basis=2026-08-23`（同一天生成的语料），不是本轮评测新增。
- 最大一组：**32 份同题**，6 种答案变体（13/9/5/3/1/1 份）；仅这一组就占 31 份冗余。
- 原提到的“劳动合同试用期”题是其中一组：**7 份、6 种答案**。
- **0 组**出现“所有候选都有坏引用”；每组至少有一条 `citation_verify` 为空的干净答案。
- 8 组在机械指标上并列（同坏引用数/同引用数/同长度），拟用 id 数字小者做确定性 tie-break。

## 2. 拟议保留规则（机械化、可复跑）

对每组按以下顺序选 1 条保留：

1. `citation_verify(answer)` 为空（没有引用库里不存在的条文）；
2. 坏引用更少；
3. 命中库内引用条数更多（`extract_citations` 去重后）；
4. 答案更长（信息更完整）；
5. id 数字更小（确定性 tie-break）。

产物：`selection.json`（33 组各保留哪条、131 条拟删清单、每组的 ranked 明细）。**该规则是机械代理，不等于法律质量判定。**

## 3. 建议（已按主建议执行）

**主建议：按机械选择删 131、保留 33（279→148）。**

- 删除前先把 279 条全量导出为 JSON 备份（question/answer/metadata），可回滚；
- 删除按 id 分批（每批 20），每批后核对 `total` 与剩余唯一题数；
- 删后核验：`total=148`、`unique_questions=148`、`citation_verify` 抽样为 0、`search_qa` 对原题只命中 1 条；
- 8 个并列组保留的答案在 `selection.md` 里逐条可查，建议人工抽看这 8 组（不抽也可以回滚）。

**保守替代：只删 47 份“答案完全相同”的副本**（零内容损失；279→232），84 份“同题不同答案”先保留，另开查询期 tie-break 票（同文重复向量 top1 无确定序，C21）。代价：直返质量仍可能在多个变体间漂。

## 4. 不删的风险

- 同题多向量 ⇒ `search_qa` 的 top1 可能随索引/距离微小差异漂移（C21 已登记）；
- 存储与嵌入成本约 1.9 倍于唯一题数；
- 同一问题可能返回不同答案，用户可见的不确定性。

## 5. 复跑

```powershell
cd c:\Users\33393\Desktop\ai-legal-helper\backend
.\venv\Scripts\python.exe ..\dispatch-output\qa-dedup-20261027\scan.py
.\venv\Scripts\python.exe ..\dispatch-output\qa-dedup-20261027\choose_keep.py
```

执行脚本：`dispatch-output/qa-dedup-20261027/apply_dedup.py`（按 `selection.json` 的 `delete_ids` 分批删，先导出备份）；删后核验：`verify_after.py`。

## 6. 执行结果（2026-10-27 02:29）

| 指标 | 读数 |
|---|---|
| 删除前 | 279 |
| 删除 | **131** |
| 保留 | 33 |
| 删除后 | **148** |
| 唯一题干（删后） | **148** |
| `keep` 全在 / `delete` 全不在 | true / true |
| 备份 | `dispatch-output/qa-dedup-20261027/backup_before_delete.json`（1.1 MB，**不入 git**，本机可回滚） |
| 32 份组剩余 | `re-15`（唯一精确命中） |
| 7 份组剩余 | `re-225`（唯一精确命中） |
| `search_qa(7 份组原题)` | 命中，score 1.0 |
| `qa_candidates` | 1364（未变，未动候选表） |

后端已重启使运行中向量视图一致（2026-10-27 02:29，PID 9828），`/api/health` / `/healthz` 全绿。证据：`dedup_result.json`、`post_dedup.json`。

## 7. 恢复演练（2026-10-27）

从 `backup_before_delete.json` 取本组 6 条已删文档，用同一嵌入模型重嵌（1024 维），写入临时 Chroma，重开 client 后核验：

| 判据 | 读数 |
|---|---|
| `count_after_add` / `count_after_reopen` | 6 / 6 |
| document 回读一致 | true |
| metadata 逐键回读一致 | true |
| query top1 命中已恢复集合 | true（`re-132`，distance 0.0） |
| 核心 `pass` | **true** |

局限：临时目录因 Chroma 0.4.24 在 Windows 上仍持有句柄，`tmp_removed=false`（已单独记录）；进程退出后由 shell 清理。**本演练证明备份的 document/metadata 可重建并可查，不证明现网 `qa_pairs_te4` 的原地恢复**（那需要另一次写操作授权）。证据：`restore_drill.json`。
