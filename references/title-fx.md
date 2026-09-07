# 标题设计手法库(多重描边 · 剪切蒙版 · 模糊 · 重组)

> 来源:MDN / CSS-Tricks / web.dev / 优设-错位排版等方法论,按「海报导出」语境整理。
> 与 effects.md 的关系:effects 是通用特效配方;本册专攻**标题的字形级处理**。
> 所有手法默认给标题加 `data-text="<标题全文>"` 属性(伪元素复制层需要)。

---

## 一、多重描边(综艺字/贴纸字/国潮细圈)

### 单层最优解:`paint-order: stroke fill`
默认 stroke 画在填充上且以轮廓为中心线,粗描边会"吃掉"字身;`paint-order` 让描边垫底:

```css
.t1 { -webkit-text-stroke: 8px #e63946; paint-order: stroke fill; color: #fff; }
```

### 双/三描边:伪元素叠层(attr 复制,粗的垫底)
```css
.t2 { position:relative; color:#fff; z-index:1; }
.t2::before { content:attr(data-text); position:absolute; left:0; top:0; z-index:-1;
  -webkit-text-stroke:12px #1d3557; }      /* 中圈 */
.t2::after  { content:attr(data-text); position:absolute; left:0; top:0; z-index:-2;
  -webkit-text-stroke:20px #f1faee; }      /* 最外圈 */
```

【硬】**中文细体禁用粗 stroke**(不打 paint-order 会打断笔画);多层伪元素行高必须完全一致。
兜底:8/16 方向 0 模糊 text-shadow(拐角圆润,只做细圈)。

## 二、剪切蒙版(background-clip: text 进阶)

三件套:`background-image` + `background-clip:text` + `-webkit-text-fill-color:transparent`,
并保留实色 `color` 兜底。

- **图片字**(标题内露出照片,电影感):`background:url(img/x.jpg) center/cover;`
- **金属/立体渐变字**:`linear-gradient(180deg,#fff 30%,#91a9cb 70%)`
- **双色拼接**(对抗/分屏主题):硬停靠 `linear-gradient(90deg,#fa0 50%,#08f 50%)`

【硬】**透明填充字禁用 text-shadow**(阴影从字底透出毁掉渐变)——阴影放 `z-index:-1` 伪元素层,或改 `filter: drop-shadow()`(作用于裁切后可见像素,结果正确)。
【硬】与描边同用时,描边画在渐变上面;要描边垫底就分层。

## 三、模糊类

- **光晕模糊字**:复制层 `filter:blur(14px)` + 高饱和色垫底,清晰层叠上(氛围感 KV):
  `.glow::before { content:attr(data-text); position:absolute; inset:0; z-index:-1; filter:blur(14px); color:#ff2d95; }`
- **下拉模糊投影**:`text-shadow:0 12px 28px rgba(0,0,0,.35)`;异形/透明字用 `filter:drop-shadow(...)`。
- 【硬】**毛玻璃标题条 backdrop-filter 在旧无头/截图管线不渲染**(Chromium bug 40895818)——导出场景一律用「预模糊背景图 + 半透明色块」替代,禁用 backdrop-filter。

## 四、重组/拆分(黄海式错位)

逐字 `<span>` 化(必须 `display:inline-block`,transform 对行内元素无效):

```css
h1 span { display:inline-block; }
h1 span:nth-child(odd) { transform:translateY(-.12em); }
h1 span:nth-child(3)   { font-size:1.3em; transform:rotate(6deg); color:var(--c-accent); }
```

- **错位纪律**:单字位移控制在**字高 10%–20%**,过大松散;配合个别字换色/旋转/字号差造节奏。
- **重复残影**:伪元素复制层同向偏移 .06em + 描边(残影),静态写死偏移,不依赖动画。

## 五、其他标题手法速查

| 手法 | 要点 | 坑 |
|---|---|---|
| 挤压变形 | 逐字 `transform:scale(.82,1.18)`;或选窄体字 | 整行统一 scale 横向露缝 |
| 字重混排 | 个别字 `font-weight:900; font-size:1.2em` | 中文字体混排=加载多文件,等全部加载完再导 |
| 双色拼接 | clip-path 叠反色层,或硬停靠渐变字 | PDF 导出需 `print-color-adjust:exact` |
| 背景色块压字 | 行内色块 `padding:.1em .3em` + `-webkit-box-decoration-break:clone` | 色块间距用 line-height 调 |

## 六、导出安全总则(无头截图)

1. **禁 backdrop-filter**(不渲染),改预模糊图+色块;
2. **透明填充字禁 text-shadow**,一律 drop-shadow 或伪元素分层;
3. glitch/flicker 类:把"抖动瞬间"**写死为默认态**(伪元素直接给偏移与 clip-path,不写动画);
4. PDF/打印需 `print-color-adjust:exact`;
5. RGB 分离偏移 ≤3–4px,超过糊成重影。

> 具体特效配方(下拉投影/荧光/渐变投影/轮廓/背景块/描边/镂空/霓虹/故障)见 effects.md「文字特效」节。
