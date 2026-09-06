---
name: artboard
description: 用 HTML/CSS 绘制平面设计级图片并导出成品的海报工作室。输入文案直出、给图复刻(OCR/VQA)、或换风格改配色,产出海报/banner/小红书封面/主KV/信息长图(PNG/GIF/MP4/PDF)。风格像 Illustrator/Photoshop 做的设计图,不是网页交互风。当用户想要:做海报、出图、画封面、小红书配图、banner、KV 主视觉、信息长图、数据图、动态海报、GIF、把文案变成图片、复刻一张设计图、换风格重做时使用。Create poster/banner/KV/social-cover/infographic images from copy or reference images via HTML rendering.
---

# artboard · HTML 海报工作室

**定位**:把文案/图片变成"平面设计成品图"。AI 不画像素、不用 AI 生图——而是像设计师一样
写 HTML/CSS(有护栏、有风格库、有字体库),再用 WPI 渲染导出 PNG/GIF/MP4/PDF。

## 流水线(7 步,细则见 references/pipeline.md)

```
Step 0 预检     scripts/preflight.py   — FATAL 停;ffmpeg 缺失且要动图 → 先问用户
Step 1 追问+路由 references/intake.md   — 五问(用途/尺寸/风格/配色/素材)打包问完带推荐;
                                          B/C 模式只问用途+尺寸;用户明说「直接做」才可跳过
Step 2 选风格   下表 → references/styles/<slug>.md
Step 3 选字体   fonts/README.md 两级筛查 → ≤3 款
Step 4 写图     scripts/scaffold.py 建项目;电商/食品/吉祥物类先走 Step 4.5
Step 4.5 素材   references/materials.md — 用户图抠图(cutout.py)/ 图库搜图(fetch_asset.py)/
                                          图片内容拿不准 → VQA 解读(config.json vqa_path)
Step 5 导出     scripts/export.py(WPI)→ 失败走 export_fallback.py(仅 PNG)
Step 6 自检     Read 导出图 → 过 7 条清单 → 修复重导(≤2 轮)
Step 7 交付     汇报路径/尺寸/风格/瑕疵;列「版权风险-」素材并提醒更换
```

## 风格清单(视觉风格)

| 风格 | slug | 一句话 | 推荐尺寸 |
|---|---|---|---|
| 小红书图文封面 | `xhs-cover` | 干货分享 3:4 封面,暖底贴纸手账感 | xhs 1080×1440 |
| 电商大促 | `ecommerce-promo` | 大字报促销,价格与紧迫感 | square/banner |
| 科技发布 KV | `tech-kv` | 深底玻璃拟态,发布级克制 | kv 1920×1080 |
| 数据长图 | `data-longform` | 报告型 2400 宽长图,ECharts 统一图表 | long 2400×auto |

## 品类清单(印刷格式,规范见 references/formats/)

| 品类 | --size | 规范分册 | 要点 |
|---|---|---|---|
| 名片 90×54mm | `card` | formats/card.md | scale 1=300dpi;7pt 可读底线;双面双画布 |
| A4 海报 | `a4p` | formats/a4p.md | scale 2=300dpi;Z 动线;禁荧光色 |
| 三折页 | `trifold` | formats/trifold.md | 双面双画布;折线 x=585/1169;文字禁跨折线 |
| 易拉宝 80×200cm | `rollup` | formats/rollup.md | scale 2=150dpi;顶部/底部盲区;短语化 |
| PPT 页 16:9 | `slide` | formats/ppt.md | scale 2=2560×1440;一页一主张;多页图片序列+PDF |

> 视觉风格与品类是正交的:任何品类可配任何风格(如「名片 × 科技 KV 风」「易拉宝 × 电商大促风」)。
> 没有匹配风格:找最近似 + 告知偏差;或按 references/style-guide.md 新建(先给用户报价)。

## 尺寸预设

| 用途 | CSS 画布 | 导出 |
|---|---|---|
| 小红书 3:4 | 1080×1440 | `--width 1080 --scale 2` |
| 长图 | 2400×内容高 | `--width 2400 --scale 1` |
| 横幅 | 1920×600 | `--width 1920 --scale 2` |
| 主 KV | 1920×1080 | `--width 1920 --scale 2` |
| 方图 / 竖屏 | 1080×1080 / 1080×1920 | `--scale 2` |
| PPT 页 16:9 | 1280×720 | `--width 1280 --scale 2 --height 720`(多页 slide-01.html…) |
| 名片 | 1063×638 | `--width 1063 --scale 1` |
| A4 海报 | 1240×1754 | `--width 1240 --scale 2` |
| 三折页单面 | 1754×1240 | `--width 1754 --scale 2`(正/背各一) |
| 易拉宝 | 2362×5906 | `--width 2362 --scale 2`(=150dpi) |

## 资源索引

| 资源 | 路径 | 说明 |
|---|---|---|
| 设计护栏(硬规则) | references/guardrails.md | 每张图必读必守 |
| 流水线细则 | references/pipeline.md | 三模式路由/动效规范 |
| 风格系统 | references/style-system.md | 布局 6 原型 / 8 组配色 tokens |
| 视觉特效 30 式 | references/effects.md | 噪点/riso/玻璃/霓虹/爆炸贴… |
| 导出手册 | references/export.md | 命令/参数/故障处理 |
| 素材分册 | references/materials.md | 找图(Pexels/Pixabay+爬虫)/抠图/版权风险机制/产品图红线 |
| 需求追问 | references/intake.md | 开工前五问(用途/尺寸/风格/配色/素材),防盲做 |
| 动效分册(M2) | references/animation.md | 十二法则/M3 缓动 token/循环规范/导出命令 |
| 新增风格指南 | references/style-guide.md | 30 分钟登记一个新风格 |
| 风格气质总表 | references/styles-catalog.md | 145 方向速查,模糊需求匹配 + 原子混搭 |
| 品类规范(名片/易拉宝/A4/三折页/PPT 页) | references/formats/*.md | 印刷尺寸/字号下限/折线/盲区/多页组织 |
| 字体库 | fonts/README.md | 5 款开源字体,两级筛查 |
| 参考案例 | assets/cases/*.html | 4 风格各一个"及格线答卷" |
| vendor | assets/vendor/ | echarts.min.js / gsap.min.js |
| 图标 | assets/icons/ | Tabler SVG(内联使用) |
| 插画包 | assets/illustrations/ | Open Peeps/Open Doodles/unDraw(CC0,SVG 换色) |

## 脚本

```bash
S="<skill 目录>/scripts"   # 本目录 scripts/

python $S/preflight.py                                   # 预检(每次开工先跑)
python $S/scaffold.py <slug> --size xhs --fonts 思源黑体,霞鹜文楷   # 建项目
python $S/export.py --source <proj>/src --output <proj>/export/o.png \
    --width 1080 --scale 2 --height 1440                  # 导出(主;固定尺寸带 --height)
python $S/export_fallback.py --source <proj>/src/index.html \
    --output <proj>/export/o.png --width 1080 --scale 2   # 导出(兜底,仅 PNG)
python $S/add_font.py <目录名> --name 显示名 --category 分类 --tags 关键词  # 登记新字体

python $S/fetch_asset.py --query "coffee cup" --theme <主题> --download --limit 6  # 搜图/下载
python $S/cutout.py <图片...> [--sticker] [--shadow] [--model isnet-anime]      # 抠图+后处理
python $S/vqa.py <图片...> [--prompt "问题"]                                    # VQA 解读图片内容
python $S/qr.py generate --data "https://…" --out img/qr.png --logo logo.png    # 二维码(品牌色/内嵌logo)
python $S/qr.py decode <图片>                                                   # 解析二维码(本地 zxing)
```

- 项目落盘:`E:\平日资料\GitHub\artboard-studio\<slug>\`(src/ + export/)。
- 环境变量:`ARTBOARD_WPI`(WPI 根目录)、`ARTBOARD_FFMPEG`(ffmpeg.exe)、
  `ARTBOARD_STUDIO`(工作室目录)——均有默认值,见各脚本头注释。

## 铁律(违反任何一条 = 重做)

1. 固定画布 + `overflow:hidden`,禁滚动依赖/`100vh`/`position:fixed`。
2. 离线渲染:HTML 零 CDN 引用;字体/vendor 一律复制进项目。
3. 一图一个焦点、层级 ≤3 层、强调 ≤2 处、特效 ≤3 种、字体 ≤3 款。
4. 文案逐字来自用户,不编造数据与条款。
5. 交付前必须 Read 导出 PNG 自检,上限 2 轮。
6. 动图(M2 已启用):无缝循环 2–6s、总长 ≤15s、fps∈{10,20,25,50};只用 transform/opacity;
   循环时长能被帧间隔整除;**终态必须仍是合格静态海报**;规范见 references/animation.md。
7. **电商/食品/吉祥物类海报必须有真实素材**——产品本体只能用户提供;爬虫图自动带 `版权风险-` 前缀,交付时列出并提醒更换;抠图默认模型链禁用 bria-rmbg(商用付费)。
8. **开工前先过 intake 五问**(用途/尺寸/风格/配色/素材),用户明说「直接做/全按推荐」才可跳过;跳过也必须在开工前复述全部假设。
9. 二维码占位在**终稿前**用 `scripts/qr.py generate` 换成真码;成品码宽 ≥ 版面宽 8%、四周留白 ≥1 模块、纠错用 H 级(内嵌 logo 时)。

## 环境配置

所有路径与 key 统一放在技能根目录 **`config.json`**(wpi_path / studio_dir / ffmpeg / pexels_key / pixabay_key / huaban_cookie / vqa_path);环境变量(`ARTBOARD_WPI` 等)可临时覆盖。脚本经 `scripts/_config.py` 读取,改 config.json 即时生效。
