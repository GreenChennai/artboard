# artboard-mcp(取图通道薄壳)

> 细则/安全边界/故障排查:**`references/mcp-assets.md`**(单一真相源);本 README 只管装与跑。

## 是什么

把 artboard 的取图能力(判定表 / 多源搜索 / 浏览器采集 / 下载登记 / 查重)包成
**5 个 MCP tool**,供支持 MCP 的 Agent 客户端调用。**只做入口包装,不复制实现**:

| Tool | 底层(单一真相源) |
|---|---|
| `assets_plan` | 本包 `plan.py`(materials.md §0 判定表的可执行形态) |
| `assets_search` / `assets_download` | `scripts/fetch_asset.py`(import 复用) |
| `assets_fetch_page` | `tools/asset-bridge/` 扩展 + `bridge.py` 本地服务 |
| `assets_dedupe` | `scripts/_img_probe.py` 的 pHash(import 复用) |

## 运行(无需安装,无需 mcp SDK)

```bash
# 1) 直调模式(调试/CI;与协议同一套实现)
python src/artboard_mcp/server.py tools
python src/artboard_mcp/server.py call assets_plan '{"brief":"科技产品发布 KV"}'
python src/artboard_mcp/server.py call assets_search '{"query":"coffee","limit":3}'
python src/artboard_mcp/server.py call assets_dedupe '{"dir":"materials/promo-coffee"}'

# 2) MCP 协议模式(stdio;客户端配置示例见 references/mcp-assets.md)
python src/artboard_mcp/server.py

# 3) 浏览器 Bridge 常驻服务(要用 assets_fetch_page 时才启动)
python src/artboard_mcp/bridge.py --serve
```

依赖:Python ≥3.10 + Pillow(artboard 本就要求);`mcp` SDK **不需要**
(server.py 自带 JSON-RPC 2.0 stdio 最小实现)。

## 安全(摘要;全文见 mcp-assets.md)

- **默认关闭**:`config.json` `mcp_enabled: false`,不启动任何监听;
- Bridge 只连 **127.0.0.1**,一次性 token + 显式授权(扩展 popup 点「连接」= 允许本次会话);
- 域名白名单硬编码(花瓣/iconfont/Pinterest/SVGRepo/Iconify),**绝不申请 `<all_urls>`**;
- 不落 cookie 明文、不上传任何数据、不绕过付费墙/验证码;
- 采集素材一律 `版权风险-` 前缀 + CREDITS 登记(与 `fetch_asset.py` 同一纪律)。
