---
id: style-preset.glass
category: style-presets
styles: [玻璃拟态]
tokens: [--ab-accent, --ab-bg, --ab-font-body, --ab-font-display, --ab-glass-alpha, --ab-glass-blur, --ab-glass-hairline, --ab-ink, --ab-margin, --ab-muted, --ab-paper, --ab-primary, --ab-radius, --ab-space-4, --ab-style-glass-blur, --ab-style-glass-edge, --ab-style-glass-saturate, --ab-style-glass-tint]
sources: [xvhuan/frostglass, mianbeishiwole/Liquid-Glass-Vue, weimo-ui-core]
status: stable
---

> 玻璃拟态的本质是 **背景有东西可透 + 一层高光边缘**,不是"白卡片 + 模糊"。
> 没有可透的背景就没有玻璃;文字永远在玻璃之上、且必须锐利。

## 目录

- [触发关键词](#触发关键词)
- [适用海报类型](#适用海报类型)
- [Design Token 清单](#design-token-清单)
- [核心 CSS 模块](#核心-css-模块)
- [字体建议](#字体建议)
- [禁忌清单](#禁忌清单)
- [参考仓库](#参考仓库)

## 触发关键词

玻璃拟态 / 玻璃 / glassmorphism / 磨砂 / 通透 / 液态玻璃 / 冰感 / 极光

## 适用海报类型

| 海报类型 | 适配度 | 说明 |
|---|---|---|
| 产品 KV / App 发布 | 高 | 渐变底 + 玻璃卡片 + 锐利标题 |
| 活动主视觉 | 中 | 需有背景图或渐变可透,纯色底失效 |
| 数据长图 | 中 | 玻璃只包住关键指标卡,正文不上玻璃 |
| 白底长文 | 低 | 无可透背景,玻璃退化为灰卡片 |

## Design Token 清单

`
:root{
  --ab-bg: #0b1020;
  --ab-paper: #101830;
  --ab-ink: #f4f2ff;
  --ab-primary: #7c9cff;
  --ab-accent: #6ef0c8;
  --ab-muted: #a9b3d0;
  --ab-glass-blur: 16px;
  --ab-glass-alpha: 0.18;
  --ab-glass-hairline: 0 0 0 1px rgba(255, 255, 255, 0.22);
  --ab-font-display: "SF Pro Display", "PingFang SC", "Helvetica Neue", sans-serif;
  --ab-font-body: "PingFang SC", "Source Han Sans SC", sans-serif;
  --ab-radius: 10px;
  --ab-margin: 9%;
  /* 风格专有 */
  --ab-style-glass-blur: var(--ab-glass-blur, 16px);
  --ab-style-glass-saturate: 165%;
  --ab-style-glass-tint: rgba(255, 255, 255, 0.12);
  --ab-style-glass-edge: rgba(255, 255, 255, 0.38);
}
`

| token | 默认值 | 作用 |
|---|---|---|
| `--ab-style-glass-blur` | 继承 `--ab-glass-blur` | 模糊半径,>24px 显现糊感 |
| `--ab-style-glass-saturate` | 165% | 背景饱和度补偿,让透出的色不发灰 |
| `--ab-style-glass-tint` | rgba(255,255,255,.12) | 玻璃本色,深底上不超过 .2 |
| `--ab-style-glass-edge` | rgba(255,255,255,.38) | 顶部高光边缘 |

## 核心 CSS 模块

`
/* 可透背景:两段径向渐变,深蓝→青,不用紫色 */
.ab-glass-bg{
  background:
    radial-gradient(120% 80% at 18% 8%, #1b3a6b 0%, transparent 60%),
    radial-gradient(100% 70% at 84% 92%, #0f2f3f 0%, transparent 62%),
    var(--ab-bg);
}
/* 玻璃卡片:必须叠在可透背景上 */
.ab-glass-panel{
  background: var(--ab-style-glass-tint);
  backdrop-filter: blur(var(--ab-style-glass-blur)) saturate(var(--ab-style-glass-saturate));
  -webkit-backdrop-filter: blur(var(--ab-style-glass-blur)) saturate(var(--ab-style-glass-saturate));
  border-radius: var(--ab-radius);
  padding: var(--ab-space-4);
  box-shadow: var(--ab-glass-hairline), 0 18px 48px rgba(4, 8, 20, 0.42);
  position: relative;
  overflow: hidden;
}
/* 顶部高光:一条 1px 渐隐线,模拟折射 */
.ab-glass-panel::before{
  content: "";
  position: absolute; inset-inline: 0; inset-block-start: 0;
  block-size: 1px;
  background: linear-gradient(90deg, transparent, var(--ab-style-glass-edge), transparent);
}
/* 文字层:不透明、不带模糊 */
.ab-glass-text{ color: var(--ab-ink); text-shadow: none; }
`

## 字体建议

- 标题:中等字重几何无衬线(SF Pro / PingFang SC Medium),靠字号与留白拉层级,不加发光。
- 正文:常规无衬线,颜色 `--ab-ink` 90% 不透明以上;玻璃上不要用灰字。
- 数字:等宽或半等宽,数值用 `--ab-accent` 一点强调。
- 禁忌:玻璃上不要放细字重小字(对比度不足,导出必糊)。

## 禁忌清单

- 不要给文字加 `backdrop-filter` 或模糊;模糊只属于背景/装饰层。
- 不叠三层以上玻璃:两层是层次,三层是灰雾。
- 不用紫色/蓝紫渐变当极光底(默认 AI 味),用深蓝 + 青或深蓝 + 暖橙。
- 玻璃卡片内边距不小于 `--ab-space-4`,否则边缘高光压字。
- 白底上禁用玻璃:没有可透背景时应改极简。
- 降级兜底:不支持 `backdrop-filter` 时,`--ab-glass-alpha` 提到 0.32 保证可读。

## 参考仓库

| 仓库 | 取什么 | 不取什么 |
|---|---|---|
| `xvhuan/frostglass` | blur 与 saturate 的组合数值、hairline 高光 | React 组件 |
| `mianbeishiwole/Liquid-Glass-Vue` | 层次深度与光泽折射的叠放顺序 | Vue 依赖 |
| `weimo-ui-core` | 磨砂材质随背景明暗自适应 token 的思路 | 未找到 GitHub 主仓,仅作思路参考 |

> 只记录来源,不建立运行时依赖;数值已重写为 `--ab-*` token。
