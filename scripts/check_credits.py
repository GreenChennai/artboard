"""artboard 素材版权复核:img 目录 ↔ CREDITS.md 逐条对账。

为什么需要它:fetch_asset 的风险机制(「版权风险-」前缀 + CREDITS 登记)靠自觉执行,
交付前没有机器门。本脚本零 token 对账:
  ① src/img 里哪些文件带「版权风险-」前缀(交付必须提醒更换)
  ② 哪些文件没有 CREDITS 记录(登记义务未履行)
输出机器生成的「待更换清单」与「未登记清单」,交付汇报直接引用。

用法:
  python check_credits.py <项目>/src/img --credits <项目>/CREDITS.md
  # --credits 缺省找 <img 同级或父目录>/CREDITS.md;输出单行 JSON 到 stdout,
  # 人类可读清单走 stderr。退出码 0=通过 / 1=有未登记项 / 2=用法错
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

RISK_PREFIX = "版权风险-"
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif"}
CREDITS_ROW = re.compile(r"^\|\s*(.+?)\s*\|", re.MULTILINE)


def read_credits_files(credits_path: str) -> set[str]:
    """CREDITS.md 表格首列(文件名;忽略表头/分隔行)。"""
    if not credits_path or not os.path.isfile(credits_path):
        return set()
    with open(credits_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    out: set[str] = set()
    for m in CREDITS_ROW.finditer(text):
        cell = m.group(1).strip()
        if not cell or cell in ("文件", "---", ":---") or set(cell) <= {"-", ":"}:
            continue
        out.add(os.path.basename(cell))
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="素材版权复核(img ↔ CREDITS 对账;详见脚本头)")
    ap.add_argument("img_dir", help="项目 src/img 目录")
    ap.add_argument("--credits", default="", help="CREDITS.md 路径(缺省自动找)")
    args = ap.parse_args()

    img_dir = args.img_dir
    if not os.path.isdir(img_dir):
        print(json.dumps({"ok": False, "error": "IMG_DIR_NOT_FOUND", "detail": img_dir},
                         ensure_ascii=False))
        print(f"img 目录不存在: {img_dir}", file=sys.stderr)
        return 2

    credits = args.credits
    if not credits:
        for cand in (os.path.join(img_dir, "CREDITS.md"),
                     os.path.join(os.path.dirname(img_dir), "CREDITS.md"),
                     os.path.join(os.path.dirname(os.path.dirname(img_dir)), "CREDITS.md")):
            if os.path.isfile(cand):
                credits = cand
                break

    registered = read_credits_files(credits)
    files = sorted(f for f in os.listdir(img_dir)
                   if os.path.splitext(f)[1].lower() in IMG_EXTS
                   and not f.startswith("~$"))
    risk_files = [f for f in files if f.startswith(RISK_PREFIX)]
    unregistered = [f for f in files if f not in registered]
    phantom = sorted(registered - set(files))  # 登记了但文件已不在(可能已删)

    result = {
        "ok": not unregistered,
        "img_dir": img_dir, "credits": credits or None,
        "count": len(files),
        "risk_files": risk_files,           # 交付必须提醒更换(不挡过,但必须出现在汇报)
        "unregistered": unregistered,       # 挡过:退出码 1
        "phantom_credits": phantom,         # 提示:登记与磁盘不同步
        "remind": ("交付汇报必须列出全部「版权风险-」素材并提醒更换;任何环节不得移除该前缀"
                   if risk_files else None),
    }
    print(json.dumps(result, ensure_ascii=False))
    if unregistered:
        print("未登记(须补 CREDITS 或删图):" + "、".join(unregistered), file=sys.stderr)
    if risk_files:
        print("风险素材待更换(交付提醒):" + "、".join(risk_files), file=sys.stderr)
    return 1 if unregistered else 0


if __name__ == "__main__":
    sys.exit(main())
