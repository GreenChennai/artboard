"""Render an SVG (or HTML) to PNG via headless browser — QA preview + PNG delivery.

  python scripts/svg_preview.py assets/map/samples/svg-cbd.svg --out assets/preview.png \
      [--width 1600] [--height 0=auto] [--scale 2]

浏览器 = VB_BROWSER_PATH > artboard _paths(Chrome/Edge)> Playwright 自带 chromium。
"""
import argparse, base64, os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _map_common import launch_kwargs
from PIL import Image


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=0, help="0 = svg's own width attr")
    ap.add_argument("--height", type=int, default=0, help="0 = keep aspect from width attr")
    ap.add_argument("--scale", type=int, default=2)
    args = ap.parse_args()

    src = os.path.abspath(args.source)
    ext = os.path.splitext(src)[1].lower()
    mime = {"svg": "image/svg+xml", "html": "text/html"}.get(ext.strip("."), "application/octet-stream")
    b64 = base64.b64encode(open(src, "rb").read()).decode()

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
      html,body {{ margin:0; padding:0; background:#fff; }}
      #wrap {{ display:inline-block; }}
      #wrap img {{ display:block; }}
    </style></head><body><div id="wrap">
      <img id="pic" src="data:{mime};base64,{b64}">
    </div></body></html>"""

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_kwargs())
        page = browser.new_page(device_scale_factor=args.scale,
                                viewport={"width": 900, "height": 700})
        page.set_content(html)
        page.wait_for_timeout(500)
        if args.width or args.height:
            style = f"width:{args.width}px" if args.width else ""
            if args.height:
                style += f";height:{args.height}px"
            page.eval_on_selector("#pic", f"el => el.style.cssText = '{style}'")
            page.wait_for_timeout(300)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        page.locator("#wrap").screenshot(path=args.out)
        browser.close()
    im = Image.open(args.out)
    print(f"saved {args.out} {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main()
