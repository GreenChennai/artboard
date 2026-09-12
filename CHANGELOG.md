# Changelog

## v1.5.0 — 复刻证据链重写 + ACL-1.0 开源协议

### Added
- **复刻证据链协议**(replicate.md 重写,方法论致谢 super-prototyping):
  网格先行(先命名分区再测量)→ 分区普查取色(tokens 必须带采样证据,
  裸眼估 hex 禁入 CSS)→ 字体无把握不点名 → **照片直接从参考图按测得 bbox 裁切**
  (img/crops.json 登记,真 1:1,替代"素材库找同主题"的默认路径)→
  tokens 契约先行 → 分区数字比对(差异争议回测量,不对 CSS 瞎补)
- `scripts/inspect_ref.py`:参考图像素普查工具四命令——
  `grid`(带标注网格)/ `census`(flat fills=真填充 / all pixels=小块 / ink core=文字墨色)/
  `bbox`(内容外接框,测边距与发丝线)/ `crop`(按测得框裁素材)
- compare.py `--region x0,y0,x1,y1`(比例坐标):局部放大比对 + ΔRGB 均值数字,
  两轮比对的数字变化即修复进度证据
- SKILL.md 路由表补 replicate.md 一行(此前 B/C 模式无路由入口)

### Fixed
- inspect_ref.py grid/crop 落盘前自动创建父目录(协议默认往 img/ 裁图,新项目无该目录会崩)

### Changed
- **LICENSE:MIT → ACL-1.0(Artboard 社区开源协议)**:强传染(复制/衍生/网络服务
  须同协议开源)、禁止转售软件本体、**产出物归使用者可自由商用**、第三方素材各随其授权
- pipeline.md 模式 B 改为指向 replicate.md 的速记版(去重复维护)

## v1.4.0 — 文字整句化 + 按组件嵌套的原生 .ai + 双层制

### Fixed
- **文字断层**(用户实测头号痛点):text_run_merger.py 把 Chromium 逐字 Td/Tj
  合并为单条 TJ 数组(字距差值用内嵌字体 /W 度量表逐字保真),AI 中
  "滚滚长江东逝水"式整句恢复为单个可编辑文字对象。实测 27/27 块合并、
  渲染像素零差异、AI 27 个整句文字对象
- ai.pdf/.ai 图层简化为 背景层+内容层 双层(原五层语义桶过细,用户反馈)

### Added
- **原生 AI 构建**(ai_build_native,.ai 的新实现):DOM 组件树 → ExtendScript
  在 Illustrator 内递归构建——元素=真编组(Ctrl+G,非剪切蒙版),子元素嵌套
  子组(组件层级即 DOM 层级),文字=TextFrame 整句,图片=内嵌。
  实测 layers=2、嵌套 7 层真组、0 剪切蒙版、25 整句文字、照片内嵌(ADR 0011)
- vectoredit2webhtml.py **多页 PDF 支持**(--pages 选页,逐页自包含 HTML);
  作品集 73 页/806MB 实测 pdf→html→pdf→html 往返:渲染 SSIM 0.936–0.945 收敛、
  最长文字串 100% 保留
- 坐标标定:ExtendScript 纵轴为底部原点向上,topY=(H−y)×0.75(标定页实验确定);
  修正背景矩形画到画布外、整版上下镜像两处错位

### Changed
- to_vector --ai 从"PDF 对象三桶分发"切换为"原生 DOM 组件树构建"(ADR 0011)

## v1.3.0 — 自写转换核心:WebHtml2VectorEdit / VectorEdit2WebHtml — 自写转换核心:WebHtml2VectorEdit / VectorEdit2WebHtml

### Added
- `scripts/webhtml2vectoredit.py`:自写正向转换核心(不再依赖 WPI)——
  Playwright settle + 单页精确尺寸 PDF 枢纽 + **DOM 分层多遍打印**
  (背景/图形/图片/蒙层/文字,面板底色克隆剥离,data-ai-layer 可手动归层)
  + pikepdf OCG 合成分层 PDF + SVG/EPS 衍生 + SSIM 相似度自检(ADR 0009/0010)
- **分层增强可编辑性**:ai.pdf 在 PDF 阅读器中图层可开关;`--ai` 经
  Illustrator COM 建 图形/图片/文字 三层并按对象类型分发,产出含 PGF 的真 .ai
- `scripts/ai_export.py`:一键矢量/工程文件导出(画布自探测,缺 project.json 也能跑)
- `scripts/vectoredit2webhtml.py`:逆向核心 PDF/EPS/SVG/.ai → 可维护 HTML
  (visual=矢量底景+透明可选文字;editable=真实文字+照片,改稿后可重导出)
- 语言选型:Python(瓶颈在子进程渲染器,ADR 0010)

### Changed
- to_vector.py 重构为薄壳 CLI,默认格式改为 ai-pdf(分层 AI 可编辑 PDF);
  SVG/EPS/outline 按需加;新增 --no-layers
- SKILL.md 铁律第 10 条:矢量/工程文件导出不在默认流水线,仅用户明确要求时运行

### Fixed
- 面板底色克隆用 div(避免被海报的 i/b 元素选择器误中,如 .rays i)
- 蒙层识别:图片后方兄弟渐变遮罩独立成层,修正 a4p 照片盖住遮罩的合成错序
- subprocess 中文控制台输出 UnicodeDecodeError(统一 errors=replace)

## v1.2.0 — 矢量交付(SVG / EPS / AI 可编辑 PDF) — 矢量交付(SVG / EPS / AI 可编辑 PDF)

### Added
- `scripts/to_vector.py`:HTML → 单页矢量 PDF 枢纽 → SVG / EPS / AI 可编辑 PDF /
  免字体依赖 PDF,输出单行 JSON + 逐格式 SSIM 相似度报告 + 差异热区图
  (ADR 0006/0007/0008;手册 references/vector-export.md)
- `scripts/setup_vector.py`:一键部署 poppler + Ghostscript 便携版
  (7-Zip 解包官方安装器,免管理员;二进制不进 git)
- `_config.py` 新增 `poppler_dir`(ARTBOARD_POPPLER)/`gs_path`(ARTBOARD_GS)
- 矢量安全清单:16 原语实测 + 五条禁令(conic-gradient 打印即丢、渐变字丢字、
  mix-blend-mode 色偏、硬切透明渐变脏色、alpha 渐变蒙版边界线)
- 词汇表 +7 词条;三样张(s2-xhs/kv/a4p)judge 三轮裁决全过,SSIM 0.958–0.989

### Fixed
- s2-xhs 引句高亮:硬切透明渐变 → 单色不透明渐变垫底 + box-decoration-break:clone
  (折行场景伪元素方案宽度归 0,一并避坑)
- s2-a4p 徽章放射线:repeating-conic-gradient 打印即丢 → 24 根 clip-path 楔形细条;
  光晕 alpha 渐变 → 不透明等价色(消除转 SVG 的软蒙版边界细线)

## v1.1.0 — 一致性收口

### Fixed
- export_local.py 补 import shutil(修复双击导出 NameError)
- make_bats 引用清理(已被 export_local.py 替代)
- 动效口径统一(guardrails/pipeline/SKILL 三处改"已启用")
- harmonyos-sans download.json 文件名修正(单文件可变字体)
- rollup 导出尺寸 11811→11812(同文件内部不一致)
- preflight WPI 缺失 FATAL→WARN(有 export_fallback 兜底)
- export.py from PIL 加 try/except(缺 Pillow 时 --cmyk 不裸 traceback)

### Changed
- guardrails.md 动画条目改为"已启用"
- pipeline.md 动效节标题去掉"禁用动画"
- scaffold --embed-fonts help 描述修正(联接非绝对路径)
- config.example.json 补 ocr_path(空串)

### Security
- preflight WPI 缺失不再 FATAL(可降级 export_fallback)
