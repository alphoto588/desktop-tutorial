#!/usr/bin/env python3
"""一句话出稿：把「澄清 → 检索 → 组装 → 检查」压成一步。

完整流程（intake → find_style → build_prompt → lint_prompt）适合正式交付，
但初次使用或随手出图时步骤偏多。本脚本只做编排，不重写任何规则：
所有判断都复用既有模块，输出与分步执行完全一致。

**定位是草稿通道**：模型缺省、风格兜底都是为了「先看到一版」。
正式交付仍按 SKILL.md 第 0 步确认模型与风格，再用 --model / --style 锁定复跑。

用法：
    python3 scripts/quick.py "国潮茶叶海报，用 Qwen-Image，3:4"
    python3 scripts/quick.py "赛博朋克雨夜街头" --model flux2-klein-base-9b
    python3 scripts/quick.py "一只青瓷茶壶" --style CN-01 --layout SM-01 --color 月白
    python3 scripts/quick.py "..." --json        # 机器可读
    python3 scripts/quick.py --list-models       # 看全部可用模型

只写一句话也能出稿：模型缺省用 Z-Image-Turbo（最通用的起点），
风格按需求文本自动推荐，比例用模型的默认比例。

退出码：0 出稿且自检通过 / 1 自检未通过 / 2 参数或数据问题
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_prompt as bp
import intake
import layout_registry as lr
import model_registry as mr
import model_render

# 一句话出稿时的兜底模型：最通用、语法最宽容的起点
DEFAULT_MODEL = "z-image-turbo"
# 一条线索都没撞上时的兜底画风：极简主义不预设题材，改起来代价最小
DEFAULT_STYLE = "DG-01"


def fallback_style(text: str) -> dict | None:
    """intake.suggest_styles 按整词打分，词表里没有的长短语会全落空。

    这里退一步，用 4→3→2 字滑窗去撞风格名/别名，能救回「水墨远山」
    「极简白瓷花瓶」这类没有分词的短句。命中即取最长的那个窗口。
    """
    db = bp.load()["styles"]
    for size in (4, 3, 2):
        for i in range(len(text) - size + 1):
            gram = text[i:i + size]
            if not re.fullmatch(r"[\u4e00-\u9fa5]{%d}" % size, gram):
                continue
            for s in db:
                if s["category"] == "CO":       # 调性类只调色，不当画风
                    continue
                if gram in s["name"] + "".join(s["aliases"]):
                    return s
    return None


def _norm(s: str) -> str:
    """归一化：忽略大小写与空格/下划线/连字符/点，方便「Flux.2-klein-9B」对上路。"""
    return re.sub(r"[\s_.\-]+", "", s.lower())


def _alias_pattern(alias: str) -> str:
    """把别名编成正则，允许字符间夹任意分隔符。"""
    return r"[\s_.\-]*".join(re.escape(ch) for ch in alias)


def parse_model(text: str) -> dict | None:
    """取最长命中的别名，避免 "flux" 抢先吃掉 "flux2-klein-base-9b"。"""
    t = _norm(text)
    best, best_len = None, 0
    for m in mr.offered():
        for alias in [m["id"], *m["aliases"]]:
            a = _norm(alias)
            if a and a in t and len(a) > best_len:
                best, best_len = m, len(a)
    return best


def parse_aspect(text: str) -> str:
    m = re.search(r"(\d+)\s*[:：]\s*(\d+)", text)
    return f"{m.group(1)}:{m.group(2)}" if m else ""


def parse_scene(text: str) -> str:
    for scene, kws in intake.SCENE_HINTS.items():
        if any(k in text for k in kws):
            return scene
    return "个人练习"


def parse_layout(text: str) -> dict | None:
    m = re.search(r"\b(SM|IG|CM|IP|EC)-(\d{2})\b", text, re.I)
    return lr.resolve_layout(m.group(0)) if m else None


def parse_color(text: str) -> dict | None:
    for c in lr.colors():
        if c["name_zh"] in text:
            return c
    return None


def strip_meta(text: str, model: dict | None, layout: dict | None, color: dict | None) -> str:
    """去掉模型名/比例/排版号/色名/场景词，剩下的当主体草稿。

    注意：只删「用/做/生成」这类动词前缀，不要用字符集整体剥离——
    那样会把「一只茶壶」的「一」也吃掉。
    """
    s = text
    if model:
        for a in sorted([model["id"], *model["aliases"]], key=len, reverse=True):
            s = re.sub(_alias_pattern(a), "", s, flags=re.I)
    if layout:
        s = s.replace(layout["id"], "")
    if color:
        s = s.replace(color["name_zh"], "")
    for kws in intake.SCENE_HINTS.values():
        for k in kws:
            s = s.replace(k, "")
    s = re.sub(r"\d+\s*[:：]\s*\d+", "", s)
    # 按逗号切段：丢掉只剩动词的碎段，以及残留的模型名碎段（含 - . _ 的拉丁串）
    verbs = {"用", "要", "做", "生成", "帮我", "请", "画", "来一张", "做一张"}
    parts = [x.strip() for x in re.split(r"[，,]", s) if x.strip()]
    parts = [x for x in parts
             if x not in verbs
             and not (re.search(r"[-._]", x) and re.search(r"[A-Za-z]", x) and len(x) < 32)]
    s = "，".join(parts)
    # 动词前缀可能连着写（"帮我做一张…"），重复剥两轮
    for _ in range(2):
        s = re.sub(r"^[\s，,。]*(?:用|要|帮我|请|做一张|做|生成|画|来一张)[\s，,]*", "", s)
    # 场景词被删后常留下"的"，收尾
    s = re.sub(r"[的，,\s]+$", "", s)
    return re.sub(r"[\s，,。]+$", "", s).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="一句话出稿（编排层，规则不变）")
    ap.add_argument("idea", nargs="?", help="一句话需求：主体 + 可选模型/比例/排版/色名")
    ap.add_argument("--model", help="指定模型，覆盖自动识别")
    ap.add_argument("--style", help="指定风格编号/名称，覆盖自动推荐")
    ap.add_argument("--layout", help="指定排版图型，如 SM-01")
    ap.add_argument("--color", help="指定主题色，如 月白")
    ap.add_argument("--no-lint", action="store_true", help="跳过成品自检")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    ap.add_argument("--list-models", action="store_true", help="列出全部可用模型后退出")
    a = ap.parse_args()

    if a.list_models:
        for i, m in enumerate(mr.offered(), 1):
            print(f"{i:2d}. {m['id']:<24} {m['label']}")
        sys.exit(0)

    if not a.idea:
        ap.print_help()
        sys.exit(2)

    model = mr.resolve(a.model) if a.model else parse_model(a.idea)
    if a.model and model is None:
        print(f"未找到模型：{a.model}\n用 --list-models 看全部可选。", file=sys.stderr)
        sys.exit(2)
    if model is None:
        model = mr.get(DEFAULT_MODEL)
        print(f"（没指定模型，按最通用的 {model['label']} 出稿；要换用 --model <id>）",
              file=sys.stderr)

    layout = lr.resolve_layout(a.layout) if a.layout else parse_layout(a.idea)
    if a.layout and layout is None:
        print(f"未找到排版图型：{a.layout}", file=sys.stderr)
        sys.exit(2)
    color = lr.resolve_color(a.color) if a.color else parse_color(a.idea)
    if a.color and color is None:
        print(f"未找到主题色：{a.color}", file=sys.stderr)
        sys.exit(2)

    aspect = parse_aspect(a.idea) or (layout["aspects"][0] if layout else "")
    scene = parse_scene(a.idea)
    subject = strip_meta(a.idea, model, layout, color)
    if not subject:
        print("没提取到主体：至少写一句「画什么」。", file=sys.stderr)
        sys.exit(2)

    # 风格：显式优先，否则按需求文本推荐第一档，再不行用兜底
    styles_db = bp.load()["styles"]
    if a.style:
        pick = bp.resolve(a.style, styles_db)
        if pick is None:
            print(f"未找到风格：{a.style}", file=sys.stderr)
            sys.exit(2)
        picks = [pick]
    else:
        cands = intake.suggest_styles(a.idea, n=1)
        picks = [c[2] for c in cands] if cands else []
        if not picks:
            fb = fallback_style(a.idea)
            if fb is not None:
                picks = [fb]
                print(f"（没读懂画风，按字面撞到 {fb['code']} {fb['name']}；--style 可换）",
                      file=sys.stderr)
            else:
                picks = [bp.resolve(DEFAULT_STYLE, styles_db)]
                print(f"（没读懂画风，先用 {DEFAULT_STYLE} 极简主义起稿；"
                      "--style 换风格，或跑 scripts/find_style.py 找候选）", file=sys.stderr)

    segs, _ = bp.build(subject, picks, ["color", "light"])
    opts = {
        "text_in_image": "",
        "transparent": False,
        "layout": ({"zh": lr.layout_clause(layout, "zh"), "en": lr.layout_clause(layout, "en")} if layout else None),
        "color": ({"zh": lr.color_clause(color, "zh"), "en": lr.color_clause(color, "en")} if color else None),
    }
    ratio, res = mr.aspect(model, aspect)
    detail = model_render.render(model, subject, segs, ratio, "", opts)

    lint_ok, lint_out = None, ""
    if not a.no_lint:
        r = subprocess.run([sys.executable, "-B", str(HERE / "lint_prompt.py"),
                            "--model", model["id"], "--text", detail["prompt"]],
                           capture_output=True, text=True)
        lint_ok = r.returncode == 0
        lint_out = (r.stdout or "").strip()

    if a.json:
        print(json.dumps({
            "idea": a.idea, "subject": subject, "scene": scene,
            "draft": True,
            "model": model["id"], "style": picks[0]["code"],
            "layout": layout["id"] if layout else None,
            "color": color["id"] if color else None,
            "aspect": ratio, "resolution": res,
            "prompt": detail["prompt"], "negative": detail["negative"],
            "params": detail["params"], "lint_ok": lint_ok,
        }, ensure_ascii=False, indent=1))
        sys.exit(0 if lint_ok in (True, None) else 1)

    print(f"【提示词】\n{detail['prompt']}\n")
    print(f"【配置】模型 {model['label']} · 风格 {picks[0]['code']} {picks[0]['name']} · "
          f"场景 {scene} · 比例 {ratio}" + (f" · 排版 {layout['id']}" if layout else "")
          + (f" · 主题色 {color['name_zh']}" if color else ""))
    print("【定位】草稿通道：模型/风格带默认值。正式交付前按 SKILL.md 第 0 步确认这两项再复跑，"
          "或用 --model / --style 锁定。")
    if detail["negative"]:
        print(f"【负向】{detail['negative']}")
    if not a.no_lint:
        tail = [l for l in lint_out.splitlines() if l.startswith("FAIL") or "不合格" in l]
        print(f"【自检】{'通过' if lint_ok else '未通过'}" + (f"：{tail[0][:60]}" if tail else ""))
        if not lint_ok:
            print("        逐项看：python3 scripts/lint_prompt.py --model "
                  f"{model['id']} --text \"<上面的提示词>\"")
    sys.exit(0 if lint_ok in (True, None) else 1)


if __name__ == "__main__":
    main()
