"""artboard 字体按需下载:读 fonts/download.json,把本地缺失的字体取回。

用法:
  python fetch_font.py              # 列出全部字体的本地状态
  python fetch_font.py <目录名>...  # 下载指定字体(如 misans alibaba-puhuiti)

说明:
- 仓库只随附每类一款代表字体(in_repo=true);其余字体按需下载,文件落在 fonts/<目录>/。
- zip_url + zip_files:从压缩包内提取指定文件。
- manual 条目无直链,打印人工下载指引。
"""

import json
import os
import sys
import zipfile

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(SKILL_DIR, "fonts")
MANIFEST = os.path.join(FONTS_DIR, "download.json")


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def load_manifest() -> dict:
    with open(MANIFEST, encoding="utf-8") as f:
        raw = json.load(f)
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def local_state(entry: dict, d: str) -> tuple[bool, list[str]]:
    missing = [f for f in entry.get("files", [])
               if not os.path.isfile(os.path.join(FONTS_DIR, d, f))]
    return (not missing), missing


def fetch(d: str, entry: dict) -> str:
    """下载单个字体目录,返回状态描述。已有完整文件则跳过。"""
    ok, missing = local_state(entry, d)
    if ok:
        return "SKIP: 本地已齐全"
    import urllib.request
    os.makedirs(os.path.join(FONTS_DIR, d), exist_ok=True)
    headers = entry.get("headers", {})
    proxy = os.environ.get("ARTBOARD_PROXY") or None

    def get(url: str, dest: str | None = None) -> bytes:
        last = None
        for attempt in (1, 2):
            try:
                req = urllib.request.Request(url, headers=headers)
                handlers = []
                if proxy:
                    handlers.append(urllib.request.ProxyHandler(
                        {"http": proxy, "https": proxy}))
                with urllib.request.build_opener(*handlers).open(req, timeout=300) as r:
                    data = r.read()
                if dest:
                    with open(dest, "wb") as f:
                        f.write(data)
                return data
            except Exception as exc:  # noqa: BLE001 — 大文件+跨境网络,重试一次
                last = exc
        raise last

    if entry.get("manual"):
        return f"MANUAL: 无直链,请从 {entry['manual']} 手动下载 {entry.get('files')}"

    if entry.get("expand"):  # 多直链模板展开(如普惠体)
        for spec in entry["expand"]:
            url = entry["url"].format(**spec)
            dest = os.path.join(FONTS_DIR, d, spec["f"])
            get(url, dest)
        return f"OK: {len(entry['expand'])} 个文件已下载"

    url = entry.get("url")
    if not url:
        return "MANUAL: 清单未配置 url"
    if entry.get("zip_files"):
        tmp = os.path.join(FONTS_DIR, d, "_pack.zip")
        get(url, tmp)
        with zipfile.ZipFile(tmp) as z:
            for spec in entry["zip_files"]:
                dest_name, _, inner_suffix = spec.partition("=")
                inner_suffix = inner_suffix or dest_name
                for name in z.namelist():
                    if name.replace("\\", "/").endswith(inner_suffix):
                        data = z.read(name)
                        with open(os.path.join(FONTS_DIR, d, dest_name), "wb") as f:
                            f.write(data)
                        break
        os.remove(tmp)
        ok, missing = local_state(entry, d)
        return "OK" if ok else f"PARTIAL: 仍缺 {missing}"
    else:
        get(url, os.path.join(FONTS_DIR, d, entry["files"][0]))
        return "OK"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    targets = sys.argv[1:]
    manifest = load_manifest()

    if not targets:
        print(f"{'目录':<20}{'仓库':<6}{'本地':<6}说明")
        for d, e in manifest.items():
            ok, missing = local_state(e, d)
            print(f"{d:<20}{'是' if e.get('in_repo') else '否':<6}"
                  f"{'有' if ok else '缺':<6}"
                  f"{d if not missing else ','.join(missing)}")
        print("\n用法: python fetch_font.py <目录名>...  下载缺失字体")
        return 0

    results = []
    for d in targets:
        e = manifest.get(d)
        if not e:
            results.append({"dir": d, "error": "清单中无此字体目录"})
            continue
        try:
            status = fetch(d, e)
            results.append({"dir": d, "status": status})
        except Exception as exc:  # noqa: BLE001
            results.append({"dir": d, "error": f"{type(exc).__name__}: {str(exc)[:160]}"})

    ok = all("error" not in r for r in results)
    emit({"ok": ok, "results": results,
          "hint": "下载后用 add_font.py 登记新目录;查看状态直接跑 fetch_font.py 不带参数"})
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
