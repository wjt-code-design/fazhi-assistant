# 已有提交代码审查（2026-09-18）

## V1 修复复验（2026-09-19，未提交）

V1 快速双击竞态已修复。`useLawCards` 现在让同一待决引用共享请求版本，使两次点击都执行函数式状态切换；点击不同引用或清空/切换会话仍递增版本并丢弃旧响应。没有增加依赖或全局状态。

- 回归测试先红：同一pending请求只调用一次API，但预期两次状态切换时实际仅一次，`1 failed / 3 passed`。
- 修复后聚焦测试：`4 passed`。完整前端：**7个文件、54项测试通过**，`tsc --noEmit`通过；Next lint exit 0，仅保留两处未修改`<img>`组件的既有警告。
- 使用与发现缺陷时相同的Edge/Playwright脚本和受控API数据复验，`fastDoubleClickCloses`由`false`变为`true`；页面身份、非空、快照版本隔离、404不回退、切会话丢弃旧响应、无框架遮罩及无运行时异常均为`true`。控制台唯一404为测试主动注入的缺失快照场景。
- 浏览器测试使用真实React页面但拦截API，不代表真实后端浏览器E2E；后端鉴权与快照存储仍由前述HTTP集成测试证明。

因此，本轮独立验收发现的唯一新问题V1已关闭。下节保留发现时的原始证据，作为审查轨迹，不应再解读为当前未解决项。E1通用事实一致性限制及两项待决安全策略仍保留。

## 修复独立验收（2026-09-19，接续中断结果）

**结论：部分通过，不作整体通过声明。** 本轮只复审、补测试与证据，没有继续修改生产代码；仍未暂存、未提交。基线固定为 `88bd16713a9c121ad3914e609464f395f8ed73fe`，范围为该基线之后的未提交修复与相关新增文件。此前325项后端、53项前端是上一轮证据，本轮未重复执行整套。

### Standards（工程质量轴）

**V1 [P3] 请求未返回时快速双击同一引用，卡片仍打开（新回归，已复现，高置信）。**

- 位置：`frontend/lib/hooks/useLawCards.ts:44` 与 `69–77`。
- 复现：初始卡片关闭；延迟 `/api/law` 响应；对同一 `.law-ref` 双击（75ms间隔）；释放响应。实际仍显示卡片，预期两次切换后关闭。
- 原因：两次点击复用同一 pending Promise，但第二次递增 `requestVersion` 使第一次退出；仅第二次执行状态切换，其看到的旧状态仍是关闭。基线代码没有该提前退出，两次函数式状态切换能顺序执行。
- 实际 Edge 浏览器的 `fastDoubleClickCloses=false` 证明现象，不仅是静态推测；正常等待后再点收起通过。只影响快速重复点击，不影响快照内容或鉴权，故将审查者初报P2校准为P3。
- 最小修复方向：在请求前保存目标及开/关意图，保留跨会话旧请求失效机制；补同一请求返回前连续点击的回归。**本验收轮未实施该修复。**

审查者另提“因此该借款已经全部清偿”及含“此前/另一笔”的事实会跳过检查：这些属于E1已明确记录的独立短句/模糊语境限制，不重复计为新缺陷，也不据此关闭原能力缺口。规范轴最终保留 **1项新确认问题，最高P3**。

### Spec（需求轴）

口语金额、E1报告反例的writer/verifier双防线、E2条号归一、E3历史快照、E4依据展示均补齐同一测试的修复前后对照。E1仍是部分收敛，通用事实一致性没有验收通过。

Spec审查者提出R15分水岭检查可能过宽；通过 `git show 88bd167:backend/agent/limitation_calc.py` 核实该函数在基线已存在，本轮未修改，不能归为本轮引入。保留为相邻既有行为待独立核验，不把静态候选升级为已确认缺陷。需求轴 **0项新确认问题，E1仍部分满足**；此结论不是宣称全仓无缺陷。

### 修复前后对照

固定提交导出到临时副本，仅复制当前验收测试；业务源代码没有混入当前修复。同一选择表达式：

```text
pytest tests/test_review_regressions.py tests/test_law_snapshot_review.py -k "oral_fee_writer or fact_conflict_writer or verifier_rejects or snippet_citation or lookup_normalizes or run_snapshot_owned" -q --tb=short
```

| 代码版本 | 结果 | 说明 |
| --- | --- | --- |
| 固定基线88bd167 | 8失败、2通过、40未选中 | 失败为两类口语金额、writer矛盾事实、独立verifier矛盾事实、snippet引用遗漏、两类条号归一、快照被当前版本替代；是功能失败而非环境报错 |
| 当前未提交修复 | 10通过、0失败/错误/跳过 | JUnit时间66.336秒；正常阿拉伯金额及中文条号对照也通过 |

新增独立verifier用例，避免writer的先行失败掩盖第二道防线。快照测试将当前索引设为不同的明确哨兵文本，验证实际返回内容而非仅断言某函数没有调用。S1是补覆盖，不要求新增正向测试在旧代码上失败。

证据目录：`C:/Users/33393/AppData/Local/Temp/alh-verification-d1bf78a07da34e298e9668894dcb7b84/`，内有 `before.xml`、`after.xml`、`browser-check.cjs`、`browser-result.json` 和三张截图。注意为临时目录，清理系统临时文件会移除这些附件。

### 浏览器验收（实际前端 + 受控API数据）

- 环境：`http://127.0.0.1:3187/chat`，本机Edge无头独立上下文，Playwright；Browser插件/skill未提供，复用已安装依赖，无新安装。桌面1440×1000，窄屏390×844。
- 路径：载入测试用户 → 历史A → 点击引用 → 关闭 → 历史B同条号 → 缺失快照 → 请求未返回时切换会话 → 延迟响应下双击。
- 所有 `/api/` 请求由测试样本拦截，其他外网请求被禁止。浏览器证据证明真实React/DOM交互，不是前后端连接真实存储的完整E2E；后端鉴权/快照存储由独立HTTP+临时数据库测试覆盖。

| 检查 | 结果 |
| --- | --- |
| 页面URL/标题、非空内容、无框架错误遮罩 | 通过 |
| 旧run展示旧证据及2022基准日；新run不复用旧证据 | 通过 |
| 正常点击展开，再点收起 | 通过 |
| 快照404提示不可用，未请求无run的当前版本 | 通过 |
| 切换会话后丢弃旧请求结果 | 通过 |
| 延迟响应时快速双击收起 | **失败，V1** |
| JavaScript运行时异常 | 无；控制台唯一404来自主动注入的缺失快照场景 |
| 移动端 | DOM测得无整页横向溢出；截图捕获到侧栏过渡状态，**不据此宣称移动端视觉验收通过** |

截图 `desktop-old-snapshot.png` 显示旧证据及基准日；`fast-double-click-result.png` 显示双击后卡片仍展开。脚本首次因同名侧栏/快捷入口造成定位器歧义而未执行交互，限定侧栏后通过定位；该次属于测试脚本问题，不计产品失败。最终测试服务已随中断停止，确认3187端口无监听。

剩余限制：V1待修；E1泛化能力未关闭；没有生产构建验收、真实模型评测或真实后端浏览器E2E。依赖检查、真实语料覆盖和两项安全策略观察本轮未扩审。

## 修复记录（2026-09-19，未提交）

按用户授权在 `88bd16713a9c121ad3914e609464f395f8ed73fe` 工作区实施最小修复，保留后续会话已有的版本适用检查等改动。**未暂存、未提交、未推送、未部署**。下文原审查结论为历史记录，不再代表修复后的工作区。

| 编号 | 本轮处理 | 验证与边界 |
| --- | --- | --- |
| S1 | 原中性上下文用例改名为 fail-open 测试；补主体真正相交、责任方向正确的正向用例 | 明确断言 writer `READY`，不再仅断言“未出现新错误码” |
| Spec P1 | 费用入口复用既有 `numeric_tokens` 解析，不另造中文数字解析器 | `5万块`、`五万元`、`50000元` 经 writer/verifier 均可验算 1050/525 |
| Spec P2 | 劳动时效处理中断及多次顺延 | 忽略起算前、届满后及相对于 `as_of` 尚未发生的中断；存续期劳动报酬规则不变 |
| B1 | 补齐 200万、500万、1000万、2000万档费率 | 独立手算锚点及边界两侧；200万元为 22800/11400 |
| B2 | 以知道权利受损日起算，2017-10-01起适用普通三年；补未届满衔接和已届满不复活 | 2019-01-01起算到2022-01-01；仍保留历史案件复核标志，未接入生产工具；不放宽历史年数白名单 |
| B3 | 历史访问仅匹配肯定的执行/引用短语，否定在本分句内处理 | “无法读取历史会话”不拦；后续分句另称“历史会话显示”仍拦 |
| E1 | **部分收敛**：writer 与 verifier 增加同一窄域清偿状态冲突检查及 `FACT_CONTRADICTION` 原因 | 已阻断报告中“尚未清偿→已经全部清偿”的反例（含绕过 writer 的 draft）；不是通用语义蕴含验证，条件、引语、多笔债务、时间变更和其他事实关系仍未覆盖，不将原能力缺口宣称全部关闭 |
| E2 | 在共享 `exact_article_lookup` 入口归一条号 | 中文、阿拉伯、全角条号通过；不只修 HTTP 入口 |
| E3 | `/api/law` 增加可选 `run_id`；验证 run 与会话归属后读保存的证据快照；实时及历史消息透传 run | 快照缺失/无权限返回404，绝不回退当前索引；卡片标明“非完整条文”和基准日。旧消息没有 run 时明确标“当前知识库条文，未关联历史版本”。缓存按 run 隔离，清会话使旧请求失效 |
| E4 | 法律依据展示取 claim 引文与绑定证据 `source_ref + snippet` 的交集，按规范引文键去重 | snippet 中获核验接受的条文不再遗漏，未被 claim 引用的 source_ref 不插入 |

### 本轮新鲜验证

- 首批18个回归用例在修复前：13失败、5通过；失败分别对应费率、口语金额、两类时效、否定历史访问。E1–E4沿用原专项反例，新增工作区验收测试；不宣称所有新增测试均在本轮执行过修复前红测。
- 最终后端选定10个测试文件：**325 passed / 6 warnings，28.31秒，exit 0**。JUnit：`dispatch-output/review-fixes-20260919-junit.xml`。警告为 multipart/httpx 依赖弃用。
- 前端：**7个文件、53项测试通过**；`tsc --noEmit` 通过；Next lint 通过，仅未修改的 `ChatImage.tsx` / `InputBar.tsx` 有既有 `<img>` 警告。新增测试覆盖 SSE final run ID、URL、快照标签与转义、缓存隔离、旧请求失效、失败重试。
- 后端变更文件 Ruff 通过；10个业务文件 mypy 通过（工具提示未注解函数体默认不检查）。
- 测试使用 `conftest.py` 的临时数据库、配额库与 Chroma 目录及离线配置；没有真实 LLM 调用、真实索引重建或部署。**这是针对性回归，不是全仓测试/浏览器端到端/真实模型质量验收。** 前端 hook 测试使用受控 React/DOM 替身。
- 前端 Vitest 初次在沙箱中因父目录访问受限未能启动；确认原因后使用获准权限运行通过，不将环境启动失败算作业务测试失败。

复现后端（在 `backend`，设置离线模型变量，使用项目 venv）：

```powershell
$env:HF_HUB_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'
$env:LLM_API_KEY='test-key-not-for-real-calls'; $env:LLM_BASE_URL='https://test.invalid/v1'
.\venv\Scripts\python.exe -m pytest tests/test_review_regressions.py tests/test_entity_precision.py tests/test_limitation_calc.py tests/test_phantom_check.py tests/test_numeric_matching_v2.py tests/test_law_snapshot_review.py tests/test_agent_writer.py tests/test_agent_verifier.py tests/test_tool_gateway.py tests/test_agent_chat_integration.py -q --tb=short
```

规则依据沿用已核实官方文本：[诉讼费用交纳办法第13、16条](https://www.court.gov.cn/jianshe/xiangqing/5092.html)、[普通时效衔接司法解释](https://www.court.gov.cn/zixun/xiangqing/108211.html)、[劳动争议调解仲裁法第27条](https://www.beijing.gov.cn/zhengce/zhengcefagui/qtwj/201912/t20191219_1307906.html)。未新增框架、依赖、数据库迁移或模型裁判。

剩余：E1 通用事实一致性能力仍需单独定义验收范围；原安全观察中的评测入参权限与日志隐私策略仍待契约决策，本轮未擅自更改。

## 结论与边界

合并证据链专项审查后，共 10 项：2 项 P1、6 项 P2、2 项 P3。其中 3 项仅在相关开关开启后触发，1 项为测试覆盖缺口，2 项为尚未接入生产链的辅助函数缺陷，1 项为已知但未补齐的关键事实一致性能力缺口。优先修正受理费公式表和关键事实反写仍可交付的问题。没有实施业务修复。

初始范围：`1be944c7299cf8e5b6509865bea0c46e4eaebd76` → `02e3851e0d095dde03bf428b26caaa1ab8d192e9`，53 个变更文件及相关既有调用链。后续证据链专项固定审查 `27d5363ace42d22678293c8878f1d72daa4e2f19`，该提交相对 `02e3851` 仅新增 Gate2 runner 测试及口径文档。因本地历史缺少 `0263bd56fcfc53a13d040e702caf75c74ba0cdb1` 等对象，无法可靠计算 merge-base，采用端点 diff，而非宣称逐提交历史完整。

后端动态验证使用固定提交的 `git archive` 隔离副本，不混入工作区修改。当前工作区的未提交修改（包括 `backend/agent/verifier.py`）不纳入本报告结论。新增产物为本报告、两个隔离副本和审查复现脚本。

P1 = 应优先处理的重要正确性问题；P2 = 常规修复项；P3 = 当前影响有限、在接入生产前处理。以下分别保留两位独立审查者的 Standards / Spec 结果，不合并成单一排名。条目编号中的 `P1/P2` 是原 Spec 编号，方括号内才是严重度。

## 复审记录（同日，HEAD 仍为 02e3851）

- 本轮检查原6项结论、上下游调用及反证，没有重新声称完成53文件的第二次全面审计。涉及的业务文件与固定HEAD相同。
- Standards S1 保留 P2，严格限定为认可案例测试的覆盖缺口。确有其他阻断测试和 E03 认可簇测试，但未补足主体相交、责任方向正确时的正向路径；不意味着所有实体校验测试失效。
- Spec P1 保留 P2；Spec P2 降至 P3。后者是已实现函数对中断参数的处理缺陷，交接书没有明确承诺劳动中断支持，不应描述为已违反明确的生产验收条款。
- B1 保留 P1，B3 保留 P2；两者本轮均补充 writer 行为证据。B2 降至 P3，与 Spec P2 同样没有生产调用者。
- 安全两项继续作为契约/策略观察。交接书明确设计了 HTTP body 注入，所以“HTTP允许传入”本身不证明越权；server-owned 在此首先表达不允许模型改写，不能直接等同仅管理员可设置。
- 纠正初审测试归因：JUnit 中 **12项**直接报缺少 `.env`，另 **1项**是子进程 checkpoint 超时，stderr 被测试丢弃，原始失败无法直接归因。此前“13项均为 `.env`”证据不足。基线 `1be944c` 已有无条件读取 `.env` 的代码，因此12项不是本批新引入的读取行为。

本轮在固定提交隔离副本中，复用 `tests.test_numeric_matching_v2.make_state/render/one_claim`，以假生成器输入明确文本、调用真实 writer/verifier，得到以下新证据（未调用模型）：

| 输入与开关 | writer | verifier |
| --- | --- | --- |
| 2000000元事实，声称费用18800元，numeric v2开 | READY | PASS |
| 同一事实，声称正确费用22800元，numeric v2开 | FAIL_SAFE / UNSUPPORTED_NUMERIC_TOKEN | 未执行 |
| 50000元事实，费用1050元，numeric v2开 | READY | PASS |
| 5万块事实，费用1050元，numeric v2开 | FAIL_SAFE / UNSUPPORTED_NUMERIC_TOKEN | 未执行 |
| 五万元事实，费用1050元，numeric v2开 | FAIL_SAFE / UNSUPPORTED_NUMERIC_TOKEN | 未执行 |
| 合法借款引用附“我无法读取您的历史会话”，phantom关 | READY | 未执行 |
| 相同输入，phantom开 | FAIL_SAFE / PHANTOM_TOOL_CLAIM | 未执行 |

费用证据仅含《诉讼费用交纳办法》第十三条及“财产案件分段累计交纳案件受理费”，不把待验证金额偷放进证据。借款证据仅含《民法典》第六百六十七条及借款合同关系。以上是组件边界复现，不是线上请求或真实生成频率评测。原纯函数反例脚本亦已重新执行，五组输出与初审一致。未重复运行全套 pytest、前端测试或静态检查；下方这些套件数字保留为初审历史证据。

## Standards 轴（1 项，最严重 P2）

### S1 [P2] “零误杀”测试没有实际触发需要验证的判断分支

- 位置：`backend/tests/test_entity_precision.py:154–159,194–198`。
- `_neut_state` 使用“本案双方为合同当事人”和“本案应如何处理”，缺少主体类型和责任方向线索；主体类型、方向判断因信息不足跳过。23 个认可法条测试主要证明缺信息时不拦截，不能证明真实案件中的认可引用不会被误杀。
- `reason_code not in NEW_CODES` 还允许其他失败原因，不能证明正常答案仍可交付。
- 与仓库测试标准中“有效边界测试、独立期望、防假绿”的要求不符。
- 最小修复：保留并重命名这些缺信息放行用例；另补真实主体、方向与有效条文片段的认可案例，对应断言 `READY`。不需要新增测试框架。
- 证据：静态分支审查；此次定向套件中的相关测试通过并不消除该缺口。

## Spec 轴（2 项，最严重 P2）

### P1 [P2] 受控费用计算未兑现口语金额归一契约

- 位置：`backend/agent/fee_calc.py:65–84`；writer/verifier 的费用白名单调用链。
- 执行书 T-A3 要求口语金额可归一。实际 `largest_amount_yuan` 只识别 `N元/N万元`；“5万块”没有匹配，“五万元”虽匹配但交给 `Decimal` 后被忽略。调用方直接传原事实，未执行注释所称的预归一。
- 动态复现：“欠款50000元”产生 `1050/525` 费用 token；“欠款5万块”和“欠款五万元”均产生空集。开启 `numeric_matching_v2` 时，正确的受理费可能被当作无来源数字拒绝。
- 最小修复：复用项目已有金额归一能力，避免另建一套解析器；补口语及中文数字的端到端允许/拒绝用例。

### P2 [P3] 未接入生产的劳动仲裁时效函数忽略中断日期

- 位置：`backend/agent/limitation_calc.py:122–142`；外部 harness 交接书 R11。
- 劳动分支直接返回，没有处理 `interruption_dates`，但民事分支处理了同一个参数。
- 动态复现：起算 `2025-01-01`、有效中断 `2025-10-01`、观察日 `2026-02-01`，当前返回届满日 `2026-01-01` 且已过期；在假定中断事实成立、无其他特别规则的这个算例中，应重新起算至 `2026-10-01`，尚未过期。
- 法律独立依据：[《劳动争议调解仲裁法》第27条](https://www.moe.gov.cn/s78/A15/s8355/moe_782/tnull_39857.html)规定仲裁时效中断后重新计算。
- 最小修复：接入生产前处理有效中断日期并补边界用例；若当前暂不支持，应明确拒绝不支持的参数，不能静默给出已处理的外观。
- 影响限制：`calc_limitation` 目前未作为生产工具接入；生产接入的是年数 token 白名单，不应将这个函数缺陷描述成已确认的线上届满日误答。

## 补充正确性轴（3 项，最严重 P1）

### B1 [P1] 100万元以上财产案件受理费档位缺失，错误结果进入受控白名单

- 位置：`backend/knowledge_base/fee_formulas.json:26`。
- 表中从100万元直接进入无上限 `0.005` 档，遗漏 `0.009/0.008/0.007/0.006` 四档。计算器忠实执行错误表，writer/verifier 又共享这张表，彼此一致不能构成独立验算。
- 动态复现：200万元标的普通程序返回18800元、简易程序9400元；正确分别为22800元、11400元。普通程序少算4000元。官方计算依据为100万元累计13800元，再加100万元×0.9%。[最高人民法院公布的《诉讼费用交纳办法》第13、16条](https://www.court.gov.cn/jianshe/xiangqing/5092.html)。
- 当前锚点仅到100万元，遗漏档位不被现有锚点测试发现。开启 `numeric_matching_v2` 后错误金额被作为受控来源接受，正确金额则可能被拒绝。
- 最小修复：补齐官方档位；用独立于公式表生成的期望值测试每个新增档位及边界两侧。无需改计算框架。

### B2 [P3] 未接入生产的民事时效函数遗漏民法总则时期

- 位置：`backend/agent/limitation_calc.py:144–151`。
- `fact_date < 2021-01-01` 一律取二年，遗漏2017年民法总则施行后的三年规则。`needs_case_review=True` 是风险提示，但不能使错误的参考数值变正确。
- 动态复现：普通民事起算2019年1月1日、观察日2021年7月1日，当前输出2021年1月1日届满且已过期；在无特殊规则、中止中断等情形的算例中，应为2022年1月1日届满且未过期。
- 独立依据：[最高人民法院关于民法总则诉讼时效司法解释的说明](https://www.court.gov.cn/zixun/xiangqing/108211.html)，明确总则施行后开始计算的普通时效适用三年。
- 最小修复：正确区分民法总则时期；对确实需要衔接判断且信息不足的场景返回不确定结果，不要伪造确定的二年届满日。
- 影响限制与 Spec P2 相同：纯计算函数反例，未证明当前线上答案已使用该届满日；2021年前年数白名单本身保守返回空集，不是本项指责对象。

### B3 [P2] 伪调用检测将否定历史访问的安全声明当成已执行动作

- 位置：`backend/agent/phantom_check.py:72`。
- memory 类模式包含裸 `历史会话`，没有判断是否实际断言读取过；`phantom_action_categories` 对任意匹配都要求真实执行记录。
- 动态复现：“我无法读取您的历史会话。”、无工具记录，返回 `['memory']`，期望为空。这是能力边界声明而非伪调用。
- 开启 `phantom_tool_check` 时，writer/verifier 可拒绝这种合规声明，造成争点缺失或失败；开关默认关闭，不声称默认线上路径必然受影响。
- 最小修复：要求肯定的已执行动作语义；补否定、能力限制和真正断言读取的对照用例。简单局部规则即可，不需引入模型判别器。

## 证据与引用链专项（固定提交 27d5363）

### E1 [P1] 与已绑定事实相反的结论仍获 `supported=True`，并通过最终输出闸门

- 位置：`backend/agent/verifier.py:362,491`；最终路径为 `main.finalize_verified_agent_answer`。
- 最小反例：已确认事实为“借款尚未清偿”，claim 用正确 `fact_id` 绑定该事实和有效法条，却写“该借款已经全部清偿”。实际 writer 为 `READY`，verifier 为 `PASS`，claim 标记 `supported=True`，finalizer 返回 `READY`；最终文本在同一页同时出现相互矛盾的两句话。
- 原因：现有检查验证绑定、数字、引文存在性、覆盖和措辞，未验证关键事实命题的正反方向。`supported=is_pass` 使结构检查通过看起来像每项结论均获事实支持。
- Agent V1 设计要求事实编造检查，并明确引用存在性不能替代 Claim-Evidence 语义核验；后续计划也将“证据绑定但语义不支持”列为独立未完成任务。因此这是已知能力缺口，不表述为新引入回归。
- 最小方向：先为清偿/未清偿等可确定反例建立关键事实一致性验收，再加有界矛盾检查；不能用生成模型自评代替独立证据。

### E2 [P2] 精确查条工具未归一条号，已有条文可能被报为未找到

- 位置：`backend/tools/exact_article.py:19`、`backend/retrieval.py:350`。
- `LookupArticleInput` 直接把条号传给等值查库。库中“第五百七十七条”与输入“第577条”不相等，返回空；普通检索和 `/api/law` 已使用现有 `_normalize_article`，因此是工具路径漏接。
- 在单条内存 collection 中，固定来源和基准日下，“第577条”结果为空，“第五百七十七条”返回同一条文快照。
- 最小修复：在共享 `exact_article_lookup` 边界复用 `_normalize_article`，补中文、阿拉伯、全角及“之”条号等价命中用例。

### E3 [P2] 引用原文卡未绑定答复所采用的法律版本

- 位置：`frontend/lib/hooks/useLawCards.ts:27–32`、`backend/main.py:1309`、`backend/retrieval.py:347`。
- Agent 工具按 run 的 `law_as_of` 取证；原文卡仅以书名和条号请求，后端无 cutoff 时默认今天，前端缓存键也不含 run、证据或版本。
- 合成版本夹具中，同条文按 `2023-01-01` 返回旧快照，省略 cutoff 返回新快照。真实检索函数执行了日期过滤；夹具日期不代表任何真实法条的修订史。
- 影响：历史答复点击原文可能展示今天版本，或在当前无有效版本时显示404，用户会把替换后的文本误认为答复依据。
- 最小方向：聊天引用优先读取消息所属 run 的绑定证据快照；若提供完整条文查询，缓存键应包含证据或版本身份，并标注基准日。

### E4 [P2] verifier 接受的 snippet 引文会在“法律依据”区遗漏

- 位置：`backend/agent/verifier.py:192–198,400`。
- 校验引用时使用绑定证据的 `source_ref + snippet`，渲染法律依据时仅从 `source_ref` 提取，两个允许集合不同。
- 反例：`source_ref` 为“民法典#第五百七十七条”，snippet 提及《民法典》第五百八十四条；claim 仅引用584并绑定该证据。writer `READY`、verifier `PASS`、finalizer `READY`，但“法律依据”显示“（无）”。
- 主线交接书要求从绑定证据的 `source_ref` 和必要 snippet 提取引用。最小修复是让展示与校验共享引用集合，并为实际命中的snippet条文生成正确标签。

## 法律版本与时效适用链专项（固定快照 `03ced940`，2026-09-20）

本节只审 `law_as_of → 检索/证据 → writer/verifier → 缓冲与流式出口`，未修改业务代码。需求依据为 `docs/process-archive/superpowers/plans/2026-09-18-r15-law-version-tripwire.md`、`docs/process-archive/handoff-r15-and-git-repair-20260919.md` 与 `evals/watershed-cases-r15.json`。两条独立审查轴均确认：当前 R15 判据能拦一部分错答，但把“知识快照日”“事实日期”“时效起算/适用法日期”混成了一个跨分水岭布尔值。

### R15-1 [P1] 正确旧法引用或明确的新旧法衔接说明仍被判为版本冲突

- 位置：`backend/agent/limitation_calc.py:225–255`；消费点 `backend/agent/verifier.py:438–444`、`backend/main.py:1201–1237`。
- 判据只检查 claim 是否含“时效”关键词，以及最早事实日与 `law_as_of` 是否分处 2021-01-01 两侧；完全不检查 claim 实际引用《民法总则》还是《民法典》，也不识别“适用旧法/需作衔接判断”等限定语。
- 系统 Python 动态复现（快照 `03ced940`）：事实为“2019年3月5日借款到期”、`law_as_of=2026-09-20` 时，以下三句均返回 `True`：正确引用《民法总则》第188条三年时效；明确说明“不直接适用《民法典》”；仅提示“需结合新旧法衔接规则判断”。开关开启后，Agent 路径会 `FAIL_SAFE`，快车道会追加版本注记并禁止正常缓存。
- 需求样本只把“对2019年事实直接按《民法典》第188条作答且不作衔接说明”列为 critical failure；当前实现扩大成“任何跨日期的时效陈述都冲突”。现有 `backend/tests/test_r15_version_tripwire.py:32–33` 反而把同形状行为锁为正确结果，测试期望本身需要修订。
- 最小修复方向：先区分 claim 所引用的法律版本和是否作衔接说明；无法确定适用法时返回“不确定/需核验”，不能仅凭两个日期直接判错。无需引入模型判定器。

### R15-2 [P1] 使用所有事实中的最早日期代理时效起算日，系统性误拦多日期案件

- 位置：`backend/agent/limitation_calc.py:252–255`（`dates[0]`）。
- 动态反例：事实同时包含“当事人1980年1月1日出生”和“2023年8月1日借款到期”，claim 正确陈述《民法典》第188条三年时效，当前返回 `True`。同类问题还包括2019年签约、2023年违约或2022年发生有效中断；最早日期并不是请求权产生、知道受损或重新起算日期。
- 影响覆盖 Agent verifier、缓冲轻量出口和旗舰流式出口。虽然判据集中在一个函数中，错误语义会被三个出口一致放大。
- 最小修复方向：让调用方提供有类型的起算/权利受损事件；缺少该事实时追问或保守标注，不能扫描全部文本后选最早日期。

### R15-3 [P1] `law_as_of` 检索只能提供基准日有效法，跨版本案件没有旧法证据可供生成与核验

- 位置：`backend/tools/legal_retrieval.py:16–26`、`backend/tools/exact_article.py:15–22`、`backend/retrieval.py:345–363,748–788`；快车道残余见 `backend/main.py:1181–1187`。
- Agent 将 `context.law_as_of` 同时作为知识快照 cutoff；当它是2026年时，已于该日前失效的旧法被过滤。于是系统即使识别出2019事实，也无法取到《民法总则》等当时适用版本作为可绑定证据，只能拒答，不能生成或核验正确的衔接结论。
- 快车道更弱：`_fast_path_law_as_of` 的日期只供绊线门消费，检索 cutoff 不随请求中的该值变化，代码注释已把此列为已知残余。
- 最小修复方向：数据模型至少拆分“知识快照日”和“待判断的法律适用区间”，并允许按明确适用区间补取历史版本；保持现有证据来源、效力起止日期和引用校验机制，不另建检索框架。

### R15-4 [P1] 快车道整段答案中的劳动关键词可使民事错误结论绕过版本门

- 位置：`backend/agent/limitation_calc.py:245–247`、`backend/main.py:1201–1222`。
- 判据只要在输入文本任意位置发现“劳动仲裁”等 `_LABOR_KEYWORDS` 就立即返回 `False`。Agent 按单 claim 检查时影响较窄，但快车道把整段答案作为一个 `claim_text` 传入：一段答案只要另有劳动仲裁内容，就会连带跳过其中民事时效结论。
- 动态复现：2019年借款事实下，答案同时包含“民事借款适用《民法典》第188条三年”和“劳动仲裁时效一年”，返回 `False`；删除劳动句后同一民事结论返回 `True`。
- 最小修复方向：在快车道按确定性句段拆分后逐段应用同一判据，或只让劳动排除作用于实际命中的句段；不要增加第二套版本门。

### R15-5 [P2] 常见日期格式不被解析，版本门静默漏判

- 位置：`backend/agent/limitation_calc.py:56–57,69–80`。
- `_DATE_RE` 只接受“2019年3月5日”，ISO `2019-03-05`、斜杠日期和中文数字日期均返回无日期，随后 fail-open。系统 Python 动态复现：把事实日期改成 `2019-03-05` 后，原本应命中的现行法错答返回 `False`。
- 最小修复方向：复用项目已有日期归一/解析能力（若无则只补 ISO 和斜杠两种明确格式），为支持和不支持的输入形状建立契约测试；不需要通用自然语言日期解析器。

### 专项验证限制

- 纯函数反例使用系统 Python 在当前工作树运行，均获得上述实际返回值；没有调用模型、网络或生产数据库。
- 定向 pytest 未执行到收集阶段：`backend/venv/Scripts/python.exe` 的启动器仍指向已不存在的 `C:\Users\33393\AppData\Local\Programs\Python\Python311\python.exe`。按重试纪律在确认同一环境故障后停止，没有把“未运行”写成测试通过。
- 本节不主张覆盖全部新旧法衔接规则，也未验证真实知识库是否已完整收录历史法版本。

## 认证授权与数据隔离专项（固定快照 `f008ed7`，2026-09-22）

权限基线经 Owner 确认：普通用户只能访问自己的会话、运行、消息、上传和产物；`case_domain` 等评测控制量仅可信评测通道可用；`law_as_of` 可作为公开历史查询条件，但必须审计且不得绕过证据有效性。审查覆盖全部 `backend/main.py` 对外端点及其 Conversation/Message/AgentRun/媒体/反馈查询链。本节未修改业务代码。

### AUTH-1 [P1] 普通认证用户可注入评测专用 `case_domain`，改变 Agent 判域与检索路径

- 位置：`backend/schemas.py:65,73–78`、`backend/main.py:1580–1582,1654–1663`、`backend/agent/r1ob.py:28–34`。
- `/api/chat` 只要求普通登录；`ChatIn` 对 `case_domain` 仅做枚举校验，随后 Agent 分支将 `body.case_domain` 原样传入 bootstrap。R1-OB 又把该值作为最高优先级判域输入。因此开启 Agent/R1-OB 后，任意普通用户都可指定 `civil/criminal/labor/...`，改变过滤后的证据池与回答路径。
- `backend/settings.py:44–48` 已把 `case_domain` 定义为评测/灰度输入，但固定快照只有 `allow_client_law_as_of`，没有对应的 case-domain 权限闸。`agent_enabled=False` 只降低当前可达性，不能保证功能开启后的权限契约。
- 最小修复：沿用现有 `_client_law_as_of` 模式，在唯一 bootstrap 调用边界过滤 `case_domain`，默认返回 `None`；评测启用不能只靠前端不传。无需新增权限框架。

### AUTH-2 [P2] `law_as_of` 的实现契约与已确认的公开历史查询契约不一致，且放行时无审计

- 位置：`backend/main.py:1209–1219,1580–1663`、`backend/settings.py:44–48`。
- 当前 `allow_client_law_as_of=False` 会静默忽略所有普通用户传入值；设为 `True` 后又对所有已登录用户统一放行，没有记录谁在何时选择了哪个历史基准日。它是全局功能开关，不是调用者权限或审计边界。
- 按本轮确认契约，普通用户可以使用历史查询条件，因此问题不在“必须改成管理员专用”，而在缺少可见的产品行为和最小审计：请求被忽略时用户不知情，放行时也无法追溯。未发现它能绕过现有 `law_as_of` cutoff；不把本项描述成跨用户越权。
- 最小修复：保留同一个入参和 cutoff 链，明确选择公开或禁用；若公开，在已有结构化记账中记录 `user_id`、`conversation_id`、`law_as_of`，不记录问题原文。无需单独建设审计系统。

### AUTH-3 [P2] Agent 域过滤日志写入原始争点文本，可能持久化姓名、证件号和案情

- 位置：`backend/tools/legal_retrieval.py:36–50`、`backend/observability.py:90–99`。
- 域过滤移除文档时，代码把未经脱敏的 `tool_input.query` 作为 `query` 字段写入 `legal.agent`。该 query 来自用户问题和争点，可能包含个人信息；与仅记录长度、哈希或计数的访问记账不同。
- 风险受 `agent_dept_filter`、Agent 流量和实际日志部署方式限制；当前项目注释将部署定位为本地单租户，因此列 P2，不升级为已证实的数据外泄。它仍违反本轮“检查日志中的案情与个人信息”的最小化原则。
- 最小修复：沿用项目已有哈希习惯，只记录 query hash/长度、domain 和 removed 数；诊断无需保留原文。

### 权限矩阵复核结果与限制

- 未发现可复现越权：会话 CRUD 和消息读取先校验 `Conversation.user_id`；Agent resume 同时绑定 run/user/conversation；媒体读取同时做路径约束与消息归属校验；反馈携带 conversation 时校验 owner；所有管理员数据出口均使用 `require_admin`。
- 固定快照已有 foreign conversation/run 测试；媒体、反馈及 `case_domain` 缺少端点级跨用户反例，属于测试覆盖缺口，不单独计为漏洞。
- 本地动态端点测试未能启动：`backend/venv/Scripts/python.exe` 仍指向已不存在的 Python 3.11，系统 Python 又缺 FastAPI/SQLAlchemy。根据已确认完成标准，本节以端点到查询条件的静态证据收口，不声称动态测试通过。
- 工作树中的 `backend/tests/test_client_case_domain_gate.py` 为未跟踪文件，不属于固定快照；它描述了拟议闸门，但当前 `backend/main.py`/`backend/settings.py` 尚无对应实现，不能作为已修复证据。

### 2026-09-23 当前快照复核（HEAD `b7d96f5`）

以下结果更新并取代上面仅针对固定快照 `f008ed7` 的实现状态和环境限制；原始发现保留作审查历史，不代表当前仍全部成立。

- **AUTH-1 已修复。** `817e7d3` 增加默认关闭的 `allow_client_case_domain` 和 `_client_case_domain()`，Agent bootstrap 边界只接收经闸门过滤的值；当前源码及 `test_client_case_domain_gate.py` 均已纳入当前快照。原发现仍说明基线当时的风险，不再列为当前未修复问题。
- 在按当前工作树构建的独立 Docker 审查镜像中，临时容器运行定向套件：`test_client_case_domain_gate.py`、`test_client_law_as_of_gate.py`、`test_agent_repository.py`、`test_agent_resume.py`、`test_phase3.py`，结果 **47 passed / 17 warnings**（20.94秒，exit 0）。测试依赖仅装在一次性容器层；容器未挂载服务数据卷，没有改动运行中的服务或生产数据。警告未导致测试失败。
- 一次性容器中的双用户端点探针得到：会话所有者 `200`、其他用户 `404`；媒体所有者 `200`、其他用户 `404`；对他人会话提交反馈 `404`。这是本次实际执行的动态端点范围，不应外推为所有公开端点均已动态覆盖。
- **AUTH-2 本地已实现、测试通过，2026-09-24 已提交为 `065038c`（父 `b7d96f5`），尚未部署。** 按已确认的公开历史查询契约收口：`allow_client_law_as_of` 默认改为 `True`（`settings.py`）；部署侧显式关闭时，携带日期的请求返回 **HTTP 503 + 可理解提示**而非静默改用当日（`main._client_law_as_of` 是唯一闸口）；`_bootstrap_only` 为每次显式历史查询记 `historical_law_query`，字段仅 `user_id`/`conv_id`/`law_as_of`，问题原文不进日志（`test_agent_gate.py` 逐字段钉死该形状）。
  - **勘误（本轮自查）**：本节先前写"由 `test_client_law_as_of_gate.py` 的 AST 哨兵防新增旁路"**不实** —— 该文件没有 `import ast`、没有任何扫源守卫（当时的 13 处 "ast" 命中全是 `fastapi`/`_fast_path_` 的子串）。真机制是 `test_client_case_domain_gate.py` 里用正则扫 `main.py` 源码、断言 `body.case_domain` 只出现在闸函数体内；它**只护 `case_domain`**。本轮已把同款守卫补到 `body.law_as_of`（`test_no_ungated_client_read_of_law_as_of_in_main`），并验证其可失败性：临时注入一处闸外直读 ⇒ 该用例变红、且不影响 `case_domain` 那条。此处现在尤其重要——闸口同时是 503 的唯一发出处，闸外直读等于让已关闭历史查询的实例重新变成静默改用当日。
  - 取数口径本轮补齐：考试分步检索 `retrieve_exam`、场景补充 `scenario_supplement_docs`、静态条文集 `cheating_docs`/`consumer_*_docs`、合同链 `build_contract_data`→`contract_supplement_docs` 全部按基准日取数；合同 `blocks[*]["articles"]` 与 `docs` 同源构建（事后重过滤改不到 `blocks`，而 `_contract_messages` 读的正是 `blocks`）。
    - **勘误（第三轮独立评审发现，先前陈述以偏概全）**：本节与提交信息先前写"此前只有 `retrieve` 一条通道带 cutoff，其余分支按当日捞、**末尾再过滤** ⇒ 表现为静默丢证据而非答错版" —— 那描述的是**上一代会话未提交的中间态**，不是父提交 `b7d96f5`。实测父提交：`retrieve` 虽有 `cutoff` 形参（`retrieval.py:965`），但 `prepare_fast_path` 的调用点是 `deps.retrieve(rewritten, k=10)`（`request_bootstrap.py:462`）**根本不传**；`main.py` 里 `is_valid_by_time` 出现 **0 次**（没有"末尾过滤"这回事）；`retrieve_exam`/`scenario_supplement_docs`/`cheating_docs`/`consumer_*_docs`/`build_contract_data` 连 `cutoff` 形参都没有。**所以已提交的基线比这句话更糟**：历史查询在快车道拿到的是**纯现行法证据集且无任何日期过滤**（只有 QA 直返靠 `law_as_of_basis` 挡了一类跨分水岭情形），即 AUTH-2 原始报告的"答错版"风险在 `b7d96f5` 上并未被部分缓解。本 commit 修的是这个状态。`提交信息`无法改写（`065038c` 已被引用），故以本节为准。
  - **第二轮自查补漏（评审发现，先前漏网）**：Agent 工具链的合同口 `tools/contract.py` 仍按当日取数（`_build_contract_data(text)` 丢掉 `context.law_as_of`，而同函数只把它用于 `map_document` 的 validity 标注）⇒ 历史 run 调 `analyze_contract` 时条号仍按现行法构建、历史有效条文从未进候选，与快车道缺口1 同一失效模式；同包 `tools/exact_article.py` 早已是正确写法。已补 `cutoff=context.law_as_of.isoformat()` 并加两腿测试（工具→适配器、适配器→`domain_rules`），改前红、改后绿。
  - 其余出口按 fail-closed 收口：历史请求不进共享答案缓存与近重复缓存（`_cacheable`）、不直返 QA 语料（`prepare_fast_path` 置 `qa_hit=None`）、**不进受控沉淀待审**（`_post` 闸；`qa_pairs` 无版本轴，采纳后会把旧版答案下发给现行查询）；普通问答与合同两条 messages 组装路径共用同一句基准日标注（`_law_version_scope_note`）。
    - **⚠️ 沉淀闸只闭了一条入口（第三轮评审发现，先前"不进受控沉淀待审"的说法过宽）**：`/api/feedback` 走的是另一个入口 `ks.create_candidate(db, body.question, propose, 0.0, "feedback:<rating>")`（`main.py:2863`），**没有任何日期闸**；人工采纳时 `add_qa_pair`（`knowledge_service.py:268`）不写 `law_as_of_basis`，而 `_qa_direct_return` 对**无 basis 的记录明写"不拦"**（`main.py:1180,1187`，那是票 I 有意为之以不扩大拦截面）。⇒ 同一条"旧版答案被采纳后下发给现行查询"的理由对这条口同样成立，口子**没闭**。
    - 本轮**未修**的原因（不是没想到，是缺服务端真源）：`FeedbackIn` 没有基准日字段，`Message` 模型也**没有**任何基准日列 ⇒ 服务端无法判断"这条被点踩/纠错的答案是在历史基准日下生成的"，只能信客户端自报。三个候选处置：① 给 `messages` 加一个可空 `law_as_of` 列并在落答案时写入、反馈时读它（**真修，但属 schema 改动**）；② 让 `feedback:` 来源的候选不得成为可直返语料（改变既有沉淀产品语义）；③ 接受并如实标注。**建议 ①，且另开票**——它越出本票"不改数据模型"的授权（同 `取舍声明①` 里"要彻底消除需给 run 加显式选择标记"是同一类 schema 决定）。给 `add_qa_pair` 补 `basis=采纳日` 被**否决**：那会把答案的实际基准标错，方向恰好是最需要防的那一侧（旧版答案→现行查询）不受保护。
  - Agent 恢复分支：基准日随 run 建立即固定，恢复请求带来不同日期时在 **CAS 之前** 409 拒绝（`ResumeLawAsOfConflict`）；技术性失败降级到快车道时沿用 `run.law_as_of`。
    - **第三轮评审补修（先前这句只做到了 bootstrap，出口各算各的）**：`_resume_bootstrap` 之后，四个出口仍写 `_fast_path_law_as_of(body)` 重算 —— QA 直返（`main.py:1880`）、轻量缓冲（`2093`）、流式版本绊线两条答案来源（`2231`/`2241`）。**降级路径上**日期在 run 上、body 里没有 ⇒ 重算得**今日**，而 `pre["law_as_of"]` 是 run 的历史日 ⇒ 版本绊线拿现行法去判历史证据、日志里的 `law_as_of` 也记错。（QA 直返那一处在该路径上因 `qa_hit=None` 提前返回，属同形不同害；另两处受 `feature_router`/版本绊线开关保护，两开关默认 False ⇒ **潜伏缺陷，非现网错答**。）已加 `main._exit_law_as_of(pre, body)`：`pre` 里那次取数用的日期优先，缺省才回落到 body 口径 ⇒ 未指定历史的默认路径逐字不变（`pre["law_as_of"]` 仅在显式日期生效时设置）。红→绿：新增 2 用例改前红在 `AttributeError: module 'main' has no attribute '_exit_law_as_of'`；两次变异各自只打死对应那条断言（把某出口退回 `body` 重算 ⇒ 只有扫源守卫红；把 `_exit_law_as_of` 改成只信 body ⇒ 只有行为用例红），`main.py` 还原后 md5 逐字节一致。
    - **同轮自查纠正**：先前那条"端到端接线用例"的判据只断言到**被捕获的 bootstrap**（`test_agent_resume.py:146,192`），看不到出口实参 ⇒ 它证明不了"出口沿用了 run 日期"，是**接线断言没钉被比对象**的复发。现在的牙齿来自两处：`_exit_law_as_of` 的行为用例 + `_fast_path_law_as_of(body)` 只准出现在该函数内的扫源守卫。
    - 取舍声明①（有损代理）：`AgentRun.law_as_of` 非空且分不清"用户选了今天"与"用户没选"，因此 `_resume_law_as_of` 把**当日折成"未指定"**。唯一偏差：首请求显式传今天会退出直返/缓存/沉淀，恢复分支降级回来时不会。取它是不动生产默认路径；要彻底消除需给 run 加"日期是否被显式选择"标记（schema 改动，不在本轮授权）。
    - 取舍声明②（审计半边）：恢复分支不走 `_bootstrap_only`，故 resume **不再产生** `historical_law_query` 记录——设计意图是"一次日期选择记一次"（记在 run 建立那次）。本轮只保证日期一致性与不静默丢弃，未新增恢复点审计。
  - 接缝防回退（本轮补）：`FastPathDependencies` 的取数口类型从 `Callable[…]` 收紧为 **cutoff 必传关键字的 `Protocol`**。实测牙齿：故意把 `deps.cheating_docs(cutoff=cutoff)` 写成 `deps.cheating_docs()` ⇒ mypy 报 `Missing named argument "cutoff"`；此前我用放宽类型换取 mypy 通过，等于在本次要护的接缝上取消了类型检查。
  - **需 Owner 复评的代价（未自行处理）**：09-21 裁定注释里"分水岭前的值会触发护栏回落 LLM ⇒ 不限通道就是公开用户的成本口子"这条事实**依然成立**，且现由 `qa_hit=None`/`_cacheable` 排除实现为结构保证。公开化把调用者从评测通道换成任意已认证用户 ⇒ 客户端可用一个日期把缓存命中打成未命中（有界：单请求、60/分钟、最贵等于一次未命中）。`settings.py` 已把该耦合写进注释，成本口径是否要加限额需 Owner 定。
  - 检索结果缓存键本身含 `cutoff`（`retrieval.py:823`），不存在跨日期串用。
  - **未闭出口（第三轮评审查出，本轮只标注不擅自改）**：条文回查端点 `/api/law`（`main.py:1563`）与 `/api/law/search`（`1588`）**恒按当日**取条文 ⇒ 历史查询里引用的条号在这两个入口 404。快车道没有 run 可挂日期，而 **Agent 路径已有**按快照回查的分支（`main.py:1529-1562`）⇒ 两条出口的契约不对等。不属"生成/缓存出口"故先前的陈述没覆盖它，但它确实落在交接票第 4 项"所有出口"的射程内，故记录为**已知未收口项**；补它要给这两个 GET 端点加可选 `law_as_of` 参数并复用同一个 503 闸口（新公开 API 面，需 Owner 认可口径）。
- **AUTH-3 本地已实现、测试通过，2026-09-24 已随 `065038c` 提交，尚未部署。** `dept_filter_removed` 不再写原始 `tool_input.query`，改记 `query_sha256` + `query_len` + 域与剔除数；结构化字段白名单同步（移除 `query`，加入两个新字段）。
  - **两层防护的归因被本轮实测分开**：把 `extra["query"]` 原样写回代码后，只有白名单哨兵 `test_log_field_whitelist` 变红，而 `test_filter_log_omits_raw_case_text` 里"`payload` 不含原文"那条**仍绿** —— 因为 `_JsonFormatter` 会把未登记字段整批丢掉，序列化结果自然没有它。也就是说该断言原先证明的是"formatter 挡住了"，证明不了"代码没写"。已补一条钉在 `LogRecord` 上的 `assert not hasattr(record, "query")`，并双向验证：干净代码 13 passed、写回原文即红。两层现在各有可归因的用例。
  - 残留（判定记录）：未加密钥的 SHA-256 **只解决"日志静止态含个人信息"，不等于匿名化**。它确定可关联——同一问句在多条日志间可被比对；且对**短/低熵**问句，持日志者可用候选句集合正算哈希做成员判定。当前判定为可接受：该字段用途就是同库内分组排障，且相对原文（完全可关联）严格更小暴露。**升级触发条件**：日志读者扩到运维以外的人群，或需要防成员判定 ⇒ 换成服务端密钥的 HMAC（`legal_retrieval` 需引入 settings 耦合，故不在本轮擅自做）。
- 本轮验证证据（隔离容器 `codex-auth-review-test`，镜像 `ai-legal-helper-backend:audit-current`，无挂载卷、无端口映射，非运行中的服务）：
  - **同步前置**：容器无 bind mount，故逐个比对宿主/容器 md5（22 个改动+新增文件，路径映射为宿主 `backend/X` → 容器 `/app/X`），全部一致后才引用下面的数字。
  - 开工前基线（补齐上一轮被中断的宽套件）：**81 passed / 2 skipped**，exit 0（33.78 秒）。
  - **2026-09-24 重跑（提交 `065038c` 那一批字节）**——定向 AUTH 套件（宽套件 7 文件 + `test_historical_law_cutoff_threading.py` + `test_agent_resume.py` + `test_light_exit_gates.py` + `test_pre_rewrite_order.py` + `test_scenario_supplement.py` + `test_domain_rules.py` + `test_tool_gateway.py` + `test_agent_gate.py` 共 15 文件）：**235 passed / 10 skipped / 59 warnings，47.06 秒，exit 0**；全量：**1407 passed / 12 failed / 25 skipped，113.87 秒，exit 1**。
  - **2026-09-24 第三轮修复后重跑（当前字节，含 `_exit_law_as_of`）**：定向 **237 passed / 10 skipped / 59 warnings，45.78 秒，exit 0**；全量（同上口径：排除 `test_gate2_runner`/`test_gate5_judge_layers`/`test_harness_fact_reveal`/`test_r15_runner_injection` 这 4 个收集期即因镜像缺件报错的评测 runner）**1409 passed / 12 failed / 25 skipped，86.54 秒，exit 1**。两次 12 项失败与下面缺件清单**逐项同名**，无新增、无消失。
  - 退出码取法：`pytest > file 2>&1; echo $?` 后再看文件尾部。**管道接 `tail` 会拿到 `tail` 的退出码**（本轮一次误跑就是这样报出假 `exit 0`），已重跑纠正。
  - **交付物自身的自检另见 [`progress-auth-review-20260924.md`](./progress-auth-review-20260924.md) 第 9 节**：代码过了第三方评审，不等于文档能外发。那一节记了五类（6 处从评审 brief 沿用未复测的 `file:line` 最多差 38 行、一条指向不存在小节的引用、两笔算不上的文件/提交数、两处"只读对照表会接错结论"的未回改正文、一笔被 shell 反引号截断的提交信息），并已把代码指针整体换成符号锚点。
  - 静态检查（宿主 `backend/venv`）：`ruff check .` 全通过；`mypy .` **Success: no issues found in 73 source files**；`git diff --check` 无空白错误。
  - `ruff format --check` 的处置：本改动集内 3 个文件（`tools/legal_retrieval.py`/`observability.py`/`schemas.py`）原先被判"需重排"，实测原因是**工作树行尾混排**（`core.autocrlf=true` 且无 `.gitattributes`，编辑工具以 LF 追加补丁 ⇒ 主体 CRLF + 补丁行 LF）。仅统一行尾后三个文件即 `already formatted`，且 `git hash-object --path --filters -w` 前后 blob 哈希**逐字节相同**（`29b2997…`/`4030f7b…`/`edc69a9…`），即零内容差异、不产生整文件噪声。仓库内另有 6 个**本改动集未触及**的文件仍被判需重排（`agent/phantom_check.py`/`verifier.py`/`writer.py`、`tests/test_entity_precision.py`/`test_law_snapshot_review.py`/`test_review_regressions.py`），属同一行尾成因的既有状态，按"不批量清理他人改动"保留并如实标注。
- **上述 12 项失败未修，归因为容器缺件与路径布局**（非本轮改动引入）：`test_chunking.py` 7 项为 `data/sample_laws/sample_law.txt` 缺失（该目录在宿主仓库里同样不存在）；`test_eval_agent.py` 2 项、`test_init_release_evidence.py` 1 项、`test_gate_exit_registry.py` 1 项为 `/release-evidence`、`/docs/gate-exit-registry.md` 未进镜像；`test_chroma_isolation.py` 1 项断言临时库不在仓库根下，容器内根路径布局与宿主不同。归因依据是失败信息本身（缺件/路径），本轮**未**做"同批用例在改动前代码上同样失败"的对照跑（新开容器被授权边界挡住）。
- 判据强度说明（防"为错的原因绿"）：本轮每个修正先有红测。`test_historical_law_cutoff_threading.py` 实现前 **7 failed / 1 passed**（唯一通过的是"不传 cutoff 保持旧形状"对照组），实现后 8 passed；`test_agent_resume.py` 新增 5 项实现前 4 failed；沉淀闸新用例实现前红在 `created` 多出一条（确实漏沉淀）。另用 `git show HEAD` 与"开工前"两份 `request_bootstrap` 副本做过旧实现对照跑：考试/学习/作弊/合同/消费者五条取数口在旧实现下 `cutoff=None` 且**证据为空**，当前实现下五条口全部带基准日且证据为历史版本。
- 本轮顺带修掉两处与 AUTH 无关但被改动暴露的测试隔离问题：`tests/_sse_harness.py` 的合同替身签名补 `cutoff`；`test_agent_gate.py::test_logging_failure_is_counted_and_fails_open` 由 `caplog` 改为直挂 handler（`setup_logging` 把 `legal.chat` 的 `propagate` 关成 False，凡先跑过完整请求链路的用例都会让 caplog 收不到 ⇒ 该用例此前只在特定执行顺序下绿）。
- **动态覆盖尚未完全达到此前确认的全矩阵阈值。** 本次没有对 AgentRun/消息/上传/导出下载和评测参数逐个完成双用户端点探针；定向测试覆盖了 AgentRun 仓储/恢复及两类入参闸门。代码中聊天上传是即时提取流程，未发现可供跨用户读取的持久化上传对象；这说明该数据类型的复现条件有限，不等于已覆盖其他导出或产物接口。会话、媒体、反馈的动态结果及其他端点的静态/测试证据应分别理解。
- 原“venv 指向不存在 Python 3.11 / 系统 Python 缺依赖”的限制只适用于旧快照的本地启动方式；本次通过隔离 Docker 容器已完成上述定向测试，不再作为当前限制。专项范围仍不等同于全面渗透测试，也未审生产环境日志访问和保留配置。

## 安全审查观察（未计入上述已确认问题）

- 基线 `f008ed7` 上 `/api/chat` 曾允许普通认证请求直接控制 `case_domain`；此项已由 AUTH-1 当前修复关闭。AUTH-2 的 `law_as_of` 静默忽略与审计缺口已按"公开历史查询 + 关闭时 503 + 最小审计"在本地代码收口（见上一节，尚未部署）。未证明跨用户越权、执行任意代码或数据泄漏，不将此升级为已确认高危漏洞。
- `agent_claim_checks` 新日志字段记录草稿前120字符。草稿可能复述姓名、案情等用户信息，“非用户输入原文”不等于脱敏。需要确认现有日志访问权限、脱敏和保留策略；未读取真实密钥或导出用户数据。
- 本次没有完成联网依赖漏洞库扫描、渗透测试或生产配置核验，因此不作“无漏洞”的结论。

## 初审验证证据与限制（本轮未重跑的套件）

0. 证据链专项在固定 `27d5363` 隔离副本运行 `test_agent_writer.py`、`test_agent_verifier.py`、`test_tool_gateway.py`、`test_agent_chat_integration.py`：**190 passed / 5 warnings**，54.80秒，exit 0。警告为依赖弃用及 `.pytest_cache` 写入受限。E1–E4 的独立反例仍能触发，说明该套件未覆盖这些行为；未将其解释为全链路或浏览器验收通过。
1. 后端隔离副本定向测试：13个测试文件，`-q -m 'not slow'`。结果 **348 passed / 13 failed / 4 warnings**，耗时59.24秒。复审逐项核对JUnit：12项直接报 `test_gate2_runner.py` 读取缺失的 `backend/.env`；另1项 `test_mid_run_process_kill_recovers_from_checkpoint` 为 checkpoint 超时，因丢弃子进程stderr而不能确定原始原因。不能把13项全部归为环境问题，也不能声称全绿。先前 collection 缺冻结评测数据，补齐提交内 fixture 后运行到此；未再自动循环重跑。
2. 后端隔离副本 `python -m ruff check . --no-cache`：exit 0，`All checks passed!`。
3. 前端工作区 `node node_modules/typescript/bin/tsc --noEmit`：exit 0；前端没有本次未提交源码变更。
4. 前端 `node node_modules/vitest/vitest.mjs run`：4文件、45测试通过。现有测试集中于 SSE/scope/coverage/annotate，不能据此声称后台页面行为已通过浏览器验收。
5. 独立审查脚本：`dispatch-output/review-02e3851-20260918/reproduce_review_findings.py`。在项目 venv 中执行，exit 0，打印实际结果及独立期望；这是诊断程序正常完成，不代表各反例满足正确行为。复现结果对应 Spec 两项及补充三项。
6. Pytest JUnit 产物：`dispatch-output/review-02e3851-20260918/focused-junit.xml`。固定源码：同目录 `committed/`。未调用真实模型、未部署、未修改生产数据库、未修复业务源码。
7. 当前 Python 安装可正常运行；沙箱内调用受限，经授权的隔离检查可运行。不能沿用此前“Python安装损坏”的结论。

## 最小后续顺序

先补受理费档位与独立锚点，以及 E1 的关键事实一致性验收；随后处理 E2、E4 两处局部口径不一致和金额归一、伪调用否定误报。E3 应单独处理消息证据版本关联；时效计算函数在正式接工具前处理其规则缺口。同步补真实认可案例测试。无需重构 Agent 架构或增加新框架。有关评测入参的权限定位和日志隐私策略，先明确现有契约再决定是否改动。
