# 任务工作汇报：汇报与票据一致性复核（2026-09-27）

**派单**：`C:\Users\33393\Desktop\ai-legal-helper\docs\assistant-briefs\report-consistency-review.md`
**负责文件**：`docs/progress-handoff-report-20260925.md`（下称"报告"，761 行）、
`docs/h1-law-version-collision-tickets-20260926.md`（下称"票据"，598 行）
**执行**：本会话，2026-09-27；只读核对 + 两轮取证。**写入**：全程未编辑任何既有文件，仅创建本汇报（本文件）。
**边界遵守**：未 push、未部署、未轮换凭据、未写任何真实库、未执行批量导入（唯一涉及库的动作是
`--dry-run` 与 sqlite `mode=ro`，均指向 %TEMP% 副本，副本 mtime 事后复量未动）。

## 0. 一页汇总

按派单只读核对两份文档是否如实反映代码、工作区、提交与验证结果。**确认 8 条问题（P1×2、P2×3、P3×3），
全部经两轮取证成立**：初审（09-27）+ 应用户要求按 `verification-before-completion` 做的二次取证（同日）。
复核轮无一撤回，并完成三件事：①把初审里两处靠推理的判断升格为实证（P1-1 的"改错方向"、P2-3 的分母分解）；
②发现并修正我初审自己的一处行号引用错误（P2-3 的"19 条"实际在票据 :172 而非 :174，见 §3）；
③重负载验证（门禁/回归）用 sha1 绑定方式确认仍绑定当前文件内容。

两份文档的**方向性主张绝大多数可现场复现**（§4），需要修的是**数字与口径**，不是结论。

## 1. 并行会话下的取证纪律（用户中途提示后收紧）

- 全程只读；对两份负责文件零编辑。
- 重负载验证跑前跑后对 7 个工作区文件取 sha1 比对，一致才引用该次读数（二次取证轮复验仍全部 OK）。
- 副本库操作后复量 mtime（fazhi-chroma-copy-20260926/chroma.sqlite3 保持 2026-09-26 02:39:16 未动）。
- 所有行号注明"2026-09-27 快照，工作树有并行写者会漂"；`git status --porcelain` 行数当日 536→538
  （未跟踪区持续有并行写入，不影响任何已提交文件的比对）。

## 2. 做了什么（按顺序）

| # | 动作 | 证据 |
|---|---|---|
| 1 | 通读两份负责文件 + git 快照 | `git status --porcelain`、`git log --oneline -25`（HEAD=`7eda4bb`） |
| 2 | 核对提交链与各节阶段叙述 | `git show 4439519 / 5d479e9`、`git rev-list --count`（a96df2c=168、HEAD=170） |
| 3 | 读工作区 diff，逐条对照票据"T1/T2 复审修正规则"（:437-449） | `git diff` law_versions.py / import_laws.py / knowledge_service.py / 4 个测试文件 |
| 4 | 现量复跑静态门禁 | `ruff check .` 通过；`ruff format --check .`=265 files；`mypy .`=73 files |
| 5 | 现量复跑八文件回归（哈希守卫） | 报告 :744 的复跑命令 ⇒ **105 passed / 2 skipped / 105 warnings，73.84s** |
| 6 | 副本 dry-run + ro 库只读查询 | dry-run：替换 1+1+0、新增 3、跳过 0、rc=0；ro：10266 / 0 / upload×10266 / version_id=0 |
| 7 | 核对四份变异产物、bundle、评审落盘文件 | 解析 4 份 mutation-verdicts.json；stat bundle（144,158,691 B）与 %TEMP% 四份评审产物 |
| 8 | 二次取证轮 | 逐条重跑命令 + 四项自查（§3 各条"复核轮"标注） |

## 3. 确证问题（终版 8 条）

### P1-1 票面 T2 变异读数与其入库产物矛盾——5d479e9"采纳评审"时把对的改错

- **位置**：票据 :420（M1/M5 句）；同源错误在报告 :560（§9.5e 终稿表该行）
- **两侧**：票面现文"M1 删掉 ⚠️ 的产生 → **1 红**；M5 把 ⚠️ 改成恒真 → **1 红**"；其引用的入库产物
  （tracked、干净、mtime 09-26 16:13 未被重跑）`dispatch-output/t2-preflight-report-20260926/mutation-verdicts.json`
  实录 M1=`M1-no-legacy-warning` newly_red=**2**、M5=`M5-always-warn` newly_red=**2**（M2/M3/M4 各 1 红与票面一致）。
  报告 :560 复测格"产物里 M1/M5 各 **1** 红"与同一产物不符
- **复核轮升格为实证**：`git show 4439519` 证实改前票面原文就是"→ 2 红；→ 2 红"（与产物一致），
  `git show 5d479e9` 的 diff 逐字显示这两处被改成 1 红 ⇒ **票面原数字是对的，"采纳"改错了方向**
- **建议替换句**：票据 :420 两处改回 2 红；报告 :560 改为"复测：产物里 M1/M5 各 **2** 红——终稿此条对 T1 成立、
  对 T2 不成立，`5d479e9` 按 1 红改票面是误读产物，需回改"

### P1-2 §0 的 quota_used.sqlite mtime"更正"在现存任一同名库上都复现不了

- **位置**：报告 :53-55（§0"边界与形状"）；对照 :127-129（§3 第 5 条原值）
- **两侧**：§0 写 quota="08-26 17:28"（09-26 更正）。09-27 现量：
  `backend/data/quota_used.sqlite`（12,288 B）= **2026-09-19 00:12:51.569**（恰为 §3 保留的原值）；
  根目录 `data/quota_used.sqlite`（4,096 B，另一份文件）= 2026-08-08 04:18:56；
  backups 两份（09-19）与 worktree 那份（09-03）也都不是 08-26 17:28 ⇒ **"更正后"的值现在无处可复现，
  而"被更正掉"的原值在 backend/data 那份上今天仍逐字成立**。09-26 那次更正疑似量错路径
- **建议替换句**：§0 该行改为"backend/data/quota_used.sqlite 09-27 复量仍为 2026-09-19 00:12:51（与 §3 原值逐字同）；
  根目录另有同名 data/quota_used.sqlite（4,096 B、08-08 04:18）不是同一文件。09-26 写下的'08-26 17:28'
  在现存任一同名库上不可复现，按量错路径处理，原读数恢复有效"

### P2-1 票据 §S0 复现脚本按字面运行即 SyntaxError

- **位置**：票据 :70-71（:59-73 代码块内）
- **两侧**：`con.execute("select m.string_value,count(*) " + B` 换行后直接跟 `"and m.key='origin'…"`——
  变量与字面量不能隐式拼接。逐字提取 :61-71 实跑 ⇒ SyntaxError；补一个 `+` 后跑通，
  且读数 `10266 / 0 / [('upload',10266)]` 与票面逐字一致
- **建议替换句**：:70 行尾 `+ B` 后补 `+`

### P2-2 票 T2"在册限制①"（批内双胞胎看不见、"待裁"）已被工作区实现推翻，但读起来仍是现状

- **位置**：票据 :428-431；对照 :443（复审修正规则"同批重复或重叠条目在写入前整批阻断"）与报告 §9.11
- **两侧**：在册限制①写"会两条都写入……要堵它得加一条批内查重，**那是新范围、待裁**"；
  而工作区 `backend/scripts/import_laws.py` 已实现 `seen_in_batch` 批内查重并整批阻断（:179/:210/:231）。
  票头豁免（:12-13）措辞只覆盖"初次判据及变异读数"，罩不住这条读起来像现行限制的"在册限制"
- **建议替换句**：①末尾追加"（**已被复审修正规则落地取代**：批内查重已在本轮工作区实现，见汇报 §9.11；
  本条保留为初次实现的历史记录）"

### P2-3 S0-c 落地记录的"现量"声明已被工作区推进；:197 与产物直接矛盾

- **位置**：票据 :172（"19 条（`--collect-only` 现量）"）、:183（"分母恒 `collected=47`"）、:197（"产物里是 46"）
- **两侧**：① :197"产物里是 46"与入库产物 `s0c-note-20260926/mutation-verdicts.json`（全条目 collected=**47**）
  及同节 :183/:188-189（"分母从 46 变 47、产物已重跑覆盖"）自相矛盾——仪器修复时点的残句；
  ② 现量 `tests/test_time_unverified_note.py` --collect-only = **20**（工作区按 §9.11 第 3 条新增恢复钩子用例），
  s0c 驱动 TARGETS 三文件现量 20+14+14=**48**，落地时 19+14+14=47；票头豁免只写了 T1/T2，罩不住 S0-c 的"现量/恒"
- **复核轮更正**：初审把"19 条"标在 :174，实为 **:172**——本条是我的行号引用错误，借此更正
- **建议替换句**：:197 改为"产物里是 47（后因补 E7 先后用例由 46 再变 47，见上）"；
  :172/:183 各加"（工作区 09-27 复核时该文件已 20 条、该分母现算为 48；47 绑定入库产物时点）"，
  或把票头豁免扩写为"T1/T2/S0-c 的落地记录"

### P3-1 验收仪器小节仍写"待落地：S0-c"与"现列 16 个出口"，与同文件落地记录冲突

- **位置**：票据 :161-162
- **两侧**："**待落地**：S0-c 的逐出口端点级测试……（评审实测该登记表**现列 16 个出口**）"；
  同文件 :164 起"S0-c 落地记录"与报告 §9.9 均记载已落地，EXITS 现量 **18**（E17/E18 在列）
- **建议替换句**："已落地（见下节 S0-c 落地记录）；'16 个出口'是评审时点读数，落地后为 18"

### P3-2 D20 行"已知下界仍是 3 份 `.env` + `:104`"缺口径，易读成现状

- **位置**：报告 :298
- **两侧**：D26 已执行且 `7eda4bb` 已提交 `:104` 形状规则（现文件计数=1 的形状规则、无字面值）；
  工作树轴按值命中现只有 3 份 `.env`（`./.env`、`backend/.env`、`frontend/.env`，按文件名核实）；
  "+:104"仅对**历史提交轴**成立（`56696c5` 版第 104 行含 13 位字母数字字面值，计数核实、未读取值）
- **建议替换句**："已知下界（**历史提交轴**）仍是'3 份 `.env` + `:104` 旧 blob'；**工作树轴** `:104`
  已改形状规则（D26），现为 3 份 `.env`，未重测"

### P3-3 S0-b 站点表/D14 的行号已漂移（依本仓"认符号不认行号"规矩的小刺）

- **位置**：票据 :92-99；报告 :292（D14）
- **两侧**：票面写 `main.py:2627`/`:2670`、`law_versions.py:32`，现量漂至 main.py:**2673**/**2716**、
  law_versions.py:**78**（八个站点的**值**全部正确落成"未验证"，逐个 grep 核实；knowledge_service.py:157、
  retrieval.py:1226、backfill_time_meta.py:19 行号仍准）
- **建议替换句**：站点表"位置"列改符号描述，或表头加"行号为 09-26 时点，认符号不认行号"

## 4. 复现一致项（检查过的状态来源；除注明外均本会话现跑）

- **提交链**：HEAD=`7eda4bb`；`4439519` 之后 `0082e22→5d479e9→a96df2c→dc88bb1→7eda4bb`；a96df2c=168 笔、HEAD=170 笔
- **工作区**：7 个 backend 文件 + 2 份 docs 的修改与 §9.11 描述一致；dispatch-output 5 个 09-21 遗留仍在；候选 json 未动
- **静态门禁**：ruff check 通过 / format 265 files / mypy 73 files
- **八文件回归**：105 passed / 2 skipped / 105 warnings（73.84s；§9.11 记载 55.15s，时长非判据）；
  二次取证轮哈希比对仍逐文件 OK ⇒ 该读数绑定当前文件内容
- **副本 dry-run**：替换 1+1+0、新增 3、跳过 0、rc=0，含两行"⚠️ 与 1 条无时效旧块并存"（与报告 :747-748、票据 :448 一致）
- **ro 库**：10266 碎片 / effective_from 非空 0 / origin 全 upload / version_id 非空 0
- **T1/T2 修订规则 ↔ 代码**：`_same_article_body`（仅已知章节行/条号前缀可差、完整正文一致）、seed 不删、
  空日期不判同版本、`compatible_versions` 单侧日期界值、`conflicts` 排除兼容项、批内查重——逐条对应复审修正规则；`--validate-only` 仍在
- **变异产物 ↔ 票面**：s0b（1 红/37）、s0c（9/2/5/3/2/3，collected=47）、t1（3/3/3/2/1，collected=32）逐字一致；唯 t2 的 M1/M5 不一致（P1-1）
- **其他**：`:104` 形状规则（计数=1）✓；D 盘 bundle 144,158,691 B ✓；%TEMP% 四份评审产物在场且字节数与 §9.8 逐字同
  （36,985 / 33,632 / 26,844 / 48,331 B；复核轮抽查 review3 同值）；EXITS=18、`_TIME_NOTE_CELLS`、
  S0C 空元组 7 个（E6/E10–E13/E15/E16，初审 grep）；PROBLEM_LOG §五 #26–#29（初审）；E7 盘点 53/5565、36/3549、6/463、4/689（初审）；
  smoke 脚本运行时校验恰 24 项（7+7+3+7，结构计数）、CONTRIBUTING"17 项"确已落后

## 5. 未核实项（明示限制，别当已核）

1. §9.11 的 smoke 24/24（EMBEDDING_PROVIDER=local、RERANK_ENABLED=false）**未复跑**（需本地嵌入模型）；
   "周末加班前六条含劳动法第四十四条"未独立复核。我核的是脚本项数与口径，不是那次跑的结论。
2. "本机实际配置 rerank_enabled=True"未核（避免读 `.env` 内容）。
3. "修前 5 failed / 修后 5 passed"及各"先红后绿"读数依赖改前代码状态，未复演（文档已自标为当轮证据）。
4. 远端轴（204 笔、`git fetch` 失败根因、推送）一律未触碰——超出派单边界。
5. D23 按值反查属 Owner 任务，且涉及凭据值，未执行。
6. 根目录 `caddy_config/`、`caddy_data/`、`.qoder/` 及 `dispatch-output/t12-frontend-sweep-20260920/` 下
   4 个新未跟踪 `.py` 的归属未核实（疑似并行会话/本地服务产物；两份文档均未提及，
   建议单一写入方下次记账时补一句归属）。
7. quota"08-26 17:28"的原始出处无法在现存五个同名库中复现——这已列为 P1-2，不是"未核实"而是"确证对不上"。

## 6. 附录：关键复现命令

```bash
# 八文件回归（在 backend/ 下；与报告 :744 一致）
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LLM_API_KEY=test-key-not-for-real-calls \
LLM_BASE_URL=https://test.invalid/v1 PYTHONDONTWRITEBYTECODE=1 \
./venv/Scripts/python.exe -B -m pytest tests/test_law_versions.py tests/test_import_laws_preflight.py \
  tests/test_import_laws_validation.py tests/test_knowledge_service.py tests/test_phase5.py \
  tests/test_time_unverified_note.py tests/test_fast_path_law_version_gate.py \
  tests/test_stream_exit_law_version_gate.py -q -rs     # ⇒ 105 passed / 2 skipped / 105 warnings

# 副本 dry-run（在 backend/ 下；只读副本）
CHROMA_DIR="C:\Users\33393\AppData\Local\Temp\fazhi-chroma-copy-20260926" \
  ./venv/Scripts/python.exe -B scripts/import_laws.py --input ../data/laws_extra.candidate-20260925.json --dry-run

# P1-1：产物与票面比对
git show 4439519:docs/h1-law-version-collision-tickets-20260926.md | grep -n 'M1 删掉'
git show 5d479e9 -- docs/h1-law-version-collision-tickets-20260926.md | grep -B2 -A2 'M1 删掉'
python -c "import json;d=json.load(open('dispatch-output/t2-preflight-report-20260926/mutation-verdicts.json',encoding='utf-8'));print([(i['mutant'],len(i.get('newly_red') or [])) for i in d])"

# P2-1：票据脚本逐字实跑（在仓库根）
sed -n '61,71p' docs/h1-law-version-collision-tickets-20260926.md > "$TEMP/repro.py" && backend/venv/Scripts/python.exe "$TEMP/repro.py"   # ⇒ SyntaxError
```
