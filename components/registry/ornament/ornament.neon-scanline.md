---
id: ornament.neon-scanline
category: ornament
styles: [赛博]
tokens: [--ab-font-body, --ab-neon-accent, --ab-scanline-alpha, --ab-scanline-gap]
sources: [sebyx07/cybercore-css]
status: stable
---

## 结构

```html
<div class="ab-neon-frame">
  <div class="ab-neon-frame__scanlines" aria-hidden="true"></div>
  <div class="ab-neon-frame__content">内容层,文字永远在这里</div>
</div>
```

## 核心 CSS

```css
.ab-neon-frame{
  position: relative;
  isolation: isolate;                    /* 让混合模式不外溢 */
  padding: 28px 32px;
  border: 1px solid var(--ab-neon-accent, #2ee6a8);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--ab-neon-accent, #2ee6a8) 30%, transparent),
    inset 0 0 24px color-mix(in srgb, var(--ab-neon-accent, #2ee6a8) 12%, transparent),
    0 0 18px var(--ab-neon-accent, #2ee6a8);   /* 静态发光:无 keyframes */
  background: rgba(7, 7, 13, 0.86);
  color: #e8e6ff;
}
.ab-neon-frame__scanlines{
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background: repeating-linear-gradient(
    180deg,
    rgba(0, 0, 0, var(--ab-scanline-alpha, 0.08)) 0 1px,
    transparent 1px var(--ab-scanline-gap, 4px)
  );
  mix-blend-mode: multiply;
}
.ab-neon-frame__content{ position: relative; z-index: 1; }
.ab-neon-frame__content h2{
  margin: 0;
  font-family: var(--ab-font-body, sans-serif);
  font-size: 1.6rem;
  letter-spacing: 0.04em;
  text-shadow: 0 0 12px color-mix(in srgb, var(--ab-neon-accent, #2ee6a8) 55%, transparent);
}
```

## Token 依赖

- `--ab-neon-accent`:霓虹主色(一图一色,不要青紫同框)
- `--ab-neon-glow`:发光强度,通过 `box-shadow` 扩散值调
- `--ab-scanline-gap` / `--ab-scanline-alpha`:扫描线密度与浓度;alpha > 0.14 会读成条纹布

## 禁忌

- **扫描线不得盖在文字上**:文字必须 `z-index:1` 且不参与 multiply。
- 默认态即完整视觉,禁止用 `@keyframes` 做闪烁;要动态导出 GIF 时才额外加。
- 发光层数 ≤2(外发光 + 内高光),三层以上会糊成色块。
- 文字本身不做 blur/glitch;glitch 只能给装饰字或图形。
