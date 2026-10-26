---
id: layout.editorial-split
category: layout
styles: [极简, 新中式, 玻璃拟态]
tokens: [--ab-font-display, --ab-gutter, --ab-ink, --ab-label-tracking, --ab-margin, --ab-muted, --ab-space-1, --ab-space-2, --ab-space-3, --ab-stroke]
sources: [nolly-studio/cult-ui]
status: stable
---

## 结构

```html
<section class="ab-split">
  <div class="ab-split__col ab-split__col--text">
    <p class="ab-split__eyebrow">FIELD NOTES / 01</p>
    <h2 class="ab-split__title">左栏放结论<br>不放大段正文</h2>
    <p class="ab-split__body">正文控制在 3–4 行,行宽 18–24 个汉字。数据与论断逐字来自用户。</p>
  </div>
  <figure class="ab-split__col ab-split__col--media">
    <img src="assets/photo.jpg" alt="说明文字" />
    <figcaption>图注:一句话,可省</figcaption>
  </figure>
</section>
```

## 核心 CSS

```css
.ab-split{
  box-sizing: border-box;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  align-items: center;
  gap: var(--ab-gutter, 48px);
  padding: var(--ab-margin, 8%);
  color: var(--ab-ink, #1b1a17);
}
.ab-split__eyebrow{
  margin: 0 0 var(--ab-space-2, 16px);
  font-size: 12px;
  letter-spacing: var(--ab-label-tracking, 0.18em);
  color: var(--ab-muted, #8a8577);
}
.ab-split__title{
  margin: 0 0 var(--ab-space-3, 24px);
  font-family: var(--ab-font-display, "Source Han Serif SC", "Songti SC", serif);
  font-size: clamp(1.9rem, 5.2cqw, 4.4rem);
  line-height: 1.12;
  letter-spacing: 0.01em;
  text-wrap: balance;
}
.ab-split__body{
  margin: 0;
  max-width: 24em;
  font-size: 1rem;
  line-height: 1.8;
  color: var(--ab-muted, #8a8577);
  border-left: var(--ab-stroke, 1px) solid currentColor;  /* 极简基线:一根线代替卡片 */
  padding-left: var(--ab-space-2, 16px);
}
.ab-split__col--media{ margin: 0; }
.ab-split__col--media img{
  display: block;
  width: 100%;
  height: auto;
  aspect-ratio: 4 / 5;
  object-fit: cover;
}
.ab-split__col--media figcaption{
  margin-top: var(--ab-space-1, 8px);
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--ab-muted, #8a8577);
}
```

## Token 依赖

- `--ab-gutter`:两栏之间的呼吸,建议 ≥ 40px;窄于 24px 会读成"两个块挤在一起"
- `--ab-margin`:画布安全区
- `--ab-stroke`:正文左侧基线(极简语言)
- `--ab-ink` / `--ab-muted`:主/次文字角色

## 禁忌

- 左栏正文超过 4 行就换 `layout.center-hero`,不要靠缩字号硬塞。
- 图片必须真实素材;禁止用渐变块冒充照片(交付触犯铁律 7 的品类)。
- 两栏不设 `overflow:hidden` 的等高卡片背景 —— 本组件靠留白分隔,不靠色块。
- 不得把 `figcaption` 当第二段正文写。
