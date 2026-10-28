# 第六、七轮：混合引用问句进入事实账本的 P1 修复

日期：2026-10-23。承接同日 `2026-10-23-round6-round7-integration-and-live-quality-followup.md` 与 `2026-10-23-round6-round7-second-check.md`；不覆盖两份旧报告。用户已授权修复与回归；按旧报告要求，**未提交、未推送、未部署**。

## 结论

二次复核的 P1（混合引用把疑问句写成 `confidence=1.0` 的确认事实）已在工作树修复，并用两个可复现输入先红后绿。Q1（引用有效但结论支持不足）、Q2（覆盖声明矛盾）、Q4（冗余追问/等待）仍未关闭；Q3 仅关闭本次 P1 入口，混合句的完整语义边界仍需真实样本。

## 修改

- [runtime.py](file:///c:/Users/33393/Desktop/ai-legal-helper/backend/agent/runtime.py#L750-L760)：事实分句扩展不再在找不到来源分句时回退为原始 `quote`。
  - 先从可信原文取包含 `quote` 的事实分句；
  - 若没有（混合引用跨分句），只从 `quote` 自身取**陈述分句**，且必须能在可信原文中定位；
  - 若仍没有（如裸疑问词「工具」），跳过该事实，不写入账本。
- [test_fact_coverage_round6.py](file:///c:/Users/33393/Desktop/ai-legal-helper/backend/tests/test_fact_coverage_round6.py#L94-L109)：新增 3 条回归：
  1. 混合引用 `双方签了保证合同，我是否变成一般保证` → 只保留 `双方签了保证合同`；
  2. 疑问分句短片段 `工具`（来源句「工具由谁提供？」）→ 不进入事实账本；
  3. 绿色对照：同一 `工具` 落在陈述句「工具由我提供」→ 扩展为完整陈述，不扩大过滤。

## 红绿证据

- 先临时还原旧回退 `... or [quote]`：`pytest tests/test_fact_coverage_round6.py -k "mixed_quote or short_fragment"` → **2 failed, 1 passed**（失败输出分别为整条混合引用、裸 `工具` 被写入）。
- 恢复修复后：`pytest tests/test_fact_coverage_round6.py tests/test_agent_runtime.py tests/test_agent_issue_scope_round7.py -q` → **74 passed**。
- `ruff check` 与 `ruff format --check`（两个改动文件）→ 通过。

## 回归范围与未复现项

- 按旧报告的 14 个相关文件在同一解释器跑：**348 passed / 16 failed**，失败全部落在 `test_stream_cancellation.py`（`FieldInfo`/Pydantic 测试替身、`_ERROR_NO_RESPONSE`）与 `test_cancel_boundaries.py`（时序等待）。
- 在干净工作树 `.worktrees/w08-p0fix-070f45a4`（不含本轮 round6/7 未提交改动）只跑这两个失败文件：**35 passed / 20 failed**，同类失败仍存在。
- 因此这 16 项不是本次事实引用修复引入；当前解释器环境与旧报告「361 passed」的依赖/替身状态不同，**不能把 361 passed 当作当前新鲜结果引用**。
- 未重跑真实服务样本；本次只做纯函数/ASGI 组件级回归，不宣称回答质量已改善。

## 仍未关闭

1. **Q1 条文支持不足**：需要审查 verifier 对「支持」的定义与证据补充路径，先冻结失败输出为反例，再设计独立判据；不继续堆提示词或以关键词黑名单代替法律适用审查。
2. **Q2 覆盖声明矛盾**：正文解释六个月规则、末尾仍称该争点未覆盖；另需修正「模型误抄证据 ID」与「检索未提供」的失败归因。
3. **Q4 冗余追问/等待**：分句覆盖规则与用户意图冲突、范围选择追问、同步模型调用不可强制停止；需独立验证后再改。
4. **Q3 剩余边界**：本次只关闭混合引用的两个入口；包含事实与问题的其他混合句仍需人工样本检查。
5. **提交/推送/部署**：按旧报告要求等待授权；当前改动仅在工作树。注意：`runtime.py` 在本轮开始前已含 round6/7 在途改动（本文件只是其中事实扩展一段），`main.py`/`prompts.py` 也仍未提交；单独 `git add runtime.py` 会连带提交未审改动，故未做任何暂存。

## 复现命令

```powershell
# 反例（旧逻辑应红）
python -m pytest backend/tests/test_fact_coverage_round6.py -q -k "mixed_quote or short_fragment"
# 修复后定向回归
python -m pytest backend/tests/test_fact_coverage_round6.py backend/tests/test_agent_runtime.py backend/tests/test_agent_issue_scope_round7.py -q
```
