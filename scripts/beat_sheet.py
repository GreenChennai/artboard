"""artboard 卡点表:BPM → 帧网格(模式 V · 视频动效件;细则见 references/video-motion.md §五)。

为什么需要它:卡点切换的"点"必须落在整数帧上,否则导出后抽帧对不齐——
肉眼在预览里觉得"准了",渲染完总会差半帧。本脚本把 BPM(或秒点列表)换算成
帧网格,输出每个 shot 的对齐出入点,供分镜表(video-motion.md §四)直接引用。

用法:
  python beat_sheet.py --bpm 120 --fps 25 --bars 16 [--subdiv 2]
  python beat_sheet.py --list "0.5,1.0,1.6,2.4" --fps 25      # 无 BPM 的秒点直接对齐

换算口径:
  拍间隔(ms) = 60000 / BPM;细分后间隔 = 拍间隔 / subdiv
  帧网格帧 = round(t_ms / (1000 / fps)) —— 四舍五入到最近整数帧

输出:stdout 单行 JSON {ok, bpm, fps, subdiv, bars, beat_ms, frame_ms,
points:[{index,t_ms,t_sec,frame}]};人类可读表走 stderr。
退出码 0=成功 / 2=用法错(缺 --bpm 与 --list)
"""

from __future__ import annotations

import argparse
import json
import sys


def build_points(bpm: float, fps: int, subdiv: int, bars: int) -> list[dict]:
    beat_ms = 60000.0 / bpm / subdiv
    frame_ms = 1000.0 / fps
    total = bars * 4 * subdiv  # 4 拍/小节
    points = []
    for i in range(total + 1):
        t_ms = i * beat_ms
        frame = round(t_ms / frame_ms)
        points.append({"index": i, "t_ms": round(t_ms, 1),
                       "t_sec": round(t_ms / 1000, 3), "frame": frame})
    return points


def snap_list(seconds: str, fps: int) -> list[dict]:
    frame_ms = 1000.0 / fps
    out = []
    for i, tok in enumerate(seconds.split(",")):
        tok = tok.strip()
        if not tok:
            continue
        t_ms = float(tok) * 1000
        frame = round(t_ms / frame_ms)
        out.append({"index": i, "t_ms": round(t_ms, 1),
                    "t_sec": round(t_ms / 1000, 3), "frame": frame,
                    "snapped_sec": round(frame * frame_ms / 1000, 3)})
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="BPM→帧 卡点表(模式 V;见 video-motion.md §五)")
    ap.add_argument("--bpm", type=float, help="曲速(与 --list 二选一)")
    ap.add_argument("--fps", type=int, default=25, help="帧率,默认 25(动画 fps 档见 animation.md)")
    ap.add_argument("--bars", type=int, default=16, help="小节数,默认 16(4 拍/小节)")
    ap.add_argument("--subdiv", type=int, default=1, help="每拍细分,默认 1(2=八分音符)")
    ap.add_argument("--list", default="", help='逗号分隔秒点(无 BPM 时用),如 "0.5,1.0,1.6"')
    args = ap.parse_args()

    if not args.bpm and not args.list:
        print(json.dumps({"ok": False, "error": "USAGE",
                          "hint": "需要 --bpm(BPM 模式)或 --list(秒点模式)"}, ensure_ascii=False))
        return 2
    if args.bpm and args.bpm <= 0:
        print(json.dumps({"ok": False, "error": "USAGE", "hint": "--bpm 必须为正"}, ensure_ascii=False))
        return 2

    if args.bpm:
        points = build_points(args.bpm, args.fps, max(args.subdiv, 1), max(args.bars, 1))
        beat_ms = round(60000.0 / args.bpm / max(args.subdiv, 1), 1)
    else:
        points = snap_list(args.list, args.fps)
        beat_ms = None
    print(json.dumps({"ok": True, "cmd": "beat_sheet",
                      "bpm": args.bpm or None, "fps": args.fps,
                      "subdiv": args.subdiv if args.bpm else None,
                      "bars": args.bars if args.bpm else None,
                      "beat_ms": beat_ms,
                      "count": len(points), "points": points}, ensure_ascii=False))
    lines = ["  #    t(s)   frame" + ("   snapped(s)" if not args.bpm else "")]
    for p in points:
        row = f"{p['index']:>4} {p['t_sec']:>7.3f} {p['frame']:>6}"
        if "snapped_sec" in p:
            row += f" {p['snapped_sec']:>10.3f}"
        lines.append(row)
    print("\n".join(lines), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
