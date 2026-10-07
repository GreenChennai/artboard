"""Probe reachable basemap tile sources with CORRECT slippy-map tile math.

用途:换底图源/换机器时,**先证伪再动手**——一次性问清"哪些瓦片端点真能出图、
CARTO 无 key 是否带水印、示例 POI 的真实 WGS-84 坐标、GCJ-02 在本地的偏移量"。

  python scripts/probe_tiles.py [--lat 23.1291 --lon 113.2644 --zoom 16]
  python scripts/probe_tiles.py --no-overpass          # 只探瓦片,不查 POI

产出:PNG 落到 `<技能根>/work/tiles/probe/`(已进 .gitignore),POI 落 JSON。
网络请求一律经 `_map_common`(代理口径与其余地图脚本一致)。
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _map_common import PROBE, ensure_dir, http_get, http_post
from _map_mercator import deg2num, wgs2gcj

OUT = PROBE
UA = {"User-Agent": "artboard-map-research/0.1 (local reproducibility test)"}

POI_QUERY = """[out:json][timeout:30];
(
 node["name"="广州塔"](23.0,113.2,23.25,113.5);
 node["name"="广州东站"](23.0,113.1,23.25,113.5);
 node["name"="琶洲"](23.0,113.2,23.2,113.45);
 node["name"="白云山"](23.1,113.2,23.3,113.4);
 node["name"="陈家祠"](23.1,113.2,23.2,113.3);
);
out center 30;"""

ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]


def fetch(out_dir, name, url, note=""):
    try:
        r = http_get(url, headers=UA, timeout=20)
        p = os.path.join(out_dir, name + ".png")
        ok = r.status_code == 200 and r.content[:4] == b"\x89PNG"
        if ok:
            with open(p, "wb") as f:
                f.write(r.content)
        print(f"[{'OK ' if ok else 'BAD'} {r.status_code} {len(r.content):>7}B] {name} {note}")
        return ok
    except Exception as e:
        print(f"[ERR {type(e).__name__}] {name} {note} :: {e}")
        return False


def probe_tiles(lat, lon, zoom, out_dir):
    x, y = deg2num(lat, lon, zoom)
    tx, ty = int(x), int(y)
    print(f"({lat},{lon}) z{zoom} tile: x={tx} y={ty} (frac {x:.2f},{y:.2f})")
    sources = {
        "carto_dark_all": f"https://basemaps.cartocdn.com/dark_all/{zoom}/{tx}/{ty}.png",
        "carto_voyager": f"https://basemaps.cartocdn.com/rastertiles/voyager/{zoom}/{tx}/{ty}.png",
        "esri_darkgray": f"https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{zoom}/{ty}/{tx}",
        "esri_topo": f"https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{zoom}/{ty}/{tx}",
    }
    # AMap 网格按 GCJ-02 索引:先转换,再算瓦片号
    gcj = wgs2gcj(lat, lon)
    off_n = (gcj[0] - lat) * 111320
    off_e = (gcj[1] - lon) * 111320 * math.cos(math.radians(lat))
    print(f"GCJ-02 offset: dLat={gcj[0]-lat:+.6f} dLon={gcj[1]-lon:+.6f}  (~{abs(off_n):.0f}m N, {abs(off_e):.0f}m E)")
    ax, ay = deg2num(gcj[0], gcj[1], zoom)
    for style in (7, 8):
        sources[f"amap_style{style}"] = (
            f"https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=2"
            f"&style={style}&x={int(ax)}&y={int(ay)}&z={zoom}")
    for name, url in sources.items():
        fetch(out_dir, name, url)


def probe_overpass(out_dir):
    for ep in ENDPOINTS:
        try:
            r = http_post(ep, data={"data": POI_QUERY}, headers=UA, timeout=60)
            els = r.json().get("elements", [])
            print(f"\nOVERPASS {ep} -> {r.status_code}, {len(els)} elements")
            for e in els[:12]:
                lat = e.get("lat") or e.get("center", {}).get("lat")
                lon = e.get("lon") or e.get("center", {}).get("lon")
                print(f"  {e.get('tags', {}).get('name')}: {lat:.6f},{lon:.6f} ({e['type']})")
            if els:
                with open(os.path.join(out_dir, "overpass_pois.json"), "w", encoding="utf-8") as f:
                    json.dump(r.json(), f, ensure_ascii=False, indent=1)
                return True
        except Exception as e:
            print(f"OVERPASS {ep} -> {type(e).__name__}: {str(e)[:120]}")
    return False


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, default=23.1291, help="WGS-84 纬度(默认广州人民公园)")
    ap.add_argument("--lon", type=float, default=113.2644)
    ap.add_argument("--zoom", type=int, default=16)
    ap.add_argument("--no-overpass", action="store_true", help="跳过 Overpass POI 查询")
    args = ap.parse_args()

    out_dir = ensure_dir(OUT)
    probe_tiles(args.lat, args.lon, args.zoom, out_dir)
    if not args.no_overpass:
        probe_overpass(out_dir)
    print(f"\nprobe 产物: {out_dir}")


if __name__ == "__main__":
    main()
