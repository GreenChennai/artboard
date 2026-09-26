"""artboard 溢出与安全区机检。

为什么需要它:读导出图看不出「文字出卡片但没出画布」与「内容进了字幕带」——
线条/颜色相近时肉眼无感,而所有人工自检(guardrails §9 / rubric / typography §六)
都以**画布**为参照系,这两类缺陷会全部通过。只有几何量测能看见。

用法:
  # 静态海报:查容器越框
  python check_overflow.py <项目目录|src目录|HTML文件>
  python check_overflow.py src --width 1080 --height 1440 --tol 2
  python check_overflow.py src --all                 # 连"已设 overflow 收口"的也报(clamp 体检)

  传**目录**时会逐页查该目录下所有 HTML(多页 PPT/三折页不再只查第一页);
  传单个文件只查该文件。

  # 视频卡:再加查内容是否越出安全区(字幕带 / 平台按钮列)
  python check_overflow.py src --safe-area 9x16                    # 标准档(保守交集)
  python check_overflow.py src --safe-area 9x16 --safe-tier tight  # 内容多时的紧凑档
  python check_overflow.py src --safe-area 9x16 --safe-tier extreme # 极限档(四边 2.5%)
  python check_overflow.py src --safe-inset 48,27,48,27            # 直接给 px(上右下左)

  # 版面复核:查内容元素互相重叠(吸底块顶穿页脚这类,A/B 都看不见)
  python check_overflow.py src --overlap

输出:stdout 单行 JSON;人类可读清单走 stderr。退出码 0=无问题 / 1=有越界 / 2=用法错

四类检测:
  A 内容溢出自身盒:scrollHeight > clientHeight + tol 且**未设 overflow 收口**
    —— 真问题(定高卡片 + 长文案,内容会画到盒外)
  B 越出绘制的祖先:文字盒超出最近"有背景色或可见边框"的祖先的 border-box
    —— 更贴近"文字突破底层边框"
  C 越出安全区(需 --safe-area):内容盒超出视频安全区矩形
    —— 字幕带 / 平台 UI 遮挡带,细则见 references/video-safe-area.md
  D 元素互相重叠(需 --overlap):两个内容元素的盒实叠 ≥20%
    —— 各自都没越界但版面已经叠了;有意的图层叠压加 data-allow-overlap

豁免:
  - 任何 `data-allow-overflow` 元素及其子树(装饰:光晕/放射线/水印)
  - `data-allow-overlap` 元素及其子树只豁免 D 类
  - 画布级容器(.poster/.stage/.bg)不算"卡片祖先",也不算安全区违规的主体
  - A 类中已设 overflow:hidden|clip|auto|scroll 的盒默认跳过(那是有意收口)
  - C 类只报**最外层**越界的元素(父子重复不刷屏)
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

# 安全区三档:每档四边保留量,单位 %(顶/底按 H,左右按 W)。
#   standard = 跨平台保守交集(video-safe-area.md §二)
#   tight    = 内容较多时的紧凑档:垂直方向压到有依据的下限;
#              **9:16 左右仍保持 17%** —— 右侧平台按钮列是硬约束,压不动
#   extreme  = 极限档:四边统一 2.5%,几乎贴画布边。代价见 video-safe-area.md §三
SAFE_TIERS: dict[str, dict[str, tuple[float, float, float, float]]] = {
    #           (top%, right%, bottom%, left%)
    "9x16": {
        "standard": (12.0, 17.0, 30.0, 17.0),
        "tight": (7.0, 17.0, 25.0, 17.0),
        "extreme": (2.5, 2.5, 2.5, 2.5),
    },
    "16x9": {
        "standard": (10.0, 8.0, 16.0, 8.0),
        "tight": (7.0, 5.0, 12.0, 5.0),
        "extreme": (2.5, 2.5, 2.5, 2.5),
    },
    "3x4": {
        "standard": (10.0, 7.0, 18.0, 7.0),
        "tight": (7.0, 5.0, 13.0, 5.0),
        "extreme": (2.5, 2.5, 2.5, 2.5),
    },
    # ↓ 三档为工程取值(未实测;video-motion.md §六 提案,video-safe-area.md §2.0)
    "1x1": {
        "standard": (8.0, 8.0, 8.0, 8.0),
        "tight": (8.0, 8.0, 8.0, 8.0),
        "extreme": (2.5, 2.5, 2.5, 2.5),
    },
    "4x5": {
        "standard": (8.0, 8.0, 16.0, 8.0),
        "tight": (8.0, 8.0, 16.0, 8.0),
        "extreme": (2.5, 2.5, 2.5, 2.5),
    },
    "2.35x1": {
        "standard": (5.0, 5.0, 5.0, 5.0),
        "tight": (5.0, 5.0, 5.0, 5.0),
        "extreme": (2.5, 2.5, 2.5, 2.5),
    },
}
SAFE_LABEL = {"standard": "标准(跨平台交集)", "tight": "紧凑(内容多)",
              "extreme": "极限(几乎贴边,有代价)"}


def guess_ratio(w: int, h: int) -> str:
    """按画布尺寸猜画幅;猜不出返回 9x16 基准比并让调用方提示。"""
    if not w or not h:
        return "9x16"
    r = w / h
    for name, (rw, rh) in (("9x16", (9, 16)), ("3x4", (3, 4)), ("1x1", (1, 1)),
                           ("4x5", (4, 5)), ("16x9", (16, 9)), ("2.35x1", (2.35, 1))):
        if abs(r - rw / rh) < 0.02:
            return name
    return "9x16" if r < 1 else "16x9"


def resolve_safe(args) -> dict | None:
    """解析安全区规则。返回 {mode,top,right,bottom,left,ratio,tier,label} 或 None。

    mode:
      'pct'  四边为百分比,由页面按**画布实际尺寸**换算(长图 h 未知也不受影响)
      'px'   四边为绝对像素
      'auto' 画幅由页面按画布长宽比判定,四边取自 SAFE_TIERS[判出的画幅][tier]
    **不在 Python 侧换算 px** —— 交给渲染后的真实几何算才准。
    """
    tier = args.safe_tier
    if tier not in SAFE_LABEL:
        return {"error": f"未知档位 {tier};可选 {'/'.join(SAFE_LABEL)}"}

    if args.safe_inset:
        parts = [p.strip() for p in args.safe_inset.split(",")]
        if len(parts) == 1:
            parts *= 4
        if len(parts) != 4:
            return {"error": "--safe-inset 需要 1 个或 4 个值(上,右,下,左),"
                             f"收到 {len(parts)} 个"}
        out: dict = {"mode": "px", "tier": tier, "ratio": None,
                     "tierLabel": SAFE_LABEL[tier], "label": "自定义 --safe-inset"}
        for name, v in zip(("top", "right", "bottom", "left"), parts):
            try:
                if v.endswith("%"):
                    out["mode"] = "pct"
                    out[name] = float(v[:-1])
                else:
                    out[name] = float(v)
            except ValueError:
                return {"error": f"--safe-inset 的 {name} 值不是数字/百分比: {v}"}
        return out

    if not args.safe_area:
        return None

    if args.safe_area == "auto":
        return {"mode": "auto", "ratio": "auto", "tier": tier,
                "tierLabel": SAFE_LABEL[tier], "label": "auto(页内判定画幅)"}

    ratio = args.safe_area
    if ratio not in SAFE_TIERS:
        return {"error": f"未知画幅 {ratio};可选 {'/'.join(SAFE_TIERS)} 或 auto"}
    t, r, b, l = SAFE_TIERS[ratio][tier]
    return {"mode": "pct", "top": t, "right": r, "bottom": b, "left": l,
            "ratio": ratio, "tier": tier, "tierLabel": SAFE_LABEL[tier],
            "label": f"{ratio} {SAFE_LABEL[tier]}"}

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

  // ---- C 类:内容越出安全区(需 --safe-area;视频卡防字幕/平台 UI 遮挡)----
  var safeInfo = null;
  if (payload.safe) {
    const S = payload.safe;
    const host = document.querySelector('.poster, .stage, .canvas') || document.body;
    const hr = R(host);
    const hw = hr.width, hh = hr.height;
    const guessRatio = (w, h) => {
      const r = w / h;
      const cands = [['9x16', 9 / 16], ['3x4', 3 / 4], ['16x9', 16 / 9]];
      for (const c of cands) { if (Math.abs(r - c[1]) < 0.02) return c[0]; }
      return r < 1 ? '9x16' : '16x9';
    };
    const ratio = S.mode === 'auto' ? guessRatio(hw, hh) : (S.ratio || '9x16');
    let vals;
    if (S.mode === 'auto') {
      const tbl = (payload.safeTiers || {})[ratio] || {};
      vals = tbl[S.tier] || [0, 0, 0, 0];
    } else {
      vals = [S.top, S.right, S.bottom, S.left];
    }
    // 百分比按**对应边**换算:上/下用 H,左/右用 W
    const toPx = (i) => (S.mode === 'px' ? vals[i]
      : Math.round(vals[i] / 100 * ((i === 1 || i === 3) ? hw : hh)));
    const insT = toPx(0), insR = toPx(1), insB = toPx(2), insL = toPx(3);
    const safeRect = { top: hr.top + insT, right: hr.right - insR,
                       bottom: hr.bottom - insB, left: hr.left + insL };
    const label = S.mode === 'auto' ? (ratio + ' ' + (S.tierLabel || S.tier)) : S.label;
    const actualRatio = guessRatio(hw, hh);
    safeInfo = {
      label: label, ratio: ratio, tier: S.tier,
      canvas: { width: Math.round(hw), height: Math.round(hh) },
      actualRatio: actualRatio,
      ratioMismatch: !!(S.mode === 'pct' && S.ratio && S.ratio !== actualRatio),
      inset: { top: insT, right: insR, bottom: insB, left: insL },
      usable: { width: Math.round(hw - insL - insR),
                height: Math.round(hh - insT - insB) },
      rect: { x: Math.round(safeRect.left - hr.left), y: Math.round(safeRect.top - hr.top),
              w: Math.round(safeRect.right - safeRect.left),
              h: Math.round(safeRect.bottom - safeRect.top) }
    };

    const CONTENT_TAGS = ['IMG', 'SVG', 'CANVAS', 'VIDEO', 'PICTURE'];
    const isContent = (el) => hasDirectText(el) || CONTENT_TAGS.includes(el.tagName);
    const outs = [];
    for (const el of document.querySelectorAll('body *')) {
      if (skip(el) || !isContent(el)) continue;
      if (isCanvas(el)) continue;                  // 画布自身不算内容主体
      const r = R(el);
      if (r.width < 1 || r.height < 1) continue;
      const o = {
        top:    Math.round(safeRect.top - r.top),
        right:  Math.round(r.right - safeRect.right),
        bottom: Math.round(r.bottom - safeRect.bottom),
        left:   Math.round(safeRect.left - r.left),
      };
      if (Math.max(o.top, o.right, o.bottom, o.left) > TOL) outs.push({ el: el, o: o });
    }
    // 只报最外层越界元素,避免父子把同一处刷成多行
    const hit = new Set();
    for (const x of outs) hit.add(x.el);
    for (const x of outs) {
      let p = x.el.parentElement, nested = false;
      while (p) { if (hit.has(p)) { nested = true; break; } p = p.parentElement; }
      if (nested) continue;
      const dirs = Object.entries(x.o).filter(function (kv) { return kv[1] > TOL; })
        .map(function (kv) { return kv[0] + ' ' + kv[1] + 'px'; }).join(', ');
      issues.push({ type: 'C', selector: SEL(x.el),
        top: Math.max(0, x.o.top), right: Math.max(0, x.o.right),
        bottom: Math.max(0, x.o.bottom), left: Math.max(0, x.o.left),
        hint: '越出安全区(' + label + '):' + dirs });
    }
  }

  // ---- D 类:内容元素互相重叠(需 --overlap;绝对定位吸底块顶穿页脚等高发)----
  // A/B 都只问「谁越出了谁」,两个各自安分的元素叠在一起谁都查不出来
  // (margin-top:auto 的统计卡顶穿绝对定位页脚就是这类)。默认关:图层
  // 叠压是有意设计,只有明确怀疑版面时才开。
  if (payload.overlap) {
    const items = [];
    let scanned = 0;
    for (const el of document.querySelectorAll('body *')) {
      if (scanned++ > 2000) break;
      if (isCanvas(el) || !hasDirectText(el)) continue;
      if (el.closest('[data-allow-overflow], [data-allow-overlap]')) continue;
      const s = getComputedStyle(el);
      if (s.display === 'none' || s.visibility === 'hidden') continue;
      if (parseFloat(s.opacity) < 0.05) continue;
      const r = R(el);
      if (r.width < 2 || r.height < 2) continue;
      items.push({ el: el, r: r });
    }
    const seen = {};
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const a = items[i], b = items[j];
        if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
        const ox = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
        const oy = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
        if (ox <= TOL || oy <= TOL) continue;
        const area = ox * oy;
        const smaller = Math.min(a.r.width * a.r.height, b.r.width * b.r.height);
        if (smaller <= 0 || area / smaller < 0.2) continue;   // 轻擦不算,只报实叠
        const key = SEL(a.el) + '|' + SEL(b.el);
        if (seen[key]) continue;
        seen[key] = 1;
        issues.push({ type: 'D', selector: SEL(a.el), other: SEL(b.el),
          overlapX: Math.round(ox), overlapY: Math.round(oy),
          ratio: Math.round(area / smaller * 100) / 100,
          hint: '与 ' + SEL(b.el) + ' 重叠 ' + Math.round(ox) + '×' + Math.round(oy) +
                'px(占较小者 ' + Math.round(area / smaller * 100) + '%;' +
                '有意的图层叠压请加 data-allow-overlap)' });
      }
    }
  }
  return { issues: issues.slice(0, 300), safe: safeInfo };
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


def resolve_source(source: str) -> tuple[str, str, list[str]]:
    """返回 (类型, 目录/文件路径, 待检 HTML 列表)。

    dir  : 列表为目录下的 HTML 文件名,`index.html` 排最前
    file : 列表为单个绝对路径

    目录模式**不再只挑一个文件**:PPT/三折页等多页品类每页一个 HTML,
    只取 `index.html` 或 `sorted()[0]` 会让其余页面全部漏检——机检「通过」
    其实一页都没查。
    """
    src = os.path.abspath(source)
    if os.path.isdir(src):
        if os.path.isfile(os.path.join(src, "src", "index.html")):
            src = os.path.join(src, "src")          # 项目目录
        htmls = sorted(f for f in os.listdir(src)
                       if f.lower().endswith((".html", ".htm")))
        if not htmls:
            return "missing", src, []
        if "index.html" in htmls:
            htmls.remove("index.html")
            htmls.insert(0, "index.html")
        return "dir", src, htmls
    if os.path.isfile(src):
        return "file", src, [src]
    return "missing", src, []


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
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    p = argparse.ArgumentParser(
        description="artboard 溢出与安全区机检(文字越出容器边框 / 内容进字幕带)")
    p.add_argument("source", help="项目目录 / src 目录 / HTML 文件")
    p.add_argument("--width", type=int, default=0)
    p.add_argument("--height", type=int, default=0)
    p.add_argument("--tol", type=int, default=4,
                   help="容差 px(默认 4:行盒亚像素差、letter-spacing 余量、"
                        "1px 描边等不计;要严可 --tol 1)")
    p.add_argument("--all", action="store_true",
                   help="连已设 overflow 收口的盒也报(clamp 体检)")
    p.add_argument("--safe-area", default="",
                   help="启用安全区检查:9x16 / 16x9 / 3x4 / auto(按画布比例判)")
    p.add_argument("--safe-tier", default="standard",
                   choices=list(SAFE_LABEL),
                   help="安全区档位:standard 跨平台交集(默认)/ tight 内容多时的紧凑档 / "
                        "extreme 极限档(四边 2.5%%,几乎贴边,有代价)")
    p.add_argument("--safe-inset", default="",
                   help="直接给四边保留量,如 48,27,48,27(上,右,下,左)或 2.5%%,"
                        "或单个值表示四边相同;优先级高于 --safe-area")
    p.add_argument("--overlap", action="store_true",
                   help="追加 D 类:内容元素互相重叠(绝对定位吸底块顶穿页脚等高发);"
                        "有意的图层叠压加 data-allow-overlap 豁免")
    args = p.parse_args()

    safe = resolve_safe(args)
    if safe and safe.get("error"):
        emit({"ok": False, "error": "BAD_SAFE_ARGS", "detail": safe["error"]})
        return 2

    kind, path, targets = resolve_source(args.source)
    if kind == "missing":
        emit({"ok": False, "error": "NO_HTML", "detail": path,
              "hint": "--source 应是项目目录(内含 src/index.html 或若干 .html)、"
                      "src/ 或 HTML 文件"})
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
        # 目录模式下**逐页查**:每页一个 HTML 的多页品类(PPT/三折页)全都在列
        plan = [(name, f"{base}/{urllib.parse.quote(name)}") for name in targets]
    else:
        plan = [(os.path.basename(path),
                 "file:///" + urllib.parse.quote(path.replace("\\", "/")))]

    issues: list[dict] = []
    files: list[dict] = []
    safe_used: dict | None = None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel=channel, headless=True)
            try:
                page = browser.new_page(
                    viewport={"width": w or 1080, "height": h or 1440},
                    device_scale_factor=1)
                page.emulate_media(reduced_motion="reduce")
                for name, url in plan:
                    page.goto(url, wait_until="load", timeout=30000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=3000)
                    except Exception:  # noqa: BLE001
                        pass
                    page.evaluate("() => document.fonts ? document.fonts.ready : true")
                    page.wait_for_timeout(500)      # 字体落位后再量,防假报
                    res = page.evaluate(DETECT_JS, {
                        "tol": args.tol, "all": args.all, "safe": safe,
                        "overlap": args.overlap,
                        "safeTiers": SAFE_TIERS,
                        "canvasClasses": list(CANVAS_CLASSES)})
                    page_issues = res.get("issues", [])
                    for it in page_issues:
                        it["file"] = name
                    issues.extend(page_issues)
                    safe_used = res.get("safe") or safe_used
                    files.append({"file": name, "url": url,
                                  "count": len(page_issues), "ok": not page_issues})
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001
        emit({"ok": False, "error": type(exc).__name__, "detail": str(exc),
              "files": files})
        return 1
    finally:
        if srv:
            srv.shutdown()

    out = {"ok": not issues,
           "source": plan[0][1] if len(plan) == 1 else path,
           "canvas": {"width": w, "height": h},
           "files": files, "count": len(issues), "issues": issues}
    if safe_used:
        out["safe_area"] = safe_used
    emit(out)

    TAGS = {"A": "A 内容溢出自身盒", "B": "B 越出容器边框", "C": "C 越出安全区",
            "D": "D 元素互相重叠"}
    if safe_used:
        si = safe_used
        print(f"\n安全区 {si['label']}  画布 {si['canvas']['width']}×"
              f"{si['canvas']['height']}", file=sys.stderr)
        print(f"  四边保留 上{si['inset']['top']} 右{si['inset']['right']} "
              f"下{si['inset']['bottom']} 左{si['inset']['left']}  →  可用 "
              f"{si['usable']['width']}×{si['usable']['height']}", file=sys.stderr)
        if si.get("ratioMismatch"):
            print(f"  △ 画幅不符:你指定 {si['ratio']},而画布实际是 "
                  f"{si['actualRatio']} —— 百分比已按实际画布边长换算,"
                  f"\n    但这通常不是你想要的。改用 --safe-area auto 让程序自己判。",
                  file=sys.stderr)

    if len(files) > 1:
        print(f"\n逐页结果({len(files)} 个页面,逐页查而非只查一个):", file=sys.stderr)
        for f in files:
            mark = "✓" if f["ok"] else "✗"
            print(f"  {mark} {f['file']}" + ("" if f["ok"] else f"  {f['count']} 处"),
                  file=sys.stderr)

    if issues:
        print(f"\n发现 {len(issues)} 处越界(容差 {args.tol}px):", file=sys.stderr)
        multi = len(files) > 1
        for i in issues[:30]:
            tag = TAGS.get(i["type"], i["type"])
            where = f"[{i['file']}] " if multi and i.get("file") else ""
            print(f"  ✗ [{tag}] {where}{i['selector']}"
                  + (f"  祖先 {i['ancestor']}" if i.get("ancestor") else "")
                  + (f"  与 {i['other']}" if i.get("other") else "")
                  + f" — {i['hint']}", file=sys.stderr)
        if len(issues) > 30:
            print(f"  … 其余 {len(issues) - 30} 处见 JSON", file=sys.stderr)
        kinds = {i["type"] for i in issues}
        print("", file=sys.stderr)
        if kinds & {"A", "B"}:
            print("  容器越框修法见 references/card-layout.md §五「一行修复对照表」;"
                  "\n  装饰元素可加 data-allow-overflow 豁免。", file=sys.stderr)
        if "C" in kinds:
            print("  安全区越界见 references/video-safe-area.md:"
                  "\n    · 先试 content 精简 / 拆卡(比贴边更稳)"
                  "\n    · 空间确实不够 → --safe-tier tight(垂直放宽,左右不动)"
                  "\n    · 仍不够 → --safe-tier extreme(四边 2.5%,字幕/按钮会盖住边缘内容)",
                  file=sys.stderr)
        if "D" in kinds:
            print("  元素重叠:改文案/换行最容易触发(吸底块变高顶穿页脚)。"
                  "\n    · 首选让父容器 flex 消化高度,别让两块各自定位"
                  "\n    · 有意的叠压(标题压图)加 data-allow-overlap 豁免",
                  file=sys.stderr)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
