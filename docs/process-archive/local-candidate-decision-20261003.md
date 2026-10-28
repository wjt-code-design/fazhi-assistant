# 本地候选裁定材料与启动凭据说明（2026-10-03）

## 当前结论

审核与联合续报（2026-10-03）：A／B单项及随后全新仓外A＋B联合离线验证已通过，见 [审核报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-independent-review.md) 与 [联合报告](C:/Users/33393/Desktop/ai-legal-helper/docs/work-report-20261003-joint-candidate.md)。B正式采纳尚未决定。**本材料下述裁定对象仍是10月2日原四文件候选**，不能用原选项直接签署新的依赖集合；本段不代签或延期。

新增联合实验仅作裁定输入：根 `C:/Users/33393/Desktop/fazhi-joint-candidate-20261003-ac701f4a880441b5a453b1b7cbb06f01`；requirements SHA-256 `594b9e664f1d63a22180ef6dbdf46ee73948a5d0a938d835e1939c9b86c48d4c`，165约束SHA-256 `e19cd1ef8ecb7c12397a1a72934c727d6c553467b60fc1859715c010b0ab249c`；实装162分发见 `evidence/environment-verification.json`，新审计34行／7包／21组、torch+cpu跳过见 `evidence/joint-results.json`／`installed-audit.json`。24/24为离线烟测，不是新的真实rerank结果。选定联合对象后须另明确适用用途／风险／证据及D2选择，不沿用旧57行扫描或旧真实模型验收；2026-10-05复审不变。

续办补充：模型来源状态仍PARTIAL；新增依赖精简核查、失败探针及分案见 [依赖风险最小处理分案](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-03-dependency-risk-followup.md)。没有因此代签风险或升级已验候选。旧86文件集合保留上一检查点快照，不含本补充及新增分案。

候选实验和限定真实 rerank 已有证据；D2／Windows 有限本地接受尚未签署。建议只讨论是否接受下述受限本地用途，暂不将候选认定为可以发布。最迟复审日期仍为 **2026-10-05**，不得自动续期。

对象固定为主线 `902e2d161e67100ed6d267a08c393538a0abe109` 加四文件增量：`backend/requirements.txt`、`backend/knowledge_service.py`、`backend/tests/test_pdf_upload.py`、`backend/tests/test_upload_rate_limit.py`。候选根：`C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b`；FastAPI 0.141.1、pypdf 6.19.0，独立 Windows Python 3.11.0 环境。新代码、依赖、模型或数据变更不能沿用本次裁定。

## 可核查的证据

以下路径均相对候选根的 `evidence`；历史结果保留实际执行时间，本日没有重跑全套测试或审计。

| 项目 | 证据及含义 |
|---|---|
| 依赖与源码 | `final-rerank-declaration-verification.json`、`final-rerank-after-candidate-source-verification.json`：27 直接需求／167 约束满足，源码四处白名单差异 |
| 功能回归 | `pdf619-evidence-summary.json`：10 月 2 日后端 1680 passed／10 skipped／18 deselected，覆盖率 85.42%；前端结果及复用边界见主报告 §9 |
| 真实 rerank | `final-rerank-real-summary.json`：10 月 2 日最终环境 7 次 HTTP 200、7/7 有效重排、24/24 快速断言；公开法规 1528 条，非生成问答验收 |
| 启动配置 | `startup-credential-check-20261003.json`：10 月 3 日真实 Settings／dotenv 离线核对，6 项检查通过；无应用启动、模型加载或 HTTP 请求 |
| 漏洞审计 | `pdf619-current-audit-summary.json`：10 月 2 日实装扫描 57 原始行／10 包／32 别名组；torch CPU 构建被跳过，另有上游精确版本查询，不能签成无漏洞 |
| 模型来源 | `bge-provenance-preflight.json`：PARTIAL；部分权重有官方指针对照，小文件与默认 BIN 精确 revision 的完整上游核验未完成 |

`pdf619-current-risks.md` 是 10 月 2 日 17 时的历史快照，其中“最终环境 rerank 尚未执行”已被 23 时结果取代。引用该文件的漏洞讨论时，不能同时沿用其旧进度判断。

## 启动凭据：根因与已验证处理

产品 `main.py` 在导入应用模块前执行 `load_dotenv()`，默认不覆盖已有进程变量；`settings.py` 导入时构造单例。Windows 系统变量修改不会自动刷新已运行的父进程或已有 Settings 对象。

**本日采样已变化：当前工具子进程继承的 RERANK_API_KEY 存在且与 Windows 系统主值一致；backend/.env 的值仍不同。** 因而不能继续将“当前进程缺少新 key”写成现状。新进程在 Settings 创建前取得正确变量即可，不需要修改产品优先级、自动读取注册表或把新 key 写回 `.env`。

在未来明确要启动的 PowerShell 窗口中，可先执行下段准备代码。它只设置当前进程变量，不启动服务；应在载入任何应用模块之前执行。缺值／异常格式直接停止，不回退到文件或备用 key。不要打印变量、打开命令追踪或导出全量环境。

```powershell
$rerankStartupKey = [Environment]::GetEnvironmentVariable('RERANK_API_KEY', 'Machine')
if ([string]::IsNullOrEmpty($rerankStartupKey) -or
    $rerankStartupKey -match '[^\x21-\x7E]' -or
    $rerankStartupKey.Contains('${') -or
    $rerankStartupKey.Contains('%') -or
    $rerankStartupKey.StartsWith('Bearer ', [StringComparison]::OrdinalIgnoreCase)) {
    throw '系统级 rerank 主凭据缺失或格式不符合要求；停止启动。'
}
[Environment]::SetEnvironmentVariable('RERANK_API_KEY', $rerankStartupKey, 'Process')
Remove-Variable rerankStartupKey
```

这段准备不改变本次调用许可，也不自动恢复真实库服务。已有应用进程仍须在其运行任务允许的窗口重启才能取得新值；本轮没有停止其他进程。容器不会因宿主机这段操作自动得到变量，未来部署另按容器配置验证。

离线探针覆盖：进程缺值时读文件、旧进程值优先、空字符串阻止文件值补入、显式新值优先、已构造 Settings 不自动刷新、真实系统主值经真实 `.env` 加载后保留。探针只导入 Settings；完整 `main` 启动、lifespan、服务健康、生产默认重试和外部 API 认证不属于本次证明。真实 key 的实际认证沿用 10 月 2 日已批准单轮证据。

初版探针清空了 Windows 运行时环境，导入依赖发生 OSError；保留初版和脱敏失败 JSON。v2 仅隔离应用配置字段后通过，未改产品文件。输出不包含 key 原文、长度或 key 哈希。

## 风险裁定对象

| 剩余项 | 事实与建议边界 | 关闭条件 |
|---|---|---|
| LangChain／LangSmith／Chroma 等已知通报 | 静态路径分析不能代替漏洞修复；仅限已核查公开数据、嵌入式库、关闭追踪的隔离实验 | 独立升级分案、兼容回归与新审计，或 Owner 明确接受具体受限用途 |
| torch／ST／Transformers 与模型来源 | 官方文件哈希不消除依赖漏洞，缓存来源仍 PARTIAL；当前限制不是已证明安全 | 完整模型来源核对，并逐条复核相关风险；不自动下载、换模型或改缓存引用 |
| setuptools 构建风险 | 已有离线 wheel 路径不覆盖任意 sdist／Linux 镜像构建 | 在未来构建环境升级和验证，不以本地 wheel 安装结果签未来环境 |
| 普通启动与界面 | 配置读取问题已有最小处理方式，完整应用启动和浏览器流程未验 | 指向独立数据库和公开库的启动／界面验收；是否启用真实生成另定明确范围 |
| Linux／远端 CI | Windows 本地结果无法替代 | 具备环境后执行同源检查；推送和触发远端流程维持原边界 |
| 发布历史凭据 | ADMIN_PASSWORD 历史处置和推送前复扫仍是发布前置 | 按发布阶段完成凭据处置、历史／待推内容检查；本材料不授权推送 |

建议的可接受用途仅为：单机 Windows、独立环境、既有批准公开法规、受控离线开发／评审。接受后仍禁止自动追加真实模型调用、导入私有数据、开放网络服务、提交／合入／push 或部署。未来每次实质变更需重新评估相应证据。

Owner 可选择：

- **A：接受上述受限本地用途至 2026-10-05 复审。** 明确承认未关闭的依赖通报、模型来源 PARTIAL 和未验范围；仅关闭 D2／Windows 有限接受，不能把完整发布验收写成通过。
- **B：暂不接受，先按风险分案继续处理。** 保持“实验材料就绪、接受待裁”；优先模型来源核验与依赖升级分案，不重复已通过的 rerank 轮次。

裁定状态：**待 Owner 选择；助手未代签。** 上述 A／B 仅为可审阅选项，本文生成或用户普通“继续”均不视为已签署具体风险接受。

## 后续顺序与交付

1. 完成 Owner 裁定；如选择 B，优先补来源证据和最小依赖升级方案。
2. 本地候选正式接受后，再准备四文件增量的本地提交／合入审阅；保留无关脏文件。
3. 启动和浏览器验收使用独立数据库／公开库，真实生成的模型、数据与调用预算单独明确。
4. 远端历史／凭据检查、CI 和服务器选型进入发布准备；服务器未确定，不安排部署。

新增交付集合为候选根 `checkpoint-closeout-20261003`：保留旧 72 文件检查点原样，按原清单复制内容并加入本轮结果／裁定材料；新集合有独立 manifest 和完整字段值／形状扫描。它是本地评审材料，不是包含源码、环境和数据库的自包含运行包，也不代表可以公开。真实状态以 `evidence/closeout-delivery-20261003.json` 为准；该文件不存在或未通过时不能声明交付扫描完成。旧归档含历史 HNSW，仍不整目录转发。
