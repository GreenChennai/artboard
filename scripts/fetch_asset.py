"""artboard 素材获取:图库 API(授权干净)+ 爬虫兜底 + CREDITS 登记。

来源与版权策略(详见 references/materials.md):
  pexels / pixabay  — 免费商用免署名(config.json 或环境变量配 key)
  bing / baidu      — 爬虫兜底,版权不确定 → 文件名自动加前缀「版权风险-」
  huaban / iconfont / pinterest — 需要 Cookie(config.json 的 *_cookie,可用
                      tools/cookie-extension 浏览器插件抓取);同为爬虫,全部风险标记

用法:
  python fetch_asset.py --query "coffee cup" --theme <主题slug> [--source auto] \
      [--limit 6] [--orientation landscape|portrait|square] [--download] [--image-type photo]

  --source auto:pexels → pixabay → 爬虫(bing/baidu/huaban)顺序取候选
  --source iconfont:矢量/图标素材(pinterest/huaban 用 --source 显式指定)
  --download:把前 limit 张候选下载进 <studio>/materials/<theme>/ 并登记 CREDITS.md
  Pixabay 要求搜索结果展示时注明来源——CREDITS.md 即履行此义务。
"""

import argparse
import datetime
import json
import os
import re
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


def http_get(url: str, headers: dict | None = None, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ---------------- 来源实现:返回 [candidate] ----------------
# candidate = {source, url, page_url, author, license, risk(bool)}

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


def search_huaban(q: str, limit: int) -> list[dict]:
    """花瓣:需要 Cookie(config.json huaban_cookie,可用浏览器插件抓取)。"""
    headers = {"X-Requested-With": "XMLHttpRequest",
               "Referer": "https://huaban.com/search/?q=" + urllib.parse.quote(q)}
    cookie = cfg("huaban_cookie")
    if cookie:
        headers["Cookie"] = cookie
    u = ("https://huaban.com/api/search?query=" + urllib.parse.quote(q) + "&page=1&per_page=" + str(limit))
    try:
        data = json.loads(http_get(u, headers, timeout=15))
    except Exception as exc:
        return [{"source": "huaban", "url": "", "page_url": "", "author": "",
                 "license": f"接口失败({type(exc).__name__}):请在 config.json 填 huaban_cookie"
                            "(用 tools/cookie-extension 插件抓取)后重试",
                 "risk": True}]
    out = []
    for pin in data.get("pins", []) or data.get("results", []):
        f = pin.get("file") or {}
        key = f.get("key")
        if not key:
            continue
        img = f"https://gd-hbimg.huaban.com/{key}_fw658" if not key.startswith("http") else key
        board = (pin.get("board") or {}).get("title", "花瓣")
        out.append({"source": "huaban", "url": img, "page_url": "https://huaban.com/pins/" + str(pin.get("pin_id", "")),
                    "author": board, "license": "不确定(爬虫结果)", "risk": True})
        if len(out) >= limit:
            break
    return out


def search_iconfont(q: str, limit: int) -> list[dict]:
    """阿里巴巴图标库 iconfont.cn:矢量/图标,需要 Cookie(config.json iconfont_cookie)。
    站点接口随时可能变动,失败时给明确提示。"""
    headers = {"Referer": "https://www.iconfont.cn/search/index?q=" + urllib.parse.quote(q)}
    cookie = cfg("iconfont_cookie")
    if cookie:
        headers["Cookie"] = cookie
    u = (f"https://www.iconfont.cn/api/icon/search.json?q={urllib.parse.quote(q)}"
         f"&page=1&pageSize={limit}")
    try:
        data = json.loads(http_get(u, headers, timeout=15))
    except Exception as exc:
        return [{"source": "iconfont", "url": "", "page_url": "", "author": "",
                 "license": f"接口失败({type(exc).__name__}):请在 config.json 填 iconfont_cookie"
                            "(用 tools/cookie-extension 插件抓取)后重试;站点接口可能已变动",
                 "risk": True}]
    out = []
    for it in data.get("data", {}).get("icons", []) or []:
        iid = it.get("id")
        if not iid:
            continue
        out.append({"source": "iconfont", "url": f"https://www.iconfont.cn/api/icon/getSvg.svg?id={iid}",
                    "page_url": f"https://www.iconfont.cn/icon/detail?iconId={iid}",
                    "author": it.get("user_name") or "iconfont",
                    "license": "不确定(iconfont 用户上传,授权不一,逐个核对)", "risk": True})
        if len(out) >= limit:
            break
    return out


def search_pinterest(q: str, limit: int) -> list[dict]:
    """Pinterest:需要 Cookie(config.json pinterest_cookie,可用浏览器插件抓取)。
    走网页版 resource 接口,站点反爬较强,失败时给明确提示。"""
    headers = {"X-Requested-With": "XMLHttpRequest",
               "Referer": f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(q)}"}
    cookie = cfg("pinterest_cookie")
    if cookie:
        headers["Cookie"] = cookie
    data_opt = json.dumps({"options": {"query": q, "page_size": min(limit, 25)}},
                          separators=(",", ":"))
    u = ("https://www.pinterest.com/resource/BaseSearchResource/get/?source_url="
         + urllib.parse.quote(f"/search/pins/?q={q}")
         + "&data=" + urllib.parse.quote(data_opt))
    try:
        data = json.loads(http_get(u, headers, timeout=15))
    except Exception as exc:
        return [{"source": "pinterest", "url": "", "page_url": "", "author": "",
                 "license": f"接口失败({type(exc).__name__}):请在 config.json 填 pinterest_cookie"
                            "(用 tools/cookie-extension 插件抓取)后重试;国内网络可能无法直连",
                 "risk": True}]
    out = []
    for pin in data.get("resource_response", {}).get("data", {}).get("results", []) or []:
        img = ((pin.get("images") or {}).get("orig") or {}).get("url") \
            or ((pin.get("images") or {}).get("736x") or {}).get("url")
        if not img:
            continue
        out.append({"source": "pinterest", "url": img,
                    "page_url": pin.get("seotitle") and f"https://www.pinterest.com/pin/{pin.get('id')}/"
                                or f"https://www.pinterest.com/pin/{pin.get('id')}/",
                    "author": (pin.get("pinner") or {}).get("username", "pinterest"),
                    "license": "不确定(爬虫结果)", "risk": True})
        if len(out) >= limit:
            break
    return out


SOURCES = {
    "pexels": lambda q, l, o, t: search_pexels(q, l, o),
    "pixabay": lambda q, l, o, t: search_pixabay(q, l, o, t),
    "bing": lambda q, l, o, t: search_bing(q, l),
    "baidu": lambda q, l, o, t: search_baidu(q, l),
    "huaban": lambda q, l, o, t: search_huaban(q, l),
    "iconfont": lambda q, l, o, t: search_iconfont(q, l),
    "pinterest": lambda q, l, o, t: search_pinterest(q, l),
}
AUTO_ORDER = ["pexels", "pixabay", "bing", "baidu", "huaban"]

EXT_BY_MAGIC = {b"\xff\xd8\xff": ".jpg", b"\x89PNG": ".png", b"GIF8": ".gif", b"RIFF": ".webp"}


def sniff_ext(data: bytes) -> str:
    for magic, ext in EXT_BY_MAGIC.items():
        if data.startswith(magic):
            return ext
    return ".jpg"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("--query", required=True)
    p.add_argument("--theme", required=True, help="素材库主题目录名(如 promo-coffee)")
    p.add_argument("--source", default="auto", choices=["auto", *SOURCES])
    p.add_argument("--limit", type=int, default=6)
    p.add_argument("--orientation", default="", choices=["", "landscape", "portrait", "square"])
    p.add_argument("--image-type", default="photo", dest="image_type",
                   choices=["photo", "illustration", "vector"], help="仅 pixabay 生效")
    p.add_argument("--download", action="store_true", help="下载前 limit 张并登记 CREDITS")
    args = p.parse_args()

    if args.source == "auto":
        cands: list[dict] = []
        for s in AUTO_ORDER:
            got = SOURCES[s](args.query, args.limit, args.orientation, args.image_type)
            cands.extend(got)
            if len(cands) >= args.limit:
                break
        cands = cands[: args.limit]
    else:
        cands = SOURCES[args.source](args.query, args.limit, args.orientation,
                                     args.image_type)[: args.limit]

    if not cands:
        emit({"ok": False, "error": "NO_RESULTS",
              "hint": "所有来源无结果;检查 key 环境变量(ARTBOARD_PEXELS_KEY/ARTBOARD_PIXABAY_KEY),"
                      "或换关键词/用 --source bing"})
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
            if not c.get("url"):
                continue
            try:
                data = http_get(c["url"], timeout=30)
                if len(data) < 3000:
                    continue
                name = f"{args.theme}-{c['source']}-{i:02d}{sniff_ext(data)}"
                if c["risk"]:
                    name = RISK_PREFIX + name
                with open(os.path.join(theme_dir, name), "wb") as f:
                    f.write(data)
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
