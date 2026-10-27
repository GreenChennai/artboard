---
id: style-preset.minimal
category: style-presets
styles: [极简]
tokens: [--ab-accent, --ab-bg, --ab-font-body, --ab-font-display, --ab-gutter, --ab-ink, --ab-margin, --ab-muted, --ab-paper, --ab-primary, --ab-radius, --ab-space-4, --ab-style-min-margin, --ab-style-min-rule, --ab-style-min-title-weight]
sources: [JassinAlSafe/NothingCN, knadh/oat, nolly-studio/cult-ui]
status: stable
---

> 极简不是全空白,而是 **一个强观点 + 极少的元素 + 精确的对齐**。
> 留白必须有边界(网格),否则就是"没做完",不是极简。

## 目录

- [触发关键词](#触发关键词)
- [适用海报类型](#适用海报类型)
- [Design Token 清单](#design-token-清单)
- [核心 CSS 模块](#核心-css-模块)
- [字体建议](#字体建议)
- [禁忌清单](#禁忌清单)
- [参考仓库](#参考仓库)

## 触发关键词

极简 / 性冷淡 / 减法 / 黑白 / 编辑部 / swiss / 数据叙事 / 高级感 / 克制

## 适用海报类型

| 海报类型 | 适配度 | 说明 |
|---|---|---|
| 数据长图 / 报告 | 高 | 网格 + 数字层级,信息密度可控 |
| 产品 KV | 高 | 单一视觉焦点 + 大留白 |
| 活动海报 | 中 | 需极强标题或单一图像支撑 |
| 节庆 / 促销 | 低 | 缺少情绪装饰,转化不占优 |

## Design Token 清单

`
:root{
  --ab-bg: #ffffff;
  --ab-paper: #fafafa;
  --ab-ink: #111111;
  --ab-primary: #333333;
  --ab-accent: #1a5cff;
  --ab-muted: #767676;
  --ab-font-display: "Helvetica Neue", "PingFang SC", "Source Han Sans SC", sans-serif;
  --ab-font-body: "PingFang SC", "Source Han Sans SC", sans-serif;
  --ab-radius: 0;
  --ab-margin: 12%;
  /* 风格专有 */
  --ab-style-min-rule: 1px;
  --ab-style-min-title-weight: 500;
  --ab-style-min-margin: 12%;
}
`

| token | 默认值 | 作用 |
|---|---|---|
| `--ab-style-min-rule` | 1px | 唯一线宽,分隔线/边框共用 |
| `--ab-style-min-title-weight` | 500 | 标题字重上限,靠字号不靠粗细 |
| `--ab-style-min-margin` | 12% | 安全边距,小于 10% 立刻显挤 |

## 核心 CSS 模块

`
/* 12 栏网格:极简的留白必须有骨架 */
.ab-min-grid{
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: var(--ab-gutter);
  padding: var(--ab-style-min-margin);
}
/* 发丝分隔线:不用卡片阴影 */
.ab-min-rule{
  border: 0;
  border-block-start: var(--ab-style-min-rule) solid color-mix(in srgb, var(--ab-ink) 18%, transparent);
  margin-block: var(--ab-space-4);
}
/* 标题:大字号 + 中等字重 + 紧行高,只用一处强调色 */
.ab-min-title{
  font-family: var(--ab-font-display);
  font-size: clamp(2.6rem, 6vw, 5rem);
  font-weight: var(--ab-style-min-title-weight);
  line-height: 1.04;
  letter-spacing: -0.01em;
  color: var(--ab-ink);
  max-inline-size: 18ch;
}
/* 强调:一条短横线或一个词,不用色块 */
.ab-min-accent{
  color: var(--ab-accent);
  text-decoration: underline;
  text-decoration-thickness: var(--ab-style-min-rule);
  text-underline-offset: 0.18em;
}
`

## 字体建议

- 标题:Helvetica Neue / 思源黑体 Medium,字距 `-0.01em`,行高 1.04;中文标题行高不低于 1.2(过紧会挤)。
- 正文:思源黑体 / PingFang SC Regular 16–17px,行高 1.65,颜色 `--ab-muted`。
- 数字:等宽或半等宽,单一大数字做视觉锚点。
- 禁忌:不用装饰字体,不用超过 2 种字体。

## 禁忌清单

- 不做"全空白 + 小字"的伪极简:至少要有 1 个清晰视觉锚点。
- 强调色只出现 1–2 处;超过 3 处就变成彩色海报。
- 不用卡片阴影、渐变、圆角图标;层级靠字号、字重、留白。
- 不使用居中对称排版(除非单行标题);左对齐 + 网格是骨架。
- 中文标题不加负字距(与 P1 机检冲突,也会挤字)。
- 留白不等于无边距:内容必须落在网格内。

## 参考仓库

| 仓库 | 取什么 | 不取什么 |
|---|---|---|
| `JassinAlSafe/NothingCN` | 复制即用的减法组件尺度、克制间距 | Next.js 依赖 |
| `knadh/oat` | 零依赖语义化 HTML/CSS 的耐久结构 | 主题系统 |
| `nolly-studio/cult-ui` | "干净但有个性"的克制样式配方 | 组件运行时 |

> 只记录来源,不建立运行时依赖;数值已重写为 `--ab-*` token。
