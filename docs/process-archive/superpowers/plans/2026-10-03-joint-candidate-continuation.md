# A＋B联合候选续办（2026-10-03）

本轮依据用户“你继续接手后续工作”推进仓外联合验证，不表示Owner已正式采纳B或签署D2。原单项执行书的其他权限不变。本轮单助手执行，不新增框架、服务或Git worktree：已有冻结归档是所需源码输入，用新仓外副本隔离，不修改主线。

运行根：`C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01`。
基线根：`C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b`。
单项根：`C:/Users/33393/Desktop/fazhi-risk-followup-75542ea22e9b4627a4e090cbc5c7f9aa`。

- [x] J1：核对41保护对象、38原库文件、整.env、HEAD／refs／原脏文档，登记其他助手变更；按2658对象冻结manifest复制源码。
- [x] J2：新source仅使用A版requirements三行差异。新约束从旧167项删langchain／community，setuptools换83.0.0，其余不变。只读核验现有wheel，离线创建新Python3.11 venv，显式安装pip26.2.1、setuptools83、torch2.6.0+cpu、dev需求。缺包则停并列下载单，不联网补包。
- [x] J3：实装应162分发，相对A仅setuptools变化；pip check、1690 nodeid一致、原27项定向、Ruff／format／mypy、全量非slow覆盖率≥70、公开副本24/24离线烟测。真实key与代理清空，Windows运行环境保留，数据库／临时文件／缓存隔离到新runtime。
- [x] J4：对新venv实装运行pip-audit，记录真实退出码／原始JSON／逐ID与alias连通组。不得用42−8推导新结果；torch+cpu扫描限制单列。元数据查询不是下载或模型调用；查询失败保留失败，不声称漏洞扫描完成。
- [x] J5：重核源码／实装／原库／旧公开库／模型缓存／Git保护，归档精确文件manifest与9字段值／形状扫描（正控成立），更新进度。失败文件不覆盖，其他任务文件不暂存／回滚。

明确未授权：正式采纳新依赖、D2签字或顺延、提交／合入／push／PR、写原库、真实模型请求、下载权重／换refs、部署。模型来源仍PARTIAL，本轮不重复失败的HF查询；可先生成给Owner的只读元数据收集说明。10月5日复审不变。

先验尺子使用既有1690 nodeid、27项定向、原公开法规与烟测代码，不改golden。替代方案是直接拼接单项结果，不能证明真实合用；因此只多做一套干净联合环境，不扩成整栈升级或双份评测系统。通过只称联合离线候选成立，不称发布安全或新环境已验真实rerank。

J1–J5实际结果见 [联合报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-joint-candidate.md)：162实装／165约束，全量1680通过／10跳过／18不选、85.42%，烟测24/24；新审计34行／7包／21组（有通报退出1，非安全绿灯）。J5于23:07+08完成：`evidence/delivery-verification-v2.json`通过，v2有49个内容对象／实际50文件，9字段值／形状正控成立、0命中。首个集合的PyJWT说明示例形状命中如实保留；v2仅精简明确列出的安装report说明字段，不放宽扫描规则。v2中的本文是完成勾选前快照，不改旧manifest。默认不重复本轮安装／门禁；尚未关闭的审批与模型来源见联合报告。
