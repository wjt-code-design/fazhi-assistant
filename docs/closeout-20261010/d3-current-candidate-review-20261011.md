# D-3 当前候选迁移复核与隔离整合验证（2026-10-11）

## 1. 结论和边界

**当前源码在既有新旧实装依赖组合下，补齐测试后均通过全量非 slow 回归；D-3 尚未正式落到候选，安全及干净安装验收仍未关闭。** 本报告不是上线批准，也不能替代当前 Git 对象的远端 CI。

本轮承接“审查 D-3 迁移成果，再补整合验证”。遵守此前 D-29“本轮不落”裁定：不修改候选或主仓，不安装/卸载 envB、envC 的依赖，不提交、合并、推送或部署。测试使用合成嵌入、测试自建数据库和回环边界，不调用真实模型，不读取现役配置、索引、业务库或模型缓存。额外联网操作仅为文档核验与依赖审计。

固定对象：

- 候选：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`。
- HEAD：`19e296e879ac2ffbb0a862c2c9e595d3c81c8ded`；验收快照为该 HEAD 对应工作树加本轮开始前已有的 D-34/D-14 未提交内容，不是仅验收提交树。
- 运行根：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`。
- 本轮隔离目录：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/d3-current-review-20261011`，下文简称 R。
- 原 D-3 迁移副本基线为 `9e3cfc5`，不能用其旧测试直接证明当前候选。原两份 diff 对当前候选的 `git apply --check` 通过，不等于业务验收通过。

按候选 `git ls-files` 加两份既有未跟踪测试，复制 2714 文件到 R/old 和 R/x1；不复制忽略的真实配置、库、缓存、venv。R/source-manifest.json 固定复制时字节。R/post-review-source-check.json 复核候选全部这些文件 **0 处改变**，HEAD 未动；副本修改仅涉及迁移 requirements 和五份测试，未改业务源码。

## 2. 两轴独立审查

主会话使用代码审查和代码验证流程，两个不同子代理分别审 Spec 与 Standards，并再次复核修订。属于同一工具链内的独立复核，不是真第三方审计。

### Spec

原复核两项确定发现：

1. **P2，迁移判据假绿。** `test_variant_of_reuses_roots_and_keeps_params` 仍查旧的 `model_kwargs.extra_body`；新 SDK 将值放在 `extra_body`，即使错误传入禁用 thinking 的参数，旧断言也可通过。违反原票“不许用放宽断言让门禁变绿”的要求。副本改为 `assert not v.extra_body`，保留客户端归属断言。只对 `variant_of` 注入强制 True 的变异，旧断言假绿、新断言 AssertionError、还原实现后绿；原报告 §4.5 将 R5 以“本就真”撤回的解释不能继续作为有效判据证明。
2. **P3，前端对照遗漏。** 原票要求 lint、tsc、vitest，原交付报告明确省略。本轮已在私有前端副本补齐，不将“前端没有改动”代替这些检查。

两项在**隔离副本/本轮证据**层关闭；尚未同步到候选。未发现本次 D-3 业务源码越界修改。

### Standards

原复核无确定硬违规，三项应修/观察：

1. 生命周期测试无条件导入 `_cached_*_httpx_client` 私有接口，而要求允许 `langchain-openai>=1.1.14,<2`。实证仅针对 1.7.0，不能保证整个窗口的私有 API 都兼容。落地前须固定已测解析组合或明确版本支持边界，不用吞 ImportError 凑绿。
2. 清缓存是测试隔离，不是生产同进程关闭后重建能力的证明。当前生产 `aclose` 入口只在 `main.lifespan` 退出；在**单注册表、一次应用生命周期、关闭后不重建**条件下未发现运行期关闭入口。原报告“生产不可达”须按这些条件理解，不作无条件承诺。本轮不为未要求的多生命周期场景重构资源架构。
3. 原报告未逐项写 10 个 skip。已从新旧 JUnit 核明：8 个真实 KB 用例，另 2 个帧采集开关用例。已补记录；旧基线输出不能复用为当前候选证明。

后续三处测试修订经两轴结案复核均可接受，无判据放宽、过度设计或越界 mock；私有接口版本边界仍待落地处理。

## 3. 当前源码全量红结果及副本修订

原样接收当前源码后，两栈都得到 **2014 passed / 2 failed / 10 skipped / 18 deselected**，覆盖率 86.55%，rc=1。保留 R/old-full.log、R/old-full.xml、R/x1-full.log、R/x1-full.xml，不倒改历史。

两项为 D-34 接口变化后的测试接线问题，不是只在新栈出现的业务回归：

- 日期透传测试替换整个 `_execute_agent_observing_disconnect`，绕过现有的 resume/bootstrap/fallback 接线，返回 fallback 却未准备 `pre`，最终得到 500 而非 599。副本改为只 stub 同步 `execute_agent_request`，保留真实拥有者包装；fallback 替身接收 `turn`，仍以 599 哨兵截停，仍独立断言 run 日期为 2019-01-01。
- 并发持久化测试的异常替身不接受新增 `accepted_agent_turn`，先被 TypeError 截断。副本显式接受并断言该参数为 `{}`，保留 RuntimeError 哨兵、同会话后续请求 0.5 秒上限和最终消息数 4。

初次定向修订为 1 failed / 2 passed，已保留 R/repaired-targets.log；定位接线层次后，R/repaired-targets-final.log 为 3 passed。未删除测试、添加 skip、降低阈值或改业务逻辑。

可复核补丁：

- [既有栈测试接线补丁](C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/d3-current-review-20261011/baseline-test-compatibility.patch)：两份测试，可与 D-3 独立处理。
- [迁移测试修订补丁](C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/d3-current-review-20261011/migration-tests-reviewed.patch)：三份迁移测试，包含原适配和补齐的 variant_of 判据，**只供新栈使用**。

两者都只执行过应用检查，未应用到候选。不能拿迁移测试补丁单独配旧栈，也不能只应用原 D-3 requirements diff 就宣称干净安装边界已修。

## 4. 最新隔离验收读数

| 检查 | 当前结果 | 原始证据（R 下） |
|---|---|---|
| old 非 slow 全量 | 2016 passed，10 skipped，18 deselected，rc=0，cov 86.55% | old-final.log、old-final.xml |
| x1 非 slow 全量 | 同上 | x1-final.log、x1-final.xml |
| 两栈 Ruff lint/format | 均 rc=0，format 285 文件 | old/x1-final-lint.log、old/x1-final-format.log |
| 两栈标准 mypy | 均 rc=0，74 source files | old/x1-final-types.log |
| 两栈 D-14 五脚本 mypy | 均 rc=0，5 source files | old/x1-d14-types.log |
| envC pip check | rc=0 | x1-final-pip-check.log |
| 前端 lint / tsc / vitest | 三项 rc=0，9 测试文件、83 项通过 | frontend-summary.json、frontend-lint.log、frontend-typecheck.log、frontend-vitest.log |
| CI 额外预算守卫/宿主 lint/format | 9 passed；两静态门 rc=0 | ci-budget-guard.xml、ci-budget-guard.log、ci-extra-summary.json及对应静态日志 |
| variant_of 判据变异 | 旧断言假绿、新断言咬红、原实现通过 | variant-mutation-final.log、variant-mutation-summary.json |

最终 XML 每栈 2026 tests，failures/errors=0，skipped=10；加排除的 18 项，共收集 2044。XML 起始时间为 old `2026-10-11T22:32:50.881876+08:00`、x1 `2026-10-11T22:33:03.348912+08:00`，不是结束时间。

old/x1-final-isolation-summary.json 均记录被拒外网尝试 0、被拒真实文件访问 0、子进程 53；这些计数是主测试进程审计钩子的观测，不是系统级沙箱证明。子进程继承合成配置、私有临时目录和 HF_HOME，不继承真实凭据。没有把异常被拒后吞掉的测试当零尝试。

全量使用仓库既有 FakeEmbeddings，不加载 BGE 权重。因而证明的是接口、控制流、存储、取消与隔离回归；**不证明真实语义检索质量、真实模型表现、现役 KB 兼容或部署成功**。10 skip 与 18 slow 排除不算通过。按原迁移票，本轮未构建前端、未构建镜像，未跑真实库/模型及远端 CI，因此不是全部发布门绿。

## 5. 仍需处理的依赖边界和审计

### 5.1 NumPy 干净安装边界缺失

这是当前依赖声明的**既有遗漏**，不是已证明由 LangChain 迁移引入的回归：

- 原 envC 构建先安装 envB 冻结集，再安装新 requirements，保留 numpy==1.26.4。
- 原 `d3-audit-envC-req.json` 的独立解析闭包却为 numpy==2.4.6、chromadb==0.4.24。
- 新旧 requirements 均没有 NumPy 上限；Chroma 0.4.24 元数据只要求 numpy>=1.22.5，其 api/types.py:102 在 import 期访问 `np.float_`。
- NumPy 2.0 官方已移除该属性。由源码和官方接口变更可判定上述干净解析组合有导入不兼容，不能由“审计族内零风险”推导“可以启动”。[NumPy 官方迁移指南](https://numpy.org/doc/2.0/numpy_2_0_migration_guide.html)

最小修订建议：保持 Chroma 0.4.x，不猴补第三方属性；在迁移方案明确 `numpy>=1.26.4,<2`，并固定本轮实际验证的版本组合。此约束属于建议，**尚未修改候选或副本 requirements，也未干净安装验证**。继承旧 freeze 的环境不能充当这一步证据。

### 5.2 最新实装审计仍红

本轮重新运行 envC 审计，不仅引用旧报告：

- 严格实装审计 rc=1，torch==2.13.0+cpu 未被 PyPI 审计源识别，见 R/envC-current-audit.log、audit-exit-codes.json。保留失败，不能记完整审计通过。
- 为取得诊断清单，另以非 strict 实装审计运行，**不是放宽正式门禁**；仍 rc=1，见 R/envC-partial-audit.json、envC-partial-audit.log、partial-audit-exit.json。
- 171 条依赖记录中，Chroma 2 条通报、setuptools 4 条通报（含同一主 ID 重复），合计 **6 条记录 / 4 个不同主 ID**。Chroma 为 PYSEC-2026-3813/3814，结果无 fix_versions；setuptools 为 PYSEC-2025-49、PYSEC-2026-3447，工具给出的修复版本分别为 78.1.1、83.0.0。
- 当前实装 LangChain 相关包及 langsmith 均 0 条已知通报；不保证宽版本窗口内任意组合都安全，也不覆盖跳过的 CPU torch。

本轮未升级 setuptools、未删依赖、未 ignore 通报、未改变 CI strictness。后续应在新的私有环境单独验证构建工具升级，并为 CPU wheel 的源、版本和审计覆盖取得明确证据；不能默默去掉 `+cpu` 后声称已审到这个实际 wheel。

## 6. 后续执行建议与接收条件

按最小可验证顺序推进，不引入新框架：

1. **先修当前旧栈的两份测试接线。** 基线补丁不需要迁移依赖；正式落到候选后重新固定源码并建立新的私有副本，在 envB 重跑相应测试与完整非 slow 门，不直接启动带现役配置/库的候选。副本通过不等于候选已经修好。
2. **确认解除 D-29“不落地”后再整合 D-3。** 同步 requirements 与三份新栈测试；保留 Chroma 窗口，补 NumPy 1.x 边界，以本轮已测组合为起点，不凭宽窗口或最新版本推测安全/兼容。
3. **新的私有环境做干净安装及审计。** 不改现有 envB/envC、backend/venv。固定 runtime/dev 实际解析结果、CPU torch 来源及新环境 freeze；做真实包导入、合成 Chroma 写读清理和全量代码门，审计解析轴与实装轴分别报告，升级 setuptools 前后保留红绿与兼容证据。
4. **仍红的安全门单独处置。** Chroma 风险和 CPU wheel 未覆盖不能用测试全绿抵消；若需要受限例外，须明确 Owner 风险裁定与到期/失效条件，不自动加入忽略规则。
5. **此后才做候选正式发布前复验。** 包括规定的构建/实际对象 CI、真实数据/模型验收、凭据与远端历史整合等独立待办。推送、真实库写入、风险接受和部署的授权不因本报告自动增加。

接收状态：D-3 当前代码兼容性 **隔离验证通过**；两处当前基线测试接线及一处迁移判据 **副本修订通过、候选未落**；干净安装、完整安全门、正式候选整合 **待完成**。本阶段没有因此完成。

复现入口：R/run_backend.py；以 envB 的 python.exe 运行 `old`、envC-1x 的 python.exe 运行 `x1`。调用前设 PYTHONHASHSEED=0、PYTHONDONTWRITEBYTECODE=1；runner 会清除真实环境配置、设置私有资源出口并替换嵌入模型。不要在候选直接跑这个 runner，也不要直接跑 smoke_citation_fast.py。已有最终日志不应覆盖，新复跑须给新日志/XML 名称。
