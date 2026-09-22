# 微信公众号图文 · HTML 与 SMIL 动效分册

> **何时才读**:用户要做「公众号文章 / 微信图文 / 秀米排版 / 微信兼容 HTML / 带动的长图文」,
> 或要把一份长内容做成**能直接粘进公众号编辑器、且动画真的会动**的 HTML 时(**必读**)。
> 只做静态海报/图片时不需要读本册。
>
> **配套脚本**:`scripts/check_wechat_svg.py`(机检门禁,零 token,交付前必跑)。

---

## §〇 定位:这是「模式 W」,与出图片的流水线不同

| | 主线(出图) | **模式 W(公众号图文)** |
|---|---|---|
| 交付物 | PNG / GIF / MP4 / PDF | **HTML 源码**(粘进编辑器) |
| 画布 | 固定尺寸 + `overflow:hidden` | `max-width:677px` 自适应,**不设固定高** |
| 尺寸 | 由画布决定,像素级控制 | 由内容撑开(长文可达 16000px+) |
| 样式 | 可用 `<style>` / class / CSS 动画 | **只能全内联**;`<style>`、`@keyframes`、JS 全被剥离 |
| 动效 | GIF / MP4(`animation.md` 的模式 P/S) | **只能内联 SVG + SMIL** |
| 导出 | `export.py` → WPI | **不导出**;发布走 **135 编辑器中转**(§八,实测 98%+ 还原度) |
| 自检 | `check_overflow.py`+`design-review-rubric` | `check_wechat_svg.py`+本册 §十一 清单 |

**共同点**(可直接复用 artboard 已有资产):一图一个焦点、层级 ≤3、强调 ≤2、
字体 ≤3 款、配色 token 来自 `color-contrast.md` / `style-system.md`、
中文排版参照 `cjk-typography-css.md`、容器布局参照 `card-layout.md`。

**一图两用**:模式 W 的正文里所有"视觉块"(hero、章节图、卡片)本身就是固定尺寸的画布,
可以先用 `export.py` 导成 PNG 做封面/预览图,再把同一份 HTML 内联进长文。

---

## §一 三条硬约束(违反任何一条 = 白做)

### 1. 只有「内联 SVG + SMIL」能在公众号里动

微信后台会**剥离** `<style>` 块(含 `@keyframes`)、全部 JavaScript,
并**过滤所有 `id` 属性**。所以:

- 纯 CSS 动画、`transition`、JS 动画 → 一定失效
- 依赖 `id` 的 `url(#…)` 引用(渐变/滤镜/遮罩/`<use>`) → 一定失效
- **唯一可行路径**:内联 `<svg>` 里写 SMIL(`<animate>` / `<animateTransform>` / `<set>`)

### 2. 只准用微信 SVG AttributeName 白名单

制定方:微信团队 & JZ Creative(2016 起生效,现为 T/CASME 1609—2024)。
**超出白名单的动画标签会被平台强制消除。**

| 元素 | 允许的目标 |
|---|---|
| `<animate>` | `x` `y` `width` `height` `cx` `cy` `opacity` `d` `points` `stroke-width` `stroke-linecap` `stroke-dashoffset` `fill` |
| `<set>` | 仅 `visibility` |
| `<animateTransform>` | `translate` `scale` `rotate` `skewX` `skewY` |
| `<animateMotion>` | `path` `rotate` `keypoints` |

**禁用标签**:`<style>` `<script>` `<filter>` `<linearGradient>` `<radialGradient>`
`<clipPath>` `<mask>` `<pattern>` `<use>` `<symbol>` `<marker>` `<foreignObject>`
→ **SVG 里不能出现任何渐变**(页面级 CSS `background:linear-gradient(...)` 内联样式不受限)。

> **没有渐变怎么画光影**:
> - 径向色阶 → **同心圆叠实色**(由外到内由深到浅,10 档就够)
> - 外发光 → **多层同色低透明度叠圆**(层数要多、单层透明度要低,见 §三·坑 7)
> - 线性渐变 → **纯色低透明度矩形叠底衬**

#### 白名单口径备注(2026-09 联网核对,来源见文末)

- 规范文本:T/CASME 1609—2024;业内通行转述页为 zer0n(计育韬)《微信 SVG AttributeName 白名单》
  (zer0n.cn/archives/wechatsvg,2020 首发、2024 仍在维护)。
- **两处口径差,按本分册实测口径执行**:
  ① `r`:zer0n 转述的规范文本里 `<animate>` 列含 `r`(并注 `cx`/`cy` "用于确定圆心"),
  doocs/md 的白名单表则不列 `cx`/`cy` —— **实操仍按坑 1 处理:`r` 不可动,半径动画一律 `scale` 套 `<g>`**;
  ② `stroke-dasharray`:规范文本在列,但我们的实测清单只验过 `stroke-dashoffset` ——
  要用先真机验证,验不了就不交付。
- `<animateMotion>` 的 `mpath` 子元素在规范列内,但经 135/编辑器链路的支持情况不明,**避免使用**。
- **交互事件优先级(zer0n 原文)**:`touchstart > touchmove > touchend > tap > click`;
  touch 系单个对象单次只识别一次、`touchmove`/`touchend` 有误触发几率、`tap` 部分终端无反应。
  **结论:交互触发统一 `begin="click"` + `fill="freeze"` + `restart="never"`**
  (doocs/md 已验证的纪律);禁止 touch 链与 click 链混用、禁止残留 touchend 回位链
  (混用曾导致回位闪烁类 bug)。PC 端要能触发需 `touchstart`+`click` 双事件。

### 3. 静默降级原则(写每个动效时的验收标准)

> **带动画的元素,它的「静态坐标」必须是它动画结束时应处的位置。**

因为微信/秀米/135 各版本对 SVG 的处理不一致,动画有概率被剥离。
只要静态坐标 = 终态,剥离后画面依然是一张构图完整的静态海报,而不是元素堆在一起或飞出画布。

```svg
<!-- ❌ 错:循环播放时元素大部分时间在画布外, 截屏经常什么都看不到 -->
<g><animateTransform attributeName="transform" type="translate"
      values="0 -420;0 0" dur="3.6s" repeatCount="indefinite"/>
  <rect .../></g>

<!-- ✅ 对:分三层嵌套 —— 外层静态=落定位置;中层落一次即停;内层持续小幅浮动 -->
<g transform="translate(86,92)">
  <g><animateTransform attributeName="transform" type="translate"
        values="0 -560;0 0" dur="1.55s" begin="0s" fill="freeze"/>
    <g><animateTransform attributeName="transform" type="translate"
          values="0 -7;0 7;0 -7" dur="3.4s" begin="1.9s" repeatCount="indefinite"/>
      <rect .../></g></g></g>
```

---

## §二 HTML 骨架与写法规范

### 可直抄的骨架(秀米 / 135 / 公众号编辑器三兼容)

```html
<!-- ========== 品牌版 ========== -->
<section style="max-width:677px;margin:0 auto;background-color:#FBF6E9;font-family:…;color:#2A2620;overflow-x:hidden;box-sizing:border-box;">

  <!-- ① 顶部安全区(黑字 Logo 必须放浅色底上) -->
  <section style="background-color:#FBF6E9;padding:20px 20px 14px;box-sizing:border-box;text-align:center;">
    <img src="…" alt="品牌" style="width:72%;max-width:100%;display:block;margin:0 auto;" />
  </section>

  <!-- ② 视觉段(可换底色成夜色) -->
  <section style="background-color:#0E1C2E;padding:0;box-sizing:border-box;">
    <svg viewBox="0 0 680 452" width="100%"
         style="display:block;width:100%;height:auto;" xmlns="http://www.w3.org/2000/svg">
      …内联 SVG + SMIL…
    </svg>
  </section>

  <!-- ③ 正文段 -->
  <section style="padding:22px 18px 0;box-sizing:border-box;">
    <p style="margin:0 0 15px;font-size:17.5px;line-height:1.9;text-align:justify;color:#2A2620;text-indent:2em;">
      <span leaf="">段落文字</span></p>
  </section>

</section>
```

### 硬规范

| 规则 | 要求 |
|---|---|
| 样式 | **全内联** `style="…"`;零 class、零 `<style>` 块、零 `id` |
| 文字节点 | 每个都包 `<span leaf="">文字</span>`(秀米系约定;漏了会样式漂移) |
| 外层容器 | `max-width:677px;margin:0 auto;overflow-x:hidden;box-sizing:border-box;` |
| 图片 | `width:100%;max-width:100%;display:block;margin:0 auto;` |
| 标签闭合 | `<br/>` `<img …/>` 自闭合;中文标签用 `&ldquo;` `&rdquo;`;`&` 写 `&amp;` |
| `overflow-x:hidden` | **必须**(某处宽了就会让整页左右滚动) |
| 不要 `position:fixed` | 微信会渲染异常 |
| 表格布局 | 图标宫格/标签组用 `<table style="width:100%;border-collapse:collapse;table-layout:fixed;">` + `<td width:%>` |

### 字体(实测结论,别再反复试)

> **铁律:正文内容强制无衬线。**
> 标题 / 特殊文字(诗词、引句、标志性大字、数字)/ 排版(表格、图例、徽章)不限制;
> **只有当用户明确声明「正文要宋体 / 要衬线 / 要某款字体」时,才允许正文用衬线。**
> 理由是硬约束而非偏好:宋体在 16px 以下笔画发虚,手机上一整篇正文会明显"花"。
> 机检已内置这条:`check_wechat_svg.py` 对**长正文段落**(≥40 汉字的 `<p>`)用衬线会报 WARN,
> 短句(诗词/标签)放行。

```css
/* 正文 / 图注 / 说明小字(≤13.5px)—— 默认且唯一 */
font-family:'PingFang SC','HarmonyOS Sans SC','Source Han Sans SC','Noto Sans SC',
            'Hiragino Sans GB','Microsoft YaHei','Heiti SC',sans-serif;
/* 标题 / 诗词 / 标志性大字(≥18px)—— 可选 */
font-family:'Source Han Serif SC','Noto Serif SC','Source Han Serif CN','Noto Serif CJK SC',
            'Songti SC','STSong','SimSun',serif;
```

- **16px 以下不要用宋体**(笔画发虚);18px 以上才显印刷质感。
- **不要内嵌字体文件**(体积 + 版权);全部走系统字体栈,四平台都有落点。
- 楷体 `'STKaiti','KaiTi'` 只在**大字号封面标题**上用(古典气质),正文别用。

### 字号层级(实测舒服的一套,可直接采用)

| 层级 | 字号 | 行高 | 与正文比 |
|---|---|---|---|
| 正文 | 17.5px | 1.9 | 1.0× |
| 图注 / meta | 13.5px | 1.7 | 0.8× |
| 卡片标题 | 18.5px | 1.5 | 1.06× |
| 小节标题 | 21px | 1.5 | 1.2× |
| 章节标题 | 27px | 1.5 | 1.5× |
| **首屏主标题** | **62px** | 1.15 | **3.2×** |
| 首屏附属信息 | 19px | — | 1.1×(**必须大于正文**) |

**留白收紧参数**(用户说"字太小/留白太多"时照抄):

| 项 | 松 | 紧 |
|---|---|---|
| 正文 `margin-bottom` | 24px | **15px** |
| 段落容器 `padding` | `34px 22px` | **`22px 18px`** |
| 卡片 `padding/margin` | `22px/26px` | **`17px/18px`** |
| 小标题 `margin` | `30px 14px` | **`20px 9px`** |
| 图注后下边距 | 30px | **14px** |
| 正文行高 | 2.05 | **1.9** |

> 把这些数字提成模块级常量(`BODY_SIZE` / `BODY_LH` / `SIDE`),
> 之后"再大一点/再紧一点"就是改一行,不用全稿 grep。

---

## §三 SMIL 动效用法

### 3.1 八个必踩的坑(按踩到频率排序)

**坑 1 · `r` 不在白名单** → 不能做圆半径动画。
改用 `animateTransform type="scale"` 套在 `<g>` 上;椭圆涟漪用 `scale` 扩散。

**坑 2 · `animateTransform` 会「覆盖」而非「叠加」静态 `transform`**(最容易漏)
`<animateTransform>` 放在一个**本身已带静态 `transform` 的元素**上时,
它是**整个覆盖掉**那个 transform —— 元素瞬间跳到坐标原点,画面上表现为一团装饰叠在左上角。
**凡动画化的 `<g>`,都必须嵌在一个只用于静态定位的外层 `<g>` 里。**

```svg
<!-- ❌ 元素会跳到原点 -->
<g transform="translate(100,80)">
  <animateTransform attributeName="transform" type="rotate" values="0;360"/>
  <rect …/></g>
<!-- ✅ -->
<g transform="translate(100,80)">
  <g><animateTransform attributeName="transform" type="rotate" values="0;360"/>
    <rect …/></g></g>
```
> 注意这条**比**"同一元素上多个 animateTransform 不叠加"更狠:
> 后者是"只生效一个",前者是"静态定位直接没了"。

**坑 3 · 文本描边** → 画**两层 `<text>`**(下层 `stroke` 加粗、上层 `fill` 覆盖),
不要指望 `paint-order`。

**坑 4 · 驼峰必须精确**:`attributeName` `repeatCount` `keyTimes` `keyPoints`
`calcMode` `attributeType` `viewBox`。写成全小写时 HTML 解析器**有时**能纠正,但别赌。

**坑 5 · `keyTimes` 必须非降序且落在 [0,1]**;用 `values` 做多帧轮换时
`values="0;1;0"` 配 `keyTimes="0;0.02;0.25"` 这种"闪一下"的写法要保证 4 帧刚好铺满 1 个 `dur`。

**坑 6 · 动画化的 `<g>` 不要设 `opacity="0"` 起手**(如果希望它在动画被剥离时仍可见)。
`<animate attributeName="opacity" values="0;1">` 而元素本身没写 `opacity` → 默认 1 → 剥离后可见 ✅;
若写了 `opacity="0"` → 剥离后彻底消失 ❌。
(只有 `ripples` 这类纯装饰才允许"剥离后消失"。)

**坑 7 · 禁用渐变画光晕:层数要多、单层透明度要低**
稀疏的 3–5 层同心圆会画出"褐色大伞",非常难看。实测正解:
**12 层**同色圆、单层 `opacity≈0.036`,半径从 `r×1.62` 递减到 `r×1.0` ——
紧贴外缘最亮、向外迅速衰减。月亮本体再用 10 档实色同心圆做径向色阶。

**坑 8 · `<img>` 会被编辑器过滤**(`data:` 内嵌图尤其)
粘贴后需要重新上传图片。见 §六 的两种对策(图床外链 / 手动上传)。

**坑 9 · 要保留静态 `transform` 又要叠加动画时,用 `additive="sum"`**(坑 2 的嵌套法之外的第二条路)
默认 `additive="replace"` 会整段替换静态 transform;加 `additive="sum"` 则在静态值基础上叠加。
**中心缩放标准三连**(zer0n 规范写法,绕开"scale 以原点为中心"的问题):

```svg
<g transform="translate(200,150)">
  <g>
    <animateTransform attributeName="transform" type="translate" additive="sum"
      values="0 0" dur="0.28s" begin="click" fill="freeze"/>
    <animateTransform attributeName="transform" type="scale" additive="sum"
      values="1;1.12" dur="0.28s" begin="click" fill="freeze"/>
    <animateTransform attributeName="transform" type="translate" additive="sum"
      values="0 0;-20 -17" dur="0.28s" begin="click" fill="freeze"/>
    <circle cx="0" cy="0" r="60" fill="#c9a227"/>
  </g></g>
<!-- 施加(到中心的负位移)→ 缩放 → 抵消(负位移),三条均 additive="sum",
     缩放视觉中心落在 (200,150) 而不是 SVG 原点 -->
```

### 3.2 常用编舞套路(可直接抄)

```svg
<!-- ① 一次性入场(落定即停) + 持续浮动 + 摇摆:三层嵌套 -->
<g transform="translate(X,Y)">
  <g><animateTransform attributeName="transform" type="translate"
        values="0 -520;0 0" dur="1.6s" begin="0s" fill="freeze"/>
    <g><animateTransform attributeName="transform" type="translate"
          values="0 -7;0 7;0 -7" dur="3.4s" begin="1.9s" repeatCount="indefinite"/>
      <g><animateTransform attributeName="transform" type="rotate"
            values="-8 0 0;8 0 0;-8 0 0" dur="2.6s" repeatCount="indefinite"/>
        <rect …/></g></g></g></g>

<!-- ② 逐字浮现(每个字一个 <g>, 静态坐标 = 终态; opacity 不要写静态 0) -->
<g transform="translate(CX,Y)">
  <g><animateTransform attributeName="transform" type="translate"
        values="0 16;0 0" dur="0.72s" begin="0.85s" fill="freeze"/>
    <animate attributeName="opacity" values="0;1" dur="0.72s" begin="0.85s" fill="freeze"/>
    <text x="0" y="0" text-anchor="middle" font-size="62" font-weight="800">月</text>
  </g></g>

<!-- ③ 金线由内向外展开(width 动画; 静态 width 必须设成终点值, 否则剥离后线消失) -->
<rect x="120" y="105" width="180" height="2" fill="#C9A24D">
  <animate attributeName="width" values="0;180" dur="0.9s" begin="0.2s" fill="freeze"/>
</rect>

<!-- ④ 骰子/卡牌换面: 每帧一个 <g opacity="0"> + 该帧自己的 opacity 闪一下 -->
<g opacity="1"><animate attributeName="opacity" values="0;1;0" keyTimes="0;0.02;0.25"
     dur="1.9s" begin="0s" repeatCount="indefinite"/>…画面1…</g>
<g opacity="0"><animate attributeName="opacity" values="0;1;0" keyTimes="0;0.02;0.25"
     dur="1.9s" begin="0.475s" repeatCount="indefinite"/>…画面2…</g>

<!-- ⑤ 呼吸(最安全, 剥离后无副作用) -->
<circle cx="340" cy="150" r="98" fill="#FFF0C4" opacity="0.03">
  <animate attributeName="opacity" values="0.03;0.075;0.03" dur="6.8s" repeatCount="indefinite"/>
</circle>
```

### 3.3 量级参考(一篇长图文的正常体量)

| 项 | 量级 |
|---|---|
| 内联 `<svg>` 组数 | 30–40 |
| `<animate>` | 150–200 |
| `<animateTransform>` | 200–240 |
| SVG 部分的 HTML 体积 | 60–80 KB(纯文本,压缩后极小) |
| 整篇成稿 | 1.8–2.3 MB(图片内嵌 base64 后) |

---

## §四 实战问题清单(现象 → 真因 → 检查 → 修法)

> 这一节是**踩过的坑的沉淀**,按"用户会怎么描述"来查。

| # | 用户会怎么说 | 真因 | 怎么查 | 修法 |
|---|---|---|---|---|
| 1 | 「动画不动 / 贴完没效果」 | 编辑器把 SVG 转义了,或用了 CSS/JS 动画 | 检查有无 `<style>`/`@keyframes`/`<script>` | 改内联 SVG+SMIL;手动方式:F12 → 右键节点 → 「Edit as HTML」→ 粘 HTML |
| 2 | 「装饰全堆在左上角」 | `animateTransform` 覆盖了静态 `transform` | 机检会直接报;或人工找"带 transform 的元素里直接嵌 animateTransform" | 外面再套一层只做静态定位的 `<g>` |
| 3 | 「静默降级后画面是空的」 | 元素起手 `opacity="0"` 或坐标在画布外 | 把所有 `animate*` 删掉看画面 | 静态坐标 = 终态;`opacity` 不写静态 0 |
| 4 | 「文字看不清 / 压在图上看不见」 | 文字压在图片上没做底衬(禁用渐变,只能纯色遮罩) | 采样对比:文字带亮度 vs 背景亮度 | 加纯色低透明底衬(`opacity 0.34~0.46`)+ 上下 1px 细线界定 |
| 5 | 「黑字 Logo 看不见」 | 黑字 Logo 被放在深色底上 | 像素采样:Logo 区是否有黑色像素 | Logo 放**浅色安全区**(浅底 + 上下留白 ≥14px),之后才切深色主视觉 |
| 6 | 「没有主标题的感觉」 | 主标题字号与章节标题几乎同大 | **DOM 量各级字号**(见 §五) | 主标题 ÷ 正文 ≥3×、÷ 章节标题 ≥2×;两行竖排 + 暗影层 + 底衬 |
| 7 | 「留白太多 / 字太小」 | 段距与内边距松、正文字号小 | 量纵向 gap(不是量背景色占比) | 照抄 §二 的「留白收紧参数」 |
| 8 | 「动画里的数量跟正文对不上」 | 画了 7 颗骰子但正文写 6 颗 | **查 DOM 计数**(不要用像素连通域,会粘连) | 改数量;注意删完"配对元素"会落空(见坑 9) |
| 9 | 「删了之后画面怪怪的」 | 删元素时它的配对装饰成了孤立元素 | 删完重看构图 | 要么把剩下的移到对称位,要么把配对装饰一起删 |
| 10 | 「两个月亮 / 元素重复」 | 同类主体元素出现了两处 | 结构层确认(如 `moon=False` 参数) | **同类主体元素全篇只保留一处** |
| 11 | 「顶部前摇太长」 | 开头堆了三四块大标题 | 量"开头到首段正文"的块高和 | 控制在整页 **≤8%**;把主标题并入主视觉一块搞定 |
| 12 | 「图片显示成一小块 / 有硬台阶/色带」 | 透明 PNG 做了 192 色减色,暗部出现色带 | 四角取样 + 放大看暗部 | 改为**按目标底色拍平存 JPG**(§六) |
| 13 | 「图片被裁了,不完整」 | alpha bbox 之后**又**裁了百分比 | 比较 alpha bbox 尺寸与最终尺寸 | alpha bbox 已是紧边界,**不要再裁百分比** |
| 14 | 「本地预览一堆断图」 | 轻量版走相对路径,但交付目录里没有对应文件(或文件名不一致) | 浏览器数 `naturalWidth===0` | 构建脚本里做素材同步 + 文件名映射(§八) |
| 15 | 「成稿是新的、轻量版还是旧的」 | base64 读工程目录、相对路径读交付目录,两者不同步 | DOM 量块高会发现尺寸对不上 | 把同步写进构建流程,不靠手工复制 |
| 16 | 「封面底部有一条亮边」 | 元素截图 @2x 多取了 1 行页面底色 | 量末行亮度(正常应 <20) | 按 `逻辑尺寸×2` 精确裁切(§七) |
| 17 | 「封面文案太小/被压到底部」 | 1:1 小图在列表里显示极小,文案却为了让画面而压底 | 量文字块中心 vs 画布中心 | **文案是主、画面是次** → 整体居中 + 放大 |
| 18 | 「这张图我不想往微信里插」 | 用户自己传到图床了 | — | 生成器加「外链优先」通道(§六) |
| 19 | **「手机上顶出屏幕右边,电脑上看正常」** | `table-layout:fixed` 下表格恒为 100%,**但单元格内容比单元格宽时会溢到右侧** —— 最后一列的内容直接出屏。桌面容器 677px 时单元格 ~155px 看不出,320px 手机时只剩 ~62–71px 就露馅 | **在 320px 视口跑 `check_mobile_width.py`**(桌面 375px 可能仍不报,要压到 320) | 见 §二·窄屏纪律:内容必须可收缩 |
| 20 | 「一整篇正文看着发花、费眼」 | 正文用了衬线(宋体在 16px 以下笔画发虚) | 机检 WARN(长正文段落用衬线) | 正文一律无衬线;只有用户明确要求才用衬线 |

---

## §四之二 窄屏纪律(手机端横向溢出)

**这一类 bug 只在真机出现,桌面预览完全正常** —— 因为公众号正文容器 `max-width:677px`,
桌面窗口宽,单元格有 ~155px;真机只有 300–430px,单元格剩 62–85px。
最典型的症状就是用户描述的那句:**「电脑版和网页以及 135 编辑器看着正常,手机预览被顶出右边的屏幕」**。

### 三条必须遵守的写法

| 规则 | ❌ 会溢出 | ✅ 正确 |
|---|---|---|
| **单元格里的固定宽元素** | `<section style="width:86px">` | `<section style="width:100%;max-width:Npx">` |
| **表格单元格** | 只写 `style="width:25%"` | **同时写 `width="25%"` 属性 + style**(属性比样式更容易存活) |
| **单元格内文字** | 字号偏大 + `letter-spacing` 偏大,挤到超出 | 按最窄 320px 倒推:3 个汉字要在 ~54px 内放下 → 字号 ≤14px、字距 ≤0.5px |

### 按最窄 320px 倒推的"可用宽度"账

```
真机 320px  →  正文容器 320
  段落左右内边距 18px×2         → 可用 284
  若再套一层卡片 padding 17px×2  → 可用 250
  4 列 ×25%                     → 每格 62~71px
  减去 <td> padding 4~6px        → 格内 56~67px
  ⇒ 格内任何元素宽度必须 ≤ 56px 才能全机型安全
```

所以:图标 `max-width` 取 86px 时,**必须写成 `width:100%;max-width:86px`**
(窄屏自动收缩到 ~67px,宽屏仍封顶 86px);标签类文字字号压到 14px、字距 0.5px 并加 `overflow:hidden` 兜底。

### 验收方式(别靠肉眼)

```bash
python scripts/check_mobile_width.py <html 或目录> --widths 300,320,360,375,414
# 退出码 1 = 存在横向溢出; 会精确报出 越界px / 元素 / style
```
⚠️ **必须压到 320px 才可靠** —— 实测同一个文件在 375px / 414px 全部 0 溢出,
**只有 320px 才复现**(最后一列越界 6px)。

---

## §五 无目视验收手法(看不到图时怎么做 QA)

模型不一定能"看"截图。以下四种手法能替代绝大多数目视检查:

### 5.1 DOM 量测(最可靠,优先用)

```js
// ① 块高与相邻空档 → 判断"留白是否收紧"
const rows = [...document.querySelectorAll('body > section section')]
  .map(c => { const r = c.getBoundingClientRect();
              return { y: Math.round(r.top + scrollY), h: Math.round(r.height) }; });
// 逐块算 gap = y - prevBottom; 平均 gap ≈20px 说明纵向已到头

// ② 实际字号 → 判断层级是否拉开
[...el.querySelectorAll('text')].map(t => t.getAttribute('font-size'));
[...document.querySelectorAll('p')].map(e => getComputedStyle(e).fontSize);

// ③ 图片是否真的加载
[...document.querySelectorAll('img')].filter(i => i.naturalWidth === 0);
```

> **DOM 计数 >> 像素计数**:数同类元素(骰子/卡片)时查 DOM,别做像素连通域
> —— 相邻元素会粘连,实测把 6 个宾语数成了 5 个。

### 5.2 像素采样

```python
from PIL import Image
im = Image.open(png).convert("RGB")
im.getpixel((x, y))                       # 核对底色 / 关键点颜色 / 四角是否铺满
# 逐行扫描找"文字行"区间(定位置、验居中、确认没压到图形)
for y in range(TOP, BOT):
    pct = sum(1 for x in range(20, 660, 2)
              if lum(im.getpixel((x, y))) > 140) * 100 / 320
    # pct > 7 的连续区间 = 一行文字
# 文字/背景对比
亮像素(>150) 占比 —— 标题带应显著高于背景(实测标题带 12%,背景 1.8%)
```

⚠️ 用**高阈值 + 只扫文字实际横跨的窄 x 区间**,否则偏亮的背景元素(月亮/云)
会被算进"文字块",居中判断会偏(实测偏差一度被算成 17px,实际 0.5px)。

### 5.3 canvas 逐像素比对验证字体(**CJK 不能用宽度验证**)

中文每个字形恒为 `1em` 宽,换任何字体测出的宽度都等于 `字数 × 字号`
(实测同一段 8 字在衬线栈/无衬线栈/monospace 下**全是 384px**),
所以"量宽度看字体有没有生效"对中文**完全无效**。`document.fonts.check()` 同样不可靠。

```js
const draw = (cv, fam) => { const g = cv.getContext('2d');
  g.fillStyle = '#fff'; g.fillRect(0, 0, cv.width, cv.height);
  g.fillStyle = '#000'; g.font = "64px " + fam; g.textBaseline = 'top';
  g.fillText('月圆相聚 钇企团圆 溯源', 6, 30);
  return g.getImageData(0, 0, cv.width, cv.height).data; };
// 两套字体栈各绘一次, 逐像素统计差异
// 判定: 差异 > 500 px 即说明解析到了不同字体
```
实测:衬线栈墨迹 14522px / 无衬线栈 12701px / 差异 10379 px → 衬线确实生效
(衬线横向笔画更重、墨迹更多,这个特征也能反向佐证)。

### 5.4 渲染切片

```js
// 整页竖切成片, 便于逐片过一眼
await page.screenshot({ path: `${i}.png`, fullPage: true,
                        clip: { x: 0, y: i * sliceH, width: 680, height: sliceH } });
```
⚠️ `element.screenshot({clip})` 的 `clip` **会被忽略**(clip 只对 `page.screenshot` 有效)。
⚠️ 本机 Playwright 用 `chromium.launch({channel:'chrome'})`(复用系统 Chrome),
并**必须**用 `pathToFileURL()` 处理含中文的本地路径。

---

## §六 素材处理

### 6.1 透明 PNG 一定要「按目标底色拍平」后存 JPG

用户给的国风素材常是大尺寸透明 PNG(单张 1–4 MB)。直接转 192 色减色 PNG 省体积 →
**在暗部(光晕/夜色渐变)出现明显色带/硬台阶**,深色底上尤其刺眼。
(实测时先怀疑了图片被裁剪/容器太窄,量了半天 DOM —— 图片其实是完整的,问题全在色带。
**先怀疑素材处理,再怀疑布局。**)

```python
im = Image.open(src).convert("RGBA")
im = im.crop(im.getchannel("A").getbbox())            # ① 先按 alpha 紧边界裁掉透明边
if im.width > target_w:                                # ② 再缩到目标宽
    im = im.resize((target_w, round(im.height * target_w / im.width)), Image.LANCZOS)
flat = Image.new("RGB", im.size, BG)                   # ③ BG = 该图容器的背景色
flat.paste(im, (0, 0), im)                             # ④ 用 alpha 当蒙版贴上去
flat.save(out, quality=90, optimize=True, progressive=True)
```

**前提(必须成立)**:拍平用的底色 **== 正文里该图容器的背景色**。
夜色段拍 `(14,28,46)`,宣纸段拍 `(251,246,233)`,与设计令牌严格同源。
效果:无缝、无任何色带、体积比减色 PNG 更小(**实测 17 MB → 340 KB**)。

### 6.2 ⚠️ alpha bbox 裁完就**不要**再裁百分比

`im.crop(im.getchannel("A").getbbox())` 之后图片已**没有多余留白**,
**任何后续百分比裁切都是破坏性的**。

实测:某张图先按 alpha bbox 裁成 1987×1691(比例 1.18),**又裁了上下各 10%**
→ 1352(比例 1.47),等于直接切进画面主体,用户一眼看出"兔子的头顶被切了"。
要调构图比例,**回到原始 PNG 上重新决定裁切框**,不要两级裁切叠加。

### 6.3 实拍图与设计底色的统一(轻微暖调即可)

色度 ×0.93、叠加暖色 `(216,178,120)` 7.5%、对比 ×1.035、亮度 ×1.012 —— 仍是自然照。

### 6.4 图床外链:给「用户自己上传的图」留一个优先通道

用户常因"往微信素材库里插某张图太麻烦"而把图挂到自己的图床/CDN。
**不要为这种情况改模板**,在生成器里加一层「外链优先」:

```python
URLS = json.load(open("urls.json", encoding="utf-8")) if os.path.exists("urls.json") else {}

def asset(key, mode="base64"):
    if URLS.get(key):            # 配了外链 → 无论哪种 mode 都走外链
        return URLS[key]
    ...                          # 否则按原逻辑 base64 / 相对路径
```

- **一处配置全链路生效**(成稿 / 轻量版 / 预览器),粘贴时不用再插这张图;
- **自动回退**:删掉登记就恢复本地图;
- **素材同步要跳过外链图**,否则交付目录会堆一批没人引用的文件。

⚠️ 验收**不能只看"链接可达"**(`curl` 返回 200 不够),要用浏览器实测 `naturalWidth > 0`。
⚠️ 顺带提醒用户两件他们想不到的事:
1. **原始 PNG 往往很大**(实测 1.6 MB / 3.9 MB),移动端首屏会明显变慢
   → 建议压成 JPG(宽 ≤1200、质量 80,各约 150 KB)后重传,换链接只改 `urls.json` 一行;
2. **原始 PNG 带透明外边距**(画布 2000×2000 但内容区只有 1987×1691),
   按 `width:100%` 显示时上下会各留一段透明边。若容器底色与该图原合成底色一致,视觉无缝,只是页面变长。

### 6.5 图床自动化上传(免去在微信编辑器里一张张插图)

**动机**:正文图片原本要在微信编辑器里**逐张手动插入**。改成图床外链后,HTML 里直接写外链,
粘过去即可 —— 但"上传图床 + 拿直链"这一步不该手工做。

**脚本**:`scripts/upload_imgchr.py`(适配 imgchr.com / 路过图床,内核是 **Chevereto**)

```bash
# ① Cookie 路(推荐: 只要浏览器登录过就能用; 无需 API 密钥)
python scripts/upload_imgchr.py out/*.jpg --cookie "PHPSESSID=…; …" \
       --urls-out urls.json --key-prefix p      # 1.jpg → {"p1": "https://…/x.jpg"}

# ② API v1 路(需要账号里的 API 密钥)
python scripts/upload_imgchr.py out/*.jpg --api-key "…"
# 凭证也可放环境变量: IMGCHR_COOKIE / IMGCHR_API_KEY
```

写出的 `urls.json` 正好喂给生成器的「外链优先」通道(见 6.4),形成闭环:
**上传 → 拿直链 → 写 urls.json → 重新生成 → 粘进 135 → 粘进公众号**,全程不用在微信里插图。

**取 cookie**:F12 → Application/Storage → Cookies → `https://imgchr.com` → 复制全部为
`k=v; k=v` 形式(`document.cookie` 取不到 HttpOnly 的,要用 Application 面板)。

**已探明的技术事实**(免得再摸索):

| 项 | 值 |
|---|---|
| 站点内核 | **Chevereto**(`/app/lib/chevereto.min.js`) |
| AJAX 端点 | `POST https://imgchr.com/json` |
| CSRF | 页面里的 `PF.obj.config.auth_token`(未登录首页也有) |
| 上传字段 | `type=image` `action=upload` `auth_token=…` + 文件字段 `source` |
| API v1 端点 | `POST https://imgchr.com/api/1/upload`,参数 `key=<密钥>`,字段 `source` |
| 直链位置 | 响应 JSON 的 `image.image.url`(退化为 `image.url` 查看页) |
| **踩坑** | cookie 里的 `PHPSESSID` 一旦无效,服务端**不返回页面**,只吐一行纯文本 `G: Sessions are not working on this server (session_start).`(整页仅 60 字节)。脚本已把这条做成自诊断提示 |

> ⚠️ **隐私提醒(必须告知用户)**:图床是**公开的** —— 拿到直链的人都能看图。
> 公司活动照片(含人脸)放公网图床等于对外公开发布。
> 若在意,用**自家已备案域名 / CDN** 更稳妥(本项目开场 Logo 与两张贴图就在 `bee-reg-ab.imagency.cn`)。

---

## §七 订阅号封面(不是正文,单独一套规矩)

公众号封面是**后台上传的静态图**,和正文完全分开。

| 项 | 要求 |
|---|---|
| 尺寸 | 大图 `900×383`(2.35:1) / 小图 `383×383`(1:1) / 二合一 `1283×383` |
| 动画 | **必须静态** —— 封面不可能播动画,动画还会让截图停到随机相位 |
| 字体 | 大字标题用**衬线/楷体**(看气质),小字信息用**无衬线**(看可读性) |
| 主次 | **文案是主、画面是次**:背景元素统一压暗(整体 `DIM≈0.58`),标题加纯色底衬 |
| 1:1 小图 | 文案**整体垂直居中**(列表里显示极小,不该为画面让位) |

**「静态封面」不必重画** —— 复用同一套组件,导出前统一删掉 SMIL:

```python
def strip_anim(svg):
    return re.sub(r'<(?:animate|animateTransform|set)\b[^>]*>', '', svg)
# 导出前断言残留为 0
assert not re.search(r"<(?:animate|animateTransform|set)\b", html)
```
前提是 §一·3 的静默降级原则。实测只有两类组件删完会"消失",封面里避开或换静态画法:
- `scroll_line` / `ruyi_line`(金线的 `<rect width="0">` + 动画展开)→ 删完线宽 0
  → **改用静态 `<rect>` + 旋转 45° 的菱形**;
- `ripples`(`opacity="0"` 起手)→ 纯装饰,消失无妨。

**导出必须做尺寸校正**:`locator().screenshot()` 截 383×383 的元素,在
`deviceScaleFactor: 2` 下**会输出 768 行而不是 766 行**,多出的一行取到**页面底色**,
在深色封面底部留下一条 1px 亮边(实测该行亮度 229,画面本体只有 6–21)。

```python
want = (lw * 2, lh * 2)
if im.size != want: im.crop((0, 0, *want)).save(p, optimize=True)
# 边缘校验: 末行/末列平均亮度, 深色封面应 < 20
```

---

## §八 135 编辑器中转法(实测推荐的发布路径)

### 8.1 为什么要中转

用户实测(**2026-09-22 本项目真实反馈**):

| 发布路径 | 还原度 |
|---|---|
| **① 本地 HTML → 135 编辑器 → 从 135「复制使用」→ 粘进公众号** | **98%+**(最佳) |
| ② 本地 HTML → 秀米(粘贴/上传) → 公众号 | 明显差 |
| ③ 本地 HTML → 直接粘进公众号 | 明显差 |

原因(已从 135 的前端代码读出来,见 8.2/8.3):
**135 的复制链路不是"过滤器"而是"规范化器"** —— 它把 HTML 收进自己的编辑区后,
在复制时做一次「补元数据 + 结构规整」,输出的是一份**已被它验证过能在公众号里活下来**的 HTML。
所以走一趟 135,等于让 135 替你做了一次"公众号兼容化"。

### 8.2 135 的结构(从 `editor_styles` 模板页 + 前端脚本读出)

9 条硬事实:

1. 底层编辑器 = **百度 UEditor**(`/js/ueditor/…`),编辑区是 `iframe` 里的 `contenteditable`。
2. 根容器:`<section data-role="outer" class="article135" style="…background-color…">`
3. 区块:`<section class="_135editor" data-id="…">` —— 135 的每块内容
4. 文字:`<span class="135brush" data-brushtype="text" style="font-size:1.75em;color:#f49696;">`
   —— 字号体系**以父级 `font-size:16px` 为基准用 `em`**
5. 图片:`<img src="…" width="93" data-width="93px" data-ratio="1.1702" data-w="611" draggable="false" style="width:93px;…">`
   —— `data-w`=原图宽、`data-ratio`=**高/宽**、`width`/`data-width`=显示宽;
   这是它「图片自适应秒刷」的元数据。⚠️ **我们自己不要手写这几个属性** ——
   135 可能会据此把图片改成固定 px 宽,反而破坏 `width:100%` 的自适应。
6. 自由布局(它家的 SVG 玩法):
   `data-role="absolute-layout" data-mode="svg" data-width/height/ratio` → 内含
   `data-role="ratio"`(空 SVG 撑高) + 多个 `data-role="block"`(百分比 margin 定位) →
   每块内嵌 `<svg viewbox="…">` → `<foreignObject data-role="block-content">` → 里面才是正常流内容
   (`section[data-role="paragraph"]` → `p` → `span.135brush`)
7. 横滑/轮播:`<section data-role="animate" dir="rtl" style="overflow-x:auto">` + 内部 `width:300%`
   + flex 子项 `width:33.33%`(注意:它的 `data-role="animate"` 指的是**横向滑动**,不是动画)
8. 镜像/翻转:`<section data-role="scale-fix" style="transform:rotateY(180deg);transform-origin:center center">`
9. **它自己的模板里 `<animate>` / `<animateTransform>` 出现 0 次** —— 135 原生动效不靠 SMIL
   (靠 GIF、横滑、以及它 SVG 编辑器的私有机制;其官方文档明说 SVG 动效需「保存同步」或插件才能到微信)

`data-role` 全集(实测):`outer` `absolute-layout` `ratio` `block` `block-content` `scale-fix`
`target` `title` `paragraph` `animate`

### 8.3 135 复制时到底做什么(读 `copy_editor_content.js`)

```js
editorHtml = getEditorHtml();                       // ← 关键: 拿的是规范化后的 HTML, 不是我们粘进去的原文
document.addEventListener("copy", function (event) {
  event.clipboardData.setData("text/html", editorHtml);
  event.preventDefault();
});
document.execCommand("copy");
// 失败则降级: 把规范化 HTML 写回编辑区 → 全选 → execCommand("copy")
```

- `getEditorHtml()` 内部先 `clean_135helper()`(清自己的辅助节点)、规整空 `<p>`(转 `<br/>`),
  最后返回 **`parse135EditorHtml(html)`** 的结果。
- **`parse135EditorHtml()` 是「遍历 DOM 补元数据」**(给图片补 `width`/`data-w`/`data-ratio` 等),
  **不是白名单清洗** —— 代码里看不到任何"按标签/属性黑名单删除"的逻辑。
  → 这就是"走一趟 135 还原度高"的根本原因:**它补全,不删减**。
- 复制后它会检测内容里有没有 `svg` / `section[data-tplid]` / `linear-gradient`,
  命中则弹「公众号兼容性」提示 —— 反过来说,**含 `<svg>` 的内容走的是 135 的特殊处理分支**。
- 另一条独立证据:135 的字符串表里有一条
  `"animatetransform,animate,animatemotion"`(正是 SMIL 三件套),挂在它的「规则」字段
  (`r_paragraph` / `r_separator`)上 —— **它明确知道并单独处理 SMIL**,不是当陌生标签丢掉。

### 8.4 结论与做法

**结论:不需要为了 135 改生成器。** 我们输出的"干净内联样式 + `<section>` 嵌套 + 内联 SVG/SMIL",
正好落在 135 愿意接受、且微信能存活的交集里。**要改的是发布流程,不是产物。**

```
① 本地打开 _预览.html → 选品牌 → 点「复制当前品牌成稿到公众号」
② 粘进 135 编辑器的**编辑区**(不是源码模式,直接粘)
③ 在 135 里肉眼过一遍(排版有无错位)
④ 点 135 右侧「复制使用」→ 回公众号编辑器 Ctrl+V
⑤ 在公众号里补充上传正文配图(= 1.jpg~10.jpg;135 不会替你上传图片)
⑥ **用手机预览**确认动效还在
```

**✅ SMIL 动画能过 135 —— 已由用户实测确认(2026-09-22)。**
所以**全程走 135 中转即可**,既拿到 98%+ 的排版还原度,动画也不用另外补。

```
① 本地打开 _预览.html → 选品牌 → 点「复制当前品牌成稿到公众号」
② 粘进 135 编辑器的**编辑区**(不是源码模式,直接粘)
③ 在 135 里肉眼过一遍(排版有无错位)
④ 点 135 右侧「复制使用」→ 回公众号编辑器 Ctrl+V
⑤ 在公众号里补充上传正文配图(= 1.jpg~10.jpg;135 不会替你上传图片)
⑥ **用手机预览**确认一遍(排版 + 动效)
```

> 兜底(万一某次不灵):**排版仍走 135 中转,动画用 F12 补** ——
> 在公众号编辑器按 F12 → 右键对应节点 → 「Edit as HTML」→ 把该 `<svg>…</svg>` 整段粘进去 → 关闭工具。

**中转时注意 3 件事**:

1. **图片仍需自己上传**(135 不代传);`data:` 内嵌图会被过滤 → 所以「轻量版 + 图床外链」组合最顺。
2. **不要在 135 里继续编辑文字** —— 135 会给文字套 `.135brush`、可能把字号改写成 `em`,
   改多了引入噪音。要改就回本地改 → 重新生成 → 重新粘。
3. **不要用 135 的「保存同步」代替复制** —— 对普通图文没有额外收益,还会引入它自己的模板结构。

### 8.4bis 素材库图床硬约束 + 两条备份通道(2026-09 联网核对补充)

**硬约束:SVG 内 `<image>` / 外层 `<img>` 的 `src` 最终必须是微信素材库(mmbiz.qq.com)链接。**
外链与 Base64 在公众号正文里**不显示**。第三方图床(imgchr 等,§6.5)只服务于**生成阶段**的预览与传递,
发布链路的最后一公里永远是:在公众号后台/135 里重新上传图片,让它落地为素材库链接。

**两条备份通道**(135 中转万一不灵时;两者对**动态 SMIL** 的存活率都还没有公开实证,走前必须真机验证):

- **A · 剪贴板直贴后台**:生成 `text/html` 富文本直接 Ctrl+V 进 mp.weixin.qq.com 编辑器。
  doocs/md 对**静态 SVG** 已实证存活(需先做 marker 展开/显式定宽,见下);动态 SMIL 未实证。
- **B · 官方草稿箱 API**(`POST /cgi-bin/draft/add`,需已认证公众号 + access_token):
  可传图建草稿;是否原样保留内联 SVG+SMIL 未实证。

**静态 SVG 直贴的三坑与修法**(doocs/md 实证,做图表/示意图直贴时先处理):

| 坑 | 真因 | 修法 |
|---|---|---|
| 箭头/标记消失 | `defs`+`marker`+`url(#id)` 引用被滤(`id` 全剥离的连锁) | marker 展开为**内联 `path`/`polygon`** |
| 图表过大 | 根节点 `width="100%"` 失效,按 viewBox 1:1 渲染 | 显式像素宽,**≤677px**,保留 `viewBox` |
| 文字错位 | `<foreignObject>` 兼容差 | 文字一律 `text`/`tspan`,或放外层 HTML section |

**真机验收矩阵(最低 4 格)**:iOS WKWebView / Android XWeb 新机型 / Android X5 老机型 / PC 微信。
每格只验三件事:**动画是否播放、点击是否触发、静止态是否等于终态**。
在拿到属性级端差实证之前,不向用户承诺端级差异细节,一律用「静态终态兜底」收口。

### 8.5 135 关键结构速查(需要手写 135 原生片段时用)

```html
<section data-role="outer" class="article135" style="background-color:#FBF6E9;box-sizing:border-box;">
  <section class="_135editor">
    <section data-role="paragraph" style="overflow:hidden;">
      <p style="margin:0 0 15px;">
        <span style="font-size:17.5px;color:#2A2620;" class="135brush" data-brushtype="text">文字</span>
      </p>
    </section>
    <img src="…" style="width:100%;max-width:100%;display:block;margin:0 auto;" />
  </section>
</section>
```

> 常规任务**不需要手写 135 结构** —— 我们的产物直接粘进 135 就会被它规范化成这套。

---

## §九 交付物与目录约定

落盘到 `…/秀米文章合集/<YYYY-MM-DD>/`:

```
1-<品牌A>-<标题>-<日期>.html            自包含成稿(图片内嵌 base64, 用于本地预览/一键复制)
1-<品牌B>-<标题>-<日期>.html
粘贴版-<品牌A>-<标题>-<日期>（轻量）.html  图片走同级相对路径, 粘编辑器用(内嵌版 2MB+ 太重)
粘贴版-<品牌B>-…html
_预览.html                             品牌切换 + 一键复制成稿(仅预览壳, 不粘进微信)
1.jpg ~ N.jpg                          压缩后的上传图, 顺序 = 正文出现顺序
封面大图-…-900x383.png / 封面小图-…-383x383.png / 双封面二合一-…-1283x383.png
发布说明.md                             交付物 + 技术说明 + 事实来源表 + 发布步骤 + 质检 + 待确认
配图对照表.md                           序号 / 位置 / 画面 / 原文件名
_旧版-<风格>-v1/                        旧风格整套归档(换风格时整包移进来, 不要覆盖)
```

### 两个必做的收尾

**① 轻量版的相对路径图必须真的同级存在**
```python
# 构建时同步素材(不要构建后手工复制)
for fn in DECO.values():
    if URLS.get(key): continue                 # 外链图不落地
    shutil.copy2(os.path.join(DECO_DIR, fn), os.path.join(OUT_DIR, fn))
for i in range(1, N+1):
    shutil.copy2(os.path.join(IMG_DIR, f"p{i}.jpg"), os.path.join(OUT_DIR, f"{i}.jpg"))
# 报告交付目录里已不再被引用的图, 提示清理
```

**② 路径模式的命名映射要写在生成器里,不要靠事后打补丁**
实测教训:第一轮用"构建完再 `re.sub` 改 HTML 里的文件名"的补丁法,
**下一次重新构建时补丁被覆盖,轻量版 10 张照片全变断图**。
正确做法是在 `asset()` 里分两个映射:
```python
PHOTO_SRC = {f"p{i}": f"p{i}.jpg" for i in range(1, 11)}   # 工程内文件名(读文件)
PHOTO_OUT = {f"p{i}": f"{i}.jpg"   for i in range(1, 11)}   # 交付目录名(写 src)
```
> 推广:**凡是"构建产物"里出现的路径/文件名,都要由构建脚本决定,而不是构建后手工修。**

---

## §十 机检门禁

```bash
S="<skill 目录>/scripts"
PY=<python>

# ① 结构/白名单门禁: 白名单 / 禁用标签 / id / url(#) / 被剥离 CSS / 标签配平 / span leaf
#    / animateTransform 覆盖静态 transform / 长正文段落误用衬线 / 过大固定 px 宽
$PY $S/check_wechat_svg.py "…/秀米文章合集/2026-09-22" --exclude "_旧版"
# 退出码 0 = 可交付; 1 = 有 FATAL, 禁止交付

# ② 窄屏门禁: 手机端横向溢出(桌面看不出来, 必须压到 320px)
$PY $S/check_mobile_width.py "…/秀米文章合集/2026-09-22" --exclude "_旧版" \
    --widths 300,320,360,375,414
# 退出码 1 = 存在横向溢出; 会精确报出 越界px / 元素 / style

# ③ 图床(可选): 上传图片拿直链, 并写成 urls.json 供生成器优先取外链
$PY $S/upload_imgchr.py out/*.jpg --cookie "…" --urls-out urls.json --key-prefix p
```

三个脚本各管一件事, **前两个都要过**:
`check_wechat_svg.py` 管「微信会不会把动画/样式灭掉」,
`check_mobile_width.py` 管「手机上会不会顶出屏幕右边」,
`upload_imgchr.py` 管「图片不用再手动插进微信编辑器」。

行为说明:

- **默认只检「会被粘进公众号的正文根节点」**(含 `max-width:677px` 的最外层 `<section>`,
  按嵌套深度取匹配收尾)。本地预览壳里的 `<style>`/`<script>`/`id` 不会被粘进编辑器,
  所以默认忽略;要连壳一起检加 `--strict`。
- `--json` 给机器读;`--quiet` 只打结论;`--exclude <子串>` 跳过归档目录。
- 报了 `animateTransform 覆盖静态 transform`、`url(#…)`、`<linearGradient>` 这三类
  **必须改**,它们不是风格问题而是"一定失效"。

---

## §十一 交付前自检清单

**机检(零 token,必跑)**
- [ ] `check_wechat_svg.py` **0 FATAL**
- [ ] `check_mobile_width.py` **各宽度 0 横向溢出**(尤其 **320px**)
- [ ] 浏览器实测轻量版 `naturalWidth===0` 的数量为 **0**
- [ ] 封面尺寸精确到 `逻辑×2`,末行/末列亮度 <20(无 1px 亮边)
- [ ] 图床外链浏览器实测 `naturalWidth > 0`(不只看链接是否 200)

**规范**
- [ ] 全内联样式;零 `<style>`/`<script>`/`id`;每个文字节点都包 `<span leaf="">`
- [ ] 无 `*Gradient` / `filter` / `clipPath` / `mask` / `<use>`
- [ ] 每个 `<svg>` 都有 `viewBox`;`<img>` 都带 `max-width:100%`
- [ ] **正文一律无衬线**(除非用户明确要求);标题/诗词/特殊文字/排版才可用衬线
- [ ] 层级:主标题 ÷ 章节标题 ≥2×、÷ 正文 ≥3×;首屏附属信息字号 > 正文
- [ ] **格内元素没有写死的 px 宽**(用 `width:100%;max-width:Npx`);表格单元格带 `width="N%"` 属性

**动效**
- [ ] 每个动画元素通过「静态降级」:删掉全部 `animate*` 后画面仍是完整海报
- [ ] 无"动画化的 `<g>` 直接带静态 transform"(会被覆盖到原点)
- [ ] 全篇同类主体元素只出现一次(如月亮)
- [ ] 顶部前摇(开头→首段正文)≤ 整页 8%
- [ ] 画面里的数量与正文一致(如"六颗骰子"→ 正好 6 颗),**用 DOM 计数核对**

**内容与素材**
- [ ] 篇幅配比符合约定(`report_ratio()` 自动打印,统计时排除 `<table>`)
- [ ] 透明 PNG 全部按目标底色拍平存 JPG;**没有**在 alpha bbox 之后叠百分比裁切
- [ ] 事实性内容(节令/民俗/政策)逐条有官方来源,写进「发布说明」的来源表
- [ ] 用户给的现场细节**逐字采用,不编造数字**;不确定的写进「待确认」
- [ ] 装饰/贴图的版权来源已注明并提醒用户确认商用授权

---

## §十二 参考来源(2026-09-22 联网核对)

- **白名单规范转述(业内通行)**:zer0n(计育韬/JZ Creative)《微信图文范畴内 SVG AttributeName 白名单规范》
  <https://zer0n.cn/archives/wechatsvg>(2020-02 首发,2024-11 最后修改);同站「高级排版」系列
  <https://zer0n.cn/archives/> 有位移动画/擦除动画/缩放器分篇实操。
- **doocs/md**(13k+ star,2026-09 仍极活跃)Markdown→公众号 HTML,仓库自带
  wechat-svg skill(SKILL.md + core-principles 原理篇,位于其 `.agents/skills/wechat-svg/`):
  交互三件套 `begin="click"`+`fill="freeze"`+`restart="never"`、无 id 冒泡编组、
  `WECHAT_MAX_WIDTH_PX = 677`、marker 展开降级(`apps/web/src/services/export/wechat-svg.ts`);
  静态 SVG 直贴三坑实证见其 PR #1724 与 issues #1730/#1914。<https://github.com/doocs/md>
- **HTML/CSS 支持概览**(Axton Liu,2025-03,综合转引多篇实证帖):
  `position` 整段被删、`id` 全剥、SVG 内 `<image>` 仅认 mmbiz 素材库链,
  <https://www.axtonliu.ai/newsletters/ai-2/posts/wechat-article-html-css-support>
- **官方文档**:草稿箱 API <https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html>;
  135 编辑器 SVG 教程 <https://www.135editor.com>
- **同类轮子**(对照参考):lyricat/wechat-format(4.5k★,停更,「ul/ol 被重置→文末参考文献索引」的解法仍有效)、
  mdnice/markdown-nice(停更)、jaywcjlove/wxmp、laogou717/md-wechat;
  Skill 类:gzh-design-skill(含 validate_gzh_html.py 合规校验思路)。
- **未找到实证、留待自测的项**:动态 SMIL 经「剪贴板直贴 / 草稿 API」的存活率;
  `stroke-dasharray` 与 `mpath` 经编辑器链路的实际存活;SMIL 属性级 iOS/Android 差异。
  以上任何一项做过的实测结果,都应回填进 §3.1 坑清单或 §8.4bis。
