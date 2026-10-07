"""GeoJSON vector layers -> fully classed, themeable SVG map (1:1 to OSM data).

Every element is its own <path> with a semantic class (hw-primary, bld-t, water,
green-park, rail, ...) so visibility/color are CSS-controllable per element,
per category, or per layer. Four themes are embedded; switching theme = flipping
the svg's data-theme attribute (no re-render). Verified 2026-09-23.

  python scripts/svg_map.py --base work/geo/cbd-gz --width 1600 \
      --theme dark-tech --points assets/map/points.cbd.json --out assets/svg-cbd.svg

Layers order (bottom->top): green, water, rail, roads(narrow->wide), buildings, labels.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from _map_mercator import world_px, from_datum

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAYERS = ["green", "water", "rail", "roads", "buildings"]  # draw order
ROAD_ORDER = ["service", "living_street", "pedestrian", "unclassified", "residential",
              "tertiary", "secondary", "primary", "trunk", "motorway"]
CASED = {"primary", "trunk", "motorway"}  # classes that get a casing halo

THEME_CSS = """
  :root, svg { --bg:#10131c; --green:#1b3325; --water:#1d3560; --rail:#3a4157;
    --r-service:#2b3145; --r-residential:#333a52; --r-tertiary:#3c4460;
    --r-secondary:#4a547a; --r-primary:#5d6a99; --r-trunk:#6d7cb4; --r-motorway:#7f90cf;
    --bld-l:#232b44; --bld-m:#2c3757; --bld-t:#3a4a78; --bld-x:#5568a8;
    --bld-stroke:#0b0e16; --label:#f2eeff; --label-halo:#10131c; --rc:#0c0f18;
    --bld-shadow:rgba(4,6,12,.5); }
  svg[data-theme="blueprint"] { --bg:#0d3b66; --green:#0f477a; --water:#082c50;
    --rail:#7fa8cf; --r-service:#2f669c; --r-residential:#3a76ae; --r-tertiary:#4a86be;
    --r-secondary:#5f9ad0; --r-primary:#7cb1e2; --r-trunk:#9bc6ef; --r-motorway:#c4e0f9;
    --bld-l:#124471; --bld-m:#1a548a; --bld-t:#2a6aa8; --bld-x:#4d90cf;
    --bld-stroke:#082c50; --label:#eaf4ff; --label-halo:#0d3b66; --rc:#083256;
    --bld-shadow:rgba(3,24,46,.5); }
  svg[data-theme="paper"] { --bg:#f7f2e7; --green:#d8e4c8; --water:#b9d4e0;
    --rail:#8a8072; --r-service:#d9cdb6; --r-residential:#cbbda1; --r-tertiary:#b8a888;
    --r-secondary:#a08f6c; --r-primary:#8a7550; --r-trunk:#6f5a38; --r-motorway:#4c3d22;
    --bld-l:#e4dbc8; --bld-m:#d9cdb4; --bld-t:#cbbd9f; --bld-x:#b9a984;
    --bld-stroke:#b1a488; --label:#3d3423; --label-halo:#f7f2e7; --rc:#fdfaf1;
    --bld-shadow:rgba(122,105,70,.22); }
  svg[data-theme="mono"] { --bg:#ffffff; --green:#efefef; --water:#dcdcdc;
    --rail:#999999; --r-service:#d0d0d0; --r-residential:#c0c0c0; --r-tertiary:#a8a8a8;
    --r-secondary:#909090; --r-primary:#787878; --r-trunk:#606060; --r-motorway:#3f3f3f;
    --bld-l:#e9e9e9; --bld-m:#dedede; --bld-t:#cfcfcf; --bld-x:#bdbdbd;
    --bld-stroke:#c4c4c4; --label:#1a1a1a; --label-halo:#ffffff; --rc:#ffffff;
    --bld-shadow:rgba(0,0,0,.12); }

  .bg-rect { fill: var(--bg); }
  #green path { fill: var(--green); stroke: none; }
  #water path.ply { fill: var(--water); stroke: none; }
  #water path.wline { fill: none; stroke: var(--water); stroke-linecap: round; }
  #rail path { fill: none; stroke: var(--rail); stroke-width: 2.2; stroke-dasharray: 9 5; }
  #roads path { fill: none; stroke-linecap: round; stroke-linejoin: round; }
  #casings path { fill: none; stroke: var(--rc); stroke-linecap: round; stroke-linejoin: round; opacity: .85; }
  #shadows path { fill: var(--bld-shadow); stroke: none; }
  .case-primary   { stroke-width: 7.6; }
  .case-trunk     { stroke-width: 8.8; }
  .case-motorway  { stroke-width: 10; }
  .hw-service      { stroke: var(--r-service); stroke-width: 1.6; }
  .hw-living_street, .hw-pedestrian, .hw-unclassified, .hw-residential { stroke: var(--r-residential); stroke-width: 2.6; }
  .hw-tertiary     { stroke: var(--r-tertiary);  stroke-width: 3.4; }
  .hw-secondary    { stroke: var(--r-secondary); stroke-width: 4.4; }
  .hw-primary      { stroke: var(--r-primary);   stroke-width: 5.6; }
  .hw-trunk        { stroke: var(--r-trunk);     stroke-width: 6.8; }
  .hw-motorway     { stroke: var(--r-motorway);  stroke-width: 8; }
  #buildings path { stroke: var(--bld-stroke); stroke-width: .6; }
  .bld-l { fill: var(--bld-l); } .bld-m { fill: var(--bld-m); }
  .bld-t { fill: var(--bld-t); } .bld-x { fill: var(--bld-x); }
  #labels text { fill: var(--label); font: 700 15px 'Source Han Sans SC','Microsoft YaHei',sans-serif;
    paint-order: stroke; stroke: var(--label-halo); stroke-width: 3.5; text-anchor: middle; }
  #labels circle { fill: var(--r-motorway); stroke: var(--bg); stroke-width: 2; }

  /* layer switches: add class no-green/no-water/... on the svg root */
  svg.no-green #green, svg.no-water #water, svg.no-rail #rail,
  svg.no-roads #roads, svg.no-buildings #buildings, svg.no-labels #labels,
  svg.no-shadows #shadows { display: none; }
"""

BUCKETS = [(24, "bld-l"), (60, "bld-m"), (150, "bld-t")]


def bucket_cls(h):
    for lim, cls in BUCKETS:
        if h < lim:
            return cls
    return "bld-x"


class Proj:
    """Web-mercator world-px -> svg coords, fitted to bbox and width."""

    def __init__(self, bbox, width, pad_ratio=0.02):
        s, w, n, e = bbox
        xa, ya = world_px(n, w, 0)   # NW corner, world px at z0 (256px grid)
        xb, yb = world_px(s, e, 0)   # SE corner
        self.ox, self.oy = min(xa, xb), min(ya, yb)
        bw, bh = abs(xb - xa), abs(yb - ya)
        self.k = width / bw
        self.pad = pad_ratio * width
        self.w = width
        self.h = int(bh * self.k + 2 * self.pad)

    def pt(self, lon, lat):
        x, y = world_px(lat, lon, 0)
        return ((x - self.ox) * self.k + self.pad, (y - self.oy) * self.k + self.pad)


def ring_to_path(coords, proj, close=True):
    pts = [proj.pt(lon, lat) for lon, lat in coords]
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return d + (" Z" if close else "")


def esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="layer base path, e.g. work/geo/cbd-gz")
    ap.add_argument("--bbox", help="override bbox: south,west,north,east (default: data extent)")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--theme", default="dark-tech",
                    choices=["dark-tech", "blueprint", "paper", "mono", "all"],
                    help="'all' = emit one file per theme (single projection pass)")
    ap.add_argument("--hide", default="", help="comma list: green,water,rail,roads,buildings,labels")
    ap.add_argument("--points", help="JSON [{name,lat,lon}] -> labels layer")
    ap.add_argument("--coord", choices=["wgs", "gcj"], default="wgs")
    ap.add_argument("--no-shadow", dest="shadow", action="store_false",
                    help="disable building micro-shadows (default on)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    data = {}
    for layer in LAYERS:
        p = f"{args.base}_{layer}_wgs84.geojson"
        if os.path.exists(p):
            data[layer] = json.load(open(p, encoding="utf-8"))["features"]
        else:
            data[layer] = []
            print(f"  note: {p} missing, layer skipped")

    # bbox: given, or data extent
    if args.bbox:
        bbox = [float(v) for v in args.bbox.split(",")]
    else:
        xs, ys = [], []
        for layer in LAYERS:
            for f in data[layer]:
                g = f["geometry"]
                for ring in (g["coordinates"] if g["type"] == "Polygon" else [g["coordinates"]]):
                    for lon, lat in ring:
                        xs.append(lon); ys.append(lat)
        bbox = [min(ys), min(xs), max(ys), max(xs)]
    proj = Proj(bbox, args.width)

    hide = set(args.hide.split(",")) - {""}
    hide_cls = " ".join("no-" + h for h in sorted(hide))
    body = [f"<title>vector map {args.base}</title>",
            "<style>/*<![CDATA[*/" + THEME_CSS + "/*]]>*/</style>",
            f'<rect class="bg-rect" x="0" y="0" width="{proj.w}" height="{proj.h}"/>']

    body.append('<g id="green">')
    for f in data["green"]:
        kind = f["properties"].get("kind", "park")
        body.append(f'<path class="green-{esc(kind)}" '
                   f'd="{ring_to_path(f["geometry"]["coordinates"][0], proj)}"/>')
    body.append("</g>")

    body.append('<g id="water">')
    for f in data["water"]:
        g = f["geometry"]
        if g["type"] == "Polygon":
            body.append(f'<path class="ply" d="{ring_to_path(g["coordinates"][0], proj)}"/>')
        else:
            body.append(f'<path class="wline" style="stroke-width:{f["properties"].get("width", 10)}" '
                       f'd="{ring_to_path(g["coordinates"], proj, close=False)}"/>')
    body.append("</g>")

    body.append('<g id="rail">')
    for f in data["rail"]:
        body.append(f'<path class="rail-{esc(f["properties"].get("class", "rail"))}" '
                   f'd="{ring_to_path(f["geometry"]["coordinates"], proj, close=False)}"/>')
    body.append("</g>")

    # roads: sort once by class rank (narrow -> wide so wide sits on top)
    order_idx = {c: i for i, c in enumerate(ROAD_ORDER)}
    ordered = sorted(data["roads"], key=lambda f: order_idx.get(f["properties"]["class"], 5))

    # casings: dark/light halo under major roads for depth (drawn beneath fills)
    body.append('<g id="casings">')
    for f in ordered:
        hw = f["properties"]["class"]
        if hw not in CASED:
            continue
        body.append(f'<path class="case-{hw}" '
                   f'd="{ring_to_path(f["geometry"]["coordinates"], proj, close=False)}"/>')
    body.append("</g>")

    body.append('<g id="roads">')
    for f in ordered:
        hw = f["properties"]["class"]
        nm = f' data-name="{esc(f["properties"].get("name", ""))}"' if f["properties"].get("name") else ""
        ow = f' data-ow="{f["properties"].get("oneway", 0)}"'
        body.append(f'<path class="hw-{hw}"{nm}{ow} '
                    f'd="{ring_to_path(f["geometry"]["coordinates"], proj, close=False)}"/>')
    body.append("</g>")

    if args.shadow:
        body.append('<defs><filter id="bsh" x="-8%" y="-8%" width="116%" height="116%">'
                    '<feGaussianBlur stdDeviation="3"/></filter></defs>')
        body.append('<g id="shadows" transform="translate(5 7)" filter="url(#bsh)">')
        for f in data["buildings"]:
            body.append(f'<path class="bld-shadow" '
                        f'd="{ring_to_path(f["geometry"]["coordinates"][0], proj)}"/>')
        body.append("</g>")

    body.append('<g id="buildings">')
    for i, f in enumerate(data["buildings"]):
        h = f["properties"].get("height", 10)
        cls = bucket_cls(h)
        nm = f' data-name="{esc(f["properties"].get("name", ""))}"' if f["properties"].get("name") else ""
        body.append(f'<path id="b-{i}" class="{cls}" data-h="{h:.1f}"{nm} '
                   f'd="{ring_to_path(f["geometry"]["coordinates"][0], proj)}"/>')
    body.append("</g>")

    if args.points:
        pts = json.load(open(args.points, encoding="utf-8"))
        body.append('<g id="labels">')
        for p in pts:
            lat, lon = (p["lat"], p["lon"])
            if args.coord == "gcj":
                from _map_mercator import gcj2wgs
                lat, lon = gcj2wgs(lat, lon)
            x, y = proj.pt(lon, lat)
            body.append(f'<g class="poi"><circle cx="{x:.1f}" cy="{y:.1f}" r="5"/>'
                       f'<text x="{x:.1f}" y="{y - 12:.1f}">{esc(p["name"])}</text></g>')
        body.append("</g>")

    themes = ["dark-tech", "blueprint", "paper", "mono"] if args.theme == "all" else [args.theme]
    for th in themes:
        if len(themes) > 1:
            stem, ext = os.path.splitext(args.out)
            out_path = args.out.replace("{theme}", th) if "{theme}" in args.out else f"{stem}-{th}{ext}"
        else:
            out_path = args.out
        text = chr(10).join(
            [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {proj.w} {proj.h}" '
             f'width="{proj.w}" height="{proj.h}" data-theme="{th}" '
             f'class="{hide_cls}">'] + body + ["</svg>"])
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        open(out_path, "w", encoding="utf-8").write(text)
        print(f"saved {out_path} ({len(text)//1024} KB, viewBox {proj.w}x{proj.h}, "
              f"theme={th}, hidden={sorted(hide) or 'none'})")


if __name__ == "__main__":
    main()
