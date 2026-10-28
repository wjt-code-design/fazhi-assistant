# 第七轮：质量约束修复与离线复核记录

日期：2026-10-22。范围：提示词契约与既有回答复核；不替代真实 Agent 生成测评。

## 已实施

修改 `backend/prompts.py` 的现有规则，没有增加新生成阶段或模型调用：

- 快车道 SYSTEM_BASE：区分用户事实与典型情形/假设；未知信息须追问或条件化分析，不从单个行为直接认定过错强度或比例。
- 结论卡保留正文中的前提、例外和待确认条件，避免把条件判断缩写成确定结论。
- 引用核对从条号/内容扩展到适用前提及所支持的具体结论，不以主题相近条文替代依据。
- 收紧第 9 条：去掉“直接基于最相关条文作答并引用”的强制尾句；改为支持部分作答，其余说明具体尚不能确定的结论及需补充的事实/依据。保留既有不暴露检索内部细节的表达约束，不把检索不足说成法律没有规定。
- Agent 的 AGENT_WRITER_SYSTEM 在同一个文件，补齐相同的事实、条件、引用纪律。JSON schema、Fact/Evidence 同争点绑定、unknown facts 逐字复制及禁止新增数字等契约保持原样。

这些是模型输入约束修复，**不是确定性语义验证器**。不能仅凭提示词存在宣称模型已经不会犯错；没有加入基于关键词封堵个案的后处理。

## 回归证据

新增 `backend/tests/test_answer_quality_prompt_round7.py`，明确只测提示词契约，不证明回答质量。

先于生产修改执行：7 失败、1 通过。失败点为缺失事实/假设边界、摘要条件、引用适用约束和旧第 9 条冲突。保留的 Agent 结构边界检查先已通过。

修改后执行（工作目录 backend）：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& venv/Scripts/python.exe -B -m pytest --noconftest -q tests/test_answer_quality_prompt_round7.py tests/test_prompts.py tests/test_agent_prompt_contracts.py -o addopts= -p no:cacheprovider --tb=short
```

结果：**24 passed in 1.98s，退出 0**。使用 `--noconftest` 避免应用级 conftest 自动导入 main 和初始化隔离 Chroma；这些文件直接导入纯字符串 prompts 模块，另有少量只读源码契约检查。

另执行 `backend/venv/Scripts/python.exe -B -m ruff check backend/prompts.py backend/tests/test_answer_quality_prompt_round7.py`，退出 0，All checks passed。

## 当前六个回答的内容复核

对象仍是另一位助手先前生成的 `dispatch-output/quality-eval-20261021/answers` 六份快车道样本，**均不是本次提示词修改后的输出**。

| 样本 | 本次观察 | 判定 |
| --- | --- | --- |
| C08 | 当前结论卡已分别列出保证方式与保证期间的条件 | 旧 Q7-01 未在本样本重现；不证明多次采样稳定通过 |
| C04 | 当前无合同编通则解释第六十五条错配；仍只泛称定金比例限制，对并用问题保留待判断 | 旧 Q7-03 未重现；完整性仍有限 |
| N01 | 第 6、38 行将未系安全绳直接称为“重大过错”；第 14 行虽称“一般自带工具”，仍需把关系定性建立在本案已知事实之上 | 过强责任判断仍有依据不足风险；新增提示词覆盖该失败类型，效果待真实生成验证 |
| N03 | “个别裁判可能认可”仍没有具体裁判来源 | 待核，不直接判定法律结论错误 |
| C02 | 没有未经核实的确定总额；时效仍主要留给进一步咨询 | 数字表达克制，完整性待补，不给整体通过 |
| H05 | 旧“该条将证明责任分配”直接说法已删除；仍有保险人需证明的论证 | 旧表述改善，举证规则与全部法律结论未在本轮重新逐条权威核验 |

不重用旧“93 分”，不计算六个风险样本的总体合格率，也不将其作为 Agent 链路成绩。

## 交付限制与后续验收

真实模型行为尚未验证。需要主任务以安全隔离环境补充两条路径的实际调用：快车道使用现有驱动，Agent 使用真实 Agent 请求/Writer 调用链，而非将快车道样本改名为 Agent。

最小对照应覆盖：未知事实与已确认事实；保证方式与期间分别变化；过错事实不充分；条文主题相近但适用前提不同；正文条件在摘要中保留。记录全部失败、输入与输出哈希、模型/提示词版本，不能只保留表现最好的回答。

本子任务未读环境密钥、未调用真实模型、未启动服务、未访问业务数据库、未修改运行配置或旧报告。只修改 prompts.py，新增专属测试和本记录。

证据目录：`C:/Users/33393/.codex/visualizations/2026/10/18/01a14fe1-dd41-7e83-a8f6-c4c2d27b6be7/fazhi-round7-quality-remediation`。含 `answer-manifest.json`、六份回答副本、`result.json`。当前基线及提示词哈希见 result.json；其他代理同时修改的 runtime/service/main 不属于本记录的独立验收范围。
