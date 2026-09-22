# 工作进度交付报告（2026-09-16，session3 续）

> 定位：存档 + 接手两用。覆盖 2026-09-14 报告（`work-progress-20260914-session3.md`）之后至 2026-09-16 本会话结束的全部工作，不重复上份报告内容。
> 口径：**C 口径**——每个数字/结论标注【实测】（本会话亲跑命令与输出，可复现）或【转抄】（引自历史记录/提交说明，本次未重跑）。每项工作附验证命令、提交号、证据路径与已知限制。
> HEAD 演进【实测，git log】：交接基准 `fa150d4` → `5677e8e`(T1) → `8353821`(T2) → `2e6b1a6`(审查修复) → `f305799`(smell 收口) → `b5fab33`(R1-OB 预注册) → `1be944c`(R1-OB 离线验证)；远端快照 `602fde3`。
> 本会话成本：**0 元**【实测——全程无付费模型调用；T3 自查与 R1-OB 离线验证均为既有数据离线作业】。
> 在库轨迹：交接书 `final-agent-mainline-handoff-20260916.md` §13 执行记录 1–7；本报告为汇总视图。

---

## 一、工作线一：交接书 T1–T4 执行（主体）

依据 `docs/final-agent-mainline-handoff-20260916.md`（基线 fa150d4），四张票据全部完成，§7 验收表 A1–A7、B1–B3、C1、D1/D2 全部满足；**C2（独立律师验收）为唯一开放项**，外部待办，按 §12 约定不由执行助手关闭。

### T1 覆盖状态契约（提交 5677e8e）——验收项 A1–A7

- **契约设计**：`LegalAgentState.uncovered_issues`（有界/唯一/必须引用既有争点）为事实源，completed 的 `AgentRun.state_json` 落库；`Message.agent_run_id` nullable 关联（migrations 幂等补列，无新迁移框架）；`AgentPublicResult` 校验器强制 completed 必须显式携带 coverage_status，full⇔空列表、partial⇔非空、其余 outcome 禁带（A1–A3）。
- **历史兼容（A5）**：`coverage_from_state_json` 纯函数投影——T1 之前的 run 缺键→"unknown"，**不得推断 full**；损坏 JSON 一律 unknown 不抛异常；用户消息→None。
- **实时/历史一致（A6）**：SSE final 事件透传结构化覆盖；`get_conversation` 批量投影（`AgentRun.id.in_()` 单查询防 N+1）；前端 `lib/coverage.ts` 纯函数两端共用，防文案漂移。
- **顶部提示（A7）**：partial 警示条渲染在答案正文之前（MessageBubble）。
- 验证【实测（当时运行）】：`pytest -m "not slow"` → 1081 passed（基线 1078+3）；`vitest run` → 41 passed（+8 覆盖契约测试）；契约断言含 4 个 ValidationError 场景。
- 已知限制：他人未跟踪 WIP（`app/admin/sections/`）致 tsc 全量 3 错（T1 触及文件 0 错误）。

### T2 法律依据收窄（提交 8353821）——验收项 B1–B3

- **规则**：§4 法律依据 = `canonical_citations(claim.text) ∩ canonical_citations(绑定证据 source_ref)`——正文未引用的已绑定条文不再展示（1e9 实测冗余 8/13、4/5 消除的根源）；顺序 = claim 顺序 × 正文首次引用顺序（`canonical_citations_in_order`，与核验同一解析真源）；跨 claim 去重；不从整篇答案提取（防自匹配）。
- **安全边界（B3）不放宽**：正文引用但未绑定的条文仍由 verifier 的 FABRICATED_CITATION 拦截。
- **离线重放【实测】**：从 1e9 evaluation.sqlite 的 agent_claim_checks + state_json 重建渲染（不重新请求模型），两份终稿法律依据 ⊆ 正文引用∩绑定证据 PASS，冗余 r1 13→4 条、r2 5→1 条；脚本 `dispatch-output/agent-quality-1e9-20260916/replay_legal_basis_t2.py` 可复现。
- 验证【实测（当时运行）】：`pytest tests/test_agent_verifier.py tests/test_agent_writer.py` → 87 passed。
- 已知限制：非成文法证据（source_ref 无条号）仅在正文可解析引用时展示。

### T3 两份 1e9 终稿四维自查——验收项 C1

- 产物：`dispatch-output/agent-quality-1e9-20260916/legal-self-review.md`，逐争点四维表格（PASS/REVIEW/FAIL + 正文片段定位），素材 = sessions.json 终稿 + evaluation.sqlite claim_checks，未重新请求模型。
- **发现**：r1 争点 3 法律适用 FAIL——终稿混入 37 条、劳动法 31 条，**把劳动者辞职预告条款错用为公司解除情形**（正确依据应为劳动合同法 §40(2)），属生成层错误；法律依据混入无关部门法，根因定位为检索污染（`required 法条召回不足`同族），需独立立项，不在本交接书范围。

### T4 最终验证——验收项 D1/D2

- 【转抄（当时运行）】`pytest -m "not slow"` → 1084 passed；ruff/mypy/vitest/tsc 门禁运行。
- **重要修正**：T4 时点"mypy 全绿"汇报后被证实为**假绿**（详见 §六 失误留痕第 1 条）；本报告的最新真实门禁见 §八 总表。

---

## 二、工作线二：git 历史损坏修复与新鲜验证

- **诊断【实测】**：`git fsck --full` 报 10 个缺失对象/4 条断链，且损坏持续恶化（两个 blob 在 09-14 尚以 loose 存在，此后丢失，疑似历次失败的 geometric repack 半途清理 loose 所致）。修复前基线备份 `.git-backup-20260916/`（134 MB）。
- **修复【实测，哈希级验证】**：
  - 6 个缺失 blob 从工作区按原内容 `git hash-object -w` 恢复，**哈希与原值完全一致（零失真）**；
  - 4 条断链经 refs/replace 接通：`0c1eb0c` graft 截断（其原始父 `03a2f140` 物理永久缺失——备份与远端均无）、`01d9b1b`/`3c6c444`/`0663dae` 替身 commit（3c6c444 树精确重建无失真；01d9b1b 时间戳近似；0663dae diff 为空但改动结果存于后续树）。
- **新鲜验证【实测】**：`verify_repair.py` 7/7 PASS（fsck 无新增丢失、log 108 提交全链、3c6c444 diff 精确、repack exit 0、测试提交零 error、HEAD 与工作树正确），一条命令可复现。
- **残余限制**（全部已知且不影响日常操作）：fsck 仍报 6 条被替换对象/不可达考古层的 broken link；被替换的物理缺失对象不可按短哈希直接引用（V4a 抓到的边界）；`0c1eb0c` 以下早期历史从 master 不可达；commit-graph 写入已禁用（.git/config 三项，writer 不走 replace，勿恢复）。
- 证据：`dispatch-output/git-repair-20260916/`（repair-report.md、check_tree.py、repair_history.py、verify_repair.py）。

---

## 三、工作线三：双轴代码审查与系统性调试处置

用户指令"T1→T4 工作审查一遍"：code-review 双并行子代理（**Standards 轴** = docs/code-review-standard.md 成文标准 + Fowler 坏味道基线；**Spec 轴** = 交接书 §4/§6/§7/§8）+ systematic-debugging 先取证后处置。

| 来源 | 发现 | 处置 |
|---|---|---|
| Standards | ruff exclude 假绿：verifier.py/chat_integration.py 仍在 exclude 内，此前"ruff 全绿"实为被跳过 | 两文件从 exclude 删除（履行解冻留痕义务），`--no-force-exclude` 验证真实干净【实测】 |
| Standards | mypy var-annotated override 未按注释义务删除 | 删 override + verifier 补注解；发现 mypy 对该文件实际零报错 |
| Spec | T2 防自匹配有实现无测试 | 补 `test_render_draft_text_legal_basis_no_self_match`（直接构造 DraftAnswer 绕过 writer 校验） |
| Spec | A6 历史投影序列化脆弱点（字段名硬编码于断言之外） | 补 `'"uncovered_issues"' in state_json` 断言锁固 |
| Standards | 疑似违反 1e9 候选锚定 | **撤销**：candidate-hashes.json 证据证明 chat_integration.py 不在锚定清单内 |

- 修复提交 `2e6b1a6`（5 文件 +53/−14）【实测】；处置后门禁 pytest **1085** passed（+1 = 新增自匹配测试）。
- 判断性 smell 4 项后续处置（f305799）：2 修复（`CoverageProjection` 类型别名收口魔法串；`coverageFromFinalEvent` 纯函数收口 api.ts 三元链，行为逐字等价 + 4 测试）、2 豁免留痕（chat_integration 多职责属边界内聚；coverageFromMessage 静默归 null 是预期态非异常）。

---

## 四、工作线四：R1-OB 预注册与离线验证 PASS

- **预注册（b5fab33）**：`docs/preregistration-dept-guard-r1-optionB-20260916.md`，判据先于实现冻结。R1-OB = 判域输入扩展（非 R1 复活），三级输入：tier-1 案例域码直判 > tier-2 用户原始问题+issue 问句确定性拼接 > mixed/零指示→None 不过滤（保守语义与 R1 逐字一致）；`dept_guard.domain_of_text` 与指示词表**零改动**（防过拟合循环）；**离线反例验证前置，FAIL 即冻结（止损线 0）**；P1–P6 判据复用 R1 框架，留出集 H01–H05 必答；付费在线批次（≤0.5 元）须离线 PASS 后另行申请。
- **验证前勘误（已在预注册留痕）**：初稿把 E01/E04 期望域写成 administrative，系撰写时记忆失真；以 `frozen-cases-v2.json` 案例定义（forbidden 均为他域程序法/刑法、required 均为民事实体法）修正为 **civil**，判据不变。
- **离线验证（1be944c）【实测，exit 0】**：脚本 `evals/validate_r1_ob_offline.py`（导入生产 dept_guard 单一真源），三部分：
  - P0 基线复现：与 `filter-simulation-r1.json` 存档逐字段一致（forb_killed 5/req_killed 0/…）——重放器可信；
  - P1 反例（真实 run 数据，app.db conv 2388/2391）：**E01 tier-2 即修复**（旧口径 4 个 issue 中 2 个零指示词→None→不过滤，拼接后 4/4 civil）；**E04 tier-2 不足实证**（issue 2「行政决定」指示词主导，用户原始问题零指示无法对冲）→ 仅 tier-1 域码可修复，**D2（harness 提供域码字段）从待确认口径升格为实现硬前提**；池级证据坐实（E01 池含行政诉讼法、E04 池含行政诉讼法+行政复议法）；
  - P2 回归（20 案例）：required 误杀 **0**、forbidden 漏杀 **0→0**、杀死 5→5 保留；6 例判域翻转**全部零行为影响**（removed 集合逐例相等，无激进翻转）。
- **已知限制**：P2 的 tier-2 输入为代理（探针数据无 issue 问句）；frozen-cases-v2.json 现状无域码字段（tier-1 验证按设计假设置值）；E04 的 frozen forbidden（刑法 133）为实体法，超出 R1-OB 设计范围（writer/verifier 层管辖，非缺陷）。
- 证据：`dispatch-output/r1-ob-offline-20260916/`（report.md、validation-result.json、counterexamples.json、extract_counterexamples.py）。

---

## 五、工作线五：推送危机与快照同步

- **发现【实测】**：push 前取证发现双重阻塞——(1) 网络：github.com:443 时通时断（connection reset/超时/502）；(2) **历史分叉**：`git merge-base master origin/master` 为空——git 修复的 graft 把 `0c1eb0c` 截断成根，本地与远端呈现为无共同祖先的两条历史，普通 push 必被拒。
- **修复尝试与证伪**：re-graft `0c1eb0c`→远端 tip `15562fc` + filter-branch 物化（替换 refs 物化为真实父链，**树逐字一致**【实测，master^{tree} 前后同为 c343d187】），dry-run 显示 fast-forward 可行；但真实 push 暴露发送集含 **2 个永久缺失 tree**（`02b3c7d2` backend 子树、`03a29ff2`，被 27bdb47 等提交引用）→ 失败。**repair report §4.1「不影响 push」声明被证伪**（从未用 dry-run+`--no-replace-objects` 验证过）。
- **三选项论证**：伪造缺失 tree 内容再改写历史（拒绝——哈希会变，违反审计锚纪律）；force push（拒绝——使远端 192 提交历史线失去引用）；**快照 squash push（采用，经用户授权"按推荐来"）**。
- **执行【实测】**：`602fde3` = commit-tree(当前完整工作树 c343d187, parent=15562fc)，发送集 1824 对象经 `rev-list --objects --missing=print` 验证**零缺失**，dry-run FF 后真实 push 成功（后台任务日志 push_exit=0；任务的 exit 128 是随后的 ls-remote 撞 GitHub 502 瞬时错误，与 push 无关，已复验 `ls-remote` = 602fde3）。
- **现状**：远端 master = `602fde3`（快照，含完整内容备份与溯源说明）；本地 master = `1be944c`（**领先远端 1 个提交**：R1-OB 勘误+验证批，快照在其之前制作）；本地 111 提交完整历史保留。
- **可选项**：完整历史直推需先从其他 clone/备份找回 2 个缺失 tree（`02b3c7d218eb908c85d72186aaaa96d0cd74575d`、`03a29ff20c49712855bc1b3b8d36177042b0a6b2`），不再阻塞任何工作；下次远端同步沿用快照机制（commit-tree parent=origin/master）即可带上 1be944c。
- **红线**（全程遵守）：未用 --force；未伪造历史对象。

---

## 六、失误与自我修正留痕（专节）

以下均为本会话发现并已修正/留痕的事实，**下一任不得把被证伪的旧声明当作已验证事实引用**：

1. **mypy 假绿（T4 时点）**：T4 汇报"mypy 全绿"，实际 main.py 存在 2 个类型错（T1 引入的 `Column[str]` 作 dict key → [index]/[call-overload]），T4 时点未被发现。发现方式：f305799 批次给 `coverage_from_state_json` 换 `CoverageProjection` 别名时暴露；`git stash` 验证实锤该错在 HEAD=2e6b1a6 即存在（非本轮引入）。修正：`str()` 运行时等价收窄，mypy 66 files 真绿【实测】。影响：交接书 §13 记录 4 的门禁声明部分失真，已在记录 6 如实纠正。
2. **R1-OB 预注册期望域写错**：初稿 E01/E04 期望域 administrative，数据核对证明均应为 civil。修正于验证执行前，预注册文档留勘误注，判据不变。教训：预注册中的示例值也必须可溯源到案例定义，不能凭记忆写。
3. **repair report §4.1「不影响 push」证伪**：该声明从未经 dry-run+`--no-replace-objects` 验证；真实 push 失败（bad tree object）暴露。修正：快照方案绕过 + 本报告与交接书如实记录。教训：对象级修复的"无影响"结论必须用发送集枚举验证，不能只验工作操作。
4. **（历史遗留，本会话复认）"连续 3 次测试提交零报错"**：实际第 1/3 次干净、第 2 次报 geometric-repack 失败；已由 verify_repair.py 7/7 新鲜验证取代旧口径（上周期 show-your-work 审计修正，本会话沿用其结论）。
5. **流程改进生效**：上周期"报告文件名撞名"教训已制度化——本报告命名前先 Glob 查重（work-progress-20260916-session3.md 无撞名）。

---

## 七、前端执行书接手登记（他人工作，本会话仅登记未执行）

- 执行书 `docs/frontend-execution-book-20260915.md`（基线 f0f9cc9，他人执行中断，用户指定后续由本会话接手）。
- **进度核对【实测，git log + 文件系统】**：T0.1–T2.3/T2.5 已提交完成（a39525d…d485b16 共 13 个提交；T2.0/T2.1 合并于 3723a22，lib/constants.ts 内容与执行书清单逐项齐全）。执行者计划图中"T2.1 未勾"为**滞后标记**，非真实待办。
- **真实剩余 = T2.4 admin 拆分收尾**：6 个 section 文件已写（`app/admin/sections/`，未跟踪未提交）但 admin/page.tsx（846 行）未集成；UploadSection 引用 lib/types 不存在的 `ChunkPreview` 导出 + line152 两处 implicit any（当前全仓仅有的 3 个 tsc 错误来源）。
- 审查发现 3 条：T1.1 方案偏差已留痕（`/_next/static/BUILD_ID` 404 → postbuild 桥接 build-id.txt），接手时需核对 postbuild 链路并确认 build-id.txt 已 gitignore；超书 hooks 2 个（useVoice/useLawCards）属合理归位放行；其 T2.2/T2.3 重构与本会话 T1 覆盖契约两线已验证兼容（vitest 45/tsc 0 错）。
- 已登记：project memory Pending Handoff 节 + 本会话 todo（f1，待用户指令启动）。

---

## 八、交付状态总表

### 提交索引（本会话，全部在本地 master）

| 提交 | 内容 |
|---|---|
| 5677e8e | T1 覆盖状态契约（A1–A7） |
| 8353821 | T2 法律依据收窄（B1–B3） |
| 2e6b1a6 | 双轴审查修复（解冻配套 + spec 缺口） |
| f305799 | smell 收口 + mypy 假绿修复 |
| b5fab33 | R1-OB 预注册（判据冻结） |
| 1be944c | R1-OB 勘误 + 离线验证脚本（PASS） |
| 602fde3 | 远端快照（远端 master 现值；本地无 ref 引用） |

### 门禁矩阵（最新【实测，本会话 16:34 前后新鲜运行，1be944c 工作树状态】）

| 检查 | 结果 |
|---|---|
| `pytest -m "not slow"` | 1085 passed, 18 deselected |
| `ruff check .` | All checks passed |
| `mypy .` | no issues in 66 files（真绿，含 main.py） |
| `vitest run` | 45 passed |
| `tsc --noEmit` | 0 错误（他人 WIP 移出项目外验证后原位恢复） |

### 未跟踪文档/证据清单（共享工作成果，不得删除）

docs/：final-agent-mainline-handoff-20260916.md、work-progress-20260914-session3.md、work-progress-handoff-20260916.md、本报告、project-quality-guide-20260914.md 等；dispatch-output/：git-repair-20260916/、r1-ob-offline-20260916/、agent-quality-1e9-20260916/ 等全部证据目录；frontend/app/admin/sections/（他人 T2.4 WIP）；.git-backup-20260916/（134 MB 备份，稳定后可删）。

### 未推送到远端的内容

本地 1be944c（R1-OB 勘误+验证批）领先远端快照 1 个提交；全部未跟踪文档不在远端（快照只含 tracked 文件）。

---

## 九、下一步建议（按优先级）

1. **C2 独立律师验收**（交接书唯一开放项，外部待办）：对 1e9 终稿与覆盖契约语义做独立复核。
2. **R1-OB 付费在线验证前置链**（已批准方向，启动需拍板）：D2 域码字段落地（harness 案例对象 + bootstrap 透传）→ R1-OB 实现（legal_retrieval.py + service.py 判域输入构造，dept_guard 零改动）→ 在线批次申请（≤0.5 元，P1–P6 判据冻结）。
3. **前端 T2.4 接手**（已登记，等指令）：补 ChunkPreview 类型 → 修 implicit any → admin/page.tsx 集成（846→≤250 行）→ V1–V8 门禁 → 独立提交。
4. **远端同步**：下次快照把 1be944c 带上远端（一条 commit-tree + push，注意网络重试）。
5. **检索召回质量立项**（已批准"先规划书后 grilling"）：required 法条召回不足，与 R1-OB 解耦。
6. `.git-backup-20260916/` 再观察几个提交周期后可删。

---

## 附：已知限制汇总（跨工作线）

- git：完整历史直推被 2 个永久缺失 tree 阻塞（可选项）；被替换对象不可短哈希引用；commit-graph 禁用；fsck 残留 6 条无害 broken link。
- R1-OB：仅为预注册+离线验证，未实现未付费验证；E04 型修复硬依赖 D2；tier-2 对「用户问题零指示+issue 带他域指示词」形态失效（E04 实证）。
- 质量：C2 独立律师验收未做（终稿质量结论均属实现者自查口径）；r1 争点 3 法律适用错误与检索污染为生成/检索层结构性缺口，工程侧已定位待立项。
- 协作：文档与证据目录多数未跟踪（沿既有状态）；远端与本地历史线不同（快照机制），他人 clone 后看不到本地 111 提交考古史。
