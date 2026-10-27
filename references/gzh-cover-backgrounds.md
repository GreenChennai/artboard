# 品类扩展 · 双封面背景体系(CSS / 内联 SVG / 生图 三层)

> 状态(v1.26.2 更新):**L1 八个 CSS 配方已全部落地**(`new --bg-recipe`:kraft-paper / gingham / dots-grid / tear / ticket / window / rays / curtain);**L3 照片层也已接进 CLI**(`new --bg-image` + `bg-prompt` / `bg-attach`,无字照片直挂、2.6MB 上限、Pillow 解码);L2 内联 SVG 仍按 §2 规范手工落,未做成开关。
> 三层的机器口径:`--bg-recipe`(CSS 配方)与 `--bg-image`(照片层)互斥,同传报 `BAD_BG_COMBO`;配方又与 shader 底材互斥,`--fx auto` 时 shader 让位。机检 `bg-recipe-known / bg-layer-budget / bg-text-safe / bg-offline` 已随 `check` 生效。
> 适用:`scripts/gzh_cover.py` 六族与 `gzh_article.py --cover-*`。
> 起因:18 张参考的背景**全部有内容**(网点、格纹、撕纸、票券、插画、照片、光斑),而现行模板只有 `linear-gradient(135deg, --c-bg, --c-bg2)` 一层底。
> 本册只回答一件事:**这些背景用什么做、怎么做、做到什么程度算合格**。

---

## 0. 三层策略(先尽力用 CSS,生图是补丁不是默认)

| 层 | 手段 | 能覆盖参考里的什么 | 体积 | 可复现 | 优先级 |
|---|---|---|---|---|---|
| **L1 CSS** | 渐变/`repeating-linear-gradient`/`radial-gradient`/`conic-gradient`/`clip-path`/伪元素/`mix-blend-mode` | 网点、格纹、纸纹、斑驳、撕纸边、票券齿孔、圆点窗框、放射光、幕布波浪、色带与破版 | 0 字节(纯 CSS) | 是(逐字节可复现) | **默认** |
| **L2 内联 SVG** | 手写 `<svg>` path,颜色走主题 token | 云、山、星、音符、相机、牡丹、胶带、箭头、圆点人物剪影等**扁平插画** | 1–8 KB/张 | 是 | **次选** |
| **L3 生图** | 图像模型出**无文字**背景图 | 照片感实景、复杂手绘场景、真实材质(面包/山景/红军剪影) | 0.4–1.5 MB/张 | 否(同提示词也会变) | **仅当 L1/L2 做不到** |

判断顺序固定:**先问 CSS 能不能做 → 再问内联 SVG 能不能画 → 最后才生图**。理由是 CSS/SVG 零依赖、可回归、不引入模型不确定性;生图的唯一优势是"真实材质与复杂场景"。

18 张参考的可达性实测(按此顺序估):

| 手法 | 参考 | L1 CSS | L2 SVG | 结论 |
|---|---|---|---|---|
| 网点/半调 | #6 | ✅ | — | CSS |
| 格纹(餐布) | #13 | ✅ | — | CSS |
| 纸纹/斑驳(牛皮纸) | #11 #16 #18 | ✅ | — | CSS |
| 撕纸边+白描边 | #13 | ✅ | — | CSS |
| 票券齿孔+内框 | #5 | ✅ | — | CSS |
| 浏览器窗圆点栏 | #3 | ✅ | — | CSS |
| 放射光+光斑 | #8 #17 | ✅ | — | CSS |
| 幕布波浪色带 | #7 #9 | ✅(单色相多明度) | 更稳 | CSS 优先,SVG 兜底 |
| 扁平插画(人/物/景) | #4 #10 #14 | ❌ | ✅ | SVG |
| 手绘花鸟/笔刷 | #16 | ❌ | 难 | CSS 打底 + SVG 主图形 |
| 照片/实景/剪影 | #2 #15 #18 | ❌ | ❌ | **生图或素材** |
| 3D 玩偶 | #3 | ❌ | ❌ | 生图或素材 |

结论:**L1+L2 能覆盖 18 张里约 14 张的背景语言**;剩下的照片感/3D 才需要生图。所以"方案一不行才生图"不是退路,而是主路 + 补丁。

---

## 1. CSS 配方(8 个,已实现为 `--bg-recipe` 开关)

> 通用约定:颜色一律走主题 token;每个配方只增加**一层**(`::before` 或 `::after`),`pointer-events:none`,`z-index` 在内容层之下;
> **禁用**紫/蓝紫渐变(`purple-gradient`)与蓝→青双停靠(`trust-gradient`),这是 `check_slop.py` 的 P0,不是建议。

### 1.1 网点 / 半调(参考 #6 · 已实现:dots-grid)

```css
.bg-dots::before {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background-color: var(--c-bg);
  background-image: radial-gradient(circle at 50% 50%,
    rgba(20, 26, 38, .13) 1.1px, transparent 1.4px);
  background-size: 6px 6px;
}
```

- 变体:`background-size: 9px 9px` 更疏;换 `--c-primary` 做彩色网点;
- 网点只做**底纹**,浓度 ≤15%(超过就成脏灰);
- 参考 #6 把网点压在蓝底上并让插画遮住中段——网点必须能被主体图形打断,不要满铺到边。

### 1.2 格纹 gingham(参考 #13 · 已实现:gingham)

```css
.bg-gingham::before {
  content: ""; position: absolute; inset: 0; pointer-events: none; opacity: .55;
  background-color: #f6f1e4;
  background-image:
    repeating-linear-gradient(90deg, rgba(232, 196, 74, .55) 0 12px, transparent 12px 24px),
    repeating-linear-gradient(0deg,  rgba(232, 196, 74, .55) 0 12px, transparent 12px 24px);
  background-blend-mode: multiply;
}
```

- 两轴同色叠 `multiply` 得到"深浅交叉格",这是餐布感的关键;单轴只是条纹;
- 格子尺寸 18–26px;小于 14px 在手机上糊成纯色。

### 1.3 纸纹 / 斑驳(参考 #11 #16 #18 · 已实现:kraft-paper)

```css
.bg-kraft::before {
  content: ""; position: absolute; inset: 0; pointer-events: none; opacity: .5;
  background-color: #ded0b4;
  background-image:
    radial-gradient(ellipse 40% 60% at 18% 30%, rgba(120, 92, 48, .18), transparent 70%),
    radial-gradient(ellipse 50% 40% at 82% 76%, rgba(120, 92, 48, .14), transparent 72%),
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)' opacity='.30'/%3E%3C/svg%3E");
}
```

- 纸纹 = 底色 + 2 处大斑 + 一层细颗粒;三层缺一层就"塑料感";
- 颗粒 `opacity` 0.22–0.32,超过 0.4 在深色主题上会出彩噪;
- 这条 data URI 是**内联资源**,`gzh_cover.py` 的 offline 审计只拦 `http(s)`/协议相对,data: 不拦;实施前用一张测试封面跑一次 `check` 确认。

### 1.4 撕纸边 + 白描边(参考 #13 · 已实现:tear)

```css
.bg-torn::before {
  content: ""; position: absolute; inset: 3% 2%; pointer-events: none;
  background: var(--c-surface);
  clip-path: polygon(0% 12%, 4% 4%, 12% 9%, 22% 2%, 34% 7%, 46% 1%, 58% 6%, 70% 2%,
                    82% 8%, 92% 3%, 100% 10%, 99% 88%, 91% 96%, 80% 91%, 68% 97%,
                    55% 92%, 43% 98%, 31% 93%, 19% 97%, 8% 92%, 1% 96%);
  filter: drop-shadow(0 2px 0 #fff) drop-shadow(0 4px 6px rgba(0, 0, 0, .12));
}
```

- 锯齿点 10–14 个,间距不均才有手撕感(等距是"锯齿边框");
- 白描边用 `drop-shadow(0 2px 0 #fff)` 逐层叠,不要 `border`(描边会跟着锯齿走直线);
- `filter` 只作用在装饰伪元素上,`gzh_cover.py` 的标题可见性策略只拦"给标题/祖先加隐藏类属性",不拦装饰模糊;
- 参考 #13 的撕纸框内含 4 字巨标:撕纸框必须比标题外接盒 **≥16px**,否则锯齿切字。

### 1.5 票券齿孔 + 内框(参考 #5 · 已实现:ticket)

```css
.bg-ticket::before {
  content: ""; position: absolute; inset: 6% 5%; pointer-events: none;
  background: #fff;
  -webkit-mask:
    radial-gradient(circle 7px at 50% 0,   transparent 98%, #000) top / 22px 14px repeat-x,
    radial-gradient(circle 7px at 50% 100%, transparent 98%, #000) bottom / 22px 14px repeat-x,
    linear-gradient(#000 0 0) center / 100% calc(100% - 12px) no-repeat;
  -webkit-mask-composite: source-in;
  mask-composite: intersect;
  box-shadow: 0 18px 40px rgba(20, 30, 60, .16);
}
```

- 齿孔只做上下两条(左右打孔会切到票面文字);
- 票面必须留白 ≥ 12%,参考 #5 的白卡占用率约 78%。

### 1.6 浏览器窗(参考 #3 · 已实现:window)

```css
.bg-window::before {
  content: ""; position: absolute; inset: 8% 4%; pointer-events: none;
  background: #fff; border-radius: 10px;
  box-shadow: 0 20px 50px rgba(20, 30, 60, .18);
}
.bg-window::after {
  content: ""; position: absolute; left: 6.4%; right: 6.4%; top: 11.2%; height: 4.6%;
  pointer-events: none;
  background:
    radial-gradient(circle 6px at 12px 50%, #cfe0f7 98%, transparent) 0 0/26px 100% repeat-x;
  border-bottom: 1px solid rgba(20, 30, 60, .08);
}
```

- 窗口 = 白卡 + 顶部圆点栏 + 一条 1px 分隔线,三件齐了才像浏览器;
- 参考 #3 的窗口是**倾斜 0°**、四角圆角 10px,别加 3D 透视。

### 1.7 放射光 + 光斑(参考 #8 #17 · 已实现:rays)

```css
.bg-rays::before {
  content: ""; position: absolute; inset: -20%; pointer-events: none; opacity: .55;
  background:
    conic-gradient(from 200deg at 30% 45%,
      transparent 0 18deg, rgba(255, 255, 255, .55) 18deg 26deg, transparent 26deg 74deg,
      rgba(255, 255, 255, .35) 74deg 84deg, transparent 84deg 360deg);
  filter: blur(2px);
  mix-blend-mode: screen;
}
```

- 光斑用 `radial-gradient(closest-side, rgba(255,255,255,.5), transparent)` 叠 2 处;
- **光只出现在文字之外**;主标区(258–642)必须 `opacity ≤0.25`,否则字被吃掉;
- 禁止"发光字"(文字 `text-shadow` 光晕)——这是现行 §七-7 的禁则,和本条不冲突:光在背景层,不在字形层。

### 1.8 幕布波浪(参考 #7 #9,单色相多明度 · 已实现:curtain)

```css
.bg-curtain::before {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background:
    radial-gradient(120% 80% at 8% 110%, #1b3fa0 0 40%, transparent 62%),
    radial-gradient(90% 70% at 96% 0%,  #4a73d8 0 44%, transparent 66%),
    linear-gradient(160deg, #12306f, #1b3fa0 60%, #2b57bd);
  filter: saturate(1.05);
}
```

- **只用同一色相(蓝)的 3–4 个明度**,不要"蓝→青";`check_slop` 的 `trust-gradient` 判的是双色相停靠,单色相多明度不触发;
- 波浪用 `border-radius: 50% 50% 0 0 / 20% 20% 0 0` 的伪元素叠两层更可控,90% 场合够用。

---

## 2. 内联 SVG 图形层(扁平插画)

规则(与 `components/registry/PIPELINE.md` 的四过滤器一致,补充封面专属):

1. **必须内联 `<svg>`**,不用 `<img>`:封面审计把 `img` 的 `src` 当资源引用校验,内联 SVG 零资源、单文件自包含;
2. 颜色只写 `currentColor` 或 `var(--c-*)`,不写裸 hex(便于换主题);
3. 单图形 ≤8 KB、`viewBox` 归一、禁用 `<filter>`/`<animate>`(渲染慢且审计易误伤);
4. 描边风格统一 1.5–1.75px(与 `assets/icons/` Tabler 同参),填充风格一套封面只用一种;
5. **禁 emoji 当图形**;需要图形就画 SVG 或用素材;
6. 图形只放**边缘/背景层**,主标区内不放细节图形(缩略图会糊成一团)。

建议首批图形(覆盖参考高频元素):`cloud` `hill` `star` `note` `tape` `arrow-doodle` `camera` `peony` `dot-figure` `seal-ring`。存放:`assets/gzh-decor/*.svg`,由模板按需内联,不入 registry(它们是封面专用资产,不是通用组件)。

---

## 3. 生图 / 照片层(仅 L1/L2 做不到时启用;v1.26.2 已进 CLI)

### 3.1 启用判定(三条同时满足才准用生图)

1. 背景必须是**照片/实景/3D/复杂手绘**,CSS 与 SVG 都画不像;
2. 用户**明确允许**或已授权"可调用生图";
3. 有可落地的资产目录与 manifest(见 3.2),否则出图即孤儿文件。

### 3.2 资产规范

```
projects/<slug>/images/bg-<style>@2x.png      # 主封面背景 2.35:1(1800×766 或更大)
projects/<slug>/images/bg-sub-<style>@2x.png  # 次条背景 1:1(766×766 或更大)
projects/<slug>/images/bg-manifest.json       # 见下
```

- 单文件 ≤1.5 MB(PNG)或 ≤600 KB(WebP),导出时由 Kiln 重采样,不要喂 4K 原图;
- 命名只用 ASCII 小写与连字符;每张图必须有 manifest 条目,缺条目 = 未登记资产,`check` 报 `BG_MANIFEST_MISSING`;
- **不覆盖已有素材**(与 `--image` 同一条纪律)。

```json
{
  "bg-<style>": {
    "prompt": "……完整提示词原文……",
    "negative": "text, letters, watermark, logo, signature, ui, frame, border",
    "model": "gpt-image-2", "size": "1536x640", "seed": null,
    "created": "2026-10-27", "license": "自生成(模型条款),可商用/需署名:否",
    "text_free_checked": "2026-10-27 人工目检 3 秒 + 缩略图 15% 复检"
  }
}
```

### 3.3 提示词骨架(所有风格共用)

```
{MEDIUM} background plate for a Chinese WeChat cover, {SUBJECT},
{PALETTE: 2 base colors + 1 accent}, {TEXTURE}, {LIGHT},
composition: subject anchored to the {LEFT|RIGHT|CORNERS},
40–55% calm low-contrast negative space in the {CENTER|LEFT|UPPER} band,
clean paper base, no perspective tricks, {ASPECT} aspect, high resolution, print-like;
NO TEXT: absolutely no letters, no characters, no numbers, no calligraphy,
no captions, no watermark, no logo, no signature, no UI elements, no frame, no border.
```

### 3.4 六套风格模板(对应参考案例)

| 模板 | 参考 | SUBJECT 关键词 | MEDIUM / TEXTURE | PALETTE 建议 |
|---|---|---|---|---|
| `memorial-red` | #2 #12 | mountain range + silhouette figures raising flags, distant pagoda | screen-print poster, flat two-tone, subtle grain | `#a51c19` `#c8372f` + `#f0dcc0` |
| `photo-overlay` | #15 | alpine peak at golden hour, mist valley | editorial photography, 35mm, natural light | warm orange `#c26a35` + deep indigo `#241f36` + cream |
| `flat-illustration` | #4 #10 #14 | running students / clouds and hills / music notes | flat vector, thick 1.5px outlines, no gradients | `#5fa36b` `#e8c44a` + `#2f4f7a` |
| `watercolor` | #16 | peony branch, butterflies, rice-paper grain | traditional Chinese watercolor on xuan paper | `#b08a3e` `#d8cbb0` + `#7f9b86` |
| `kraft-collage` | #11 #18 | bakery interior / city cafe tickets / torn kraft paper edges | hand-cut paper collage, kraft fibers, tape | `#c9ad84` `#7a5c34` + `#f2e7d2` |
| `print-halftone` | #6 | single object or figure, heavy halftone dots | risograph two-ink print, visible dot screen | `#1f4fa8` `#e9eef7` + `#f2b514` |

### 3.5 与文字的隔离(防"文字变模糊像素"的三道闸)

1. **提示词层**:必须包含 `NO TEXT` 全段,并把"低对比留白区"写进 composition——模型很难在留白区编字;
2. **版面层**:背景图之上强制叠一层**安全区压平**(CSS),把文字区的高频细节压掉,任何误生成的字形残影都会被吃掉:

```css
.bg-photo .safe-flatten {
  position: absolute; left: 25.6%; right: 25.6%; top: 0; bottom: 0;  /* 258–642 / 900 */
  background: linear-gradient(180deg, rgba(0,0,0,.10), rgba(0,0,0,.22));
  backdrop-filter: blur(2px);   /* 只在背景层,不作用于文字 */
}
```

3. **验收层**:3 条硬门 ——
   - 缩到 **15% 宽**看 3 秒:若"像有字但读不出",重生成(不是加模糊糊过去);
   - 文字区 100% 裁切放大:出现笔画/字符轮廓即不合格;
   - 记录在 manifest 的 `text_free_checked` 里,写日期与两种复检方式。

### 3.6 后处理纪律

- **不要把文字、标题、色块烧进生图**;生图只交"背景层",所有排版由 `gzh_cover.py` 的 HTML 完成;
- 需要压暗/叠色/裁切,一律用 CSS 层做(`::after` + rgba 渐变 / `object-position`),便于换主题与回归;
- 照片类背景必须保证主标对比度 ≥4.5:1(大字 3:1),不达标就加暗角层,不许改字色硬扛。

---

## 4. 与既有门禁的关系(实施前必须对齐)

| 门禁 | 约束 | 对本册的影响 |
|---|---|---|
| `check_slop.py` P0 | `purple-gradient` / `trust-gradient` / `ai-default-indigo` / `emoji-icon` / `invented-metric` / `filler-copy` | 配方 1.8 只准单色相;所有示例色避开 `#6366f1 #8b5cf6` 等;插画禁 emoji |
| `gzh_cover.py check` `offline-only` | 禁 `http(s)://` 与协议相对 URL | data: URI 与内联 `<svg>` 可用;生图资产用本地相对路径 `images/bg-*.png` |
| `gzh_cover.py check` `title-*` | 标题可见性与断行 | 背景层不得遮挡标题;`filter`/`blur` 只允许在装饰伪元素 |
| `guardrails.md` 铁律 | 色相 ≤2、强调 ≤2、字体 ≤3、特效 ≤3 | 一张封面背景最多 2 个色相 + 1 种纹理手法 |
| `PIPELINE.md` 四过滤器 | 静态优先 / 文字锐利 / token 化 / 单文件自包含 | L1 全部满足;L3 生图需登记 manifest 并保持单文件自包含(相对路径) |

---

## 5. 接入 SOP(新增背景风格时按序执行)

1. **判层**:按 §0 顺序判定用 L1 / L2 / L3,写进本次任务说明;
2. **落配方**:L1 写进对应族模板(每族最多叠 2 层伪元素);L2 放 `assets/gzh-decor/` 并在模板内联;L3 走 3.2 资产目录 + manifest;
3. **登记**:在 `references/gzh-cover-layouts.md` 该族的"背景层"段落记一行(用什么层、配方名、参考编号);
4. **验门**:`gzh_cover.py check` + `check_slop.py` + 15% 缩略图目检;生图另加 §3.5 三道闸;
5. **回归**:同标题、同主题、同族,接入前后各出一张,并排看"背景是否抢了标题";
6. **记来源**:L3 在 manifest 与 README「开源组件与视觉来源」写明模型/许可(自生成则写"模型条款,不建立运行时依赖")。

---

## 6. 背景预算(防"堆料变噪")

| 项 | 上限 | 说明 |
|---|---|---|
| 背景层数(伪元素) | **2** | 一层纹理 + 一层光效/色带;超 2 层必然互相打架 |
| 纹理手法 | **1 种** | 网点/格纹/纸纹/撕纸 只选一种主纹理 |
| 色相 | **2** | 与 `guardrails` 一致 |
| 生图资产 | **2 张**(主 + 次) | 次条可复用主图裁切,不必各生一张 |
| 背景细节在主标区 | **0** | 主标区只允许低对比渐变或纯色 |

> 判据:把封面缩到 15% 宽,**第一眼看到的必须是主标,不是背景**。背景抢戏就是超预算。
