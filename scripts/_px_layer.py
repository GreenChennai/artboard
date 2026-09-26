"""P0-C 图层与合成:混合模式 25 种 / 图层栈 / 填充 / 描边 / 投影。

混合模式在 float32 [0,1] RGB 域逐像素定义(与 PS 混合模式同公式;色域为 sRGB,
**近似实现非色卡级一致**——交付验收走肉眼 + contrast-check)。
"""

from __future__ import annotations

import os

import numpy as np

from _px_core import hex_to_rgb, luma, to_rgb


def _lum(c):
    return 0.3 * c[..., 0] + 0.59 * c[..., 1] + 0.11 * c[..., 2]


def _clip_color(c):
    l = _lum(c)[..., None]
    mn = c.min(-1)[..., None]
    mx = c.max(-1)[..., None]
    out = c.copy()
    lo = l - mn / 1e-6
    out = np.where(mn < 0, l + (c - l) * l / (l - mn + 1e-6), c)
    hi = mx - l
    out = np.where(mx > 1, l + (out - l) * (1 - l) / (hi + 1e-6), out)
    return np.clip(out, 0, 1)


def _set_lum(c, l):
    d = l - _lum(c)
    return _clip_color(c + d[..., None])


def _sat(c):
    return c.max(-1) - c.min(-1)


def _set_sat(c, s):
    order = np.argsort(c, axis=-1)
    mn = np.take_along_axis(c, order[..., :1], -1)
    md = np.take_along_axis(c, order[..., 1:2], -1)
    mx = np.take_along_axis(c, order[..., 2:], -1)
    md_new = np.where(mx > mn, (md - mn) * s / (mx - mn + 1e-6), 0) + mn
    out_sorted = np.concatenate([mn, md_new, mn + s], -1)
    out = np.zeros_like(c)
    np.put_along_axis(out, order, out_sorted, -1)
    return out


# ---------------- 25 种混合模式(base b, top t ∈ [0,1]) ----------------

def bm_normal(b, t, **_):
    return t


def bm_dissolve(b, t, opacity_seed=0.5, seed=7, **_):
    rng = np.random.default_rng(seed)
    keep = rng.random(b.shape[:2])[..., None] < opacity_seed
    return np.where(keep, t, b)


def bm_darken(b, t, **_):
    return np.minimum(b, t)


def bm_multiply(b, t, **_):
    return b * t


def bm_color_burn(b, t, **_):
    return np.where(t <= 0, 0, 1 - np.clip((1 - b) / (t + 1e-6), 0, 1))


def bm_linear_burn(b, t, **_):
    return np.clip(b + t - 1, 0, 1)


def bm_lighter(b, t, **_):
    return np.maximum(b, t)


def bm_screen(b, t, **_):
    return 1 - (1 - b) * (1 - t)


def bm_color_dodge(b, t, **_):
    return np.where(t >= 1, 1, np.clip(b / (1 - t + 1e-6), 0, 1))


def bm_linear_dodge(b, t, **_):
    return np.clip(b + t, 0, 1)


def bm_overlay(b, t, **_):
    return np.where(b <= 0.5, 2 * b * t, 1 - 2 * (1 - b) * (1 - t))


def bm_soft_light(b, t, **_):
    low = (2 * t - 1) * (np.sqrt(b) - b) + b  # t<0.5 分支
    high = (2 * t - 1) * ((np.sqrt(b) if False else ((16 * b - 12) * b + 4) * b - b)) + b
    return np.where(t <= 0.5, low, high)


def bm_hard_light(b, t, **_):
    return np.where(t <= 0.5, 2 * b * t, 1 - 2 * (1 - b) * (1 - t))


def bm_vivid_light(b, t, **_):
    return np.where(t <= 0.5,
                    np.clip(1 - (1 - b) / (2 * t + 1e-6), 0, 1),
                    np.clip(b / (2 * (1 - t) + 1e-6), 0, 1))


def bm_linear_light(b, t, **_):
    return np.clip(b + 2 * t - 1, 0, 1)


def bm_pin_light(b, t, **_):
    return np.where(t <= 0.5, np.minimum(b, 2 * t), np.maximum(b, 2 * t - 1))


def bm_hard_mix(b, t, **_):
    return (b + t >= 1).astype(np.float32)


def bm_difference(b, t, **_):
    return np.abs(b - t)


def bm_exclusion(b, t, **_):
    return b + t - 2 * b * t


def bm_subtract(b, t, **_):
    return np.clip(b - t, 0, 1)


def bm_divide(b, t, **_):
    return np.clip(b / (t + 1e-6), 0, 1)


def bm_hue(b, t, **_):
    return _set_lum(_set_sat(t, _sat(b)), _lum(b))


def bm_saturation(b, t, **_):
    return _set_lum(_set_sat(b, _sat(t)), _lum(b))


def bm_color(b, t, **_):
    return _set_lum(t, _lum(b))


def bm_luminosity(b, t, **_):
    return _set_lum(b, _lum(t))


BLEND_MODES = {
    "normal": bm_normal, "dissolve": bm_dissolve,
    "darken": bm_darken, "multiply": bm_multiply, "color-burn": bm_color_burn,
    "linear-burn": bm_linear_burn,
    "lighter": bm_lighter, "screen": bm_screen, "color-dodge": bm_color_dodge,
    "linear-dodge": bm_linear_dodge,
    "overlay": bm_overlay, "soft-light": bm_soft_light, "hard-light": bm_hard_light,
    "vivid-light": bm_vivid_light, "linear-light": bm_linear_light,
    "pin-light": bm_pin_light, "hard-mix": bm_hard_mix,
    "difference": bm_difference, "exclusion": bm_exclusion, "subtract": bm_subtract,
    "divide": bm_divide,
    "hue": bm_hue, "saturation": bm_saturation, "color": bm_color,
    "luminosity": bm_luminosity,
}
UNSUPPORTED = []  # PS 的「实色混合(pass-through 特例)」等已按可稳定实现取舍;此处留空


def blend(base, top, mode="normal", opacity=1.0, mask=None, **kw):
    """base/top: HxW3 float;mask: HxW(可选);opacity ∈ [0,1]。"""
    if mode not in BLEND_MODES:
        raise ValueError(f"未知混合模式 {mode!r};可用 {sorted(BLEND_MODES)}")
    mixed = BLEND_MODES[mode](base, top, **kw)
    out = base * (1 - opacity) + mixed * opacity
    if mask is not None:
        m = mask[..., None]
        out = base * (1 - m) + out * m
    return np.clip(out, 0, 1)


def fill(w, h, color=None, gradient=None, direction="v", **_):
    """纯色 / 渐变填充。gradient = [[hex,pos],...](v 上→下 / h 左→右)。"""
    if gradient:
        pos = np.asarray([s[1] for s in gradient], np.float32)
        cols = np.asarray([hex_to_rgb(s[0]) for s in gradient], np.float32)
        t = np.linspace(0, 1, h if direction == "v" else w, dtype=np.float32)
        chan = np.stack([np.interp(t, pos, cols[:, i]) for i in range(3)], -1)  # t×3
        if direction == "v":
            return np.repeat(chan[:, None, :], w, axis=1)
        return np.repeat(chan[None, :, :], h, axis=0)
    c = np.asarray(hex_to_rgb(color or "#000000"), np.float32)
    return np.full((h, w, 3), c, np.float32)


def stroke(arr, width=4, color="#ffffff", position="outside", **_):
    """描边:基于 alpha(无 alpha 用亮度边缘)。position ∈ outside/inside/center。
    outside = 膨胀-本体;inside = 本体-腐蚀;center = 膨胀-腐蚀。"""
    from PIL import Image, ImageFilter
    if arr.shape[2] == 4:
        alpha = arr[..., 3]
    else:
        alpha = np.asarray(Image.fromarray((luma(arr) * 255).astype(np.uint8))
                           .filter(ImageFilter.FIND_EDGES), np.float32) / 255
    k = max(int(width), 1)
    if k % 2 == 0:
        k += 1
    pil_a = Image.fromarray((alpha * 255).astype(np.uint8), "L")
    g = np.asarray(pil_a.filter(ImageFilter.MaxFilter(k + 2)), np.float32) / 255
    e = np.asarray(pil_a.filter(ImageFilter.MinFilter(k + 2)), np.float32) / 255
    if position == "inside":
        m = np.clip(alpha - e, 0, 1)
    elif position == "center":
        m = np.clip(g - e, 0, 1)
    else:
        m = np.clip(g - alpha, 0, 1)
    c = np.asarray(hex_to_rgb(color), np.float32)
    rgb = arr[..., :3]
    out = rgb * (1 - m[..., None]) + c * m[..., None]
    if arr.shape[2] == 4:
        out = np.dstack([out, np.maximum(arr[..., 3], m)])
    return np.clip(out, 0, 1)


def drop_shadow(arr, dx=12, dy=16, blur=24, color="#000000", opacity=0.35, **_):
    """投影:基于 alpha 的偏移模糊;合成在纯透明画布上。"""
    from PIL import Image, ImageFilter
    if arr.shape[2] != 4:
        raise ValueError("drop-shadow 需要 RGBA 输入(先 cutout 或 alpha-extract)")
    h, w = arr.shape[:2]
    a = Image.fromarray((arr[..., 3] * 255).astype(np.uint8), "L")
    pad = int(blur * 2 + max(abs(dx), abs(dy)))
    big = Image.new("L", (w + pad * 2, h + pad * 2), 0)
    big.paste(a, (pad, pad))
    sh = big.filter(ImageFilter.GaussianBlur(blur))
    sh_a = np.asarray(sh, np.float32) / 255 * opacity
    c = np.asarray(hex_to_rgb(color), np.float32)
    canvas = np.zeros((h, w, 4), np.float32)
    ys, xs = dy + pad, dx + pad
    src = sh_a[max(-ys, 0): h + pad * 2 - ys if ys + h <= sh_a.shape[0] else None,
               max(-xs, 0): w + pad * 2 - xs if xs + w <= sh_a.shape[1] else None]
    ys0, xs0 = max(ys, 0), max(xs, 0)
    hh = min(h, src.shape[0]); ww = min(w, src.shape[1])
    shadow_rgb = np.zeros((h, w, 3), np.float32)
    am = np.zeros((h, w), np.float32)
    shadow_rgb[ys0:ys0 + hh, xs0:xs0 + ww] = c
    am[ys0:ys0 + hh, xs0:xs0 + ww] = src[:hh, :ww]
    # shadow over transparent → 把主体叠回
    over = np.dstack([shadow_rgb, am])
    alpha = arr[..., 3:4]
    out_rgb = over[..., :3] * (1 - alpha) + arr[..., :3] * alpha
    out_a = np.clip(am + alpha, 0, 1)
    return np.dstack([out_rgb, out_a[..., 0]])


def layer_stack(base, layers, workdir=""):
    """图层栈:layers = [{src, mode, opacity, mask}, ...](自底向上,base 为最底层)。
    src 相对 workdir 解析;每层经 blend() 合成。"""
    from _px_core import build_mask, load_image
    out = base[..., :3]
    h, w = out.shape[:2]
    for i, lay in enumerate(layers or []):
        path = lay.get("src")
        if not path:
            raise ValueError(f"layers[{i}] 缺 src")
        top = load_image(path if os.path.isabs(path) else os.path.join(workdir, path))
        if top.shape[:2] != (h, w):
            from PIL import Image
            im = Image.fromarray((np.clip(top, 0, 1) * 255).astype(np.uint8), "RGBA")
            top = np.asarray(im.resize((w, h)), np.float32) / 255
        m = build_mask(lay["mask"], (h, w), top) if lay.get("mask") else None
        out = blend(out, to_rgb(top), mode=lay.get("mode", "normal"),
                    opacity=float(lay.get("opacity", 1.0)), mask=m)
    return out

