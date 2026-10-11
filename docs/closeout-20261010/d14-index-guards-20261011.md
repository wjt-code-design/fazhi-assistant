# D-14：知识库 CLI 安全改造与本地复核（2026-10-11）

## 结论与范围

Owner 选择 A 后批准本会话执行修订范围。D-14 的**限定本地入口安全验证通过，改动尚未提交**；非部署收尾阶段整体仍 **BLOCKED**。本报告不代表全项目测试、真实模型/语料验收、远端 CI 或发布门通过。

- 主仓：`C:/Users/33393/Desktop/ai-legal-helper`，本轮未写入。
- 候选：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`。
- 分支：`codex/nondeploy-closeout-20261010`；HEAD 保持 `19e296e879ac2ffbb0a862c2c9e595d3c81c8ded`。
- 运行根：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`。本报告、修订票和测试证据仅保存在此处，未镜像入候选文档。
- 修订契约：`tickets/dispatch-D14-index-write-guards-20261011.md` 顶部“当前执行契约”，优先于该票下文保留的历史要求。
- 本轮仅改四只 CLI、必要共用守卫及一个新增测试文件；不修改 D-34、依赖、schema、真实配置或数据。不提交、合并、推送、部署，不启动应用/容器，不调用真实模型。

主仓最后只读现量仍为 588 条状态（21 tracked dirty、567 untracked），不能称其干净。候选目前 6 条 tracked 修改、2 个 untracked 测试文件：其中 `main.py` 与 `test_agent_turn_compensation.py` 是原 D-34 成果，本轮字节未变；余下 5 个脚本和 `test_index_cli_safety.py` 属于 D-14。Git 索引为空。

## 实现与使用变化

| 文件（候选 backend 下） | 当前行为 |
| --- | --- |
| `scripts/import_docs.py` | 默认预览；`--write` 才导入/删除，`--dry-run` 与其互斥。初始化前要求显式目标；延迟运行依赖；`--dir` 真正用于打开选定文件，修复旧版“枚举选定目录却从默认目录读取”的问题。保留 hash 幂等、seed 取代与原校验。 |
| `scripts/backfill_time_meta.py` | 默认预览；显式 `--write` 回填。补缺键时保留其他元数据；用 `.get()` 修复缺键产生 KeyError 的路径。 |
| `scripts/chroma_dir_guard.py` | 保留旧固定目标 `assert_matches`；增加动态目标 `require_explicit_target` 与独立评测 `isolated_chroma`，不以恒等比较冒充守卫。 |
| `scripts/eval_chunking.py` | 在私有临时知识库运行原合成夹具对比，退出/异常均走行级清理；不读取外部知识库。 |
| `scripts/verify_new_law.py` | 在私有临时库验证合成条文，移除显式 dotenv 加载；异常/退出也清理；原检索与幂等判据未放宽。 |
| `tests/test_index_cli_safety.py` | 40 项：真实子进程入口、真实合成 Chroma、模型边界替身、守卫负例及四种退出路径。 |

操作口径：

1. 导入/回填**预览也必须显式设置非空 `CHROMA_DIR`**。Chroma 初始化自身可能建目录、collection 或持久化基础文件，所以“默认预览”仅承诺不执行业务导入/删除/元数据更新，不承诺文件系统只读。
2. 目标在调用时的 cwd 正规化为绝对路径；已加载的 rag_chain 绑定不同目标时拒绝，要求独立 CLI。内部库操作函数仍保留现有测试注入接口，不新增第二套业务实现。
3. 四脚本的纯导入和 `--help` 不加载运行服务、不读取 dotenv、不建库、不改 cwd。导入/回填的入口解析与目标保护先于输入读取和运行依赖。
4. 评测只允许独立进程：settings/rag_chain/retrieval/knowledge_service 若已加载则拒绝。先绑定临时 Chroma、配额、应用 DB，再加载服务；固定本地嵌入、关闭云 rerank、零云配额、HF 离线。
5. 自审发现 Chroma/Pydantic 的 Settings 会隐式查找 cwd 下的 `.env`。因此评测运行期暂时进入**自己新建的临时工作目录**，并在 finally 恢复 cwd 和被覆盖环境；不能仅用“删除 load_dotenv”证明没有配置读取。此行为不适合嵌入运行中的 Web 进程，入口预加载拒绝正是其边界。
6. Windows 上 Chroma 文件锁可能使临时目录残留。正常返回、RuntimeError、SystemExit(0/1) 都尝试清理并提示残留绝对路径；进程结束后可按路径核对再清理。**不声称所有目录已经物理删除**；本轮未递归删除任何实际库。

调用示意（说明用，未对真实目标执行）：先将 `CHROMA_DIR` 配置为已核准目标，运行 `python scripts/import_docs.py --dir <输入目录>` 或 `python scripts/backfill_time_meta.py` 预览；确认输入与目标后另获写入授权，再加 `--write`。评测脚本自行选择临时目标，不能用它给生产库补数据。真实入库仍需备份/恢复验证与具体授权。

## 最终同版证据

以下 XML/runner 均在运行根 `evidence/`。通过数不是覆盖率；定向/邻域没有被称为全项目测试。D-14 40 项已包含在 208 项内，不能相加；邻域 24 项是另外的既有病例。

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| 最终 D-14 + D-34 隔离回归 | **208 passed / 4 deselected，rc=0，91.59s** | `d14-d34-closeout-20261011.xml`；D-14 40 + 原 D-34/邻近 168 |
| 既有导入与固定守卫邻域 | **24 passed，rc=0，27.50s** | `d14-neighbor-isolated-20261011.xml`、`d14-neighbor-runner-20261011.py` |
| 异常出口残留提示，先红后绿 | 3 failed / 1 passed → 4 passed | `d14-cleanup-warning-red-20261011.xml` / `d14-cleanup-warning-green-20261011.xml`；后续 cwd 改造前版本 |
| 隐式 dotenv 读取复现 | **2 failed，rc=1** | `d14-implicit-dotenv-red-20261011.xml`；真实依赖尝试读取调用目录内的**合成** `.env` 被审计钩子拒绝，未读取实际配置 |
| 临时 cwd 四出口，先红 | **4 failed，rc=1** | `d14-runtime-cwd-red-20261011.xml`；正确失败在未进入临时 cwd |
| dotenv + cwd 四出口，修复后 | **6 passed，rc=0** | `d14-runtime-cwd-green-20261011.xml`；两只真实 CLI + 四种退出 |
| Ruff lint 全 backend | rc=0 | envB `ruff check --no-cache .`，最终控制台结果 |
| Ruff format 全 backend | rc=0，285 files already formatted | envB `ruff format --check --no-cache .`，最终控制台结果 |
| 常规 mypy | rc=0，74 source files | envB `mypy .`；配置默认排除本次 5 只脚本，不以该绿替代脚本验证 |
| 本次 5 脚本显式 mypy | rc=0，5 source files | 明确点名 5 只脚本；保持仓库既有类型检查强度，未额外承诺检查所有无注解函数体 |
| Diff 空白检查 | rc=0 | 候选 `git diff --check` |

测试隔离：子进程使用环境白名单与专属路径，禁止打开 `.env*`、候选 app.db 与实际数据目录，阻断 socket 网络连接；只替换 HuggingFace 模型加载边界为既有 FakeEmbeddings，Chroma、脚本与相关服务逻辑真实运行。不加载应用 conftest 或实际模型缓存。邻域 runner 另外绕过既有测试和 Chroma Settings 的 dotenv 读取，保留安全审计钩子；这是测试适配，不是生产代码改动。

### 反证与中间失败的归因

- 原入口红证据：`d14-entry-red-20261011.xml`，14 failed / 6 deselected，失败发生在不应提前加载的运行服务/配置入口。
- 固定旧四脚本反事实：`d14-script-baseline-counterfactual-20261011.xml`，23 failed / 1 passed / 10 deselected；只替换内存中的四脚本，不是完整项目 baseline。此证据中的清理腿曾被提前配置读取失败遮挡，**不能单独证明清理断言有效**。
- 已补 `d14-mutation-runner-20261011.py`：仅编译内存源码，磁盘产品不替换，替换位置必须唯一。五组 `d14-mutation-*-20261011.xml` 分别为 absent-blank **4 fail**、bound **1 fail**、relative **1 fail**、preloaded **4 fail**、cleanup **2 fail**。
- 守卫负例分别红在未抛拒绝、绝对路径不符或过晚初始化；预加载 rag_chain 那条被次级目标守卫拦截，仍因不是入口拒绝而红。清理变异只移除 finally 中行级清理调用，两只脚本先经过注入查询故障、保留外部 sentinel，随后因临时库仍有 **16 / 4 条**而在空库断言失败，补足 B3 鉴别力证据。
- 初期测试适配失败曾包括 Windows 子进程编码、环境白名单中的 SystemRoot、Pydantic 隐式 dotenv。保留原 XML：`d14-cli-green-first-20261011.xml`（14 fail/6 pass）、`d14-cli-env-fixed-20261011.xml`（18 pass/2 fail，后两项为真实回填 KeyError）、`d14-neighbor-20261011.xml`（13 fail/9 pass/2 error，配置读取被阻断与编码适配问题）。这些不是最终门结果，也没有被覆盖成绿。
- 202 项、206 项综合绿是测试增补前的中间版本；最终取 208 项文件，不能引用旧计数冒充同版验收。

### 重要限制：安全通过不等于检索质量通过

最终综合 XML 记录合成测量退出码：`eval_chunking=0`、`verify_new_law=1`。FakeEmbeddings 只验证连接、写入和隔离，不能替代真实 BGE 检索评测。

`verify_new_law` 原判据仍有失败；没有把预期改成“能退出就通过”，也没有篡改日期/幂等逻辑凑绿。安全测试有意接受测量码 0/1，但必须证明目标隔离、禁止配置/网络访问、合成条文清理及环境恢复。本轮不关闭“真实检索质量/语料版本幂等验收”；后续应在另行批准的独立模型/合成语料验收中分类复现原失败，不能据此自动修改生产法律规则。

未运行：完整项目 `pytest -m 'not slow' --cov...`、全项目覆盖率、前端/浏览器、容器、最新在线依赖审计、真实模型、真实语料恢复、凭据值扫描、远端操作/CI。原完整门只描述旧对象，不能给本次 dirty 候选兜底。

## 两轴复核与最终版本

已按代码审查规范做独立 Spec/Standards 两轴：Spec 找出的 Windows 异常出口提示 P2 已修复，Standards 找出的新增守卫与清理 B3 反证缺口已补。执行会话另发现并修复隐式 dotenv 入口；最终变动经两轴只读复核，均未发现未关闭的确定问题。Spec 独立复算最后 6 项通过；Standards 独立复算最后 6 项通过（11.17s）且前后 hash 一致。两轴与执行使用同一 envB 工具链，不冒称第三方环境复现。

本轮未增加通用生命周期框架、依赖或 schema；共用保护限于现有守卫模块，局部 finally 管住临时状态。不以减少代码量为理由删安全检查。

最终 SHA-256（若任何文件再改，须重新验证，不以 HEAD 未变代表源码未变）：

```text
scripts/chroma_dir_guard.py   102AF10DF777D15BC0C01E3A7A4B135D449CE784B2ADC22E8C64EB1F8DE52398
scripts/import_docs.py        26A4705231CD411A3082A89341243A0C92F4910065C3F00687D3AE3273907912
scripts/backfill_time_meta.py E73C658EDD06887DDA83681745CA3BBF08E72EAEDB87D9B5B0E473E87EEE58F8
scripts/eval_chunking.py      12608E19BE6D4BABFEC945E668FB98A75989CF4D828972FF95281DAA6BB6D94A
scripts/verify_new_law.py     98B1856996AD82BE57FF9D0F6BC0F568E654368A7C25EA70D9AC8D456600D7FD
tests/test_index_cli_safety.py DB757A074BB96FCE3587537BA45EBB4B3EE59D99AE1DAA3CE337643FAE9FC82C
```

D-34 原锚定保持不变：`main.py=88E035318A0264D1E59B33E2D8402A1A05C3163E6B5ED1901D8632B3F11636D5`，`tests/test_agent_turn_compensation.py=2CC8A49A42554242ADC8F1E47AFDB4619E0F120EC17C4530BDECECAE0DED8A77`。

## 复算入口与后续顺序

统一解释器：运行根 `candidate-envB/Scripts/python.exe`；Ruff 同目录。cwd 为候选 `backend`；不要换成主仓或共享 venv，不要加载真实配置。最小独立复算：

```powershell
$python = 'C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/candidate-envB/Scripts/python.exe'
Set-Location 'C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend'
& $python -B -m pytest --noconftest -p no:cacheprovider tests/test_index_cli_safety.py -q -o junit_family=xunit1
```

综合回归以 `--noconftest -p no:cacheprovider -p test_agent_turn_compensation` 加载既有隔离夹具，并先把 `tests` 放入 sys.path；测试文件为 D-14、test_agent_turn_compensation、test_cancel_boundaries、test_stream_cancellation、test_agent_state_machine、test_agent_budget_terminal_edges、test_agent_chat_integration。排除的四个名称模式：chat_live_agent_selection、forbidden_agent_failure、fallback_to_fast_path_requires、conversation_history_coverage_projection；这四条需要不同的完整应用环境，不算通过。

后续优先接收并独立审查 D-3 依赖迁移票的结果，不能仅因风险 ID 变少就直接替换整栈；迁移/整合后再建安全私有副本，跑包含本次病例的完整门，保留新增/跳过原因，不能要求计数机械等于旧版。D-34 与 D-14 未提交改动须按归属审阅后再决定分笔提交。

凭据实际失效、公开内容范围、D-20 历史整合、当前对象远端 CI、真实模型/语料与专业审签的缺口仍以 `owner-review-and-next-actions-20261011.md` 为准。本次不扩大这些动作的权限，部署始终不纳入。
