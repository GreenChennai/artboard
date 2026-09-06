"""artboard VQA:调用本地 VQA 项目解释图片内容(离线,CPU)。

用法:
  python vqa.py <图片...> [--prompt "问题"] [--mode qora|caption]

  qora(默认)  — QORA-0.8B 中文问答:可自定义问题("图里有什么文字?""这瓶饮料是什么口味?")
  caption      — MiniCap 英文一句描述(快,备用;qora 失败时自动回退)

输出:单行 JSON {ok, results:[{image, description, mode}]}
配置:vqa_path(config.json 或环境变量 ARTBOARD_VQA)。
"""

import argparse
import json
import os
import subprocess
import sys

from _config import cfg

DEFAULT_PROMPT = "用中文详细描述这张图片的内容,包括主体、颜色、场景和可见文字。"


def emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def run_qora(img: str, prompt: str) -> str:
    vqa = cfg("vqa_path")
    exe = os.path.join(vqa, "qora_assets", "qor08b.exe")
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"qor08b.exe 不存在: {exe}")
    cmd = [exe, "--prompt", prompt, "--image", os.path.abspath(img), "--no-think"]
    r = subprocess.run(cmd, cwd=os.path.dirname(exe), capture_output=True,
                       encoding="utf-8", errors="ignore", timeout=300)
    out = (r.stdout or "").strip()
    if not out:
        raise RuntimeError(f"qora 无输出(stderr: {(r.stderr or '')[:120]})")
    return out


def run_caption(img: str) -> str:
    vqa = cfg("vqa_path")
    py = os.path.join(vqa, "venv", "Scripts", "python.exe")
    script = os.path.join(vqa, "caption.py")
    for p in (py, script):
        if not os.path.isfile(p):
            raise FileNotFoundError(p)
    r = subprocess.run([py, script, os.path.abspath(img)], cwd=vqa, capture_output=True,
                       encoding="utf-8", errors="ignore", timeout=300)
    out = (r.stdout or "").strip()
    if not out:
        raise RuntimeError(f"caption 无输出(stderr: {(r.stderr or '')[:120]})")
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("images", nargs="+")
    p.add_argument("--prompt", default=DEFAULT_PROMPT)
    p.add_argument("--mode", default="qora", choices=["qora", "caption"])
    args = p.parse_args()

    if not cfg("vqa_path"):
        emit({"ok": False, "error": "NO_VQA_PATH",
              "hint": "config.json 填 vqa_path(本地 VQA 项目路径)"})
        return 2

    results = []
    for img in args.images:
        if not os.path.isfile(img):
            results.append({"image": img, "error": "文件不存在"})
            continue
        desc, used, err = "", args.mode, None
        try:
            desc = run_qora(img, args.prompt) if args.mode == "qora" else run_caption(img)
        except Exception as exc:  # noqa: BLE001 — qora 失败回退 caption(反向不回退)
            err = f"{type(exc).__name__}: {str(exc)[:160]}"
            if args.mode == "qora":
                try:
                    desc = run_caption(img)
                    used = "caption(fallback)"
                except Exception as exc2:  # noqa: BLE001
                    err += f" | caption 回退也失败: {type(exc2).__name__}: {str(exc2)[:120]}"
        results.append({"image": os.path.abspath(img), "description": desc,
                        "mode": used, "error": err} if not desc
                       else {"image": os.path.abspath(img), "description": desc, "mode": used})

    ok = all("description" in r and r["description"] for r in results)
    emit({"ok": ok, "results": results})
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
