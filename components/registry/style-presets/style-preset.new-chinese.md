---
id: style-preset.new-chinese
category: style-presets
styles: [新中式]
tokens: [--ab-accent, --ab-bg, --ab-font-body, --ab-font-display, --ab-gold, --ab-ink, --ab-margin, --ab-muted, --ab-paper, --ab-primary, --ab-radius, --ab-seal-ink, --ab-title-leading, --ab-title-tracking, --ab-xuan]
sources: [you-want/han-design, shuimo-design/shuimo-ui]
status: stable
---

## 结构

预设不产生 DOM,只产出一段 `:root` 覆盖。项目里放在所有组件 CSS 之前。

```css
:root{
  --ab-bg: #f3ece0;            /* 宣纸 */
  --ab-paper: #f9f4e9;
  --ab-ink: #1c1a17;           /* 墨,不是纯黑 */
  --ab-primary: #384a45;       /* 黛青 */
  --ab-accent: #a5342a;        /* 朱砂 */
  --ab-muted: #6f6a5f;         /* 淡墨 */
  --ab-gold: #b08d57;
  --ab-xuan: #f3ece0;
  --ab-seal-ink: #a5342a;
  --ab-font-display: "Source Han Serif SC", "Noto Serif CJK SC", "Songti SC", serif;
  --ab-font-body: "Source Han Serif SC", "Noto Serif CJK SC", "Songti SC", serif;
  --ab-title-tracking: 0.06em;  /* 衬线中文放大字距才有"碑帖"气 */
  --ab-title-leading: 1.08;
  --ab-margin: 10%;
  --ab-radius: 1px;
}
```

## 核心 CSS(落地规则,非组件)

```css
.ab-preset-new-chinese{ background: var(--ab-bg); color: var(--ab-ink); }
.ab-preset-new-chinese .ab-rule{
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--ab-ink) 18%, var(--ab-ink) 82%, transparent);
  opacity: 0.35;
}
```

## Token 依赖

- `--ab-font-display` / `--ab-font-body`:全衬线是这套预设的骨架;混黑体会掉气质
- `--ab-title-tracking` 0.04–0.08em:`>0.1em` 会散
- `--ab-margin` ≥9%:留白是这套预设的主角
- `--ab-accent`(朱砂)全图 ≤2 处,其中一处通常是印章

## 禁忌

- **一种风格一次只吸收 3–5 个核心规则**:本预设的可调项就是留白、字距、墨色层级、朱砂用量。
- 不用纯白底 `#fff` 配纯黑字 `#000`:那是"国潮"不是"新中式"。
- 不叠加大面积金色渐变;金只做细节(线/编号/小字)。
- 纹理(opacity)与朱砂不要同时抢:印章出现时,底纹降到 0.04 以下。
