"""B 票变异驱动（v2，2026-09-28 加固）：证明引用判据回归网里哪几条断言**是吃力的**（每只变异都必须打红）。

不证明"实现缺席时会红"，而证明"实现还在、只是判据被悄悄放宽/接线被拆掉时也会红"——
这正是本票要防的失效形状（错法名同条号整排隐身）。

本版按本票 DoD 加固的四件事（旧版的三处缺口在括号里点明）：
① **在副本树做变异**，不在活动工作树（旧版 `ROOT = HERE.parents[1]` 直接 `path.write_bytes(mutated)`
   改活动工作树，进程若在"写入变异"与"行内还原"之间被 Ctrl-C/崩溃，工作树**永久残留被变异的源码**，
   没有任何恢复保障）。副本树由 `git ls-files` + 工作树当前内容现建；`.env` / `chroma_db` / `venv`
   天然不在场。
② **还原放 `finally`**：异常/中断也把副本树写回**进入本次变异前读到的原始字节**；
   活动工作树**从始至终一个字节都不动**（`--selftest interrupt` 会核对 live 文件 sha256 不变 +
   副本树已还原两份读数）。
③ **每只变异都验运行完整性**：该次运行 **junit 用例数 ≥ 基线 junit 用例数**（改用 `--junitxml` 取数）。
   变异一旦让收集期报错，pytest 会**中断整会话**、junit 只剩 1 条"收集错误"伪用例，而 `rc != 0`
   ⇒ 旧版 `verdict = "KILLED" if rc != 0 else "SURVIVED"` 会把它记成 **KILLED（假杀）**。
   判为"实验无效"的变异**不计入 KILLED**、不计入存活，并让驱动非零退出。
④ **退出码语义**：存活 > 0 ⇒ 非零；任一"实验无效"/"还原失败"/锚点不合格 ⇒ 非零；
   只有「全部杀死 + 零无效 + 还原逐字通过」才 0（旧版：存活已经非零，但"无效"这条不存在 ⇒
   中断/收集失败会被读成 KILLED 且整体仍可能返回 0）。

`--selftest <positive|collect-fail|survived|restore-fail|interrupt|all>`：负向自证（受控注入失效形状），
跑独立副本树、**不写库内读数**。

用法（在仓库根跑；本文件按自身位置推出仓库根，与 cwd 无关）：
  backend\\venv\\Scripts\\python.exe dispatch-output\\b-citation-checks-20260927\\run_mutations.py
自证：同上再加 `--selftest collect-fail`

做法：先取字节 → 锚点必须唯一（count==1，否则报错/记无效、绝不带病继续）→ 在副本树跑目标用例文件 →
还原原始字节并核对 sha256。恢复是硬校验：核对不过就非零退出。
不连 Chroma、不调模型、不发网络请求：目标用例文件本身只读脚本对象与源码文本。
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BACKEND = ROOT / "backend"
PY = BACKEND / "venv" / "Scripts" / "python.exe"
TARGET = "tests/test_smoke_citation_assertions.py"
TREE = Path(os.environ["TEMP"]) / "b-mut-20260927"
TREE_SPECS = ("backend", "CONTRIBUTING.md", "data")  # 目标用例要 backend/ + 根 CONTRIBUTING.md
READINGS = HERE / "mutation-readings.txt"

FAST = BACKEND / "scripts" / "smoke_citation_fast.py"
FULL = BACKEND / "scripts" / "smoke_citation_full.py"
CONTRIB = ROOT / "CONTRIBUTING.md"

COLLECT_FAULT_SRC = "def test_zz_mut_fault(:\n    pass\n"
RESTORE_FAULT_SUFFIX = "\n# MUT-SELFTEST：还原后再改一次，验「还原失败」闸（自证用，只落在副本树）\n"

_EXPAND_BOTH = "output_normalize.expand_citations(output_normalize.expand_law_names(answer or \"\"))"

MUTANTS = [
    (
        "S1｜fast 判据退回只看条号（丢掉法名那一半）",
        FAST,
        "if src in want_sources and art in want_articles:",
        "if art in want_articles:",
    ),
    (
        "S2｜full 判定对法名失明（只比条号）",
        FULL,
        "any(src == want and art in set(expected_articles) for src, art in pairs)",
        "any(art in set(expected_articles) for src, art in pairs)",
    ),
    (
        "S3｜full 去掉 expand_law_names（裸法名不再补书名号）",
        FULL,
        _EXPAND_BOTH,
        "output_normalize.expand_citations(answer or \"\")",
    ),
    (
        "S4｜full 去掉 expand_citations（连续省略条号不再展开）",
        FULL,
        _EXPAND_BOTH,
        "output_normalize.expand_law_names(answer or \"\")",
    ),
    (
        "S5｜fast 法名归一退化为恒等（不再走 retrieval._source_key）",
        FAST,
        "return _source_key(name)",
        "return name",
    ),
    (
        "S6｜full 条号形状收窄（丢掉 〇○ 两字，与 retrieval._ART_FULL_RE 分叉）",
        FULL,
        "[零〇○一二三四五六七八九十百千万0-9０-９]+条(?:之",
        "[零一二三四五六七八九十百千万0-9０-９]+条(?:之",
    ),
    (
        "S7｜full 拆掉一处接线（两个出口里少一处过判据）",
        FULL,
        "ok_cite = answer_cites(c, source, expects)",
        "ok_cite = True",
        1,  # 该锚点天然出现两次（两个出口各一处）⇒ 只改第 1 处，用来验 AST 绊线数得对不对
    ),
    (
        "S8｜CONTRIBUTING 计数漂回旧值（17 项）",
        CONTRIB,
        "（24 项非 LLM 门禁 = 意图 7 + 召回 7 + 引用校验 3 + 复杂度 4 + 自检 3",
        "（17 项非 LLM 门禁 = 意图 7 + 召回 7 + 引用校验 3 + 复杂度 4 + 自检 3",
    ),
]

# 行为零变化的中性改动（自证"存活 ⇒ 非零退出"用）：任何测试都不该因此变红。
NEUTRAL_MUTANT = (
    "S0-survived｜自证：注释级中性改动",
    FAST,
    "import os",
    "import os  # MUT-SELFTEST-NEUTRAL（注释级中性改动，行为零变化）",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha16(path: Path) -> str:
    return sha(path)[:16]


def rel_of(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def build_tree(tree: Path) -> None:
    """副本树 = 工作树里 tracked 文件的当前内容（含各助手未提交的改动）。活动工作树只读。"""
    listed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", *TREE_SPECS],
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
        src, dst = ROOT / rel, tree / rel
        if not src.is_file():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    print(f"副本树建好：{n} 个文件 → {tree}", flush=True)


def reading(proc: subprocess.CompletedProcess) -> tuple[int, list[str], str]:
    """取出**全部** FAILED 用例名与收尾汇总行——只留 tail 会把失败名单吃掉，报告就没法逐条核。"""
    out = proc.stdout + proc.stderr
    failed = [ln.split("::")[-1].split(" - ")[0].strip() for ln in out.splitlines() if ln.startswith("FAILED")]
    summary = [
        ln.strip().split("\n")[-1]
        for ln in out.splitlines()
        if " passed" in ln or " failed" in ln or " error" in ln
    ]
    return proc.returncode, failed, (summary[-1] if summary else "(无 summary 行)")


def testcase_count(xml_path: Path) -> int:
    """junit 里的用例数：收集期报错时**只剩 1 条**"收集错误"伪用例（本机实测），✓ 运行完整性的读数。"""
    root = ET.parse(xml_path).getroot()
    suite = root if root.tag == "testsuite" else root[0]
    return sum(1 for _ in suite.iter("testcase"))


def run_target(tree: Path, xml_name: str, extra: list[str] | None = None) -> tuple[int, list[str], str, int]:
    xml = tree / xml_name
    proc = subprocess.run(
        [
            str(PY),
            "-B",
            "-m",
            "pytest",
            TARGET,
            "-q",
            "-p",
            "no:cacheprovider",
            f"--junitxml={xml}",
            *(extra or []),
        ],
        cwd=tree / "backend",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    rc, failed, summary = reading(proc)
    ran = testcase_count(xml) if xml.exists() else -1
    return rc, failed, summary, ran


def collect_count(tree: Path, extra: list[str] | None = None) -> tuple[int, int]:
    res = subprocess.run(
        [str(PY), "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only", TARGET, *(extra or [])],
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


def write_readings(lines: list[str]) -> None:
    """只重写机器读数，**保留**文件里人工写的 `## 附…` 段；落 **LF**（`newline=""`）。"""
    out = READINGS
    kept = ""
    if out.exists():
        text = out.read_text(encoding="utf-8", errors="replace")
        idx = text.find("\n## 附")
        kept = text[idx + 1 :].rstrip("\n") if idx >= 0 else ""
    body = "\n".join(lines) + "\n"
    if kept:
        body += "\n" + kept + "\n"
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write(body)


def apply_collect_fault(tree: Path, tag: str) -> list[str]:
    """受控注入"收集期失败"：放一个语法错模块进副本树 tests/ ⇒ 会话在收集期中断。"""
    broken = tree / "backend" / "tests" / f"test_zz_mut_fault_{tag}.py"
    with open(broken, "w", encoding="utf-8", newline="") as fh:
        fh.write(COLLECT_FAULT_SRC)
    return [f"tests/{broken.name}"]


def run_pipeline(tree: Path, mutants, *, faults: dict[str, str] | None = None) -> tuple[int, list[str], dict]:
    """建树 → 基线闸 → 逐只变异（③ 运行完整性 + ② `finally` 还原 + sha256 校验）→ ④ 聚合退出码。"""
    faults = faults or {}
    stats = {
        "baseline_ok": False,
        "denom": -1,
        "ran": -1,
        "killed": 0,
        "survived": 0,
        "invalid": 0,
        "restore_failed": 0,
        "interrupted": 0,
        "verdicts": [],
    }
    if not PY.exists():
        print(f"venv python 不在预期位置：{PY}")
        return 3, [], stats
    build_tree(tree)

    targets = sorted({p for _n, p, *_rest in mutants}, key=str)
    live_digests = {rel_of(p): sha(p) for p in targets}  # 活动工作树的进入前指纹（自证用）

    emit_lines: list[str] = []

    def emit(line: str) -> None:
        print(line, flush=True)
        emit_lines.append(line)

    denom, denom_rc = collect_count(tree)
    rc, failed, summary, ran = run_target(tree, "clean.xml")
    if denom <= 0 or denom_rc != 0 or ran < denom:
        emit(
            f"‼️ 基线没真跑过（collect-only={denom} / rc={denom_rc}，junit 用例数={ran}）"
            "⇒ 变异实验无意义，直接退出（不写读数）。"
        )
        return 3, emit_lines, stats
    stats.update(baseline_ok=True, denom=denom, ran=ran)
    emit("== 基线（未变异，副本树）==")
    emit(f"分母（--collect-only 单取）={denom}  junit 用例数={ran}")
    emit(f"rc={rc}  {summary}")
    if rc != 0:
        emit(f"基线就不是绿的（失败：{failed or '—'}）⇒ 变异实验无意义，直接退出。")
        return 3, emit_lines, stats
    emit(f"### 基线红清单（机器生成，逐条列全；共 {len(failed)} 条）")
    for fn in failed:
        emit(f"- {fn}")
    emit("（基线 rc=0 ⇒ 空；此后任一只变异的失败都是新增）")
    emit("活动工作树指纹（进入前，本次全程不得变）：")
    for rel, digest in live_digests.items():
        emit(f"  {rel}  sha256={digest[:12]}…")

    for name, path, old, new, *rest in mutants:
        tag = name.split("｜")[0].strip().lower().replace("-", "_")
        nth = rest[0] if rest else None
        rel = rel_of(path)
        target = tree / rel
        original = target.read_bytes()
        body = original.decode("utf-8")
        seen = body.count(old)
        if (nth is None and seen != 1) or (nth is not None and seen < nth):
            stats["invalid"] += 1
            stats["verdicts"].append((name, "实验无效"))
            emit(f"[实验无效] {name}｜锚点在副本树里 count={seen}、需 {nth or 1}，未执行变异")
            continue
        fault = faults.get(tag, "")
        mutated = body.replace(old, new, nth or 1).encode("utf-8")
        extra: list[str] = []
        interrupted = ""
        ran_m, rc, failed, summary = -1, -1, [], "(未跑)"
        try:
            target.write_bytes(mutated)  # ← 只写副本树；活动工作树此刻起也不动
            if fault == "interrupt":
                # 自证：模拟"写入变异"与"还原"之间被 Ctrl-C/崩溃打断（旧版正是在这两行之间没有 finally）
                raise KeyboardInterrupt("自证：模拟写入变异后、还原前被中断")
            if fault == "break-collect":
                extra = apply_collect_fault(tree, tag)
            rc, failed, summary, ran_m = run_target(tree, f"{tag}.xml", extra)
        except KeyboardInterrupt as exc:
            interrupted = str(exc)
        finally:
            # ② 还原：无论 return / 异常 / KeyboardInterrupt / 崩溃路径，都写回进入前的原始字节
            target.write_bytes(original)
            if fault == "break-collect":
                (tree / "backend" / "tests" / f"test_zz_mut_fault_{tag}.py").unlink(missing_ok=True)

        # 还原校验（副本树）+ 活动工作树未被触碰（自证 interrupt 的关键读数）
        ok_restore = sha(target) == sha_backup(original)
        live_ok = all(sha(ROOT / rel2) == digest for rel2, digest in live_digests.items())
        if fault == "break-restore":
            with open(target, "ab") as fh:
                fh.write(RESTORE_FAULT_SUFFIX.encode("utf-8"))
            ok_restore = sha(target) == sha_backup(original)
        complete = ran_m >= ran

        if interrupted:
            stats["interrupted"] += 1
            stats["invalid"] += 1
            verdict = "中断（已还原）"
        elif not ok_restore:
            stats["restore_failed"] += 1
            stats["invalid"] += 1
            verdict = "还原失败"
        elif not complete:
            stats["invalid"] += 1
            verdict = "实验无效"
        elif rc != 0:
            stats["killed"] += 1
            verdict = "KILLED"
        else:
            stats["survived"] += 1
            verdict = "SURVIVED"
        stats["verdicts"].append((name, verdict))
        emit(f"[{verdict}] {name}")
        emit(f"          rc={rc}  {summary}  ({rel})")
        emit(f"          运行完整性：本次 junit 用例数={ran_m} / 基线={ran} ⇒ {'通过' if complete else '无效（收集期报错/会话被中断）'}")
        emit(f"          副本树还原逐字一致={ok_restore}；活动工作树未被触碰={live_ok}")
        if verdict in ("KILLED", "SURVIVED"):
            for fn in failed:
                emit(f"          - {fn}")
        if verdict == "SURVIVED":
            emit("          ⚠️ 零新增失败 —— 这只变异在本回归网里没有守卫（变异存活）")
        if verdict == "实验无效":
            emit("          [!] 该次运行不完整 ⇒ 不计入 KILLED、不计入存活，且驱动非零退出")
        if interrupted:
            emit(f"          [!] 中断自证：{interrupted} ⇒ 副本树已还原={ok_restore}、live 未动={live_ok}")
        if not live_ok:
            emit("          ‼️ 活动工作树被改写了！驱动器事实违约，立即停。")
            break
        if not ok_restore:
            emit("          ‼️ 副本树还原失败 ⇒ 停在这里（后续变异不再执行）")
            break

    emit(
        f"== 汇总：KILLED {stats['killed']} / SURVIVED {stats['survived']} / 实验无效 {stats['invalid']}"
        f"（其中还原失败 {stats['restore_failed']}、中断 {stats['interrupted']}）/ 共 {len(mutants)} 只 =="
    )
    ok = stats["survived"] == 0 and stats["invalid"] == 0
    code = 0 if ok else 1
    emit(
        f"== 退出码判据：存活={stats['survived']} 无效={stats['invalid']}"
        f"（还原失败={stats['restore_failed']} 中断={stats['interrupted']}）⇒ rc={code} =="
    )
    emit("== 还原校验（对比进入前的活动工作树指纹）==")
    for rel, digest in live_digests.items():
        emit(f"{'OK' if sha(ROOT / rel) == digest else 'FAIL'}  {rel}  sha256={digest[:12]}…")
    return code, emit_lines, stats


def sha_backup(data: bytes) -> str:
    """与 `sha(Path)` 同轴：都是"文件内容的 sha256"（自证里比的是字节）。"""
    return hashlib.sha256(data).hexdigest()


def run_selftest(name: str) -> int:
    """负向自证：受控注入三种失效形状 + 一条正路 + 中断恢复，证明 ③④ 与 `finally` 会拦。**不写读数**。"""
    m = {entry[0].split("｜")[0].strip().lower().replace("-", "_"): entry for entry in MUTANTS}
    cases = {
        "positive": ([m["s1"]], {}, "KILLED", 0),
        "collect-fail": ([m["s1"]], {"s1": "break-collect"}, "实验无效", 1),
        "survived": ([NEUTRAL_MUTANT], {}, "SURVIVED", 1),
        "restore-fail": ([m["s1"]], {"s1": "break-restore"}, "还原失败", 1),
        "interrupt": ([m["s1"]], {"s1": "interrupt"}, "中断（已还原）", 1),
    }
    names = list(cases) if name == "all" else [name]
    unknown = [n for n in names if n not in cases]
    if unknown:
        print(f"未知自证名 {unknown}；可选 {list(cases)} 或 all", file=sys.stderr)
        return 2
    overall = 0
    for n in names:
        mutants, faults, expect_verdict, expect_rc = cases[n]
        tree = Path(os.environ["TEMP"]) / f"b-mut-selftest-{n}"
        print(f"\n===== 自证 {n}：期望判定={expect_verdict} / 期望退出码={expect_rc} =====", flush=True)
        code, lines, stats = run_pipeline(tree, mutants, faults=faults)
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
    code, lines, stats = run_pipeline(TREE, MUTANTS)
    if stats["baseline_ok"] and code in (0, 1):
        write_readings(lines)
        print(f"读数已写入 {READINGS}（LF）", flush=True)
    else:
        print("‼️ 本次基线无效 ⇒ 不写读数（保留上一次有效读数）", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
