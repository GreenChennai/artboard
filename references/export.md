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

# PDF(CID 中文真文本,可选中可复制)
python scripts/export.py --source "<project>/src" --output "<project>/export/out.pdf" \
  --width 1080 --format PDF

# 矢量/工程文件(SVG/EPS/AI/PPTX)走 vector-export.md 分册

# 兜底(仅 PNG)
python scripts/export_fallback.py --source "<project>/src/index.html" \
  --output "<project>/export/out.png" --width 1080 --scale 2
```

## 输出解析

export.py 输出**单行 JSON**:
- `ok: true` → `path/width/height/frames` 直接采信;
  **`degraded_artboard: true` 时画布尺寸是内容推导值**,人工核对后再交付;
  **`engine_fallback: true` 说明引擎降级过**(光栅格式已自动转兜底,矢量格式
  需人工核对);`warnings` 数组非空时检查(资源缺失/CMYK 跳过/引擎告警等);
- `ok: false` → 看 `error`:
  - `KILN_NOT_FOUND` → 跑 `scripts/setup_kiln.py`,或 config.json 填
    `kiln_cli_exe`,或设 `ARTBOARD_KILN_CLI`;
  - `KILN_CLI_FAILED` → 看 stderr detail;急用 PNG 走兜底;
  - 其他 → 转告用户 detail。

## 已知行为(Kiln 语义)

- **动画 = 逐帧求值**:GIF/MP4 按 @keyframes + animation 声明逐帧渲染,
  `--max-wait` 即五段式总时长;静态图求值到 t=0(首帧),不依赖浏览器收敛;
- 超大画布守门:单边 >32768px 或像素面积超限时显式报错(不静默截断);
- MP4 无 ffmpeg 自动降级 GIF 流并告警;GIF 永远可出(内置量化器);
- `--scale 4/8` 仅特殊需求用(印刷);常规 2。

## 本册用到的脚本

| 脚本 | 何时用 | 一行示例 |
|---|---|---|
| `export.py` | 导出主路径 | `python scripts/export.py --source … --output …` |
| `export_fallback.py` | 无 Kiln 兜底(仅 PNG) | `python scripts/export_fallback.py --source src/index.html -o o.png` |
| `make_bats.py` | 双击导出 bat | `python scripts/make_bats.py <项目> --embed` |
| `export_local.py` | 本机直出变体 | `python scripts/export_local.py --help` |
| `pack.py` | 交付自包含打包 | `python scripts/pack.py <slug>` |
| `slim_project.py` | 项目瘦身 | `python scripts/slim_project.py --help` |
| `setup_kiln.py` | Kiln 引擎部署 | `python scripts/setup_kiln.py` |
| `setup_ffmpeg.py` | ffmpeg 部署 | `python scripts/setup_ffmpeg.py` |
| `doctor.py` | 环境诊断 | `python scripts/doctor.py` |

> 参数的权威说明在脚本自身 `--help`(不在此复制);全量索引见 `docs/scripts.md`。
