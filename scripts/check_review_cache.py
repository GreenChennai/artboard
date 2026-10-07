"""缓存隔离审计:证明"缓存/抽稀只影响预览,不影响成片内容与预览完整性"。

为什么需要它:审片台为了"改完立刻能看"常开加速开关(抽稀、时间复用、离屏缓存)。
这类开关一旦污染了无加速路径,后果是**画面悄悄变了** —— 肉眼看不出来,只有量化才知道。
本脚本是那条"理论上不该变"的算术证明。

两组判据(别混):
  ① **页内纯度**:同一个 t 反复画,路径为
        A(基准) → 中途去别处狂画(seek 到远处再回来) → 回到同 t 得 C → 得 D
     A/C/D 必须**逐字节相同**(sha1)。任何"缓存污染后续全量渲染"都会在这里露出来。
     可用 `--abuse-js` 追加项目自己的"抽稀/加速"钩子(见下),这才是完整版审计。
  ② **跨页对照**(可选,`--baseline <目录>`):审片台 vs 成片(或上一轮的冻结帧)。
     两个页面的 DOM 层数不同 ⇒ 画布走的光栅化路径不同,每个字形的抗锯齿会差一级,
     所以**不要求逐字节**:平均差 ≤2/255 且 差>32 的像素 <6%(称"AA 级差异")。

用法:
  python check_review_cache.py --url http://127.0.0.1:8860/__rv/review.html --times 1.0,2.0,3.5
  python check_review_cache.py --url … --baseline <基线目录> --baseline-name f%05d.png
  python check_review_cache.py --url … --abuse-js "() => { for (let i=0;i<60;i++) window.SEEK(30+i/60); }"
输出:stdout 单行 JSON;人类可读清单走 stderr。退出码 0=通过 / 1=不一致 / 2=用法或环境错。

默认的 `--seek-js` 是 `(t) => window.__rv.seek(t)`(审片台挂的测试钩子);通用性说明:
来源工程的"抽稀/时间复用"钩子(`ENG.ADEC/AREUSE`)是**项目专属**,所以不写死:
用 `--abuse-js` 传进来,不传就只做"去别处再回来"的缓存纯度检查(仍是有效判据)。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

BARE_JS = """() => {
  const st = document.createElement('style');
  st.textContent = `#rv-topbar,#rv-transport,#rv-right,#rv-fsbar,#rv-hover,
    #rv-badge-diff,#rv-fs-tip{display:none !important}
    body.rv{display:block !important} #rv-left{display:block !important}
    #rv-viewport{position:absolute !important;left:0 !important;top:0 !important;
      width:1920px !important;height:1080px !important;overflow:visible !important;
      background:#000 !important} #rv-scaler{transform:none !important}`;
  document.head.appendChild(st); return true;
}"""


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def sha1(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def cmp_img(a: str, b: str) -> tuple[float, int, float]:
    """返回 (平均通道差/255, 最大通道差, 差>32 的像素占比)。"""
    import numpy as np                                     # noqa: PLC0415
    from PIL import Image                                  # noqa: PLC0415
    x = np.asarray(Image.open(a).convert("RGB")).astype(np.int16)
    y = np.asarray(Image.open(b).convert("RGB")).astype(np.int16)
    if x.shape != y.shape:
        return -1.0, 255, 1.0
    d = np.abs(x - y)
    mx = d.max(axis=2)
    return float(d.mean()), int(mx.max()), float((mx > 32).sum()) / float(mx.size)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:                                  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="审片台缓存隔离审计(页内逐字节 + 跨页 AA 容差)")
    ap.add_argument("--url", default="", help="审片台页面 URL(必须 http,不是 file://)")
    ap.add_argument("--times", default="1.0,2.0,3.5", help="采样时刻(秒,逗号分隔)")
    ap.add_argument("--seek-js", default="(t) => window.__rv.seek(t)",
                    help="把页面 seek 到 t 的表达式(默认用审片台的 __rv.seek)")
    ap.add_argument("--abuse-js", default="",
                    help="可选:项目自己的抽稀/加速钩子(在两次采样之间狂画),用于完整版审计")
    ap.add_argument("--baseline", default="", help="可选:跨页对照的基线目录")
    ap.add_argument("--baseline-name", default="f%05.0f.png",
                    help="基线文件名模板(%%f = t×fps);默认 f%%05.0f.png")
    ap.add_argument("--fps", type=int, default=60, help="配合 --baseline-name 换算帧号")
    ap.add_argument("--out", default="", help="截图输出目录(默认 <临时目录>/review-cache)")
    ap.add_argument("--tol-mean", type=float, default=2.0, help="跨页平均差上限(/255)")
    ap.add_argument("--tol-big", type=float, default=0.06, help="跨页 差>32 像素占比上限")
    args = ap.parse_args()

    if not args.url:
        emit({"ok": False, "error": "USAGE", "hint": "先起审片台,再把页面 URL 传 --url"})
        return 2
    if not args.url.startswith("http://"):
        emit({"ok": False, "error": "NEED_HTTP", "detail": args.url,
              "hint": "file:// 会命中 CORS 且取不到 __rv;必须用 http://127.0.0.1:…"})
        return 2
    try:
        import numpy  # noqa: F401,PLC0415
        from PIL import Image  # noqa: F401,PLC0415
        from playwright.sync_api import sync_playwright           # noqa: PLC0415
    except Exception as exc:                               # noqa: BLE001
        emit({"ok": False, "error": "NO_DEPS", "detail": str(exc),
              "hint": "pip install playwright numpy pillow"})
        return 2

    out = args.out or os.path.join(os.environ.get("TEMP", "/tmp"), "review-cache")
    os.makedirs(out, exist_ok=True)
    times = [float(x) for x in args.times.split(",") if x.strip()]
    rows, ok_all = [], True

    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page(viewport={"width": 1920, "height": 1080})
        errs: list[str] = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(args.url, wait_until="load")
        try:
            pg.wait_for_function("!!window.__rv", timeout=30000)
        except Exception:                                  # noqa: BLE001
            emit({"ok": False, "error": "NO_RV_HOOK",
                  "hint": "页面没挂 window.__rv;确认打开的是审片台页面,且影片脚本加载成功",
                  "pageerror": errs[:3]})
            br.close()
            return 2
        # 预热:排掉"首次 seek 的中间态"与字体未落位(都会让首帧与之后不同)
        pg.evaluate(BARE_JS)
        pg.evaluate("() => document.fonts && document.fonts.ready")
        pg.wait_for_timeout(900)
        pg.evaluate(args.seek_js, 0.0)

        def shot(name: str) -> str:
            p = os.path.join(out, name)
            pg.screenshot(path=p, type="png")
            return p

        def seek(t: float) -> None:
            pg.evaluate(args.seek_js, t)
            pg.wait_for_timeout(250)

        print(f"① 页内缓存纯度({len(times)} 个时刻,A/C/D 必须逐字节相同)", file=sys.stderr)
        for t in times:
            seek(t)
            a = shot("A_%07.3f.png" % t)
            if args.abuse_js:
                pg.evaluate(args.abuse_js)
            seek(times[0] + 7.3 if t < times[0] + 7.3 else times[-1] - 3.0)  # 去别处
            seek(t)
            c = shot("C_%07.3f.png" % t)
            if args.abuse_js:
                pg.evaluate(args.abuse_js)
            seek(t + 1.7)
            seek(t)
            d = shot("D_%07.3f.png" % t)
            same = sha1(a) == sha1(c) == sha1(d)
            ok_all &= same
            rows.append({"t": t, "pure": same,
                         "sha": [sha1(a)[:10], sha1(c)[:10], sha1(d)[:10]]})
            print(f"   t={t:<7} A={sha1(a)[:10]} C={sha1(c)[:10]} D={sha1(d)[:10]}  "
                  f"{'一致' if same else '!! 不一致'}", file=sys.stderr)

        cross = []
        if args.baseline:
            print("② 跨页对照(AA 容差:平均差 ≤%.1f/255 且 差>32 <%.0f%%)"
                  % (args.tol_mean, args.tol_big * 100), file=sys.stderr)
            for t in times:
                name = args.baseline_name % (t * args.fps)
                ref = os.path.join(args.baseline, name)
                if not os.path.isfile(ref):
                    print(f"   t={t:<7} 基线缺 {name}(跳过)", file=sys.stderr)
                    continue
                seek(t)
                mean, mx, big = cmp_img(shot("X_%07.3f.png" % t), ref)
                good = 0 <= mean <= args.tol_mean and big < args.tol_big
                ok_all &= good
                cross.append({"t": t, "mean": round(mean, 3), "max": mx,
                              "big_ratio": round(big, 4), "ok": good})
                print(f"   t={t:<7} 平均差 {mean:.2f}/255  最大 {mx}  差>32 {big * 100:.2f}%  "
                      f"{'AA 级(可接受)' if good else '!! 超出容差'}", file=sys.stderr)
        print(f"   页面报错 {len(errs)}", file=sys.stderr)
        br.close()

    emit({"ok": bool(ok_all), "url": args.url, "times": times,
          "abuse_js": bool(args.abuse_js), "baseline": args.baseline or None,
          "out": out, "pure": rows, "cross": cross,
          "counts": {"pure_fail": sum(1 for r in rows if not r["pure"]),
                     "cross_fail": sum(1 for c in cross if not c["ok"])},
          "pageerror": errs[:5],
          "hint": "" if args.abuse_js else
                  "未传 --abuse-js:只做了「去别处再回来」的纯度检查;"
                  "要审项目自己的抽稀/加速开关,用 --abuse-js 传它的钩子"})
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
