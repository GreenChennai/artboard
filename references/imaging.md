# 位图工序(imaging)

> **调色/滤镜/图层合成**走配方引擎 `scripts/pixel.py`(references/pixel-pipeline.md):
> 本册管工序(裁/缩/压/转),调整类能力(色阶/曲线/HSL/混合模式等)一律用 pixel。

## 0. 何时读本分册 / 何时不要读

- **读**:任务里有"已存在的图片文件"要被加工(裁/缩/压/转/水印/切片/体检)
- **不读**:从 HTML 出图(→ `export.md`)、抠图(→ `materials.md` §3)、复刻测量(→ `replicate.md`)
- **图像的语言层(该怎么用:角色/色调分级/裁切语法/景深/处理链顺序)见 `image-language.md`;本册只管"用哪条命令"**

## 1. 三种边界(先明确用哪个工具)

| 需求 | 用 |
|---|---|
| 从 HTML 到图 | `export.py` |
| **从图到图** | `imageops.py`(本分册) |
| 抠图/去背/贴纸化 | `cutout.py`(AI 链路,含 bria-rmbg 许可证红线) |
| 复刻取色/测量盒裁切 | `inspect_ref.py` |

## 2. 铁律三条

1. **任何几何操作前先 `rotate --exif-fix`**——手机图带 Orientation 标签,先旋正再裁切,否则方向错乱。
2. **尺寸只认 `scaffold.py` 的 `SIZES`**——本分册不复制尺寸表;`--presets` 只接受其键名。
3. **平台体积红线一律 `compress` 收口**——淘宝主图 ≤3MB / 详情页单图 ≤500KB / 朋友圈广告 ≤300KB(数值出处 `material-catalog.md`,此处不复制)。

## 3. 场景 → 子命令速查

| 场景 | 命令 |
|---|---|
| 素材能不能用 | `imageops.py probe --in "materials/*.jpg"` |
| 平台要 3:4(允许裁) | `imageops.py fit --in a.jpg --presets xhs` |
| 不许裁边(产品图/含文字图) | `imageops.py pad --in a.jpg --aspect 1:1 --bg edge` |
| 上传超体积 | `imageops.py compress --in a.jpg --target 500KB --format webp` |
| 发九宫格 | `imageops.py slice --in long.png --grid 3x3` |
| 长图按高度切 | `imageops.py slice --in detail.png --max-height 1500 --overlap 24` |
| 发多平台多规格 | `imageops.py derive --in kv.png --presets square,xhs,kv --formats png,webp --matrix` |
| 透明图转 JPG | `imageops.py convert --in a.png --to jpg --alpha flatten --bg '#ffffff'` |
| 文字发糊 | JPG 细文字加 `--subsampling` 场景改走 webp 或 `export.py --scale 2` 重导 |
| 压字看不清 | `imageops.py contrast-check --in 成品.png --box L,T,R,B --fg '#fff' --method p95-1` |
| 要印刷 | `imageops.py dpi-check --in a.png --lpi 175 --print-size 210x297` → 不过红线就回 HTML 重导 |
| 手机图方向乱 | `imageops.py rotate --in phone.jpg --exif-fix` |
| 裁透明边/纯色边 | `imageops.py trim --in cut.png` |
| 圆角卡片化 | `imageops.py card --in p.jpg --radius 48 --shadow 0,8,24,#00000040` |
| 加水印(不压主体) | `imageops.py watermark --in p.jpg --text "©品牌" --position br --opacity 0.35` |
| 纵向拼接 | `imageops.py stitch --in a.png b.png --direction v --gap 24`(公众号双封面仍走 `gzh_cover.py`) |
| 统一多图色调 | `imageops.py tone --in a.jpg --duotone '#1b2a41,#e8f1ff'`(或 `--saturation/--temp`) |
| 模糊铺底转竖版 | `imageops.py blur-bg --in shot.jpg --aspect 3:4`(产品白底图禁用,用 `pad --bg '#ffffff'`) |
| 一条链到底 | `imageops.py pipeline "exif-fix; fit aspect=1:1; compress target=300KB format=webp"` |
| 位图族依赖状态 | `imageops.py deps`(探测到 ffmpeg 编码器级:libwebp/libsvtav1) |

## 4. 质量档位(profile)

唯一真源在 `scripts/_img_core.py` 的 `PROFILES`(web / web-hq / thumb / print / platform)。
本分册不复制数值,只说明何时用哪个:`web` 常规网络图;`platform` 平台上传;`thumb` 缩略图;`print` 印刷前的高质量留存。

## 5. 印刷交付链

`dpi-check`(分辨率够不够)→ 不过红线回 HTML 加 `--scale` 重导 → 够则 `export.py --cmyk` 出印刷件(色彩管理细节在 `print-cmyk.md` / `print-production.md`,本分册不重复)。

## 6. 正反例

- **裁 vs 补**:允许裁边用 `fit`,不允许用 `pad`;**含文字图禁止裁字**(`responsive-reflow.md` 硬红线)。
- **有损 vs 无损**:照片用 `--profile web/platform`;扁平色矢量风量化才划算(渐变图禁量化)。
- **水印**:不压产品主体/人脸;不透明度 ≤0.5;电商主图禁文字牛皮癣。
- **blur-bg**:产品白底图禁用(毁干净白底);用于氛围类海报转竖版。

## 7. 自检项

交付前必跑:`probe`(体积/尺寸/方向机检);压字的成品加跑 `contrast-check`(WCAG ≥4.5:1 正文 / ≥3:1 大字)。

## 8. 与既有资源的关系(防多真相源)

- 尺寸 → `scaffold.py SIZES`;体积红线 → `material-catalog.md`;DPI/LPI → `print-production.md`;对比度口径 → `color-contrast.md`。
- 本分册只给"怎么调用",不重复数值。

## 本册用到的脚本

| 脚本 | 何时用 | 一行示例 |
|---|---|---|
| `imageops.py` | 位图工序唯一入口 | `python scripts/imageops.py --help` |

> 参数的权威说明在脚本自身 `--help`(不在此复制);全量索引见 `docs/scripts.md`。
