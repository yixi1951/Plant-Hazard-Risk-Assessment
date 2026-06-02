import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, random_split
import torchvision.transforms as transforms
import torchvision.models as models
from PIL import Image
import json
import os
import numpy as np
from tqdm import tqdm
import glob
import re
from sklearn.metrics import f1_score, classification_report


# ========== 1. 优化的Focal Loss（解决类别不平衡） ==========
class FixedFocalLoss(nn.Module):
    def __init__(self, alpha=None, gamma=2.0, reduction='mean'):
        super().__init__()
        self.gamma = gamma
        self.reduction = reduction
        if alpha is not None:
            if isinstance(alpha, (list, np.ndarray)):
                self.register_buffer('alpha', torch.tensor(alpha, dtype=torch.float32))
            else:
                self.register_buffer('alpha', alpha.clone().detach().to(torch.float32))
        else:
            self.register_buffer('alpha', None)

    def forward(self, inputs, targets):
        targets = targets.long()
        ce_loss = nn.CrossEntropyLoss(reduction='none')(inputs, targets)
        pt = torch.exp(-ce_loss)
        focal_loss = (1 - pt) ** self.gamma * ce_loss

        if self.alpha is not None:
            alpha_t = self.alpha.to(inputs.device)[targets]
            focal_loss = alpha_t * focal_loss

        if self.reduction == 'mean':
            return focal_loss.mean()
        return focal_loss.sum()


# ========== 2. 增强数据集类（重点修正标签映射） ==========
class AgricultureDiseaseDataset(Dataset):
    def __init__(self, data_dir, json_file=None, list_file=None, transform=None, is_training=True):
        self.data_dir = data_dir
        self.transform = transform
        self.is_training = is_training
        self.image_paths = []
        self.labels = []
        self.focal_alpha = None  # 用于Focal Loss的类别权重

        # 加载优先级：列表文件 → JSON文件（列表格式） → 目录遍历
        load_success = False
        if list_file and os.path.exists(list_file):
            print(f"从列表文件加载数据: {list_file}")
            load_success = self._load_from_list_file(list_file)
        elif json_file and os.path.exists(json_file):
            print(f"从JSON文件加载数据: {json_file}")
            load_success = self._load_from_json(json_file)
        else:
            print("无标注文件，尝试目录加载")
            load_success = self._load_from_directory()

        # 若加载失败，强制目录加载
        if not load_success or len(self.image_paths) == 0:
            print("⚠️  标注文件加载失败，强制从目录加载")
            self._load_from_directory()

        # 数据清洗+权重计算
        self._remove_duplicates()
        self._compute_class_weights()

        print(f"数据集加载完成: {len(self.image_paths)} 张图片, {len(set(self.labels))} 个类别")

    def _load_from_json(self, json_file):
        """适配列表格式JSON：每个条目含"disease_class"和"image_id" """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in tqdm(data, desc="解析JSON标注"):
                    if isinstance(item, dict) and 'image_id' in item and 'disease_class' in item:
                        image_id = item['image_id']
                        label = item['disease_class']
                        self._add_image(image_id, label)
                return len(self.image_paths) > 0
            else:
                print("JSON格式不支持（非列表格式）")
                return False
        except Exception as e:
            print(f"加载JSON失败: {str(e)[:50]}")
            return False

    def _load_from_list_file(self, list_file):
        try:
            with open(list_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line_num, line in enumerate(tqdm(lines, desc="解析列表文件"), 1):
                line = line.strip()
                if not line:
                    continue
                # 匹配 "路径 + 标签" 格式
                match = re.match(r'(.*?\.(jpg|jpeg|png|JPG|JPEG|PNG))\s+(\d+)$', line)
                if match:
                    img_rel = match.group(1).replace('\\', '/')
                    label = int(match.group(3))
                    # 提取images后的路径（适配训练集结构）
                    if 'images/' in img_rel:
                        img_rel = img_rel.split('images/')[1]
                    self._add_image(img_rel, label)
            return len(self.image_paths) > 0
        except Exception as e:
            print(f"读取列表文件失败: {str(e)[:50]}")
            return False

    def _load_from_directory(self):
        """从目录递归加载图像，按文件名推断标签（重点修正标签逻辑）"""
        # 强制适配images子文件夹结构
        images_dir = os.path.join(self.data_dir, 'images')
        if not os.path.exists(images_dir):
            images_dir = self.data_dir
            print(f"警告: 未找到images子目录，使用根目录: {images_dir}")

        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']
        for ext in image_extensions:
            for img_path in tqdm(glob.glob(os.path.join(images_dir, '**', ext), recursive=True), desc="目录加载图像"):
                # 从文件名推断标签（严格匹配“类别_编号.jpg”格式）
                filename = os.path.basename(img_path)
                label = self._infer_label_from_filename(filename)
                self.image_paths.append(img_path)
                self.labels.append(label)
        return len(self.image_paths) > 0

    def _infer_label_from_filename(self, filename):
        """重点修正：严格解析标签，确保和数据集类别一致"""
        # 匹配 "数字_xxx.jpg"（如 "60_1350.jpg" → 标签60）
        match = re.match(r'^(\d+)_', filename)
        if match:
            return int(match.group(1))
        # 匹配纯数字文件名（如 "5.jpg" → 标签5）
        elif filename.split('.')[0].isdigit():
            return int(filename.split('.')[0])
        # 兜底：打印异常文件名，确保标签可追溯
        else:
            print(f"警告：文件名{filename}无法解析标签，默认返回0（需手动检查）")
            return 0

    def _add_image(self, image_id, label):
        """精准拼接images子文件夹路径"""
        # 强制拼接：data_dir/images/image_id
        full_path = os.path.join(self.data_dir, 'images', image_id)
        if os.path.exists(full_path):
            self.image_paths.append(full_path)
            self.labels.append(label)
            return True

        # 递归搜索（防止图像在子文件夹）
        search_pattern = os.path.join(self.data_dir, 'images', '**', image_id)
        matches = glob.glob(search_pattern, recursive=True)
        if matches:
            self.image_paths.append(matches[0])
            self.labels.append(label)
            return True

        # 未找到图像（打印日志便于排查）
        print(f"跳过不存在的图像: {image_id}")
        return False

    def _remove_duplicates(self):
        """基于图像哈希去重，解决重复标注"""
        from hashlib import md5
        seen_hashes = set()
        unique_paths = []
        unique_labels = []
        for path, label in tqdm(zip(self.image_paths, self.labels), desc="数据去重"):
            try:
                with open(path, 'rb') as f:
                    img_hash = md5(f.read()).hexdigest()
                if img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    unique_paths.append(path)
                    unique_labels.append(label)
            except Exception as e:
                # 跳过损坏图像
                continue
        duplicate_count = len(self.image_paths) - len(unique_paths)
        self.image_paths = unique_paths
        self.labels = unique_labels
        print(f"数据清洗完成: 移除 {duplicate_count} 个重复/损坏样本")

    def _compute_class_weights(self):
        """计算Focal Loss的类别权重"""
        if len(self.labels) == 0:
            self.focal_alpha = np.ones(61)
            return
        unique, counts = np.unique(self.labels, return_counts=True)
        total_samples = len(self.labels)
        # 逆频率权重（平衡少样本类别）
        weights = total_samples / (len(unique) * counts)
        class_weight_dict = dict(zip(unique, weights))
        # 补全61类权重（未出现类别用1.0）
        self.focal_alpha = np.array([class_weight_dict.get(i, 1.0) for i in range(61)])

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        try:
            image = Image.open(self.image_paths[idx]).convert('RGB')
            label = self.labels[idx]
            if self.transform:
                image = self.transform(image)
            return image, torch.tensor(label, dtype=torch.long)
        except Exception as e:
            print(f"加载图像失败: {os.path.basename(self.image_paths[idx])}, 错误: {str(e)[:30]}")
            default_image = Image.new('RGB', (224, 224), color='black')
            if self.transform:
                default_image = self.transform(default_image)
            return default_image, torch.tensor(0, dtype=torch.long)


# ========== 3. 轻量化迁移学习模型（保持不变，确保预训练权重加载） ==========
class LightTransferLearningModel(nn.Module):
    def __init__(self, num_classes=61):
        super().__init__()
        # 加载ResNet34预训练模型（参数更轻量）
        self.backbone = models.resnet34(weights='IMAGENET1K_V1')
        # 冻结前2层卷积（仅微调layer3、layer4和分类头）
        for param in self.backbone.conv1.parameters():
            param.requires_grad = False
        for param in self.backbone.layer1.parameters():
            param.requires_grad = False

        # 替换分类头（大幅简化，减少参数）
        in_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Sequential(
            nn.Dropout(0.5),
            nn.Linear(in_features, 512),  # 从1024→512，减少参数
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes)
        )

        # 验证参数数量（确保≤5000万）
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        print(f"模型总参数: {total_params:,}（≤5000万）")
        print(f"可训练参数: {trainable_params:,}（仅微调部分）")
        assert total_params <= 50_000_000, "模型参数超过5000万限制"

    def forward(self, x):
        return self.backbone(x)


# ========== 4. 简化数据增强（CPU训练先收敛，再逐步增强） ==========
def create_enhanced_transforms():
    # 训练集：简化增强，先确保收敛
    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(p=0.3),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # 验证集：保持稳定
    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    return train_transform, val_transform


# ========== 5. 数据文件查找函数（保持不变，确保路径正确） ==========
def find_data_files(base_dir="C:\\Users\\ASUS\\Desktop\\Problem B：Data"):
    data_files = {
        'train_json': None, 'train_list': None, 'train_dir': None,
        'val_json': None, 'val_list': None, 'val_dir': None
    }

    # 定位Problem B根目录
    problem_b_dir = base_dir
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path) and "Problem B" in item and "Data" in item:
            problem_b_dir = item_path
            break

    # 查找训练集目录和文件
    train_dirs = []
    for item in os.listdir(problem_b_dir):
        item_path = os.path.join(problem_b_dir, item)
        if os.path.isdir(item_path) and "train" in item.lower():
            train_dirs.append(item_path)
    data_files['train_dir'] = train_dirs[0] if train_dirs else problem_b_dir

    # 查找验证集目录和文件
    val_dirs = []
    for item in os.listdir(problem_b_dir):
        item_path = os.path.join(problem_b_dir, item)
        if os.path.isdir(item_path) and ("val" in item.lower() or "test" in item.lower()):
            val_dirs.append(item_path)
    data_files['val_dir'] = val_dirs[0] if val_dirs else problem_b_dir

    # 查找JSON文件
    for root, dirs, files in os.walk(problem_b_dir):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                if 'train' in file.lower() and 'annotation' in file.lower():
                    data_files['train_json'] = file_path
                elif 'val' in file.lower() and 'annotation' in file.lower():
                    data_files['val_json'] = file_path

    # 查找列表文件（适配ttest_list）
    for root, dirs, files in os.walk(problem_b_dir):
        for file in files:
            if 'train_list' in file.lower() and file.endswith('.txt'):
                data_files['train_list'] = os.path.join(root, file)
            elif any(kw in file.lower() for kw in ['val_list', 'ttest_list', 'test_list']) and file.endswith('.txt'):
                data_files['val_list'] = os.path.join(root, file)

    return data_files


# ========== 6. 优化训练函数（降低学习率，先确保收敛） ==========
def train_task1_optimized():
    print("=" * 50)
    print("任务1: 农业病害图像分类（标签修正+简化训练版）")
    print("=" * 50)

    # 1. 查找数据
    data_files = find_data_files()
    print("找到的数据文件:")
    for key, value in data_files.items():
        print(f"  {key}: {value if value else '未找到'}")

    # 2. 创建数据变换（简化增强）
    train_transform, val_transform = create_enhanced_transforms()

    # 3. 加载数据集
    train_dataset = AgricultureDiseaseDataset(
        data_dir=data_files['train_dir'],
        json_file=data_files['train_json'],
        list_file=data_files['train_list'],
        transform=train_transform,
        is_training=True
    )
    val_dataset = AgricultureDiseaseDataset(
        data_dir=data_files['val_dir'],
        json_file=data_files['val_json'],
        list_file=data_files['val_list'],
        transform=val_transform,
        is_training=False
    )

    # 处理空验证集（强制拆分训练集）
    if len(val_dataset) == 0:
        print("⚠️  验证集为空，拆分训练集为训练+验证（9:1）")
        val_size = int(0.1 * len(train_dataset))
        train_size = len(train_dataset) - val_size
        train_dataset, val_dataset = random_split(
            train_dataset, [train_size, val_size]
        )

    # 4. 确定类别数（修正：从标签集合中获取，而非数据集长度）
    all_labels = []
    for _, label in train_dataset:
        all_labels.append(label.item())
    num_classes = len(set(all_labels))
    print(f"最终类别数: {num_classes}（实际为61类）")

    # 5. 硬件适配
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    batch_size = 32 if device.type == 'cuda' else 8  # GPU增大batch_size
    num_workers = 4 if device.type == 'cuda' else 0  # CPU禁用多线程
    print(f"使用设备: {device}, 批次大小: {batch_size}")

    # 6. 初始化模型、损失、优化器（降低学习率）
    model = LightTransferLearningModel(num_classes=num_classes).to(device)
    # 使用Focal Loss（传入类别权重）
    criterion = FixedFocalLoss(alpha=train_dataset.focal_alpha, gamma=2.0).to(device)
    # AdamW优化器（降低学习率，先确保收敛）
    optimizer = optim.AdamW(
        model.parameters(),
        lr=5e-4,  # 从1e-3降至5e-4
        weight_decay=1e-4,
        betas=(0.9, 0.999)
    )
    # 自适应学习率调度（移除verbose参数）
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', patience=3, factor=0.5, min_lr=1e-6
    )

    # 7. 数据加载器
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=device.type == 'cuda'
    )
    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=device.type == 'cuda'
    )

    # 8. 训练循环（30轮，先看前5轮收敛情况）
    num_epochs = 30
    best_val_acc = 0.0
    best_val_f1 = 0.0

    for epoch in range(num_epochs):
        # 训练阶段
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        train_bar = tqdm(train_loader, desc=f'Epoch {epoch+1}/{num_epochs} [训练]')
        for images, labels in train_bar:
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            # 统计训练指标
            train_loss += loss.item() * images.size(0)
            _, predicted = torch.max(outputs, 1)
            train_total += labels.size(0)
            train_correct += (predicted == labels).sum().item()
            train_avg_acc = 100 * train_correct / train_total

            train_bar.set_postfix({
                '损失': f'{loss.item():.4f}',
                '准确率': f'{train_avg_acc:.2f}%'
            })

        train_avg_loss = train_loss / train_total
        scheduler.step(train_avg_loss)  # 传入损失值触发调度

        # 验证阶段
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        all_preds = []
        all_labels = []

        with torch.no_grad():
            val_bar = tqdm(val_loader, desc=f'Epoch {epoch+1}/{num_epochs} [验证]')
            for images, labels in val_bar:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)

                val_loss += loss.item() * images.size(0)
                _, predicted = torch.max(outputs, 1)
                val_total += labels.size(0)
                val_correct += (predicted == labels).sum().item()

                all_preds.extend(predicted.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        val_avg_loss = val_loss / val_total if val_total > 0 else 0
        val_avg_acc = 100 * val_correct / val_total if val_total > 0 else 0
        val_macro_f1 = f1_score(all_labels, all_preds, average='macro', zero_division=0) if val_total > 0 else 0

        # 打印指标
        print(f"\nEpoch {epoch+1} 总结:")
        print(f"  训练损失: {train_avg_loss:.4f}, 训练准确率: {train_avg_acc:.2f}%")
        print(f"  验证损失: {val_avg_loss:.4f}, 验证准确率: {val_avg_acc:.2f}%")
        print(f"  验证宏平均F1: {val_macro_f1:.4f}")

        # 保存最佳模型（基于准确率+F1）
        if val_avg_acc > best_val_acc and val_macro_f1 > best_val_f1:
            best_val_acc = val_avg_acc
            best_val_f1 = val_macro_f1
            torch.save({
                'epoch': epoch+1,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'best_acc': best_val_acc,
                'best_f1': best_val_f1,
                'num_classes': num_classes
            }, 'best_task1_optimized_final.pth')
            print(f"✅ 保存最佳模型: 准确率={best_val_acc:.2f}%, F1={best_val_f1:.4f}")

    # 最终评估
    print(f"\n训练完成！最佳验证准确率: {best_val_acc:.2f}%, 最佳宏平均F1: {best_val_f1:.4f}")
    # 输出分类报告
    print("\n最终分类报告:")
    print(classification_report(all_labels, all_preds, zero_division=0, digits=4))


if __name__ == "__main__":
    train_task1_optimized()