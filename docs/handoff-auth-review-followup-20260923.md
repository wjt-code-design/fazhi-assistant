# 工作交接：AUTH-2 / AUTH-3 后续修复

> **2026-09-24 状态：本文的"接手后优先核验的正确性缺口"四项已全部收口，勿重复执行。**
> 缺口 1（考试检索不带 cutoff）、缺口 2（合同 cutoff 与 `blocks` 数据流）、缺口 3（Agent 恢复分支静默丢弃日期）、
> 缺口 4（其余出口：共享缓存/QA 直返/**受控沉淀**/检索缓存键）已实现并由红→绿测试锁定；
> 本文第 72 行那次"被中断、没有最终结果"的宽套件已补跑为 **81 passed / 2 skipped / exit 0**（开工前基线）。
>
> **2026-09-24 二轮（双轴自评 code review + systematic debugging）**另修 4 项：Agent 工具链
> `tools/contract.py` 同样漏传 cutoff（与缺口1/2 同一失效模式，**本文未列出该 caller**）；
> `body.law_as_of` 缺 `case_domain` 那种防旁路扫源守卫；`FastPathDependencies` 曾被放宽成
> `Callable[…]`（＝在本次要护的接缝上取消 mypy 覆盖）；`_resume_bootstrap` 日期形参默认 `None` 属 fail-open。
> 另：本文与报告先前所述"AUTH-2 有 AST 哨兵"**不实**，已在报告勘误。
>
> **2026-09-24 终态重跑（22 个改动文件宿主↔容器 md5 逐字节一致后的同一批字节）**：定向 AUTH 套件
> **235 passed / 10 skipped / exit 0**（15 文件，含 `test_tool_gateway.py`/`test_agent_gate.py`），
> 全量 **1407 passed / 12 failed / 25 skipped / exit 1**（12 项均为镜像缺件，见报告归因），
> `ruff check` 通过、`mypy .` 73 文件零问题。退出码经重定向文件取得（不走 `| tail`，那会报出假 exit 0）。
>
> 当前结论、测试证据与残留限制以 [`code-review-report-02e3851-20260918.md`](./code-review-report-02e3851-20260918.md)
> 的「2026-09-23 当前快照复核」节为准。**变更仍未提交、仍未部署**（授权仅到本地代码与测试）。

更新时间：2026-09-23（Asia/Shanghai）  

项目：`C:\Users\33393\Desktop\ai-legal-helper`  
交接目标：让接手助手从当前工作树继续，不重做前置调查，也不误把未完成验证当作完成。

## 当前任务从哪里来

本工作承接 Codex 会话 `codex://threads/01a0a9c7-c5e8-7731-ad1b-2f120a2e89c5` 的后续任务。前序上下文涉及项目 Git 损坏检查与修复；当前继续处理的是权限审查报告中的两个后端问题，而不是重新执行 Git 修复或部署。

审查依据及历史结论见 [`docs/code-review-report-02e3851-20260918.md`](./code-review-report-02e3851-20260918.md)，重点为 AUTH-2、AUTH-3 和报告末尾的状态说明。报告当前仍保留“AUTH-2 / AUTH-3 未解决”的旧结论；本次代码改动尚未通过最终验证，因此不能仅凭工作树变化就把报告标成已修复。（**此段为 09-23 写作时的状态，已被本文顶部横幅与报告「2026-09-23 当前快照复核」节取代**：四项缺口已收口、报告已按实测更新结论，但仍**未提交、未部署**。）

## 用户已确认的产品决策与边界

- `law_as_of` 是普通已认证用户可用的公开历史查询条件，不是管理员专属，也不能绕过证据有效性校验。
- 服务端默认允许此条件；若部署配置明确关闭，客户端传入日期时必须明确返回 HTTP 503 和可理解的提示，不能静默忽略。
- 历史查询需要最小结构化审计：记录用户、会话和所选日期；不记录原始法律问题、案情或其他用户输入。
- `case_domain` 是评测/可信通道控制量，默认关闭；前序工作已处理，不要为了本任务重复改动或放宽。
- 用户尚未选择服务器，已明确要求**暂不部署**。不得部署、迁移、发布、重启线上服务、写服务器配置或选择服务器。当前授权仅涵盖本地代码与测试。
- 当前变更未提交。除非用户另行明确授权，不暂存或提交；不得用 `git reset --hard`、`git clean`、`git checkout --` 等方式清理工作树，也不要覆盖其他未提交文件。

## 工作树状态

- 分支：`master`
- 本文编写时 HEAD：`b7d96f5`。以下状态是 2026-09-23 的快照；接手时先重新查看 `git status` 和 `git rev-parse --short HEAD`。若 HEAD 已变化，不要因此重置、切换或覆盖工作树。
- 本次 AUTH 修复涉及的 12 个后端文件均为未提交修改：
  - `backend/main.py`
  - `backend/observability.py`
  - `backend/request_bootstrap.py`
  - `backend/schemas.py`
  - `backend/settings.py`
  - `backend/tests/_sse_harness.py`
  - `backend/tests/test_client_law_as_of_gate.py`
  - `backend/tests/test_fast_path_law_version_gate.py`
  - `backend/tests/test_r1ob.py`
  - `backend/tests/test_request_bootstrap.py`
  - `backend/tests/test_stream_exit_law_version_gate.py`
  - `backend/tools/legal_retrieval.py`
- 当前工作树还有大量不在本次 12 文件清单中的修改/未跟踪文件（包括 `dispatch-output/`、`docs/code-review-report-02e3851-20260918.md`、`docs/superpowers/plans/2026-09-22-git-repair-execution-runbook.md`、`.qoder/`、`outputs/` 等）。这些文件的来源和归属未逐项确认；保留原样，逐项核对后再动，禁止批量清理、重置或覆盖。
- 本交接文档 `docs/handoff-auth-review-followup-20260923.md` 已新增，本文编写时为未跟踪文件。
- `git diff --check` 此前未发现空白错误；Git 输出的只是工作树 LF/CRLF 转换提示。

## 已有实现（仍需审查，不代表已验收）

### AUTH-2：历史查询契约

- `backend/settings.py` 将 `allow_client_law_as_of` 默认值改为 `true`。
- `backend/main.py` 在配置显式关闭且请求携带日期时返回 503；正常请求把显式日期传入 bootstrap / 快车道检索。历史查询进入共享缓存判断时不可缓存。
- bootstrap 阶段为显式历史查询记录 `historical_law_query`，字段是用户 ID、会话 ID、日期，不含用户问题原文。
- 普通问答的 `_build_messages` 会标注显式历史法律基准日；不要把这点外推到合同或 Agent 恢复路径，后两者列在下方待核验项。
- `backend/request_bootstrap.py` 对显式日期的普通快车道检索传 cutoff，禁用当前 QA 直返，并对拼装后的证据按时间有效性再过滤。
- `backend/schemas.py` 与相关注释已改为公开历史查询语义。

### AUTH-3：敏感争点日志

- `backend/tools/legal_retrieval.py` 不再把原始 `query` 写入 `dept_filter_removed` 日志，改写入 SHA-256、长度、领域和剔除数量。
- `backend/observability.py` 的结构化字段白名单加入 `query_sha256` / `query_len`，移除原始 `query` 字段。
- 复核时还应评估未加密钥的 SHA-256 是否会被猜测或用于跨请求关联。它比记录原文少暴露，但不能等同匿名化；若威胁模型不接受，应由测试驱动改用合适的 keyed digest 或不记录摘要。

对应测试已覆盖默认开关、关闭时 503、日期传入检索、历史请求不共享缓存、历史查询审计字段、历史快车道证据过滤/提示标记，以及日志不包含原始问题。

## 验证证据与未完成项

测试环境使用隔离容器 `codex-auth-review-test`，镜像为 `ai-legal-helper-backend:audit-current`。2026-09-23 复核时容器状态为 `running`，没有挂载卷，也没有发布端口；它是测试容器，不是已启动的 API 服务。此前健康检查显示 `unhealthy`，原因是镜像健康检查期望应用进程，而测试容器没有启动应用。宿主机 Python venv 前序检查已知损坏，不能假设本机 venv 可用。接手后应先重新检查容器状态及文件同步情况。

已观察到的测试结果：

- 一次针对 AUTH-2 的定向测试在实现后通过：`8 passed, 11 warnings`。容器内命令：`docker exec -w /app codex-auth-review-test python -m pytest tests/test_client_law_as_of_gate.py tests/test_request_bootstrap.py::test_historical_fast_path_uses_date_for_all_evidence_and_skips_current_qa -q -p no:cacheprovider`。
- AUTH-3 日志脱敏和白名单测试通过：`3 passed, 2 warnings`。容器内命令：`docker exec -w /app codex-auth-review-test python -m pytest tests/test_r1ob.py::TestLegalRetrievalFiltering::test_filter_log_omits_raw_case_text tests/test_log_field_whitelist.py -q -p no:cacheprovider`。
- 加入 prompt 日期标记断言后，该单测通过：`1 passed, 2 warnings`。容器内命令：`docker exec -w /app codex-auth-review-test python -m pytest tests/test_request_bootstrap.py::test_historical_fast_path_uses_date_for_all_evidence_and_skips_current_qa -q -p no:cacheprovider`。
- 较早的相邻套件曾得到 `78 passed, 2 skipped, 3 failed`。其中两项流式退出用例仍假定显式历史日期可写共享缓存；按“历史请求不进共享缓存”的契约改成无显式日期。第三项 caplog 捕获方式不适配已配置 logger，已改为专用 handler。
- 修正以上三项后，第二次宽套件运行期间被中断，**没有最终结果**。中断前将后续更新的 `backend/tests/test_r1ob.py` 与 `backend/tests/test_stream_exit_law_version_gate.py` 复制到容器；这不等于其余源文件/测试都与当前工作树一致。重跑前逐一核对下面宽套件涉及的所有实现文件和测试文件，并同步任何差异。

可复现的宽套件命令（在同步当前源文件和测试文件到容器后执行）：

```powershell
docker exec -w /app codex-auth-review-test python -m pytest `
  tests/test_client_law_as_of_gate.py `
  tests/test_client_case_domain_gate.py `
  tests/test_request_bootstrap.py `
  tests/test_fast_path_law_version_gate.py `
  tests/test_stream_exit_law_version_gate.py `
  tests/test_r1ob.py `
  tests/test_log_field_whitelist.py `
  -q -p no:cacheprovider
```

不要只复用容器中已有文件；容器没有宿主机 bind mount。用 `docker cp <本地文件> codex-auth-review-test:/app/<对应相对路径>` 更新每个改动文件，或通过其他可核验方式确认其内容一致。

### 接手后优先核验的正确性缺口

目前实现对普通法律问答路径做了日期 cutoff 和证据过滤，但不能据此宣称所有请求模式都完整支持历史查询。接手助手应先检查并加测试，尤其是：

1. 考试检索分支使用 `retrieve_exam`，依赖接口目前没有 cutoff 参数；末尾过滤可以剔除新证据，却可能漏掉历史有效证据。
2. 合同模式使用 `build_contract_data`。目前 `prepare_fast_path` 最后会重新过滤局部变量 `docs`，但 `contract_data["docs"]` 和由此生成的 `contract_data["blocks"]` 并未随之更新；`_contract_messages` 直接读取 blocks。此外合同消息组装路径是否标注基准日也需确认。先用测试验证这一具体数据流，再决定按 cutoff 构建合同证据，或在合同模式明确拒绝历史日期。
3. `chat()` 的 Agent 恢复分支在计算 `_client_law_as_of(body)` 后直接走 run 恢复逻辑，不经过普通请求 bootstrap；目前看不到本次 body 日期被用于恢复处理或审计。核对 AgentRun 已保存的日期契约，并明确拒绝不兼容组合或保证日期一致，不能静默接受后丢弃。
4. 检查 QA 直返、补充检索、场景检索及所有生成/缓存出口是否统一尊重显式日期。若某路径无法可靠支持，先定最小安全行为（例如明确 4xx 拒绝该组合），并由测试锁定，不要伪称支持。

这是尚未完成的范围核验，不是已确认的线上漏洞。选择“支持所有模式”还是“对暂不支持的模式显式拒绝”时，保持公开产品契约可见、fail-closed，并避免静默退回当前日期。

## 下一步执行顺序

1. 先查看 12 个目标文件的 `git diff`，确认没有误伤其他改动；特别核对 `main.py` 的各请求出口及 `request_bootstrap.py` 的全部检索分支。
2. 解决上节列出的考试、合同、Agent 恢复等日期语义问题；每个新修正先增加能在旧行为下失败的测试，再实现。
3. 将最终工作树中的源文件和测试同步至隔离容器，重跑定向及上述宽套件；记录完整退出码、通过/跳过/失败数和警告，不把中断或部分结果写成通过。
4. 运行合适的静态检查及 `git diff --check`。若失败，分析失败原因再决定重试；同一命令最多原样重试一次。
5. 在所有必要验证通过后，更新权限审查报告里 AUTH-2 / AUTH-3 的当前结论，区分“本地代码实现/测试证据”与“尚未部署”，并记录未覆盖路径和限制。
6. 最终向用户报告变更、测试证据、残余限制和未部署状态。等待用户选择服务器并明确授权后，才讨论部署。
