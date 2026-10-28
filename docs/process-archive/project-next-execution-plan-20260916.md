# 项目后续执行建议方案（2026-09-16）

状态：方案已编写；决策按用户授权采用推荐选项。本文不表示实施、付费评测或发布已经完成。

## 1. 目标与依据

下一阶段目标：让当前项目可稳定复验、收尾已有前端工作，并用真实失败样本决定一次最小质量改进。暂不扩大功能范围。

依据：

- `docs/process-archive/work-progress-20260916-session3.md`：历史交付与已知缺口。
- `docs/process-archive/final-agent-mainline-handoff-20260916.md`：覆盖契约、法律依据筛选及验收条件。
- `docs/process-archive/frontend-execution-book-20260915.md`：前端剩余 T2.4 与 V1–V8。
- `docs/process-archive/preregistration-dept-guard-r1-optionB-20260916.md`：R1-OB 已冻结判据。
- 本次及上一轮只读检查：HEAD 为 `1be944c`；当前 TypeScript 检查报 UploadSection 三处错误；Git 对象库仍有已知断链。历史 pytest 1085、Vitest 45 等数字不作为本轮新鲜通过证据。

纠正前次核验的环境结论：Python 启动“拒绝访问”、npm CLI 路径缺失与 esbuild 目录读取失败，只能证明当时执行环境受阻，尚不足以证明宿主安装损坏。先验证权限与可执行路径，再决定是否需要修复安装。

## 2. Grilling 决策记录

用户已授权无需逐题询问，以下按依赖顺序完成质询并采用推荐决策；这是方案内的决策对齐记录，不冒充用户逐项口头确认。

| 质询 | 采用的决策及理由 |
|---|---|
| 当前最需要新功能还是可验证的现有交付？ | 先恢复可验证性。环境受阻和未完成 WIP 会让后续效果难以归因。 |
| 是否先重装 Python/npm？ | 否。先检查沙箱权限、解释器和 CLI 实际路径；确认真实安装问题后才做局部修复。 |
| 是否将 WIP 移走就算前端验收成功？ | 否。交付对象是保留有效工作成果的完整工作树；完成 T2.4 后再验。 |
| 是否优先恢复全部 Git 历史？ | 否。先确保当前代码与关键证据可恢复；缺失历史对象的考古恢复不在关键路径。 |
| 是否立即推进 R1-OB 在线批次？ | 暂缓。E04 依赖评测域码，普通生产请求没有该输入；先明确实验能回答什么。 |
| 是否把域码加到公共接口、再让模型判断域？ | 否。没有证明产品需要这个输入；不引入模型判域或新增用户步骤。 |
| 质量改进从何处开始？ | 复用两份 1e9 终稿和已有题集，定位 required 条文未进入答案的具体阶段，再选择一个改动。 |
| 是否更换模型、向量库或 Agent 框架？ | 暂不。现有证据不足以支持平台级重做；先验证最小可证伪改动。 |
| 是否用“completed/full”认定法律正确？ | 否。运行完成、争点覆盖、法律正确分别验收；独立法律验收保留开放。 |
| 是否安排多个 Agent 同时改动？ | 默认串行、一票一提交。当前剩余工作小且存在共享 WIP，协调成本高于收益。 |

## 3. 执行顺序与票据

顺序：T0 完成后，T1 与 T2 均可启动，二者没有前后依赖；默认单执行者按需安排，不因此新增并行 Agent。T2 完成后可开始 T3 的只读定位，实施改动须等 T1、T2 完成并记录完整工作树基线。T4 仅在满足前提时启动。法律独立复核可在准备好材料后与工程工作并行，由适格复核人完成。

### T0：恢复可复验基线

动作：

1. 记录执行起点 HEAD、tracked diff 和相关未跟踪文件清单；保留他人 WIP。
2. 核对 `backend/venv/pyvenv.cfg` 指向的解释器；对拒绝访问按工具权限流程申请必要的提权复验。前端优先验证已有本地 CLI，避免直接安装新依赖。
3. 环境能执行后，先跑受影响的后端契约测试及前端测试，记录基线错误；当前 T2.4 三个 TypeScript 错误登记为 T1 待办。
4. 当前树与关键交付文档、重放脚本、脱敏评测证据形成一次可恢复检查点。数据库、账本与对话证据先检查隐私和密钥，不批量加入版本库。

验收：解释器和本地测试工具可启动；命令、退出码、HEAD 与实际失败项能对应；检查点中能恢复并核对当前 tracked 文件及选定交付材料。环境受阻则如实保留“受阻”，不把未执行记为通过。

Git 限制：不运行 `dispatch-output/git-repair-20260916/verify_repair.py` 作为普通检查。源码包含 `repack -d`、测试提交和硬编码 `reset --soft 8353821`，不适合当前 HEAD。仅用只读对象检查及树对比；不新增修复框架，不改写历史、不删除备份。

### T1：完成前端 T2.4，并恢复完整工作树门禁

范围：`frontend/app/admin/page.tsx`、现有 `sections/` 和必要的 `frontend/lib/types.ts`；以现有 WIP 为基础。

动作：核对上传预览响应的真实结构，复用已有类型或补齐准确的 `ChunkPreview`；修复两处隐式 any；将六个 section 接入页面，保持权限、请求、状态重置和错误反馈语义。

验收：

- 完整工作树 `tsc --noEmit` 无错误，现有 Vitest、lint、build 通过。
- 按原执行书完成 V1–V8；其中 V4 的改动归属改按“本票据起点到本票据提交”核对，不能用含其他工作线的历史区间判定越界。该口径调整明确留痕。
- admin 页面达到原定 ≤250 行，且保持页面组装职责；不得靠压行或无意义拆文件达标。
- 六个后台 section 的加载、切换、上传预览/提交、错误态及权限行为验证通过；原执行书聊天关键路径不回归。
- SW 构建号桥接按 `package.json` 的真实 build 链验证，检查 `build-id.txt` 的生成和忽略规则；不因其名称被叫作“postbuild”就假设存在同名脚本。

提交前在 `backend` 使用 T0 验证过的项目解释器运行门禁。若保留现有虚拟环境，命令为 `.\venv\Scripts\python.exe -m pytest -m "not slow"`、`.\venv\Scripts\python.exe -m ruff check .`、`.\venv\Scripts\python.exe -m ruff format --check .`、`.\venv\Scripts\python.exe -m mypy .`；若解释器位置变更，统一替换为 T0 实测路径并记录，不依赖 PATH 中的裸 `python/ruff/mypy`。记录实际结果及既有失败；发现无关故障先归因，不顺手扩大本票据。

### T2：补齐交付证据，并准备独立法律复核

动作：

- 在现有测试中核对 full/partial/all-fail、旧历史 unknown、实时与历史一致，以及“正文引用 ∩ 同一 claim 绑定证据”的真实断言；已有有效测试直接复用。
- 修正 T2 重放脚本的证据缺口：当前脚本检查正文引用集合，却未独立核对同一 claim 的证据交集；发现 violations 也只是打印。重放应核对交集及顺序去重，并在无有效样本或违规时返回非零退出码。
- 重放结果写入新证据位置，避免覆盖历史文件；R1-OB 离线脚本现会写回原 `validation-result.json`，复用前同样处理输出位置。
- 整理两份终稿、对应争点与证据定位、覆盖提示语义、已发现的问题，交给独立复核人；保留“未完成独立验收”标记。

验收：两份终稿能逐份定位，重放通过或失败均可准确反映；断言确实能识别未绑定条文，而非仅重复渲染器结论。独立复核没有发生时，工程票据可以完成，但法律正确性验收保持开放。

范围约束：本票据准备复核材料，不重新裁定具体法律适用、不把既有自查意见作为独立法律金标。

### T3：定位一个质量缺口，只做一次最小改进

先调查，后选择实现；不另建大型评测平台。

1. 从现有 1e9 失败争点及冻结开发集数据定位 required 条文：库中是否有 → 原始召回是否有 → 重排/截断后是否有 → writer 是否收到 → 最终引用及适用是否正确。H01–H05 不用于选择或调整本轮实现，保留作冻结验收回归；核对其历史使用情况，若曾据其结果调整实现，应标记为已使用的回归集，不再声称它提供独立留出证据。需要新的独立泛化结论时，再在实现冻结后由独立来源准备未用于调优的样本，不事后替换原验收集。
2. 复用现有日志和数据；仅在缺少决定性证据的边界补最小观测。无证据就标“待定位”，不笼统定性为检索污染。
3. 在改动前冻结案例、输入和候选代码 hash，选定一个改动点。若条文不在库，优先处理数据；若候选已包含但排序丢失，处理选择；若已经送达 writer，归入生成/适用问题。
4. 独立来源核定验收目标：目标 required 条文进入正确阶段、未新增 forbidden、原有完成行为不回退。法律适用正确仍需要独立复核。

验收：选定反例先失败、改动后通过；冻结回归集未新增误杀或协议回归。未取得可比的在线证据，只可声称离线改善。出现同类问题连续三次修复失败，停止补丁并重新质疑假设。

停止条件：没有可定位根因、需要同时重做多个模块、或只能靠扩大关键词表/改金标“改善”，则交付定位结论并冻结实现，不堆补丁。

### T4：R1-OB 条件性实验（非默认必做）

启动条件：T0–T2 完成，且研究问题明确为“受信任域信息/原始问题是否改善判域输入”，具有生产价值或明确的研究价值。

- 分开记录有域码和无域码两种输入条件。无域码保留原始问题拼接语义；有域码仅来自受信任评测通道，不将答案标签泄漏给普通生产请求。
- D2 值先经独立案例定义核对；非法值拒绝或按明确契约处理。不得为达到 E04 指标而事后标域。
- 保持 `dept_guard` 指示词表与实体法不过滤边界不变；复用既有机制，只增预注册要求的最小可回滚开关，默认关闭。
- E01/E04、冻结回归与 H01–H05 均纳入对应阶段。在线沿用原 P1–P6，尤其不能因实体法超出过滤范围就从总体验收排除 E04 的 forbidden。
- 评测域码分支 PASS 不等于生产无域码分支 PASS；分开写结果，不合并成产品质量改善。

付费运行遵循原 R1-OB 文档的单独申请要求；本轮方案决策授权不替代真实调用授权。历史预算估算不视为当前报价，执行前核对实际模型定价与运行范围；不为探路新增模型供应商。

任一冻结判据失败即按原止损规则冻结；不调整词表、样本或判据救数。

## 4. 交付边界与本轮不做

每票沿用现有提交和文档体系，仅记录范围、变更、命令结果与残余问题。T0–T4 五个小目标结束或遇到连续失败时，做一次整体复盘，不建立新的流程平台。

远端同步在内容检查点就绪后执行；沿既有快照方法，先取得实际远端 tip，并比对它相对上次已核实同步点的内容变化，确认远端新增改动已纳入目标快照。存在未整合变化时，先整合并验证；无法确定上次同步点时，先完成内容核对，不直接用本地树覆盖远端。随后以已核对的远端 tip 为父提交，验证发送对象完整、快照树与整合后目标内容一致，再普通推送并核对远端哈希。若推送期间远端前进，重新核对新增变化，不仅替换父提交后重推。fast-forward 成功不等于远端内容得到保留。不得把“内容只差一批”称作 Git 历史仅领先一个提交。未跟踪文件不会自动进入快照。

本轮不做：完整 Git 历史重建、新 Agent 框架、新向量库、新模型选型、通用状态管理、前端视觉重做、额外管理平台、全仓无差别重构、未经必要性验证的缓存与并发优化。

完成边界：T0–T2 是近期交付；T3 是一个定位与最小改进窗口；T4 可以有理由地不启动。工程门禁通过后仍不自动发布，独立法律验收与生产发布各自保留明确状态。

## 5. 方案对抗检查

- 边界：环境、前端、证据、质量实验分票，避免把所有问题塞进一次改动。
- 替代方案：立即实施 R1-OB 或整体重做检索都比当前方案扩大假设；先定位已有样本的真实失败阶段成本更低。
- 历史教训：不移走 WIP 造全绿、不运行带 Git 写操作的“验证脚本”、不覆盖旧证据、不以评测域码收益冒充生产收益。
- 可查事实：引用现有文档与本轮源码检查；所有历史指标保留历史口径，不承诺未经测量的提升幅度与工期。
- 可验收：工具可运行、完整工作树门禁、能失败的交集重放、单一反例与冻结回归分别对应清晰结果；代码行数和 completed 均不能替代真实行为与法律质量。

---

## 执行记录与整体复盘（2026-09-16 晚，接手批次；本节为执行后追加，不修改上文方案）

状态：**T0–T3 完成；T4 依计划条件未启动**；后端四门禁首次全绿；远端已同步。证据目录：`dispatch-output/t0-baseline-checkpoint-20260916/`、`dispatch-output/t2-evidence-replay-20260916/`。

### 提交栈（本批次，均为普通提交）

| 提交 | 内容 |
|---|---|
| 504dbd6 | T1：admin 拆分六 section 接入（page 847→214 行）；`ChunkPreviewResult` 复用修 3 处 tsc 基线错误 |
| 8a7df68 | T2：R1-OB 离线脚本 `R1OB_OUT_DIR` 参数化（复用不再覆盖历史证据） |
| cd368af | T3：writer 零 claim 抖动在 partial 开时重试一次（反例先红→绿） |
| 0de8671 | 修 2 处既有 ruff format 失败（全后端 216 文件转绿） |
| 8be9a4c | 远端快照（commit-tree，parent=602fde3；已推送并核对，FF 非强推） |

### 各票结果对照

- **T0**：HEAD 1be944c 起点记录、75 项 WIP 全保留（事后 75/75 复查）、venv/tsc/vitest/npm均实测可执行（**纠正前次"拒绝访问"结论：环境受阻假象，无需重装**）；检查点 263MB zip（testzip OK）+ 109 材料 + 隐私扫描。未运行 git-repair 脚本、未改历史。
- **T1**：tsc 0 / lint 0 error / Vitest 45/45 / build 5 路由（/chat 106kB ≤ 114.4）/ admin 214 行；V4 本票据区间（1be944c..504dbd6）backend+dispatch-output 零改动、V5 annotate.ts 零 diff；SW 构建号桥接按真实 build 链验证。
- **T2**：严格重放（逐 claim 交集+全等+负向探针+非零退出码）1e9 两 run PASS；**断言敏感性补测**（语义回滚缺陷版多列 4/9 条、断言报 mismatch）；R1-OB 参数化后历史文件 hash 实测不变；复核材料包 `review-package.md`（独立法律验收仍开放）。
- **T3**：反例定位 = 1e9 r2 争点3（87 条已检索归位却被 writer 漏写）→ **缺口在生成段而非检索段**；最小改动（partial 开时对 ISSUE_CLAIMS_MISSING 重试一次）；红（`assert 'partial'=='full'`）→ 绿（5 passed）→ 全量 **1086 passed / 0 failed** 零回退。效果层（真实 LLM 收益）未在线验证——按计划只声称离线改善。
- **T4**：未启动（研究价值未拍板 + 付费须单独授权，符合计划启动条件约束）。

### 计划外补完项

1. **后端门禁首次全绿**：0de8671 修复 2 处既有 `ruff format --check` 失败（verifier 折行合并；prompt_contracts 统一 CRLF 行尾、规范化后内容零变化），全后端 216 文件 format 转绿。
2. **远端同步完成**（计划 §4 流程全执行）：远端 tip 实测 602fde3（零前进）→ commit-tree 快照 8be9a4c（树一致 PASS、发送集 23 对象零缺失、dry-run FF）→ 普通推送成功 → `ls-remote` 核对 PASS。增量仅 12 文件（T0–T3 已知改动）。未强推、未伪造历史。
3. **V7 浏览器层全闭环**（playwright 实机验证）：连续两次 build BUILD_ID 变化（vP7FwRRF→jmjFbeQun）→ SW 缓存名 `fazhi-shell-jmjFbeQunY8P42Rnz3BAq` 与 `public/build-id.txt` 一致 → **断网刷新页面正常渲染**（离线兜底实测）。截图与 JSON 证据在 t2 证据目录。
4. **V8 可自动化部分完成**：/admin、/chat 未登录跳转 /login（权限守卫）；登录页（封面式两步）渲染正常；400px 视口零横向溢出；零失败请求。留人工：登录提交、消息流式、六 section 数据加载（需后端+LLM）。
5. **show-your-work 审计**：3 处过强表述更正（"同分布"→"同为近似输入"、"假象"归因降级、"重试"标注仅机制层）；2 项补测（V7 二次 build、T2 断言敏感性）；审计报告 `show-your-work-audit-20260916.md`。

### 整体复盘

**奏效的**：①"先取证后动手"在 T3 收效最大——链路考古（库中有→召回有→归位有→writer 丢）把直觉结论"扩检索"改写为"writer 重试"，避免了一个错误方向的大改动；②快照同步机制（commit-tree + 发送集验证 + FF 核对）第二次使用成熟，零故障一次通过；③"红先于绿"纪律执行到位，T3 反例与 T2 审计自检都有可视红。

**仍未验证（显式开放）**：V8 需后端的交互路径；T3 重试的真实 LLM 收益（需付费重跑）；独立法律验收（材料已备，待适格复核人）；R1-OB 在线批次（T4 域）。

**教训**：①本地 `origin/master` 引用会停留在旧 tip（fetch 前不代表远端现状），判断"远端是否前进"必须用 `ls-remote` 实测——本轮先用过期引用得出了"差 1971 文件"的假象，差点误导同步方案；②CRLF 混合行尾会让 `ruff format --check` 红而 git 看不见差异（本轮 prompt_contracts 实证），写文件须统一行尾。

**建议下一步**（按优先级，均需用户拍板）：①独立法律复核人对接（材料包已备）；②V8 剩余路径需起后端手测（或接入 harness 后一并验）；③T4 域内工作（D2 域码落地 + R1-OB 在线批次申请）；④检索召回质量立项（与 R1-OB 解耦的既有待办）。

---

## §6 第二批执行计划（2026-09-16 晚；用户授权自动执行，grilling 决策采用推荐项）

范围：上述建议的第 ②③④ 点（① 为外部依赖，保持开放）。执行序：P2 → P3 → P4，全绿后 code review + systematic debugging 收尾。

### P2 · V8 端到端交互路径（补齐剩余人工项）

- 步骤：① 起后端 `uvicorn main:app --port 8000`（venv 解释器 + `HF_HUB_OFFLINE=1/TRANSFORMERS_OFFLINE=1`，/healthz 就绪确认）；② 起前端 `next start :3000`（API 经 next rewrites → localhost:8000，已核实）；③ 浏览器脚本走剩余路径：
  a. **登录**（凭证取 `backend/.env` ADMIN_*，**不落任何日志**）；b. **admin 六 section** 切换与数据加载；c. **消息发送→流式**（单条真实 LLM）；d. 400px 移动视口下 admin/chat 无横向溢出。
- 证据：截图 + JSON 到 t2 证据目录；对 app.db 的测试写入（一条测试对话）如实标注。
- **Grilling 自答**：用真实 app.db 而非隔离库（六 section 需数据；单会话写入可接受）｜消息问题选低澄清概率的直答类｜后端起不来（BGE 失败）→ 降级 /healthz + 静态验证并如实标注，不反复重试。
- 停止条件：后端 2 次启动失败即转降级记录；浏览器脚本硬错即停。

### P3 · T4 域：D2 域码通道 + R1-OB 实现 + 离线验证 +（PASS 后）在线批次

- 依据：**预注册文档 §2.3 实施要点，判据已冻结、不得改判据**（`docs/process-archive/preregistration-dept-guard-r1-optionB-20260916.md`）。
- 步骤：① 侦察 `backend/tools/legal_retrieval.py` 判域调用点、`service.py` R1b 调用点、settings 开关现状、gate2_runner 案例对象结构；② D2 通道：案例对象 `domain` 字段 → bootstrap 透传（生产缺省 None，代码路径存在恒不触发）；③ R1-OB 实现：三级判域输入（tier1 域码 > tier2 用户原始问题+issue 问句拼接 > None）+ 单开关 `r1_ob_enabled` 默认 False；`dept_guard` 零改动；④ 测试（tier1/tier2/开关关零行为/E04 案例）；⑤ 离线验证：`validate_r1_ob_offline.py` 用**真实实现**重跑（R1OB_OUT_DIR 隔离输出）——判据：反例 2/2 + required 误杀 0 + 无新增漏杀；⑥ 离线 PASS 后在线批次（评测集 8 例 + H01–H05，P1–P6，上限 0.5 元，宿主 serve.py 隔离机制）。
- **Grilling 自答**：在线批次现在就做（用户"自动执行"+ 费用授权在 9-14 已放宽 + 上限 0.5 元）｜离线 FAIL → 按 D3 冻结并记录证伪，**不迭代救数**｜域码非法值 → 拒绝（按契约处理，不为 E04 事后标域）。
- 停止条件：任一冻结判据 FAIL 即冻结；serve/网络问题不重试超过 2 次。

### P4 · 检索召回立项收口（结论固化 + 剩余选项判定，无生产代码改动）

- 现状（1d/R4 已定论，全部可溯源）：四族否证（排序/池深/k/改写）+ KB 覆盖抽检 16/16 在库 + R4 转 (c) 接受 43.4%。
- 步骤：① 产出终局规划书 `docs/process-archive/retrieval-recall-final-plan-20260916.md`（事实链、四族否证表、KB 抽检、剩余选项 (a)(b)(c) 逐项评估）；② 对 (a) 换 embedding 做零成本可行性判定（查当前模型配置 + 磁盘/内存/网络约束量化）；③ 给出"何时重开"的触发器与推荐决策。
- **Grilling 自答**：(a) 换 embedding **不在本轮实现**（C 盘空间/网络约束 + 收益未证）｜(b) LLM 直出条文 **不实现**（架构级改动 + 幻觉风险，须专项设计评审）｜推荐决策 = 维持 R4 的 (c)，以 (a) 的可量化触发条件作为重开开关。
- 停止条件：文档产出即止。

---

## §7 第二批执行记录（2026-09-16 深夜滚动）

### P2 完成（V8 端到端交互路径，实机）

- 环境：后端 `uvicorn main:app :8000`（HF offline，3s 就绪）+ 前端 `next start :3000`。
- **关键发现（环境混淆坑）**：本地 build 内联了 `frontend/.env` 的 `NEXT_PUBLIC_API_URL=http://162.14.81.34:8000`（部署配置）→ 本地浏览器把登录请求发去**腾讯云生产**。修复：测试 build 时 shell 覆盖 `NEXT_PUBLIC_API_URL=http://localhost:8000`（内联实测：chunks 含 localhost×2、旧 IP×0）；CORS 已放行 `localhost:\d+`。
- 实测结果（截图+JSON 于 t2 证据目录 `p2-*.json / shot-p2*.png`）：
  - 登录（封面→表单→提交）→跳 /admin ✅；六 section 真实数据加载（统计 5 卡 / 用户 8 行 / 知识库 53 条 / 对话 50 行 / 日志 100 行）✅；400px 零溢出 ✅；
  - 消息 Enter 发送 → SSE 流式（4 次文本增长）→ 终态「参考条文（21）」折叠展开 ✅；兜底声明正常；
  - 👍 反馈：点按后 disabled + "已记录，谢谢反馈" ✅；正文 `.law-ref` 点击 → 内联法条卡注入（+236 字符）✅；
  - **图片/语音入口按后端能力隐藏**（`/api/health` 返回 `image_chat=false, voice_transcribe=false`——"诚实停用"设计正确工作）；文件入口存在 ✅。
- 诚实标注：Shift+Enter/流式期禁用/图片真实上传/语音真实录音 未单独实测（前端逻辑与单测已覆盖）；对 app.db 写入一条测试会话（如实记录）。
- 旁证（转 P4 §6）：参考答案混入《公务员法》《保险法》《刑事诉讼法》——程序法串台可被 R1 线治理，实体法混入超出 R1 边界。

### P3 完成（实现 + 离线 + 在线批次运行中）

- **实现**（提交 66426d1，14 文件 +286/−18）：`agent/r1ob.resolve_domain` 三级构造 + D2 透传链（`ChatIn.case_domain`（非法 422）→ `RequestBootstrap` → `LegalAgentState`（持久化，resume 可见）→ `ToolContext` → 两处判域点）+ 单开关 `agent_dept_filter_r1ob`（默认关，行为逐字不变）+ gate2_runner 域映射（`_CASE_DOMAIN_MAP`，未映射标签保守 None）。
- **测试**：11 条（三级语义/防御/mixed + legal_retrieval 集成契约）；**语义回滚 watch-it-fail 实证**（回滚 tier-1 → 2 条正确变红，其中 E04 敏感性用例是首轮发现"不敏感测试"后重设计的）；全量 **1097 passed / 0 failed**；ruff/format/mypy 全绿。
- **离线验证**：改 `validate_r1_ob_offline.py` 用**生产实现**重跑（R1OB_OUT_DIR 隔离输出）→ **PASS**（P0 复现 / E01 tier-2 / E04 tier-1 / P2 required 误杀 0）——**满足预注册"离线 PASS"条件**。
- **在线批次**（运行中，`dispatch-output/r1ob-online-20260917/`）：两臂（r1ob off=对照 / on）× 两集（评测 8 例 E01-E05+C05/C07/C09 + 留出 H01-H05），独立证据目录/账本，`AGENT_PROC_MISROUTE_CHECK=true` 联测；判据脚本 `analyze_r1ob_batch.py`（P1–P6 冻结判据）已备。

### P4 完成（检索召回终局规划书）

- 产出 `docs/process-archive/retrieval-recall-final-plan-20260916.md`：事实链 + 四族否证表 + 剩余选项量化评估 + **重开触发器**。
- **新核实事实**：云 embedding 通道（`text-embedding-v4`，768 维）**已实现**——换武器无需新架构，只需配置+重建库+回归；资源约束实测（C 110GB free / D 911GB free / chroma_db 345MB）；本地模型 bge-base-zh-v1.5。
- 推荐决策：维持 R4 的 (c)；以触发器（§5）作为重开开关。

### P3 在线批次结果（判据完成，2026-09-17 凌晨）

- **裁决：P1–P4、P6 达成；P5 不可判定（如实）**——未触发冻结条件。报告 `dispatch-output/r1ob-online-20260917/report.md`，机器可读结果 `criteria-report.json`。
  - P1 forbidden（评测）0/0 ✅；P2 completed 4=4 无下降 ✅；P3 无未知码 ✅（KNOWN 集合核对代码出处后补全 3 个既有码）；P4 留出 forbidden 0/0 ✅；
  - **P6 亮点**：对照臂 **1 例串台**（proc_misroute）→ R1-OB 臂 **0**——判域输入扩展消掉对照臂既有串台（方向与预注册预期一致）；过滤事件 4→6 次；
  - **P5 不可判定**：留出集两臂同因 `PLANNER_PARSE_ERROR` 0/5 完成（环境性普遍失败，非 R1-OB 回归；基准=0 时"≥对照 80%"无定义）——**不救数**，如实移交为独立观察项。
- 单例波动如实记录：E03（off 完成→on 澄清耗尽）、C05（off 失败→on 完成）互相抵消（净 4=4，n 不足不下因果结论）；on 臂 1 例 `CITATION_CHECK_FAILED` 为**既有码 + 防线工作**（非新失败面）。
- **状态边界（预注册纪律）**：评测域码通道验证通过 ≠ 生产无域码分支收益；开关 `agent_dept_filter_r1ob` **保持默认关**，生产行为逐字不变；默认开启=产品决策。

### 收尾（code review + systematic debugging）

- code review 两轴完成（报告 `r1ob-online-20260917/code-review-report-20260917.md`）：Standards 无阻断（注释误导已修）；Spec 缺口已修（空池契约、重试盲区）——修复提交 `e829688`（+2 测试）。
- systematic-debugging 处置 4 事件（E01 假性通过 / settings 缩进事故 / commit 引号坑 / KNOWN_CODES 漏码）均"定位→一次性修→验证"闭环，记录于 same 报告附录。

### T-A0 数字溯源诊断完成（2026-09-17，零成本离线；主线一首项）

- 报告：`dispatch-output/ta0-numeric-trace-20260917/report.md`；证据 12 份 state dump + 12 脚本
  （showyourwork_recheck.py 复现 13/13 PASS）。
- **结论：11 次 UNSUPPORTED_NUMERIC_TOKEN 拒绝全部 (a) 匹配缺陷**——主机理 = 数字 token
  形态不归一（`_AMOUNT_RE` 必须"元"结尾："5万块/8万开工款"→number:N vs "N万元"→amount:N:万）；
  次机理 = 跨争点事实数字无白名单 + 未决事实脱敏副作用（writer.py:286-291）。
  "三年"有受控来源（民法典188 已检索挂时效争点——证据挂载只在 agent_evidence 表，
  state_json.evidence 无 issue_id 字段，分析勿按后者分组）。
- **(b) 仅受理费金额**：KB 缺《诉讼费用交纳办法》（laws*.json / laws_raw 三处 0 命中）→
  T-A3(b) 受控计算需 Owner 授权补源。
- **勘误**：E02 受理费被拒码 = UNKNOWN_EVIDENCE_ID（非 NUMERIC）；E02 的 NUMERIC 拒绝
  在"5万债权成立"争点。T-A3(a) 两项修复方向均被证实必要（白名单须取脱敏前原值）。
- 零代码改动、零生产影响。

### T-A1 法条库标注（预标+自查完成，2026-09-17；待复核人抽验）

- 金标 53 entries → **38 条唯一 (law,article)**（15 跨案例重复，留痕）；LLM 预标 38/38、0 failed
  （text 档 temperature=0，每条 1 次+解析失败重试 1 次，76s）。
- 产出：`backend/knowledge_base/law_annotations.json`（四字段 schema+词表冻结于 _meta；
  键与运行时 evidence.source_ref 同构）+ `dispatch-output/ta1-annotation-20260917/` 全链路证据。
- 程序自查 H1–H5 全 PASS（覆盖/枚举/词表零外溢/chapter 空白归一逐字回查/applies_when）；
  分歧候选 2 条（民法典496 / 消保55，条文混合形态两可）强制进抽验样。
- 抽验：`reviewer-sample.md` 14 条（36.8% ≥ 1/3，系统抽样 ∪ 分歧条）待复核人回填 → 分歧裁决 → T-A2。

### T-A1 复核收口 + T-A2 实现完成（2026-09-17 晚）

- **T-A1 收口**：复核 56 项 53 是/3 否（94.6%）；3 项 subject_types 已修正（1179/693/686）、
  词表 v2、分歧裁决与建议处置留痕（`ta1-annotation-20260917/disagreement-verdicts.md`）。
- **T-A2 完成**（D1 选项一/D2/D3 已拍板）：标注库 69 条（`_ta2.direction_subjects`）；新模块
  `backend/agent/entity_precision.py`（机制A 事实类型词域 / 机制B duty-right 错位）挂
  **writer 渲染循环 citation 检查同位**（非 verifier 终态——service.py:466 会违反 P3）；
  开关 `entity_precision_check` 默认关；service `_UNCOVERED_REASON_TEXT` 加两文案。
- 实测拦截 **3/10**（独资42、合伙102、民法典804）；残余 7 项精确清单固化于测试
  （6/49 归 R1 线；128/131/801/802/807 需 domain_tags 机制，T-A5 后议）。
  标注修正 2 处（787 主体系定作人/承揽人；102 债权人移 right 侧）。
- 测试：`tests/test_entity_precision.py` 30 passed（四组）；watch-it-fail 落盘；
  ruff/format/mypy 全绿；**全量门禁 1137 passed / 0 failed**（5m43s）。
- 通道教训：dashscope 403 FreeTierOnly 后先逐条试 LLM_MODELS_JSON 回退（仅 priority 0 耗尽，
  1-5 可用）——Owner 指正后改正，siliconflow 弯路产物留证。
- 下一项 = T-A3 拒答策略分级（依据 T-A0：(a) 为主 → 数字归一 + 事实数字白名单）。
- 前端本地 build 已从测试配置（localhost:8000）**恢复生产配置**（chunks 实测 162.14.81.34×2 / localhost×0）；端口 18111/8000/3000 全释放。

### 待办处置（2026-09-17 凌晨，用户"全按推荐"授权后执行）

- **#2 推送完成（三轮快照）**：`f710915`（第二批：R1-OB 实现 + review 修复）→ `3d0c267`（LLM 修复）。
  均树一致 + 发送集零缺失 + FF + 远端核对 PASS；远端 master 现 = `3d0c267`。
- **#3 PLANNER_PARSE_ERROR 诊断完成 + 缺陷修复（新提交 `41364db`）**：
  - 根因（两层）：时段性网络抖动（APIConnectionError×6）**放大缺陷** = `is_transient_error`
    漏判 openai SDK 包装形态 → 6 模型全部 `mark_depleted` → 连锁 `QuotaExhausted` →
    `PLANNER_PARSE_ERROR`（留出集 0/5 的直接解释；与 R1-OB 无关——off 臂同样触发）；
  - 修复：`llm_errors._is_transport_like`（类名 + 异常链上溯，有界 6 层，不 import SDK）；
    watch-it-fail 闭环（回滚→2 红→恢复 41 passed）；全量 **1101 绿**；
  - 报告 `r1ob-online-20260917/planner-parse-error-diagnosis.md`。
  - 同族第 3 次记录（rerank 1k → LLM 主链路 1c → **SDK 包装形态**本次覆盖）。
- **#5 mypy 注释勘误完成**（pyproject：明确 scripts/ 在 exclude 内不参与检查 + 4 个既有错误留痕）。
- 维持项：V8 剩余人测（不做）｜.git-backup 保留｜部署切链后置｜召回触发器无动作。
- 待拍板：R1/R1-OB 开关上生产（建议先做"生产形态"（无域码）批次验证 tier-2）；独立法律复核人对接。

### 生产形态批次（2026-09-17 凌晨 02:00–02:20，"按你的建议先做"）

- 目的：生产**无域码**（tier-1 不触发）——验证 tier-2 实效（runner 新增 `--no-case-domain`，
  提交 `80f7169`；缺省行为不变）。
- **裁决：P1–P4、P6 达成**（报告 `dispatch-output/r1ob-prodform-20260917/report.md`）：
  - **P6：无域码下 tier-2 也消掉对照臂 1 例串台（1→0）**——"生产是否值得开启"的直接证据；
  - **P2：4/8 → 5/8**（唯一 per-case 差异 E05 被救回；n=1 不下因果）；P1/P3/P4 达成；
  - P5 不可判定：holdout 5 例恰逢**真实网络全断窗口**（02:07–02:08 全模型不可达）——
    机制正确应对；**无连锁**（对比上批“标死连锁”）。
- **41364db 修复获两个相互独立的现场实证**：本批 `failover_switch mode=transient`（上批为
  `permanent`）+ 连锁消失（失败只影响当次请求）。
- 建议：开关开启决策可考虑**灰度**（n=13/臂、单批次，效果量为小样本观测）；跑批前可加网络
  健康预检（本批未做）。
- 远端同步：`3d0c267`（LLM 修复）→ `138719d`（runner 生产形态）→ `dbb80b6`（review 修复）
  → `cfdf66c`（A/B 调查批）——远端 master 现值。

### A/B 调查批 + 法律复核材料（2026-09-17 下午，部署外待办清空）

- **A1 历史受影响复核** ✅：全 dispatch-output 日志扫描——修复前特征仅 2 批（1e 末尾无连锁、
  online 本轮自有）；**1e2–1e8/baseline-v2 等历史结论零污染**（`a1-historical-scan.txt` 含结论）。
- **A2 tier-2 归因（降级版）** ✅：四臂 removed 事件逐条归因——tier-2 生效场景=E01 型、生效面
  窄于 tier-1（2 vs 6）；**P6 的 1→0 不能归因到过滤机制**（E04 两臂均无剔除动作——已修订
  生产形态报告防 overclaiming；`a2-tier2-attribution.md`）。
- **A3 探针口径修正** ✅（9794eef+f4d908c）：k=6→4+cutoff 对齐生产；输出改
  `probe-results-k4.json`（**冻结资产 probe-results.json hash 实测未动**）；k4 合规基线首获：
  **召回 17/53=32.1%、污染 3/20**（与真实记录口径 43.4% 口径不同，不可混比）。
- **B4 实体法污染定位** ✅：疑似 60 条 → **人工判读真污染仅 ~8 条**（E02 保险法/消保法、
  E03 商业银行法、E04 消保法/劳动仲裁法、E05 证券法）；**100% 召回侧、writer 擅引=0**；
  规模小不值立项（`b4-entity-contamination-report.md`，自查口径标注）。
- **B5 网络健康工具** ✅（9794eef）：`backend/scripts/net_health.py`（check 预检 / report 跑后小结）。
- **教训**：`cmd | python -c` 管道吞退出码 → 曾提交未过 lint 文件（已补 f4d908c）——
  lint 检查禁止用管道吞退出码。
- **法律复核材料包** ✅：`dispatch-output/review-package-law-20260917/法律复核材料.docx`
  （5 例 E01–E05 干净终稿，中性脱敏 0 泄漏，法条核查表+总体判读+选做盲答；C05 因唯一终稿含
  GENERATOR_FAILURE 被防呆剔除）。**已交用户转复核人；回执回来后做三方对比出背书报告。**

### 开放项终版（2026-09-17 14:05）

1. **R1/R1-OB 生产开关**：暂缓（用户决策）；证据全备 + 开启手册固化于本文档；
2. **独立法律复核**：材料已交付用户，等回执 → 回执后三方对比；
3. **V8 剩余人测**：低优先，维持不做。

### 决策留痕：R1/R1-OB 生产开关「暂缓部署」（2026-09-17 02:53，用户决定）

- 用户在看过完整解释（三级证据链 / 开与不开的利弊 / 灰度现实含义 / 执行清单）后，
  决定**暂时不做部署**——两个开关保持默认关，生产行为逐字不变。
- 本决定不改变证据状态（离线 + 两形态在线均 PASS）；**未来若要开启，按下方手册执行**。

#### （备查）未来开启操作手册——R1/R1-OB 上生产

1. **代码侧**（进 git）：`docker-compose.yml` 的 backend `environment:` 白名单加两行透传
   （当前 compose 是**逐项白名单**，缺透传则服务器改 .env 也不生效）：
   `- AGENT_DEPT_FILTER=${AGENT_DEPT_FILTER:-false}`
   `- AGENT_DEPT_FILTER_R1OB=${AGENT_DEPT_FILTER_R1OB:-false}`
2. **本地**：`backend/.env` 加 `AGENT_DEPT_FILTER=true` + `AGENT_DEPT_FILTER_R1OB=true`，
   起后端跑真实问答验证：日志出现 `dept_filter_removed`（过滤真在跑）+ 回答正常。
3. **服务器**：根 `.env` 追加同两行 → `docker compose up -d backend` → 验证
   `docker compose logs --tail=50 backend | grep -E 'dept_filter|proc_misroute'`。
4. **观测三信号**：`dept_filter_removed` / `empty_retrieval` / `proc_misroute_flag`；
   **回滚**：根 .env 删两行 → `up -d backend`（≈1 分钟，行为逐字回到现状）。
5. 不变量：不改词表/阈值；不重建索引；开关仅影响检索时过滤。

### T-A5 / P5 重点复核包（2026-09-17，§7 追加）
- 已备 `outputs/p5-review-20260917/` 三份 Markdown/JSON 材料：匿名全文与判读表、后置四条重点判读、匿名回执。
- 5 案例×2 版本槽位，7 份全文逐字核验、3 个空终稿标材料不足；独立随机映射保留在 `dispatch-output/ta5-arms-20260917/p5-private/`，不对复核人分发。
- P5 尚未人工验收；E03 缺终稿导致三类错误覆盖不足。上一轮 P1 的 50% 混入不可比样本，撤回其判据裁决；引用差集也不是因果证据。保持生产开关不动。
