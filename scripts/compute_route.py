"""Compute real shortest paths on the OSM road network (A*, spatial-hash snap).

v2 optimizations over v1 (both verified live):
  - OD snapping via spatial hash grid (O(1) amortized instead of full node scan)
  - A* search with haversine-based heuristic (admissible, in meters) instead of Dijkstra
  - route polyline simplified with Douglas-Peucker in SVG px space (~1.2px tolerance)
    -> fewer points, smoother animation, smaller embedded JSON

Output identical schema to v1: {"routes":[{name,a,b,pts(px),meters}]}
"""
import argparse, heapq, json, math, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from svg_map import Proj


def seg_meters(a, b):
    lat = (a[1] + b[1]) / 2
    return math.hypot((b[0] - a[0]) * 111320 * math.cos(math.radians(lat)),
                      (b[1] - a[1]) * 110540)


class Graph:
    def __init__(self, base):
        roads = json.load(open(f"{base}_roads_wgs84.geojson", encoding="utf-8"))["features"]
        self.adj = defaultdict(list)
        self.pts = {}
        self.grid = defaultdict(list)   # spatial hash for snapping
        self.cell = 0.005               # ~500m
        for f in roads:
            c = f["geometry"]["coordinates"]
            for i in range(len(c) - 1):
                a = f"{c[i][0]:.7f},{c[i][1]:.7f}"
                b = f"{c[i+1][0]:.7f},{c[i+1][1]:.7f}"
                w = seg_meters(c[i], c[i + 1])
                self.adj[a].append((b, w))
                self.adj[b].append((a, w))
                self.pts[a] = c[i]
                self.pts[b] = c[i + 1]
        for k, (lo, la) in self.pts.items():
            self.grid[(int(lo / self.cell), int(la / self.cell))].append(k)

    def snap(self, lon, lat, max_m=500):
        """Nearest graph node via expanding ring search on the spatial hash."""
        cx, cy = int(lon / self.cell), int(lat / self.cell)
        best, bd = None, 1e18
        for r in range(0, 8):
            for gx in range(cx - r, cx + r + 1):
                for gy in range(cy - r, cy + r + 1):
                    if max(abs(gx - cx), abs(gy - cy)) != r:
                        continue                      # ring only
                    for k in self.grid.get((gx, gy), ()):
                        d = seg_meters((lon, lat), self.pts[k])
                        if d < bd:
                            best, bd = k, d
            if best is not None and bd < r * self.cell * 111000:
                break                                 # ring already wider than best dist
        if best is None or bd > max_m:
            raise RuntimeError(f"OD ({lon},{lat}) snapped {bd:.0f}m away — outside road graph?")
        return best

    def astar(self, src, dst):
        def h(k):
            return seg_meters(self.pts[k], self.pts[dst])
        dist = {src: 0.0}
        prev = {}
        pq = [(h(src), 0.0, src)]
        seen = set()
        while pq:
            _, d, u = heapq.heappop(pq)
            if u in seen:
                continue
            seen.add(u)
            if u == dst:
                break
            for v, w in self.adj[u]:
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd + h(v), nd, v))
        if dst not in dist:
            raise RuntimeError("no path")
        path, u = [dst], dst
        while u != src:
            u = prev[u]
            path.append(u)
        return path[::-1], dist[dst]


def douglas_peucker(pts, tol):
    """pts: list of [x,y] in px; tolerance in px."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        ax, ay = pts[i]; bx, by = pts[j]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy or 1e-12
        dmax, imax = -1.0, -1
        for m in range(i + 1, j):
            t = ((pts[m][0] - ax) * dx + (pts[m][1] - ay) * dy) / L2
            t = max(0.0, min(1.0, t))
            px_, py_ = ax + t * dx, ay + t * dy
            d = math.hypot(pts[m][0] - px_, pts[m][1] - py_)
            if d > dmax:
                dmax, imax = d, m
        if dmax > tol:
            keep[imax] = True
            stack.append((i, imax)); stack.append((imax, j))
    return [p for p, k in zip(pts, keep) if k]


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--bbox", required=True)
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--od", action="append", required=True,
                    help="nameA,latA,lonA,nameB,latB,lonB (WGS-84), repeatable")
    ap.add_argument("--tol", type=float, default=1.2, help="simplify tolerance (px)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    g = Graph(args.base)
    print(f"graph: {len(g.adj)} nodes, {sum(len(v) for v in g.adj.values())//2} edges")
    proj = Proj([float(v) for v in args.bbox.split(",")], args.width)

    routes = []
    for spec in args.od:
        na, lata, lona, nb, latb, lonb = spec.split(",")
        s = g.snap(float(lona), float(lata))
        d = g.snap(float(lonb), float(latb))
        path, meters = g.astar(s, d)
        px = []
        for k in path:
            lon, lat = g.pts[k]
            px.append([round(v, 1) for v in proj.pt(lon, lat)])
        px = [px[0]] + [p for i, p in enumerate(px[1:], 1) if p != px[i - 1]]
        raw = len(px)
        px = douglas_peucker(px, args.tol)
        routes.append({"name": f"{na} → {nb}", "a": na, "b": nb,
                       "pts": px, "meters": round(meters)})
        print(f"  {na} → {nb}: {raw} pts -> {len(px)} pts (simplified), {meters:.0f} m")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump({"routes": routes}, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
