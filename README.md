# artboard · HTML 海报工作室

> AI Agent Skill:用 HTML/CSS 绘制**平面设计级**图片,经 Playwright 渲染导出成品。
> 像 Illustrator/Photoshop 做的设计图,不是网页交互风,也不是 AI 生图。

| 小红书封面 | 电商大促 | 科技发布 KV |
|---|---|---|
| ![小红书封面](docs/samples/xhs-cover.png) | ![电商大促](docs/samples/ecommerce-promo.png) | ![科技KV](docs/samples/tech-kv.png) |

另有:数据长图、易拉宝、名片、三折页 —— 见 [docs/samples/](docs/samples/)。

## ✨ 特性

- **三种输入**:文案直出 / 给图复刻(高保真 OCR+VQA 复刻)/ 已有内容换风格改配色
- **开工先追问**:内置五问协议(用途→骨架、尺寸、风格、配色、素材),拒绝拿到文案就盲做
- **风格 × 品类正交**:4 种视觉风格(小红书封面 / 电商大促 / 科技 KV / 数据长图)× 6+ 介质品类(3:4、长图、banner、KV、名片、A4、三折页、易拉宝),随意组合
- **真实素材体系**:Pexels/Pixabay 授权图库 + 爬虫通道(花瓣/图标库/Pinterest,自动 `版权风险-` 标记)+ rembg 本地抠图(去残边/羽化/贴纸白边/软投影)
- **本地 VQA**:下载的图拿不准内容?离线中文问答先解读再选图
- **印刷级导出**:PNG/JPG(1–8 倍超采样)、透明底、PDF(三折页自动合双面),名片 300dpi、易拉宝 150dpi 直出
- **出图自检闭环**:渲染后自动看图检查(溢出/对比度/字体加载),修复重导,2 轮上限
- **全部离线**:字体/图表库/特效 CSS 全部本地化,断网可渲染

## 🧩 工作原理

```
五问追问 → 选风格 → 选字体 → scaffold 建项目 → [素材:抠图/搜图/VQA]
→ 按护栏写 HTML → WPI(Playwright)渲染导出 → 看图自检(≤2 轮) → 交付
```

设计自由度来自「硬护栏 + 风格分册」,不是填空模板:每风格一份
色彩角色表 + 字体栈 + 字号阶 + 组件语言 + 调性禁则,另附一个"及格线"参考案例。

## 📦 安装

1. 把整个 `artboard/` 目录放进 Agent Skill 目录(如 `.agents/skills/`),重启会话即被发现。
2. 复制 `config.example.json` → `config.json`,填入路径与 key(该文件已被 gitignore,不会提交)。
3. 可选增强:
   - `pip install "rembg[cpu]"` —— 抠图/贴纸化
   - [WPI](https://github.com/) 渲染导出后端(Playwright 驱动系统 Edge/Chrome)
   - 本地 VQA 项目(图片内容离线问答),路径填进 config.json

## ⚙️ 配置(config.json)

| 键 | 说明 |
|---|---|
| `wpi_path` | WPI 项目根目录(渲染导出引擎) |
| `studio_dir` | 海报项目落盘目录 |
| `ffmpeg` | 可选,启用 GIF 调色板优化与 MP4 |
| `pexels_key` / `pixabay_key` | 免费图库 API key([注册](https://www.pexels.com/api/) / [注册](https://pixabay.com/api/docs/)) |
| `huaban_cookie` / `iconfont_cookie` / `pinterest_cookie` | 素材站 Cookie,用 [tools/cookie-extension](tools/cookie-extension/)(MV3,Edge/Chrome 通用)一键抓取后粘贴 |
| `vqa_path` | 本地图片问答项目路径 |

优先级:环境变量 > config.json > 默认值。改完即生效。

## 🚀 快速开始(对话示例)

```
我: 给「山雾茶町」做一张 88 会员日的咖啡促销方图
AI: 五问 → 用途电商主图?尺寸默认 1080×1080?风格电商大促?配色促红?产品图你有吗?
我: 全按推荐,没产品图
AI: (Pexels 干净授权底图 + 烫金字 + 优惠券 + 爆炸贴 → 导出 2160×2160 → 看图自检 → 交付)
```

```
我: 按这张图复刻一份内容,换成我们的品牌色 #1f4e9c
AI: (视觉拆解原图 → 重建 HTML → 换 tokens → 复述确认 → 导出)
```

脚本也可独立使用:

```bash
python scripts/fetch_asset.py --query "coffee dark" --theme promo --download   # 搜图
python scripts/cutout.py product.jpg --sticker --shadow                        # 抠图
python scripts/export.py --source <项目>/src --output out.png --width 1080 --scale 2 --height 1440
```

## 🔍 素材来源与版权政策

| 层级 | 来源 | 授权 |
|---|---|---|
| 1 | Pexels / Pixabay API | 免费商用免署名,最干净 |
| 2 | 爬虫(必应/百度/花瓣/图标库/Pinterest,Cookie 经插件抓取) | **不确定** → 文件名自动加 `版权风险-` 前缀,交付时提醒更换 |

- 产品实拍图**只能用户提供**(真实产品是品牌资产,图库没有也不该编)。
- 爬虫素材的 `版权风险-` 前缀任何环节不得移除。
- 插件只在本机复制 Cookie,无任何上传;Cookie 只存 config.json(已被 gitignore)。

## 🧰 目录结构

```
artboard/
├── SKILL.md               # Agent 入口:流水线 + 铁律
├── config.example.json    # 复制为 config.json 填写
├── references/            # 护栏/追问/流水线/风格系统/特效30式/素材/导出/风格指南
│   ├── styles/            # 4 个视觉风格分册
│   └── formats/           # 名片/A4/三折页/易拉宝 品类规范
├── scripts/               # preflight/scaffold/export/cutout/fetch_asset/vqa/add_font
├── fonts/                 # 5 款开源中文字体(每款含气质简介)
├── assets/
│   ├── vendor/            # ECharts / GSAP
│   ├── icons/             # Tabler SVG 精选
│   ├── illustrations/     # Open Doodles(CC0)
│   └── cases/             # 各风格"及格线"参考案例
└── tools/cookie-extension/ # 素材站 Cookie 抓取插件(MV3)
```

## 🙏 致谢

设计方法与规则提炼自(均为思想借鉴,代码自写):
[baoyu-skills](https://github.com/JimLiu/baoyu-skills)(MIT) ·
[diagram-design](https://github.com/cathrynlavery/diagram-design)(MIT) ·
[stylekit](https://github.com/AnxForever/stylekit)(MIT,风格 schema/反 AI 味自检/原子化方法) ·
[html-anything](https://github.com/nexu-io/html-anything)(Apache-2.0) ·
[esther-design-system](https://github.com/esthersjw/esther-design-system)(CC BY-NC-SA,仅思想) ·
[Art](https://github.com/zhuxice-ctrl/Art)(仅特效原理) ·
[rembg](https://github.com/danielgatis/rembg)(MIT) ·
[Tabler Icons](https://github.com/tabler/tabler-icons)(MIT) ·
[Open Doodles](https://www.opendoodles.com/)(CC0) ·
字体:思源黑体/宋体(Noto CJK)、得意黑、霞鹜文楷、站酷快乐体(OFL/免费商用)

## License

MIT
