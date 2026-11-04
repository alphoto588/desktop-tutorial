#!/usr/bin/env python3
"""批量生成同风格提示词，并输出一致性证据。

一套图最怕的是"每张都差一点"。本脚本锁定风格与平台，逐条换主体，最后给出
风格段哈希与体检分布——让"一致"这件事可验证，而不是靠肉眼。

用法：
    python3 scripts/batch_prompt.py --style CN-01 --subjects subjects.txt
    python3 scripts/batch_prompt.py --style CN-01,CO-07 --dims color \
        --platform mj --aspect 3:4 --subjects subjects.txt --out batch.md
    printf '一只茶壶\\n两只茶盏\\n' | python3 scripts/batch_prompt.py --style CN-01 --stdin

退出码：0 全部合格 / 1 有主体不合格 / 2 参数错误
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bp", HERE / "build_prompt.py")
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)


def read_subjects(args) -> list[str]:
    if args.stdin:
        raw = sys.stdin.read()
    else:
        raw = Path(args.subjects).read_text(encoding="utf-8")
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description="批量同风格提示词")
    ap.add_argument("--style", required=True, help="风格，逗号分隔，首个为主风格")
    ap.add_argument("--subjects", help="主体清单文件，每行一条")
    ap.add_argument("--stdin", action="store_true", help="从标准输入读主体")
    ap.add_argument("--dims", help="副风格覆盖维度，默认 color,light")
    ap.add_argument("--aspect", default="", help="画面比例")
    ap.add_argument("--platform", "--model", dest="platform", default="generic",
                    choices=sorted(bp.PLATFORMS), help="目标模型，语法按 assets/models.json 适配")
    ap.add_argument("--negative", default="", help="追加负向词")
    ap.add_argument("--out", help="输出 Markdown 到文件")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if not args.subjects and not args.stdin:
        print("需要 --subjects 文件或 --stdin", file=sys.stderr)
        sys.exit(2)

    db = bp.load()
    styles = db["styles"]
    tokens = [t for t in args.style.replace("，", ",").split(",") if t.strip()]
    picks, missing = [], []
    for t in tokens:
        hit = bp.resolve(t, styles)
        (picks.append(hit) if hit else missing.append(t.strip()))
    if missing:
        print(f"未找到风格：{'、'.join(missing)}", file=sys.stderr)
        sys.exit(2)
    if len(picks) > 3:
        print("最多 3 个风格", file=sys.stderr)
        sys.exit(2)

    dims = [d.strip() for d in (args.dims or "color,light").replace("，", ",").split(",") if d.strip()]
    subjects = read_subjects(args)
    if not subjects:
        print("主体清单为空", file=sys.stderr)
        sys.exit(2)

    base_conf = []
    for i in range(len(picks)):
        for j in range(i + 1, len(picks)):
            base_conf.extend(bp.conflicts(picks[i], picks[j]))

    rows, hashes, scores = [], set(), []
    for idx, subject in enumerate(subjects, 1):
        segs, notes = bp.build(subject, picks, dims)
        chk = bp.check_subject(subject, styles)
        negative = args.negative            # 模型自带的负向默认值由渲染层补，不在这里叠加
        prompt, neg_out, params = bp.render(args.platform, args.aspect, subject, segs, negative)
        style_part = "，".join(s["text"] for s in segs)
        h = hashlib.md5(style_part.encode()).hexdigest()[:8]
        hashes.add(h)
        scores.append(chk["score"])
        rows.append({
            "index": idx, "subject": subject, "prompt": prompt, "negative": neg_out,
            "params": params, "style_hash": h, "subject_score": chk["score"],
            "subject_issues": [i["tag"] for i in chk["issues"]], "notes": notes,
        })

    consistent = len(hashes) == 1
    bad = [r for r in rows if r["subject_score"] < 85 or r["subject_issues"]]
    summary = {
        "style": [{"code": p["code"], "name": p["name"]} for p in picks],
        "platform": bp.PLATFORMS[args.platform]["label"],
        "aspect": args.aspect,
        "count": len(rows),
        "style_consistent": consistent,
        "style_hashes": sorted(hashes),
        "avg_subject_score": round(sum(scores) / len(scores), 1),
        "bad_subjects": [{"index": r["index"], "subject": r["subject"], "issues": r["subject_issues"]} for r in bad],
        "conflicts": base_conf,
    }

    if args.json:
        print(json.dumps({"summary": summary, "items": rows}, ensure_ascii=False, indent=1))
        sys.exit(1 if bad else 0)

    out = []
    out.append(f"# 批量提示词 · {' + '.join(p['name'] for p in picks)}")
    out.append("")
    out.append(f"- 平台：{bp.PLATFORMS[args.platform]['label']}　比例：{args.aspect or '未指定'}")
    out.append(f"- 条数：{len(rows)}　风格段哈希：{' / '.join(sorted(hashes))}")
    out.append(f"- 一致性：{'通过（全部条目风格段完全相同）' if consistent else '不一致，请检查'}")
    out.append(f"- 主体体检均分：{summary['avg_subject_score']}")
    if bad:
        out.append("- 待改主体：" + "、".join("#%d" % r["index"] for r in bad))
    if base_conf:
        out.append(f"- 风格冲突：{len(base_conf)} 项（详见 build_prompt.py 单条输出）")
    out.append("")
    for r in rows:
        out.append(f"## {r['index']:02d}　{r['subject']}")
        out.append("")
        out.append(f"```text\n{r['prompt']}\n```")
        if r["negative"]:
            out.append(f"负向：`{r['negative']}`")
        if r["params"]:
            out.append(f"参数：`{r['params']}`")
        if r["subject_issues"]:
            out.append(f"> 主体待改：{'、'.join(r['subject_issues'])}")
        out.append("")
    text = "\n".join(out)

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"已写入 {args.out}（{len(rows)} 条，一致性{'通过' if consistent else '不通过'}）")
    else:
        print(text)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
