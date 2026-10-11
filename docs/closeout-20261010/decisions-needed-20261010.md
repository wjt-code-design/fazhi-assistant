# 待你裁台账（2026-10-10 非部署收尾轮）—— 每条一词可答

口径：只列**现在真的还没定**的。已裁过并执行完的放在最后一节，不再问你。
每条都给了现量证据的位置，你要查就按那条命令查，不必信我的转述。

## A. 已裁，但只剩你手上的动作（我不代做，也不代签）

| 编号 | 已裁成的形状 | 为什么我不能推进它 | 你可以答 |
|---|---|---|---|
| **D-5 凭据与推送** | 按推荐＝先轮换 `ADMIN_PASSWORD`，再普通 `git push` + 开 PR | 轮换只能你动（我不读 `.env`、不碰凭据）；推送与开 PR 是共享状态动作，没有你那一键我不做。连带两条已在册：① 推 `codex/*` 本身不产生 CI 读数（`on.push.branches` 只列 main 与 master，10-11 重核过），要第三方验证就得连开 PR 一起做；② 远端主线历史 push 全红，别把 CI 红当成这笔候选的判决。逐条前置与命令在 `tickets/runbook-I-push-pr-merge.md`（已刷到 10-11 现量） | 「已轮换，推+开 PR」/「走无父快照备选」/「先不推」 |
| **D-19 文档 ref 一起推** | 按推荐＝一起推 `codex/local-candidate-closeout`（现量：仓库内 `git grep -o fbc29e8` = 103 次引用 / 15 个文件，而该尖端 `fbc29e8` 不是 master 的祖先（`merge-base --is-ancestor` rc=1）、这支从未推送 ⇒ 不推就是 103 处在远端悬空） | 同一个动作、同一把钥匙：它也是一条 push，排在 D-5 之后。两条已核的连带事实：只多 4 笔独联提交（`rev-list --count 候选..closeout` = 4），且**不新增凭据外泄**（按值反查 closeout 对象集 value_hits=1，候选里也已是 1） | 「随 D-5 一起推」/「只推代码支」 |

## B. 不卡交付、但答了我就能继续动手的

| 编号 | 一句话 | 现量证据 | 我的推荐 | 你可以答 |
|---|---|---|---|---|
| **D-33 409 的 step_budget 档今天走不到** | 这档文案留着还是把不可达的站点删掉？ | 复核 B 打出来：DB-15 起 `(WAITING_USER→PLANNING)` 在 `agent/state_machine.py:29-36` 的 `FREE_STEP_EDGES` 里不计步，`transition` 的 `_limit(steps)`（同文件 `:60-62` + `:74-77`）在这两个 raise 站点不会炸 ⇒ `ResumeRunConflict("step_budget")` 实际不可达（预算被调小或持久状态越界时仍可能命中）。真正的追问轮数上界是 `max_clarifications`，它耗尽走 `CLARIFY_BUDGET_EXHAUSTED`、不落 409。复算：`grep -n FREE_STEP_EDGES backend/agent/state_machine.py` | **本轮只改准措辞并就地标注**（文案已换成「这次任务可用的处理步骤已经用完了」，不再说「追问次数」；站点保留不删）。下一轮二选一：① 删两个不可达站点；② 让 `max_clarifications` 耗尽也进这条码并配测试。判据盲区写明：AST 全覆盖只保证「每个成因码有一档」，不保证成因码可达 | 「本轮只标注」/「现在就删站点」/「让澄清耗尽并进来」 |
| **D-34 Agent 轮次没有占位补偿腿** | 要不要给 Agent 路径也配成对性补偿？ | 复核 B 的新发现（**不是本轮引入**）：`_agent_streaming_response`（`backend/main.py:836`）用裸 `StreamingResponse`，没有 `on_response_close`；assistant 行只在 DRAFTING→COMPLETED 的 CAS 里写（`backend/agent/chat_integration.py`），而用户行早在 bootstrap 落库 ⇒ Agent 轮次被取消/失败时可能留下**没有配对 assistant 的用户消息**，正是快车道上花力气堵的那个形状（对抗审计 v2 #5/#8）。复算：`grep -n on_response_close backend/main.py` | **本轮不动**：它要自己的用例集（成对性、message_count、不重复落），且刚被复核钉过的取消面不宜在同批里二次改动。要么并入 D-14 那张票，要么另开 | 「并入 D-14 票」/「另开一张」/「先只做读数」 |

> 这两条是复核 A/B（10-11 06:5x）之后新问出来的，发现时间在上一次整包授权**之后**，所以不并入已裁。
> 上一批离场 15 条（§A/§B 由 18 降到 2），本批加回 2 条 ⇒ 等你动的现在是：§A 两条推送动作 + 本节两条。
> 各档现数不要引用本节措辞，用脚本现读：`evidence/ledger_row_audit.py`（按 §A/§B/§C 切段，抽编号，报重复与缺号）。
## C. 已裁过、已执行完（不再问你，只作对账）

| 编号 | 内容 | 落地位置 |
|---|---|---|
| D-1 | `agent/state_machine.py` 解冻并保留 DB-15 改动 | `backend/pyproject.toml` ruff exclude 3→2 + 解冻记录；格式化前后 **AST 等价**已证（`evidence/state_machine-format-ast.json`）；提交 `5ca3315` |
| D-2 | chromadb 两条残余风险「在册接受 + 失效条件」 | 复用 10-03 那份风险册（不新建第二份）；候选复扫：0.4.24 两条 `fix_versions` 空、1.5.0 反成 5 条 |
| D-3 | langchain 族 13 个 ID：BLOCKED，另开跨大版本迁移票 | `reports/gates.md` C 行；未动任何调用面 |
| D-4 | DB-19 回落**收窄** | `backend/retrieval.py` + `observability.py` + 新测试 9 条；变异仪 M1/M2 双向红（`evidence/category-mutants.log`） |
| — | B-45 `import_laws` CLI 守卫 | `backend/scripts/import_laws.py` + 新测试 4 条（子进程真跑 CLI）；变异 M1 删守卫 ⇒ 恰好红在分歧腿 |
| — | E.2 加载信任门 / E.3 合成备份恢复演练 | `reports/trust-and-data-drill.md`；行为级五臂 `GATE_HOLDS` + 入库 4/7 条 + 两台变异仪 |
| D-26 | D-3 跨大版本迁移票派给谁 ⇒ Owner 答「新会话」（10-11 01:5x） | 票 `tickets/dispatch-D3-langchain-migration-20261011.md`（8 节，含并发纪律）；分母与符号面两根轴都随票落盘（`evidence/audit_axes.js`、`evidence/d3_symbol_surface.py`） |
| D-27 | 独立复核腿怎么办 ⇒ Owner 答「新会话」（同上） | 票 `tickets/dispatch-independent-review-20261011.md`（5 节 / 7 颗钉子 / 只读约束）；本会话已停派 agent，结果将并进 `closeout-final-J-draft.md` §5 |
| D-13 | 并行会话那 5 只 `frontend/` 改动的处置 ⇒ Owner 先答「等 D」，D 交回后按 hunk 整合 | **已执行**：D 验收「6 绿 1 红」后落第五笔 `9e3cfc5`（5 文件 `+69/−7`）；提交前用 `git apply -R --check` 与「纯净 HEAD 重放 ⇒ 5/5 blob 相等」自证；现量候选树 `porcelain=0` ⇒ 盘上那份不再处于「只活在磁盘」状态 |
| D-21 | 「§14 那份从没进过任何提交」的整合动作 | **已执行**（同上，第五笔 `9e3cfc5`）；证据 `evidence/frontend-dirty-20261010.patch` 与 `.manifest`。**注意 J3（生产构建 purge 徽章类名）没有随这笔修掉**，那是 D-22，另开票 |
| D-22 | J3：生产构建把四个 `badge-*` 类名 purge 掉 | **已执行并闭合**（Owner 裁「按推荐」→ 本会话自验）：`ui.tsx` 改静态映射 + 新增 `npm run build:check`（带 INERT 判据）+ CI 既有 Build 步并入；提交 `842ef0b`、`0d3d662`。产物层 0/0/0/0 → 1/1/1/1；变异臂只让被改那一类变 0 |
| D-28 | D-22 暴露的徽章配色 AA（前景压自己浅底只有 1.42–4.01）怎么裁 | **已裁 (b) 并已执行**：前景统一 `--ink`，差异交给底色 + inset 环（不用 `border-left`：胶囊会弯成碎片且撑高 2px）。复量 **11.15 / 11.22 / 10.30 / 5.70，全部 ≥4.5**；按「底色+环」两维 6 对里相同 0 对；提交 `033cd3d`。同一把尺子本轮出现三态（全同→红 / AA 不达→红 / 现在→绿）⇒ 它不是恒绿的 |
| D-12 | 本轮交付物要不要入库 | **已执行**：`docs/closeout-20261010/` 现量 **32 只 `.md` 全部 tracked**（10-11 06:5x；这数随每轮交付增，读法 `ls docs/closeout-20261010/*.md \| wc -l` 配 `git ls-files -- docs/closeout-20261010 \| wc -l`，两数相等才算入库）（随 4 笔 docs 提交入册；未含 `evidence/`、`candidate-env*`、`synthetic/`）。入库前三检留痕：逐只 CR=0；凭据形状复扫 `sk-`/AKIA/JWT/PEM/URL-in-creds 命中 0，13 位形状 45 处全是普通标识符、与参照值相同 0 处；`git diff --cached --name-only` 自证未夹带 |
| D-6 | 开发环境对齐怎么办 ⇒ 已开票，本轮不动宿主机 venv | 票 tickets/dispatch-D6-dev-env-alignment-20261011.md（7 节）。10-11 现量：对【候选】requirements.txt 偏离 6 只（fastapi 0.110.3 / uvicorn 0.52.1 高于上限 / sentence-transformers 2.7.0 / sqlalchemy 2.0.51 / pypdf 6.14.2 / torch 2.6.0+cpu），pip check 既有 2 条红；⚠️ 同一条命令读【主仓旧那份】只得 4 条偏离（那份没有 torch 行、sqlalchemy 下限还是 >=2.0）⇒ 报数必须点名读哪一份。尺子 evidence/venv_vs_requirements_axis.py，读数 evidence/d6-venv-axis-20261011.txt |
| D-8 | DB-19 的 category 字段摘不摘 ⇒ 已裁：不摘 | Owner 10-11「都交由你的推荐执行」＝采纳维持现状；schema 与回落形状未动，category_filter_* 三字段读数继续存在。零代码改动 |
| D-9 | DB-22 拒答冷却分档 ⇒ 已执行并测到 | backend/llm_registry.py：REJECT_COOLDOWN_BY_STATUS（401/403/404 = 3600s）+ reject_cooldown_s() + reject_kind() + ModelEntry.rejected_kind；status() 每行带 rejected_kind（config 与 shape 分得开）；两字段登记进 observability._ACCOUNT_FIELDS。新增 3 条用例（tests/test_llm_reject_channel.py）。负向自证：M1 把长档塌回 300 ⇒ 杀 2 条；M2 取消登记 ⇒ 杀 2 条（含 AST 哨兵那条）⇒ evidence/batchA-mutation-20261011.log |
| D-10 | DB-23 的 409 文案 ⇒ 已执行，且实拆成 4 档（台账原写三条） | backend/agent/controller.py：RESUME_CONFLICT_DETAILS 成因码表 + resume_conflict_detail()（未登记码回落旧句 ⇒ 409 不会变 500），ResumeRunConflict.detail 承载；main.py 用 _resume_exc.detail，不再拼第二份。分档轴是【用户下一步动作】（已处理过 / 再答一次 / 预算用完 / 接不上），所以 answer_invalid 单列一档 ⇒ 共 4 条文案。新腿：AST 现读成因码全覆盖（新增抛点自动进门）+ 回落腿 + 四档互不相同且不泄漏内部标识；变异 M5（全塌成旧句）杀 5 条、M6（两档共用一句）杀 1 条 ⇒ evidence/batchB-mutation-20261011.log。文案由我起草并经整包授权落地，Owner 未逐字过稿（D-31）：改词只动常量，逐字用例会变红（那是预期信号） |
| D-11 | 在册风险册入库 ⇒ 已执行 | 主仓那份 docs/chroma-risk-triage-20261003.md（3,252 B / 23 行 / sha256 前缀 0847ba2d）10-11 现量仍是未跟踪且未被忽略（两棵树 ls-files 都 0、check-ignore 无命中），候选树里根本没有 ⇒ 已 cp -a 进候选 docs/（mtime 与 sha 逐字相同），随本轮文档提交。⚠️ 同族未跟踪文档主仓现量 34 只 ⇒ 见新行 D-30 |
| D-14 | 索引写入口守卫覆盖面 ⇒ 已开票 | 票 tickets/dispatch-D14-index-write-guards-20261011.md（8 节）。10-11 现量：守卫消费方 4 只（backup_data / import_laws / rebuild_embeddings / switch_embedding）；无守卫却能改生产向量库的 CLI 4 只共 13 个站点（import_docs 2、verify_new_law 7、eval_chunking 3、backfill_time_meta 1），且四只写目标都是 vectorstore._collection = 生产库 |
| D-15 | DB-7 技术降级白名单 ⇒ 已执行并测到 | backend/routing_metrics.py：TOOL_BUSY 进 TECHNICAL_FALLBACK_REASON_CODES（集合 5→6）；record_agent_route 的 raise 两侧都有用例钉住；管理台快照 fallback_reason_code_counts 里 TOOL_BUSY 与 TOOL_UNAVAILABLE 分列（逐键断言）。变异 M3 摘掉 TOOL_BUSY ⇒ 杀 2 条（精确集合 + 分列） |
| D-16 | DB-10 事件响应文档 ⇒ 已执行，并更正我台账的读数面 | DEPLOYMENT.md 新增 §7（三行表：信号 / 看哪个计数器 / 读到之后做什么），只写计数器不写法律口径。⚠️ 我原句写错：读数面不是 /metrics（全仓没有这个路由），真身 = GET /api/admin/llm-status（backend/main.py:3082，require_admin），返回 models / utility_quota / metrics |
| D-17 | F 的可播种语料 ⇒ 已裁：用冻结题集，本轮不播种 | Owner 10-11「按你的推荐」＝可播种条文仅 11 对，不足以撑 F2 的 12 题；F 腿仍由 §A 的 D-7 卡着，零代码改动 |
| D-18 | DB-24 注释与真值不符 ⇒ 已执行，且发现比台账宽 | 两处「8」改成「条数以 DEFAULT_ROLES 为准，注释里不抄数」。新发现：同一只 docstring 举的 7 个模型名里 6 个不在表里（deepseek-r1-distill-qwen-7b / qwen2.5-omni-7b / qwen3.5-omni-flash / qwen3-vl-235b / qwen3-vl-32b / qwen-plus 现量命中 0，只有 qwen3.7-plus 与 qwen3.5-omni-plus-2026-03-15 在）；「现有 6 个辅助调用点」这条现量是 registry.get() 15 处 ⇒ 假例子已删，条数与调用点数都改成指向真源。get() 返回 omni-plus 那句核为真（DEFAULT_KEY=vision_flag ⇒ qwen3.5-omni-plus-2026-03-15），未动 |
| D-20 | 合 master ⇒ 已开票，且数会随头动 | 票 tickets/dispatch-D20-merge-into-master-20261011.md（7 节）+ 尺子 evidence/merge_trial_blobs.py、evidence/merge_trial_reconcile.py + 清单 evidence/d20-diff-list.txt。10-11 04:0x 在头 5e9bba8 × refs/closing/remote-master（985d53e，与当日 ls-remote 一致）重跑：候选 2706 / 远端 2136 / 交集 2136 / 远端独有 0 / 同 blob 2040 / 异 blob 96 = CONFLICT 96（全 add/add）⇒ 两把尺子吻合。台账旧写 94 是 9e3cfc5 轴、更早 115 是本地陈旧 ref 轴，均已就地作废。分组（176899f 上的 99 只）：backend 74、frontend 15、docs 5、`DEPLOYMENT.md`/`CONTRIBUTING.md`/`.gitignore`/`.github`/`dispatch-output` 各 1；**头一动分組就重算**，别引用本句做排工。⚠️ **同一把尺子在 10-11 05:5x 的本轮三笔提交后再跑 = 异 blob 99 = CONFLICT 99（头 bffbe1c，A 路径 2707、B 独有 0）** ⇒ 96 只在 5e9bba8 上成立；这条不是笔误，是"数随头动"的现行演示，也正是票里写死"开工时与最终头上都要重跑"的原因 |
| D-23 | 取消占位文案 ⇒ 已执行并测到 | backend/main.py：_PLACEHOLDER_NO_RESPONSE（复用 _ERROR_NO_RESPONSE，两处只差句号，不抄第二份）与 _PLACEHOLDER_STOPPED 两档；_post_placeholder(pre, reason)。两条路分别钉住：正文生成器 finally 只在【抓到 GeneratorExit / CancelledError】时记 stopped。〔10-11 复核 B 打中我第一版：那时用「有没有走到 try 结尾」反推取消，而 try 体里有 5 处主动 return （轻量分支空答走 :2415），会把「服务端没给出内容」错写成「用户已停止」，同样的空答在旗舰分支却写「不响应」——同一症状两句话。已改为断开信号置档，并补一条 AST 结构不变量测试（只有 except 能置 _client_gone）。变异读数：旧版 M4 杀 4 条；改写后 M8 抽掉该信号杀 3 条（含这条新测试），日志 evidence/batchC-mutation-M8-20261011.log〕；compensate_unstarted（响应已关而正文从未进入）记 stopped（M7 ⇒ 杀 2 条）。服务侧真故障（空答 / 异常 / bootstrap 抛错 main.py:738）仍走 no_response。前端当场文案未动 ⇒ 见新行 D-32 |
| D-24 | 探针失败往宽还是往窄 ⇒ 已裁：保持宽 | Owner 10-11「按你的推荐」＝保持 _corpus_advertises_category 探测失败 return False ⇒ 无过滤回落；代价由 category_filter_* 三条日志字段承担（可见而不静默）。零代码改动 |
| D-25 | 出厂 Dockerfile 源侧缺陷 ⇒ 已执行（回落 + 可观测两条腿） | backend/Dockerfile：torch 步与 requirements 步各加 `\|\|` 失败回落（官方 CPU find-links / -i pypi.org），选 `\|\|` 而非 --extra-index-url 的理由写在文件里（不合并两源候选，避免版本选择权外移）。.github/workflows/ci.yml 新增 source-probe 作业（PyPI 逐包 pip download --no-deps --no-cache-dir + torch CPU 目录双源核对；主源红 = 降级 warning，两源同红 = 真红），只挂 schedule + dispatch，不占每次 PR。⚠️ 10-11 本机复量：缺陷已自愈（阿里云 pydantic-2.14.0 可取 487 kB rc=0；官方页 torch-2.13.0%2Bcpu-cp311 在列）⇒ 落的是【这一类】故障的兜底，不是复现中的补丁。自检：evidence/d25-probe-selfcheck-20261011.log、evidence/d25-pipleg-selfcheck-20261011.log（假版本必两源皆红、rc=1） |
| D-29 | D-3 的两份 diff 要不要现在落 ⇒ 已裁：本轮不落 | Owner 10-11「按你的推荐」＝不落地。迁移证据已交付且我独立复算过族 ID 13→0，但落它＝换整栈依赖，与本轮【验收对象 = 交付对象】的收口顺序冲突；登记为下一轮首票（连同 D-3 报告 §6 的两条观察项） |
| **D-7 | F 五类真实模型验收这轮开不开 ⇒ 已裁：不开 | 按推荐执行＝本轮零模型调用（在册预算 81/162 未动用）；冻结稿在 `docs/closeout-20261010/gold-freeze-draft.md`，F 的三根阻塞（含可播种语料仅 11 对）逐条仍在报告里挂着，**没有**被本轮顺手做掉 |
| **D-30 | 主仓其余未跟踪文档 ⇒ 已裁：本轮不收 | 现量：主仓 `docs/` 未跟踪 34 只，本轮只按 D-11 收了点名的 `chroma-risk-triage-20261003.md`。不收的理由是公开仓一推就永久可见；要收时一次性裁「收哪几类、放哪个目录」 |
| **D-31 | 我代起草的用户可见文案 ⇒ 整包授权下按草案落地（**未逐字过稿**；要改词只动常量，判据不动） | 409 四档在 `backend/agent/controller.py` 的 `RESUME_DETAIL_*`；取消与故障两档在 `backend/main.py` 的 `_PLACEHOLDER_STOPPED` / `_PLACEHOLDER_NO_RESPONSE`。每条都有用例逐字钉住 ⇒ 将来改词只动常量，分档与判据不动（改词会让那几条逐字断言红，那是预期信号，不是回归） |
| **D-32 | 取消的历史文案与前端当场文案 ⇒ 已裁：保持两套 | `frontend/lib/hooks/useChatStream.ts:65-66`（当场，可能有半截答案）与 `backend/main.py` 的历史占位（一定没有答案）语义不同，不合并；本轮前端零改动 |

## D. 一句话门禁现状（截至本文件写出时）

候选 `codex/nondeploy-closeout-20261010`；本轮提交笔数用 `git log --oneline 0b54396..HEAD` 现量（本文不写死笔数，写完就会过期）
**未推送、未开 PR、未合并、未轮换任何凭据、未动真实库与容器**。
门禁现量（2026-10-11 07:3x，头 `bee37d3`＝复核修复后）：`ruff check .` rc=0、`ruff format --check .` 283 files rc=0、`mypy .` Success（74 files）、
全量非 slow **1933 passed / 0 failed / 10 skipped / 18 deselected**、覆盖率 **86.38%**（门槛 70）rc=0、
基线闸：collected **1943/1961**、junit tests=1943 skipped=10 failures=0 errors=0（1933+10=1943）；
前端 `tsc` rc=0、`next lint` rc=0、`vitest` **83 passed**、`npm run build:check` rc=0（产物断言 VERDICT=OK）。
证据 `evidence/final-gates-backend-20261011.log`、`final-gates-junit-20261011.xml`、`final-gates-static-frontend-20261011.log`；
`socket` 守卫与 `pip check` 两轴本轮未重跑（未动依赖与网络面），在册读数见 `reports/gates.md` §38。 注：第二遍全量的 collected/junit 只在新加那条 AST 不变量测试后 +1；两遍读数都在 evidence/final-gates*-20261011.log。

## E. C 单元（依赖风险）的收口建议：15 条其实只剩**两条处置要你点头**

现量（`evidence/audit-cand-{runtime,dev}.json` 两轴同集）：**15 个主 ID，分布 5 只包**。不是 15 个独立决定——按「修法是否存在」分两堆：

| 堆 | 条数 | 包 | 修法 | 现处置 | 建议 |
|---|---|---|---|---|---|
| A | **13** | `langchain-core` / `langchain-openai` / `langchain-text-splitters` / `langsmith`。**两根轴都要点名**：每包**条目**（含重复）= `core 11 / langsmith 5 / splitters 4 / openai 2`；每包 **distinct 主 ID** = `core 6 / langsmith 4 / splitters 2 / openai 1`，且**跨包无重叠**（和 = 并集 = 13） | 修复线全在 **0.3.x / 1.x**（如 `langchain-core 1.2.22`、`langsmith 0.8.18`）⇒ 必须跨大版本 | **D-3 已 BLOCK 成独立迁移票**（本轮不动调用面） | **维持 D-3**；本条只是把分母说清：它背 13/15 |
| B | **2** | `chromadb` `PYSEC-2026-3813/3814` | **两条 `fix_versions` 均为空**（无修复版；且升到 1.5.0 反把适用面从 2 条扩到 5 条） | **D-2 已在册接受**（复用 10-03 风险册，不新建） | **维持 D-2** |

⇒ **已裁（2026-10-11，Owner「按你的推荐」）：按这两条处置收口** —— **A 堆 13 条**走 D-3 的独立迁移票（本轮不动调用面）；**B 堆 2 条 chromadb** 沿用 D-2 的在册接受（不新建第二份风险册）。本条自此为**已执行状态**，不再是待决项。

**就地更正（2026-10-11 01:3x，两处，都是我自己的错）**
1. 上一句原写「本轮不动调用面，**票面已存在**」——**该断言当时为假**：`tickets/` 当时只有 3 只文件（D 单票、D 验收尺、I 执行卡），没有任何迁移票；"票面要点"只以散文形式存在于 `reports/owner-decisions-20261010.md:39`（写着"供你派单"）。
   现已按 D-3 把票**真正写出**：`tickets/dispatch-D3-langchain-migration-20261011.md`（7 节，含现量分母、符号面 16 项、副本树双跑配方、能红的验收尺子、停止条件）。这条"已裁"自此才有归宿。
2. 上面 A 行原写每包 `core(7)/openai(1)/splitters(2)/langsmith(3)` ⇒ **这一处是错的**（7 与 3 两个数在任何轴上都数不出来）。
   但我要**同时撤回自己 01:2x 那次"更正"**：我当时写"两处手抄拆法（含 `owner-decisions-20261010.md:35` 的 core 6 / langsmith 4 / splitters 2 / openai 1）都不可复现"——**这句为假，是我错怪了那只文件**。
   现量（复算器 `evidence/audit_axes.js`，读 `evidence/audit-cand-runtime.json` 与 `-dev.json`，两份同集）：
   - 每包**条目**（同一 ID 在同包可出现两次）= `core 11 / langsmith 5 / splitters 4 / openai 2`（+`chromadb 2` = 全 24 条目）；
   - 每包 **distinct 主 ID** = `core 6 / langsmith 4 / splitters 2 / openai 1`，**跨包无重叠**（和 = 并集 = **13**，与"A 堆 13 条"吻合）；
   - `distinct ID with fix_versions` 与上面同值（⇒ "有修复线/无修复线"不是差异来源），CVE 前缀只有 `langsmith 1`，族主 ID + aliases = **38**。
   ⇒ **`owner-decisions:35` 那句在 distinct 轴上完全正确，保持原样不改动它**；要改的只有本文件那行的 7/3。
   **根因登记**：我第一次只算了"条目"和"族并集"两根轴，就宣布别人的拆法不可复现——**报"不可复现"之前要先把对方可能用的那根轴跑一遍**（这台机器我已经在别的节里批评过一次）。

```bash
# 两根轴一次印全（2026-10-11 独立复核 C §3.3 之后，脚本已补上 per-package distinct 轴）
R=C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
node "$R/evidence/audit_axes.js" "$R/evidence/audit-cand-runtime.json" "$R/evidence/audit-cand-dev.json"
# 注意：原先这块写的是 python -c 里 glob('<msys 路径>').replace('','/')，两处坏：
#   ① '' 是未闭合字符串 ⇒ SyntaxError；② 即使修好，Windows 解释器打不开 /c/... 形式 ⇒ 会静默打印 0（假干净）。
```

## F. 本轮总账（这一节的存在理由：让本文件可以单独转发）

**状态**：候选分支本地 8 笔、头 `dae319d`、`git status --porcelain` = 0 行、未跟踪 0；**未 push、未开 PR、未合并、未轮换任何凭据、未动真实库/向量库/容器/端口 3021 与 8088**。代码面自 `bee37d3` 起未再变动（其后两笔都是 docs）。
**门禁现量（07:3x 当场跑，不是推的）**：全量非 slow 1933 passed / 0 failed / 10 skipped / 18 deselected、cov 86.38%、rc=0；collected 1943/1961、junit tests=1943；ruff check、ruff format --check（283 files）、mypy（74 files）均 rc=0；前端 tsc、lint、vitest 83、`npm run build:check` 的产物断言 VERDICT=OK。复算命令在 `reports/gates.md` §45 与本文 §D。

**等你答的只有 4 条**：§A 的 D-5（先轮换 `ADMIN_PASSWORD` 再普通推 + 开 PR）与 D-19（文档 ref 一起推）；§B 的 D-33（不可达的 step_budget 档怎么处置）与 D-34（Agent 轮次没有占位补偿腿）。

**独立复核二轮（两路子代理，正交）**
- A 复现腿 `reviews/20261011-round2/independent-review-A-replication-20261011.md`：采纳 8 / 驳回 1 / 核不了 0。它自己在 `git archive` 副本树上复刻了变异、重跑了全量门禁与对象轴，没引用我的转述。
- B 对抗腿 `reviews/20261011-round2/independent-review-B-challenge-20261011.md`：新发现 12 条，其中四处我当场验实后**本轮已修**——① 取消档原先用"有没有走到 try 结尾"反推 ⇒ 只认真实断开信号（并补结构不变量测试）；② `source-probe` 缺**作业级** `if:` ⇒ 补上（我三处"不占每次 PR"是假话）；③ torch 回落只换 find-links 不换 index ⇒ 已同时换官方源；④ D-14 票的机制前提不成立（那四只脚本跟随 `CHROMA_DIR`，`assert_matches` 对它们是**恒等式**、永不咬红）⇒ 票已重写。
- 另两条只登记不实现：就是 §B 的 D-33、D-34。

**推送量的一条自我更正（影响你怎么读 D-5）**：我上一轮写"上传集会因对象身份被折小"**是错的**，这次复量到 `rev-list --objects remote-master..HEAD` == `rev-list --objects HEAD` == **4464**，且两侧同 blob 的 2037 只**全部**仍在上传集里 ⇒ 无关历史时剪的是 commit 链不是对象身份。方向不变的结论只有一条：那只 13 位裸值的 blob 在上传集里、不在远端可达集里 ⇒ **先轮换再推**。

**我本轮的自曝错（原先只在对话里说过，现按规矩落进正文；细节在 `reports/gates.md` §42、§45、§47 与 J §10.2）**
1. 给新测试编了不存在的符号（`registry.snapshot()` 真名 `status()`；白名单真名 `_ACCOUNT_FIELDS`）。
2. 写过一条**恒真**三元断言（期望值由被测值现算，永不红）。
3. D-6 对账第一次**读错轴**：拿主仓旧那份 requirements 比 venv，得 4 条偏离；换成候选那份才是 6 条。
4. D-20 的两把尺子各带一处仪器错（`rev-parse` 取不到返回空被算成差异；`partition` 把行尾留在 key 里）。
5. 计数词口算：写过"18 条全部处置完"，真值是 §A/§B 由 18 降到 2 ⇒ 现在**计数词又是口算的**这条被脚本兜着（差集实测）。
6. 中文串里嵌 ASCII 双引号 ⇒ `SyntaxError`，**同一个坑我又踩第三次**；之后脚本里的中文散文不带 ASCII 双引号，竖线用 `chr(124)`、反斜杠用 `chr(92)`。
7. 表格单元里写 shell 的竖线导致**劈列**（4 列变 7 列），被 `evidence/md_table_columns.py`（自带 `--selftest`）抓到。
8. 用 `bytes(10)` 当换行去数节数 ⇒ 恒返 0（那是 10 个 NUL）；改按 `chr(10)` 切行后现量 47 节。
9. 在册报告 `gates.md` 里有一个**真 NUL 字节**（`grep` 把整份台账当二进制），已修并复量 NUL=0。
10. heredoc 会把双反斜杠折成单个 ⇒ 第一次修 NUL 时被自己的长度断言拦下；写法改成 `chr(92)` 构造。
11. `grep -q` 在 `set -o pipefail` 下让上游 `sed` 收 **SIGPIPE** ⇒ 正对照假阴性（探针差点被我误判为"两页都缺件"）。
12. `pip download` 不加 `--no-cache-dir` 时用 "Using cached" 冒充"官方源真取到"（第一次的假绿）。
13. 两条**新待裁项错放进 §C**（已裁档）且列数写成四列 ⇒ 被列数检查器与重号脚本同时抓到，已挪回 §B。
14. 汇报自查：本轮"都写进决策文件了吗"由 `evidence/work_log_key_audit.py` 出数——29 个 key 只对这一只文件跑，最初缺 14 个（就是本节存在的原因）。

**交付物路径**（运行根 `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`）
- 汇报：`reports/closeout-final-J-draft.md`（§0 状态、§3 待裁四条、§10.2 我的错、§11 复核二轮）
- 状态与读数：`reports/gates.md`（§38–§47）
- 本文件：`reports/decisions-needed-20261010.md`（§A/§B 待裁、§C 已裁 30 条逐条落地位置、§D 门禁、§F 总账）
- 下一轮三张票：`tickets/dispatch-D14-index-write-guards-20261011.md`、`tickets/dispatch-D6-dev-env-alignment-20261011.md`、`tickets/dispatch-D20-merge-into-master-20261011.md`
- 你要动手时用：`tickets/runbook-I-push-pr-merge.md`（推送前置与命令；已按 §44 更正刷新）
- 两份复核报告：上面"复核二轮"里那两个路径；均已同步进仓内 `docs/closeout-20261010/`（34 只 .md，与运行根逐只 sha 相同）

**本轮未做（不是"已做"）**：F 五类真实模型腿未跑（Owner 裁本轮不开，冻结稿在册）；`socket` 守卫与 `pip check` 两轴未重跑（未动依赖与网络面）；D-18 的旧断言我只清了代码注释与文档引用面；D-33/D-34 只登记未实现；D-3 的两份 diff 按 D-29 本轮不落。

## G. 本轮做了什么（穷尽清单；细读数在 `reports/gates.md` §38–§47，叙述在 J）

**单元层（A–J 按执行书的单元记账）**
- A 接手保护与登记：闭合（基线 `reports/baseline.md`，候选分支 `codex/nondeploy-closeout-20261010`）。
- B 后端四票 + B-45 守卫 + D-3 迁移证据：闭合（D-3 由我独立复算验收，落地转 D-29）。
- C 依赖风险：闭合（15 条压成两堆处置，Owner 已裁；迁移票已真写出并交付）。
- D 前端五项残差 + 取消流程真实浏览器验收：已验收；其 J3 红（生产构建 purge 掉 `badge-*`）由我自验并修（D-22），连带暴露的配色 AA 按 D-28(b) 修（D-22/D-28 均闭合）。
- E 模型来源、加载信任门、合成数据演练：闭合（行为级五臂 + 恢复演练）。
- F 五类真实模型验收：**本轮不跑**（Owner 裁；冻结稿在册，可播种语料仅 11 对是三条阻塞之一）。
- G 现役环境升级：判为不动（现役是 Docker 容器；宿主 venv 的对齐转 D-6 票）。
- H 包装、凭据/历史、远端 CI：闭合但带披露（凭据轴见 §2 与 D-5；CI 历史与触发语义见 D-5 现量列）。
- I 独立审查、本地提交、PR、合并：**只差你手上的推送动作**；本地提交笔数现读 `git log --oneline 0b54396..HEAD | wc -l`（写本行时=27，其中本半段 8 笔）。
- J 收尾：正式稿（本文件 §F/§G/§H + `closeout-final-J-draft.md`）。

**改动面（代码，按文件）**：`backend/llm_registry.py`（拒答冷却两档 + `rejected_kind` 进 `status()` + DB-24 注释更正）、`backend/observability.py`（两个日志字段登记进 `_ACCOUNT_FIELDS`）、`backend/routing_metrics.py`（`TOOL_BUSY` 进白名单、与 `TOOL_UNAVAILABLE` 分列）、`backend/main.py`（409 用异常携带的分档文案；占位两档；只认 `GeneratorExit`/`CancelledError` 为断开）、`backend/agent/controller.py`（`RESUME_CONFLICT_DETAILS` 成因码表 + 回落 + 不可达性标注）、`backend/settings.py`（注释去抄数）、`backend/tests/`（`test_llm_reject_channel.py`、`test_agent_rollout.py`、`test_agent_resume.py`、`test_cancel_boundaries.py`（含新结构不变量测试）、`test_chat_turn_persistence.py`、`test_stream_cancellation.py` 签名对齐）。
**改动面（文档与部署）**：`DEPLOYMENT.md` §7 事件响应三行；`backend/Dockerfile` 两步各加失败回落（torch 那发同时换 index）；`.github/workflows/ci.yml` 新增 `source-probe` 作业（含作业级门与逐包正对照）+ 触发段加 schedule/dispatch；`docs/chroma-risk-triage-20261003.md` 入库（D-11）；`docs/closeout-20261010/` 交付镜像现读 `ls docs/closeout-20261010/*.md | wc -l`（写本行时=34，且与 `git ls-files` 同数）。
**判据与仪器（本轮新增）**：变异 9 枪（M1–M3 批 A、M4–M7 批 B、M8 复核后；每枪只动一个 site、finally 还原、逐文件 sha 位级相同）；`evidence/venv_vs_requirements_axis.py`、`merge_trial_blobs.py` + `merge_trial_reconcile.py`、`md_table_columns.py`（自带 `--selftest`）、`ci_yaml_check.py`、`d25-*-selfcheck`、`work_log_key_audit.py`（key×文件对账）、`push-upload-axis-recheck-20261011.md`。
**票与复核**：新写三张票（D-14 / D-6 / D-20），刷新 runbook；两路独立子代理复核（A 复现、B 对抗）报告入库，其判决与我的响应在 §F 与 gates §46。

## H. 还差什么没做（分类穷尽；每条指名归属与出处）

**只能你动、我没动（也不该动）**
1. 凭据轮换（`ADMIN_PASSWORD` 等）——D-5 的前置；我不读 `.env`、不代做。
2. 普通 push + 开 PR + 合并 master——共享状态动作；命令与三条"推送前现跑"的前置在 `tickets/runbook-I-push-pr-merge.md`。
3. 推 `codex/local-candidate-closeout` 那支文档 ref——D-19，同一把钥匙。
4. 用户可见文案的**过字**（409 四档 + 取消两档由我起草、按整包授权已落地，但你未逐字过稿）——D-31；改词只动常量。

**已裁成票、留给下一轮执行（本轮有意不做）**
5. D-14 四只无守卫 CLI（票已按复核重写机制前提）。
6. D-6 开发环境 `backend/venv` 对齐（现量 6 条偏离 + `pip check` 2 条既有红）。
7. D-20 合 master：现量 **99 次**内容裁决（会随头动，开工前重跑）。
8. D-29 落 D-3 的两份 langchain diff（本轮不落；下一轮首票）。
9. D-33（不可达的 step_budget 档：删站点 或 让 `max_clarifications` 耗尽并进来）、D-34（Agent 轮次没有占位补偿腿）。
10. D-30 主仓其余 33 只未跟踪文档：本轮不收，要收时一次性裁范围。

**未跑的读数/轴（我明确没做，不是做了没写）**
11. F 单元全部：五类真实模型验收、真实路由、独立 gold（零模型调用，预算未动用）。
12. `socket` 守卫非回环读数 与 `pip check`（本轮未动依赖与网络面）⇒ 仍是上一轮在册值。
13. 远端 CI 读数：合并前拿不到（`on.push.branches` 只列 main/master，推 `codex/*` 不产生 run；新加的 `source-probe` 又只在默认分支才响应 schedule）。
14. `docker build` 全量冒烟：探针只覆盖源侧"文件取不取得到"，模型烘焙那层没跑；且 10-10 那次源侧故障今天复量已自愈 ⇒ 没有正在复现的缺陷可证。
15. 真实知识库语义面：两棵树 `backend/chroma_db` 都是空壳 ⇒ `real_kb` 走 skip，10 条 skip 的**构成**未逐条列（在册纪律要求报"几条走 skip"，这条只做到"未逐条列"）。
16. 浏览器计算样式那一腿（J3 的六状态视觉等价）由 D 会话与我的 CSS 产物断言承载，我**没有**独立复跑浏览器腿；复核 C 也把这条列为未复算项。
17. `evidence/` 整目录不入库（交付镜像只含 reports 与 tickets）⇒ 数字可复算的前提是这台机器上的运行根还在。

**已知限制（不影响"做没做"，影响怎么读结论）**
18. `closeout-final-J-draft.md` §7 那张自我更正表写的是"八条"，那是**写表时**的条数；第二批的错在 §10.2、复核后的错在 §F 第 1–14 条。编号不重排，避免十余处按号引用漂移。
19. 凭据轴的结论是"轮换前不能推"，**即使推了并轮换，历史里那只 13 位裸值仍在**（只是不再现役）——签了也不解除。
20. D-25 的 CI 探针**不等于**出厂构建可用；`--no-deps` 逐包解析与整表联合求解可能选到不同版本（该偏差写在作业注释里）。
21. 台账里所有"几笔提交/几份文件/几次裁决/几个对象"都是**写行时的现量**，一律以同行给的命令为准；本行写这些数字时头是 `50b39ec`。
