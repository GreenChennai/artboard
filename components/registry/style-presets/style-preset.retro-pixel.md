---
id: style-preset.retro-pixel
category: style-presets
styles: [复古像素]
tokens: [--ab-accent, --ab-bg, --ab-font-body, --ab-font-display, --ab-ink, --ab-margin, --ab-muted, --ab-paper, --ab-primary, --ab-radius, --ab-stroke, --ab-style-pixel-accent, --ab-style-pixel-ink, --ab-style-pixel-paper, --ab-style-pixel-shadow, --ab-style-pixel-unit]
sources: [lumpenspace/puxel, keinan21/gameboy-css-framework, joangeldelarosa/pxlkit]
status: stable
---

> 像素不是给图片加滤镜,而是 **网格约束 + 受限色板 + 硬边阴影**。
> 三件事做对,像素感自然出现;做错一件,就是低分辨率糊图。

## 目录

- [触发关键词](#触发关键词)
- [适用海报类型](#适用海报类型)
- [Design Token 清单](#design-token-清单)
- [核心 CSS 模块](#核心-css-模块)
- [字体建议](#字体建议)
- [禁忌清单](#禁忌清单)
- [参考仓库](#参考仓库)

## 触发关键词

复古像素 / 像素风 / 8-bit / 16-bit / 街机 / Game Boy / retro / 硬阴影 / brutalist

## 适用海报类型

| 海报类型 | 适配度 | 说明 |
|---|---|---|
| 活动 / 音乐节 | 高 | 大标题 + 像素边框 + 4 色板即可成立 |
| 产品 KV | 中 | 只让边框与角标像素化,主体图保持清晰 |
| 数据长图 | 低 | 像素字体做正文可读性不足,正文用黑体 |
| 公众号头图 / 名片 | 高 | 小尺寸下像素网格反而更整 |

## Design Token 清单

`
:root{
  --ab-bg: #e8e0c4;
  --ab-paper: #f2ecd8;
  --ab-ink: #1c1a17;
  --ab-primary: #4a4238;
  --ab-accent: #9c2b26;
  --ab-muted: #6f6656;
  --ab-font-display: "PingFang SC", "Source Han Sans SC", sans-serif;
  --ab-font-body: "PingFang SC", "Source Han Sans SC", sans-serif;
  --ab-radius: 0;
  --ab-stroke: 2px;
  --ab-margin: 9%;
  /* 风格专有 */
  --ab-style-pixel-unit: 4px;
  --ab-style-pixel-paper: #e8e0c4;
  --ab-style-pixel-ink: #1c1a17;
  --ab-style-pixel-accent: #9c2b26;
  --ab-style-pixel-shadow: 6px 6px 0 #1c1a17;
}
`

| token | 默认值 | 作用 |
|---|---|---|
| `--ab-style-pixel-unit` | 4px | 间距/边框的唯一刻度,所有值取整数倍 |
| `--ab-style-pixel-shadow` | 6px 6px 0 | 唯一允许的阴影形态(硬偏移、无模糊) |
| `--ab-style-pixel-accent` | #9c2b26 | 全图 ≤2 处 |

## 核心 CSS 模块

`
/* 像素框:硬边 + 硬阴影,零圆角 */
.ab-pixel-frame{
  border: var(--ab-style-pixel-unit) solid var(--ab-style-pixel-ink);
  box-shadow: var(--ab-style-pixel-shadow);
  border-radius: 0;
  background: var(--ab-paper);
}
/* 8px 棋盘格底纹:纯 CSS,不引图 */
.ab-pixel-grid{
  background-color: var(--ab-style-pixel-paper);
  background-image:
    linear-gradient(90deg, color-mix(in srgb, var(--ab-style-pixel-ink) 8%, transparent) 50%, transparent 50%),
    linear-gradient(color-mix(in srgb, var(--ab-style-pixel-ink) 8%, transparent) 50%, transparent 50%);
  background-size: calc(var(--ab-style-pixel-unit) * 2) calc(var(--ab-style-pixel-unit) * 2);
}
/* 像素标题:硬阴影做体素感,文字本身不模糊 */
.ab-pixel-title{
  font-family: var(--ab-font-display);
  font-weight: 800;
  letter-spacing: 0.02em;
  color: var(--ab-style-pixel-ink);
  text-shadow: calc(var(--ab-style-pixel-unit) / 2) calc(var(--ab-style-pixel-unit) / 2) 0 var(--ab-style-pixel-accent);
}
`

## 字体建议

- 标题:思源黑体 / PingFang SC 特粗,字距 `0.02em`,配硬阴影;英文数字可 `ui-monospace`。
- 正文:常规黑体 16px 起;绝不用像素字体做正文(小字号在 Retina 上糊)。
- 强调:等宽大写 + `2px` 下划线,不用彩色胶囊。
- 中文标题不加 `text-transform`(对中文无效),像素感交给边框与网格。

## 禁忌清单

- 不把整张图做像素化/低分辨率缩放——那是滤镜,不是风格。
- 不用圆角与连续曲线:像素网格里没有真正的圆。
- 不叠加大面积模糊或发光(与硬边语言冲突)。
- 色相不超过 4 个;Game Boy 只有 4 色,限制本身即风格。
- 不用 indigo/violet 紫当强调色(默认 AI 味)。
- 像素元素只出现在边框、角标、分隔线;正文区域保持干净。
- 阴影必须 0 模糊半径;一旦模糊就不再是像素。

## 参考仓库

| 仓库 | 取什么 | 不取什么 |
|---|---|---|
| `lumpenspace/puxel` | 硬偏移阴影与粗边框的组合节奏 | 组件 API |
| `keinan21/gameboy-css-framework` | 4 色受限色板与像素级间距 | 整套 class 体系 |
| `joangeldelarosa/pxlkit` | 图标像素对齐的一致性 | React 依赖 |

> 只记录来源,不建立运行时依赖;数值已重写为 `--ab-*` token。
