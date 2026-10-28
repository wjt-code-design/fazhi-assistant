# 本地候选产品收尾与验收执行计划书

> **For agentic workers:** 按 `executing-plans` 逐任务执行并在每项验收后记录；若该 skill 不可用，按本书的顺序、边界和门禁直接执行。默认由一个助手串行负责，不自行创建其他会话或派发子助手。代码修改先 RED 后 GREEN，交付前自审。本书是完整任务入口，不要求读取本会话。

**编制日期：** 2026-10-06，Asia/Shanghai。

**Goal：** 将已有取消修复推进到同一候选上的产品退出修复、取消边界核查和完整本地联调收尾，交付可复核候选及下一阶段整合建议。

**Architecture：** 保留现有 FastAPI lifespan、LLMRegistry、SSE、SQLite、React hook 和并发门控。优先复用同一 entry 已有 SDK 客户端，由 registry 负责应用级资源收尾，lifespan 在事件循环仍运行时调用。单请求只关闭其回答流，不能关闭共享连接池。实验工具与产品修改分开记账，不新增取消平台、客户端管理框架或数据字段。

**Tech Stack：** 现有 Python 3.11 / asyncio / threading / contextlib、FastAPI / Starlette、已安装 LangChain / OpenAI SDK；TypeScript / React / Vitest / Next.js；现有固定 BGE CPU 环境。不得安装或升级依赖。

## 0. 先读这一页：任务范围与停止线

本书可执行的范围是 **A—F**：保护基线、产品 SDK 生命周期修复、联调工具修正、两个取消窗口核查及必要最小修复、完整本地复验、交付自审和整合建议。**G 仅列下一阶段前置条件，不授权执行。**

全局约束：

- 只修改新建的独立文件候选。主仓代码、旧候选、旧工具、旧证据、原始语料、原模型缓存、真实配置、共享 venv 全部只读；主仓本执行书也不回填。
- 不合入主仓、不创建 Git 分支/worktree、不暂存、不提交、不推送、不部署；不写真实数据库、不启动或停止用户原有服务。
- 动态实验只用公开库新副本、固定离线 BGE CPU、回环 LLM 替身及合成账户；禁真实 LLM、rerank、Agent 请求。真实 rerank 以前有调用许可和验收记录，但本书不借用旧许可扩展当前实验。
- 服务仅监听 `127.0.0.1`。用户原有 `http://127.0.0.1:3021/` 页面和服务不得操作。
- 不加载真实 `.env`、不继承真实凭据到实验环境、不输出密钥值/密钥指纹/命中片段。F 中凭据扫描是唯一例外：批准的扫描器只能在自己的进程内读取指定值作比对，不能拿凭据发请求。
- 不改法律日期/版本门、认证、模型优先级、配额业务、摘要阈值、取消占位契约及界面布局。必要修复应处在本书指定的资源/取消边界。
- 不用 `os._exit`、强制 GC、换事件循环、吞异常、跳过断言、删除失败消息、提高整体超时或盲目升级来换取绿色。
- 每次运行独占新 evidence/runtime 子目录；文件写入拒绝覆盖。失败证据保留，不循环试到成功。
- 同一失败命令先分析原因，原样最多重试一次。同一 bug 经三次产品修订仍不通过则停止修改，提交失败证据和设计质疑；不要把先前 A 的多次试验误作本轮新 bug 的次数。
- 有并行任务、原始资源变化、写入越界、敏感值泄漏或需要扩大权限时，停止受影响任务，用中文纯文本说明，不覆盖他人修改，不弹交互卡片。

完成本书不等于上线完成，也不等于依赖风险全部消除。未满足验收的任务必须记为 FAIL / UNVERIFIED / INCOMPLETE，不能以“已执行”代替“通过”。

## 1. 输入、路径、当前事实

下列别名在整份文件中有固定含义，带别名的路径均从这里展开：

| 别名 | 完整绝对路径与用途 |
| --- | --- |
| REPO | `C:/Users/33393/Desktop/ai-legal-helper`，主仓，只读 |
| BASE | `C:/Users/33393/Desktop/fazhi-cancel-repair-20261005-13137719e0d043d5ba17a9efc33d30ce`，最新冻结候选与证据，只读 |
| NEWROOT | `C:/Users/33393/Desktop/fazhi-local-closeout-20261006`，本轮新建目录 |
| PY | `C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe`，只执行，不安装/修改 |
| NODE | `C:/Program Files/nodejs/node.exe` |
| PUBLIC_SEED | `BASE/runtime/public-kb`，已许可公开语料，只读复制 |
| MODEL_SEED | `BASE/runtime/hf-cache`，已固定离线模型缓存，只读复制 |

截至编制时 NEWROOT 不存在。执行时若已存在，**不要合并、删除或复用**；改用 `fazhi-local-closeout-20261006-<实际时间戳>` 的新目录，在 `reports/progress.md` 写出完整新路径，随后所有 NEWROOT 引用统一指向它。

### 当前基线，不是本轮新验收结果

- 主仓 HEAD：`902e2d161e67100ed6d267a08c393538a0abe109`，暂存区为空。六个既有跟踪修改：
  - `docs/process-archive/superpowers/plans/2026-09-29-local-candidate-decision-and-release-prep.md`
  - `frontend/app/admin/sections/KnowledgeSection.tsx`
  - `frontend/app/admin/sections/UploadSection.tsx`
  - `frontend/app/chat/page.tsx`
  - `frontend/app/globals.css`
  - `frontend/components/chat/InputBar.tsx`
- BASE/source 是独立文件候选，**不是 Git 仓库**。冻结产品文件 backend 289 + frontend 73 = 362；从此候选开始，不从主仓直接复制代码替代它。
- A/B 已有取消与会话归属修复，正式矩阵为直连 API 两例 + 实际 UI 四例。保存记录中这些子门通过；整次 round-03 联调仍失败，后端实际退出 `3221225477 / 0xC0000005`，控制器 UI watchdog 后退出 1。
- C3 对照已区分：不做 SDK 额外关闭的 control-03/04 后端崩溃；额外关闭应用 registry 可达异步 SDK 的 intervention-01/02 后端自然退出 0。04/02 为同版工具配对。它支持应用级收尾修复方向，**不是产品已修复或底层原生根因全面证明**。
- 最新诊断工具 cleanup P2 已修，保存记录中 13 项测试及二审通过；安全修订版没有重跑 native 实验。它可以作为新工具适配起点，不能把旧四轮算成新版工具运行。
- 公开库基线 1528 法律块、4 来源、QA 0；BGE revision `f03589ceff5aac7111bd60cfc7d497ca17ecac65`，CPU，768 维。

### 开工需要核对的本地输入

本书已说明任务要求；以下文件用于核对源码、证据和复用工具，不要求助手猜测历史决定：

1. `REPO/docs/work-report-20261005-cancel-repair.md`，以末尾“C3最终收尾记录（2026-10-06）”更新历史待办。
2. `BASE/evidence/backend-input-manifest-structural.json`、`frontend-input-manifest-structural.json`：最新产品逐文件冻结清单。
3. `BASE/reports/task-C-shutdown-diagnostic-review-v2.md`、`BASE/evidence/shutdown-coordinator-paired-verification.json`：工具安全与真实退出分离的证据。
4. `BASE/reports/task-D-contract.md`、`round-03-fixture-classification.md`：正式案例判据与旧工具误操作。

若上述必要文件/模型/公开 seed 缺失或指纹不符，记录阻塞，不下载替代品、不借用全量真实语料、不沿用旧 PASS。

## 2. 文件责任与任务顺序

`NEWROOT/source/` 放产品；`NEWROOT/baseline-source/` 放开工时相同的362文件且之后只读；`NEWROOT/tests/` 放实验工具测试；`NEWROOT/evidence/` 放原始执行证据；`NEWROOT/runtime/` 放隔离数据库/模型副本/临时文件；`NEWROOT/reports/` 放进度和最终报告。

| 任务 | 允许修改/新增的主要文件 | 依赖与产出 |
| --- | --- | --- |
| A 基线保护 | NEWROOT 下目录、工具副本、输入清单、`reports/progress.md` | 后续任务使用的冻结起点和保护快照 |
| B SDK 生命周期 | `source/backend/main.py`、`llm_registry.py`、新增 `tests/test_llm_lifecycle.py` | 可在真实 lifespan 中退出的产品候选 |
| C 联调工具 | 根目录 `stub.py`、`orchestrate.py`、`bootstrap.py`、`shutdown_bootstrap.py`、`shutdown_diagnostic.py`、`probe.py`、`checks.py`、`verify_api_cancel.py`、`verify_final.py`、冻结/扫描/保护脚本；`tests/` | 只读观察产品、可靠结束并如实裁定的工具 |
| D 取消窗口 | `source/backend/llm_guard.py`、`main.py`，必要时既有 `rag_chain.py`；新增 `tests/test_cancel_boundaries.py` | 排队取消及正文开始前取消的定向结论/修复 |
| E 同候选复验 | 新 evidence/runtime、既有前端测试/构建输出 | 正式矩阵、存储、native 退出及整次联调裁定 |
| F 自审交付 | `reports/results.md`、`review.md`、`integration-notes.md`、变更 patch 和最终清单 | 一个可转交的候选与证据索引，不自动整合 |

表中产品测试均位于 `NEWROOT/source/backend/tests/`；C 的工具测试位于 `NEWROOT/tests/`。不修改前端产品代码，除非复验得到新的直接证据并先向用户说明需要扩大范围。

顺序：**A → B → C → D → 冻结最终候选 → E → F**。B 与 C 可以分别思考，但由同一助手串行执行；所有模型/数据库/浏览器联调必须独占运行。不要为了并行复制多份不一致的最终基线。

## A. 保护基线与建立新候选

- [ ] 读取适用 AGENTS.md，核对主仓 HEAD、暂存区、六个修改的文件 SHA，以及本次任务相关目录是否有其他执行者。只输出状态/路径/文件 SHA，不输出真实配置内容。
- [ ] 按两个 structural manifest 校验 BASE/source 的 362 文件；遇到缺文件立即失败，不把“扫描零项/跳过异常”算作无差异。
- [ ] 在 NEWROOT 独占创建目录，仅复制 manifest 列出的源码文件及必要工具。不得把整个 BASE/runtime、真实 `.env`、旧数据库、旧日志或 `.git` 一并复制。
- [ ] 将同一 manifest 的产品文件再复制一份到 `baseline-source/`，校验与 `source/` 一致，之后不修改。它是 control05 的未修复产品输入，不包含 node_modules、数据库或缓存。
- [ ] 前端 `node_modules` 从 `BASE/source/frontend/node_modules` 普通物理复制到新候选，不使用指向旧目录的 junction/symlink/hardlink；禁止执行安装器。构建缓存只写新候选。
- [ ] 将 PUBLIC_SEED、MODEL_SEED 普通复制到 `NEWROOT/runtime/public-kb`、`hf-cache`，逐文件比对内容与模型 ref。每轮服务再从公开 seed 复制独占 `runtime/<轮次>/read-kb`。
- [ ] 复制旧工具的当前安全版本，并记录复制时 SHA。优先复用 `stage_guard.py`、`node_guard.cjs`、`checks.py`、`probe.py`、`verify_api_cancel.py`、`shutdown_diagnostic.py`/`shutdown_bootstrap.py`、`test_shutdown_diagnostic.py`、`stub.py`、`bootstrap.py`、`orchestrate.py`、`verify_final.py`、`freeze_source.py`、`protection_check.py`、`scan_records.py` 和 `tests/`。先读再适配，不能直接运行这些带硬编码的脚本。
- [ ] 在 B 开始前完成 `checks.py` 的最小路径/固定命令适配。复用它 AST 提取 `clean_env()` 的现有做法，不执行 orchestrate 顶层；追加固定模式 LIFECYCLE / BOUNDARIES / MECHANISMS / TOOLS，分别执行生命周期测试、取消窗口测试、既有取消测试、工具tests。每模式使用环境白名单及独占标签日志，保留每个实际退出码。不得直接在带真实凭据的 shell 子进程中执行示例 pytest。
- [ ] 在 `evidence/input-start/` 保存输入 manifest、工具 manifest、主仓/原资源保护快照。记录 PY/NODE 的实际版本及已装相关包版本；不升级。

新目录和文件编辑使用当前平台可靠的文件工具；代码/文档编辑优先 apply_patch。副本操作用普通复制并检查绝对路径，不用递归删除或目录镜像覆盖。

保护脚本目前依赖 `C:/Users/33393/Desktop/fazhi-next-acceptance-review-20261004-a43ad25a98f04fb597e5b1aabe270b9a/verify_evidence.py`。先确认存在、阅读其 snapshot，再在工具副本中记录当前开工快照与结束对比；不能只信历史快照。主仓新增本执行书属于已知输入，不允许把其他变化自动加入“忽略名单”。

**A 门：** 原始资源不变、复制内容匹配、输入可用、没有尚未协调的写入冲突。失败时停止动态实验。

## B. 最小产品 SDK 生命周期修复

### B1 所有权核对和设计取舍

- [ ] 追踪 `LLMRegistry.__init__/_load/_build/get/variant/variant_of/reload` 的所有调用；核对 main 的 `admin_llm_switch`、回答重试、辅助同步调用和异步流。记录每条路径是否创建新 SDK、谁持有、何时关闭。
- [ ] 检查当前安装版 ChatOpenAI 的客户端注入字段和公共 SDK close API；结论来自已安装代码/实际契约测试，不依赖对其他版本的记忆。
- [ ] 默认取舍：variant 与 model-only reload 若只改变模型/思考请求参数，优先复用原 entry 的 SDK 客户端，保持请求参数语义，避免每次创建新连接池。不同 provider/端点/凭据/timeout 不得未经证明地共用同一客户端。
- [ ] 新接口定义为 `async LLMRegistry.aclose() -> None`，由 `main.lifespan` 的退出路径在运行中 loop 内调用。它关闭 registry 实际拥有的唯一 SDK 资源，重复调用不重复关闭；同步 SDK 的实际拥有者也应有明确收尾，不能据旧实验“sync仍open但没崩”认定它们不必关闭。

不直接复制诊断中的散落私有字段访问；若当前库只提供私有接缝，将其局限在 registry 的一处，并以版本契约测试和限制说明保护。允许必要的局部所有权记录，但不能每次 variant/reload 将旧客户端永久追加进列表。关闭失败应继续尝试其他资源、最终显式失败并可定位到资源类别/模型 key；不打印完整 cfg、URL 认证信息或异常中的敏感内容。

**备选而非默认：** 为每请求另建 SDK/池、应用退出扫描 GC 中所有 HTTP 客户端、整体升级依赖。它们的变更面或所有权风险更大，当前没有必要。本方案若不能以现有客户端注入契约安全复用，应停止该分支，说明最小替代方案和影响，用中文纯文本向用户对齐；不擅自造新管理框架。

### B2 先产品 RED，再最小实现

- [ ] 新建 `source/backend/tests/test_llm_lifecycle.py`，按现有取消测试方式 AST 提取实际产品函数/类，或使用受控 import。测试不得 import 导致真实配置、Chroma、模型加载的全局 conftest；不得手写第二份产品实现。
- [ ] 必测：正常 lifespan 退出关闭；lifespan 内业务异常仍收尾且原异常不被静默吞掉；唯一对象仅关闭一次；一个 close 失败仍尝试其余且门禁失败；variant/reload 请求参数保持正确；多次 variant/reload 不增长 SDK 所有者数量；单请求取消不关闭共享客户端，也不伤及另一请求。
- [ ] RED 阶段至少用当前真实函数证明缺少退出收尾；另外证明 variant/reload 当前新建客户端的资源缺口。保存失败输出和准确原因；纯语法/缺包错误不算有效 RED。
- [ ] 实现上述最小接口和生命周期 finally；不要顺手重构整个 registry，不更改路由/配额 API。线程锁只保护短快照/变更，不能持有 RLock 跨 await。
- [ ] 运行同一测试 GREEN，再运行既有取消机制回归。记录接口/字段兼容性与关闭异常传播边界。

可直接放入新测试文件的最小 lifespan 回归起点（不是全部 B 的测试）：

```python
import ast
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace


def test_real_lifespan_closes_registry_in_running_loop():
    events = []

    class Registry:
        async def aclose(self):
            assert asyncio.get_running_loop().is_running()
            events.append("close")

    async def threadpool(fn):
        return fn()

    path = Path(__file__).resolve().parents[1] / "main.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                and n.name == "lifespan")
    ns = {
        "asynccontextmanager": asynccontextmanager,
        "setup_logging": lambda level: None,
        "settings": SimpleNamespace(log_level="INFO"),
        "run_in_threadpool": threadpool,
        "prewarm": lambda: events.append("prewarm"),
        "registry": Registry(),
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)

    async def exercise():
        async with ns["lifespan"](None):
            assert events == ["prewarm"]
        assert events == ["prewarm", "close"]

    asyncio.run(exercise())
```

从 `NEWROOT` 执行，使用下列第 3 节 PY 变量，分别保存两项退出码：

```powershell
& $taskPy -I -B checks.py LIFECYCLE lifecycle-green-01
& $taskPy -I -B checks.py MECHANISMS mechanisms-green-01
```

**B 门：** 正确原因 RED、同契约 GREEN、所有权和参数兼容证据齐全。单元门通过仅允许进入 E，不提前称 native 修复通过。

## C. 修正联调工具，不伪造产品成功

- [ ] 所有路径、白名单命令、轮次限制、manifest 输入及环境根路径改到 NEWROOT；仍需白名单、回环网络、禁止真实 .env、runtime 写入边界。不要 import 旧 orchestrate 执行其顶层启动代码。
- [ ] `stub.scenario()` 先识别实际 system 中“法律对话摘要器”，记为 summary；重写只解析当前问题后缀，摘要历史取消标签不得变成当前 answer。摘要走有界正常替身返回，不延迟/输出 72 片段；回答取消路径仍保持首字前/部分案例的原判据。
- [ ] `tests/test_stub_selector.py` 先增加 summary + 历史取消标签的 RED，再修 classifier。保留既有 rewrite/answer 两项回归；补请求目的与响应类型的一致性，不通过禁用产品摘要实现工具通过。
- [ ] 浏览器操作只使用显式 `tab/case/question/conversation_id/request_id` 输入，不能复用上次 case 的可变全局状态。若浏览器工具对象必须放在会话变量中，绑定案例映射并核对 expected id；错误写入不覆盖旧文件。
- [ ] `ui-finished.marker` 只在四个正式 UI 案例、同 ID 重问、API/SQL 终态和输入恢复证据齐全后由协调端写出。此前取得局部证据不意味着完成；缺案例不能写 marker。总 watchdog 保持现有 1200 秒上限，不靠加长超时修复。
- [ ] `verify_final.py` 必须要求恰好六个互不重复的正式案例，严格阶段/SQL/退出判据。新增负控：案例缺失、request_id 重复、后端退出未知/非0、控制器非0、强制停止后端、证据不同源码版本均拒绝 PASS。
- [ ] 复用诊断工具当前 cleanup 修订：按已保存的进程身份/句柄逐项收尾，一个失败仍尝试其余；状态未知必须 INCOMPLETE。先核对现有 13 项契约，再补新增适配的最小回归，不新建进程管理平台。
- [ ] 无 UI 产品退出验证可用新工具副本的 control 模式，但须新增明确标签 `shutdown-control-05` / `shutdown-control-06`，分别关联新 baseline/final manifest。两次都禁止实验额外 close，报告 `experimental_extra_close=false`；旧 control04/intervention02 只读保留，不沿用旧判断或冻结计数。
- [ ] 固定来源映射：control05 仅从 `NEWROOT/baseline-source` 加载产品，control06 与 round04 仅从 `NEWROOT/source` 加载产品；白名单仍只有本轮工具与固定角色。相应 manifest、静态配置提取和 readonly-source 守卫覆盖正确来源，不能由任意外部路径参数绕过。其他路径不得偷偷回落旧 BASE。

**C 门：** 工具定向测试通过、负控确实阻止假绿、路径和白名单只指向新候选。B 产品修复的验收不能使用 intervention 模式。

## D. 两个旧取消窗口：先验证，证实后最小修复

### D1 等待并发名额时取消

当前 `_LLMGuard.__aenter__` 用 `asyncio.to_thread(self._sem.acquire, ...)`。取消等待任务不一定停止 acquire 线程，线程后来拿到名额可能没有匹配 release。核对所有同步/异步调用，不能只修一个 caller。

- [ ] 在 `source/backend/tests/test_cancel_boundaries.py` 用实际 `_LLMGuard` 定向复现：占满并发位 → 异步等待 → 等待期间取消 → 释放原持有者 → 等到 acquire 线程终态 → 再次获取全部容量。用 Event/Barrier 定位阶段，避免只靠 sleep 和读取 `_value`。
- [ ] 期望：取消向调用方传播，发出cancel后3秒内结束等待任务，不触发 provider/重试/耗尽；释放原持有者后等待acquire线程终态并证明迟到名额归还，检查期限为测试配置的queue timeout加3秒。正常等待、超时、同步与异步混用、授予和取消同窗口不超限或双 release。测试须先证明已经进入等待阶段，不能取消尚未启动的任务冒充覆盖。
- [ ] RED 成立才做最小修复，保持同步/异步共用一个计数源，不强杀线程、不另建队列服务或第二个信号量池。取消及时返回与迟到资源回收分别验证。

### D2 用户消息落库后、响应正文尚未开始时取消

main 的 `_pre`/bootstrap 可能已经落 user 消息，而取消占位逻辑位于流内部。仅关闭一个尚未迭代的异步生成器，不能假定它的 finally 已执行。

- [ ] 用真实路由/ASGI 接收与发送边界和隔离 SQLite 定向复现：用户消息已 commit，首个正文迭代/发送之前 disconnect；另测前置线程工作尚未结束时 disconnect 后完成。
- [ ] 期望：正常有序收尾后，同 conversation 的已落库 user 恰有一个失败助手占位、coverage unknown，无半截正文，无重复占位；无 provider 请求的案例不得计为上游断开案例。前置业务失败遵循已有错误/持久化契约，不能把所有 HTTP 错误都写成取消占位。
- [ ] 有有效 RED 才在现有 response/route 所有权边界修，保留 stream finally 正常路径。不强杀线程，不新增持久化任务表，不修改法律结果或失败占位文案。
- [ ] 补正常正文、部分取消、重复 disconnect、前置失败的回归。若必须改变业务持久化语义而不是补资源收尾，停止并说明需要确认的具体契约。

**D 门：** 两窗口均有可观察结论；证实的缺陷须 RED/GREEN，并能回归原取消机制。未复现只能注明当前输入未复现，不能称“已排除所有竞态”。任一明确缺陷未修或必要测试无法完成，本阶段仍未完成。

## E. 同一最终候选的本地验收

- [ ] B/C/D 定稿后生成新 source/tool manifest、产品 diff，冻结公开 seed、模型 revision 和测试样本。新增测试应计入 manifest；不得硬保留 362 文件数量，也不能仅验证旧文件遗漏新增文件。
- [ ] 若控制实验需要证明 RED，用改产品前的独占 baseline 副本；GREEN 用 final 副本。同一源码不能边运行边编辑。所有正式 E 结果必须对应 final 的同一版本。
- [ ] 执行 B/D 及既有取消机制测试；工具套件与 cleanup 契约；完整前端 Vitest、TypeScript 检查及 Next 生产构建。只使用已有依赖命令，不用 npx/npm install。
- [ ] 所有服务继承环境白名单，LLM 27-role 配置来自候选静态常量但端点/凭据替换为回环合成值，quota 为0、Agent/rerank禁用；不得写成“正常模型池健康”。原有 Node 回环守卫、Python 守卫正向控制保留，记录它们不是 OS 级完整沙箱保证。
- [ ] 同轮确认真实 lifespan/prewarm、1528块/4来源/QA0，并复用 `bootstrap.py` 的8个冻结公开样本检查：CPU768维、固定 revision，与公开库已存向量余弦均≥0.99999。样本及向量指纹不变；额外通过管理员API核对劳动法第四十四条公开gold id/正文SHA，复用 `probe.py setup round-04` 的既有独立期望，不改gold。
- [ ] 先执行一次无 UI、真实 lifespan、无实验额外 close 的产品退出 GREEN：两个新会话、两取消、两正常同 ID 重问。stop 前 HTTP/task 排空、并发容量恢复；实际后端 Python 与 shim 均自然 exit0，stub 自然 exit0，端口释放。若 B/D 又修改产品，先前 GREEN 不再覆盖最终版本，需按新版本重验。
- [ ] 再执行一次完整正式矩阵：直连 API 首字前/部分两例；UI 已有/新会话各首字前/部分四例。每例唯一问题、明确 request_id，重问核对同 ID；新会话还重新打开历史检查占位和完整重问。
- [ ] 触发一次现有摘要边界，确认 fixture 识别 summary、正常结束；额外请求单列，不混入六例。不能删除历史消息或禁用摘要来通过。
- [ ] API 与 SQL 终态比对：消息 id/role/content/conversation_id/计数一致、轮次成对、`integrity_check=ok`；取消占位 coverage unknown，半截只保留当前页面，不能宣称已保存。
- [ ] 全部证据到位后写 finish marker，控制器正常结束，后端与 stub 自然退出并记录实际/native 和 shim 码。前端服务若按已登记 owned 身份受控终止，应单列其退出方式与码，不能把它算自然退出。未知身份/遗留服务/端口/关闭错误均失败；只允许清理本轮保存身份，不按端口或进程名杀其他服务。
- [ ] 重新运行 final verifier，保护比对和 F 的选定文件扫描；不可引用旧测试、旧扫描代替当前执行。

### 固定的行为判据

| 门 | 必须直接观察的事实 |
| --- | --- |
| 首字前取消 | 真实上游已收到 request_id，但取消前正文0片段；实际 client_disconnect 在 stop 后3秒内，未发满72片段 |
| 部分取消 | UI 有可见正文、上游至少1片段；同样3秒内真实断开且不足72片段 |
| 会话 | 取消与重问属于同一明确 conversation_id，API/SQL 配对，不只检查页面标题 |
| SDK/并发 | 每请求不关共享池；最终应用拥有的客户端完成收尾；无残留名额，关闭失败不可绿色 |
| 后端退出 | 最终产品真实 lifespan 收尾，无包装器额外 close，无强停，实际 Python/shim exit0 |
| 完整联调 | 六正式案例、存储、最终同源、控制器正常结束、owned 清理、保护和扫描同时满足 |

取消 fixture 单次探测/写间隔应不大于0.5秒，以支持3秒断连判据。首字前 start→stop 需在同一浏览器操作中完成，避免工具往返把首字前拖成部分；分类错误须保留并排除，不能按名称硬算成功。

全后端套件若需要未许可语料/不存在输入，登记准确测试名称、collection/执行输出、缺失输入和影响。允许运行本书隔离可运行范围，**不允许换全量真实库、修改测试 golden、skip 后宣称全套通过**；未运行的整体后端/法律质量门留给 G，不改变本地限定验收的口径。

## 3. 固定运行入口与证据格式

在每次新 PowerShell 会话设置任务变量，不复用 HOME/CODEX_HOME 等系统变量。若 A 已改 NEWROOT，先将下列 `$taskRoot` 改成登记的完整新路径。

```powershell
$taskRoot = 'C:/Users/33393/Desktop/fazhi-local-closeout-20261006'
$taskPy = 'C:/Users/33393/Desktop/fazhi-next-local-20261004-356fb810b3144d158e5dd18b9e276499/joint/venv/Scripts/python.exe'
$taskNode = 'C:/Program Files/nodejs/node.exe'
Set-Location -LiteralPath $taskRoot
& $taskPy -I -B checks.py LIFECYCLE lifecycle-green-final
& $taskPy -I -B checks.py BOUNDARIES boundaries-green-final
& $taskPy -I -B checks.py MECHANISMS mechanisms-green-final
& $taskPy -I -B checks.py TOOLS tools-green-final
```

checks.py 的四个固定模式分别对应 `PY -I -B -m pytest --noconftest source/backend/tests/test_llm_lifecycle.py`、`test_cancel_boundaries.py`、`test_stream_cancellation.py`（后两项也使用完整 `source/backend/tests/` 前缀），以及 `PY -I -B -m pytest tests`；统一追加 `-q -p no:cacheprovider`。模式不同但命令不得包含任意shell字符串。这些子命令须由记录器分别运行、分别读取退出码，不能只记录最后一个命令成功。RED/GREEN标签独占，pytest stdout/stderr、command/working_directory/环境字段名（非值）/实际退出码均保存。单元不得因本地 conftest 或配置产生模型/数据库副作用。

前端命令由 C 适配后的白名单控制器在 `NEWROOT/source/frontend` 中运行，带 `node_guard.cjs`、`BACKEND_URL=http://127.0.0.1:8041` 和禁 telemetry 环境，不手工继承整套当前 shell 的密钥：

```text
NODE node_modules/vitest/vitest.mjs run
NODE node_modules/typescript/bin/tsc --noEmit
NODE node_modules/next/dist/bin/next build
NODE scripts/write-build-id.mjs
```

C 须保留并适配这些实际入口，写出精确命令和原始输出：

```powershell
& $taskPy -I -B shutdown_diagnostic.py shutdown-control-05 control
& $taskPy -I -B shutdown_diagnostic.py shutdown-control-06 control
& $taskPy -I -B orchestrate.py round-04
& $taskPy -I -B probe.py setup round-04
& $taskPy -I -B verify_api_cancel.py round-04
& $taskPy -I -B probe.py snapshot final round-04
& $taskPy -I -B verify_final.py round-04
```

control05 是 A 保存的未修复 baseline 复现，可在 C 工具完成后运行，不能用此时已修改的 source 冒充旧基线；control06 是 B/D 全部定稿后的 final 产品。两个 control 的 source 映射与守卫白名单在 C 先明确。`orchestrate.py round-04` 与 setup/API/UI/snapshot 采样需要协调运行，不能等20分钟控制器返回后才采样；进程启动、就绪、交互、marker、清理、verifier 构成一条执行流程。旧脚本目前不接受这些新标签，直接运行前必须完成 C 适配和契约测试。这段列出入口而非要求阻塞式依次执行。

端口默认 3041/8041/8791；启动前绑定检查。冲突则停下，改用确认空闲的回环端口并统一改 URL、白名单、构建代理与证据；不能终止占用者。无浏览器/UI操作能力时记 UI 门 UNVERIFIED，不能用 hook/HTTP 代替实际页面验收。

## F. 自审、保护、扫描与交付

- [ ] 比较 final 与 A 输入的全部产品变更，逐项检查资源所有权、异常/取消传播、幂等性、线程/loop边界、variant/reload参数与现有占位契约。既有 A 的 Sequence trace 变化、SDK注入接缝仍须登记，不借本轮声称全部回调/真实Agent兼容。
- [ ] 自审五问写入 `reports/review.md`：模块边界是否自然；为何不选更复杂备选；怎样防并发/静默降级/假绿；每条事实来自哪里；DoD 是否实际观察目标而不是代理指标。自审不写成“独立审查”。
- [ ] 开工/交付的主仓 HEAD/refs/index、六个原修改、原配置/语料/模型/依赖文件快照一致；其他任务若发生变化，应报告而非自动忽略。
- [ ] 在复制后的 `scan_records.py` 中将目标明确扩展到本轮全部新增/修改产品、测试、工具、报告、日志/patch和本执行书。保留当前9项精确值与5类形状正控；不得漏扫 llm_registry、llm_guard 和新测试。旧扫描脚本固定选择 main/rag_chain 等文件，直接复制不修改范围会漏项。
- [ ] 扫描器所需原 pattern 文件：`C:/Users/33393/Desktop/fazhi-local-candidate-20261002-67944caf51ff48ce9432831cdd62f72b/source/dispatch-output/local-candidate-closeout-20260928/secret_shape_scan.py`；仅 AST 读取 literal pattern，不执行它的自测副作用。真实值仅来自 `REPO/backend/.env` 的8字段 `ADMIN_PASSWORD / JWT_SECRET / RERANK_API_KEY / LLM_API_KEY / EMBEDDING_API_KEY / ZHIPUAI_API_KEY / DASHSCOPE_API_KEY / SILICONFLOW_API_KEY`，以及 Machine 层 RERANK_API_KEY 第9项；读取dotenv时禁变量插值。不得在父工具输出、日志或模型上下文显示值。缺字段记扫描 UNVERIFIED，不能当0泄漏。
- [ ] 命中只输出文件路径、字段/规则名和计数；已知 scanner 正控按准确位置/规则/数量归类，不能豁免整个目录。真实凭据命中即停止扩散/提交，报告并保全脱敏证据；不得擅自轮换用户凭据。
- [ ] 报告定稿后保存最终文件 manifest，并复核其覆盖报告定稿后的字节。扫描仅证明本轮选定文件的当前输入/已知形状，不证明未知、编码、Git历史或全盘安全。
- [ ] 最终 source、公开 seed、模型副本和工具指纹清楚；本轮 owned 服务已停、临时标签页关闭，用户3021未动；失败数据库和日志保留。

### 交付文件

必须产出下列路径，使用户只需把 `NEWROOT/reports/results.md` 交给复核者就能找齐材料：

1. `reports/results.md`：完整 NEWROOT 路径、输入/最终指纹索引、A—F状态、准确执行命令及退出码、每门证据、限制/阻塞、下一步建议。先写总裁定，历史结果单独标注。
2. `reports/review.md`：本轮自审、发现和处理，不冒充独立审查。
3. `reports/integration-notes.md`：产品文件白名单 diff、与主仓现有修改的重叠、推荐整合顺序和未通过门；不执行整合。
4. `reports/product-changes.patch`、`tool-changes.patch`：分别相对 A 的输入；非 Git 候选可用逐文件 no-index diff，exit1表示确有差异而非命令故障。
5. `evidence/final-source-manifest.json`、`final-tools-manifest.json`，各轮 command/result/log、取消 case/request_id 索引、API/SQL终态、native/shim身份/退出/清理、保护/扫描与扫描目标manifest。

最终裁定分层，不混成一个“完成”：

- **执行交付完成：** A—F实际工作和证据已交付，失败/未验证项也如实交付；这本身不代表阶段通过。
- **本地限定技术门 PASS：** B/D有效回归、E正式矩阵/存储/native/整次控制器、F保护与扫描均满足；明确不是全法律质量或上线认证。
- **阶段验收待复核：** 若没有另一位未参与实现者复核本轮 product/tool diff和关键原始证据，应保持待复核；不冒称已有独立PASS。用户可另派助手只读审核本报告，不需要它重建全部历史。
- **FAIL / UNVERIFIED / INCOMPLETE：** 对应真实失败、未执行/缺输入、收集/清理不完整；逐项写下一项最小动作，不缩小本书验收标准。

## G. 下一阶段清单：仅准备建议，本书不执行

本地技术门通过且新变更复核通过后，再另立最终候选整合与发布准备任务：

1. 把已验证候选与主仓重叠逐项整合到新的 Git 候选，保留用户六处修改，冻结单一代码/依赖/公开数据对象；经允许后才提交。不能把独立目录的文件称已提交。
2. 在该对象上补可运行的全后端、安全/法律质量门，注明缺失测试输入；复核依赖风险、模型来源及期限。旧10/05复审点已过去，旧候选的风险接受不能自动转移/延期；本轮不直接升级依赖。
3. 真实模型/Agent/text-light/rerank范围、测试样本与费用边界另行确认后验收。此前 key 轮换和rerank调用已有记录，不重复写成“仍未配置”，也不把旧7次HTTP200等同最终链路通过。
4. 推送前核对远端历史、当前及历史凭据、CI触发与目标Linux同源验证；实际 push 是独立发布动作，不由本书触发。
5. 服务器选定后再确定部署方案、真实库备份/恢复验证、TLS/配置/日志/健康检查/回滚演练和小范围试运行。本书不迁移真实库、不选择或购买服务器、不部署。

### 给执行助手的建议

- 先验证 SDK 复用的参数契约，再写 close；关闭缺口和无限建池不能只修其中一个。
- 优先在小型无模型/无数据库测试中得到正确 RED，昂贵联调只在产品和工具稳定后各按计划执行，不用完整重跑代替定位。
- 若六例通过但退出失败，保留“取消子门通过、退出/综合失败”，不要重写旧失败或重新解释为整体成功。
- 每完成一个任务把实际证据与下一步写进 progress.md；进度不靠“已经勾选”推断。
- 不追求本轮解决所有技术债。新功能、UI改版、依赖全面升级、客户端框架、部署都不是当前关键路径；已发现且影响本书契约的缺陷不能以简化为由略过。

## 4. 编制自复核

- 范围与权限：A—F可执行，G仅建议；主仓/旧候选只读，提交/推送/真实库/部署均不包含。
- 版本与证据：保存的历史PASS/FAIL有时间与对象边界；新版工具未native重跑明确；final所有门同源，不累加异版通过数。
- 所有权：单请求流与应用SDK池分离；variant/reload、同步/异步、失败继续关闭、运行中loop均有明确判据。
- 工具假绿：summary分类、显式case、marker、重复/缺失案例、native/shim/控制器分离、未知/强停拒绝绿色均覆盖。
- 简化：复用现有registry/lifespan/并发源与本地工具，不新增框架、schema、依赖或发布步骤。
- 交接：完整输入/运行环境/命令/文件责任/报告入口/停止条件齐全；只能在必要输入可访问且无并行冲突时直接执行，不能把本书当成已有验收结果。
