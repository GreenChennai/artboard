"""artboard 开工前检查单(Brief Gate)机检。

为什么需要它:铁律 8 要求「缺失 ≥1 强制补齐,不许用推荐值静默补齐」——但检查单
是否齐全此前只能靠 Agent 自觉。本脚本零 token 解析 design-prompt.txt 里的
【开工前检查单】块(或「直接做」路径的【假设清单(请确认)】块),机械判定
必需字段是否齐备,把"猜着开工"拦在机检门上。

用法:
  python check_brief.py <项目>/design-prompt.txt

解析口径(与 references/intake.md §开工前检查单 的模板逐字对应):
  ✅ 已给    用途=小红书封面 | 尺寸=1080×1440 | 禁忌=不要蓝紫渐变
  🟡 可推定  配色=暖纸(依据:你选了"有质感手账风")
  ❌ 缺失    ① 必含文案元素  ② 是否要配图(初判:建议)

只报「必需字段缺失」,不做语义判断(防误报):🟡 缺"依据"只在 stderr 提醒,不影响退出码。

输出:stdout 单行 JSON {ok, missing, assumed, given};人类可读清单走 stderr。
退出码 0=齐 / 1=有缺失或文件缺失 / 2=用法错
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# 9 字段与别名(intake.md §开工前检查单 的字段表;匹配用"片段包含别名"策略)
FIELDS: dict[str, tuple[str, ...]] = {
    "用途": ("用途", "投放", "用在哪", "使用场景", "场景"),
    "尺寸": ("尺寸", "比例", "画布"),
    "风格": ("风格", "气质"),
    "配色": ("配色", "品牌色", "色板", "颜色"),
    "素材": ("素材", "配图", "图片", "照片", "图库"),
    "必含文案": ("必含文案", "必含元素", "文案元素", "必含"),
    "交付格式": ("交付格式", "交付", "格式"),
    "禁忌": ("禁忌", "反参照"),
    "期限": ("期限", "deadline", "截止", "优先级"),
}
REQUIRED = ("用途", "尺寸", "风格", "配色", "素材", "必含文案")

MARKER = "【开工前检查单】"
MARKER_ASSUME = "【假设清单"
STATE_RE = re.compile(r"[✅🟡❌]")


def canon(fragment: str) -> str | None:
    """片段 → 规范字段名;匹配不到返回 None。"""
    frag = fragment.strip().strip("、,;。 ")
    for name, aliases in FIELDS.items():
        if frag == name or any(alias in frag for alias in aliases):
            return name
    return None


def parse_field_tokens(line: str) -> list[str]:
    """一行里的「字段=值 | 字段=值」→ 字段名列表;裸字段名也认。"""
    out: list[str] = []
    for token in re.split(r"[|｜]", line):
        token = token.strip()
        if not token:
            continue
        head = token.split("=", 1)[0].strip()
        name = canon(head)
        if name:
            out.append(name)
    return out


def parse_missing_items(line: str) -> list[str]:
    """❌ 行 → 缺失项列表(规范字段名;映射不上的保留原文片段)。"""
    body = line.split("缺失", 1)[-1] if "缺失" in line else line
    parts = re.split(r"[①②③④⑤⑥⑦⑧⑨⑩、]", body)
    out: list[str] = []
    for part in parts:
        part = part.strip(" ,;。()（）")
        if not part:
            continue
        out.append(canon(part) or part)
    return out


def extract_block(text: str, marker: str, need_state: bool = True) -> list[str]:
    """取【marker】块的行,直到下一个【小节或 EOF。
    need_state=True 只收三态标记行(检查单);False 收全部行(假设清单无三态标记)。"""
    lines = text.splitlines()
    out: list[str] = []
    inside = False
    for line in lines:
        if line.strip().startswith("【"):
            inside = line.strip().startswith(marker)
            continue
        if inside and (not need_state or STATE_RE.search(line)):
            out.append(line)
    return out


def check(path: str) -> dict:
    result: dict = {"ok": False, "missing": [], "assumed": [], "given": []}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        result["missing"] = list(REQUIRED)
        return result

    state_lines = extract_block(text, MARKER)
    if not state_lines:
        # 「直接做」路径:没有检查单,但有假设清单 → 字段视为已给(假设确认留痕)
        assume_lines = extract_block(text, MARKER_ASSUME, need_state=False)
        given: set[str] = set()
        for line in assume_lines:
            given.update(parse_field_tokens(line))
        result["given"] = sorted(given)
        result["missing"] = [f for f in REQUIRED if f not in given]
        result["ok"] = not result["missing"]
        if not assume_lines:
            result["missing"] = list(REQUIRED)
        return result

    given: set[str] = set()
    assumed: set[str] = set()
    missing: list[str] = []
    for line in state_lines:
        if "✅" in line:
            given.update(parse_field_tokens(line))
        elif "🟡" in line:
            assumed.update(parse_field_tokens(line))
            if "依据" not in line:
                print("提醒:🟡 可推定项未写「依据」(铁律:可推定必须带依据,防'我以为')",
                      file=sys.stderr)
        elif "❌" in line:
            missing.extend(parse_missing_items(line))

    resolved_missing = {m for m in missing if m in REQUIRED}
    for field in REQUIRED:
        if field not in given and field not in assumed and field not in resolved_missing:
            resolved_missing.add(field)
    result["given"] = sorted(given)
    result["assumed"] = sorted(assumed)
    result["missing"] = sorted(resolved_missing)
    result["ok"] = not result["missing"]
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Brief Gate 开工前检查单机检(细则见 references/intake.md)")
    ap.add_argument("file", help="design-prompt.txt 路径")
    args = ap.parse_args()

    result = check(args.file)
    print(json.dumps(result, ensure_ascii=False))
    if not result["ok"]:
        print(f"缺失 {len(result['missing'])} 项必需字段:{'、'.join(result['missing'])}"
              f" —— 铁律 8:缺失 ≥1 强制补齐一轮,不许按推荐静默开工", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
