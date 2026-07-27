"""认证相关 API。"""
from __future__ import annotations

import logging

from flask import jsonify, request

from app.api import api_bp
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_user,
    decode_access_token,
)
from app.services.audit_service import log_action

logger = logging.getLogger("zhinong.api.auth")


@api_bp.route("/auth/login", methods=["POST"])
def login():
    """用户登录。
    POST body: { "username": "...", "password": "..." }
    Returns: { "ok": true, "access_token": "...", "user": {...} }
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"ok": False, "error": "用户名和密码不能为空"}), 400

    user = authenticate_user(username, password)
    if not user:
        log_action(
            action="login_failed",
            resource_type="user",
            resource_id=username,
            ip_address=request.remote_addr,
        )
        return jsonify({"ok": False, "error": "用户名或密码错误"}), 401

    token = create_access_token(user)
    log_action(
        action="login",
        resource_type="user",
        resource_id=str(user.id),
        user_id=user.id,
        username=user.username,
        ip_address=request.remote_addr,
    )

    return jsonify({
        "ok": True,
        "access_token": token,
        "user": user.to_dict(),
    })


@api_bp.route("/auth/register", methods=["POST"])
def register():
    """用户注册（仅管理员可调用，或开放注册）。"""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not email or not password:
        return jsonify({"ok": False, "error": "用户名、邮箱和密码不能为空"}), 400

    if len(password) < 6:
        return jsonify({"ok": False, "error": "密码长度至少 6 位"}), 400

    user = create_user(username=username, email=email, password=password)
    if not user:
        return jsonify({"ok": False, "error": "用户名或邮箱已存在"}), 409

    log_action(
        action="register",
        resource_type="user",
        resource_id=str(user.id),
        username=username,
        ip_address=request.remote_addr,
    )

    return jsonify({"ok": True, "user": user.to_dict()}), 201


@api_bp.route("/auth/me", methods=["GET"])
def me():
    """获取当前用户信息（需 Authorization header）。"""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        return jsonify({"ok": False, "error": "未提供认证令牌"}), 401

    payload = decode_access_token(token)
    if not payload:
        return jsonify({"ok": False, "error": "令牌无效或已过期"}), 401

    from app.services.auth_service import get_user_by_id
    user = get_user_by_id(int(payload["sub"]))
    if not user:
        return jsonify({"ok": False, "error": "用户不存在"}), 404

    return jsonify({"ok": True, "user": user.to_dict()})
