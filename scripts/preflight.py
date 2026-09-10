"""artboard 任务预检:渲染环境一次查清,输出人类可读清单 + 单行 JSON。

检查项与严重级:
  FATAL — WPI 不可用且无兜底浏览器:静态导出无法进行,终止。
  WARN  — ffmpeg 缺失:GIF 降级 Pillow、MP4 不可用;任务含动图时先向用户要路径。
  WARN  — 字体/vendor 资产缺失:提示补齐。

用法: python preflight.py [--quick]
退出码: 0=可开工; 1=存在 FATAL。
"""

import json
import os
import shutil
import sys

from _config import cfg

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_WPI = r"E:\平日资料\GitHub\WPI"

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]
FONT_EXTS = (".ttf", ".otf", ".woff", ".woff2", ".ttc", ".otc")


def emit(results: list[dict]) -> None:
    print(json.dumps({"items": results}, ensure_ascii=False))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    results: list[dict] = []

    def add(name: str, level: str, detail: str, hint: str = "") -> None:
        results.append({"check": name, "level": level, "detail": detail, "hint": hint})
        mark = {"FATAL": "✗", "WARN": "△", "PASS": "✓"}[level]
        line = f"{mark} [{level:<5}] {name}: {detail}"
        if hint:
            line += f"\n         ↳ {hint}"
        print(line)

    # 1. WPI
    wpi = cfg("wpi_path", DEFAULT_WPI)
    has_controller = os.path.isfile(
        os.path.join(wpi, "src", "core", "controller.py"))
    if has_controller:
        add("WPI", "PASS", wpi)
    else:
        add("WPI", "WARN", f"未找到 {wpi}",
            "设环境变量 ARTBOARD_WPI 指向 WPI 根目录;或仅用 export_fallback.py 兜底(需 playwright)")

    # 2. 系统浏览器(主路径与兜底都依赖)
    edge = next((p for p in EDGE_PATHS if os.path.isfile(p)), None)
    chrome = next((p for p in CHROME_PATHS if os.path.isfile(p)), None)
    if edge or chrome:
        add("浏览器内核", "PASS", f"{'Edge' if edge else ''}{'+' if edge and chrome else ''}"
            f"{'Chrome' if chrome else ''}")
    else:
        add("浏览器内核", "FATAL", "未找到 Edge/Chrome", "安装 Microsoft Edge 后重试")

    # 3. playwright(兜底路径依赖;主路径由 WPI 依赖)
    try:
        import playwright  # noqa: F401
        add("playwright", "PASS", "可导入")
    except ImportError:
        add("playwright", "WARN", "未安装",
            "pip install playwright —— WPI 不可用时的兜底导出需要它")

    # 4. ffmpeg(动图)
    ffmpeg = (cfg("ffmpeg")
              or os.environ.get("WPI_FFMPEG")
              or shutil.which("ffmpeg")
              or (wpi and os.path.isfile(os.path.join(wpi, "ffmpeg.exe"))
                  and os.path.join(wpi, "ffmpeg.exe"))
              or None)
    if ffmpeg:
        add("ffmpeg", "PASS", str(ffmpeg))
    else:
        add("ffmpeg", "WARN", "未找到",
            "GIF 将用 Pillow 回退(质量略降)、MP4 不可用。"
            "提供 ffmpeg.exe 路径后设置环境变量 ARTBOARD_FFMPEG")

    # 5. 字体库
    fonts_dir = os.path.join(SKILL_DIR, "fonts")
    if os.path.isdir(fonts_dir):
        fams = sorted(d for d in os.listdir(fonts_dir)
                      if os.path.isdir(os.path.join(fonts_dir, d))
                      and not d.startswith("."))
        loaded = [f for f in fams if any(
            fn.lower().endswith(FONT_EXTS)
            for fn in os.listdir(os.path.join(fonts_dir, f)))]
        import json as _json
        manifest = _json.load(open(os.path.join(fonts_dir, "download.json"),
                                   encoding="utf-8")) if os.path.isfile(
            os.path.join(fonts_dir, "download.json")) else {}
        missing = [d for d, e in manifest.items() if not d.startswith("_") and any(
            not os.path.isfile(os.path.join(fonts_dir, d, f))
            for f in e.get("files", []))]
        add("字体库", "PASS" if loaded else "WARN",
            f"{len(loaded)} 款在位" + (f",缺 {len(missing)} 款: {', '.join(missing)}" if missing else ""),
            "缺的跑 scripts/fetch_font.py <目录名> 按需下载" if missing else
            ("渲染将回退系统字体" if not loaded else ""))
    else:
        add("字体库", "WARN", "fonts/ 目录不存在", "静态海报仍可用系统字体渲染")

    # 6. vendor 资产
    vendor = os.path.join(SKILL_DIR, "assets", "vendor")
    for name in ("echarts.min.js", "gsap.min.js"):
        p = os.path.join(vendor, name)
        add(f"vendor/{name}", "PASS" if os.path.isfile(p) else "WARN",
            "就绪" if os.path.isfile(p) else "缺失(图表/动图场景需要)",
            "" if os.path.isfile(p) else "从 cdn 下载: echarts@5 / gsap@3 dist 单文件")

    # 7. 素材体系
    import importlib.util
    if importlib.util.find_spec("rembg"):
        add("rembg(抠图)", "PASS", "可导入")
    else:
        add("rembg(抠图)", "WARN", "未安装",
            "pip install \"rembg[cpu]\" —— 需要抠图/贴纸化的素材任务必装")
    keys = {"Pexels": cfg("pexels_key"), "Pixabay": cfg("pixabay_key")}
    if any(keys.values()):
        add("图库 key", "PASS", ", ".join(k for k, v in keys.items() if v) + "(config.json/环境变量)")
    else:
        add("图库 key", "WARN", "未配置 Pexels/Pixabay key",
            "找图将仅有爬虫通道(素材自动带「版权风险-」前缀);"
            "在 config.json 填 pexels_key/pixabay_key 启用授权干净的图库源")

    # 7.4 视觉模式(Agent 视觉优先 vs 本地模型强制)
    vmode = cfg("vision_mode", "auto")
    add("视觉模式", "PASS",
        f"{vmode}" + ("(Agent 视觉优先,本地 VQA/OCR 为备选)" if vmode == "auto"
                      else "(强制本地 VQA/OCR)") if vmode in ("auto", "local") else f"未知值 {vmode}(按 auto 处理)")

    # 7.5 VQA(看图理解)
    vqa = cfg("vqa_path", r"E:\平日资料\GitHub\VQA")
    if vqa and os.path.isdir(vqa):
        add("VQA", "PASS", vqa)
    else:
        add("VQA", "WARN", "未找到(vqa_path)",
            "看图理解素材内容时将退回 Agent 自身视觉能力;在 config.json 填 vqa_path 启用本地 VQA")
    illo = os.path.join(SKILL_DIR, "assets", "illustrations")
    packs = [d for d in os.listdir(illo) if os.path.isdir(os.path.join(illo, d))] \
        if os.path.isdir(illo) else []
    add("插画包", "PASS" if packs else "WARN",
        f"{len(packs)} 套: {', '.join(packs)}" if packs else "assets/illustrations/ 为空",
        "" if packs else "人物/吉祥物插画兜底不可用")

    emit(results)
    fatal = [r for r in results if r["level"] == "FATAL"]
    warns = [r for r in results if r["level"] == "WARN"]
    pass_n = len(results) - len(fatal) - len(warns)

    # 环境自检报告(人类可读)
    print()
    print("═" * 62)
    print(" artboard 环境自检报告")
    print("═" * 62)
    print(f"  就绪  {pass_n:>2} 项   △ 待补 {len(warns):>2} 项   ✗ 阻断 {len(fatal):>2} 项")
    if fatal:
        for r in fatal:
            print(f"  ✗ {r['check']}: {r['detail']}")
            if r["hint"]:
                print(f"     ↳ {r['hint']}")
    if warns:
        for r in warns:
            print(f"  △ {r['check']}: {r['detail']}")
            if r["hint"]:
                print(f"     ↳ {r['hint']}")
    print("─" * 62)
    # 能力结论(按任务类型)
    def has(name):
        return any(r["check"] == name and r["level"] == "PASS" for r in results)
    caps = []
    caps.append(("静态海报", not fatal))
    caps.append(("动图 GIF", not fatal and (has("ffmpeg") or True)))  # Pillow 回退可用
    caps.append(("MP4 视频", has("ffmpeg")))
    caps.append(("抠图/贴纸", has("rembg(抠图)")))
    caps.append(("授权图库", has("图库 key")))
    caps.append(("二维码", True))
    caps.append(("VQA 看图", has("VQA")))
    line = " · ".join(f"{'✓' if ok else '✗'}{name}" for name, ok in caps)
    print(f"  能力: {line}")
    if fatal:
        print("  结论: 存在阻断项,先按上面提示处理后开工。")
    elif warns:
        print("  结论: 可开工;待补项按需处理(不阻断当前任务)。")
    else:
        print("  结论: 环境全就绪,可直接开工。")
    print("═" * 62)
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
