# 法智：W10 依赖锁落库 + 续跑「独立复核」验收报告（2026-10-19）

日期：2026-10-19（Asia/Shanghai）。

> 定位：本文件是**交付验收**报告（核对一批交付物是否自洽），**不是缺陷清单**。同目录的 `2026-10-19-independent-readonly-audit.md`（R01–R14）与 `2026-10-19-independent-readonly-audit-round2.md`（R15–R25）是**代码缺陷审计 + 修复交接**；本文件与其体裁不同，**编号 / 行号 / 结论不可混用**。

## A1. 范围与对象

- 对象：候选工作树 `.worktrees/nondeploy-closeout-20261010`，HEAD `187174f`，工作区干净。
- 受审改动（3 笔提交）：
  - `c7a381f`：`backend/constraints.txt`（新增）+ `.github/workflows/ci.yml`
  - `b406ab8`：`backend/Dockerfile`
  - `187174f`：`backend/requirements.txt`（仅注释）
- 远端：公仓分支 `nondeploy-closeout-20261018` = 本地 HEAD `187174f`。
- 证据根：run `fazhi-full-closeout-20261018-af101aa9bca543b1a9c21fd0bace9780` 的 `evidence/net/*`。
- 本文件位置：M 仓 `docs/process-archive/reviews/`（**untracked**），不在 run 根 manifest 的扫描范围。

## A2. 方法与独立性

- 「1 主审 + 2 并行独立验证者」：主审跑新鲜命令；两名验证者各自独立复跑同一组声明、互不知晓彼此结论。
- 期望独立性：版本由 pip resolver 决定（非自算）；哈希用独立工具 `Get-FileHash` 与 python `hashlib` **双算**；YAML 用 `yaml.safe_load`；私有符号边界用真实导入 + 真实测试用例。
- 全程未改动任何文件/仓库/远端；未读 `.env`、真实凭据、真实数据库。仅在一个临时目录 `D:\fazhi-caches\w10-audit-tmp\` 下做过差分用副本。

## A3. 新鲜证据表

| 编号 | 声明 | 新鲜证据（命令 → 读数） | 判定 |
|---|---|---|---|
| C1 | 候选 HEAD 与工作区干净 | `git rev-parse HEAD` → `187174ffab1b…`；`git status --short` → 空 | 成立 |
| C2 | 远端 = 本地 | `git ls-remote … refs/heads/nondeploy-closeout-20261018` → `187174ffab1b…` | 成立 |
| C3 | c7a381f 改动面 | `git show --stat c7a381f` → `ci.yml` + `constraints.txt`，2 files +157/−1 | 成立 |
| C4 | constraints 内容 | `Get-FileHash`=python `hashlib` → `F13EAFDC…09E0E6B`；`name==version` 计 136；`torch==2.13.0`（无 `+cpu`）；`+` 命中 0；nvidia/cuda **依赖条目** 0（仅一行注释含 “CUDA” 字样） | 成立 |
| C5 | requirements 未被改版 | 直接钉 24 条全 `==`；`git show 187174f -- backend/requirements.txt` → 变更行全为 `#` 注释、版本行零改动（+6/−1） | 成立 |
| C6 | ci.yml 接线 | `yaml.safe_load(ci.yml)` → jobs=backend/frontend/source-probe；backend `Install deps` = `pip install -r requirements-dev.txt -c constraints.txt` | 成立 |
| C7 | Dockerfile 接线 | 含 `COPY constraints.txt .`；两条 runtime 安装分支各带 `-c constraints.txt`；`backend/.dockerignore` 未排除 `constraints` | 成立 |
| C8 | 离线复解析（Linux-target） | `pip download -r <reqs−jieba> -c constraints.txt --no-index --find-links D:\fazhi-caches\linux-closure <交叉平台标签>` → **rc=0，135 wheels**；含 `langsmith-0.14.11`、`transformers-5.20.1`、`torch-2.13.0+cpu` | 成立 |
| C9 | b406ab8 / 187174f 改动面 | `git show --stat b406ab8` → 仅 `backend/Dockerfile` +9/−2；`187174f` → 仅 `backend/requirements.txt` +6/−1 | 成立 |
| C10 | manifest 冻结读数 | `evidence/manifest.json` `counts` → entries=112、total_bytes=1862651、forbidden=0、walk_errors=0 | 成立 |
| C11 | langsmith 0.14.11 边界 | 隔离探针 venv → `langsmith 0.14.11`；`_cached_sync/async_httpx_client` 均可调用；`pytest --noconftest tests/test_llm_lifecycle.py -q` → **11 passed rc=0** | 成立 |
| C12 | 记录已同步 | `task-status.json` 可解析；`W10.evidence` 同时含 `b406ab8` 与 `187174f` | 成立 |

**两名独立验证者结论**：均为 **12/12 成立、0 反证**（各自独立跑了上述命令）。

## A4. 红能力（差分实测）

同一命令、同一输入，仅把 constraints 的**临时副本**里 `langsmith==0.14.11` 改成 `langsmith==0.0.1`：

- 原 constraints → `Successfully downloaded`，**rc=0，135 wheels**
- 变异副本 → `ResolutionImpossible`，**rc=1，0 wheels**

⇒ 约束确实对解析生效、判据能红（不是装饰）。变异只发生在 `D:\fazhi-caches\w10-audit-tmp\` 的副本上，候选本体未被触碰。

## A5. 审计中抓出的问题（分类）

- **假红**：0 条。
- **判据写错（仪器口径，非产物缺陷）**：验证者在统计直接钉时，首轮正则未覆盖方括号名 `uvicorn[standard]==0.27.1`，得 23 条；改用「非注释非空行」全列后为 **24 条**，与声明一致。属**尺子的错**，已修正。
- **真发现**：0 条（未发现产品侧缺陷）。

## A6. 已知限制（诚实边界）

1. **CI 未跑（本轮结构性阻断）**：公共默认分支 `master` 上的 `ci.yml` **没有 `workflow_dispatch`**，`push` 触发只认 `main/master`，且本地线与 `origin/master`（`985d53e4`）**无共同祖先** ⇒ PR 不可建。故本轮 `-c` 接线**未在任何 CI（ubuntu）上实跑**。本机亦无 `gh` CLI/token，浏览器扩展未连接。
2. **镜像未构建**：`docker build` 因 C 盘磁盘占用 `BLOCKED`（`docker_data.vhdx`）。
3. **非 Linux 真跑**：C8 用交叉平台标签离线解析，**不等于** Linux 真装真跑。
4. **transformers 5.20.1 行为未复测**：其导入需 torch，本轮未在本地行为复测（仅 resolver 一致）；`langsmith 0.14.11` 边界已在隔离 venv 复测。
5. **覆盖边界**：本报告只覆盖上述 3 笔提交 / 5 个文件与本 run 根的对应记录；不含 W06 其它改动，也不代表主目录问题。
6. 另注：`backend/venv` 实为 legacy 环境（`langchain-core 0.1.53` / `langsmith 0.1.147`）；「已测组合 0.14.7 / transformers 5.19.0」对应的是 `backend/venv-new`，非 `backend/venv`。

## A7. 净结论

- 本轮 W10 交付在本轮**可核范围内自洽**：12/12 声明成立、0 反证、红能力差分成立、无真发现。
- 但「**真 CI / 真镜像 / Linux 真跑 / transformers 5.20.1 行为**」四项**未闭合**，解除条件见 A6；不得据此宣称端到端已验证。

## A9. 签核前补记（2026-10-20，供独立审核人一步即签）

> 本节为**日期化补记**，不改写上文任何历史快照读数；A1–A8 原貌保持。补记只反映**本报告口径下**的现态变化，不引入新主张。

1. **快照口径与后续提交**：A1 记录的快照 HEAD 为 `187174f`。此后候选树新增四笔**有意**提交（均为本报告口径下的后续动作，不改写上文任何历史读数）——
   `8b2e79f`（fix(W09): 拒绝公知占位口令，C05 加固；红→绿 8 failed → 40 passed；全量 not-slow 2507 passed / 11 skipped）、
   `b1bfe91`（docs(W10/A6): ADR-019 真 CI 结构性不可行 + 本地等效真实验证替代）、
   `1d36c91`（fix(W09): **本轮独立复核主审抓出的 Medium 项 R-1**——重置入口 `backend/scripts/reset_admin_password.py` 原只比单一 `PUBLIC_DEFAULT_PASSWORD`，未消费 W09-E 加宽拒斥集，`change_me`/`password`/`123456` 仍可经重置入口写回管理员账户；改用单一真源 `auth.is_public_default_password`，并新增 5 条参数化负例；红→绿 6 failed/49 passed → 55 passed；全量 not-slow 2512 passed / coverage 88.58% rc=0。注：红在 `dev-tree` 副本上做，候选本体只落修复）与
   `ee5bfef`（docs(W10/A6): ADR-019 阻断②分支名表述更正）。
   四笔均已推送，远端 tip ＝ 本地 HEAD `ee5bfef`（`git ls-remote` 复核；见 `evidence/net/w13-push-closeout2-ssh443.log`、`evidence/net/w13-ls-remote-closeout2.txt`）。
2. **A7「四项未闭合」的现态**（逐项更新，其余边界不变）：
   - ① **真 CI 未跑** → 改判为**结构性不可行**（默认分支无 `workflow_dispatch`、`push` 只匹配 main/master、与 `origin/master` 无共同祖先致 PR 不可建），以「隔离 venv 逐字复刻 CI 后端作业」的**本地等效真实验证**替代，残余差＝宿主 Windows ≠ `ubuntu-latest`、人工调度；裁记见 `docs/ADR.md` 的 **ADR-019**。
   - ② **镜像未构建** → **已闭合**：`docker build` rc=0，镜像 `fazhi-backend-w12q3:20261020`，3.97GB，断言 `torch CPU build 校验通过: 2.13.0+cpu`、无 nvidia 包、`backend/.env` 未进镜像。
   - ③ **非 Linux 真跑** → **仍开放**（无 ubuntu 宿主；仅离线交叉平台闭包解析，两者不可互替）。
   - ④ **transformers 5.20.1 行为未复测** → **已闭合**：真权重离线探针 `V transformers 5.20.1` / `EMB_BUILT ok` / `DIM 768` / `DETERMINISTIC True` / `SEMANTIC_ORDER_OK True` / `PROBE_RC=0`。
3. **manifest 口径**：A3 表 C10 的 `entries=112` 为当时快照；本批重冻结后 `counts.entries` 变为 **114**（新增证据/票据文件），故 C10 判据应读为**动态引用 `counts.entries`**，而非固定常数。
4. **净结论边界不变**：本报告「在可核范围内自洽、12/12 成立、0 反证、红能力差分成立、无真发现」的净结论仍成立；未闭合项由**四项收敛为一项**（非 Linux 真跑）。新增的诚实项（A2 交「未做」、A3 只闭合「可构建」不含启动镜像）已在 run 根台账 `tickets/closeout-continuation-20261020.md` 登记。**仍不得宣称端到端已在 CI 上验证。**
5. **A5 裁定**：`docs/process-archive/reviews/*.md` 在候选树与主仓均 `tracked=0`（非交付索引），故**保持原貌、不入库、不归一化行号**（改写会破坏审计原貌这一证据属性）。

## A8. 独立签核位（他人不得代签）

- 独立审核人签字：haimeng
- 签核日期：2026-10-21（锚定 `187174f` 快照；A3 中 C1/C2 为快照读数非现态）

> 本报告由本轮主审整理，两名验证者的复跑读数已并入 A3；签核栏已由指定独立审核人于 2026-10-21 落笔（见上）。本报告的完成仅指本轮复核材料已整理，不代表「非 Linux 真装真跑」这一项已消除（其余三项现态见 A9.2）。
