# artboard 素材分册(找图 · 抠图 · 素材纪律)

> 管线位置:**Step 4.5 素材处理**——选风格之后、写 HTML 之前。

---

## 1. 三级来源与版权策略

| 级 | 来源 | 授权 | 风险标记 |
|---|---|---|---|
| 1 | Pexels API(`ARTBOARD_PEXELS_KEY`) | 免费商用免署名,最干净 | 无 |
| 1 | Pixabay API(`ARTBOARD_PIXABAY_KEY`),`--image-type illustration/vector` 可搜插画 | 免费商用免署名(要求展示来源→CREDITS.md 履行) | 无 |
| 2 | 爬虫兜底:bing / baidu / **huaban / iconfont / pinterest**(需 Cookie,可用 `tools/cookie-extension` 浏览器插件抓取后填进 config.json 的 `*_cookie`) / **miankoutu**(免抠 PNG 聚合站,签名 API 免 Cookie) | **不确定** | **文件名自动加前缀 `版权风险-`** |

> Cookie 插件(MV3,Edge/Chrome 通用):`tools/cookie-extension/` → 浏览器「加载解压缩的扩展」→ 登录目标站 → 点插件复制片段 → 粘贴进 config.json。Cookie 只存本机。iconfont 是矢量/图标源(`--source iconfont`);huaban/pinterest/miankoutu 用 `--source` 显式指定,不进 auto 通道。
> **miankoutu 通道**:`--source miankoutu` 直搜免抠 PNG(透明底,适合产品/吉祥物贴纸),搜索免 Cookie(内置签名),下载按源站自动带 Referer;聚合源无统一授权,保留风险前缀;版权禁词会静默返回空。

> 

**风险机制(先做出来,随后再换):**
- 爬虫来源图片**默认视为版权不确定**,`fetch_asset.py` 自动加 `版权风险-` 文件名前缀 + CREDITS 标记。
- 交付汇报必须列出所有 `版权风险-` 素材并提醒用户更换;**任何环节不得删除该前缀**。

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
- 新模型不用开 `-a` matting(已是软 alpha);白底图残边靠默认后处理即可。
- 模型缓存:`~/.rembg/models/<模型>/<模型>.onnx`;技能已预取 isnet-general-use 与 isnet-anime。
  **下载坑**:本机 Python requests/pooch 走 GitHub 会 SSL 证书验证失败——模型下载改用 curl 直拉
  `https://github.com/danielgatis/rembg/releases/download/v0.0.0/<模型>.onnx` 放进对应目录即可(pooch 校验 hash 通过不重下)。
- **选图经验(实测)**:主体与背景明度差越大抠图越稳;黑杯子配暗底抠出来也没法合成进深色海报
  (主体会融进背景)——深色海报优先选亮主体或玻璃/暖色主体,或干脆用实拍原图做底不抠图。
- 中文文件名素材可直接进 `src/img/` 并在 CSS `url()` 引用(实测 WPI 静态服务无碍);`版权风险-` 前缀**不许因引用方便而改名**。

## 4. 本地插画包(零网络兜底,人物/吉祥物感)

`assets/illustrations/` 三套全 CC0/等效免署名商用:

| 包 | 风格 | 用法 |
|---|---|---|
| Open Peeps | 手绘人物,可拼装(发型/姿势/服装) | 吉祥物首选;SVG 改 `fill` 换品牌色 |
| Open Doodles | 涂鸦场景/物件 | 氛围点缀 |
| unDraw | 扁平插画,官网色即主题色 | 科技/互联网场景;SVG 改主色 hex 即全套换装 |

- 用法:直接内联 SVG 进 HTML(改 fill 为 tokens 色);或转 PNG 进 `src/img/`。
- 手账/可爱风格注意:插画人物配 [霞鹜文楷](../fonts/lxgw-wenkai/INTRO.md)/[站酷快乐体](../fonts/zcool-kuaile/INTRO.md) 才不违和。

## 5. 素材在版式里的纪律(补 guardrails)

- 真实照片必须**统一色调**再上版:冷色场景加统一滤镜,或 `fx-duotone`;多图同屏至少做到明度接近。
- 抠图产品图配 `--shadow` 软投影,禁止无投影裸贴(像贴纸假)。
- 照片做背景时压暗/降饱和后文字才能立住(对比度 ≥4.5:1)。
- 食品图选图标准:特写、暖光、有蒸汽/光泽/颗粒感——"能闻到味道"的图才配卖它。
- 一张海报最多 2 张照片;产品图(主体)+氛围图(背景)各一,再多就乱。
