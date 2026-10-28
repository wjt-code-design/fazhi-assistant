# 依赖风险执行轮汇总（Owner 汇报文档，2026-10-03）

> 本文为2026-10-03依赖风险执行轮的Owner汇总。技术细节以 [正式报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-dependency-risk-execution.md) 为准；后续独立审核见 [审核报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-independent-review.md)。[执行书](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-03-next-local-candidate-execution.md) 已补自包含指令和防重复状态，修订后的文本不是原助手执行时版本。原执行集合中的报告副本保留原时点，没有覆盖为本次修订稿。

> **最新进展以§十为准（2026-10-04）：** A＋B联合验证及交付已完成（§九），正式采纳B／D2未决定；新增模型链与活跃LangChain的只读预检，不是升级验收。§二至§八记述原单项执行及当时独立审核，旧快照中的“联合未验”已被§九取代，不要求重跑。

## 一、一页结论

| 项 | 结论 | 关键数字 |
|---|---|---|
| A 删包实验 | **通过，Owner 已采纳** | 全量非 slow **1680 passed／10 skipped／18 deselected，覆盖率 85.42%**；1690 个 nodeid 与旧基线逐条一致；烟测 24/24；新审计 42 行／8 包／25 组 |
| B setuptools 升级 | **Owner批准下载后已续办，通过；正式采纳未定** | 单因素实装恰一处变化（65.5.0→83.0.0）；pkg_resources真实缺失下jieba分词／字典回退通过；全量同A；审计49行／9包／28组；83.0.0自身0通报，旧8行（4别名组）消失 |
| A＋B联合续办 | **仓外离线验证通过；正式采纳与D2仍待裁** | 新venv162实装／165约束；1680通过／10跳过／18不选、85.42%；1690 nodeid一致、烟测24/24；新实装审计34行／7包／21组；v2交付50实际文件扫描通过 |
| C 模型来源 | **PARTIAL**（本地半程已证） | refs/main 未被切；11 文件与 10-02 指纹全符；上游精确 revision 指纹因本机到 HF 不可达未取得 |
| D 交付 | **原执行集合可核查；审核补充另存** | manifest列71个内容对象，目录实际73文件（另有manifest自身与生成后的终扫JSON）；71条hash相符；审核对实际73文件复扫，9字段正控成立、0命中；不是全历史扫描或发布许可 |

## 二、Owner 裁定与落实

| 事项 | 裁定 | 落实情况 |
|---|---|---|
| setuptools 83.0.0 wheel 单项下载 | **批准** | 当日执行：官方 PyPI 元数据核验→单项下载→大小 1008090 与 SHA-256 双重相符→运行根 `owner-wheels/`。记录 `evidence/b1b-download-record.json` |
| 删包采纳为候选变更 | **采纳** | 记录为既定方向；冻结候选根三处未就地改写；实际整合按裁定材料既定顺序另行进行（本地候选正式接受后再准备提交／合入审阅） |
| D2／Windows 有限用途签署 | **未提及** | 仍待裁，未代签；复审 **2026-10-05 不延长** |

## 三、实际做了什么

**接手与基线**：读齐执行书指定证据；仓外新建运行根 `C:/Users/33393/Desktop/fazhi-risk-followup-75542ea22e9b4627a4e090cbc5c7f9aa`，旧候选根（source／venv／evidence）只读未改写；确认仓内无 AGENTS.md，以执行书纪律为准。

**A1–A6（全部完成）**：2658 文件 manifest 逐 hash 复核 0 漂移并复制核验；探针 `socket.bind` 失败定位为 urllib3 导入期 IPv6 回环探测（`HAS_IPV6 = _has_ipv6("::1")`，绑定 `::1:0` 即关，非开放监听），按授权做严格回环核验后通过；仓内对两包直接与动态引用 0 处，`--adapter` 外部清单不可得故结论限定仓内受控路径；独立 venv 纯离线安装（仅既有缓存，未运行旧安装脚本）；实验源码差异精确 1 文件（requirements 三行 diff）；pip check=0、定向 27 通过、Ruff/mypy 0、全量与烟测全绿；conftest 空库副作用按 10-02 先例隔离；新实装审计中 15 条通报随包消失（其中 CVE-2026-45134 组仍由 langsmith 0.1.147 命中，如实单列，未写"修复漏洞"）。

**B1–B3（Owner批准后完成）**：experiment-b以2658文件逐hash复制源码，约束仅换setuptools一行；五项创建／安装退出码记录全0；pkg_resources真实缺失，jieba导入／分词／字典回退成功。原“10个分发有导入”是字符串扫描口径错误：AST确认numpy/scipy/sklearn等命中仅为注释，实际裸导入位于pytest条件分支、jieba回退与onnxruntime可选benchmark；没有证据证明所有分支都运行。实装差异恰一处；审计49行／9包／28组，setuptools 83.0.0自身0通报；conftest副作用同例隔离。

**C（本地半程）**：`refs/main=f03589…` 未变；默认 snapshot 恰 11 文件、逐文件 SHA 与 10-02 记录全符；唯一一次联网尝试（python urllib 20s）被拒（WinError 10061），按执行书停止，未换镜像、未重试、未下载权重、未改 refs。

**D（完成）**：唯一正式报告；交付集合 `delivery-risk-followup-20261003/`（含本汇总）；manifest 逐文件 hash 相符；9 字段（8 个 .env census 值＋Windows 机器级 RERANK_API_KEY）值/形状扫描正控命中、集合内 0 命中、禁止文件 0；不覆盖旧 72／86 文件薄包。

## 四、质量过程（可审计）

- **独立审查**：独立只读子代理对全部承重论断重算复核成立（2658 文件走查、freeze/nodeid/审计重算、交付 hash、HF 缓存重 hash、git 状态、PyPI 在线核对）；其提出 1 项重要更正（"每条附退出码"措辞过强）与 3 项次要证据卫生问题，已全部落入正式报告 §7 并同步交付副本。
- **当场复现**：按证据五连问重跑关键检查全部复现原结果（pip check、闭包差异、审计重算、collect、全量套件、烟测），重跑日志用新文件名（`showwork-*.log`）不覆盖原证据。
- **证据边界更正**（正式报告§7）：原A4/A5和B3除审计外的验收没有逐项命令JSON，B2五项创建／安装与B3审计有记录；不能笼统写“B轮起全部逐命令记录”。六个JSON内嵌时间为手写近似值，mtime也不是精确执行时刻，不能恢复顺序；a1-baseline曾就地更正，原值仅日志留痕；constraints行尾归一。原文件不覆写，不事后补造历史退出码。本次审核新建副本重跑A／B，14条命令均有新执行时间与真实退出码，见§八。

## 五、原单项执行轮没做的／没声称的（联合续办见§九）

**未执行**：C 上游精确 revision 指纹补证（本机到 HF 不可达，两个历史尝试均有记录）；候选变更的实际整合与提交（已采纳但按既定顺序走）；setuptools==83.0.0 写入候选约束（属**新的独立裁定**，B 通过≠自动采纳）。

**未声称**：A 不声称对所有外部 `--adapter` 兼容；"15 行通报消失"不写成"修复漏洞"；真实 rerank／生成质量、Linux／远端 CI、完整应用启动、浏览器端到端均未验——10-02 的 7 次 200 不因本轮改写成"新环境已验"；发布就绪未声称。

**未越边界**：原执行轮未提交／合入／push／建PR，未写真实库，未停止他人进程，真实模型调用0，第四轮标记保留。原“主仓仅新增两报告”只属原检查时点；当前另有5个前端跟踪文件与原脏文档未提交，审核不修改／暂存它们，也不宣称全工作区干净。D2未代签，复审日未顺延。

## 六、待 Owner 裁定与技术待办（不是只有三件工作）

1. **C 的解决方式**：① 在可直连 HF 的环境跑只读 tree API 取回 JSON；② Owner 任一有网设备打开 `https://huggingface.co/api/models/BAAI/bge-base-zh-v1.5/tree/f03589ceff5aac7111bd60cfc7d497ca17ecac65?recursive=true` 把 JSON 交我逐文件比对（小文件比 Git blob SHA-1、权重比 LFS SHA256，几 KB 元数据，不下载权重）；③ 接受 PARTIAL 写入 D2 一并考虑。
2. **setuptools==83.0.0 是否写入候选约束**（B 已通过，采纳与否独立裁定）。
3. **D2／Windows 有限用途签署**（复审 2026-10-05 不延长）。

以上是三个裁定入口，不是全部待办。A＋B已按后续“继续接手”请求做仓外联合技术验证（§九），不必等正式采纳才做只读／隔离实验，也不因此自动接受新依赖。还需：模型链／活跃LangChain适配与Chroma剩余通报分案；独立启动与浏览器验收；后续Linux／CI、历史凭据与推送前检查。提交／push／原库写入／部署仍另设权限门；未选服务器，不安排部署。原助手记录的“批准、采纳”仅支持其已执行的那两项，不扩大为本轮新的采纳／整合授权。

## 七、材料索引

| 材料 | 位置 |
|---|---|
| 唯一正式报告（含 §1–8） | `docs/process-archive/work-report-20261003-dependency-risk-execution.md` |
| 本汇总文档 | `docs/process-archive/work-report-20261003-owner-summary-20261003.md` |
| 运行根 | `C:/Users/33393/Desktop/fazhi-risk-followup-75542ea22e9b4627a4e090cbc5c7f9aa`（experiment-a／experiment-b／evidence／owner-wheels） |
| 交付集合 | 运行根 `delivery-risk-followup-20261003/`：71个列入内容对象＋manifest＋manifest之后写入的终扫JSON，实际73文件；其中报告副本为原时点 |
| Owner 下载单与下载记录 | 运行根 `evidence/b1-setuptools-download-order.json`、`evidence/b1b-download-record.json` |
| B 逐命令退出码记录 | 运行根 `evidence/b2-cmd-*.json`；B 总结 `experiment-b/evidence/b3-summary.json` |
| 保护复核（四次全过） | 运行根 `evidence/` 下 a1-baseline-protection、d1-protection-predelivery／postdelivery、b4-protection-postb |

## 八、独立审核补充（2026-10-03）

不是仅审阅文字：审核者对2658个冻结源码对象、新旧实装分发、1690个nodeid、三个原始审计JSON、71条交付manifest与实际73文件、setuptools wheel重新核对；并用新源码副本分别运行两套后端全量门禁和公开库离线烟测。A／B各1680通过、10跳过、18不选，覆盖率85.42%，烟测24/24；14条命令均退出0。审计数值是对原JSON重新计算，不是重新联网扫描公告服务。

证据根：`C:/Users/33393/Desktop/fazhi-risk-review-20261003-e30b720af8364e4c83ded98210868f7b`。结果、问题更正和当时未完成项见 [独立审核报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-independent-review.md)。此审核时A与B仍为两个单因素实验，尚未创建联合候选；随后§九另做联合验证，没有把它回填为此处的独立审核结果。C仍PARTIAL，D2仍待裁；“报告审核完成”不等于“发布阶段完成”。

## 九、接手续办：联合候选与交付（2026-10-03）

用户要求继续接手后，另建 `C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01`，仅用冻结2658对象、A版requirements、旧约束中两项删除＋setuptools83换版及既有wheel。没有新下载、修改旧环境或主仓业务代码。

新实装162分发／165约束，相对A仅setuptools变化；1690 nodeid与旧基线相同，定向27、全量1680通过／10跳过／18不选、85.42%、公开库离线烟测24/24。14条安装／验收／审计有真实时间和退出码：13条0，漏洞扫描1（存在通报，不是执行失败）。新原始JSON实装审计 **34行／7包／21全局别名组**，torch+cpu仍被扫描器跳过，不写成安全绿灯。

41保护对象、原库38文件、整.env、HEAD／refs、旧源码／公开库／默认模型缓存及开工时5个前端并行修改均核对不变。交付脚本新增文件头错误已红→绿修正；首次集合因PyJWT包说明中的JWT示例形状命中未通过，保留原件。另建v2，只明确精简4份安装report的说明字段；原件／派生件hash和删减路径齐全。v2有49个manifest内容对象、实际50文件，9字段值与形状正控成立，50文件扫描0命中，manifest验证通过。扫描结果在集合外 `evidence/delivery-verification-v2.json`，原失败结果不覆写；包中文档为扫描前快照，主仓当前状态不回填旧manifest。

完整对象／SHA、日志及失败披露见 [联合报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-joint-candidate.md)。另交付 [模型精确revision只读补证说明](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/assistant-briefs/bge-exact-revision-metadata-request-20261003.md) 和 [Chroma风险核对](C:/Users/33393/Desktop/ai-legal-helper/docs/chroma-risk-triage-20261003.md)。模型仍PARTIAL，Chroma两条通报未关闭；B正式采纳、新对象D2与2026-10-05复审仍待Owner。没有真实模型调用、提交／合入／push、原库写入或部署；本地联合技术验证完成不等于发布就绪。

## 十、剩余依赖只读预检（2026-10-04）

已查官方版本元数据、修复公告和标签源码，主审保存并离线核对13份LangChain相关PyPI原始响应，未下载或安装二进制。旧TF5.10.0目标已撤回；相邻5.10.1仅待验证。ST5.6.0公告虽列patched，源码仍允许本地目录绕过信任开关，不能据版本号关闭风险；模型链还缺hub精确目标、完整闭包和CPU torch独立风险核对。

LangChain修复线联动OpenAI SDK1→2；已查可容纳新core的Chroma适配包又要求Chroma本体1.x，不能只换core保留0.4.24。Chroma两条通报未关闭，公开库副本迁移／恢复验收必须另立门槛。langsmith新增0.8.18修复线，旧0.8.0分案不足。详见 [剩余依赖预检与执行边界](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-04-remaining-dependency-preflight.md) 和 [模型链报告](C:/Users/33393/Desktop/ai-legal-helper/docs/dependency-model-chain-preflight-20261003.md)。

本轮只完成调查分案，不形成可直接安装锁或下载批准；后续先解决信任门禁／Chroma目标，再补精确声明闭包及下载单。模型来源仍PARTIAL，不重试此前HF失败请求；B正式采纳、新对象D2仍未签，10月5日不自动顺延。没有主仓业务改动、模型请求、原库写入、提交／推送或部署。未变的旧联合测试本轮不重跑；原交付manifest不回填当前报告。

后续统一队列见 [10月4日本地候选执行计划](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-04-local-candidate-next-execution-plan.md)：T0基线／复审→T1模型、T2Chroma、T3启动准备可并行→T4精确单审批→T5分案→T6联合与应用验收→T7复核／裁定。当前只是计划，未执行升级／启动；10月5日复审不等完整升级结束，也不默认风险接受或安排部署。
