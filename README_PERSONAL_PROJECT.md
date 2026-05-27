# 农业病害诊断个人项目（可在无原赛题数据时运行）

## 1. 项目目标
将数学建模论文代码改造成可复现、可演示、可迭代的个人项目。

当前仓库已包含以下任务脚本：
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
- 后续可加一个轻量 Web Demo（Gradio/Streamlit）作为展示入口。

## 6. 可选：替换为真实公开数据集
如需更真实测试，可用 PlantVillage 等公开数据集。保持目录结构一致后即可复用当前训练流程。
