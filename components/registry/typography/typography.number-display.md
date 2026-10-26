---
id: typography.number-display
category: typography
styles: [极简, 赛博, 新中式]
tokens: [--ab-font-numeric, --ab-ink, --ab-label-size, --ab-muted, --ab-space-1, --ab-stat-size, --ab-stat-unit-size]
sources: [lumpenspace/puxel]
status: stable
---

## 结构

```html
<div class="ab-num">
  <span class="ab-num__value">38<span class="ab-num__unit">%</span></span>
  <span class="ab-num__label">复购率 · 2026 Q3</span>
  <span class="ab-num__meta">来源:运营月报</span>
</div>
```

## 核心 CSS

```css
.ab-num{ display: flex; flex-direction: column; gap: var(--ab-space-1, 8px); }
.ab-num__value{
  font-family: var(--ab-font-numeric, "Roboto Flex", "Helvetica Neue", Arial, sans-serif);
  font-size: var(--ab-stat-size, 96px);
  font-weight: 800;
  line-height: 0.92;
  letter-spacing: -0.02em;               /* 大数字收紧,视觉更稳 */
  color: var(--ab-ink, #1b1a17);
  font-variant-numeric: tabular-nums;    /* 多数字并排时不跳动 */
  font-feature-settings: "lnum" 1;
}
.ab-num__unit{
  font-size: var(--ab-stat-unit-size, 0.32em);
  font-weight: 600;
  margin-left: 0.12em;
  vertical-align: 0.62em;                /* 单位上标到数字视觉中线 */
  color: var(--ab-muted, #8a8577);
}
.ab-num__label{
  font-size: var(--ab-label-size, 13px);
  letter-spacing: 0.12em;
  color: var(--ab-ink, #1b1a17);
}
.ab-num__meta{
  font-size: 11px;
  letter-spacing: 0.04em;
  color: var(--ab-muted, #8a8577);
}
```

## Token 依赖

- `--ab-font-numeric`:数字族,必须支持 `tabular-nums`
- `--ab-stat-size`:主数字字号;一屏只允许一个"超大数字"
- `--ab-stat-unit-size`:单位相对尺寸
- `--ab-label-size`:标签字号

## 禁忌

- 数字必须真实(铁律 4):不许为了版式好看编造百分比/金额。
- 一页只允许一个视觉主数字;第二个数字降一档(0.5×)并使用同一族。
- 不使用 `text-align: justify` 排数字;不手动插空格对齐(用 `tabular-nums`)。
- 数字层禁止加模糊/发光滤镜 —— 文字必须保持清晰渲染路径。
