"""取图薄壳:import 复用 scripts/fetch_asset.py,不复制实现(单一真相源,ADR-AB-E03)。

统一出参 schema(与 fetch_asset candidate 字段一一映射):
  {id, title, url, thumbnail, width, height, author, source, license, risk, page_url}
"""

from __future__ import annotations

import os
import re
import sys

_SKILL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))  # …/mcp/artboard-mcp/src/artboard_mcp/ → skill 根
_SCRIPTS = os.path.join(_SKILL, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import fetch_asset as fa  # noqa: E402


def normalize(c: dict, idx: int) -> dict:
    """fetch_asset candidate → MCP 统一 schema。缺字段给 None,不编造。"""
    return {
        "id": f"{c.get('source', 'src')}-{idx:03d}",
        "title": c.get("name_hint") or c.get("author") or "",
        "url": c.get("url") or "",
        "thumbnail": c.get("fallback_url") or c.get("url") or "",
        "width": None, "height": None,  # 搜索阶段拿不到真实像素,交给 probe 体检
        "author": c.get("author") or "",
        "source": c.get("source") or "",
        "license": c.get("license") or "不确定",
        "risk": bool(c.get("risk")),
        "page_url": c.get("page_url") or "",
    }


def search(query: str, sources: list[str] | None = None, orientation: str = "",
           limit: int = 6, image_type: str = "photo") -> dict:
    """多源搜索。sources 缺省走 fetch_asset.AUTO_ORDER(干净 API 优先)。"""
    if not query:
        return {"ok": False, "error": "USAGE", "hint": "query 必填(bridge 通道除外)"}
    order = sources or list(fa.AUTO_ORDER)
    unknown = [s for s in order if s not in fa.SOURCES]
    if unknown:
        return {"ok": False, "error": "UNKNOWN_SOURCE",
                "hint": f"未知来源 {unknown};可用:{sorted(fa.SOURCES)}"}
    items: list[dict] = []
    for s in order:
        try:
            cands = fa.SOURCES[s](query, limit, orientation, image_type)
        except Exception as exc:  # noqa: BLE001 — 单源失败不断链
            items.append(normalize({"source": s, "url": "", "author": "",
                                    "license": f"该源异常({type(exc).__name__})", "risk": True},
                                   len(items)))
            continue
        items.extend(normalize(c, len(items)) for c in cands)
        if len(items) >= limit:
            break
    items = items[:limit]
    return {"ok": bool(items), "error": None if items else "NO_RESULTS",
            "hint": None if items else "所有来源无结果;换关键词或加 sources(如 miankoutu/pinterest)",
            "items": items}


def download(items: list[dict], theme: str) -> dict:
    """按 fetch_asset 的落盘 + CREDITS 登记纪律下载(风险前缀在 download_one 内统一处理)。"""
    if not theme:
        return {"ok": False, "error": "USAGE", "hint": "theme 必填(素材库主题目录名)"}
    if len(items) > 20:
        return {"ok": False, "error": "BUDGET",
                "hint": "单次下载 ≤20 张(数量预算);先检索再 Read 挑图,别整页搬"}
    if not items:
        return {"ok": False, "error": "USAGE",
                "hint": "items 为空:先 assets_search 挑图再下载"}
    studio = fa.cfg("studio_dir", fa.DEFAULT_STUDIO)
    theme_dir = os.path.join(studio, "materials", theme)
    os.makedirs(theme_dir, exist_ok=True)
    files, credits_rows, errors = [], [], []
    import datetime
    credits = os.path.join(theme_dir, "CREDITS.md")
    if not os.path.isfile(credits):
        with open(credits, "w", encoding="utf-8") as f:
            f.write(f"# CREDITS · {theme}\n\n"
                    "| 文件 | 来源 | 作者 | 授权 | 来源页 | 日期 |\n|---|---|---|---|---|---|\n")
    import base64 as _b64
    for i, it in enumerate(items, 1):
        # 页内 fetch 通道(svgrepo/vector4free 等_CF 站):字节已回传,直接落盘
        if it.get("content_b64"):
            try:
                data = _b64.b64decode(it["content_b64"])
            except Exception as exc:  # noqa: BLE001
                errors.append({"id": it.get("id"), "error": f"base64: {exc}"})
                continue
            cand = {"source": it.get("source") or "bridge", "risk": bool(it.get("risk")),
                    "author": it.get("author") or "unknown",
                    "license": it.get("license") or "不确定(浏览器采集)",
                    "page_url": it.get("page_url") or it.get("link") or ""}
            base = f"{theme}-{cand['source']}-{i:02d}"
            if cand["risk"]:
                base = fa.RISK_PREFIX + base
            name = base + fa.sniff_ext(data)
            with open(os.path.join(theme_dir, name), "wb") as f:
                f.write(data)
            row = (f"| {name} | {cand['source']} | {cand['author']} | {cand['license']} "
                   f"| {cand['page_url']} | {datetime.date.today().isoformat()} |" + chr(10))
            with open(credits, "a", encoding="utf-8") as f:
                f.write(row)
            files.append({"file": os.path.join(theme_dir, name), "source": cand["source"],
                          "license": cand["license"], "risk": cand["risk"],
                          "page_url": cand["page_url"]})
            continue
        url = it.get("url") or ""
        if not url:
            continue
        cand = {"source": it.get("source") or "mcp", "url": url,
                "page_url": it.get("page_url") or it.get("link") or "",
                "author": it.get("author") or "unknown",
                "license": it.get("license") or "不确定(浏览器采集)",
                "risk": bool(it.get("risk"))}
        page = it.get("page_url") or it.get("link") or ""
        if page.startswith("http"):  # 图床防盗链:Referer = 来源页站点(花瓣/新浪系必需)
            m = re.match(r"(https?://[^/]+/)", page)
            if m:
                cand["dl_headers"] = {"Referer": m.group(1)}
        base = f"{theme}-{cand['source']}-{i:02d}"
        try:
            name, err = fa.download_one(cand, theme_dir, base)
        except Exception as exc:  # noqa: BLE001
            name, err = "", f"{type(exc).__name__}: {exc}"
        if err:
            errors.append({"id": it.get("id"), "url": url, "error": err})
            continue
        row = (f"| {name} | {cand['source']} | {cand['author']} | {cand['license']} "
               f"| {cand['page_url']} | {datetime.date.today().isoformat()} |\n")
        with open(credits, "a", encoding="utf-8") as f:
            f.write(row)
        files.append({"file": os.path.join(theme_dir, name), "source": cand["source"],
                      "license": cand["license"], "risk": cand["risk"],
                      "page_url": cand["page_url"]})
    risk_files = [f for f in files if f["risk"]]
    return {"ok": bool(files), "error": None if files else "ALL_FAILED",
            "files": files, "credits": credits, "risk_files": risk_files, "errors": errors}
