# A＋B联合候选续办与自核报告（2026-10-03）

## 结论与对象

已完成一个**全新仓外source／venv的A＋B联合离线验证**，不是把两个单项的绿灯或审计数值相加减。安装、后端门禁和公开库烟测通过；新实装漏洞扫描仍报红。正式采纳新约束、D2受限用途接受及发布验收没有因此完成。

联合根：`C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01`。以下证据名均相对该根的 `evidence/`。

输入保留只读：10月2日原候选 `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b`；A／B单项根 `C:/Users/33393/Desktop/fazhi-risk-followup-75542ea22e9b4627a4e090cbc5c7f9aa`；主仓HEAD `902e2d161e67100ed6d267a08c393538a0abe109`。本轮不使用当前5项并行前端改动作为候选输入。

按冻结manifest复制2658个源码对象，新source相对10月2日候选仅 `backend/requirements.txt` 不同：去掉langchain／langchain-community，显式声明既有langchain-text-splitters。相对主线仍是原四文件白名单增量，未加业务功能；setuptools只在仓外约束及实装换为83.0.0，不改主仓声明。

联合requirements SHA-256：`594b9e664f1d63a22180ef6dbdf46ee73948a5d0a938d835e1939c9b86c48d4c`。
联合165项constraints SHA-256：`e19cd1ef8ecb7c12397a1a72934c727d6c553467b60fc1859715c010b0ab249c`。该清单保留旧约束除两目标包及setuptools外的所有版本；165约束不等于165实装，因闭包缩减实装为162分发。

## 实际安装与回归

只用既有wheel缓存及已核验的setuptools83 wheel，所有pip install均 `--no-index --only-binary=:all:`。新建Python3.11环境，显式安装pip26.2.1／setuptools83.0.0／torch2.6.0+cpu／dev需求；无新下载、sdist构建、共享venv安装或旧环境卸包。

| 项目 | 新结果 | 原始证据 |
|---|---|---|
| 实装／源码／约束 | 162分发；相对A没有增删包，只换setuptools；源码仅requirements差异；声明及165约束满足 | `environment-verification.json`（22:33:28+08）、4份安装report、5份 `install-*-command.json`／日志 |
| 一致性与定向 | pip check退出0；1690 nodeid与旧基线完全一致；三文件定向27通过 | `test-pip-check.log`、`test-collect.log`、`test-targeted.log`及对应命令JSON |
| 静态门禁 | Ruff check／format退出0；mypy 74文件无错误（仍有未标注函数不检查的提示，不称所有函数均已类型检查） | `test-ruff-check.log`、`test-ruff-format.log`、`test-mypy.log` |
| 全量非slow | **1680 passed／10 skipped／18 deselected，覆盖率85.42%，退出0** | `test-full.log`、`test-full-command.json` |
| 公开库离线烟测 | **24/24，退出0**；使用1528条既有批准公开法规的副本，rerank关闭，不是24个生成答案 | `test-smoke.log`、`test-smoke-command.json` |
| pkg_resources缺失 | 真实导入缺失下，jieba中文分词与dict.txt回退读取通过 | `joint-results.json`；不覆盖任意第三方benchmark／sdist分支 |

共14条安装／门禁／审计命令，均持久化实际 `started_at`、`ended_at`、`exit_code`；13条退出0，漏洞扫描退出1。结果自核在 `joint-results.json`，取得时间 **2026-10-03T22:41:45.956992+08:00**。本轮审计读取同一已安装venv，测试并行时没有安装变更。

测试启动前清空实际密钥和代理变量，保留Windows必要环境；使用fixture配置、HF／Transformers离线、追踪关闭与本地runtime中的数据库／缓存／TEMP。conftest在新source默认位置生成的Chroma已只读查明：0文档、0metadata、0queue、1空collection；验证后移入新runtime的 `isolated-conftest-kb`，SHA不变，不删除数据。证据 `stray-db-isolation.json`。未动原项目库。

## 新实装风险扫描

`installed-audit-command.json` 记录本次联网公告查询于22:35:27–22:36:27+08执行，退出1；`installed-audit.json`为新原始JSON。162条分发记录逐名／版本核对实装；torch CPU构建一项被扫描器跳过，其余有审计字段。统计方法是包级原始行，以及所有ID／aliases的全局连通分量，不把重复别名称为独立漏洞。

| 受影响包 | 原始通报行 |
|---|---:|
| chromadb | 2 |
| langchain-core | 11 |
| langchain-openai | 2 |
| langchain-text-splitters | 4 |
| langsmith | 5 |
| sentence-transformers | 1 |
| transformers | 9 |
| 合计 | **34行／7包／21全局别名组** |

该时点扫描中setuptools83自身0通报，两目标包未安装；相对旧57行快照无新增ID。但这不意味着剩余漏洞被修复或未来没有新通报。`torch==2.6.0+cpu`仍因PyPI无法找到该构建被跳过，不能写成CPU torch无漏洞。不得用旧42−8替代此次真实扫描。

Chroma已另做一手公告与当前嵌入式接口的只读适用面核对，见 [Chroma风险核对](C:/Users/33393/Desktop/ai-legal-helper/docs/chroma-risk-triage-20261003.md)。两条通报仍保留，不加ignore ID、不运行漏洞利用，也不凭静态接口差异裁定漏洞不适用。

## 保护与交付边界

`protection-before.json` 与 `protection-after.json` 核对通过：41保护对象、原Chroma38文件、整.env、主仓HEAD／refs、原脏文档不变；旧2658冻结源码、原公开库、本地默认11个模型文件及refs均保持。当前原脏文档及其他任务5个前端跟踪文件的hash与本轮开工时相同，未暂存／回滚／审核其功能。不声称工作区干净。

本轮薄集合为联合根内的独立检查点：首次 `delivery-joint-20261003/` 卫生未通过，仅保留本地；随后另建 `delivery-joint-20261003-v2/`。只收本轮日志／声明／约束／四文件patch／四份文档及独立manifest，不含venv、完整source、数据库、.env、模型、旧受限快照。patch相对902基线生成，仅供审阅，未应用到主仓。旧72／86／73文件集合不覆写。

交付扫描结果保存在集合**外**：首次 `evidence/delivery-verification.json` 未通过；v2须核对 `evidence/delivery-verification-v2.json`。v2文件不存在或 `passed` 不是true时，不能声称J5交付完成。扫描须含9字段值／形状正控、集合全部文件（含manifest自身）、manifest hash／大小验证及禁止文件核对。本文首次写入时该步骤正在准备；最终完成事实以本报告后续收尾记录及上述JSON为准，不回填旧证据。卫生扫描只覆盖选定集合，不是全Git历史扫描或公开许可。

交付辅助脚本初次执行退出1：两份新增测试在902基线中不存在，无条件git show返回128。基线ls-tree和最小检查已复现此缺陷（退出1），修正为新增文件使用 `/dev/null` 旧侧；只改仓外交付脚本，未改产品。失败时尚未创建patch或集合，观察记录在 `delivery-setup-failure.json`（观察时间不冒充执行时间）。复验及交付结果另以真实新输出核对，不掩盖该辅助错误。

补丁检查修正后退出0。首次集合扫描仍退出1：9字段值正控成立、实际值0命中，但安装报告 `install[18].metadata.description`（PyJWT2.15.0说明中的JWT示例）有1个形状命中文件。没有关闭／放宽规则。原JSON及首个失败集合保留；v2仅将4份pip安装report导出为标明 `metadata-pruned` 的派生件，去掉各包description／description_content_type，保留下载URL／hash、包名／版本／requires_dist及其他字段，记录原件与派生件SHA和逐字段删减路径。审计JSON和命令日志不删减。诊断见 `hygiene-diagnosis.json`；v2是否通过必须看新扫描，不能把首次失败改写为0命中。

## 剩余事项与推荐顺序

1. **模型来源仍PARTIAL。** 本轮没有重复本机失败请求、下载模型、换refs或重建索引。[只读精确revision元数据补证说明](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/assistant-briefs/bge-exact-revision-metadata-request-20261003.md)可交给可达官方HF的设备／助手；拿回完整分页JSON后核对10个小文件Git blob OID与BIN的LFS SHA-256。来源证据不关闭依赖风险。
2. **正式候选对象与D2仍待Owner。** 联合离线技术验证已完成，但B正式采纳不是普通“继续”的含义。选定最终源码、constraints、实装及证据后，D2受限Windows用途必须绑定这个新对象；10月2日原候选的裁定文本不能直接签新依赖。最迟复审仍 **2026-10-05**，本轮不代签、不顺延。
3. **剩余模型链／活跃LangChain／Chroma风险继续分案。** 先做精确一致版本及wheel可得性预检，取得下载范围再升级；不盲升整栈、不强装违反现有上界的Transformers5、不写原库或改变持久格式。Chroma受限静态核对不等于风险关闭。
4. **独立启动／浏览器、Linux／CI、历史凭据与发布前置仍未验。** 当前5项前端并行修改不在此轮验收；生成与新的真实rerank仍需精确范围和调用许可。10月2日7次200只绑定原环境，本轮不认定联合环境已验真实模型。

本轮无提交／合入／push／PR，无原库写入、他人进程停止、新真实模型调用或部署。服务器未选，不安排部署。后续应先补来源并确定风险处理／最终对象，不重复A／B单因素或已经通过的联合门禁。

## 交付收尾记录（2026-10-03，23:07+08）

v2扫描已实际退出0，`delivery-verification-v2.json` 的 `passed=true`：**49个manifest内容对象，目录实际50文件（另1为manifest自身），全部50文件均扫描**；49条bytes／SHA核对相符；9字段值与5类形状正控成立，值／形状／禁止文件均0命中。扫描结果JSON保存在集合外，不故意漏扫自身来描述总数。首个47文件失败集合及原失败JSON原样保留，不宜交付。

补丁最小检查退出0，并以 `git apply --check --reverse` 对联合source只读验证退出0；含两份修改、两份新增测试的路径和新增文件头正确，未实际反向应用。验证与保护步骤不计入上述14条安装／门禁／审计命令。

v2里的四份文档是**扫描前冻结快照**，不含本节或后来主仓文档的完成勾选；此后只更新主仓当前进度，没有覆盖集合或重写manifest。交付结果以集合外的最终JSON核对。本轮联合实验与交付技术任务完成，但正式依赖采纳／模型来源／D2／发布门仍未关闭。
