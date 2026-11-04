#!/usr/bin/env python3
"""在 173 条美学风格库中检索风格。

用法：
    python3 scripts/find_style.py 水墨
    python3 scripts/find_style.py "干净 日系" --top 5 --json
    python3 scripts/find_style.py --category CN
    python3 scripts/find_style.py --code CN-01
    python3 scripts/find_style.py --random 3

退出码：0 有结果 / 1 无匹配 / 2 参数或数据错误
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "assets" / "styles-173.json"

EXACT_NAME, EXACT_ALIAS, PARTIAL_NAME, PARTIAL_ALIAS, EN_HIT, BODY_HIT = 100, 92, 78, 66, 70, 24

# 口语 → 风格编号。用户说的往往不是风格名而是感受，这里做一层显式翻译。
# 只收录有共识的映射；表里没有的词不会硬猜。
INTENT_MAP = {
    "高级": [1, 139, 90, 8], "高级感": [1, 139, 90, 8],
    "干净": [44, 90, 1], "清爽": [44, 45, 90], "性冷淡": [90, 139, 145],
    "治愈": [46, 126, 135, 44], "温暖": [149, 47, 126],
    "文艺": [126, 109, 135, 29], "复古": [42, 96, 60, 112],
    "怀旧": [42, 97, 112, 168], "老旧": [8, 97, 42],
    "赛博": [92, 106, 142], "未来": [92, 107, 95, 104],
    "国风": [6, 21, 37, 12], "古风": [2, 30, 22, 18],
    "东方": [1, 7, 10, 11], "日系": [44, 48, 46, 45],
    "清新": [135, 140, 44, 151], "梦幻": [151, 66, 108, 140],
    "潮流": [94, 101, 93], "年轻": [94, 141, 121, 101],
    "压抑": [153, 152, 98], "恐怖": [153, 25, 152],
    "奢华": [2, 71, 70, 26], "贵气": [2, 26, 71],
    "极简": [90, 1, 11], "繁复": [91, 71, 19],
    "手绘": [135, 130, 162, 126], "照片": [109, 114, 112],
    "真实": [114, 119, 109], "电影": [119, 155], "海报": [83, 127, 91],
    "插画": [127, 128, 135, 126], "头像": [114, 120, 121],
    "产品": [115, 119, 90], "包装": [83, 90, 127],
}
INTENT_BOOST = 60


def load():
    try:
        return json.loads(DATA.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"数据文件缺失：{DATA}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"数据文件损坏：{exc}", file=sys.stderr)
        sys.exit(2)


def score_one(style: dict, terms: list[str]) -> tuple[int, list[str]]:
    """返回 (得分, 命中说明)。多个检索词按累加计分，避免单词误伤。"""
    total, hits = 0, []
    name = style["name"].lower()
    name_en = style["name_en"].lower()
    aliases = [a.lower() for a in style["aliases"]]
    body = (style["template"] + style["sample"]).lower()

    for term in terms:
        if term == name:
            total += EXACT_NAME
            hits.append(f"名称精确:{style['name']}")
        elif term in aliases:
            total += EXACT_ALIAS
            hits.append("别名精确")
        elif term in name:
            total += PARTIAL_NAME
            hits.append(f"名称包含:{term}")
        elif any(term in a for a in aliases):
            total += PARTIAL_ALIAS
            hits.append(f"别名包含:{term}")
        elif term in name_en:
            total += EN_HIT
            hits.append(f"英文名:{style['name_en']}")
        elif term in body:
            total += BODY_HIT
            hits.append(f"模板命中:{term}")
        for key, ids in INTENT_MAP.items():
            if key in term and style["id"] in ids:
                total += INTENT_BOOST
                hits.append(f"口语映射:{key}")
                break
    if style["flags"]["broad"] and total:
        total -= 12          # 名称过宽的条目降权，避免"风景""卡通"抢答
    return total, hits


def brief(style: dict, score: int, hits: list[str]) -> dict:
    return {
        "id": style["id"],
        "code": style["code"],
        "name": style["name"],
        "name_en": style["name_en"],
        "category": style["category_name"],
        "score": score,
        "matched": hits,
        "template": style["template"],
        "flags": style["flags"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="173 种美学风格检索")
    ap.add_argument("query", nargs="*", help="风格名 / 别名 / 英文名 / 描述关键词，可多个")
    ap.add_argument("--category", help="按分类码过滤：CN/JP/WR/WE/DG/PH/IL/CO/SB/EX")
    ap.add_argument("--code", help="按风格编号精确取单条，如 CN-01")
    ap.add_argument("--top", type=int, default=5, help="返回条数，默认 5")
    ap.add_argument("--random", type=int, metavar="N", help="随机取 N 条做灵感探索")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args()

    db = load()
    styles = db["styles"]

    if args.code:
        hit = [s for s in styles if s["code"].lower() == args.code.lower()]
        if not hit:
            print(f"未找到编号 {args.code}", file=sys.stderr)
            sys.exit(1)
        picked = [brief(hit[0], 100, ["编号命中"])]
    elif args.random:
        picked = [brief(s, 0, ["随机"]) for s in random.sample(styles, min(args.random, len(styles)))]
    elif args.category:
        code = args.category.upper()
        if code not in {c["code"] for c in db["categories"]}:
            print(f"未知分类码 {code}", file=sys.stderr)
            sys.exit(2)
        subset = [s for s in styles if s["category"] == code]
        picked = [brief(s, 0, ["分类浏览"]) for s in subset]
    elif args.query:
        terms = [q.lower() for q in args.query if q.strip()]
        ranked = []
        for s in styles:
            sc, hits = score_one(s, terms)
            if sc > 0:
                ranked.append((sc, s, hits))
        ranked.sort(key=lambda x: (-x[0], x[1]["id"]))
        picked = [brief(s, sc, hits) for sc, s, hits in ranked[: args.top]]
    else:
        ap.print_help()
        sys.exit(2)

    if not picked:
        if args.json:
            print(json.dumps({"query": args.query, "results": []}, ensure_ascii=False))
        else:
            print("没有匹配的风格。可换用更具体的词（如：水墨 / 侘寂 / 赛博 / 胶片），或先按分类浏览 --category CN")
        sys.exit(1)

    if args.json:
        print(json.dumps({"query": args.query, "count": len(picked), "results": picked},
                         ensure_ascii=False, indent=1))
        return

    print(f"命中 {len(picked)} 条\n")
    for r in picked:
        mark = []
        if r["flags"]["broad"]:
            mark.append("名称较宽/需补充限定")
        if r["flags"]["living_artist"]:
            mark.append("在世艺术家/须转写特征")
        note = f"  [{'；'.join(mark)}]" if mark else ""
        print(f"[{r['code']}] #{r['id']} {r['name']} / {r['name_en']}{note}")
        print(f"  {r['template']}")
        if r["flags"]["related"]:
            near = [s["name"] for s in styles if s["id"] in r["flags"]["related"]]
            print(f"  近邻易混：{'、'.join(near)}")
        print()


if __name__ == "__main__":
    main()
