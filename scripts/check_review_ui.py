"""审片台页面自检(不用浏览器):id 引用 / 页签配对 / 与影片页 DOM 是否一致。

为什么需要它:审片台的失效方式**几乎都是静默的** ——
  ① JS 里 `$("x")` / `getElementById("x")` 引用的 id 在 HTML 里不存在 →
     `Cannot set properties of null`,页面半瘫(按钮全不响应,控制台只有一行);
  ② 页签 `data-tab` 指向的面板不存在 → 切过去是空白,不会报错;
  ③ 审片台页面是**影片页的复制品 + 一层 UI**,复制品少了 `#prog` 这类元素,
     预览就会和成片差一条 —— 这种差异肉眼极难发现。
三条都是纯文本可判的,所以放在 Step 6 机检里跑(零 token、不用浏览器)。

用法:
  python check_review_ui.py --root <项目>
  python check_review_ui.py --root <项目> --tool <技能>/tools/review-station
  python check_review_ui.py --root <项目> --page review.html --film src/index.html
输出:stdout 单行 JSON;人类可读清单走 stderr。退出码 0=通过 / 1=有缺失 / 2=用法错。

判据(与来源工程一致,但**去掉了项目专属的白名单**):
  ① review.js 引用的 id ⊆ review.html 定义的 id(运行时才建的元素用 --dynamic-id 追加);
  ② 每个 `data-tab="x"` 都有对应的 `.rv-panel#x` 面板;
  ③ 审片台页面 `<div id="stage">` 内的 id 集合与 canvas 标签,必须与影片页**完全一致**
     (多了少了都报,不做"必须含某些 id"的硬编码)。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT_DEFAULT = os.getcwd()
# 「运行时才创建」的元素:静态检查会误报,可按项目追加(逗号分隔)
DEFAULT_DYNAMIC = "rv-diffcv"


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def film_dom(html: str) -> tuple[list[str], list[str]]:
    """取 `<div id="stage">` 里的 id 列表与 canvas 标签(与影片页对齐用)。"""
    m = re.search(r'<div id="stage">(.*?)</div>\s*(?:<div id="prog">|</div>)', html, re.S)
    if not m:
        m = re.search(r'<div id="stage">(.*?)</div>\s*\n', html, re.S)
    seg = m.group(1) if m else ""
    return re.findall(r'id="([^"]+)"', seg), re.findall(r"<canvas[^>]*>", seg)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:                               # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="审片台页面自检(id 引用 / 页签配对 / DOM 一致性)")
    ap.add_argument("--root", default="", help="项目根(默认当前目录;用来找影片页)")
    ap.add_argument("--tool", default="", help="审片台目录(默认 <技能根>/tools/review-station)")
    ap.add_argument("--page", default="review.html")
    ap.add_argument("--script", default="review.js")
    ap.add_argument("--film", default="src/index.html", help="影片页(相对 --root)")
    ap.add_argument("--dynamic-id", default=DEFAULT_DYNAMIC,
                    help="运行时才创建的元素 id,静态检查豁免(逗号分隔)")
    args = ap.parse_args()

    root = os.path.abspath(args.root or ROOT_DEFAULT)
    tool = os.path.abspath(args.tool) if args.tool else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "review-station")
    page_p = os.path.join(tool, args.page)
    script_p = os.path.join(tool, args.script)
    film_p = os.path.join(root, args.film)
    missing = [p for p in (page_p, script_p) if not os.path.isfile(p)]
    if missing:
        emit({"ok": False, "error": "NO_TOOL_FILES", "detail": missing,
              "hint": "--tool 指向审片台目录(内含 review.html / review.js)"})
        return 2
    skip_film = not args.film.strip()
    if not skip_film and not os.path.isfile(film_p):
        emit({"ok": False, "error": "NO_FILM_PAGE", "detail": film_p,
              "hint": "--root 应是项目根(内含 src/index.html);"
                      "只想跑前两项检查(不比对影片页)可加 --film ''"})
        return 2

    dynamic = {s.strip() for s in args.dynamic_id.split(",") if s.strip()}
    html = read(page_p)
    js = read(script_p)
    issues: list[dict] = []

    # ① id 引用
    ids = set(re.findall(r'id="([^"]+)"', html))
    used = sorted(set(re.findall(r'\$\("([^"]+)"\)', js)) |
                  set(re.findall(r'getElementById\("([^"]+)"\)', js)))
    miss = [u for u in used if u not in ids and u not in dynamic]
    for u in miss:
        issues.append({"id": "missing-element-id", "level": "P0",
                       "msg": f"review.js 引用了 #{u},但 review.html 里没有这个元素",
                       "fix": f"在 review.html 补 id=\"{u}\" 的元素(或把运行时才建的 id 加进 "
                              f"--dynamic-id)"})

    # ② 页签 ↔ 面板
    tabs = re.findall(r'data-tab="([^"]+)"', html)
    panels = re.findall(r'class="rv-panel[^"]*" id="([^"]+)"', html)
    for t in [x for x in tabs if x not in panels]:
        issues.append({"id": "tab-without-panel", "level": "P0",
                       "msg": f"页签 data-tab=\"{t}\" 没有对应面板",
                       "fix": f"补 <div class=\"rv-panel\" id=\"{t}\">(类名必须含 rv-panel)"})

    # ③ 影片 DOM 一致性(审片台页面必须是影片页的忠实复制品 + 一层 UI)
    film_ids, film_cv = film_dom(read(film_p)) if not skip_film else ([], [])
    page_ids, page_cv = film_dom(html)
    if not skip_film:
        for x in [i for i in film_ids if i not in page_ids]:
            issues.append({"id": "film-dom-missing", "level": "P0",
                           "msg": f"影片页 #stage 里有 #{x},审片台页面没有 → 预览会缺这一层",
                           "fix": "把该元素补进审片台页面的 #stage(审片台页面是影片页的复制品)"})
        for x in [i for i in page_ids if i not in film_ids]:
            issues.append({"id": "film-dom-extra", "level": "P1",
                           "msg": f"审片台页面 #stage 多出 #{x}(影片页没有)",
                           "fix": "确认是有意加的调试层;不是就删掉,否则预览与成片会对不上"})
        if film_cv != page_cv:
            issues.append({"id": "film-canvas-mismatch", "level": "P0",
                           "msg": f"canvas 标签不一致:影片页 {len(film_cv)} 个 / "
                                  f"审片台 {len(page_cv)} 个",
                           "fix": "逐条对齐 <canvas> 的属性(width/height/id/class)"})

    out = {"ok": not any(i["level"] == "P0" for i in issues),
           "root": root, "tool": tool, "page": os.path.basename(page_p),
           "film": os.path.relpath(film_p, root).replace("\\", "/"),
           "counts": {"ids": len(ids), "js_refs": len(used), "tabs": len(tabs),
                      "panels": len(panels), "issues": len(issues)},
           "issues": issues}
    emit(out)

    if issues:
        print(f"\n审片台页面自检:{len(issues)} 处(✗ P0 {sum(1 for i in issues if i['level'] == 'P0')})",
              file=sys.stderr)
        for i in issues[:20]:
            print(f"  {'✗' if i['level'] == 'P0' else '△'} [{i['id']}] {i['msg']}", file=sys.stderr)
            print(f"      修:{i['fix']}", file=sys.stderr)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
