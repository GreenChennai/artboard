r"""artboard 配置编辑器(纯 tkinter,零第三方依赖,可 PyInstaller 打包成单文件 exe)。

功能:可视化编辑 config.json 的全部键;界面顶部显示实际写入路径;
保存时自动校验 JSON 合法性,小白不再需要手工处理逗号/引号。

打包 exe(在技能根目录执行):
  python -m PyInstaller --onefile --windowed --name artboard-config-editor ^
      --distpath tools/config-editor --workpath .build --specpath .build ^
      scripts/config_gui.py

⚠️ frozen(PyInstaller)状态下 `__file__` 指向解包临时目录(_MEIPASS),
   不能用来定位技能根 —— 必须以 `sys.executable` 为起点向上搜索技能根标志
   文件 `config.example.json`。见 locate_skill_dir()。
"""

import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

SKILL_MARKERS = ("config.example.json", "config.json")


def locate_skill_dir() -> tuple[str, str]:
    """定位技能根(含 config.example.json / config.json 的目录)。

    返回 (技能根, 诊断说明)。搜索起点:
      - frozen(exe):`sys.executable` 所在目录 —— exe 在 tools/config-editor/ 下,
        向上 3 级即技能根;被拷贝到别处也能靠标志文件找到;
      - 源码态:`__file__` 所在 scripts/,向上 1 级即技能根。
    最多向上 6 级;都找不到则回落到「起点」并如实报告,由界面提示用户。
    """
    frozen = bool(getattr(sys, "frozen", False))
    start = os.path.dirname(os.path.abspath(
        sys.executable if frozen else __file__))
    d = start
    for _ in range(6):
        if any(os.path.isfile(os.path.join(d, m)) for m in SKILL_MARKERS):
            verb = "exe" if frozen else "源码"
            return d, f"已定位技能根({verb}态,自 {start} 上溯)"
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return start, f"[!] 未找到 config.example.json(自 {start} 上溯 6 级),请手动确认路径"


SKILL_DIR, LOCATE_NOTE = locate_skill_dir()
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")
EXAMPLE = os.path.join(SKILL_DIR, "config.example.json")

# 键 → (中文名, 类型, 获取指引)
FIELDS = [
    ("wpi_path", "WPI 渲染引擎路径", "dir",
     "WPI 项目根目录(里面应有 src\\core\\controller.py)。\n"
     "没有?跑 scripts\\setup_wpi.py 一键从 GitHub 下载部署,\n"
     "或手动克隆 github.com/GreenChennai/WPI。"),
    ("studio_dir", "作品落盘目录", "dir",
     "生成的海报项目保存位置,例如 E:\\artboard-studio。\n"
     "每个海报会建一个子文件夹(src/ 源码 + export/ 成品图)。"),
    ("ffmpeg", "FFmpeg 路径(可选)", "file",
     "ffmpeg.exe 的完整路径。用于高质量 GIF 与 MP4 视频。\n"
     "没有?跑 scripts\\setup_ffmpeg.py 一键下载部署;留空则 MP4 不可用。"),
    ("pexels_key", "Pexels API Key", "text",
     "免费图库 Pexels 的密钥。获取:注册 pexels.com → 登录(验证邮箱、\n"
     "设置用户名头像)→ 回主页悬停右上角「…」→「图片和视频 API」→\n"
     "填写名称与用途说明 → 即刻发放。"),
    ("pixabay_key", "Pixabay API Key", "text",
     "免费图库 Pixabay 的密钥。获取:注册 pixabay.com → 登录(验证邮箱、\n"
     "完善基础信息)→ 打开 pixabay.com/api/docs/ → 页内「Your API key」\n"
     "后面的字符串就是。"),
    ("huaban_cookie", "花瓣网 Cookie(可选)", "text",
     "花瓣搜索通道用。浏览器登录 huaban.com → F12 → 网络(Network)\n"
     "→ 刷新 → 任一请求 → 请求头 Cookie 全值复制。\n"
     "更简单:用 tools\\cookie-extension 插件一键抓取。"),
    ("iconfont_cookie", "图标库 Cookie(可选)", "text",
     "iconfont.cn 矢量图标搜索用。同上,在 iconfont.cn 登录后抓取。"),
    ("pinterest_cookie", "Pinterest Cookie(可选)", "text",
     "Pinterest 图片搜索用(国内网络需代理)。登录 pinterest.com 后抓取。"),
    ("proxy", "本地代理(可选)", "text",
     "访问 Pinterest 等境外源的代理,如 http://127.0.0.1:7890。\n"
     "留空 = 直连。"),
    ("wpi_cli_exe", "WPI CLI 单文件(可选)", "file",
     "WPI-noGUI-cli.exe 的完整路径(约 63MB 单文件引擎)。\n"
     "跑 scripts\\setup_wpi.py 自动从 artboard 发行页下载部署;\n"
     "手动更新:下载新 exe 覆盖即可。"),
    ("vision_mode", "视觉识别模式", "choice: auto,local",
     "auto = Agent 自带视觉优先(推荐);\nlocal = 强制用本地 VQA/OCR 模型。"),
    ("vqa_path", "本地 VQA 路径(可选)", "dir",
     "本地图片问答模块目录(内含 qora_assets\\qor08b.exe)。\n"
     "没有?跑 scripts\\fetch_model.py vqa 从 GitHub 发行页下载。"),
    ("ocr_path", "本地 OCR 路径(可选)", "dir",
     "本地 OCR 模块目录(内含 OCR.exe)。没有?跑 scripts\\fetch_model.py ocr。\n"
     "注:artboard 主流水线不消费 OCR(复刻走 Agent 视觉,见 ADR-0003)。"),
    ("poppler_dir", "Poppler 目录(可选)", "dir",
     "矢量导出用的 poppler 工具目录(内含 pdftocairo.exe / pdftops.exe)。\n"
     "没有?跑 scripts\\setup_vector.py 一键部署。"),
    ("gs_path", "Ghostscript 路径(可选)", "file",
     "gswin64c.exe / gs.exe 的完整路径,用于 EPS 与转曲 PDF。\n"
     "没有?跑 scripts\\setup_vector.py 一键部署。"),
]


def load_config() -> dict:
    for path in (CONFIG_PATH, EXAMPLE):
        if os.path.isfile(path):
            try:
                return json.load(open(path, encoding="utf-8"))
            except Exception:
                pass
    return {}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("artboard 配置编辑器 v1.7.3")
        self.geometry("900x680")
        self.minsize(720, 520)
        cfg = load_config()

        head = tk.Label(self, text="artboard 配置(保存即生效,无需重启)",
                        font=("Microsoft YaHei UI", 12, "bold"), anchor="w")
        head.pack(fill="x", padx=14, pady=(12, 2))

        # 关键诊断:把"实际会写到哪"显示出来(旧版写错目录却毫无提示)
        warn = "[!] 未定位到技能根" in LOCATE_NOTE
        path_lbl = tk.Label(
            self, text=f"写入目标:{CONFIG_PATH}", anchor="w", justify="left",
            fg="#c0392b" if warn else "#5a5a5a",
            font=("Consolas", 8), wraplength=740)
        path_lbl.pack(fill="x", padx=14)
        tk.Label(self, text=LOCATE_NOTE, anchor="w",
                 fg="#c0392b" if warn else "#8a8a8a",
                 font=("Microsoft YaHei UI", 8)).pack(fill="x", padx=14, pady=(0, 6))

        # 可滚动区:15 个字段 + 指引行远超窗口高度,不加滚动会看不到末尾几项
        wrap = tk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=(14, 4))
        canvas = tk.Canvas(wrap, highlightthickness=0, borderwidth=0)
        vsb = tk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        body = tk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(win_id, width=e.width))
        self.bind_all("<MouseWheel>",
                      lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        self.widgets = {}
        for i, (key, label, kind, guide) in enumerate(FIELDS):
            row = tk.Frame(body)
            row.pack(fill="x", pady=3)
            lbl = tk.Label(row, text=label, width=18, anchor="w",
                           font=("Microsoft YaHei UI", 10))
            lbl.pack(side="left")
            val = str(cfg.get(key, ""))
            if kind.startswith("choice"):
                options = kind.split(":", 1)[1].split(",")
                var = tk.StringVar(value=val or options[0])
                w = tk.OptionMenu(row, var, *options)
                w.configure(width=38)
                w.pack(side="left", fill="x", expand=True)
                self.widgets[key] = ("var", var, guide)
            else:
                var = tk.StringVar(value=val)
                ent = tk.Entry(row, textvariable=var,
                               font=("Consolas", 10))
                ent.pack(side="left", fill="x", expand=True)
                if kind == "dir":
                    btn = tk.Button(row, text="浏览…", width=6,
                                    command=lambda v=var: self._pick_dir(v))
                    btn.pack(side="left", padx=(6, 0))
                elif kind == "file":
                    btn = tk.Button(row, text="浏览…", width=6,
                                    command=lambda v=var: self._pick_file(v))
                    btn.pack(side="left", padx=(6, 0))
                self.widgets[key] = ("var", var, guide)
            # 指引行
            tip = tk.Label(body, text=guide, justify="left", anchor="w",
                           font=("Microsoft YaHei UI", 8), fg="#7a7a7a")
            tip.pack(fill="x", padx=(150, 0))

        btns = tk.Frame(self)
        btns.pack(fill="x", padx=14, pady=12)
        tk.Button(btns, text="保存", width=14, bg="#2ee6a8",
                  font=("Microsoft YaHei UI", 10, "bold"),
                  command=self.save).pack(side="left")
        tk.Button(btns, text="另存为…", width=10,
                  command=lambda: self.save(ask=True)).pack(side="left", padx=8)
        tk.Button(btns, text="打开所在目录", width=12,
                  command=self._open_dir).pack(side="left", padx=8)
        self.status = tk.Label(btns, text="", fg="#0a7d4b",
                               font=("Microsoft YaHei UI", 10))
        self.status.pack(side="left", padx=10)

    def _pick_dir(self, var):
        d = filedialog.askdirectory()
        if d:
            var.set(os.path.normpath(d))

    def _pick_file(self, var):
        f = filedialog.askopenfilename()
        if f:
            var.set(os.path.normpath(f))

    def _open_dir(self):
        d = os.path.dirname(CONFIG_PATH)
        if os.path.isdir(d):
            os.startfile(d)                      # noqa: S606 — Windows 资源管理器
        else:
            messagebox.showwarning("目录不存在", d)

    def save(self, ask=False):
        data = load_config()
        for key, (kind, var, _g) in self.widgets.items():
            data[key] = var.get().strip()
        # 与 config.json 的其它键合并(不丢手工写过的内容)
        if os.path.isfile(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, encoding="utf-8") as f:
                    old = json.load(f)
                if isinstance(old, dict):
                    old.update(data)
                    data = old
            except (OSError, ValueError):
                pass
        path = CONFIG_PATH
        if ask:
            path = filedialog.asksaveasfilename(
                defaultextension=".json", initialfile="config.json",
                filetypes=[("JSON", "*.json")])
            if not path:
                return
        elif "[!] 未定位到技能根" in LOCATE_NOTE:
            if not messagebox.askyesno(
                    "路径可疑",
                    f"未能自动定位技能根,当前将写入:\n{path}\n\n"
                    f"若这不是 <技能根>\\config.json,脚本读不到,配置不会生效。\n"
                    f"确定继续?"):
                return
        try:
            # 原子写:先 .tmp 再 replace,避免写一半崩溃留下截断的 config.json
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            self.status.config(text=f"✓ 已写入 {path}")
            print(f"[config] 已写入: {path}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))


if __name__ == "__main__":
    # 排障/自检:打印定位结果后退出(不弹窗)。
    #   python scripts/config_gui.py --locate
    #   tools\config-editor\artboard-config-editor.exe --locate
    if "--locate" in sys.argv:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(f"frozen      = {bool(getattr(sys, 'frozen', False))}")
        print(f"skill_dir   = {SKILL_DIR}")
        print(f"config.json = {CONFIG_PATH}")
        print(f"example     = {EXAMPLE}")
        print(f"note        = {LOCATE_NOTE}")
        raise SystemExit(0)
    App().mainloop()
