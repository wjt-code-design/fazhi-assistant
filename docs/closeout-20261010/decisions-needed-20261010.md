# 待你裁台账（2026-10-10 非部署收尾轮）—— 每条一词可答

口径：只列**现在真的还没定**的。已裁过并执行完的放在最后一节，不再问你。
每条都给了现量证据的位置，你要查就按那条命令查，不必信我的转述。

## A. 卡住交付的（答完才能往下走）

| 编号 | 一句话 | 现量证据 | 我的推荐 | 你可以答 |
|---|---|---|---|---|
| **D-5 凭据与推送** | 候选分支要不要现在普通 `git push` + 开 PR？ | 两条路线现在**都有实测对象集**（`reports/h-ci-and-credentials.md` §2.1 与 §7）：**(a) 普通推**＝**4315 对象**〔2026-10-11 更正，旧写 4301 是第四笔时的数〕，**含那只 13 位历史裸值**（按值反查 **239** 棵树 hits=61/files=1，HEAD 树已无；裸值引入笔 `817e7d3` 既不在陈旧 `origin/master`、也不在远端真实头 `985d53e` ⇒ 无论跟哪个 ref 比，推上去都是 4315，因为两侧**无共同祖先**）；**(b) 无父快照**＝2581 对象（1 commit/173 tree/2407 blob，比 (a) 少 **1734**），**按值反查 0 命中**；⚠️ **原句「树与 `HEAD^{tree}` 逐字相同」在 03:0x 前为假**——那枚旧快照的树 `04dd97ad` 是**第四笔 `3f605de`** 的树，而现 HEAD 树是 `1e91913c`（这条由**独立复核 C §2.1** 抓到，不是我自查）。**03:1x 已按现 HEAD 重生成**：新快照 `1b1c307e…`，树 = `1e91913c` == `HEAD^{tree}`（独立复验 + 冷恢复读回同树），pack 141,794,859 B `verify-pack ok`，并用新 ref `refs/closing/orphan-snapshot-20261011` 钉住（否则两周后会被 gc 剪）；旧三件改名保留为 `orphan-snapshot.{pack,idx,sha}.3f605de.bak`，未删除且同一把值在真实历史里正对照咬住 ⇒ **不外泄是构造性质，不是扫描结论**；快照已出 pack（141,791,027 B）并**冷恢复读回跑通**（临时裸仓只补 `HEAD` 文件，无 ref 指向它）。**10-11 01:5x 复测（推翻 10-10 那句 rc=35）**：`api.github.com` **200**、`github.com` **200**、`ssh -p 443` 认证通、`git ls-remote --heads origin` **rc=0** ⇒ **(a) 两条轨都推得动，远端读数也拿得到**（"网络不通"这道偶然护栏今天没了）。新读到的远端现状：仓库 **public**（`private:false`）⇒ **转 private 会开始吃套餐分钟、且余额匿名读不到**，若你这一轮的目的含"让 CI 真跑一次"，转 private 是可能把目的本身卡死的动作；远端**只有 `master` 一支**（头 `985d53e`，09-17 15:15，**不在本地对象库**）；CI 历史 `total_count=18` = **17 场 push 全 `failure`** + 1 场 `dispatch` success（#1，08-08），**`pull_request` 0 场** ⇒ 精确说法是"push 触发的 CI 从未绿过"。⚠️ **普通推 `codex/*` 分支不会触发任何 CI**（候选 `ci.yml` 的 `on.push.branches` 只列 `[main, master]`）⇒ **"推了就等于有第三方验证"这句不成立**；要远端证据只有：开 PR（这条路历史 0 次，且两侧无共同祖先时合成 merge ref 可能压根不调度）、或事后 `workflow_dispatch`（只认**默认分支上那份**定义，量的不是我这份改动）。内容轴提醒：`ls-tree --long` 按路径加总 368,248,372 B 会**说大近 2.6 倍**（`diag/frozen-index-004/005` 逐 blob 相同、每目录 37 路径只有 30 个唯一 blob）⇒ 真实外发看 pack 141,791,027 B。唯一未知仍是「该旧值是否仍现役」，需读 `.env`（书禁区） | **先轮换 `ADMIN_PASSWORD` 再普通推 + 开 PR**；(b) 留作「你不想现在轮换」的备选，代价是 PR base 无共同祖先、`ci.yml` 触发要按 compare 分流。**签之前要知道的两条连带**：① 推分支本身**不产生 CI 读数**（见现量列最后一条），想要第三方验证就得连"开 PR"一起签；② 远端主线自己 **17/17 push 全红**（09-17 之前就这样），所以**别把"CI 红"当我的候选的判决**——它今天仍是红的，且原因与本次改动无关（这条我只测到"结论分布"，没测失败步骤）。 | 「轮换」/「走孤儿快照」/「先不推」 |
| **D-6 现役环境（G 单）** | 要不要我动宿主机 `backend/venv`（按新 requirements 升级 + 实测回退）？ | `reports/local-environment-switch.md` §1-§3：现役跑的是 **Docker 容器（镜像 3 周前构建，`restart=unless-stopped`，今天 15:08 被自动拉起）**，宿主机没有 python/node 在监听产品端口；`backend/venv` 现量 SQLAlchemy **2.0.51**、torch **2.6.0+cpu**，已在候选声明区间之下，且 `pip check` 有两条既有不一致 | **本轮不动它**，另开一张"开发环境对齐"票：先 `pip freeze` 存证、逐包 `--no-deps` 单变量升、装完复跑全量对账。理由：升级现役=部署动作（越界），升级开发环境不阻塞合并，但**必须在合并后明确告知所有用这个 venv 的人** | 「不动，另开票」/「现在就升」/「写进 DEPLOYMENT 提示就行」 |
| **D-7 F 单（真实模型验收）** | 五类真实模型调用这一轮开不开？ | 执行书 §0.4：F 需要 B/C/D/E 的硬前置 + 候选自审 + 独立复核都过。现在 B/E 有读数、C 两类残余待你确认、D 正在跑；两路独立复核也还在跑 | **等 D 单与两路复核回来再答**，并且开跑前先把 F2 那张表的病例与 gold **冻结入库**（我可以先写冻结稿，零调用、零花费） | 「先写冻结稿」/「等 D 完再谈」/「本轮不跑 F」 |

## B. 不卡交付、但答了我就能继续动手的

| 编号 | 一句话 | 现量证据 | 我的推荐 | 你可以答 |
|---|---|---|---|---|
| **D-8 DB-19** | `RetrieveLawsInput.category` 要不要从 schema 摘掉？ | `reports/trust-and-data-drill.md` §6 与 `evidence/db19-probe.out`：现网 10,266 条 metadata **根本没有 `category` 键**；本轮已把回落收窄成"语料不声明该键才回落"（9 条用例 + 变异仪双向证明判据承重） | **先不摘**。等写侧（`import_docs.py` 一族）真给语料补上 `category` 那天，再决定"摘 or 让过滤真生效"，并且**那天必须删掉回落这条腿**（否则跨类冒充会回来） | 「先不摘」/「现在摘」 |
| **D-9 DB-22** | 401/403/404 这类**配置性拒绝**和 400/422 共用 300 秒冷却？ | 本轮 DB-17 落地的 `mark_rejected` + 300s TTL 是单一档（`backend/llm_registry.py`）；配置性错误不会自己好，300 秒后必然再撞一次 | **分两档**：401/403/404 → 3600 秒且管理台快照单列一格；400/422 → 维持 300 秒。配额账仍一字不动 | 「分两档」/「就 300」/「先不动」 |
| **D-10 DB-23** | `409` 那三条用户可见文案拆不拆？ | 判据层已做（`reason_code` + 结构化日志），文案仍是一条"任务已变化"覆盖三种成因（ownership 冲突 / 预算炸 / 恢复数据非法） | **拆**，并请你给一句措辞授权。我给出三条映射草稿，法律口径我不替你定 | 「拆，草稿发我」/「不拆」 |
| **D-11 在册风险册要不要入库** | `docs/chroma-risk-triage-20261003.md` 现在是**未跟踪文件** | `git ls-files` 现量 0 ⇒ 你 10-10 的"在册接受"只活在这台机器上，不随任何分支走 | **纳入** `docs/`，随本轮文档一起提交（内容一字不改，只解决归宿） | 「纳入」/「不纳入」 |
| **D-12 本轮交付物要不要入库** | 执行书 + 本轮 7 份报告都在仓库外（运行根） | 09-30 那轮的在册教训：报告与执行书未跟踪 ⇒ "39/39 勾"只活在盘上 | **入库**：把执行书与 `reports/*.md`（含 D 单浏览器验收、两路独立复核）复制进 `docs/closeout-20261010/` 并单独一笔提交 | 「入库」/「只留盘上」 |
| **D-14 索引写入口守卫的覆盖面** | B-45 只给 `import_laws` 上了闸，还有几只能写知识库的 CLI 没有？ | 候选树 `git grep -n chroma_dir_guard backend/` 现量：消费方 = `backup_data` / `import_laws` / `rebuild_embeddings` / `switch_embedding`；而 `import_docs.py`（2 处，含 delete）、`verify_new_law.py`（7 处，含 delete）、`eval_chunking.py`（3 处，含 delete）、`backfill_time_meta.py`（1 处）**一只都没有守卫** ⇒ 我上一版「唯一未检查的写入入口」是低估 | **本轮不扩**（执行书 B 单只点名 B-45），把这 4 只登记成下一轮同族票 | 「登记下一轮」/「这轮一起补」 |
| **D-15 DB-7 技术降级白名单** | `TOOL_BUSY` 要不要进 `TECHNICAL_FALLBACK_REASON_CODES`？ | 候选树现量：`backend/routing_metrics.py:13-20` 该集合 5 员（`PLANNER_PARSE_ERROR`/`TOOL_TIMEOUT`/`TOOL_UNAVAILABLE`/`AGENT_BUDGET_EXCEEDED`/`VERIFIER_TECHNICAL_FAILURE`），`TOOL_BUSY` **不在**；它唯一的产点是 `backend/tools/gateway.py:246`，而该分支是 `try_submit(...)` 返回 `None` 就直接 return——`_fingerprints.add` 与 `_call_counts` 都在它**之后** ⇒ 既没发起工具调用、也没记账。⚠️ **更正重核 agent 的一句**：它说「白名单今天确实被扩过一格（`AGENT_BUDGET_EXCEEDED`）」——`git log -S AGENT_BUDGET_EXCEEDED -- backend/routing_metrics.py` 显示那格是 `5e51384`(**2026-09-17**) 进的，**不是今天**；今天动的是 `agent/state_machine.py:29-37` 的 `FREE_STEP_EDGES`（另一只集合，DB-15），两者别混 | **进**（与已在册的 `TOOL_UNAVAILABLE` 同族，且实测满足 `state_machine.py:26` 自写的那条判据「该边是否发起模型或工具调用」）。连带两条一起签才完整：① `record_agent_route` 的 `raise`（`routing_metrics.py:74`）是这只白名单的门，扩格要同时钉测试；② 管理台快照里 `TOOL_BUSY` **单列一格**，别并进 `TOOL_UNAVAILABLE` 的桶（否则容量背压和依赖不可见会混成同一个数） | 「进+单列」/「进」/「不进」 |
| **D-16 DB-10 事件响应文档** | 要不要补 `DEPLOYMENT.md` 的事件响应三行？ | 仓库根 `DEPLOYMENT.md` 里 `grep -n "事件响应\|降级\|incident"` **0 命中**；这是待裁清单里**最便宜的一条缺口**（三行文档，不改码） | **补**，且只写三行：谁在什么信号出现时看哪只计数器（`/metrics` 的降级计数 + 配额账）。法律口径我不写 | 「补三行」/「另开票」 |
| **D-17 F 的可播种语料** | 本轮要跑 F2 那 12 题，语料从哪来？ | `model-validation/gold_denominators.py` 现量（`.out` 已落盘）：候选树里可播种条文只有 **11 对 `(法名,条号)`**（覆盖 8 部法）；`eval_set.json` 28 个期望条号只有 **6** 个能配对、`eval_exam.json` 35 个只有 **3**、`eval_agent_complex.json` 40 个只有 **3**；`eval_negative.json` 15 条期望行为**齐备且不要求条文在场** ⇒ 引用类病例现在**抄谁都会有一半以上是语料缺口造成的假未命中**（执行书 §F3 的 gold 污染立即停止条件） | **本轮不扩语料**，用我已写好的 `model-validation/gold-freeze-draft.md`：12 题全部只用这 11 条 + 负例 + 合成刺激构造（我没编任何法条原文）。若你要 12 题都走真实现成 eval，就得先给一批公开条文进私有副本——那是数据动作，另裁 | 「按冻结稿（11 条内构造）」/「先补公开语料」/「F 本轮不排」 |
| **D-18 两处"8 个代表模型"注释与真值不符** | 这算缺陷还是算文档债，谁来修？ | `backend/llm_registry.py:3` 写"代表模型 **8 个**"、`backend/settings.py:188` 写"内置的 **8** 代表模型默认表"；`DEFAULT_ROLES`（`:44..298`）现量 **27 条**（19 text / 3 vision / 5 voice，全 `tier="flag"`）。复算：`awk '/^DEFAULT_ROLES: /,/^]/' backend/llm_registry.py \| grep -c '"model":'` | **修注释不修表**（表是实配来源，动它＝改路由行为，越本会话边界）。随下一轮同族票一起落，登记为 **DB-24** | 「改注释（DB-24）」/「连表一起审」/「先不动」 |
| **D-19 文档引用悬空（103 处 / 15 文件）** | 推送时要不要把 `codex/local-candidate-closeout` 一起推上去？ | 现量：`fbc29e8` 可解析但 **不是 master 的祖先**（`merge-base --is-ancestor` rc=1），它是本地分支 `codex/local-candidate-closeout`（193 笔）的尖端，该分支**从未推送**；而仓库内 `git grep -o fbc29e8` = **103 次引用 / 15 个文件**。两支关系：`rev-list --count 候选..closeout` = **4 笔独联提交**，且**不新增凭据外泄**（按值反查 closeout 对象集 value_hits=1，候选里也已是 1） | **一起推**（多 4 笔提交，换来 103 处引用在远端可解析）；`--no-ff` 合并不解决这个问题，别把它当已处置 | 「一起推」/「只推候选并登记悬空」/「改写这 103 处引用」 |
| **D-20 「合 master」这件事本身** | 要不要把"合并进 master"留成独立裁决项，本轮只推分支？ | **〔2026-10-11 03:0x 换轴重跑，旧数作废〕** 真实头轴现量（`git merge-tree --write-tree --merge-base=<空树> 9e3cfc5 refs/closing/remote-master`）：候选路径 **2676**、真实头路径 **2136**、**交集 2136 ⇒ 远端全部路径都在候选树里存在**；交集内 blob 相同 **2042**、不同 **94**；判决 **94 条 CONFLICT，全部 add/add**（差异数＝冲突数，两把尺子吻合）。冲突面点名：`.github/workflows/ci.yml`、`.gitignore`、`CONTRIBUTING.md`、`backend/Dockerfile`、`frontend/.env.example`。 ｜⚠️ **原句作废并留下痕迹**：我先前写的是「两树路径 2668 / `origin/master` 261、交集 260、blob 相同 145、不同 115、**115 条 CONFLICT**」——那些数是**本地陈旧跟踪 ref `15562fc`（08-25）** 的轴，不是远端真实头；换轴后成本从 115 次降到 **94 次内容裁决**，且形状从「两棵树几乎不相干」变成「远端内容几乎全被候选覆盖，只差这 94 只」。`merge-base` 仍为空（rc=1）⇒ 无共同祖先未变 ⇒ 等价于重做一轮配置与门禁审查，且书禁"丢弃改动让合并过去" | **留成独立裁决项**：本轮只推 `codex/*` 分支（新 ref，天然非 force、零冲突面），把 **94 次**内容裁决单开一票（旧写作 115 次，已在现量列里作废）。**前置更新（10-11 01:5x）**：原句"先拿到远端真实头（今天 TLS rc=35 读不到）"**已满足**——`git ls-remote --heads origin` rc=0，远端真实头 = `985d53e`（09-17 15:15），且远端只有 `master` 一支。⚠️ **但那 115 条冲突的试演对象是本地陈旧 ref `15562fc`（08-25），不是 `985d53e`** ⇒ 这一票开工前必须**先取回 `985d53e` 再重跑试演**；我**没 fetch**（默认 refspec 会顶掉别的会话正在读的 `refs/remotes/origin/master`，且该对象不在本地库）。要动请给一句授权。 | 「留独立票」/「现在合（要 115 次裁决）」/「连远端那支都不要」 |
| **D-22 J3：生产构建把徽章类名 purge 掉了** | 修不修、怎么修、谁修？ | **机理已证（不再是指断）**：主会话在 H 里做了 build 级最小变异——把 `components/ui.tsx:39` 的 `className={`badge badge-${kind}`}` 换成含静态字面量的等价写法，**重建后四个徽章类名在 `.next/static/css/*.css` 里各出现 1 次**（变异前全 0）；还原文件后重建又回到 0。三次构建 rc 均 0；还原后 blob 与 HEAD 逐字相同、树 0 脏 0 未跟踪。日志 `evidence/h-next-build{,-mutant,-restored}.log`，变异脚本 `evidence/mutate_ui.py`。**范围收窄一条**：D 报告把 `.btn-ghost-dark` 与四个徽章类名并列，但现量 `grep -rn "ghost-dark" frontend --include=*.tsx` **0 命中**（只有 `globals.css:418/423` 的类定义）⇒ 该类**无人使用，被 purge 是正确行为**，不在缺陷面内。真正要修的是 4 个 `badge-*`。**票已写出（这次是真存在，文件已 `test -f` 过）**：`tickets/dispatch-D22-badge-purge-fix-20261011.md`；它的主尺子现跑仍判 `VERDICT=DEFECT_PRESENT`（四个计数 0、阳性对照 `.badge{`=1）。 | **另开修复票**：修法（六个状态映射到静态类名，或给 `@layer components` 加 safelist）由前端票定；修完**必须用 `next build` 产物复量这 4 个类名**，并加一条构建级回归——本仓现在没有任何测试覆盖 dev/build 差异，这正是本次红的成因 | 「另开票」/「本会话顺手修」/「先只登记」 |
| **D-23 取消后的占位文案把"用户取消"说成"服务故障"** | 改不改？ | D 单实测：用户主动停止后前端当场显示"已停止生成"，但服务端为保持成对落的那条 assistant 占位是 **`服务暂时无响应，请稍后重试。`**（`backend/main.py:1037`、常量 `:1090`）⇒ 刷新/换设备看历史时，用户看到的是"服务不可用"。判据（不重复/不跨会话）不因此变红，但这是**用户可见文案与事实不符** | **改**（取消路径的占位文案单独一条），但需你给一句措辞；改动面含后端常量与可能的前端文案断言，属**产品文案决策** | 「改，草稿发我」/「不改」 |
| **D-24 探针失败时往宽还是往窄** | `_corpus_advertises_category` 探测不到集合时就 `return False` ⇒ 触发**无过滤回落**（宽）；要不要改成"探针失败⇒保持空"（窄）？ | `retrieval.py` 现量：探测异常一律 `return False`（`except Exception  # noqa: BLE001`），注释写明"探测能力缺失不该变成用户侧的硬失败（那是另一种静默）"；`tests/test_retrieval_category_narrow_fallback.py::test_probe_unavailable_keeps_the_old_shape` 用**负控**钉住"旧形状若不再兜底，这条负控就没咬住任何东西" ⇒ 是有意为之且被钉。但方向与 D-4"**收窄**"相反：维度存在而值不存在时保持空（不跨类 borrow），探针失败时却回落（可能 borrow） | **维持现状**（可用性优先，且与 D-4 只对"能判定"的情形收窄并不矛盾）；若你要安全优先，改成"探针失败⇒保持空"需同步改那条负控与其理由 | 「维持」/「改成保持空」 |
| **D-25 出厂 Dockerfile 的源侧缺陷怎么处置** | 加回落 / 换单源 / 保持现状只在 CI 加探测？ | 现量：`[5/9]` 步今天的失败是**阿里云 PyPI 的 `pydantic-2.14.0` 文件 404**（索引页 200、文件 404，本机可复现）；`[4/9]` 的阿里云 `pytorch-wheels` 则**冻结 30+ 分钟**（连接判据确认当时无活连接）。本轮的镜像是在**两处偏离**下建成的（torch 走官方源 + 该步加 `pypi.org` 回落），**故不证明出厂路径今天可用**。 | **给需求落点**：出厂 Dockerfile 加 pypi 回落（最小改动、与出厂"不换源"精神冲突最小）；或在 CI 里加一条"构建冒烟"（每天/每 PR 真跑一次 `docker build` 到 `[5/9]` 通过即停），把源侧故障变成**可观测**而不是上线才发现。我倾向前者 + 后者一起 | 「加回落+CI 冒烟」/「只加 CI 冒烟」/「不动」 |

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

## D. 一句话门禁现状（截至本文件写出时）

候选 `codex/nondeploy-closeout-20261010`；本轮提交笔数用 `git log --oneline 0b54396..HEAD` 现量（本文不写死笔数，写完就会过期）
**未推送、未开 PR、未合并、未轮换任何凭据、未动真实库与容器**。
门禁现量：`ruff check .` rc=0、`ruff format --check .` 283 files rc=0、`mypy .` Success（74 files）、
全量非 slow **1925 passed / 0 failed / 10 skipped / 18 deselected**、覆盖率 **86.35%**（门槛 70）RC=0、
socket 守卫非回环 **0**、`pip check` rc=0（候选闭包）。

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
