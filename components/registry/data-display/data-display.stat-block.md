---
id: data-display.stat-block
category: data-display
styles: [极简, 赛博, 玻璃拟态]
tokens: [--ab-font-numeric, --ab-ink, --ab-label-size, --ab-muted, --ab-stat-size, --ab-stroke]
sources: []
status: stable
---

## 结构

```html
<div class="ab-stats">
  <div class="ab-stat">
    <span class="ab-stat__value">128<span class="ab-stat__unit">家</span></span>
    <span class="ab-stat__label">合作门店</span>
    <span class="ab-stat__src">来源:2026 年报</span>
  </div>
  <div class="ab-stat">
    <span class="ab-stat__value">4.9<span class="ab-stat__unit">/5</span></span>
    <span class="ab-stat__label">平均评分</span>
  </div>
</div>
```

## 核心 CSS

```css
.ab-stats{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0;
  border-top: var(--ab-stroke, 1px) solid color-mix(in srgb, var(--ab-ink, #1b1a17) 20%, transparent);
}
.ab-stat{
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 22px 24px 20px;
  border-right: var(--ab-stroke, 1px) solid color-mix(in srgb, var(--ab-ink, #1b1a17) 12%, transparent);
}
.ab-stat:last-child{ border-right: 0; }
.ab-stat__value{
  font-family: var(--ab-font-numeric, "Roboto Flex", Arial, sans-serif);
  font-size: var(--ab-stat-size, 96px);
  font-size: clamp(2.2rem, calc(var(--ab-stat-size, 96px) * 0.42), var(--ab-stat-size, 96px));
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.02em;
  color: var(--ab-ink, #1b1a17);
  font-variant-numeric: tabular-nums;
}
.ab-stat__unit{ font-size: 0.3em; font-weight: 600; margin-left: 0.1em; color: var(--ab-muted, #8a8577); }
.ab-stat__label{ font-size: var(--ab-label-size, 13px); letter-spacing: 0.1em; color: var(--ab-ink, #1b1a17); }
.ab-stat__src{ font-size: 11px; letter-spacing: 0.02em; color: var(--ab-muted, #8a8577); }
```

## Token 依赖

- `--ab-stat-size`:主数字上限(用 clamp 做响应式缩放)
- `--ab-label-size`:指标名
- `--ab-stroke`:分隔线粗细
- `--ab-ink` / `--ab-muted`:主/次文字

## 禁忌

- 统计块的数字必须带来源或口径;来源不明的数字不得上版(铁律 4)。
- 一屏 ≤4 个统计块;四个以上说明该用图表,不是堆数字。
- 禁止给数字加渐变/发光/描边;统计块的可信度来自"干净"。
- 分隔线不得比文字粗;`--ab-stroke` 保持 1px。
