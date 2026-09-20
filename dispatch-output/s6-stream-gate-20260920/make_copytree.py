"""票 C/S6 副本树搭建器（跑变异 / 采改前基线用；live 树禁止全量）。

用法（cwd 任意，脚本自己算路径）：
    backend/venv/Scripts/python.exe dispatch-output/s6-stream-gate-20260920/make_copytree.py \
        <commit> <目标目录> [--overlay 相对路径 …]

做三件事，每件都会在 stdout 里回读自证：
  ① `git archive <commit> | tar -x -C <目标>` —— 拿到**当时提交**的源码，不受在途工作树影响；
     `--overlay` 给出的一批路径随后用**工作树当前内容**盖进去（改后树用得上：本票的改动还没提交，
     `git archive HEAD` 里没有它。故意不走 `git stash create`/`commit-tree` —— 那会往 `.git`
     里写对象，而本票边界禁止）。
  ② 把**本轮新写的测试文件**盖进去（`_sse_harness.py` + `test_stream_exit_law_version_gate.py`）：
     改前/改后逐帧比对要成立，两侧必须是**同一套测试代码、只有被测源码不同**；
  ③ 自备 `dispatch-output/task1/`（被 .gitignore 排除）—— 缺了它
     `tests/test_harness_fact_reveal.py` 会在**收集期**抛错（不是运行期失败），
     而变异执行器把"基线有 error"判成 RUN_VOID。

不复制 `.env`（副本里必须没有它：`tests/conftest.py` 会把 DATABASE_URL/QUOTA_DB/CHROMA_DIR
无条件指到进程私有临时路径，真实库因此零接触；而 §6-⑦ 那条"真实配置"读数只在 live 树取）。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEST_FILES = (
    "backend/tests/_sse_harness.py",
    "backend/tests/test_stream_exit_law_version_gate.py",
)
TASK1_KEEP = (
    "hidden_runner.py",
    "hidden-cases-v1.json",
    "hidden-commitment.json",
    "hidden-round-protocol-v1.json",
)


def main() -> int:
    argv = sys.argv[1:]
    overlay: list[str] = []
    if "--overlay" in argv:
        i = argv.index("--overlay")
        overlay = argv[i + 1 :]
        argv = argv[:i]
    if len(argv) != 2:
        print(__doc__)
        return 2
    commit, dest = argv[0], Path(argv[1]).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    with (
        subprocess.Popen(
            ["git", "archive", "--format=tar", commit], cwd=REPO, stdout=subprocess.PIPE
        ) as pro,
        tarfile.open(fileobj=pro.stdout, mode="r|") as tf,  # type: ignore[arg-type]
    ):
        # `filter=` 是 3.11.6+/3.12 才有的形参；本机 venv 在哪个小版本上不该由本脚本猜。
        try:
            tf.extractall(dest, filter="data")
        except TypeError:  # pragma: no cover - 老解释器
            tf.extractall(dest)
    rc = pro.wait()
    print(f"git archive {commit} -> {dest}  rc={rc}")

    for rel in overlay:
        src = REPO / rel
        if not src.is_file():
            print(
                f"overlay {rel}  MISSING（工作树里没有这个文件，副本树将停在 {commit} 的版本）"
            )
            continue
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        same = dst.read_bytes() == src.read_bytes()
        print(f"overlay(worktree) {rel}  bytes={dst.stat().st_size}  逐字节相同={same}")

    for rel in TEST_FILES:
        shutil.copyfile(REPO / rel, dest / rel)
        print(f"overlay {rel}  bytes={(dest / rel).stat().st_size}")

    t1 = dest / "dispatch-output/task1"
    t1.mkdir(parents=True, exist_ok=True)
    for name in TASK1_KEEP:
        src = REPO / "dispatch-output/task1" / name
        if src.is_file():
            shutil.copyfile(src, t1 / name)
            print(f"task1 {name}  bytes={(t1 / name).stat().st_size}")
        else:
            print(f"task1 {name}  MISSING（收集期会炸，先确认 {src} 在不在）")

    # 自证：副本里的被测源码必须是**当时提交**的版本，不是本轮在途版本。
    src_main = (dest / "backend/main.py").read_bytes().decode("utf-8")
    print(
        "VERIFIED copybase main.py 含 EXIT_STREAM =",
        "EXIT_STREAM" in src_main,
        "(改前树应为 False)",
    )
    print("VERIFIED copybase 无 .env =", not (dest / "backend/.env").exists())
    print(
        "VERIFIED harness 有 fallback_text =",
        "fallback_text" in (dest / TEST_FILES[0]).read_text(encoding="utf-8"),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
