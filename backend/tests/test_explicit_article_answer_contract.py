"""W04 / D-50：明确条号未命中与引用对题（C02 已于 2026-10-17 按推荐裁定）。

裁定原文（plan:198）＝「推荐显式未命中，允许说明性旁引；**检索/证据选择与主条号替代分别验**，
不要求所有答案只引一个条号」。这句话直接决定了本文件的分组形状：

- **组一 `TestParseAndLookupSide`**＝检索/解析侧：用户点了**两条**，不能被降级成"只问第一条"；
  未命中必须分成「库里没有这条」与「有，但按查询时点版本不确定」两态
  （plan W04 第 2 条：「查不到不证明法律不存在」——所以两态不许合成一态）。
- **组二 `TestAnswerOutletSide`**＝主条号替代/出口侧：未命中时**明说**未命中，
  同时**允许**引用别条（只要说明关系）。

为什么每条红的都配一条"不误伤"的对照：C02 出口句写的是
「正常/旁引/多法/未知版本**不误伤**」⇒ 只测"该拦的拦住了"等于没测，
把判据写成"所有答案只引一个条号"那种宽约束恰恰是裁定明令禁止的方向
（`test_explanatory_side_citation_is_allowed_not_banned` 钉的就是这条反向）。

边界：全程不接真实 Chroma、不出网。`article_lookup_report` 设计成对**注入的两个探针**求值
（带时点 / 不带时点），这样"版本不确定 vs 库里没有"两态能在合成数据上分开触发；
`retrieve` 的多引用只 monkeypatch `exact_article_lookup` 与 `hybrid_retrieve`，
量的是"每一条都被查过"这个调度事实，不是检索质量。
"""

from __future__ import annotations

import request_bootstrap as RB
import retrieval as R

# 导入期抓住原厂依赖工厂：`_deps_with` 需要它，而测试会把模块属性换成会递归的 lambda。
_ORIGINAL_DEPS_FACTORY = RB._default_fast_path_dependencies


class _MinimalDeps:
    """依赖替身的容器。用类而不是 `class _D: pass` 在函数里现造，是为了让
    `dir(real)` 的复制结果可预测（每次现造类会带出不同的属性面）。"""


def doc(source: str, article: str, text: str):
    from langchain_core.documents import Document

    return Document(page_content=text, metadata={"source": source, "article": article})


class TestParseAndLookupSide:
    """组一：解析与直查调度。C02 里「不把首个匹配当所有多引用意图」落在这一组。"""

    def test_multi_reference_query_keeps_every_named_pair(self):
        """点了两条 ⇒ 两条都要被识别。今天 `parse_article_query` 只回第一条（`.search` 非 `finditer`）。"""
        pairs = R.parse_article_queries("《劳动法》第九十九条和《劳动合同法》第八十七条分别怎么适用")
        assert pairs == [("劳动法", "第九十九条"), ("劳动合同法", "第八十七条")]

    def test_single_reference_query_matches_the_legacy_parser(self):
        """不误伤：单引用时新旧两个解析器必须给出同一对，旧调用点行为逐字不变。"""
        q = "《劳动法》第九十九条经济补偿金怎么算"
        legacy = R.parse_article_query(q)
        assert legacy is not None and R.parse_article_queries(q) == [legacy]

    def test_no_explicit_reference_yields_no_pairs(self):
        """不误伤：没点条号的普通问题不产生任何"未命中"判断。"""
        assert R.parse_article_queries("没签合同被辞退能要求赔偿吗") == []

    def test_each_named_article_is_looked_up_not_just_the_first(self, monkeypatch):
        """直查调度：两条都要查。今天 `retrieve` 只查第一条（retrieval.py:1222）。"""
        seen: list[tuple[str, str]] = []

        def fake_lookup(source, article, cutoff=None):
            seen.append((source, article))
            return [doc(source, article, "正文")]

        monkeypatch.setattr(R, "exact_article_lookup", fake_lookup)
        monkeypatch.setattr(R, "hybrid_retrieve", lambda *a, **kw: [])
        out = R.retrieve("《劳动法》第九十九条、《劳动合同法》第八十七条")
        assert seen == [("劳动法", "第九十九条"), ("劳动合同法", "第八十七条")]
        assert [d.metadata["article"] for d in out] == ["第九十九条", "第八十七条"]

    def test_duplicate_reference_is_looked_up_once(self, monkeypatch):
        """同一对写两遍不该付两次查库成本（去重按有序集合，不按 set 打乱顺序）。"""
        seen: list[tuple[str, str]] = []
        monkeypatch.setattr(R, "exact_article_lookup", lambda s, a, cutoff=None: seen.append((s, a)) or [])
        monkeypatch.setattr(R, "hybrid_retrieve", lambda *a, **kw: [])
        R.retrieve("《劳动法》第九十九条；再说一次《劳动法》第九十九条")
        assert seen == [("劳动法", "第九十九条")]


class TestLookupReportThreeStates:
    """组一的判据本体：三态分开——命中 / 库里没有 / 有时点不对。"""

    def _report(self, query, docs, *, timed_hit, anytime_hit):
        return R.article_lookup_report(
            query,
            docs,
            lookup_with_cutoff=lambda s, a: timed_hit,
            lookup_any_time=lambda s, a: anytime_hit,
        )

    def test_found_article_is_not_reported_missing(self):
        rep = self._report(
            "《劳动法》第九十九条",
            [doc("劳动法", "第九十九条", "正文")],
            timed_hit=[doc("劳动法", "第九十九条", "正文")],
            anytime_hit=[doc("劳动法", "第九十九条", "正文")],
        )
        assert rep["asked"] == [("劳动法", "第九十九条")]
        assert rep["missing"] == [] and rep["state"] == "all_found"

    def test_absent_article_is_reported_as_not_in_library(self):
        """库里根本没有这条 ⇒ `not_in_library`。"""
        rep = self._report("《劳动法》第九百九十九条", [], timed_hit=[], anytime_hit=[])
        assert rep["state"] == "not_in_library"
        assert rep["missing"] == [("劳动法", "第九百九十九条")]

    def test_article_that_exists_but_not_at_the_query_date_is_version_uncertain(self):
        """有这条、但按提问时点不现行 ⇒ 只能是「版本不确定」，不许谎称「库里没有」。

        plan W04 第 2 条明写：「查不到不证明法律不存在」。合成两态各一条，就是把这句话拆成能红的断言。
        """
        rep = self._report(
            "《劳动法》第九十九条",
            [],
            timed_hit=[],  # 带时点查不到
            anytime_hit=[doc("劳动法", "第九十九条", "现行正文")],  # 不带时点查得到
        )
        assert rep["state"] == "version_uncertain"

    def test_mixed_query_reports_per_article(self):
        """两条问、一条中 ⇒ missing 只记没中的那条（不是整问一态）。"""
        rep = R.article_lookup_report(
            "《劳动法》第九十九条和《劳动合同法》第八十七条",
            [doc("劳动法", "第九十九条", "正文")],
            lookup_with_cutoff=lambda s, a: [doc(s, a, "正文")] if a == "第九十九条" else [],
            lookup_any_time=lambda s, a: [doc(s, a, "正文")] if a == "第九十九条" else [],
        )
        assert rep["found"] == [("劳动法", "第九十九条")]
        assert rep["missing"] == [("劳动合同法", "第八十七条")]

    def test_mixed_absent_and_expired_are_not_all_called_absent(self):
        """一条根本没收录＋一条只是时点不对 ⇒ 不许整份判成「库里没有」。

        这是三态里最容易糊过去的一格：合成两态时如果只写「有/没有」，
        对"存在但按 as-of 不现行"的那条就是**假陈述**（plan W04 第 2 条正是禁这个）。
        """
        rep = R.article_lookup_report(
            "《劳动法》第九百九十九条和《劳动合同法》第八十七条",
            [],
            lookup_with_cutoff=lambda s, a: [],
            lookup_any_time=lambda s, a: [doc(s, a, "正文")] if a == "第八十七条" else [],
        )
        assert rep["state"] == "mixed"
        assert sorted(rep["missing"]) == [("劳动合同法", "第八十七条"), ("劳动法", "第九百九十九条")]

    def test_query_without_explicit_reference_produces_no_verdict(self):
        """不误伤：没点条号就没有"未命中"可言，`asked` 为空、state 为 no_explicit_reference。"""
        rep = R.article_lookup_report(
            "被辞退能要赔偿吗", [], lookup_with_cutoff=lambda s, a: [], lookup_any_time=lambda s, a: []
        )
        assert rep["asked"] == [] and rep["state"] == "no_explicit_reference"


class TestAnswerOutletSide:
    """组二：证据选择 与 主条号替代 分开验——未命中要明说，但别条引用不能被禁掉。"""

    def test_miss_statement_is_prepared_before_the_supplementary_text(self):
        """主条号替代这一侧：context 必须先讲清"所问条号本库未直接命中"，再放补充条文。"""
        line = RB.article_miss_note(
            {
                "asked": [("劳动合同法", "第八十七条")],
                "found": [],
                "missing": [("劳动合同法", "第八十七条")],
                "state": "not_in_library",
            }
        )
        assert "劳动合同法" in line and "第八十七条" in line
        assert "未" in line and "知识库" in line

    def test_version_uncertain_says_so_instead_of_absent(self):
        """两态措辞必须不同——把「版本不确定」写成「库里没有」是假陈述。"""
        absent = RB.article_miss_note(
            {
                "asked": [("劳动法", "第九十九条")],
                "found": [],
                "missing": [("劳动法", "第九十九条")],
                "state": "not_in_library",
            }
        )
        unsure = RB.article_miss_note(
            {
                "asked": [("劳动法", "第九十九条")],
                "found": [],
                "missing": [("劳动法", "第九十九条")],
                "state": "version_uncertain",
            }
        )
        assert absent != unsure
        assert "不确定" in unsure

    def test_explanatory_side_citation_is_allowed_not_banned(self):
        """C02 反向钉子：出口只能说「引别条要说明关系」，不能说「只能引所问条号」。

        这条防的是我自己最容易犯的过度收紧：把"别旁条冒充"修成"禁止任何旁引"，
        正好撞在裁定明令禁止的那一句上（不要求所有答案只引一个条号）。
        """
        line = RB.article_miss_note(
            {
                "asked": [("劳动法", "第九十九条")],
                "found": [],
                "missing": [("劳动法", "第九十九条")],
                "state": "not_in_library",
            }
        )
        banned = ("只能引用", "只可引用", "不得引用其他", "禁止引用其他", "仅引用所问")
        assert not any(b in line for b in banned), line
        assert "关系" in line

    def test_no_note_when_nothing_is_missing(self):
        """不误伤：全命中 / 没点条号 都不该冒出这段说明。"""
        assert (
            RB.article_miss_note(
                {
                    "asked": [("劳动法", "第九十九条")],
                    "found": [("劳动法", "第九十九条")],
                    "missing": [],
                    "state": "all_found",
                }
            )
            == ""
        )
        assert RB.article_miss_note({"asked": [], "found": [], "missing": [], "state": "no_explicit_reference"}) == ""


def _bootstrap(text: str) -> RB.RequestBootstrap:
    """按 `tests/test_agent_gate.py:21` 那副形状构造（25 个字段全是必填）。

    先记一笔：我第一版只传了 6 个关键字，那两条"接线红"其实是**我的夹具坏了**
    （`TypeError: missing 11 required positional arguments`），不是产品缺行为。
    红要红在该红的地方，否则实现完变绿也证明不了任何事。
    """
    return RB.RequestBootstrap(
        conv_id=17,
        summary="",
        recent=[],
        recent_messages=[],
        image=None,
        user_text=text,
        image_rel=None,
        thumb_rel=None,
        image_description="",
        raw_query=text,
        supplement_text=text,
        intent="legal_query",
        is_exam=False,
        has_options=False,
        contract_mode=False,
        contract_text=None,
        client_truncated=False,
    )


class TestWiredIntoFastPath:
    """接线：判据住在检索侧，出口消费它——两处只有一份规则（防第二个漂移点）。"""

    def test_fast_path_puts_the_note_into_context(self, monkeypatch):
        """走 `prepare_fast_path` 时，未命中说明要落到 `pre["context"]`。"""
        monkeypatch.setattr(
            RB,
            "_default_fast_path_dependencies",
            lambda: _deps_with(monkeypatch, lambda query, k=10, cutoff=None, **kw: []),
        )
        q = "《劳动合同法》第八十七条怎么规定"
        pre = RB.prepare_fast_path(_bootstrap(q))
        assert "第八十七条" in pre["context"] and "未" in pre["context"]

    def test_note_is_rendered_by_the_single_producer(self, monkeypatch):
        """接线钉子：出口必须是调 `article_miss_note`，不是自己抄一份文案。

        把函数换成哨兵实现，`prepare_fast_path` 的 context 必须带上哨兵串——
        否则说明文案有第二份真源（这条形状同 `tests/test_qa_citation_gate_symmetry.py` 钉的同一性）。
        """
        monkeypatch.setattr(
            RB,
            "_default_fast_path_dependencies",
            lambda: _deps_with(monkeypatch, lambda query, k=10, cutoff=None, **kw: []),
        )
        seen = {}

        def sentinel(report):
            if report.get("missing"):
                seen["hit"] = True
                return "【哨兵：未命中说明由这里唯一生成】"
            return ""

        monkeypatch.setattr(RB, "article_miss_note", sentinel)
        q = "《劳动合同法》第八十七条怎么规定"
        pre = RB.prepare_fast_path(_bootstrap(q))
        assert seen.get("hit") is True, "fast path 没走 article_miss_note ⇒ 文案有第二份真源"
        assert "哨兵" in pre["context"]


def _deps_with(monkeypatch, fake_retrieve):
    """给 `prepare_fast_path` 一副最小可跑的依赖：真检索全换成确定值。

    必须用**导入期抓住的原厂**造依赖：测试把 `RB._default_fast_path_dependencies` 换成了
    会调用本函数的 lambda，这里再走模块属性就是自我递归（第一版就这么炸过一次
    `RecursionError`，那条红是夹具坏了，不是产品缺行为）。
    """
    real = _ORIGINAL_DEPS_FACTORY()

    d = _MinimalDeps()
    for name in dir(real):
        if name.startswith("_"):
            continue
        setattr(d, name, getattr(real, name))
    d.retrieve = fake_retrieve
    d.rewrite_for_retrieval = lambda raw, recent, msgs, has_options: raw
    d.search_qa = lambda q: None
    d.scenario_supplement_docs = lambda text, cutoff=None: []
    d.is_consumer_clause_scenario = lambda q: False
    d.is_consumer_fraud_scenario = lambda q: False
    d.consumer_clause_docs = lambda cutoff=None: []
    d.consumer_fraud_docs = lambda cutoff=None: []
    monkeypatch.setattr(R, "retrieve", fake_retrieve, raising=False)
    return d
