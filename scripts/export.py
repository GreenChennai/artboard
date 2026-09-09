"""artboard 导出薄壳(主路径):直接 import WPI 的 run_export_sync,GUI 无关。

用法:
  python export.py --source <项目目录|HTML文件|URL> --output out.png \
      [--format PNG|GIF|MP4|PDF] [--width 1080] [--scale 1|2|4|8] \
      [--height 0] [--fps 25] [--transparent] [--max-wait 15]

输出:单行 JSON。ok=false 时带 error/hint,按 hint 处理(常见:改用 export_fallback.py)。
"""

import argparse
import json
import os
import sys

from _config import cfg

DEFAULT_WPI = r"E:\平日资料\GitHub\WPI"

FIELDS = ("format", "path", "width", "height", "frames", "encoder", "warnings")


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def find_wpi() -> str | None:
    cand = cfg("wpi_path", DEFAULT_WPI)
    if cand and os.path.isfile(os.path.join(cand, "src", "core", "controller.py")):
        return cand
    return None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="artboard → WPI 导出")
    p.add_argument("--source", required=True, help="项目目录 / HTML 文件 / http(s) URL")
    p.add_argument("--output", required=True)
    p.add_argument("--format", default="PNG", choices=["PNG", "GIF", "MP4", "PDF"])
    p.add_argument("--width", type=int, default=1080)
    p.add_argument("--scale", type=int, default=1, choices=[1, 2, 4, 8])
    p.add_argument("--height", type=int, default=0, help=">0 时锁定高度,超出不导出")
    p.add_argument("--fps", type=int, default=25)
    p.add_argument("--transparent", action="store_true")
    p.add_argument("--cmyk", action="store_true",
                   help="打印交付:追加导出 CMYK PDF + TIFF(印刷流程见 print-cmyk.md)")
    p.add_argument("--max-wait", type=float, default=15.0, dest="max_wait")
    args = p.parse_args()

    wpi = find_wpi()
    if not wpi:
        emit({"ok": False, "error": "WPI_NOT_FOUND",
              "hint": f"未找到 WPI(默认 {DEFAULT_WPI})。设环境变量 ARTBOARD_WPI 指向 WPI 根目录,"
                      "或改用 scripts/export_fallback.py(仅 PNG)"})
        return 2

    src = os.path.join(wpi, "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        from core.controller import ExportParams, run_export_sync
    except Exception as exc:  # noqa: BLE001
        emit({"ok": False, "error": "WPI_IMPORT_FAILED", "detail": str(exc),
              "hint": "检查 WPI 依赖(playwright/Pillow),或改用 scripts/export_fallback.py(仅 PNG)"})
        return 3

    params = ExportParams(
        source=args.source, format=args.format, width=args.width,
        scale=args.scale, height=args.height, fps=args.fps,
        transparent=args.transparent, max_wait=args.max_wait,
        output_path=args.output,
    )
    try:
        result = run_export_sync(params)
    except Exception as exc:  # noqa: BLE001
        emit({"ok": False, "error": type(exc).__name__, "detail": str(exc)})
        return 1

    # CMYK 打印交付:PNG → CMYK PDF + TIFF(印刷流程,见 print-cmyk.md)
    if getattr(args, "cmyk", False):
        png_path = os.path.splitext(args.output)[0] + ".png"
        if os.path.isfile(png_path):
            from PIL import Image
            im = Image.open(png_path).convert("CMYK")
            base = os.path.splitext(args.output)[0]
            im.save(base + "-cmyk.pdf", resolution=300)
            im.save(base + "-cmyk.tif", compression="tiff_lzw")
            print(json.dumps({"cmyk": [base + "-cmyk.pdf", base + "-cmyk.tif"]},
                             ensure_ascii=False))

    emit({"ok": True, **{k: result.get(k) for k in FIELDS}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
