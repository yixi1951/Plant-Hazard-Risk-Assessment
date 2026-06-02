import argparse
import shutil
from pathlib import Path

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.JPG', '.JPEG', '.PNG', '.BMP'}


def is_image_file(path: Path) -> bool:
    return path.suffix in IMAGE_EXTENSIONS


def find_class_folders(source_dir: Path):
    """Return leaf folders that look like class folders.

    Supports common Kaggle layouts:
    - source/class_name/*.jpg
    - source/train/class_name/*.jpg
    - source/PlantVillage/class_name/*.jpg
    - source/colored/train/class_name/*.jpg
    """
    if not source_dir.exists():
        raise FileNotFoundError(f'源目录不存在: {source_dir}')

    candidates = []
    for child in source_dir.iterdir():
        if child.is_dir():
            image_count = sum(1 for p in child.rglob('*') if p.is_file() and is_image_file(p))
            if image_count > 0:
                candidates.append(child)

    # If source_dir itself is already a class folder container (e.g. data/train)
    if candidates:
        # Prefer the shallowest set of folders with direct images beneath them.
        direct_level = [p for p in candidates if any(p.glob('*'))]
        return direct_level or candidates

    # Recurse one level deeper for layouts like source/train/class_name
    nested_roots = []
    for child in source_dir.iterdir():
        if child.is_dir():
            inner = [g for g in child.iterdir() if g.is_dir() and any(p.is_file() and is_image_file(p) for p in g.rglob('*'))]
            if inner:
                nested_roots.extend(inner)
    if nested_roots:
        return nested_roots

    raise ValueError(f'未在源目录中找到可用的类别文件夹: {source_dir}')


def copy_split(source_dir: Path, output_dir: Path, train_ratio: float, seed: int):
    import random

    random.seed(seed)
    class_dirs = find_class_folders(source_dir)
    if not class_dirs:
        raise ValueError(f'未找到任何类别文件夹: {source_dir}')

    output_dir.mkdir(parents=True, exist_ok=True)

    total_train = 0
    total_val = 0
    for class_dir in class_dirs:
        images = [p for p in class_dir.rglob('*') if p.is_file() and is_image_file(p)]
        if not images:
            continue

        random.shuffle(images)
        split_index = max(1, int(len(images) * train_ratio))
        train_images = images[:split_index]
        val_images = images[split_index:] or images[-1:]

        for split_name, split_images in [('train', train_images), ('val', val_images)]:
            target_dir = output_dir / split_name / class_dir.name
            target_dir.mkdir(parents=True, exist_ok=True)
            for image_path in split_images:
                shutil.copy2(image_path, target_dir / image_path.name)

        total_train += len(train_images)
        total_val += len(val_images)

    print('=' * 70)
    print('Kaggle 数据目录适配完成')
    print(f'源目录: {source_dir}')
    print(f'输出目录: {output_dir}')
    print('目标结构: output/train/<class_name>/*.jpg 和 output/val/<class_name>/*.jpg')
    print(f'训练样本: {total_train} | 验证样本: {total_val}')
    print('=' * 70)


def main():
    parser = argparse.ArgumentParser(description='将 Kaggle/公开图像数据集切分为 train/val 结构，供 q1new.py 直接训练')
    parser.add_argument('--source-dir', type=str, required=True, help='Kaggle 原始数据目录，内部为类别文件夹或包含 train/val 子目录')
    parser.add_argument('--output-dir', type=str, default='data/kaggle_plantvillage', help='输出目录，默认 data/kaggle_plantvillage')
    parser.add_argument('--train-ratio', type=float, default=0.8, help='训练集比例，默认0.8')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    copy_split(source_dir, output_dir, args.train_ratio, args.seed)

    print('\n训练命令示例：')
    print(f'python q1new.py --dataset-mode kaggle --data-dir {output_dir} --sample-ratio 1.0 --epochs 15 --patience 5')


if __name__ == '__main__':
    main()
