"""artboard H5 交互页机检(模式 H;规范见 references/h5-interactive.md)。

为什么需要它:H5 与静态海报规则完全不同(允许滚动/固定定位,不适用铁律 1),
因此有一套自己的机检门。8 项静态可判定检查:viewport 合法性 / 安全区配套 /
零 CDN / 触摸目标 / 图片尺寸与 alt / 100vh 误用 / reduced-motion 分支 / 体积预算。

用法:
  python check_h5.py <页面.html|目录> [--min-touch 44] [--budget-kb 300]

输出:stdout 单行 JSON {ok, files:[{path, issues:[{code,severity,msg}]}]};
severity: FAIL(挡过)/ WARN(须自查)。退出码 0 = 无 FAIL / 1 = 有 FAIL / 2 = 用法错。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

RE_VIEWPORT = re.compile(r'<meta[^>]+name=["\']viewport["\'][^>]*>', re.I)
RE_WIDTH_DW = re.compile(r"width\s*=\s*device-width", re.I)
RE_NO_SCALE = re.compile(r"user-scalable\s*=\s*no", re.I)
RE_COVER = re.compile(r"viewport-fit\s*=\s*cover", re.I)
RE_EXT = re.compile(r"""(?:src|href)\s*=\s*["']https?://""", re.I)
RE_IMG = re.compile(r"<img\b[^>]*>", re.I)
RE_ANIM = re.compile(r"animation\s*:|@keyframes|transition\s*:", re.I)
RE_100VH = re.compile(r"\b100vh\b")
RE_REDUCED = re.compile(r"prefers-reduced-motion", re.I)
RE_SAFE = re.compile(r"env\(\s*safe-area-inset-", re.I)
RE_TOUCH_CSS = re.compile(
    r"(?:button|\.btn[^\w{]*|\ba\b|input|textarea)\b[^{]*\{[^}]*\}", re.I)
RE_DIM = re.compile(r"(?:min-)?(width|height)\s*:\s*(\d+(?:\.\d+)?)px")


def check_file(path: str, min_touch: int, budget_kb: int) -> list[dict]:
    issues: list[dict] = []

    def add(code, severity, msg):
        issues.append({"code": code, "severity": severity, "msg": msg})

    with open(path, encoding="utf-8", errors="replace") as f:
        html = f.read()

    # ① viewport
    m = RE_VIEWPORT.search(html)
    if not m:
        add("VIEWPORT_MISSING", "FAIL", "缺 <meta name=viewport>(移动端适配的根基)")
    else:
        tag = m.group(0)
        if not RE_WIDTH_DW.search(tag):
            add("VIEWPORT_INVALID", "FAIL", "viewport 缺 width=device-width(MDN 基线)")
        if RE_NO_SCALE.search(tag):
            add("USER_SCALABLE_NO", "FAIL",
                "user-scalable=no 被禁用(阻止低视力缩放违反 WCAG,且 iOS10+/浏览器设置可忽略——双重不合规)")

    # ② 安全区配套
    if RE_COVER.search(html) and not RE_SAFE.search(html):
        add("SAFE_AREA_MISSING", "FAIL",
            "用了 viewport-fit=cover 但没有 env(safe-area-inset-*)——内容会落进刘海/手势区")

    # ③ 零 CDN
    for i, line in enumerate(html.splitlines(), 1):
        if RE_EXT.search(line):
            add("CDN_REF", "FAIL", f"第 {i} 行外部 http(s) 资源引用(离线优先红线;第三方库 vendored 进项目)")
            break

    # ④ 触摸目标(静态判定:样式表里按钮/链接类规则的显式尺寸)
    style_blocks = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S | re.I))
    dims: list[float] = []
    for rule in RE_TOUCH_CSS.findall(style_blocks):
        for _kind, val in RE_DIM.findall(rule if isinstance(rule, str) else ""):
            dims.append(float(val))
    inline = re.findall(r'<(?:button|a|input)\b[^>]*style=["\']([^"\']*)["\']', html, re.I)
    for st in inline:
        for _kind, val in RE_DIM.findall(st):
            dims.append(float(val))
    big = [d for d in dims if d >= min_touch]
    if dims and not big:
        add("TOUCH_TARGET", "FAIL",
            f"交互元素显式尺寸均 < {min_touch}px(WCAG 2.5.5 AAA 线 {min_touch};最低 24)")
    elif not dims:
        add("TOUCH_TARGET_UNKNOWN", "WARN",
            "未能从样式判定触摸目标尺寸(确认主交互 ≥44×44,次要 ≥24×24)")
    elif min(big) < min_touch:
        add("TOUCH_TARGET_SMALL", "WARN", f"存在 {min(big):.0f}px 的显式尺寸 < {min_touch}px(次要控件须有间距补偿)")

    # ⑤ 图片尺寸与 alt
    for tag in RE_IMG.findall(html):
        srcm = re.search(r'src=["\']([^"\']+)', tag)
        name = (srcm.group(1) if srcm else "?")[-40:]
        if not re.search(r"\balt\s*=", tag):
            add("IMG_ALT", "WARN", f"图片缺 alt({name})")
        if not (re.search(r"\bwidth\s*=\s*[\"'\d]", tag) and re.search(r"\bheight\s*=\s*[\"'\d]", tag)):
            add("IMG_DIM", "WARN", f"图片缺显式 width/height(CLS 风险;{name})")
            break

    # ⑥ 100vh 误用
    if RE_100VH.search(html):
        add("VH_MISUSE", "WARN", "100vh 做布局会被移动端地址栏吃掉一块;建议 100dvh / 100svh")

    # ⑦ reduced-motion(有动画时)
    if RE_ANIM.search(html) and not RE_REDUCED.search(html):
        add("REDUCED_MOTION", "FAIL",
            "有 CSS 动画但无 prefers-reduced-motion 分支(H5 铁律 6:无障碍必配)")

    # ⑧ 体积预算
    kb = os.path.getsize(path) / 1024
    if kb > budget_kb:
        add("BUDGET", "WARN", f"单文件 {kb:.0f}KB > 预算 {budget_kb}KB(首屏关键资源口径;按场景可调)")
    return issues


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    class P(argparse.ArgumentParser):
        def error(self, message):
            print(json.dumps({"ok": False, "error": "USAGE", "hint": message}, ensure_ascii=False))
            raise SystemExit(2)

    ap = P(description="H5 交互页机检(模式 H;细则见 references/h5-interactive.md)")
    ap.add_argument("paths", nargs="+", help="HTML 文件或目录")
    ap.add_argument("--min-touch", type=int, default=44, dest="min_touch")
    ap.add_argument("--budget-kb", type=int, default=300, dest="budget_kb")
    args = ap.parse_args()

    files: list[str] = []
    for p in args.paths:
        if os.path.isdir(p):
            files.extend(os.path.join(p, f) for f in sorted(os.listdir(p)) if f.endswith(".html"))
        elif os.path.isfile(p):
            files.append(p)
    if not files:
        print(json.dumps({"ok": False, "error": "USAGE", "hint": "没有找到 HTML"}, ensure_ascii=False))
        return 2
    results, has_fail = [], False
    for p in files:
        issues = check_file(p, args.min_touch, args.budget_kb)
        if any(i["severity"] == "FAIL" for i in issues):
            has_fail = True
        try:
            shown = os.path.relpath(p)
        except ValueError:  # 跨盘符
            shown = p
        results.append({"path": shown, "issues": issues})
        for it in issues:
            mark = "✗" if it["severity"] == "FAIL" else "△"
            print(f"  {mark} [{it['code']}] {os.path.basename(p)} {it['msg']}", file=sys.stderr)
    print(json.dumps({"ok": not has_fail, "count": len(results), "files": results},
                     ensure_ascii=False))
    return 1 if has_fail else 0


if __name__ == "__main__":
    sys.exit(main())
