# 待你裁台账（2026-10-10 非部署收尾轮）—— 每条一词可答

口径：只列**现在真的还没定**的。已裁过并执行完的放在最后一节，不再问你。
每条都给了现量证据的位置，你要查就按那条命令查，不必信我的转述。

## A. 卡住交付的（答完才能往下走）

| 编号 | 一句话 | 现量证据 | 我的推荐 | 你可以答 |
|---|---|---|---|---|
| **D-5 凭据与推送** | 候选分支要不要现在普通 `git push` + 开 PR？ | 两条路线现在**都有实测对象集**（`reports/h-ci-and-credentials.md` §2.1 与 §7）：**(a) 普通推**＝**现量 4252 对象**（03:3x，`rev-list --objects refs/closing/remote-master..HEAD`，HEAD=`fbd9eb2`）。〔沿革：旧写 4301＝第四笔时；4315＝第五笔时的**全量可达对象数**；我 03:1x 那句「因无共同祖先，跟哪个 ref 比都是 4315」**机理讲错了并已撤回**——`--objects A..B` 是按**对象身份**排除，不是按祖先，两侧内容相同的 blob/tree 会被折掉，所以真实上传集比总数小。**这个数每提一笔都会变，推送前须现跑**〕，**含那只 13 位历史裸值**（按值反查 **239** 棵树 hits=61/files=1，HEAD 树已无；裸值所在**那只 blob** `d59a7b61…`（`git rev-parse 817e7d3:<该文件>`）**不在远端真实头的可达对象里**（把它放进 `rev-list --objects refs/closing/remote-master` 的输出里 grep 计数 = **0**，而它在 `remote-master..HEAD` 差集里 = **1**）⇒ 直推必然把它带上去。这条判据是**按对象身份直接查集合**，比早先那套「引入笔不是远端祖先」的推断强一档，也正是我 03:1x 那句错话的替代品）；**(b) 无父快照**＝2581 对象（1 commit/173 tree/2407 blob，比 (a) 少 **1734**），**按值反查 0 命中**；⚠️ **原句「树与 `HEAD^{tree}` 逐字相同」在 03:0x 前为假**——那枚旧快照的树 `04dd97ad` 是**第四笔 `3f605de`** 的树，而现 HEAD 树是 `1e91913c`（这条由**独立复核 C §2.1** 抓到，不是我自查）。**03:1x 我按当时现 HEAD 重生成过（快照 `1b1c307e…`，树 `1e91913c` == 当时 `HEAD^{tree}`＝`9e3cfc5` 的树；pack `verify-pack ok`；旧三件改名保留未删除），**但 03:2x 我又提了两笔 docs 入册 ⇒ 现 `HEAD^{tree}` 已前移到 `a5eff903`，这条相等再次失效——也就是我把复核 C §2.1 刚抓出的缺陷自己复现了一遍**。⇒ 结论换成形：**(b) 路线的快照必须在推送前最后一刻现生成**，两条当场读数相等（`rev-parse 'HEAD^{tree}'` vs `rev-parse '<新快照>^{tree}'`）才放行；存放着的快照不是可依赖对象。`refs/closing/orphan-snapshot-20261011` 只是把当时那枚无父对象从 gc 嘴下钉住，**不代表当前交付内容**且同一把值在真实历史里正对照咬住 ⇒ **不外泄是构造性质，不是扫描结论**；快照已出 pack（141,791,027 B）并**冷恢复读回跑通**（临时裸仓只补 `HEAD` 文件，无 ref 指向它）。**10-11 01:5x 复测（推翻 10-10 那句 rc=35）**：`api.github.com` **200**、`github.com` **200**、`ssh -p 443` 认证通、`git ls-remote --heads origin` **rc=0** ⇒ **(a) 两条轨都推得动，远端读数也拿得到**（"网络不通"这道偶然护栏今天没了）。新读到的远端现状：仓库 **public**（`private:false`）⇒ **转 private 会开始吃套餐分钟、且余额匿名读不到**，若你这一轮的目的含"让 CI 真跑一次"，转 private 是可能把目的本身卡死的动作；远端**只有 `master` 一支**（头 `985d53e`，09-17 15:15，**不在本地对象库**）；CI 历史 `total_count=18` = **17 场 push 全 `failure`** + 1 场 `dispatch` success（#1，08-08），**`pull_request` 0 场** ⇒ 精确说法是"push 触发的 CI 从未绿过"。⚠️ **普通推 `codex/*` 分支不会触发任何 CI**（候选 `ci.yml` 的 `on.push.branches` 只列 `[main, master]`）⇒ **"推了就等于有第三方验证"这句不成立**；要远端证据只有：开 PR（这条路历史 0 次，且两侧无共同祖先时合成 merge ref 可能压根不调度）、或事后 `workflow_dispatch`（只认**默认分支上那份**定义，量的不是我这份改动）。内容轴提醒：`ls-tree --long` 按路径加总 368,248,372 B 会**说大近 2.6 倍**（`diag/frozen-index-004/005` 逐 blob 相同、每目录 37 路径只有 30 个唯一 blob）⇒ 真实外发看 pack 141,791,027 B。唯一未知仍是「该旧值是否仍现役」，需读 `.env`（书禁区） | **先轮换 `ADMIN_PASSWORD` 再普通推 + 开 PR**；(b) 留作「你不想现在轮换」的备选，代价是 PR base 无共同祖先、`ci.yml` 触发要按 compare 分流。**签之前要知道的两条连带**：① 推分支本身**不产生 CI 读数**（见现量列最后一条），想要第三方验证就得连"开 PR"一起签；② 远端主线自己 **17/17 push 全红**（09-17 之前就这样），所以**别把"CI 红"当我的候选的判决**——它今天仍是红的，且原因与本次改动无关（这条我只测到"结论分布"，没测失败步骤）。 | 「轮换」/「走孤儿快照」/「先不推」 |
| **D-7 F 单（真实模型验收）** | 五类真实模型调用这一轮开不开？ | 执行书 §0.4：F 需要 B/C/D/E 的硬前置 + 候选自审 + 独立复核都过。现在 B/E 有读数、C 两类残余待你确认、D 正在跑；两路独立复核也还在跑 | **等 D 单与两路复核回来再答**，并且开跑前先把 F2 那张表的病例与 gold **冻结入库**（我可以先写冻结稿，零调用、零花费） | 「先写冻结稿」/「等 D 完再谈」/「本轮不跑 F」 |

## B. 不卡交付、但答了我就能继续动手的

| 编号 | 一句话 | 现量证据 | 我的推荐 | 你可以答 |
|---|---|---|---|---|
| **D-19 文档引用悬空（103 处 / 15 文件）** | 推送时要不要把 `codex/local-candidate-closeout` 一起推上去？ | 现量：`fbc29e8` 可解析但 **不是 master 的祖先**（`merge-base --is-ancestor` rc=1），它是本地分支 `codex/local-candidate-closeout`（193 笔）的尖端，该分支**从未推送**；而仓库内 `git grep -o fbc29e8` = **103 次引用 / 15 个文件**。两支关系：`rev-list --count 候选..closeout` = **4 笔独联提交**，且**不新增凭据外泄**（按值反查 closeout 对象集 value_hits=1，候选里也已是 1） | **一起推**（多 4 笔提交，换来 103 处引用在远端可解析）；`--no-ff` 合并不解决这个问题，别把它当已处置 | 「一起推」/「只推候选并登记悬空」/「改写这 103 处引用」 |
| **D-30 主仓其余未跟踪文档要不要一起入库 | 本轮按 D-11 只收了点名那一只，其余要不要一起收？ | 10-11 现量：主仓 git status --porcelain --untracked-files=all -- docs/ 的 ?? 行 = 34（含十余只 work-report、plans、审计与 assistant-briefs；本轮已收 chroma-risk-triage-20261003.md 一只）；候选树 docs/ 未跟踪 = 0、tracked = 240 | 【本轮不收】：它们是历史轮的过程交付，公开仓一推就永久可见；要收时一次性裁「收哪几类、放哪个目录」 | 「一起收」/「收一部分」/「不收」 |
| **D-31 D-10 与 D-23 的新文案要你过字 | 四档 409 文案 + 两条占位文案是我起草并已落码的，词要不要换？ | 现量位置：backend/agent/controller.py 的 RESUME_DETAIL_*（4 条）与 backend/main.py 的 _PLACEHOLDER_STOPPED / _PLACEHOLDER_NO_RESPONSE。每条都有用例逐字钉住 ⇒ 改词只动常量、不动分档与判据 | 【照草案】（法律口径我不替你定；要改词直接划在上面） | 「照草案」/「我改几个词」 |
| **D-32 取消的历史文案与前端当场文案要不要统一 | 当场显示「已停止生成。」，刷新后历史里是「本次回答已停止，未生成完整内容。」——要不要同一句？ | frontend/lib/hooks/useChatStream.ts:65-66：有半截答案时追加「（已停止生成，以上为未完成回答。）」，无内容时「已停止生成。」；backend 新落的历史文案只在【没有任何 assistant 内容】时才写 | 【保持两套】：两者语义不同（一个可能有半截答案、一个一定没有），统一成一句反而要让历史承载部分答案的分支 | 「保持两套」/「统一成一句」 |

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
| D-12 | 本轮交付物要不要入库 | **已执行**：`docs/closeout-20261010/` 现量 **29 只 `.md` 全部 tracked**（随 4 笔 docs 提交入册；未含 `evidence/`、`candidate-env*`、`synthetic/`）。入库前三检留痕：逐只 CR=0；凭据形状复扫 `sk-`/AKIA/JWT/PEM/URL-in-creds 命中 0，13 位形状 45 处全是普通标识符、与参照值相同 0 处；`git diff --cached --name-only` 自证未夹带 |
| D-6 | 开发环境对齐怎么办 ⇒ 已开票，本轮不动宿主机 venv | 票 tickets/dispatch-D6-dev-env-alignment-20261011.md（7 节）。10-11 现量：对【候选】requirements.txt 偏离 6 只（fastapi 0.110.3 / uvicorn 0.52.1 高于上限 / sentence-transformers 2.7.0 / sqlalchemy 2.0.51 / pypdf 6.14.2 / torch 2.6.0+cpu），pip check 既有 2 条红；⚠️ 同一条命令读【主仓旧那份】只得 4 条偏离（那份没有 torch 行、sqlalchemy 下限还是 >=2.0）⇒ 报数必须点名读哪一份。尺子 evidence/venv_vs_requirements_axis.py，读数 evidence/d6-venv-axis-20261011.txt |
| D-8 | DB-19 的 category 字段摘不摘 ⇒ 已裁：不摘 | Owner 10-11「都交由你的推荐执行」＝采纳维持现状；schema 与回落形状未动，category_filter_* 三字段读数继续存在。零代码改动 |
| D-9 | DB-22 拒答冷却分档 ⇒ 已执行并测到 | backend/llm_registry.py：REJECT_COOLDOWN_BY_STATUS（401/403/404 = 3600s）+ reject_cooldown_s() + reject_kind() + ModelEntry.rejected_kind；status() 每行带 rejected_kind（config 与 shape 分得开）；两字段登记进 observability._ACCOUNT_FIELDS。新增 3 条用例（tests/test_llm_reject_channel.py）。负向自证：M1 把长档塌回 300 ⇒ 杀 2 条；M2 取消登记 ⇒ 杀 2 条（含 AST 哨兵那条）⇒ evidence/batchA-mutation-20261011.log |
| D-10 | DB-23 的 409 文案 ⇒ 已执行，且实拆成 4 档（台账原写三条） | backend/agent/controller.py：RESUME_CONFLICT_DETAILS 成因码表 + resume_conflict_detail()（未登记码回落旧句 ⇒ 409 不会变 500），ResumeRunConflict.detail 承载；main.py 用 _resume_exc.detail，不再拼第二份。分档轴是【用户下一步动作】（已处理过 / 再答一次 / 预算用完 / 接不上），所以 answer_invalid 单列一档 ⇒ 共 4 条文案。新腿：AST 现读成因码全覆盖（新增抛点自动进门）+ 回落腿 + 四档互不相同且不泄漏内部标识；变异 M5（全塌成旧句）杀 5 条、M6（两档共用一句）杀 1 条 ⇒ evidence/batchB-mutation-20261011.log。文案要你过字见新行 D-31 |
| D-11 | 在册风险册入库 ⇒ 已执行 | 主仓那份 docs/chroma-risk-triage-20261003.md（3,252 B / 23 行 / sha256 前缀 0847ba2d）10-11 现量仍是未跟踪且未被忽略（两棵树 ls-files 都 0、check-ignore 无命中），候选树里根本没有 ⇒ 已 cp -a 进候选 docs/（mtime 与 sha 逐字相同），随本轮文档提交。⚠️ 同族未跟踪文档主仓现量 34 只 ⇒ 见新行 D-30 |
| D-14 | 索引写入口守卫覆盖面 ⇒ 已开票 | 票 tickets/dispatch-D14-index-write-guards-20261011.md（8 节）。10-11 现量：守卫消费方 4 只（backup_data / import_laws / rebuild_embeddings / switch_embedding）；无守卫却能改生产向量库的 CLI 4 只共 13 个站点（import_docs 2、verify_new_law 7、eval_chunking 3、backfill_time_meta 1），且四只写目标都是 vectorstore._collection = 生产库 |
| D-15 | DB-7 技术降级白名单 ⇒ 已执行并测到 | backend/routing_metrics.py：TOOL_BUSY 进 TECHNICAL_FALLBACK_REASON_CODES（集合 5→6）；record_agent_route 的 raise 两侧都有用例钉住；管理台快照 fallback_reason_code_counts 里 TOOL_BUSY 与 TOOL_UNAVAILABLE 分列（逐键断言）。变异 M3 摘掉 TOOL_BUSY ⇒ 杀 2 条（精确集合 + 分列） |
| D-16 | DB-10 事件响应文档 ⇒ 已执行，并更正我台账的读数面 | DEPLOYMENT.md 新增 §7（三行表：信号 / 看哪个计数器 / 读到之后做什么），只写计数器不写法律口径。⚠️ 我原句写错：读数面不是 /metrics（全仓没有这个路由），真身 = GET /api/admin/llm-status（backend/main.py:3082，require_admin），返回 models / utility_quota / metrics |
| D-17 | F 的可播种语料 ⇒ 已裁：用冻结题集，本轮不播种 | Owner 10-11「按你的推荐」＝可播种条文仅 11 对，不足以撑 F2 的 12 题；F 腿仍由 §A 的 D-7 卡着，零代码改动 |
| D-18 | DB-24 注释与真值不符 ⇒ 已执行，且发现比台账宽 | 两处「8」改成「条数以 DEFAULT_ROLES 为准，注释里不抄数」。新发现：同一只 docstring 举的 7 个模型名里 6 个不在表里（deepseek-r1-distill-qwen-7b / qwen2.5-omni-7b / qwen3.5-omni-flash / qwen3-vl-235b / qwen3-vl-32b / qwen-plus 现量命中 0，只有 qwen3.7-plus 与 qwen3.5-omni-plus-2026-03-15 在）；「现有 6 个辅助调用点」这条现量是 registry.get() 15 处 ⇒ 假例子已删，条数与调用点数都改成指向真源。get() 返回 omni-plus 那句核为真（DEFAULT_KEY=vision_flag ⇒ qwen3.5-omni-plus-2026-03-15），未动 |
| D-20 | 合 master ⇒ 已开票，且数会随头动 | 票 tickets/dispatch-D20-merge-into-master-20261011.md（7 节）+ 尺子 evidence/merge_trial_blobs.py、evidence/merge_trial_reconcile.py + 清单 evidence/d20-diff-list.txt。10-11 04:0x 在头 5e9bba8 × refs/closing/remote-master（985d53e，与当日 ls-remote 一致）重跑：候选 2706 / 远端 2136 / 交集 2136 / 远端独有 0 / 同 blob 2040 / 异 blob 96 = CONFLICT 96（全 add/add）⇒ 两把尺子吻合。台账旧写 94 是 9e3cfc5 轴、更早 115 是本地陈旧 ref 轴，均已就地作废。分组：backend 72（含 tests 33）、frontend 15、docs 5、门禁会读的配置 4。⚠️ **同一把尺子在 10-11 05:5x 的本轮三笔提交后再跑 = 异 blob 99 = CONFLICT 99（头 bffbe1c，A 路径 2707、B 独有 0）** ⇒ 96 只在 5e9bba8 上成立；这条不是笔误，是"数随头动"的现行演示，也正是票里写死"开工时与最终头上都要重跑"的原因 |
| D-23 | 取消占位文案 ⇒ 已执行并测到 | backend/main.py：_PLACEHOLDER_NO_RESPONSE（复用 _ERROR_NO_RESPONSE，两处只差句号，不抄第二份）与 _PLACEHOLDER_STOPPED 两档；_post_placeholder(pre, reason)。两条路分别钉住：正文生成器 finally 只在【没走到自然结尾】时记 stopped（M4 把两档塌成一句 ⇒ 杀 4 条）；compensate_unstarted（响应已关而正文从未进入）记 stopped（M7 ⇒ 杀 2 条）。服务侧真故障（空答 / 异常 / bootstrap 抛错 main.py:738）仍走 no_response。前端当场文案未动 ⇒ 见新行 D-32 |
| D-24 | 探针失败往宽还是往窄 ⇒ 已裁：保持宽 | Owner 10-11「按你的推荐」＝保持 _corpus_advertises_category 探测失败 return False ⇒ 无过滤回落；代价由 category_filter_* 三条日志字段承担（可见而不静默）。零代码改动 |
| D-25 | 出厂 Dockerfile 源侧缺陷 ⇒ 已执行（回落 + 可观测两条腿） | backend/Dockerfile：torch 步与 requirements 步各加 `\|\|` 失败回落（官方 CPU find-links / -i pypi.org），选 `\|\|` 而非 --extra-index-url 的理由写在文件里（不合并两源候选，避免版本选择权外移）。.github/workflows/ci.yml 新增 source-probe 作业（PyPI 逐包 pip download --no-deps --no-cache-dir + torch CPU 目录双源核对；主源红 = 降级 warning，两源同红 = 真红），只挂 schedule + dispatch，不占每次 PR。⚠️ 10-11 本机复量：缺陷已自愈（阿里云 pydantic-2.14.0 可取 487 kB rc=0；官方页 torch-2.13.0%2Bcpu-cp311 在列）⇒ 落的是【这一类】故障的兜底，不是复现中的补丁。自检：evidence/d25-probe-selfcheck-20261011.log、evidence/d25-pipleg-selfcheck-20261011.log（假版本必两源皆红、rc=1） |
| D-29 | D-3 的两份 diff 要不要现在落 ⇒ 已裁：本轮不落 | Owner 10-11「按你的推荐」＝不落地。迁移证据已交付且我独立复算过族 ID 13→0，但落它＝换整栈依赖，与本轮【验收对象 = 交付对象】的收口顺序冲突；登记为下一轮首票（连同 D-3 报告 §6 的两条观察项） |

## D. 一句话门禁现状（截至本文件写出时）

候选 `codex/nondeploy-closeout-20261010`；本轮提交笔数用 `git log --oneline 0b54396..HEAD` 现量（本文不写死笔数，写完就会过期）
**未推送、未开 PR、未合并、未轮换任何凭据、未动真实库与容器**。
门禁现量（2026-10-11 05:4x，头 `bffbe1c`）：`ruff check .` rc=0、`ruff format --check .` 283 files rc=0、`mypy .` Success（74 files）、
全量非 slow **1932 passed / 0 failed / 10 skipped / 18 deselected**、覆盖率 **86.37%**（门槛 70）rc=0、
基线闸：collected **1942/1960**、junit tests=1942 skipped=10 failures=0 errors=0；
前端 `tsc` rc=0、`next lint` rc=0、`vitest` **83 passed**（`build:check` 本轮未重跑，前端字节零改动）。
证据 `evidence/final-gates-backend-20261011.log`、`final-gates-junit-20261011.xml`、`final-gates-static-frontend-20261011.log`；
`socket` 守卫与 `pip check` 两轴本轮未重跑（未动依赖与网络面），在册读数见 `reports/gates.md` §38。

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
