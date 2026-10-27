---
id: style-preset.new-chinese
category: style-presets
styles: [新中式]
tokens: [--ab-accent, --ab-bg, --ab-font-body, --ab-font-display, --ab-gold, --ab-ink, --ab-margin, --ab-muted, --ab-paper, --ab-primary, --ab-radius, --ab-seal-ink, --ab-seal-rotate, --ab-space-1, --ab-space-4, --ab-stroke, --ab-style-cn-ink-2, --ab-style-cn-ink-3, --ab-style-cn-seal-size, --ab-style-cn-texture-alpha, --ab-title-leading, --ab-title-tracking, --ab-xuan]
sources: [you-want/han-design, shuimo-design/shuimo-ui, zhui-team/zhui]
status: stable
---

> 新中式不是红金配色加龙凤纹样,而是 **墨色层级 + 宣纸底 + 朱砂一点 + 大留白**。
> 四个变量定生死,纹样只是可选项——先做对墨色,再谈符号。

## 目录

- [触发关键词](#触发关键词)
- [适用海报类型](#适用海报类型)
- [Design Token 清单](#design-token-清单)
- [核心 CSS 模块](#核心-css-模块)
- [字体建议](#字体建议)
- [禁忌清单](#禁忌清单)
- [参考仓库](#参考仓库)

## 触发关键词

新中式 / 东方 / 水墨 / 国风 / 宋韵 / 节气 / 茶 / 书房 / 雅致 / 禅意

## 适用海报类型

| 海报类型 | 适配度 | 说明 |
|---|---|---|
| 文化 / 节气 / 展览 | 高 | 墨色层级 + 朱砂印章即成立 |
| 品牌联名 / 礼盒 | 高 | 留白即溢价感,忌塞满 |
| 产品 KV | 中 | 只让标题与印章中式,产品图保持写实 |
| 数据长图 | 低 | 墨色层级做表格对比度不足,改用极简 |
| 名片 / 邀请函 | 高 | 小尺寸下细线与印章最稳 |

## Design Token 清单

`
:root{
  /* 基础角色 */
  --ab-bg: #f3ece0;
  --ab-paper: #f9f4e9;
  --ab-ink: #1c1a17;
  --ab-primary: #384a45;
  --ab-accent: #a5342a;
  --ab-muted: #6f6a5f;
  --ab-gold: #b08d57;
  --ab-xuan: #f3ece0;
  --ab-seal-ink: #a5342a;
  --ab-seal-rotate: -3deg;
  --ab-font-display: "Songti SC", "Source Han Serif SC", "Noto Serif SC", serif;
  --ab-font-body: "Songti SC", "Source Han Serif SC", serif;
  --ab-title-tracking: 0.06em;
  --ab-title-leading: 1.08;
  --ab-margin: 10%;
  --ab-radius: 1px;
  /* 风格专有 */
  --ab-style-cn-ink-2: #4a463f;
  --ab-style-cn-ink-3: #8a8272;
  --ab-style-cn-seal-size: 52px;
  --ab-style-cn-texture-alpha: 0.045;
}
`

| token | 默认值 | 作用 |
|---|---|---|
| `--ab-style-cn-ink-2` | #4a463f | 二级墨色:副标题、引言 |
| `--ab-style-cn-ink-3` | #8a8272 | 三级墨色:页码、注释 |
| `--ab-style-cn-seal-size` | 52px | 印章边长,全图只此一处 |
| `--ab-style-cn-texture-alpha` | 0.045 | 宣纸纤维强度,>0.06 显脏 |

## 核心 CSS 模块

`
/* 宣纸底:横向纤维,纯 CSS,不引图 */
.ab-cn-paper{
  background-color: var(--ab-xuan);
  background-image: repeating-linear-gradient(
    0deg,
    color-mix(in srgb, var(--ab-ink) calc(var(--ab-style-cn-texture-alpha) * 100%), transparent) 0 1px,
    transparent 1px 3px
  );
}
/* 朱砂印章:文字反白,只做点状强调 */
.ab-cn-seal{
  inline-size: var(--ab-style-cn-seal-size);
  block-size: var(--ab-style-cn-seal-size);
  display: grid;
  place-items: center;
  background: var(--ab-seal-ink);
  color: var(--ab-paper);
  border-radius: var(--ab-radius);
  transform: rotate(var(--ab-seal-rotate));
  font-family: var(--ab-font-display);
  letter-spacing: 0.08em;
}
/* 双线框:内细外更细,替代粗描边 */
.ab-cn-frame{
  padding: var(--ab-space-4);
  border: var(--ab-stroke) solid color-mix(in srgb, var(--ab-ink) 26%, transparent);
  outline: var(--ab-stroke) solid color-mix(in srgb, var(--ab-ink) 12%, transparent);
  outline-offset: var(--ab-space-1);
}
`

## 字体建议

- 标题:宋体族(思源宋体 / Songti SC),字距 `0.06em`,行高 `1.08`,靠 **字重与字号** 拉层级,不靠颜色。
- 正文:同上宋体,或思源黑体 Regular;中文正文不小于 16px。
- 数字/英文:衬线小号 + 全大写 + `0.12em` 字距,与中文标题形成气质差。
- 备选:书法字体只用于 2–4 字短标题,超过 4 字必换宋体(可读性)。

## 禁忌清单

- 不用纯黑 `#000` / 纯白 `#fff`:墨要有纸的暖调。
- 朱砂面积不超过全图 3%,只做印章、短线、单字强调三选一。
- 不加金色渐变描边、不加投影发光——那是喜庆模板味,不是雅致。
- 一张图最多 1 个传统符号(云纹/回纹/窗棂);两个以上立刻变庙会。
- 中文标题不加负字距,不做全大写式压缩。
- 宣纸纹理 alpha 不超过 0.06,满版纹理会让 PNG 出现脏噪点。

## 参考仓库

| 仓库 | 取什么 | 不取什么 |
|---|---|---|
| `you-want/han-design` | data-theme 多主题的墨色分层组织方式 | 组件 API 与主题切换运行时 |
| `shuimo-design/shuimo-ui` | 墨色浓淡五级映射、留白比例 | Vue 组件 |
| `zhui-team/zhui` | 克制的小元素(角标/分隔线)尺度 | 整包引入 |

> 只记录来源,不建立运行时依赖;数值已重写为 `--ab-*` token。
