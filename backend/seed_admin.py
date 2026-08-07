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
            if existing.role == "admin":
                print(f"管理员 {username} 已存在，跳过创建")
                return
            # 同名普通用户被抢占（对抗审计 v2 #4）：seed 不再静默跳过，否则管理接口永远 403
            print(f"错误：用户名 {username} 已被普通用户占用（role={existing.role}），无法创建管理员。")
            print("请修改 .env 的 ADMIN_USERNAME 改用其他名称，或先清理该占位用户后再运行 seed_admin.py。")
            raise SystemExit(1)
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
