"""重置已有用户（含管理员）的口令。与 seed_admin.py 互补：

- `seed_admin.py` 只在用户不存在时创建，见账号已存在就直接返回 ⇒ 改 `backend/.env` 里的
  `ADMIN_PASSWORD`、或重跑 seed，都**不会**碰到库里那个 `password_hash`（对抗审计 2026-08-07 的
  "禁止公知默认口令上线" 只挡住首次创建，挡不住这一步）；
- 本脚本只改**已存在**的用户，且不接受命令行传口令、不读 `ADMIN_PASSWORD`——口令只从终端
  `getpass` 进来（先校验再二次确认）⇒ 正在退役的旧值不可能被顺手写回数据库。

用法（默认预览，不写库）：

    cd backend && python scripts/reset_admin_password.py --username admin
    cd backend && python scripts/reset_admin_password.py --username admin --write

限制（已钉成判据 `tests/test_reset_admin_password.py`）：改口令**不会**作废已签发的 JWT——
token payload 里没有密码版本，认证只校 `JWT_SECRET` 与 `is_active`。要立刻踢掉旧会话，
需另换 `JWT_SECRET` 并重启后端，代价是所有用户重新登录。
"""

import argparse
import getpass
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)

from dotenv import load_dotenv

load_dotenv()

from audit import log_audit
from auth import hash_password
from database import SessionLocal, init_db
from models import User

AUDIT_ACTION = "admin.password_reset"
# 对抗审计 2026-08-07 点名的公知默认口令：不允许被"重置"回去
PUBLIC_DEFAULT = "admin12345"


def _read_new_password() -> str | None:
    try:
        first = getpass.getpass("新口令（输入不回显）：")
    except EOFError:
        print("终端不可交互：请在有 tty 的会话里运行（容器内用 docker exec -it）。", file=sys.stderr)
        return None
    if not first:
        print("空口令被拒绝。", file=sys.stderr)
        return None
    if first == PUBLIC_DEFAULT:
        print("公知默认口令被拒绝（见对抗审计 2026-08-07）。", file=sys.stderr)
        return None
    try:
        second = getpass.getpass("再输一次确认：")
    except EOFError:
        print("终端不可交互：请在有 tty 的会话里运行（容器内用 docker exec -it）。", file=sys.stderr)
        return None
    if first != second:
        print("两次输入不一致，未写入。", file=sys.stderr)
        return None
    return first


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="重置已有用户口令（默认预览；口令只从终端输入）")
    ap.add_argument("--username", default=None, help="用户名（缺省时取 .env 的 ADMIN_USERNAME）")
    ap.add_argument("--write", action="store_true", help="真正写库；不带此参数只预览目标")
    args = ap.parse_args(argv)

    username = args.username or os.getenv("ADMIN_USERNAME", "admin")
    password = _read_new_password()
    if password is None:
        return 1

    if args.write:
        init_db()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            print(
                f"用户 {username} 不存在：本脚本只改已存在的账号，不创建管理员（新建请用 seed_admin.py）。",
                file=sys.stderr,
            )
            return 1
        user_id = user.id
        role = user.role
        if not args.write:
            print(f"预览：目标 {username}（id={user_id}，role={role}），未写入。加 --write 才会改库。")
            return 0
        user.password_hash = hash_password(password)
        db.commit()
    finally:
        db.close()

    log_audit(user_id, AUDIT_ACTION, target=username, detail="via-cli")
    print(f"已重置 {username} 的口令。")
    print("注意：已签发的 JWT 不会因为改口令而失效；要立刻作废旧会话请换 JWT_SECRET 并重启后端。")
    print("同步提示：若 backend/.env 仍留着退役中的旧口令，请一并改掉（本脚本不读 ADMIN_PASSWORD）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
