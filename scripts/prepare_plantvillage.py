import argparse
from pathlib import Path

from prepare_public_dataset import copy_split


def main():
    parser = argparse.ArgumentParser(description='将 PlantVillage 数据集切分为 train/val 结构')
    parser.add_argument('--source-dir', type=str, required=True, help='PlantVillage 原始数据目录，内部为类别文件夹')
    parser.add_argument('--output-dir', type=str, default='data/plantvillage', help='输出目录，默认 data/plantvillage')
    parser.add_argument('--train-ratio', type=float, default=0.8, help='训练集比例，默认0.8')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    copy_split(source_dir, output_dir, args.train_ratio, args.seed)
    print('PlantVillage 数据集已准备完成，可直接使用 --dataset-mode plantvillage 训练。')


if __name__ == '__main__':
    main()
