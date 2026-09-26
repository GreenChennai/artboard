# artboard 素材分册(判定 · 找图 · 抠图 · 素材纪律)

> 管线位置:**Step 4.5 素材处理**——选风格之后、写 HTML 之前。

---

## 0. 配图必要性判定表(P0 闸门,先判定再动手)

> **为什么**:配图不上心、默认走无图模式,与"图库糊弄产品图"是同一种懒——都不做判定。
> 本表把"要不要配图"变成**可审计的决策**:结果 + 理由写入 `project.json.image_plan`
> (可执行形态:`mcp/artboard-mcp` 的 `assets_plan`,细则见 mcp-assets.md)。

| 品类 | 是否需配图 | 谁提供 | 数量预算 | 说明 |
|---|---|---|---|---|
| 电商主图 / 食品 / 产品 | **必须** | **用户提供产品本体** + 氛围图可自取 | 1 主体 + 1 氛围 | §1 红线 |
| OOTD / 探店 / 菜品摆盘 | **必须** | **用户供图**(intake 即声明) | 1–2 | 图库糊弄不可接受 |
| 品牌 KV / 科技发布 | **建议** | 自取(氛围 / 材质 / 场景) | 0–2 | 纯排版亦可 |
| 小红书封面 / 干货卡 | **视风格** | 自取或纯排版 | 0–2 | 手账 / 贴纸风可零图 |
| 数据长图 / 报告 | **不需要** | — | 0 | 图表为主 |
| 名片 / 三折页 / 易拉宝 | **视品类** | 自取或用户 | 0–2 | 印刷慎用低清图(300dpi 见 dpi-check) |
| 公众号双封面 | **建议** | 自取 | 0–1 | 信息流缩略图靠主体 |
| 电影 / 活动海报 | **建议** | 自取(氛围) | 0–1 | 主体可用排版承担 |
| 视频动效件(片头/尾/章节/转场) | **不需要** | — | 0 | 以排版/几何为主(video-motion.md) |

**判定纪律(硬)**:

1. 判定结果 + 理由写入 `project.json.image_plan`:
   `{need_images, reason, level, budget, must_ask, action_taken, query}`;
2. **`required`/`recommended` 且 `must_ask=false` → 不问即主动检索**(不等用户点出来;
   这就是"主动取图"与旧习惯的区别);
3. **`required` 且属产品本体 / 人像 / 品牌 → `must_ask=true`,先问**(§1 红线不放松);
4. 判定 `not_needed` → 不检索,交付时**说明理由**(不给"省事"留口子);
5. 用户可显式覆盖(要图/不要图),覆盖原因一并写进 `image_plan`。

**数量预算(硬上限)**:单次检索 ≤50 条;单次下载 ≤20 张(Read 挑 1–2 张上版);
上版照片 ≤2 张(§5);Bridge 采集 ≤5 页/次(mcp-assets.md §4)。

---

## 1. 三级来源与版权策略

| 级 | 来源 | 授权 | 风险标记 |
|---|---|---|---|
| 1 | Pexels API(`ARTBOARD_PEXELS_KEY`) | 免费商用免署名,最干净 | 无 |
| 1 | Pixabay API(`ARTBOARD_PIXABAY_KEY`),`--image-type illustration/vector` 可搜插画 | 免费商用免署名(要求展示来源→CREDITS.md 履行) | 无 |
| 2 | 爬虫兜底:bing / baidu / **huaban / iconfont / pinterest**(需 Cookie:装 `tools/asset-bridge` 扩展后由 MCP **自动抓写**——`assets_cookie` tool,或 `python -m artboard_mcp cookie --site iconfont`;也可在扩展 popup 手动抓) / **miankoutu**(免抠 PNG 聚合站,签名 API 免 Cookie) | **不确定** | **文件名自动加前缀 `版权风险-`** |
| 2.5 | **Bridge 素材站**(asset_hunt 多站编排,0927 迭代):**vector4free**(免费矢量,S3 预览图页内取;授权逐条各异→前缀)/ **svgrepo**(30 万 SVG,Cloudflare 盾→页内 fetch;多数 CC0→前缀)/ **gahag**(日系照片+矢量,**明示 Public Domain**→无前缀但 ACworks 条款自查;**日文关键词命中更高**) | 题材 Iconify/API 覆盖不了时;一条命令:`python scripts/asset_hunt.py --query <词> --theme <主题> --sites svgrepo,gahag,…` | 按站点(见 asset_hunt.SITES) |

> Cookie 插件(MV3,Edge/Chrome 通用;旧 cookie-extension 已删除,由 asset-bridge 全面替代):`tools/asset-bridge/` →「加载解压缩的扩展」→ 登录目标站 → Cookie 抓取走 MCP 自动写 config.json,无需手动粘贴。Cookie 只存本机。iconfont 是矢量/图标源(`--source iconfont`);huaban/pinterest/miankoutu 用 `--source` 显式指定,不进 auto 通道。
> **miankoutu 通道**:`--source miankoutu` 直搜免抠 PNG(透明底,适合产品/吉祥物贴纸),搜索免 Cookie(内置签名),下载按源站自动带 Referer;聚合源无统一授权,保留风险前缀;版权禁词会静默返回空。

> 

**风险机制(先做出来,随后再换):**
- 爬虫来源图片**默认视为版权不确定**,`fetch_asset.py` 自动加 `版权风险-` 文件名前缀 + CREDITS 标记。
- 交付汇报必须列出所有 `版权风险-` 素材并提醒用户更换;**任何环节不得删除该前缀**。

**代理开关(0927 迭代):`proxy_enabled` 默认**关**——所有下载/安装脚本直连;国内网络需要时把开关设 true 并填 proxy(preflight 会报告状态)。代理唯一出口:`_config.proxy_active()`。**

**纪律红线:**
1. **产品实拍图只能用户提供**——图库没有"你的产品",自动编造既不真实也不合规;图库/爬虫只补氛围、场景、背景。
2. 人像照片避免选可辨认面孔(肖像权);必选时在交付提醒中注明。
3. Unsplash API 因强制 hotlink/署名/审查条款不进管线;StockSnap/Burst 无 API 不用。

## 2. fetch_asset.py 速查

```bash
S="<skill>/scripts"
# 自动档:pexels → pixabay → 爬虫补位(key 已配用户级环境变量)
python $S/fetch_asset.py --query "coffee cup dark background" --theme promo-coffee --download --limit 6
# 指定来源 / 竖图 / 插画
python $S/fetch_asset.py --query "咖啡拉花特写" --source pexels --orientation portrait --download
python $S/fetch_asset.py --query "mascot cute" --source pixabay --image-type illustration --download
```
- 输出单行 JSON:`downloaded[]` 含 file/source/license/author/risk。
- 落盘:`<studio>/materials/<theme>/`,同目录自动维护 `CREDITS.md`(文件|来源|作者|授权|来源页|日期)。
- 选图流程:先 `--download` 拿候选 → **Read 看图挑 1–2 张** → 复制进项目 `src/img/`(重命名为语义名,保留 CREDITS 记录)。
- **视觉识别优先级**:Agent 自身视觉是**首选**(config `vision_mode: auto` 默认);
  仅当 ①Agent 无视觉能力 ②用户明说用本地模型 ③config 设 `vision_mode: local` 时,
  才强制走本地 VQA/OCR。
- **图片内容拿不准**(不知拍的是什么、有没有水印/商标/不合适元素)→ 用 VQA 解读:
  `python scripts/vqa.py <图片> --prompt "描述主体,有没有水印、logo 或不适元素?"`(本地 QORA 中文问答,离线 CPU;详见脚本头)。

## 3. cutout.py 速查(抠图 + 四件套后处理)

```bash
S="<skill>/scripts"
# 产品图/食品照(默认 isnet-general-use,CPU 1-2 秒)
python $S/cutout.py src/img/product.jpg --sticker --shadow
# 卡通/吉祥物(边缘更干净)
python $S/cutout.py mascot.png --model isnet-anime --sticker --trim
# 高质量(慢;嫌慢先 pip install onnxruntime-directml 再加 --dml)
python $S/cutout.py hero.jpg --quality high --dml
```
- 后处理四件套:去白底残边(1px 腐蚀+羽化,默认开)/ 贴纸白描边(`--sticker`)/ 软投影(`--shadow`)/ 透明边裁切(`--trim`)。
- **模型红线:`bria-rmbg`(rembg 新版默认)商用需付费协议,脚本层硬拒绝**;允许模型白名单见脚本头注释。
- **抠图后调色**:透明件不做全图 tone(image-language §七);需要色调用 `pixel.py <调整> --mask alpha` 局部应用(references/pixel-pipeline.md)。
- 新模型不用开 `-a` matting(已是软 alpha);白底图残边靠默认后处理即可。
- 模型缓存:`~/.rembg/models/<模型>/<模型>.onnx`;技能已预取 isnet-general-use 与 isnet-anime。
  **下载坑**:本机 Python requests/pooch 走 GitHub 会 SSL 证书验证失败——模型下载改用 curl 直拉
  `https://github.com/danielgatis/rembg/releases/download/v0.0.0/<模型>.onnx` 放进对应目录即可(pooch 校验 hash 通过不重下)。
- **选图经验(实测)**:主体与背景明度差越大抠图越稳;黑杯子配暗底抠出来也没法合成进深色海报
  (主体会融进背景)——深色海报优先选亮主体或玻璃/暖色主体,或干脆用实拍原图做底不抠图。
- 中文文件名素材可直接进 `src/img/` 并在 CSS `url()` 引用(实测 WPI 静态服务无碍);`版权风险-` 前缀**不许因引用方便而改名**。

## 4. 本地插画包与矢量素材源(状态以磁盘为准,2026-09 核对)

> **本节只说真话**:`assets/illustrations/` 目前**只有一套已落地**(open-doodles 31 个 SVG)。
> 其余两套是"可获取",不是"已有"——别把预留当库存用。

| 包 | 磁盘状态 | 获取方式 | 许可 |
|---|---|---|---|
| **Open Doodles** | ✅ **已落地**(`open-doodles/`,31 SVG) | 直接用 | CC0 |
| Open Peeps | ⬜ 需人工获取 | [openpeeps.com](https://openpeeps.com) → Download(zip)→ 解压到 `assets/illustrations/open-peeps/`;官网表单下载无直链,自动化不稳定 | CC0 |
| unDraw | ⬜ 需人工获取 | [undraw.co](https://undraw.co) 逐张下载 SVG(可先在官网设主题色);批量接口 2026-09 实测 405 | 自定义开放许可(免署名商用,禁转售插画本身) |
| illustrations.co | ❌ 未接入 | 许可待核,核清前不取用 | 待核 |
| **Iconify 图标** | ✅ 可脚本获取(30 万+,按需 + 离线缓存) | `scripts/fetch_svg.py iconify --set tabler --query <词>`;许可**逐集不同**,白名单与清单见 `docs/svg-licenses.md` | 逐集(多数 MIT/Apache/CC0) |

- 用法:直接内联 SVG 进 HTML(改 fill 为 tokens 色);或转 PNG 进 `src/img/`。
- **自绘前先查素材源**:`fetch_svg.py`(图标)→ 本地插画包 → 最后才是现画;
  现画走 `vector-drawing.md §4.3` 构成七步 + §4.7 质量门(`check_svg.py`)。
- 插画混源禁令:同屏插画必须同一形状语言(vector-drawing.md §4.3)。
- 手账/可爱风格注意:插画人物配 [霞鹜文楷](../fonts/lxgw-wenkai/INTRO.md)/[站酷快乐体](../fonts/zcool-kuaile/INTRO.md) 才不违和。

## 5. 素材在版式里的纪律(补 guardrails)

- 真实照片必须**统一色调**再上版:冷色场景加统一滤镜,或 `fx-duotone`;多图同屏至少做到明度接近。
- 抠图产品图配 `--shadow` 软投影,禁止无投影裸贴(像贴纸假)。
- 照片做背景时压暗/降饱和后文字才能立住(对比度 ≥4.5:1)。
- 食品图选图标准:特写、暖光、有蒸汽/光泽/颗粒感——"能闻到味道"的图才配卖它。
- 一张海报最多 2 张照片;产品图(主体)+氛围图(背景)各一,再多就乱。
- 图像角色与处理链(先定"这张当主体还是背景"再处理,处理顺序模型)见 `image-language.md`。

## 本册用到的脚本

| 脚本 | 何时用 | 一行示例 |
|---|---|---|
| `fetch_asset.py` | 图库/爬虫搜图下载 | `python scripts/fetch_asset.py --query "coffee" --theme t --download` |
| `cutout.py` | 抠图+四件套 | `python scripts/cutout.py product.jpg --sticker --shadow` |
| `vqa.py` | 本地图片问答(内容拿不准) | `python scripts/vqa.py <图> --prompt "描述主体"` |
| `fetch_model.py` | VQA 模型下载 | `python scripts/fetch_model.py` |
| `check_credits.py` | 素材版权对账 | `python scripts/check_credits.py <项目>/src/img` |
| `asset_hunt.py` | 全自动多站搜素材(开页→筛→下→去重→关页) | `python scripts/asset_hunt.py --query "咖啡" --theme t --limit 8` |

> 参数的权威说明在脚本自身 `--help`(不在此复制);全量索引见 `docs/scripts.md`。
