"""服务器无关项 6：`case_domain` 评测通道闸 + 顺带修 `Settings.__repr__` 明文密钥泄漏。

背景（安全发现，2026-09-22）：`case_domain` 闸的先红跑次里，pytest 打印
`AttributeError: Settings(...) has no attribute ...` ⇒ **整个 Settings 对象 repr 被写进日志**，
其中含**明文真实密钥**（dashscope / zhipuai / siliconflow 的 key）与 admin 密码。
任何测试失败/断言失败都会复现这条泄漏 ⇒ 修 `__repr__` 统一打码。
"""

from __future__ import annotations

import pathlib
import re

BE = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper/backend")
OUT = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t12-frontend-sweep-20260920")

# ── A. settings.py：新增开关 + repr 打码 ──
sp = BE / "settings.py"
s = sp.read_text(encoding="utf-8")

anchor_cfg = '    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")\n'
assert s.count(anchor_cfg) == 1
repr_block = anchor_cfg + '''
    # 敏感字段名标记（大小写不敏感的子串匹配）：命中即打码。
    _SECRET_NAME_MARKERS = ("api_key", "password", "secret", "token")

    def __repr__(self) -> str:
        """掩盖敏感字段值（2026-09-22 安全修复）。

        为什么必须修：`AttributeError`/断言失败会把 **Settings 的 repr 整段打进日志**——
        实测在 pytest 失败输出里泄漏过明文 `dashscope_api_key`/`zhipuai_api_key`/
        `siliconflow_api_key` 与 `admin_password`。任何 CI 日志收集都会把它带走。
        注意：`model_dump()` **不在**本修复范围内（未观察到它进入日志路径）；
        若将来有接口输出配置，仍需另行脱敏。
        """
        parts: list[str] = []
        for name, value in self:
            if any(marker in name.lower() for marker in self._SECRET_NAME_MARKERS) and value:
                parts.append(f"{name}='<masked:len={len(str(value))}>'")
            else:
                parts.append(f"{name}={value!r}")
        return f"Settings({', '.join(parts)})"
'''
s = s.replace(anchor_cfg, repr_block, 1)

anchor_flag = "    allow_client_law_as_of: bool = False\n"
assert s.count(anchor_flag) == 1
new_flag = anchor_flag + '''
    # 同款的另一半（Owner 2026-09-21 裁定的 `case_domain` 侧，2026-09-22 落地）：
    # False（默认）⇒ 客户端传的 `case_domain` 被忽略（各消费方落 None，行为与"没传"一致）；
    # True ⇒ 评测/灰度放行。理由：该值决定 R1-OB 判域，属评测输入而非用户偏好；
    # 前端实测**从不传**该字段 ⇒ 默认关在生产**零行为变化**。
    allow_client_case_domain: bool = False
'''
s = s.replace(anchor_flag, new_flag, 1)
sp.write_text(s, encoding="utf-8", newline="")
print("[A] settings.py：新增 allow_client_case_domain + __repr__ 打码")

# ── B. main.py：闸函数 + 改消费点 + 订正注释 ──
mp = BE / "main.py"
m = mp.read_text(encoding="utf-8")

old_doc = "    `case_domain` 的同款限制待 agent 路径启用时一并处理（当前 Agent Path 零流量）。"
new_doc = "    `case_domain` 的同款限制已于 2026-09-22 一并落地（见 `_client_case_domain`）。"
assert m.count(old_doc) == 1
m = m.replace(old_doc, new_doc, 1)

anchor_gate = """    if not settings.allow_client_law_as_of:
        return None
    return body.law_as_of
"""
assert m.count(anchor_gate) == 1
new_gate = anchor_gate + '''

def _client_case_domain(body) -> str | None:
    """客户端传入的 `case_domain`，经**评测通道闸**过滤（与 `_client_law_as_of` 同款）。

    定位：该值决定 R1-OB 判域（劳/民/商…），是**评测/灰度输入**，不是普通用户的偏好。
    `settings.allow_client_case_domain=False`（默认）⇒ 返回 None ⇒ 消费方落默认，
    行为与"客户端没传"完全一致（前端从不传该字段，生产默认路径零变化）。

    ⚠️ 本闸的消费点当前**只在 agent 启用分支内**（`if not settings.agent_enabled:` 之后）⇒
    本文件无端点级用例（harness 没有 agent 路由）；已有回归守卫保证"闸外不得存在直读"
    （`tests/test_client_case_domain_gate.py`）。
    """
    if not settings.allow_client_case_domain:
        return None
    return body.case_domain
'''
m = m.replace(anchor_gate, new_gate, 1)

old_call = "                    body.case_domain,\n"
assert m.count(old_call) == 1
m = m.replace(old_call, "                    _client_case_domain(body),\n", 1)
mp.write_text(m, encoding="utf-8", newline="")
print("[B] main.py：新增 _client_case_domain + 消费点改走闸 + 订正 law_as_of 注释")

# ── C. 证据文件里的明文密钥 → 打码（保留失败证据本身）──
ev = OUT / "evidence-cd-before.txt"
raw = ev.read_text(encoding="utf-8", errors="replace")
patterns = [
    (r"'sk-[A-Za-z0-9._\-]{10,}'", "'<masked>'"),
    (r"'178d[0-9a-f]{20,}[^']*'", "'<masked>'"),
    (r"'[A-Za-z0-9]{13}'", "'<masked>'"),  # 09-26 整改：原写法把管理口令的字面值写进 pattern，打码工具自己成了明文源 ⇒ 改按形状匹配（宁多打不漏打）。凭据是否已轮换由 Owner 掌握，本注释不作断言（此处原写"值已轮换，旧值失效"未经证实，2026-09-29 删）；状态见 docs/handoff-local-candidate-closeout-20260929.md §6② 第六条 4b/5 与台账 D25。
    (r"sk-[A-Za-z0-9._\-]{10,}", "<masked>"),
]
n = 0
for pat, rep in patterns:
    raw, k = re.subn(pat, rep, raw)
    n += k
ev.write_text(raw, encoding="utf-8", newline="")
print(f"[C] evidence-cd-before.txt 已打码 {n} 处密钥/密码")
