"""从**原始 junit xml** 独立重算变异审计结论，再和已入库的 mutation-report-full.json 对账。

为什么值得做：那份 json 是当时脚本顺手写的——用它自证 = 同源循环。这里改用 xml 重算，
若两边结论不一致，说明"ALL_KILLED"这句话的证据链在仪器层就有问题。
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

D = Path("dispatch-output/s5-followup-20260920")


def failed_ids(xml_path: Path) -> set[str]:
    out = set()
    for tc in ET.parse(xml_path).iter("testcase"):
        if tc.find("failure") is not None or tc.find("error") is not None:
            out.add(f"{tc.get('classname')}::{tc.get('name')}")
    return out


base = failed_ids(D / "full-baseline.xml")
print(f"baseline_failed={len(base)}  （票 G 复审口径应为 21）")

rep = json.loads((D / "mutation-report-full.json").read_text(encoding="utf-8"))
ok = len(base) == 21
for k, v in rep.items():
    if k == "_self_check":
        continue
    x = D / f"full-{k}.xml"
    if not x.exists():
        print(f"FAIL  {k}: 找不到 {x}")
        ok = False
        continue
    m = failed_ids(x)
    newly_red = sorted(m - base)
    newly_green = sorted(base - m)
    verdict = "KILLED" if newly_red else "SURVIVED"
    match = (
        verdict == v["status"]
        and len(m) == v["mutant_failed"]
        and sorted(v["newly_red"]) == newly_red
        and sorted(v.get("newly_green", [])) == newly_green
    )
    ok = ok and match
    print(
        f"{'PASS ' if match else 'FAIL '} {k}: xml 重算 failed={len(m)} newly_red={len(newly_red)} "
        f"{verdict} | json 记的 failed={v['mutant_failed']} {v['status']} | 一致={match}"
    )
    for t in newly_red:
        print("        newly_red:", t)

sc = rep.get("_self_check")
print("\n仪器自证（脚本自己的还原证明）:", json.dumps(sc, ensure_ascii=False)[:200])
print(f"\nALL_KILLED 独立复算成立 = {ok and all(v['status'] == 'KILLED' for k, v in rep.items() if k != '_self_check')}")
