# T7 候选 manifest（post-C01fix）—— 2026-09-10 重采

采集时间（UTC）：2026-09-10T06:24:39.357906+00:00
采集方式：Git Bash `git rev-parse HEAD` / `git status --porcelain` + Python hashlib SHA256

## 这份 manifest 为什么存在

T7 预登记用的 `t7-run12-manifest.json` 是在 **C01 修复之前**采集的，其 `dirty_files_sha256`
已不能锚定当前候选（`controller.py` 新增改动、`test_agent_chat_integration.py` 已漂移）。
按项目方法论（T0 manifest："脏改动就地保留，未 commit、未 stash、未 reset"），
**修正候选的正确做法是重新采集哈希，而不是 git commit**——本文件即该重采结果，**取代**
`t7-run12-manifest.json` 中的 `dirty_files_sha256` 用于候选锚定。

## HEAD 与工作区

- HEAD：`ebe82e2bda26185236d50afd780cfb48c7c5e946`
- 分支：`master`（工作树**有意保持脏**，不 commit / 不 stash / 不 reset）
- tracked 修改（13）：
  - `backend/agent/controller.py`
  - `backend/agent/runtime.py`
  - `backend/agent/service.py`
  - `backend/agent/writer.py`
  - `backend/observability.py`
  - `backend/scripts/gate2_runner.py`
  - `backend/tests/test_agent_chat_integration.py`
  - `backend/tests/test_agent_controller.py`
  - `backend/tests/test_agent_gate.py`
  - `backend/tests/test_agent_resume.py`
  - `backend/tests/test_agent_runtime.py`
  - `backend/tests/test_agent_writer.py`
  - `docs/v2-optimization-execution-taskbook-20260909.md`
- 关键未跟踪源码/测试（4）：属候选的一部分，列出并锚定，**不 git add**
  - `backend/scripts/review_sidecar.py`
  - `backend/tests/test_agent_coverage_loop.py`
  - `backend/tests/test_gate2_runner.py`
  - `backend/tests/test_review_sidecar.py`

## 候选代码 SHA256

| 文件 | SHA256（全 64 位） | 角色 |
|---|---|---|
| `backend/agent/controller.py` | `35f8e9c2592f27cf15e64b0b6c7ea6e536692709598f004f56b72a4a87b01fa0` | 本轮编辑 |
| `backend/agent/runtime.py` | `274e8f2ef0fc085e8eb70dec26b2044ee7793421f1feb4ba93a4e7771cf98f30` | 本轮编辑 |
| `backend/agent/service.py` | `35791c20377b087fd65d017eb86caf16f714518ffbc31f3322cc8078b0e5666c` | 本轮编辑 |
| `backend/agent/writer.py` | `fd24dd16bcf58a71ae8a6576b9214c4aef52724cbc1bc6ff78ee2458022f4501` | 本轮编辑 |
| `backend/observability.py` | `710f2820e31b23958eab8c9f307dd9ff9e9e8ce8864f38bda4e8ec88fa23c8ff` | 本轮编辑 |
| `backend/scripts/gate2_runner.py` | `21dfa8f2d70718021b3f353837201862f70e3779f8c11c7f6b2881f22d2798f1` | 本轮编辑 |
| `backend/tests/test_agent_chat_integration.py` | `773e6f06c5cec49f43672a16ee8119b79452fb98fd1c0678b15ea024ddefcedd` | 本轮编辑 |
| `backend/tests/test_agent_controller.py` | `ec127d47d19e104ccb81872c8b324165efe64cee69444a71a66796e51835d7ac` | 本轮编辑 |
| `backend/tests/test_agent_gate.py` | `cd3a5c8569a4a5ca90fc51c9991d4e5124a3053a605df6be33c0acb199f443f2` | 本轮编辑 |
| `backend/tests/test_agent_resume.py` | `349ff43e91445fac23ea691646a5663653fe7f52e8e8d19d292e552041179868` | 本轮编辑 |
| `backend/tests/test_agent_runtime.py` | `bd831d272dea123f2f5094586c9e698a133a8973a593ede0bd5da5db2d6b9b16` | 本轮编辑 |
| `backend/tests/test_agent_writer.py` | `81cd40a7f21f1ffb76416861ffe11beace1af2c3a24df152e398a2c000260250` | 本轮编辑 |
| `docs/v2-optimization-execution-taskbook-20260909.md` | `ee2884cb18c411e35d8af6a7bf6dcfcf7c2b69285575a72bfc37f1f7f1fb01b2` | 本轮编辑 |
| `backend/scripts/review_sidecar.py` | `85c16360536cff6d0b6b1653e18949b83abfcc6a1d07a2d9ba6416eaa601e417` | 未跟踪（候选的一部分） |
| `backend/tests/test_agent_coverage_loop.py` | `1dbeba7aa722dcad7f79420f6acd141e51e0e8f7ec15877a9e46555ac457192c` | 未跟踪（候选的一部分） |
| `backend/tests/test_gate2_runner.py` | `17b23c0d717ce43cd38a13bc010d8f9c4f145621acdaad3b340a070bc0ce6b67` | 未跟踪（候选的一部分） |
| `backend/tests/test_review_sidecar.py` | `1998a130482cf23f738c99d3151325dd3e987f7ad22938b4b8282c14497c2cf6` | 未跟踪（候选的一部分） |

## 冻结物 SHA256（本轮不得变化）

| 产物 / 文件 | SHA256（全 64 位） | 说明 |
|---|---|---|
| `backend/agent/verifier.py` | `47b37a0a421eaa2c8a5d8ce5e8a369d77010a4f9df515aea7e0cd8002c679a2a` | 判定逻辑 |
| `backend/agent/chat_integration.py` | `f05c43c33b7d1e53e80bce69af4d4e78bee4c9a799a893aedef571f5bd4139f9` | equality guard / CAS / ownership |
| `backend/agent/state_machine.py` | `9de7c35f3543e749aaac1c034ac652fc73e2d5ee7c4ec90bf96ff2c4ff51c0bb` | 状态机 |
| `backend/agent/repository.py` | `57c1c00dc00df76cb290c36e0a4b6d5a2aa0720a2bbf9656c0d43ae592af4fe7` | compare_and_save |
| `backend/prompts.py` | `65c5211c81109830be1f1033b86d6679b62ff6461ad28d11548075399d639f7f` | 系统提示词常量 |
| `backend/scripts/gate5_judge.py` | `90487960771dd372b14de2b1cd19bc25048f9baa639e217627ad8242a340b5db` | 冻结判分器 |
| `release-evidence/legal-agent-v1-complex-v1-20260907/frozen-cases-v1.json` | `be281ab275024b2c6199c5c218b42dd77650fd36bbcda51226076c00ff82a4e5` | 冻结题集 C01-C10 |
| `release-evidence/legal-agent-v1-complex-v1-20260907/frozen-fact-ids-v1.json` | `262456b6fd06d2fbe9670570be7eaedeb0bf7a7473db06dc3e2294df66146a73` | 冻结事实 ID |
| `release-evidence/legal-agent-v1-complex-v1-20260907/frozen-round-protocol-v1.json` | `89d8d9167262ae8389f1c4ae0e7d93f76e845aa528587e08ea5fde32e5e1961a` | 冻结轮次协议 |
| `dispatch-output/task1/hidden-cases-v1.json` | `d1f0b1f053b2f4b32db153b08a499467ab36988c4890c60263e03dd300cb752f` | hidden 题集 |
| `dispatch-output/task1/hidden-round-protocol-v1.json` | `e4de149b4bf9eccf0e9d2243f7fdb6789ca38abf709d911399f6997593377eff` | hidden 协议 |
| `dispatch-output/task1/hidden-commitment.json` | `1ae1488c9e693b0e8ae5aee8d1f63267ee906b645acccec55942e21a35984f4b` | hidden 承诺 |
| `dispatch-output/task1/salt.txt` | `51157d68a830b3d5fe7a06785b829281b6e387d9608abf2b7255e0dc791860f8` | salt |

## 与上一份 manifest 的差异（候选 delta）

| 相对 `t7-run12-manifest.json` | 说明 |
|---|---|
| `backend/agent/controller.py` | **新增改动**（C01 修复：`_every_issue_retrieval_attempted` + 幂等转移短路，+64 行） |
| `backend/tests/test_agent_chat_integration.py` | **已漂移**（新增 3 条 C01 回归测试 / `_MultiIssueTransport` 护栏） |
| 其余 12 个 tracked 文件 | 与预登记一致 |

## 本轮实现质量证据（离线，非付费）

- 全量 `tests/`（70 模块）：**903 passed / 0 failed**（`dispatch-output/t2-persistence-20260909/fix-v2-final-junit.xml`）
- agent 17 模块子集：**362 passed / 0 failed**（`fix-v2-agent17-junit.xml`）
- 冻结物复核脚本：`dispatch-output/t2-persistence-20260909/verify_frozen_for_handoff.py`

## 红线（沿用 T0，仍然有效）

- 不 commit / 不 stash / 不 reset（候选 = 脏工作树）
- 不清扫、不 git add `diag/`、`dispatch-output/`、`release-evidence/`、`.workbuddy/`
- 不修改冻结物（verifier / chat_integration / state_machine / repository / prompts / gate5_judge / frozen-* / hidden-* / 历史 sessions）
- 不并行跑共享数据库 / 端口 / 付费账户

