# 审查计划书：方案 B 执行弧 + rerank 集成（2026-09-07）

## 1. 审查范围（固定点）

- 基点：`c53677a^`（上次已审查状态：阶段 C 终态）
- 终点：`HEAD`（`4eef8a0`）
- 提交清单：`git log c53677a^..HEAD --oneline`（含 rerank 集成 2 提交、008 评测 2 提交、
  方案 B 6 提交、治理文档 2 提交）
- 代码审查聚焦文件（排除证据/诊断数据 bulk）：
  - `backend/scripts/eval_agent.py`（v1.2.0 口径变更）
  - `backend/scripts/capture_eval.py`（题数下限、HTTPException 重试）
  - `backend/scripts/check_agent_release.py`（政策 v2 容差）
  - `backend/retrieval.py`（SiliconFlow 分支、门禁 key 回退）
  - `backend/settings.py`、`backend/agent/service.py`（pre-run 失败日志）
  - `backend/tests/test_rerank_siliconflow.py`、`test_capture_eval.py`、
    `test_eval_agent.py`、`test_agent_release_check.py`、`test_agent_prompt_contracts.py`
  - `diag/launch_preflight_004.sh`、`diag/bind_claims.py`、`diag/assemble_release_manifest.py`、
    `backend/scripts/recompute_boundary_manifests.py`
  - `docs/`（5 份新文档的事实准确性）

## 2. 审查维度

用户指定四维 + 自补四维：

### 用户指定
1. **可优化**：多行代码可否用更少行实现一模一样效果（含配置/脚本冗余）
2. **死代码**：不可达分支、未使用变量/参数/导入、废弃未标注的脚本
3. **Bug**：逻辑错误、边界条件、异常路径、路径/编码/平台问题
4. **不合理/不合逻辑**：设计矛盾、语义错误、与既有约定冲突

### 自补充
5. **安全**：密钥处理、注入面、检查器改动是否弱化任何既有门禁
6. **一致性**：文档陈述 vs 代码事实；同类逻辑多副本的漂移风险
7. **流程模式**：本次执行中反复出现的系统性失误模式（已知候选：后台任务 + 相对
   路径 cwd 漂移导致的环境污染 ×3）——根因是否已在工具层修复
8. **测试有效性**：新测试是否真的守护其声称的行为（含被 monkeypatch 绕过门禁
   的历史教训复查）

## 3. 审查方法

- 双轴并行子代理（code-review 技能）：
  - **Standards 轴**：CONTRIBUTING.md + smell 基线 + 用户四维
  - **Spec/Bug 轴**：政策 v2 语义正确性 + 检查器不变量 + 采集/报告链事实核对
- 自审清单：两位审查者结论的交叉验证 + 修复优先级裁定
- 不变量回归证明：`test_agent_release_check.py` 全绿（含削弱门禁拒绝测试）

## 4. 验收标准

- 每个发现：文件+行号+证据，区分「硬伤（必须修）/判断题（记录）」
- 硬伤修复后再验证（红绿或回归证明）
- 判断题全部入档（STATUS/PROGRESS 或代码注释），不静默丢弃

## 5. 输出物

- 双轴审查报告（聚合）
- 硬伤修复提交 + 回归证明
- 本计划书执行完毕的对照勾选
