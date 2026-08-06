import os

from dotenv import load_dotenv

load_dotenv()

from auth import hash_password
from database import SessionLocal, init_db
from models import User


def seed():
    init_db()  # 幂等建表
    db = SessionLocal()
    try:
        username = os.getenv("ADMIN_USERNAME", "admin")
        password = os.getenv("ADMIN_PASSWORD", "")
        if not password:
            print("错误：未设置 ADMIN_PASSWORD，拒绝创建管理员（禁止公知默认口令 admin12345 上线，对抗审计 2026-08-07）")
            raise SystemExit(1)
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"管理员 {username} 已存在，跳过创建")
            return
        admin = User(
            username=username,
            password_hash=hash_password(password),
            role="admin",
        )
        db.add(admin)
        db.commit()
        print(f"已创建管理员：{username}（初始密码见 .env 的 ADMIN_PASSWORD，请尽快修改）")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
