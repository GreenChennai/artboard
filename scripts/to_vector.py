"""artboard 矢量交付 CLI(薄壳):核心在 webhtml2vectoredit.py,不依赖 WPI。

用法:
  python to_vector.py --source <proj>/src --output <proj>/export/poster \
      --width 1080 --height 1440 \
      [--formats ai-pdf,svg,eps,print-pdf,outline-pdf] [--no-layers] \
      [--eps-engine poppler|gs] [--ai] [--threshold 0.95] [--no-check] [--max-wait 15]

默认只出「分层 AI 可编辑 PDF」(Illustrator 打开即见图层);SVG/EPS 等按需加。
正常流水线不含这一步——仅当用户明确要矢量/工程文件时才运行;
一键用法见 ai_export.py。细则与验收标准见 references/vector-export.md。

输出:进度走 stderr,末行单行 JSON 到 stdout(同 export.py 约定)。
"""

import argparse
import json
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import webhtml2vectoredit as core

ALL_FORMATS = ("ai-pdf", "print-pdf", "svg", "eps", "outline-pdf")


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="artboard 矢量交付转换器(WebHtml2VectorEdit)")
    p.add_argument("--source", required=True, help="项目目录或 HTML 文件")
    p.add_argument("--output", required=True, help="输出前缀(无扩展名)")
    p.add_argument("--width", type=int, required=True, help="CSS 画布宽(px)")
    p.add_argument("--height", type=int, required=True, help="CSS 画布高(px)")
    p.add_argument("--formats", default="ai-pdf",
                   help="逗号分隔:" + ",".join(ALL_FORMATS) + "(默认仅分层 AI 可编辑 PDF)")
    p.add_argument("--no-layers", action="store_true",
                   help="跳过 DOM 分层(ai-pdf 退化为单层平面 PDF)")
    p.add_argument("--eps-engine", default="poppler", choices=["poppler", "gs"],
                   help="poppler 只压平透明区;gs 转曲但遇透明整页栅格化")
    p.add_argument("--ai", action="store_true",
                   help="按 DOM 组件树原生构建 .ai:嵌套真组(Ctrl+G 语义)+"
                        "整句文字+背景/内容双层;需已安装 Illustrator,启动约 30-90s")
    p.add_argument("--threshold", type=float, default=0.95)
    p.add_argument("--no-check", action="store_true", help="跳过相似度自检")
    p.add_argument("--max-wait", type=float, default=15.0, dest="max_wait")
    args = p.parse_args()

    fmts = tuple(f.strip() for f in args.formats.split(",") if f.strip())
    bad = [f for f in fmts if f not in ALL_FORMATS]
    if bad:
        emit({"ok": False, "error": "BAD_FORMAT", "detail": ",".join(bad),
              "hint": "可选:" + ",".join(ALL_FORMATS)})
        return 2
    if "svg" in fmts and not core.poppler_exe("pdftocairo.exe"):
        emit({"ok": False, "error": "TOOL_MISSING", "detail": "pdftocairo",
              "hint": "跑 python scripts/setup_vector.py 一键部署,"
                      "或 config.json 手填 poppler_dir / gs_path"})
        return 2
    if "eps" in fmts and args.eps_engine == "poppler" and not core.poppler_exe("pdftops.exe"):
        emit({"ok": False, "error": "TOOL_MISSING", "detail": "pdftops",
              "hint": "跑 python scripts/setup_vector.py 或改 --eps-engine gs"})
        return 2
    if "eps" in fmts and args.eps_engine == "gs" and not core.gs_exe():
        emit({"ok": False, "error": "TOOL_MISSING", "detail": "gs",
              "hint": "跑 python scripts/setup_vector.py"})
        return 2

    try:
        job = core.WebHtml2VectorEdit(
            source=args.source, output=args.output,
            width=args.width, height=args.height,
            layers=not args.no_layers, formats=fmts,
            eps_engine=args.eps_engine, threshold=args.threshold,
            no_check=args.no_check, max_wait=args.max_wait)
        report = job.run()
    except Exception as exc:  # noqa: BLE001
        emit({"ok": False, "error": type(exc).__name__, "detail": str(exc)})
        return 1

    if args.ai:
        try:
            report["ai_layers"] = core.ai_build_native(
                args.source, args.output + ".ai", width=args.width,
                height=args.height, max_wait=args.max_wait)
            report["outputs"]["ai"] = args.output + ".ai"
        except Exception as exc:  # noqa: BLE001
            report.setdefault("warnings", []).append(
                f".ai 产出失败: {exc}(其余产物不受影响)")

    emit(report)
    return 0 if report.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
