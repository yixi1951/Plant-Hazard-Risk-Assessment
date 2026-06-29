import os
import json
import argparse
from datetime import datetime

from PIL import Image

from scripts.inference_utils import find_sample_images, predict_image


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def process_images(input_dir, model_path, reports_dir, images_out_dir, limit=None):
    ensure_dir(reports_dir)
    ensure_dir(images_out_dir)

    # find images; fallback to reports/images if input empty
    paths = find_sample_images(input_dir, limit=1000)
    if not paths:
        alt = os.path.join(os.getcwd(), 'reports', 'images')
        paths = find_sample_images(alt, limit=1000)
    if limit:
        paths = paths[:limit]

    if not paths:
        print('No images found in', input_dir)
        return 0

    count = 0
    for p in paths:
        try:
            img = Image.open(p).convert('RGB')
            annotated, summary, probs, meta = predict_image(img, model_path=model_path)

            ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            base = os.path.splitext(os.path.basename(p))[0]
            out_img_name = f'annotated_{base}_{ts}.png'
            out_json_name = f'report_{base}_{ts}.json'

            annotated_path = os.path.join(images_out_dir, out_img_name)
            annotated.save(annotated_path)

            report_obj = {
                'generated_at': ts,
                'source': p,
                'summary': summary,
                'probabilities': probs,
                'meta': meta,
            }
            with open(os.path.join(reports_dir, out_json_name), 'w', encoding='utf-8') as fh:
                json.dump(report_obj, fh, ensure_ascii=False, indent=2)

            # also copy annotated to static screenshots for README preview
            try:
                import shutil
                shutil.copyfile(annotated_path, os.path.join(images_out_dir, f'readme_{count+1}.png'))
            except Exception:
                pass

            print('Processed', p, '->', annotated_path)
            count += 1
        except Exception as e:
            print('Failed', p, e)
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', default='data/plantvillage/test', help='Directory with test images')
    parser.add_argument('--model', default='models/best_multitask_model.pth', help='Model path')
    parser.add_argument('--reports-dir', default='reports', help='Where to write JSON reports')
    parser.add_argument('--images-out', default='static/screenshots', help='Where to save annotated images')
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()

    n = process_images(args.input_dir, args.model, args.reports_dir, args.images_out, limit=args.limit)
    print(f'Done. Processed {n} images.')


if __name__ == '__main__':
    main()
