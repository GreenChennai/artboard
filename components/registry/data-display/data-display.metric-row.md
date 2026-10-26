---
id: data-display.metric-row
category: data-display
styles: [极简, 玻璃拟态]
tokens: [--ab-font-numeric, --ab-ink, --ab-label-size, --ab-muted, --ab-stroke]
sources: []
status: stable
---

## 结构

```html
<dl class="ab-metrics">
  <div class="ab-metrics__item"><dt>起售价</dt><dd>¥ 2,980</dd></div>
  <div class="ab-metrics__item"><dt>续航</dt><dd>18 h</dd></div>
  <div class="ab-metrics__item"><dt>重量</dt><dd>1.2 kg</dd></div>
</dl>
```

## 核心 CSS

```css
.ab-metrics{
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0;
  margin: 0;
}
.ab-metrics__item{
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 20px;
  border-left: var(--ab-stroke, 1px) solid color-mix(in srgb, var(--ab-ink, #1b1a17) 18%, transparent);
}
.ab-metrics__item:first-child{ padding-left: 0; border-left: 0; }
.ab-metrics dt{ font-size: var(--ab-label-size, 13px); letter-spacing: 0.12em; color: var(--ab-muted, #8a8577); }
.ab-metrics dd{
  margin: 0;
  font-family: var(--ab-font-numeric, "Roboto Flex", Arial, sans-serif);
  font-size: 1.35rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--ab-ink, #1b1a17);
  white-space: nowrap;
}
```

## Token 依赖

- `--ab-label-size`:指标名
- `--ab-stroke`:竖分隔线
- `--ab-ink` / `--ab-muted`:数值/标签

## 禁忌

- 一行指标 ≤4 个;超了换 `data-display.stat-block` 折行。
- 数值单位不可拆行(`white-space:nowrap`),否则 `¥ 2,980` 会断成两行。
- 不把不同口径的指标并排放(如"门店数"与"复购率"混排会暗示同一量纲)。
