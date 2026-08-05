"""multi_extract 纯函数单测（零 BGE——multi_extract 只依赖 re，pytest 秒级跑，不停后端）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multi_extract import multi_ok  # noqa: E402

# 通用金标：A、B 真，C 假（code-review 顺手项：抽 helper 消除三用例重复的 ov/ans 结构）。
_OV = {"A": True, "B": True, "C": False}


def _item(letter: str, verdict: str) -> str:
    return f"**{letter}. 内容**【判断】{verdict}\n"


# ---------------- multi_ok 全选对判定 ----------------
def test_multi_ok_none_when_not_multi():
    # 正确项 ≤1 → 非多选，不参与 multi_ok 统计
    assert multi_ok("", {"A": True, "B": False}) is None
    assert multi_ok("", {}) is None


def test_multi_ok_true_when_all_correct():
    assert multi_ok(_item("A", "正确") + _item("B", "正确") + _item("C", "错误"), _OV) is True


def test_multi_ok_false_when_miss_required():
    # 漏选 B（正确项没全声明）→ 不算全选对
    assert multi_ok(_item("A", "正确") + _item("B", "错误") + _item("C", "错误"), _OV) is False


def test_multi_ok_false_when_extra_false_declared():
    """金标 C=错误，回答却把 C 也声明正确（选错 C）→ 不算全选对。

    2026-08-05 diagnosing-bugs：原实现 `true_letters <= declared` 只查"不漏选"，
    未查"不误选"——declared 含假项仍返回 True（选多了也算对），与「全选对」语义不符。
    """
    assert multi_ok(_item("A", "正确") + _item("B", "正确") + _item("C", "正确"), _OV) is False


# ---------------- 抽取盲区修复（2026-08-05 Step 1，id8/id10 真实答案片段） ----------------
def test_multi_ok_id8_correct_answer_colon():
    """id8 机动车赔偿：结论 '正确答案：A、B、C'（冒号格式，原连接词表不认'答案'）→ 全选对。"""
    ov = {"A": True, "B": True, "C": True, "D": False}
    ans = "综上所述，选项 A、B、C 均符合规定，选项 D 表述错误。**正确答案：A、B、C**"
    assert multi_ok(ans, ov) is True


def test_multi_ok_id10_all_four_signal():
    """id10 商标权：'A、B、C、D 四个选项的说法均正确' + 结论'均为正确/全选' → 全选对。"""
    ov = {"A": True, "B": True, "C": True, "D": True}
    ans = (
        "根据提供的《商标法》条文，本题中 **A、B、C、D 四个选项的说法均正确**。"
        "…**A、B、C、D 四项表述均有明确法律依据，均为正确说法**。若为多选题，则全选。"
    )
    assert multi_ok(ans, ov) is True


def test_multi_ok_full_select_suppressed_when_explicit_wrong():
    """答案'全选'但显式判定 C 错误（自相矛盾）→ 全选信号抑制，不因结论'全选'判全对。"""
    ov = {"A": True, "B": True, "C": True, "D": True}
    ans = (
        "**A项判断：正确。**\n"
        "**B项判断：正确。**\n"
        "**C项判断：错误。**\n"
        "结论：本题全选。"
    )
    assert multi_ok(ans, ov) is False


def test_multi_ok_partial_mean_correct_not_all():
    """部分选项'均正确'不是全选：A、B 均正确，金标 A、B、C → 漏 C，不全对。"""
    ov = {"A": True, "B": True, "C": True, "D": False}
    ans = "A、B 均正确，C、D 说法错误。"
    assert multi_ok(ans, ov) is False
