# artboard 部署指南(小白版,照着点就行)

> 本页解决三件事:①装好运行环境 ②拿到图库 Key ③填对配置文件。
> 全程约 10 分钟,只需做一次。**推荐直接用图形配置器**(见第 4 步),不用手改 JSON。

---

## 第 1 步 · 放置 Skill

把整个 `artboard/` 文件夹放进你的 Agent 技能目录,例如:

```
C:\Users\你\.agents\skills\artboard\
```

重启你的 AI 编程工具(Claude Code / Codex 等)后,对话里说「做一张海报」即可触发。

## 第 2 步 · 创建你的配置文件

进入 `artboard\` 文件夹,把 **`config.example.json` 复制一份**,重命名为 **`config.json`**。

> ⚠️ `config.example.json` 是模板,`config.json` 是真正生效的配置(已设为不上传,密钥安全)。

不用手改 JSON——下一步用图形界面填。

## 第 3 步 · 拿两把免费图库 Key(各 5 分钟)

### Pexels(主图源,质量最好)

1. 打开 [pexels.com/zh-cn](https://www.pexels.com/zh-cn/) → 右上角**注册**
   (可用邮箱或 Google 账号)。
2. **验证邮箱**:收件箱里点验证链接。
3. 登录后补一下基础信息(用户名、头像,随便设)。
4. 回到主页,把鼠标悬停到**右上角的「…」(三个点)**,点 **「图片和视频 API」**。
5. 选择「作为个人使用/团队」,填写:
   - 名称:随便起(如 `artboard`)
   - 使用说明:一句话(如 `个人设计海报生成工具`)
6. 提交后页面直接显示 **Your API Key**——复制那串字符。

### Pixabay(副图源,插画多)

1. 打开 [pixabay.com](https://pixabay.com/) → **注册 → 验证邮箱 → 完善基础信息**。
2. 打开 [pixabay.com/api/docs/](https://pixabay.com/api/docs/)。
3. 往下翻,找到 **「key」→「Your API key」**,后面的字符串就是 Key,复制。

> 两把 Key 都是免费、可商用的。**不要把 Key 发到公开场合**(截图前打码)。

## 第 4 步 · 填配置(图形界面)

双击运行 `tools\config-editor\artboard-config-editor.exe`
(没有这个文件?见下方「命令行方式」)。

逐项填写:

| 配置项 | 填什么 | 必填? |
|---|---|---|
| WPI 渲染引擎路径 | 见第 5 步(可一键部署) | ✅ |
| 作品落盘目录 | 海报保存位置,如 `E:\artboard-studio` | ✅ |
| Pexels API Key | 第 3 步复制的 Key | 推荐 |
| Pixabay API Key | 第 3 步复制的 Key | 推荐 |
| FFmpeg 路径 | 见第 5 步(可一键部署) | 用 MP4 才需要 |
| 花瓣/图标库/Pinterest Cookie | 用 `tools\cookie-extension` 浏览器插件抓取(见仓库内说明) | 可选 |
| 本地代理 | 访问 Pinterest 等境外源时填,如 `http://127.0.0.1:7890` | 可选 |
| 视觉识别模式 | 保持 `auto`(Agent 自带视觉优先) | 保持默认 |
| 本地 VQA / OCR 路径 | 跑 `scripts\fetch_model.py vqa`(或 `ocr`)自动下载部署 | 可选 |

点**保存**。配置即改即生效,不用重启。

> **命令行方式**(不想用 GUI):直接用记事本编辑 `config.json`,
> 每行格式是 `"键名": "值",`——逗号、引号一个都不能少,改完可跑
> `python -c "import json;json.load(open('config.json',encoding='utf-8'))"` 验证。

## 第 5 步 · 一键部署运行环境(在 `artboard\scripts\` 下打开命令行)

```bat
:: WPI 渲染引擎(GitHub 自动下载 + 装依赖)
python setup_wpi.py

:: FFmpeg(可选:GIF 高质量 + MP4 视频)
python setup_ffmpeg.py

:: 本地 VQA 模型(可选:离线看图问答,约 600MB)
python fetch_model.py vqa

:: 本地 OCR 模型(可选:离线文字识别,约 110MB)
python fetch_model.py ocr
```

## 第 6 步 · 体检

```bat
python scripts\preflight.py
```

会打印**环境自检报告**:就绪几项、待补几项、每项怎么补,以及你的环境能做什么
(静态海报 / GIF / MP4 / 抠图 / 图库…)。全部 ✓ 即可开工。

## 常见问题

| 现象 | 处理 |
|---|---|
| 技能不被识别 | 确认放对目录 + 重启 AI 工具;文件夹名必须是 `artboard` |
| 找图只有爬虫结果 | Pexels/Pixabay Key 没填或填错,重看第 3 步 |
| 字体缺失提示 | `python scripts\fetch_font.py` 查看并按需下载 |
| MP4 导出失败 | FFmpeg 未部署,跑 `python scripts\setup_ffmpeg.py` |
| 改了 config 不生效 | 检查 JSON 是否合法(少逗号最常见),或改用 GUI 编辑器 |
