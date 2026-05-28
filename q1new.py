import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
import argparse
import glob
import os
from datetime import datetime

import cv2
import matplotlib.pyplot as plt
import matplotlib.font_manager as font_manager
import numpy as np
import seaborn as sns
from sklearn.metrics import accuracy_score, f1_score
from tqdm import tqdm
import torchvision.transforms as transforms
from torchvision.models import MobileNet_V2_Weights
from torchvision.datasets import ImageFolder
from PIL import Image


def configure_chinese_font():
    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    preferred_fonts = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]
    chosen_font = next((font_name for font_name in preferred_fonts if font_name in available_fonts), None)

    if chosen_font:
        plt.rcParams["font.sans-serif"] = [chosen_font]
    else:
        plt.rcParams["font.sans-serif"] = preferred_fonts
    plt.rcParams["axes.unicode_minus"] = False


configure_chinese_font()

def find_data_files(base_dir=None):
    # 优先级: 显式参数 > 环境变量 > 项目内默认测试数据目录
    if base_dir is None:
        base_dir = os.environ.get("AGRI_DATA_DIR", "data/mock_problem_b")

    if not os.path.exists(base_dir):
        raise FileNotFoundError(
            f"数据根目录不存在: {base_dir}。请使用 --data-dir 指定，或设置环境变量 AGRI_DATA_DIR"
        )

    data_files = {'train_txt': None, 'train_dir': None, 'val_txt': None, 'val_dir': None}
    problem_b_dir = base_dir
    # 自动定位附件数据根目录
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path) and "Problem B" in item and "Data" in item:
            problem_b_dir = item_path
            break
    print(f"数据根目录: {problem_b_dir}")

    def find_best_txt(root):
        txt_files = []
        for dirpath, _, filenames in os.walk(root):
            for file in filenames:
                if file.lower().endswith('.txt'):
                    txt_files.append(os.path.join(dirpath, file))
        if not txt_files:
            return None
        primary_files = [f for f in txt_files if '(1)' not in f]
        return primary_files[0] if primary_files else txt_files[0]

    # 定位训练集与验证集路径
    train_dir = os.path.join(problem_b_dir, 'AgriculturalDisease_trainingset', 'images')
    data_files['train_dir'] = train_dir if os.path.exists(train_dir) else None
    data_files['train_txt'] = find_best_txt(os.path.join(problem_b_dir, 'AgriculturalDisease_trainingset'))

    val_dir = os.path.join(problem_b_dir, 'AgriculturalDisease_validationset', 'images')
    data_files['val_dir'] = val_dir if os.path.exists(val_dir) else None
    data_files['val_txt'] = find_best_txt(os.path.join(problem_b_dir, 'AgriculturalDisease_validationset'))

    # 打印数据查找结果
    for key, desc in [('train_dir', '训练集images目录'), ('val_dir', '验证集images目录'),
                      ('train_txt', '训练集TXT标注文件'), ('val_txt', '验证集TXT标注文件')]:
        if data_files[key] and os.path.exists(data_files[key]):
            print(f"✅ 找到{desc}: {data_files[key]}")
        else:
            print(f"❌ 未找到{desc}，请检查数据路径！")
    return data_files


def parse_txt_annotations(txt_path):
    annotations = []
    if not txt_path or not os.path.exists(txt_path):
        return annotations
    print(f"解析TXT标注文件: {txt_path}")
    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
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
            is_duplicate = any('duplicate' in p.lower() for p in parts[2:])
            if not is_duplicate:
                annotations.append({'image_id': image_id, 'disease_class': disease_class})
    print(f"解析到 {len(annotations)} 个有效标注样本")
    return annotations


def build_image_index(data_dirs):
    image_index = {}
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp')
    for data_dir in data_dirs:
        if not os.path.exists(data_dir):
            continue
        for root, _, files in os.walk(data_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    full_path = os.path.join(root, file)
                    key = os.path.splitext(file)[0].lower()
                    image_index[key] = full_path
                    image_index[os.path.splitext(key)[0]] = full_path
    return image_index


def _normalize_label_name(label_name):
    return str(label_name).replace('_', ' ').replace('-', ' ').strip().lower()


def infer_severity_from_name(label_name):
    name = _normalize_label_name(label_name)
    if any(keyword in name for keyword in ['healthy', 'normal', 'health']):
        return 0
    if any(keyword in name for keyword in ['blight', 'rust', 'virus', 'mildew', 'rot', 'scab', 'canker', 'spot', 'smut', 'burn']):
        return 2
    return 1


def get_disease_details(disease_label):
    if isinstance(disease_label, int):
        return DISEASE_DETAILS.get(disease_label, {
            "name": f"未知病害_{disease_label}",
            "description": "该病害暂无详细描述信息（可参考公开数据集类别名补充）",
            "suggestion": "建议结合数据集标签与农学知识进行人工复核"
        })

    label_name = str(disease_label)
    return {
        "name": label_name,
        "description": f"公开数据集类别：{label_name}",
        "suggestion": "建议结合公开数据集说明文档与农学经验进一步诊断"
    }


def get_crop_type(disease_class):
    """根据附件文档的10种目标作物映射（兼容公开数据集的类别名）"""
    if isinstance(disease_class, str):
        label = _normalize_label_name(disease_class)
        keyword_mapping = {
            '苹果': ['apple', '苹果'],
            '樱桃': ['cherry', '樱桃'],
            '玉米': ['corn', 'maize', '玉米'],
            '葡萄': ['grape', '葡萄'],
            '柑桔': ['citrus', 'orange', '柑橘', '柑桔'],
            '桃': ['peach', '桃'],
            '辣椒': ['pepper', 'chili', '辣椒'],
            '马铃薯': ['potato', '马铃薯'],
            '草莓': ['strawberry', '草莓'],
            '番茄': ['tomato', '番茄']
        }
        for crop, keywords in keyword_mapping.items():
            if any(keyword in label for keyword in keywords):
                return crop
        return "其他"

    crop_mapping = {
        "苹果": [0, 1, 2, 3, 4, 5], "樱桃": [6, 7, 8],
        "玉米": [9, 10, 11, 12, 13, 14, 15, 16], "葡萄": [17, 18, 19, 20, 21, 22, 23],
        "柑桔": [24, 25, 26], "桃": [27, 28, 29], "辣椒": [30, 31, 32],
        "马铃薯": [33, 34, 35, 36, 37], "草莓": [38, 39, 40],
        "番茄": [41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60]
    }
    for crop, classes in crop_mapping.items():
        if disease_class in classes:
            return crop
    return "其他"


def disease_to_severity(disease_class):
    """将附件文档的61类标签映射为健康/一般/严重三级"""
    if isinstance(disease_class, str):
        return infer_severity_from_name(disease_class)

    # 健康类别（附件文档中10个健康标签，对应ID：0、6、9、17、27、30、33、38、41）
    healthy_ids = {0, 6, 9, 17, 27, 30, 33, 38, 41}
    if disease_class in healthy_ids:
        return 0  # 健康
    # 严重疾病类别（附件文档中24个严重等级标签）
    severe_ids = {2, 5, 8, 11, 13, 15, 19, 21, 23, 26, 29, 32, 35, 37, 40, 43, 45, 47, 49, 51, 53, 55, 57, 59}
    if disease_class in severe_ids:
        return 2  # 严重疾病
    return 1  # 一般疾病


def find_public_data_files(base_dir):
    """查找公开数据集的 train/val 文件夹模式。"""
    candidates = [base_dir]
    for name in ['train', 'training', 'train_set', 'trainingset']:
        candidates.append(os.path.join(base_dir, name))
    for name in ['val', 'valid', 'validation', 'validationset', 'test']:
        candidates.append(os.path.join(base_dir, name))

    train_root = None
    val_root = None
    for path in candidates:
        if os.path.isdir(path) and any(os.path.isdir(os.path.join(path, child)) for child in os.listdir(path)):
            lower = os.path.basename(path).lower()
            if 'train' in lower and train_root is None:
                train_root = path
            if any(keyword in lower for keyword in ['val', 'valid', 'test']) and val_root is None:
                val_root = path

    if train_root is None:
        train_root = os.path.join(base_dir, 'train') if os.path.isdir(os.path.join(base_dir, 'train')) else base_dir
    if val_root is None:
        val_root = os.path.join(base_dir, 'val') if os.path.isdir(os.path.join(base_dir, 'val')) else base_dir

    return {'train_dir': train_root, 'val_dir': val_root}


# ========== 4. 多任务数据集（支持附件文档的双任务标签加载） ==========
class MultiTaskDataset(Dataset):
    def __init__(self, data_dir, txt_file=None, transform=None, sample_ratio=1.0):
        self.data_dir = data_dir
        self.transform = transform
        self.image_paths = []
        self.disease_labels = []
        self.severity_labels = []
        self.disease_mapping = {}
        self.num_diseases = 0
        self.image_filenames = []

        if txt_file and os.path.exists(txt_file):
            print(f"\n从TXT标注文件加载数据集: {txt_file}")
            self._load_from_txt(txt_file, sample_ratio)
        else:
            print(f"\n从图像目录加载数据集: {data_dir}")
            self._load_from_directory(sample_ratio)

        if len(self.image_paths) == 0:
            raise ValueError("数据集加载失败！请检查数据路径或TXT标注文件是否正确")

        # 构建疾病类别映射（适配附件文档的61类）
        all_diseases = list(set(self.disease_labels))
        self.disease_mapping = {disease: idx for idx, disease in enumerate(all_diseases)}
        self.num_diseases = len(self.disease_mapping)
        self.disease_labels = [self.disease_mapping[label] for label in self.disease_labels]

        print(f"数据集加载成功: 共{len(self.image_paths)}个样本，{self.num_diseases}种疾病类别")

    def _load_from_txt(self, txt_file, sample_ratio):
        image_index = build_image_index([self.data_dir])
        annotations = parse_txt_annotations(txt_file)
        if sample_ratio < 1.0:
            sample_size = int(len(annotations) * sample_ratio)
            annotations = annotations[:sample_size]

        for item in tqdm(annotations, desc="解析TXT标注"):
            image_id = item['image_id']
            disease_class = item['disease_class']
            image_key = os.path.splitext(os.path.basename(image_id))[0].lower()
            image_path = image_index.get(image_key)

            if image_path and os.path.exists(image_path):
                self.image_paths.append(image_path)
                self.image_filenames.append(os.path.basename(image_path))
                self.disease_labels.append(disease_class)
                self.severity_labels.append(disease_to_severity(disease_class))

    def _load_from_directory(self, sample_ratio):
        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(f"图像目录不存在: {self.data_dir}")
        image_extensions = ['*.jpg', '*.jpeg', '*.png']
        image_files = []
        for ext in image_extensions:
            image_files.extend(glob.glob(os.path.join(self.data_dir, '**', ext), recursive=True))
        if sample_ratio < 1.0:
            sample_size = int(len(image_files) * sample_ratio)
            image_files = image_files[:sample_size]

        print(f"从目录找到 {len(image_files)} 张图像")
        for img_path in tqdm(image_files, desc="加载图像"):
            filename = os.path.basename(img_path)
            self.image_filenames.append(filename)
            disease_class = self._infer_disease_from_filename(filename)
            self.image_paths.append(img_path)
            self.disease_labels.append(disease_class)
            self.severity_labels.append(disease_to_severity(disease_class))

    def _infer_disease_from_filename(self, filename):
        match = re.match(r'^(\d+)_', filename)
        if match:
            return int(match.group(1))
        elif filename.split('.')[0].isdigit():
            return int(filename.split('.')[0])
        return 0  # 默认健康

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        try:
            image = Image.open(self.image_paths[idx]).convert('RGB')
            disease_label = self.disease_labels[idx]
            severity_label = self.severity_labels[idx]
            filename = self.image_filenames[idx]
            if self.transform:
                image = self.transform(image)
            return image, disease_label, severity_label, filename
        except Exception as e:
            # 异常图像返回默认黑色图
            default_image = Image.new('RGB', (128, 128), color='black')
            if self.transform:
                default_image = self.transform(default_image)
            return default_image, 0, 0, "error_image.jpg"


class PublicFolderDataset(Dataset):
    """适配公开数据集文件夹结构：root/class_name/image.jpg"""

    def __init__(self, data_dir, transform=None, sample_ratio=1.0):
        self.data_dir = data_dir
        self.transform = transform
        self.image_paths = []
        self.disease_labels = []
        self.severity_labels = []
        self.image_filenames = []
        self.class_names = []
        self.disease_mapping = {}
        self.num_diseases = 0

        self._load_from_folder(sample_ratio)

    def _load_from_folder(self, sample_ratio):
        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(f"公开数据集目录不存在: {self.data_dir}")

        class_dirs = [d for d in sorted(os.listdir(self.data_dir)) if os.path.isdir(os.path.join(self.data_dir, d))]
        if not class_dirs:
            raise ValueError(f"未在目录中找到类别子文件夹: {self.data_dir}")

        self.class_names = class_dirs
        self.disease_mapping = {idx: name for idx, name in enumerate(self.class_names)}
        self.num_diseases = len(self.class_names)

        for class_idx, class_name in enumerate(self.class_names):
            class_dir = os.path.join(self.data_dir, class_name)
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.JPG', '*.JPEG', '*.PNG', '*.BMP']:
                image_files.extend(glob.glob(os.path.join(class_dir, '**', ext), recursive=True))

            if sample_ratio < 1.0:
                sample_size = max(1, int(len(image_files) * sample_ratio))
                image_files = image_files[:sample_size]

            for img_path in image_files:
                self.image_paths.append(img_path)
                self.image_filenames.append(os.path.basename(img_path))
                self.disease_labels.append(class_idx)
                self.severity_labels.append(infer_severity_from_name(class_name))

        print(f"公开数据集加载成功: 共{len(self.image_paths)}个样本，{self.num_diseases}种疾病类别")

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        try:
            image = Image.open(self.image_paths[idx]).convert('RGB')
            disease_label = self.disease_labels[idx]
            severity_label = self.severity_labels[idx]
            filename = self.image_filenames[idx]
            if self.transform:
                image = self.transform(image)
            return image, disease_label, severity_label, filename
        except Exception:
            default_image = Image.new('RGB', (128, 128), color='black')
            if self.transform:
                default_image = self.transform(default_image)
            return default_image, 0, 0, "error_image.jpg"


# ========== 5. 多任务网络模型（双任务协同+轻量部署适配） ==========
class CrossTaskAttention(nn.Module):
    def __init__(self, input_dim, hidden_dim):
        super().__init__()
        self.disease_query = nn.Linear(input_dim, hidden_dim)
        self.severity_query = nn.Linear(input_dim, hidden_dim)
        self.value_proj = nn.Linear(input_dim, hidden_dim)

    def forward(self, x):
        # x: (batch_size, input_dim) → (batch, 1280)
        disease_q = self.disease_query(x)  # (batch, 256)
        severity_q = self.severity_query(x)  # (batch, 256)
        value = self.value_proj(x)  # (batch, 256)

        # 计算注意力权重（修复维度逻辑）
        disease_attention = torch.softmax(torch.sum(disease_q * value, dim=1, keepdim=True), dim=1)
        severity_attention = torch.softmax(torch.sum(severity_q * value, dim=1, keepdim=True), dim=1)

        # 应用注意力权重（输出维度：batch×256）
        disease_features = disease_attention * value
        severity_features = severity_attention * value

        return disease_features, severity_features


class MultiTaskNetwork(nn.Module):
    def __init__(self, num_diseases, num_severity=3):
        super().__init__()
        # 加载MobileNetV2（修复pretrained警告）
        self.backbone = torch.hub.load('pytorch/vision:v0.10.0', 'mobilenet_v2',
                                       weights=MobileNet_V2_Weights.IMAGENET1K_V1)
        self.feature_extractor = self.backbone.features  # 用于Grad-CAM的特征提取层
        self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc_input_dim = 1280  # MobileNetV2输出维度

        # 冻结大部分层，仅训练最后3层
        for param in list(self.feature_extractor.parameters())[:-3]:
            param.requires_grad = False

        # 交叉注意力机制（输入1280，输出256）
        self.cross_attention = CrossTaskAttention(self.fc_input_dim, 256)

        # 疾病分类头（输入256，输出num_diseases）
        self.disease_head = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(128, num_diseases)
        )

        # 严重程度分类头（输入256，输出3）
        self.severity_head = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(128, num_severity)
        )

        # 统计参数数量
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        print(f"模型总参数: {total_params:,} (可训练: {trainable_params:,})")

    def forward(self, x):
        # 特征提取：(batch,3,128,128) → (batch,1280,4,4)
        features = self.feature_extractor(x)
        # 全局平均池化：(batch,1280,4,4) → (batch,1280)
        shared_features = self.avg_pool(features).view(features.size(0), -1)
        # 交叉注意力：(batch,1280) → (batch,256) × 2
        disease_features, severity_features = self.cross_attention(shared_features)
        # 双任务输出
        disease_output = self.disease_head(disease_features)
        severity_output = self.severity_head(severity_features)
        return disease_output, severity_output, features


# ========== 6. 单任务模型（用于协同效应评估） ==========
class SingleTaskDiseaseModel(nn.Module):
    """仅疾病分类的单任务模型（与多任务共享骨干）"""

    def __init__(self, num_diseases):
        super().__init__()
        self.backbone = torch.hub.load('pytorch/vision:v0.10.0', 'mobilenet_v2',
                                       weights=MobileNet_V2_Weights.IMAGENET1K_V1)
        # 冻结前N-3层，与多任务模型一致
        for param in list(self.backbone.features.parameters())[:-3]:
            param.requires_grad = False
        # 替换分类头（仅疾病分类）
        self.backbone.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(1280, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(128, num_diseases)
        )

        # 参数统计
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        print(f"单任务疾病模型总参数: {total_params:,} (可训练: {trainable_params:,})")

    def forward(self, x):
        return self.backbone(x)


class SingleTaskSeverityModel(nn.Module):
    """仅严重程度分级的单任务模型（与多任务共享骨干）"""

    def __init__(self, num_severity=3):
        super().__init__()
        self.backbone = torch.hub.load('pytorch/vision:v0.10.0', 'mobilenet_v2',
                                       weights=MobileNet_V2_Weights.IMAGENET1K_V1)
        # 冻结前N-3层，与多任务模型一致
        for param in list(self.backbone.features.parameters())[:-3]:
            param.requires_grad = False
        # 替换分类头（仅严重程度分级）
        self.backbone.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(1280, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(128, num_severity)
        )

        # 参数统计
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        print(f"单任务严重程度模型总参数: {total_params:,} (可训练: {trainable_params:,})")

    def forward(self, x):
        return self.backbone(x)


# ========== 7. 多任务/单任务训练器（统一训练条件） ==========
class TaskTrainer:
    def __init__(self, model, task_type="multitask", num_diseases=None, num_severity=3):
        self.model = model
        self.task_type = task_type  # "multitask", "disease", "severity"
        self.criterion = nn.CrossEntropyLoss()
        # 统一优化器配置（确保对比公平）
        self.optimizer = optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-4)
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(self.optimizer, 'min', patience=3, factor=0.5)
        self.num_diseases = num_diseases
        self.num_severity = num_severity

    def train_epoch(self, dataloader, device):
        self.model.train()
        total_loss = 0.0
        correct = 0
        total_samples = 0

        for batch_idx, (images, disease_labels, severity_labels, _) in enumerate(dataloader):
            images = images.to(device)
            if self.task_type == "disease":
                labels = disease_labels.to(device)
            elif self.task_type == "severity":
                labels = severity_labels.to(device)
            else:
                disease_labels = disease_labels.to(device)
                severity_labels = severity_labels.to(device)

            self.optimizer.zero_grad()
            if self.task_type == "disease":
                outputs = self.model(images)
                loss = self.criterion(outputs, labels)
            elif self.task_type == "severity":
                outputs = self.model(images)
                loss = self.criterion(outputs, labels)
            else:
                disease_output, severity_output, _ = self.model(images)
                disease_loss = self.criterion(disease_output, disease_labels)
                severity_loss = self.criterion(severity_output, severity_labels)
                loss = 1.0 * disease_loss + 0.8 * severity_loss  # 与多任务一致的权重

            loss.backward()
            self.optimizer.step()

            total_loss += loss.item()
            if self.task_type != "multitask":
                _, preds = torch.max(outputs, 1)
                correct += (preds == labels).sum().item()
                total_samples += labels.size(0)

        avg_loss = total_loss / len(dataloader)
        if self.task_type != "multitask":
            acc = 100. * correct / total_samples
            return avg_loss, acc
        return avg_loss

    def evaluate(self, dataloader, device):
        self.model.eval()
        all_preds = []
        all_labels = []
        total_loss = 0.0

        with torch.no_grad():
            for images, disease_labels, severity_labels, _ in dataloader:
                images = images.to(device)
                if self.task_type == "disease":
                    labels = disease_labels.to(device)
                    outputs = self.model(images)
                elif self.task_type == "severity":
                    labels = severity_labels.to(device)
                    outputs = self.model(images)
                else:
                    # 多任务评估需返回双任务结果
                    return self._eval_multitask(images, disease_labels, severity_labels, device)

                loss = self.criterion(outputs, labels)
                total_loss += loss.item()
                _, preds = torch.max(outputs, 1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        avg_loss = total_loss / len(dataloader)
        acc = 100. * accuracy_score(all_labels, all_preds)
        f1 = f1_score(all_labels, all_preds, average='macro', zero_division=0)
        return avg_loss, acc, f1

    def _eval_multitask(self, images, disease_labels, severity_labels, device):
        """多任务专用评估函数：返回输出、标签、损失、准确率、F1"""
        disease_labels = disease_labels.to(device)
        severity_labels = severity_labels.to(device)
        disease_output, severity_output, _ = self.model(images)

        # 计算损失
        disease_loss = self.criterion(disease_output, disease_labels)
        severity_loss = self.criterion(severity_output, severity_labels)
        total_loss = (1.0 * disease_loss + 0.8 * severity_loss).item()

        # 计算准确率和F1
        _, d_preds = torch.max(disease_output, 1)
        _, s_preds = torch.max(severity_output, 1)
        d_acc = 100. * accuracy_score(disease_labels.cpu().numpy(), d_preds.cpu().numpy())
        d_f1 = f1_score(disease_labels.cpu().numpy(), d_preds.cpu().numpy(), average='macro', zero_division=0)
        s_acc = 100. * accuracy_score(severity_labels.cpu().numpy(), s_preds.cpu().numpy())
        s_f1 = f1_score(severity_labels.cpu().numpy(), s_preds.cpu().numpy(), average='macro', zero_division=0)

        return disease_output, severity_output, disease_labels, severity_labels, total_loss, d_acc, d_f1, s_acc, s_f1


# ========== 8. 协同效应计算与可视化（核心补充模块） ==========
def calculate_synergy(mt_metrics, st_disease_metrics, st_severity_metrics):
    """
    计算协同效应：多任务性能 - 单任务性能
    mt_metrics: (d_acc, d_f1, s_acc, s_f1) 多任务指标
    st_disease_metrics: (acc, f1) 单任务疾病指标
    st_severity_metrics: (acc, f1) 单任务严重程度指标
    """
    mt_d_acc, mt_d_f1, mt_s_acc, mt_s_f1 = mt_metrics
    st_d_acc, st_d_f1 = st_disease_metrics
    st_s_acc, st_s_f1 = st_severity_metrics

    # 计算协同增益
    d_acc_gain = mt_d_acc - st_d_acc
    d_f1_gain = mt_d_f1 - st_d_f1
    s_acc_gain = mt_s_acc - st_s_acc
    s_f1_gain = mt_s_f1 - st_s_f1
    avg_acc_gain = (d_acc_gain + s_acc_gain) / 2
    avg_f1_gain = (d_f1_gain + s_f1_gain) / 2

    # 打印协同效应结果
    print("\n" + "=" * 60)
    print("多任务协同效应评估结果（基于附件文档数据集）")
    print("=" * 60)
    print(f"{'任务':<15} {'多任务性能':<15} {'单任务性能':<15} {'协同增益':<15}")
    print("-" * 60)
    print(f"疾病分类准确率   {mt_d_acc:<15.2f}% {st_d_acc:<15.2f}% +{d_acc_gain:<14.2f}个百分点")
    print(f"疾病分类F1       {mt_d_f1:<15.4f} {st_d_f1:<15.4f} +{d_f1_gain:<14.4f}")
    print(f"严重程度准确率   {mt_s_acc:<15.2f}% {st_s_acc:<15.2f}% +{s_acc_gain:<14.2f}个百分点")
    print(f"严重程度F1       {mt_s_f1:<15.4f} {st_s_f1:<15.4f} +{s_f1_gain:<14.4f}")
    print("-" * 60)
    print(
        f"平均协同增益     -                -                准确率+{avg_acc_gain:.2f}个百分点 / F1+{avg_f1_gain:.4f}")
    print("=" * 60)

    # 可视化协同效应
    visualize_synergy(mt_metrics, st_disease_metrics, st_severity_metrics)
    return avg_acc_gain, avg_f1_gain


def visualize_synergy(mt_metrics, st_disease_metrics, st_severity_metrics):
    """可视化多任务与单任务性能对比"""
    mt_d_acc, mt_d_f1, mt_s_acc, mt_s_f1 = mt_metrics
    st_d_acc, st_d_f1 = st_disease_metrics
    st_s_acc, st_s_f1 = st_severity_metrics

    # 准备数据
    tasks = ['疾病分类\n准确率(%)', '疾病分类\nF1', '严重程度\n准确率(%)', '严重程度\nF1']
    mt_values = [mt_d_acc, mt_d_f1, mt_s_acc, mt_s_f1]
    st_values = [st_d_acc, st_d_f1, st_s_acc, st_s_f1]

    # 调整F1值范围（与准确率统一可视化）
    mt_values[1] *= 100
    mt_values[3] *= 100
    st_values[1] *= 100
    st_values[3] *= 100

    # 创建柱状图
    x = np.arange(len(tasks))
    width = 0.35

    plt.figure(figsize=(12, 6))
    bars1 = plt.bar(x - width / 2, mt_values, width, label='多任务模型', color='#2E86AB', alpha=0.8)
    bars2 = plt.bar(x + width / 2, st_values, width, label='单任务模型', color='#A23B72', alpha=0.8)

    # 添加数值标签
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2., height + 0.5,
                     f'{height:.2f}', ha='center', va='bottom', fontsize=9)

    # 设置图表属性
    plt.title('多任务与单任务模型性能对比（协同效应可视化）', fontweight='bold', fontsize=14)
    plt.xlabel('评估指标', fontsize=12)
    plt.ylabel('性能值（准确率% / F1×100）', fontsize=12)
    plt.xticks(x, tasks, fontsize=10)
    plt.legend(fontsize=10)
    plt.grid(axis='y', alpha=0.3)

    # 添加协同增益标注
    for i in range(len(tasks)):
        gain = mt_values[i] - st_values[i]
        if i in [1, 3]:
            gain /= 100  # F1增益还原为原始尺度
            plt.text(i, max(mt_values[i], st_values[i]) + 3,
                     f'增益:+{gain:.4f}', ha='center', color='red', fontweight='bold', fontsize=9)
        else:
            plt.text(i, max(mt_values[i], st_values[i]) + 3,
                     f'增益:+{gain:.2f}%', ha='center', color='red', fontweight='bold', fontsize=9)

    plt.tight_layout()
    plt.savefig('synergy_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\n✅ 协同效应对比图已保存为 synergy_comparison.png")


# ========== 9. 诊断报告生成器（贴合附件文档需求） ==========
def batch_generate_reports(model, dataloader, device, disease_mapping, max_reports=30):
    os.makedirs("diagnostic_reports", exist_ok=True)
    model.eval()
    # 兼容两种 disease_mapping 结构：
    # - {name: idx} (MultiTaskDataset)
    # - {idx: name} (PublicFolderDataset)
    if all(isinstance(k, int) for k in disease_mapping.keys()):
        idx_to_label = disease_mapping
    else:
        idx_to_label = {v: k for k, v in disease_mapping.items()}
    count = 0

    with torch.no_grad():
        for batch_idx, (images, _, _, filenames) in enumerate(tqdm(dataloader, desc="生成诊断报告")):
            if count >= max_reports:
                break
            images = images.to(device)
            disease_outputs, severity_outputs, _ = model(images)
            disease_probs = torch.softmax(disease_outputs, dim=1)
            severity_probs = torch.softmax(severity_outputs, dim=1)
            _, disease_preds = torch.max(disease_outputs, 1)
            _, severity_preds = torch.max(severity_outputs, 1)

            for i in range(len(images)):
                if count >= max_reports:
                    break
                image_path = dataloader.dataset.image_paths[batch_idx * dataloader.batch_size + i]
                filename = filenames[i]
                pred_idx = int(disease_preds[i].item())
                # 先尝试用索引获取标签名/id，若不存在则回退为索引本身
                pred_label = idx_to_label.get(pred_idx, pred_idx)
                pred_disease_id = pred_label
                pred_severity = int(severity_preds[i].item())
                crop_type = get_crop_type(pred_disease_id)

                # 关联附件文档的病害详情
                disease_info = get_disease_details(pred_disease_id)
                # 置信度转换为百分比
                disease_conf = disease_probs[i][disease_preds[i]].item() * 100
                severity_conf = severity_probs[i][severity_preds[i]].item() * 100

                # 风险等级判定（适配附件文档“精准防控”需求）
                if pred_severity == 2 and disease_conf > 80:
                    risk_level = "高风险（需紧急防控）"
                elif pred_severity == 1 and disease_conf > 70:
                    risk_level = "中风险（需密切监测）"
                else:
                    risk_level = "低风险（常规管理）"

                # 生成Markdown格式诊断报告
                report = f"""# 作物病害智能诊断报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
图像文件名: {filename}
图像路径: {image_path}

## 诊断核心结果
- 作物类型: {crop_type}
- 病害名称: {disease_info['name']}
- 严重程度: {['健康', '一般疾病', '严重疾病'][pred_severity]}
- 病害置信度: {disease_conf:.2f}%
- 严重程度置信度: {severity_conf:.2f}%
- 风险等级: {risk_level}

## 病害详细描述（参考附件文档）
{disease_info['description']}

## 防控建议（贴合农业生产实际）
{disease_info['suggestion']}
"""
                report_path = os.path.join("diagnostic_reports", f"{os.path.splitext(filename)[0]}_report.txt")
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report)
                count += 1

    print(f"✅ 诊断报告已保存至 diagnostic_reports 目录（共{count}份）")


# ========== 10. Grad-CAM可视化（解释模型决策） ==========
def grad_cam_visualization(model, dataloader, device, num_samples=3, output_dir="grad_cam_visualizations"):
    os.makedirs(output_dir, exist_ok=True)
    model.eval()

    # 定位MobileNetV2最后一层卷积层
    target_layer = model.feature_extractor[-1]

    # 存储梯度和特征图的变量
    gradients = None
    features = None

    # 梯度钩子：保存反向传播梯度
    def save_gradients(module, grad_in, grad_out):
        nonlocal gradients
        gradients = grad_out[0]

    # 特征钩子：保存前向传播特征图
    def save_features(module, feat_in, feat_out):
        nonlocal features
        features = feat_out.detach()

    # 注册钩子
    grad_hook = target_layer.register_backward_hook(save_gradients)
    feat_hook = target_layer.register_forward_hook(save_features)

    sample_count = 0
    for images, _, _, filenames in dataloader:
        if sample_count >= num_samples:
            break
        images = images.to(device)
        for i in range(len(images)):
            if sample_count >= num_samples:
                break
            img_tensor = images[i:i + 1].requires_grad_(True)
            img_path = dataloader.dataset.image_paths[sample_count]

            # 1. 前向传播获取疾病分类输出
            with torch.enable_grad():
                disease_output, _, _ = model(img_tensor)

            # 2. 反向传播（针对预测的疾病类别）
            pred_class = disease_output.argmax(dim=1).item()
            model.zero_grad()
            disease_output[:, pred_class].backward()

            # 3. 计算Grad-CAM热力图
            weights = torch.mean(gradients, dim=[2, 3], keepdim=True)
            cam = torch.sum(weights * features, dim=1).squeeze()
            cam = torch.relu(cam)

            # 4. 归一化并上采样到原图尺寸
            cam = cam.cpu().detach().numpy()
            cam = cv2.resize(cam, (128, 128))
            cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)

            # 5. 加载原始图像并叠加热力图
            original_img = Image.open(img_path).convert('RGB').resize((128, 128))
            img_np = np.array(original_img) / 255.0
            cam_colored = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
            cam_colored = cv2.cvtColor(cam_colored, cv2.COLOR_BGR2RGB) / 255.0
            visualization = img_np * 0.6 + cam_colored * 0.4

            # 6. 保存可视化结果
            save_path = os.path.join(output_dir, f"grad_cam_{filenames[i]}")
            plt.imsave(save_path, visualization)
            print(f"✅ 保存Grad-CAM可视化结果: {save_path}")
            sample_count += 1

    # 移除钩子
    grad_hook.remove()
    feat_hook.remove()
    print(f"Grad-CAM可视化结果已保存至 {output_dir} 目录（共{sample_count}个样本）")


# ========== 11. 风险评估功能（支撑附件文档“精准防控”） ==========
def confidence_based_risk_assessment(model, dataloader, device, disease_mapping, sample_ratio=0.1):
    print("\n=== 作物病害风险等级评估（基于附件文档分级规则） ===")
    model.eval()
    reverse_disease_mapping = {v: k for k, v in disease_mapping.items()}
    risk_stats = {"高风险（需紧急防控）": 0, "中风险（需密切监测）": 0, "低风险（常规管理）": 0, "不确定（需人工复核）": 0}
    total_samples = 0
    max_samples = int(len(dataloader.dataset) * sample_ratio)

    with torch.no_grad():
        for images, _, _, _ in tqdm(dataloader, desc="风险等级评估"):
            if total_samples >= max_samples:
                break
            images = images.to(device)
            disease_outputs, severity_outputs, _ = model(images)
            disease_probs = torch.softmax(disease_outputs, dim=1)
            severity_probs = torch.softmax(severity_outputs, dim=1)
            _, disease_preds = torch.max(disease_outputs, 1)
            _, severity_preds = torch.max(severity_outputs, 1)

            for i in range(len(images)):
                if total_samples >= max_samples:
                    break
                disease_conf = disease_probs[i][disease_preds[i]].item()
                severity_conf = severity_probs[i][severity_preds[i]].item()
                pred_severity = severity_preds[i].item()

                # 基于置信度和严重程度的风险分级
                if disease_conf < 0.7 or severity_conf < 0.7:
                    risk_stats["不确定（需人工复核）"] += 1
                elif pred_severity == 2:
                    risk_stats["高风险（需紧急防控）"] += 1
                elif pred_severity == 1:
                    risk_stats["中风险（需密切监测）"] += 1
                else:
                    risk_stats["低风险（常规管理）"] += 1
                total_samples += 1

    # 打印风险统计结果
    print(f"风险分布（共评估{total_samples}个样本）:")
    for risk, count in risk_stats.items():
        print(f"- {risk}: {count}个样本，占比{count / total_samples * 100:.1f}%")

    # 可视化风险分布
    plt.figure(figsize=(8, 5))
    risk_labels = list(risk_stats.keys())
    risk_values = list(risk_stats.values())
    sns.barplot(
        x=risk_labels,
        y=risk_values,
        hue=risk_labels,
        palette="viridis",
        dodge=False,
        legend=False,
    )
    plt.title("作物病害风险等级分布（基于附件文档分级）")
    plt.xlabel("风险等级")
    plt.ylabel("样本数量")
    plt.xticks(rotation=30)
    for i, v in enumerate(risk_values):
        plt.text(i, v + 0.5, str(v), ha='center')
    plt.tight_layout()
    plt.savefig("risk_distribution.png", dpi=300)
    plt.close()
    print("✅ 风险分布可视化图已保存为 risk_distribution.png")


# ========== 12. 数据变换（适配MobileNetV2输入） ==========
def create_data_transforms():
    train_transform = transforms.Compose([
        transforms.Resize((128, 128)),
        transforms.RandomHorizontalFlip(p=0.3),
        transforms.RandomRotation(10),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    val_transform = transforms.Compose([
        transforms.Resize((128, 128)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    return train_transform, val_transform


# ========== 13. 主函数（全流程驱动：多任务+单任务+协同效应） ==========
def train_multitask_with_synergy(sample_ratio=0.5, num_epochs=15, early_stopping_patience=5, data_dir=None, dataset_mode="mock"):
    print("=" * 80)
    print("【问题四：多任务联合学习与可解释诊断】完整解决方案（含协同效应评估）")
    print("=" * 80)

    # 1. 设备配置
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"当前训练设备: {device}")

    # 2. 数据路径查找与加载
    if dataset_mode in {"public", "plantvillage"}:
        default_public_dir = "data/plantvillage" if dataset_mode == "plantvillage" else "data/public_dataset"
        data_files = find_public_data_files(data_dir or os.environ.get("AGRI_DATA_DIR", default_public_dir))
        train_data_dir = data_files['train_dir']
        val_data_dir = data_files['val_dir']
        train_txt_file = None
        val_txt_file = None
    else:
        data_files = find_data_files(data_dir)
        train_data_dir = data_files['train_dir']
        train_txt_file = data_files['train_txt']
        val_data_dir = data_files['val_dir']
        val_txt_file = data_files['val_txt']

    # 3. 数据变换
    train_transform, val_transform = create_data_transforms()

    # 4. 加载数据集
    try:
        print("\n=== 加载训练集 ===")
        if dataset_mode in {"public", "plantvillage"}:
            train_dataset = PublicFolderDataset(
                data_dir=train_data_dir,
                transform=train_transform,
                sample_ratio=sample_ratio
            )
        else:
            train_dataset = MultiTaskDataset(
                data_dir=train_data_dir,
                txt_file=train_txt_file,
                transform=train_transform,
                sample_ratio=sample_ratio
            )
        print("\n=== 加载验证集 ===")
        if dataset_mode in {"public", "plantvillage"}:
            val_dataset = PublicFolderDataset(
                data_dir=val_data_dir,
                transform=val_transform,
                sample_ratio=min(sample_ratio, 1.0)
            )
        else:
            val_dataset = MultiTaskDataset(
                data_dir=val_data_dir,
                txt_file=val_txt_file,
                transform=val_transform,
                sample_ratio=min(sample_ratio, 1.0)
            )
    except Exception as e:
        print(f"数据集加载失败: {str(e)}")
        return

    # 5. 数据加载器（CPU适配：num_workers=0）
    batch_size = 16 if device.type == "cuda" else 4
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True,
        num_workers=0, pin_memory=False
    )
    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False,
        num_workers=0, pin_memory=False
    )

    # 6. 训练多任务模型
    print("\n" + "=" * 50)
    print("阶段1：训练多任务模型")
    print("=" * 50)
    mt_model = MultiTaskNetwork(
        num_diseases=train_dataset.num_diseases,
        num_severity=3
    ).to(device)
    mt_trainer = TaskTrainer(mt_model, task_type="multitask")

    best_mt_d_acc = 0.0
    best_mt_d_f1 = 0.0
    best_mt_s_acc = 0.0
    best_mt_s_f1 = 0.0
    best_val_loss = float('inf')
    early_stopping_counter = 0

    for epoch in range(num_epochs):
        print(f"\n=== Epoch {epoch + 1}/{num_epochs} ===")
        # 训练
        train_loss = mt_trainer.train_epoch(train_loader, device)
        # 评估
        _, _, _, _, val_loss, d_acc, d_f1, s_acc, s_f1 = mt_trainer.evaluate(val_loader, device)

        print(f"训练损失: {train_loss:.4f}")
        print(f"验证准确率: 疾病分类 {d_acc:.2f}% | 严重程度分级 {s_acc:.2f}%")
        print(f"验证宏平均F1: 疾病分类 {d_f1:.4f} | 严重程度分级 {s_f1:.4f}")

        # 早停与最佳模型保存
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_mt_d_acc = d_acc
            best_mt_d_f1 = d_f1
            best_mt_s_acc = s_acc
            best_mt_s_f1 = s_f1
            torch.save(mt_model.state_dict(), 'best_multitask_model.pth')
            print("✅ 保存最佳多任务模型权重")
            early_stopping_counter = 0
        else:
            early_stopping_counter += 1
            print(f"早停计数: {early_stopping_counter}/{early_stopping_patience}")
            if early_stopping_counter >= early_stopping_patience:
                print("⚠️ 触发早停机制，停止多任务训练")
                break

    mt_metrics = (best_mt_d_acc, best_mt_d_f1, best_mt_s_acc, best_mt_s_f1)
    print(f"\n多任务模型最佳性能:")
    print(f"疾病分类：准确率{best_mt_d_acc:.2f}%，F1{best_mt_d_f1:.4f}")
    print(f"严重程度：准确率{best_mt_s_acc:.2f}%，F1{best_mt_s_f1:.4f}")

    # 7. 训练单任务模型（疾病分类）
    print("\n" + "=" * 50)
    print("阶段2：训练单任务疾病分类模型")
    print("=" * 50)
    st_disease_model = SingleTaskDiseaseModel(num_diseases=train_dataset.num_diseases).to(device)
    st_disease_trainer = TaskTrainer(st_disease_model, task_type="disease")

    best_st_d_acc = 0.0
    best_st_d_f1 = 0.0
    best_st_d_loss = float('inf')
    early_stopping_counter = 0

    for epoch in range(num_epochs):
        print(f"\n=== Epoch {epoch + 1}/{num_epochs} ===")
        train_loss, train_acc = st_disease_trainer.train_epoch(train_loader, device)
        val_loss, val_acc, val_f1 = st_disease_trainer.evaluate(val_loader, device)

        print(f"训练损失: {train_loss:.4f}，训练准确率: {train_acc:.2f}%")
        print(f"验证损失: {val_loss:.4f}，验证准确率: {val_acc:.2f}%，验证F1: {val_f1:.4f}")

        if val_loss < best_st_d_loss:
            best_st_d_loss = val_loss
            best_st_d_acc = val_acc
            best_st_d_f1 = val_f1
            torch.save(st_disease_model.state_dict(), 'best_single_disease_model.pth')
            print("✅ 保存最佳单任务疾病模型权重")
            early_stopping_counter = 0
        else:
            early_stopping_counter += 1
            if early_stopping_counter >= early_stopping_patience:
                print("⚠️ 触发早停机制，停止单任务疾病训练")
                break

    st_disease_metrics = (best_st_d_acc, best_st_d_f1)
    print(f"\n单任务疾病模型最佳性能: 准确率{best_st_d_acc:.2f}%，F1{best_st_d_f1:.4f}")

    # 8. 训练单任务模型（严重程度分级）
    print("\n" + "=" * 50)
    print("阶段3：训练单任务严重程度分级模型")
    print("=" * 50)
    st_severity_model = SingleTaskSeverityModel(num_severity=3).to(device)
    st_severity_trainer = TaskTrainer(st_severity_model, task_type="severity")

    best_st_s_acc = 0.0
    best_st_s_f1 = 0.0
    best_st_s_loss = float('inf')
    early_stopping_counter = 0

    for epoch in range(num_epochs):
        print(f"\n=== Epoch {epoch + 1}/{num_epochs} ===")
        train_loss, train_acc = st_severity_trainer.train_epoch(train_loader, device)
        val_loss, val_acc, val_f1 = st_severity_trainer.evaluate(val_loader, device)

        print(f"训练损失: {train_loss:.4f}，训练准确率: {train_acc:.2f}%")
        print(f"验证损失: {val_loss:.4f}，验证准确率: {val_acc:.2f}%，验证F1: {val_f1:.4f}")

        if val_loss < best_st_s_loss:
            best_st_s_loss = val_loss
            best_st_s_acc = val_acc
            best_st_s_f1 = val_f1
            torch.save(st_severity_model.state_dict(), 'best_single_severity_model.pth')
            print("✅ 保存最佳单任务严重程度模型权重")
            early_stopping_counter = 0
        else:
            early_stopping_counter += 1
            if early_stopping_counter >= early_stopping_patience:
                print("⚠️ 触发早停机制，停止单任务严重程度训练")
                break

    st_severity_metrics = (best_st_s_acc, best_st_s_f1)
    print(f"\n单任务严重程度模型最佳性能: 准确率{best_st_s_acc:.2f}%，F1{best_st_s_f1:.4f}")

    # 9. 计算并可视化协同效应
    calculate_synergy(mt_metrics, st_disease_metrics, st_severity_metrics)

    # 10. 后续任务：诊断报告、Grad-CAM、风险评估
    batch_generate_reports(mt_model, val_loader, device, train_dataset.disease_mapping)
    grad_cam_visualization(mt_model, val_loader, device)
    confidence_based_risk_assessment(mt_model, val_loader, device, train_dataset.disease_mapping)

    print("\n🎉 所有任务执行完毕！")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="多任务农业病害诊断训练入口")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="数据根目录（包含 AgriculturalDisease_trainingset 与 AgriculturalDisease_validationset）"
    )
    parser.add_argument("--sample-ratio", type=float, default=0.5, help="数据采样比例，默认0.5")
    parser.add_argument("--epochs", type=int, default=15, help="训练轮次，默认15")
    parser.add_argument("--patience", type=int, default=5, help="早停耐心值，默认5")
    parser.add_argument(
        "--dataset-mode",
        type=str,
        choices=["mock", "public", "plantvillage"],
        default="mock",
        help="数据模式：mock 使用当前赛题模拟数据，public 使用通用公开数据集文件夹，plantvillage 使用 PlantVillage 数据集"
    )

    args = parser.parse_args()

    train_multitask_with_synergy(
        sample_ratio=args.sample_ratio,
        num_epochs=args.epochs,
        early_stopping_patience=args.patience,
        data_dir=args.data_dir,
        dataset_mode=args.dataset_mode
    )