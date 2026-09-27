"""票 T5 变异仪：在**副本树**上逐处断开接线，跑全量并与干净基线做 junit 集合差分。

为什么在副本树：本仓常设纪律（Owner 2026-09-20 裁决）—— live 工作树跑全量会污染隔离指纹、
让并行会话的门禁轮判 RUN_VOID；副本树内全量 = 允许。副本树只装 **git tracked** 文件，
所以 `.env` / `chroma_db` / `venv` 天然不在场（真实语料缺席时 `real_kb` 自己 skip）。

为什么还原不用 git：归属文件与邻居文件都带着其他助手**未提交**的改动，
`git checkout --` / `git restore` 会把它们一起抹掉 ⇒ 变异前把目标文件 `cp` 成 `.orig`，还原用那份。

三条硬约束写在代码里，不靠人记：
① 每处变异**只动一个 site** ⇒ 施加前断言锚点在该文件里出现恰好 1 次（无锚点的批量替换会连
   被测样本一起改掉，本仓据此误判过一次自己的断言空转）；
② 还原必须逐字回原样 ⇒ 比对 `.orig` 的 sha256，不符就停；
③ 分母只认 `--collect-only`（`passed+skipped` 会随失败自缩）。

跑法：cd backend && venv\\Scripts\\python.exe ..\\dispatch-output\\d-t5-import-types-20260927\\run_mutations.py
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
PY = BACKEND / "venv" / "Scripts" / "python.exe"
TREE = Path(os.environ["TEMP"]) / "d-mut-20260927"
TREE_SPECS = ("backend", "release-evidence", "dispatch-output/task1", "data")
OWNED = ("backend/scripts/import_laws.py", "backend/tests/test_import_laws_preflight.py")

# (标签, 相对副本树根的文件, 锚点原文, 变异后, 这一处要证明什么)
MUTATIONS = [
    (
        "M1",
        "backend/knowledge_service.py",
        "        if n and stale_ids:\n",
        "        if n and stale_ids and False:  # MUT-M1\n",
        "断开「写入成功后删旧」这一句本身",
    ),
    (
        "M2",
        "backend/scripts/import_laws.py",
        'metas[0].get("origin") == "seed"',
        'metas[0].get("origin") == "seed-MUT-M2"',
        "seed 判定永不命中：跳过路径整条失效",
    ),
    (
        "M2b",
        "backend/scripts/import_laws.py",
        'return bool(metas) and metas[0].get("origin") == "seed"',
        "return True  # MUT-M2b",
        "seed 判定恒命中：证明 upload 对照腿不是空枪",
    ),
    (
        "M2c",
        "backend/scripts/import_laws.py",
        'print(f"  跳过（与种子冲突，请改 laws.json 后重建）：{title} {article}")',
        'print("  跳过（与种子冲突，请改 laws.json 后重建）")  # MUT-M2c',
        "跳过了但不点名：让「点名」二字独占一条会红的断言",
    ),
    (
        "M3",
        "backend/scripts/import_laws.py",
        'origin="import", extra_meta=extra)',
        'origin="import", extra_meta=None)  # MUT-M3',
        "脚本不把算好的版本元数据交给写入器：断在脚本→写入器的参数上",
    ),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def build_tree() -> None:
    """副本树 = 工作树里 tracked 文件的当前内容（含各助手未提交的改动）。"""
    listed = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", *TREE_SPECS],
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    if TREE.exists():
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(TREE)], check=False)
    TREE.mkdir(parents=True, exist_ok=True)
    n = 0
    for raw in listed:
        rel = raw.decode("utf-8")
        if not rel:
            continue
        src, dst = REPO / rel, TREE / rel
        if not src.is_file():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    print(f"副本树建好：{n} 个文件 → {TREE}", flush=True)


def sync_pristine() -> None:
    """把变异目标文件恢复到交付态：归属文件从 live 重取并刷新 `.orig`，邻居文件从 `.orig` 还原。"""
    for rel in OWNED:
        src, dst = REPO / rel, TREE / rel
        shutil.copyfile(src, dst)
        shutil.copyfile(dst, Path(str(dst) + ".orig"))
    for tag, rel, *_ in MUTATIONS:
        target = TREE / rel
        orig = Path(str(target) + ".orig")
        if rel not in OWNED:
            if not orig.exists():
                shutil.copyfile(target, orig)
            else:
                shutil.copyfile(orig, target)


def run_pytest(xml_name: str) -> tuple[int, str]:
    xml, log = TREE / xml_name, TREE / xml_name.replace(".xml", ".log")
    with open(log, "w", encoding="utf-8") as fh:
        rc = subprocess.call(
            [str(PY), "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}"],
            cwd=TREE / "backend",
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    summary = next((ln for ln in reversed(lines) if "passed" in ln or "error" in ln), "(无汇总行)")
    return rc, summary


def failures(xml_path: Path) -> dict[str, str]:
    root = ET.parse(xml_path).getroot()
    suite = root if root.tag == "testsuite" else root[0]
    out: dict[str, str] = {}
    for tc in suite.iter("testcase"):
        for kind in ("failure", "error"):
            node = tc.find(kind)
            if node is not None:
                key = f"{tc.get('classname')}::{tc.get('name')}"
                out[key] = (node.get("message") or "").replace("\n", " ")[:220]
    return out


def collect_count() -> int:
    res = subprocess.run(
        [str(PY), "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only"],
        cwd=TREE / "backend",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    line = next((ln for ln in res.stdout.splitlines() if "tests collected" in ln), "")
    words = line.split()
    return int(words[0]) if words and words[0].isdigit() else -1


def locate(rel: str, anchor: str) -> tuple[str, int, int]:
    """返回 (原文, 锚点出现次数, 锚点所在行)。带 \\n 的锚点要用 keepends 才数得到行号。"""
    with open(TREE / rel, encoding="utf-8", newline="") as fh:
        text = fh.read()
    hits = text.count(anchor)
    line_no = next(
        (i for i, ln in enumerate(text.splitlines(keepends=True), 1) if anchor in ln),
        -1,
    )
    return text, hits, line_no


def main() -> int:
    if not PY.exists():
        print(f"venv python 不在：{PY}", file=sys.stderr)
        return 2
    if not (TREE / "backend" / "tests").is_dir():
        build_tree()
    sync_pristine()

    # 锚点预检放在全量之前：一处对不上的锚点不该等 3 分钟才暴露（本仪表已为此烧过两轮）
    bad: list[str] = []
    for tag, rel, anchor, _mut, _claim in MUTATIONS:
        _t, hits, line_no = locate(rel, anchor)
        print(f"预检 {tag}: {rel} 锚点 {hits} 次 / 行 {line_no}", flush=True)
        if hits != 1 or line_no < 0:
            bad.append(tag)
    if bad:
        print(f"‼️ 锚点不合格：{bad} —— 一处不动，先修仪表", file=sys.stderr)
        return 3

    drift = ""
    ks_live, ks_tree = REPO / "backend" / "knowledge_service.py", TREE / "backend" / "knowledge_service.py"
    if sha256(ks_live) != sha256(ks_tree):
        drift = f" ‼️ 邻居文件 knowledge_service.py 在快照后又变了（live={sha256(ks_live)}）"
    denom = collect_count()
    rc, summary = run_pytest("clean.xml")
    base = failures(TREE / "clean.xml")
    head = [
        f"分母（--collect-only 单取）= {denom}",
        f"干净基线：rc={rc}  {summary}  失败集 = {len(base)} 条{drift}",
        "交付文件 sha256：" + "、".join(f"{Path(r).name}={sha256(REPO / r)}" for r in OWNED),
        "",
    ]
    print("\n".join(head), flush=True)
    lines = list(head)

    for tag, rel, anchor, mut, claim in MUTATIONS:
        sync_pristine()
        target = TREE / rel
        text, hits, line_no = locate(rel, anchor)
        if hits != 1:
            block = f"### {tag}: 放弃 —— 锚点在 {rel} 里出现 {hits} 次（必须恰好 1 次）\n"
            lines.append(block)
            print(block, flush=True)
            continue
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(text.replace(anchor, mut))
        rc, summary = run_pytest(f"{tag}.xml")
        after = failures(TREE / f"{tag}.xml")
        killed = sorted(set(after) - set(base))
        gone = sorted(set(base) - set(after))
        sync_pristine()
        ok_restore = sha256(target) == sha256(Path(str(target) + ".orig"))
        block = [
            f"### {tag}（{rel}:{line_no}）— {claim}",
            f"  rc={rc}  {summary}",
            f"  还原后逐字一致={ok_restore}",
            f"  新增红 {len(killed)} 条 / 基线红消失 {len(gone)} 条 {gone}",
        ]
        for key in killed:
            block.append(f"    [红] {key}\n         {after[key]}")
        if not killed:
            block.append("    ⚠️ 零新增红 —— 这条接线在本仓所有测试里没有守卫（变异存活）")
        text_block = "\n".join(block) + "\n"
        lines.append(text_block)
        print(text_block, flush=True)
        if not ok_restore:
            lines.append(f"‼️ {tag} 还原后哈希不符，停在这里\n")
            print(lines[-1], flush=True)
            break

    out = Path(__file__).with_name("mutation-readings.txt")
    out.write_text("\n".join(lines), encoding="utf-8")
    sync_pristine()
    print(f"读数控成 → {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
