"""artboard 导出薄壳(主路径):Kiln 原生引擎(v1.9.0 起)→ 失败给 hint。

用法:
  python export.py --source <项目目录|HTML文件> --output out.png \
      [--format PNG|JPG|GIF|MP4|PDF|SVG|EPS|AI|PPTX] [--width 1080] [--scale 1|2|4|8] \
      [--height 0] [--fps 25] [--transparent] [--max-wait 15]

引擎:
  Kiln 原生单文件(config.json: kiln_cli_exe / env ARTBOARD_KILN_CLI,
  兜底自动探测仓库内 VellumBench/dist/Kiln-noGUI-CLI.exe)。
  零浏览器/Python 依赖;GIF/MP4 动画按 --duration(缺省取 --max-wait)逐帧求值。
  找不到引擎 → ok=false + hint(改用 scripts/export_fallback.py,仅 PNG)。

与 WPI 的参数差异(引擎换血):
  --width/--height 为采集视口口径(0 = 按画板几何自适应);非 1080 画幅
  (banner 1920 / kv 1920 / rollup 2362 等)必须显式传入,否则按 1080 渲染。
  --max-wait 在 GIF/MP4 时作为动画时长(--duration)透传,其余格式忽略。
  静态格式单帧;含 @keyframes 的 HTML 输出 GIF/MP4 时自动逐帧求值。

输出:单行 JSON。ok=false 时带 error/hint,按 hint 处理。
"""

import argparse
import json
import os
import subprocess
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)          # safe_path 环境(脚本目录不再自动入 sys.path)
from _config import cfg, near_workspace   # noqa: E402  同目录导入需显式补路径(同 preflight.py)

DEFAULT_KILN = near_workspace(os.path.join("VellumBench", "dist", "Kiln-noGUI-CLI.exe"))
DEFAULT_KILN_DEV = near_workspace(os.path.join("VellumBench", "target", "release", "kiln-cli.exe"))

FIELDS = ("format", "path", "width", "height", "frames", "encoder", "warnings")

# Kiln stderr 里解析出的布局告警(合成画板回填/overflow 裁剪/grid 降级)
kiln_layout_notes: list[str] = []


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def _supports(path: str, flag: str) -> bool:
    """能力探测:二进制参数面是否含 flag(dist 曾长期滞后于源码,
    默认选中旧 CLI 是「技能传了 --height 却一切静默」的根因)。"""
    try:
        r = subprocess.run([path, "export", "--help"], capture_output=True, timeout=20)
    except Exception:  # noqa: BLE001
        return False
    return flag.encode() in r.stdout


def find_kiln() -> str:
    """返回满足参数面的 kiln-cli 路径;找不到返回空串。

    优先 dev 构建(target/release,随源码更新),dist 兜底;能力探测过滤
    参数面滞后的旧二进制(--engine/--height/--vector 为双车道契约最低集)。
    """
    cli = cfg("kiln_cli_exe")
    if cli and os.path.isfile(cli):
        return cli
    need = ("--engine", "--height", "--vector")
    for cand in (DEFAULT_KILN_DEV, DEFAULT_KILN):
        if cand and os.path.isfile(cand) and all(_supports(cand, f) for f in need):
            return cand
    # 全都不满足时退回原顺序放行(让上层拿到可诊断错误,而非静默用旧 CLI)
    for cand in (DEFAULT_KILN, DEFAULT_KILN_DEV):
        if cand and os.path.isfile(cand):
            return cand
    return ""


def export_via_kiln(cli: str, args) -> tuple[int, dict, dict]:
    """Kiln CLI:退出码 0 且产出文件视为成功。

    返回 (退出码, 失败时 error dict, 成功时解析出的引擎单行 JSON)。
    """
    cmd = [cli, "export",
           "--source", args.source, "--output", args.output,
           "--format", args.format,
           "--scale", str(args.scale),
           "--max-wait", str(args.max_wait)]
    if args.width > 0:
        # 0 = 交由 Kiln 按画板几何自适应(非 1080 画幅必须显式传,
        # 否则浏览器车道按 1080 视口渲染;D 修:此前恒传 1080)
        cmd += ["--width", str(args.width)]
    if getattr(args, "height", 0) and args.height > 0:
        # 此前仅解析、从不透传(C 修:与 SKILL.md「固定尺寸必带 --height」对齐)
        cmd += ["--height", str(args.height)]
    if args.format in ("GIF", "MP4"):
        cmd += ["--fps", str(args.fps)]
        # 动画时长:artboard 语义里 --max-wait 即总时长(五段式总长 + 余量)
        cmd += ["--duration", str(args.max_wait)]
    if args.transparent:
        cmd += ["--transparent"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=900)
    except Exception as exc:  # noqa: BLE001
        return 1, {"ok": False, "error": "KILN_CLI_FAILED", "detail": str(exc),
                   "hint": "改用 scripts/export_fallback.py(仅 PNG)"}, {}
    # Kiln stderr 的布局告警要在失败判定前解析(存到模块级供 main 读取)
    global kiln_layout_notes
    kiln_layout_notes = []
    # 两条子路线告警前缀不同:自研布局 vb_layout:、DOM 路线 domwarn
    # (L 修:曾只认前者 → DOM 路线的降级被静默吞掉)
    for line in r.stderr.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        for key, field in (("vb_layout:", "warn"), ("domwarn:", "domwarn")):
            if key not in line:
                continue
            note = line.split(key, 1)[1].rstrip('"}')
            if line.startswith("{"):
                try:
                    note = str(json.loads(line).get(field, note))
                except ValueError:
                    pass
            kiln_layout_notes.append(note)
            break
    # 解析 stdout 单行 JSON(Kiln 契约;B 修:此前只读 stderr,
    # width/height/frames 恒 None,gzh_cover 打印 NonexNone 即此因)
    engine_out: dict = {}
    for line in reversed(r.stdout.decode("utf-8", errors="replace").splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("ok"):
            engine_out = obj
            break
    if r.returncode != 0:
        return 1, {"ok": False, "error": "KILN_CLI_FAILED", "detail": f"rc={r.returncode}",
                   "stderr": r.stderr.decode("utf-8", errors="replace")[:400],
                   "hint": "改用 scripts/export_fallback.py(仅 PNG)"}, engine_out
    if not os.path.isfile(args.output):
        return 1, {"ok": False, "error": "KILN_CLI_NO_OUTPUT", "detail": args.output,
                   "hint": "CLI 退出 0 但没产出文件;改用 scripts/export_fallback.py(仅 PNG)"}, engine_out
    return 0, {}, engine_out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="artboard → Kiln 导出")
    p.add_argument("--source", required=True, help="项目目录 / HTML 文件")
    p.add_argument("--output", required=True)
    p.add_argument("--format", default="PNG",
                   choices=["PNG", "JPG", "GIF", "MP4", "PDF", "SVG", "EPS", "AI", "PPTX"])
    p.add_argument("--width", type=int, default=0,
                   help="采集视口宽(CSS px);0 = Kiln 按画板几何自适应(D 修:"
                        "曾恒传 1080,非 1080 画幅被按 1080 视口渲染)")
    p.add_argument("--scale", type=int, default=1, choices=[1, 2, 4, 8])
    p.add_argument("--height", type=int, default=0,
                   help="采集视口高(CSS px);0 = 自适应;动画卡 100vh 型必须显式锁定")
    p.add_argument("--fps", type=int, default=25)
    p.add_argument("--transparent", action="store_true")
    p.add_argument("--cmyk", action="store_true",
                   help="打印交付:追加导出 CMYK PDF + TIFF(印刷流程见 print-cmyk.md)")
    p.add_argument("--max-wait", type=float, default=15.0, dest="max_wait",
                   help="GIF/MP4 时作为动画总时长(秒),其余格式忽略")
    args = p.parse_args()

    kiln = find_kiln()
    if not kiln:
        emit({"ok": False, "error": "KILN_NOT_FOUND",
              "hint": "未找到 Kiln 引擎。跑 scripts/setup_kiln.py 部署,"
                      "或设 ARTBOARD_KILN_CLI 指向 Kiln-noGUI-CLI.exe,"
                      "或改用 scripts/export_fallback.py(仅 PNG)"})
        return 2

    result: dict = {}
    rc, err, engine_out = export_via_kiln(kiln, args)
    if rc != 0:
        if engine_out:
            err["engine"] = engine_out
        emit(err)
        return rc
    result = {"path": os.path.abspath(args.output), "format": args.format,
              "engine": str(engine_out.get("engine") or "kiln")}
    # 引擎自报字段回填(B 修):width/height/frames 来自引擎单行 JSON
    for k in FIELDS:
        if engine_out.get(k) is not None:
            result[k] = engine_out[k]
    if engine_out.get("vector"):
        result["vector"] = engine_out["vector"]

    warnings: list[str] = []
    # 布局告警透传:画板尺寸被内容回填/裁剪/grid 降级时,调用方必须可见
    # (此前静默 ok:true,存量项目失真无从判定——部署报告 Issue 2/6.3)
    if kiln_layout_notes:
        result["degraded_artboard"] = any(
            ("尺寸回填" in w) or ("裁剪" in w) or ("grid" in w)
            for w in kiln_layout_notes)
        warnings.extend(f"vb_layout:{w}" for w in kiln_layout_notes)

    # CMYK 打印交付:PNG → CMYK PDF + TIFF(印刷流程,见 print-cmyk.md)
    if args.cmyk:
        png_path = os.path.splitext(args.output)[0] + ".png"
        if os.path.isfile(png_path):
            try:
                from PIL import Image
                im = Image.open(png_path).convert("CMYK")
                base = os.path.splitext(args.output)[0]
                im.save(base + "-cmyk.pdf", resolution=300)
                im.save(base + "-cmyk.tif", compression="tiff_lzw")
                warnings.append(
                    f"CMYK 已导出: {base}-cmyk.pdf / {base}-cmyk.tif")
            except ImportError:
                warnings.append("Pillow 未安装,已跳过 CMYK 交付: pip install Pillow")
        else:
            warnings.append(f"未找到 PNG({png_path}),跳过 CMYK 交付")

    payload = {k: result.get(k) for k in FIELDS} if result else {}
    payload["ok"] = True
    payload["engine"] = result.get("engine", "kiln")
    # 引擎自报的降级标志优先于 stderr 文本推断(L 修的一半;另一半在上面的双前缀解析)
    if engine_out.get("degraded_artboard") or engine_out.get("degraded"):
        payload["degraded_artboard"] = True
    if result.get("degraded_artboard"):
        payload["degraded_artboard"] = True
    if warnings:
        payload["warnings"] = (result.get("warnings") or []) + warnings
    emit(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
