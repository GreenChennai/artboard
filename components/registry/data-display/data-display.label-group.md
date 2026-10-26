---
id: data-display.label-group
category: data-display
styles: [极简, 新中式]
tokens: [--ab-ink, --ab-muted, --ab-stroke]
sources: [nolly-studio/cult-ui]
status: stable
---

## 结构

```html
<dl class="ab-labels">
  <div class="ab-labels__row"><dt>展期</dt><dd>2026.10.24 — 11.09</dd></div>
  <div class="ab-labels__row"><dt>地点</dt><dd>上海 · 西岸艺术中心 B 馆</dd></div>
  <div class="ab-labels__row"><dt>票价</dt><dd>早鸟 ¥80 / 现场 ¥120</dd></div>
</dl>
```

## 核心 CSS

```css
.ab-labels{ display: grid; gap: 0; margin: 0; }
.ab-labels__row{
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 0;
  border-bottom: var(--ab-stroke, 1px) dotted color-mix(in srgb, var(--ab-ink, #1b1a17) 30%, transparent);
}
.ab-labels__row:last-child{ border-bottom: 0; }
.ab-labels dt{
  flex: 0 0 5.5em;
  font-size: 12px;
  letter-spacing: 0.14em;
  color: var(--ab-muted, #8a8577);
}
.ab-labels dd{
  flex: 1 1 auto;
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.5;
  color: var(--ab-ink, #1b1a17);
  text-align: left;
}
```

## Token 依赖

- `--ab-stroke`:点线分隔的粗细
- `--ab-ink` / `--ab-muted`:值/键

## 禁忌

- 键(左列)不用主色、不加粗:它是坐标,不是内容。
- 单行值超 2 行说明该换 `layout.editorial-split`,不是缩字号。
- 点线分隔只用于"清单感";正式合同/票据类改用实线或表格。
