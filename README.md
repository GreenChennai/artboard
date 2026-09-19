<p align="center">
  <img src="./docs/readme/hero.svg" width="100%" alt="artboard · HTML 海报工作室:字落生根,版上开花——把文案与照片养成印刷级设计图,导出 PNG/JPG/GIF/MP4/PDF/SVG/EPS/AI/PPTX">
</p>

<h1 align="center">artboard · HTML 海报工作室</h1>

<p align="center">
  <strong>AI Agent Skill:让 AI 像设计师一样工作</strong><br>
  不调用 AI 生图,而是写 HTML/CSS、用真实摄影素材、按印刷规范排版,<br>
  再经 <strong>Kiln 原生引擎</strong>渲染成成品图——文字永远锐利,配色永远可控,<br>
  结果永远可复现,而且<b>零浏览器依赖、单文件离线直出九种格式</b>。
</p>

---

## 🆕 v1.9.0 · 导出引擎全面换血

> 渲染引擎从浏览器方案(WPI/Playwright)整体切换为 **Kiln**——
> VellumBench 出品的 Rust 原生导出核心,单文件零依赖,平均提速 **20×+**。

- **九格式同源直出**:PNG / JPG / GIF / MP4 / SVG / PDF / EPS / AI / PPTX,
  一次渲染全部可得;
- **CSS 动画原生时间轴**:`@keyframes` 逐帧求值直出 GIF/MP4——五段式场景卡、
  入场/循环动画不再依赖浏览器录制,没有录制偏移,`t=0` 即首帧;
- **PDF 中文真文本**:CIDFontType2 字体子集嵌入 + ToUnicode,
  中文在阅读器里**可选中、可复制、可检索**;
- **矢量真文本**:SVG/PPTX 保留真实文字节点,PDF/Ai 走 CID 真文本,
  Illustrator 直接打开;
- **外部矢量稿改造**:`kiln-cli import` 把设计师交付的 PDF/AI/SVG
  反向导回规范化 HTML(SVG 纯 Rust 解析,文本不转曲),继续在 artboard 里迭代;
- **保真度背书**:五用例固定基准套件以浏览器渲染为基线全像素平均
  **97.76/100**;22 案例全语料「可编辑 PDF → PDFium 栅格化 vs 原生渲染」
  平均 **98.63/100**、文本一致率 100%(口径与验收脚本随仓库开源,可复跑)。

## ✨ 成品样例

<table>
<tr>
<td align="center" width="25%"><img src="docs/samples/xhs-cover.png" width="100%"><br><sub>小红书封面 · 轻食研究所</sub></td>
<td align="center" width="25%"><img src="docs/samples/gzh-cover.png" width="100%"><br><sub>公众号封面 · 栗食记</sub></td>
<td align="center" width="25%"><img src="docs/samples/promo-square.png" width="100%"><br><sub>电商主图 · 铁象健身</sub></td>
<td align="center" width="25%"><img src="docs/samples/tech-kv.png" width="100%"><br><sub>科技发布 KV · 青梧智联</sub></td>
</tr>
<tr>
<td align="center"><img src="docs/samples/a4-poster.png" width="100%"><br><sub>A4 海报 · 城市之声室内乐</sub></td>
<td align="center"><img src="docs/samples/movie-poster.png" width="100%"><br><sub>电影海报 · 开票的人</sub></td>
<td align="center"><img src="docs/samples/card-front.png" width="100%"> <img src="docs/samples/card-back.png" width="100%"><br><sub>名片 · 正/背 · 闻山律所</sub></td>
<td align="center"><img src="docs/samples/trifold-front.png" width="100%"> <img src="docs/samples/trifold-back.png" width="100%"><br><sub>三折页 · 半山云宿</sub></td>
</tr>
<tr>
<td align="center" colspan="2"><img src="docs/samples/data-longform.png" width="100%"><br><sub>数据长图 · 城市咖啡图鉴</sub></td>
<td align="center" colspan="2"><img src="docs/samples/rollup.png" width="100%"><br><sub>易拉宝 80×200cm · 青梧智联校招</sub></td>
</tr>
</table>

> 每张均为本技能端到端产出:Pexels 授权摄影 / 开源字体(MiSans、得意黑、文楷等)/ 手写 CSS 排版与特效,300dpi 印刷直出。

## 🎯 它解决什么问题

AI 生图工具做海报的三座大山:**文字必糊、配色看运气、改一个字重跑一次**。artboard 反其道而行:

| | AI 生图 | artboard |
|---|---|---|
| 文字 | 概率性糊字/错字 | HTML 渲染,永远锐利可编辑 |
| 配色 | 每次随机 | 设计 token 锁定,改一处全局生效 |
| 迭代 | 改一字重跑全图 | 定点修改 HTML,秒级重导 |
| 素材 | AI 幻觉 | 真实摄影(Pexels 授权/用户提供) |
| 交付 | 一张位图 | 九格式:位图 + 矢量 + 视频 + 工程文件 |

## 🔄 工作流水线

<p align="center">
  <img src="./docs/readme/pipeline.svg" width="100%" alt="五问追问 → 风格字体 → 素材抠图 → 写 HTML → 导出 → 看图自检">
</p>

- **开工先追问**:内置五问协议(用途/尺寸/风格/配色/素材),拒绝拿到文案就盲做;
- **单文件原生导出**:Kiln 引擎九格式零浏览器依赖,独立 Playwright 脚本兜底(可选);
- **出图自检闭环**:渲染后自动看图检查溢出/对比度/字体加载,修复重导,2 轮上限;
- **动图**:CSS `@keyframes` 逐帧求值直出 GIF/MP4,迪士尼十二法则 + Material 缓动
  token,无缝循环经帧差校验;双模式:**海报循环**(模式 P)/ **视频场景卡**
  (模式 S,口播信息卡五段式出入场,ADR-0012);
- **物料尺寸总表**:社媒/电商/印刷/办公/广告 40+ 物料的尺寸、安全区与设计法则。

## 🚀 快速开始

把 `artboard/` 放进 Agent Skill 目录(如 `.agents/skills/`),然后直接对话:

```text
「给山雾茶町做一张 88 会员日的咖啡促销方图,产品图我有」
「按这张图复刻内容,换成我们的品牌色」
「做一份三折页,A4 横,正面背面都要」
「这张 GIF 动图,循环 3 秒」
```

**第 2 步 · 拿两把免费图库 Key(各 5 分钟)**

| 平台 | 步骤 |
|---|---|
| [Pexels](https://www.pexels.com/zh-cn/) | 注册 → 验证邮箱 → 补基础信息 → 悬停右上角「…」→「图片和视频 API」→ 填名称与用途 → 即刻发放 |
| [Pixabay](https://pixabay.com/) | 注册 → 验证邮箱 → 打开 [api/docs](https://pixabay.com/api/docs/) → 找「Your API key」→ 复制 |

**第 3 步 · 填配置(图形界面)**

双击 `tools\config-editor\artboard-config-editor.exe`(纯 tkinter 零依赖,已编译 exe),
逐项填写后点保存——即改即生效,不用重启。

> 界面顶部会显示**实际写入路径**,保存后也会回显一次。请确认它是
> `<技能根>\config.json`(不是 `scripts\config.json`)。
> 路径不对或想排障:命令行跑
> `artboard-config-editor.exe --locate`,会打印定位结果。
>
> exe 从**自身位置向上搜索**技能根(识别 `config.example.json`),所以放在
> `tools\config-editor\` 下、或临时拷到别处都能正确工作;窗口内可滚动,
> 另有「打开所在目录」按钮直接定位到 config.json。

**第 4 步 · 一键部署运行环境**(`artboard\scripts\` 下)

```bat
pip install -r ..\requirements.txt   :: 兜底导出与机检(playwright)+ 像素工序(Pillow)
python setup_kiln.py                 :: Kiln 渲染引擎(自动探测;可 --from 直链下载)
python setup_ffmpeg.py               :: FFmpeg(可选:MP4 + 高质量 GIF)
python fetch_model.py vqa            :: 本地 VQA 模型(可选:离线看图问答)
```

> Kiln 引擎也可以从上游自行构建:
> `git clone https://github.com/GreenChennai/VellumBench`
> → `cargo build -p vb_kiln --release --bin kiln-cli`。

**第 5 步 · 体检**

```bat
python scripts\preflight.py
```

打印环境自检报告:就绪几项、待补几项、每项怎么补。全部 ✓ 即可开工。

## 📐 品类与尺寸

| 品类 | 预设 | CSS 画布(px) | 导出 |
|---|---|---|---|
| 小红书 3:4 | `xhs` | 1080×1440 | 2x = 2160×2880 |
| 长图 / KV / 方图 / 竖屏 | `long` `kv` `square` `vertical` | 2400×auto 等 | 1–2x |
| 名片 90×54mm | `card` | 1063×638 | 1x = 300dpi |
| A4 海报 | `a4p` | 1240×1754 | 2x = 300dpi |
| 三折页(双面) | `trifold` | 1754×1240 | 2x = 300dpi + 合 PDF |
| 易拉宝 80×200cm | `rollup` | 2362×5906 | 2x = 150dpi |
| PPT 页 16:9 | `slide` | 1280×720 | 2x = 2560×1440 |
| 公众号封面 | `gzh` | 900×383 | 2x |
| 公众号双封面 | `gzh_cover.py` | 900×383 + 383×383 | 2x(另出合并图) |
| 电商主图 | `taobao` | 800×800 | 2x |

> 完整 40+ 物料尺寸(含社媒/广告/印刷)见 [material-catalog.md](references/material-catalog.md)。

## ⚙️ 配置

环境统一在根目录 `config.json`(复制 `config.example.json`,已被 gitignore):

| 键 | 说明 |
|---|---|
| `kiln_cli_exe` | Kiln 引擎 exe 路径(未配置则自动探测) |
| `studio_dir` | 海报项目与素材库落盘目录 |
| `pexels_key` / `pixabay_key` | 免费图库 API key |
| `*_cookie` | 素材站 Cookie,用 [tools/cookie-extension](tools/cookie-extension/)(MV3)一键抓取 |
| `proxy` | 本地代理(访问境外源用) |
| `ffmpeg` | 可选,启用 MP4 与高质量 GIF |
| `vision_mode` | `auto`(Agent 视觉优先)/ `local`(强制本地 VQA/OCR) |
| `vqa_path` | 本地 VQA 模块路径(`fetch_model.py vqa` 自动部署) |

优先级:环境变量 > config.json > 默认值。改完即生效。

## 🧩 矢量交付与工程文件(Kiln 原生)

默认流水线产出 PNG/JPG 等成品图;当用户需要**设计软件可编辑的工程文件**时,
Kiln 同一渲染管线直接产出矢量格式——真文本、中文可选中、免转换损耗:

```bash
python scripts/ai_export.py <项目目录>                      # 一键:SVG + PDF
python scripts/ai_export.py <项目目录> --eps --ai --pptx    # 追加 EPS / Ai / PPTX
python scripts/to_vector.py --source src --outdir export --formats svg,pdf,eps
```

| 产物 | 说明 |
|---|---|
| `*.svg` | 全矢量 + **真实文字节点**(非转曲),浏览器/Figma/AI 通吃,分组可开关 |
| `*.pdf` | CIDFontType2 字体子集嵌入 + Identity-H,**中文可选中复制可检索**,OCG 图层 |
| `*.ai` | PDF 兼容流 + Illustrator 头(ADR-0008),Illustrator 直接打开 |
| `*.eps` | 老印刷流程用(中文轮廓化) |
| `*.pptx` | 真文本 shape,汇报/二次编辑 |

> v1.9 起矢量交付不再经过浏览器打印/poppler 转换链,也不再有 SSIM 转换验收——
> 同一引擎同源渲染,保真度走 [bench/fidelity.py](../VellumBench/bench/fidelity.py)
> (五用例平均 97.76/100,详见上游 BENCHMARK.md §九)。
> 细节与验收清单见 [references/vector-export.md](references/vector-export.md)。

**矢量安全清单**:五条禁令(硬切透明渐变 / mix-blend-mode / 渐变字 /
conic-gradient / 渐变 alpha-stop 压圆角)——目标产物含矢量交付时源 HTML 应避免,
细则见 vector-export.md §4。

**逆向重维护**:`kiln-cli import` 把外部矢量稿导回规范化 HTML——

```bash
Kiln-noGUI-CLI.exe import --source poster.pdf --output <项目目录>   # PDF/AI:需 pdfium.dll
Kiln-noGUI-CLI.exe import --source poster.svg --output <项目目录>   # SVG:纯 Rust(usvg),零外部依赖
```

- 产出 `index.html + styles/main.css + assets/`,文本可编辑、可直接重导出;
- PDF/AI 依赖 `pdfium.dll`(环境变量 `PDFIUM_DLL` 指定,或放在 exe 同目录);
- v1 边界:PDF 统一近似色 + 路径盒近似;SVG 矩形/圆角/圆/椭圆/文本精确,
  自由曲线包围盒近似 + 警告,渐变取中点色。

**位图工序(从图到图)**

> 唯一入口 `scripts/imageops.py`;`python scripts/imageops.py --help` 列全,
> `python scripts/imageops.py help-map` 给"场景 → 子命令"映射。细则见 [references/imaging.md](references/imaging.md)。

```bash
python scripts/imageops.py probe --in "materials/*.jpg"          # 单图/批量体检(尺寸·DPI·alpha·体积·主色·疑点)
python scripts/imageops.py rotate --in a.jpg --exif-fix          # 手机图方向矫正(任何几何操作前先跑)
python scripts/imageops.py fit --in a.jpg --presets xhs          # 按比例裁到小红书 1080×1440
python scripts/imageops.py pad --in a.jpg --aspect 1:1 --bg edge # 补边到 1:1(不裁内容)
python scripts/imageops.py convert --in a.png --to webp --profile web    # 格式转换
python scripts/imageops.py compress --in a.jpg --target 500KB    # 压到目标体积(二分逼近)
python scripts/imageops.py derive --in kv.png --presets square,xhs,kv --formats png,webp --matrix  # 一图多规格
python scripts/imageops.py slice --in long.png --grid 3x3        # 九宫格切片
python scripts/imageops.py card --in p.jpg --radius 48 --shadow 0,8,24,#00000040  # 圆角卡片化
python scripts/imageops.py watermark --in p.jpg --text "©品牌" --position br --opacity 0.35
python scripts/imageops.py pipeline "exif-fix; fit aspect=1:1; compress target=300KB format=webp"  # 一条链
python scripts/imageops.py deps                                  # 位图工序族依赖状态
```

> 边界:`export.py` = 从 HTML 到图;`imageops.py` = 从图到图;抠图 = `cutout.py`;复刻测量 = `inspect_ref.py`。

## 📦 脚本一览

> SKILL.md 只留主线 6 条命令(省 token),完整清单在此。

**主线**:预检 → 建项目 → 写 HTML → 导出

```bash
python scripts/preflight.py                                    # 环境自检报告
python scripts/scaffold.py <slug> --size xhs --fonts 思源黑体,霞鹜文楷
python scripts/export.py --source src --output out.png \
    --width 1080 --scale 2                                     # 导出(主路径,九格式)
python scripts/export.py --source src --output out.gif \
    --format GIF --fps 25 --max-wait 6                         # 动画时长 = max-wait
python scripts/export_fallback.py --source src/index.html \
    --output out.png --width 1080 --scale 2                    # 导出(兜底,仅 PNG)
python scripts/check_overflow.py src                           # 机检文字越出容器边框(A/B 类)
python scripts/check_overflow.py src --safe-area 9x16          # 追加安全区检查(C 类)
```

**公众号双封面与正文排版**(v1.8.0 新增)

```bash
python scripts/gzh_cover.py new <slug> --title "标题" --theme blue   # 双封面项目(主 900×383 + 次 383×383)
python scripts/gzh_cover.py export <slug>                            # 三图齐出:主/次/合并(可 --only 单出)
python scripts/gzh_cover.py merge <slug> --gap 57                    # 仅重拼合并图(Pillow 纯拼接)
python scripts/gzh_article.py convert 文章.md --out article.html --preview  # 正文排版(Markdown→内联样式 HTML)
python scripts/gzh_article.py check article.html                     # 公众号兼容性自检
python scripts/gzh_article.py demo --outdir <目录>                   # 全组件示例 + 自检报告
```

> 规格与兼容性依据:[docs/gzh-spec-summary.md](docs/gzh-spec-summary.md) ·
> 排版规范:[references/gzh-typography.md](references/gzh-typography.md) ·
> 使用指南:[docs/gzh-guide.md](docs/gzh-guide.md)

**双击即出图**(用户改稿后自给自足)

```bash
python scripts/make_bats.py <项目> --embed   # 每个 HTML 生成"导出-<名字>.bat"
python scripts/export_local.py               # 批量导出器本体(须先投放到 <项目>/src/)
```

**矢量 / 工程文件 / 逆向**(仅当用户明确要 SVG/EPS/AI/PPTX/PDF 工程文件或外部矢量稿改造)

```bash
python scripts/ai_export.py <项目目录> [--svg --eps --ai --pptx]   # 一键矢量
python scripts/to_vector.py --source src --outdir export --formats svg,pdf,eps
Kiln-noGUI-CLI.exe import --source poster.pdf --output <项目目录>   # 逆向:PDF/AI(需 pdfium.dll)→ HTML
Kiln-noGUI-CLI.exe import --source poster.svg --output <项目目录>   # 逆向:SVG(纯 Rust)→ HTML
```

**素材**

```bash
python scripts/fetch_asset.py --query "…" --theme t --download # 搜图/下载
python scripts/cutout.py product.jpg --sticker --shadow        # 抠图+投影
python scripts/vqa.py image.jpg --prompt "描述这张图"           # VQA 看图问答
```

**复刻测量**

```bash
python scripts/compare.py 参考图 复刻图                          # 并排比对(--region 局部+ΔRGB)
python scripts/inspect_ref.py grid 参考图 -o grid.png            # 带标注网格
python scripts/inspect_ref.py census 参考图 --box x0,y0,x1,y1    # 分区普查取色(证据链)
python scripts/inspect_ref.py bbox 参考图 --box x0,y0,x1,y1      # 内容外接框(测边距)
python scripts/inspect_ref.py crop 参考图 --box x0,y0,x1,y1 -o img/p.png  # 裁素材
```

**维护(仓库自检,开发/改文档后跑)**

```bash
python scripts/selfcheck.py                 # 全部 7 项,人类可读
python scripts/selfcheck.py --only build    # 只跑一项
python scripts/selfcheck.py --json          # 单行 JSON,给 CI
```

| 检查 | 拦的是什么 |
|---|---|
| `refs` | Markdown 里引用的 `scripts/*.py` / `references/*.md` 是否真存在 |
| `nums` | 同一事实多处不一致(字体数 / 特效数 / 风格方向数 / 尺寸 / 字号下限 / 禁令条数) |
| `cfg` | `cfg("k")` 读的键 vs 声明处;双向 diff(未声明 / 死配置) |
| `route` | `references/` 下有无"从未被 SKILL.md 路由表引用"的孤儿分册 |
| `build` | **被跟踪的 exe 是否比源码旧**(源与产物同仓的维护陷阱) |
| `smoke` | 每个脚本能 import、CLI 能装配 |
| `jsonfail` | 关键脚本喂必失败输入,最后一行 stdout 必须是合法 JSON |

> 这 7 项各自对应一次真实发生过的缺陷:`make_bats` 断链、rollup 11811/11812 打架、
> `ocr_path` 死配置、`print-cmyk.md` 孤儿、配置编辑器 exe 过期、
> `vectoredit2webhtml.py` 异常分支缺 `import json`。

**字体 / 二维码 / 打包 / 换算 / 环境**

```bash
python scripts/fetch_font.py <目录名>                            # 按需下载缺失字体
python scripts/add_font.py <目录名> --name 显示名 --category 分类 --tags 关键词
python scripts/qr.py generate --data "…" --out img/qr.png --logo logo.png
python scripts/qr.py decode poster.png
python scripts/pack.py <项目> [--include-fonts] [--include-vendor]   # 自包含 zip
python scripts/slim_project.py <项目> --dry-run                  # 老项目改瘦身影子
python scripts/calc_size.py mm 210 297 --dpi 300 --scale 2       # 印刷尺寸计算器
python scripts/setup_kiln.py                                     # 部署 Kiln 引擎
python scripts/setup_ffmpeg.py                                   # 部署 FFmpeg
python scripts/fetch_model.py vqa                                # 部署本地 VQA
```

## 📁 目录结构

```
artboard/
├── SKILL.md                 # Agent 入口:流水线 + 铁律
├── config.example.json      # 复制为 config.json
├── references/              # 设计知识分册
│   ├── intake.md            #   开工五问追问(防盲做)
│   ├── guardrails.md        #   设计护栏 + 反 AI 味自检 12 条
│   ├── pipeline.md          #   流水线细则 + 动效规范
│   ├── style-system.md      #   布局原型 + 配色系统
│   ├── effects.md           #   视觉特效 43 式(fx- 34 + tx- 9)
│   ├── title-fx.md          #   标题手法(描边/蒙版/模糊/重组)
│   ├── composition.md       #   构图与版式骨架(动线/三分/黄金/视觉重量/基线网格)
│   ├── card-layout.md       #   卡片与容器布局(防文字出框:卡高公式/自适应/收口)
│   ├── video-safe-area.md   #   视频安全区(字幕带 / 平台 UI 遮挡,三画幅)
│   ├── typography-rules.md  #   排版硬规则(断行/层级/留白/数字)
│   ├── cjk-typography-css.md#   中文排版 CSS 落地(标点挤压/中西文间距/断行)
│   ├── numeric-typography.md#   数字·单位·日期排版
│   ├── dataviz.md           #   数据可视化规范(选型/坐标轴/系列色/大数字卡)
│   ├── color-contrast.md    #   对比度与色彩工程(WCAG/ΔL 速判/压图遮罩/色盲)
│   ├── responsive-reflow.md #   一稿多尺寸重排规则
│   ├── brand-system.md      #   品牌一致性(logo 净空/品牌色阶/跨物料)
│   ├── design-review-rubric.md # 设计评审打分表(五维度加权 + 及格线)
│   ├── materials.md         #   素材管线(找图/抠图/版权)
│   ├── print-cmyk.md        #   打印 CMYK 流程 + 安全色谱
│   ├── print-production.md  #   印前与后工艺(陷印/专色/裁切线/LPI/后加工)
│   ├── replicate.md         #   图片复刻协议
│   ├── export.md            #   导出手册
│   ├── vector-export.md     #   矢量交付手册(v1.9:Kiln 原生直出)
│   ├── style-guide.md       #   新增风格指南
│   ├── styles-catalog.md    #   123 风格方向速查
│   ├── styles/              #   4 个视觉风格分册(+参考案例)
│   └── formats/             #   名片/A4/三折页/易拉宝/PPT 品类规范
├── scripts/                 # preflight/scaffold/export/cutout/fetch_asset
│   │                        #   vqa/qr/add_font/setup_kiln/setup_ffmpeg
│   │                        #   fetch_font/export_local/junction/slim_project
├── fonts/                   # 28 款开源中英文字体族(按需下载,见 fonts/README.md)
├── assets/
│   ├── vendor/              # ECharts / GSAP
│   ├── icons/               # Tabler SVG 精选
│   ├── illustrations/       # Open Doodles(CC0)
│   └── cases/               # 各风格"及格线"参考案例 HTML
├── tools/
│   ├── cookie-extension/    # 素材站 Cookie 助手(MV3)
│   └── config-editor/       # 图形配置编辑器(exe)
└── docs/
    ├── setup.md             # 新手部署教程
    ├── glossary.md          # 词汇表 + 术语消歧
    ├── samples/             # 成品展示图
    └── references/          # 风格参考图
```

> 仓库只收"实际性工作内容 + 必备指导文档"。以下为**本地留档,不进仓库**
> (已在 `.gitignore` 排除):`docs/adr/`(架构决策)、`docs/ITERATION.md`(迭代台账)、
> `docs/review/`(审查报告)。
>
> 上游渲染引擎:[GreenChennai/VellumBench](https://github.com/GreenChennai/VellumBench)
> (Kiln 导出核心,发行资产 kiln-cli-v0.6.0;布局引擎/文本引擎/CSS 动画时间轴/CID 中文真文本/PDF·AI·SVG 导入/22 案例保真度 98.63)。

## 🔑 素材与版权政策

| 层级 | 来源 | 授权 |
|---|---|---|
| 1 | [Pexels](https://www.pexels.com/) / [Pixabay](https://pixabay.com/) API | 免费商用免署名 |
| 2 | 爬虫(必应/百度/图标库/Pinterest/花瓣) | **不确定** → 自动加 `版权风险-` 前缀,交付时提醒更换 |

- 产品实拍图**只能用户提供**——真实产品是品牌资产,图库没有也不该编;
- 爬虫素材的 `版权风险-` 前缀任何环节不得移除;
- Cookie 只存本机 config.json(已被 gitignore),无任何上传。

## 🙏 致谢

设计方法论与规则提炼自(思想借鉴,代码自写):

| 来源 | 许可 | 借鉴内容 |
|---|---|---|
| [baoyu-skills](https://github.com/JimLiu/baoyu-skills) | MIT | 风格×布局×配色枚举 |
| [diagram-design](https://github.com/cathrynlavery/diagram-design) | MIT | 编辑纪律/删减哲学 |
| [stylekit](https://github.com/AnxForever/stylekit) | MIT | 风格 schema/反 AI 味自检/原子化方法 |
| [html-anything](https://github.com/nexu-io/html-anything) | Apache-2.0 | 物料分区范式 |
| [esther-design-system](https://github.com/esthersjw/esther-design-system) | CC BY-NC-SA | 暖底/去 AI 味思想(重写) |
| [Art](https://github.com/zhuxice-ctrl/Art) | 无(仅特效原理) | 视觉特效实验室 |
| [guizang-ppt/social-card](https://github.com/op7418) | AGPL | 踩坑规则思想(重写) |
| [super-prototyping](https://github.com/ReScienceLab/super-prototyping) | Apache-2.0 | 复刻证据链方法论:网格先行/测量优先/普查取色(replicate.md) |
| [rembg](https://github.com/danielgatis/rembg) | MIT | 本地抠图引擎 |

字体:思源黑体/宋体(Noto CJK)· 得意黑(Smiley Sans)· 霞鹜文楷(LXGW WenKai)· 站酷快乐体(ZCOOL KuaiLe)· MiSans(小米)· 阿里巴巴普惠体 3.0 · HarmonyOS Sans(华为)。

图标:[Tabler Icons](https://github.com/tabler/tabler-icons)(MIT) · 插画:[Open Doodles](https://www.opendoodles.com/)(CC0)。

渲染引擎:[GreenChennai/VellumBench](https://github.com/GreenChennai/VellumBench) — Kiln 导出核心(Rust,自研)。

## 📄 License

**ACL-1.0(Artboard 社区开源协议)** — 传染性开源,详见 [LICENSE](LICENSE):

- ✅ 免费使用 / 学习 / 修改 / 分发;**产出物(海报、图、PDF 等)归使用者,可自由商用、闭源、售卖**
- 🔁 传染:复制或衍生(含打包进其他项目、包装成在线服务)必须整体按 ACL-1.0 开源
- 🚫 禁止转售软件本体;部署/定制/咨询等服务费与产出物收入不受限
- 📦 捆绑的字体/图标/vendor 库各随其原始授权
