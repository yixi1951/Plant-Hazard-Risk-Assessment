"""
智农 · 唯一生产 WSGI 入口
=========================
本地开发与 Docker 容器均通过此文件启动。
    $ gunicorn wsgi:app
    $ python wsgi.py                    # 开发模式

通过 importlib 加载 app.py（因 app/ 包名与 app.py 同名冲突）。
"""
from __future__ import annotations

import importlib.util
import logging
import os
import signal
import sys

_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _APP_ROOT)

# ── 从 app.py 加载 Flask 应用实例 ───────────────────────
_spec = importlib.util.spec_from_file_location(
    "zhinong_app_main",
    os.path.join(_APP_ROOT, "app.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
app = _mod.app

logger = logging.getLogger("zhinong.wsgi")


def graceful_shutdown(*args):  # noqa: ARG001
    """接收 SIGTERM/SIGINT 时优雅关闭。"""
    logger.info("Received shutdown signal, exiting gracefully...")
    sys.exit(0)


signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)

if __name__ == "__main__":
    host = os.environ.get("APP_HOST", "0.0.0.0")
    port = int(os.environ.get("APP_PORT", "7860"))
    debug = os.environ.get("DEBUG", "0").lower() in ("1", "true", "yes")
    logger.info("Starting dev server on %s:%s (debug=%s)", host, port, debug)
    app.run(host=host, port=port, debug=debug)

__all__ = ["app"]
