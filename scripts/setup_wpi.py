"""artboard 环境部署:一键部署 WPI 渲染引擎(CLI 单文件版,由 artboard 发行页统一分发)。

用法:
  python setup_wpi.py                      # 默认:部署 WPI-noGUI-cli.exe(约 63MB,推荐)
  python setup_wpi.py --dir D:\tools      # 指定部署目录
  python setup_wpi.py --source-install     # 高级:克隆 WPI 源码 + 装 Python 依赖(export.py 主路径)

说明:
- CLI 版是无 GUI 单文件(Playwright 驱动系统 Edge/Chrome,不随附 FFmpeg),
  由 artboard 发行页统一分发版本;手动更新:下载新 exe 覆盖即可。
- 源码模式供 export.py 的 Python API 路径使用,功能相同、需要 pip 依赖。
部署后会把路径写入 config.json(wpi_cli_exe / wpi_path)。
"""

import argparse
import json
import os
import sys
import urllib.request

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
from _config import cfg, CONFIG_PATH  # noqa: E402

RELEASE_BASE = ("https://github.com/GreenChennai/artboard/releases/download/"
                "wpi-cli-v3.2.0-3582225")
CLI_EXE = "WPI-noGUI-cli.exe"
CLI_URL = f"{RELEASE_BASE}/{CLI_EXE}"
CLI_README = f"{RELEASE_BASE}/README-CLI.md"
DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "artboard-tools", "WPI")
WPI_REPO_ZIP = "https://codeload.github.com/GreenChennai/WPI/zip/refs/heads/main"


def ok_source(path: str) -> bool:
    return os.path.isfile(os.path.join(path, "src", "core", "controller.py"))


def write_config(patch: dict) -> None:
    data = {}
    if os.path.isfile(CONFIG_PATH):
        data = json.load(open(CONFIG_PATH, encoding="utf-8"))
    data.update(patch)
    json.dump(data, open(CONFIG_PATH, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def download(url: str, dest: str) -> None:
    def report(blocks, bs, total):
        if total > 0 and blocks % 100 == 0:
            print(f"\r  {blocks * bs // 1024 // 1024}/{total // 1024 // 1024} MB",
                  end="", flush=True)
    urllib.request.urlretrieve(url, dest, reporthook=report)
    print()


def deploy_cli(target_dir: str) -> None:
    os.makedirs(target_dir, exist_ok=True)
    exe = os.path.join(target_dir, CLI_EXE)
    print(f"[1/2] 下载 {CLI_EXE}(约 63MB,artboard 发行页统一分发)…")
    download(CLI_URL, exe)
    try:
        download(CLI_README, os.path.join(target_dir, "README-CLI.md"))
    except Exception:  # noqa: BLE001 — 说明文件非必需
        pass
    write_config({"wpi_cli_exe": exe})
    print(f"[2/2] 完成!已写入 config.json: wpi_cli_exe = {exe}")
    print("  · 需要 Edge 或 Chrome(系统已装即可);FFmpeg 可选,未装则 MP4 不可用。")


def deploy_source(target_dir: str) -> None:
    import subprocess
    print(f"[1/3] 下载 WPI 源码(main.zip)…")
    os.makedirs(target_dir, exist_ok=True)
    tmp_zip = os.path.join(target_dir, "_wpi.zip")
    download(WPI_REPO_ZIP, tmp_zip)
    print("[2/3] 解压…")
    import zipfile
    with zipfile.ZipFile(tmp_zip) as z:
        z.extractall(target_dir)
    os.remove(tmp_zip)
    inner = os.path.join(target_dir, "WPI-main")
    if os.path.isdir(inner):
        for item in os.listdir(inner):
            os.rename(os.path.join(inner, item), os.path.join(target_dir, item))
        os.rmdir(inner)
    if not ok_source(target_dir):
        print(f"[FAIL] 部署后未找到 src/core/controller.py: {target_dir}")
        sys.exit(1)
    print("[3/3] 安装 Python 依赖(playwright + Pillow)…")
    r = subprocess.run([sys.executable, "-m", "pip", "install",
                        "playwright>=1.40", "Pillow>=10.0"])
    if r.returncode != 0:
        print("[WARN] 依赖安装失败,请手动: pip install playwright Pillow")
    write_config({"wpi_path": target_dir})
    print(f"完成!wpi_path 已写入 config.json: {target_dir}")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="")
    p.add_argument("--source-install", action="store_true",
                   help="高级:部署 WPI 源码版(Python API 路径)")
    args = p.parse_args()

    # 已有任一形态即通过
    cli_exe = cfg("wpi_cli_exe")
    if cli_exe and os.path.isfile(cli_exe) and not args.source_install:
        print(f"[OK] WPI CLI 已部署: {cli_exe}")
        return 0
    if ok_source(cfg("wpi_path")) and not args.source_install:
        print(f"[OK] WPI 源码版已就绪: {cfg('wpi_path')}")
        return 0

    target = args.dir or DEFAULT_DIR
    if args.source_install:
        deploy_source(target)
    else:
        deploy_cli(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
