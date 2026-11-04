#!/usr/bin/env python3
"""反向解析：给一段现成提示词，判断它接近库里哪条风格、缺了哪些维度、怎么补。

打分方式是可解释的：命中风格名/别名 +3.0；命中该条目的特征词按 IDF 加权
（越罕见的词权重越高，"三远法"比"高级"更能标识一条风格）。

用法：
    python3 scripts/analyze_prompt.py "一只鹤站在浅水里，淡墨，留白很多，宣纸质感"
    python3 scripts/analyze_prompt.py --file draft.txt --top 3
    python3 scripts/analyze_prompt.py "..." --fix          # 用最接近的风格补齐缺口
    python3 scripts/analyze_prompt.py "..." --fix --style CN-12

局限：这是字面特征匹配，不是语义理解。措辞与你完全不同但意思相近的风格可能排不上来，
务必看候选列表人工确认。

退出码：0 找到候选 / 1 无候选 / 2 参数错误
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "assets" / "styles-173.json"
DIM_CN = {"style": "风格标记", "color": "色彩", "composition": "构图",
          "texture": "材质质感", "light": "光影", "quality": "画质细节", "mood": "情绪氛围"}
NAME_WEIGHT = 3.0
# 维度权重：色彩与材质最能标识一条风格，情绪最不能
DIM_WEIGHT = {"style": 1.2, "texture": 1.2, "color": 1.0, "light": 1.0,
              "quality": 0.8, "composition": 0.7, "mood": 0.6}


def build_idf(styles: list[dict]) -> dict[str, float]:
    df: dict[str, int] = {}
    for s in styles:
        seen = set()
        for seg in s["segments"]:
            seen.update(seg.get("kw", []))
        for w in seen:
            df[w] = df.get(w, 0) + 1
    total = len(styles) + 1
    return {w: math.log(total / (d + 0.5)) for w, d in df.items()}


def partial_hit(kw: str, text: str) -> bool:
    """长特征词允许部分命中：任意相邻两字出现在文本里。"""
    if len(kw) < 4:
        return False
    return any(kw[i:i + 2] in text for i in range(len(kw) - 1))


def score_style(style: dict, text: str, idf: dict[str, float]) -> dict:
    total = 0.0
    hits: list[str] = []
    # 名称/别名只计一次：同一概念不重复加分，避免"宣纸"与"宣纸画"双重计分
    name_hit = next((c for c in [style["name"], *style["aliases"]]
                     if len(c) >= 2 and c in text), None)
    if name_hit:
        total += NAME_WEIGHT
        hits.append(f"{name_hit}(名称)")

    dims = []
    for seg in style["segments"]:
        dim_hit = False
        for kw in seg.get("kw", []):
            if kw == name_hit:
                continue
            w = idf.get(kw, 1.0) * DIM_WEIGHT.get(seg["dim"], 1.0)
            if kw in text:
                total += w
                hits.append(kw)
                dim_hit = True
            elif partial_hit(kw, text):
                total += w * 0.5
                hits.append(f"{kw}~")
                dim_hit = True
        dims.append({"dim": seg["dim"], "dim_cn": DIM_CN[seg["dim"]],
                     "text": seg["text"], "hit": dim_hit})
    return {"score": total, "hits": list(dict.fromkeys(hits)), "dims": dims}


def main() -> None:
    ap = argparse.ArgumentParser(description="提示词反向解析")
    ap.add_argument("text", nargs="?", help="要分析的提示词")
    ap.add_argument("--file", help="从文件读取")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--fix", action="store_true", help="用最接近的风格补齐缺口")
    ap.add_argument("--style", help="指定用哪条风格来补")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    raw = args.text if args.text else (Path(args.file).read_text(encoding="utf-8") if args.file else "")
    raw = raw.strip()
    if not raw:
        print("需要提供提示词文本或 --file", file=sys.stderr)
        sys.exit(2)

    db = json.loads(DATA.read_text(encoding="utf-8"))
    styles = db["styles"]
    idf = build_idf(styles)

    scored = [(score_style(s, raw, idf), s) for s in styles]
    scored.sort(key=lambda x: -x[0]["score"])
    ranked = [x for x in scored if x[0]["score"] > 0][: args.top]

    if not ranked:
        print("没有命中任何库内特征。可能原因：① 描述太短且未用风格词汇；② 它是纯写实描述而非风格化表达；③ 库内没有这个流派")
        print("建议：先用 find_style.py 按关键词找，或直接描述你想要的画面让我推荐")
        sys.exit(1)

    if args.style:
        target = next((s for s in styles if args.style.lower() in
                       (s["code"].lower(), s["name"].lower(), str(s["id"]))), None)
        if not target:
            print(f"未找到指定风格 {args.style}", file=sys.stderr)
            sys.exit(2)
        tscore = next(sc for sc, s in scored if s["id"] == target["id"])
    else:
        target = ranked[0][1]
        tscore = ranked[0][0]

    missing = [d for d in tscore["dims"] if not d["hit"]]
    covered = [d for d in tscore["dims"] if d["hit"]]

    result = {
        "input_length": len(raw),
        "target": {"code": target["code"], "name": target["name"], "name_en": target["name_en"],
                   "score": round(tscore["score"], 2), "hits": tscore["hits"]},
        "candidates": [{"code": s["code"], "name": s["name"], "score": round(sc["score"], 2)}
                       for sc, s in ranked],
        "covered": covered,
        "missing": missing,
        "completion": None,
    }
    if args.fix:
        body = "，".join(d["text"] for d in tscore["dims"])
        result["completion"] = f"{raw.rstrip('。，,')}，{body}"

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return

    print(f"【最接近】{target['code']} {target['name']} / {target['name_en']}　得分 {tscore['score']:.1f}")
    print(f"【凭据】{'、'.join(tscore['hits']) if tscore['hits'] else '无'}")
    print(f"\n【维度覆盖】{len(covered)} / {len(tscore['dims'])}")
    for d in tscore["dims"]:
        mark = "✓" if d["hit"] else "✗"
        note = d["text"] if d["hit"] else f"缺 → 可补「{d['text']}」"
        print(f"  {mark} {d['dim_cn']:<4} {note}")
    if len(ranked) > 1:
        others = "　".join(f"{s['code']} {s['name']} {sc['score']:.1f}" for sc, s in ranked[1:])
        print(f"\n【其它候选】{others}")
    if missing:
        print("\n【建议】")
        for d in missing:
            print(f"  - 补{d['dim_cn']}：{d['text']}")
        print("  - 只补你真需要的一两段。补满会盖掉你原本的表达，变成这条风格的复制品")
    print("\n注意：以上为字面特征匹配，措辞差异大时排序可能不准，请结合候选列表人工判断。")
    if result["completion"]:
        print("\n【补全结果】")
        print(result["completion"])


if __name__ == "__main__":
    main()
