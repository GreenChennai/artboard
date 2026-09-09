"""artboard 一键导出批处理生成器:给项目里每个 .html 生成自识别导出 bat。

用法:
  python make_bats.py <项目路径> [--force]

- 每个 src/*.html 生成同目录 `导出-<名字>.bat`(自识别:双击即导出同名 HTML);
- 已存在的 bat 不覆盖(--force 可覆盖);
- 模板:tools/导出-模板.bat(与本脚本同规则维护)。

bat 能力:双击 → WPI 引擎导出 高清 PNG + PDF;HTML 含 @keyframes 动画时
追加 GIF/MP4;画布参数自动读 project.json;打印件可配合 project.json
"print": true 提醒走 CMYK 流程。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import cfg

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(SKILL_DIR, "tools", "导出-模板.bat")

BAT_HEADER = r"""@echo off
rem ============================================================
rem  artboard 一键导出批处理(自识别版,由 make_bats.py 生成)
rem  规则:本文件名去掉"导出-"前缀 = 同目录同名 .html
rem  输出:.\导出\ 下生成 PNG(高清)+ PDF;
rem        若 HTML 含 @keyframes 动画,追加 GIF / MP4(需 FFmpeg)
rem ============================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title artboard 一键导出 - %~n0

set "SELF=%~n0"
set "NAME=!SELF:导出-=!"
set "SRC=%~dp0!NAME!.html"
set "OUT=%~dp0导出"

if not exist "%SRC%" (
  echo [X] 未找到 %SRC%
  pause
  exit /b 2
)

rem ---- 引擎(生成时已解析烧定)----

rem ---- 画布参数(生成时从 project.json 烧定)----

set "HARG="
if defined H set "HARG=--height %H%"

echo ============================================
echo   artboard 一键导出  ^|  %NAME%
echo   画布 %W% px  ^|  倍率 x%SC%  ^|  输出: 导出\
echo ============================================
if not exist "%OUT%" mkdir "%OUT%"

echo.
echo [1/3] 高清 PNG…
if defined EXEARG (
  %EXE% "%EXEARG%" --export --source "%SRC%" --output "%OUT%\%NAME%.png" --width %W% --scale %SC% %HARG%
) else (
  "%EXE%" --source "%SRC%" --output "%OUT%\%NAME%.png" --width %W% --scale %SC% %HARG%
)
if exist "%OUT%\%NAME%.png" (echo   [OK] %NAME%.png) else (echo   [X] PNG 导出失败)

echo.
echo [2/3] PDF…
if defined EXEARG (
  %EXE% "%EXEARG%" --export --source "%SRC%" --output "%OUT%\%NAME%.pdf" --width %W% --format PDF %HARG%
) else (
  "%EXE%" --source "%SRC%" --output "%OUT%\%NAME%.pdf" --width %W% --format PDF %HARG%
)
if exist "%OUT%\%NAME%.pdf" (echo   [OK] %NAME%.pdf) else (echo   [X] PDF 导出失败)

findstr /c:"@keyframes" "%SRC%" >nul 2>&1
if errorlevel 1 goto done
echo.
echo [3/3] 检测到动画,导出 GIF / MP4…
echo   -- GIF(25fps,录制 6 秒)…
if defined EXEARG (
  %EXE% "%EXEARG%" --export --source "%SRC%" --output "%OUT%\%NAME%.gif" --width %W% --scale %SC% --format GIF --fps 25 --max-wait 6 %HARG%
) else (
  "%EXE%" --source "%SRC%" --output "%OUT%\%NAME%.gif" --width %W% --scale %SC% --format GIF --fps 25 --max-wait 6 %HARG%
)
set "FF="
where ffmpeg >nul 2>&1 && set "FF=1"
if defined ARTBOARD_FFMPEG if exist "%ARTBOARD_FFMPEG%" set "FF=1"
if defined FF (
  echo   -- MP4(30fps,需 FFmpeg)…
  if defined EXEARG (
    %EXE% "%EXEARG%" --export --source "%SRC%" --output "%OUT%\%NAME%.mp4" --width %W% --scale %SC% --format MP4 --fps 30 --max-wait 6 %HARG%
  ) else (
    "%EXE%" --source "%SRC%" --output "%OUT%\%NAME%.mp4" --width %W% --scale %SC% --format MP4 --fps 30 --max-wait 6 %HARG%
  )
) else (
  echo   -- 未找到 FFmpeg,跳过 MP4
)

:done
echo.
echo ============================================
echo   完成!文件在: %OUT%
echo ============================================
pause
exit /b 0
"""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("project")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    src = os.path.join(os.path.abspath(args.project), "src")
    if not os.path.isdir(src):
        emit_fail = json.dumps({"ok": False, "error": f"src/ 不存在: {src}"},
                               ensure_ascii=False)
        print(emit_fail)
        return 1

    created, skipped = [], []
    # 画布参数:从 project.json 读取并烧定进 bat(生成时定,运行时零解析)
    W, SC, H = 1080, 2, 0
    pj = os.path.join(os.path.dirname(src), "project.json")
    if os.path.isfile(pj):
        try:
            j = json.load(open(pj, encoding="utf-8"))
            W = j.get("width", W)
            H = j.get("height", 0)
        except Exception:
            pass

    # 解析引擎:cli exe > source(python main.py)> artboard-tools 默认位
    engine_exe, engine_arg = None, None
    cli = cfg("wpi_cli_exe")
    if cli and os.path.isfile(cli):
        engine_exe = cli
    else:
        wp = cfg("wpi_path")
        if wp and os.path.isfile(os.path.join(wp, "src", "main.py")):
            engine_exe, engine_arg = "python", os.path.join(wp, "src", "main.py")
        else:
            cand = os.path.join(os.path.expanduser("~"),
                                "artboard-tools", "WPI", "WPI-noGUI-cli.exe")
            if os.path.isfile(cand):
                engine_exe = cand

    for fn in sorted(os.listdir(src)):
        if not fn.lower().endswith((".html", ".htm")):
            continue
        name = os.path.splitext(fn)[0]
        bat = os.path.join(src, f"导出-{name}.bat")
        if os.path.isfile(bat) and not args.force:
            skipped.append(os.path.basename(bat))
            continue
        engine_lines = ""
        if engine_exe:
            engine_lines += f'set "EXE={engine_exe}"\r\n'
        if engine_arg:
            engine_lines += f'set "EXEARG={engine_arg}"\r\n'
        canvas_lines = f'set "W={W}"\r\nset "SC={SC}"\r\nset "H={H}"\r\n'
        bat_src = BAT_HEADER.replace(
            "rem ---- 引擎(生成时已解析烧定)----",
            engine_lines + canvas_lines + "rem ---- 引擎/画布(已烧定,重跑 make_bats.py 可刷新)----")
        with open(bat, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(bat_src)
        created.append(os.path.basename(bat))

    print(json.dumps({"ok": True, "created": created, "skipped": skipped,
                      "hint": "双击 bat 即可导出 PNG+PDF(动图含 GIF/MP4),无需 Agent"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
