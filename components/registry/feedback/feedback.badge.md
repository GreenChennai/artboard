---
id: feedback.badge
category: feedback
styles: [极简, 赛博, 新中式]
tokens: [--ab-accent, --ab-badge-bg, --ab-badge-ink, --ab-radius]
sources: [lumpenspace/puxel]
status: stable
---

## 结构

```html
<span class="ab-badge">限时 3 天</span>
<!-- 角标:绝对定位到父级右上 -->
<div class="ab-badge-corner">NEW</div>
```

## 核心 CSS

```css
.ab-badge{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--ab-radius, 2px);
  background: var(--ab-badge-bg, #1b1a17);
  color: var(--ab-badge-ink, #fbf8f1);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  line-height: 1.4;
  white-space: nowrap;
}
.ab-badge::before{                       /* 状态点:比文字更快被读到 */
  content: "";
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--ab-accent, #b3382c);
}
.ab-badge-corner{
  position: absolute;
  top: 0;
  right: 0;
  padding: 6px 14px 6px 16px;
  background: var(--ab-accent, #b3382c);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.2em;
  clip-path: polygon(10px 0, 100% 0, 100% 100%, 0 100%);  /* 斜切角:静态,不用伪 3D */
}
```

## Token 依赖

- `--ab-badge-bg` / `--ab-badge-ink`:徽章底与字(默认反白)
- `--ab-accent`:状态点
- `--ab-radius`:硬边框语言用 2px,玻璃语言可用 999px

## 禁忌

- 全图 ≤2 个徽章;多了就变成电商牛皮癣。
- 徽章字不加描边、不加投影;角标不要旋转(会与其他元素打架)。
- 不用徽章承载价格或行动号召(CTA 是另一回事)。
