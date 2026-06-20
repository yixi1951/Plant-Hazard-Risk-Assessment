"""
农业病害诊断项目 —— 共享工具函数
集中存放数据集查找、标注解析、作物/严重程度映射等重复逻辑。
"""

import os
import glob

from scripts.disease_catalog import DISEASE_DETAILS


# ========================================================================
# 字体配置
# ========================================================================
def configure_chinese_font():
    """配置 matplotlib 中文字体"""
    import matplotlib.font_manager as font_manager
    import matplotlib.pyplot as plt
    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    preferred_fonts = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]
    chosen_font = next((f for f in preferred_fonts if f in available_fonts), None)
    if chosen_font:
        plt.rcParams["font.sans-serif"] = [chosen_font]
    else:
        plt.rcParams["font.sans-serif"] = preferred_fonts
    plt.rcParams["axes.unicode_minus"] = False


# ========================================================================
# 数据集文件查找
# ========================================================================
def find_data_files(base_dir=None):
    """
    查找 Problem B 竞赛数据集的训练/验证目录和 TXT 标注文件。

    优先级: 显式参数 > 环境变量 AGRI_DATA_DIR > 默认值 data/mock_problem_b
    """
    if base_dir is None:
        base_dir = os.environ.get("AGRI_DATA_DIR", "data/mock_problem_b")

    if not os.path.exists(base_dir):
        raise FileNotFoundError(
            f"数据根目录不存在: {base_dir}。请使用 --data-dir 指定，或设置环境变量 AGRI_DATA_DIR"
        )

    data_files = {'train_txt': None, 'train_dir': None, 'val_txt': None, 'val_dir': None}
    problem_b_dir = base_dir
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

    train_dir = os.path.join(problem_b_dir, 'AgriculturalDisease_trainingset', 'images')
    data_files['train_dir'] = train_dir if os.path.exists(train_dir) else None
    data_files['train_txt'] = find_best_txt(os.path.join(problem_b_dir, 'AgriculturalDisease_trainingset'))

    val_dir = os.path.join(problem_b_dir, 'AgriculturalDisease_validationset', 'images')
    data_files['val_dir'] = val_dir if os.path.exists(val_dir) else None
    data_files['val_txt'] = find_best_txt(os.path.join(problem_b_dir, 'AgriculturalDisease_validationset'))

    for key, desc in [('train_dir', '训练集images目录'), ('val_dir', '验证集images目录'),
                      ('train_txt', '训练集TXT标注文件'), ('val_txt', '验证集TXT标注文件')]:
        if data_files[key] and os.path.exists(data_files[key]):
            print(f"✅ 找到{desc}: {data_files[key]}")
        else:
            print(f"❌ 未找到{desc}，请检查数据路径！")
    return data_files


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


# ========================================================================
# TXT 标注文件解析
# ========================================================================
def parse_txt_annotations(txt_path):
    """解析 TXT 格式的标注文件，返回标注字典列表。"""
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


# ========================================================================
# 图像索引构建
# ========================================================================
def build_image_index(data_dirs):
    """构建图像文件名（不含扩展名）到完整路径的映射。"""
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


# ========================================================================
# 标签名称规范化
# ========================================================================
def _normalize_label_name(label_name):
    return str(label_name).replace('_', ' ').replace('-', ' ').strip().lower()


def infer_severity_from_name(label_name):
    """根据标签名称关键字推断严重程度（用于公开数据集）。"""
    name = _normalize_label_name(label_name)
    if any(keyword in name for keyword in ['healthy', 'normal', 'health']):
        return 0
    if any(keyword in name for keyword in ['blight', 'rust', 'virus', 'mildew', 'rot', 'scab', 'canker', 'spot', 'smut', 'burn']):
        return 2
    return 1


# ========================================================================
# 病害详情查询
# ========================================================================
def get_disease_details(disease_label):
    """根据病害标签（int 或 str）返回病害名称、描述与建议。"""
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


# ========================================================================
# 作物类型推断
# ========================================================================
def get_crop_type(disease_class):
    """
    根据病害类别ID或标签名称获取作物类型。
    兼容附件文档的10种目标作物与公开数据集名称。
    """
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
            '番茄': ['tomato', '番茄'],
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
        "番茄": [41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60],
    }
    for crop, classes in crop_mapping.items():
        if disease_class in classes:
            return crop
    return "其他"


# ========================================================================
# 严重程度映射
# ========================================================================
def disease_to_severity(disease_class):
    """
    将病害类别映射为三级严重程度: 0-健康, 1-一般疾病, 2-严重疾病。
    兼容附件文档61类标签体系与公开数据集的名称关键字。
    """
    if isinstance(disease_class, str):
        return infer_severity_from_name(disease_class)

    healthy_ids = {0, 6, 9, 17, 27, 30, 33, 38, 41}
    if disease_class in healthy_ids:
        return 0

    severe_ids = {
        2, 5, 8, 11, 13, 15, 19, 21, 23, 26, 29, 32, 35, 37, 40,
        43, 45, 47, 49, 51, 53, 55, 57, 59,
    }
    if disease_class in severe_ids:
        return 2
    return 1
