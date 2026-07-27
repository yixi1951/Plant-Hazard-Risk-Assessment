"""审计日志查询 API。"""
from __future__ import annotations

import logging

from flask import jsonify, request

from app.api import api_bp
from app.services.audit_service import query_logs
from app.services.auth_service import decode_access_token

logger = logging.getLogger("zhinong.api.audit")


def _require_admin():
    """验证请求是否为 admin 角色，返回 user_id 或中断。"""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    if payload.get("role") != "admin":
        return None
    return int(payload["sub"])


@api_bp.route("/audit-logs", methods=["GET"])
def list_audit_logs():
    """查询审计日志（需 admin 角色）。
    Query params: page, per_page, action, resource_type
    """
    user_id = _require_admin()
    if not user_id:
        return jsonify({"ok": False, "error": "需要 admin 权限"}), 403

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    action = request.args.get("action")
    resource_type = request.args.get("resource_type")

    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20

    items, total = query_logs(
        page=page,
        per_page=per_page,
        action=action,
        resource_type=resource_type,
    )

    return jsonify({
        "ok": True,
        "logs": items,
        "page": page,
        "per_page": per_page,
        "total": total,
    })
