"""artboard 矢量交付 CLI(v1.9:Kiln 原生九格式薄壳)。

用法:
  python to_vector.py --source <proj>/src --outdir <proj>/export       [--formats svg,pdf,eps,ai,pptx] [--scale 1]

矢量交付由 Kiln 原生直出(SVG 真文本/分组、PDF CID 中文真文本 + OCG、
EPS、Ai(PDF 兼容流)、PPTX);不再经过浏览器/poppler 链路。
正常流水线不含这一步——仅当用户明确要矢量/工程文件时才运行。
细则见 references/vector-export.md(v1.9 重写版)。

输出:进度走 stderr,末行单行 JSON 到 stdout(同 export.py 约定)。
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

ALL_FORMATS = ("svg", "pdf", "eps", "ai", "pptx")


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


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
    p = argparse.ArgumentParser(description="artboard → Kiln 矢量交付")
    p.add_argument("--source", required=True, help="项目目录 / HTML 文件")
    p.add_argument("--outdir", required=True, help="输出目录")
    p.add_argument("--formats", default="svg,pdf",
                   help="逗号分隔:" + ",".join(ALL_FORMATS))
    p.add_argument("--scale", type=int, default=1)
    args = p.parse_args()

    kiln = find_kiln()
    if not kiln:
        emit({"ok": False, "error": "KILN_NOT_FOUND",
              "hint": "跑 scripts/setup_kiln.py 部署,或设 ARTBOARD_KILN_CLI"})
        return 2

    fmts = [f.strip().lower() for f in args.formats.split(",") if f.strip()]
    bad = [f for f in fmts if f not in ALL_FORMATS]
    if bad:
        emit({"ok": False, "error": f"未知格式:{','.join(bad)}"})
        return 2

    os.makedirs(args.outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.source.rstrip("/\\") if os.path.isfile(args.source) else "poster"))[0]
    made = []
    for fmt in fmts:
        out = os.path.join(args.outdir, f"{base}.{fmt}")
        r = subprocess.run([kiln, "export", "--source", args.source,
                            "--output", out, "--format", fmt.upper(),
                            "--scale", str(args.scale)],
                           capture_output=True, timeout=600)
        if r.returncode == 0 and os.path.isfile(out):
            made.append(out)
            print(f"[OK] {fmt}: {out}", file=sys.stderr)
        else:
            err = r.stderr.decode("utf-8", errors="replace")[:200]
            print(f"[FAIL] {fmt}: {err}", file=sys.stderr)
    emit({"ok": bool(made), "files": made, "count": len(made)})
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
