"""`Settings.__repr__` 必须掩盖敏感字段（2026-09-22 安全修复的回归守卫）。

**为什么有这条**：`case_domain` 闸的先红跑次里，pytest 打出
`AttributeError: Settings(...) has no attribute ...` ⇒ **整个 Settings repr 写进日志**，
里面是**明文真实密钥**（dashscope / zhipuai / siliconflow 的 api_key）与 `admin_password`。
CI/日志收集会把它们带走。修法是 `__repr__` 按字段名打码；本文件把它钉住。

判据（2 条 = 1 安全 + 1 控制）：
  ① 安全：repr 里**不得出现**任何敏感字段的实际值（含 key/secret/password/token 名）。
  ② 控制腿：非敏感字段仍然出现（防"把 repr 全打码"这种过度修复）。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import settings as settings_mod  # noqa: E402

MARKERS = ("api_key", "password", "secret", "token")


def test_repr_masks_every_secret_value():
    """① 安全：repr 里不得出现任何敏感字段的实际值。"""
    s = settings_mod.settings
    text = repr(s)
    leaked = [
        name for name, value in s if any(marker in name.lower() for marker in MARKERS) and value and str(value) in text
    ]
    assert not leaked, f"这些敏感字段的值仍出现在 repr 里（泄漏面）：{leaked}"
    assert "<masked" in text, "repr 里应有打码标记（否则说明打码逻辑没生效）"


def test_repr_keeps_non_secret_fields():
    """② 控制腿：非敏感字段仍要出现（防过度打码把 repr 变成无用信息）。"""
    text = repr(settings_mod.settings)
    assert "feature_hybrid=" in text, "非敏感字段应保留"
    assert "log_level=" in text, "非敏感字段应保留"
