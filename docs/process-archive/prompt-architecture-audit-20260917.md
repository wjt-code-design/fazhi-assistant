# 法智项目 LLM 提示词架构评估报告

> 日期：2026-09-17  
> 视角：大语言模型提示词架构师  
> 模式：只读分析，未修改任何代码或文件  
> 范围：backend/ 全部 LLM 调用点（9 处）+ 前端零提示词

---

## 一、提示词资产总览

### 1.1 资产分布（散落 5 个文件，无集中注册表）

| # | 文件 | 行号 | 常量名 | 作用 | 输出形态 |
|---|------|------|--------|------|----------|
| 1 | `prompts.py` | 12-40 | `SYSTEM_BASE` | 普通法律咨询基底 | 自由文本 |
| 2 | `prompts.py` | 45-57 | `SYSTEM_STUDY` | 学习辅助（法考题解析）基底 | 自由文本 |
| 3 | `prompts.py` | 60-68 | `SYSTEM_CHEATING` | 作弊请求拒绝+释法 | 自由文本 |
| 4 | `prompts.py` | 71-79 | `OUTPUT_FORMAT_RULE` | 禁 LaTeX/markdown/金额符号 | 自由文本后缀 |
| 5 | `prompts.py` | 82-88 | `IMAGE_GUIDANCE` | 图片分析要求 | 自由文本后缀 |
| 6 | `prompts.py` | 93-98 | `_EXAM_TYPE_SUFFIX` | 法考题型判定（单选/多选/不定项/unknown） | 自由文本后缀 |
| 7 | `prompts.py` | 105-115 | `_EXAM_VERDICT_RULE` | 法考判断规则（五条口径） | 自由文本后缀 |
| 8 | `prompts.py` | 131-154 | `AGENT_WRITER_SYSTEM` | Agent 受限起草器（JSON） | 严格 JSON |
| 9 | `prompts.py` | 160-168 | `SYSTEM_CONTRACT_REVIEW` | 合同风险评估模板 | 自由文本后缀 |
| 10 | `prompts.py` | 173-178 | `SYSTEM_CONTRACT_FOLLOWUP` | 合同追问 | 自由文本后缀 |
| 11 | `prompts.py` | 181-187 | `CONTRACT_CLARIFY_PROMPT` | 合同澄清信息收集 | 自由文本 |
| 12 | `domain_rules.py` | 321-330 | `CITATION_SELECTION_RULE` | 引用选择规则 | 自由文本后缀 |
| 13 | `agent/runtime.py` | 62-76 | `_ISSUE_SYSTEM_PROMPT` | 争点分解器（JSON） | 严格 JSON |
| 14 | `agent/runtime.py` | 78-99 | `_PLANNER_SYSTEM_PROMPT` | 受限 Planner（JSON） | 严格 JSON |
| 15 | `query_rewrite.py` | 43-52 | `_SYSTEM` | 检索查询改写（JSON） | 严格 JSON |
| 16 | `memory.py` | 73-77 | 对话摘要器 | 增量压缩 | 自由文本 |
| 17 | `memory.py` | 108-110 | `rewrite_query` | 指代消解改写 | 自由文本 |
| 18 | `multimodal.py` | 106-109 | `AUDIO_PROMPT` | 语音转写 | 自由文本 |
| 19 | `multimodal.py` | 139-144 | `describe_image` | 图片描述/合同转写 | 自由文本 |

### 1.2 组装入口

| 入口 | 文件:行号 | 逻辑 |
|------|-----------|------|
| Fast Path 主回答 | `main.py:429 _build_messages` | 按 intent 选基底 → 加题型后缀 → 加格式规则 → 加引用规则 → 加图片引导 → 加摘要 → 拼 context_block + user_text |
| 合同首轮 | `main.py:546 _contract_messages` | SYSTEM_BASE + SYSTEM_CONTRACT_REVIEW + 风险等级 + 截断提示 |
| 合同追问 | `main.py:528-543` | SYSTEM_BASE + SYSTEM_CONTRACT_FOLLOWUP + 历史 + 追问 |
| Agent 三角色 | `agent/runtime.py` / `agent/writer.py:810` | 各自独立调用，共用 AGENT_WRITER_SYSTEM |

---

## 二、组织方式评估

### 2.1 现状

```
prompts.py          ← 主体集中（19 个常量中的 12 个）
domain_rules.py     ← CITATION_SELECTION_RULE 藏在领域规则里
agent/runtime.py    ← _ISSUE_SYSTEM_PROMPT + _PLANNER_SYSTEM_PROMPT 硬编码
query_rewrite.py    ← _SYSTEM 局部定义
memory.py           ← 两处内联提示词
multimodal.py       ← 两处内联提示词
```

### 2.2 评估

| 维度 | 评分 | 依据 |
|------|------|------|
| 集中度 | ⚠️ 中低 | 主体在 `prompts.py`，但 7 个提示词散落在其他 4 个文件，无注册表统一索引 |
| 可发现性 | ⚠️ 低 | `domain_rules.py:321` 藏了一条提示词，命名不含 PROMPT 关键词，极易漏审 |
| 版本管理 | ❌ 无 | 无版本号、无变更日志、无回滚机制。改提示词=改字符串常量，无法追溯历史 |
| 可测试性 | ⚠️ 中 | 有 `test_agent_prompt_contracts.py` 契约测试，但全是 `token in PROMPT` 子串断言——防删字段，不防语义漂移 |
| 可扩展性 | ⚠️ 低 | 新意图=新 `SYSTEM_` 常量+新 `if` 分支；新工具=改 Planner 提示词+改 gateway。无模板引擎，无插件机制 |

---

## 三、任务类型匹配度

### 3.1 调用点 × 任务类型 × 策略匹配

| 调用点 | 任务类型 | 当前策略 | 模型 | 匹配度 | 依据 |
|--------|----------|----------|------|--------|------|
| Fast Path 主回答 | 角色扮演+指令型 | 零样本，10条指令拼接 | qwen3.7-plus | ⚠️ 中 | 指令过多（10条）且存在冲突（第1条允许拒答 vs 第7/9条禁拒答），模型注意力分散 |
| 合同首轮 | 模板填空 | 零样本+模板（①结论②风险清单③解读） | qwen3.7-plus | ✅ 高 | 模板明确，输出结构化，与任务匹配 |
| 合同追问 | 上下文问答 | 零样本+历史+追问 | qwen3.7-plus | ✅ 高 | 有 FOLLOWUP 专用提示词，带历史 Q&A |
| 语音转写 | 格式转换 | 零样本（AUDIO_PROMPT） | qwen3-vl | ✅ 高 | 任务简单，提示词简洁 |
| 图片描述 | 视觉理解 | 零样本（describe_image） | qwen3-vl | ⚠️ 中 | 单次调用，按内容自路由（合同转写 vs 普通描述），无 few-shot |
| 对话摘要 | 压缩 | 零样本（memory.py:73） | qwen3.7-plus | ✅ 高 | 增量压缩，SUMMARY_MAX=400 字 |
| 查询改写 | 改写 | 零样本（query_rewrite.py:43） | qwen3.7-plus | ⚠️ 中 | 默认关闭，已否证（真实路径救回 2~3 < DoD 4） |
| Agent 争点分解 | 严格 JSON 输出 | 零样本+schema 描述 | qwen3.7-plus | ⚠️ 中低 | schema 描述靠自然语言，无 JSON Schema 约束，模型易猜错字段名 |
| Agent Planner | 严格 JSON 决策 | 零样本+schema 描述+示例 | qwen3.7-plus | ⚠️ 中 | 有示例但 ask_user 三段摇摆（允许→禁止→用法） |
| Agent Writer | 严格 JSON 起草 | 零样本+schema 描述 | qwen3.7-plus | ⚠️ 中低 | 条件化论述要求复杂，模型理解不稳定 |

### 3.2 关键发现

1. **Fast Path 占 100% 生产流量**，但提示词质量最不稳定（10 条指令+冲突+编号错序 1..6,7,9,8,10）
2. **Agent Path 生产零流量**（`agent_enabled=False`），但提示词设计最精细（严格 JSON+schema 描述+示例）
3. **资源错配**：精力投入与流量分布成反比

---

## 四、上下文管理策略评估

### 4.1 现状

| 组件 | 实现 | 位置 |
|------|------|------|
| 上下文窗口 | summary + 最近 RECENT_K=6 条原文 | `memory.py:15` |
| 压缩触发 | 双阈值：轮次>12 或 (summary+recent)字符>6000 | `memory.py:46-51` |
| 压缩方式 | 增量：只把"刚滑出窗口的旧消息"合并进摘要 | `memory.py:71-84` |
| 摘要上限 | SUMMARY_MAX=400 字 | `memory.py:18` |
| 历史图片 | 用视觉描述代替裸 [图片] | `main.py:449-452` |
| 摘要注入位置 | system 尾部（`main.py:444-445`） | ⚠️ |
| context_block | user message 首部（`main.py:461-464`） | ✅ |

### 4.2 评估

| 维度 | 评分 | 依据 |
|------|------|------|
| 窗口设计 | ✅ 合理 | summary+recent 经典模式，RECENT_K=6 覆盖典型多轮 |
| 压缩策略 | ✅ 合理 | 增量压缩避免重复劳动，双阈值兼顾轮次和字符 |
| 摘要注入位置 | ⚠️ 存疑 | 摘要塞进 system 尾部（`main.py:444-445`），而非 user message。system message 是"角色设定"，摘要属于"对话事实"，混在一起会模糊角色边界 |
| 历史图片处理 | ✅ 合理 | 用描述替代裸标记，保持后续轮次可见 |
| 失败处理 | ✅ 合理 | 压缩失败不推进 summary_upto，下次重试 |

---

## 五、可扩展性评估

### 5.1 新增意图

```
现状流程：
1. prompts.py 加 SYSTEM_XXX 常量
2. main.py:_build_messages 加 if intent == "xxx" 分支
3. （可选）domain_rules.py 加配套规则
4. 测试：手动写断言

问题：
- main.py 已 2528 行，_build_messages 已 43 行
- 每加一个意图，if 分支多一层，可读性下降
- 无意图注册表，无法枚举全部意图
```

### 5.2 新增工具

```
现状流程：
1. tools/gateway.py 加 ToolPolicy
2. agent/runtime.py:_PLANNER_SYSTEM_PROMPT 加工具描述
3. tests/test_agent_prompt_contracts.py 加 _TOOL_ARGS_FIELDS 条目

问题：
- 提示词与代码两处维护，易不同步
- 契约测试只查子串存在，不查语义正确
```

### 5.3 评分

| 维度 | 评分 | 依据 |
|------|------|------|
| 新意图扩展 | ⚠️ 中 | 可加但无框架支撑，if 分支累积 |
| 新工具扩展 | ⚠️ 中 | 提示词+代码双维护，契约测试保底 |
| 跨模型扩展 | ❌ 低 | 无跨模型兼容性测试，temperature 无配置项 |
| 版本回滚 | ❌ 无 | 无版本号，无变更日志 |

---

## 六、关键问题（按严重度排序）

### S1. 全链路零采样参数治理

- **位置**：`llm_registry.py` 的 `ChatOpenAI` 构造
- **现状**：`temperature` 全仓只出现在 `scripts/_judge.py`(judge=0)、`gen_qwen_cases.py`(0.7)、测试 mock；生产 9 个调用点全部走 SDK/服务端默认
- **影响**：与 `PLANNER_PARSE_ERROR`、writer 生成段抖动症状同构
- **根因**：`settings.py` 无 temperature 配置项 → 调采样/推理参数只能改 `llm_registry.py`

### S2. SYSTEM_BASE 指令自相矛盾

- **位置**：`prompts.py:15`（第1条允许「无法完整回答」）vs `:27-32`（第7/9条禁检索范围措辞+严禁拒答）
- **现状**：编号实为 1..6,7,9,8,10（错序）；第7条末段与第9条几乎重复
- **影响**：模型同时收到允许拒答和禁止拒答的指令，行为不稳定

### S3. OUTPUT_FORMAT_RULE 自指悖论

- **位置**：`prompts.py:76-78`
- **现状**：为禁用 `**` 与 `$` 必在正文写出它们 → 自指悖论，弱化禁令
- **影响**：格式规则自身违反格式规则

### S4. Planner ask_user 三段摇摆

- **位置**：`runtime.py:80-95`
- **现状**：允许 ask_user → 禁止 ask_user 工具调用 → 又描述 ask_user 用法
- **影响**：模型同时收到允许/禁止/用法三条指令

### S5. 无版本管理

- **位置**：全局
- **现状**：无版本号、无变更日志、无回滚机制
- **影响**：改提示词=改字符串常量，无法追溯历史；改坏了不知道改了什么

### S6. 提示词散落多文件

- **位置**：`prompts.py`(12) + `domain_rules.py`(1) + `agent/runtime.py`(2) + `query_rewrite.py`(1) + `memory.py`(2) + `multimodal.py`(2)
- **现状**：无集中注册表，无统一索引
- **影响**：`domain_rules.py:321 CITATION_SELECTION_RULE` 藏在领域规则里，极易漏审

---

## 七、适配建议

### 7.1 短期（1-2 天，零代码改动）

| # | 建议 | 依据 |
|---|------|------|
| 1 | 修 SYSTEM_BASE 编号错序（1..6,7,9,8,10 → 1..10） | 编号错序=指令混乱的直接证据 |
| 2 | 删第7条末段与第9条的重复内容 | 重复指令浪费 token 且无增益 |
| 3 | 裁决「允许拒答 vs 禁止拒答」冲突 | 第1条允许「无法完整回答」与第7/9条禁检索范围措辞+严禁拒答直接冲突 |
| 4 | 修 OUTPUT_FORMAT_RULE 自指悖论 | 改写「禁止 ** 却在正文写出 **」的表述，改用描述式禁令 |
| 5 | 修 Planner ask_user 三段摇摆 | 统一为「ask_user 决策仅用于补足关键事实，同一会话最多两轮追问」 |

### 7.2 中期（1-2 周，需改代码）

| # | 建议 | 依据 |
|---|------|------|
| 6 | 集中注册：所有提示词移入 `prompts.py`，建立 `PROMPT_REGISTRY: dict[str, str]` | 统一索引，可发现性 |
| 7 | 版本管理：每个提示词加 `VERSION` 常量 + `CHANGELOG` 注释 | 可追溯历史，可回滚 |
| 8 | 采样参数：`llm_registry.py` 加 `temperature` 参数，`settings.py` 加配置项 | 与 PLANNER_PARSE_ERROR、writer 抖动同构 |
| 9 | 契约测试升级：从 `token in PROMPT` 子串断言 → 语义断言（JSON Schema 验证） | 防语义漂移 |
| 10 | Fast Path 格式合规基线：扫历史回答，用正则统计违规率 | 零 LLM 成本，决定投哪里 |

### 7.3 长期（1-2 月，架构升级）

| # | 建议 | 依据 |
|---|------|------|
| 11 | 提示词模板引擎：引入 Jinja2 或类似，支持变量注入、条件分支、循环 | 替代当前 `+=` 拼接，可读性+可维护性 |
| 12 | few-shot 示例库：为每个调用点维护 3-5 个高质量示例，示例与金标概念域正交 | 提升弱模型 JSON 形状遵循 |
| 13 | 评测基线：为每个调用点建立 20-30 条固定测试用例，冻结 hash | 跨阶段可比，防异集混比 |
| 14 | 跨模型兼容性测试：主要提示词在 2+ 模型上跑回归 | 防回退模型行为漂移 |

---

## 八、架构评估结论

### 8.1 总体评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 提示词质量 | ⚠️ 7/10 | 内容专业（法律引用纪律、绝对化措辞禁令、条件化论述），但有冲突和编号错序 |
| 组织方式 | ⚠️ 5/10 | 主体集中但 7 个散落其他文件，无注册表，无版本管理 |
| 任务类型匹配 | ⚠️ 6/10 | 合同/摘要/语音匹配度高，但 Fast Path 主回答指令过多+冲突 |
| 上下文管理 | ✅ 8/10 | summary+recent 经典模式，增量压缩，双阈值，设计合理 |
| 可扩展性 | ⚠️ 5/10 | 可加但无框架支撑，if 分支累积，无模板引擎 |
| 可测试性 | ⚠️ 4/10 | 有契约测试但全是子串断言，不防语义漂移 |
| 可观测性 | ❌ 3/10 | 无提示词版本日志，无 A/B 测试框架，无线上效果监控 |

### 8.2 一句话结论

> **提示词内容专业但组织散乱，上下文管理合理但可扩展性不足，可测试性薄弱且无版本管理。短期优先修冲突与编号错序，中期集中注册+采样参数+契约测试升级，长期引入模板引擎+few-shot 示例库+评测基线。**

### 8.3 关键依据

1. **生产流量分布**：Fast Path 100%，Agent Path 0%（`agent_enabled=False`）→ 优化资源应投 Fast Path
2. **提示词散落 5 文件**：`prompts.py`(12) + `domain_rules.py`(1) + `agent/runtime.py`(2) + `query_rewrite.py`(1) + `memory.py`(2) + `multimodal.py`(2) → 无集中注册
3. **契约测试全是子串断言**：`test_agent_prompt_contracts.py` 全是 `token in PROMPT` → 防删字段，不防语义漂移
4. **全链路零采样参数**：`temperature` 全仓只出现在 scripts/_judge.py(judge=0)、gen_qwen_cases.py(0.7)、测试 mock → 生产 9 个调用点走 SDK 默认
5. **SYSTEM_BASE 指令冲突**：第1条允许拒答 vs 第7/9条禁拒答 → 模型行为不稳定
6. **上下文管理设计合理**：summary+recent+增量压缩+双阈值 → 经典模式，设计合理

---

## 附录 A：提示词资产完整清单

| # | 文件 | 行号 | 常量名 | 作用 | 输出形态 | 被契约测试覆盖 |
|---|------|------|--------|------|----------|----------------|
| 1 | `prompts.py` | 12-40 | `SYSTEM_BASE` | 普通法律咨询基底 | 自由文本 | ❌ |
| 2 | `prompts.py` | 45-57 | `SYSTEM_STUDY` | 学习辅助基底 | 自由文本 | ❌ |
| 3 | `prompts.py` | 60-68 | `SYSTEM_CHEATING` | 作弊拒绝 | 自由文本 | ❌ |
| 4 | `prompts.py` | 71-79 | `OUTPUT_FORMAT_RULE` | 格式禁令 | 自由文本后缀 | ❌ |
| 5 | `prompts.py` | 82-88 | `IMAGE_GUIDANCE` | 图片分析 | 自由文本后缀 | ❌ |
| 6 | `prompts.py` | 93-98 | `_EXAM_TYPE_SUFFIX` | 题型判定 | 自由文本后缀 | ❌ |
| 7 | `prompts.py` | 105-115 | `_EXAM_VERDICT_RULE` | 判断规则 | 自由文本后缀 | ❌ |
| 8 | `prompts.py` | 131-154 | `AGENT_WRITER_SYSTEM` | 起草器 | 严格 JSON | ✅ |
| 9 | `prompts.py` | 160-168 | `SYSTEM_CONTRACT_REVIEW` | 合同评估 | 自由文本后缀 | ❌ |
| 10 | `prompts.py` | 173-178 | `SYSTEM_CONTRACT_FOLLOWUP` | 合同追问 | 自由文本后缀 | ❌ |
| 11 | `prompts.py` | 181-187 | `CONTRACT_CLARIFY_PROMPT` | 合同澄清 | 自由文本 | ❌ |
| 12 | `domain_rules.py` | 321-330 | `CITATION_SELECTION_RULE` | 引用选择 | 自由文本后缀 | ❌ |
| 13 | `agent/runtime.py` | 62-76 | `_ISSUE_SYSTEM_PROMPT` | 争点分解 | 严格 JSON | ❌ |
| 14 | `agent/runtime.py` | 78-99 | `_PLANNER_SYSTEM_PROMPT` | Planner | 严格 JSON | ✅ |
| 15 | `query_rewrite.py` | 43-52 | `_SYSTEM` | 查询改写 | 严格 JSON | ❌ |
| 16 | `memory.py` | 73-77 | 对话摘要器 | 压缩 | 自由文本 | ❌ |
| 17 | `memory.py` | 108-110 | `rewrite_query` | 指代消解 | 自由文本 | ❌ |
| 18 | `multimodal.py` | 106-109 | `AUDIO_PROMPT` | 语音转写 | 自由文本 | ❌ |
| 19 | `multimodal.py` | 139-144 | `describe_image` | 图片描述 | 自由文本 | ❌ |

**契约测试覆盖率：2/19 = 10.5%**

---

## 附录 B：评估方法

1. **只读勘察**：读取 `prompts.py`、`domain_rules.py`、`agent/runtime.py`、`agent/writer.py`、`agent/verifier.py`、`query_rewrite.py`、`memory.py`、`multimodal.py`、`main.py`、`settings.py`、`llm_registry.py`、`tests/test_agent_prompt_contracts.py`
2. **五问对抗**（vet-plan-new）：
   - 模块边界：提示词散落 5 文件，无注册表 → 边界不清晰
   - 更优解：集中注册 vs 现状散落 → 集中注册更优
   - 教训对照：`[fz]` judge 基线被缓存污染、`[oss]` 代理目标 → 须绕缓存+重复采样
   - 事实核查：生产模型 qwen3.7-plus、Agent Path 零流量 → 已核验
   - DoD：格式合规率（正则可判）+ 输出稳定性（重复采样方差）→ 可测
3. **代理目标识别**：格式合规率代理「提示词遵循度」，非「回答质量」→ 须两层 DoD

---

## 八、执行与裁决记录（2026-09-17 晚追加，grilling 对齐后执行）

### 8.1 已执行提交链（f4d908c → HEAD）

| 提交 | 内容 | 对应建议 |
|---|---|---|
| f889da3 | SYSTEM_BASE 编号/冲突裁决 + OUTPUT_FORMAT_RULE 去自指 + Planner ask_user 统一 | §7.1 #1-#5 |
| f5900b5 | 审查后 P1 修复（错例误归一）+ 4 类契约断言 | code-review 报告建议 1/3 |
| e6a94f5 | ¥ 描述化 + SYSTEM_BASE 两处星号清理 + 2 把契约锁 | §7.1 #4 残余（§7.2 #10 归因前置） |
| bbbdf00 | 合同链补齐 OUTPUT_FORMAT_RULE + CITATION_SELECTION_RULE | 本节 8.2 高危发现 |

契约测试 9 → 15（test_prompts 6→8 + test_agent_prompt_contracts 6→7；新增锁共 6 把：
编号连续性、拒答冲突裁决、OUTPUT_FORMAT_RULE 无字面符号、SYSTEM_BASE 无星号强调、
ask_user 形态边界、合同链通用规则注入）。门禁限改动文件全绿。

### 8.2 合同链只读增量审计发现（子代理审查，主审已亲验 main.py 组装点）

| # | 严重度 | 发现 | 处置 |
|---|---|---|---|
| 1 | 高 | 合同链（main.py:537/:546）漏拼 OUTPUT_FORMAT_RULE 与 CITATION_SELECTION_RULE——两规则自述「所有意图统一」，主链均拼，唯合同链缺 → 合同回答不受格式禁令与引用纪律约束 | 已修（bbbdf00）+ 源码锁 |
| 2 | 中 | CITATION_SELECTION_RULE 未注入合同链（该规则格式条款→民法典496/497 映射即合同审查场景） | 已随 #1 一并补齐 |
| 3 | 低 | CONTRACT_CLARIFY_PROMPT 分点风格「1)2)3)」与 OUTPUT_FORMAT_RULE「1.」不一致 | 不修：clarify 为零 LLM 直出字符串，不经模型，风格差异无实害 |
| 其余 | — | 任务匹配/编号完整/无自指/无矛盾：通过 | — |

### 8.3 grilling 裁决（2026-09-17 晚，Owner 拍板）

- §7.1 #4 残余（¥+星号）：**做** → e6a94f5。
- §7.2 #6 集中注册 / #7 版本常量 / #9 语义断言升级：**不做**（git 历史即版本管理；
  搬迁回归风险 > 可发现性收益；最小断言已锁住已修缺陷）——记入本节留痕。
- §7.2 #8 temperature 采样参数：**绑 Agent Path 开启前做**（零流量无实害；
  改采样参数须绕缓存+锁模型+K 次采样三项对照验证，成本前置收益未证实）。
- 格式合规复测：Owner 选「现在就复测」→ 结论见 8.4。

### 8.4 复测结果（dispatch-output/prompt-format-recheck-20260917/）

- 口径单源（import 基线 scan.CHECKS），样本 2031 → 2031（增量 0），九项数字逐项一致
  → **确定性复现通过**；尚无新增回答，修复效果验证以 backend 重启后 ≥200 条新回答的
  下次复测为准。
- 现状基线（存量，旧提示词产物）：markdown_star 34.61% / forbidden_phrases 14.33% /
  overconfident 8.47% / markdown_hash_head 4.78%，其余 ≤0.15%。

### 8.5 遗留与边界说明

- prompts.py:29「[法律名 第X条]」为故意错例模式（同条号错例），保留不清理。
- AGENT_WRITER_SYSTEM 的 `**` 是 Agent Path 结构化提示词强调（输出走校验器不进聊天 UI），
  不在清理范围。
- 快照同步义务：f889da3 → bbbdf00 四个提交待按快照推送机制同步（模板
  dispatch-output/review-package-law-20260917/）。
