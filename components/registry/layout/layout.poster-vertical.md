---
id: layout.poster-vertical
category: layout
styles: [新中式, 赛博, 玻璃拟态, 极简]
tokens: [--ab-bg, --ab-canvas-ratio, --ab-font-body, --ab-font-display, --ab-gutter, --ab-ink, --ab-label-tracking, --ab-margin, --ab-muted, --ab-space-2, --ab-space-3, --ab-stroke, --ab-title-leading, --ab-title-tracking]
sources: []
status: stable
---

## 结构

```html
<main class="ab-poster" style="--ab-canvas-ratio: 3 / 4">
  <div class="ab-poster__bleed" aria-hidden="true"></div>
  <header class="ab-poster__kicker">品牌 · 系列 · 第 07 期</header>
  <section class="ab-poster__hero">
    <h1 class="ab-poster__title">主标控制<br>在两到四行</h1>
    <p class="ab-poster__sub">一句话副标,不抢主标</p>
  </section>
  <footer class="ab-poster__foot"><span>2026 · 秋</span><span>example.com</span></footer>
</main>
```

## 核心 CSS

```css
.ab-poster{
  position: relative;
  box-sizing: border-box;
  aspect-ratio: var(--ab-canvas-ratio, 3 / 4);
  width: 100%;
  overflow: hidden;                 /* 铁律 1:固定画布,禁滚动依赖 */
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: calc(var(--ab-gutter, 48px) / 2);
  padding: var(--ab-margin, 8%);
  background: var(--ab-bg, #f7f4ee);
  color: var(--ab-ink, #1b1a17);
  font-family: var(--ab-font-body, "Source Han Sans SC", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif);
}
.ab-poster__bleed{                  /* 底纹/光效出血层:永远在文字之下 */
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
.ab-poster > *:not(.ab-poster__bleed){ position: relative; z-index: 1; }

.ab-poster__kicker{
  font-size: 13px;
  letter-spacing: var(--ab-label-tracking, 0.18em);
  text-transform: uppercase;
  color: var(--ab-muted, #8a8577);
}
.ab-poster__hero{ display: flex; flex-direction: column; justify-content: center; gap: var(--ab-space-3, 24px); }
.ab-poster__title{
  margin: 0;
  font-family: var(--ab-font-display, "Source Han Serif SC", "Songti SC", serif);
  font-size: clamp(2.5rem, 11cqw, 9rem);
  line-height: var(--ab-title-leading, 0.95);
  letter-spacing: var(--ab-title-tracking, 0.02em);
  text-wrap: balance;
}
.ab-poster__sub{ margin: 0; max-width: 26em; font-size: 1.05rem; line-height: 1.7; color: var(--ab-muted, #8a8577); }
.ab-poster__foot{
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 12px; letter-spacing: 0.08em;
  padding-top: var(--ab-space-2, 16px);
  border-top: var(--ab-stroke, 1px) solid color-mix(in srgb, var(--ab-ink, #1b1a17) 18%, transparent);
}
```

> `cqw` 需要父级 `container-type: inline-size`。项目里最外层 canvas 加一行
> `.ab-canvas{container-type:inline-size}` 即可;不支持容器查询时用 `vw` 兜底也可出图。

## Token 依赖

- `--ab-canvas-ratio`:画布比例,由 Brief 决定(海报 3:4,手机全屏 9:16)
- `--ab-margin`:安全区;**百分比内边距按宽度计算**,9:16 长图要按短边给边距时,
  用 `container-type:size` + `padding:` 改 `5cqh 8cqw`
- `--ab-gutter`:`grid` 行间距基准
- `--ab-bg` / `--ab-ink` / `--ab-muted`:底色与文字角色
- `--ab-stroke`:页脚分隔线

## 禁忌

- 不在此组件内设置全局 `body` 字体族或重置 —— 只作用于 `.ab-poster` 作用域。
- 禁用 `100vh` / `position:fixed` / 滚动依赖(铁律 1)。
- `.ab-poster__bleed` 里的装饰不得遮挡文字安全区;层级只允许 0(装饰)/1(内容)两层。
- 主标超过 4 行说明文案该删,不是把字号调小。
