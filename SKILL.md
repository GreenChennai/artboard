---
name: artboard
description: 用 HTML/CSS 绘制平面设计级图片并导出成品的海报工作室。输入文案直出、给图复刻、或换风格改配色,产出海报/banner/小红书封面/主KV/信息长图(PNG/GIF/MP4/PDF),并为视频制作场景卡(口播信息卡/图解动画卡/片头尾,支持出入场动画)。风格像 Illustrator/Photoshop 做的设计图,不是网页交互风。当用户想要:做海报、出图、画封面、小红书配图、banner、KV 主视觉、信息长图、数据图、动态海报、GIF、视频信息卡、科普动画卡、把文案变成图片、复刻一张设计图、换风格重做时使用。Create poster/banner/KV/social-cover/infographic images from copy or reference images via HTML rendering.
version: 1.7.2
---

# artboard · HTML 海报工作室

**定位**:把文案/图片变成"平面设计成品图"。不调用 AI 生图,而是写 HTML/CSS
(有护栏、风格库、字体库),经 WPI 渲染导出 PNG/GIF/MP4/PDF;
用户要矢量/工程文件时才走 WebHtml2VectorEdit(**正常流水线无此步**)。

## 流水线(Step 0–7,含 1.5/4.5 两个子步,细则见 references/pipeline.md)

```
Step 0 预检     scripts/preflight.py   — 有 FATAL 才停(WPI 缺失已降级 WARN,可走兜底);
                                          ffmpeg 缺失且要动图 → 先问用户
Step 1 追问+路由 references/intake.md   — 五问(用途/尺寸/风格/配色/素材)打包问完带推荐;
                                          B/C 模式只问用途+尺寸;用户明说「直接做」才可跳过
Step 1.5 设计简报  输出「生图式提示词」(画面 + 风格/配色/字体/素材);
                                          用户确认或说「直接做」即出图;此后改稿不重跑,见 Step 6
Step 2 选风格   下表 → references/styles/<slug>.md
Step 3 选字体   fonts/README.md 两级筛查 → ≤3 款
Step 4 写图     scripts/scaffold.py 建项目;电商/食品/吉祥物类先走 Step 4.5
Step 4.5 素材   references/materials.md — 用户图抠图(cutout.py)/ 图库搜图(fetch_asset.py)/
                                          图片内容拿不准 → VQA 解读(config.json vqa_path)
Step 5 导出     scripts/export.py(WPI)→ 失败走 export_fallback.py(仅 PNG)
Step 6 自检+改稿 Read 导出图 → 过自检清单 → 修复重导(≤2 轮);
                用户不满意 → **不重新生成**:按用户指定部位改现有 HTML(同 AI 生图的局部重绘)
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

> 尺寸:先查 `references/sizes-common.md`(默认入口),查无再翻 `material-catalog.md`(40+ 物料);
> 18 个画布预设的真实定义在 `scripts/scaffold.py` 的 `SIZES`。

## 资源索引(按需读取,禁止批量预读)

> **读取纪律(省 token)**:只读**当前任务需要**的文件;本表即路由表——
> "何时读"列决定是否打开;风格分册一次只读命中的那一份;其余一律不读不解析。

| 资源 | 路径 | 何时才读 |
|---|---|---|
| 设计护栏(硬规则) | references/guardrails.md | **每次出图必读**(一次) |
| 流水线细则 | references/pipeline.md | 流程不确定时 |
| 风格分册 | references/styles/<命中项>.md | 选定该风格时,只读命中的 1 份 |
| 风格系统 | references/style-system.md | 需要布局原型/配色 tokens 时 |
| **构图与版式骨架** | references/composition.md | 选完风格之后、写 HTML 之前;或画面"看着散/没重点"时 |
| 视觉特效 43 式 | references/effects.md | 需要特效配方时(通常写 HTML 时) |
| 标题手法库 | references/title-fx.md | 标题需要描边/蒙版/错位等处理时 |
| 物料尺寸总表 | references/material-catalog.md | 需要非常规物料尺寸/平台规范时(40+ 物料) |
| 排版细则 | references/typography-rules.md | 自检发现断行/层级/留白问题时 |
| 中文排版 CSS 落地 | references/cjk-typography-css.md | 写中文正文/标题时(标点挤压/中西文间距/断行的实现) |
| 数字·单位·日期 | references/numeric-typography.md | 版面出现价格/百分比/统计/日期/序号时 |
| 数据可视化规范 | references/dataviz.md | 版面出现图表/数据卡/排行榜时 |
| **对比度与色彩工程** | references/color-contrast.md | 定配色 tokens、文字压图、自检"看不清"时(WCAG 定义 + 遮罩数值 + 色盲) |
| 一稿多尺寸重排 | references/responsive-reflow.md | 同一设计要出多个画布比例时 |
| 品牌一致性 | references/brand-system.md | 用户给了品牌色/logo/VI,或一次做多张同品牌物料 |
| 素材分册 | references/materials.md | 任务涉及图片素材时 |
| 图片复刻协议 | references/replicate.md | 复刻/换风格任务(B/C 模式)开工时必读(一次) |
| 需求追问 | references/intake.md | 每次新任务开工前(一次) |
| 常用物料速查 | references/sizes-common.md | 定尺寸时先查(默认入口) |
| 动效分册 | references/animation.md | 动图任务(GIF/MP4)或**视频桥场景卡**(口播信息卡/图解卡)时 |
| 导出手册 | references/export.md | 导出参数/故障不确定时 |
| 矢量交付手册 | references/vector-export.md | 用户要 SVG/EPS/AI 可编辑 PDF/.ai/可编辑矢量时(必读) |
| 品类规范 | references/formats/<品类>.md | 选中印刷/PPT 品类时,只读命中 1 份(注意 slug `slide` 的文件是 `ppt.md`) |
| 印刷 CMYK 流程 | references/print-cmyk.md | 印刷任务定色时(TAC/单色黑/安全色谱) |
| 印前与后工艺 | references/print-production.md | 用户提"印刷/打样/烫金/UV/模切/专色/裁切线"时 |
| 风格气质总表 | references/styles-catalog.md | 用户需求模糊、需要匹配方向时 |
| 新增风格指南 | references/style-guide.md | 仅当要新建风格分册 |
| **设计评审打分表** | references/design-review-rubric.md | Step 6 自检的两个时机(首版完成 / 用户要求) |
| 字体库 | fonts/README.md | 选字体时(两级筛查) |
| 参考案例 | assets/cases/*.html | 写 HTML 需要参照时,只读命中风格的 1 份 |
| vendor/图标/插画包 | assets/… | 引用具体文件时,不预读 |
| 模型下载 | scripts/fetch_model.py | 本地 VQA 模型缺失且需要时 |
| 环境部署 | scripts/setup_wpi.py / setup_ffmpeg.py | 预检报缺失时 |
| 词汇表·术语消歧 | docs/glossary.md | 术语含义或取值口径有疑问时 |

## 脚本(主线;完整清单见 README)

```bash
S="<skill 目录>/scripts"

python $S/preflight.py                        # 预检(每次开工先跑)
python $S/scaffold.py <slug> --size xhs --fonts 思源黑体,霞鹜文楷
python $S/export.py --source <proj>/src --output <proj>/export/o.png \
    --width 1080 --scale 2 --height 1440      # 导出主路径(固定尺寸必带 --height)
python $S/export_fallback.py --source <proj>/src/index.html \
    --output <proj>/export/o.png --width 1080 --scale 2   # 兜底(仅 PNG)
python $S/make_bats.py <项目> --embed         # 给每个 HTML 生成"导出-<名字>.bat"双击即出图
python $S/ai_export.py <项目目录> [--svg --eps --ai]      # 矢量/工程文件(用户明确要才跑)
```

> 素材(`fetch_asset/cutout/vqa`)、复刻(`inspect_ref/compare`)、字体(`fetch_font/add_font`)、
> 环境部署(`setup_*`)、二维码/打包/换算 的完整参数在 **README「脚本一览」** 与各自分册
> (`materials.md` / `replicate.md` / `export.md`),用到时再查,不预记。

- 项目落盘:`config.json` 的 `studio_dir` 下 `<slug>/`(src/ + export/)。
- **瘦身影子(默认)**:src/fonts、src/vendor 是指向 Skill 资产库的目录联接,零拷贝;
  交付迁移用 `pack.py` 打包自包含 zip;`--embed-fonts` 则真拷贝(体积大,单件交付用)。
- 环境变量 `ARTBOARD_WPI` / `ARTBOARD_FFMPEG` / `ARTBOARD_STUDIO` 可临时覆盖 config.json。

## 铁律(违反任何一条 = 重做)

1. 固定画布 + `overflow:hidden`,禁滚动依赖/`100vh`/`position:fixed`。
2. 离线渲染:HTML 零 CDN 引用;字体/vendor 一律复制进项目。
3. 一图一个焦点、层级 ≤3 层、强调 ≤2 处、特效 ≤3 种、字体 ≤3 款。
4. 文案逐字来自用户,不编造数据与条款。
5. **自检只在两个时机触发**:①首版 HTML 完成时;②用户要求检查时。之后的用户改稿一律定点修改,不自动自检不派子代理(省时省 token)。
6. 动图**分两模式**(数值细则见 references/animation.md §〇):
   **模式 P 海报循环**——无缝循环,终态必须仍是合格静态海报;
   **模式 S 视频场景卡**(口播桥/图解卡)——五段式一次性时间轴,全 finite 禁 infinite、
   必须有出场,导出 MP4。
7. **电商/食品/吉祥物类海报必须有真实素材**——产品本体只能用户提供;爬虫图自动带 `版权风险-` 前缀,交付时列出并提醒更换;抠图默认模型链禁用 bria-rmbg(商用付费)。
8. **开工前先过 intake 五问**(用途/尺寸/风格/配色/素材),用户明说「直接做/全按推荐」才可跳过;跳过也必须在开工前复述全部假设。
9. 二维码占位在**终稿前**用 `scripts/qr.py generate` 换成真码;成品码宽 ≥ 版面宽 8%、四周留白 ≥1 模块、纠错用 H 级(内嵌 logo 时)。
10. **矢量/工程文件导出不在默认流水线**:仅当用户明确要 SVG/EPS/AI 可编辑 PDF/.ai/工程文件时才跑 `ai_export.py`(vector-export.md);主动出工程文件=过度交付。

## 环境配置

路径与 key 统一在技能根目录 **`config.json`**(`config.example.json` 是全键模板);
脚本经 `scripts/_config.py` 读取,改完即时生效。
依赖:`pip install -r requirements.txt`,矢量交付再加 `requirements-vector.txt`。
