# 评测题集 v2 构建与检索探针报告 — 2026-09-13

对齐过程：grilling 5 问（对象=Agent 能力评测为主+检索探针为辅；用途=新缺陷面素材为主体并入 v1；
金标=自动起草+双保险校验；边界=题集+零成本探针，付费基线另授权；存放=仓库根 evals/ 入 git）。
自审封堵 8 漏洞（条目级禁引/子查询双轨/排序路径标注/scope 只测确定性/runner 协议自包含/
KB 版本对照标注/v1 逐字校验/复跑配方）。

## 交付物

| 文件 | 作用 | 状态 |
|---|---|---|
| `evals/frozen-cases-v2.json` | 20 例题集（C01-C10 逐字复用 v1 + E01-E10 新写），status=FROZEN | ✅ 已提交 |
| `evals/validate_cases.py` | 金标校验：article_in_kb 全量 + v1 逐字 + 结构契约 | ✅ PASS (fails=0) |
| `evals/retrieval_probe.py` | 双轨探针（required 召回 + forbidden 混入），零成本 | ✅ 跑通 |
| `evals/probe-results.json` | 探针机器可读结果快照 | ✅ 已提交 |

## 校验结果（e3）

`checked: required_laws=53 forbidden_articles=12 fails=0 warns=0 → VALIDATION PASS`
- 53 条 required + 12 条 forbidden 全部经 `article_in_kb` 确定性核验存在于知识库
- C01-C10 与 v1 真源 9 字段逐字相等（防分叉）
- 新案例 fact_reveal 自包含（r1/r2 text+keywords，对齐 runner 协议）

## 探针结果（e4，排序路径=池内余弦精排降级路径）

**负向轨（禁引混入）= 缺陷量化尺子，有效性已证实**：
```
E01 req 1/3 forb 2/2   ← 民案"起诉条件"query 行政诉讼法49/51 全混入 = C07 事故稳定复现
E02 req 0/3 forb 3/6   ← 借贷"起诉立案材料"混入行政诉讼法 50/51/52（初版漏禁，探针抓到后扩判据）
E03 req 1/2 forb 0/1   ← 修正 required(806 建设工程) 后 806 命中
E04 req 2/3 forb 0/1 / E05 req 0/3 forb 0/2   ← 单次子查询未钓出陷阱
汇总 forbidden 5/12 混入率 41.7%
```
**正向轨（required ∈ 单查询 top-6）= 19/53（35.9%）**：如实标注——这是**检索层诊断尺**，
不是端到端判据。Agent 实际证据池是多子查询并集 + 锚点保底；跑 Agent 基线时 required 判据
应取「最终证据池包含」而非「任一单查询 top-6 包含」。

**增量发现（修复目标具象化）**：「起诉/立案/材料」类程序性 query 是**程序法跨部门混入重灾区**
（E01/E02 两案 5/5 全混入，top-6 被行政诉讼法/刑事诉讼法占据）——未来部门法过滤修复的
第一靶点即此类 query。

## 探针即时校准价值（金标 2 处修正在冻结前完成）

1. E02 forbidden 扩列（+行政诉讼法 50/51/52）：初版漏判据，探针混入数据直接暴露
2. E03 required 改 [577, 806]：初版误列过泛总则条文；KB 把装修合同归建设工程施工合同
   章（806 等）才是法律上更准的召回，金标按法律准绳修正（不迁就探针输出）

## 下次跑 Agent 付费基线的配方（未跑，待授权）

```powershell
# 1) 隔离宿主（换批次建新证据目录；GUARD = 累计授权 20 − 已花费；累计已花约 0.23 元）
$env:EVAL_EVIDENCE_DIR="<新目录>"; $env:EVAL_PORT=18124; $env:EVAL_GUARD_LIMIT="19.77"
backend\venv\Scripts\python.exe dispatch-output\agent-quality-20260911\serve.py
# 2) 跑 v2 题集（runner 需小改读取端以消费新案例 fact_reveal——KEYWORDS 现硬编码于 runner，
#    C01-C10 可直接跑；E01-E10 接入属 backend/scripts 改动，另行授权）
backend\venv\Scripts\python.exe backend\scripts\gate2_runner.py --cases-file evals\frozen-cases-v2.json ...
```
scope_trigger/forbidden_articles 判据的消费端在 runner/评测器侧，属基线 run 的实施项。

## 防幻觉五连问

1. 数字来源：probe-results.json（机器可读逐案例）、validate 输出（exit 0）、git diff（backend 零改动）
2. 可复现：两条命令即配方，本地零成本，无网络依赖（embedding 本地、缓存冷启动亦可）
3. 亲历红/绿：是——首跑 JSON 语法红、金标 2 处修正后全绿；混入率从 22.2%→41.7% 是判据
   扩列所致（度量更严，非缺陷恶化）
4. 期望独立：required/forbidden 由法律适用性起草（官方法条常识），存在性由 KB 独立接口核验；
   探针不校准自己——金标修正依据是法律准绳不是探针输出
5. 已知限制：探针=降级排序路径（云 rerank 配额耗尽），云路径混入率可能不同；单查询判据≠
   端到端判据；语义适用性复核=自查标注（非执业律师）；E04/E05 陷阱单次未触发（子查询变体
   有限，Agent 端到端可能用其他问法）；新案例入 runner 需小改读取端（未动，留授权）