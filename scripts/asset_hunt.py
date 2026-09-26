"""artboard 全自动素材搜索(asset_hunt):一条命令 = 开页→搜词→筛→下→去重→关页→JSON 报告。

为什么存在(0927 迭代 D8):此前 Agent 搜素材要"开浏览器→点扩展→采集→挑图→下载"
多轮往返烧 token;本脚本把全流程收进**一次调用**,Agent 只读最终单行 JSON 报告。

架构(ADR 见桌面《artboard-Bridge素材搜索迭代-20260927》§2):
  本脚本 ⇄ 狩猎 hub(固定端口 8811 + 固定长效 token,绑定常态化)
            ⇅ 专用素材浏览器(独立 profile;首次可见登录,日常 --headless=new;装 asset-bridge 扩展)
  站点批次:花瓣(DOM 自动化勾"素材范围=不看素材")+ SVGRepo(Bridge);
            Pexels/Pixabay(API,授权干净);unDraw 网络不可达自动跳过(诚实报告)

用法:
  python asset_hunt.py --query "咖啡 拉花" --theme promo-coffee2 --limit 8
  python asset_hunt.py --query "上传 下载" --transparent --orientation portrait --color "#2f6fed"
  python asset_hunt.py --query "促销 背景" --strict          # 筛空不降级,exit 1
  python asset_hunt.py --ensure-browser --visible            # 首次绑定:可见窗口登录+扩展填一次

输出:stdout 单行 JSON(ok/query/sites/files/risk_files/filtered/degraded/tabs_closed/…)。
退出码 0=成功 / 1=失败(含 EMPTY_AFTER_FILTER)/ 2=需要绑定等人工步骤。
纪律:产品本体/人像/品牌必问的红线不在本脚本职责内(intake 层管);Bridge 采集一律
`版权风险-` 前缀;Cookie 仅走 localhost,从不上传。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(SCRIPTS)
MCP_PKG = os.path.join(SKILL, "mcp", "artboard-mcp", "src", "artboard_mcp")
EXT_DIR = os.path.join(SKILL, "tools", "asset-bridge")
sys.path.insert(0, MCP_PKG)
sys.path.insert(0, SCRIPTS)

HUNT_PORT = 8811
HUNT_TOKEN_KEY = "bridge_hunt_token"
PROFILE_KEY = "bridge_browser_profile"


def cfg(key: str, default: str = "") -> str:
    try:
        from _config import cfg as _cfg
        return _cfg(key, default) or default
    except Exception:  # noqa: BLE001
        return default


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def fail(code: str, detail: str, hint: str = "") -> int:
    emit({"ok": False, "error": code, "detail": detail, "hint": hint})
    return 2 if code in ("BINDING_REQUIRED", "USAGE") else 1


def studio_dir() -> str:
    d = cfg("studio_dir")
    return d or os.path.join(os.path.dirname(SKILL), "artboard-studio")


# ---------------- hub / 浏览器管理(D9 绑定常态化;D1 混合可见/无头) ----------------

def hub_token() -> str:
    """固定长效 token:存 config.json,首次自动生成(绑定一次,永久有效)。"""
    tok = cfg(HUNT_TOKEN_KEY)
    if tok:
        return tok
    import secrets
    tok = secrets.token_urlsafe(24)
    _write_config(HUNT_TOKEN_KEY, tok)
    return tok


def _write_config(key: str, value) -> None:
    """合并写 config.json 的单个键(不动其他键;该文件本就 gitignored)。"""
    path = os.path.join(SKILL, "config.json")
    data = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data[key] = value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _hub_alive(token: str) -> bool:
    try:
        from bridge import BridgeClient
        cli = BridgeClient(HUNT_PORT, token)
        ready = cli.handshake(role="client")
        cli.close()
        return ready.get("type") == "ready"
    except Exception:  # noqa: BLE001
        return False


def ensure_hub(token: str) -> None:
    """狩猎 hub 不在则拉起常驻进程(detached;浏览器比脚本活得久也仍能连)。"""
    if _hub_alive(token):
        return
    bridge_py = os.path.join(MCP_PKG, "bridge.py")
    log = open(os.path.join(studio_dir(), "bridge-hunt.log"), "ab")
    subprocess.Popen(
        [sys.executable, bridge_py, "--port", str(HUNT_PORT), "--token", token,
         "--token-ttl", "0", "--json"],
        stdout=log, stderr=log,
        creationflags=(0x00000008 | 0x00000200) if os.name == "nt" else 0)  # DETACHED|NEW_GROUP
    for _ in range(40):
        time.sleep(0.4)
        if _hub_alive(token):
            return


def _find_browser_exe() -> str | None:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates += [os.path.join(local, r"Google\Chrome\Application\chrome.exe"),
                       os.path.join(local, r"Microsoft\Edge\Application\msedge.exe")]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def ensure_browser(token: str, visible: bool = False) -> tuple[bool, list[str]]:
    """确保专用浏览器在位。返回 (connected, notes)。"""
    from bridge import BridgeClient
    notes: list[str] = []
    if _ext_alive(token):
        return True, notes
    exe = _find_browser_exe()
    if not exe:
        return False, ["未找到 Chrome/Edge,请安装或把路径加入 PATH"]
    profile = cfg(PROFILE_KEY) or os.path.join(studio_dir(), "bridge-browser")
    os.makedirs(profile, exist_ok=True)
    base = [exe, f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--window-size=1280,900",
            f"--disable-extensions-except={EXT_DIR}", f"--load-extension={EXT_DIR}"]
    head = [] if visible else ["--headless=new"]
    subprocess.Popen(base + head + ["about:blank"],
                     creationflags=(0x00000008) if os.name == "nt" else 0)
    for i in range(60):  # ≤30s 等扩展连上
        time.sleep(0.5)
        if _ext_alive(token):
            if head:
                notes.append("headless=new 启动成功")
            return True, notes
        if i == 14 and not visible:  # 无头 7s 未连 → 可见重试一次(降级)
            notes.append("headless 扩展未连,降级可见窗口重试")
            subprocess.Popen(base + ["about:blank"],
                             creationflags=(0x00000008) if os.name == "nt" else 0)
    return _ext_alive(token), notes


def _ext_alive(token: str) -> bool:
    """扩展在位探测:发一次 open about:blank 的轻量等价物不可行 → 用 hub 状态文件不可得;
    改为:让扩展回应一次 cookie 探测(白名单内 URL,不产生页面)。"""
    try:
        from bridge import BridgeClient
        cli = BridgeClient(HUNT_PORT, token)
        if cli.handshake(role="client").get("type") != "ready":
            cli.close()
            return False
        out = cli.call({"type": "cookie", "url": "https://huaban.com/"}, timeout=10)
        cli.close()
        return out.get("type") == "cookies"
    except Exception:  # noqa: BLE001
        return False


# ---------------- 站点编排(D2 批次) ----------------

def site_urls(site: str, kw: str) -> dict:
    if site == "huaban":
        return {"url": "https://huaban.com/search?q=" + urllib.parse.quote(kw),
                "automations": [{"trigger": "素材范围", "option": "不看素材"}],
                "pages": 2, "min_px": 200}
    if site == "svgrepo":
        return {"url": f"https://www.svgrepo.com/vectors/{urllib.parse.quote(kw)}/",
                "pages": 1, "min_px": 64}
    return {}


def hunt_site(site: str, kw: str, limit: int, client_timeout: float = 90) -> dict:
    """经 Bridge 开页采集单站。返回 items/automations/tabId/error。"""
    from bridge import BridgeClient, read_session
    cfg_s = site_urls(site, kw)
    if not cfg_s:
        return {"collected": 0, "error": f"未知站点 {site}"}
    info = {"port": HUNT_PORT, "token": hub_token()}
    cli = BridgeClient(info["port"], info["token"])
    ready = cli.handshake(role="client")
    if ready.get("type") != "ready":
        cli.close()
        return {"collected": 0, "error": "hub 握手失败"}
    out = cli.call({"type": "open", "url": cfg_s["url"],
                    "scroll": True, "pages": cfg_s["pages"],
                    "limit": limit, "automations": cfg_s.get("automations"),
                    "min_px": cfg_s["min_px"]}, timeout=client_timeout)
    cli.close()
    if out.get("type") != "items" and "items" not in out:
        return {"collected": 0, "error": out.get("error") or out.get("hint") or "无应答"}
    # 与 server.assets_fetch_page 同口径:风险强制 + link 接通 + 花瓣原图升级
    import re as _re
    fixed = []
    for it in out.get("items", []):
        it["risk"] = True
        it["source"] = f"bridge-{site}"
        it["page_url"] = it.get("page_url") or it.get("link") or ""
        u = it.get("url") or ""
        if "gd-hbimg" in u and "huaban.com" in u:
            it["url"] = _re.sub(r"_(?:fw|sq)\d+webp", "", u)
        fixed.append(it)
    return {"collected": len(fixed), "items": fixed,
            "tabId": out.get("tabId"),
            "source_filter": (out.get("automations") or {}).get("applied") or [],
            "source_filter_failed": (out.get("automations") or {}).get("failed") or [],
            "error": out.get("error")}


# ---------------- 下载 / 筛选 / 去重(D3 原图兜底;D4 筛选降级) ----------------

def download_items(items: list[dict], theme: str) -> dict:
    import sources
    return sources.download(items, theme)


def detail_fallback(failed_items: list[dict], theme: str, budget: int) -> tuple[list[dict], list[int]]:
    """原图兜底(D3):剥后缀/下载失败的,开详情页采大图再下(每张 2–4s;预算内)。
    返回 (files, 打开过的 tabIds——由主流程统一关闭)。"""
    got: list[dict] = []
    tabs: list[int] = []
    seen: set[str] = set()
    for it in failed_items[:budget]:
        page = it.get("page_url") or ""
        if "huaban.com/pins" not in page or page in seen:
            continue
        seen.add(page)
        try:
            from bridge import BridgeClient
            cli = BridgeClient(HUNT_PORT, hub_token())
            cli.handshake(role="client")
            out = cli.call({"type": "open", "url": page, "scroll": False,
                            "pages": 1, "limit": 6, "min_px": 200}, timeout=60)
            cli.close()
            if out.get("tabId") is not None:
                tabs.append(out["tabId"])
            cands = [i for i in out.get("items", [])
                     if (i.get("w") or 0) * (i.get("h") or 0) > 0]
            if not cands:
                continue
            best = max(cands, key=lambda i: (i.get("w") or 0) * (i.get("h") or 0))
            best["risk"] = True
            best["page_url"] = page
            r = download_items([best], theme)
            got.extend(r.get("files", []))
        except Exception:  # noqa: BLE001 — 单张兜底失败不断全局
            continue
    return got, tabs


def _load_rgb(path: str):
    from PIL import Image
    with Image.open(path) as im:
        return im.convert("RGB"), (im.mode in ("RGBA", "LA") and bool(
            Image.open(path).getchannel("A").getextrema()[0] < 250))


def apply_filters(theme_dir: str, files: list[str], transparent: bool,
                  orientation: str, color: str, color_tol: int) -> dict:
    """对已下载文件做硬筛(透明/横竖/主色)。返回 {kept, filtered:{原因:[文件]}}。"""
    kept, dropped = [], {"transparent": [], "orientation": [], "color": []}
    for f in files:
        p = os.path.join(theme_dir, f)
        try:
            _rgb, has_alpha = _load_rgb(p)
            w, h = _rgb.size
        except Exception:  # noqa: BLE001 — 坏图直接淘汰
            dropped["transparent"].append(f)
            continue
        if transparent and not has_alpha:
            dropped["transparent"].append(f)
            continue
        if orientation == "landscape" and w <= h:
            dropped["orientation"].append(f)
            continue
        if orientation == "portrait" and h <= w:
            dropped["orientation"].append(f)
            continue
        if color:
            from _px_core import hex_to_rgb  # noqa: PLC0415
            tr = hex_to_rgb(color)
            small = _rgb.resize((8, 8))
            px = list(small.getdata())
            mean = tuple(sum(c[i] for c in px) / len(px) for i in range(3))
            dist = sum((mean[i] - tr[i]) ** 2 for i in range(3)) ** 0.5
            if dist > color_tol:
                dropped["color"].append(f)
                continue
        kept.append(f)
    return {"kept": kept, "filtered": dropped}


RELAX_LADDER = [("color", "放宽主色筛选"), ("transparent", "放宽透明要求"), ("orientation", "放宽横竖要求")]


# ---------------- 主流程 ----------------

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="全自动素材搜索(开页→搜→筛→下→去重→关页;0927 迭代)")
    ap.add_argument("--query", required=True, help="搜索关键词(多词空格分隔)")
    ap.add_argument("--theme", required=True, help="素材库主题目录名")
    ap.add_argument("--sites", default="huaban,svgrepo,pexels,pixabay")
    ap.add_argument("--limit", type=int, default=8, help="单站采集上限")
    ap.add_argument("--transparent", action="store_true", help="只要透明 PNG")
    ap.add_argument("--orientation", default="any", choices=["any", "landscape", "portrait"])
    ap.add_argument("--color", default="", help="目标主色 #rrggbb")
    ap.add_argument("--color-tol", type=int, default=90, dest="color_tol")
    ap.add_argument("--min-px", type=int, default=400, dest="min_px")
    ap.add_argument("--strict", action="store_true", help="筛空不降级(默认自动放宽一档)")
    ap.add_argument("--no-detail", action="store_true", dest="no_detail", help="关闭详情页原图兜底")
    ap.add_argument("--visible", action="store_true", help="专用浏览器用可见窗口(首次绑定用)")
    ap.add_argument("--ensure-browser", action="store_true", dest="ensure_browser",
                    help="只做浏览器绑定/启动,不搜索")
    args = ap.parse_args()

    token = hub_token()
    ensure_hub(token)
    connected, notes = ensure_browser(token, visible=args.visible)
    if args.ensure_browser:
        emit({"ok": connected, "cmd": "ensure_browser", "port": HUNT_PORT,
              "token": token, "profile": cfg(PROFILE_KEY) or os.path.join(studio_dir(), "bridge-browser"),
              "notes": notes,
              "binding_required": None if connected else
              "在弹出的专用浏览器里:①登录花瓣;②点扩展图标,填上面 port/token,点「连接本机会话」(一辈子一次)"})
        return 0 if connected else 2
    if not connected:
        return fail("BINDING_REQUIRED",
                    "专用浏览器未绑定",
                    hint="先跑:python scripts/asset_hunt.py --query x --theme x --ensure-browser --visible,"
                         f"在弹出的窗口登录花瓣并把 port={HUNT_PORT} / token 填进扩展(一次即可)")

    theme_dir = os.path.join(studio_dir(), "materials", args.theme)
    os.makedirs(theme_dir, exist_ok=True)
    report = {"ok": False, "cmd": "asset_hunt", "query": args.query, "theme": args.theme,
              "sites": {}, "files": [], "risk_files": [], "filtered": {}, "degraded": notes,
              "tabs_closed": [], "errors": []}

    tab_ids: list[int] = []
    pool_items: list[dict] = []
    for site in [s.strip() for s in args.sites.split(",") if s.strip()]:
        if site in ("huaban", "svgrepo"):  # Bridge 通道
            r = hunt_site(site, args.query, args.limit)
            if r.get("tabId") is not None:
                tab_ids.append(r["tabId"])
            site_r = {"collected": r.get("collected", 0),
                      "source_filter": r.get("source_filter") or [],
                      "source_filter_failed": r.get("source_filter_failed") or [],
                      "error": r.get("error")}
            pool_items.extend(r.get("items", [])[: args.limit])
        elif site in ("pexels", "pixabay"):  # 干净 API 通道(无浏览器)
            try:
                import sources
                r = sources.search(args.query, [site], limit=args.limit)
                items = r.get("items", [])
                site_r = {"collected": len(items), "error": r.get("error")}
                pool_items.extend(items)
            except Exception as exc:  # noqa: BLE001
                site_r = {"collected": 0, "error": f"{type(exc).__name__}"}
        else:
            site_r = {"collected": 0, "error": "未知站点(第一批:huaban/svgrepo/pexels/pixabay)"}
        report["sites"][site] = site_r

    if not pool_items:
        report["errors"].append("所有站点 0 结果:换关键词/检查绑定与登录态")
        emit(report)
        return 1

    dl = download_items(pool_items, theme=args.theme)
    files = [os.path.basename(f["file"]) for f in dl.get("files", [])]
    report["risk_files"] = [os.path.basename(f["file"]) for f in dl.get("risk_files", [])]
    report["errors"].extend(f"{e.get('url', '')[:60]}: {e.get('error')}" for e in dl.get("errors", []))

    # 原图兜底(D3):下载失败/过小的花瓣项,开详情页重采
    if not args.no_detail:
        small = []
        for f in dl.get("files", []):
            p = os.path.join(theme_dir, os.path.basename(f["file"]))
            try:
                if (os.path.getsize(p) < 20000 and "huaban" in (f.get("source") or "")
                        and "/pins/" in f.get("page_url", "")):
                    small.append({"page_url": f["page_url"], "risk": True})
            except OSError:
                pass
        if small:
            extra, fb_tabs = detail_fallback(small, args.theme, budget=6)
            tab_ids.extend(fb_tabs)
            files += [os.path.basename(x["file"]) for x in extra]
            report["risk_files"] += [os.path.basename(x["file"]) for x in extra
                                     if x.get("risk")]
            report["degraded"].append(f"详情页兜底重采 {len(extra)} 张")

    # 筛选(D4:严格/降级阶梯)
    wants_filter = args.transparent or args.orientation != "any" or args.color
    if wants_filter:
        fr = apply_filters(theme_dir, files, args.transparent, args.orientation, args.color, args.color_tol)
        if not fr["kept"] and not args.strict:
            for drop_key, note in RELAX_LADDER:
                t2 = args.transparent and drop_key != "transparent"
                o2 = args.orientation if drop_key != "orientation" else "any"
                c2 = args.color if drop_key != "color" else ""
                if (t2, o2, c2) == (args.transparent, args.orientation, args.color):
                    continue
                fr = apply_filters(theme_dir, files, t2, o2, c2, args.color_tol)
                report["degraded"].append(note)
                if fr["kept"]:
                    break
        if not fr["kept"] and not args.strict and wants_filter:
            fr = apply_filters(theme_dir, files, False, "any", "", args.color_tol)
            report["degraded"].append("全部筛选已放宽")
        if not fr["kept"] and wants_filter:
            report["errors"].append("EMPTY_AFTER_FILTER:严格模式下没有满足条件的素材")
            report["filtered"] = {k: v for k, v in fr["filtered"].items() if v}
            emit(report)
            return 1
        report["filtered"] = {k: v for k, v in fr["filtered"].items() if v}
        files = fr["kept"]

    # 去重 + 关页(D10)
    try:
        from _img_probe import cmd_dedupe  # noqa: F401 — 经 imageops 子命令更贴纪律
    except Exception:  # noqa: BLE001
        pass
    dedupe_note = None
    try:
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "imageops.py"),
                            "dedupe", theme_dir, "--threshold", "6"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if r.returncode == 0 and r.stdout:
            d = json.loads([l for l in r.stdout.splitlines() if l.strip()][-1])
            dedupe_note = f"pHash 查重:{len(d.get('dups', []))} 组近重复(保留 {len(d.get('kept', []))})"
    except Exception as exc:  # noqa: BLE001
        dedupe_note = f"查重跳过({type(exc).__name__})"

    if tab_ids:
        try:
            from bridge import BridgeClient
            cli = BridgeClient(HUNT_PORT, token)
            cli.handshake(role="client")
            closed = cli.call({"type": "close_tab", "tabIds": tab_ids}, timeout=20)
            cli.close()
            report["tabs_closed"] = closed.get("closed", [])
        except Exception as exc:  # noqa: BLE001
            report["errors"].append(f"关页失败:{type(exc).__name__}")

    report.update({"ok": bool(files), "files": files,
                   "dedupe": dedupe_note,
                   "theme_dir": theme_dir,
                   "credits": os.path.join(theme_dir, "CREDITS.md"),
                   "hint": None if files else "无成品:换关键词/放宽 --transparent --orientation/--min-px"})
    emit(report)
    return 0 if files else 1


if __name__ == "__main__":
    sys.exit(main())
