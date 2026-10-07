# artboard · 上游 Kiln 缺陷跟踪台账

> **纪律**(ADR-AB-E08):不改上游 VellumBench —— 发现问题**只登记 + 给绕行**,
> 修复建议以 issue 方式人工提交上游;上游修好后在本表标"已修 + 版本"。
> 用户问及相关问题时的提示语:**"该问题在上游,已登记本台账,绕行方案见表。"**(06-X2)

| # | 现象 | 复现 | 影响 | 绕行 | 上游状态 |
|---|---|---|---|---|---|
| **UP-1** | Kiln 浏览道对 `src/fonts` **目录联接** canonicalize 判越界 → **webfont 静默回退系统字体** | 用默认瘦身影子(联接)建项目 → 导出 → 输出字形为系统字体 | 字体选型失效,且**无任何告警**(最容易不知不觉翻车的坑) | `scaffold --embed-fonts`(真拷贝)或 export 前把字体真拷进项目 | **已修(v0.10.0,ADR-0045)**:词法规范化主判定 + canonicalize 允许根集合;--embed-fonts 绕行不再必需(保留为极端兜底) |
| **UP-2** | Kiln **native 道**对伪3D 原语(translateZ/rotateY/perspective)**静默降级无告警** | `--engine native` 导含伪3D 原语的页,对比 auto/browser 道 | 矢量/降级输出与预期不符,无提示 | 用 `--engine auto`;按 `references/depth-3d.md` 双道矩阵选原语 | **已修(v0.10.0,ADR-0046)**:三处收集聚合计数,命中置 degraded:true;新增 UnsupportedPropertyDropped/InlineSvgRasterized 等强类型告警与 warnings_by_kind 聚合 |
| **UP-3** | Kiln **GIF 车道**对 `steps()` 时序函数(`steps(1,end)` 硬跳变动画)**输出错帧**:该跳变的元素要么全程停在 `from` 色,要么落到与自身关键帧无关的颜色;**同页同参数的 MP4 车道正确** | 1080×1920 页:`.a`=`animation: jump 2s steps(1,end) forwards`(红→蓝,≥2s 应纯蓝);`.b`=`animation: jump2 4s steps(1,end) 2s forwards`(绿→蓝,≥6s 应纯蓝)。`python scripts/export.py --source <页> --output out.gif --format GIF --fps 10 --max-wait 8`(另出一份 `--format MP4` 对照),再用 **ffmpeg 独立解码**取帧 5/15/35/65/75 采样 `(540,300)` 与 `(540,1500)` | GIF:`.a` 80 帧**全程红**(从未跳变),`.b` 前 6s 绿、之后变**红**(红色不在 `.b` 关键帧里,也不是页面底色);MP4 同参数:`.a` 第 15 帧已蓝、`.b` 第 65 帧已蓝,**均正确** ⇒ 用 steps() 做的"硬切/闪切"卡点在 **GIF** 里不可信(JPEG/PNG 静态导出不受影响,仍快进到终态) | 卡点动画改用**连续**时序函数(`linear`/`ease-*`),或改出 MP4,或在每帧内用多个 `<div>` 显隐切换 | **已提交**:[#1](https://github.com/GreenChennai/VellumBench/issues/1)(2026-10-07,artboard 侧实测:ffmpeg 独立解码 + MP4 对照) |
| **UP-4** | Kiln 的 **GIF/MP4 编码参数不可调**:GIF 走单 pass 内置量化(无 `palettegen stats_mode=diff` 两 pass、无 `sierra2_4a` 抖动控制),MP4 的 GOP / B 帧 / 色彩标签也不暴露 —— 同稿导出的体积与观感不如 ffmpeg 两 pass;带 B 帧的 MP4 在部分播放器上可能有**首帧黑**(负 DTS) | 同一动效稿分别用 `export.py --format GIF/MP4` 与 ffmpeg 直出(GIF 两 pass / MP4 `-bf 0`)对比体积与首帧 | 交出去的文件"能不能播、够不够小";首帧黑属可避免的兼容性问题 | ① 审片台的「裁片段」用 ffmpeg 直出(已带 `-bf 0` 与偶数尺寸 pad);② 对成片做一次 ffmpeg 后处理转码。期望参数清单见 `references/export.md`「GIF/MP4 的编码质量」 | **已提交**:[#2](https://github.com/GreenChennai/VellumBench/issues/2)(2026-10-07,artboard 侧整理;期望参数来源 hyperframes `gifEncodeArgs.ts`/`chunkEncoder.ts`,Apache-2.0) |
