---
id: feedback.tag
category: feedback
styles: [极简, 新中式, 玻璃拟态]
tokens: [--ab-ink, --ab-muted, --ab-radius, --ab-stroke]
sources: [nolly-studio/cult-ui]
status: stable
---

## 结构

```html
<ul class="ab-tags">
  <li>城市漫游</li>
  <li>胶片质感</li>
  <li>周末限定</li>
</ul>
```

## 核心 CSS

```css
.ab-tags{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.ab-tags li{
  padding: 5px 12px;
  border: var(--ab-stroke, 1px) solid color-mix(in srgb, var(--ab-muted, #8a8577) 55%, transparent);
  border-radius: var(--ab-radius, 2px);
  font-size: 12px;
  letter-spacing: 0.08em;
  line-height: 1.5;
  color: var(--ab-ink, #1b1a17);
  white-space: nowrap;
}
```

## Token 依赖

- `--ab-stroke`:描边粗细(空心胶囊,不做实底)
- `--ab-muted`:描边色基准
- `--ab-radius`:2px 硬朗 / 999px 柔和

## 禁忌

- 标签 ≤6 个,每个 ≤8 字;长句不是标签。
- 标签内容不重复主标题里的词(重复 = 噪音)。
- 不给标签加背景色块堆叠:空心描边是为了"退后一层"。
