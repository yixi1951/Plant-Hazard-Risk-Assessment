# Plant Hazard Risk Assessment

> 个人项目 — 农作物病虫害 AI 智能识别与预警系统。
>
> 基于多任务深度学习，同时输出病害类别、严重程度分级与风险评分，并提供完整的 Web 演示界面与诊断报告。

[![CI](https://github.com/your-org/zhinong/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/zhinong/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.0%2B-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 目录

- [项目概述](#项目概述)
- [快速部署](#快速部署docker-compose-推荐)
- [快速开始（本地开发）](#快速开始)
- [使用流程](#使用流程)
- [项目结构](#项目结构)
- [模型架构](#模型架构)
- [API 文档](#api-文档)
- [实验结果](#实验结果)

---

## 项目概述

**核心能力：**
- **多任务联合学习** — 单模型同时预测病害种类（61 类）、严重程度（3 级）和风险评分
- **可解释诊断** — 支持 Grad-CAM 热力图可视化与结构化诊断报告
- **风险分级预警** — 自动分三级（高/中/低），指派责任人并生成 SOP 标准处置建议
- **生产级后端** — PostgreSQL + JWT 鉴权 + RBAC 角色控制 + 审计日志 + Excel 报告导出
- **Web 交互界面** — 浅色简洁仪表盘，支持本地图片上传、URL 抓取、拖拽上传与批量预测
- **灵活部署** — Flask 后端，支持 Docker Compose 一键部署、Nginx 反向代理

---

## 快速部署（Docker Compose 推荐）

### 前置条件

- Docker Engine 24+ 和 Docker Compose v2+
- 模型权重文件 `models/best_multitask_model.pth`（无模型时仅演示模式可用）

### 一键部署

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/zhinong.git
cd zhinong

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，至少修改 FLASK_SECRET_KEY、JWT_SECRET、ADMIN_PASSWORD

# 3. 启动所有服务
docker compose up -d

# 4. 验证
curl http://localhost:7860/healthz
```

访问 `http://localhost:7860` 即可使用。

### 详细部署说明

参见 [docs/DEPLOY.md](docs/DEPLOY.md) 包含：
- 手动部署步骤
- 环境变量完整参考
- PostgreSQL 配置与备份
- Nginx 反向代理 + HTTPS 配置
- 安全加固清单
- 监控与日志
- 常见故障排除

---

## 快速开始

### 1. 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 生成模拟数据集

```powershell
python scripts/generate_mock_dataset.py --output-dir data/mock_problem_b --num-classes 6 --train-per-class 80 --val-per-class 20
```

### 3. 训练模型

**多任务主模型（模拟数据快速验证）：**

```powershell
python train_multitask_model.py --data-dir data/mock_problem_b --sample-ratio 1.0 --epochs 5 --patience 2
```

**多任务主模型（PlantVillage 完整数据集）：**

```powershell
python train_multitask_model.py --dataset-mode plantvillage --data-dir data/plantvillage --sample-ratio 1.0 --epochs 15 --patience 5
```

**可识别具体病害名称的多任务模型：**

```powershell
python scripts/train_disease_multitask.py --train-dir data/plantvillage/train --val-dir data/plantvillage/val --save-path artifacts/disease_multitask.pth --epochs 15 --batch-size 32
```

切换模型推理：

```powershell
$env:MODEL_PATH='artifacts/disease_multitask.pth'
python app.py
```

### 4. 启动 Web 界面

```powershell
python app.py
```

访问 `http://localhost:7860` 即可使用。

---

## 使用流程

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 上传图片 | 支持拖拽上传、点击选择或粘贴图片 URL |
| 2 | 预览 | 确认图片内容无误 |
| 3 | 识别 | 模型输出病害名称、严重程度、风险评分 |
| 4 | 查看方案 | 阅读详细防治方案与复查时间线 |
| 5 | 批量预测 | 支持多张图片同时处理，或上传 ZIP 压缩包 |
| 6 | 获取报告 | 查看结果图、复制摘要、下载诊断报告 (JSON/PDF) |

### Kaggle 数据客户演示

```powershell
# 1) 在 Kaggle 下载 PlantVillage 等数据集后，切分为 train/val
py scripts/prepare_kaggle_dataset.py --source-dir D:\kaggle\plantvillage --output-dir data/kaggle_demo

# 2) 快速训练（3 epoch 即可用于演示）
py scripts/train_disease_multitask.py --train-dir data/kaggle_demo/train --val-dir data/kaggle_demo/val --epochs 3 --save-path artifacts/kaggle_demo.pth

# 3) 抽样推理，生成 7 条演示报告
py scripts/kaggle_client_demo.py --data-dir data/kaggle_demo/val --model-path artifacts/kaggle_demo.pth --samples 7 --output-dir demo_reports

# 4) 将报告复制到 Web 项目并启动
copy demo_reports\*.json reports\
py app.py
```

Web 界面也可直接点击 **「客户演示样例」** 卡片查看完整识别结果；启动服务时会自动注入 7 条演示诊断记录（无需模型）。

**客户演示（开箱即用）：**
- 打开首页即可看到 **玉米大斑病** 等 4 个样例识别结果与防治方案
- 概览统计、趋势图自动显示 7 条历史演示数据
- 设置 `DEMO_DEFAULT_RESULT=0` 可关闭首页默认样例

---

## API 文档

系统提供两套 API：

### 传统 API（`app.py` 内置）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/predict` | POST | 图片诊断（文件/URL/预览 token） |
| `/api/preview` | POST | 图片预览 |
| `/batch_predict` | POST | 批量预测 |
| `/api/diseases` | GET | 病害目录 |
| `/api/dashboard_stats` | GET | 仪表盘统计数据 |
| `/reports/<fname>` | GET | 下载诊断报告 |

### REST API v1（`/api/v1/`）

| 端点 | 方法 | 鉴权 | 说明 |
|------|------|------|------|
| `/api/v1/healthz` | GET | 否 | 健康检查 |
| `/api/v1/auth/login` | POST | 否 | 用户登录，返回 JWT |
| `/api/v1/auth/register` | POST | 否 | 用户注册 |
| `/api/v1/auth/me` | GET | 是 | 当前用户信息 |
| `/api/v1/assessments` | POST | 否 | 提交风险评估 |
| `/api/v1/assessments/<id>` | GET | 否 | 查询评估详情 |
| `/api/v1/assessments` | GET | 否 | 评估历史列表 |
| `/api/v1/assessments/export` | POST | 否 | 导出 Excel 报告 |
| `/api/v1/risk-rules` | GET | 否 | 风险规则列表 |

详细 API 文档见 Web 界面 `/api` 页面。

---

## 项目结构

```
.
├── app.py                              # Flask Web 主程序（传统路由）
├── app/                                # 生产级应用包
│   ├── __init__.py
│   ├── config.py                       # 统一配置管理（env → .env → 默认值）
│   ├── factory.py                      # Flask 应用工厂
│   ├── middleware.py                    # 请求 ID、结构化日志、安全头
│   ├── api/                            # REST API v1 蓝图
│   │   ├── __init__.py
│   │   ├── auth.py                     # 登录/注册/用户信息
│   │   ├── assessments.py              # 评估 CRUD + Excel 导出
│   │   ├── risk_rules.py               # 风险规则查询
│   │   └── health.py                   # 健康检查
│   ├── models/                         # SQLAlchemy ORM
│   │   ├── __init__.py
│   │   ├── database.py                 # 引擎与会话工厂
│   │   ├── user.py                     # 用户模型 (admin/assessor/readonly)
│   │   ├── assessment.py               # 评估记录模型
│   │   ├── risk_rule.py                # 风险规则 + 版本历史
│   │   ├── hazard_record.py            # 灾害记录模型
│   │   └── audit_log.py               # 审计日志模型
│   └── services/                       # 业务逻辑层
│       ├── __init__.py
│       ├── auth_service.py             # JWT 认证 + RBAC
│       ├── risk_service.py             # 风险评分 + SOP 生成
│       ├── risk_rules_config.py        # 三级风险规则 + SOP 模板
│       ├── audit_service.py            # 审计日志写入/查询
│       └── report_service.py           # Excel 报告导出
│
├── train_multitask_model.py            # 多任务联合训练入口
├── train_single_disease.py             # 单病害分类器训练
├── train_severity_gradcam.py           # 严重程度三分类 + GradCAM
├── few_shot_classification.py          # 少样本学习与可视化
├── risk_assessment.py                  # 多任务诊断与风险评估
├── plot_training_curves.py             # 训练曲线可视化
│
├── scripts/
│   ├── utils.py                        # 共享工具函数
│   ├── inference_utils.py              # 模型加载与推理引擎
│   ├── risk_score.py                   # 统一风险评分函数
│   ├── report_schema.py                # 诊断报告规范
│   ├── train_disease_multitask.py      # 带病害名称输出的多任务训练
│   ├── batch_infer.py                  # 批量推理脚本
│   ├── generate_mock_dataset.py        # 模拟数据集生成
│   ├── prepare_kaggle_dataset.py       # Kaggle 数据适配
│   ├── prepare_plantvillage.py         # PlantVillage 数据准备
│   ├── prepare_public_dataset.py       # 公开数据集处理
│   ├── export_onnx.py                  # ONNX 导出
│   ├── generate_report.py              # 诊断报告生成
│   ├── test_inference.py               # 推理测试脚本
│   └── __init__.py
│
├── templates/                          # Jinja2 页面模板
│   ├── index.html                      # 主界面（仪表盘 + ECharts）
│   ├── base.html                       # 基础布局骨架
│   └── about.html / team.html / faq.html / api.html
│
├── static/                             # 静态资源
│   ├── css/main.css                    # 全局样式
│   ├── js/main.js                      # 前端交互
│   └── vendor/                         # 第三方库 (echarts, bootstrap)
│
├── migrations/
│   └── 001_initial_schema.sql          # PostgreSQL 初始建表 + 种子数据
│
├── tests/
│   ├── test_risk_service.py            # 风险服务 17 个单元测试
│   ├── test_api_flask.py               # API 集成测试
│   ├── test_upload_security.py         # 上传安全测试
│   └── ...
│
├── docker-compose.yml                  # Docker Compose (PostgreSQL + App)
├── Dockerfile                          # 生产镜像
├── docker-entrypoint.sh                # 容器入口（DB 迁移 + Gunicorn）
├── .dockerignore
├── .env.example                        # 环境变量模板
├── .github/workflows/ci.yml           # GitHub Actions CI
├── setup.cfg                           # pytest + flake8 配置
│
├── data/                               # 数据集
├── reports/                            # 诊断报告输出
├── models/                             # 模型权重
├── logs/                               # Gunicorn 日志
├── tmp_uploads/                        # 临时上传文件
│
├── requirements.txt                    # 生产依赖
├── requirements-optional.txt           # 可选依赖
├── .gitignore
└── README.md
```

---

## 模型架构

```
输入图像 (128x128x3)
    ↓
MobileNetV2 Backbone (预训练特征提取)
    ↓
  AdaptiveAvgPool
    ↓
  CrossTaskAttention
   ↙            ↘
病害分类头     严重程度头
(61 classes)   (3 classes)
   ↓              ↓
病害名称 +    健康/一般/严重
风险评分      + 置信度
```

- **骨干网络**：MobileNetV2（轻量级，适合边缘部署）
- **跨任务注意力**（CrossTaskAttention）：让病害分类和严重程度分级共享特征并互相增强
- **输出**：病害类别概率、严重程度概率、综合风险评分

---

## 实验结果

| 指标 | 验证集表现 |
|------|-----------|
| Top-1 准确率 | ~74.7% (61 类) |
| 宏平均 F1 | ~0.70 |
| 严重程度分类 | ~85%+ |

输出产物：
- `models/best_multitask_model.pth` / `models/best_single_disease_model.pth` / `models/best_single_severity_model.pth`
- `models/best_multitask_model.onnx` — ONNX 导出格式
- `diagnostic_reports/` — 每张图片的详细诊断文本
- `grad_cam_visualizations/` — 模型关注区域可视化
- `reports/` — 结构化 JSON + PDF 诊断报告
- `docs/img/` — 训练曲线、风险分布、协同效应等可视化图片

---

## 演示亮点

- **拖拽上传**：支持单张拖拽与多文件批量拖拽
- **批量预测**：同时处理多张图片或 ZIP 压缩包，实时进度反馈
- **诊断报告**：每张图片自动生成 JSON + PDF 诊断报告
- **结果分享**：一键复制摘要、分享结果、下载标注图
- **ECharts 仪表盘**：风险趋势折线图、多维度统计图、筛选与 PNG 导出
- **批量导出**：CSV / JSON / 批量图表 PNG，便于客户现场带走数据

---

## 仪表盘与数据可视化

首页「趋势分析」与「诊断数据可视化」共用同一套报告聚合逻辑（`scripts/dashboard_analytics.py`）。

| 能力 | 说明 |
|------|------|
| **病害风险趋势** | 最近 7 条诊断的风险 / 处理建议 / 置信度折线 |
| **筛选** | 时间：全部 · 近 7 天 · 近 30 天；来源：全部 · 仅真实识别 · 仅演示 |
| **筛选联动** | 更改筛选后，**趋势图与下方 7 张统计图同步刷新**（`GET /api/dashboard_stats?days=&source=`） |
| **导出** | 「导出仪表盘 PNG」下载趋势 + 各统计图 |
| **批量图表** | 批量识别完成后展示成功/失败、风险区间、病种 Top、严重程度；可导出 CSV / JSON / PNG |

### 指标含义（答辩常用）

- **病害风险评分**（0–100%）：综合模型输出与严重程度的业务风险指数，越高越需尽快防治。
- **识别置信度**：模型对当前预测（尤其严重程度）的确信程度，与风险分相互独立；低置信度建议人工复核。
- **处理建议指数**：由风险分推导的处置紧迫度启发值（非独立模型头）。
- **紧急程度**：防治方案引擎根据病害与严重程度给出的「低 / 中 / 高」执行优先级。

### 诊断报告 JSON 规范（v1）

写入 `reports/*.json` 时统一经 `scripts/report_schema.py`：

| 字段 | 说明 |
|------|------|
| `schema_version` | 当前为 `1` |
| `generated_at` | UTC 时间戳，如 `20250612T120000Z` |
| `demo` | 是否演示数据（用于「仅演示」筛选） |
| `source` | `web_predict` / `demo_seed` / `batch_predict` 等 |
| `meta` | 含 `disease_name`, `crop`, `severity`, `disease_risk_percent`, `severity_confidence`, `urgency` 等 |
| `probabilities` | 严重程度三档概率 |
| `treatment_plan` | 防治方案详情 |
| `batch_id`, `input_filename` | 批量识别可选字段 |

### 模型能力展示要点

- **多任务**：一次前向同时得到病害相关输出、严重程度与风险建议（见「模型架构」）。
- **MC Dropout**：上传区可勾选「不确定性分析」，结果区展示风险标准差。
- **知识库**：`/api/diseases` 返回 60+ 病种防治条目，与识别结果中的 `treatment_plan` 一致。

API 细节见 Web 内 **API 文档** 页（`/api`）或下文接口说明。

---

## 部署

```powershell
# 虚拟环境（开发测试）
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py

# Gunicorn（生产环境 — Linux/WSL）
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:7860 app:app

# Docker
docker build -t plant-hazard:latest .
docker run -p 7860:7860 plant-hazard:latest
```

---

> 本项目为个人学习与展示项目，数据来源于 PlantVillage 公开数据集及竞赛模拟数据。
