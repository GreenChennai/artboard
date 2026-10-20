# artboard 导出手册(v1.9.1 · Kiln 引擎)

## 引擎选择(三级)

1. **Kiln 原生引擎**(唯一主引擎):`kiln_cli_exe` 单文件,九格式
   PNG/JPG/GIF/MP4/SVG/PDF/EPS/AI/PPTX 直出,零浏览器/Python 依赖;
   未部署时 `scripts/setup_kiln.py` 从 artboard 发行页自动下载;
2. **export_fallback.py**(独立 Playwright):仅 PNG 的最后兜底;
3. 都不可用 → 报错(`KILN_NOT_FOUND`)。

> WPI 三级引擎(v1.8 及以前)已整体退役:`wpi_path`、`wpi_cli_exe`、
> `setup_wpi.py`、`ARTBOARD_WPI` 均已删除,遇到旧文档/旧脚本提及即过时。

## 双路径

| | 主路径 `export.py` | 兜底 `export_fallback.py` |
|---|---|---|
| 引擎 | Kiln 单文件(`kiln_cli_exe`) | 独立 Playwright 脚本 |
| 格式 | PNG / JPG / GIF / MP4 / PDF / SVG / EPS / AI / PPTX | 仅 PNG |
| 何时用 | 默认 | export.py 报 `KILN_NOT_FOUND` / `KILN_CLI_FAILED`,或引擎自报降级 |

**降级会自动转兜底**:Kiln 的浏览器车道不可用时,`engine=auto`
会落到自研引擎 —— 自研引擎对真实海报页会丢照片/遮罩/绝对定位,基本是废图。
现在 Kiln 在结果 JSON 里置 `engine_fallback:true`,而 `export.py` 见到该字段
且格式是 PNG/JPG 时,**自动改调 `export_fallback.py` 重出同一路径**
(结果 JSON 带 `auto_fallback_from:"kiln-native"`);非光栅格式不自动转,
但会在 `warnings` 里明确写出降级,交付前必须人工核对。
加 `--no-auto-fallback` 可关掉这个自动切换。

> 自研引擎环境里也打不开浏览器时,根治办法是让浏览器车道本身可用:
> 设环境变量 `VB_BROWSER_PATH` 指向 Chrome/Edge 可执行文件。

## 画板合成规则(存量项目必读)

Kiln 对无 `vb-artboard` 标记的普通 HTML **合成画板**,尺寸按以下规则:

1. **`.poster` 等显式尺寸容器是画布真值的唯一来源**:合成画板尺寸 =
   内容包围盒,但包围盒计算**尊重 `overflow:hidden` 裁剪**——
   `.poster{width:1240px;height:1754px;overflow:hidden}` 内部溢出的
   子内容不会撑大画布;
2. **CSS Grid 已支持**:`display:grid` + `grid-template-columns/rows`
   (fr/px/%/repeat)/gap 按真实网格布局;模板无法解析时该容器**降级
   块布局并输出告警**,不再静默塌成单列;
3. 回填发生时 Kiln 结果 JSON 带 **`degraded_artboard: true`** 字段
   (stderr 同时有 `vb_layout:合成画板尺寸回填` warn)——批量重跑脚本
   应检查该字段,`true` 说明画布尺寸由内容推导而非显式声明,需人工核对;
4. `--width`/`--height` 是**采集视口口径**(CSS px):`0`(默认)= Kiln
   按画板几何自适应;**非 1080 画幅(banner 1920 / kv 1920 / rollup 2362)
   必须显式传入**,否则浏览器车道按 1080 视口渲染。
   画布真值仍在 HTML 容器声明里,命令行只影响采集视口。

## 尺寸与倍率预设

| 用途 | --size | 画布(CSS px) | 成品(px,@scale2) |
|---|---|---|---|
| 小红书封面 | xhs | 1080×1440 | 2160×2880 |
| 长图 | long | 2400×auto | 2400×内容高(scale1 可 2) |
| 横幅 banner | banner | 1920×600 | 3840×1200 |
| 主 KV | kv | 1920×1080 | 3840×2160 |
| 方图 | square | 1080×1080 | 2160×2160 |
| 竖屏 9:16 | vertical | 1080×1920 | 2160×3840 |
| 名片 90×54mm | card | 1063×638 | 1063×638(scale1=300dpi) |
| A4 海报 | a4p | 1240×1754 | 2480×3508(300dpi) |
| 三折页单面 | trifold | 1754×1240 | 3508×2480(300dpi,正/背各导) |
| 易拉宝 80×200cm | rollup | 2362×5906 | 4724×11812(150dpi) |

> 印刷品类规范(字号下限/折线/盲区/双面工作流)见 `references/formats/`。
> 画布真值在 HTML 容器声明里(上表为 scaffold 预设);`--width/--height`
> 只决定采集视口,不决定画布。

## 尺寸换算公式与计算器

> 更多物料尺寸(社媒/电商/广告全量)见 material-catalog.md 总表;高频先查 sizes-common.md。

**唯一公式链**(记住这一个,其余都是它的变形):

```
像素 px = 物理长度 ÷ 25.4 × DPI        (25.4 = 1 inch)
物理长度 mm = px ÷ DPI × 25.4
成品 px = CSS 画布 px × scale          (scale 即导出倍率)
成品 DPI = 成品 px ÷ (成品 mm ÷ 25.4)
```

**红线**:印刷成品 ≥300dpi;喷绘大幅面(>A2)≥150dpi;屏幕图 72-144 即可。

**计算器**:
```bash
python scripts/calc_size.py mm 210 297 --dpi 300        # A4→px: 2480×3508
python scripts/calc_size.py mm 90 54 --dpi 300          # 名片→px: 1063×638
python scripts/calc_size.py px 1080 1440 --dpi 300 --scale 2   # 反查物理尺寸
python scripts/calc_size.py dpi --px 2480 3508 --mm 210 297    # 反推 DPI
```

## 命令速查

```bash
# 静态 PNG(最常用;--width/--height 缺省自适应,非 1080 画幅显式传视口)
python scripts/export.py --source "<project>/src" --output "<project>/export/out.png" \
  --width 1080 --scale 2 --height 1440

# GIF 动图(动画逐帧求值,总时长 = --max-wait 秒)
python scripts/export.py --source "<project>/src" --output "<project>/export/out.gif" \
  --width 1080 --scale 2 --format GIF --fps 25 --max-wait 6

# MP4(需 ffmpeg)
python scripts/export.py --source "<project>/src" --output "<project>/export/out.mp4" \
  --width 1080 --scale 2 --format MP4 --fps 30 --max-wait 6

# WebGPU 动效卡(含 requestAnimationFrame / 无确定性 seek 的 shader):使用墙钟采样
# MP4 yuv420p 画布宽高必须为偶数;视频卡建议独立使用 900×384 等偶数画布。
python scripts/export.py --source "<project>/src" --output "<project>/export/shader-card.mp4" \
  --width 900 --height 384 --format MP4 --fps 10 --max-wait 2 --webgpu --wall

# 重页面/长动画:调大墙钟上限(默认 900s)。逐帧动画实测约 0.9 帧/秒,
# 1080x1440 @25fps x 15s = 375 帧 ≈ 427s —— 别等它自己撞死。
python scripts/export.py --source "<project>/src" --output "<project>/export/out.gif" \
  --width 1080 --format GIF --fps 25 --max-wait 15 --timeout 1800

# PDF(CID 中文真文本,可选中可复制)
python scripts/export.py --source "<project>/src" --output "<project>/export/out.pdf" \
  --width 1080 --format PDF

# 矢量/工程文件(SVG/EPS/AI/PPTX)走 vector-export.md 分册

# 兜底(仅 PNG)
python scripts/export_fallback.py --source "<project>/src/index.html" \
  --output "<project>/export/out.png" --width 1080 --scale 2
```

### 三个时间量(Kiln ≥0.14.1 起必须分清)

| 脚本参数 | 传给引擎 | 语义 | 默认 |
|---|---|---|---|
| `--max-wait` | `--duration` | **动画总时长**(秒)。静态格式忽略 | 15 |
| `--timeout` | — | **整棵进程树**(含浏览器孙进程)的墙钟上限;超时强杀并报 `KILN_CLI_TIMEOUT` | 900 |
| `--max-wait-budget` | `--max-wait` | 浏览器车道 **settle/截图的总预算**;**0 = 不下发**(推荐) | 0 |

⚠️ **`--max-wait-budget` 默认不传是有意的**。Kiln 0.14.1 把 `--max-wait` 从
「静默忽略」改成**真接线**的每实例总 deadline(`set_overall_deadline`,settle 与全部
CDP 长等待各自被 `min(默认上限, 剩余预算)` 收口)。给了小值会怎样,实测:
`--max-wait 0.5` 跑重页面 → 浏览器车道直接失败 → **静默降级自研引擎**
(`engine_fallback:true` + `degraded:true`),而自研引擎对真实海报页是废图。
所以它**不是性能旋钮**;引擎行为异常先查 `docs/upstream-issues.md`。

## 输出解析

export.py 输出**单行 JSON**:
- `ok: true` → `path/width/height/frames` 直接采信;
  **`degraded_artboard: true` 时画布尺寸是内容推导值**,人工核对后再交付;
  **`engine_fallback: true` 说明引擎降级过**(光栅格式已自动转兜底,矢量格式
  需人工核对);`warnings` 数组非空时检查(资源缺失/CMYK 跳过/引擎告警等);
- `ok: false` → 看 `error`:
  - `KILN_NOT_FOUND` → 没装引擎。跑 `scripts/setup_kiln.py`,或 config.json 填
    `kiln_cli_exe`,或设 `ARTBOARD_KILN_CLI`;
  - `KILN_TOO_OLD` → 装了但参数面过旧(响应带 `missing_flags`,当前要求
    `--engine/--height/--vector/--duration`)。跑 `setup_kiln.py --force` 升级。
    **不要**去手工传 Kiln 不认的参数 —— 旧 CLI 会静默忽略,现象是"传了没效果";
  - `KILN_CLI_TIMEOUT` → 撞了 `--timeout`。先确认是**真慢**还是**挂死**:动图逐帧
    本来就慢(见 UP-5),调大 `--timeout` 即可;静态单帧也超时才是引擎问题,查台账;
  - `KILN_CANCELLED` → 导出期间在 stdin 敲了 `c`(Kiln 0.14.0 起的协作取消),
    未留半截产物,重跑即可,不是故障;
  - `KILN_CLI_FAILED` → 看 stderr detail;急用 PNG 走兜底;
  - 其他 → 转告用户 detail。

## 已知行为(Kiln 语义)

- **静态图(PNG/JPG)= 把有限动画「快进到终态」再截**,不是 t=0 首帧;`--max-wait`(动画时长)
  **只对 GIF/MP4 有意义**。
  实测(2026-10-07,本机,Kiln 经 `scripts/export.py`,结果 JSON `engine:"browser"`、`frames:1`):
  - `.box{animation:toBlue 2s linear forwards}`(红→蓝)→ 出图 = 纯蓝 **RGB(0,0,255)**;
    `.fade{opacity:0→1, 2s linear forwards}` → 出图 = 纯绿 **RGB(0,255,0)**(不是首帧的透明态);
  - 带延迟的 `.b{animation:toBlue 2s linear 1s forwards}`(总 3s 才到终态)同样 = 纯蓝 ——
    **延迟不影响"快进到终态"**;
  - **`infinite` 动画不收敛,静态相位不确定**:`.c{animation:toBlue 2s linear infinite}` 连导三次分别为
    RGB(198,0,57) / (200,0,55) / (185,0,70),换算相位 ≈0.45s / 0.43s / 0.55s(2s 周期)——
    静态交付(封面/缩略图)不要依赖 `infinite`(见 `animation.md` §一【硬】、§五);
- **动画(GIF/MP4)= 逐帧求值 + 固定时长**:帧数 = `--fps` × `--max-wait`
  (实测 `--format GIF --fps 10 --max-wait 2` → 20 帧、每帧 100ms;`--max-wait 6` → 60 帧;
  结果 JSON `engine:"browser-anim"`)。**但第一帧不是动画的 0% 态**:捕获起点在 CSS 时间轴
  **≈1.0s 处**(200–400px 页面实测 **0.9–1.0s** / **1080×1920 交叉验证 1.0–1.25s**,均 2026-10-07),
  动画结束后的余帧冻结在终态。三组独立样例的推导:
  - 200×200、4s 无延迟动画:第 30 帧(3.0s)到纯蓝 → 起点 = 4.0 − 3.0 = **1.0s**;
  - 同页 2s 延迟 + 4s 动画:第 50 帧(5.0s)到纯蓝 → 起点 = 6.0 − 5.0 = **1.0s**
    (运动起点落在第 ~10 帧 = 2.0s 延迟 − 1.0s,自洽);
  - **1080×1920 渐变探针**(`--format GIF --fps 4 --max-wait 8`:两条 4s 红→蓝,`.a` 无延迟 / `.b` +2s 延迟):
    R 通道序列 `[190,190,158,142,…,45,29,13,13,13,…]`(每帧 0.25s,调色板步长 16 ≈ 255/16);
    首帧 R=190 → 进度 0.255 → CSS ≈1.02s;末步 R=13 → 进度 0.949 → CSS ≈3.80s(第 11 帧,捕获 2.75s)
    → 起点 ≈1.05s;`.b` 独立算出同一值 ⇒ 该画幅上 **1.0–1.25s**;
  ⇒ **从 0s 起播的入场,前约 1s 会被截掉**(对策见 `animation.md` §八 前置静置 ≥2.0s;
  最坏值 1.25s 时仍留 ≥0.75s 余量,故该硬规则照旧保留);
- 超大画布守门:单边 >32768px 或像素面积超限时显式报错(不静默截断);
- MP4 无 ffmpeg 自动降级 GIF 流并告警;GIF 永远可出(内置量化器);
- `--scale 4/8` 仅特殊需求用(印刷);常规 2。

> **车道**:`scripts/export.py` **没有** `--engine` 参数(实跑 `--engine native` →
> `error: unrecognized arguments`,`[exit code: 2]`);浏览器/自研车道由 Kiln 内部决定,
> 结果 JSON 的 `engine` 字段回报实际车道(静态有浏览器时 `browser`,动画为 `browser-anim`)。
> 故本文的静态/动画语义均按**浏览器车道**记(车道细节见 `docs/glossary.md`「Kiln 双车道」)。

## GIF / MP4 的编码质量(v0.14.2 起可配)

**v0.14.2 之前**编码参数确实不在 artboard 手里(全仓 `grep palettegen|libx264` 无命中),
只能登记上游(`docs/upstream-issues.md` UP-4)。**现在 Kiln 已把它们暴露成 CLI 参数**,
`scripts/export.py` 原样透传:

| 参数 | 语义 | 默认 |
|---|---|---|
| `--gop <N>` | 关键帧间隔(x264 链自动配 `-x264-params forced-idr=1` 钉死网格) | 不下发 = 编码器默认 |
| `--bf <N>` | B 帧数;**`--bf 0` 是显式意图**(关 B 帧),不是缺省 | 不下发 = 编码器默认 |
| `--pix-fmt <fmt>` | 像素格式(默认 `yuv420p`) | `yuv420p` |
| `--no-color-tags` | **不写**色彩标签(关掉 ≠ 写 `unknown`);色程压缩保留 | 关 = 写 bt709 |

```bash
# 要能直接粘进微信 / 播客编辑器、且首帧绝不为黑:关 B 帧 + 锁 GOP
python scripts/export.py --source <proj>/src --output out.mp4 \
  --format MP4 --fps 25 --max-wait 6 --gop 25 --bf 0
```

> 默认逐位保持旧行为(已用 `ffprobe` 核对:不带参数时成片仍含 B 帧),
> 所以「以前能播的现在还能播」。要改就走上面的显式参数,别再自己拼 ffmpeg 后处理。

### 曾经踩过的两个坑(已在上游修掉,记下来别再引入)

1. **`palettegen=stats_mode=diff` 会静默错色**。`diff` 只把「相邻帧之间变化过的像素」
   纳入调色板统计,而硬切动画(`steps()` 卡点)恰恰是「大片纯色整体切换」——
   从不变化的部分零贡献,某些颜色进不了调色板,被映射到最接近的已有色。
   实测 40 帧(0-19 红 / 20-39 蓝):`diff` → 整段蓝色丢失;`full` → 正确。
   **现引擎用 `stats_mode=full`**。调色板会略大(2269B → 2737B),换来不交付错色。
2. **裸 `-forced-idr` 会让整条 ffmpeg 命令崩**。ffmpeg 解析器不认它是布尔标志,
   会把后一个 token 当输出文件名(`Unable to choose an output format for 'yuv420p'`)。

> 审片台「裁片段」仍自带 `-bf 0` 与偶数尺寸 pad(`yuv420p` 硬要求,奇数画布直接报错)——
> 那条走自己的 ffmpeg 调用,与引擎参数无关。

## 素材到底加载出来了吗(别只看 `ok`)

`ok: true` 只说明**流程跑完了**,不代表**内容是对的**。两类最隐蔽的损坏都报 `ok: true`:

| 损坏 | 产物表现 | 怎么查 |
|---|---|---|
| 图片断图 | 只剩 alt 文字 / 占位块 | `img.naturalWidth === 0` |
| 字体静默降级 | 版面看着差不多,字重字距全错 | `document.fonts[].status` 是 `error`/`unloaded` |

**现在有门禁替你查了**(v1.22.0 起,`check_overflow.py` 新增两类):

```bash
python scripts/check_overflow.py <proj>/src
```

- **E 类** = 图片没加载出来(1x1 追踪像素自动跳过,免得淹没真问题)
- **F 类** = 自定义字体未生效,已静默降级

两条都默认开、零额外开销(复用本来就要起的那次浏览器)。跑机检时若 E/F 为空,
即可确认素材到位;**不要靠肉眼看缩略图**。

### 素材路径:只写相对路径,绝不写 `file:///`

**实测结论**(2026-10-09,Kiln v0.14.3,合成纯色图 + 洋红底做对照):

| 写法 | 结果 |
|---|---|
| `img/logo.png`(相对,`scaffold.py` 建的目录联接) | **正常** |
| `file:///D:/.../logo.png`(绝对 URI) | **被 Chromium 拦** |
| `data:image/png;base64,...` | 正常 |

Chromium 禁止 `file://` 页面加载 `file://` **绝对 URI** 子资源。两种写法解析后是
**同一个 URL 字符串**,所以早期诊断报出来无法区分,很容易把锅甩给相对路径 ——
方向反了,绕行方案也就跟着错。v0.14.3 起告警消息会直接标注来源:

```
外部资源加载失败: [绝对 file:// URI,Chromium 必拦,改相对路径] file:///D:/.../logo.png
```

> 顺带留档:曾试过让引擎加 `--allow-file-access-from-files`,**实测无效** ——
> 加与不加,同一页导出**逐像素完全相同、`bytes` 一字不差**。Kiln 静态车道用
> `Page.navigate` 打开 `file:///<abs>/index.html`,Chromium 对**同目录** file://
> 子资源本就放行。所以**不需要**任何额外开关,只要不写 `file:///`。

## 交付后审阅(动效类)

出片不是终点:动效/视频卡的返修走**审片台闭环** —— 逐帧看 → 元素拾取 → 意见落盘成 JSON →
下一轮直接读文件改。口径见 `references/review-loop.md`,工具在 `tools/review-station/`。

## 本册用到的脚本

| 脚本 | 何时用 | 一行示例 |
|---|---|---|
| `export.py` | 导出主路径 | `python scripts/export.py --source … --output …` |
| `export_fallback.py` | 无 Kiln 兜底(仅 PNG) | `python scripts/export_fallback.py --source <项目>/src/index.html --output <项目>/export/out.png` |
| `make_bats.py` | 双击导出 bat | `python scripts/make_bats.py <项目> --embed` |
| `export_local.py` | 项目内一键导出(被 `scaffold.py` 投放为 `<项目>/src/导出.py`) | 在项目 `src/` 目录下双击 `导出.py`(或在该目录跑 `python 导出.py`)——**没有命令行参数,也不能在技能 `scripts/` 下运行** |
| `pack.py` | 交付自包含打包 | `python scripts/pack.py <slug>` |
| `slim_project.py` | 项目瘦身 | `python scripts/slim_project.py --help` |
| `setup_kiln.py` | Kiln 引擎部署 | `python scripts/setup_kiln.py` |
| `setup_ffmpeg.py` | ffmpeg 部署 | `python scripts/setup_ffmpeg.py` |
| `doctor.py` | 存量项目体检(扫 studio 目录) | `python scripts/doctor.py <studio_dir>` |

> 参数的权威说明在脚本自身 `--help`(不在此复制);全量索引见 `docs/scripts.md`。
