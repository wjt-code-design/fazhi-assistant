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
③ 分母只认 `--collect-only`（`passed+skipped` 会随失败自缩）；
④ **基线必须真跑过才继续**：收集期报错会**中断整会话**，junit 里只剩 1 条"收集错误"伪用例
   （实测 collect-only=1663 / junit 用例数=1），此后每条变异都会算出"零新增红" ⇒ 假绿。
   判据取 **junit 用例数 < collect-only 数**（写成"==0"会漏网，本机实测踩过）。本仪表 2026-09-27
   踩过一次（副本树缺**未入库**的收集期依赖），故把"真跑过"做成闸，而不是靠人看汇总行。
⑤ 副本树必须**自足**：本仪表靠**基线闸**（④）兑现这件事——树若不自足，`--collect-only` 就报错、
   junit 用例数会掉到 1，基线闸直接退出 3，不会把退化读数写进库。2026-09-27 之前
   `hidden_runner.py` 在**模块级**读两个**未入库**的 JSON（`.gitignore:77` 忽略 `dispatch-output/task1/`），
   故 `build_tree()` 当时**硬要求**补拷那两个 JSON；**2026-09-28 上游票已把它们改成运行期读取**、
   `tests/test_harness_fact_reveal.py` 也改成自带脱敏夹具 ⇒ 补拷**已非必需**（本次实测：不补拷的树
   collect-only 与全量都跑得完）。仍保留为**尽力而为**（有就拷、没有不报错）：运行期的
   `load_cases()` / `load_protocol()` 仍读这两个真值文件，将来任何真去调它们的用例在副本树里仍需在场。
⑥ 驱动只重生成**机器读数**；`## 附…` 那些手写分析**原样保留**（早期版本重跑会把附录吃掉）。
⑦ 写回在库读数必须落 **LF**：本仓 `.gitattributes` 是 `* text=auto eol=lf`，而 Windows 上
   `Path.write_text` 默认 `newline=None` 会把 `\n` 翻成 CRLF ⇒ 工作树留下 CRLF 文件，index 归一后
   `git status` 永远显示 ` M`（本文件 2026-09-27 实测 111 行全 CRLF）。故一律 `open(..., newline="")`。
⑧ **每只变异都要验该次运行完整**（2026-09-28 加）：该次运行的 **junit 用例数 ≥ 基线 junit 用例数**，
   否则判 **"实验无效"**：不计入 KILLED、不计入存活，且驱动**非零退出**。理由：变异一旦让收集期
   报错，pytest 就中断整会话（junit 只剩 1 条伪用例）而 `rc != 0` ⇒ 旧版会把它记成 **KILLED（假杀）**。
⑨ **退出码语义**（2026-09-28 加）：存活变异 > 0 ⇒ 非零；任一"实验无效"/"还原失败"/锚点不合格 ⇒ 非零；
   只有「全部杀死 + 零存活 + 零无效 + 还原逐字通过」才 0。
⑩ `--selftest <正路|collect-fail|survived|restore-fail|all>`：**负向自证**——受控注入三种失效形状，
   证明 ⑧⑨ 两条闸真的会拦。自证用独立副本树 + 缩小选择集（只跑 `test_import_laws_preflight.py`），
   走的是与外层**完全相同**的判据与退出码聚合代码，且**绝不写库内读数**。
⑪ **本轮固定一个快照**（2026-09-28 加，见 `sync_pristine` 与 `snapshot_drift`）：目标文件在建树时存 `.orig`，
   每只变异都从 `.orig` 还原、**不回读 live** ⇒ 并发会话中途改归属文件不会把基线腿与变异腿拼成两个版本。
   `--selftest drift` 用"改副本树再还原"证明这条闸**能红也能放**，不跑 pytest。

跑法：cd backend && venv\\Scripts\\python.exe ..\\dispatch-output\\d-t5-import-types-20260927\\run_mutations.py
自证：同上，末尾加 `--selftest collect-fail`（或 survived / restore-fail / positive / all）
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
# 根文件 CONTRIBUTING.md 必须进树：`test_smoke_citation_assertions::test_gate_item_counts_match_contributing`
# 读的是**仓库根**那份，缺了它就是一条与产品无关的环境假红（2026-09-28 补；B 侧的驱动早已带它）。
TREE_SPECS = ("backend", "release-evidence", "dispatch-output/task1", "data", "CONTRIBUTING.md")
OWNED = ("backend/scripts/import_laws.py", "backend/tests/test_import_laws_preflight.py")
READINGS = Path(__file__).resolve().with_name("mutation-readings.txt")
# 未入库的收集期依赖（历史必需、现为**尽力而为**）：见模块 docstring ⑤。
UNTRACKED_FIXTURES = (
    "dispatch-output/task1/hidden-cases-v1.json",
    "dispatch-output/task1/hidden-round-protocol-v1.json",
)

# 自证用选择集：只跑归属文件，够快，且判据/退出码聚合代码与全量跑**逐字相同**。
SELFTEST_SELECTION = ["tests/test_import_laws_preflight.py"]
# 受控"收集期失败"注入：往副本树 tests/ 里放一个语法错模块 ⇒ pytest 收集期中断，
# junit 里只剩 1 条"收集错误"伪用例（正是 ⑧ 要拦的形状）。只落在副本树，finally 里删除。
COLLECT_FAULT_SRC = "def test_zz_mut_fault(:\n    pass\n"
RESTORE_FAULT_SUFFIX = "\n# MUT-SELFTEST：还原后再改一次，验「还原失败」闸（自证用，只落在副本树）\n"

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

# 行为零变化的中性改动（自证"存活 ⇒ 非零退出"用）：任何测试都**不该**因此变红。
NEUTRAL_MUTATION = (
    "S-survived",
    "backend/scripts/import_laws.py",
    "import argparse",
    "import argparse  # MUT-SELFTEST-NEUTRAL（注释级中性改动，行为零变化）",
    "自证用：行为零变化 ⇒ 必然存活 ⇒ 退出码必须非零",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def build_tree(tree: Path, topup: bool = True) -> None:
    """副本树 = 工作树里 tracked 文件的当前内容（含各助手未提交的改动）。

    `topup`：未入库夹具是**尽力而为**补拷（见 docstring ⑤）。缺失**不再**报错——
    树是否自足由基线闸（④）在真跑时判定，而不是靠建树期的硬断言。
    """
    listed = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", *TREE_SPECS],
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    if tree.exists():
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(tree)], check=False)
    tree.mkdir(parents=True, exist_ok=True)
    n = 0
    for raw in listed:
        rel = raw.decode("utf-8")
        if not rel:
            continue
        src, dst = REPO / rel, tree / rel
        if not src.is_file():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    topup_n, topup_missing = 0, []
    if topup:
        for rel in UNTRACKED_FIXTURES:
            src, dst = REPO / rel, tree / rel
            if not src.is_file():
                topup_missing.append(rel)
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            topup_n += 1
    else:
        topup_missing = list(UNTRACKED_FIXTURES)
    print(
        f"副本树建好：{n} 个文件（未入库夹具尽力补拷 {topup_n} 个"
        f"；缺失 {len(topup_missing)} 个 = {topup_missing}）→ {tree}",
        flush=True,
    )


def sync_pristine(tree: Path) -> None:
    """把变异目标恢复到**本轮快照**：每个目标文件在第一次进入时存 `.orig`，此后一律从 `.orig` 还原。

    2026-09-28（E 验收补的硬闸）：归属文件原先是**每只变异前从 live 重取**——那等于把"本轮固定快照"
    做成只有邻居文件固定，并发会话若在跑动中途改 `import_laws.py`，基线腿与变异腿就拼成两个版本，
    而读数里只有建树时刻的 sha，事后看不出来。现在 OWNED 与邻居走同一条 `.orig` 语义：
    树由 `build_tree()` 从 live 建好 ⇒ `.orig` = 建树时刻 = 本轮唯一快照；live 后续怎么变都不进本轮。
    live 与快照的差异改由 `snapshot_drift()` 显式记录，不再靠人眼看。
    """
    for tag, rel, *_ in [("", r) for r in OWNED] + [*MUTATIONS, NEUTRAL_MUTATION]:
        target = tree / rel
        orig = Path(str(target) + ".orig")
        if not orig.exists():
            shutil.copyfile(target, orig)
        else:
            shutil.copyfile(orig, target)


def snapshot_drift(tree: Path) -> list[str]:
    """本轮快照与活动工作树的差异（只报，不改任何东西）。非空 ⇒ 读数对应建树时刻，不对应当前工作树。"""
    out = []
    for rel in sorted({*OWNED, *[m[1] for m in MUTATIONS], NEUTRAL_MUTATION[1]}, key=str):
        live, snap = REPO / rel, tree / rel
        if not live.is_file() or not snap.is_file():
            continue
        if sha256(live) != sha256(snap):
            out.append(f"{rel}（快照={sha256(snap)}、当前工作树={sha256(live)}）")
    return out


def run_pytest(tree: Path, xml_name: str, selection: list[str]) -> tuple[int, str]:
    """跑一次 pytest：副本树内、禁用 cache、落 junit。`selection` 空 = 全量。"""
    xml, log = tree / xml_name, tree / xml_name.replace(".xml", ".log")
    with open(log, "w", encoding="utf-8") as fh:
        rc = subprocess.call(
            [str(PY), "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", *selection],
            cwd=tree / "backend",
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


def testcase_count(xml_path: Path) -> int:
    """junit 里的用例数：收集期报错时**只剩 1 条**"收集错误"伪用例（本机实测），是判"这次运行完不完整"的读数。"""
    root = ET.parse(xml_path).getroot()
    suite = root if root.tag == "testsuite" else root[0]
    return sum(1 for _ in suite.iter("testcase"))


def write_readings(lines: list[str]) -> None:
    """只重写机器读数，**保留**文件里人工写的 `## 附…` 段（早期版本重跑会把附录吃掉）。"""
    out = READINGS
    kept = ""
    if out.exists():
        text = out.read_text(encoding="utf-8", errors="replace")
        idx = text.find("\n## 附")
        kept = text[idx + 1 :].rstrip("\n") if idx >= 0 else ""
    body = "\n".join(lines) + "\n"
    if kept:
        body += "\n" + kept + "\n"
    # `newline=""` 不可省：本仓 `.gitattributes` 是 `* text=auto eol=lf`，而 Windows 上
    # `Path.write_text` 默认 `newline=None` 会把 `\n` 翻成 CRLF ⇒ 落一个 CRLF 工作树文件，
    # index 归一后 `git status` 永远显示 ` M`（本文件 2026-09-27 实测 111 行全 CRLF）。
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write(body)


def collect_count(tree: Path, selection: list[str]) -> tuple[int, int]:
    """`--collect-only` 单取分母；同时返回 rc —— 收集期报错时 rc != 0，本身就该让实验停。"""
    res = subprocess.run(
        [str(PY), "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only", *selection],
        cwd=tree / "backend",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    line = next((ln for ln in res.stdout.splitlines() if "tests collected" in ln), "")
    words = line.split()
    denom = int(words[0]) if words and words[0].isdigit() else -1
    return denom, res.returncode


def locate(tree: Path, rel: str, anchor: str) -> tuple[str, int, int]:
    """返回 (原文, 锚点出现次数, 锚点所在行)。带 \\n 的锚点要用 keepends 才数得到行号。"""
    with open(tree / rel, encoding="utf-8", newline="") as fh:
        text = fh.read()
    hits = text.count(anchor)
    line_no = next(
        (i for i, ln in enumerate(text.splitlines(keepends=True), 1) if anchor in ln),
        -1,
    )
    return text, hits, line_no


def apply_collect_fault(tree: Path, tag: str) -> list[str]:
    """受控注入"收集期失败"：放一个语法错模块进副本树 tests/ ⇒ 会话在收集期中断。

    返回这次 pytest 需要追加的选择参数（否则 pytest 只收集显式给的路径，看不见注入模块）。
    """
    broken = tree / "backend" / "tests" / f"test_zz_mut_fault_{tag.lower()}.py"
    with open(broken, "w", encoding="utf-8", newline="") as fh:
        fh.write(COLLECT_FAULT_SRC)
    return [f"tests/{broken.name}"]


def run_pipeline(
    tree: Path,
    mutations,
    selection: list[str],
    *,
    topup: bool = True,
    faults: dict[str, str] | None = None,
) -> tuple[int, list[str], dict]:
    """建树 → 基线闸 → 逐只变异（⑧ 运行完整性 + ② 还原校验）→ ⑨ 聚合退出码。

    返回 (退出码, 读数行, 统计)。**不写读数**：由调用方按 `stats["baseline_ok"]` 决定写不写。
    """
    faults = faults or {}
    stats = {
        "baseline_ok": False,
        "denom": -1,
        "ran": -1,
        "killed": 0,
        "survived": 0,
        "invalid": 0,
        "restore_failed": 0,
        "verdicts": [],
    }
    if not PY.exists():
        print(f"venv python 不在：{PY}", file=sys.stderr)
        return 3, [], stats
    build_tree(tree, topup=topup)
    sync_pristine(tree)

    # 锚点预检放在全量之前：一处对不上的锚点不该等 3 分钟才暴露（本仪表已为此烧过两轮）
    bad: list[str] = []
    for tag, rel, anchor, _mut, _claim in mutations:
        _t, hits, line_no = locate(tree, rel, anchor)
        print(f"预检 {tag}: {rel} 锚点 {hits} 次 / 行 {line_no}", flush=True)
        if hits != 1 or line_no < 0:
            bad.append(tag)
    if bad:
        print(f"‼️ 锚点不合格：{bad} —— 一处不动，先修仪表", file=sys.stderr)
        stats["invalid"] += len(bad)
        return 3, [], stats

    drift = ""
    drift_at_base = snapshot_drift(tree)
    if drift_at_base:
        drift = " ‼️ 建树后目标文件又被改过 ⇒ 本读数固定在建树时刻的快照：" + "；".join(drift_at_base)
    denom, denom_rc = collect_count(tree, selection)
    rc, summary = run_pytest(tree, "clean.xml", selection)
    base = failures(tree / "clean.xml")
    ran = testcase_count(tree / "clean.xml")
    if denom <= 0 or denom_rc != 0 or ran < denom:
        # 基线闸：收集期报错时 pytest **中断整会话**，junit 里只剩那 1 条"收集错误"伪用例
        # （本机实测：collect-only=1663，junit 用例数=1）⇒ 此后每条变异都算出"零新增红"、全报存活，
        # 或者反过来把中断读成 KILLED。判据是 **junit 用例数 < collect-only 数**，不是"等于 0"。
        # 此处**不写读数**：宁可让在库读数停在一次有效运行，也别覆盖成退化读数。
        print(
            f"‼️ 基线没真跑过（collect=-only {denom} / rc={denom_rc}，junit 用例数={ran}）"
            "⇒ 变异实验无意义，直接退出。",
            file=sys.stderr,
        )
        return 3, [], stats
    stats["baseline_ok"] = True
    stats["denom"] = denom
    stats["ran"] = ran
    head = [
        f"分母（--collect-only 单取）= {denom}",
        f"干净基线：rc={rc}  {summary}  失败集 = {len(base)} 条 / junit 用例数 = {ran}{drift}",
        "本轮快照 sha256（副本树，建树即定、本轮不再回读 live）："
        + "、".join(f"{Path(r).name}={sha256(tree / r)}" for r in OWNED),
        "",
        f"### 基线红清单（机器生成，逐条列全；共 {len(base)} 条）",
        '每条变异的"新增红" = 该次运行的红集 − 这份名单（不要用人工附录里的旧名单对账）',
    ]
    head += [f"- {key}" for key in sorted(base)]
    head.append("")
    lines = list(head)

    for tag, rel, anchor, mut, claim in mutations:
        sync_pristine(tree)
        target = tree / rel
        text, hits, line_no = locate(tree, rel, anchor)
        fault = faults.get(tag, "")
        extra: list[str] = []
        if hits != 1:
            stats["invalid"] += 1
            stats["verdicts"].append((tag, "实验无效"))
            block = (
                f"### {tag}: 实验无效 —— 锚点在 {rel} 里出现 {hits} 次（必须恰好 1 次），未施加变异\n"
            )
            lines.append(block)
            print(block, flush=True)
            continue
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(text.replace(anchor, mut))
        if fault == "break-collect":
            extra = apply_collect_fault(tree, tag)
        try:
            rc, summary = run_pytest(tree, f"{tag}.xml", [*selection, *extra])
            after = failures(tree / f"{tag}.xml")
            ran_m = testcase_count(tree / f"{tag}.xml")
        finally:
            if fault == "break-collect":
                (tree / "backend" / "tests" / f"test_zz_mut_fault_{tag.lower()}.py").unlink(missing_ok=True)
        killed = sorted(set(after) - set(base))
        gone = sorted(set(base) - set(after))
        sync_pristine(tree)
        if fault == "break-restore":
            with open(target, "a", encoding="utf-8", newline="") as fh:
                fh.write(RESTORE_FAULT_SUFFIX)
        ok_restore = sha256(target) == sha256(Path(str(target) + ".orig"))
        complete = ran_m >= ran  # ⑧ 运行完整性：本次运行不得比基线"少用例"
        if not ok_restore:
            stats["restore_failed"] += 1
            stats["invalid"] += 1
            verdict = "还原失败"
        elif not complete:
            stats["invalid"] += 1
            verdict = "实验无效"
        elif killed:
            stats["killed"] += 1
            verdict = "KILLED"
        else:
            stats["survived"] += 1
            verdict = "SURVIVED"
        stats["verdicts"].append((tag, verdict))
        block = [
            f"### {tag}（{rel}:{line_no}）— {claim}",
            f"  判定={verdict}  rc={rc}  {summary}",
            f"  运行完整性：本次 junit 用例数={ran_m} / 基线={ran} ⇒ {'通过' if complete else '无效（收集期报错/会话被中断）'}",
            f"  还原后逐字一致={ok_restore}",
            f"  新增红 {len(killed)} 条 / 基线红消失 {len(gone)} 条 {gone}",
        ]
        if verdict == "实验无效":
            block.append("    [!] 该次运行不完整 ⇒ **不计入 KILLED**、不计入存活，且驱动非零退出")
            block.append(
                "    [!] 本次红集仅作记录、不作证据：" + (f"{len(killed)} 条" if killed else "—")
            )
        elif verdict == "KILLED":
            for key in killed:
                block.append(f"    [红] {key}\n         {after[key]}")
        elif verdict == "SURVIVED":
            block.append("    ⚠️ 零新增红 —— 这条接线在本仓所有测试里没有守卫（变异存活）")
        else:
            block.append("    [!!] 还原校验未过 ⇒ 该次结果不作任何证据（不记 KILLED）")
        text_block = "\n".join(block) + "\n"
        lines.append(text_block)
        print(text_block, flush=True)
        if not ok_restore:
            lines.append(f"‼️ {tag} 还原后哈希不符 ⇒ 停在这里（后续变异不再执行）\n")
            print(lines[-1], flush=True)
            break

    drift_at_end = snapshot_drift(tree)
    if drift_at_end:
        lines.append(
            "‼️ 跑完后活动工作树与本轮快照已不一致（下面这轮读数仍只对应建树时刻）：" + "；".join(drift_at_end)
        )
        lines.append("")
    lines.append(
        f"== 汇总：KILLED {stats['killed']} / SURVIVED {stats['survived']}"
        f" / 实验无效 {stats['invalid']}（其中还原失败 {stats['restore_failed']}）/ 共 {len(mutations)} 只 =="
    )
    ok = stats["survived"] == 0 and stats["invalid"] == 0
    code = 0 if ok else 1
    lines.append(
        f"== 退出码判据：存活={stats['survived']} 无效={stats['invalid']}"
        f"（还原失败={stats['restore_failed']}）⇒ rc={code} =="
    )
    print("\n".join(lines[-2:]), flush=True)
    sync_pristine(tree)
    return code, lines, stats


def run_drift_selftest() -> int:
    """⑪ 的负向自证：`snapshot_drift` 必须**能红**（副本树被改）也**能放**（还原后），全程不跑 pytest、不碰 live。"""
    tree = Path(os.environ["TEMP"]) / "d-mut-selftest-drift"
    build_tree(tree)
    sync_pristine(tree)
    probe = [OWNED[0], MUTATIONS[0][1]]  # 一个归属文件 + 一个邻居文件（邻居原先只有注记、没有闸）
    rc = 0
    empty_at_build = snapshot_drift(tree)
    print(f"[drift] 建树即快照：drift={empty_at_build} ⇒ 期望 []（副本树 == live）", flush=True)
    if empty_at_build:
        print("[drift] FAIL 建树后就有差异 ⇒ 快照本身不可信", flush=True)
        rc = 1
    for rel in probe:
        target = tree / rel
        before = target.read_bytes()
        with open(target, "ab") as fh:
            fh.write("\n# MUT-SELFTEST-DRIFT（只落副本树）\n".encode())
        got = [d for d in snapshot_drift(tree) if d.startswith(rel)]
        print(f"[drift] 改副本树 {rel}: drift 报出={bool(got)} ⇒ 期望 True", flush=True)
        if not got:
            rc = 1
        with open(target, "wb") as fh:
            fh.write(before)
    after_restore = snapshot_drift(tree)
    print(f"[drift] 还原后：drift={after_restore} ⇒ 期望 []", flush=True)
    if after_restore:
        rc = 1
    print(f"[自证] drift ⇒ {'PASS' if rc == 0 else 'FAIL'}（rc={rc}）", flush=True)
    return rc


def run_selftest(name: str) -> int:
    """⑩ 负向自证：受控注入三种失效形状 + 一条正路，证明 ⑧⑨ 两条闸会拦。**不写库内读数**。"""
    m2 = next(m for m in MUTATIONS if m[0] == "M2")
    cases = {
        "positive": ([m2], {}, "KILLED", 0),
        "collect-fail": ([m2], {"M2": "break-collect"}, "实验无效", 1),
        "survived": ([NEUTRAL_MUTATION], {}, "SURVIVED", 1),
        "restore-fail": ([m2], {"M2": "break-restore"}, "还原失败", 1),
    }
    names = (list(cases) + ["drift"]) if name == "all" else [name]
    unknown = [n for n in names if n not in cases and n != "drift"]
    if unknown:
        print(f"未知自证名 {unknown}；可选 {list(cases)} + drift 或 all", file=sys.stderr)
        return 2
    overall = 0
    for n in names:
        if n == "drift":
            print("\n===== 自证 drift：期望「改副本树能红、还原能放」 =====", flush=True)
            overall |= run_drift_selftest()
            continue
        mutations, faults, expect_verdict, expect_rc = cases[n]
        tree = Path(os.environ["TEMP"]) / f"d-mut-selftest-{n}"
        print(f"\n===== 自证 {n}：期望判定={expect_verdict} / 期望退出码={expect_rc} =====", flush=True)
        code, lines, stats = run_pipeline(tree, mutations, SELFTEST_SELECTION, faults=faults)
        print("\n".join(lines), flush=True)
        got = stats["verdicts"][0][1] if stats["verdicts"] else "(未执行)"
        ok = got == expect_verdict and code == expect_rc
        print(
            f"[自证] {n}: 实测判定={got} / 实测退出码={code}"
            f"（期望 {expect_verdict} / {expect_rc}）⇒ {'PASS' if ok else 'FAIL'}",
            flush=True,
        )
        if not ok:
            overall = 1
    print(f"\n[自证] 合计 ⇒ {'PASS' if overall == 0 else 'FAIL'}（rc={overall}）", flush=True)
    return overall


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "--selftest":
        return run_selftest(argv[1] if len(argv) > 1 else "all")
    topup = "--no-fixture-topup" not in argv
    only: list[str] = []
    if "--only" in argv:
        only = argv[argv.index("--only") + 1].split(",")
    mutations = [m for m in MUTATIONS if not only or m[0] in only]
    if not mutations:
        print(f"--only {only} 没匹配到任何变异", file=sys.stderr)
        return 2
    code, lines, stats = run_pipeline(TREE, mutations, [], topup=topup)
    if lines:
        print("\n".join(lines), flush=True)
    if stats["baseline_ok"]:
        write_readings(lines)
        print(f"读数控成 → {READINGS}", flush=True)
    else:
        print("‼️ 本次基线无效 ⇒ 不写读数（保留上一次有效读数）", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
