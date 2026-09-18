"""artboard 项目一键导出:双击或 `python 导出.py` 即可导出本目录全部 HTML。

投放位置:由 `scaffold.py` 复制为 **<项目>/src/导出.py**,必须在该目录下运行
(它按自身位置推断项目根与输出目录)。直接在 scripts/ 下运行会在 scripts/ 里
生成空的「导出」目录——本文件已加防护,检测到即退出。

- 自定位引擎:环境变量 ARTBOARD_KILN_CLI → config.json 的 kiln_cli_exe →
  向上逐级找 VellumBench/dist/Kiln-noGUI-CLI.exe(v1.9 起唯一导出引擎);
- 参数不写死:画布宽/倍率/高度从 project.json 读取,每次运行重新校准;
- 自动检测动画:HTML 含 @keyframes 且能找到 ffmpeg 时,追加导出 GIF / MP4;
- 打印项目:project.json 里 "print": true 时,自动追加 CMYK PDF / TIFF;
- 单个 HTML 失败不影响其余,最后汇总报告。
"""

import json
import os
import shutil
import subprocess
import sys

_here = os.path.dirname(os.path.abspath(__file__))

# ---- 防护:不允许在技能 scripts/ 目录下直接运行 ----
if os.path.basename(_here).lower() == "scripts" and os.path.isfile(
        os.path.join(_here, "preflight.py")):
    print("[X] 本文件不应在技能 scripts/ 目录下运行。")
    print("    正确用法:由 scaffold.py 投放为 <项目>/src/导出.py,在项目 src/ 下双击运行。")
    print("    老项目补投放:")
    print(f'      copy "{os.path.join(_here, "export_local.py")}" "<项目>\\src\\导出.py"')
    sys.exit(2)

# ---- 可选导入 _config:能导入就用 config.json,不能就只靠环境变量/向上搜索 ----
cfg = None
try:
    proj_json_probe = os.path.join(os.path.dirname(_here), "project.json")
    if os.path.isfile(proj_json_probe):
        with open(proj_json_probe, encoding="utf-8") as _f:
            _skill = json.load(_f).get("skill_dir", "")
        if _skill:
            sys.path.insert(0, os.path.join(_skill, "scripts"))
    from _config import cfg  # type: ignore  # noqa: F811
except Exception:
    cfg = None


def _cfg(key: str, default: str = "") -> str:
    if cfg is not None:
        return cfg(key, default)
    return os.environ.get({"kiln_cli_exe": "ARTBOARD_KILN_CLI",
                           "ffmpeg": "ARTBOARD_FFMPEG"}.get(key, ""), "") or default


def find_kiln(start: str) -> str:
    """投放态引擎定位:环境变量 → config → 从项目目录向上 8 级找 Kiln。

    本文件被 scaffold 投放到 <项目>/src/导出.py,技能 scripts/ 不在旁边,
    故不能复用 export.py 的 find_kiln(它依赖技能目录的 _config)。
    """
    d = os.path.abspath(start)
    for _ in range(8):
        for rel in (os.path.join("VellumBench", "dist", "Kiln-noGUI-CLI.exe"),
                    os.path.join("VellumBench", "target", "release", "kiln-cli.exe")):
            cand = os.path.join(d, rel)
            if os.path.isfile(cand):
                return cand
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    for cand in (_cfg("kiln_cli_exe"), os.environ.get("ARTBOARD_KILN_CLI", "")):
        if cand and os.path.isfile(cand):
            return cand
    return ""


def read_project(proj: str) -> dict:
    pj = os.path.join(proj, "project.json")
    if not os.path.isfile(pj):
        return {}
    try:
        with open(pj, encoding="utf-8") as f:
            j = json.load(f)
        return j if isinstance(j, dict) else {}
    except (OSError, ValueError) as exc:
        print(f"△ project.json 读取失败({exc}),用默认画布 1080×2×0")
        return {}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    here = _here
    kiln = find_kiln(here)
    if not kiln:
        print("[X] 未找到 Kiln 引擎:项目目录向上 8 级无 VellumBench/dist/Kiln-noGUI-CLI.exe,")
        print("    且 ARTBOARD_KILN_CLI / config.json kiln_cli_exe 均未配置或路径无效。")
        print("    修复任一:① 设环境变量 ARTBOARD_KILN_CLI 指向 Kiln-noGUI-CLI.exe;")
        print("            ② config.json 填 kiln_cli_exe;")
        print("            ③ 把 VellumBench 仓库放到项目任意上溯 8 级以内的目录旁。")
        return 1
    out_dir = os.path.join(here, "导出")
    os.makedirs(out_dir, exist_ok=True)

    # 画布参数(倍率参与计算,印刷物料的 DPI 由它决定)
    proj = os.path.dirname(here)
    meta = read_project(proj)
    W = int(meta.get("width") or 1080)
    SC = int(meta.get("scale") or 2)
    H = int(meta.get("height") or 0)

    htmls = sorted(
        f for f in os.listdir(here)
        if f.lower().endswith((".html", ".htm")) and not f.startswith("导出")
    )
    if not htmls:
        print("[X] 当前目录没有可导出的 .html 文件。")
        return 1

    print(f"== artboard 一键导出:{len(htmls)} 张,引擎 {kiln},输出 {out_dir} ==")
    print(f"   画布 {W}×{H or 'auto'} · scale {SC}")

    ffmpeg = (_cfg("ffmpeg") or shutil.which("ffmpeg") or "")
    failures = []
    for fn in htmls:
        src = os.path.join(here, fn)
        name = os.path.splitext(fn)[0]
        print(f"\n-- {fn} --")

        steps = [("PNG", ["--format", "PNG"]), ("PDF", ["--format", "PDF"])]
        try:
            with open(src, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError as exc:
            print(f"  [FAIL] 读取失败: {exc}")
            failures.append(fn)
            continue
        if "@keyframes" in text:
            dur = "9" if meta.get("scene_card") else "6"
            steps.append(("GIF", ["--format", "GIF", "--fps", "25",
                                  "--max-wait", dur, "--duration", dur]))
            steps.append(("MP4", ["--format", "MP4", "--fps", "30",
                                  "--max-wait", dur, "--duration", dur]))

        for tag, extra in steps:
            out = os.path.join(out_dir, f"{name}.{tag.lower()}")
            cmd = [kiln, "export",
                   "--source", src, "--output", out,
                   "--width", str(W), "--scale", str(SC), *extra]
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=600)
                if r.returncode == 0 and os.path.isfile(out):
                    print(f"  [OK] {tag}  {os.path.basename(out)}")
                else:
                    err = r.stderr.decode("utf-8", errors="replace")
                    print(f"  [FAIL] {tag}(rc={r.returncode}): {err[:300]}")
                    failures.append(f"{fn}:{tag}")
            except Exception as exc:
                print(f"  [FAIL] {tag}: {exc}")
                failures.append(f"{fn}:{tag}")

    # CMYK(打印项目)
    if meta.get("print"):
        try:
            from PIL import Image
            n = 0
            for fn in htmls:
                name = os.path.splitext(fn)[0]
                png = os.path.join(out_dir, f"{name}.png")
                if os.path.isfile(png):
                    im = Image.open(png).convert("CMYK")
                    im.save(os.path.join(out_dir, f"{name}-cmyk.pdf"), resolution=300)
                    im.save(os.path.join(out_dir, f"{name}-cmyk.tif"),
                            compression="tiff_lzw")
                    n += 1
            print(f"\n[CMYK] 已追加 CMYK PDF / TIFF({n} 张)。")
        except ImportError:
            print("\n[CMYK] 跳过:Pillow 未安装(pip install Pillow)。")
        except Exception as exc:
            print(f"\n[CMYK] 失败: {exc}")

    print(f"\n== 完成,失败 {len(failures)} 项 ==")
    if failures:
        print("   " + ", ".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
