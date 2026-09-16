"""一键矢量导出(v1.9:Kiln 原生九格式薄壳)。

用法:
  python ai_export.py <项目目录>                # 出 SVG + PDF
  python ai_export.py <项目目录> --eps --ai     # 追加 EPS / Ai
  python ai_export.py <项目目录>/src/index.html --pptx

画布尺寸由 Kiln 从画板几何自适应;矢量格式全部真文本可编辑
(SVG/PPTX 真文本、PDF CID 中文真文本、EPS 轮廓)。
"""

import argparse
import json
import os
import subprocess
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
from _config import cfg, near_workspace  # noqa: E402


def find_kiln() -> str:
    cli = cfg("kiln_cli_exe")
    if cli and os.path.isfile(cli):
        return cli
    for cand in (near_workspace(os.path.join("VellumBench", "dist", "Kiln-noGUI-CLI.exe")),
                 near_workspace(os.path.join("VellumBench", "target", "release", "kiln-cli.exe"))):
        if cand and os.path.isfile(cand):
            return cand
    return ""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="artboard → Kiln 一键矢量导出")
    p.add_argument("source", help="项目目录 / HTML 文件")
    p.add_argument("--outdir", default="", help="输出目录(缺省 <项目>/export)")
    p.add_argument("--svg", action="store_true")
    p.add_argument("--pdf", action="store_true")
    p.add_argument("--eps", action="store_true")
    p.add_argument("--ai", action="store_true")
    p.add_argument("--pptx", action="store_true")
    args = p.parse_args()

    kiln = find_kiln()
    if not kiln:
        print("[X] 未找到 Kiln 引擎:跑 scripts/setup_kiln.py 或设 ARTBOARD_KILN_CLI")
        return 2

    src = args.source.rstrip("/\\")
    proj = src if os.path.isdir(src) else os.path.dirname(os.path.abspath(src))
    outdir = args.outdir or os.path.join(proj, "export")
    os.makedirs(outdir, exist_ok=True)

    fmts = []
    if args.svg: fmts.append("SVG")
    if args.pdf: fmts.append("PDF")
    if args.eps: fmts.append("EPS")
    if args.ai: fmts.append("AI")
    if args.pptx: fmts.append("PPTX")
    if not fmts:
        fmts = ["SVG", "PDF"]

    base = os.path.splitext(os.path.basename(src if os.path.isfile(src) else "poster"))[0]
    made = []
    failed = []
    for fmt in fmts:
        out = os.path.join(outdir, f"{base}.{fmt.lower()}")
        r = subprocess.run([kiln, "export", "--source", src,
                            "--output", out, "--format", fmt],
                           capture_output=True, timeout=600)
        if r.returncode == 0 and os.path.isfile(out):
            made.append(out)
            print(f"[OK] {fmt}: {out}", file=sys.stderr)
        else:
            failed.append(fmt)
            print(f"[FAIL] {fmt}", file=sys.stderr)
    print(json.dumps({"ok": bool(made), "made": made,
                      "failed": failed or []}, ensure_ascii=False))
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
