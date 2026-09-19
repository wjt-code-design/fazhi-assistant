"""复证「锚点是纯注释」，并且把口径钉在**两个 blob** 上，不依赖工作树当下状态。

两版都错过：
- 初版写"与 HEAD 逐字节相同" ⇒ ①autocrlf 下 blob 是 LF、工作树是 CRLF，"逐字节"根本不成立；
  ②锚点本身就是 fad2cee 加的，拿 HEAD 比是自我比对（恒等，无意义）。
- 二版改成"剥标记后的**工作树文件** vs fad2cee~1" ⇒ 仍然会烂：本会话后来动了 main.py 的
  docstring（合法改动，与锚点无关），这句话当场变假。**"锚点没改代码"是关于那一笔提交的性质，
  不是关于当下工作树的性质** ⇒ 两边都必须按 commit 取。
"""

import re
import subprocess

MARK = re.compile(rb"[ \t]*#[ \t]*gate-exit:[ \t]*E\d+[^\r\n]*")


def blob(ref: str) -> bytes:
    return subprocess.run(["git", "show", ref], capture_output=True, check=True).stdout


with_m = blob("fad2cee:backend/main.py")  # 加完锚点那一笔
base = blob("fad2cee~1:backend/main.py")  # 它的前一版

CR, LF = b"\r", b"\n"  # 先命名：f-string 的表达式里不许放反斜杠（Py3.11）
print(
    f"blob 存 LF（autocrlf 归一）：with_m CR={with_m.count(CR)} base CR={base.count(CR)}"
)
print(
    "A) 原样字节（不剥标记）      :", with_m == base, "← 必然 False，标记就是差异本身"
)
print(
    "B) 剥标记 vs 前一版（同 LF） :",
    MARK.sub(b"", with_m) == base,
    "← 这句才是「锚点纯注释」的成立口径",
)
print(
    "   两边行数                  :",
    with_m.count(b"\n"),
    "vs",
    base.count(b"\n"),
    "← 相等 ⇒ 一条代码行都没多",
)
print("markers_found", len(re.findall(rb"gate-exit:", with_m)))
