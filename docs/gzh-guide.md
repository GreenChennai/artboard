# 公众号双封面与内容排版 · 使用指南

> artboard 当前提供微信公众号**双封面**(头条 + 次条,可单独导出/合并成一张)、**公众号正文排版**(Markdown → 全内联样式 HTML)与独立**预览复制页**(选择版本、手机预览、复制到官方 135)。
> 规格依据与来源见 [gzh-spec-summary.md](gzh-spec-summary.md);
> 排版细则见 [../references/gzh-typography.md](../references/gzh-typography.md);
> 封面品类规范见 [../references/formats/gzh-cover.md](../references/formats/gzh-cover.md)。

## 一、功能总览

| 能力 | 命令入口 | 产物 |
|---|---|---|
| 双封面项目生成 | `gzh_cover.py new` | src/index.html(主 900×383)+ src/sub.html(次 383×383) |
| 单图交付(v1.26) | `gzh_cover.py export` | 一整张合一图 PNG(长封面在左 + 方形在右),即后台上传件 |
| 分件导出 | `export --split` / `--only main` / `--only sub` | 显式要单张/分三张时才出;默认不出 |
| 仅重拼合并图 | `gzh_cover.py merge` | 合并图(`kiln-cli img stitch` 纯像素拼接,不重渲染 HTML;仍需 Kiln CLI 在位,缺则报 `KILN_NOT_FOUND`) |
| 正文排版 | `gzh_article.py convert` | 全内联样式正文 HTML + 按封面文案自动选族的双封面单图 |
| 正文与预览复制 | `gzh_article.py convert --preview` | 通用全内联正文 HTML + `*.preview-copy.html`；封面可用 `--cover-layout auto`/六族/`legacy`，`plate-page` 另需 `--cover-image` 本地照片，`--cover-fx` 控制 MIT shader |
| 预览复制页 | `gzh_preview_copy.py` | 单文件预览、版本选择、HTML/纯文本复制、打开官方 135 |
| 排版示例 | `gzh_article.py demo` | 示例 .md + 转换结果 + 自检报告 |
| 兼容自检 | `gzh_article.py check` | 单行 JSON 违规报告 |

## 二、双封面:五分钟上手

```bash
S="<skill 目录>/scripts"

# 1. 生成项目(内置 6 套统一主题:ink/night/warm/grass/red/mono;色源 scripts/_gzh_theme.py)
python $S/gzh_cover.py new my-post --title "双封面工作法" \
    --sub-title "双封面法" --kicker "ARTBOARD · 02" \
    --sub "一次设计 · 一体出片" --footer "WECHAT OFFICIAL ACCOUNT" \
    --num "02" --theme ink --layout band-editorial

# 2. 导出(默认只出一张合一图 = 后台上传件)
python $S/gzh_cover.py export my-post
#   → export/cover-my-post.png         2680×766  (左 1800×766 + 右 766×766,一体出片)
#
# 需要单张或三张分件时(非默认):
#   python $S/gzh_cover.py export my-post --split
#   → cover-main-… 1800×766 / cover-sub-… 766×766 / cover-merged-… 2680×766

# 3. 静态几何/离线检查
python $S/gzh_cover.py check my-post

# 4. 只改了文案?重跑 new --force + export 覆盖;或手工改 HTML 后只重导单张
python $S/gzh_cover.py export my-post --only main
```

- `--layout` 可选 `center-band`、`band-editorial`、`stack-cards`、`giant-caps`、`kraft-note`、`plate-page`；直接运行 `gzh_cover.py new` 不传布局时仍保留旧模板。文章转换的 `--cover-layout auto` 有 `--cover-sub` 时先选 `band-editorial`，无副题选 `center-band`；若主/次标题断点不适配会回退 `center-band`，显式布局不回退。`--cover-fx auto` 接入版式默认的MIT WebGPU效果，`none` 关闭；`legacy`显式恢复旧式。
- `gzh_cover.py check` 对六族执行完整安全区/信息层级检查，并检查显式标题断点是否拆词或把助词推到行首/行尾；旧 `legacy` 返回 `coverage=partial`，不把旧标记误报成新族溢出。
- `gzh_cover.py new` 的 CSS `--bg-pattern` 与 WebGPU `--fx` 为互斥底材；显式选一个时自动层让位，两者都显式启用则报 `BACKGROUND_LAYER_CONFLICT`，不静默丢弃用户参数。
- **尺寸预设**:头条采用 900×383(约 2.35:1)、次条采用 383×383，作为 Artboard 内部尺寸预设，参考第三方 135 教程；不是微信官方规格，也不表示平台保证按中央区域或左侧裁切。中央 383×383 仅作保守排版安全区，发布前核对当前公众号后台预览。依据见 [gzh-spec-summary.md](gzh-spec-summary.md) §一。
- **自定义字体**:`--fonts smiley-sans,source-han-sans`(第一款=展示体,第二款=正文体);
  `auto` 用默认双字体。字体来自 `fonts/` 库(离线渲染)。
- **手工改稿**:直接编辑 `src/index.html` / `src/sub.html`(设计 tokens 在 `:root`,
  与 scaffold 项目同构),改完重跑 export;机检 `check_overflow.py` 同样适用:
  ```bash
  python $S/check_overflow.py <项目>/src --width 900 --height 383
  ```
- **合一图(默认交付)**:主封面(左)+ 次条(右)等高拼接,默认间隔 **0**(v1.26.2 起,出片即可上传,不留白缝),
  `kiln-cli img stitch` 纯像素搬运(v1.9 起,不再用 Pillow),单张原始比例不变。
  确需留白或换底色时显式覆盖:`merge my-post --gap 80 --bg "#0f1b3d"`;导出时也可加 `export my-post --gap 80`。
  这张合一图**就是**公众号后台上传件;分件只在被明确要求时用 `--split` 出。
- **背景优先级(高 → 低)**:① 实拍/生图照片层(`new --bg-image <图>`,已有项目用 `bg-attach` 挂图)
  → ② AI 生图提示词(`bg-prompt` 生成 `bg-prompt.txt`,交给生图工具出图后 `bg-attach` 挂回)
  → ③ CSS 配方(`--bg-recipe`,八套见 references/gzh-cover-backgrounds.md)。
  照片层与配方互斥,同传报 `BAD_BG_COMBO`;`--bg-recipe` 与 shader 底材也互斥,`--fx auto` 时 shader 让位。
  照片必须**无文字**(提示词整段写明 NO TEXT,让模型画字必糊),单文件 ≤2.6MB,超出报 `BG_IMAGE_TOO_LARGE`;
  解码失败 `BG_IMAGE_DECODE_FAILED`,缺 Pillow `BG_IMAGE_PILLOW_MISSING`。

## 三、正文排版:从 Markdown 到公众号

```bash
# 通用文章 HTML + 独立预览复制页
python $S/gzh_article.py convert 文章.md --out article.html \
    --title "文章标题" --author "署名" --theme ink --preview --no-cover
python $S/gzh_article.py check article.html     # 必须 ok:true

# 正文 HTML + 独立预览复制页；默认同步生成同主题双封面
python $S/gzh_article.py convert 文章.md --out output/article.html --outdir output --theme ink --preview --cover-layout band-editorial --cover-kicker "栏目" --cover-sub "主封面副题" --cover-sub-title "次条标题"
# 使用画页分栏时，COVER_IMAGE 需指向现存的本地 PNG/JPEG/WebP；不会上传到 135
python $S/gzh_article.py convert 文章.md --out output/article.html --outdir output --cover-layout plate-page --cover-image "$COVER_IMAGE"
# 已有 HTML 时直接包装；多篇/多品牌使用重复 --doc
python $S/gzh_preview_copy.py output/article.html --label "品牌A版"
python $S/gzh_preview_copy.py --doc "品牌A=output/a.html" --doc "品牌B=output/b.html" --out output/preview-copy.html
```

- 默认封面会先运行 `gzh_cover.py check` 再导出。若返回 `COVER_CHECK_FAILED`，正文/预览文件已生成但封面不导出；看 `cover_hint` 的 `title-word-break` / `title-particle-edge`，改写封面标题或换族后重跑。结构断点检查不代替最终实图审美检查。

1. 支持组件:标题(h1–h4)、正文、引用、无序/有序列表(嵌套 1 层)、表格、
   围栏代码块(带语言标签)、行内代码、图片、分割线、加粗/斜体/删除线/链接;
2. 产物是**全内联样式**的 `<section>` 片段:无 class/id/`<style>`/`<script>`/外部 CSS;
3. `convert --preview` 生成 `*.preview-copy.html`：选择篇目/品牌、手机宽度预览、复制 `text/html` + 纯文本；兼容复制路径失败会显示状态。预览/剪贴板会剥除 script、事件属性与 `javascript:` URL；该页不是 135 编辑器，也不模拟私有 DOM;
4. 在预览复制页点击“复制当前篇目”，再点“打开 135 编辑器”；粘贴到官方 135 编辑区（不要粘源码模式），核对后点“复制使用”，最后粘到公众号;
5. 本地图片不会由 135/复制页上传；粘贴后在 135/公众号检查并替换图片，发布前用手机预览;
6. 主题:`ink`(#3b82f6 蓝,默认)/ `night`(#e8b04b 深底金)/ `warm`(#d47435 暖橘)/
   `grass`(#1a7a4f 绿)/ `red`(#c0392b 红)/ `mono`(#444444 黑白)——上列是图文主色
   (`primary`);封面另取 `bg/bg2/ink/accent`。旧名 `default`/`orange`/`green` 是
   **弃用别名**(用时打印一次性提示,色值等于对应新名),不再各自成板;
   旧文档的「`default` = 微信蓝 #576b95」已作废(`default` → `ink`,主色 #3b82f6)。
7. 自定义配色:**唯一色源是 `scripts/_gzh_theme.py` 的 `THEMES` 表**(`gzh_article.py`
   与 `gzh_cover.py` 都只从它取角色子集,一处改色两产物同变)——不要去改
   `gzh_article.py` 里的 `THEMES`(那只是 `_gzh_theme.article_themes()` 的返回值)。

快速体验:`python $S/gzh_article.py demo --outdir <目录>` 生成文章、预览复制页与自检报告。

## 四、与 artboard 流水线的关系

- 双封面走现行导出主链(**Kiln 原生引擎**:`gzh_cover.py export` → `scripts/export.py`
  → `kiln_cli_exe`;引擎缺失报 `KILN_NOT_FOUND`。旧 WPI 主链 v1.8 及以前已退役,
  口径见 `references/export.md`),`project.json` 的 `kind: "gzh-cover"`;
- Step 6 机检门禁适用于双封面 HTML(`check_overflow.py`);
- 风格上双封面可用任意设计手法手写,品类纪律(安全区/字号阶/禁则)
  见 `references/formats/gzh-cover.md`;正文排版纪律见 `references/gzh-typography.md`。

## 五、异常处理

| 现象 | 报错 | 处理 |
|---|---|---|
| 渲染引擎缺失 | `KILN_NOT_FOUND` | `python $S/setup_kiln.py` 或设 `ARTBOARD_KILN_CLI` |
| 字体目录写错 | `NO_FONTS` | 用 `fonts/` 下真实目录名;`auto` 恒可用 |
| 找不到已导出件 | `MISSING_EXPORTS` | 默认 `export` 已直接出合一图;仅 `--only` 指定分件时才需要先 `--split` |
| 合并图拼接失败 | `STITCH_FAILED` / `KILN_NOT_FOUND` | 合并图由 `kiln-cli img stitch` 拼接:确认两张单图存在且未损坏、引擎已部署 |
| 项目已存在 | `EXISTS` | 换 slug 或 `--force` 覆盖 |
| Markdown 为空 | `EMPTY_INPUT` | 检查输入文件 |
| 兼容自检不过 | `violations` 列表 | 按提示删 class/script/外链后重转 |

本册涉及的**机检 / 转换 / 导出类脚本**失败时仍输出单行 JSON(`ok:false` + `error`/`hint`),
可被上层脚本链消费。已核实(读代码 + 实跑失败路径)的清单:`gzh_cover.py`(如 `PROJECT_NOT_FOUND`)、
`gzh_article.py`(`FILE_NOT_FOUND`/`EMPTY_INPUT`/`BAD_THEME`)、`check_overflow.py`(`NO_HTML`)、
`export.py`(`KILN_CLI_FAILED`)、`export_fallback.py`(`NO_BROWSER`/`NO_PLAYWRIGHT`/`EMPTY_SCREENSHOT`)。
**不在此名单内**(别指望它吐 JSON):`setup_kiln.py` 等部署脚本打纯文本(如 `[X] --exe 指向的文件不存在: …`);
`check_wechat_svg.py` 默认打人读报告,要 JSON 得加 `--json`;`imageops.py` 的 montage 缺图路径仍会裸 traceback。

## 六、回滚

- 本次迭代在 `feat/wechat-dual-cover` 分支开发,合并前 main 不受影响;
- 单提交回滚:`git revert <commit>`;整批回滚:`git revert <merge-commit> -m 1`;
- 紧急恢复到迭代前:`git checkout v1.7.6 -- scripts/ SKILL.md README.md CHANGELOG.md references/ docs/`。

## 七、样例

双封面默认产物是**一张图**,落在项目的 `export/` 里:
`cover-<slug>.png`(合一图,后台上传件)。
只有显式 `--split` 时才额外出 `cover-main-<slug>.png`、`cover-sub-<slug>.png`、`cover-merged-<slug>.png`。
正文排版产物是单文件 HTML(`--out` 指定路径),`--preview` 会另出一份手机宽度的预览页;
`demo` 子命令一键生成全组件示例,顺手跑一遍兼容性自检。

---

## 图文与封面绑定(11 迭代,2026-09-26)

- **单向绑定**:出图文(`gzh_article.py convert`)默认同时出同主题双封面单图(`--cover-split` 才分三张);
  只出封面(`gzh_cover.py`)不产图文。`--no-cover` 是逃生口,用了要在交付汇报里说明。
- **标题来源**:封面主标题取 `--cover-title > --title > 文章 H1`；无须另行复制标题，但断点质量门若拒绝，需按 `cover_hint` 改写/加自然停顿，不能把失败输出当成可用封面。
- **主题唯一真相源**:`scripts/_gzh_theme.py`,6 套:ink(蓝黑)/ night(深色金)/
  warm(暖米)/ grass(绿)/ red(红)/ mono(黑白)。封面取 bg/bg2/ink/accent/muted/line,
  图文取 primary/text/muted/soft/border/quote,同角色同值。
- **一致性机检**:
  `gzh_article.py check <图文.html> --theme-consistency --cover-html <项目>/src/index.html --theme <名>`
  → 两产物核心角色必须同值,且不得混入他主题强调色(退出码 1 = 不同风格,挡交)。
- **旧主题名迁移**(一次性提示,不影响出图):

| 旧名 | 用在哪 | 新名 | 注意 |
|---|---|---|---|
| blue | 封面 | ink | 色值统一 |
| dark | 封面 | night | 色值统一 |
| default | 图文 | ink | 色值统一 |
| orange | 图文 | warm | 色值统一 |
| green | 封面+图文 | grass | **同名不同色隐患已消除:统一为一套绿** |
