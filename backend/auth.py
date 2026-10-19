import os
from datetime import UTC, datetime, timedelta

# 2026-09-10（独立验收回执 §D.1）：部署环境为 Python 3.11（backend/Dockerfile「FROM python:3.11-slim」、
# DEPLOYMENT.md §2.1「后端（Python 3.11）」）⇒ `datetime.UTC`（3.11+ 别名）可用，
# ruff UP017 自动修复已统一至此写法。原注释「服务器为 3.10，需 timezone.utc 兼容」
# 自 Dockerfile 切 3.11 起即过期，且与代码自相矛盾，本处据实更正（原 `UTC = timezone.utc`
# 兼容别名已随之删除——它对本仓库的任何运行环境都已是 no-op）。
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import User

JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


def _jwt_secret() -> str:
    # 调用时才读，避免模块导入早于 load_dotenv() 而抓到 None
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("缺少 JWT_SECRET，请在 .env 中设置")
    return secret


# auto_error=False：未带令牌时返回 None，由我们自行抛出统一的 401
_bearer = HTTPBearer(auto_error=False)

# 公知默认口令的**唯一真源**（对抗审计 2026-08-07）。原来只有 `scripts/reset_admin_password.py`
# 认得这个值，而 `seed_admin.py` 的报错文案承诺"禁止 admin12345 上线"却只校了"空" ⇒
# 同一事实两份拷贝、改一处漏一处（显式公知值仍会被种进库里）。
PUBLIC_DEFAULT_PASSWORD = "admin12345"

# 拒斥显式公知口令的**单一真源集合**（C05 / W09-E，2026-10-18）。刻意小集合——只挡模板占位、
# 历史泄漏值与最常见的几个弱口令；**口令强度策略不在本项范围内**，别把它当成通用强度校验。
PUBLIC_PLACEHOLDER_PASSWORDS: frozenset[str] = frozenset(
    {
        PUBLIC_DEFAULT_PASSWORD,  # 仓库历史里泄漏过的那个值（引用常量，不再手抄字面量）
        "change_me",  # 部署模板 .env.example 的原占位值（cp .env.example .env 就种出它）
        "changeme",  # 同上占位值的常见无下划线写法
        "your_password",  # 模板里常见的占位口令
        "your-password",  # 同上占位值的连字符写法
        "password",  # 最常见的弱口令
        "123456",  # 最常见的弱口令
    }
)


def is_public_default_password(password: str) -> bool:
    # strip().lower() 归一化是**有意的收紧**（C05 / W09-E）：大小写/首尾空白变体（如 " Change_Me "）
    # 同样要被拒，否则模板占位口令换个写法就能上线。
    return password.strip().lower() in PUBLIC_PLACEHOLDER_PASSWORDS


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "exp": datetime.now(UTC) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(creds.credentials, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="令牌无效或已过期") from None
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
