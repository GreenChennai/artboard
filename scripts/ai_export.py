"""一键矢量导出:项目目录 → 分层 AI 可编辑 PDF(默认)/ SVG / EPS / 真 .ai。

用法(在项目目录或任意位置):
  python ai_export.py <项目目录>                  # 出 分层AI可编辑PDF
  python ai_export.py <项目目录> --svg --eps --ai  # 追加 SVG / EPS / 真 .ai
  python ai_export.py <项目目录>/src/index.html --svg

画布尺寸自动读取项目 project.json(width/height),缺省 1080×1440。
正常 artboard 流水线不含本步——仅当用户明确要矢量/工程文件时使用。
"""

import argparse
import json
import os
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
import webhtml2vectoredit as core


def resolve_canvas(source: str) -> tuple[int | None, int | None]:
    """从 source(或其父目录)的 project.json 读画布;没有则交给核心自探测。"""
    probe = source if os.path.isdir(source) else os.path.dirname(os.path.abspath(source))
    for cand in (os.path.join(probe, "project.json"),
                 os.path.join(os.path.dirname(probe), "project.json")):
        if os.path.isfile(cand):
            try:
                j = json.load(open(cand, encoding="utf-8"))
                w = int(j.get("width") or 0)
                h = int(j.get("height") or 0)
                if w and h:
                    return w, h
            except (ValueError, OSError):
                pass
    return None, None


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="一键矢量/工程文件导出(WebHtml2VectorEdit)")
    p.add_argument("source", help="项目目录或 HTML 文件")
    p.add_argument("--out", default="", help="输出目录(默认 <项目>/export)")
    p.add_argument("--name", default="poster", help="输出文件名前缀(默认 poster)")
    p.add_argument("--svg", action="store_true", help="追加 SVG")
    p.add_argument("--eps", action="store_true", help="追加 EPS")
    p.add_argument("--outline", action="store_true", help="追加免字体依赖 PDF")
    p.add_argument("--ai", action="store_true",
                   help="追加真 .ai(需本机装有 Illustrator)")
    p.add_argument("--no-layers", action="store_true", help="不分层")
    p.add_argument("--no-check", action="store_true", help="跳过 SSIM 自检")
    args = p.parse_args()

    source = os.path.abspath(args.source)
    src_html = os.path.join(source, "src", "index.html")   # 项目目录 → src/
    if os.path.isdir(source) and os.path.isfile(src_html):
        source = os.path.join(source, "src")
    if not os.path.exists(source):
        emit({"ok": False, "error": "SOURCE_NOT_FOUND", "detail": source})
        return 2
    root = os.path.dirname(source) if os.path.basename(source) == "src" else source
    out_dir = os.path.abspath(args.out) if args.out else (
        os.path.join(root, "export") if os.path.isdir(root)
        else os.path.dirname(source))
    os.makedirs(out_dir, exist_ok=True)
    prefix = os.path.join(out_dir, args.name)
    w, h = resolve_canvas(source)

    fmts = ["ai-pdf"]
    if args.svg:
        fmts.append("svg")
    if args.eps:
        fmts.append("eps")
    if args.outline:
        fmts.append("outline-pdf")

    print(f"[1/2] 画布 {w}×{h} · 格式 {'/'.join(fmts)}"
          + (" + 真.ai" if args.ai else ""), file=sys.stderr)
    try:
        job = core.WebHtml2VectorEdit(
            source=source, output=prefix, width=w, height=h,
            layers=not args.no_layers, formats=tuple(fmts),
            no_check=args.no_check)
        report = job.run()
    except Exception as exc:  # noqa: BLE001
        emit({"ok": False, "error": type(exc).__name__, "detail": str(exc)})
        return 1

    if args.ai:
        src_pdf = report["outputs"].get("print-pdf") or report["outputs"].get("ai-pdf")
        if src_pdf:
            try:
                report["ai_layers"] = core.ai_save(src_pdf, prefix + ".ai")
                report["outputs"]["ai"] = prefix + ".ai"
            except Exception as exc:  # noqa: BLE001
                report.setdefault("warnings", []).append(
                    f".ai 产出失败: {exc}(其余产物不受影响)")

    emit(report)
    return 0 if report.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
