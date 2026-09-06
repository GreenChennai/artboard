"""artboard 兜底导出:独立 Playwright → 静态 PNG。

仅在主路径(export.py / WPI)不可用时使用。支持:整页/锁定高度、1-4 倍分辨率、透明底。
不依赖 WPI;需要 playwright 包 + 系统 Edge/Chrome。
"""

import argparse
import http.server
import json
import os
import socket
import sys
import threading
import urllib.parse

EXE_CANDIDATES = {
    "msedge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
}


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def pick_channel() -> str | None:
    for channel, paths in EXE_CANDIDATES.items():
        if any(os.path.isfile(p) for p in paths):
            return channel
    return None


def serve(directory: str) -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *a, directory=directory, **k)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{port}"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="artboard 兜底 PNG 导出")
    p.add_argument("--source", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--width", type=int, default=1080)
    p.add_argument("--scale", type=int, default=1, choices=[1, 2, 4])
    p.add_argument("--height", type=int, default=0, help=">0 时锁定高度")
    p.add_argument("--transparent", action="store_true")
    args = p.parse_args()

    channel = pick_channel()
    if not channel:
        emit({"ok": False, "error": "NO_BROWSER",
              "hint": "未找到 Edge/Chrome,无法渲染"})
        return 2

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        emit({"ok": False, "error": "NO_PLAYWRIGHT",
              "hint": "pip install playwright", "detail": str(exc)})
        return 3

    is_dir = os.path.isdir(args.source)
    srv = None
    if is_dir:
        srv, base = serve(os.path.abspath(args.source))
        url = base + "/" + (resolve_index(args.source) or "index.html")
    else:
        url = "file:///" + urllib.parse.quote(
            os.path.abspath(args.source).replace("\\", "/"))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=channel, headless=True)
        try:
            ctx = browser.new_context(
                viewport={"width": args.width, "height": args.width},
                device_scale_factor=args.scale,
            )
            page = ctx.new_page()
            page.emulate_media(reduced_motion="reduce")
            page.goto(url, wait_until="load", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:  # noqa: BLE001
                pass
            page.evaluate("() => document.fonts ? document.fonts.ready : true")
            page.wait_for_timeout(400)

            if args.height > 0:
                page.set_viewport_size(
                    {"width": args.width, "height": args.height})
                page.wait_for_timeout(200)
                image = page.screenshot(omit_background=args.transparent)
            else:
                image = page.screenshot(
                    full_page=True, omit_background=args.transparent)
            with open(args.output, "wb") as f:
                f.write(image)
            emit({"ok": True, "path": os.path.abspath(args.output),
                  "engine": f"fallback:{channel}", "scale": args.scale})
            return 0
        except Exception as exc:  # noqa: BLE001
            emit({"ok": False, "error": type(exc).__name__, "detail": str(exc)})
            return 1
        finally:
            browser.close()
            if srv:
                srv.shutdown()


def resolve_index(directory: str) -> str | None:
    for name in ("index.html", "index.htm"):
        if os.path.isfile(os.path.join(directory, name)):
            return name
    htmls = [f for f in os.listdir(directory) if f.lower().endswith(".html")]
    return htmls[0] if htmls else None


if __name__ == "__main__":
    sys.exit(main())
