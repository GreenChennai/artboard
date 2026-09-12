# artboard 矢量交付手册(SVG / EPS / AI 可编辑 PDF / .ai / 逆向 HTML)

> 把 HTML 海报转成设计软件可编辑的矢量产物,转换相似度 ≥95%(合格)/ ≥99%(优秀)。
> 转换核心:**WebHtml2VectorEdit**(正向)/**VectorEdit2WebHtml**(逆向),
> 文字整句合并、图层简化为背景/内容双层、
> 原生 AI 构建(按 DOM 组件树嵌套真组,--ai)
> **触发规则:正常 artboard 流水线没有这一步——仅当用户明确要"工程文件/矢量文件/
> SVG/EPS/AI 可编辑/.ai"时才运行**(一键入口 scripts/ai_export.py)。

## 0. 快速上手

```bash
# 一次性部署转换工具(poppler + ghostscript 便携版,约 110MB,需要 7-Zip)
python scripts/setup_vector.py

# 一键:项目目录 → 分层 AI 可编辑 PDF(默认产物)
python scripts/ai_export.py <项目目录>

# 追加其他格式 / 真 .ai
python scripts/ai_export.py <项目目录> --svg --eps --outline --ai
```

底层 CLI(需要精确控制画布时):`to_vector.py --source <proj>/src --output
<proj>/export/poster --width 1080 --height 1440 [--formats ai-pdf,svg,eps,...]`

输出(前缀默认 poster):

| 文件 | 说明 |
|---|---|
| `poster-ai.pdf` | **默认交付物**:分层 AI 可编辑 PDF(Illustrator 打开即见图层,PDF 阅读器里可开关图层) |
| `poster-print.pdf` | 平面枢纽 PDF(文字内嵌可改字,SVG/EPS 的衍生源) |
| `poster-outline.pdf` | 免字体依赖 PDF(cairo 重内嵌字形,任何机器视觉一致) |
| `poster.svg` | 全矢量 SVG(转曲,网页/AI/Figma 通吃) |
| `poster.eps` | EPS(老印刷流程) |
| `poster.ai` | 真 .ai 源文件(--ai;Illustrator 亲手写入,含 PGF 私有数据与图层) |
| `poster-reference.png` / `poster-diff-*.png` | 相似度基准与差异热区 |

## 1. 架构:PDF 枢纽 + 双核心

```
                          ┌─ WebHtml2VectorEdit(正向)──────────────────────截图基准 + 平面枢纽 PDF(单页精确尺寸 ≈100%)
HTML ─Playwright settle─▶│    ├─ DOM 分层手术(背景/图形/图片/蒙层/文字)
                          │    │    └─ 每层单独打印 → pikepdf OCG 合成 → ai.pdf
                          │    ├─ pdftocairo -svg -r300 → SVG
                          │    ├─ pdftocairo -pdf → 免字体依赖 PDF
                          │    └─ pdftops -level3 / gs eps2write → EPS
                          │    └─ SSIM 自检(skimage)+ 差异热区
                          └─ VectorEdit2WebHtml(逆向)──────────────────── PDF/ai/eps ─pdftohtml xml + pdftocairo svg─▶ 可维护 HTML(visual/editable)
```

- Chromium 打印的 PDF 是"矢量快照":文字=CIDFont+ToUnicode、渐变=Shading、
  圆角=路径;**图片按原始分辨率直嵌**(实测 breakfast.jpg 867×1300 原样进入,
  JPEG 直通不重压——质量优先策略。
- 矢量管线自行打印**精确尺寸单页** PDF(WPI 的 PDF 分页兼容不适用于矢量交付;
  本核心不依赖 WPI)。
- poppler/gs 打不开非 ASCII 路径:核心内部全部在 ASCII 临时目录转换再搬运。

## 2. 分层与组件化(增强 AI 可编辑性)

**图层只有两层(item 5):背景层 + 内容层。**

- 背景 = 画布底色 + 纯装饰图形(卡片壳、徽章、放射纹等"面板底色克隆");
- 内容 = 全部文字、图片、蒙层。
- 手动干预:元素加 `data-ai-layer="背景|内容"` 强制归层。
- **多画板**:Illustrator 从多页 PDF 生成多画板;双画布品类(名片/三折页)正反面
  各自导出一份即可。

### 组件化编组(--ai 原生构建,item 1/2)

用户要的编组语义:"大矩形里有 4 个小矩形,小矩形里有文字 → 文字+小矩形先成组,
四组再成组,再与外层大矩形成组"。这**只能跟随 DOM 层级**,纯 PDF 反推做不到
(AI 不认手写 OCG,实测恒 1 层)。因此 `--ai` 走原生构建:

```
HTML DOM 组件树(几何/底色/圆角/边框/文字样式/图片)
  ─ExtendScript→ Illustrator 内递归构建:
     元素 = groupItem(真编组,非剪切蒙版)
     子元素 = 组内子组(嵌套层级即 DOM 层级)
     文字 = TextFrame(整句、字号/颜色/字距)
     图片 = placedItem + embed(内嵌)
```

实测(s2-xhs):layers=2、嵌套 7 层真组、0 剪切蒙版、25 个整句 TextFrame、照片内嵌。
v1 边界:渐变/阴影/滤镜不写入 .ai(留空),**极限保真以 ai.pdf/print.pdf 为准**,
.ai 定位为"可维护组件源";文字定位为近似(字体需本机安装)。

### 文字断层修复

Chromium 的 BT 块内本是整句,只是逐字 `Td<Tj>` 定位——AI 把每对拆成独立文字对象。
枢纽与每层打印后,`text_run_merger.py` 自动把同字体+同字号+同基线的连续 Tj
合并为**单条 TJ 数组**(字距差值用内嵌字体 /W 度量表逐字精确复现)。
实测:27/27 块合并、渲染像素零差异、AI 中 27 个整句文字对象
(最长"转给总不吃早饭的 TA · 科普参考非诊疗建议"完整可编辑)。

## 3. 真 .ai(COM 自动化,需本机装 Illustrator)

```bash
python scripts/ai_export.py <项目目录> --ai
```

Illustrator 的可编辑私有数据(PGF)只有它自己能写——`--ai` 用 PowerShell 起
`Illustrator.Application` COM → DoJavaScriptFile 跑 ExtendScript:
打开平面 PDF → **建 图形/图片/文字 三层,按对象类型把全部对象分发入层** →
`saveAs(new IllustratorSaveOptions)` → 得到含 PGF 与图层的真 .ai
(实测 s2-xhs:文字层 136 对象/图片层 14/图形层 71,Creator=Adobe Illustrator 30.0)。
注意:AI 首次启动 30–90s;AI 原本没开着则结束后代为退出;
没装 Illustrator 的机器自动跳过并告警,其余产物不受影响。

## 4. 相似度验收协议(SSIM)

- 基准:与打印同一次页面加载的 Chromium 截图(settle 条件一致);
- PDF 栅格化:pdftocairo -png -r96(**别用 pdftoppm**,其 AA 噪声会把 SSIM 虚压到 0.94);
- SVG:Chromium 直接打开截图;EPS:gs png16m -r96(必须 -dEPSCrop,否则按 A4 摆放虚落 0.68);
- 阈值:**≥0.95 合格,≥0.99 优秀**;SSIM 对小区域内容损失不敏感(徽章全丢仅掉 0.01),
  内容级缺陷必须 judge/人眼终审兜底。

**三样张终值(2026-09-12,全过线)**:

| 样张 | ai-pdf(分层) | print.pdf | svg | eps(poppler) |
|---|---|---|---|---|
| s2-xhs 图文封面 | 0.9781 | 0.9893 | 0.9869 | 0.9750 |
| s2-kv 玻璃拟态 KV | 0.9742 | 0.9742 | 0.9578 | — |
| s2-a4p 印刷海报 | 0.9715 | 0.9875 | 0.9776 | — |

## 5. 矢量安全清单(转换前复制一份Html(不动原Html),修改兼容之后再导出为矢量格式)

| # | CSS 原语 | 判定 | 说明/替代 |
|---|---|---|---|
| 1 | 纯色块/边框/圆角/clip-path/rotate | ✅ 0.990+ | — |
| 2 | 实心 linear/radial 渐变(不透明 stop) | ✅ 0.970+ | — |
| 3 | **硬切透明渐变高亮**(transparent 58%,X 58%) | ⛔ 脏色盖字 | 单色不透明渐变垫底 + background-size:100% 42% + box-decoration-break:clone |
| 4 | **伪元素高亮** | ⚠️ | 折行 span 上绝对定位宽度归 0 → 用 #3 |
| 5 | **mix-blend-mode** | ⛔ 0.942 色偏 | 预混成纯色 |
| 6 | **渐变字 background-clip:text** | ⛔⛔ 0.869 丢字 | 改实色字 |
| 7 | **repeating-conic-gradient** | ⛔ 打印即丢(散点) | clip-path 楔形细条旋转(a4p 24 根实测通过) |
| 8 | **alpha-stop 渐变 + border-radius** | ⚠️ 转 SVG 出软蒙版边界细线 | 光晕用不透明等价色 |
| 9 | box-shadow/text-shadow/drop-shadow | ✅ 0.982+(PDF 里转位图,视觉无损) | — |
| 10 | rgba 常量透明卡片 / 照片 cover / text-stroke | ✅ 0.977+ | — |
| 11 | 内联 `<svg>` 图形 | ⚠️ 打印完美;转 SVG 可能有发丝线伪影 | 几何装饰优先 CSS 原语 |

**五条禁令**:①硬切透明渐变 ②mix-blend-mode ③渐变字 ④conic-gradient ⑤渐变 alpha-stop 压圆角。

## 6. 逆向:VectorEdit2WebHtml(矢量 → HTML)

```bash
python scripts/vectoredit2webhtml.py poster-ai.pdf rebuild.html            # 视觉完整
python scripts/vectoredit2webhtml.py poster-print.pdf rebuild.html --mode editable
```

| 输入 | 处理 |
|---|---|
| PDF / .ai | pdftohtml -xml(文字坐标/字号/颜色 + 图片位)+ pdftocairo -svg(矢量底景);**多页支持**(--pages 选页,逐页自包含 HTML) |
| EPS | gs -dEPSCrop 转 PDF 再走上述管线(EPS 无透明已压平,视觉与源一致) |
| SVG | 直接内嵌(文字已转曲,**无法还原字串**——要可编辑文字用 PDF/.ai 输入) |

**往返鲁棒性(2026-09-12 实测)**:真实作品集 73 页/806MB(A4 横版)抽第 1/25/73 页
做 pdf→html→pdf→html 往返:渲染 SSIM 0.936–0.945(收敛型损失,首轮后稳定,
验收线 ≥0.93),**最长文字串 100% 保留**;文字块数因再分段增加(5→7 等)属
pdftohtml 重分段,内容不减。透明文字层 + 矢量底景是往返稳定的根基。

| 模式 | 内容 | 用途 |
|---|---|---|
| visual(默认) | 矢量底景(SVG data-uri,视觉 100%)+ 透明可选文字层 | 存档/复制文字/交付预览 |
| editable | 真实彩色文字 + 照片 img(**无装饰矢量**) | 改文案后重走 WebHtml2VectorEdit 再导出 |

## 7. 工具部署与许可

`python scripts/setup_vector.py`(路径写 config.json `poppler_dir`/`gs_path`;
环境变量 ARTBOARD_POPPLER / ARTBOARD_GS 可覆盖):

| 工具 | 许可 | 来源 | 用途 |
|---|---|---|---|
| poppler 26.x | GPL-2/3 | oschwartz10612/poppler-windows | pdftocairo/pdftops/pdftohtml/pdfimages |
| Ghostscript 10.x | AGPL 双许可 | Artifex 官方安装器 7-Zip 解包便携化(免管理员,**绝不静默运行安装器**——UAC 会被全屏应用挡住挂起) | EPS 转曲、EPS 栅格校验、EPS→PDF |

二进制不进 git;技能仅子进程调用。gs 可选:缺失时 SVG/print/outline/poppler-EPS
全可用,仅 gs-EPS 引擎与 EPS 校验降级。Python 依赖:playwright + pikepdf +
scikit-image + pillow(pip 安装)。

## 8. 边界与已知限制

- 长图(long,高>2400px)暂不走矢量交付;双画布品类正反面各导一份。
- 分层 SSIM 略低于平面(面板克隆 + 分层合成开销,实测 0.97–0.99 仍过线);
  ai.pdf 与 print.pdf 并存就是为了"可编辑性"与"极限保真"各取所需。
- AI 打开 print.pdf 缺字体时会替换(交付说明带"先装 fonts/ 字体");
  合成粗体/斜体跨查看器不一致 → 字体必须带真实字重(fonts/ 库已满足)。
- EPS 无透明;gs eps2write 遇透明整页栅格化;gs 10.08 pdfwrite 转曲有褪色坑
  (0.969)+ ColorImageFilter=/DCTDecode 触发 rangecheck——转曲 PDF 主选
  pdftocairo -pdf(0.9885),别加该参数。
- 动图海报先收敛终态再转矢量(与 M2 一致)。

## 9. 排障速查

| 症状 | 处置 |
|---|---|
| TOOL_MISSING | setup_vector.py;或 config.json 手填 poppler_dir/gs_path |
| SVG 里高亮/渐变字脏块丢字 | §5 禁令 1/3,改 HTML 重转 |
| SVG 渐变色块外圈细线方框 | §5 禁令 5:alpha-stop → 不透明等价色 |
| 徽章放射纹打印即散点 | §5 禁令 4:conic → clip-path 楔形 |
| SSIM 0.94 左右但看图正常 | 换 pdftocairo 栅格化(§4 陷阱) |
| EPS 渲染偏移/白边 | gs 加 -dEPSCrop |
| 转曲后想改文案 | 回 HTML 改字重转;或逆向出 editable HTML 改完重导 |
