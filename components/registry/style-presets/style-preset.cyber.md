---
id: style-preset.cyber
category: style-presets
styles: [赛博]
tokens: [--ab-accent, --ab-bg, --ab-font-mono, --ab-ink, --ab-label-tracking, --ab-muted, --ab-neon-accent, --ab-paper, --ab-primary, --ab-radius, --ab-scanline-alpha, --ab-scanline-gap]
sources: [sebyx07/cybercore-css]
status: stable
---

## 结构

```css
:root{
  --ab-bg: #07070d;
  --ab-paper: #0d0d16;
  --ab-ink: #e8e6ff;
  --ab-primary: #6f7bff;
  --ab-accent: #ff2e88;          /* 品红只做一次强调 */
  --ab-muted: #8f8db0;
  --ab-neon-accent: #2ee6a8;     /* 霓虹主色:与 accent 不同色 */
  --ab-scanline-gap: 4px;
  --ab-scanline-alpha: 0.07;
  --ab-radius: 2px;              /* 赛博要"硬",不要大圆角 */
  --ab-font-mono: ui-monospace, "JetBrains Mono", Consolas, monospace;
  --ab-label-tracking: 0.22em;
}
```

## 核心 CSS(落地规则)

```css
.ab-preset-cyber{ background: var(--ab-bg); color: var(--ab-ink); }
.ab-preset-cyber .ab-meta{
  font-family: var(--ab-font-mono);
  font-size: 11px;
  letter-spacing: var(--ab-label-tracking);
  text-transform: uppercase;
  color: var(--ab-neon-accent);
}
.ab-preset-cyber .ab-hair{                 /* 分隔:细线 + 短刻度 */
  position: relative;
  height: 1px;
  background: color-mix(in srgb, var(--ab-neon-accent) 45%, transparent);
}
.ab-preset-cyber .ab-hair::before{
  content: "";
  position: absolute; left: 0; top: -3px;
  width: 40px; height: 7px;
  background: var(--ab-neon-accent);
}
```

## Token 依赖

- `--ab-neon-accent`:霓虹主色;全图只允许一种霓虹色
- `--ab-accent`:品红/热粉,用于一次"事件"(价格、警告、关键帧)
- `--ab-scanline-*`:扫描线浓度;深底上 alpha 0.05–0.09
- `--ab-radius`:≤2px,大圆角与赛博语言冲突

## 禁忌

- 霓虹不要三色同框(青 + 紫 + 粉 = 廉价游戏 UI)。
- 发光只给 1 个元素:标题或边框,二选一。
- 深底上不要用纯白字:用 `#e8e6ff`,并保证对比 ≥4.5:1。
- 默认态静态完整;扫光/故障只作为 GIF 导出的附加 keyframes。
