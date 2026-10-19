"""C21-A Task 1 纯选择合同测试（S01–S12）。

只 import 标准库与 `qa_selection`（不引入任何产品模块），可用 `unittest` 直接执行。
覆盖设计合同 §3.1/§3.2 的窗口、同分组、重复认定与稳定身份选择；期望来自 Owner 规则，
**不由被测选择函数生成**。
"""

from __future__ import annotations

import itertools
import sys
import unittest
from pathlib import Path

# 自行定位 backend 导入路径（本文件在 backend/tests 下）。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qa_selection import (  # noqa: E402
    REASONS,
    WINDOW,
    Candidate,
    select_candidate,
)


def make(
    doc_id="a",
    answer="方案甲",
    score=0.95,
    allowed=True,
    *,
    question="合成问题甲",
    evidence="合成来源甲|第一条",
    basis="2026-10-01",
    fingerprint="",
    cand_id=7,
    drop=(),
    **over,
):
    """合成候选（固定项 G 的形状）；`drop` 用来删掉某个键以造「键缺失」样本。"""
    hit = {
        "question": question,
        "answer": answer,
        "evidence": evidence,
        "law_as_of_basis": basis,
        "fingerprint": fingerprint,
        "qa_candidate_id": cand_id,
    }
    for key in drop:
        hit.pop(key, None)
    hit.update(over)
    return Candidate(hit, doc_id, score, allowed)


class SelectionContract(unittest.TestCase):
    # ==================== S01 拒绝兄弟挡合格者 ====================

    def test_s01_rejected_sibling_does_not_block_eligible(self):
        bad = make("b", score=0.95, allowed=False)
        good = make("a", score=0.95)
        for items in itertools.permutations([bad, good]):
            result = select_candidate(items)
            self.assertIs(result.hit, good.hit, "选中的不是原对象 / 固定拿了第一项")
            self.assertEqual(result.reason, "hit")
            self.assertEqual(result.scanned, 2)

    def test_s01_all_rejected_is_no_eligible(self):
        bad_a = make("a", allowed=False)
        bad_b = make("b", allowed=False)
        for items in itertools.permutations([bad_a, bad_b]):
            result = select_candidate(items)
            self.assertIsNone(result.hit)
            self.assertEqual(result.reason, "no_eligible")

    # ==================== S02 同分不同答案 ====================

    def test_s02_same_score_different_answer_is_ambiguous(self):
        a = make("a")
        b = make("b", answer="不采用方案甲")
        for items in itertools.permutations([a, b]):
            result = select_candidate(items)
            self.assertIsNone(result.hit)
            self.assertEqual(result.reason, "ambiguous")

    # ==================== S03 五字段全同 → 最小 doc id ====================

    def test_s03_verified_duplicates_choose_stable_identity(self):
        a = make("a")
        b = make("b")
        for items in itertools.permutations([a, b]):
            result = select_candidate(items)
            self.assertIs(result.hit, a.hit, "未按 doc id 字典序选最小项 / 丢了原对象")
            self.assertEqual(result.reason, "hit")

    def test_s03_public_keys_and_doc_id_are_preserved(self):
        a = make("a")
        b = make("b")
        result = select_candidate([b, a])
        self.assertIs(result.hit, a.hit)
        self.assertEqual(
            set(result.hit),
            {"question", "answer", "evidence", "law_as_of_basis", "fingerprint", "qa_candidate_id"},
        )
        self.assertEqual(result.hit.get("qa_candidate_id"), 7)

    # ==================== S04 五元组任一不同 ====================

    def test_s04_any_tuple_field_difference_is_ambiguous(self):
        variants = {
            "evidence": make("b", evidence="合成来源乙|第二条"),
            "basis": make("b", basis="2026-10-02"),
            "fingerprint": make("b", fingerprint="opt-1"),
            "question": make("b", question="合成问题乙"),
        }
        for label, other in variants.items():
            a = make("a")
            for items in itertools.permutations([a, other]):
                result = select_candidate(items)
                self.assertIsNone(result.hit, label)
                self.assertEqual(result.reason, "ambiguous", label)

    def test_s04_same_candidate_id_cannot_merge_different_content(self):
        a = make("a", cand_id=7)
        b = make("b", cand_id=7, answer="不采用方案甲")
        for items in itertools.permutations([a, b]):
            result = select_candidate(items)
            self.assertEqual(result.reason, "ambiguous", "以同一 candidate id 合并了不同内容")

    # ==================== S05 必要字段缺失/非法 ====================

    def test_s05_missing_or_invalid_required_fields_never_confirm_duplicate(self):
        cases = {
            "missing_basis": ("a", make("b", basis=None, drop=("law_as_of_basis",))),
            "invalid_basis": ("a", make("b", basis="2026-13-40")),
            "missing_fingerprint_key": ("a", make("b", drop=("fingerprint",))),
            "empty_answer": ("a", make("b", answer="   ")),
            "empty_evidence": ("a", make("b", evidence="")),
        }
        for label, (_, other) in cases.items():
            a = make("a")
            for items in itertools.permutations([a, other]):
                result = select_candidate(items)
                self.assertIsNone(result.hit, label)
                self.assertEqual(result.reason, "ambiguous", label)

    # ==================== S06 非选项题 fingerprint 键在且为空 ====================

    def test_s06_empty_fingerprint_value_still_confirms_duplicate(self):
        a = make("a", fingerprint="")
        b = make("b", fingerprint="")
        result = select_candidate([b, a])
        self.assertIs(result.hit, a.hit)
        self.assertEqual(result.reason, "hit")

    def test_s06_missing_fingerprint_key_differs_from_empty_value(self):
        present = make("a", fingerprint="")
        missing = make("b", drop=("fingerprint",))
        result = select_candidate([present, missing])
        self.assertIsNone(result.hit, "「键缺失」被当成「键存在且为空」")
        self.assertEqual(result.reason, "ambiguous")

    # ==================== S07 固定锚，不链式扩组 ====================

    def test_s07_top_two_differing_content_is_ambiguous(self):
        c0 = make("a", answer="方案甲", score=0.9500000)
        c1 = make("b", answer="方案甲", score=0.9500009)
        c2 = make("c", answer="不采用方案甲", score=0.9500018)
        for items in itertools.permutations([c0, c1, c2]):
            result = select_candidate(items)
            self.assertIsNone(result.hit)
            self.assertEqual(result.reason, "ambiguous", "同分组只应以最高分为锚")

    def test_s07_lowest_tier_is_not_chained_into_the_group(self):
        # 最高两条同内容；最低（0.9500000）内容相同但带最小 doc id——若被链式并组就会胜出。
        c0 = make("aa", answer="方案甲", score=0.9500000)
        c1 = make("b", answer="方案甲", score=0.9500009)
        c2 = make("c", answer="方案甲", score=0.9500018)
        result = select_candidate([c0, c1, c2])
        self.assertIs(result.hit, c1.hit, "最低项被链式扩组纳入")
        self.assertEqual(result.reason, "hit")

    # ==================== S08 raw 分胜出，不以公开舍入造同分 ====================

    def test_s08_raw_score_beats_public_rounding(self):
        a = make("a", answer="方案甲", score=0.95004)
        b = make("b", answer="不采用方案甲", score=0.95000)
        self.assertEqual(round(a.raw_score, 4), round(b.raw_score, 4), "两支公开分本就相等，样本无效")
        for items in itertools.permutations([a, b]):
            result = select_candidate(items)
            self.assertIs(result.hit, a.hit, "以公开舍入分制造了同分")
            self.assertEqual(result.reason, "hit")

    # ==================== S09 空窗/低分/无资格/非有限数 ====================

    def test_s09_empty_window(self):
        result = select_candidate([])
        self.assertIsNone(result.hit)
        self.assertEqual(result.reason, "empty")
        self.assertEqual(result.scanned, 0)

    def test_s09_all_below_threshold(self):
        low = [make("a", score=0.5), make("b", score=0.6)]
        result = select_candidate(low)
        self.assertIsNone(result.hit)
        self.assertEqual(result.reason, "no_eligible")
        self.assertEqual(result.scanned, 2)

    def test_s09_all_ineligible(self):
        bad = [make("a", score=0.95, allowed=False), make("b", score=0.94, allowed=False)]
        result = select_candidate(bad)
        self.assertIsNone(result.hit)
        self.assertEqual(result.reason, "no_eligible")

    def test_s09_non_finite_scores_are_not_admitted(self):
        for bad_score in (float("nan"), float("inf"), float("-inf")):
            result = select_candidate([make("a", score=bad_score)])
            self.assertIsNone(result.hit)
            self.assertEqual(result.reason, "score_error", bad_score)

    # ==================== S10 缺稳定身份 ====================

    def test_s10_duplicate_without_stable_identity_is_unstable(self):
        a = make(None, cand_id=None, score=0.95)
        b = make(None, cand_id=None, score=0.95)
        for items in itertools.permutations([a, b]):
            result = select_candidate(items)
            self.assertIsNone(result.hit)
            self.assertEqual(result.reason, "unstable_id")

    def test_s10_single_real_unlinked_seed_is_served_by_doc_id(self):
        seed = make("seed-1", cand_id=None, score=0.95)
        result = select_candidate([seed])
        self.assertIs(result.hit, seed.hit)
        self.assertEqual(result.reason, "hit")

    def test_s10_no_doc_id_but_distinct_candidate_id_is_stable(self):
        a = make(None, cand_id=7)
        b = make(None, cand_id=8)
        for items in itertools.permutations([a, b]):
            result = select_candidate(items)
            self.assertIs(result.hit, a.hit, "candidate id 数值未用作兜底排序键")
            self.assertEqual(result.reason, "hit")

    # ==================== S11 前 8 全拒、第 9 合格 ====================

    def test_s11_sentinel_is_never_a_service_item(self):
        window = [make(f"w{i}", score=0.95, allowed=False) for i in range(WINDOW)]
        sentinel = make("s", score=0.99, allowed=True)
        result = select_candidate(window + [sentinel])
        self.assertIsNone(result.hit, "拿第 9 条兜底了")
        self.assertEqual(result.reason, "no_eligible")
        self.assertEqual(result.scanned, WINDOW)

    # ==================== S12 边界哨兵风险 ====================
    #
    # 哨兵是**第 9 条**（窗口 8+1）：所以下面的窗都补满 8 条（前 7 条拒绝），第 9 条才是哨兵。

    def _window_with(self, good, sentinel):
        fillers = [make(f"bad{i}", score=0.95, allowed=False) for i in range(WINDOW - 1)]
        items = fillers + [good, sentinel]
        self.assertEqual(len(items), WINDOW + 1)
        return items

    def test_s12_sentinel_in_tie_band_is_window_boundary(self):
        good = make("a", score=0.95)
        sentinel = make("s", score=0.9500005, allowed=True)
        result = select_candidate(self._window_with(good, sentinel))
        self.assertIsNone(result.hit)
        self.assertEqual(result.reason, "window_boundary")

    def test_s12_sentinel_higher_is_window_boundary(self):
        good = make("a", score=0.95)
        sentinel = make("s", score=1.0, allowed=True)
        result = select_candidate(self._window_with(good, sentinel))
        self.assertIsNone(result.hit)
        self.assertEqual(result.reason, "window_boundary")

    def test_s12_low_sentinel_leaves_the_window_item_selectable(self):
        good = make("a", score=0.95)
        sentinel = make("s", score=0.94, allowed=True)
        result = select_candidate(self._window_with(good, sentinel))
        self.assertIs(result.hit, good.hit)
        self.assertEqual(result.reason, "hit")

    def test_s12_explicit_boundary_unsafe_flag_rejects(self):
        good = make("a", score=0.95)
        result = select_candidate([good], boundary_unsafe=True)
        self.assertIsNone(result.hit)
        self.assertEqual(result.reason, "window_boundary")

    # ==================== reason 枚举与确定性 ====================

    def test_reason_vocabulary_is_closed(self):
        observed = set()
        cases = [
            [make("a")],
            [],
            [make("a", score=float("nan"))],
            [make("a", allowed=False)],
            [make("a"), make("b", answer="不采用方案甲")],
            [make(None, cand_id=None), make(None, cand_id=None)],
            self._window_with(make("a"), make("s", score=1.0, allowed=True)),
        ]
        for items in cases:
            observed.add(select_candidate(items).reason)
        self.assertTrue(observed <= set(REASONS), observed)
        self.assertEqual(
            observed,
            {"hit", "empty", "score_error", "no_eligible", "ambiguous", "unstable_id", "window_boundary"},
        )

    def test_input_sequence_is_not_mutated(self):
        a = make("a")
        b = make("b")
        original = [b, a]
        snapshot = list(original)
        select_candidate(original)
        self.assertEqual([id(x) for x in original], [id(x) for x in snapshot], "入参序列被就地改动")

    def test_permutations_are_order_independent(self):
        a = make("a")
        b = make("b")
        results = {
            (select_candidate(items).reason, id(select_candidate(items).hit))
            for items in itertools.permutations([a, b])
        }
        # 两个排列都必须选中 a 的原对象：reason 一致，且命中对象 id 唯一。
        self.assertEqual(len(results), 1)
        self.assertEqual(next(iter(results)), ("hit", id(a.hit)))


if __name__ == "__main__":
    unittest.main()
