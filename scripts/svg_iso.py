"""GeoJSON vector layers -> axonometric 2.5D SVG (buildings extruded, themeable).

Same element-per-path + CSS-theme architecture as svg_map.py, but the camera is a
tilted orthographic view: ground is rotated by --bearing and squashed by cos(pitch);
buildings are extruded by their real OSM heights (painter's algorithm, back->front;
walls culled by outward-normal test). Pure standard library.

  python scripts/svg_iso.py --base work/geo/cbd-gz --bbox 23.1055,113.3120,23.1300,113.3350 \
      --width 1600 --bearing -24 --pitch 55 --theme dark-tech --out assets/iso-cbd.svg
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from _map_mercator import world_px, from_datum
from svg_map import THEME_CSS, bucket_cls, ROAD_ORDER, esc

ISO_CSS = """
  svg { --bld-wall:#161d31; --bld-wall2:#202a45; --bld-top-stroke:#2b3860; }
  svg[data-theme="blueprint"] { --bld-wall:#0a2f52; --bld-wall2:#1a4a80; --bld-top-stroke:#3f7fb8; }
  svg[data-theme="paper"]     { --bld-wall:#c2b190; --bld-wall2:#d4c6a8; --bld-top-stroke:#a89a78; }
  svg[data-theme="mono"]      { --bld-wall:#b0b0b0; --bld-wall2:#c8c8c8; --bld-top-stroke:#9a9a9a; }
  .bg-rect { fill: var(--bg); }
  #green path { fill: var(--green); }
  #water path.ply { fill: var(--water); }
  #water path.wline { fill: none; stroke: var(--water); stroke-linecap: round; }
  #rail path { fill: none; stroke: var(--rail); stroke-width: 2; stroke-dasharray: 8 5; }
  #roads path { fill: none; stroke-linecap: round; stroke-linejoin: round; }
  .hw-service      { stroke: var(--r-service); stroke-width: 1.4; }
  .hw-living_street, .hw-pedestrian, .hw-unclassified, .hw-residential { stroke: var(--r-residential); stroke-width: 2.2; }
  .hw-tertiary     { stroke: var(--r-tertiary);  stroke-width: 3; }
  .hw-secondary    { stroke: var(--r-secondary); stroke-width: 3.8; }
  .hw-primary      { stroke: var(--r-primary);   stroke-width: 4.8; }
  .hw-trunk        { stroke: var(--r-trunk);     stroke-width: 5.8; }
  .hw-motorway     { stroke: var(--r-motorway);  stroke-width: 7; }
  #buildings .wall { stroke: none; }
  .wall.wa { fill: var(--bld-wall); }
  .wall.wb { fill: var(--bld-wall2); }
  #buildings .top  { stroke: var(--bld-top-stroke); stroke-width: .7; stroke-linejoin: round; }
  .bld-l { fill: var(--bld-l); } .bld-m { fill: var(--bld-m); }
  .bld-t { fill: var(--bld-t); } .bld-x { fill: var(--bld-x); }
  #labels text { fill: var(--label); font: 700 16px 'Source Han Sans SC','Microsoft YaHei',sans-serif;
    paint-order: stroke; stroke: var(--label-halo); stroke-width: 3.5; text-anchor: middle; }
  #labels circle { fill: var(--r-motorway); stroke: var(--bg); stroke-width: 2; }
  svg.no-green #green, svg.no-water #water, svg.no-rail #rail,
  svg.no-roads #roads, svg.no-buildings #buildings, svg.no-labels #labels { display: none; }
"""


class Iso:
    """World-px -> rotated orthographic screen coords, with height in meters->px."""

    def __init__(self, bbox, width, bearing, pitch, lat0, vex=1.15, pad_ratio=0.03):
        s, w, n, e = bbox
        xa, ya = world_px(n, w, 0)
        xb, yb = world_px(s, e, 0)
        self.ox, self.oy = min(xa, xb), min(ya, yb)
        self.k = width / abs(xb - xa)
        th = math.radians(bearing)
        self.cs, self.sn = math.cos(th), math.sin(th)
        self.cp, self.sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
        mpp = 156543.034 * math.cos(math.radians(lat0))  # meters per world-px at z0
        self.px_per_m = self.k / mpp * vex
        self.pad = pad_ratio * width

    def ground(self, lon, lat):
        x, y = world_px(lat, lon, 0)
        x, y = (x - self.ox) * self.k, (y - self.oy) * self.k
        rx = x * self.cs - y * self.sn
        ry = x * self.sn + y * self.cs
        return rx, ry * self.cp          # screen coords at h=0

    def lift(self, p, h_m):
        return p[0], p[1] - h_m * self.px_per_m * self.sp

    def depth(self, lon, lat):
        x, y = world_px(lat, lon, 0)
        x, y = (x - self.ox) * self.k, (y - self.oy) * self.k
        return x * self.sn + y * self.cs  # larger = closer to viewer


def fmt(pts):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"


def building_svg(coords, h_m, proj):
    """Return svg string: visible wall quads + top face for one building."""
    ring = [proj.ground(lon, lat) for lon, lat in coords]
    # signed area to know orientation (screen y is down => positive area = CW visually)
    area2 = sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
                for i in range(len(ring) - 1))
    for i in range(len(ring) - 1):
        ax, ay = ring[i]
        bx, by = ring[i + 1]
        mx, my = (ax + bx) / 2, (ay + by) / 2
        # two normals of the edge in ground plane
        n1 = (by - ay, -(bx - ax))
        # pick outward: pointing away from centroid-ish (use first vertex as ref)
        ref = ring[0]
        n = n1 if (n1[0] * (mx - ref[0]) + n1[1] * (my - ref[1])) > 0 else (-n1[0], -n1[1])
        if n[1] <= 0:          # faces away from viewer (+y is toward viewer)
            continue
        # two-tone walls: outward-normal x sign picks lit vs shaded face
        # (light from screen-left: normals pointing left = lit)
        tone = "wb" if n[0] > 0 else "wa"
        top_a, top_b = proj.lift((ax, ay), h_m), proj.lift((bx, by), h_m)
        yield f'<polygon class="wall {tone}" points="{ax:.1f},{ay:.1f} {bx:.1f},{by:.1f} {top_b[0]:.1f},{top_b[1]:.1f} {top_a[0]:.1f},{top_a[1]:.1f}"/>'
    top = [proj.lift(p, h_m) for p in ring]
    yield f'<polygon class="top {bucket_cls(h_m)}" points="' + \
          " ".join(f"{x:.1f},{y:.1f}" for x, y in top) + '"/>'


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--bbox", required=True, help="south,west,north,east (WGS-84)")
    ap.add_argument("--width", type=int, default=1600, help="ground width in px")
    ap.add_argument("--bearing", type=float, default=-24)
    ap.add_argument("--pitch", type=float, default=55)
    ap.add_argument("--vex", type=float, default=1.15, help="vertical exaggeration")
    ap.add_argument("--theme", default="dark-tech",
                    choices=["dark-tech", "blueprint", "paper", "mono"])
    ap.add_argument("--hide", default="")
    ap.add_argument("--points", help="JSON [{name,lat,lon}]")
    ap.add_argument("--coord", choices=["wgs", "gcj"], default="wgs")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    data = {}
    for layer in ["green", "water", "rail", "roads", "buildings"]:
        p = f"{args.base}_{layer}_wgs84.geojson"
        data[layer] = json.load(open(p, encoding="utf-8"))["features"] if os.path.exists(p) else []

    bbox = [float(v) for v in args.bbox.split(",")]
    lat0 = (bbox[0] + bbox[2]) / 2
    proj = Iso(bbox, args.width, args.bearing, args.pitch, lat0, args.vex)

    # flat layers -> svg fragments with ground screen coords
    flat = {"green": [], "water": [], "rail": [], "roads": []}
    for f in data["green"]:
        flat["green"].append(f'<path d="{fmt([proj.ground(lon, lat) for lon, lat in f["geometry"]["coordinates"][0]])}"/>')
    for f in data["water"]:
        g = f["geometry"]
        if g["type"] == "Polygon":
            flat["water"].append(f'<path class="ply" d="{fmt([proj.ground(lon, lat) for lon, lat in g["coordinates"][0]])}"/>')
        else:
            flat["water"].append(f'<path class="wline" style="stroke-width:{f["properties"].get("width", 10)}" '
                                 f'd="M' + " L".join(f"{x:.1f},{y:.1f}" for x, y in
                                                     (proj.ground(lon, lat) for lon, lat in g["coordinates"])) + '"/>')
    for f in data["rail"]:
        flat["rail"].append('<path d="M' + " L".join(f"{x:.1f},{y:.1f}" for x, y in
                            (proj.ground(lon, lat) for lon, lat in f["geometry"]["coordinates"])) + '"/>')
    for hw in ROAD_ORDER:
        for f in data["roads"]:
            if f["properties"]["class"] != hw:
                continue
            flat["roads"].append(f'<path class="hw-{hw}" d="M' + " L".join(
                f"{x:.1f},{y:.1f}" for x, y in
                (proj.ground(lon, lat) for lon, lat in f["geometry"]["coordinates"])) + '"/>')

    # buildings: sort back -> front by centroid depth
    blist = []
    for i, f in enumerate(data["buildings"]):
        coords = f["geometry"]["coordinates"][0]
        depth = sum(proj.depth(lon, lat) for lon, lat in coords[:-1]) / (len(coords) - 1)
        blist.append((depth, i, coords, f["properties"].get("height", 10)))
    blist.sort(key=lambda t: t[0])
    bld_svg = []
    for _, i, coords, h in blist:
        parts = list(building_svg(coords, h, proj))
        cls = bucket_cls(h)
        bld_svg.append(f'<g id="b-{i}" class="{cls}">' + "".join(parts) + "</g>")

    # extent: ground corners + max height lift
    corners = [proj.ground(lon, lat) for lon, lat in
               [(bbox[1], bbox[0]), (bbox[3], bbox[0]), (bbox[1], bbox[2]), (bbox[3], bbox[2])]]
    hmax = max((h for _, _, _, h in blist), default=20)
    pts = corners + [proj.lift(c, hmax) for c in corners]
    minx = min(p[0] for p in pts) - proj.pad
    miny = min(p[1] for p in pts) - proj.pad
    maxx = max(p[0] for p in pts) + proj.pad
    maxy = max(p[1] for p in pts) + proj.pad
    W, H = int(maxx - minx), int(maxy - miny)

    hide = set(args.hide.split(",")) - {""}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
           f'width="{W}" height="{H}" data-theme="{args.theme}" '
           f'class="{" ".join("no-" + h for h in sorted(hide))}">']
    out.append(f"<style>{THEME_CSS}</style><style>{ISO_CSS}</style>")
    out.append(f'<rect class="bg-rect" x="0" y="0" width="{W}" height="{H}"/>')
    out.append(f'<g transform="translate({-minx:.1f},{-miny:.1f})">')
    for layer in ["green", "water", "rail", "roads"]:
        out.append(f'<g id="{layer}">' + "".join(flat[layer]) + "</g>")
    out.append('<g id="buildings">' + "".join(bld_svg) + "</g>")

    if args.points:
        pts_json = json.load(open(args.points, encoding="utf-8"))
        lab = []
        for p in pts_json:
            lat, lon = p["lat"], p["lon"]
            if args.coord == "gcj":
                lat, lon = from_datum(lat, lon, "gcj")
            gx, gy = proj.ground(lon, lat)
            tx, ty = proj.lift((gx, gy), 24)  # labels float a bit above ground
            lab.append(f'<g class="poi"><circle cx="{gx:.1f}" cy="{gy:.1f}" r="5"/>'
                       f'<text x="{tx:.1f}" y="{ty - 8:.1f}">{esc(p["name"])}</text></g>')
        out.append('<g id="labels">' + "".join(lab) + "</g>")
    out.append("</g></svg>")

    text = "\n".join(out)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    open(args.out, "w", encoding="utf-8").write(text)
    print(f"saved {args.out} ({len(text)//1024} KB, viewBox {W}x{H}, pitch={args.pitch}, "
          f"bearing={args.bearing}, theme={args.theme})")


if __name__ == "__main__":
    main()
