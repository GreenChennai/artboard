"""artboard 位图配方引擎(pixel):声明式配方 + PS 对照的调整/滤镜/图层能力。

与 imageops 的分工(ADR-AB-E10):imageops = **工序**(裁/缩/压/转/水印/切片/体检,
"点哪条命令");pixel = **配方**(调整/滤镜/图层栈/混合/蒙版,"怎么调")。
调用关系:pixel.py(像素加工)→ imageops.py(编码/规格收口)→ 进项目。

用法:
  python pixel.py levels --in a.jpg -o b.png --black 0.04 --gamma 1.05 --white 0.96 --mask luminosity
  python pixel.py sharpen-usm --in a.jpg -o b.png --amount 0.6
  python pixel.py blend --in base.jpg --top glow.png --mode screen --opacity 0.8 -o out.png
  python pixel.py recipe validate my.json
  python pixel.py recipe run my.json --in a.jpg -o b.png [--allow-degrade]
  python pixel.py recipe batch my.json --in-dir imgs/ --out-dir out/ --rename "{name}_v2"
  python pixel.py deps                              # 能力矩阵(Pillow/cv2/pyvips)

契约:stdout 单行 JSON(ok/error/hint/degraded[]);退出码 0/1/2/3。
**不做**(提示即拒):AI 生成式填充(content-aware fill)、人像液化、超分模型(属 MomentShift)、
WebGL 图像编辑——这是本引擎的边界,不是缺陷。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _px_core as core  # noqa: E402
import _px_layer as LAYER  # noqa: E402
import _px_recipe as R  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    class JsonParser(argparse.ArgumentParser):
        def error(self, message):
            core.emit({"ok": False, "cmd": "pixel", "error": "USAGE", "detail": message,
                       "hint": "pixel.py --help;recipe/deps 子命令见模块 docstring"})
            raise SystemExit(core.EXIT_USAGE)

    ap = JsonParser(prog="pixel", description="位图配方引擎(PS 对照;分册 references/pixel-pipeline.md)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    reg = R.registry()

    def common(g, has_mask=True):
        g.add_argument("--in", dest="inp", required=True, help="输入图片")
        g.add_argument("-o", "--out", required=True, help="输出图片(png/jpg)")
        if has_mask:
            g.add_argument("--mask", default="", help="蒙版:luminosity/luminosity-inv/alpha/"
                                                       "color:#hex,tol/shape:rect:l,t,r,b/"
                                                       "shape:circle:cx,cy,r/shape:gradient:top/灰度图路径")
        g.add_argument("--allow-degrade", action="store_true", dest="allow_degrade",
                       help="允许依赖降级(缺 cv2 时用近似;degraded[] 非空)")

    # 通用参数:每个 op 一个子命令;参数从 docstring 级 registry 反推太重 → 透传 **extra
    for name, meta in sorted(reg.items()):
        if meta["kind"] == "builtin" or name == "blend":  # blend 有专用形态(下方)
            continue
        g = sub.add_parser(name, help=f"{meta['kind']} · 阶段{meta['stage']}"
                                      + (f"(依赖 {meta['deps']})" if meta["deps"] else ""))
        g.add_argument("--in", dest="inp", required=True)
        g.add_argument("-o", "--out", required=True)
        g.add_argument("--mask", default="")
        g.add_argument("--allow-degrade", action="store_true", dest="allow_degrade")
        g.add_argument("--params", default="{}", help='op 参数(JSON 对象,如 \'{"amount":0.6}\')'
                                                      ";各 op 参数区间表见 pixel-pipeline.md")
        g.set_defaults(kind=meta["kind"], fn=meta["fn"], op=name)

    # blend 快捷形态(top 独立参数)
    g = sub.add_parser("blend", help="图层 · 混合模式(25 种,见 --list-modes)")
    g.add_argument("--in", dest="inp", required=True)
    g.add_argument("--top", required=True, help="上层图片")
    g.add_argument("--mode", default="normal")
    g.add_argument("--opacity", type=float, default=1.0)
    g.add_argument("--mask", default="")
    g.add_argument("-o", "--out", required=True)
    g.add_argument("--list-modes", action="store_true")

    p = sub.add_parser("recipe", help="配方:save/validate/run/batch")
    rp = p.add_subparsers(dest="rcmd", required=True)
    r1 = rp.add_parser("validate"); r1.add_argument("recipe"); r1.add_argument("--allow-degrade", action="store_true")
    r2 = rp.add_parser("run"); r2.add_argument("recipe"); r2.add_argument("--in", dest="inp", required=True)
    r2.add_argument("-o", "--out", required=True); r2.add_argument("--allow-degrade", action="store_true")
    r3 = rp.add_parser("batch"); r3.add_argument("recipe"); r3.add_argument("--in-dir", dest="in_dir", required=True)
    r3.add_argument("--out-dir", dest="out_dir", required=True)
    r3.add_argument("--rename", default="{name}_px"); r3.add_argument("--allow-degrade", action="store_true")
    r4 = rp.add_parser("save"); r4.add_argument("--out", required=True)

    d = sub.add_parser("deps", help="能力矩阵(Pillow/cv2/pyvips + 逐 op 依赖)")

    ap.list_modes = None
    return ap


def _mask_or_none(args):
    arr_loaded = args._arr
    if getattr(args, "mask", ""):
        h, w = arr_loaded.shape[:2]
        return core.build_mask(args.mask, (h, w), arr_loaded)
    return None


def run_op(args) -> int:
    try:
        arr = core.load_image(args.inp)
    except FileNotFoundError:
        return core.fail(args.cmd, "INPUT_NOT_FOUND", args.inp, hint="检查 --in 路径")
    if args.cmd == "blend":
        try:
            top = core.load_image(args.top)
        except FileNotFoundError:
            return core.fail("blend", "INPUT_NOT_FOUND", args.top)
        h, w = arr.shape[:2]
        if top.shape[:2] != (h, w):
            from PIL import Image
            t = Image.fromarray((core.to_rgb(top) * 255).astype("uint8")).resize((w, h))
            top = t if t.mode != "RGBA" else None or top
        m = core.build_mask(args.mask, (h, w), top) if args.mask else None
        try:
            out = LAYER.blend(core.to_rgb(arr), core.to_rgb(top), mode=args.mode,
                              opacity=args.opacity, mask=m)
        except ValueError as exc:
            return core.fail("blend", "USAGE", str(exc))
        core.save_image(out, args.out)
        core.emit({"ok": True, "cmd": "blend", "mode": args.mode, "out": args.out,
                   "modes_available": sorted(LAYER.BLEND_MODES), "degraded": []})
        return core.EXIT_OK

    fn = args.fn
    if not callable(fn):  # 图层类:registry 存的是 _px_layer 的函数名
        fn = getattr(LAYER, fn)
    params = json.loads(getattr(args, "params", "{}") or "{}")
    mask = core.build_mask(args.mask, arr.shape[:2], arr) if getattr(args, "mask", "") else None
    try:
        out = fn(arr, **params)
    except TypeError as exc:
        return core.fail(args.cmd, "USAGE", f"参数不对:{exc}",
                         hint=f"参数区间表见 references/pixel-pipeline.md;--params '<json>'")
    except RuntimeError as exc:
        return core.fail(args.cmd, "NO_DEP", str(exc), hint="pip install opencv-contrib-python")
    except ValueError as exc:
        return core.fail(args.cmd, "USAGE", str(exc))
    if mask is not None:
        out = core.apply_mask(arr, out, mask)
    core.save_image(out, args.out)
    core.emit({"ok": True, "cmd": args.cmd, "out": args.out, "degraded": []})
    return core.EXIT_OK


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        core.emit({"ok": False, "cmd": "pixel", "error": "USAGE",
                   "hint": "pixel.py <op> --in x.jpg -o y.png [--params '{}'] [--mask …];"
                           "recipe / deps 子命令见 --help"})
        return core.EXIT_USAGE

    # 轻解析:先取 cmd 定分支(避免 argparse 对未知 op 参数报错太早)
    ap = build_parser()
    if argv[0] == "deps":
        import _px_filter as FLT
        try:
            import pyvips  # noqa: F401
            vips = True
        except Exception:  # noqa: BLE001
            vips = False
        contrib = FLT.HAS_CV2 and hasattr(FLT.cv2, "xphoto") and hasattr(FLT.cv2.xphoto, "oilPainting")
        matrix = {
            "pillow": True, "numpy": True,
            "opencv(cv2)": FLT.HAS_CV2,
            "opencv-contrib(xphoto)": bool(contrib),
            "pyvips": vips,
        }
        notes = []
        for name, meta in sorted(R.registry().items()):
            if meta["deps"]:
                notes.append({"op": name, "requires": meta["deps"]})
        core.emit({"ok": True, "cmd": "deps", "matrix": matrix,
                   "ops_with_deps": notes,
                   "hint": "缺依赖的 op 默认报错不静默;--allow-degrade 才降级且 degraded[] 非空"})
        return core.EXIT_OK
    if argv[0] == "recipe":
        rest = argv[1:]
        if not rest:
            core.emit({"ok": False, "cmd": "recipe", "error": "USAGE",
                       "hint": "recipe validate|run|batch|save"})
            return core.EXIT_USAGE
        rcmd = rest[0]
        a = argparse.ArgumentParser(prog="pixel recipe")
        if rcmd == "validate":
            a.add_argument("recipe"); a.add_argument("--allow-degrade", action="store_true")
            n = a.parse_args(rest[1:])
            recipe = json.loads(open(n.recipe, encoding="utf-8").read())
            v = R.validate(recipe, n.allow_degrade)
            core.emit({"ok": v["ok"], "cmd": "recipe validate", "recipe": n.recipe,
                       "errors": v["errors"], "degraded": v["degraded"]})
            return core.EXIT_OK if v["ok"] else core.EXIT_FAIL
        if rcmd == "run":
            a.add_argument("recipe"); a.add_argument("--in", dest="inp", required=True)
            a.add_argument("-o", "--out", required=True)
            a.add_argument("--allow-degrade", action="store_true")
            n = a.parse_args(rest[1:])
            recipe = json.loads(open(n.recipe, encoding="utf-8").read())
            r = R.run_recipe(recipe, n.inp, n.out, n.allow_degrade)
            core.emit({"ok": r["ok"], "cmd": "recipe run", "out": r.get("out"),
                       "errors": r["errors"], "degraded": r["degraded"]})
            return core.EXIT_OK if r["ok"] else core.EXIT_FAIL
        if rcmd == "batch":
            a.add_argument("recipe"); a.add_argument("--in-dir", dest="in_dir", required=True)
            a.add_argument("--out-dir", dest="out_dir", required=True)
            a.add_argument("--rename", default="{name}_px")
            a.add_argument("--allow-degrade", action="store_true")
            n = a.parse_args(rest[1:])
            recipe = json.loads(open(n.recipe, encoding="utf-8").read())
            r = R.batch(recipe, n.in_dir, n.out_dir, n.rename, n.allow_degrade)
            core.emit({"ok": r["ok"], "cmd": "recipe batch", "count": r["count"],
                       "results": r["results"], "degraded": []})
            return core.EXIT_OK if r["ok"] else core.EXIT_FAIL
        if rcmd == "save":
            a.add_argument("--out", required=True)
            n = a.parse_args(rest[1:])
            if os.path.isfile(n.out):
                core.emit({"ok": True, "cmd": "recipe save", "out": n.out,
                           "hint": "配方已存在(保存=落盘 recipes/*.json;此处仅确认路径可写)"})
                return core.EXIT_OK
            sample = {"version": 1, "stages": [{"op": "auto-orient"},
                                               {"op": "levels", "black": 0.04, "gamma": 1.05, "white": 0.96}],
                      "output": {"format": "png"}}
            with open(n.out, "w", encoding="utf-8") as f:
                json.dump(sample, f, ensure_ascii=False, indent=2)
            core.emit({"ok": True, "cmd": "recipe save", "out": n.out,
                       "hint": "已写配方模板;编辑后先 recipe validate"})
            return core.EXIT_OK
        core.emit({"ok": False, "cmd": "recipe", "error": "USAGE",
                   "hint": "recipe validate|run|batch|save"})
        return core.EXIT_USAGE

    args = ap.parse_args(argv)
    args._arr = None
    return run_op(args)


if __name__ == "__main__":
    sys.exit(main())
