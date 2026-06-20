# 智农 Design System

> **Baseline** 保下限 · **Impeccable** 精细规范 · **Taste** 设计质感

---

## tokens

```yaml
colors:
  canvas: "#f7f6f3"
  surface: "#ffffff"
  surface-muted: "#f5f4f0"
  ink: "#1c1917"
  ink-muted: "#57534e"
  ink-subtle: "#78716c"
  border: "#e7e5e4"
  border-strong: "#d6d3d1"
  brand-green: "#15803d"
  brand-green-soft: "#ecfdf3"
  brand-blue: "#2563eb"
  brand-blue-soft: "#eff6ff"
  brand-orange: "#c2410c"
  brand-red: "#b91c1c"
  focus-ring: "rgba(37, 99, 235, 0.35)"

typography:
  display: '"Plus Jakarta Sans", "Noto Sans SC", sans-serif'
  body: '"Plus Jakarta Sans", "Noto Sans SC", sans-serif'
  scale:
    xs: 12px
    sm: 13px
    base: 15px
    lg: 18px
    xl: 22px
    hero: clamp(28px, 3vw, 36px)
  line-height:
    tight: 1.25
    normal: 1.55
    relaxed: 1.75

spacing: [4, 8, 12, 16, 20, 24, 32, 40, 48]
radius:
  sm: 8px
  md: 12px
  lg: 16px
  pill: 999px

elevation:
  none: "none"
  sm: "0 1px 2px rgba(28, 25, 23, 0.04)"
  md: "0 4px 14px rgba(28, 25, 23, 0.06)"
  lift: "0 8px 24px rgba(28, 25, 23, 0.08)"

motion:
  fast: 120ms
  base: 200ms
  slow: 320ms
  easing: "cubic-bezier(0.22, 1, 0.36, 1)"
```

---

## 1. Baseline（保下限）

功能与可访问性底线，任何改版不得破坏。

- 对比度：正文 `#1c1917` on `#ffffff` ≥ 4.5:1
- 触控目标：按钮/链接最小高度 **40px**
- 焦点：`focus-visible` 2px 蓝色描边，禁止移除 outline 而不替代
- 间距：仅使用 4px 倍数（4/8/12/16/24/32）
- 状态：hover / active / disabled / loading 必须可辨
- 响应式：`992px` 侧边栏堆叠，`576px` 单列卡片
- 图表：禁用 ECharts 内置空白 tooltip，使用 `#trend_chart_tip`
- 弹窗：有缓存数据时立即渲染，禁止长期「加载中」

## 2. Impeccable（精细规范）

跨页面一致的组件与排版纪律。

| 域 | 规则 |
|----|------|
| Typography | 标题 -0.02em tracking；正文 15px / 1.55；最多 3 级字重（400/600/700） |
| Color | 一主色（绿=农业）+ 一辅色（蓝=数据）；禁止紫罗兰渐变装饰 |
| Spatial | 卡片内边距 20–24px；区块间距 18–24px；网格 gap 16–18px |
| Interaction | 过渡 120–200ms；`:active` 轻微下沉 ≤2px |
| Responsive | 表格/网格在小屏折行，禁止横向溢出 |
| UX Writing | 短句、动词开头；禁止「赋能」「一站式」「99.99%」等 AI 套话 |

**反模式（禁止）**

- 紫色霓虹描边 / `#7c3aed` 装饰渐变
- 卡片套卡片超过 2 层
- `backdrop-filter` 大面积毛玻璃
- 纯黑 `#000` 文字
- 无 formatter 的 ECharts 原始时间戳

## 3. Taste（设计质感）

智农专属气质：**温暖田野 × 专业 SaaS**。

- **画布**：暖灰 `#f7f6f3`，非冷灰 `#f3f4f6`
- **品牌**：徽章绿 `#15803d` + 数据蓝 `#2563eb`，渐变仅用于 logo 小面积
- **深度**：hairline 边框 + 单层 soft shadow，不用多层堆叠阴影
- **动效**：入场 stagger 可选；尊重 `prefers-reduced-motion`
- **图标**：导航用 CSS 圆点/色块，正文区可保留少量 emoji 作提示
- **记忆点**：Overview 卡片左侧色条 + 圆角图标，演示样例卡片左侧 severity 色带

---

## 组件速查

```
dashboard-shell
├── admin-sidebar（260px）
└── admin-main
    ├── topbar-panel
    ├── steps-guide
    ├── panel-group / analytics-grid
    └── content-panel
```

| 组件 | 类名 |
|------|------|
| 主按钮 | `.btn.btn-primary` |
| 卡片 | `.content-panel`, `.card-panel` |
| 可点击卡片 | `.card-3d`（轻 elevation，非厚重 3D） |
| 步骤 | `.steps-guide` > `.step-card` |
| 图表提示 | `#trend_chart_tip.trend-chart-tip` |

---

## 文件

- 样式唯一源：`static/css/main.css`
- 主控制台：`templates/index.html`
- 子页壳：`templates/base.html`
- Cursor 规则：`.cursor/rules/ui-design.mdc`
- Skill：`.cursor/skills/zhinong-ui/SKILL.md`
