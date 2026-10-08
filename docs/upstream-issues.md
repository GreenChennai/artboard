# artboard · 上游 Kiln 缺陷跟踪台账

> **纪律**(ADR-AB-E08):**不自动改上游 VellumBench** —— 发现问题**只登记 + 给绕行**,
> 提交 issue / 改上游代码 / 关 issue 都是**人工**动作(需要 GitHub 授权与用户确认)。
> 上游修好后在本表标"已修 + 版本";**确认修好之前不删本行** —— 删了就丢了复现步骤。
> 用户问及相关问题时的提示语:**"该问题在上游,已登记本台账,绕行方案见表。"**(06-X2)
>
> **一条缺陷走完的路径**:① 实测复现(记下命令与期望/实际)→ ② 订正事实
> (复核上游源码,别把猜测写进去 —— v0.14.1 复核就勘误了 UP-4)→ ③ 在本表登记
> + 给 artboard 侧绕行 → ④ **由用户**在 VellumBench 提 issue(附本表复现步骤)→
> ⑤ 同步引擎版本后复查,改「上游状态」列。**④ 不要自动做**:issue 是公开的、
> 不可撤回,且需要用户的 GitHub 身份。
>
> **基线**:Kiln **v0.14.3**(`CHANGELOG.md` 顶条)。发行资产在 **artboard 发行页**
> `kiln-cli-v0.14.3`,`scripts/setup_kiln.py` 内置该版本的 URL + sha256 + 版本基线
> 三件套(`KILN_VERSION` / `RELEASE_SHA256` / `BASELINE`),**换版时三处同改**。
> 校验实测:工作区里已部署的那份引擎 exe 与发行资产 sha256 一致
> (`00185547…`);`setup_kiln.py --force` 对不符值**拒绝写 config 并保留产物**。
> 引擎 `selfcheck` 回报 `{"ok":true,"formats":9,"browser_lane":"ok(true) Edg/154.0.4258.62"}`。
> v0.11–0.14.1 的修复见下方各条「上游状态」列。

| # | 现象 | 复现 | 影响 | 绕行 | 上游状态 |
|---|---|---|---|---|---|
| **UP-1** | Kiln 浏览道对 `src/fonts` **目录联接** canonicalize 判越界 → **webfont 静默回退系统字体** | 用默认瘦身影子(联接)建项目 → 导出 → 输出字形为系统字体 | 字体选型失效,且**无任何告警**(最容易不知不觉翻车的坑) | `scaffold --embed-fonts`(真拷贝)或 export 前把字体真拷进项目 | **已修(v0.10.0,ADR-0045)**:词法规范化主判定 + canonicalize 允许根集合;--embed-fonts 绕行不再必需(保留为极端兜底)。v0.14.1 复查仍有效 |
| **UP-2** | Kiln **native 道**对伪3D 原语(translateZ/rotateY/perspective)**静默降级无告警** | `--engine native` 导含伪3D 原语的页,对比 auto/browser 道 | 矢量/降级输出与预期不符,无提示 | 用 `--engine auto`;按 `references/depth-3d.md` 双道矩阵选原语 | **已修(v0.10.0,ADR-0046)**:三处收集聚合计数,命中置 degraded:true;新增 UnsupportedPropertyDropped/InlineSvgRasterized 等强类型告警与 `warnings_by_kind` 聚合 |
| **UP-3** | Kiln **GIF 车道**对 `steps()` 时序函数(`steps(1,end)` 硬跳变动画)**输出错帧**:该跳变的元素全程停在 `from` 色,永不到 `to` 色;**同页同参数的 MP4 车道正确** | 1080×1920 页:`.a{position:absolute;top:200px;height:400px;background:#f00;animation:jump 2s steps(1,end) forwards}`、`@keyframes jump{from{background:#f00}to{background:#00f}}`。`python scripts/export.py --source <页> --output out.gif --format GIF --width 1080 --height 1920 --fps 10 --max-wait 4`,再 `ffmpeg -i out.gif -vf "select='eq(n,0)+eq(n,10)+eq(n,25)+eq(n,39)'" -fps_mode passthrough f%02d.png` 取帧读 `(540,400)` | 卡点动画做的"硬切/闪切"在 **GIF** 里不可信 —— 40 帧实测全为 `(255,0,0)`,第 20 帧后应已是 `(0,0,255)`(静态导出不受影响,仍快进到终态) | 卡点动画改用**连续**时序函数(`linear`/`ease-*`),或改出 MP4,或在每帧内用多个 `<div>` 显隐切换。**这与本技能铁律一致**:`references/animation.md` 本就禁用 `steps()`(硬切用帧内显隐实现) | **已修(v0.14.2)**。根因是**三处独立缺陷叠加**,单修任一处都只是挪位置:① --run-all-compositor-stages-before-draw 让合成器停摆,captureScreenshot 永远等不到帧(**静态车道也一起挂**,单次 encode_ms 813978);② --enable-begin-frame-control 无条件下发,而现代 Chromium 已移除 HeadlessExperimental.beginFrame,flag 与调用必须成对选择(新增 LaunchOptions::begin_frame_control);③ repaint 等待挂在 VB_NO_BEGINFRAME 环境变量上,于是唯一可行路径反而不等;④ 末帧不触达片长((n-1)/fps 恒小于 duration)。修复后实测:首帧红 → **第 20 帧蓝** → 末帧蓝。**本条可从工作绕行清单移除** |
| **UP-4** | Kiln 的 **GIF 调色板质量取决于本机有没有 ffmpeg,且 MP4 的 GOP / B 帧 / 色彩标签不暴露** | ① 无 ffmpeg 环境导出 GIF(`vb_kiln/src/frames.rs:encode_gif` 走 image crate 感知量化 LZW 单 pass);② 对比有/无 ffmpeg 的 GIF 体积与色阶;③ `ffprobe` 看 MP4 是否带 B 帧(GOP 默认 250、B 帧默认 3) | 无 ffmpeg 时 GIF 色阶明显劣化;带 B 帧的 MP4 在部分播放器上可能有**首帧黑**(负 DTS) | ① 装 ffmpeg(`scripts/setup_ffmpeg.py`)—— 有 ffmpeg 时 GIF **已经**是 `palettegen=stats_mode=diff` + `paletteuse=dither=sierra2_4a` 两 pass,**这一格不用绕**;② 对成片做一次 ffmpeg 后处理转码(`-bf 0`、偶数尺寸 pad),或用审片台「裁片段」(已带 `-bf 0` 与偶数 pad) | **已修(v0.14.2)**。**勘误(v0.14.1 复查)**:原登记"GIF 走单 pass 内置量化"不准确 —— 两 pass 路径自 v0.9.0 起就存在,只是 `if ffmpeg_available()` 门控,报告里也不声明走了哪条;MP4 码率已由 `--bitrate` 暴露。**新增** `--gop` / `--bf` / `--pix-fmt` / `--no-color-tags`(默认不下发 = 逐位保持旧行为,已用 ffprobe 核对默认仍含 B 帧)。另修掉一处**静默错色**:`palettegen` 的 `stats_mode=diff` → `full`(`diff` 只统计帧间变化过的像素,硬切动画的大片纯色进不了调色板,实测 40 帧里蓝色整段丢失)。路径声明由 `encode_gif` 回传 `GifEncodeOutcome`,native GIF 写出器 / MP4→GIF 降级 / 浏览器动画车道三个出口各自 push 进 report |
| **UP-5** | **Kiln 动画车道极慢**:逐帧截图 + 逐帧 PNG 落盘,实测 **0.88 帧/秒**(1080×1440 @25fps × 15s = 375 帧 → **427s**);轻量页 40 帧 3.37 帧/秒 | `python scripts/export.py --source <动效页> --output o.gif --format GIF --width 1080 --height 1440 --fps 25 --max-wait 15` | 动图迭代周期被拉长到分钟级,叠加 `--timeout`(默认 900s)时**重页面有真被砍掉的风险**;且长任务后**残留孤儿浏览器进程**(实测 27 个 `msedge` 不退,会把后续导出的截图拖到超时) | ① 迭代期用低 fps/短时长核对版式(`--fps 10 --max-wait 3`),定稿再上高参数;② `references/export.md` 的「帧网格量化」把动画压到 8–12 个关键状态,帧数 = 状态数 × 2;③ 引擎报告的 `instances[].fps` 与 `frame_interval_ms.p95/p99` 是判断"慢 vs 卡"的权威数据(0.14.0 新增);④ **孤儿进程由 artboard 侧的进程树看门狗兜住**(`scripts/_proc.py` 超时强杀整棵树) | **未修**(无 issue;属设计取舍:动画车道默认 `--workers 0`=串行,因为两轮下游实测多实例都是负收益)。**但 `export.py` 已加进程树墙钟看门狗**(`scripts/_proc.py`),超时强杀并如实报 `KILN_CLI_TIMEOUT`,不再"卡住、杀不掉、也不报错" |
| **UP-6** | **动画两道结果 JSON 的 `width`/`height` 恒为 0**(未显式传 `--width`/`--height` 时):CLI 把原始 `width`/`height`(默认 0)直接填进结果,而实际视口是引擎内部兜底后的 1080 | `kiln-cli export --format mp4 --source page.html -o out.mp4`(帮助文本明说"默认自适应画板")→ 成片真实 1080×1080,JSON 报 `"width":0,"height":0`。`export.py` 的 FIELDS 会把它原样回填进结果 payload | 下游按 JSON 做尺寸门/排版/画幅校验必错。**SKILL.md 已要求非 1080 画幅显式传 `--width/--height`,这条正是那条纪律的技术理由** | 动图一律显式传 `--width` **与 `--height`**(动画卡尤其别省 `--height`,`100vh` 型必须锁);或不信 JSON,直接量成片尺寸 | **未修**(2026-10-07 复核 `kiln-cli.rs:695-696`/`:759-760` 发现,尚未提 issue) |
| **UP-7** | **浏览器静态/动画车道的 `degraded` 硬编码 `false`**,但同一份 warnings 里已有语义降级信号(无限动画未收敛、settle 未收敛、静态资源 404) | 页面含 CSS `infinite` 动画 → 交付的是"某一帧"却报 `ok:true, degraded:false`;下游"degraded==true 拒收"门禁被静默绕过(与 ADR-0046「降级必须可观测」相悖) | 门禁形同虚设。artboard 只能靠 `stderr` 的 `domwarn:` 行与 `degraded_artboard` 两个独立信号兜 | 门禁**不要只看 `ok`/`degraded`**:`export.py` 已把 `domwarn:` 前缀的告警并入 `warnings`(`vb_layout:` 之外那半条分支),按 warnings 有无来判 | **未修**(2026-10-07 复核 `kiln-cli.rs:842`/`:693`/`:757` 发现,尚未提 issue) |
