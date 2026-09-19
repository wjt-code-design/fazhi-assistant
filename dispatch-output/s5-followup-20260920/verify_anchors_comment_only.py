"""复证「锚点是纯注释」到底成不成立，以及成立的**准确口径**是什么。

起因：ADR-018 初稿写"剥掉标记后的文件与 HEAD 逐字节相同"，实测 `git show HEAD:backend/main.py`
是 **LF**（autocrlf 在检入时归一），而工作树文件是 **CRLF** ⇒ 那句在字节层为假。
本脚本给出可复核的两个数：工作树两侧字节比对、归一 EOL 后的字节比对。
"""

import re
import subprocess
from pathlib import Path

CUR = Path("backend/main.py").read_bytes()
# 锚点是在 fad2cee 加的 ⇒ 基线必须是**它的前一提交**，拿 HEAD 比是自我比对（恒等，无意义）。
HEAD = subprocess.run(
    ["git", "show", "fad2cee~1:backend/main.py"],
    capture_output=True,
    check=True,
).stdout

MARK = re.compile(rb"[ \t]*#[ \t]*gate-exit:[ \t]*E\d+[^\r\n]*")
STRIPPED = MARK.sub(b"", CUR)

print("cur_crlf", CUR.count(b"\r\n"), "cur_lf", CUR.count(b"\n"))
print("stripped_crlf", STRIPPED.count(b"\r\n"), "stripped_lf", STRIPPED.count(b"\n"))
print("head_bytes_lf_only", HEAD.count(b"\r\n") == 0, "head_lines", HEAD.count(b"\n"))
print("A) 剥标记 vs HEAD 原样字节        :", STRIPPED == HEAD)
print("B) 剥标记 vs HEAD 归一 EOL 后字节 :", STRIPPED.replace(b"\r\n", b"\n") == HEAD)
print("markers_found", len(re.findall(rb"gate-exit:", CUR)))
