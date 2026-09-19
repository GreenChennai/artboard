"""E 组(编码与体积)实现(指导书 §5.2):convert / compress / optimize / strip-meta。
禁止硬编码 quality 默认值——一律经 _img_core.PROFILES。"""

from __future__ import annotations

import pathlib

from _img_core import (ALPHA_CAPABLE, encode_image, fail, input_expand,
                       ok_envelope, out_path_for, quality_for, result_item)

ALPHA_WARN = "ALPHA_FLATTENED"


def _open(p):
    from PIL import Image
    return Image.open(p)


def _flatten(img, bg_hex: str):
    """E7(alpha 与底色合成):透明 → 铺底(默认白,禁止黑底)。"""
    from PIL import Image
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        base = Image.new("RGB", img.size, (255, 255, 255) if bg_hex in (None, "", "#ffffff") else bg_hex)
        rgba = img.convert("RGBA")
        base.paste(rgba, mask=rgba.getchannel("A"))
        return base, True
    return img, False


def _parse_target(s: str) -> int:
    s = s.strip().upper()
    if s.endswith("KB"):
        return int(float(s[:-2]) * 1024)
    if s.endswith("MB"):
        return int(float(s[:-2]) * 1024 * 1024)
    return int(s)


def cmd_convert(args) -> int:
    """E1:格式转换(引擎自动:webp/avif 优先 ffmpeg,其余 Pillow)。"""
    to = args.to.lower()
    if to not in ALPHA_CAPABLE and args.alpha == "keep":
        args.alpha = "flatten"
    results = []
    for src in input_expand(args):
        try:
            img = _open(src)
            before = src.stat().st_size
            warns = []
            if args.alpha == "flatten" or (to in ("jpeg", "bmp") ):
                img, flat = _flatten(img, args.bg)
                if flat and to in ("jpeg", "bmp"):
                    warns.append(ALPHA_WARN)
            img = _apply_exif_icc(img, args, warns)
            if args.colors:
                img = _quantize(img, args.colors)
            q = quality_for(args, to)
            data, meta = encode_image(img, to, q, args)
            if args.dpi:
                out = args.out or out_path_for(src, args, "", to)
                _rewrite_with_dpi(data, to, args.dpi, out)
            else:
                out = args.out or out_path_for(src, args, "convert", to)
                pathlib.Path(out).write_bytes(data)
            item = result_item(src, out, before, data, engine=meta["engine"],
                               quality=q, warnings=warns + meta["warnings"],
                               degraded=meta["degraded"])
            results.append(item)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return ok_envelope("convert", results)


def _apply_exif_icc(img, args, warns: list):
    """E1 的 --exif strip(默认,隐私)与 --icc keep/strip/srgb。"""
    if getattr(args, "exif", "strip") == "strip":
        try:
            img.info.pop("exif", None)
        except Exception:  # noqa: BLE001
            pass
    icc_action = getattr(args, "icc", "keep")
    if icc_action == "strip" and "icc_profile" in img.info:
        img.info.pop("icc_profile", None)
        warns.append("ICC_STRIPPED")
    return img


def _rewrite_with_dpi(data: bytes, fmt: str, dpi, out: pathlib.Path):
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(data))
    dpi_tuple = (dpi, dpi) if isinstance(dpi, int) else tuple(int(v) for v in str(dpi).split(","))
    img.save(out, dpi=dpi_tuple)


def _encode_at(img, fmt: str, q: int, args) -> bytes:
    data, _meta = encode_image(img.copy(), fmt, q, args)
    return data


def cmd_compress(args) -> int:
    """E2:目标体积压缩(§5.2 E2 唯一二分实现)。"""
    target = _parse_target(args.target)
    fmt = (args.format or "").lower()
    fmt = {"jpg": "jpeg"}.get(fmt, fmt)
    results = []
    for src in input_expand(args):
        try:
            img = _open(src)
            before = src.stat().st_size
            warns: list[str] = []
            fmt_eff = fmt or {"PNG": "png"}.get((img.format or "png").upper(),
                                                (img.format or "png").lower())
            if fmt_eff not in ("jpeg", "webp", "avif", "png", "tiff", "bmp"):
                fmt_eff = "png"
            if fmt_eff in ("jpeg", "bmp") or (fmt_eff not in ALPHA_CAPABLE):
                img, flat = _flatten(img, args.bg)
                if flat:
                    warns.append(ALPHA_WARN)
            work = img
            steps = args.steps or (4 if fmt_eff == "avif" else 8)
            best_q, best_data = args.max_quality, _encode_at(work, fmt_eff, args.max_quality, args)
            if len(best_data) <= target * (1 + args.tolerance):
                quality = best_q
            else:
                low, high, quality, best_data = args.min_quality, args.max_quality, None, None
                for _ in range(max(1, steps)):
                    if low > high:
                        break
                    mid = (low + high) // 2
                    buf = _encode_at(work, fmt_eff, mid, args)
                    if len(buf) <= target:
                        quality, best_data = mid, buf
                        low = mid + 1
                    else:
                        high = mid - 1
            degraded = False
            if quality is None:
                # 降级链:换格式 → 缩尺寸 → min_quality 兜底(§5.2 E2)
                quality = args.min_quality
                if args.allow_format_switch and fmt_eff != "webp":
                    fmt_eff = "webp"
                    best_data = _encode_at(work, fmt_eff, quality, args)
                elif args.allow_downscale:
                    for _ in range(3):
                        work = work.resize((max(1, work.width * 9 // 10),
                                            max(1, work.height * 9 // 10)))
                        best_data = _encode_at(work, fmt_eff, quality, args)
                        if len(best_data) <= target:
                            break
                if best_data is None or len(best_data) > target:
                    best_data = best_data or _encode_at(work, fmt_eff, quality, args)
                    degraded = True
                    warns.append("TARGET_UNREACHABLE")
            out = args.out or out_path_for(src, args, "compress",
                                           "jpg" if fmt_eff == "jpeg" else fmt_eff)
            pathlib.Path(out).write_bytes(best_data)
            item = result_item(src, out, before, best_data,
                               engine=("ffmpeg" if fmt_eff == "avif" else "pillow"),
                               quality=quality, warnings=warns, degraded=degraded)
            results.append(item)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return ok_envelope("compress", results)


def cmd_optimize(args) -> int:
    """E3:无损优化(Pillow optimize/compress_level=9;外部 oxipng 探测含假阳性守卫)。"""
    results = []
    for src in input_expand(args):
        try:
            before = src.stat().st_size
            img = _open(src)
            fmt = (img.format or src.suffix.lstrip('.')).lower()
            fmt = {"jpg": "jpeg"}.get(fmt, fmt)
            data, meta = encode_image(img, fmt, 95,
                                      type("A", (), {"optimize": True})())
            out = args.out or out_path_for(src, args, "opt",
                                           "jpg" if fmt == "jpeg" else fmt)
            pathlib.Path(out).write_bytes(data)
            item = result_item(src, out, before, data, engine=meta["engine"])
            results.append(item)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return ok_envelope("optimize", results)


def cmd_strip_meta(args) -> int:
    """E6:剥离 EXIF/GPS/XMP(--keep-icc 默认开:剥 ICC 会让广色域变灰)。"""
    results = []
    for src in input_expand(args):
        try:
            img = _open(src)
            before = src.stat().st_size
            warns = []
            for k in ("exif", "xmp", "Adobe", "photoshop"):
                img.info.pop(k, None)
            if not args.keep_icc and "icc_profile" in img.info:
                img.info.pop("icc_profile", None)
                warns.append("ICC_STRIPPED")
            fmt = (src.suffix.lstrip('.') or "png").lower()
            fmt = {"jpg": "jpeg"}.get(fmt, fmt)
            out = args.out or out_path_for(src, args, "strip",
                                           "jpg" if fmt == "jpeg" else fmt)
            img.save(out)
            item = result_item(src, out, before, out.stat().st_size,
                               warnings=warns)
            results.append(item)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return ok_envelope("strip-meta", results)
