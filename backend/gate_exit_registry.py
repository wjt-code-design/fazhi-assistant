"""/api/chat「出口 × 闸门」登记表 · **真源**（ADR-016：借 NeMo 的槽位声明形状，不引依赖）。

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
                "GAP-TODO",
                "票 C/S6 §4-Q2。**结构性走不到**：收口点的门在生成分支上，而本出口在门之前就 return ⇒ "
                "挂到收口处的门对缓存复用型答复永远不命中；且库里已有条目不受新门影响。",
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
            "版本绊线": ("GAP-TODO", "票 C/S6 §4-Q2。同 E1：预生成语料按生成当日版本作答，事实跨分水岭时无人判。"),
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
                "（`clarify.py:285-286` 注释），保证意外经过 self_check 也能 PASS。",
            ),
            "自检": ("DISABLED", "`record(strategy, ..., checked=False)`。"),
            "多选完整性": ("NA", "模板不是答案。"),
            "配额降级注记": ("NA", "零 LLM。"),
            "版本绊线": (
                "GAP-ACCEPTED",
                "本轮实测两条模板全文均不含 `_CIVIL_KEYWORDS`（诉讼时效 / 时效期间 / 时效）任一词，"
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
            "版本绊线": ("GAP-ACCEPTED", "同 E3：`prompts.py::CONTRACT_CLARIFY_PROMPT` 全文无时效表述 ⇒ 挂门成空门。"),
            "写缓存闸": ("NA", "不写缓存。"),
            "评测可信度": ("NA", "合同类不在 `evals/` 冻结集内（frozen-cases-v2 20 例 / holdout 5 例均为法律问答）。"),
        },
    },
    {
        "id": "E5",
        "where": "stream() / 分支0.3 合同报告流式增量（变量 `piece`）",
        "traffic": "静态可达（执行未证）",
        "cells": {
            "可达性": ("PASS", "`pre[contract_data]` 在场且不需澄清 ⇒ 流式产出报告。"),
            "引用校验": ("PASS", "`bad = citation_verify(answer)` ⇒ 未收录引用追加告警注记（见 E6 帧）。"),
            "自检": (
                "DISABLED",
                "`record(" + '"contract_review"' + ", ..., checked=False)` ⇒ 合同分支**不跑** `quality.self_check`。",
            ),
            "多选完整性": ("NA", "报告体，非选择题。"),
            "配额降级注记": (
                "GAP-TODO",
                "待开票：合同分支没有 NOTE_QUOTA/降级出口，failover 全灭时只能落到外层 error 帧"
                "（不在本表范围）⇒ 用户看到「无响应」而不是「已降级」。",
            ),
            "版本绊线": (
                "GAP-ACCEPTED",
                "票 C §4a-Q1（`cd29211`）裁定不接：合同事实来自**上传文本**而非用户自述，"
                "`_fast_path_fact_texts` 那套取法在此不成立，硬接只能接出一道恒不命中的空门。"
                "遗留风险「按现行法评估 2019 年签的合同」无人管 ⇒ Owner 若不接受须另开票。",
            ),
            "写缓存闸": (
                "GAP-TODO",
                "待开票（本表 2026-09-20 新发现）：`answer_cache.put(..., model=" + '"contract_review"' + ")` "
                "发生在追加引用告警注记**之前**，且本出口不跑自检 ⇒ "
                "**引用未收录的合同报告会以「无告警」的形态进缓存并被零 token 复播**。"
                "⚠️ 判定其实**早就算好了**：`bad = citation_verify(answer)` 在 `:1883`，"
                "写闸在 `:1884` 却没看它 ⇒ 修法近乎免费（`if cache_key and not bad:`），"
                "代价只是带告警的报告不进缓存。全仓三处写闸（`:1886` / `:1936` / `:2074`）"
                "条件集互不相同，另见 E7、E6 两格。",
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
                "GAP-TODO",
                "待开票（与 E5 同一个缺陷的另一面）：注记没进被缓存的那份 answer ⇒ "
                "引用未收录的合同报告被零 token 复播时**丢掉那条告警**。",
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
                "经 `quality.self_check` 内的 `citation_verify`（`quality.py:63`）—— 本轮查证，"
                "别误判成「轻量出口不查引用」。差异只在**呈现**：流式出口追加告警注记帧，"
                "这里由 verdict 驱动升级/注记。",
            ),
            "自检": (
                "PASS",
                "`_light_buffered_locked` 内 `quality.self_check(raw, ctx_present)`（至多一次升级旗舰重答后再判）。",
            ),
            "多选完整性": (
                "GAP-TODO",
                "待开票（本表新发现）：`multi_incomplete` 全仓只有流式出口一处调用 ⇒ "
                "轻量缓冲路径的**多选漏答零防护**，而法考多选题恰是最可能被路由到轻量档的题型。",
            ),
            "配额降级注记": (
                "PASS",
                "轻量五个 return 点里有 NOTE_QUOTA（配额耗尽不升级）与 NOTE_COMPLEX（升级后仍 FAIL）。",
            ),
            "版本绊线": (
                "PASS",
                "S5 接 + 本轮补契约第①半（`_fast_path_law_as_of`）。判据强度：全量变异复审 4/4 全杀"
                "（`dispatch-output/s5-followup-20260920/02-mutation-verdicts.txt`），含 reason 双支各一条端点级用例。"
                "⚠️ 但本出口零流量 ⇒ 这格是「代码正确」，不是「线上生效」。",
            ),
            "写缓存闸": (
                "GAP-TODO",
                "待开票（本表新发现）：两条闸**字面条件集交集只有 `cache_key`**"
                '（`:1933` = cache_key / `res.verdict == "pass"` / `not res.law_version_hit`；'
                "`:2071` = cache_key / `not flag_degraded` / `_cache_write_ok` / `not multi_bad`）。"
                '逐条对：流式的 `not flag_degraded` 在轻量侧由 `verdict == "pass"` 承担'
                '（配额耗尽分支 `:1249-1251` 把 verdict 写成 `v.reason or "low_quota"`）⇒ 不是漏闸，'
                "但**降级与自检 FAIL 两个信号被合进同一个条件**，归因粒度比流式粗。"
                "轻量侧真正**无任何对应物**的两件：`_cache_write_ok`（确定性写闸，全文只在 `:2071` 出现）"
                "与 `not multi_bad`（`quality.multi_incomplete` 全文只在 `:2030` 流式侧调用）"
                "⇒ 同一个「拦错答进缓存」的形状两份实现、强弱不同（`[PL#13]`）。"
                "已有的那条 `not law_version_hit` 本轮已配端点级用例（能杀删闸变异）。",
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
                "GAP-TODO",
                "**票 C/S6 正题**：这是唯一承流量的生成出口，而它没有版本判定。票面已补前置"
                "（§5-4 必须传 `_fast_path_law_as_of(body)`、§6-③ 零变化必须端点级逐帧、§6-④ 变异跑全量）。",
            ),
            "写缓存闸": (
                "PASS",
                "四条件：cache_key + `not flag_degraded` + `_cache_write_ok(pre, answer)` + `not multi_bad`。"
                "⚠️ 票 C 接上门后必须加第五条件 `not law_version_hit`，且**必须连带一条能杀它的测试**（S5 的前科）。",
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
            "版本绊线": ("GAP-TODO", "票 C/S6 §2c 点名的**第二个答案来源**：只接流式不接兜底 = 门留了个口子。"),
            "写缓存闸": ("PASS", "同 E8。"),
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
]

# agent 路径**不在本表**（它不是 `stream()` 的出口，闸门在 `agent/verifier.py`），
# 但登记一句免得下任重画一遍：`AGENT_ENABLED=False` 时线上流量 100% 走上面 13 条。
OUT_OF_SCOPE: dict = {
    "agent_path": "版本绊线由 `settings.law_version_tripwire_check` 管（默认 False），判定在 `agent/verifier.py`；"
    "它消费的是**落库后**的 `run.law_as_of`（`create_run` 已 `or date.today()`）⇒ 那边 None 是异常、这里是日常。",
    "contract_file_endpoint": "`/api/chat/file` 只回文本给前端，不吐 SSE 正文帧 ⇒ 不属于「会吐答复文本的出口」。",
}

# 豁免清单（哨兵要求每项带票号或 Owner 裁决；空清单也要显式存在）。
EXEMPTIONS: list[dict] = []
