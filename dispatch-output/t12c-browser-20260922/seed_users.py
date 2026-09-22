"""卡 C 前置：往**隔离库**播种浏览器测试账号（注册已在生产关闭 ⇒ 走"管理员建号"同款路径）。

只写 `dispatch-output/t12c-browser-20260922/verify.db`（本卡自己的隔离库），**不碰真库 `backend/app.db`**。
密码哈希复用后端自己的 `auth.hash_password`（bcrypt）——不自造第二套。
"""

from __future__ import annotations

import os
import pathlib
import sys

BACKEND = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper/backend")
DB = pathlib.Path(r"C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/t12c-browser-20260922/verify.db")
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env")

import sqlite3  # noqa: E402

from auth import hash_password  # noqa: E402

PWD = "t12c-Verify-123"
USERS = [("t12c_user", "user"), ("t12c_admin", "admin")]


def main() -> int:
    con = sqlite3.connect(DB)
    cur = con.cursor()
    for name, role in USERS:
        cur.execute("SELECT id FROM users WHERE username=?", (name,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE users SET password_hash=?, role=?, is_active=1 WHERE id=?",
                        (hash_password(PWD), role, row[0]))
            print(f"更新 {name} role={role}")
        else:
            cur.execute(
                "INSERT INTO users (username, password_hash, role, is_active, created_at) VALUES (?,?,?,1,CURRENT_TIMESTAMP)",
                (name, hash_password(PWD), role),
            )
            print(f"新建 {name} role={role}")
    con.commit()
    n = cur.execute("SELECT count(*) FROM users").fetchone()[0]
    con.close()
    print("隔离库 users 总数 =", n, "；真库未被触碰（db 路径:", DB.name, ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
