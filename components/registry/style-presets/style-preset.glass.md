---
id: style-preset.glass
category: style-presets
styles: [玻璃拟态]
tokens: [--ab-accent, --ab-bg, --ab-glass-alpha, --ab-glass-blur, --ab-glass-hairline, --ab-ink, --ab-muted, --ab-paper, --ab-primary, --ab-radius]
sources: [xvhuan/frostglass, mianbeishiwole/Liquid-Glass-Vue]
status: stable
---

## 结构

```css
:root{
  --ab-bg: #0b1020;
  --ab-paper: #101830;
  --ab-ink: #f4f2ff;
  --ab-primary: #7c9cff;
  --ab-accent: #6ef0c8;
  --ab-muted: #a8a6c8;
  --ab-glass-blur: 18px;
  --ab-glass-alpha: 0.15;
  --ab-glass-hairline: rgba(255, 255, 255, 0.26);
  --ab-radius: 10px;
}
```

## 核心 CSS(落地规则)

```css
.ab-preset-glass{
  background:
    radial-gradient(120% 90% at 15% 10%, #1b2a5c 0%, transparent 55%),
    radial-gradient(90% 80% at 85% 88%, #34184d 0%, transparent 58%),
    var(--ab-bg);
  color: var(--ab-ink);
}
.ab-preset-glass .ab-kicker{
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: color-mix(in srgb, var(--ab-ink) 62%, transparent);
}
```

## Token 依赖

- `--ab-bg` + 两个 `radial-gradient`:玻璃必须有"后面的东西",底色不能是纯色
- `--ab-glass-blur` 12–22px:`<10px` 看不出玻璃,`>28px` 背景信息丢失
- `--ab-glass-alpha` 0.12–0.2;卡片层叠加后总不透明度要保证文字对比
- `--ab-radius` 8–12px:玻璃语言的圆角天生比极简软

## 禁忌

- 玻璃卡 ≤2 块/屏;第三块改实底,否则整张图像蒙了雾。
- 不在玻璃卡上再叠纹理或印章(材质冲突)。
- 不支持 `backdrop-filter` 的环境降级为实底,而不是半透明裸奔。
- 文字对比度必须单独验,不能靠"看着还行"。
