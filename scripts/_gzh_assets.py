"""公众号封面 · 素材层(v1.27):AI 生图插画/图案 → 自动抠图 → 按版式落位 → 内联。

为什么是"纯 PIL 平面底抠图"而不是 rembg:
  1) 全自动链路不能联网下载模型(rembg 首次运行要拉 ONNX,离线/新机器直接失败);
  2) GPT 出的插画/图案天然是**纯色平底**,边缘分离靠"边界连通 + 容差"就够,
     不需要分割网络;真需要照片级抠图时再用 scripts/cutout.py(rembg 可选增强);
  3) 确定性:同一张图同一结果,回归测试可复现。

对外契约(gzh_cover.py asset-attach 调用):
  cutout(path)        → dict(ok, error, hint, image=RGBA, stats)
  trim(image, pad)    → 去掉透明留白
  to_data_uri(image)  → PNG data URI(超预算自动降采样)
  pick_slot(layout, page, want, img_w, img_h, scale) → dict(slot, rect, box, opacity, mode)
  SLOTS / PROTECTED / ASSET_MAX_COUNT

坐标系 = 封面画布像素(主封 900×383,次条 383×383),与 check 的几何断言同一坐标系。
"""

import base64
import io
import os
from collections import deque

try:
    from PIL import Image, ImageFilter
except Exception:  # noqa: BLE001 — Pillow 是硬依赖,缺失时由调用方报错
    Image = None
    ImageFilter = None

# whole 槽位是满幅氛围层,不压到 25% 以下文字就读不出来,所以上限写死。
WHOLE_MAX_OPACITY = 0.25

ASSET_MAX_COUNT = 2                 # 一页最多两个素材层(第三个就是噪音)
ASSET_MAX_BYTES = 2_600_000         # 与背景图同预算:data URI 内联不失控
ASSET_MAX_WIDTH = 1200              # 2x 画布下 600 宽的素材已够,再大只是字节
FLAT_SPREAD_MAX = 30               # 边框色散超过它 → 判定"非平底",拒绝自动抠
FLAT_TOL_MIN = 24                   # 容差下限(JPEG 噪点)
MIN_SUBJECT_RATIO = 0.08           # 抠完主体少于画布 8% → 判定主体被吃
DEFAULT_WATERMARK_OPACITY = 0.16

# 版式安全区(与 _gzh_layouts.py 的 .safe/.band/.panel/.plate 几何一一对应)。
# 素材不许压字:非 whole 槽位与 protected 的重叠必须为 0(由 check 断言)。
PROTECTED = {
    "center-band":   {"main": (40, 96, 820, 232),  "sub": (17, 24, 349, 335)},
    "band-editorial": {"main": (84, 30, 636, 323), "sub": (44, 22, 295, 339)},
    "stack-cards":   {"main": (258, 48, 384, 287), "sub": (28, 28, 327, 327)},
    "giant-caps":    {"main": (40, 30, 820, 323),  "sub": (24, 24, 335, 335)},
    "kraft-note":    {"main": (262, 26, 348, 331), "sub": (38, 26, 307, 331)},
    "plate-page":    {"main": (272, 26, 352, 331), "sub": (34, 26, 206, 331)},
}

# 槽位 = (x, y, w, h) 画布像素;whole 是"整幅氛围层"(文字之下,允许与文字区重叠)。
SLOTS = {
    "center-band": {
        "main": {"default": "whole",
                 "slots": {"top": (40, 8, 820, 80), "bottom": (40, 336, 820, 39),
                           "whole": (0, 0, 900, 383)}},
        "sub": {"default": "whole", "slots": {"whole": (0, 0, 383, 383)}},
    },
    "band-editorial": {
        "main": {"default": "right",
                 "slots": {"right": (728, 8, 164, 367), "whole": (0, 0, 900, 383)}},
        "sub": {"default": "whole", "slots": {"whole": (0, 0, 383, 383)}},
    },
    "stack-cards": {
        "main": {"default": "right",
                 "slots": {"left": (10, 20, 240, 343), "right": (650, 20, 240, 343),
                           "whole": (0, 0, 900, 383)}},
        "sub": {"default": "whole", "slots": {"whole": (0, 0, 383, 383)}},
    },
    "giant-caps": {
        # 巨字版主标横跨整幅(保护 40–860 × 30–353),没有能放实体物件的空地,
        # 所以只给 whole 氛围层;想放实体物件请换 band-editorial / kraft-note。
        "main": {"default": "whole", "slots": {"whole": (0, 0, 900, 383)}},
        "sub": {"default": "whole", "slots": {"whole": (0, 0, 383, 383)}},
    },
    "kraft-note": {
        "main": {"default": "left",
                 "slots": {"left": (8, 28, 240, 327), "right": (618, 132, 272, 240),
                           "whole": (0, 0, 900, 383)}},
        "sub": {"default": "whole", "slots": {"whole": (0, 0, 383, 383)}},
    },
    "plate-page": {
        "main": {"default": "plate",
                 "slots": {"plate": (672, 0, 228, 383), "whole": (0, 0, 900, 383)}},
        "sub": {"default": "plate",
                "slots": {"plate": (260, 0, 123, 383), "whole": (0, 0, 383, 383)}},
    },
}


def open_rgba(path):
    if Image is None:
        return None, "NO_PILLOW"
    try:
        with Image.open(os.path.abspath(os.path.expanduser(path))) as raw:
            return raw.convert("RGBA"), ""
    except Exception:  # noqa: BLE001
        return None, "ASSET_DECODE_FAILED"


def _border_samples(im):
    w, h = im.size
    px = im.load()
    pts = []
    for x in range(0, w, max(1, w // 200)):
        pts.append(px[x, 0])
        pts.append(px[x, h - 1])
    for y in range(0, h, max(1, h // 200)):
        pts.append(px[0, y])
        pts.append(px[w - 1, y])
    return pts


def _median_color(samples):
    chans = [[s[i] for s in samples] for i in range(3)]
    for c in chans:
        c.sort()
    mid = len(samples) // 2
    return tuple(c[mid] for c in chans)


def _dist(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))


def _spread(samples, base):
    ds = sorted(_dist(s, base) for s in samples)
    return ds[int(len(ds) * 0.9)]


def cutout(path):
    """平底自动抠图:边界连通 + 容差,BFS 四连通。

    返回 ok=False 时带 error/hint,调用方可据此降级为 --mode rect(矩形贴)或让用户重出图。
    """
    im, err = open_rgba(path)
    if im is None:
        return {"ok": False, "error": err, "hint": "需要可解码的 PNG/JPEG/WebP"}
    if im.size[0] * im.size[1] > 12_000_000:
        im = im.resize((int(im.width * 0.5), int(im.height * 0.5)), Image.LANCZOS)
    w, h = im.size
    if im.getchannel("A").getextrema()[0] < 250:
        # 生图工具已经给了 alpha(用户自己抠好/PNG 导出)→ 直接沿用
        alpha = im.getchannel("A")
        ratio = sum(1 for v in alpha.getdata() if v < 24) / float(w * h)
        return {"ok": True, "image": im, "stats": {"engine": "existing-alpha",
                                                   "transparent_ratio": round(ratio, 3)}}
    samples = _border_samples(im)
    base = _median_color(samples)
    spread = _spread(samples, base)
    if spread > FLAT_SPREAD_MAX:
        return {"ok": False, "error": "ASSET_BG_NOT_FLAT",
                "hint": ("边框色散 %d(上限 %d):这不是纯色平底图。让 GPT 出"
                         "「纯白底 #FFFFFF、无阴影」的单体插画,或改用 --mode rect 直接矩形贴图"
                         % (spread, FLAT_SPREAD_MAX)),
                "stats": {"bg": base, "spread": spread}}
    tol = max(FLAT_TOL_MIN, spread + 12)
    px = im.load()
    total = w * h
    bgmask = bytearray(total)
    queue = deque()
    for x in range(w):
        for y in (0, h - 1):
            if not bgmask[y * w + x] and _dist(px[x, y], base) <= tol:
                bgmask[y * w + x] = 1
                queue.append(y * w + x)
    for y in range(h):
        for x in (0, w - 1):
            if not bgmask[y * w + x] and _dist(px[x, y], base) <= tol:
                bgmask[y * w + x] = 1
                queue.append(y * w + x)
    while queue:
        idx = queue.popleft()
        x, y = idx % w, idx // w
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                nidx = ny * w + nx
                if not bgmask[nidx] and _dist(px[nx, ny], base) <= tol:
                    bgmask[nidx] = 1
                    queue.append(nidx)
    alpha = bytearray(b"\xff" * total)
    for i in range(total):
        if bgmask[i]:
            alpha[i] = 0
    kept = total - sum(bgmask)
    ratio = kept / float(total)
    if ratio < MIN_SUBJECT_RATIO:
        return {"ok": False, "error": "ASSET_SUBJECT_LOST",
                "hint": ("主体只剩 %.0f%%(阈值 %.0f%%):主体触边被当底色吃掉了。"
                         "让 GPT 四周留 8%% 白边重出,或改用 --mode rect 走矩形贴图"
                         % (ratio * 100, MIN_SUBJECT_RATIO * 100)),
                "stats": {"bg": base, "tol": tol, "kept_ratio": round(ratio, 3)}}
    out = im.copy()
    out.putalpha(Image.frombytes("L", (w, h), bytes(alpha)))
    # 去残边 + 羽化:1px 腐蚀收紧,再 0.8px 高斯,避免白边/黑边
    a = out.getchannel("A").filter(ImageFilter.MinFilter(3))
    a = a.filter(ImageFilter.GaussianBlur(0.8))
    out.putalpha(a)
    return {"ok": True, "image": out,
            "stats": {"engine": "flat-bfs", "bg": base, "tol": tol,
                      "kept_ratio": round(ratio, 3)}}


def trim(im, pad=8):
    """按 alpha 裁掉四周留白,保留 pad 像素呼吸位。"""
    if Image is None:
        return im
    bbox = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if not bbox:
        return im
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(im.width, x1 + pad)
    y1 = min(im.height, y1 + pad)
    return im.crop((x0, y0, x1, y1))


def to_data_uri(im):
    """RGBA → PNG data URI;超预算时按档降采样,仍超则返回错误。"""
    if Image is None:
        return None, "NO_PILLOW"
    work = im
    for maxw in (ASSET_MAX_WIDTH, 1000, 860, 700, 560):
        if work.width > maxw:
            work = im.resize((maxw, max(1, round(im.height * maxw / im.width))),
                             Image.LANCZOS)
        buf = io.BytesIO()
        work.save(buf, "PNG", optimize=True)
        if buf.tell() <= ASSET_MAX_BYTES:
            return ("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"),
                    "")
    return None, "ASSET_TOO_LARGE"


def contain_box(slot, img_w, img_h, scale=1.0, pad=6):
    """把图等比装进槽位(contain),返回画布坐标系里的 (x, y, w, h)。"""
    sx, sy, sw, sh = slot
    inner_w = max(1.0, (sw - 2 * pad) * scale)
    inner_h = max(1.0, (sh - 2 * pad) * scale)
    a = img_w / float(img_h)
    if inner_w / inner_h > a:
        bh = inner_h
        bw = bh * a
    else:
        bw = inner_w
        bh = bw / a
    return (round(sx + (sw - bw) / 2.0, 2), round(sy + (sh - bh) / 2.0, 2),
            round(bw, 2), round(bh, 2))


def overlap_ratio(rect_a, rect_b):
    ax, ay, aw, ah = rect_a
    bx, by, bw, bh = rect_b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    area = max(1.0, aw * ah)
    return inter / area


def pick_slot(layout, page, want, img_w, img_h, scale=1.0):
    """按版式/页面挑槽位:want 为空走该版式默认;非法槽位返回 error。"""
    spec = SLOTS.get(layout) or SLOTS["center-band"]
    page_spec = spec.get(page) or spec["main"]
    slots = page_spec["slots"]
    name = want or page_spec["default"]
    if name not in slots:
        return {"ok": False, "error": "BAD_ASSET_SLOT",
                "hint": ("%s/%s 可用槽位:%s" % (layout, page, ", ".join(sorted(slots)))),
                "available": sorted(slots)}
    rect = slots[name]
    box = contain_box(rect, img_w, img_h, scale)
    return {"ok": True, "slot": name, "rect": rect, "box": box,
            "mode": "watermark" if name == "whole" else "plate",
            "protected": PROTECTED.get(layout, {}).get(page)}


BASE_CSS = """
.poster > .ab-asset { position: absolute; z-index: 0; pointer-events: none;
  object-fit: contain; object-position: center; }
.poster > .ab-asset--pattern { background-repeat: repeat; background-position: top left; }
"""


def asset_css(box, opacity, mode, pattern_tile=0, idx=1):
    """为单页生成素材层规则(画布像素,绝对定位)。

    选择器带 data-asset 序号:一页两个素材时,后一个不能吃前一个的定位。
    """
    sel = '.poster > .ab-asset[data-asset="%d"]' % idx
    if mode == "pattern":
        return ("%s { inset: 0; width: auto; height: auto; opacity: %s;"
                " background-size: %dpx auto; }" % (sel, round(opacity, 3), pattern_tile))
    x, y, w, h = box
    return ("%s { left: %spx; top: %spx; width: %spx; height: %spx; opacity: %s; }"
            % (sel, x, y, w, h, round(opacity, 3)))


def img_tag(data_uri, mode="cutout", slot="right", idx=1):
    """素材标签:img 走位图,div 走图案平铺。"""
    if mode == "pattern":
        return ('<div class="ab-asset ab-asset--pattern" data-asset="%d" data-asset-mode="pattern"'
                ' data-asset-slot="%s" aria-hidden="true"></div>' % (idx, slot))
    return ('<img class="ab-asset" data-asset="%d" data-asset-mode="%s" data-asset-slot="%s"'
            ' alt="" aria-hidden="true" src="%s">' % (idx, mode, slot, data_uri))


ILLUSTRATION_PROMPT = """Generate ONE standalone illustration asset for a Chinese poster — not a poster, not a layout, just one object.
- Canvas 1024x1024.
- SUBJECT: {subject}
- STYLE: {style}
- PALETTE: {palette}
- Flat pure white background (#FFFFFF), no gradient, no paper texture, no shadow on the ground.
- Subject isolated, centered, occupying 70-80% of the canvas, at least 8% white margin on every side (nothing touches the edge).
- Crisp clean silhouette edges — hard boundary between subject and white background, no feathering, no outline glow, no semi-transparent haze.
- Optional soft inner shading only; no drop shadow, no reflection, no floor.
- NEGATIVE: text, letters, Chinese characters, numbers, logo, watermark, frame, border, background scenery, multiple objects, collage, mockup, screenshot, UI, 3D glossy render.
This image will be auto cut out on a flat-color background, so keep the white truly white and the edges unambiguous."""

PATTERN_PROMPT = """Generate ONE seamless repeating decorative pattern tile.
- Canvas 1024x1024, tileable on all four edges (motifs crossing the edge must continue on the opposite side).
- MOTIF: {subject}
- STYLE: {style}
- PALETTE: {palette}
- Even density, no single focal point, no gradients, flat vector-like shapes with clean edges.
- Background: flat {bg} so it composes over the poster without a white box.
- NEGATIVE: text, letters, logo, watermark, frame, border, vignette, perspective, drop shadow, one-off hero element.
Output the tile only — it will be repeated as a texture."""


def illustration_prompts(theme, subject="a single symbolic object (produce / device / tool)", style="flat vector illustration with subtle grain"):
    t = theme or {}
    bg = t.get("bg", "#0f1b3d")
    palette = "%s base, %s main, %s accent" % (bg, t.get("ink", "#f5f7ff"), t.get("accent", "#3b82f6"))
    return {
        "illustration": ILLUSTRATION_PROMPT.format(subject=subject, style=style, palette=palette),
        "pattern": PATTERN_PROMPT.format(subject=subject, style=style, palette=palette, bg=bg),
    }
