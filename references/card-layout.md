# artboard 卡片与容器布局(防文字出框)

> **何时读**:写任何"带背景/边框/圆角的文字容器"时——卡片、要点框、标签块、信息条目、优惠券、表格行。
> **一句话**:文字容器**一律自适应高度**;确需定高必须配 `line-clamp` 收口。禁止"定高盒 + 长文案"。
> **可机检**:`scripts/check_overflow.py` 能自动报出"文字越出容器边框"(见 §七)。

---

## 一、为什么会出框:三个叠加的缺口

| # | 缺口 | 后果 |
|---|---|---|
| 1 | **容器定高**:`height: 92px` 类写法 | 文案超一行就画到背景色之外 |
| 2 | **无收口**:全技能 `min-height` / `line-clamp` / `text-overflow` 出现 **0 次** | 内容既长不出去也裁不掉,只能越框 |
| 3 | **自检以"画布"为参照** | 文字出卡片但没出画布 → 五维评审**全部放过** |

第 3 条是根因:**问题不出在作者不小心,出在"没人看得见"**。所以修法必须同时给
①正确写法 ②可机检手段,只给"注意一点"没用。

### 最常见的三种出框写法

```css
/* ✗ A 定高卡片 + 可换行文案 */
.coupon { height: 92px; }              /* 文案到第 3 行就出框 */

/* ✗ B 上下双向锁死 + space-between */
.list   { top: 660px; bottom: 170px; } /* 可用高度被锁死 */
.item p { font: 400 24px/1.6; }        /* 任一条多一行 → 卡重叠或压页脚 */

/* ✗ C 底锚容器 + 无高度约束 */
.cards  { bottom: 96px; }              /* 内容变长 → 整体向上顶穿上主标 */
.card   { flex: 1; }                   /* flex:1 只管等宽,不管高度 */
```

三者共性:**容器高度由"位置"或"定值"决定,内容高度由文案决定,两者没有约束关系。**

---

## 二、三条硬规则

1. **文字容器禁写死 `height`**。要定高度下限用 `min-height`;要固定视觉高度且文案不可控,
   必须同时 `line-clamp` 收口(§四.2)。
2. **禁同时锁 `top` 与 `bottom`** 去装会被撑高的内容(那是"固定带")。要么只用一边、
   要么用 `flex` / `grid` 让容器跟随内容。
3. **装饰越界要显式声明**(见 §六):容器内只放会自适应流式布局的内容,不用 `position:absolute`
   去摆条目标题(绝对定位脱离流,内容就无处生长)。

> `xhs-cover.md:94`「禁止用 `flex:1` 上下夹击」的**准确语境**:禁的是"用 `flex:1` 制造上下大留白",
> **不是**禁止 flex 自适应。用 `flex` 让内容自然撑开容器**恰恰是本册推荐的**。

---

## 三、卡高公式(设计前估算,不是事后补救)

接 `composition.md` 的**基线单位**(= `round(正文字号 × 行高 ÷ 4) × 4`):

```
卡高 = padding-top + padding-bottom
     + 标题行数 × (标题字号 × 标题行高)
     + 条间距 × (条数 − 1)
     + 正文行数 × (正文字号 × 正文行高)
```

其中行数由字数反推:

```
每行字数 = floor( (卡宽 − 2×padding) ÷ 字号 )     ← 中文 1 字宽 ≈ 1em
行数     = ceil( 字数 ÷ 每行字数 )
```

**算例**(1080 宽小红书卡,`padding 36`,正文 28px/1.6,标题 34px/1.35,3 条):

| 项 | 计算 | 值 |
|---|---|---|
| 内边距 | 36 × 2 | 72 |
| 标题 | 1 行 × 34 × 1.35 | 45.9 |
| 条间距 | 2 × 12 | 24 |
| 正文 | 每条 28 字 → 每行 `floor((900−72)/28)=29` → 1 行/条 → 3 × 28 × 1.6 | 134.4 |
| **单卡高** | | **≈ 276px** |

**用法**:
- **按最长的那一条估**,并把同一组卡片**统一到最大卡高**(CRAP 的 R 重复:同组卡不等高最丑);
- 算出来的值用于**分配版面高度**,不是拿去写 `height!`;
  实现仍是 `min-height: <值>px`,内容更多时允许撑开;
- 总高算完必须与可用高度对账:**超出就减内容**(`guardrails.md §7`),不要缩字号。

---

## 四、五种骨架(直接抄)

### 1 · 默认:自适应高度 + flex 排布

```css
.card{
  padding: 36px 40px;
  border-radius: 20px;
  background: var(--c-bg-2);
  min-height: var(--baseline);        /* 下限,不是定高 */
  display: flex; flex-direction: column;
  gap: 12px;
}
.list{
  display: flex; flex-direction: column;
  gap: 24px;                          /* 卡间距,组内一致 */
  flex: 1;                            /* 让列表吃满剩余高度 */
  justify-content: center;            /* 内容少时居中,而非撑出大留白 */
}
```
**关键**:`min-height` 给下限,`gap` 给节奏,外层 `flex:1 + justify-content:center` 消化高度差。
**不要**给 `.card` 写 `height`。

### 2 · 文案长度不可控:line-clamp 收口

```css
.clamp-1, .clamp-2, .clamp-3{
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.clamp-1{ -webkit-line-clamp: 1; }
.clamp-2{ -webkit-line-clamp: 2; }
.clamp-3{ -webkit-line-clamp: 3; }
```
**用在哪**:用户提供的文案、抓来的数据、可能被改长的字段。
**不要用在哪**:自己写的标题(该手动断行,见 `typography-rules.md §一`)。
**代价**:被截断的内容不可见 → 必须在**交付时提示**"以下文案被截断,建议精简"。

### 3 · 等高等宽网格:grid auto-rows

```css
.grid{
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-auto-rows: minmax(120px, auto);   /* 行高自适应,下限 120 */
  gap: 24px;
  align-content: center;
}
```
`grid` 天然让**同一行的卡等高**,比 flex 更省事。

### 4 · 短条目/标签:flex-wrap

```css
.tags{ display: flex; flex-wrap: wrap; gap: 14px 20px; }
.tag{ padding: 10px 22px; border-radius: 999px; white-space: nowrap; }
```
`white-space: nowrap` + `flex-wrap` = 标签不内折、超宽自动换行,**永不越框**。

### 5 · 确需定高(表格行、时间轴节点):定高 + 收口 + 字号下调

```css
.row{
  height: 88px;                       /* 定高是有意的 */
  display: flex; align-items: center; gap: 18px;
  overflow: hidden;                   /* 兜底收口 */
}
.row .txt{ min-width: 0; }            /* 关键:允许 flex 子项收缩 */
.row .txt .line1{ font: 700 30px/1.2; white-space: nowrap; text-overflow: ellipsis; overflow: hidden; }
.row .txt .line2{ font: 400 22px/1.3; }
```
`.row .txt{ min-width: 0 }` 是**必需**的:flex 子项默认 `min-width:auto` 不肯收缩,
加了它 `text-overflow:ellipsis` 才会生效。

### 6 · ⚠️ 定高块在纵向 flex 容器里被压成 0 高(flex 收缩陷阱,2026-09 实战案例)

**症状(极具迷惑性)**:固定 `height` 的色块条(如数据分配条)在导出图里**整个消失**,
机检报「内容比盒大,越出盒 top/bottom 各 ~33px」——内容从 0 高的盒子里居中溢出。

**真因链(三条同时满足才触发)**:
1. 父级是**纵向 flex 容器**(整页 `.pad{display:flex;flex-direction:column}` 布局);
2. 所有子项的**自然高度总和 > 画布高**(常见诱因:标题比预算多折了一行);
3. 该块自身有 `overflow:hidden` —— **flex 规范里非 visible 的 overflow 会把
   `min-height:auto` 解析成 0**,于是 `flex-shrink:1`(默认值)可以把它压扁到任意高度,
   优先被压的恰恰是这种"有收口"的块,而没设 overflow 的兄弟块只会把内容顶出去。

**修法(两层都做)**:

```css
.pad  { display: flex; flex-direction: column; }
.bar  { height: 124px; overflow: hidden; flex: none; }   /* 定高块一律 flex:none */
```
加上**内容总高预算**:写完后把各块的 margin + height 手加一遍,必须 ≤ 画布高。
标题断行是最大变量——大标题的**行数要锁死**(宽度留余量或手工 `<br>`),
行数 ×1 就是总高爆掉的量。

> 判别口诀:**「定高元素渲染成 0 高 → 先查它是不是纵向 flex 的子项」**。
> 用 `getComputedStyle(el).height` 一秒确诊;别去调字号——字号是症状,shrink 是病根。

---

## 五、一行修复对照表

| 症状 | 改法 |
|---|---|
| 文字画到卡片背景外 | `height` → `min-height`;外层用 flex 消化高度差 |
| 卡片互相重叠 / 压页脚 | 去掉 `top`+`bottom` 双锁,改 `gap` + `flex:1` |
| 卡片顶穿上一个板块 | 去 `bottom:` 绝对锚定,容器改流式;或给上方板块留 `margin-bottom` |
| 文案太长撑破版面 | `line-clamp-N` 收口 + 交付时提示截断 |
| 表格行文字被挤 | 子项加 `min-width: 0`;行内文字 `nowrap + ellipsis` |
| 同组卡片高矮不齐 | 统一 `min-height` 到**最大估高**;或改 `grid-auto-rows: minmax(...)` |

---

## 六、装饰越界的正确姿势

装饰(光晕/放射线/噪点/大数字水印)**允许**越出卡片甚至画布,但必须显式:

```css
.card{ position: relative; overflow: visible; }   /* 默认就是 visible,别去设 hidden */
.card .glow{ position: absolute; inset: -60px; opacity: .35; pointer-events: none; }
```

- **文字与关键图形**绝不越界;**装饰**可以,且要低透明度(≤0.5);
- 给装饰加 `pointer-events: none`(避免影响将来交互/选中);
- **不要**用 `overflow: hidden` 去"兜住"文字——那会把文字裁掉一半,比出框更难看。
  `overflow: hidden` 只用于**确认会截断且截断可接受**的位置(图片框、clamp)。

---

## 七、机检:自动找出出框

```bash
# 容器越框(A/B 类)—— 每次重导前的门禁
python scripts/check_overflow.py <项目>/src

# 视频卡 / 会被叠字幕的动图:追加安全区检查(C 类)
python scripts/check_overflow.py <项目>/src --safe-area auto
```

用 Playwright 加载页面后遍历 DOM,报三类:

| 类型 | 判据 |
|---|---|
| **A 内容溢出自身盒** | `scrollHeight > clientHeight + tol` 或 `scrollWidth > clientWidth + tol`(限"有背景/边框"的盒) |
| **B 越出绘制的祖先** | 文字盒超出最近"有背景色或可见边框"的祖先盒(容差 `tol` px) |
| **C 越出安全区** | 内容盒超出视频安全区矩形(`--safe-area` 时启用,细则见 `video-safe-area.md`) |

```json
{"ok": false, "issues": [
  {"type":"A","selector":".coupon","overflowY":14,"hint":"内容比盒高 14px"},
  {"type":"B","selector":".card p","ancestor":".card","right":22,"bottom":9}
]}
```

- 装饰元素用 `data-allow-overflow` 标记即豁免:`<div class="glow" data-allow-overflow>`
- 尺寸由页面实际几何算,不必传 `--width/--height`(长图也可用)
- 退出码 0/1;**已接进流水线 Step 6.0 作为每次重导前的门禁**(零 token 成本)

**它是唯一能看见"出卡片但没出画布"的手段**——读导出图看不出(线条颜色相近时),
必须靠几何量测。

---

## 八、自检(逐条过)

1. 所有文字容器**没有**写死 `height`?(`min-height` 可以)
2. 装会被撑高的内容时,**没有**同时用 `top` + `bottom`?
3. 同组卡片的 `min-height` 统一到**最大估高**?
4. 别人的/会长变的文案用了 `line-clamp`?交付时提示了截断?
5. flex 子项要省略号时,加了 `min-width: 0`?
6. 跑过 `check_overflow.py` 且 `ok: true`?(或已人工确认越界的只有装饰)
7. 装饰越界处透明度 ≤0.5、带 `data-allow-overflow`?

## 本册用到的脚本

| 脚本 | 何时用 | 一行示例 |
|---|---|---|
| `check_overflow.py` | 卡片越框 A/B 类机检 | `python scripts/check_overflow.py <proj>/src` |

> 参数的权威说明在脚本自身 `--help`(不在此复制);全量索引见 `docs/scripts.md`。
