"""artboard 溢出机检:找出"文字越出容器边框"与"内容溢出自身盒"。

为什么需要它:读导出图看不出「文字出卡片但没出画布」——线条颜色相近时肉眼无感,
而所有人工自检(guardrails §9 / rubric / typography §六)都以**画布**为参照系,
这类缺陷会全部通过。只有几何量测能看见。

用法:
  python check_overflow.py <项目目录|src目录|HTML文件>
  python check_overflow.py src --width 1080 --height 1440 --tol 2
  python check_overflow.py src --all          # 连"已设 overflow 收口"的也报(clamp 体检)
输出:stdout 单行 JSON;人类可读清单走 stderr。退出码 0=无问题 / 1=有越界 / 2=用法错

两类检测:
  A 内容溢出自身盒:scrollHeight > clientHeight + tol 且**未设 overflow 收口**
    —— 真问题(定高卡片 + 长文案,内容会画到盒外)
  B 越出绘制的祖先:文字盒超出最近"有背景色或可见边框"的祖先的 border-box
    —— 更贴近"文字突破底层边框"

豁免:
  - 任何 `data-allow-overflow` 元素及其子树(装饰:光晕/放射线/水印)
  - 画布级容器(.poster/.stage/.bg)不算"卡片祖先"
  - A 类中已设 overflow:hidden|clip|auto|scroll 的盒默认跳过(那是有意收口)
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import socket
import sys
import threading
import urllib.parse

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
from _config import cfg  # noqa: E402
from _paths import pick_channel  # noqa: E402

CANVAS_CLASSES = ("poster", "stage", "canvas", "bg", "backdrop")

DETECT_JS = r"""
(payload) => {
  const TOL = payload.tol, CHECK_CLAMPED = payload.all;
  const CANVAS_CLASSES = payload.canvasClasses;
  const issues = [];
  const SEL = (el) => {
    if (!el || el === document.body) return 'body';
    if (el.id) return '#' + el.id;
    let cls = '';
    if (typeof el.className === 'string' && el.className.trim())
      cls = '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.');
    return el.tagName.toLowerCase() + cls;
  };
  const alphaOf = (c) => {
    if (!c) return 0;
    const m = String(c).match(/rgba?\(([^)]+)\)/);
    if (!m) return 0;
    const p = m[1].split(/[, ]+/).map(Number);
    return p.length > 3 ? p[3] : 1;
  };
  const painted = (el) => {
    const s = getComputedStyle(el);
    if (alphaOf(s.backgroundColor) > 0.02) return true;
    const bw = [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth]
      .map(v => parseFloat(v) || 0);
    if (bw.some(w => w > 0) && alphaOf(s.borderTopColor) > 0.02) return true;
    return false;
  };
  const isCanvas = (el) => {
    if (!el.classList) return false;
    return CANVAS_CLASSES.some(c => el.classList.contains(c));
  };
  const skip = (el) => !!(el.closest && el.closest('[data-allow-overflow]'));
  const hasDirectText = (el) =>
    [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 0);
  const seamed = (s) => /hidden|clip|auto|scroll/.test(s.overflowY) ||
                        /hidden|clip|auto|scroll/.test(s.overflowX);

  // ---- A 类:内容溢出自身盒 ----
  // 只查**有背景或边框**的盒(painted):无绘制的纯文字元素(如 h1)内容略大于自身盒
  // 是行盒(line box < 字体 content area)的正常现象,不构成本册要治的"文字突破底层边框"。
  for (const el of document.querySelectorAll('body *')) {
    if (skip(el)) continue;
    const s = getComputedStyle(el);
    if (s.display === 'inline') continue;
    if (!painted(el)) continue;
    if (seamed(s) && !CHECK_CLAMPED) continue;
    const dY = el.scrollHeight - el.clientHeight;
    const dX = el.scrollWidth - el.clientWidth;
    if (dY > TOL || dX > TOL) {
      const which = (dY > TOL ? '高 ' + dY + 'px ' : '') + (dX > TOL ? '宽 ' + dX + 'px' : '');
      issues.push({ type: 'A', selector: SEL(el),
        overflowY: Math.max(0, dY), overflowX: Math.max(0, dX),
        clamped: seamed(s),
        hint: seamed(s) ? '已设 overflow 收口(clamp 体检模式,内容' + which + ')'
                        : '内容比盒大(' + which + '),且未设 overflow 收口' });
    }
  }

  // ---- B 类:文字越出"绘制的祖先" ----
  const R = (el) => el.getBoundingClientRect();
  for (const el of document.querySelectorAll('body *')) {
    if (!hasDirectText(el) || skip(el)) continue;
    const r = R(el);
    if (r.width < 1 || r.height < 1) continue;
    let a = el.parentElement, guard = 0;
    while (a && guard++ < 15) {
      if (isCanvas(a) || a === document.body || a === document.documentElement) { a = null; break; }
      if (painted(a)) break;
      a = a.parentElement;
    }
    if (!a || skip(a)) continue;
    const sA = getComputedStyle(a);
    const bt = parseFloat(sA.borderTopWidth) || 0, br = parseFloat(sA.borderRightWidth) || 0;
    const bb = parseFloat(sA.borderBottomWidth) || 0, bl = parseFloat(sA.borderLeftWidth) || 0;
    const ar = R(a);
    const out = {
      top:    Math.round(ar.top + bt - r.top),
      right:  Math.round(r.right - (ar.right - br)),
      bottom: Math.round(r.bottom - (ar.bottom - bb)),
      left:   Math.round(ar.left + bl - r.left),
    };
    const worst = Math.max(out.top, out.right, out.bottom, out.left);
    if (worst > TOL) {
      const dirs = Object.entries(out).filter(([, v]) => v > TOL)
        .map(([k, v]) => k + ' ' + v + 'px').join(', ');
      issues.push({ type: 'B', selector: SEL(el), ancestor: SEL(a),
        top: Math.max(0, out.top), right: Math.max(0, out.right),
        bottom: Math.max(0, out.bottom), left: Math.max(0, out.left),
        hint: '越出 ' + SEL(a) + ' 边框:' + dirs });
    }
  }
  return issues.slice(0, 300);
}
"""


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def serve(directory: str) -> tuple[http.server.ThreadingHTTPServer, str]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a) -> None:
            pass

    handler = lambda *a, **k: Quiet(*a, directory=directory, **k)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{port}"


def resolve_source(source: str) -> tuple[str, str, str]:
    """返回 (类型, 路径, URL 或待建服务目录)。"""
    src = os.path.abspath(source)
    if os.path.isdir(src):
        if os.path.isfile(os.path.join(src, "src", "index.html")):
            src = os.path.join(src, "src")          # 项目目录
        if not os.path.isfile(os.path.join(src, "index.html")):
            htmls = [f for f in os.listdir(src) if f.lower().endswith((".html", ".htm"))]
            if not htmls:
                return "missing", src, ""
            return "dir", src, sorted(htmls)[0]
        return "dir", src, "index.html"
    if os.path.isfile(src):
        return "file", src, ""
    return "missing", src, ""


def canvas_size(source_dir: str, arg_w: int, arg_h: int) -> tuple[int, int]:
    if arg_w and arg_h:
        return arg_w, arg_h
    for cand in (os.path.join(source_dir, "project.json"),
                 os.path.join(os.path.dirname(source_dir), "project.json")):
        if os.path.isfile(cand):
            try:
                with open(cand, encoding="utf-8") as f:
                    j = json.load(f)
                return int(arg_w or j.get("width") or 1080), int(arg_h or j.get("height") or 0)
            except (OSError, ValueError):
                break
    return arg_w or 1080, arg_h or 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="artboard 溢出机检(文字越出容器边框)")
    p.add_argument("source", help="项目目录 / src 目录 / HTML 文件")
    p.add_argument("--width", type=int, default=0)
    p.add_argument("--height", type=int, default=0)
    p.add_argument("--tol", type=int, default=4,
                   help="容差 px(默认 4:行盒亚像素差、letter-spacing 余量、"
                        "1px 描边等不计;要严可 --tol 1)")
    p.add_argument("--all", action="store_true",
                   help="连已设 overflow 收口的盒也报(clamp 体检)")
    args = p.parse_args()

    kind, path, index = resolve_source(args.source)
    if kind == "missing":
        emit({"ok": False, "error": "NO_HTML", "detail": path,
              "hint": "--source 应是项目目录(内含 src/index.html)、src/ 或 HTML 文件"})
        return 2

    channel = pick_channel()
    if not channel:
        emit({"ok": False, "error": "NO_BROWSER",
              "hint": "未找到 Edge/Chrome(含用户级安装);本检查需 Playwright 渲染"})
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        emit({"ok": False, "error": "NO_PLAYWRIGHT",
              "hint": "pip install playwright", "detail": str(exc)})
        return 2

    w, h = canvas_size(path if kind == "dir" else os.path.dirname(path),
                       args.width, args.height)
    srv = None
    if kind == "dir":
        srv, base = serve(path)
        url = f"{base}/{urllib.parse.quote(index)}"
    else:
        url = "file:///" + urllib.parse.quote(path.replace("\\", "/"))

    issues: list[dict] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel=channel, headless=True)
            try:
                page = browser.new_page(
                    viewport={"width": w or 1080, "height": h or 1440},
                    device_scale_factor=1)
                page.emulate_media(reduced_motion="reduce")
                page.goto(url, wait_until="load", timeout=30000)
                try:
                    page.wait_for_load_state("networkidle", timeout=3000)
                except Exception:  # noqa: BLE001
                    pass
                page.evaluate("() => document.fonts ? document.fonts.ready : true")
                page.wait_for_timeout(500)          # 字体落位后再量,防假报
                issues = page.evaluate(DETECT_JS, {
                    "tol": args.tol, "all": args.all,
                    "canvasClasses": list(CANVAS_CLASSES)})
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001
        emit({"ok": False, "error": type(exc).__name__, "detail": str(exc)})
        return 1
    finally:
        if srv:
            srv.shutdown()

    out = {"ok": not issues, "source": url, "canvas": {"width": w, "height": h},
           "count": len(issues), "issues": issues}
    emit(out)

    if issues:
        print(f"\n发现 {len(issues)} 处越界(容差 {args.tol}px):", file=sys.stderr)
        for i in issues[:30]:
            tag = "A 内容溢出自身盒" if i["type"] == "A" else "B 越出容器边框"
            print(f"  ✗ [{tag}] {i['selector']}"
                  + (f"  祖先 {i['ancestor']}" if i.get("ancestor") else "")
                  + f" — {i['hint']}", file=sys.stderr)
        if len(issues) > 30:
            print(f"  … 其余 {len(issues) - 30} 处见 JSON", file=sys.stderr)
        print("\n  修法见 references/card-layout.md §五「一行修复对照表」;"
              "\n  装饰元素可加 data-allow-overflow 豁免。", file=sys.stderr)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
