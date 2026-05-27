# -*- coding: utf-8 -*-
"""
农业病害严重程度三分类 + Grad-CAM可视化
任务：基于农作物叶片图像预测病害严重程度（健康、一般疾病、严重疾病）
"""

import os
import random
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import tensorflow as tf
from sklearn.metrics import classification_report, confusion_matrix, f1_score, recall_score, accuracy_score
import json
from collections import Counter
import glob
from tqdm import tqdm

# =========================
# 0. 基本配置
# =========================
# 设置路径
BASE_DIR = "C:/Users/ASUS/Desktop/Problem B：Data"
TRAIN_ROOT = os.path.join(BASE_DIR, "AgriculturalDisease_trainingset")
VAL_ROOT = os.path.join(BASE_DIR, "AgriculturalDisease_validationset")

# 模型参数
IMG_SIZE = 224
BATCH_SIZE = 32
EPOCHS = 25
SEVERITY_CLASSES = 3  # 0:健康, 1:一般疾病, 2:严重疾病

# 十种目标作物
TARGET_CROPS = ["苹果", "樱桃", "玉米", "葡萄", "柑桔", "桃", "辣椒", "马铃薯", "草莓", "番茄"]

# 固定随机种子
random.seed(42)
np.random.seed(42)
tf.random.set_seed(42)

print("当前工作目录:", os.getcwd())
print("TensorFlow版本:", tf.__version__)


# =========================
# 1. 工具函数：查找TXT文件和图像
# =========================
def find_best_txt_file(root_dir):
    """
    查找最佳的TXT文件，优先选择没有(1)后缀的文件
    返回单个文件路径，而不是列表
    """
    txt_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for file in filenames:
            if file.lower().endswith('.txt'):
                txt_files.append(os.path.join(dirpath, file))

    if not txt_files:
        return None

    # 优先选择没有(1)的文件
    primary_files = [f for f in txt_files if '(1)' not in f]
    if primary_files:
        best_file = primary_files[0]
        print(f"选择主TXT文件: {os.path.basename(best_file)}")
    else:
        best_file = txt_files[0]
        print(f"没有找到主文件，使用: {os.path.basename(best_file)}")

    return best_file


def build_image_index(root_dirs):
    """构建图像文件名到路径的映射"""
    image_index = {}
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.JPG', '.JPEG', '.PNG')

    for root_dir in root_dirs:
        if not os.path.exists(root_dir):
            continue

        for root, _, files in os.walk(root_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    full_path = os.path.join(root, file)
                    # 使用文件名（不含扩展名）作为键
                    key = os.path.splitext(file)[0].lower()
                    image_index[key] = full_path

                    # 也添加不含扩展名的版本
                    key_no_ext = os.path.splitext(key)[0]
                    image_index[key_no_ext] = full_path
    return image_index


# =========================
# 2. 病害类别到严重程度的映射
# =========================
def get_crop_type(disease_class):
    """根据病害类别ID获取作物类型"""
    crop_mapping = {
        "苹果": [0, 1, 2, 3, 4, 5],
        "樱桃": [6, 7, 8],
        "玉米": [9, 10, 11, 12, 13, 14, 15, 16],
        "葡萄": [17, 18, 19, 20, 21, 22, 23],
        "柑桔": [24, 25, 26],
        "桃": [27, 28, 29],
        "辣椒": [30, 31, 32],
        "马铃薯": [33, 34, 35, 36, 37],
        "草莓": [38, 39, 40],
        "番茄": [41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60]
    }

    for crop, classes in crop_mapping.items():
        if disease_class in classes:
            return crop
    return "其他"


def disease_to_severity(disease_class):
    """根据病害类别ID映射到严重程度"""
    # 健康类别
    healthy_ids = {0, 6, 9, 17, 27, 30, 33, 38, 41}
    if disease_class in healthy_ids:
        return 0  # 健康

    # 严重疾病类别
    severe_ids = {
        2, 5, 8, 11, 13, 15, 19, 21, 23, 26, 29, 32, 35, 37, 40,
        43, 45, 47, 49, 51, 53, 55, 57, 59
    }
    if disease_class in severe_ids:
        return 2  # 严重疾病

    # 其他类别视为一般疾病
    return 1  # 一般疾病


# =========================
# 3. 数据加载和预处理
# =========================
def parse_txt_annotations(txt_path):
    """解析TXT标注文件"""
    annotations = []
    if not txt_path or not os.path.exists(txt_path):
        return annotations

    print(f"解析标注文件: {os.path.basename(txt_path)}")
    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            image_id = parts[0]
            try:
                disease_class = int(parts[1])
            except ValueError:
                continue

            # 检查是否为重复样本
            is_duplicate = any('duplicate' in p.lower() for p in parts[2:])
            if is_duplicate:
                continue

            annotations.append({
                'image_id': image_id,
                'disease_class': disease_class,
                'duplicate': is_duplicate
            })

    print(f"解析到 {len(annotations)} 个标注")
    return annotations


def build_samples_from_annotations(annotations, image_index, split_name):
    """从标注构建样本"""
    samples = []
    missing_count = 0

    for ann in tqdm(annotations, desc=f"处理{split_name}数据"):
        image_id = ann['image_id']
        disease_class = ann['disease_class']

        # 获取作物类型
        crop_type = get_crop_type(disease_class)
        if crop_type not in TARGET_CROPS:
            continue  # 跳过非目标作物

        # 映射到严重程度
        severity = disease_to_severity(disease_class)

        # 查找图像文件
        image_key = os.path.splitext(os.path.basename(image_id))[0].lower()
        image_path = image_index.get(image_key)

        if image_path and os.path.exists(image_path):
            samples.append({
                'image_path': image_path,
                'disease_class': disease_class,
                'crop_type': crop_type,
                'severity': severity,
                'split': split_name
            })
        else:
            missing_count += 1
            if missing_count <= 5:  # 只打印前5个缺失文件
                print(f"警告: 未找到图像文件: {image_id}")

    return samples, missing_count


def load_and_preprocess_data():
    """加载和预处理所有数据"""
    print("正在查找数据文件...")

    # 查找最佳TXT文件（避免重复）
    train_txt = find_best_txt_file(TRAIN_ROOT)
    val_txt = find_best_txt_file(VAL_ROOT)

    if not train_txt or not val_txt:
        print("错误: 未找到必要的TXT文件")
        return [], []

    # 构建图像索引
    print("构建图像索引...")
    image_index = build_image_index([TRAIN_ROOT, VAL_ROOT])
    print(f"找到图像文件: {len(image_index)}个")

    # 解析标注
    train_annotations = parse_txt_annotations(train_txt)
    val_annotations = parse_txt_annotations(val_txt)

    # 构建样本
    print("构建训练样本...")
    train_samples, miss_train = build_samples_from_annotations(train_annotations, image_index, "train")

    print("构建验证样本...")
    val_samples, miss_val = build_samples_from_annotations(val_annotations, image_index, "val")

    print(f"\n数据统计:")
    print(f"训练集样本数: {len(train_samples)} (缺失: {miss_train})")
    print(f"验证集样本数: {len(val_samples)} (缺失: {miss_val})")

    if not train_samples or not val_samples:
        print("错误: 没有找到足够的数据样本")
        return [], []

    # 分析严重程度分布
    train_severities = [s['severity'] for s in train_samples]
    val_severities = [s['severity'] for s in val_samples]

    severity_names = ["健康", "一般疾病", "严重疾病"]
    print("\n训练集严重程度分布:")
    for i in range(SEVERITY_CLASSES):
        count = train_severities.count(i)
        percentage = count / len(train_severities) * 100 if train_severities else 0
        print(f"  {severity_names[i]}: {count}样本 ({percentage:.1f}%)")

    print("\n验证集严重程度分布:")
    for i in range(SEVERITY_CLASSES):
        count = val_severities.count(i)
        percentage = count / len(val_severities) * 100 if val_severities else 0
        print(f"  {severity_names[i]}: {count}样本 ({percentage:.1f}%)")

    return train_samples, val_samples


# =========================
# 4. 数据管道和增强
# =========================
def load_and_preprocess_image(path, label):
    """加载和预处理单个图像"""
    img = tf.io.read_file(path)
    img = tf.image.decode_image(img, channels=3, expand_animations=False)
    img = tf.image.convert_image_dtype(img, tf.float32)
    img = tf.image.resize(img, [IMG_SIZE, IMG_SIZE])
    return img, label


def create_data_augmentation():
    """创建数据增强管道"""
    return tf.keras.Sequential([
        tf.keras.layers.RandomFlip("horizontal"),
        tf.keras.layers.RandomRotation(0.1),
        tf.keras.layers.RandomZoom(0.1),
        tf.keras.layers.RandomContrast(0.2),
    ], name="data_augmentation")


def create_dataset(samples, batch_size=32, training=True):
    """创建TensorFlow数据集"""
    image_paths = [s['image_path'] for s in samples]
    labels = [s['severity'] for s in samples]

    dataset = tf.data.Dataset.from_tensor_slices((image_paths, labels))

    if training:
        dataset = dataset.shuffle(len(samples))

    dataset = dataset.map(
        load_and_preprocess_image,
        num_parallel_calls=tf.data.AUTOTUNE
    )

    if training:
        augmentation = create_data_augmentation()
        dataset = dataset.map(
            lambda img, label: (augmentation(img, training=True), label),
            num_parallel_calls=tf.data.AUTOTUNE
        )

    dataset = dataset.batch(batch_size)
    dataset = dataset.prefetch(tf.data.AUTOTUNE)

    return dataset


# =========================
# 5. 模型定义
# =========================
def create_model():
    """创建ResNet50基础的三分类模型"""
    # 使用预训练的ResNet50作为特征提取器
    base_model = tf.keras.applications.ResNet50(
        include_top=False,
        weights='imagenet',
        input_shape=(IMG_SIZE, IMG_SIZE, 3),
        pooling='avg'
    )

    # 冻结基础模型的前面层
    for layer in base_model.layers[:-20]:
        layer.trainable = False

    # 添加自定义分类头
    inputs = tf.keras.Input(shape=(IMG_SIZE, IMG_SIZE, 3))
    x = base_model(inputs, training=False)
    x = tf.keras.layers.Dropout(0.5)(x)
    x = tf.keras.layers.Dense(256, activation='relu')(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    outputs = tf.keras.layers.Dense(SEVERITY_CLASSES, activation='softmax')(x)

    model = tf.keras.Model(inputs, outputs)

    # 编译模型
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )

    return model


# =========================
# 6. 训练和评估
# =========================
def train_and_evaluate():
    """训练和评估模型"""
    # 加载数据
    train_samples, val_samples = load_and_preprocess_data()

    if not train_samples or not val_samples:
        print("错误: 没有足够的数据进行训练")
        return None, None, None

    # 创建数据集
    train_dataset = create_dataset(train_samples, BATCH_SIZE, training=True)
    val_dataset = create_dataset(val_samples, BATCH_SIZE, training=False)

    # 创建模型
    model = create_model()
    model.summary()

    # 回调函数
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            patience=10,
            restore_best_weights=True,
            verbose=1
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            factor=0.5,
            patience=5,
            verbose=1
        ),
        tf.keras.callbacks.ModelCheckpoint(
            'best_severity_model.h5',
            save_best_only=True,
            monitor='val_loss',
            verbose=1
        )
    ]

    # 训练模型
    print("\n开始训练模型...")
    history = model.fit(
        train_dataset,
        epochs=EPOCHS,
        validation_data=val_dataset,
        callbacks=callbacks,
        verbose=1
    )

    # 评估模型
    print("\n评估模型...")
    val_loss, val_accuracy = model.evaluate(val_dataset, verbose=0)
    print(f"验证损失: {val_loss:.4f}")
    print(f"验证准确率: {val_accuracy:.4f}")

    # 生成预测
    print("\n生成预测...")
    all_true = []
    all_pred = []

    for images, labels in val_dataset:
        predictions = model.predict(images, verbose=0)
        pred_classes = np.argmax(predictions, axis=1)

        all_true.extend(labels.numpy())
        all_pred.extend(pred_classes)

    # 计算评估指标
    accuracy = accuracy_score(all_true, all_pred)
    macro_f1 = f1_score(all_true, all_pred, average='macro')
    recall_scores = recall_score(all_true, all_pred, average=None)

    print(f"\n=== 最终评估结果 ===")
    print(f"准确率: {accuracy:.4f}")
    print(f"宏平均F1: {macro_f1:.4f}")

    severity_names = ["健康", "一般疾病", "严重疾病"]
    print("各类别召回率:")
    for i in range(SEVERITY_CLASSES):
        print(f"  {severity_names[i]}: {recall_scores[i]:.4f}")

    # 分类报告
    print("\n分类报告:")
    print(classification_report(all_true, all_pred, target_names=severity_names, digits=4))

    # 混淆矩阵
    cm = confusion_matrix(all_true, all_pred)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=severity_names, yticklabels=severity_names)
    plt.title('病害严重程度混淆矩阵')
    plt.ylabel('真实标签')
    plt.xlabel('预测标签')
    plt.tight_layout()
    plt.savefig('severity_confusion_matrix.png', dpi=300, bbox_inches='tight')
    plt.show()

    # 训练历史可视化
    plt.figure(figsize=(12, 4))

    plt.subplot(1, 2, 1)
    plt.plot(history.history['loss'], label='训练损失')
    plt.plot(history.history['val_loss'], label='验证损失')
    plt.title('训练和验证损失')
    plt.xlabel('Epoch')
    plt.ylabel('损失')
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(history.history['accuracy'], label='训练准确率')
    plt.plot(history.history['val_accuracy'], label='验证准确率')
    plt.title('训练和验证准确率')
    plt.xlabel('Epoch')
    plt.ylabel('准确率')
    plt.legend()

    plt.tight_layout()
    plt.savefig('training_history.png', dpi=300, bbox_inches='tight')
    plt.show()

    return model, all_true, all_pred


# =========================
# 7. Grad-CAM 可视化
# =========================
def make_gradcam_heatmap(img_array, model, last_conv_layer_name, pred_index=None):
    """生成Grad-CAM热力图"""
    grad_model = tf.keras.models.Model(
        [model.inputs],
        [model.get_layer(last_conv_layer_name).output, model.output]
    )

    with tf.GradientTape() as tape:
        conv_outputs, predictions = grad_model(img_array)
        if pred_index is None:
            pred_index = tf.argmax(predictions[0])
        class_channel = predictions[:, pred_index]

    grads = tape.gradient(class_channel, conv_outputs)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

    conv_outputs = conv_outputs[0]
    heatmap = conv_outputs @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)

    # 归一化热力图
    heatmap = tf.maximum(heatmap, 0) / tf.math.reduce_max(heatmap)
    return heatmap.numpy()


def visualize_gradcam(model, samples, num_samples=9):
    """可视化Grad-CAM"""
    # 获取最后卷积层的名称
    last_conv_layer_name = None
    for layer in model.layers[::-1]:
        if isinstance(layer, tf.keras.layers.Conv2D):
            last_conv_layer_name = layer.name
            break

    if not last_conv_layer_name:
        print("未找到卷积层，无法生成Grad-CAM")
        return

    # 选择样本进行可视化
    plt.figure(figsize=(15, 10))
    selected_samples = random.sample(samples, min(num_samples, len(samples)))

    for i, sample in enumerate(selected_samples):
        img_path = sample['image_path']
        true_severity = sample['severity']
        crop_type = sample['crop_type']

        # 加载和预处理图像
        img = tf.io.read_file(img_path)
        img = tf.image.decode_image(img, channels=3, expand_animations=False)
        img = tf.image.convert_image_dtype(img, tf.float32)
        img = tf.image.resize(img, [IMG_SIZE, IMG_SIZE])
        img_array = tf.expand_dims(img, axis=0)

        # 预测
        predictions = model.predict(img_array, verbose=0)
        pred_severity = np.argmax(predictions[0])

        # 生成热力图
        heatmap = make_gradcam_heatmap(img_array, model, last_conv_layer_name, pred_severity)

        # 显示原图和热力图
        plt.subplot(3, 3, i + 1)
        plt.imshow(img.numpy())
        plt.imshow(heatmap, alpha=0.5, cmap='jet')
        plt.title(f'{crop_type}\nTrue: {true_severity}, Pred: {pred_severity}')
        plt.axis('off')

    plt.tight_layout()
    plt.savefig('gradcam_visualization.png', dpi=300, bbox_inches='tight')
    plt.show()


# =========================
# 8. 主函数
# =========================
def main():
    """主函数"""
    print("开始农业病害严重程度三分类任务...")

    # 训练和评估模型
    model, true_labels, pred_labels = train_and_evaluate()

    if model is not None:
        # 加载验证集数据进行Grad-CAM可视化
        _, val_samples = load_and_preprocess_data()
        if val_samples:
            print("\n生成Grad-CAM可视化...")
            visualize_gradcam(model, val_samples)

        print("\n任务完成！")
        print("生成的文件:")
        print("- severity_confusion_matrix.png: 混淆矩阵")
        print("- training_history.png: 训练历史")
        print("- gradcam_visualization.png: Grad-CAM可视化")
        print("- best_severity_model.h5: 最佳模型权重")
    else:
        print("任务失败，请检查数据和配置")


if __name__ == "__main__":
    main()