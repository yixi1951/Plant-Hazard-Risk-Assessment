"""
客户演示数据 — 开箱即用的样例报告与识别结果（无需模型权重）。
"""

import base64
import io
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.utils import DISEASE_DETAILS
from scripts.treatment_engine import build_treatment_plan
SEED_REPORTS_DIR = ROOT / 'data' / 'demo' / 'reports'
SHOWCASE_PATH = ROOT / 'data' / 'demo' / 'showcase.json'

# (id, severity, risk, confidence, days_ago_offset label)
DEMO_CASES = [
    ('apple_healthy', 0, '健康', 12.0, 0.94, 6, '苹果 · 健康叶片'),
    ('apple_scab', 1, '一般', 58.0, 0.88, 5, '苹果 · 斑点落叶病'),
    ('corn_blight', 10, '严重', 82.0, 0.91, 4, '玉米 · 大斑病（高风险）'),
    ('grape_rot', 18, '一般', 65.0, 0.86, 3, '葡萄 · 黑腐病'),
    ('corn_spot', 11, '一般', 52.0, 0.89, 2, '玉米 · 小斑病'),
    ('cherry_healthy', 6, '健康', 8.0, 0.96, 1, '樱桃 · 健康'),
    ('grape_healthy', 17, '健康', 15.0, 0.93, 0, '葡萄 · 健康'),
]

SHOWCASE_IDS = ['corn_blight', 'apple_scab', 'grape_rot', 'apple_healthy']


def _leaf_color(disease_id, severity):
    if severity == '健康' or disease_id in (0, 6, 9, 17):
        return (72, 160, 95), (45, 120, 70)
    if severity == '严重':
        return (180, 120, 60), (120, 70, 40)
    return (160, 140, 70), (100, 85, 50)


def make_demo_annotated_b64(disease_name, severity, risk):
    """生成演示用标注图（无需真实叶片照片）。"""
    from PIL import Image, ImageDraw, ImageFont

    w, h = 320, 280
    c1, c2 = _leaf_color(0, severity)
    img = Image.new('RGB', (w, h), (240, 245, 250))
    draw = ImageDraw.Draw(img)
    draw.ellipse([40, 30, 280, 220], fill=c1, outline=c2, width=3)
    draw.ellipse([80, 50, 200, 180], fill=c2)
    if severity != '健康':
        for i in range(8):
            x, y = 100 + i * 15, 80 + (i % 3) * 25
            draw.ellipse([x, y, x + 22, y + 14], fill=(90, 60, 40) if severity == '严重' else (130, 90, 50))

    try:
        font_l = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 18)
        font_s = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 14)
    except Exception:
        font_l = ImageFont.load_default()
        font_s = font_l

    box_h = 72
    draw.rounded_rectangle([12, h - box_h - 8, w - 12, h - 8], radius=10, fill=(30, 41, 59))
    draw.text((24, h - box_h + 6), '【演示样例】' + disease_name, fill=(255, 235, 160), font=font_l)
    draw.text((24, h - box_h + 32), f'风险 {risk:.0f}% · {severity}', fill=(255, 255, 255), font=font_s)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def build_case_payload(case_key):
    """构建单条演示识别结果（与 predict 返回结构一致）。"""
    mapping = {c[0]: c for c in DEMO_CASES}
    if case_key not in mapping:
        case_key = 'corn_blight'
    key, did, severity, risk, conf, _, label = mapping[case_key]
    info = DISEASE_DETAILS.get(did, {'name': '演示病害'})
    tp = build_treatment_plan(info['name'], severity=severity, disease_idx=did,
                              risk_percent=risk, confidence=conf)
    disease_name = tp['disease_name']
    summary = (
        f"【客户演示样例】{label}\n"
        f"识别病害: {disease_name} (置信度 {conf:.1%})\n"
        f"作物类型: {tp['crop']}\n"
        f"病害风险评分: {risk:.1f}%\n"
        f"严重程度: {severity}\n"
        f"紧急程度: {tp['urgency']}\n"
        f"防治建议: {tp['quick_suggestion']}"
    )
    probs = (
        {'健康': 0.1, '一般': 0.25, '严重': 0.65} if severity == '严重'
        else ({'健康': 0.72, '一般': 0.18, '严重': 0.1} if severity == '健康'
              else {'健康': 0.15, '一般': 0.62, '严重': 0.23})
    )
    meta = {
        'device': 'demo-sample',
        'disease_risk_percent': risk,
        'disease_name': disease_name,
        'disease_confidence': conf,
        'severity': severity,
        'severity_confidence': 0.9,
        'crop': tp['crop'],
        'urgency': tp['urgency'],
        'urgency_score': tp['urgency_score'],
        'treatment_plan': tp,
        'demo': True,
    }
    return {
        'case_id': key,
        'label': label,
        'annotated_image': make_demo_annotated_b64(disease_name, severity, risk),
        'summary': summary,
        'probabilities': probs,
        'meta': meta,
        'treatment_plan': tp,
    }


def build_report_object(case_key, generated_at=None):
    from scripts.report_schema import normalize_report_object

    payload = build_case_payload(case_key)
    if generated_at is None:
        generated_at = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    return normalize_report_object(
        summary=payload['summary'],
        probabilities=payload['probabilities'],
        meta=payload['meta'],
        treatment_plan=payload['treatment_plan'],
        generated_at=generated_at,
        demo=True,
        source='demo_seed',
        case_id=case_key,
    )


def write_seed_reports(target_dir=None):
    """写入 7 条演示 JSON 到 data/demo/reports 或指定目录。"""
    target = Path(target_dir or SEED_REPORTS_DIR)
    target.mkdir(parents=True, exist_ok=True)
    base = datetime.utcnow()
    written = []
    for key, did, severity, risk, conf, days_ago, _ in DEMO_CASES:
        ts = (base - timedelta(days=days_ago)).strftime('%Y%m%dT%H%M%SZ')
        fname = f'demo_{key}_{ts}.json'
        obj = build_report_object(key, ts)
        path = target / fname
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2)
        written.append(fname)
    return written


def ensure_runtime_reports(force=False):
    """
    启动时若 reports/ 为空，从 data/demo/reports 复制演示数据。
    返回 (copied_count, message)
    """
    reports_dir = ROOT / 'reports'
    seed_dir = SEED_REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)

    if not seed_dir.exists() or not list(seed_dir.glob('demo_*.json')):
        write_seed_reports(seed_dir)

    existing = list(reports_dir.glob('*.json'))
    if existing and not force:
        return 0, '已有诊断报告，跳过演示数据注入'

    copied = 0
    for src in sorted(seed_dir.glob('demo_*.json')):
        dst = reports_dir / src.name
        if force or not dst.exists():
            shutil.copy2(src, dst)
            copied += 1
    return copied, f'已注入 {copied} 条客户演示报告'


def get_showcase_list():
    """返回首页展示的 4 个精选样例摘要。"""
    items = []
    for cid in SHOWCASE_IDS:
        p = build_case_payload(cid)
        items.append({
            'id': cid,
            'label': p['label'],
            'disease_name': p['meta']['disease_name'],
            'crop': p['meta']['crop'],
            'severity': p['meta']['severity'],
            'risk': p['meta']['disease_risk_percent'],
            'urgency': p['meta']['urgency'],
            'confidence': round(p['meta']['disease_confidence'] * 100, 1),
            'suggestion': p['treatment_plan']['quick_suggestion'][:60] + '…',
        })
    return items


if __name__ == '__main__':
    files = write_seed_reports()
    print(f'已生成 {len(files)} 个演示报告 -> {SEED_REPORTS_DIR}')
