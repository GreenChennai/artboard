"""配方引擎:recipe.json 解析 / 校验(未知 op·参数·乱序·缺依赖)/ 单图重放 / 目录批量。

配方阶段序沿用 image-language.md §七(不许乱序):
  orient(1) → geometry(2) → cutout(3) → adjust(4) → layer(5) → output(6)
"""

from __future__ import annotations

import glob
import json
import os
import re

from _px_core import load_image, save_image

# op → (阶段, 依赖要求, 实现模块的函数名前缀).阶段用于乱序校验;依赖用于降级纪律。
def _stage_of(op: str) -> int:
    if op in ("auto-orient", "exif-fix"):
        return 1
    if op in ("resize", "fit", "crop", "pad", "rotate", "trim"):     # 几何收口走 imageops
        return 2
    if op in ("cutout",):
        return 3
    if op in _ADJUST_OPS or op in _FILTER_OPS:
        return 4
    if op in ("blend", "layer-stack", "fill", "stroke", "drop-shadow", "vignette", "glow"):
        return 5
    if op in ("compress", "convert"):
        return 6
    return 4


try:
    import _px_adjust as ADJ
    import _px_filter as FLT
    _ADJUST_OPS = {k: v for k, v in vars(ADJ).items()
                   if callable(v) and not k.startswith("_")
                   and k in ("levels", "curves", "brightness_contrast", "exposure", "vibrance",
                             "hsl", "color_balance", "black_white", "channel_mixer",
                             "photo_filter", "gradient_map", "selective_color",
                             "shadows_highlights", "posterize", "threshold", "invert",
                             "desaturate", "match_color")}
    _FILTER_OPS = {k: v for k, v in vars(FLT).items()
                   if callable(v) and not k.startswith("_")
                   and k in ("blur_gaussian", "blur_motion", "blur_radial", "sharpen_usm",
                             "sharpen_highpass", "noise_reduce", "add_noise", "emboss",
                             "find_edges", "glow", "vignette", "oil_paint")}
except ImportError:  # pragma: no cover
    raise

OP_ALIASES = {"brightness-contrast": "brightness_contrast", "auto-orient": "exif_fix",
              "range": "range_sel", "hsl": "hsl"}


def registry() -> dict:
    """op 名 → {fn, stage, deps, kind}(pixel.py CLI 与 recipe validate 共用)。"""
    reg: dict = {}
    for k, v in _ADJUST_OPS.items():
        reg[k.replace("_", "-")] = {"fn": v, "stage": 4, "deps": [], "kind": "adjust"}
    for k, v in _FILTER_OPS.items():
        deps = [] if k in ("blur_gaussian", "sharpen_usm", "sharpen_highpass", "add_noise",
                           "emboss", "find_edges", "glow", "vignette") else (["cv2"] if k != "oil_paint" else ["cv2-contrib"])
        reg[k.replace("_", "-")] = {"fn": v, "stage": 4, "deps": deps, "kind": "filter"}
    reg["auto-orient"] = {"fn": None, "stage": 1, "deps": [], "kind": "builtin"}
    reg["blend"] = {"fn": "blend", "stage": 5, "deps": [], "kind": "layer"}
    reg["fill"] = {"fn": "fill", "stage": 5, "deps": [], "kind": "layer"}
    reg["stroke"] = {"fn": "stroke", "stage": 5, "deps": [], "kind": "layer"}
    reg["drop-shadow"] = {"fn": "drop_shadow", "stage": 5, "deps": [], "kind": "layer"}
    reg["layer-stack"] = {"fn": "layer_stack", "stage": 5, "deps": [], "kind": "layer"}
    return reg


def validate(recipe: dict, allow_degrade: bool = False) -> dict:
    """校验配方;返回 {ok, errors[], degraded[]}。乱序/未知 op/缺依赖都在这里拦。"""
    errors: list[str] = []
    degraded: list[str] = []
    if not isinstance(recipe.get("stages"), list) or not recipe.get("stages"):
        return {"ok": False, "errors": ["stages 必须为非空数组"], "degraded": []}
    reg = registry()
    last_stage = 0
    for i, st in enumerate(recipe["stages"]):
        op = st.get("op", "")
        if op not in reg:
            errors.append(f"stages[{i}] 未知 op:{op}(可用 {sorted(reg)})")
            continue
        stage = reg[op]["stage"]
        if stage < last_stage:
            errors.append(f"stages[{i}] {op} 乱序:阶段 {stage} 出现在阶段 {last_stage} 之后"
                          f"(处理链固定序:方向→几何→抠图→色调→合成→输出,见 image-language.md §七)")
        last_stage = max(last_stage, stage)
        missing = []
        for d in reg[op]["deps"]:
            if d == "cv2" and not getattr(__import__("_px_filter"), "HAS_CV2", False):
                missing.append("opencv-python(cv2)")
            if d == "cv2-contrib" and not hasattr(__import__("cv2", fromlist=["xphoto"]) if _has_cv2() else object(), "xphoto"):
                missing.append("opencv-contrib-python(cv2.xphoto)")
        if missing and not allow_degrade:
            errors.append(f"stages[{i}] {op} 缺依赖:{', '.join(missing)}"
                          f"(pixel.py deps 看能力矩阵;确认降级用 --allow-degrade)")
        elif missing:
            degraded.append(f"stages[{i}] {op}:{'、'.join(missing)}")
        if op == "curves":
            pts = st.get("points")
            if not pts or any(p2[0] <= p1[0] for p1, p2 in zip(pts, pts[1:])):
                errors.append(f"stages[{i}] curves.points x 必须严格递增")
    return {"ok": not errors, "errors": errors, "degraded": degraded}


def _has_cv2() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


def run_recipe(recipe: dict, in_path: str, out_path: str,
               allow_degrade: bool = False) -> dict:
    """重放配方到单图。返回 {ok, out, degraded[], errors[]}。"""
    import _px_core as core
    v = validate(recipe, allow_degrade)
    if not v["ok"]:
        return {"ok": False, "errors": v["errors"], "degraded": v["degraded"]}
    arr = load_image(in_path)
    h, w = arr.shape[:2]
    reg = registry()
    for i, st in enumerate(recipe["stages"]):
        op = st.get("op", "")
        meta = reg.get(op)
        if meta is None:
            return {"ok": False, "errors": [f"stages[{i}] 未知 op {op}"], "degraded": []}
        params = {k: val for k, val in st.items() if k not in ("op", "mask")}
        mask = core.build_mask(st["mask"], (h, w), arr) if st.get("mask") else None
        if op == "auto-orient":
            continue  # load_image 已做 exif 旋正
        if meta["kind"] == "layer":
            if op == "layer-stack":
                arr = _px_layer_call("layer_stack", arr, layers=st.get("layers"),
                                     workdir=os.path.dirname(os.path.abspath(in_path)))
            elif op == "blend":
                top = st.get("top") or ""
                t = load_image(top if os.path.isabs(top) else os.path.join(
                    os.path.dirname(os.path.abspath(in_path)), top)) if top else None
                if t is None:
                    return {"ok": False, "errors": [f"stages[{i}] blend 需要 top=<图层路径>"],
                            "degraded": []}
                m = core.build_mask(st["mask"], (h, w), t) if st.get("mask") else None
                import _px_layer as L
                arr = L.blend(core.to_rgb(arr), core.to_rgb(t),
                              mode=st.get("mode", "normal"),
                              opacity=float(st.get("opacity", 1.0)), mask=m)
            elif op == "fill":
                import _px_layer as L
                canvas = L.fill(w, h, color=st.get("color"),
                                gradient=st.get("gradient"),
                                direction=st.get("direction", "v"))
                m = core.build_mask(st["mask"], (h, w), arr) if st.get("mask") else \
                    core.build_mask("luminosity-inv", (h, w), arr)
                arr = arr * (1 - m[..., None]) + canvas * m[..., None] if st.get("mask") else canvas
            else:
                arr = _px_layer_call(meta["fn"], arr, **params)
            continue
        out = meta["fn"](arr, **params)          # 调整/滤镜:可能因缺依赖 RuntimeError
        arr = core.apply_mask(arr, out, mask) if mask is not None else out
    save_image(arr, out_path, fmt=recipe.get("output", {}).get("format"))
    return {"ok": True, "out": out_path, "errors": [], "degraded": v["degraded"]}


def _px_layer_call(fn_name: str, arr, **params):
    import _px_layer as L
    return getattr(L, fn_name)(arr, **params)


def batch(recipe: dict, in_dir: str, out_dir: str, rename: str = "{name}_px",
          allow_degrade: bool = False) -> dict:
    files = sorted(glob.glob(os.path.join(in_dir, "*.jpg")) + glob.glob(os.path.join(in_dir, "*.png"))
                   + glob.glob(os.path.join(in_dir, "*.jpeg")) + glob.glob(os.path.join(in_dir, "*.webp")))
    results = []
    for i, f in enumerate(files, 1):
        name = re.sub(r"\.[^.]+$", "", os.path.basename(f))
        out = os.path.join(out_dir, rename.format(name=name, i=i) + ".png")
        r = run_recipe(recipe, f, out, allow_degrade)
        r["in"] = f
        results.append(r)
    return {"ok": all(r["ok"] for r in results) if results else False,
            "count": len(results), "results": results}
