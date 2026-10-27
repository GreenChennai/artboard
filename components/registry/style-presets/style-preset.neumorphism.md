---
id: style-preset.neumorphism
category: style-presets
styles: [新拟态]
tokens: [--ab-accent, --ab-bg, --ab-font-body, --ab-font-display, --ab-ink, --ab-margin, --ab-muted, --ab-paper, --ab-primary, --ab-radius, --ab-style-neu-dark, --ab-style-neu-depth, --ab-style-neu-light, --ab-style-neu-surface]
sources: [nregret/Neumorphism-UI, mrturck/neumorphic-react, AKAspanion/ui-neumorphism]
status: stable
---

> 新拟态的物理规则只有一条:**同一光源,凸起左上亮、右下暗,凹陷反之**。
> 破坏光源一致性,柔光立刻变成脏阴影;对比度不足是它最大的落地风险。

## 目录

- [触发关键词](#触发关键词)
- [适用海报类型](#适用海报类型)
- [Design Token 清单](#design-token-清单)
- [核心 CSS 模块](#核心-css-模块)
- [字体建议](#字体建议)
- [禁忌清单](#禁忌清单)
- [参考仓库](#参考仓库)

## 触发关键词

新拟态 / 拟物 / neumorphism / 柔光 / 浮雕 / 软 UI / 触摸感 / 极简质感

## 适用海报类型

| 海报类型 | 适配度 | 说明 |
|---|---|---|
| 产品 KV / 科技发布 | 高 | 柔光模块 + 深墨文字,质感即卖点 |
| 报价 / 会员权益 | 中 | 用于模块卡片,正文不上浮雕 |
| 数据长图 | 低 | 低对比度做表格必糊,改极简 |
| 白底长文 | 低 | 纯白底无法建立双光源,须用浅灰底 |

## Design Token 清单

`
:root{
  --ab-bg: #e9edf3;
  --ab-paper: #eef1f7;
  --ab-ink: #2a2f3a;
  --ab-primary: #3b4250;
  --ab-accent: #4a6fa5;
  --ab-muted: #7c8494;
  --ab-font-display: "PingFang SC", "Source Han Sans SC", sans-serif;
  --ab-font-body: "PingFang SC", "Source Han Sans SC", sans-serif;
  --ab-radius: 18px;
  --ab-margin: 9%;
  /* 风格专有 */
  --ab-style-neu-surface: #e9edf3;
  --ab-style-neu-light: #ffffff;
  --ab-style-neu-dark: #c9cfd9;
  --ab-style-neu-depth: 18px;
}
`

| token | 默认值 | 作用 |
|---|---|---|
| `--ab-style-neu-surface` | #e9edf3 | 唯一底材,凸起与凹陷都从它派生 |
| `--ab-style-neu-depth` | 18px | 阴影偏移/模糊基准,>24px 变糊 |
| `--ab-style-neu-light` | #ffffff | 光源亮面,永远在左上 |
| `--ab-style-neu-dark` | #c9cfd9 | 光源暗面,永远在右下 |

## 核心 CSS 模块

`
/* 凸起:左上亮 + 右下暗,双阴影同源 */
.ab-neu-raised{
  background: var(--ab-style-neu-surface);
  border-radius: var(--ab-radius);
  box-shadow:
    calc(var(--ab-style-neu-depth) * -1) calc(var(--ab-style-neu-depth) * -1) calc(var(--ab-style-neu-depth) * 1.4) var(--ab-style-neu-light),
    var(--ab-style-neu-depth) var(--ab-style-neu-depth) calc(var(--ab-style-neu-depth) * 1.4) var(--ab-style-neu-dark);
}
/* 凹陷:内外互换,用于输入框/进度槽 */
.ab-neu-inset{
  background: var(--ab-style-neu-surface);
  border-radius: var(--ab-radius);
  box-shadow:
    inset calc(var(--ab-style-neu-depth) * -0.8) calc(var(--ab-style-neu-depth) * -0.8) var(--ab-style-neu-depth) var(--ab-style-neu-light),
    inset calc(var(--ab-style-neu-depth) * 0.8) calc(var(--ab-style-neu-depth) * 0.8) var(--ab-style-neu-depth) var(--ab-style-neu-dark);
}
/* 文字层:不参与浮雕,只用深墨保证对比度 */
.ab-neu-text{
  color: var(--ab-ink);
  text-shadow: none;
  font-family: var(--ab-font-body);
}
`

## 字体建议

- 标题:常规黑体中粗,字距 `0.01em`;不要给标题加浮雕,柔光会吃掉笔画。
- 正文:思源黑体 / PingFang SC Regular 16px 起,颜色用 `--ab-ink`(#2a2f3a),不用灰字。
- 数字:同族半等宽,大小对比拉层级。
- 禁忌:不用细字重(100–300)做正文,浮雕底上必糊。

## 禁忌清单

- 不用纯白或纯黑做底:双光源没有中间灰就无法成立。
- 光源方向必须全局一致(左上亮/右下暗),不许局部反转。
- 阴影不加色相偏移;带蓝/紫的柔光是廉价感来源。
- 文字不加浮雕;浮雕只属于容器层。
- 深色底上禁用新拟态(会退化成霓虹描边)。
- 对比度红线:正文与底色对比不低于 4.5:1,不足就换 `--ab-ink`。
- 层级不超过两层凸起;三层以上会变成橡皮泥。

## 参考仓库

| 仓库 | 取什么 | 不取什么 |
|---|---|---|
| `nregret/Neumorphism-UI` | sm/md/lg 三层深度体系与凸起/凹陷双态 | 组件 API |
| `mrturck/neumorphic-react` | 柔和阴影的数值配方 | React 依赖 |
| `AKAspanion/ui-neumorphism` | 凹陷态的 inset 参数比例 | 项目脚手架 |

> 只记录来源,不建立运行时依赖;数值已重写为 `--ab-*` token。
