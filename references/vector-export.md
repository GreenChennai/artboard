# artboard 矢量交付手册(v1.9:Kiln 原生直出 SVG / PDF(CID 中文真文本)/ EPS / AI / PPTX)

> 把 HTML 海报直出为设计软件可编辑的矢量产物。九格式同源:一次渲染,
> SVG/PPTX 真文本、PDF CID 中文真文本(可选中复制)、EPS/AI(PDF 兼容流)。
> 引擎:**Kiln**(VellumBench 原生,零浏览器/poppler 依赖)。
> **触发规则:正常 artboard 流水线没有这一步——仅当用户明确要"工程文件/
> 矢量文件/SVG/EPS/AI 可编辑"时才运行**(一键入口 scripts/ai_export.py)。

## 0. 快速上手

```bash
# 一键:项目目录 → SVG + PDF(默认产物)
python scripts/ai_export.py <项目目录>

# 追加其他格式
python scripts/ai_export.py <项目目录> --eps --ai --pptx

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
| Ai | 同 PDF(PDF 兼容流,ADR-0008) | 同 PDF | ✅ | Illustrator 打开 |
| EPS | Latin 真文本;中文轮廓 | 无 | 轮廓化 | 老印厂 |
| PPTX | 真文本 shape | shape 树 | ✅ | 汇报/二次编辑 |

已知边界:中文在 EPS 中轮廓化(不可改字);渐变高亮等填充装饰在 PDF/EPS
按中值色降级;`@property` 数字滚动为静态终值。

## 2. 与 v1.8 的差异

- poppler + Ghostscript + pikepdf + scikit-image 全链退役(setup_vector.py 删除)
- WebHtml2VectorEdit / VectorEdit2WebHtml / text_run_merger 退役(Kiln 原生直出)
- 中文 PDF 从"整句轮廓"升级为"CID 真文本可选中"
- 相似度自检(SSIM)随浏览器基线退役;保真度走上游 bench/fidelity.py

## 3. 逆向重维护(kiln-cli import)

外部矢量稿(设计师交付的 PDF/AI)→ 规范化 HTML:

```bash
Kiln-noGUI-CLI.exe import --source poster.pdf --output <项目目录>
```

- 产出 index.html + styles/main.css(绝对定位规范化形态)+ assets/
- 文本可编辑;路径/图像分别映射;依赖 pdfium.dll(PDFIUM_DLL 指定)
- v1 边界:对象取色未暴露(统一近似色);路径以盒近似;SVG 源后续版

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
- [ ] .ai 在 Illustrator 打开不报错、图层可辨
- [ ] 与 PNG 导出视觉一致(排版无漂移)
