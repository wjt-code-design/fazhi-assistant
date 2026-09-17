"""R1-OB（判域输入扩展）测试——2026-09-16 预注册 optionB。

覆盖：
- resolve_domain 三级语义（tier-1 域码压制文本歧义 / tier-2 拼接实证 / 非法值防御 / mixed→None）；
- legal_retrieval 过滤路径的开关契约（r1ob 开 = 三级输入；关 = 以 issue query 判域，行为不变）；
- 数据取自真实反例（dispatch-output/r1-ob-offline-20260916/counterexamples.json 的 E01/E04 文本）。
"""

from __future__ import annotations

from types import SimpleNamespace

from agent.r1ob import VALID_CASE_DOMAINS, resolve_domain

# 真实反例文本（E01/E04，抄自 counterexamples.json——预注册 §2.2 反例集）
E01_USER_Q = "一家公司欠我们货款20万已经两年多了，负责人总躲着我，我们能起诉吗？"
E01_ISSUE3 = "被告公司的诉讼主体资格是否明确且具备应诉能力？"
E04_USER_Q = "我开车蹭到电动车，对方轻微擦伤鉴定为轻微伤，交警定我主责，对方医疗费和误工费该怎么赔？"
E04_ISSUE2 = "交警认定用户承担主要责任这一行政决定是否合法有效？"


class TestResolveDomain:
    def test_tier1_overrides_text_ambiguity(self):
        """tier-1 域码直判：文本含行政词（E04 issue2）也被域码压制为 civil。"""
        assert resolve_domain("civil", E04_USER_Q, E04_ISSUE2) == "civil"

    def test_tier2_repairs_zero_hint_issue(self):
        """tier-2：E01 issue3 零指示词，用户原始问题（'起诉'）补齐域线索 → civil。"""
        assert resolve_domain(None, E01_USER_Q, E01_ISSUE3) == "civil"

    def test_tier2_insufficient_for_e04_issue2(self):
        """tier-2 单独不足（预注册实证）：E04 issue2 行政指示词主导 → administrative（方向偏离，
        仅 tier-1 可修复）——本测试如实锁定该已知边界。"""
        assert resolve_domain(None, E04_USER_Q, E04_ISSUE2) == "administrative"

    def test_mixed_text_returns_none(self):
        """多域命中 → None（不过滤，与 R1 保守语义一致）。"""
        assert resolve_domain(None, "行政处罚与劳动仲裁的选择", None) is None

    def test_empty_inputs_return_none(self):
        assert resolve_domain(None, None, None) is None
        assert resolve_domain(None, "", "") is None

    def test_invalid_case_domain_falls_back_to_tier2(self):
        """非法域码：防御性按无域码处理（第二层；入站层已 422 拒绝）。"""
        assert (
            resolve_domain(
                "bogus",
                None,
                "劳动纠纷起诉",
            )
            == "civil"
        )
        assert resolve_domain("bogus", None, None) is None

    def test_valid_case_domains_set(self):
        assert VALID_CASE_DOMAINS == {"civil", "criminal", "administrative", "special-maritime"}


class TestLegalRetrievalFiltering:
    """legal_retrieval 的判域过滤路径：三级输入经 context 生效。"""

    @staticmethod
    def _fake_docs():
        return [
            SimpleNamespace(metadata={"source": "行政诉讼法", "article": "第四十九条"}),
            SimpleNamespace(metadata={"source": "劳动合同法", "article": "第四十条"}),
        ]

    @staticmethod
    def _fake_docs_e04():
        # E04 敏感性场景：行政诉讼法（administrative 域）+ 民事诉讼法（civil 域）
        return [
            SimpleNamespace(metadata={"source": "行政诉讼法", "article": "第四十九条"}),
            SimpleNamespace(metadata={"source": "民事诉讼法", "article": "第六十四条"}),
        ]

    def _run(self, monkeypatch, *, r1ob: bool, case_domain, user_question, query, docs=None):
        from datetime import date

        import tools.legal_retrieval as lr
        from settings import settings
        from tools.contracts import RetrieveLawsInput, ToolContext

        monkeypatch.setattr(settings, "agent_dept_filter", True, raising=False)
        monkeypatch.setattr(settings, "agent_dept_filter_r1ob", r1ob, raising=False)
        monkeypatch.setattr(lr, "_retrieve", lambda **kwargs: docs() if docs else self._fake_docs())
        context = ToolContext(
            user_id=1,
            conversation_id=1,
            run_id="r1ob-test",
            law_as_of=date(2026, 9, 16),
            case_domain=case_domain,
            user_question=user_question,
        )
        tool_input = RetrieveLawsInput(query=query, k=4, category=None)
        out = lr.retrieve_laws(context, tool_input)
        return [(e.source, e.article) for e in out.evidence]

    def test_r1ob_on_uses_tier1_and_filters(self, monkeypatch):
        """r1ob 开 + tier-1 域码 civil：issue query 零指示词也过滤他域程序法。"""
        sources = self._run(monkeypatch, r1ob=True, case_domain="civil", user_question=E01_USER_Q, query=E01_ISSUE3)
        assert sources == [("劳动合同法", "第四十条")]

    def test_r1ob_tier1_sensitivity_e04(self, monkeypatch):
        """tier-1 敏感性（watch-it-fail 实证）：E04 issue2 下 tier-2 判 administrative
        （行政诉讼法属本域→保留），tier-1 域码 civil 推翻 → 行政诉讼法被剔、民事诉讼法保留。
        **回滚 tier-1 分支时本测试必红**（方向相反，tier-2 无法伪装通过）。"""
        on = self._run(
            monkeypatch,
            r1ob=True,
            case_domain="civil",
            user_question=E04_USER_Q,
            query=E04_ISSUE2,
            docs=self._fake_docs_e04,
        )
        assert on == [("民事诉讼法", "第六十四条")]  # tier-1=civil：行政诉讼法（他域）被剔
        off = self._run(
            monkeypatch,
            r1ob=False,
            case_domain="civil",
            user_question=E04_USER_Q,
            query=E04_ISSUE2,
            docs=self._fake_docs_e04,
        )
        assert off == [("行政诉讼法", "第四十九条")]  # tier-2=administrative：民事诉讼法（他域）被剔

    def test_r1ob_off_keeps_current_behavior(self, monkeypatch):
        """r1ob 关：判域退回 issue query（E01 issue3 零指示 → None → 不过滤，R1 现状）。"""
        sources = self._run(monkeypatch, r1ob=False, case_domain="civil", user_question=E01_USER_Q, query=E01_ISSUE3)
        assert ("行政诉讼法", "第四十九条") in sources  # 未过滤（保守现状）

    def test_r1ob_on_without_case_domain_uses_tier2(self, monkeypatch):
        """r1ob 开 + 无域码：tier-2 拼接（user_question 含'起诉' → civil）→ 过滤他域程序法。"""
        sources = self._run(monkeypatch, r1ob=True, case_domain=None, user_question=E01_USER_Q, query=E01_ISSUE3)
        assert sources == [("劳动合同法", "第四十条")]

    def test_r1ob_filter_yields_empty_pool_explicitly(self, monkeypatch):
        """空池可观测（预注册 §2.3 要求保留 R1 §3 条款）：r1ob 过滤致空池 →
        空证据列表 + 显式「未检索到」statement——不抛异常、不静默。"""
        from datetime import date

        import tools.legal_retrieval as lr
        from settings import settings
        from tools.contracts import RetrieveLawsInput, ToolContext

        monkeypatch.setattr(settings, "agent_dept_filter", True, raising=False)
        monkeypatch.setattr(settings, "agent_dept_filter_r1ob", True, raising=False)
        monkeypatch.setattr(
            lr,
            "_retrieve",
            lambda **kw: [SimpleNamespace(metadata={"source": "行政诉讼法", "article": "第四十九条"})],
        )
        ctx = ToolContext(
            user_id=1,
            conversation_id=1,
            run_id="t",
            law_as_of=date(2026, 9, 16),
            case_domain="civil",
            user_question=None,
        )
        out = lr.retrieve_laws(ctx, RetrieveLawsInput(query="行政主体资格", k=4, category=None))
        assert out.evidence == []
        assert "未检索到" in out.statement
