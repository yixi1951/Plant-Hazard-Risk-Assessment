"""
统一配置管理模块
层级: env > .env > defaults
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional


def _load_dotenv(dotenv_path: Optional[str] = None) -> None:
    """手动加载 .env 文件（不依赖 python-dotenv 包）。"""
    if dotenv_path is None:
        dotenv_path = os.path.join(os.getcwd(), ".env")
    if not os.path.isfile(dotenv_path):
        return
    with open(dotenv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and not os.environ.get(key):
                os.environ.setdefault(key, value)


_load_dotenv()


def str_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def bool_env(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, str(default)).lower().strip()
    return val in ("1", "true", "yes", "on")


def int_env(key: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


# ── 数据库 ──────────────────────────────────────────────────
DATABASE_URL: str = str_env(
    "DATABASE_URL",
    "sqlite:///data/zhinong.db",
)

# ── Flask ───────────────────────────────────────────────────
SECRET_KEY: str = str_env("FLASK_SECRET_KEY", "dev-change-me-in-production")
APP_HOST: str = str_env("APP_HOST", "0.0.0.0")
APP_PORT: int = int_env("APP_PORT", 7860)
DEBUG: bool = bool_env("DEBUG", False)

# ── JWT ─────────────────────────────────────────────────────
JWT_SECRET: str = str_env("JWT_SECRET", SECRET_KEY)
JWT_ACCESS_TOKEN_EXPIRES: int = int_env("JWT_ACCESS_TOKEN_EXPIRES", 3600)

# ── 模型 ────────────────────────────────────────────────────
MODEL_PATH: str = str_env("MODEL_PATH", "models/best_multitask_model.pth")

# ── 上传 ────────────────────────────────────────────────────
MAX_UPLOAD_MB: int = int_env("MAX_UPLOAD_MB", 200)
MAX_CONTENT_LENGTH: int = MAX_UPLOAD_MB * 1024 * 1024

# ── Redis ───────────────────────────────────────────────────
REDIS_URL: str = str_env("REDIS_URL", "")

# ── Sentry ──────────────────────────────────────────────────
SENTRY_DSN: str = str_env("SENTRY_DSN", "")

# ── 日志 ────────────────────────────────────────────────────
LOG_LEVEL: str = str_env("LOG_LEVEL", "INFO")

# ── 管理员初始账号 ──────────────────────────────────────────
ADMIN_EMAIL: str = str_env("ADMIN_EMAIL", "admin@zhinong.local")
ADMIN_PASSWORD: str = str_env("ADMIN_PASSWORD", "Admin123!")

# ── 路径 ────────────────────────────────────────────────────
BASE_DIR: Path = Path(os.getcwd())
REPORTS_DIR: Path = BASE_DIR / "reports"
LOGS_DIR: Path = BASE_DIR / "logs"
TMP_UPLOADS_DIR: Path = BASE_DIR / "tmp_uploads"


def to_dict() -> Dict[str, Any]:
    """导出全部配置为 dict（用于调试/健康检查）。"""
    return {k: v for k, v in globals().items()
            if k.isupper() and not k.startswith("_")}
