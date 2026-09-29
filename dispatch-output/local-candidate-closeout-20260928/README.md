# 本地候选收口执行证据（2026-09-28）

状态（2026-09-28 接手会话更新）：候选代码已按 F 节在 `codex/local-candidate-closeout` 提交（4 笔 / 7 文件，`HEAD = fbc29e8`），
提交后门禁已在无未提交修改的候选树复验（`postcommit-gates.log`）。**本地候选仍未收口，不得作为发布就绪结论**：
依赖风险 47/57 条未获 Owner 接受，真实 rerank 验收因凭据轮换暂停。三态结论 = **阶段仍未完成 / 候选受阻**（详见报告 §9.12.17）。
🚨 本轮另发现本仓库对嵌套分支引用的写入缺陷，见文末「仓库 git 缺陷」。

- 用户批准：pypdf / FastAPI 隔离升级、必要兼容修复和本地提交。不部署、不 push、不写真实库、不调用生成模型。
- 基线：`aec8d5c22a202c2b7b711d169096777d316f2932`。
- 候选工作树：`C:/Users/33393/.codex/worktrees/local-candidate-closeout/ai-legal-helper`。
- Python 3.11 独立环境：`C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/venv`。
- 下载派单：`download-brief-for-assistant.md`；助手回执：`download-report-from-assistant-20260928.md`。使用离线 wheelhouse 安装到独立候选环境，没有修改共享 venv。
- 主树已有两份报告修改已审阅并保留；未批量暂存。新增本证据目录后 `git ls-files --others --exclude-standard` 展开为 34085 个未跟踪文件；不能与此前 518 个折叠状态条目直接比较。

## A：Git 与数据保护

- `protected-before.json`：保护库文件的大小、UTC mtime、SHA-256；尚待最终后测比较。
- 完成后测：41 个保护对象的大小、UTC mtime、SHA-256 均与基线一致，见 `protected-after-check.log`。
- 独立 Git 审计库：`C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/remote-audit.git`。
- 初次完整远端 fetch 超过五分钟无 pack 数据增长，终止本任务的两个 fetch 进程；未重试同一命令。随后 `--filter=blob:none` 获取成功，本地仓库 remote refs 未改。
- 最新远端 master：`985d53e4ee81efc066cc6915abcba98954e7d408`；本地：上述基线；`merge-base` rc=1（无共同祖先）；`rev-list --left-right --count local-master...remote-master` = `189 204`。
- `remote-tree-diff.txt` 为本地→远端方向的差异，不是待实施删除清单。
- `remote-ci.yml` 为远端读取的工作流：push 只监听 main/master，另监听 PR。新建快照分支 push 本身不触发这份工作流，也不会抹除祖先中的敏感内容。
- 同步建议：先审查具体发布树和历史敏感内容，之后单独批准建立远端基线上的集成分支、迁入已审阅改动并提 PR。不直接强推、不无审查合并两段不相关历史。本轮只核对，不执行同步。

## B/C：兼容性检查

- PyPI 版本元数据查询：pypdf 6.16.1 与 FastAPI 0.141.1 均存在，返回 vulnerabilities 空列表；这不是全依赖集审计结果。
- 先用现有解释器、但在无 `.env` 的独立工作树中运行新增 PDF 测试，数据库均由 conftest 隔离。`pdf-red-existing-runtime.log`：2 failed / 5 passed，两个坏 PDF 上传接口实际返回 500。
- 根因：`pypdf.errors.PdfStreamError` 属于 `PyPdfError`，接口只捕获 `ValueError`。在共用 PDF 解析边界转换该异常族，不捕获所有 Exception、不向客户端回显解析异常原文。
- `pdf-green-existing-runtime.log`：PDF + 既有 DOCX 用例 20 passed / 7 warnings，rc=0。这是原运行库上的修复对照，不冒充新候选依赖的验收。
- `test_upload_rate_limit.py` 对两个上传路由启用真实限流器；用坏扩展名请求避免任何知识库写入；独立验证第 21 / 11 次返回 429。
- `limiter-existing-runtime.log`：两条上述限流断言均通过，rc=0；新候选环境测试包含在最终完整回归内。
- 最终独立环境版本记录：`candidate-versions-final.log`；`pip-check-final.log` 为 `No broken requirements found`。B/C 完整相关测试及契约回归见 `fastapi-contract-tests.log`（84 passed、1 skipped）。
- 最终 requirements 审计 `candidate-requirements-pip-audit.json`：47 条/8 包；独立环境全量审计 `candidate-installed-pip-audit.json`：57 条/10 包（多出的包含测试/开发工具）。两者都是未接受的风险读数，不是通过结果。
- 两项升级并用的 requirements 提案见 `requirements-web-candidate.txt`；`audit-web-proposal.json` / 日志重新解析出 47 条原始告警（8 个包），而旧声明是 138 条（10 个包）。这是 requirements 解析集的审计结果，**不是**候选 venv 已通过测试，也不是 47 项风险已接受。

## D：语料副本与剩余风险

- 候选输入 SHA-256：`f32f585259c9a3816f34bab12558caad878185538d90da943f611a83eb3631b1`，与旧记录相同；三条 `content` 与各自 `source_document_sha256` 逐项一致。本轮直接将民法典 1260（去空白后 141 字）与仲裁法 27（去空白后 272 字）的完整候选正文逐字对照 `data/laws_clean/`，两者均命中；合同法 428 仍为单源。这也核实了既有取数记录**后续复核**所述结论，取代同文件更早的“27 仅第一款有旧记录”阶段状态。哈希一致、旧库对照仍不等于独立法务签字。官方公开文本的参考入口：[人大公报民法典](https://www.npc.gov.cn/wxzlhgb/c27214/gb2020/202006/P020230313538731037747.pdf)、[人大网仲裁法](https://www.npc.gov.cn/WZWSREL3pncmR3L25wYy8vLy94aW53ZW4vbGZnei96eGZsLzIwMDctMTIvMjkvY29udGVudF8xMzg3ODA5Lmh0bQ%3D%3D)、[中国政府网合同法](https://www.gov.cn/banshi/2005-07/11/content_13695_11.htm)。本轮未改变候选正文、日期或溯源字段。
- 原运行环境在稳定 Chroma 副本上的 `corpus-existing-runtime.log`：validate-only 与 dry-run 均 rc=0、无记录变化；首次实际导入将 2 个无日期旧块替换、新增 3 条，跳过 0；再次导入后仍只有每条一份 import 块，共 10267 条，目标语义哈希及无关记录哈希不变。脚本第二轮报告“替换 3 旧片段”指替换刚导入的同版本块，不是再次删除原始历史块。
- 另一份从原始稳定快照恢复的副本见 `corpus-restored-existing-runtime.log`；全记录与元数据哈希匹配首次导入前的 10266 条状态。38 个原始 Chroma 文件拷贝前后逐文件哈希一致。
- 可复现实验脚本 `verify_corpus.py` 只接受本任务的两个临时副本路径，环境变量在导入后端模块前设置为隔离库。
- 26 组非 PDF/Web 依赖通报的逐项触发条件、可达性证据及待裁状态见 `residual-risk-review.md`；原始 47 条仍保留，助手未接受风险。

## E：已独立完成的前端检查

候选前端文件未改动，基线同上；因此可先行验证，不需要等待 Python 包下载。

- `frontend-install.log`：`npm ci --no-audit --no-fund` rc=0，454 packages；存在废弃包警告，未顺手升级。
- `frontend-check.log`：`npm run check` rc=0，7 test files / 54 tests passed。
- `frontend-build.log`：`npm run build` rc=0。
- 这些结果不代表依赖安全审计通过，也不代表服务器或远端 CI 已验证。

## 最终候选验收与暂停项

- `backend-full-tests-final-v2.log`：独立候选 Python 3.11 环境，`1650 passed, 10 skipped, 18 deselected`，总覆盖率 85.25%，rc=0。两次较早日志保留失败诊断，不得把 `backend-full-tests.log` 或 `backend-full-tests-final.log` 当作最终结果。
- `mypy-final.log`（74 source files）、`ruff-final.log`、`ruff-format-final.log`、`pip-check-final.log` 均通过；质量守卫 `agent-quality-test.log` 为 9 passed。
- `qa-log-capture-targeted-final.log` 为两项日志断言修正后的定向验证（2 passed）。最终全量回归已包含该测试修正。
- 真实 rerank 未复验；生成模型没有调用。检查本地配置时有命令意外把 `.env` 中的 rerank 凭据值打印到了工具输出。未将凭据值写入本仓库文件，但应按已暴露处理：Owner 轮换活动 SiliconFlow key 与保留的旧备用 key 后，另行决定是否恢复一次真实 rerank 验收。这里和其他报告均不记录凭据值。
- 依赖告警、rerank 验收和本地交接收口未完成，因此当前结论是“阶段仍未完成/候选受阻”，不是“本地候选就绪”。远端推送、真实库写入、生成式冒烟及部署属于第 4 节后续阶段，当前不派发、不执行。

---

## F：提交与提交后复验（2026-09-28 接手会话）

**候选分支提交（只在 `codex/local-candidate-closeout`，未合入 master、未推送）** —— 共 4 笔 / 7 文件，`HEAD = fbc29e8`：

| 提交 | 内容 |
|---|---|
| `ca0eb5e` | `requirements.txt` pypdf 6.16.1；`knowledge_service.py` 把 `pypdf.errors.PyPdfError` 转受控 `ValueError`；新增 `tests/test_pdf_upload.py` |
| `ecdc6b3` | `requirements.txt` fastapi 0.141.1；`main.py` 补 mypy 必需类型标注（3 处，依据 `backend-static-gates.log`）；新增 `tests/test_upload_rate_limit.py` |
| `39f4266` | `tests/test_request_bootstrap.py` 留痕捕获改独立 Handler（语义不变，只换捕获方式） |
| `fbc29e8` | `docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md` 执行口径修订 |

`aec8d5c..fbc29e8` 的改动面（`git diff --name-status`）：`M backend/knowledge_service.py`、`M backend/main.py`、
`M backend/requirements.txt`、`A backend/tests/test_pdf_upload.py`、`M backend/tests/test_request_bootstrap.py`、
`A backend/tests/test_upload_rate_limit.py`、`M docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md`。

**提交后门禁（无未提交修改的 `fbc29e8` 候选树，日志 `postcommit-gates.log`）**

| 步 | 读数 | rc |
|---|---|---|
| `pip check` | No broken requirements found | 0 |
| `ruff check .` / `ruff format --check .` | All checks passed / 全部已格式化 | 0 / 0 |
| `mypy .` | Success: no issues found in 74 source files | 0 |
| `pytest -m 'not slow' --cov=. --cov-fail-under=70` | **1650 passed, 10 skipped, 18 deselected**，coverage **85.25%**（211.38s） | 0 |
| agent-quality `ruff check` / `format --check` / `test_budget_guard.py` | All checks passed / 4 files already formatted / **9 passed** | 0 / 0 / 0 |
| `pip_audit -r requirements.txt --format json` | **47 条 / 8 包 / 扫 132 包**（重试日志 `postcommit-pip-audit-retry.log`） | 1（漏洞非零） |

- **第 9 步首跑是扫描器自身失败，不是漏洞读数**：`postcommit-gates.log` 抛 `pypi.org` `ReadTimeout (read timeout=15)`，rc=1。
  按纪律不与"漏洞非零"混算；分析后重试一次并加大到 `--timeout 60`，得上面那行 47/8。
- 第 6–8 步首次跑红（`ruff E902 系统找不到指定的文件`、`pytest file or directory not found`）**是路径形态假红**：
  本机把 `/c/Users/...` 当相对路径解析成 `C:\c\Users\...`。换 `C:/Users/...` 重跑，日志中以 `[6R]/[7R]/[8R]` 记录，三步全 rc=0。
- 前端本轮未改，沿用既有读数（`npm ci` rc=0；`npm run check` 7 files / 54 passed；`npm run build` rc=0）。
- 保护对象复验：41 个对象在提交与测试后重算 size+SHA-256，**41/41 与 A 基线一致**（`protected-postcommit-check.log`）。
- 候选树 `backend/chroma_db` 为 144KB 空桩（测试自建），**不是**主树 349MB 真实库 ⇒ 候选测试不污染真实 KB。

**未完成与阻塞（三条）**：① 凭据轮换（Owner）⇒ 真实 rerank 未复验，无本阶段 24/24 新读数；② 依赖风险 47/57 条未获接受 ⇒ 不能判“就绪”；
③ 下方仓库 git 缺陷。

---

## 🚨 仓库 git 缺陷：`refs/heads/<目录>/<名>` 的写入被静默抹除（2026-09-28 首次观测）

- 现象：`git commit` 到 `codex/local-candidate-closeout` 后，该分支 loose ref 消失，`git log` 报
  `your current branch ... does not have any commits yet`；**提交对象与分支 reflog 完好**（恢复靠 reflog）。
- 复现（对任意嵌套引用成立）：`git update-ref refs/heads/x/y <sha>` → rc=**0**、reflog 有记录、ref 文件不存在；
  对**已存在**的嵌套 ref 做同样操作，ref 文件连同父目录一并被删。对照：顶层名（`refs/heads/zz`）正常；
  `git init` 的全新仓库里嵌套引用也正常 ⇒ **不是 git 2.55 通用 bug，本仓库特有**（`extensions.worktreeConfig=true`
  与多 worktree 在临时仓库里复现不出）。
- **决定性时序证据（2026-09-29 实测，脚本 `watch-ref-write.py`，10ms 级轮询）**：git 其实**写成功了** ——
  `mkdir refs/heads/zzy` → 建 `one.lock` → 写 reflog → **`.lock` 改名为 `one`（ref 出现）** → 之后
  **113–144 ms（三次：122.5 / 113 / 124.5 ms）** 该 ref 与其父目录被**另一个进程**删除。
  ⇒ **推翻"git 写失败"的假设，改判为"外部进程在 git 提交 ref 后约 120 ms 删除它"**。
  旁证：手工 `printf >` 写的同名 ref **可长期存活**（已复核 ≥25 分钟）；顶层 ref 不受影响。
- 应对（本轮实际使用，已验证）：每次提交后按 reflog 回填引用 ——
  `mkdir -p .git/refs/heads/codex && printf '%s\n' "$(tail -n 1 .git/logs/refs/heads/codex/local-candidate-closeout | awk '{print $2}')" > .git/refs/heads/codex/local-candidate-closeout`
  然后核对 `git worktree list` 与 `git status`。
- 未定因；排查期建的对照引用与临时仓库已全部清除。**接手者动该分支前必须先复核引用仍在。**

**双保险（2026-09-29 落地，Owner 选「分层：回填+备份，根因另立诊断」）**

1. **恢复脚本**：`restore-candidate-ref.sh`（本目录）。两级恢复 + 三处核对，已实测两条路径：
   引用存在时直接判 OK；把 ref 文件挪走后能从 reflog 恢复并核对 `rev-parse`/`worktree list`/`log`。
   用法 `bash restore-candidate-ref.sh [仓库路径] [bundle 路径]`。
2. **增量 bundle 备份**（**故意放在仓库外**，以便 `.git` 本身受损时仍可用）：
   `C:\Users\33393\Desktop\ai-legal-helper-bundles\local-candidate-closeout-fbc29e8.bundle`
   —— 7299 B，含 `refs/heads/codex/local-candidate-closeout = fbc29e8`，前置依赖 `aec8d5c`（本机存在）；
   sha256 `f706c1ccf80e39c214e29dd90b819a5416636d4d725c8b52d3a94bfc41c36de7`。
   核对：`git bundle verify <bundle>` → `is okay`。重建：`git bundle create <bundle> codex/local-candidate-closeout --not master`
   （**路径必须用 `C:/...` 原生形态**，用 `/c/...` 会报 `.bundle.lock: No such file or directory`）。
3. 根因（哪个进程删的）**未定**，已列为待排的定向诊断；期间每次提交后都要回填并核对。

**未跟踪产物归属**：本轮只暂存本证据目录与本计划；主工作区未跟踪 34107 个（`dispatch-output` 占 33938），未 `git add -A`；
其余 worktree 只登记不动。

---

## G：B 档运行时探针（2026-09-29 接续会话，Owner 裁「先做 B 档探针，再裁依赖风险」）

这一节把 `residual-risk-review.md` 的 B 档从**静态 0 命中**升级到**运行时 0 调用**。
判定表由读数现生：`python b_probe_matrix.py` → `b-probe-verdict-matrix.md`（**报告引用那张表，别手抄这里的数**）。

### G.1 跑了什么（命令与场）

| 场 | 驱动 | 完整性读数 | 结果 |
|---|---|---|---|
| 仪器自检 | `PROBE_OUT=<本目录>/b-probe-selfcheck.json python b_runtime_probe.py selfcheck` | 桩装上 19/22，未 resolve 的 3 只是 `G4d/G4f/G4g`（自检场没导入那几个模块），`failures` 0 | `SELFCHECK PASS` rc=0 |
| 自检负例 | `PROBE_OUT=<本目录>/b-probe-selfcheck-break.json ... selfcheck --break G3b` | 故意撤一只桩 | rc=1，红因正是 `G3b: 桩被 ... 撤走`（装上 18/22、failures=1） |
| 请求体脱敏对照 | `python b_probe_net_sanity.py` | 带哨兵口令/哨兵头值的 POST 打到环回 `:9`；7 条断言里 4 条钉"键里确实记了 URL/方法/头键名"、3 条钉"哨兵串 0 命中" | rc=0，7/7 PASS（`b-probe-net-sanity.log`） |
| 副本树 | `python b_probe_build_tree.py` | `git archive fbc29e8` → 2563 文件；禁止对象 0；pypdf/fastapi 固定均在 | `b-probe-tree-build.json` |
| 测试场（两腿） | `python b_probe_run_suite.py <tree>` ×2 | selected=**1660** / total=1678 / deselected=18；junit **1660**；failed **0**；rc **0**；**171.6s / 176.9s**；装桩前已加载=**无**（⚠️ `total=1678` 只在运行器**标准输出**打印过，`b-probe-pytest-*.log` 里落的是 `collected = 1660` 与 pytest 自己的 `1650 passed, 10 skipped, 18 deselected` ⇒ 1678 由 `1660+18` 推得，不是日志里的现量） | `b-probe-readings-pytest-20260929-103147.json` + `...-103511.json`（逐条零差异，见 G.6） |
| 应用路径 | `python b_probe_app_paths.py both <tree>` | qa 与 upload 两步均跑通（upload `chunks_written=2`）；装桩前已加载=`[]` | `b-probe-readings-app-20260929-103841.json` |
| 两腿复跑比对 | `python b_probe_pair_check.py <A> <B>` | 22 只桩五轴差异 **0**；`collected`/`exitstatus`/`compile`/`kinds`/`total`/在场模块/别名/装桩前 全同；junit 从各自 `junit.xml` **现算** 1660==1660 | rc=0（`b-probe-pair-check.log`） |
| 网络归类审计 | `python b_probe_net_audit.py --selftest` 再 `... <三份入库读数>` | 归类器 **15 条合成键**全对（9 条必须判非环回，含 IPv6 四元组、十进制 IP、`os.system` 带 URL 三种**前一版会静默漏掉**的形状；4 条钉"不许误伤"；2 条单列）；对**全部 206 个键**逐键归类（每测试腿）：环回 **312** / 非环回 **1** / 无主机字段 **35** | rc=**1**，红因正是那 1 次非环回（已归因，见下） |
| 归类器的数据侧对照 | `python b_probe_net_audit.py --injected-selftest` | 往**真读数的副本**注入 2 类外发（云元数据 IP + 其十进制写法），且只同步 `kinds/total` ⇒ "自洽"轴保持绿，红的只能是外发判定 | rc=0：3 条非环回全抓到、整链路判红、临时件已删（`b-probe-net-audit-injected.log`） |
| 非环回归因 | `python b_probe_dns_trace.py <tree>` | 独立插件另跑一场（junit 1660、rc 0、非环回 1 次），带用例名与栈帧 | `tests/test_phase3.py::test_healthz_components` → `main.py:340` 的 `socket.create_connection` |
| 主张复算 | `python b_probe_claim_check.py` | 61 条主张逐条对着入库读数重算 | **61/61 通过** rc=0（`b-probe-claim-check.json`） |
| 复算器变异对照 | `python b_probe_claim_mutants.py` | 12 只"改期望值"变异（覆盖 11 条主张：urllib 键形那对有两只），要求每只整体 rc=1 **且红的正是该钉的那一条** | **12/12 被杀** rc=0（`b-probe-claim-mutants.log`） |

复现要点：`PYTHONPATH` 指向本目录（插件与 canary 从这里 import），解释器用候选 venv，
环境变量按 `docs/handoff-local-candidate-closeout-20260929.md` §4 那一套假值 + 库路径全指临时目录，
`CHROMA_DIR` 指空副本目录（**不引入真实语料**，因此本节的检索读数不含命中后的上下文组装；那一段由测试场覆盖）。

### G.2 判定（逐条公告 → 运行时事实）

- **G1 Core 反序列化与模板构造**（7 只桩：`load`/`loads`/`dumps`/`load_prompt`/`load_prompt_from_config`/
  `PromptTemplate.from_template`/`ChatPromptTemplate.from_messages`）—— 两场均 **ZERO-CALL**。
  另有一条静态事实支撑：候选工作树 `backend/` 里 `PromptTemplate` **0 个文件命中**（含 tests 与 scripts 全扫），
  问答链是 `rag_chain.py:137` 的 `llm | StrOutputParser()` 直接吃 messages 列表，不经模板类。
- **G2 图片 token 计数（SSRF / DNS 重绑定）** —— 测试场三只桩全 **ZERO-CALL**（这条是真阴性：`langchain_openai` 在该场在场）。
  应用路径场则是**未测**不是阴性：那个场的驱动只 import `rag_chain` / `retrieval` / `knowledge_service`
  （`b_probe_app_paths.py:71-73,89`），**从不 import `main` / `llm_registry`**，而 `llm_registry.py:20` 是模块级
  `from langchain_openai import ChatOpenAI` ⇒ 真实 `/api/chat` 一定会加载它。
  所以"应用场 `chat_models.base` NEVER-IMPORTED"只说明**驱动没建聊天客户端**，不能当"应用不走这条路"的证据；
  复算器已把这条不对称钉成主张（"G2 在该场是未测"）。基类两只桩在该场 ZERO-CALL 同理是"没对象可计"。
  版本级线索：候选实装 `langchain-openai 0.1.7` 的 `BaseChatOpenAI.get_num_tokens_from_messages` 走 tiktoken，
  该文件内 `openai_image_token_length` / `requests.get` / `_try_download_image` **均无命中**；
  这与"公告所述实装版本"是否吻合仍属公告核对问题，本探针只报"运行期 0 调用"。
- **G3 Transformers 模型与 config 加载** —— 两场均 `AutoConfig.from_pretrained`、
  `PreTrainedModel.from_pretrained`、`PreTrainedTokenizerBase.from_pretrained`、`SentenceTransformer.__init__` **各 1 次**，
  调用方全部归到 **`backend/rag_chain.py:39`**，模型名只有 **`BAAI/bge-base-zh-v1.5`**（源码常量），
  且 **`trust_remote_code` 取值 = `False`** —— 但这条**只对把它当实参传进去的两只成立**：
  `G3a PreTrainedModel.from_pretrained`（kw 含 `trust_remote_code`）与 `G3b AutoConfig.from_pretrained`（同）读数都是 `['False']`；
  `G3d PreTrainedTokenizerBase.from_pretrained` 与 `G3e SentenceTransformer.__init__` 的实参里**根本没有这个键**
  （G3d 是 `_commit_hash/_from_auto/cache_dir/revision/token`，G3e 是 `cache_folder/device`），
  所以那两只不能算"信任远程代码 = False"的证据，只能说"这次调用没走那个参数"。`PretrainedConfig.from_pretrained` 0 次。
- **G4 未被应用引用的 loader / 追踪 / Hub 拉取** —— `langsmith.middleware.TracingMiddleware`、
  `SitemapLoader`、`EverNoteLoader`、`FAISS`、`GraphCypherQAChain` 两场均 **NEVER-IMPORTED**；
  `langsmith.client.Client.__init__` 与 `Client.pull_prompt` 模块在场但 **ZERO-CALL**。
  更结构性的一条：`langchain_community` 包本身在两场均**从未被导入**。
  **这些"从未被导入"不是"包没装"**（否则这条读数是白捡的）：候选 venv 里 `langchain-community 0.0.38`、`langchain 0.1.20`、
  `langsmith 0.1.147` 都在，五个目标模块 `importlib.util.find_spec` 逐个 FOUND（`sitemap` / `evernote` / `faiss` /
  `chains.graph_qa.cypher` / `langsmith.middleware`）⇒ 装得了、也能导入，只是这两场运行没走到。
- **外联（对 CVE-2026-26013 / CVE-2026-41488 这类 SSRF 是直接读数；`CVE-2026-41481` 没有桩，不在这一条里）**
  —— 测试场 348 次事件、206 个键，**逐键机器归类**（`b_probe_net_audit.py`，不是看打印窗口）：
  连接类目的 **312 次 127.0.0.1 + 1 次对 `test.invalid:443` 的 DNS 解析尝试 + 35 次"键里没有主机字段"**
  （那 35 次是 `ctypes.dlopen` 与 `subprocess.Popen`，**不许折进"环回"里**）。
  那唯一 1 次非环回**已归因到用例**：`tests/test_phase3.py::test_healthz_components` 走
  `main.py:340` 的 `socket.create_connection((host, port), timeout=3)` —— 是 `/healthz` 对
  `LLM_BASE_URL` 主机的设计内连通探测（假端点解析失败，**没有对应的 `socket.connect`，连接未建立**），
  不是任何 CVE 目标路径。应用路径场连接类事件 **0** 次，只有本地 DLL 加载与 torch 的 `ver`/`lscpu` CPU 探测。
  ⚠️ **但"外联普查"不等于"应用的外联全集"**——这两场是**按开关把外发面关掉之后**跑的：
  驱动设 `RERANK_ENABLED=false`、`EMBEDDING_PROVIDER=local`、两个配额总量 0、`LLM_BASE_URL` 指向保留不可解析域
  （`b_probe_run_suite.py:32-36`、`b_probe_app_paths.py:40-44`），而本机 `backend/.env` 实为 **`RERANK_ENABLED=true`**。
  于是这几条真实外呼路**一次都没进过普查**：
  ① rerank —— `retrieval.py:85-87` 的 `if not settings.rerank_enabled or not _effective_key: return None` 直接短路掉
  `retrieval.py:168` / `:184` 的 `httpx.post(rerank_base_url + "/rerank", headers={Authorization: Bearer …})`；
  ② 云端嵌入（`EMBEDDING_PROVIDER=aliyun` 那条）；③ LLM 调用本身（`llm_registry` → `ChatOpenAI` → `LLM_BASE_URL`，
  应用场根本没构造它，见上面 G2 那条）；④ MCP 侧 `mcp_server.py:45,51` 的 `httpx.Client`；
  ⑤ `/api/chat/transcribe`（`main.py:1464` 起）这类按请求才走云端的端点。
  （`manage.py:55` 的 urlopen 是环回，不构成外联。）
  ⇒ 所以这句的**准确读法**是："这两场窗口内真实发生的连接，除 `/healthz` 那次解析外全在环回"；
  它**不**支撑"这个应用不会带着凭据外发"。带凭据的外发面要单独按配置审，不在本探针射程内。
- **公告视角由脚本现生**：`python b_probe_matrix.py` 末尾的「公告视角」把登记表
  `residual-risk-review.md` 的公告去重后分成两栏 —— 26 条里本探针**有桩可答 17 条**、
  **答不上 9 条**（CVE-2024-3095 / 2024-7774 / 2025-6985 / 2026-1839 / 2026-41481 / 2026-45830 /
  2026-45833 / 2026-55443 / 2026-9856），并带闭合检查 `17 + 9 == 26 PASS`。
  **答不上的那 9 条不许被读成"已排除"**：它们要么没有运行期入口可桩（Chroma HTTP 面、text-splitters 的
  XSLT/URL splitter），要么问题本身不在调用点上（2024-7774 的包映射疑点，另立 D6 待裁）。

### G.3 本轮为这批读数付的代价（仪器自审，逐条已在代码里修掉）

1. 符号解析循环漏试单段包名 ⇒ 把 `transformers.PreTrainedModel.from_pretrained` 误报成"符号不存在"；
   是包内 grep 与解析读数打架才发现的。
2. 仪器在别的模块执行中途对 `transformers` 包做惰性 getattr ⇒ 触发循环 import，**把 `tests/test_citation.py` 的收集打爆**。
   当时 junit 只剩 1 条伪用例，闸门判"实验无效"并把读数改名 `.INVALID`（`b-probe-readings-pytest-20260929-021024.json.INVALID`）。
   修法：后置钩子只对"刚执行完的那个 owner"补桩，且每只补桩都带护栏，护栏异常进 `apply_errors`。
3. 分母读错轴：`1660/1678 tests collected` 里取了 1678 ⇒ 把一场 1660/1660 全绿的运行误判成"实验无效"
   （`...021441.json.INVALID`）。修法：闸门的轴定为 **selected**，并打印 selected/total/deselected 三个数。
4. 装桩时刻太晚（`pytest_configure`）⇒ conftest 期间的模型加载看不见，出现 **G3e=0 而同一处的 `from_pretrained`=1** 的自相矛盾。
   修法：`-p` 载入即装桩，并新增 `preloaded_app_at_install` 完整性读数 —— 非空就判本场不可用于"0 调用"结论。
5. `sentence_transformers.SentenceTransformer` 这种**模块名与类名同名**的形状解析不到 ⇒ class-init 计数器在惰性导入链里必然漏首次实例化。
   修法：解析先试"整条点号路径本身是模块"，改后两场 G3e 均 1-CALLS。
6. 别名对照原本**没有区分力**（`install()` 末尾自带一次 sweep，把遮蔽腿也补上了，读数写成"+1"）。
   修法：拆成 `install(sweep=False)` + 显式 sweep，对照变成差分 `+0 → +1`；canary 用 `import y as z` 复现改名遮蔽。
7. `compile` 审计事件（本场 9826 次）把连接类明细挤出截断窗口 ⇒ 早先"连接全是环回"是从**被截断的集合**得出的。
   修法：`compile` 单独计数不进明细，明细窗口 120 → 400。
8. 我的 runner/driver 把 `DATABASE_URL` 写成裸路径（要 `sqlite:///`）。测试场未受影响（conftest 无条件覆盖它，
   1660/1660 + 保护对象 41/41 是旁证），应用路径场第一次 upload 步骤因此报 `ArgumentError` 失败，改对形态后跑通。
9. 🚨 **审计明细把 HTTP 请求体写进了读数**（提交前扫密才发现）。`urllib.Request` 事件的 `args[1]` 就是请求体，
   测试里那几次登录带的正是 `{"username": ..., "password": ...}` ⇒ 前两份读数各含 **44 条**这种键
   （**"44" 是删除前实测的数，样本已随文件销毁、现在不可复算**；能复算的是修复后的不变量，见下与 G.6 主张）。
   处置：**两份受污染的读数已从磁盘删除**（本目录不再留任何含体样本），仪器改成只记
   URL / 方法 / 头的**键名**（CPython 签名 `(full_url, data, headers, method)`，`data` 一律不碰，
   已对着 `Python311/Lib/urllib/request.py:518` 核过轴），并新增哨兵对照 `b_probe_net_sanity.py`：
   同一个键既要"确实记下了 URL/方法/`Authorization` 键名"（证明这一层在被记），
   又要"哨兵口令与头值 0 命中"（证明进不来）—— 只断言后者会被"这条根本没记录"蒙过去。
   **教训**：外联明细天然含敏感值，"只记有没有连"这件事本身就要求脱敏，此前我没把它当敏感面。
10. **"连接全是环回"此前是靠运行器打印的前 25 条键说的**（把截断集当全集；且插入序里 `compile` 已把连接明细挤出去）。
    现在改成 `b_probe_net_audit.py` 对**全部 206 个键**逐条归类，并把"键里没有主机字段"
    （`ctypes.dlopen` / `subprocess.Popen`）**单列一档**，不许折进"环回"充数；
    归类器自带 `--selftest`：8 条合成键里 3 条**必须**被判成非环回（公网 IP、外网域名、带 URL 的命令行），
    否则"0 条非环回"只是尺子瞎了。该审计整体 **rc=1**，红因就是那 1 次 `test.invalid` 解析 ——
    **我没有为了让它绿而放宽判据**，而是去把那次解析归因清楚。
11. 复算器里曾有一条**永远不会红**的主张：`claim("历史 1650/10/18 读数只出现在 09-28 那批段落", True, "人工核对")`。
    恒真的"复算"是装饰不是证据（而且它的前提也错了：本轮同版代码跑出来**也是** 1650 passed / 10 skipped / 18 deselected）。
    已删，换成两条真会算的（从最新测试场日志解析 `passed+skipped == collected`、`deselected == 18`），
    并新增 `b_probe_claim_mutants.py`：对 11 条关键主张各造一只（共 12 只变异）"改期望值"反例，
    要求整体 rc=1 **且红的正是该钉的那一条**（红的不是该条 = 覆盖不成立）。现量 **12/12 被杀**。
12. 提交前**扫密本身也造过一次假零**：我把待提交清单存进变量再 `grep $FILES`，而清单里是仓库相对路径、
    cwd 却在证据目录 ⇒ `grep` 全线报错被我 `2>/dev/null` 吞掉，八个模式齐刷刷"hits=0"。
    改用 `git ls-files --others` + `xargs`（在仓库根跑）并**先打正向对照**（`test.invalid` 这类已知存在的假值必须命中）
    才得到真读数：32 只待提交件里 `sk-` / `LTAI` / `AKIA` / `PRIVATE KEY` / JWT 头 `eyJ….eyJ` 均 **0 命中**；
    `password`/`secret`/`api_key`/`Bearer` 的命中逐条摊开后全是驱动里的**假值常量**、脱敏检查代码本身、
    以及一个 pydantic 类型名 `Optional[SecretStr]`；`Authorization` 59 处全是**头键名**形态
    （`headers[Authorization,Content-type]`），无一处带值。
    **教训**：`2>/dev/null` + 变量传路径 = 假零的生产器；扫密这类"负向主张"必须先有一条能命中的正向对照钉方法。
13. 🚨 **外联归类器有三处静默漏判，而且三处都朝"看起来更安全"的方向漏**（独立评审提出，我逐条跑反例复现后才改）：
    IPv6 四元组 `socket|(2606:…,443,0,0)` 被吞进"无主机字段"（旧正则只吃两段）；
    `socket.getaddrinfo` 的**十进制整数 IP**（`2852065534` = 169.254.169.254，正是 SSRF 绕过的写法）被
    `host.isdigit()` 当成"那是端口"而吞掉；`os.system` 事件带 URL 也**完全不扫**（只有 `subprocess.Popen` 扫）。
    修法：改判据方向为 **non-loopback 优先**、用 `ipaddress` 认址（顺带把"十进制 127.0.0.1 仍算环回"钉住不误伤）、
    `os.system` 与 `Popen` 同扫命令行；合成反例从 8 条加到 **15 条**（9 条必须判非环回 / 4 条不许误伤 / 2 条单列），
    再加一条**数据侧对照** `--injected-selftest`：往真读数的副本里注入两类外发（并只同步 kinds/total，
    让"自洽"轴保持绿），要求整条链路 rc=1 且红的正是外发判定。
    为什么这条最重：前两处修法（第 7、10 条）我都以为自己改对了，**但自证的合成键集合本身就是按旧理解写的**，
    所以"归类器能红"这句话当时只覆盖了我想到的形状。评审的价值在于补了我没想到的形状。
14. **我把上一轮那份证据日志覆盖了**：本轮早段（03:21）无参跑 `verify-protected.py`，
    写掉的正是 09-28 报告引用的 `protected-postcommit-check.log`。内容与复跑结果一致（两份都 41/41、`diff` 为空，
    所以**没有丢结论**），但"09-28 那份未被覆盖"这句话此前是错的，已在 §12/计划书/README 三处改写。
    随后给脚本加了可选 `argv[1]` 输出路径（本轮复验落 `protected-probe-rerun-check.log`），
    就是为了不再发生第三次。
15. **判定表把"没测到"和"测到 0 次"混打印**：`b_probe_matrix.py` 原来每组只打一个"判定集合"，
    `['NEVER-IMPORTED', 'ZERO-CALL']` 读起来像"这组都答了、都是 0"。改成三档分栏
    （测到有调用 / 测到 0 次 / 未测）。
16. **两条名实不符的主张**：`claim("qa 步骤跑通且未调用生成模型", "retrieved" in qa)` 实际只断言"字段存在"
    （既没看 `failures` 也没看生成），现拆成两条真判据；文档残留检查里的 `if d.is_file()` 会让**改了名的文档整条检查空过**，
    现补一条"N 份文档全部在位"的主张。另把"总桩数=22"改成闭合式 `22 == 四组之和`。主张数 58 → **61**。
17. **三处 over-claim 被评审抓出后收回并改写**（都是我把"某场的读数"写成了"应用的事实"）：
    ① "应用路径场 `langchain_openai.chat_models.base` 从未被导入" —— 那是**驱动没 import `llm_registry`**
    （`b_probe_app_paths.py:71-73,89`），真实 `/api/chat` 一定会加载它 ⇒ 改判"该场对 G2 是未测"；
    ② "`trust_remote_code` 取值 False" 被推广到四只桩 —— 只有 `G3a/G3b` 把它当实参传（读数 `['False']`），
    `G3d/G3e` 的实参里**没这个键**（读数 `[]`）⇒ 限定到两只；
    ③ "外联普查"没披露**被开关关掉的那几条带凭据的外呼**（rerank 的 `httpx.post`、云端嵌入、LLM 调用本身；
    本机 `.env` 里 `RERANK_ENABLED=true`）⇒ 见 G.2 的 ⚠️ 段。

### G.4 这批读数**不**证明什么（边界，别让它超出证据）

- **测试场里生成链是替身**：`tests/_sse_harness.py:207` 用 `monkeypatch.setattr(main, "make_chain", lambda llm: _FakeChain(...))`
  把链工厂整个换掉（该文件 :40 定义 `_FakeChain`）。所以"SSE/流式那些用例 0 调用"里，有一部分是**替身没去调真链**，
  不是真链被证明不调。⇒ 本节所有"运行时 0 调用"都要读成"这两个窗口内 0 调用"，跨窗口的通路（真实生成链内部）不在射程内。
- **子进程与第二解释器完全在外**：仪器只桩在**本进程**的 `sys.modules` 上。两场读数里就有 7 类 / 22 次
  `subprocess.Popen`（例如 `python.exe -B …`、`python.exe scripts/…`），那些子进程内部发生了什么本探针一概看不见。
- **类内遮蔽未扫**：别名补钉只扫**模块字典**（`b_runtime_probe.py` 的 `sweep_aliases` 自述），
  类的 `mappingproxy`、实例属性、闭包捕获与 `functools.partial` 里绑走的原函数引用都不会被改指计数器。
- **反序列化原语没有桩**：`torch.load` / `pickle.loads` / `safetensors` 只在 `EXTRA_WATCH` 里记"有没有被导入"，没有计数；
  G3 那 1 次模型加载**内部真正发生的解序列化**没有读数。同样，`langchain_core.load.dumpd` 与
  `PromptTemplate.__init__`（直接构造，不经 `from_template`）也**不在 22 只桩上** ⇒ G1 的 ZERO-CALL 只覆盖我桩住的那些入口。
- **脱敏不变量只钉了 `urllib.Request` 一类键**：判据是键形 + 字面量 `password`/`|{`。
  `subprocess.Popen` 的命令行前 3 段各 90 字符是**原样入读数**的，URL 的查询串/userinfo 若带 token 也会照录。
  本轮实扫 11 份读数除 `kw=…token`（这是**键名**）外无敏感命中，但"URL 里带凭据仍在面上"这条要如实说出。
- **"离线"不是环境结构保证的，是事后读数证明的**：驱动确实设了 `HF_HUB_OFFLINE=1`（`rag_chain.py:15` 也只是 `setdefault`），
  但 `knowledge_base.py:5` 是**无条件** `os.environ["HF_HUB_OFFLINE"] = "0"` 并顺手 `setdefault("HF_ENDPOINT", "hf-mirror.com")`
  —— 只要有进程 import 它，离线前提就地失效。本轮两场都**没有**导入它（`tests/` 与 `scripts/` 里那些名字是注释与文档串，
  应用路径驱动只 import `rag_chain`/`retrieval`/`knowledge_service`），且读数里 `hf-mirror`/`huggingface.co` **0 痕迹**、
  非环回只有 `test.invalid` 那 1 次 ⇒ 模型确实取自缓存。但这条要如实写成"**将来有人把 `knowledge_base` 引进同一进程，
  本探针的离线前提就没了**"，不是"环境锁死了离线"。
- **探针只覆盖这两个执行窗口（1660 条非 slow 测试 + 两条直调路径）在该隔离环境下的事实**；不是"不可达证明"，
  也不覆盖将来新增的入口。18 条 slow 用例未跑。
- 未调用真实 rerank 与生成模型（凭据待轮换），LLM 端点指向不可用地址，因此生成侧之后的那段只有 mock 测试覆盖。
- 应用路径场用**空副本集合**，`retrieved=0` 是构造使然，不是检索质量结论。
- **应用有一个设计内的主动外联点**：`/healthz` 会拿 `settings.llm_base_url` 的主机做 TCP 连通探测
  （`backend/main.py:337-342`，`socket.create_connection(..., timeout=3)`，软检查）。
  ⇒ 本节的"运行期 0 调用 / 连接基本全环回"是**对被桩的 22 个目标与本场连接事件**成立，
  **不等于**"这个应用不会 outbound"。接受风险时请把这一条算进暴露面。
- **CVE-2024-7774 的包映射疑点不在这把尺子的射程内**（那是公告与包名映射的核对问题，不是调用点问题），仍然待办。
- `pip-audit` 仍是 47 条 / 8 包（解析集）与 57 条 / 10 包（实装集）的**红**读数；本探针**不减少漏洞条数**，只升级可达性证据等级。

### G.5 本目录文件数：只给命令，不抄数（抄了就过期）

```bash
cd dispatch-output/local-candidate-closeout-20260928
find . -maxdepth 1 -type f | wc -l                       # 总文件数
find . -maxdepth 1 -type f -name '*.log' | wc -l          # 按仓规不入库的
find . -maxdepth 1 -type f ! -name '*.log' | wc -l        # 可入库的
git ls-files . | wc -l                                    # 实际已入库
```

`.log` 全仓被 `.gitignore:45` 忽略，所以"可入库件数"与"目录件数"永远不等，这不是丢件。
上文 09-28 那节写的"62 个文件 / 26 个非 `.log` 入库"属于**当时的快照**，不要拿来对现在的目录。

### G.6 复跑一致性与主张复算（这两件事是本轮读数的承重墙）

- **同一份入库代码复跑两场，逐条零差异**：`b-probe-readings-pytest-20260929-103147.json` 与
  `...-103511.json` 在**判定 / 计数 / 干跑数 / 调用方集合 / 实参摘要**五个轴上 22 只桩全部相同，
  `collected` 1660、`pytest_exitstatus` 0、`compile` 9826、net **206 类 / 348 次**、在场模块 29、
  别名补钉 4 项（`G1a/G1b/G1c/G1g`）、`preloaded_app_at_install` 空 也逐一相同。
  比对**已脚本化**：`python b_probe_pair_check.py <A> <B>`（junit 用例数从各场 `junit.xml` 现算，不抄打印）。
  上一轮这里写的是一次性 `python -c`，"分析器不入库 = 数字不可核"，故本轮落成文件。
  ⚠️ 上一轮引用的那对读数（`023538` / `030644`）**已因含 HTTP 请求体被从磁盘删除**（见 G.3 第 9 条），
  不要再去找它们；改后修复版的第一对是 `033015` / `033335`（判定与计数与现行版逐条相同，只是代码风格随后又被清了一遍）。
- **主张复算器**：`python b_probe_claim_check.py` → **61 条**主张逐条判 PASS/FAIL，现量 **61/61 通过**
  （结果落 `b-probe-claim-check.json`）。它把"61 条主张覆盖到的数字"重新对着**入库读数**算一遍（README 散文里未被主张覆盖的数字仍会漂移，见 G.6 末尾）：组内桩数、各目标调用次数、
  调用方归属、模型名集合、`trust_remote_code` 取值、缺席模块、外联分轴与**键形状/脱敏不变量**、
  两腿复跑一致性、net 计数自洽、读数出处代次，以及"文档里不该残留已被推翻的说法"。
- **复算器自己红过三次，三次都是它自己的问题，不是主张错了**：
  ① 取模型名时没截掉 `arg_samples` 里的 ` kw=` 尾巴 ⇒ 误报"模型名不唯一"；
  ② `glob` 返回字符串却当 `Path` 用 ⇒ 直接 `AttributeError`；
  ③ 本轮新增的变异对照第一版把 mutant 放进临时目录跑 ⇒ 12 只全部 rc=2「缺入库读数」，
     看起来像"变异都被杀掉"，其实是**变异根本没跑**（复算器按 `__file__` 的父目录找读数）。
     改成就地生成 + finally 删除，并在跑完后**复跑正算子取回** canonical JSON（否则留在目录里的是某只变异的红读数）。
  **记下来是因为这正是"工具的 0 不可信"的反面用法**：尺子会红，红的要先归因到尺子还是主张。
- **复算器能不能红，另外单独证了一次（但要看清它证到哪一步）**：`python b_probe_claim_mutants.py` 对 **11 条**
  关键主张各造一只"把期望值改得与实测不符"的变异（共 12 只；`urllib.Request` 键形那对有两只），
  要求整体 rc=1 **且红的正是该钉的那一条**（红别的条目算覆盖不成立）。现量 **12/12 被杀**
  （`b-probe-claim-mutants.log` / `-mutants.json`）。必要性：本轮删掉的那条 `claim(..., True, "人工核对")`
  就是恒真主张混在 58 条里的实例，只报"61/61 通过"不构成证据。
  ⚠️ **这只证明了"主张不是恒真话、它确实随实测值变"，没证明"主张测的是正确的谓词"**——
  评审原话的意思是：如果外发被归类器吞掉（第 13 条那种缺陷），这 12 只变异一只都不会红。
  补的那一侧是**数据侧**对照：`b_probe_net_audit.py --injected-selftest` 往真读数副本注入两类外发，
  要求整链路判红且红的正是外发判定（见 G.1 与 G.3 第 13 条）。
- **读数的出处代次已核，且这条现在是复算器的一条主张**：本轮被引用的读数
  （pytest `103147` + `103511`、app `103841`、selfcheck `b-probe-selfcheck.json`）
  **mtime 全部晚于** `b_runtime_probe.py` / `b_probe_run_suite.py` / `b_probe_app_paths.py` 的最后一次编辑
  （那次编辑是 ruff 对 `E,F,W,I,UP,B` 规则集的风格清理，含 `io.open`→`open` 与 `typing.List`→`list`；
  改完重跑自检 19/22 + 两腿 + 应用场，才是上面这些数）。
  核对命令：`ls -l --time-style=+%H:%M:%S b_runtime_probe.py b-probe-readings-*.json`。
- **本目录脚本的 lint 口径**（写清楚，免得下一个人以为整目录都绿）：本轮新增的 12 只 `b_*.py` 加 `b-probe-survey.py`
  与改过的 `verify-protected.py` 共 **14 只**，按仓库 `backend/pyproject.toml` 的规则集
  （`--select E,F,W,I,UP,B --ignore E501,B008 --line-length 120 --target-version py311 --isolated`）
  `ruff check` 与 `ruff format --check` **全 rc=0**。
  09-28 那批脚本（`verify_corpus.py`、`watch-ref-write.py`、`summarize_audit.py`）**本轮不动**：
  `watch-ref-write.py` 有 1 条 `UP009`、`verify_corpus.py` 与 `watch-ref-write.py` 未过 formatter。
  不顺手清的原因不是"没必要"，而是**它们产出的读数是上一轮已入库引用的证据**，
  本轮没有复跑它们，把风格改动混进来会让"数字出自哪版代码"重新变糊。
  注：本目录**不在 CI 的 lint 范围内**（CI 只 lint `backend/` 与 `dispatch-output/agent-quality-20260911`），
  所以这两条红不会让 CI 变红。



**本目录的入库边界（`.gitignore:45` 全仓忽略 `*.log`）**：口径只认 G.5 那三条命令，每次复跑都会变，
下面这组是 **2026-09-29 本轮收尾时的一次快照**（过期了以上面命令现量）：
总 120 只 / `.log` 60 只 / 非 `.log` 60 只 —— 非 `.log` 里含 2 只 `*.INVALID`（被闸门判废的读数，
**留盘作仪器缺陷证据但不入库**），所以本轮实际可提交 58 只；本轮之前已入库 26 只，其余 **32 只**随本节所在提交进入。
`.log` 与 `*.INVALID` 都不入库、**留在磁盘上供人工查看**，读数已摘录进本文件与报告；关键日志路径：
`postcommit-gates.log`（提交后 1–9 步）、`postcommit-pip-audit-retry.log`（第 9 步加大超时的重试读数）、
`protected-postcommit-check.log`（09-28 的 41 个保护对象复验）、
`protected-probe-rerun-check.log`（09-29 B 档各场跑完后的第二次复验，同样 41/41）、
`backend-full-tests-final-v2.log`（提交前全量）、
`candidate-versions-final.log`、`pip-check-final.log`、`mypy-final.log`、`ruff-final.log`、`ruff-format-final.log`、
`fastapi-contract-tests.log`、`pdf-green-existing-runtime.log`/`pdf-red-existing-runtime.log`（修复前后对照）、
`corpus-existing-runtime.log`/`corpus-restored-existing-runtime.log`（语料副本）、`precommit-targeted.log`（提交前定向复跑）。
