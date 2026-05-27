import argparse
import os
import random
import shutil
from pathlib import Path

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.JPG', '.JPEG', '.PNG', '.BMP'}


def is_image_file(path: Path) -> bool:
    return path.suffix in IMAGE_EXTENSIONS


def copy_split(source_dir: Path, output_dir: Path, train_ratio: float, seed: int):
    random.seed(seed)

    class_dirs = [p for p in source_dir.iterdir() if p.is_dir()]
    if not class_dirs:
        raise ValueError(f'未在源目录中找到类别文件夹: {source_dir}')

    for class_dir in class_dirs:
        images = [p for p in class_dir.rglob('*') if p.is_file() and is_image_file(p)]
        if not images:
            continue

        random.shuffle(images)
        split_index = max(1, int(len(images) * train_ratio))
        train_images = images[:split_index]
        val_images = images[split_index:]

        for split_name, split_images in [('train', train_images), ('val', val_images)]:
            target_dir = output_dir / split_name / class_dir.name
            target_dir.mkdir(parents=True, exist_ok=True)
            for image_path in split_images:
                shutil.copy2(image_path, target_dir / image_path.name)

    print('=' * 70)
    print('公开数据集切分完成')
    print(f'源目录: {source_dir}')
    print(f'输出目录: {output_dir}')
    print('最终结构: output/train/<class_name>/*.jpg 和 output/val/<class_name>/*.jpg')
    print('=' * 70)


def main():
    parser = argparse.ArgumentParser(description='将公开图像分类数据集切分为 train/val 结构')
    parser.add_argument('--source-dir', type=str, required=True, help='原始数据集目录，内部为类别文件夹')
    parser.add_argument('--output-dir', type=str, default='data/public_dataset', help='输出目录')
    parser.add_argument('--train-ratio', type=float, default=0.8, help='训练集比例，默认0.8')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    copy_split(source_dir, output_dir, args.train_ratio, args.seed)


if __name__ == '__main__':
    main()
