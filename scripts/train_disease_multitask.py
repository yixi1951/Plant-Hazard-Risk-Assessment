import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, random_split
from torchvision import datasets, transforms
from tqdm import tqdm

from scripts.inference_utils import IMAGE_SIZE, MultiTaskNetwork


HEALTHY_KEYWORDS = ("healthy", "health", "normal", "无病", "健康", "background", "control")
SEVERE_KEYWORDS = ("blight", "rust", "virus", "mildew", "rot", "scab", "canker", "spot", "smut", "burn", "wilt", "mosaic")


def _normalize(name: str) -> str:
    return str(name).replace('_', ' ').replace('-', ' ').strip().lower()


def infer_severity_from_name(name: str) -> int:
    normalized = _normalize(name)
    if any(keyword in normalized for keyword in HEALTHY_KEYWORDS):
        return 0
    if any(keyword in normalized for keyword in SEVERE_KEYWORDS):
        return 2
    return 1


def build_train_transform():
    return transforms.Compose([
        transforms.RandomResizedCrop(IMAGE_SIZE, scale=(0.75, 1.0)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(15),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


def build_eval_transform():
    return transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


class DiseaseFolderDataset(Dataset):
    def __init__(self, root_dir, transform=None):
        self.root_dir = Path(root_dir)
        self.transform = transform
        self.dataset = datasets.ImageFolder(self.root_dir)
        self.class_names = self.dataset.classes
        self.class_to_idx = self.dataset.class_to_idx
        self.severity_by_class_idx = {idx: infer_severity_from_name(name) for name, idx in self.class_to_idx.items()}

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, idx):
        image, disease_label = self.dataset[idx]
        if self.transform:
            image = self.transform(image)
        class_name = self.class_names[disease_label]
        severity_label = self.severity_by_class_idx[disease_label]
        path, _ = self.dataset.samples[idx]
        return image, torch.tensor(disease_label, dtype=torch.long), torch.tensor(severity_label, dtype=torch.long), path, class_name


@dataclass
class EpochMetrics:
    epoch: int
    train_loss: float
    val_loss: float
    disease_acc: float
    severity_acc: float


def _accuracy(preds, labels):
    return (preds == labels).float().mean().item() if len(labels) else 0.0


def _prepare_loaders(train_dir, val_dir, batch_size, num_workers, val_ratio, seed):
    base_train_dataset = DiseaseFolderDataset(train_dir, transform=build_train_transform())
    if val_dir and Path(val_dir).exists():
        val_dataset = DiseaseFolderDataset(val_dir, transform=build_eval_transform())
        train_dataset = base_train_dataset
    else:
        total_len = len(base_train_dataset)
        val_len = max(1, int(total_len * val_ratio))
        train_len = max(1, total_len - val_len)
        train_dataset, val_dataset = random_split(
            base_train_dataset,
            [train_len, val_len],
            generator=torch.Generator().manual_seed(seed),
        )
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=torch.cuda.is_available())
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=torch.cuda.is_available())
    return base_train_dataset, train_dataset, val_dataset, train_loader, val_loader


def train_one_epoch(model, loader, criterion, optimizer, device, disease_loss_weight=1.0, severity_loss_weight=0.8):
    model.train()
    total_loss = 0.0
    for images, disease_labels, severity_labels, *_ in tqdm(loader, desc='Train', leave=False):
        images = images.to(device)
        disease_labels = disease_labels.to(device)
        severity_labels = severity_labels.to(device)

        optimizer.zero_grad()
        disease_logits, severity_logits, _ = model(images)
        disease_loss = criterion(disease_logits, disease_labels)
        severity_loss = criterion(severity_logits, severity_labels)
        loss = disease_loss_weight * disease_loss + severity_loss_weight * severity_loss
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    return total_loss / max(1, len(loader))


@torch.no_grad()
def evaluate(model, loader, criterion, device, disease_loss_weight=1.0, severity_loss_weight=0.8):
    model.eval()
    total_loss = 0.0
    disease_preds = []
    disease_labels_all = []
    severity_preds = []
    severity_labels_all = []

    for images, disease_labels, severity_labels, *_ in tqdm(loader, desc='Val', leave=False):
        images = images.to(device)
        disease_labels = disease_labels.to(device)
        severity_labels = severity_labels.to(device)
        disease_logits, severity_logits, _ = model(images)
        disease_loss = criterion(disease_logits, disease_labels)
        severity_loss = criterion(severity_logits, severity_labels)
        loss = disease_loss_weight * disease_loss + severity_loss_weight * severity_loss
        total_loss += loss.item()

        disease_preds.extend(disease_logits.argmax(dim=1).cpu())
        disease_labels_all.extend(disease_labels.cpu())
        severity_preds.extend(severity_logits.argmax(dim=1).cpu())
        severity_labels_all.extend(severity_labels.cpu())

    disease_acc = _accuracy(torch.stack(disease_preds) if disease_preds else torch.tensor([]), torch.stack(disease_labels_all) if disease_labels_all else torch.tensor([]))
    severity_acc = _accuracy(torch.stack(severity_preds) if severity_preds else torch.tensor([]), torch.stack(severity_labels_all) if severity_labels_all else torch.tensor([]))
    return total_loss / max(1, len(loader)), disease_acc, severity_acc


def main():
    parser = argparse.ArgumentParser(description='训练可识别具体病害名称的多任务模型')
    parser.add_argument('--train-dir', type=str, required=True, help='训练集目录，内部为类别文件夹')
    parser.add_argument('--val-dir', type=str, default='', help='验证集目录，内部为类别文件夹')
    parser.add_argument('--save-path', type=str, default='artifacts/disease_multitask.pth', help='模型权重保存路径')
    parser.add_argument('--epochs', type=int, default=15)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--lr', type=float, default=5e-4)
    parser.add_argument('--weight-decay', type=float, default=1e-4)
    parser.add_argument('--val-ratio', type=float, default=0.2, help='未提供 val-dir 时，从 train-dir 划分验证集的比例')
    parser.add_argument('--num-workers', type=int, default=2)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--patience', type=int, default=5)
    parser.add_argument('--device', type=str, default='')
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    base_dataset, train_dataset, val_dataset, train_loader, val_loader = _prepare_loaders(
        args.train_dir,
        args.val_dir or None,
        args.batch_size,
        args.num_workers,
        args.val_ratio,
        args.seed,
    )

    class_names = base_dataset.class_names
    num_diseases = len(class_names)
    num_severity = 3

    device = torch.device(args.device or ('cuda' if torch.cuda.is_available() else 'cpu'))
    model = MultiTaskNetwork(num_diseases=num_diseases, num_severity=num_severity).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=2, factor=0.5)

    save_path = Path(args.save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = save_path.with_suffix('.json')

    best_val_loss = float('inf')
    best_epoch = -1
    patience_left = args.patience
    history = []

    for epoch in range(1, args.epochs + 1):
        train_loss = train_one_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, disease_acc, severity_acc = evaluate(model, val_loader, criterion, device)
        scheduler.step(val_loss)

        record = EpochMetrics(epoch, float(train_loss), float(val_loss), float(disease_acc), float(severity_acc))
        history.append(asdict(record))
        print(f'[Epoch {epoch:02d}] train_loss={train_loss:.4f} val_loss={val_loss:.4f} disease_acc={disease_acc*100:.2f}% severity_acc={severity_acc*100:.2f}%')

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            patience_left = args.patience
            torch.save(model.state_dict(), save_path)
            metadata = {
                'class_names': class_names,
                'class_to_idx': base_dataset.class_to_idx,
                'num_diseases': num_diseases,
                'num_severity': num_severity,
                'healthy_indices': [idx for idx, name in enumerate(class_names) if infer_severity_from_name(name) == 0],
                'best_epoch': best_epoch,
                'best_val_loss': float(best_val_loss),
                'history': history,
            }
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            print(f'  -> saved best checkpoint to {save_path}')
        else:
            patience_left -= 1
            if patience_left <= 0:
                print(f'Early stopping at epoch {epoch}. Best epoch: {best_epoch}')
                break

    print('\n训练完成。')
    print(f'最佳模型: {save_path}')
    print(f'类别数: {num_diseases}')
    print(f'类别名称: {class_names}')
    print(f'元数据: {meta_path}')
    print('若要让 Web 页面使用新模型，可设置环境变量 MODEL_PATH 指向该权重文件。')


if __name__ == '__main__':
    main()