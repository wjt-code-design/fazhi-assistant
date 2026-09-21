"""/api/chat「出口 × 闸门」登记表 · **真源**（ADR-018：借 NeMo 的槽位声明形状，不引依赖）。

为什么要有这张表（不是文档癖）：本仓两次出现「门接在活代码上、但那条代码今天没人走到 / 某个出口根本没接」，
第二次比第一次更难发现 —— 它过单元测试（`[PL#14] 假接线` 的具体形态）。
⇒ 每个出口 × 每道闸门都必须有一格，且**每格带取证**；填不出的格子必须显式写
`GAP-ACCEPTED+理由` 或 `GAP-TODO+票号`，**不许留空**（留空 = 三个月后没人知道是「没查」还是「不必查」）。

状态词汇沿用 `docs/capability-matrix.md`（别造第三套词）：
    PASS          已接，且有判据能证明它真的在管这件事
    DISABLED      接了，但当前配置/开关下不生效（≠ 已受保护）
    BLOCKED       要接必须先改用户可见行为或先解一个前置，写清阻断点
    NA            结构上不适用（理由必填 —— 不是「我懒得查」）
    GAP-ACCEPTED  未覆盖，且已裁定接受（理由 + 出处必填）
    GAP-TODO      未覆盖，待修（**必须带票号**）

机器约束（由 `tests/test_gate_exit_registry.py` 哨兵双向绑定，四条腿硬红）：
  源码里每条 `content` 帧 yield 必须带 `# gate-exit: E<n>` 锚点；锚点 ID 必须在 EXITS 里；
  EXITS 每行 ID 必须在源码出现；每行必须把 COLUMNS 全部填满。
生成物 `docs/gate-exit-registry.md` 由 `backend/scripts/gen_gate_exit_registry.py` 渲染，**不要手改 md**。
"""

from __future__ import annotations

import ast
import re

# 锚点形状的**唯一定义处**（测试与生成器都从这里取，别再抄第二份 `[PL#13]`）。
ANCHOR_RE = re.compile(r"#\s*gate-exit:\s*(E\d+)\b")


def _json_dumps_dict_keys(node: ast.AST) -> tuple[str, ...] | None:
    """`f"data: {json.dumps({...}, ensure_ascii=False)}\\n\\n"` 里那个 dict 的常量键。

    ⚠️ 出口帧不是 dict 字面量，是 **f-string 包 json.dumps** ⇒ 识别规则必须是
    `JoinedStr → Call(dumps) → Dict`。本仓曾按"dict 字面量"写扫描规则，实测命中 **0** 条
    （计划 §九-A1）—— 那条规则是空的，哨兵会静默恒真。
    """
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        fname = getattr(sub.func, "attr", None) or getattr(sub.func, "id", None)
        if fname == "dumps" and sub.args and isinstance(sub.args[0], ast.Dict):
            return tuple(k.value for k in sub.args[0].keys if isinstance(k, ast.Constant) and isinstance(k.value, str))
    return None


def scan_content_yields(src: str) -> list[tuple[int, str]]:
    """返回 `(行号, 正文表达式)` 升序 —— 「什么算一个会吐用户可见正文的出口」全仓只有这一份定义。

    哨兵、锚点插入脚本、生成器三处都 import 它，免得出现两份判定然后互相不一致（`[PL#13]`）。
    """
    out: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Yield) or node.value is None:
            continue
        keys = _json_dumps_dict_keys(node.value)
        if keys is None or "content" not in keys:
            continue
        expr = "?"
        for sub in ast.walk(node.value):
            if isinstance(sub, ast.Call) and sub.args and isinstance(sub.args[0], ast.Dict):
                for k, v in zip(sub.args[0].keys, sub.args[0].values, strict=True):
                    if isinstance(k, ast.Constant) and k.value == "content":
                        expr = ast.unparse(v)
        out.append((node.lineno, expr))
    return sorted(out)


def exits_by_anchor(src: str) -> dict[str, str]:
    """`{锚点 ID: 该出口当前吐的正文表达式}` —— **按 ID 绑，不按位置绑**。

    为什么不用 `zip(EXITS, scan_content_yields(...))`：那是按行序配对。将来在文件中间插一条出口，
    后面每一行的"现在吐什么"都会**静默错配到别的出口**，而 `strict=True` 只在**条数**不等时才炸 ⇒
    生成的 md 会自洽地假。行序不参与判定，锚点 ID 才参与。
    重复锚点（两条 yield 都写 `E7`）在这里会被计数并交给哨兵判红，不静默合并。
    """
    lines = src.splitlines()
    out: dict[str, str] = {}
    dups: list[str] = []
    for ln, expr in scan_content_yields(src):
        m = ANCHOR_RE.search(lines[ln - 1])
        if not m:
            continue  # 无锚点由哨兵 leg1 判红，这里不重复报
        if m.group(1) in out:
            dups.append(m.group(1))
        out.setdefault(m.group(1), expr)
    if dups:
        raise ValueError(f"重复锚点 {sorted(set(dups))}：一条 ID 只能绑一个出口")
    return out


def classify_non_text_frames(src: str) -> list[tuple[int, tuple[str, ...]]]:
    """`json.dumps` 帧里**不含 `content`** 的那些：`(行号, 顶层常量键)`。

    存在意义：让 `NON_TEXT_FRAME_KEYS` 变成**被核对的东西**而不是注释。哨兵两头钉它——
    ①每帧都必须能被清单里的某个键分类（否则是"出现了一种没人判过算不算出口的新帧"）；
    ②清单里每个键都必须真的还能在源码里用到（否则清单会烂成一段历史说明）。
    """
    out: list[tuple[int, tuple[str, ...]]] = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, (ast.JoinedStr, ast.Call)):
            continue
        keys = _json_dumps_dict_keys(node)
        if keys and "content" not in keys:
            out.append((getattr(node, "lineno", 0), keys))
    return sorted(set(out))


# 列顺序 = 生成 md 时的列顺序。
COLUMNS: tuple[str, ...] = (
    "可达性",
    "引用校验",
    "自检",
    "多选完整性",
    "配额降级注记",
    "版本绊线",
    "写缓存闸",
    "评测可信度",
)

# 合法状态值（哨兵据此判「这格填的是词表里的东西」）。
STATUSES: frozenset[str] = frozenset({"PASS", "DISABLED", "BLOCKED", "NA", "GAP-ACCEPTED", "GAP-TODO"})

# 非正文帧（按 payload 键分类）：登记表**不管**，但哨兵要认得，免得下任加一个 error 帧时
# 无从判断「这算不算一个会吐用户可见文本的出口」。
NON_TEXT_FRAME_KEYS: tuple[str, ...] = ("error", "type", "conversation_id")

# 每格 = (状态, 取证)。取证要么给 `main.py` 的符号/行为，要么给读数出处。
EXITS: list[dict] = [
    {
        "id": "E1",
        "where": "stream() / 分支0 缓存命中直返（变量 `ca`）",
        "traffic": "有执行取证",
        "cells": {
            "可达性": (
                "PASS",
                "默认配置即承流量：`test_flagship_quality.py` 同题二次请求实测 cache_hit_rate==0.5"
                "（本轮改后复跑 1 passed）⇒ 本出口真被走到。",
            ),
            "引用校验": (
                "GAP-ACCEPTED",
                "本出口不复判；引用是在**写入侧**过的（E8 的 `_cache_write_ok` + `quality.self_check` "
                "内含 `citation_verify`）。复判只加延迟、改不了已定内容。",
            ),
            "自检": (
                "DISABLED",
                "`routing_metrics.record("
                + '"cache"'
                + ", ..., checked=False)` ⇒ 本出口不跑自检（零 token 直返的定义）。",
            ),
            "多选完整性": ("DISABLED", "本出口不调 `quality.multi_incomplete`；选项指纹只在写侧参与存盘。"),
            "配额降级注记": ("NA", "零 LLM ⇒ 不存在降级语义。"),
            "版本绊线": (
                "GAP-ACCEPTED",
                "**2026-09-20 裁为 `GAP-ACCEPTED`（票 I 收口时的回表）**：E2 **已修**"
                "（语料标版本基准日 + 第四道护栏），而 E1 **不同修**——理由是它的暴露面比 E2 低一档、"
                "且同一手段治不了它：本出口读的是 `answer_cache`（进程内 `rc.LRU(maxsize=512)` + `TTL=6h`），"
                "重启与知识增删（`retrieval.invalidate()` → `clear()`）都清空 ⇒ 一条错版本答复的暴露窗 "
                "**≤ 6 小时**；而**开关要生效本来就得重启** ⇒ 开门那一刻顺手就把它清了，不需要专门动作。"
                "**结构性走不到**（这是技术理由，不是偷懒）：收口点的门在生成分支上，而本出口在门之前就 "
                "`return` ⇒ 挂到收口处的门对缓存复用型答复永远不命中。"
                "**不由票 C 解决**：票 C §4-Q2 于 2026-09-20 已裁「不判读侧」"
                "（读侧加判定会把「零 token 直返」这个特性本身打穿）。"
                "⚠️ **E2 不能照抄这个理由**：它是 **Chroma 持久**集合，无 TTL、重启不清、"
                "`clear()` 也碰不到 ⇒ 所以 E2 必须**真修**（票 I 的 I-2(a) 已修）。",
            ),
            "写缓存闸": ("NA", "读侧出口，不写缓存。"),
            "评测可信度": (
                "BLOCKED",
                "评测必须 `no_cache` 绕本出口，否则测的是缓存不是模型。前科 `[fz]`：qa_cache 曾让 "
                "multi_ok 0.43/0.57/0.64 三个数全失真 —— 数字失真比没数字危险。",
            ),
        },
    },
    {
        "id": "E2",
        "where": "stream() / 分支0.2 QA 持久语义缓存直返（变量 `qa_ans`）",
        "traffic": "命中率未量",
        "cells": {
            "可达性": (
                "PASS",
                "`_qa_direct_return` 依赖 `ks.search_qa`（Chroma `qa_pairs` 集合）。门禁读数：该集合条目 279 条"
                "⇒ 语料在场；**命中率本轮未量**（别把「能命中」读成「常命中」）。",
            ),
            "引用校验": (
                "GAP-ACCEPTED",
                "预生成语料（8-23 智谱免费 token 离线生成），读侧不复判；写侧护栏=高阈值+选项指纹+evidence 时效三闸。",
            ),
            "自检": ("DISABLED", "`record(" + '"qa_cache"' + ", ..., checked=False)`。"),
            "多选完整性": ("DISABLED", "选项指纹参与**命中判定**（防跨题误命中），但不跑 `multi_incomplete` 注记。"),
            "配额降级注记": ("NA", "零 LLM。"),
            "版本绊线": (
                "PASS",
                "**票 I 的 I-2(a) 已修（2026-09-20）**：给语料标版本基准日 + 加**第四**道护栏。"
                "① **语料标注**：279/279 条写入 `law_as_of_basis` = "
                '`"2026-08-23"`（生成日**上界**，来自 `scripts/gen_qa_corpus.py` docstring'
                "「智谱免费 token …（8-23 到期前消耗）」）+ 出处字段 "
                '`law_as_of_basis_src` = `"inferred-docstring-8-23"`'
                "（**是推断就让它随数据走**，而不是只活在报告里）。"
                "既有 metadata 键（answer/evidence/options_fingerprint/origin）**一个没动**："
                "写前逐条断言「合并结果 == 原 metadata + 我的两个键」，并已产出**逐条备份** "
                "`corpus-backup-qa_pairs.json`（回滚路径）。"
                "② **运行时护栏**（`main._qa_direct_return` 的**第四**条，前三条**一字未动**）："
                "请求的 `law_as_of` 与语料基准日若分处 `limitation_calc.CIVIL_CODE_EFFECTIVE`"
                "（2021-01-01，**复用既有常量，不另立分水岭**）两侧 ⇒ miss 回落 LLM。"
                "③ **为什么这条「推断」是安全的（本设计的承重点）**：护栏只关心「是否跨分水岭」，"
                "而 2026-08-23 与真实生成日（≤ 同一天）**必然同侧** ⇒ 判定对该推断的误差**不敏感**。"
                "判据：`tests/test_qa_direct_return_version_guard.py` 5 条 = **1 先红 + 4 控制腿**；"
                "先红在改前树上红在功能点（`assert '（预生成解析答案）…' is None`，非 TypeError），"
                "4 条控制腿两侧都绿。**「零 token 直返」这个特性保住了** —— 这正是选 (a) 不选 (b) 的全部理由。"
                "**不由票 C 解决**：票 C §4-Q2 已裁「不判读侧」（读侧加判定会把该特性本身打穿）——"
                "本票做的不是读侧加**判定**，而是给语料补**数据** + 一次**日期比较**。"
                "同 E1 是结构性走不到，但**本格是全表唯一真正的存量面**"
                "（⚠️ 这里原来写的『9 格里』已作废：那个数是开票时的缺口计数，票 C 收口后就不成立了 ⇒ "
                "**取证里不许再写会随别票变化的计数**）："
                "它读的不是 `answer_cache` 而是 **Chroma 持久语料**"
                "（`main._qa_direct_return` docstring 原文「QA 持久语义缓存直返（8-23 智谱免费 token "
                "预生成语料）」）⇒ **无 TTL、重启不清、`answer_cache.clear()` 也碰不到它**。"
                "三道护栏名义上是 score ≥0.92 / 选项指纹 / 「条文仍在库且有效」，**没有一条是版本判定** ⇒ "
                "预生成那天的法版本会被无限期当成今天的法作答。"
                "⚠️ **选项指纹护栏的覆盖面（2026-09-21 T7 补采后已从 60/279 修到 168/279）**："
                "T7 清点发现当时全仓只有 `gen_qa_corpus.py:178` 一个写侧算指纹（其余写入口不传）"
                "⇒ 279 条里存了**非空**指纹的只有 60 条（另有 75 条键在值空），护栏条件是 "
                "`q_fp and stored_fp and 不等` ⇒ 指纹这道门当时对 219 条空转（票 I 的 I-5；"
                "Owner 裁不加「部分覆盖」状态词，以取证标注）。"
                "**2026-09-21 Owner 点头补采**：按 T7 的现算口径（题面文本 × `_options_fingerprint`）"
                "回填 **108** 条（B 类存空 18 + E 类无键 90），写后非空 = **168/279**"
                "（= 带选项记录的 **100%**；既有键一个没动，写前逐条断言 + 全量备份 "
                "`fp-backfill-backup.json`）。现算与存量 **A 类不一致 0 条** ⇒ 生成器口径与现算一致。"
                "余下 111 条（57 键空 + 54 无键）是**真不带选项**的记录，指纹本来就不适用。"
                "**2026-09-21 T6 写侧补口**：补采只覆盖存量 ⇒ 另修写侧——`add_qa_pair` 在调用方"
                "未给指纹时**自算**（复用读侧同一 `_options_fingerprint`），堵住自动收录"
                "（`create_candidate`）/人工采纳（`decide_candidate`）/`qa_seeds` 三条路径的盲区；"
                "显式传入优先（`gen_qa_corpus` 逐字不变）⇒ 写侧不再是「唯一一处」。"
                "第三道**已修**（票 I 的 I-6，2026-09-20）：QA 语料写 `宪法` 而主库存成 `宪法（1982年）`、"
                "而 `canon_source` 没有这条别名 ⇒ `exact_article_lookup` 对简称**精确取空**。"
                "修法是**复用全仓唯一的源名归一规则 `_source_key`** 做一次候选回退"
                "（不加版本承诺、不另写「去括注」正则 —— 那会变成第二份规则）。"
                "读数：改前抽样 5 个宪法条号**全为 0 条**、改后**全为 1 条**"
                "（`tests/test_exact_article_lookup_sourcekey.py` 4 条 = 2 先红 + 2 控制腿）；"
                "blast radius = 主库 **99 个源名里唯一带括注的就是它**（138 行）。"
                "**命中率已于 2026-09-20 量过（票 I 的 I-1，全部本地 embedder 零花费）**，口径是三条"
                "互不合并的读数：① 自问 279/279 全部 ≥0.92（min=1.0，仪器有效性门）；"
                "② 覆盖探针 60 条抽样里「换问法」**59 条仍直返**、而「剥掉选项只剩题干」只有 **22 条**"
                "⇒ 暴露面真实存在且不需要逐字重复；③ 误命中探针（24 条自述式咨询 + 12 条语料外部门法题）"
                "**直返 0 条**（最高分 0.8287 / 0.8350）⇒ 0.92 不误伤无关问题。"
                "⚠️ 这三条都**不是线上命中率**（本地无流量分布），引用必须带口径。"
                "⚠️ 严重度是**前瞻性**的：语料 metadata 里没有生成时间戳，日期只能从 docstring 的「8-23」推，"
                "所以今天**没有证据**说它在答旧法；成立的说法是「修法时它没有任何失效机制」。"
                "⇒ 修法两种，都不在票 C 射程内：给 E2 补一次判定（则直返不再零成本），"
                "或给那份语料**打版本标 + 生成时间戳**（一次性离线，运行时按 `law_as_of` 过滤，保住零 token 直返）。",
            ),
            "写缓存闸": ("NA", "读侧。"),
            "评测可信度": (
                "BLOCKED",
                "`[fz]` 污染 judge 基线的前科**就是这一条通道**。judge 与语料同源时会「和 LLM 一起错」，"
                "一致率 ≥0.7 的自评不可信；0/1 判定必须走确定性金标。",
            ),
        },
    },
    {
        "id": "E3",
        "where": "stream() / 分支0.5 低置信反问 / 诚实拒答（变量 `msg`，零 LLM 模板）",
        "traffic": "静态可达（执行未证）",
        "cells": {
            "可达性": (
                "PASS",
                "`strategy = clarify.decide(...)` 判 clarify/refuse 即走本出口；执行层未单独取证 ⇒ 只算静态可达。",
            ),
            "引用校验": (
                "NA",
                "固定模板文本，不含模型生成的引用。REFUSE 措辞刻意命中 `quality._HONEST_REFUSE_MARKS`"
                "（依据是 `clarify.py` 里 `REFUSE_PROMPT` 上方那段注释，**认符号不认行号**），"
                "保证意外经过 self_check 也能 PASS。",
            ),
            "自检": ("DISABLED", "`record(strategy, ..., checked=False)`。"),
            "多选完整性": ("NA", "模板不是答案。"),
            "配额降级注记": ("NA", "零 LLM。"),
            "版本绊线": (
                "NA",
                "**2026-09-21 由 `GAP-ACCEPTED` 改判 `NA`（Owner 裁定；不造新词）**："
                "原判据是「挂门恒不命中 ⇒ 空门 ⇒ 接受这个缺口」，但「结构性走不到」在词表里的正确落点是 "
                "`NA`（本格不适用），`GAP-ACCEPTED` 说的是「该修但接受」——两者语义不同，登记词用错了。"
                "事实不变：本轮实测两条模板全文均不含 `_CIVIL_KEYWORDS`（诉讼时效 / 时效期间 / 时效）任一词，"
                "挂门必然恒不命中 = 空门 ⇒ 接它只会多一处假接线。",
            ),
            "写缓存闸": ("NA", "不写缓存（模板不进 cache）。"),
            "评测可信度": ("PASS", "确定性模板 ⇒ 评测读数与模型无关，可信。"),
        },
    },
    {
        "id": "E4",
        "where": "stream() / 分支0.3 合同信息确认闸（常量 `CONTRACT_CLARIFY_PROMPT`，零 LLM）",
        "traffic": "静态可达（执行未证）",
        "cells": {
            "可达性": ("PASS", "`cd[need_clarify]` 为真即走本出口（触发条件在 contract 模块）。"),
            "引用校验": ("NA", "固定模板。"),
            "自检": ("DISABLED", "`record(" + '"contract_clarify"' + ", ..., checked=False)`。"),
            "多选完整性": ("NA", "模板不是答案。"),
            "配额降级注记": ("NA", "零 LLM。"),
            "版本绊线": (
                "NA",
                "**2026-09-21 由 `GAP-ACCEPTED` 改判 `NA`（同 E3，Owner 裁定；不造新词）**："
                "`prompts.py::CONTRACT_CLARIFY_PROMPT` 全文无时效表述 ⇒ 挂门成空门 ⇒ 属「本格不适用」"
                "（`NA`），而非「该修但接受」（`GAP-ACCEPTED`）。事实不变。",
            ),
            "写缓存闸": ("NA", "不写缓存。"),
            "评测可信度": ("NA", "合同类不在 `evals/` 冻结集内（frozen-cases-v2 20 例 / holdout 5 例均为法律问答）。"),
        },
    },
    {
        "id": "E5",
        "where": "stream() / 分支0.3 合同报告流式增量（变量 `piece`）",
        "traffic": "有执行取证（真实配置下入口可达；报告产出未端到端取证）",
        "cells": {
            "可达性": (
                "PASS",
                "`pre[contract_data]` 在场且不需澄清 ⇒ 流式产出报告。"
                "**票 H 补的真实配置读数**（`dispatch-output/hij-h-20260920/probe_contract_reachability.py`，"
                "只读、不桩判定函数、不调模型）：一份 4 条的真实租赁合同文本下 "
                "`is_contract_review=True` / `need_clarify=False` / `n_blocks=5` / `n_docs=24` / "
                "`main._cacheable=True` / `cache_key` 非 None / `feature_router=True` / "
                "`feature_multi_analyze=True` ⇒ 本分支的入口在真实配置下确实进得去"
                "（读数 `17-reachability-realconfig.json`）。⚠️ 仍**未**端到端取证的是"
                "「一次真实模型调用产出一份真实报告」——那要花钱，属评测批事项；"
                "本节的两道闸判据一律在端点级用替身模型取得。",
            ),
            "引用校验": ("PASS", "`bad = citation_verify(answer)` ⇒ 未收录引用追加告警注记（见 E6 帧）。"),
            "自检": (
                "DISABLED",
                "`record(" + '"contract_review"' + ", ..., checked=False)` ⇒ 合同分支**不跑** `quality.self_check`。",
            ),
            "多选完整性": ("NA", "报告体，非选择题。"),
            "配额降级注记": (
                "PASS",
                "票 H-2 已接：`degraded = use_router and flag_degraded`（收口点求值）⇒ 追加 NOTE_QUOTA 注记帧"
                "（**本表 E15**，与流式 E13 同族）。判据：端点级 `tests/test_contract_exit_gates.py` 的 "
                "`test_degraded_contract_report_carries_quota_note`（先红：断言原文 "
                "`assert '\\n\\n> 注：模型配额紧张，本回答仅供参考。' in '<报告正文>'`）+ 控制腿 "
                "`test_control_non_degraded_report_has_no_quota_note`。"
                "**先量的收场（打桩计数，非推断）**：三次 config 全抛异常 ⇒ 上抛到外层 `except Exception` ⇒ "
                "error 帧「服务暂时无响应，请稍后重试」（实测 `boom_astream_calls=3`）；"
                '**三次尝试全「空内容且无异常」 ⇒ `answer == ""` ⇒ 既不产 error 帧也不产任何注记帧（静默收场）**'
                "—— 票面 H-2 假设的「只能落到外层 error 帧」在这一支**不成立**，"
                "读数在 `dispatch-output/hij-h-20260920/00-smoke.stdout.txt` 与 "
                "`test_contract_failover_endings_are_characterized` 落盘的 `contract-failover-endings.json`。"
                "⚠️ 如实登记未覆盖：**「静默空」这一支今天仍不受保护**"
                "（合同分支是唯一不产 error 帧的生成出口；补 error 帧会改用户可见行为、超票 H-2 射程 ⇒ "
                "须 Owner 另裁，别当成已修）。",
            ),
            "版本绊线": (
                "GAP-ACCEPTED",
                "票 C §4a-Q1（`cd29211`）裁定不接：合同事实来自**上传文本**而非用户自述，"
                "`_fast_path_fact_texts` 那套取法在此不成立，硬接只能接出一道恒不命中的空门。"
                "遗留风险「按现行法评估 2019 年签的合同」无人管 ⇒ Owner 若不接受须另开票。",
            ),
            "写缓存闸": (
                "PASS",
                "票 H-1 + H-2 已接，认形状 `if cache_key and not bad and not degraded:`"
                '（本合同分支里唯一的 `answer_cache.put(..., model="contract_review")` 就在它下面）。'
                "两道条件的由来：`bad = citation_verify(answer)` 在**上一行**就算好了（判定本来就有，"
                "不需要新造），漏的只是「有没有看它」；`degraded` 与 E15 同源。"
                "判据：`test_bad_citation_report_is_not_cached`（先红原文 "
                "`AssertionError: 引用未收录的合同报告进了缓存：[{... 'model': 'contract_review'}]`，"
                "即改前该报告确实以「无告警」形态入了缓存）+ 控制腿 "
                "`test_control_good_report_is_still_cached_once` + 降级腿 "
                "（`test_degraded_contract_report_carries_quota_note` 里的 `assert sink == []` 一条）。"
                "⚠️ 一起登记的代价：带告警（或降级）的报告从此不进缓存 ⇒ 同一份合同重问会重烧 token。"
                "Owner 若不接受，替代方案是「照写，但把注记一并写进被缓存的那份」——那要改缓存条目语义，"
                "须另裁（本格不预设该结论）。"
                "⚠️ 认形状不认行号：本仓行号已漂过五次，最近一次是被本表自己的取证改动挤掉的。",
            ),
            "评测可信度": ("NA", "不在冻结集内。"),
        },
    },
    {
        "id": "E6",
        "where": "stream() / 分支0.3 合同引用告警注记帧（变量 `note`）",
        "traffic": "条件命中（bad 非空）",
        "cells": {
            "可达性": ("PASS", "`bad` 非空才有这一帧；它本身就是 E5 的告警呈现方式。"),
            "引用校验": ("PASS", "本帧即引用校验的产物（`citation_verify` 结果）。"),
            "自检": ("NA", "注记帧，非答案。"),
            "多选完整性": ("NA", "注记帧。"),
            "配额降级注记": ("NA", "同上。"),
            "版本绊线": ("NA", "注记帧不参与版本判定。"),
            "写缓存闸": (
                "PASS",
                "票 H-1 已接。改前：注记在 `answer += note` 之后才追加，而写缓存发生在**注记之前、且不看 `bad`**"
                " ⇒ 被缓存的那份永远不含本条注记，零 token 复播时告警消失（本格与 E5 是同一缺陷的两面）。"
                "改后：`bad` 非空 ⇒ 整块 `put` 不执行 ⇒ **不存在「缓存掉告警」这个形状**。"
                "判据：`test_bad_citation_report_is_not_cached` 同一条用例同时断言"
                "「注记帧仍在下发」与「缓存零写入」。",
            ),
            "评测可信度": ("NA", "不在冻结集内。"),
        },
    },
    {
        "id": "E7",
        "where": "stream() / 分支1 缓冲轻量整答（变量 `answer`，来自 `_light_buffered`）",
        "traffic": "零流量（配置不可达）",
        "cells": {
            "可达性": (
                "DISABLED",
                "**三份独立证据同向**：① `docs/capability-matrix.md` §0 部署态角色表只有 longcat_text_flag / "
                "vision_omni / voice_omni，无 text-light；② 票 G `measure_roles.py` 读数 tier 全集=['flag'] ⇒ "
                "`has_role('text','light')=False`；③ `test_flagship_quality.py` docstring 第 3 行原文就写着："
                "「text 无 light 档 ⇒ use_light=False」。⇒ S5 那道门今天**没有线上流量经过**。",
            ),
            "引用校验": (
                "PASS",
                "经 `quality.self_check`：该函数体内 `R.citation_verify(a, in_kb=in_kb)` 全文唯一一处"
                "（被调方定义在 `retrieval.py`，`quality.py` 只是调用方）—— 本轮查证，"
                "别误判成「轻量出口不查引用」。差异只在**呈现**：流式出口追加告警注记帧，"
                "这里由 verdict 驱动升级/注记。",
            ),
            "自检": (
                "PASS",
                "`_light_buffered_locked` 内 `quality.self_check(raw, ctx_present)`（至多一次升级旗舰重答后再判）。",
            ),
            "多选完整性": (
                "PASS",
                "票 J-2 已接：调用点复用流式那份**纯函数** `quality.multi_incomplete`（全仓仍只有这一处规则，"
                "没有写第二份判定），症状命中 ⇒ 追加注记帧（**本表 E16**）+ 拦缓存 + 落 "
                "`kind=”multi_incomplete”` 日志（与流式 E11 同形状）。注记措辞也收成**唯一真源** "
                "`main.NOTE_MULTI_INCOMPLETE`（流式 E11 一并改读它，防两处文案漂移）。"
                "判据：端点级 `tests/test_light_exit_gates.py` —— 先红 "
                "`test_light_path_flags_multi_incomplete_and_blocks_cache`（改前红因原文 "
                "`AssertionError: 多选漏答的答复进了缓存：[{… 'model': ''}]`）+ 控制腿 "
                "`test_control_light_path_does_not_flag_full_multi_answer` / "
                "`test_control_light_path_plain_question_still_cached`（两条都断言「同一请求形状照常写一次"
                "缓存」⇒ 上一条的 `sink == []` 是被闸拦下，不是「压根没有 cache_key」）。"
                "⚠️ 本出口仍**零流量**（见「可达性」格）⇒ 本格是「代码正确」，不是「线上生效」。",
            ),
            "配额降级注记": (
                "PASS",
                "轻量五个 return 点里有 NOTE_QUOTA（配额耗尽不升级）与 NOTE_COMPLEX（升级后仍 FAIL）。",
            ),
            "版本绊线": (
                "PASS",
                "S5 接 + 本轮补上「缺省落当日」这一小条（`_fast_path_law_as_of`）。判据强度：全量变异复审 4/4 全杀"
                "（`dispatch-output/s5-followup-20260920/02-mutation-verdicts.txt`），含 reason 双支各一条端点级用例。"
                "⚠️ 但本出口零流量 ⇒ 这格是「代码正确」，不是「线上生效」。"
                "⚠️ **别说成「契约第①半已搬齐」**：`create_run` 那半还含「随 run 持久化」与「被工具 cutoff/"
                "证据有效性判定消费」，快车道无 run 对象 ⇒ 本值只有绊线门一个消费者，检索 cutoff 不随它变"
                "（ADR-018 已知残留 ④）。",
            ),
            "写缓存闸": (
                "PASS",
                "票 J-2 已接，认形状 `if (\\n cache_key\\n and not res.degraded\\n and "
                '_cache_write_ok(pre, answer)\\n and res.verdict == "pass"\\n and not multi_bad\\n and '
                "not res.law_version_hit\\n ):`——**六**条件，与流式 E8 那一组逐条对齐："
                "`cache_key`（安全形态）· `not res.degraded`（票 J 新增的**独立**降级信号，对应流式的 "
                "`not flag_degraded`）· `_cache_write_ok(pre, answer)`（确定性写闸，此前轻量侧**无任何"
                '对应物**）· `res.verdict == "pass"`（自检 PASS）· `not multi_bad`（多选漏答不入缓存）· '
                "`not res.law_version_hit`（命中版本绊线不入缓存）。"
                "归因粒度也已对齐：票 J 给 `_LightResult` 补了 `degraded: bool`（**不复用 verdict**），"
                "并把它记进 account 日志（`observability._ACCOUNT_FIELDS` 已登记 `degraded`）⇒ "
                "「自检 FAIL」与「配额降级」两条原因能同时出现在一张日志里"
                '（改前只能从 verdict 里那个 `"low_quota"` 字符串反推）。'
                "判据：端点级 `tests/test_light_exit_gates.py` 四条 —— 先红 "
                "`test_light_path_cache_write_ok_blocks_foreign_citation`（改前红因原文 "
                "`AssertionError: 引用不在检索条文内的答案进了缓存：[{… 'model': ''}]`）与 "
                "`test_light_path_degraded_signal_is_independent_from_verdict`（改前红因 "
                "`assert None is True`，即日志里根本没有 `degraded` 键）；控制腿 "
                "`test_control_light_path_cache_write_ok_allows_retrieved_citation` 与 "
                "`test_control_light_path_non_degraded_records_false_and_caches`。"
                "⚠️ 认形状不认行号：本仓行号已漂过五次，最近一次是被本表自己的取证改动挤掉的。"
                "⚠️ 本出口仍**零流量** ⇒ 本格是「代码正确 + 两条出口对称」，不是「线上生效」。",
            ),
            "评测可信度": (
                "DISABLED",
                "分支不可达 ⇒ 任何评测读数里它出现 0 次。**别把「改完评测一分没变」当它被验证过**"
                "（本轮实测：frozen-cases-v2 20 例、holdout 5 例均不含可触发该门的形态）。",
            ),
        },
    },
    {
        "id": "E8",
        "where": "stream() / 分支2 旗舰流式增量（变量 `piece`）",
        "traffic": "有执行取证（主承流量）",
        "cells": {
            "可达性": (
                "PASS",
                "票 A 执行取证：默认配置下三种法律问句形态**全部**走本出口那条 `stream_with_retry`。"
                "⇒ 本表最该修的一格在这里。",
            ),
            "引用校验": (
                "PASS",
                "`citation_verify(answer)` ⇒ 未收录引用追加注记（E10 帧）+ 落 citation_anomaly 日志。",
            ),
            "自检": ("PASS", "`quality.self_check(answer, bool(pre['sources']))`；⚠️ 闲聊豁免（intent != chitchat）。"),
            "多选完整性": ("PASS", "`quality.multi_incomplete(...)` ⇒ 漏答追加注记（E11 帧）且不写缓存。"),
            "配额降级注记": ("PASS", "`flag_degraded` ⇒ 追加 NOTE_QUOTA（E13 帧），明说降级不静默。"),
            "版本绊线": (
                "PASS",
                "**票 C/S6 已接**（本表立表读出的那一格：唯一承流量的生成出口没门）。判定仍只在 "
                "`limitation_calc.law_version_crosses_watershed`；两个答案来源（E8 流式 join 与 "
                "E9 `_invoke_llm` 兜底）各过一次**同一份** `_law_version_gate`（票 C §5-2 授权把该函数"
                "的入参从 `_LightResult` 改成答案文本，S5 的五个 return 点行为不变）。"
                "判据强度：端点级 SSE 定向 14 条（`tests/test_stream_exit_law_version_gate.py`，"
                "collect-only 实测 14 collected，改前先红 2 条）+ 全量变异 **7/7 全杀**"
                "（r3：`dispatch-output/s6-stream-gate-20260920/mut-out-r3/mutation-report-full.json`，"
                "分母恒 `tests=1378 errors=0`，每条各自产出 `newly_red` 非空）。"
                "**前两轮的读数为什么不能用**：r1 里 C-M1/C-M2 记的是 `denominator-drift`"
                "（变异体把整套打崩到 tests=5，执行器按规矩拒绝把它算成杀）；r2 修好后只跑到第 4 条就断在"
                "会话轮次上限上。基线余 2 条红是 `tests/test_eval_agent.py` 的 `release_eligible` 断言，"
                "**在没有本票改动的 b40076b 副本树上同样红、在 live 树 18/18 绿** ⇒ 属副本缺未跟踪资产，"
                "与本票无关；它在基线和 7 个变异体里是同一集合，故差分判据不受影响（口径见 "
                "`docs/handoff-independent-sessions-20260919.md` 环境第 5 条）。"
                "开关默认关下的零变化证据是**端点级逐帧 sha**，不是直接调被测函数那台旧仪器"
                "（它对调用点的改动不可见）。⚠️ 采集口最初是**跨树**比的（改前在 `b40076b` 副本、"
                "改后在 live），那不成判据；接手时已在**同一副本 lane** 重采改后侧"
                "（`dispatch-output/s6-stream-gate-20260920/02-stream-AFTER-in-copytree.json`），"
                "两侧 sha 逐字相同 ⇒ 现在是同 lane 的读数。"
                "⚠️ 开关 `fast_path_law_version_check` 仍默认 False ⇒ 本格是「已接线且分支可达」，"
                "**不是**「线上已生效」；生效属评测批预登记事项。"
                "⚠️ 本出口与 E7 同享 `_fast_path_law_as_of`：基准日只有绊线门一个消费者，快车道的检索 "
                "cutoff 不随它变（ADR-018 已知残留 ④），且**别读成「R15-lite 契约第①半已搬齐」**。",
            ),
            "写缓存闸": (
                "PASS",
                "五条件（票 C §5-6 由四条改来）：`cache_key` + `not flag_degraded` + "
                "`_cache_write_ok(pre, answer)` + `not multi_bad` + **`not law_version_hit`**。"
                "⚠️ 认形状不认行号：加到第五条后 ruff-format 把它拆成多行 `if ( … ):`（`if (` 与 `cache_key`"
                " 分在两行），「同一行同时出现 `_cache_write_ok` 与 `not multi_bad`」这个**定位用**特征已不再成立 "
                "（票面 §5-6 写的是改前形状）；现在的唯一形状是「全文件恰好一块含 "
                "`_cache_write_ok(pre, answer)` 的 `if (` 块」，`verify_doc_claims.py` 就按这条定位。"
                "新增的第五条件配了端点级用例 + 控制腿（开关关时确实写一次），并被变异 C-M3 实测能杀"
                "（删第五条件 ⇒ 全量差分新增红；票 G F5 的前科就是这道闸零敏感）。",
            ),
            "评测可信度": ("PASS", "真实生成路径；但仍须 `no_cache` 跑（否则被 E1/E2 的缓存直返污染）。"),
        },
    },
    {
        "id": "E9",
        "where": "stream() / 分支2 流式空答后的 `_invoke_llm` 兜底整答（变量 `answer`）",
        "traffic": "条件命中（流式返回空）",
        "cells": {
            "可达性": ("PASS", "流式 `not answer` ⇒ 走 `_invoke_llm(messages, flag_llm)` 非流式兜底。"),
            "引用校验": ("PASS", "兜底产物与流式产物共用其后同一套注记/写缓存判定。"),
            "自检": ("PASS", "同上（answer 已合并后统一判）。"),
            "多选完整性": ("PASS", "同上。"),
            "配额降级注记": ("PASS", "同上（flag_degraded 判定在它之后）。"),
            "版本绊线": (
                "PASS",
                "**票 C/S6 §5-3 点名的第二个答案来源，已接**：`stream()` 里 `_invoke_llm` 兜底产出的"
                "`answer` 与流式 join 是两个不同来源，只接流式 = 流式一空答门就整体消失"
                "（S5 那个「漏 return 点」换了形状）。判据：端点级用例 "
                "`test_fallback_answer_also_passes_the_gate` + 它的控制腿 "
                "`test_control_leg_writes_cache_on_fallback_path_when_switch_off`，"
                "加上变异 **C-M1**（删掉兜底那一行门）实测被杀。"
                "⚠️ 这条以前**在测试里也打不到**：旧 `_sse_harness` 的 `flag_llm` 是裸 `object()`，"
                "`_invoke_llm` 必抛 AttributeError 被 `except` 吞掉 ⇒ E9 恒等于「兜底也失败」，"
                "任何只接在兜底分支上的代码都测不出红。本轮给它加了 `fallback_text` 参数（可 `invoke` 的"
                "替身）才第一次可达 ⇒ 登记一条仪器事实：以前关于 E9 的「已覆盖」说法都要打折。",
            ),
            "写缓存闸": ("PASS", "同 E8（五条件）。"),
            "评测可信度": ("PASS", "同 E8。"),
        },
    },
    {
        "id": "E10",
        "where": "stream() / 分支2 引用告警注记帧（变量 `note`）",
        "traffic": "条件命中（bad_cites 非空）",
        "cells": {
            "可达性": ("PASS", "`citation_verify` 有未收录引用才发。"),
            "引用校验": ("PASS", "本帧即其产物。"),
            "自检": ("NA", "注记帧。"),
            "多选完整性": ("NA", "注记帧。"),
            "配额降级注记": ("NA", "注记帧。"),
            "版本绊线": ("NA", "注记帧不参与判定。"),
            "写缓存闸": (
                "PASS",
                "⚠️ 细节：注记在 `answer += note` 之后才写缓存 ⇒ 与 E5/E6 的顺序**相反**。"
                "这个不一致就是本表存在的理由（同一个形状两处实现，一处防住了错答复播、一处没有）。",
            ),
            "评测可信度": ("NA", "注记帧。"),
        },
    },
    {
        "id": "E11",
        "where": "stream() / 分支2 多选漏答注记帧（变量 `note`）",
        "traffic": "条件命中（multi_bad）",
        "cells": {
            "可达性": ("PASS", "`quality.multi_incomplete` 为真才发。"),
            "引用校验": ("NA", "注记帧。"),
            "自检": ("NA", "注记帧。"),
            "多选完整性": ("PASS", "本帧即其产物，且 `not multi_bad` 是写缓存第四条件 ⇒ 漏答不入缓存。"),
            "配额降级注记": ("NA", "注记帧。"),
            "版本绊线": ("NA", "注记帧。"),
            "写缓存闸": ("PASS", "见 E10 同一处。"),
            "评测可信度": ("NA", "注记帧。"),
        },
    },
    {
        "id": "E12",
        "where": "stream() / 分支2 自检 FAIL 的 NOTE_COMPLEX 注记帧",
        "traffic": "条件命中（self_check FAIL 且非 study_aid）",
        "cells": {
            "可达性": ("PASS", "自检 FAIL 且 intent != study_aid 才追加（法考只停写缓存不加注，审查 I3）。"),
            "引用校验": ("NA", "注记帧。"),
            "自检": ("PASS", "本帧即自检 FAIL 的显式呈现（不静默）。"),
            "多选完整性": ("NA", "注记帧。"),
            "配额降级注记": ("NA", "与配额无关（配额走 E13）。"),
            "版本绊线": ("NA", "注记帧。"),
            "写缓存闸": ("PASS", "自检 FAIL ⇒ `sv.ok` 假 ⇒ 整块 put 不执行。"),
            "评测可信度": ("NA", "注记帧。"),
        },
    },
    {
        "id": "E13",
        "where": "stream() / 分支2 回退不可用的 NOTE_QUOTA 注记帧",
        "traffic": "条件命中（flag_degraded 且非闲聊）",
        "cells": {
            "可达性": ("PASS", "`use_router and flag_degraded and answer and intent != chitchat`。"),
            "引用校验": ("NA", "注记帧。"),
            "自检": ("NA", "注记帧。"),
            "多选完整性": ("NA", "注记帧。"),
            "配额降级注记": ("PASS", "本帧即「降级明说」的载体（S2：不静默烧耗尽模型）。"),
            "版本绊线": ("NA", "注记帧。"),
            "写缓存闸": ("PASS", "`not flag_degraded` 是第四条件之一 ⇒ 降级答案不入缓存（防缓存掉免责注）。"),
            "评测可信度": ("NA", "注记帧。"),
        },
    },
    {
        # 票 C/S6 新增的第 14 条正文出口：旗舰流式出口命中版本绊线时追加的那一帧 NOTE_LAW_VERSION。
        # 为什么必须单独成行而不是并进 E8：本表的一条铁律是「每条 content 帧都要有自己的格子」，
        # 哨兵 `test_main_py_exits_are_all_registered` 按 `scan_content_yields` 的**条数**对账，
        # 少一行就红（这不是 flaky，`test_registry_scope_is_whole_backend_not_just_main_py` 也钉同一件事）。
        "id": "E14",
        "where": "stream() / 分支2 版本绊线命中的 NOTE_LAW_VERSION 注记帧",
        "traffic": "条件命中（law_version_hit 且答案非空）",
        "cells": {
            "可达性": (
                "PASS",
                "票 C §6-⑦：真实配置（未改 `.env`、未桩 `has_role`/`complexity.assess`）下打桩计数 "
                "`_law_version_gate` 在本分支被调用的次数 > 0 —— 这条就是 S5 缺的那一步（E7 零流量）。",
            ),
            "引用校验": ("NA", "注记帧。"),
            "自检": ("NA", "注记帧。"),
            "多选完整性": ("NA", "注记帧。"),
            "配额降级注记": ("NA", "与配额无关（配额走 E13）；与 E12/E13 同为「流式已发出 ⇒ 追加一帧」形状。"),
            "版本绊线": ("PASS", "本帧即其产物（不静默替换答案、不收回已吐出的帧 —— 票 C §2b 第四次沿用）。"),
            "写缓存闸": (
                "PASS",
                "命中时 `answer` 已含本帧文本，但**它不进缓存**（第五条件 `not law_version_hit`）⇒ "
                "不存在「缓存掉注记」问题；反向风险（错版答复被固化）由同一道闸拦。",
            ),
            "评测可信度": (
                "NA",
                "注记帧。⚠️ 但**它的存在会让整答文本变长**：拿 E8 的答复对分/对指纹的评测，"
                "开开关前后不是同一个字符串（本开关从未在任何评测批打开过 ⇒ 目前无既有结果受影响）。",
            ),
        },
    },
    {
        # 票 H/H-2 新增的第 15 条正文出口：合同报告降级（`flag_degraded`）时追加的那一帧 NOTE_QUOTA。
        # 为什么必须单独成行而不是并进 E5：本表的一条铁律是「每条 content 帧都要有自己的格子」——
        # `test_main_py_exits_are_all_registered` 按 `scan_content_yields` 的**条数**对账，少一行就红。
        # 另一条理由与 E14 相同：并进 E5 会让「报告本体」与「降级免责」共用一个格子，归因反而变粗。
        "id": "E15",
        "where": "stream() / 分支0.3 合同报告降级产出的 NOTE_QUOTA 注记帧",
        "traffic": "条件命中（flag_degraded 且报告正文非空）",
        "cells": {
            "可达性": (
                "PASS",
                "`degraded = use_router and flag_degraded`（在收口点求值、由 `if answer:` 兜住空答）。"
                "票 H-2 打桩计数：把 `_safe_pick` 的第三元（degraded）桩成 True 后，本帧在**端点级**"
                "实测出现（`tests/test_contract_exit_gates.py::test_degraded_contract_report_carries_quota_note`，"
                "改前先红、改后绿）。⚠️ 这条与 E14 的性质不同：E14 的读数是**真实配置**下打桩计数，"
                "本条是**桩住一个运行时状态**（默认模型被标不可用）后计数 ⇒ 它证明「接线有反应」。"
                "**并且已量清它今天不会命中**：真实配置下 `registry.is_unavailable(registry.default_key())"
                "=False`（默认模型 `agent_text_37max0608` 可用）⇒ `flag_degraded` 恒假 ⇒ 本帧**零命中**"
                "（读数 `dispatch-output/hij-h-20260920/17-reachability-realconfig.json`）。"
                "⇒ 如实登记：本格是「接线正确、今天不生效」，不是「线上已生效」。",
            ),
            "引用校验": ("NA", "注记帧。"),
            "自检": ("NA", "注记帧（且合同分支本就不跑 `quality.self_check`，见 E5 的「自检」格）。"),
            "多选完整性": ("NA", "注记帧；报告体非选择题。"),
            "配额降级注记": (
                "PASS",
                "本帧即合同分支「降级明说」的唯一载体（S2 / E13 同族：不静默烧耗尽模型）。"
                "合同分支此前没有任何降级出口 ⇒ 用户看到一份「看起来正常」的报告。",
            ),
            "版本绊线": ("NA", "注记帧不参与版本判定（合同分支的版本绊线另见 E5 的「版本绊线」格）。"),
            "写缓存闸": (
                "PASS",
                "`not degraded` 是 E5 写闸的第二道条件 ⇒ 降级报告不进缓存（否则零 token 复播时本帧消失，"
                "与 E13 的 `not flag_degraded` 完全同族）。",
            ),
            "评测可信度": ("NA", "注记帧；合同类不在 `evals/` 冻结集内。"),
        },
    },
    {
        # 票 J 新增的正文出口：轻量缓冲出口（E7）在多选漏答症状命中时追加的那一帧。
        # 为什么单独成行而不是并进 E7：本表铁律「每条 content 帧都要有自己的格子」，
        # `test_main_py_exits_are_all_registered` 按 `scan_content_yields` 的**条数**对账，少一行就红。
        "id": "E16",
        "where": "stream() / 分支1 缓冲轻量出口的多选漏答注记帧（常量 `NOTE_MULTI_INCOMPLETE`）",
        "traffic": "零流量（随 E7 不可达）",
        "cells": {
            "可达性": (
                "DISABLED",
                "`use_light` 恒假（`llm_registry` 实配只有 `('text','flag')`，见 E7 的「可达性」格）⇒ "
                "本帧今天**零流量**。端点级判据把它打通了："
                "`tests/test_light_exit_gates.py::test_light_path_flags_multi_incomplete_and_blocks_cache` "
                "（夹具把 tier/准入/`has_role` 造真）。⚠️ 这**不是**「线上生效」的证据。",
            ),
            "引用校验": ("NA", "注记帧。"),
            "自检": ("NA", "注记帧（自检已在 `_light_buffered_locked` 内跑过，见 E7 的「自检」格）。"),
            "多选完整性": ("PASS", "本帧即其产物，且 `not multi_bad` 是写闸条件之一 ⇒ 漏答不入缓存。"),
            "配额降级注记": ("NA", "与配额无关（配额走 `NOTE_QUOTA`，在 `_light_buffered_locked` 内）。"),
            "版本绊线": ("NA", "注记帧不参与版本判定。"),
            "写缓存闸": (
                "PASS",
                "注记在 `answer += NOTE_MULTI_INCOMPLETE` 之后才写缓存，且 `not multi_bad` 是写闸条件 ⇒ "
                "**不存在「缓存掉注记」这个形状**（与流式 E10/E11 同族：那里靠 `not multi_bad` 兜住）。",
            ),
            "评测可信度": ("DISABLED", "分支不可达 ⇒ 评测读数里出现 0 次（同 E7）。"),
        },
    },
]

# agent 路径**不在本表**（它不是 `stream()` 的出口，闸门在 `agent/verifier.py`），
# 但登记一句免得下任重画一遍：`AGENT_ENABLED=False` 时线上流量 100% 走本表登记的这些出口。
# （这里**不写条数**：那是会随别票变化的计数，写死了下一票就得回来改。）
OUT_OF_SCOPE: dict = {
    "agent_path": "版本绊线由 `settings.law_version_tripwire_check` 管（默认 False），判定在 `agent/verifier.py`；"
    "它消费的是**落库后**的 `run.law_as_of`（`create_run` 已 `or date.today()`）⇒ 那边 None 是异常、这里是日常。",
    "contract_file_endpoint": "`/api/chat/file` 只回文本给前端，不吐 SSE 正文帧 ⇒ 不属于「会吐答复文本的出口」。",
}

# 豁免清单（哨兵要求每项带票号或 Owner 裁决；空清单也要显式存在）。
EXEMPTIONS: list[dict] = []
