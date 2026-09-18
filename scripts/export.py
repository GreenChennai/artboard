"""artboard 导出薄壳(主路径):Kiln 原生引擎(v1.9.0 起)→ 失败给 hint。

用法:
  python export.py --source <项目目录|HTML文件> --output out.png \
      [--format PNG|JPG|GIF|MP4|PDF|SVG|EPS|AI|PPTX] [--width 1080] [--scale 1|2|4|8] \
      [--height 0] [--fps 25] [--transparent] [--max-wait 15]

引擎:
  Kiln 原生单文件(config.json: kiln_cli_exe / env ARTBOARD_KILN_CLI,
  兜底自动探测仓库内 VellumBench/dist/Kiln-noGUI-CLI.exe)。
  零浏览器/Python 依赖;GIF/MP4 动画按 --duration(缺省取 --max-wait)逐帧求值。
  找不到引擎 → ok=false + hint(改用 scripts/export_fallback.py,仅 PNG)。

与 WPI 的参数差异(引擎换血):
  --width 保留但 Kiln 以画板几何为准;--height 不再支持(画板尺寸决定);
  --max-wait 在 GIF/MP4 时作为动画时长(--duration)透传,其余格式忽略。
  静态格式单帧;含 @keyframes 的 HTML 输出 GIF/MP4 时自动逐帧求值。

输出:单行 JSON。ok=false 时带 error/hint,按 hint 处理。
"""

import argparse
import json
import os
import subprocess
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)          # safe_path 环境(脚本目录不再自动入 sys.path)
from _config import cfg, near_workspace   # noqa: E402  同目录导入需显式补路径(同 preflight.py)

DEFAULT_KILN = near_workspace(os.path.join("VellumBench", "dist", "Kiln-noGUI-CLI.exe"))
DEFAULT_KILN_DEV = near_workspace(os.path.join("VellumBench", "target", "release", "kiln-cli.exe"))

FIELDS = ("format", "path", "width", "height", "frames", "encoder", "warnings")

# Kiln stderr 里解析出的布局告警(合成画板回填/overflow 裁剪/grid 降级)
kiln_layout_notes: list[str] = []


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def find_kiln() -> str:
    """返回 kiln-cli exe 路径;找不到返回空串。"""
    cli = cfg("kiln_cli_exe")
    if cli and os.path.isfile(cli):
        return cli
    for cand in (DEFAULT_KILN, DEFAULT_KILN_DEV):
        if cand and os.path.isfile(cand):
            return cand
    return ""


def export_via_kiln(cli: str, args) -> tuple[int, dict]:
    """Kiln CLI:退出码 0 且产出文件视为成功。返回 (退出码, 失败时 error dict)。"""
    cmd = [cli, "export",
           "--source", args.source, "--output", args.output,
           "--format", args.format,
           "--width", str(args.width), "--scale", str(args.scale),
           "--max-wait", str(args.max_wait)]
    if args.format in ("GIF", "MP4"):
        cmd += ["--fps", str(args.fps)]
        # 动画时长:artboard 语义里 --max-wait 即总时长(五段式总长 + 余量)
        cmd += ["--duration", str(args.max_wait)]
    if args.transparent:
        cmd += ["--transparent"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=900)
    except Exception as exc:  # noqa: BLE001
        return 1, {"ok": False, "error": "KILN_CLI_FAILED", "detail": str(exc),
                   "hint": "改用 scripts/export_fallback.py(仅 PNG)"}
    # Kiln stderr 的布局告警要在失败判定前解析(存到模块级供 main 读取)
    global kiln_layout_notes
    kiln_layout_notes = []
    for line in r.stderr.decode("utf-8", errors="replace").splitlines():
        if "vb_layout:" in line:
            kiln_layout_notes.append(line.split("vb_layout:", 1)[1].rstrip('"}'))
    if r.returncode != 0:
        return 1, {"ok": False, "error": "KILN_CLI_FAILED", "detail": f"rc={r.returncode}",
                   "stderr": r.stderr.decode("utf-8", errors="replace")[:400],
                   "hint": "改用 scripts/export_fallback.py(仅 PNG)"}
    if not os.path.isfile(args.output):
        return 1, {"ok": False, "error": "KILN_CLI_NO_OUTPUT", "detail": args.output,
                   "hint": "CLI 退出 0 但没产出文件;改用 scripts/export_fallback.py(仅 PNG)"}
    return 0, {}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="artboard → Kiln 导出")
    p.add_argument("--source", required=True, help="项目目录 / HTML 文件")
    p.add_argument("--output", required=True)
    p.add_argument("--format", default="PNG",
                   choices=["PNG", "JPG", "GIF", "MP4", "PDF", "SVG", "EPS", "AI", "PPTX"])
    p.add_argument("--width", type=int, default=1080)
    p.add_argument("--scale", type=int, default=1, choices=[1, 2, 4, 8])
    p.add_argument("--height", type=int, default=0, help="兼容保留(Kiln 以画板几何为准)")
    p.add_argument("--fps", type=int, default=25)
    p.add_argument("--transparent", action="store_true")
    p.add_argument("--cmyk", action="store_true",
                   help="打印交付:追加导出 CMYK PDF + TIFF(印刷流程见 print-cmyk.md)")
    p.add_argument("--max-wait", type=float, default=15.0, dest="max_wait",
                   help="GIF/MP4 时作为动画总时长(秒),其余格式忽略")
    args = p.parse_args()

    kiln = find_kiln()
    if not kiln:
        emit({"ok": False, "error": "KILN_NOT_FOUND",
              "hint": "未找到 Kiln 引擎。跑 scripts/setup_kiln.py 部署,"
                      "或设 ARTBOARD_KILN_CLI 指向 Kiln-noGUI-CLI.exe,"
                      "或改用 scripts/export_fallback.py(仅 PNG)"})
        return 2

    result: dict = {}
    rc, err = export_via_kiln(kiln, args)
    if rc != 0:
        emit(err)
        return rc
    result = {"path": os.path.abspath(args.output), "format": args.format,
              "engine": "kiln"}

    warnings: list[str] = []
    # 布局告警透传:画板尺寸被内容回填/裁剪/grid 降级时,调用方必须可见
    # (此前静默 ok:true,存量项目失真无从判定——部署报告 Issue 2/6.3)
    if kiln_layout_notes:
        result["degraded_artboard"] = any(
            ("尺寸回填" in w) or ("裁剪" in w) or ("grid" in w)
            for w in kiln_layout_notes)
        warnings.extend(f"vb_layout:{w}" for w in kiln_layout_notes)

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
    payload["engine"] = "kiln"
    if result.get("degraded_artboard"):
        payload["degraded_artboard"] = True
    if warnings:
        payload["warnings"] = (result.get("warnings") or []) + warnings
    emit(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
