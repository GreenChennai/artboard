---
id: style-preset.minimal
category: style-presets
styles: [极简]
tokens: [--ab-accent, --ab-bg, --ab-font-numeric, --ab-ink, --ab-label-tracking, --ab-margin, --ab-muted, --ab-paper, --ab-primary, --ab-radius, --ab-stroke, --ab-title-tracking]
sources: [nolly-studio/cult-ui]
status: stable
---

## 结构

```css
:root{
  --ab-bg: #ffffff;
  --ab-paper: #fafafa;
  --ab-ink: #111111;
  --ab-primary: #111111;
  --ab-accent: #1a5cff;      /* 极简允许一个冷色,用于链接/编号 */
  --ab-muted: #767676;
  --ab-stroke: 1px;
  --ab-radius: 0;            /* 直角是这套预设的态度 */
  --ab-margin: 12%;
  --ab-title-tracking: -0.01em;
  --ab-label-tracking: 0.2em;
}
```

## 核心 CSS(落地规则)

```css
.ab-preset-minimal{ background: var(--ab-bg); color: var(--ab-ink); }
.ab-preset-minimal .ab-rule{
  height: var(--ab-stroke);
  background: var(--ab-ink);
  opacity: 0.9;
}
.ab-preset-minimal .ab-index{
  font-family: var(--ab-font-numeric, Arial, sans-serif);
  font-size: 12px;
  letter-spacing: 0.18em;
  color: var(--ab-muted);
  font-variant-numeric: tabular-nums;
}
```

## Token 依赖

- `--ab-radius:0`:全部方角;一处圆角就破功
- `--ab-margin` ≥10%:留白是主体
- `--ab-label-tracking` 0.16–0.22em:小字大字距制造"档案感"
- `--ab-accent`:最多用于编号或一条线,全图 ≤1 处

## 禁忌

- 不加阴影、不加渐变、不加纹理:极简只有"字 + 线 + 空"。
- 不为了"高级"把字缩到 10px;小字也必须可读(≥11px,对比 ≥4.5:1)。
- 一屏最多两种字号层级差;第三层级用字距而不是字号区分。
- 别用浅灰小字当正文(`--ab-muted` 只给辅助信息)。
