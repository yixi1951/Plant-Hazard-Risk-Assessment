import glob
import os
from functools import lru_cache

import torch
import torch.nn as nn
import torchvision.transforms as transforms
from PIL import Image, ImageDraw, ImageFont
from torchvision import models


IMAGE_SIZE = 128
SEVERITY_LABELS = ["健康", "一般", "严重"]


def build_transform():
    return transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


class CrossTaskAttention(nn.Module):
    def __init__(self, input_dim, hidden_dim):
        super().__init__()
        self.disease_query = nn.Linear(input_dim, hidden_dim)
        self.severity_query = nn.Linear(input_dim, hidden_dim)
        self.value_proj = nn.Linear(input_dim, hidden_dim)

    def forward(self, x):
        disease_q = self.disease_query(x)
        severity_q = self.severity_query(x)
        value = self.value_proj(x)
        disease_attention = torch.softmax(torch.sum(disease_q * value, dim=1, keepdim=True), dim=1)
        severity_attention = torch.softmax(torch.sum(severity_q * value, dim=1, keepdim=True), dim=1)
        return disease_attention * value, severity_attention * value


class MultiTaskNetwork(nn.Module):
    def __init__(self, num_diseases=1, num_severity=3):
        super().__init__()
        self.backbone = models.mobilenet_v2(weights=None)
        self.feature_extractor = self.backbone.features
        self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc_input_dim = 1280

        self.cross_attention = CrossTaskAttention(self.fc_input_dim, 256)

        self.disease_head = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(128, num_diseases),
        )

        self.severity_head = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(128, num_severity),
        )

    def forward(self, x):
        features = self.feature_extractor(x)
        shared_features = self.avg_pool(features).view(features.size(0), -1)
        disease_features, severity_features = self.cross_attention(shared_features)
        disease_output = self.disease_head(disease_features)
        severity_output = self.severity_head(severity_features)
        return disease_output, severity_output, features


def _safe_load_state_dict(model, model_path, device):
    state = torch.load(model_path, map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model


@lru_cache(maxsize=2)
def load_model(model_path="best_multitask_model.pth", device_name=None):
    device = torch.device(device_name or ("cuda" if torch.cuda.is_available() else "cpu"))
    model = MultiTaskNetwork(num_diseases=1, num_severity=3).to(device)
    _safe_load_state_dict(model, model_path, device)
    return model, device


def find_sample_images(root_dir, limit=4):
    if not os.path.isdir(root_dir):
        return []
    image_paths = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.JPG", "*.JPEG", "*.PNG", "*.BMP"):
        image_paths.extend(glob.glob(os.path.join(root_dir, "**", ext), recursive=True))
    return sorted(image_paths)[:limit]


def _get_font(size=24):
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def annotate_result(image, title, lines):
    canvas = image.convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_title = _get_font(26)
    font_body = _get_font(20)

    pad = 18
    box_h = min(170, canvas.size[1] // 3)
    draw.rounded_rectangle(
        [pad, canvas.size[1] - box_h - pad, canvas.size[0] - pad, canvas.size[1] - pad],
        radius=18,
        fill=(14, 17, 26, 190),
    )
    draw.text((pad + 18, canvas.size[1] - box_h - pad + 14), title, font=font_title, fill=(255, 235, 160, 255))

    y = canvas.size[1] - box_h - pad + 54
    for line in lines:
        draw.text((pad + 18, y), line, font=font_body, fill=(255, 255, 255, 255))
        y += 26

    return Image.alpha_composite(canvas, overlay).convert("RGB")


def predict_image(image, model_path="best_multitask_model.pth", device_name=None):
    if image is None:
        return None, "请先上传图片。", {}, {}

    model, device = load_model(model_path=model_path, device_name=device_name)
    transform = build_transform()
    tensor = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        disease_logit, severity_logits, _ = model(tensor)
        disease_score = torch.sigmoid(disease_logit).item()
        severity_probs = torch.softmax(severity_logits, dim=1)[0].detach().cpu().tolist()

    severity_idx = int(torch.tensor(severity_probs).argmax().item())
    severity_name = SEVERITY_LABELS[severity_idx]
    severity_conf = severity_probs[severity_idx]
    disease_risk = disease_score * 100.0

    if severity_idx == 0 and disease_score < 0.5:
        advice = "当前结果偏向健康，建议继续保持常规巡检。"
    elif severity_idx == 1:
        advice = "检测到一般风险，建议尽快复查叶片并关注病斑变化。"
    else:
        advice = "检测到较高风险，建议及时隔离、处理病叶并进一步人工复核。"

    summary = (
        f"病害风险评分: {disease_risk:.1f}%\n"
        f"严重程度: {severity_name} (置信度 {severity_conf:.1%})\n"
        f"反馈: {advice}"
    )

    annotated = annotate_result(
        image,
        title="植物病害评估结果",
        lines=[
            f"病害风险: {disease_risk:.1f}%",
            f"严重程度: {severity_name}",
            f"建议: {advice}",
        ],
    )

    probability_map = {
        "健康": round(severity_probs[0], 4),
        "一般": round(severity_probs[1], 4),
        "严重": round(severity_probs[2], 4),
    }
    meta = {
        "device": str(device),
        "disease_risk_percent": round(disease_risk, 2),
        "severity": severity_name,
        "severity_confidence": round(float(severity_conf), 4),
    }
    return annotated, summary, probability_map, meta
