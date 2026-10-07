# -*- coding: utf-8 -*-
"""审片台启动器(artboard 版)。

为什么是"包装器"而不是把服务复制一份
    真正的服务只有 `review_server.py` 一份实现。这个入口只做三件事:
      ① 按**本文件位置**找到同目录的 `review_server.py`(不依赖当前工作目录)
      ② 原样转发参数(含 `--root`),并把页面 URL 算好打出来
      ③ `--stop` 按端口收掉正在跑的实例(Windows 用 PowerShell 精确匹配命令行;
         POSIX 用 pgrep)
用法
    python <skill>/tools/review-station/review_station.py                 # 当前目录当工程根
    python <skill>/tools/review-station/review_station.py --root <项目> --port 9000
    python <skill>/tools/review-station/review_station.py --stop          # 收掉默认端口上的实例
"""
import argparse
import os
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "review_server.py")
API = "review_server.py"


def die(msg, code=1):
    sys.stderr.write("[审片台] %s\n" % msg)
    return code


def stop_running(port):
    """按端口找并结束正在跑的审片台。"""
    if os.name == "nt":
        ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
              "Where-Object { $_.CommandLine -like '*%s*' -and "
              "$_.CommandLine -like '*%d*' } | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" % (API, port))
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if r.returncode != 0:
            return die("清理失败:%s" % (r.stderr or "").strip()[:200])
        print("[审片台] 已按端口 %d 清理正在运行的实例。" % port)
        return 0
    # POSIX:pgrep 匹配命令行(来源工程的已知限制:原版只有 Windows 分支)
    r = subprocess.run(["pgrep", "-f", "%s.*--port %d" % (API, port)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    pids = [p for p in (r.stdout or "").split() if p.strip()]
    if not pids:
        print("[审片台] 端口 %d 上没有找到实例(可能本来就没起)。" % port)
        return 0
    for pid in pids:
        subprocess.run(["kill", pid], capture_output=True)
    print("[审片台] 已结束 %d 个实例:%s" % (len(pids), " ".join(pids)))
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="起审片台(画面/时间轴/字幕/意见/性能一体的网页审片工具)",
        formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--root", default="", help="工程根(默认当前目录)")
    ap.add_argument("--work-dir", default="", help="运行期目录(默认 <root>/review)")
    ap.add_argument("--port", type=int, default=8860, help="端口(默认 8860)")
    ap.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    ap.add_argument("--stop", action="store_true", help="停掉正在运行的审片台")
    ap.add_argument("--audio", default="", help="显式指定音频")
    ap.add_argument("--mp4", default="", help="显式指定成片")
    ap.add_argument("--fps", type=int, default=30, help="帧率(默认 30)")
    ap.add_argument("--title", default="", help="片名(默认目录名)")
    a = ap.parse_args()

    if a.stop:
        return stop_running(a.port)
    if not os.path.isfile(SERVER):
        return die("找不到服务实现:%s" % SERVER)

    root = os.path.abspath(a.root or os.getcwd())
    url = "http://127.0.0.1:%d/__rv/review.html" % a.port
    print("[审片台] 启动入口:%s" % os.path.abspath(__file__))
    print("[审片台] 服务实现:%s" % SERVER)
    print("[审片台] 工程根:  %s" % root)
    print("[审片台] 页面:    %s" % url)
    print("[审片台] 停止服务:此窗口按 Ctrl+C,或另开窗口跑 --stop")
    cmd = [sys.executable, SERVER, "--root", root, "--port", str(a.port),
           "--fps", str(a.fps)]
    if a.work_dir:
        cmd += ["--work-dir", a.work_dir]
    if a.audio:
        cmd += ["--audio", a.audio]
    if a.mp4:
        cmd += ["--mp4", a.mp4]
    if a.title:
        cmd += ["--title", a.title]
    if a.no_open:
        cmd += ["--no-open"]
    return subprocess.call(cmd, cwd=root)


if __name__ == "__main__":
    sys.exit(main())
