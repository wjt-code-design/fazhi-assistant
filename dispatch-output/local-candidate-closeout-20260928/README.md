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
- **决定性时序证据（2026-09-29 实测，脚本 `watch_ref.py`，10ms 级轮询）**：git 其实**写成功了** ——
  `mkdir refs/heads/zzy` → 建 `one.lock` → 写 reflog → **`.lock` 改名为 `one`（ref 出现）** → 之后
  **113–144 ms（三次：122.5 / 113 / 124.5 ms）** 该 ref 与其父目录被**另一个进程**删除。
  ⇒ **推翻"git 写失败"的假设，改判为"外部进程在 git 提交 ref 后约 120 ms 删除它"**。
  旁证：手工 `printf >` 写的同名 ref **可长期存活**（已复核 ≥25 分钟）；顶层 ref 不受影响。
- 应对（本轮实际使用，已验证）：每次提交后按 reflog 回填引用 ——
  `mkdir -p .git/refs/heads/codex && printf '%s\n' "$(tail -n 1 .git/logs/refs/heads/codex/local-candidate-closeout | awk '{print $2}')" > .git/refs/heads/codex/local-candidate-closeout`
  然后核对 `git worktree list` 与 `git status`。
- 未定因；排查期建的对照引用与临时仓库已全部清除。**接手者动该分支前必须先复核引用仍在。**

**未跟踪产物归属**：本轮只暂存本证据目录与本计划；主工作区未跟踪 34107 个（`dispatch-output` 占 33938），未 `git add -A`；
其余 worktree 只登记不动。

**本目录的入库边界（`.gitignore:45` 全仓忽略 `*.log`）**：本目录 59 个文件中，**23 个非 `.log` 文件入库**
（README、各 audit/resolve/install 的 `.json`、`protected-before.json`、`requirements-web-candidate.txt`、`remote-ci.yml`、
`remote-tree-diff.txt`、`residual-risk-review.md`、两份回执、`summarize_audit.py`、`verify_corpus.py`）。
36 个 `.log` 按仓规不入库、**留在磁盘上供人工查看**，读数已摘录进本文件与报告；关键日志路径：
`postcommit-gates.log`（提交后 1–9 步）、`postcommit-pip-audit-retry.log`（第 9 步加大超时的重试读数）、
`protected-postcommit-check.log`（41 个保护对象复验）、`backend-full-tests-final-v2.log`（提交前全量）、
`candidate-versions-final.log`、`pip-check-final.log`、`mypy-final.log`、`ruff-final.log`、`ruff-format-final.log`、
`fastapi-contract-tests.log`、`pdf-green-existing-runtime.log`/`pdf-red-existing-runtime.log`（修复前后对照）、
`corpus-existing-runtime.log`/`corpus-restored-existing-runtime.log`（语料副本）、`precommit-targeted.log`（提交前定向复跑）。
