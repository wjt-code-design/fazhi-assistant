# 10月4日本地候选修订与补验续办

## 当前结论

10月5日续办状态：用户随后批准受限公开副本本机实验，实际管理端33项、BGE CPU八样本、正文法条原文配对已补验；冻结前端没有用户主动取消入口，“取消后重问”仍未通过。详细结果和保留限制见[公开副本补验收尾报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261005-public-local-acceptance.md)。下文记录10月4日取得实验许可前的修订工作，不能把其中“下一步待许可”当成当前状态。

**已将日期修复整合进独立后端副本，并完成本轮红绿测试、静态检查和公开语料缺项核对。T6仍部分完成，尚未合入主仓、提交或发布。**

本轮依据用户“你来执行”及[上一轮验收报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261004-next-local-acceptance-review.md)第4节推进。未把普通继续指令解释为真实语料、模型运行或风险签署许可。

- 新修订根：`C:/Users/33393/Desktop/fazhi-next-local-repair-20261004-a6b8b40ac2f74c94b331eeda8a30072c`，下称REPAIR。
- 被审原候选RUN：`C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499`。
- REPAIR仅有后端源码副本，不是整树复制／全项目发布包。原2658清单中287个backend文件逐hash匹配RUN后复制；排除清单外的DB、配置、运行产物、模型和venv。不吸收主仓5份未交付前端改动。
- 复用RUN联合venv的解释器作只读检查，没有下载、安装或修改依赖。精确约束166条，SHA-256 `f857df91bd33e90398ceb81d2f661c158504082565c94f9519a355631dc20b2e`；requirements与RUN一致。
- 主仓HEAD仍 `902e2d161e67100ed6d267a08c393538a0abe109`，暂存区空；原6份tracked脏文件内容未变。前后保护核对均通过，证据为REPAIR `evidence/protection-before.json`／`protection-after.json`。这证明检查时指纹一致，不追溯证明所有历史时刻均未写过。

## 1. 日期修复：已在修订副本整合

业务改动只有 `source/backend/schemas.py` 的5行，使用已有标准库 `date.fromisoformat`。保留四字段的字符串接口、一般知识的空日期语义、填写条号必须有生效日、版本区间顺序与既有错误契约；无新依赖、框架、helper或邻近重构。

新增 `source/backend/tests/test_knowledge_calendar_dates.py` 72项，另运行原样的 `tests/test_law_versions.py` 28项。新增测试与上轮REVIEW相同；**本次在实际整合副本重新看红再修，不复用上轮结果冒充本轮执行**。

| 检查 | 本次结果 | 证据，均在REPAIR/evidence |
| --- | --- | --- |
| 同套100项，修复前 | 36 failed／64 passed，rc=1；非法日期未抛校验错／HTTP未拒绝 | calendar-red.log、calendar-red.json |
| 同套100项，修复后 | 100 passed／1 warning，rc=0 | calendar-green.log、calendar-green.json |
| 后端Ruff check | 通过，rc=0 | ruff-check.log、ruff-check.json |
| 后端format check | 270 files already formatted，rc=0；未执行format改写 | ruff-format.log、ruff-format.json |
| 后端mypy | 74 source files无错误，rc=0 | mypy.log、mypy.json |
| 文件级复核 | 287原文件仅schema变更，新增1个测试；5行增加／0删除，166约束一致 | initial-revision-verification.json |

warning是已装Starlette TestClient的httpx弃用提示；不安装httpx2“消警告”。mypy沿用原配置（包括不检查无类型函数体及既有exclude），不以其通过声称所有代码都有类型保障。

范围限制：本轮pytest使用 `--noconftest`，不导入main、启动应用、运行BGE或打开Chroma客户端。13项HTTP测试绑定最小FastAPI路由，**不是实际管理端鉴权／持久写入验收**；100通过不是完整回归通过。

文件：[实际修订schema](C:/Users/33393/Desktop/fazhi-next-local-repair-20261004-a6b8b40ac2f74c94b331eeda8a30072c/source/backend/schemas.py)、[新增回归](C:/Users/33393/Desktop/fazhi-next-local-repair-20261004-a6b8b40ac2f74c94b331eeda8a30072c/source/backend/tests/test_knowledge_calendar_dates.py)、[5行业务patch](C:/Users/33393/Desktop/fazhi-next-local-repair-20261004-a6b8b40ac2f74c94b331eeda8a30072c/knowledge-calendar-validation.patch)。patch在RUN只做 `git apply --check`通过，未apply回RUN或主仓。

## 2. 公开语料范围下的回归缺口：已定位，不回避

本轮不可写SQLite读取RUN公开副本元数据，确认仍为民法典1260、消费者权益保护法63、劳动合同法98、劳动法107，共1528；QA=0。读取前后SQLite主体SHA一致；不读取原真实库正文，不启动模型、不验证HNSW。测试需求来自原测试断言，不由替身答案生成。

| 非slow real_kb用例 | 所需输入 | 当前公开集合 |
| --- | --- | --- |
| test_verify_against_real_kb | 刑法13、宪法2；另有虚构条文拒绝断言 | 两部法规均不在集合，不能完整验 |
| test_classify_answer_defaults_real_kb | 民法典801；“刑法存在但999条不存在”的分级前提 | 民法典满足，刑法不在集合，不能期待article_missing |
| test_hybrid_retrieve_expected_laws_weights_topk | 民法典577 | 条文存在；本轮未执行检索 |
| test_hybrid_retrieve_exam_long_recalls_core_articles | 刑法347、348 | 输入缺失 |
| test_hybrid_retrieve_short_crime_query | 刑法348 | 输入缺失 |
| test_hybrid_retrieve_plain_long_text | 民法典1209 | 条文存在；本轮未执行检索 |
| test_retrieve_exam_default_cap | 返回1–6条，无指定法名＋条号断言 | 仅长度／上限检查，不作为法律召回证明 |
| test_retrieve_exam_explicit_k_preserves_old_cap | 同上，显式k=6 | 同上 |

详见REPAIR `evidence/initial-revision-verification.json`：静态列出全部real_kb用例及slow标记，8个非slow的需求逐项核对。**本轮不新增skip、不替换金标、不扩到完整真实库。** 原全量1688通过保留为其实际完整库对象的历史记录，不成为当前公开范围的全通过证据。

另一个未关闭限制：助手归因材料记录新栈4条单跑为3失败，而整套为4失败，仍有次序／状态差异需说明。本轮只能确认缺输入足以使上述断言不满足，不能据“两栈都失败”证明升级与每个行为完全无关。

## 3. 自审、证据保存与下一停点

- 按TDD核对红测是未拒绝非法日期，不是工具错误；日期合法／非法边界来自日历规则，保留可选字段与区间兼容。
- 按Ponytail保持5行标准库修复；辅助脚本只位于REPAIR，未给产品增加测试框架／接口。未改测试判据、依赖或主仓并行代码。
- 所有测试命令记录实际argv／cwd／起止时间／退出码／日志SHA。证据以独占新建方式保存，不覆盖旧失败；续跑必须新增明确命令名，不直接重跑会撞文件的旧标签。
- REPAIR `run_checks.py` 是**限定schema／静态检查入口，不是T6全量或服务启动器**。`verify_revision.py`不导入应用；原危险换库／清理脚本未重用。
- 最终文件级验证通过，结果保存在REPAIR `evidence/final-revision-verification.json`及 `final-backend-source-manifest.json`（288文件）。首次 `records-scan.json`扫描22文件，九字段当前值／五类形状均无命中，全部正控有效；正文收尾后另存 `records-final-scan.json`，不覆盖首次证据。扫描范围为本轮报告、evidence、patch、改动源码／测试和精确约束，不含数据库、权重、venv或mypy缓存；不输出凭据值／长度／key hash。未知、历史、编码形式不在证明范围；未准备或外发整根包。
- 本轮为执行者自审，**不是新的独立复核或Owner风险签署**。上轮冻结delivery和下载审批文档不改写。

下一步仍由本会话接手：先取得受限本机实验许可，再在新对象修复禁网／不换库／不覆写证据／进程所有权仪器，补真实管理端拒绝非法日期、合法闰日、损坏PDF及引用点击／停止后重问。仅允许1528公开副本和可丢弃写入副本，不接完整真实语料；普通本机替身不得冒充法律生成验收。

由于冻结BGE上游来源仍PARTIAL，启用它需要明确知情的本机CPU实验许可；许可对象固定原revision `f03589ceff5aac7111bd60cfc7d497ca17ecac65`、禁网、禁trust_remote_code、2026-10-05复审点不自动顺延。真实rerank、外部LLM、下载／安装、真实库写入、合入／提交／push、部署和风险接受均不包括。

因此当前阶段是“本地候选验收缺口补齐”，尚未完成T6或本地正式接受，不处于部署阶段。
