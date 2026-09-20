"""C 组(合成层)实现(指导书 §5.4,批次二核心项提前落地):
card(圆角+描边+阴影)/ watermark(文字·平铺)/ stitch(纵·横拼接)/
montage(网格拼图·多稿联络表)/ tone(色调统一)。
混合模式矩阵与 PROFILES 禁止在本模块重建(唯一真源 _img_core)。"""

from __future__ import annotations

import pathlib

from _img_core import (encode_image, fail, input_expand, ok_envelope,
                       out_path_for, parse_color, resample_of, result_item)


def _open(p):
    from PIL import Image
    return Image.open(p)


def _shadow_layer(size, radius, shadow: str):
    """C1 阴影:dx,dy,blur,#rrggbbaa → 独立 RGBA 层。"""
    from PIL import Image, ImageFilter
    dx, dy, blur, color = shadow.split(",")
    W, H = size
    layer = Image.new("RGBA", (W + blur * 4, H + blur * 4), (0, 0, 0, 0))
    from PIL import ImageDraw
    d = ImageDraw.Draw(layer)
    c = parse_color(color)
    d.rounded_rectangle([blur * 2, blur * 2, blur * 2 + W, blur * 2 + H],
                        radius=radius, fill=c)
    layer = layer.filter(ImageFilter.GaussianBlur(float(blur)))
    return layer, int(dx) + blur, int(dy) + blur


def cmd_card(args) -> int:
    """C1:圆角 + 描边 + 阴影(任意矩形卡片化,不依赖 alpha)。"""
    results = []
    for src in input_expand(args):
        try:
            from PIL import Image, ImageDraw
            img = _open(src).convert("RGBA")
            before = src.stat().st_size
            radius = int(args.radius or 0)
            pad = 0
            shadow_layer = None
            if args.shadow:
                shadow_layer, ox, oy = _shadow_layer(img.size, radius, args.shadow)
                blur = int(args.shadow.split(",")[2])
                pad = blur * 2
            W, H = img.width + pad * 2, img.height + pad * 2
            canvas = Image.new("RGBA", (W, H), parse_color(args.bg or "transparent"))
            if shadow_layer is not None:
                canvas.alpha_composite(shadow_layer, (max(0, pad - blur), max(0, pad - blur)))
            # 圆角蒙版裁切主体
            if radius > 0:
                mask = Image.new("L", img.size, 0)
                d = ImageDraw.Draw(mask)
                d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=radius, fill=255)
                canvas.paste(img, (pad, pad), mask)
            else:
                canvas.paste(img, (pad, pad), img)
            if args.border:
                w_str, col = args.border.split(":", 1)
                bw = int(w_str)
                d = ImageDraw.Draw(canvas)
                d.rounded_rectangle([pad, pad, pad + img.width - 1, pad + img.height - 1],
                                    radius=radius, outline=parse_color(col), width=bw)
            out = args.out or out_path_for(src, args, "card", "png")
            data, meta = encode_image(canvas, "png", 95)
            out.write_bytes(data)
            results.append(result_item(src, out, before, data, engine=meta["engine"]))
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return ok_envelope("card", results)


def cmd_watermark(args) -> int:
    """C3:水印(文字/图片,单点九锚/平铺)。禁压主体是设计纪律,工具不拦。"""
    results = []
    for src in input_expand(args):
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = _open(src).convert("RGBA")
            before = src.stat().st_size
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            opacity = max(0.05, min(1.0, float(args.opacity or 0.35)))
            if args.text:
                font = ImageFont.truetype(args.font, int(args.size or 24)) if args.font else ImageFont.load_default()
                color = parse_color(args.color or "#ffffff")
                color = (color[0], color[1], color[2], int(255 * opacity))
                if args.position == "tile":
                    tw, th = (int(v) for v in (args.tile_gap or "240x180").lower().split("x"))
                    for y in range(0, img.height + th, th):
                        for x in range(0, img.width + tw, tw):
                            d.text((x, y), args.text, font=font, fill=color)
                else:
                    anchors = {"tl": "la", "tc": "ma", "tr": "ra", "ml": "lm", "mc": "mm",
                               "mr": "rm", "bl": "ls", "bc": "ms", "br": "rs"}
                    pos = args.position or "br"
                    margin = int(args.margin or 24)
                    xy = {"la": (margin, margin), "ma": (img.width // 2, margin),
                          "ra": (img.width - margin, margin),
                          "lm": (margin, img.height // 2), "mm": (img.width // 2, img.height // 2),
                          "rm": (img.width - margin, img.height // 2),
                          "ls": (margin, img.height - margin),
                          "ms": (img.width // 2, img.height - margin),
                          "rs": (img.width - margin, img.height - margin)}[pos]
                    d.text(xy, args.text, font=font, fill=color, anchor=anchors[pos])
            elif args.image:
                logo = _open(args.image).convert("RGBA")
                if args.scale and args.scale != 1:
                    logo = logo.resize((max(1, round(logo.width * args.scale)),
                                        max(1, round(logo.height * args.scale))), resample_of(None, False))
                xy = (img.width - logo.width - int(args.margin or 24),
                      img.height - logo.height - int(args.margin or 24))
                if opacity < 1.0:
                    a = logo.getchannel("A").point(lambda v: int(v * opacity))
                    logo.putalpha(a)
                layer.alpha_composite(logo, xy)
            out_img = Image.alpha_composite(img, layer)
            fmt = (src.suffix.lstrip('.') or "png").lower()
            fmt = {"jpg": "jpeg"}.get(fmt, fmt)
            ext = "jpg" if fmt == "jpeg" else fmt
            out = args.out or out_path_for(src, args, "wm", ext)
            if fmt == "jpeg":
                out_img = out_img.convert("RGB")
            data, meta = encode_image(out_img, fmt, 92)
            out.write_bytes(data)
            results.append(result_item(src, out, before, data, engine=meta["engine"]))
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return ok_envelope("watermark", results)


def cmd_stitch(args) -> int:
    """C4:拼接(横/纵;通用补位,公众号双封面仍走 gzh_cover.py)。"""
    imgs = [_open(p).convert("RGB") for p in input_expand(args)]
    if len(imgs) < 2:
        raise SystemExit(fail("stitch", "USAGE", "至少两张图"))
    gap = int(args.gap or 0)
    direction = args.direction or "h"
    if direction == "h":
        h = min(i.height for i in imgs)
        imgs = [i.resize((max(1, round(i.width * h / i.height)), h), resample_of(None, False)) for i in imgs]
        W = sum(i.width for i in imgs) + gap * (len(imgs) - 1)
        canvas = Image.new("RGB", (W, h), parse_color(args.bg or "#ffffff")[:3])
        x = 0
        for i in imgs:
            canvas.paste(i, (x, 0))
            x += i.width + gap
    else:
        w = min(i.width for i in imgs)
        imgs = [i.resize((w, max(1, round(i.height * w / i.width))), resample_of(None, False)) for i in imgs]
        H = sum(i.height for i in imgs) + gap * (len(imgs) - 1)
        canvas = Image.new("RGB", (w, H), parse_color(args.bg or "#ffffff")[:3])
        y = 0
        for i in imgs:
            canvas.paste(i, (0, y))
            y += i.height + gap
    src0 = input_expand(args)[0]
    out = args.out or out_path_for(src0, args, "stitch", "png")
    data, meta = encode_image(canvas, "png", 95)
    out.write_bytes(data)
    from _img_core import result_item
    results = [result_item(src0, out, src0.stat().st_size, data, engine=meta["engine"])]
    return ok_envelope("stitch", results)


def _label_font(size: int):
    """montage 标签字体:优先 load_default(size)(Pillow ≥10.1 矢量默认字),
    旧 Pillow 退回位图默认字(小,但不崩)。不依赖 fonts/ 目录。"""
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _suggest_grid(n: int) -> str:
    """给 n 张图推荐浪费格最少、行列最方正的网格(3 图 → 1x3)。"""
    best_key, best = None, "1x1"
    for cols in range(1, n + 1):
        rows = -(-n // cols)  # ceil(n/cols)
        key = (rows * cols - n, abs(cols - rows), rows, cols)
        if best_key is None or key < best_key:
            best_key, best = key, f"{rows}x{cols}"
    return best


def cmd_montage(args) -> int:
    """C5:网格拼图(多稿联络表 contact sheet;与 stitch 同族,一表看全 N 稿)。
    行为契约:图数 < 格数 → 空格留底色(warn 不报错);图数 > 格数 → 报错并给建议网格;
    各图等比缩进格子居中(不裁内容——联络表要"看全");--label 在每格左上角叠 A/B/C/D…。"""
    from PIL import Image, ImageDraw
    try:
        paths = input_expand(args)
    except NotImplementedError:
        # --in 收到绝对路径时 pathlib.glob 会抛此异常(input_expand 既有边界,全族共有):
        # montage 自身守住 JSON 契约——绝对路径请用位置参数直给
        raise SystemExit(fail("montage", "USAGE", "--in 不支持绝对路径(既有限制)",
                              hint="把绝对路径直接写作位置参数:montage C:\\a.png C:\\b.png --grid 2x2"))
    if len(paths) < 1:
        raise SystemExit(fail("montage", "USAGE", "至少一张图(多稿联络表通常 4 张)",
                              hint="montage --in a.png b.png c.png d.png --grid 2x2 --gap 24 --label"))
    if not args.grid:
        raise SystemExit(fail("montage", "USAGE", "需要 --grid 行x列,如 2x2",
                              hint="4 稿 → 2x2;3 稿 → 1x3;6 稿 → 2x3"))
    try:
        rows, cols = (int(v) for v in str(args.grid).lower().split("x"))
    except ValueError:
        raise SystemExit(fail("montage", "USAGE", f"--grid 形如 行x列(如 2x2),收到: {args.grid}",
                              hint="4 稿 → 2x2;3 稿 → 1x3;6 稿 → 2x3"))
    if rows < 1 or cols < 1:
        raise SystemExit(fail("montage", "USAGE", "--grid 行与列都必须 ≥1"))
    cells = rows * cols
    if len(paths) > cells:
        raise SystemExit(fail("montage", "GRID_OVERFLOW",
                              f"{len(paths)} 张图放不进 {rows}x{cols}={cells} 格",
                              hint=f"{len(paths)} 图建议 --grid {_suggest_grid(len(paths))}"
                                   f";或加大网格留空格"))
    imgs = [_open(p).convert("RGB") for p in paths]
    gap = int(args.gap or 0)
    margin = int(getattr(args, "margin", 0) or 0)
    cw = max(i.width for i in imgs)
    ch = max(i.height for i in imgs)
    W = margin * 2 + cols * cw + gap * (cols - 1)
    H = margin * 2 + rows * ch + gap * (rows - 1)
    canvas = Image.new("RGB", (W, H), parse_color(args.bg or "#ffffff")[:3])
    warnings = []
    if len(paths) < cells:
        warnings.append(f"GRID_EMPTY_CELLS: {cells - len(paths)} 格留底色"
                        f"(3 稿也可改 --grid {_suggest_grid(len(paths))})")
    d = ImageDraw.Draw(canvas)
    label_size = int(getattr(args, "label_size", 0) or 0) or max(28, ch // 24)
    font = _label_font(label_size) if args.label else None
    stroke = max(2, label_size // 12)
    for idx, img in enumerate(imgs):
        r, c = divmod(idx, cols)
        s = min(cw / img.width, ch / img.height)  # cw/ch 是全图最大值,故 s ≤ 1,只缩不放
        if s < 1.0:
            img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))),
                             resample_of(None, False))
        ox = margin + c * (cw + gap) + (cw - img.width) // 2
        oy = margin + r * (ch + gap) + (ch - img.height) // 2
        canvas.paste(img, (ox, oy))
        if args.label:
            letter = chr(ord("A") + idx) if idx < 26 else f"#{idx + 1}"
            d.text((ox + label_size // 2, oy + label_size // 2), letter, font=font,
                   fill=(255, 255, 255), stroke_width=stroke, stroke_fill=(0, 0, 0))
    src0 = paths[0]
    out = pathlib.Path(args.out) if args.out else out_path_for(src0, args, "montage", "png")
    data, meta = encode_image(canvas, "png", 95)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    except OSError as e:
        return fail("montage", "WRITE_FAILED", detail=f"{out}: {e}",
                    hint="检查输出路径与权限,或改用 --out 指定可写位置")
    item = result_item(src0, out, src0.stat().st_size, data, engine=meta["engine"])
    item["grid"] = f"{rows}x{cols}"
    item["inputs"] = len(paths)
    item["cell"] = [cw, ch]
    item["labels"] = [chr(ord("A") + i) if i < 26 else f"#{i + 1}"
                      for i in range(len(paths))] if args.label else []
    return ok_envelope("montage", [item], warnings=warnings)


def cmd_tone(args) -> int:
    """C8:统一色调 / 双色调 / 饱和度 / 温度(materials.md 色彩纪律的工具化)。"""
    results = []
    for src in input_expand(args):
        try:
            from PIL import ImageOps
            import numpy as np
            img = _open(src).convert("RGB")
            before = src.stat().st_size
            if args.duotone:
                c1 = parse_color(args.duotone.split(",")[0])[:3]
                c2 = parse_color(args.duotone.split(",")[1])[:3]
                g = ImageOps.grayscale(img)
                lut = []
                for ch in range(3):
                    lut += [round(c1[ch] + (c2[ch] - c1[ch]) * v / 255) for v in range(256)]
                img = g.convert("RGB").point(lut)
            if args.saturation and abs(args.saturation - 1) > 1e-3:
                from PIL import ImageEnhance
                img = ImageEnhance.Color(img).enhance(float(args.saturation))
            if args.temp and int(args.temp) != 0:
                arr = np.asarray(img).astype(float)
                t = int(args.temp) / 100 * 30
                arr[:, :, 0] = arr[:, :, 0].clip(0, 255) + t
                arr[:, :, 2] = arr[:, :, 2].clip(0, 255) - t
                img = __import__("PIL.Image", fromlist=["Image"]).fromarray(arr.clip(0, 255).astype("uint8"))
            if args.autocontrast is not None:
                img = ImageOps.autocontrast(img, cutoff=int(args.autocontrast))
            if args.equalize:
                img = ImageOps.equalize(img)
            if args.gamma and abs(args.gamma - 1) > 1e-3:
                import numpy as np
                arr = (np.asarray(img).astype(float) / 255) ** (1 / float(args.gamma)) * 255
                img = __import__("PIL.Image", fromlist=["Image"]).fromarray(arr.clip(0, 255).astype("uint8"))
            fmt = (src.suffix.lstrip('.') or "png").lower()
            fmt = {"jpg": "jpeg"}.get(fmt, fmt)
            ext = "jpg" if fmt == "jpeg" else fmt
            out = args.out or out_path_for(src, args, "tone", ext)
            data, meta = encode_image(img, fmt, 92)
            out.write_bytes(data)
            results.append(result_item(src, out, before, data, engine=meta["engine"]))
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            results.append(result_item(src, None, 0, None, error=f"{type(exc).__name__}: {exc}"))
    return ok_envelope("tone", results)
