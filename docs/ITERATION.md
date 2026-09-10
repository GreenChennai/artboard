# artboard 迭代与优化手册

> 本文档既是**一次评审的结论**,也是**后续每轮迭代的作业规程**。
> 评审日期:2026-09-10 · 评审基线:`main @ c586d1a`
> 评审方式:全量阅读 + 实跑验证(非纸面推断)。所有结论均标注 `文件:行号` 或实测输出,可复现。

---

## 0. TL;DR

| 项 | 结论 |
|---|---|
| 整体判定 | **REQUEST CHANGES** —— 架构与知识沉淀质量高于同类 skill,但存在 3 个 Critical 缺陷,其中 2 个是"文档承诺 = 代码不存在"的断链 |
| 最严重的一条 | `scripts/export_local.py:78` 未导入 `shutil`,而它是文档承诺的"双击即导出"唯一实现 → 该功能 100% 崩溃 |
| 系统性问题 | 不是能力不足,是**一致性债 + 零自动化验证**:2956 行脚本 0 测试 0 CI,缺陷只能靠人肉发现 |
| 迭代主线建议 | **先收口一致性债(v1.1 纯修复,不加功能)→ 再立基础设施(v1.2)→ 最后扩能力(v1.3)** |
| 明确反对 | 不要以"加更多风格/更多字体"作为下一轮迭代主线 —— 会成倍放大已有的多真相源问题 |

---

## 1. 评审结论(五轴)

按 Addy Osmani 的 Five-Axis 框架,把"技能"当作可交付物来审:正确性 / 可读性 / 架构 / 安全 / 性能。

### 1.1 Correctness(正确性)—— 不通过

**Critical**

- **C1 `scripts/export_local.py:78` 使用 `shutil.which` 但 `shutil` 未导入。**
  - 证据:AST 全量扫描 21 个脚本,仅此一处"未导入即使用"(`[export_local.py] 未导入即使用: ['shutil']`)。
  - 触发条件:脚本被放进项目 `src/` 且目录内有 `.html`(即它被设计出来的唯一用途)。直接跑 `--help` 不会崩,因为 `main()` 在 `scripts/` 目录下会先因"没有可导出的 .html"提前 return —— **缺陷只在真正使用时暴露,发布前的人肉测试抓不到**。
  - 影响:这一行之后的所有逻辑(逐张 PNG/PDF/GIF/MP4、CMYK、汇总报告)全部不可达。用户双击得到 `NameError`。
  - 修复:`import shutil`(1 行)。

- **C2 "双击即导出"能力整体断链:文档引用的 `make_bats.py` 不存在,且无脚本把 `export_local.py` 投放到项目里。**
  - 证据:
    - `SKILL.md:108` → `python $S/make_bats.py <项目>   # 给每个 HTML 生成"导出-*.bat"双击即出图`
    - `README.md:144`、`README.md:174`、`references/pipeline.md:136` 同样引用
    - `scripts/` 实际文件清单中**没有** `make_bats.py`(21 个 `.py` 全枚举过)
    - `git log` 显示 `6983bd0 refactor: bat 方案替换为 Python 自识别导出器(export_local.py…)` —— 文件被替换了,4 处文档没跟着改
    - `scaffold.py` 只创建 `src/` `export/` 与 fonts/vendor 联接,**没有任何步骤把 `export_local.py` 复制进项目**
  - 影响:Agent 执行 `pipeline.md` Step 6.5 必然 `FileNotFoundError`;而取代它的 `export_local.py` 在 `SKILL.md` 的资源索引里**一次都没被提及**(只出现在 README 的目录树里)。
  - 修复方向(二选一,推荐前者):① 删除 4 处 `make_bats` 引用,改写 Step 6.5 为"`scaffold.py` 自动把 `export_local.py` 投放为 `<proj>/src/导出.py`";② 恢复 `make_bats.py`。**不能两头都留。**

- **C3 动效指令自相矛盾,同一需求两次运行行为不确定。**
  - 证据:
    - `SKILL.md:134` 铁律 6:`动图(M2 已启用):无缝循环 2–6s…`
    - `references/guardrails.md:87` §6 末句:`所有动画(M2 之前一律不做)规范见 pipeline.md 动效节。`
    - `references/pipeline.md:149` 标题:`## 动效规范(M2 生效,现在写入案例时禁用动画)`
    - 同时 `references/animation.md` 存在(5722 字节),`SKILL.md:83` 资源索引标注"仅动图任务(GIF/MP4)"
  - 影响:guardrails 是**每次出图必读**的最高频分册(`SKILL.md:72`),Agent 读到"一律不做"就会拒绝做动画;而 SKILL.md 铁律说已启用。这不是风格问题,是**指令冲突**——比单点 bug 更伤,因为它让技能行为不可复现。
  - 修复:guardrails §6 与 pipeline 标题改为 `动图已启用(M2),规范见 references/animation.md`;若确实只在特定条件下启用,把条件写死。

**Important**

- **I1 `references/export.md:6` 承诺的"三级引擎"在代码里只有两级。**
  - 文档:`2. WPI CLI 单文件(wpi_cli_exe,约 63MB)…源码版不可用时自动切换(同参数命令行,退出码 0 = 成功)`
  - 代码:`scripts/export.py:27-31 find_wpi()` 只检查 `wpi_path/src/core/controller.py`,**全文不出现 `wpi_cli_exe`**;`_config.py:16-27` 的 `ENV_MAP` 也没有它。
  - 但 `wpi_cli_exe` 在 `config.example.json:4`、`config.json:4`、`config_gui.py:55`、`setup_wpi.py:65` 都在写 —— 写了一份没人读的配置。
  - 影响:无 WPI 源码时,Agent 按文档预期"会自动切 CLI",实际直接拿到 `WPI_NOT_FOUND`,可能反复重试而非转向 fallback。
  - 修复:在 `export.py` 的 `find_wpi()` 失败分支里实际调用 CLI(`cfg("wpi_cli_exe")`),或把 export.md 降为"两级引擎"。

- **I2 `ocr_path` 是死配置,而 frontmatter description 对外宣称 OCR 能力。**
  - `fetch_model.py:34` 写入 `ocr_path`;`README.md:130` 列进配置表;`README.md:90` 给出 `python fetch_model.py ocr` 命令。
  - 但**没有任何脚本消费 `ocr_path`**(无 `ocr.py`),且 `references/pipeline.md:28` 明确写着"用自身视觉能力读图,**不调外部 OCR 工具**"。
  - 影响:用户按 README 装 110MB OCR 模型,装完无处可用;description 里的"给图复刻(OCR/VQA)"也误导触发判断。
  - 修复:三选一 —— 补一个 `ocr.py` 消费者 / 删掉 OCR 部署链路 / 至少在 README 标注"OCR 模型已废弃,仅保留 VQA"。

- **I3 `preflight.py:107-109` 对 `harmonyos-sans` 永久误报缺失。**
  - 实测输出:`✓ [PASS ] 字体库: 28 款在位,缺 1 款: harmonyos-sans`
  - 根因:`download.json` 声明三文件 `HarmonyOS_Sans_SC_{Regular,Medium,Bold}.ttf`,而磁盘上是单文件可变字体 `HarmonyOS_Sans_SC.ttf`(`fonts/harmonyos-sans/` 下 20.6MB)。检查逻辑按清单逐文件名比对 → 永远认为缺。
  - 影响:每次预检都吐一条假告警,诱导 Agent 跑 `fetch_font.py` 重新下载,或误判环境不完整。
  - 修复:把 `download.json` 的 `files` 改为实际的 `HarmonyOS_Sans_SC.ttf`,或在 preflight 里加"目录内存在任意字体文件即视为在位"的兜底。

- **I4 `docs/adr/` 被 `.gitignore` 忽略,5 份 ADR 从不进仓库。**
  - 证据:`.gitignore` 第 9 行 `docs/adr/`;`git ls-files docs` 输出中**无任何 adr 文件**;远端 clone 拿不到。
  - 影响:ADR 的全部价值在于"让协作者看到当初为什么这么决定"(`0001` 联接 vs 绝对路径、`0005` 导出安全三禁令都是极硬的领域知识)。被 gitignore 等于全部失效,只在你本机可见。
  - 修复:删掉这一行,`git add docs/adr/`。**需确认这是笔误还是有意为之**(见 §7 待拍板)。

- **I5 字体数量口径三处不一致。**
  - `README.md:175`:`21 款开源中英文字体(内置 6 款代表)`
  - 实际:`fonts/README.md` 表格 28 行(= 28 个字体族);preflight 实测"28 款在位";磁盘 36 个字体文件;`git ls-files fonts | grep -c '\.ttf\|\.otf'` = **17**(与 `fonts/.gitignore` 的 6 个中文白名单 + 11 个英文白名单吻合)
  - `ADR-0004` 的"21 款/6 款"是决策当时的快照,ADR 保留历史口径可以接受;**README 是现状描述,必须改**。
  - 修复:README 改为"28 款字体族(仓库随附 17 款,其余按需 `fetch_font.py`)"。

- **I6 `config.example.json` 缺 `vqa_path` / `ocr_path`,但 README 配置表列了它们。**
  - `config.example.json` 的键:`wpi_path / wpi_cli_exe / studio_dir / ffmpeg / pexels_key / pixabay_key / huaban_cookie / iconfont_cookie / pinterest_cookie / proxy / vision_mode` —— 没有 `vqa_path`。
  - `README.md:130` 却写 `vqa_path / ocr_path | 本地 VQA / OCR 模块路径`;`preflight.py:147` 也在读 `vqa_path`。
  - 影响:新用户复制 example 建 config,永远配不上 VQA,预检长期 WARN。
  - 修复:`config.example.json` 补齐 `vqa_path` / `ocr_path`(空串)。

- **I7 尺寸真相源至少 5 处,且已经算出不一致。**
  - 定义点:`scaffold.py:29-50 SIZES` / `references/sizes-common.md` / `references/material-catalog.md` / `references/export.md` 尺寸表 / `SKILL.md:58-63` 核心 6 款 / 各 `references/formats/*.md`
  - **实测冲突**:易拉宝 `rollup` = 2362×5906,scale 2 → 应为 **4724×11812**。而:
    - `references/export.md:31`(尺寸预设表)写 `4724×11811` ❌
    - `references/export.md:71`(速算表)写 `4724×11812` ✅
    - `scripts/scaffold.py:40` 注释写 `4724×11811` ❌
    - 即**同一个文件内部都不一致**,且注释里算错了 1px。
  - 影响:印刷交付尺寸错 1px 通常无害,但"同一数字三种写法"意味着下一个改动点必然漏改某处 —— 这是 I7 的真正风险,不是这 1px。
  - 修复:抽出单一事实源(如 `references/sizes.json`),`scaffold.py` 与文档表格从它生成或至少加校验(见 §4 Step 1 的 selfcheck)。

**Suggestion**

- **S1 `scaffold.py:91` argparse help 写"默认绝对路径引用 Skill 字体库省空间",实现是 NTFS 联接**(`scaffold.py:137-158`)。`--embed-fonts` 的表述对,默认路径的描述是旧版残留。
- **S2 CLI 契约不统一**:20 个脚本里,`fetch_font.py` / `fetch_model.py` 把 `--help` 当普通参数(实测输出 `{"ok": false, "error": "未知模块: --help"}`);`export_local.py` / `junction.py` / `config_gui.py` 没有 argparse。建议统一 `--help`。
- **S3 `export.py:87 from PIL import Image` 无保护**,违背脚本头声明的"输出:单行 JSON"契约 —— 缺 Pillow 时 `--cmyk` 抛裸 traceback。
- **S4 `README.md:81` 称 config-editor 是"纯 tkinter 零依赖"**,但 `scripts/config_gui.py` 源码实测在托管 Python 3.13.12 下 `ModuleNotFoundError: No module named 'tkinter'`。只有编译好的 exe 才免依赖,应写明。
- **S5 无 `CHANGELOG.md`、frontmatter 无 `version` 字段**。迭代没有版本锚点,回归时无法指出"对比哪个基线";`README` 与 `ADR` 的口径漂移(I5)正是因为缺"改版本号时同步清单"这个动作。
- **S6 无 `tests/`、无 `.github/`(CI)**。2956 行脚本零自动化验证 —— C1 这种一行缺陷能存活到发布,根因就在这里。
- **S7 硬编码本机绝对路径**:`preflight.py:20 DEFAULT_WPI`、`preflight.py:147 DEFAULT_VQA`、`export_local.py:32 known = r"E:\平日资料\GitHub\WPI"`、`scaffold.py:26 STUDIO`。技能是发到 GitHub 的(`origin: GreenChennai/artboard`),别人 clone 后 preflight 直接 FATAL。另外 **WPI 缺失判 FATAL 过严** —— `export_fallback.py` 本可兜底(仅 PNG),应为 WARN。
- **S8 与 ADR-0002 的自我要求轻微偏离**:ADR-0002 定了"渐进披露",但 `SKILL.md` 内仍内嵌风格清单(4 款)、品类清单(5 款)、尺寸预设(6 款),而 `scaffold.py SIZES` 有 18 款、`styles-catalog.md` 有 145 个风格 —— 内嵌清单天然会漂移(当前"核心 6 款"与"实际 18 款"已不同步)。
- **S9 没有把 `docs/samples/` 14 张成品图用作回归基准**。它们是天然的 golden set;`compare.py` 目前只做人工并排,不参与自动校验。
- **S10 `tools/config-editor/artboard-config-editor.exe` 是入库二进制**(约 10MB 级),无法 code review,且与 `config_gui.py` 可能版本漂移。建议入库构建说明或改为源码分发。

### 1.2 Readability —— 通过(优秀)

- `SKILL.md` 的**资源索引即路由表**+"何时才读"列(`SKILL.md:65-92`)是同类 skill 里少见的成熟设计,直接回应了 ADR-0002。Agent 不需要猜"该不该读这份分册"。
- `pipeline.md` 每步都有"输入-动作-产出",`改稿协议` 用表格映射"用户说的话 → 动作"(`pipeline.md:62-68`),对 LLM 执行极其友好。
- 脚本统一单行 JSON + `error`/`hint` 字段(`export.py:56-58`),Agent 可解析、可自愈,不需要读 traceback。
- 唯一扣分:各脚本"用法"docstring 与 argparse `help` 偶有陈旧(S1),建议把 docstring 里的用法删掉、只留 argparse,避免第二处真相源。

### 1.3 Architecture —— 基本通过

- **做得好**:视觉风格(styles/)与品类(formats/)正交拆分(`SKILL.md:50` 明确写出"任何品类可配任何风格"),这是正确的分解方式 —— 避免 N×M 组合爆炸成分册。
- **做得好**:三级素材来源 + 强制 `版权风险-` 前缀 + "任何环节不得移除"(`SKILL.md:136`、`materials.md`),把法律风险工程化成了不可绕过的机制,而不是一句"注意版权"。
- **做得好**:ADR-0005「文字特效必须通过导出安全审查」从真机踩坑(backdrop-filter 无头不渲染 / 透明填充字 text-shadow 透底 / glitch 默认态截出普通字)提炼成三条硬禁令。这是最高价值的知识固化形态。
- **风险**:多真相源(§根因 R2)。尺寸、字体数、引擎级数、脚本清单都在 3-5 个地方各写一遍。
- **风险**:零可验证性(§根因 R3)。一个"技能"的正确性 = Agent 行为的确定性;而当前指令冲突(C3)+ 文档断链(C2)意味着行为不可复现。

### 1.4 Security —— 通过

- `config.json` 已在 `.gitignore` 第 2 行,实测 `git ls-files` 确认未被跟踪;`config.json` 里的真实 Pexels/Pixabay key 与 iconfont/pinterest cookie 未泄漏 ✓
- `tools/cookie-extension/manifest.json` 的 `host_permissions` **精确限定**三个域(huaban / iconfont / pinterest),未申请 `<all_urls>` ✓
- `dist/`(>100MB 模型包)已 gitignore,改走 GitHub Releases ✓
- 无任何上传/回传逻辑,全部本地 ✓
- 唯一提醒:入库的 `.exe`(S10)是供应链黑盒,虽不影响安全(纯本地 tkinter),但破坏了"可审查"性质。

### 1.5 Performance —— 通过

- 渐进披露(ADR-0002)+ 铁律 5「自检只在两个时机触发,之后改稿不自动自检不派子代理」(`SKILL.md:133`、`pipeline.md:121-125`)是针对 token 成本的务实取舍,且被明确写进最高优先级规则,不会被 Agent"好心"违背。
- 瘦身联接(junction)让批量制作零拷贝(ADR-0001),单项目不再 500MB+。
- 字体按需下载(ADR-0004)把仓库控制在可克隆体积。
- 唯一隐患:`preflight.py` 每次开工都跑,而它自身包含一次 `os.listdir` 全字体目录 + `import rembg` 探测;`rembg` 导入较重,实测当前环境(未装)很快,装了之后每次预检会付一次 1-3s 级导入成本。建议改为 `importlib.util.find_spec("rembg")` 探测而不真正 import。

---

## 2. 根因:为什么这些缺陷会出现(比缺陷本身更重要)

三条系统性原因,分别对应不同类别的缺陷。**修 bug 不修根因 = 下轮重新长出来。**

| 编号 | 根因 | 对应缺陷 | 本质 |
|---|---|---|---|
| **R1** | **文档先行、代码跟进,但两者之间没有同步机制**。`make_bats.py` 被删了,引用它的 4 处文档没人改;`wpi_cli_exe` 加了配置字段没人实现消费者;`ocr_path` 写入了没人读。 | C2 / I1 / I2 / S1 | 文档引用的符号**没有任何检查**保证其存在 |
| **R2** | **多真相源**。同一个数字(尺寸/字体数/引擎级数/自检时机)在 3-5 个文件里各写一遍,改一处必漏其余。 | I5 / I7 / S8 / C3(动效开关写了两处且相反) | 缺少"唯一来源 + 派生"的纪律 |
| **R3** | **零自动化验证**。2956 行脚本、0 测试、0 CI。所有回归依赖人肉。 | C1 能存活到 main / C2 断链三个月没人发现 / I3 假告警每次都看到但没修 | 没有"改完自动知道有没有坏"的回路 |

**结论**:**下一轮迭代的主线不是加能力,而是补上 R1/R2/R3 三个缺环。** 加内容(更多风格/字体/物料)会成倍放大 R2 —— 每加一个风格就多一处"SKILL.md 表格 vs styles/ 目录 vs styles-catalog.md"的三方漂移点。

---

## 3. 迭代方法论:六门禁迭代环

### 3.1 先定义"这个技能好不好"的六个验收维度

传统软件用"测试通过率"当验收;技能的验收对象是 **Agent 的行为确定性**。六个维度:

| 维度 | 含义 | 检查手段 | 通过标准 |
|---|---|---|---|
| ① 可发现性 | 该触发时触发,不该触发时不触发 | 拿 10 条真实用户口述跑一遍,看 description 是否命中 | 命中 ≥9/10,且无越界触发 |
| ② 可执行性 | 文档里写的每条命令/路径,实际跑得通 | 全脚本 `--help` 冒烟 + 引用路径存在性扫描 | 0 失败、0 悬空引用 |
| ③ 一致性 | 同一个事实在 N 处只有一种说法 | 多真相源 diff 脚本 | 0 冲突 |
| ④ 可移植性 | 干净机器上能跑通 | 换 `studio_dir` / 换无 WPI 环境跑 preflight | 无本机专属 FATAL |
| ⑤ 可验证性 | 改动后能自动知道有没有坏 | golden sample 渲染 + 像素/尺寸 diff | 关键品类可选回归 |
| ⑥ 可维护性 | 下一轮改动只需改一处 | 真相源数量审计 | 每个事实 ≤1 个权威定义 |

**当前得分估算(评审基线)**

| 维度 | 现状 | 主要缺口 |
|---|---|---|
| ① 可发现性 | B+ | description 宣称 OCR 但无该能力(I2) |
| ② 可执行性 | **D** | C1 崩溃、C2 悬空引用、I3 假告警 |
| ③ 一致性 | **D** | I5/I7/C3 三处冲突 |
| ④ 可移植性 | **F** | S7 硬编码本机路径,他人 clone 即 FATAL |
| ⑤ 可验证性 | **F** | S6 无测试无 CI |
| ⑥ 可维护性 | C | R2 多真相源 |

### 3.2 每轮迭代开工前必答的 7 个拷问(grilling checklist)

**在动手改任何东西之前,逐条回答;答不上来就先别改。**

1. **这条改动会改变 Agent 的行为吗?** 如果会,变化是**可预测且唯一**的吗?(如果两条规则一改就冲突,先解决冲突,别只改一条 —— 参见 C3)
2. **这个事实现在出现在几个文件里?** 我改了几处?剩下的会不会漏?
3. **有一个真实的失败案例吗?** 没有的话,这是"推测的需求"还是"真需求"?(推测的需求应进 backlog,不占本轮)
4. **新增的脚本 / 配置字段 / 目录,谁消费它?** 有没有孤儿?(I1 `wpi_cli_exe`、I2 `ocr_path` 都是孤儿)
5. **一台干净机器(无 WPI、无本机路径)上能跑通吗?** 跑不通的话,失败是 FATAL 还是可降级?
6. **用什么证据证明修好了?** 必须是可复现的观测(命令输出 / 渲染图 / diff),不能是"我看了一遍觉得对"。
7. **这次改动删掉了什么?** 删掉的东西还有引用者吗?(`grep` 全文再删)

### 3.3 迭代环(六个门禁,顺序不可颠倒)

```
        ┌──────────────────────────────────────────────────┐
        │  Gate 0  触发来源(只从这三种进,不凭感觉改)      │
        │   ① 真实使用中的失败(最高优先,带复现)        │
        │   ② 一致性体检报告(§4 Step 1 自动产出)        │
        │   ③ 能力扩张需求(最低优先,须回答拷问 #3)     │
        └───────────────────────┬──────────────────────────┘
                                ▼
   Gate 1  单一事实源对齐 —— 先决定"这个事实归谁管",再改
                                ▼
   Gate 2  可执行性验证 —— 每条被改/被引用的命令实跑一次,留输出
                                ▼
   Gate 3  一致性验证 —— 悬空引用扫描 + 多真相源 diff,0 冲突
                                ▼
   Gate 4  回归验证 —— golden sample 渲染,尺寸与关键区域对齐
                                ▼
   Gate 5  交付 —— version + CHANGELOG + tag + 变更清单
                                ▼
                        下一轮 Gate 0
```

**关键纪律**:Gate 1 必须在 Gate 2 之前。先想清楚"这个数字以后归谁管",不然修完还是多真相源。

---

## 4. 单轮迭代 SOP(可直接照做)

### Step 0 · 冻结基线(5 分钟)

```bash
cd .agents/skills/artboard
git status --short                 # 必须干净
git tag -a baseline-YYYYMMDD -m "迭代基线"   # 打锚点,回归时可比
```

同时把当前体检报告存档(见 Step 1 的输出),否则"改好了吗"无从回答。

**产出**:一个 tag + 一份体检报告快照。

### Step 1 · 跑自动体检(今日没有,需先建)

现状是**手搓**体检(本次评审就是手工做的)。建议一次性投入,把本次评审用到的检查固化成 `scripts/selfcheck.py`。最小可用版只需 5 条检查:

| # | 检查 | 实现要点 | 能抓住 |
|---|---|---|---|
| 1 | **悬空引用扫描** | 扫 `SKILL.md` / `README.md` / `references/**/*.md` / `docs/*.md` 里所有 `` `xxx.py` ``、`scripts/xxx`、`references/xxx.md`、`assets/xxx` 形式的引用,逐个 `os.path.isfile` | **C2**(make_bats 不存在)、未来的重命名遗漏 |
| 2 | **脚本冒烟** | 遍历 `scripts/*.py`,跑 `--help`,要求退出码 0 | C1 类崩溃(前提是脚本接 argparse → 见 S2)、S2 |
| 3 | **未导入即使用扫描** | 本次评审用的 AST 脚本(约 30 行,见附录 A),直接纳管 | **C1** |
| 4 | **配置孤儿扫描** | `config.example.json` 的每个 key,在 `scripts/*.py` 里 `grep` 至少一次出现 | **I1** `wpi_cli_exe`、**I2** `ocr_path` |
| 5 | **多真相源 diff** | 把 `scaffold.py SIZES` 与 `references/export.md` 表格解析后逐项比对 | **I7**(rollup 11811 vs 11812)、I5 |

**通过标准**:全部 0 error。任何一条非 0 即阻断本轮迭代的交付。

> 这 5 条检查覆盖了本次评审发现的 **6 个缺陷中的 6 个**(C1/C2/I1/I2/I5/I7)。性价比极高。

### Step 2 · 收集真实失败案例(每次实际使用后 2 分钟)

用户每次报障 / 你自己每次跑出意外,立刻追加一行到 `docs/FAILURES.md`(新建):

```markdown
- [2026-09-10] 双击 导出.py → NameError: shutil。复现:项目 src/ 有 index.html。
  期望:导出 PNG+PDF。→ 已修 (v1.1)
```

**纪律**:只记**真实发生过**的,不记"可能会"。没复现的进 backlog 不进本轮(拷问 #3)。

### Step 3 · 归类与排序

每条候选改动贴一个标签,然后按优先级排:

| 优先级 | 判据 |
|---|---|
| **P0** | Agent 行为不可预测,或文档承诺的能力直接崩溃(C1/C2/C3) |
| **P1** | 违反六大维度任一,但不阻塞使用(I1/I2/I3/I4/I6/I7) |
| **P2** | 体验/整洁度(S1-S10 里的非一致性项) |

**每轮只做 P0 + 当轮能验证的 P1。** 一轮塞太多 = 无法归因。

### Step 4 · 单点修复 + 立即验证

**一个 commit 修一个缺陷**,commit message 写清"症状 / 根因 / 验证方式"。

修完立刻跑 Gate 2 的那一条对应检查,把输出贴进 commit body 或本轮记录。**禁止"顺手把这个也改了"** —— 范围纪律,否则回归无法归因。

### Step 5 · 同步文档(单一事实源规则)

| 改了 | 必须同步 |
|---|---|
| 增删/重命名脚本 | `SKILL.md` 脚本清单 + 资源索引、`README.md` 脚本一览 + 目录树、`pipeline.md` 对应 Step |
| 改尺寸/预设 | `scaffold.py SIZES`(权威)→ 重新生成/校对 `export.md`、`sizes-common.md`、`SKILL.md` |
| 改配置字段 | `config.example.json` + `README.md` 配置表 + `_config.py ENV_MAP` + 消费脚本 |
| 改字体库 | `fonts/README.md` + `fonts/download.json` + `fonts/.gitignore` 白名单 + `README.md` 口径 |
| 改行为规则(铁律) | `SKILL.md` 铁律 + `guardrails.md` + `pipeline.md` **三处一起改**(C3 就是这么坏的) |

**规则**:如果一次改动需要改 3 个以上地方才能保持一致 —— 说明这个事实没有单一来源,**先抽来源,再改值**。

### Step 6 · 回归验证

最小可行回归(不需要 CI 也能做):

```bash
# 1. 环境体检
python scripts/preflight.py                 # 期望:无 FATAL,告警已知

# 2. 端到端渲染一个代表品类(用 docs/samples 里已有的工程参数)
python scripts/scaffold.py _regression --size xhs --fonts source-han-sans
# 写入 src/index.html(可用 docs/samples/xhs-cover.png 对应的已知工程)
python scripts/export.py --source <proj>/src --output <proj>/export/r.png \
    --width 1080 --scale 2 --height 1440
# 3. 断言:产出尺寸 = 2160×2880,且文件存在
```

**断言必须机器可判**(尺寸/文件存在/像素差),不能是"我 Read 了一眼挺好看"。Read 图用于**审美**校验,用于**回归**校验的是数字。

进阶:把 `docs/samples/*.png` 作为 golden,渲染同参数后跑 `compare.py` 做并排 + 像素差阈值。**先只覆盖 2-3 个代表品类,不要一次全上。**

### Step 7 · 交付与版本锚点

```bash
# frontmatter 增加 version 字段(SKILL.md 顶部)
# 追加 CHANGELOG.md
git add -A && git commit -m "fix(export): 导入 shutil,修复双击导出 NameError (v1.1.0)"
git tag -a v1.1.0 -m "一致性收口"
```

交付汇报模板(延续你现有的习惯):

| 项 | 内容 |
|---|---|
| 本轮改了什么 | 逐条,带 file:line |
| 验证证据 | 体检输出 / 渲染尺寸 / 复现命令 |
| 已知未修 | 明确列出,不许含糊 |
| 下轮建议 | 从剩余 P1 里挑 |

---

## 5. 优先路线图(三轮,建议顺序)

### 迭代 A · v1.1 「一致性收口」(纯修复,0 新功能)

**目标**:把六大维度里两个 F(可执行性、可移植性)提到 C 以上。**不加任何能力。**

| 序 | 任务 | 对应 |
|---|---|---|
| A1 | `export_local.py` 补 `import shutil` | C1 |
| A2 | 决定"双击导出"的归属:删 4 处 `make_bats` 引用 + 让 `scaffold.py` 投放 `导出.py`,或恢复 `make_bats.py` | C2 |
| A3 | 统一动效开关口径(guardrails §6 / pipeline 标题 / SKILL.md 铁律 6 三处一致) | C3 |
| A4 | `export.py` 要么实现 CLI 引擎,要么把 export.md 降为两级 | I1 |
| A5 | OCR:补消费者 / 删链路 / 标注废弃 + 改 description | I2 |
| A6 | 修 `download.json` harmonyos 文件名校验(或 preflight 兜底) | I3 |
| A7 | `.gitignore` 去掉 `docs/adr/` 并入库 5 份 ADR | I4 |
| A8 | README 字体口径改 28/17;`config.example.json` 补 `vqa_path`/`ocr_path` | I5 / I6 |
| A9 | 尺寸:确定权威源,统一 rollup 11812,并加多真相源校验 | I7 |
| A10 | preflight:WPI 缺失由 FATAL 降 WARN(有 fallback);`rembg` 改 `find_spec` 探测 | S7 / 1.5 |
| A11 | 硬编码路径外置:至少把 `export_local.py:32 known` 改为读 config | S7 |

**验收**:`selfcheck.py` 五条检查全绿;preflight 无 FATAL;端到端出一张 xhs 尺寸正确。

### 迭代 B · v1.2 「立基础设施」

**目标**:把"可验证性 F"和"可维护性 C"提上去,让下一轮迭代有安全网。

| 序 | 任务 | 说明 |
|---|---|---|
| B1 | `scripts/selfcheck.py`(5 条检查) | §4 Step 1,本轮核心 |
| B2 | 抽出尺寸单一事实源(`references/sizes.json`),`scaffold.py SIZES` 与文档表格从它派生或校验 | 消灭 I7/S8 的再生 |
| B3 | `docs/CHANGELOG.md` + `SKILL.md` frontmatter `version` | S5 |
| B4 | `tests/test_selfcheck.py` + `tests/test_smoke.py`(只测脚本契约:退出码/JSON 可解析) | S6 |
| B5 | 可选 `.github/workflows/check.yml`:仅跑 selfcheck + 单元测试(不需要图形渲染,秒级) | S6 |
| B6 | golden 回归最小版:2-3 个品类,尺寸断言 + 像素差阈值 | S9 |
| B7 | 统一 CLI 契约:所有 Agent 可见脚本支持 `--help` | S2 / S3 |

**验收**:`python scripts/selfcheck.py` 一键给出完整体检;任何人改坏悬空引用会被 CI 拦住。

### 迭代 C · v1.3 「扩能力 / 可移植」

**目标**:在安全网之上扩能力,且每次扩张都必须过六门禁。

候选(按价值排序,**每项都需先过拷问 #3 确认真需求**):

1. **风格/物料扩张**:当前 4 个风格分册 vs `styles-catalog.md` 145 个方向 —— 若真实使用中频繁"没有匹配风格",优先补 2-3 个高频风格,而不是一次补 20 个(拷问 #2:每加一个风格,漂移点 +3)。
2. **属性化自检**:把 `guardrails.md` 反 AI 味 12 条里**可机器判**的几条(正文行宽 ≤22 字、留白 ≥25%、强调色出现次数、层级字号比 ≥1.5)做成 `scripts/lint_layout.py`,让自检从"Agent 目测"升级为"脚本给数 + Agent 判断"。
3. **跨平台**(若确有非 Windows 用户):硬编码路径全部走 config + junction 逻辑加 macOS/Linux 分支(symlink);否则在 README 明确标注 "Windows only"。
4. **复刻质量闭环**:把 `compare.py` 接进 `replicate.md` 的 Step R4,输出结构化差异(色差 / 版式偏移量)而不只是并排图。

---

## 6. 反模式:迭代时不要做的事

| 反模式 | 为什么危险 |
|---|---|
| 以"加更多风格/字体/物料"为主线 | 每加一个就多 3 处漂移点(R2)。能力扩张必须建立在一致性机制之上 |
| 一次 commit 修多个不相关缺陷 | 回归失败时无法归因;你的 `git log` 里 `f5554b4` 那种"一次干 6 件事"的 commit 是 C2 断链的温床 |
| 只改代码不同步文档 | 这正是 C2/I1/I2 的来源 —— 删除/重命名后引用者没人查 |
| 在 `SKILL.md` 里内嵌会漂移的清单 | 内嵌清单 = 第二真相源。已内嵌的应逐步改为一句话 + 指向 references |
| 用"我 Read 了一眼觉得对"当验证 | 必须是可复现的观测(尺寸 / 退出码 / diff)。审美判断和回归判断要分开 |
| 把 FATAL 阈值调松以"让预检好看" | I3 那种假告警应该修根因,不是调阈值。阈值松了真问题也拦不住 |
| 在没有 golden 基线时改渲染参数 | 改 scale / settle 行为会让所有既有成图静默变化,没有基线就发现不了 |
| 给不同文件写不同的"当前状态" | README 写 21 款、fonts/README 写 28 行、preflight 报 28 —— 三处口径并存就是 I5 |

---

## 7. 需要你拍板的 3 个问题

评审中遇到 3 处**无法从代码判断意图**的决策,不改动,列在这里等你裁决:

1. **`docs/adr/` 进 `.gitignore`(第 9 行)是有意的还是笔误?**
   若是笔误 → v1.1 直接删掉该行并入库 5 份 ADR(推荐)。
   若是有意(比如 ADR 含内部信息) → 需要在 `README.md` 说明"ADR 仅本地可见",否则协作者会以为项目没有决策记录。

   用户选择: adr不入GitHub库

2. **"双击即导出"这个能力要不要保?**
   保 → 恢复 `make_bats.py` 或让 `scaffold.py` 投放 `导出.py`(二选一,推荐后者:少一个脚本、参数自校准)。
   不保 → 删掉 4 处引用,`pipeline.md` Step 6.5 整节删除,`export_local.py` 一并删除。**最忌讳的是留在文档里但不存在**(现状)。

   用户选择: 保留

3. **本地 VQA / OCR 的定位。**
   规则上已定"Agent 视觉优先"(ADR-0003),那么 `ocr_path` + `fetch_model.py ocr` + description 里的 "OCR" 三者是残留还是要补实现?建议:OCR 链路整体下线,VQA 保留为离线备选,description 去掉 "OCR" 字样。

   用户选择: 保留OCR,优先Agent,如果Agent没有OCR那就用Skill自带的

---

## 附录 A · 本次评审用的 AST 未导入即使用扫描器

约 30 行,可直接纳入 `scripts/selfcheck.py`(抓 C1 那类缺陷):

```python
import ast, os, builtins

def scan_missing_imports(path: str) -> list[str]:
    """返回文件中「未导入即当模块使用」的名字列表。"""
    tree = ast.parse(open(path, encoding="utf-8").read())
    imported: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                imported.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                imported.add(a.asname or a.name)

    roots: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute):
            r = n
            while isinstance(r, ast.Attribute):
                r = r.value
            if isinstance(r, ast.Name):
                roots.add(r.id)

    defined = set(imported) | set(dir(builtins))
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            defined.add(n.id)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(n.name)
        if isinstance(n, ast.arg):
            defined.add(n.arg)
        if isinstance(n, ast.ExceptHandler) and n.name:
            defined.add(n.name)
        if isinstance(n, ast.alias):
            defined.add((n.asname or n.name).split(".")[0])

    return sorted(r for r in roots if r not in defined)
```

## 附录 B · 本次评审的实测证据留存

| 命令 | 关键输出 |
|---|---|
| `python scripts/preflight.py` | `就绪 10 项 / 待补 2 项 / 阻断 0 项`;`字体库: 28 款在位,缺 1 款: harmonyos-sans`(假告警,I3);`playwright 未安装`、`rembg 未安装` |
| 20 个脚本逐个 `--help` | `export_local.py` 提前 return 未暴露 C1;`fetch_font.py`/`fetch_model.py` 把 `--help` 当参数(输出 `未知模块: --help`);`config_gui.py` → `ModuleNotFoundError: No module named 'tkinter'` |
| AST 全量扫描 `scripts/*.py` | 唯一命中:`[export_local.py] 未导入即使用: ['shutil']`(C1) |
| `git ls-files docs` | 无任何 `docs/adr/*`(I4) |
| `git ls-files fonts \| grep -c '\.ttf\|\.otf'` | 17(README 称 "21 款 / 内置 6 款",I5) |
| `grep wpi_cli_exe` | 出现在 config.example/config/setup_wpi/config_gui/export.md,**不出现于 export.py**（I1) |
| `grep ocr_path` | 出现在 fetch_model.py / config_gui.py / README,**无消费者**(I2) |
| `5906 × 2` | = 11812;`export.md:31` 与 `scaffold.py:40` 写 11811,`export.md:71` 写 11812(I7) |

---

*本手册的迭代环与拷问清单遵循工程实践:spec 先于 code、小步原子提交、证据驱动验证、诚实评审。修改本手册时请同步 `CHANGELOG.md`。*
