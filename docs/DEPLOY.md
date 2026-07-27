# 智农 · 部署指南

> 农作物病虫害 AI 智能识别与预警系统 — 生产部署文档

---

## 目录

1. [环境要求](#1-环境要求)
2. [快速部署（Docker Compose）](#2-快速部署docker-compose)
3. [手动部署](#3-手动部署)
4. [环境变量参考](#4-环境变量参考)
5. [数据库](#5-数据库)
6. [Nginx 反向代理配置](#6-nginx-反向代理配置)
7. [安全加固](#7-安全加固)
8. [监控与日志](#8-监控与日志)
9. [常见问题](#9-常见问题)

---

## 1. 环境要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 10 GB | 50 GB+（存储报告和日志） |
| Python | 3.10+ | 3.11 / 3.12 |
| Docker | 24+ | 24+（使用 Docker 部署时） |

**注意**: 模型推理在 CPU 模式下约需 2-4 GB 内存。如需 GPU 支持，请参考 [GPU 部署](#gpu-support) 章节。

---

## 2. 快速部署（Docker Compose）

### 2.1 前置条件

- Docker Engine 24+
- Docker Compose v2+
- 模型权重文件 `models/best_multitask_model.pth`（若无则使用演示模式）

### 2.2 部署步骤

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/zhinong.git
cd zhinong

# 2. 配置环境变量（编辑 .env 文件）
cp .env.example .env
# 编辑 .env，至少修改以下值:
#   FLASK_SECRET_KEY=<随机字符串>
#   JWT_SECRET=<随机字符串>
#   ADMIN_PASSWORD=<强密码>

# 3. 放置模型文件
# 将 best_multitask_model.pth 放入 models/ 目录

# 4. 启动服务
docker compose up -d

# 5. 验证
curl http://localhost:7860/healthz
# 应返回 {"status":"ok","database":"connected"}

# 6. 查看日志
docker compose logs -f zhinong
```

### 2.3 访问

- Web 界面: `http://localhost:7860`
- API 文档: `http://localhost:7860/api`
- 健康检查: `http://localhost:7860/healthz`

### 2.4 常用命令

```bash
# 停止服务
docker compose down

# 停止并删除数据卷（会丢失数据库）
docker compose down -v

# 重新构建镜像
docker compose build --no-cache zhinong

# 查看资源使用
docker stats

# 进入容器
docker compose exec zhinong /bin/bash
```

---

## 3. 手动部署

### 3.1 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

### 3.2 配置环境

```bash
cp .env.example .env
# 编辑 .env 中的配置值
```

### 3.3 初始化数据库

```bash
# SQLite（自动创建）:
# 设置 DATABASE_URL=sqlite:///data/zhinong.db

# PostgreSQL:
# 先创建数据库:
createdb zhinong
# 运行迁移:
psql -U zhinong -d zhinong -f migrations/001_initial_schema.sql
```

### 3.4 启动

```bash
# 开发模式
python app.py

# 生产模式（推荐 Gunicorn）
gunicorn -w 2 -b 0.0.0.0:7860 --timeout 120 --access-logfile logs/access.log app:app
```

---

## 4. 环境变量参考

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `FLASK_SECRET_KEY` | `change-me-in-production` | Flask 密钥，**必须修改** |
| `APP_HOST` | `0.0.0.0` | 监听地址 |
| `APP_PORT` | `7860` | 监听端口 |
| `DATABASE_URL` | `sqlite:///data/zhinong.db` | 数据库连接串 |
| `JWT_SECRET` | `change-me-jwt-secret` | JWT 签名密钥，**必须修改** |
| `JWT_ACCESS_TOKEN_EXPIRES` | `3600` | Token 过期时间（秒） |
| `ADMIN_EMAIL` | `admin@zhinong.local` | 初始管理员邮箱 |
| `ADMIN_PASSWORD` | `Admin123!` | 初始管理员密码，**必须修改** |
| `MODEL_PATH` | `models/best_multitask_model.pth` | 模型权重路径 |
| `MAX_UPLOAD_MB` | `200` | 上传文件大小限制（MB） |
| `LOG_LEVEL` | `INFO` | 日志级别 (DEBUG/INFO/WARNING/ERROR) |
| `SENTRY_DSN` | 空 | Sentry DSN（可选错误监控） |
| `REDIS_URL` | 空 | Redis 连接串（可选缓存） |

---

## 5. 数据库

### 5.1 支持

| 数据库 | 支持 | 说明 |
|--------|------|------|
| SQLite | ✅ | 开发/单机；自动建表 |
| PostgreSQL | ✅ | 生产推荐；需手动迁移或通过入口脚本 |

### 5.2 切换数据库

```bash
# SQLite（单机开发）
DATABASE_URL=sqlite:///data/zhinong.db

# PostgreSQL（生产）
DATABASE_URL=postgresql://user:password@host:5432/zhinong
```

### 5.3 数据库迁移

```bash
# 手动运行迁移
psql -U zhinong -d zhinong -f migrations/001_initial_schema.sql

# Docker 环境下自动运行（通过 docker-entrypoint.sh）
```

### 5.4 备份

```bash
# PostgreSQL 备份
pg_dump -U zhinong zhinong > backup_$(date +%Y%m%d).sql

# SQLite 备份
cp data/zhinong.db data/zhinong.db.backup
```

---

## 6. Nginx 反向代理配置

```nginx
server {
    listen 80;
    server_name zhinong.example.com;

    # 上传大小限制
    client_max_body_size 200M;

    location / {
        proxy_pass http://127.0.0.1:7860;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持（如需）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /static/ {
        alias /path/to/zhinong/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # 限制 /api/v1 访问（可选 IP 白名单）
    location /api/v1/ {
        allow 10.0.0.0/8;
        allow 172.16.0.0/12;
        allow 192.168.0.0/16;
        deny all;

        proxy_pass http://127.0.0.1:7860;
    }
}
```

### HTTPS (Let's Encrypt)

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d zhinong.example.com
```

---

## 7. 安全加固

### 7.1 必需操作

1. **修改所有默认密钥**
   ```bash
   # 生成随机密钥
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   更新 `.env` 中的 `FLASK_SECRET_KEY` 和 `JWT_SECRET`

2. **修改管理员密码**
   更新 `.env` 中的 `ADMIN_PASSWORD`

3. **关闭调试模式**
   确保 `DEBUG=false`

### 7.2 网络安全

- 使用 Nginx 反向代理（见上节）
- 启用 HTTPS（Let's Encrypt）
- 配置防火墙: `ufw allow 443/tcp && ufw allow 22/tcp`
- API 端点限制 IP 白名单
- JWT token 设置合理过期时间

### 7.3 文件上传安全

系统已内置以下防护：
- ✅ 图片内容签名检查（魔数检测）
- ✅ 拒绝内网 URL 请求（SSRF 防护）
- ✅ 文件名合法性校验
- ✅ 上传大小限制（`MAX_UPLOAD_MB`）
- ✅ 临时文件自动清理（1 小时过期）

---

## 8. 监控与日志

### 8.1 日志位置

```bash
# 应用日志
logs/                          # Docker 挂载目录
  access.log                   # Gunicorn 访问日志
  error.log                    # Gunicorn 错误日志

# 报告存储
reports/                       # 诊断报告 JSON/PDF
```

### 8.2 Sentry 错误监控（可选）

在 `.env` 中设置:
```
SENTRY_DSN=https://your-dsn@sentry.io/123456
```

### 8.3 健康检查

```
GET /healthz
# 返回: {"status":"ok","database":"connected","timestamp":"..."}
```

### 8.4 Docker 监控

```bash
# 实时资源
docker stats

# 容器日志
docker compose logs -f --tail=100 zhinong
```

---

## 9. 常见问题

### Q: 启动后页面能打开但识别报错？

A: 检查模型文件 `models/best_multitask_model.pth` 是否存在且完整。无模型时系统仅演示模式可用。

### Q: PostgreSQL 连接失败？

```bash
# 检查数据库是否就绪
docker compose exec db pg_isready -U zhinong

# 查看数据库日志
docker compose logs db
```

### Q: 上传图片报 "图片太大"？

调整环境变量 `MAX_UPLOAD_MB=500`（默认 200 MB）。

### Q: 如何开启 GPU 推理？

当前版本仅支持 CPU 推理。GPU 支持计划在后续版本中加入。

### Q: 审计日志在哪里查看？

审计日志存储在数据库 `audit_logs` 表中，可通过 API `GET /api/v1/audit-logs` 查询。

---

> 更多问题请提交 [GitHub Issues](https://github.com/your-org/zhinong/issues)
