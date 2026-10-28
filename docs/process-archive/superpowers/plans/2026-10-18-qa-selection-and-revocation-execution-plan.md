# QA候选选择、撤回与历史来源追踪：分阶段执行方案

> **For agentic workers:** REQUIRED SUB-SKILL: 使用executing-plans逐票推进；确需派发时使用subagent-driven-development。共享热点只设一名写入者。当前交付是方案，非本轮产品实现指令；不自动启动协作会话。

**Goal:** 分阶段完成有界资格选择、可验证重复、缓存撤回、输出前复核，以及历史/摘要/改写/Agent/派生QA的来源追踪与撤回隔离；保留原始查询、安全边界和已发送历史。

**Architecture:** C21-A保留原始search_qa，服务默认绑定新的资格选择适配器；纯选择模块只管排名与重复。W06-B复用SQL身份/资格版本和现有LRU。W06-C持久化消息/摘要/派生QA的真实依赖，统一模型上下文投影及摘要失效处理，不引入全局消息基础设施。

**Tech Stack:** 候选现有Python、SQLAlchemy、SQLite、Chroma、pytest及标准库；无新增依赖/模型。具体解释器和闭包在执行run.json核定。

**已裁但未完整落实的前置：** C03=P明确包含暂停自动批准。当前create_candidate仍有高分自动approved/写向量分支，不能把“读侧有资格字段”算作P写侧完成。执行顺序补为Task 0→W06-P0→原三阶段；P0是既有决定的落实，不是新产品选择。

## Global Constraints

- 产品规则与范围以[Owner记录](C:/Users/33393/Desktop/ai-legal-helper/docs/full-scope-decisions-20261018.md)和[窄设计合同](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/specs/2026-10-18-qa-read-and-cache-contract.md)为准；原完整执行书其他票不在本轮顺带重写。
- 候选：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`；只读核对HEAD为042f8090c4d76ed0289b26935b222259fa30292e。保护主仓21项tracked改动，执行前再核身份/归属。
- 本轮仅编制文档。后续实现不读.env、实库或未授权副本/向量/会话，不联网外发/调用模型/装依赖，不迁移生产、不部署、不公开Git；不把技能的默认commit步骤当成Git写入授权。
- Owner已批准「可以分阶段，但最终执行计划书里都要有」：H01/W06-C是最终必做范围，不再挂为是否做的待决项。前两阶段可独立验收，第三阶段及最终联合门未闭前，全部撤回路径不得PASS；具体旧未知来源输入策略仍在Task 6对齐。
- 窗口8+1为工程初值；内部同分带1e-6，保留0.7检索和0.92直返阈值。阈值通过不等于法律正确性。
- 全部以下测试均为待新增/待执行用例，尚无红绿结果。文档检查不算产品测试。

---

## 0. 文件责任及拟定接口

### 阶段顺序（全范围必做）

| 阶段 | 任务 | 独立交付 | 对完整验收的限制 |
| --- | --- | --- | --- |
| 准备 | Task 0 | 精确对象与安全runner | 未通过不得执行产品集成测试 |
| 前置：W06-P0 | 本文前置票 | 新生成高分仅pending，明确人工采纳保留 | 未闭则不能报告C03=P完整实现 |
| 一：C21-A | Task 1–2 | 有界候选、资格/分歧与稳定选择 | 不代表缓存及历史撤回已生效 |
| 二：W06-B | Task 3–5 | 缓存依赖、生成/发送前复核及局部验收 | 历史/摘要仍未闭时只能Partial |
| 三：W06-C | Task 6–9 | 消息/摘要/派生QA来源，安全模型上下文，旧未知内容规则 | 为最终计划必做；缺授权或策略仅阻塞具体子项，不能删票 |
| 最终联合 | Task 10 | 57项语义控制、最终对象回归及独立审阅 | 全部相关路径满足才申请W06完整结论；不代替W08法律质量/生产门 |

下列现有文件链接均属于候选；新增文件路径在落地前不存在，不应被报告为已实现。

| 文件/责任 | 具体写面 |
| --- | --- |
| 新增纯选择模块 | `C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/qa_selection.py`；仅标准库，无SQL/向量/模型/日志副作用 |
| [knowledge_service.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/knowledge_service.py:387) | 复用hit构造、保留raw search_qa，新增search_eligible_qa；不改写侧审批/seed语义 |
| [request_bootstrap.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/request_bootstrap.py:336) | 默认依赖绑定新适配器，保留search_qa字段与现有产生处资格复核 |
| [qa_eligibility.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/qa_eligibility.py:1) | 资格唯一真源；增加阶段性fresh读取、不可变依赖快照及复核，不复制来源/引用判据 |
| [answer_cache.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/answer_cache.py:53) | 条目新增可选依赖元数据，保留scope/TTL/generation；模块本身不打开SQL |
| [main.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/main.py:2250) | 命中读取、3个put、QA注入/直返、轻量缓冲与旗舰首正文前复核；SQL继续在线程池 |
| [observability.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/observability.py)、[gate_exit_registry.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/gate_exit_registry.py) | 仅为新增reason/真实受影响出口更新登记，不重写无关门；日志不含问题、答案、证据全文或其摘要 |
| 新增测试 | `C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_qa_selection.py`、`test_qa_selection_adapter.py`、`test_qa_cache_read_guard.py`、`test_qa_first_content_guard.py`；其余文件均在同一tests根 |
| 现有回归 | [test_request_bootstrap.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_request_bootstrap.py)、[test_qa_read_eligibility.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_qa_read_eligibility.py)、[test_cache_scope_invalidation.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_cache_scope_invalidation.py)及其引用的QA/缓存/流式回归 |

拟新增API（以下名字是方案规定，不是现有函数）：

```python
# qa_selection.py，纯选择，不自行判资格
@dataclass(frozen=True)
class Candidate:
    hit: Mapping[str, Any]  # adapter实际传QaHit，选中必须原对象返回
    doc_id: str | None
    raw_score: float
    allowed: bool

@dataclass(frozen=True)
class Selection:
    hit: Mapping[str, Any] | None
    reason: str
    scanned: int

def select_candidate(
    candidates: Sequence[Candidate], *, threshold: float = 0.7,
    boundary_unsafe: bool = False,
) -> Selection: ...

# knowledge_service.py，服务入口；raw search_qa原签名不变
def search_eligible_qa(query: str, threshold: float = 0.7) -> QaHit | None: ...

# qa_eligibility.py，增加字段而不把SQL状态混入公开hit字典
@dataclass(frozen=True)
class QaDependency:
    candidate_id: int
    vector_doc_id: str
    eligibility_version: int
    record_digest: str  # SQL question/answer/evidence的确定性内部摘要

def capture_dependency(hit: QaHit) -> QaDependency | None: ...
def validate_dependencies(deps: tuple[QaDependency, ...] | None) -> Eligibility: ...
def load_read_state_for(hit, *, fresh: bool = False): ...
def evaluate_revocation_state(qa_hit, *, fresh: bool = False) -> Eligibility: ...
```

`None`依赖未知→拒缓存；`() `确认无QA依赖→允许继续原缓存守卫；非空tuple→每次用新会话复核全部依赖。capture须校验SQL与hit内容/链一致；实现不能自行把None降成空tuple。

## Task 0：冻结运行对象与安全测试入口（两票共用）

责任：统筹。只写新的隔离run根/安全测试入口，不碰共享环境、旧RUN或生产数据。

- [ ] 记录实际C/HEAD/tree、主仓修改归属、解释器与安装闭包；若HEAD有别人新改动，复读差异再继续，不reset。记录所有拟改文件源码摘要，数据文件不参与摘要扫描。
- [ ] 按完整执行书W01/6.2复用已审安全runner；若无法找到满足本票隔离边界的实际runner，先交付新runner并审计其副作用，不直接跑pytest或collect-only。
- [ ] 子进程显式设置合成DATABASE_URL、QUOTA_DB、CHROMA_DIR、模型缓存/coverage/cache目录；源码纯树白名单不含.env、数据、模型或会话。屏蔽网络/外部进程外发，不继承现役凭据。通过实际文件/网络守卫阻止逃逸，不能仅依赖setdefault或“我们用了fake”。
- [ ] 在同一runner先做预期反例：读取任意.env、访问隔离根外合成哨兵库、发出socket连接均被阻止；正常读取合成源码和临时库允许。记录“命令未启动/断言红/隔离拦截”三种不同结果。
- [ ] 命令记录器用exit0、exit7及不存在程序验证实际退出码；全部满足后在新run.json落`python`、`safe_runner`、`source_root`、`test_root`绝对路径。

原测试conftest会在收集期建Chroma，多份测试显式load_dotenv。不能用“收集而不执行”绕过本任务。Task 0未通过时仅可做纯文本/纯函数隔离控制，不得称集成已验。

## 前置票 W06-P0：暂停自动批准（已裁必须落实）

责任：knowledge_service.py唯一写入者；与C21-A串行集成。写面仅create_candidate及其实际写入调用者、受影响测试/注释；不删除旧QA、不改生产数据、不修改原始search_qa去重语义。

- [ ] 先核c_gates.C03的P正文，不用“P”字母或旧汇报的FIXED状态替代要求。记录当前HEAD下高分分支设approved、写QA向量的源码差异，Task 0通过后用P01运行反例，不能拿ImportError算旧红。
- [ ] 修改新生成候选创建行为：高分/低分都只保存pending，分数和来源证据照实保留；不自动add_qa_pair、不自签human，不靠调整0.89阈值假装暂停批准。明确人工decide_candidate(approved)仍按既定链/资格写入。
- [ ] 加P01–P04控制，并将既有撤回/缓存控制中“先高分自动批准”的准备改为显式人工批准；旧历史自动记录另建合成fixture，不能删掉其撤回/提交失败控制，不能修改gold迎合原自动行为。
- [ ] 人工采纳、拒绝、提交失败、同进程失效正常/异常回归，核_post所有实际候选生产者没有另一条自动向量写入旁路；失败只留候选或明确异常，不把失败当同意发布。
- [ ] 按当前Task 0安全runner执行新控制和受影响QA/写侧测试；仅在新run记状态及证据，独立review后才把C03写侧从“原则已裁/代码不符”改为已实现。旧approved存量按原资格/迁移策略另验，不能本票一键清空。

最小验收真值：`grounded_score=0.95`仍pending且向量add调用数为0；明确人工采纳后才有可服务向量和human来源；正常低分候选保留；实际调用链不存在另一条自动批准入口。新增测试拟放在`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_qa_pending_only_creation.py`，不能仅改文案/标志后宣称实现。

## Task 1／C21-A1：纯选择与确定性反例

责任：C21唯一写入者；写qa_selection.py与test_qa_selection.py，不先改main。消费Candidate；产出Selection，reason仅为有限枚举`hit/empty/score_error/no_eligible/ambiguous/unstable_id/window_boundary`。

- [ ] 按[用例S01–S12](C:/Users/33393/Desktop/ai-legal-helper/reports/planning/qa-read-contract-20261018/acceptance-cases.md)先冻结输入/期望；每个期望来自Owner规则，不由被测选择函数生成。
- [ ] 新测试文件只import标准库与qa_selection，可用unittest直接执行，避免为纯逻辑引入产品模块。至少包含下面的独立控制；其余按用例表参数化：

```python
import itertools
import unittest
from qa_selection import Candidate, select_candidate

class SelectionContract(unittest.TestCase):
    def make(self, doc_id, answer="方案甲", score=0.95, allowed=True):
        return Candidate(
            {"question": "合成问题甲", "answer": answer,
             "evidence": "合成来源甲|第一条", "law_as_of_basis": "2026-10-01",
             "fingerprint": "", "qa_candidate_id": 7},
            doc_id, score, allowed,
        )

    def test_rejected_sibling_does_not_block_eligible(self):
        bad, good = self.make("b", allowed=False), self.make("a")
        for items in itertools.permutations([bad, good]):
            self.assertIs(select_candidate(items).hit, good.hit)

    def test_different_answers_never_resolve_by_input_order(self):
        a, b = self.make("a"), self.make("b", answer="不采用方案甲")
        for items in itertools.permutations([a, b]):
            result = select_candidate(items)
            self.assertIsNone(result.hit)
            self.assertEqual(result.reason, "ambiguous")

    def test_verified_duplicates_choose_stable_identity(self):
        a, b = self.make("a"), self.make("b")
        for items in itertools.permutations([a, b]):
            self.assertIs(select_candidate(items).hit, a.hit)

if __name__ == "__main__":
    unittest.main()
```

- [ ] 按设计合同3节实现select_candidate：验证有限score→筛threshold/allowed→最高分锚同分组→严格五元组比较→稳定身份选择；boundary_unsafe优先拒绝。没有同分组时不额外改变原单条守卫。
- [ ] 运行新用例，记录旧行为/明确故障替身的红：固定取第一条会被S02/S03排列控制检出；忽略allowed会被S01检出。ImportError/新文件不存在只算脚手架未就绪，不能冒充缺陷被复现。
- [ ] 禁止排序时修改原列表/hit或拷贝掉QaHit槽；未通过前不集成适配器。

## Task 2／C21-A2：接入有界服务入口

责任：同一C21写入者。消费select_candidate；产出search_eligible_qa及产生处实际接线，原raw API/写侧去重不变。

- [ ] 在knowledge_service提取一个私有hit构造器供raw与服务入口复用，维持原公开键、doc_id、4位score和原始search_qa的k=1行为。
- [ ] 新入口一次取k=9；按集合实际metric分别计分、构造前8个QaHit。仅由qa_eligibility判资格，拒绝/异常留下reason但不输出题干答案；不新造另一份SQL/引用判据。
- [ ] 计算边界哨兵风险，调用纯选择，返回所选原对象或None。候选全拒绝不扩大查询，边界同分不谎称全局稳定。
- [ ] `_default_fast_path_dependencies`将既有search_qa字段绑定search_eligible_qa；原prepare_fast_path的统一复核保留，显式历史日期仍不查QA。现有替身deps签名不变。
- [ ] 新增S13–S18适配器控制：真实默认依赖接线、1次k=9查询、cosine/noncosine两支、失败、边界、raw去重不变；跑现有producer、raw链/撤回及指纹/版本回归。SQL/Chroma只可用Task 0通过的合成路径。
- [ ] 记录K=1/4/8的调用数、SQL数、候选数及延迟分布；不同K不是同一个召回分母，不用人工向量宣布语义收益。首轮生产值最多8，不因某组红就继续扩池。

验收：S01–S18全覆盖且各有原日志/退出码，必要正常腿保持通过。若旧raw观察测试突然“找不到被撤回记录”，检查是否把资格策略错误塞进raw接口，不改该测试掩盖。

## Task 3／W06-B1：不可变QA依赖与缓存读写守卫

责任：W06-B唯一写入者，在C21-A接口冻结后串行接入；不同时改知识写侧或数据库schema。

- [ ] 增加QaDependency/capture_dependency/validate_dependencies；复用同一状态判据。record_digest由SQL的question/answer/evidence按固定字段顺序JSON编码计算，内部使用不落日志；身份缺失、向量/SQL内容不一致、异常一律无法签发依赖。
- [ ] 缓存put增加关键字`qa_dependencies: tuple[QaDependency, ...] | None = None`并保存冻结值；get/get_similar仍是存储查询，main不能拿其返回值直接发送。旧条目没有该字段视为未知。
- [ ] 在main建立一个共享的异步缓存核验入口，在线程池调用validate_dependencies；精确、相似命中都必须经过它。拒绝后走正常流程，不能相似兜底又把同一失效条目捞回发送。
- [ ] 对3个put（合同、轻量、旗舰）记录“实际使用输入”的依赖快照，并在写入前验证；没有用QA明确传空tuple，用了不可追踪QA不写缓存。put默认None防漏接线，不默认信任历史无元数据条目。
- [ ] 保留现有generation/scope/日期/意图/引用写闸，依赖不能覆盖旧守卫。读取当前QA为空时仍核缓存自身依赖；不把“已清pre”当作旧缓存答案不再依赖QA。
- [ ] 覆盖B01–B11与B17：暖精确/相似、未知依赖、已知空、丢行/异常、version/映射/内容变化、同进程旧generation与不同进程外部撤回。
- [ ] 跨进程用独立合成SQLite文件：读进程先缓存并等待Event；写进程提交撤回，不调用读进程clear；写成功后读进程发起新请求，断言无旧答案content、无旧QA注入。不能用同一Session缓存充当第二进程。

验收：状态/身份/版本/内容任一变化可检出；正常已知空缓存与未变化依赖缓存保持可用。业务代码从主线程调用同步SQL视为未完成。

## Task 4／W06-B2：生成前与首正文前复核

责任：同一W06-B写入者。消费fresh资格及实际输入依赖；产出P/O/W阶段边界，维持既有流式、错误、取消和资源关闭行为。

- [ ] 给load_read_state_for和evaluate_revocation_state增加默认False的fresh关键字；fresh时清理该hit的状态/链记忆并创建新SQL会话，不复用早期ORM对象。阶段内复用不改变判据，阶段边界明确新读。
- [ ] 构造messages前复核QA，实际发起模型调用前再确认其依赖仍有效；旧messages若含失效QA必须重建，不能只清pre后继续旧messages。依赖快照绑定本次生成，禁止在完成时从后来被清空的pre重新签发空依赖。
- [ ] 缓存E1、QA直返E2、轻量整答E7、旗舰E8/E9首个非空正文之前执行O；status/restart已经发出不跳过O。其他分支确认其实际不含QA时保留原行为，并登记覆盖证明。
- [ ] O拒绝旧缓存/直返则正常回退；拒绝已缓冲生成结果则close旧生成器、丢弃旧产物，用不含失效QA的新messages最多重做1次，仍失败走既有显式错误路径。不得把旧答案_post为成功，也不得写入缓存。
- [ ] 首个非空content已发后允许旧流完成，保留历史；W检查失败则不写缓存。用户取消/断连优先，finally只关闭本请求拥有的资源，不能因回退多发DONE或重复_post。
- [ ] 按B12–B16控制P/O/W间撤回：用Event/Barrier控制缓冲整答与首块，不使用sleep；阴性控制须先证明旧内容确实在待发产物里，防“本来就没引用”假绿。
- [ ] 更新旧“每请求1次SQL”的测试为阶段内复用、跨阶段新读及有界计数；保留原并发失效控制，不整删原性能断言。记录每阶段和每候选实际读数。

验收：可控撤回在O读取之前提交时，首正文无旧产物；O之后已开始正文的流不被主动打断；历史行不被改写；中断、重建、失败、缓存及_post计数都有独立反例。不能把O前status帧当作“允许流继续”的证据。

## Task 5：阶段一/二局部验收与阶段三交接

责任：统筹集成，独立reviewer只读复核。实现者不能自己签整体验收。

- [ ] 跑S/B用例与受影响QA/缓存/消息构造/流式测试，先定位产品断言红、环境错误与数据守卫拦截，失败分析后再决定重试。
- [ ] 使用Task 0核定的runner，命令只允许读run.json中的路径，不能拼猜解释器。示例命令对runner要求：接受pytest参数并原样返回真实退出码；不满足就先修runner，不直接调用pytest：

```powershell
$qaRun = Get-Content -LiteralPath $qaRunJson -Raw | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $qaRun.python -PathType Leaf)) { throw '解释器不存在' }
if (-not (Test-Path -LiteralPath $qaRun.safe_runner -PathType Leaf)) { throw '隔离runner不存在' }
$qaArgs = @('-q', 'tests/test_qa_selection.py', 'tests/test_qa_selection_adapter.py',
  'tests/test_qa_cache_read_guard.py', 'tests/test_qa_first_content_guard.py',
  'tests/test_request_bootstrap.py', 'tests/test_qa_chain_by_doc_id.py',
  'tests/test_qa_read_eligibility.py', 'tests/test_qa_direct_return.py',
  'tests/test_qa_direct_return_version_guard.py', 'tests/test_qa_revocation_lifecycle.py',
  'tests/test_answer_cache.py', 'tests/test_cache_similar.py',
  'tests/test_cache_scope_invalidation.py')
& $qaRun.python $qaRun.safe_runner @qaArgs
if ($LASTEXITCODE -ne 0) { throw ('定向门失败，rc=' + $LASTEXITCODE) }
```

- [ ] 新纯选择unittest文件可在不收集conftest的安全子进程先运行；其文件须自行定位backend导入路径，且只import标准库与qa_selection。不把纯函数通过外推为SQL/SSE已通过。
- [ ] 精确交付树跑ruff/format/mypy及完整书W12要求的对应安全门；旧3d08c09门只作历史对照，不为新HEAD填PASS。按完整书记录coverage、skip/deselect与环境缺腿，不能为了计数上涨删旧红。
- [ ] 汇总用例逐行PASS/FAIL/BLOCKED/NOT_RUN、命令/退出码/对象、反例与未测项；产品门与法律/真实模型门分开。
- [ ] H01/H02的旧行为反例交给阶段三，明确该阶段必做；不因S/B通过就销项。此处不自行实现历史清空，真实数据迁移、外发和发布仍走原独立关口。

## Task 6／W06-C1：来源契约、输入策略与覆盖清单

责任：统筹与C的同一接口负责人；先做合成规格/控制，不读真实会话。消费阶段二QaDependency；产出模型上下文投影、持久来源格式、输入策略和迁移回退契约。

**新增责任文件：** [memory.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/memory.py)、[tools/memory.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tools/memory.py)、[tools/contracts.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tools/contracts.py)、[agent/chat_integration.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/agent/chat_integration.py)、[agent/runtime.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/agent/runtime.py)、[models.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/models.py)、[migrations.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/migrations.py)，以及前两阶段main/request_bootstrap/qa_eligibility/knowledge_service写面。只改确实读写这些依赖的路径，Agent若某路径确无历史输入则交覆盖证据，不顺带重构Agent规划器。

- [ ] 冻结H01–H18用例，先用旧构造器在纯合成pre复现history/summary回流；逐一列普通回答、rewrite_query、摘要压缩、retrieve_memory、Agent新建/恢复/工具Observation重放、缓存回放及_post再沉淀的生产者与消费者。
- [ ] 定义统一来源包：schema_version=1、complete、qa_dependencies、input_message_ids/输入摘要快照标识。祖先包未知/坏格式/容量耗尽时complete=false，不能改成空依赖；依赖类型复用QaDependency，JSON序列化与验证集中一个入口。
- [ ] 新增模型专用load_model_context，保留原始历史读取接口以服务UI/审计。RequestBootstrap/RecentMessageSnapshot及工具DTO按契约显式携带内部来源，不把它们混到用户消息正文或模型伪造可写字段。
- [ ] 给Owner具体对照后确定旧未知来源输入规则：推荐UI原文保留、模型侧不将未知assistant/摘要当可信既有结论，优先从用户事实/核验材料重建并允许澄清；同时列出对多轮指代、旧Agent恢复和命中率的影响。这是策略对齐，不重复问历史/摘要是否做；未确认前不全量屏蔽或默认放行未知。
- [ ] 确定nullable字段迁移、幂等/失败回退和权限范围；只在合成旧schema/新schema演练。真实存量处理单列目标、权限、恢复证据，不将“计划纳入”当实库授权。

最小新增存储契约（拟定字段，不是已有实现）：

```text
Message.qa_provenance: nullable TEXT
Conversation.summary_provenance: nullable TEXT
QaCandidate.qa_provenance: nullable TEXT

NULL：旧来源未知；绝不等价于“无QA依赖”。
schema_version=1, complete=true, qa_dependencies=[]：真实输入已证明无QA祖先。
schema_version=1, complete=true, qa_dependencies=[...]：完整传递依赖。
complete=false、坏JSON、未来未支持schema版本：来源未知，不作可信空集。
```

## Task 7／W06-C2：消息、派生QA与来源原子落盘

责任：C负责models/migrations/knowledge_service及来源共用契约；统筹串行集成main/_post；Agent写入者只改已冻结DTO与finalize边界。新增测试文件`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_context_provenance.py`。

- [ ] 新列沿现有_COLUMN_MIGRATIONS幂等增加并补schema parity控制；旧content/summary/角色/排序不变，旧行字段NULL，不用批量默认complete=true洗白。
- [ ] 收集本次实际使用的QA、历史assistant、summary和工具结果的传递依赖，去重后签发来源包；任何未知祖先污染完整性。原始用户事实与已有助手法律结论分开，不能仅因当前qa_hit为空签已知空。
- [ ] main._post把规范化后的回答与原生成来源包同一事务落盘；缓存回放传原依赖，不因curate=False丢来源。Agent finalize在其现有原子终稿事务落来源，不破坏所有权、状态版本与幂等。占位/错误消息显式标识其实际来源，不假充已核答案。
- [ ] 新QaCandidate记录派生来源；不能从新的引用集合反推“原QA已不再参与”。资格读取在现有唯一判据中校验传递依赖，防从失效祖先生成的新candidate绕过撤回。
- [ ] 派生来源核验拒绝循环、自引用、未知格式与超限链；按实际依赖去重，不无限递归。阶段三的record_digest纳入规范化来源包及schema版本，旧格式缓存保守miss，不能在祖先包变化后复用旧“已核”快照。
- [ ] 对半途提交失败、回放重复、祖先未知、格式坏、依赖容量耗尽及跨用户ID控制运行H03–H06/H12/H16/H17。仅在完整输入已知无QA时签空包的阳性必须保留。

验收：消息/来源不能只落一半，历史原文未删改，继承链不因缓存/Agent/新candidate丢失。旧真实数据迁移未授权则保留对应BLOCKED，不阻止合成实现及安全门。

## Task 8／W06-C3：统一模型上下文与所有入口复核

责任：C实现模型上下文投影；B接查询改写和普通回答；Agent唯一写入者接tools/runtime。共享memory/main热文件串行集成。新增测试文件`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_memory_revocation_integration.py`。

- [ ] load_model_context先核用户/会话归属，再读真实模型输入来源；使用阶段二fresh复核，生成可供模型使用的summary/recent及其完整依赖。原load_context/历史显示保留，不能在读历史UI时顺便清库。
- [ ] request_bootstrap的序列化recent、RecentMessageSnapshot与rewrite_query消费同一安全投影；已知失效assistant在改写阶段就不能被当成既有结论，不允许等改写后的问句洗净来源再过滤最终messages。
- [ ] main普通_build_messages及其他使用history的模型构造器逐项接入；pre不自行持有一份绕过投影的原始summary。重新构造messages时继承投影来源，P/O/W继续跨阶段新读。
- [ ] tools.memory从授权会话读取同一投影，MemoryMessage/RetrieveMemoryOutput新增内部来源字段需单一DTO变更及消费者回归；Agent新建、恢复与持久Observation重放在再次交模型前复核依赖。没有来源的旧观察按Task 6已裁规则处理，不能只过滤新工具返回值。
- [ ] 按已裁旧未知策略处理模型输入，UI仍保留原文；不以相似字符串剔除用户事实，不把用户引用的旧答案提升为已证法律依据。必要澄清用现有通道，避免另造一套会话模式。
- [ ] 跑H01/H02/H07/H12–H15正常及反例：同一合成历史在UI可见而模型不复用失效助手结论；多轮指代、用户事实、合法无QA历史继续可用；输出前撤回与取消控制沿阶段二重跑。

验收：历史→改写→模型与历史→Agent工具/恢复→模型两条实际链均有运行证据，不能仅测投影纯函数。未覆盖入口明确BLOCKED，不能报全部prompt已隔离。

## Task 9／W06-C4：摘要失效、重建与再次沉淀

责任：C/B协同，memory.py唯一写入者；main._post/knowledge_service只按其返回契约串行接入。新增测试文件`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_summary_revocation.py`。

- [ ] compress汇总旧摘要与实际压缩批次的来源并集；祖先未知保持未知。失效旧摘要不能作为_extend_summary的existing输入重用；重建只用已裁规则下可用的用户事实和核验材料。
- [ ] 内容、summary_upto和summary_provenance同事务更新，以读取时的摘要/指针/来源快照作乐观并发条件；压缩期间撤回或别的任务更新会话时，拒绝过时产物，最多重新构造一次，不覆盖较新安全摘要。
- [ ] 重建失败不推进指针、不覆盖原summary，不把旧失效摘要继续送入新prompt。保留原文供UI显示；模型上下文可以不用失效摘要，必要时澄清，不假装旧结论仍可信。
- [ ] 重新沉淀前复核实际生成来源。撤回后允许完成的旧流可保存历史，但不能自动生成新的可服务QA；新候选保留祖先来源，读侧继续复核。不得借新candidate id、重写evidence或摘要再次生成洗掉撤回。
- [ ] 用fake摘要器观察真实输入，不调用真实模型。覆盖H08–H11/H17：摘要并集、旧摘要污染、压缩竞态、失败游标、再沉淀；阳性控制证明正常增量压缩与正确已知无QA答案仍可复用。

验收：失效来源不能经“摘要→改写→回答→新摘要/新QA”回到可服务集合。未知存量仅按已裁策略处理，不删除源记录凑绿；真实对象应用另走授权/恢复门。

## Task 10：全范围最终联合验收与交付

责任：统筹，另设只读独立reviewer；需取得实际最终源码/闭包及合成数据身份，不混用三阶段旧HEAD的绿。

- [ ] 对P01–P04、S01–S18、B01–B17、H01–H18共57项语义ID逐项对账；复现P0写侧及原H01/H02反例，再验证新流程阻断，同时保留人工采纳、UI历史/用户事实/正常缓存/正常摘要阳性。
- [ ] 在Task 5的定向命令中追加已新增的test_context_provenance.py、test_memory_revocation_integration.py、test_summary_revocation.py及既有test_memory.py、test_migration_schema_parity.py；另核实际受影响Agent/工具/会话/API回归清单，不猜未存在测试路径。
- [ ] 同时接收前置P0的test_qa_pending_only_creation.py及其实际写侧回归；没有P01–P04运行证据不能只用读侧57项中的其余部分补齐。
- [ ] 合成旧schema升级连续两次、迁移中失败及恢复、未知NULL与已知空包、消息与来源原子性、摘要并发、新/旧Agent观察重放都必须有证据。测试准许新增列不等于准许对真实库启动import迁移。
- [ ] 测新请求在撤回成功后的直接QA、精确/相似缓存、历史、summary、改写、Agent及派生QA各入口；对在途首正文前后分别核原Owner边界。不能以第一条status帧或本地clear作为全闭环证明。
- [ ] 最终纯树按完整书W12跑必要工程门并独立复核；W08真实/法律质量、W14实库/环境与发布关口分别列结果。只要历史/摘要必做子项未实现、未测或待策略，W06完整撤回结论保持Partial/BLOCKED。
- [ ] 交付说明明确schema/来源格式与读写代码版本必须匹配；混合运行的旧进程可能绕过守卫，不能拿新进程测试证明现役已切换。具体切换/回退/旧reader退出由原W14准备方案，不在本次文档任务执行。
- [ ] 更新完整执行书W06/W12/W15及current交接、逐票清单与未测项。第三阶段不得移到无责任人的“以后优化”；有真实权限阻塞就列对象、解除条件和责任人，不用文档数量或测试数销账。

## 6. 派发与回件短提示

```text
你只负责W06-P0、C21-A、W06-B或W06-C指定写面，先读Owner记录、分阶段设计与本票步骤，回报实际候选HEAD。P0必须展开C03=P正文核写侧，不因旧状态FIXED而跳过。
你不是唯一助手；不覆盖/回退其他修改，main/knowledge_service/qa_eligibility由唯一写入者串行接收。
先通过隔离runner反例，再做目标控制；原始search_qa去重语义不能变，资格不得分叉。
P/S/B/H期望来自已冻结用例，不改gold/阈值或用同源模型自证。历史/摘要阶段已明确必做，不扩大为删除会话、真实数据迁移或通用记忆平台。
交付精确diff、API、用例ID、命令rc、原日志、独立反例、SQL/模型/缓存实际调用数和未测项。
没有真实数据/外发/生产/Git公开授权；没有跑过的腿明确NOT_RUN，不只报“全部通过”。
```

### 6.1 使用方法与共同指导

全新统筹先用[总执行书7.0启动提示词](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-15-full-scope-remediation-and-closeout-execution-plan.md)；子助手收到“本节通用短提示＋对应6.2/6.3/6.4/6.5卡＋设计合同＋用例表＋实际对象/写面/依赖”。只转标题或口头说“都按计划”不算派发契约。A/B/C旧助手代号与C21-A/W06-B/W06-C票ID分开，不能把C21-A误派成初始化助手A的所有任务。

统筹在实际派发前落task-contract.md并写清实际trace_id、候选HEAD/tree、唯一允许文件、run根、接口版本、前置票、验收ID、数据/外发边界。下面提示词通过读取该契约取得动态值；不在提示词中填猜测路径或过期SHA。缺契约的子助手先返回缺失字段与可安全只读的核对结果，不擅自写热点文件。

实施指导：

- 先追真实调用链再修改，现有函数名或注释不等于实际接线；“源码应当如此”不能充当已执行证据。
- 优先复用已有资格判据、LRU、迁移与错误通道。先证明目标问题，避免顺手整理main、换框架或建立通用记忆平台。
- 使用明确合成哨兵答案作为“旧内容泄漏”观察值，证明阳性确实能进入待测缓存/prompt/缓冲产物；没有对象的“未出现”不是有效负控。
- 性能控制按真实向量/SQL/嵌入/模型调用次数记录；K和epsilon是方案初值，不把人工排名或本地嵌入说成语义质量/零开销证明。
- 来源未知、确认无QA、依赖仍有效是三种不同状态；NULL/空列表/查库失败不能互相代换。不向模型暴露内部状态并让模型自行签完整性。
- 缓存只是一条输入路径，历史/摘要/改写/工具结果同样可能产生派生依赖；必须跟随实际生成输入，不能在输出完成时根据已被清空的pre重签空包。
- 读写/验收共享同一契约，不重复维护两份schema。每完成可验小片先记证据再更新状态，禁止实现者自己的“确认”代替独立review。

### 6.2 阶段一助手卡：有界候选与可验证重复

```text
你只负责C21-A的Task 1–2，以task-contract.md实际写面为准，不改main/缓存/历史schema。
先读Owner决策2/3、设计3节、S01–S18和现有raw search_qa所有调用者；先回报基线身份与接口，接收P0前置的写侧修复/独立review或明确阻塞，不把“P已裁”当P0已做。
原search_qa的k=1和写侧去重语义保留；新增服务适配器接真实默认deps。资格由qa_eligibility唯一裁决，纯选择模块只处理分数、同分组、重复和稳定身份。
窗口8+1：第9条只是边界哨兵，不能偷偷作为服务候选，也不能反复补池。保留两条metric计分分支与现有0.7/0.92及版本/指纹守卫。
先用候选排列反例钉住“拒绝兄弟挡合格者”“同分不同内容不能任选”“raw舍入不能造同分”。确认为重复的元组仍须资格通过；同一candidate id不能证明答案版本相同。
使用Task 0安全入口，纯选择控制与SQL/Chroma接缝分开。固定候选排列通过只证明窗内规则，不报全库确定性或法律正确率。
回件附真实deps绑定、raw接口保持、S项证据、实际调用计数、diff和未测项；不只交一个排序函数说已集成。
```

### 6.3 阶段二助手卡：缓存与生成/输出前复核

```text
你只负责W06-B的Task 3–5，先取得阶段一接口与独立review结果；共享main/qa_eligibility热点按唯一写入者串行。
先画本次实际生成输入到缓存条目的依赖链。当前基线main有3处put及精确/相似两种命中，先现量核对，源码变了按真实调用点补齐。
依赖None=未知，空tuple=完整输入已证明无QA，非空=全部实际QA祖先。旧缓存或有未追踪summary/assistant输入都不能默认签空。
精确/相似命中均在content前新读SQL依赖；保留旧scope/TTL/generation/质量写闸。跨进程撤回用独立进程+合成SQL验证，不用“clear调用了”冒充全局失效。
P/O/W分阶段读，不能复用早期QaHit/ORM状态到O。只清pre不重建messages，或只重建messages却继续发送旧缓冲答案，都不算修复。
status/restart不是正文开始。O发现失效就丢弃旧答案，关闭旧生成器，按合同最多重做一次；已开始非空content的旧流允许完成，但不得再写可复用失效缓存。
观察取消、断连、_post和DONE次数；用Event/Barrier安排撤回时点，不sleep赌时序。不要新造消息总线、全局epoch迁移或无界重试。
回件按B01–B17逐项交证据，列真实输入快照、SQL阶段计数、3个put元数据、成功/失败/正常缓存控制；明确第三阶段尚未关闭的输入路径。
```

### 6.4 阶段三助手卡：历史、摘要、Agent及再次沉淀

```text
你只负责W06-C的Task 6–9。Owner已决定历史/摘要最终必做，不再问要不要做；Task 6只对齐旧未知来源具体输入行为。用户已决定历史原文/UI保留，不能拿删历史当修复。
先追memory.py、request_bootstrap、main的messages/_post、tools.memory、Agent终稿/恢复/Observation以及create_candidate的真实依赖；别只在最终_build_messages前加过滤。
复用阶段二依赖类型。Message、summary与派生QaCandidate记录真实传递来源，未知祖先必须传播未知；内容/来源/摘要游标同事务或受控原子更新，旧NULL不能默认已知空。
历史UI读取与模型输入投影分开。查询改写、摘要器、普通回答、Agent新工具与持久观察重放使用同一来源规则，先做用户/会话归属检查，再读取或核验内容。
旧未知输入策略实施前用6.8方式给具体合成例子/代价，只问缺失选择；其他已定来源schema和合成控制可继续准备。不读取真实会话来造例子，不从答案字符串/日期猜来源。
摘要不能继续吃已失效existing；压缩期间撤回/其他压缩先提交时拒绝过时结果，失败不推进summary_upto。仅给旧摘要贴新标签不算重建。
已开始输出的旧流可以保存历史，不意味着其失效祖先可以自动再沉淀为可服务QA。继承依赖防新candidate id洗白；循环/自引用/容量耗尽要有失败控制。
只在合成新旧schema演练迁移/恢复，真实数据与现役切换另走原W14授权。既有DTO extra=forbid，新增字段必须同时更新真实消费者与正常控制，不吞验证错/skip救绿。
回件H01–H18逐项说明原始历史保留、各模型入口不复用失效结论、正常用户事实/指代仍有效、事务/并发/异常/Agent恢复/再沉淀及未测项；不自称所有历史已清理或所有prompt已安全。
```

### 6.5 独立reviewer卡（只读）

```text
你负责独立复核指定阶段或Task 10。只读源码/合成证据，不改产品、测试、gold或实现者结果；不启动有未审副作用的入口。
先取得实际HEAD/tree、精确diff、接口契约、P/S/B/H逐项回执与原日志。沿规格符合/工程可靠两轴给PASS/FAIL/Partial/Unknown及证据，不因实现者汇报“都绿”而放宽预期。
优先反证：raw去重变义；资格只挂一个出口；第9项偷偷兜底；舍入造同分；旧缓存依赖被当前空hit洗掉；本地clear冒充跨进程；status冒充首正文；pre清了messages/缓冲没清；未知NULL当空；历史在rewrite/summary/Agent重放回流；新candidate洗掉失效祖先；压缩指针先推进。
每个拒绝测试都核阳性对象是否真实存在，每个异常都核失败归因。两个进程输出相同不等于确定性；有引用不等于支持结论；工程门不等于法律专业签核。
发现给实际文件/行、触发条件、后果、置信度、允许环境的复现步骤、原日志和最小修正方向。证据不足标Unknown，不编线上事故。
如需执行复验，先核Task 0守卫，命令rc/被测对象必须实际可见；无该条件就明确未运行。回件给当前统筹，不代合并或宣告生产可用。
```

### 6.6 统筹接件与集成卡

```text
你负责实际派发、写面锁定、接件和最终状态。先核用户当前授权；本提示词不授权创建新用户会话或对外发消息。
依赖顺序为Task 0→W06-P0→阶段一→阶段二→阶段三→Task 10；可并行的是独立只读审阅/隔离用例准备，不能让多个助手并写main/knowledge_service/qa_eligibility/memory/models/migrations。
每票先核产物字节与回执/被review对象一致，再核API/DTO、正常/失败控制、实际命令与未测项。接口不一致退回责任票，不批量取一侧拼绿；同一代码修复最多两轮退回，第三次仍失败按用户纪律质疑结构。
先跑新增/受影响定向控制，再在精确集成对象跑原完整书要求的必要门；不把独立各自HEAD通过拼成最终HEAD通过。更改后只按影响复验，不无理由反复全量。
退回项明确“哪一语义ID、哪个输出不符、原证据在哪、期望是什么”，不给“再完善一下”式无边界任务。接管只修不合格部分，跨模块接管后重新独立复核。
已批准原则继续执行，缺事实自行查允许的源码；确需新产品取舍用一次一个问题的grilling并给推荐/代价。真实数据、模型外发、生产和发布要先交具体可审准备，再按对应关口处理，不提前索要整包许可。
所有57项语义ID保留在总账；P0写侧、阶段一/二只报各自局部验收。历史/摘要未闭不能删票，实际数据/环境/专业审签缺证就列具体BLOCKED和解除条件，不笼统推给Owner。
```

### 6.7 每票回执（补充总书1.2，不代替原日志）

```text
票ID/阶段/trace_id；实际C、HEAD/tree、起止时间：
本轮授权来源、已裁选择、唯一写面；是否存在其他写入者：
症状与最小根因；实际diff/契约变更及受影响调用者：
语义用例ID逐项状态（PASS/FAIL/BLOCKED/NOT_RUN）及证据路径：
旧红/故障控制命令、实际rc；修后命令、实际rc；环境/守卫拦截另列：
阳性/阴性/异常/并发控制；真实组件与替身边界：
向量/SQL/嵌入/模型调用数、样本与分母；是否有真实外发：
未完成/未测/具体阻塞、解除条件、下一责任人：
对原始数据、主仓dirty、旧RUN/review、gold及未授权路径的保护说明：
自审结论/独立review对象与回件/统筹接收结果：
下阶段仍需处理的缺口；不据此声称的产品/质量/生产结论：
```

证据路径必须是实际存在的允许文本/合成日志，不附真实数据或秘密。未发命令不能填rc=0；无测试代码的设计用例仍是NOT_RUN，不能填PASS。“Partial”用于阶段汇总，逐用例如有缺失要展开到未测/失败/阻塞，不能用一个总状态掩盖。

### 6.8 阶段三具体产品取舍的提问范式

```text
先说明新查到的具体源码事实、来源与合成反例，再问一个产品行为问题：
“旧assistant/摘要没有可追踪来源。原文会保留，但用户追问‘那下一步呢’时，系统应怎样使用这段未知结论？”
给推荐：模型不把未知结论当已确认依据，保留用户事实，必要时重新检索/澄清。
同时说明代价：某些旧会话要多问一句或重新生成；不能承诺原多轮体验完全不变。
等待Owner回答后再实施该具体行为；不要重问历史/摘要是否纳入、历史能否删除或此前已批准选择。
```

这只是提问结构，不是预填Owner答案。由源码即可查得的字段、路径、版本、测试状态先自行核，不向用户提事实竞猜题；必要选择落新的决策条目，引用原话与影响票。

## 7. 编制自审

| 五问/风险 | 本方案处理 |
| --- | --- |
| 边界自然吗 | 纯排序不判资格；SQL资格唯一真源；缓存模块不依赖SQL；main只编排阶段 |
| 更小替代是什么 | 复用现有SQL身份与LRU，不新增总线/epoch迁移；保留raw接口而非改动所有写侧调用 |
| 并发/默认值/假接线/降级/评测污染 | fresh跨阶段；None依赖默认拒绝；验证默认deps真实绑定；回退可观测且有界；排列/阳性/阴性及no_cache隔离 |
| 事实有来源吗 | 源码链接和实际HEAD；8+1/1e-6明示技术初值；新函数标明尚不存在，未虚构执行数据 |
| 指标是否代理目标 | 控制资格、旧产物泄漏、依赖变化与有界IO；不把测试数、覆盖率、召回或稳定性当法律正确率 |
| 是否覆盖全部已裁规则 | C03=P前置、原五项规则与“允许分阶段、全范围必做”均有P/S/B/H控制、任务与最终门；具体旧未知输入策略不冒充已批 |

本方案完成不等于三阶段完成；前两阶段局部通过不能替代第三阶段；三阶段工程完成也不等于W06生产迁移、W08真实质量、J1–J6全部通过。

覆盖与歧义补充：总执行书8.2的U01–U13仍需在原W00–W15承接，本子计划只具体实现P0及W06三阶段；不得因子计划用例较细就遗漏生产准备、仪器、账本、临时资源、真实模型/浏览器及其他总书任务。关键表述按总书8.3消歧，执行循环按8.4；有不一致先记录具体规范/事实差异，不自行挑最宽解释。
