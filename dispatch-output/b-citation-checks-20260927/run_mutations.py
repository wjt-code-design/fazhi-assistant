"""B 票变异驱动：证明引用判据回归网里哪几条断言**是吃力的**（每只变异都必须打红）。

不证明"实现缺席时会红"，而证明"实现还在、只是判据被悄悄放宽/接线被拆掉时也会红"——
这正是本票要防的失效形状（错法名同条号整排隐身）。

用法（在仓库根跑；本文件按自身位置推出仓库根，与 cwd 无关）：
  backend\\venv\\Scripts\\python.exe dispatch-output\\b-citation-checks-20260927\\run_mutations.py

做法：先取字节 → 锚点必须唯一（count==1，否则报错退出，绝不带病继续）→ 跑目标用例文件 →
还原原始字节并核对 sha256。恢复是硬校验：核对不过就非零退出。
不连 Chroma、不调模型、不发网络请求：目标用例文件本身只读脚本对象与源码文本。
"""

import hashlib
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BACKEND = ROOT / "backend"
PY = BACKEND / "venv" / "Scripts" / "python.exe"
TARGET = "tests/test_smoke_citation_assertions.py"
READINGS = HERE / "mutation-readings.txt"

FAST = BACKEND / "scripts" / "smoke_citation_fast.py"
FULL = BACKEND / "scripts" / "smoke_citation_full.py"
CONTRIB = ROOT / "CONTRIBUTING.md"

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


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reading(proc: subprocess.CompletedProcess) -> tuple[int, list[str], str]:
    """取出**全部** FAILED 用例名与收尾汇总行——只留 tail 会把失败名单吃掉，报告就没法逐条核。"""
    out = proc.stdout + proc.stderr
    failed = [ln.split("::")[-1].split(" - ")[0].strip() for ln in out.splitlines() if ln.startswith("FAILED")]
    summary = [ln.strip().split("\n")[-1] for ln in out.splitlines() if " passed" in ln or " failed" in ln]
    return proc.returncode, failed, (summary[-1] if summary else "(无 summary 行)")


def run_target() -> tuple[int, list[str], str]:
    proc = subprocess.run(
        [str(PY), "-m", "pytest", TARGET, "-q", "-p", "no:cacheprovider"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    return reading(proc)


def main() -> int:
    if not PY.exists():
        print(f"venv python 不在预期位置：{PY}")
        return 2

    originals = {p: p.read_bytes() for p in {FAST, FULL, CONTRIB}}
    baseline = {p: sha(p) for p in originals}
    log: list[str] = []

    def emit(line: str) -> None:
        print(line)
        log.append(line)

    emit("== 基线（未变异）==")
    rc, failed, summary = run_target()
    emit(f"rc={rc}  {summary}")
    if rc != 0:
        emit(f"基线就不是绿的（失败：{failed or '—'}）⇒ 变异实验无意义，直接退出。")
        READINGS.write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
        return 3

    killed = survived = 0
    for name, path, old, new, *rest in MUTANTS:
        nth = rest[0] if rest else None
        body = originals[path].decode("utf-8")
        seen = body.count(old)
        if (nth is None and seen != 1) or (nth is not None and seen < nth):
            emit(f"[锚点异常] {name}｜count={seen}、需 {nth or 1}，未执行（锚点必须唯一/够数）")
            survived += 1
            continue
        path.write_bytes(body.replace(old, new, nth or 1).encode("utf-8"))
        rc, failed, summary = run_target()
        path.write_bytes(originals[path])  # 立即还原，再做校验
        verdict = "KILLED" if rc != 0 else "SURVIVED"
        killed += rc != 0
        survived += rc == 0
        emit(f"[{verdict}] {name}")
        emit(f"          rc={rc}  {summary}  ({path.name})")
        for fn in failed:
            emit(f"          - {fn}")

    emit("== 还原校验 ==")
    bad = [str(p) for p, digest in baseline.items() if sha(p) != digest]
    if bad:
        emit(f"还原失败（sha256 不符）：{bad}")
        READINGS.write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
        return 4
    for p, digest in baseline.items():
        emit(f"OK  {p.relative_to(ROOT)}  sha256={digest[:12]}…")

    emit(f"== 汇总：KILLED {killed} / SURVIVED {survived} / 共 {len(MUTANTS)} 只 ==")
    READINGS.write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
    print(f"读数已写入 {READINGS}")
    return 0 if survived == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
