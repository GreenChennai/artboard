# artboard 流水线(详细版)

> 总入口 SKILL.md 的 Step 0–6 细则。每一步都有明确的输入、动作、产出。

---

## Step 0 预检(每个任务开始前)

```bash
python "<skill>/scripts/preflight.py"
```

- 输出 JSON + 清单。**有 FATAL → 停止**,把 hint 转告用户。
- `ffmpeg` 缺失 + 任务包含 GIF/MP4 → **先问用户要 ffmpeg.exe 路径**,拿到后设环境变量 `ARTBOARD_FFMPEG` 再继续(用户不提供:GIF 可用 Pillow 回退继续,MP4 明确告知做不了)。
- 字体/vendor 缺失 WARN:静态任务可继续,动图/图表任务先补齐。

## Step 1 需求追问与路由(细则见 intake.md)

**先追问,后开工**:按 intake.md 五问(用途/尺寸/风格/配色/素材)打包发问、每问带推荐、最多追问一轮;
B 复刻/C 换风格只问用途+尺寸;用户明说「直接做/全按推荐」才可跳过,跳过也要复述假设。
用途决定品类与呈现骨架,尺寸确认防默认值误伤。三模式路由:

### 模式 A · 文案直出
从用户文案提炼信息结构:**主标(一句话)/ 副标 / 要点(≤5 条)/ CTA / 元信息(日期·价格·二维码位)**。
要点超过 5 条 → 建议拆多图或转数据长图;主标超过 14 字 → 主动帮用户压缩出 2 个候选。

### 模式 B · 图片复刻(OCR/VQA)
用自身视觉能力读图,**不调外部 OCR 工具**。细则协议见 **references/replicate.md**(开工必读),速记:
1. **先看后量**:网格图上命名分区 → 逐区普查取色(inspect_ref.py),tokens 必须带采样证据,裸眼估的 hex 不进 CSS。
2. **文案逐字**抄录(不确定的字标注待确认)。
3. **素材先裁后生成**:参考图里已有的照片直接按测得 bbox 裁出(img/crops.json 登记),太小/要换图才走素材库。
4. **字体判定无把握不点名**(近似匹配,交付注明)。
5. tokens 契约先行 → 写图 → **分区数字比对**(compare.py --region);差异争议回测量,不对 CSS 瞎补。
默认**高保真复刻**;用户明说「可以改良」才允许按护栏优化细节。

### 模式 C · 换风格 / 改配色
- 输入是 artboard 项目 → 只动 `:root` tokens + 字体声明 + 装饰层,内容区结构保持。
- 输入是用户 HTML → 先提取内容结构,再按目标风格分册重写样式层。
- 输入是图片 → 先走模式 B 拿到结构,再按本模式换装。

## Step 1.5 设计简报(生图式提示词,AI 生图习惯对齐)

五问答完(或用户「直接做」)后、动工前,**先输出一段"提示词"**——模拟 AI 生图用户会看到的 prompt:

```
【画面】一张 1080×1440 小红书封面:暖米纸底上,超大号黑色标题「新手摄影避雷」,
        配斜贴「避雷指南」贴纸与 6 条编号列表;第 3 条带手写批注。
【风格】xhs-cover(dense 知识卡)+ 暖纸 tokens + 荧光笔高亮
【字体】思源黑体 900(主标)/ 霞鹜文楷(批注)/ 得意黑(序号)
【素材】无照片,纯排版 + Tabler 图标
【同款意象】"小红书知识卡片 · 财税避雷风"
```

- 用户看完可直接说「可以,出图」/「把标题换成 XX」——**简报改完才动工,省一轮废稿**;
- 用户已明说「直接做」时,简报随首图一起交付(先做后补);
- 提示词保存进项目 `design-prompt.txt`,后续改稿对照它定位部位。
- **多稿同出为可选模式**:仅当用户要求(「多出几版 / 给几个方案」)或说指令(`多稿` / `出 4 稿`)时启用(细则见 `multi-draft.md`);**默认单稿**——未被要求不主动出多稿。

## 改稿协议(不满不重跑,同 AI 生图的局部重绘)

用户对成图不满意时:**在现有 HTML 上定点修改**,禁止从头重新生成(除非用户明说"重新来一版")。
指哪改哪的明确指令按下表速查;**说不清哪里不满的「模糊愿望」**(不够高级 / 太乱 / 做减法)→ **references/revision-protocol.md**(先诊断再动手,翻译表 + 减法阶梯 + 引导提问)。

| 用户说 | 动作 |
|---|---|
| 「标题换 XX」「价格改 39」 | 只改对应文本节点,重导 |
| 「红色太扎眼」 | 只调 tokens 的 accent/primary,重导 |
| 「整体再紧凑一点」 | 调间距/字号阶,重导 |
| 「换一种构图」 | 同项目新文件(alt-01.html),原版保留对照 |
| 「重新来一版」 | 允许全重做;design-prompt 更新后再动工 |
| 「不够高级 / 太乱 / 做减法 / 说不出但不满」(模糊愿望) | 先诊断到维度,再按 **references/revision-protocol.md** 定点改;不重生成 |

改完重导同一输出路径(或 `*-v2.png` 保留对照),汇报改动点。**改稿不计数于 2 轮自检上限**——
那是 AI 自检;用户驱动的改稿轮次不限。

## Step 2 选风格

读 `SKILL.md` 风格清单 → 打开对应 `references/styles/<风格>.md`。
没有匹配风格:① 找气质最近的风格 + 明确告知偏差;② 或按 `style-guide.md` 现做一个(耗时,先报价给用户)。

## Step 3 选字体

两级筛查:`fonts/README.md` 按分类定大类 → 读候选字体 `INTRO.md` 确认气质与慎用场景 → 定 ≤3 款。
可变字体(思源黑/宋)记得用足字重轴,别只吃 Regular。

## Step 4 建项目 + 写 HTML

```bash
python "<skill>/scripts/scaffold.py" <slug> --size <预设> --fonts <款1,款2>
```

- scaffold 生成 `artboard-studio/<slug>/{src,export}`,复制字体/vendor,产出画布骨架。

> **触发多稿时**(已过 `multi-draft.md §1` 闸门):同一项目 scaffold 只建 1 次,以 `index.html`
> 为母版复制 `draft-a…d.html`,只改差异区(`:root` tokens / 骨架类 / 主视觉层),内容与文案共享;
> 流程与成本纪律见 `multi-draft.md §4/§7`。默认不走此分支。

### Step 4.5 素材处理(细则见 materials.md)

判定:这张图的风格**必须**有真实照片/素材吗?(电商促销/食品/人物吉祥物 = 必须;科技 KV/数据长图/编辑排版 = 可选)
需要 → 按序取材;**照片先定角色再处理**(主体/背景/纹理/氛围,角色决定裁切与色调 → `image-language.md`):

1. **用户自备图**(吉祥物/产品/食品)= 首选:复制进 `src/img/` → `cutout.py` 抠图 + 四件套后处理(产品图 `--shadow`,吉祥物 `--sticker --trim`,卡通图 `--model isnet-anime`)。
2. **图库/爬虫补氛围**:`fetch_asset.py --query <英文效果更好> --theme <主题> --download`,Read 挑图 → 复制进 `src/img/`。
3. **红线**:产品本体只能用户提供;`版权风险-` 前缀的素材交付时必须提醒更换;人像选图避可辨认面孔。
4. 照片统一色调(`fx-duotone`/滤镜)后才上版;抠图件必须带软投影。

之后写内容层:
  - tokens 全走 `:root`(风格分册的色板);
  - 组件可参考风格分册的「组件语言」与 `assets/cases/` 参考案例;
  - 特效从 `references/effects.md` 挑,**一图 ≤3 种特效**;
  - 图标内联:`assets/icons/*.svg` 复制 `<svg>` 内容进 HTML(保持 `stroke="currentColor"`)。

## Step 5 导出

```bash
# 主路径(固定尺寸预设必须带 --height <画布高>,长图不传)
python "<skill>/scripts/export.py" --source "<project>/src" \
  --output "<project>/export/<slug>.png" --width <画布宽> --scale 2 --height <画布高>
```

- 尺寸/倍率表见 `export.md`;失败(error 字段)→ 按 hint 处理 → 兜底:
```bash
python "<skill>/scripts/export_fallback.py" --source "<project>/src/index.html" \
  --output "<project>/export/<slug>.png" --width <画布宽> --scale 2
```

> **触发多稿时**:4 稿 Demo 一律 `--scale 1` 各导一张(`demo-a…d.png`,可并行),再用
> `imageops.py montage` 拼一张 2×2 联络表;仅用户选定转正后才以 scale 2 出成品
> (细则见 `multi-draft.md §5/§7`)。默认仍为单稿导出。

## Step 6 自检循环(仅两个触发时机)

**触发条件(2026-09 用户确立,其余一律不自检不派子代理)**:
① 首版 HTML 完成时自检一遍;② 用户明确要求检查时自检一遍。
用户迭代改稿阶段 → 定点修改重导即可,不自动自检(省时省 token)。

> **"机检"与"自检"是两件事**,别混:
> - **机检**(`check_overflow.py`)= **每次重导前的门禁**,跑一次 3–5 秒、**零 token 成本**,
>   **不受**上面两个时机限制。它做几何量测,查的是肉眼看不见的那两类缺陷
>   (文字出卡片框但没出画布、内容进了字幕带)。
> - **自检**= Agent 的 Read 看图与评审,只在上面两个时机做。
>
> 改稿阶段虽然不自检,但**机检仍要跑** —— 改文案/字号/间距正是溢出最常见的成因。

### 6.0 机检门禁(每次重导前必跑)

```bash
# 静态海报:查容器越框(A/B 类)
python "<skill>/scripts/check_overflow.py" "<project>/src"

# 视频卡 / 会被叠字幕的动图:追加安全区检查(C 类)
python "<skill>/scripts/check_overflow.py" "<project>/src" --safe-area auto
```

- `ok:false` / 退出码 1 → **先修再导**,别导完再改(白导一轮);
- **A/B 类(容器越框)** → 修法见 `card-layout.md §五「一行修复对照表」`;
- **C 类(越出安全区)** → 先精简文案 / 拆卡(比贴边稳);确实装不下才降档:
  `--safe-tier tight`(垂直放宽、左右不动)→ `--safe-tier extreme`(四边 2.5%,有代价);
  细则与代价见 `video-safe-area.md §二`;
- 尺寸由页面实际几何算,不必传 `--width/--height`(长图也可用);
- 装饰越界是设计,加 `data-allow-overflow` 即豁免。

### 6.1 看图自检(触发时)

1. **Read 导出的 PNG**(必须看图,不能只看代码)。
2. 过 `guardrails.md` 排版自检清单 + 风格分册的禁则;视频卡再过 `video-safe-area.md §六`;
   首版完成时可过 `design-review-rubric.md` 打分。
3. 发现问题 → 改 HTML → **重跑 6.0 机检** → 重导 → 再看。
   **2 轮后仍有小瑕疵:交付并明确列出已知瑕疵**;
   有 FATAL 级问题(文字溢出/字体没加载)→ 告知用户并给修复建议。

## Step 6.5 生成一键导出入口(每张 HTML 都要有)

用户改稿后可自己双击导出,不必再叫 Agent。写完 HTML 后:
```bash
python scripts/make_bats.py <项目> --embed
```
给 `src/` 下每个 .html 生成同名 **`导出-<名字>.bat`**,双击即导出该张:

- 画布宽/倍率/高度从 `project.json` 读,不写死;
- 默认出 PNG + PDF 到 `../export/`;`--formats` 可改;
- HTML 含 `@keyframes` 且 ffmpeg 在 → 自动追加 GIF / MP4;
- `project.json` 标 `"print": true` → 追加 `--cmyk`(CMYK PDF + TIFF);
- `--embed` 让 bat 自带兜底:主引擎失败自动改调 `export_fallback.py`(仅 PNG);
- bat 内写死当前 Python 与 export.py 的绝对路径(双击时 PATH 里通常没有 python)。

补充:`scaffold.py` 建项目时还会投放 **`导出.py`**(双击导出**全部** HTML),
与上面的单张 bat 互补。**两者都必须在 `<项目>/src/` 下运行** —— 直接在 `scripts/` 下
执行会在 skill 目录里生成多余产物。

## 版本与命名规范(多版稿 / 多尺寸 / 备选稿;09)

> 一张图改三轮、多尺寸同出之后,`index_final_final2.html` 就是灾难。约定四条:

| 场景 | 命名 | 例 |
|---|---|---|
| 同一设计第 N 版(定点改稿留档) | 原名 + `_v2/_v3` | `index.html` → `index_v2.html` |
| 同项目的备选方向(改稿期三版对比) | `index_alt-<方向字母>` | `index_alt-a.html` / `index_alt-b.html` |
| 同设计多倍率 / 多尺寸产物 | 倍率或尺寸后缀 | `index@2x.png`、`kv_1080x1920.png` |
| 落选稿 / 旧版归档 | 移入 `src/_archive/`,**不删** | `src/_archive/index_v2.html` |

- **正稿永远是 `index.html`**:scaffold、机检 `check_overflow.py`、一键导出都以它为默认入口——在 `_v3` 上继续改而不回写正稿 = 下次重导拿到旧图;
- 版本号只增不减、备选字母按三版对比的方向序(保守/激进/折中 = a/b/c),看到文件名就能还原决策历史;
- 归档不删除:用户回头要旧方向时直接取;`export/` 里的旧导出图同理带版本后缀共存。

## Step 7 交付

汇报:项目路径、成品图路径+尺寸、风格/字体/特效清单、自检结论、已知瑕疵。
**字体授权一句话**(商用交付必附):注明本图所用字体的来源与许可——`fonts/` 库字体报目录名(许可见各 `<目录>/INTRO.md`,开源可商用),用户自备字体注明"用户提供、许可自查";理由:字体授权争议是商用交付最常见的售后风险,一句话存档即可免责。
**甲方要正式「设计说明」时**(09-H,轻量):把上述汇报扩成一段即可——设计概念一句话(取自 `design-prompt.txt`)+ 使用规范三条(留白比例 / 最小展示尺寸 / 禁改色禁拉伸),**不新开模板文件**,免得第二真相源。
提示可选后续:换风格(模式 C)/ 出动图版(M2)/ 出 PDF / 换尺寸重导。

---

## 动效规范(M2 已启用)

- 一切动画必须**无缝循环**,单循环 2–6 秒,总录制时长 ≤ 15 秒。
- fps ∈ {10, 20, 25, 50}(GIF)——循环时长须能被帧间隔整除(如 25fps 下循环 2.0s / 2.4s / 3.2s)。
- 只用 `transform` / `opacity` / `background-position`(可被逐帧采样的属性);**禁用依赖交互/滚动/音频的动画**。
- 动效模式库、缓动 token、无缝循环写法、导出自检 → **references/animation.md**(M2 已启用)。
- 录制从页面加载完成后开始:入场动画可能被错过,**动图主体靠循环表达**。
- 导出:`--format GIF --fps 25 --max-wait 6`(无 ffmpeg 时 Pillow 回退);MP4 需 ffmpeg。
