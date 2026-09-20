"""T-E S5 门禁跑者：把「必须等安静窗口」换成「跑完自己判定这轮算不算」。

为什么需要它：本仓多个 AI 会话共享同一工作树并行改码。直接跑 `pytest -m "not slow"`
出红时无法归因——红可能是别人中途改了源码（本仓已发生过一次整轮 ImportError 假失败）。
执行书 §4 T-E 因此把全量跑挂在"等无并发窗口"上；但窗口不可控，这条判据就一直不闭。

本脚本的处置：不承诺"无并发"，改成**事后自证**——
  ① 跑前对 backend 下所有 .py（排除 venv/.缓存/tests 的 basetemp）取 sha256 快照；
  ② 跑前/跑后各采一次 python 进程数（只作观测，不作判据）；
  ③ 跑前/跑后各做一次真实 chroma_db 整目录清单（manifest_chroma.py 的口径）；
  ④ 跑完再取一次 sha256。任何 .py 在跑的过程中变了 ⇒ **RUN_VOID**（这轮的 passed/failed
     都不可用作 T-E 判据，重跑）；没变 ⇒ **RUN_VALID**。
判据分两类，别混：
  - 内容/回归判据：pytest 退出码 + 末行计数（仅 RUN_VALID 时有效）。
  - 隔离判据：真实库清单前后一致（RUN_VOID 时**依然有效**——因为默认层已让每个会话
    的写盘落到各自私有目录，别人中途改码不会让真实库被写）。

用法（cwd=backend）：
  ./venv/Scripts/python.exe ../dispatch-output/te-chroma-isolation-20260918/run_gate_full.py <标签>
产出：同目录下 gate-<标签>.log / gate-<标签>-source-sha.json / gate-<标签>-verdict.txt
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "backend"
SKIP_DIR_NAMES = {
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "node_modules",
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_sources() -> dict[str, str]:
    out = {}
    for root, dirs, files in os.walk(BACKEND):
        dirs[:] = [
            d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith(".ptmp")
        ]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = Path(root) / fn
            out[p.relative_to(BACKEND).as_posix()] = sha256_of(p)
    return out


def fingerprint_others() -> dict:
    """真实 app.db / quota_used.sqlite 的指纹（把"测试不写它们"从 mtime 推断升级成实测）。

    读不到就记 None，不炸门禁；SQLite 的 file change counter（头 24-28 字节）是
    "有没有被写过"的独立判据，比 mtime 硬（mtime 可被复制/还原改写）。
    """
    out = {}
    for name, rel in (("app_db", "app.db"), ("quota_db", "data/quota_used.sqlite")):
        f = BACKEND / rel
        if not f.is_file():
            out[name] = {"absent": True}
            continue
        b = f.read_bytes()
        st = f.stat()
        cc = int.from_bytes(b[24:28], "big") if len(b) >= 28 else -1
        out[name] = {
            "sha256": hashlib.sha256(b).hexdigest(),
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "cc": cc,
        }
    return out


def count_python_procs() -> int:
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # 观测项，取不到不影响门禁
        print(f"  (进程采样失败，仅观测：{exc})")
        return -1
    return len(
        [
            ln
            for ln in r.stdout.splitlines()
            if ln.strip().lower().startswith('"python.exe"')
        ]
    )


def worktree_fingerprint() -> dict:
    """全仓工作树指纹（第 2 层检测兜底）：**删除与新增分开数**。

    目的：守卫豁免后，"意外删除"不再被守卫**预防** ⇒ 改为**检测**——
    跑前/跑后各取一次。检测目标是 **删除**（` D`/`D ` 行）；**新增不算异常**
    （并行会话随时会在未跟踪目录里落新文件——第一版把总行数当信号，
    被并行会话的一次正常落盘触发假警报，归因后改成删除单列）。
    """
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=BACKEND.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = sorted(r.stdout.splitlines())
    deletions = [ln for ln in lines if ln.startswith(" D") or ln.startswith("D")]
    untracked = sum(1 for ln in lines if ln.startswith("??"))
    return {
        "deleted_tracked": len(deletions),
        "deleted_tracked_list": deletions[:20],
        "untracked": untracked,
        "signature": lines,
    }


def run_pytest(basetemp: Path, log: Path, exempt_safe_delete: bool) -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "not slow",
        "-q",
        f"--basetemp={basetemp}",
        "-p",
        "no:cacheprovider",
    ]
    env = dict(os.environ)
    if exempt_safe_delete:
        # 第 1 层（Owner 2026-09-21 批准）：为 **pytest 子进程**剥离守卫激活所需的两个变量。
        # 依 sitecustomize._check_bulk_delete_guard：两者缺一 ⇒ 守卫对该进程不激活
        # ⇒ 子进程获得与 CI 相同的语义（CI 上本无此守卫）。只影响本子进程；
        # 交互式 agent 的删除操作（本跑者自身的 rm/unlink）仍受守卫保护。
        for k in ("CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR", "CODEBUDDY_TOOL_CALL_ID"):
            env.pop(k, None)
        print(
            "  guard=exempt（子进程已剥离 CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR / TOOL_CALL_ID）",
            flush=True,
        )
    else:
        print(
            "  guard=guarded（守卫随环境激活；若被踩中请按 T1 的复跑规则处置）",
            flush=True,
        )
    print("  $ " + " ".join(cmd), flush=True)
    with log.open("wb") as fh:
        return subprocess.run(
            cmd,
            cwd=BACKEND,
            stdout=fh,
            stderr=subprocess.STDOUT,
            timeout=3600,
            check=False,
            env=env,
        ).returncode


def manifest(tag: str) -> dict:
    log = HERE / f"manifest-{tag}.log"
    with log.open("wb") as fh:
        subprocess.run(
            [sys.executable, str(HERE / "manifest_chroma.py"), tag],
            cwd=BACKEND,
            stdout=fh,
            stderr=subprocess.STDOUT,
            timeout=600,
            check=False,
        )
    return json.loads((HERE / f"manifest-{tag}.json").read_text(encoding="utf-8"))


def main() -> int:
    raw_args = list(sys.argv[1:])
    exempt_safe_delete = "--exempt-safe-delete" in raw_args
    raw_args = [a for a in raw_args if a != "--exempt-safe-delete"]
    if raw_args and raw_args[0].startswith(("-", "--")):
        print(__doc__)
        return 2
    tag = raw_args[0] if raw_args else time.strftime("run-%Y%m%d-%H%M%S")
    verdict_path = HERE / f"gate-{tag}-verdict.txt"
    # basetemp 必须放在 backend/ 之外：test_log_field_whitelist 会递归扫 backend/ 全树找
    # 未登记的日志字段，而它自己造的哨本文件就落在 tmp_path 里 ⇒ basetemp 设在 backend 内
    # 会让该用例**永远红**（失败后 pytest 保留其 temp 目录，下轮继续被扫到，自反馈）。
    basetemp = Path(tempfile.gettempdir()) / f"fazhi_gate_{tag}"
    log = HERE / f"gate-{tag}.log"

    print("[1/5] 跑前源码快照 + 进程观测 …", flush=True)
    pre_src = snapshot_sources()
    procs_pre = count_python_procs()
    wt_pre = worktree_fingerprint()
    print(
        f"      .py 文件 {len(pre_src)} 个；python 进程 {procs_pre} 个（仅观测）",
        flush=True,
    )

    print("[2/5] 跑前真实库清单 …", flush=True)
    man_pre = manifest(f"{tag}-pre")
    others_pre = fingerprint_others()

    t0 = time.time()
    print("[3/5] 全量 -m 'not slow' …", flush=True)
    rc = run_pytest(basetemp, log, exempt_safe_delete)
    dur = time.time() - t0

    print("[4/5] 跑后源码快照 + 真实库清单 …", flush=True)
    post_src = snapshot_sources()
    procs_post = count_python_procs()
    wt_post = worktree_fingerprint()
    man_post = manifest(f"{tag}-post")
    others_post = fingerprint_others()

    changed = sorted(
        k for k in set(pre_src) | set(post_src) if pre_src.get(k) != post_src.get(k)
    )
    src_stable = not changed
    wt_stable = wt_pre["deleted_tracked"] == 0 and wt_post["deleted_tracked"] == 0
    db_untouched = man_pre["content_fingerprint"] == man_post[
        "content_fingerprint"
    ] and (man_pre["sqlite_change_counter"] == man_post["sqlite_change_counter"])
    tail = [
        ln
        for ln in log.read_text(encoding="utf-8", errors="replace").splitlines()
        if ln.strip()
    ][-1:]
    summary = tail[0].strip() if tail else "(末行空？去 log 里看)"
    wt_note = (
        "✅ 无已跟踪文件被删除"
        if wt_stable
        else f"❌ 检测到已跟踪文件被删除：跑后 {wt_post['deleted_tracked']} 条（{wt_post['deleted_tracked_list']}）"
    )

    lines = [
        f"标签: {tag}",
        f"结论: {'RUN_VALID（源码全程未变，passed/failed 可用作 T-E 判据）' if src_stable else 'RUN_VOID（跑的过程中源码被改，本轮不可用，重跑）'}",
        f"pytest 退出码: {rc}   耗时: {dur / 60:.1f} 分   basetemp: {basetemp}（在 %TEMP%，仓库外）",
        f"守卫: {'exempt（子进程已剥离激活变量；依 sitecustomize 两者缺一即不激活）' if exempt_safe_delete else 'guarded'}",
        f"工作树指纹: {wt_note}",
        f"末行: {summary}",
        f"真实库隔离: {'零写入 ✅' if db_untouched else '被写过 ❌（归因见 mtime/cc）'}",
        f"  前: fingerprint={man_pre['content_fingerprint']}",
        f"  后: fingerprint={man_post['content_fingerprint']}",
        f"  sqlite cc {man_pre['sqlite_change_counter']} → {man_post['sqlite_change_counter']}；集合条目 {man_post['collection_counts']}",
        f"源码变动文件 ({len(changed)}): {changed}",
        f"python 进程数 观测: 前 {procs_pre} → 后 {procs_post}",
        "其余真实产物指纹（前==后 ⇒ 测试 lane 未写）:",
        "  app.db  "
        + ("不变 ✅" if others_pre["app_db"] == others_post["app_db"] else "变了 ❌ ")
        + f"cc {others_pre['app_db'].get('cc')} → {others_post['app_db'].get('cc')}",
        "  quota   "
        + (
            "不变 ✅"
            if others_pre["quota_db"] == others_post["quota_db"]
            else "变了 ❌ "
        )
        + f"cc {others_pre['quota_db'].get('cc')} → {others_post['quota_db'].get('cc')}",
        "注意: 隔离判据与 RUN_VOID 无关——源码被改只让『0 failed』失效，不让『零写入』失效。",
    ]
    text = "\n".join(lines)
    verdict_path.write_text(text + "\n", encoding="utf-8", newline="\n")
    (HERE / f"gate-{tag}-source-sha.json").write_text(
        json.dumps(
            {"pre": pre_src, "post": post_src, "changed": changed},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(text)
    print(f"⇒ 已写 {verdict_path.name}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
