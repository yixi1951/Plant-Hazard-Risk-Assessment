# 智农 Web + PyTorch 推理（CPU）
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV APP_HOST=0.0.0.0 \
    APP_PORT=7860 \
    MODEL_PATH=/app/models/best_multitask_model.pth \
    FLASK_SECRET_KEY=change-me-in-production

RUN mkdir -p tmp_uploads reports

EXPOSE 7860

# 生产环境请挂载权重：-v ./models/best_multitask_model.pth:/app/models/best_multitask_model.pth
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:7860", "--timeout", "120", "app:app"]