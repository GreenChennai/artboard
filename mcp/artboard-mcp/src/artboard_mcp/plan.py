"""配图必要性判定表(materials.md §0 的可执行形态)。

对应 03 迭代 D-03-1/D-03-2:把"要不要配图"从隐性变可审计——
判定结果 + 理由写入 project.json.image_plan;氛围/背景/纹理类不问即主动检索;
产品本体 / 人物肖像 / 品牌资产必须先问(materials.md 红线不动)。

判定三档:required(必须)/ recommended(建议)/ not_needed(不需要);
另有 conditional(视风格/品类,由风格或品类细节决定,判定时一并给默认动作)。
"""

from __future__ import annotations

import argparse
import json
import sys

# 品类关键字 → 判定(顺序即优先级;命中即停)
RULES: list[tuple[tuple[str, ...], dict]] = [
    (("片头", "片尾", "动效件", "视频卡", "场景卡", "章节卡", "转场"),
     {"need_images": "not_needed", "level": "none", "budget": 0, "must_ask": False,
      "reason": "视频动效件以排版/几何为主,不依赖照片(02:视频动效体系)"}),
    (("数据", "报告", "图表", "长图", "排行"),
     {"need_images": "not_needed", "level": "none", "budget": 0, "must_ask": False,
      "reason": "数据长图以图表与排版为主,配照片反而干扰读数"}),
    (("科技", "发布", "kv", "品牌", "发布会"),
     {"need_images": "recommended", "level": "optional", "budget": 2, "must_ask": False,
      "reason": "氛围/材质/场景图可提升质感但非必需;纯排版合法,主动检索不问"}),
    (("电商", "产品", "商品", "食品", "促销", "主图", "菜品"),
     {"need_images": "required", "level": "must", "budget": 2, "must_ask": True,
      "reason": "电商/食品/产品类必须有真实素材;产品本体只能用户提供(materials.md 红线),"
                "氛围图可主动检索"}),
    (("ootd", "穿搭", "探店", "摆盘", "实拍", "环境"),
     {"need_images": "required", "level": "must", "budget": 2, "must_ask": True,
      "reason": "依赖真实拍摄的品类图库糊弄不可接受,intake 即声明需要用户供图"}),
    (("小红书", "干货", "知识卡", "封面"),
     {"need_images": "conditional", "level": "optional", "budget": 2, "must_ask": False,
      "reason": "手账/贴纸/纯排版可零图;若风格吃照片(摄影感)则主动检索 0-2 张氛围图"}),
    (("名片", "三折页", "易拉宝", "印刷", "a4"),
     {"need_images": "conditional", "level": "optional", "budget": 2, "must_ask": False,
      "reason": "印刷类视品类:慎用低清图,300dpi 需求下优先矢量/排版;用图则主动检索高清源"}),
    (("公众号", "双封面", "gzh"),
     {"need_images": "recommended", "level": "optional", "budget": 1, "must_ask": False,
      "reason": "信息流缩略图靠主体辨识,0-1 张氛围图即可;主动检索"}),
    (("电影", "活动", "演出", "赛事"),
     {"need_images": "recommended", "level": "optional", "budget": 1, "must_ask": False,
      "reason": "主体可由排版承担,0-1 张氛围图造气氛;主动检索"}),
]
FALLBACK = {"need_images": "conditional", "level": "optional", "budget": 2, "must_ask": False,
            "reason": "未命中已知品类,按默认预算 0-2 张氛围图主动检索;"
                      "用户给了明确'不要配图'则以用户为准"}

STYLE_HINTS = (("手账", "贴纸", "纯排版", "极简", "瑞士", "编辑"), "该风格可零图,倾向不配图"), \
              (("摄影", "真实", "质感", "胶片", "food"), "该风格吃真实照片,倾向配图")


def plan(brief: str, category: str = "", style: str = "",
         need: str = "") -> dict:
    """判定是否需要配图。need ∈ {"", "yes", "no"} 为用户显式覆盖(记录原因)。"""
    text = f"{category} {brief}".lower()
    hit = next((rule for kws, rule in RULES
                if any(k.lower() in text for k in kws)), FALLBACK)
    out = {"category": category or ("auto:" + next(
        (kws[0] for kws, rule in RULES if rule is hit), "generic")),
           **hit, "style": style or None}
    # 风格微调(不翻档,只调理由)
    if out["need_images"] != "not_needed" and style:
        for kws, note in STYLE_HINTS:
            if any(k in style for k in kws):
                out["reason"] += f";{note}"
                break
    # 用户显式覆盖优先,并留痕
    if need == "yes":
        out.update({"need_images": "required", "must_ask": False,
                    "reason": "用户显式要求配图(覆盖判定表):" + out["reason"]})
    elif need == "no":
        out.update({"need_images": "not_needed", "level": "none", "budget": 0,
                    "reason": "用户显式要求不配图(覆盖判定表),交付时按纯排版说明"})
    out["suggested_queries"] = suggest_queries(out, brief)
    return out


def suggest_queries(verdict: dict, brief: str) -> list[str]:
    """给 2-3 条英文检索词(图库英文命中率高于中文,materials.md 惯例)。"""
    if verdict["need_images"] == "not_needed":
        return []
    theme = {
        "科技": "abstract dark gradient texture", "kv": "abstract dark gradient texture",
        "食品": "food photography close up warm light", "产品": "product photography studio light",
        "小红书": "cozy desk lifestyle flat lay", "干货": "cozy desk lifestyle flat lay",
        "公众号": "clean minimal background texture", "电影": "cinematic moody atmosphere",
        "名片": "paper texture premium close up", "印刷": "paper texture premium close up",
    }
    for k, q in theme.items():
        if k in brief or k in str(verdict.get("reason", "")):
            return [q]
    return ["minimal background texture", "soft gradient atmosphere"]


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="配图必要性判定(写入 project.json.image_plan 前调用)")
    ap.add_argument("--brief", required=True, help="需求一句话(品类关键词命中判定表)")
    ap.add_argument("--category", default="", help="显式品类(可选)")
    ap.add_argument("--style", default="", help="风格 slug 或气质词(可选)")
    ap.add_argument("--need", default="", choices=["", "yes", "no"], help="用户显式覆盖")
    args = ap.parse_args(argv)
    print(json.dumps(plan(args.brief, args.category, args.style, args.need),
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
