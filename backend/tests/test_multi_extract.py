"""multi_extract 纯函数单测（零 BGE——multi_extract 只依赖 re，pytest 秒级跑，不停后端）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multi_extract import multi_ok  # noqa: E402


# ---------------- multi_ok 全选对判定 ----------------
def test_multi_ok_none_when_not_multi():
    # 正确项 ≤1 → 非多选，不参与 multi_ok 统计
    assert multi_ok("", {"A": True, "B": False}) is None
    assert multi_ok("", {}) is None


def test_multi_ok_true_when_all_correct():
    ov = {"A": True, "B": True, "C": False}
    ans = (
        "**A. 内容**【判断】正确\n"
        "**B. 内容**【判断】正确\n"
        "**C. 内容**【判断】错误\n"
    )
    assert multi_ok(ans, ov) is True


def test_multi_ok_false_when_miss_required():
    # 漏选 B（正确项没全声明）→ 不算全选对
    ov = {"A": True, "B": True, "C": False}
    ans = (
        "**A. 内容**【判断】正确\n"
        "**B. 内容**【判断】错误\n"
        "**C. 内容**【判断】错误\n"
    )
    assert multi_ok(ans, ov) is False


def test_multi_ok_false_when_extra_false_declared():
    """金标 C=错误，回答却把 C 也声明正确（选错 C）→ 不算全选对。

    2026-08-05 diagnosing-bugs：当前实现 `true_letters <= declared` 只查"不漏选"，
    未查"不误选"——declared 含假项仍返回 True（选多了也算对），与「全选对」语义不符。
    """
    ov = {"A": True, "B": True, "C": False}
    ans = (
        "**A. 内容**【判断】正确\n"
        "**B. 内容**【判断】正确\n"
        "**C. 内容**【判断】正确\n"
    )
    assert multi_ok(ans, ov) is False
