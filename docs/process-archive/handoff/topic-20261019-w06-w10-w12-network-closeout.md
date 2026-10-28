# 交接：W06 收口 + W10/W12 工程门 + 网络批（2026-10-19）

> 定位：current 交接快照。历史计划书（`docs/process-archive/superpowers/plans/2026-10-1*.md`）保持原样不改；真源读数在
> `reports/execution-runs/fazhi-full-closeout-20261018-af101aa9bca543b1a9c21fd0bace9780/task-status.json`（下称 RUN/task-status）。
> 候选对象：`.worktrees/nondeploy-closeout-20261010`，起点 HEAD `042f8090`；本轮新增本地提交见 §4。

## 1. 已完成（本轮 fresh 证据）

| 票 | 状态 | 一句话读数 | 证据（RUN 相对路径） |
|---|---|---|---|
| W00/Task0 | PASS | 对象冻结 + 三重守卫安全 runner | tickets/T0-task0-contract.md |
| W06-P0/C21-A/W06-B/W06-C | 完成 | create_candidate 一律 pending；有界选择 S01–S18；缓存依赖 P/O/W 复核 B01–B17；来源追踪/投影/摘要 CAS H01–H17 | tickets/W06-{P0,C21A,W06B,W06C}-report.md 等 |
| Task 10 | 完成 | **57/57 语义控制逐条对账** 136 passed rc=0；全量非 slow 2498/11/0 rc=0；ruff/mypy 绿（修 1 处本轮引入 mypy arg-type）；独立复核 1 主审+2 验证者 | tickets/W06-Task10-final-acceptance.md |
| W12 工程门（可做子集） | 完成 | coverage **88.67%**≥70（红canary 95⇒22.15% rc≠0）；ruff `.`/mypy `.` 76 文件绿；合成恢复→启动 28 passed；前端四门 rc=0；dispatch 守卫 9 passed | tickets/W12-engineering-gates.md |
| W10 网络批 | 完成 | pip-audit 三轴分级清单（runtime/dev 唯一发现 chromadb×2 无修复版沿 D-2；torch 2.13.0 审计 0 条；A 类 pip 已升清零）；Linux 闭包 CI 序 rc=0（135 wheels/0.35GB/0 nvidia）；D-45 审计（24/24 全 `==`，判据 4/4） | tickets/W10-network-closure.md，evidence/net/* |
| HF 权重 | 完成 | bge-base-zh-v1.5 → D 盘私有缓存 + junction 入沙箱；全量重跑 2498/11/0 与此前一致（证实隔离红为伪象） | evidence/net/full-nonslow-clean.log |
| W10 锁落库+续跑 | 完成（`c7a381f` push；续跑 2 笔本地） | 依 Owner「授权」并入候选：`backend/constraints.txt` + `ci.yml` `-c`（`c7a381f`，已 push）；续跑：Dockerfile 接 `-c`（`b406ab8`）+ requirements 锁口径注释（`187174f`）；隔离 venv 补测锁定 langsmith 0.14.11 边界（11 passed）；**2026-10-20 续**：隔离 venv 真装锁定闭包（`transformers 5.20.1` + 真 `torch 2.13.0+cpu`）→ CI 后端作业**等效门全绿**（ruff/format/mypy rc=0，pytest 非 slow **2498 passed / cov 88.58% / rc=0**），先前「交 CI」的 `transformers 5.20.1` 行为复测就此闭合；同日另**跑通真权重嵌入**（离线私有缓存 `bge-base-zh-v1.5`，199 tensors、768 维、确定性、语义序正确） | tickets/W10-lock-landing.md（§2.1）、evidence/net/w10-transformers-probe.log、w10-lock-landing-verify.log、w10-dockerfile-verify.log、w10-langsmith-probe.log |

## 2. Owner 已裁决（2026-10-19「照办」）

1. **`_input_qa_dependencies` 口径**：按**投影后**实际生成输入签名；`()` 对投影消毒后的输入是事实真话。设计合同 §4.1 已补带日期补裁句（本文件同日写入）；B07b docstring 补口径注记。产品代码零改动。
2. **Agent 未知观察**：维持现状不降级（未知=正常工具输出；memory 通道上游已消毒；失效观察已剔除）。
3. **pip 22.3**：venv-new 内升 **26.2.1**，A 类清零；requirements 零改动。
4. （更早，同日）网络批 6 域白名单、方案 C、HF 私有缓存、W10 三件套——见 tickets/W10-network-closure.md 授权节。

## 3. 未闭合（诚实边界，均有解除条件）

| 项 | 卡点 | 解除 |
|---|---|---|
| W08 真实五类 + 终轮 19 题 | 需真实模型/路径/专业签核 | Owner 配置后（W10 解析闭包已就绪） |
| W13 公开 push/PR | **已发布 + C14 已裁**（见 §4.1）；须独立 review 最终提交对象 | 待独立签核 |
| W14 现役切换/凭据/真实备份门 | Owner 专属动作 | Owner 择机 |
| docker build / Windows 包体 | vhdx 92GB 在 C（余 26.8GB） | Owner 迁 Docker data-root 至 D 后按 W12-gates Q3 补跑 |
| D-55 Chroma 副本对账 | 待核指定对象 | Owner 指认 |
| ~~传递依赖 lock 式冻结~~ | **本轮已闭合**（见 §6） | 已产出 136 条锁并**落库候选**（`backend/constraints.txt` + CI `-c`），`c7a381f` 已 push；续跑 Dockerfile `-c` + 锁口径注释（`b406ab8`/`187174f`，均已 push） |
| slow lane（真权重 lane B） | **本轮已跑**（见 §6） | 15 条语料类仍受禁读边界 |
| W03/W05/W01/W02/W04/W07 收口 | 各票残留（见 task-status） | 按 §5 顺序 |

**D-55/U12 hook 子项本轮已闭合**：共享 pre-commit 存在且与 2026-10-17 记录一致（暂存 .py → ruff check+format，尺子失明 fail-closed）；隔离正负空例 3/3（RUN/sandbox/hooktest）。附发现：ruff 0.17 对 **BOM 的 .py** 会 panic（钩子方向安全但报错难读）；post-checkout/post-commit 为空壳。未修改任何共享 hook。

## 4. 本轮 Git 动作（候选 C，本地）

按「照办+授权」执行，六笔本地提交（分支 `codex/nondeploy-closeout-20261010`；**前 4 笔已于 2026-10-19 依 Owner 授权 push 到公仓**，见 §4.1；第 5、6 笔 `b406ab8`/`187174f` 为 W10 锁续跑，**亦已 push**）：

| SHA | 内容 | 规模 |
|---|---|---|
| `e3f4f5a` | feat(W06)：产品代码（含新文件 qa_selection.py） | 18 文件 +1232/−110 |
| `bf2a44c` | test(W06)：57 项语义控制用例 + 旧契约迁移（9 只新测试文件） | tests 25 文件 |
| `17f0558` | docs(W06-P0/D-45)：登记表重生成 + requirements 注释勘误 | 2 文件 +7/−5 |
| `c7a381f` | chore(W10)：传递依赖锁落库——`backend/constraints.txt` 新增 + `ci.yml` Install deps 加 `-c` | 2 文件 +157/−1 |
| `b406ab8` | build(W10)：Dockerfile 接 `-c constraints.txt`（`COPY constraints.txt` + 两条安装分支） | 1 文件 +9/−2 |
| `187174f` | docs(W10)：requirements 锁口径注释更正（仅注释） | 1 文件 +6/−1 |

本地新 HEAD `187174f`（远端 `187174f`，2026-10-20 复核），工作区归零。**完整性证明（针对前 3 笔）**：35 个 tracked 文件的 `042f8090..17f0558` 子集 diff 与交付补丁 SHA **逐字节一致**（`5D90CDE0…`）；10 个新文件经 dev-tree 同步后 21 passed 覆盖；`git fsck --no-dangling` rc=0。未动主仓；**前 4 笔远端已于本日发布**（见 §4.1），第 5、6 笔本地提交并已发布。

### 4.1 发布结果（2026-10-19，报告 §5 修正声明）

- 依据 Owner 指令「发布 347 提交 + PR(base=origin/master)」执行：远端新增 `refs/heads/nondeploy-closeout-20261018` = `17f0558` = 本地 HEAD（`ls-remote`/`fetch` 已复核，字节一致）；`evidence/net/w13-push-ssh443.log` 末行 `SSH443_RC=0`。
- （2026-10-19 续跑，Owner「推送吧」）再推 1 笔：远端 `nondeploy-closeout-20261018` 由 `17f0558` **快进至 `c7a381f`**（`git push` 输出 `17f0558..c7a381f`，`ls-remote` 复核 = `c7a381f`，`PUSH_RC=0`，SSH over 443）。后续 W10 锁续跑两笔 `b406ab8`/`187174f` **亦已 push**。**（2026-10-20 更正）**：此前文档写「未 push」系陈旧说法——该通道用显式 URL（`ssh://git@ssh.github.com:443/...`）推送，按 git 语义**不更新本地 tracking ref**，故 `refs/remotes/origin/nondeploy-closeout-20261018` 停留 `17f0558` 属正常；经 ssh443 `ls-remote` 复核远端 = `187174f` = 本地 HEAD。
- ⚠️ 报告 §5 初版曾写「BLOCKED / 远端零变更」，**系核对前误判，已更正为「成功」**。
- **Owner 裁定（2026-10-19「1」）**：选①——**以已推分支为交付物，不做 PR**（无新增公开动作）；W13「发布 + PR/整合」子项就此闭合。
- **C14 公开范围同步裁定**（同日「你来帮我决策」）：**维持存量不动**——存量不删不改、远端旧 3 ref 保留、禁历史重写；唯一动作项＝Owner 核验 10-10「13 位裸值」现役性，若是则 W14 轮换口令。⇒ W13 全部子项闭合，状态转 FIXED_PENDING_REVIEW。

## 5. 建议下一步

1. W13：**已全部闭合**（发布 + review + C14 裁定），待独立签核；不再有未决子项。
2. W08 真实批（模型配好即开跑）；W03/W05 模型收口可并行。
3. 维护窗口迁 Docker data-root → 补 build/包体门。
4. W15 终局：**本轮已落盘**（见 §6），只剩独立签核与 Owner 专属项。

## 6. W15 收尾 + 两项残留闭合（2026-10-19 续跑）

三件新交付物（均在 RUN 根内，不改候选产品代码、不动主仓 M、无历史重写）：

| 交付物 | 路径 | 读数 |
|---|---|---|
| 五层结果清单 | `reports/results.md` | 语义控制/工程门/合成恢复/真实质量/实库发布 五层 + 逐票表 + Owner 裁决 + 未闭合 |
| 阶段门与工程门读数 | `reports/gates.md` | J1 IN_PROGRESS、J2/J3/J4/J6 NOT_STARTED、J5 BLOCKED_EXTERNAL；工程门逐项 + 红能力实证 |
| 工作汇报 | `reports/work-report.md` | 短摘要 + 完整字段/链接；含**尾部哨兵** `SENTINEL_TAIL_NEXT_OWNER=` 证明未被 230 字符静默截断 |
| 证据冻结清单 | `evidence/manifest.json` | 一次写：schema `fazhi.run-evidence-manifest/v1`，**件数取该文件的 `counts.entries`**（清单自指排除，故不复述件数与字节以免被每次重冻结绑架；2026-10-20 重冻结，新增 `evidence/net/w10-transformers-probe*.log`），raw + LF 双轴 sha256，禁名只按名计数不哈希，另记 `skipped_dirs`（路径级）与 `walk_errors`（非空即清单不完整）。精确字节数见其 `counts.total_bytes`——清单自指排除，故不复述以免被每次重冻结绑架 |
| 旧账对账 | `evidence/historical-manifest-reconciliation.json` | `R_20261016` 自有清单（449）⇒ SELF_CLOSED；`legacy_20261010` **无清单 ⇒ BLOCKED**；只做名字/大小扫描；R reports 窄口径 15 md/108 cited/82 present/26 absent |

**两项残留闭合（fresh 证据）**：

- **W12 slow lane**：默认 `-m slow` ⇒ **5 passed / 17 skipped rc=0**；开 `FAZHI_REAL_EMBEDDING_LANE=1` ⇒ **7 passed / 15 skipped rc=0**，转绿的 2 条即 lane B 验收本体。15 条语料类因真实 `chroma_db` 属禁读对象 + 守卫拒库外 sqlite ⇒ 仍 skip（诚实阻塞）。证据 `evidence/w12-slow*.log`。
- **W10 传递依赖锁**：离线解析两遍（无网络）⇒ **136 条 `name==version`**，逐包差分 **0**，`torch==2.13.0+cpu`、0 条 nvidia。**2026-10-19 依 Owner「授权」落库候选**：`backend/constraints.txt`（新建，唯一归一 `torch 2.13.0+cpu→2.13.0`）+ `ci.yml` Install deps 加 `-c constraints.txt`；离线复验 **V1 135/135 差分 0、V2 直接钉 24/24 命中、V3 dev 工具 dry-run rc=0**。**`c7a381f` 已 commit 并 push**（公仓 `nondeploy-closeout-20261018`，FF `17f0558..c7a381f`）。**续跑**（Owner「推送吧…并处理」）：`b406ab8` Dockerfile 接 `COPY constraints.txt` + 两条安装分支 `-c`（D1 静态接线 + D2 离线复解析 135 wheels rc=0，torch 仍 2.13.0+cpu）；`187174f` requirements 锁口径注释更正（仅注释）；**隔离 venv 补测锁定 langsmith 0.14.11 边界**（`_client_utils` 私有符号可调用 + `test_llm_lifecycle.py` 11 passed rc=0）⇒ 裁「0.14.7 为历史口径、现行以 constraints.txt 为准」；`b406ab8`/`187174f` 提交并**已 push**（远端 = `187174f`）；**2026-10-20 续**：`transformers 5.20.1` 行为复测改以**本地等效真实验证**闭合（CI 触发结构性不可行——`master` 无 `workflow_dispatch`、`push` 仅 `main/master`、无共同祖先致 PR 不可建）——隔离 venv 真装锁定闭包 + CI 后端作业逐字复刻：ruff/format/mypy **rc=0**、`pytest -m 'not slow'` **2498 passed / 11 skipped / 22 deselected**、coverage **88.58%** ≥70、dispatch-output guard **9 passed**，全部 rc=0（证据 `evidence/net/w10-transformers-probe.log` + `w10-transformers-probe-realweights.log`；诚实边界：宿主 Windows 非 ubuntu；真权重嵌入 lane 已于同日跑通）。证据 `evidence/net/transitive-lock-linux.txt`（SHA256 `2C6AF8E9…42D33`）、`evidence/net/w10-lock-resolve{1,2}.log`、`evidence/net/w10-lock-landing-verify.log`、`evidence/net/w10-dockerfile-verify.log`、`evidence/net/w10-langsmith-probe.log`、`tickets/W10-lock-landing.md`。

**未随本轮闭合（诚实保留）**：执行书历史计划书不改；旧 R/legacy 欠账保持 BLOCKED、**不用新根清单消旧账**；QA 请求/记录对账（277→140/141、154/279 分母）需授权样本，本轮**未交付**；旧清单工具（`build_run_manifest.py` / `manifest_closeout_c20.py`）**未重跑**。

**新增工具**：`tools/w15_build_manifest.ps1`（ASCII-only，规避 PS 5.1 无 BOM 中文乱码 + `@()` 于 `List[object]` 的 `PSEnumerableBinder` 崩溃）、`tools/w15_old_roots_recon.py`。

**独立复核（TRAE-code-review，1 主审 + 2 并行验证者；2026-10-19）**：抓出并已修正 4 条成立问题（另有 1 条未获验证者确认、按低置信排除）——

1. 对账产物 `唯一例外` 硬编码「顶层 34 个报告」与同产物 `md_files_scanned=15` 自相矛盾（数字编造）⇒ 改为按实测动态生成。
2. 对账产物 `读法` 声称「没有打开任何旧根文件做内容读取」，但脚本实为判定 SELF_CLOSED 会 `json.load` 旧根 `evidence/manifest.json` ⇒ 改为显式列出两处读取例外（含实测读取只数）。
3. manifest 只记被跳过目录的**名字**不记路径 ⇒ 增记 `skipped_dirs`（路径级），使被丢弃子树可回溯而非静默。
4. manifest 的 `Walk` 无异常处理（不可读目录会中止整次生成），与 recon 的 `OSError` 容错不一致 ⇒ 改用 `GetDirectories/GetFiles` 让异常可就地捕获，并新增 `walk_errors` 字段（非空即表示清单不完整，fail-loud）。

另修正一处**陈旧数字**：文档/真源原引 manifest「105 件 / 1,817,688 字节」为首冻结读数，重冻结后即失效 ⇒ 现改引「107 件」并把精确字节数交给 `counts.total_bytes`（清单自指排除，避免文档被每次重冻结绑架）。重冻结后对全部 **107** 条做独立 `Get-FileHash` 复算，**0 条不符**（2026-10-20 再重冻结 → **113** 条，独立复算 **113/113 相符、0 miss**）。

**本轮 W10 交付的独立验收复核（2026-10-19）**：报告 `docs/process-archive/reviews/2026-10-19-w10-lock-landing-independent-verification.md`（M 仓 **untracked**，不在 run 根 manifest 扫描范围；**单一正本**，不在 `…-audit.md` / `…-audit-round2.md` 内重复）。方法＝1 主审 + 2 并行独立验证者；结论 **12/12 声明成立、0 反证**；红能力差分成立（约束副本 `langsmith 0.14.11`→`0.0.1` 变异后离线解析 `ResolutionImpossible` rc=1 / 0 wheels）；无真发现。**四项未闭合**：真 CI（`master` 无 `workflow_dispatch` + PR 不可建）、真镜像（磁盘 `BLOCKED`）、Linux 真跑、`transformers 5.20.1` 行为复测——**其中第四项已于 2026-10-20 以本地等效真实验证闭合（本文件 §1/§6 增量；该报告正文未改，待签核时以上述增量为准，剩三项不变）**；签核栏留空待指定独立审核人 `haimeng`。
