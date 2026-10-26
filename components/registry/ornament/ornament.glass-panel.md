---
id: ornament.glass-panel
category: ornament
styles: [玻璃拟态, 赛博, 极简]
tokens: [--ab-glass-alpha, --ab-glass-blur, --ab-glass-hairline, --ab-radius]
sources: [xvhuan/frostglass]
status: stable
---

## 结构

```html
<div class="ab-glass">
  <p class="ab-glass__kicker">FEATURE 01</p>
  <h3 class="ab-glass__title">一块浮起来的卡</h3>
  <p class="ab-glass__body">正文保持不透明清晰渲染,模糊只发生在卡片背后。</p>
</div>
```

## 核心 CSS

```css
.ab-glass{
  position: relative;
  box-sizing: border-box;
  padding: 24px 26px;
  border-radius: var(--ab-radius, 2px);
  border: 1px solid var(--ab-glass-hairline, rgba(255, 255, 255, 0.28));
  background: linear-gradient(
    145deg,
    rgba(255, 255, 255, calc(var(--ab-glass-alpha, 0.16) + 0.10)) 0%,
    rgba(255, 255, 255, var(--ab-glass-alpha, 0.16)) 55%,
    rgba(255, 255, 255, calc(var(--ab-glass-alpha, 0.16) - 0.06)) 100%
  );
  -webkit-backdrop-filter: blur(var(--ab-glass-blur, 16px)) saturate(140%);
  backdrop-filter: blur(var(--ab-glass-blur, 16px)) saturate(140%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.35),   /* 顶部高光边 = 玻璃厚度 */
    0 18px 48px rgba(0, 0, 0, 0.28);
  color: #f4f2ff;
}
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))){
  .ab-glass{ background: rgba(18, 18, 30, 0.92); }   /* 降级成实底,不降对比度 */
}
.ab-glass__kicker{ margin: 0 0 8px; font-size: 11px; letter-spacing: 0.18em; color: rgba(244, 242, 255, 0.62); }
.ab-glass__title{ margin: 0 0 10px; font-size: 1.2rem; font-weight: 600; }
.ab-glass__body{ margin: 0; font-size: 0.95rem; line-height: 1.7; color: rgba(244, 242, 255, 0.78); }
```

## Token 依赖

- `--ab-glass-blur`:模糊半径,10–20px 像玻璃;>28px 背景糊成一片,失去"后面有东西"的信息
- `--ab-glass-alpha`:透明度,0.12–0.2 之间;>0.32 读成实色卡
- `--ab-glass-hairline`:1px 高光边
- `--ab-radius`:圆角,玻璃卡允许 6–12px(与极简语言的 2px 不同)

## 禁忌

- 玻璃必须**有东西可透**:下方要有渐变/图形/照片,压在纯色上等于白做。
- 文字层不加模糊;卡片内文字对比度仍需 ≥4.5:1(深底上用 ≥0.75 白)。
- 同屏最多 2 块玻璃卡;第三块起改实底。
- 不叠加 `filter: blur()` 到整卡(会连文字一起糊)。
