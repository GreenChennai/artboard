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

    # blend 快捷形态(top 独立参数);--in/--top/-o 非 required:--list-modes 要免这三者,
    # 缺参由 run_op 吐 USAGE JSON(而不是 argparse 富文本)
    g = sub.add_parser("blend", help="图层 · 混合模式(25 种,见 --list-modes)")
    g.add_argument("--in", dest="inp", required=False, default=None)
    g.add_argument("--top", required=False, default=None, help="上层图片(与 --in 尺寸不同则自动缩放)")
    g.add_argument("--mode", default="normal")
    g.add_argument("--opacity", type=float, default=1.0)
    g.add_argument("--mask", default="")
    g.add_argument("-o", "--out", required=False, default=None)
    g.add_argument("--list-modes", dest="list_modes", action="store_true",
                   help="列出全部混合模式键名(单行 JSON;此用法无需 --in/--top/-o)")

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


def _resize_top(top, w: int, h: int):
    """上层与下层尺寸不同 → 缩放到 (w, h),**返回 numpy 数组**(下游全是 ndarray 运算)。

    旧实现把 top 换成 PIL Image 对象,下游 `core.to_rgb(top)` 立刻
    `AttributeError: 'Image' object has no attribute 'ndim'`;`t if t.mode != "RGBA"
    else None or top` 两条分支都不对(非 RGBA → 传 PIL 对象;RGBA → 压根没缩)。
    带 alpha 时连 alpha 一起缩,保持与"等尺寸"路径一致的通道数(--mask alpha 才有意义)。
    """
    import numpy as np
    from PIL import Image
    mode = "RGBA" if top.ndim == 3 and top.shape[2] == 4 else "RGB"
    im = Image.fromarray((np.clip(top, 0, 1) * 255).astype("uint8"), mode).resize((w, h))
    return np.asarray(im, dtype=np.float32) / 255.0


def _load_recipe(path: str, cmd: str):
    """读配方 JSON → `(recipe, None)`,失败 → `(None, 退出码)`。

    失败统一走 core.fail 的失败信封(末行必为合法 JSON;此前三条 recipe 路径都裸
    FileNotFoundError/JSONDecodeError traceback):文件不存在 → RECIPE_NOT_FOUND,
    坏 JSON / 顶层非对象 → BAD_RECIPE。
    """
    try:
        with open(path, encoding="utf-8") as f:
            recipe = json.load(f)
    except FileNotFoundError:
        return None, core.fail(cmd, "RECIPE_NOT_FOUND", path,
                               hint="检查配方路径;模板可 `recipe save --out x.json`")
    except IsADirectoryError:
        return None, core.fail(cmd, "RECIPE_NOT_FOUND", f"{path} 是目录,不是配方文件",
                               hint="recipe 后面跟 .json 文件路径")
    except (ValueError, OSError) as exc:  # JSONDecodeError ⊂ ValueError
        return None, core.fail(cmd, "BAD_RECIPE", f"{path}: {exc}",
                               hint="配方须是合法 JSON;改完先 recipe validate")
    if not isinstance(recipe, dict):
        return None, core.fail(cmd, "BAD_RECIPE",
                               f"{path}: 顶层须是 JSON 对象,收到 {type(recipe).__name__}",
                               hint='形如 {"version":1,"stages":[...]}')
    return recipe, None


def run_op(args) -> int:
    if args.cmd == "blend" and not (args.inp and args.top and args.out):
        return core.fail("blend", "USAGE", "blend 需要 --in/--top/-o(仅 --list-modes 免)",
                         hint="python pixel.py blend --in base.png --top glow.png "
                              "--mode screen -o out.png")
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
            top = _resize_top(top, w, h)
        try:
            m = core.build_mask(args.mask, (h, w), top) if args.mask else None
        except ValueError as exc:
            return core.fail("blend", "USAGE", f"蒙版无效:{exc}",
                             hint="蒙版语法见 pixel.py --help 的 --mask 说明")
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
    try:
        params = json.loads(getattr(args, "params", "{}") or "{}")
    except ValueError as exc:  # JSONDecodeError ⊂ ValueError
        return core.fail(args.cmd, "USAGE", f"--params 不是合法 JSON:{exc}",
                         hint='形如 --params \'{"amount":0.6}\'')
    if not isinstance(params, dict):
        return core.fail(args.cmd, "USAGE",
                         f"--params 须是 JSON 对象,收到 {type(params).__name__}",
                         hint='形如 --params \'{"amount":0.6}\'')
    try:
        mask = core.build_mask(args.mask, arr.shape[:2], arr) if getattr(args, "mask", "") else None
    except ValueError as exc:
        return core.fail(args.cmd, "USAGE", f"蒙版无效:{exc}",
                         hint="蒙版语法见 pixel.py --help 的 --mask 说明")
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
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
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
            recipe, err = _load_recipe(n.recipe, "recipe validate")
            if err is not None:
                return err
            v = R.validate(recipe, n.allow_degrade)
            core.emit({"ok": v["ok"], "cmd": "recipe validate", "recipe": n.recipe,
                       "errors": v["errors"], "degraded": v["degraded"]})
            return core.EXIT_OK if v["ok"] else core.EXIT_FAIL
        if rcmd == "run":
            a.add_argument("recipe"); a.add_argument("--in", dest="inp", required=True)
            a.add_argument("-o", "--out", required=True)
            a.add_argument("--allow-degrade", action="store_true")
            n = a.parse_args(rest[1:])
            recipe, err = _load_recipe(n.recipe, "recipe run")
            if err is not None:
                return err
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
            recipe, err = _load_recipe(n.recipe, "recipe batch")
            if err is not None:
                return err
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
    if getattr(args, "list_modes", False):  # 最先处理:此用法不需要 --in/--top/-o
        core.emit({"ok": True, "cmd": "blend", "count": len(LAYER.BLEND_MODES),
                   "modes": sorted(LAYER.BLEND_MODES), "degraded": []})
        return core.EXIT_OK
    args._arr = None
    return run_op(args)


if __name__ == "__main__":
    sys.exit(main())
