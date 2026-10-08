# Changelog

## v1.21.0 — 同步 Kiln v0.14.2:UP-3/UP-4 上游修复 + 编码参数首次可配(2026-10-08)

> 起因:上游台账登记的 **UP-3**(GIF 车道 `steps()` 硬切动画全片停在 from 色)与
> **UP-4**(GIF 调色板质量取决于本机有无 ffmpeg 且不声明 / MP4 的 GOP·B 帧·色彩标签
> 全仓不可配)由上游修掉并发行 **v0.14.2**。本轮同步部署、接入新能力、撤掉绕行。

### Added · MP4 编码参数首次可配(等了很久的两个参数)

`export.py` 新增四个透传参数,**默认全不传 = 落编码器默认 = 逐位保持旧行为**
(已用 `ffprobe` 核对:不带参数时成片仍含 B 帧,以前能播的现在还能播):

| 参数 | 语义 | 典型用途 |
|---|---|---|
| `--gop <N>` | 关键帧间隔(x264 链自动钉死网格) | 便于后续 `-c copy` 拼片 |
| `--bf <N>` | B 帧数;**`--bf 0` 是显式意图** | 关 B 帧 → 开头 DTS 不为负 → 部分播放器首帧不黑 |
| `--pix-fmt <fmt>` | 像素格式 | `yuv420p`(默认)/ `yuv422p` |
| `--no-color-tags` | **不写**色彩标签(关掉 ≠ 写 `unknown`) | 目标播放器对 bt709 标签处理异常时 |

实测:经 artboard 导出 50 帧 MP4,`--gop 25 --bf 0` → `ffprobe` 帧类型分布
`{I:2, P:48}`,**无 B 帧**,透传生效。

此前 `references/export.md` 写的是「参数不在 artboard 手里,调不了,除非改上游,
需要高质量只能走 ffmpeg 后处理」——那段连同它推荐的 `palettegen=stats_mode=diff`
**一并重写**:后者已被证明会静默错色(见下)。

### Fixed · 撤掉已失效的绕行

- **`references/animation.md`**:原写「`steps(1, end)` 这类硬跳变在 GIF 车道表现异常
  (2026-10-07 探针疑似不按关键帧走,待上游复核),需要硬切时先做 5 分钟小样探针或改走 MP4」。
  该限制已随 v0.14.2 解除,改为「已支持,但硬切对末帧是否落在片长终点敏感,
  仍建议先做小样探针」。
- **UP-3 / UP-4 台账行标记为已修(v0.14.2)**,并把修法与实测数据写进表内
  (便于日后回溯「为什么当初要绕」)。UP-3 的绕行方案(「卡点动画改用 linear/ease」)
  同步从工作约束里撤下。

### Changed

- `setup_kiln.py` 发行三件套升到 `KILN_VERSION=0.14.2` / 新 `RELEASE_SHA256`
  (`33a783c5…`)/ `BASELINE=(0,14,2)`。实测 `setup_kiln.py --force`:
  **sha256 校验通过 → 版本 0.14.2 == 基线 → 引擎自检 `{"ok":true,"formats":9,
  "browser_lane":"ok(true) Edg/154.0.4258.62"}`**。
- `docs/setup.md`、`docs/upstream-issues.md` 的版本引用同步到 v0.14.2
  (SKILL.md 与台账里「Kiln ≥0.14.1 起…」的沿革表述**保留** —— 那些行为从 0.14.1 起属实)。

### 验证

- 发行资产与本地构建 sha256 **逐位一致**(`33a783c5b3b331f3…`)。
- UP-3 在 release 二进制上确认修复:复现页 `steps(1,end)` 2s 硬切 40 帧,
  首帧 `(255,0,0)` → **第 20 帧 `(0,0,255)`** → 末帧 `(0,0,255)`,首蓝帧索引正好 20。
- artboard 端到端:静态 PNG 走**浏览器车道**(`engine: "browser"`),
  此前该车道在本机会因引擎侧合成器停摆而超时退化到自研引擎。
- `preflight.py` / `selfcheck.py` 全绿。

## v1.20.0 — 全量审查修复 + 同步 Kiln v0.14.1 + SKILL.md 定位瘦身(2026-10-07)

> 触发:一次对 v1.19.0 的全量代码审查(OCR 委派模式 + 定向核实)。**v1.19.0 引入的两处
> 未完成改动让 `export.py` 全线失效**,审查第一轮就实测复现;其余为审片台与 `check_slop.py`
> 的缺陷收口,以及同步上游 Kiln v0.10.0 → **v0.14.1**。
> 结论:不留半吊子上游缺陷 —— 下面每一条都有复现命令或代码位置。

### Fixed · export.py P0 回归(v1.19.0 遗留,实测复现)

- **`--timeout` 参数根本没注册**:`export_via_kiln` 已在用 `args.timeout`,但 argparse
  从未声明 → 每一次导出都走进 `except Exception` 报 `KILN_CLI_FAILED: 'Namespace'
  object has no attribute 'timeout'`。**技能的主路径 100% 失效**,且错误信息完全指错方向。
- **`_proc.Result.stdout` 已是 str,代码还在 `.decode()`**:`r.stdout.decode(...)` 抛
  `AttributeError`,`r.stderr.decode(...)` 同理。修掉上一条之后立刻撞上这条 —— 两处漏改。
- **`find_kiln()` 末尾的"兜底放行"循环**:注释写"让上层拿到可诊断错误,而非静默用旧 CLI",
  代码却恰恰是把参数面滞后的旧 CLI 放行出去。**注释与行为相反**,是最典型的一处兜圈子。
  改为三处候选(含显式配置的 `cfg`)走**同一条**能力判定;全不满足时按"缺哪个 flag"
  报 `KILN_TOO_OLD`,不再让人从一句 `KILN_CLI_FAILED` 里猜。
- **能力探测漏了 `--duration`**:动画车道全靠它。只探 `--engine/--height/--vector`
  分不出新旧 CLI(0.14.1 起 `--max-wait` 从"静默忽略"变成真总预算,行为已剧变)。
- **`run_playwright_fallback` 仍用 `subprocess.run(timeout=600)`**:兜底车道会拉起
  Playwright 浏览器(孙进程继承管道),正是 `_proc.py` 头注描述的"timeout 形同虚设"。
  `_proc.py` 写了两天,自己却没在自己的兜底路径上用 —— 现已统一。

### Fixed · `--max-wait` 语义与 Kiln 0.14.1 撞车(实测)

Kiln 0.14.1 把 `--max-wait` 从**静默忽略**改成**真接线**的每实例总 deadline
(`set_overall_deadline`;settle 与全部 CDP 长等待被 `min(默认上限, 剩余预算)` 收口)。
而 artboard 一直把 `--max-wait` 当**动画时长**用 —— 于是"给动画时长"意外变成
"给整条导出链路的总预算"。实测(`--max-wait 0.5` 跑重页面):浏览器车道直接失败 →
**静默降级自研引擎**(`engine_fallback:true` + `degraded:true`)→ 真实海报页出废图。

- 三个时间量彻底分家:`--max-wait`(动画时长,透传 `--duration`)/
  `--timeout`(进程树墙钟上限)/ `--max-wait-budget`(引擎预算,**默认不下发**)。
- 命中 `KILN_CLI_TIMEOUT` 时按"先调大 `--timeout`,再怀疑引擎"给提示,并登记 UP-5。
- 新认 `KILN_CANCELLED`(Kiln 0.14.0 的协作取消,退出码 130)—— 取消不是故障,单独报。

### Fixed · check_slop.py

- **规则崩溃被静默吞掉**:`except Exception: continue` 让"签名与调用不符"的规则
  悄悄失效 —— 实测中 `rule_cjk_leading` 因签名没跟着改就整条不跑了,门禁显示"通过"。
  改为收集并在结果里报 `rule-crashed`(P2,附异常类型与消息)。**门禁"看起来过了"比误报危险得多。**
- **死参数**:`lint_page(..., ignores)` 在函数体第一行就被 `parse_ignores` 的返回值覆盖,
  调用方永远传 `set()`。删。
- **四路分发阶梯塌成两路**:`raw-hex` / `accent-overuse` / `else` 三个分支调的是同一个
  `fn(html)`;`rule_canvas` / `rule_cjk_*` 的 `css_all` 形参从未被读。收敛成 `_call()` 一处。
- **死代码 `TAGS`**(定义了从未引用)、**`RULE_META` 兜底分支**(`get(rid, (level, ""))`
  永远不会走到,因为动态规则全在台账里)。
- **文件头规则表与台账不符**:表里写 `P1 canvas-discipline`,台账里是 P0(共 9 P0 + 6 P1)。
  表改成从台账口径重写,并写明"级别台账是唯一真相源"。
- **`line-height` 的百分号双算**:`px = num if unit=="px" else num*fs` 之后又用
  `if unit=="%"` 覆盖一次 —— 中间那行对 `%` 是错的,靠后面覆盖蒙对。改成一个 dict 查表。
- **`rule_raw_hex` 只扫第一个 `<style>` 块**:拆成多段样式的页,后半截的裸 hex 全漏。
- **`--strict` 下 `files[].ok` 与 `blocking` 自相矛盾**:单页 `ok:true` 但整体 `blocking>0`。
- `rule_canvas` 扫全 html 而不只是 `<style>`:行内 `style="position:fixed"` 同样违反铁律 1。

### Fixed · 审片台(tools/review-station,本次审查的主体)

- **`sb-strokecolor` id 大小写不匹配** → **每次开页必弹"页面缺 1 个控件"红条**。
  `cfgApply` 用 `$("sb-" + kCamel(k))` 查,配置键是 `strokeColor`,控件 id 是全小写;
  `getElementById` 大小写敏感。`kCamel` 本身还是个**恒等函数**(纯兜圈子)。
  改 `.toLowerCase()` 查表并删掉 `kCamel`。
- **行距滑块写进错单位**:配置存 `1.35`,滑块是 `100..220` 的 range → 被钳到 100,
  显示 100% 而实际 135%,用户一动就跳变。现在按 `lh` 显式换算后再赋值。
- **坏 JSON 静默清空审片意见**:`read_json` 解析失败 `return {}`,于是
  `notes`/`subs`/`config` 的 POST 把它当"用户要存空内容"写盘 —— 浏览器崩溃或代理
  截断一次,已落盘的审片意见**不可恢复地清空**。改为抛 `BadRequest` + 400 拒写。
  实测回归:坏 body → HTTP 400,原有意见仍在。
- **裁片段任务无超时**:`for line in proc.stdout` 阻塞到管道 EOF,ffmpeg 卡死则 job 永远
  `running`、前端 1.5s 无限轮询、`JOBS` 只增不删。与刚写完的 `_proc.py` 口径**相反**。
  按段长 6 倍 + 60s 兜底强杀整棵进程树。
- **`jid` 用毫秒时间戳会撞键**:同一毫秒点两次渲染,后一条覆盖前一条,先完成的把
  state 写成 done,前端轮询到错误任务。改 `uuid4().hex[:8]`。
- **工具自己的产物污染成片探测**:`find_mp4s` 扫 `WORK`,而 `片段/`、`字幕导出/`
  是中文目录名,`_scan` 只跳过 `.`/`_` 开头的 —— 点几次「渲染此段」后
  `primary_mp4()`(取体积最大)会锁到某个片段。实测修复后 `refs` 干净。
- **字幕导出回环丢字幕**:`字幕导出/*.srt` 被列进"可编辑字幕候选",用户切回它 →
  用被按片长裁过、丢过整条的版本覆盖 `字幕轨.json` → **丢的字幕永久丢失**。已排除。
- **意见文本注入**:`buildMarkBars` 把 `tag`/`note` 拼进 `title="…"`,`paintMarks` 把
  `tag`/`note`/`fix`/元素名直接拼进 `innerHTML`;`esc()` 只转 `&<>`、**不转引号**,
  而且这两处根本没用它。意见文件会被 Agent 写回 → 跨进程注入通道。现补全 `esc()` 并全部走它。
- **Range 后缀区间解析错**:`bytes=-500`(末 500 字节)被当成 `bytes=0-500`,返回文件头。
  416 缺 `Content-Range: bytes */size`;多段 Range 被静默当单段按 206 返回。全部修正,
  三种情形均已实测(`0-99` / `-50` / 越界)。
- **取帧缓存键只到秒**,且 ffmpeg 中途失败留的 0 字节文件会被永久缓存成坏图。
  键加字节数、失败删文件、`with` 读文件。
- **每次探测/取帧弹黑框**:`ffprobe`/`ffmpeg` 都没传 `CREATE_NO_WINDOW`(三处补齐),
  而 `_proc.py` 早就把它列为 Windows 必需项。
- **死代码/迁移遗留**:`PY` 变量、`review_station.py` 未用的 `import urllib.parse`;
  HTML 里只 `log()` 的死控件 `sel-sub`(option 还写着移植时漏改的 `../06_成片输出/…`);
  `sb-open`/`sb-srt` 的 title 也还写着 `06_成片输出`;一处注释乱码字(`放��视口里`)。

### Fixed · 引擎发行同步(`setup_kiln.py`)

- **下载无完整性校验**:`download()` 只保证字节流落盘,不保证落的是 exe。代理截断 /
  把 404 的 HTML 存成 `.exe` / CDN 半截文件,都会得到一个"下载成功"的**坏引擎**;
  而 `--version` 探测失败只报「继续自检」,于是坏引擎照样被写进 `config.json`,
  之后每次导出才炸。现按发行资产承诺的 sha256 校验,**不符则拒绝写 config 并保留产物**
  (留产物是为了能比对与复现)。实测:传错值 → 退出码 3 + 打印期望/实际。
  用户自带 `--from` 的第三方资产**不比对**官方 sha256(必然误报),可用 `--sha256` 自带。
- **版本没有基线,坏版本也报 OK**:低版本引擎照样能导 PNG,于是被静默接受;而 0.14.1
  起 `--max-wait` 从"静默忽略"变成真总预算,拿老引擎配新参数会**静默出废图**。
  现装版本 vs `BASELINE` 逐元比,低版本**告警但不拦**(用户可能故意用老版做对比),
  并指明 `export.py` 会报 `KILN_TOO_OLD` 而不是静默用错语义。
- 发行事实集中成三件套 `KILN_VERSION` / `RELEASE_SHA256` / `BASELINE`(原先 URL 散在
  函数体里、sha256 根本没有),换版时三处同改;`docs/setup.md` 与
  `docs/upstream-issues.md` 补上这条同步纪律与实测记录。

### Changed

- **SKILL.md「定位」瘦身**:原来 32 行的定位段把地图/模式 W/模式 H/审片台四条分支的
  能力矩阵、工具清单、机检、约束全复述了一遍,与下面的资源索引表**内容重复**。
  改为「一句定位 + 不适配清单 + 资源索引(按需读取,禁止批量预读)」,资源索引上提到
  定位处并按 **① 五条分支(触发词 → 必读 → 交付物 → 机检)② 主流程常用分册
  ③ 素材/位图/交付/环境** 三段重排;分支的硬约束收成五条要点清单,细节指向各自那一册。
  重复的旧表整段删除。
- **README 追上现状**:「五问协议」→ **Brief Gate 九字段检查单**(v1.19 已改口径);
  补 `check_slop.py` 这道门禁(原文只写 `check_overflow`)、补审片台与模式 H/矢量两条分支;
  Kiln 徽章与基线 v0.10.0 → **v0.14.1**;新「交付后审阅(审片台)」一节;
  致谢补 open-design / hyperframes 两库的改编来源;脚本一览补三个时间量的说明。
- **`references/export.md`**:补「三个时间量」对照表 + UP-5 实测帧率;错误码表补
  `KILN_TOO_OLD`/`KILN_CLI_TIMEOUT`/`KILN_CANCELLED`;删掉指向已失效行号的引用。

### 台账(`docs/upstream-issues.md`)

- **UP-4 勘误**:原登记"GIF 走单 pass 内置量化(无 palettegen 两 pass)"**不准确** ——
  `frames.rs:105` 的 `palettegen=stats_mode=diff` + `paletteuse=dither=sierra2_4a`
  自 v0.9.0 起就存在,只是 `if ffmpeg_available()` 门控,且报告里不声明走了哪条。
  真实缺陷是"**质量取决于本机有没有 ffmpeg 且不声明**"。MP4 码率已由 `--bitrate` 暴露,
  仍缺 GOP / `-bf` / 色彩标签。状态改为「部分已修」。
- **UP-3 复核未修**:0.14.1 上重跑原复现(40 帧 @10fps,`steps(1,end)` 红→蓝),
  取帧读中心像素**全为 (255,0,0)**,第 20 帧后应为 (0,0,255) —— 仍未修,结论不变。
- **UP-5 新增**:动画车道实测 0.88 帧/秒(375 帧 427s),且长任务后**残留 27 个孤儿
  `msedge` 进程**会把后续导出的截图拖到超时。
- **UP-6 / UP-7 新增**:动画两道结果 JSON 的 `width/height` 未传时恒为 0(下游尺寸门必错);
  浏览器两条车道 `degraded` 硬编码 `false`(降级门禁被静默绕过,与 ADR-0046 相悖)。
- **纪律条款**改为可执行路径:实测复现 → 订正事实 → 登记 + 绕行 → **由用户**提 issue
  → 复查改状态。明确「确认修好之前不删本行」(删了丢复现步骤),且提 issue / 改上游 /
  关 issue 都不自动做。

### 验证

- `export.py` 真实导出通过(PNG 走浏览器车道,JSON 含 `width/height/frames/engine`);
  浏览器车道不可用时**自动兜底按设计生效**:拒绝信任自研引擎 → 改走 Playwright 重出
  → 返回可用 PNG + 明确告警。
- `check_slop.py` 固样例判定不变(坏样例 10 P0 + 4 P1 / 好样例 0);全量 49 个内置样例
  跑一遍 **0 条规则崩溃**,P0>0 集中在 `slop-bad/`(故意)、`h5-bad/cdn.html`(故意)、
  `video-opener.html`(104px 双行中文主标行高 —— 即 v1.19.0 已知的那一条)与
  地图 demo 页(用 100vh,非海报稿)。
- 审片台端到端:ping / meta / notes 写入 / **坏 JSON 400 且意见存活** / Range 三态 /
  裁片段 job done / `refs` 不被片段污染 / 取帧返回真 PNG(25843 字节)。
- `selfcheck` **FAIL 0 / WARN 0 / PASS 12**(引用 1008 处 · 路由 65/65 · 脚本 75 全部可达)。
- `preflight.py` 全绿(Kiln / Edge / playwright / ffmpeg / 字体库 28 款 / vendor / rembg / 图库 key)。
- `setup_kiln.py` 两条路径实测:正常探测 → 版本 0.14.1 == 基线,引擎自检 `ok:true`;
  错 sha256 → **拒绝写 config**、保留产物、打印期望/实际。
- 同步 `VellumBench`:`main` 612a405 → **007d8e1**(0.14.1 发行,65 提交)已入库;
  `target/release/kiln-cli.exe` 原是 9/28 的 **v0.10.0** 旧物(`6f714f2d…`),按当前 HEAD
  重建后 sha256 为 `4e303144…` —— **与已发布资产 `00185547…` 不同**:Rust release 默认
  非位级可复现(无 `build-std`、工具链版本参与码生成)。但**输出等价**:同一真实样例
  (`assets/cases/card-case.html` @1080×1440)两个构建导出的 PNG **sha256 逐位一致**,
  `selfcheck` 都是 `{"ok":true,"formats":9}`。**故不覆盖已发布资产** —— 同版本号下
  换资产会让已下载者拿到不同文件,并连带失效 `setup_kiln.py` 里记录的 sha256。
  另:GB 镜像那条「可复现但无 sha256」的路子给不出校验值,所以完整性校验**只对正式资产生效**。
- `VellumBench` 补入 `docs/iteration-review-2026-10-04.md`(653 行;上一条发行提交的
  message 写了「iteration-review 收口后」,但那份记录本身一直只躺在工作区),已推送。

## v1.19.0 — 机检三连 + 交付后审阅(审片台)并入 + 两库方法论吸收(2026-10-07)

> 依据两条外部输入:**① 迭代指导**(基于 heygen-com/hyperframes 与 nexu-io/open-design,
> 两库均 Apache-2.0,已浅克隆到 `_ref/` 供逐条查证);**② MV 审片台资产包**(真实 MV 项目
> 33 轮返修沉淀:20 条审片台铁律 + 8 条渲染铁律 + 4 条诊断方法论 + 7 个机检门禁 + 一个
> 纯标准库的网页审片台)。落地时**改编处逐条标注来源**,引用的第三方规则文件在文内注明许可。
> 抄写合规:两库 Apache-2.0 / guizang-ppt MIT / refero_skill MIT 均允许改写与私有使用;
> 若将来整体对外发布,在 NOTICE 加一行「部分规则/代码改编自 hyperframes、open-design、
> guizang-ppt(歸藏)、refero_skill」即可。

### Added · 机检三连(AI 味 / 铁律 / 中文行高)

- **`scripts/check_slop.py`(新)** —— 纯 stdlib、无浏览器、单页 <0.3s 的静态机检,
  移植 open-design `apps/daemon/src/lint-artifact.ts` 的规则集并按 artboard 口径重定级:
  **P0** 默认 indigo / 紫蓝渐变 / 蓝青"信任渐变" / emoji 当图标 / 编造指标 / 填充文案 /
  标题回落系统无衬线 / **中文标题行高 <1.3** / **离线铁律(引用 http 资源)** / **固定画布(100vh·fixed)**;
  **P1** 大写字距 / `:root` 外裸 hex / 强调色滥用 / 圆角+左彩边 / 中文负字距。
  每条 finding 带 `{severity,id,message,fix,snippet}` —— **fix 字段直接给修法**;
  支持 `<!-- slop-ignore: 规则id -->` 显式豁免(交付时要说明理由)、`--strict`/`--only`/`--list-rules`。
  与上游的差异逐条注在文件头(left-accent 降 P1:引用卡合法;新增两条铁律与两条 CJK 规则)。
- **`docs/samples/slop-good` + `slop-bad`(新固样例)** —— 好样例必须零 P0/P1(规则过严即报)、
  坏样例必须报出 P0(检查器钝化即报),接入 selfcheck 的 `golden` 门禁。
  校准:技能自带 39 个样例稿过一遍,只在实际违规处报出 1 条 P0(见下"发现")。
- **`references/guardrails.md` §5.1/§5.2(新)** —— **AI 味七宗罪表**(判据/谁查/修法),
  并给原有 12 条自检逐条标 **【机检】/【目检】** —— 规则文件与机检脚本谁管什么,对 Agent 诚实
  (上游的契约写法:`auto-enforced by the linter` vs `guidance, not auto-checked`)。
- **`references/cjk-typography-css.md` §一(新)** —— **行高与字距三条数值铁律**:
  中文 Display/H1 **1.3–1.4**(大字无豁免)、正文 1.7–1.8、负字距是拉丁专属、大写 ≥0.06em;
  章节重编号(原 §一–§十 → §二–§十一),同步 `typographic-expression.md`/`bilingual-typography.md`
  的 §四/§八 引用与本节自检 7 条 → 9 条。
- **门禁顺序**:`pipeline.md` Step 6.0 与 `SKILL.md` 改为"先静态后几何"
  (`check_slop.py` → `check_overflow.py`);铁律 5 的机检豁免同步到两条脚本。

### Added · 交付后审阅(审片台)并入

- **`tools/review-station/`(新)** —— 网页审片台:画面逐帧 / 时间轴缩放 + 磁力吸附 /
  字幕行内编辑 / **元素级拾取**(F12 式,带画布坐标)/ 意见落盘 / 离线队列 / 性能面板。
  服务端**纯标准库**(`review_server.py`,11 个 action);按 artboard 布局重写,**移植必改 6 处全部改完**
  (显式 `--root`、音频由 `meta` 探测、落盘路径参数化到 `--work-dir`、字幕候选走 `subfiles`、
  `--stop` 补 POSIX、`shot`/`render` 改为基于成片的 ffmpeg 出帧/切片),另加**双挂载**
  (`/__rv/*` → 工具目录)与 accept 队列 5→128(并发取帧不再 `ERR_CONNECTION_REFUSED`)。
  片段编码吸收了 hyperframes 的两条:**`-bf 0`**(消负 DTS,不再出现"音频先响、画面卡首帧")+ **偶数尺寸 pad**。
- **`references/review-loop.md`(新分册)** —— 口径层:意见文件即 **Agent 接口**(JSON 字段与读法)、
  交付后审阅的定位与边界、**交互层通用铁律**(contenteditable 三硬规则 / 保存层抗打离线队列 /
  磁力吸附按像素 / 缩放必配平移滑条 / flex 列分离操作区与数据区 / 唯一临时名 / 文本清洗顺序 /
  拆并互逆 / 快捷键白名单)、字幕是审片台自己的图层与三格式解析坑、
  **诊断方法论**(缩略图会骗人→numpy 量化;找真凶不改现象;量化后才写铁律)、
  **MV 动效补强**(音频→节拍→逐句时间轴数据链、多镜头工程三原则、`sat((t-t0)/w)` 窗口判断、
  缓存只能影响预览的三道防线)、**与既有能力的 4 处重叠裁决**。
- **3 个机检门禁(新)**:
  `check_review_ui.py`(页面自检:id 引用 / 页签配对 / 审片台与影片页 DOM 一致性)、
  `check_review_cache.py`(缓存隔离审计:同一 t 反复画 A/C/D **逐字节相同** + 跨页 AA 容差)、
  `check_px_baseline.py`(成片像素基线回归:差异像素占比 ≤0.05% 且最大通道差 ≤64,与 `compare.py` 分工)。
- **`docs/adr/0028`(本地留档)** —— 记录"为什么引入交付后审阅、为什么不扩写 `video-motion.md`、
  为什么工具进 `tools/` 而门禁进 `scripts/`"。
- **`references/revision-protocol.md` §10(新)** —— 动效/视频的改稿出口:读意见文件 → 按 `el` 先定位 →
  定点改 → 回写状态;并说明该入口对海报/图文同样成立。

### Added · 两库方法论吸收(P1)

- **`intake.md` §封闭词表**(新):维度 → 封闭取值 → 真相源,配两条硬规则 ——
  **未识别的值必须反问不许猜**、**末尾必须报告哪些维度用了默认值+按哪条规则推的**。
- **`style-guide.md §2.5`(新)**:歸藏 guizang-ppt 的三个工程机制 —— **类名预检**(模板是类名唯一真相源)、
  **主题封闭**(不接受现场 hex/禁跨风格拼配)、**症状/根因/处方三段式 checklist**。
- **`design-review-rubric.md §3.5`(新)**:**机械可数规则**(眉题每 3 区块 ≤1 / 布局族最多连续 2 /
  格数=条目数 / 跑马灯 ≤1 / 同意图一个 label / 主视觉文本 ≤4 / CTA 不换行 / 禁三等分特性卡)
  + **前置推理块**(读场一句话 / 三旋钮 / 数学验证三行)。
- **`brand-system.md §2.4` + §5.1(新)**:品牌 token **四层模型**(A1 识别 / A1 结构 / A2 操作 / B 槽位)
  与"**必须全量声明,不能靠运行时 fallback**"的论证、`color-mix(in oklab,…)` 派生色、克制清单;
  以及"换物料按**角色**映射(canvas/ink/accent/display),不逐个 hex 替换"。
- **`effects.md §〇`(新)**:货架格式六字段(`what/use_when/avoid_when/variables/pairs_with/cues`)
  + **适用速查 40 行 / 覆盖全部 43 式**(use_when / 真实误用型 avoid_when / pairs_with,部分行合并成对配方);
  `styles-catalog.md` 同步该格式口径。
- **`animation.md §1.1/§1.2/§3.1/§3.2`(新)**:确定性三件套(`Math.floor(t*fps+1e-9)` 帧网格量化、
  页面 settle 链(字体→图片"失败即就绪"→`decode()` 上 GPU→背景图)、double-capture、
  四类禁用),时长阈值表与两条红线(1s 内闪烁 ≤3 次 / 静止 ≠ 冻结),**形容词→缓动映射表**、
  时长速记、**stagger 情绪表**。
- **`video-motion.md §九·五`(新)**:分镜描述**改写对照**(别写"一切静止"、补尾拍、两事件显式让位、
  画面文案加引号、形容词→参数),并指路 `review-loop.md §六` 的 MV 数据链。
- **`export.md`(新节)**:GIF/MP4 的**期望编码参数**与被委托给 Kiln 的现实(全仓无 `palettegen`/`libx264`,
  故"参数不可调")+ 上游建议;`docs/upstream-issues.md` 登记 **UP-4**。
- **P2 三小项**:`responsive-reflow.md §2.1`(横→竖字号系数 ×1.3/×1.2、padding 收到 24–36px)、
  `materials.md §5.1`(检索用词两极规则:原子档或具体档,**具体查询失败就丢弃不放宽**)、
  `replicate.md` 头部补"**测量而非记忆**"的机制解释(模型均值回归到 Inter+indigo 的根因)。

### Corrected · 上游二次查证(同日)

指导里给的两处路径与规模描述与上游实际不符,已按**真实文件**二次核对并修正内容(不是只改注释):

| 指导原文 | 上游实际 | 本次修正 |
|---|---|---|
| hyperframes `registry/`(400 积木 / 237 组件货架) | `registry/components/CATALOG.md` = **"the shelf of 21"**(21 条 hero 原语,手写散文货架);其余 ~236 个组件只有极简 `registry-item.json`(无 `use_when`),两套互不引用 | `effects.md §〇` 补上 CATALOG 的**文件级四条约定**:先查货架再自造 / **`avoid_when` 是 QA 真误用、当硬约束** / **多出来的时长变 HOLD、不是拉长动画** / 变量只传要改的 |
| open-design `docs/prompting/vocabulary.mdx`(同事首轮报"不存在") | 实际在 **hyperframes** `docs/prompting/vocabulary.mdx` + `anatomy.mdx`;但**没有独立的"stagger 情绪表"** | `animation.md §3.2` 改为**四条硬规则**(无共享起止时刻 / 偏移必须短于动画、否则变排队 / 延迟配角不延迟焦点 / 只对"正在发生"错峰,`项数×stagger ≤ ~0.5s`)+ 档位参考;`video-motion.md §九·五` 补齐为**原文 6 组改写**(新增"模糊否定""格式盲数字"),并新增 **§九·六**(简报六段式 `[route][spec][beats][copy][technique][negatives]` + 每拍五槽 `[元素][动作][布局][风格][时间]` + 转场能量三档) |

### Fixed

- **selfcheck `refs` 门禁两处盲区**:① 脚本调用检查此前只认裸文件名且只在 `scripts/` 下找 ——
  `tools/` 下的工具脚本完全不在覆盖内;现按**已知顶层目录**(scripts/tools/docs/…)解析,
  `$S/x.py`、`<skill>/tools/x.py`、`../tools/x.py` 三种写法都判对(修完引用核验 947 → 992 处);
  ② `docs/review/` 的过程文档豁免与 `.gitignore` 对齐。
- `jsonfail` 用例 25 → **29**(新增 `check_slop` 2 条 + 三个审片台门禁 4 条);
  `golden` 增加 slop 固样例 2 组判据。

### Verified

- 全量自检 **FAIL 0 / WARN 0 / PASS 12**:引用 994 处、路由 **65/65** 分册、脚本 **74** 个
  (冒烟 57、失败路径 29)、冒烟/构建/部署/过期引用/素材/基线/数字一致全绿。
- **上游两条 issue 已提交**(按台账纪律,issue 稿全文保留在 `docs/review/05-上游issue待提交稿.md`):
  UP-3 → VellumBench **#1**(GIF `steps()` 错帧)、UP-4 → VellumBench **#2**(编码参数请求);
  `docs/upstream-issues.md` 两行的「上游状态」已由"待登记/待复核"改为**已提交 + 链接**。
- `effects.md` 选用速查**补齐到全 43 式**(40 行,部分行合并成对配方),并保持"引用的配方 id 都存在"。
- **机检校准**:`check_slop.py` 过技能自带 39 个样例稿 → 1 条 P0(video-opener 的 104px 双行中文主标
  `line-height:1.22` —— 正是新铁律要抓的高频违规)+ 7 条 P1;好/坏固样例判据稳定。
- **审片台端到端**(真实 MV 样例工程 + 合成项目两轮):11 个 action 全通;`subfiles` 识别 5 份样例字幕;
  `srt` 按片长裁剪(截断 1 / 丢弃 0);无成片时 `shot` 回 `NO_MP4` + 提示;
  页面 `window.__rv` 挂载、**14 个 canvas 渲染出影片**、非预期 404 = 0(仅字体 404,属样例包已知限制);
  `check_review_ui.py` 0 issue(157 个 id / 137 处 JS 引用 / 8 页签配对 / DOM 一致);
  `check_review_cache.py` 页内纯度 A=C=D 逐字节相同、0 页面报错;
  合成项目 `shot` 出真 PNG(24KB)、`render` 裁 1–3s → ffprobe 核验 **`has_b_frames=0` / yuv420p / 2.000s**。
- `check_px_baseline.py` 三分支实测(相同帧过 / 微差但超通道差门限被拦 / 整体变色被拦)。

## v1.18.0 — 地图模块并入 + 两轮审计缺陷收口(2026-10-07)

> 依据:两名只读审计员的全量报告(脚本 18 项 / 文档-代码一致性 23 项)+ 地图模块
> (原 `map-studio`)整体并入。全部结论都带复现命令,修完逐条实测。

### Added · 地图模块整体并入(不再是独立的附属模块)
- **脚本**:`map_tiles.py`(高德瓦片平面拼接+网点)、`fetch_osm_data.py`(OSM 五层矢量)、
  `svg_map.py` / `svg_iso.py`(主题化 2D / 2.5D 等轴测 SVG)、`render_3d.py` /
  `render_3d_vec.py`(真 3D:栅格底图 / 全矢量主题)、`svg_preview.py`(SVG→PNG)、
  `compute_route.py`(A\* 寻路)、`build_player.py`(自包含动画播放器)、
  `probe_tiles.py`(底图源探测)、`test_v7.py`(V1-V12 自动化验收);
  内部层新增 `_map_common.py`(浏览器/代理/缓存/临时页单点)与 `_map_mercator.py`(瓦片数学 +
  **本地** WGS-84 ↔ GCJ-02 实现)。
- **子技能卡片**:`references/map-studio.md` —— 触发词、能力矩阵、实测命令、踩坑速记、
  合规口径、文档索引;SKILL.md 资源索引与 frontmatter 触发词同步接入。
- **资产**:成品样张 30 件 → `assets/map/samples/`;主题 JSON → `assets/map/themes/`;
  网点/路径 → `assets/map/`;播放器模板与产物 → `assets/map/demo/`;
  MapLibre GL v5.9.0(BSD-3)vendor → `assets/vendor/maplibre/`(渲染页零 CDN)。
- **运行期产物**统一落 `<技能根>/work/`(瓦片缓存 / OSM 底料 / 临时渲染页 / 源探测图),已进 .gitignore;
  历史留档 `docs/map/ITERATION.md`、`docs/map/adr/`、`docs/map/legacy-patches/` 也按仓库口径本地留档,
  调研与术语文档进仓库。
- **路由**:SKILL.md 资源索引新增 6 行 docs/ 路由(setup / gzh-guide / failures /
  gzh-spec-summary / svg-licenses / upstream-issues),消除"文档存在但无入口"。

### Fixed · 地图模块(并入时发现的真 bug,均已实测)
- **3D/SVG 截图硬编码 Chrome 路径** → 本机只有 Edge,原实现 `--executable_path` 指向不存在的文件,
  `render_3d` / `render_3d_vec` / `svg_preview` **必然启动失败**。改为
  `VB_BROWSER_PATH` > `_paths`(Chrome/Edge)> Playwright 自带 chromium 三级回退,实测 Edge 出图成功。
- **`mercator` 依赖 pip 包 eviltransform**(本机未装 → 任何 GCJ 转换必崩)→ 改本地实现,
  与 eviltransform 对拍 8 点最大偏差 1.1e-7 度(≈1cm),往返误差 0;`requirements.txt` 不再需要它。
- **临时渲染页写进仓库根**(`_render_3d.html` / `_render_3d_vec.html`)→ 移入 `work/tmp/`。
- **`__BLD_URL__` 用 `basename` 拼绝对 `/assets/`** → 换目录即 404;改为按技能根相对解析(`repo_url`)。
- **`--base`/`--theme`/`--points` 默认值指向已不存在的旧路径** → 全部改到新布局,并为缺图层/缺建筑
  文件加**可读前置报错**(原来只有 MapLibre 控制台 404)。
- `build_player.py` 的 SVG 尺寸替换写死 `width="1600" height="1917"`(换 bbox 后**静默不改**)→
  改为按属性正则替换;`test_v7.py` 补 argparse(`--help` 不再触发整轮验收)+ `--no-shots`;
  `probe_tiles.py` 补 argparse/`__main__` 防护(原先 import 即联网探测)。
- `map_tiles.py` / `fetch_osm_data.py` 的 `json.dump(open(...))` 句柄泄漏、`fetch_osm_data --out` 深层目录
  不存在即崩、调色板瓦片触发 Pillow 警告 → 一并修。
- **3D 渲染瓦片留洞**(俯仰相机视野超出预缓存窗口,MapLibre 静默 404 留洞)→ 本地服务改
  **按需补抓**缺失瓦片(落同一缓存,同视角可离线复跑),并修并发下的 accept 队列溢出
  (`request_queue_size 5→128`,实测并发补抓时浏览器报 `ERR_CONNECTION_REFUSED`);
  render 页面的 `/favicon.ico` 一律空响应,不再污染 `CONSOLE ERRORS`。
- 播放器验收回归:`build_player` → `test_v7.py` **V1-V12 全绿**(与并入前产物逐字节一致,仅构建时间戳不同)。

### Fixed · 全库审计缺陷(18 项脚本 + 23 项文档,节选 P0/P1)
- **P0** `imageops stitch` 必抛 `NameError`(`_img_compose.py` 缺 PIL `Image` import)→ 顶部统一导入;
  同函数 `args.out` 是 str 却调 `write_bytes` 的第二处缺陷一并修。
- **P0** `imageops convert --colors` 引用的 `_quantize` 全库未定义(选项从未实现却被登记进 `--help`)→ 实现。
- **P1** `export_fallback.py` 把视口**高度设成宽度**(1080×1440 封面默认导出成 1080×1080)→ 修;
  `pack.py` 资源引用少一层 `../`(打包产物 HTML 引用全失效)→ 按文件深度重算;
  `scaffold.py` 生成的 `.poster` 丢 `height`(自家 doctor 立刻判 degraded)与 `slug` 未消毒(可逃出 studio);
  `doctor.py` 缺分量时整条跳过(漏报)、`check_svg.py` 三处(第 13 条路径起静默免检 / fill-only 假阳性 /
  坏 viewBox 崩溃并中断整批)、`fetch_font.py` 多文件清单只下第一个却报 OK、
  `fetch_asset.py` 恒 `ok:true` + `--theme` 可逃出 studio、`qr.py` 绕过唯一代理出口、
  `_config.py` 非字符串配置被静默丢弃 + 带 BOM 的 config.json 全盘失效、
  `cutout.py --prefetch` 缺 `import subprocess`、`pixel.py` blend 尺寸不同即崩 + `--list-modes` 不可用 +
  三条失败路径无 JSON 信封、`gen_script_index.py --help` 会**真重写**生成物、
  `check_h5.py` 触摸目标检查是不可达死分支、5 个脚本 stdout 按 GBK 编码(中文 JSON 变乱码)、
  `calc_size/beat_sheet/inspect_ref` 5 处输入校验缺位(裸 traceback)。
- **文档**:`export.md`/`pipeline.md` 的 `export_fallback -o`、`doctor.py` 缺位置参数、
  `export_local.py --help`、`materials.md` 缺 `--theme` 等"照抄即失败"的示例;`gzh-guide.md` 主题口径
  (4 套旧名 → 6 套 `ink/night/warm/grass/red/mono`,真相源指向 `_gzh_theme.py`);
  `glossary.md` 把已退役矢量流水线当现行(SSIM → `ai_fidelity --min-score 97`);
  `setup.md` 正文里的 BEL 控制字符 + 工作目录口径分裂;裸 `WPI` 退役残留 8 处。

### Fixed · 静态导出求值点(实测推翻旧文档)
- 实测(2026-10-07,Kiln 浏览器车道,`export.py`):**静态导出把有限动画快进到终态**
  (红→蓝 2s `forwards` → 出图纯蓝;带 1s 延迟同样到终态),**不是** `export.md` 曾写的 "t=0 首帧";
  **无限循环动画**不报错但出的图相位**不确定**(2s 周期三次独立导出实测 ≈0.43/0.45/0.55s 相位)。
- **GIF/MP4 的捕获起点也不是 0s**:帧数确实 = `fps × --max-wait`,但内容对齐被前移
  —— 200–400px 页面实测 ≈0.9–1.0s,1080×1920 实测 **≈1.0–1.25s**(渐变探针 R 通道逐帧反推,
  两条独立动画互校);动画结束后余帧冻结在终态。故"前置静置 ≥2.0s"仍是硬规则,
  且 ≤15s 只是设计预算(`--max-wait` 可超,不是引擎上限)。
- 据此修正 `export.md` / `animation.md` / `glossary.md` / `pipeline.md` / `effects.md` /
  `video-motion.md`,并把模式 P 的规则改为:"静态版要确定性就用**有限版本**(终态必须仍是合格海报);
  确要无限循环则必须另出有限静态图,或保证任意相位都合格"(SKILL.md 铁律 6 同步)。
- **新登记上游缺陷 UP-3(Kiln GIF 车道 `steps()` 错帧)**:`steps(1,end)` 硬跳变动画在 GIF 输出里
  要么全程停在 `from` 色、要么落到无关颜色;**同页同参数 MP4 正确**(已用 ffmpeg 独立解码 +
  MP4 对照排除读取误差,详见 `docs/upstream-issues.md`)。绕行:卡点用连续时序函数或改出 MP4。

### Changed · 自检门禁补盲区(`scripts/selfcheck.py`)
- `refs`:支持 `../` 相对引用(按文件所在目录解析)——历史上 `references/styles/*.md` 的
  `../../fonts/…` 一类错误**结构性地查不到**;新增项目级投放脚本豁免(`导出.py`)。
- `route`:覆盖范围从 `references/**` 扩到 `docs/*.md`,路由数 54 → 64(暴露并补上 6 个无入口文档)。
- `stale`:从"仅 references/ 一层 + 6 个精确键"改为递归 `references/**` + `docs/*.md` 且**含裸 `wpi`**,
  带"WPI 时代概念,v1.9 起消亡"注记的历史行仍豁免。
- `cfg`:新增 `EXTERNAL_KEYS` 豁免表(在 `scripts/` 之外被消费的键),消掉长期 WARN;
  `bridge_port: 0`(= 随机端口)的判定改按整数 >0,不再被 `str()` 口径误成"固定端口 0"。
- `smoke`:`gen_script_index.py` 改用 `--check`(原 `--help` 会写盘,自检自称"只读"却弄脏工作区);
  `jsonfail` 用例新增 pixel/imageops 的 4 条失败路径。
- `--help` 契约补全:`preflight` / `junction` / `fetch_model` / `config_gui` / `export_local` /
  `gen_script_index` 现在都秒回用法(此前分别表现为:跑整轮预检 / 零输出 / 报未知模块 /
  **弹 Tk 窗口挂死** / 报 `[X]` 退出 2 / 静默重写生成物)。
- 统一 stdout+stderr UTF-8 样板到全部脚本(原先 5 个脚本管道输出为 GBK,中文 JSON 消费方报
  `UnicodeDecodeError`)。

### Fixed · 收尾轮(接上轮中断点)
- **`imageops stitch`/`montage` 输入缺失或损坏仍裸 traceback**(破坏"失败路径末行必为 JSON"
  契约)→ 新增 `_img_compose._load_inputs`,缺失/读失败统一回 `INPUT_NOT_FOUND` / `READ_FAILED`
  信封;`jsonfail` 门禁新增该用例。
- **`gen_script_index.py` 生成物"用途"列吐源码碎片**(`import argparse` / `last = ""`):
  `docstring_purpose` 从正则改 **ast**(正则对 `r"""` 前缀与 >4000 字窗口两个真实形态失手);
  生成器补**二轮收敛**(`docs/scripts.md` 自身参与提及扫描,首轮写盘后立刻 `--check` 必报过期);
  表头注记"少数无 argparse 的脚本打印模块说明"。
- **`fetch_font.py --help` / `export_local.py --help` 契约补全**(前者把 `--help` 当字体目录名报
  "清单中无此目录";后者用法文本在管道下是 GBK 字节)。
- `animation.md` 两处裸 `WPI` 补退役注记;`docs/map/` 四份调研/术语文档的并入前旧路径
  (`tools/` `demo/` `assets/*.png` `tiles/cache/` …)全部改到新布局,并删去两处已不存在的样张引用
  (改注明"可由命令重跑")。
- 自检门禁:`refs` 覆盖 `docs/map/*.md`(925 处引用);`docs/map/ITERATION.md`、`docs/map/adr/`、
  `docs/map/legacy-patches/` 按过程文档豁免(与 `.gitignore` 同口径);`jsonfail` 新增
  `doctor --json` / `gzh_cover merge` 两条用例。
- `doctor.py --fix-meta --json` 的 `[OK] 已回写 N 个` 人类行改走 stderr(此前污染 stdout 的
  单行 JSON 契约),`fixed` 计数进 JSON;`gzh_cover.py` 的 `merge` 帮助文案与模块 docstring 改口
  —— 合并图走 `kiln img stitch`(**需要 Kiln**),原写"Pillow 拼接 / 不需要引擎"与实现不符;
  拼接成功但 kiln JSON 解析失败时回读产物用 PIL 取尺寸(`ok:true` 必有 width/height)。

### Verified
- 地图链路端到端实测:平面 PNG(900×600,z13,AMap 瓦片 + 4 网点 + 版权条)、
  OSM 五层抓取(523 建筑 / 270 道路 / 17 轨道 / 13 绿地 / 1 水系)、`svg_map --theme all` 四主题、
  `svg_iso` 等轴测、`render_3d` 与 `render_3d_vec`(Edge,3840×2160)、`svg_preview`、
  `compute_route`(1316 节点 / 82→26 点简化 / 1457m)、`probe_tiles`、`build_player` + `test_v7` V1-V12 全绿。
- 审计缺陷逐条复现对照(修前现象 → 修后现象),证据见各修复报告;
  自检:`refs / route / stale / cfg / smoke / jsonfail / deploy / materials / golden / scriptdocs` 全绿。
- 仓库自检 `scripts/selfcheck.py` 最终结果见提交说明(FAIL 0)。

## v1.17.0 — 代理开关 + 素材站扩展(2026-09-27)

### Fixed · 代理模型(用户实测痛点:残留死代理致首轮下载必败)
- 新增 `proxy_enabled`(默认 **关**)+ `_config.proxy_active()` 代理唯一出口
  (ENV `ARTBOARD_PROXY_ENABLED`);消费者全量改造:fetch_font / _download / fetch_asset
  (pinterest + curl 兜底)/ mcp sources;preflight 新增代理状态报告;config_gui 提示同步

### Added · 素材站扩展(hunt 多站编排)
- **vector4free**:免费矢量(S3 预览图,页内 fetch 下载;授权逐条各异→前缀)
- **svgrepo**:30 万 SVG(Cloudflare 盾→**Bridge 页内 fetch**;多数 CC0→前缀)
- **gahag**:日系照片/矢量,**明示 Public Domain**;原图 URL 从缩略图直接推导
  (img01.gahag.net/<ym>/<N>o/,已验证 3.1MB 原图)+ Referer 防盗链;日文关键词命中更高
- Bridge 协议新增 `fetchfile`(SW fetch 优先→页内 fetch 兜底,≤8MB);sources.download
  支持 content_b64;站点级 license/risk 进 SITES 注册表(materials.md §1 同步)

### Changed · 引擎发行
- Kiln 发行页升级 **v0.10.0**(重构 release 后真机构建,SHA-256 6f714f2d…):
  VB-1 静态服务目录联接 404 根修(artboard UP-1 关闭,瘦身影子下 webfont 恢复,
  不再需要 --embed-fonts 绕行)+ VB-2 native/矢量道静默丢弃改降级可观测(UP-2 关闭)
  + warnings_by_kind / anim_coverage / SVG 导入跳过清单强类型化;
  setup_kiln.py 默认地址与 README 徽章已同步

### Verified
- 代理开关双态单测(关=直连 None / 开=带代理);离线全协议两遍全过
  (降级阶梯/strict/全收+查重/cookie/兜底+关页/svgrepo page_fetch/gahag 直下无前缀)

## v1.16.0 — Bridge 全自动素材搜索(2026-09-27)

> 依据桌面《artboard-Bridge素材搜索迭代-20260927》;grilling 九问收敛(D1–D10)。

### Added
- `scripts/asset_hunt.py`:一条命令全自动素材搜索——多站编排(花瓣/SVGRepo/Pexels·Pixabay API)
  → 花瓣 DOM 自动化勾「素材范围=不看素材」(来源侧规避水印)→ 下载+原图升级(剥后缀→详情页兜底)
  → 筛选(透明 PNG/横竖图/主色距离,默认降级留痕,--strict 严格)→ pHash 查重 → 关闭本轮标签页
  → 单行 JSON 报告
- **专用素材浏览器**:独立 profile(持久登录)+ 首次可见绑定/日常 --headless=new 后台(混合,不抢用户浏览器);
  狩猎 hub 固定端口 8811 + **固定长效 token**(config bridge_hunt_token)→ 扩展凭据一次填好永久有效 = 登录常态化
- Bridge 协议 v3:`open`(后台标签+等待+DOM 自动化)/`close_tab`/`cookie` 三命令;扩展 v2.1.0(manifest +tabs)
- MCP 第 6 tool `assets_cookie`:**Cookie 自动抓取并合并写 config.json**(取代手动复制粘贴;
  Cookie 仅 localhost 传输、只落本机)

### Removed
- `tools/cookie-extension/` 删除(asset-bridge 全面替代);全库引用改口(README/setup/materials/fetch_asset/config_gui)

### Verified
- 离线全协议 5/5:降级阶梯/严格空手 exit 1/全收+查重/Cookie 写入/详情页兜底+关页(WS 替身+本地图床)
- 真机(用户浏览器):白名单拦截/采集/下载/前缀/CREDITS 全链通;MV3 SW 休眠→alarms 自愈实测

## v1.15.0 — 迭代计划 v2:料 · 动 · 确定性(2026-09-26)

> 落地《artboard-迭代计划-v2-20260925》00–11 全部阶段;决策台账见 `docs/adr/0027`(本地)。

### Added · 能力面(按诉求)
- **开工确定性(04)**:铁律 8 升级 Brief Gate(9 字段三态标注/缺项强制补齐/「直接做」须假设确认);
  `check_brief.py` 机检;intake/pipeline/SKILL 三处口径同步
- **配图判定与取图通道(03)**:materials §0 判定表(写 image_plan,主动取图);
  `mcp/artboard-mcp` 五 tool(stdio JSON-RPC,零 SDK;plan/search/fetch_page/download/dedupe);
  `tools/asset-bridge`(MV3,localhost WS + token + 白名单 + 显式授权);config 新键 mcp_enabled/bridge_port/bridge_token_ttl
- **视频动效体系(02)**:`video-motion.md` 模式 V(五类件×时长契约/五类视频矩阵/7 式语法/分镜表/卡点表);
  `beat_sheet.py`;5 案例全机检 + MP4 导出 + 抽帧三点验证;画幅扩展 1:1/4:5/2.35:1(文档+机检同步)
- **SVG/插画(05)**:`fetch_svg.py`(Iconify,逐集许可白名单 + docs/svg-licenses.md 238 集)+
  `check_svg.py`(9 项);图标 63→648 枚(24px 并排校验无异类);vector-drawing §4.7 rubric / §4.8 两路线决策树
- **位图配方引擎(09)**:`pixel.py` + `_px_*` 5 模块:18 调整 + 12 滤镜 + 25 混合模式 + 蒙版 DSL;
  recipe save/validate/run/batch(乱序报错);`pixel deps` 能力矩阵(缺依赖报错不静默);
  公共配方库 `assets/recipes/` 6 套;`pixel-pipeline.md`
- **H5 交互页(10)**:模式 H(`h5-interactive.md`,H5 铁律 7 条,不适用铁律 1;MDN/WCAG/CWV 口径,
  不采纳 user-scalable=no);`check_h5.py` 8 项机检;2 案例 + 3 坏样例
- **图文⇒封面单向绑定(11)**:`_gzh_theme.py` 统一主题源(6 套,消灭 green 同名不同色);
  `gzh_article convert --with-cover` 默认出同主题三封面(--no-cover 逃生口);一致性机检 `check --theme-consistency`

### Added · 工程与台账(06/08)
- `imageops dedupe`(pHash 查重)、`check_credits.py`(版权对账)
- `docs/upstream-issues.md`(UP-1/UP-2 登记带绕行);failures 复查留痕(8 条全已修)
- selfcheck 增 `materials`(声明 vs 磁盘)/`golden`(回归基线)/`scriptdocs`(脚本可达)三门禁 → PASS 9→12
- 脚本文档架构(08):SKILL 脚本块瘦身为主线 5 条;29 册新增「本册用到的脚本」;
  `registry.json` + `docs/scripts.md` 生成物(gen_script_index.py);README 清单改指针
- 公共配方库 `assets/recipes/` 6 套;`assets/recipes` 与新增产物合计 +9.7MB(≤30MB 预算)

### Fixed · 文档说谎与口径
- materials「插画三套全 CC0」→ 按磁盘真实状态改写(仅 open-doodles 落地,其余标获取方式)
- `green` 主题同名不同色隐患消除(统一主题源 + 迁移说明)

### Upstream(只登记,不改上游)
- UP-1 浏览道字体联接 canonicalize 判越界(绕行 --embed-fonts);UP-2 native 道伪3D 静默降级(绕行 --engine auto)

## v1.14.0 — 合并「模式 W」公众号图文分支 + 联网核对白名单口径(2026-09-22)

来自外部交付的 `artboard-modeW` 增量包(基线 1.7.6)正式并入主线。安装器对 1.13.0 干跑校验:
4 个新文件 sha256 一致、机检夹具双绿(bad.html→1 / good.html→0);两处旧锚点因 1.13.0 重写
而失配,改为按现结构手工注入(SKILL.md 定位段/分册索引/脚本清单 + README 脚本一览)。
CHANGELOG 不回填包内过时的 v1.8.x 条目,以本条目替代。

### Added · 模式 W(微信公众号图文)
- `references/wechat-article.md`:微信图文主分册(内联样式/内联 SVG+SMIL/静默降级/窄屏纪律/
  无目视验收四法/135 中转发布法/机检门禁)
- `scripts/check_wechat_svg.py`:微信 SVG 白名单/禁用标签/id/url(#)/被剥离 CSS/标签配平/
  animateTransform 覆盖陷阱机检(退出码 1 = 禁交)
- `scripts/check_mobile_width.py`:手机窄屏横向溢出机检(必须压到 320px 才可靠)
- `scripts/upload_imgchr.py`:图床直链上传(imgchr/Chevereto 内核,纯标准库)

### Added · 联网核对回填(zer0n 白名单原文 / doocs-md wechat-svg skill / Axton Liu 概览)
- 分册新增「白名单口径备注」:`r`/`cx`/`cy` 的规范与实测口径差、`stroke-dasharray` 待真机验证、
  `mpath` 避免使用、交互事件优先级与 **`begin="click"`+`fill="freeze"`+`restart="never"`** 统一纪律
- §三新增坑 9:`additive="sum"` 保留静态 transform + 中心缩放「施加→缩放→抵消」三连写法
- §八新增 8.4bis:**SVG 内图片 src 最终必须是 mmbiz 素材库链接**(外链/Base64 不显示)、
  剪贴板直贴与官方草稿 API 两条备份通道(动态 SMIL 存活率标注未实证)、静态 SVG 直贴三坑表、
  真机验收 4 格矩阵
- 文末新增 §十二 参考来源(含全部 URL 与「未实证留待自测」清单)
- SKILL.md / README.md 同步模式 W 分支说明、分册索引行与三条脚本命令

### Added · card-layout.md §4.6 flex 收缩陷阱
纵向 flex 容器里「定高 + overflow:hidden」的子项在内容总高超画布时会被压成 0 高
(`min-height:auto` 因非 visible overflow 解析为 0)——症状是色块条整条消失、机检报
双向对称越框。修法:定高块一律 `flex:none` + 内容总高预算 ≤ 画布高。
(源自 a3 数据分配条渲染消失的实战案例,playwright 计算样式确诊)

## v1.13.0 — 缺陷收口 + Kiln v0.9.0 + 仓库瘦身(2026-09-22)

### Fixed · imageops 六条「已探明未修」一次收口(docs/failures.md 台账回填)
- `card --shadow`:`_shadow_layer()` 解析即转数值(此前 `blur` 是字符串,
  `W + blur * 4` 必 `TypeError`),并新增 `BAD_SHADOW` 参数校验;
  顺带修好阴影位移——此前 `dx/dy` 被丢弃,阴影方向被裁
- `thumb`:dest 与消费端字段名不一致(`format_out` vs `args.format`)→ 统一,
  并补上此前被忽略的 `--out`
- `contrast-check`:numpy 标量进 `json.dumps` 不可序列化 → `_wcag_ratio()`
  入口/出口 `float()` 化,判定值 `bool()` 化
- `--in` 绝对路径 glob:`Path.glob` 不接受绝对模式 → 新增 `_glob()`
  拆「盘根 + 相对模式」;montage 的特例守卫随之删除
- `watermark` 单点九锚:坐标表按 anchor 码取值(此前拿位置名索引,必 `KeyError`);
  十种位置实测全通
- `tone/card --out`:字符串未包 `Path()` → 三处统一

### Fixed · 本轮新暴露
- `exif-fix`:把 `st_size`(int)塞给 `result_item()` 的字节形参 → 整条命令全失败
- **位置参数给目录**:直接当文件交给 PIL → `PermissionError`;现递归展开图片
  (默认扩展名白名单,可 `--ext` 收窄),空目录给 `INPUT_NOT_FOUND`
- `config_gui.py`:`scripts\setup_kiln.py` 的 `\s` 非法转义(SyntaxWarning)
- `export.py`:引擎 `warnings` 是**计数**,回填进字符串列表会在计数 >0 时
  `int + list` 抛 TypeError → 改转成一条可读告警

### Fixed · Kiln(v0.9.0,上游 VellumBench)
- **Edge 无头端点探测**:msedge 不往 stderr 打印 DevTools 行 → 浏览器车道在
  只有 Edge 的机器上必失败;改为 stderr 行 + `DevToolsActivePort` 文件双路轮询
- **降级可见**:浏览器车道失败落自研引擎时,结果 JSON 置 `engine_fallback:true`
  并置 `degraded` ——自研引擎对真实海报页是废图,不能再 `ok:true` 静默混过去
- **JSON 转义根修**:手拼 JSON 未转义 Windows 路径反斜杠 → 调用方
  `json.loads` 必失败、`width/height/engine` 永远取不到;新增 `jesc()` 统一转义
- `export --help` 补 `VB_BROWSER_PATH` / `PDFIUM_DLL` 说明

### Changed · 导出链路
- `export.py` 见 `engine_fallback` 且格式为 PNG/JPG 时**自动改走
  `export_fallback.py` 重出同一路径**(结果带 `auto_fallback_from`),
  `--no-auto-fallback` 可关;非光栅格式不自动转,但 warnings 明示降级
- `setup_kiln.py` 新增 `--force`(升级路径:此前 probe 命中即返回,
  `--from` 下载分支被短路,引擎永远升不上去);默认下载源升到 kiln-cli-v0.9.0;
  部署后打印引擎版本
- `scaffold.py --fonts` 接受**显示名**(思源宋体/得意黑/霞鹜文楷…),
  解析失败改为报错并列出可用目录——静默回退系统字体会让人以为选上了

### Changed · 机检
- `check_overflow.py` 传**目录**时逐页查所有 HTML(多页 PPT/三折页此前只查
  `index.html` 或 `sorted()[0]`,其余页面全漏检);输出新增 `files` 数组
- 新增 **D 类:元素互相重叠**(`--overlap`,默认关):A/B 只问「谁越出了谁」,
  两个各自安分的元素叠在一起谁都查不出来;`data-allow-overlap` 豁免

### Changed · 文档与仓库
- README 重写:极客简洁风。头图与流水线图改由 **artboard 自己做**(HTML +
  思源黑体 → Kiln 导出 PNG),不再依赖 SVG 的系统字体回退(此前中文落到宋体),
  并过机检保证零溢出;README 直接引用 `hero-preview.png` / `pipeline-preview.png`
- **样例重做**:上一版 5 张全是纯 CSS 硬撑、没有一张照片,质感不达标,已弃用。
  本版按版式分组、每组内尺寸严格一致,全部使用 Pexels 授权摄影 + 开源字体:
  - 小红书封面 1080×1440 ×4(保留「轻食研究所」)
  - A4 正反面 ×4(城市之声室内乐 / 城市设计周,各含正反两面)
  - 电影·广告海报 1080×1920 ×4(保留「开票的人」)
  - PPT 页 / KV 1920×1080 ×2
  - 数据长图 2400 宽 ×1(保留「城市咖啡图鉴」)
  素材经 `probe` 体检按清晰度挑选、`cover` 裁切(重心 0.42,防切掉主体),
  成图逐张像素采样验证照片确实渲染(而非图片路径失效却看不出来)
- 文档与脚本注释清理:散落在交付文档、`--help` 与代码注释里的迭代补丁代号
  (`X 修:`、`此前…`)全部改写成「讲清现状与理由」,历史沿革只留在 CHANGELOG

### Verified
- Kiln 双车道端到端:Edge 浏览器车道出图 ✓;强制浏览器失败 →
  `engine_fallback:true` → export.py 自动转 Playwright 兜底 ✓
- imageops 六条复现命令逐一复跑全过;`check_overflow.py` 目录逐页 + `--overlap`
  对造出来的 A/B/D 样张全检出 ✓;`selfcheck.py` FAIL 0

## v1.12.0 — 设计维度迭代:生成层/表达层/纵深/混排/改稿决策/多稿同出(2026-09-21)

> 依据《artboard-设计维度迭代文档-20260921》(00 主文档 + 9 份任务书)。本轮为**设计知识分册轮**:
> references 顶层分册 30→39(route 40→49)、案例 +10、术语 +43;脚本仅新增 `montage`,不动既有行为。

### Added · 九份新分册
- `revision-protocol.md` 改稿决策:模糊愿望→rubric 五维诊断;翻译表 13 条;减法阶梯 L1删–L5点;
  引导式提问;反驳公式;高级感清单 10 条(与反 AI 味防守清单分立)
- `depth-3d.md` 伪3D与空间感:统一光源 tokens + 四级高程;六手法;标题三配方;剪切蒙版造空间 4 写法;
  景深;**Kiln 双车道支持矩阵 7 项实测**(真3D=浏览器道可用/自研道静默丢失/矢量道全丢);体积增量 ≈23KB
- `typographic-expression.md` 排版表达:语气 4 种;尺度地板/天窗;节奏/张力;字体即图形;编辑母版 7 法;实验四问
- `vector-drawing.md` 矢量绘制:CSS vs SVG 判据;构成四法;图标 7 规范 + 24px 校验;
  矢量道几何边界实测(内联图标会栅格化)
- `image-language.md` 位图语言:图像角色 5 类;色调分级 5 法;裁切 5 式 4 红线;景深;主体分离;处理链①–⑥
- `design-thinking.md` 设计思维/生成层:四段翻译模型;主导动作 8 类;概念生成 5 法;卖点映射 10 组;
  反套路 8 类;复杂度预算;三方向
- `bilingual-typography.md` 中西文结合:关系四分;搭配矩阵 8 组;密度匹配三招;基线对齐;
  引号按风格分派;双语 vs 装饰小字一句判据
- `multi-draft.md` 多稿同出:**备选模式,默认单稿**,仅指令/用户要求触发;受控轴 4 维;联络表;
  转正/归档;计时实测 4 稿 = 单稿 ×1.27(≤ ×2 达标)
- `material-language.md` 材质语言:纸/金属/玻璃/布/木/塑料 → 配方总表

### Added · 脚本 / 案例 / 台账
- `imageops.py montage`(C5 网格拼图;--grid/--gap/--margin/--bg/--label;过 smoke/jsonfail)
- `assets/cases/` +10(全部机检 ok + rubric 自评 ≥3.5;**独立视觉裁决 9/9 pass,4.0–4.8**)
- `docs/failures.md` 失效案例库新建(6 条既有脚本缺陷"已探明未修",走 ITERATION 代码迭代环)
- `docs/glossary.md` +43 词条;`docs/adr/0019–0026`(本地)记录本轮八项决策
- `pipeline/SKILL/intake/guardrails/effects/title-fx` 等既有分册共 17 处指针接线(双向互指)

### Upstream 发现(未修,记录在案)
- Kiln 浏览道对 `src/fonts` 目录联接 canonicalize 判越界 → webfont 静默回退系统字体
  (绕行 `scaffold --embed-fonts`;根修在上游 staticsrv)
- Kiln 自研道(native)对伪3D 原语静默降级无告警(上游告警通道建议)

## v1.11.0 — 位图工序族 + Kiln v0.8.0(2026-09-20)

### Added · 位图工序唯一入口(依据《artboard-位图脚本库扩充-迭代指导书》批次一+批次二核心)
- `scripts/imageops.py` + `_img_core/_img_geom/_img_encode/_img_compose/_img_probe`:
  30 子命令 + `pipeline` 链式(单次读单次写),覆盖几何/编码/派生切片/合成/检测/工程六类
- 统一契约:单行 JSON 信封(失败路径也吐 JSON)/ 退出码 0·1·2·3 / `--profile` 质量
  档位唯一真源 / 尺寸只读 `scaffold.SIZES` / 依赖编码器级探测(deps)/ 版权前缀守卫
- `references/imaging.md`:位图工作分册(与 materials.md 分工:来源 vs 加工)
- `SKILL.md`:版本对齐 1.11.0;资源索引登记成像分册;Step 4.5 补 `probe`;脚本小节补 imageops
- `README.md`:位图工序段 + 内部助手登记;`requirements.txt` 补注释登记 rembg/qrcode/zxing-cpp
- `selfcheck.py`:JSONFAIL_CASES 增 imageops 三用例;9 项检查全绿

### Fixed · review 修复
- `cutout.py --prefetch`:pooch 走 GitHub SSL 失败时自动改 curl 直拉 release .onnx
  (此前 materials.md 记录了绕行方案但脚本未采纳)
- SKILL.md frontmatter 版本 1.9.0 与 CHANGELOG 脱节的口径分裂收口

### Upstream · Kiln v0.8.0(kiln-cli-v0.8.0 发行资产)
- ADR-0022 导出路线按格式分化(PNG 回浏览器原生截屏,消融验证 G1 99.82)
- 导出副产物出源目录(K4);动画简写 var/calc 时序解析修复(5 卡单帧)
- **animlane 车道 B 动画逐帧**(WPI 理论):GIF/MP4 主路改真浏览器实时采样,
  人工评分 35 → 99.4(21s/卡)
- AI 可编辑三轮(21 篇):G6 浏览器真值门禁 / 分段样式逐段整形 / 矢量渐变
  Pattern / 圆角控制点公式修复 / border 颜色 longhand / svg 矢量导入(近似路径守卫)


## v1.10.1 — 技能侧契约收口 + AI 可编辑交付验证(2026-09-19)

### Fixed · 脚本缺陷(指导书《Kiln-迭代指导书.md》§7.3 补丁 A/B/C/D/E/F/G/H/I/K/L/M 全量落地)
- **A** `preflight.py`:删除未定义变量 `wpi` 引用(特定环境下整个预检
  NameError 崩溃);ffmpeg 探测统一 `ARTBOARD_FFMPEG`(`WPI_FFMPEG` 兼容旧环境)
- **B** `export.py`:解析引擎 stdout 单行 JSON,回填真实
  `width/height/frames/engine` —— 此前恒为 `null`,`gzh_cover` 打印
  `NonexNone` 即此因(已端到端实测:JSON 返回 `width:1240, height:1754`)
- **C** `export.py`:`--height` 此前仅解析、从不透传,现按>0 条件透传
- **D**(行为变更)`export.py`:`--width` 默认 `1080`→`0`(Kiln 按画板几何
  自适应);非 1080 画幅(banner 1920 / kv 1920 / rollup 2362)必须显式传,
  否则按 1080 视口渲染;`references/export.md` 同步(「保留但无效」说法删除)
- **E** `ai_export.py`:相似度门禁不达标时进程退出码改 1(此前恒 0,脚本链无法拦截)
- **F** `ai_export.py`:ai_fidelity 校验补 `timeout=300`(pypdfium2 卡死不再无限挂起)
- **G** `preflight.py`:`VellumBench\dist\...` 非法转义路径改 `os.path.join`
- **H** `export_local.py` / `setup_kiln.py`:超时与执行失败分报,不再宽
  `except Exception` 静默「跳过」
- **I** `junction.py`:PowerShell stderr 解码改 UTF-8 优先、GBK 兜底
- **K** 依赖与文档漂移:`requirements.txt` 补 `pypdfium2`(ai_fidelity 依赖);
  SKILL.md / docs/setup.md 删除不存在的 `requirements-vector.txt` 引用;
  CHANGELOG 删除不存在的 `kiln_import.py` 声明
- **L** `export.py`:降级告警协议统一(`vb_layout:` 与 DOM 路线 `domwarn`
  双前缀都认,引擎 `degraded_artboard` 字段优先)
- **M** `find_kiln()`(export.py / ai_export.py 同构):增加**能力探测**
  (`--engine/--height/--vector` 参数面),优先 dev 构建 —— 此前默认选中
  参数面滞后的 dist 旧二进制,是「技能传了新参数却一切静默」的根因

### Verified · AI 可编辑交付(引擎侧 VellumBench ADR-0022 批次)
- 7 项 AI 打开体验问题闭环:未知阴影/图像结构报错(零 Shading/零 Type3)、
  剪切蒙版泛滥(新导出 W n=0)、逐字断字(整行 CID Tj)、强制转曲
  (pdfium 文本抽取 delta=0,含中秋案例)、双图层(背景/内容 OCG)、
  多画板(双 `--source` → 单 .ai 双页)、PNG 保真主路恢复(G1 99.82)
- 交付链同步:本地 `dist/Kiln-noGUI-CLI.exe` 已更新到当前源码构建
- AI 文件边界(PGF 私有数据无公开规范故不含、拉丁 base-14 未嵌入)不变,
  详见 VellumBench `docs/ai-editability-checklist.md`

## v1.10.0 — Kiln v0.7.0 双车道保真导出(2026-09-19)

### Changed · 引擎升级(kiln-cli-v0.7.0 发行资产,上游 VellumBench design/19 + ADR-0020)
- **双车道导出**:`kiln-cli --engine auto|browser|native`(auto 默认)。浏览器车道由
  Kiln 内建 Rust 原生 CDP 驱动系统 Edge/Chrome(headless):PNG=整页截图
  (WPI 捕获协议十要素移植)、PDF/AI=printToPDF(screen 媒体+精确纸张);
  浏览器缺席自动降级自研引擎并在 JSON 结果 `warnings` 告警
- **导出参数**:`export` 新增 `--engine` 与 `--height`(高度锁定,WPI 兼容);
  JSON 结果新增 `engine` / `browser` 字段;`selfcheck` 新增浏览器探活
- **保真度口径修正**:v1.9.x 宣传的 98.63 系自洽对拍分(无浏览器真值);
  v0.7.0 起验收以系统浏览器渲染为基线,6 类 26 案例机器门禁:
  G1 PNG 对拍平均 **99.93**(最差 99.65)、G2/G3 PDF/AI 平均 **99.37**、
  G5 字体 100% 嵌入(报告随 VellumBench `bench/acceptance/` 开源)

### 注意
- 浏览器车道需系统 Edge/Chrome(免费);无浏览器环境自动降级车道 K(自研引擎,
  保真分下降并在结果中声明)。可用环境变量 `VB_BROWSER_PATH` 指定浏览器路径
- AI 文件 = PDF 兼容流 + AI9 头(Illustrator 可开/文字可改/矢量保留;
  PGF 私有数据无公开规范故不含),边界详见 VellumBench `docs/ai-editability-checklist.md`

## v1.9.1 — Kiln v0.6.0:PDF 保真度全绿 + SVG 导入(2026-09-18)

### Changed · 引擎升级(kiln-cli-v0.6.0 发行资产,上游 VellumBench main 968be94)
- **PDF 保真度全绿**:22 案例全语料「可编辑 PDF→PDFium 栅格化 vs
  HTML→Kiln 原生渲染」全像素平均 **98.63/100**(达标线 97),文本一致率
  100%,0 案例 <90;验收脚本 `VellumBench/bench/pdf_fidelity.py` 开源可复跑
- **渐变实现换血**:pdfium 不渲染 PDF shading(实测),线性/径向渐变按
  CPU 栅格同款数学降采样为位图嵌入 + SMask 半透明——任意渲染器结果一致;
  rgba 色标渐变修复(括号感知切分/四通道插值/SMask 独立编号),此前
  rgba 渐变蒙版被静默丢弃
- **透明度修复**:实心/描边/文本 = 项透明度 × 颜色 alpha 分部发
  ExtGState(此前 rgba alpha 被丢弃,玻璃卡片变不透明白块)
- **旋转统一**:q+cm 仅旋转项单层包裹(此前文本 Tm 手工旋转与图像块二次旋转)

### Added · SVG 导入(纯 Rust,零外部依赖)
- `kiln-cli import --source x.svg`:usvg 解析,矩形/圆角矩形(半径反推)/
  圆/椭圆/真实文本(不转曲)/嵌入位图逐对象映射;
  自由曲线 v1 包围盒近似 + 警告;PDF/AI 导入不变(需 pdfium.dll)
- setup_kiln.py 默认下载源升级 kiln-cli-v0.6.0;vector-export.md、README 同步

### Fixed · 外部部署报告六项(v1.9.1 实测反馈)
- **P0 export_local.py NameError**:WPI→Kiln 重构漏改,投放的「导出.py」
  调用未定义的 find_kiln()——补齐定义(环境变量→config→向上 8 级找
  VellumBench/dist|target),清掉 find_wpi 残留;selfcheck 新增 deploy 门禁
  (AST 名称解析 + WPI 残留扫描),import 级冒烟拦不住这类 P0
- **P1 存量项目重跑失真**:CSS Grid 落地(taffy grid,grid-template-columns/
  rows 的 fr/px/%/repeat + gap;模板不可解析降级块布局并告警,不再静默塌
  单列);合成画板包围盒尊重 overflow:hidden 裁剪(.poster 显式尺寸成为
  画布真值,250px 溢出不再把 A4 撑成 2004 高);Kiln JSON 新增
  degraded_artboard 字段,export.py 解析 Kiln stderr 布局告警透传 warnings
- **P2 references/export.md 仍是 WPI 时代内容**:重写为 Kiln 三级
  (Kiln→export_fallback→报错)+ 新增「画板合成规则」章节;
  selfcheck 新增 stale 门禁(已退役 WPI 键不得出现在正文,退役注记豁免)
- **P2 setup_kiln.py 死代理卡部署**:_download 代理先 TCP 探活,不可达
  warn 后自动直连;报错区分「代理进程未运行 / 未配置代理 / 直连被拒」;
  setup_kiln.py 新增 --exe 参数与 artboard-tools 探测候选
- **P3 project.json 元数据漂移**:新增 scripts/doctor.py——扫 studio 目录,
  核对 skill_dir 有效性、.poster 真值 vs project.json 尺寸、scale 缺键;
  --fix-meta 按 .poster 真值回写 width/height

## v1.9.0 — Kiln 引擎全面换血(WPI 退役)

### Changed · 渲染引擎整体替换(v1.9 主线)
- **Kiln 原生引擎上位**:导出走 VellumBench Kiln 单文件(九格式
  PNG/JPG/GIF/MP4/SVG/PDF/EPS/AI/PPTX),零浏览器/Python 依赖,
  速度 1.9×–48×;三级引擎简化为 Kiln → export_fallback.py(PNG 兜底)
- **WPI 全量退役**:删除 wpi_path/wpi_cli_exe/ARTBOARD_WPI、
  setup_wpi.py、WPI_FFMPEG 私有约定;WPI_NOT_FOUND → KILN_NOT_FOUND
- **配置收敛**:kiln_cli_exe 单键 + ARTBOARD_KILN_CLI + near_workspace
  自动探测(VellumBench/dist);setup_wpi.py → setup_kiln.py

### Added · Kiln v0.5 能力(上游 VellumBench,tag v0.5.0-kiln)
- **文档流布局引擎**(taffy):flow/flex/absolute/inset/margin/padding/
  gap;后代链选择器;var()/calc() 求值;font 简写展开;@font-face 注册表
- **文本引擎**:`<br>`/`
` 真断行、共享贪心断行(禁则逐字策略)、
  行高/字距/对齐、行内富文本段(span 颜色/粗斜体)、五写出器全部多行化
- **CSS 动画时间轴**:@keyframes 逐帧求值(@keyframes/animation 简写/
  cubic-bezier/fill-mode/alternate),transform+opacity 全量,
  clip-path(inset/circle/ellipse)+ filter(blur/brightness/saturate);
  五段式场景卡 GIF/MP4 原生直出(不再依赖浏览器录制)
- **PDF 中文真文本**:CIDFontType2/Identity-H 子集嵌入 + ToUnicode,
  中文可选中可复制;SVG/PPTX 真文本;AI(PDF 兼容流)
- **PDF/AI 导入**:`kiln-cli import --source x.pdf --output <dir>` →
  规范化 HTML(替代 VectorEdit2WebHtml 的外部矢量稿改造通道)

### Changed · 矢量交付与逆向
- 矢量交付改 Kiln 直出(to_vector.py/ai_export.py 重写为 Kiln 薄壳);
  删除 webhtml2vectoredit.py / text_run_merger.py / vectoredit2webhtml.py /
  setup_vector.py / requirements-vector.txt(poppler/gs/pikepdf 链退役)

### Removed
- WPI 全链(源码 API/CLI 调用/部署脚本/错误码/文档)
- poppler + Ghostscript + pikepdf + scikit-image 依赖链

### 已知边界
- 动画 clip-path 仅 inset/circle/ellipse;@property 数字滚动静态化
- L3 滤镜(blur/brightness/saturate)仅 CPU 栅格路径(SVG/PDF 矢量输出不含)
- kiln import 的 PDF 取色未暴露(v1 统一近似色);SVG 导入后续版

## v1.8.0 — 微信公众号双封面 + 内容排版

### Added · 公众号双封面(gzh_cover.py)
- **双封面一次生成**:`new` 产出主封面 900×383(2.35:1 头条)+ 次条 383×383(1:1),
  共用同一套主题 tokens(blue/dark/warm/green 四套)与字体,信息流里"同一个栏目"
- **三种导出路径**:`export` 默认三图齐出(合一导出);`--only main|sub|merged` 单出任意一张;
  `merge` 仅重拼合并图(Pillow 纯像素拼接,不重渲染,单张原始比例零形变)
- **居中安全区版式**:转发卡片只露中央 383×383 → 主封面关键信息全部居中;
  次条元素 ≤3 居中堆叠(规格依据 docs/gzh-spec-summary.md,多源交叉验证)
- 产物命名 `cover-main/sub/merged-<slug>.png`,可直接上传公众号后台

### Added · 公众号正文排版(gzh_article.py)
- **Markdown → 全内联样式 HTML**:零依赖解析(标题/引用/列表/表格/代码块/分割线/图片),
  每个元素 style 内联,无 class/id/`<style>`/`<script>`/外链 CSS——粘贴进公众号编辑器不塌样式
- **四套主题**(default=微信蓝/green/orange/red)+ 本地预览页(`--preview`,手机宽度壳)
- **兼容性自检**:`check` 子命令输出违规报告(禁用模式/白名单外标签/缺内联样式标签);
  `demo` 一键生成全组件示例并自检

### Added · 规范文档
- `references/formats/gzh-cover.md`:双封面品类分册(尺寸/安全区/合并图规范/字号阶/禁则)
- `references/gzh-typography.md`:公众号排版分册(兼容性硬规则/组件样式表/阅读节奏)
- `docs/gzh-spec-summary.md`:权威资料归纳(封面规格与排版约束的来源清单 + 决策映射)
- `docs/gzh-guide.md`:使用指南(上手/规格/导出方式/异常处理/回滚)

### Fixed · 导出健壮性
- `export.py` 同目录导入在 Python safe_path 环境(≥3.11 PYTHONSAFEPATH / 3.13+ 默认)下
  不再 `ModuleNotFoundError`(补 sys.path 守卫,同 preflight.py 先例)


## v1.7.6 — 机检纳入 Step 6 门禁 + 安全区三档降级

### Added · 机检门禁(ADR-0017 决策一)
- **`check_overflow.py` 接进流水线 Step 6**,拆为 **6.0 机检门禁** + **6.1 看图自检**,
  并写明两者区别:机检是**每次重导前必跑**的门禁(3–5s、**零 token**),
  自检是 Agent 的 Read 看图评审(仍只在铁律 5 的两个时机)。
  改稿阶段省自检但不能省机检——**改文案/字号/间距正是溢出最常见的成因**
- `SKILL.md` 铁律 5 补「机检 `check_overflow.py` 不受此限」,防误读为"改稿不能跑检查"
- `guardrails.md §9` / `animation.md §十三` / `card-layout.md §七` 同步补机检命令

### Added · 安全区三档(ADR-0017 决策二)
- `check_overflow.py` 新增 **C 类检测(内容越出安全区)** 与三个参数:
  `--safe-area 9x16|16x9|3x4|auto`、`--safe-tier standard|tight|extreme`、
  `--safe-inset`(任意 px / 百分比)
- **三档数值**(9:16,代码与文档单点一致):

  | 档 | 四边保留 | 可用区 | 代价 |
  |---|---|---|---|
  | 标准(默认) | 顶 230 / 底 576 / 左右 184 | 712×1114 | 无 |
  | 紧凑 | 顶 134 / 底 480 / **左右仍 184** | **712×1306** | 通吃性下降 |
  | 极限 | 四边 **2.5%** | **1026×1824** | 字幕/按钮会盖住边缘内容 |

  - **紧凑档左右不动**:9:16 右侧平台按钮列是 180px 硬约束,压不下去;
    只放宽垂直(顶 12%→7%、底 30%→25%)—— 比"四边等比缩"更符合物理事实
  - **极限档**由用户直接确立(极端情况只留 2%–3%);配四条纪律:
    先试精简/拆卡 → 关键信息不下放(主标/CTA 仍留紧凑档内)→ 必须声明代价 →
    收到"被盖"反馈先退回上一级
- 安全区矩形**由页面渲染后的实际几何换算**(百分比在 JS 侧按对应边算),
  不用传入的 `--width/--height` —— 长图 h 未知、画布也可能不是传入值;
  C 类只报**最外层**越界元素(父子不重复刷屏)
- `references/video-safe-area.md`:§二 重写为三档结构 + 降级纪律 + 机检用法小节;
  §三 平台明细标注为紧凑档取值依据;§六 自检补机检与降档条目;
  §七 补「极限档是工程取值非实测」与它的定位说明

### Verified
- 三档实测(9:16 样本,含贴底 100px 落款与贴右 40px 序号):
  标准档报 2 处 C 类 ✓ → 紧凑档仍报(底越界 476→380px)✓ → **极限档 `ok:true`** ✓
- `--safe-inset "2.5%"` 与 `"48,27,48,27"` 等价 ✓;`--safe-area auto` 正确判出 9x16 ✓;
  非法画幅/参数个数 → `BAD_SAFE_ARGS` + hint + 退出码 2 ✓
- 装饰(`data-allow-overflow`)与安全区内的内容均未误报 ✓

## v1.7.5 — 卡片防出框 + 视频安全区(两个用户实测痛点)

### Fixed · 文字越出卡片边框(字多时尤甚)
**根因是结构性的,不是"不小心"**:三处缺口叠加 ——
① 容器写死 `height`;② 全技能 `min-height`/`line-clamp`/`text-overflow` 出现 **0 次**
(没有任何收口手段);③ **所有自检都以"画布"为溢出参照系**,「文字出卡片但没出画布」
在 rubric 五维里全部达标 → 这类缺陷**无人看得见**。

- **新增 `scripts/check_overflow.py`(机检,治本)**:Playwright 加载后遍历 DOM 报两类
  - A 内容溢出自身盒(限**有背景/边框**的盒,排除行盒噪声)
  - B 文字越出最近"绘制的祖先"的 border-box —— 正是"突破底层边框"
  - 装饰加 `data-allow-overflow` 豁免;容差默认 4px;退出码 0/1 可接 CI
  - **校准过程**:首版报 11/11 案例全中,实为噪声(`h1{172px/1.12}` 的行盒小于字体
    content area;`.kicker` 等无背景行内元素)。加"必须 painted"条件后:
    **案例 0 假报、造的真溢出样本 5 处全检出**
- **新增 `references/card-layout.md`**:三条硬规则(禁写死 height / 禁 top+bottom 双锁装
  可撑高内容 / 装饰越界要显式声明)+ **卡高公式**(接基线单位,含算例)+ 五种骨架
  (min-height 自适应 / line-clamp 收口 / grid auto-rows / flex-wrap / 定高+收口)
  + 「一行修复对照表」+ 三个真实反例写法
- `scaffold.py` 模板内置防线:`.card`(min-height)、`.clamp-1/2/3`、`.ellip`、
  `.allow-ovf`、间距 token(`--pad`/`--gap`/`--radius`),并在 HTML 注释里给出卡片写法示例
- `guardrails.md` §7 溢出修复**分两类**并新增「**第 0 步:让框跟随内容**」
  (首选结构修复;明确禁止用 `overflow:hidden` 兜文字——会裁掉半个字);
  §9 自检新增「跑过 check_overflow 且 ok」
- `design-review-rubric.md` B 维度补「文字无一处越出容器边框」,
  硬伤补「文字越出卡片框 ≥20px」——此前该缺陷在五维中全无判据
- `styles/xhs-cover.md:94`「禁止用 `flex:1`」补语境限定:禁的是**制造**留白,
  不是禁 flex 自适应(原文易被误读成"别用 flex",反而加剧问题)

### Fixed · 视频卡内容被字幕/平台 UI 盖住
- **新增 `references/video-safe-area.md`**:三画幅保守可用区 + 平台 UI 遮挡明细 + 字幕带
  参数 + 内容与字幕的三种共存方案
- **补齐 `animation.md` 只有一行的旧规范**(原仅 9:16 且只写 230/576/118):
  - **发现并修正一处真错误**:左右安全区原从 CutFlow 口径取 8%(86px),
    而 2026 平台实测 TikTok 右侧按钮列宽 **180px**、三平台交集 **17%(184px)** ——
    原值**严重不足**,"logo 放右下""落款贴边"必被按钮盖
  - 9:16 统一为 **左/右 184 / 顶 230 / 底 576**;新增 16:9(10%/16%/8%)与
    3:4(10%/18%/7%)两档(原文完全没有)
  - 数据来源与置信度、漂移声明(Reels 底部两源差 80px:420 vs 500)一并写明
- `animation.md` 模式 S 骨架新增 `.safe` 包裹层(内容层)与 `.bg` 装饰层分离,
  用 flex 居中代替逐个 `top:` 定位;`scaffold.py` 模板同步给出 `.safe`
- 场景卡自检清单把安全区改为**指向 video-safe-area.md 并补全三画幅**,
  点名"最容易漏的是左右 184px"

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
