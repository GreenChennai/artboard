@echo off
rem ============================================================
rem  artboard 一键导出批处理(自识别版)
rem  规则:本文件名去掉"导出-"前缀 = 同目录同名 .html
rem  例:导出-index.bat  →  导出 index.html
rem  输出:.\导出\ 下生成 PNG(高清)+ PDF;
rem        若 HTML 含 @keyframes 动画,追加 GIF / MP4(需 FFmpeg)
rem  放置:与本 HTML 同目录,双击即可,无需修改任何内容。
rem ============================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title artboard 一键导出 - %~n0

rem ---- 1. 自识别目标 HTML ----
set "SELF=%~n0"
set "NAME=!SELF:导出-=!"
set "SRC=%~dp0!NAME!.html"
set "OUT=%~dp0导出"

if not exist "%SRC%" (
  echo [X] 未找到 %SRC%
  echo     批处理文件名必须与 HTML 同名:导出-index.bat 对应 index.html
  pause
  exit /b 2
)

rem ---- 2. 定位 WPI 引擎 ----
set "EXE="
if defined ARTBOARD_WPI_CLI if exist "%ARTBOARD_WPI_CLI%" set "EXE=%ARTBOARD_WPI_CLI%"
if not defined EXE if exist "%USERPROFILE%\artboard-tools\WPI\WPI-noGUI-cli.exe" set "EXE=%USERPROFILE%\artboard-tools\WPI\WPI-noGUI-cli.exe"
if not defined EXE (
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "try{(Get-Content -LiteralPath (Join-Path (Split-Path -Parent '%~f0') '..\..\scripts\export.py') -TotalCount 5 -ErrorAction Stop)|Out-Null}catch{}; $cfg=Join-Path (Get-Location) 'config.json'; if(Test-Path $cfg){(Get-Content $cfg -Raw -Encoding UTF8|ConvertFrom-Json).wpi_cli_exe}" 2^>nul`) do if exist "%%i" set "EXE=%%i"
)
if not defined EXE (
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$d=Split-Path -Parent (Split-Path -Parent (Split-Path -Parent '%~f0'));$p=Join-Path $d 'config.json';if(Test-Path $p){(Get-Content $p -Raw -Encoding UTF8|ConvertFrom-Json).wpi_cli_exe}" 2^>nul`) do if exist "%%i" set "EXE=%%i"
)
if not defined EXE (
  echo [X] 未找到 WPI 引擎 WPI-noGUI-cli.exe
  echo     请先在 Skill 目录运行: python scripts\setup_wpi.py
  echo     或设置环境变量 ARTBOARD_WPI_CLI 指向 WPI-noGUI-cli.exe
  pause
  exit /b 1
)

rem ---- 3. 画布参数(project.json:width / scale / height / print)----
set "W=1080"
set "SC=2"
set "H="
set "PRINT="
set "PJ=%~dp0..\project.json"
for /f "usebackq tokens=1-4 delims= " %%a in (`powershell -NoProfile -Command "$p='%PJ%';if(Test-Path $p){$j=Get-Content $p -Raw -Encoding UTF8|ConvertFrom-Json;$s=if($j.scale){$j.scale}else{2};$h=if($j.height){$j.height}else{0};$pr=if($null -ne $j.print){$j.print}else{$false};Write-Output \"$($j.width) $s $h $pr\"}"`) do (
  set "W=%%a"
  set "SC=%%b"
  if not "%%c"=="0" set "H=%%c"
  if /i "%%d"=="true" set "PRINT=1"
)

set "HARG="
if defined H set "HARG=--height %H%"

echo ============================================
echo   artboard 一键导出  ^|  %NAME%
echo   画布 %W% px  ^|  倍率 x%SC%  ^|  输出: 导出\
echo ============================================

if not exist "%OUT%" mkdir "%OUT%"

rem ---- 4. 高清 PNG ----
echo.
echo [1/3] 高清 PNG(=%W% x %SC% 倍)…
"%EXE%" --source "%SRC%" --output "%OUT%\%NAME%.png" --width %W% --scale %SC% %HARG%
if exist "%OUT%\%NAME%.png" (echo   [OK] %NAME%.png) else (echo   [X] PNG 导出失败)

rem ---- 5. PDF(打印 CMYK 流程见 Skill 的 print-cmyk.md)----
echo.
echo [2/3] PDF…
"%EXE%" --source "%SRC%" --output "%OUT%\%NAME%.pdf" --width %W% --format PDF %HARG%
if exist "%OUT%\%NAME%.pdf" (echo   [OK] %NAME%.pdf) else (echo   [X] PDF 导出失败)

rem ---- 6. 动图:HTML 含 @keyframes 才导 GIF / MP4 ----
findstr /c:"@keyframes" "%SRC%" >nul 2>&1
if errorlevel 1 goto done
echo.
echo [3/3] 检测到动画,导出 GIF / MP4…
echo   -- GIF(25fps,录制 6 秒)…
"%EXE%" --source "%SRC%" --output "%OUT%\%NAME%.gif" --width %W% --scale %SC% --format GIF --fps 25 --max-wait 6 %HARG%
set "FF="
where ffmpeg >nul 2>&1 && set "FF=1"
if defined ARTBOARD_FFMPEG if exist "%ARTBOARD_FFMPEG%" set "FF=1"
if defined FF (
  echo   -- MP4(30fps,需 FFmpeg)…
  "%EXE%" --source "%SRC%" --output "%OUT%\%NAME%.mp4" --width %W% --scale %SC% --format MP4 --fps 30 --max-wait 6 %HARG%
) else (
  echo   -- 未找到 FFmpeg,跳过 MP4(运行 scripts\setup_ffmpeg.py 可解锁)
)

:done
echo.
echo ============================================
echo   完成!文件在: %OUT%
echo ============================================
pause
exit /b 0
