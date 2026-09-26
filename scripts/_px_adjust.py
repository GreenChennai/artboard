"""P0-A 调整类 18 项(对标 PS Adjustments;全 Pillow+numpy 自实现,无可选依赖)。

每个 op = fn(arr: float32 HxW(3|4), **params) -> float32 HxW3(仅 RGB;蒙版与 alpha
由 _px_core.apply_mask 在外层合成)。参数区间表见 references/pixel-pipeline.md §参数。
"""

from __future__ import annotations

import numpy as np

from _px_core import hex_to_rgb, luma, to_rgb


def _chan_lut(arr: np.ndarray, ch: int, lut: np.ndarray) -> np.ndarray:
    out = arr.copy()
    out[..., ch] = np.clip(np.interp(out[..., ch], np.linspace(0, 1, len(lut)), lut), 0, 1)
    return out


def _rgb_lut(arr: np.ndarray, lut: np.ndarray, channel: str = "rgb") -> np.ndarray:
    idx = {"r": 0, "g": 1, "b": 2}
    chans = list(idx.values()) if channel == "rgb" else [idx[channel]]
    out = arr.copy()
    for c in chans:
        out[..., c] = np.clip(np.interp(out[..., c], np.linspace(0, 1, len(lut)), lut), 0, 1)
    return out


def levels(arr, channel="rgb", black=0.0, gamma=1.0, white=1.0, **_):
    black, white = min(black, white - 1e-4), max(white, black + 1e-4)
    x = np.linspace(0, 1, 256)
    lut = ((x - black) / (white - black)).clip(0, None) ** gamma
    lut = np.clip(lut, 0, 1)
    return _rgb_lut(arr, lut.astype(np.float32), channel)


def curves(arr, points=None, **_):
    pts = sorted(points or [[0, 0], [1, 1]])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if any(b <= a for a, b in zip(xs, xs[1:])):
        raise ValueError("curves 控制点 x 必须严格递增(单调)")
    lut = np.interp(np.linspace(0, 1, 256), xs, ys).clip(0, 1)
    return _rgb_lut(arr, lut.astype(np.float32))


def brightness_contrast(arr, brightness=0.0, contrast=0.0, **_):
    out = to_rgb(arr) + brightness
    if contrast:
        c = contrast * 0.9 + 1.0 if contrast > 0 else contrast + 1.0
        out = (out - 0.5) * c + 0.5
    out = np.clip(out, 0, 1)
    if arr.ndim == 3 and arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def exposure(arr, exposure=0.0, offset=0.0, gamma_correction=1.0, **_):
    out = to_rgb(arr) * (2.0 ** exposure) + offset
    out = np.clip(out, 0, 1) ** (1.0 / gamma_correction)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def vibrance(arr, amount=0.0, **_):
    rgb = to_rgb(arr)
    mx = rgb.max(-1, keepdims=True)
    mn = rgb.min(-1, keepdims=True)
    sat = mx - mn                                   # 饱和度越低提升越多(护肤色倾向)
    boost = 1.0 + amount * (1.0 - sat)
    mean = rgb.mean(-1, keepdims=True)
    out = np.clip(mean + (rgb - mean) * boost, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def _rgb_to_hsl(rgb):
    mx = rgb.max(-1)
    mn = rgb.min(-1)
    l = (mx + mn) / 2
    d = mx - mn
    s = np.where(d == 0, 0, d / (1 - np.abs(2 * l - 1) + 1e-8))
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(l)
    m = d > 1e-8
    idx = m & (mx == r); h[idx] = ((g - b)[idx] / d[idx]) % 6
    idx = m & (mx == g); h[idx] = (b - r)[idx] / d[idx] + 2
    idx = m & (mx == b); h[idx] = (r - g)[idx] / d[idx] + 4
    return h * 60, np.clip(s, 0, 1), l


def _hsl_to_rgb(h, s, l):
    c = (1 - np.abs(2 * l - 1)) * s
    hp = (h % 360) / 60
    x = c * (1 - np.abs(hp % 2 - 1))
    z = np.zeros_like(c)
    k = hp[..., None]  # 条件与选项同维(H,W,1)
    rgb = np.select([k < 1, k < 2, k < 3, k < 4, k < 5, k < 6],
                    [np.stack([c, x, z], -1), np.stack([x, c, z], -1),
                     np.stack([z, c, x], -1), np.stack([z, x, c], -1),
                     np.stack([x, z, c], -1), np.stack([c, z, x], -1)])
    m = l - c / 2
    return np.clip(rgb + m[..., None], 0, 1)


def hsl(arr, range_sel="all", hue=0.0, sat=0.0, light=0.0, **_):
    rgb = to_rgb(arr)
    h, s, l = _rgb_to_hsl(rgb)
    if range_sel != "all":  # 分通道:R 0±45 / Y 60 / G 120 / C 180 / B 240 / M 300
        center = {"r": 0, "y": 60, "g": 120, "c": 180, "b": 240, "m": 300}[range_sel.lower()]
        dist = np.minimum(np.abs(h - center), 360 - np.abs(h - center))
        w = np.clip((45 - dist) / 22.5, 0, 1).astype(np.float32)
    else:
        w = np.ones_like(h, dtype=np.float32)
    h2 = (h + hue * w) % 360.0
    s2 = np.clip(s + sat * w * (s if sat > 0 else (1 - s)), 0, 1)
    l2 = np.clip(l + light * 0.5 * w, 0, 1)
    out = _hsl_to_rgb(h2, s2, l2)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def color_balance(arr, shadow=(0, 0, 0), mid=(0, 0, 0), high=(0, 0, 0), **_):
    rgb = to_rgb(arr)
    lum = luma(rgb)
    ws = np.clip((0.5 - lum) * 2, 0, 1)[..., None]
    wh = np.clip((lum - 0.5) * 2, 0, 1)[..., None]
    wm = 1 - ws - wh
    out = rgb + (np.asarray(shadow, np.float32) * ws + np.asarray(mid, np.float32) * wm
                 + np.asarray(high, np.float32) * wh)
    out = np.clip(out, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def black_white(arr, rw=0.30, gw=0.59, bw=0.11, cw=0.0, mw=0.0, yw=0.0, **_):
    rgb = to_rgb(arr)
    # CMY 以补色近似参与(青=1-r 等),权重可负(PS 同款允许)
    gray = (rw * rgb[..., 0] + gw * rgb[..., 1] + bw * rgb[..., 2]
            + cw * (1 - rgb[..., 0]) + mw * (1 - rgb[..., 2]) + yw * (1 - rgb[..., 1]))
    gray = np.clip(gray, 0, 1)[..., None]
    return np.repeat(gray, 3, axis=-1)


def channel_mixer(arr, r=(1, 0, 0), g=(0, 1, 0), b=(0, 0, 1), monochrome=False, **_):
    rgb = to_rgb(arr)
    if monochrome:
        mono = np.clip(rgb @ np.asarray(r, np.float32), 0, 1)[..., None]
        out = np.repeat(mono, 3, axis=-1)
    else:
        m = np.asarray([r, g, b], np.float32)
        out = np.clip(rgb @ m.T, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def photo_filter(arr, color="#ff9800", density=0.25, preserve_luminosity=True, **_):
    rgb = to_rgb(arr)
    tint = np.asarray(hex_to_rgb(color), np.float32)
    if preserve_luminosity:
        lum = luma(rgb)[..., None]
        target = tint * luma(np.asarray([[tint]], np.float32))[0, 0] * 2  # 滤色片自身亮度归一
        out = rgb * (1 - density) + (target * (lum / (luma(np.asarray([[target]], np.float32))[0, 0] + 1e-6))) * density
    else:
        out = rgb * (1 - density) + tint * density
    out = np.clip(out, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def gradient_map(arr, stops=None, **_):
    rgb = to_rgb(arr)
    g = luma(rgb)
    stops = stops or [["#000000", 0.0], ["#ffffff", 1.0]]
    pos = np.asarray([s[1] for s in stops], np.float32)
    cols = np.asarray([hex_to_rgb(s[0]) for s in stops], np.float32)
    out = np.stack([np.interp(g, pos, cols[:, i]) for i in range(3)], -1).astype(np.float32)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def selective_color(arr, color="reds", cyan=0.0, magenta=0.0, yellow=0.0, black=0.0,
                    relative=True, **_):
    rgb = to_rgb(arr)
    h, s, l = _rgb_to_hsl(rgb)
    centers = {"reds": 0, "yellows": 60, "greens": 120, "cyans": 180, "blues": 240,
               "magentas": 300, "whites": -1, "neutrals": -2, "blacks": -3}
    c = centers[color]
    if c >= 0:
        dist = np.minimum(np.abs(h - c), 360 - np.abs(h - c))
        w = np.clip((60 - dist) / 30, 0, 1) * (s > 0.08)
    elif c == -1:
        w = (l > 0.75).astype(np.float32)
    elif c == -2:
        w = ((l <= 0.75) & (l >= 0.25) & (s < 0.25)).astype(np.float32)
    else:
        w = (l < 0.25).astype(np.float32)
    w = np.asarray(w, np.float32)[..., None]
    delta = np.asarray([-cyan, -magenta, -yellow], np.float32)  # CMY 与 RGB 反向
    if relative:
        out = rgb * (1 + delta * w)
    else:
        out = rgb + delta * w
    if black > 0:      # 黑色分量:压暗该色域
        out = out * (1 - black * w)
    elif black < 0:    # 减黑:提亮该色域
        out = out + (-black) * w * (1 - out) * 0.5
    out = np.clip(out, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def shadows_highlights(arr, shadows=0.0, highlights=0.0, radius=48, **_):
    rgb = to_rgb(arr)
    lum = luma(rgb)
    # 低/高亮度软蒙版(半径用图像对角比例做软过渡)
    r = max(radius, 8) / max(lum.shape)
    sm = np.clip((0.5 - lum) / max(0.5 * r * 2, 1e-3), 0, 1)
    hm = np.clip((lum - 0.5) / max(0.5 * r * 2, 1e-3), 0, 1)
    lift = sm[..., None] * shadows * 0.5
    press = hm[..., None] * highlights * 0.5
    out = np.clip(rgb + lift - press, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def posterize(arr, levels_n=4, **_):
    n = max(int(levels_n), 2)
    lut = (np.floor(np.linspace(0, 1, 256) * (n - 1)) / (n - 1))
    return _rgb_lut(to_rgb(arr), lut.astype(np.float32))


def threshold(arr, t=0.5, **_):
    g = luma(to_rgb(arr))
    out = (g > t).astype(np.float32)
    return np.repeat(out[..., None], 3, axis=-1)


def invert(arr, **_):
    rgb = 1.0 - to_rgb(arr)
    if arr.shape[2] == 4:
        rgb = np.dstack([rgb, arr[..., 3]])
    return rgb


def desaturate(arr, **_):
    g = luma(to_rgb(arr))[..., None]
    out = np.repeat(g, 3, axis=-1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def match_color(arr, reference="", strength=1.0, **_):
    """匹配颜色(简化):通道均值/方差对齐到参考图;strength 控制力度。"""
    from _px_core import load_image
    ref = load_image(reference) if reference else None
    if ref is None:
        raise ValueError("match-color 需要 reference=<参考图路径>")
    rgb, rr = to_rgb(arr), to_rgb(ref)
    out = rgb.copy()
    for c in range(3):
        mu, mr = rgb[..., c].mean(), rr[..., c].mean()
        sd, sr = rgb[..., c].std() + 1e-6, rr[..., c].std() + 1e-6
        moved = (rgb[..., c] - mu) * (sr / sd) + mr
        out[..., c] = rgb[..., c] * (1 - strength) + moved * strength
    out = np.clip(out, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out
