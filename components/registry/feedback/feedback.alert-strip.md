---
id: feedback.alert-strip
category: feedback
styles: [极简, 新中式]
tokens: [--ab-ink, --ab-radius, --ab-stroke, --ab-warn]
sources: []
status: stable
---

## 结构

```html
<div class="ab-alert" role="note">
  <span class="ab-alert__bar" aria-hidden="true"></span>
  <p class="ab-alert__text"><strong>改期提醒</strong>原定 10.24 场次顺延至 11.02,已购票观众可选择全额退款。</p>
</div>
```

## 核心 CSS

```css
.ab-alert{
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 12px 16px;
  border: var(--ab-stroke, 1px) solid color-mix(in srgb, var(--ab-warn, #c9761f) 45%, transparent);
  background: color-mix(in srgb, var(--ab-warn, #c9761f) 8%, transparent);
  border-radius: var(--ab-radius, 2px);
}
.ab-alert__bar{
  flex: 0 0 3px;
  align-self: stretch;
  border-radius: 2px;
  background: var(--ab-warn, #c9761f);
}
.ab-alert__text{
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ab-ink, #1b1a17);
}
.ab-alert__text strong{ font-weight: 700; letter-spacing: 0.04em; }
```

## Token 依赖

- `--ab-warn`:提示语义色(不要用红色,红是错误色)
- `--ab-stroke`:外框
- `--ab-ink`:正文

## 禁忌

- 提示条是补充信息,不是第二主标:字号 ≤ 正文,不放大。
- 一页 ≤1 条;两条以上请合并成一句人话。
- 不用它放营销话术;它存在的意义是"别让用户漏看"。
