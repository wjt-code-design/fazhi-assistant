"""R11 时效确定性计算（limitation_calc）测试。

对照 docs/external-harness-plan-gap-analysis-20260918.md P0-1 与
agent/limitation_calc.py docstring 的边界说明。
"""

from datetime import date

from legal_workflow.limitation_calc import (
    CIVIL_CODE_EFFECTIVE,
    CIVIL_GENERAL_YEARS,
    CIVIL_MAXIMUM_YEARS,
    CIVIL_PRE_CODE_YEARS,
    LABOR_ARBITRATION_YEARS,
    calc_limitation,
    controlled_limitation_tokens,
    extract_dates,
)


def test_constants_match_legal_sources():
    """常量本身即数据真源：改动必须显式过本测试（防手滑改错法条数字）。"""
    assert CIVIL_GENERAL_YEARS == 3  # 民法典第188条第1款
    assert CIVIL_MAXIMUM_YEARS == 20  # 民法典第188条第2款
    assert CIVIL_PRE_CODE_YEARS == 2  # 民法通则第135条
    assert LABOR_ARBITRATION_YEARS == 1  # 劳动争议调解仲裁法第27条
    assert CIVIL_CODE_EFFECTIVE == date(2021, 1, 1)  # 民法典第1260条


def test_extract_dates_basic_and_invalid():
    dates = extract_dates(["2023年8月1日受损", "于2024年02月30日就诊", "二〇二一年一月一日（不解析）"])
    assert dates == [date(2023, 8, 1)]  # 非法日期跳过；中文数字日期 fail-open
    assert extract_dates(["没有日期"]) == []
    assert extract_dates([]) == []


def test_extract_dates_nfkc_fullwidth():
    assert extract_dates(["２０２２年０３月０４日"]) == [date(2022, 3, 4)]


def test_civil_post_cutoff_basic():
    result = calc_limitation("civil", fact_date=date(2023, 8, 1), as_of=date(2026, 8, 1))
    assert result is not None
    assert result["law_basis"] == "《民法典》第188条"
    assert result["general_years"] == 3
    assert result["start_date"] == date(2023, 8, 1)  # 缺 knowledge_date → 以 fact_date 起算
    assert result["expiry_date"] == date(2026, 8, 1)
    assert result["expired_as_of"] is False  # 当天到期，次日起过期
    assert result["needs_case_review"] is False
    assert result["max_protection_expiry"] == date(2043, 8, 1)


def test_civil_post_cutoff_expired():
    result = calc_limitation("civil", fact_date=date(2023, 8, 1), as_of=date(2026, 8, 2))
    assert result is not None and result["expired_as_of"] is True


def test_civil_knowledge_date_defers_start():
    """知道/应当知道日晚于受损日 → 起算点后移（民法典188条第2款）。"""
    result = calc_limitation("civil", fact_date=date(2021, 6, 1), knowledge_date=date(2024, 1, 1))
    assert result is not None
    assert result["start_date"] == date(2024, 1, 1)
    assert result["expiry_date"] == date(2027, 1, 1)


def test_civil_interruption_restarts_period():
    """中断（民法典195条）：自中断之日起重新计算。"""
    result = calc_limitation(
        "civil",
        fact_date=date(2021, 6, 1),
        interruption_dates=[date(2023, 3, 1), date(2020, 1, 1)],  # 后者在起算前 → 忽略
    )
    assert result is not None
    assert result["expiry_date"] == date(2026, 3, 1)


def test_civil_maximum_period_caps_restarted_period():
    """中断重新起算不得突破最长20年（188条第2款，不适用中止中断）。

    前提（民法典时代）：fact 2021-06-01 → 最长保护期至 2041-06-01；
    起算 2038-01-01 → 原届满 2041-01-01；2040-06-01 中断 → 重新计算至
    2043-06-01，突破上限 → 必须被截断到 2041-06-01。
    """
    result = calc_limitation(
        "civil",
        fact_date=date(2021, 6, 1),
        knowledge_date=date(2038, 1, 1),
        interruption_dates=[date(2040, 6, 1)],
    )
    assert result is not None
    assert result["max_protection_expiry"] == date(2041, 6, 1)
    assert result["expiry_date"] == date(2041, 6, 1)
    assert any("20年" in note for note in result["notes"])


def test_civil_interruption_outside_running_period_is_ignored():
    """中断日必须落在 [起算, 届满] 区间内：期间已过届满日的中断日不延长时效。"""
    result = calc_limitation(
        "civil",
        fact_date=date(2021, 6, 1),
        knowledge_date=date(2021, 6, 1),
        interruption_dates=[date(2024, 10, 1)],  # 普通时效 2024-06-01 已届满
    )
    assert result is not None
    assert result["expiry_date"] == date(2024, 6, 1)  # 不受区间外中断影响
    assert result["expired_as_of"] is None  # 未传 as_of → 不判定（保持确定性）


def test_civil_pre_cutoff_flags_case_review():
    """跨 2021-01-01（方案 T1）：给旧法口径 + 强制 needs_case_review，不固化衔接判断。"""
    result = calc_limitation("civil", fact_date=date(2019, 5, 1))
    assert result is not None
    assert result["general_years"] == 3
    assert result["needs_case_review"] is True
    assert result["expiry_date"] == date(2022, 5, 1)
    assert "民法典" in result["notes"][0]


def test_labor_arbitration_one_year():
    result = calc_limitation("labor_arbitration", fact_date=date(2025, 1, 1), as_of=date(2026, 1, 2))
    assert result is not None
    assert result["general_years"] == 1
    assert result["expiry_date"] == date(2026, 1, 1)
    assert result["expired_as_of"] is True


def test_labor_remuneration_ongoing_not_limited():
    """第27条第4款：劳动关系存续期间拖欠劳动报酬不受1年限制。"""
    result = calc_limitation("labor_remuneration", fact_date=date(2020, 1, 1))
    assert result is not None
    assert result["not_limited_within_relationship"] is True
    assert result["expiry_date"] is None


def test_labor_remuneration_terminated_starts_from_termination():
    result = calc_limitation("labor_remuneration", fact_date=date(2020, 1, 1), labor_termination_date=date(2025, 3, 15))
    assert result is not None
    assert result["start_date"] == date(2025, 3, 15)
    assert result["expiry_date"] == date(2026, 3, 15)


def test_invalid_claim_type_returns_none():
    assert calc_limitation("criminal", fact_date=date(2023, 1, 1)) is None


def test_feb29_add_years_lands_feb28():
    result = calc_limitation("civil", fact_date=date(2024, 2, 29))
    assert result is not None
    assert result["expiry_date"] == date(2027, 2, 28)


# ---- 受控 token（writer/verifier 白名单消费口径）----


def test_tokens_civil_post_cutoff():
    tokens = controlled_limitation_tokens("本案诉讼时效期间为三年。", ["2023年8月1日受损"])
    assert tokens == {"duration:3:年", "duration:20:年"}


def test_tokens_civil_pre_cutoff_empty_fail_open():
    """分水岭前事实 → 空集（衔接期不固化判断，fail-open）。"""
    assert controlled_limitation_tokens("诉讼时效为三年。", ["2019年5月1日受损"]) == set()


def test_tokens_civil_without_dates_empty():
    assert controlled_limitation_tokens("诉讼时效为三年。", ["没有日期的事实"]) == set()


def test_tokens_labor():
    assert controlled_limitation_tokens("仲裁时效为一年。", ["2020年1月1日入职"]) == {"duration:1:年"}


def test_tokens_no_claim_keyword_empty():
    """claim 不含时效关键词 → 不放行（防年份常量泄漏给无关 claim）。"""
    assert controlled_limitation_tokens("借款期限为三年。", ["2023年8月1日"]) == set()


def test_tokens_match_writer_numeric_token_contract():
    """跨模块契约：controlled token 必须与 writer.numeric_tokens 的产出形态一致，
    否则白名单减法恒为空（形同虚设）。"""
    from legal_workflow.writer import numeric_tokens

    claim = "根据《民法典》第一百八十八条，诉讼时效期间为三年，最长保护二十年。"
    produced = numeric_tokens(claim, loose_amounts=True)
    allowed = controlled_limitation_tokens(claim, ["2023年8月1日受损"])
    assert {"duration:3:年", "duration:20:年"} <= produced
    assert allowed == {"duration:3:年", "duration:20:年"} <= produced


# ---- writer 集成（numeric_matching_v2 门限联动，镜像 fee_calc 消费点）----


def _writer_state_with_dated_fact():
    from datetime import datetime

    from legal_workflow.schemas import (
        Evidence,
        Fact,
        LegalAgentState,
        LegalIssue,
        LegalValidity,
        Observation,
        SourceType,
    )

    return LegalAgentState(
        issues=[
            LegalIssue(
                issue_id="issue-a",
                question="诉讼时效多久？",
                facts=[
                    Fact(
                        statement="2023年8月1日对方拖欠货款",
                        source=SourceType.USER,
                        source_ref="user:q",
                        confidence=1,
                    )
                ],
            )
        ],
        evidence=[
            Evidence(
                evidence_id="ev-a",
                source_id="source-ev-a",
                source_ref="《民法典》第一百八十八条",
                source_type=SourceType.STATUTE,
                snippet="《民法典》第一百八十八条规定诉讼时效期间为三年。",
                legal_validity=LegalValidity.EFFECTIVE,
                acquired_at=datetime(2026, 8, 30),
            )
        ],
        # build_writer_payload 只收「经 observation 关联到本争点」的证据。
        observations=[
            Observation(
                issue_id="issue-a",
                statement="retrieved statute",
                evidence_ids=["ev-a"],
                confidence=0.9,
            )
        ],
    )


class _ParaphraseGenerator:
    """证据只含"三年"、claim 复述"三年 + 二十年"——20年 token 无文本来源，
    只能由受控时效计算放行（R11 的真实消费场景）。"""

    TEXT = "根据《民法典》第一百八十八条，自权利受损之日起诉讼时效为三年，最长保护二十年。"

    def generate(self, *, payload, system_prompt, feedback=None):
        issue = payload.issues[0]
        return {
            "claims": [
                {
                    "local_id": "local-1",
                    "issue_id": issue.issue_id,
                    "text": self.TEXT,
                    "evidence_ids": [issue.evidence[0].evidence_id],
                    "fact_ids": [],
                    "section": "conclusion",
                }
            ],
            "missing_information": [],
        }


def test_writer_gate_on_allows_computed_limitation_numbers(monkeypatch):
    import settings as settings_module
    from legal_workflow.writer import EvidenceBoundedWriter, WriterStatus

    monkeypatch.setattr(settings_module.settings, "numeric_matching_v2", True)
    result = EvidenceBoundedWriter(_ParaphraseGenerator()).render(_writer_state_with_dated_fact())
    assert result.status is WriterStatus.READY


def test_writer_gate_off_blocks_the_same_numbers(monkeypatch):
    """对照（watch-it-fail 的正向面）：不开 numeric_matching_v2（= 无受控放行集），
    同一 claim 因 20 年 token 无来源被拦——证明放行确实来自本模块而非碰巧通过。"""
    import settings as settings_module
    from legal_workflow.writer import EvidenceBoundedWriter, WriterStatus

    monkeypatch.setattr(settings_module.settings, "numeric_matching_v2", False)
    result = EvidenceBoundedWriter(_ParaphraseGenerator()).render(_writer_state_with_dated_fact())
    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "UNSUPPORTED_NUMERIC_TOKEN"
