# P1（D-3 langchain 1.x 迁移）：干净安装与新栈门禁（2026-10-12）

**一句话结论**：迁移在**干净安装 + 纯发布物树**上跑绿（与旧栈**逐字同读数**），但**尚未落地到候选**——落地被 D-44（候选工作树在 04:33 被别的会话整片重写）挡住，等 Owner 裁恢复方向。本报告不是"已上线"，也不是"阶段完成"。

## 1. 固定对象与边界

- 候选 worktree：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`，分支 `codex/nondeploy-closeout-20261010`。**开工时 HEAD 现读**（本文件写出时 `d2684ba`；写作期间我另入了 docs 笔，头会动，别引用我这个字面量）。
- 运行根：`C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`；本轮工作目录 `p1-migration-20261012/`。
- 新解释器 **envD**（干净私有 venv，基座 = 系统 `Python 3.11.0`，不继承任何 site-packages）。**没有动** envB / envC-1x / 宿主 `backend/venv` / 生产容器 / compose 栈。
- 本轮**未提交产品字节**：`requirements.txt` 的迁移版只存在于 `p1-migration-20261012/requirements-migrated.txt` 与副本树；三只迁移测试只存在于副本树。未推送、未合并、未读 `.env` 值、未连真实库、零真实模型调用。
- 测试进程环境按在册配方：假 JWT/LLM 值、六根出网轴全指 `127.0.0.1:9`、`EMBEDDING_PROVIDER=local`、`HF_HUB_OFFLINE=1`、`PYTHONHASHSEED=0`、`PYTHONDONTWRITEBYTECODE=1`；不跑 `smoke_citation_*`。

## 2. 读数（每条都给我自己跑的命令，不引用上一轮的数）

| 检查 | 读数 | 证据（`p1-migration-20261012/`） |
|---|---|---|
| envD 干净安装 | STEP2/STEP3 rc=0；`pip check` = No broken requirements found；freeze 164 行 | `envD-build.log`、`envD-freeze.txt` |
| 解析出的关键版本 | langchain-core 1.6.9 / langchain-openai 1.7.0 / langchain-chroma 0.2.3 / langchain-huggingface 1.2.3 / langchain-text-splitters 1.1.3 / openai 2.54.0 / langsmith 0.14.7 / chromadb 0.4.24 / **numpy 1.26.4** | `envD-build.log` STEP5 + 与 `reports/d3-langchain-migration.md` §1.1 的表逐版相同 |
| torch 单变量替换 | `2.13.0` → **`2.13.0+cpu`**，freeze 差集**只有这一行**（`< torch==2.13.0` / `> torch==2.13.0+cpu`）；镜像同式防呆通过（`+cpu`、`torch.version.cuda is None`、无 `nvidia-*`）；`pip check` 仍零红 | `envD-torch-cpu.log`、`freeze-before/after-torchswap.txt`、脚本 `swap_torch_cpu.sh`（照 `backend/Dockerfile:58` 的两发形状，不再自造 `--index-url`） |
| 新栈全量非 slow（纯 HEAD 树） | **2030 passed / 0 failed / 10 skipped / 18 deselected**，cov **86.57%**，rc=0，268.02s；junit `tests=2040 failures=0 errors=0 skipped=10` | `envD-headtree-full-20261012.log` / `.xml` |
| 与旧栈基线的关系 | 旧栈（envB，同 HEAD 纯树）在册读数同为 2030/86.57%/collected 2040-2058 ⇒ **换栈不改任何用例数与覆盖率**；collected 轴复算命令 `pytest --collect-only -q -m 'not slow'` | 对照 `evidence/integration-gates-backend-pass3-20261012.log` 与我这轮 archive 树日志 |
| 静态腿（envD） | ruff check rc=0；ruff format --check rc=0（286 files）；mypy rc=0（74 source files） | `envD-static-20261012.log` |
| 审计·解析轴 `pip-audit -r` | 1 只有通报 = **chromadb 2 条**（`PYSEC-2026-3813/3814`，`fix_versions` 为空）；errors=0；rc=1（有通报即 rc=1）⇒ **langchain 族 13 个主 ID 归零**，与 §E 的 15 = 13 + 2 分母对上 | `audit-resolved.json` / `.log` |
| 审计·实装轴 `pip-audit --local` | 164 只被审；2 只有通报：**chromadb 2 条** + **pip 22.3 的 14 条目 / 7 个不同主 ID**（fix 线含 23.3/25.3/26.0/26.1/26.1.2/26.2/26.2.0）；distinct 主 ID 合计 **9**；errors=0 | `audit-local.json` / `.log` |

**审计两轴必须分开读**：`--local` 看得见 `pip` 这类环境自带工具，`-r` 看不见；而 CI 的 `pip-audit -r requirements.txt` 只看声明轴（在册限制，本轮再次命中）。**setuptools 在 envD 是 84.0.0、0 通报**——上一轮 envC 那 4 条构建工具通报在干净安装上自然消失，但只在 Windows/envD 这一套上成立。

## 3. 落地前置（测出来的，不是推的）

- **`requirements.txt` 与三只迁移测试必须同一笔提交**。证据：把迁移后的三只测试配**旧栈**解释器（envB，langchain-core 0.1.53）单跑 —— `test_llm_lifecycle.py` **收集期即 `ModuleNotFoundError: langchain_openai.chat_models._client_utils`**；`test_stream_cancellation.py` 15 failed / 27 passed；`test_cancel_boundaries.py` 1 failed / 13 passed。分开落必有一边红。
- 落地后 **envB 不再是可跑全套的解释器**，它降级为"旧栈历史基线"。⇒ 回退方案是 **revert 那一笔提交**，不是"换回 envB 继续跑"。这条要写进合并/发布卡，否则下一位会以为有第二条退路。
- **D-45（版本窗口 vs 私有 API）**：那只测试 import 的是新 SDK 的私有模块路径，而声明窗口 `>=1.1.14,<2` 比已测组合宽。处置按推荐：**不吞 ImportError、不加 skip 凑绿**，在 requirements 注释写死"已测组合 = core 1.6.9 / openai 1.7.0 / langsmith 0.14.7；跳窗若在收集期炸 ⇒ 视为支持边界外另开票"。

## 4. 我自己这轮犯的错（都靠读数当场暴露）

1. **副本树建错**：为图快只拷了 `backend/`，漏掉仓库根的 `release-evidence/` 等目录 ⇒ 第一趟新栈跑出 **86 failed**，真因是 `scripts/gate2_runner.py` 在 import 期读 `release-evidence/…/frozen-cases-v1.json` 拿不到文件。这条坑在册教训里明写着"tracked-only 建树要带 release-evidence/dispatch-output/task1/data"，我又犯一次。**那 86 条红因此作废**，改从 `git archive HEAD` 出树（2724 只 = tracked 2724 只，逐只对哈希）重跑。
2. **假 0 又踩同一个键**：我第一版审计解析器读 `vulnerabilities` 键 ⇒ 打出"packages_with_hits=0"，而 `rc=1` 和日志里"Found 2 known vulnerabilities"当场矛盾。pip-audit 的键是 `dependencies[].vulns`（npm 才用 `vulnerabilities`）——这条在册已经记过一次，本轮再记一次：**报 0 之前必须先跟 rc 对质**。
3. **给工具传了不存在的旗标**：`pip-audit --no-cache-dir` 不存在 ⇒ 两腿 `rc=2` 用法错误。我先把它读成"审计跑完了"才发现尾巴是 usage error；重跑后才有条目数。
4. **自造安装命令前没读仓库那条命令的注释**：`--index-url` 装 CPU torch 失败（缺 `flit_core` 退回 sdist），而 `backend/Dockerfile:22-34` 早已写明同一根因与"为什么用 `--find-links`"。改成照抄仓库的两发形状后一次成功。

## 5. 现在停在哪、下一步

- **停**：新栈门已绿，但**不落**。阻塞 = **D-44**（候选工作树 04:33 被整片重写：1486 只脏、31 只差内容且逐只等于主仓工作树版本、0 只等于 HEAD；我的提交在 HEAD 里完好）。我拒绝往那棵树上写，因为一旦写，就无法区分"我的改动"与"别人的旧内容"。
- Owner 三个选项：① 由我从 HEAD 重刷工作树后再落（推荐）；② 先问那个会话；③ 用 plumbing 从 HEAD 直接造提交（不碰工作树，但别的会话仍读旧树）。
- 落地那一笔的内容已经准备好：`requirements-migrated.txt`（相对 HEAD 只差那 7 处：5 个窗口 + `openai>=2.26,<3` + `numpy>=1.26.4,<2` + 注释）与 `d3-current-review-20261011/migration-tests-reviewed.patch`（3 只测试，`git apply --check` 在当前候选 rc=0）。
- 落地后仍需的独立腿（本轮**有意未跑**，不记成通过）：`docker build` 全量（镜像里的 Linux `+cpu` 轮与本机的 win_amd64 `+cpu` 不是同一个对象，审计对 `2.13.0+cpu` 的识别本轮 `version=None` ⇒ **不能声称已审到生产那个 wheel**）、前端腿（本轮零前端改动）、`slow`/`real_kb`、真实模型（P3）。


## 6. 落地后补记（同轮，Owner「按推荐」批准恢复＋落地）

- 恢复：重刷前把 31 只内容差异文件整份备份（`incident-20261012-worktree-overwrite/pre-restore-backup/`，31 只 / 689,835 B），
  再 `git checkout -- .`；重刷后 `porcelain=0`、untracked=0，`backend/.dockerignore` 的 `**/*.db`+`.ptmp*` 与脚本的 `import getpass` 全部回到修好的状态。
  **谁做的那次覆盖仍未查明**，我只恢复了树，没有替任何会话认领。
- 落地：`requirements.txt`（+15/−5：五个窗口 + `openai>=2.26,<3` + `numpy>=1.26.4,<2` + D-45 支持边界注释）与三只迁移测试**同一笔**，提交 `0ce047d`。
- 复验两趟逐字同读数：落地前副本树、落地后 `git archive HEAD` 纯树，都是 **2030 passed / 0 failed / 10 skipped / 18 deselected、cov 86.57%、rc=0**，
  collected 轴 **2040/2058**，junit `tests=2040 failures=0 errors=0 skipped=10`；静态腿 ruff/format/mypy 全 rc=0。
- 交付身份：4 只文件 `rev-parse HEAD:<path>` == `hash-object --no-filters`，CR=0、NUL=0、`git diff --check` rc=0。
- 新基线绑定 envD：envB 自此只是旧栈历史基线；回退＝revert `0ce047d`。
- 未闭合：CI 审计步预期红（D-46，成因＝chromadb 2 条无修复版）、`docker build` 与生产 Linux `+cpu` 轮未审、前端腿未重跑、`slow`/`real_kb` 未跑、
  真实模型验收（P3）待你给配额与审签口径；D-42 只做了 runbook 前置、`isatty` 代码前置留下一轮；D-43 未动。
