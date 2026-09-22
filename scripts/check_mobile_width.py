#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_mobile_width.py — 手机窄屏「横向溢出」机检(零 token)

为什么需要它:
    桌面预览(677px / 1280px 浏览器)看不到这个问题。公众号正文容器是 max-width:677px,
    真机手机宽度只有 300–430px —— 很多在桌面完全正常的行内布局, 到手机上会把最后一列
    顶出屏幕右侧。典型元凶:
      · `table-layout:fixed` 下表格恒为 100%, 但**单元格内容比单元格宽时内容会溢到右侧**,
        最后一列的内容直接出屏;
      · 行内元素写死了 px 宽(如 `width:86px`), 而单元格在窄屏只剩 ~67px;
      · 4 列 × 25% 的行内块, 内容不可收缩。

    所以「在电脑上看正常、手机上看顶出右边」是这一类问题的固定症状。

用法:
    python check_mobile_width.py <html 或目录> [--widths 300,320,360,375,414]
                                 [--container "section[style*='max-width:677px']"] [--json]

退出码: 0 = 各宽度均无横向溢出 ; 1 = 存在溢出
"""
import argparse
import json
import os
import sys

DEFAULT_WIDTHS = [300, 320, 360, 375, 414]
DEFAULT_CONTAINER = "section[style*='max-width:677px']"

PROBE = r"""
(args) => {
  const root = document.querySelector(args.sel) || document.body;
  const rb = root.getBoundingClientRect();
  const limit = rb.right;
  const out = [];
  for (const el of root.querySelectorAll('*')) {
    const b = el.getBoundingClientRect();
    if (b.width === 0 || b.height === 0) continue;
    const over = Math.round(b.right - limit);
    if (over > 1) {
      out.push({
        tag: el.tagName.toLowerCase(),
        over,
        w: Math.round(b.width),
        left: Math.round(b.left - rb.left),
        style: (el.getAttribute('style') || '').slice(0, 90),
        text: (el.textContent || '').replace(/\s+/g, '').slice(0, 18)
      });
    }
  }
  // 只保留每棵树里最深处的叶子级元凶: 按 over 降序, 同 over 取最后出现的
  out.sort((a, b) => b.over - a.over);
  return {
    containerW: Math.round(rb.width),
    rootScroll: root.scrollWidth,
    rootClient: root.clientWidth,
    docScroll: document.documentElement.scrollWidth,
    docClient: document.documentElement.clientWidth,
    items: out.slice(0, 20)
  };
}
"""


def collect(paths, exclude=()):
    import glob
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += sorted(glob.glob(os.path.join(p, "**", "*.html"), recursive=True))
        else:
            out += sorted(glob.glob(p))
    out = [f for f in dict.fromkeys(out) if os.path.isfile(f)]
    for pat in exclude:
        out = [f for f in out if pat not in f.replace("\\", "/")]
    return out


def main():
    ap = argparse.ArgumentParser(description="手机窄屏横向溢出的机检")
    ap.add_argument("paths", nargs="+", help="HTML 文件或目录")
    ap.add_argument("--widths", default=",".join(map(str, DEFAULT_WIDTHS)),
                    help="要测的视口宽度(px), 逗号分隔。默认 300,320,360,375,414")
    ap.add_argument("--container", default=DEFAULT_CONTAINER,
                    help="正文容器选择器(默认抓 max-width:677px 的那层)")
    ap.add_argument("--exclude", action="append", default=[], help="跳过路径含该子串的文件")
    ap.add_argument("--wait", type=int, default=1500,
                    help="每个文件首次加载后的等待毫秒(默认 1500)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--headful", action="store_true", help="显示浏览器窗口(排查用)")
    a = ap.parse_args()

    widths = [int(x) for x in a.widths.split(",") if x.strip()]
    files = collect(a.paths, a.exclude)
    if not files:
        print("没有找到 HTML 文件:", a.paths)
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("需要 playwright:  pip install playwright && playwright install chromium")
        return 2

    from urllib.parse import quote as urlquote
    report, bad = [], []

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="chrome", headless=not a.headful)
        except Exception:
            browser = pw.chromium.launch(headless=not a.headful)
        # 每个文件只加载一次, 之后只改视口尺寸 —— 重开页面会慢 5 倍以上
        for fp in files:
            name = os.path.basename(fp)
            url = "file:///" + urlquote(os.path.abspath(fp).replace("\\", "/"))
            entry = {"file": name, "widths": {}}
            page = browser.new_page(viewport={"width": widths[0], "height": 900})
            # 外链图可能很大(实测有 3.9MB 的), 不阻塞在图片上: 布局宽度与图片无关
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(a.wait)
            for w in widths:
                page.set_viewport_size({"width": w, "height": 900})
                page.wait_for_timeout(220)
                r = page.evaluate(PROBE, {"sel": a.container})
                entry["widths"][w] = r
                if r["items"]:
                    bad.append((name, w, r))
            page.close()
            report.append(entry)
        browser.close()

    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"测试宽度: {widths}\n")
        for e in report:
            line = "  ".join(
                f"{w}px:{len(e['widths'][w]['items'])}越界" for w in widths)
            print(f"{e['file']}\n   {line}")
        if bad:
            print("\n===== 横向溢出明细 =====")
            for name, w, r in bad:
                print(f"\n[{name}] 视口 {w}px  容器 {r['containerW']}px"
                      f"  (容器 scrollWidth {r['rootScroll']} / clientWidth {r['rootClient']})")
                for it in r["items"]:
                    print(f"   越界 {it['over']:>4}px  <{it['tag']}> w={it['w']} left={it['left']}"
                          f"  «{it['text']}»")
                    if it["style"]:
                        print(f"                  style=\"{it['style']}\"")
        print("\n结论:", "通过 ✅ 各宽度均无横向溢出"
              if not bad else f"未通过 ❌ {len(bad)} 个(文件×宽度)组合有溢出")

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
