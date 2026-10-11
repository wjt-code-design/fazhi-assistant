"""CHROMA_DIR 一致性守卫（T-E2，2026-09-19）。

背景：`rag_chain.CHROMA_DIR` 是一个**环境变量出口**（生产不设 ⇒ 落 `backend/chroma_db`）。
但运维脚本各自把真实路径写死（本文件诞生时还有 6 处），于是存在一条静默错库通道：
谁为了部署在 shell / compose 里导出 `CHROMA_DIR`，`rag_chain` 会去新目录，而
`backup_data` 仍备份旧目录——**且照常打印"备份完成"**。备份/重建都是不可逆动作，
这种分歧不能靠"事后发现"。

本守卫**不做重定向**：备份的目标必须是显式的，不能让一个测试用的环境变量把它拐走。
它只做一件事——发现分歧就拒绝执行。

旧固定目标的 `assert_matches` 调用位置是硬约束：只能在 `if __name__ == "__main__"` 路径上调（见各脚本的 `_check_env_contract`），
**不能放进 `main()`，更不能在 import 期执行**——`tests/conftest.py` 会把 `CHROMA_DIR`
无条件指向测试临时库，若在 import 期或 `main()` 里读它，`test_backup_data` 这类直接调用
`main()` 的用例会被守卫打成 SystemExit，等于把测试套件钉红。

D-14 动态目标 CLI 在 main() 解析参数后调用 require_explicit_target，先选目标再加载库。
评测 CLI 使用 isolated_chroma；三者不能互相替代。
"""

import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager


def assert_matches(expected_dir: str, caller: str, env_name: str = "CHROMA_DIR") -> None:
    """环境变量未设、或与本脚本固定目标同指一处 ⇒ 放行；否则拒绝执行。"""
    got = os.environ.get(env_name)
    if not got:
        return
    if os.path.abspath(got) == os.path.abspath(expected_dir):
        return
    raise SystemExit(
        f"[{caller}] 拒绝执行：{env_name}={got} 指向与本脚本目标 {expected_dir} 不同的目录。\n"
        f"        二者分歧时备份/重建会作用在错误的向量库上且不可逆。\n"
        f"        处置：取消该环境变量，或把本脚本的路径常量改成同一个真源后再跑。"
    )


def require_explicit_target(caller: str) -> str:
    """CLI 读写前选择目标；初始化 Chroma 自身也可能写入，预览同样检查。"""
    chosen = os.environ.get("CHROMA_DIR")
    if not chosen or not chosen.strip():
        raise SystemExit(f"[{caller}:require_explicit_target] 拒绝执行：请先显式设置 CHROMA_DIR。")
    target = os.path.abspath(chosen)
    loaded = sys.modules.get("rag_chain")
    if loaded is not None:
        bound = getattr(loaded, "CHROMA_DIR", None)
        if bound is None or os.path.normcase(os.path.realpath(bound)) != os.path.normcase(os.path.realpath(target)):
            raise SystemExit(
                f"[{caller}:require_explicit_target] 拒绝执行：已初始化的知识库与目标不同，请用独立 CLI 进程。"
            )
    os.environ["CHROMA_DIR"] = target
    return target


@contextmanager
def isolated_chroma(caller: str) -> Iterator[str]:
    """评测专用的独立 CLI 进程，在加载运行单例前选择临时库。"""
    if any(name in sys.modules for name in ("settings", "rag_chain", "retrieval", "knowledge_service")):
        raise SystemExit(f"[{caller}:isolated_chroma] 拒绝执行：运行依赖已加载，请用独立 CLI 进程。")
    # ponytail: Windows Chroma 可持有文件锁；清理遗留需在 CLI 进程退出后进行。
    lane = None
    try:
        with tempfile.TemporaryDirectory(prefix=f"fazhi-{caller}-", ignore_cleanup_errors=True) as lane:
            overrides = {
                "CHROMA_DIR": os.path.join(lane, "chroma"),
                "QUOTA_DB": os.path.join(lane, "quota.sqlite"),
                "DATABASE_URL": "sqlite:///" + os.path.join(lane, "app.db").replace("\\", "/"),
                "EMBEDDING_PROVIDER": "local",
                "RERANK_ENABLED": "false",
                "EMBEDDING_QUOTA_TOTAL": "0",
                "RERANK_QUOTA_TOTAL": "0",
                "HF_HUB_OFFLINE": "1",
            }
            previous = {key: os.environ.get(key) for key in overrides}
            previous_cwd = os.getcwd()
            try:
                os.environ.update(overrides)
                # Chroma Settings reads cwd/.env implicitly, even without load_dotenv.
                os.chdir(lane)
                print(f"临时知识库：{overrides['CHROMA_DIR']}")
                yield require_explicit_target(caller)
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
                os.chdir(previous_cwd)
    finally:
        if lane is not None and os.path.exists(lane):
            print(f"[{caller}] 临时目录仍被文件锁占用，进程退出后可清理：{lane}", file=sys.stderr)
