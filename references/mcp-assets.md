# artboard 取图通道:MCP 与浏览器素材 Bridge

> 管线位置:Step 4.5 素材处理的"主动取图"执行层。**本册是 MCP/Bridge 的唯一真相源**;
> 来源与版权纪律的真相源仍是 `materials.md`(本册不重复其红线,只引用)。
> 与 `fetch_asset.py` 的关系(ADR-AB-E03):MCP 只是**薄壳**,搜索/下载逻辑经 import 复用
> `fetch_asset.py`,不建第二实现;判定表真相在 `materials.md §0`,可执行形态在
> `mcp/artboard-mcp/src/artboard_mcp/plan.py`。

---

## 1. 何时用哪个通道

| 场景 | 通道 |
|---|---|
| Agent 直接干活(默认) | `fetch_asset.py`(materials.md §2 速查)+ `materials.md §0` 判定 |
| Agent 客户端支持 MCP,想统一工具面 | `artboard-mcp` 五 tool |
| 要取**登录态站点**(花瓣画板 / Pinterest / iconfont / SVGRepo / Iconify) | **素材 Bridge**(浏览器扩展 + 本地服务) |

> 范围边界(X5):只做 artboard 需要的 **5 个 tool + 1 个 Bridge**,不做通用爬虫框架。
> 判定优先级不变:**先判定(`assets_plan` / materials §0)→ 再选通道**;
> 产品本体 / 人物肖像 / 品牌资产无论哪个通道都**必须用户提供**(materials.md 红线)。

## 2. artboard-mcp(MCP 服务)

**形态**:本地 stdio(默认),轻量 JSON-RPC 2.0,**不依赖 mcp SDK**;安装/直调见
`mcp/artboard-mcp/README.md`。MCP 客户端配置示例:

```json
{ "mcpServers": { "artboard": {
    "command": "python",
    "args": ["<skill>/mcp/artboard-mcp/src/artboard_mcp/server.py"] } } }
```

### 工具契约(5 个;单行 JSON;失败路径也吐 JSON)

| Tool | 入参 → 出参 | 备注 |
|---|---|---|
| `assets_plan` | `{brief, category?, style?, need?}` → `{need_images, level, reason, budget, must_ask, suggested_queries[], category}` | 判定结果**写入 `project.json.image_plan`** 再动工;`need:"yes"/"no"` 是用户显式覆盖,必须留痕 |
| `assets_search` | `{query, sources?, orientation?, limit≤50, image_type?}` → `{items[{id,title,url,thumbnail,width,height,author,source,license,risk}]}` | 默认干净 API 优先;每项**必带 source/license**;风险项 `risk:true` |
| `assets_fetch_page` | `{url?, scroll, pages≤5, limit≤50, min_px=120}` → `{items[{url,thumb,w,h,link,risk:true,page_url}]}` | **需要 Bridge 会话**(§3);非白名单域名在扩展侧拒绝;返回项**强制 `risk:true`**(登录态采集授权不确定,自动带「版权风险-」前缀);默认过滤 <120px 小图标(`min_px:0` 关闭) |
| `assets_download` | `{items[], theme}` → `{files[], credits, risk_files[], errors[]}` | 落盘 `<studio>/materials/<theme>/` + CREDITS 自动登记;**≤20 张/次** |
| `assets_dedupe` | `{dir \| files, threshold≤6}` → `{dups[[a,b,dist]], kept[]}` | pHash 汉明距离;只报告不删图 |
| `assets_cookie` | `{site: huaban|iconfont|pinterest}` → 自动抓该站 Cookie **并合并写进 config.json** 对应 `*_cookie` 键 | 取代手动抓取;Cookie 仅走 localhost、只落本机(0927 迭代 D7) |

**纪律**:判定为 required/recommended 且 `must_ask=false` → **立即主动检索**,
不等用户点出来;`not_needed` → 不检索,交付时说明理由;`must_ask=true` → 先问用户。

## 3. 素材 Bridge(浏览器扩展,`tools/asset-bridge/`)

**升级自旧插件 cookie-extension(已删除)**:Cookie 抓取与"导出本页素材 JSON"(clipboard 旧通道,现由本扩展 popup 承接)
**原样保留**;新增**被本机服务调用**的滚动/分页采集。

```
浏览器扩展 --WS--> bridge.py 常驻服务(127.0.0.1:随机端口) <--WS-- server.py(assets_fetch_page)
```

**使用步骤**:

```bash
# ① 启动常驻服务(打印端口/token,并写 .bridge-session.json 供 MCP 连接)
cd <skill>/mcp/artboard-mcp/src && python -m artboard_mcp.bridge --serve
# ② 浏览器装扩展:tools/asset-bridge →「加载解压缩的扩展」
# ③ 打开目标站(登录态),点扩展 popup,填端口+token,点「连接本机会话」
# ④ Agent/MCP 调 assets_fetch_page → 扩展在当前页滚动采集并回传
```

### 安全纪律(硬,逐条验收;违反任一条 = 关停重审)

1. 本地服务**只监听 `127.0.0.1`**,端口默认随机(`bridge_port:0`);
2. **一次性会话 token**(`bridge_token_ttl` 默认 900 秒过期),写进
   `mcp/artboard-mcp/.bridge-session.json`(仅本机;服务重启即刷新);
3. **域名白名单**(manifest `host_permissions` 与 background `ALLOWED` 双保险):
   花瓣 / iconfont / Pinterest / SVGRepo / Iconify;**绝不申请 `<all_urls>`**;
4. **显式授权**:popup 点「连接本机会话」= 允许**本次会话**采集;默认拒绝,未连接时
   `assets_fetch_page` 返回 `BRIDGE_NOT_CONNECTED/BRIDGE_NOT_STARTED`(不静默);
5. **不落 cookie 明文**(Bridge 不读写 cookie;抓 Cookie 是旧通道的独立按钮,结果只进剪贴板);
   **不上传任何数据**到外部;不绕过付费墙/验证码;
6. 采集素材一律 `版权风险-` 前缀 + CREDITS 登记(`fetch_asset.py`/`sources.py` 统一处理);
   **不得移除前缀**;
7. **生命周期(06-N)**:重启 `bridge.py` 即换端口+token(轮换);删除
   `.bridge-session.json` = 一键作废当前会话;采集数据只落本机素材库,无云侧副本;
8. 插件与 MCP **默认不启用**(`mcp_enabled:false` 不启动本地服务);预检
   (`preflight.py`)会报告通道状态。

### 通信协议(一帧一条 JSON)

```
双方 → {type:"hello", token, role:"extension"|"client"} → {type:"ready"}
client → {type:"collect", url?, scroll, pages, limit}
client → {type:"open", url, scroll, pages, limit, automations?}
                                      开后台标签→等加载→(DOM 自动化)→采集
client → {type:"close_tab", tabIds:[]}          收尾关闭本轮页面(D10)
client → {type:"cookie", url}                   抓 Cookie(白名单站)
extension → {type:"items", items:[{url, thumb, w, h, link, tabId?}]}
extension → {type:"cookies", url, count, cookie} | {type:"closed", closed}
client → {type:"download", urls:[...]}   extension → {type:"downloaded", results:[...]}

automations 例(花瓣去水印,来源侧规避):
  [{"trigger":"素材范围","option":"不看素材"}]
  扩展在 ant-dropdown-trigger 找触发文本并点选项;失败如实回传 failed,不重试轰炸。
```

## 4. 数量预算(硬上限)

| 项 | 上限 |
|---|---|
| 单次检索返回 | ≤ 50 条 |
| 单次下载落盘 | ≤ 20 张(再 Read 挑 1–2 张上版) |
| 单张海报上版照片 | ≤ 2 张(materials.md 既有纪律) |
| Bridge 单次采集页数 | ≤ 5 页 |

## 5. 与查重 / 版权复核的衔接

```bash
python scripts/imageops.py dedupe "<素材目录>" --threshold 6   # 近重复(多来源采集后必跑)
python scripts/check_credits.py "<项目>/src/img"               # CREDITS 对账 + 待更换清单
```

交付汇报直接引用 `check_credits.py` 的 `risk_files` / `unregistered` 字段,不手抄。

## 5.5 专用素材浏览器 + 全自动搜索(asset_hunt;0927 迭代)

```bash
# 一次性绑定(可见窗口):启动专用 Chrome/Edge(独立 profile,装 asset-bridge)
# → 窗口里登录花瓣 → 扩展 popup 填端口/token(命令输出里有)→ 点「连接」;此后永久有效
python scripts/asset_hunt.py --query x --theme x --ensure-browser --visible

# 日常:一条命令全自动(默认 --headless=new 后台,不抢用户浏览器)
python scripts/asset_hunt.py --query "咖啡 拉花" --theme promo-coffee --limit 8     [--transparent] [--orientation portrait|landscape] [--color "#2f6fed"]     [--strict] [--sites huaban,svgrepo,pexels,pixabay]
```

- 狩猎 hub:**固定端口 8811 + 固定长效 token**(config `bridge_hunt_token`,首次自动生成)
  → 扩展凭据永久有效,配合 alarms 自愈 = **绑定一次,登录常态化**(D9);
- 采集后自动:原图升级(剥后缀→详情页兜底)→ 筛选(透明/横竖/主色,默认降级留痕)→
  pHash 查重 → **关闭本轮全部标签页**(保留浏览器与登录态)→ 单行 JSON 报告;
- 批次站点:花瓣 / SVGRepo / Pexels·Pixabay(API,授权干净);unDraw 网络不可达自动跳过;
  **付费站不做**(版权不可商用)。

## 6. 故障排查

| 症状 | 处置 |
|---|---|
| `assets_fetch_page` 报 `BRIDGE_NOT_STARTED` | 没起 `bridge.py --serve`;先起服务再连扩展 |
| 报 `BRIDGE_NOT_CONNECTED` | 扩展没点「连接本机会话」(或 token 过期);重新授权 |
| 报 `BRIDGE_AUTH` | token 不匹配/过期:服务重启会刷新,重跑 `--serve` 并重填 |
| 报 `域名不在白名单` | 该站未进白名单:**不要**自行加域;走 `fetch_asset.py` 已有来源 |
| `assets_search` 全空 | 未配 `pexels_key/pixabay_key`,仅剩爬虫;或关键词太偏,换英文短词 |
| 扩展装不上 | MV3 需 Edge/Chrome 开发者模式;`chrome://extensions` 看具体报错 |

> **实测结论(2026-09-27,真机)**:①白名单拦截真实生效(非白名单域名在扩展侧被拒);
> ②采集/下载/CREDITS 全链可用;③**MV3 SW 闲置 ~30s 被杀 → WS 断连**确证(v2.0.0 实测),
> v2.0.1 起扩展带 alarms 自愈:断开后 ≤1 分钟用保存的凭据静默重连(凭据仅存本机
> chrome.storage.local);重载扩展后 SW 冷启动也会自动恢复会话,一般无需重开 popup。
> 临时手动恢复:重开扩展 popup 点「连接本机会话」。

## 本册用到的脚本

| 脚本 | 何时用 | 一行示例 |
|---|---|---|
| `fetch_asset.py` | 搜索/下载的底层实现(MCP 薄壳复用) | `python scripts/fetch_asset.py --query q --theme t` |
| `check_credits.py` | 采集后版权对账 | `python scripts/check_credits.py <项目>/src/img` |

> 参数的权威说明在脚本自身 `--help`(不在此复制);全量索引见 `docs/scripts.md`。
