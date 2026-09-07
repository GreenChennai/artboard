# artboard 视觉特效分册(30 配方,纯 CSS/SVG,静态渲染安全)

> 原理研究自 zhuxice-ctrl/Art 的「组件」视觉特效实验室(约 90 个),代码全部为本技能自写
> (原仓库无 LICENSE,不复制其代码)。每条 = 类名 + 用途 + 片段。
> **使用纪律:一图 ≤3 种特效;特效服务层级,不堆砌。**
> 全部为静态形态(WPI 导出 PNG 时动画会收敛到终态,勿依赖动画中间帧)。

---

## 一、印刷质感

### fx-noise 噪点颗粒
万能"胶片感"顶层,压住数字味的平底。**叠最上层,`pointer-events:none`**。
```css
.fx-noise { position:absolute; inset:0; opacity:.06; mix-blend-mode:multiply; pointer-events:none;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='120' height='120' filter='url(%23n)'/%3E%3C/svg%3E"); }
```

### fx-halftone 半调网点
波普/印刷感背景。网点由密到疏。
```css
.fx-halftone { position:absolute; inset:0; pointer-events:none;
  background-image:radial-gradient(circle, var(--c-ink) 1.2px, transparent 1.3px);
  background-size:12px 12px;
  -webkit-mask-image:linear-gradient(115deg, #000 15%, transparent 60%); }
```

### fx-riso 孔版印刷错版
两色错位叠印,复古印刷的灵魂。双元素或双背景 + `multiply`。
```css
.fx-riso { position:relative; }
.fx-riso::before, .fx-riso::after { content:attr(data-text); position:absolute; inset:0; }
.fx-riso::before { color:var(--c-primary); transform:translate(-3px,-2px); mix-blend-mode:multiply; }
.fx-riso::after  { color:var(--c-accent); transform:translate(3px,2px);  mix-blend-mode:multiply; }
```

### fx-misprint 文字错版(单层版)
riso 的轻量版:主文字 + 1px 错位色影。
```css
.fx-misprint { text-shadow: 3px 3px 0 var(--c-accent), -2px -2px 0 var(--c-primary); }
```

### fx-paper 纸感底色
暖底 + 细噪(配合 fx-noise)。
```css
.fx-paper { background:
  radial-gradient(120% 90% at 20% 10%, #fffdf8 0%, var(--c-bg) 55%, #efe7da 100%); }
```

### fx-newsprint 报纸灰调
```css
.fx-newsprint { background:#ece9e2; color:#2b2a26; }
.fx-newsprint img { filter:grayscale(1) contrast(1.05); }
```

## 二、渐变与光学

### fx-mesh 网格渐变(Asymmetric Mesh)
多层 radial 叠加,当代海报底色之王。色值换 tokens。
```css
.fx-mesh { background:
  radial-gradient(60% 55% at 18% 22%, var(--c-primary) 0%, transparent 62%),
  radial-gradient(50% 45% at 82% 18%, var(--c-accent) 0%, transparent 58%),
  radial-gradient(70% 65% at 70% 88%, color-mix(in srgb, var(--c-primary) 55%, #fff) 0%, transparent 60%),
  var(--c-bg); }
```

### fx-aurora 极光帷幕
conic 大尺度色带 + 大模糊。**模糊层独立放背景,别包内容**。
```css
.fx-aurora { position:absolute; inset:-20%; filter:blur(60px); opacity:.75; pointer-events:none;
  background:conic-gradient(from 210deg at 30% 40%,
    transparent 0deg, var(--c-primary) 60deg, transparent 130deg,
    var(--c-accent) 200deg, transparent 280deg); }
```

### fx-iridescent 虹彩薄膜
多色相线性渐变 + 低对比,科技感文字块。
```css
.fx-iridescent { background:linear-gradient(100deg,
  #8ec5ff, #e0c3fc 30%, #ffd3e0 55%, #c3f0e0 80%, #fff3b0);
  filter:saturate(1.1); }
```

### fx-chrome 液态铬金文字
bg-clip 双渐变 + 高光切线。大标题专属。
```css
.fx-chrome { background:
  linear-gradient(175deg, #fdfdfd 8%, #a8b2bd 28%, #4d565f 46%,
                  #e8edf2 52%, #6b7480 68%, #22262b 88%);
  -webkit-background-clip:text; background-clip:text; color:transparent; }
```

### fx-foil 烫金箔
```css
.fx-foil { background:
  linear-gradient(100deg, #7a5a1e 0%, #d8b45a 22%, #fff0c2 38%,
                  #c9992e 55%, #8a6a24 72%, #e8c96a 100%);
  -webkit-background-clip:text; background-clip:text; color:transparent; }
```

### fx-halation 光晕
层叠 box-shadow,给主标或焦点图标。
```css
.fx-halation { box-shadow:
  0 0 18px  color-mix(in srgb, var(--c-accent) 55%, transparent),
  0 0 60px  color-mix(in srgb, var(--c-accent) 30%, transparent),
  0 0 140px color-mix(in srgb, var(--c-accent) 18%, transparent); }
```

### fx-lightleak 光斑漏光
```css
.fx-lightleak { position:absolute; inset:0; pointer-events:none; mix-blend-mode:screen;
  background:radial-gradient(42% 34% at 86% 8%, rgba(255,214,140,.55), transparent 70%),
             radial-gradient(30% 26% at 6% 92%, rgba(255,140,160,.35), transparent 70%); }
```

## 三、材质

### fx-glass 玻璃拟态卡片
深底 KV 的信息卡片标准件。**需要背后有色块才成立**。
```css
.fx-glass { background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.22);
  border-radius:20px; backdrop-filter:blur(18px);
  box-shadow:0 8px 32px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.25); }
```

### fx-frosted 磨砂白卡
浅底版玻璃。
```css
.fx-frosted { background:rgba(255,255,255,.72); backdrop-filter:blur(14px);
  border:1px solid rgba(0,0,0,.06); border-radius:16px; }
```

### fx-neon 霓虹描字
深底 + 单色霓虹(强调色纪律:全图只给一个霓虹元素)。
```css
.fx-neon { color:#fff;
  text-shadow:0 0 6px #fff, 0 0 14px var(--c-accent),
              0 0 34px var(--c-accent), 0 0 80px var(--c-accent); }
```

### fx-velvet 丝绒
```css
.fx-velvet { background:
  radial-gradient(80% 60% at 50% 0%, color-mix(in srgb, var(--c-primary) 70%, #fff) 0%,
                  var(--c-primary) 45%, color-mix(in srgb, var(--c-primary) 55%, #000) 100%);
  box-shadow:inset 0 0 60px rgba(0,0,0,.45); }
```

### fx-plasma 星云等离子
conic + radial 混合,科技底纹。
```css
.fx-plasma { background:
  radial-gradient(40% 30% at 70% 30%, rgba(46,230,168,.5), transparent 70%),
  conic-gradient(from 90deg at 30% 70%, #2b1b5e, #7c5cff 90deg, #2b1b5e 200deg, #133 300deg, #2b1b5e); }
```

## 四、图形图案

### fx-candy 糖果条纹
```css
.fx-candy { background:repeating-linear-gradient(45deg,
  var(--c-primary) 0 14px, transparent 14px 28px); }
```

### fx-checker 棋盘格
```css
.fx-checker { background:
  conic-gradient(var(--c-ink) 90deg, transparent 90deg 180deg,
                 var(--c-ink) 180deg 270deg, transparent 270deg);
  background-size:32px 32px; opacity:.08; }
```

### fx-starburst 星芒爆炸贴
促销爆炸贴主体。conic 硬停角等分。
```css
.fx-starburst { background:repeating-conic-gradient(var(--c-accent) 0 11.25deg, transparent 11.25deg 22.5deg);
  border-radius:50%; }
/* 用法:圆形色块垫底 + 此层旋转 11.25deg 叠加 */
```

### fx-rings 同心圆靶心
```css
.fx-rings { background:repeating-radial-gradient(circle at 50% 50%,
  var(--c-primary) 0 10px, transparent 10px 26px); }
```

### fx-grid 网格坐标纸
科技/工程感底纹。
```css
.fx-grid { background:
  linear-gradient(rgba(255,255,255,.07) 1px, transparent 1px) 0 0/ 48px 48px,
  linear-gradient(90deg, rgba(255,255,255,.07) 1px, transparent 1px) 0 0/ 48px 48px,
  var(--c-bg); }
```

### fx-gradient-border 渐变描边框
```css
.fx-gradient-border { border:2px solid transparent; border-radius:18px;
  background:linear-gradient(var(--c-bg), var(--c-bg)) padding-box,
             linear-gradient(120deg, var(--c-primary), var(--c-accent)) border-box; }
```

## 五、边框与装饰件

### fx-ticket 票券打孔边
优惠券标准件。两侧半圆挖孔。
```css
.fx-ticket { --r:14px; position:relative; background:var(--c-bg);
  -webkit-mask:radial-gradient(circle var(--r) at left 50%, transparent 97%, #000) left / 51% 100% no-repeat,
               radial-gradient(circle var(--r) at right 50%, transparent 97%, #000) right / 51% 100% no-repeat; }
```

### fx-sticker 贴纸白边
```css
.fx-sticker { background:var(--c-accent); border-radius:14px; padding:8px 18px;
  color:#fff; transform:rotate(-2deg);
  box-shadow:0 0 0 5px #fff, 0 6px 18px rgba(0,0,0,.18); }
```

### fx-tape 胶带
```css
.fx-tape { position:absolute; width:150px; height:36px; left:50%; top:-14px;
  transform:translateX(-50%) rotate(-3deg);
  background:rgba(255,255,255,.5); border-left:2px dashed rgba(0,0,0,.12);
  border-right:2px dashed rgba(0,0,0,.12); box-shadow:0 2px 6px rgba(0,0,0,.08); }
```

### fx-double-frame 双线框
```css
.fx-double-frame { outline:2px solid var(--c-ink); outline-offset:6px;
  border:1px solid var(--c-ink); }
```

## 六、文字效果

### fx-outline-stroke 空心描边大字
```css
.fx-outline-stroke { color:transparent; -webkit-text-stroke:2.5px var(--c-ink); }
```

### fx-longshadow 长投影
```css
.fx-longshadow { text-shadow:2px 2px 0 var(--c-accent), 4px 4px 0 var(--c-accent),
  6px 6px 0 var(--c-accent), 8px 8px 0 var(--c-accent), 10px 10px 0 var(--c-accent); }
```

### fx-duotone 图片双色调
```css
.fx-duotone { position:relative; overflow:hidden; }
.fx-duotone img { filter:grayscale(1) contrast(1.1); }
.fx-duotone::after { content:""; position:absolute; inset:0; mix-blend-mode:screen;
  background:var(--c-primary); }
.fx-duotone::before { content:""; position:absolute; inset:0; z-index:1; mix-blend-mode:multiply;
  background:var(--c-accent); }
```

### fx-emboss 浮雕压印
```css
.fx-emboss { color:var(--c-bg);
  text-shadow:1px 1px 0 rgba(255,255,255,.6), -1px -1px 1px rgba(0,0,0,.35); }
```

### fx-highlight 荧光笔划线
关键词高亮标准件(小红书知识卡常用,比整块底色更"手写感")。
```css
.fx-highlight { background:linear-gradient(transparent 60%, var(--c-accent) 60%);
  padding:0 4px; border-radius:3px; }
```

### fx-table-stripe 表格行交替底
对比/分级型知识卡的行分隔(比边框线更轻)。
```css
.fx-table-stripe tr:nth-child(even) { background:rgba(0,0,0,.035); }
```

---

## 七、文字特效九式(全部假设标题带 data-text 属性;导出安全见 title-fx.md)

### tx-shadow-drop 下拉式模糊投影
```css
.tx-drop { text-shadow:0 12px 28px rgba(0,0,0,.35); }
/* 透明填充字改用: filter:drop-shadow(0 12px 28px rgba(0,0,0,.35)); */
```

### tx-glow 荧光
```css
.tx-glow { color:#fff; text-shadow:0 0 7px #fff, 0 0 10px #fff, 0 0 21px #fff,
  0 0 42px var(--c-accent), 0 0 82px var(--c-accent), 0 0 102px var(--c-accent); }
```
灯芯白色小模糊 + 主色逐级大模糊;**仅深底可用**(浅底发灰)。

### tx-grad-shadow 渐变投影
text-shadow 不支持渐变——伪元素垫层:
```css
.tx-gs { position:relative; z-index:1; }
.tx-gs::before { content:attr(data-text); position:absolute; left:.04em; top:.04em;
  z-index:-1; color:var(--c-primary); }
```
两层字号字重必须严格一致。

### tx-outline 轮廓(空心字)
```css
.tx-outline { color:transparent; -webkit-text-stroke:2px var(--c-ink); }
```
中文细体配 `paint-order:stroke fill`;杂乱背景上加半透明底色块。

### tx-chip 文字背景块
```css
.tx-chip { display:inline; background:var(--c-ink); color:#fff;
  padding:.08em .25em; -webkit-box-decoration-break:clone; box-decoration-break:clone; }
```
多行断开逐行补块;行高 ≥1.6。

### tx-stroke 描边
见 title-fx.md 第一节(paint-order 方案/伪元素多层方案/阴影兜底)。

### tx-knockout 镂空(透明字露底图)
```css
.tx-knockout { background:url(img/hero.jpg) center/cover;
  -webkit-background-clip:text; background-clip:text;
  -webkit-text-fill-color:transparent; color:#888; }
```
字内必须"有东西可露";真挖洞露页面背景用 `mix-blend-mode:screen`(黑底白字)。

### tx-neon 霓虹
```css
.tx-neon { color:#fff; border:2px solid #fff; border-radius:8px; padding:.2em .5em;
  text-shadow:0 0 7px #fff, 0 0 14px var(--c-accent), 0 0 34px var(--c-accent);
  box-shadow:0 0 8px #fff, inset 0 0 8px #fff, 0 0 24px var(--c-accent), inset 0 0 24px var(--c-accent); }
```
灯管=描边+内外发光;暗底专属;flicker 动画导出时禁用定格。

### tx-glitch 故障风
```css
.tx-glitch { position:relative; color:var(--c-ink); }
.tx-glitch::before, .tx-glitch::after { content:attr(data-text); position:absolute; left:0; top:0; }
.tx-glitch::before { color:var(--c-ink); text-shadow:-2px 0 #f0f;
  clip-path:inset(0 0 55% 0); transform:translateX(-3px); }
.tx-glitch::after  { color:var(--c-ink); text-shadow:2px 0 #0ff;
  clip-path:inset(55% 0 0 0); transform:translateX(3px); }
```
【硬】**把"抖动瞬间"写死为默认态**(不写 clip-path:inset(0 0 0 0) 的普通态);RGB 偏移 ≤4px。

## 附:导出适配注意

1. `backdrop-filter` 在无头 Chromium 可用,但玻璃层背后必须有实际色块,纯白底上等于隐身。
2. `mix-blend-mode` 叠层导出稳定;**避免 `filter: blur()` 直接包文字**(会糊)。
3. 细密纹理(halftone 12px 以下)在 scale=1 长图上可能出现摩尔纹——长图用 ≥14px 网距或 scale=2。
4. 所有特效层一律 `pointer-events:none`(虽然没有交互,保持习惯)。
