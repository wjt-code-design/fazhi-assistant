# 审查问题修复与后续本地准备执行书

> **For agentic workers:** 使用 `executing-plans` 逐项执行；技能不可用时直接遵守本书。默认一个助手串行负责，不自行派发子助手或新建其他会话。用 checkbox 跟踪任务，代码先 RED 后 GREEN，交付前自审。本书为完整任务入口，不要求读取原聊天或遍历全部历史计划。

**编制日期：** 2026-10-06，Asia/Shanghai。  
**Goal：** 关闭最新候选的四项独立审查问题，重新取得同源本地验收证据，再完成下一阶段的本地整合与发布准备材料。  
**Architecture：** 保留现有 FastAPI/Starlette、聊天流、SQLite、LLMRegistry 和并发门。取消补偿在本请求的 response/route 所有权边界补齐；UI 结论来自实际页面观察；清单和扫描覆盖交付最终字节。不新增取消平台、数据库字段或测试框架。  
**Tech Stack：** 现有 Python 3.11、anyio/asyncio、SQLAlchemy、已安装 LangChain/OpenAI SDK；React/Next.js/Vitest；固定离线 BGE CPU、公开法规副本、回环 LLM 替身。不得安装或升级依赖。

## 0. 执行边界：当前完善 + 后续准备，不含发布动作

**先执行 A—E：** 新候选保护、四项修复、同候选复验。  
**本书也执行 G：** 后续阶段的只读核对和本地准备材料，在E之后、F封口之前完成。它不是“只列建议”，但不授权把代码合入主仓或访问真实业务数据。  
**F/H：** 最终交付字节封口与汇总。  
**I：** 需要用户另行批准的动作，本书不执行。

### Global Constraints（全局约束）

必须遵守：

- 主仓产品、旧候选及其源码/工具/证据、真实配置、原始数据库/语料、原模型缓存、共享 venv 全部只读。只修改新建的独立文件候选；执行中不回填本执行书。
- 不创建 Git 分支/worktree，不暂存、提交、合并、推送、PR、触发远端 CI，不部署，不购买或选择服务器。主仓当前未提交修改属于用户，不能顺手整理进提交。
- 不调用真实 LLM、Agent 或 rerank；不加载真实 `.env` 到产品或实验环境。此前真实 rerank 有调用许可和历史结果，本书不据此扩展当前实验；不再把“未配置 key”当成未经核对的阻塞项。
- 动态实验仅使用新公开库副本、离线固定 BGE、回环替身、合成账户。服务只监听 `127.0.0.1`；用户原有 `http://127.0.0.1:3021/` 页面和服务不得操作。
- 只允许批准的扫描器在其进程内读取指定凭据作比对；禁止输出真实值、指纹、命中片段、带认证信息的 URL，不擅自轮换凭据。
- 不改认证、法律日期/版本门、模型路由/配额、摘要阈值、取消占位文案、界面布局；不为绿色使用强制 GC、`os._exit`、吞异常、跳过断言、删除消息、加大整体超时或盲目升版。
- 每轮独占新 evidence/runtime 目录，拒绝覆盖历史文件。失败先分析，完全相同命令最多重试一次；同一 bug 经三次修订仍不通过，停止修改并质疑设计。
- 遇到输入不符、并行写入冲突、越界或需要扩大范围，停止受影响任务，用简短中文纯文本对齐。没有浏览器能力就写 UI `UNVERIFIED`，不能用 HTTP/hook 测试替代页面验收。
- 简化优先：已有代码 → 标准库/平台 → 已装依赖 → 最小局部实现。不得削减数据保护、输入校验、错误处理和明确验收要求。

**本书不承诺直接“上线就绪”。** 当前限定技术门、后续准备完成、发布条件满足是三个不同结论。

## 1. 固定路径、输入与当前事实

全文别名仅在此定义；所有相对路径都按表中根目录展开。

| 别名 | 完整绝对路径 / 用途 |
| --- | --- |
| REPO | `C:/Users/33393/Desktop/ai-legal-helper`，主仓，只读 |
| BASE | `C:/Users/33393/Desktop/fazhi-local-closeout-20261006`，最新助手交付，只读 |
| NEWROOT | `C:/Users/33393/Desktop/fazhi-closeout-reviewfix-20261006`，本书执行目录 |
| PY | `C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe`，只执行 |
| NODE | `C:/Program Files/nodejs/node.exe` |
| PUBLIC_SEED | `BASE/runtime/public-kb`，只读物理复制 |
| MODEL_SEED | `BASE/runtime/hf-cache`，只读物理复制 |
| PROTECTION_HELPER | `C:/Users/33393/Desktop/fazhi-next-acceptance-review-20261004-a43ad25a98f04fb597e5b1aabe270b9a/verify_evidence.py` |
| SCAN_PATTERN_HELPER | `C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/source/dispatch-output/local-candidate-closeout-20260928/secret_shape_scan.py` |

编制时 NEWROOT 不存在。执行时若已存在，改用 `fazhi-closeout-reviewfix-20261006-<实际时间戳>`，在 `NEWROOT/reports/progress.md` 写明完整新路径；不得合并、删除或重用旧目录。

### 1.1 已核对的起点，不是新修复结果

- 主仓 HEAD：`902e2d161e67100ed6d267a08c393538a0abe109`，暂存区为空。六个既有跟踪修改：
  - `docs/process-archive/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md`
  - `frontend/app/admin/sections/KnowledgeSection.tsx`
  - `frontend/app/admin/sections/UploadSection.tsx`
  - `frontend/app/chat/page.tsx`
  - `frontend/app/globals.css`
  - `frontend/components/chat/InputBar.tsx`
- BASE/source 不是 Git 仓库。编制时按 `BASE/evidence/final-source-manifest.json` 验证 **364 个文件全部匹配**；包含已有两个新增后端测试。不得再把旧 362 数量硬套在本候选上。
- 已有 SDK 生命周期修复和并发取消修复保留。独立审查曾新跑生命周期 9、边界 8、取消机制 28、工具 29 项，共 74 项通过，但仍发现下表问题。**已有通过数不替代本书的新验收。**
- 历史 control05/06 支持 SDK 收尾修复：前者未修复产品自然退出 `0xC0000005`，后者当时产品自然 exit0、lifespan 后 sync/async SDK 均关闭。它们只覆盖当时来源；本书改变 main 后必须再验最终产品。
- 历史 round04 的服务/存储证据存在，但 UI 的部分结论为写死字段；不能据其重新宣称“六例已独立验收”。

起点 SHA-256（执行 A 时复核；工具以实际字节为准，不信旧 tool manifest）：

| BASE 内文件 | SHA-256 |
| --- | --- |
| `evidence/final-source-manifest.json` | `6ebd2c913d20b01bf00f09d878ab8d1d86f41e18c95e7a73729e69eedf6b2fdd` |
| `source/backend/main.py` | `5b0e620f87dde439dd4dcaa2a44cce14e6066e423386320b82911b8858d3aa3b` |
| `source/backend/tests/test_cancel_boundaries.py` | `036d40ae4c39c09d3b4a04a9e9d9d8387446ba2c738af44b48f8cbe8a395a1b4` |
| `write_ui_evidence.py` | `f5ce9b934d469f370c91eeb3f65963b69723bb0612bfdccb851c1540344f521f` |
| `freeze_final.py` | `7c04b18aebf8fff622e3fe0081f5bb2eeeb807831cbec11456d5a975e83b306d` |

### 1.2 本书要关闭的四项发现

| 编号 | 已确认问题与定位 | 必须得到的结果 |
| --- | --- | --- |
| R1 / P1 | `BASE/source/backend/main.py` 的 `_ChatStreamingResponse.__call__`（编制时1667附近）：`http.response.start` 发送阻塞时断开，body 尚未进入；关闭未启动 async generator 不执行其 finally。隔离 SQLite 复现只剩 user、没有 assistant、provider 调用0 | response/route 边界补偿，无 provider 的取消也恰一个占位；正常/已启动流不重复补偿 |
| R2 / P2 | `test_cancel_boundaries.py` 的 `test_d1_grant_and_cancel_same_window_never_overruns_or_double_releases`（222附近）：逐个 acquire 后立即 release，只证明至少1个名额，不能证明2个全恢复 | 同时持有全部容量、额外名额不可获取；故意丢1个名额的负控确实失败 |
| R3 / P2 | `BASE/write_ui_evidence.py` 中 `partial_ui_observed/input_restored/same_browser_operation_start_stop/history_placeholder_checked` 写死；缺少可独立复核的页面原始记录。`verify_final.py` 也未要求每个恢复字段都有观察证据 | 四例重做实际页面取证；字段由观察推导，缺记录/观察失败必须拒绝 PASS |
| R4 / P2 | `BASE/freeze_final.py` 丢失 `tests/`、`tools/` 前缀；旧 manifest 中 scanner 指纹过时、漏后加 review helper；最后扫描后 `reports/results.md` 又改字节 | 全部交付工具可唯一定位、指纹匹配；报告定稿后扫描，最终字节与扫描清单一致 |

R1 现有两个 D2 用例只执行内部 stream + response，且“前置等待”实际是 provider create 中的等待，**不是完整 `_pre`/路由前置窗口**。不得仅改测试名称后声称补了路由覆盖。R3 不等于断言旧助手没操作浏览器；结论是已交证据不足。

## 2. 文件责任与顺序

`NEWROOT/source/` 为新产品；`baseline-source/` 为 BASE 的364文件只读起点；`tests/` 是工具测试；`runtime/` 是实验数据；`evidence/` 是原始证据；`reports/` 是交付材料。

| 任务 | 修改 / 新建范围 | 验收产物 |
| --- | --- | --- |
| A 保护起点 | NEWROOT 目录、必要工具副本、输入快照、progress | 新旧对象隔离、来源匹配 |
| B R1 取消补偿 | `source/backend/main.py`、`source/backend/tests/test_cancel_boundaries.py` | 正确原因 RED/GREEN、路由/响应边界覆盖 |
| C R2 容量断言 | 同一边界测试文件 | 全容量检查与丢槽负控，不改 guard 产品 |
| D R3 UI 取证 | `write_ui_evidence.py`、`verify_final.py`、`tests/test_verify_final_negative.py`；可新增 `tests/test_ui_evidence.py` | 实际观察输入、拒绝无证据布尔值 |
| E R4 清单与复验 | `freeze_final.py`、`scan_records.py`；必要最小适配 controller/probe/bootstrap/shutdown/guard；可新增 `tests/test_delivery_manifest.py` | 同源测试、native/正式矩阵、可定位清单 |
| F 当前交付闭环 | reports、patch、最终扫描/保护 sidecar | 四发现逐项关闭或准确阻塞 |
| G 后续本地准备 | `reports/next-stage-preparation.md`、`integration-notes.md`、必要公开元数据证据 | 真实缺口、整合预案、独立授权请求 |
| H 总交付 | results、review、证据入口 | 可转交审核的单一入口 |

顺序为 **A → B → C → D → E → G → F/H最终定稿与扫描**。F 的报告草稿可提前写；**G 的报告必须在最后扫描前完成**。全部由同一助手串行执行，服务/数据库/浏览器实验独占运行。

## A. 保护与副本（先做，不运行旧脚本顶层）

- [ ] 读取适用 AGENTS.md；核对 HEAD/index、六修改的 SHA、必要路径、端口和其他执行者。主仓若已经变化，先报告具体差异，不静默更新预期或覆盖工作。
- [ ] 验证1.1清单指纹及364个实际文件；缺项/字节差异即停止。检查非生成文件是否有未列入 manifest 的额外项。生成项仅排除 `node_modules/.next/__pycache__/.pytest_cache` 目录、`.pyc`、`frontend/public/build-id.txt`、`frontend/tsconfig.tsbuildinfo`；不得用更广忽略掩盖新源码。
- [ ] 创建全新 NEWROOT，按该 manifest 物理复制到 source 与 baseline-source，复核两份一致；不复制 `.git`、`.env`、旧数据库/日志/runtime整树。
- [ ] 物理复制 BASE/source/frontend/node_modules、PUBLIC_SEED、MODEL_SEED；不用 junction/symlink/hardlink，不跑安装器。公开库每轮再复制到独占目录。BGE固定 revision `f03589ceff5aac7111bd60cfc7d497ca17ecac65`、CPU768维；公开库1528块/4来源/QA0。
- [ ] 复制必要根级 Python/CJS、tests/tools副本，至少包含 `stage_guard.py/node_guard.cjs/checks.py/freeze_final.py/gen_patches.py/protection_check.py/scan_records.py/run_controller.py/orchestrate.py/bootstrap.py/shutdown_bootstrap.py/shutdown_diagnostic.py/test_shutdown_diagnostic.py/stub.py/probe.py/verify_api_cancel.py/verify_final.py/write_ui_evidence.py`、`tests/`及实际交付的`tools/`。按**实际文件**另存 `evidence/input-start/tools-manifest.json`；不能依赖 BASE 过时 tool manifest。供参考的旧 evidence 只读，不伪装成新运行输出。
- [ ] 复用 `BASE/evidence/input-start/bge-space-verification-reference.json` 作为冻结公开样本输入，逐字节保存来源和SHA；公开gold/样本不换。
- [ ] 阅读 PROTECTION_HELPER 的 snapshot 和副本 `protection_check.py`，保存新的开工快照；保护 HEAD/refs/index、用户修改、原配置/语料/模型/依赖及 BASE/source/tools/既有 evidence。最后与开工逐项比，不仅调用一次“历史12项PASS”。
- [ ] 先适配副本 `checks.py` 的白名单及四个固定模式；TOOLS同时执行 `tests/` 与根级 `test_shutdown_diagnostic.py`，避免漏掉cleanup契约。保存真实 command/cwd/环境字段名（非值）/开始结束/exit/timed_out/完整日志。不得执行 `orchestrate.py` 顶层来取 clean_env，不带真实 shell 凭据运行裸 pytest。

**A门：** 只读输入一致、新候选隔离、保护可核对。未通过不得启动实验。

## B. R1：正文生成器未启动的取消补偿

### B1 先精确 RED

- [ ] 复用现有 `_isolated_db/_commit_user_message/_build_stream_namespace/_stream_namespace_base/_real_chat_response`，只修改新副本。加入下面的确定性测试，先在未修产品上运行 BOUNDARIES，保存失败：期望2条，实为只有user；不得把缺变量/语法错误算RED。

可直接加入现有边界测试的回归起点：

```python
def test_d2_disconnect_during_response_start_before_iterator_enters():
    sm, engine = _isolated_db()
    try:
        _commit_user_message(sm)
        namespace, guard = _build_stream_namespace(sm)
        llm = _LLM(_Response())
        _stream_namespace_base(namespace, llm)
        response = _real_chat_response(namespace)
        headers_started = asyncio.Event()
        bodies = []

        async def send(message):
            if message["type"] == "http.response.start":
                headers_started.set()
                await anyio.sleep_forever()
            elif message["type"] == "http.response.body":
                bodies.append(message)

        async def receive():
            await headers_started.wait()
            return {"type": "http.disconnect"}

        async def scenario():
            with anyio.fail_after(3):
                await response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send)

        anyio.run(scenario, backend="asyncio")
        snapshot = _await_placeholder(sm, engine, expected_rows=2, timeout=0.5)
        assert [row["role"] for row in snapshot["messages"]] == ["user", "assistant"], snapshot
        assert snapshot["messages"][1]["content"] == PLACEHOLDER
        assert snapshot["message_count"] == 2
        assert bodies == []
        assert llm.async_client.calls == []
        assert namespace.get("_post_calls", []) == []
        assert guard._sem.acquire(blocking=False)
        guard._sem.release()
    finally:
        engine.dispose()
```

- [ ] 另建真实 chat 路由/前置窗口测试：在隔离环境实际执行路由函数（可AST去装饰器），用 Event 证明用户消息 commit 后 `_pre`/bootstrap 的线程工作尚未结束，再注入 disconnect并放行线程。若替换昂贵检索/模型，仅在外部接缝替换；用户落库与补偿使用真实产品函数和隔离 SQLite。保存前置结束、响应开始、body进入的顺序。
- [ ] 区分两层：上面的 AST 内部流测试直接证明response缺陷；真实前置测试证明route交接，不可把 fake SDK create 等待当 `_pre`。没有provider请求的用例只算持久化边界，不加入六例上游断连统计。

### B2 推荐最小实现与回归

默认思路：请求局部记录**实际 stream 函数是否已进入**；response 结束/异常的 finally 在关闭body之后，仅对“未进入”请求执行受保护、可等待的补偿。已进入流继续由原stream的 `_posted/finally`负责。不要依赖 async generator 私有frame、轮询数据库最后一条消息或再造第二套持久化。

一个可采用的response接缝如下；不是要求增加全局回调系统：

```python
from anyio import CancelScope


class _ChatStreamingResponse(StreamingResponse):
    def __init__(self, *args, on_response_close=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_response_close = on_response_close

    async def __call__(self, scope, receive, send):
        try:
            async with ClosingStream(self.body_iterator):
                await super().__call__(scope, receive, send)
        finally:
            if self._on_response_close is not None:
                with CancelScope(shield=True):
                    await self._on_response_close()
```

chat 内连接方式（其余既有 stream 内容保留，不用此示例替换完整函数）：

```python
stream_started = False

async def compensate_unstarted():
    if not stream_started:
        await run_in_threadpool(_post_placeholder, pre)

# 在现有 async def stream() 的第一条语句加入：
nonlocal stream_started
stream_started = True

# 在现有 _ChatStreamingResponse(...) 构造中增加：
on_response_close=compensate_unstarted,
```

必须检查 main 当前导入；测试AST提取也要提取这些**真实产品局部声明**，不能在测试中另写补偿实现。若B1真实前置测试暴露“route取消时尚未移交response”的缺口，需在route同一所有权交接处补齐；这段response示例**不能证明该窗口已修**。不改变持久化业务语义，若必须改变则停下说明具体原因。

- [ ] GREEN验证：headers阻塞断连、开始后的首字前/部分取消、重复disconnect、正常完成、前置工作完成/失败、补偿DB失败。保持 user/assistant恰成对、失败占位为 `服务暂时无响应，请稍后重试。`、coverage unknown、无半截正文、无重复补偿。
- [ ] 正常完成测试用真实 `_post` 的隔离持久化接缝或实际API/SQL证明完整answer落库；“_post调用记录不为空”只能算调用层，不能算真实持久化验收。
- [ ] 补偿失败须可观察且门禁失败，不能 `except: pass` 掩盖；保留取消/业务异常传播，日志不输出不受控异常中的敏感值。不要扩大为重写所有既有落库异常分支。
- [ ] 新response接口默认参数保持其他caller兼容；单请求取消不关闭共享SDK。运行BOUNDARIES、MECHANISMS、LIFECYCLE并保存各自退出码。

**B门：** R1有效RED/GREEN、真实前置窗口结论、正常与取消一次性补偿契约齐全。前置测试未做只能记PARTIAL，不能把R1整体关闭。

## C. R2：证明全部并发容量恢复

- [ ] 只修边界测试，不改已修好的 `llm_guard.py`，不读 `_value` 当唯一证明。
- [ ] 保存负控：2名额中故意占住1个，原“acquire立即release”检查仍可通过；新检查必须拒绝。使用真正的BoundedSemaphore，不用永远返回预设值的mock。
- [ ] 用下列检查替换storm测试中原循环；保留全部授予/取消负载和异常检查。

```python
def _assert_full_capacity(guard, limit):
    held = 0
    try:
        for _ in range(limit):
            assert guard._sem.acquire(blocking=False), "capacity lost after grant/cancel storm"
            held += 1
        extra = guard._sem.acquire(blocking=False)
        held += int(extra)
        assert not extra, "capacity exceeds configured limit"
    finally:
        for _ in range(held):
            guard._sem.release()


def test_capacity_assertion_rejects_one_lost_slot():
    guard = _LLMGuard(limit=2, timeout=1.0)
    assert guard._sem.acquire(blocking=False)  # 无害模拟一个未归还名额
    try:
        with pytest.raises(AssertionError, match="capacity lost"):
            _assert_full_capacity(guard, 2)
    finally:
        guard._sem.release()
    _assert_full_capacity(guard, 2)
```

- [ ] 运行BOUNDARIES，并核对正常等待、timeout、同步/异步共用、取消风暴均保留。不要新增性能基准/自定义信号量。

**C门：** 真实全容量恢复、无法超额获取、丢槽负控可拒绝，失败后测试自身不残留持有名额。

## D. R3：UI观察与验收工具

- [ ] `write_ui_evidence.py` 移除固定epoch、固定会话ID和写死成功字段；顶层import不能登录或发请求。把四例映射/校验抽成一个小型纯函数，命令入口读取**本轮实际观察文件**及stub时间线；无需通用浏览器框架。
- [ ] 四个固定案例名保持：`ui-existing-first/partial`、`ui-new-first/partial`。每例在 `evidence/round-05/ui-observations/<完整case名>.json` 保存结构化观察，在同目录保存引用的原始snapshot/DOM读数/工具输出。记录至少含：本轮/操作/tab/case标识、唯一问题、send/stop真实时间、页面会话ID及API核对、停止前正文读数、停止后输入控件状态、同ID重问、新会话重开历史的实际内容；不保存cookies、Authorization或localStorage token。`write_ui_evidence.py round-05`固定读取这四份输入，不接收任意根外路径。
- [ ] 统一时间单位：浏览器原始记录保留epoch毫秒，生成证据的`sent_at/stopped_at`转换为epoch秒，与stub的`at`比较；不得把单调计时值与epoch混用。四个输出沿用 `ui-existing-first-final.json/ui-existing-partial-final.json/ui-new-first-final.json/ui-new-partial-final.json`，保留原始输入引用及SHA。
- [ ] 原始观察不能只是助手手填四个true。由可见正文中的本机替身标记推导partial，由textarea/button实际enabled/disabled状态推导恢复，由重开历史后的实际占位/完整答案推导history；保存观察引用和SHA，复核者可读回。截图可补充，不能替代必要的结构化状态。
- [ ] `same_browser_operation_start_stop` 只能由真实操作记录推导；首字前send→stop在同一浏览器操作内完成，并以stub已收到请求而正文0片段校验，避免停止早于请求。部分案例同样记录真实操作链，不硬填true。
- [ ] provider request_id按本轮唯一问题/场景/时间窗匹配，必须唯一；终态必须真实client_disconnect。不唯一、已completed、阶段错误均作废保留，不更换名称充数。
- [ ] `verify_final.py`读取引用的原始观察，校验其指纹和同轮/同case/会话关系；不得只信生成JSON里的布尔值。新增负控：缺观察、观察SHA不符、正文实际为空却partial=true、input仍disabled却恢复=true、新会话未重开历史却history=true、错tab/会话/request_id、首字前无上游请求或实际已有正文，全部拒绝PASS。
- [ ] 在未修工具上得到正确负控失败，再修工具；TOOLS全部回归。原样保留缺例/重复ID/源码不同版/控制器失败/退出未知或强停/SDK未关净/摘要未完成的负控。

**D门：** 工具不制造成功、原始观察能追溯、负控确实拒绝假绿。实际四例在E运行，不用旧round04记录填新文件。

## E. R4修复与同版本完整复验

### E1 清单与固定入口适配

- [ ] `freeze_final.walk`支持独立的relbase：产品条目相对 `NEWROOT/source`；工具条目统一相对 NEWROOT，保留 `tests/`、`tools/` 前缀。新增工具/测试必须枚举进去；root和nested同名不得覆盖。每清单保存path/bytes/SHA，拒绝重复、绝对路径、`..`或根外链接。
- [ ] 工具负控至少验证：`tests/a.py`与`tools/a.py`并存、后加工具被纳入、manifest缺文件/重复/改字节/越界均拒绝绿色。最终冻结后不再改scanner/helper。
- [ ] 修订scan目标：所有本轮新增/修改产品及测试、所有交付工具（包括nested）、报告/日志/patch、准备材料、本执行书。当前代码只glob根脚本会漏nested工具，不能直接沿用。
- [ ] 本轮新标签固定为 **`shutdown-control-07`（只加载NEWROOT/source）** 和 **`round-05`（同一source）**；不运行intervention，不复做历史control05。此处baseline-source是本次未加R1修复的364文件起点，**不是旧SDK未修复362基线**。
- [ ] 适配所有相关固定标签/白名单/路径：`run_controller/orchestrate/bootstrap/shutdown_bootstrap/shutdown_diagnostic/probe/verify_api_cancel/verify_final/stage_guard/node_guard/checks`，及引用的fixture/tests；把旧BASE_RUNTIME依赖换为新公开seed。只做路径、标签、观察和判据适配，不建设进程平台。
- [ ] final verifier须核对每次运行保存的源码/tool输入快照与冻结版本，control07与round05一致；只核对“当前source符合manifest”不能证明旧运行也来自该版本。
- [ ] 复用已有shutdown工具的saved-native句柄/身份逻辑。完整控制器也记录实际Python与shim身份/退出，不能把Popen shim码冒充native码；一个cleanup失败仍清理其余owned，未知/强停后端拒绝PASS。不按端口、进程名批量杀用户服务。
- [ ] 在实验前固定source/tool manifest；G需要的测试记录器/公开元数据辅助脚本也提前定稿，后续优先用已有工具或直接只读命令，不在E跑完后临时编辑工具。原始日志/报告随后生成，最后再按F闭环报告字节。两类快照分开，不覆盖input-start。

### E2 固定白名单命令与执行协调

所有命令只在NEWROOT运行；例中默认路径如A另选目录，统一替换。先完成E1适配，旧脚本**不接受新标签**，不能照抄直接跑。

```powershell
$taskRoot = 'C:/Users/33393/Desktop/fazhi-closeout-reviewfix-20261006'
$taskPy = 'C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe'
Set-Location -LiteralPath $taskRoot
& $taskPy -I -B checks.py BOUNDARIES boundaries-final-01
& $taskPy -I -B checks.py MECHANISMS mechanisms-final-01
& $taskPy -I -B checks.py LIFECYCLE lifecycle-final-01
& $taskPy -I -B checks.py TOOLS tools-final-01
```

四条分别记录exit，不仅看最后一条；RED和中途GREEN用不同独占标签。四模式子命令为 `PY -I -B -m pytest -q -p no:cacheprovider` 加：前三模式 `--noconftest source/backend/tests/test_cancel_boundaries.py` / `--noconftest source/backend/tests/test_stream_cancellation.py` / `--noconftest source/backend/tests/test_llm_lifecycle.py`，TOOLS为 `tests test_shutdown_diagnostic.py`。测试不执行真实配置或全局有副作用conftest。

前端由白名单控制器在 `NEWROOT/source/frontend`运行：

```text
NODE node_modules/vitest/vitest.mjs run
NODE node_modules/typescript/bin/tsc --noEmit
NODE node_modules/next/dist/bin/next build
NODE scripts/write-build-id.mjs
```

NODE取第1节路径；带现有回环node_guard、禁telemetry和代理指向新后端；不用npx/npm install，不继承真实凭据。

退出验证入口（适配完成后，在NEWROOT运行）：

```powershell
& $taskPy -I -B shutdown_diagnostic.py shutdown-control-07 control
```

- [ ] 先用control07跑最终产品真实lifespan、两取消+两正常同ID重问，排空请求再自然停止。**无包装器额外SDK close**，native Python/shim/backend和stub自然exit0、SDK sync/async最终0打开、并发全容量、端口释放。旧control06不能代替。
- [ ] 完整round05协调流程：启动 `run_controller.py` → 等UI/backend ready → `probe.py setup round-05` → `verify_api_cancel.py round-05` → 四例实际浏览器操作及原始观察 → `write_ui_evidence.py round-05`生成/核对 → `probe.py snapshot final round-05` → 证据齐才写finish marker → 等controller清理/退出 → `verify_final.py round-05`。上述入口须E1先适配，controller固定round05。
- [ ] controller需后台隐藏运行并记录其PID/退出，交互与采样在1200秒UI watchdog期间进行；不能阻塞等controller返回才开始UI。就绪检测有时限，禁止延长watchdog凑通过。
- [ ] 服务默认端口3041/8041/8791。启动前检查空闲；被其他服务占用则不杀它，统一换已确认空闲的回环端口并更新URL/白名单/构建代理/证据。用户3021不动。

### E3 必须直接观察的验收目标

| 门 | 判据 |
| --- | --- |
| 启动/空间 | 真实lifespan/prewarm；1528块/4来源/QA0；固定revision、CPU768维；8冻结公开样本逐条余弦≥0.99999；管理员API核对原公开劳动法第四十四条gold id/正文SHA |
| 正式矩阵 | 恰6个不同provider request_id：API首字前/部分2例 + UI已有/新会话首字前/部分4例；R1无provider测试另列 |
| 断连 | provider真实started；首字前正文0片段，部分有页面正文且上游≥1片段；stop后3秒内client_disconnect，不发满72片段；替身探测间隔≤0.5秒 |
| UI会话 | 取消/完整重问同明确conversation_id，输入恢复；新会话重开历史核对占位和完整重问；结论均有页面原始观察 |
| 存储 | API与SQL逐消息id/role/content/conversation_id深等价、计数/成对一致、integrity_check=ok；占位coverage unknown；半截不落库 |
| 摘要 | 按现有阈值触发一次summary，替身正确识别并有界正常完成；额外请求不混入六例 |
| 退出 | control07与round05来源一致；真实lifespan关闭SDK，无实验额外close；后端/stub自然退出、owned身份/码齐、端口释放；前端受控终止单列，不算自然退出 |
| 整体 | controller正常exit0、final verifier通过、四修复关闭、保护一致，最后扫描覆盖实际交付字节 |

任何产品/工具在冻结后再改，受影响执行证据失效；生成新版本/新轮次重验，保留旧失败，不拼接异版PASS。

**E门：** 同一最终候选的定向/前端/退出/六例/存储/摘要均有新证据。整次失败时可保留已通过子门，不能写整体PASS。

## F. 交付字节、保护与扫描闭环

- [ ] 相对A输入生成 `reports/product-changes.patch` 与 `tool-changes.patch`，区分产品/测试/工具，不将node_modules、DB、缓存、真实配置入patch。对main逐块自审取消一次性、未启动/已启动/正常/错误分支；检查旧SDK和guard修复未被破坏。
- [ ] 先完成G材料和H全部报告，包括限制与失败。报告可以先写“最终扫描以 evidence/delivery-final-scan.json 为准”，**不能为补一个扫描结果尾句在扫描后再改报告**。
- [ ] 保存结束保护快照，与A逐项比；BASE既有内容必须保持不变。若其他助手修改主仓资源，报告冲突，不能自动加入忽略列表。
- [ ] 定稿后生成 `evidence/final-report-manifest.json`；final-source/tool manifest与当前全部文件深比，新增/缺失/多余非生成文件都检查。每条有唯一根与相对路径，旧7个无前缀路径的问题不得残留。
- [ ] Scanner仅在自己的进程内读取 `REPO/backend/.env` 的8字段：`ADMIN_PASSWORD/JWT_SECRET/RERANK_API_KEY/LLM_API_KEY/EMBEDDING_API_KEY/ZHIPUAI_API_KEY/DASHSCOPE_API_KEY/SILICONFLOW_API_KEY`，以及Machine层RERANK_API_KEY第9项；dotenv禁插值，pattern仅AST读取 SCAN_PATTERN_HELPER literal。不得打印真实值或其hash。
- [ ] 运行固定 `scan_records.py delivery-final`（E1须适配输出到 `evidence/delivery-final-scan.json`）：9值无缺项、0命中，5类形状正控通过；正控位置精确归类，未知命中停止扩散。缺字段是UNVERIFIED，不是零泄漏。
- [ ] 最后只读复核扫描target manifest与实际文件bytes/SHA完全一致，source/tool/report清单同样匹配，写独占 `evidence/delivery-closure.json`。改任何报告/代码/工具须新扫描与新closure，不覆盖旧记录。

为避免自引用：最终scan结果和最后closure记录是封口sidecar，明确不作为它们自己的扫描输入；scan结果仅含路径/字段名/规则名/计数/内容hash，不含凭据值，生成schema有负控。已生成的manifest、报告、logs/patch/preparation均在扫描范围。报告预先引用这两个确定文件名，最后消息直接读取sidecar裁定。**不得宣称sidecar也被它自身逐字节扫描。**

扫描只证明本轮选定文件没有这9个当前精确值/已知形状未归类命中，不证明未知编码、历史凭据或全盘安全。

**F门：** 输入/运行/交付版本关系清晰，所有交付工具可定位，报告扫描后字节不变，保护一致，owned服务已停止、临时实验标签页关闭。

## G. 后续阶段：本书可直接执行的本地准备

本节是**实际准备任务**，不是实际整合/上线许可。B—F必要证据未满足时，可以先做这里的只读材料，但不得把候选标为可直接合入或发布。

### G1 整合预案：核对整个候选链，不只本轮patch

- [ ] 在 `reports/integration-notes.md` 比较 **REPO当前产品 → BASE/source → NEWROOT/source** 的完整文件差异与来源。记录每个待整合文件的当前/目标SHA、已有用户修改、依赖关系、拟采取动作；检查候选已有 `rag_chain.py`、聊天hook等上游变化，不只检查本轮main/测试。
- [ ] 六个脏文件中前端与取消功能同链，**文件不重叠不等于无语义交集**。报告必须核对聊天页面/hook的接口与会话契约，不照抄旧“无语义交集”结论。
- [ ] 只在NEWROOT内做patch适用性检查/普通文件副本dry-run；不复制.git/真实配置，不向REPO应用patch，不用整目录覆盖前端。若无可证明公共基底，列为需人工核对，不自动二方拼接。
- [ ] 给出拟整合顺序、逐文件白名单、哪些用户改动保留、哪些差异需确认、回退方案（撤销新候选而非reset主仓）、建议提交拆分与每步重验门。只输出建议，不执行commit。

**G1产出：** 可复核整合映射与dry-run结果/冲突清单，不得声称“已合入”。若dry-run副本发生代码组合变化，它是另一对象；本轮E的PASS不自动覆盖组合对象。

### G2 后端、安全、法律质量的缺口账

- [ ] 在白名单隔离环境静态列出当前测试入口/非slow集合；只尝试公开输入能支持的测试，collection/import也可能加载配置，运行前检查副作用。日志保存准确nodeid、command、exit和未满足输入，不借真实语料、改gold、加skip或安装包。
- [ ] 按认证/输入与文件上传安全、法律日期和版本、费用计算、引用原文与支持度、RAG检索、会话/取消/摘要逐类映射到现有测试和证据，列“已覆盖/本轮实际运行/只历史通过/缺输入/未验证”。不为了表格齐全新造泛化评测框架。
- [ ] 必要缺口给出一个最小后续测试/修复任务及验收值；没有独立法律gold的项明确不能由LLM自评宣称通过。公共替身只验证接线/控制流，不能验证真实答案质量。

**G2产出：** `reports/next-stage-preparation.md` 中测试门清单、可运行结果、实际阻塞输入和最小下一动作。缺输入不反过来篡改E限定技术门，但阻止“完整发布验证通过”。

### G3 依赖、模型来源和风险期限复核：只裁定准备，不升版

- [ ] 读取现存裁定及原始审计：`REPO/docs/local-candidate-decision-20261003.md`、`docs/process-archive/work-report-20261003-joint-candidate.md`、`docs/process-archive/superpowers/plans/2026-10-04-remaining-dependency-preflight.md`。其中版本/风险均是历史对象，先对应本轮实际PY实装、候选requirements/constraints SHA，不能把两个不同venv的审计合成“当前已清零”。
- [ ] 核对模型来源PARTIAL、CPU torch扫描跳过、Chroma/LangChain依赖联动、现存风险接受对象和截止日期是否仍成立。任何2026-10-05截止记录不可自动顺延、转移到新候选或代Owner签署。
- [ ] 需要新事实时只取官方公告/精确版本JSON/源码等小体积公开元数据，独立非实验进程且不携带凭据，保存取得时间/URL/bytes/SHA/原始响应；不继承真实key，不下载wheel/权重，不安装/运行未知模型代码。
- [ ] 产出每条风险的适用面、当前证据、修复/分案线索、待Owner裁定项、复审条件。PyPI无漏洞列表、升级数字或CPU模式都不能自动当风险消除。若完整审计要缺失工具/下载权限，记未执行，不临时装审计器。

**G3产出：** 按实际对象的风险清单和待裁定建议；本书不续签风险、不直接升级Chroma/LangChain/模型依赖。

### G4 发布前置核对：只准备，不触发

- [ ] 本地只读核对branch、HEAD/refs、origin追踪状态及候选拟提交关系；记录“本地缓存的远端信息，非实时”。若要更新远端证据，可在不打印认证URL、不写refs、无交互/有时限条件下执行只读 `git ls-remote --heads origin`；不fetch/pull/push，鉴权失败先分析，不循环尝试。
- [ ] 阅读 `.github/workflows` 的触发分支、secrets字段名、平台/依赖门；写CI拟触发方式及必须补的Linux同源验证。准备清单不能代替CI运行证据。
- [ ] 凭据分为当前选定文件已扫、历史/编码/其他key未证。只列push前需要的扫描范围、停止线和审批，不将当前9值扫描写成“Git历史安全”。历史扫描若要扩大到含真实旧凭据，另请用户确认脱敏范围。
- [ ] 保留服务器未选定事实：列真实库备份+恢复验证、配置/TLS、日志/健康检查、回滚、小范围试运行的必要输入及执行顺序。不要写凭空的服务器IP/系统/域名，不执行真实备份/迁移/部署。

**G4产出：** 一份明确的发布前置和授权请求清单；没有服务器时该部署分支记“未进入”，不是在本书中反复等待。

## H. 最终交付与裁定

执行者把 `NEWROOT/reports/results.md` 的**完整绝对路径**交给用户。该文件须自包含：NEWROOT、BASE及冻结身份，任务/发现状态，原始证据索引，准确命令/实际结果，失败与限制，后续准备结果，需审批的最小动作。

必须有：

1. `reports/results.md`：统一入口，R1—R4逐条关闭/阻塞，不能复制旧PASS。
2. `reports/review.md`：实现者自审；不得写成独立审查。
3. `reports/progress.md`：任务记录、失败原因、版本/标签、下一个动作。
4. `reports/integration-notes.md`、`next-stage-preparation.md`：G的实际材料及未满足门。
5. `reports/product-changes.patch`、`tool-changes.patch`：相对本书A输入；此前候选→主仓差异另列，不能混称本轮新增。
6. `evidence/input-start/`、`final-source-manifest.json`、`final-tools-manifest.json`、`final-report-manifest.json`、各轮原始日志/结果、UI原始观察及映射、API/SQL、native/shim身份与退出、保护、`delivery-final-scan.json`、`delivery-closure.json`。

最终结论分层：

| 层 | 可以何时写“完成/通过” |
| --- | --- |
| 执行交付 | A—H工作及真实失败/阻塞均有材料；这不等于技术通过 |
| 当前本地限定技术门 | R1—R4关闭，B—F全部必要门在同最终候选上通过 |
| 后续本地准备 | G1—G4实际材料齐，未具备输入/授权的分支准确列出；不要求假造上线PASS |
| 阶段验收 | 未参与实现者另行审核新diff和关键原始证据后裁定；没有就保持“待独立复核” |
| 发布上线 | 本书无权批准；完整测试/质量/安全/真实链路/Linux/数据恢复/服务器等门另验 |

技术项状态使用 `PASS / FAIL / PARTIAL / UNVERIFIED / INCOMPLETE`，另列是否BLOCKED及阻塞原因。新增测试数量按实际结果报告，不硬保留旧9/8/28/29数字。明列实际运行的是哪个对象、哪些是历史证据。

## I. 下一个授权请求：不在本书中默认执行

| 动作 | 申请应包含 |
| --- | --- |
| 新Git候选整合/提交 | 精确文件及基底、保留用户改动、冲突与重验、提交拆分；不能捆绑push |
| 真实rerank/模型/Agent验收 | 本轮端点/角色/样本/调用次数/费用上限/脱敏日志、凭据使用范围；不要让用户在聊天贴key |
| 依赖下载/安装/迁移实验 | 官方精确文件URL/版本/SHA/平台/总量、新venv/公开库副本、回退和验收；不改共享环境 |
| Push/远端CI | 远端历史和凭据结论、目标分支、触发的CI/外部影响、撤回方案 |
| 真实库/部署 | 已选服务器、配置/TLS、备份恢复实证、迁移/回滚、监控；当前不具备服务器条件 |

申请推荐下一步时优先给**一个最小动作**，不要一次申请所有权限。G风险材料可准备；风险接受/延期只能由Owner作出。

## 3. 给执行助手的操作建议与本书自复核

- 先做便宜且确定性的R1 RED，再动产品；工具负控先完成，昂贵联调在source/tools冻结后集中跑，不靠重跑完整流程定位一个小错误。
- 取消持久化所有权只有一处负责每个窗口；添加response补偿不能与已启动stream finally重复。前置线程不能强杀，必须等待明确终态并验证交接。
- UI证据测的是页面真实可见/可操作状态，不是写出了JSON；容量测的是全配置名额，不是又成功获取了一次；native码测的是实际后端，不是启动器。这三个代理指标陷阱必须主动检查。
- 不顺手重构main、清除全部旧技术债或升级整个模型链。已有SDK/guard修复保持；允许工具小型纯函数，不许扩展为管理平台。
- 一个任务遇阻，保存证据并继续无依赖的只读准备；必要门未满足就如实交付，不能缩小验收条件。资源泄漏/越界则先安全结束本轮owned任务。

编制复核要点：四发现各有任务和可测判据；已有364起点与新测试数量分开；新native/矩阵标签不冒用旧记录；实际前置窗口不与provider等待混淆；工具路径/报告字节最终闭环；G在最终扫描前完成；旧候选只读；自审不冒称独立验收；当前完善、后续准备和需授权执行三段分明。**本文件是计划，不是修复已完成的证明。**
