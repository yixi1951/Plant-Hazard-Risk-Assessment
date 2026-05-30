# Agricultural Disease Diagnosis Project

> 将农业病害识别、严重程度分级、风险评估与 Web 演示整合为一个可复现、可展示、可部署的完整项目。

## 项目亮点

- 多任务学习：同时输出病害类别、严重程度和风险反馈。
- 可解释诊断：支持 Grad-CAM、诊断报告和结果可视化。
- 可演示 Web UI：支持本地图片上传、图片 URL 预览、结果图展示与下载。
- 可复现实验：支持模拟数据集和 PlantVillage 数据集两种流程。
- 可公网访问：Flask 服务默认监听 `0.0.0.0:7860`，便于局域网或服务器部署。

## 你会看到什么

- 训练主模型：`q1new.py`
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
python q1new.py --data-dir data/mock_problem_b --sample-ratio 1.0 --epochs 5 --patience 2
```

PlantVillage 数据：

```powershell
python q1new.py --dataset-mode plantvillage --data-dir data/plantvillage --sample-ratio 1.0 --epochs 15 --patience 5
```

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

- `q1.py`：病害分类基础模型
- `q1new.py`：多任务联合学习主入口
- `q2.py`：少样本学习与可视化
- `q3.py`：严重程度三分类与 Grad-CAM 可视化
- `q4.py`：多任务诊断与风险评估
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

