# 票组 H1：无时效旧块与批导入的静默并存（T1–T5）

开票日 2026-09-26。来源：`docs/superpowers/plans/2026-09-25-next-phase-local-candidate.md` 文末 §独立评审
（两路独立评审 agent + 执行者逐条复测）与 `docs/corpus-time-meta-ticket-20260925.md` §8。

**本组票据的状态：全部未实施。** 本轮（Owner 定为 B 档）只写判据、不动生产码。
每条"证据"都是本机实跑读数，不是推理；复现路径写在 §0。

---

## 0. 复现凭证（下一条读者可一次跑完）

三份真实库副本（原件零改动：`backend/chroma_db/chroma.sqlite3` mtime 仍 `2026-09-21 02:06`、38 文件、
`find -newermt 2026-09-26` = 0）：

```bash
cp -r backend/chroma_db "$TEMP/fazhi-chroma-copy-20260926"     # 只读对照（dry-run 用）
cp -r backend/chroma_db "$TEMP/fazhi-chroma-h1repro-20260926"  # 实跑导入 → 10266→10269
cp -r backend/chroma_db "$TEMP/fazhi-chroma-fixed-20260926"    # 导入后删 2 旧块 → 10267
cd backend && CHROMA_DIR="$(cygpath -w "$TEMP/fazhi-chroma-h1repro-20260926")" \
  ./venv/Scripts/python.exe scripts/import_laws.py --input ../data/laws_extra.candidate-20260925.json
```

关键读数（逐字）：

| 读数 | 值 |
|---|---|
| 预检（真实库副本 `--dry-run`） | `将替换 0 旧片段 + 新增：民法典 第一千二百六十条` ×3、`跳过 0 条` |
| 现网 origin 分布 | `legal_provisions_cos` 10266 条全 `upload`；`origin='seed'` **0 条**；QA 段 279 条 `qa` |
| 现网时效字段 | `effective_from` 非空 **0 条**（10266 条皆空串），`status` 全 `现行`，无 `version_id` |
| 旧块无日期 ⇒ 谓词 fail-open | `is_valid_by_time` 在 2020-01-01 / 2021-01-01 / 2026-09-26 **全 True** |
| 遮蔽效应 | `exact_article_lookup('民法典','第一千二百六十条',cutoff='2020-06-01')` → **n=1，即那份无日期旧块** |
| 排序净效果（k=4，5 题） | **+1 命中**（1260 进 top-4）**／−2 挤出**（`劳动法 83`、`仲裁法 90` 掉出） |
| 删旧块后 | 两题挤出项全部回来，1260 的第 3 名**保留** ⇒ 处置旧块 = 去代价留收益 |
| 文本形状 | 1260 旧 165 字 vs 新 141 字；27 旧 290 vs 新 275；`exact_equal=False`，去空白/全角后 `new ⊆ old` 两对皆 True、`old ⊆ new` 皆 False |

---

## T1 — 让"无时效旧块"可被带时效的新版安全取代

**现象/根因**：`law_versions.replaceable_version_ids`（`backend/law_versions.py:40-55`）判"同一版本"的两条分支是
`stored_version_id == version_id` **或** `(无 version_id 且 stored_effective_from == effective_from)`（:53）。
现网旧块**既无 `version_id`、`effective_from` 又是空串** ⇒ 空串永不等上新值 ⇒ 旧块**不可取代**，
新块只能并排加进去。这不是数据错，是"版本化之前的遗留副本"这条分支从未按"整个时效轴缺失"来定义。

**改点**：`law_versions.py` 单一函数本体（**不在调用方另写一份判断**——本仓对 `_source_key`、
`is_valid_by_time` 立的都是"单一真源"规矩，两处判断必然漂移）。函数改为**一次返回两半**：

```
(可替换的旧块 ids, 需报警的并存块)     # 同一判断的两半，禁止拆成两次遍历
```

- **可替换**：`无 version_id` **且** `effective_from`、`effective_to` 皆为空 **且** `origin ∈ {upload, manual}`
  **且** 归一化包含成立（见下）。
- **需报警的并存**：同 (source, article) 存在旧块但**不满足**上述包含关系，或 `origin ∉ {upload, manual}`。
- **归一化包含**：`norm(t) = re.sub(r"[\s\u3000]+", "", t)`（覆盖全角空格 `　`），条件 `norm(new) ⊆ norm(old)`。
  ⚠️ **不许用"正文逐字相等"当前置** —— §0 实测两对旧/新块 `exact_equal` 全 False（旧块带章节行与条号前缀），
  该写法会让这条分支**在本库永不触发**，等于没修。
- 两个调用点各取所需：`scripts/import_laws.py:158`（预检）与 `knowledge_service.py:209`（手动添加/导入的实际写入）。
  两处现在都只 `include=["metadatas"]`，需改 `include=["metadatas", "documents"]` 并把正文传进来
  （`chroma:document` 也在 metadata 里，可作回退源）。

**判据（怎么算修好）**：
1. `tests/test_law_versions.py`（既有断言点在 :33）新增：无 `version_id` + 两日期皆空 + `origin='upload'` 的旧块
   **配 `norm(new) ⊆ norm(old)` 的正文** ⇒ 返回该 id 为可替换、并存列表为空。
2. 正文互不包含 ⇒ 不删、且**出现在并存列表里**（不许静默）。
3. `origin='seed'` 的无日期旧块 ⇒ **不碰**（它归 `knowledge_base.py` 重建管）。
   ⚠️ 别和 `_seed_conflict()` 混成一件事，两句主语不同：`_seed_conflict` 决定**进来的这条要不要处理**
   （库里该 (source,article) 有 seed 副本 ⇒ 整条跳过、不改），本条决定**处理时哪些旧副本可删**（seed 副本永不进可删集）。
4. 同一 (source, article) 已有**带日期**旧块且日期不同 ⇒ 仍按"修订版并存"，不进可替换列表（现有语义不许回归）。
5. **变异跑**：把白名单里 `upload` 去掉 ⇒ 必须红；把归一化里的 `\u3000` 去掉 ⇒ 必须红
   （旧块章节行用的正是 `\u3000`，实测 `chapter='第十章\u3000建筑物和物件损害责任'`）。
6. 真实库副本重跑 §0 第三条命令：1260/27 两行必须变成 `将替换 1 旧片段`，`合同法 428` 保持 `将替换 0`（它本就没有旧块）。
7. **可测性限定（09-26 回炉补）**：判据只在**同进程**内立即成立 —— 写入路径 `add_chunks` 会调
   `retrieval.invalidate()`（`knowledge_service.py:162` → `retrieval.py:668`）清 LRU 与 BM25 缓存；
   **跨进程读侧（运行中的 `fazhi-backend` 容器）看不到别的进程的失效**，要等它自己下一次写入或重启。
   ⇒ 票的验收写"同进程新查询只剩 1 块 + 副本目录 count 可查"，**不许**写成"线上立即可查"。


**回退**：函数纯逻辑、无落库副作用，回退=还原 `law_versions.py` + 两处 `include`。已产生的双胞胎不在回退范围内（属 E7）。

---

## T2 — 预检必须把"并存"说出来（现在完全静默）

**现象/根因**：`scripts/import_laws.py:143-176` 的预检只报 `将替换 N 旧片段 + 新增` 与 `跳过（与种子冲突…）`。
T1 之前 N 恒为 0、`_seed_conflict()`（:96-104）因**库里 0 条 seed** 恒为 False ⇒ 预检对"旁边躺着一份无限期有效的旧块"
**一个字都不说**。§0 第一行就是它的逐字输出。

**改点**：消费 T1 返回的第二半。`_seed_conflict()` 的语义（只认 `origin=="seed"`）**保留不动**，
但函数名要在票里标明它今天对现网是死码，避免下一个人继续拿它当"重叠会被拦下"的信心来源。

**退出码分档（Owner 已裁定）**：
- 真并存（新 ⊆ 旧，旧块只是无时效）⇒ 预检打印 `⚠️ 与 M 条无时效旧块并存（将被 T1 取代）`，**rc=0**。
- 互不包含（库里同条文有另一套文字）⇒ **rc=1**，交人工判 —— 脚本无权替法务在两个不同版本里选一个删。
- 输入违规（时效字段缺失/占位符/哈希不符）⇒ **整批不出**，沿用已签口径，本票不改这条。

**判据**：
1. 该报警分支**可达且有用例**（拿 `include` 出来的旧块元数据构造，不 mock 成空列表）。
2. 真实库副本 `--dry-run`：1260/27 两行必须出现 `⚠️`，`合同法 428` 不出现；rc 仍为 0。
3. 构造一个"互不包含"的假条目（同法名条号 + 正文改一个字）⇒ rc=**1**，且**不写入任何内容**。
4. 分类判据只在 T1 的函数里有一份；`grep` 本票验收时要确认 `import_laws.py` 里**没有**第二处
  `effective_from`/`version_id` 的空值判断。

---

## T3 — 校验器四个"看着有、实际不拦"（四条独立小改）

| # | 位置 | 现状（实测） | 改成 |
|---|---|---|---|
| ① | `scripts/import_laws.py:56` | `status = _text_field(...) or "现行"` ⇒ **省略 status 时静默按现行**，于是 :71-72 那条"已修改/已废止必带 `effective_to`"（Owner 09-25 已裁）**根本触发不了** | `status` 键**缺失**时按已签口径要求显式声明（缺失即报错），空串仍按现行 |
| ② | `scripts/import_laws.py:32` `_PLACEHOLDER_RE` | 放行 `待核`/`TBD`/`XXX`（三条负例全 `errors=[]`） | 补七个词 `待核`、`待定`、`待补充`、`TBD`、`TODO`、`XXX`、`（略）`，仍只作用于 `title`/`content`。现网 10266 条正文对这七个词**命中 0**（已实测），无需收窄 |
| ③ | `:75-77` + `law_versions.py:34` | 声明哈希只做 64-hex 格式检查（`"0"×64` 通过），且**提供了值就永不重算** ⇒ 声明与正文可无成本脱钩 | 加一支复核：`sha256(content)`（**不做任何归一**，与 `source_document_sha256()` 现有定义一致）与声明值不符即报错；或**不接受外部值**，一律由正文计算（票里二选一并写理由） |
| ④ | `:69-70` 只查了 `effective_to < effective_from` | **没有查 `effective_from` 与本条 `promulgated_at` 的方向** ⇒ E7 盘点实测：99 部里 36 部的正文末条日期早于本版公布日（那是**原法**施行日），照抄入库就是把时效轴整体前挪且无测试会红 | 加 `effective_from < promulgated_at ⇒ 报错`；**同日必须放行**（PUB 档 7 部是"自公布之日起施行"，写成严格大于会误杀） |

④ 的证据与全清单见 `docs/e7-legacy-undated-corpus-inventory-20260926.md`（元典独立核过：
专利法(2020修正) `publication_date 2020-10-17` / `effective_date 2021-06-01`，而正文末条写 1985-04-01）。

**实施前必须先知道的既有回归面（09-26 自己复算，不是评审给的）**：
③ 的"哈希必须等于正文"一旦落地，**会打挂两处现有测试** —— `tests/test_tool_gateway.py:212` 与 `:240` 传的是
`source_document_sha256 = "a"*64`（假哈希，配合假 content）。⇒ ③ 的判据要加一句：
"要么把这两例改成传真哈希，要么显式声明该字段可缺省、只在提供时复核"，二选一写进票，别留给 builder 猜。
④ 则相反：`data/laws.json` 的 **7 条种子全部没有 `promulgated_at`**，所以 ④ 只能作用在**批导入路径**
（`validate_entry`），不许顺手加到 `knowledge_base.py` 的种子构造上 —— 那会当场把 7 条种子全判死。



**判据**：三条负例由 `errors=[]` 变红；**同时本轮那 3 条真候选必须仍全绿**（防"为拦住坏例把真语料一起判死"）。
②**现网误伤面已量过：0**。拿真实库副本的 10266 条正文跑七个新词
（`待核`/`待定`/`待补充`/`TBD`/`TODO`/`XXX`/`（略）`）**全部命中 0 条**，现有正则也命中 0 条
⇒ 直接加，不必收窄词形；但要留一条"现网正文命中 0"的复量脚本进票的验收，防止以后语料变多时无人重算。
③注意别写成"重算一切"：`version_metadata` 的生产者实测只有三处 —— `knowledge_base.py:38`（种子）、
`knowledge_service.py:183`（manual/import）、`scripts/import_laws.py:153`（批导入），三者传的 `content`
**都是单条条文正文**；而 `import_docs.py` 的整法上传路径**根本不经过** `version_metadata`
⇒ 复核支只需覆盖这三处同源形状，不必为整法路径特判。

---

## T4 — 三处失效的 SHA 指针

**现象**：`b40076b` 在本仓与远端审计克隆都 `cat-file -t` → fatal。它被当作"改前红基线"写进了
`backend/gate_exit_registry.py:549`、`:553` 和 `backend/tests/test_stream_exit_law_version_gate.py:471`，
其中**测试 docstring 那处是按字面可执行的指令**（"在 `b40076b` 的副本树里跑"），照抄必失败。

**根因与替身（已实测）**：09-22 那次 cutover 重写了对象，旧 SHA 全失效但内容还在 ——
按 subject 反查得本仓等价提交 **`c25fbd6`**（同 subject `docs(派票C/票面自洽): 清掉票 C 里两处会误导 builder 的话`、
同日期 2026-09-20），两者 **tree 同为 `cfa6cab27d236b9bff932ce0e6b881d0b0c89932`**（内容逐字相同）。

**改点**：三处 `b40076b` → `c25fbd6`，并各附一句"2026-09-22 cutover 换写；tree 同为 `cfa6cab2…`"，
免得下一个人再怀疑是否同一提交。**这是纯注释/文档改动，零行为影响**，因此不许顺手改任何断言。
**判据**：`git cat-file -t c25fbd6` = commit；`git rev-parse c25fbd6^{tree}` = `cfa6cab2…`；
`git archive c25fbd6` 能出树（对侧逐帧基线即 E6 因此可执行）。

---

## T5 — 守门器落在所有静态门的作用面之外

**现象（实测）**：与 CI 同 cwd 跑 `./venv/Scripts/python.exe -m mypy scripts/import_laws.py` → **1 error**：
`:48 Need type annotation for "errors"`。而 `backend/pyproject.toml` 的 mypy `exclude = ["(?x)^(tests/|scripts/|venv/)"]`
（coverage 同样 `omit` 掉 `tests/* scripts/*`）⇒ **CI 结构上不可能看见它**。

**改点**：①`:48` 补 `errors: list[str] = []`；②决定"批导入守门器是否必须过类型"——
若要，就把 `scripts/import_laws.py`（**只这一个文件**，不是整个 `scripts/`）加进 mypy 作用面并跑一次全量看余量；
若不要，就在 `pyproject.toml` 旁写明"守门器由 `tests/test_import_laws_validation.py` 的正/负例负责，静态门不管它"。
**不许留成"没人说过这件事"。**

**判据**：选①则单跑 mypy 该文件 0 error；选②则 `pyproject.toml` 或票里要有那句明文，且 CI 不变。

---

## T6 — `gen_r8_disposition.py` 能凭空铸出"已批准"（开票当日新查，阻 E3 的执行方式）

**现象（读码 + 实测口径，非推测）**：`backend/scripts/gen_r8_disposition.py`
把结论字段**写死**了 —— `:69 scan_date = "2026-09-07"`、`:106-110 owner_approval = {"status": "APPROVED",
"decision": "数据所有者批准整体 Risk Accepted（2026-09-07）", "approved_at": "2026-09-07"}`，
且输出路径是**固定的** `:17 OUT = release-evidence/legal-agent-v1-grayscale-20260907`、
`:18 RAW` 与 `:113 r8-disposition-20260907.json` 同名，`:48 RAW.write_text(...)` **原地覆盖**。

**后果两条**：
1. **"重跑生成器来复扫"这个动作今天会覆盖 09-07 的已签证据件**（`git status` 立刻显形，但覆盖前的内容只剩 git 里那份）。
2. 更要紧：它会把 `owner_approval.status = "APPROVED"` **连同一个旧日期**一起写进新产物 ——
   也就是说这台机器可以生成一份"看着像 Owner 批过"的处置记录，而**没有任何新批准**。
   这与本轮我在 §7-1 里 flagged 的"AI 已填复核卷"是**同一族失效**：证据的形状先于证据的事实。

**改点（判据）**：① `scan_date` / 输出文件名由入参或当日日期派生，不许硬编码；
② `owner_approval` 三段由脚本置为 `{"status": "PENDING", "decision": "", "approved_at": ""}`，
批准只能由人事后填；③ 目标文件已存在时**拒绝覆盖**（`--force` 才允许），且写前把旧件哈希打进日志；
④ 补一条测试钉住"脚本产物的 `owner_approval.status` 不是 APPROVED"（防回归）。
⑤ 另三条同批查出的事实也要一并修：**`:48` 连原始审计件 `r8-audit-20260907.json` 都是原地改写**（不只是派生的处置件）、
脚本**没有任何 dry-run/守卫**、且首行 docstring 自称"待签"与 `:106-110` 硬编码 `APPROVED` **直接矛盾**
（`:93` 的 `approver` 至今仍是占位符）⇒ 矛盾本身就是"这份批准从未真发生过"的书面证据，改码时以 docstring 为准。


**E3 因此怎么执行（本轮按此，不改动依赖）**：
1. 复扫只取**读数**：`pip-audit` 的 json 落到 `dispatch-output/` 一类工作目录，**不写 `release-evidence/`**；
2. 新处置记录**手写日期、人工签署**，命名 `r8-disposition-<复扫日>.json`，**09-07 两份原件一字不改**（审计链要能并列看）；
3. 签署字段仍由 Owner 给：助手可以准备扫描与逐包表，**不代填 `owner_approval`**。
   在 T6 落地前，任何人跑这个脚本都等于伪造批准 ⇒ 这一条要写在脚本头的 docstring 里。



## T7 — pypdf 上限：从"风险接受"改判"计划修复"（E3 的一部分，Owner 已裁按此做）

**读价（09-26 本机复扫，输出在 `%TEMP%\r8-rescan-20260926\pip-audit-20260926.json`，rc=1）**：
132 个依赖里 **10 包 / 138 行 / 77 个不同公告 ID**，其中 **pypdf 5.9.0 独占 77 行（56%）**；
其余 starlette 14、langchain-core 11、langchain-community 8、transformers 8、langchain 7、langsmith 5、
text-splitters 4、langchain-openai 2、chromadb 2。`fixes` 数组为空。
⚠️ 口径：**138 是"行数"、77 是"去重公告 ID"**，两个轴不许混用；本轮另一次读数得 80 个 ID ⇒
差值是 OSV 侧公告变动，不是本地依赖变化（本地 10 包集合与解析版本零漂移）。

**为什么单独摘它**：① 它是最大单块（56%）；② 全仓只有 **1 个调用点**（`knowledge_service.py:108-111` 仅用 `extract_text`）；
③ **本机现在实际在跑 pypdf 6.14.2**（越出 `>=4.0,<6.0` 区间锁），并且是在它上面取到 1544 passed 的
⇒ 兼容性风险已被一次"意外的真实读数"抵掉一大半，但这**不等于**验证过：那 1544 条里没有针对 pdf 边界的断言。

**改点（判据）**：① 放宽上限到含 6.x（具体上界由 Owner 定），改 `requirements.txt` 与 `Dockerfile` 同源；
② 补 pdf 路径的定向测试（含 10MB 上限、解压炸弹、`extract_text` 之外的调用为零这一事实）；
③ **不许**沿用本机现状当"已验证"——必须在按新锁重装出来的环境里重跑一次门禁；
④ 顺手解决另一处越锁：`uvicorn 0.52.1` vs 钉 `>=0.27,<0.28`（同一族问题：本机依赖集 ≠ 发布物依赖集）。

## T8 — 存量 10266 条无时效碎片补日期（原 E7，已给成本读数）

盘点件：**`docs/e7-legacy-undated-corpus-inventory-20260926.md`**。要点三条：
① 机械化率不是"96/99"而是 **52 部方向自洽 + 7 部公布即施行**，**36 部正文末条日期是原法施行日（用了就错）**、4 部取不到；
② 主源必须是元典结构化字段（`publication_date`/`effective_date`/`validity_status`/`document_number` + 留 `id` 溯源），
正文正则只准**报警不准填值**；③ 本票**只补 `effective_from`/`promulgated_at`**，
`status` 与 `effective_to` 不动 —— 元典 `部分失效`/`尚未生效` 到本仓字面值的映射**尚未签字**（数据票 §3-A）。

前置：Owner 撤"本轮不动库"边界；T1/T2 先落地（否则补了日期仍会与旧块并存）；建议排在独立法律复核回来之后。


## 7. 本组票据**不含**的一件事（免得被当已完成）

1. **独立法律复核仍未取得。** 唯一那份"已填"卷（`outputs/法律咨询回答复核作业-已填-20260918.md`）
   署名是 `法律合规专家（WorkBuddy AI）`（第 202/1015 行），且第 **1267** 行自带一条流程违规声明：
   因材料为单文件版，第四、五部分在第一阶段开始前已读入，"意见冻结前不读第四、五部分"的防锚定流程未严格执行。
   ⇒ 结论是"**既非人类、也未按盲评流程执行**"。派给真人的复核包必须显式带回这两条约束：
   分件盲评（甲/乙对应关系不进包）、回执 `reviewer` 字段留空由人签、**AI 不得代填**。
