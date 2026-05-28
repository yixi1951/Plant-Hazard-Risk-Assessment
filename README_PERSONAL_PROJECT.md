# 农业病害诊断个人项目（答辩/汇报版）

## 封面摘要

**项目名称**：农业病害智能诊断与风险评估系统

**项目定位**：面向农业病害识别、严重程度判断和风险预警的深度学习应用

**一句话简介**：将原始数学建模题目代码整理为一个可训练、可解释、可演示的完整项目，支持本地图片上传评估。

**核心能力**：

- 叶片病害分类与严重程度分级。
- 诊断报告自动生成与 Grad-CAM 可视化。
- 风险分级输出，辅助精准防控展示。
- 支持模拟数据集与 PlantVillage 数据集复现。

**展示状态**：

- 训练和推理流程已验证。
- Web 上传评估 UI 已完成。
- 结果文件与可视化产物已生成。
- 已推送到 GitHub，可作为汇报版本直接使用。

## 1. 项目目标
将数学建模论文代码改造成可复现、可演示、可迭代的个人项目。

当前仓库已包含以下任务脚本，并已验证训练、推理和上传评估流程可运行：
- q1.py: 问题一分类模型
- q2.py: 少样本学习与可视化
- q3.py: 严重程度三分类（TensorFlow）
- q4.py / q1new.py: 多任务学习 + 可解释诊断

## 2. 当原数据集丢失时的解决方案
本项目新增了模拟数据集生成器：
- scripts/generate_mock_dataset.py

它会生成与你原始代码兼容的目录结构：
- data/mock_problem_b/AgriculturalDisease_trainingset/images
- data/mock_problem_b/AgriculturalDisease_trainingset/train_list.txt
- data/mock_problem_b/AgriculturalDisease_validationset/images
- data/mock_problem_b/AgriculturalDisease_validationset/val_list.txt

## 3. 快速开始
### 3.1 安装依赖
建议先创建虚拟环境后安装：

```powershell
pip install torch torchvision pillow numpy scikit-learn matplotlib seaborn tqdm opencv-python
```

### 3.2 生成测试数据集
```powershell
python scripts/generate_mock_dataset.py --output-dir data/mock_problem_b --num-classes 6 --train-per-class 80 --val-per-class 20
```

### 3.3 训练多任务模型（项目主入口）
```powershell
python q1new.py --data-dir data/mock_problem_b --sample-ratio 1.0 --epochs 5 --patience 2
```

如果使用 PlantVillage，请优先把数据放在本机 C 盘或本地 SSD，然后执行：

```powershell
python q1new.py --dataset-mode plantvillage --data-dir C:\Users\ASUS\Desktop\新建文件夹\data\plantvillage --sample-ratio 1.0 --epochs 15 --patience 5
```

## 4. 输出结果位置
运行 q1new.py 后，常见输出包括：
- best_multitask_model.pth
- best_single_disease_model.pth
- best_single_severity_model.pth
- diagnostic_reports/
- grad_cam_visualizations/
- synergy_comparison.png
- risk_distribution.png

## 5. 个人项目展示建议
- README 中补充：任务背景、方法图、实验结果、失败案例分析。
- 增加命令行参数说明和复现实验步骤。
- 当前已提供图片上传评估界面，可直接作为展示入口。

## 6. 可选：替换为真实公开数据集
如需更真实测试，可用 PlantVillage 等公开数据集。保持目录结构一致后即可复用当前训练流程。

## 7. 当前完成度
- 已完成训练、测试、诊断报告、Grad-CAM 和风险评估。
- 已完成上传评估 UI。
- 已推送到 GitHub，可直接用于展示和复现。
