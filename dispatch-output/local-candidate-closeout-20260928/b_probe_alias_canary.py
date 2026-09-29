"""别名canary：在打桩之前就 `from X import y` 把原函数引用绑走，用来验证 sweep_aliases 是否真能补上。

这个模块本身就是「猴子补丁盲区」的最小复现。b_runtime_probe 的 selfcheck 会：
  1) 先 import 本模块（此时绑走的是原函数）；
  2) 装桩并做一次 sweep；
  3) 调 call_via_alias() 两次，中间强制再 sweep 一次；
  4) 断言第一次不计数（盲区真实存在）、第二次计数（sweep 有牙）。
"""

from __future__ import annotations

from langchain_core.load import loads as aliased_loads  # noqa: F401 - 故意在打桩前绑走原引用


def call_via_alias() -> object:
    return aliased_loads('{"_probe": "not-a-lc-doc"}')
