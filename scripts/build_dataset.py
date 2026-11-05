#!/usr/bin/env python3
"""把散落在分类目录里的 173 张风格参考图，整理成可被脚本与画廊直接消费的数据集。

产物（全部落在 assets/dataset/）：
    images/{bucket}/{id}.webp     缩略图，按 100 张分桶（001-100 / 101-200）
    _grid/{code}.webp             每个大类的拼版大图，快速扫一眼用
    manifest.jsonl                一行一条：编号、名称、七维特征、模板、图片路径、校验值
    README.md                     字段说明与扩充方法

另有 assets/reference-map.json，给生成流程用：编号 → 参考图路径 + 哈希。

为什么不直接引用原图：原图 51 MB 且散在技能目录之外，打包或换机就断链。
缩略图让技能自包含，原图路径仍记录在 manifest 的 source 字段里，可回溯。

用法：
    python3 scripts/build_dataset.py                     # 自动定位工作区
    python3 scripts/build_dataset.py --source /path/to/images   # 手动指定
    python3 scripts/build_dataset.py --max 640 --quality 78
退出码：0 成功 / 1 有图片缺失 / 2 参数或依赖问题
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "styles-173.json"
OUT = ROOT / "assets" / "dataset"
REFMAP = ROOT / "assets" / "reference-map.json"

BUCKET = 100
TILE = 220
COLS = 6


def bucket_name(sid: int) -> str:
    lo = (sid - 1) // BUCKET * BUCKET + 1
    return f"{lo:03d}-{lo + BUCKET - 1:03d}"


def find_source_dir() -> Path | None:
    """向上查找含有风格分类文件夹的目录，不假设任何客户端目录结构。"""
    cur = ROOT
    for _ in range(6):
        cur = cur.parent
        if cur.parent == cur:
            break
        try:
            named = [c for c in cur.iterdir()
                     if c.is_dir() and re.match(r"^[一二三四五六七八九十]、", c.name)]
        except OSError:
            continue
        if len(named) >= 3:
            return cur
    return None


def scan_images(src: Path) -> dict[int, Path]:
    found: dict[int, Path] = {}
    for d in sorted(src.iterdir()):
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            m = re.match(r"^(\d+)\.\s*.+\.(jpg|jpeg|png|webp)$", f.name, re.I)
            if m:
                found[int(m.group(1))] = f
    return found


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def main() -> None:
    ap = argparse.ArgumentParser(description="构建风格参考图数据集")
    ap.add_argument("--source", help="原始图片所在目录（含 10 个分类文件夹）")
    ap.add_argument("--max", type=int, default=480, help="缩略图最长边，默认 480")
    ap.add_argument("--quality", type=int, default=72, help="webp 质量，默认 72")
    a = ap.parse_args()

    try:
        from PIL import Image
    except ImportError:
        print("需要 Pillow：pip install pillow", file=sys.stderr)
        sys.exit(2)

    db = json.loads(DATA.read_text(encoding="utf-8"))
    styles = {s["id"]: s for s in db["styles"]}

    src = Path(a.source) if a.source else find_source_dir()
    if not src or not src.is_dir():
        print("找不到原图目录，请用 --source 指定", file=sys.stderr)
        sys.exit(2)
    found = scan_images(src)
    print(f"原图目录：{src}\n扫描到 {len(found)} 张，样式表 {len(styles)} 条")

    (OUT / "images").mkdir(parents=True, exist_ok=True)
    (OUT / "grid").mkdir(parents=True, exist_ok=True)

    manifest, refmap, missing = [], {}, []
    by_cat: dict[str, list[Path]] = {}

    for sid in sorted(styles):
        s = styles[sid]
        src_img = found.get(sid)
        if not src_img:
            missing.append(sid)
            continue
        b = OUT / "images" / bucket_name(sid)
        b.mkdir(parents=True, exist_ok=True)
        dst = b / f"{sid:03d}.webp"
        if not dst.exists() or dst.stat().st_mtime < src_img.stat().st_mtime:
            with Image.open(src_img) as im:
                im = im.convert("RGB")
                im.thumbnail((a.max, a.max), Image.LANCZOS)
                im.save(dst, "WEBP", quality=a.quality, method=6)
        with Image.open(dst) as im:
            w, h = im.size
        rel = dst.relative_to(ROOT).as_posix()
        digest = sha1(dst)
        by_cat.setdefault(s["category"], []).append(dst)

        rec = {
            "id": sid, "code": s["code"], "name": s["name"], "name_en": s["name_en"],
            "category": s["category"], "category_name": s["category_name"],
            "medium": s["medium"], "traits": [g["text"] for g in s["segments"]],
            "template": s["template"], "image": rel, "source": src_img.relative_to(src).as_posix(),
            "sha1": digest, "bytes": dst.stat().st_size, "width": w, "height": h,
        }
        manifest.append(rec)
        refmap[str(sid)] = {"code": s["code"], "name": s["name"], "image": rel,
                            "sha1": digest, "source": rec["source"]}

    # 每类一张拼版图，便于快速扫
    for code, files in by_cat.items():
        rows = (len(files) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * TILE, rows * TILE), "#ffffff")
        for i, f in enumerate(files):
            with Image.open(f) as im:
                im = im.convert("RGB")
                im.thumbnail((TILE - 12, TILE - 12), Image.LANCZOS)
                x = (i % COLS) * TILE + (TILE - im.width) // 2
                y = (i // COLS) * TILE + (TILE - im.height) // 2
                sheet.paste(im, (x, y))
        sheet.save(OUT / "grid" / f"{code}.webp", "WEBP", quality=70, method=6)

    with (OUT / "manifest.jsonl").open("w", encoding="utf-8") as fh:
        for rec in manifest:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    REFMAP.write_text(json.dumps({"version": 1, "count": len(refmap), "by_id": refmap},
                                 ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    total = sum(r["bytes"] for r in manifest)
    print(f"缩略图 {len(manifest)} 张 / {total/1024/1024:.1f} MB　拼版 {len(by_cat)} 张")
    print(f"清单 {OUT/'manifest.jsonl'}　映射 {REFMAP.relative_to(ROOT)}")
    if missing:
        print(f"[!] 缺图编号：{missing}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
