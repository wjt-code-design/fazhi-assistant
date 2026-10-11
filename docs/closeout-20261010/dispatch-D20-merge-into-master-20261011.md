# 票 D-20：候选与远端历史整合——按实际差异逐项裁决

> **2026-10-11 后续复核：本票暂不逐行执行。** “PR 已合”不能作为解决共同祖先/冲突的前置；正确顺序是私有整合、复验与独立审查、公开前凭据处置、独立分支推送、PR 当前检查、正常合并。§3 的旧分组相加为 98，与旧 96 不一致，禁止用于排工。本次 HEAD `19e296e` 的静态异 blob 数为 99（未重跑 merge-tree）；所有数字必须在实际对象上重核。完整边界见 `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2/reports/owner-review-and-next-actions-20261011.md`。下文相冲突的旧前置/固定数/“同数”要求作废；不修改主仓、refs 或实际历史。

> 台账出处：`reports/decisions-needed-20261010.md` §B 的 **D-20**（Owner 裁「留成独立裁决项：本轮只推 `codex/*` 分支」）。
> 本票**不在本轮执行**：它的前置是凭据轮换 + 分支推送 + PR 已合或已批准。开工前先向 Owner 取那一句授权。
> 路径：候选树 = `C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`；运行根 = `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`。

## §0 三行汇总

1. **形状**（2026-10-11 04:0x，候选头 `5e9bba8` × `refs/closing/remote-master` = `985d53e`）：候选路径 **2706**、远端路径 **2136**、交集 **2136**、**远端独有 0**、候选独有 **570**；交集内同 blob **2040**、异 blob **96**；`merge-tree` 报 **96 条 CONFLICT，全部 add/add** ⇒ 两把尺子吻合（差异数 = 冲突数）。
2. **这两个数会随头动**：台账里 03:0x 那次是 `9e3cfc5` 头上得到的 **94**；本票写完后同一把尺子在本会话又提的三笔之后 = **99**（头 `bffbe1c`，A 路径 2707、B 独有仍是 0、两把尺子仍吻合）⇒ 从 94→96→99 只隔了几小时和几笔提交。**开工时、以及在最终头上都要重跑**（§1 的命令），不要引用本票数字做决策。
3. **成本不是"点几下接受"**：`merge-base` 为空（两树无共同祖先，rc=1 已核），所以这不是常规三方合并，而是**逐文件选边 + 一轮配置/门禁重审**；执行书禁"丢弃改动让合并过去"。

## §1 复算命令（尺子已入库在运行根，随票可跑）

```bash
R=/c/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2
C=/c/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010
EMPTY_TREE=4b825dc642cb6eb9a060e54bf8d69288fbee4904   # git hash-object -t tree /dev/null
# ① 远端真实头（只读，不动任何跟踪 ref）
git -C "$C" ls-remote --heads origin                      # 2026-10-11 读数：985d53e…（rc=0）
# ② 路径/blob 对照（只用 ls-tree，不用 rev-parse ⇒ 不会有"取不到当差异"的假红）
"$R/candidate-envB/Scripts/python.exe" "$(cygpath -w "$R/evidence/merge_trial_blobs.py")" \
    "$(cygpath -w "$C")" HEAD refs/closing/remote-master "$(cygpath -w "$R/evidence/d20-diff-list.txt")"
# ③ 试演合并 + 两把尺子对齐
git -C "$C" -c core.quotePath=false merge-tree --write-tree --merge-base="$EMPTY_TREE" \
    HEAD refs/closing/remote-master > /tmp/mt.out; echo rc=$?   # 有冲突时 rc=1 是预期，不是脚本失败
"$R/candidate-envB/Scripts/python.exe" "$(cygpath -w "$R/evidence/merge_trial_reconcile.py")" \
    "$(cygpath -w /tmp/mt.out)" "$(cygpath -w "$R/evidence/d20-diff-list.txt")"
```

⚠️ 三台已踩过的仪器坑（都已在尺子里修掉，别绕过尺子自己写一遍）：
- **`core.quotePath` 默认开启** ⇒ CJK 路径在 `ls-tree`/`merge-tree` 输出里是八进制转义，`grep -F` 原始路径会假失配（我第一次就得出"3 只差得不明不白"）。
- **`git rev-parse "<ref>:<path>"` 取不到时返回空** ⇒ 会被算成"内容不同"。我第一次用它得出 **100 条差异**，其中 4 条（`.dockerignore`、`.env.example`、`.pre-commit-config.yaml`、`.zcode/plans/plan-sess_*.md`）**两侧 blob 其实相同**。
- **`line.partition("\t")` 会把行尾一起留在 key 里** ⇒ 清单变成 192 行（96 条 + 96 空行）。改 `rstrip` 后重跑，两把尺子才是**逐条吻合**：异 blob **96** = CONFLICT **96**，"差异却不冲突"0 条、"冲突而内容不差"0 条。

## §2 前置（顺序不可换）

1. **凭据已轮换**：在册 13 位裸值仍在候选历史里（`reports/h-ci-and-credentials.md`），普通推必然把那只 blob 上传 ⇒ 轮换是 Owner 的动作，没做完不要开工。
2. **推送的是 `codex/*` 新分支**（天然非 force），合并动作本身才成立。
3. **开工时重取远端真实头**：`ls-remote` 与本地 `refs/closing/remote-master` 必须一致；不一致 ⇒ 用 `git fetch origin <那个 sha>` 只写 `FETCH_HEAD`，**绝不**用默认 refspec 的 `git fetch`（那会顶掉别的会话正在读的 `refs/remotes/origin/master`——本会话已因这件事翻过一次车并留痕）。
4. 在**最终头**上重跑 §1，把新读数写进你的报告开头（旧数作废要就地标注）。

## §3 任务范围：96 次裁决按面分组（2026-10-11 现量，按顶层目录）

| 面 | 只数 | 这面的实际风险 |
|---|---|---|
| `backend/` | **72** | 其中 `backend/tests` 33 只 ⇒ 大头是**判据**不是产品码；选边错 = 门禁被静默换掉 |
| `frontend/` | **15** | 含 `frontend/package.json`（scripts 面）与 `.env.example` |
| `docs/` | **5** | `ADR.md` / `ARCHITECTURE.md` / `PROBLEM_LOG.md` / `capability-matrix.md` / `dispatch-tasks-20260908.md` |
| 配置与门禁 | **4** | `.github/workflows/ci.yml`、`.gitignore`、`CONTRIBUTING.md`、`backend/Dockerfile` |
| 其余 | **2** | `dispatch-output/task1`（未入库实配）、`backend/requirements*.txt` 与 `settings.py` 落在 backend 计数内 |

> 上面第四行刻意点名**门禁会读的字节**：`ci.yml`（步骤与审计轴）、`requirements.txt`/`requirements-dev.txt`（区间即声明）、`Dockerfile`（出厂路径与镜像源回落）、`.gitignore`（忽略面 = 扫描面的分母）。这四只不许"批量取一侧"，要逐只读 diff 再选。

做：
1. 按 §1 在最终头上重跑，拿到新的差异清单（行数 = 冲突行数才继续）。
2. 逐只裁决时**每只留一行记录**：路径 / 选哪一侧 / 另一侧有什么是选中的那侧没有的 / 判据。33 只测试文件的裁决要点是"这条断言在测什么"，不是"哪边新"。
3. 合并结果跑**全量门禁四腿** + `pip-audit` 两根轴 + 前端三条独立腿，读数与候选头逐字对齐；对不齐就指名差在哪条。
4. 合并提交前：`git status --porcelain` 两轴（tracked / 未跟踪）都报数，并核 `git diff --cached --name-only` 确认没夹带别的会话的文件（本仓判例：别人的"工作区快照"提交会把你未提交的文件一并带走）。

不做：
- **不 force-push、不改历史、不绕过分支保护**（红线）。
- **不"丢弃改动让合并过去"**（执行书禁语）：任何一侧的内容若要舍，必须在记录里写清舍掉了什么、为什么可舍。
- 不动凭据（轮换是 Owner 的动作）。
- 不顺手修与合并无关的缺陷；发现就登记成新行，别夹进合并提交。

## §4 判据

1. 差异数 = 冲突数（两把尺子吻合），且"差异却不冲突"= 0 —— 尺子形如 §1 的 `merge_trial_reconcile.py`。
2. 合并后：远端独有文件数 **必须为 0**（今天现量：远端 2136 条路径全部存在于候选 ⇒ 合并不会丢远端文件面）；若这一条翻转，先停下回报。
3. 必需用例和安全/功能门禁不丢失；collected / passed / skipped / deselected + cov 按最终对象逐轴解释。合法新增测试允许改变分母，不以机械“同数”代替行为等价。
4. 实际差异、模式/路径变化和真实冲突的裁决记录完整；不固定要求 96 行。命令退出码非预期时停止，不把空 stdout 算作零差异。

## §5 停止条件

1. `ls-remote` 与本地镜像 ref 不一致，且取回新头后差异数变了 ⇒ 重跑全部分组再动手，别按本票的 72/15/5 排工。
2. 网络读不到远端（TLS rc=35 之类）⇒ **停**（本仓网络轴按天翻，昨天的"读不到"不是今天的护栏，今天的"读得到"也不进护栏）。
3. 某只文件两侧的差异是"同一规则的两份拷贝"（判据漂移），选边解决不了 ⇒ 登记待裁，别硬选。
4. 门禁出现合并引入的红且归因不到具体某只裁决 ⇒ 停，回报。

## §6 交付物与回报

- `<运行根>/reports/d20-merge-20261011.md`：§0 三行 → §1 头上的两把尺子读数 → §2 96 行裁决表（路径/选边/舍掉什么/判据）→ §3 门禁前后对照 → §4 我犯的错 → §5 已知限制 → §6 待裁台账 → §7 证据指针。
- 证据：`evidence/d20-*.log`（`ls-tree` 两份、`merge-tree` 原始输出、对账尺输出、门禁四腿）。
- 回报一句话结论 + 上面读数 + 全部绝对路径。文件一律 **LF**（`tr -dc '\r' | wc -c` = 0）。
