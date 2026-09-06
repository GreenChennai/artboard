"""artboard 二维码工具:生成(品牌色/内嵌 logo)+ 解析(本地 zxing,URL 走草料 API)。

用法:
  python qr.py generate --data "https://shanwu.cafe" --out qr.png [--size 600]
                        [--fg "#241a10"] [--bg "#faf6ef"] [--logo logo.png] [--engine local|cliim]
  python qr.py decode <图片>            # 本地 zxing-cpp(离线,推荐)
  python qr.py decode --url <图片URL>   # 草料 API(图片需公网可访问)

海报工作流:设计稿里放「二维码占位」→ 终稿前 generate 真码替换占位 → 重导。
依赖:本地引擎 pip install qrcode zxing-cpp;cliim 引擎免鉴权(草料开放平台)。
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.parse

from _config import cfg

PROXY = None  # 惰性读取


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def proxy() -> str | None:
    global PROXY
    if PROXY is None:
        PROXY = cfg("proxy") or None
    return PROXY


def http_get(url: str, timeout: int = 30) -> bytes:
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0 Safari/537.36"})
    handlers = []
    if proxy():
        handlers.append(urllib.request.ProxyHandler({"http": proxy(), "https": proxy()}))
    with urllib.request.build_opener(*handlers).open(req, timeout=timeout) as r:
        return r.read()


def gen_local(data: str, out: str, size: int, fg: str, bg: str, logo: str | None) -> str:
    import qrcode
    from PIL import Image
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H,
                       box_size=10, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fg, back_color=bg).convert("RGBA")
    img = img.resize((size, size), Image.NEAREST)
    if logo and os.path.isfile(logo):
        lsize = size // 5  # H 级纠错可承受 ~20% 遮盖
        limg = Image.open(logo).convert("RGBA")
        limg.thumbnail((lsize, lsize))
        img.alpha_composite(limg, ((size - limg.width) // 2, (size - limg.height) // 2))
    img.save(out)
    return out


def gen_cliim(data: str, out: str) -> str:
    data_b = http_get("https://api.2dcode.biz/v1/create-qr-code?data="
                      + urllib.parse.quote(data))
    with open(out, "wb") as f:
        f.write(data_b)
    return out


def decode_local(img: str) -> dict:
    import zxingcpp
    from PIL import Image
    results = zxingcpp.read_barcodes(Image.open(img))
    if not results:
        raise RuntimeError("未识别到二维码/条码")
    return {"texts": [r.text for r in results],
            "formats": [r.format.name for r in results]}


def decode_api(url: str) -> dict:
    api = ("https://api.2dcode.biz/v1/read-qr-code?file_url="
           + urllib.parse.quote(url, safe=""))
    raw = http_get(api).decode("utf-8", "ignore")
    try:
        data = json.loads(raw)
    except Exception:
        raise RuntimeError(f"草料 API 返回非 JSON: {raw[:120]}")
    if isinstance(data, dict) and data.get("code") not in (0, 200, "0", "200"):
        raise RuntimeError(f"草料 API: {str(data)[:160]}")
    return {"raw": data}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="生成二维码")
    g.add_argument("--data", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--size", type=int, default=600)
    g.add_argument("--fg", default="#241a10")
    g.add_argument("--bg", default="#ffffff")
    g.add_argument("--logo", default="", help="中心 logo 图(自动缩到 20%%,需 H 级纠错)")
    g.add_argument("--engine", default="local", choices=["local", "cliim"])

    d = sub.add_parser("decode", help="解析二维码")
    d.add_argument("image", nargs="?", default="")
    d.add_argument("--url", default="", help="公网图片 URL(走草料 API)")

    args = p.parse_args()

    try:
        if args.cmd == "generate":
            os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
            if args.engine == "cliim":
                path = gen_cliim(args.data, args.out)
            else:
                path = gen_local(args.data, args.out, args.size,
                                 args.fg, args.bg, args.logo or None)
            emit({"ok": True, "path": os.path.abspath(path),
                  "hint": "海报最小展示尺寸:码宽 ≥ 版面宽的 8%,且四周留白 ≥ 1 模块"})
        else:
            if args.url:
                emit({"ok": True, **decode_api(args.url)})
            elif args.image:
                emit({"ok": True, **decode_local(args.image)})
            else:
                p.error("decode 需要 <图片> 或 --url")
    except Exception as exc:  # noqa: BLE001
        emit({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
