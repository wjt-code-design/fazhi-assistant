# 任务工作汇报：A｜报告对账与 T7 依赖分案（2026-09-27 深夜）

**派单**：`docs/assistant-briefs/next-phase-A-docs-t7-20260927.md`
**负责文件**：`docs/h1-law-version-collision-tickets-20260926.md`（下称"票据"）、
`docs/progress-handoff-report-20260925.md`（下称"汇报"，按派单只动历史证据段，最终阶段验收段落留给 E 助手）、
新建 `docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md`（下称"T7 分案"）
**执行**：本会话，2026-09-27 深夜；八项复核 → 两文档更正 → pip-audit 双模式 → T7 分案 → 双轴自评审与修复。
本汇报文件系 Owner 指示补写（超出派单三文件写区的新建件，其余写区纪律未破）。
**边界遵守**：全程未提交、未 push、未部署、未轮换凭据、未写任何真实库；未改 `requirements*.txt` 与任何代码；
未 `git add`/`stash`/`clean`/`checkout --`；不打开不输出 `.env` 值；grep/find 排除 venv、`.worktrees/` 与
dispatch-output 下 copytree/beforetree/aftertree/pretree/copybase 假树，未读任何 `laws_extra*.json` 副本。

## 0. 一页汇总

按派单把 09-27 一致性评审（`dispatch-output/report-consistency-review-20260927.md` §3）的**八条问题逐项复核，
全部本机复现成立，无一照抄**，据此更正两份旧文档 **11 处**（每处带"09-27 对账"标记；有历史意义的旧数字
一律标时点保留，不伪装成当前值）。`pip-audit` 双模式 **rc=1＝有通报**（不是网络失败，两次均完整出结果）。
T7 分案给出 **pypdf / FastAPI·Starlette / Chroma 三条可执行升级路径**（每节五要素齐备，三处"未核"明写）。
随后按 `code-review` 双轴自评审：Standards 轴（子代理）3 硬违规候选＋4 判断题，**核实后 5 处修复**（其中
1 条实为并行竞态、降级为时点标注）；Spec 轴子代理两次因验证码服务超时未能派发，降级为内联执行，零硬发现。

**工作树是活的**：对账期间 `CONTRIBUTING.md` 被另一会话改为"24 项"含明细并新增未跟踪测试
`backend/tests/test_smoke_citation_assertions.py`（17 passed）——归属未核，A 全程只读未碰。本文所有哈希只对
A 的编辑时点负责。

## 1. 做了什么（按顺序）

| # | 动作 | 证据 |
|---|---|---|
| 1 | 记录基线：`git rev-parse HEAD`＝`7eda4bb`（全程未动）＋两文档改前 `git diff` 与 SHA256 | 改前哈希见 §6 |
| 2 | 八项逐条复核（不照抄）：产物 JSON、`git show 4439519/5d479e9`、quota 五份同名库 stat、票据脚本逐字实跑、`--collect-only` 现量、EXITS 计数、`56696c5:104` 形状计数、八站点 grep | §2 各条 |
| 3 | backend 下 `pip_audit -r requirements.txt`（模块入口可用）＋环境模式＋`pip check`＋`pip index versions`×4 | §4 |
| 4 | 新建 T7 分案（三节×五要素＋共同前置＋未核节） | `docs/assistant-briefs/t7-dependency-upgrade-options-20260927.md` |
| 5 | 两份旧文档 11 处更正（全部带"09-27 对账"标记） | §3 |
| 6 | `git diff --check` rc=0；精确文件 diff 复查（§9.11 与汇报尾部逐字未动，E 助手段落未代写） | 交付判据项 |
| 7 | 双轴自评审：Standards 子代理 ＋ Spec 内联（子代理两败于验证码超时） | §5 |
| 8 | 评审发现 5 处修复并复跑绿循环 | §5 |

## 2. 八项结论（全部"成立"，每条本机复现）

（下文所引票据/汇报行号均为 09-27 一致性评审快照时点；A 更正落笔后行号已漂移，认内容不认行号。）

1. **P1-1 M1/M5 `newly_red=2`**：t2 产物 M1/M5 各 2（tracked、干净、mtime 09-26 16:13 未重跑）；
   `4439519` 原文即"2 红；2 红"，`5d479e9` diff 逐字显示改成 1 红 ⇒ "采纳"改错方向。票面已回改 2 红＋注记。
2. **P1-2 quota mtime**：现存五份同名库无一为 08-26 17:28——`backend/data/`（12,288 B）＝**2026-09-19
   00:12:51.569**（§3 原值逐字成立）、根 `data/`（4,096 B）＝08-08 04:18、backups 两份 09-19、worktree 09-03
   （diag/hij 下另有测试夹具件，非现状口径）⇒ 按"09-26 量错路径"处理，§0 已恢复原值并留痕。
3. **P2-1 缺 `+`**：票据 :61-71 逐字提取实跑＝SyntaxError（"Perhaps you forgot a comma?"）；补 `+` 后在
   ro 副本跑通，**10266 / 0 / [('upload',10266)]** 与票面逐字一致。已补并加注（评审轮补的注，见 §5-4）。
4. **P2-2 批内查重已被落地**：`import_laws.py` 的 `seen_in_batch` 声明/批内比对/命中即连同 `conflicts`
   进 `blocked` 整批不写入（09-27 工作区时点，认符号不认行号）；票面在册限制①仍写"待裁" ⇒ 已加
   "被复审修正规则落地取代"注记，原文保留为历史。
5. **P2-3 S0-c 47/48**：s0c 产物 7 条目 `collected` 恒 47（:197"产物里是 46"系仪器修复时点残句）；
   现量 `--collect-only`＝`test_time_unverified_note.py` **20**、三 TARGET 合计 **48**（落地时 19+14+14=47）
   ⇒ :172/:183 改"落地时点读数＋09-27 现量"双口径，:197 改 47。
6. **P3-1 出口 16→18**：`gate_exit_registry.py` 现量 EXITS=18（E17、E18 在列）；票面"待落地"与"现列 16 个
   出口"已改"已落地＋评审时点读数"。
7. **P3-2 D20 两轴**：历史轴 `56696c5` 版 :104 含 13 位字母数字字面值恰 **1** 处（计数核实、未读取值）；
   工作树轴 :104 已是形状规则（`7eda4bb`）、3 份 `.env` 在场（3,351/3,725/343 B，按文件名核实）
   ⇒ D20 行改两轴口径，按值命中未重测（归 D23）。
8. **P3-3 行号漂移**：`main.py` 2627→**2673**、2670→**2716**、`law_versions.py` 32→**78**（八站点现值全
   "未验证"）；`knowledge_service.py:157`、`retrieval.py:1226`、`backfill_time_meta.py:19` 仍准；
   `import_docs.py:108` 旧形状已被修复本身移除 ⇒ 站点表加"09-26 时点快照、认符号不认行号"注记。

## 3. 文档更正清单（11 处，全部带"09-27 对账"标记）

- **票据（8 处）**：① §0 脚本补 `+`（后加对账注）；② 站点表加"09-26 时点快照"注记；
  ③ :161"待落地"→"已落地＋16 为评审时点读数"；④ :172 加现量 20；⑤ :183 加现算 48；⑥ :197"46"→"47"；
  ⑦ 变异句 M1/M5 回改 2 红＋误读产物注记；⑧ 在册限制①加"已被复审修正规则落地取代"。
- **汇报（3 处）**：① §0 quota 行恢复原值＋量错路径定性（worktree/backups 佐证写入）；
  ② D20 行改历史轴/工作树轴两轴口径；③ §9.5e 终稿表 §T2 行改"产物各 2 红、采纳改错方向、已回改"。

## 4. pip-audit（命令与退出码；rc=1＝有通报，非网络失败）

- **主命令**（模块入口可用，未走 fallback）：backend 下 `venv\Scripts\python.exe -m pip_audit -r requirements.txt`
  （pip-audit 2.10.1）⇒ **rc=1**，自报"Found 138 known vulnerabilities in 10 packages"（含按需求分组的重复行，
  去重后 82 行：pypdf 41、starlette 7、transformers 7、langchain 系 25、chromadb 2）。
  注意：`-r` 模式审的是**按区间新解析出的安装集**（pypdf 解析到 5.9.0），不是本机实装集。
- **环境模式**（不带 `-r`）：⇒ **rc=1**，91 条/14 包。T7 相关实装面：pypdf **6.14.2**（越 `<6.0`）余 6 条
  （修 6.15.0–6.16.1）、starlette **0.36.3** 七条（修 0.40.0–1.3.1）、chromadb **0.4.24** 两条**未给修复版本**。
- **附加事实**：`pip check` 两条红（fastapi 0.110.3 要 starlette≥0.37.2 而实装 0.36.3；sse-starlette 3.4.8
  〔mcp 传递、backend 未 import〕要 ≥0.49.1）⇒ venv 现状不自洽；CI（ci.yml:45-46）每次跑 `-r` 模式 ⇒
  按解析集读数**推断** CI 的 pip-audit 步必红（未查实际 CI 运行记录）。
- 实装版本：fastapi 0.110.3（在区间）、chromadb 0.4.24（在区间）、pypdf 6.14.2 与 uvicorn 0.52.1（均越声明区间，
  与汇报 §9.11 记载一致）。PyPI 在售：chromadb 1.5.9（0.5.x 至 0.5.23）、pypdf 6.19.0、fastapi 0.141.1、
  starlette 1.7.0。

## 5. 双轴自评审与修复（code-review + diagnosing-bugs）

**Standards 轴（子代理独立跑）**：3 硬违规候选＋4 判断题。逐条核实后的处置：

| # | 指控 | 核实 | 处置 |
|---|---|---|---|
| 1 | §9.11"CONTRIBUTING 17 项"与现值不符 | **降级为并行竞态**：HEAD 版 ：10 即"17 项"，该句当时属实；对账期间工作树被另一会话改"24 项"＋对账测试（17 passed） | 该句后加"09-27 深夜对账注"标时点，不改内容 |
| 2 | T7"详见汇报回执"悬空指针 | 属实 | 改"完整读数在会话回执、未落盘，此处录要点" |
| 3 | 票据注 `:179/:210/:231` 违"认符号不认行号"（:231 无该字面） | 属实 | 改符号描述＋"09-27 工作区时点" |
| 4 | §0 脚本就地改 `+` 未注何时因何 | 属实（A 漏加注） | 补"09-27 对账注"（含读数复现与"不改变历史凭证定位"） |
| 5 | T7"CI 现在就是红的"系推断 | 属实 | 改"按解析集读数推断…（未查实际 CI 运行记录）" |
| 6 | "复审修正规则"与 §9.11 同规则双写（Duplicated Code） | 属实，判断题；都在早前会话 hunk | **不动作**，留单一写入方下轮（一处为准、一处指针） |
| 7 | 票据 @@ -336 实测数字改定性句未留痕 | 属实但数字仍存活于汇报 :564 与 git 历史 | **不动作**，已在此记账 |

子代理另核：新引 9 个 SHA 全可解析、对账声明经产物复核全部成立、两会话顺序写入不违 D28。

**Spec 轴（子代理两次验证码超时后内联执行）**：对照派单与评审 §3 建议替换句逐条核——八项更正全部落地且
形态合格；T7 三节五要素齐备、"未核"明写、无编造版本；改动全部带对账标记且不越三文件写区，§9.11 主体与
汇报尾部逐字未动，E 助手验收段落未代写。**零硬发现**；一处措辞偏离（P1-1 汇报行未照抄"对 T1 成立、
对 T2 不成立"字面，语义由"采纳改错方向"＋相邻行完整承载，无信息损失）。

**diagnosing-bugs 纪律**：五条已证实缺陷的红循环＝上表对应的单命令核查（各自红过一次）→ 修复 → 复跑全绿
（`git diff --check` rc=0；五处标记 grep 命中 2/1/2）。

## 6. 逐文件 SHA256（前 → 后）

| 文件 | A 编辑前 | 一轮更正后 | 评审修复后（当前） |
|---|---|---|---|
| 票据 | `24e69ee7f65e…fa6c8` | `d573793d5cce…31b6` | `83347648efb8…3748`（复核轮后再修 1 处标记口径，见 §8） |
| 汇报 | `9cc2bbb707ef…10b34` | `f51142a44d50…3744a` | `6f523add50d4…6180` |
| T7 分案 | —（新建 `d69cd0be…55ef`） | `02533e4aae24…b9402` | `48c1231e9571…89c0b` |

（工作树并行写者活跃——上表只对 A 的编辑时点负责；收口前请重取。）

## 7. 未解决项

1. T7 三处"未核"：允许 starlette≥1.3.1 的 fastapi 版本；chromadb 0.5/1.x 能否清 PYSEC-2026-3813/3814
   （审计库对 0.4.24 未给修复版本）；`langchain-chroma>=0.1,<0.2` 对 chromadb 的实际上限。
2. `.env` 按值命中计数（D23）归 Owner——A 不读 `.env` 值。
3. 汇报 §3 第 5 条历史行路径简写 `data/` 实指 `backend/data/`——原值成立、简写歧义，不在八项内，留裁。
4. Standards 判断题两条（规则双写、定性化改写）都在早前会话 hunk，动否归单一写入方下轮。
5. smoke 门禁 24 项的内部构成存在两个口径（一致性评审 7+7+3+7 vs CONTRIBUTING 现文 7+7+3+4+3），
   对账测试 `test_gate_item_counts_match_contributing` 的覆盖面未核。
6. `CONTRIBUTING.md` 工作树改动与 `test_smoke_citation_assertions.py` 的归属未核（A 只读未碰）。
7. CI 红为推断，未查实际 CI 运行记录；工作树并行修改持续出现（对账期间 17→19 个 modified 的通报与本文
   观察一致）。

## 8. 复核轮（Owner 令"复核一遍有没有疏漏和错误"）发现与处置

按 `verification-before-completion` 铁律全部新跑一遍，三处问题当场修复：

1. **附录 P2-1 复现命令失效（真错误）**：原写 `sed -n '61,71p'` 取工作树文件——但工作树已补 `+`，
   该命令不再复现 SyntaxError，且 HEAD 版行号按偏移应为 54-64。已改为
   `git show HEAD:… | sed -n '54,64p'` 并实跑复验（⇒ SyntaxError）。
2. **"11 处每处带'09-27 对账'标记"不准（口径）**：票据在册限制①那处标的是"09-27 工作区时点"，
   grep 字标只 7/8。已把该处改为"09-27 对账：工作区时点"，现 8/8＋汇报 3/3 齐。
3. **快照行号缺时点声明（口径）**：§2/§3 引用的 :161/:172/:183/:197 是评审快照行号，更正落笔后已漂
   （如 M1/M5 句现落 :431）。已在 §2 头部加"认内容不认行号"声明。

另补测闭合一处：P2-3 的 14+14 分解此前只验过合计 48，本轮单独量两文件＝14、14，20+14+14=48 全部亲测。
终验：HEAD 仍 `7eda4bb`；四文件哈希见 §6（票据列已更新为本轮修后值）。

## 附录：关键复现命令

（本节命令全部在本会话实跑验证过；其中 P2-1 原稿复现在复核轮重跑过一次，输出为 SyntaxError。）

```bash
# P1-1：产物与票面/提交史比对（仓库根）
python -c "import json;d=json.load(open('dispatch-output/t2-preflight-report-20260926/mutation-verdicts.json',encoding='utf-8'));print([(i['mutant'],len(i.get('newly_red') or [])) for i in d])"
git show 4439519:docs/h1-law-version-collision-tickets-20260926.md | grep -n 'M1 删掉'
git show 5d479e9 -- docs/h1-law-version-collision-tickets-20260926.md | grep -B1 -A1 '红'

# P2-1：票据脚本逐字实跑（仓库根；ro 副本指向 %TEMP%\fazhi-chroma-ro.sqlite3）
# P2-1 原稿复现须取 HEAD 版（工作树已补 +，且行号按 HEAD 偏移为 54-64，非评审快照的 61-71）：
git show HEAD:docs/h1-law-version-collision-tickets-20260926.md | sed -n '54,64p' > "$TEMP/repro.py" && backend/venv/Scripts/python.exe "$TEMP/repro.py"   # ⇒ SyntaxError
sed 's/" + B$/" + B +/' "$TEMP/repro.py" > "$TEMP/repro_fixed.py" && backend/venv/Scripts/python.exe "$TEMP/repro_fixed.py"   # ⇒ 10266 / 0 / [('upload', 10266)]

# S0-c 现量（backend/ 下）
./venv/Scripts/python.exe -B -m pytest tests/test_time_unverified_note.py tests/test_gate_exit_registry.py tests/test_stream_exit_law_version_gate.py --collect-only -q -p no:cacheprovider   # ⇒ 48（单文件 20）

# 审计（backend/ 下；两条都要跑，口径不同）
./venv/Scripts/python.exe -m pip_audit -r requirements.txt   # ⇒ rc=1（CI 口径）
./venv/Scripts/python.exe -m pip_audit                        # ⇒ rc=1（实装口径）
./venv/Scripts/python.exe -m pip check                        # ⇒ 两条红
```
