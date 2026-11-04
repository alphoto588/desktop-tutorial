#!/usr/bin/env python3
"""把署名信息统一写入各文档，并检查是否走样。

单一数据源是 assets/author.json。文档里只放一对标记，标记之间的内容由本脚本生成：

    <!-- AUTHOR:BEGIN -->
    ...（脚本生成，勿手改）...
    <!-- AUTHOR:END -->

这样改公众号名只需改 author.json 再跑一次，不会出现「SKILL 改了 README 没改」。

用法：
    python3 scripts/stamp_author.py --check     # 只检查，CI 用
    python3 scripts/stamp_author.py --fix       # 重写标记块
退出码：0 一致 / 1 不一致或缺标记 / 2 数据文件缺失
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "author.json"
TARGETS = [ROOT / "SKILL.md", ROOT / "README.md"]
BEGIN, END = "<!-- AUTHOR:BEGIN -->", "<!-- AUTHOR:END -->"


def load() -> dict:
    if not DATA.exists():
        print(f"缺少 {DATA}", file=sys.stderr)
        sys.exit(2)
    return json.loads(DATA.read_text(encoding="utf-8"))


def block(a: dict, heading: str = "## 关于作者") -> str:
    return "\n".join([
        BEGIN,
        "",
        heading,
        "",
        f"- **作者**：{a['name']}",
        f"- {a['signature']}",
        f"- **许可**：{a['license']}",
        f"- **版权**：{a['copyright']}，保留所有权利",
        "",
        "> 转载、二次分发或商用，请保留上述署名与联系方式。",
        "",
        END,
    ])


def replace_block(text: str, new: str) -> tuple[str, bool]:
    if BEGIN in text and END in text:
        pat = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
        return pat.sub(new, text, count=1), True
    return text, False


def main() -> None:
    ap = argparse.ArgumentParser(description="署名块同步与检查")
    ap.add_argument("--check", action="store_true", help="只检查")
    ap.add_argument("--fix", action="store_true", help="写入标记块")
    args = ap.parse_args()
    auth = load()
    want = block(auth)

    problems = []
    for path in TARGETS:
        if not path.exists():
            problems.append(f"{path.name} 不存在")
            continue
        text = path.read_text(encoding="utf-8")
        if BEGIN not in text or END not in text:
            problems.append(f"{path.name} 缺 AUTHOR 标记块")
            continue
        new_text, _ = replace_block(text, want)
        if auth["signature"] not in new_text:
            problems.append(f"{path.name} 未包含署名串「{auth['signature']}」")
        if auth["account"] not in new_text:
            problems.append(f"{path.name} 未包含账号「{auth['account']}」")
        if args.fix and new_text != text:
            path.write_text(new_text, encoding="utf-8")
            print(f"已更新 {path.name}")

    if problems:
        print("署名检查未通过：")
        for x in problems:
            print(f"  [ERR] {x}")
        sys.exit(1)
    print(f"署名一致：{auth['signature']} · 检查 {len(TARGETS)} 个文件")


if __name__ == "__main__":
    main()
