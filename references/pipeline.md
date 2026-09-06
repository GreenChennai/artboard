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
用自身视觉能力读图,**不调外部 OCR 工具**。读图顺序:
1. **版式骨架**:画布比例 → 分区(几栏几行)→ 视觉动线(Z 型/C 型/中轴)→ 网格还是自由布局。
2. **文案逐字**抄录(不确定的字标注待确认)。
3. **色彩**:估 5 个关键 hex(底/主文/主色/强调/辅助),说明判断依据。
4. **字体气质**:衬线/黑体/手写/装饰 + 字重对比 + 字距感觉 → 到字体库选最接近款。
5. **装饰语言**:贴纸/线框/渐变/噪点/照片处理方式。
默认**高保真复刻**;用户明说「可以改良」才允许按护栏优化细节。

### 模式 C · 换风格 / 改配色
- 输入是 artboard 项目 → 只动 `:root` tokens + 字体声明 + 装饰层,内容区结构保持。
- 输入是用户 HTML → 先提取内容结构,再按目标风格分册重写样式层。
- 输入是图片 → 先走模式 B 拿到结构,再按本模式换装。

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

### Step 4.5 素材处理(细则见 materials.md)

判定:这张图的风格**必须**有真实照片/素材吗?(电商促销/食品/人物吉祥物 = 必须;科技 KV/数据长图/编辑排版 = 可选)
需要 → 按序取材:

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

## Step 6 自检循环(上限 2 轮)

1. **Read 导出的 PNG**(必须看图,不能只看代码)。
2. 过 `guardrails.md` 第 7 节的 7 条自检清单 + 风格分册的禁则。
3. 发现问题 → 改 HTML → 重导 → 再看。**2 轮后仍有小瑕疵:交付并明确列出已知瑕疵**;有 FATAL 级问题(文字溢出/字体没加载)→ 告知用户并给修复建议。

## Step 7 交付

汇报:项目路径、成品图路径+尺寸、风格/字体/特效清单、自检结论、已知瑕疵。
提示可选后续:换风格(模式 C)/ 出动图版(M2)/ 出 PDF / 换尺寸重导。

---

## 动效规范(M2 生效,现在写入案例时禁用动画)

- 一切动画必须**无缝循环**,单循环 2–6 秒,总录制时长 ≤ 15 秒。
- fps ∈ {10, 20, 25, 50}(GIF)——循环时长须能被帧间隔整除(如 25fps 下循环 2.0s / 2.4s / 3.2s)。
- 只用 `transform` / `opacity` / `background-position`(可被逐帧采样的属性);**禁用依赖交互/滚动/音频的动画**。
- 动效模式库、缓动 token、无缝循环写法、导出自检 → **references/animation.md**(M2 已启用)。
- 录制从页面加载完成后开始:入场动画可能被错过,**动图主体靠循环表达**。
- 导出:`--format GIF --fps 25 --max-wait 6`(无 ffmpeg 时 Pillow 回退);MP4 需 ffmpeg。
