"""Kiln 引擎一键部署(v1.9.0 起,WPI 已退役)。

优先级:
  1. 已配置(config.json: kiln_cli_exe / env ARTBOARD_KILN_CLI)→ 直接可用
  2. 仓库内自动探测:<工作区>/VellumBench/dist/Kiln-noGUI-CLI.exe
  3. --from <url> 手动下载(默认指向 artboard 发行页的 kiln-cli 资产)
  4. 上游构建:克隆 VellumBench → cargo build -p vb_kiln --release --bin kiln-cli

用法:
  python setup_kiln.py                # 探测 + 写 config.json + 自检
  python setup_kiln.py --from <url>   # 首次部署:从指定 URL 下载后写入
  python setup_kiln.py --force        # 升级:忽略已装引擎,重新下载覆盖
  python setup_kiln.py --exe <路径>   # 用手动下载的 exe(可与 --force 并用)

发行同步(v0.14.1 轮):发行资产带 sha256,这里**强制校验**再写 config.json。
`download()` 只保证字节流落盘,不保证落的是 exe —— 代理截断、把 404 的 HTML
存成 .exe、CDN 半截文件,都会得到一个"下载成功"的坏引擎,而 `--version` 探测
失败只报「继续自检」,于是坏引擎被写进 config,后续每次导出才炸。
更糟的是 GB 镜像正式版**故意不给 sha256**(只承诺可复现),所以拿别的构建冒充
本版也校验不出来 —— 这条只能靠记 baseline 版本号兜(见 BASELINE)。
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
from _config import cfg, write_config, near_workspace  # noqa: E402

CANDIDATES = [
    near_workspace(os.path.join("VellumBench", "dist", "Kiln-noGUI-CLI.exe")),
    near_workspace(os.path.join("VellumBench", "target", "release", "kiln-cli.exe")),
    near_workspace(os.path.join("artboard-tools", "Kiln-noGUI-CLI.exe")),
]

SELF_CHECK = ["--help"]

# ── 发行同步(改版本时三处同改:URL / SHA256 / BASELINE)────────────────────
KILN_VERSION = "0.15.0"
RELEASE_URL = ("https://github.com/GreenChennai/artboard/releases/download/"
               "kiln-cli-v" + KILN_VERSION + "/Kiln-noGUI-CLI.exe")
# 正式版才承诺 sha256(GB 镜像「可复现但无 sha256」是另一条路,见文档头注)
RELEASE_SHA256 = "14aeea5e76606c347b68dcdbc3a04874fb258f86d7443f3c9c32a863fca2c0cf"
# 已知基线:低于它 export.py 的参数面/语义对不上(KILN_TOO_OLD 判定用)
BASELINE = (0, 15, 0)


def probe() -> str:
    cli = cfg("kiln_cli_exe")
    if cli and os.path.isfile(cli):
        return cli
    for c in CANDIDATES:
        if c and os.path.isfile(c):
            return c
    return ""


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def read_version(exe: str) -> str:
    """`Kiln-noGUI-cli 0.14.1` → `0.14.1`;探不到返回空串(不猜)。"""
    try:
        r = subprocess_run([exe, "--version"])
    except Exception:  # noqa: BLE001 —— 探不到版本不是致命错,交给基线判定
        return ""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", r)
    return m.group(0) if m else ""


def vtuple(v: str):
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except Exception:  # noqa: BLE001
        return (0, 0, 0)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Kiln 引擎部署 / 升级")
    ap.add_argument("--from", dest="from_url", default=RELEASE_URL,
                    help="从 URL 下载 Kiln-noGUI-CLI.exe(默认 artboard 发行页最新资产)")
    ap.add_argument("--exe", dest="exe", default="",
                    help="指向已手动下载的 Kiln-noGUI-CLI.exe(跳过下载,写 config 并自检)")
    ap.add_argument("--sha256", dest="sha256", default="",
                    help="配合 --from 校验下载产物(默认:内置 RELEASE_SHA256;"
                         "发行资产换版时同步更新)")
    ap.add_argument("--force", action="store_true",
                    help="已装可用引擎时也重新下载/覆盖(升级路径)")
    args = ap.parse_args()

    # probe() 命中即返回,会让 --from 下载分支被短路,于是永远只能首次部署、
    # 升不上去。--force 时直接跳过探测走覆盖路径。
    found = "" if args.force else probe()
    if args.force:
        print("[i] --force:忽略已装引擎,按 --exe / --from 重新部署")
    if args.exe:
        if os.path.isfile(args.exe):
            found = os.path.abspath(args.exe)
        else:
            print(f"[X] --exe 指向的文件不存在: {args.exe}")
            return 2
    elif not found and args.from_url:
        # 升级就地覆盖已配置的那份;首次部署落默认 artboard-tools
        dest = cfg("kiln_cli_exe") or ""
        if not (dest and os.path.isfile(dest)):
            dest = near_workspace(os.path.join("artboard-tools", "Kiln-noGUI-CLI.exe"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        # 只对**内置发行 URL** 用内置校验值:用户自带 --from 的资产没有承诺过
        # sha256,拿官方值去比对第三方构建必然误报。
        want = (args.sha256 or "").strip().lower()
        if not want and args.from_url.rstrip("/") == RELEASE_URL.rstrip("/"):
            want = RELEASE_SHA256
        if want:
            print(f"下载 {args.from_url} → {dest}")
        else:
            print(f"下载 {args.from_url} → {dest}(非官方发行资产,跳过 sha256 校验)")
        try:
            from _download import download
            download(args.from_url, dest)
        except Exception as exc:  # noqa: BLE001
            print(f"[X] 下载失败: {exc}")
            return 1
        if want:
            got = sha256_of(dest)
            if got != want:
                # 不删:留着好比对与复现。只**拒绝写 config**,免得坏引擎生效。
                print(f"[X] sha256 不符,已拒绝写入 config(产物保留在 {dest})")
                print(f"    期望 {want}")
                print(f"    实际 {got}")
                print("    多为下载被截断/代理改写/CDN 半截文件;重试,或用 --sha256 <值> 覆盖")
                return 3
            print(f"[OK] sha256 校验通过({got[:16]}…)")
        found = dest

    if not found:
        print("[X] 未找到 Kiln 引擎。任选其一:")
        print("    1) 克隆上游并构建:git clone https://github.com/GreenChennai/VellumBench")
        print("       cd VellumBench && cargo build -p vb_kiln --release --bin kiln-cli")
        print("       产物:target/release/kiln-cli.exe(复制到 dist/Kiln-noGUI-CLI.exe)")
        print("    2) 从 artboard 发行页下载 Kiln-noGUI-CLI.exe 后:")
        print("       python setup_kiln.py --force --from <exe 直链>")
        return 1

    # 引擎版本 vs 基线:低版本**照样能用**(能导 PNG),但参数面/语义对不上 ——
    # 0.14.1 起 --max-wait 从静默忽略变成真总预算,拿老引擎配新参数会静默出废图。
    # 这里只告警不拦(用户可能故意用老版对比),但要说清差在哪。
    ver = read_version(found)
    if ver and vtuple(ver) < BASELINE:
        print(f"[!] 引擎版本 {ver} 低于已知基线 {'.'.join(map(str, BASELINE))}"
              f"(当前发行版 {KILN_VERSION})。")
        print("    export.py 会按参数面报 KILN_TOO_OLD 而不是静默用错语义;")
        print("    升级:python scripts/setup_kiln.py --force")
    elif ver:
        print(f"[OK] 引擎版本 {ver}(基线 {'.'.join(map(str, BASELINE))})")

    write_config({"kiln_cli_exe": found})
    print(f"[OK] Kiln 引擎:{found}")
    print("[OK] 已写入 config.json:kiln_cli_exe")
    # 超时/执行失败分报,不再宽 except 一律「跳过」
    import subprocess as _sp
    try:
        r = subprocess_run([found, "selfcheck"])
        print(f"[OK] 引擎自检:{r}")
    except _sp.TimeoutExpired:
        print("△ 引擎自检超时(120s),已跳过:引擎通常仍可导出,建议人工跑一次 selfcheck")
    except OSError as exc:
        print(f"△ 引擎自检执行失败({exc}):检查 {found} 是否完整,必要时重跑 setup_kiln.py")
    return 0


def subprocess_run(cmd):
    import subprocess
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    return r.stdout.decode("utf-8", errors="replace").strip() or "(无输出)"


if __name__ == "__main__":
    sys.exit(main())
