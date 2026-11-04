#!/usr/bin/env python3
"""净化名单的唯一读写入口：加载 assets/living-names.json，扫描文本里是否出现姓名。

名单口径（保守单向阀）：在世 + 去世未满 50 年 + 生卒信息不明，一律按在世处理。
判据与可观察特征都写在 JSON 里，脚本不内置第二份名单——要改判据只改 JSON。

用法（作为库）：
    import name_guard as ng
    ng.load()                     # → {"version", "policy", "note", "names": [...]}
    ng.hits("画面用霓虹绿与暗红对撞的窄巷")   # → [{"name": ..., "zh": ..., "kind": ..., "features": ...}]

命令行自检：
    python3 scripts/name_guard.py --list
    python3 scripts/name_guard.py --text "用 Annie Leibovitz 的硬光"
退出码：0 无命中 / 1 命中（或参数错误以外的异常）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "living-names.json"
_CACHE: dict | None = None


def load() -> dict:
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.loads(DATA.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise SystemExit(f"净化名单缺失：{DATA}")
        except json.JSONDecodeError as exc:
            raise SystemExit(f"净化名单损坏：{exc}")
    return _CACHE


def names() -> list[dict]:
    return load().get("names", [])


def _patterns(entry: dict) -> list[re.Pattern]:
    """一个条目的所有匹配式：中文按子串，英文按词边界（避免 fan ho 命中 fan hold）。"""
    out = []
    zh = (entry.get("zh") or "").strip()
    en = (entry.get("name") or "").strip()
    if zh:
        out.append(re.compile(re.escape(zh)))
    if en:
        out.append(re.compile(r"\b" + r"\s*".join(re.escape(w) for w in en.split()) + r"\b",
                              re.IGNORECASE))
    return out


def hits(text: str) -> list[dict]:
    """返回文本命中的姓名条目（同一人只报一次，附命中片段）。"""
    found: list[dict] = []
    if not text:
        return found
    for entry in names():
        snippet = ""
        for pat in _patterns(entry):
            m = pat.search(text)
            if m:
                snippet = text[max(0, m.start() - 12): m.end() + 12].replace("\n", " ").strip()
                break
        if snippet:
            found.append({"name": entry.get("name", ""), "zh": entry.get("zh", ""),
                          "kind": entry.get("kind", ""), "features": entry.get("features", ""),
                          "snippet": snippet})
    return found


def describe(entry: dict) -> str:
    """把姓名条目转成一句可直接写进提示词的特征描述。"""
    return entry.get("features", "")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="净化名单自检")
    ap.add_argument("--list", action="store_true", help="列出全部姓名与特征")
    ap.add_argument("--text", help="扫描一段文本")
    a = ap.parse_args()
    if a.list:
        for i, e in enumerate(names(), 1):
            print(f"{i:>3} {e.get('zh','')} / {e.get('name','')} [{e.get('kind','')}]")
            print(f"     → {e.get('features','')}")
        print(f"共 {len(names())} 条；口径：{load().get('policy','')}")
        return
    if a.text is None:
        print("用法：--list 或 --text <文本>", file=sys.stderr)
        sys.exit(2)
    hit = hits(a.text)
    if not hit:
        print("未命中姓名")
        return
    for h in hit:
        print(f"[HIT] {h['zh']} / {h['name']}（{h['kind']}）：{h['snippet']}")
        print(f"      改写为：{h['features']}")
    sys.exit(1)


if __name__ == "__main__":
    main()
