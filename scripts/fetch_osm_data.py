"""Fetch OSM vector layers (buildings/roads/water/green/rail) for a bbox via ONE
Overpass request, split into per-layer GeoJSON files (WGS-84 + GCJ-02).

Supersedes the single-kind fetcher (v1). Verified live 2026-09-23:
overpass-api.de works from this machine; busy responses return HTML -> retry loop.

Outputs, for --out BASE:
  BASE_buildings_wgs84.geojson / _gcj02   (Polygon, props: height, name)
  BASE_roads_wgs84.geojson    / _gcj02   (LineString, props: class, name)
  BASE_rail_wgs84.geojson     / _gcj02   (LineString, props: class)
  BASE_water_wgs84.geojson    / _gcj02   (Polygon + river/canal LineString class=wline)
  BASE_green_wgs84.geojson    / _gcj02   (Polygon, props: kind)
Building height rule: height tag | building:levels*3.2 | 10m default (no fabrication).
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(__file__))
from _map_common import http_post
from _map_mercator import wgs2gcj

UA = {"User-Agent": "artboard-map-studio/0.2 (local asset generation)"}

Q_ALL = """[out:json][timeout:150];
(
 way["building"]({b});
 way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|unclassified|living_street|service|pedestrian|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"]({b});
 way["railway"~"^(rail|tram|light_rail|subway)$"]({b});
 way["natural"="water"]({b});
 way["waterway"~"^(riverbank|river|canal)$"]({b});
 way["leisure"~"^(park|garden|pitch|playground|golf_course)$"]({b});
 way["landuse"~"^(grass|forest|meadow|recreation_ground|village_green|cemetery)$"]({b});
 way["natural"~"^(wood|scrub)$"]({b});
);
out geom qt;"""

ROAD_CLASSES = {"motorway", "trunk", "primary", "secondary", "tertiary", "residential",
                "unclassified", "living_street", "service", "pedestrian"}
GREEN_KINDS = {"park", "garden", "pitch", "playground", "golf_course", "grass", "forest",
               "meadow", "recreation_ground", "village_green", "cemetery", "wood", "scrub"}


def overpass(query, tries=5):
    for i in range(tries):
        try:
            r = http_post("https://overpass-api.de/api/interpreter",
                          data={"data": query}, headers=UA, timeout=150)
            j = r.json()
            if "elements" in j:
                return j["elements"]
            print(f"  try{i}: unexpected payload: {str(j)[:160]}")
        except Exception as e:
            print(f"  try{i}: {type(e).__name__}: {str(e)[:140]}")
        time.sleep(20)
    raise RuntimeError("overpass failed after retries")


def way_height(tags):
    if "height" in tags:
        try:
            return float(str(tags["height"]).replace("m", "").strip())
        except ValueError:
            pass
    if "building:levels" in tags:
        try:
            return float(tags["building:levels"]) * 3.2
        except ValueError:
            pass
    return 10.0


def classify(e):
    """One OSM way -> (layer, feature props) or None."""
    t = e.get("tags", {})
    geom = e.get("geometry") or []
    coords = [[p["lon"], p["lat"]] for p in geom]
    if t.get("building") in ("no", "No"):
        pass
    elif "building" in t:
        if len(coords) < 3:
            return None
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        return "buildings", {"height": way_height(t), "name": t.get("name", "")}, \
               {"type": "Polygon", "coordinates": [coords]}
    if "highway" in t:
        if len(coords) < 2:
            return None
        hw = t["highway"]
        if hw.endswith("_link"):
            hw = hw.split("_")[0]
        ow = 0
        if t.get("oneway") == "yes":
            ow = 1
        elif t.get("oneway") == "-1":
            ow = -1
        return "roads", {"class": hw, "name": t.get("name", ""), "oneway": ow}, \
               {"type": "LineString", "coordinates": coords}
    if "railway" in t:
        if len(coords) < 2:
            return None
        return "rail", {"class": t["railway"]}, \
               {"type": "LineString", "coordinates": coords}
    if t.get("natural") == "water" or t.get("waterway") == "riverbank":
        if len(coords) < 3:
            return None
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        return "water", {"kind": "water"}, {"type": "Polygon", "coordinates": [coords]}
    if t.get("waterway") in ("river", "canal"):
        if len(coords) < 2:
            return None
        return "water", {"kind": "wline", "width": 14 if t["waterway"] == "river" else 8}, \
               {"type": "LineString", "coordinates": coords}
    for key in ("leisure", "landuse", "natural"):
        v = t.get(key)
        if v in GREEN_KINDS:
            if len(coords) < 3:
                return None
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            return "green", {"kind": v}, {"type": "Polygon", "coordinates": [coords]}
    return None


def convert_gcj(fc):
    def c1(lonlat):
        lat, lon = wgs2gcj(lonlat[1], lonlat[0])
        return [lon, lat]
    out = {"type": "FeatureCollection", "features": []}
    for f in fc["features"]:
        g = f["geometry"]
        if g["type"] == "Polygon":
            coords = [[c1(c) for c in ring] for ring in g["coordinates"]]
        else:
            coords = [c1(c) for c in g["coordinates"]]
        out["features"].append({"type": "Feature", "properties": f["properties"],
                                "geometry": {"type": g["type"], "coordinates": coords}})
    return out


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True, help="south,west,north,east (WGS-84)")
    ap.add_argument("--out", required=True, help="output base path (no ext)")
    args = ap.parse_args()
    bbox = ",".join(args.bbox.split(","))

    print(f"fetching ALL layers for {args.bbox} ...")
    els = overpass(Q_ALL.format(b=bbox))
    layers = {}
    for e in els:
        c = classify(e)
        if not c:
            continue
        layer, props, geom = c
        layers.setdefault(layer, []).append(
            {"type": "Feature", "properties": props, "geometry": geom})

    for layer, feats in layers.items():
        fc = {"type": "FeatureCollection", "features": feats}
        wgs_path = f"{args.out}_{layer}_wgs84.geojson"
        gcj_path = f"{args.out}_{layer}_gcj02.geojson"
        os.makedirs(os.path.dirname(os.path.abspath(wgs_path)), exist_ok=True)
        with open(wgs_path, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False)
        with open(gcj_path, "w", encoding="utf-8") as f:
            json.dump(convert_gcj(fc), f, ensure_ascii=False)
        print(f"  {layer:10s} {len(feats):5d} features -> {args.out}_{layer}_*.geojson")
    if "buildings" not in layers:
        print("  WARNING: no buildings in result")
