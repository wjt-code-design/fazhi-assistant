"""票 B：两道引用冒烟门的判据必须钉到 `(法名, 条号)` 联合，而不是只看条号。

派单：`docs/assistant-briefs/next-phase-B-citation-checks-20260927.md`；
证据：`docs/assistant-briefs/verification-scope-review-findings-20260927.md` §2 缺口 1——主集合
`legal_provisions_cos` 口径下 第十九条 被 97 部法共用、第四十四条 87 部、第二十五条 95 部，
所以"回答里出现了第八十七条"根本不构成证据（可能引的是《刑法》）。

**为什么每个否定式都配一条同数据的对照腿**：判据收紧最坏的失败模式是改完恒 False。
只看见"错法名红了"分不清是判据严还是判据死了，所以每条 False 旁边都放一条只把法名改对的 True。

**为什么 fast 的归一化从外面注入**：`retrieval.py` 在 import 期就建 Chroma 客户端并加载 BGE 嵌入模型，
而这两道门要判的只是"配对语义"。纯语义用例注入 `str.strip` 当近似恒等替身，免得把"归一化对不对"
和"配对对不对"混进同一条断言；生产口径另有两条专测（拼写容忍 + 委托给 retrieval）分别钉住。

隔离约定：两个脚本按文件路径加载，且 import 期不得有副作用——`smoke_citation_fast.py` 的
`os.chdir`/`load_dotenv`、`smoke_citation_full.py` 的缺凭据 `sys.exit(2)` 都必须挪进 `main()`，
否则 CI 上没有 `.env` 时收集阶段就炸。检索结果用生产同类型 `langchain_core.documents.Document` 造，
不读真实索引、不发嵌入或答案生成调用。
诚实边界：默认归一化那条用例与"不许漂移"绊线要 `import retrieval`，它在 import 期会加载本机 BGE——
这笔钱 conftest 的 autouse 夹具 `tests/conftest.py::_disable_rate_limit`（每条用例都 `import main`）
已付过，本文件没有新增，但"零模型成本"这种话不能说。
"""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import sys
from pathlib import Path

import pytest
from langchain_core.documents import Document

BACKEND = Path(__file__).resolve().parents[1]
CONTRIBUTING = BACKEND.parent / "CONTRIBUTING.md"
sys.path.insert(0, str(BACKEND))


def _load(name: str):
    """按路径加载 `scripts/<name>.py`，并还原它 import 期可能改掉的 cwd（`import_laws` 同款陷阱）。"""
    cwd = os.getcwd()
    spec = importlib.util.spec_from_file_location(f"_b_{name}_under_test", BACKEND / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    finally:
        os.chdir(cwd)
    return mod


@pytest.fixture(scope="module")
def fast():
    return _load("smoke_citation_fast")


@pytest.fixture(scope="module")
def full():
    return _load("smoke_citation_full")


def _doc(source: str | None, article: str | None) -> Document:
    """造一条召回结果。正文是构造样本，不是库内原文。"""
    meta = {} if source is None and article is None else {"source": source, "article": article}
    return Document(page_content="构造样本条文正文，非库内原文。", metadata=meta)


# ==================== fast：召回层的 (source, article) 联合 ====================


def test_recall_hit_rejects_right_article_from_wrong_law(fast):
    """核心回归腿：条号对、法名错 ⇒ 不红就是判据没生效。旧实现（只看条号）在这里必过。"""
    docs = [_doc("刑法", "第八十七条")]
    hit = fast.recall_hit(docs, ["劳动合同法"], ["第八十七条"], norm_source=str.strip, norm_article=str.strip)
    assert hit is False


def test_recall_hit_accepts_matching_pair(fast):
    """对照腿：只把法名改对，同一份 docs 必须过——证明上一条红在法名，不是判据恒 False。"""
    docs = [_doc("劳动合同法", "第八十七条")]
    hit = fast.recall_hit(docs, ["劳动合同法"], ["第八十七条"], norm_source=str.strip, norm_article=str.strip)
    assert hit is True


def test_recall_hit_keeps_any_of_two_articles(fast):
    """定金用例的两条可接受条文：任中一条即算召回，这个既有语义不许被收紧弄丢。"""
    docs = [_doc("民法典", "第五百八十七条")]
    hit = fast.recall_hit(
        docs, ["民法典"], ["第五百八十六条", "第五百八十七条"], norm_source=str.strip, norm_article=str.strip
    )
    assert hit is True


def test_recall_hit_rejects_pair_split_across_two_docs(fast):
    """法名和条号必须落在**同一条**文档上。

    `any(src in es) and any(art in ea)` 这种写法在真实召回结果里几乎总会绿——k=6 的池子里同时躺着
    消保法的别的条文和别的法的第二十五条。
    """
    docs = [_doc("消费者权益保护法", "第八条"), _doc("民法典", "第二十五条")]
    hit = fast.recall_hit(docs, ["消费者权益保护法"], ["第二十五条"], norm_source=str.strip, norm_article=str.strip)
    assert hit is False


def test_recall_hit_survives_docs_without_source_or_article(fast):
    """`qa_pairs` 集合根本不带 source/article 两个键（2026-09-27 只读实测其 279 块的元数据键）⇒
    池子里混进 QA 块是常态：不能崩，也只能判不命中。"""
    docs = [_doc(None, None), _doc("劳动合同法", None), _doc(None, "第八十七条")]
    hit = fast.recall_hit(docs, ["劳动合同法"], ["第八十七条"], norm_source=str.strip, norm_article=str.strip)
    assert hit is False


def test_recall_hit_defaults_follow_production_spelling_rules(fast):
    """默认参数必须按生产口径归一化：去"中华人民共和国"前缀、剥"（1982年）"年份括注、阿拉伯↔中文条号；
    同时联合判据在归一化之后仍然拒跨法。"""
    docs = [_doc("中华人民共和国劳动合同法", "第87条"), _doc("宪法（1982年）", "第二十五条")]
    assert fast.recall_hit(docs, ["劳动合同法"], ["第八十七条"]) is True
    assert fast.recall_hit(docs, ["宪法"], ["第二十五条"]) is True
    assert fast.recall_hit(docs, ["劳动合同法"], ["第二十五条"]) is False


def test_recall_hit_defaults_delegate_to_retrieval_instead_of_a_second_copy(fast, monkeypatch):
    """钉委托，不钉复述：默认归一化必须真的调用 `retrieval` 的那一对函数。

    脚本里另写一份 `strip("中华人民共和国")` 能过上一条拼写用例，却会在下一次生产改口径时静默分叉
    ——所以这里用打点替身证明"归一化来自 retrieval"，红法是"没人打点"。
    """
    import retrieval

    src_calls: list[str] = []
    art_calls: list[str] = []
    monkeypatch.setattr(retrieval, "_source_key", lambda name: src_calls.append(name) or name)
    monkeypatch.setattr(retrieval, "_normalize_article", lambda art: art_calls.append(art) or art)

    docs = [_doc("劳动合同法", "第八十七条")]
    assert fast.recall_hit(docs, ["劳动合同法"], ["第八十七条"]) is True
    assert "劳动合同法" in src_calls, "默认法名归一化没走 retrieval._source_key"
    assert "第八十七条" in art_calls, "默认条号归一化没走 retrieval._normalize_article"


# ==================== full：答案文本层的 (法名, 条号) 联合 ====================


def test_answer_cites_rejects_right_article_from_wrong_law(full):
    """回答引的是《刑法》第八十七条 ⇒ 期望"劳动合同法+第八十七条"必须红（旧实现只看条号会绿）。"""
    assert full.answer_cites("依据《刑法》第八十七条，应当支付赔偿金。", "劳动合同法", ["第八十七条"]) is False


def test_answer_cites_accepts_matching_pair(full):
    assert full.answer_cites("依据《劳动合同法》第八十七条。", "劳动合同法", ["第八十七条"]) is True


def test_answer_cites_tolerates_official_prefix_and_year_note(full):
    """全称与带年份括注都在容忍面内（与生产 `retrieval._source_key` 同截口径）。

    比生产**少**一层：`article_in_kb` 在 `_source_key` 之前还套了 `canon_source`（retrieval.article_in_kb 里的简称→全称别名表）。门不需要它——场景表里写的就是库内正式名，把那层映射牵进来只会多一个可漂移点。
    """
    assert full.answer_cites("《中华人民共和国劳动合同法》第八十七条。", "劳动合同法", ["第八十七条"]) is True
    assert full.answer_cites("《劳动合同法（2012年修正）》第十九条。", "劳动合同法", ["第十九条"]) is True


def test_answer_cites_rejects_name_and_article_in_separate_sentences(full):
    """法名与条号必须相邻成对。

    这条挡住"回答别处提过某法、又在别处裸写了一个条号"被算成命中——正是
    `法名 in answer and 条号 in answer` 这种偷懒写法的失败形态。
    """
    answer = "《消费者权益保护法》第二十五条规定了七日无理由退货。至于解除合同的赔偿，另见第八十七条。"
    assert full.answer_cites(answer, "劳动合同法", ["第八十七条"]) is False


def test_answer_cites_accepts_any_listed_spelling(full):
    """提示词让模型写阿拉伯条号（`domain_rules.CITATION_SELECTION_RULE` 里的"《民法典》第496条"），
    知识库条号是中文数字 ⇒ 同一场景的两种写法都进可接受列表，别的条号必须红。"""
    accepted = ["第四百九十六条", "第496条"]
    assert full.answer_cites("《民法典》第496条。", "民法典", accepted) is True
    assert full.answer_cites("《民法典》第四百九十六条。", "民法典", accepted) is True
    assert full.answer_cites("《民法典》第498条。", "民法典", accepted) is False


def test_citation_pairs_extracts_adjacent_pairs_only(full):
    """抽取器是 `answer_cites` 的判据本体，单独钉住它返回的是归一化后的配对集合。"""
    answer = "《中华人民共和国民法典》第一千二百一十三条、《消费者权益保护法》第二十五条。"
    assert full.citation_pairs(answer) == {("民法典", "第一千二百一十三条"), ("消费者权益保护法", "第二十五条")}


def test_citation_pairs_accepts_bare_law_name_without_book_marks(full):
    """模型常写"劳动合同法第八十七条"（无书名号）。生产端在写库前用
    `output_normalize.expand_law_names` 补书名号（`main._post` 里那一步），而 **E5/E8 两条流式出口
    直发模型原文**（`gate-exit: E5` / `gate-exit: E8` 的 yield）⇒ 门自己累加到的是没补过的原文，
    必须自己过同一对函数，否则这种答案假红。"""
    assert full.citation_pairs("依劳动合同法第八十七条，用人单位应当支付赔偿金。") == {("劳动合同法", "第八十七条")}
    assert full.answer_cites("依劳动合同法第八十七条支付。", "劳动合同法", ["第八十七条"]) is True


def test_citation_pairs_expands_continuous_article_list(full):
    """连续续接形式（《民法典》第496条、第497条）里第二条省了书名——生产端的
    `output_normalize.expand_citations` 只在这种形状上补回，门跟着它走；
    散文里隔开的裸条号不补（与生产同界，不自己发明"最近书名"归属）。"""
    answer = "《民法典》第496条、第497条规定了格式条款。"
    assert full.citation_pairs(answer) == {("民法典", "第496条"), ("民法典", "第497条")}
    prose = "《民法典》第四百九十六条规定了格式条款的认定，另有第四百九十七条列举无效情形。"
    assert full.citation_pairs(prose) == {("民法典", "第四百九十六条")}


# ==================== 接线与漂移绊线 ====================


def _fn_src(script: str, fn: str) -> str:
    """取脚本里某个顶层函数的源码段。

    用 AST 而不是 `inspect.getsource`：被测模块是用 importlib 现加载的、没进 `sys.modules`，
    `getsource` 找不到所属模块会直接抛 TypeError。本仓的先例是
    `tests/test_qa_citation_gate_symmetry.py` 的 `_body()`（同款"函数体扫描，全文扫描会误伤"）。
    """
    src = (BACKEND / "scripts" / f"{script}.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == fn)
    return ast.get_source_segment(src, node) or ""


def _non_loop_checks(script: str) -> int:
    """数 `main()` 里**不在任何 for 循环内**的 `check(...)` 调用点——即"表驱动之外手写的腿"。"""
    src = (BACKEND / "scripts" / f"{script}.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "main")

    def sites(node):
        return [c for c in ast.walk(node) if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "check"]

    inside_loop = {id(c) for node in ast.walk(fn) if isinstance(node, ast.For) for c in sites(node)}
    return len([c for c in sites(fn) if id(c) not in inside_loop])


def test_fast_main_is_wired_to_the_pair_judge():
    """判据函数存在≠门禁在用它。旧接线（`any(a in arts for a in ea)`）被实测能骗过本文件全部其余用例，
    所以这条绊线钉住 `main()` 真在调 `recall_hit`，并钉住旧形状没被抄回来。"""
    body = _fn_src("smoke_citation_fast", "main")
    assert "recall_hit(docs, es, ea)" in body, "fast 的 main() 没在调用联合判据"
    assert "for a in ea" not in body, "fast 的 main() 里又出现了只看条号的旧形状"


def test_full_main_is_wired_to_the_pair_judge():
    """同上，且 full 有**两个**生成出口（正向 8 与轻量 2）——只接一处正是本仓点过名的失效形状。"""
    body = _fn_src("smoke_citation_full", "main")
    assert body.count("answer_cites(c, source, expects)") == 2, "full 的两处引用断言必须都走联合判据"
    assert "for e in expects" not in body, "full 的 main() 里又出现了子串匹配的旧形状"


def test_full_name_normalizer_cannot_drift_from_retrieval(full):
    """full 自带的 `norm_law_name` 是生产 `_source_key` 的第二份字面量 ⇒ 必须钉住不许分叉。

    样本里特意放一个 `retrieval._norm_source`（只去前缀、不剥括注的弱一档函数）**过不了**的输入：
    一旦有人把 full 侧改成照抄那个更弱的近名函数，这条就红。
    """
    import retrieval

    samples = ["中华人民共和国劳动合同法", "宪法（1982年）", "民法典", " 劳动法 ", "消费者权益保护法", ""]
    for name in samples:
        assert full.norm_law_name(name) == retrieval._source_key(name), f"法名归一与 retrieval 分叉：{name!r}"
    assert full.norm_law_name("宪法（1982年）") != retrieval._norm_source("宪法（1982年）"), (
        "钉错对象：应当对齐 _source_key"
    )


def test_full_smoke_sends_no_cache_so_it_proves_a_real_generation(full, monkeypatch):
    """R25（改前失败）：门必须发 `no_cache`，否则整条结论可能来自缓存/QA 直返。

    改前 `chat()` 只发 `{"question": q}` ⇒ 候选 main.py 在模型生成**之前**允许"回答缓存命中"
    与"QA 持久语义缓存直返"两条零 token 捷径 ⇒ 门里的"引对了/诚实拒答了"证明不了本次真的调用了模型。
    这里不打桩业务逻辑，只看脚本**实际发出去的请求体**（把 `urlopen` 换成记录器）。
    """
    import json

    sent: dict = {}

    class _Resp:
        def __iter__(self):
            return iter([b'data: {"content": "\\u7b54"}\n', b"data: [DONE]\n"])

    def fake_urlopen(req, timeout=0):  # noqa: ARG001
        sent["body"] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(full.urllib.request, "urlopen", fake_urlopen)
    full.chat("tok", "劳动合同试用期最长能约定多久？")

    assert sent["body"].get("no_cache") is True, f"请求体没关缓存/直返两条捷径：{sent['body']}"
    assert sent["body"].get("question") == "劳动合同试用期最长能约定多久？"


def test_full_citation_pattern_cannot_drift_from_retrieval(full):
    """full 的条号形状必须仍是 `retrieval._ART_FULL_RE` 里那一截，不许各改各的。"""
    import retrieval

    assert full._ART_CORE in retrieval._ART_FULL_RE.pattern, "full 的条号正则与生产正则已不是同一截"


# ==================== 场景期望与门禁项数 ====================

# 期望值独立写在测试里；不可从脚本用例表推导，否则改错条号也会全绿。
EXPECTED_FAST_PAIRS = {
    "公司违法解除劳动合同，赔偿金怎么算？": ({"劳动合同法"}, {"第八十七条"}),
    "公司合同到期不续签，经济补偿金怎么算？": ({"劳动合同法"}, {"第四十七条"}),
    "劳动合同试用期最长能约定多久？": ({"劳动合同法"}, {"第十九条"}),
    "周末加班，加班费怎么算？": ({"劳动法"}, {"第四十四条"}),
    "机动车发生交通事故，交强险先赔还是商业险先赔？": ({"民法典"}, {"第一千二百一十三条"}),
    "交了定金又不想买了，定金能退吗？": ({"民法典"}, {"第五百八十六条", "第五百八十七条"}),
    "网购商品七天无理由退货需要满足什么条件？": ({"消费者权益保护法"}, {"第二十五条"}),
}


def test_fast_table_keeps_each_scenario_law_and_articles(fast):
    """七个检索场景的法名和可接受条号都由独立期望锁定。"""
    table = {query: (set(sources), set(articles)) for query, sources, articles, _intent in fast.RETRIEVAL_CASES}
    assert len(table) == len(fast.RETRIEVAL_CASES), "检索问题重复"
    assert table == EXPECTED_FAST_PAIRS


# 派单的法名归属与各题操作性条文；两种数字写法均可接受。
EXPECTED_FULL_PAIRS = {
    "网购退货格式条款": ("民法典", {"第四百九十六条", "第496条", "第四百九十七条", "第497条"}),
    "违法解除赔偿金": ("劳动合同法", {"第八十七条", "第87条"}),
    "合法解除经济补偿": ("劳动合同法", {"第四十七条", "第47条"}),
    "试用期上限": ("劳动合同法", {"第十九条", "第19条"}),
    "周末加班费": ("劳动法", {"第四十四条", "第44条"}),
    "交强险赔偿顺序": ("民法典", {"第一千二百一十三条", "第1213条"}),
    "定金退不退": ("民法典", {"第五百八十六条", "第586条", "第五百八十七条", "第587条"}),
    "七天无理由退货": ("消费者权益保护法", {"第二十五条", "第25条"}),
    "轻量-试用期": ("劳动合同法", {"第十九条", "第19条"}),
    "轻量-七天退货": ("消费者权益保护法", {"第二十五条", "第25条"}),
}


def test_full_tables_keep_each_scenario_law_and_articles(full):
    """十个带引用断言的场景逐项锁定法名和可接受条号。"""
    rows = [*full.POSITIVE, *full.LIGHT_POSITIVE]
    table = {label: (source, set(articles)) for label, _query, source, articles in rows}
    assert len(table) == len(rows), "场景名重复"
    assert table == EXPECTED_FULL_PAIRS


def test_full_negatives_carry_no_citation_expectation(full):
    """负向场景判的是"诚实拒答"，不许被塞进引用配对里（那会把拒答测成引用测）。"""
    assert len(full.NEGATIVE) == 2
    assert all(len(row) == 2 for row in full.NEGATIVE)


def test_gate_item_counts_match_contributing(fast, full):
    """交付判据要求"脚本项数和贡献指南一致"，所以把这两个数变成机器核的，不再靠人眼数。

    fast 的 24 = 意图 7 + 召回 7 + 引用校验 3 + 复杂度 4 + 自检 3。前三项由用例表长度推出，
    后两项（不在循环里的那些 `check(` 调用点）用 AST 现数——不然 "+7" 是我手抄的，
    加一条自检腿照样能骗过这条对账。full 的 12 = 正向 8 + 负向 2 + 轻量 2。
    """
    tail = _non_loop_checks("smoke_citation_fast")
    counts = {
        "smoke_citation_fast.py": 2 * len(fast.RETRIEVAL_CASES) + len(fast.VERIFY_CASES) + tail,
        "smoke_citation_full.py": len(full.POSITIVE) + len(full.NEGATIVE) + len(full.LIGHT_POSITIVE),
    }
    text = CONTRIBUTING.read_text(encoding="utf-8")
    for script, derived in counts.items():
        line = next(line for line in text.splitlines() if script in line)
        stated = int(re.search(r"（\s*(\d+)", line).group(1))
        assert stated == derived, f"CONTRIBUTING.md 对 {script} 写的是 {stated}，脚本实际 {derived}"


# ==================== 隔离：import 期零副作用 ====================


def test_scripts_import_without_credentials_or_model_calls(monkeypatch):
    """没有 ADMIN_PASSWORD 也不能在 import 期 `sys.exit`，且不得把 cwd 改走——CI 收集期与并行会话都要靠这个。

    这里**故意不还原 cwd**：`_load` 的 finally 会把脚本改掉的工作目录盖回去，用它测就等于恒过；
    所以先 chdir 到 `backend/` 之外，让模块级 `os.chdir(BACKEND)` 真的暴露出来（monkeypatch.chdir 会还原）。
    """
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.chdir(BACKEND.parent)
    expected_cwd = os.getcwd()
    for name in ("smoke_citation_fast", "smoke_citation_full"):
        spec = importlib.util.spec_from_file_location(f"_b_isolation_{name}", BACKEND / "scripts" / f"{name}.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # 抛 SystemExit 即红
        assert os.getcwd() == expected_cwd, f"{name}.py 在 import 期改了工作目录"
        # 本机 .env 里 ADMIN_PASSWORD 是有值的：模块级 load_dotenv 会把它重新灌进环境，
        # 于是"没凭据也不许 exit"这条腿在这台机器上恒过。钉住"import 期不读 .env"才让它真能红。
        # 断言不回显 os.environ——pytest 会把整个环境（含真口令）打进失败输出。
        assert "ADMIN_PASSWORD" not in os.environ, f"{name}.py 在 import 期读了 .env，凭据被灌回环境"
