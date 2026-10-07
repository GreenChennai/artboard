# -*- coding: utf-8 -*-
"""审片台服务端(artboard 版)。

它解决什么
    artboard 的动效/视频卡(模式 S/V)与 MV 这类长动效,"改完看不出问题"——
    出一次片要几十秒到几分钟,而绝大多数毛病(卡点错位、元素闪、字没进场、
    字幕遮主体)看一眼逐帧就能发现。审片的本质是**起一个本地服务 + 一个网页 UI**:
      ① 静态服务工程根(影片脚本 / 音频 / 成片在同一棵树下)
      ② 浏览器拖动 MP4 做对照需要 Range 请求 → 自己实现(成片动辄 GB 级)
      ③ `?action=shot`   从**成片**按时间精确取一帧(PNG),做 预览 vs 成片 对照
      ④ `?action=render` 把当前这一段**裁成 mp4**(审片发现问题 → 一键出片段)
      ⑤ `?action=job`    查任务进度(裁切在后台进程,页面轮询它)
      ⑥ `?action=refs`   列出可作对照的成片
    意见/字幕/配置全部落盘成 JSON —— **那是给 Agent 用的接口**(见
    `references/review-loop.md`):下一轮改稿直接读文件,不用人肉转述。

用法(在**项目根**下跑;`--root` 默认取当前目录)
    python <skill>/tools/review-station/review_server.py --root <项目> --no-open
    python <skill>/tools/review-station/review_server.py --root . --port 8870
    python <skill>/tools/review-station/review_station.py --root .        # 启动器(算好 URL,可选 --stop)

目录约定(全部可用参数覆盖)
    <root>/src/…            影片本体(scaffold 产出的项目;也可指向任意含 index.html 的目录)
    <root>/export/*.mp4     成片(refs / shot / render 的数据源)
    <root>/review/          审片台运行期:意见.json / 字幕轨.json / 配置.json / 字幕导出/ / 片段/
    --work-dir 改运行期目录;--audio 指定音频;--mp4 指定成片;--fps 指定帧率

与来源工程(原 `map-studio` 之外的 MV 审片台)的差异 —— 迁移时按 artboard 口径重写过:
    1. `ROOT` 从"`__file__` 上两级"改成**显式 `--root`**(默认 cwd):artboard 项目由
       `scaffold.py` 生成,深度与"上两级"假设不一致(原包 README 必改第 1 条);
    2. 5 个落盘路径全部参数化到 `--work-dir`(必改第 3 条),不再写死 `06_成片输出/`;
    3. **双挂载**:`/__rv/*` 指工具目录、其余指工程根 —— 工具与工程不在同一棵树,
       原版"服务整个工程根"的假设不成立(这是移植里唯一不好照抄的结构性改动);
    4. `shot` / `render` 由"转调工程自带的 `tools/render.py`"改为**基于成片的 ffmpeg 出帧/切片**:
       artboard 的渲染器不支持按时间区间出片,而且"对照成片"本来只需对成片取帧;
    5. `--stop` 补 POSIX 分支(必改第 5 条);
    6. 音频不再硬编码 `Mili.mp3`:`meta` 返回探测结果,前端据此设置 `<audio>`
       (必改第 2 条);字幕候选不再写死探测顺序,统一走 `subfiles`(必改第 4 条)。

依赖:服务端**只用标准库**;只有 `shot` / `render` 需要 ffmpeg(与 artboard 其余脚本同一口径:
`config.json` 的 `ffmpeg` / `ARTBOARD_FFMPEG` / PATH,经 `scripts/_img_core.ffmpeg_path()` 取)。
"""
import argparse
import io
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import webbrowser

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 路径(由 main() 按参数写入;__rv 挂载点用绝对路径常量占位) ──
TOOL = os.path.dirname(os.path.abspath(__file__))          # tools/review-station
SKILL = os.path.dirname(os.path.dirname(TOOL))             # 技能根
MOUNT = "/__rv"                                            # 工具静态挂载点
PAGE = "review.html"
API = os.path.basename(os.path.abspath(__file__))          # review_server.py

ROOT = os.getcwd()          # 工程根
WORK = os.path.join(ROOT, "review")    # 审片台运行期目录
NOTES = os.path.join(WORK, "审片意见.json")
SUBS = os.path.join(WORK, "字幕轨.json")
CFG = os.path.join(WORK, "审片台配置.json")
SRT_OUT = os.path.join(WORK, "字幕导出")
SHOTS = os.path.join(WORK, "_shot")
SEGS = os.path.join(WORK, "片段")
AUDIO = ""       # 显式 --audio;空 = 自动探测
MP4 = ""         # 显式 --mp4;空 = 自动探测
FPS = 30
TITLE = ""
SUB_EXT = (".srt", ".vtt", ".ass", ".ssa")
MEDIA_EXT = (".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac", ".opus")
PY = sys.executable
JOBS = {}
LOCK = threading.Lock()


def set_paths(root, work, audio, mp4, fps, title):
    """把命令行参数落到模块级(函数式写法的代价:用一个显式入口收敛)。"""
    global ROOT, WORK, NOTES, SUBS, CFG, SRT_OUT, SHOTS, SEGS, AUDIO, MP4, FPS, TITLE
    ROOT = os.path.abspath(root)
    WORK = os.path.abspath(work or os.path.join(ROOT, "review"))
    NOTES = os.path.join(WORK, "审片意见.json")
    SUBS = os.path.join(WORK, "字幕轨.json")
    CFG = os.path.join(WORK, "审片台配置.json")
    SRT_OUT = os.path.join(WORK, "字幕导出")
    SHOTS = os.path.join(WORK, "_shot")
    SEGS = os.path.join(WORK, "片段")
    AUDIO, MP4 = audio or "", mp4 or ""
    FPS, TITLE = int(fps or 30), title or ""


def rel(p):
    try:
        return os.path.relpath(p, ROOT).replace("\\", "/")
    except ValueError:
        return p


# ── ffmpeg / ffprobe(与 artboard 其余脚本同一套配置口径) ──
def ffmpeg_exe():
    scripts = os.path.join(SKILL, "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        from _img_core import ffmpeg_path      # noqa: PLC0415 — 延迟导入:自检冒烟时不依赖它
        p = ffmpeg_path()
        if p:
            return p
    except Exception:
        pass
    return shutil.which("ffmpeg") or ""


def ffprobe_exe():
    exe = ffmpeg_exe()
    if exe:
        cand = os.path.join(os.path.dirname(exe), "ffprobe.exe" if os.name == "nt" else "ffprobe")
        if os.path.isfile(cand):
            return cand
    return shutil.which("ffprobe") or ""


def probe_duration(path):
    """成片时长(秒);取不到返回 0(页面会自己按影片时长兜底)。"""
    pb = ffprobe_exe()
    if not (pb and path and os.path.isfile(path)):
        return 0.0
    try:
        r = subprocess.run([pb, "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
        return float((r.stdout or "0").strip() or 0)
    except Exception:
        return 0.0


def _scan(names, dirs, depth=3):
    """在 dirs 下按扩展名找文件(限深,不进 node_modules/.git);按 mtime 新→旧。"""
    hits = []
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        base_depth = d.rstrip("\\/").count(os.sep)
        for cur, subdirs, files in os.walk(d):
            subdirs[:] = [s for s in subdirs
                          if not s.startswith((".", "_")) and s != "node_modules"]
            if cur.count(os.sep) - base_depth >= depth:
                subdirs[:] = []
            for fn in files:
                if fn.lower().endswith(tuple(names)):
                    hits.append(os.path.join(cur, fn))
    hits.sort(key=lambda p: -os.path.getmtime(p))
    return hits


def find_audio():
    if AUDIO:
        return AUDIO if os.path.isfile(AUDIO) else ""
    hits = _scan(MEDIA_EXT, [os.path.join(ROOT, "src"), os.path.join(ROOT, "assets"),
                             os.path.join(ROOT, "audio"), ROOT], depth=3)
    return hits[0] if hits else ""


def find_mp4s():
    """可作对照的成片:export/ 与运行期目录下的 mp4(按体积降序)。"""
    hits = _scan([".mp4"], [os.path.join(ROOT, "export"), WORK, os.path.join(ROOT, "dist")],
                 depth=2)
    hits.sort(key=lambda p: -os.path.getsize(p))
    if MP4 and os.path.isfile(MP4):
        hits = [MP4] + [p for p in hits if os.path.abspath(p) != os.path.abspath(MP4)]
    return hits


def primary_mp4():
    if MP4 and os.path.isfile(MP4):
        return MP4
    hits = find_mp4s()
    return hits[0] if hits else ""


def _url(p):
    """本地文件 → 页面可用 URL(工程根内用根相对;工具目录用 /__rv)。"""
    ap = os.path.abspath(p)
    if ap.startswith(os.path.abspath(TOOL) + os.sep):
        return MOUNT + "/" + urllib.parse.quote(os.path.relpath(ap, TOOL).replace("\\", "/"))
    if ap.startswith(os.path.abspath(ROOT) + os.sep):
        return "/" + urllib.parse.quote(os.path.relpath(ap, ROOT).replace("\\", "/"))
    return ""


# ── 落盘(原子替换;临时名唯一) ──
_WRITE_LOCK = threading.Lock()


def atomic_write(path, text):
    """原子写:同目录**唯一**临时名 → os.replace。

    ⚠️ 临时名必须唯一(来源工程的实测教训):服务是多线程的,前端一次编辑可能连发两次
    保存,固定临时名会让两个线程互相 `os.replace` 撞 EINVAL/找不到文件,用户看到"保存失败"。
    """
    with _WRITE_LOCK:
        d = os.path.dirname(path) or "."
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".tmp", dir=d)
        try:
            with io.open(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            os.replace(tmp, path)
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
    return rel(path)


def read_json(path, default=None):
    """读 JSON;坏文件当空(不让页面白屏)。"""
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def notes_load():
    if not os.path.isfile(NOTES):
        return [], rel(NOTES)
    d = read_json(NOTES)
    if d is None:
        return [], "意见文件读不出来(坏 JSON?):%s" % rel(NOTES)
    return (d or {}).get("notes", []), rel(NOTES)


def notes_save(notes):
    data = {"film": TITLE or os.path.basename(ROOT),
            "note": "审片台导出的修改意见。t0/t1 单位秒;t1==t0 表示时间点;"
                    "el 是元素拾取器抓到的画布坐标与外观。给 Agent 读的就是这份文件。",
            "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "notes": notes}
    return atomic_write(NOTES, json.dumps(data, ensure_ascii=False, indent=2))


def subs_load():
    """字幕轨存档;没有则 None(前端回落到影片自带的歌词层)。"""
    if not os.path.isfile(SUBS):
        return None, rel(SUBS)
    d = read_json(SUBS)
    if d is None:
        return None, "字幕轨读不出来(坏 JSON?)"
    return d, rel(SUBS)


# ─────────────── 带 Range 的静态服务(双挂载) ───────────────
class Handler(__import__("http.server", fromlist=["SimpleHTTPRequestHandler"]).SimpleHTTPRequestHandler):
    def translate_path(self, path):
        """URL 路径 → 本地文件。

        ⚠️ 三个坑(前两个来自来源工程):
          ① `urlparse` 会把最后一段 `;` 之后当 **params** 切掉(`a.mp3;b` → `a.mp3`),
             必须用 **urlsplit**;
          ② 不能对 URL 路径调 `os.path.normpath` —— Windows 的 ntpath 会把分号当分隔符;
          ③ 新增:`/__rv/*` 指工具目录,其余指工程根(工具与工程不同树)。
        """
        p = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
        base = TOOL if p == MOUNT or p.startswith(MOUNT + "/") else ROOT
        if base is TOOL:
            p = p[len(MOUNT):]
        parts = []
        for seg in p.replace("\\", "/").split("/"):
            if not seg or seg in (".", ".."):
                continue
            parts.append(seg)
        return os.path.join(base, *parts)

    def end_headers(self):
        """所有响应 no-store:审片台是开发工具,改完文件刷新就必须生效。"""
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *a):          # 静音访问日志
        pass

    # ---- Range:Chrome 的 <video> 拖动必须要 ----
    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if os.path.basename(u.path) == API:
            try:
                return self.api(u, "GET")
            except Exception as e:                      # noqa: BLE001
                print("[review] 未捕获异常:\n" + traceback.format_exc())
                try:
                    return self.j({"ok": False, "error": "%s" % e})
                except Exception:
                    return self.send_error(500)
        rng = self.headers.get("Range")
        if not rng:
            return super().do_GET()
        fs = self.translate_path(u.path)
        if not os.path.isfile(fs):
            return super().do_GET()
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        if not m:
            return super().do_GET()
        size = os.path.getsize(fs)
        a = int(m.group(1)) if m.group(1) else 0
        b = int(m.group(2)) if m.group(2) else size - 1
        a, b = max(0, a), min(size - 1, b)
        if a > b:
            self.send_error(416)
            return
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(fs))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, size))
        self.send_header("Content-Length", str(b - a + 1))
        self.end_headers()
        with open(fs, "rb") as f:
            f.seek(a)
            left = b - a + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except Exception:               # noqa: BLE001
                    return
                left -= len(chunk)

    # ---- POST 也走 API ----
    def do_POST(self):
        u = urllib.parse.urlsplit(self.path)
        if os.path.basename(u.path) != API:
            return self.send_error(405)
        try:
            return self.api(u, "POST")
        except Exception as e:                          # noqa: BLE001
            # 顶层兜底:抛出去连接会被直接关掉,浏览器只看到 "Failed to fetch",看不到原因
            tb = traceback.format_exc()
            print("[review] 未捕获异常:\n" + tb)
            try:
                return self.j({"ok": False, "error": "%s" % e, "tb": tb[-800:]})
            except Exception:
                return self.send_error(500)

    def read_json(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except Exception:                               # noqa: BLE001
            n = 0
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception as e:                          # noqa: BLE001
            print("[review] 请求体不是合法 JSON:%s" % e)
            return {}

    # ---- API ----
    def api(self, u, method):
        q = urllib.parse.parse_qs(u.query)
        act = (q.get("action") or [""])[0]
        try:
            if act == "ping":
                return self.j({"ok": True, "pong": True, "root": ROOT, "work": WORK})
            if act == "meta":
                return self.j(self.meta())
            if act == "refs":
                return self.j({"ok": True, "refs": [_url(p) for p in find_mp4s()]})
            if act == "subfiles":
                return self.j({"ok": True, "files": list_subfiles()})
            if act == "shot":
                return self.shot(float((q.get("t") or ["0"])[0]))
            if act == "subs" and method == "GET":
                data, where = subs_load()
                return self.j({"ok": True, "data": data, "file": where})
            if act == "subs" and method == "POST":
                body = self.read_json()
                try:
                    where = atomic_write(SUBS, json.dumps(body, ensure_ascii=False, indent=2))
                except Exception as e:                  # noqa: BLE001
                    return self.j({"ok": False, "error": "%s" % e})
                print("[review] 字幕轨已保存 -> %s(%d 段)"
                      % (where, len(body.get("lines") or [])))
                return self.j({"ok": True, "file": where, "n": len(body.get("lines") or [])})
            if act == "config" and method == "GET":
                return self.j({"ok": True, "data": read_json(CFG, {}) or {}, "file": rel(CFG)})
            if act == "config" and method == "POST":
                body = self.read_json()
                try:
                    where = atomic_write(CFG, json.dumps(body, ensure_ascii=False, indent=2))
                except Exception as e:                  # noqa: BLE001
                    return self.j({"ok": False, "error": "%s" % e})
                print("[review] 审片台配置已保存 -> %s" % where)
                return self.j({"ok": True, "file": where})
            if act == "srt" and method == "POST":
                return self.save_srt()
            if act == "notes" and method == "GET":
                ns, where = notes_load()
                return self.j({"ok": True, "notes": ns, "file": where})
            if act == "notes" and method == "POST":
                body = self.read_json()
                try:
                    where = notes_save(body.get("notes") or [])
                except Exception as e:                  # noqa: BLE001
                    tb = traceback.format_exc()
                    print("[review] 意见保存失败:\n" + tb)
                    return self.j({"ok": False, "error": "%s" % e, "tb": tb[-900:]})
                print("[review] 意见已落盘 -> %s" % where)
                return self.j({"ok": True, "file": where, "n": len(body.get("notes") or [])})
            if act == "job":
                return self.j(job((q.get("id") or [""])[0]))
            if act == "render" and method == "POST":
                body = self.read_json()
                return self.j(start(body))
            return self.j({"ok": False, "error": "unknown action: %s" % act})
        except Exception as e:                          # noqa: BLE001
            return self.j({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    # ---- 各 action 的实现 ----
    def meta(self):
        """影片元信息。音频/成片**探测结果**也在这里给前端(不再硬编码文件名)。"""
        audio = find_audio()
        mp4 = primary_mp4()
        return {"ok": True, "root": ROOT, "work": WORK,
                "title": TITLE or os.path.basename(ROOT) or "未命名",
                "fps": FPS,
                "dur": probe_duration(mp4),
                "audio": _url(audio) if audio else "",
                "audio_name": os.path.basename(audio) if audio else "",
                "mp4": _url(mp4) if mp4 else "",
                "mp4_name": os.path.basename(mp4) if mp4 else "",
                "refs": [_url(p) for p in find_mp4s()],
                "page": MOUNT + "/" + PAGE,
                "ffmpeg": bool(ffmpeg_exe()),
                "hint": ("" if audio else "未探测到音频(--audio 可显式指定);"
                         "无水印/无音频不影响逐帧审片")
                        + ("" if mp4 else ";未探测到成片(export/*.mp4),'成片对照'页签将为空")}

    def save_srt(self):
        body = self.read_json()
        text = body.get("srt") or ""
        try:
            dur = float(body.get("dur") or 0)
        except Exception:                               # noqa: BLE001
            dur = 0
        clipped = dropped = 0
        if dur > 0:
            # 字幕允许排到片长之外,但导出**以实际片长为准**:结束时间截到 dur,
            # 整条落在片长之外的丢弃(来源工程铁律⑰)。
            text, clipped, dropped = clip_srt(text, dur)
        name = os.path.basename((body.get("name") or "").strip() or "字幕.srt")
        name = name.replace("/", "_").replace("\\", "_")
        if not name.lower().endswith(SUB_EXT):
            name += ".srt"
        try:
            where = atomic_write(os.path.join(SRT_OUT, name), text)
        except Exception as e:                          # noqa: BLE001
            return self.j({"ok": False, "error": "%s" % e})
        print("[review] 字幕已写出 -> %s%s" % (
            where, ("(按片长 %.3fs 裁剪:截断 %d / 丢弃 %d)" % (dur, clipped, dropped)) if dur else ""))
        return self.j({"ok": True, "file": where, "clipped": clipped,
                       "dropped": dropped, "dur": dur})

    def j(self, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def shot(self, t):
        """从成片按时间取一帧(PNG)。ffmpeg 的 `-ss` 放在 `-i` 前:走关键帧快速定位。"""
        mp4 = primary_mp4()
        if not mp4:
            return self.j({"ok": False, "error": "NO_MP4",
                           "hint": "没找到成片(export/*.mp4);先用 export.py 出片,"
                                   "或直接用页面里的实时预览逐帧看"})
        exe = ffmpeg_exe()
        if not exe:
            return self.j({"ok": False, "error": "NO_FFMPEG",
                           "hint": "配置 config.json 的 ffmpeg 或设 ARTBOARD_FFMPEG"})
        os.makedirs(SHOTS, exist_ok=True)
        stamp = "%d_%07.3f" % (int(os.path.getmtime(mp4)), t)
        png = os.path.join(SHOTS, "f%s.png" % stamp)
        if not os.path.exists(png):
            cmd = [exe, "-y", "-v", "error", "-ss", "%.3f" % max(0.0, t), "-i", mp4,
                   "-frames:v", "1", "-f", "image2", png]
            r = subprocess.run(cmd, capture_output=True, timeout=180,
                               encoding="utf-8", errors="replace")
            if not os.path.exists(png):
                return self.j({"ok": False, "error": "SHOT_FAILED",
                               "detail": (r.stderr or "")[-300:]})
        data = open(png, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Shot-File", rel(png))
        self.end_headers()
        self.wfile.write(data)


SUB_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*"
                      r"(\d+):(\d+):(\d+)[,.](\d+)")


def _tc(x):
    """秒 → SRT 时间码(毫秒四舍五入,别留 3.9995 这种尾巴)。"""
    ms = int(round(x * 1000))
    h, ms = divmod(ms, 3600000)
    mnt, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, mnt, sec, ms)


def clip_srt(text, dur):
    """按片长裁剪 SRT:结束时间截到 dur,整条在片长之外的丢弃。
    返回 (新文本, 被截断条数, 被丢弃条数)。WEBVTT/NOTE 头部原样保留。"""
    blocks = re.split(r"\n\s*\n",
                      text.replace("\r\n", "\n").replace("\r", "\n").strip())
    cues, raws = [], []
    clipped = dropped = 0
    for b in blocks:
        lines = [x for x in b.split("\n") if x.strip() != ""]
        if not lines:
            continue
        hi = 0 if "-->" in lines[0] else (1 if len(lines) > 1 else 0)
        head = lines[hi] if hi < len(lines) else ""
        m = SUB_TIME.search(head)
        if not m:
            # 看着像字幕块(有序号行或 -->)却解析不出时间 → 坏条目,丢掉;
            # 否则它会被原样保留又被重新编号,产出编号重复的坏 SRT
            if re.match(r"^\s*\d+\s*$", lines[0]) or "-->" in b:
                dropped += 1
                continue
            raws.append("\n".join(lines))
            continue
        g = [int(x) for x in m.groups()]
        t0 = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        t1 = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        if t0 >= dur - 1e-6:
            dropped += 1
            continue
        if t1 > dur:
            t1 = dur
            clipped += 1
        cues.append("\n".join([_tc(t0) + " --> " + _tc(t1)] + lines[hi + 1:]))
    out = list(raws)
    for k, b in enumerate(cues, 1):
        if out:
            out.append("")
        out.append(str(k))
        out.append(b)
    return "\n".join(out) + "\n", clipped, dropped


def list_subfiles():
    """可编辑的字幕候选:工程里所有字幕文件(不写死探测顺序——原版 README 必改第 4 条)。"""
    hits = _scan(SUB_EXT, [WORK, os.path.join(ROOT, "export"),
                           os.path.join(ROOT, "src"), ROOT], depth=3)
    return [{"name": os.path.basename(p), "path": rel(p), "size": os.path.getsize(p),
             "mtime": int(os.path.getmtime(p)), "url": _url(p)} for p in hits]


# ─────────────── 裁片段(后台任务) ───────────────
def start(cfg):
    """把 [t0,t1] 从成片裁成 mp4。

    与来源工程的差别:原版是"重新渲染该段"(转调工程自带的 render.py);artboard 版
    是**从成片裁一段** —— 够用(要的是"把问题片段交出去")且不依赖渲染器。
    需要"真重渲",直接跑 export.py 全片重导。
    """
    mp4 = primary_mp4()
    if not mp4:
        return {"ok": False, "error": "NO_MP4", "hint": "先有成片(export/*.mp4)才能裁片段"}
    exe = ffmpeg_exe()
    if not exe:
        return {"ok": False, "error": "NO_FFMPEG", "hint": "配置 config.json 的 ffmpeg"}
    t0 = float(cfg.get("t0", 0))
    t1 = float(cfg.get("t1", t0 + 5))
    if t1 <= t0:
        return {"ok": False, "error": "BAD_RANGE", "hint": "t1 必须大于 t0"}
    preset = cfg.get("preset", "veryfast")
    try:
        crf = int(cfg.get("crf", 18))
    except Exception:                                   # noqa: BLE001
        crf = 18
    os.makedirs(SEGS, exist_ok=True)
    out = os.path.join(SEGS, "seg_%07.2f-%07.2f.mp4" % (t0, t1))
    jid = "r%d" % int(time.time() * 1000 % 1e9)
    # 编码口径(来源:hyperframes 的 chunkEncoder,Apache-2.0;此处只取与"能播"相关的两条):
    #   · `-bf 0` —— 关掉 B 帧。B 帧会让流开头的 DTS 变负,部分浏览器/硬件解码器会卡首帧
    #     (音频先响、画面不动)。片段是要发出去给人看的,值这点体积代价;
    #   · `-vf pad=ceil(iw/2)*2:…` —— yuv420p 硬要求偶数尺寸,奇数画布会直接报错。
    # 锁 GOP(-g/-keyint_min/-sc_threshold 0)只在需要 `-c copy` 拼片时才必要,这里不需要。
    cmd = [exe, "-y", "-v", "error", "-progress", "pipe:1", "-nostats",
           "-ss", "%.3f" % max(0.0, t0), "-to", "%.3f" % t1, "-i", mp4,
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-bf", "0",
           "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
           "-movflags", "+faststart", out]
    with LOCK:
        JOBS[jid] = {"id": jid, "state": "running", "t0": t0, "t1": t1,
                     "out": rel(out), "pct": 0.0, "tail": "", "mp4": rel(mp4)}
    p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    threading.Thread(target=watch, args=(jid, p, t1 - t0), daemon=True).start()
    print("[review] 裁片段 %s 的 %.2f–%.2fs -> %s" % (rel(mp4), t0, t1, rel(out)))
    return {"ok": True, "id": jid, "out": rel(out)}


def watch(jid, proc, span):
    """跟着 ffmpeg 的 `-progress pipe:1` 走:解析 out_time_us 算百分比。"""
    try:
        for line in proc.stdout or []:
            line = line.strip()
            m = re.match(r"out_time_us=(\d+)", line)
            with LOCK:
                JOBS[jid]["tail"] = line[:160]
                if m and span > 0:
                    JOBS[jid]["pct"] = min(100.0, float(m.group(1)) / 1e6 / span * 100.0)
        rc = proc.wait()
    except Exception as e:                              # noqa: BLE001
        rc = -1
        with LOCK:
            JOBS[jid]["tail"] = "watch 异常:%s" % e
    with LOCK:
        JOBS[jid]["state"] = "done" if rc == 0 else "error"
        JOBS[jid]["pct"] = 100.0 if rc == 0 else JOBS[jid].get("pct", 0.0)


def job(jid):
    with LOCK:
        j = JOBS.get(jid)
    if not j:
        return {"ok": False, "error": "no such job"}
    return {"ok": True, "state": j["state"], "pct": round(j.get("pct", 0), 1),
            "out": j["out"], "tail": j.get("tail", "")}


# ─────────────── 入口 ───────────────
def page_url(port):
    return "http://127.0.0.1:%d%s/%s" % (port, MOUNT, PAGE)


def main():
    ap = argparse.ArgumentParser(
        description="审片台服务端(artboard 版):把动效/成片变成可逐帧审、可批注、可回读的网页",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="例:python review_server.py --root <项目> --no-open\n"
               "页面地址会自动打印;审片意见/字幕轨/配置都落在 <项目>/review/")
    ap.add_argument("--root", default="", help="工程根(默认当前目录;里面应有 src/ 与 export/)")
    ap.add_argument("--work-dir", default="", help="运行期目录(默认 <root>/review)")
    ap.add_argument("--port", type=int, default=8860)
    ap.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    ap.add_argument("--audio", default="", help="显式指定音频文件(默认自动探测)")
    ap.add_argument("--mp4", default="", help="显式指定成片(默认取 export/ 下最大的)")
    ap.add_argument("--fps", type=int, default=30, help="帧率(默认 30;MV 类常用 60)")
    ap.add_argument("--title", default="", help="片名(默认取目录名)")
    a = ap.parse_args()

    set_paths(a.root or os.getcwd(), a.work_dir, a.audio, a.mp4, a.fps, a.title)
    if not os.path.isdir(ROOT):
        print(json.dumps({"ok": False, "error": "NO_ROOT", "root": ROOT,
                          "hint": "--root 指向的目录不存在"}, ensure_ascii=False))
        return 2
    os.makedirs(WORK, exist_ok=True)

    class S(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True
        # 页面一次会并发拉十几张帧图,默认 accept 队列(5)会溢出成 ERR_CONNECTION_REFUSED
        request_queue_size = 128

    try:
        srv = S(("127.0.0.1", a.port), Handler)
    except OSError as e:
        print(json.dumps({"ok": False, "error": "PORT_BUSY", "detail": str(e),
                          "hint": "换 --port,或用 review_station.py --stop 收掉旧实例"},
                         ensure_ascii=False))
        return 2

    url = page_url(a.port)
    print("[review] 页面:%s" % url)
    print("[review] 工程根:%s" % ROOT)
    print("[review] 运行期:%s" % WORK)
    print("[review] 成片 %d 个 / 音频 %s / ffmpeg %s"
          % (len(find_mp4s()), os.path.basename(find_audio()) or "未探测到",
             "可用" if ffmpeg_exe() else "缺失(shot/render 不可用)"))
    if not a.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[review] 已停止")
    except Exception:                                   # noqa: BLE001
        print("[review] **服务异常退出**(上面的堆栈是原因):")
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
