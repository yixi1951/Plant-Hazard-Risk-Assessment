# Agricultural Disease Diagnosis Project

将数学建模论文代码整理为可复现、可演示、可扩展的个人项目。

## 项目内容

- `q1.py`: 病害分类基础模型
- `q1new.py`: 多任务联合学习主入口，支持命令行指定数据目录
- `q2.py`: 少样本学习与可视化
- `q3.py`: 严重程度三分类与 Grad-CAM 可视化
- `q4.py`: 多任务诊断与风险评估
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
- 可作为个人项目的发布版基础
- 已提供 TensorBoard 报告和图片上传评估界面
