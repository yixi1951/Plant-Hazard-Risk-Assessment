import os
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import rcParams
import warnings
warnings.filterwarnings('ignore')  # 过滤字体警告

# --------------------------
# 1. 配置可视化样式（专业美观，支持中文）
# --------------------------
plt.rcParams.update({
    'font.sans-serif': ['SimHei', 'DejaVu Sans'],  # 中文字体+英文备用
    'axes.unicode_minus': False,  # 解决负号显示问题
    'figure.figsize': (16, 12),  # 画布尺寸（适配多子图）
    'figure.dpi': 300,  # 高清输出（300 DPI，适配新版matplotlib）
    'axes.grid': True,  # 显示网格（便于读数）
    'grid.alpha': 0.3,  # 网格透明度（不遮挡数据）
    'legend.fontsize': 10,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10
})

# --------------------------
# 2. 从问题一训练日志提取核心数据（一一对应30个Epoch）
# --------------------------
# 训练轮次（1-30）
epochs = list(range(1, 31))

# 1. 损失指标（训练+验证）
train_loss = [
    3.1534, 2.4632, 2.1828, 2.2203, 1.8142, 2.0489, 1.8409, 1.9989, 1.5582, 1.6585,
    1.2713, 1.7706, 1.3087, 1.4625, 1.1533, 1.2227, 1.1992, 1.3023, 1.0696, 1.0407,
    1.0169, 0.7952, 1.0395, 0.7805, 0.9806, 0.7771, 0.7878, 0.7826, 0.6258, 0.7223
]
val_loss = [
    3.1231, 3.6952, 2.9666, 2.7530, 2.5975, 1.6921, 2.1901, 3.5271, 3.0512, 1.9630,
    1.5888, 1.4542, 1.8657, 1.4945, 1.0301, 1.4350, 1.9261, 0.9461, 1.1242, 1.4718,
    1.0147, 0.8619, 1.3121, 1.3508, 1.4127, 1.3516, 0.9905, 1.1876, 0.6402, 1.4945
]

# 2. 准确率指标（训练+验证，%）
train_acc = [
    18.42, 31.38, 35.83, 33.58, 37.93, 38.43, 37.14, 40.95, 43.84, 47.19,
    50.06, 43.30, 50.59, 48.08, 50.13, 54.75, 55.64, 51.49, 54.84, 56.33,
    56.65, 60.28, 58.57, 60.88, 59.75, 63.55, 62.90, 61.36, 64.95, 64.38
]
val_acc = [
    28.01, 18.47, 36.04, 50.70, 50.41, 53.90, 63.65, 54.87, 60.05, 66.28,
    54.29, 67.67, 61.29, 69.21, 70.14, 65.97, 51.80, 65.15, 68.70, 69.61,
    68.62, 68.97, 71.73, 73.14, 74.29, 65.59, 70.03, 71.33, 72.48, 74.73
]

# 3. 验证宏平均F1
val_f1 = [
    0.2003, 0.1318, 0.2816, 0.4172, 0.4128, 0.4577, 0.5273, 0.4810, 0.4893, 0.5840,
    0.4516, 0.5998, 0.5470, 0.6157, 0.6372, 0.5868, 0.4804, 0.5847, 0.6011, 0.6163,
    0.6348, 0.6306, 0.6572, 0.6611, 0.6951, 0.6126, 0.6736, 0.6621, 0.6651, 0.6967
]

# 4. 最佳模型信息（从日志提取：Epoch 30，验证准确率74.73%，F1=0.6967，损失1.4945）
best_epoch = 30
best_val_acc = 74.73
best_val_f1 = 0.6967
best_val_loss = 1.4945
best_train_acc = 64.38  # Epoch30训练准确率
best_train_loss = 0.7223  # Epoch30训练损失

# 5. 类别级性能（从最终分类报告提取：挑选样本量>50的重点类别，避免图表拥挤）
selected_classes = [0, 6, 9, 16, 24, 25, 26, 33, 41, 58, 59]  # 样本量较多的类别ID
class_names = [
    "苹果健康", "樱桃健康", "玉米健康", "玉米矮化花叶病毒", "柑桔健康",
    "柑桔黄化(一般)", "柑桔黄化(严重)", "马铃薯健康", "番茄健康",
    "番茄黄叶卷病毒(一般)", "番茄黄叶卷病毒(严重)"
]
class_precision = [0.9618, 0.9341, 0.9811, 0.9915, 0.9808, 0.5812, 0.7674, 0.9019, 0.9936, 0.4934, 0.9484]
class_recall = [0.8935, 1.0000, 0.9630, 1.0000, 0.9808, 0.8253, 0.3779, 0.9461, 0.9070, 0.9492, 0.4164]
class_f1 = [0.9264, 0.9659, 0.9720, 0.9957, 0.9808, 0.6820, 0.5064, 0.9234, 0.9483, 0.6493, 0.5787]


# --------------------------
# 3. 生成四合一可视化图表（训练趋势+类别性能）
# --------------------------
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))  # 2行2列子图

# --------------------------
# 子图1：训练 vs 验证损失趋势（突出最佳模型）
# --------------------------
ax1.plot(epochs, train_loss, label='训练损失', color='#2E86AB', linewidth=2.5, marker='o', markersize=3)
ax1.plot(epochs, val_loss, label='验证损失', color='#A23B72', linewidth=2.5, marker='s', markersize=3)
# 标注最佳模型的损失点
ax1.scatter(best_epoch, best_val_loss, color='red', s=80, zorder=5, edgecolor='black')
ax1.annotate(
    f'最佳模型\nEpoch {best_epoch}\n损失: {best_val_loss:.4f}',
    xy=(best_epoch, best_val_loss),
    xytext=(best_epoch-5, best_val_loss+0.8),
    arrowprops=dict(arrowstyle='->', color='red', alpha=0.8, lw=2),
    color='red', fontweight='bold', fontsize=9,
    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8)
)
ax1.set_title('农业病害分类模型 - 训练与验证损失趋势', fontweight='bold', pad=20)
ax1.set_xlabel('训练轮次（Epoch）')
ax1.set_ylabel('损失值（Focal Cross Entropy）')
ax1.legend(loc='upper right')
ax1.set_ylim(bottom=0)  # 损失值不小于0
ax1.set_xticks(epochs[::2])  # 每2个Epoch显示一个刻度，避免拥挤

# --------------------------
# 子图2：训练 vs 验证准确率趋势（突出最佳模型）
# --------------------------
ax2.plot(epochs, train_acc, label='训练准确率', color='#F18F01', linewidth=2.5, marker='o', markersize=3)
ax2.plot(epochs, val_acc, label='验证准确率', color='#C73E1D', linewidth=2.5, marker='s', markersize=3)
# 标注最佳模型的准确率点
ax2.scatter(best_epoch, best_val_acc, color='red', s=80, zorder=5, edgecolor='black')
ax2.annotate(
    f'最佳模型\nEpoch {best_epoch}\n准确率: {best_val_acc:.2f}%',
    xy=(best_epoch, best_val_acc),
    xytext=(best_epoch-8, best_val_acc-15),
    arrowprops=dict(arrowstyle='->', color='red', alpha=0.8, lw=2),
    color='red', fontweight='bold', fontsize=9,
    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8)
)
ax2.set_title('农业病害分类模型 - 训练与验证准确率趋势', fontweight='bold', pad=20)
ax2.set_xlabel('训练轮次（Epoch）')
ax2.set_ylabel('准确率（%）')
ax2.legend(loc='lower right')
ax2.set_ylim(0, 100)  # 准确率范围0-100%
ax2.set_xticks(epochs[::2])

# --------------------------
# 子图3：验证宏平均F1趋势（突出最佳模型）
# --------------------------
ax3.plot(epochs, val_f1, label='验证宏平均F1', color='#3B1F2B', linewidth=3, marker='o', markersize=3, markerfacecolor='yellow')
# 标注最佳模型的F1点
ax3.scatter(best_epoch, best_val_f1, color='red', s=80, zorder=5, edgecolor='black')
ax3.annotate(
    f'最佳模型\nEpoch {best_epoch}\n宏平均F1: {best_val_f1:.4f}',
    xy=(best_epoch, best_val_f1),
    xytext=(best_epoch-8, best_val_f1-0.15),
    arrowprops=dict(arrowstyle='->', color='red', alpha=0.8, lw=2),
    color='red', fontweight='bold', fontsize=9,
    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8)
)
ax3.set_title('农业病害分类模型 - 验证宏平均F1趋势', fontweight='bold', pad=20)
ax3.set_xlabel('训练轮次（Epoch）')
ax3.set_ylabel('宏平均F1值')
ax3.legend(loc='lower right')
ax3.set_ylim(0, 1)  # F1值范围0-1
ax3.set_xticks(epochs[::2])

# --------------------------
# 子图4：重点类别性能对比（样本量>50，避免拥挤）
# --------------------------
x = np.arange(len(selected_classes))  # 类别索引
width = 0.25  # 柱状图宽度

# 绘制三类指标柱状图
bars1 = ax4.bar(x - width, class_precision, width, label='精准率（Precision）', color='#6A994E', alpha=0.8)
bars2 = ax4.bar(x, class_recall, width, label='召回率（Recall）', color='#BC4749', alpha=0.8)
bars3 = ax4.bar(x + width, class_f1, width, label='F1分数', color='#277DA1', alpha=0.8)

# 添加数值标签（仅显示F1分数，避免拥挤）
for i, bar in enumerate(bars3):
    height = bar.get_height()
    ax4.text(bar.get_x() + bar.get_width()/2., height + 0.01,
             f'{class_f1[i]:.2f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

ax4.set_title('重点类别性能对比（样本量>50）', fontweight='bold', pad=20)
ax4.set_xlabel('作物病害类别')
ax4.set_ylabel('性能指标值（0-1）')
ax4.set_xticks(x)
ax4.set_xticklabels(class_names, rotation=45, ha='right')  # 类别名称旋转45度，避免重叠
ax4.legend(loc='lower right')
ax4.set_ylim(0, 1.1)  # 留出空间显示数值标签

# --------------------------
# 4. 整体布局调整与保存
# --------------------------
plt.tight_layout()  # 自动调整子图间距
plt.subplots_adjust(hspace=0.3, wspace=0.3)  # 垂直/水平间距
save_path = 'task1_training_visualization.png'
plt.savefig(save_path, bbox_inches='tight', dpi=300)  # 保存高清图像
plt.close()

# --------------------------
# 5. 输出完成信息与关键结论
# --------------------------
print("=" * 60)
print("✅ 问题一训练结果可视化图像已生成！")
print(f"📁 保存路径: {os.path.abspath(save_path)}")
print("\n🔍 关键结论总结:")
print(f"1. 最佳模型性能（Epoch {best_epoch}）:")
print(f"   - 验证准确率: {best_val_acc:.2f}% | 验证宏平均F1: {best_val_f1:.4f}")
print(f"   - 训练准确率: {best_train_acc:.2f}% | 训练损失: {best_train_loss:.4f}")
print("2. 训练趋势特征:")
print("   - 训练损失从3.15降至0.72，模型有效收敛；")
print("   - 验证准确率从28.01%提升至74.73%，泛化能力显著；")
print("   - 部分Epoch（如2、17）验证性能波动，属正常训练现象。")
print("3. 类别级性能:")
print("   - 健康类别（如苹果健康、玉米健康）性能最优（F1>0.92）；")
print("   - 严重病害类别（如柑桔黄化(严重)）召回率偏低（0.38），需优化特征提取。")
print("=" * 60)