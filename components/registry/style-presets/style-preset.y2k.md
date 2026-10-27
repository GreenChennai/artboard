---
id: style-preset.y2k
category: style-presets
styles: [Y2K]
tokens: [--ab-accent, --ab-bg, --ab-font-body, --ab-font-display, --ab-ink, --ab-margin, --ab-muted, --ab-paper, --ab-primary, --ab-radius, --ab-space-3, --ab-style-y2k-chrome-hi, --ab-style-y2k-chrome-lo, --ab-style-y2k-fill, --ab-style-y2k-stroke, --ab-style-y2k-window]
sources: [cjlaserna/y2k-ui-lib, facebook/astryx]
status: stable
---

> Y2K 的配方是 **海军蓝粗描边 + 粉彩填充 + 蓝银镀铬渐变**,
> 再加一层"窗口/任务栏"式的旧界面结构。关键是零模糊:所有边缘干净利落。

## 目录

- [触发关键词](#触发关键词)
- [适用海报类型](#适用海报类型)
- [Design Token 清单](#design-token-清单)
- [核心 CSS 模块](#核心-css-模块)
- [字体建议](#字体建议)
- [禁忌清单](#禁忌清单)
- [参考仓库](#参考仓库)

## 触发关键词

Y2K / 千禧 / 2000s / kawaii / 镀铬 / chrome / 复古未来 / 任务栏 / 弹窗

## 适用海报类型

| 海报类型 | 适配度 | 说明 |
|---|---|---|
| 派对 / 音乐活动 | 高 | 粗描边 + 粉彩 + 镀铬标题 |
| 品牌联名 / 潮牌 | 高 | 用窗口结构做版式骨架 |
| 产品 KV | 中 | 只保留描边与镀铬字,去掉过多装饰 |
| 商务 / 严肃长图 | 低 | 语言冲突,换极简或新中式 |

## Design Token 清单

`
:root{
  --ab-bg: #eef2fb;
  --ab-paper: #ffffff;
  --ab-ink: #101a3a;
  --ab-primary: #2b3f7a;
  --ab-accent: #ff2e93;
  --ab-muted: #5c6684;
  --ab-font-display: "Arial Black", "Helvetica Neue", "PingFang SC", sans-serif;
  --ab-font-body: "PingFang SC", "Helvetica Neue", sans-serif;
  --ab-radius: 6px;
  --ab-margin: 8%;
  /* 风格专有 */
  --ab-style-y2k-chrome-hi: #eaf2ff;
  --ab-style-y2k-chrome-lo: #93a9d6;
  --ab-style-y2k-stroke: 3px;
  --ab-style-y2k-fill: #ffd8e6;
  --ab-style-y2k-window: #dfe8ff;
}
`

| token | 默认值 | 作用 |
|---|---|---|
| `--ab-style-y2k-stroke` | 3px | 海军蓝描边唯一宽度,不许半透明 |
| `--ab-style-y2k-fill` | #ffd8e6 | 粉彩填充,大色块用 |
| `--ab-style-y2k-chrome-hi/lo` | #eaf2ff / #93a9d6 | 镀铬渐变的亮/暗端 |
| `--ab-style-y2k-window` | #dfe8ff | 窗口标题栏底色 |

## 核心 CSS 模块

`
/* 镀铬标题:蓝银金属渐变裁字,不是蓝紫 */
.ab-y2k-chrome{
  background: linear-gradient(180deg,
    var(--ab-style-y2k-chrome-hi) 0%,
    var(--ab-style-y2k-chrome-lo) 46%,
    #ffffff 52%,
    var(--ab-style-y2k-chrome-lo) 58%,
    var(--ab-style-y2k-chrome-hi) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-stroke: 1px var(--ab-ink);
  font-family: var(--ab-font-display);
  letter-spacing: -0.01em;
}
/* 粗描边卡片:零模糊,描边不透明 */
.ab-y2k-card{
  background: var(--ab-style-y2k-fill);
  border: var(--ab-style-y2k-stroke) solid var(--ab-ink);
  border-radius: var(--ab-radius);
  box-shadow: none;
}
/* 旧界面窗口:标题栏 + 内容区 */
.ab-y2k-window{
  border: var(--ab-style-y2k-stroke) solid var(--ab-ink);
  border-radius: var(--ab-radius);
  overflow: hidden;
  background: var(--ab-paper);
}
.ab-y2k-window::before{
  content: "My Poster 2000";
  display: block;
  padding: calc(var(--ab-style-y2k-stroke) * 2) var(--ab-space-3);
  background: linear-gradient(180deg, var(--ab-style-y2k-window), var(--ab-style-y2k-chrome-lo));
  border-block-end: var(--ab-style-y2k-stroke) solid var(--ab-ink);
  font-family: var(--ab-font-body);
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--ab-ink);
}
`

## 字体建议

- 标题:超粗无衬线(Arial Black / 思源黑体 Black),可镀铬;中文镀铬要加 `-webkit-text-stroke` 否则边缘糊。
- 正文:常规黑体,PingFang SC 15–16px,行高 1.55。
- 强调:全大写 + `0.12em` 字距,或用粉彩胶囊;标签固定 12px。
- 数字:等宽或 Arial Black,与标题同族。

## 禁忌清单

- 不用蓝→青的"信任渐变"做底(默认 AI 味,也过不了机检)。
- 不用全息彩虹渐变铺满;Y2K 的彩是**局部**镀铬,不是整张彩虹。
- 不加柔和投影与模糊:这一风格靠硬边和描边建立物理感。
- 描边不用半透明色;半透明描边会直接掉档成廉价霓虹。
- 窗口/任务栏元素最多 2 个,多了变界面截图而非海报。
- 中文正文不用镀铬特效,只给标题。

## 参考仓库

| 仓库 | 取什么 | 不取什么 |
|---|---|---|
| `cjlaserna/y2k-ui-lib` | 扁平窗口、粗海军蓝描边、粉彩填充配方 | 组件运行时 |
| `facebook/astryx` | 多主题 token 的组织方式(Y2K 为其主题之一) | 主题切换机制 |
| `uiverse-io/galaxy` | 缺元素时按关键词淘单个 CSS 效果 | 整包依赖 |

> 只记录来源,不建立运行时依赖;数值已重写为 `--ab-*` token。
