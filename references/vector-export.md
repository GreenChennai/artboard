# artboard 矢量交付手册(v1.9:Kiln 原生直出 SVG / PDF(CID 中文真文本)/ EPS / AI / PPTX)

> 把 HTML 海报直出为设计软件可编辑的矢量产物。九格式同源:一次渲染,
> SVG/PPTX 真文本、PDF CID 中文真文本(可选中复制)、EPS/AI(PDF 兼容流)。
> 引擎:**Kiln**(VellumBench 原生,零浏览器/poppler 依赖)。
> **触发规则:正常 artboard 流水线没有这一步——仅当用户明确要"工程文件/
> 矢量文件/SVG/EPS/AI 可编辑"时才运行**(一键入口 scripts/ai_export.py)。
> 绘制侧(怎么画:几何构成 / 图标语言 / 插画语言)见 `vector-drawing.md`;本册只管导出与交付安全。

## 0. 快速上手

```bash
# 一键:项目目录 → SVG + PDF(默认产物)
python scripts/ai_export.py <项目目录>

# 追加其他格式
python scripts/ai_export.py <项目目录> --eps --ai --pptx

# 双面 A4：一个 AI 文件内两个画板（按参数顺序排列）
python scripts/ai_export.py --source front/index.html --source back/index.html --ai

# 对照参考 PNG，未达到 97 分直接失败
python scripts/ai_export.py poster --ai --reference poster.png --similarity 97

# 细粒度控制(指定输出目录与格式清单)
python scripts/to_vector.py --source <项目>/src --outdir <项目>/export --formats svg,pdf,eps
```

引擎定位:config.json `kiln_cli_exe` → 环境变量 `ARTBOARD_KILN_CLI` →
`<工作区>/VellumBench/dist/Kiln-noGUI-CLI.exe`。没有引擎?跑 `scripts/setup_kiln.py`。

## 1. 格式能力矩阵(v1.9)

| 格式 | 文本 | 图层 | 中文 | 适用 |
|---|---|---|---|---|
| SVG | 真文本 `<text>`/`<tspan>` | 分组 | ✅ | 网页/设计工具复用 |
| PDF | 真文本(CIDFontType2/Identity-H) | OCG | ✅ 可选中复制 | 打印/交付 |
| Ai | 同 PDF(PDF 兼容流,ADR-0008) | **背景 / 内容两层** | ✅ | Illustrator 打开；多源为多画板 |
| EPS | Latin 真文本;中文轮廓 | 无 | 轮廓化 | 老印厂 |
| PPTX | 真文本 shape | shape 树 | ✅ | 汇报/二次编辑 |

已知边界:中文在 EPS 中仍可能轮廓化(不可改字);可编辑交付请使用 AI/PDF，
AI 路线保留 CID 真文本、避免 Type3/逐元素剪切蒙版；`@property` 数字滚动为静态终值。

## 2. 与 v1.8 的差异

- poppler + Ghostscript + pikepdf + scikit-image 全链退役(setup_vector.py 删除)
- WebHtml2VectorEdit / VectorEdit2WebHtml / text_run_merger 退役(Kiln 原生直出)
- 中文 PDF 从"整句轮廓"升级为"CID 真文本可选中"
- 相似度自检(SSIM)随浏览器基线退役;保真度走上游 bench/fidelity.py

## 3. 逆向重维护(kiln-cli import)

外部矢量稿(设计师交付的 PDF/AI/SVG)→ 规范化 HTML:

```bash
Kiln-noGUI-CLI.exe import --source poster.pdf --output <项目目录>   # PDF/AI:需 pdfium.dll(PDFIUM_DLL 指定)
Kiln-noGUI-CLI.exe import --source poster.svg --output <项目目录>   # SVG:纯 Rust(usvg),零外部依赖
```

- 产出 index.html + styles/main.css(绝对定位规范化形态)+ assets/
- 文本可编辑(提取真实字符串,不转曲);路径/图像分别映射
- PDF v1 边界:pdfium 对象取色未暴露(统一近似色);路径以盒近似
- SVG v1 边界:矩形/圆角矩形(半径反推)/圆/椭圆/文本/嵌入位图逐对象
  精确映射;其余自由路径以包围盒矩形近似并给警告;渐变取中点色;
  filter/mask/clipPath 跳过

## 4. 矢量安全清单(五条禁令)

以下 CSS 原语在 Kiln 原生渲染下无法忠实转矢量(要么丢弃要么脏色),
**目标产物含矢量交付时,源 HTML 应避免**:

① 硬切透明渐变(`linear-gradient` 带 transparent 端点)——矢量端变实色,渐变断裂
② mix-blend-mode —— PDF/EPS 无对应混合语义,整层脏色
③ 渐变字(background-clip:text)——文字退回纯色
④ conic-gradient —— 解析为降级填充
⑤ alpha 渐变 stop 压圆角 —— 圆角外溢出杂边

## 5. 验收清单

- [ ] SVG 在浏览器/设计工具打开,文字可选中、中文无豆腐块
- [ ] PDF 文本可选中复制(中文逐字正确)
- [ ] .ai 在 Illustrator 打开不报错（无未知阴影/图像结构提示）、图层仅「背景/内容」
- [ ] 文本以单个 Text 对象保存，可整句编辑，不逐字断裂、不强制转曲
- [ ] 双面输入导出为单个 `.ai`，页数/画板数为 2
- [ ] AI 栅格化回 PNG 与参考图相似度 ≥ 97（运行 `scripts/ai_fidelity.py`）
- [ ] 与 PNG 导出视觉一致(排版无漂移)

## 本册用到的脚本

| 脚本 | 何时用 | 一行示例 |
|---|---|---|
| `ai_export.py` | 矢量/工程文件导出 | `python scripts/ai_export.py <项目>/src --svg` |
| `to_vector.py` | 位图转矢量草稿 | `python scripts/to_vector.py --help` |
| `ai_fidelity.py` | 矢量保真对拍 | `python scripts/ai_fidelity.py --help` |

> 参数的权威说明在脚本自身 `--help`(不在此复制);全量索引见 `docs/scripts.md`。
