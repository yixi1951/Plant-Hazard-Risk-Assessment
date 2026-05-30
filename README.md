# Agricultural Disease Diagnosis Project

面向农业病害识别与风险评估的个人项目，已将数学建模论文代码整理为可复现、可演示、可扩展的完整工程。当前版本已完成训练、评估、可解释分析、图片上传演示界面与 GitHub 发布，适合作为答辩与项目展示版本。

## 封面摘要

**项目名称**：农业病害智能诊断与风险评估

**项目定位**：基于深度学习的叶片病害识别、多任务严重程度分级与可解释诊断系统

**核心亮点**：

- 多任务联合学习：同时输出病害类别与严重程度分级。
- 可解释诊断：提供诊断报告、Grad-CAM 热力图和风险评估结果。
- 可演示界面：支持图片上传后直接返回预测结果与风险反馈。
- 可复现实验：支持模拟数据集与 PlantVillage 数据集两种运行方式。

**项目成果**：

- 训练流程已验证可运行。
- 诊断报告与可视化结果已生成。
- 上传推理 UI 已实现并可本地演示。
- 代码已推送到 GitHub，可直接用于汇报展示。

**答辩建议展示顺序**：问题定义 -> 数据集 -> 模型结构 -> 实验结果 -> 可解释分析 -> UI 演示。

## 项目内容

- `q1.py`: 病害分类基础模型
- `q1new.py`: 多任务联合学习主入口，支持命令行指定数据目录
- `q2.py`: 少样本学习与可视化
- `q3.py`: 严重程度三分类与 Grad-CAM 可视化
- `q4.py`: 多任务诊断与风险评估
- `app.py`: 图片上传评估界面，本地即可演示
- `scripts/generate_mock_dataset.py`: 在原始赛题数据丢失时，生成可运行的模拟测试数据集

## 目录说明

- `data/`: 测试数据与后续扩展数据
- `scripts/`: 辅助脚本
- `diagnostic_reports/`: 诊断报告输出
- `grad_cam_visualizations/`: 可解释性图像输出
- `few_shot_visualizations/`: 少样本实验可视化输出

## 快速开始

### 1. 创建虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

### 3. 生成测试数据集

```powershell
python scripts/generate_mock_dataset.py --output-dir data/mock_problem_b --num-classes 6 --train-per-class 80 --val-per-class 20
```

### 4. 训练主模型（模拟数据）

```powershell
python q1new.py --data-dir data/mock_problem_b --sample-ratio 1.0 --epochs 5 --patience 2
```

### 4.1 训练主模型（PlantVillage，推荐用于最终展示）

如果你已经准备好 PlantVillage 数据并切分到本地目录，可以直接训练：

```powershell
python q1new.py --dataset-mode plantvillage --data-dir C:\Users\ASUS\Desktop\新建文件夹\data\plantvillage --sample-ratio 1.0 --epochs 15 --patience 5
```

当前项目在 Windows 下已经验证可跑通，训练时建议把数据放在本机 C 盘或本地 SSD，避免外接盘掉盘导致中断。

### 5. 训练主模型（PlantVillage）

如果你下载的是 PlantVillage 原始目录结构，可以先切分成训练/验证集：

```powershell
python scripts/prepare_plantvillage.py --source-dir <你的PlantVillage原始目录> --output-dir data/plantvillage --train-ratio 0.8
```

整理后会得到：

- `data/plantvillage/train/<class_name>/*.jpg`
- `data/plantvillage/val/<class_name>/*.jpg`

然后执行：

```powershell
python q1new.py --dataset-mode plantvillage --data-dir data/plantvillage --sample-ratio 1.0 --epochs 5 --patience 2
```

### 6. 启动图片上传评估界面

```powershell
python app.py
```

默认情况下，页面会监听 `0.0.0.0:7860`，同一局域网内的其他设备可以通过你这台电脑的局域网 IP 访问它。若只想本机访问，可以显式设置：

```powershell
$env:APP_HOST='127.0.0.1'
$env:APP_PORT='7860'
python app.py
```

如果你想把它真正放到公网给更多人使用，建议部署到 VPS、云服务器或带公网地址的平台，然后把 `APP_HOST` 保持为 `0.0.0.0`，再通过反向代理或平台提供的域名对外访问。

如果你在 GPU conda 环境里运行，可以用：

```powershell
$conda = Join-Path $env:USERPROFILE 'Miniconda3\Scripts\conda.exe'
& $conda run -p D:\conda_envs\torch-gpu python app.py
```

### 7. 命令行测试单张图片

```powershell
python scripts/test_inference.py --data-dir data/plantvillage/val
```

如果指定图片：

```powershell
python scripts/test_inference.py --image <你的图片路径>
```

## 交付状态

- 训练流程已验证可运行，包括多任务训练、单任务对比、诊断报告、Grad-CAM 和风险评估。
- 图片上传评估界面已可本地演示。
- 代码已推送到 GitHub，可直接作为个人项目展示。
- 当前保留的主要非阻塞项是部分图表字体警告和 seaborn 版本兼容提示，不影响结果生成。

## 推荐展示方式

如果你把它当作个人项目展示，建议在 README 里继续补充以下内容：

- 项目背景与问题定义
- 数据集结构
- 模型架构图
- 实验结果表
- 失败案例分析
- 可视化结果截图

## 当前状态

- 已支持生成模拟数据集
- 已支持自定义数据目录
- 已提供 TensorBoard 报告和图片上传评估界面
- 已完成可运行的发布版整理并推送到 GitHub
