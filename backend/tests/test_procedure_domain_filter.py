"""_procedure_domain_excludes 单测：程序法域限定（P0-2）。

覆盖：三域各自排除集、无域词不过滤、多域同现兜底不过滤、
实体法与司法解释永不排除、边界词不误判。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from retrieval import _procedure_domain_excludes  # noqa: E402


def test_civil_domain_excludes_other_procedure_laws():
    ex = _procedure_domain_excludes("民事诉讼中谁承担举证责任？")
    assert ex == frozenset({"刑事诉讼法", "行政诉讼法", "行政复议法"})
    # 民诉法本身与民诉解释不在排除集
    assert "民事诉讼法" not in ex


def test_criminal_domain():
    ex = _procedure_domain_excludes("我被骗了，报警后检察院会公诉吗？刑事诉讼流程是什么")
    assert ex == frozenset({"民事诉讼法", "行政诉讼法", "行政复议法"})


def test_administrative_domain():
    ex = _procedure_domain_excludes("我对行政处罚不服，能申请行政复议还是提起行政诉讼？")
    assert ex == frozenset({"刑事诉讼法", "民事诉讼法"})


def test_no_domain_word_no_filter():
    # 纯实体法问题：不过滤
    assert _procedure_domain_excludes("我交了十万元定金，卖家不卖了能拿回二十万吗？") == frozenset()
    assert _procedure_domain_excludes("楼上漏水泡坏我家地板怎么赔？") == frozenset()
    assert _procedure_domain_excludes("") == frozenset()


def test_multi_domain_fallback_no_filter():
    # 同时点名多个法域 ⇒ 不过滤（宁可少排不可误排）
    q = "我应该起诉他还是报警？刑事诉讼和民事诉讼哪个更适合"
    assert _procedure_domain_excludes(q) == frozenset()


def test_entity_laws_never_excluded():
    # 即使命中法域，民法典/司法解释也不在排除集
    for q in ("民事诉讼中定金能双倍返还吗", "报警后诈骗罪怎么认定", "行政诉讼中政府违约怎么赔"):
        ex = _procedure_domain_excludes(q)
        for keep in ("民法典", "刑法", "劳动合同法", "民法典合同编通则解释"):
            assert keep not in ex


def test_criminal_case_phrasing_is_not_misread_as_civil():
    """「一审/二审/上诉」不属于任何单一法域（回归 q103，2026-10-26）。

    旧词表把「上诉/二审」算进 civil，于是「刑事案件一审的裁定…提起了上诉」被判成民事，
    反而把刑事诉讼法排除掉——实测 q103 召回全是民诉法 177-182，期望的刑诉法 240 完全缺席。
    """
    q = "刑事案件一审的裁定我不服，提起了上诉，二审法院一般会怎么处理？"
    ex = _procedure_domain_excludes(q)
    assert ex == frozenset({"民事诉讼法", "行政诉讼法", "行政复议法"})
    # 只有「上诉/二审」而无域词 ⇒ 不再硬判民事，不过滤（宁可不排不可误排）
    assert _procedure_domain_excludes("判决不服可以上诉吗？") == frozenset()
    assert _procedure_domain_excludes("二审要开庭吗？") == frozenset()
