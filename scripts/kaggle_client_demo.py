"""
Kaggle 数据集客户演示测试脚本
================================
在 Kaggle / 本地快速验证数据管道与模型推理，生成可展示的 JSON 报告。

用法示例（Kaggle Notebook 或本地）:
  # 1) 切分 Kaggle 数据集
  python scripts/prepare_kaggle_dataset.py --source-dir /kaggle/input/plantvillage-dataset --output-dir data/kaggle_demo

  # 2) 快速训练（可选，已有权重可跳过）
  python scripts/train_disease_multitask.py --train-dir data/kaggle_demo/train --val-dir data/kaggle_demo/val --epochs 3 --save-path artifacts/kaggle_demo.pth

  # 3) 客户演示：随机抽样推理并生成报告
  python scripts/kaggle_client_demo.py --data-dir data/kaggle_demo/val --model-path artifacts/kaggle_demo.pth --samples 7 --output-dir demo_reports
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image

from scripts.inference_utils import predict_image


def collect_images(data_dir: Path, limit_per_class=2):
    exts = {'.jpg', '.jpeg', '.png', '.bmp'}
    images = []
    for class_dir in sorted(data_dir.iterdir()):
        if not class_dir.is_dir():
            continue
        class_images = [p for p in class_dir.iterdir() if p.suffix.lower() in exts]
        random.shuffle(class_images)
        for p in class_images[:limit_per_class]:
            images.append(p)
    return images


def run_demo(data_dir, model_path, samples, output_dir, seed=42):
    random.seed(seed)
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not data_dir.exists():
        raise FileNotFoundError(f'数据目录不存在: {data_dir}')

    images = collect_images(data_dir)
    if not images:
        raise ValueError(f'未找到图片: {data_dir}')

    random.shuffle(images)
    selected = images[:samples]
    os.environ['MODEL_PATH'] = str(model_path)

    results = []
    base_time = datetime.utcnow()
    for i, img_path in enumerate(selected):
        image = Image.open(img_path).convert('RGB')
        annotated, summary, probabilities, meta = predict_image(image, model_path=str(model_path))
        ts = (base_time - timedelta(days=6 - i)).strftime('%Y%m%dT%H%M%SZ')
        report = {
            'summary': summary,
            'probabilities': probabilities,
            'meta': meta,
            'treatment_plan': meta.get('treatment_plan'),
            'generated_at': ts,
            'source': str(img_path),
            'class_folder': img_path.parent.name,
        }
        fname = f'demo_report_{i + 1:02d}.json'
        with open(output_dir / fname, 'w', encoding='utf-8') as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        results.append({
            'file': fname,
            'disease': meta.get('disease_name'),
            'severity': meta.get('severity'),
            'risk': meta.get('disease_risk_percent'),
            'confidence': meta.get('disease_confidence'),
        })
        print(f'[{i + 1}/{len(selected)}] {img_path.name} -> {meta.get("disease_name")} ({meta.get("severity")})')

    summary_path = output_dir / 'demo_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as fh:
        json.dump({'total': len(results), 'results': results}, fh, ensure_ascii=False, indent=2)

    print('=' * 60)
    print(f'演示报告已生成: {output_dir}')
    print(f'共 {len(results)} 条，摘要: {summary_path}')
    print('将 demo_reports/*.json 复制到项目 reports/ 目录后刷新 Web 页面即可展示趋势图')
    print('=' * 60)
    return results


def main():
    parser = argparse.ArgumentParser(description='Kaggle 数据集客户演示测试')
    parser.add_argument('--data-dir', required=True, help='验证集目录 (class_name/*.jpg)')
    parser.add_argument('--model-path', default='best_multitask_model.pth', help='模型权重路径')
    parser.add_argument('--samples', type=int, default=7, help='抽样图片数量（默认7，对应趋势图）')
    parser.add_argument('--output-dir', default='demo_reports', help='演示报告输出目录')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    run_demo(args.data_dir, args.model_path, args.samples, args.output_dir, args.seed)


if __name__ == '__main__':
    main()
