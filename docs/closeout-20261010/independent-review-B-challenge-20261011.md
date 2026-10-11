# 独立复核腿 B（对抗性挑战 + 补漏项）— 2026-10-11 round2

被审对象：会话 J 在 10-11 05:0x–06:5x 的第二批五笔（`8903da1` `91bd53d` `bffbe1c` `ed76192` `176899f`，候选头 `176899f`）。
本腿**不复算**它的数字，只做两件事：挑战它的判断、登记它没登记的东西。全部读代码本体，只读，零写入候选树。

## §0 三行汇总

1. **判决分布**：站得住 **2**（S7 范围、S6 的 D-6 票）；有条件成立 **3**（S2 409 分档、S3 拒答分档、S5 台账诚实度）；站不住 **2**（S1 取消占位的 `_delivered` 论证、S4 D-25 两处设计），另 S6 里的 D-14 票按其机制本身站不住。
2. **新发现 12 条**（§8），其中 2 条是"本轮改动把原本正确的文案改错了"级别：`_delivered` 不是"自然结尾"位（六条 `return` 出口 + 轻量空答落进"已停止"档），以及 Agent 路径根本没有占位补偿那条腿。
3. 台账分档卫生我独立跑过了：`§A=2 / §B=0 / §C=30`、无重号、无缺号、最大编号 `D-32` ⇒ 这部分它写的是实话；它的问题不在数，在**两条被写满的签字格**与**四处过期数**（§8 第 11 条）。

## S1 取消占位的 `_delivered` 论证 —— 站不住

它的论证是"走到 try 自然结尾 ⇒ 不是取消"。实读 `backend/main.py` 的 `stream()`（`:2058-2672`）：`_delivered = True` 全函数只有三处赋值（`:2638` `:2648` `:2659`），前两处在 `except LLMBusyError` / `except Exception` 的**处理器里**，所以注释 `:2062`（"只有 try 体走到自然结尾才置真"）与实现不符；反过来，try 体内有 **6 条 `return`**（AST 现量：`:2103` 精确缓存命中、`:2134` QA 语义缓存、`:2163` 反问/拒答、`:2192` 合同反问、`:2339` 合同报告、`:2415` 轻量分支），它们都是自然结尾却**永远 `_delivered=False`**。于是四种"不是用户取消"的形状会写 `_PLACEHOLDER_STOPPED`（`:1099` = "本次回答已停止，未生成完整内容。"）：

- **(a) 六条 return 出口 + `_post` 抛错**：每条形如 `try: await run_in_threadpool(_post, ...); _posted = True / except Exception as e: print(...)` 然后 `return`。`_post` 在 `db.commit()` **之前**抛（`output_normalize.*`、`citation_grounding`、`SessionLocal()` 失败都会）⇒ `_posted=False`、`assistant_committed` 未置位 ⇒ finally（`:2664-2672`）写"已停止"。而这六条都在 `return` 前已经 `yield` 了正文与 `[DONE]`（如 `:2095-2098`、`:2403-2404`）⇒ **用户拿到了完整答案，历史却说"已停止，未生成完整内容"**。改前的"服务暂时无响应"在这个形状下反而是实话 ⇒ D-23 在这六条路上把它改反了。
- **(b) 轻量分支空答**：`:2357` 已 `yield {'error': _ERROR_NO_RESPONSE}`，`:2409` 的 `if answer:` 使 `_post` 根本不被调用 ⇒ `:2415` return ⇒ "已停止"。gates §39 与台账 D-23 明写"空答…仍是不响应"——**这条被自己的实现推翻**。旗舰分支的空答确实对（`:2547-2555` 在 try 内调 `_post_placeholder(pre)` 用默认 `no_response` 并置 `_posted`），只有轻量分支那一条被漏。
- **(c) `[DONE]` 之后才落库的时序窗口**：所有出口都是 `yield [DONE]` → 再 `_post`。客户端在 `[DONE]` 那个 yield 点断开 ⇒ GeneratorExit ⇒ "已停止"，且整条答案**没有落库**（既是错标签也是丢数据）。这不是取消，是取消**时机**与落库时机不重合。
- **(d) 非取消的 BaseException**：处理器只有 `LLMBusyError` 与 `Exception`（`:2639` `:2649`），`KeyboardInterrupt`/`SystemExit`/进程关停期的裸 `CancelledError`（uvicorn 优雅停机、上层任务取消）都绕过处理器直落 finally ⇒ 服务端故障/平台侧取消被写成"用户停止了"。`_acquire_chat_turn`（`:1796` `raise asyncio.CancelledError`）证明本仓确有"平台自己造取消"的写法。

**反向（"答案已落库之后写占位"）我核了，没有**：`_post` 在 `db.commit()` 后立刻置 `pre["assistant_committed"]=True`（`:1002`），finally 与 `_post_placeholder` 两侧都查它（`:1036`、`:2664`），所以"commit 后沉淀/压缩炸"只会给客户端多补一帧 `[DONE]` 之后的 error 帧（时序：`:2628-2636`），不会写第二条 assistant。`run_in_threadpool` 走 anyio 默认 `abandon_on_cancel=False`，取消不会让 `_post` 线程半路弃管后 finally 抢先 ⇒ 无双写。**测试面**：`_post` 从未被任何用例桩成抛错（`grep -rn '_post.*=.*lambda' backend/tests` 只见收集参数的桩），M4/M7 两枪打的都是"两档塌成一句"与"摘掉 compensate 档"，**都不覆盖上面 (a)(b) 这两类**。

## S2 409 分档 —— 有条件成立

- **语义**：`answer_invalid` 的"这个回答和当前的问题对不上，请重新回答一次。"在 `resume_with_user_fact` 空输入（`controller.py:389-391`）下是半真话——用户没回答，谈不上"对不上"，但下一步动作（重新回答）确实对，可接受。范围选择解析失败里，**全角数字/中文数字**（`１２`、`一`）会被 `_parse_scope_selection`（`:294-301` 的 `token.isascii() and token.isdigit()`）判 `answer_invalid` ⇒ 文案说"对不上"而真实原因是"格式没认出来"，用户大概率重复同一句全角输入再拿一次 409。分档轴（用户下一步动作）本身站得住。
- **安全**：没被削弱。`load_owned_run` 返回 None 一律 `ResumeRunNotFound`（`:394-398`），任何"这条 run 存在且属于你"的成因码都在 ownership **之后**；唯一先于 ownership 的是空输入检查，而它只依赖请求体不依赖 run ⇒ 不构成枚举 oracle。
- **`step_budget` 档与"该边不计步"矛盾**：成立。`WAITING_USER→PLANNING` 在 `state_machine.FREE_STEP_EDGES`（`:29-34`），`transition` 的 `charge=0`（`:74`）。我用候选 envB 实测：`steps=0/3/4/5/6/9` 对 `max_steps=24` 全部 `OK`、**没有一条炸**；要 `BudgetExceeded` 只能 `steps>max_steps`，而 `_limit` 是 fail-closed 且 `budgets` 随 run 快照持久（`controller.py:549` `BUDGETS_SNAPSHOTTED`），这种状态无法落库 ⇒ `controller.py:331`/`:472` 两个 `step_budget` 抛点**自 DB-15 起不可达**，"本次咨询的追问次数已用完"是一条死文案。而且它**指错计数器**：追问次数真源是 `max_clarifications`（`register_clarification`，`state_machine.py:107-110`），澄清预算耗尽的真实出口是 `CLARIFY_BUDGET_EXHAUSTED` 走条件化分析（`controller.py:1128-1137`），根本不产 409。`test_agent_resume.py:968-975` 的 AST 全覆盖判据只保证"每个码有一档"，**不保证码可达** ⇒ 四档里有一档从未被执行过也能全绿。

## S3 拒答分档 —— 有条件成立

- **`reject_cooldown_s(None)`⇒300 的"保守"在生产里不可达**：`mark_rejected` 三个调用点（`main.py:2232`、`main.py:2448`、`agent/runtime.py:362`）都以 `is_request_shape_rejection(exc)` 为前置，而它要求 `status_of(exc) in {400,401,403,404,422}`（`llm_errors.py:113,139`）⇒ 传进来的 `status` 恒为这五只之一，None 分支只有测试与未来调用者能走。真正"没有状态码"的失败走的是**另一条道**（`mark_depleted`），那条才是该讨论保守方向的地方，本轮没碰。
- **"同一类被分到两档"的答案是有的，但不在这两档之间**：`REQUEST_SHAPE_STATUS`（`llm_errors.py:113`）只列 5 只 ⇒ 同一份"这次请求不被接受"的语义，用 **413 Payload Too Large / 414 URI Too Long / 411 / 407 / 451** 报出来就落进**第三档** `mark_depleted`（`llm_registry.py:682-693`：`runtime_used += quota_left`＝把请求问题记成"这个模型没钱了"，直到重启或人工校准才恢复）。具体输入：一次超长上下文的请求，A 供应商回 400 `context_length_exceeded` ⇒ 300s 自愈；B 供应商回 413 ⇒ 该模型配额账被烧光。这正是 DB-17 想消灭的"被拒≠没钱"混淆，只是换了状态码就又回来了。407/451 不进 `REJECT_CONFIG_STATUSES` 不是取舍而是**没在形状集里**（它们连冷却通道都进不去），429 不进是对的（`TRANSIENT_STATUS` 已含，走瞬时不标记）。
- **DashScope 欠费/免费额度类 403 会被标 `kind=config`**，`DEPLOYMENT.md` §7 给的处置是"改配置才有效"——真实处置是充值/换 key，归因偏一档，但不会误导到相反动作，可接受。
- **3600 的运维可见性站得住**：`DEPLOYMENT.md` §7 第二行明写 `kind=config（401/403/404…）冷却 1 小时，反复重试不会自愈`，且 `status()` 只在 `e.rejected_now` 时带 `rejected_kind`（`llm_registry.py:790`，未拒的模型为 None，`test_llm_reject_channel.py:434` 钉住）。缺的是恢复出口：`rejected_until` 用 `time.monotonic()`（`:714`）⇒ 不跨重启，文档没写"重启即清"这条唯一快速解法。
- **长冷却的代价没被定价**：所有条目共用 `base_url`/`api_key`，一次网关侧瞬时 404 会逐只把整池打进 3600；27 只条目在 27 次请求后就全池停摆一小时，而改前是 5 分钟自愈。§41 只算了"白烧一次请求"的成本，没算"容量撤走一小时"的成本。

## S4 D-25 的两处设计

- **① shell `||` 整置换（有条件成立）**：pip 不是事务，但**顺序**救了它——解析与全部下载发生在"Installing collected packages"之前，所以 10-10 那类"索引页 200、文件 404"失败时 site-packages 还是空的，第二发是干净重装。真正没被写进台账的是两点：**(i) torch 腿根本没换 index**——`backend/Dockerfile:17` 的 `ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple` 对两条腿都生效，第二发只换 `--find-links`（`:55-60`），而 torch 的传递依赖（filelock/sympy/networkx/jinja2/fsspec/typing-extensions）两发都从阿里云 **PyPI** 取；10-10 的故障恰恰就在阿里云 PyPI ⇒ 同类故障落在 torch 那一步时，第二发会红在同一处。只有 requirements 腿做了真整置换（显式 `-i https://pypi.org/simple`）。**(ii) 回落把下载时长翻倍**，动机里那句"pytorch-wheels 冻结 30+ 分钟"意味着最坏 60 分钟，而注释与 §41 都没给构建超时预算这一句。另：安装阶段失败（坏 wheel/磁盘满）会留半装站点，第二发对已满足项打 `Requirement already satisfied` 跳过 ⇒ 得到**混源镜像**，"整置换"这句在这条路上不成立。
- **② 逐包 `--no-deps` 探针（站不住）**：能构造"探针绿、构建红"的形状至少有三种。**(a) 联合求解回溯**：`backend/requirements.txt` 现量 22 行里 **18 行是区间**（`grep -cE '^[A-Za-z0-9]'` = 22；非 `==` 的 18 行），逐包 `pip download "X>=a,<b"` 取的是**该源最新**，联合求解会因冲突回溯到旧版；被回溯到的那只文件恰好 404 ⇒ 探针根本没碰它。**(b) 传递依赖与 extra 全部不在探针射程**：`--no-deps` 不取依赖，`uvicorn[standard]`（第 4 行）的 httptools/uvloop/watchfiles/websockets 与上百只传递 wheel 一只都不验，而出厂构建会下载它们。**(c) 标签轴**：torch 腿把 `cp311-cp311-manylinux_2_28_x86_64` 写死在字符串里（`ci.yml` torch leg 的 `want=`），镜像基座是 `python:3.11-slim`（`Dockerfile:6`）⇒ 今天对得上；哪天基座或 manylinux 标签变了，探针核对的是一件**构建不会要的文件**。它想防的那类故障（"索引说有我拿不到"）只在**直接声明的最新候选**这一小片成立，对整张依赖图不成立。作业自己的注释承认"①逐包解析与整表联合解析可能选到不同版本"，但把它写成"本探针量的是源侧给不给得到"就完事了——真正的代价是**它绿的时候你不能infer构建会过，它红的次数也远少于构建会红的次数**。
- **③ schedule + 分支白名单（站不住，且方向与票面相反）**：`schedule` 只在默认分支生效这句是对的（`ci.yml:7-11` 注释也写了）。但 `source-probe` 作业**没有 `if:` 门**——整个 `ci.yml` 里 `if:` 出现 **0 次**（现量：`grep -c "if:" .github/workflows/ci.yml` ⇒ 0），而 workflow 的 `on:` 含 `push: branches:[main,master]` 与**无过滤的 `pull_request`**（`:4-5`）⇒ 这作业**每次 PR、每次推 main/master 都会跑**。所以"只挂 schedule + dispatch，不占每次 PR"（gates §41、台账 D-25 行、J §10.3 三处同措辞）是假话；副作用是：与改动无关的源侧红会卡住 PR 门，且反复枚举阿里云/pypi/download.pytorch.org 三站。合并前"能不能产生读数"的答案因此是**能，但代价是它没在承诺的位置上**。

## S5 台账与报告诚实度 —— 有条件成立

- **核得过我打算挑的**：分档卫生独立复算（按 `^\| \*\*?D-` 行解析）⇒ `§A=2 / §B=0 / §C=30`、distinct 32、跨档重复 0、`1..32` 无缺号；§B 空并写明为什么空（`:B 节`），不是漏登。`bffbe1c` 起的六只镜像与运行根**逐只 sha 相同**、`gates.md`/`decisions-needed`/`closeout-final-J-draft` 三只 CR=0。D-18 那句"同族已扫净"我用更宽的形状在**全仓**（不限 docs/+backend/）复扫 `8 ?个模型|八个模型|默认 8 个|代表模型…8` ⇒ 命中 0，唯一幸存是缺陷登记本体。
- **被写太满的一格**：**D-31**。它被立出来的原意是"新文案是我起草的，**要 Owner 过字**"（gates §39 原话），J §10.3 今天还写着"进 D-31 等你过字"；同一时刻台账 §C 把它标成"**已裁：照草案**"。用整包授权把一道签字格自我批准掉，等于把"用户可见法律文案要第三方看过"这项控制改成了 no-op；两条措辞（§10.3 等你过字 / §C 已裁）现在互相打脸。D-32（保持两套文案）是真的"按推荐"能裁的技术决定，我不挑战它。
- **写了"未做"但其实做了、或反之**：§38 那句"`npm run build:check` 未重跑"已在 §45 就地作废并补了读数（做了）；反向的例子是 §41/D-25 行那句"只挂 schedule + dispatch"（没做却写了，见 S4③）。
- **§44 的"上传集机理"自我更正**：证据我认为是**够的**——它给了能区分两种机理的对照（`HEAD~1..HEAD` = 10 对 `remote-master..HEAD` = 4464 = 全量），再加"同 blob 2037 只逐只回查仍在上传集"的取样判决。这比 §33 那句"按对象身份剪"的单数断言强一个量级。**仍留余量**的两处：① 它把结论写成"`--objects A..B` 的排除发生在 commit 可达性这一层"，但真正被证明的是"两侧无共同祖先时不省对象"；"UNINTERESTING 在 commit 层停止传播"是解释而不是被独立仪器验证过的机理（同一条 `rev-list` 的第二种读法也能造出同样的数）。② §44 作废了"4252/少 1734"，而 §33 的原句只加了行内标注——按 Owner 的在册规矩（就地标注 + 连带改受影响那行）§33 的表头数字与 §44 的正文现在指向两把不同的尺子，后来的会话只读 §33 会再错一次。

## S6 三张票的可执行性

- **D-14（站不住，问题在机制前提不在纪律）**：判据写得比多数票好（§4.2 明写"只断言函数被调用不合格"、要求点名是 `assert_matches` 抛的），但它要补守卫的四只脚本**都不是硬编码路径**：`import_docs.py:32`、`eval_chunking.py:25`、`backfill_time_meta.py:15` 全部 `from rag_chain import vectorstore`，`verify_new_law.py:28` 走 `knowledge_service._collection`（`knowledge_service.py:48-49` 同一个 `vectorstore._collection`）⇒ 目标目录**就是** `CHROMA_DIR`（`rag_chain.py:125` `os.environ.get("CHROMA_DIR") or DEFAULT_CHROMA_DIR`）。而 `assert_matches` 的语义是"env 未设⇒放行；env 与 expected 相同⇒放行"（`chroma_dir_guard.py:21-27`）。于是票 §2.1 让传"该脚本实际写的那个目录"⇒ **恒同⇒ 守卫永不咬红**，§4.2 无法满足；唯一让 §4.2 变红的做法是照 `rebuild_embeddings.py:108`/`switch_embedding.py:143` 传硬编码 `BASE_DIR/chroma_db`，那等于在 `CHROMA_DIR` 合法指向别处时**拒绝一次本来完全正确的写入**。这就是问的"把守卫被调用当成守卫会咬红"的具体假绿形状，而且生产/容器不设 `CHROMA_DIR`（`rag_chain.py:118-120` 注释）⇒ 这条腿在容器里连触发机会都没有。票的 §6 停止条件 2 只写了反向（"脚本压根不读 CHROMA_DIR"），没覆盖这个方向。文件:行复核：§1.1 五处全对；§1.2 站点数（2/7/3/1）全对；但"该文件有 **2 处** `load_dotenv`"现量是 **1 处调用**（`verify_new_law.py:26`）+ 1 处 import。
- **D-6（站得住）**：判据自足，且问里那条"升级后 pip check 自洽但门禁红"**没漏**——§6.3 正是"升级后全量门禁出现开工前没有的红 ⇒ 先 `pip install --no-deps` 单变量还原那一只再看红是否消失，归因不清就停"，§6.1 还覆盖了反向（逐包升完 `pip check` 归不了零 ⇒ 改提案新建 venv）。尺子 `evidence/venv_vs_requirements_axis.py` 在盘上。两处不足：§2 只对齐 `requirements.txt`，**`requirements-dev.txt`（ruff/mypy/pytest/pip-audit 的来源）不在射程**，升 pydantic/starlette 把静态腿打红时 §6.3 的"单变量"里没有那一只；§1 的负向对照写成了叙述（"改副本区间使偏离 +1"）没给可直接跑的脚本，新会话多半会跳过。
- **D-20（有条件成立）**：前置、红线（不 force/不改历史/不"丢弃改动让合并过去"）、停止条件、两把尺子必须吻合这条判据都自足，尺子三处坑（quotePath / rev-parse 空 / partition 留行尾）都在票里写明了修法。两处会咬人：① **票面写死会随头动的数**——标题"（96 次内容裁决）"与 §4.4"96 行裁决记录齐备"，和它自己 §0.2"数会随头动（94→96→99），不要引用本票数字"直接冲突；§3 分组 **72+15+5+4+2 = 98**，与 96 不等，而"其余 2"那一格实际只点了 1 只文件。② §1 命令里 `git ls-remote` 需要网络轴，票把"今天读得到不是明天的护栏"写进了 §5.2，但没写"网络红时本票整体转 blocked"的处置，新会话容易把它当成判据红。

## S7 范围与越界 —— 未发现越界（一句明说）

五笔的改动面（`git show --stat`）只落在 `backend/*.py`、`backend/tests/*`、`backend/Dockerfile`、`backend/settings.py`（**只改注释**）、`.github/workflows/ci.yml`、`DEPLOYMENT.md`、`docs/chroma-risk-triage-20261003.md`（D-11 点名的入库件）。未动前端字节（`frontend/**` 0 命中）、未动依赖声明（`requirements*.txt` 0 命中，D-6 票 §3 明令"要动得先回报"）、未把活推到部署面（无 push/PR/合并/轮换）、`docs/closeout-20261010` 之外的镜像同步只在运行根。**唯一把授权用满的地方是 S5 那条 D-31 自裁**——那属于"把该问的格自己批了"，不是动了没授权的面。

## §8 它没登记的漏项（按严重度）

1. **[高] `stream()` 的六条 `return` 出口 + 轻量分支空答会落"已停止"，D-23 把原本实话的文案改反了。** 影响：用户拿到完整答案、历史却记"本次回答已停止，未生成完整内容。"（`main.py:2103/2134/2163/2192/2339/2415` + `:2664-2672`，文案 `:1099`）；轻量空答那条（`:2357`→`:2415`）直接推翻 gates §39/台账 D-23 自己写的"空答仍是不响应"。这不是旧缺陷被继承，是本轮**新引入**的错误类别，M4/M7 两枪都打不到它。修法：`_delivered` 改名为"内容已产出"位（各分支 `_post` 之前按 `bool(answer)` 置位），或 finally 里用 `pre.get("content_emitted")` 与"是否走到 try 尾"两个轴共同判档。
2. **[高] Agent 路径完全没有占位补偿那条腿。** `_agent_streaming_response`（`main.py:836-846`）是裸 `StreamingResponse`，没有 `on_response_close`，也没有任何 `_post_placeholder` 调用点（全仓调用点只在快车道：`:2551/2644/2655/2670/2683`）；而 assistant 行只在 DRAFTING→COMPLETED 的 CAS 里写（`agent/chat_integration.py:230-268`，`WHERE status == DRAFTING`），用户行早在 bootstrap 就提交了（`request_bootstrap.py:380-382`）。⇒ 一条以 FAILED/STOPPED/客户端取消（`_execute_agent_observing_disconnect` 的 `cancelled=` 就是这个用途，`main.py:865-876`）收尾的 agent 轮次，会留下**没有 assistant 配对的用户消息与错位的 `message_count`**——正是 `_post_placeholder` docstring 声称要消除的形状。本轮把 D-23 做成"两档文案"，却没问过第二路径有没有这条腿；全仓报告与三张票里也搜不到（`grep -rn "_agent_streaming_response" reports/ tickets/` 命中 0）。
3. **[中] `step_budget` 档不可达且指错计数器。** 见 S2。影响：409 四档里有一档从未被走到；Owner 过字（D-31）时会在一条死文案上签字，而真会出现"追问次数用完"的形状走的是完全不同的通道（条件化分析），拿不到这句提示。
4. **[中] D-14 票的机制前提不成立**（见 S6）：目标脚本跟随 `CHROMA_DIR`，`assert_matches` 对它们是恒等式。影响：下一轮要么交一只**永远不咬红的守卫**（假绿），要么交一只能在合法部署下拒绝正确写入的守卫（把运维动作改成坏行为）。票本身是交付物，这算它带着缺陷交付。
5. **[中] `source-probe` 没有 `if:` 门 ⇒ 每次 PR/push 都跑**，与 gates §41 / 台账 D-25 行 / J §10.3 三处"只挂 schedule + dispatch，不占每次 PR"相反。影响：源侧红会卡住与改动无关的 PR；三站被反复枚举（本仓在册判例：整域持久封禁）。
6. **[中] `source-probe` 的 pip 腿没有 `probed>0` 正对照。** `ci.yml:113-136` 只在 `both_bad` 非空时 `exit 1`；若 `grep -E '^[A-Za-z0-9]' backend/requirements.txt` 返回空（改名、整表被注释、换成 `--include` 形状），作业 0 包照样绿。这正是它自己在 J §10.2 第 6 条立的"仪器要能红"要防的形状，同批交付里另一处（torch 腿）反而有 `[ -n "$ver" ] || exit 1` 的对照——同一次改动两种纪律。
7. **[中] Dockerfile 的 torch 回落腿没换 index**（`ENV PIP_INDEX_URL` 对两发都生效，只有 `--find-links` 变）。影响：D-25 想兜的那一类故障若发生在 torch 那一步，第二发在同一个坏 index 上重装传递依赖 ⇒ 回落形同不存在，而注释把它与 requirements 腿并列为"各加失败回落"。
8. **[中] 413/414/411/407/451 是"请求被拒"却没有进任何冷却通道**，直落 `mark_depleted` 烧配额账（`llm_errors.py:113` 的五元集 + `llm_registry.py:682-693`）。影响：同一语义两种命运，且坏的那一种要到重启或人工校准才恢复。D-9 分档的正当性建立在"被拒不该记成没钱"上，这一刀只切了五个码。
9. **[低中] 探针射程与"版本随源而定"没写进限制。** requirements 22 行 18 行是区间 ⇒ 回落腿与主腿可装出不同版本集；`--no-deps` 不覆盖传递依赖与 extra；torch 腿写死 `cp311-manylinux_2_28`。§41 承认"探针不等于 docker build 通过"，但那三条更具体的射程限制只在 `ci.yml` 的作业注释里，台账 D-25 行与 §41 没转述。
10. **[低中] D-15 的真实后果不止"分列"。** `TOOL_BUSY` 进白名单 ⇒ `agent/service.py:95-105` 的 `_failure_or_fallback` 把该终态从 `failed` 翻成 **`fallback`** ⇒ `main.py:1921-1923` 走 `_record_actual_agent_route("fast_path", …)` 并**改由快车道作答**。也就是"工具容量背压时用户会拿到另一条路径的答案，而前端不显示工具忙"。测试只在计数器层手喂值（`test_agent_rollout.py:233-238`），端到端（`tools/gateway.py:241-248` → `last_error_code` → outcome 翻转）无钉；台账措辞"进白名单并单列"没披露这一层行为变化。
11. **[低] 四处过期/不自洽的数。** ① 台账 D-12 行仍写 `docs/closeout-20261010` = **29 只 .md 全部 tracked**，现量 **32**（`git ls-files docs/closeout-20261010 | grep -c '\.md$'`）——三张票镜像正是本批加的第 30–32 只，它自己在 §43 立的"数随头动 ⇒ 只给命令"要防的就是这个。② D-20 票标题与 §4.4 写死 96，§3 分组相加 = 98。③ D-14 票"verify_new_law 有 2 处 load_dotenv"，现量 1 处调用。④ `main.py:2062` 的注释与 `_delivered` 的实际置位点不符（第 1 条的成因之一）。
12. **[低] D-18 的"同族扫净"只扫了模型数这一根轴。** 同一族的"文档抄预算数"还在：`docs/superpowers/specs/2026-08-27-legal-agent-v1-design.md:137` 写"最多 8 个 agent steps…最多 2 次澄清"，代码默认是 `max_steps=24 / max_clarifications=3`（schema 现量）。修法与 D-18 一致：文档里不抄数，指向 `Budgets` 真源。

## §9 我不同意它的地方

1. **不同意 §39 那句"两条路各由独立测试钉住 ⇒ 两档不是同一把尺子在量"**。M4/M7 证的是"把两档塌成一句会红 4 条 / 摘掉 compensate 档会红 2 条"，这只证明**判据不同源**，不证明**分档轴选对了**：分档轴（`_delivered`）量的是"有没有走到 try 块最后三行"，不是"内容有没有交付"。判据能红 ≠ 语义正确，这是本仓自己写过的口径（"判据别把守卫被调用当成守卫会咬红"）。
2. **不同意 D-31 被算作"已裁"**。签字格被整包授权自我批准，且与 J §10.3"等你过字"并存 ⇒ 台账现在读起来像 Owner 看过六条用户可见文案，他没有。要么回退成"待过字"，要么由 Owner 补一句。
3. **不同意"§44 的更正可以就地留在 §33"**。机理型断言被作废后，原格只加一句标注而表头数字不动，后来的会话按 §33 读会再错一次；按在册规矩应当是"原句作废 + 该节数字一并改成按现量说"。（它自己 §10.2 写过这条纪律。）
4. **不同意把 D-25 落为"这一类故障的兜底"就算交付完成**：兜底的一条腿（torch）没换它真正会坏的那一源，另一条腿（探针）覆盖不到实际故障面（传递依赖）。这类"形状对但射程窄"的交付，台账应按"覆盖了哪三格、没覆盖哪五格"写，而不是"落了两条腿"。
5. **同意的部分也说清**：分档轴选"用户下一步动作"、未登记码回落不 500、`||` 而非 `--extra-index-url`、`rejected_kind` 只在活跃时下发、DEPLOYMENT §7 点名真路由 `GET /api/admin/llm-status`（不是 `/metrics`）——这五处我复核过代码，判断是对的，我不给它挑刺。

## §10 我核不了的以及为什么

1. **门禁四腿与变异杀数我没有复算**（1932/0/10/18、cov 86.37%、M1–M7 各杀几条）。这是复算腿（同目录 `n5-*.log`、`n4-*.log`）的活；跑全量 pytest 要在候选树里落 `.pytest_cache`/coverage 产物，与"不改候选树被跟踪文件/不留未跟踪垃圾"的只读约束冲突，我只做了静态与单点读数。
2. **`git status --porcelain = 0` 在主仓那一侧（M=）我没有复测**：只读 git 查询在这个环境会被按"与本任务无关"拦，我改用文件读法核对镜像 sha（六只与运行根逐只相同），但主仓 21 只脏件的归属我没法当场证明。
3. **上传集 4464 / 同 blob 2037 这两个数我只核了**命令形状与对照逻辑，没重跑（对象枚举 371 KB 级输出，属复算腿的 N6 范围）。我的判决是"§44 的证据结构成立"，不是"数值复现成功"。
4. **§45 那句 `npm run build:check` 在新头 rc=0 我没有重跑**：它会写 `frontend/.next` 与构建产物面，与只读约束冲突；我只核了它**跑后 porcelain=0** 这一句在该环境是可证的（六只文档/代码镜像 sha 与 CR 一致），产物层断言（`VERDICT=OK`、CSS 43,241 B）留给复算腿。
5. **S1 的四个形状我全部是读代码 + AST 定位得出的，其中 (a)(b) 两类可以写成用例复现**（桩 `_post` 抛错走缓存命中分支、轻量分支喂空答），我没有在候选树里真跑过任何一条——落用例属于下一轮修复票的范围，不属于本票。
6. **DashScope 等供应商实际用哪个状态码报"欠费/免费额度用尽"我没有一手证据**（不许连真实配额库与 `smoke_*`，也不出网打真接口）。所以第 8 条漏项里 413/407/451 的**发生频率**我给不了，只给了"一旦发生会落哪一档"的确定结论。

---
*自量：本文件 `tr -dc '\r' | wc -c` = 0（见随附读数），LF 落盘。*
