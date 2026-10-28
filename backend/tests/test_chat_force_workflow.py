"""Gate 4 目标测试：手动深入分析入口 ChatIn.force_agent（先红后绿：probe C01 red→green）。

- 默认 False（现有行为不变，不静默切换）
- force_agent=True 合法载荷校验
- resume 三件套强制校验不受 force 影响（失败路径防线仍生效）
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas import ChatIn


def test_force_agent_defaults_false():
    m = ChatIn(content="问题")
    assert m.force_agent is False


def test_force_agent_true_parses():
    m = ChatIn(content="问题", force_agent=True)
    assert m.force_agent is True


def test_resume_identity_still_required_with_force_agent():
    # 失败路径：即使 force_agent=True，resume 三件套缺失仍必须被拒绝
    with pytest.raises(ValidationError):
        ChatIn(content="回答", force_agent=True, agent_run_id="00000000-0000-0000-0000-000000000001")
