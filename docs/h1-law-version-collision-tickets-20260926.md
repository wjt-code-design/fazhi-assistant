# 票组 H1：无时效旧块与批导入的静默并存（S0、T1–T8）

开票日 2026-09-26。来源：`docs/superpowers/plans/2026-09-25-next-phase-local-candidate.md` 文末 §独立评审
（两路独立评审 agent + 执行者逐条复测）与 `docs/corpus-time-meta-ticket-20260925.md` §8。

**票据状态（09-26 当日两次更新）**：
① 开票时 Owner 定为 **B 档**——只写判据、不动生产码；
② 同日 grilling 十题裁决后，**S0（三笔）＋ T1 ＋ T2 获准进入代码轮**（Q6/Q10：同一轮、分相邻 commit，
   且 Q10 要求"先落本票段给你过目，再动码"）；**T3–T8 仍未获授权**，导入窗口另裁。
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

## S0 — 把"时效未知"变成显式状态（09-26 grilling 十题裁决；本轮首要目标）

**为什么不排在 T1 后面而是前面**（本机只读复量，`fazhi-chroma-ro.sqlite3` / collection `legal_provisions_te4`）：
**10266/10266** 条 `effective_from` 是空串、`origin` 全 `upload`、`status` 全 `现行` ⇒
`retrieval_core.is_valid_by_time`（`:42-63`）的四个排除分支**一条都不触发**（它们要么要求"有日期"、
要么要求 `status∈{已废止,即将施行,未生效}`）⇒ **每一次检索都在走 fail-open**，与"我下一步会不会导入双胞胎"无关。
T1/T2 治的是"新导入造双胞胎"，治不到这条天天在走的通路。

复现（只读；**条号键是 `article`，不是 `article_number`** —— 我用错过一次，join 空表差点报成"库里没有"）：

```bash
backend/venv/Scripts/python.exe - <<'PY'
import sqlite3, os
ro = os.path.expandvars(r"%TEMP%\fazhi-chroma-ro.sqlite3")
con = sqlite3.connect(f"file:{ro.replace(chr(92),'/')}?mode=ro", uri=True)
B = ("from embedding_metadata m join embeddings e on e.id=m.id "
     "join segments s on s.id=e.segment_id join collections c on c.id=s.collection "
     "where c.name='legal_provisions_te4' ")
sel = lambda extra: con.execute("select count(*) " + B + extra).fetchone()[0]
print("碎片总数        :", sel("and m.key='source'"))
print("effective_from 非空:", sel("and m.key='effective_from' and m.string_value<>''"), "（0 = 全部 fail-open）")
print("origin 分布     :", con.execute("select m.string_value,count(*) " + B
                                       "and m.key='origin' group by 1 order by 2 desc").fetchall())
PY
```

三个读数同一个口径（**都限定在 `legal_provisions_te4` 这一棵集合内**；不限定会看到 `41064`，
那是 `_te4` 与 `_cos` 两份等量副本之和 —— 本票所有数字都不使用该口径）：
`10266 / 0 / [('upload', 10266)]`。

### S0 的层位（Q2 裁决：谓词侧 + 写侧，答案层只做窄面消费者）

| 编号 | 改点 | 位置 |
|---|---|---|
| S0-a | 新增**与谓词并列**的纯函数 `time_validity_state(meta)`，返回 `'verified'` 或 `'unknown'`（日期齐 ⇒ verified；否则 unknown）。**不改 `is_valid_by_time` 的 bool 签名**（它是向量池/BM25/grounded 打分的唯一共用谓词，动签名要连带五处调用点） | `backend/retrieval_core.py` |
| S0-b | **写侧止血**：`status` 的默认值不再是 `现行` ⇒ "现行"从此只能由人或源侧显式签出 | 四处，见下表 |
| S0-c | 答案层注记：**仅当本次答案使用了显式历史基准日**（`bootstrap.law_as_of is not None`）且引用块里有 `unknown` ⇒ 尾行加一句时效未验证注记 | `main.py` 源头传参 + 各出口 |
| — | **明确排除**："日期缺失即不参与检索"（fail-closed）。库里 unknown 比例 = 100% ⇒ 等于清空知识库。这条是算出来的，不是偏好 | —— |

**S0-b 的默认值站点 —— 票面原写"四处"，实施日用守卫测试扫出来是 8 处**（`80ff584`）：

| 位置 | 现形状 | 处置 |
|---|---|---|
| `backend/knowledge_service.py:157` | `base["status"] = (extra_meta or {}).get("status") or "现行"` —— 最深，任何调用方不传即得"现行" | ⇒ `or "未验证"` |
| `backend/scripts/import_docs.py:108` | `extra_meta={"status": "现行"}` | ⇒ 不写 status，由唯一缺省接管 |
| `backend/scripts/import_laws.py:56` | `status = _text_field(...) or "现行"` | ⇒ 改成**必填**，省略即整条拒（并 T3①） |
| `backend/law_versions.py:32` | `str(entry.get("status") or "现行")` | ⇒ `or "未验证"` |
| `backend/main.py:2627` | `"status": body.status or "现行"`（管理端新增知识） | ⇒ `or "未验证"` |
| `backend/main.py:2670` | `"status": "现行"`（管理端上传文件 payload） | ⇒ `未验证` |
| `backend/retrieval.py:1226` | `d.metadata.get("status", "现行")`（管理端检索测试展示，**读侧**） | ⇒ `未验证` |
| `backend/scripts/backfill_time_meta.py:19` | `DEFAULTS = {"status": "现行", ...}`（存量回填） | ⇒ `未验证` |

另修一处**结构性**隐患：`backend/schemas.py:177` 有第二份硬编码 status 集合 ⇒ 只扩 `retrieval_core` 的白名单
会让 API 把 `未验证` 判成 422。已改成 `from retrieval_core import STATUS_WHITELIST`（单一真源）。

⚠️ **`tools/contracts.py:235` —— 09-26 已裁并落地**（代码保持原样，只补了钉子）：
`elif status == "现行" and effective_date is None: validity = "effective"` 是**比较**不是缺省，
但缺省一改，新写入的无日期块就不再走这条兜底 ⇒ `validity` 落 `unknown`。
下游不是打标签而是闸门：`agent/writer.py:222-227` 只有 `EFFECTIVE` 的法条算可引证据，
`agent/verifier.py:369-375` 引了非 `EFFECTIVE` 法条 ⇒ 整条 claim 判 **`FAIL_SAFE`（拒答）**。
⇒ 净效果 = agent 合同路径上出现一个**局部 fail-closed**，只作用于"S0-b 之后写入且无人给 status"的块；
**存量 10266 条元数据仍是 `现行` ⇒ 行为逐字不变**（动它们的是 E7，不是本票）。

Owner 裁决：**不恢复兜底**，把它钉成故意的。落地 = `tests/test_tool_gateway.py::test_unverified_status_without_dates_maps_to_unknown_validity`
（含两个对照组：`现行`+无日期仍 `effective`；有日期就按日期判，`未验证` 不覆盖日期证据）。
变异验证：把 `未验证` 塞回那条分支 ⇒ 该用例红（还原后 `diff` 确认 SAME）。
口径提醒：这里问的是"该条在基准日是否有效"，与 `retrieval_core.time_validity_state` 问的
"我们有没有资格这样断言"是**两个概念**，别互相冒充。

已实测的两条安全边界：`derive_version_id` 的身份串只有 `title+article+effective_from`（`law_versions.py:20`）
⇒ **status 不进版本 id**，改默认值不会让既有 `lv-*` 失效或凭空造出双胞胎；
且 `grep '"现行"' tests/*.py` 命中的断言**全是显式传 status 的谓词测试** ⇒ **没有一条测试钉的是默认值本身**
（这条我先前说重过一次，见下文"裁决变更史"末尾的更正）。

**校验器侧连带（与 T3① 是同一件事，必须一起改）**：`STATUS_WHITELIST`（`retrieval_core.py:39`）新增 `未验证`
= 放宽校验 ⇒ 若 `import_laws.py` 仍允许"省略 status"，就会出现"新导入的块默认未验证、门一声不响"的静默态。
所以 S0-b 落地时同步把批导入的 `status` 改成**必须显式给**（省略即整条拒），判据并入 T3① 那条。

### S0-c 的接线判据（为什么写这么细）

`cutoff` 在检索层**永远非空**：`retrieval.py:379` 与 `:844` 都写 `cutoff = cutoff or date.today().isoformat()`
⇒ **"只在带 cutoff 时注记"是空判据**。真正的区分在上层：`main.py:695 if bootstrap.law_as_of is not None`、
`_resume_law_as_of`（`main.py:775-784`，run 落当日返回 `None`）。
消费点实测是散的：`main.py:439`（快车道）、`prepare_fast_path` 直返、prompt 注入、
`domain_rules.py:28/41/71/105/552/554`（四个文档集 + 语义回落）、`exact_article_lookup`、`retrieve`。
⇒ **判据不许写成"确认各出口都加了注记"**（本仓就在"所有出口都挡了"这句话上漏过一条平行入口）。
要写成：① `unknown` 信号从 `bootstrap.law_as_of` 这**一个源头**以显式参数下传；
② **每个出口各一条测试**，逐出口点名，测试里断言的是**注记文本出现在该出口产出的答案里**（不是"函数被调用过"）。

### S0 的验收（Q5 裁的形状）

1. 单元层：`time_validity_state` 的 verified/unknown 两类 + 四处默认值各一条负例（不传 status ⇒ 落成 `未验证`）。
2. 端点层：抄 `tests/test_stream_exit_law_version_gate.py` 那 14 条的**端点级 SSE 逐帧**形状，逐出口证明注记真出现在答案里。
3. 端到端：在隔离 chroma 副本上实跑（`%TEMP%\fazhi-chroma-copy-20260926` 那三棵，7 秒可重建），**不碰真实库**。
4. **全量变异**（每个改动点至少一个变异体）：要能杀掉"把 `未验证` 悄悄塞进某个过滤条件"这一类。
   成本：本机全量 pytest 一次 317.90s ⇒ 数个体约 37 分钟起（**这是按 317.90s×N 推算的，不是实测**）。
5. **74 题评测集不在本轮**（`eval_set.json` 28 / `eval_exam.json` 20 / `eval_negative.json` 15 /
   `eval_contract.json` 的 `cases` 11 ⇒ Σ=74）。
   ⚠️ 本行原写"79 题（20/20/20/11）"，**两处错**：单文件数抄错两个、分量和也不等于总数（20+20+20+11=71≠79）；
   我最初那次实测输出其实是对的（11/20/15/28），错在往下抄。由第四轮评审抓出。
   理由不变：注记会改答案文本 ⇒ 逐帧 sha 与质量分都会动，同轮既改码又跑评测**无法归因**。要看影响 → 下一张票，先冻结本轮为 baseline。

**验收仪器落地进度（09-26 实施日更新）**：
- 已落地：`tests/test_time_validity_state.py`（S0-a，7 条）＋ `tests/test_status_default_unverified.py`（S0-b，7 条）。
- **评审抓出的覆盖缺口已补**：原验收只防得住"谓词内部被塞进 `未验证`"，防不住**检索层**
  （`retrieval.py:846` 那个 `valid` 闭包）——全仓无一测试可杀。现已加端点级负例
  `test_retrieval_valid_closure_accepts_unverified_blocks`，并用变异验证过：
  把 `and rc.time_validity_state(m) == "verified"` 塞进该闭包 ⇒ 该条红（还原后 `diff` 确认 SAME）。
- 待落地：S0-c 的逐出口端点级测试。**出口清单请绑 `backend/gate_exit_registry.py`**（评审实测该登记表现列 16 个出口）
  而不是手写文件名 —— 手写那份会在下一次加出口时悄悄失效，而这正是本票要防的形状。

### S0-c 落地记录（09-26 实施日）

码：判据本体 `main._time_unverified_hit`（**全仓唯一一份**；①只认 `pre["law_as_of"]`，②复用 S0-a 的
`time_validity_state`）＋ 措辞真源 `main.NOTE_TIME_UNVERIFIED`。
接的位置：E7 缓冲整答**并进同一帧**（`NOTE_LAW_VERSION` 的既有形状）；E8 与 E9 在两个答案来源**合流之后**
追加一帧 ⇒ 登记表新增 **E17**；E5 合同报告同理 ⇒ 新增 **E18**。⇒ **出口数 16 → 18**，
登记表并新增一列「时效未核验注记」（`COLUMNS` + 每格取证；这一列的取证集中写在 `_TIME_NOTE_CELLS`，
因为它是横切列：拆进 18 个字面量就看不出"哪些出口没接"）。
测试：`tests/test_time_unverified_note.py` **18 条**（`--collect-only` 现量），四条元测试把清单绑在 `EXITS` 上 ——
①登记表加出口不填这一列 ⇒ 红；②格子写 `PASS` 却没有真用例 ⇒ 红；③用例名指向不存在的测试（假指针）⇒ 红；
④没用例的格必须写明状态、且 `GAP-TODO` 得上票号。

**全量变异 6/6 全杀**（仪器与读数随票入库：`dispatch-output/s0c-note-20260926/mutate.py` +
`mutation-verdicts.json`；跑的是那三个端点级/登记表文件，分母恒 `collected=46`（`--collect-only` 现量），
每体跑完字节比对确认还原）：
M1 删 E17 帧 → 9 红（含 E8/E9/顺序/期望表/三条登记表哨兵）；M2 E7 不注记 → 1 红（正是那条 E7 用例）；
M3 删 E18 帧 → 5 红；M4 判据丢掉"显式基准日"这一半 → 3 红（含控制腿）；M5 判据丢掉"unknown"这一半 →
2 红（含控制腿）；M6 摘掉 E17 锚点 → 3 红（哨兵按条数对账那两条）。
⚠️ M2 的**第一版是个假变异体**：它删掉整行 `answer += ...` 后留下一个只剩注释的 `if` 块 ⇒
`IndentationError` ⇒ `collected=0`。驱动按"分母漂移"拒算了这一次（票 C r1 立的规矩），改成 `pass` 之后才拿到真读数。
另记一条锚点陷阱：`" "*20 + "answer += NOTE_TIME_UNVERIFIED"` 会**同时命中 24 空格那一处**
（24 个空格的前 20 个也是空格）⇒ 锚点计数 2 ⇒ 驱动拒跑；变异锚点必须带行首换行。
⚠️ **本票第一版产物里的"45"是错标的轴**（我拿 `passed+failed` 之和当 collected ⇒ 把 1 条 skipped 吞了；
修仪器时又一度拿 `passed+skipped` 当分母 ⇒ 那个数一有失败就自己缩小，每个变异体"分母"都不一样）。
两条都已改：真 collected 由 `--collect-only` 量一次作常量，本轮跑了多少 = passed+failed+skipped+error，
对不上就判漂移。上表读数**已用修好的仪器重跑**，产物里是 46。

**上线后可见后果（要 Owner 知道的范围，不是缺陷）**：判据的②在现网**恒真**
（E7 清点：10266/10266 条无日期）⇒ 凡带显式历史基准日的答复都会带这句注记，直到 E7 把日期补上为止。
这正是 S0-c 的本意（没资格断言就该说出来），但它改的是用户可见文本：
`tests/test_stream_exit_law_version_gate.py` 的独立期望表因此加了一项
（`want = claim + 时效注记 + 版本注记`）；顺序"时效在前、版本在后"由
`test_e17_frame_precedes_the_version_note` 钉成判据，不靠运气。

**我自己写错又改回的两处（留痕，别让下任以为原设计就是这样）**：
1. 我起初把 E1 判成"缓存键缺基准日轴"的缺陷、预备开 **票 T9**。写取证用例时被打回来：
   `_cacheable` 的合取项里本来就写着 `not pre.get("law_as_of")`（函数注释原文「显式历史日期不进共享答案缓存」）
   ⇒ 带注记的答复**永不进**缓存、历史请求**读不到**缓存 ⇒ 那条"缺陷"不成立，**T9 没开**，E1 改判 `NA`。
   我原来那句推断是从 `_cache_key(pre)` 的签名反推的 —— 规矩同 09-25 那条：**会推翻已签判断的说法，
   落笔前要读被引用的函数本体**。
2. E2（QA 语料直返）我一度接了注记，随后撤掉：`prepare_fast_path` 写 `qa_hit = None if cutoff`
   ⇒ 有显式基准日就没有 `qa_hit`，那条注记是**恒不命中的空门**（与 E3/E4 版本绊线格同一个前科形状）。
   两处"不适用"都留了**带对照腿**的用例（E1 那条断"根本没写缓存"、E2 那条断"不传基准日时确实去取语料"），
   不给"用 NA 糊过去"留空间。

### 裁决变更史（本轮替换了什么、**没**替换什么）

- **替换**：09-25 数据票 §2 那条隐含口径"上传即 `现行`"（它从未被单独签过，是代码默认值替所有人做的断言）
  ⇒ 自 S0-b 起，`现行` 必须由人/源显式给出。`STATUS_WHITELIST` 随之扩一格 `未验证`。
- **不替换**：`tests/test_phase5.py:13` `test_valid_by_time_amended_window_pin_per_owner_ruling`
  —— 它钉的是 09-25 你裁的"**给 `已修改` 的旧版补 `effective_to`**"那件事，与 status 默认值无关；
  `:34/:35/:45-56` 那批 fail-open 断言**显式传 status**，S0 全不动它们 ⇒ **S0 落地后这些测试应当仍然全绿**，
  若有红，说明改到了谓词行为本身，那是**跑偏**、要停下来问，不是顺手改测试。
- **一次自我更正**：我在 grilling Q10 说过"Q3 会拔掉 `pin_per_owner_ruling` 那根钉子"。
  落票前 grep 断言原文证伪了自己的这句话 ⇒ 上文的"不替换"以复测为准。规矩同前：**会推翻已签裁决的说法，
  落笔前要读被引断言的原文**，不能凭测试名和印象推断。

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
5. **变异跑**：把白名单里 `upload` 去掉 ⇒ 必须红。
   ⚠️ **原判据 5 的第二半作废（09-26 独立评审抓出，我本机复测确认）**：票原来写"把归一化里的 `\u3000` 去掉 ⇒ 必须红"，
   那是**一条永远杀不掉的假变异** —— Python 3 的 `\s` 本就匹配全角空格 U+3000。实测：
   `re.match(r'\s','　')` = `True`，且 `re.sub(r"[\s　]+","",s)` 与 `re.sub(r"\s+","",s)` 对
   `chapter='第十章　建筑物和物件损害责任'` 的输出**逐字相同**（`第十章建筑物和物件损害责任`）。
   ⇒ 换成两条**真能改变行为**的变异：
   ① 把 `norm()` 里的 `re.sub(...)` 整段去掉（不做归一化）⇒ 必须红（1260 旧块带章节行与全角空格）；
   ② 把包含判断 `norm(new) ⊆ norm(old)` 换成精确相等 `new == old` ⇒ 必须红（这正是本票 §"已被否掉的想当然修法"
   记下的那条：旧 165 字 vs 新 141 字，精确相等永不成立）。
   另：`norm` 定义里的 `\u3000` 只是**给人看的意图注释**，不承担可测性 —— 想让它可测就得先证明 `\s` 不覆盖它，
   而那条证明刚才跑出来是反的。
6. 真实库副本重跑 §0 第三条命令：1260/27 两行必须变成 `将替换 1 旧片段`，`合同法 428` 保持 `将替换 0`（它本就没有旧块）。
7. **可测性限定（09-26 回炉补）**：判据只在**同进程**内立即成立 —— 写入路径 `add_chunks` 会调
   `retrieval.invalidate()`（`knowledge_service.py:162` → `retrieval.py:668`）清 LRU 与 BM25 缓存；
   **跨进程读侧（运行中的 `fazhi-backend` 容器）看不到别的进程的失效**，要等它自己下一次写入或重启。
   ⇒ 票的验收写"同进程新查询只剩 1 块 + 副本目录 count 可查"，**不许**写成"线上立即可查"。


**落地记录（09-26 实施日）**

⚠️ **返回形状修正（落 T2 时改的，先记在这里免得两票各说一套）**：票面写的是"一次返回两半"。
两半不够 T2 用 —— 它要单独报出「与 M 条**无时效**旧块并存」，那个 M 数的是"遗留无时效"这一类；
只给"可替换"总和的话，调用方就得自己重推"哪些是遗留无时效" ⇒ 那是**第二份判据**。
⇒ 实作为 `ReplacementPlan`（`NamedTuple`，三个桶 `same_version` / `legacy_undated` / `coexist`，
`replaceable` 是前两桶之和的 property），**仍是一次遍历**，`test_replaceable_is_exactly_the_two_replacement_buckets`
钉住"删除面只有一个来源"。原语义未动：`same_version` 就是改动前那唯一一条分支。

码按票面落在**单一本体**：`law_versions.replaceable_version_ids` 一次遍历分三个桶，新增 origin 白名单常量 `_LEGACY_REPLACEABLE_ORIGINS = ("upload", "manual")`
与 `_norm_text`。判"可替换"的三条合取（无 `version_id` / 时效轴两个键皆空 / `origin` 在白名单）**加上**
归一化包含，全仓只有这一处 —— 票 T2 判据 4 的 grep 复量：`import_laws.py` 里 `effective_from`/`version_id`
只出现在①入口校验（:62-83，主语是"进来的这条"）与②把新值喂给本函数（:162-166），
**没有**第二处"库里这块是不是无时效遗留"的空值判断。
两个调用点都改成 `include=["metadatas", "documents"]` 并传 `new_content`：
写侧（`knowledge_service.add_text`）只消费 `plan.replaceable` —— 并存块**不删**是安全侧，"要说出来"归预检；
预检侧（`scripts/import_laws.py`）三个桶都读，见下面 T2 的落地记录。

测试：`tests/test_law_versions.py` **11 条**（`--collect-only` 现量：判据 1/2/3/4 各一条，
外加三条边界 —— 只有 `effective_to` 的废止版不算"整个缺失"、调用方没传正文时 **fail-safe 进并存**
（判不出就绝不猜"能删"）、不传 `documents` 时回退 `chroma:document`）。既有那条
`test_replacement_keeps_other_effective_versions` 只改了返回形状，选择结果逐字未动 ⇒ 判据 4 的
"现有语义不许回归"由它守。

**变异 5/5 全杀**（仪器 `dispatch-output/t1-legacy-replace-20260926/mutate.py` + `mutation-verdicts.json`，
分母恒 `collected=31`，每体跑完字节比对还原）：M1 白名单去掉 `upload`（判据 5 指名）→ 2 红；
M2 不做归一化（判据 5①）→ 2 红；M3 包含换成逐字相等（判据 5②）→ 2 红；
M4 丢掉"时效轴整个缺失"这一半 → 2 红（正是"带日期的修订版被误删"那条）；
M5 丢掉 origin 白名单 → 1 红（seed 副本被吞那条）。
M4/M5 是我加在票面之外的两条 —— 判据 5 只要求"去掉 upload 要红"，但**误删**比**漏删**严重，
所以那两个方向也各自有守卫。

**判据 6 真实库副本复量（只读那份 `fazhi-chroma-copy-20260926`，逐字）**：

```
共 3 条，开始预检：
  将替换 1 旧片段 + 新增：民法典 第一千二百六十条
  将替换 1 旧片段 + 新增：劳动争议调解仲裁法 第二十七条
  将替换 0 旧片段 + 新增：合同法 第四百二十八条

预检完成：将删除 2 旧片段，新增 3 条，跳过 0 条。
```

对照 §0 基线（三行全是 `将替换 0`）⇒ 两对双胞胎现在都被认成可取代，而本来就没有旧块的
`合同法 428` 保持 0（没有因新分支被误报）。真实库零改动：`backend/chroma_db/chroma.sqlite3`
mtime 仍是 `2026-09-21 02:06`、`backend/app.db` 仍是 `2026-09-19 00:28`。

**判据 7（可测性限定）照票面执行**：以上都是**同进程**读数。跨进程读侧（运行中的 `fazhi-backend`
容器）看不到本进程的 `retrieval.invalidate()` ⇒ 本票**不**声称"线上立即可查"，那一步属导入窗口批次。

---

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

**落地记录（09-26 实施日）**

预检改成**两趟**：第一趟全量判定 + 播报，第二趟才写。票面"互不包含 ⇒ rc=1 且不写入任何内容"在旧的
"边判边写"形状下做不到（前几条已落库才发现后面并存 ⇒ 只能回滚）。
播报是一个**纯函数** `preflight_lines(title, article, plan)`（`LINE_REPLACE` / `LINE_LEGACY` / `LINE_COEXIST`
三条措辞常量），它只把三个桶说出来，**不重新判** —— 判据仍只有 `law_versions` 那一份。
`_seed_conflict()` 语义一字未动，但给它补了 docstring 写明"今天对现网是死码"（E7 读数：10266 条 origin 全
`upload`、seed 0 条 ⇒ 恒 False），免得下一个人把它当"重叠会被拦下"的信心来源。

**判据 4（只有一份判据）机器化成了用例**：`test_import_laws_holds_no_second_copy_of_the_judgment`
断言 `_LEGACY_REPLACEABLE_ORIGINS` / `_norm_text` / `stored_effective_from` / `chroma:document`
这四个零件在 `import_laws.py` 里**一次都不出现**。（人肉 grep 的读数同向：该文件里 `effective_from`/`version_id`
只出现在①入口校验（主语是"进来的这条"）与②把新值喂给判据函数两处。）
选"符号是否出现"而不是行号：行号会被本文件其他改动挤掉。

**判据 1（报警分支可达且有用例，不 mock 成空列表）**：`tests/test_import_laws_preflight.py` **7 条** ——
三条单元腿直接吃真 `replaceable_version_ids` 的产物（遗留并存 / 互不包含 / 同版本控制腿），
三条端点腿真跑 `main()` 打真临时 Chroma（`⚠️` 出现且 rc=0、`✗` ⇒ rc=1 且**两条手**钉住没写入：
`add_text` 换成会炸的替身 + 集合条目数前后不变），外加一条对照组
（判据全过的批次**确实**走到写入 ⇒ 防"整批不写入"那条是空枪）。

**判据 2 真实库副本复量（只读那份，逐字）**：

```
共 3 条，开始预检：
  将替换 1 旧片段 + 新增：民法典 第一千二百六十条
  ⚠️ 与 1 条无时效旧块并存（将被 T1 取代）：民法典 第一千二百六十条
  将替换 1 旧片段 + 新增：劳动争议调解仲裁法 第二十七条
  ⚠️ 与 1 条无时效旧块并存（将被 T1 取代）：劳动争议调解仲裁法 第二十七条
  将替换 0 旧片段 + 新增：合同法 第四百二十八条

预检完成：将删除 2 旧片段（其中 2 条是**无时效遗留块**），新增 3 条，跳过 0 条。确认后去掉 --dry-run 实跑。
```

`⚠️` 只在 1260/27 两行出现、`合同法 428` 不出现（它本就没有旧块）⇒ rc 仍 0。真实库零改动：
`backend/chroma_db/chroma.sqlite3` mtime 仍 `2026-09-21 02:06`、`find -newermt 2026-09-26` = 0。

**判据 3**：见上面的端点腿 `test_non_contained_blocks_the_whole_batch_without_writing`
（构造"同法名条号 + 正文互不包含"的假条目 ⇒ `SystemExit.code == 1`、写入替身未被调用、条目数不变）。

**变异 5/5 全杀**（`dispatch-output/t2-preflight-report-20260926/{mutate.py,mutation-verdicts.json}`，
分母恒 `collected=19`）：M1 删掉 ⚠️ 的产生 → 2 红；M5 把 ⚠️ 改成恒真 → 2 红（含"普通重传不该报"那条控制腿）；
M2 去掉 `sys.exit(1)` → 1 红；M3 `blocked` 桶永不填 → 1 红；M4 把"先判后写"退成"边判边写" → 1 红。
后三条都落在同一条端点腿上，说明"整批不写入"这个承诺同时被三个不同的破坏方式守着。

**回退**：`preflight_lines` + `main()` 的两趟结构 + `_seed_conflict` 的 docstring；措辞常量删掉即回到旧输出。
判据本身没动（仍是 T1 那一处）。

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

**现象**：`b40076b` 在本仓与远端审计克隆都 `cat-file -t` → fatal（09-26 两侧各跑一次确认）。
⚠️ **作用面更正（09-26）**：本票原写"三处"，那是我拿 `grep -rn … | head -10` 截断后当全集读的**假数**。
按 tracked 轴重量（`git grep -n b40076b HEAD`）= **6 个文件 / 8 行**，且形状各不相同，处置方式也不同：

| 位置 | 载体形状 | 处置 |
|---|---|---|
| `backend/gate_exit_registry.py:549`、`:553` | 证据叙述**字符串字面量**（真源 dict，会渲染进门禁报告） | 改 |
| `backend/tests/test_stream_exit_law_version_gate.py:471` | 测试 docstring | 改 |
| `dispatch-output/s6-stream-gate-20260920/run_red_and_zero_change.py:4` | **可执行形状**：`git archive b40076b`（照抄必失败）；`:123` 是同一句的字符串 | 改 |
| `dispatch-output/i1-e2-hitrate-20260920/probe_b_direct_return_rate.py:97` | 注释 | 改 |
| `docs/gate-exit-registry.md:158` | **生成物**（`gen_gate_exit_registry.py` 渲染；`tests/test_gate_exit_registry.py:276` 就是"手改 md"的绊线） | **不手改**：改完真源后重渲染 |
| `dispatch-output/s6-stream-gate-20260920/00-zero-change-verdict.txt:5` | 当次运行留下的**历史证据读数** | **不追溯改写**，只在本票注明 |

另有未跟踪的存档副本树 `dispatch-output/hij-h-20260920/beforetree/`（`git ls-files` = 0）内含 7 行，那是快照、不算作用面。
口径注：`git grep -c` 数**行**、`git grep -o \| wc -l` 数**次**（本例 18 行 vs 21 次，后者含我在文档里把它当反例引的 10 处）。

**根因与替身（已实测）**：09-22 那次 cutover 重写了对象，旧 SHA 全失效但内容还在 ——
按 subject 反查得本仓等价提交 **`c25fbd6`**（同 subject `docs(派票C/票面自洽): 清掉票 C 里两处会误导 builder 的话`、
同日期 2026-09-20），两者 **tree 同为 `cfa6cab27d236b9bff932ce0e6b881d0b0c89932`**（内容逐字相同）。

**改点**：三处 `b40076b` → `c25fbd6`，并各附一句"2026-09-22 cutover 换写；tree 同为 `cfa6cab2…`"，
免得下一个人再怀疑是否同一提交。**不许顺手改任何断言。**
⚠️ **归口更正（09-26 复验后）**：票最初把这处写作"纯注释、零行为影响"，**不成立** ——
`gate_exit_registry.py:549/:553` 两处位于**证据叙述字符串内部**（会被渲染进门禁报告），
`:471` 在测试 docstring 里 ⇒ 三处都在 `.py` 文件内。因此本票**算代码轮的一笔**：
落地时要连带跑 `tests/test_gate_exit_registry.py` 与全量门禁，并且它会使那一轮不再是"代码零改动"。
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
① 机械化率不是"96/99"而是 **53 部方向自洽 + 6 部公布即施行**，**36 部正文末条日期是原法施行日（用了就错）**、4 部取不到；
   （部数 09-26 由第三轮评审复算订正过一次：原写 `52 + 7`，LATER↔PUB 之间差一部 48 碎片的法，规则与脚本现钉在盘点件 §6）
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
