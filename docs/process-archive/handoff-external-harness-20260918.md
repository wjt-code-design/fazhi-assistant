# 交接书 · 外部 harness 批次（R11 / R12 / R15-lite + 冻结物处置）—— 2026-09-18 晚

> **本文是「外部 harness 改进批次」工作流的接手入口**（Owner 2026-09-18 明确要求新建）。
> 项目级第一入口仍是 `docs/process-archive/handoff-takeover-20260918.md`（T-A 主线 primer，并行会话所建）+
> `docs/process-archive/execution-plan-entity-precision-20260917.md`（深度执行书）。本文只写**本批次特有**的
> 上下文、已锁决策与坑；与执行书冲突时以执行书为准并留痕差异。
> 本文件未提交（docs/ 长期未跟踪惯例），是否入快照由 Owner 定。

---

## 0. 30 秒定位

- 仓库 `C:\Users\33393\Desktop\ai-legal-helper`（master，**全部本地提交未推送**）。
- **接手第一步：`git log -6 --oneline` 确认实际 HEAD**——并行会话高频提交，别假设停在哪个号；
  再 `git status --short --untracked-files=no` 看工作树（有别人的在途改动时，任何"跑出来的数字"
  都不对应提交态，见 §5）。
- 本批次提交链（均在 2026-09-18）：

| 提交 | 内容 | 归属 |
|---|---|---|
| `9d79389` | R15-lite：law_as_of 法律版本基准日服务端注入管道 | 本会话（被并行会话收编提交） |
| `7c7261c` | R11+R12：时效确定性 `limitation_calc` + 伪调用检测 `phantom_check` | 本会话（同上）⚠️ 劈分混乱：本批的 service.py kwarg 与 gate/chat_integration 两个测试被并进了这个提交 |
| `afd3138` / `777e332` | P1 harness 测试（评测 resume 归属 / 词表分支 / 归属绊线） | 并行会话自己的工作 |
| `8479a5b` | 冻结物解冻留痕（pyproject）+ repository lint 折叠修复 | 本会话收官 |

- 基线：全量 `pytest -m "not slow"` = **1233 passed / 18 deselected / 0 failed**（423.71s，
  `_pytest_r15full2.txt`；含并行 P1 的 3 个测试）。ruff format/check 228 files 全绿；mypy 71 files 0 issues。
  **旧数字 974/990/992/1101/1155/1188/1190/1225 全部作废禁止引用。**

---

## 1. 本批做了什么（为什么）

外部人士对法智一无所知地写了一份 agent harness 优化建议（知识库
《legal-agent-harness-review-optimization-plan》，新旧两版以 sha 区分，新版 `PkpoxuSZgfdzex4EnAbWnQ`）。
对其做 64 项差距分析（`docs/process-archive/external-harness-plan-gap-analysis-20260918.md`：16 实现 / 28 部分 / 20 缺失，
文末有实施进度表），Owner 圈定 P0 = R11 时效、R12 伪调用、R15-lite 注入基准日。
**三者全部默认关 / 缺省行为逐字不变**——线上 Agent Path 零流量（AGENT_ENABLED=False），改动只影响评测。

### R15-lite 管道（本批核心，接手必读）

```
ChatIn.law_as_of（HTTP body，ISO 日期，非法 422）
  → /chat 端点（body.law_as_of 位置传参）
  → _bootstrap_only(law_as_of=…)
  → bootstrap_request → RequestBootstrap.law_as_of（server-owned）
  → service.execute_agent_request → create_run(..., law_as_of=bootstrap.law_as_of)
  → AgentRun.law_as_of（缺省 None ⇒ 落当日，行为逐字不变）
      ├→ 工具 cutoff（legal_retrieval / exact_article 的 context.law_as_of）
      └→ AgentEvidence.law_as_of（证据有效性审计）
```

- 消费点全部是**既有机制**（本批未改）：gateway `_OWNERSHIP_FIELDS` / runtime/planner 契约清单
  会拒收模型输出里的 law_as_of ⇒ server-owned 保障天然成立。
- 测试 5 个，覆盖每一跳；watch-it-fail **四重**全部"为正确原因红过"：
  M1 repository 忽略注入（repo+service 红）/ M2 service 丢 kwarg（service 红）/
  M3 bootstrap 返回丢字段（bootstrap 红）/ M4 ChatIn 删字段（schema 红 AttributeError）。
  另有透传锁测试在真实缺陷（签名编辑未落盘）上自然红过一次。
- 用途：T1 跨 2021-01-01（民法典分水岭）评测场景 + R38 fact_date 的注入通道。

### R11 / R12 速览

- `agent/limitation_calc.py`：诉讼时效 3 年（民法典 188 条）/ 20 年上限（不中止不中断）/ 劳动仲裁 1 年 /
  2021-01-01 前事实 fail-open（`needs_case_review=True`、不放行 token）；受控 token 只放 `duration:N:年`。
- `agent/phantom_check.py`：声明动作 vs 实际成功工具比对 → `PHANTOM_TOOL_CLAIM`
  （writer 拦截 + verifier 第二道防线 + service 纠正性重试码登记）。
- 新开关：`phantom_tool_check`（默认 False）。

---

## 2. 已锁定的决策（不要重开、不要"顺手改"）

1. **repository.py 已解冻**（Owner 决策卡 2026-09-18：「解冻并保留改动」）。判据=不在最新 1e9 锚定
   （candidate-hashes.json 仅 6 项、不含 repository；仅 09-10 t2-persistence 老 manifest 锚定过，
   历史可经 git 复现）。pyproject exclude 已移除 + 注释留痕。
   **state_machine / prompts / gate5_judge 仍冻结**——触碰前必须走 Owner 决策卡（B1：触碰即阻断
   候选冻结/付费轮），绝不能顺手改。
2. 全部新开关默认关：`entity_precision_check` / `numeric_matching_v2` / `agent_partial_delivery_enabled` /
   `agent_writer_corrective_retry_enabled` / `phantom_tool_check`。**开启 = 评测批预登记事项，不是代码改动。**
3. law_as_of 缺省语义 = None → create_run 落当日。不要改成必填、不要动默认行为。
4. `case_domain` / `law_as_of` 是仅有的两个评测通道注入字段（HTTP body，生产前端不传）。
   **新增注入字段必须镜像这套链路 + 每跳透传锁测试**（本批的透传锁曾逮住一次真实静默丢失）。

---

## 3. 怎么验证（接手第一步跑这些）

```bash
cd "C:/Users/33393/Desktop/ai-legal-helper/backend"
# 门禁三绿
./venv/Scripts/python.exe -m ruff format --check . ; ./venv/Scripts/python.exe -m ruff check .
./venv/Scripts/python.exe -m mypy .
# 全量（--basetemp 必须全新目录；输出重定向文件，本机 Bash 无 grep/tail）
./venv/Scripts/python.exe -m pytest -q -m "not slow" --basetemp="../_pt_<新目录>" > "../_<日志名>.txt" 2>&1
# 本批定向（5 个测试）
./venv/Scripts/python.exe -m pytest tests/test_request_bootstrap.py tests/test_agent_repository.py \
  tests/test_agent_chat_integration.py tests/test_phase2.py tests/test_agent_gate.py \
  -q -m "not slow" -k law_as_of
```

- 声称完成前过**证据五连问**（skill `show-your-work-new`）；变异测试后 `git grep` 查变异残留。
- **1233 的字节口径**：全量跑在 `777e332` 树上，与 `8479a5b` 的差异仅 2 文件（pyproject [tool.ruff]
  注释/排除表 + repository.py 签名空白折叠），已证 AST 逐字节等价（ast.dump 比对 True）且 pytest/mypy
  配置零触及 ⇒ 按证据门禁边界规则以等价性证明代替重跑。
- ⚠️ 工作树有并行会话在途改动时，你跑出的数字**不对应任何提交**——先看 §5。

---

## 4. 下一步（按差距分析优先级）

1. **R38 fact_date**：评测案例携带事实发生日 → 经本批 law_as_of 管道注入，跑跨 2021-01-01 对照臂。
   ~~入手点：`evals/gate2_runner.py`~~ **（2026-09-18 勘误）路径写错了**：真实文件是
   `backend/scripts/gate2_runner.py`（`evals/` 下只有题集 JSON 与校验/分析脚本，无 runner）；
   首轮 payload 原在 `:460-464`（原记 "L461" 正确，现已抽为 `_round1_payload`）、
   `--no-case-domain` 在 `:293-298`、`--cases-file` 在 `:304-308`。
   **该项已由接手会话完成注入侧**（见下第 5 条），仍缺事实日抽取环节。
2. **R32 红线 YAML**：按建议书附录 C `legal_rules.cn.yaml` 骨架落配置（red_lines /
   deterministic_tools / version_anchors / retrieval / citation_output_format 五段）。
3. **R24 引用格式模板**。
4. 已知小缺口（接受现状，除非 Owner 要求）：端点→`_bootstrap_only` 一跳无端点级集成测试
   （与 case_domain 先例同口径，`_bootstrap_only` 已有单元透传锁）。
5. **R15 版本适用绊线已落（2026-09-18 晚，接手会话；提交 `7d4b2da`→`5aa9dbd`）**：
   `limitation_calc.law_version_crosses_watershed`（判定真源，纯新增）+ `verifier` 门
   （`LAW_VERSION_WATERSHED_MISMATCH`）+ 接线自检（`LAW_TRIPWIRE_NOT_WIRED`）+ `service` 从
   `AgentRun.law_as_of` 透传 + **基准日随 PASS 结果传给 `render_verified` 的二次验证**（⚠️ 接手时
   发现的关键一跳：`verifier.py:226` 会再跑一次 `verify()`，`main.py:878` 生产路径经它出答案；
   不携带基准日则开关一开整轮静默不交付，症状是 `VERIFIER_NOT_PASS` 而不是绊线原因码）
   + `gate2_runner` 的 `as_of_date` 出口 + 非冻结对照样本 `evals/watershed-cases-r15.json`。
   开关 `law_version_tripwire_check` **默认关，开启属评测批预登记**（§2.2）。
   §2.3 的缺省行为未动（`repository.py` 仅补 docstring 边界）。**对照臂执行仍待 Owner 侧起服务**
   （命令见 `docs/process-archive/superpowers/plans/2026-09-18-r15-law-version-tripwire.md` Task 4 Step 10）。
   **收口数字（2026-09-18 23:5x）**：全量 `1266 passed / 0 failed / 18 deselected`（140.94s，
   **对应提交态 `aaf088b`**——T-E 的 `44210ef` 也已入树、`git status -uno` 为空）、
   本批 lane `249`（基线 227 + 22）、三绿 + `pre-commit` RC=0、probe 1 passed；
   执行证据与**八条限制**（含"service→verifier 一跳以守卫代替透传锁""`_*` 留痕日志含 .env 密钥不得 add"
   "对照臂 n=1，只证明门会响、不等于评测基线已建立"）都在上述 plan 的《收口记录》《对照臂真实读数》两节。
   ⚠️ 本会话另两枚未提交的文档订正只在工作树里（docs/ 未跟踪惯例），被并行会话同步回提交态会丢。
   **对照臂已实跑（2026-09-19 凌晨，本机后台 uvicorn + LongCat）**：臂 A（agent、绊线关）W01 对 2019
   事实按"三年"作答并交付；臂 B（同服务改 `LAW_VERSION_TRIPWIRE_CHECK=true`，env 注入、代码默认未动）
   W01 → `LAW_VERSION_WATERSHED_MISMATCH` 且零字交付，W02（2023）仍正常交付 ⇒ 门会响也不误伤。
   🔴 **顺手量出的覆盖缺口**：版本门只在 agent 路径上，**快车道没有版本判定**，而线上
   `AGENT_ENABLED=False` ⇒ 用户当下走的恰是无保护那条路（臂 0 读数=直接给三年 + 2022 届满、无衔接说明）。
   详见 plan《对照臂真实读数》节（含"对照样本需先调 `fact_reveal` 关键词才能正式用于评测批"）。

---

## 5. 并行会话协同（🔴 本批两次事故都来自这里，必读）

- **事故 1**：并行"零记忆接手会话"在间隙把我的工作树收编提交（9d79389/7c7261c…），其快照时点
  **早于我的最新编辑**，随后把工作树同步回提交态，**抹掉了我两处未提交修改**（pyproject 解冻留痕 +
  lint 折叠）——已重放并 `8479a5b` 固化。
- **事故 2**：它的提交劈分把我的文件并进语义不符的提交（R15-lite 的部分文件进了 "R11+R12" 提交）。
  内容无损，但接手者按提交信息回溯时会困惑——以本文 §0 的归属表为准。
- **规则**：Owner 决策类/关键修改落盘后**立即本地提交**；动笔前 `git diff --stat` 确认基线；
  声称完成前 `git status` 复核；看到别的会话在改同一文件 → **停手确认**；禁止 `git stash` /
  `git reset --hard` / `git clean`（会毁他人证据，接手书同款红线）。

---

## 6. 坑速查（全表在 `.workbuddy/memory/MEMORY.md`，这里只列本批踩到的）

- 工具 Edit 显示"成功"≠落盘：本批一次 main.py 签名编辑实际未落盘，靠新加的透传锁测试以
  TypeError 逮住 ⇒ 关键编辑后 `git diff` 复核。
- 同批多次编辑同一文件常撞 EBUSY：重试同一编辑即成功（非数据丢失）。
- pytest/lint 一律重定向到文件（本机 Bash 无 grep/head/tail/ls/cat/dirname，管道会 SIGPIPE 杀 pytest）；
  含反引号/`$` 的 Python 内联一律写 .py 文件。
- 本机 git：`git log -- path` 会被 refs/replace 遮挡报 unable to read → 用 `--no-replace-objects` /
  `git diff` 对照；mypy 必须 `mypy .`（bare `mypy` 报 missing target）。
- 后台 pytest 会被会话中断杀掉（日志止于中途 = 被收割，重跑即可）。

---

## 7. 待 Owner 决策

1. **推送**：`9d79389`→`8479a5b` 共 5 个本地提交未推送。按快照机制：`ls-remote` 实测远端 tip 作
   parent → commit-tree → 安全闸（diff ⊆ 预期路径）→ push → 核对。
2. **下一批范围**：R38 / R32 / R24 的取舍与顺序。
3. **基线刷新**：并行会话 P1/词表工作收敛提交后，重取全量基线数字（旧 1233 作废）。

---

## 8. 证据索引

| 用途 | 位置 |
|---|---|
| 批次报告（管道图/变更清单/M1-M4/门禁/冻结物处置全记录） | `dispatch-output/r15lite-20260918/report.md` |
| 差距分析（64 项 + 实施进度表） | `docs/process-archive/external-harness-plan-gap-analysis-20260918.md` |
| 测试留痕 | 根目录 `_pytest_r15m1/m2/m3.txt`（变异红）、`_pytest_r15sc/sc2.txt`（schema 红/绿）、`_pytest_r15lite/lite2.txt`（定向）、`_pytest_r15full2.txt`（全量 1233）、`_pytest_r15final.txt`（提交后复验） |
| lint/类型 | `_ruff_unfreeze2.txt`、`_mypy_r15b.txt` |
| 冻结物取证 | `backend/pyproject.toml` 注释；`dispatch-output/agent-quality-1e9-20260916/candidate-hashes.json`（不含 repository.py）；`dispatch-output/t2-persistence-20260910/candidate-manifest-*.json`（历史锚定 57c1c00d…） |
| 当日日志 | `.workbuddy/memory/2026-09-18.md`（R15-lite 收口段 + 交接书落盘段） |
| 长期约定 | `.workbuddy/memory/MEMORY.md` |
