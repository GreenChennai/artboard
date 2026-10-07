"""地图模块公共层:浏览器内核 / 代理 / 瓦片缓存 / 临时页服务。

artboard `_` 前缀 = 内部模块,不进 Agent 上下文、不进脚本总表。
被 map_tiles.py、fetch_osm_data.py、svg_map.py、svg_iso.py、svg_preview.py、
render_3d.py、render_3d_vec.py、probe_tiles.py、test_v7.py 引用。

统一口径(三条,原 map-studio 各脚本各写一份):
1. **浏览器**:`VB_BROWSER_PATH` > artboard `_paths`(Chrome/Edge)> Playwright 自带
   chromium。原脚本硬编码 `C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe`,
   本机只有 Edge,`--executable_path` 指向不存在的文件 → 3D 渲染直接启动失败。
2. **网络**:下载/查询一律经 `_config.proxy_active()` 取代理(默认关 = 直连),
   禁止各脚本自读 `proxy`(artboard 纪律:`_config.proxy_active` 是唯一出口)。
3. **落盘**:瓦片缓存 / GeoJSON 底料 / 临时渲染页统一进 `<技能根>/work/`(已进 .gitignore),
   不再往仓库根写 `_render_3d.html`。
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import requests  # noqa: E402

from _config import proxy_active  # noqa: E402
from _paths import find_chrome, find_edge  # noqa: E402

ROOT = os.path.dirname(_HERE)
WORK = os.path.join(ROOT, "work")              # 地图模块运行期产物(已进 .gitignore)
TILE_CACHE = os.path.join(WORK, "tiles", "cache")   # map_tiles.py / render_3d.py 共用
GEO = os.path.join(WORK, "geo")                # fetch_osm_data.py 产出的 GeoJSON 底料
TMP = os.path.join(WORK, "tmp")                # 临时渲染页(不污染仓库根)
PROBE = os.path.join(WORK, "tiles", "probe")   # probe_tiles.py 产物


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


# ------------------------------------------------------------------ 浏览器

def browser_executable() -> str:
    """返回可用的浏览器 exe;都没有则返回空串(= 用 Playwright 自带 chromium)。"""
    env = os.environ.get("VB_BROWSER_PATH", "").strip()
    if env and os.path.isfile(env):
        return env
    return find_chrome() or find_edge() or ""


def launch_kwargs(extra_args=()) -> dict:
    """`pw.chromium.launch(**launch_kwargs([...]))` 的公共参数。"""
    kw: dict = {"headless": True}
    exe = browser_executable()
    if exe:
        kw["executable_path"] = exe
    if extra_args:
        kw["args"] = list(extra_args)
    return kw


# ------------------------------------------------------------------ 网络

def _proxies():
    p = proxy_active()
    return {"http": p, "https": p} if p else None


def http_get(url, **kw):
    """带代理口径的 GET(调用方仍可覆盖 timeout/headers)。"""
    kw.setdefault("timeout", 25)
    kw.setdefault("proxies", _proxies())
    return requests.get(url, **kw)


def http_post(url, **kw):
    kw.setdefault("timeout", 150)
    kw.setdefault("proxies", _proxies())
    return requests.post(url, **kw)


# ------------------------------------------------------------------ 本地服务

def serve_dir(directory: str = ROOT):
    """在随机端口起一个只读静态服务(渲染页 + 瓦片缓存 + vendor 都要能被页面取到)。

    瓦片**按需补抓**:相机俯仰(pitch)会把视野拉到平面窗口之外,预缓存的窗口
    永远猜不准(实测 pitch63/bearing-28 在北侧还要再多 2 排)→ MapLibre 静默
    留洞。这里在静态文件缺失时按需补抓一张再交给文件分支,离线/抓失败时维持
    原来的 404 行为。设 `ARTBOARD_TILE_ONDEMAND=0` 可关闭(纯离线复跑时)。
    """
    import threading
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    tile_re = re.compile(r"^/work/tiles/cache/([A-Za-z0-9\-]+)/(\d+)/(\d+)/(\d+)\.(png|jpg)$")
    failed: set = set()          # 抓失败过的瓦片:不重复重试(避免每次请求都等超时)

    def ensure_tile(path_qs: str) -> None:
        if os.environ.get("ARTBOARD_TILE_ONDEMAND", "1") == "0":
            return
        key = path_qs.split("?", 1)[0]
        m = tile_re.match(key)
        if not m or key in failed:
            return
        style, z, x, y = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        try:
            from map_tiles import fetch_tile      # 延迟导入:map_tiles 反向依赖本模块
            fetch_tile(style, z, x, y)
        except Exception:  # noqa: BLE001 — 离线/端点失败都退回 404,不打断渲染
            failed.add(key)

    class _Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a):      # 逐条请求日志对渲染毫无价值,只会淹没输出
            pass

        def do_GET(self):
            # 浏览器会无条件请求 /favicon.ico;默认 404 会被 render_3d / render_3d_vec
            # 的 console 监听打成 "CONSOLE ERRORS: 404",看起来像页面缺资源。空响应即可。
            if self.path.split("?", 1)[0] == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            super().do_GET()

        def send_head(self):
            try:
                if not os.path.isfile(self.translate_path(self.path)):
                    ensure_tile(self.path)
            except Exception:  # noqa: BLE001 — 补抓环节绝不影响正常静态服务
                pass
            return super().send_head()

    class _Server(ThreadingHTTPServer):
        daemon_threads = True
        # 按需补抓会让处理线程阻塞在网络上(几百 ms~秒级);默认 accept 队列只有 5,
        # 相机一次要十几张瓦片时队列溢出 → 浏览器报 ERR_CONNECTION_REFUSED(实测 5 张)。
        request_queue_size = 128

    handler = partial(_Quiet, directory=directory)
    srv = _Server(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def write_tmp_page(name: str, html: str) -> str:
    """把临时渲染页写进 tiles/tmp/,返回绝对路径。"""
    ensure_dir(TMP)
    p = os.path.join(TMP, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    return p


def repo_url(path: str) -> str:
    """把技能根下的路径转成渲染页可用的站内 URL(反斜杠归一 + URL 编码空格等)。"""
    rel = os.path.relpath(os.path.abspath(path), ROOT).replace("\\", "/")
    if rel.startswith(".."):
        raise ValueError(f"路径在技能根之外,无法通过本地服务取到: {path}")
    from urllib.parse import quote
    return "/" + quote(rel)
