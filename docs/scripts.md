# artboard 脚本总表(生成物)

> 由 `scripts/gen_script_index.py` 生成 @ 2026-09-27;**不要手改**。
> 权威参数 = 各脚本 `--help`;分册末尾「本册用到的脚本」是就近索引。

## 脚本(39个)

| 脚本 | 用途(=docstring 首行) | 被哪些文档提到 |
|---|---|---|
| add_font.py | artboard 字体登记:把 fonts/<目录> 注册进字体总目录 fonts/README.md。 | docs/scripts.md、fonts/README.md、references/brand-system.md |
| ai_export.py | 一键矢量导出(v1.9:Kiln 原生九格式薄壳)。 | README.md、SKILL.md、docs/scripts.md、references/depth-3d.md、references/formats/ppt.md、references/print-production.md… |
| ai_fidelity.py | PNG ↔ 可编辑 AI/PDF 相似度门禁。 | docs/scripts.md、docs/setup.md、references/vector-export.md |
| asset_hunt.py | artboard 全自动素材搜索(asset_hunt):一条命令 = 开页→搜词→筛→下→去重→关页→JSON 报告。 | SKILL.md、docs/glossary.md、docs/scripts.md、references/materials.md、references/mcp-assets.md |
| beat_sheet.py | artboard 卡点表:BPM → 帧网格(模式 V · 视频动效件;细则见 references/video-motion.md §五)。 | docs/glossary.md、docs/scripts.md、references/video-motion.md |
| calc_size.py | artboard 尺寸计算器:px / mm / inch / DPI 互转,印刷导出一把算清。 | docs/scripts.md、references/export.md、references/material-catalog.md、references/print-cmyk.md、references/print-production.md、references/sizes-common.md |
| check_brief.py | artboard 开工前检查单(Brief Gate)机检。 | docs/glossary.md、docs/scripts.md、references/intake.md |
| check_credits.py | artboard 素材版权复核:img 目录 ↔ CREDITS.md 逐条对账。 | SKILL.md、docs/scripts.md、references/materials.md、references/mcp-assets.md、references/pipeline.md |
| check_h5.py | artboard H5 交互页机检(模式 H;规范见 references/h5-interactive.md)。 | SKILL.md、docs/scripts.md、references/h5-interactive.md |
| check_mobile_width.py | import argparse | README.md、SKILL.md、docs/scripts.md、references/wechat-article.md |
| check_overflow.py | artboard 溢出与安全区机检。 | README.md、SKILL.md、docs/glossary.md、docs/gzh-guide.md、docs/scripts.md、references/animation.md… |
| check_svg.py | artboard SVG 质量门(9 项结构机检;细则见 references/vector-drawing.md §4.7)。 | docs/glossary.md、docs/scripts.md、references/materials.md、references/vector-drawing.md |
| check_wechat_svg.py | 从整页文档里切出「会被粘贴进公众号」的那一段。 | README.md、SKILL.md、docs/scripts.md、references/wechat-article.md |
| compare.py | artboard 复刻比对:参考图 vs 复刻导出图并排拼接,供视觉逐项核对。 | docs/ITERATION.md、docs/glossary.md、docs/scripts.md、references/pipeline.md、references/replicate.md |
| cutout.py | artboard 抠图:本地 rembg + 四件套后处理(去残边/羽化/贴纸白边/软投影)。 | SKILL.md、docs/scripts.md、references/image-language.md、references/imaging.md、references/materials.md、references/pipeline.md… |
| doctor.py | artboard 项目体检:扫 studio 目录,核对 project.json 与 HTML 真值。 | docs/scripts.md、references/export.md |
| export.py | artboard 导出薄壳(主路径):Kiln 原生引擎(v1.9.0 起)→ 失败给 hint。 | README.md、SKILL.md、docs/ITERATION.md、docs/scripts.md、references/animation.md、references/dataviz.md… |
| export_fallback.py | artboard 兜底导出:独立 Playwright → 静态 PNG。 | README.md、SKILL.md、docs/ITERATION.md、docs/scripts.md、references/export.md、references/pipeline.md |
| export_local.py | artboard 项目一键导出:双击或 ` 导出.py` 即可导出本目录全部 HTML。 | docs/ITERATION.md、docs/scripts.md、references/export.md |
| fetch_asset.py | artboard 素材获取:图库 API(授权干净)+ 爬虫兜底 + 剪贴板入库 + CREDITS 登记。 | SKILL.md、docs/scripts.md、references/materials.md、references/mcp-assets.md、references/pipeline.md |
| fetch_font.py | artboard 字体按需下载:读 fonts/download.json,把本地缺失的字体取回。 | docs/ITERATION.md、docs/scripts.md、docs/setup.md、fonts/README.md、references/brand-system.md |
| fetch_model.py |  | README.md、SKILL.md、docs/ITERATION.md、docs/scripts.md、docs/setup.md、references/materials.md |
| fetch_svg.py | artboard 矢量素材获取:Iconify 图标(按需 + 离线缓存 + 逐集许可)。 | docs/scripts.md、docs/svg-licenses.md、references/materials.md、references/vector-drawing.md |
| gzh_article.py | 公众号文章排版器:Markdown → 微信公众号编辑器可直接粘贴的全内联样式 HTML。 | README.md、SKILL.md、docs/gzh-guide.md、docs/gzh-spec-summary.md、docs/scripts.md、references/gzh-typography.md |
| gzh_cover.py | 微信公众号双封面工作站:一次设计,三张产物(主封面/次条/合并预览图)。 | README.md、SKILL.md、docs/gzh-guide.md、docs/scripts.md、references/formats/gzh-cover.md、references/imaging.md… |
| imageops.py | 位图工序唯一入口(指导书 §1.3/附录 D.2):只做参数分发与结果汇总,不含算法。 | README.md、SKILL.md、docs/failures.md、docs/scripts.md、references/depth-3d.md、references/image-language.md… |
| inspect_ref.py | artboard 复刻测量:参考图像素普查工具(证据链协议,见 references/replicate.md)。 | docs/glossary.md、docs/scripts.md、references/imaging.md、references/pipeline.md、references/replicate.md |
| make_bats.py | artboard 一键导出批处理生成:给 src/ 下每个 HTML 生成一个双击即出图的 .bat。 | docs/ITERATION.md、docs/scripts.md、references/export.md、references/pipeline.md |
| pack.py | artboard 工程打包:把瘦身影子项目引用的所有外部文件收集进 zip,可迁移交付。 | SKILL.md、docs/glossary.md、docs/scripts.md、references/export.md、references/h5-interactive.md |
| pixel.py | artboard 位图配方引擎(pixel):声明式配方 + PS 对照的调整/滤镜/图层能力。 | docs/glossary.md、docs/scripts.md、references/image-language.md、references/imaging.md、references/materials.md、references/pixel-pipeline.md |
| preflight.py | artboard 任务预检:渲染环境一次查清,输出人类可读清单 + 单行 JSON。 | README.md、SKILL.md、docs/ITERATION.md、docs/scripts.md、docs/setup.md、references/depth-3d.md… |
| qr.py | artboard 二维码工具:生成(品牌色/内嵌 logo)+ 解析(本地 zxing,URL 走草料 API)。 | SKILL.md、docs/scripts.md、references/formats/a4p.md、references/formats/card.md、references/formats/rollup.md、references/formats/trifold.md |
| scaffold.py | artboard 项目脚手架:在 artboard-studio/ 下生成海报项目(src/ + export/)。 | README.md、SKILL.md、docs/ITERATION.md、docs/glossary.md、docs/scripts.md、references/depth-3d.md… |
| setup_ffmpeg.py | artboard 环境部署:一键下载部署 FFmpeg(Windows)。 | README.md、SKILL.md、docs/scripts.md、docs/setup.md、references/export.md |
| setup_kiln.py | Kiln 引擎一键部署(v1.9.0 起,WPI 已退役)。 | README.md、SKILL.md、docs/gzh-guide.md、docs/scripts.md、docs/setup.md、references/export.md… |
| slim_project.py | artboard 项目瘦身:把项目里"实体拷贝"的 fonts/vendor 目录换成 Skill 资产库的目录联接。 | docs/scripts.md、references/export.md |
| to_vector.py | artboard 矢量交付 CLI(v1.9:Kiln 原生九格式薄壳)。 | docs/scripts.md、references/vector-export.md |
| upload_imgchr.py | last = "" | README.md、docs/scripts.md、references/wechat-article.md |
| vqa.py | artboard VQA:调用本地 VQA 项目解释图片内容(离线,CPU)。 | docs/scripts.md、references/materials.md |

## 内部 / 维护(白名单,不进 Agent 上下文)(18个)

| 脚本 | 用途(=docstring 首行) | 被哪些文档提到 |
|---|---|---|
| _config.py | artboard 共享配置读取与写入:环境变量 > config.json > 默认值。 | SKILL.md、docs/ITERATION.md、docs/scripts.md |
| _download.py | artboard 共享下载器:带超时、带重试、带进度、临时文件必清理。 | docs/scripts.md |
| _gzh_theme.py | 公众号统一主题真相源(图文 gzh_article + 双封面 gzh_cover 共用;11 迭代 D-11-2)。 | SKILL.md、docs/glossary.md、docs/gzh-guide.md、docs/scripts.md、references/formats/gzh-cover.md、references/gzh-typography.md… |
| _img_compose.py | C 组(合成层)实现(指导书 §5.4,批次二核心项提前落地): | docs/failures.md、docs/scripts.md |
| _img_core.py | imageops 公共契约(《artboard-位图脚本库扩充-迭代指导书》§4): | docs/failures.md、docs/scripts.md、references/imaging.md |
| _img_encode.py | E 组(编码与体积)实现(指导书 §5.2):convert / compress / optimize / strip-meta。 | docs/scripts.md |
| _img_geom.py | G 组(几何与尺寸)+ D 组(派生与切片)实现(指导书 §5.1/§5.3)。 | docs/failures.md、docs/scripts.md |
| _img_probe.py | P 组(检测与体检)实现(指导书 §5.5):零 token 机检,只出 JSON 不写图。 | docs/failures.md、docs/scripts.md |
| _paths.py | artboard 共享路径探测:浏览器内核 / 7-Zip 的候选路径单点定义。 | docs/scripts.md |
| _px_adjust.py | P0-A 调整类 18 项(对标 PS Adjustments;全 Pillow+numpy 自实现,无可选依赖)。 | docs/scripts.md |
| _px_core.py | pixel 引擎公共层:JSON 契约、图像 IO(float32 归一)、蒙版解析。 | docs/scripts.md |
| _px_filter.py | P0-B 滤镜类 12 项(对标 PS Filter;依赖分级:纯 Pillow 可跑,cv2 提速/增强)。 | docs/scripts.md |
| _px_layer.py | P0-C 图层与合成:混合模式 25 种 / 图层栈 / 填充 / 描边 / 投影。 | docs/scripts.md |
| _px_recipe.py | 配方引擎:recipe.json 解析 / 校验(未知 op·参数·乱序·缺依赖)/ 单图重放 / 目录批量。 | docs/scripts.md |
| config_gui.py |  | docs/ITERATION.md、docs/scripts.md |
| gen_script_index.py | artboard 脚本索引生成器(08 迭代 D-08-3):registry.json + docs/scripts.md。 | README.md、docs/ITERATION.md、docs/glossary.md、docs/scripts.md |
| junction.py | NTFS 目录联接(junction)创建/检测。 | docs/ITERATION.md、docs/scripts.md |
| selfcheck.py | artboard 仓库自检:拦住"文档说有、代码没有"与"同一事实多处不一致"这一类缺陷。 | docs/ITERATION.md、docs/scripts.md |
