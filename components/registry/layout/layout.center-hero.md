---
id: layout.center-hero
category: layout
styles: [极简, 玻璃拟态, 赛博]
tokens: [--ab-font-display, --ab-font-numeric, --ab-ink, --ab-label-tracking, --ab-margin, --ab-muted, --ab-primary, --ab-space-3, --ab-space-4, --ab-stroke]
sources: []
status: stable
---

## 结构

```html
<section class="ab-hero">
  <p class="ab-hero__eyebrow">2026 产品发布</p>
  <h1 class="ab-hero__title">一句话说完<br>这页要卖什么</h1>
  <p class="ab-hero__sub">副标只补主标说不完的那半句</p>
  <dl class="ab-hero__anchors">
    <div><dt>日期</dt><dd>10.24</dd></div>
    <div><dt>地点</dt><dd>上海</dd></div>
    <div><dt>渠道</dt><dd>官网直播</dd></div>
  </dl>
</section>
```

## 核心 CSS

```css
.ab-hero{
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: var(--ab-space-3, 24px);
  min-height: 100%;
  padding: calc(var(--ab-margin, 8%) * 1.4) var(--ab-margin, 8%);
  color: var(--ab-ink, #1b1a17);
}
.ab-hero__eyebrow{
  margin: 0;
  font-size: 12px;
  letter-spacing: var(--ab-label-tracking, 0.18em);
  text-transform: uppercase;
  color: var(--ab-primary, #2f4f43);
}
.ab-hero__title{
  margin: 0;
  max-width: 18em;
  font-family: var(--ab-font-display, "Source Han Serif SC", "Songti SC", serif);
  font-size: clamp(2.2rem, 9cqw, 7rem);
  line-height: 1.06;
  text-wrap: balance;
}
.ab-hero__sub{
  margin: 0;
  max-width: 30em;
  font-size: 1rem;
  line-height: 1.8;
  color: var(--ab-muted, #8a8577);
}
.ab-hero__anchors{
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--ab-space-4, 40px);
  margin: var(--ab-space-4, 40px) 0 0;
  padding-top: var(--ab-space-3, 24px);
  border-top: var(--ab-stroke, 1px) solid color-mix(in srgb, var(--ab-ink, #1b1a17) 16%, transparent);
}
.ab-hero__anchors dt{ font-size: 11px; letter-spacing: 0.14em; color: var(--ab-muted, #8a8577); text-transform: uppercase; }
.ab-hero__anchors dd{ margin: 4px 0 0; font-family: var(--ab-font-numeric, Arial, sans-serif); font-size: 1.1rem; font-variant-numeric: tabular-nums; }
```

## Token 依赖

- `--ab-margin`:上下再乘 1.4,让居中版式的"空"真正空出来
- `--ab-space-3/4`:标题到副标、锚点到页面的节奏
- `--ab-primary`:眉标唯一强调色
- `--ab-ink` / `--ab-muted`:主/次文字

## 禁忌

- 居中版式只允许 **1 个焦点**:标题。锚点上不得再用主色块。
- `min-height:100%` 依赖父级有确定高度;没有就把画布比例交给 `layout.poster-vertical`。
- 主标两行以内最好;三行以内可接受,四行请回左对齐分栏。
- 禁止给整块加发光背景 —— 那是 `ornament.*` 的职责,不是版式的。
