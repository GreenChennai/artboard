"""artboard SVG 质量门(9 项结构机检;细则见 references/vector-drawing.md §4.7)。

为什么需要它:自绘 SVG"画完不知好坏"——线宽不一、端点不统一、裸 hex、编辑器残留、
栅格混入这些问题肉眼在 24px 下无感,一上版就"异类"。本脚本零 token 把结构问题拦在交付前。
9 项判据与 vector-drawing.md §4.3 图标 7 规范同源(默认阈值按 Tabler 语言:stroke-width 2)。

用法:
  python check_svg.py <文件或目录>…            # 目录递归;多文件批量
  python check_svg.py --strict x.svg           # 收紧:单路径节点 ≤200
  python check_svg.py --max-nodes 600 x.svg    # 放宽节点上限(插画类常用)
  python check_svg.py --allow-image x.svg      # 放行内嵌 <image>(默认报错)

九项:① XML 可解析 ② viewBox 存在且与 width/height 一致 ③ stroke-width 唯一
④ linecap/linejoin 统一 round ⑤ 无裸 hex(currentColor/CSS 变量;#fff 白边例外)
⑥ <g> 嵌套 ≤5 ⑦ 单路径节点数 ≤ 上限 ⑧ 无编辑器残留(metadata/sodipodi/inkscape/注释)
⑨ 无 <image> 栅格混入(可豁免)

输出:stdout 单行 JSON {ok, files:[{path, issues:[{code,line,msg}]}]};人类清单走 stderr。
退出码 0=全过 / 1=有问题 / 2=用法错。fill-only 图标(fill 无 stroke)自动跳过 ③④。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

SVG_NS = "{http://www.w3.org/2000/svg}"
NODE_COUNT_RE = re.compile(r"[mMlLhHvVcCsSqQtTaAzZ]")
HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
RESIDUE_RE = re.compile(r"<metadata|sodipodi:|inkscape:|<!--")


def rel(p: str) -> str:
    try:
        return os.path.relpath(p)
    except ValueError:  # 跨盘符(Windows)
        return p


def iter_svg_files(paths: list[str]) -> list[str]:
    out: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                out.extend(os.path.join(root, f) for f in sorted(files)
                           if f.lower().endswith(".svg"))
        elif os.path.isfile(p):
            out.append(p)
    return out


def path_node_count(d: str) -> int:
    """路径指令参数个数近似(节点数上限的工程估计)。"""
    return len(NODE_COUNT_RE.findall(d))


def check_file(path: str, max_nodes: int, allow_image: bool,
               strict: bool) -> list[dict]:
    issues: list[dict] = []

    def add(code: str, line: int, msg: str) -> None:
        issues.append({"code": code, "line": line, "msg": msg})

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except OSError as exc:
        add("IO", 0, f"读不了:{exc}")
        return issues

    # ① XML 可解析
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        add("XML", 0, f"解析失败:{exc}")
        return issues

    # ⑧ 编辑器残留(XML 注释/命名空间/metadata)
    m = RESIDUE_RE.search(raw)
    if m:
        line = raw[:m.start()].count("\n") + 1
        add("RESIDUE", line, f"编辑器残留:{m.group(0)}")

    # ② viewBox
    vb = (root.get("viewBox") or "").strip()
    if not vb:
        add("VIEWBOX", 1, "缺 viewBox(缩放会错)")
    else:
        w, h = root.get("width"), root.get("height")
        if w and h:
            def px(v: str) -> float | None:
                # 只比纯数值 / px;1em 这类相对单位不比(Iconify 惯例 width="1em")
                num = re.sub(r"px$", "", v.strip())
                try:
                    return float(num)
                except ValueError:
                    return None
            pw, ph = px(w), px(h)
            if pw is not None and ph is not None:
                vw, vh = (float(x) for x in vb.split()[-2:])
                if (pw, ph) != (vw, vh):
                    add("VIEWBOX", 1,
                        f"width/height ({w}×{h}) 与 viewBox ({vw}×{vh}) 不一致")

    # 收集属性
    strokes: set[str] = set()
    caps: set[str] = set()
    joins: set[str] = set()
    hex_hits: list[tuple[int, str]] = []
    g_depth = 0
    max_g_depth = 0
    has_stroke = False
    has_fill_only = False
    path_counts: list[int] = []
    images = 0

    def walk(el: ET.Element, depth: int) -> None:
        nonlocal g_depth, max_g_depth, has_stroke, has_fill_only, images
        tag = el.tag.replace(SVG_NS, "")
        if tag == "g":
            g_depth += 1
            max_g_depth = max(max_g_depth, g_depth)
        style = el.get("style") or ""
        attrs = dict(el.attrib)
        for frag in style.split(";"):
            if ":" in frag:
                k, v = frag.split(":", 1)
                attrs.setdefault(k.strip(), v.strip())
        stroke = attrs.get("stroke")
        fill = attrs.get("fill")
        if stroke and stroke not in ("none",):
            has_stroke = True
            strokes.add(str(attrs.get("stroke-width", "2")).strip())
            caps.add(attrs.get("stroke-linecap", "butt"))
            joins.add(attrs.get("stroke-linejoin", "miter"))
        if tag == "path" and fill not in ("none", None) and not stroke:
            has_fill_only = True
        if tag == "path" and attrs.get("d"):
            path_counts.append(path_node_count(attrs["d"]))
        if tag == "image":
            images += 1
        # ⑤ 裸 hex(currentColor 之外的具名色)
        for key in ("fill", "stroke"):
            v = attrs.get(key)
            if v and v.startswith("#") and v.lower() not in ("#fff", "#ffffff"):
                hex_hits.append((getattr(el, "sourceline", 0) or 0, v))
        for child in el:
            walk(child, depth + 1)
        if tag == "g":
            g_depth -= 1

    walk(root, 0)

    if not has_stroke and not has_fill_only:
        add("SHAPE", 0, "既无 stroke 也无 fill 路径(空图或用了不支持的表达)")
    if has_stroke:
        if len(strokes) > 1:
            add("STROKE_WIDTH", 0, f"stroke-width 不唯一:{sorted(strokes)}(同组应唯一,默认 2)")
        bad_caps = caps - {"round", None}
        if bad_caps:
            add("LINECAP", 0, f"stroke-linecap 不统一:{sorted(x for x in caps if x)}(应 round)")
        bad_joins = joins - {"round", None}
        if bad_joins:
            add("LINEJOIN", 0, f"stroke-linejoin 不统一:{sorted(x for x in joins if x)}(应 round)")
    for line, v in hex_hits[:8]:
        add("HEX", line, f"裸 hex 颜色 {v}(应 currentColor / CSS 变量;#fff 白边例外)")
    if max_g_depth > 5:
        add("DEPTH", 0, f"<g> 嵌套 {max_g_depth} 层 > 5")
    limit = 200 if strict else max_nodes
    for i, n in enumerate(path_counts[:12]):
        if n > limit:
            add("PATH_NODES", 0, f"第 {i + 1} 条路径约 {n} 个节点 > {limit}(曲线堆;简化或 --max-nodes 放宽)")
            break
    if images and not allow_image:
        add("RASTER", 0, "内嵌 <image> 栅格混入(矢量纯净;确认要混入加 --allow-image)")
    return issues


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    class JsonParser(argparse.ArgumentParser):
        def error(self, message):  # 失败路径也吐合法 JSON(jsonfail 契约)
            print(json.dumps({"ok": False, "error": "USAGE", "hint": f"{message};{self.prog} --help"},
                             ensure_ascii=False))
            raise SystemExit(2)

    ap = JsonParser(description="SVG 质量门:9 项结构机检(vector-drawing.md §4.7)")
    ap.add_argument("paths", nargs="+", help="SVG 文件或目录(目录递归)")
    ap.add_argument("--strict", action="store_true", help="收紧:单路径节点 ≤200")
    ap.add_argument("--max-nodes", type=int, default=400, dest="max_nodes")
    ap.add_argument("--allow-image", action="store_true", dest="allow_image")
    args = ap.parse_args()

    files = iter_svg_files(args.paths)
    if not files:
        print(json.dumps({"ok": False, "error": "USAGE",
                          "hint": "没有找到 SVG(传文件或目录)"}, ensure_ascii=False))
        return 2
    results = []
    for p in files:
        issues = check_file(p, args.max_nodes, args.allow_image, args.strict)
        results.append({"path": rel(p), "issues": issues})
        if issues:
            for it in issues:
                print(f"  ✗ [{it['code']}] {rel(p)}:{it['line']} {it['msg']}",
                      file=sys.stderr)
    bad = sum(1 for r in results if r["issues"])
    print(json.dumps({"ok": bad == 0, "count": len(results), "bad": bad,
                      "files": results}, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
