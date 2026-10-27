# Shader Effects · WebGPU 效果接入

> **适用面**：公众号双封面(`gzh_cover.py --fx`)、WebGPU 视频卡与 `shader_fx.py` 独立底图导出。
> 平面海报/主 KV/长图的默认质感走 `components/registry/` 的静态 CSS 组件 + `--ab-*` token，不用 shader。

> Artboard 随包携带 `vendor/shaders/upstream.js`，其中包含来源于上游的 shader 代码和本地 global/API wrapper；`vendor/shaders/runtime.js` 是 Artboard 参数与生命周期适配层，不实现 shader 算法。MIT 许可随包保留在 `vendor/shaders/LICENSES/shaders-LICENSE`。
>
> 上游来源：[shader-effects-inc/shaders](https://github.com/shader-effects-inc/shaders)，版本 `4.0.4` 的 tag 对应 commit `81fd4ece5d493ca6c424a2af41f0e2c361ec8258`。官方 npm 文件 `dist/js/bundle.js` 为 2,584,407 bytes，SHA256 `E00B8C9954C819910F1C8660C5035CA24F79814E752689F819F05C610299625E`；Artboard 本地 `upstream.js` 为 2,589,367 bytes，SHA256 `CAD63C8EE9F907F9773772AC8CA03EBBE21F85CD9EF75C1D6B2C430EA8795290`。两文件不同，因此本地文件不是字节级原包；从上游源码重建并验证构建复现尚未完成。Artboard 暴露 11 个效果入口。

## 1. 何时使用

| 场景 | 用法 |
|---|---|
| 公众号双封面、独立底图导出 | 静态 WebGPU shader 作为底层质感；标题、图表和正文仍在独立 HTML 层 |
| 视频卡、片头、章节卡、转场 | 保持官方 animation loop；用上游组件的 `speed` 控制动态节奏 |
| 135 图文正文 | 用 `gzh_article.py convert --preview` 生成通用内联正文和预览复制页；shader 画面作为独立素材，不把文章变成 canvas，也不仿制 135 私有 DOM |
| 照片/产品主体 | 不用 shader 代替真实素材 |

**运行边界：**官方 runtime 是 WebGPU-only。导出必须使用支持 `--webgpu` 的 VellumBench/Kiln；不支持的 Kiln 或没有 adapter 时明确失败，不静默切回自写 WebGL、原生渲染或 CSS 渐变。不要在 Artboard 项目里复制/重写 shader 算法。

## 2. 组件与效果入口

| `data-fx` | 上游组件 | 说明 |
|---|---|---|
| `aurora` | `Aurora` | 分层极光帘幕和光柱 |
| `mesh-gradient` | `MeshGradient` | 多色网格渐变 |
| `flowing-gradient` | `FlowingGradient` | 有机流动色带 |
| `godrays` | `Godrays` | 放射体积光 |
| `curl-noise` | `CurlNoise` | 旋涡流场 |
| `bokeh` | `BokehBlur` | 官方散景滤镜；适配层在其前插入 MeshGradient 底图组件 |
| `dot-grid` | `DotGrid` | 点阵纹理 |
| `halftone` | `Halftone` | 官方印刷网点滤镜；适配层在其前插入 MeshGradient 底图组件 |
| `truchet` | `Truchet` | Truchet 瓷砖曲线 |
| `vignette-grain` | `Vignette` + `FilmGrain` | 官方滤镜按前序组件顺序应用于 MeshGradient 底图 |
| `water` | `Water` | 水面、波纹和焦散 shape-effect |

`bokeh`、`halftone`、`vignette-grain` 是需要输入内容的上游滤镜。上游 renderer 的 `requiresChild` 约定通过前序 sibling 组件组合；适配层按顺序生成官方 `MeshGradient` 底图、再追加官方滤镜，`vignette-grain` 继续追加 `Vignette` 与 `FilmGrain`。不使用不存在的 `role="filter"` 分支，也不传造出来的 child prop。Artboard 额外接受 `backdropColorA` / `backdropColorB`（以及 `grainStrength` / `grainBias`）作为底图/滤镜组合参数；这些不是上游组件属性。其他参数按上游 component props 透传，未知属性会被忽略。

公众号封面默认：`center-band` / `band-editorial` 使用 `halftone`，`stack-cards` 使用 `dot-grid`，`giant-caps` 使用 `aurora`；`kraft-note`、`plate-page` 默认不加 shader，以保留纸张/版心语义。`--fx none` 可显式关闭，`--fx <slug>` 可选 11 个入口。CSS `--bg-pattern` 与 WebGPU `--fx` 是互斥底材：明确指定 CSS 底纹会压过版式自动 shader；指定 shader 时自动 CSS 底纹记为 `none`；若两者都显式指定为非空效果，命令返回 `BACKGROUND_LAYER_CONFLICT`，不会静默忽略其中一项。

## 3. HTML 接入

脚本必须从本地 `vendor/shaders/` 加载；不使用 CDN。canvas 保持绝对定位铺底，文字放在更高的独立层：

```html
<canvas class="ab-shader" data-fx="mesh-gradient"
  data-webgpu-required="true" data-freeze="true"
  data-params='{"colorA":"#102038","colorB":"#e44b88","speed":0,"seed":7}'
  style="position:absolute;inset:0;width:100%;height:100%;z-index:0"></canvas>
<div style="position:relative;z-index:1">标题与正文</div>
<script src="vendor/shaders/upstream.js"></script>
<script src="vendor/shaders/runtime.js"></script>
```

`runtime.js` 自动 mount `canvas.ab-shader[data-fx]`，并为 canvas 写入 `data-webgpu-status=pending|ready|failed`。Artboard 适配层调用本地 bundle 暴露的 `createShader(..., {disableTelemetry:true})`；不发 telemetry、不访问 CDN。若声明 `data-webgpu-required="true"`，Kiln 会等待所有相应 canvas 首帧成功后再截图。`gzh_article.py convert --cover-fx auto` 按版式选择效果，`none` 关闭；显式 `<slug>` 可覆盖。`pack.py` 检测到 shader 引用时会打入完整 `vendor/shaders/`，并强制包含 `runtime.js`、`upstream.js` 与 MIT LICENSE：来源必须是 Skill 自带的许可 vendor 树，或项目内真实目录；shader 树内不允许嵌套 symlink/junction，外部链接或嵌套链接返回 `SHADER_VENDOR_LINK_FAILED`，必需文件或许可证缺失返回 `SHADER_VENDOR_INCOMPLETE`；封面运行时还会对 runtime、upstream bundle 与许可证逐项校验固定 SHA256，不匹配返回 `SHADER_VENDOR_HASH_MISMATCH`；`shader_fx.py --bake` 也在创建临时页、启动 Kiln 前校验同一组 pin，拒绝执行被篡改的脚本。打包前先拒绝不可信链接，不会先读取或收集其目标；`src` 根不能是联接；普通目录联接不受打包器递归支持，会 fail closed（`PROJECT_LINK_FAILED`）。仅 `src/fonts`→Skill 字体根、`src/vendor`→Skill vendor 根、`src/vendor/shaders`→`SKILL_DIR/vendor/shaders` 完整根（不接受 `LICENSES`、`glsl` 等子目录）是允许的目录根联接；普通文件联接只可指向真实 `src/` 文件或明确许可的 Skill 资产，不能打包 `src` 外的项目私有文件。一个 ZIP 只能使用一种 shader vendor 来源；同时引用 Skill 树与项目本地树时以 `SHADER_VENDOR_ROOT_CONFLICT` 拒绝，避免两个 runtime 覆盖到相同包内路径。

公众号封面 `gzh_cover.py check` 另有严格静态门禁：拒绝 `<base>`，脚本必须解析到当前页实际 `src/vendor/shaders/` 下且命中固定 SHA256（runtime.js `4510B13162748597896C5CA45E3FD509499BE9F670AEDDB7E7BF51A128B1A7E6`；upstream.js `CAD63C8EE9F907F9773772AC8CA03EBBE21F85CD9EF75C1D6B2C430EA8795290`；LICENSE `EEAAA26F5C65CB6DFEBF1C098AC2375FDCDB497CEBF105B0542F229482B106F4`）；不接受任意内联脚本、事件处理器或 `srcdoc`。HTML URL、CSS 资源、`background` 属性和 Water 的 `shapeSdfUrl` 必须位于 `src/` 或明确授权的 Skill 资产根内，禁止 `../` 越界；仅受限的 raster data URL 可内嵌。发现外链、越界本地资源或未审计代码都会使 `offline-only` 失败。静态检查同时拒绝可遮挡封面的 poster 伪元素、被 CSS 隐藏/移走的标题、`video/audio` 和多帧 raster 图像，避免导出空白、遮挡或随时间变化的帧。

### 静态图和双封面

- `data-freeze="true"`：等上游 `onReady`（首帧已渲染）后调用 `ShaderInstance.pause()`；暂停保留最后一帧。`data-freeze-at` 不再使用，不要依赖猜测秒数。
- 静态底图的时间属性设为 `speed:0`、固定 `seed`；两张公众号封面使用相同 `data-fx` 和相同参数，画布尺寸可以不同。
- VellumBench/Kiln `--webgpu` 明确选择浏览器 GPU 路径；无 adapter、首帧失败、旧版 CLI 不支持该参数都返回错误，不允许悄悄出一张空白/降级图。

### 视频卡

- 不设置 `data-freeze="true"`（或设为 `false`），保留官方动画循环。
- 所有 props 使用上游控制面板的原始量纲，不要自行归一化；例如 Aurora 的 `waviness` 是 0–200、`height` 是 10–200、`intensity` 是 0–100。视频卡按官方 props 提供 `speed`；建议低速，文字与背景分层，不用动效抢口播信息。
- WebGPU lane 在编码/截帧前等待首帧 ready；之后动画保持运行。含 `data-freeze="false"` 的 WebGPU 视频卡，导出 GIF 或 MP4 时指定 `--webgpu --wall` 按墙钟实时采样，避免把 requestAnimationFrame 误当成可确定性 seek 的时间轴。当前验证的 Edge 已移除 `HeadlessExperimental.beginFrame`，Kiln 会回退到 `captureScreenshot`；因此需要较新 Kiln 和对应浏览器。MP4 的 `yuv420p` 输出宽高均需为偶数，视频卡应使用如 900×384 的独立画布，不直接复用 900×383 封面画布。

## 4. 命令

```powershell
# 枚举本地 vendored upstream effect registry 的 11 个 Artboard slug
python scripts/shader_fx.py --list

# 先设置为支持 --webgpu 的 VellumBench/Kiln 构建产物，再强制导出静态 PNG
$env:ARTBOARD_KILN_CLI = "D:\path\to\VellumBench\target\release\kiln-cli.exe"
python scripts/shader_fx.py --bake aurora --out "$env:TEMP\aurora.png" `
  --width 900 --height 383 --kiln "$env:ARTBOARD_KILN_CLI"

# 输出可嵌入设计页/视频卡的本地 canvas 与脚本标签
python scripts/shader_fx.py --embed aurora --dynamic --speed 0.6

# 公众号双封面：由布局默认效果自动启用，也可覆盖
python scripts/gzh_cover.py new article.md --layout band-editorial --fx halftone
python scripts/gzh_cover.py export article.md --layout band-editorial --fx halftone --outdir output
```

`shader_fx.py --bake` 走 `scripts/export.py --webgpu`。`export.py` 检查 Kiln `--help` 是否包含 `--webgpu`，并按格式验证成功 JSON：PNG 必须是 `engine="browser"`；GIF 必须是 `browser-anim`；MP4 接受 `browser-anim` 或 `browser-anim-webcodecs`；三者都必须 `webgpu=true`。否则返回 `KILN_WEBGPU_UNSUPPORTED` 或 `KILN_WEBGPU_UNVERIFIED`。可用 `--kiln` 显式指定 VellumBench 构建产物，避免误用旧安装版。

## 5. 构建、许可与排障

- 静态 PNG 会完整解码并验像素；RGBA 全透明、色彩/亮度变化不足或损坏图像都会拒绝，原有输出保持不变。
- Artboard 使用的上游代码为 `vendor/shaders/upstream.js`；更新它时，从固定/审阅过的 `shader-effects-inc/shaders` source 构建并校验 commit、版本和 MIT notice。`vendor/shaders/runtime.js` 只保留 effect slug、主题 props、previous-sibling backdrop composition、freeze/readiness adapter。
- `vendor/shaders/LICENSES/shaders-LICENSE` 保留完整 MIT License。README「直接集成与许可」须注明这是上游组件的直接 bundle，而不是“设计借鉴”。
- `KILN_WEBGPU_UNSUPPORTED`：当前 CLI 太旧；更新 VellumBench/Kiln 并将 `ARTBOARD_KILN_CLI` 指向新构建。
- adapter 不可用：检查 WebGPU/GPU 驱动；任务保持失败，不应改用旧 renderer 冒充成功。
- `KILN_WEBGPU_UNVERIFIED`、`data-webgpu-status=failed` 或首帧超时：检查浏览器控制台及 `data-webgpu-error`，确认本地 upstream bundle/组件 props；不要删掉门禁。
- 纹理太抢主体：先降主题参数、透明度或换一个上游效果；不改写组件算法。对于滤镜，确认 `requiresChild` 触发的前序底图 sibling 已加入且顺序正确，不要传不存在的 `child` prop。

## 6. 交付自检

- [ ] 页面只加载本地 `vendor/shaders/upstream.js` 与 Artboard 薄适配层；MIT License 保留。
- [ ] 静态导出报告 `webgpu=true`，canvas 首帧 ready 后 pause；未走降级路径。
- [ ] 双封面同效果、同 seed/speed/props；标题和正文仍独立可读。
- [ ] 视频导出不 freeze，并能在 WebGPU lane 取到首帧。
- [ ] README 署名、VellumBench/Kiln `--webgpu` 与 Artboard 文档同步。
