# 审片台(review station)· 交付后逐帧审阅

> **它补的是 artboard 流水线的最后一段**:Step 7 交付之后。动效/视频卡出片后,
> 不再是"丢一个 mp4 给用户",而是给一个**能拖时间轴逐帧看、能像 F12 一样拾取元素、
> 能把意见落盘成文件**的本地网页工具。
>
> 来源:MV 审片台资产包(`world.execute(me);` 的 33 轮返修工程),按 artboard 布局重写。
> 通用铁律与"意见文件即 Agent 接口"的用法见 `references/review-loop.md`。

---

## 一、怎么跑

```bash
# ① 启动器(在项目根跑;自动算好 URL 并开浏览器)
python <skill>/tools/review-station/review_station.py --root <项目>
python <skill>/tools/review-station/review_station.py --root <项目> --port 9000 --no-open
python <skill>/tools/review-station/review_station.py --stop          # 收掉实例

# ② 服务端本体(CI/脚本友好;--no-open 不开浏览器)
python <skill>/tools/review-station/review_server.py --root <项目> --port 8860 --no-open
```

页面地址:`http://127.0.0.1:8860/__rv/review.html`

- **必须用 `http://` 打开**(页面里的保存走 fetch;`file://` 会命中 CORS,全部保存失败);
- 改前端后 **`Ctrl+Shift+R` 强刷**——服务端对所有响应发 `Cache-Control: no-store`;
- 依赖:**服务端纯标准库**;只有"取帧 / 裁片段"需要 ffmpeg(与其余脚本同口径:
  `config.json` 的 `ffmpeg` / `ARTBOARD_FFMPEG` / PATH);页面端需要 playwright 的浏览器跑吗?
  **不需要** —— 浏览器就是用户自己的。

---

## 二、项目布局(全部可用参数覆盖)

```
<项目>/                        ← --root(默认当前目录)
├─ src/…                      ← 影片/动效本体(scaffold 产出的项目;或任意含影片页的目录)
├─ export/*.mp4               ← 成片:对照 / 取帧 / 裁片段的唯一数据源
└─ review/                    ← 运行期(--work-dir;默认 <root>/review)
   ├─ 审片意见.json            ← ★ 给 Agent 读的接口
   ├─ 字幕轨.json
   ├─ 审片台配置.json
   ├─ 字幕导出/*.srt
   ├─ _shot/*.png              ← 取帧缓存
   └─ 片段/*.mp4               ← 裁出来的问题片段
```

`--audio` / `--mp4` / `--fps` / `--title` 可显式指定;音频与成片默认**自动探测**,
探测不到只提示不阻断(逐帧审片不依赖它们)。

---

## 三、HTTP 契约(11 个 action)

单端点:`?action=<name>`,GET 读 / POST 写。JSON 一律 `{ok:...}`。

| action | 方法 | 作用 | 落盘 |
|---|---|---|---|
| `ping` | GET | 健康探测(页面的离线队列靠它判断服务是否恢复) | — |
| `meta` | GET | 片名 / 时长 / 帧率 / **探测到的音频与成片 URL** / 页面路径 | — |
| `refs` | GET | 可作对照的成片列表(`export/*.mp4`) | — |
| `shot` | GET | `&t=<秒>` 从成片取一帧(PNG) | `review/_shot/` |
| `subfiles` | GET | 工程里的字幕候选(`.srt/.vtt/.ass/.ssa`) | — |
| `subs` | GET/POST | 读/写字幕轨 | `review/字幕轨.json` |
| `srt` | POST | 导出字幕(**按片长裁剪**:截尾 / 丢弃片外条目) | `review/字幕导出/*.srt` |
| `config` | GET/POST | 读/写界面设置 | `review/审片台配置.json` |
| `notes` | GET/POST | 读/写审片意见 | `review/审片意见.json` |
| `render` | POST | 把 `[t0,t1]` **从成片裁成 mp4**(后台任务) | `review/片段/` |
| `job` | GET | `&id=` 查后台任务进度 | — |

写入一律**原子替换**(唯一临时名 + `os.replace`),坏 JSON 当空不白屏。

---

## 四、功能一览

| 区 | 能力 |
|---|---|
| 顶栏 | 片名 / 状态芯片(资源自检、ms/帧、配置落盘) / 成片对照 / 传送带 |
| 画面 | 播放 / 逐帧 / 循环 / 倍速 / 缩放;`←→` 步进 1s,`Ctrl+←→` 步进 1 帧 |
| 时间轴 | 主刻度 + 平移滑条 + `Alt+滚轮` 缩放轨道(10~600 倍);字幕块头尾**磁力吸附** |
| 右栏 6 页签 | 段落 / 歌词 / 字幕 / 元素 / 标记 / 性能 / 工具 |
| 元素页 | `Ctrl+Shift+C` 进检查模式,鼠标移动实时高亮 + tooltip,点击选中即写意见(带画布坐标) |
| 字幕页 | 逐条**行内编辑**:`Enter` 拆句、行首 `Backspace` 并入上句、`Ctrl+Z` 撤销、双语轨切换 |
| 标记页 | 段落区间标记,意见一键导出 Markdown |
| 离线兜底 | 服务断开时保存进队列,每 2.5s 探活自动补写 |

常用键位:`空格` 播放/暂停 · `←/→` ±1s · `Shift+←/→` ±1 帧(看"逐帧"用 `Ctrl+←/→`)·
`Ctrl+Shift+C` 检查模式 · `P` 抓元素 · `Home/End` 片头/片尾 · `Alt+滚轮` 轨道缩放 · `双击空白` 复位。

---

## 五、与来源工程的差异(移植必改 6 处,已全部改完)

| # | 来源工程 | 本版 | 为什么 |
|---|---|---|---|
| 1 | `ROOT = 上两级(__file__)` | **`--root`**(默认 cwd) | artboard 项目由 `scaffold.py` 生成,深度不固定 |
| 2 | 硬编码 `Mili.mp3` | `meta` 探测 + 前端注入 `<audio src>` | 每个项目音频名不同;没有音频不算错 |
| 3 | 5 个落盘路径写死 `06_成片输出/…` | 全部到 `--work-dir`(默认 `<root>/review`) | 不污染项目结构,可整目录删 |
| 4 | 前端写死字幕探测顺序 `.zh.srt→.zh.vtt→…` | 统一走 `subfiles`,前端列真实文件列表 | 写死顺序在别的项目上必然失效 |
| 5 | `--stop` 只有 Windows 分支 | 补 POSIX(`pgrep -f`) | 跨平台可用 |
| 6 | `shot` / `render` 转调工程自带 `render.py` | **基于成片的 ffmpeg 取帧 / 裁片段** | artboard 没有"按时间区间渲染"的渲染器;而"对照成片"本来就只需对成片操作 |

另外两处结构性改动:`/__rv/*` **双挂载**(工具与工程不同树);accept 队列 5→128
(页面并发拉十几张帧图,默认队列溢出会报 `ERR_CONNECTION_REFUSED`)。

**与原版的功能性差别(诚实标注)**:原版 `render` 是"重新渲染该段"并轮询渲染日志进度;
本版是**从成片裁一段**(进度按 ffmpeg `-progress` 算)。要"真重渲",跑 `export.py` 全片重导。

---

## 六、已知限制

1. **字体缺失就退系统字体**:影片自带 webfont 才会完全还原;缺字体只影响观感(尤其 ASCII 网格场景),不影响功能;
2. **取帧 / 裁片段需要 ffmpeg 与成片**:没有成片时"成片对照"页签为空、`shot` 返回 `NO_MP4`(会给出提示);
   逐帧审阅本身**不依赖成片**——页面直接 `SEEK(t)` 驱动动效;
3. **成片裁片段不重新渲染**:画面与成片逐字节一致,但不会反映"改代码后的新画面"(那是 export 的事);
4. **意见/字幕/配置是 JSON 文件**,不是数据库:多人同时编辑同一份会互相覆盖(单人工作流够用);
5. 点位的语义(段落/歌词/标记)沿用来源工程的影片数据模型;换成别的项目时,
   右栏"段落/歌词"页签的数据源由影片自己的模块提供,缺了就只有字幕/标记可用。

---

## 本册用到的脚本

| 脚本 | 何时用 | 一行示例 |
|---|---|---|
| `review_station.py` | 起审片台(交付后逐帧审阅) | `python tools/review-station/review_station.py --root <项目>` |
| `review_server.py` | 只起服务(CI/无浏览器) | `python tools/review-station/review_server.py --root <项目> --no-open` |

> 验收与联调记录见 `references/review-loop.md §六`;意见文件的字段结构见该册 §二。
