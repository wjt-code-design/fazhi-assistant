# 依赖风险助手工作独立审核与续办结果（2026-10-03）

> 后续状态更新（同日23:07+08）：本文记录单项A／B独立审核的时点。随后另建联合环境完成A＋B验证及新审计，见 [联合报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-joint-candidate.md)。下文“联合未验”是本审核当时事实，已被新结果取代；没有回填旧证据或把单项结果相减当成联合扫描。正式采纳／D2及模型来源仍未关闭。

## 结论

助手A删包、B setuptools独立实验的主要技术结果成立；本次不是只看汇报，已核对实际源码／实装／原始审计并分别重跑后端验收。没有发现本轮需要修改主仓业务代码的问题；需修正报告夸大与矛盾、补新命令证据、明确剩余边界，已完成这些补充。**这不等于当前阶段已获风险接受或项目可上线。**

主线仍为 `902e2d161e67100ed6d267a08c393538a0abe109`。助手原运行根为 `C:/Users/33393/Desktop/fazhi-risk-followup-75542ea22e9b4627a4e090cbc5c7f9aa`；本次新证据根为 **`C:/Users/33393/Desktop/fazhi-risk-review-20261003-e30b720af8364e4c83ded98210868f7b`**。旧候选及原助手证据均保留，未就地安装／卸载或覆盖失败记录。

## 独立验证

| 对象 | 实際核对／新执行 | 结果与限制 |
|---|---|---|
| 源码 | 按冻结manifest重新hash2658对象；审查requirements与约束差异 | 旧源码无漂移；A只变requirements三行；B源码不变。工具运行产物不是额外业务改动 |
| 实装 | 三个venv用importlib.metadata重新枚举 | A162分发，只少两目标包与3个不再需要的传递包，无换版／新增；B167分发，仅setuptools 65.5.0→83.0.0 |
| 后端门禁 | 新source／runtime副本，A／B分别pip check、收集、Ruff check／format、mypy、完整非slow及公开库离线烟测 | 两侧各1680通过、10跳过、18未选；覆盖率85.42%；1690 nodeid与基线完全相同；烟测24/24。14条新命令退出0 |
| pkg_resources | AST核对原命中文件，真实缺失下执行jieba分词、字典回退 | 通过；不声明所有第三方条件分支／benchmark／构建场景已覆盖 |
| wheel | 重新读本地文件大小／SHA，对照既有官方元数据记录 | setuptools83.0.0：1008090字节，SHA-256 `29b23c360f22f414dc7336bb39178cc7bcbf6021ed2733cde173f09dba19abb3`一致；本轮无再次下载 |
| 审计 | 原三个JSON按ID与aliases连通分量独立重算 | 原57行／10包／32组，A42／8／25，B49／9／28。未重新联网扫描公告服务，torch+cpu依然被原扫描跳过 |
| 原交付 | 71条manifest的bytes／SHA与目录核对；实际73文件完整扫描 | 另2文件为manifest和生成后的终扫JSON；9字段输入及正控成立，值／形状0命中，无禁止文件。不是全Git历史扫描 |
| 原库／配置／基线 | 41对象、38文件原Chroma、整.env、HEAD／refs、原脏文档、旧公开库验后比较 | 输出见 `independent-final-review.json`；不以旧“只有一个脏项”假设覆盖当前并行工作区 |
| 模型缓存 | 默认11文件与历史SHA／大小／refs重比 | 本地稳定性核对，不是官方精确revision绑定。来源仍PARTIAL，本轮不重复失败联网查询 |

主要机器证据：证据根的 `independent-evidence-review.json`、`independent-pkg-resources-review.json`、14份 `a-*-command.json`／`b-*-command.json`及日志、`independent-final-review.json`。两侧解释器沿用助手各自venv只读运行，新源码和数据库路径不指向原项目；不声称又重新离线安装了一遍或创建联合环境。测试产生的源码默认空Chroma仅在审核副本内，查验0文档／metadata／queue，不迁移原库。

## 发现并完善的事项

1. **B状态矛盾**：正式报告开头与未验段残留“experiment-b未创建／全部未执行”，现明确为早期阻塞记录，已被B续办取代。
2. **pkg_resources静态误报**：10个顶层位置的文字命中被写成10个分发实际导入；numpy／scipy／sklearn命中只是注释。AST确认真正裸导入为pytest条件分支、jieba回退和onnxruntime两份可选benchmark。全量套件通过不证明每条第三方分支被执行，已收窄结论。
3. **退出码与时间夸大**：B2安装／创建和B3审计有命令记录，不代表B3所有验收均有记录；结果布尔不是退出码，mtime不是执行时间。原历史不补造，本次另建副本重跑14条命令以填补复核证据。
4. **统计与集合口径**：A消失15条包级通报，14条无其他包命中不等于14个独立漏洞；全局组实际减少7。B消失8条setuptools通报归4组。交付71个内容对象不等于目录71文件，实际73文件；0命中不等于“0误报”。
5. **后续与裁定对象**：原“三件待裁”不是所有待办；A／B单独通过不等于联合候选。原四文件候选D2材料不能接受另一个依赖集合。执行书已补防重复、真实日志采集、pip显式安装、隔离路径、扫描方式与保护边界。

变更文档：[Owner汇总](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-owner-summary-20261003.md)、[正式报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-dependency-risk-execution.md)、[执行书](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-03-next-local-candidate-execution.md)、[裁定材料](C:/Users/33393/Desktop/ai-legal-helper/docs/local-candidate-decision-20261003.md)。原交付中的副本没有回填，不宣称本次修订已经打进旧交付包。

审核辅助脚本曾出现两项初始化错误：torch被跳过时JSON无vulns字段；Windows默认GBK读取UTF-8。根因确认后各修正一次，初次失败留在 `reviewer-setup-failures.json`，均非产品bug。原A的手工近似时间、曾覆写汇总等历史缺陷仍披露，不因本次新绿灯抹去。

## 剩余工作与建议顺序

1. **确定最终候选依赖组合。** 建议正式采纳B的受限Windows验证方向后，在全新仓外source／venv联合A＋B做一轮同源验收／审计；不在已验A／B环境就地改包。联合结果未产生，不用42−8推算成“已验34行”。助手报告中的“批准、采纳”只记录其原两事项，不能扩成新的正式采纳／整合权限。
2. **补模型来源。** Owner可在可达设备取得官方精确revision的完整tree元数据JSON（含分页），只取几KB元数据；按Git blob SHA-1／LFS SHA-256核对11文件。不要下载409MB权重、切refs或以main指针替代。若决定保留PARTIAL，必须具体写入最终对象的风险裁定，助手不能代签。
3. **处理剩余依赖风险。** ST／Transformers／CPU torch联合预检、活跃LangChain适配最小一致集合、Chroma公告适用面分别推进；先分案、选精确版本、查wheel，再获下载范围。来源校验不消除库漏洞，pytest绿灯也不替代风险裁定。
4. **最终对象D2与本地功能。** 最迟复审仍2026-10-05，不自动续期；签字必须绑定最终源码、锁定分发与证据。独立公开库启动／浏览器流程另做，真实生成与新增rerank需要新精确授权。
5. **发布前置仍保留。** Linux／CI、历史凭据／待推内容检查、提交整合、push、真实库备份恢复、服务器与部署是后续阶段；没有服务器，不部署，也不借本次请求提交或push。

该审核时还存在5项其他任务的前端跟踪改动及原脏文档；本轮未审核其功能、未改动／暂存／回滚。后端独立实验结果不能用于认定这些前端改动通过。该时点可称“依赖实验与审核证据就绪，联合验证／风险裁定待办”；随后联合技术验证见页首链接，正式接受与风险裁定仍待办，不能称“发布就绪”。
