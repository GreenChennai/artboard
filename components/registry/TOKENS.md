# Artboard 组件 Token 契约

> 组件文件里的视觉值一律走 `--ab-*` 命名空间。组件 CSS 必须写成 `var(--ab-x, <默认值>)`,
> 这样组件被单独贴进任意 HTML 也能看,项目里覆盖 `:root` 就能换肤。
> 本文件是**默认值真相源**:新增视觉值先在这里登记,再进组件;反向不成立。

## 默认值(项目里贴一次即可)

```css
:root{
  /* 画布 */
  --ab-canvas-ratio: 3 / 4;
  --ab-margin: 8%;
  --ab-gutter: 48px;
  --ab-space-1: 8px;
  --ab-space-2: 16px;
  --ab-space-3: 24px;
  --ab-space-4: 40px;

  /* 色彩角色(语义,不含具体色相) */
  --ab-bg: #f7f4ee;
  --ab-paper: #fbf8f1;
  --ab-ink: #1b1a17;
  --ab-primary: #2f4f43;
  --ab-accent: #b3382c;
  --ab-muted: #8a8577;

  /* 文字 */
  --ab-font-display: "Source Han Serif SC", "Noto Serif CJK SC", "Songti SC", serif;
  --ab-font-body: "Source Han Sans SC", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  --ab-font-numeric: "Roboto Flex", "Helvetica Neue", Arial, sans-serif;
  --ab-font-mono: ui-monospace, "JetBrains Mono", Consolas, monospace;
  --ab-title-tracking: 0.02em;
  --ab-title-leading: 0.95;
  --ab-label-tracking: 0.18em;

  /* 形状与线条 */
  --ab-radius: 2px;
  --ab-stroke: 1px;
  --ab-stroke-pixel: 4px;
  --ab-shadow-hard: 8px 8px 0 var(--ab-ink);

  /* 玻璃拟态 */
  --ab-glass-blur: 16px;
  --ab-glass-alpha: 0.16;
  --ab-glass-hairline: rgba(255, 255, 255, 0.28);

  /* 霓虹与扫描线 */
  --ab-neon-accent: #2ee6a8;
  --ab-neon-glow: 0 0 18px;
  --ab-scanline-gap: 4px;
  --ab-scanline-alpha: 0.08;

  /* 新中式 */
  --ab-seal-ink: #a5342a;
  --ab-seal-rotate: -4deg;
  --ab-gold: #b08d57;
  --ab-xuan: #f3ece0;

  /* 数据展示 */
  --ab-stat-size: 96px;
  --ab-stat-unit-size: 0.32em;
  --ab-label-size: 13px;

  /* 状态与反馈 */
  --ab-badge-bg: var(--ab-ink);
  --ab-badge-ink: var(--ab-paper);
  --ab-warn: #c9761f;
  /* 风格预设专有(--ab-style-<name>-*:只放该风格独有的值) */
  --ab-style-cn-ink-2: #4a463f;
  --ab-style-cn-ink-3: #8a8272;
  --ab-style-cn-seal-size: 52px;
  --ab-style-cn-texture-alpha: 0.045;
  --ab-style-cyber-grid: 32px;
  --ab-style-cyber-glitch: 2px;
  --ab-style-cyber-glow-alpha: 0.55;
  --ab-style-glass-blur: var(--ab-glass-blur, 16px);
  --ab-style-glass-saturate: 165%;
  --ab-style-glass-tint: rgba(255, 255, 255, 0.12);
  --ab-style-glass-edge: rgba(255, 255, 255, 0.38);
  --ab-style-pixel-unit: 4px;
  --ab-style-pixel-paper: #e8e0c4;
  --ab-style-pixel-ink: #1c1a17;
  --ab-style-pixel-accent: #9c2b26;
  --ab-style-pixel-shadow: 6px 6px 0 #1c1a17;
  --ab-style-y2k-chrome-hi: #eaf2ff;
  --ab-style-y2k-chrome-lo: #93a9d6;
  --ab-style-y2k-stroke: 3px;
  --ab-style-y2k-fill: #ffd8e6;
  --ab-style-y2k-window: #dfe8ff;
  --ab-style-neu-surface: #e9edf3;
  --ab-style-neu-light: #ffffff;
  --ab-style-neu-dark: #c9cfd9;
  --ab-style-neu-depth: 18px;
  --ab-style-min-rule: 1px;
  --ab-style-min-title-weight: 500;
  --ab-style-min-margin: 12%;
}
```

## 分组登记表

| 组 | token | 用于 | 改动影响 |
| :--- | :--- | :--- | :--- |
| 画布 | `--ab-canvas-ratio` `--ab-margin` `--ab-gutter` | 版式组件 | 全局重排 |
| 间距 | `--ab-space-1..4` | 所有组件 | 节奏 |
| 色彩 | `--ab-bg/paper/ink/primary/accent/muted` | 所有组件 | 换肤 |
| 文字 | `--ab-font-*` `--ab-title-*` `--ab-label-tracking` | 文字组件 | 气质 |
| 形状 | `--ab-radius` `--ab-stroke` `--ab-stroke-pixel` `--ab-shadow-hard` | 卡片/边框 | 硬/软 |
| 玻璃 | `--ab-glass-blur/alpha/hairline` | ornament.glass-panel | 通透度 |
| 霓虹 | `--ab-neon-accent/glow` `--ab-scanline-*` | ornament.neon-scanline | 赛博强度 |
| 新中式 | `--ab-seal-ink/rotate` `--ab-gold` `--ab-xuan` | ornament.seal-stamp / preset | 东方感 |
| 数据 | `--ab-stat-size/unit-size` `--ab-label-size` | data-display.* | 数据层级 |
| 反馈 | `--ab-badge-bg/ink` `--ab-warn` | feedback.* | 语义强度 |
| 风格预设 | `--ab-style-cn-*` `--ab-style-cyber-*` `--ab-style-glass-*` `--ab-style-pixel-*` `--ab-style-y2k-*` `--ab-style-neu-*` `--ab-style-min-*` | style-presets/* | 只影响该风格;基础角色仍走 `--ab-*` |

## 四条硬规则

1. **先登记后使用**:组件里出现未在默认值块登记过的 `--ab-*` = 索引与实现不一致,CI 视为缺陷。
2. **fallback 必须等于默认值**:`var(--ab-gutter, 48px)` 的兜底值要和本文件一致,否则单独贴用时走形。
3. **组件不写死字体族与色相**:需要新色相就新增语义 token,不要在组件属性里直接写 hex。
4. **对比度**:正文 ≥ 4.5:1,大字号(≥24px 或 ≥18.66px 粗体)≥ 3:1;玻璃/霓虹只能作用在背景与装饰层,文字层保持清晰渲染路径。
