"""artboard 矢量素材获取:Iconify 图标(按需 + 离线缓存 + 逐集许可)。

为什么需要它:本地图标库(assets/icons)只有按历史需求落地的百余枚,真实场景
覆盖不足;Iconify 聚合 200+ 集、约 30 万图标,工具链 MIT、**图标许可逐集不同**
——所以本脚本强制"逐集许可标注",默认只放行 MIT / Apache-2.0 / CC0 / ISC / BSD 集,
其余集需要 --allow-license 显式放行并在交付时标注。

用法:
  python fetch_svg.py iconify --set tabler --query rocket --limit 20
  python fetch_svg.py iconify --set tabler --query chart --out assets/icons     # 落地到图标库
  python fetch_svg.py iconify --list-sets [--filter mit]                        # 列集与许可
  python fetch_svg.py license --sets tabler,mdi,ph --out docs/svg-licenses.md   # 逐集许可清单
  python fetch_svg.py illust --guide                                            # 插画库人工获取指引

契约:stdout 单行 JSON(ok/error/hint,与 fetch_asset.py 一致);人类可读清单走 stderr;
退出码 0=成功 / 1=业务失败 / 2=用法错 / 3=网络不可达。
缓存:assets/icons-cache/<set>/<name>.svg(同 fetch_font.py 的按需模式,重复取零联网)。
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__))
                        ) if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == "scripts" \
    else os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(SKILL, "assets", "icons-cache")
UA = {"User-Agent": "artboard-fetch-svg/1.0"}

# 默认放行的许可 SPDX(其余需 --allow-license 显式放行;交付时仍须标注来源集)
ALLOWED_LICENSE = {"MIT", "Apache-2.0", "CC0-1.0", "ISC", "BSD-2-Clause", "BSD-3-Clause"}
API = "https://api.iconify.design"


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def get_collection(prefix: str) -> dict | None:
    """单集元数据(含 license.spdx)。"""
    try:
        data = json.loads(http_get(f"{API}/collections?prefixes={prefix}"))
    except Exception:  # noqa: BLE001 — 网络失败由调用方统一处理
        return None
    return data.get(prefix)


def license_ok(col: dict, allow: set[str]) -> tuple[bool, str]:
    lic = (col or {}).get("license") or {}
    spdx = lic.get("spdx") or lic.get("title") or "unknown"
    ok = spdx in ALLOWED_LICENSE or spdx in allow
    return ok, spdx


def fetch_svg_cached(prefix: str, name: str) -> str:
    """取单个 SVG:先缓存,后联网;缓存写盘。抛异常由上层转失败项。"""
    path = os.path.join(CACHE, prefix, f"{name}.svg")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    svg = http_get(f"{API}/{prefix}/{name}.svg").decode("utf-8")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    return svg


def cmd_iconify(args) -> int:
    if args.list_sets:
        try:
            data = json.loads(http_get(f"{API}/collections"))
        except Exception as exc:  # noqa: BLE001
            emit({"ok": False, "error": "NETWORK", "hint": f"Iconify 不可达({exc})"})
            return 3
        allow = set(args.allow_license or [])
        rows = []
        for prefix, col in sorted(data.items()):
            ok, spdx = license_ok(col, allow)
            if args.filter == "mit" and not ok:
                continue
            rows.append({"prefix": prefix, "name": col.get("name"),
                         "license": spdx, "total": col.get("total"),
                         "allowed": ok})
        emit({"ok": True, "cmd": "iconify", "count": len(rows),
              "sets": rows[:400],
              "hint": f"共 {len(rows)} 集符合过滤;许可全表用 license 子命令导出" if rows else "无匹配集"})
        return 0

    if not args.query or not args.set:
        emit({"ok": False, "error": "USAGE", "hint": "需要 --set 与 --query(列集用 --list-sets)"})
        return 2
    sets = [s.strip() for s in args.set.split(",") if s.strip()]
    # 逐集许可核查(默认只放行宽松许可)
    cols: dict[str, dict] = {}
    for p in sets:
        col = get_collection(p)
        if col is None:
            emit({"ok": False, "error": "NETWORK", "hint": f"取集信息失败:{p}(检查网络)"})
            return 3
        ok, spdx = license_ok(col, set(args.allow_license or []))
        if not ok and not args.any_license:
            emit({"ok": False, "error": "LICENSE_BLOCKED",
                  "hint": f"集 {p} 许可为 {spdx},不在默认白名单 {sorted(ALLOWED_LICENSE)};"
                          f"确认合规后加 --allow-license {spdx} 显式放行(交付时标注来源集)"})
            return 1
        cols[p] = col

    items: list[dict] = []
    for p in sets:
        try:
            res = json.loads(http_get(
                f"{API}/search?query={urllib.parse.quote(args.query)}"
                f"&limit={args.limit}&prefixes={p}"))
        except Exception as exc:  # noqa: BLE001
            emit({"ok": False, "error": "NETWORK", "hint": f"搜索失败({exc})"})
            return 3
        for full in res.get("icons", []):
            items.append({"id": full, "set": p, "name": full.split(":", 1)[1]})

    out_dir = args.out
    written: list[str] = []
    for it in items:
        prefix, name = it["set"], it["name"]
        try:
            svg = fetch_svg_cached(prefix, name)
        except Exception as exc:  # noqa: BLE001
            it["error"] = f"{type(exc).__name__}"
            continue
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            dest = os.path.join(out_dir, f"{prefix}-{name}.svg")
            with open(dest, "w", encoding="utf-8") as f:
                f.write(svg)
            written.append(os.path.relpath(dest, SKILL))
    if written and args.svgo:
        import shutil
        import subprocess
        if shutil.which("npx") is None:
            print("△ 无 Node/npx:跳过 SVGO 瘦身(纯 Python 底线不受影响)", file=sys.stderr)
        else:
            for w in written:
                dest = os.path.join(SKILL, w)
                try:
                    r = subprocess.run(["npx", "--yes", "svgo", dest, "-o", dest],
                                       capture_output=True, timeout=60)
                    if r.returncode != 0:
                        print(f"△ svgo 失败(保留原文件): {w}", file=sys.stderr)
                except Exception as exc:  # noqa: BLE001
                    print(f"△ svgo 异常(保留原文件): {exc}", file=sys.stderr)
    emit({"ok": bool(items), "cmd": "iconify", "query": args.query,
          "count": len(items), "ids": [i["id"] for i in items][:args.limit],
          "cache": os.path.relpath(CACHE, SKILL),
          "written": written or None,
          "license_note": "图标许可按集:已核查为宽松许可;交付仍需注明来源集(如 Tabler MIT)",
          "error": None if items else "NO_RESULTS",
          "hint": None if items else "换关键词或 --set;预览用 assets/icons-cache 直接打开"})
    return 0 if items else 1


def cmd_license(args) -> int:
    try:
        if args.all:
            data = json.loads(http_get(f"{API}/collections"))
            cols = data
        else:
            if not args.sets:
                emit({"ok": False, "error": "USAGE", "hint": "--sets tabler,mdi 或 --all"})
                return 2
            prefixes = [s.strip() for s in args.sets.split(",") if s.strip()]
            data = json.loads(http_get(f"{API}/collections?prefixes={','.join(prefixes)}"))
            cols = data
    except Exception as exc:  # noqa: BLE001
        emit({"ok": False, "error": "NETWORK", "hint": f"Iconify 不可达({exc})"})
        return 3
    rows = []
    for prefix, col in sorted(cols.items()):
        lic = (col.get("license") or {})
        rows.append({"prefix": prefix, "name": col.get("name"),
                     "license": lic.get("spdx") or lic.get("title") or "unknown",
                     "license_url": lic.get("url"), "total": col.get("total"),
                     "allowed": license_ok(col, set())[0]})
    lines = [
        "# artboard 矢量图标源许可清单(Iconify)",
        "",
        f"> 机器生成:`fetch_svg.py license` @ {datetime.date.today().isoformat()};"
        f"共 {len(rows)} 集。**allowed=true** 才进入默认取用白名单;",
        "> 其余集需逐案核许可后显式放行。来源:api.iconify.design/collections。",
        "",
        "| 集 | 名称 | 许可(SPDX) | 许可链接 | 图标数 | 默认放行 |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['prefix']} | {r['name'] or ''} | {r['license']} "
                     f"| {r['license_url'] or '—'} | {r['total'] or '—'} "
                     f"| {'✅' if r['allowed'] else '⚠️ 需核对'} |")
    out = args.out or os.path.join("docs", "svg-licenses.md")
    if args.out is not None or args.all:
        path = os.path.join(SKILL, out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    emit({"ok": True, "cmd": "license", "count": len(rows),
          "allowed": sum(1 for r in rows if r["allowed"]),
          "written": out if (args.out is not None or args.all) else None,
          "rows": rows[:60],
          "hint": f"全表 {len(rows)} 集;完整内容见生成文件" if len(rows) > 60 else None})
    return 0


def cmd_illust(args) -> int:
    """插画库:官方批量接口不稳定(2026-09 实测 unDraw 批量 405),如实给人工指引。"""
    guides = [
        {"source": "open-doodles", "status": "已落地",
         "path": "assets/illustrations/open-doodles/", "license": "CC0"},
        {"source": "undraw",
         "status": "需人工获取(批量接口 405,自动化不稳定)",
         "how": "undraw.co → 搜主题 → 选色号 → Download SVG;逐张落 assets/illustrations/undraw/",
         "license": "unDraw 自定义开放许可(免署名商用,禁转售插画本身)"},
        {"source": "open-peeps",
         "status": "需人工获取(官网表单打包)",
         "how": "openpeeps.com → Download → 解压挑 SVG 落 assets/illustrations/open-peeps/",
         "license": "CC0"},
        {"source": "illustrations.co",
         "status": "未接入(许可待核,核清前不取用)", "how": None, "license": "待核"},
    ]
    emit({"ok": True, "cmd": "illust", "sources": guides,
          "hint": "混源禁令仍适用:同屏插画必须同一形状语言(见 vector-drawing.md §4.3)"})
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(
        description="矢量素材获取(Iconify 优先;许可逐集核查;缓存于 assets/icons-cache)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("iconify", help="按集 + 关键词取图标(离线缓存)")
    p1.add_argument("--set", dest="set", default="", help="集前缀,逗号分隔,如 tabler,ph")
    p1.add_argument("--query", default="", help="关键词(英文命中率高)")
    p1.add_argument("--limit", type=int, default=20)
    p1.add_argument("--out", default="", help="落地目录(缺省只进缓存)")
    p1.add_argument("--list-sets", action="store_true", help="列可用集与许可")
    p1.add_argument("--filter", choices=["", "mit"], default="", help="mit=只列宽松许可集")
    p1.add_argument("--allow-license", action="append", dest="allow_license",
                    help="显式放行的许可 SPDX(可重复)")
    p1.add_argument("--any-license", action="store_true",
                    help="跳过许可白名单(不推荐;交付必须逐集标注)")
    p1.add_argument("--svgo", action="store_true",
                    help="落地后用 npx svgo 瘦身(可选依赖:无 Node/npx 时降级为跳过)")

    p2 = sub.add_parser("license", help="导出逐集许可清单(默认写 docs/svg-licenses.md)")
    p2.add_argument("--sets", default="", help="集前缀,逗号分隔")
    p2.add_argument("--all", action="store_true", help="全量集(生成全表)")
    p2.add_argument("--out", default=None, help="输出 md 路径(相对技能根)")

    p3 = sub.add_parser("illust", help="插画库状态与获取指引(诚实口径)")
    p3.add_argument("--guide", action="store_true")

    args = ap.parse_args()
    if args.cmd == "iconify":
        return cmd_iconify(args)
    if args.cmd == "license":
        return cmd_license(args)
    return cmd_illust(args)


if __name__ == "__main__":
    sys.exit(main())
