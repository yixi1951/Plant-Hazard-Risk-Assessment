#!/bin/sh
# 智农 Docker 入口脚本
# 负责: 数据库迁移、数据目录初始化、应用启动
set -e

echo "=== 智农 · 容器启动 ==="

# ── 确保必要目录 ──
mkdir -p /app/reports /app/logs /app/data /app/tmp_uploads

# ── 等待数据库就绪（PostgreSQL） ──
if echo "$DATABASE_URL" | grep -q "postgresql"; then
    echo "等待 PostgreSQL 就绪..."
    # 从 DATABASE_URL 提取主机和端口
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@\([^:/]*\).*|\2|p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@\([^:/]*\).*|\1|p')
    DB_PORT=${DB_PORT:-5432}
    DB_HOST=${DB_HOST:-db}

    for i in $(seq 1 30); do
        if nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
            echo "PostgreSQL 已就绪"
            break
        fi
        echo "等待数据库 ($i/30)..."
        sleep 1
    done
fi

# ── 数据库迁移 ──
if echo "$DATABASE_URL" | grep -q "postgresql"; then
    echo "运行数据库迁移..."
    if [ -f /app/migrations/001_initial_schema.sql ]; then
        # 提取连接信息运行 SQL
        PGPASSWORD=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
        DB_USER=$(echo "$DATABASE_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
        DB_NAME=$(echo "$DATABASE_URL" | sed -n 's|.*/\([^?]*\)$|\1|p')
        export PGPASSWORD
        psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f /app/migrations/001_initial_schema.sql 2>/dev/null || echo "迁移脚本已执行（可忽略重复错误）"
    fi
else
    echo "使用 SQLite，由 SQLAlchemy 自动建表"
fi

echo "=== 启动应用 ==="

# ── 启动 Gunicorn ──
exec gunicorn \
    -w "${GUNICORN_WORKERS:-1}" \
    -b "0.0.0.0:${APP_PORT:-7860}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile /app/logs/access.log \
    --error-logfile /app/logs/error.log \
    --log-level "${LOG_LEVEL:-INFO}" \
    "wsgi:app"
