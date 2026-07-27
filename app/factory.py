"""
Flask 应用工厂。
生产环境和开发环境共用统一入口。
"""
from __future__ import annotations

import logging
import sys

from flask import Flask

from app.config import (
    BASE_DIR,
    DEBUG,
    LOG_LEVEL,
    LOGS_DIR,
    MAX_CONTENT_LENGTH,
    REPORTS_DIR,
    SECRET_KEY,
    SENTRY_DSN,
    TMP_UPLOADS_DIR,
)
from app.middleware import register_middleware


def create_app() -> Flask:
    """创建并配置 Flask 应用实例。"""
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )

    # ── 基础配置 ────────────────────────────────────────
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    app.config["DEBUG"] = DEBUG

    # ── 日志 ────────────────────────────────────────────
    _setup_logging()

    # ── 中间件 ──────────────────────────────────────────
    register_middleware(app)

    # ── 数据库 ──────────────────────────────────────────
    _init_database(app)

    # ── 蓝图 ────────────────────────────────────────────
    _register_blueprints(app)

    # ── 确保目录 ────────────────────────────────────────
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    TMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Sentry ──────────────────────────────────────────
    if SENTRY_DSN:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            sentry_sdk.init(
                dsn=SENTRY_DSN,
                integrations=[FlaskIntegration()],
                traces_sample_rate=0.5,
            )
            logging.getLogger("zhinong").info("Sentry initialized")
        except ImportError:
            logging.getLogger("zhinong").warning("sentry-sdk not installed, skipping")

    # ── 管理员初始化 ────────────────────────────────────
    try:
        from app.services.auth_service import init_admin_user
        init_admin_user()
    except Exception as exc:
        logging.getLogger("zhinong").warning("Admin init skipped: %s", exc)

    logging.getLogger("zhinong").info("✅ App created (debug=%s)", DEBUG)
    return app


def _setup_logging() -> None:
    """配置统一日志格式。"""
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    # 保证 logs 目录存在
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s] [%(request_id)s] %(message)s"
    )

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # 文件 handler
    file_handler = logging.FileHandler(
        str(LOGS_DIR / "zhinong.log"), encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # 根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # 清除默认 handler 避免重复
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # 应用 logger
    app_logger = logging.getLogger("zhinong")
    app_logger.setLevel(log_level)

    # werkzeug logger
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def _init_database(app: Flask) -> None:
    """初始化数据库。"""
    from app.models.database import init_db
    try:
        init_db()
        logging.getLogger("zhinong").info("Database initialized")
    except Exception as exc:
        logging.getLogger("zhinong").warning(
            "Database init failed (will retry on first request): %s", exc
        )


def _register_blueprints(app: Flask) -> None:
    """注册所有蓝图。"""
    from app.api import api_bp
    app.register_blueprint(api_bp)
    logging.getLogger("zhinong").debug("Blueprints registered: %s", api_bp.name)
