#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""upload_imgchr.py — 上传图片到图床(imgchr / 路过图床, Chevereto 内核)并拿到直链

用途(模式 W 的收尾环节):
    公众号正文里的图片本来要在微信编辑器里**一张张手动插入**。改了「图床外链」之后
    就不用了 —— 图片挂在图床上, 文章 HTML 里直接写外链, 粘过去即可。
    本脚本负责「上传 → 取直链 → 写成 urls.json」这一段, 与生成器的「外链优先」通道对接。

两条路(任选, 都无需浏览器自动化):

  ① **Cookie 路(推荐, 只要浏览器登录过就能用)**
     从浏览器复制 cookie 里那一串, 脚本自己去页面里抓 auth_token(CSRF), 再 POST /json。
         python upload_imgchr.py 1.jpg 2.jpg --cookie "PHPSESSID=xxxx; ..."
     取 cookie: F12 → Application/Storage → Cookies → https://imgchr.com → 复制全部为
     "k=v; k=v" 形式; 或 Console 里 `document.cookie`(HttpOnly 的取不到, 用 Application 面板)。

  ② **API v1 路(需要 API 密钥)**
         python upload_imgchr.py 1.jpg --api-key "xxxx"
     密钥在站点的账号设置里(Chevereto 的 /settings/api)。

  凭证也可放环境变量: IMGCHR_COOKIE / IMGCHR_API_KEY

写出 urls.json(供生成器的 asset() 优先取外链):
    python upload_imgchr.py out/*.jpg --cookie "..." --urls-out urls.json --key-prefix p
    → 1.jpg 写成 {"p1": "https://…/xxx.jpg"}  (与 PHOTO_SRC 的 p1..p10 键对齐)

⚠️ 隐私提醒: 图床是**公开**的 —— 拿到直链的人都能看图。公司活动照片(有人脸)放公网图床
   等于对外公开发布。若在意, 用自家已备案域名/CDN(如 bee-reg-ab.imagency.cn)更稳妥。
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = "https://imgchr.com"
JSON_API = BASE + "/json"
API_V1 = BASE + "/api/1/upload"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}


def http(url, data=None, headers=None, method=None, timeout=120):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", UA)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})
    except Exception as e:
        return 0, str(e).encode(), {}


def multipart(fields, files):
    """构造 multipart/form-data。files: [(fieldname, filename, bytes)]"""
    b = "----WPBoundary" + uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for fname, fn, raw in files:
        mime = MIME.get(os.path.splitext(fn)[1].lower(), "application/octet-stream")
        out.append(
            f"--{b}\r\nContent-Disposition: form-data; name=\"{fname}\"; "
            f"filename=\"{os.path.basename(fn)}\"\r\nContent-Type: {mime}\r\n\r\n".encode()
            + raw + b"\r\n")
    out.append(f"--{b}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={b}"


def fetch_auth_token(cookie):
    """从页面里抓 Chevereto 的 CSRF token(未登录首页也有)

    返回 (token, logged_in, note)。note 非空表示失败原因, 已做成可自诊断的提示 ——
    实测踩坑: cookie 里的 PHPSESSID 一旦无效, 服务端**不再返回页面**,
    而是直接吐一小段纯文本 `G: Sessions are not working on this server (session_start).`
    (整页只有 60 字节)。看到这个就说明 cookie 过期/复制错了。
    """
    last = ""
    for path in ("/", "/upload"):
        st, body, _ = http(BASE + path, headers={"Cookie": cookie})
        html = body.decode("utf-8", "replace")
        m = re.search(r'auth_token\s*=\s*"([^"]+)"', html)
        if m:
            logged_in = bool(re.search(r"logout|/settings|sign-out", html, re.I))
            return m.group(1), logged_in, ""
        last = html.strip()[:140] or f"HTTP {st} 空响应"
    hint = ""
    if "Sessions are not working" in last:
        hint = (" ← 服务端拒绝了 session: cookie 里的 PHPSESSID 无效或已过期"
                "(F12 → Application → Cookies → imgchr.com 重新复制整串)")
    elif len(last) < 200:
        hint = " ← 响应异常短, 多半是 cookie 不对或触发了风控"
    return None, False, f"抓不到 auth_token (HTTP {st})。服务端原文: {last!r}{hint}"


def pick_url(payload):
    """从 Chevereto 上传响应里取直链(直接取源文件), 退化为查看页"""
    img = payload.get("image") or {}
    if isinstance(img, dict):
        inner = img.get("image") or {}
        for cand in (inner.get("url"), img.get("url"), (img.get("medium") or {}).get("url")):
            if cand:
                return cand
    return None


def upload_cookie(path, cookie, token):
    with open(path, "rb") as f:
        raw = f.read()
    fields = {"type": "image", "action": "upload", "auth_token": token}
    body, ctype = multipart(fields, [("source", path, raw)])
    st, resp, _ = http(JSON_API, data=body, headers={
        "Cookie": cookie, "Content-Type": ctype,
        "X-Requested-With": "XMLHttpRequest", "Referer": BASE + "/",
    })
    try:
        j = json.loads(resp.decode("utf-8", "replace"))
    except Exception:
        return None, f"HTTP {st} 非 JSON 响应: {resp[:200]!r}"
    if j.get("status_code") != 200:
        msg = (j.get("error") or {}).get("message") or j.get("status_txt")
        return None, f"HTTP {st} {msg}  ← 原始: {resp[:200]!r}"
    return pick_url(j), None


def upload_apikey(path, api_key):
    with open(path, "rb") as f:
        raw = f.read()
    body, ctype = multipart({"key": api_key}, [("source", path, raw)])
    st, resp, _ = http(API_V1, data=body, headers={"Content-Type": ctype})
    try:
        j = json.loads(resp.decode("utf-8", "replace"))
    except Exception:
        return None, f"HTTP {st} 非 JSON 响应: {resp[:200]!r}"
    if j.get("status_code") != 200:
        msg = (j.get("error") or {}).get("message") or j.get("status_txt")
        return None, f"HTTP {st} {msg}"
    return pick_url(j), None


def main():
    ap = argparse.ArgumentParser(description="上传图片到图床(imgchr)取直链, 并可写成 urls.json")
    ap.add_argument("images", nargs="+", help="本地图片路径")
    ap.add_argument("--cookie", default=os.environ.get("IMGCHR_COOKIE", ""),
                    help="浏览器里的 cookie 串 (k=v; k=v)")
    ap.add_argument("--api-key", default=os.environ.get("IMGCHR_API_KEY", ""),
                    help="Chevereto API v1 密钥")
    ap.add_argument("--urls-out", help="把结果合并写入该 urls.json (键=文件名(去扩展名), 值=直链)")
    ap.add_argument("--key-prefix", default="", help="写 urls.json 时给键加前缀(如 p → p1)")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    a = ap.parse_args()

    imgs = [p for p in a.images if os.path.isfile(p)]
    if not imgs:
        print("没有找到图片:", a.images)
        return 2

    token = None
    if a.cookie:
        token, logged_in, note = fetch_auth_token(a.cookie)
        if not a.json:
            print(f"Cookie 校验: auth_token={'拿到 ✅' if token else '没拿到 ❌'}  "
                  f"登录态={'像已登录' if logged_in else '未确认'}")
        if not token:
            print("!! " + note)
            return 3
    elif not a.api_key:
        print("需要凭证: 给 --cookie, 或给 --api-key。\n"
              "  取 cookie: F12 → Application → Cookies → https://imgchr.com → 复制全部 k=v; k=v")
        return 2

    results, fails = {}, []
    for p in imgs:
        if a.cookie:
            url, err = upload_cookie(p, a.cookie, token)
        else:
            url, err = upload_apikey(p, a.api_key)
        stem = os.path.splitext(os.path.basename(p))[0]
        if url:
            results[stem] = url
            if not a.json:
                print(f"  ✅ {os.path.basename(p):24s} -> {url}")
        else:
            fails.append((p, err))
            if not a.json:
                print(f"  ❌ {os.path.basename(p):24s} {err}")

    if a.urls_out:
        old = {}
        if os.path.exists(a.urls_out):
            try:
                old = json.load(open(a.urls_out, encoding="utf-8"))
            except Exception:
                old = {}
        for k, v in results.items():
            old[a.key_prefix + k] = v
        with open(a.urls_out, "w", encoding="utf-8") as f:
            json.dump(old, f, ensure_ascii=False, indent=2)
            f.write("\n")
        if not a.json:
            print(f"\n已写入 {a.urls_out} ({len(old)} 条) —— 生成器会自动优先使用外链")

    if a.json:
        print(json.dumps({"ok": results, "failed": [p for p, _ in fails]},
                         ensure_ascii=False, indent=2))
    else:
        print(f"\n成功 {len(results)} / 失败 {len(fails)}")
    return 1 if fails and not results else 0


if __name__ == "__main__":
    sys.exit(main())
