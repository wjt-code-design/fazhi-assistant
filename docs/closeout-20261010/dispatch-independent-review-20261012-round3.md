# 票：10-12 接手轮的独立复核（非实现者腿，两路正交，只读）

**为什么需要这张票**：本轮六笔提交（三笔代码 + 三笔文档）由**同一个会话**接收、复验、集成并写入台账。
执行书 §I 要求独立审查者从候选 diff、原始日志和冻结清单**自行复算**，实现者不得担任 reviewer。本票就是这个缺口。

**对象**：分支 `codex/nondeploy-closeout-20261010`，起点 `19e296e`，终点现读 `git rev-parse HEAD`（写票时为 `673a5ea`，会随入册变动）。
候选 worktree `C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`；运行根 `C:/Users/33393/Desktop/fazhi-nondeploy-closeout-20261010-b4e7a2`。
统一解释器 `运行根/candidate-envB/Scripts/python.exe`（Python 3.11.0）。

**两路必须正交**（在册教训：两路里只有对抗腿产生新发现）
- A 路（复现）：逐颗钉子按给出的命令跑一遍，报"复现成功/失败/命令本身坏"。
- B 路（对抗）：**不许复现我的结论**，只回答三件事——哪条主张的证据撑不住、哪个数或指针已经随头过期、我明确没跑却写得像跑过的有哪些。

**七颗钉子**
1. 全量门：`pytest -q -m "not slow" --cov=. --cov-fail-under=70 -p no:cacheprovider` ⇒ 期望 **2016 passed / 0 failed / 10 skipped / 18 deselected、cov 86.55%、rc=0**；分母闭合要求 collected 轴 **2026/2044**、junit `tests=2026 skipped=10 failures=0 errors=0`。请在**副本树或 `git archive HEAD` 的纯发布物树**上跑，别在候选直接跑；跑前后各记一次候选 `git status --porcelain`，必须都是 0 行。
2. 归因（不要重跑全量）：证明那两只红是 D-34 改接口造成的，而不是本来就红。做法：在起点 `19e296e` 的树上跑**未修的**那两条用例应绿；在当前树把接线修反向还原（`git apply -R` 那份 patch）应红，且红的是同两条同名用例。两次都要点名用例名。
3. `.dockerignore` 修法：不许复用运行根的 10 格矩阵自证。请用另一种独立判据（读 moby `patternmatcher` 对 `**` 的文档语义并做一次你自己的最小构建对照，或对镜像层内容直接检查），回答两问：`**/*.db` 是否仍覆盖上下文根的 `app.db`；有没有把运行时**需要**的文件挡掉（`git ls-files backend/data` 现量 2 只评测件必须仍在镜像里）。
4. 交付==验收：逐只把 `git ls-tree -r HEAD` 的 blob 与 `git hash-object --no-filters` 的盘上值比对，覆盖本轮 11 只代码/测试文件；并核这 11 只里没有 CRLF。
5. 凭据轴（本轮新入册 8 只 + 回灌 6 只）：形状扫描与值级对照要**自带咬得住的正对照**（假 `sk-` 值与 13 位参照值的自匹配）。运行根 `evidence/mirror_precheck.py` 可复用，但你必须自己跑一次红控，否则"0 命中"不算数。**不要读 `.env`，不要打印任何值。**
6. 台账一致性：`python -B 运行根/evidence/ledger_row_audit.py 运行根` ⇒ §A/§B/§C 无跨档重复、并集 1..38 无缺号；`work_log_key_audit.py` 多文件跑"未落正文=无"、单文件（决策台账）缺=0。请挑战 KEYS 本身：本轮有哪些主张**没有**对应 key（尤其 D-35/D-36/D-37 是否被我写成已解决）。
7. 未完成面：对照 `reports/owner-review-and-next-actions-20261011.md` 的 R1–R8，逐条回答"本轮有没有处置记录、处置在哪一只文件的哪一节"。R3 的凭据失效入口现在是否真的落成 D-35 而不是被"已轮换"这句话糊过去。

**只读与红线**
- 不改候选、不改主仓、不改运行根既有日志与报告（新证据一律新文件名）；不提交、不推送、不动 refs。
- 不往 `candidate-envB` 装任何东西（另有会话可能在读它）；需要新依赖就自建私有 venv 或副本树。
- 不跑 `backend/scripts/smoke_citation_fast.py` 与 `smoke_citation_full.py`（二者 `os.chdir` 加 `load_dotenv(".env")` ⇒ 会装真实配置、写真实配额库）。
- 不碰真实库/向量库/媒体/备份，不读写 `.env` 值，不起现役栈，不占 3021/8088，不调用真实模型，不跑 `slow` 与 `real_kb` 腿。
- 本机坑：PATH 上 `~/.local/bin/env` 会吞掉 `env VAR=x cmd` 整条命令并返回 0 ⇒ 用 shell 内 `export` 起进程，并先证明命令真的跑了。
- 在线 `pip-audit` 本轮有意未重跑（D-3 未落地）；你要跑请单独记账，别把它当本轮门禁。

**交付**：一份新报告放运行根 `reports/`（建议名 `independent-review-20261012-round3.md`），每条钉子给"复现命令 + 当场读数 + 判定"；
不替我改台账。若发现我某条主张为假，写清假在哪一句、证据是哪条命令，由我按"就地标注撤回"的规矩处理。
