"""artboard 尺寸计算器:px / mm / inch / DPI 互转,印刷导出一把算清。

用法:
  python calc_size.py mm 210 297 --dpi 300          # mm→px(印刷 300dpi)
  python calc_size.py px 1080 1440 --dpi 300        # px→物理尺寸(mm/inch)与等效 DPI
  python calc_size.py inch 8.5 11 --dpi 300         # inch→px
  python calc_size.py dpi --px 2480 3508 --mm 210 297   # 反推 DPI

公式(全链路只有一个):
  像素 = 物理尺寸(inch) × DPI        →  px = mm ÷ 25.4 × DPI
  物理尺寸(inch) = 像素 ÷ DPI        →  mm = px ÷ DPI × 25.4
  成品导出:CSS 画布 px × scale = 成品 px;成品 px ÷ (mm/25.4) = 成品 DPI
"""

import argparse
import json
import sys

MM_PER_INCH = 25.4


def out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="px/mm/inch/DPI 换算")
    p.add_argument("mode", choices=["mm", "px", "inch", "dpi"])
    p.add_argument("w", nargs="?", type=float)
    p.add_argument("h", nargs="?", type=float)
    p.add_argument("--dpi", type=float, default=300.0)
    p.add_argument("--scale", type=float, default=2.0, help="导出倍率(px 模式用)")
    p.add_argument("--mm", nargs=2, type=float, metavar=("W", "H"))
    p.add_argument("--px", nargs=2, type=float, metavar=("W", "H"))
    args = p.parse_args()

    if args.mode == "mm":
        if not args.w or not args.h:
            p.error("mm 模式需要 宽 高(mm)")
        pxw, pxh = round(args.w / MM_PER_INCH * args.dpi), round(args.h / MM_PER_INCH * args.dpi)
        out({"mode": "mm→px", "mm": [args.w, args.h], "dpi": args.dpi,
             "css_canvas": [pxw, pxh],
             "export": f"--width {pxw} --scale 1(即 {args.dpi}dpi)",
             "scale2": f"--width {pxw} --scale 2 --height {pxh} → {pxw*2}×{pxh*2}"})
    elif args.mode == "inch":
        if not args.w or not args.h:
            p.error("inch 模式需要 宽 高(inch)")
        pxw, pxh = round(args.w * args.dpi), round(args.h * args.dpi)
        out({"mode": "inch→px", "inch": [args.w, args.h], "dpi": args.dpi,
             "css_canvas": [pxw, pxh],
             "export": f"--width {pxw} --scale 1(即 {args.dpi}dpi)"})
    elif args.mode == "px":
        if not args.w or not args.h:
            p.error("px 模式需要 宽 高(css px)")
        exw, exh = round(args.w * args.scale), round(args.h * args.scale)
        mm_w = exw / args.dpi * MM_PER_INCH
        mm_h = exh / args.dpi * MM_PER_INCH
        out({"mode": "px→物理(按目标dpi印刷)", "css_px": [args.w, args.h],
             "scale": args.scale, "export_px": [exw, exh],
             "dpi": args.dpi,
             "成品_mm": [round(mm_w, 1), round(mm_h, 1)],
             "成品_inch": [round(mm_w / MM_PER_INCH, 2), round(mm_h / MM_PER_INCH, 2)],
             "hint": "印刷须 ≥300dpi;反推(已知 mm 求 dpi)用 dpi 模式"})
    else:  # dpi 反推
        if not args.px or not args.mm:
            p.error("dpi 模式需要 --px W H 与 --mm W H")
        dpi_w = args.px[0] / (args.mm[0] / MM_PER_INCH)
        dpi_h = args.px[1] / (args.mm[1] / MM_PER_INCH)
        out({"mode": "反推DPI", "px": args.px, "mm": args.mm,
             "dpi": [round(dpi_w, 1), round(dpi_h, 1)],
             "建议": "印刷 ≥300;大幅面(>A2)可 150"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
