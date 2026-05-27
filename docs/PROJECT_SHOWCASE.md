# 项目展示页

## 项目名称
农作物病害智能诊断项目

## 项目亮点
- 支持模拟数据集快速跑通流程
- 支持公开数据集文件夹模式直接训练
- 支持多任务学习、诊断报告、Grad-CAM、风险评估
- 适合作为 GitHub 个人项目展示

## 推荐展示内容
- 任务背景图
- 模型结构图
- 训练曲线
- 混淆矩阵
- Grad-CAM 可视化
- 诊断报告样例

## 推荐目录
- `data/`：数据
- `docs/`：展示说明
- `scripts/`：运行和准备脚本
- `q1new.py`：主训练入口

## 公开数据集接入方式
将公开数据集整理为：
- `data/public_dataset/train/<class_name>/*.jpg`
- `data/public_dataset/val/<class_name>/*.jpg`

然后执行：

```powershell
.\.venv\Scripts\python.exe q1new.py --dataset-mode public --data-dir data/public_dataset --sample-ratio 1.0 --epochs 5 --patience 2
```
