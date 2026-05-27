import base64
import io

from flask import Flask, render_template_string, request
from PIL import Image

from scripts.inference_utils import predict_image


app = Flask(__name__)


HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>植物病害图片评估</title>
  <style>
    :root {
      --bg1: #07111f;
      --bg2: #0f172a;
      --card: rgba(15, 23, 42, 0.88);
      --line: rgba(148, 163, 184, 0.18);
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #22c55e;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(34, 197, 94, 0.22), transparent 28%),
        radial-gradient(circle at top right, rgba(59, 130, 246, 0.20), transparent 24%),
        linear-gradient(180deg, var(--bg1), var(--bg2));
      min-height: 100vh;
    }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 36px 20px 56px; }
    .hero {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 20px;
      margin-bottom: 22px;
    }
    .panel {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: 0 20px 60px rgba(0,0,0,.30);
      backdrop-filter: blur(16px);
    }
    .header { padding: 28px; }
    .header h1 { margin: 0 0 12px; font-size: 40px; line-height: 1.1; }
    .header p { margin: 0; color: var(--muted); font-size: 16px; line-height: 1.7; }
    .badge {
      display: inline-block; padding: 8px 12px; border-radius: 999px;
      background: rgba(34,197,94,.12); color: #bbf7d0; border: 1px solid rgba(34,197,94,.24);
      margin-bottom: 16px; font-size: 13px;
    }
    .form-panel { padding: 26px; }
    .upload-box {
      border: 1.5px dashed rgba(148,163,184,.40);
      border-radius: 18px; padding: 22px; background: rgba(15,23,42,.50);
    }
    .upload-box input[type=file] { width: 100%; color: var(--muted); }
    .actions { display: flex; gap: 12px; margin-top: 16px; align-items: center; flex-wrap: wrap; }
    .btn {
      appearance: none; border: 0; border-radius: 14px; padding: 12px 18px;
      background: linear-gradient(135deg, #22c55e, #16a34a); color: white; font-weight: 700;
      cursor: pointer; box-shadow: 0 12px 24px rgba(34,197,94,.24);
    }
    .hint { color: var(--muted); font-size: 14px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
    .card { padding: 22px; }
    .card h2 { margin-top: 0; margin-bottom: 14px; font-size: 20px; }
    .image-view { width: 100%; border-radius: 16px; border: 1px solid var(--line); overflow: hidden; }
    .image-view img { display: block; width: 100%; height: auto; }
    .summary { white-space: pre-wrap; line-height: 1.8; font-size: 16px; }
    .probs { display: grid; gap: 10px; }
    .prob {
      display: flex; justify-content: space-between; gap: 10px;
      padding: 12px 14px; border-radius: 12px; background: rgba(148,163,184,.09); border: 1px solid var(--line);
    }
    .meta { color: var(--muted); font-size: 14px; line-height: 1.6; }
    .error {
      margin-top: 16px; padding: 14px 16px; border-radius: 14px; background: rgba(239,68,68,.12); color: #fecaca;
      border: 1px solid rgba(239,68,68,.24);
    }
    .footer { margin-top: 18px; color: var(--muted); font-size: 13px; }
    @media (max-width: 900px) {
      .hero, .grid { grid-template-columns: 1fr; }
      .header h1 { font-size: 32px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="panel header">
        <div class="badge">PlantVillage / 叶片病害评估</div>
        <h1>植物病害图片评估界面</h1>
        <p>上传一张叶片图片，页面会调用当前训练好的多任务模型，返回病害风险评分、严重程度判断和处理建议。<br>界面已按项目模型输出对接，可直接做演示和汇报。</p>
      </div>
      <div class="panel form-panel">
        <form method="post" enctype="multipart/form-data">
          <div class="upload-box">
            <input type="file" name="image" accept="image/*" required>
            <div class="actions">
              <button class="btn" type="submit">开始评估</button>
              <span class="hint">支持 JPG / PNG / BMP 等常见图片格式</span>
            </div>
          </div>
        </form>
        <div class="footer">提示：使用的后端模型为 `best_multitask_model.pth`，推理时会自动做 128×128 归一化预处理。</div>
      </div>
    </div>

    {% if result %}
    <div class="grid">
      <div class="panel card">
        <h2>模型反馈图</h2>
        <div class="image-view">
          <img src="data:image/png;base64,{{ result.annotated_image }}" alt="评估结果图">
        </div>
      </div>
      <div class="panel card">
        <h2>评估结果</h2>
        <div class="summary">{{ result.summary }}</div>
        <h2 style="margin-top: 22px;">严重程度概率</h2>
        <div class="probs">
          {% for name, value in result.probabilities.items() %}
          <div class="prob"><span>{{ name }}</span><strong>{{ '%.1f%%'|format(value * 100) }}</strong></div>
          {% endfor %}
        </div>
        <h2 style="margin-top: 22px;">运行信息</h2>
        <div class="meta">
          设备：{{ result.meta.device }}<br>
          病害风险评分：{{ '%.2f'|format(result.meta.disease_risk_percent) }}%<br>
          严重程度：{{ result.meta.severity }}<br>
          置信度：{{ '%.2f'|format(result.meta.severity_confidence * 100) }}%
        </div>
      </div>
    </div>
    {% endif %}

    {% if error %}
    <div class="error">{{ error }}</div>
    {% endif %}
  </div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None
    if request.method == "POST":
        file = request.files.get("image")
        if not file or not file.filename:
            error = "请先选择一张图片。"
        else:
            try:
                image = Image.open(file.stream).convert("RGB")
                annotated, summary, probabilities, meta = predict_image(image)
                buffer = io.BytesIO()
                annotated.save(buffer, format="PNG")
                annotated_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                result = {
                    "annotated_image": annotated_b64,
                    "summary": summary,
                    "probabilities": probabilities,
                    "meta": meta,
                }
            except Exception as exc:
                error = f"图片评估失败：{exc}"
    return render_template_string(HTML, result=result, error=error)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7860, debug=False)