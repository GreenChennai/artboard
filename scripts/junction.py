"""NTFS 目录联接(junction)创建/检测。

创建走 PowerShell `New-Item -ItemType Junction`(Windows 10/11 自带,原生 Unicode);
路径经环境变量传递,彻底避开引号/编码问题。探测用 realpath 偏移判断。
"""

import os
import subprocess


def is_junction(path: str) -> bool:
    """path 是否为联接(reparse point 且指向别处)。"""
    try:
        return (os.path.isdir(path) and
                os.path.realpath(path).replace(os.sep, "/").lower() !=
                os.path.abspath(path).replace(os.sep, "/").lower())
    except OSError:
        return False


def probe(path: str) -> bool:
    """联接穿透验证:目录可列出且非空。"""
    try:
        return bool(os.listdir(path))
    except OSError:
        return False


def create_junction(link: str, target: str) -> None:
    """在 link 处创建指向 target 的目录联接。失败抛 RuntimeError/OSError。"""
    if is_junction(link):
        return
    if not os.path.isdir(target):
        raise OSError(2, f"联接目标不存在: {target}")
    os.makedirs(link)  # 创建空目录作为联接载体

    env = {**os.environ,
           "AB_LINK": link, "AB_TARGET": target}
    script = ("New-Item -ItemType Junction -Path $env:AB_LINK "
              "-Value $env:AB_TARGET | Out-Null")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, env=env, timeout=120)
    if r.returncode != 0 or not probe(link):
        err = (r.stderr or b"").decode("gbk", errors="replace")[:160]
        raise RuntimeError(f"PowerShell 建联接失败: {err or '穿透验证失败'}")
    if not probe(link):
        raise RuntimeError("联接穿透验证失败")
