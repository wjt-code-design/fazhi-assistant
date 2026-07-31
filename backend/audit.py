"""管理员操作审计日志写入（best-effort：独立会话，失败仅记日志，不影响主流程/主事务）。"""
import logging

import database
from models import AuditLog

_log = logging.getLogger("legal.audit")


def log_audit(admin_id, action: str, target: str = "", detail: str = "") -> None:
    try:
        db = database.SessionLocal()  # 动态取，便于测试 monkeypatch 重定向
        try:
            db.add(AuditLog(admin_id=admin_id, action=action, target=str(target or ""), detail=detail or ""))
            db.commit()
        finally:
            db.close()
    except Exception as e:  # 审计绝不影响业务
        _log.warning("audit write failed: %s", e)
