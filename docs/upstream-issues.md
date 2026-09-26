# artboard · 上游 Kiln 缺陷跟踪台账

> **纪律**(ADR-AB-E08):不改上游 VellumBench —— 发现问题**只登记 + 给绕行**,
> 修复建议以 issue 方式人工提交上游;上游修好后在本表标"已修 + 版本"。
> 用户问及相关问题时的提示语:**"该问题在上游,已登记本台账,绕行方案见表。"**(06-X2)

| # | 现象 | 复现 | 影响 | 绕行 | 上游状态 |
|---|---|---|---|---|---|
| **UP-1** | Kiln 浏览道对 `src/fonts` **目录联接** canonicalize 判越界 → **webfont 静默回退系统字体** | 用默认瘦身影子(联接)建项目 → 导出 → 输出字形为系统字体 | 字体选型失效,且**无任何告警**(最容易不知不觉翻车的坑) | `scaffold --embed-fonts`(真拷贝)或 export 前把字体真拷进项目 | 未修(根修在 staticsrv;2026-09-22 CHANGELOG 登记) |
| **UP-2** | Kiln **native 道**对伪3D 原语(translateZ/rotateY/perspective)**静默降级无告警** | `--engine native` 导含伪3D 原语的页,对比 auto/browser 道 | 矢量/降级输出与预期不符,无提示 | 用 `--engine auto`;按 `references/depth-3d.md` 双道矩阵选原语 | 未修(建议上游加告警通道;2026-09-22 CHANGELOG 登记) |
