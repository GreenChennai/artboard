"""成片像素基线回归:改过影片/动效代码后,确认出图与冻结基线**没被动到别处**。

为什么需要它:动效代码里改一处(加个元素、挪 2px、换个缓动),很容易顺手影响到别的时刻。
"我看了一遍没问题"不算数 —— 本脚本给的是**带容差的算术判据**:

    · 差异像素(通道差 > 8)占比 > 0.05%  → 不通过
    · 或 最大通道差 > 64                → 不通过

容差不是偷懒:有**时间相位型覆盖层**的动效(扫描线、噪点、抖动),同一份代码连渲两遍
也会有几个像素不同。真正的内容改动(颜色/位置/大面积重绘)会远远超过这两个门限。

与 `compare.py` 的分工(避免双真相源):
    `compare.py`            = 两张图/两段视频"差异在哪"的**诊断**报告;
    `check_px_baseline.py`  = 一组帧对"冻结基线"的**回归门禁**(只回答过/不过 + 哪几帧)。

用法:
  # 1) 先建基线(认可当前出图)
  python check_px_baseline.py --new <新出的帧目录> --baseline <基线目录> --set-baseline
  # 2) 之后每次改完影片代码,重新出图再回归
  python check_px_baseline.py --new <新出的帧目录> --baseline <基线目录>
  # 出图这一步由你自己的渲染链路负责(artboard: export.py / 审片台的 shot)
输出:stdout 单行 JSON;人类可读清单走 stderr。退出码 0=一致 / 1=有差异 / 2=用法或数据缺失。
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import sys

TOL_RATIO = 0.0005      # 差异像素占比门限(与来源工程一致)
TOL_DELTA = 64          # 单像素最大通道差门限


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def sha1(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def diff_pixels(pa: str, pb: str) -> tuple[int, int, list[int]]:
    """返回 (差异像素数, 最大通道差, 涉及的行号前 6 个);尺寸不同返回 (-1, 255, [])。"""
    import numpy as np                                     # noqa: PLC0415
    from PIL import Image                                  # noqa: PLC0415
    a = np.asarray(Image.open(pa).convert("RGB")).astype(np.int16)
    b = np.asarray(Image.open(pb).convert("RGB")).astype(np.int16)
    if a.shape != b.shape:
        return -1, 255, []
    d = np.abs(a - b).max(axis=2)
    ys, _ = np.nonzero(d > 8)
    return int(len(ys)), int(d.max()), sorted(set(ys.tolist()))[:6]


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:                                   # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="成片像素基线回归(容差判据,不用 sha1 判内容)")
    ap.add_argument("--new", required=True, help="本次出图的帧目录")
    ap.add_argument("--baseline", required=True, help="冻结基线目录")
    ap.add_argument("--glob", default="*.png", help="帧文件名模式(默认 *.png)")
    ap.add_argument("--set-baseline", action="store_true", help="认可当前出图,刷新基线")
    ap.add_argument("--tol-ratio", type=float, default=TOL_RATIO,
                    help="差异像素占比门限(默认 0.05%%)")
    ap.add_argument("--tol-delta", type=int, default=TOL_DELTA,
                    help="单像素最大通道差门限(默认 64)")
    args = ap.parse_args()

    new_dir = os.path.abspath(args.new)
    base_dir = os.path.abspath(args.baseline)
    if not os.path.isdir(new_dir):
        emit({"ok": False, "error": "NO_NEW_DIR", "detail": new_dir,
              "hint": "--new 是本次出图的帧目录(先跑渲染/导出)"})
        return 2
    frames = sorted(glob.glob(os.path.join(new_dir, args.glob)))
    if not frames:
        emit({"ok": False, "error": "NO_FRAMES", "detail": new_dir,
              "hint": f"没找到 {args.glob};确认出图目录与文件名模式"})
        return 2

    if args.set_baseline:
        os.makedirs(base_dir, exist_ok=True)
        n = 0
        for p in frames:
            shutil.copy2(p, os.path.join(base_dir, os.path.basename(p)))
            n += 1
        emit({"ok": True, "cmd": "set-baseline", "baseline": base_dir, "copied": n})
        print(f"[baseline] 已写入 {n} 帧 -> {base_dir}", file=sys.stderr)
        return 0

    if not os.path.isdir(base_dir) or not glob.glob(os.path.join(base_dir, args.glob)):
        emit({"ok": False, "error": "NO_BASELINE", "detail": base_dir,
              "hint": "基线目录空/不存在:先跑一次 --set-baseline 建基线"})
        return 2

    rows, bad = [], 0
    for p in frames:
        name = os.path.basename(p)
        ref = os.path.join(base_dir, name)
        if not os.path.isfile(ref):
            rows.append({"frame": name, "state": "baseline-missing"})
            bad += 1
            continue
        if sha1(ref) == sha1(p):
            rows.append({"frame": name, "state": "identical"})
            continue
        cnt, mx, rows_y = diff_pixels(ref, p)
        if cnt < 0:
            rows.append({"frame": name, "state": "size-mismatch"})
            bad += 1
            continue
        ratio = cnt / float(1920 * 1080)                    # 仅用于门限;尺寸不等已在上面拦掉
        mild = ratio <= args.tol_ratio and mx <= args.tol_delta
        rows.append({"frame": name, "state": "minor" if mild else "diff",
                     "pixels": cnt, "ratio": round(ratio, 6), "max_delta": mx,
                     "rows": rows_y})
        if not mild:
            bad += 1

    ok = bad == 0
    emit({"ok": ok, "new": new_dir, "baseline": base_dir,
          "frames": len(frames), "diff": bad,
          "tol": {"ratio": args.tol_ratio, "delta": args.tol_delta}, "detail": rows})
    print(f"\n像素基线:{len(frames)} 帧,{bad} 帧不通过"
          f"(门限:差异像素占比 ≤{args.tol_ratio * 100:.3f}% 且 最大通道差 ≤{args.tol_delta})",
          file=sys.stderr)
    for r in rows:
        if r["state"] in ("diff", "baseline-missing", "size-mismatch"):
            extra = (f"{r.get('pixels', '?')} px / {r.get('ratio', 0) * 100:.4f}% / "
                     f"最大差 {r.get('max_delta')} / 行 {r.get('rows')}"
                     if r["state"] == "diff" else r["state"])
            print(f"  ✗ {r['frame']}  {extra}", file=sys.stderr)
    if not ok:
        print("  → 有真差异就先看是不是自己改的;确认无误后用 --set-baseline 刷新基线",
              file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
