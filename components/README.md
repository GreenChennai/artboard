# components · 组件注册体系

三层渐进披露:**目录常驻、正文按需**。

| 层 | 文件 | 读取时机 | 成本 |
| :--- | :--- | :--- | :--- |
| 1 | `SKILL.md` 的"组件库"路由摘要 | 常驻 | 极低 |
| 2 | `registry/<category>/INDEX.md` | 需要某类组件时 | 每组件一行 |
| 3 | `registry/<category>/<id>.md` | 命中后 | 只读命中文件 |

入口:

- 全量扁平清单:`registry/MASTER.md`
- token 契约与默认值:`registry/TOKENS.md`
- 新增组件 SOP:`registry/PIPELINE.md`

**硬约束**:没读组件文件不许自创样式;没有索引条目的组件不算存在。
