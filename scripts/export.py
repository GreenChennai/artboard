"""artboard 导出薄壳(主路径):Kiln 原生引擎(v1.9.0 起)→ 失败给 hint。

用法:
  python export.py --source <项目目录|HTML文件> --output out.png \
     [--format PNG|JPG|GIF|MP4|PDF|SVG|EPS|AI|PPTX] [--width 1080] [--scale 1|2|4|8] \
     [--height 0] [--fps 25] [--transparent] [--max-wait 15] [--timeout 900]

引擎:
  Kiln 原生单文件(config.json: kiln_cli_exe / env ARTBOARD_KILN_CLI,
  兜底自动探测仓库内 VellumBench/dist/Kiln-noGUI-CLI.exe)。
  零浏览器/Python 依赖;GIF/MP4 动画按 --duration 逐帧求值。
  找不到引擎 → ok=false + hint(改用 scripts/export_fallback.py,仅 PNG)。

三个时间量,别混(混了就是 v0.14.1 之后最常见的导出失败):
  --duration  GIF/MP4 的**动画总时长**(秒)。Kiln 侧同名参数。
  --timeout  本进程树(含浏览器孙进程)的**墙钟上限**(秒),超时即强杀并
             如实报 KILN_CLI_TIMEOUT。这是"卡住且杀不掉"的唯一解药。
  --max-wait  浏览器车道 settle/截图的**总预算**(秒,Kiln ≥0.14.1 才真接线,
             此前被静默忽略)。**默认不传** —— 不传即用 Kiln 各阶段默认上限
             (settle 5s / 截图 180s / printToPDF 300s);传了会把上面所有阶段
             一起收口到该值,重页面与逐帧动画必然中途耗尽。只在确认引擎慢
             而非挂死、需要给静默等待更长预算时才显式给。

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
from _proc import run as run_tree          # noqa: E402  进程树超时(见 _proc.py 头注)

DEFAULT_KILN = near_workspace(os.path.join("VellumBench", "dist", "Kiln-noGUI-CLI.exe"))
DEFAULT_KILN_DEV = near_workspace(os.path.join("VellumBench", "target", "release", "kiln-cli.exe"))

FIELDS = ("format", "path", "width", "height", "frames", "encoder", "warnings")

# Kiln stderr 里解析出的布局告警(合成画板回填/overflow 裁剪/grid 降级)
kiln_layout_notes: list[str] = []


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def _export_help(path: str) -> bytes:
    try:
        return subprocess.run([path, "export", "--help"],
                              capture_output=True, timeout=20).stdout or b""
    except Exception:  # noqa: BLE001
        return b""


def _supports(path: str, flags: tuple) -> bool:
    """能力探测:二进制参数面是否含这些 flag。

    dist 曾长期滞后于源码,默认选中旧 CLI 是「技能传了 --height 却一切静默」
    的根因。`--duration` 也在契约内 —— 动画车道靠它,缺了等于交出九格式里的
    两格(0.14.1 起 `--max-wait` 已从「静默忽略」变成真总预算,新旧 CLI 行为
    完全不同,光看 `--engine` 分不出来)。
    """
    help_txt = _export_help(path)
    return all(f.encode() in help_txt for f in flags)


# 双车道 + 动画时长的最低参数面契约
NEED_FLAGS = ("--engine", "--height", "--vector", "--duration")


def _candidates() -> list:
    """所有在位的 Kiln 候选(显式配置优先,去重)。"""
    out = []
    configured = cfg("kiln_cli_exe")
    if configured and os.path.isfile(configured):
        out.append(configured)
    out += [c for c in (DEFAULT_KILN_DEV, DEFAULT_KILN)
            if c and os.path.isfile(c) and c not in out]
    return out


def find_kiln() -> str:
    """返回满足参数面的 kiln-cli 路径;找不到返回空串。

    优先 dev 构建(target/release,随源码更新),dist 兜底。所有候选走**同一条**
    判定 —— 显式配置的 cfg 也不例外:配错了要报可诊断的错误,而不是静默用旧 CLI。
    """
    for cand in _candidates():
        if _supports(cand, NEED_FLAGS):
            return cand
    return ""


def export_via_kiln(cli: str, args) -> tuple[int, dict, dict]:
    """Kiln CLI:退出码 0 且产出文件视为成功。

    返回 (退出码, 失败时 error dict, 成功时解析出的引擎单行 JSON)。
    """
    cmd = [cli, "export",
           "--source", args.source, "--output", args.output,
           "--format", args.format,
           "--scale", str(args.scale)]
    if args.width > 0:
        # 0 = 交由 Kiln 按画板几何自适应(非 1080 画幅必须显式传,
        # 否则浏览器车道按 1080 视口渲染)
        cmd += ["--width", str(args.width)]
    if args.height > 0:
        # 与 SKILL.md「固定尺寸必带 --height」对齐
        cmd += ["--height", str(args.height)]
    if args.format in ("GIF", "MP4"):
        cmd += ["--fps", str(args.fps),
                "--duration", str(args.max_wait)]
    if args.transparent:
        cmd += ["--transparent"]
    # --max-wait 只在用户显式给预算时下发:Kiln ≥0.14.1 把它当浏览器车道
    # **总 deadline**(settle + 全部 CDP 长等待),默认 15s 会让重页面与
    # 逐帧动画中途耗尽。不传 = 各阶段默认上限,这才是绝大多数情形想要的。
    if args.max_wait_budget > 0:
        cmd += ["--max-wait", str(args.max_wait_budget)]
    # MP4/GIF 编码参数(Kiln v0.14.2 起可配,此前只能改上游或事后 ffmpeg 转码)。
    # **默认全不传** = 落编码器默认 = 逐位保持旧行为;这里只做薄透传,
    # 语义与取舍见 references/export.md「GIF / MP4 的编码质量」。
    # 注意 `--bf 0` 是显式意图(关 B 帧,让开头 DTS 不为负 → 部分播放器首帧黑),
    # 所以用 is not None 判定而不是真值判定。
    if getattr(args, "gop", None):
        cmd += ["--gop", str(args.gop)]
    if getattr(args, "bf", None) is not None:
        cmd += ["--bf", str(args.bf)]
    if getattr(args, "pix_fmt", ""):
        cmd += ["--pix-fmt", str(args.pix_fmt)]
    if getattr(args, "no_color_tags", False):
        cmd += ["--no-color-tags"]
    try:
        r = run_tree(cmd, timeout=args.timeout)
    except Exception as exc:  # noqa: BLE001
        return 1, {"ok": False, "error": "KILN_CLI_FAILED", "detail": str(exc),
                   "hint": "改用 scripts/export_fallback.py(仅 PNG)"}, {}
    if r.timed_out:
        # 逐帧动画重页面本来就可能跑很久,超时多半是**真慢**而不是挂死;
        # 先提示调 --timeout,再怀疑引擎(台账见 docs/upstream-issues.md)。
        return 1, {"ok": False, "error": "KILN_CLI_TIMEOUT",
                   "detail": f"超过 {args.timeout:.0f}s 未返回,已强杀进程树",
                   "seconds": round(r.seconds, 1),
                   "stderr_tail": r.stderr.strip().splitlines()[-1][:200] if r.stderr.strip() else "",
                   "hint": f"确认引擎慢而非挂死后提高 --timeout(如 {args.timeout * 2:.0f});"
                           "或减小 --max-wait(动画时长)/--fps。静态单帧若也超时,"
                           "查 docs/upstream-issues.md 已登记的已知缺陷"}, {}
    # Kiln stderr 的布局告警要在失败判定前解析(存到模块级供 main 读取)
    global kiln_layout_notes
    kiln_layout_notes = []
    # 两条子路线告警前缀不同:自研布局 vb_layout:、DOM 路线 domwarn
    # (只认前者会让 DOM 路线的降级被静默吞掉)
    for line in r.stderr.splitlines():
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
    # 解析 stdout 单行 JSON(Kiln 契约;width/height/frames 只能从这条取)
    # _proc.Result 的 stdout/stderr 已是 str,不要再 decode
    engine_out: dict = {}
    for line in reversed(r.stdout.splitlines()):
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
        # 130 = 用户在 stdin 敲 c 协作取消(Kiln ≥0.14.0),不是故障
        cancelled = r.returncode == 130
        return 1, {"ok": False, "cancelled": cancelled,
                   "error": "KILN_CANCELLED" if cancelled else "KILN_CLI_FAILED",
                   "detail": f"rc={r.returncode}",
                   "stderr": r.stderr[:400],
                   "hint": "导出被协作取消,未留半截产物;重跑即可"
                           if cancelled else
                           "改用 scripts/export_fallback.py(仅 PNG)"}, engine_out
    if not os.path.isfile(args.output):
        return 1, {"ok": False, "error": "KILN_CLI_NO_OUTPUT", "detail": args.output,
                   "hint": "CLI 退出 0 但没产出文件;改用 scripts/export_fallback.py(仅 PNG)"}, engine_out
    return 0, {}, engine_out


def run_playwright_fallback(args) -> tuple[int, dict]:
    """调 export_fallback.py 重出同一路径(浏览器车道降级时的自动兜底)。

    返回 (退出码, 失败时的 error dict / 成功时的结果 dict)。
    """
    script = os.path.join(_SCRIPTS, "export_fallback.py")
    if not os.path.isfile(script):
        return 1, {"ok": False, "error": "FALLBACK_MISSING", "detail": script}
    cmd = [sys.executable, script, "--source", args.source, "--output", args.output,
           "--scale", str(args.scale if args.scale in (1, 2, 4) else 2)]
    if args.width > 0:
        cmd += ["--width", str(args.width)]
    if args.height > 0:
        cmd += ["--height", str(args.height)]
    if args.transparent:
        cmd += ["--transparent"]
    # 同样走 _proc:export_fallback.py 会拉起 Playwright 浏览器(孙进程继承
    # 管道),`subprocess.run(timeout=)` 在 Windows 上形同虚设 —— 这正是
    # _proc.py 存在的理由,兜底车道没理由豁免。
    try:
        r = run_tree(cmd, timeout=args.timeout)
    except Exception as exc:  # noqa: BLE001
        return 1, {"ok": False, "error": "FALLBACK_FAILED", "detail": str(exc)}
    if r.timed_out:
        return 1, {"ok": False, "error": "FALLBACK_TIMEOUT",
                   "detail": f"超过 {args.timeout:.0f}s 未返回,已强杀进程树",
                   "seconds": round(r.seconds, 1)}
    for line in reversed(r.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("ok"):
                return 0, obj
            return 1, obj if isinstance(obj, dict) else {}
    return 1, {"ok": False, "error": "FALLBACK_NO_JSON", "detail": r.stderr[:300]}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    p = argparse.ArgumentParser(description="artboard → Kiln 导出")
    p.add_argument("--source", required=True, help="项目目录 / HTML 文件")
    p.add_argument("--output", required=True)
    p.add_argument("--format", default="PNG",
                   choices=["PNG", "JPG", "GIF", "MP4", "PDF", "SVG", "EPS", "AI", "PPTX"])
    p.add_argument("--width", type=int, default=0,
                   help="采集视口宽(CSS px);0 = Kiln 按画板几何自适应。"
                        "非 1080 画幅必须显式传,否则按 1080 视口渲染")
    p.add_argument("--scale", type=int, default=1, choices=[1, 2, 4, 8])
    p.add_argument("--height", type=int, default=0,
                   help="采集视口高(CSS px);0 = 自适应;动画卡 100vh 型必须显式锁定")
    p.add_argument("--fps", type=int, default=25)
    p.add_argument("--gop", type=int, default=0,
                   help="MP4 关键帧间隔;0 = 不下发(编码器默认)。"
                        "要能直接粘进微信/播客编辑器时配 --gop 25 --bf 0")
    p.add_argument("--bf", type=int, default=None,
                   help="MP4 B 帧数。**--bf 0 是显式意图**(关 B 帧,让开头 DTS 不为负,"
                        "避免部分播放器首帧黑);不传 = 编码器默认")
    p.add_argument("--pix-fmt", dest="pix_fmt", default="",
                   help="MP4 像素格式(如 yuv420p / yuv422p);空 = 不下发。"
                        "yuv420p 要求偶数画布,奇数尺寸会直接报错")
    p.add_argument("--no-color-tags", dest="no_color_tags", action="store_true",
                   help="不写色彩标签(关掉 ≠ 写 unknown);色程压缩仍保留。"
                        "仅当目标播放器对 bt709 标签处理异常时才用")
    p.add_argument("--transparent", action="store_true")
    p.add_argument("--cmyk", action="store_true",
                   help="打印交付:追加导出 CMYK PDF + TIFF(印刷流程见 print-cmyk.md)")
    p.add_argument("--max-wait", type=float, default=15.0, dest="max_wait",
                   help="GIF/MP4 时作为动画总时长(秒)透传给 Kiln --duration,其余格式忽略。"
                        "注意这不是引擎的等待预算 —— 那是 --max-wait-budget")
    p.add_argument("--max-wait-budget", type=float, default=0.0, dest="max_wait_budget",
                   help="浏览器车道 settle/截图的总预算(秒,Kiln --max-wait)。"
                        "0 = 不下发,用引擎各阶段默认上限(推荐);"
                        "给了会把所有阶段一起收口,重页面与逐帧动画会中途耗尽")
    p.add_argument("--timeout", type=float, default=900.0,
                   help="整棵进程树(含浏览器)的墙钟上限(秒);超时强杀并报 "
                        "KILN_CLI_TIMEOUT。逐帧动画跑不动的常见解法是调大它")
    p.add_argument("--no-auto-fallback", action="store_true", dest="no_auto_fallback",
                   help="Kiln 浏览器车道不可用(engine_fallback)时,不自动改走 "
                        "export_fallback.py(PNG/JPG 默认自动兜底)")
    args = p.parse_args()

    kiln = find_kiln()
    if not kiln:
        # 区分「没装」与「装了但版本太老」—— 后者过去会静默挑一个参数面
        # 滞后的旧 CLI,然后报一句无法定位的 KILN_CLI_FAILED。
        stale = [c for c in _candidates() if not _supports(c, NEED_FLAGS)]
        if stale:
            missing = [f for f in NEED_FLAGS
                       if not all(f.encode() in _export_help(c) for c in stale)]
            emit({"ok": False, "error": "KILN_TOO_OLD", "detail": stale,
                  "missing_flags": missing,
                  "hint": "已找到 Kiln 但参数面过旧(缺 " + " ".join(missing) + ")。"
                          "跑 scripts/setup_kiln.py --force 升级,"
                          "或把 config.json 的 kiln_cli_exe 指向新版"})
        else:
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

    warnings: list[str] = []
    # 浏览器车道失败 → Kiln 降级自研引擎,结果带 engine_fallback:true。
    # 自研引擎对真实海报页是废图(丢照片/遮罩/绝对定位,只剩系统字体堆叠),
    # 光栅格式直接改走 Playwright 兜底重出;其余格式至少把降级讲清楚。
    if engine_out.get("engine_fallback"):
        if args.format.upper() in ("PNG", "JPG") and not args.no_auto_fallback:
            fb_rc, fb = run_playwright_fallback(args)
            if fb_rc == 0:
                emit({"ok": True, "format": args.format,
                      "path": os.path.abspath(args.output),
                      "engine": fb.get("engine") or "fallback",
                      "auto_fallback_from": "kiln-native",
                      "warnings": ["Kiln 浏览器车道不可用(engine_fallback=true),"
                                   "自研引擎输出不可信 → 已自动改用 export_fallback.py"]})
                return 0
            emit({"ok": False, "error": "KILN_DEGRADED_AND_FALLBACK_FAILED",
                  "detail": fb.get("detail") or fb.get("error") or str(fb_rc),
                  "hint": "设 VB_BROWSER_PATH 指向 Chrome/Edge;或 pip install playwright;"
                          "或人工核对 Kiln 自研引擎输出后再交付"})
            return 1
        warnings.append("Kiln 浏览器车道不可用,已降级自研引擎(engine_fallback=true);"
                        "该输出可能丢失照片/渐变/绝对定位,交付前必须人工核对")

    result = {"path": os.path.abspath(args.output), "format": args.format,
              "engine": str(engine_out.get("engine") or "kiln")}
    # 引擎自报字段回填:width/height/frames 来自引擎单行 JSON。
    # warnings 例外 —— 引擎侧是**计数**(int),直接回填会污染下方的字符串
    # 列表拼接(`2 + [...]` 抛 TypeError);改在下方转成一条可读告警。
    for k in FIELDS:
        if k == "warnings":
            continue
        if engine_out.get(k) is not None:
            result[k] = engine_out[k]
    if engine_out.get("vector"):
        result["vector"] = engine_out["vector"]
    eng_warn = engine_out.get("warnings")
    if isinstance(eng_warn, int) and eng_warn > 0:
        warnings.append(f"Kiln 引擎自报 {eng_warn} 条告警(细节见引擎 stderr)")

    # 布局告警透传:画板尺寸被内容回填/裁剪/grid 降级时,调用方必须可见
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

    payload = {k: result.get(k) for k in FIELDS
               if k != "warnings" and result.get(k) is not None}
    payload["ok"] = True
    payload["engine"] = result.get("engine", "kiln")
    # 引擎自报的降级标志优先于 stderr 文本推断(另一半在上面的双前缀解析)
    if engine_out.get("degraded_artboard") or engine_out.get("degraded"):
        payload["degraded_artboard"] = True
    if result.get("degraded_artboard"):
        payload["degraded_artboard"] = True
    if warnings:
        payload["warnings"] = warnings
    emit(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
