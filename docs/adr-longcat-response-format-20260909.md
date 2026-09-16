# ADR：LongCat response_format=json_schema 支持验证（方案 A / V2-G6）

> 日期：2026-09-09 ｜ 验证依据：实测调 LongCat API（探测脚本）
> （dispatch-output/probe_longcat_response_format.py）
> 决策对象：是否用"模型层结构化输出"替代/辅助"生成后回喂纠错"以根治 L1 parse 失败面。

## 结论

**LongCat-2.0（base_url https://api.longcat.chat/openai）支持 OpenAI 兼容 response_format，
且 json_schema(strict) 具有真实约束力。**

| 探测 | 结果 |
|---|---|
| baseline（无 response_format） | HTTP 200，`{"n": 1}` |
| response_format=json_object | HTTP 200，`{"n": 1}` |
| **诱导输出 prose**（明确要求"不要JSON"） | **仍返回 `{"n": 1}`** → schema 强制 JSON |
| **诱导输出错误字段**（要求 n:"hello"） | **仍返回 `{"n": 1}`** → schema 强制类型 |

## 证据边界（诚实声明）

1. 探测用**单产出 JSON 对象**的简单 schema；planner 是**多 kind 联合判别**的复杂 schema，
   其约束力需接入后以真实 prompt/schema 实测（下一步）。
2. `response_format` 约束**格式与字段类型，不约束内容正确性**（如编造 issue_id/法条号）。
   因此下游 `_strict_json` + schema 校验 + verifier + fail-closed 一律保留，不因本验证放宽任何安全边界。
3. 本验证基于极小 token（3+2 次短调用），费用可忽略；key 未落盘。

## 决策

- 采纳方案 A 路线：为 planner/decomposer/writer 引入 `response_format=json_schema`
  （按各自输出 schema 构造），作为 L1 parse 失败面的根治尝试。
- 实施顺序（最小步）：先只给 **planner** 接 json_schema 并**单题验证**（成本最低），
  parse 降即全量 run-10；不降则回滚该改动并转向 plan-then-execute。
- **不改动**：`_strict_json`、回喂重试、`_PLANNER_SYSTEM_PROMPT`（F3 教训：prompt 文本不动），
  只新增请求层 response_format 参数（transport/adapter 侧）。

## 接入实测结论（2026-09-09，补写）

对 ADR "简单 schema 的约束力需接入后以真实 prompt/schema 实测"之边界完成实测：

| 实测项 | 结果 |
|---|---|
| 直接调用 `PlanDecision.model_json_schema()`（初版实现） | **抛 AttributeError 被静默吞掉** → 回退普通调用，方案 A 从未真正启用 |
| `TypeAdapter(PlanDecision).json_schema()`（判别联合顶层） | 可用；LongCat 输出 kind/issue_id/tool_name 正确 |
| `args` 字段（`SerializeAsAny[BaseModel]` 泛型） | schema 编码为空对象 → 模型只能输出 `args:{}`，parse 校验失败 |
| **args 注入具体工具输入联合**（请求层改 schema，不动推理类型） | LongCat 正确填出 `{"query":"…","k":4}`，`parse_plan_decision` 通过 |
| 生产链路差异：ChatOpenAI `streaming=True` + bind | 实测通过，输出完整合法决策 |

**实现要点（已并入 runtime.py）**：
- 新函数 `_planner_response_schema()`：`TypeAdapter(PlanDecision).json_schema()` +
  把 `$defs["ToolCallDecision"].properties.args` 替换为
  `RetrieveLawsInput | LookupArticleInput | ContractInput | RetrieveMemoryInput` 的 anyOf $ref。
- fail-safe 保留：bind/schema/调用任何失败一律静默回退普通 invoke（验证脚本同目录
  probe_longcat_planner_bind.py / probe_longcat_args_inject.py 可复现）。
- 安全边界不变：回喂重试、parse_plan_decision 严格校验、gateway policy 校验全部保留。

## 参考

- 探测脚本：dispatch-output/probe_longcat_response_format.py（含 5 次调用，可复现）
- 接入验证：dispatch-output/probe_longcat_planner_bind.py（bind 完整链路）、
  dispatch-output/probe_longcat_args_inject.py（args 注入对照）
- 上游：V2 执行书 §4 G6（docs/v2-optimization-execution-taskbook-20260909.md）