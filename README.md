# Plant Hazard Risk Assessment

> 个人项目 — 农作物病虫害 AI 智能识别与预警系统。
>
> 基于多任务深度学习，同时输出病害类别、严重程度分级与风险评分，并提供完整的 Web 演示界面与诊断报告。

---

## 项目概述

本项目是一个端到端的农作物病害智能诊断系统，涵盖从数据准备、模型训练到 Web 部署的完整流程。

**核心能力：**
- **多任务联合学习** — 单模型同时预测病害种类（61 类）、严重程度（3 级）和风险评分
- **可解释诊断** — 支持 Grad-CAM 热力图可视化与结构化诊断报告
- **Web 交互界面** — 暗色主题仪表盘，支持本地图片上传、URL 抓取、拖拽上传与批量预测
- **灵活部署** — Flask 后端，默认监听 `0.0.0.0:7860`，局域网内即可访问

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
| 4 | 批量预测 | 支持多张图片同时处理，或上传 ZIP 压缩包 |
| 5 | 获取报告 | 查看结果图、复制摘要、下载诊断报告 (JSON/PDF) |

---

## 项目结构

```
.
├── app.py                              # Flask Web 主程序
├── train_multitask_model.py            # 多任务联合训练入口
├── train_single_disease.py             # 单病害分类器训练
├── train_severity_gradcam.py           # 严重程度三分类 + GradCAM
├── few_shot_classification.py          # 少样本学习与可视化
├── risk_assessment.py                  # 多任务诊断与风险评估
├── plot_training_curves.py             # 训练曲线可视化
│
├── scripts/
│   ├── utils.py                        # 共享工具函数（病害字典、数据查找、标注解析）
│   ├── inference_utils.py              # 模型加载与推理引擎
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
│   ├── index.html                      # 主界面（暗色仪表盘 + ECharts）
│   ├── base.html                       # 基础布局
│   ├── about.html / team.html / faq.html / api.html
│
├── static/
│   ├── css/main.css                    # 全局样式（玻璃拟态 + 暗色主题）
│   ├── js/main.js                      # 前端交互逻辑
│   └── favicon.svg
│
├── data/                               # 数据集
│   ├── mock_problem_b/                 # 模拟验证数据
│   ├── plantvillage/                   # PlantVillage 数据
│   └── raw/                            # 原始数据
│
├── reports/                            # 诊断报告输出目录
├── diagnostic_reports/                 # 详细诊断文本报告
├── grad_cam_visualizations/            # Grad-CAM 热力图
│
├── requirements.txt
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
- `best_multitask_model.pth` / `best_single_disease_model.pth` / `best_single_severity_model.pth`
- `diagnostic_reports/` — 每张图片的详细诊断文本
- `grad_cam_visualizations/` — 模型关注区域可视化
- `reports/` — 结构化 JSON + PDF 诊断报告

---

## 演示亮点

- **拖拽上传**：支持单张拖拽与多文件批量拖拽
- **批量预测**：同时处理多张图片或 ZIP 压缩包，实时进度反馈
- **诊断报告**：每张图片自动生成 JSON + PDF 诊断报告
- **结果分享**：一键复制摘要、分享结果、下载标注图
- **ECharts 仪表盘**：风险趋势折线图、风险仪表盘、信心度分布

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
