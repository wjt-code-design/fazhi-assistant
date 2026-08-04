"""embedding 换班一键脚本（ADR-011 阶段7，grilling 更优解①）。

换班 = 切到备用 embedding 模型并重建向量库（不同模型语义空间不同，须重建）。自动完成：
  1. 校验目标模型在换班序列中 + 当前为云端模式
  2. 估算本次重建 token（读旧库字符 ≈ 861K）并检查当前 embedding 配额是否足够
  3. 改 backend/.env 的 EMBEDDING_MODEL（+ 可选 --dimensions）
  4. 调 rebuild_embeddings.py 全量重嵌入（含 count/dimension/召回校验）
  5. 提示重启后端生效

换班序列（强度降序，grilling 用户确认）：text-embedding-v4（主力）→ 备用强 → 中 → 弱。
用法：cd backend && python scripts/switch_embedding.py <模型名> [--dimensions N] [--dry-run]
"""

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = os.path.join(BACKEND, ".env")
load_dotenv(ENV)

from rebuild_embeddings import _COLLECTION_LOCAL, _QA_COLLECTION_LOCAL, _read_old  # noqa: E402

from rag_chain import COLLECTION_NAME, QA_COLLECTION_NAME  # noqa: E402
from settings import settings  # noqa: E402

# 换班序列（强度降序；换班顺序 = 先强后弱，耗尽再下探）
SWITCH_SEQUENCE = [
    "text-embedding-v4",  # 主力（当前）
    "tongyi-embedding-vision-plus",  # 强
    "qwen3-vl-embedding",  # 强
    "tongyi-embedding-vision-plus-2026-03-06",  # 中
    "qwen3.7-text-embedding",  # 中
    "tongyi-embedding-vision-flash-2026-03-06",  # 中
    "tongyi-embedding-vision-flash",  # 弱（轻量）
    "qwen2.5-vl-embedding",  # 弱（轻量）
]

# 模型→建议维度（已实测确认填值；None=未确认，执行时查阿里云文档）
MODEL_DIMENSIONS: dict[str, int | None] = {
    "text-embedding-v4": 768,
    "tongyi-embedding-vision-plus": None,
    "qwen3-vl-embedding": None,
    "tongyi-embedding-vision-plus-2026-03-06": None,
    "qwen3.7-text-embedding": None,
    "tongyi-embedding-vision-flash-2026-03-06": None,
    "tongyi-embedding-vision-flash": None,
    "qwen2.5-vl-embedding": None,
}


def _env_set(key: str, value: str) -> None:
    lines: list[str] = []
    found = False
    if os.path.exists(ENV):
        with open(ENV, encoding="utf-8") as f:
            lines = f.readlines()
    with open(ENV, "w", encoding="utf-8") as f:
        for line in lines:
            if line.strip().startswith(key + "="):
                f.write(f"{key}={value}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"{key}={value}\n")
    print(f"  .env: {key}={value}")


def _estimate_rebuild_tokens() -> int:
    """读**当前活跃库**全量字符估算重建 token（与 rebuild 同口径；B1 修复：数据源=当前库）。"""
    import chromadb

    from quota_utils import estimate_tokens_chars

    client = chromadb.PersistentClient(path=os.path.join(BACKEND, "chroma_db"))
    col = client.get_collection(COLLECTION_NAME)
    if col.count() == 0 and COLLECTION_NAME != _COLLECTION_LOCAL:
        col = client.get_collection(_COLLECTION_LOCAL)
    docs_main, _ = _read_old(col, col.name)
    qa_docs: list[str] = []
    try:
        qa_col = client.get_collection(QA_COLLECTION_NAME)
        if qa_col.count() == 0 and QA_COLLECTION_NAME != _QA_COLLECTION_LOCAL:
            qa_col = client.get_collection(_QA_COLLECTION_LOCAL)
        qa_data = qa_col.get(include=["documents"])
        qa_docs = list(qa_data["documents"] or [])
    except Exception:
        pass
    total_chars = sum(len(d) for d in docs_main) + sum(len(d) for d in qa_docs)
    return estimate_tokens_chars(total_chars)


def _port_pid(port: int) -> str | None:
    """找监听指定端口的 PID（Windows netstat -ano 解析）。"""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and f":{port}" in parts[1] and parts[3] == "LISTENING":
            return parts[4]
    return None


def _restart_backend() -> None:
    """重启后端（仅 --restart 显式触发，Windows）：停 8000 进程后启动 uvicorn。"""
    import time

    pid = _port_pid(8000)
    if pid:
        print(f"  检测到 8000 端口进程 PID={pid}，正在停止…")
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
        for _ in range(20):  # 等端口释放（最多 ~10s）
            if _port_pid(8000) is None:
                break
            time.sleep(0.5)
    print("  启动后端（uvicorn main:app --port 8000）…")
    DETACHED = 0x00000008
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=BACKEND,
        creationflags=DETACHED | subprocess.CREATE_NEW_PROCESS_GROUP,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("  后端已启动（日志在独立进程；8000 端口访问）。")


def main() -> None:
    ap = argparse.ArgumentParser(description="embedding 换班：切备用模型并重建向量库")
    ap.add_argument("model", help="目标 embedding 模型名（换班序列之一）")
    ap.add_argument("--dimensions", type=int, default=None, help="目标模型向量维度（默认保持当前配置）")
    ap.add_argument("--dry-run", action="store_true", help="只校验与估算，不改配置不重建")
    ap.add_argument(
        "--restart", action="store_true",
        help="换班后自动重启后端（停 8000 进程再启动；默认不碰服务，只提示手动重启）",
    )
    args = ap.parse_args()

    print(f"当前 embedding provider: {settings.embedding_provider}")
    if settings.embedding_provider != "aliyun":
        print("⚠ 当前非云模式（EMBEDDING_PROVIDER=local）。换班仅对云端有效；本地 BGE 无需换班。")
        sys.exit(1)

    if args.model not in SWITCH_SEQUENCE:
        print(f"❌ {args.model} 不在换班序列：{' → '.join(SWITCH_SEQUENCE)}")
        sys.exit(1)

    print(f"当前模型: {settings.embedding_model}（dimensions={settings.embedding_dimensions}）")
    print(f"目标模型: {args.model}（dimensions={'保持 ' + str(settings.embedding_dimensions) if args.dimensions is None else str(args.dimensions)}）")
    if args.model == settings.embedding_model and args.dimensions is None:
        print("⚠ 目标模型与当前相同且维度不变——无需换班。")
    # 维度校验（B7）：已知维度且与当前不同 → 必须显式 --dimensions 一并改，否则 rebuild 维度校验会失败
    known_dim = MODEL_DIMENSIONS.get(args.model)
    target_dim = args.dimensions if args.dimensions is not None else settings.embedding_dimensions
    if known_dim is None:
        print(f"⚠ {args.model} 的维度未确认——若 rebuild 校验报维度不匹配，请查阿里云文档后用 --dimensions 指定")
    elif known_dim != target_dim:
        print(f"❌ {args.model} 维度 {known_dim} ≠ 当前配置 {settings.embedding_dimensions}——必须用 --dimensions {known_dim} 一并改，否则向量库维度不匹配。")
        sys.exit(1)

    # 配额检查（诚实计费：重建消耗计入当前 embedding 配额）
    from quota_utils import utility_pct_left, utility_quota_total_for

    total = utility_quota_total_for("embedding")
    need = _estimate_rebuild_tokens()
    print("\n=== 估算 ===")
    print(f"本次重建约需 ~{need:,} token")
    if total <= 0:
        print("当前未启用配额监控（EMBEDDING_QUOTA_TOTAL=0）——不检查配额。")
    else:
        left = utility_pct_left("embedding")
        print(f"当前 embedding 配额剩余 {left * 100:.1f}%（总 {total:,}）")
        if left <= 0:
            print("❌ 当前 embedding 配额已耗尽——换班重建需要配额。请先给备用模型配额度（RERANK_QUOTA 无关）。")
            sys.exit(1)
        if utility_quota_total_for("embedding") * left < need:
            print("⚠ 当前配额可能不足以完成整次重建——换班后配额会显示真实剩余，接近耗尽时重建可能中断。")

    if args.dry_run:
        print("\n--dry-run：不修改配置、不重建。确认后去掉 --dry-run 实跑。")
        sys.exit(0)

    # 改 .env
    print("\n=== 改配置 ===")
    _env_set("EMBEDDING_MODEL", args.model)
    if args.dimensions is not None:
        _env_set("EMBEDDING_DIMENSIONS", str(args.dimensions))

    # 调 rebuild（新进程，加载改后的 .env）
    print("\n=== 全量重嵌入（复用 rebuild_embeddings.py）===")
    r = subprocess.run([sys.executable, os.path.join(BACKEND, "scripts", "rebuild_embeddings.py")], cwd=BACKEND)
    if r.returncode != 0:
        print("\n❌ 重建失败。.env 已改为新模型；可重跑本脚本或检查 quota 后修复。")
        sys.exit(r.returncode)

    print("\n=== 换班完成 ===")
    if args.restart:
        print("重启后端（--restart）…")
        _restart_backend()
    else:
        print("未传 --restart（默认不碰服务）。请手动重启后端生效：")
        print("  cd backend && venv\\Scripts\\activate && python -m uvicorn main:app --port 8000")
    print("验证：登录管理员后台看 embedding 配额剩余（= 新模型总额 − 本次重建消耗）。")


if __name__ == "__main__":
    main()
