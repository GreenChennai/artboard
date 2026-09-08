# artboard 导出手册

## 引擎选择(三级)

1. **WPI 源码版**(`wpi_path`,Python API):功能最全,默认;
2. **WPI CLI 单文件**(`wpi_cli_exe`,约 63MB):`setup_wpi.py` 从 artboard 发行页部署;
   源码版不可用时自动切换(同参数命令行,退出码 0 = 成功);
3. **export_fallback.py**(独立 Playwright):仅 PNG 的最后兜底。

## 双路径

| | 主路径 `export.py` | 兜底 `export_fallback.py` |
|---|---|---|
| 引擎 | WPI(Playwright + 系统 Edge/Chrome,settle 收敛) | 独立 Playwright 脚本 |
| 格式 | PNG / GIF / MP4 / PDF | 仅 PNG |
| 何时用 | 默认 | export.py 报 `WPI_NOT_FOUND` / `WPI_IMPORT_FAILED` |

## 尺寸与倍率预设

| 用途 | --size | 画布(CSS px) | 导出命令参数 | 成品(px) |
|---|---|---|---|---|
| 小红书封面 | xhs | 1080×1440 | `--width 1080 --scale 2 --height 1440` | 2160×2880 |
| 长图 | long | 2400×auto | `--width 2400 --scale 1`(图内容多可 2) | 2400×内容高 |
| 横幅 banner | banner | 1920×600 | `--width 1920 --scale 2 --height 600` | 3840×1200 |
| 主 KV | kv | 1920×1080 | `--width 1920 --scale 2 --height 1080` | 3840×2160 |
| 方图 | square | 1080×1080 | `--width 1080 --scale 2 --height 1080` | 2160×2160 |
| 竖屏 9:16 | vertical | 1080×1920 | `--width 1080 --scale 2 --height 1920` | 2160×3840 |
| 名片 90×54mm | card | 1063×638 | `--width 1063 --scale 1`(即 300dpi) | 1063×638 |
| A4 海报 | a4p | 1240×1754 | `--width 1240 --scale 2 --height 1754` | 2480×3508(300dpi) |
| 三折页单面 | trifold | 1754×1240 | `--width 1754 --scale 2 --height 1240`(正/背各导一次) | 3508×2480(300dpi) |
| 易拉宝 80×200cm | rollup | 2362×5906 | `--width 2362 --scale 2 --height 5906`(慢,分块拼接属正常) | 4724×11811(150dpi) |

> 印刷品类规范(字号下限/折线/盲区/双面工作流)见 `references/formats/`。

> **固定尺寸预设(除长图)必须带 `--height <画布高>`**:WPI 初始视口是"宽×宽",
> 画布矮于视口时整页截图会把视口高度一并截进去(kv 实测出过 3840×3840)。
- 高度锁定(卡片式精确高度):`--height <px>`(超出内容不导出)。
- 透明底:`--transparent`(PNG;HTML 里 body 背景设 `transparent`)。

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

**常用尺寸速算表(scale 后成品)**:

| 品类 | mm | CSS 画布 | scale | 成品 px | 成品 DPI |
|---|---|---|---|---|---|
| 名片 | 90×54 | 1063×638 | 1 | 1063×638 | 300 |
| A4 | 210×297 | 1240×1754 | 2 | 2480×3508 | 300 |
| 三折页 | 297×210 | 1754×1240 | 2 | 3508×2480 | 300 |
| 易拉宝 | 800×2000 | 2362×5906 | 2 | 4724×11812 | 150 |
| 小红书 | (3:4) | 1080×1440 | 2 | 2160×2880 | 屏 |
| PPT 页 | 16:9 | 1280×720 | 2 | 2560×1440 | 屏 |

## 命令速查

```bash
# 静态 PNG(最常用;固定尺寸带 --height)
python scripts/export.py --source "<project>/src" --output "<project>/export/out.png" \
  --width 1080 --scale 2 --height 1440

# GIF 动图(循环动画,录制 6 秒)
python scripts/export.py --source "<project>/src" --output "<project>/export/out.gif" \
  --width 1080 --scale 2 --format GIF --fps 25 --max-wait 6

# MP4(需 ffmpeg)
python scripts/export.py --source "<project>/src" --output "<project>/export/out.mp4" \
  --width 1080 --scale 2 --format MP4 --fps 30 --max-wait 6

# PDF(长图转 PDF,超 2400px 自动分页)
python scripts/export.py --source "<project>/src" --output "<project>/export/out.pdf" \
  --width 1080 --format PDF

# 兜底(仅 PNG)
python scripts/export_fallback.py --source "<project>/src/index.html" \
  --output "<project>/export/out.png" --width 1080 --scale 2
```

## 输出解析

export.py 输出**单行 JSON**:
- `ok: true` → `path/width/height/frames` 直接采信;`warnings` 数组非空时检查是否有资源加载失败。
- `ok: false` → 看 `error`:
  - `WPI_NOT_FOUND` → 设 `ARTBOARD_WPI` 指向 WPI 根目录,或用兜底;
  - `WPI_IMPORT_FAILED` → 提示用户 `pip install playwright pillow` 后重试,急用走兜底;
  - 其他 → 转告用户 detail。

## 已知行为(来自 WPI,遇到不慌)

- 导出前自动 settle:等字体(`document.fonts.ready`)、懒加载图片、滚动触发 reveal、**动画收敛到终态**——所以静态图不要依赖动画中间态,动图走 `--format GIF/MP4`(不冻结)。
- 单拍超 15000px 或有首屏外 canvas:自动分块截图 + 拼接,慢是正常的。
- GIF 无 ffmpeg 时用 Pillow 回退(质量略降,仍可用);MP4 无 ffmpeg 直接失败。
- `--scale 4/8` 仅特殊需求用(印刷);常规 2。
