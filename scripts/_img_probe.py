"""P 组(检测与体检)实现(指导书 §5.5):零 token 机检,只出 JSON 不写图。
probe / palette / contrast-check / dpi-check。"""

from __future__ import annotations

import pathlib

from _img_core import emit, fail, input_expand, ok_envelope, result_item

LUMA_W = (0.2126, 0.7152, 0.0722)


def _open(p):
    from PIL import Image
    return Image.open(p)


def _dominant(img, k: int = 5):
    rgb = img.convert("RGB").quantize(colors=min(16, max(2, k * 3)))
    pal = rgb.getpalette() or []
    counts = sorted(rgb.getcolors(maxcolors=256) or [], reverse=True)
    total = sum(c for c, _ in counts) or 1
    out = []
    for c, idx in counts[:k]:
        r, g, b = pal[idx * 3:idx * 3 + 3]
        luma = round((0.2126 * r + 0.7152 * g + 0.0722 * b) / 255, 3)
        out.append({"hex": f"#{r:02x}{g:02x}{b:02x}", "ratio": round(c / total, 3),
                    "luma": luma})
    return out


def _content_bbox(img, tol: int = 12):
    from PIL import ImageChops
    base = img.convert("RGB")
    bg = _edge_color(base)
    solid = __import__("PIL.Image", fromlist=["Image"]).new("RGB", base.size, bg)
    diff = ImageChops.difference(base, solid).convert("L")
    return diff.point(lambda v: 255 if v > tol else 0).getbbox()


def _edge_color(rgb):
    W, H = rgb.size
    px = rgb.load()
    from collections import Counter
    cnt: Counter = Counter()
    for x in range(0, W, max(1, W // 80)):
        for y in (0, H - 1):
            cnt[px[x, y]] += 1
    for y in range(0, H, max(1, H // 80)):
        for x in (0, W - 1):
            cnt[px[x, y]] += 1
    return cnt.most_common(1)[0][0] if cnt else (255, 255, 255)


def _sharpness(img):
    """拉普拉斯方差:cv2 精确,numpy 近似;都无则 None(§5.5 P1)。"""
    try:
        import cv2
        import numpy as np
        g = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
        return round(float(cv2.Laplacian(g, cv2.CV_64F).var()), 1)
    except Exception:  # noqa: BLE001
        pass
    try:
        import numpy as np
        from PIL import ImageFilter
        g = img.convert("L").filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0]))
        arr = np.asarray(g, dtype=float)
        return round(float(arr.var()), 1)
    except Exception:  # noqa: BLE001
        return None


def _exif_orientation(img):
    try:
        ex = img.getexif()
        return int(ex.get(274, 1) or 1)
    except Exception:  # noqa: BLE001
        return 1


def cmd_probe(args) -> int:
    """P1:单图体检(尺寸/模式/体积/DPI/EXIF/alpha/ICC/主色/清晰度/留白/疑点)。"""
    results = []
    for src in input_expand(args):
        try:
            img = _open(src)
            before = src.stat().st_size
            has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
            alpha_cov = None
            if has_alpha:
                a = img.convert("RGBA").getchannel("A")
                hist = a.histogram()
                alpha_cov = round(sum(hist[1:]) / max(1, sum(hist)), 4)
            dpi = None
            try:
                d = img.info.get("dpi")
                if d:
                    dpi = round(float(d[0]), 1)
            except Exception:  # noqa: BLE001
                pass
            ori = _exif_orientation(img)
            luma = img.convert("L")
            import statistics
            sample = list(luma.getdata())
            if len(sample) > 400_000:
                sample = sample[:: len(sample) // 400_000]
            mean_l = round(statistics.fmean(sample), 1)
            std_l = round(statistics.pstdev(sample), 1)
            bbox = _content_bbox(img)
            insets = {"top": bbox[1], "left": bbox[0],
                      "right": img.width - bbox[2], "bottom": img.height - bbox[3]} if bbox else None
            suspects = []
            if ori != 1:
                suspects.append("NEEDS_EXIF_FIX")
            if std_l < 2:
                suspects.append("NEAR_UNIFORM")
            for limit_name, limit in (("OVERSIZE_FOR_TAOBAO", 3 * 1024 * 1024),
                                      ("OVERSIZE_FOR_DETAIL", 500 * 1024)):
                if before > limit:
                    suspects.append(limit_name)
                    break
            item = {"input": str(src.resolve()), "size": list(img.size), "mode": img.mode,
                    "format": (img.format or "").lower(), "bytes": before,
                    "has_alpha": has_alpha, "alpha_coverage": alpha_cov,
                    "dpi": dpi, "exif_orientation": ori,
                    "icc": {"present": "icc_profile" in img.info},
                    "near_uniform": std_l < 2,
                    "sharpness": _sharpness(img),
                    "content_bbox": list(bbox) if bbox else None,
                    "insets": insets,
                    "dominant": _dominant(img, 5),
                    "mean_luma": mean_l, "std_luma": std_l,
                    "suspect": suspects,
                    "engine": "pillow+cv2" if _sharpness(img) else "pillow",
                    "degraded": False, "warnings": [], "error": None}
            results.append(item)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return ok_envelope("probe", results)


def cmd_palette(args) -> int:
    """P2:主色/调色板(hex + 占比 + luma)。"""
    results = []
    k = max(2, min(16, args.colors))
    for src in input_expand(args):
        try:
            img = _open(src)
            dom = _dominant(img, k)
            results.append({"input": str(src.resolve()), "palette": dom,
                            "degraded": False, "warnings": [], "error": None})
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return ok_envelope("palette", results)


def _wcag_ratio(fg_hex: str, bg_rgb) -> float:
    """WCAG 对比度。**入口先 float() 化**:bg 常来自 numpy 数组的均值,
    numpy.float64 会让比值一路传播到 json.dumps(不可序列化),返回前必须转回 Python 标量。"""
    def rel(c):
        c = float(c) / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def lum(rgb):
        r, g, b = (rel(v) for v in tuple(rgb)[:3])
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    from _img_core import parse_color
    l1 = lum(parse_color(fg_hex))
    l2 = lum(bg_rgb)
    lighter, darker = max(l1, l2), min(l1, l2)
    return round(float((lighter + 0.05) / (darker + 0.05)), 2)


def cmd_contrast_check(args) -> int:
    """P6:压字对比度采样(color-contrast.md 的 WCAG 口径在位图侧落地)。"""
    import numpy as np
    from PIL import Image
    src = input_expand(args)[0]
    img = _open(src).convert("RGB")
    W, H = img.size
    if "," in args.box and "%" in args.box:
        l, t, r, b = [float(v.strip().rstrip('%')) / 100 for v in args.box.split(",")]
        box = (round(l * W), round(t * H), round(r * W), round(b * H))
    else:
        box = tuple(int(v) for v in args.box.split(","))
    region = np.asarray(img.crop(box), dtype=float)
    ratio = _wcag_ratio(args.fg, tuple(region.reshape(-1, 3).mean(axis=0)))
    worst = ratio
    if args.method == "p95-1":
        flat = region.reshape(-1, 3)
        bright = flat[np.argsort(flat.sum(axis=1))[-max(1, len(flat) // 20):]].mean(axis=0)
        dark = flat[np.argsort(flat.sum(axis=1))[:max(1, len(flat) // 100)]].mean(axis=0)
        worst = min(_wcag_ratio(args.fg, bright), _wcag_ratio(args.fg, dark))
    elif args.method == "dominant":
        dom = _dominant(img.crop(box), 1)
        if dom:
            hx = dom[0]["hex"]
            worst = _wcag_ratio(args.fg, tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5)))
    emit_obj = {"ok": True, "cmd": "contrast-check", "input": str(src.resolve()),
                "box": list(box), "fg": args.fg, "method": args.method,
                "ratio": float(ratio), "worst_ratio": float(worst),
                "pass_normal": bool(worst >= 4.5), "pass_large": bool(worst >= 3.0),
                "degraded": False, "warnings": [], "error": None}
    from _img_core import emit
    emit(emit_obj)
    return 0 if emit_obj["pass_large"] else 1


def cmd_dpi_check(args) -> int:
    """P8:印刷分辨率校验(DPI = LPI×2;print-production.md 口径)。"""
    src = input_expand(args)[0]
    img = _open(src)
    if args.lpi:
        target_dpi = args.lpi * 2
    elif args.target_dpi:
        target_dpi = args.target_dpi
    else:
        raise SystemExit(fail("dpi-check", "USAGE", "需要 --lpi 或 --target-dpi"))
    if args.print_size:
        w_mm = float(str(args.print_size).lower().split("x")[0])
        required_px = round(w_mm / 25.4 * target_dpi)
    else:
        required_px = None
    actual_px = img.width
    effective = round(actual_px / (w_mm / 25.4), 1) if (args.print_size and w_mm) else None
    passed = (actual_px >= required_px) if required_px else None
    from _img_core import emit
    emit({"ok": True, "cmd": "dpi-check", "input": str(src.resolve()),
          "size": list(img.size), "lpi": args.lpi, "target_dpi": target_dpi,
          "print_size_mm": w_mm if args.print_size else None,
          "required_px": required_px, "actual_px": actual_px,
          "effective_dpi": effective, "pass": passed,
          "degraded": False, "warnings": [], "error": None})
    return 0 if (passed is None or passed) else 1


# ---------------- C9 查重(pHash 感知哈希;03 迭代新增) ----------------

def _phash(img, size: int = 32) -> int:
    """64-bit 感知哈希:缩 32×32 灰度 → 2D DCT → 左上 8×8 中位数二值化。
    纯 Python DCT(32×32 规模开销可忽略),不引 numpy。"""
    from PIL import Image
    import math
    px = list(img.convert("L").resize((size, size), Image.HAMMING).getdata())
    n = size
    norm = [(1 / n) ** 0.5 if u == 0 else (2 / n) ** 0.5 for u in range(n)]
    cos = [[norm[u] * math.cos((2 * x + 1) * u * math.pi / (2 * n))
            for x in range(n)] for u in range(n)]
    rows = [sum(cos[u][x] * px[y * n + x] for x in range(n)) for y in range(n) for u in range(n)]
    dct = [sum(cos[v][y] * rows[y * n + u] for y in range(n)) for v in range(8) for u in range(8)]
    med = sorted(dct)[len(dct) // 2]
    bits = "".join("1" if v > med else "0" for v in dct)
    return int(bits, 2)


def cmd_dedupe(args) -> int:
    """C9:同图/近重复检测(pHash 汉明距离 ≤ threshold 视为同图)。
    用于素材库收敛与多来源采集后的去重;只报告不删图。"""
    srcs = input_expand(args)
    if len(srcs) < 2:
        return fail("dedupe", "USAGE", "需要 ≥2 张输入(文件或 --in/--in-dir 目录)",
                    hint='imageops dedupe --in "materials/**/*.jpg" --threshold 6')
    hashes: dict[str, int] = {}
    warnings: list[str] = []
    for p in srcs:
        try:
            hashes[str(p)] = _phash(_open(p))
        except Exception as exc:  # noqa: BLE001 — 坏图跳过不拦全局
            warnings.append(f"{p.name}: 无法解码({type(exc).__name__})")
    names = sorted(hashes)
    dups: list[list] = []
    dropped: set[str] = set()
    for i, a in enumerate(names):
        if a in dropped:
            continue
        for b in names[i + 1:]:
            if b in dropped:
                continue
            dist = (hashes[a] ^ hashes[b]).bit_count()
            if dist <= args.threshold:
                dups.append([a, b, dist])
                dropped.add(b)  # 保留字母序靠前者作 keeper
    emit({"ok": True, "cmd": "dedupe", "count": len(names),
          "dups": dups, "kept": [n for n in names if n not in dropped],
          "threshold": args.threshold,
          "degraded": False, "warnings": warnings, "error": None})
    return 0
