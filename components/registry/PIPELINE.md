# 组件接入流水线(SOP)

> 每新增一个组件或一种风格,按本文件走一遍。目的是让组件库**可重复地**变好,
> 而不是靠一次性堆砌。任何一步跳过都算未接入完成。

## Step 1 · 判定缺口与来源

1. 先查 `components/registry/MASTER.md` 与对应类目 `INDEX.md`。
2. 已有组件能覆盖 **80%** 需求时,**扩展已有组件**(加变体/token),不新增平行副本。
3. 确认是缺口后,从下列来源提取**视觉规则**,不是复制组件代码:

| 方向 | 来源库 | 取什么 |
| :--- | :--- | :--- |
| 新中式 | `you-want/han-design` · `shuimo-design/shuimo-ui` | 主题 token、印章/卷轴语义、墨色层级 |
| 赛博科技 | `sebyx07/cybercore-css` | glitch/scanline/neon 的静态配方,不引入交互动画 |
| 玻璃拟态 | `xvhuan/frostglass` · `mianbeishiwole/Liquid-Glass-Vue` | `backdrop-filter` 数值与半透明层逻辑 |
| 复古/像素/新拟态 | `lumpenspace/puxel` · `nregret/Neumorphism-UI` | 硬偏移阴影、像素边框、内外阴影数值 |
| 极简 | `JassinAlSafe/NothingCN` · `nolly-studio/cult-ui` | 颜色 token、字体栈对比、克制基线 |
| 兜底 | `uiverse-io/galaxy` | 按关键词淘单个 CSS 效果 |

> **已移除**:`shader-effects-inc/shaders`。接入后效果不理想,不再作为视觉源,
> 新组件**禁止**引用它;既有引用按 `README.md` 的"已移除"口径清理并标 deprecated。

## Step 2 · 适配 Artboard 约束(四项过滤器)

1. **静态优先**:默认态即完整视觉;hover/click 改写为静态变体,只有导出 GIF 时才追加最小 keyframes。
2. **文字锐利不可妥协**:模糊、像素化、glitch 只作用于背景/装饰层;文字层保持清晰渲染。
3. **token 化**:新值进 `--ab-*` 命名空间,先登记进 `TOKENS.md`,不写死原始值。
4. **单文件自包含**:纹理优先纯 CSS(重复渐变/mask/data URI),字体只用系统栈或单行 `<link>`。

## Step 3 · 注册与挂载

1. 组件落 `components/registry/<category>/<id>.md`,frontmatter 填齐
   `id / category / styles / tokens / sources / status`。
2. 同步三处,缺一不可:
   - 类目 `INDEX.md`:一行 `ID / 用途 / 加载条件`(用途与加载条件用**任务语言**);
   - `MASTER.md`:一行 `ID / 标题 / 类目`;
   - 若带来新 token:`TOKENS.md` 登记(含默认值与分组表)。
3. **只加组件文件不更新索引 = 组件不存在。** 反向的索引坏链接同样 fail。

## Step 4 · 回归验证

1. 用同一个 Brief 出"接入前/接入后"两版,确认组件被真实加载且视觉有可辨识提升。
2. 主入口常驻 token 增量检查:`SKILL.md` 的"组件库"路由摘要每次迭代**增长 ≤ 3 行**;
   超了说明你在索引层写了正文,搬去类目 INDEX 或组件文件。
3. 一致性机检(零 token):

```bash
python scripts/check_component_registry.py            # 索引/正文/frontmatter/链接/行数
python scripts/check_slop.py <proj>/src               # 用了组件的项目照常过 AI 味门禁
git diff --check
```

## Step 5 · 记录来源

组件 frontmatter 的 `sources` 指向真实参考库;同步更新 `README.md` 的
"开源组件与视觉来源"表(状态只允许 `使用中` / `备用` / `已移除`)。
不一致时以 registry 为准,修正 README。

## 组件文件模板

```markdown
---
id: category.slug
category: layout | typography | ornament | data-display | feedback | style-presets
styles: [新中式, 赛博, 玻璃拟态, 极简]
tokens: [--ab-canvas-ratio, --ab-gutter]
sources: []            # 视觉规则来源;自研留空
status: stable         # stable | beta | deprecated
---

## 结构
可直接贴进单文件 HTML 的结构片段。

## 核心 CSS
带 token 引用的 CSS,不写死颜色/间距。

## Token 依赖
- `--ab-xxx`:作用

## 禁忌
- 明确不能做的事
```

> 组件正文超过 100 行时,顶部加目录或拆分;单文件仍应能独立粘贴使用。
