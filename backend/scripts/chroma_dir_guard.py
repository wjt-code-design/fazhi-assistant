"""CHROMA_DIR 一致性守卫（T-E2，2026-09-19）。

背景：`rag_chain.CHROMA_DIR` 是一个**环境变量出口**（生产不设 ⇒ 落 `backend/chroma_db`）。
但运维脚本各自把真实路径写死（本文件诞生时还有 6 处），于是存在一条静默错库通道：
谁为了部署在 shell / compose 里导出 `CHROMA_DIR`，`rag_chain` 会去新目录，而
`backup_data` 仍备份旧目录——**且照常打印"备份完成"**。备份/重建都是不可逆动作，
这种分歧不能靠"事后发现"。

本守卫**不做重定向**：备份的目标必须是显式的，不能让一个测试用的环境变量把它拐走。
它只做一件事——发现分歧就拒绝执行。

调用位置是硬约束：只能在 `if __name__ == "__main__"` 路径上调（见各脚本的 `_check_env_contract`），
**不能放进 `main()`，更不能在 import 期执行**——`tests/conftest.py` 会把 `CHROMA_DIR`
无条件指向测试临时库，若在 import 期或 `main()` 里读它，`test_backup_data` 这类直接调用
`main()` 的用例会被守卫打成 SystemExit，等于把测试套件钉红。
"""

import os


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
