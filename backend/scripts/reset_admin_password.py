"""重置用户密码（含管理员）。与 seed_admin.py 互补：
- seed_admin 仅在用户不存在时创建（不覆盖已改密码）；
- 本脚本仅修改已有用户（不存在则报错），且打印 .env 同步提示。

用法：cd backend && python scripts/reset_admin_password.py --username admin --password 新密码
不传参数时回退到 backend/.env 的 ADMIN_USERNAME / ADMIN_PASSWORD。
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)

from dotenv import load_dotenv

load_dotenv()

from auth import hash_password  # noqa: E402
from database import SessionLocal, init_db  # noqa: E402
from models import User  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="重置用户密码（默认管理员）")
    ap.add_argument("--username", default=None, help="用户名（默认取 .env 的 ADMIN_USERNAME）")
    ap.add_argument("--password", default=None, help="新密码（默认取 .env 的 ADMIN_PASSWORD）")
    args = ap.parse_args()

    username = args.username or os.getenv("ADMIN_USERNAME", "admin")
    password = args.password or os.getenv("ADMIN_PASSWORD", "")
    if not password:
        print("未提供密码：请用 --password 传入，或在 backend/.env 设置 ADMIN_PASSWORD。", file=sys.stderr)
        sys.exit(1)

    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"用户 {username} 不存在，请先运行 python seed_admin.py 创建。", file=sys.stderr)
            sys.exit(1)
        user.password_hash = hash_password(password)
        db.commit()
        print(f"已重置 {username} 的密码。")
        print(
            "同步提示：请同时更新 backend/.env 的 ADMIN_PASSWORD 为新值，"
            "保持 .env 与数据库一致（seed_admin.py 仅在用户不存在时创建，不会覆盖已改密码）。"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
