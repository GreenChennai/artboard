"""artboard-mcp · stdio 服务(轻量 JSON-RPC 2.0,不依赖 mcp SDK;可选装亦可)。

Tools ×5(mcp-assets.md §工具契约):
  assets_plan        判定要不要配图(plan.py 判定表)
  assets_search      多源搜索(sources.py → fetch_asset.py)
  assets_fetch_page  经浏览器 Bridge 采集当前页/画板(bridge.py)
  assets_download    下载落盘 + CREDITS 登记(sources.py → fetch_asset.py)
  assets_dedupe      pHash 查重(dedupe.py → _img_probe.py)

传输:stdin/stdout 每行一条 JSON-RPC 2.0;支持 initialize / tools/list / tools/call / ping。
直调(调试/CI,不走协议):python server.py call <tool> '<json-args>' —— 同一套实现。
所有返回为单行 JSON;失败路径也吐 JSON(exit 1)。
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bridge  # noqa: E402
import dedupe as dedupe_mod  # noqa: E402
import plan as plan_mod  # noqa: E402
import sources  # noqa: E402

SERVER_INFO = {"name": "artboard-mcp", "version": "0.1.0"}

TOOLS = [
    {"name": "assets_plan",
     "description": "判定任务要不要配图(materials.md §0 判定表);结果写入 project.json.image_plan",
     "inputSchema": {"type": "object",
                     "properties": {"brief": {"type": "string"}, "category": {"type": "string"},
                                    "style": {"type": "string"},
                                    "need": {"type": "string", "enum": ["", "yes", "no"]}},
                     "required": ["brief"]}},
    {"name": "assets_search",
     "description": "多源图片搜索(默认干净 API 优先);每项必带 source/license/risk",
     "inputSchema": {"type": "object",
                     "properties": {"query": {"type": "string"},
                                    "sources": {"type": "array", "items": {"type": "string"}},
                                    "orientation": {"type": "string"},
                                    "limit": {"type": "integer", "maximum": 50},
                                    "image_type": {"type": "string"}},
                     "required": ["query"]}},
    {"name": "assets_fetch_page",
     "description": "经浏览器素材 Bridge 采集当前页/画板(仅白名单域名,需扩展显式授权连接;"
                    "返回项强制 risk=true,默认过滤 <120px 小图标)",
     "inputSchema": {"type": "object",
                     "properties": {"url": {"type": "string"}, "scroll": {"type": "boolean"},
                                    "pages": {"type": "integer", "maximum": 5},
                                    "limit": {"type": "integer", "maximum": 50},
                                    "min_px": {"type": "integer",
                                               "description": "最小宽高 px,默认 120;0=不过滤"}}}},
    {"name": "assets_download",
     "description": "下载候选落盘到 <studio>/materials/<theme>/ 并登记 CREDITS(≤20 张/次)",
     "inputSchema": {"type": "object",
                     "properties": {"items": {"type": "array"}, "theme": {"type": "string"}},
                     "required": ["theme"]}},
    {"name": "assets_cookie",
     "description": "自动抓取白名单站点的登录 Cookie 并写入本机 config.json 对应 *_cookie 键"
                    "(取代手动抓取;Cookie 仅 localhost 传输、只落本机)",
     "inputSchema": {"type": "object",
                     "properties": {"site": {"type": "string",
                                             "enum": ["huaban", "iconfont", "pinterest"]}},
                     "required": ["site"]}},
    {"name": "assets_dedupe",
     "description": "pHash 查重(汉明距离 ≤ threshold 视为同图;只报告不删图)",
     "inputSchema": {"type": "object",
                     "properties": {"dir": {"type": "string"}, "files": {"type": "array"},
                                    "threshold": {"type": "integer"}},
                     "description": "dir 与 files 二选一"}},
]


def call_tool(name: str, args: dict) -> dict:
    if name == "assets_plan":
        return {"ok": True, **plan_mod.plan(args.get("brief", ""),
                                            args.get("category", ""),
                                            args.get("style", ""),
                                            args.get("need", ""))}
    if name == "assets_search":
        return sources.search(args.get("query", ""), args.get("sources"),
                              args.get("orientation", ""), min(int(args.get("limit", 6)), 50),
                              args.get("image_type", "photo"))
    if name == "assets_fetch_page":
        out = bridge.fetch_page(url=args.get("url", ""),
                                scroll=bool(args.get("scroll", True)),
                                limit=min(int(args.get("limit", 50)), 50),
                                pages=int(args.get("pages", 1)))
        # Bridge 采集 = 登录态站点,授权一律不确定:强制 risk(安全纪律 6,不得绕过)。
        # 注意:fetch_page 透传扩展应答(无 ok 键),只要带 items 就必须后处理。
        if "items" in out:
            min_px = int(args.get("min_px", 120))  # 过滤站点图标/按钮(可用 0 关闭)
            fixed = []
            for it in out.get("items", []):
                it["risk"] = True
                it["source"] = it.get("source") or "bridge"
                it["page_url"] = it.get("page_url") or it.get("link") or ""
                # 缩略图→原图升级(已知 CDN;与 fetch_asset 的 pinterest 736x→originals 同模式):
                # 花瓣 gd-hbimg* 的 _fw240webp/_sq75webp 是 Resize 标记,剥掉即原图
                # (2026-09-27 实测:auth_key 不锁 Resize;原图 130KB vs 缩略 11KB)
                u = it.get("url") or ""
                upgraded = False
                if "gd-hbimg" in u and "huaban.com" in u:
                    it["url"] = re.sub(r"_(?:fw|sq)\d+webp", "", u)
                    if it.get("thumbnail"):
                        it["thumbnail"] = re.sub(r"_(?:fw|sq)\d+webp", "", it["thumbnail"])
                    upgraded = True  # 花瓣缩略图天生小(sq75 头像/fw240 卡片),尺寸过滤不适用
                w, h = int(it.get("w") or 0), int(it.get("h") or 0)
                if (not upgraded) and min_px > 0 and (w or h) and (w < min_px or h < min_px):
                    continue
                fixed.append(it)
            out["items"] = fixed[: int(args.get("limit", 50))]
            out["ok"] = bool(out["items"]) or out.get("error") is None
            out["filtered_small"] = f"(已过滤 <{min_px}px 小图标)" if min_px > 0 else None
        return out
    if name == "assets_download":
        return sources.download(args.get("items") or [], args.get("theme", ""))
    if name == "assets_cookie":
        r = bridge.fetch_cookie(args.get("site", ""))
        if r.get("ok"):
            key = args.get("site", "") + "_cookie"
            w = _write_config_key(key, r["cookie"])
            r["written_to"] = w if w else None
            r["hint"] = f"{key} 已更新;fetch_asset 的 {site_key_note(args.get('site', ''))} 通道即刻可用"
        return r
    if name == "assets_dedupe":
        target = args.get("dir") or args.get("files") or []
        return dedupe_mod.dedupe(target, int(args.get("threshold", 6)))
    return {"ok": False, "error": "UNKNOWN_TOOL", "hint": f"可用:{[t['name'] for t in TOOLS]}"}


COOKIE_SITES = {"huaban": "花瓣登录态(huaban_cookie)", "iconfont": "图标库接口(iconfont_cookie)",
                "pinterest": "Pinterest 抓取(pinterest_cookie)"}


def site_key_note(site: str) -> str:
    return COOKIE_SITES.get(site, site)


def _write_config_key(key: str, value: str) -> str:
    """合并写 skill config.json 单键(文件本就 gitignored;Cookie 只落本机)。"""
    skill = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))))
    path = os.path.join(skill, "config.json")
    data = {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:  # noqa: BLE001 — 无 config 则新建
        data = {}
    data[key] = value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write(chr(10))
    return path


# ---------------- JSON-RPC 2.0(stdio,每行一条) ----------------

def handle(msg: dict) -> dict | None:
    method = msg.get("method", "")
    mid = msg.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid,
                "result": {"protocolVersion": msg.get("params", {}).get(
                    "protocolVersion", "2024-11-05"),
                    "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params", {})
        out = call_tool(params.get("name", ""), params.get("arguments") or {})
        if not out.get("ok", True) and mid is not None:
            return {"jsonrpc": "2.0", "id": mid,
                    "result": {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}],
                               "isError": True}}
        return {"jsonrpc": "2.0", "id": mid,
                "result": {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}]}}
    if method.startswith("notifications/"):
        return None  # 通知不回包
    if mid is not None:
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"method 未知: {method}"}}
    return None


def serve_stdio() -> int:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            print(json.dumps({"jsonrpc": "2.0", "id": None,
                              "error": {"code": -32700, "message": "JSON 解析失败"}}),
                  flush=True)
            continue
        resp = handle(msg)
        if resp is not None:
            print(json.dumps(resp, ensure_ascii=False), flush=True)
    return 0


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:  # 无参 = stdio 协议模式
        return serve_stdio()
    if argv[0] == "call":  # 直调:call <tool> <json-args>
        try:
            out = call_tool(argv[1], json.loads(argv[2] if len(argv) > 2 else "{}"))
        except IndexError:
            print(json.dumps({"ok": False, "error": "USAGE",
                              "hint": 'call <tool> <json-args>'}, ensure_ascii=False))
            return 2
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out.get("ok", True) else 1
    if argv[0] == "tools":
        print(json.dumps({"ok": True, "tools": [t["name"] for t in TOOLS]}, ensure_ascii=False))
        return 0
    print(json.dumps({"ok": False, "error": "USAGE",
                      "hint": "无参=stdio 协议;call <tool> <json>;tools"}, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
