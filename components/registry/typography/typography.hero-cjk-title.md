---
id: typography.hero-cjk-title
category: typography
styles: [新中式, 赛博, 极简]
tokens: [--ab-font-display, --ab-ink, --ab-title-leading, --ab-title-tracking]
sources: [you-want/han-design]
status: stable
---

## 结构

```html
<h1 class="ab-title-xl">
  <span class="ab-title-xl__line">大象无形</span>
  <span class="ab-title-xl__line ab-title-xl__line--thin">大音希声</span>
</h1>
```

## 核心 CSS

```css
.ab-title-xl{
  margin: 0;
  font-family: var(--ab-font-display, "Source Han Serif SC", "Songti SC", serif);
  font-weight: 900;
  font-size: clamp(2.6rem, 13cqw, 12rem);
  line-height: var(--ab-title-leading, 0.95);
  letter-spacing: var(--ab-title-tracking, 0.02em);
  color: var(--ab-ink, #1b1a17);
  text-wrap: balance;
  text-spacing-trim: trim-start;      /* 中文标点挤压:需 Chrome 133+/Edge 133+ */
  font-kerning: normal;
}
.ab-title-xl__line{ display: block; }
.ab-title-xl__line--thin{ font-weight: 200; }             /* 字重对比 = 层级,不靠字号 */
.ab-title-xl__line--outline{
  color: transparent;
  -webkit-text-stroke: 1.5px var(--ab-ink, #1b1a17);      /* 描边字:装饰层用途 */
}
.ab-title-xl__line--indent{ padding-left: 0.6em; }        /* 错位一行,制造节奏 */
```

## Token 依赖

- `--ab-font-display`:标题字体族(衬线/黑体由预设决定)
- `--ab-title-leading`:行高,大字用 0.9–1.0;低于 0.9 中文会顶字
- `--ab-title-tracking`:字距,衬线 0.02em,黑体 0.04em 更冷
- `--ab-ink`:文字色

## 禁忌

- **字号不是唯一层级**:同一标题里最多两档字重(900 + 200),再多就是噪音。
- 中文 `letter-spacing` > 0.08em 会把词读散 —— 只有 2–4 字的短标题才允许。
- 描边字只能用在装饰/副行;正文和小字用描边 = 不可读。
- 不在此组件设 `font-feature-settings` 全局开关,字距/行高交给 token。
