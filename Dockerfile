# 智农 Web + PyTorch 推理（CPU）
# 生产版 — 支持 PostgreSQL + REST API + 审计日志 + Excel 导出
FROM python:3.11-slim-bookworm

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    netcat-openbsd \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 运行时目录
RUN mkdir -p tmp_uploads reports logs data && \
    chmod +x docker-entrypoint.sh

# 环境变量默认值
ENV APP_HOST=0.0.0.0 \
    APP_PORT=7860 \
    GUNICORN_WORKERS=1 \
    GUNICORN_TIMEOUT=120 \
    MODEL_PATH=/app/models/best_multitask_model.pth \
    FLASK_SECRET_KEY=change-me-in-production \
    DATABASE_URL=sqlite:///data/zhinong.db \
    JWT_SECRET=change-me-jwt-secret \
    JWT_ACCESS_TOKEN_EXPIRES=3600 \
    LOG_LEVEL=INFO \
    MAX_UPLOAD_MB=200

EXPOSE 7860

# 使用入口脚本（负责 DB 迁移、目录初始化、Gunicorn 启动）
ENTRYPOINT ["/app/docker-entrypoint.sh"]