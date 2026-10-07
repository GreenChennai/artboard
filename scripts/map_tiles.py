"""Stitch a flat map PNG from XYZ raster tiles — artboard map asset generator.

Reproducible (verified 2026-09-23 on this machine, CN network):
  --style amap   AMap street tiles (webrd0{1-4}.is.autonavi.com, style=8, GCJ-02,
                 Chinese labels, roads/POIs visible). scale=2 = denser retina tiles.
  --style amap-sat  AMap satellite (webst0{1-4}, style=6, GCJ-02)

  Input coords are WGS-84 by default (--coord gcj to feed AMap-picked coords);
  WGS-84 → GCJ-02 由 `_map_mercator` 本地实现(不再依赖 pip 包 eviltransform)。

Examples:
  python scripts/map_tiles.py --lat 23.1291 --lon 113.2644 --zoom 12 \
      --width 1600 --height 1200 --style amap --scale 2 --out assets/gz.png
  python scripts/map_tiles.py --bbox 23.10,113.23,23.16,113.38 --zoom 14 ...

瓦片缓存落 `<技能根>/work/tiles/cache/`(已进 .gitignore):首跑联网,之后离线可复跑。
"""
import argparse, json, os, sys, math
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
from _map_common import TILE_CACHE as CACHE, http_get
from _map_mercator import TILE, deg2num, num2deg, world_px, px_to_latlon, meters_per_pixel, to_datum, from_datum

UA = {"User-Agent": "artboard-map-studio/0.1 (local asset generation)"}

STYLES = {
    # datum: coordinate system the tile grid is indexed in
    "amap":     {"datum": "gcj",
                 "urls": [f"https://webrd0{i}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=2&style=8&x={{x}}&y={{y}}&z={{z}}" for i in range(1, 5)],
                 "ext": "png", "attribution": "© AMap · data © OpenStreetMap (ODbL)"},
    "amap-sat": {"datum": "gcj",
                 "urls": [f"https://webst0{i}.is.autonavi.com/appmaptile?style=6&x={{x}}&y={{y}}&z={{z}}" for i in range(1, 5)],
                 "ext": "jpg", "attribution": "© AMap satellite"},
}


def tile_path(style, z, x, y):
    return os.path.join(CACHE, style, str(z), str(x), f"{y}.{STYLES[style]['ext']}")


def fetch_tile(style, z, x, y):
    p = tile_path(style, z, x, y)
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return p
    url = STYLES[style]["urls"][(x + y) % len(STYLES[style]["urls"])].format(x=x, y=y, z=z)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    r = http_get(url, headers=UA, timeout=25)
    if r.status_code != 200 or len(r.content) < 100:
        raise RuntimeError(f"tile {z}/{x}/{y} -> HTTP {r.status_code} ({len(r.content)}B)")
    tmp = p + ".part"
    with open(tmp, "wb") as f:
        f.write(r.content)
    os.replace(tmp, p)
    return p


def _rgb(path):
    """瓦片统一转 RGB。调色板 PNG 带 tRNS 时直接 convert("RGB") 会触发 Pillow 警告,
    先过一层 RGBA 再降位即可(AMap 部分瓦片就是 P 模式)。"""
    im = Image.open(path)
    if im.mode in ("P", "PA"):
        im = im.convert("RGBA")
    return im.convert("RGB")


def stitch(style, z, x0, y0, x1, y1):
    """Download tiles [x0..x1]x[y0..y1] (inclusive) and return stitched PIL image."""
    w, h = (x1 - x0 + 1), (y1 - y0 + 1)
    img = Image.new("RGB", (w * TILE, h * TILE), (24, 26, 32))
    jobs = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        paths = list(ex.map(lambda j: fetch_tile(style, z, j[0], j[1]), jobs))
    for (x, y), p in zip(jobs, paths):
        img.paste(_rgb(p), ((x - x0) * TILE, (y - y0) * TILE))
    return img


def draw_marker(img, px, py, label, color=(230, 57, 70)):
    d = ImageDraw.Draw(img)
    r = 9
    d.ellipse([px - r, py - r * 2, px + r, py], fill=color, outline=(255, 255, 255), width=3)
    d.ellipse([px - 3, py - r * 2 + 6, px + 3, py - 6], fill=(255, 255, 255))
    if label:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
        except OSError:
            font = ImageFont.load_default()
        bb = d.textbbox((0, 0), label, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        lx, ly = px - tw // 2, py - r * 2 - th - 14
        d.rounded_rectangle([lx - 10, ly - 8, lx + tw + 10, ly + th + 8], 8, fill=(255, 255, 255, 235))
        d.text((lx, ly), label, fill=(30, 30, 34), font=font)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--style", choices=STYLES, default="amap")
    ap.add_argument("--zoom", type=int, required=True)
    ap.add_argument("--lat", type=float); ap.add_argument("--lon", type=float)
    ap.add_argument("--bbox", help="south,west,north,east (overrides --lat/--lon)")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=1200)
    ap.add_argument("--coord", choices=["wgs", "gcj"], default="wgs", help="datum of --lat/--lon/--points input")
    ap.add_argument("--points", help="JSON: [{name, lat, lon}] baked as pins")
    ap.add_argument("--out", required=True)
    ap.add_argument("--meta", help="write render metadata json here (for HTML overlay)")
    args = ap.parse_args()

    src = STYLES[args.style]
    datum = src["datum"]

    def to_native(lat, lon):
        """input datum -> tile-source native datum"""
        if args.coord == datum:
            return lat, lon
        if args.coord == "wgs" and datum == "gcj":
            return to_datum(lat, lon, "gcj")
        return from_datum(lat, lon, "gcj")

    if args.bbox:
        s, w, n, e = [float(v) for v in args.bbox.split(",")]
        s2, w2 = to_native(s, w); n2, e2 = to_native(n, e)
        px0, py0 = world_px(n2, w2, args.zoom)   # NW corner
        px1, py1 = world_px(s2, e2, args.zoom)   # SE corner
        cw, ch = px1 - px0, py1 - py0
        cpx, cpy = px0 + cw / 2, py0 + ch / 2
        crop_w, crop_h = int(cw), int(ch)
        # honor --width/--height as minimum canvas, keep bbox aspect if larger
        crop_w, crop_h = max(crop_w, args.width), max(crop_h, args.height)
    else:
        lat, lon = to_native(args.lat, args.lon)
        cpx, cpy = world_px(lat, lon, args.zoom)
        crop_w, crop_h = args.width, args.height

    tx0, ty0 = cpx / TILE, cpy / TILE
    x0, y0 = math.floor(tx0 - crop_w / 2 / TILE), math.floor(ty0 - crop_h / 2 / TILE)
    x1, y1 = math.ceil(tx0 + crop_w / 2 / TILE), math.ceil(ty0 + crop_h / 2 / TILE)
    img = stitch(args.style, args.zoom, x0, y0, x1, y1)

    # crop centered on requested center pixel
    ox, oy = int(round(cpx - x0 * TILE)), int(round(cpy - y0 * TILE))
    W, H = img.size
    left = max(0, min(W - crop_w, ox - crop_w // 2))
    top = max(0, min(H - crop_h, oy - crop_h // 2))
    img = img.crop((left, top, left + crop_w, top + crop_h))

    # markers
    points = []
    if args.points:
        points = json.load(open(args.points, encoding="utf-8"))
    for p in points:
        lat, lon = to_native(p["lat"], p["lon"])
        px, py = world_px(lat, lon, args.zoom)
        px, py = px - x0 * TILE - left, py - y0 * TILE - top
        if 0 <= px < crop_w and 0 <= py < crop_h:
            draw_marker(img, px, py, p.get("name", ""))
        p["px"], p["py"] = px, py

    # attribution (license honesty)
    d = ImageDraw.Draw(img)
    try:
        f_at = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)
    except OSError:
        f_at = ImageFont.load_default()
    att = src["attribution"]
    bb = d.textbbox((0, 0), att, font=f_at)
    d.rectangle([crop_w - (bb[2] - bb[0]) - 14, crop_h - 26, crop_w, crop_h], fill=(255, 255, 255))
    d.text((crop_w - (bb[2] - bb[0]) - 7, crop_h - 23), att, fill=(80, 80, 84), font=f_at)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    img.save(args.out)
    print(f"saved {args.out} {img.size[0]}x{img.size[1]} zoom={args.zoom} style={args.style} "
          f"(~{meters_per_pixel(23.1, args.zoom):.1f} m/px @lat23)")
    if args.meta:
        meta = {"style": args.style, "datum": datum, "zoom": args.zoom,
                "crop": [left, top, crop_w, crop_h], "tile_origin": [x0, y0],
                "points": points}
        with open(args.meta, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        print(f"meta  {args.meta}")


if __name__ == "__main__":
    main()
