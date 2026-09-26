"""P0-B 滤镜类 12 项(对标 PS Filter;依赖分级:纯 Pillow 可跑,cv2 提速/增强)。

降级纪律(pixel.py 统一执行):缺 cv2 时,blur-motion / blur-radial 走 Pillow 近似
并记入 degraded[];oil-paint 无近似实现 → 直接报错(不静默)。
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from _px_core import luma, to_rgb

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    cv2 = None  # type: ignore[assignment]


def _rgb_img(arr):
    return Image.fromarray((np.clip(to_rgb(arr), 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")


def blur_gaussian(arr, radius=4.0, **_):
    out = _rgb_img(arr).filter(ImageFilter.GaussianBlur(radius))
    a = np.asarray(out, np.float32) / 255.0
    if arr.shape[2] == 4:
        a = np.dstack([a, arr[..., 3]])
    return a


def blur_motion(arr, length=18, angle=0, **_):
    """动感模糊:cv2 线核;降级 = 多方向高斯叠加近似(弱但可用)。"""
    rgb = to_rgb(arr)
    if HAS_CV2:
        size = max(int(length), 3)
        if size % 2 == 0:
            size += 1
        k = np.zeros((size, size), np.float32)
        k[size // 2, :] = 1.0
        import math
        m = cv2.getRotationMatrix2D((size / 2 - 0.5, size / 2 - 0.5), angle, 1.0)
        k = cv2.warpAffine(k, m, (size, size))
        k /= k.sum()
        out = np.stack([cv2.filter2D(rgb[..., c], -1, k) for c in range(3)], -1)
    else:
        approx = blur_gaussian(rgb, radius=max(length / 6, 1))
        out = (rgb + approx) / 2
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def blur_radial(arr, amount=8, mode="zoom", **_):
    """径向(缩放/旋转)模糊:cv2 logPolar 位移;降级 = 多档缩放/旋转混合。"""
    rgb = to_rgb(arr)
    h, w = rgb.shape[:2]
    if HAS_CV2:
        center = (w / 2, h / 2)
        if mode == "zoom":
            m = cv2.getRotationMatrix2D(center, 0, 1.0)
            m[0, 2] += 0
            base = rgb
            acc = np.zeros_like(rgb)
            for i in range(1, 7):
                s = 1.0 - amount / 100.0 * i / 6
                resized = cv2.resize(base, None, fx=s, fy=s)
                canvas = np.zeros_like(rgb)
                rh, rw = resized.shape[:2]
                y0, x0 = (h - rh) // 2, (w - rw) // 2
                canvas[max(y0, 0):max(y0, 0) + min(rh, h), max(x0, 0):max(x0, 0) + min(rw, w)] = \
                    resized[-min(y0, 0): -min(y0, 0) + min(rh, h), -min(x0, 0): -min(x0, 0) + min(rw, w)]
                acc += canvas
            out = (base + acc / 6) / 2
        else:
            polar = cv2.logPolar(rgb, (w / 2, h / 2), w / 8, cv2.WARP_FILL_OUTLIERS)
            rest = cv2.linearPolar(polar, (w / 2, h / 2), w / 8, cv2.WARP_INVERSE_MAP)
            out = (rgb.astype(np.float32) + rest.astype(np.float32)) / 2
        out = out.astype(np.float32)
    else:
        pil = _rgb_img(rgb)
        acc = np.asarray(pil, np.float32)
        for i in range(1, 5):
            if mode == "zoom":
                s = 1.0 + 0.004 * amount * i
                t = np.asarray(pil.resize((int(w * s), int(h * s))), np.float32) / 255
                x0, y0 = (t.shape[1] - w) // 2, (t.shape[0] - h) // 2
                acc += t[y0:y0 + h, x0:x0 + w]
            else:
                acc += np.asarray(pil.rotate(amount * i / 5, resample=Image.BILINEAR), np.float32)
        out = acc / 5
        out = out / 255.0 if out.max() > 1.5 else out
        out = np.clip(out, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def sharpen_usm(arr, amount=0.6, radius=1.5, threshold=3, **_):
    im = _rgb_img(arr)
    out = im.filter(ImageFilter.UnsharpMask(radius=max(radius, 0.5), percent=int(amount * 150),
                                            threshold=int(threshold)))
    a = np.asarray(out, np.float32) / 255.0
    if arr.shape[2] == 4:
        a = np.dstack([a, arr[..., 3]])
    return a


def sharpen_highpass(arr, amount=0.8, radius=6, **_):
    rgb = to_rgb(arr)
    low = to_rgb(blur_gaussian(rgb, radius))
    high = rgb - low
    out = np.clip(rgb + high * amount, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def noise_reduce(arr, strength=0.5, **_):
    rgb = to_rgb(arr)
    if HAS_CV2:
        h = int(3 + strength * 7)
        bgr = (rgb[..., ::-1] * 255).astype(np.uint8)
        out = cv2.fastNlMeansDenoisingColored(bgr, None, h, h, 7, 21).astype(np.float32) / 255
        out = out[..., ::-1]
    else:
        med = np.asarray(_rgb_img(rgb).filter(ImageFilter.MedianFilter(3)), np.float32) / 255
        out = rgb * (1 - strength) + med * strength
    out = np.clip(out, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def add_noise(arr, amount=0.05, monochrome=True, seed=7, **_):
    rng = np.random.default_rng(seed)
    rgb = to_rgb(arr)
    if monochrome:
        n = rng.normal(0, amount, rgb.shape[:2])[..., None]
    else:
        n = rng.normal(0, amount, rgb.shape)
    out = np.clip(rgb + n.astype(np.float32), 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def emboss(arr, strength=1.0, **_):
    out = np.asarray(_rgb_img(arr).filter(ImageFilter.EMBOSS), np.float32) / 255
    out = to_rgb(arr) * (1 - strength) + out * strength
    out = np.clip(out, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def find_edges(arr, strength=1.0, invert=False, **_):
    out = np.asarray(_rgb_img(arr).filter(ImageFilter.FIND_EDGES), np.float32) / 255
    if invert:
        out = 1 - out
    out = np.clip(to_rgb(arr) * (1 - strength) + out * strength, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def glow(arr, radius=12, amount=0.5, **_):
    """发光 = 高亮部提取 → 模糊 → 屏幕混合。"""
    rgb = to_rgb(arr)
    lum = luma(rgb)[..., None]
    hi = np.clip((lum - 0.6) / 0.4, 0, 1) * rgb
    soft = to_rgb(blur_gaussian(hi, radius))
    out = 1 - (1 - rgb) * (1 - np.clip(soft * amount * 2, 0, 1))  # screen
    out = np.clip(out, 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def vignette(arr, amount=0.3, feather=0.6, **_):
    rgb = to_rgb(arr)
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (xx / w - 0.5) * 2, (yy / h - 0.5) * 2
    d = np.sqrt(nx * nx + ny * ny) / np.sqrt(2)
    v = np.clip((d - (1 - feather)) / max(feather, 1e-3), 0, 1) * amount
    out = np.clip(rgb * (1 - v[..., None]), 0, 1)
    if arr.shape[2] == 4:
        out = np.dstack([out, arr[..., 3]])
    return out


def oil_paint(arr, size=6, **_):
    """油画:需要 OpenCV(xphoto);无实现降级路径 → 报错(诚实,不静默)。"""
    if not HAS_CV2 or not hasattr(cv2, "xphoto") or not hasattr(cv2.xphoto, "oilPainting"):
        raise RuntimeError("oil-paint 需要 opencv-contrib-python(cv2.xphoto);pip install opencv-contrib-python"
                           "(或改用 posterize+noise-reduce 近似手工链)")
    bgr = (to_rgb(arr)[..., ::-1] * 255).astype(np.uint8)
    out = cv2.xphoto.oilPainting(bgr, int(size), 1)
    a = out[..., ::-1].astype(np.float32) / 255
    if arr.shape[2] == 4:
        a = np.dstack([a, arr[..., 3]])
    return a
