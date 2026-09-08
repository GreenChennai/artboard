r"""artboard 配置编辑器(纯 tkinter,零第三方依赖,可 PyInstaller 打包成单文件 exe)。

功能:可视化编辑 config.json 的全部键,保存时自动校验 JSON 合法性,
小白不再需要手工处理逗号/引号。

打包 exe:
  pyinstaller --onefile --windowed --name artboard-config-editor config_gui.py
"""

import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.isfile(os.path.join(SKILL_DIR, "config.json")) or \
        os.path.isfile(os.path.join(SKILL_DIR, "config.example.json")):
    CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")
else:
    CONFIG_PATH = os.path.join(os.getcwd(), "config.json")
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
     "本地 OCR 模块目录(内含 OCR.exe)。没有?跑 scripts\\fetch_model.py ocr。"),
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
        self.title("artboard 配置编辑器")
        self.geometry("780x640")
        self.minsize(700, 560)
        cfg = load_config()

        head = tk.Label(self, text="artboard 配置(保存写入 config.json,即改即生效)",
                        font=("Microsoft YaHei UI", 12, "bold"), anchor="w")
        head.pack(fill="x", padx=14, pady=(12, 6))

        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=14)

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

    def save(self, ask=False):
        data = load_config()
        for key, (kind, var, _g) in self.widgets.items():
            data[key] = var.get().strip()
        path = CONFIG_PATH
        if ask:
            path = filedialog.asksaveasfilename(
                defaultextension=".json", initialfile="config.json",
                filetypes=[("JSON", "*.json")])
            if not path:
                return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.status.config(text=f"✓ 已保存 {os.path.basename(path)}(即改即生效)")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))


if __name__ == "__main__":
    App().mainloop()
