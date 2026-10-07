"""Render a pitched 2.5D/3D map (raster basemap + OSM building extrusions) to PNG.

Pipeline (all local, reproducible; network only needed for first tile/data download):
  local HTTP server -> MapLibre GL v5.9.0 (vendored, no CDN)
                      -> AMap raster tiles from local cache (GCJ-02 grid)
                      -> building GeoJSON fill-extrusion (OSM heights, GCJ-02)
                      -> HTML overlay pins/labels (Chinese, project()-positioned)
                      -> headless browser screenshot (Playwright;VB_BROWSER_PATH >
                         artboard _paths 的 Chrome/Edge > Playwright 自带 chromium)

Zoom model: MapLibre camera zoom cz draws a 256px raster tile at 512*2^(cz-z) px.
For crisp 1:1 pixels at deviceScaleFactor=2 use camera zoom = raster_z - 1.

  python scripts/render_3d.py --center 23.1291,113.2644 --buildings <base>_buildings_gcj02.geojson ...

依赖:`<base>_buildings_gcj02.geojson` 由 fetch_osm_data.py 产出(不随技能附带)。
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from _map_common import TILE_CACHE, http_get, launch_kwargs, repo_url, serve_dir, write_tmp_page  # noqa: F401
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
  #attr { position:absolute; right:8px; bottom:6px; font:11px/1 Arial, sans-serif; color:rgba(255,255,255,.85);
          background:rgba(0,0,0,.45); padding:3px 8px; border-radius:4px; z-index:9; }
</style></head>
<body><div id="map"></div>__ATTR__
<script>
const POINTS = __POINTS__;
const map = new maplibregl.Map({
  container: 'map',
  antialias: true,
  attributionControl: false,
  center: [__C_LON__, __C_LAT__],
  zoom: __CAMERA_ZOOM__, pitch: __PITCH__, bearing: __BEARING__,
  style: {
    version: 8,
    sources: {
      amap: { type:'raster', tiles:['__TILE_URL__'], tileSize:256, maxzoom:__SRC_MAXZOOM__ },
      bld:  { type:'geojson', data:'__BLD_URL__' }
    },
    layers: [
      { id:'amap', type:'raster', source:'amap' },
      { id:'bld', type:'fill-extrusion', source:'bld',
        paint: {
          'fill-extrusion-height': ['get','height'],
          'fill-extrusion-base': 0,
          'fill-extrusion-color': ['interpolate',['linear'],['get','height'],
              10,  '#3d4a63',  50, '#46608f',  120, '#5a7fb8',  250, '#7fa8d8',  400, '#b8d4f2'],
          'fill-extrusion-opacity': 0.96
        } }
    ]
  }
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
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--center", required=True, help="lat,lon (WGS-84)")
    ap.add_argument("--zoom", type=int, default=15, help="raster tile zoom to precache/serve")
    ap.add_argument("--camera-zoom", type=float, default=14.0)
    ap.add_argument("--pitch", type=float, default=60)
    ap.add_argument("--bearing", type=float, default=-25)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--buildings", default="work/geo/cbd-gz_buildings_gcj02.geojson")
    ap.add_argument("--points", default="assets/map/points.guangzhou.json")
    ap.add_argument("--accent", default="#E8462E")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-attr", action="store_true", help="omit in-image attribution line (poster footer carries it)")
    args = ap.parse_args()

    bld_path = os.path.join(ROOT, args.buildings)
    if not os.path.isfile(bld_path):
        raise SystemExit(f"[X] 建筑图层不存在: {bld_path}\n"
                         f"    先跑 fetch_osm_data.py --bbox <s,w,n,e> --out work/geo/cbd-gz,\n"
                         f"    再用 --buildings work/geo/cbd-gz_buildings_gcj02.geojson")

    lat, lon = [float(v) for v in args.center.split(",")]
    gcj_lat, gcj_lon = to_datum(lat, lon, "gcj")

    points = json.load(open(os.path.join(ROOT, args.points), encoding="utf-8")) if args.points else []
    for p in points:
        p["lat"], p["lon"] = to_datum(p["lat"], p["lon"], "gcj")

    # precache raster tile window for zooms maplibre may request (camera cz -> level cz-1..cz+1)
    from _map_mercator import deg2num
    from map_tiles import fetch_tile
    cx, cy = deg2num(gcj_lat, gcj_lon, args.zoom)
    # 只预算「正视角」平面窗口:俯仰(pitch)+ bearing 会把视野拉到窗口之外,旧实现
    # 靠放大窗口猜,既猜不准(实测 pitch63/bearing-28 北侧仍缺 2 排 → 底图留洞)又
    # 白下几千张瓦片。现在由本地服务**按需补抓**(`_map_common.serve_dir`,抓到的
    # 瓦片同样落 work/tiles/cache → 同视角可离线复跑)。
    span = int(args.width / 256) + 4
    vspan = int(args.height / 256) + 4
    all_jobs = []
    for z in {max(3, args.zoom - 2), max(3, args.zoom - 1), args.zoom}:
        sx, sy = span * (2 ** (args.zoom - z)), vspan * (2 ** (args.zoom - z))
        x0, y0 = int(cx - sx / 2), int(cy - sy / 2)
        x1, y1 = int(cx + sx / 2), int(cy + sy / 2)
        all_jobs += [("amap", z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    print(f"precaching {len(all_jobs)} tiles (z{args.zoom-2}-{args.zoom}) ...")
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda j: fetch_tile(*j), all_jobs))

    pts_json = json.dumps([{"name": p["name"], "lon": p["lon"], "lat": p["lat"]} for p in points],
                          ensure_ascii=False)
    attr_html = '' if args.no_attr else '<div id="attr">© AMap · 建筑数据 © OpenStreetMap 贡献者 (ODbL) · MapLibre GL</div>'
    tpl = HTML.replace("__ATTR__", attr_html)
    html = (tpl
            .replace("__W__", str(args.width)).replace("__H__", str(args.height))
            .replace("__ACCENT__", args.accent)
            .replace("__C_LAT__", str(gcj_lat)).replace("__C_LON__", str(gcj_lon))
            .replace("__CAMERA_ZOOM__", str(args.camera_zoom))
            .replace("__PITCH__", str(args.pitch)).replace("__BEARING__", str(args.bearing))
            .replace("__TILE_URL__", repo_url(TILE_CACHE) + "/amap/{z}/{x}/{y}.png")
            .replace("__SRC_MAXZOOM__", str(args.zoom))
            .replace("__BLD_URL__", repo_url(bld_path))
            .replace("__POINTS__", pts_json))

    render_page = write_tmp_page("_render_3d.html", html)

    srv = serve_dir(ROOT)
    port = srv.server_address[1]
    url = f"http://127.0.0.1:{port}/" + os.path.relpath(render_page, ROOT).replace("\\", "/")
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
        page.wait_for_timeout(1500)  # settle compositing
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        page.screenshot(path=args.out)
        if errors:
            print("CONSOLE ERRORS:")
            for e in errors[:10]:
                print("  ", e[:300])
        browser.close()
    srv.shutdown()
    from PIL import Image
    im = Image.open(args.out)
    print(f"saved {args.out} {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main()
