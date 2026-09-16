"""T7 交接前核验：冻结物与关键文件哈希 vs T0 manifest 期望值。只读，不改任何东西。"""
import hashlib
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
REL = "release-evidence/legal-agent-v1-complex-v1-20260907"

# (路径, manifest 期望值前16位, 说明)
CHECKS = [
    # 冻结代码
    ("backend/agent/verifier.py", "47b37a0a421eaa2c", "冻结：判定逻辑"),
    ("backend/agent/chat_integration.py", "f05c43c33b7d1e53", "冻结：equality guard/CAS/ownership"),
    ("backend/agent/state_machine.py", "9de7c35f3543e749", "冻结"),
    ("backend/agent/repository.py", "57c1c00dc00df76c", "冻结：compare_and_save"),
    ("backend/prompts.py", "65c5211c81109830", "冻结：系统提示词常量"),
    ("backend/scripts/gate5_judge.py", "90487960771dd372", "冻结判分器 F2"),
    # 本轮/上一轮已改动（期望变化）
    ("backend/agent/writer.py", "e0bc200ab3befd66", "→ 已改（谓词抽取，用户确认）"),
    ("backend/agent/service.py", "7588a65a80cb553f", "→ 已改（T2/T3）"),
    ("backend/agent/runtime.py", "c73cefe93ad0fbd4", "→ 已改（T4）"),
    ("backend/agent/controller.py", "3b2bf12f61162f19", "→ 已改（V2-G1/G2 + C01 修复）"),
    # 冻结产物
    (f"{REL}/frozen-cases-v1.json", "be281ab275024b2c", "冻结题集 C01-C10"),
    (f"{REL}/frozen-fact-ids-v1.json", "262456b6fd06d2fb", "冻结事实ID"),
    (f"{REL}/frozen-round-protocol-v1.json", "89d8d9167262ae83", "冻结轮次协议"),
    (f"{REL}/gate2-run-gate5-dev-run-9-sessions.json", "08181f2e6e17a6c2", "历史 run-9 基线"),
    (f"{REL}/gate2-run-gate5-dev-run-10-sessions.json", "e11c104bacf8bb82", "历史 run-10 基线"),
    (f"{REL}/gate2-run-gate5-dev-run-11-sessions.json", "bd56d3e18bad627c", "历史 run-11 基线"),
    ("dispatch-output/task1/hidden-cases-v1.json", "d1f0b1f053b2f4b3", "hidden 题集"),
    ("dispatch-output/task1/hidden-round-protocol-v1.json", "e4de149b4bf9eccf", "hidden 协议"),
    ("dispatch-output/task1/hidden-commitment.json", "1ae1488c9e693b0e", "hidden 承诺"),
    ("dispatch-output/task1/salt.txt", "51157d68a830b3d5", "salt"),
]

print(f"{'文件':<62} {'当前':<18} {'期望':<18} 判定")
print("-" * 120)
same = changed = missing = 0
for rel, expected, note in CHECKS:
    p = ROOT / rel
    if not p.exists():
        print(f"{rel:<62} {'(缺失)':<18} {expected:<18} ❌ 文件不存在  [{note}]")
        missing += 1
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    if h == expected:
        verdict = "✅ 一致（冻结被遵守）"
        same += 1
    else:
        verdict = "⚠️ 已变化（需人工确认是否授权改动）"
        changed += 1
    print(f"{rel:<62} {h:<18} {expected:<18} {verdict}  [{note}]")

print("-" * 120)
print(f"一致={same}  变化={changed}  缺失={missing}")
