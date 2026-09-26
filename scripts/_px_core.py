"""pixel 引擎公共层:JSON 契约、图像 IO(float32 归一)、蒙版解析。

约定(与 imageops/_img_core 同风格):
- 内部一律 float32 / [0,1] / RGB(带 alpha 为 H×W×4),出口才转 8bit;
- 蒙版统一为 H×W float32 [0,1]:1 = 完全应用本步效果,0 = 完全保留原图;
- 失败路径末行必为合法 JSON(selfcheck.jsonfail 契约);
- 退出码:0 成功 / 1 业务失败 / 2 参数错 / 3 依赖缺失。
"""

from __future__ import annotations

import json
import os
import re
import sys

import numpy as np
from PIL import Image

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_DEP = 0, 1, 2, 3


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def fail(cmd: str, code: str, detail: str = "", hint: str = "") -> int:
    emit({"ok": False, "cmd": cmd, "error": code, "detail": detail, "hint": hint})
    return EXIT_DEP if code == "NO_DEP" else (EXIT_USAGE if code == "USAGE" else EXIT_FAIL)


def load_image(path: str) -> np.ndarray:
    """读图 → float32 RGB(A)[0,1];EXIF 旋正(方向矫正属于链路第一步,读取时顺带做)。"""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with Image.open(path) as im:
        im = im.convert("RGBA")
        try:
            from PIL import ImageOps
            im = ImageOps.exif_transpose(im)
        except Exception:  # noqa: BLE001 — 无 EXIF 时跳过
            pass
        arr = np.asarray(im, dtype=np.float32) / 255.0
    return arr


def save_image(arr: np.ndarray, path: str, fmt: str | None = None) -> str:
    """float [0,1] → 8bit 落盘。输出编码/压缩收口仍归 imageops(pixel 只做像素加工)。"""
    a = np.clip(arr, 0, 1)
    mode = "RGBA" if a.ndim == 3 and a.shape[2] == 4 else "RGB"
    im = Image.fromarray((a * 255 + 0.5).astype(np.uint8), mode)
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    im.save(path, format=(fmt.upper() if fmt else None))
    return path


def to_rgb(arr: np.ndarray) -> np.ndarray:
    """丢 alpha(调整类不拍平透明件:调用方在蒙版里保留 alpha 通道)。"""
    return arr[..., :3] if arr.ndim == 3 and arr.shape[2] == 4 else arr


def luma(arr: np.ndarray) -> np.ndarray:
    """Rec.709 亮度(HxW)。"""
    rgb = to_rgb(arr)
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


_HEX = re.compile(r"^#([0-9a-fA-F]{6})$")


def hex_to_rgb(s: str) -> tuple[float, float, float]:
    m = _HEX.match((s or "").strip())
    if not m:
        raise ValueError(f"颜色须为 #rrggbb,得到 {s!r}")
    v = m.group(1)
    return tuple(int(v[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def build_mask(spec: str, shape: tuple[int, int], ref: np.ndarray | None = None) -> np.ndarray:
    """蒙版 DSL → H×W float32。

    luminosity            亮度即蒙版(亮部应用效果,保护暗部)
    luminosity-inv        反亮度(暗部/阴影应用)
    alpha                 用参考图 alpha(无 alpha = 全 1)
    color:#rrggbb,tol     色彩范围(色距 ≤ tol∈[0,1],可用 PIL 端先给)
    shape:rect:l,t,r,b    矩形(px;r/b 可为负数表示距右边/底)
    shape:circle:cx,cy,r  圆(px)
    shape:gradient:top    垂直渐变(上 1 → 下 0);bottom 反向
    <图片路径>            外部灰度图作蒙版(自动缩放到画布)
    """
    h, w = shape[:2]
    if not spec:
        return np.ones((h, w), dtype=np.float32)
    if spec == "luminosity":
        return np.clip(luma(ref) if ref is not None else np.ones((h, w), np.float32), 0, 1)
    if spec == "luminosity-inv":
        v = np.clip(luma(ref) if ref is not None else np.ones((h, w), np.float32), 0, 1)
        return 1.0 - v
    if spec == "alpha":
        if ref is not None and ref.ndim == 3 and ref.shape[2] == 4:
            return ref[..., 3].copy()
        return np.ones((h, w), dtype=np.float32)
    if spec.startswith("color:"):
        col, _, tol = spec[6:].partition(",")
        cr, cg, cb = hex_to_rgb(col)
        t = float(tol or 0.2)
        rgb = to_rgb(ref)
        dist = np.sqrt(((rgb - np.array([cr, cg, cb], np.float32)) ** 2).sum(-1))
        m = np.clip((t * 1.732 - dist) / max(t * 0.577, 1e-4), 0, 1)  # 软边
        return m.astype(np.float32)
    if spec.startswith("shape:rect:"):
        l, t, r, b = (float(x) for x in spec[11:].split(","))
        r = w + r if r < 0 else r
        b = h + b if b < 0 else b
        m = np.zeros((h, w), np.float32)
        m[max(int(t), 0):min(int(b), h), max(int(l), 0):min(int(r), w)] = 1.0
        return m
    if spec.startswith("shape:circle:"):
        cx, cy, rr = (float(x) for x in spec[13:].split(","))
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        return np.clip((rr - np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)) / 2.0, 0, 1)
    if spec.startswith("shape:gradient:"):
        direction = spec[15:]
        g = np.linspace(1, 0, h, dtype=np.float32) if direction == "top" else np.linspace(0, 1, h, dtype=np.float32)
        return np.repeat(g[:, None], w, axis=1)
    if os.path.isfile(spec):
        with Image.open(spec) as mim:
            mm = np.asarray(mim.convert("L").resize((w, h)), dtype=np.float32) / 255.0
        return mm
    raise ValueError(f"未知蒙版 spec:{spec}")


def apply_mask(base: np.ndarray, adjusted: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """out = base*(1-m) + adjusted*m;base/adjusted 形状以 base 为准。"""
    m = mask[..., None] if base.ndim == 3 else mask
    if adjusted.shape != base.shape:
        adjusted = to_rgb(adjusted) if base.shape[2] == 3 else adjusted
    return base * (1 - m) + adjusted * m
