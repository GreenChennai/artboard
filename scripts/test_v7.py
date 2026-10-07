"""地图播放器自动化验收 V1-V12(依据 docs/map/research-v7-route-ants.md §四)。

  python scripts/test_v7.py              # 全部断言 + 截图到 assets/map/samples/v7-*.png
  python scripts/test_v7.py --no-shots   # 只跑断言(快)

前置:先跑 `build_player.py` 生成 assets/map/demo/map-player.html。
V9-V12 的"贴边/出城/对角线"断言按随技能附带的样例画布 **1600×1917** 写死,
换 bbox 重出 SVG 后需同步这两处(见脚本内 `1600`/`1917` 字面量)。
"""
import argparse
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT / "assets" / "map" / "samples"

INIT_HOOK = """
(() => {
  const orig = window.requestAnimationFrame.bind(window);
  window.__frames = [];
  window.__strokes = 0;
  const sp = CanvasRenderingContext2D.prototype.stroke;
  CanvasRenderingContext2D.prototype.stroke = function () {
    window.__strokes++;
    return sp.apply(this, arguments);
  };
  window.requestAnimationFrame = function (cb) {
    return orig(function (ts) {
      cb(ts);
      try {
        const cars = window.__cars;
        if (cars && cars.length) {
          const fr = [ts, []];
          for (let i = 0; i < cars.length; i++) {
            const q = cars[i];
            if (!q.tr) continue;
            const ii = Math.min(q.tr.n - 2, (q.s / q.tr.step) | 0), t = q.s / q.tr.step - ii;
            fr[1].push([q.gid, q.tr.xs[ii] + (q.tr.xs[ii + 1] - q.tr.xs[ii]) * t,
                        q.tr.ys[ii] + (q.tr.ys[ii + 1] - q.tr.ys[ii]) * t, q.v, q.s]);
          }
          if (window.__frames.length > 500) window.__frames.shift();
          window.__frames.push(fr);
        }
      } catch (e) {}
    });
  };
})();
"""


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--player", default="assets/map/demo/map-player.html",
                    help="播放器 HTML(相对技能根)")
    ap.add_argument("--no-shots", action="store_true", help="跳过 V8 三张截图")
    args = ap.parse_args()

    player = (ROOT / args.player).resolve()
    if not player.is_file():
        raise SystemExit(f"[X] 播放器不存在: {player}\n"
                         f"    先跑 python scripts/build_player.py 生成")

    results = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1500, "height": 950})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.add_init_script(INIT_HOOK)
        pg.goto(player.as_uri())
        pg.wait_for_timeout(2000)

        # 开全特效(boot 除外,避免入场期干扰)
        pg.evaluate("""() => {
          document.querySelectorAll('[data-fx]').forEach(el => {
            if (el.dataset.fx !== 'boot' && !el.checked) el.click();
          });
        }""")
        pg.wait_for_timeout(2000)
        pg.evaluate("() => { window.__frames.length = 0; window.__strokes = 0; }")

        # ---- V1: 25s 全特效长跑 ----
        t0 = time.time()
        pg.wait_for_timeout(25000)
        v1_sec = time.time() - t0

        info = pg.evaluate("""() => ({
          fps: window.__fps, graph: window.__GRAPH, stat: window.__stat,
          cars: (window.__cars || []).length,
          frames: window.__frames, strokes: window.__strokes
        })""")
        frames = info["frames"]
        print(f"frames sampled: {len(frames)}, strokes(25s): {info['strokes']}, "
              f"fps: {info['fps']}, stat: {info['stat']}, cars: {info['cars']}")

        # ---- V2: 连续性(帧间跳变,按 gid 跟踪同一辆车) ----
        # 阈值语义:允许极低频的合流防穿模微回推(≤8 次/25s 且 ≤12px,肉眼不可见);
        # 瞬移类 bug 是百像素级,V2 依旧严抓
        v2_max_jump, v2_bad, v2_top = 0.0, 0, []
        for a, bfr in zip(frames, frames[1:]):
            dt = (bfr[0] - a[0]) / 1000.0
            if dt <= 0 or dt > 0.2:
                continue
            amap = {c[0]: c for c in a[1]}
            for c in bfr[1]:
                pa = amap.get(c[0])
                if pa is None:
                    continue
                dx = c[1] - pa[1]
                dy = c[2] - pa[2]
                jump = (dx * dx + dy * dy) ** 0.5
                lim = c[3] * dt * 1.05 + 2.5
                if jump > lim:
                    v2_bad += 1
                    v2_top.append((round(jump, 2), round(lim, 2), round(c[3], 1), round(dt, 3)))
                v2_max_jump = max(v2_max_jump, jump)
        v2_top.sort(reverse=True)
        v2_bounded = all(t[0] <= 12 for t in v2_top)
        results.append(("V2 帧间连续性(微修正≤8次且≤12px)", v2_bad <= 8 and v2_bounded,
                        f"max jump {v2_max_jump:.2f}px, corrections {v2_bad}, top {v2_top[:3]}"))

        # ---- V3: 贴路(span 区间内采样,头部跳过 b0 桥区,尾部留 8px) ----
        v3 = pg.evaluate("""() => {
          const CORR = window.__CORR || [];
          const cars = (window.__cars || []).filter(q => q.tr);
          let worst = 0, n = 0;
          for (const q of cars) {
            for (const span of q.tr.spans) {
              const lo = span.s0 + (span.b0 || 0) + 8, hi = span.s1 - 8;
              for (let s = lo; s < hi; s += 20) {
                const ii = Math.min(q.tr.n - 2, (s / q.tr.step) | 0);
                const px = q.tr.xs[ii], py = q.tr.ys[ii];
                let best = 1e9;
                for (let ci = 0; ci < CORR.length; ci++) {
                  const c = CORR[ci];
                  const bb = c.bb;
                  if (px < bb[0]-8 || px > bb[0]+bb[2]+8 || py < bb[1]-8 || py > bb[1]+bb[3]+8) continue;
                  for (let si = 0; si < c.n; si++) {
                    const dx = c.xs[si]-px, dy = c.ys[si]-py;
                    const d = dx*dx+dy*dy;
                    if (d < best) best = d;
                  }
                }
                worst = Math.max(worst, Math.sqrt(best));
                n++;
              }
            }
          }
          return {worst, n};
        }""")
        results.append(("V3 贴路 ≤4px(走廊区间,跳过桥区)", v3["worst"] <= 4.0,
                        f"worst {v3['worst']:.2f}px over {v3['n']} samples"))

        # ---- V4: 同走廊同向间隙(≥-12px:合流起点堆叠的受钳瞬态,防穿模回推兜底且视觉为
        #      两光点短暂叠亮;中位间隙看疏密健康度) ----
        v4 = pg.evaluate("""() => {
          const cars = (window.__cars || []).filter(q => q.tr && !q.fading);
          const bk = new Map();
          for (const q of cars) {
            const key = q.tr.spans[Math.min(q.spanI, q.tr.spans.length-1)].key;
            if (!bk.has(key)) bk.set(key, []);
            bk.get(key).push(q.s);
          }
          let minGap = 1e9;
          const gaps = [];
          bk.forEach(arr => {
            arr.sort((a, b) => a - b);
            for (let i = 1; i < arr.length; i++) {
              const g = arr[i] - arr[i-1] - 12;
              minGap = Math.min(minGap, g);
              gaps.push(g);
            }
          });
          gaps.sort((a, b) => a - b);
          return {minGap, med: gaps.length ? gaps[gaps.length >> 1] : -1, pairs: gaps.length};
        }""")
        results.append(("V4 跟驰(瞬态≥-12px,中位>30px)+ 排队呈现实感", v4["minGap"] >= -12 and v4["med"] > 30,
                        f"min gap {v4['minGap']:.1f}px, median {v4['med']:.0f}px, {v4['pairs']} pairs"))

        # ---- V5: 转弯减速 ----
        v5 = pg.evaluate("""() => {
          const cars = (window.__cars || []).filter(q => q.tr);
          let near = 0, slow = 0;
          for (const q of cars) {
            for (const tn of q.tr.turns) {
              const d = tn.s - q.s;
              if (d > 0 && d < 45) {
                near++;
                const vT = 34 + 62 * Math.max(0, tn.straight);
                const vCap = Math.sqrt(vT*vT + 2*140*d);
                if (q.v <= vCap * 1.15 + 6) slow++;
                break;
              }
            }
          }
          return {near, slow, ratio: near ? slow / near : 1};
        }""")
        results.append(("V5 转弯制动符合制动曲线", v5["ratio"] >= 0.9,
                        f"near-turn {v5['near']}, compliant {v5['slow']} ({v5['ratio']*100:.0f}%)"))

        # ---- V6: 绘制调用(合并模式,口径:每帧 stroke 数) ----
        n_frames = max(1, len(frames))
        spf = info["strokes"] / 25.0 / min(info["fps"], n_frames / 25.0) if info["fps"] else 0
        spf = info["strokes"] / max(1, round(25.0 * info["fps"]))  # 帧数 ≈ fps×秒
        results.append(("V6 stroke ≤60/帧(全开)", spf <= 60, f"{spf:.0f} strokes/frame"))

        # ---- V7: 帧率(无头软渲染环境) ----
        results.append(("V7 fps ≥ 25(软渲染;真 GPU 预期 60)", info["fps"] >= 25, f"{info['fps']} fps"))

        # ---- V8: 三阶段截图(寻路 4.5s 周期内取相) ----
        pg.evaluate("""() => {
          document.querySelectorAll('[data-fx]').forEach(el => {
            el.checked = el.dataset.fx === 'route' || el.dataset.fx === 'pulse';
            el.dispatchEvent(new Event('change'));
          });
        }""")
        pg.wait_for_timeout(300)
        if args.no_shots:
            results.append(("V8 截图(人审)", True, "已按 --no-shots 跳过"))
        else:
            SHOTS.mkdir(parents=True, exist_ok=True)
            pg.screenshot(path=str(SHOTS / "v7-ants.png"))
            pg.wait_for_timeout(1600)
            pg.screenshot(path=str(SHOTS / "v7-route-draw.png"))
            pg.wait_for_timeout(5200)
            pg.screenshot(path=str(SHOTS / "v7-route-flow.png"))
            results.append(("V8 截图(人审)", True,
                            "assets/map/samples/v7-ants.png / v7-route-draw.png / v7-route-flow.png"))

        # ---- V9: 掉头合法性 + 到达率(A* 导航 300 条入口→出口;跨段重访是"兜圈"设计,只严抓掉头) ----
        v9 = pg.evaluate("""() => {
          const pool = window.ENTRY_POOL, plan = window.astarRoute, share = window.sharesRoad;
          const edge = c => Math.min(c.ex, 1600 - c.ex, c.ey, 1917 - c.ey) <= 14;
          let n = 0, bad = 0, revisits = 0, exits = 0, notBoundary = 0;
          for (let k = 0; k < 300; k++) {
            const c0 = pool[Math.random() * pool.length | 0];
            if (!c0) continue;
            const rr = plan(c0);
            const r = rr.route;
            n++;
            const seen = {};
            for (let i = 0; i < r.length; i++) {
              if (seen[r[i].id]) revisits++;
              seen[r[i].id] = true;
              if (i > 0 && share(r[i - 1], r[i])) { bad++; break; }   // 相邻共享道路 = 掉头
            }
            if (rr.exit) {
              exits++;
              if (!edge(r[r.length - 1])) notBoundary++;
            }
          }
          return {n, bad, revisits, exits, notBoundary};
        }""")
        ok9 = v9["bad"] == 0 and v9["notBoundary"] == 0 and v9["exits"] >= v9["n"] * 0.9
        results.append(("V9 导航合法性(300 条:零掉头/到达率≥90%;跨段重访为兜圈设计)", ok9,
                        f"planned {v9['n']}, U-turns {v9['bad']}, revisits(info) {v9['revisits']}, "
                        f"exits {v9['exits']}, notBoundary {v9['notBoundary']}"))

        # ---- V10: 环岛行为(环走廊不超限、不逆行、出口必达) ----
        v10 = pg.evaluate("""() => {
          const RING = window.RING_OF, CORR = window.CORR, plan = window.astarRoute;
          const edge = c => Math.min(c.ex, 1600 - c.ex, c.ey, 1917 - c.ey) <= 14;
          const entries = [];
          for (let i = 0; i < CORR.length; i++) if (RING[i] >= 0) entries.push(CORR[i]);
          if (!entries.length) return {n: 0};
          let tested = 0, laps = 0, badExit = 0, bannedUse = 0;
          for (let k = 0; k < Math.min(30, entries.length * 3); k++) {
            const c0 = entries[Math.random() * entries.length | 0];
            const rr = plan(c0);
            const r = rr.route;
            tested++;
            let ringCount = 0;
            for (let i = 0; i < r.length; i++) {
              if (RING[r[i].id] >= 0) ringCount++;
              if (r[i].banned) bannedUse++;
            }
            if (ringCount > 10) laps++;
            if (rr.exit && !edge(r[r.length - 1])) badExit++;
          }
          return {n: entries.length, tested, laps, badExit, bannedUse};
        }""")
        ok10 = v10["n"] > 0 and v10["laps"] == 0 and v10["badExit"] == 0 and v10["bannedUse"] == 0
        results.append(("V10 环岛行为(环走廊 62 条:不绕圈/不逆行/出口必达)", ok10,
                        f"ring corridors {v10['n']}, tested {v10['tested']}, laps {v10['laps']}, "
                        f"badExit {v10['badExit']}, bannedUse {v10['bannedUse']}"))

        # ---- V11: 路线确定性 + 目的地多样性(同(车,目的地)逐 id 一致;远出口≥2 的入口去向≥2种) ----
        v11 = pg.evaluate("""() => {
          const pool = window.ENTRY_POOL, route = window.astarRoute, one = window.astarOne,
                EXOF = window.EXITS_OF, VBW = 1600, VBH = 1917;
          const diag = Math.hypot(VBW, VBH);
          let detPairs = 0, detBad = 0, divCars = 0, divOk = 0, n = 0, singleExit = 0;
          for (let k = 0; k < 60; k++) {
            const c0 = pool[Math.random() * pool.length | 0];
            if (!c0) continue;
            n++;
            const exl = EXOF[c0.id] || [];
            const far = exl.filter(e => Math.hypot(e.ex - c0.sx, e.ey - c0.sy) >= diag * 0.42);
            const pick = far.length ? far : exl;
            if (pick.length <= 1) { singleExit++; continue; }  // 只有一条远路,无多样性可言
            const d = pick[k % pick.length];
            const r1 = one(c0, d), r2 = one(c0, d);
            if (r1 && r2) {
              detPairs++;
              const ids1 = r1.route.map(x => x.id).join(',');
              const ids2 = r2.route.map(x => x.id).join(',');
              if (ids1 !== ids2) detBad++;
            }
            const seen = {};
            let distinct = 0;
            for (let t = 0; t < 6; t++) {
              const rr = route(c0);
              const key = rr.route.map(x => x.id).join(',');
              if (!seen[key]) { seen[key] = true; distinct++; }
            }
            divCars++;
            if (distinct >= 2) divOk++;
          }
          return {n, detPairs, detBad, divCars, divOk, singleExit};
        }""")
        if "weird" in v11:
            results.append(("V11 确定性/多样性", False, f"weird: {v11['weird']}"))
        else:
            ok11 = v11["detBad"] == 0 and v11["divOk"] >= v11["divCars"] * 0.9
            results.append(("V11 路线确定性+目的地多样性(同目标必同路;多远路入口去向≥2种)", ok11,
                            f"cars {v11['n']}, determinism {v11['detPairs'] - v11['detBad']}/{v11['detPairs']}, "
                            f"diverse {v11['divOk']}/{v11['divCars']} (单远路入口 {v11['singleExit']} 不计)"))

        # ---- V12: 边缘出生 + 穿城(所有入口贴边;出口距出生 ≥0.35 对角线占多数) ----
        v12 = pg.evaluate("""() => {
          const pool = window.ENTRY_POOL, route = window.astarRoute, np = window.nodePos,
                VBW = 1600, VBH = 1917;
          const diag = Math.hypot(VBW, VBH);
          let edgeOK = 0;
          for (const c of pool) {
            const dEdge = Math.min(c.sx, VBW - c.sx, c.sy, VBH - c.sy);
            if (dEdge <= 14) edgeOK++;
          }
          let n = 0, exits = 0, through = 0;
          const dists = [];
          for (let k = 0; k < 60; k++) {
            const c0 = pool[Math.random() * pool.length | 0];
            if (!c0) continue;
            const rr = route(c0);
            n++;
            if (!rr.exit) continue;
            exits++;
            const last = rr.route[rr.route.length - 1];
            const p1 = np.get(last.eNode);
            const d = Math.hypot(p1[0] - c0.sx, p1[1] - c0.sy);
            dists.push(d);
            if (d >= diag * 0.35) through++;
          }
          dists.sort((a, b) => a - b);
          const med = dists.length ? dists[dists.length >> 1] : 0;
          return {poolN: pool.length, edgeOK, n, exits, through, med: Math.round(med), diag: Math.round(diag)};
        }""")
        ok12 = (v12["poolN"] > 0 and v12["edgeOK"] == v12["poolN"]
                and v12["exits"] >= v12["n"] * 0.95 and v12["through"] >= v12["exits"] * 0.6)
        results.append(("V12 边缘出生+穿城(入口全贴边;出口距出生≥0.35对角线占≥6成)", ok12,
                        f"entries {v12['poolN']}(贴边 {v12['edgeOK']}), planned {v12['n']}, exits {v12['exits']}, "
                        f"through {v12['through']}, median exit dist {v12['med']}px / diag {v12['diag']}px"))

        # ---- V1 结论 ----
        results.insert(0, ("V1 长跑零报错", len(errs) == 0, f"{v1_sec:.0f}s, errors: {errs or '无'}"))

        b.close()

    print("\n===== 验收结果 =====")
    fails = 0
    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            fails += 1
        print(f"[{mark}] {name} — {detail}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
