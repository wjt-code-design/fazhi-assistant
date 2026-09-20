"""归因副本树基线里的红：把 junit xml 的 failure 按"消息首行"聚类，给出用例名与条数。

为什么先做这件事：票 C 的变异结论建立在"基线 tests=1396 failures=19"上，
而"19 条红"如果来自**仪器环境**（副本缺 .env / 缺 task1 / 缺 chroma），那整轮变异要在修好的仪器上重跑；
如果来自**builder 自己的改动**，那 19 条就是它没做完的活。两种处置完全不同，先看数再看代码。
"""

from __future__ import annotations

import pathlib
import sys
import xml.etree.ElementTree as ET

path = pathlib.Path(sys.argv[1])
root = ET.parse(path).getroot()
cases = root.iter("testcase")
groups: dict[str, list[str]] = {}
for tc in cases:
    name = f"{tc.get('classname')}::{tc.get('name')}"
    for tag in ("failure", "error"):
        for f in tc.findall(tag):
            msg = (f.get("message") or (f.text or "")).strip().splitlines()
            first = msg[0][:150] if msg else "<无消息>"
            groups.setdefault(f"{tag} | {first}", []).append(name)
total = sum(len(v) for v in groups.values())
print(f"文件={path.name} 红条数={total}")
for k, v in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    print(f"\n[{len(v)}] {k}")
    for n in v[:6]:
        print("   -", n)
    if len(v) > 6:
        print(f"   ... 另 {len(v) - 6} 条")
