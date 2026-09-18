"""绊线探针：证明 `over2_replay.py` 的三道校准门禁**真的会拦**，而不是永远放行。

审计脚本最容易犯的毛病是"无论数据怎样都说没问题"。这里用两处定向变异，各自必须被**指定的那道门**拦下：

M1  把现行谓词 `> CLARIFY_ROUND_LIMIT` 改成 `>= CLARIFY_ROUND_LIMIT`（判据放宽半格）
    ⇒ 期望 **FATAL(calibrate-a)**：合成真值表 45 条立刻对不上。
M2  把分档器里 `"漏标"` 这一档改成 `"一致"`（分类器哑火，漏标永不可达）
    ⇒ 期望 **FATAL(calibrate-c)**：五档可达性自检必须报警。
      若 M2 仍能出数，就说明"漏标 0 条"这个结论毫无证明力。

字节级备份 + sha256 自证还原（探针只改本目录的审计脚本，绝不碰 backend/）。
"""

import hashlib
import subprocess
import sys
from pathlib import Path

TARGET = Path(__file__).with_name("over2_replay.py")
REPO = Path(__file__).resolve().parents[2]
PY = REPO / "backend" / "venv" / "Scripts" / "python.exe"

MUTATIONS = [
    (
        "M1 现行谓词放宽半格",
        "    return (n + (1 if tail else 0)) > CLARIFY_ROUND_LIMIT",
        "    return (n + (1 if tail else 0)) >= CLARIFY_ROUND_LIMIT",
        "FATAL(calibrate-a)",
    ),
    (
        "M2 分档器漏标档哑火",
        '        return ("漏标" if preds["new_protocol"] else "反向差异"), matched',
        '        return "一致", matched',
        "FATAL(calibrate-c)",
    ),
]

raw0 = TARGET.read_bytes()
text0 = raw0.decode("utf-8")
sha0 = hashlib.sha256(raw0).hexdigest()
print(f"审计脚本基线 sha256 = {sha0}")

fails = 0
for name, old, new, want in MUTATIONS:
    if text0.count(old) != 1:
        print(f"  {name}: FATAL 锚点命中 {text0.count(old)} 次（期望 1），跳过")
        fails += 1
        continue
    TARGET.write_bytes(text0.replace(old, new, 1).encode("utf-8"))
    try:
        p = subprocess.run(
            [str(PY), str(TARGET)],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            check=False,
        )
        out = (p.stdout or "") + (p.stderr or "")
        hit = want in out
        ok = (p.returncode != 0) and hit
        print(
            f"  {name}: 退出码={p.returncode} 期望非0 | 报出 {want} = {hit} ⇒ {'拦住' if ok else '没拦住'}"
        )
        if not ok:
            fails += 1
            print(
                "    尾部输出：",
                out.strip().splitlines()[-2:] if out.strip() else "(空)",
            )
    finally:
        TARGET.write_bytes(raw0)
        sha_now = hashlib.sha256(TARGET.read_bytes()).hexdigest()
        print(f"    还原 sha256 = {sha_now} 一致={sha_now == sha0}")
        if sha_now != sha0:
            sys.exit("FATAL: 还原不一致，必须人工检查！")

# 变异全部还原后，再确认一次干净树能正常出数（防"还原成了坏版本"）
p = subprocess.run(
    [str(PY), str(TARGET)], capture_output=True, text=True, cwd=str(REPO), check=False
)
print(f"  还原后复跑：退出码={p.returncode}")
if p.returncode != 0:
    fails += 1
    print("    ", (p.stdout + p.stderr).strip().splitlines()[-3:])
print(f"\n绊线结论：{'全部拦住' if fails == 0 else f'{fails} 处没拦住 —— 门禁不可信'}")
sys.exit(0 if fails == 0 else 1)
