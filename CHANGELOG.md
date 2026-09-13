# Changelog

## v1.7.4 — 仓库自检 `selfcheck.py`(把审查发现变成可执行门禁)

### Added
- **`scripts/selfcheck.py`**:7 项只读检查,把 `docs/review/01` 附录里的规格落地为
  可执行门禁。每一项都对应一次**真实发生过的缺陷**:

  | 检查 | 对应缺陷 |
  |---|---|
  | `refs` 悬空引用 | `make_bats.py` 已删却 4 处仍引用 |
  | `nums` 数字一致性 | rollup 11811/11812、字体 21/28、特效 30/43、风格 145/123、矢量禁令三条/五条 |
  | `cfg` 配置契约 | `ocr_path` 死配置;`vqa_path`/`poppler_dir`/`gs_path` 未声明 |
  | `route` 路由完备性 | `print-cmyk.md` 孤儿分册 |
  | **`build` 构建产物同步** | **配置编辑器 exe 比源码旧 5 天,用户拿到的是坏版本** |
  | `smoke` 脚本冒烟 | 硬编码路径导致 import 期崩溃 |
  | `jsonfail` 失败路径 JSON | `vectoredit2webhtml.py` 异常分支缺 `import json` |

- 用法:`python scripts/selfcheck.py [--only build] [--json] [--list]`;退出码
  0=全过 / 1=有 FAIL,可直接作 CI 门禁;`--json` 输出单行 JSON
- `build` 项在报 FAIL 时**直接打印重新打包命令**,照抄即可

### 设计取舍
- **不接进 `preflight.py`**:preflight 面向"这台机器能不能出图",selfcheck 面向
  "仓库是否自洽"。塞进去会让每张图都多花时间,且两者受众不同(使用者 vs 维护者)。
  仅登记在 README「脚本一览 · 维护」分组
- **不接进 SKILL.md 路由表**:它是维护者工具,不进 Agent 的出图上下文(省 token)
- 过程性文档(`docs/adr` / `docs/review` / `docs/ITERATION.md`)纳入豁免:
  里面记的是提案与历史,不是现存引用,纳入核验只会产生假阳性

### Verified
- 当前仓库:`FAIL 0 · WARN 1 · PASS 7`(WARN = `huaban_cookie` / `ocr_path` 两个
  死配置,保留待决)
- `build` 项有效性实测:故意把 exe 时间戳改旧 5 天 → 报 FAIL 并给出打包命令、
  退出码 1;复原后恢复 PASS、退出码 0

## v1.7.3 — 图形配置编辑器随配置契约同步重制

### Fixed
- **`tools/config-editor/artboard-config-editor.exe` 严重过期**:上次打包于 2026-09-09,
  而 `config_gui.py` 与 `config.example.json` 之后已多次变更,exe 里仍是旧逻辑。
  更关键的是:**PyInstaller onefile 下 `__file__` 指向解包临时目录(`_MEIPASS`)**,
  旧代码用 `dirname(dirname(abspath(__file__)))` 定位技能根 →
  实际会写到 `%TEMP%\...\config.json`,**保存后配置完全不生效**。
  上一版按源码态修好的路径(两层 dirname)对 exe **同样不成立**——
  这是本轮才发现的底层问题。
- **`config_gui.py` 定位重写 `locate_skill_dir()`**:`sys.frozen` 判定分派
  (frozen 用 `sys.executable`,源码用 `__file__`),自起点**向上最多 6 级**
  搜索技能根标志文件(`config.example.json` / `config.json`)。
  实测三场景全对:源码态、exe 在 `tools/config-editor/`、exe 被拷到桌面
  (第三种回落并如实报告"未定位到技能根")。
- 界面顶部新增**实际写入路径**与定位说明(未定位到时红字告警);
  保存前若判定路径可疑,弹确认;保存改为**原子写**(`.tmp` + `os.replace`)
  并与 `config.json` 已有键合并;新增「打开所在目录」按钮
- **内容可滚动**:字段从 13 增到 15 后,窗口高度装不下(旧版末尾几项被裁掉看不见)

### Added
- `config_gui.py --locate`:打印 frozen 状态与定位结果后退出,便于排障;
  源码态与 exe 都可用
- `config_gui.py` 头部补充打包命令与 frozen 注意事项(防下次再踩)
- `.gitignore` 排除 PyInstaller 构建残留(`.build/` / `.pkgtest/` / `*.spec`)

### Changed
- `README`「第 3 步 · 填配置」与 `docs/setup.md` 第 4 步:补充写入路径核对方法、
  `--locate` 排障、可滚动提示;配置项表补 Poppler / Ghostscript 两行
- exe 重新打包(11.99MB,`--onefile --windowed`,pyinstaller 6.22.2)

## v1.7.2 — 恢复 make_bats · 仓库只收实用文档 · 提示词瘦身

### Fixed · v1.7.1 复核补漏(逐项 72 项断言核对 + 25 项端到端测试发现)
- **`vectoredit2webhtml.py` 缺 `import json`**(v1.7.1 引入的回归):把失败分支的
  `%r` 换成 `json.dumps` 时,连同原来那句 `import json` 一起删掉了,
  导致**失败路径抛 `NameError`,连错误信息都吐不出来**(正好是最需要它的时刻)。
  改为文件顶部统一 import,失败路径实测输出合法 JSON
- `docs/glossary.md` 的「矢量安全清单」词条仍是「三条禁令」(v1.7.0 只在下方
  「已作废表述」表里记了,主词条漏改)→ 改为五条并补全五条内容

### Added
- **`scripts/make_bats.py`**(新写):给 `src/` 下每个 HTML 生成 `导出-<名字>.bat`,
  双击即出图。画布参数从 `project.json` 读(不写死);默认 PNG + PDF 到 `../export/`;
  HTML 含 `@keyframes` 且 ffmpeg 在 → 自动追加 GIF/MP4;`"print": true` → 追加 `--cmyk`;
  `--embed` 让 bat 自带兜底(主引擎失败自动改调 `export_fallback.py`,仅 PNG);
  bat 内写死当前 Python 与 export.py 的绝对路径(双击时 PATH 里通常没有 python)。
  与 `scaffold.py` 投放的 `导出.py`(批量导全部)互补。端到端实测通过(rc=0,PNG+PDF 产出)
- `scripts/_paths.py`(浏览器/7-Zip 探测单点)、`scripts/_download.py`(下载统一实现)
  已在 v1.7.1 落地,本版补登记

### Changed · 仓库只收"实际性工作内容 + 必备指导文档"
- `.gitignore` 排除过程性文档:`docs/adr/`、`docs/ITERATION.md`、`docs/review/`
  (本地保留,不进仓库);已跟踪的 `docs/ITERATION.md` 从索引移除
- 相应清理:`SKILL.md` 路由表删「技能审查报告」行;README 目录树标注上述目录为本地留档;
  CHANGELOG 中 ADR 引用改为编号(ADR-0013 / ADR-0014)

### Changed · 提示词瘦身(省 token)
- `SKILL.md`(每次都读,成本最高)精简 ~30 行:
  脚本清单由 30 行压到主线 6 条 + 一句「其余查 README/分册」;
  删「尺寸预设」整表(已在路由表指向 `sizes-common.md`);
  定位段、Step 1.5、铁律 6(动效数值留给 animation.md)、项目落盘段、环境配置段各压 30–50%
- 9 份新分册的头部元信息(「它补什么」这类迭代说明)全部删掉,
  只留「何时读」+ 必要的优先级/来源声明
- 完整脚本清单迁到 **README「脚本一览」**(按主线/双击导出/矢量/素材/复刻/字体·二维码·打包·换算·环境分组)

## v1.7.1 — 脚本缺陷修复(审查报告 02 的落地)

> 对应 `docs/review/02-脚本缺陷审查.md`。已用 `py_compile` + `--help` 冒烟 +
> scaffold→导出→一键导出端到端实测验证。

### Fixed · 严重(静默失败 / 能力全废)
- **P0-3** `ai_export.py:100` 调用不存在的 `core.ai_save()` → 改调
  `core.ai_build_native(source, …)`。`--ai` 此前 100% 抛 `AttributeError` 并被吞进
  warnings、退出码仍 0;现已能产出真 .ai。同步清理注释里的悬空符号
- **P0-4** `config_gui.py:16` 少一层 `dirname`(算成 `scripts/`)→ 改为技能根,
  与 `_config.py` / `export.py` / `preflight.py` 一致。图形配置编辑器此前**写入无效**;
  保存后现在会打印实际写入路径便于核对
- **P0-5** `setup_wpi.py` 部署的 63MB CLI 零消费者 → `export.py` 新增 CLI 分支:
  引擎按 **wpi_path(源码)→ wpi_cli_exe(CLI)** 选用,CLI 走同参数子进程
  (`--export --source --output --format --width --scale --height --fps --max-wait --transparent`),
  退出码 0 且产出文件才算成功。三级引擎至此真正闭环
- **P0-6** `export_fallback.py` 无 HTML 时截图 404 却报 `ok:true` → 提前返回
  `NO_INDEX_HTML`(带 hint);再补 `EMPTY_SCREENSHOT`(<1KB)与输出目录 `makedirs`
- ~~**P0-7** `.gitignore` 删除 `docs/adr/` 排除行~~ —— **该判定为误判**:作者既已确立
  「`docs/adr` 仅本地」的约定(提交 `5d24e59`),此处不是缺陷。v1.7.2 已恢复排除

### Fixed · 能力断链
- **P0-1/P0-2** `scaffold.py` 建项目时**自动投放** `scripts/export_local.py` 为
  `<项目>/src/导出.py`,并在 `project.json` 写入 `skill_dir`(导出器靠它 import `_config`)。
  "双击即导出"从文档承诺变为可用能力(端到端实测:1 张 PNG + PDF 成功)
- `export_local.py`:**倍率 `--scale` 不再写死 2**(改从 project.json 读,印刷 DPI 才对);
  `find_wpi(start)` 真正使用入参;全部 `json.load(open())` 改 `with open`;
  新增「禁止在 scripts/ 下直接运行」的防护与提示;CMYK 分支缺 Pillow 时明确告知

### Fixed · 配置契约与依赖
- `_config.py`:区分 `FileNotFoundError` 与 `JSONDecodeError`(后者打印到 stderr 并由
  `preflight` 报 FATAL,不再静默回落默认值);新增 `config_error()` / `cfg_raw()` /
  **原子写** `write_config()`(.tmp + os.replace,与已有键合并);ENV_MAP 补
  `wpi_cli_exe` / `vision_mode` / `ocr_path`;`preflight.py` 的 `WPI_FFMPEG` 加注释说明
- `config.example.json`:补 `vqa_path` / `poppler_dir` / `gs_path`;占位值清空
- `config_gui.py`:补 `poppler_dir` / `gs_path` 两个输入框
- **新增 `requirements.txt`**(Pillow + playwright)与 **`requirements-vector.txt`**
  (pikepdf / scikit-image / numpy / qrcode / zxing-cpp / rembg)

### Fixed · 可移植性
- 7 处硬编码 `E:\平日资料\GitHub\…` 全部改为 `_config.near_workspace()`(工作区同级目录
  回落):`export.py` / `export_local.py` / `preflight.py` ×2 / `vqa.py` / `scaffold.py` /
  `fetch_asset.py`。他人 clone 后不再指向作者机器
- 浏览器探测三份合一 → 新建 **`scripts/_paths.py`**(含用户级安装的 Chrome,
  修掉 `webhtml2vectoredit.py` 漏探测 Chrome 的问题);7-Zip 探测并入

### Fixed · 中/轻
- **下载**:新建 **`scripts/_download.py`**(urlopen + 分块写盘,`timeout=300`、
  重试 2 次退避、进度显示、`.part` 临时文件必清理、尊重 proxy),
  `setup_wpi.py` / `setup_ffmpeg.py` / `setup_vector.py` / `fetch_model.py` 全部改用
  (此前 4 份 `urlretrieve` 无超时,跨境网络可无限期挂起)
- 四处 `write_config` 重复实现 → 统一用 `_config.write_config()`
- `webhtml2vectoredit.py`:`run()` 对 None 参数提前报「跑 setup_vector.py」;
  `run_gs()` 缺 gs 时明确报错;`work_dir()` 非 ASCII 时改落 `C:\Windows\Temp`
  (中文用户名下 %TEMP% 不成立);`run()` 与 `ai_build_native` 异常路径也清临时目录
- `to_vector.py` / `ai_export.py`:自检需要 `pdftocairo` 时提前校验并给
  「setup_vector.py / --no-check」提示(此前抛 TypeError 被吞)
- `slim_project.py`:先重命名为 `.bak` → 建联接 → 失败**回滚**(此前无条件 rmtree,
  联接失败即丢字体);失败项不再计入 saved_mb;删重复 import
- `vectoredit2webhtml.py:289` `%r` 拼 JSON(输出单引号非法 JSON)→ `json.dumps`
- `pack.py`:`--out` 只给文件名时 `dirname` 为空崩溃 → `os.path.abspath` 兜底
- `setup_vector.py`:`inner[0]` 未判空 → 明确报错;poppler 部署失败不再崩整个脚本
- `cutout.py`:rembg/Pillow 缺失时 emit `NO_REMBG`/`NO_PILLOW` + 安装指引(此前裸 traceback)
- `compare.py` / `inspect_ref.py`:`--region` / `--box` 参数个数校验;Pillow 缺失优雅退出;
  图片尺寸为 0 保护;删死代码
- `export.py`:`--cmyk` 遇 Pillow 缺失改为 warnings 明示(此前静默 pass);
  `run_export_sync` 返回非 dict 时报错而非 `AttributeError`
- `preflight.py`:删除 `or True` 死逻辑(GIF 能力真实反映 ffmpeg/Pillow);
  新增 `wpi_cli_exe` 检查与 config.json 解析错误检查;删重复 import
- `vqa.py`:`DEFAULT_VQA_PATH` 死代码激活(此前仅 `vqa_path` 已配置时才可能用到)
- `calc_size.py`:mm 模式口径与 `scaffold.py`/`export.md` 统一为
  `CSS 画布 = 成品 px ÷ scale`(A4 300dpi scale2 → 1240×1754,导出 2480×3508)
- `fetch_asset.py`:`studio_dir` 改为每次读取(此前模块导入时求值);
  下载下限 3000B→512B(合法小图标不再被误判);curl 兜底失败原因不再被吞;
  花瓣 `search_huaban` 返回空列表而非"空 url 伪候选"(此前显示"搜到 1 条"却零下载)
- `fetch_font.py`:proxy 改走 `_config.cfg("proxy")`(config.json 的代理此前对它无效)
- 删除 `scripts/导出/` 空目录(`export_local.py` 被误执行的历史残留)

## v1.7.0 — 设计知识补强(9 分册)+ 文档口径收口

### Added · 设计知识补强(填补此前完全空白的设计维度)
- **构图与版式骨架** `references/composition.md`:三次决策顺序(动线→骨架→网格);
  S/中轴·Z·F·放射·环 五动线;视觉重量六项加权(面积40/对比25/位置15/孤立10/方向5/纹理5);
  六种骨架的 CSS(三分 / 黄金 1:1.618 / 中轴 / 对角 15–30° / 框中框 / 满版出血);
  栏数-栏沟表与基线单位公式;`styles-catalog.md` 那 17 个只有名字的布局模式**逐个落到骨架**
- **设计评审打分表** `references/design-review-rubric.md`(ADR-0013):五维度 × 0–5 分 + 权重
  (A 层级焦点 30 / B 排版 25 / C 色彩对比 20 / D 构图留白 15 / E 去 AI 味 10);
  及格线 ≥3.5 且无单项 ≤1;硬伤直接计 0;**不新增自检时机**(挂铁律 5 的两个时机)
- **对比度与色彩工程** `references/color-contrast.md`:补上全库缺失的 **WCAG 2.2「大字」定义**
  (≥18pt/24px 常规 或 ≥14pt/18.66px 粗体 → 3:1);相对亮度与对比比公式;OKLCH ΔL 速判表
  (0.33/0.45/0.54);**压图遮罩数值**(渐变 α ≤.75、局部块 α .55–.70、收边投影 α ≤.50);
  色盲友好(全库此前 0 命中)+ Okabe-Ito 改良四色系列
- **数字·单位·日期排版** `references/numeric-typography.md`:千分位/万·亿 vs K·M/货币符号
  40–45%/百分比/小数位/负号 U+2212/范围 en dash/日期 24h/序号体系
- **数据可视化规范** `references/dataviz.md`:论点形态→图表选型矩阵;坐标轴(刻度 4–6 条、
  柱图零基线、可见断点);图例取舍;系列色 ≤4 且 OKLCH L 差 ≥0.12;大数字卡参数
- **一稿多尺寸重排** `references/responsive-reflow.md`(ADR-0014):四类元素(可等比缩放/
  需重新定位/需重新排布/需重新裁切);字号换算改为**按栏宽开方**;母版+变体工作流
- **中文排版 CSS 落地** `references/cjk-typography-css.md`:`text-spacing-trim` /
  `text-autospace` / `word-break:keep-all` + `line-break:strict` + `text-wrap:pretty`
  的完整配方 + 降级方案 + Unicode 符号规范(此前只有规则、零实现)
- **印前与后工艺** `references/print-production.md`:陷印 0.25–0.5pt、专色标注法、五种印前标记、
  出血换算(300dpi 下 1mm=11.811px)、LPI 与所需 DPI 对照、网点扩大与纸张补偿、UV/烫金/模切版要求
- **品牌一致性** `references/brand-system.md`:logo 净空 = 高/宽 25%(屏幕 ≥12px / 印刷 ≥1.5mm)、
  最小尺寸、五条禁则;**品牌色阶生成法**(固定 H/C、OKLCH L 从 97%→21% 十阶);跨物料 7 项一致项

### Added · 治理
- ADR-0013(加权设计评审 rubric)、ADR-0014(字号阶单一母阶 + 栏宽换算)
  —— ADR 为本地留档,不进仓库,见 `.gitignore`
- `docs/glossary.md`:+23 词条;新增**术语消歧**节(预设/物料/品类、风格/风格方向、
  大字/主标、等比换算/栏宽换算)与「已作废表述」表
- `docs/review/`:技能审查报告 3 份(总览与修复优先级 / 一致性与文档 / 脚本缺陷)

### Fixed · 文档口径(此前互相打架的数值)
- **P0** `make_bats.py` 已删但 4 处仍引用(SKILL.md / README ×2 / pipeline.md Step 6.5)→
  全部改为 `export_local.py`,Step 6.5 整节改写为「投放一键导出脚本」并注明必须在 src/ 下运行
- `SKILL.md` 资源索引表补 12 行:9 份新分册 + **孤儿 `print-cmyk.md`** + glossary + review 目录
- `formats/rollup.md:6` 导出高 11811 → **11812**(v1.1.0 漏改的一处)
- 三折页成品尺寸统一为 **A4 横 297×210**(sizes-common / material-catalog 原写 210×285,
  与 trifold.md / scaffold.py / export.md 的 3508×2480 矛盾)
- 名片最小字 6pt → **7pt**(sizes-common / material-catalog 对齐 card.md)
- 特效数 30 → **43**(effects.md / SKILL.md / README)
- 风格总表 145 → **123**,5 个节标题逐一改正(modern 29→20 / retro 25→20 / minimal 21→20 /
  expressive 52→46 / 布局 18→17)
- 字体数 21 → **28**(README;fonts/README 28 行 = download.json 28 条目 = 磁盘 28 目录)
- 矢量安全清单禁令 三条 → **五条**(glossary)
- OCR 能力从文档下线:SKILL.md description / README 配置表(与 pipeline.md「不调外部 OCR 工具」
  及 ADR-0003 Agent 视觉优先一致;`ocr_path` 零消费者)
- 自检步骤号 Step 5 → **Step 6**(guardrails.md);流水线「7 步」→「Step 0–7,含 1.5/4.5 子步」
- 「18 预设」改指真实出处 `scripts/scaffold.py` SIZES(原错挂给 sizes-common.md)
- 品类路由 slug `slide` ↔ 文件 `ppt.md` 不匹配 → 路由表显式标注
- `styles-catalog.md` 的断链引用 `其他开源项目参考/` → 改为可降级表述 + composition.md 指向
- SKILL.md frontmatter 补 `version: 1.7.0`
- CHANGELOG 补 **v1.0.0** 段挂载孤儿 ADR 0001–0005
- README 目录树补 9 份新分册 + `docs/glossary.md` + `docs/adr/` + `docs/review/`

### Known issues(不属 Markdown 范畴,需代码层修复,详见 docs/review/02)
- `ai_export.py:100` 调用不存在的 `core.ai_save()` → `--ai` 静默失败(应改 `ai_build_native`)
- `config_gui.py:16` 少一层 `dirname` → 图形配置编辑器写错目录
- `setup_wpi.py` 部署的 `wpi_cli_exe` 零消费者
- `export_fallback.py` 无 HTML 时输出 404 废图却报 `ok:true`
- `export_local.py` 从未被 `scaffold.py` 投放;`--scale` 写死 2
- `.gitignore:9` 排除 `docs/adr/`(与 ACL-1.0 开源承诺冲突)
- 7 处硬编码 `E:\平日资料\GitHub\`;无 `requirements.txt`

## v1.6.0 — 视频场景卡模式(口播桥适配)+ 中文标题语义断行

### Added
- **动效分册分双模式**(animation.md §〇 路由):模式 P 海报循环(原规范不变)
  / **模式 S 视频场景卡**——插进口播之间的信息卡/图解卡(ADR-0012):
  - 五段式时间轴契约:前置静置 ≥2.0s(实测录制起点 1.7–1.9s)→ 入场
    0.5–0.8s(decelerate)→ 持住(与口播句对齐)→ **出场 0.4–0.6s**
    (accelerate,三原则:比入场短/方向延续/stagger 反序)→ 收尾静置 ≥0.3s
  - 入场/持住/出场模式库:骨架先行、标题逐行、图元 stagger、焦点收缩、
    擦除收回等;全 finite 禁 `infinite`(否则录制无法提前停)
  - **生动性词汇表**(科普/教程):图解渐进构建(stroke-dashoffset 画出)、
    逐词强调、@property 数字计数、卡内前后对比、聚光灯、Ken Burns、
    次要动作与夸张有度(迪士尼第 8/10 法则落地)
  - 可动属性白名单分级:L1 transform/opacity → L2 clip-path、stroke-dashoffset、
    @property → L3 filter(数量/尺寸护栏);重排属性依旧全禁
  - 前置静置 ≥2.0s 吸收录制起点偏移(实测 1.7–1.9s,ffprobe 时长反推+
    时钟探针首帧读数互证);"resize 重对表"方案实测否决(录制期主线程
    提交被采样饿死,ADR-0012 留档防重试)
  - 【硬】入场+出场分属两层嵌套元素(外入内出)——同元素双动画(简写相叠
    或逗号列表)都会被后一场的 backwards fill 压成"从 0s 起常驻"
    (实测踩坑,"帧 0 满构图、没有入场"的元凶)
  - 模式 S CSS 骨架(整段可抄)+ 场景卡自检清单(抽帧验证出入场在片)
- **中文标题语义断行规程**(typography-rules.md §一;修复"店群运营被认/定为
  拆分收入"式词中劈开):展示文字手动断行制——两行=两个 `.tl` span,
  断点选语法边界;`word-break: keep-all` + `<wbr>` + `text-wrap: balance`
  配方(CSS Text 3 官方用法;balance 只匀称不认语义,不得单用);
  正反例句库 + "每行独立成意"验收标准;正文段落维持 clreq 默认
- scaffold.py 模板内置 `.tl` / `.t-keep` 断行工具类(带规程注释)
- SKILL.md:铁律 6 分模式表述;路由表 animation.md 行补"视频桥场景卡"触发;
  description 补"视频信息卡/科普动画卡"触发词
- docs/adr/0012(场景卡模式与录制偏移对策);glossary 补 9 个新词条

### Fixed
- 视频桥场景卡切换僵硬:根因是"只有循环概念、没有出场"+入场被录制偏移吃掉,
  由模式 S 五段式整体修复(见 ADR-0012)

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

## v1.0.0 — 首个可用版本

> 补记:本段为挂载 ADR 0001–0005 而补(此前 CHANGELOG 从 v1.1.0 起记,导致这 5 份
> 2026-09-06 的 ADR 在 CHANGELOG 中零提及,成为孤儿)。

### Added
- HTML/CSS 固定画布海报管线:scaffold 建项目 → 写 HTML → WPI(Playwright 驱动系统
  Edge/Chrome)渲染导出 PNG,失败走独立 Playwright 兜底
- 开工五问协议(intake.md)与设计护栏(guardrails.md)
- 字体库按需下载与瘦身影子(NTFS 目录联接)

### ADR(0001–0005)
- **0001** 项目资产引用用 NTFS 目录联接(junction),而非绝对路径或拷贝
- **0002** 参考资料按需读取(渐进披露),SKILL.md 资源索引表是唯一路由表
- **0003** Agent 视觉优先(复刻/看图用 Agent 自身视觉,不依赖外部 OCR)
- **0004** 字体库按需下载(不随仓库全量携带)
- **0005** 文字特效必须通过导出安全审查(防渲染/打印丢效果)
