"""G 组(几何与尺寸)+ D 组(派生与切片)实现(指导书 §5.1/§5.3)。
禁止在本模块定义尺寸表(唯一真源 = scaffold.SIZES,经 _img_core.size_of)。"""

from __future__ import annotations

import pathlib

from _img_core import (encode_image, fail, ok_envelope, out_path_for,  # noqa: F401
                       input_expand, parse_color, resample_of, result_item,
                       size_of, need)

PIPELINE_OPS: dict[str, callable] = {}


def op(name):
    def deco(fn):
        PIPELINE_OPS[name] = fn
        return fn
    return deco


def _open(p: pathlib.Path):
    from PIL import Image
    return Image.open(p)


def _save_result(args, src, img, fmt, quality, engine="pillow", extra=None):
    """落盘 + 组装 result_item(dry-run 只回填预测路径)。"""
    from _img_core import quality_for
    quality = quality_for(args, fmt) if quality in (None, 100) else quality
    tag = getattr(args, "size_tag", "") or "out"
    ext = fmt if fmt != "jpeg" else "jpg"
    out = pathlib.Path(args.out) if getattr(args, "out", None) else out_path_for(src, args, tag, ext)
    if getattr(args, "dry_run", False):
        return result_item(src, out, src.stat().st_size if src.exists() else 0,
                           None, engine=engine, quality=quality)
    data, meta = encode_image(img, fmt, quality, args)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    item = result_item(src, out, src.stat().st_size if src.exists() else 0, data,
                       engine=engine or meta["engine"], quality=quality,
                       warnings=(extra or []) + meta.get("warnings", []),
                       degraded=meta.get("degraded", False))
    return item


def _target_spec(args, img):
    """G2/G3/D1 共用:--aspect/--size/--presets 三选一 → (w,h)。
    返回 None 表示未指定。h==0 的预设(long)必须给 --aspect/--height。"""
    if getattr(args, "size", None):
        w, h = args.size.lower().split("x")
        return int(w), int(h)
    if getattr(args, "presets", None):
        names = [s.strip() for s in args.presets.split(",") if s.strip()]
        if len(names) != 1:
            raise SystemExit(fail(args.cmd, "USAGE", "--presets 这里只接受一个键"))
        w, h = size_of(names[0])
        if h == 0:
            h = img.height
        return w, h
    if getattr(args, "aspect", None):
        aw, ah = args.aspect.replace("：", ":").split(":")
        ratio = float(aw) / float(ah)
        # 以源图长边为基准推目标尺寸(保持像素量)
        if img.width >= img.height:
            return img.width, max(1, round(img.width / ratio))
        return max(1, round(img.height * ratio)), img.height
    return None


@op("resize")
def apply_resize(img, p: dict):
    """G1:缩放。p: to/width/height/scale/max_edge/resample/no_upscale。"""
    from PIL import Image
    w, h = img.size
    if p.get("to"):
        tw, th = p["to"].lower().split("x")
        tw, th = int(tw), int(th)
    elif p.get("width") or p.get("height"):
        if p.get("width"):
            tw = int(p["width"]); th = max(1, round(h * tw / w))
        else:
            th = int(p["height"]); tw = max(1, round(w * th / h))
    elif p.get("scale"):
        s = float(p["scale"]); tw, th = max(1, round(w * s)), max(1, round(h * s))
    elif p.get("max_edge"):
        me = int(p["max_edge"])
        if max(w, h) <= me:
            return img
        s = me / max(w, h)
        tw, th = max(1, round(w * s)), max(1, round(h * s))
    else:
        raise SystemExit(fail("resize", "USAGE", "需要 --to/--width/--height/--scale/--max-edge 之一"))
    if p.get("no_upscale") and (tw > w or th > h):
        return img
    resample = resample_of(p.get("resample"), upscaling=(tw > w or th > h))
    if img.mode in ("1", "P"):
        resample = Image.Resampling.NEAREST
    return img.resize((tw, th), resample)


@op("fit")
def apply_fit(img, p: dict):
    """G2:cover 语义裁满目标框。"""
    from PIL import ImageOps
    tgt = p.get("target")
    if not tgt:
        raise SystemExit(fail("fit", "USAGE", "需要 --aspect/--size/--presets 之一"))
    tw, th = tgt
    # 目标尺寸语义:以给定 tw/th 为准(aspect 推导已保像素量)
    gravity = p.get("gravity", "center")
    if gravity == "smart":
        img = _smart_window(img, tw, th)
    out = ImageOps.fit(img, (tw, th), resample_of(p.get("resample"), False),
                       bleed=float(p.get("bleed", 0)) if p.get("bleed") else 0.0)
    return out


@op("pad")
def apply_pad(img, p: dict):
    """G3:contain 补边。bg: 颜色/edge/dominant/transparent;blur-bg 走 C6。"""
    from PIL import Image
    tgt = p.get("target")
    if not tgt:
        raise SystemExit(fail("pad", "USAGE", "需要 --aspect/--size/--presets 之一"))
    tw, th = tgt
    scale = min(tw / img.width, th / img.height)
    nw, nh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    resample = resample_of(p.get("resample"), False)
    inner = img.resize((nw, nh), resample)
    bg = p.get("bg", "#ffffff")
    if p.get("blur_bg"):
        return _blur_bg_canvas(img, tw, th, p)
    if bg == "edge":
        color = _edge_color(img)
    elif bg == "dominant":
        color = _dominant_color(img, 1)[0][0]
    else:
        color = parse_color(bg if bg != "transparent" else "#ffffff")[:3]
    canvas = Image.new("RGBA" if img.mode in ("RGBA", "LA") else "RGB", (tw, th),
                       color if isinstance(color, tuple) else color)
    if isinstance(color, tuple) and len(color) == 4 and img.mode not in ("RGBA", "LA"):
        canvas = canvas.convert("RGBA")
    canvas.paste(inner, ((tw - nw) // 2, (th - nh) // 2))
    return canvas


@op("crop")
def apply_crop(img, p: dict):
    """G4:box/pct/anchor+size 裁切(通用,非测量语义)。"""
    W, H = img.size
    if p.get("box"):
        l, t, r, b = [int(v) for v in p["box"].split(",")]
    elif p.get("pct"):
        l, t, r, b = [float(v) / 100 for v in p["pct"].split(",")]
        l, t, r, b = round(l * W), round(t * H), round(r * W), round(b * H)
    elif p.get("anchor") and p.get("size"):
        cw, ch = (int(v) for v in p["size"].lower().split("x"))
        anchors = {"tl": (0, 0), "tc": ((W - cw) // 2, 0), "tr": (W - cw, 0),
                   "ml": (0, (H - ch) // 2), "mc": ((W - cw) // 2, (H - ch) // 2),
                   "mr": (W - cw, (H - ch) // 2), "bl": (0, H - ch),
                   "bc": ((W - cw) // 2, H - ch), "br": (W - cw, H - ch)}
        l, t = anchors[p["anchor"]]
        r, b = l + cw, t + ch
    else:
        raise SystemExit(fail("crop", "USAGE", "需要 --box/--pct/--anchor+--size 之一"))
    clamp = p.get("clamp", True)
    if not clamp and (l < 0 or t < 0 or r > W or b > H):
        raise SystemExit(fail("crop", "OUT_OF_BOUNDS", f"({l},{t},{r},{b}) 越界于 {W}x{H}"))
    l, t = max(0, l), max(0, t)
    r, b = min(W, r), min(H, b)
    if r <= l or b <= t:
        raise SystemExit(fail("crop", "EMPTY_BOX", f"裁切框为空 ({l},{t},{r},{b})"))
    return img.crop((l, t, r, b))


@op("expand")
def apply_expand(img, p: dict):
    """G5:四周加固定边距。"""
    from PIL import ImageOps
    m = p.get("margin", "0")
    parts = [int(v) for v in str(m).split(",")]
    if len(parts) == 1:
        border = parts[0] * 4
    elif len(parts) == 2:
        border = (parts[0], parts[1]) * 2
    else:
        border = (parts[0], parts[1], parts[2], parts[3])
    color = parse_color(p.get("bg", "#ffffff"))
    if color[3] == 0 and img.mode not in ("RGBA", "LA"):
        return ImageOps.expand(img, border=border, fill=(255, 255, 255))
    if img.mode == "RGB" and color[3] == 255:
        return ImageOps.expand(img, border=border, fill=color[:3])
    rgba = img.convert("RGBA")
    out = ImageOps.expand(rgba, border=border, fill=color)
    return out


@op("rotate")
def apply_rotate(img, p: dict):
    """G6:旋转/翻转/EXIF 旋正(exif-fix 必须最先,§5.1 G6)。"""
    if p.get("exif_fix"):
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    if p.get("flip"):
        from PIL import ImageOps
        img = ImageOps.mirror(img) if p["flip"] == "h" else ImageOps.flip(img)
    if p.get("angle"):
        expand = bool(p.get("expand"))
        fill = parse_color(p.get("fill", "#ffffff"))
        img = img.rotate(float(p["angle"]), expand=expand,
                         fillcolor=fill[:3] if img.mode == "RGB" else fill)
    return img


@op("trim")
def apply_trim(img, p: dict):
    """G7:裁透明边(alpha)或纯色边(color+tol)。"""
    by = p.get("by", "alpha")
    if by == "alpha":
        if img.mode not in ("RGBA", "LA"):
            return img, ["NO_ALPHA_FOUND"]
        bbox = img.getchannel("A").getbbox()
    else:
        bg = p.get("bg", "edge")
        from PIL import ImageChops
        base = img.convert("RGB")
        ref = (_edge_color(base) if bg == "edge" else parse_color(bg)[:3])
        solid = __import__("PIL.Image", fromlist=["Image"]).new("RGB", base.size, ref)
        diff = ImageChops.difference(base, solid).convert("L")
        tol = int(p.get("tol", 12))
        bbox = diff.point(lambda v: 255 if v > tol else 0).getbbox()
    if not bbox:
        return img, ["NO_ALPHA_FOUND"] if by == "alpha" else ["FULLY_UNIFORM"]
    pad = int(p.get("pad", 0))
    l, t, r, b = bbox
    l, t = max(0, l - pad), max(0, t - pad)
    r, b = min(img.width, r + pad), min(img.height, b + pad)
    return img.crop((l, t, r, b)), []


def _edge_color(img) -> tuple:
    """四边众数色(G3 --bg edge;淡化接缝)。"""
    rgb = img.convert("RGB")
    W, H = rgb.size
    px = rgb.load()
    from collections import Counter
    cnt: Counter = Counter()
    for x in range(0, W, max(1, W // 100)):
        for y in (0, H - 1):
            cnt[px[x, y]] += 1
    for y in range(0, H, max(1, H // 100)):
        for x in (0, W - 1):
            cnt[px[x, y]] += 1
    return cnt.most_common(1)[0][0] if cnt else (255, 255, 255)


def _dominant_color(img, k: int = 6) -> list:
    """主色 top-k(P2 共用):quantize 中板,返回 [(rgb, ratio)]。"""
    rgb = img.convert("RGB")
    q = rgb.quantize(colors=min(16, max(2, k * 3)))
    pal = q.getpalette() or []
    counts = sorted(q.getcolors(maxcolors=256) or [], reverse=True)
    total = sum(c for c, _ in counts) or 1
    out = []
    for c, idx in counts[:k]:
        rgbv = tuple(pal[idx * 3:idx * 3 + 3])
        out.append((rgbv, c / total))
    return out


def _smart_window(img, tw, th):
    """G8 降级链:smartcrop → cv2 显著性 → center(§5.1 G8)。"""
    try:
        import smartcrop  # type: ignore  # noqa: F401
        sc = smartcrop.SmartCrop()
        res = sc.crop(img, width=tw, height=th)
        box = res["topCrop"]
        l, t = box["x"], box["y"]
        cw, ch = box["width"], box["height"]
        # 取覆盖比例窗
        return img.crop((l, t, min(img.width, l + cw), min(img.height, t + ch)))
    except ImportError:
        pass
    try:
        import cv2  # type: ignore
        import numpy as np
        gray = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
        sal = cv2.saliency.StaticSaliencySpectralMethod_create() if hasattr(cv2.saliency, "StaticSaliencySpectralMethod") else None
        if sal is not None:
            ok, m = sal.computeSaliency()
            if ok:
                ys, xs = np.where(m > 2 * m.mean())
                if len(xs) > 10:
                    l, r = int(xs.min()), int(xs.max())
                    t, b = int(ys.min()), int(ys.max())
                    ratio = tw / th
                    cw = min(r - l, img.width)
                    ch = min(b - t, img.height)
                    cw = max(cw, int(ch * ratio)); ch = max(ch, int(cw / ratio))
                    cx, cy = (l + r) // 2, (t + b) // 2
                    l = max(0, min(img.width - cw, cx - cw // 2))
                    t = max(0, min(img.height - ch, cy - ch // 2))
                    return img.crop((l, t, l + cw, t + ch))
    except Exception as exc:  # noqa: BLE001 显著性失败 → 规则裁
        _ = exc
    return img  # center:调用方 fit 兜底


def _blur_bg_canvas(img, tw, th, p: dict):
    """C6:自身放大模糊铺底 + 居中原图(pad --blur-bg 等价入口)。"""
    from PIL import Image, ImageFilter, ImageEnhance
    bg = img.convert("RGB").resize((tw, th), resample_of(None, True))
    bg = bg.filter(ImageFilter.GaussianBlur(float(p.get("blur", 24))))
    dim = float(p.get("dim", 0.25))
    if dim > 0:
        bg = ImageEnhance.Brightness(bg).enhance(1.0 - dim)
    s = float(p.get("scale", 1.0)) if p.get("scale") else 1.0
    nw = max(1, round(tw * s)) if s <= 1.0 else tw
    scale = min(tw / img.width, th / img.height) * (s if s <= 1.0 else 1.0)
    nw, nh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    inner = img.resize((nw, nh), resample_of(None, False))
    canvas = bg.convert("RGBA") if inner.mode == "RGBA" else bg
    canvas.paste(inner, ((tw - nw) // 2, (th - nh) // 2), inner if inner.mode == "RGBA" else None)
    return canvas


# ---------------- CLI 处理器 ----------------

def _run_single(args, transform, tag: str, fmt: str, quality: int):
    """单文件处理骨架:开图 → 变换 → 落盘。transform 返回 img 或 (img, warns)。"""
    results, all_warns = [], []
    for src in input_expand(args):
        try:
            img = _open(src)
            before = src.stat().st_size
            out = transform(img)
            warns: list[str] = []
            if isinstance(out, tuple):
                out, warns = out
            item = _save_result(args, src, out, fmt, quality, extra=warns)
            item["size_tag"] = tag
            results.append(item)
        except SystemExit:
            raise
        except OSError as exc:
            results.append(result_item(src, None, 0, None, error=f"OSError: {exc}"))
        except Exception as exc:  # noqa: BLE001 兜底必须带类型与消息(§9.3)
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return results, all_warns


def cmd_geom(args) -> int:
    quality = getattr(args, "quality", None) or 82
    fmt = (getattr(args, "format_out", None) or "png").lower()
    fmt = {"jpg": "jpeg"}.get(fmt, fmt)
    p = vars(args)
    if args.cmd == "resize":
        transform = lambda im: apply_resize(im, p)  # noqa: E731
    elif args.cmd in ("fit", "pad", "smartcrop"):
        # target 依赖源图(aspect 按源推),懒解析
        transform = lambda im: {"fit": apply_fit, "pad": apply_pad, "smartcrop": apply_fit}[
            args.cmd](im, {**p, "target": _target_spec(args, im),
                           "gravity": p.get("gravity", "center" if args.cmd != "smartcrop" else "smart")})  # noqa: E731
    elif args.cmd == "crop":
        transform = lambda im: apply_crop(im, p)  # noqa: E731
    elif args.cmd == "expand":
        transform = lambda im: apply_expand(im, p)  # noqa: E731
    elif args.cmd == "rotate":
        transform = lambda im: apply_rotate(im, p)  # noqa: E731
    elif args.cmd == "trim":
        transform = lambda im: apply_trim(im, p)  # noqa: E731
    elif args.cmd == "blur-bg":
        results, warns = _run_geom_blurbg(args, p)
        return ok_envelope("blur-bg", results, warns)
    else:
        raise SystemExit(fail(args.cmd, "USAGE", f"未知几何子命令 {args.cmd}"))
    results, warns = _run_single(args, transform, args.cmd, fmt, quality)
    return ok_envelope(args.cmd, results, warns)


def _run_geom_blurbg(args, p):
    results = []
    for src in input_expand(args):
        try:
            img = _open(src)
            tgt = _target_spec(args, img)
            out = _blur_bg_canvas(img, tgt[0], tgt[1], p)
            results.append(_save_result(args, src, out,
                                        (getattr(args, "format_out", None) or "png").lower(),
                                        getattr(args, "quality", None) or 82))
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return results, []


def cmd_derive(args) -> int:
    """D1:一图 → 多规格矩阵(尺寸/预设/比例 × 格式 × 倍率)。"""
    results = []
    formats = [f.strip().lower() for f in (args.formats or "").split(",") if f.strip()] or ["png"]
    scales = [float(s) for s in (args.scales or "1").split(",") if s.strip()]
    presets = [s.strip() for s in (args.presets or "").split(",") if s.strip()]
    sizes = []
    for pr in presets:
        w, h = size_of(pr)
        if h == 0:
            if not args.aspect:
                raise SystemExit(fail("derive", "USAGE",
                                      f"预设 {pr} 为 h=0(高度随内容),必须配 --aspect",
                                  hint="--aspect 3:4 或 --sizes 2400x6000"))
            img0 = _open(input_expand(args)[0])
            aw, ah = args.aspect.split(":")
            h = max(1, round(w * float(ah) / float(aw)))
        sizes.append((pr, w, h))
    for raw in (args.sizes or "").split(","):
        raw = raw.strip().lower()
        if raw:
            w, h = raw.split("x")
            sizes.append((raw, int(w), int(h)))
    if not sizes:
        raise SystemExit(fail("derive", "USAGE", "需要 --presets 或 --sizes"))
    for src in input_expand(args):
        try:
            img = _open(src)
            before = src.stat().st_size
            for (pname, tw, th) in sizes:
                for fmt in formats:
                    for sc in scales:
                        p = {"target": (round(tw * sc), round(th * sc)),
                             "gravity": args.gravity}
                        out = apply_fit(img, p) if args.mode == "fit" else apply_pad(img, p)
                        fmt_norm = {"jpg": "jpeg"}.get(fmt, fmt)
                        args.size_tag = f"{pname}{'' if sc == 1 else f'@{int(sc)}x'}"
                        args.out = None
                        args.size_tag = args.size_tag
                        item = _save_result(args, src, out, fmt_norm,
                                            _profile_q(args, fmt_norm))
                        item["preset"] = pname
                        item["scale"] = sc
                        results.append(item)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return ok_envelope("derive", results)


def _profile_q(args, fmt: str) -> int:
    from _img_core import PROFILES
    prof = PROFILES[getattr(args, "profile", None) or "platform"]
    key = {"jpeg": "jpeg", "webp": "webp", "avif": "avif"}.get(fmt)
    if fmt == "png":
        return 100
    return int(getattr(args, "quality", None) or prof.get(key, 82))


def cmd_slice(args) -> int:
    """D2:宫格切片 / 长图切分。"""
    results = []
    if not args.in_glob and not getattr(args, "inputs", None):
        raise SystemExit(fail("slice", "USAGE", "需要 --in"))
    for src in input_expand(args):
        try:
            img = _open(src)
            fmt = (src.suffix.lstrip('.') or "png").lower()
            fmt = {"jpg": "jpeg"}.get(fmt, fmt)
            outs = []
            if args.grid:
                rows, cols = (int(v) for v in args.grid.lower().split("x"))
                cw, ch = img.width // cols, img.height // rows
                for r in range(rows):
                    for c in range(cols):
                        box = (c * cw, r * ch, (c + 1) * cw if c < cols - 1 else img.width,
                               (r + 1) * ch if r < rows - 1 else img.height)
                        outs.append((f"-r{r + 1}c{c + 1}", img.crop(box)))
            elif args.rows or args.cols:
                rows = args.rows or 1
                cols = args.cols or 1
                cw, ch = img.width // cols, img.height // rows
                for r in range(rows):
                    for c in range(cols):
                        box = (c * cw, r * ch, min(img.width, (c + 1) * cw),
                               min(img.height, (r + 1) * ch))
                        outs.append((f"-r{r + 1}c{c + 1}", img.crop(box)))
            elif args.max_height or args.max_width:
                overlap = int(args.overlap or 0)
                if args.max_height:
                    step = args.max_height - overlap
                    idx = 1
                    y = 0
                    while y < img.height:
                        box = (0, y, img.width, min(img.height, y + args.max_height))
                        outs.append((f"-p{idx:02d}", img.crop(box)))
                        y += step
                        idx += 1
                else:
                    step = args.max_width - overlap
                    idx = 1
                    x = 0
                    while x < img.width:
                        box = (x, 0, min(img.width, x + args.max_width), img.height)
                        outs.append((f"-p{idx:02d}", img.crop(box)))
                        x += step
                        idx += 1
            else:
                raise SystemExit(fail("slice", "USAGE", "需要 --grid/--rows/--cols/--max-height/--max-width 之一"))
            before = src.stat().st_size
            d = pathlib.Path(args.out_dir or src.parent)
            d.mkdir(parents=True, exist_ok=True)
            for tag, piece in outs:
                out = d / f"{src.stem}{tag}.{ 'jpg' if fmt == 'jpeg' else fmt }"
                data, meta = encode_image(piece, fmt, 92)
                out.write_bytes(data)
                results.append(result_item(src, out, before, data, engine=meta["engine"]))
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return ok_envelope("slice", results)


def cmd_thumb(args) -> int:
    """D3:缩略图 / LQIP base64(批次三,提前并入;Pillow 足够)。"""
    import base64
    import io
    results = []
    fmt = (args.format or "webp").lower()
    for src in input_expand(args):
        try:
            img = _open(src)
            s = args.max_edge / max(img.width, img.height)
            th = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))),
                            resample_of(None, False))
            out = out_path_for(src, args, f"th{args.max_edge}", fmt)
            data, meta = encode_image(th, fmt, 80)
            out.write_bytes(data)
            item = result_item(src, out, src.stat().st_size, data, engine=meta["engine"])
            if args.lqip:
                s2 = args.lqip / max(img.width, img.height)
                tiny = img.resize((max(1, round(img.width * s2)), max(1, round(img.height * s2))),
                                  resample_of(None, False))
                if args.blur:
                    from PIL import ImageFilter
                    tiny = tiny.filter(ImageFilter.GaussianBlur(float(args.blur)))
                buf = io.BytesIO()
                tiny.save(buf, "WEBP", quality=40)
                item["lqip"] = f"data:image/webp;base64,{base64.b64encode(buf.getvalue()).decode()}"
            results.append(item)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return ok_envelope("thumb", results)

