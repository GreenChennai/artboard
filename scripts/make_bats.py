"""artboard 一键导出批处理生成:给 src/ 下每个 HTML 生成一个双击即出图的 .bat。

用法:
  python make_bats.py <项目目录>              # 扫 <项目>/src/*.html
  python make_bats.py <项目目录>/src          # 也可直接给 src 目录
  python make_bats.py <项目目录> --formats PNG,PDF,GIF
  python make_bats.py <项目目录> --embed      # bat 自带回退:主引擎失败改用 export_fallback.py

产物:
  <项目>/src/导出-<名字>.bat     —— 双击即导出该张 HTML,不必再叫 Agent
  (配合 scaffold.py 投放的 <项目>/src/导出.py 使用:那个是批量导全部,
   这些 bat 是单个导一张)

细节:
- 画布参数(width/height/scale/print)从 <项目>/project.json 读,不写死;
- HTML 含 @keyframes 且能找到 ffmpeg → 自动追加 GIF / MP4;
- project.json 里 "print": true → 追加 --cmyk(CMYK PDF + TIFF);
- bat 里写死当前 Python 解释器与 export.py 的绝对路径(双击运行时
  系统 PATH 里通常没有 python);
- 已存在的同名 bat 直接覆盖(幂等)。
"""

import argparse
import json
import os
import shutil
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
from _config import cfg  # noqa: E402

SKILL_DIR = os.path.dirname(SCRIPTS)
EXPORT_PY = os.path.join(SCRIPTS, "export.py")
FALLBACK_PY = os.path.join(SCRIPTS, "export_fallback.py")

BAT_HEAD = """@echo off
chcp 65001 >nul
cd /d "%~dp0"
"""

BAT_TAIL_OK = """
echo.
echo [OK] 已导出到 ..\\export\\
pause
"""

BAT_TAIL_FAIL = """
echo.
echo [FAIL] 导出失败,看上面 JSON 里的 hint 字段。
pause
exit /b 1
"""


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def project_of(src_dir: str) -> str:
    return os.path.dirname(src_dir) if os.path.basename(src_dir) == "src" else src_dir


def read_project(proj: str) -> dict:
    pj = os.path.join(proj, "project.json")
    if not os.path.isfile(pj):
        return {}
    try:
        with open(pj, encoding="utf-8") as f:
            j = json.load(f)
        return j if isinstance(j, dict) else {}
    except (OSError, ValueError) as exc:
        print(f"△ project.json 读取失败({exc}),用默认 1080 / scale 2")
        return {}


def ffmpeg_path() -> str:
    return cfg("ffmpeg") or shutil.which("ffmpeg") or ""


def steps_for(html_text: str, formats: list[str], is_print: bool) -> list[tuple[str, list[str]]]:
    """返回 [(产物后缀, 传给 export.py 的额外参数)]。"""
    out = []
    for fmt in formats:
        fmt = fmt.strip().upper()
        if not fmt:
            continue
        if fmt in ("PNG", "PDF"):
            out.append((fmt.lower(), ["--format", fmt]))
        elif fmt in ("GIF", "MP4"):
            fps = "25" if fmt == "GIF" else "30"
            out.append((fmt.lower(), ["--format", fmt, "--fps", fps, "--max-wait", "6"]))
    # 动图:仅在 HTML 真有动画且 ffmpeg 在时才加
    if "@keyframes" in html_text and ffmpeg_path():
        for fmt, extra in (("gif", ["--format", "GIF", "--fps", "25", "--max-wait", "6"]),
                           ("mp4", ["--format", "MP4", "--fps", "30", "--max-wait", "6"])):
            if fmt not in [s for s, _ in out]:
                out.append((fmt, extra))
    return out


def _q(s: str) -> str:
    return f'"{s}"'


def _cmd(py: str, opts: list[tuple[str, str]]) -> str:
    """拼 `python <脚本> --k v …`。opts 里值为空串的当**开关**(只写 --k)。"""
    parts = [_q(sys.executable), _q(py)]
    for k, v in opts:
        parts.append(k)
        if v != "":
            parts.append(_q(v) if " " in v else v)
    return " ".join(parts)


def build_bat(name: str, steps, width: int, height: int, scale: int,
              is_print: bool, embed_fallback: bool) -> str:
    lines = [BAT_HEAD]
    for ext, extra in steps:
        opts = [("--source", f"{name}.html"),
                ("--output", f"..\\export\\{name}.{ext}"),
                ("--width", str(width)), ("--scale", str(scale))]
        opts += [(extra[i], extra[i + 1]) for i in range(0, len(extra), 2)]
        if height:
            opts.append(("--height", str(height)))
        if is_print and ext == "png":
            opts.append(("--cmyk", ""))          # 开关参数,无值

        lines.append(f"echo [{ext.upper()}] {name}.{ext} ...")
        lines.append(_cmd(EXPORT_PY, opts))
        lines.append("if errorlevel 1 (")
        if embed_fallback and ext == "png":
            fb = [("--source", f"{name}.html"),
                  ("--output", f"..\\export\\{name}.png"),
                  ("--width", str(width)), ("--scale", str(min(scale, 2)))]
            if height:
                fb.append(("--height", str(height)))
            # 注意:bat 的 if(...) 块里不能出现半角括号,否则块被提前闭合
            lines.append("  echo   主引擎失败,改用兜底导出 —— 仅 PNG")
            lines.append("  " + _cmd(FALLBACK_PY, fb))
            lines.append("  if errorlevel 1 goto :fail")
        else:
            lines.append("  goto :fail")
        lines.append(")")
    lines.append(BAT_TAIL_OK)
    lines.append("exit /b 0")
    lines.append(":fail")
    lines.append(BAT_TAIL_FAIL)
    return "\n".join(lines)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="给每个 HTML 生成双击即出图的 bat")
    p.add_argument("project", help="项目目录(或直接给 src/ 目录)")
    p.add_argument("--formats", default="PNG,PDF",
                   help="每种格式出一个产物,逗号分隔;默认 PNG,PDF")
    p.add_argument("--embed", action="store_true",
                   help="bat 内加兜底:主引擎失败时自动改调 export_fallback.py")
    args = p.parse_args()

    src_dir = os.path.abspath(args.project)
    if os.path.basename(src_dir) != "src":
        cand = os.path.join(src_dir, "src")
        src_dir = cand if os.path.isdir(cand) else src_dir
    if not os.path.isdir(src_dir):
        emit({"ok": False, "error": "NO_SRC", "detail": src_dir,
              "hint": "参数应是项目目录(内含 src/),或直接给 src/ 目录"})
        return 2

    proj = project_of(src_dir)
    meta = read_project(proj)
    width = int(meta.get("width") or 1080)
    height = int(meta.get("height") or 0)
    scale = int(meta.get("scale") or 2)
    is_print = bool(meta.get("print"))
    out_dir = os.path.join(proj, "export")
    os.makedirs(out_dir, exist_ok=True)

    htmls = sorted(f for f in os.listdir(src_dir)
                   if f.lower().endswith((".html", ".htm"))
                   and not f.startswith("导出"))
    if not htmls:
        emit({"ok": False, "error": "NO_HTML", "detail": src_dir})
        return 1

    made = []
    for fn in htmls:
        name = os.path.splitext(fn)[0]
        try:
            with open(os.path.join(src_dir, fn), encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            text = ""
        steps = steps_for(text, args.formats.split(","), is_print)
        bat = os.path.join(src_dir, f"导出-{name}.bat")
        with open(bat, "w", encoding="utf-8-sig", newline="\r\n") as f:
            f.write(build_bat(name, steps, width, height, scale, is_print, args.embed))
        made.append(bat)

    emit({"ok": True, "project": proj, "src": src_dir, "export": out_dir,
          "count": len(made), "bats": made,
          "canvas": {"width": width, "height": height, "scale": scale,
                     "print": is_print}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
