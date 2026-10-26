---
id: ornament.seal-stamp
category: ornament
styles: [新中式]
tokens: [--ab-font-display, --ab-seal-ink, --ab-seal-rotate]
sources: [you-want/han-design, shuimo-design/shuimo-ui]
status: stable
---

## 结构

```html
<span class="ab-seal" aria-hidden="true">墨<br>戏</span>
<!-- 白文(反白)变体 -->
<span class="ab-seal ab-seal--inverse" aria-hidden="true">观<br>止</span>
```

## 核心 CSS

```css
.ab-seal{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.6em;
  height: 2.6em;
  padding: 0.24em;
  box-sizing: border-box;
  writing-mode: vertical-rl;          /* 印章文字竖排从右向左 */
  font-family: var(--ab-font-display, "Source Han Serif SC", serif);
  font-size: 20px;
  font-weight: 700;
  line-height: 0.92;
  letter-spacing: 0.1em;
  color: var(--ab-seal-ink, #a5342a);
  border: 2px solid currentColor;
  border-radius: 2px;
  transform: rotate(var(--ab-seal-rotate, -4deg));
  opacity: 0.92;
  mix-blend-mode: multiply;           /* 压在纸上更像油墨,而不是贴纸 */
  pointer-events: none;
  user-select: none;
}
.ab-seal--inverse{
  background: var(--ab-seal-ink, #a5342a);
  color: #f7f1e6;
  mix-blend-mode: normal;
}
```

## Token 依赖

- `--ab-seal-ink`:印泥色(默认朱砂;不要用纯红 `#f00`)
- `--ab-seal-rotate`:倾斜角,−6°~−2° 之间像手盖;0° 像 UI 图标
- `--ab-font-display`:印章字用衬线/楷体,不用黑体

## 禁忌

- 印章是**收尾**不是主体:面积不超过画面 4%,全图 ≤1 枚。
- 不加投影、不加发光、不做渐变:印章的可信度来自"平"。
- 不用印章承载必读信息(电话/二维码/价格)。
- `mix-blend-mode` 下方必须是实底;压在照片上会脏,改用白文变体并加深色底。
