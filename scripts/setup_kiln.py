"""Kiln 引擎一键部署(v1.9.0 起,WPI 已退役)。

优先级:
  1. 已配置(config.json: kiln_cli_exe / env ARTBOARD_KILN_CLI)→ 直接可用
  2. 仓库内自动探测:<工作区>/VellumBench/dist/Kiln-noGUI-CLI.exe
  3. --from <url> 手动下载(默认指向 artboard 发行页的 kiln-cli 资产)
  4. 上游构建:克隆 VellumBench → cargo build -p vb_kiln --release --bin kiln-cli

用法:
  python setup_kiln.py                # 探测 + 写 config.json + 自检
  python setup_kiln.py --from <url>   # 从指定 URL 下载 exe 后再探测写入
"""

import argparse
import json
import os
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


def probe() -> str:
    cli = cfg("kiln_cli_exe")
    if cli and os.path.isfile(cli):
        return cli
    for c in CANDIDATES:
        if c and os.path.isfile(c):
            return c
    return ""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Kiln 引擎部署")
    default_url = "https://github.com/GreenChennai/artboard/releases/download/kiln-cli-v0.8.0/Kiln-noGUI-CLI.exe"
    ap.add_argument("--from", dest="from_url", default=default_url,
                    help="从 URL 下载 Kiln-noGUI-CLI.exe(默认 artboard 发行页最新资产)")
    ap.add_argument("--exe", dest="exe", default="",
                    help="指向已手动下载的 Kiln-noGUI-CLI.exe(跳过下载,写 config 并自检)")
    args = ap.parse_args()

    found = probe()
    if not found and args.exe:
        if os.path.isfile(args.exe):
            found = os.path.abspath(args.exe)
        else:
            print(f"[X] --exe 指向的文件不存在: {args.exe}")
            return 2
    if not found and args.from_url:
        dest = near_workspace(os.path.join("artboard-tools", "Kiln-noGUI-CLI.exe"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        print(f"下载 {args.from_url} → {dest}")
        try:
            from _download import download
            download(args.from_url, dest)
        except Exception as exc:  # noqa: BLE001
            print(f"[X] 下载失败: {exc}")
            return 1
        found = dest

    if not found:
        print("[X] 未找到 Kiln 引擎。任选其一:")
        print("    1) 克隆上游并构建:git clone https://github.com/GreenChennai/VellumBench")
        print("       cd VellumBench && cargo build -p vb_kiln --release --bin kiln-cli")
        print("       产物:target/release/kiln-cli.exe(复制到 dist/Kiln-noGUI-CLI.exe)")
        print("    2) 从 artboard 发行页下载 Kiln-noGUI-CLI.exe 后:")
        print("       python setup_kiln.py --from <exe 直链>")
        return 1

    write_config({"kiln_cli_exe": found})
    print(f"[OK] Kiln 引擎:{found}")
    print("[OK] 已写入 config.json:kiln_cli_exe")
    # H 修:超时/执行失败分报,不再宽 except 一律「跳过」
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
