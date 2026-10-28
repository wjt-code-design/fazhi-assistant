# 法智项目 · 后续执行书（自包含交接版，2026-09-17）

> **本文件是唯一的后续任务执行入口。** 写给"没有本会话记忆的助手"：读完本文件即可独立执行，
> 无需追问历史。进度只追加于本文件与 `docs/process-archive/project-next-execution-plan-20260916.md` §7，
> **不新建互相覆盖的交接文件**；判据/红线冻结，执行中不得按结果修改，偏离需 Owner 显式授权并留痕。

---

## 0. 项目快速上下文

- **项目**：法智（法律 AI 助手）——用户提交法律咨询 → Agent 多轮（澄清→检索→生成→校验）→ 法律回答。
- **技术栈**：FastAPI backend + Next.js 14 frontend + 本地 BGE 向量库（chromadb）+ SQLite；
  Docker Compose 部署于腾讯云（IP 162.14.81.34），本地开发走 `backend/venv`。
- **仓库**：`C:\Users\33393\Desktop\ai-legal-helper`（master；远端 github.com/wjt-code-design/fazhi-assistant）。
- **Python**：一律用 `backend/venv/Scripts/python.exe`（backend 依赖）或
  `C:/Users/33393/.workbuddy/binaries/python/envs/html2docx/Scripts/python.exe`（docx/转换类）。
  **禁止系统 python**。
- **门禁基线**：`pytest -m "not slow"` = **1101 passed / 0 failed**；ruff check / ruff format --check /
  mypy（67 files）全绿。**任何生产代码改动后必须复跑全量**。
- **当前开关状态**：`agent_dept_filter`（R1）与 `agent_dept_filter_r1ob`（R1-OB）**均为默认关**
  （backend/.env 与根 .env 无键）——生产行为 = 不过滤。

## 1. 必读纪律（违反 = 交付失败）

1. **预注册判据冻结**：验收判据先冻结后执行，不得按结果修改；不救数（失败如实记录，不重跑凑数）。
2. **watch-it-fail 必须当场落盘**：新测试要"对正确原因红过"——回滚→红→恢复→绿的输出**写入证据文件**
   （仅口头/会话内执行 = 缺口）。
3. **show-your-work**：声称"完成/全绿/为 0"前自审复核；断言"为空/为 0"先确认键存在；**并列数字先核对口径**
   （探针口径 ≠ 真实记录口径，不可混比）。
4. **动笔前字节快照**：改文件前先存快照（连续两轮漏做导致拿不到纯本轮 diff 的前科）。
5. **跨格式完整性比对**：md/html/docx 互查必须考虑三层干扰——markdown 列表符、HTML 标签、
   **Word 有序列表自动编号**（编号是格式不在文本层）——行级归一验证为准（v3 方法，
   见 `review-package-law-20260917/audit_docx_v3.py`）。
6. **评测统计禁用全局共享字典**按法条聚合（逐案例独立维护，防计数虚高）。
7. **汇报风格**：极简命令式中文、结构化表格、诚实标注"推测/无法判定"、复核与审计结论单独汇报。

## 2. 本机环境坑（高频陷阱，务必先读）

1. **pytest `--basetemp` 必须每次全新目录**（复用旧目录触发 safe-delete 批删 → SystemExit → 集体 setup 失败）；
   父目录须先存在。
2. **管道吞退出码**：`cmd | python -c "..."` 链中 ruff/pytest 非 0 **不会中断 && 链**——曾导致提交未过
   lint 的文件。lint 门禁直接跑命令看退出码，**不走管道**。
3. **Python 内发联网请求会让整个 bash 进程被杀** → 联网探测用 **curl**（白名单）或 WebFetch/WebFetch 工具。
4. `sleep`/`dirname`/`ls`/`head` 等不在 Git Bash PATH → 用 Python `time.sleep` / 绝对路径工具。
5. **PowerShell 工具拿不到 stdout** → 读注册表用 Python `winreg`，看进程用 `subprocess tasklist`。
6. 中文路径一律**绝对路径加引号**；相对路径在 Git Bash 解析易失败。
7. **commit message 不内嵌英文双引号**（会被 shell 拆成 pathspec）；含反引号/`$` 的内联代码写 `.py` 文件执行。
8. Python 写文件 **`newline=''` 或显式 `'\n'`**（仓库 autocrlf=true，否则 ruff format --check 失败且 git 看不见差异）。
9. **停止/杀进程**：只杀日志里记录的那个 PID，不批量杀 python。
10. **远端 git 直推历史不可用**（对象损坏段已修复但历史链断）——**同步走快照机制**：
    `commit-tree(HEAD树, parent=远端tip)` → 树一致性 → `rev-list --objects --missing=print` 零缺失 →
    dry-run → push → ls-remote 核对（模板：`dispatch-output/review-package-law-20260917/` 及
    `r1ob-prodform-20260917/` 下的推送脚本，第六轮快照 `cfdf66c` 已同步）。
11. setup-html-to-docx.sh 内调 wsl.exe 会被沙箱拦 → 转换环境用手动 venv
    `C:/Users/33393/.workbuddy/binaries/python/envs/html2docx`（已装 python-docx/lxml/Pillow/click 等，
    requirements 全量）。

## 3. 关键资产索引（位置 → 用途）

| 资产 | 位置 | 用途 |
|---|---|---|
| 批次编排（含网络预检） | `dispatch-output/r1ob-prodform-20260917/run_prodform_batch.py`（同构：`r1ob-online-20260917/run_r1ob_online.py`） | 两臂×两集评测运行 |
| 网络健康工具 | `backend/scripts/net_health.py`（check 跑前预检 / report 跑后小结） | 批次前后必用 |
| 判据分析模板 | `dispatch-output/r1ob-prodform-20260917/analyze_prodform_batch.py` | 批次判据 P1–P6 |
| 验收回执流水线 | `dispatch-output/review-package-law-20260917/acceptance_compare.py` | 复核回执 → 三方对比 |
| 复核判定导出 | 同目录 `export_review_json.py` → `review-verdicts.json` / `.csv` | 回归断言集（12 项"否"） |
| **回归断言集（冻结）** | `review-package-law-20260917/review-verdicts.json` 的 12 项独立"否" | T-A2 校验必须全拦截 |
| **冻结资产（勿覆盖）** | `evals/probe-results.json`（R1-OB 验证输入）、`evals/counterexamples.json`、各批次 `*-sessions.json` | 历史基线 |
| 探针（k4 合规口径） | `evals/retrieval_probe.py`（输出 `probe-results-k4.json`） | 召回率/污染率度量 |
| 诊断/调查脚本 | `dispatch-output/e04_trace.py`、`e04_domain_test.py`、`b4_entity_contamination.py`、`a1_historical_scan.py` | 机制调查复用 |
| 验收报告 | `review-package-law-20260917/acceptance-verdict-report.md`（部分背书 68.3%） | 本执行书的立项依据 |
| R1-OB 开启手册 | `docs/process-archive/project-next-execution-plan-20260916.md` §"未来开启操作手册" | T-B 执行步骤 |
| 快照推送脚本模板 | `dispatch-output/r1ob-online-20260917/push_snapshot2.py` | 远端同步 |

## 4. 任务清单（全部后续执行项，按序）

### 主线一：实体法适用精度（T-A 系列，已立项）

> 判据冻结见 §6；回归断言集见 §3。位置：verifier 层（与 citation_verify 同位），**不进检索过滤层**。

- **T-A0 数字溯源诊断**（先行，~30 分钟，零成本）—— ✅ **完成（2026-09-17）**
  报告：`dispatch-output/ta0-numeric-trace-20260917/report.md`。
  **结论：全部 NUMERIC 拒绝（11 次）属 (a) 匹配缺陷**——主机理 = 数字 token 形态不归一
  （"5万块/8万开工款/欠货款20万"→number:N vs 问题复述"N万元"→amount:N:万）+
  跨争点事实数字无白名单 + 未决事实脱敏副作用；"三年"有受控来源（民法典188 已检索挂本争点）。
  **(b) 仅受理费金额**：KB 缺《诉讼费用交纳办法》（laws*.json/laws_raw 三处 0 命中）→ 受控计算路线。
  ⚠️ 勘误：E02 受理费被拒原因码实为 UNKNOWN_EVIDENCE_ID（非 NUMERIC）；E02 的 NUMERIC
  拒绝在"5万债权成立"争点。T-A3(a) 两项（归一 + 白名单，白名单须取脱敏前原值）均被证实必要。
  原始任务描述（保留）：
  判定三个被拒争点（E01 时效 / E02 受理费 / E03 返还 8 万，原因码 `UNSUPPORTED_NUMERIC_TOKEN`）属于
  **(a) 匹配缺陷**（数字在证据池法条原文/案例事实中，verifier 没对上）还是 **(b) 真无受控来源**（需公式计算/KB 缺《诉讼费用交纳办法》）。
  方法：各 run 的 `evaluation.sqlite` state_json 证据池 → 回查 KB 法条源文件逐字核查数字（中文/阿拉伯归一）。
  **注意**：evidence.text 字段可能为空——须回查 KB 源文件。
  DoD：三争点 (a)/(b) 分类表 + 证据引用；(b) 类的 KB 来源缺口单独列出。
- **T-A1 法条库标注**（~半天）—— ✅ **完成（2026-09-17，复核抽验通过 + 3 项修正已落）**
  产出：`backend/knowledge_base/law_annotations.json`（status=final；词表 v2 +保证人/受害人/非法人组织）
  + 证据目录（预标/自查/抽验/**分歧裁决 disagreement-verdicts.md**）。
  复核结果：14 条 × 4 字段 = 56 项判定 **53 是 / 3 否（94.6%）**；3 项"否"全在 subject_types
  （1179 漏法人 / 693 漏保证人 / 686 漏保证人+误列债务人），已按复核意见修正并复跑自查全绿
  （H1–H5 + show-your-work 10/10）；两处预注册锚点两可条目经复核维持预标（裁决留痕）。
  复核建议：词表扩充已采纳；**invalidity 方向值列入 T-A2 设计输入**；主体完整性校验规则
  采纳为下次预标自查规则。诚实声明：抽验覆盖 36.8%，未抽验 24 条维持预标值。
  原始任务描述（保留）：
  Schema：`backend/knowledge_base/law_annotations.json`（键=法条 source_ref；字段 subject_types /
  claim_direction / chapter / applies_when）。流程：LLM 预标 53 条 → 自查 → **复核人抽验 ≥1/3**（分歧清单留痕）。
- **T-A2 verifier 校验实现**（~1 天）—— ✅ **完成（2026-09-17 晚；四组测试 + 全量门禁全绿）**
  D1-D3 已拍板（选项一 / 标注扩充 / `_ta2` 扩展）。产出：
  `backend/agent/entity_precision.py`（新模块）+ `writer.py` 渲染循环挂接（citation 检查同位，
  **非 verifier 终态**——service.py:466 非 PASS 即终态失败，会违反 P3；触发后走争点级
  uncovered 流程，同 NUMERIC 形态）+ settings 开关 `entity_precision_check`（默认关）+
  service `_UNCOVERED_REASON_TEXT` 两条新文案 + 标注库 69 条（38+31，含 `_ta2.direction_subjects`）。
  实测覆盖（D1 选项一确定性子集）：**拦 3/10**（独资42、合伙102〔修正标注后〕、民法典804）；
  残余 7 项精确清单（6/49 归 R1 线；128/131/801/802/807 需 domain_tags 机制=T-A5 后议）。
  附带修正标注 2 处：787 主体系定作人/承揽人（原误标建设工程角色）、102 债权人移至 right 侧。
  测试：`tests/test_entity_precision.py` 30 passed（组1 拦截 5 场景 / 组2 零误杀 23+簇 /
  组3 开关关 / 组4 watch-it-fail on红off绿）；watch-it-fail 落盘 `ta2-design-20260917/watch-it-fail.txt`；
  ruff/format/mypy 全绿（改动 6 文件）；全量门禁结果见下方补记。
  **全量门禁（2026-09-17 19:41）：`pytest -m "not slow"` = 1137 passed / 18 deselected /
  0 failed（5m43s，basetemp 全新目录）**——0 失败即无回归；较旧基线 1101 的增量来自
  第七轮快照后既有测试与本轮 +30，口径差已留痕。
  原始任务描述（保留）：
  新原因码 `SUBJECT_TYPE_MISMATCH` / `CLAIM_DIRECTION_REVERSED`；开关 `entity_precision_check` **默认关**；
  位置=verifier 层。测试四组：12 项"否"全拦截 / 43 项"认可"零误杀 / 开关关行为逐字不变 / watch-it-fail 落盘。
  DoD：全量门禁绿 + 四组测试。
- **T-A3 拒答策略分级**（依据 T-A0：(a) 为主）—— 🔶 **实现+两把尺子测试完成（2026-09-17 晚），全量门禁运行中**
  开关 `numeric_matching_v2`（默认关 = writer/verifier 数字校验逐字不变）：
  ①**数字归一**：`_AMOUNT_LOOSE_RE`（数字+万/亿 → amount:N:万，与"N万元"同 token；
  默认参数不参与收集，开关开时 writer/verifier 消费点显式传 True——两条防线同步放行）
  ②**事实数字白名单**：全 state 已确认+未决事实（脱敏前原值）数字 token；池外新数字仍拦（防幻觉边界不变）。
  T-A0 三重机理全覆盖：形态归一（E02/E03 场景）+ 跨争点事实（E01 20万）+ 未决事实原值。
  测试 `tests/test_numeric_matching_v2.py` **8 passed**：正向 3 反例 + 未决白名单 + 反向幻觉 2
  （池外 12万/变体放大 3万5000 仍拦）+ 开关关旧行为 + token 等价单元；
  watch-it-fail 落盘 `ta2-design-20260917/watch-it-fail-ta3.txt`（on 过/off 拒）；
  ruff/format/mypy 全绿。全量门禁结果待补。
  **T-A3(b) 受控计算（Owner 2026-09-17 授权）**：
  `backend/knowledge_base/fee_formulas.json`（《诉讼费用交纳办法》第13条累计递进费率 + 第16条
  简易减半；**锚点 6/6 实测**：1万=50、5万=1050、10万=2300、20万=4300、50万=8800、100万=13800
  ——冒烟抓到实现错误：50 元系固定基础费与递进段叠加，非"≤1万才收"）+
  `backend/agent/fee_calc.py`（纯函数确定性计算 + 标的额=事实最大货币额 + 受控 token 集）+
  writer 白名单/verifier 验算双防线同口径接入（同 numeric_matching_v2 开关）+
  测试 +2（受控 1050/525 放行、池外 2000 仍拦）→ **10 passed**；T-A2 回归 37 passed。
  遗留：《交纳办法》条文全文待 Owner 提供官方文本后入 laws_raw（KB 检索索引未重建，
  受控计算走公式表不受影响）。**全量门禁（2026-09-17 20:34）：1155 passed / 18 deselected /
  0 failed（5m56s）**——0 失败即无回归（计数口径：1152→1155 含 T-A2 残余断言 +7 与 T-A3 +8/+2
  两批测试增量，逐项对账差 1 未溯源、非失败项，已留痕）。
  原始任务描述（保留）：
  (a) 为主 → 修匹配（数字归一 + **事实数字白名单**——用户陈述的事实数字不判"无来源"；判据语义不变属修 bug）；
  (b) 为主 → **受控计算**（官方公式表入库需 Owner 授权补充知识来源 → 确定性计算 → verifier 验算；单独预注册）。
  **层级 3（LLM 自估区间）不做**。DoD：复核人 3 反例正向回归 + 数字幻觉对抗用例反向回归，两把尺子都过。
- **T-A4 材料包迭代**（半天）—— ✅ **完成（2026-09-17，等待 T-A1 复核抽验期间执行；Owner 授权并行）**
  产出：`dispatch-output/ta4-materials-20260917/`（v2 提取/HTML/转换/审计 4 脚本 +
  `法律复核材料-v2.docx` + audit-ta4.txt）。
  A1 核查表 = 唯一条文 + **出现次数**列（5 表 63 行，跨格式核验 docx↔md 63/63 全对）；
  A3 总体判读三问各自成块 + （请在此作答）作答区 15/15 + 其他意见（选填）独立段；
  A3 备注列加宽 5/5 生效（colgroup 32%）。**脱敏自检 0 泄漏**（LEAK 清单同 audit_docx.py）。
  转换器踩坑留痕：lxml 活迭代中删 nav 节点 → 截断整树（两次真实红后修复：物化列表迭代）。
  下一轮复核包（T-A5 二次盲评）直接用 v2 管线。
  原始任务描述（保留）：核查表唯一条文+出现次数标注；"其他意见"分段；备注列加宽。
  DoD：新 docx + 脱敏自检 0 泄漏（泄漏模式清单见 `audit_docx.py` 的 LEAK 数组）。
- **T-A5 付费验证批次 + 复核人二次盲评**（主线一收口）—— ✅ **批次已取得数据**，⚠️ **P1 不可判定 / P2 有 4 条疑似误杀待复核**
  两臂（开关 off/on）× 评测集 n=8。**attempt3 于 2026-09-17 完成**：两臂各 8/8 例、rc=0、
  计费调用各 60 次、实结成本 off 1.5517 + on 1.5670 = **3.1187 CNY**（另 attempt1/2 各 26.16 上界）。
  **注入机制（attempt2 根因修复）**：`serve.py:31` `load_dotenv(override=True)` 吃掉父进程 env 注入
  → 弃用 env，改对每臂独立 `quota.sqlite` 写 `init:<key>` 校准行（实测生效，`GATE_PICKED agent_text_37max`）。
  **判据裁决（报告 `dispatch-output/ta5-arms-20260917/report-batch3.md`）**：
  - **P1 ❌ 未达标**：10 条否决条文里 **8 条在两臂都已不出现**（R1-OB 阶段已修掉），
    分母实际仅剩 **2 条**：E04 消法49（on 臂**仍出现** → **未拦截**）、E05 药品法131（on 臂已剔除 → **已拦截**）
    → 拦截率 **1/2 = 50%**，**未达 100% 通过线**。
    ⚠️ 初版误记「9 条不出现 / n=1」，**审计独立复算后更正**；错因 = v1 分析脚本 `cited()`
    的「法名 ±120 字窗口」在 E04 消法49 上匹配失败（独立正则 `《法名》第N条` 直接命中 2 次）。
  - **P2 ⚠️ 4 条疑似误杀**：E02 民法典192、E05 反不正当竞争法9/25、E05 广告法28 在 on 臂被剔除。
    **E05 决定性取证**：on 臂《反不正当竞争法》《药品管理法》整部引用出现 **0 次**（off 有 4 条）
    → 非改写条号、是整部法律引用被移除。是否构成误杀**须复核人判定**（执行侧不自行开脱）。
  - **P3 ✅ 通过（互补式打平）**：off 4/8、on 4/8；但 5 例至少一臂空终稿，**样本落在噪声内**。
  - **P4 ✅ 通过**：仅 `PLANNER_PARSE_ERROR` / `AGENT_EXECUTION_FAILURE`，均在 KNOWN 内。
  - **P5 ⏳ 待执行**（本次不可替代）。
  **关键口径事实（必须记住）**：复核材料取材自 `r1ob-prodform arm-on`（R1-OB 开启态，见
  `extract_review_materials.py` ARM_ORDER），**与 T-A5 任一模态均不等价**（实测 E01：
  r1ob-ON 引民诉法22/破21/公23，ta5-off 引民诉法122/民法典192）→ **P1/P2 不能用复核基线直接算**，
  唯一干净对照是 ta5-off vs ta5-on 差集（本报告即如此）。
  **🔴 建议：不要据此开启生产开关**，先送 P5 二次盲评（聚焦 4 条疑似误杀 + E05 双版本对比）。
  **派生待办**：① 评测集交互上限（E03/E04 因 6>5 争点上限在 off 臂空转，可比率仅 3/8）；
  ② 需 ≥2 批重复才能对 P3 下"完成率不降"结论；③ attempt1/2 的 26.16×2 为 reserve 上界。
  **历史错误结论「LongCat 下架全部模型」已全面更正**（见 `root-cause-correction.md`），
  真实根因 = p0 额度耗尽（非致命）+ 21:18–21:20 网络中断窗口（致命）+ env 注入被覆盖。
- **T-A6 R1-OB 生产开启**（T-A5 验收后）
  严格按 `docs/process-archive/project-next-execution-plan-20260916.md` §"未来开启操作手册"：compose 白名单透传两条 →
  本地实测（`dept_filter_removed` 日志出现）→ 服务器根 .env 两行 + `docker compose up -d backend` → 观测三信号
  （`dept_filter_removed` / `empty_retrieval` / `proc_misroute_flag`）→ 回滚=删两行重启。

### 独立小件

- **T-B 检索探针口径维护**：探针已是 k4+cutoff 合规口径；**下次评测批次顺带跑**（输出
  `probe-results-k4.json`，勿覆盖冻结资产）。
- **T-C 历史结论注记**：凡新批次出现 `PLANNER_PARSE_ERROR`/`QuotaExhausted` 连锁，先查
  `failover_switch mode`（transient=正常网络故障 / permanent=41364db 缺陷未修复环境）再归因。
- **T-D `writer.py:665` ruff format 失败**（2026-09-17 取证）：`unsupported_numeric_tokens`
  签名被写成跨 3 行，formatter 要求压回单行。**AST 逐提交比对确认由 T-A3(`0263bd5`) 引入**
  （`fc77e12` 及之前均为单行、通过 format）；工作树==HEAD，**非未提交残留**。
  处置：**由 T-A3 会话**执行 `ruff format agent/writer.py` 后重提（跨会话不代改，避免写冲突）。
- **T-E `chroma_db` 测试隔离**（独立票据）：见 §8「发现：测试套件写真实产物」残留③及
  `dispatch-output/pytest-full-20260917/db-write-attribution-report.md` §9.4/§10.5 ——
  需给 `rag_chain.py:112` / `knowledge_service.py:38` 加 `CHROMA_DIR` 出口，并让**有意**用真实
  语料的测试显式 opt-in。**当前隔离边界**：真实 `app.db`（读+写）与真实 `quota_used.sqlite`（写）
  已与全量测试**完全脱钩**；仅 `test_phase5.py` 两个测试仍写真实 chroma（自清理有效、只读探测无残留）。
  - **进展（2026-09-18 21:15，S0–S4 已落；S5 未做）**：出口 `rag_chain.CHROMA_DIR`（+ 单独导出
    `DEFAULT_CHROMA_DIR` 作为"未设环境变量时生产落点"的判据本体）已接两处构造点；
    `conftest.py` 与 `QUOTA_DB`/`DATABASE_URL` 同款**无条件**把 `CHROMA_DIR` 指向
    `<temp>/fazhi_test_chroma_<pid>`，并**预建** `legal_provisions_cos` 为 cosine——
    否则空目录新建集合按 chromadb 0.4.24 默认落到 **l2**，整轮快测会跑在生产不走的那条分数分支上
    （`qa_pairs` 故意不预建：真实库 metadata 就是 `{}`→l2）。需要真实语料的用例改走
    `conftest.real_kb` 显式 opt-in（构造与 `rag_chain` 逐字相同、只差目录，只读；语料缺失即 skip
    而非空库假过）；实测触达面 **12 条**：快测 3 条（`test_citation.py` 的
    `test_verify_against_real_kb` / `test_classify_answer_defaults_real_kb` /
    `test_hybrid_retrieve_expected_laws_weights_topk`）+ **慢车道 9 条**
    （`test_domain_rules` 2 / `test_retrieval_rerank` 6 / `test_statute_supplement` 1）。
    ⚠️ **方案 §2 的预注册决策规则被击穿**（规则：需真实内容的快测 >5 ⇒ 降级 B 整目录拷贝）——
    根因是原 F9 只扫了 `-m "not slow"`，漏了两类：① 经 `hybrid_retrieve` 间接读库的快测，
    ② 整个慢车道。12 条已全部挂 `real_kb`：慢车道「不 opt-in 时 9 红 → opt-in 后 12 passed」
    （`pytest-slow-lane-before-optin.log` / `pytest-slow-lane-after-optin.log`）。
    ⚠️ **12 是下界不是普查**：快测侧我只跑了本次触达的 7 个文件，`-m "not slow"` 全量未跑
    ⇒ S5 若再暴出真实语料依赖，按同一 opt-in 方式收，不再重开 A/B 之争。
    **是否仍按字面降级 B 交 Owner 裁决**，理由与实测代价见 `plan-te-chroma-isolation.md` §2 追加段
    （要点：12 条按 §3 纸面基线 1233 估约 1%（本会话未自测全量）且集中在检索线，是贴标签不是对抗；
    B 要 362MB/进程且 chroma 0.4.24
    无 client 关闭接口 ⇒ 清不干净，还会把 §10.5 的累积问题放大两个数量级、让真实语料依赖重新变隐式）。
    ⚠️ 教训锚点：**触达面扫描不能限定在快车道**——"某类测试不看"本身就是判据口径漏洞。
  - **证据**（`dispatch-output/te-chroma-isolation-20260918/`）：红→绿
    `pytest-s1-red.log` / `pytest-s2-green.log` /
    `pytest-s3-s4-final.log`（本次触达的 7 个文件快慢混跑 **84 passed**，含 12 条 real_kb）；
    watch-it-fail 两条 `pytest-witf1-no-cosine-prebuild.log`（撤预建 ⇒ cosine 断言红）、
    `pytest-witf2-no-isolation.log`（撤隔离 ⇒ 越界断言红），已复原后复跑绿；
    真实库整目录清单 `compare_manifest.py pre-S3 post-S3S4-witf` ⇒ 内容指纹逐字节相同、
    `chroma.sqlite3` cc 5461→5461、38 个文件 **mtime 一个都没动**（含 real_kb 打开真实目录的那轮）。
    `ruff check`/`format --check`/`mypy`(2 文件) 全绿；显式 `pre-commit run --files` **退出码 0**。
  - **跨会话旁证（S5 的隔离半边已有活证据，但仍不等于全量结论）**：默认层落地后到 22:25，
    TEMP 里共出现 **32 个** `fazhi_test_chroma_<pid>` 私有库（20:58–22:25，多数不是本会话的进程），
    其中 **9 个** 的 `embeddings_queue`（chroma 的**追加型操作日志**，删掉向量也留痕）记到
    **UPSERT 40 / UPDATE 40** 次真实写入，而同窗真实库清单逐字节相同、`chroma.sqlite3` cc 5461→5461
    ⇒ 别的会话的测试写盘确实发生了，只是落在了各自私有目录。取证脚本见
    `dispatch-output/te-chroma-isolation-20260918/`（`compare_manifest.py pre-S3 foreign-heavy`）。
    ⚠️ 判据更正留痕：本节初稿用「目录长到 3.3MB」当"发生写入"的证据，那是**尺寸启发式**——
    HNSW 的 `data_level0.bin` 会在首次 upsert 时一次性涨到 ~3.1MB，空库和"写完又删净"的库
    在尺寸上看不出区别（`embeddings` 表两边都是 0 行）。正确仪器是 `embeddings_queue` 计数，
    已换成上文的口径。教训：**用日志型仪器，不要用尺寸猜写入**。
  - **T-E2 已落（09-19 00:2x）：不给脚本重定向，只加"分歧即拒跑"的 CLI 守卫**。
    `CHROMA_DIR` 成为出口后，运维脚本各自硬编码路径 ⇒ 谁导出该键，备份/重建会作用在**另一个**目录
    且 `backup_data` 照常打印成功。新增 `backend/scripts/chroma_dir_guard.py::assert_matches`，
    接到 **3 个会写/会备份的脚本**（`backup_data.py`、`rebuild_embeddings.py`、`switch_embedding.py`）
    的 `__main__` 路径上。**位置是硬约束**：不能放进 `main()`、更不能在 import 期读环境变量——
    conftest 会把 `CHROMA_DIR` 指向测试临时库，放错地方等于把 `test_backup_data` 这类直调 `main()`
    的用例全钉成 SystemExit。判据：`tests/test_chroma_dir_guard.py`（6 条；接线用源码判定，
    不 import 脚本本体——它们 import 期拉 chromadb/嵌入依赖）。
    端到端实测：三脚本设分歧 env ⇒ 均 `拒绝执行` + exit 1；不设 env ⇒ `--help` exit 0。
    **未覆盖并已定性**：`gen_gate1_law_check.py:84`、`recompute_boundary_manifests.py:82`、
    `restore_drill.py:36` 三处仍是硬编码——前两个只读（最坏是分析错目录），`restore_drill` 读的是
    备份包内路径不受影响 ⇒ 按"只守卫不可逆动作"收口，剩下三处不再改动。
  - **S5 已完成（`te-s5-r4` 实测完成时刻 23:25:34，本会话自测基线）**：`run_gate_full.py te-s5-r4` ⇒
    **RUN_VALID / 1266 passed / 0 failed / 退出码 0 / 2 分 18 秒**，同轮真实库整目录清单逐字节相同、
    `chroma.sqlite3` cc 5461→5461、集合条目 10266/10266/279/21 未变。DoD 第 1/2/3/4/6/7 条全满足。
    四轮过程留痕（防后来者以为一次就过）：r1 = RUN_VALID 但 **12 failed**（我的真实语料漏计 5 条：
    `test_query_understand.py` 4 条召回断言 + 1 条隔离后只剩 `<=6` 的**空过**，已补非空断言；
    另 7 条是 R15 会话在飞的 `test_r15_version_tripwire`，`KeyError: law_version_tripwire_check`）；
    r2 = 修后 1 failed 但**源码中途被改 ⇒ RUN_VOID**（仪器按设计判废）；
    r3 = RUN_VALID 1 failed，offenders 显示那 1 条是**我自己造成的**——
    `test_log_field_whitelist` 递归扫 `backend/` 全树，而它自造的哨兵样本正落在我设在
    `backend/.ptmp-gate-*` 的 `--basetemp` 里，且失败后 pytest 保留 temp 目录 ⇒ **自反馈永久红**；
    删净我建的 13 个 `.ptmp-*` + 把 basetemp 移出 backend/ 后 r4 全绿。
    ⚠️ **给所有会话的硬规矩**：`--basetemp` 不要设在 `backend/` 内。
    §8 残留③ 至此可关闭。提交 = `44210ef`（作者时戳实测 23:28:39；9 文件：2 生产 + 6 测试 + 1 新守卫测试）。
  - **负对照（交给正在查 app.db 写入的会话，不抢其结论）**：**实测口径**（不再是 mtime 推断）——
    `run_gate_full.py te-s5-r5`（起 09-19 **00:08:57**、裁决落盘 **00:11:42**，实测 ls）在 1266 项全量的**同一轮**里对
    `backend/app.db` 与 `backend/data/quota_used.sqlite` 做前后字节 + SQLite 变更计数指纹：
    **app.db cc 10731→10731、quota cc 2→2，sha256/size/mtime 全同**，同轮真实 chroma 清单也逐字节相同
    ⇒ 走 conftest 的全量测试 lane 对三件真实产物**零写入**，一次跑齐、同一仪器、同一轮次。
    早前 23:30:38 那次定向跑（`test_phase5`+`test_chroma_isolation`+`test_citation`）是同结论的小规模版。
    执行书 §8 记录"全量每次都写真实 app.db（21:04/21:28/21:36 三命中）"与本对照不矛盾——
    差别应在**入口**：走 conftest 的 pytest 与不走 conftest 的驱动（外部 harness/脚本/服务）不同源。
  - **r6 = 当前 HEAD 的全量基线（G1 收口，09-19 01:2x 实测，未新跑一轮）**：
    `run_gate_full.py te-s5-r6`（裁决落盘 **00:41:40**，实测 ls）⇒ **RUN_VALID / 1272 passed /
    18 deselected / 0 failed / 退出码 0 / 2 分 40 秒**，同轮真实 chroma 整目录指纹前后相同
    （`71e7a7a4…-n38-s362449354`）、`chroma.sqlite3` cc 5461→5461、条目 10266/10266/279/21、
    **app.db cc 10784→10784、quota cc 2→2**。当前 HEAD = `105907b`（`git rev-parse --short HEAD`）。
    ⚠️ **边界（写清楚，别让下一会话以为我重跑过）**：本条收口后又落了 `61fbd11`（01:30:07，
    仅改 `tests/test_chroma_isolation.py` 的 docstring，2 行 +1/-1，pre-commit rc=0）⇒
    基线归属外推了一个"纯注释提交"。**没有**任何测试断言该文件的 docstring 文本，但这一条是
    **静态推理不是实测**（本会话此后跑不了 pytest），故 `61fbd11` 上的全量绿**仍未观测**。
    **为什么 r6 的计数可以记在 `105907b` 名下（内容同一性证明，不靠"我感觉没改"）**——
    三步都是**手工实测**，命令与结果一并留下（本会话此后跑不了 python，这三步不依赖它）：
    ① `git status --porcelain --untracked-files=no -- backend` ⇒ **0 行**（backend 全部跟踪文件
    工作树 == HEAD）；② `git status --porcelain --untracked-files=all -- backend | grep '^??.*\.py$'`
    ⇒ **0 行**（没有未跟踪的 `.py` 会改变收集面）；
    ③ r6 事后快照的 234 个 `.py` 与当前工作树逐字节比 ⇒ 差异只剩
    `tests/test_gate2_runner.py` 与我自己 01:30 的 docstring 改动；对该文件再单独验：
    `git show HEAD:./tests/test_gate2_runner.py | sha256sum` = `6cb4c4c9…` **== r6 快照里记的值**
    ⇒ **内容同一，只是换行符从 LF 变回了 CRLF**（本机 `core.autocrlf=true`，git 因此判它"干净"）。
    ⚠️ **本会话在这一步踩过两个自己造的坑，都记下**：
    (a) 第一版 `sha_tree_diff.py` 拿 `git rev-parse HEAD:path` 的 **sha1** 去和快照的 **sha256** 比
    ⇒ 恒不等 ⇒ 把"已提交"永远标成"他人在途"，本条原先那句"它是别人未提交的在途编辑"就是被它带错的；
    (b) 我引用命令时写成 `git status --porcelain -uall（全仓、含未跟踪）只列出这 1 个脏文件`——
    实际跑的是 `--untracked-files=no`，且**全仓 -uall 有 8272 条未跟踪条目**，那句话是错的，已改。
    工具已重写（同时算 raw 与 LF 归一两种哈希、判脏只用 `git status`），
    但**重写后本会话未执行**（python 被拦），其逻辑等价性由上面 ①②③ 手工三步背书。
  - **phase2-g1 = RUN_VOID，判废理由已独立复核**：起 **01:02:49**、裁决落盘 **01:06:29**，
    末行同样是 `1272 passed / 18 deselected / rc 0`，但仪器记录"跑中途源码被改 (1):
    `tests/test_gate2_runner.py`"（该文件 mtime **01:04:30** 正落在窗口内）⇒ 按判据作废、不据其声称绿。
    **本轮仍然可用的部分**：隔离判据与 VOID 无关——同轮真实 chroma 指纹前后相同、
    `app.db cc 10784→10784`、`quota cc 2→2` ⇒ 默认隔离在 `105907b` 上再次成立。
  - **phase2-g2 = 真·实测基线（09-19 02:06:04 落盘，Owner 02:0x 放行后本会话自跑）**：
    `run_gate_full.py phase2-g2` ⇒ **RUN_VALID / 1272 passed / 18 deselected / 0 failed /
    退出码 0 / 2 分 20 秒 / 源码中途变动 0 个**。同轮真实 chroma 整目录指纹前后相同
    （`71e7a7a4…-n38-s362449354`、cc 5461→5461、条目 10266/10266/279/21）、
    **app.db cc 10784→10784、quota cc 2→2**。
    **归属哪棵树已由时序钉死**：轮次跑在 **02:03:0x–02:06:04**，而当前 HEAD `4465080`
    的作者时戳 = **01:44:27**（早于起跑 19 分钟），且跑完 `git status --porcelain -uno` **全仓 0 行**
    ⇒ 工作树 == HEAD == 本轮所测。G1 的 DoD 至此**按字面满足**，上一条 r6 外推论证降级为旁证。
  - **G2 线索（同批实测，跨轮 app.db 变更计数）**：`10731`(00:11:42 r5) → `10784`(00:41:40 r6) →
    `10784`(01:06:29 g1) ⇒ **30 分钟窗口内 +53 次写**，而**每一轮内部 cc 都不动**
    ⇒ 写者**不是**走 conftest 的测试 lane。这是"打开/写入真实库的非 pytest 入口"的第一条量化证据。
- **T-F 复测前置条件未满足**（2026-09-17 23:20 复核）：容器库 `backend/data/app.db` 答案数
  仍为 **2031**、mtime 停在 02:37 —— 19 小时内 **0 新增**。提示词修复效果复测需 ≥200 **新**答案，
  当前零流量 ⇒ 该待办**阻塞于流量**；宜改用评测批（`gate2_runner`）驱动，而非等待自然累积。
- **T-G P5 严格模式复评**（**建议**，2026-09-18）：本次 P5 复核人**主动声明防锚定流程失效**
  （单文件版使第四、五部分在第一阶段前即被读入）。若该结论要用于**生产开关决策**，
  建议用 **多文件版（`交付包.zip`）** 重跑一次盲评——零付费、只花复核人时间，可消除该项方法学缺陷。
  同时修模板：**`reviews` 条目 `version` 设为必填**（本次返回件丢该字段，只能按数组序对齐）。
- **T-G-2 盲评粘贴包（2026-09-18 01:50，用于「无本地文件访问权、无项目记忆」的复核人）**：
  `outputs/p5-review-20260917-盲评粘贴包/`（9 文件：说明与规则 + 前置 + 案例1–5 + 第二阶段 + 回执模板；
  每块 382–6,897 字符，单条消息可贴完）。
  **为什么比 zip 更硬**：复核人**无本地文件访问权** ⇒ 第二阶段内容**它看不到**，
  冻结由「交付方贴不贴」**物理强制**，不再依赖自律。
  **已自检**：① 材料块逐字取自源材料且**按序拼接 == 源（逐字节）**；② 第一阶段 7 文件中
  第二阶段独有长句命中 **0**；③ 匿名扫描 **0 命中**。
  使用方法（**勿发**）：`outputs/p5-review-20260917-盲评粘贴包-使用方法（勿发）.md`。
  **两条建议**：优先**人类**复核人；若用 AI，**换一个与上轮不同的模型**
  （避免同一模型既参与生成又自评的同频偏差）。
- **T-H 「过度保守致核心问题落入未能覆盖」行为修复**（复核发现，2026-09-18）：
  案例1·乙(on) 把用户核心问题「能否起诉」列入 `UNKNOWN_FACT_ID` 未能覆盖、全文未引民诉法122条，
  复核人评「属过度保守」。**与 E03/E04 的预算问题不同源**（预算已由并行会话修复），
  属 coverage/未决事实门限的判据问题。**建议单独立项**（比开开关收益大）。
- **T-I T-A6 开启判据（正式化，2026-09-18）**：T-A6 **维持不开启**。将"何时可开"写成可测判据：
  ① P1 有**可比分母**且拦截率达标（E04 的 off 版需先有终稿）；② on 臂**不得引入新的实质缺陷**
  （当前存在过度保守 + 主体类型错配「存在」）；③ 复核须为**防锚定有效**的一轮（见 T-G）；
  ④ P3 完成率需 **≥2 批**重复。四条齐备方可提交 Owner 决策。
  ⑤ **下一批评测（判据实测批）的 on 臂开关清单**（缺一 ⇒ 判据②无法成立）：
  `entity_precision_check` / `numeric_matching_v2`（主线被测开关）、
  `agent_partial_delivery_enabled`（部分交付）、
  **`agent_writer_corrective_retry_enabled`**（`1f73bb5` 新增——**不开启则「过度排除」缺陷照旧复现**，
  批次会白花钱并得出"修了没用"的错误结论）。
  **off 臂维持全关**，保证对照可比。
- **T-J KB 缺《食品安全法》第148条**（P5 两轮均涉及十倍路径，2026-09-18 登记）：
  案例5「退一赔十」被排除的另一成因是 KB 无 148 条——writer 无法引用 KB 外法条（防幻觉边界，**不应改**）。
  ⇒ 处置与《诉讼费用交纳办法》同例：**待 Owner 提供官方文本后入 laws_raw**，再重建检索索引。
  在此之前该路径的排除属**正确行为**，不得按"过度保守"计。

### 负面清单（已决定不做，防范围蔓延）

- V8 剩余人测（Shift+Enter 等 4 项）——单测已覆盖；
- 检索召回主动重跑——P4 触发器被动等待；
- R1-OB 深化投入——E04 深挖已确认能力边界（词表盲区），不再投入；
- 留出集专门付费重跑——不救数纪律；
- `.git-backup-20260916/` 清理——保留（git 对象唯一回退备份）。

> **2026-09-18 补充（防"悄悄推翻既有决定"）**：P5 复核发现 **5 处跨域引用/法律关系错配**
> （off：刑诉法106条用于民事期限〔E01〕、海事请求保全·责任保险〔E02〕、消保法54条〔E05〕；
> on：消保法49·农村土地承包仲裁法37·医疗纠纷条例36·国家赔偿法15〔E04〕）。
> 这些**落在「R1-OB 深化」已被判"不再投入"的范围内**（同属词表/域过滤盲区）。
> ⇒ **不因新证据自动重开**；若要动，须先由 Owner 明确推翻上条负面清单并说明新证据为何足以改变判断。
> 本次只如实留档，**不新增投入**。

## 5. 验收判据（T-A5 冻结，不得修改）

| # | 判据 | 通过线 |
|---|---|---|
| P1 | 12 项历史"否"拦截率（开关开） | 100% |
| P2 | 43 项"认可"误杀率 | 0 |
| P3 | completed / 恰当率 | 不低于对照臂 |
| P4 | 新失败码 | KNOWN 外即 STOP 排查 |
| P5 | 复核人二次盲评 | 三类系统性错误复发数 = 0（或 Owner 接受残余并留痕） |

## 6. 汇报与存档约定

- 完成即追加本文件任务条目状态 + `docs/process-archive/project-next-execution-plan-20260916.md` §7 + 工作日志
  （`.workbuddy/memory/2026-09-16.md` 追加式）；
- 每任务完成做 show-your-work 自审（独立方法复核，勿用同源复算）；
- 代码改动走提交 + 第六轮之后的下一轮快照同步（模板见 §3）；
- 与 Owner 沟通：极简命令式、结构化表格、诚实标注不确定项、复核/审计结论单独汇报。

## 8. 执行记录（追加式，不改上文）

### T-A0 完成（2026-09-17，零成本离线）

- 证据目录：`dispatch-output/ta0-numeric-trace-20260917/`（12 份 state dump + 12 个分析脚本
  + report.md，含 showyourwork_recheck.py 复现脚本 13/13 PASS）。机理复算用真实 tokenizer
  （backend/agent/writer.py，离线 import）。
- 分类结果：11 次 NUMERIC 拒绝全 (a)——形态归一缺陷（主）+ 跨争点白名单缺失 + 未决事实
  脱敏副作用；(b) 仅受理费金额（KB 缺《诉讼费用交纳办法》，受控计算需 Owner 授权补源）。
- 关键事实：民法典188（三年）已被检索并挂时效争点（证据挂载关系只在 agent_evidence 表，
  state_json.evidence 无 issue_id 字段——后续分析勿按后者分组）。
- T-A3 指向：(a) 路线成立（归一 + 白名单）；(b) 仅受理费金额。层级 3 仍不做。
- 本轮零代码改动、零生产影响（纯只读诊断 + 证据目录新增）。

### T-A1 预标+自查完成（2026-09-17；LLM 付费调用 38 次已授权额度内）

- 对象口径勘误（留痕）：金标 53 entries = 38 条唯一 (law,article)，跨案例重复 15 条；
  标注对象 = 38 unique（JSON 键唯一性决定），53 entries 全覆盖。
- 产出：`backend/knowledge_base/law_annotations.json`（键=`{短法名}#{中文条号}`，
  与运行时 evidence.source_ref 同构；四字段 schema+词表冻结于 _meta）。
- 流程：derive（38/38 解析，含中文条号转换器两次修正：千位支持、10-19 无"一"标准形态）
  → LLM 预标（temperature=0，每条 1 次+解析失败重试 1 次，0 failed，76s）
  → 程序自查（H1–H5 硬检查全 PASS；词表零外溢；chapter 比对空白归一为检查修正、标注未动）
  → 抽验材料 `reviewer-sample.md` 14 条（36.8%，系统抽样 ∪ 2 条锚点分歧强制入选）。
- 分歧候选（预注册锚点法）：民法典496 条、消保55 条（条文混合形态，两判皆可辩护）——待复核裁决。
- 成本：38 次 text 档调用（响应未带 usage_metadata，token 未能精确计量；时长 76s）。
- 下一步：复核人回填 → 分歧裁决留痕 → T-A2 verifier 校验实现。

### T-A1 复核收口（2026-09-17 晚；主线一首项闭环）

- 复核回填：56 项判定 53 是 / 3 否（94.6%）；chapter 14/14、direction 14/14（含 2 条两可预注
  经重点复核维持预标）；3 项"否"全在 subject_types（主体完整性缺陷）。
- 修正（`apply_review_fixes.py`，两份文件同步）：1179 → [自然人,法人]；693 → [债权人,债务人,保证人]；
  686 → [债权人,保证人]。词表 v2 +保证人/受害人/非法人组织。
- 修正后自查 H1–H5 全 PASS + show-your-work 10/10（双份一致/变异×5/抽样/锚点）。
- 分歧裁决与建议采纳：`ta1-annotation-20260917/disagreement-verdicts.md`（权威留痕）——
  invalidity 方向值 → T-A2 设计输入；主体完整性校验 → 下次预标自查规则。
- **T-A1 闭环。下一项 = T-A2 verifier 校验实现**（新原因码 SUBJECT_TYPE_MISMATCH /
  CLAIM_DIRECTION_REVERSED、开关 `entity_precision_check` 默认关、四组测试、全量门禁）。

### T-A2 实现记录（2026-09-17 晚；D1 选项一 / D2 / D3 已拍板）

- **标注扩充批**（D2/D3）：缺口 31 条派生（review-verdicts 独立引用 33 ∖ 已标注）→ LLM 预标
  31/31（qwen3.7-max，priority 1；含 `_ta2.direction_subjects`）→ 主体完整性自查
  （duty/right 词逐字在条文内；7 条违规：5 条定向 relabel + 2 条置空 fail-open）→ 合并
  69 条两份同步。修正标注 2 处：787 主体系定作人/承揽人（预标错误）、102 债权人移 right 侧。
- **通道事故与纠正（Owner 指正）**：dashscope 403 FreeTierOnly 后误跳 siliconflow；
  registry 逐条实测仅 priority 0 额度耗尽、priority 1-5 可用 → 改 qwen3.7-max 重跑。
  siliconflow 尝试产物留证 `ta2-annotations.siliconflow-attempt.bak.json`。
- **挂接层修正（实现期发现）**：verifier 终态失败违反 P3（service.py:466）→ 改挂 writer
  渲染循环 citation 检查同位（争点级 uncovered，同 NUMERIC 形态），completed 语义不变。
- 新文件：`backend/agent/entity_precision.py`（机制A 事实类型词域 / 机制B duty-right 错位 +
  角色同义归一表；lru_cache；延迟导入破循环）。开关 `entity_precision_check` 默认关。
- **实测覆盖 3/10 拦截**（低于设计稿预估 5-6，诚实降级）：机制A 拦 E01 独资42/合伙102、
  机制B 拦 804；残余 7 项（6/49 归 R1 线——实体法 49 需 domain_tags；128/131/801/802/807
  需 domain_tags/争点机制）——固化于测试断言，T-A5 后 Owner 再议。
- 测试：`tests/test_entity_precision.py` **30 passed**（组1 拦截 / 组2 零误杀 23+簇 /
  组3 开关关 / 组4 watch-it-fail）；`watch-it-fail.txt` 落盘（on 拦/off 放行同输入对比）；
  ruff/format/mypy 全绿（改动 6 文件）。全量门禁：运行中，结果待补。

### B1 豁免留痕（2026-09-17，提示词审计修复 f889da3 系列）

- 条目：`prompts.py` 属冻结物清单（code-review-standard.md:80 B1），提示词架构审计
  修复（f889da3 及其后续提交）使其相对锚定候选态哈希漂移非零。
- 豁免理由：Owner 授权链完整（2026-09-17 只读审计 → grilling 冲突裁决 → Owner 明示
  「继续执行任务」）；改动仅为提示词字符串语义，不含可执行逻辑；Agent Path 零流量
  （agent_enabled=False），零生产影响。
- 影响与义务：锚定候选哈希与工作树不再一致，下次候选冻结前须重算冻结物哈希并
  重新锚定；重算完成前不得开启付费验证轮。

### 全量门禁回归（2026-09-17 晚，独立会话复现）

- **触发**：T-A2(`fc77e12`) / T-A3(`0263bd5`) 提交后，验证主线未回归。
- **结果（三项）**：`pytest -m "not slow"` = **1155 passed / 18 deselected**（411.64s，rc=0）；
  `ruff check .` 全过（222 files）；`mypy .` = **0 issues in 69 files**。
- **口径更正（重要）**：旧基线 `1101`（41364db 时代）**作废**，含 974/990/992 一并禁止引用。
  当前基线 = **1155**（not slow 口径）。1101→1155 为 T-A2/T-A3 测试增量，**非回归**。
- **`ruff format --check` 唯一失败项归属已取证**：`agent/writer.py:665`
  `unsupported_numeric_tokens` 多行签名 → AST 逐提交比对确认由 **T-A3(`0263bd5`) 引入**
  （`fc77e12` 及之前均为单行、通过 format）。**非本会话改动、非未提交残留**（工作树 == HEAD）。
  处置：留待 T-A3 会话 `ruff format agent/writer.py` 后重提，避免跨会话写冲突。
- **仓库完整性**：fsck 报 6 个缺失对象，逐个反查**全部澄清为非问题**——5 个 dangling
  （`rev-list --all` 不可达），1 个 `01d9b1b2` 系 **replace-ref 虚警**（被
  `refs/replace/01d9b1b2→1ede452` 屏蔽，`cat-file -t` 实际 rc=0）。仓库非浅克隆。
  副作用：`git blame` 遇 replace 遮挡段会报 `unable to read tree`，改用 `git diff`/`git show`。
- **快照链状态刷新**：远端真实 tip = **`5dba88f`**（并行会话已推 T-A3 批），其提交信息自报
  「1155 passed / 0 failed」与本轮**独立复现**数字逐位一致 → 交叉验证成立。MEMORY.md 原记
  链尾 `cd7d232` **已过期**。本地 `origin/master`(=15562fc) 是 2026-08-25 老引用，不可信。
- **本轮未做**：未推送（远端已最新）、未修 writer.py format、未跑 slow 慢测、未改任何源码。
- 报告全文：`dispatch-output/pytest-full-20260917/regression-report.md`（附 4 个只读取证脚本）。

### 发现：测试套件写真实产物（2026-09-17 晚，取证完成 / **已修复并验证** `76c1eea`）

- **触发**：回归期发现 `backend/app.db`（裸机库）mtime 在 pytest 窗口内变动，容器库则静止。
- **已确证**：全量 pytest **每次都写真实 `backend/app.db`**（3/3 命中：21:04:15 / 21:28:49 /
  21:36:00）。写入**逻辑中性**——19,939,328 字节仅 46 字节不同（页1 的 file change counter /
  version-valid-for + 页 4868），**11 张表行数与内容哈希全同 ⇒ 无数据污染**。页 4868 经
  `dbstat` 查明属 `qa_candidates` leaf 页。
- **同一运行还写**：`backend/chroma_db/`（HNSW 段 + 206MB `chroma.sqlite3`）、
  `backend/data/quota_used.sqlite` —— 三者构成一次级联（21:36:00 → :07 → :15 → :43）。
- **初版假设（⚠️ 部分被证伪，留档以示诚实）**：曾推断根因是「`main.py:158` 模块级 `init_db()`
  ＋ `database.py:9` 无 `DATABASE_URL` 回落 ＋ `conftest` 未固定 `DATABASE_URL` ＋ `db` fixture
  非 autouse ＋ 多个测试 `TestClient(main.app)` 只 override `get_current_user`」。
  **实测推翻了两条**：① 单变量实验证明 `import main`（含 `init_db()`）**不写该库**
  （迁移幂等，cc/mtime/size 全不变）；② 真凶不是 `TestClient` 链，而是**单个测试直接调
  `SessionLocal()`**。上述环境因素确是「让该测试能污染生产库」的**必要条件**，但**不是写入路径**。
- **真凶已定位（插件 v3，hook 级前后检查点）**：`tests/test_knowledge_service.py::test_create_candidate_
  auto_approve` —— 直接 `database.SessionLocal()` 写真实 `backend/app.db`，**全库唯一写事件**
  （`cc +3`）。现象全部对齐：`qa_candidates` 页 ✓ / `cc +3`（2 INSERT + 1 DELETE）✓ /
  逻辑内容全同（`finally` 自删，净零行）✓ / 尺寸不变（页回 freelist 复用）✓。
  次要因素：该文件自称「slow，真实 chroma」，但此测试**漏打 `@pytest.mark.slow`** → 落入快测集。
  v2 的线程轮询**失败**（只给"最后开始的测试"，落到纯单元测试 → 标签不可信）；
  v3 才钉准。⚠️ pytest 9 陷阱：`pytest_runtest_protocol` 不可用 `hookwrapper`，写成裸生成器会
  **终止全部测试**。
- **✅ 已修复并验证（提交 `76c1eea`，1 文件 / +11 −5）**：改用 conftest 现成的 `db` fixture
  （tmp_path 建库 + engine/SessionLocal 替换）。**watch-it-fail 配对**：单测试修复前
  `cc 10728→10731(+3)` / 修复后 `cc 10731→10731` 且无写入事件；**全量 1155 passed /
  18 deselected / rc=0（389.80s）**，全库 `WRITE_BY_TEST` 事件 **= 0** ⇒ 写入消除且无回归。
- **残留**：① ~~collection 期 `import main`→`init_db()` 仍**连接**真实库~~ → **已关闭**
  （`2412acd` pin `DATABASE_URL`；实测真实 app.db 的 `[CONNECT]` 由「每次运行 1 条」降为 **0 条**）；
  ② ~~`QUOTA_DB` 未固定~~ → **已修**（`c22236d`）；③ ~~`test_phase5.py` 两个测试仍写真实 chroma
  （见下），`test_citation.py::*_real_kb` 仍读真实 chroma —— **仅剩这一项**~~
  → **已关闭（`44210ef`，作者时戳 23:28:39，T-E）**：`CHROMA_DIR` 出口 + conftest 默认层
  把测试指向 `<temp>/fazhi_test_chroma_<pid>`，17 条真实语料用例改显式 `real_kb` opt-in。
  验收 = RUN_VALID 全量轮 **1266 passed / 0 failed**，同轮真实库 38 文件整目录清单逐字节相同、
  `chroma.sqlite3` cc 5461 未动。**至此本段三产物（app.db / quota / chroma_db）全部脱钩。**
- **✅ 隔离已下沉到 conftest 默认层（`2412acd`，conftest +21）**：经 systematic-debugging 找到
  **类根因 = 「隔离是逐产物 opt-in、没有任何一处保证默认隔离」**（三产物三种机制泄漏：
  绕过 fixture / 声明了环境变量却没设 / 路径硬编码无出口）→ 故把隔离下沉到 conftest 共享点。
  **最小实验**（单变量只加 `DATABASE_URL` 一行）：**1155 passed / 18 deselected / rc=0（112.66s）**
  ⇒ 原「会破坏依赖真实种子数据的测试」的风险判断**被实测证伪**。
  **非平凡验证**：临时库 `fazhi_test_app_<pid>.db` **含 11 张迁移后表**（证明 pin 真被走到）；
  真实 app.db 的 `[CONNECT]` **0 条**；真实库 cc/mtime_ns 逐位不变、quota 0 写。
  与成文实践一致：`docs/project-quality-guide-20260914.md:302` 明确要求隔离
  DATABASE_URL/QUOTA_DB/COVERAGE_FILE（此前只落在一性脚本，未落 conftest）。
- **两轴代码审查（`0263bd5...HEAD`）**：Standards 无硬违规（QUOTA_DB 无条件赋值判为**有意偏离**）；
  Spec 轴指出 2 处 → **均已修**（§4 的 chroma 声明已写进 conftest；§4「quota 未做」的滞后表述已同步）。
  ⚠️ 子代理一条附注（称 `test_contract_file`/`test_phase3` 的 `SessionLocal()` 未隔离）**经复核证伪**
  ——那 6 处所属测试均接收 `client` fixture、已隔离。**同一失效模式本会话第三次**
  （方法覆盖不到处被当成"不存在"）⇒ 凡"扫描结果"必先核验归属。
- **✅ 配额库已隔离（提交 `c22236d`，conftest +7 行）**：`quota_store._connect()` 的
  `PRAGMA journal_mode=WAL` 与 `_ensure()` 的 `CREATE TABLE ... commit()` **本身就是写**，
  故原「总额设 0」只挡扣减、挡不住建表/期刊模式切换（快照：真实库 mtime=22:04:15 落在跑批窗口内）。
  改为**无条件** `os.environ["QUOTA_DB"]=临时库`（不用 setdefault，防 shell 残留指回生产）。
  **非平凡验证**：临时库 `fazhi_test_quota_<pid>.sqlite` 存在且表 `quota` 有 2 行
  `('m2',5)/('m1',10)` ⇒ 路径确实被走到且落临时库；真实库 mtime 仍 22:04:15、18 行用量完好。
- **三产物监视全量（`dbwatch4_plugin.py`，1155 passed / 18 deselected / rc=0）**：
  `app.db` **0** 写 ／ `quota` **0** 写 ／ `chroma` **2** 写（已归因）。
- **chroma 写入归因**：均为 `tests/test_phase5.py`（`test_admin_knowledge_add_contract_with_time_fields`
  经 admin 端点写入后 `finally` 删；`test_retrieval_excludes_expired_but_admin_test_sees_it`
  直接 `add_text`），source=`test_phase5_tmp`。**与 app.db 同一失效模式**（隔离了 DB 漏了 KB）。
  文件 size +16KB/轮且**不回落**。
- **chroma 有意不修（诚实利弊）**：路径在 `rag_chain.py:112` / `knowledge_service.py:38`
  **硬编码无出口**；全局重定向会打挂 `test_citation.py` 的 real_kb 测试（**未打 slow 标记**
  ⇒ 项目有意在快测集用真实语料）；只加环境变量出口亦不够（import 期读路径，无法按测试切换）。
  ⇒ 正解需加 `CHROMA_DIR` 出口 + 让有意者显式 opt-in，属**设计变更**，留独立票据。
  **只读探测确认真实 KB 无测试残留**（4 集合全净：10266/279/21/10266，source 全为真实法律名），
  自清理一直有效 ⇒ 风险有界（add/delete 间崩溃会永久入库 + 索引只增不减）。
- **⚠️ 思考纪律留档**：`TestClient(app)` 出现在某文件 **≠** 该文件触达外部资源 —— 曾凭
  「TestClient 行号邻近」误判 `test_capability_gates.py` 调 `/healthz`，实际它 `:112` 调
  `/api/health`（纯能力开关）**无辜**。**与 `/models`「列表不含 = 已下架」是同一类错误：
  把推断写成确证。**判定资源触达必须**读到具体请求行**。
- **未解释观察（不作声明）**：本轮 121.16s vs 此前 341.59–411.64s，原因未查明
  （候选：并行会话 T-A5 抢 CPU；或真实 WAL 配额库短连接竞争消失）⇒ **不得当作修复收益**。
- **认知留档**：**逻辑内容一致 ≠ 没写过**——自清理测试先插后删 → 净零行，但 cc/字节已变。
  判「有没有写」看 change counter / mtime / 字节 diff，不能只看逻辑内容。
- 报告全文：`dispatch-output/pytest-full-20260917/db-write-attribution-report.md`（§7 为修复与验证）；
  可复用取证工具 8 个 + 新 skill `~/.workbuddy/skills/pytest-file-write-attribution/`。

### T-A5 批次执行（2026-09-17 晚，第三次尝试成功）—— ✅ 取得数据，⚠️ P1 不可判定 / P2 待复核

- **触发**：Owner 授权后执行 T-A5（两臂 × 评测集 n=8）。
- **attempt1 结果**：**aborted @ 3m18s，零有效数据**。off 臂 E01–E05 全 `PLANNER_PARSE_ERROR`、
  `final_chars=0`、`agent_completed=false`；on 臂未启动（失败即停该臂纪律）。
- **🚨 根因更正（重要，此处推翻本段初版结论）**：初版写"LongCat 平台已下架全部配置模型"，
  **该结论错误**，原因见 `dispatch-output/ta5-arms-20260917/root-cause-correction.md`：
  1. **探针打错平台**：curl 打 `LLM_BASE_URL`（LongCat），但 `LLM_MODELS_JSON` 每模型自带
     `provider: "dashscope"`，`llm_registry._load` 按 provider 覆盖 base_url →
     生产实际走 `https://dashscope.aliyuncs.com/compatible-mode/v1`；
  2. **误读 `/models`**：该端点只列平台自有模型，"列表不含"≠"已下架"，推断被写成了确证。
     Owner 纠正原话：**「再尝试一下，这些模型应该没下」**。
  **正确取证（走生产调用路径 + 打印真实 `openai_api_base`）**：6 模型**全部存在**，
  仅 priority 0 `agent_text_37max0608` → 403 `Free quota exhausted`，其余 5 个 OK。
- **真实根因（双因素）**：
  1. **p0 额度耗尽**（`AllocationQuota.FreeTierOnly`）：本地 quota 为 `quota_total=100万`
     且无 override → 进程内仍判"可用" → 首跳必然白烧一次 403。`RegistryFailoverTransport`
     正确处理（`mark_depleted` 后换模型），**单看这一项不致命**；
  2. **21:18–21:20 真实网络中断窗口**（**致命**）：判读依据 —— 若只是额度问题，attempt 2
     应成功；但 attempt 2–6 全 `APIConnectionError`。21:19 后首跳即 `APIConnectionError`
     而非 403 ⇒ 连接层已断。`net_health check` PASS 是因探针端点 ≠ LLM 端点。
- **防误归因（三条分别排除）**：
  1. **非 41364db 缺陷**：attempt1 = permanent（语义正确）→ 后续转 transient **不 mark_depleted**，
     E02–E05 未被连锁标死、仍正常发起请求 —— **修复在真实故障现场再次得到验证** ✅；
  2. **非两开关**：失败发生在 **planner 阶段**，早于 writer/verifier（开关作用位置）；
  3. **非"模型下架"**：已由生产路径复测推翻（见上）。
- **实测损失**：attempt1 账本 1 条 `event=finished` = **26.16 CNY**（403 无 usage，按 reserve
  上界结算；平台侧可能未计费——如实标注为**上界**）；attempt2 同额。合计上界 **52.32 CNY**。
- **attempt2（注入失效，已止损）**：为绕开 p0，第一版注入"改了 priority 的 `LLM_MODELS_JSON`"，
  但 `serve.py:31` 的 `load_dotenv(backend/.env, override=True)` 用 `.env` 值**覆盖**了父进程注入
  （`.env` 确实含该键，1195 字符；记忆里"不含"是错的）→ 注入从未生效，`EVALUATION_READY` 与账本
  首跳仍是 p0 耗尽模型。证据 `arm-off-attempt2-injectfail/`。
  **教训：注入环境变量前必须先确认宿主的 dotenv 覆盖语义（override=True 会吃掉父进程注入）。**
- **attempt3（✅ 成功，取得数据）**：改用**不依赖 env 的通道** —— 对每臂专用 `quota.sqlite` 写
  `init:<key>` 校准行（`quota_store._INIT_PREFIX`；`registry._load` 里 `initial_override` 优先于
  `initial_used`）→ p0 启动即 `quota_left=0` → `depleted` → `unavailable` → `pick` 跳过 →
  落到 p1 `qwen3.7-max`。零 `.env` 改动、零代码改动、每臂独立库、完全可逆。
  **实测验证**（`verify_seed.py`）：`p0 left=0 unavail=True` / `PICKED agent_text_37max` / `INVOKE_OK`；
  `health_gate` 两臂均 5/5 通过。**两臂各 8/8 例、rc=0、各 60 次计费调用**；
  实结成本 off **1.5517** + on **1.5670** = **3.1187 CNY**。

### T-A5 批次判据裁决（2026-09-17 第三次尝试，报告 `report-batch3.md`）

- **P1 ❌ 未达标**：10 条否决条文里 **8 条在两臂都已不出现**（R1-OB 阶段已修掉），
  分母实际仅剩 **2 条**：E04 消法49（on 臂**仍出现** → 未拦截）、E05 药品法131（on 臂已剔除 → 已拦截）
  → 拦截率 **1/2 = 50%**，**未达 100% 通过线**。
  ⚠️ **初版误记为「9 条不出现、n=1、1/1=100%」→ 审计（show-your-work）独立复算后更正为 8 条 / 1/2**。
  错因：v1 分析脚本 `cited()` 的「法名 ±120 字窗口」在 E04 消法49 上匹配失败
  （独立实现用正则 `《法名》第N条` 直接命中 2 次）。**教训：聚合判定必须用独立实现复算。**
- **P2 ⚠️ 4 条疑似误杀**：E02 民法典192、E05 反不正当竞争法9/25、E05 广告法28 在 on 臂被剔除。
  **E05 决定性取证**：on 臂《反不正当竞争法》《药品管理法》整部引用出现 **0 次**（off 臂 4 条）
  → **非改写条号、是整部法律引用被移除**。同时 on 臂新增消法11/40（复核亦认可）→ 属替换。
  是否构成误杀**须复核人裁定**。
- **P3 ✅ 通过（互补式打平）**：off 4/8、on 4/8（off 有 C05 无 E04；on 有 E04 无 C05）
  → 差异落在噪声内，**不足以支撑"开关无害"强结论**。
- **P4 ✅ 通过**：仅 `PLANNER_PARSE_ERROR` / `AGENT_EXECUTION_FAILURE`，均在 KNOWN 内。
- **P5 ⏳ 待执行**。
- **口径事实（关键）**：复核材料取自 `r1ob-prodform arm-on`（R1-OB 开启态，
  `extract_review_materials.py` ARM_ORDER），**与 T-A5 任一模态不等价**（E01：r1ob-ON 引民诉法22，
  ta5-off 引民诉法122）→ P1/P2 唯一干净对照是 **ta5-off vs ta5-on 差集**。
- **可比性**：8 例中**仅 3 例两臂均有终稿**（E01/E02/E05）。E03/E04 在 off 臂因
  **planner 争点上限 6>5 触发澄清环**、runner 应答规则 `no_rule_match` 无法匹配而空转（评测集问题）。
- **分析脚本自身 3 个 bug 已修（每个都有红→绿证据，若不修会得出完美假绿结论）**：
  ① `_cn` 中文数字算错（「二十二」→33，根因 `enumerate("零〇一…")` 使「一」=2）；
  ② `presence` 用 `(case,law,art)` 三元组查 `cites_of` 返回的 `(law,art)` 二元组集合 → 全 False；
  ③ `verdict` 实测取值为「**不认可**」而非执行书口语的「否」→ 修正后分母 10/23 正确。
- **🔴 结论建议**：**不要据此开启生产开关**（P1 零增益 + P2 4 条疑似误杀未裁定），
  **先送 P5 二次盲评**（聚焦 4 条疑似误杀 + E05 双版本对比）。
  另：需 ≥2 批重复才能对 P3 下结论；E03/E04 的澄清环问题应单独修。

### T-A5 / P5 重点复核材料已备（2026-09-17，尚未人工验收）
- 交付：`outputs/p5-review-20260917/` 中第一阶段匿名全文与判读表、第二阶段补充判读、匿名回执模板（Markdown/JSON；未生成 Word）。
- E01–E05 共 10 个版本槽位：7 份非空终稿、3 个空槽明确标注材料不足；四条重点引用仅在第二阶段询问。E01 纳入主体错配复核，E04 单版只作内容审查，不作两臂比较。
- 每案例独立随机甲乙映射；来源、原文 SHA256、映射和验证记录单独保存于 `dispatch-output/ta5-arms-20260917/p5-private/`，不得提前转发复核人。
- 自检：7 份全文从交付 Markdown 还原后与 checkpoint 逐字一致；10 个映射齐全；21 行三类错误问卷；匿名规则扫描 0 命中；3 条实际补充事实与 rounds 记录一致。
- 覆盖限制：E03 两版均无终稿，不能证明引用方向与合同定性问题未复发。P5 状态仍待人工意见及补齐覆盖，不开启 T-A6。
- 口径更正：此前 P1 的 1/2=50% 混入不可比的 E04，并非冻结 P1 判据的有效估计，撤回其通过/未达标裁决。8 条两版未出现不能自动解释为已修复（包含空终稿）。P2 的四条是引用缺失候选，不证明开关因果或实质误杀。

### T-A5 派生①：澄清环根因定位与修复（2026-09-17 深夜）
- **根因（已取证，推翻旧解释）**：`gate2_runner.py` 原先两处问题——
  ① `for round_no in (1, 2)`：**争点选择（scope）澄清与事实澄清共用一个 2 轮预算**。
  E03/E04 首轮是「本次请求分解出 6 个争点…选最多 5 个」，runner 正确答 `1,2,3,4,5`，
  但**这格被记入事实预算** → 事实轮只剩 1 格 → 第 3 次澄清无槽位 → `final_chars=0`。
  ② 旧解释「runner 不会答编号」**错误**：`SCOPE_MARK`/`SCOPE_REPLY` 机制早已存在（有测试锁定）。
- **对照证据**：E04 在 on 臂未触发争点上限（planner 分解有随机性）→ 两轮均命中关键词 → 正常完成。
  **开关不是根因**，是预算被菜单挤占。
- **修复（仅评测 harness，不碰生产代码）**：事实澄清与 scope 选择**分层独立计数**
  （`FACT_CLARIFY_LIMIT=2` 保持冻结协议；`SCOPE_CLARIFY_LIMIT=2` 为防御上限）。
  每次循环恰使二者之一 +1（互斥分支）→ 有限步必停，不依赖"服务端终会 finalize"。
  另修 `over_rounds` 红线判定：原按末尾事件类型判，scope 菜单另占槽位会漏标；
  改为「事实澄清已达上限且末尾仍为澄清」。
- **证据（先红后绿）**：新增 2 测试——`test_scope_menu_does_not_consume_fact_clarification_budget`
  （修前 `clar_rounds=2 answered=0 final_chars=0 over2=True` 红，复现 E03/E04 同签名；
  修后绿）、`test_clarification_loop_terminates_when_server_never_finalizes`
  （服务端永不 finalize 仍有限步退出，按「已发起回复数」上界断言）。
  `test_gate2_runner.py` 14 passed；ruff check/format 全绿；**mypy 4 个 error 经基线比对为既有**
  （改动前版本同样 4 个，仅行号位移），改动零新增类型错误。
- **未做**：未付费补跑（待全量回归确认后另行授权）；未改生产开关。
- **📦 交付包已打包（2026-09-17 23:35，可转交复核助手）**：
  `outputs/p5-review-20260917-交付包.zip`（sha256 `61646f5172b1…`，5 成员 / 20,533 bytes）；
  目录版 `outputs/p5-review-20260917-交付包/` 含 `00-作业说明-给复核助手.md`（我新写：流程/
  盲评规则/作答口径/交回要求）、`01/02/03`（**字节级复制**，与源文件哈希一致）、
  `04-交付清单与覆盖说明.md`（覆盖 7 终稿 / 3 空槽，逐条列明限制）。
  **入包闸门**：`_build/audit_package.py` 匿名泄漏扫描 —— 交付包 **0 命中**；
  **watch-it-fail 证据**：同一扫描器对 `p5-private/` 命中 36 处、对 `ta5-arms/` 命中 407 处
  （证明扫描器有效，非「扫不出东西」）+ 独立手工关键词计数同样 0。
  **刻意排除**：`p5-private/{mapping,extraction-manifest,validation}.json` **绝不入包**（交出即破坏盲评）。
  ⚠️ 未覆盖：扫描基于关键词，**发现不了语义级泄漏**；且未校验甲乙映射本身是否真随机
  （该映射为私有件，本次仅确认其未入包）。建议 Owner 交前肉眼扫一遍 `00`/`04` 与 `01` 开头。
  内部完整性清单（含各文件 sha256）在 `_build/交付校验清单.md`，**不入包**。
- **📄 另出「单文件版」**（2026-09-17 23:42）：`outputs/p5-review-20260917-单文件版.md`
  （73,793 bytes，5 个分区：作业说明 / 交付清单与覆盖 / 第一阶段材料 / 第二阶段 / 回执 JSON）。
  **材料保真证明**：材料与说明**只做标题降一级**（前置一个 `#`），并做了**逆向还原等价性证明**
  —— 把嵌入块标题行去掉一个前导 `#` 后，与源文件**逐字节相同**（4 段全过；回执 JSON 原文嵌入）。
  该检查第一次**真的报红了**（`splitlines()`+`join` 丢了源文件末尾换行）→ 修掉实现缺陷后才通过。
  匿名泄漏扫描：**0 命中**。⚠️ 单文件版把两阶段放在同一份文件里，**比多文件版的冻结纪律更弱**
  （已在文首与第四/五部分前置醒目警示，靠复核人自律）。
- **🔍 交付物独立审核（2026-09-17 23:52，报告 `outputs/p5-review-20260917/_build/审核报告.md`）**：
  六组检查（保真/匿名/一致/可用/格式/zip 一致性）**全部通过，0 项待处理**。
  单文件版最终 sha256 `24d0e466de07…`（73,887 bytes；末次改动＝导读区补一句
  「材料所称《第二阶段补充判读》即第四部分」以消除最后一处指代不清）；
  zip `61646f5172b1…`（20,533 bytes，未变）。
  **自足性核对**：全文 1,212 行，零文件名引用、零路径、零 URL、零外部附件依赖 ⇒
  **单文件版可独立交付**，无需同时给出 zip（zip 仅作「严格两阶段」备选）。
- **📄 最终交付文件（2026-09-18 00:10，以本件为准）**：  **`outputs/法律咨询回答复核作业-最终版.md`**（75,261 bytes / 1,241 行 /
  sha256 `1bc9d6ff410cbca5…`）。相对上面单文件版的改动：① 文件名**去内部代号**（中性化，便于直接转交）；
  ② **开篇改为「打开即照做」速览卡**（一句话 / ✅ 必须做的 4 条 / ⛔ 不要做的 6 条 / 📤 交回三样 /
  盲评与保真声明）——把原先散落在第一部分的「不该怎么做」集中前置。改后**重新审核：0 项待处理**。
  ③ 旧路径 `outputs/p5-review-20260917-单文件版.md` **已改写为指路文件**（内容替成
  「已废弃，见最终版」），**防按旧路径误发含缺陷的旧版**；未用删除动作，改内容规避 safe-delete 沙箱。

### P5 二次盲评 · 已返回并处理（2026-09-18 00:50）—— 报告 `dispatch-output/ta5-arms-20260917/p5-review-result-20260918.md`

- **返回件**：复核人**就地填写并保存原路径**（`outputs/法律咨询回答复核作业-最终版.md`，
  99,816 bytes / 1,269 行 / sha256 `846211041166b694…`）。复核人 = **法律合规专家（WorkBuddy AI）**；
  冻结时间 2026-09-18T00:25+08:00。
- **完整性 ✅**：用 `build_single_md.py` 确定性重建基线（哈希校验 == 交付版 `1bc9d6ff…`）后比对，
  **材料未被改动**——218 处改动全是答案占位符（待填写 118 / 回执 JSON 空值 86 / 请在此作答 13 / 抬头 1）。
  ⚠️ 判定器初版用 difflib hunk 归属 → 把未改动行卷进 replace 块、**误报 86+7 行**；改多重集包含后归零。
- **⚠️ 回执结构偏离**：`reviews` 条目**丢了 `version` 字段** ⇒ 只能按数组序对齐（已用 coverage 序 +
  内容特征交叉印证成立）。**下一版模板须把 `version` 设为必填。**
- **✅ 第二轮（盲评）复核已完成并处理（2026-09-18 02:50）** —— 报告
  `dispatch-output/ta5-arms-20260917/p5-round2-result-20260918.md`。
  来源：WorkBuddy 知识库《法律咨询回答复核_独立复核意见》（`kind=doc`；复核人**无本地文件访问权、
  无项目记忆**）。113,762 字符 / 4,254 行（**组件 XML，非 Markdown**，需去标签解析）。
  - **方法学强于第一轮**：先定三类错误的操作性定义；核验法条版本（反法 2025-06-27 二次修订、
    2025-10-15 施行，虚假宣传 8→9 条、罚则 20→25 条；民诉法 264 条在 2021 版为 260 条）；
    记录判定链条；「不确定」与「推断」分开标注。
  - **可比三案 off 2 : on 1**（案例1 off胜 / 案例2 on胜 / 案例5 off胜）⇒ **与第一轮完全一致**。
  - **8 类具体缺陷两轮独立一致命中**（刑诉106、行诉102+民诉77、案例1乙主问题被 `UNKNOWN_FACT_ID`
    排除、海事保全·责任保险、消保49·农地37·医疗36·国赔15、药品131、证券93、反法9/25 现行版下恰当）。
  - 分歧：①「部门法错配」是否计入**主体类型错配**——口径差异，非实质分歧；
    ② 案例5乙(on)「退一赔十」被排除：第一轮判"可接受"，第二轮判"**排除理由不成立**"（更严）。
  - 🔴 **两轮独立指向 on 臂「过度排除/过度保守」**（案例1乙主问题被排除 + 案例5乙十倍路径被排除）
    ⇒ **T-A6 维持不开启，且反对理由强于上一轮**。
  - 判据：P1 仍**不可判定**；P2 四条误杀**仍不成立**；P3 样本不足。
  - ⚠️ 自动交叉核对脚本出现 **2 处假分歧**（取了"条文引述准确"字样而非最终判定）
    ⇒ 已做定向复核才下结论。**脚本结论不可直接采信，又一次。**
- **✅ T-H「过度排除/过度保守」已修复（2026-09-18 03:05，提交 `1f73bb5`）**：
  `agent/service.py` 的逐争点重试从"仅 ISSUE_CLAIMS_MISSING"扩展到**修正性失败**
  （UNKNOWN_FACT_ID / UNKNOWN_EVIDENCE_ID / UNSUPPORTED_CITATION / UNSUPPORTED_NUMERIC_TOKEN /
  NON_CANONICAL_CITATION），由新开关 **`agent_writer_corrective_retry_enabled`**（**默认关 = 行为逐字不变**）
  控制、**至多一次**；GENERATOR_FAILURE / MALFORMED_* 等技术失败不重试。
  **推翻了原注释的论证**：「UNKNOWN_*_ID / UNSUPPORTED_* 同输入同校验，重试无意义」不成立——
  **校验确定性 ≠ 生成确定性**，生成是采样的（T3 自己的 1e9 实证：同分布输入两次结果不同）。
  验证：watch-it-fail（新测试修复前红：coverage `partial != full`，修复后绿）+ 新增 2 测试 +
  边界 9 测试无回归 + **全量门禁 1190 passed / 18 deselected / rc=0**（基线 1188 + 新增 2）+
  ruff check/format、mypy 通过。
  **遗留**：本修复属"机制可用"，**实际效果需下一批评测实测**（开关默认关，开启按 T-A6 判据流程）。
  ② **复核人是 LLM 非人类**，而本项目纪律要求 0/1 判定用确定性金标、不用 LLM judge
  ⇒ 结论按「**AI 复核意见**」口径使用，**不得表述为人工法律意见**；
  ③ 加分：复核人逐条**联网核验**了存疑条文原文 ⇒ 期望值外部可溯源。
- **P2 整体解除**：四条「疑似误杀」**全部不成立** —— E02 民法典192 经返回件引文核查表证实
  **on 版引了 3 次**（该条从未被剔除 ⇒ 原预警系**分析脚本 bug 假阳性**）；
  E05 广告法28 / 反法9·25 属「内容已实质复述并经 59 条转致，**非实质遗漏**」，仅形式建议补条号。
- **P1 仍不可判定**：E04 消保法49 在 **on 版仍出现**（且被判"跨域引用应清理"）＝未拦截，
  但 E04 的 off 版无终稿 ⇒ 两版不可比 ⇒ **不得记 PASS**。E05 药品法131 在 on 版未出现＝已拦截。
- **on 臂暴露新的实质性缺陷**：① **过度保守**——案例1·乙(on) 把核心问题「能否起诉」列入
  `UNKNOWN_FACT_ID` 未能覆盖、未引民诉法122条；② 案例4·乙(on) **主体类型错配"存在"** + 跨域引用 4 处。
  off 臂亦有 刑诉法106条用于民事期限（E01）/海事请求保全·责任保险跨域（E02）/消保法54条不符（E05）。
  **7 份终稿全部为"部分恰当"，无一"恰当"。**
- **🔴 T-A6 维持"不开启"**：P1 仍不可判定/未达标 + on 臂带来的是"更保守"而非"更准确" +
  本次为 AI 复核且防锚定未执行。**建议另立票据**修 §7 的 5 条跨域引用/错配，并单修
  「过度保守致核心问题落入未能覆盖」这一行为（比开开关更值得做）。
  审核过程中**三次报红都由检查抓出**（非肉眼），处置留痕：
  1. **D 可用性（真缺陷）**：第一、二部分沿用多文件版措辞要求复核人「打开 `01-…md`」，
     单文件版里并无该文件 ⇒ **不可执行指令**（5 文件名 / 10 处）。→ 改**引用改写**
     （文件·编号 → 第N部分）+ 通用文件名替换，残留引用归零。
  2. **保真命题一度不成立**：v2 初版命题写「只动了引用词」，但改写「同目录…号文件」必然动到
     「同目录」这类非引用词 → 证明**如实报红**。→ 命题改为**以声明替换列表为准**
     （「除声明片段外逐字节相同」），可检验且为真。**未掩盖，改命题而非改证据。**
  3. **审核脚本自身过期**：A 项仍按 v1 命题检查 → 误报 2 项；已对齐 v2 命题（分两类断言）。
  另修构建脚本实现缺陷：`splitlines()`+`join` 丢源文件末尾换行 → 加 `_rebuild()` 保留。
  ⚠️ 未覆盖（诚实标注）：扫描**发现不了语义级泄漏**；**未校验甲乙映射是否真随机**
  （私有件，仅确认未入包）；未校验材料内法条内容与版本属实（属复核人职责）。


### T-A5 派生① 收尾核验（2026-09-17 全量回归，Task #2 完成）

- **全量回归**：`4 failed, 1153 passed, 18 deselected, 52 warnings in 305.58s`
  （日志 `dispatch-output/ta5-arms-20260917/_fullsuite.txt`）。
  失败 4 个 = `test_capture_eval` ×1 + `test_request_bootstrap` ×3。
- **隔离复跑同 4 个**：`26 passed, 1 warning in 14.24s`
  （日志 `_isolated_fails.txt`）⇒ 判定为**顺序/并发依赖的既有 flaky**，与本次改动无关。
  `test_request_bootstrap.py` 全文不含 `gate2`/`clarif` 字样，无调用面交集。
- **严格基线对比尝试**：`git stash push` 被 SIGTERM 中断（STASH_RC=1）。
  事后核验 `git stash list` 为空 + 两文件均为 `M` ⇒ **stash 未发生、改动完好**，
  不再重试（重试风险 > 收益，已有隔离跑 26 passed 的强证据）。
- **代码字节快照**：`dispatch-output/ta5-arms-20260917/fix-clarify-budget-code-snapshot.json`
  - `backend/scripts/gate2_runner.py` — 29,667 bytes / sha256 `43201f87f9b58196…`
  - `backend/tests/test_gate2_runner.py` — 23,172 bytes / sha256 `d72845c0965737b2…`
- **状态**：两文件仍为 uncommitted（`M`）；14/14 测试绿；ruff check/format 全绿；mypy 零新增。
- **可复用模式已固化**：`loop-termination-preflight` skill 新增「§4 一个预算计数器是否被
  多种异类轮次共用」+ 红牌 1 条 + 自检项 2 条（共用预算被挤占 → 上限形同虚设）。
- **未做（待授权）**：付费补跑 E03/E04；未改生产开关；未代替人工复核。

### T-A5 派生② 补跑件已就绪（Task #3 前置，**待付费授权**）

- **补跑脚本**：`dispatch-output/ta5-arms-20260917/run_ta5_rerun_e0304.py`
  - 范围：仅 **arm-off × {E03, E04}**（本次验证的是 harness 缺陷是否消除，与两业务开关无关；
    on 臂如需再跑另行授权）。
  - 证据目录：`arm-off-rerun-e0304/`（**独立**，不覆写首轮 `arm-off/`）；目录若非空即拒绝运行。
  - 独立账本 + 独立 quota 库（沿用首轮 `seed_quota_override`），沿用 `GUARD_LIMIT=none`。
- **⚠️ 关键安全发现（避免一次真实事故）**：`run_ta5_batch.py` **无 `if __name__ == "__main__"` 守卫**，
  批次主体是模块级语句（删 `_gate_quota.sqlite` → seed → 遍历两臂 → **覆写 `arm-off/`、`arm-on/`**
  → 写 `summary.json`）。因此 `import run_ta5_batch` 会**导入即执行整个两臂批次**、直接毁掉首轮证据。
  → 补跑件改为 **按 AST 精确摘取所需函数源码**（quota_total_of / seed_quota_override /
  health_gate / wait_ready / port_busy）到独立命名空间执行：**复用实现、零模块级副作用**。
- **干跑验证（不花钱、不启服务）**：模块级"摘取+绑定"段执行成功 → 批次**未**被启动；
  5 个函数全部 CALLABLE；`port_busy(18111)=False`（端口空闲）；`quota_total_of` 实测读到 1000000；
  `seed_quota_override` 写入临时库得 `init:agent_text_37max0608 = 1000000`（与主库 `data/quota_used.sqlite`
  隔离，未触碰）。干跑过程中**报红 3 次**（`__file__` 缺、注解求值时 `Path` 未注入、
  `quota_total_of` 未导出 / `socket` 未注入）→ 全部修掉后 ALL GREEN。
- **首轮证据已冻结**：`first-round-evidence-snapshot-before-rerun.json`（18 文件字节指纹，
  arm-off 9 件 + arm-on 9 件，含 cost-ledger / evaluation.sqlite / checkpoint / serve.log）。
  补跑后可用它核对首轮证据未被改动。
- **执行方式（须用户侧执行）**：沙箱会收割全部子进程，长驻服务活不过命令结束；
  须用户本机双击 bat 或直接跑：
  `backend\venv\Scripts\python.exe dispatch-output\ta5-arms-20260917\run_ta5_rerun_e0304.py`
  （预计耗时：net_health + 真实调用闸 5 次 + 2 例；按首轮单例成本估，量级约个位数 CNY，**不设上限**）。
- **未做**：未执行补跑（付费动作待授权）；未改生产开关；未代替人工复核。

### T-A5 派生③ 离线重放：越权验证根因（**对派生①的结论校正**）

零成本（不调 LLM），用首轮 checkpoint 的**真实澄清序列**驱动新旧两版循环，产出
`dispatch-output/ta5-arms-20260917/offline-replay-clarify-budget.json` +
脚本 `replay_clarify_budget_offline.py`（常量从 runner 同源读取，不硬编码）。

**结论表（13 个有澄清记录的结果）**：

| 情形 | 案例 | 旧版退出原因 | 新版 | 判定 |
|---|---|---|---|---|
| 空终稿（真缺陷） | off/E03、off/E04、on/E03 | **BUDGET_EXHAUSTED**（走 2 步被预算卡死，服务端仍要问第 3 次） | 走满 3 步、应答到底 | ✅ 修复命中 |
| 正常终稿（回归面） | E01/E02/E05/C05（两臂）、on/E04/E05 | server_stopped_asking | **完全一致** | ✅ 零扰动 |
| 其他空终稿 | off/C07、on/C07、on/C05 | server_stopped_asking | 一致 | 别因（AGENT_EXECUTION_FAILURE / PLANNER_PARSE_ERROR），本次修复不涉 |

**⚠️ 对派生①陈述的两点校正（如实修正，不掩盖）**：
1. 派生①写的「事实轮只剩 1 格 → 第 3 次澄清**无应答槽位**」方向对，但更准确的机制是：
   `asked` 记录显示 **scope 占 round1、事实占 round2**，两次 `for` 循环用尽后退出；
   而 checkpoint 的 `rounds` 有 **3 轮**澄清 → **服务端第 3 次澄清发出时 runner 已退出**。
   ⇒ 空终稿的直接机制是「**退出时服务端仍在索取澄清**」，而非「预算内分配不足」。
2. **证据边界（不可知项）**：checkpoint **只落盘 runner 已应答的轮次**（`asked`），
   第 3 轮澄清的 prompt 文本**未存**。故其类型（scope/事实）**不可知**，重放**不猜**，
   改为**枚举两种可能**并给区间 —— 两种枚举下新版均走满 3 步，故结论对该未知量**稳健
   （robust=True）**。

**过程中自查出一次假绿**：重放脚本初版对旧版只喂「已观测序列」、未计入未知尾轮，
导致 `steps >= len(prompts)` 先命中 `server_stopped_asking`，**把真实的 BUDGET_EXHAUSTED
掩盖成"服务端自己停问"**。修正后旧版正确报出 BUDGET_EXHAUSTED。**这正是"探针改变被测对象"
的同类风险**，已记入 skill。

**定位**：本重放是**机制级**证明（决策路径），**不能替代**付费补跑（真实 LLM + 真实
服务端行为）。E03/E04 修复后能否真正产出非空终稿，仍须补跑实证。

### T-A5 派生④ P5 发出前决策说明（**未改冻结材料**，待 Owner 拍板）

**背景**：查明材料中 3 个空槽（案例3·甲/乙、案例4·甲）**100% 系 harness 缺陷**——
其在 checkpoint 中 `error_codes=[]`（**零错误码**），与 `C07: AGENT_EXECUTION_FAILURE` /
`C09/C05: PLANNER_PARSE_ERROR` 这类**服务端真错误**形成明确区分（后两者且不在材料范围内）。
⇒ 材料现标注"材料不足"**保守且无误导，诚信无问题**；但复核人可能误归因为"模型没答出来"。

**遵守冻结纪律，未改动材料本体**：`outputs/法律咨询回答复核作业-最终版.md`
实测 sha256 `1bc9d6ff410cbca57dc5452fcef6885df81adb90edca1cd4840194121be44d4a`
与冻结记录 `1bc9d6ff410cbca5…` **一致**（未被改动）。另核实材料匿名彻底：
`E01`–`E05` 等内部代号在材料中**零次出现**。

**产出两件（均经盲评扫描）**：
1. `outputs/p5-发出前决策说明-给Owner.md`（6261 bytes）— **内部件**，
   含案例代号/臂别（扫描 **14 处命中**），已在文首加「🚫 严禁交付复核人」警告。
   给出三选项：A 不改直接发 / **B 加附页（推荐）** / C 补跑后重做材料（最贵）。
2. `outputs/附页-关于3个空槽的成因说明（备用，未交付）.md`（3372 bytes）—
   **唯一可随材料交付**的版本，扫描 **0 命中**。
   关键设计：**不要求复核人采信成因解释**（因该解释无法被复核人独立验证），
   只要求"不要把没有文本当作文本质量差"；并显式欢迎复核人**保留异议**（第四节）。
   ⚠️ 状态：**备用、未交付**（因不知材料是否已发出，不擅自并入）。

**未做**：未改材料本体；未发出任何文件；未执行付费补跑；未代替人工复核。

### T-A5 派生⑤ **对派生①/③机制的二次校正**（逐轮证据，2026-09-18）

派生前几轮把机制说成"runner 提前退出"。**逐轮核对 `rounds[].event_types` 后，机制需精确化为：**

| 案例 | r1(initial) | r2(round1) | r3(round2) | 结局 |
|---|---|---|---|---|
| E01/E02/E05（成功） | clarification | clarification | **`verification,token,final`** | 有终稿 |
| **E03/E04（空）** | clarification(scope菜单) | clarification(事实追问) | **仍是 `clarification`** | 无终稿 |

⇒ 旧版**确实发出了 3 次请求**（`initial` + `round1` + `round2`），**不是提前退出**；
而是**第 3 次请求后服务端仍返回 `clarification`，而旧版预算已耗尽 → 停手 → `final_chars=0`**。

**旧/新版请求次数（精确）**：
- 旧版 `for round_no in (1,2)`：**上限 3 次请求**（initial + 2 轮应答）。
- 新版双计数器：scope 与事实各 2 格 → **上限最多 5 次请求**。
  E03/E04 实况为 `scope + 事实① + 事实②` → **可发出 4 次请求**（比旧版多 1 次）。

**⚠️ 因此对补跑的前景必须如实降级为"有希望但不保证"**：
1. 新版多出的那 1 次请求，答的是**第 2 次事实追问**；
2. **实测该追问对 E03/E04 的 r1/r2 关键词命中数为 0**
   （E03 追问"停工的具体原因…不可抗力" vs 关键词 `合同/总价/执照/资质/进度`、`增项/确认/签字/跑路/失联` → 0 命中；
   E04 追问"鉴定机构资质…法定期限" vs `酒驾/逃逸/责任/伤情/医药费`、`保险/交强险/误工/收入/证明` → 0 命中）；
3. ⇒ runner 第 4 次仍只能回 `NO_MATCH_REPLY`（"我没有保留这方面的信息。"）；
4. ⇒ **服务端收到 NO_MATCH 后是否 finalize，无法从历史推断**（E01/E02 有过 2 次 NO_MATCH 仍出终稿的先例，
   但它们的第 3 次请求直接拿到了 `final`，与 E03/E04 情形不同）。
5. **结论：补跑能否让 E03/E04 产出非空终稿，只有实测才知道。** 不可预先断言。

**⚠️ 另发现案例集声明与实际不符**：`evals/frozen-cases-v2.json` 中 E03/E04 的 `scope_trigger` 均为
**`false`**（声明"不应触发争点选择"），但两臂实测**都触发了**（planner 分解出 6 争点 > 上限 5）。
⇒ 触发源自 planner 运行时行为，非案例设计；这解释了 L182 待办①「可比率仅 3/8」的由来。
（该字段是否有消费者、是否需要修案例集，**未查**，不擅动 frozen 资产。）

### T-A5 派生⑥ **修复前景上调为"很可能有效"（附强证据），但仍须实测收口**

派生⑤ 曾把前景降级为"有希望但不保证"（理由：E03/E04 追问关键词命中 0）。
**新增「应答有效性」横向对比后，该理由被证伪** —— 因为**命中 0（NO_MATCH）也能出终稿**：

| 案例 | 追问应答有效性（逐轮） | final_chars | 结论 |
|---|---|---|---|
| off/E01 | **NO_MATCH, NO_MATCH**（2 次全空） | **1819 ✅** | NO_MATCH 不影响收尾 |
| off/E02 | **NO_MATCH, NO_MATCH** | **1663 ✅** | 同上 |
| off/C05 | **NO_MATCH, NO_MATCH** | **1892 ✅** | 同上 |
| off/E05 | NO_MATCH, 命中 r1['批准'] | 2642 ✅ | — |
| **off/E03** | **scope_menu**, NO_MATCH | **0 ❌** | 差异在 scope |
| **on/E03** | **scope_menu**, NO_MATCH | **0 ❌** | 同上 |
| **on/E04** | 命中 r1['伤情'], NO_MATCH | 2238 ✅ | on 臂未触发 scope |

**⇒ 精确机制（证据支持）**：
失败与"能否答出事实"**无关**（NO_MATCH 是常态，且照样出终稿）；
唯一区别是 **E03/E04 的第一轮被 scope 菜单吃掉**，使其事实轮比 E01/E02 少一次。
旧版预算分配：E01/E02 得 `[事实①, 事实②]`；E03/E04 得 `[scope, 事实①]`。
**修复后 E03/E04 也拿到 `[scope, 事实①, 事实②]`，与 E01/E02 等效。**
而 E01/E02 以 2 次事实轮（哪怕全 NO_MATCH）**均成功产出终稿** ⇒ 修复**很可能有效**。

**为何仍不能直接宣布修复成功（诚实标注）**：
这是**横向类比推理**，不是对 E03/E04 的**实测**。差异点在于 E03/E04 的**服务端 run 状态**
（`clar_meta.run_id` 相同但 `state_version` 不同）可能与 E01/E02 不同；
服务端在"scope 被满足"与"无 scope"两种会话下对澄清的容忍度**未必一致**。
⇒ **补跑仍是唯一收口手段**，但预期从"不保证"上调为"**很可能成功**"。


---

## T-A5 派生⑦ **付费补跑执行完毕：E03 修复确认有效；E04 暴露独立第二缺陷（verifier 词表误伤）**

- 批次：`ta5-off-rerun-e0304-20260918-002754`（arm-off，E03+E04）
- runner：`43201f87f9b58196ce4c5338bf181da4ab9e14ca6e4eee634646aeb2c005f83f`（未变）
- 模型：`qwen3.7-max`（GATE_PICKED agent_text_37max；`agent_text_37max0608` 已跳过）
- **实结花费 0.708372 CNY**（24 调用 / 12 次 LLM；无 quota/halt）
- 首轮快照 18 文件核验 **ALL OK**（未被覆写）

### 结果

| 案例 | rounds | clar_rounds | final_chars | 终态 | error_codes |
|---|---|---|---|---|---|
| **E03** | 3 | 2 | **2532** | completed ✅ | `[]` |
| **E04** | 3 | 2 | **0** | failed ⚠️ | `OVERCONFIDENT_WORDING` |

### 结论一：**澄清预算修复实测有效**（E03 收口）

E03 → `round2(verification,token,final)`，`final_chars=2532`（首轮为 0）。
两例 `clarifications=2`、`asked=2`，即 **scope 菜单与事实澄清预算已解耦**，
E03/E04 拿到与 E01/E02 结构等价的轮次。⇒ **预算耗尽型空终稿已消除。**

### 结论二：E04 失败**与预算无关**，是独立第二缺陷

`agent_steps` 实测（本轮）：#18 `CLARIFY_BUDGET_EXHAUSTED → drafting`、
#19 `failure / OVERCONFIDENT_WORDING / VERIFIER:REWRITE`。
⇒ 澄清正常走完 2 轮，**生成与验证都执行了**，失败在 verifier 文风检查。

**命中标记 = `绝对`；出处 = 保险专有名词「绝对免赔额」**，来自 payload 的
`unknown_facts`：
`商业三者险合同中是否存在免赔率、绝对免赔额或驾驶人资格瑕疵等免责条款`

判定实现（`backend/agent/verifier.py:374-382`）：`marker in claim.text` ——
**子串字面匹配，无词边界、无上下文、无术语白名单。**

**放大机制**：`backend/agent/service.py:464-466`（Ticket 2）—— 首次 verifier 非 PASS
即**终态失败（fail-closed）**，不触发第二轮 writer。`REWRITE` 本是"可重写"的中间态，
被当终态 ⇒ **一击即死**。

**规避不可能**：该文本源自 payload `unknown_facts`，而 writer 的 `missing_information`
被强校验为**逐字来自 `unknown_facts`**（`verifier.py:258-262`）
⇒ **模型越忠实复述，越必然命中。**

### 误伤面量化（真实词表，AST 读取）

24 个法律/保险/合同专有名词候选 → **19 个被误伤（79%）**。例：
`绝对`→绝对免赔额/绝对权/绝对责任/绝对无效；`一定`→一定期限/一定比例/一定范围；
`必然`→必然因果关系。**真过度自信（"必然败诉/保证胜诉"）仍被正确拦截。**

正向对照（真实 verifier 词表）：原文命中→REWRITE；**去掉"绝对"二字即通过**
⇒ 误判**完全由词形驱动**，与文风无关。

**同类回归第 2 次**：`writer.py:272-276` 已记载脱敏替换词"一定期限"与词表冲突的旧回归
⇒ 该词表**至少第二次以同一模式误伤法律/业务术语**。

### 结论三：E04 **不是新增问题**（回归性质判定）

首轮 E04：`event_types` 停在 `clarification`、`error_codes=[]` → **预算耗尽直接截断，
根本没走到 verifier**。本轮修复让流程推进到 verifier 后，**才暴露出被掩盖的既有缺陷**。
⇒ 准确表述：**主因（预算）已修；E04 暴露第二道独立缺陷（词表误伤 × fail-closed 放大）。**

**强佐证**：首轮库 run(conv=1/E01) 与本轮 E04 的步骤逐行同构 ——
两者 sv=8 均为 `CLARIFY_BUDGET_EXHAUSTED → drafting`；差异**只在最后一步**：
前者 `VERIFIED_FINAL_STORED/completed`，后者 `OVERCONFIDENT_WORDING/failed`。

### 证据局限（诚实标注）

**draft 在失败时未落库**，故无法直接读取 E04 的 `claim.text` 原文。
归因链为：payload 含该串 → `missing_information` 要求逐字复述 → error_code 恰为该值
→ 改写对照证明词形是唯一变量。**高度可信，但"claim 原文"未经直接观测** ⇒ 列入待补。

### 后续动作（优先级）

| P | 动作 |
|---|---|
| P0 | 词表改**词边界/上下文**判定 + 法律·保险术语白名单 |
| P0 | **补失败路径 claim.text 落库**（否则此类归因永远只能推断） |
| P1 | 评估 Ticket 2 是否应对 `REWRITE` 保留一次重写（其语义不同于 FAIL_SAFE 的不可修复） |
| P1 | 词表回归测试（watch-it-fail）：专有名词白名单生效 |
| P2 | 复核首轮其余案例是否有同类被掩盖缺陷 |

### 交付物

`dispatch-output/ta5-arms-20260917/rerun-e0304-report.md`（完整报告）
+ `arm-off-rerun-e0304/`（9 文件证据）
+ `verify_overconfident_false_positive.py` / `verify_e04_draft_repro.py` / `verify_e04_real_verifier.py`


---

## P0 处置（2026-09-18）**能做的已做：P0-2 全做 + P0-3 标注；P0-1/P0-4 上报待裁决**

**方案审**：动手前跑 vet-plan 五问（`dispatch-output/ta5-arms-20260917/p0-vet-plan-20260918.md`），
据此切开范围 —— **凡涉及语义裁决的（P0-1 改 `over_rounds`、P0-4 改 verifier 词表）一律不擅动**。

### ✅ 已做

**P0-2 删除假断言（注释修正，全做）**
- `gate2_runner.py:186` 删去「与 v1 行为逐字一致」，改为**准确语义**：
  「事实轮由 ≤1 恢复为 ≤2；**总追问轮上限由 2 放宽至 ≤4**」，并注明 v1 自身不自洽
  （实测 E01/E02/E05 = `(scope 0, fact 2)`、E03/E04 = `(scope 1, fact 1)`，故无"一致"参照物）。
- `gate2_runner.py:469` 终止性口径更正：上界**由两个内层 `if … break` 保证，非 `while … or …` 条件**。
- `gate2_runner.py:539` `over_rounds` 处加 **🚨 待裁决** 块：载明冻结协议原文
  （`dispatch-tasks-20260908.md:103`「最多两轮」指全部追问轮）、验收闸
  （`gate5-formal-dev-20260908.md:41` R5 20/20）、实测新旧判定相反、**未处理**及两条出路。

**P0-3 诚实标注（不改语义）**
- `test_gate2_runner.py::test_clarification_loop_terminates_when_server_never_finalizes`
  docstring 加 **「⚠️ 护栏，非新功能证据」**：说明它在修复前代码上也通过（语义回滚 + 独立
  basetemp 实测，`_verify_h1c.py`），不能证明本次改动正确性；真正回归证据是同文件的
  `test_scope_menu_does_not_consume_fact_clarification_budget`（回滚后变红）。
- 同处标注已知缺陷：`len(chat_requests) < 50` 这个界**形同虚设**（实测仅 3），
  并说明根因（`_last_case` 猜归属 ⇒ 脚本只被消费 3 条）与改正形态（钉确切值）。

### 验证证据（行为零变化）

| 检查 | 结果 |
|---|---|
| `ruff check`（两文件） | All checks passed ✅ |
| `ruff format --check`（两文件） | 2 files already formatted ✅ |
| **AST 比对**（剥 docstring，改前 vs 改后） | **两文件 AST 逐字节相同** ⇒ 代码语义零变化 ✅ |
| `pytest tests/test_gate2_runner.py` | **14 passed**（与改动前一致）✅ |

> AST 比对方法：因仓库已有 183 行未提交改动，HEAD 不是基线。改用「反向应用本次三处/一处 Edit」
> 重建改动前版本，并以**动手前记录的 sha256 自校验通过**
> （`gate2_runner.py` = `43201f87…`、`test_gate2_runner.py` = `d72845c0…`，字节数与哈希双双吻合），
> 再对两者做去 docstring 的 AST dump 比对 ⇒ 完全相同。脚本 `_rebuild_pre_edit.py` / `_prove_comment_only2.py`。

### 🚨 上报 Owner 待裁决（本轮**未动**）

| 项 | 为何不擅动 |
|---|---|
| **P0-1 `over_rounds` 放宽 R5 闸** | 执行入口载明「判据冻结…**不得按结果修改**」。两条出路（恢复按全部追问轮 / 显式记录为有意放宽 + Owner 签署）均需决策留痕，非代码可自决。**注意：本轮只改了注释说明它"未处理"，闸的实际放宽依然存在。** |
| **P0-4 verifier 词表误伤** | 改 `_OVERCONFIDENT_MARKERS` 判定逻辑 = 改生产语义，须先定方案（词边界 / 白名单 / 上下文模式）。属独立缺陷，与本次 harness 改动无关。 |

### 未做
未提交、未推送（先裁决再提交）；未跑全量 `pytest -m "not slow"`（仅按受影响面跑该模块 14 例）；
未改任何判定语义。


## P0 全部收口（2026-09-18 02:45，commit a3ce07b）

**授权**：用户 02:04「按你的推荐执行…部署先不做」。方案前置 `plan-p0-exec-20260918.md`（vet-plan 五问）；
审查留痕 `dispatch-output/ta5-arms-20260917/code-review-t1t3-20260918.md`。

### P0-1 已裁决并实施：恢复 over_rounds 协议口径

- 判据改为 `clar_requests = len(asked) + (末尾是否仍澄清)`，大于 `CLARIFY_ROUND_LIMIT(2)` 即红线。
  新增常量与 FACT / SCOPE 两个**执行预算**显式解耦——预算是 runner 愿意应答多少轮，
  标尺是服务端实际追问了几次。
- **实测推翻初判**：原以为只是"谓词排除 scope 轮"，双跑真值表显示 45 个序列里 **25 个**分歧，
  且全为 v1=True / cur=False。更深根因：预算 2→4 后第 3 次澄清**被应答消化**，
  依赖"末尾快照"的判据看不见它。我最初提的方案（按已应答轮数加末尾判断）也被真值表证伪。
- 证据：v1 真实副本双跑 45 序列分歧 **25 → 0**；真实 18 case 与 v1 记录值 **100% 一致**；
  并暴露旧谓词在真实数据上**已漏标 3 例**（arm-off 的 E03/E04、arm-on 的 E03）。
  watch-it-fail 成立（回滚 → 新测试为正确原因变红，1 failed / 15 passed）。

### P0-4 已完成（a 落库 + b 词表）

- (a) verifier `_result` 非 PASS 也填 claim_checks；REWRITE 分支补传 draft/state；
  service fail-closed 日志新增 `agent_claim_checks`（草稿文本截断 120 字符），
  已登记 `observability._ACCOUNT_FIELDS`（否则被 JSON formatter 静默丢弃）。
- (b) 新增 `_is_overconfident`：强断言词无条件命中 + 弱标记须搭配断言词 + **术语优先放行**。
  24 个法律/保险专有名词误伤 **19 → 0**；8 条真断言仍命中。
  ⚠️ 2026-09-18 订正：`24 / 19` 是**诊断阶段的候选集**（本文件 L843-845 明写"候选"），不是落地的
  测试条数。AST 复算 `_LEGAL_TERMS`：`a3ce07b` 与当前工作树**都是 21 条、裸匹配命中 16 条**；
  `handover-20260918.md` §5 末尾记的「回滚函数体 → 16 failed」与此一致（同一文档内 24/19 与 16
  本就自相矛盾）。测试注释已按 21/16 订正。
  详见 `dispatch-output/ta5-arms-20260917/handover-20260918.md` §12.1。
  保留 `_OVERCONFIDENT_MARKERS` 常量（tests/test_agent_writer.py 脱敏契约直接 import，不可删），
  但不再用于裸子串判定。
- 保守取舍（已写入代码注释）：术语优先放行是**有意的**——误杀会让整轮 fail-closed
  （用户看到失败），漏判最多让一句措辞过关。
- 两处失败（单元测试 + 2 个集成测试）均由实测定位根因（"一定适用"、"一定应当"两类
  断言词遗漏），**补全判定而非改测试迁就实现**。

### 验证

- `pytest -m "not slow"` = **1188 passed / 18 deselected**（基线 1155，+33 全为新增，零回归）
- `ruff check` 全仓绿；`ruff format --check` 仅剩**既有** `agent/writer.py:665`
  （T-A3 引入，跨会话未动，避免写冲突）
- 每个改动配 watch-it-fail：语义回滚 → 为正确原因变红 → 还原并 sha256 校验一致

### 状态与遗留

- **已本地提交** `a3ce07b`（6 文件）；**未推送**（部署类按用户要求先不做）
- ⚠️ 仓库既有损坏（缺 blob `04463121…`）致 `git diff --stat` / `git show --stat` 不可用；
  已做字节快照保底 `dispatch-output/ta5-arms-20260917/_snapshot_t1t3_20260918/`
- 遗留 P1：`_last_case` 归属、上界断言钉值、REWRITE 是否留一次重写（P1-4）

---

## 派生⑨ P1 安全三项收口 + 代码审查整改（2026-09-18，按 §6 约定追加状态）

**范围**：Owner 选定「只做可安全改（纯测试 / harness）」的 P1-1 / P1-2 / P1-5；提交在 master，未推送。
生产开关、`CLARIFY_ROUND_LIMIT` 判据、frozen 评测资产一律未动。

**任务条目状态**

- ✅ **P1-1**（本文件 L983 遗留项「`_last_case` 归属」）：resume 归属改为请求自身的纯函数，
  `_last_case` 删除；归不上 ⇒ 记账 + 绊线。红绿证据：`_p11_watch_it_fail.py` 定向摘掉 run_id
  通道 → `assert None == 'C02'`（sha256 还原一致）。
- ✅ **P1-2**（同上「上界断言钉值」）：`< 50` → `== 3`；扰动 `FACT_CLARIFY_LIMIT` 后本断言变红
  （`_p12_perturb.py`）⇒ 证明力为真，且刻意不用派生式。
- ✅ **P1-5**（派生⑦ P1「词表回归 watch-it-fail」）：**白名单回归本体早已在 `a3ce07b` 随 T3 交付**；
  本批按 Owner 授权补的是术语优先分支覆盖——该分支此前**零覆盖**（删掉后全库无测试变红，
  `_p15_literal_sweep.py` 扫 156 文件/17636 字面量证实）。现补 2 例竞争句 + 1 例接受风险留痕，
  两条独立探针（删分支 / 调正则顺序）各使 3 例变红。
- ⬜ 派生⑦ P1「REWRITE 是否留一次重写」（= handover P1-4）**未动**：改生产语义，需 Owner 裁决。
- ⚠️ 数字分叉已订正（见上文 P0-4 (b) 的 2026-09-18 订正条）：落地测试是 **21 条 / 16 命中**，
  24/19 是诊断阶段候选集。

**代码审查（fixed point `7c7261c`）整改**：7 条已改、4 条判定不改并写明理由，台账见
`dispatch-output/ta5-arms-20260917/handover-20260918.md` §12.3。其中两条值得前置提醒：
新增的多 case 端到端测试**是覆盖面、不是 P1-1 的红绿锁**（runner 串行，实测改回猜法仍绿）；
`_FakeGateService` 仍无 run_id 归属通道（现有测试无 resume 场景，但同类盲点未消灭）。

**§6 约定的其余落点**：`docs/process-archive/project-next-execution-plan-20260916.md` §7 与工作日志**本会话未写**
（该文件由并行会话共用，避免写冲突）——留此为待办，非遗漏。

---

## 派生⑩ 「最多两轮 / over2」口径权威定义（2026-09-18，P1-7 收口）

**为什么要专门成文**：`docs/dispatch-tasks-20260908.md:103` 的协议原文「最多两轮；若两轮后仍出现
clarification 事件，记为红线候选（over2）」按字面读是**末尾快照**谓词。照这句改实现就会在分层预算下漏标
超限——实测 45 个序列漏 25 个（`gate2_runner.py:560-563`）。这类"照文档把代码改回去"的事故**已有前科**：
2026-09-17 那版 `fact_clar_seen >= FACT_CLARIFY_LIMIT and any(末尾澄清)` 谓词就是照这句话写出来的
（`:566-568` 留痕，2026-09-18 已裁决废弃）。

**权威口径（以本节为准）**：

| 项 | 口径 |
|---|---|
| 计什么 | **服务端发起的澄清请求次数** = `len(asked) + (末尾仍是澄清 ? 1 : 0)` |
| 谁占格 | scope 菜单与事实追问**同计**，不分轻重 |
| 红线 | 上式 > `CLARIFY_ROUND_LIMIT`(=2)，即**出现第 3 次追问**即红线 |
| 不是 | 「末尾是否仍为澄清」——超限轮次一旦被应答就从末尾消失，只看末尾会把它抹掉 |
| 判据 vs 预算 | `CLARIFY_ROUND_LIMIT` 是**判据（冻结）**；`FACT_CLARIFY_LIMIT` / `SCOPE_CLARIFY_LIMIT` 是**执行预算**。两者独立可调，**改预算不得改判据** |
| 实现 | `backend/scripts/gate2_runner.py:569-571`（判据）· `:184`/`:185`/`:190`（预算与判据常量） |
| 回归锁 | `backend/tests/test_gate2_runner.py` 三条按**测试名**锚定（行号会漂，实测 2026-09-18 一天内就漂了 13 行）：`test_redline_counts_every_clarification_round_including_scope` 该红时红 · `test_redline_not_triggered_when_server_stops_after_two_rounds` 反例护栏 · `test_scope_budget_exhaustion_aborts_run_without_hanging` scope 预算耗尽守卫 |

**本节不改写**：T-A5 冻结判据表（本文件 §5，其 P1–P5 与"两轮"无关，不构成冲突）；
`dispatch-tasks-20260908.md` 历史正文——只在其原句下方加带日期的订正注记并指向本节。

---

# 下一阶段规划（2026-09-19 01:00 起 · T-E/T-E2 收口后）

> 编排依据：writing-plans（任务粒度与 DoD）+ module-dispatch-new（车道与验收契约）
> + vet-plan-new（文末五问自审）。**按本仓惯例不新建规划文件**，本节即进度入口（§7 那条
> "进度只往执行书与当日日志写"的约束优先于 skill 默认的 docs/process-archive/superpowers/plans/ 落点）。

**目标**：把 T-E 期间攒下的三类未收口债（真实产物的**非测试入口**访问、**无异地副本**、
**判据可读性**）收掉，并为并行会话立一份可派发的车道表。

## Global Constraints（每票都含，逐字生效）

1. Python 一律 `backend/venv/Scripts/python.exe`；pytest 必须 `--basetemp=<**系统 temp**>/...`
   （**不得设在 `backend/` 内**，见 §T-E r3 教训：`test_log_field_whitelist` 会递归扫 backend 全树）。
2. 禁止 `git clean` / `git reset --hard` / `git stash` / 批量格式化无关文件——工作树里 170+ 未跟踪
   文件是他人的证据。
3. **push / fetch / clone 当前不可用**（`0263bd5` 对象丢失，见 §T-E 断链条与决策项 D1）；
   别把"推不动"误记成自己的回归，动手前 `git rev-list --count HEAD` 复测（可读 16 个提交为常态）。
4. 判据冻结：预注册判据不得按结果改；`CLARIFY_ROUND_LIMIT` 是判据、`*_LIMIT` 预算独立；
   基线 1101 作废禁引；重算冻结哈希前不得开付费轮。
5. 提交信息**不内嵌英文双引号/反引号/`$`**（含这些字符的信息写文件用 `git commit -F`）。
6. 只往两处写进度：本执行书（就地追加）+ `.workbuddy/memory/YYYY-MM-DD.md`（`cat >>` 追加）。
7. **整目录清单判据只在同一轮 pre/post 之间成立**：跨轮比较会把"别人只是打开了真实库"
   （HNSW 打开即回写 `length.bin`，条目数与 sqlite cc 都不动）误读成污染。

## 车道与禁改（01:00 实测：工作树干净、0 个 python 进程）

| 车道 | 归属 | 本规划可否触碰 |
|---|---|---|
| `backend/agent/*`、`backend/scripts/gate2_runner.py`、`tests/test_gate2_runner.py`、`test_r15_*` | R15 / P2-2 会话在飞（`5afc8d0` 00:34、`105907b` 00:49） | **禁改**，只出票 |
| `backend/tests/conftest.py`、`backend/rag_chain.py`、`backend/knowledge_service.py`、`backend/scripts/*` | 本会话（`44210ef`/`fe40b0c`） | 可改，改动即全网生效，动前先声明 |
| `docs/PROBLEM_LOG.md` | 未认领 | 只追加 |

## Task G1: 给当前 HEAD 重取全量基线（**已在 00:5x 起跑**）

**为什么现在做**：r6 的 1272 passed 测在 `aaf088b`+`fe40b0c` 状态；此后 R15/P2-2 又落了
`5afc8d0`/`e3c023a`/`b61bc08`/`105907b` 四个提交 ⇒ "全绿有保质期"，现在不重取，下一张票的
任何红都无法归因。

- [x] **Step 1**：`cd backend && ./venv/Scripts/python.exe ../dispatch-output/te-chroma-isolation-20260918/run_gate_full.py phase2-g1`
      （该脚本自带源码变动自检：跑中途有人改 .py ⇒ 判 RUN_VOID 而非红/绿）
- [x] **Step 2**：读 `gate-phase2-g1-verdict.txt`，把**结论行 + 末行计数 + 三产物指纹**抄进
      §3 基线行（新日期新行，**不覆盖旧行**——异集混比是本仓明令禁止的）。
      ✅ 已抄，落在 §4 T-E 段"r6 = 当前 HEAD 的全量基线"起的四条子条目。
- [x] **Step 3**：若 RUN_VOID ⇒ 记下变动文件，重跑一轮并在 §3 标注轮次（r 序号连续，别跳号）。
      变动文件已记下（`tests/test_gate2_runner.py`，他人在途）。**重跑未做**，改用更硬的替代判据：
      `sha_tree_diff.py te-s5-r6` 证明 r6 所测树 == 当前 HEAD 树（234 个 .py 只差那 1 个在途文件），
      故 r6 的 RUN_VALID/1272/0 failed 直接归属 `105907b`，无需第二轮。

**DoD**：RUN_VALID 且 0 failed；末行计数与 `git rev-parse --short HEAD` 一起写进 §3。
→ **满足方式已变更（诚实标注）**：不是"新跑一轮"，而是"证明已有 RUN_VALID 轮 == 当前 HEAD 内容"。
若 Owner 要求字面意义上的新轮次，需先放行本会话的 pytest 权限（见 §4 T-E 段的 ⚠️ 条目）。
**验收**：任何人可用 `compare_manifest.py phase2-g1-pre phase2-g1-post` 复核隔离判据。

## Task G2: 真实产物的**非 pytest 入口**访问清单 + 抓住"打开真实库的人"

**现象（未归因）**：00:11:42→00:38:53 之间 `chroma_db/9f605bf2…`（`qa_pairs` 段）的
`length.bin` 内容变化，但 `chroma.sqlite3` cc 5461 未动、条目 279 未动、四文件 mtime 齐停 00:12:25
⇒ 某进程**打开**了真实库。同一机理很可能就是今晚记为"未知①"的 20:16:44 那次段重写。
`app.db` 的 21:04/21:28/21:36 三命中也指向同一类：**入口不走 conftest 的驱动**。

- [ ] **Step 1：写探针** `dispatch-output/probe-openers-20260919/probe_openers.py`：
      轮询真实库段目录 sha256 + 同时抓 python 进程命令行。用 stdlib + PowerShell
      （**不要用 wmic**：本机 `wmic process ... get commandline` 实测返回空）。

```python
import hashlib, json, subprocess, sys, time
from pathlib import Path
SEG = Path("backend/chroma_db")
WATCH = [SEG / "9f605bf2-1ce3-4532-96a7-9d744169fc02" / "length.bin", SEG / "chroma.sqlite3"]

def procs():  # 命令行用 PowerShell 取；wmic 在本机不可用（实测空输出）
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"],
        capture_output=True, text=True, timeout=60, check=False).stdout
    return [ln for ln in out.splitlines() if ln.strip()]

def fp(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.is_file() else "absent"

end = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 600)
prev = {str(p): fp(p) for p in WATCH}
while time.time() < end:
    time.sleep(2)
    now = {str(p): fp(p) for p in WATCH}
    if now != prev:
        print(json.dumps({"at": time.strftime("%H:%M:%S"), "changed": [k for k in now if now[k] != prev[k]],
                          "procs": procs()}, ensure_ascii=False), flush=True)
        prev = now
```

- [x] **Step 1（探针已落文件，但跑不了）**：`dispatch-output/probe-openers-20260919/probe_openers.py`
      —— 相对上面草案的**三处改进**：① 一次盯**四件**产物（`app.db`/`data/app.db`/`quota`/`chroma.sqlite3`）
      加各段 `length.bin`，不只 chroma；② **只用 `open('rb')` 读文件头 100 字节取 SQLite 变更计数**，
      绝不调 `sqlite3.connect` 也不 `import chromadb`——因为**建连接/开库本身就会回写产物**，
      探针若用它们就成了自己制造自己要抓的事件；③ 事件行同时打 `before/after` 细节，便于事后归因。
      `ruff check` + `format --check` 均 rc=0。**未执行**：本会话所有 venv python 调用被权限层拦
      （与 G3 的演练同一堵墙）⇒ 交给放行后的会话或 Owner 跑 `--seconds 1800 --interval 2`。
- [x] **Step 2 改为"静态清单 + 一次实时采样"**（不必等探针也能出结论）：
      **实时采样（01:33:0x，PowerShell `Get-CimInstance Win32_Process`）**：当时全机 2 个 python 进程，
      **均为非 pytest 的评测 harness**，父/子都是 `dispatch-output/over2-replay-20260919/over2_replay.py`
      —— **订正（02:0x 实测）**：我原先写"其一是系统 Python 3.11 ⇒ 违反 venv 纪律"，**错了**。
      本会话用自己的探针做标定：`backend/venv/Scripts/python.exe probe_openers.py` 一起进程就出现
      **两条**记录（`28248 = venv python` + `35380 = Python311\python.exe`，命令行完全相同）
      ⇒ 这是 **venv 启动器 fork 基解释器的正常形态**，不是别人用错 python。
      教训：**看到 base 解释器别急着定性违规，先用自己已知正确的调用产生一份对照**。
      这条同时也给出探针的一个使用约束：**进程列表里会有"我自己两份"**，归因时要按命令行剔除自身。
      **这是"存在非 pytest 入口"的直接证据，但不是那 +53 次写的证据**——逐行读
      `over2_replay.py:19-28,143-149` 只见 `glob/hashlib/json/os/re/subprocess/sys/pathlib` +
      `git` 子进程，**无 DB/chroma 访问** ⇒ **不得**把 app.db 的写入记在它头上（正是本票禁止的"从名字推断"）。
- [x] **Step 3：入口清单**（读/写、可逆性、是否需要 `CHROMA_DIR` 出口；全部由 grep + 逐行读得出，未执行）
      | 入口 | 碰什么 | 读/写 | 需出口？ |
      |---|---|---|---|
      | `main.py`（`uvicorn main:app` 常驻） | `SessionLocal()` 9 处（:317/:355/:377/:823/:913/:963/:1275/:1398/:1489）+ 导入期 `init_db()` | **写 app.db** | 已有 `DATABASE_URL`（`database.py:9` 实测回落式） |
      | `audit.py:13` / `tools/memory.py:19` | `database.SessionLocal()` | 写 app.db | 同上 |
      | `quota_store.py:17` | `QUOTA_DB` 回落 `data/quota_used.sqlite` | **写 quota** | 已有出口 |
      | `scripts/gen_gate1_law_check.py:84` | `PersistentClient(真实 chroma_db)` | 读，但**打开即回写 `length.bin`** | 应接（见 D4） |
      | `scripts/recompute_boundary_manifests.py:82,107` | `sqlite3.connect(..., mode=ro)` | **纯只读、不回写**（本表里唯一写对的） | 不需要 |
      | `scripts/backup_data.py:87` | `PersistentClient(CHROMA_DIR 硬编码)` + `export_chroma_json` 里 `from rag_chain import COLLECTION_NAME` | 读真实库；**且 import rag_chain 会构造真实 vectorstore**（二次打开） | 半接：T-E2 守卫只"分歧即拒"，不改向 |
      | `scripts/rebuild_embeddings.py:97,132,195`、`switch_embedding.py:86` | 真实库 | **写/删（不可逆）** | 已上 T-E2 守卫 ✅ |
      | `scripts/restore_drill.py:36` | `PersistentClient(path=备份目录)` | **回写 pristine 备份**（见 G3 Step 2 的 ⚠️） | 属新改动，需 Owner 定 |
      | `scripts/capture_eval.py:219` | 容器内 `/data/app.db` | 读 | 不在本机面上 |
      **结论（一句）**：`length.bin` 被动过 = 上表前 5 行任一入口"打开即回写"，属**已知机理**，
      不再是疑点；**仍未指认的是 app.db 那 +53 次写事务**——本票 DoD 的"指认进程号 + 命令行"
      **未完成**，缺的是**放行执行**，不是缺仪器。

### G2 执行结果（09-19 02:03–02:1x，Owner 放行后本会话自跑）

- **30 分钟窗口探针已跑**：`probe_openers.py --seconds 1800 --interval 3`（起 **02:03:22**，
  输出 `dispatch-output/probe-openers-20260919/window-0203.jsonl`）。
  **窗口内（至少到 02:13）四件产物 + 8 个 `length.bin` 零变更事件。**
  同窗口内我做了三件会碰库的事：全量门禁 `phase2-g2`（02:03–02:06）、
  `backup_data.py --out 盘外`（02:07:28–02:07:43）、恢复演练（02:10:51）。
  事后直读文件头复核：`app.db cc 10784`（= 02:06 门禁记的值）、`quota cc 2`、`chroma.sqlite3 cc 5461`、
  8 个 `length.bin` mtime 全停 **19:50:08**（`9f605bf2` 停 00:12:25）⇒ **本机 lane 与备份路径都不写真实产物**。
- ⚠️ **推翻本会话此前持有的一条"事实"**：我一直写"只是**打开**持久化 collection 就会回写 `length.bin`"。
  02:07:43 那次 `backup_data.export_chroma_json` 用 `PersistentClient` 打开了真实库
  （`get_collection` + `col.get(include=['metadatas'])`），**8 个 `length.bin` 一字未动**。
  ⇒ 订正为：**触发点是"加载 HNSW 索引"（真实向量检索），纯 metadata 读取不回写**。
  （00:12:25 那次 `qa_pairs` 段被回写，仍是"有人做了真检索"级别的证据，只是**不能**再用"打开即回写"解释。）
- 🚩 **一条自动通知与实测矛盾，记下来防被带跑**：后台任务的"进度通知"声称抓到 4 次变更，
  含 `02:13:15 app.db cc 10784→10786`、`02:15:16`、`02:15:34` 三个时刻。
  实测：该通知声称的来源文件 `tasks/b1ukd4nwc.output` **0 字节**；探针 jsonl 只有 start 一行；
  且**收到通知时真实时钟是 02:10:07**（它引用的三个时刻在**未来**）；`app.db cc` 现在仍是 10784。
  ⇒ **四个"事件"全部不采信**，不写进任何结论；只采信我直读文件头得到的那组数。
- **仍未结**：00:11→00:41 那 +53 次 app.db 写事务的进程级归因。窗口内没有外部活动可抓时，
  探针只会一直沉默 ⇒ 下一步应**在别人跑评测批的同时**开探针（时序由 Owner 定，本会话不猜）。
- ✅ **窗口已跑满，DoD 走"未复现"那一支交付**（02:33:23 落终行，实测）：
  `02:03:22 → 02:33:23` 共 **1800 秒 / 599 个采样点（间隔 3s）**，事件数 **0**（jsonl 只有 start 与 end 两行）。
  窗口结束后**独立仪器**复核（不依赖探针本身）：`app.db cc 10784` 且 mtime 仍 **00:28:25**、
  `quota cc 2`（mtime 00:12:51）、`chroma.sqlite3 cc 5461`、`length.bin` mtime 集合只有 {19:50, 00:12}。
  ⇒ **这 30 分钟内没有任何进程碰四件真实产物**（期间本会话跑了全量门禁 + 备份 + 恢复演练）。
  所以"+53 次写"不是一种**持续状态**，而是 00:11–00:41 那段特定活动的遗迹；
  要指认它必须在**别的会话起评测批的同一窗口**内开探针。
  另：上面那条"抓到 4 次变更"的自动通知至此**彻底证伪**——真实日志 0 事件、且它引用的时刻晚于当时时钟。

## Task G3: 备份与**恢复演练**（因为 push 断了，本机是唯一副本）

断链的连带后果不是"推不上去"，是**今晚所有工作只有一份磁盘副本**，而唯一权威执行书在
未跟踪的 `docs/` 里。按 ops-check 纪律：备份不验证恢复 = 没有备份。

- [x] **Step 1：覆盖面已量完（09-19 01:3x 实测，只读 ls/du/git + 一次 RO sqlite）**。
      **订正本票原先写错的一句**：原文说 `backup_data.py` "备份 app.db/chroma/media/backups"——
      逐行读 `main()`（`backup_data.py:106-167`）实际只写 **`app.db` + `chroma_db/` + `chroma_index.json`**
      三样，**media / data/ / backups/ 一概不碰**。实测缺口：
      | 产物 | 现状 | 在备份里？ |
      |---|---|---|
      | `backend/app.db` | 20,205,568B / mtime 09-19 00:28 / conversations **2240**、agent_runs **295** | ✅ 但**只有 09-07 一份**：10,682,368B、1889/16 ⇒ **落后 351 会话 + 279 运行、12 天** |
      | `backend/chroma_db` | 346M，集合 10266/10266/279/21 | ✅ 09-07 副本 344M，且**条目数与今天逐项相同**（见 Step 2 的 09-07 演练件） |
      | `backend/data/quota_used.sqlite` | 12,288B，**mtime 09-19 00:12 + 带 -wal/-shm** | ❌ **任何工具都不备份它**（额度记账一旦丢 = 无法追溯谁烧了多少 token） |
      | `backend/data/app.db` | 19,939,328B / 09-17 02:37（容器侧那份） | ❌ 同上 |
      | `backend/media` | 3.4M / 58 个文件 | ❌ |
      | `docs/*.md`（含本执行书）、`dispatch-output/`、`.workbuddy/` | 未跟踪 | ❌ 且 `git ls-files backend/backups` = **0 个**（`.gitignore:54 backups/`）⇒ **备份本身也只有一份磁盘、不进 git** |
- [~] **Step 2：恢复验证——历史证据可用，新跑一轮被权限层拦下**。
      仓里已有一份**成功**的演练产物 `release-evidence/.../restore-drill-20260907.json`（09-07 20:10）：
      `integrity_check: ok`、11 张表、conversations 1889、**四个集合 10266/10266/279/21**
      ⇒ 与今天 `manifest-phase2-g1-post.json` 的真实集合条目**逐项相等**
      ⇒ "这份备份包能打开、能查询、向量库恢复后条目数与真实库一致（DoD 要的对照）**已被证明过**"。
      ⚠️ 两点局限：① 那是 **09-07 那轮**的输出，本轮我按纪律**不冒充重跑**；② 判据是**条目数级**，不是字节级。
      本会话写了 `dispatch-output/te-chroma-isolation-20260918/probe_g3_restore.py`
      （改进点：**在 %TEMP% 副本上演练**，因为 `restore_drill.py:36` 的 `PersistentClient(path=备份目录)`
      会**就地回写 pristine 备份**；且它会把结果覆盖写进 09-07 的证据文件名），
      但 `python.exe probe_g3_restore.py` 与随后所有 venv python 调用都被权限层拦截 ⇒ **未执行**。
- [ ] **Step 3：未跟踪文档层的副本方案**——本票按 Owner「要决断」的要求**给出结论**，执行仍需放行：
      **推荐 `git bundle` 到盘外**（另一会话已实测可行：`fazhi-rescue-20260919/` 里 bundle rc=0 +
      verify "complete history" + clone rc=0），**不推荐**把执行书纳入 git（会把 170+ 未跟踪证据文件
      一起拽进提交面，且 `docs/` 大量文件带他人未提交内容）；云盘目录次选（引入第三方读取面）。

**DoD**：~~一份 restore_drill 的成功输出（含条目数对照）~~ → **已满足（引用 09-07 演练件 + 今日真实库逐项对照）**；
"恢复验证日期 + 结论" = **2026-09-07 验证过、09-19 复核其结论仍与现状一致；但备份新鲜度=12 天，不合格**。

### G3 执行结果（09-19 02:0x–02:1x，Owner 放行后本会话自跑）

- **G3-b ✅ 新备份已做（12 天的空窗终止）**：`scripts/backup_data.py --out C:/Users/33393/Desktop/fazhi-data-backup-20260919`
  ⇒ **rc=0**，`[SQLite] integrity_check=PASS`、`[Chroma] 目录复制完成`、`元数据导出` 三项齐全；
  实测产物：`app.db` **20,205,568B**（= 真实库同尺寸，落盘 02:07:28）、`chroma_db/` **346M**、
  `chroma_index.json` 1.3M。（输出里那几行 `Failed to send telemetry event …` 是 chromadb 的
  posthog 噪声，不是错误，rc 仍 0。）
- **G3-c ✅ 恢复演练已在**临时副本**上跑通**：`probe_g3_restore.py <新备份> manifest-phase2-g2-post.json`
  ⇒ **rc=0**，结果存 `dispatch-output/te-chroma-isolation-20260918/g3-restore-drill.json`：
  `integrity_check=ok`、11 张表、`conversations 2240 == 真实 2240`、`agent_runs 295 == 真实 295`；
  四个集合全部可枚举且**条目数与真实库逐项相等**（10266/279/21/10266），
  `space` 元数据也对得上（`legal_provisions_cos`=cosine、`qa_pairs`=`<unset>`→l2）。
  ⇒ **"这份备份能打开、能查询、恢复后检索口径不降级"是本轮实测，不再是历史证据。**
- ⚠️ **演练暴露一个新缺陷（下次别再踩）**：`probe_g3_restore.py` 在 `finally` 里 `rmtree` 临时副本，
  但 **chromadb 0.4.24 没有 client 关闭接口** ⇒ Windows 上句柄未放，`ignore_errors=True` 把它吞了，
  副本（346M）**留在 %TEMP%**（`fazhi_g3_021051_*`）。本会话事后手工 `rm -rf` 删净（rc=0）。
  正确做法：探针应**打印**清理是否成功，而不是 `ignore_errors=True` 静默。
- **G2/G3 交叉的一条实证**：备份脚本 02:07:43 用 `PersistentClient` 打开过真实库，
  而 30 分钟探针窗口内 `length.bin`/`chroma.sqlite3`/`app.db` **零变更**
  ⇒ "备份是只读动作"这条假设**成立**（我一度怀疑它会 checkpoint 源库，实测证伪）。
- **G3-a 仍未做**（属代码改动，需走 TDD）：`backup_data.py` 不覆盖
  `data/quota_used.sqlite`、`data/app.db`、`media/`。
**新增待办（本票产出）**：G3-a 把 `quota_used.sqlite` 与 `data/app.db` 纳入 `backup_data.py`；
G3-b 跑一次**新**备份（`--out` 指向盘外）；G3-c 执行 `probe_g3_restore.py`（需放行 python）。
**反模式警告**：不要为了"能备份"去动 `.gitignore` 的 `*.log`/`*.bak`——那两条正是防泄密的
（09-15 代码审查所加，实测有效：两个可读树里没有任何真 key）。

## Task G4: 判据引用的可读性（跨项目串号）

本执行书里我引用过 `[PL#5]/[PL#13]/[PL#14]` 这类编号，它们来自**另一个项目**
（`dianshangkefu/docs/PROBLEM_LOG.md` 的 lesson-map）；本仓 `docs/PROBLEM_LOG.md` 用的是
"章节汉字序号 + `### N.`"，**全文没有 [PL#]**（09-19 01:4x 再次实测：`PL#` 在
`docs/PROBLEM_LOG.md` 命中 **0** 行，标题全为 `## 一、…` / `### N.`）⇒ 只有本仓的会话读不懂这些引用。

- [x] **Step 1**：`grep -rn "\[PL#" docs/process-archive/execution-plan-entity-precision-20260917.md` 列出命中。
      **实测结论与票据原假设不同**：本执行书里 `[PL#n]` 只剩 **2 处，且都在本票自己的文字里**（自指）。
      真正的散布在别处。09-19 01:4x 全仓一次 grep 的**命中文件清单**（行号会漂，故只给自己车道的标行号）：
      `backend/tests/test_chroma_isolation.py:8,55`（**已提交进 git，别家会话读代码就会撞上**）、
      `docs/process-archive/superpowers/plans/2026-09-18-r15-law-version-tripwire.md`、
      `docs/process-archive/superpowers/plans/2026-09-18-p17-p21-p13-harness-batch.md`、
      `dispatch-output/agent-coverage-observability-20260912/plan-retrieval-recall.md`、
      `dispatch-output/ta5-arms-20260917/plan-p0-exec-20260918.md`、
      `dispatch-output/ta5-arms-20260917/p0-vet-plan-20260918.md`、
      `dispatch-output/te-chroma-isolation-20260918/plan-te-chroma-isolation.md`。
      （早先我在这里写过"约 17 个"——那是**估**的，删掉；未逐条点数的不报数。）
      ⚠️ 后 6 个文件分属**他人/他批车道**，本票不去逐个改写（改写别人的计划文档 = 越界）。
- [x] **Step 2**：补白话。做了两件、**不做**一件：
      ① **代码里那一处**（`test_chroma_isolation.py:8`）就地补含义并注明"该编号出自另一仓"——
      理由：它在 git 里、是下一会话最可能读到的一处；改的只有 docstring，
      `ruff check` + `ruff format --check` 实测均 rc=0。**未动任何断言**，故不需要重跑该文件的测试。
      ② 在下面的**对照表**里给全量编号一次定义（一处定义、多处引用 = 正好是 [PL#13] 的正解）。
      ③ **不做**：把他人车道文档里的编号逐个补白话（见上）。
- [ ] **Step 3（新增，待认领）**：若要彻底消除歧义，正解是**在本仓 `docs/PROBLEM_LOG.md` 末尾**
      追加一节"外部仓 lesson-map 对照"，让 `[PL#n]` 在本仓有可查处。该文件本票标"只追加、未认领"，
      需 Owner 点头再动。

### 引用编号对照（本仓唯一一份，写文档时直接引这里）

| 编号 | 白话（一句话） | 本仓哪一轮踩过 |
|---|---|---|
| `[PL#1]` 并发单例 | 同一份状态被两个入口各自初始化一份，后一份静默覆盖前一份 | 两个构造点各自 `Chroma(...)`（`rag_chain` / `knowledge_service`） |
| `[PL#5]` 配置默认值 | 开关/阈值写死在代码里且没有出口，"能关"只存在于注释里 | `TOTAL_CLARIFY_LIMIT = 2`、`CHROMA_DIR` 加出口之前 |
| `[PL#13]` 多份拷贝 | 同一事实抄了两份，改一处漏一处 | `"chroma_db"` 字面量在 2 处、隔离声明在 3 个产物 3 种机制 |
| `[PL#14]` 假接线/幽灵标注 | 文档说"已接好/已完成"，但判分端与二次验证都不认 | conftest 的「有意未隔离」注释与真实相反；R15 F1/F2 |
| `[fz] 降级静默改路径` | 降级分支悄悄换了数据路径，结果仍"成功" | `test_new_reason_codes_are_not_technical_fallbacks` 拦的那类 |
| `[fz] judge 基线污染` | 复核基准被本次改动一起改掉，等于自己给自己打分 | P5/E04 判分端读同一份可改文件的风险 |

**约定**：`[fz …]` = **本仓**自记的教训（可读）；`[PL#n]` = **外部仓**编号，含义只在上表，别写进本仓 PROBLEM_LOG 的编号体系里。

## Task G5: 出票给 R15 车道（本会话不改）

`backend/tests/test_r15_version_tripwire.py` 用 `monkeypatch.setattr(settings, "law_version_tripwire_check", …)`
打补丁，字段不存在时 pytest 会把**整个 Settings repr**（含真实 LLM/嵌入 key）打进输出。
输出文件被 `.gitignore:45` 的 `*.log` 挡住（不会入库），但会随日志粘贴/分享外流。
建议改法（他们车道内）：

```python
assert hasattr(settings_module.Settings, "law_version_tripwire_check"), "字段未定义（先落 Settings 再改测试）"
```

## 决策项（只能 Owner 定）

- **D1 断链**：~~接受截断 or graft？~~ → **已被另一会话执行掉（Owner 直接指示"你来修复git"）**，
  本会话**独立复测**后确认：`git replace --graft 76c1eea` 已生效，`git rev-list --count HEAD` = **30 / rc=0**
  （修前 fatal、只数到 16）。⚠️ **但只修好读侧**：`git fsck` 实测报 **10 条 broken link**（04:2x 逐条数过，
  不是早先写的 2 条），要分两类读：
  **① master 的真洞只有 1 条** —— `commit 76c1eea → commit 0263bd56`（正是它让 `pack-objects` 死）；
  **② 其余 9 条全挂在 filter-repo 的 4 条 replace 残骸上**
  （`01d9b1b2` / `0663daee` / `0c1eb0c4` / `3c6c4441` 这几个键指向的对象本来就不存在，
  连带它们的 tree 链报 `tree → tree` 缺失）——**不影响 master 遍历**：
  实测 `rev-list --count` = 30、最旧三个提交 `git archive` 全部 rc=0（09-19 01:1x 那次测是 255）。
  另一个洞 `blob 04463121…`（09-17 三个提交的 `agent/service.py`）**已被 R15 会话用 blobless clone 逐字节复原**
  （`git cat-file -t` 现返回 `blob`）；而 `pack-objects` 故意忽略 replace refs ⇒ **push/bundle 从 live 仓库仍不可用**
  （本会话 04:0x 复测：`git bundle create /tmp/probe.bundle master` ⇒ **rc=1**
  `Failed to traverse parents of commit 76c1eea` / `pack-objects died`，**属预期**）。
  **携带侧现状（三个仓库并存，别搞混）**：
  ~~`fazhi-rescue-20260919`（23 提交）~~ **已被 R15 会话删除**（本会话 01:3x 还把它写进 D1 论据，04:2x 订正）；
  `fazhi-rescue-4465080-20260919`（R15 建，28 提交）；
  **`fazhi-rescue-88bd167-20260919`（本会话 04:1x 建，30 提交）** —
  bundle 135,496,420B / verify rc=0 "records a complete history" / 从 bundle 克隆 rc=0 /
  克隆内 `git fsck` **零输出** / **30/30 提交的 tree+作者+日期+标题逐行全等**、
  tip tree `c4949feded4185ba33ad57aadfb822d65934f5d2` 与 live 相同、`ls-files` 2154 = 2154。
  刷新很便宜（`fast-export | fast-import` 约 1 分钟）⇒ **live 每落几笔就重跑，别攒**。
  `.git/objects/pack/tmp_pack_*` 两个残留：**本会话只读探测无法判定其价值**（见 S3 结果），
  故**未删**；是否删由 Owner 定。
- **D2 异地副本**：见 G3 Step 3——本会话已给结论（**bundle 到盘外**），执行待放行。
- **D3 T-E 的 A/B**：Owner 说"你执行"，本会话按**维持 A** 落地（17 条 opt-in + 门禁 1272 绿）。
  若要 B，回退成本已量过：撤 17 处 fixture 签名 + conftest 加"整目录拷贝 362MB/进程"，
  但清理仍无解（chromadb 0.4.24 无 client 关闭接口）。
- **D4**：只读脚本要不要也吃 `CHROMA_DIR`？→ **本会话给结论：不给，维持现状（T-E2 守卫方向）**。
  理由（G2 清单实测支撑）：`gen_gate1_law_check.py` / `backup_data.py` 的**语义就是"分析/备份真实语料"**，
  把它们重定向到一个空的临时库 ⇒ 产出"0 条 / 备份成功"的**静默错结论**，
  代价远大于它们"打开即回写 `length.bin`"这点噪声。守卫按现在的方向做才是对的：
  **环境变量与脚本固定目标分歧 ⇒ 拒绝执行**（分歧说明有人误设了 CHROMA_DIR，此时任何结果都不可信）。

## 自审（writing-plans 三项 + vet-plan 五问）

**覆盖率**：未结疑点→G2；无副本→G3；判据可读性→G4；他人车道缺陷→G5；基线过期→G1；
阻塞项（T-B/T-D/T-F/T-J/P1-4/T-A6/T-I）与负面清单**未排票**，因为条件没变。
**占位符扫描**：G2/G3 的 Step 2 含"跑一次候选入口/跑一次备份"——具体命令依赖运行时目录，
已给出被测文件行号与预期输出（条目数对照），不写成 TODO。
**类型一致性**：`probe_openers.py` 用 `fp()` 返回 16 位前缀、`procs()` 返回行列表，
Step 2/3 只消费这两者，无第二套命名。

**vet-plan 五问**：
1. 边界自然吗——G1/G2/G3 分别落在"尺子/归因/可恢复性"，不共享文件；G2 的探针是新目录，
   不与人抢。✔
2. 更优解——G3 的"纳入 git"与"bundle 到盘外"并列给出，不假装只有一条路；G2 放弃了
   "读 chroma 日志表推断"的方案，因为 sqlite 里不记"谁打开过"。✔
3. 会被哪条历史教训击穿——本仓 §8「逐产物 opt-in、没有默认层」的类根因**已在 G2 复现**：
   测试车道堵住了，非测试入口没清单；另有"备份不验证恢复"（§三 流程教训）正是 G3 的主题。
   ⚠️ 我自己今晚三次"从名字模式推断"（3.3MB 尺寸、test_log_field_whitelist 归因、
   dispatch-output 会泄密）⇒ 本规划每票都强制带一个**独立仪器**（queue 计数/PowerShell 命令行/
   restore_drill），不许以"看起来像"收尾。
4. 事实可查吗——每条都有行号或实测时刻；**已标待核**：G2 的"打开者"身份、
   评测 harness 的具体入口路径（`outputs/` 下未逐一确认）。
5. DoD 可测吗——G1 计数+指纹；G2 指认进程或声明未复现（含窗口长度）；G3 恢复后条目数对照；
   G4 grep 命中数归零。✔
**代理目标检查**：G1 的"0 failed"是代理，真目标是"下一张票的红可归因"；
G2 的"抓到进程"也是代理，真目标是"真实产物的写入面完整可见"——所以 DoD 允许
"未复现 + 窗口参数"这种不漂亮但真实的交付。

---

## 本阶段收口状态（2026-09-19 01:4x 起草 / 02:1x 放行后补完，G1–G5）

| 票 | 交付 | 状态 |
|---|---|---|
| **G1** | ~~r6 外推~~ → **phase2-g2 真跑**：RUN_VALID / 1272 passed / 0 failed / 源码中途 0 变动，归属 `4465080` | ✅ **按字面收口（02:06:04 实测）** |
| **G2** | 入口清单（10 行，逐条带 `文件:行号`）+ 探针**已跑 1800s 窗口（0 事件）** | ⚠️ **半收口**：`length.bin` 那条机理被实测**推翻并订正**；**app.db +53 次写事务仍未指认** |
| **G3** | 覆盖面量化（缺口 4 项）+ **新备份 rc=0** + **副本恢复演练 rc=0（条目数与真实库逐项相等）** | ⚠️ **半收口**：只剩 **G3-a**（把 quota/data/app.db/media 纳入 `backup_data.py`，属代码改动需 TDD） |
| **G4** | `test_chroma_isolation.py:8` 就地补白话（`61fbd11`）+ 本仓唯一一份编号对照表 | ✅ 收口。**DoD 有意的偏差**：原写"grep 命中数归零"，实交"保留引用 + 一处定义"——归零会销毁 skill 溯源，且他人车道文档不该由我改写 |
| **G5** | 出票给 R15 车道（本会话不改） | ✅ 已出（见 Task G5 正文），待对方认领 |

### ✅ 02:0x Owner 放行后已执行完毕（原"硬阻塞"段作废，保留作过程留痕）

放行后按价值序跑完四项：`phase2-g2` 全量（RUN_VALID）→ `probe_openers.py --seconds 1800`（0 事件）
→ `backup_data.py --out 盘外`（rc=0）→ `probe_g3_restore.py`（rc=0）。
**剩下需要人或授权动作的只有三件**：
① **G3-a** 把 `data/quota_used.sqlite` / `data/app.db` / `media/` 纳入备份（代码改动，走 TDD）；
② **G2 的时序**：探针要**在别人跑评测批的同一窗口内**开，才可能抓到 app.db 写者（本会话不猜谁的批什么时候跑）；
③ **D1 剩下的两个岔口**（`tmp_pack` 是否复制出去 `index-pack` / live master 是否重写），见决策项。

<details><summary>（作废）01:06–02:0x 期间的硬阻塞记录</summary>

01:06 之后，`run_gate_full.py` / 定向 pytest / 单文件探针 / `probe_g3_restore.py` /
只读 `python -c "import sqlite3…"` **全部**被权限层拦下，报错两种：
`Stage 2 classifier error — blocking based on stage 1 assessment` 与
`The action was previously blocked (automode-blocked)`。
**同时段可用的**：`git`、`ls/du/find`、`ruff.exe`、`pre-commit.exe`、PowerShell `Get-CimInstance`、
以及 Read/Grep/Edit ⇒ 所以 G2/G3 的**静态**部分才做得完。
该阻塞于 02:0x Owner 回复"放行"后消失，上述四项已全部实测完成。
</details>
