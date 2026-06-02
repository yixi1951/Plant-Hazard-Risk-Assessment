# Agricultural Disease Diagnosis Project

> 将农业病害识别、严重程度分级、风险评估与 Web 演示整合为一个可复现、可展示、可部署的完整项目。

## 项目亮点

- 多任务学习：同时输出病害类别、严重程度和风险反馈。
- 可解释诊断：支持 Grad-CAM、诊断报告和结果可视化。
- 可演示 Web UI：支持本地图片上传、图片 URL 预览、结果图展示与下载。
- 可复现实验：支持模拟数据集和 PlantVillage 数据集两种流程。
- 可公网访问：Flask 服务默认监听 `0.0.0.0:7860`，便于局域网或服务器部署。

## 你会看到什么

- 训练主模型：`train_multitask_model.py`
- 训练“可识别具体病害名称”的多任务模型：`scripts/train_disease_multitask.py`
- 生成模拟数据：`scripts/generate_mock_dataset.py`
- 运行上传评估界面：`app.py`
- 输出诊断结果：`diagnostic_reports/`
- 输出可解释图：`grad_cam_visualizations/`
- 输出对比图：`risk_distribution.png`、`synergy_comparison.png`

## 快速开始

### 1. 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 生成测试数据集

```powershell
python scripts/generate_mock_dataset.py --output-dir data/mock_problem_b --num-classes 6 --train-per-class 80 --val-per-class 20
```

### 3. 训练主模型

模拟数据：

```powershell
python train_multitask_model.py --data-dir data/mock_problem_b --sample-ratio 1.0 --epochs 5 --patience 2
```

PlantVillage 数据：

```powershell
python train_multitask_model.py --dataset-mode plantvillage --data-dir data/plantvillage --sample-ratio 1.0 --epochs 15 --patience 5
```

### 3.1 训练可识别具体病害名称的模型

如果你的数据已经按“类别文件夹”整理好，例如 `train/Apple_scab/*.jpg`、`train/healthy/*.jpg`，可以直接训练一个会输出“病害名称 + 严重程度”的模型：

```powershell
python scripts/train_disease_multitask.py --train-dir data/plantvillage/train --val-dir data/plantvillage/val --save-path artifacts/disease_multitask.pth --epochs 15 --batch-size 32
```

训练完成后会生成：

- `artifacts/disease_multitask.pth`
- `artifacts/disease_multitask.json`

页面推理时如果要使用新模型，只需设置：

```powershell
$env:MODEL_PATH='artifacts/disease_multitask.pth'
python app.py
```

这样页面就能直接显示“识别到什么病”，而不仅是风险分数。

### 3.2 适配 Kaggle 数据目录

如果你下载的是 Kaggle 版数据集，先把原始目录整理成 `train/val` 结构，再直接复用当前训练流程：

```powershell
python scripts/prepare_kaggle_dataset.py --source-dir D:\kaggle\PlantVillage --output-dir data/kaggle_plantvillage --train-ratio 0.8
python train_multitask_model.py --dataset-mode kaggle --data-dir data/kaggle_plantvillage --sample-ratio 1.0 --epochs 15 --patience 5
```

脚本会把 Kaggle 目录下的类别文件夹自动切分为：

- `data/kaggle_plantvillage/train/<class_name>/*.jpg`
- `data/kaggle_plantvillage/val/<class_name>/*.jpg`

这样就能无缝接入你现在这套多任务训练、推理和 Web 页面。

### 4. 启动 Web 页面

```powershell
python app.py
```

默认会监听 `0.0.0.0:7860`。同一局域网内的其他设备可以通过这台电脑的 IP 访问页面。若只想本机访问，可显式指定：

```powershell
$env:APP_HOST='127.0.0.1'
$env:APP_PORT='7860'
python app.py
```

## 页面流程

1. 上传本地图片或输入公开图片 URL。
2. 先生成缩略图预览，确认内容无误。
3. 再启动模型评估。
4. 查看病害风险评分、严重程度与处理建议。
5. 下载结果图或复制摘要用于汇报。

## 目录结构

- `train_disease_classifier.py`：病害分类基础模型
- `train_multitask_model.py`：多任务联合学习主入口
- `few_shot_classification.py`：少样本学习与可视化
- `severity_gradcam.py`：严重程度三分类与 Grad-CAM 可视化
- `risk_assessment.py`：多任务诊断与风险评估
- `app.py`：图片上传评估界面
- `scripts/`：训练、数据准备与测试脚本
- `data/`：数据集目录
- `reports/`：实验/报告产物

## 结果与产物

运行训练与评估后，常见输出包括：

- `best_multitask_model.pth`
- `best_single_disease_model.pth`
- `best_single_severity_model.pth`
- `diagnostic_reports/`
- `grad_cam_visualizations/`
- `risk_distribution.png`
- `synergy_comparison.png`

## 运行状态

- 训练、测试和推理流程已验证可跑通。
- Web 演示页面已完成并可本地/局域网访问。
- 项目代码已推送到 GitHub，可直接用于答辩展示或课程汇报。

## 适合怎么展示

建议在答辩或项目介绍时按下面顺序讲：

- 问题定义
- 数据集与目录结构
- 模型结构与多任务学习
- 实验结果与对比图
- 可解释分析
- Web 演示与结果反馈

## 备注

如果你准备把它部署到更正式的环境，建议继续加上：

- Docker 或云服务器部署说明
- 公开访问域名
- 在线演示截图
- 典型成功案例与失败案例

## 部署与运行（建议）

推荐使用虚拟环境或容器化部署以保证依赖一致性。

- 使用 Python 虚拟环境（快速测试）:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

- 使用 Gunicorn（生产建议）:

```powershell
# 安装 gunicorn
pip install gunicorn
# 启动（在 Linux/WSL 或服务器上）
gunicorn -w 4 -b 0.0.0.0:7860 app:app
```

- 使用 Docker（可选）: 在项目根创建 `Dockerfile`，示例内容：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 7860
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:7860", "app:app"]
```

构建并运行：

```powershell
docker build -t agri-ai:latest .
docker run -p 7860:7860 agri-ai:latest
```

## 安全与输入校验说明

后端在处理用户上传或 URL 下载时应注意以下安全点（本项目已实现部分校验）：

- 限制上传大小：服务器端 `app.config['MAX_CONTENT_LENGTH']` 已设置为 5MB，避免大文件消耗资源。
- 校验 URL：仅允许 `http`/`https`，并拒绝解析到私网/回环地址（避免 SSRF / 内网探测）。
- 校验资源类型：在下载 URL 时验证 `Content-Type` 为 `image/*`。
- 上传文件名与扩展：阻止可疑扩展（如 `.php`, `.exe` 等），并在服务器端用 PIL 尝试解析图像内容作为最终验证。
- 日志记录：关键事件（拒绝的 URL、过大文件、可疑上传）会记录到服务器日志，便于排查。

在生产环境中，也建议：

- 将应用置于反向代理后面（如 Nginx），并启用 HTTPS。
- 对公开 API 限频（rate limiting）以防滥用。
- 在需要时使用专门的文件扫描/杀毒服务对上传内容做进一步检测。

## 示例截图

- 首页仪表盘（示例）： `reports/report_20260531_161200.json` 中对应的结果图和历史趋势会在仪表盘中呈现。

### 仪表盘预览（示例图）

<p align="center">
	<img src="static/screenshots/readme_1.png" alt="Dashboard 示例" width="880">
</p>

*图 1：仪表盘示例（来自批量推理的注释图） — 显示历史病害风险趋势与关键快捷统计。*

### 结果示例（示例图）

<p align="center">
	<img src="static/screenshots/readme_2.png" alt="评估结果示例" width="520">
</p>

*图 2：识别结果示例（来自批量推理的注释图） — 模型输出的病害类别、严重程度与风险评分摘要。*

(注：当前 README 中使用的是示例截图与示例报告，部署到真实服务器后建议替换为真实截图或托管链接。)

## 开发流程（本地复现）

1. 准备环境：创建并激活虚拟环境，安装依赖（见上文）。
2. 数据准备：将数据放入 `data/`，如果是 Kaggle 数据，先在本地解压并按下面的建议划分目录。可运行 `scripts/generate_mock_dataset.py` 快速生成测试用数据。
3. 划分数据集：建议按照 80% train / 10% val / 10% test 划分；或使用 k-fold（例如 5-fold）进行更稳健的超参搜索与模型验证。切记：**不要在训练或调参时使用 test 集**，test 仅用于最终评估。

示例目录结构（训练/验证/测试）:

```
data/plantvillage/
	train/
		classA/
		classB/
	val/
		classA/
		classB/
	test/
		classA/
		classB/
```

4. 训练示例（用 `train_multitask_model.py`）：

```powershell
python train_multitask_model.py --data-dir data/plantvillage --epochs 20 --batch-size 32 --patience 5 --save-dir artifacts/
```

5. 验证与早停：在训练脚本中使用 `--patience` 参数或在训练循环中监控验证集指标并保存最优权重。

6. 生成报告：推理后，结果与 JSON 报告会写入 `reports/`，Web 页面会自动读取最近的报告以绘制历史趋势图。

## 测试

- 单元/集成测试：项目包含若干测试脚本（例如 `test.py`、`test_upload.py`），可直接用 Python 运行或用 `pytest`（如已安装）：

```powershell
pytest -q
```

## 贡献与许可

- 欢迎 issue 与 PR，建议先在 issue 中描述你的改进点。
- 若需商业使用或署名许可，请在合并前选择合适的 `LICENSE`（常用 MIT / Apache-2.0）。

---

如果你需要，我可以：
- 把当前示例截图复制到 `static/` 并在 README 中嵌入预览；
- 添加 `CONTRIBUTING.md`、`LICENSE`（例如 MIT）并初始化 GitHub 仓库的推荐文件；
- 编写训练数据拆分脚本（从 Kaggle 下载后的自动划分与重命名）。

请告诉我你希望下一步我代办哪项。

