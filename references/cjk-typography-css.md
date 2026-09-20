# artboard 中文排版 CSS 落地

> **何时读**:写中文正文/标题的 HTML 时;或自检发现标点别扭、中西文挤在一起、标题断在词中间。
> 规则在 `typography-rules.md`,本册只给 **CSS 实现**(浏览器默认不做这些)。冲突时规则优先。
> 来源:MDN `text-spacing-trim` <https://developer.mozilla.org/zh-CN/docs/Web/CSS/Reference/Properties/text-spacing-trim> ·
> MDN `text-autospace` <https://developer.mozilla.org/zh-CN/docs/Web/CSS/Reference/Properties/text-autospace> · W3C clreq

---

## 〇、先认清:浏览器默认会做什么、不会做什么

| 你要的效果 | 浏览器默认 | 需要你做 |
|---|---|---|
| 句读点不出现在行首 | ✅ 会(`line-break` 默认 `auto` 已含禁则) | 用 `line-break: strict` 收紧 |
| 全角标点行尾挤压为半角 | ❌ 不会(永远占 1em) | `text-spacing-trim` |
| 连续两标点 2em → 1.5em | ❌ 不会 | `text-spacing-trim` |
| 中西文之间 1/4 em 空隙 | ❌ 不会(要手写空格) | `text-autospace` 或手写 `&thinsp;` |
| 中文标题按语义断行 | ❌ 不会(按任意字符断) | 手动 `<span class="tl">` + `<wbr>` |
| 破折号/省略号不拆行 | ⚠️ 部分 | `white-space: nowrap` 包裹 |
| 汉字不拉长压扁 | ✅ 默认不会(除非你写了 `transform`) | 别写 `transform: scaleX()` |

**结论**:禁则免费,挤压和间距要钱。所以下面的配方是必需的,不是可选优化。

---

## 一、标点挤压:`text-spacing-trim`

控制 CJK 标点的内部间距(把 1em 的全角标点按要求压到半角 / 1.5em→1em)。

```css
.poster {
  text-spacing-trim: space-first;      /* 推荐值,见下表 */
}
```

| 值 | 效果 |
|---|---|
| `normal` | 不挤压(默认,标点永远占满 1em) |
| `space-first` | 行首标点压到半角宽,连续标点压缩;**行尾不压**(最稳,推荐) |
| `space-all` | 行首行尾全压(更紧,但行尾可能显得空) |
| `trim-start` | 只处理行首 |

**降级写法**(引擎版本不可控时必须):
```css
.poster { text-spacing-trim: normal; }              /* 兜底 */
@supports (text-spacing-trim: space-first) {
  .poster { text-spacing-trim: space-first; }
}
```

> ⚠️ **导出验证是硬要求**:`text-spacing-trim` 的支持随 Chromium 版本变化,而 WPI 用的是**系统 Edge/Chrome**。写完后必须导出 PNG 肉眼确认标点位置;若确认不支持,退回手写方案(§五)。

---

## 二、中西文 / 数字间距:`text-autospace`

自动在中日韩文字与拉丁字母、数字之间插入 1/4 em 间距(即 `guardrails.md:46` 要的那个 1/4 空格)。

```css
.poster {
  text-autospace: ideograph-alpha ideograph-numeric;
}
```

| 值 | 作用 |
|---|---|
| `ideograph-alpha` | 汉字 ↔ 拉丁字母 之间自动加间距 |
| `ideograph-numeric` | 汉字 ↔ 数字 之间自动加间距 |
| `punctuation` | 标点处的间距优化 |
| `no-autospace` | 关闭 |

```css
/* 降级:先关,支持才开 */
.poster { text-autospace: normal; }
@supports (text-autospace: ideograph-alpha) {
  .poster { text-autospace: ideograph-alpha ideograph-numeric; }
}
```

**与手写空格的关系**:如果文案里已经手打了空格(`共计 24 帧`),`text-autospace` 会**再**加一份 → 间距翻倍。
→ **二选一**:要么全用 `text-autospace` 且文案不写空格,要么写空格且不开 `text-autospace`。**同一项目内必须统一。**

> 中西文**怎么搭**(搭配矩阵/密度匹配/双语层级)见 `bilingual-typography.md`;本节只管"间隔多大"。

---

## 三、断行控制:四件套

```css
.poster {
  word-break: keep-all;        /* 1. 中文不在任意字符处断(由 line-break 决定断点) */
  line-break: strict;          /* 2. 严守禁则:句读点/收尾引号不落行首 */
  overflow-wrap: break-word;   /* 3. 西文长词兜底,防溢出 */
  text-wrap: pretty;           /* 4. 避免末行孤字(见下) */
}
```

| 属性 | 为什么 |
|---|---|
| `word-break: keep-all` | 默认 `normal` 会让**西文单词**断行;中文里主要防的是英文词被劈开。中文本身靠 `line-break` 断 |
| `line-break: strict` | 收紧禁则。`auto` 会在某些情况下放松(比如允许逗号落行首),`strict` 不放 |
| `overflow-wrap: break-word` | 最后一道防线:URL、长英文词不溢出画布 |
| `text-wrap: pretty` | 优化末行,减少孤字;`balance` 只匀称不认语义,**标题不许单用**(见 §四) |

> ⚠️ `text-wrap: balance` 与 `pretty` 的区别:`balance` 让各行长度接近(好看但断点随机),`pretty` 只优化孤字(保守)。
> `guardrails.md` 的「孤字」是硬禁,所以**正文用 `pretty`,标题用手动断行**。

---

## 四、标题语义断行(沿用 `typography-rules.md` §一)

CSS 帮不了语义 —— 标题必须**手动给断点**。

```html
<h1 class="title">
  <span class="tl">新手摄影</span>
  <span class="tl">6 个避雷点</span>
</h1>
```
```css
.title .tl { display: block; }          /* 每个 span 一行 */
```

配套(让自动回退也安全):
```css
.title {
  word-break: keep-all;
  line-break: strict;
  text-wrap: balance;    /* 只在"没手动断行"时兜底;手动断行后它不起作用 */
}
```

**软断点**(允许但不强制断):
```html
<span class="t-keep">店群运营<wbr>被认定为<wbr>拆分收入</span>
```
`<wbr>`(U+200B 语义)告诉浏览器"这里可以断",比硬 `<br>` 灵活。

**验收**:每行独立成意。读一遍断好的标题,任意一行的最后一个词和下一行第一个词**不能组成一个词**。
- ✅ `新手摄影 / 6 个避雷点`
- ❌ `店群运营被认 / 定为拆分收入`(「认定」被劈开)

---

## 五、降级方案(引擎不支持新属性时)

若导出验证发现 `text-spacing-trim` / `text-autospace` 无效,用手工方案补足:

### 5.1 中西文 1/4 em 间距

```html
共计&thinsp;24&thinsp;帧
```
```css
.lat { margin-inline: .06em; }   /* 等价的类方案 */
```
- `&thinsp;` = 窄空格(1/6–1/5 em),接近 1/4 em
- 或精确点:`&#8288;` 不推荐;`&thinsp;` 最实用

### 5.2 标点挤压(手工)

只对**行尾紧邻边界**的标点做局部处理:
```html
<span class="squeeze">,</span>
```
```css
.squeeze { display: inline-block; width: .5em; text-align: center; }
```
⚠️ 只用于**确定的、少量**位置(如标题末尾的句号),不要全文套——全文手工挤压会引入更多错位。

### 5.3 决策顺序

```
1. 先试 text-spacing-trim + text-autospace(一行 CSS)
2. 导出 PNG 验证
3. 不支持 → 中西文用 &thinsp; 手写(便宜、可控)
4. 标点挤压放弃(手工代价 > 收益),改用 line-break: strict 保禁则即可
```

---

## 六、破折号 · 省略号 · 引号(Unicode 规范)

| 符号 | 正确 | 错误 | 码位 |
|---|---|---|---|
| 破折号 | `——`(两个 U+2014) | `――`、`--` | U+2014 ×2 |
| 省略号 | `……`(两个 U+2026) | `...`、`。。。` | U+2026 ×2 |
| 左双引号 | `"` | `"`(直引号) | U+201C |
| 右双引号 | `"` | `"` | U+201D |
| 单引号 | `' '` | `' '` | U+2018 / U+2019 |
| 书名号 | `《》` | `<>` | U+300A / U+300B |
| 间隔号 | `·` | `・`、`．` | U+00B7 |
| 连接/范围 | `–`(en dash) | `-`(hyphen) | U+2013 |

**不许拆行**:
```css
.nowrap { white-space: nowrap; }
```
```html
<span class="nowrap">——</span>  <span class="nowrap">……</span>
```
破折号/省略号占 2 字宽,**必须整体**,断到下一行会出现行首 `—` 的畸形。

---

## 七、字体特性(可选,按字体支持)

```css
.poster {
  font-feature-settings: "palt" 1;        /* 西文/标点比例宽度,收紧标点 */
  font-variant-east-asian: proportional-width;   /* 等价的标准属性,优先用这个 */
}
```
- `"palt"` 让全角标点在**非行首行尾**时按半角绘制,视觉上比 `text-spacing-trim` 更彻底
- **风险**:部分中文字体不支持 `palt`,开启后无变化;少数字体开启后标点贴太紧
- **用法**:先不开,导出对比一次,确认变好再开

数字相关(`font-variant-numeric`)见 `numeric-typography.md` §一,不在这里重复。

---

## 八、竖排(可选,特殊风格用)

```css
.vertical { writing-mode: vertical-rl; text-orientation: upright; }
```
- 竖排下 `text-spacing-trim` 依然生效
- 数字用 `text-combine-upright: digits 2` 让两位数横向合并
- ⚠️ 竖排 + 固定画布 + 长文 = 极易溢出,只在**短标题/书法风**用

---

## 九、可复制配方(整段抄)

```css
:root{
  --cjk-safe: 1;
}
.poster{
  /* ① 断行与禁则(免费,必开) */
  word-break: keep-all;
  line-break: strict;
  overflow-wrap: break-word;

  /* ② 孤字优化(正文) */
  text-wrap: pretty;

  /* ③ 平滑与可读 */
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;

  /* ④ 渐进增强:标点挤压 */
  text-spacing-trim: normal;
  text-autospace: normal;
}
@supports (text-spacing-trim: space-first){
  .poster{ text-spacing-trim: space-first; }
}
@supports (text-autospace: ideograph-alpha){
  .poster{ text-autospace: ideograph-alpha ideograph-numeric; }
}

/* ⑤ 标题手动断行 */
.title .tl{ display:block; word-break:keep-all; line-break:strict; }

/* ⑥ 不拆行的符号(破折号/省略号/数字+单位) */
.nowrap{ white-space:nowrap; }
```

对应 HTML:
```html
<h1 class="title">
  <span class="tl">新手摄影</span>
  <span class="tl">6 个避雷点</span>
</h1>
<p class="body">共计&thinsp;24&thinsp;帧,覆盖 <span class="nowrap">9–13 日</span>。</p>
```

---

## 十、中文排版落地自检(7 条)

1. `word-break: keep-all` + `line-break: strict` 都写了?
2. 导出的 PNG 上,**没有**句读点/收尾引号落在行首?(肉眼,不是看代码)
3. 中西文之间有间距(`text-autospace` 生效,或手写了 `&thinsp;`)?**没有双倍间距?**
4. 标题是**手动断行**的?每行独立成意?没有词被劈开?
5. 正文末行不是孤字?
6. 破折号用 `——`、省略号用 `……`,且包了 `nowrap`?
7. 引号是弯引号 `""`,不是直引号 `""`?

> 打分走 `design-review-rubric.md`(并入「B 排版质量」25%;孤字/词中劈开直接判该维度 ≤2)。
> 规则条文(为什么这么规定)见 `typography-rules.md`。
