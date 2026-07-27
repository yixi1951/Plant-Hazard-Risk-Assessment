"""健康检查 API。"""
from __future__ import annotations

from flask import jsonify
from sqlalchemy import text

from app.api import api_bp


@api_bp.route("/healthz", methods=["GET"])
def healthz():
    """健康检查接口，用于 Docker / K8s / 负载均衡探测。"""
    try:
        from app.models.database import get_db_session
        with get_db_session() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return jsonify({"status": "unhealthy", "database": "disconnected"}), 503

    return jsonify({
        "status": "healthy",
        "app": "zhinong",
        "version": "1.0.0",
    })
