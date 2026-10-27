# 组件主清单(扁平索引)

> **第三落点**:类目 INDEX 无命中时才读本文件。这里只给 ID + 标题 + 类目,不含用途细节 ——
> 命中后仍然回该类目读 `INDEX.md` 拿加载条件,再读 `<id>.md` 正文。
> 新增组件必须同时更新:本文件 + 类目 `INDEX.md` + 组件文件的 `id`/`category`。

| 组件 ID | 标题 | 类目 |
| :--- | :--- | :--- |
| `layout.poster-vertical` | 竖版海报基础画布 | 版式 |
| `layout.editorial-split` | 图文分栏 | 版式 |
| `layout.center-hero` | 居中主视觉 + 底部信息锚 | 版式 |
| `typography.hero-cjk-title` | 超大中文标题 | 文字 |
| `typography.bilingual-stack` | 中英双语层级 | 文字 |
| `typography.number-display` | 数字主视觉 | 文字 |
| `ornament.seal-stamp` | 印章 | 装饰 |
| `ornament.neon-scanline` | 霓虹描边 + 扫描线 | 装饰 |
| `ornament.glass-panel` | 玻璃拟态面板 | 装饰 |
| `ornament.paper-grain` | 纸张纹理底 | 装饰 |
| `data-display.stat-block` | 统计块 | 数据 |
| `data-display.metric-row` | 指标行 | 数据 |
| `data-display.label-group` | 标签组 | 数据 |
| `feedback.badge` | 徽章 / 角标 | 状态与反馈 |
| `feedback.tag` | 关键词标签 | 状态与反馈 |
| `feedback.alert-strip` | 提示条 / 公告条 | 状态与反馈 |
| `style-preset.new-chinese` | 新中式预设 | 风格预设 |
| `style-preset.cyber` | 赛博科技预设 | 风格预设 |
| `style-preset.glass` | 玻璃拟态预设 | 风格预设 |
| `style-preset.minimal` | 极简预设 | 风格预设 |
| `style-preset.retro-pixel` | 复古像素预设 | 风格预设 |
| `style-preset.y2k` | Y2K 预设 | 风格预设 |
| `style-preset.neumorphism` | 新拟态预设 | 风格预设 |

## 盘点口径

- 总数 23;新增/下线后本表行数与 `find components/registry -name '*.md' | wc -l` 的对应关系见 `components/registry/PIPELINE.md` Step 4。
- 只有组件文件、没有索引条目 = 不存在;只有索引条目、没有组件文件 = 坏链接,二者都算未接入完成。
