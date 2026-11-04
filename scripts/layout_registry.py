#!/usr/bin/env python3
"""排版图型与主题色的加载、解析、推荐。

两个数据源：
    assets/layouts.json   5 个家族 / 54 个图型
    assets/colors.json    36 个单色主题色

设计要点：图型只描述「信息怎么摆」，不描述「画成什么样」——后者由风格库负责。
两者是正交的，可以任意组合：风格 × 图型 × 主题色。

用法：
    python3 scripts/layout_registry.py --list
    python3 scripts/layout_registry.py --suggest 小红书
    python3 scripts/layout_registry.py --show IG-01
    python3 scripts/layout_registry.py --color 胭脂
退出码：0 正常 / 1 未找到
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAYOUTS = ROOT / "assets" / "layouts.json"
COLORS = ROOT / "assets" / "colors.json"

_CACHE: dict[str, dict] = {}


def _load(path: Path, key: str) -> dict:
    if key not in _CACHE:
        _CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
    return _CACHE[key]


def layouts() -> list[dict]:
    return _load(LAYOUTS, "layouts")["layouts"]


def families() -> list[dict]:
    return _load(LAYOUTS, "layouts")["families"]


def colors() -> list[dict]:
    return _load(COLORS, "colors")["colors"]


def _norm(s: str) -> str:
    return re.sub(r"[\s_\-]+", "", s.lower())


def resolve_layout(token: str) -> dict | None:
    t = _norm(token or "")
    if not t:
        return None
    for x in layouts():
        if t == _norm(x["id"]):
            return x
    for x in layouts():
        if t in _norm(x["name"]) or _norm(x["name"]) in t:
            return x
    return None


def resolve_color(token: str) -> dict | None:
    t = _norm(token or "")
    if not t:
        return None
    for c in colors():
        if t == _norm(c["id"]):
            return c
    for c in colors():
        if t in (_norm(c["name_zh"]), _norm(c["name_en"])):
            return c
    for c in colors():
        if t and t in _norm(c["name_zh"]):
            return c
    return None


def suggest(scene: str, limit: int = 4) -> list[dict]:
    """按场景关键词推图型。场景词可以是「小红书」「公众号」「长图」「电商」等。"""
    s = (scene or "").strip()
    if not s:
        return []
    mapping = _load(LAYOUTS, "layouts").get("scene_map", {})
    picked: list[str] = []
    for key, ids in mapping.items():
        if any(w and w in s for w in key.split("/")):
            picked.extend(ids)
    if not picked:
        for x in layouts():
            if s in x["use"] or s in x["name"]:
                picked.append(x["id"])
    out, seen = [], set()
    for i in picked:
        if i in seen:
            continue
        seen.add(i)
        hit = resolve_layout(i)
        if hit:
            out.append(hit)
        if len(out) >= limit:
            break
    return out


def layout_clause(layout: dict, lang: str = "zh") -> str:
    return layout["prompt_en"] if lang == "en" else layout["prompt_zh"]


def color_clause(color: dict, lang: str = "zh") -> str:
    if lang == "en":
        return (f"palette anchored on {color['name_en']}, kept restrained, "
                f"at most one accent color")
    return f"整体配色以{color['name_zh']}为主调，用量克制，最多再加一个点缀色"


def describe(layout: dict) -> str:
    fam = next((f for f in families() if f["code"] == layout["family"]), {})
    return (f"[{layout['id']}] {layout['name']}　{layout['use']}　"
            f"{'/'.join(layout['aspects'])}　信息密度 {layout['density']}　"
            f"（{fam.get('name_zh', layout['family'])}）")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="排版图型 / 主题色检索")
    ap.add_argument("--list", action="store_true", help="列出全部图型")
    ap.add_argument("--families", action="store_true", help="只列家族概览")
    ap.add_argument("--suggest", help="按场景推荐图型")
    ap.add_argument("--show", help="查看单个图型")
    ap.add_argument("--color", help="查看或检索主题色")
    a = ap.parse_args()

    if a.families:
        for f in families():
            print(f"{f['code']}  {f['name_zh']:<10} {f['count']:>2} 型   {f['use']}")
        return

    if a.list:
        for x in layouts():
            print(describe(x))
        return

    if a.suggest:
        hits = suggest(a.suggest)
        if not hits:
            print(f"没有匹配「{a.suggest}」的图型，试试：小红书 / 公众号 / 长图 / 电商 / 分镜 / IP", file=sys.stderr)
            sys.exit(1)
        for x in hits:
            print(describe(x))
        return

    if a.show:
        x = resolve_layout(a.show)
        if not x:
            print(f"未找到图型：{a.show}", file=sys.stderr)
            sys.exit(1)
        print(describe(x))
        print(f"  中文指令：{x['prompt_zh']}")
        print(f"  英文指令：{x['prompt_en']}")
        return

    if a.color:
        c = resolve_color(a.color)
        if c:
            print(f"[{c['id']}] {c['name_zh']} / {c['name_en']}　{c['hex']}　"
                  f"{c['family']}·{c['value']}　适合：{c['use']}　搭配：{c['pairs']}")
            return
        hits = [x for x in colors() if a.color in x["name_zh"] or a.color in x["use"]]
        for x in hits:
            print(f"[{x['id']}] {x['name_zh']} {x['hex']}　{x['use']}")
        if not hits:
            print(f"未找到颜色：{a.color}", file=sys.stderr)
            sys.exit(1)
        return

    print("用法：--list / --families / --suggest 场景 / --show 编号 / --color 色名")


if __name__ == "__main__":
    main()
