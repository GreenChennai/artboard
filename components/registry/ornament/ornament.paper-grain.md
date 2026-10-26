---
id: ornament.paper-grain
category: ornament
styles: [新中式, 极简]
tokens: [--ab-ink, --ab-paper]
sources: []
status: stable
---

## 结构

```html
<div class="ab-paper">
  <div class="ab-paper__grain" aria-hidden="true"></div>
  <div class="ab-paper__content">内容层</div>
</div>
```

## 核心 CSS

```css
.ab-paper{
  position: relative;
  isolation: isolate;
  background: var(--ab-paper, #fbf8f1);
  color: var(--ab-ink, #1b1a17);
}
.ab-paper__grain{
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.6;
  background-image:
    repeating-linear-gradient(92deg, rgba(27, 26, 23, 0.035) 0 1px, transparent 1px 3px),
    repeating-linear-gradient(2deg, rgba(27, 26, 23, 0.028) 0 1px, transparent 1px 4px),
    radial-gradient(circle at 18% 22%, rgba(176, 141, 87, 0.10) 0 18%, transparent 42%),
    radial-gradient(circle at 82% 78%, rgba(27, 26, 23, 0.06) 0 14%, transparent 38%);
  mix-blend-mode: multiply;
}
.ab-paper__content{ position: relative; z-index: 1; }
```

> 需要真正的纤维噪点时,可另加 `background-image:url("data:image/svg+xml,...feTurbulence...")`,
> 但 data URI 必须内联且 ≤2KB;默认用纯渐变,保证单文件零外链。

## Token 依赖

- `--ab-paper`:纸底色(米白/宣纸,不要纯白)
- `--ab-ink`:墨色,用于纹理对比
- `--ab-xuan` / `--ab-gold`:可选暖色斑

## 禁忌

- 纹理不透明度总和 ≤0.12;超过就成了脏纸,不是纸感。
- 纹理层禁止 `z-index` 大于内容层。
- 不加 `background-attachment:fixed`(固定画布下会产生视差错觉)。
- 印刷品类慎用大面积纹理:CMYK 叠印会发灰,交付前看样。
