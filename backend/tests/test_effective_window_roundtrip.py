"""R15-3 前置：**写↔读贯通**契约测试 —— 带效力区间的条文，检索侧必须按 cutoff 正确取舍。

**为什么补这条**：写侧（`knowledge_service.add_text` 的 `extra_meta` 归一化 + `law_versions`）与
读侧（`retrieval_core.is_valid_by_time` ← `retrieval._valid_docs` ← `exact_article_lookup`）
都**早已实现**，各自也有纯函数测试（`test_phase5` / `test_law_versions`）；
但**"写进去的效力区间，检索时真的按 cutoff 取舍"这条贯通链没有测试**。
R15-3 的阻塞点只有"历史法文本"这一项数据——本测试把它变成**可验证的准备就绪**：
数据一到，只要灌进去，取舍行为就已被钉住。

判据（4 条边界 + 1 条状态可见性）：
  ① 2019-06-01 ⇒ 旧版（区间内）
  ② 2020-12-31 ⇒ 旧版（`effective_to == cutoff` 当日仍有效 —— 边界语义）
  ③ 2021-01-01 ⇒ 新版（`effective_from == cutoff` 当日生效 —— 边界语义）
  ④ 2026-09-22 ⇒ 新版（旧版已过废止日）
  ⑤ 写入侧 `status` 落地可见（`count_docs(status="已废止")` ≥ 1）
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import knowledge_service as ks  # noqa: E402
import retrieval as R  # noqa: E402

SRC = "效力窗口贯通测试法"
ART = "第一条"
OLD_TEXT = "第一条 【旧版】本法施行前的条文内容（贯通测试）"
NEW_TEXT = "第一条 【新版】修正后的条文内容（贯通测试）"


def _write_two_versions() -> None:
    """写两条同法同条号、不同效力期的记录（写侧应视为不同版本而并存）。"""
    ks.add_text(
        OLD_TEXT,
        source=SRC,
        article=ART,
        origin="manual",
        extra_meta={"effective_from": "2019-01-01", "effective_to": "2020-12-31", "status": "已废止"},
    )
    ks.add_text(
        NEW_TEXT,
        source=SRC,
        article=ART,
        origin="manual",
        extra_meta={"effective_from": "2021-01-01", "status": "现行"},
    )


def _texts_at(cutoff: str) -> list[str]:
    return [d.page_content for d in R.exact_article_lookup(SRC, ART, cutoff=cutoff)]


def _setup_once() -> None:
    if not R.exact_article_lookup(SRC, ART, cutoff="2019-06-01"):
        _write_two_versions()


def test_write_then_read_old_version_in_window():
    """① 区间内（2019-06-01）⇒ 只应取到旧版。"""
    _setup_once()
    texts = _texts_at("2019-06-01")
    assert OLD_TEXT in texts, f"旧版应在 2019-06-01 可见，实得 {texts}"
    assert NEW_TEXT not in texts, f"新版 2021-01-01 才生效，2019-06-01 不应可见，实得 {texts}"


def test_write_then_read_boundary_last_day():
    """② 边界：`effective_to == cutoff` 当日仍有效（废止日当天没失效）。"""
    _setup_once()
    texts = _texts_at("2020-12-31")
    assert OLD_TEXT in texts, f"废止日当天仍应可见（边界语义），实得 {texts}"


def test_write_then_read_boundary_first_day():
    """③ 边界：`effective_from == cutoff` 当日即生效；同日旧版应已被取代。"""
    _setup_once()
    texts = _texts_at("2021-01-01")
    assert NEW_TEXT in texts, f"生效日当天应可见新版，实得 {texts}"
    assert OLD_TEXT not in texts, f"2021-01-01 已过旧版废止日，不应可见，实得 {texts}"


def test_write_then_read_today_only_new():
    """④ 今天 ⇒ 只应取到新版。"""
    _setup_once()
    texts = _texts_at("2026-09-22")
    assert NEW_TEXT in texts and OLD_TEXT not in texts, f"今日应只见新版，实得 {texts}"


def test_write_side_status_visible():
    """⑤ 写入侧 `status` 真的落到 metadata（`count_docs` 能按状态数出来）。"""
    _setup_once()
    assert ks.count_docs(status="已废止") >= 1, "写入的『已废止』状态未在库中可见"
