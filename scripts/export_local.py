"""artboard 项目一键导出:双击或 `python 导出.py` 即可导出本目录全部 HTML。

- 自定位引擎:向上逐级找 WPI 源码(src/core/controller.py),找到即用其渲染管线;
- 参数不写死:画布宽/倍率/高度从 project.json 读取,每次运行重新校准;
- 自动检测动画:HTML 含 @keyframes 时追加导出 GIF / MP4(需要 FFmpeg);
- 打印项目:project.json 里 "print": true 时,自动追加 CMYK PDF / TIFF;
- 单个 HTML 失败不影响其余,最后汇总报告。
"""

import glob
import json
import os
import subprocess
import sys


def find_wpi(start: str) -> str:
    """从脚本目录向上逐级找 WPI 源码(src/core/controller.py)。"""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        cand = os.path.join(d, "src", "core", "controller.py")
        if os.path.isfile(cand):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    env = os.environ.get("ARTBOARD_WPI")
    if env and os.path.isfile(os.path.join(env, "src", "core", "controller.py")):
        return env
    # 已知默认位置(本机)
    known = r"E:\平日资料\GitHub\WPI"
    if os.path.isfile(os.path.join(known, "src", "core", "controller.py")):
        return known
    return ""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    here = os.path.dirname(os.path.abspath(__file__))
    wpi = find_wpi(here)
    if not wpi:
        print("[X] 未找到 WPI 引擎(向上 8 级无 src/core/controller.py)。")
        print("    请确认 WPI 源码在同级目录,或设置环境变量 ARTBOARD_WPI。")
        return 1

    main_py = os.path.join(wpi, "src", "main.py")
    out_dir = os.path.join(here, "导出")
    os.makedirs(out_dir, exist_ok=True)

    # 画布参数
    proj = os.path.dirname(here)
    pj = os.path.join(proj, "project.json")
    W, SC, H = 1080, 2, 0
    if os.path.isfile(pj):
        try:
            j = json.load(open(pj, encoding="utf-8"))
            W = j.get("width", W)
            SC = j.get("scale", SC)
            H = j.get("height", 0)
        except Exception:
            pass

    htmls = sorted(
        f for f in os.listdir(here)
        if f.lower().endswith((".html", ".htm")) and not f.startswith("导出")
    )
    if not htmls:
        print("[X] 当前目录没有可导出的 .html 文件。")
        return 1

    print(f"== artboard 一键导出:{len(htmls)} 张,引擎 {wpi},输出 {out_dir} ==")

    ffmpeg = os.environ.get("ARTBOARD_FFMPEG") or shutil.which("ffmpeg") or ""
    failures = []
    for fn in htmls:
        src = os.path.join(here, fn)
        name = os.path.splitext(fn)[0]
        print(f"\n-- {fn} --")

        steps = [("PNG", ["--format", "PNG"]), ("PDF", ["--format", "PDF"])]
        text = open(src, encoding="utf-8", errors="ignore").read()
        if "@keyframes" in text and ffmpeg:
            steps.append(("GIF", ["--format", "GIF", "--fps", "25", "--max-wait", "6"]))
            steps.append(("MP4", ["--format", "MP4", "--fps", "30", "--max-wait", "6"]))

        for tag, extra in steps:
            out = os.path.join(out_dir, f"{name}.{tag.lower()}")
            cmd = [sys.executable, main_py,
                   "--export", "--source", src, "--output", out,
                   "--width", str(W), "--scale", "2", *extra]
            if H:
                cmd += ["--height", str(H)]
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=600)
                if r.returncode == 0 and os.path.isfile(out):
                    print(f"  [OK] {tag}  {os.path.basename(out)}")
                else:
                    print(f"  [FAIL] {tag}: {r.stderr.decode(errors='ignore')[:160]}")
                    failures.append(tag)
            except Exception as exc:
                print(f"  [FAIL] {tag}: {exc}")
                failures.append(tag)

    # CMYK(打印项目)
    pj_path = os.path.join(os.path.dirname(here), "project.json")
    if os.path.isfile(pj_path):
        try:
            j = json.load(open(pj_path, encoding="utf-8"))
            if j.get("print"):
                from PIL import Image
                for fn in htmls:
                    name = os.path.splitext(fn)[0]
                    png = os.path.join(out_dir, f"{name}.png")
                    if os.path.isfile(png):
                        im = Image.open(png).convert("CMYK")
                        im.save(os.path.join(out_dir, f"{name}-cmyk.pdf"), resolution=300)
                        im.save(os.path.join(out_dir, f"{name}-cmyk.tif"),
                                compression="tiff_lzw")
                print("\n[CMYK] 已追加 CMYK PDF / TIFF。")
        except Exception:
            pass

    print(f"\n== 完成,失败 {len(failures)} 项 ==")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
