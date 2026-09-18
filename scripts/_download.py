"""artboard 共享下载器:带超时、带重试、带进度、临时文件必清理。

背景:原先各 setup 脚本各写一份 `urllib.request.urlretrieve(...)`,无 timeout
(跨境网络下进程可无限期挂起,表现为"卡死无输出"),失败后残留 _xx.zip 不清理。
本模块统一实现 `urlopen` + 分块写盘(urlretrieve 不支持 timeout),用法:

    from _download import download
    download(url, dest)                       # 默认 300s 超时,重试 2 次
    download(url, dest, timeout=60, retries=0, label="FFmpeg")

- 先写 `<dest>.part`,成功才 os.replace → 绝不留下半个文件
- 失败自动删除 .part,按 retries 重试(退避 2s / 4s)
- 尊重 config.json 的 proxy / 环境变量 ARTBOARD_PROXY
"""

import os
import sys
import time
import urllib.request

DEFAULT_TIMEOUT = 300      # 秒
DEFAULT_RETRIES = 2
CHUNK = 1 << 18            # 256KB


def _proxy() -> str:
    try:
        from _config import cfg
        return cfg("proxy")
    except Exception:
        return ""


def _proxy_alive(proxy: str, timeout: float = 3.0) -> bool:
    """TCP 探活代理地址(host:port);解析失败即视为不可达。"""
    try:
        from urllib.parse import urlparse
        u = urlparse(proxy)
        host = u.hostname or ""
        port = u.port or (443 if u.scheme == "https" else 80)
        import socket
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _opener(proxy: str) -> urllib.request.OpenerDirector:
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener()


def _printer(label: str):
    last = [0.0]

    def hook(done: int, total: int) -> None:
        now = time.time()
        if total > 0 and (now - last[0] > 0.2 or done >= total):
            last[0] = now
            print(f"\r  {label} {done // 1024 // 1024}/{total // 1024 // 1024} MB"
                  f" ({min(100, done * 100 // total)}%)   ", end="", flush=True)
    return hook


def download(url: str, dest: str, timeout: float = DEFAULT_TIMEOUT,
             retries: int = DEFAULT_RETRIES, label: str = "",
             proxy: str = "") -> str:
    """下载 url → dest。成功返回 dest;彻底失败抛 RuntimeError(带原因与补救指引)。"""
    label = label or os.path.basename(dest) or "下载"
    proxy = proxy or _proxy()
    parent = os.path.dirname(os.path.abspath(dest))
    if parent:
        os.makedirs(parent, exist_ok=True)
    part = os.path.abspath(dest) + ".part"

    # 传输模式序列:配置了代理 → [代理, 直连];代理探活失败直接跳过
    # (死代理会让"连接拒绝"重试全烧在代理上,直连本可成功——部署实测 Issue 4)
    modes: list[tuple[str, str]] = []
    if proxy:
        if _proxy_alive(proxy):
            modes.append(("代理", proxy))
        else:
            print(f"  △ {label} 配置的代理 {proxy} 不可达(无进程监听),改直连")
    modes.append(("直连", ""))

    last_err: Exception | None = None
    tried: list[str] = []
    for mode_name, mode_proxy in modes:
        for attempt in range(retries + 1):
            try:
                opener = _opener(mode_proxy)
                opener.addheaders = [("User-Agent", "artboard-skill")]
                with opener.open(url, timeout=timeout) as resp:
                    total = int(resp.headers.get("Content-Length") or 0)
                    hook = _printer(label)
                    done = 0
                    with open(part, "wb") as f:
                        while True:
                            chunk = resp.read(CHUNK)
                            if not chunk:
                                break
                            f.write(chunk)
                            done += len(chunk)
                            hook(done, total)
                if not os.path.isfile(part) or os.path.getsize(part) == 0:
                    raise RuntimeError("下载结果为空(0 字节)")
                os.replace(part, dest)
                print(f"\r  {label} 完成-{mode_name}({os.path.getsize(dest) // 1024 // 1024} MB)      ")
                return dest
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                tried.append(f"{mode_name}:{exc}")
                try:
                    if os.path.isfile(part):
                        os.remove(part)
                except OSError:
                    pass
                if attempt < retries:
                    wait = 2 * (attempt + 1)
                    print(f"\n  △ {label} {mode_name}第 {attempt + 1} 次失败({exc}),{wait}s 后重试…")
                    time.sleep(wait)

    proxy_cfg = f"config.json proxy = {proxy}" if proxy else "config.json 未配置 proxy"
    raise RuntimeError(
        f"{label} 下载失败: {last_err}\n"
        f"  源地址: {url}\n"
        f"  尝试轨迹: {'; '.join(tried) if tried else '(未发起)'}\n"
        f"  当前: {proxy_cfg}\n"
        f"  · 代理连接拒绝 = 代理进程未运行(常见:代理客户端没启动);\n"
        f"  · 未配置代理且直连被拒 = 网络不可达 GitHub,可在 config.json 填 proxy;\n"
        f"  · 或手动下载后放到: {dest}\n"
        f"    并执行: python scripts/setup_kiln.py --exe <该文件路径>")
