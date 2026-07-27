"""审计日志服务。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from app.models.audit_log import AuditLog
from app.models.database import get_db_session

logger = logging.getLogger("zhinong.audit_service")


def log_action(
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Optional[int]:
    """写入审计日志。"""
    try:
        with get_db_session() as session:
            log = AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                detail=json.dumps(detail, ensure_ascii=False) if detail else None,
                ip_address=ip_address,
                request_id=request_id,
            )
            session.add(log)
            session.flush()
            return log.id
    except Exception as exc:
        logger.warning("Failed to write audit log: %s", exc)
        return None


def query_logs(
    page: int = 1,
    per_page: int = 50,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[int] = None,
) -> tuple:
    """分页查询审计日志。"""
    try:
        with get_db_session() as session:
            query = session.query(AuditLog)
            if action:
                query = query.filter(AuditLog.action == action)
            if resource_type:
                query = query.filter(AuditLog.resource_type == resource_type)
            if user_id is not None:
                query = query.filter(AuditLog.user_id == user_id)

            total = query.count()
            query = query.order_by(AuditLog.created_at.desc())
            query = query.offset((page - 1) * per_page).limit(per_page)
            items = [log.to_dict() for log in query.all()]
        return items, total
    except Exception as exc:
        logger.warning("Failed to query audit logs: %s", exc)
        return [], 0
