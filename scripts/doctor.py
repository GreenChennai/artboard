"""artboard 项目体检:扫 studio 目录,核对 project.json 与 HTML 真值。

来源:v1.9.x 外部部署报告 Issue 5——存量项目 skill_dir 失效引用、
画布尺寸与真实交付不符、缺 scale 键,持续制造「重跑不一致」困惑。

口径(与报告建议一致):
  - HTML 里画布容器的显式 width/height 是画布真值的唯一来源;
    project.json 仅为默认值;高度随内容的画布(预设 h=0,如 long)没有高度真值,
    只核宽度,不按"缺显式尺寸"报;
  - skill_dir 必须指向存在的技能目录(投放脚本靠它定位引擎/config);
  - scale 必须显式:缺键时 <项目>/src/导出.py 与 导出-*.bat 回落按 2、export.py
    默认按 1——口径分裂(印刷 DPI 会错),列为待修;scaffold 建项目时已写入预设值。

用法:
  python scripts/doctor.py <studio目录>            # 体检全部项目
  python scripts/doctor.py <studio目录> --fix-meta # 把 .poster 真值回写 project.json
输出:人读报告 + --json 单行结论。退出码:0 干净 / 1 有待修项 / 2 参数错。
"""

import argparse
import json
import os
import re
import sys

POSTER_BLOCK = re.compile(r"\.poster\s*{[^}]*}", re.S)
WIDTH_RE = re.compile(r"(?:^|[;{]\s*)width\s*:\s*(\d+(?:\.\d+)?)px")
HEIGHT_RE = re.compile(r"(?:^|[;{]\s*)height\s*:\s*(\d+(?:\.\d+)?)px")


def poster_size(html_path: str) -> tuple[int, int] | None:
    """从 HTML 提取 .poster 显式声明尺寸;无 .poster 返回 None。"""
    try:
        with open(html_path, encoding="utf-8", errors="replace") as f:
            css_blocks = "".join(POSTER_BLOCK.findall(f.read()))
    except OSError:
        return None
    if not css_blocks:
        return None
    w = WIDTH_RE.search(css_blocks)
    h = HEIGHT_RE.search(css_blocks)
    if not (w and h):
        return None
    return int(float(w.group(1))), int(float(h.group(1)))


def as_int(v) -> int:
    """配置值 → int;缺失/非数值一律 0(展示时写 "(缺)")。"""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def poster_width(html_path: str) -> int | None:
    """只取 .poster 的显式宽度(高度随内容的画布只有宽是真值)。"""
    try:
        with open(html_path, encoding="utf-8", errors="replace") as f:
            css_blocks = "".join(POSTER_BLOCK.findall(f.read()))
    except OSError:
        return None
    m = WIDTH_RE.search(css_blocks) if css_blocks else None
    return int(float(m.group(1))) if m else None


def content_height(meta: dict) -> bool:
    """project.json 是否声明「高度随内容」(长图预设 h=0)。

    口径与 scaffold.SIZES(h=0)及 _img_core.size_of("h==0 = 高度随内容")一致:
    这类画布没有高度真值可比,若按"缺显式尺寸 = degraded"报,scaffold 自己的
    long 预设会被恒判为待修(体检对自产项目永远红灯)。
    """
    return (meta.get("size") == "long"
            or ("height" in meta and as_int(meta.get("height")) == 0))


def scan_project(proj: str) -> dict:
    """体检单个项目目录(含 src/ 的叶子目录)。"""
    rep: dict = {"project": proj, "issues": [], "htmls": 0}
    pj_path = os.path.join(proj, "project.json")
    meta: dict = {}
    if os.path.isfile(pj_path):
        try:
            with open(pj_path, encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError) as exc:
            rep["issues"].append(f"project.json 解析失败: {exc}")
    skill = str(meta.get("skill_dir") or "")
    if os.path.isfile(pj_path) and (not skill or not os.path.isdir(skill)):
        rep["issues"].append(
            f"skill_dir 失效引用: {skill or '(空)'}(投放脚本找不到引擎/config)")
    src = os.path.join(proj, "src")
    if not os.path.isdir(src):
        return rep
    for fn in sorted(os.listdir(src)):
        if not fn.lower().endswith((".html", ".htm")):
            continue
        rep["htmls"] += 1
        html_path = os.path.join(src, fn)
        truth = poster_size(html_path)
        if truth is None:
            pw = poster_width(html_path)
            if content_height(meta) and pw:
                # 长图(h=0):高度随内容是设计,不是缺陷;但宽度仍有真值,必须核
                mw = as_int(meta.get("width"))
                if os.path.isfile(pj_path) and mw != pw:
                    rep["issues"].append(
                        f"{fn}: project.json 宽度 {mw or '(缺)'} ≠ .poster 真值宽 "
                        f"{pw}(长图预设:高度随内容,只核宽)")
            else:
                rep["issues"].append(f"{fn}: 无 .poster 显式尺寸,画布将由内容包围盒合成(degraded)")
            continue
        w, h = truth
        mw, mh = as_int(meta.get("width")), as_int(meta.get("height"))
        # 不再要求 mw/mh 都非零:project.json 缺 height 正是最常见的"尺寸不符"
        # 来源(--fix-meta 会补,体检却整条跳过 → 自相矛盾);缺的分量按 "(缺)" 展示。
        if os.path.isfile(pj_path) and (mw, mh) != (w, h):
            rep["issues"].append(
                f"{fn}: project.json 尺寸 {mw or '(缺)'}×{mh or '(缺)'} "
                f"≠ .poster 真值 {w}×{h}")
    if os.path.isfile(pj_path) and not meta.get("scale"):
        rep["issues"].append(
            "缺 scale 键(<项目>/src/导出.py 与 导出-*.bat 回落按 2、export.py 默认按 1,"
            "印刷 DPI 口径分裂)")
    return rep


def fix_meta(proj: str) -> int:
    """把首个 HTML 的 .poster 真值回写 project.json(仅修正宽高)。"""
    src = os.path.join(proj, "src")
    pj_path = os.path.join(proj, "project.json")
    if not (os.path.isdir(src) and os.path.isfile(pj_path)):
        return 0
    fixed = 0
    try:
        with open(pj_path, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return 0
    for fn in sorted(os.listdir(src)):
        if not fn.lower().endswith((".html", ".htm")):
            continue
        path = os.path.join(src, fn)
        truth = poster_size(path)
        if truth:
            w, h = truth
        elif content_height(meta):
            # 长图:高度随内容 → 宽取真值、高回写 0(与体检口径一致,否则 --fix-meta 修不动)
            w = poster_width(path)
            if w is None:
                continue
            h = 0
        else:
            continue
        if as_int(meta.get("width")) != w or as_int(meta.get("height")) != h:
            meta["width"], meta["height"] = w, h
            fixed += 1
        break
    if fixed:
        with open(pj_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    return fixed


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="artboard 项目体检")
    ap.add_argument("root", help="studio 根目录(逐层扫含 src/ 的项目)")
    ap.add_argument("--fix-meta", action="store_true",
                    help="把 .poster 真值回写 project.json(width/height)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()
    if not os.path.isdir(args.root):
        print(json.dumps({"ok": False, "error": "目录不存在", "path": args.root},
                         ensure_ascii=False))
        return 2

    projects: list[str] = []
    for cur, dirs, _files in os.walk(args.root):
        dirs[:] = [d for d in dirs if not d.startswith((".", "_"))]
        if os.path.isdir(os.path.join(cur, "src")):
            projects.append(cur)

    fixed = 0
    if args.fix_meta:
        fixed = sum(fix_meta(p) for p in projects)
        # --json 时这行必须走 stderr:此前直接 print 会污染 stdout 的 JSON 末行契约
        print(f"[OK] 已按 .poster 真值回写 {fixed} 个 project.json",
              file=(sys.stderr if args.as_json else sys.stdout))

    reports = [scan_project(p) for p in sorted(projects)]
    bad = [r for r in reports if r["issues"]]
    if args.as_json:
        print(json.dumps({"ok": not bad, "projects": len(reports),
                          "bad": len(bad), "fixed": fixed, "detail": bad},
                         ensure_ascii=False))
    else:
        print(f"== artboard 体检:{len(reports)} 个项目,{len(bad)} 个待修 ==")
        for r in bad:
            print(f"\n-- {os.path.relpath(r['project'], args.root)} --")
            for i in r["issues"]:
                print(f"  △ {i}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
