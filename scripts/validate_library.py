#!/usr/bin/env python3
"""风格库体检：结构完整性、字段缺失、编号连续性、模板一致性、标记覆盖。

用法：python3 scripts/validate_library.py
退出码：0 全部通过 / 1 存在错误
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
import model_registry as mr
import name_guard as ng

DATA = ROOT / "assets" / "styles-173.json"
MEDIA = {"photo", "painting", "print", "illustration", "animation", "digital",
         "3d", "graphic", "cgi", "mixed", "tone"}

# references 单层、份数固定：新增文档要同时改这里，防止悄悄多出一份没人维护的说明
EXPECTED_REFERENCE_FILES = 15
# style-anchors.md 只收「173 库未覆盖」的参照，条数固定，库里已有的必须改成序号跳转
EXPECTED_ANCHOR_ROWS = 24

# 姓名扫描的豁免规则分两类，写死、不扩面、不用通配：
#   ① 文档豁免只有一个：references/taxonomy.md（10 大类总表）。它是**目录**，条目名是它的内容；
#      「索引表允许出现条目名；提示词正文与模板不允许」——正文类文档一处都不许有。
#   ② 数据豁免只给三个「以条目名/别名为值」的 JSON，它们存的就是标识符本身；
#      把这三个也扫，等于要求数据文件不能记录自己的条目名。
# 其余 references/*.md、SKILL.md、README.md 与 assets 下其它 JSON 一律零容忍。
NAME_SCAN_SKIP_DOCS = {"references/taxonomy.md"}
NAME_SCAN_SKIP_DATA = {
    "assets/living-names.json",     # 判据表自身
    "assets/styles-173.json",       # 条目 name / aliases 是标识符
    "assets/reference-map.json",    # 编号 → 图片映射，同名标识
}
NAME_SCAN_SKIP = NAME_SCAN_SKIP_DOCS | NAME_SCAN_SKIP_DATA

errors: list[str] = []
warns: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def guarded_style_ids(styles: list[dict]) -> set[int]:
    """净化名单里在册的人，落在库内哪些条目上（按条目名或别名匹配）。

    这是「库内 living_artist 该有哪几条」的唯一判据：名单是权威，标记跟着名单走，
    不再维护一份手写 id 集合，避免名单加了人而标记忘了补。
    """
    keys = {(e.get("zh") or "").strip() for e in ng.names()} | \
           {(e.get("name") or "").strip() for e in ng.names()}
    keys = {k for k in keys if k}
    out = set()
    for s in styles:
        blob = [s.get("name", ""), s.get("name_en", "")] + list(s.get("aliases") or [])
        if any(k in b for k in keys for b in blob):
            out.add(s["id"])
    return out


def by_id_for(styles: list[dict], ids) -> list[str]:
    m = {s["id"]: f"{s['id']} {s.get('name', '?')}" for s in styles}
    return [m.get(i, str(i)) for i in sorted(ids)]


def anchor_rows(text: str) -> list[str]:
    """取「参照」表的首列（参照名），跳过表头、分隔行与文件里的其他表（如禁忌表）。"""
    out: list[str] = []
    header: list[str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            header = None                      # 离开表格，下一张表重新认表头
            continue
        cells = [c.strip().replace("`", "").replace("**", "") for c in line.strip("|").split("|")]
        if header is None:
            header = cells                      # 表格第一行即表头
            continue
        if not cells or set("".join(cells)) <= set("-: "):
            continue                            # 分隔行
        if header[0] != "参照" or not cells[0]:
            continue
        out.append(cells[0])
    return out


def main() -> None:
    if not DATA.exists():
        print(f"[FAIL] 数据文件不存在：{DATA}")
        sys.exit(1)
    db = json.loads(DATA.read_text(encoding="utf-8"))
    styles = db["styles"]

    # 1 数量与编号
    if len(styles) != 173:
        err(f"条目数为 {len(styles)}，应为 173")
    ids = [s["id"] for s in styles]
    if ids != list(range(1, 174)):
        err("编号不连续或重复")
    codes = Counter(s["code"] for s in styles)
    dup_code = [c for c, n in codes.items() if n > 1]
    if dup_code:
        err(f"风格代码重复：{dup_code}")

    # 2 分类数量
    cat_count = Counter(s["category"] for s in styles)
    for c in db["categories"]:
        if cat_count[c["code"]] != c["count"]:
            err(f"分类 {c['code']} 声明 {c['count']} 条，实际 {cat_count[c['code']]} 条")

    for s in styles:
        tag = f"#{s['id']} {s.get('name', '?')}"
        for field in ("name", "name_en", "template", "segments", "category", "medium"):
            if not s.get(field):
                err(f"{tag} 字段 {field} 为空")
        if s.get("medium") not in MEDIA:
            err(f"{tag} medium 取值非法：{s.get('medium')}")
        if not s["template"].startswith("【画面主体】，"):
            err(f"{tag} 模板未以「【画面主体】，」开头")
        joined = "【画面主体】，" + "，".join(x["text"] for x in s["segments"])
        if joined != s["template"]:
            err(f"{tag} segments 与 template 不一致")
        if any(x["dim"] not in {"style", "color", "composition", "texture",
                                "light", "quality", "mood"} for x in s["segments"]):
            err(f"{tag} 存在未知维度")
        if not re.search(r"[\u4e00-\u9fa5]", s["name"]):
            warn = f"{tag} 名称不含中文，检查是否录入错误"
            warns.append(warn)

    # 3 重名与别名冲突
    names = Counter(s["name"] for s in styles)
    for n, c in names.items():
        if c > 1:
            err(f"风格名称重复：{n} ×{c}")
    ens = Counter(s["name_en"] for s in styles)
    for n, c in ens.items():
        if c > 1:
            warns.append(f"英文名重复：{n} ×{c}")
    alias_map: dict[str, list[int]] = {}
    for s in styles:
        for a in s["aliases"]:
            alias_map.setdefault(a, []).append(s["id"])
    for a, owner in alias_map.items():
        if len(owner) > 1:
            err(f"别名「{a}」被多条占用：{owner}")

    # 4 近邻双向性
    by_id = {s["id"]: s for s in styles}
    for s in styles:
        for other in s["flags"]["related"]:
            if other not in by_id:
                err(f"#{s['id']} 的近邻 {other} 不存在")
            elif s["id"] not in by_id[other]["flags"]["related"]:
                warns.append(f"近邻不对称：#{other} 未回指 #{s['id']}")

    # 5 特征词覆盖（少量缺失可接受，超过阈值才报）
    no_kw = sum(1 for s in styles for seg in s["segments"] if not seg.get("kw"))
    if no_kw > 30:
        warns.append(f"有 {no_kw} 个维度段没有特征词，反向解析会漏判")

    # 6 标记覆盖
    broad = sum(1 for s in styles if s["flags"]["broad"])
    living_ids = {s["id"] for s in styles if s["flags"]["living_artist"]}
    living = len(living_ids)
    if broad < 10:
        warns.append(f"宽泛条目标记仅 {broad} 条，检索降权可能不足")
    # 不写裸数字：库内标记必须与净化名单里「确实出现在库条目名/别名中」的人一一对应，
    # 漏标（名单里有、库内没标）与多标（库内标了、名单没有）都算错。
    want_ids = guarded_style_ids(styles)
    if living_ids != want_ids:
        missing = sorted(want_ids - living_ids)
        extra = sorted(living_ids - want_ids)
        if missing:
            err(f"以下条目在 assets/living-names.json 里在册，却未标 living_artist：{missing}"
                f"（{'、'.join(by_id_for(styles, missing))}）")
        if extra:
            err(f"以下条目标了 living_artist，但净化名单里没有对应姓名：{extra}"
                f"（{'、'.join(by_id_for(styles, extra))}）")

    # 7 模型档案（与风格库同等重要：模型写错，语法全错）
    try:
        merrs = mr.validate(verbose=False)
    except SystemExit as exc:
        merrs = [f"模型档案无法加载：{exc}"]
    errors.extend(f"模型档案 → {e}" for e in merrs)

    # 7.1 预算字段：每条模型都要有 budget，且与 syntax 不冲突（mr.validate 已判，这里只复核完备性）
    no_budget = [m.get("id", "?") for m in mr.models() if not m.get("budget")]
    if no_budget:
        err(f"以下模型缺 budget：{no_budget}（长度上限的唯一出处，不许留空）")
    for m in mr.models():
        b = m.get("budget") or {}
        if b and m.get("renderer") in ("prose", "cn_structured") and b.get("enforce") == "none":
            err(f"{m['id']} 是 {m['renderer']} 渲染器却把 enforce 设为 none，等于不查长度")

    # 7.2 references 单层且份数固定
    refdir = ROOT / "references"
    if not refdir.exists():
        err("references 目录不存在")
    else:
        subdirs = [p.name for p in refdir.iterdir() if p.is_dir()]
        if subdirs:
            err(f"references 必须单层，发现子目录：{subdirs}")
        docs = sorted(p for p in refdir.glob("*.md"))
        others = sorted(p.name for p in refdir.iterdir()
                        if p.is_file() and p.suffix != ".md")
        if others:
            err(f"references 里混进了非 .md 文件：{others}")
        if len(docs) != EXPECTED_REFERENCE_FILES:
            err(f"references 为 {len(docs)} 份，应为 {EXPECTED_REFERENCE_FILES} 份"
                f"（改份数请同步改 validate_library.EXPECTED_REFERENCE_FILES）")
        empty = [p.name for p in docs if len(p.read_text(encoding="utf-8").strip()) < 200]
        if empty:
            err(f"以下 references 内容过短，疑似占位：{empty}")

    # 7.3 净化名单：写指令的文档里不得出现任何在册姓名
    scanned = list(refdir.glob("*.md")) if refdir.exists() else []
    scanned += sorted((ROOT / "assets").glob("*.json"))
    scanned += [ROOT / "SKILL.md", ROOT / "README.md"]
    for fp in scanned:
        rel = fp.relative_to(ROOT).as_posix()
        if rel in NAME_SCAN_SKIP or not fp.exists():
            continue
        for h in ng.hits(fp.read_text(encoding="utf-8")):
            err(f"{rel} 出现在册姓名「{h['zh'] or h['name']}」→ 改写为：{h['features'][:40]}…（判据见 assets/living-names.json）")

    # 7.4 库外参照不得与 173 库重名：重名说明这条本来就已经覆盖，应改成序号跳转
    anchors = ROOT / "references" / "style-anchors.md"
    if not anchors.exists():
        err("references/style-anchors.md 不存在（库外参照表）")
    else:
        rows = anchor_rows(anchors.read_text(encoding="utf-8"))
        if len(rows) != EXPECTED_ANCHOR_ROWS:
            err(f"style-anchors.md 参照行为 {len(rows)} 条，应为 {EXPECTED_ANCHOR_ROWS} 条"
                f"（只收库未覆盖的；改条数请同步改 EXPECTED_ANCHOR_ROWS）")
        code_of = {s["name"]: s["code"] for s in styles}
        dup = [f"{r}（库内 {code_of[r]}）" for r in rows if r in code_of]
        if dup:
            err(f"style-anchors.md 与 173 库重名：{dup} → 改为序号跳转，不要重复收录")
        same = [f"{r}（库内存在同名英文条目）" for r in rows
                if r in {s["name_en"] for s in styles}]
        if same:
            err(f"style-anchors.md 与 173 库英文名重名：{same} → 改为序号跳转")

    # 8 参考图数据集（存在则校验，缺失只提醒不报错）
    man = ROOT / "assets" / "dataset" / "manifest.jsonl"
    if man.exists():
        recs = [json.loads(x) for x in man.read_text(encoding="utf-8").splitlines() if x.strip()]
        if len(recs) != len(styles):
            warns.append(f"数据集 {len(recs)} 条，与风格 {len(styles)} 条不一致")
        miss = [r["id"] for r in recs if not (ROOT / r["image"]).exists()]
        if miss:
            err(f"数据集缺图：{miss[:6]}{'…' if len(miss) > 6 else ''}")
        no_src = [r["id"] for r in recs if not r.get("source")]
        if no_src:
            warns.append(f"{len(no_src)} 条缺少原图出处，无法回溯")
    else:
        warns.append("数据集未构建：跑 scripts/build_dataset.py，否则画廊无图")

    # 9 署名一致性（单一数据源 author.json）
    ap = ROOT / "assets" / "author.json"
    if not ap.exists():
        err("缺少 assets/author.json，署名无法统一维护")
    else:
        auth = json.loads(ap.read_text(encoding="utf-8"))
        sig, acc = auth.get("signature", ""), auth.get("account", "")
        if not sig or not acc:
            err("author.json 缺 signature 或 account")
        for f in ("SKILL.md", "README.md", "assets/gallery.html"):
            fp = ROOT / f
            if not fp.exists():
                warns.append(f"{f} 不存在，跳过署名检查")
                continue
            body = fp.read_text(encoding="utf-8")
            if sig not in body:
                err(f"{f} 未包含完整署名「{sig}」")
            elif acc not in body:
                err(f"{f} 未包含账号「{acc}」")

    # 10 排版图型与主题色
    lp, cp = ROOT / "assets" / "layouts.json", ROOT / "assets" / "colors.json"
    if not lp.exists() or not cp.exists():
        err("缺少 layouts.json 或 colors.json")
    else:
        L = json.loads(lp.read_text(encoding="utf-8"))
        C = json.loads(cp.read_text(encoding="utf-8"))
        lids = [x["id"] for x in L["layouts"]]
        if len(lids) != len(set(lids)):
            err("排版图型编号重复")
        fams = {f["code"] for f in L["families"]}
        for x in L["layouts"]:
            if x["family"] not in fams:
                err(f"{x['id']} 的家族 {x['family']} 未登记")
            if not x.get("prompt_zh") or not x.get("prompt_en"):
                err(f"{x['id']} 缺少中英指令")
        for k, ids in L.get("scene_map", {}).items():
            for i in ids:
                if i not in lids:
                    err(f"scene_map「{k}」指向不存在的图型 {i}")
        if len(lids) < 40:
            warns.append(f"排版图型仅 {len(lids)} 个，覆盖可能不足")
        cids = [c["id"] for c in C["colors"]]
        if len(cids) != len(set(cids)):
            err("主题色编号重复")
        for c in C["colors"]:
            if not re.match(r"^#[0-9A-Fa-f]{6}$", c["hex"]):
                err(f"{c['id']} 色值格式非法：{c['hex']}")

    # 打分
    score = max(0, 100 - len(errors) * 8 - min(len(warns), 10) * 1)
    print(f"条目 {len(styles)} / 分类 {len(db['categories'])} / 宽泛标记 {broad} / 在世艺术家 {living}")
    print(f"模型档案 {len(mr.models())} 个 / 采集槽位 {len(mr.load()['intake_slots'])} 个"
          f" / 带预算 {len(mr.models()) - len(no_budget)} 条")
    print(f"references {len(list(refdir.glob('*.md'))) if refdir.exists() else 0} 份（单层）"
          f" / 净化名单 {len(ng.names())} 人")
    print(f"错误 {len(errors)} / 警告 {len(warns)} / 得分 {score}")
    for e in errors[:20]:
        print(f"  [ERR] {e}")
    for w in warns[:10]:
        print(f"  [WARN] {w}")
    if score >= 90 and not errors:
        print("结论：通过")
        sys.exit(0)
    print("结论：不通过")
    sys.exit(1)


if __name__ == "__main__":
    main()
