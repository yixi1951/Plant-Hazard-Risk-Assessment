"""训练/验证图像变换（田间场景：光照、色彩、轻微几何扰动）。"""
import torchvision.transforms as transforms

IMAGE_SIZE = 128
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def create_train_val_transforms(image_size: int = IMAGE_SIZE):
    train_transform = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.1),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.2, hue=0.03),
        transforms.RandomAffine(degrees=0, translate=(0.05, 0.05), scale=(0.92, 1.08)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        transforms.RandomErasing(p=0.1, scale=(0.02, 0.08), ratio=(0.3, 3.3)),
    ])
    val_transform = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])
    return train_transform, val_transform