# 公众号内容排版规范(gzh-typography)

> **与封面同主题(11 迭代)**:图文 `--theme` 与双封面共用唯一主题源 `scripts/_gzh_theme.py`(6 套);`convert` 默认同时出同主题三张封面,一致性机检:
> `gzh_article.py check a.html --theme-consistency --cover-html <项目>/src/index.html --theme <名>`。

> 公众号正文与普通网页 HTML 的关键差异:微信编辑器会**剥离 `<style>`/`<script>` 标签、
> class/id 属性与部分标签**,只有写在每个元素 `style` 属性里的内联样式能存活。
> 本分册是"公众号兼容 HTML"的写法规范;配套工具 `scripts/gzh_article.py`
> 把 Markdown 一键转成本规范的 HTML。来源与决策记录见 `docs/gzh-spec-summary.md`。

## 一、兼容性硬规则(违反即样式崩塌)

1. **只写内联样式**:每个元素必须带 `style` 属性;禁止 `<style>` 标签、外部 CSS、`class`、`id`。
2. **禁脚本与表单**:`<script>`、`<iframe>`、`<form>`、事件属性一律不写(编辑器直接剥离)。
3. **用 `<section>` 做容器**:公众号对 `<div>` 支持不稳,主流排版引擎(doocs/md、mdnice、135editor)统一用 `<section>` 包裹。
4. **标签白名单**:`section/p/h1-h6/span/strong/em/del/br/hr/img/a/table/thead/tbody/tr/th/td/ul/ol/li/blockquote/code/figure/figcaption`。白名单之外的标签一律不用。
5. **图片**:必须 `max-width:100%;display:block;`,居中用外层 `text-align:center`(公众号不支持 `margin:auto` 在部分场景的居中);图片仅支持公众号素材库/已上传图床的外链,本地路径无效。
6. **颜色写法**:用十六进制 `#333333`;`color-mix()/hsl(var())` 等新语法会被忽略。
7. **字体**:不指定具体字体族(公众号正文由用户端渲染),栈只到系统字体;自定义字体在正文里不可用(封面图里可以用——图是位图)。

## 二、组件样式表(gzh_article.py 内置;手写时照抄)

| 组件 | 关键内联样式(摘录) |
|---|---|
| 正文段 | `margin:24px 8px;font-size:15px;line-height:1.75;letter-spacing:0.5px;color:#333;text-align:justify;` |
| H1 | 居中 20px 加粗,上下大间距 |
| H2 | 胶囊底色块:`display:table;padding:6px 14px;margin:0 auto;background:主色;color:#fff;border-radius:6px;` |
| H3 | 左竖线:`border-left:3px solid 主色;padding-left:10px;` |
| H4 | 主色加粗 15px |
| 引用 | `border-left:3px solid 主色;background:浅底;border-radius:0 6px 6px 0;padding:12px 14px;` |
| 无序/有序列表 | 不用 `<ul>/<ol>`(样式被重置),用 `<section>` 逐项排;序号/圆点用主色 `<span>` |
| 代码块 | 外框 section(`border+radius+overflow:hidden`)+ 语言标签行 + `white-space:pre-wrap;word-break:break-all;` 正文 |
| 行内代码 | `font-family:monospace栈;font-size:87%;` |
| 表格 | `border-collapse:collapse;min-width:80%;margin:0 auto;`,表头浅底加粗 |
| 分割线 | 不用 `<hr>` 裸样式,用 `border-top:1px solid 边框色` 的空 section |
| 强调 | 加粗=主色 `strong`;斜体→主色着色(中文斜体在移动端可读性差);删除线=降灰 |
| 链接 | `color:主色;text-decoration:none;` |

## 三、阅读节奏(公众号阅读习惯)

- 正文 **15px/1.75 行高**为最稳档(14px 略挤、16px 端差异大);字间距 0.5–1px。
- 段间距 ≥ 行高感:块间 margin 24px 起步;**段落两端对齐**(`text-align:justify`)。
- 层级 ≤3 级(H2 章节标题 → H3 小节 → 加粗强调),与 artboard 出图纪律一致。
- 手机屏 375–430 逻辑像素宽:两侧留白用 `margin:24px 8px`(编辑器会再包一层)。
- 中英混排:数字/英文短语用行内代码样式或加粗突出,不混斜体。

## 四、工作流(Markdown → 公众号)

```bash
python $S/gzh_article.py convert 文章.md --out article.html \
    --title "标题" --author "署名" --theme default --preview
python $S/gzh_article.py check article.html      # 兼容性自检(应 ok:true)
```

1. 写 Markdown(标题/引用/列表/表格/代码块/分割线全支持,列表嵌套 1 层);
2. `convert` 产出**全内联样式片段**(浏览器打开 `.preview.html` 预览手机效果);
3. `check` 自检:无 class/script/外链 CSS/白名单外标签/缺内联样式的标签;
4. 粘贴:浏览器打开片段 HTML → 全选复制 → 公众号编辑器粘贴(或用编辑器"HTML 源码"模式粘源码);
5. 图片:先在公众号编辑器上传替换(本地路径会被剥除),再微调。

主题:`default`(微信蓝)/ `green` / `orange` / `red`,均为"浅底 + 一抹主色"基调,可自定义(改 THEMES 表)。

## 五、与排版工具的关系

doocs/md(20k+ star)验证了这套内联样式路线的可行性:其主题 CSS 的选择器体系
(h1-h6/p/blockquote/codespan/table/hr)与字号口径(15px 基准、代码 90%)
被本分册内联化吸收;差异点:本分册连 Markdown 转 HTML 的依赖也去掉(零依赖解析器),
列表与分割线改用 section 方案(规避编辑器对 ul/ol/hr 的样式重置)。

> **X5 边界提示(此能力不做)**:书刊级 DTP(多页流排、目录/页码/脚注、跨页绕图)不在 artboard 范围——固定画布单页产物已覆盖海报/长图/公众号场景;确需书刊级排版走专业 DTP 工具(InDesign / Affinity Publisher),本技能不实现。

## 六、异常与边界

| 情况 | 行为 |
|---|---|
| 输入文件为空/不存在 | `EMPTY_INPUT` / `INPUT_READ_FAILED`,退出码 1 |
| 未知主题 | `BAD_THEME` + 可选值列表 |
| 文章无内容块 | `EMPTY_INPUT`(只有图片/空行的文章) |
| check 发现违规 | 逐条列出(class/script/外链/裸标签),退出码 1 |
| 粘贴后样式丢失 | 按本文 §一 逐项核对;常见原因:用了 class、粘了 `<style>` 块 |

## 本册用到的脚本

| 脚本 | 何时用 | 一行示例 |
|---|---|---|
| `gzh_article.py` | Markdown→公众号 HTML | `python scripts/gzh_article.py convert a.md --out a.html` |

> 参数的权威说明在脚本自身 `--help`(不在此复制);全量索引见 `docs/scripts.md`。
