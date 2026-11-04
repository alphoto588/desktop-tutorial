#!/usr/bin/env python3
"""从原始 Markdown 重建 assets/styles-173.json。

源文档：视觉美学风格提示词库（173 种，10 类）
本脚本是开发工具，仅在源文档更新后运行；技能运行时只读 assets/styles-173.json。

用法：
    python3 scripts/rebuild_library.py --source <源md路径>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "styles-173.json"

CATEGORIES = [
    ("CN", "中国古典、文人美学与东方幻想", 1, 37),
    ("JP", "日本与东亚近现代美学", 38, 49),
    ("WR", "世界区域美学", 50, 61),
    ("WE", "西方艺术流派", 62, 89),
    ("DG", "数字、科幻与现代设计", 90, 108),
    ("PH", "摄影与光影", 109, 119),
    ("IL", "插画、动画与绘本", 120, 138),
    ("CO", "色彩与调性", 139, 151),
    ("SB", "亚文化与暗黑美学", 152, 154),
    ("EX", "补充篇：题材与画家", 155, 173),
]

# id -> (英文名, 别名列表)
META = {
    1: ("Song Dynasty Aesthetics", ["宋代美学", "宋式"]),
    2: ("High Tang Grandeur", ["盛唐"]),
    3: ("Ming Dynasty Aesthetics", ["明代美学"]),
    4: ("Wei-Jin Scholar Elegance", ["魏晋"]),
    5: ("New Chinese Style", ["新中式风格"]),
    6: ("Neo-Chinese Chic", ["新国风设计"]),
    7: ("Eastern Zen", ["禅意", "禅意风"]),
    8: ("Wabi-Sabi", ["侘寂", "诧寂", "wabi-sabi"]),
    9: ("Mono no Aware", ["物哀美学", "mono no aware"]),
    10: ("Yugen", ["幽玄美学", "yugen"]),
    11: ("Negative Space", ["空白", "negative space"]),
    12: ("Ink Wash", ["水墨", "水墨画", "ink wash"]),
    13: ("Xieyi Freehand Brushwork", ["写意画", "大写意"]),
    14: ("Gongbi Fine Brushwork", ["工笔", "工笔重彩"]),
    15: ("Baimiao Line Drawing", ["线描", "白描画"]),
    16: ("Blue-Green Landscape", ["青绿山水画"]),
    17: ("Gold-and-Blue Landscape", ["金碧山水画"]),
    18: ("Dunhuang Murals", ["敦煌", "敦煌壁画风"]),
    19: ("Dunhuang Aesthetics", ["敦煌风"]),
    20: ("Thangka", ["唐卡画"]),
    21: ("China Chic", ["国潮风"]),
    22: ("Xianxia Fantasy", ["仙侠", "仙侠剧"]),
    23: ("Wuxia", ["武侠"]),
    24: ("Classic of Mountains and Seas", ["山海经"]),
    25: ("Zhiguai Strange Tales", ["志怪"]),
    26: ("Forbidden City Aesthetics", ["故宫", "紫禁城美学"]),
    27: ("Suzhou Garden", ["苏州园林风", "江南园林"]),
    28: ("Huizhou Architecture", ["徽派", "徽州建筑"]),
    29: ("Literati Painting", ["文人画风"]),
    30: ("Hanfu Style", ["汉服"]),
    31: ("Taoist Naturalness", ["道法自然美学"]),
    32: ("New Year Offering Still Life", ["岁朝清供图"]),
    33: ("Zen Painting", ["禅意画"]),
    34: ("Ink Wash Animation", ["水墨动画片"]),
    35: ("Splashed-Ink Landscape", ["泼墨", "泼墨山水画"]),
    36: ("Xuan Paper Painting", ["宣纸"]),
    37: ("Chinese Style", ["中式", "chinoiserie", "中国风设计"]),
    38: ("Ukiyo-e", ["浮世绘风格", "ukiyo-e"]),
    39: ("Rinpa", ["琳派风格", "尾形光琳"]),
    40: ("Kano School", ["狩野派画派"]),
    41: ("Showa Era Style", ["昭和"]),
    42: ("Showa Retro", ["昭和怀旧"]),
    43: ("Taisho Romanticism", ["大正浪漫风"]),
    44: ("Japanese Style", ["日系", "和风设计"]),
    45: ("Wafu Japanese", ["和风风格", "日式和风"]),
    46: ("Studio Ghibli Style", ["吉卜力", "ghibli"]),
    47: ("Hayao Miyazaki Style", ["宫崎骏", "miyazaki"]),
    48: ("Makoto Shinkai Style", ["新海诚", "shinkai"]),
    49: ("Satoshi Kon Style", ["今敏", "kon"]),
    50: ("Korean Aesthetics", ["韩系", "韩式风格"]),
    51: ("Korean Webtoon", ["韩漫", "webtoon"]),
    52: ("Indian Style", ["印度美学"]),
    53: ("Persian Miniature", ["波斯细密画风"]),
    54: ("Egyptian Art", ["埃及风", "古埃及艺术"]),
    55: ("African Tribal Art", ["非洲艺术", "部落艺术"]),
    56: ("Dia de los Muertos", ["亡灵节", "墨西哥亡灵节"]),
    57: ("Nordic Style", ["北欧风", "nordic"]),
    58: ("Scandinavian Style", ["斯堪的纳维亚", "scandi"]),
    59: ("Slavic Mythology", ["斯拉夫神话"]),
    60: ("American Retro", ["美式复古风", "american retro"]),
    61: ("Bohemian", ["波西米亚", "boho"]),
    62: ("Impressionism", ["印象派风格", "impressionism"]),
    63: ("Post-Impressionism", ["后印象派风格"]),
    64: ("Expressionism", ["表现主义风格"]),
    65: ("Abstract Expressionism", ["抽象表现"]),
    66: ("Surrealism", ["超现实", "surrealism"]),
    67: ("Dadaism", ["达达", "dada"]),
    68: ("Cubism", ["立体派", "cubism"]),
    69: ("Art Nouveau", ["新艺术", "art nouveau"]),
    70: ("Art Deco", ["装饰艺术", "art deco"]),
    71: ("Baroque", ["巴洛克", "baroque"]),
    72: ("Rococo", ["洛可可", "rococo"]),
    73: ("Neoclassicism", ["新古典", "neoclassical"]),
    74: ("Romanticism", ["浪漫派", "romanticism"]),
    75: ("Realism", ["写实主义", "realism"]),
    76: ("Symbolism", ["象征派", "symbolism"]),
    77: ("Pre-Raphaelite", ["拉斐尔前派风格"]),
    78: ("Futurism", ["未来派", "futurism"]),
    79: ("Constructivism", ["构成派", "constructivism"]),
    80: ("Bauhaus", ["包豪斯", "bauhaus"]),
    81: ("Medieval Aesthetics", ["中世纪", "medieval"]),
    82: ("Renaissance", ["文艺复兴", "renaissance"]),
    83: ("Pop Art", ["波普", "pop art"]),
    84: ("Mosaic", ["马赛克拼贴", "mosaic"]),
    85: ("Wood Panel Painting", ["木板油画", "panel painting"]),
    86: ("Copperplate Etching", ["铜版", "etching"]),
    87: ("Lithography", ["石版", "lithograph"]),
    88: ("Oil Painting", ["油画", "oil painting"]),
    89: ("Impasto Oil Texture", ["厚涂油画", "impasto"]),
    90: ("Minimalism", ["极简", "minimalism"]),
    91: ("Maximalism", ["极繁", "maximalism"]),
    92: ("Cyberpunk", ["赛博朋克风", "cyberpunk"]),
    93: ("Vaporwave", ["蒸汽波美学", "vaporwave"]),
    94: ("Y2K Aesthetic", ["千禧年", "Y2K"]),
    95: ("3D Render", ["3D渲染", "三维", "c4d"]),
    96: ("Retro", ["复古风", "retro"]),
    97: ("Faded Retro", ["褪色复古", "faded"]),
    98: ("Wasteland", ["废土", "末日废土", "post-apocalyptic"]),
    99: ("Pixel Art", ["像素", "pixel"]),
    100: ("Low Poly", ["低模", "lowpoly"]),
    101: ("Acid Graphics", ["酸性设计", "acid"]),
    102: ("Steampunk", ["蒸汽朋克风", "steampunk"]),
    103: ("Dieselpunk", ["柴油朋克风", "dieselpunk"]),
    104: ("Solarpunk", ["太阳朋克", "solarpunk"]),
    105: ("Biopunk", ["生物朋克风", "biopunk"]),
    106: ("Glitch Art", ["故障风", "glitch"]),
    107: ("Sci-Fi", ["科幻", "sci-fi", "science fiction"]),
    108: ("Fantasy", ["奇幻", "fantasy"]),
    109: ("Film Photography", ["胶片", "film look"]),
    110: ("Polaroid", ["宝丽来相纸", "polaroid"]),
    111: ("Instax", ["富士拍立得", "instax"]),
    112: ("Kodak Film Look", ["柯达", "kodak"]),
    113: ("Fujifilm Look", ["富士", "fujifilm", "pro 400h"]),
    114: ("Portrait Photography", ["人像", "portrait"]),
    115: ("Fashion Photography", ["时尚大片", "fashion editorial"]),
    116: ("Street Photography", ["街拍", "street"]),
    117: ("Tyndall Effect", ["耶稣光", "god rays", "丁达尔光"]),
    118: ("Shallow Depth of Field", ["大光圈", "浅景深虚化", "bokeh"]),
    119: ("Cinematic", ["电影感风格", "cinematic"]),
    120: ("Anime Style", ["动漫", "anime"]),
    121: ("ACG Style", ["二次元风格", "niji", "acg"]),
    122: ("American Comic", ["美漫", "comic book"]),
    123: ("Pixar Style", ["皮克斯", "pixar"]),
    124: ("Disney Style", ["迪士尼", "disney"]),
    125: ("DreamWorks Style", ["梦工厂", "dreamworks"]),
    126: ("Picture Book", ["绘本", "picturebook"]),
    127: ("Flat Illustration", ["扁平化插画", "flat design"]),
    128: ("Vector Illustration", ["矢量图", "vector"]),
    129: ("Pencil Sketch", ["素描", "sketch"]),
    130: ("Crayon Drawing", ["蜡笔", "crayon"]),
    131: ("Chalk Drawing", ["粉笔", "chalk"]),
    132: ("Cel Animation", ["赛璐璐", "cel"]),
    133: ("Claymation", ["黏土动画", "clay"]),
    134: ("Origami", ["折纸", "origami"]),
    135: ("Watercolor", ["水彩", "watercolour"]),
    136: ("Watercolor Paper Texture", ["水彩纸", "cold press"]),
    137: ("Polka Dot Art", ["波点", "polka dot"]),
    138: ("Yayoi Kusama Style", ["草间弥生", "kusama"]),
    139: ("Morandi Palette", ["莫兰迪", "morandi"]),
    140: ("Macaron Palette", ["马卡龙", "macaron"]),
    141: ("Candy Colors", ["糖果色系"]),
    142: ("Neon Colors", ["霓虹", "neon"]),
    143: ("Fluorescent Colors", ["荧光", "fluorescent"]),
    144: ("High Saturation", ["高饱和", "vivid"]),
    145: ("Desaturated", ["低饱和", "desaturated"]),
    146: ("Muted Grey Tone", ["灰调子", "muted"]),
    147: ("Monochrome", ["单色", "monochromatic"]),
    148: ("Black and White", ["黑白摄影", "b&w", "monochrome photo"]),
    149: ("Warm Tone", ["暖色", "warm"]),
    150: ("Cool Tone", ["冷色", "cool"]),
    151: ("Pastel", ["粉彩色", "pastel"]),
    152: ("Gothic", ["哥特", "gothic"]),
    153: ("Dark Aesthetic", ["暗黑", "dark"]),
    154: ("Lolita Street Culture", ["洛丽塔", "lolita"]),
    155: ("Cinematic Portrait", ["电影剧照", "cinematic portrait"]),
    156: ("Landscape", ["风光", "landscape"]),
    157: ("Figure Statue", ["手办模型", "pvc figure"]),
    158: ("Printmaking", ["版画风", "print"]),
    159: ("Classical Academic", ["古典油画", "academic art"]),
    160: ("Abstract", ["抽象画", "abstract art"]),
    161: ("Fluorescent Painting", ["荧光画"]),
    162: ("Colored Pencil", ["彩铅", "colored pencil"]),
    163: ("Sharp-Line Illustration", ["锐利线条插画"]),
    164: ("Risograph Print", ["Riso", "孔版印刷", "riso"]),
    165: ("CG Animation", ["CG", "三维动画"]),
    166: ("Cartoon", ["卡通画", "cartoon"]),
    167: ("Hong Kong Comic", ["港漫", "港风漫画"]),
    168: ("Retro Anime", ["复古动画", "90s anime"]),
    169: ("Children's Drawing", ["儿童画", "kids drawing"]),
    170: ("Claude Monet", ["莫奈", "monet"]),
    171: ("Pablo Picasso", ["毕加索", "picasso"]),
    172: ("Rembrandt", ["伦勃朗", "rembrandt"]),
    173: ("Henri Matisse", ["马蒂斯", "matisse"]),
}

# 名称过宽、单靠名字锁定不住画风的条目：检索时降权，并要求补充限定
BROAD = {21, 37, 44, 45, 52, 57, 61, 96, 107, 108, 155, 156, 157, 158, 159, 160, 166, 169}
# 在世艺术家：不得直接以人名作为风格指令，须转写为可描述特征
# 在世/保护期内条目的 id（去世未满 50 年按在世处理）：47 宫崎骏、48 新海诚、49 今敏、138 草间弥生
LIVING = {47, 48, 49, 138}
# 语义近邻：检索命中时提示"易混"
RELATED = {
    8: [7, 31], 12: [13, 29, 34, 35, 36], 13: [12, 29], 14: [15, 29],
    18: [19, 20], 19: [18, 20], 29: [12, 13, 14], 31: [7, 33], 33: [7, 31],
    46: [47, 48], 47: [46, 48], 48: [46, 47], 49: [120, 168],
    44: [45, 50], 45: [44], 57: [58], 58: [57],
    62: [63, 170], 63: [62], 170: [62], 90: [146, 145], 91: [144],
    92: [101, 142], 93: [94, 142], 94: [93, 142], 99: [100, 95], 100: [99, 95],
    102: [103, 92], 103: [102], 106: [101, 99], 107: [108, 92], 108: [107],
    109: [112, 113, 110, 111], 110: [111, 109], 111: [110, 109], 112: [113, 109], 113: [112, 109],
    117: [118, 119], 118: [117, 119], 119: [117, 118, 155], 155: [119, 114],
    120: [121, 132, 168], 121: [120, 132], 122: [120, 167], 123: [124, 125, 95],
    124: [123, 125], 125: [123, 124], 127: [128, 90], 128: [127, 90],
    129: [15, 162], 130: [131, 169], 131: [130], 132: [120, 168], 135: [136, 151],
    136: [135], 137: [138], 138: [137, 91], 139: [145, 146], 140: [141, 151],
    141: [140, 151], 142: [143, 92], 143: [142, 161], 144: [91], 145: [139, 146],
    146: [139, 145], 147: [148], 148: [147], 149: [150], 150: [149], 151: [140, 135],
    152: [153, 154], 153: [152], 154: [152, 153], 156: [155], 157: [133, 95],
    158: [86, 87, 164], 159: [82, 88, 172], 160: [65], 162: [129, 130],
    164: [158], 166: [120, 127], 167: [122, 168], 168: [120, 167],
    169: [130], 171: [68], 172: [159, 88], 173: [83, 160],
}

DIM_RULES = [
    ("style", ("风格", "美学", "主义", "画派", "流派", "派")),
    ("light", ("侧光", "逆光", "顶光", "底光", "主光", "补光", "柔光", "硬光",
               "顺光", "漫射光", "自然光", "窗光", "闪光", "灯光", "天光", "光晕")),
    ("color", ("色",)),
    ("composition", ("构图", "视角", "景深", "画幅", "留白", "对称", "俯视", "仰视", "平视", "满幅", "竖幅", "横幅", "特写", "全景")),
    ("texture", ("质感", "肌理", "材质", "笔触", "颗粒", "纹理", "纸", "光泽", "哑光", "厚涂", "平涂", "粗粝")),
    ("light", ("光", "照明", "阴影", "曝光")),
    ("quality", ("超清", "高清", "细节", "8k", "分辨率", "清晰")),
]


MEDIUM_RULES = [
    ("3d", ("三维", "3d", "渲染", "cg ", "cg动画", "低多边形", "手办", "pvc")),
    ("digital", ("像素", "故障", "矢量", "扁平", "赛博", "蒸汽波", "y2k", "酸性", "千禧年")),
    ("animation", ("动画", "赛璐珞", "黏土", "折纸", "水墨动画", "吉卜力", "宫崎骏", "新海诚", "今敏")),
    ("print", ("版画", "木板", "铜版", "石版", "油墨", "孔版", "木刻", "浮世绘", "琳派", "马赛克", "波普")),
    ("illustration", ("插画", "漫画", "卡通", "绘本", "二次元", "动漫", "美漫", "港漫", "波点")),
    ("photo", ("摄影", "胶片", "镜头", "照片", "实拍", "剧照", "宝丽来", "拍立得", "柯达", "富士", "证件")),
]
MEDIUM_OVERRIDE = {
    21: "graphic", 27: "photo", 28: "photo", 37: "mixed", 44: "mixed", 45: "mixed",
    57: "photo", 58: "photo", 90: "photo", 91: "mixed", 101: "graphic", 107: "cgi",
    108: "cgi", 119: "photo", 156: "photo", 157: "3d", 159: "painting", 160: "painting",
    166: "illustration", 169: "illustration", 6: "mixed", 5: "photo", 26: "photo",
}


def medium_of(sid: int, name: str, template: str, category: str) -> str:
    if category == "CO":
        return "tone"      # 色彩条目只改调性，不改成像体系，不参与媒介冲突
    if sid in MEDIUM_OVERRIDE:
        return MEDIUM_OVERRIDE[sid]
    if category == "PH":
        return "photo"
    blob = (name + template).lower()
    for label, keys in MEDIUM_RULES:
        if any(k in blob for k in keys):
            return label
    return "painting"


STOP_KW = {"色彩", "色调", "构图", "质感", "光影", "光线", "风格", "美学", "画面",
           "背景", "主体", "细节", "整体", "呈现", "带有", "充满", "高级", "统一"}
PREFIX_KW = ("色彩为", "色彩以", "色彩是", "色彩", "风格为", "风格是", "材质", "整体", "画面")
SUFFIX_KW = ("为主", "质感", "构图", "光影", "风格", "美学", "色调", "细节")


def keywords(text: str) -> list[str]:
    """从一段风格描述里提取特征词，用于反向识别与检索。"""
    out = []
    for part in re.split(r"[、，与和的及]", text):
        orig = part.strip()
        p = orig
        for pre in PREFIX_KW:
            if p.startswith(pre):
                p = p[len(pre):]
        for suf in SUFFIX_KW:
            if p.endswith(suf) and len(p) - len(suf) >= 2:
                p = p[: -len(suf)]
        p = p.strip("的要与和以且")
        if len(p) < 2 or p in STOP_KW:
            p = orig                      # 清理后无意义就退回原段
        if 2 <= len(p) <= 10 and re.fullmatch(r"[\u4e00-\u9fa5a-zA-Z ]+", p.strip()) and p not in STOP_KW:
            out.append(p.strip())
            if 5 <= len(p) <= 10:
                out.append(p[:4] if len(p) >= 7 else p[:3])   # 长词给一个可命中的短锚点
    return list(dict.fromkeys(out))


def dim_of(text: str) -> str:
    low = text.lower()
    for name, keys in DIM_RULES:
        if any(k in low for k in keys):
            return name
    return "mood"


def cat_for(idx: int):
    for code, name, lo, hi in CATEGORIES:
        if lo <= idx <= hi:
            return code, name, idx - lo + 1
    raise SystemExit(f"编号 {idx} 不在任何分类区间内")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="原始 Markdown 路径")
    args = ap.parse_args()

    raw = Path(args.source).read_text(encoding="utf-8").replace("\r\n", "\n")
    blocks = re.split(r"\n(?=\*\*\d+\. )", raw)

    styles = []
    for block in blocks[1:]:
        head = re.match(r"\*\*(\d+)\. (.+?)\*\*", block)
        if not head:
            continue
        sid, name = int(head.group(1)), head.group(2).strip()
        codes = re.findall(r"```\n(.*?)\n```", block, re.S)
        tpl_block = next(c for c in codes if c.startswith("提示词模板"))
        sample = next(c for c in codes if not c.startswith("提示词模板"))
        body = tpl_block.replace("提示词模板：", "", 1).replace("【画面主体】，", "", 1)
        segments = [{"dim": dim_of(p), "text": p, "kw": keywords(p)}
                    for p in body.split("，") if p.strip()]
        img = re.search(r"!\[alt text\]\(<?([^)>]+)>?\)", block)
        code, cname, seq = cat_for(sid)
        en, aliases = META[sid]
        styles.append({
            "id": sid,
            "code": f"{code}-{seq:02d}",
            "name": name,
            "name_en": en,
            "aliases": aliases,
            "category": code,
            "category_name": cname,
            "template": f"【画面主体】，{body}",
            "segments": segments,
            "sample": sample.strip(),
            "medium": medium_of(sid, name, body, code),
            "image": img.group(1).strip() if img else None,
            "flags": {
                "broad": sid in BROAD,
                "living_artist": sid in LIVING,
                "related": RELATED.get(sid, []),
            },
        })

    # 近邻关系对称化：易混是相互的，避免只单向记录
    rel = {s["id"]: set(s["flags"]["related"]) - {s["id"]} for s in styles}
    for sid, vs in list(rel.items()):
        for v in vs:
            rel.setdefault(v, set()).add(sid)
    for s in styles:
        s["flags"]["related"] = sorted(rel.get(s["id"], set()))

    styles.sort(key=lambda s: s["id"])
    assert len(styles) == 173, f"条目数异常：{len(styles)}"
    assert [s["id"] for s in styles] == list(range(1, 174)), "编号不连续"

    payload = {
        "version": "1.0.0",
        "generated_by": "scripts/rebuild_library.py",
        "source_doc": "视觉美学风格提示词库：美学风格173种，9大类+提示词模板.md",
        "count": len(styles),
        "categories": [
            {"code": c, "name": n, "count": h - l + 1} for c, n, l, h in CATEGORIES
        ],
        "dim_labels": {
            "style": "风格标记", "color": "色彩", "composition": "构图",
            "texture": "材质质感", "light": "光影", "quality": "画质细节", "mood": "情绪氛围",
        },
        "styles": styles,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK 写入 {OUT} 共 {len(styles)} 条", file=sys.stderr)


if __name__ == "__main__":
    main()
