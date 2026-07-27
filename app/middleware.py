"""Flask 中间件：请求日志、安全头、统一错误处理。"""
from __future__ import annotations

import logging
import uuid

from flask import Flask, g, jsonify, request

logger = logging.getLogger("zhinong.middleware")


def register_middleware(app: Flask) -> None:
    """注册所有中间件。"""

    @app.before_request
    def assign_request_id():
        g.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]

    @app.before_request
    def log_request():
        logger.info(
            "[%s] %s %s from %s | content_length=%s | content_type=%s",
            g.get("request_id", "-"),
            request.method,
            request.path,
            request.remote_addr,
            request.content_length,
            request.content_type,
        )

    @app.after_request
    def add_security_headers(response):
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        response.headers["X-Request-Id"] = g.get("request_id", "-")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"ok": False, "error": "接口不存在"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"ok": False, "error": "请求方法不允许"}), 405

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"ok": False, "error": "上传文件太大"}), 413

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("Internal server error: %s", e)
        return jsonify({"ok": False, "error": "服务器内部错误"}), 500
