"""artboard 导出薄壳(主路径):WPI 源码版(Python API)→ WPI CLI 单文件 → 失败给 hint。

用法:
  python export.py --source <项目目录|HTML文件|URL> --output out.png \
      [--format PNG|GIF|MP4|PDF] [--width 1080] [--scale 1|2|4|8] \
      [--height 0] [--fps 25] [--transparent] [--max-wait 15]

引擎优先级:
  1. WPI 源码版(config.json: wpi_path / env ARTBOARD_WPI)→ import core.controller
  2. WPI CLI 单文件(config.json: wpi_cli_exe)→ 同参数子进程调用
  3. 都没有 → ok=false + hint(改用 scripts/export_fallback.py,仅 PNG)

输出:单行 JSON。ok=false 时带 error/hint,按 hint 处理。
"""

import argparse
import json
import os
import subprocess
import sys

from _config import cfg, near_workspace

DEFAULT_WPI = near_workspace("WPI")

FIELDS = ("format", "path", "width", "height", "frames", "encoder", "warnings")


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def find_wpi() -> tuple[str, str]:
    """返回 (引擎类型, 路径):("source", dir) / ("cli", exe) / ("", "")。"""
    src_dir = cfg("wpi_path", DEFAULT_WPI)
    if src_dir and os.path.isfile(os.path.join(src_dir, "src", "core", "controller.py")):
        return "source", src_dir
    cli = cfg("wpi_cli_exe")
    if cli and os.path.isfile(cli):
        return "cli", cli
    return "", ""


def export_via_cli(cli: str, args) -> tuple[int, dict]:
    """WPI 单文件 CLI:与 main.py --export 同参数,退出码 0 且产出文件视为成功。
    返回 (退出码, 失败时的 error dict)。成功时 error dict 为空。"""
    cmd = [cli, "--export",
           "--source", args.source, "--output", args.output,
           "--format", args.format,
           "--width", str(args.width), "--scale", str(args.scale)]
    if args.height > 0:
        cmd += ["--height", str(args.height)]
    if args.format in ("GIF", "MP4"):
        cmd += ["--fps", str(args.fps)]
    cmd += ["--max-wait", str(args.max_wait)]
    if args.transparent:
        cmd += ["--transparent"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=900)
    except Exception as exc:  # noqa: BLE001
        return 1, {"ok": False, "error": "WPI_CLI_FAILED", "detail": str(exc),
                   "hint": "改用 scripts/export_fallback.py(仅 PNG)"}
    if r.returncode != 0:
        return 1, {"ok": False, "error": "WPI_CLI_FAILED", "detail": f"rc={r.returncode}",
                   "stderr": r.stderr.decode("utf-8", errors="replace")[:400],
                   "hint": "改用 scripts/export_fallback.py(仅 PNG)"}
    if not os.path.isfile(args.output):
        return 1, {"ok": False, "error": "WPI_CLI_NO_OUTPUT", "detail": args.output,
                   "hint": "CLI 退出 0 但没产出文件;改用 scripts/export_fallback.py(仅 PNG)"}
    return 0, {}


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

    kind, wpi = find_wpi()
    if not kind:
        emit({"ok": False, "error": "WPI_NOT_FOUND",
              "hint": "未找到 WPI。跑 scripts/setup_wpi.py 部署,"
                      "或设 ARTBOARD_WPI 指向 WPI 根目录,"
                      "或改用 scripts/export_fallback.py(仅 PNG)"})
        return 2

    result: dict = {}
    if kind == "cli":
        rc, err = export_via_cli(wpi, args)
        if rc != 0:
            emit(err)
            return rc
        result = {"path": os.path.abspath(args.output), "format": args.format}
    else:
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
        if not isinstance(result, dict):
            emit({"ok": False, "error": "WPI_BAD_RESULT",
                  "detail": f"run_export_sync 返回 {type(result).__name__},期望 dict"})
            return 1

    warnings: list[str] = []

    # CMYK 打印交付:PNG → CMYK PDF + TIFF(印刷流程,见 print-cmyk.md)
    if args.cmyk:
        png_path = os.path.splitext(args.output)[0] + ".png"
        if os.path.isfile(png_path):
            try:
                from PIL import Image
                im = Image.open(png_path).convert("CMYK")
                base = os.path.splitext(args.output)[0]
                im.save(base + "-cmyk.pdf", resolution=300)
                im.save(base + "-cmyk.tif", compression="tiff_lzw")
                warnings.append(
                    f"CMYK 已导出: {base}-cmyk.pdf / {base}-cmyk.tif")
            except ImportError:
                warnings.append("Pillow 未安装,已跳过 CMYK 交付: pip install Pillow")
        else:
            warnings.append(f"未找到 PNG({png_path}),跳过 CMYK 交付")

    payload = {k: result.get(k) for k in FIELDS} if result else {}
    payload["ok"] = True
    if kind == "source":
        payload["engine"] = "wpi-source"
    if warnings:
        payload["warnings"] = (result.get("warnings") or []) + warnings
    emit(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
