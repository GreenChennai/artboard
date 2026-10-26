---
id: typography.bilingual-stack
category: typography
styles: [极简, 玻璃拟态, 赛博]
tokens: [--ab-font-body, --ab-font-display, --ab-ink, --ab-label-tracking, --ab-muted, --ab-space-2]
sources: [nolly-studio/cult-ui]
status: stable
---

## 结构

```html
<div class="ab-bi">
  <p class="ab-bi__kicker">MOTION &amp; LIGHT</p>
  <h2 class="ab-bi__cn">光在动</h2>
  <p class="ab-bi__en">A study of movement, stillness and the space between</p>
</div>
```

## 核心 CSS

```css
.ab-bi{ display: flex; flex-direction: column; gap: var(--ab-space-2, 16px); }
.ab-bi__kicker{
  margin: 0;
  font-family: var(--ab-font-body, sans-serif);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: var(--ab-label-tracking, 0.18em);
  text-transform: uppercase;
  color: var(--ab-muted, #8a8577);
}
.ab-bi__cn{
  margin: 0;
  font-family: var(--ab-font-display, "Source Han Serif SC", "Songti SC", serif);
  font-size: clamp(2rem, 7cqw, 5.5rem);
  line-height: 1.05;
  letter-spacing: 0.01em;
  color: var(--ab-ink, #1b1a17);
}
.ab-bi__en{
  margin: 0;
  max-width: 34em;
  font-family: var(--ab-font-body, sans-serif);
  font-size: 0.95rem;
  font-style: italic;              /* 斜体只在英文行用,中文不用假斜体 */
  line-height: 1.7;
  color: var(--ab-muted, #8a8577);
}
```

## Token 依赖

- `--ab-font-display` / `--ab-font-body`:中文行与英文行分族
- `--ab-label-tracking`:英文 kicker 的字距
- `--ab-ink` / `--ab-muted`:主/次

## 禁忌

- **层级只允许三层**:kicker / 中文主标 / 英文副行。第四层(英文再套小标)直接删。
- 中文不要用 `font-style: italic` —— 浏览器会给中文做假斜体,读起来像倾斜的错字。
- 中英混排不加空格凑对齐;间距靠 `gap`,不靠 `&nbsp;`。
- 英文 kicker 全大写时字号不超过中文主标的 0.22 倍。
