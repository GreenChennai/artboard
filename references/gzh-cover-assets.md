# 双封面素材层(v1.27):AI 出插画 → 自动抠图 → 按版式落位

> 一句话:背景层解决「氛围」,素材层解决「有一个看得见的东西」。
> 背景图铺满整幅、素材是主体物件;两者可同时存在,但都在文字之下。

## 1. 什么时候用素材层(而不是背景图)

| 需求 | 用哪个 | 命令 |
| --- | --- | --- |
| 整幅要有照片/氛围底 | 背景层 | `bg-prompt` + `bg-attach` |
| 画面里要出现一个具体物件(信封、咖啡杯、产品) | **素材层** | `asset-prompt` + `asset-attach` |
| 要一层低对比纹理铺底 | 素材层 pattern | `asset-attach --mode pattern` |
| 照片要抠人/抠产品 | 不属于本链路 | `scripts/cutout.py`(rembg,非全自动) |

核心判据:**主体有清晰轮廓、要落在某个版式区域**,走素材层;**只是气氛**,走背景层。

## 2. 全自动链路(四步,逐步可失败可解释)

```bash
# 0 有项目(已有封面项目就跳过)
python scripts/gzh_cover.py new my-cover --title 秋日来信 --layout band-editorial --theme ink --fx none

# 1 出提示词(带项目时读主题色/版式,写 asset-prompt.txt)
python scripts/gzh_cover.py asset-prompt my-cover --subject "a folded paper letter" \
        --style "flat vector illustration with subtle grain"

# 2 把 prompts.illustration 交给生图工具 → 存 1024×1024 PNG

# 3 抠图 + 落位 + 内联(一步完成:cutout → trim → contain → data URI)
python scripts/gzh_cover.py asset-attach my-cover --image ~/Downloads/asset.png --mode cutout

# 4 验收 + 导出
python scripts/gzh_cover.py check my-cover && python scripts/gzh_cover.py export my-cover
```

`asset-attach` 一条命令做四件事:抠图 → 去留白 → 按版式槽位等比装入 → 生成 data URI 并内联进
`src/index.html` 与 `src/sub.html`(各自按自己的画布尺寸算 CSS)。

## 3. 生图契约(为什么提示词里写死了这些)

抠图是**纯 PIL 的「平底 + 边界连通」**,不联网、不下模型、结果确定。它成立的唯一前提是:

1. **纯色平底**(`#FFFFFF`),无渐变、无纸纹、无地面阴影 → 否则边框色散 > 30 直接报 `ASSET_BG_NOT_FLAT`;
2. **主体不触边**,四周留 ≥8% 白边 → 否则主体被当成底色吃掉,报 `ASSET_SUBJECT_LOST`;
3. **单元素**,不拼贴、不加边框 → 多物件时抠图会连成一片;
4. **无文字/水印/LOGO** → 抠进来的字会变成脏点。

`asset-prompt` 生成的提示词已固化这四条;换主体只改 `--subject`,换画风只改 `--style`。

## 4. 槽位表(按版式给位置,不是让 AI 随便摆)

槽位坐标 = 封面画布像素(主封 900×383,次条 383×383),与 `check` 的几何断言同一坐标系。

| 版式 | 主封默认 | 主封可选 | 次条默认 |
| --- | --- | --- | --- |
| center-band | `whole`(整幅 0.16 水印) | `top`(820×80) `bottom`(820×39) | `whole` |
| band-editorial | `right`(164×367,右侧栏) | `whole` | `whole` |
| stack-cards | `right`(240×343) | `left`(240×343) `whole` | `whole` |
| giant-caps | `whole` | `whole`(巨字横跨整幅,没有实体空地) | `whole` |
| kraft-note | `left`(240×327 便签旁) | `right`(272×240) `whole` | `whole` |
| plate-page | `plate`(228×383 画页栏) | `whole` | `plate`(123×383) |

- `whole` = 铺满画布的**氛围层**,默认 `opacity 0.16`,允许与文字重叠(z-index 0);
  它的不透明度**上限 0.25**:传更大的值会被压到 0.25 并在 `placements.opacity_capped` 标记,
  因为满幅素材压过 25% 文字就读不出来了(`asset-whole-dim` 断言);
- 其它槽位 = **实体位**,默认 `opacity 1.0`,必须让开文字安全区(重叠 ≤2%,由 `asset-text-safe` 断言);
- `--scale 0.8` 在槽位内再缩;`--slot xxx` 显式指定;
- **槽位回退**:某槽位只属于主封(如 `plate` 之外的个体位),次条没有时**不报错**,
  次条改用其默认槽位并在 `placements[...].fallback = true` 标记;
  只有该槽位在整套版式里都不存在才报 `BAD_ASSET_SLOT`(带回 `available` 与 `by_page`);
- **写盘是原子的**:`asset-attach` 先把两页的槽位/不透明度全部算完并校验,
  全部通过才写 HTML。中途失败不会留下「主封改了、次条没改」的半成品项目。

## 5. 三种模式

| `--mode` | 做什么 | 用于 |
| --- | --- | --- |
| `cutout`(默认) | 平底抠图 + 去留白 | 插画、单个物件 |
| `rect` | 整张矩形贴入(不抠) | 已经是透明 PNG、或需要方形块面 |
| `pattern` | 缩到 `--tile`(默认 320px)后平铺,槽位固定 `whole`,默认 `opacity 0.18` | 无缝图案纹理 |

## 6. 失败码与处置

| error | 含义 | 处置 |
| --- | --- | --- |
| `ASSET_BG_NOT_FLAT` | 边框色散 >30,不是平底图 | 让生图工具出纯白底,或 `--mode rect` |
| `ASSET_SUBJECT_LOST` | 主体 <8%,被当底色吃掉 | 要求四周留白重出,或 `--mode rect` |
| `ASSET_DECODE_FAILED` | 图不可解码 | 换 PNG/JPEG/WebP |
| `ASSET_TOO_LARGE` | 降采样到 560 宽仍超 2.6MB | 先生成小一点的图 |
| `ASSET_LIMIT` | 一页已有 2 个素材 | 删一个再挂(第三个就是噪音) |
| `BAD_ASSET_SLOT` | 该版式没有这个槽位(整套版式都不存在) | 按 `available` / `by_page` 选 |

## 7. check 新增断言(硬门,不过不交付)

| id | 断言 |
| --- | --- |
| `asset-budget` | 一页 ≤2 个素材层 |
| `asset-offline` | 所有素材 src 必须是 `data:image/`(离线导出不丢图) |
| `asset-cutout-real` | 解码 data URI,透明像素 ≥5%(证明真的抠了,不是把白底图直接贴) |
| `asset-text-safe` | 非 `whole` 槽位与文字安全区重叠 ≤2% |
| `asset-whole-dim` | `whole` 满幅层 opacity ≤0.25(手改 HTML 也会被拦) |
| `asset-below-text` | 素材规则 z-index ≤ 0(永远在文字之下) |

## 8. 与背景层同用

```bash
python scripts/gzh_cover.py bg-attach   my-cover --image bg.jpg     # 氛围底
python scripts/gzh_cover.py asset-attach my-cover --image obj.png --mode cutout   # 主体物
```

顺序无所谓;背景层是 `.ab-bg-layer`(带横向 scrim),素材层是 `.ab-asset[data-asset=N]`,
两者都 `z-index:0`、都在信息层之前。**素材层是叠在背景层之上的第二个 0 层,不是背景的一部分**。

## 9. 与主题的配合

素材配色取自 `scripts/_gzh_theme.py`(主题唯一真相源),`asset-prompt` 自动把 `bg/ink/accent`
写进提示词,所以生图工具出的插画天然与封面同色系。**换主题后要重跑 `asset-prompt` 再重出图**,
否则素材与封面撞色。