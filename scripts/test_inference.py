import argparse
import json
import os
import sys

from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.inference_utils import find_sample_images, predict_image


def main():
    parser = argparse.ArgumentParser(description="测试单张图片的病害评估输出")
    parser.add_argument("--image", default=None, help="要测试的图片路径")
    parser.add_argument("--data-dir", default="data/plantvillage/val", help="找不到图片时用于抽样的目录")
    parser.add_argument("--model", default="best_multitask_model.pth", help="模型权重路径")
    args = parser.parse_args()

    image_path = args.image
    if image_path is None:
        candidates = find_sample_images(args.data_dir, limit=1)
        if not candidates:
            raise FileNotFoundError(f"未找到可测试图片: {args.data_dir}")
        image_path = candidates[0]

    if not os.path.exists(image_path):
        raise FileNotFoundError(image_path)

    image = Image.open(image_path).convert("RGB")
    _, summary, probabilities, meta = predict_image(image, model_path=args.model)

    output = {
        "image": image_path,
        "summary": summary,
        "probabilities": probabilities,
        "meta": meta,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
