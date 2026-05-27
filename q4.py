import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, recall_score, f1_score
import matplotlib.pyplot as plt
import seaborn as sns
import os
import glob
import re
from datetime import datetime
import cv2
from tqdm import tqdm

# ========== 1. 病害详细信息映射（贴合附件文档标签体系） ==========
DISEASE_DETAILS = {
    0: {"name": "苹果健康", "description": "苹果叶片无明显病害症状，生长状态良好",
        "suggestion": "保持现有种植管理措施，定期监测"},
    1: {"name": "苹果斑点落叶病", "description": "叶片出现圆形或不规则褐色斑点，边缘清晰，后期斑点扩大并穿孔",
        "suggestion": "及时清除病叶，喷施多菌灵或甲基托布津"},
    2: {"name": "苹果褐斑病", "description": "叶片呈现暗褐色不规则病斑，表面产生黑色小点，严重时叶片脱落",
        "suggestion": "加强通风透光，喷施苯醚甲环唑或戊唑醇"},
    6: {"name": "樱桃健康", "description": "樱桃叶片无病害症状，光合作用正常",
        "suggestion": "常规水肥管理，注意蚜虫防治"},
    7: {"name": "樱桃穿孔病", "description": "叶片出现圆形或不规则褐色病斑，后期病斑脱落形成穿孔",
        "suggestion": "喷施波尔多液或噻唑锌"},
    8: {"name": "樱桃褐斑病", "description": "叶片呈现褐色圆形病斑，中心颜色较浅，边缘深色",
        "suggestion": "加强排水，喷施嘧菌酯或肟菌酯"},
    9: {"name": "玉米健康", "description": "玉米叶片无病害症状，光合作用正常",
        "suggestion": "常规水肥管理，注意地下害虫防治"},
    10: {"name": "玉米大斑病", "description": "叶片出现梭形黄褐色大斑，病斑沿叶脉扩展",
        "suggestion": "轮作倒茬，喷施丙环唑或嘧菌酯"},
    11: {"name": "玉米小斑病", "description": "叶片出现椭圆形黄褐色小斑，病斑密集",
        "suggestion": "选用抗病品种，喷施苯醚甲环唑或吡唑醚菌酯"},
    17: {"name": "葡萄健康", "description": "葡萄叶片无病害症状，光合作用正常",
        "suggestion": "常规水肥管理，注意霜霉病预防"},
    18: {"name": "葡萄黑腐病", "description": "叶片出现圆形褐色病斑，中心灰白色，边缘黑色",
        "suggestion": "清除病残体，喷施代森锰锌或甲基硫菌灵"},
    19: {"name": "葡萄褐斑病", "description": "叶片出现不规则褐色病斑，严重时叶片干枯",
        "suggestion": "加强通风，喷施戊唑醇或氟硅唑"},
    # 可根据附件文档扩展更多病害详情
}


# ========== 2. 文件查找与解析函数（适配附件数据结构） ==========
def find_data_files(base_dir="C:/Users/ASUS/Desktop/Problem B：Data"):
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


# ========== 3. 作物类型与严重程度映射（严格对齐附件文档分级规则） ==========
def get_crop_type(disease_class):
    """根据附件文档的10种目标作物映射（苹果、樱桃、玉米、葡萄等）"""
    crop_mapping = {
        "苹果": [0, 1, 2, 3, 4, 5], "樱桃": [6, 7, 8],
        "玉米": [9, 10, 11, 12, 13, 14, 15, 16], "葡萄": [17, 18, 19, 20, 21, 22, 23],
        "柑桔": [24, 25, 26], "桃": [27, 28, 29], "辣椒": [30, 31, 32],
        "马铃薯": [33, 34, 35, 36, 37], "草莓": [38, 39, 40], "番茄": [41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60]
    }
    for crop, classes in crop_mapping.items():
        if disease_class in classes:
            return crop
    return "其他"


def disease_to_severity(disease_class):
    """将附件文档的61类标签映射为健康/一般/严重三级"""
    # 健康类别（附件文档中10个健康标签，对应ID：0、6、9、17、27、30、33、38、41）
    healthy_ids = {0, 6, 9, 17, 27, 30, 33, 38, 41}
    if disease_class in healthy_ids:
        return 0  # 健康
    # 严重疾病类别（附件文档中24个严重等级标签，示例ID：2、5、8、11、13、15、19、21、23、26、29、32、35、37、40、43、45、47、49、51、53、55、57、59）
    severe_ids = {
        2, 5, 8, 11, 13, 15, 19, 21, 23, 26, 29, 32, 35, 37, 40,
        43, 45, 47, 49, 51, 53, 55, 57, 59
    }
    if disease_class in severe_ids:
        return 2  # 严重疾病
    return 1  # 一般疾病


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


# ========== 5. 多任务网络模型（双任务协同+轻量部署适配） ==========
## ========== 5. 多任务网络模型（双任务协同+轻量部署适配） ==========
class CrossTaskAttention(nn.Module):
    def __init__(self, input_dim, hidden_dim):
        super().__init__()
        self.disease_query = nn.Linear(input_dim, hidden_dim)
        self.severity_query = nn.Linear(input_dim, hidden_dim)
        self.value_proj = nn.Linear(input_dim, hidden_dim)

    def forward(self, x):
        # x: (batch_size, input_dim)
        disease_q = self.disease_query(x)  # (batch, hidden_dim)
        severity_q = self.severity_query(x)  # (batch, hidden_dim)
        value = self.value_proj(x)  # (batch, hidden_dim)

        # 计算注意力权重
        disease_attention = torch.softmax(torch.sum(disease_q * value, dim=1, keepdim=True), dim=1)
        severity_attention = torch.softmax(torch.sum(severity_q * value, dim=1, keepdim=True), dim=1)

        # 应用注意力权重
        disease_features = disease_attention * value
        severity_features = severity_attention * value

        return disease_features, severity_features


class MultiTaskNetwork(nn.Module):
    def __init__(self, num_diseases, num_severity=3):
        super().__init__()
        # 使用预训练的MobileNetV2作为backbone
        self.backbone = torch.hub.load('pytorch/vision:v0.10.0', 'mobilenet_v2', pretrained=True)
        self.feature_extractor = self.backbone.features
        self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc_input_dim = 1280  # MobileNetV2输出维度

        # 冻结大部分层
        for param in list(self.feature_extractor.parameters())[:-3]:
            param.requires_grad = False

        # 交叉注意力机制
        self.cross_attention = CrossTaskAttention(self.fc_input_dim, 256)

        # 疾病分类头
        self.disease_head = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(128, num_diseases)
        )

        # 严重程度分类头
        self.severity_head = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(128, num_severity)
        )

        # 参数统计
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        print(f"模型总参数: {total_params:,} (可训练: {trainable_params:,})")

    def forward(self, x):
        # 特征提取
        features = self.feature_extractor(x)
        features = self.avg_pool(features).view(features.size(0), -1)

        # 交叉注意力
        disease_features, severity_features = self.cross_attention(features)

        # 分类
        disease_output = self.disease_head(disease_features)
        severity_output = self.severity_head(severity_features)

        return disease_output, severity_output, features


# ========== 6. 诊断报告生成器（贴合附件文档“可读可执行”要求） ==========
def batch_generate_reports(model, dataloader, device, disease_mapping, max_reports=30):
    os.makedirs("diagnostic_reports", exist_ok=True)
    model.eval()
    reverse_disease_mapping = {v: k for k, v in disease_mapping.items()}
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
                pred_disease_id = reverse_disease_mapping[disease_preds[i].item()]
                pred_severity = severity_preds[i].item()
                crop_type = get_crop_type(pred_disease_id)

                # 关联附件文档的病害详情
                disease_info = DISEASE_DETAILS.get(pred_disease_id, {
                    "name": f"未知病害_{pred_disease_id}",
                    "description": "该病害暂无详细描述信息（可参考附件文档补充）",
                    "suggestion": "建议结合附件文档的专业标注进一步诊断"
                })
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


# ========== 7. 纯PyTorch实现Grad-CAM可视化（解释模型决策依据） ==========
def grad_cam_visualization(model, dataloader, device, num_samples=3, output_dir="grad_cam_visualizations"):
    os.makedirs(output_dir, exist_ok=True)
    model.eval()

    # 定位MobileNetV2最后一层卷积层（用于特征可视化）
    target_layer = model.feature_extractor[-1]

    # 存储梯度和特征图的变量
    gradients = None
    features = None

    # 梯度钩子：保存反向传播梯度
    def save_gradients(module, grad_in, grad_out):
        nonlocal gradients
        gradients = grad_out[0]  # 捕获梯度输出

    # 特征钩子：保存前向传播特征图
    def save_features(module, feat_in, feat_out):
        nonlocal features
        features = feat_out.detach()  # 捕获特征图输出

    # 注册钩子
    grad_hook = target_layer.register_backward_hook(save_gradients)
    feat_hook = target_layer.register_forward_hook(save_features)

    sample_count = 0
    with torch.no_grad():
        for images, _, _, filenames in dataloader:
            if sample_count >= num_samples:
                break
            images = images.to(device)
            for i in range(len(images)):
                if sample_count >= num_samples:
                    break
                img_tensor = images[i:i + 1].requires_grad_(True)  # 需保留梯度用于反向传播
                img_path = dataloader.dataset.image_paths[sample_count]

                # 1. 前向传播获取疾病分类输出
                disease_output, _, _ = model(img_tensor)

                # 2. 反向传播（针对预测的疾病类别）
                pred_class = disease_output.argmax(dim=1).item()
                model.zero_grad()
                disease_output[:, pred_class].backward()  # 计算类别梯度

                # 3. 计算Grad-CAM热力图
                weights = torch.mean(gradients, dim=[2, 3], keepdim=True)  # 全局平均池化梯度
                cam = torch.sum(weights * features, dim=1).squeeze()  # 加权求和特征图
                cam = torch.relu(cam)  # 仅保留对类别有正贡献的区域

                # 4. 归一化并上采样到原图尺寸
                cam = cam.cpu().detach().numpy()
                cam = cv2.resize(cam, (128, 128))  # 与输入图像尺寸对齐
                cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)  # 归一化到[0,1]

                # 5. 加载原始图像并叠加热力图
                original_img = Image.open(img_path).convert('RGB').resize((128, 128))
                img_np = np.array(original_img) / 255.0  # 图像归一化
                cam_colored = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)  # 伪彩色热力图
                cam_colored = cv2.cvtColor(cam_colored, cv2.COLOR_BGR2RGB) / 255.0  # 转RGB并归一化
                visualization = img_np * 0.6 + cam_colored * 0.4  # 图像与热力图融合

                # 6. 保存可视化结果
                save_path = os.path.join(output_dir, f"grad_cam_{filenames[i]}")
                plt.imsave(save_path, visualization)
                print(f"✅ 保存Grad-CAM可视化结果: {save_path}")
                sample_count += 1

    # 移除钩子（避免内存泄漏）
    grad_hook.remove()
    feat_hook.remove()
    print(f"Grad-CAM可视化结果已保存至 {output_dir} 目录（共{sample_count}个样本）")


# ========== 8. 风险评估功能（支撑附件文档“精准防控”决策） ==========
def confidence_based_risk_assessment(model, dataloader, device, disease_mapping, sample_ratio=0.1):
    print("\n=== 作物病害风险等级评估（基于附件文档分级规则） ===")
    model.eval()
    reverse_disease_mapping = {v: k for k, v in disease_mapping.items()}
    risk_stats = {"高风险（需紧急防控）": 0, "中风险（需密切监测）": 0, "低风险（常规管理）": 0, "不确定（需人工复核）": 0}
    total_samples = 0
    max_samples = int(len(dataloader.dataset) * sample_ratio)  # 限制评估样本量，提升效率

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

                # 基于置信度和严重程度的风险分级（贴合附件文档“防控优先级”）
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
    sns.barplot(x=list(risk_stats.keys()), y=list(risk_stats.values()), palette="viridis")
    plt.title("作物病害风险等级分布（基于附件文档分级）")
    plt.xlabel("风险等级")
    plt.ylabel("样本数量")
    plt.xticks(rotation=30)
    for i, v in enumerate(risk_stats.values()):
        plt.text(i, v + 0.5, str(v), ha='center')
    plt.tight_layout()
    plt.savefig("risk_distribution.png", dpi=300)
    plt.close()
    print("✅ 风险分布可视化图已保存为 risk_distribution.png")


# ========== 9. 多任务训练器（平衡双任务损失与训练效率） ==========
class MultiTaskTrainer:
    def __init__(self, model, disease_weight=1.0, severity_weight=0.8):
        self.model = model
        self.disease_weight = disease_weight
        self.severity_weight = severity_weight
        self.disease_criterion = nn.CrossEntropyLoss()
        self.severity_criterion = nn.CrossEntropyLoss()
        self.optimizer = optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-4)
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(self.optimizer, 'min', patience=3, factor=0.5)

    def train_epoch(self, dataloader, device):
        """训练一个epoch"""
        self.model.train()
        total_loss = 0.0
        disease_correct = 0
        severity_correct = 0
        total_samples = 0

        for batch_idx, (images, disease_labels, severity_labels, _) in enumerate(dataloader):
            images = images.to(device)
            disease_labels = disease_labels.to(device)
            severity_labels = severity_labels.to(device)

            self.optimizer.zero_grad()
            disease_output, severity_output, _ = self.model(images)

            # 计算损失
            disease_loss = self.disease_criterion(disease_output, disease_labels)
            severity_loss = self.severity_criterion(severity_output, severity_labels)
            loss = self.disease_weight * disease_loss + self.severity_weight * severity_loss

            loss.backward()
            self.optimizer.step()

            total_loss += loss.item()

            # 计算准确率
            _, disease_preds = torch.max(disease_output, 1)
            _, severity_preds = torch.max(severity_output, 1)

            disease_correct += (disease_preds == disease_labels).sum().item()
            severity_correct += (severity_preds == severity_labels).sum().item()
            total_samples += disease_labels.size(0)

        # 计算平均指标
        avg_loss = total_loss / len(dataloader)
        disease_acc = 100. * disease_correct / total_samples
        severity_acc = 100. * severity_correct / total_samples

        return avg_loss, disease_acc, severity_acc

    def evaluate(self, dataloader, device):
        """评估模型 - 修复数据类型问题"""
        self.model.eval()
        disease_logits = []
        severity_logits = []
        disease_labels = []
        severity_labels = []

        with torch.no_grad():
            for images, d_true, s_true, _ in dataloader:
                images = images.to(device)
                d_out, s_out, _ = self.model(images)

                disease_logits.append(d_out.cpu())
                severity_logits.append(s_out.cpu())
                disease_labels.append(d_true)
                severity_labels.append(s_true)

        # 合并所有batch的结果
        disease_logits = torch.cat(disease_logits, dim=0)
        severity_logits = torch.cat(severity_logits, dim=0)
        disease_labels = torch.cat(disease_labels, dim=0)
        severity_labels = torch.cat(severity_labels, dim=0)

        # 计算预测类别
        _, disease_preds = torch.max(disease_logits, 1)
        _, severity_preds = torch.max(severity_logits, 1)

        return (disease_logits, severity_logits,
                disease_preds.numpy(), severity_preds.numpy(),
                disease_labels.numpy(), severity_labels.numpy())


# ========== 10. 数据变换（适配MobileNetV2输入与数据增强） ==========
def create_data_transforms():
    # 图像尺寸调整为128x128，平衡计算效率与特征保留
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


# ========== 11. 单任务模型（用于多任务协同效应评估） ==========
class SingleTaskDiseaseModel(nn.Module):
    def __init__(self, num_diseases):
        super().__init__()
        self.backbone = torch.hub.load('pytorch/vision:v0.10.0', 'mobilenet_v2', pretrained=True)
        self.backbone.classifier[1] = nn.Linear(1280, num_diseases)  # 适配附件文档61类
        for param in list(self.backbone.features.parameters())[:-3]:
            param.requires_grad = False

    def forward(self, x):
        return self.backbone(x)


class SingleTaskSeverityModel(nn.Module):
    def __init__(self, num_severity=3):
        super().__init__()
        self.backbone = torch.hub.load('pytorch/vision:v0.10.0', 'mobilenet_v2', pretrained=True)
        self.backbone.classifier[1] = nn.Linear(1280, num_severity)  # 适配附件文档3级
        for param in list(self.backbone.features.parameters())[:-3]:
            param.requires_grad = False

    def forward(self, x):
        return self.backbone(x)


# ========== 12. 协同效应计算（量化多任务联合价值） ==========
def calculate_synergy(mt_disease_acc, mt_severity_acc, st_disease_acc, st_severity_acc):
    """计算多任务学习相比单任务学习的性能增益"""
    disease_gain = mt_disease_acc - st_disease_acc
    severity_gain = mt_severity_acc - st_severity_acc
    avg_gain = (disease_gain + severity_gain) / 2
    print(f"\n=== 多任务协同效应评估结果（基于附件文档数据集） ===")
    print(f"疾病分类任务协同增益：{disease_gain:.2f}个百分点")
    print(f"严重程度分级任务协同增益：{severity_gain:.2f}个百分点")
    print(f"平均协同增益：{avg_gain:.2f}个百分点")
    return avg_gain


# ========== 13. 主函数（全流程驱动） ==========
def train_multitask_model(sample_ratio=0.5, num_epochs=15, early_stopping_patience=5):
    print("=" * 80)
    print("【问题四：多任务联合学习与可解释诊断】完整解决方案（修复版）")
    print("=" * 80)

    # 设备配置
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"当前训练设备: {device}")

    # 数据路径查找
    data_files = find_data_files()
    train_data_dir = data_files['train_dir']
    train_txt_file = data_files['train_txt']
    val_data_dir = data_files['val_dir']
    val_txt_file = data_files['val_txt']

    # 数据变换
    train_transform, val_transform = create_data_transforms()

    # 加载数据集
    try:
        print("\n=== 加载训练集 ===")
        train_dataset = MultiTaskDataset(
            data_dir=train_data_dir,
            txt_file=train_txt_file,
            transform=train_transform,
            sample_ratio=sample_ratio
        )
        print("\n=== 加载验证集 ===")
        val_dataset = MultiTaskDataset(
            data_dir=val_data_dir,
            txt_file=val_txt_file,
            transform=val_transform,
            sample_ratio=min(sample_ratio, 1.0)
        )
    except Exception as e:
        print(f"数据集加载失败: {str(e)}")
        return

    # 数据加载器
    batch_size = 16 if device.type == "cuda" else 4
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True,
        num_workers=0, pin_memory=False
    )
    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False,
        num_workers=0, pin_memory=False
    )

    # 初始化模型
    model = MultiTaskNetwork(
        num_diseases=train_dataset.num_diseases,
        num_severity=3
    ).to(device)

    # 初始化训练器
    trainer = MultiTaskTrainer(model)

    # 训练过程
    best_val_loss = float('inf')
    early_stopping_counter = 0
    best_disease_acc = 0.0
    best_severity_acc = 0.0

    train_losses = []
    val_losses = []
    train_disease_accs = []
    train_severity_accs = []
    val_disease_accs = []
    val_severity_accs = []

    for epoch in range(num_epochs):
        print(f"\n=== Epoch {epoch + 1}/{num_epochs} ===")

        # 训练
        train_loss, train_disease_acc, train_severity_acc = trainer.train_epoch(train_loader, device)

        # 验证 - 使用修复后的评估方法
        disease_logits, severity_logits, d_preds, s_preds, d_labels, s_labels = trainer.evaluate(val_loader, device)

        # 修复：正确计算验证损失
        disease_loss = trainer.disease_criterion(
            disease_logits.to(device),
            torch.tensor(d_labels, dtype=torch.long).to(device)
        )
        severity_loss = trainer.severity_criterion(
            severity_logits.to(device),
            torch.tensor(s_labels, dtype=torch.long).to(device)
        )
        val_loss = (disease_loss + severity_loss).item()

        # 计算验证准确率
        val_disease_acc = 100. * accuracy_score(d_labels, d_preds)
        val_severity_acc = 100. * accuracy_score(s_labels, s_preds)

        # 记录训练历史
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        train_disease_accs.append(train_disease_acc)
        train_severity_accs.append(train_severity_acc)
        val_disease_accs.append(val_disease_acc)
        val_severity_accs.append(val_severity_acc)

        print(f"训练损失: {train_loss:.4f}")
        print(f"训练准确率: 疾病分类 {train_disease_acc:.2f}% | 严重程度分级 {train_severity_acc:.2f}%")
        print(f"验证损失: {val_loss:.4f}")
        print(f"验证准确率: 疾病分类 {val_disease_acc:.2f}% | 严重程度分级 {val_severity_acc:.2f}%")

        # 早停机制
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_disease_acc = val_disease_acc
            best_severity_acc = val_severity_acc
            torch.save(model.state_dict(), 'best_multitask_model.pth')
            print("✅ 保存最佳模型权重")
            early_stopping_counter = 0
        else:
            early_stopping_counter += 1
            print(f"早停计数: {early_stopping_counter}/{early_stopping_patience}")
            if early_stopping_counter >= early_stopping_patience:
                print("⚠️ 触发早停机制，停止训练")
                break

        # 学习率调整
        trainer.scheduler.step(val_loss)

    # 最终评估
    print("\n" + "=" * 50)
    print("最终评估结果")
    print("=" * 50)
    print(f"最佳验证集疾病分类准确率: {best_disease_acc:.2f}%")
    print(f"最佳验证集严重程度分级准确率: {best_severity_acc:.2f}%")

    # 可视化训练历史
    plt.figure(figsize=(15, 5))

    # 损失曲线
    plt.subplot(1, 3, 1)
    plt.plot(train_losses, label='训练损失')
    plt.plot(val_losses, label='验证损失')
    plt.title('训练和验证损失')
    plt.xlabel('Epoch')
    plt.ylabel('损失')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # 疾病分类准确率
    plt.subplot(1, 3, 2)
    plt.plot(train_disease_accs, label='训练准确率')
    plt.plot(val_disease_accs, label='验证准确率')
    plt.title('疾病分类准确率')
    plt.xlabel('Epoch')
    plt.ylabel('准确率 (%)')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # 严重程度分类准确率
    plt.subplot(1, 3, 3)
    plt.plot(train_severity_accs, label='训练准确率')
    plt.plot(val_severity_accs, label='验证准确率')
    plt.title('严重程度分类准确率')
    plt.xlabel('Epoch')
    plt.ylabel('准确率 (%)')
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('training_history.png', dpi=300, bbox_inches='tight')
    plt.show()

    # 生成详细评估报告
    generate_detailed_evaluation(model, val_loader, device, train_dataset.disease_mapping)

    # 生成诊断报告
    batch_generate_reports(model, val_loader, device, train_dataset.disease_mapping)

    print("\n🎉 所有任务执行完毕！")


def generate_detailed_evaluation(model, val_loader, device, disease_mapping):
    """生成详细评估报告"""
    model.eval()
    disease_preds = []
    severity_preds = []
    disease_labels = []
    severity_labels = []

    with torch.no_grad():
        for images, d_true, s_true, _ in val_loader:
            images = images.to(device)
            d_out, s_out, _ = model(images)

            _, d_pred = torch.max(d_out, 1)
            _, s_pred = torch.max(s_out, 1)

            disease_preds.extend(d_pred.cpu().numpy())
            severity_preds.extend(s_pred.cpu().numpy())
            disease_labels.extend(d_true.numpy())
            severity_labels.extend(s_true.numpy())

    # 分类报告
    severity_names = ["健康", "一般疾病", "严重疾病"]
    print("\n" + "=" * 50)
    print("详细分类报告")
    print("=" * 50)

    print("\n严重程度分类报告:")
    print(classification_report(severity_labels, severity_preds,
                                target_names=severity_names, digits=4))

    # 混淆矩阵
    cm = confusion_matrix(severity_labels, severity_preds)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=severity_names, yticklabels=severity_names)
    plt.title('严重程度分类混淆矩阵')
    plt.ylabel('真实标签')
    plt.xlabel('预测标签')
    plt.tight_layout()
    plt.savefig('severity_confusion_matrix.png', dpi=300, bbox_inches='tight')
    plt.show()

    # 计算各类别指标
    disease_acc = accuracy_score(disease_labels, disease_preds)
    severity_acc = accuracy_score(severity_labels, severity_preds)
    disease_f1 = f1_score(disease_labels, disease_preds, average='macro')
    severity_f1 = f1_score(severity_labels, severity_preds, average='macro')

    print(f"\n关键指标:")
    print(f"疾病分类准确率: {disease_acc:.4f}")
    print(f"疾病分类宏平均F1: {disease_f1:.4f}")
    print(f"严重程度分类准确率: {severity_acc:.4f}")
    print(f"严重程度分类宏平均F1: {severity_f1:.4f}")

    # 各类别召回率
    recall_scores = recall_score(severity_labels, severity_preds, average=None)
    print("\n各类别召回率:")
    for i, name in enumerate(severity_names):
        print(f"  {name}: {recall_scores[i]:.4f}")


if __name__ == "__main__":
    train_multitask_model(sample_ratio=0.5, num_epochs=15)