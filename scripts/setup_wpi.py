r"""artboard 环境部署:从 GitHub 下载并部署 WPI 渲染引擎。

用法:
  python setup_wpi.py                 # 检查并部署到 config 的 wpi_path(或默认)
  python setup_wpi.py --dir D:\wpi    # 指定部署目录

做什么:
  1. 检查 wpi_path 是否已有可用 WPI(src/core/controller.py 存在即通过);
  2. 没有 → 从 https://github.com/GreenChennai/WPI (公开仓库)下载 main 分支 zip;
  3. 解压到目标目录,补装 Python 依赖(playwright + Pillow;PySide6 可选,仅 GUI 用);
  4. 把路径写回 Skill 的 config.json;
  5. 提示 playwright 浏览器:WPI 走系统 Edge/Chrome,无需下载浏览器;
     若机器没有 Edge/Chrome,请安装其中之一。
"""

import argparse
import io
import json
import os
import sys
import urllib.request
import zipfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
from _config import cfg, CONFIG_PATH  # noqa: E402

REPO_ZIP = "https://codeload.github.com/GreenChennai/WPI/zip/refs/heads/main"
DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "artboard-tools", "WPI")


def ok(path: str) -> bool:
    return os.path.isfile(os.path.join(path, "src", "core", "controller.py"))


def find_existing() -> str | None:
    """本地已装 WPI 的常见位置探测。"""
    cands = [cfg("wpi_path"), r"E:\平日资料\GitHub\WPI",
             DEFAULT_DIR, os.path.join(os.path.dirname(cfg("studio_dir") or os.sep), "WPI")]
    for c in cands:
        if c and ok(c):
            return c
    return None


def write_config_wpi(path: str) -> None:
    data = {}
    if os.path.isfile(CONFIG_PATH):
        data = json.load(open(CONFIG_PATH, encoding="utf-8"))
    data["wpi_path"] = path
    json.dump(data, open(CONFIG_PATH, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="")
    args = p.parse_args()

    existing = find_existing()
    if existing and not args.dir:
        write_config_wpi(existing)
        print(f"[OK] 本机已有 WPI: {existing}(已写入 config.json)")
        return 0

    target = args.dir or DEFAULT_DIR
    if ok(target):
        write_config_wpi(target)
        print(f"[OK] WPI 已在 {target}")
        return 0

    print(f"[1/4] 下载 WPI(main.zip)…")
    os.makedirs(target, exist_ok=True)
    tmp_zip = os.path.join(target, "_wpi.zip")
    urllib.request.urlretrieve(REPO_ZIP, tmp_zip)
    print("[2/4] 解压…")
    with zipfile.ZipFile(tmp_zip) as z:
        z.extractall(target)
    os.remove(tmp_zip)
    # 仓库解包出 WPI-main/ 一层,把内容提到 target
    inner = os.path.join(target, "WPI-main")
    if os.path.isdir(inner):
        for item in os.listdir(inner):
            os.rename(os.path.join(inner, item), os.path.join(target, item))
        os.rmdir(inner)
    if not ok(target):
        print(f"[FAIL] 部署后未找到 src/core/controller.py,请检查 {target}")
        return 1

    print("[3/4] 安装 Python 依赖(playwright + Pillow)…")
    import subprocess
    deps = ["playwright>=1.40", "Pillow>=10.0"]
    r = subprocess.run([sys.executable, "-m", "pip", "install", *deps])
    if r.returncode != 0:
        print("[WARN] 依赖安装失败,请手动: pip install playwright Pillow")
        return 1

    write_config_wpi(target)
    print(f"[4/4] 完成!wpi_path 已写入 config.json: {target}")
    print("  · WPI 走系统 Edge/Chrome 渲染,无需额外下载浏览器;")
    print("  · 若机器没有 Edge/Chrome,请安装其中之一后重跑 preflight。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
