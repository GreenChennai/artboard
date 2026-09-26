# 公众号双封面与内容排版 · 使用指南

> artboard v1.8.0 新增能力:微信公众号**双封面**(头条 + 次条,可单独导出/合并成一张)
> 与**公众号正文排版**(Markdown → 全内联样式 HTML,粘贴进公众号编辑器不塌样式)。
> 规格依据与来源见 [gzh-spec-summary.md](gzh-spec-summary.md);
> 排版细则见 [../references/gzh-typography.md](../references/gzh-typography.md);
> 封面品类规范见 [../references/formats/gzh-cover.md](../references/formats/gzh-cover.md)。

## 一、功能总览

| 能力 | 命令入口 | 产物 |
|---|---|---|
| 双封面项目生成 | `gzh_cover.py new` | src/index.html(主 900×383)+ src/sub.html(次 383×383) |
| 三种导出 | `gzh_cover.py export` | 主封面 PNG / 次条 PNG / 合并对比图 PNG(默认三图齐出) |
| 单独导出 | `export --only main` / `--only sub` / `--only merged` | 任意单张重出 |
| 仅重拼合并图 | `gzh_cover.py merge` | 合并图(Pillow 纯拼接,无需渲染引擎) |
| 正文排版 | `gzh_article.py convert` | 全内联样式 HTML 片段 + 本地预览页 |
| 排版示例 | `gzh_article.py demo` | 示例 .md + 转换结果 + 自检报告 |
| 兼容自检 | `gzh_article.py check` | 单行 JSON 违规报告 |

## 二、双封面:五分钟上手

```bash
S="<skill 目录>/scripts"

# 1. 生成项目(内置 4 套主题:blue/dark/warm/green)
python $S/gzh_cover.py new my-post --title "双封面工作法" \
    --sub-title "双封面法" --kicker "ARTBOARD · 02" \
    --sub "一次设计 · 三张产物" --footer "WECHAT OFFICIAL ACCOUNT" \
    --num "02" --theme blue

# 2. 导出(默认三图齐出 = 合一导出)
python $S/gzh_cover.py export my-post
#   → export/cover-main-my-post.png    1800×766  (900×383 @2x)
#   → export/cover-sub-my-post.png      766×766  (383×383 @2x)
#   → export/cover-merged-my-post.png  2680×766  (合并对比图)

# 3. 只改了文案?重跑 new --force + export 覆盖;或手工改 HTML 后只重导单张
python $S/gzh_cover.py export my-post --only main
```

- **尺寸规格**:头条 2.35:1(900×383),转发卡片只露中央 383×383 → 关键信息居中;
  次条 1:1(383×383,官方下限 200×200)。依据见 gzh-spec-summary.md §一。
- **自定义字体**:`--fonts smiley-sans,source-han-sans`(第一款=展示体,第二款=正文体);
  `auto` 用默认双字体。字体来自 `fonts/` 库(离线渲染)。
- **手工改稿**:直接编辑 `src/index.html` / `src/sub.html`(设计 tokens 在 `:root`,
  与 scaffold 项目同构),改完重跑 export;机检 `check_overflow.py` 同样适用:
  ```bash
  python $S/check_overflow.py <项目>/src --width 900 --height 383
  ```
- **合并图**:主封面(左)+ 57px 间隔 + 次条(右)等高拼接,Pillow 纯像素搬运,
  单张原始比例不变。间隔/底色可调:`merge my-post --gap 80 --bg "#0f1b3d"`。
  合并图用于对比展示/汇报存档,**公众号后台上传仍用单张文件**。

## 三、正文排版:从 Markdown 到公众号

```bash
# 写好 Markdown 后一条命令
python $S/gzh_article.py convert 文章.md --out article.html \
    --title "文章标题" --author "署名" --theme default --preview
python $S/gzh_article.py check article.html     # 必须 ok:true
```

1. 支持组件:标题(h1–h4)、正文、引用、无序/有序列表(嵌套 1 层)、表格、
   围栏代码块(带语言标签)、行内代码、图片、分割线、加粗/斜体/删除线/链接;
2. 产物是**全内联样式**的 `<section>` 片段:无 class/id/`<style>`/`<script>`/外部 CSS;
3. 预览:浏览器打开 `article.html.preview.html`(手机宽度壳);
4. 粘贴进公众号:浏览器打开 `article.html` → 全选(Ctrl+A)复制 → 公众号编辑器粘贴;
   或用编辑器"HTML 源码"模式粘源码;
5. 图片:本地路径在公众号内无效,粘贴后先在编辑器里上传替换图片;
6. 主题:`default`(微信蓝 #576b95)/ `green` / `orange` / `red`;
   自定义:改 `gzh_article.py` 的 `THEMES` 表。

快速体验:`python $S/gzh_article.py demo --outdir <目录>` 生成全组件示例并自检。

## 四、与 artboard 流水线的关系

- 双封面走既有导出主链(WPI),`project.json` 的 `kind: "gzh-cover"`;
- Step 6 机检门禁适用于双封面 HTML(`check_overflow.py`);
- 风格上双封面可用任意设计手法手写,品类纪律(安全区/字号阶/禁则)
  见 `references/formats/gzh-cover.md`;正文排版纪律见 `references/gzh-typography.md`。

## 五、异常处理

| 现象 | 报错 | 处理 |
|---|---|---|
| 渲染引擎缺失 | `KILN_NOT_FOUND` | `python $S/setup_kiln.py` 或设 `ARTBOARD_KILN_CLI` |
| 字体目录写错 | `NO_FONTS` | 用 `fonts/` 下真实目录名;`auto` 恒可用 |
| 单张未导出就合并 | `MISSING_EXPORTS` | 先 `export --only main` / `--only sub` |
| Pillow 缺失 | `PILLOW_MISSING` | `pip install Pillow` |
| 项目已存在 | `EXISTS` | 换 slug 或 `--force` 覆盖 |
| Markdown 为空 | `EMPTY_INPUT` | 检查输入文件 |
| 兼容自检不过 | `violations` 列表 | 按提示删 class/script/外链后重转 |

所有脚本失败时仍输出单行 JSON(`ok:false` + `error`/`hint`),可被上层脚本链消费。

## 六、回滚

- 本次迭代在 `feat/wechat-dual-cover` 分支开发,合并前 main 不受影响;
- 单提交回滚:`git revert <commit>`;整批回滚:`git revert <merge-commit> -m 1`;
- 紧急恢复到迭代前:`git checkout v1.7.6 -- scripts/ SKILL.md README.md CHANGELOG.md references/ docs/`。

## 七、样例

双封面产物是三张图,落在项目的 `export/` 里,可整包上传公众号后台:
`cover-main-<slug>.png`(主)、`cover-sub-<slug>.png`(次)、`cover-merged-<slug>.png`(合并)。
正文排版产物是单文件 HTML(`--out` 指定路径),`--preview` 会另出一份手机宽度的预览页;
`demo` 子命令一键生成全组件示例,顺手跑一遍兼容性自检。

---

## 图文与封面绑定(11 迭代,2026-09-26)

- **单向绑定**:出图文(`gzh_article.py convert`)默认同时出同主题双封面三图;
  只出封面(`gzh_cover.py`)不产图文。`--no-cover` 是逃生口,用了要在交付汇报里说明。
- **标题自动**:封面主标题取 `--cover-title > --title > 文章 H1`,通常零输入。
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
