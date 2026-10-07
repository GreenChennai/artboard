"""Fully vector, theme-driven true-3D render (no raster basemap at all).

Same camera/overlay/screenshot machinery as render_3d.py, but every visual element
comes from OSM GeoJSON layers styled by a theme JSON (assets/map/themes/*.json):
background, green, water (polygon+line), roads by class, rail, and buildings
extruded with a height color ramp. Switching theme = switching one JSON.

  python scripts/render_3d_vec.py --center 23.1145,113.3255 --camera-zoom 14.6 \
      --pitch 63 --bearing -28 --theme assets/map/themes/dark-tech.json \
      --base work/geo/cbd-gz --points assets/map/points.cbd.json --out assets/v3d-darktech.png

Data files (GCJ-02, aligned with camera space): BASE_{layer}_gcj02.geojson.
依赖:数据由 fetch_osm_data.py 产出;截图浏览器 = VB_BROWSER_PATH > artboard _paths
(Chrome/Edge)> Playwright 自带 chromium。
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from _map_common import launch_kwargs, repo_url, serve_dir, write_tmp_page
from _map_mercator import to_datum

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="/assets/vendor/maplibre/maplibre-gl.css">
<script src="/assets/vendor/maplibre/maplibre-gl.js"></script>
<style>
  html,body,#map { margin:0; padding:0; width:__W__px; height:__H__px; overflow:hidden; }
  #map { position:absolute; }
  .pin { position:absolute; transform:translate(-50%,-100%); display:flex; flex-direction:column; align-items:center; pointer-events:none; }
  .pin .card { background:__ACCENT__; color:#fff; font:600 15px/1.25 "Microsoft YaHei",sans-serif;
               padding:6px 12px; border-radius:8px; white-space:nowrap; box-shadow:0 4px 14px rgba(0,0,0,.35);
               border:1.5px solid rgba(255,255,255,.85); }
  .pin .stem { width:2.5px; height:16px; background:rgba(255,255,255,.9); }
  .pin .dot { width:11px; height:11px; border-radius:50%; background:__ACCENT__; border:2.5px solid #fff; margin-top:-2px; box-shadow:0 2px 8px rgba(0,0,0,.4); }
</style></head>
<body><div id="map"></div>
<script>
const POINTS = __POINTS__;
const T = __THEME__;
const ROAD_ORDER = ["service","living_street","pedestrian","unclassified","residential",
                    "tertiary","secondary","primary","trunk","motorway"];

const layers = [
  { id:'bg', type:'background', paint:{ 'background-color': T.bg } },
  { id:'green', type:'fill', source:'green', paint:{ 'fill-color': T.green } },
  { id:'water-ply', type:'fill', source:'water', filter:['==','$type','Polygon'],
    paint:{ 'fill-color': T.water } },
  { id:'water-line', type:'line', source:'water', filter:['==','$type','LineString'],
    layout:{ 'line-cap':'round' },
    paint:{ 'line-color': T.water, 'line-width': ['coalesce',['get','width'],10] } },
];
for (const cls of ROAD_ORDER) {
  if (!T.roads[cls]) continue;
  layers.push({ id:'r-'+cls, type:'line', minzoom:0,
    source:'roads', filter:['==','class',cls],
    paint:{ 'line-color': T.roads[cls][0], 'line-width': T.roads[cls][1],
            'line-opacity': 0.92 } });
}
layers.push({ id:'rail', type:'line', source:'rail',
  paint:{ 'line-color': T.rail[0], 'line-width': T.rail[1], 'line-dasharray': [2,1.6] } });
layers.push({ id:'bld', type:'fill-extrusion', source:'buildings',
  paint:{ 'fill-extrusion-height': ['get','height'],
          'fill-extrusion-base': 0,
          'fill-extrusion-vertical-gradient': true,
          'fill-extrusion-color': ['interpolate',['linear'],['get','height']]
              .concat(T.bld_stops.map((s,i)=>[s, T.bld[i]]).flat()),
          'fill-extrusion-opacity': 0.97 } });

const map = new maplibregl.Map({
  container: 'map',
  antialias: true,
  attributionControl: false,
  center: [__C_LON__, __C_LAT__],
  zoom: __CAMERA_ZOOM__, pitch: __PITCH__, bearing: __BEARING__,
  style: { version: 8,
    sources: {
      buildings: { type:'geojson', data:'__BASE___buildings_gcj02.geojson' },
      roads:     { type:'geojson', data:'__BASE___roads_gcj02.geojson' },
      rail:      { type:'geojson', data:'__BASE___rail_gcj02.geojson' },
      water:     { type:'geojson', data:'__BASE___water_gcj02.geojson' },
      green:     { type:'geojson', data:'__BASE___green_gcj02.geojson' }
    },
    layers: layers }
});
map.on('error', e => { document.title = 'MAP_ERROR: ' + (e && e.error && e.error.message || e); });
map.on('idle', () => {
  const el = document.getElementById('map');
  for (const p of POINTS) {
    const pt = map.project([p.lon, p.lat]);
    const d = document.createElement('div');
    d.className = 'pin';
    d.style.left = pt.x + 'px'; d.style.top = pt.y + 'px';
    d.innerHTML = `<div class="card">${p.name}</div><div class="stem"></div><div class="dot"></div>`;
    el.appendChild(d);
  }
  window.__ready = true;
});
</script></body></html>"""


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--center", required=True, help="lat,lon (WGS-84)")
    ap.add_argument("--camera-zoom", type=float, default=14.6)
    ap.add_argument("--pitch", type=float, default=63)
    ap.add_argument("--bearing", type=float, default=-28)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--base", default="work/geo/cbd-gz")
    ap.add_argument("--theme", default="assets/map/themes/dark-tech.json")
    ap.add_argument("--points", default="assets/map/points.cbd.json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    lat, lon = [float(v) for v in args.center.split(",")]
    gcj_lat, gcj_lon = to_datum(lat, lon, "gcj")
    points = json.load(open(os.path.join(ROOT, args.points), encoding="utf-8"))
    for p in points:
        p["lat"], p["lon"] = to_datum(p["lat"], p["lon"], "gcj")
    theme = json.load(open(os.path.join(ROOT, args.theme), encoding="utf-8"))

    for layer in ("buildings", "roads", "water", "green"):
        p = os.path.join(ROOT, f"{args.base}_{layer}_gcj02.geojson")
        if not os.path.isfile(p):
            raise SystemExit(f"[X] 矢量图层缺失: {p}\n"
                             f"    先跑 fetch_osm_data.py --bbox <s,w,n,e> --out {args.base}")

    base = repo_url(os.path.join(ROOT, args.base))
    html = (HTML
            .replace("__W__", str(args.width)).replace("__H__", str(args.height))
            .replace("__ACCENT__", theme.get("accent", "#E8462E"))
            .replace("__C_LAT__", str(gcj_lat)).replace("__C_LON__", str(gcj_lon))
            .replace("__CAMERA_ZOOM__", str(args.camera_zoom))
            .replace("__PITCH__", str(args.pitch)).replace("__BEARING__", str(args.bearing))
            .replace("__BASE__", base)
            .replace("__THEME__", json.dumps(theme, ensure_ascii=False))
            .replace("__POINTS__", json.dumps(
                [{"name": p["name"], "lon": p["lon"], "lat": p["lat"]} for p in points],
                ensure_ascii=False)))

    page_path = write_tmp_page("_render_3d_vec.html", html)

    srv = serve_dir(ROOT)
    url = f"http://127.0.0.1:{srv.server_address[1]}/" + os.path.relpath(page_path, ROOT).replace("\\", "/")
    print("serving", url)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_kwargs(
            ["--enable-unsafe-swiftshader", "--use-angle=swiftshader",
             "--disable-dev-shm-usage"]))
        page = browser.new_page(viewport={"width": args.width, "height": args.height},
                                device_scale_factor=2)
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        try:
            page.wait_for_function("window.__ready === true", timeout=90000)
        except Exception:
            print("TITLE:", page.title())
            print("ready flag never set")
        page.wait_for_timeout(1500)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        page.screenshot(path=args.out)
        if errors:
            print("CONSOLE ERRORS:")
            for e in errors[:8]:
                print("  ", e[:240])
        browser.close()
    srv.shutdown()
    from PIL import Image
    im = Image.open(args.out)
    print(f"saved {args.out} {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main()
