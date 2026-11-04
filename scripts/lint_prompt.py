#!/usr/bin/env python3
"""成品提示词自检闸门：交付前按目标模型查文本，不查数据。

分工：`validate_library.py` 管数据（档案字段、名单、断链），本脚本管文本（长度、
语法、密度、覆盖、收尾、人名）。预算数值只有一个出处——`assets/models.json` 的
`budget` 字段，经 `model_registry.budget()` 读取；本脚本不内置任何字数上限。

为什么不塞进 build_prompt：build_prompt 交付时英文段往往还没译完（只在
`translation_todo` 里），内置检查只能查半成品，必然假 FAIL；且它还要能查人工改稿、
用户粘贴的现成提示词。所以保持独立脚本 + 管道：

    python3 scripts/build_prompt.py -s "主体" --style CN-01 --model z-image-turbo --bare \
        | python3 scripts/lint_prompt.py --model z-image-turbo -

检查项（每项给出 pass/fail/warn/skip 与一句人话说明）：
    1 budget    长度预算（按模型 budget 与 enforce 分派）
    2 syntax    禁用语法（权重括号、方括号、花括号、BREAK、--、::、<lora:…>）
    3 density   标签堆砌（逗号短词成串、没有完整句子）
    4 coverage  结构覆盖（主体/场景/光影/风格/细节 五维至少占三维）
    5 closing   质量收尾锚点（提示级，不是硬指标）
    6 name      人名命中（读 assets/living-names.json，命中即 FAIL）
    7 aesthetic 色彩主张与动机光源（提示级，可用 --no-aesthetic 关掉）
    8 anchors   参照物数量（1 主 1 次为界：>2 FAIL、=2 WARN、≤1 不报）

参照计数的口径（单一信息源，不另建关键词表）：
    计数集合 = styles-173.json 里 flags.broad=false 且 category≠CO 的条目名
              ∪ references/style-anchors.md 的 24 条参照名（含其英文锚点列的关键词）
    长名优先去重（「表现主义」被「抽象表现主义」包含时只算一次）；
    用 --style 指明本次选用的风格时，与该风格同名的那一项不计入。

等级约定：`fail` 影响退出码，`warn` 只提示，`skip` 必带原因。
硬指标（默认就影响退出码）：超预算 / 禁用语法 / 标签堆砌 / 五维覆盖不足 / 人名命中。
提示级（默认不拦交付）：质量收尾语、色彩主张、动机光源——模板本身未必写这些，极简与
抽象题材也不该被拦。加 `--strict` 走终稿口径：低于预算下限、缺色彩主张、缺动机光源
这三类也升为 FAIL（对应需求文档验收 4 的五类缺陷）。

用法：
    python3 scripts/lint_prompt.py --model flux2-klein-base-9b -f prompt.txt
    python3 scripts/lint_prompt.py --model generic --text "……"
    python3 scripts/lint_prompt.py --model qwen-image-2.1 -f p.txt --lang zh --json
    python3 scripts/lint_prompt.py --model z-image-turbo -f p.txt --max-chars 260

退出码：0 无 FAIL / 1 存在 FAIL / 2 参数或输入错误。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import model_registry as mr
import name_guard as ng

CJK_RE = re.compile(r"[\u4e00-\u9fa5]")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
LABEL_RE = re.compile(
    r"^[ \t>*#]*(?:【)?[ \t]*(中文|英文|Chinese|English)[ \t]*(?:】)?[ \t]*[:：][ \t]*",
    re.MULTILINE)
BANNER_RE = re.compile(r"^[【\[]?[^\n]{0,12}(提示词|prompt)[^\n]{0,12}[】\]]?$", re.IGNORECASE)

# 五维语义骨架：只用来判「有没有写到」，不是词库标准。宁可漏判，不要误判。
DIMS = {
    "主体": {
        "zh": ["人物", "女子", "男子", "少女", "少年", "老者", "孩童", "孩子", "身影", "背影",
               "面容", "侧脸", "双手", "一只手", "兽", "鸟", "鱼", "龙", "猫", "狗", "马",
               "花", "树", "器物", "茶壶", "茶杯", "碗", "瓶", "壶", "椅", "桌", "书", "灯",
               "船", "车", "屋", "建筑", "雕塑", "机器人", "主体"],
        "en": ["portrait", "figure", "woman", "man", "child", "girl", "boy", "creature",
               "animal", "bird", "flower", "tree", "vessel", "teapot", "object", "chair",
               "table", "book", "lantern", "boat", "building", "statue", "robot",
               "silhouette", "hands", "face", "holding", "standing", "sitting", "walking"],
    },
    "场景": {
        "zh": ["构图", "视角", "机位", "镜头", "景别", "特写", "中景", "全景", "广角", "俯拍",
               "仰视", "平视", "前景", "背景", "留白", "三分", "对角", "对称", "框架", "纵深",
               "画幅", "室内", "室外", "街", "巷", "山", "水面", "庭院", "空间"],
        "en": ["composition", "angle", "shot", "close-up", "medium shot", "wide shot",
               "foreground", "background", "perspective", "negative space", "thirds",
               "diagonal", "symmetrical", "framing", "depth", "indoor", "outdoor",
               "street", "alley", "mountain", "interior"],
    },
    "光影": {
        "zh": ["光影", "光线", "逆光", "侧光", "顶光", "底光", "柔光", "硬光", "光比", "色温",
               "阴影", "高光", "反光", "倒影", "霓虹", "烛光", "灯光", "窗光", "晨光", "暮色",
               "荧光", "发光", "冷光", "暖光", "柔焦光", "环境光", "光源",
               "雾气", "薄雾", "尘埃", "氛围", "丁达尔", "光束"],
        "en": ["light", "lit", "lighting", "shadow", "shadows", "backlit", "rim light",
               "soft light", "hard light", "key light", "chiaroscuro", "glow", "reflection",
               "neon", "candlelight", "lantern light", "window light", "mist", "fog",
               "haze", "volumetric", "sunlight", "moonlight"],
    },
    "风格": {
        "zh": ["风格", "美学", "画风", "流派", "笔触", "水墨", "油画", "版画", "摄影", "胶片",
               "渲染", "插画", "动画", "质感", "材质", "肌理", "敦煌", "宋式", "极简", "复古"],
        "en": ["style", "aesthetic", "painting", "ink wash", "watercolor", "film",
               "photograph", "render", "illustration", "anime", "texture", "material",
               "brushwork", "minimal", "retro"],
    },
    "细节": {
        "zh": ["细节", "纹理", "颗粒", "锐利", "清晰", "超清", "分辨率", "毛孔", "纤维", "裂纹",
               "包浆", "层次", "8K", "4K"],
        "en": ["detail", "detailed", "grain", "sharp", "resolution", "8k", "4k",
               "intricate", "pores", "fibers", "patina", "micro"],
    },
}

CLOSING_ANCHORS = ["8k", "4k", "超清", "超高清", "高清", "锐利", "颗粒", "masterpiece",
                   "best quality", "highly detailed", "sharp focus", "film grain",
                   "resolution", "分辨率", "高度细节", "极致细节"]

HUE_WORDS = ["红", "橙", "黄", "金", "绿", "青", "蓝", "紫", "洋红", "粉", "白", "黑", "灰",
             "赭石", "花青", "石绿", "朱砂", "胭脂", "月白", "天青", "色彩", "配色", "色调",
             "red", "crimson", "vermilion", "orange", "amber", "ochre", "gold", "yellow",
             "green", "jade", "teal", "cyan", "blue", "cobalt", "indigo", "violet", "purple",
             "magenta", "pink", "ivory", "white", "black", "grey", "gray", "charcoal",
             "palette", "hue", "tone"]
PALETTE_WORDS = ["主色", "辅色", "点缀", "配色", "基调", "色卡", "冷暖", "色温", "对比色",
                 "为主", "色系", "色阶", "单一色相",
                 "dominated by", "accent", "palette", "monochromatic", "analogous",
                 "complementary", "warm", "cool", "temperature"]
MOTIVE_WORDS = ["窗", "天窗", "门缝", "灯笼", "烛", "油灯", "火盆", "霓虹", "路灯", "车灯",
                "屏幕", "手电", "篝火", "熔炉", "月光", "阳光", "晨光", "天光", "水面反射",
                "自发光", "window", "lantern", "candle", "oil lamp", "torch", "neon sign",
                "street lamp", "headlight", "screen glow", "firelight", "moonlight",
                "sunlight", "skylight", "practical light", "self-luminous"]

# 禁用语法：每条 = (正则, 人话说明)。仅对 prose / cn_structured 生效。
BANNED = [
    (r"\(\s*[^()：:\n]{1,40}\s*:\s*[\d.]+\s*\)", "权重括号 (word:1.2)"),
    (r"\[[^\]\n]{1,40}\]", "方括号 [word]"),
    (r"\{[^}\n]{1,40}\}", "花括号 {word}"),
    (r"<lora:[^>\n]*>", "LoRA 调用 <lora:...>"),
    (r"<[A-Za-z_][^>\n]{0,30}>", "尖括号标签 <tag>"),
    (r"\bBREAK\b", "控制标记 BREAK"),
    (r"(?<![\w-])--(?=\s|$)", "控制标记 --"),
    (r"::", "权重标记 ::（NovelAI）"),
]
DENSITY_RENDERERS = ("prose",)      # 标签堆砌只对散文渲染器成立：标签式本来就该是短词
SYNTAX_FREE_RENDERERS = ("tag", "json_layout")

MIN_DIMS = 3          # 五维至少覆盖三维
# 词表收不全的中文表述，用结构式补三条（只对 zh 生效）：模板里「平光无明暗」「矿物颜料」
# 「水润光泽」这类写法很常见，靠穷举词表必然漏，漏了就会把合规模板判成覆盖不足。
ZH_AUX_PATTERNS = {
    "光影": re.compile(r"(光线|光影|光束|光质|光比|闪光|平光|强光|柔光|硬光|顶光|侧光|逆光|"
                     r"底光|冷光|暖光|荧光|光晕|的光|明暗)"),
    "风格": re.compile(r"(线描|白描|颜料|矿物|相纸|显影|毛笔|勾勒|笔意|笔法|墨|绢|宣纸|"
                     r"胶片|渲染|插画|油画|版画|工笔)"),
    "细节": re.compile(r"(纹理|光泽|肌理|颗粒|线条|韵律|纹样|开片|釉面|纤维|裂纹|包浆)"),
}
SUBJECT_MARKER = re.compile(r"[一两几这那][只个位朵株片座台条名把棵匹头枚幅张]")
SHORT_ZH = 4          # 中文短词：≤4 字
SHORT_EN = 2          # 英文短词：≤2 词


# ---------------------------------------------------------------- 输入与切分

def read_input(args) -> str:
    if args.text is not None:
        return args.text
    if args.file and args.file != "-":
        try:
            return Path(args.file).read_text(encoding="utf-8")
        except OSError as exc:
            raise UsageError(f"读不到文件 {args.file}：{exc}")
    if sys.stdin.isatty():
        raise UsageError("没有输入：给 -f/--file 或 --text，或从标准输入管道灌入（用 - 显式声明）")
    return sys.stdin.read()


def split_sections(raw: str) -> list[dict]:
    """切成 [{label, lang, text}]。

    优先按「中文：/英文：」标签切；没有标签就按空行分块，再用汉字占比判语言。
    交付口径是「中文段 + 空行 + 英文段」，所以无标签时也能认出来。
    """
    body = raw.replace("\r\n", "\n").strip()
    if not body:
        return []
    parts = LABEL_RE.split(body)
    sections: list[dict] = []
    if len(parts) > 1:
        head = parts[0].strip()
        if head:
            sections.append(_section("未标注段", head))
        for i in range(1, len(parts) - 1, 2):
            label = parts[i]
            text = parts[i + 1].strip()
            if text:
                sections.append(_section(label, text))
        return sections
    for block in re.split(r"\n\s*\n", body):
        clean = "\n".join(line for line in block.splitlines()
                          if line.strip() and not BANNER_RE.match(line)).strip()
        if clean:
            sections.append(_section("未标注段", clean))
    return sections


def _section(label: str, text: str) -> dict:
    cjk = len(CJK_RE.findall(text))
    proxy = cjk + len(WORD_RE.findall(text)) * 2      # 一个西文词约等于两个汉字的视觉量
    lang = "zh" if proxy and cjk / max(proxy, 1) >= 0.35 else "en"
    name = {"中文": "中文段", "英文": "英文段", "Chinese": "中文段",
            "English": "英文段"}.get(label, label)
    return {"label": name, "lang": lang, "text": text}


def count_zh(text: str) -> int:
    """中文段的「字数」：汉字数 + 西文词数（专名与型号常夹在中文里）。"""
    return len(CJK_RE.findall(text)) + len(WORD_RE.findall(text))


def count_en(text: str) -> int:
    return len(WORD_RE.findall(text))


# ---------------------------------------------------------------- 单项检查

def _hit(pool: list[str], text: str, lang: str) -> list[str]:
    out = []
    low = text.lower()
    for kw in pool:
        if lang == "en":
            needle = kw.lower()
            if re.fullmatch(r"[a-z0-9' ]+", needle):
                if re.search(r"(?<![a-z])" + re.escape(needle) + r"(?![a-z])", low):
                    out.append(kw)
            elif needle in low:
                out.append(kw)
        elif kw in text:
            out.append(kw)
    return out


def check_budget(text: str, lang: str, model: dict, override: int | None,
                 strict: bool) -> dict:
    renderer = model.get("renderer")
    b = mr.budget(model) or {}
    spec = b.get(lang) or {}
    if renderer in ("tag", "json_layout"):
        return {"id": "budget", "level": "skip", "value": None, "limit": None,
                "reason": f"{renderer} 渲染器不以长度为准（标签式 / JSON 布局），长度不判"}
    if b.get("enforce") == "none":
        return {"id": "budget", "level": "skip", "value": None, "limit": None,
                "reason": f"{model['id']} 档案标注 enforce=none，长度不判"}
    n = count_zh(text) if lang == "zh" else count_en(text)
    unit = "字" if lang == "zh" else "词"
    lo, hi = spec.get("min"), spec.get("max")
    source = b.get("source", "heuristic")
    if override is not None and lang == "zh":
        hi, source = override, "override"
    if hi is None:
        return {"id": "budget", "level": "skip", "value": n, "limit": None,
                "reason": "档案里没有该语言的预算上限"}
    msg = f"{n}/{hi} {unit}（{source}）"
    if n > hi:
        return {"id": "budget", "level": "fail", "value": n, "limit": hi,
                "msg": msg + f"，超出 {n - hi} {unit}，删解释性从句，保住主体与光影"}
    level, reason = "ok", ""
    if b.get("enforce") == "both" and lo is not None and n < lo:
        level = "fail" if strict else "warn"
        reason = f"低于下限 {lo} {unit}，信息密度可能不足（加 --strict 时按下限判）"
    return {"id": "budget", "level": level, "value": n, "limit": hi, "msg": msg,
            "reason": reason}


def check_syntax(text: str, model: dict) -> dict:
    renderer = model.get("renderer")
    if renderer in SYNTAX_FREE_RENDERERS:
        return {"id": "syntax", "level": "skip", "value": 0, "limit": None,
                "reason": f"{renderer} 渲染器允许标签 / JSON 结构，禁用语法不适用"}
    found = []
    for pat, why in BANNED:
        for m in re.finditer(pat, text):
            found.append(f"{why} → {m.group(0).strip()}")
    if found:
        return {"id": "syntax", "level": "fail", "value": len(found), "limit": 0,
                "msg": f"命中 {len(found)} 处禁用语法：" + "；".join(found[:4])}
    return {"id": "syntax", "level": "ok", "value": 0, "limit": 0,
            "msg": "没有权重括号 / 控制标记，模型会把这些当普通文字"}


def check_density(text: str, lang: str, model: dict) -> dict:
    renderer = model.get("renderer")
    if renderer not in DENSITY_RENDERERS:
        return {"id": "density", "level": "skip", "value": None, "limit": None,
                "reason": f"{renderer} 渲染器本来就允许标签串，密度不判"}
    if lang == "zh":
        segs = [s.strip() for s in re.split(r"[，,；;、]", text) if s.strip()]
        lengths = [len(CJK_RE.findall(s)) + (1 if WORD_RE.search(s) else 0) for s in segs]
        short_th, long_th, unit = SHORT_ZH, 10, "字"
    else:
        segs = [s.strip(" .") for s in re.split(r"[,;]", text) if s.strip(" .")]
        lengths = [len(WORD_RE.findall(s)) for s in segs]
        short_th, long_th, unit = SHORT_EN, 6, "词"
    if not segs:
        return {"id": "density", "level": "skip", "value": None, "limit": None,
                "reason": "该段没有内容可分句"}
    short = sum(1 for n in lengths if n <= short_th)
    # "有完整句"看的是最长分句够不够长——只靠句尾的「。」不能算句子，
    # 标签串也常以句号收尾，那个句号不是句子的证据。
    has_sentence = max(lengths) >= long_th
    detail = f"{short}/{len(segs)} 个分句不超过 {short_th} {unit}"
    # 阈值取在「库内 173 条成稿之上、真标签串之下」：实测成稿最坏一条是 5 个短分句 /
    # 占比 0.5（CN-01 配极短主体），而真标签串普遍 ≥6 个短分句、占比 ≥0.8。
    if short >= 6 and short / len(segs) >= 0.65 and not has_sentence:
        return {"id": "density", "level": "fail", "value": short, "limit": len(segs),
                "msg": f"像标签堆砌：{detail}，且没有一句完整句子；改写为连贯长句"}
    if not has_sentence:
        return {"id": "density", "level": "warn", "value": short, "limit": len(segs),
                "msg": f"分句偏碎（{detail}），建议合并成一句完整描述"}
    return {"id": "density", "level": "ok", "value": short, "limit": len(segs),
            "msg": f"分句密度正常（{detail}）"}


def check_coverage(text: str, lang: str, model: dict, enabled: bool = True) -> dict:
    renderer = model.get("renderer")
    if renderer in SYNTAX_FREE_RENDERERS:
        return {"id": "coverage", "level": "skip", "value": None, "limit": None,
                "reason": f"{renderer} 渲染器不按语义段落组织，覆盖不判"}
    if not enabled:
        return {"id": "coverage", "level": "skip", "value": None, "limit": None,
                "reason": "已用 --no-aesthetic（抽象 / 版式类题材），五维覆盖不判"}
    got = {}
    for dim, pool in DIMS.items():
        got[dim] = _hit(pool[lang], text, lang)
    if lang == "zh":
        for dim, pat in ZH_AUX_PATTERNS.items():
            if not got[dim]:
                m = pat.search(text)
                if m:
                    got[dim] = [m.group(0)]
    if lang == "zh" and not got["主体"] and SUBJECT_MARKER.search(text):
        got["主体"] = [SUBJECT_MARKER.search(text).group(0)]   # 一/两/这/那 + 量词：点明了「什么东西」
    covered = [d for d, v in got.items() if v]
    missing = [d for d, v in got.items() if not v]
    msg = f"覆盖 {len(covered)}/5 维：{'、'.join(covered) or '无'}"
    if len(covered) < MIN_DIMS:
        return {"id": "coverage", "level": "fail", "value": len(covered), "limit": MIN_DIMS,
                "msg": msg + f"；缺 {'、'.join(missing)}，至少写满 {MIN_DIMS} 维"}
    return {"id": "coverage", "level": "ok", "value": len(covered), "limit": MIN_DIMS,
            "msg": msg + (f"；缺 {'、'.join(missing)}" if missing else "")}


def check_closing(text: str, lang: str, model: dict, strict: bool = False) -> dict:
    if model.get("renderer") in SYNTAX_FREE_RENDERERS:
        return {"id": "closing", "level": "skip", "value": None, "limit": None,
                "reason": f"{model.get('renderer')} 渲染器不要求收尾语"}
    tail = text[-60:] if lang == "zh" else " ".join(text.split()[-18:])
    low = tail.lower()
    for a in CLOSING_ANCHORS:
        if a.lower() in low:
            return {"id": "closing", "level": "ok", "value": a, "limit": None,
                    "msg": f"结尾有质量锚点「{a}」"}
    return {"id": "closing", "level": "warn", "value": None, "limit": None,
            "msg": "结尾没有质量收尾语（不是每条模板都有，可补一句超清细节 / sharp focus）"}


def check_name(text: str) -> dict:
    hit = ng.hits(text)
    if hit:
        first = hit[0]
        return {"id": "name", "level": "fail", "value": len(hit), "limit": 0,
                "msg": f"出现个人姓名：{'、'.join(h['zh'] or h['name'] for h in hit)}",
                "reason": f"改写为可观察特征：{first['features']}"}
    return {"id": "name", "level": "ok", "value": 0, "limit": 0,
            "msg": "没有出现净化名单里的姓名"}


def check_aesthetic(text: str, lang: str, model: dict, enabled: bool,
                    strict: bool = False) -> dict:
    if not enabled:
        return {"id": "aesthetic", "level": "skip", "value": None, "limit": None,
                "reason": "已用 --no-aesthetic 关掉（抽象 / 极简 / 版式类题材可以不写）"}
    if model.get("renderer") in SYNTAX_FREE_RENDERERS:
        return {"id": "aesthetic", "level": "skip", "value": None, "limit": None,
                "reason": f"{model.get('renderer')} 渲染器不做审美层判读"}
    hue = _hit(HUE_WORDS, text, lang)
    palette = _hit(PALETTE_WORDS, text, lang)
    motive = _hit(MOTIVE_WORDS, text, lang)
    lacks = []
    if not (hue and palette):
        lacks.append("色彩主张（主/辅/点缀或冷暖对撞）")
    if not motive:
        lacks.append("动机光源（光要有出处：窗、灯、火、屏、反射）")
    if lacks:
        # 默认只提示（模板未必写色彩主张 / 极简题材可以不写）；--strict 时算硬伤
        return {"id": "aesthetic", "level": "fail" if strict else "warn",
                "value": len(lacks), "limit": 0,
                "msg": "审美层缺 " + "；".join(lacks) + "，画面容易发灰或像棚拍"}
    return {"id": "aesthetic", "level": "ok", "value": 0, "limit": 0,
            "msg": "色彩主张与动机光源都在"}



# ------------------------------------------------------------ 参照计数（第 8 项）

_STYLE_INDEX: dict[str, str] | None = None      # code -> 条目名
_ANCHORS: list[dict] | None = None
ANCHOR_FAIL_OVER = 2      # 库外锚点：>2 FAIL、=2 WARN
STYLE_WARN_AT = 3         # 库内条目名按 code 去重：=3 WARN、>=4 FAIL
STYLE_FAIL_AT = 4


def style_index() -> dict[str, str]:
    """库内参照池：code -> 条目名（只取非宽泛、非 CO 的条目）。

    只认条目名，不认别名：别名（港漫/动漫/水墨）常与别的条目重名，或本身就是常用词，
    算进去会重复计数、也会把正常描述判成堆叠。同一 code 天然只算一次。
    """
    global _STYLE_INDEX
    if _STYLE_INDEX is None:
        path = ROOT / "assets" / "styles-173.json"
        try:
            db = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"参照计数需要 {path}：{exc}")
        _STYLE_INDEX = {x["code"]: x["name"] for x in db["styles"]
                        if not (x.get("flags") or {}).get("broad")
                        and x.get("category") != "CO"}
    return _STYLE_INDEX


def anchors() -> list[dict]:
    """库外参照池：style-anchors.md 的 24 条（中文名 + 英文锚点列当关键词）。

    不另建关键词表——表格本身就是单一信息源，改表即改判据。
    """
    global _ANCHORS
    if _ANCHORS is None:
        path = ROOT / "references" / "style-anchors.md"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"参照计数需要 {path}：{exc}")
        header, out = None, []
        for raw in text.splitlines():
            line = raw.strip()
            if not line.startswith("|"):
                header = None
                continue
            cells = [c.strip().replace("`", "").replace("**", "")
                     for c in line.strip("|").split("|")]
            if header is None:
                header = cells
                continue
            if set("".join(cells)) <= set("-: ") or header[0] != "参照" or not cells[0]:
                continue
            en = cells[header.index("英文锚点")] if "英文锚点" in header and \
                header.index("英文锚点") < len(cells) else ""
            keys = [k.strip() for k in re.split(r"[,，]", en) if len(k.strip()) >= 6]
            out.append({"name": cells[0], "keys": keys})
        _ANCHORS = out
    return _ANCHORS


def _en_hit(key: str, text: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(key.lower()) + r"(?![a-z])", text.lower()) is not None


STYLE_SUFFIXES = ("风格", "美学", "主义", "画风", "画派", "流派", "风", "派", "画", "绘")


def _cited(name: str, text: str) -> bool:
    """判断库内条目名是「被当作风格引用」还是「恰好同形的技法词」。

    例：「背景留白」里的「留白」是构图手法（CN-11 也叫留白），不该算一次风格引用；
    而「宋式美学」「水墨风」「浮世绘」这类自带引用形态的名字，出现在句子里就算引用。
    判定：名字自带风格后缀（风格/美学/主义/风/派/画…）→ 出现即算；
          否则必须在逗号分句里单独成句，或被「风格/美学」直接跟随时才算。
    """
    if name.endswith(STYLE_SUFFIXES):
        return name in text
    if any(c.strip() == name for c in re.split(r"[，,。；;、\s]+", text)):
        return True
    return re.search(re.escape(name) + r"(?:风格|美学)", text) is not None


def check_anchor_overuse(text: str, lang: str, exclude: set[str]) -> dict:
    """参照数量：库外锚点与库内条目名分开计数、分开判级。

      ext = style-anchors.md 的 24 条库外锚点   → ext > 2 判 FAIL（1 主 1 次的红线针对参照）
      int = 173 库内条目名（按 code 去重）      → int = 3 WARN，int >= 4 FAIL
    库内为什么 3 个只提示：装配器（build_prompt）本身允许最多 3 个风格，检查器不能比它更严。
    """
    ext = [a["name"] for a in anchors()
           if a["name"] in text or (lang == "en" and any(_en_hit(k, text) for k in a["keys"]))]
    ext = [h for h in dict.fromkeys(ext) if h not in exclude]
    ints = [name for name in style_index().values()
            if name not in exclude and _cited(name, text)]
    n_ext, n_int = len(ext), len(ints)
    count_msg = f"ext {n_ext} / int {n_int}"
    if ext:
        count_msg += f"（库外：{'、'.join(ext[:3])}{'…' if n_ext > 3 else ''}）"
    if ints:
        count_msg += f"（库内：{'、'.join(ints[:3])}{'…' if n_int > 3 else ''}）"

    if n_ext > ANCHOR_FAIL_OVER:
        return {"id": "anchors", "level": "fail", "value": n_ext, "limit": ANCHOR_FAIL_OVER,
                "msg": f"库外参照 {n_ext} 个，超过 1 主 1 次的上限；{count_msg}",
                "reason": "留 1 个主参照 + 最多 1 个只借色彩或光影的次参照，其余改写成可观察特征"}
    if n_int >= STYLE_FAIL_AT:
        return {"id": "anchors", "level": "fail", "value": n_int, "limit": STYLE_WARN_AT,
                "msg": f"库内风格 {n_int} 个，超过装配器 3 个上限；{count_msg}",
                "reason": "删到 1 主 + 1 次，其余并进主体描述，不要让四个风格互相稀释"}
    if n_int == STYLE_WARN_AT:
        return {"id": "anchors", "level": "warn", "value": n_int, "limit": STYLE_WARN_AT,
                "msg": f"三个风格并列，装配器上限内，但画面容易互相稀释；{count_msg}",
                "reason": "确认主风格是哪一个，另外两个只借色彩或光影，不要三段造型都留"}
    if n_ext == ANCHOR_FAIL_OVER:
        return {"id": "anchors", "level": "warn", "value": n_ext, "limit": ANCHOR_FAIL_OVER,
                "msg": f"库外参照 2 个，正好压在上限；{count_msg}",
                "reason": "确认第二次参照只借一个维度（通常是光或构图），否则删掉"}
    return {"id": "anchors", "level": "ok", "value": max(n_ext, n_int),
            "limit": ANCHOR_FAIL_OVER, "msg": f"参照在限内；{count_msg}"}


def resolve_style_names(spec: str) -> set[str]:
    """把 --style 的编号/名称解析成规范条目名，用于从参照计数里剔除自身。"""
    out: set[str] = set()
    if not spec:
        return out
    try:
        db = json.loads((ROOT / "assets" / "styles-173.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    by_code = {x["code"].lower(): x["name"] for x in db["styles"]}
    by_name = {x["name"]: x["name"] for x in db["styles"]}
    for tok in re.split(r"[,，]", spec):
        t = tok.strip()
        if not t:
            continue
        if t.lower() in by_code:
            out.add(by_code[t.lower()])
        elif t in by_name:
            out.add(by_name[t])
    return out


def selftest() -> int:
    """3 正 3 反：3 个应拦交付（exit 1）、3 个应放行（exit 0），外加 173 条成稿回归。"""
    cases = [
        ("库内 3 名 → 放行", "宋式美学，浮世绘，赛博朋克", 0),
        ("库内 4 名 → 拦下", "宋式美学，浮世绘，赛博朋克，工笔画", 1),
        ("库外 3 锚点 → 拦下", "荷兰黄金时代的室内窗光，南宋山水的「一角半边」，霓虹绿与暗红对撞的窄巷", 1),
        ("库内 1 名 → 放行", "宋式美学", 0),
        ("库外 1 锚点 → 放行", "荷兰黄金时代的室内窗光", 0),
        ("零参照 → 放行", "一只青瓷茶壶立在素麻布上，柔光，三分构图，超清细节", 0),
    ]
    bad = 0
    for label, text, want_exit in cases:
        r = check_anchor_overuse(text, "zh", set())
        got_exit = 1 if r["level"] == "fail" else 0
        ok = got_exit == want_exit
        bad += 0 if ok else 1
        print(f"[{'OK ' if ok else 'BAD'}] {label}：level={r['level']} exit={got_exit}"
              f"（期望 {want_exit}）{r['msg']}")
    # 库内成稿回归：模板 + 主体，任何一条被 anchors 或 density 判 FAIL，都算闸门在打自己
    import json as _json
    db = _json.loads((ROOT / "assets" / "styles-173.json").read_text(encoding="utf-8"))
    fails = []
    for st in db["styles"]:
        text = st["template"].replace("【画面主体】", "茶壶")
        a = check_anchor_overuse(text, "zh", set())
        d = check_density(text, "zh", {"id": "self", "renderer": "prose"})
        if a["level"] == "fail" or d["level"] == "fail":
            fails.append((st["code"], a["level"], d["level"]))
    print(f"[{'OK ' if not fails else 'BAD'}] 库内 {len(db['styles'])} 条成稿："
          f"参照/密度 FAIL = {len(fails)}" + (f" → {fails[:5]}" if fails else ""))
    bad += 1 if fails else 0
    print(f"自测：{len(cases) + 1 - bad}/{len(cases) + 1} 通过")
    return 0 if bad == 0 else 1


# ---------------------------------------------------------------- 汇总与输出

LEVEL_MARK = {"ok": "PASS", "warn": "WARN", "fail": "FAIL", "skip": "SKIP"}


def inspect(text: str, model: dict, lang: str, args) -> dict:
    override = args.max_chars if lang == "zh" else None
    checks = [
        check_budget(text, lang, model, override, args.strict),
        check_syntax(text, model),
        check_density(text, lang, model),
        check_coverage(text, lang, model, not args.no_aesthetic),
        check_closing(text, lang, model, args.strict),
        check_name(text),
        check_aesthetic(text, lang, model, not args.no_aesthetic, args.strict),
        check_anchor_overuse(text, lang, args.style_names),
    ]
    for c in checks:
        c.setdefault("msg", "")
        c.setdefault("reason", "")
    counts = {lv: sum(1 for c in checks if c["level"] == lv)
              for lv in ("ok", "warn", "fail", "skip")}
    return {"lang": lang, "checks": checks, "counts": counts,
            "ok": counts["fail"] == 0}


def render_text(section_label: str, result: dict, quiet: bool) -> str:
    if quiet:
        return f"[{'PASS' if result['ok'] else 'FAIL'}] {section_label}"
    lines = [f"{'PASS' if result['ok'] else 'FAIL'}  {section_label}"
             f"（{result['lang']}，{result['counts']['ok']} 通过"
             f" / {result['counts']['warn']} 提示 / {result['counts']['fail']} 不合格"
             f" / {result['counts']['skip']} 不适用）"]
    for c in result["checks"]:
        mark = LEVEL_MARK[c["level"]]
        line = f"  [{mark:4}] {c['id']:9} {c.get('msg', '')}"
        if c["level"] == "skip" and c.get("reason"):
            line += f"（跳过：{c['reason']}）"
        elif c.get("reason"):
            line += f"\n         → {c['reason']}"
        lines.append(line)
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="成品提示词自检（预算读 models.json，人名读 living-names.json）")
    ap.add_argument("-f", "--file", help="提示词文件路径；用 - 表示标准输入")
    ap.add_argument("--text", help="直接给一段提示词文本")
    ap.add_argument("path", nargs="?", help="位置参数形式的文件路径（等价 -f，兼容管道写法）")
    ap.add_argument("--style", default="",
                    help="本次用到的风格（编号或名称，逗号分隔）：与它同名的参照不计入参照数")
    ap.add_argument("--selftest", action="store_true",
                    help="内置参照闸门自测（3 正 3 反），跑完退出；不需要 --model")
    ap.add_argument("--model",
                    help="目标模型（必填，--selftest 除外）：预算与检查项都按它的 renderer 分派；"
                         "泛用场景显式写 generic")
    ap.add_argument("--lang", choices=("zh", "en", "both"), default="both",
                    help="只查中文段 / 只查英文段 / 都查（默认 both）")
    ap.add_argument("--max-chars", type=int, default=None,
                    help="覆盖中文段上限（报告里标 budget_source=override）")
    ap.add_argument("--strict", action="store_true",
                    help="终稿口径：低于预算下限、缺色彩主张、缺动机光源都判 FAIL（默认这三项是提示）")
    ap.add_argument("--no-aesthetic", action="store_true",
                    help="关掉审美层判读（抽象 / 极简 / 版式类题材）")
    ap.add_argument("--json", action="store_true", help="机器可读报告")
    ap.add_argument("--quiet", action="store_true", help="只输出 PASS / FAIL")
    args = ap.parse_args()
    if args.path and not args.file:
        args.file = args.path

    if args.selftest:
        return selftest()
    if not args.model:
        print("必须给 --model：预算与检查项都按目标模型分派；泛用场景写 --model generic",
              file=sys.stderr)
        return 2
    args.style_names = resolve_style_names(args.style)

    model = mr.resolve(args.model)
    if not model:
        print(f"未知模型：{args.model}。可用 --model generic 走通用档；"
              f"模型清单见 python3 scripts/model_registry.py --list", file=sys.stderr)
        return 2
    if model["id"] != args.model.strip().lower():
        print(f"「{args.model}」按别名解析为 {model['id']}（预算按 {model['id']} 判）",
              file=sys.stderr)
    if args.max_chars is not None and args.max_chars <= 0:
        print("--max-chars 必须是正整数", file=sys.stderr)
        return 2

    try:
        raw = read_input(args)
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    sections = split_sections(raw)
    if not sections:
        print("输入为空，没有可检查的内容", file=sys.stderr)
        return 2

    want = ("zh", "en") if args.lang == "both" else (args.lang,)
    picked = [s for s in sections if s["lang"] in want]
    skipped = [s for s in sections if s["lang"] not in want]

    results = []
    for s in picked:
        results.append((s["label"], inspect(s["text"], model, s["lang"], args)))

    if not results:
        print(f"输入里没有 --lang {args.lang} 对应的段落"
              f"（识别到：{[s['lang'] for s in sections]}）", file=sys.stderr)
        return 2

    all_ok = all(r["ok"] for _, r in results)
    overall_counts = {lv: sum(r["counts"][lv] for _, r in results)
                      for lv in ("ok", "warn", "fail", "skip")}

    if args.json:
        payload = {
            "ok": all_ok,
            "model": {"id": model["id"], "renderer": model["renderer"],
                      "language": model.get("language")},
            "budget": mr.budget(model),
            "budget_source": "override" if args.max_chars is not None else
                             (mr.budget(model) or {}).get("source"),
            "counts": overall_counts,
            "checks": [{"section": label, **c} for label, r in results for c in r["checks"]],
            "sections": [{"section": label, **r} for label, r in results],
            "skipped_sections": [{"section": s["label"], "lang": s["lang"]} for s in skipped],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for label, r in results:
            print(render_text(label, r, args.quiet))
        if not args.quiet:
            print("-" * 56)
            print(f"模型 {model['id']}（{model['renderer']}）｜预算：{mr.budget_line(model)}")
            if skipped:
                print(f"按 --lang {args.lang} 跳过：{[s['label'] for s in skipped]}")
            print("结论：" + ("通过" if all_ok else
                              f"有 {overall_counts['fail']} 项不合格，改完再交付"))
    return 0 if all_ok else 1


class UsageError(Exception):
    """参数或输入问题，统一走退出码 2。"""


if __name__ == "__main__":
    sys.exit(main())
