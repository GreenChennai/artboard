"""artboard 环境部署:一键下载部署 FFmpeg(Windows)。

用法:
  python setup_ffmpeg.py                # 检查并部署;路径写回 config.json
  python setup_ffmpeg.py --dir D:\tools # 指定部署目录

来源:gyan.dev 的 essentials 构建(官方认可发行渠道,免费)。
仅下载 ffmpeg.exe(解码/编码主力);ffprobe 如需可从同包手动取。
"""

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
from _config import cfg, CONFIG_PATH  # noqa: E402

SOURCE_ZIP = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "artboard-tools", "ffmpeg")


def ok(path: str) -> bool:
    if not path:
        return False
    exe = path if path.lower().endswith(".exe") else os.path.join(path, "ffmpeg.exe")
    return os.path.isfile(exe)


def write_config_ffmpeg(path: str) -> None:
    data = {}
    if os.path.isfile(CONFIG_PATH):
        data = json.load(open(CONFIG_PATH, encoding="utf-8"))
    data["ffmpeg"] = path if path.lower().endswith(".exe") else \
        os.path.join(path, "bin", "ffmpeg.exe")
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

    from _config import cfg as _cfg
    existing = _cfg("ffmpeg")
    if existing and (os.path.isfile(existing) or shutil.which("ffmpeg")):
        print(f"[OK] ffmpeg 已就绪: {existing or 'PATH 上'}")
        return 0
    if shutil.which("ffmpeg"):
        print("[OK] ffmpeg 在 PATH 上")
        return 0

    target = args.dir or DEFAULT_DIR
    print(f"[1/3] 下载 ffmpeg essentials(约 80MB,来源 gyan.dev)…")
    os.makedirs(target, exist_ok=True)
    tmp_zip = os.path.join(target, "_ff.zip")
    urllib.request.urlretrieve(SOURCE_ZIP, tmp_zip)
    print("[2/3] 解压并提取 ffmpeg.exe…")
    found = None
    with zipfile.ZipFile(tmp_zip) as z:
        for n in z.namelist():
            if n.endswith("bin/ffmpeg.exe"):
                z.extract(n, target)
                found = os.path.join(target, n)
                break
    os.remove(tmp_zip)
    if not found:
        print("[FAIL] 包内未找到 bin/ffmpeg.exe(发行版结构可能变化)")
        return 1
    final = os.path.join(target, "ffmpeg.exe")
    shutil.move(found, final)

    write_config_ffmpeg(final)
    print(f"[3/3] 完成!ffmpeg 已部署并写入 config.json: {final}")
    print("  · GIF 走高质量调色板编码,MP4 视频导出解锁。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
