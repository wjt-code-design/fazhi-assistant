import os
from dotenv import load_dotenv

load_dotenv()

from database import SessionLocal, init_db
from models import User
from auth import hash_password


def seed():
    init_db()  # 幂等建表
    db = SessionLocal()
    try:
        username = os.getenv("ADMIN_USERNAME", "admin")
        password = os.getenv("ADMIN_PASSWORD", "admin12345")
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
