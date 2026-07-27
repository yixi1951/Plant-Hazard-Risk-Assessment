"""
根级运维端点 — 存活/就绪/版本探测。
不依附于 /api/v1 前缀，注册时 url_prefix=""。
"""
from __future__ import annotations

import os
import sys

from flask import Blueprint, jsonify
from sqlalchemy import text

root_bp = Blueprint("root", __name__)


@root_bp.route("/healthz")
def healthz_liveness():
    """存活探针 — 纯粹返回 200，不依赖任何外部服务。"""
    return "OK", 200


@root_bp.route("/readyz")
def readyz_readiness():
    """就绪探针 — 检查数据库连接。"""
    try:
        from app.models.database import get_db_session
        with get_db_session() as session:
            session.execute(text("SELECT 1"))
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as exc:
        return jsonify({"status": "unhealthy", "database": str(exc)}), 503


@root_bp.route("/version")
def version_info():
    """版本信息 — commit SHA、构建时间、Python 版本。"""
    commit_sha = os.environ.get("COMMIT_SHA", "")
    build_time = os.environ.get("BUILD_TIME", "")
    return jsonify({
        "app": "zhinong",
        "version": "1.0.0",
        "commit": commit_sha,
        "build_time": build_time,
        "python": sys.version.split()[0],
    })
