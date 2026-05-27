import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
import torchvision.transforms as transforms
from PIL import Image
import os
import random
import re
from tqdm import tqdm
import glob
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.manifold import TSNE
import collections

# ========== 0. 可视化配置（中文+图片保存） ==========
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示
plt.rcParams["figure.dpi"] = 100  # 默认分辨率
SAVE_DIR = "few_shot_visualizations"
os.makedirs(SAVE_DIR, exist_ok=True)  # 创建可视化保存目录


# ========== 1. 数据路径自动查找 ==========
def find_data_files(base_dir="C:/Users/ASUS/Desktop/Problem B：Data"):
    """自动定位训练集根目录、list文件"""
    data_files = {
        "train_root": None,
        "train_list": None,
        "val_root": None,
        "val_list": None
    }

    # 遍历目录，匹配训练集和验证集
    for root, dirs, files in os.walk(base_dir):
        if "AgriculturalDisease_trainingset" in root and "images" in dirs:
            data_files["train_root"] = root
            for file in files:
                if file == "train_list.txt":
                    data_files["train_list"] = os.path.join(root, file)

        if "AgriculturalDisease_validationset" in root and "images" in dirs:
            data_files["val_root"] = root
            for file in files:
                if file == "val_list.txt" or "test" in file.lower():
                    data_files["val_list"] = os.path.join(root, file)

    return data_files


# ========== 2. 修复的数据集类（支持少样本采样+可视化所需信息） ==========
class FewShotAgricultureDataset(Dataset):
    def __init__(self, train_root, train_list, n_shot=10, transform=None, mode='train'):
        """少样本数据集类 - 每个类别只取n_shot张图像"""
        self.images_dir = os.path.join(train_root, "images")
        self.transform = transform
        self.mode = mode
        self.n_shot = n_shot
        self.image_paths = []
        self.labels = []
        self.class_to_images = collections.defaultdict(list)  # 保存类别-图像路径映射（用于可视化）

        # 加载数据并实施少样本采样
        self._load_and_sample_data(train_list)

        print(f"✅ {mode}数据集加载完成：共{len(self.image_paths)}张图像，{len(set(self.labels))}个类别")

    def _load_and_sample_data(self, train_list):
        """加载数据并实施每个类别n_shot张的采样"""
        # 首先按类别分组所有图像
        with open(train_list, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in tqdm(lines, desc="分组图像"):
            line = line.strip()
            if not line:
                continue

            # 跳过重复标注行
            if any(keyword in line.lower() for keyword in ['duplicate', 'replicate']):
                continue

            parts = re.split(r'\s+', line, maxsplit=1)
            if len(parts) != 2:
                continue

            img_rel_path, label_str = parts
            try:
                label = int(label_str)
                if 0 <= label <= 60:  # 确保标签在0-60范围内
                    # 查找图像文件
                    img_filename = self._extract_filename(img_rel_path)
                    img_full_path = self._find_image_file(img_filename)

                    if img_full_path and os.path.exists(img_full_path):
                        self.class_to_images[label].append(img_full_path)
            except ValueError:
                continue

        # 实施少样本采样：每个类别随机选择n_shot张图像
        for label, image_list in self.class_to_images.items():
            if len(image_list) >= self.n_shot:
                selected_images = random.sample(image_list, self.n_shot)
            else:
                selected_images = image_list
                print(f"警告: 类别{label}只有{len(image_list)}张图像")

            for img_path in selected_images:
                self.image_paths.append(img_path)
                self.labels.append(label)

    def _extract_filename(self, relative_path):
        """提取文件名"""
        relative_path = relative_path.replace('\\', '/')
        if 'images/' in relative_path:
            return relative_path.split('images/')[-1]
        return os.path.basename(relative_path)

    def _find_image_file(self, filename):
        """查找图像文件"""
        possible_paths = [
            os.path.join(self.images_dir, filename),
            os.path.join(self.images_dir, 'images', filename),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # 递归搜索
        search_pattern = os.path.join(self.images_dir, '**', filename)
        matches = glob.glob(search_pattern, recursive=True)
        return matches[0] if matches else None

    def get_class_distribution(self):
        """获取类别样本分布（用于可视化）"""
        return collections.Counter(self.labels)

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        """安全的getitem方法（返回图像、标签、路径）"""
        if idx < 0 or idx >= len(self.image_paths):
            return self._get_default_sample()

        try:
            image = Image.open(self.image_paths[idx]).convert('RGB')
            label = self.labels[idx]
            img_path = self.image_paths[idx]

            if self.transform:
                image = self.transform(image)

            return image, label, img_path
        except Exception as e:
            print(f"加载图像失败: {self.image_paths[idx]}, 错误: {e}")
            return self._get_default_sample()

    def _get_default_sample(self):
        """返回默认样本"""
        default_image = Image.new('RGB', (224, 224), color='black')
        if self.transform:
            default_image = self.transform(default_image)
        return default_image, 0, ""


# ========== 3. 符合问题二要求的少样本模型 ==========
class FewShotModel(nn.Module):
    def __init__(self, num_classes=61):
        """少样本分类模型 - 参数控制在2000万以内"""
        super(FewShotModel, self).__init__()

        # 特征提取器（轻量级设计）
        self.feature_extractor = nn.Sequential(
            # 第一层
            nn.Conv2d(3, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # 第二层
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # 第三层
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            # 第四层
            nn.Conv2d(256, 512, kernel_size=3, padding=1),
            nn.BatchNorm2d(512),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1))
        )

        # 分类头
        self.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(256, num_classes)
        )

        # 参数统计和验证
        total_params = sum(p.numel() for p in self.parameters())
        print(f"📊 模型参数总数: {total_params:,}")

        if total_params > 20_000_000:
            raise ValueError("模型参数超过2000万限制！")
        else:
            print("✅ 模型参数符合问题二要求（≤2000万）")

    def forward(self, x):
        features = self.feature_extractor(x)
        features_flat = features.view(features.size(0), -1)
        outputs = self.classifier(features_flat)
        return outputs, features_flat  # 返回输出和特征（用于TSNE可视化）


# ========== 4. 元学习训练策略 ==========
class MetaLearningTrainer:
    def __init__(self, model, train_loader, val_loader, device):
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device

        # 优化器和损失函数
        self.optimizer = optim.AdamW(
            model.parameters(),
            lr=1e-3,
            weight_decay=1e-4
        )
        self.criterion = nn.CrossEntropyLoss()

        # 学习率调度
        self.scheduler = optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=50
        )

        # 记录训练过程（用于可视化）
        self.train_losses = []
        self.train_accs = []
        self.val_losses = []
        self.val_accs = []

    def train_epoch(self, epoch):
        """训练一个epoch"""
        self.model.train()
        total_loss = 0
        correct = 0
        total = 0

        pbar = tqdm(self.train_loader, desc=f'Epoch {epoch} [训练]')
        for images, labels, _ in pbar:
            images, labels = images.to(self.device), labels.to(self.device)

            self.optimizer.zero_grad()
            outputs, _ = self.model(images)
            loss = self.criterion(outputs, labels)
            loss.backward()
            self.optimizer.step()

            total_loss += loss.item() * images.size(0)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

            pbar.set_postfix({
                'Loss': f'{loss.item():.4f}',
                'Acc': f'{100 * correct / total:.2f}%'
            })

        avg_loss = total_loss / total
        avg_acc = 100 * correct / total
        self.train_losses.append(avg_loss)
        self.train_accs.append(avg_acc)
        self.scheduler.step()
        return avg_loss, avg_acc

    def validate(self, epoch=None):
        """验证模型（返回准确率、预测结果、标签、损失、特征）"""
        self.model.eval()
        all_preds = []
        all_labels = []
        all_features = []
        all_losses = []

        with torch.no_grad():
            for images, labels, _ in tqdm(self.val_loader, desc='验证'):
                images, labels = images.to(self.device), labels.to(self.device)
                outputs, features = self.model(images)
                loss = self.criterion(outputs, labels)
                _, predicted = torch.max(outputs, 1)

                all_preds.extend(predicted.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
                all_features.extend(features.cpu().numpy())
                all_losses.append(loss.item() * images.size(0))

        avg_loss = sum(all_losses) / len(all_labels) if all_labels else 0
        accuracy = accuracy_score(all_labels, all_preds)

        # 记录验证指标
        if epoch is not None:
            self.val_losses.append(avg_loss)
            self.val_accs.append(100 * accuracy)

        return accuracy, avg_loss, all_preds, all_labels, np.array(all_features)


# ========== 5. 数据增强策略 ==========
def create_transforms():
    """创建数据增强变换"""
    train_transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.RandomCrop(224),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    return train_transform, val_transform


# ========== 6. 核心可视化函数（6类） ==========
def plot_class_distribution(class_counts, title="训练集类别样本分布", save_name="class_distribution.png"):
    """1. 类别样本分布直方图（少样本关键验证）"""
    plt.figure(figsize=(16, 6))
    labels = sorted(class_counts.keys())
    counts = [class_counts[label] for label in labels]
    colors = ['green' if c == 10 else 'orange' for c in counts]  # 10-shot为绿色，不足为橙色

    plt.bar(labels, counts, color=colors, alpha=0.7)
    plt.axhline(y=10, color='red', linestyle='--', label='10-shot目标线')
    plt.xlabel('类别标签')
    plt.ylabel('样本数量')
    plt.title(title)
    plt.legend()
    plt.xticks(range(0, 61, 5))  # 每5个类别显示一次标签
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(SAVE_DIR, save_name), dpi=300)
    plt.show()
    print(f"✅ 类别分布直方图已保存至 {os.path.join(SAVE_DIR, save_name)}")


def plot_train_curves(train_losses, train_accs, val_losses, val_accs, save_name="train_curves.png"):
    """2. 训练/验证损失+准确率曲线（双轴图）"""
    fig, ax1 = plt.subplots(figsize=(12, 6))

    # 损失曲线（左轴）
    ax1.plot(range(1, len(train_losses) + 1), train_losses, 'b-', marker='o', label='训练损失')
    ax1.plot(range(1, len(val_losses) + 1), val_losses, 'b--', marker='s', label='验证损失')
    ax1.set_xlabel('轮次')
    ax1.set_ylabel('损失', color='b')
    ax1.tick_params(axis='y', labelcolor='b')
    ax1.legend(loc='upper left')
    ax1.grid(alpha=0.3)

    # 准确率曲线（右轴）
    ax2 = ax1.twinx()
    ax2.plot(range(1, len(train_accs) + 1), train_accs, 'r-', marker='^', label='训练准确率')
    ax2.plot(range(1, len(val_accs) + 1), val_accs, 'r--', marker='v', label='验证准确率')
    ax2.set_ylabel('准确率 (%)', color='r')
    ax2.tick_params(axis='y', labelcolor='r')
    ax2.legend(loc='upper right')

    plt.title('训练/验证损失与准确率变化曲线')
    plt.tight_layout()
    plt.savefig(os.path.join(SAVE_DIR, save_name), dpi=300)
    plt.show()
    print(f"✅ 训练曲线已保存至 {os.path.join(SAVE_DIR, save_name)}")


def plot_confusion_matrix_simplified(all_labels, all_preds, top_k=20, save_name="confusion_matrix.png"):
    """3. 简化混淆矩阵（只显示样本数前20的类别，避免拥挤）"""
    # 统计样本数前20的类别
    label_counts = collections.Counter(all_labels)
    top_labels = [label for label, _ in label_counts.most_common(top_k)]
    top_labels.sort()

    # 筛选标签
    mask = np.isin(all_labels, top_labels)
    filtered_labels = np.array(all_labels)[mask]
    filtered_preds = np.array(all_preds)[mask]

    # 生成混淆矩阵
    plt.figure(figsize=(14, 12))
    cm = confusion_matrix(filtered_labels, filtered_preds, labels=top_labels)
    sns.heatmap(cm, annot=False, fmt='d', cmap='Blues',
                xticklabels=top_labels, yticklabels=top_labels)
    plt.xlabel('预测标签')
    plt.ylabel('真实标签')
    plt.title(f'混淆矩阵（样本数前{top_k}类）')
    plt.tight_layout()
    plt.savefig(os.path.join(SAVE_DIR, save_name), dpi=300)
    plt.show()
    print(f"✅ 简化混淆矩阵已保存至 {os.path.join(SAVE_DIR, save_name)}")


def plot_prediction_samples(model, val_loader, device, num_samples=16, save_name="prediction_samples.png"):
    """4. 预测样本可视化（含正确/错误标注+置信度）"""
    model.eval()
    images_list = []
    true_labels = []
    pred_labels = []
    confidences = []
    img_paths = []

    with torch.no_grad():
        for images, labels, paths in val_loader:
            images = images.to(device)
            outputs, _ = model(images)
            probs = torch.softmax(outputs, dim=1)
            confs, preds = torch.max(probs, 1)

            images_list.extend(images.cpu())
            true_labels.extend(labels.numpy())
            pred_labels.extend(preds.cpu().numpy())
            confidences.extend(confs.cpu().numpy())
            img_paths.extend(paths)

            if len(images_list) >= num_samples:
                break

    # 绘制网格
    num_rows = (num_samples + 3) // 4
    plt.figure(figsize=(4 * 4, num_rows * 4.5))

    for i in range(min(num_samples, len(images_list))):
        plt.subplot(num_rows, 4, i + 1)
        # 反归一化图像
        img = images_list[i].numpy().transpose(1, 2, 0)
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        img = std * img + mean
        img = np.clip(img, 0, 1)

        plt.imshow(img)
        # 标注（正确绿色，错误红色）
        color = 'green' if true_labels[i] == pred_labels[i] else 'red'
        plt.title(f"真实: {true_labels[i]}\n预测: {pred_labels[i]}\n置信度: {confidences[i]:.3f}", color=color)
        plt.axis('off')

    plt.tight_layout()
    plt.savefig(os.path.join(SAVE_DIR, save_name), dpi=300)
    plt.show()
    print(f"✅ 预测样本可视化已保存至 {os.path.join(SAVE_DIR, save_name)}")


def plot_class_error_rate(all_labels, all_preds, save_name="class_error_rate.png"):
    """5. 类别错误率柱状图（定位难分类类别）"""
    label_counts = collections.Counter(all_labels)
    error_counts = collections.defaultdict(int)

    for true, pred in zip(all_labels, all_preds):
        if true != pred:
            error_counts[true] += 1

    # 计算每个类别的错误率
    labels = sorted(label_counts.keys())
    error_rates = [error_counts.get(label, 0) / label_counts[label] for label in labels]

    plt.figure(figsize=(16, 6))
    bars = plt.bar(labels, error_rates, alpha=0.7, color='orangered')
    # 标注错误率>50%的类别
    for i, (label, rate) in enumerate(zip(labels, error_rates)):
        if rate > 0.5:
            bars[i].set_color('red')
            plt.text(label, rate + 0.02, f'{rate:.2f}', ha='center', fontsize=8)

    plt.xlabel('类别标签')
    plt.ylabel('错误率')
    plt.title('各类别错误率分布（红色表示错误率>50%）')
    plt.xticks(range(0, 61, 5))
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(SAVE_DIR, save_name), dpi=300)
    plt.show()
    print(f"✅ 类别错误率图已保存至 {os.path.join(SAVE_DIR, save_name)}")


def plot_tsne_features(features, labels, save_name="tsne_features.png"):
    """6. TSNE特征可视化（看类别聚类效果）"""
    # 采样减少计算量（少样本场景下最多1000个样本）
    n_samples = min(1000, len(features))
    sample_idx = random.sample(range(len(features)), n_samples)
    sample_features = features[sample_idx]
    sample_labels = np.array(labels)[sample_idx]

    # TSNE降维
    print("正在进行TSNE降维（可能需要1-2分钟）...")
    tsne = TSNE(n_components=2, random_state=42, perplexity=30)
    features_2d = tsne.fit_transform(sample_features)

    # 绘制散点图
    plt.figure(figsize=(12, 10))
    unique_labels = sorted(list(set(sample_labels)))
    colors = plt.cm.get_cmap('tab20', len(unique_labels))  # 多类别配色

    for i, label in enumerate(unique_labels):
        mask = sample_labels == label
        plt.scatter(
            features_2d[mask, 0], features_2d[mask, 1],
            c=[colors(i)], label=f'类别{label}', alpha=0.7, s=30
        )

    plt.xlabel('TSNE维度1')
    plt.ylabel('TSNE维度2')
    plt.title('特征TSNE可视化（类别聚类效果）')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(SAVE_DIR, save_name), dpi=300)
    plt.show()
    print(f"✅ TSNE特征可视化已保存至 {os.path.join(SAVE_DIR, save_name)}")


# ========== 7. 主训练函数（集成所有可视化） ==========
def train_few_shot_model():
    """问题二主训练函数（含完整可视化）"""
    print("=" * 60)
    print("任务二：少样本农业病害识别（带6类可视化）")
    print("要求：每个类别10张图像，61类分类，模型参数≤2000万")
    print("=" * 60)

    # 1. 查找数据文件
    data_files = find_data_files()
    print("找到的数据文件:")
    for key, value in data_files.items():
        if value:
            print(f"  {key}: {value}")

    if not data_files["train_root"] or not data_files["train_list"]:
        raise FileNotFoundError("未找到训练数据！")

    # 2. 创建数据变换
    train_transform, val_transform = create_transforms()

    # 3. 创建少样本数据集（每个类别10张图像）
    print("\n📁 创建少样本数据集...")
    train_dataset = FewShotAgricultureDataset(
        train_root=data_files["train_root"],
        train_list=data_files["train_list"],
        n_shot=10,  # 每个类别10张图像
        transform=train_transform,
        mode='train'
    )

    # 创建验证集
    if data_files["val_root"] and data_files["val_list"]:
        val_dataset = FewShotAgricultureDataset(
            train_root=data_files["val_root"],
            train_list=data_files["val_list"],
            n_shot=10,
            transform=val_transform,
            mode='val'
        )
    else:
        val_size = min(100, len(train_dataset) // 5)
        train_size = len(train_dataset) - val_size
        train_dataset, val_dataset = random_split(
            train_dataset, [train_size, val_size]
        )
        # 恢复random_split后丢失的get_class_distribution方法
        train_dataset.get_class_distribution = lambda: collections.Counter(
            [train_dataset.dataset.labels[i] for i in train_dataset.indices])

    # 4. 数据加载器
    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False, num_workers=0)

    print(f"训练集: {len(train_dataset)} 张图像")
    print(f"验证集: {len(val_dataset)} 张图像")

    # 5. 设备与模型
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")
    model = FewShotModel(num_classes=61).to(device)

    # 6. 训练器初始化
    trainer = MetaLearningTrainer(model, train_loader, val_loader, device)

    # ========== 可视化1：类别样本分布 ==========
    plot_class_distribution(train_dataset.get_class_distribution())

    # 7. 训练循环
    best_accuracy = 0
    num_epochs = 50
    final_preds, final_labels, final_features = [], [], np.array([])

    print("\n🚀 开始训练...")
    for epoch in range(1, num_epochs + 1):
        # 训练
        train_loss, train_acc = trainer.train_epoch(epoch)

        # 验证（每5轮/最后一轮）
        if epoch % 5 == 0 or epoch == num_epochs:
            val_acc, val_loss, val_preds, val_labels, val_features = trainer.validate(epoch)
            print(f"Epoch {epoch} - 验证准确率: {val_acc:.4f}, 验证损失: {val_loss:.4f}")

            # 保存最佳模型和结果
            if val_acc > best_accuracy:
                best_accuracy = val_acc
                final_preds, final_labels, final_features = val_preds, val_labels, val_features
                torch.save({
                    'epoch': epoch,
                    'model_state_dict': model.state_dict(),
                    'optimizer_state_dict': trainer.optimizer.state_dict(),
                    'accuracy': best_accuracy
                }, 'best_few_shot_model.pth')
                print(f"✅ 保存最佳模型，准确率: {best_accuracy:.4f}")

    # ========== 训练后可视化（5类） ==========
    print("\n📊 生成训练后可视化...")
    # 可视化2：训练曲线
    plot_train_curves(
        trainer.train_losses, trainer.train_accs,
        trainer.val_losses, trainer.val_accs
    )

    # 可视化3：混淆矩阵
    plot_confusion_matrix_simplified(final_labels, final_preds)

    # 可视化4：预测样本
    plot_prediction_samples(model, val_loader, device)

    # 可视化5：类别错误率
    plot_class_error_rate(final_labels, final_preds)

    # 可视化6：TSNE特征
    if len(final_features) > 0:
        plot_tsne_features(final_features, final_labels)

    # 8. 最终评估报告
    print("\n📋 最终评估结果:")
    checkpoint = torch.load('best_few_shot_model.pth')
    model.load_state_dict(checkpoint['model_state_dict'])
    final_accuracy, _, _, _, _ = trainer.validate()

    print(f"最终验证准确率: {final_accuracy:.4f}")
    print("\n分类报告（前20类）:")
    label_counts = collections.Counter(final_labels)
    top_20_labels = [label for label, _ in label_counts.most_common(20)]
    print(classification_report(
        final_labels, final_preds,
        labels=top_20_labels, target_names=[f'类别{l}' for l in top_20_labels],
        digits=4, zero_division=0
    ))

    print(f"\n🎯 任务二完成！最佳准确率: {best_accuracy:.4f}")
    print(f"📁 所有可视化文件已保存至: {SAVE_DIR}")


# ========== 8. 验证函数 ==========
def validate_few_shot_setup():
    """验证少样本设置"""
    print("验证少样本设置...")

    data_files = find_data_files()
    if not data_files["train_list"]:
        return False

    # 检查每个类别的图像数量
    class_counts = collections.defaultdict(int)
    with open(data_files["train_list"], 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parts = re.split(r'\s+', line, maxsplit=1)
        if len(parts) == 2:
            try:
                label = int(parts[1])
                if 0 <= label <= 60:
                    class_counts[label] += 1
            except ValueError:
                continue

    print(f"发现 {len(class_counts)} 个类别")
    for label in sorted(class_counts.keys())[:20]:  # 只打印前20类
        count = class_counts[label]
        status = "✅" if count >= 10 else "⚠️"
        print(f"  类别 {label}: {count} 张图像 {status}")
    if len(class_counts) > 20:
        print("  ...（其余类别省略）")

    # 检查是否有足够类别满足少样本要求
    sufficient_classes = sum(1 for count in class_counts.values() if count >= 10)
    print(f"满足10张图像要求的类别数: {sufficient_classes}/61")

    return sufficient_classes >= 50  # 至少50个类别满足要求


if __name__ == "__main__":
    # 首先验证少样本设置
    if validate_few_shot_setup():
        print("\n少样本设置验证通过，开始训练...")
        train_few_shot_model()
    else:
        print("少样本设置验证失败，请检查数据文件")