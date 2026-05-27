import argparse
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw


def _draw_pattern(img: Image.Image, label: int, seed: int) -> None:
    random.seed(seed)
    draw = ImageDraw.Draw(img)

    # 背景基色按标签变化，保证类别之间有可学习差异
    base_colors = [
        (70, 130, 90),
        (90, 150, 70),
        (110, 120, 80),
        (85, 140, 110),
        (120, 160, 90),
        (95, 115, 85),
    ]
    bg = base_colors[label % len(base_colors)]
    draw.rectangle((0, 0, img.width, img.height), fill=bg)

    # 模拟叶脉
    for i in range(6):
        x0 = random.randint(10, img.width - 10)
        y0 = random.randint(10, img.height - 10)
        x1 = x0 + random.randint(-30, 30)
        y1 = y0 + random.randint(20, 50)
        draw.line((x0, y0, x1, y1), fill=(30, 80, 30), width=2)

    # 按标签添加不同“病斑”风格
    spot_count = 4 + label * 2
    for _ in range(spot_count):
        r = random.randint(6, 14)
        x = random.randint(r, img.width - r)
        y = random.randint(r, img.height - r)
        color = (
            min(255, 120 + label * 15 + random.randint(-10, 10)),
            70 + random.randint(0, 30),
            40 + random.randint(0, 25),
        )
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)


def _write_split(split_root: Path, split_name: str, classes, samples_per_class: int, image_size: int):
    images_dir = split_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    list_name = "train_list.txt" if split_name == "train" else "val_list.txt"
    list_path = split_root / list_name

    lines = []
    for label in classes:
        for idx in range(samples_per_class):
            filename = f"{label}_{split_name}_{idx:04d}.jpg"
            image_path = images_dir / filename

            image = Image.new("RGB", (image_size, image_size), (0, 0, 0))
            _draw_pattern(image, label, seed=label * 100000 + idx)
            image.save(image_path, quality=95)

            lines.append(f"images/{filename} {label}\n")

    random.shuffle(lines)
    with open(list_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return list_path, len(lines)


def generate_dataset(output_root: Path, num_classes: int, train_per_class: int, val_per_class: int, image_size: int):
    if num_classes < 2:
        raise ValueError("num_classes 至少为 2")

    classes = list(range(num_classes))

    train_root = output_root / "AgriculturalDisease_trainingset"
    val_root = output_root / "AgriculturalDisease_validationset"

    train_list, train_count = _write_split(
        split_root=train_root,
        split_name="train",
        classes=classes,
        samples_per_class=train_per_class,
        image_size=image_size,
    )
    val_list, val_count = _write_split(
        split_root=val_root,
        split_name="val",
        classes=classes,
        samples_per_class=val_per_class,
        image_size=image_size,
    )

    print("=" * 70)
    print("模拟数据集生成完成")
    print(f"数据根目录: {output_root}")
    print(f"训练样本: {train_count} | 标注: {train_list}")
    print(f"验证样本: {val_count} | 标注: {val_list}")
    print("目录结构与原赛题兼容，可直接用于 q1new.py")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="生成可用于测试的农业病害模拟数据集")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/mock_problem_b",
        help="输出目录，默认 data/mock_problem_b",
    )
    parser.add_argument("--num-classes", type=int, default=6, help="类别数量，默认6")
    parser.add_argument("--train-per-class", type=int, default=80, help="每类训练样本数，默认80")
    parser.add_argument("--val-per-class", type=int, default=20, help="每类验证样本数，默认20")
    parser.add_argument("--image-size", type=int, default=128, help="图像边长，默认128")

    args = parser.parse_args()

    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    generate_dataset(
        output_root=output_root,
        num_classes=args.num_classes,
        train_per_class=args.train_per_class,
        val_per_class=args.val_per_class,
        image_size=args.image_size,
    )


if __name__ == "__main__":
    main()
