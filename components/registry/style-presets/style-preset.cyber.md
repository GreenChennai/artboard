---
id: style-preset.cyber
category: style-presets
styles: [赛博]
tokens: [--ab-accent, --ab-bg, --ab-font-body, --ab-font-display, --ab-font-mono, --ab-ink, --ab-label-tracking, --ab-margin, --ab-muted, --ab-neon-accent, --ab-neon-glow, --ab-paper, --ab-primary, --ab-radius, --ab-scanline-alpha, --ab-scanline-gap, --ab-style-cyber-glitch, --ab-style-cyber-glow-alpha, --ab-style-cyber-grid]
sources: [sebyx07/cybercore-css, magicuidesign/magicui, aceternity]
status: stable
---

> 赛博的底层逻辑是 **黑底 + 单一霓虹强调 + 一点点故障**。
> 霓虹是标点不是正文:全图彩色发光 = 廉价游戏广告;一处通电 = 高级。

## 目录

- [触发关键词](#触发关键词)
- [适用海报类型](#适用海报类型)
- [Design Token 清单](#design-token-清单)
- [核心 CSS 模块](#核心-css-模块)
- [字体建议](#字体建议)
- [禁忌清单](#禁忌清单)
- [参考仓库](#参考仓库)

## 触发关键词

赛博 / 科技 / 未来 / 霓虹 / 故障 / glitch / HUD / 终端 / 暗黑科技 / launch

## 适用海报类型

| 海报类型 | 适配度 | 说明 |
|---|---|---|
| 产品发布 KV | 高 | 黑底 + 单霓虹 + 网格即成立 |
| 活动 / 音乐节 | 高 | 故障标题 + 扫描线,静态即出氛围 |
| 数据长图 | 中 | 数值用等宽 + 霓虹强调色,避免满屏发光 |
| 白底物料 | 低 | 赛博依赖暗场,改深灰底或换风格 |

## Design Token 清单

`
:root{
  --ab-bg: #07070d;
  --ab-paper: #0d0d16;
  --ab-ink: #e8e6ff;
  --ab-primary: #6f7bff;
  --ab-accent: #ff2e88;
  --ab-muted: #8c8aa8;
  --ab-neon-accent: #2ee6a8;
  --ab-neon-glow: 0 0 18px;
  --ab-scanline-gap: 4px;
  --ab-scanline-alpha: 0.08;
  --ab-font-display: "Inter", "Helvetica Neue", Arial, sans-serif;
  --ab-font-body: "Inter", "PingFang SC", "Microsoft YaHei", sans-serif;
  --ab-font-mono: "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
  --ab-label-tracking: 0.22em;
  --ab-radius: 2px;
  --ab-margin: 8%;
  /* 风格专有 */
  --ab-style-cyber-grid: 32px;
  --ab-style-cyber-glitch: 2px;
  --ab-style-cyber-glow-alpha: 0.55;
}
`

| token | 默认值 | 作用 |
|---|---|---|
| `--ab-style-cyber-grid` | 32px | 网格线间距,4 的倍数 |
| `--ab-style-cyber-glitch` | 2px | 故障位移量,>4px 开始糊字 |
| `--ab-style-cyber-glow-alpha` | 0.55 | 光晕透明度上限 |

## 核心 CSS 模块

`
/* 科技网格:纯 CSS 双线,压在内容下层 */
.ab-cyber-grid{
  background-color: var(--ab-bg);
  background-image:
    linear-gradient(to right, color-mix(in srgb, var(--ab-primary) 14%, transparent) 1px, transparent 1px),
    linear-gradient(to bottom, color-mix(in srgb, var(--ab-primary) 14%, transparent) 1px, transparent 1px);
  background-size: var(--ab-style-cyber-grid) var(--ab-style-cyber-grid);
}
/* 霓虹边框:文字不发光,只有边缘发光 */
.ab-cyber-frame{
  border: 1px solid color-mix(in srgb, var(--ab-neon-accent) 70%, transparent);
  box-shadow: 0 0 calc(var(--ab-style-cyber-grid) / 2) color-mix(in srgb, var(--ab-neon-accent) calc(var(--ab-style-cyber-glow-alpha) * 100%), transparent);
  border-radius: var(--ab-radius);
  background: color-mix(in srgb, var(--ab-paper) 82%, transparent);
}
/* 故障标题:偏移只作用于装饰副本,主文字保持锐利 */
.ab-cyber-title{ position: relative; color: var(--ab-ink); }
.ab-cyber-title::before,
.ab-cyber-title::after{
  content: attr(data-text);
  position: absolute;
  inset-inline-start: 0;
  opacity: 0.55;
  pointer-events: none;
}
.ab-cyber-title::before{ clip-path: inset(0 0 52% 0); transform: translateX(var(--ab-style-cyber-glitch)); color: var(--ab-accent); }
.ab-cyber-title::after{ clip-path: inset(48% 0 0 0); transform: translateX(calc(var(--ab-style-cyber-glitch) * -1)); color: var(--ab-neon-accent); }
/* 扫描线:覆盖层,不阻断点击 */
.ab-cyber-scanlines{ position: relative; }
.ab-cyber-scanlines::after{
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: repeating-linear-gradient(
    0deg,
    transparent 0 var(--ab-scanline-gap),
    color-mix(in srgb, #000 calc(var(--ab-scanline-alpha) * 100%), transparent) var(--ab-scanline-gap) calc(var(--ab-scanline-gap) * 2)
  );
}
`

## 字体建议

- 标题:几何无衬线(Inter / Helvetica)特粗,英文全大写 + `0.02em`;中文用思源黑体 Heavy,不加发光。
- 正文:思源黑体 Regular,16px 起,行高 1.6,颜色 `--ab-muted` 而非纯白。
- 数值/标签:等宽(JetBrains Mono),标签 `letter-spacing: var(--ab-label-tracking)`。
- 禁忌:不用像素字体做正文,不用 emoji 当图标。

## 禁忌清单

- 霓虹色不超过 2 个(一个主、一个点缀),满屏彩色 = 廉价。
- 文字本身不加 `text-shadow` 光晕;光晕只给边框与装饰层(锐利度优先)。
- 故障偏移不超过 4px,且永远只作用于 `::before/::after` 副本。
- 不用蓝紫渐变铺底(默认 AI 味);暗场靠黑 + 网格,不靠彩虹。
- 扫描线覆盖层必须 `pointer-events: none`。
- 不做持续闪烁动画;导出 GIF 时才加最小 keyframes。

## 参考仓库

| 仓库 | 取什么 | 不取什么 |
|---|---|---|
| `sebyx07/cybercore-css` | glitch / scanlines / neon-border 的类名逻辑与数值 | 整套 class 体系 |
| `magicuidesign/magicui` | Hero 光晕的静态渐变做法 | React 组件与动画库 |
| `aceternity`(ui.aceternity.com) | 网格 + 聚光灯的层叠顺序 | Framer Motion 依赖 |

> 只记录来源,不建立运行时依赖;数值已重写为 `--ab-*` token。
