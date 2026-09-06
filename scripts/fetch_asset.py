"""artboard 素材获取:图库 API(授权干净)+ 爬虫兜底 + 剪贴板入库 + CREDITS 登记。

来源与版权策略(详见 references/materials.md):
  pexels / pixabay  — 免费商用免署名(config.json 或环境变量配 key)
  bing / baidu      — 爬虫兜底,版权不确定 → 文件名自动加前缀「版权风险-」
  iconfont          — POST 接口(Cookie),SVG 源码内嵌在搜索结果里;风险标记
  pinterest         — 搜索页 HTML 解析(走 config.json 的 proxy)+ curl 下载图床;风险标记
  huaban            — WAF 拦截程序化访问,走插件通道:浏览器装 tools/cookie-extension,
                      在花瓣搜索页点「导出本页素材 JSON」,再 --source clipboard 入库;风险标记

用法:
  python fetch_asset.py --query "coffee cup" --theme <主题slug> [--source auto] \
      [--limit 6] [--orientation landscape|portrait|square] [--download] [--image-type photo]

  --source auto:pexels → pixabay → bing → baidu
  --source clipboard:读取剪贴板里的素材 JSON(由 cookie-extension「导出本页素材」生成),
                     无需 --query;配合花瓣等 WAF 站点使用
  --download:把前 limit 张候选下载进 <studio>/materials/<theme>/ 并登记 CREDITS.md
  Pixabay 要求搜索结果展示时注明来源——CREDITS.md 即履行此义务。
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

from _config import cfg

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDIO = cfg("studio_dir", r"E:\平日资料\GitHub\artboard-studio")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) artboard-asset-fetch/1.0",
      "Accept": "*/*"}
RISK_PREFIX = "版权风险-"


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def http_get(url: str, headers: dict | None = None, timeout: int = 20,
             proxy: str | None = None, data: str | None = None) -> bytes:
    req = urllib.request.Request(url, headers={**UA, **(headers or [])},
                                 data=data.encode("utf-8") if isinstance(data, str) else None)
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()


def curl_get(url: str, out_path: str | None = None, proxy: str | None = None,
             headers: dict | None = None, timeout: int = 40) -> bytes:
    """python TLS 被站点挡时的兜底:子进程 curl(独立的 TLS 指纹)。"""
    cmd = ["curl", "-sL", "-m", str(timeout), "-w", "%{http_code}",
           "-H", f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0 Safari/537.36"]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    if proxy:
        cmd += ["-x", proxy]
    if out_path:
        cmd += ["-o", out_path]
    else:
        cmd += ["--output", "-"]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    return r.stdout


# ---------------- 来源实现:返回 [candidate] ----------------
# candidate = {source, url?, content?, page_url, author, license, risk(bool)}
# 带 content 的候选直接使用该内容(如 iconfont 内嵌 SVG),不走 HTTP 下载。

def search_pexels(q: str, limit: int, orientation: str) -> list[dict]:
    key = cfg("pexels_key")
    if not key:
        return []
    u = ("https://api.pexels.com/v1/search?query=" + urllib.parse.quote(q)
         + f"&per_page={limit}" + (f"&orientation={orientation}" if orientation else ""))
    try:
        data = json.loads(http_get(u, {"Authorization": key}))
    except Exception:
        return []
    return [{"source": "pexels", "url": p["src"]["large2x"], "page_url": p.get("url", ""),
             "author": p.get("photographer", "unknown"),
             "license": "Pexels License(免费商用免署名)", "risk": False}
            for p in data.get("photos", [])]


def search_pixabay(q: str, limit: int, orientation: str, image_type: str = "photo") -> list[dict]:
    key = cfg("pixabay_key")
    if not key:
        return []
    u = ("https://pixabay.com/api/?key=" + key + "&q=" + urllib.parse.quote(q)
         + f"&image_type={image_type}&per_page={limit}&safesearch=true"
         + (f"&orientation={orientation}" if orientation else ""))
    try:
        data = json.loads(http_get(u))
    except Exception:
        return []
    return [{"source": "pixabay", "url": h.get("largeImageURL", ""), "page_url": h.get("pageURL", ""),
             "author": h.get("user", "unknown"),
             "license": "Pixabay Content License(免费商用免署名)", "risk": False}
            for h in data.get("hits", [])]


RX_BING_MURL = re.compile(r'murl&quot;:&quot;(.*?)&quot;')
RX_BING_PURL = re.compile(r'purl&quot;:&quot;(.*?)&quot;')


def search_bing(q: str, limit: int) -> list[dict]:
    u = ("https://www.bing.com/images/search?q=" + urllib.parse.quote(q)
         + "&qft=+filterui:photo-photo&form=IRFLTR")
    try:
        html = http_get(u, timeout=15).decode("utf-8", "ignore")
    except Exception:
        return []
    murls = [m.replace("\\u002f", "/") for m in RX_BING_MURL.findall(html)][: limit * 2]
    purls = [p.replace("\\u002f", "/") for p in RX_BING_PURL.findall(html)]
    out = []
    for i, m in enumerate(murls):
        if m.startswith("http"):
            out.append({"source": "bing", "url": m, "page_url": purls[i] if i < len(purls) else "",
                        "author": "网页来源", "license": "不确定(爬虫结果)",
                        "risk": True})
        if len(out) >= limit:
            break
    return out


def search_baidu(q: str, limit: int) -> list[dict]:
    u = ("https://image.baidu.com/search/acjson?tn=resultjson_com&ipn=rj&word="
         + urllib.parse.quote(q) + f"&pn=0&rn={limit}&ie=utf-8&z=9")
    try:
        raw = http_get(u, timeout=15).decode("utf-8", "ignore")
        items = re.findall(r'\{.*?"middleURL".*?\}', raw)
    except Exception:
        return []
    out = []
    for it in items:
        try:
            d = json.loads(it)
        except Exception:
            continue
        url = d.get("middleURL") or d.get("thumbURL")
        if url:
            out.append({"source": "baidu", "url": url, "page_url": d.get("fromUrl", ""),
                        "author": d.get("fromPageTitle", "网页来源")[:60],
                        "license": "不确定(爬虫结果)", "risk": True})
        if len(out) >= limit:
            break
    return out


def search_iconfont(q: str, limit: int) -> list[dict]:
    """阿里巴巴图标库:POST 接口,SVG 源码内嵌在 show_svg 字段(实测 2026-09)。
    需要 Cookie(config.json iconfont_cookie,tools/cookie-extension 插件抓取)。"""
    headers = {"Accept": "application/json",
               "Referer": "https://www.iconfont.cn/search/index?q=" + urllib.parse.quote(q)}
    cookie = cfg("iconfont_cookie")
    if cookie:
        headers["Cookie"] = cookie
    u = "https://www.iconfont.cn/api/icon/search.json"
    body = urllib.parse.urlencode({"q": q, "page": 1, "pageSize": max(limit, 3)})
    try:
        data = json.loads(http_get(u, headers, timeout=15, data=body).decode("utf-8", "ignore"))
    except Exception as exc:
        return [{"source": "iconfont", "url": "", "page_url": "", "author": "",
                 "license": f"接口失败({type(exc).__name__}):请确认 config.json 的 iconfont_cookie"
                            "(tools/cookie-extension 插件抓取);站点接口可能已变动",
                 "risk": True}]
    out = []
    for it in data.get("data", {}).get("icons", []) or []:
        svg = it.get("show_svg")
        if not svg:
            continue
        out.append({"source": "iconfont", "content": svg,
                    "page_url": f"https://www.iconfont.cn/icon/detail?iconId={it.get('id')}",
                    "author": it.get("user_name") or f"iconfont.user_{it.get('user_id')}",
                    "license": "不确定(iconfont 用户上传,授权不一,逐个核对)", "risk": True,
                    "name_hint": it.get("name") or it.get("font_class") or "icon"})
        if len(out) >= limit:
            break
    return out


RX_PINIMG = re.compile(r'https://i\.pinimg\.com/(?:736x|originals)/[a-f0-9/]+\.(?:jpg|jpeg|png)')


def search_pinterest(q: str, limit: int) -> list[dict]:
    """Pinterest:搜索页 HTML 解析(需要 config.json 的 proxy 走本地代理),
    图床下载用 curl(python TLS 会被 pinimg 掐断,实测 curl 可用)。风险标记。"""
    proxy = cfg("proxy")
    headers = {"Cookie": cfg("pinterest_cookie"),
               "Accept-Language": "en-US,en;q=0.9"}
    u = "https://www.pinterest.com/search/pins/?q=" + urllib.parse.quote(q)
    try:
        html = http_get(u, headers, timeout=25, proxy=proxy).decode("utf-8", "ignore")
    except Exception as exc:
        return [{"source": "pinterest", "url": "", "page_url": "", "author": "",
                 "license": f"接口失败({type(exc).__name__}):确认 config.json 已填 proxy(本地代理)"
                            "与 pinterest_cookie(插件抓取);国内网络 Pinterest 需代理",
                 "risk": True}]
    urls = list(dict.fromkeys(RX_PINIMG.findall(html)))
    seen, uniq = set(), []
    for u in urls:  # 736x 与 originals 是同一张图,按图片路径去重
        key = re.sub(r"/(736x|originals)/", "/", u)
        if key not in seen:
            seen.add(key)
            uniq.append(u)
    urls = uniq
    out = []
    for i, img in enumerate(urls[: limit]):
        # 736x → originals 原图(部分不存在,下载失败由 curl 回退 736x)
        orig = img.replace("/736x/", "/originals/")
        out.append({"source": "pinterest", "url": orig, "fallback_url": img,
                    "page_url": f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(q)}",
                    "author": "pinterest", "license": "不确定(爬虫结果)", "risk": True})
    return out[:limit]


def search_huaban(q: str, limit: int) -> list[dict]:
    """花瓣:WAF 拦截一切程序化访问(urllib/requests/curl/无头浏览器实测全 403/405),
    走插件通道:tools/cookie-extension 在花瓣搜索页「导出本页素材 JSON」→ --source clipboard。"""
    return [{"source": "huaban", "url": "", "page_url": "", "author": "",
             "license": "花瓣 WAF 拦截程序化访问:请在浏览器装 tools/cookie-extension 插件,"
                        "打开花瓣搜索页点「导出本页素材 JSON」,然后 --source clipboard 入库",
             "risk": True}]


def search_clipboard(q: str, limit: int) -> list[dict]:
    """剪贴板入库:读取 cookie-extension「导出本页素材」生成的 JSON。"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-command",
             "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard"],
            capture_output=True, encoding="utf-8", errors="ignore", timeout=30)
        raw = (r.stdout or "").strip()
    except Exception as exc:
        return [{"source": "clipboard", "url": "", "page_url": "", "author": "",
                 "license": f"读剪贴板失败({type(exc).__name__})", "risk": True}]
    try:
        data = json.loads(raw)
    except Exception:
        return [{"source": "clipboard", "url": "", "page_url": "", "author": "",
                 "license": "剪贴板内容不是素材 JSON:请在插件上点「导出本页素材 JSON」后再试",
                 "risk": True}]
    out = []
    for it in data.get("items", [])[:limit]:
        src = it.get("src") or ""
        if not src.startswith("http"):
            continue
        out.append({"source": f"clipboard-{data.get('site','web')}", "url": src,
                    "page_url": it.get("link") or data.get("page_url", ""),
                    "author": it.get("alt") or "网页来源",
                    "license": "不确定(爬虫结果)", "risk": True})
    return out


SOURCES = {
    "pexels": lambda q, l, o, t: search_pexels(q, l, o),
    "pixabay": lambda q, l, o, t: search_pixabay(q, l, o, t),
    "bing": lambda q, l, o, t: search_bing(q, l),
    "baidu": lambda q, l, o, t: search_baidu(q, l),
    "huaban": lambda q, l, o, t: search_huaban(q, l),
    "iconfont": lambda q, l, o, t: search_iconfont(q, l),
    "pinterest": lambda q, l, o, t: search_pinterest(q, l),
    "clipboard": lambda q, l, o, t: search_clipboard(q, l),
}
AUTO_ORDER = ["pexels", "pixabay", "bing", "baidu"]

EXT_BY_MAGIC = {b"\xff\xd8\xff": ".jpg", b"\x89PNG": ".png", b"GIF8": ".gif",
                b"RIFF": ".webp"}


def sniff_ext(data: bytes) -> str:
    for magic, ext in EXT_BY_MAGIC.items():
        if data.startswith(magic):
            return ext
    if data.lstrip()[:5] in (b"<?xml", b"<svg ") or data.lstrip().startswith(b"<svg"):
        return ".svg"
    return ".jpg"


def download_one(c: dict, theme_dir: str, base: str) -> tuple[str, str]:
    """下载单个候选到 theme_dir,返回 (最终文件名, 错误)。支持 content 直存与 curl 回退。
    base = 不含扩展名的文件名(前缀/扩展名在本函数内统一处理)。"""
    def finalize(name: str, data: bytes) -> str:
        if c.get("risk"):
            name = RISK_PREFIX + name
        with open(os.path.join(theme_dir, name), "wb") as f:
            f.write(data)
        return name

    if c.get("content"):
        hint = re.sub(r"[^a-zA-Z0-9_-]", "", c.get("name_hint", "") or "item") or "item"
        name = finalize(f"{base}-{hint}.svg", c["content"].encode("utf-8"))
        return name, ""

    for url in (c.get("url"), c.get("fallback_url")):
        if not url:
            continue
        try:
            data = http_get(url, timeout=30)
            if len(data) < 3000:
                raise RuntimeError(f"过小 {len(data)}B")
            return finalize(f"{base}{sniff_ext(data)}", data), ""
        except Exception:  # noqa: BLE001 — python TLS 被掐时 curl 兜底
            for curl_proxy in (None, cfg("proxy") or None):  # 直连优先,代理其次
                tmp = os.path.join(theme_dir, base + ".bin")
                try:
                    code = curl_get(url, out_path=tmp, proxy=curl_proxy, timeout=45)
                    if (os.path.isfile(tmp) and os.path.getsize(tmp) > 3000
                            and code.decode(errors="ignore").startswith(("2", "3"))):
                        data = open(tmp, "rb").read()
                        name = finalize(f"{base}{sniff_ext(data)}", data)
                        os.remove(tmp)
                        return name, ""
                    if os.path.isfile(tmp):
                        os.remove(tmp)
                except Exception:  # noqa: BLE001
                    if os.path.isfile(tmp):
                        os.remove(tmp)
    return "", "所有下载方式均失败"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("--query", default="", help="clipboard 源可省略")
    p.add_argument("--theme", required=True, help="素材库主题目录名(如 promo-coffee)")
    p.add_argument("--source", default="auto", choices=["auto", *SOURCES])
    p.add_argument("--limit", type=int, default=6)
    p.add_argument("--orientation", default="", choices=["", "landscape", "portrait", "square"])
    p.add_argument("--image-type", default="photo", dest="image_type",
                   choices=["photo", "illustration", "vector"], help="仅 pixabay 生效")
    p.add_argument("--download", action="store_true", help="下载前 limit 张并登记 CREDITS")
    args = p.parse_args()

    if args.source == "clipboard" and not args.query:
        args.query = "clipboard"
    if not args.query:
        p.error("需要 --query(clipboard 源除外)")

    if args.source == "auto":
        cands: list[dict] = []
        for s in AUTO_ORDER:
            cands.extend(SOURCES[s](args.query, args.limit, args.orientation, args.image_type))
            if len(cands) >= args.limit:
                break
        cands = cands[: args.limit]
    else:
        cands = SOURCES[args.source](args.query, args.limit, args.orientation,
                                     args.image_type)[: args.limit]

    if not cands:
        emit({"ok": False, "error": "NO_RESULTS", "hint": "所有来源无结果;换关键词或 --source"})
        return 1

    results = []
    if args.download:
        theme_dir = os.path.join(STUDIO, "materials", args.theme)
        os.makedirs(theme_dir, exist_ok=True)
        credits = os.path.join(theme_dir, "CREDITS.md")
        if not os.path.isfile(credits):
            with open(credits, "w", encoding="utf-8") as f:
                f.write(f"# CREDITS · {args.theme}\n\n"
                        "| 文件 | 来源 | 作者 | 授权 | 来源页 | 日期 |\n|---|---|---|---|---|---|\n")
        for i, c in enumerate(cands, 1):
            if not (c.get("url") or c.get("content")):
                continue
            try:
                base = f"{args.theme}-{c['source']}-{i:02d}"
                name, err = download_one(c, theme_dir, base)
                if err:
                    results.append({"url": c.get("url", ""), "error": err})
                    continue
                row = (f"| {name} | {c['source']} | {c['author']} | {c['license']} "
                       f"| {c['page_url']} | {datetime.date.today().isoformat()} |\n")
                with open(credits, "a", encoding="utf-8") as f:
                    f.write(row)
                results.append({"file": os.path.join(theme_dir, name), "source": c["source"],
                                "license": c["license"], "author": c["author"],
                                "risk": c["risk"]})
            except Exception as exc:  # noqa: BLE001
                results.append({"url": c.get("url", ""), "error": f"{type(exc).__name__}: {exc}"})

    emit({"ok": True, "candidates": len(cands), "downloaded": results if args.download else None,
          "risk_note": "带「版权风险-」前缀的文件禁止移除前缀直接当无风险素材使用;"
                       "交付时必须在汇报中列出并提醒用户更换" if args.download else None,
          "hint": None if any(cfg(k) for k in ("pexels_key", "pixabay_key"))
          else "未配置图库 key:在 config.json 填 pexels_key / pixabay_key 启用授权干净的图库源"
               "(当前仅爬虫可用)"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
