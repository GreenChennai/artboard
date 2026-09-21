# 品类规范 · PPT 页(slide)

> 介质品类:16:9 演示页。**输出为图片序列/PDF**(不是网页翻页 PPT)——每页一个 HTML,
> 逐页导出 PNG,再合 PDF;需要真翻页 PPT 时图片可直接贴进 PowerPoint/WPS。

## 画布与导出

- 每页画布 **1280×720**(16:9),`--scale 2` → 2560×1440 高清页。
- 多页工作流:`scaffold.py <slug> --size slide` 后,每页一个 HTML
  (`slide-01.html` 封面 / `slide-02.html`…),逐页:
  `python scripts/export.py --source <proj>/src/slide-01.html --output export/slide-01.png --width 1280 --scale 2 --height 720`
- **固定尺寸品类优先锁 --height**:画板尺寸一律显式声明
  (`.poster{width:1280px;height:720px;overflow:hidden}`)+ 导出带
  `--width 1280 --height 720`,别让引擎「按内容回填」——绝对定位元素一多,
  回填出来的画板会比 720 高一截,同组页面尺寸就不齐了。批量脚本必须检查
  结果 JSON 的 `degraded_artboard`;为 `true` 说明尺寸是内容推导值,要人工核对。
- 合 PDF(全页导入 PowerPoint 亦可):
  `python -c "from PIL import Image; Image.init(); import glob; pages=[Image.open(p) for p in sorted(glob.glob('export/slide-*.png')); pages[0].save('export/<slug>.pdf', save_all=True, append_images=pages[1:], resolution=192)"`
- **合 PPTX(交付 PPTX 时)**:本机无 Office/LibreOffice 也能做——安装
  `pip install python-pptx`,按 16:9 版式(13.333×7.5 in)逐页满幅贴 PNG:
  ```python
  from pptx import Presentation; from pptx.util import Inches
  prs = Presentation(); prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
  for p in sorted(glob.glob("export/slide-*.png")):
      prs.slides.add_slide(prs.slide_layouts[6]).shapes.add_picture(p, 0, 0, prs.slide_width, prs.slide_height)
  prs.save("export/<slug>.pptx")
  ```
  贴图版不可编辑,但版式零漂移;要可编辑文字改走 `ai_export.py --pptx`(真文本 shape)。
- 最小字号 **18px**(1280 画布;投影场景正文 ≥22px)。内容放不下:**先删文案/拆两页,不许压字号**。

## 多页共享样式(>8 页必读)

一页一个 HTML 没有共享 CSS 文件机制,页面一多就会**样式漂移**:某个共享类
(如 `.navy{background:…}`)写在了某一页的专属 `<style>` 里,别的页加了类名却没规则
——于是「深底页配白字」变成「浅底配白字」,主标几乎不可见。

做法:**用生成器脚本统一注入**,不要在每页手抄:

1. 把 tokens + 共享类 + 页眉页脚写在一个 `gen.py` 里(一份字符串模板);
2. 每页只写"本页独有的内容与版式",由 `gen.py` 循环渲染成 `slide-XX.html`;
3. 改 tokens / 改页脚改一处,全部页面同步——也就不会漏定义。

验收:导出前用 `python scripts/check_overflow.py <proj>/src`(传**目录**,
逐页查),再用同一份 `gen.py` 重生成一次,确认无 diff。

## 字号阶(1280×720 画布;中文标题长度分档)

| 元素 | 字号 | 说明 |
|---|---|---|
| 封面主标 | 72–96px | **一行 ≤8 字**;9–12 字降到 60–72px;更长先改写 |
| 页标题 | 44–56px | 一行 ≤14 字 |
| 小节标 | 30–34px | |
| 正文要点 | 22–26px | 每页要点 ≤4 条,每条 ≤18 字 |
| 数据大字 | 90–130px | 一页最多一个数据主角 |
| 页脚/meta | 14–16px | 页码 + 章节标记 |

字重阶梯:**越大越细,越小越粗**——大标题可用 600-700,小字必须 500+(同页内小字字重 ≥ 大字字重)。

## 页面版式登记表(从下表选,不临时发明)

| 版式 | 结构 | 适用 |
|---|---|---|
| 封面 | 主标 + 副标 + 日期/署名,视觉锤占 40% | 开场 |
| 章节页 | 章节号大字 + 标题,极简 | 分幕 |
| 论点页 | 一句话主张 + 2-3 支撑点 | 观点 |
| 数据页 | 大数字主角 + 图表 + 一句解读 | KPI/结果 |
| 对比页 | 左右分栏(Before/After、A vs B) | 方案对比 |
| 流程页 | 横向步骤线 3-5 步 | 方法/时间线 |
| 引用页 | 大引号金句 + 署名,大量留白 | 转折/强调 |
| 图文页 | 图占 55% + 侧栏要点 | 产品/案例 |
| 收尾页 | Takeaway 3 条 + 联系方式 | 收束 |

**多页节奏规则**:① 一页一主张;② 不许连续 3 页同底色/同版式;③ 8 页以上至少各 1 页深底与极简页换气;
④ 页数换算:15 分钟演讲 ≈ 10 页,30 分钟 ≈ 20 页。
**叙事弧**(无大纲时的骨架):钩子 1 页 → 定调 1–2 页 → 主体 3–5 页 → 转折 1 页 → 收束 1–2 页。

## 调性禁则

1. 禁把 Word 文档贴上页:每页只回答一个问题。
2. 禁 <18px 字号、禁要点超 4 条、禁整段文字。
3. 禁页间样式漂移:全组 tokens/字体/装饰语言一致(重复原则)。
4. 禁脱离品类画布:所有页同尺寸;混尺寸用导出倍率统一分辨率。
