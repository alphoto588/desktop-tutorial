#!/usr/bin/env python3
"""把「画面主体 + 1~3 个风格」组装成可直接使用的提示词。

核心规则：每条风格被拆成六个维度段（色彩/构图/质感/光影/画质/风格标记/情绪）。
主风格给全段；后续风格只覆盖你指定的维度，避免同一段描述互相矛盾。

用法：
    python3 scripts/build_prompt.py -s "青瓷茶具静物" --style CN-01
    python3 scripts/build_prompt.py -s "新中式客厅" --style 新中式,莫兰迪色系 --platform mj --aspect 3:4
    python3 scripts/build_prompt.py -s "赛博城市" --style DG-03 --dims color,light,composition --json

退出码：0 正常 / 1 风格未找到 / 2 参数错误 / 3 检出硬冲突且 --strict
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))          # 允许脚本被 importlib 以文件路径加载时仍能导入同目录模块
import layout_registry as lr
import model_registry as mr
import model_render

ROOT = HERE.parent
DATA = ROOT / "assets" / "styles-173.json"
ORDER = ["style", "color", "composition", "texture", "light", "quality", "mood"]

FLAT_KW = ("平涂", "矢量", "描边", "漫画", "卡通", "像素", "波普", "扁平", "勾线", "白描")
REAL_KW = ("毛孔", "皮肤质感", "照片", "摄影", "实拍", "胶片", "写实", "剧照", "镜头")
HARD_KW = ("硬光", "直射", "强反差", "强对比", "明暗", "侧光", "逆光", "聚光")
SOFT_KW = ("柔光", "漫射", "均匀光", "无影光", "柔焦", "柔化", "散射")

MEDIUM_CN = {"photo": "摄影", "painting": "绘画", "print": "版画", "illustration": "插画",
             "animation": "动画", "digital": "数字图形", "3d": "三维", "graphic": "平面设计",
             "cgi": "CG", "mixed": "混合媒介", "tone": "调性"}

ASPECTS = {"1:1", "3:4", "4:3", "2:3", "3:2", "9:16", "16:9", "21:9", "5:2", "2.35:1"}

NEG_BASE = "低清、模糊、畸变、多余手指、过曝、欠曝、塑料感、文字乱码、水印"

# 模型清单由 assets/models.json 驱动。新增模型只改 JSON，不改本文件。
PLATFORMS: dict[str, dict] = {}
for _m in mr.models():
    PLATFORMS[_m["id"]] = {
        "label": _m["label"],
        "params": "",
        "neg_style": (_m.get("negative") or {}).get("mode", "separate"),
        "renderer": _m["renderer"],
    }
for _alias in ("sd", "sd-xl", "sdxl-base"):     # 旧命令兼容：SD 系指向 FLUX.2 klein 4B（同为 4B 级开放权重）
    if "flux2-klein-base-4b" in PLATFORMS:
        PLATFORMS[_alias] = PLATFORMS["flux2-klein-base-4b"]


def load() -> dict:
    try:
        return json.loads(DATA.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"数据文件缺失：{DATA}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"数据文件损坏：{exc}", file=sys.stderr)
        sys.exit(2)


def resolve(token: str, styles: list[dict]) -> dict | None:
    t = token.strip().lower()
    for s in styles:
        if t in (str(s["id"]), s["code"].lower(), s["name"].lower(), s["name_en"].lower()):
            return s
    for s in styles:
        if t in [a.lower() for a in s["aliases"]]:
            return s
    for s in styles:
        if t and (t in s["name"].lower() or t in s["name_en"].lower()):
            return s
    return None


FILLER = ("高级感", "唯美", "大气", "惊艳", "氛围感", "有故事感", "有意境",
          "好看", "漂亮", "震撼", "绝美", "完美", "精致感", "艺术感", "高颜值")
ABSTRACT = ("孤独", "时间流逝", "禅意", "呼吸感", "灵魂", "生命力", "故事",
            "情绪", "气质", "韵味", "留白", "空白", "意境")
NEGATION = ("不要", "没有", "不含", "避免", "别", "勿", "无任何")
ENV_HINT = ("光", "影", "晨", "昏", "夜", "午后", "清晨", "黄昏", "窗", "灯",
            "逆光", "侧光", "室内", "户外", "天空", "墙面", "背景", "远处", "前景")
# 这些名字本身是常用描述词，出现在主体里属正常，不算风格名重复
SUBJECT_NAME_EXEMPT = {11, 148, 156, 157, 158, 159, 160, 166}


def check_subject(subject: str, styles: list[dict]) -> dict:
    """主体句体检：找出会让画面不稳定的写法，并给出可执行的改法。"""
    issues, tips = [], []
    score = 100
    text = subject.strip()
    n = len(text)

    if n < 10:
        score -= 15
        issues.append({"tag": "过短", "hit": f"{n} 字", "why": "模型会自行补全，通常补成最俗套的版本",
                       "fix": "补上摆放面、陪体与一条环境线索，控制在 20–60 字"})
    elif n > 120:
        score -= 10
        issues.append({"tag": "过长", "hit": f"{n} 字", "why": "挤占风格段的注意力，风格还原度会下降",
                       "fix": "删掉解释性从句，压到 60 字以内"})

    hits = [s for s in styles
            if s["id"] not in SUBJECT_NAME_EXEMPT and s["name"] in text]
    if hits:
        score -= 15
        issues.append({"tag": "含风格名", "hit": "、".join(s["name"] for s in hits),
                       "why": "风格段还会再拼一次，同一概念被强调两遍会过拟合，画面反而更塑料",
                       "fix": "主体只写内容，风格交给 --style"})

    f = [w for w in FILLER if w in text]
    if f:
        score -= 12
        issues.append({"tag": "空泛评价词", "hit": "、".join(f),
                       "why": "模型没有对应的视觉操作，这几个字等于没写",
                       "fix": "换成可拍的细节：「釉面有细密开片」「桌面只有一只壶」"})

    neg = [w for w in NEGATION if w in text]
    if neg:
        score -= 10
        issues.append({"tag": "否定句", "hit": "、".join(neg),
                       "why": "扩散模型对否定处理很弱，「没有人物」常被理解成「有人物」",
                       "fix": "转成正向陈述：「画面仅此一物」"})

    # 「留白的墙」「禅意的庭院」是具体修饰，不算空谈；只有当它被当作画面本身时才扣分
    ab = [w for w in ABSTRACT if w in text and not re.search(re.escape(w) + "的", text)]
    if ab:
        score -= 8
        issues.append({"tag": "抽象概念", "hit": "、".join(ab),
                       "why": "概念不能直接被画，模型只能猜到最俗套的符号",
                       "fix": "换成载体：孤独→独坐的背影；时间→被风翻起的日历"})

    if n >= 10 and not any(w in text for w in ENV_HINT):
        score -= 8
        tips.append({"tag": "缺环境线索",
                     "why": "没有光向、时间或空间关系，画面容易悬空",
                     "fix": "补一句「晨光自左侧斜入」或「身后是斑驳白墙」"})

    score = max(0, score)
    return {"score": score, "length": n, "issues": issues, "tips": tips,
            "ok": score >= 85 and not issues}


def conflicts(a: dict, b: dict) -> list[dict]:
    """三条可解释的叠加冲突规则，命中即给出理由与解法。"""
    out = []
    ta, tb = a["template"], b["template"]
    ma, mb = a.get("medium", "painting"), b.get("medium", "painting")
    pairs = [
        ({"photo"}, {"painting", "print", "illustration", "animation"}),
        ({"3d"}, {"painting", "print", "illustration", "animation"}),
        ({"digital"}, {"painting", "print", "photo"}),
    ]
    if any((ma in x and mb in y) or (mb in x and ma in y) for x, y in pairs):
        out.append({"rule": "媒介冲突", "level": "high",
                    "why": f"{a['name']}（{MEDIUM_CN.get(ma, ma)}）与 {b['name']}（{MEDIUM_CN.get(mb, mb)}）不是在同一个成像体系里，模型会在两种渲染方式之间摇摆，成品常见「半写实半插画」的塑料感",
                    "fix": "二选一；若确实要融合，必须在主体里显式分工（如「人物实拍质感，背景手绘」），否则不要叠加"})

    hard_a, soft_a = any(k in ta for k in HARD_KW), any(k in ta for k in SOFT_KW)
    hard_b, soft_b = any(k in tb for k in HARD_KW), any(k in tb for k in SOFT_KW)
    if (hard_a and soft_b) or (hard_b and soft_a):
        hard_one, soft_one = (a, b) if hard_a and soft_b else (b, a)
        out.append({"rule": "光影冲突", "level": "medium",
                    "why": f"{hard_one['name']} 要求硬质光、{soft_one['name']} 要求柔性光，两段光影词会被模型平均掉，结果既不硬也不柔，通常表现为「灰扑扑」",
                    "fix": "只保留一个风格的光影段（用 --dims 排除 light），另一个只借色彩"})

    ancient = a["category"] in {"CN", "JP"}
    digital = b["category"] == "DG"
    if (ancient and digital) or (b["category"] in {"CN", "JP"} and a["category"] == "DG"):
        out.append({"rule": "时代冲突", "level": "low",
                    "why": f"{a['name']} 属古典语汇、{b['name']} 属数字语汇，直接拼接容易得到「古建筑上贴霓虹」的廉价拼贴感",
                    "fix": "这类混搭可行但需要说明融合逻辑（材质替换、载体错置、时间叠印），否则建议改用已内置融合的条目，如新国风、国潮"})
    return out


def build(subject: str, picks: list[dict], dims: list[str]) -> tuple[list[dict], list[str]]:
    """返回 (最终段列表, 覆盖说明)。"""
    base = picks[0]
    segs = [dict(s) for s in base["segments"]]
    notes = []
    for extra in picks[1:]:
        for dim in dims:
            incoming = [s for s in extra["segments"] if s["dim"] == dim]
            if not incoming:
                continue
            same = [i for i, s in enumerate(segs) if s["dim"] == dim]
            if same:
                segs[same[0]] = dict(incoming[0])
                for i in reversed(same[1:]):
                    segs.pop(i)
                notes.append(f"{extra['name']} 覆盖了 {base['name']} 的{dim_label(dim)}段")
            else:
                segs.insert(min(len(segs), max(0, len(segs) - 1)), dict(incoming[0]))
                notes.append(f"{extra['name']} 补充了{dim_label(dim)}段")
    # 同一维度重复出现时合并去重，保持原顺序
    seen, out = set(), []
    for s in segs:
        key = (s["dim"], s["text"])
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out, notes


DIM_CN = {"style": "风格标记", "color": "色彩", "composition": "构图",
          "texture": "材质质感", "light": "光影", "quality": "画质细节", "mood": "情绪氛围"}


def dim_label(d: str) -> str:
    return DIM_CN.get(d, d)


def render(platform: str, aspect: str, subject: str, segs: list[dict],
           negative: str = "", opts: dict | None = None) -> tuple[str, str, str]:
    """兼容旧调用的三元组接口；语法细节全部委托给 model_render。"""
    model = mr.resolve(platform) or mr.resolve("generic")
    out = model_render.render(model, subject, segs, aspect, negative, opts)
    return out["prompt"], out["negative"], out["params"]


def render_detail(platform: str, aspect: str, subject: str, segs: list[dict],
                  negative: str = "", opts: dict | None = None, lang: str = "zh") -> dict:
    model = mr.resolve(platform) or mr.resolve("generic")
    return model_render.render(model, subject, segs, aspect, negative, opts, lang=lang)


def _brief_get(brief: dict, path: str):
    cur = brief
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _subject_from_brief(brief: dict) -> str:
    """把主体与创意追问的答案并成一句，而不是挂成两条互不相干的指令。"""
    s = brief.get("subject") or {}
    parts = [str(s.get(k, "")).strip() for k in ("who", "action", "setting", "detail")]
    view = str(s.get("viewpoint", "")).strip()
    twist = str(s.get("twist", "")).strip()
    mood = str(s.get("mood", "")).strip()
    if view:
        parts.append(f"{view}视角")
    if twist:
        parts.append(twist)
    if mood:
        parts.append(f"{mood}的氛围")
    return "，".join([x for x in parts if x])


def _list_models_and_exit(msg: str) -> None:
    print(msg, file=sys.stderr)
    for i, m in enumerate(mr.offered(), 1):
        print(f"  {i:2d}. {m['label']}", file=sys.stderr)
    print("\n选定后用 --model <序号或名称> 重跑。", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    ap = argparse.ArgumentParser(description="组装风格提示词（按目标模型语法渲染）")
    ap.add_argument("-s", "--subject", help="画面主体；配合 --brief 时可省略")
    ap.add_argument("--style", help="风格：编号/代码/名称/别名，逗号分隔，首个为主风格")
    ap.add_argument("--model", "--platform", dest="model", default=None,
                    help="目标模型：id / 显示名 / 序号均可；不给会列出清单并退出")
    ap.add_argument("--brief", help="intake.py 产出的 brief.json；给了就先做完整性体检")
    ap.add_argument("--dims", help="副风格可覆盖的维度，默认 color,light")
    ap.add_argument("--aspect", default="", help="画面比例，如 3:4 / 16:9")
    ap.add_argument("--text-in-image", default="", help="要渲染在图上的文字原文")
    ap.add_argument("--transparent", action="store_true", help="需要透明底（仅部分模型支持）")
    ap.add_argument("--variant", default="", help="模型变体，如 SFT / Large / 2K")
    ap.add_argument("--layout-json", metavar="FILE", dest="layout_json", help="MOSS-Image 布局对象数组（JSON），给了就输出 layout JSON")
    ap.add_argument("--negative", default="", help="追加负向词")
    ap.add_argument("--no-negative", action="store_true", help="不输出负向词")
    ap.add_argument("--strict", action="store_true", help="出现高等级冲突时直接失败")
    ap.add_argument("--force", action="store_true", help="brief 体检不通过也继续")
    ap.add_argument("--bare", action="store_true", help="只输出提示词正文（不含任何说明块）")
    ap.add_argument("--layout", help="排版图型编号或名称，如 IG-01 / 公众号题图")
    ap.add_argument("--color", help="主题色编号或名称，如 C-03 / 胭脂")
    ap.add_argument("--with-ref", action="store_true", help="附带主风格的参考图说明（隔离子句 + 图片路径）")
    ap.add_argument("--edit", default="", help="编辑模型：要改什么")
    ap.add_argument("--preserve", default="", help="编辑模型：要保留什么")
    ap.add_argument("--en-map", metavar="FILE", help="中英对照表（subject + segments），给了才输出英文版")
    ap.add_argument("--subject-en", default="", help="英文主体；不给则用 --en-map 里的 subject")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args()

    db = load()
    styles = db["styles"]

    subject = (args.subject or "").strip()
    style_tokens = (args.style or "").strip()
    model_id = args.model
    aspect = args.aspect.strip()
    text_in_image = args.text_in_image.strip()
    transparent = args.transparent
    intake_res = None

    if args.brief:
        bpath = Path(args.brief)
        if not bpath.exists():
            print(f"brief 文件不存在：{bpath}", file=sys.stderr)
            sys.exit(2)
        brief = json.loads(bpath.read_text(encoding="utf-8"))
        import intake
        intake_res = intake.check(brief)
        if not intake_res["ok"] and not args.force:
            print(f"【需求完整性】{intake_res['score']} 分 —— 信息不足，先补齐再出稿")
            for k in intake_res["missing"]:
                print(f"  [ ] 缺 {k}")
            for e in intake_res["errors"]:
                print(f"  [ERR] {e}")
            for w in intake_res["warnings"]:
                print(f"  [i] {w}")
            print("\n补齐后重跑，或用 --force 带缺口出稿。")
            sys.exit(4)
        if not subject:
            subject = _subject_from_brief(brief)
        if not style_tokens:
            style_tokens = (str(_brief_get(brief, "style.specified") or "")).strip()
        if not aspect:
            aspect = (str(_brief_get(brief, "scene.aspect") or "")).strip()
        if model_id == "generic" and _brief_get(brief, "model"):
            model_id = str(_brief_get(brief, "model"))
        text_in_image = text_in_image or str(_brief_get(brief, "scene.text_in_image") or "")
        transparent = transparent or bool(_brief_get(brief, "scene.transparent"))

    if not model_id:
        _list_models_and_exit("请先选择一个模型——不同模型的语法、负向、步数、尺寸完全不同：")

    if str(model_id).isdigit():
        off = mr.offered()
        idx = int(model_id)
        if 1 <= idx <= len(off):
            model_id = off[idx - 1]["id"]
    model = mr.resolve(str(model_id))
    if model is None:
        _list_models_and_exit(f"未识别的模型：{model_id}")

    if not subject:
        print("缺少主体：用 -s 指定，或提供 brief.json", file=sys.stderr)
        sys.exit(2)
    if not style_tokens:
        print("缺少风格：用 --style 指定，或提供 brief.json", file=sys.stderr)
        sys.exit(2)

    tokens = [t for t in style_tokens.replace("，", ",").split(",") if t.strip()]
    picks, missing = [], []
    for t in tokens:
        hit = resolve(t, styles)
        (picks.append(hit) if hit else missing.append(t.strip()))
    if missing:
        print(f"未找到风格：{'、'.join(missing)}。先用 find_style.py 查准确名称", file=sys.stderr)
        sys.exit(1)
    if len(picks) > 3:
        print("最多叠加 3 个风格，超过后互相稀释，建议删减", file=sys.stderr)
        sys.exit(2)

    lay = col = None
    if args.layout:
        lay = lr.resolve_layout(args.layout)
        if lay is None:
            print(f"未找到排版图型：{args.layout}。用 layout_registry.py --list 查看全部", file=sys.stderr)
            sys.exit(1)
        if not aspect:
            aspect = lay["aspects"][0]
    if args.color:
        col = lr.resolve_color(args.color)
        if col is None:
            print(f"未找到主题色：{args.color}。用 layout_registry.py --color 检索", file=sys.stderr)
            sys.exit(1)

    ratio, res = mr.aspect(model, aspect)
    if aspect and aspect not in (model.get("aspects") or {}):
        print(f"{model['label']} 未登记比例 {aspect}，已按最接近的 {ratio}（{res or '不指定像素'}）输出",
              file=sys.stderr)

    dims = [d.strip() for d in (args.dims or "color,light").replace("，", ",").split(",") if d.strip()]
    bad = [d for d in dims if d not in ORDER]
    if bad:
        print(f"未知维度：{bad}，可用：{ORDER}", file=sys.stderr)
        sys.exit(2)

    segs, notes = build(subject, picks, dims)

    subject_check = check_subject(subject, styles)
    warns = []
    for issue in subject_check["issues"]:
        level = "medium" if issue["tag"] in {"含风格名", "空泛评价词", "过短"} else "low"
        warns.append({"rule": f"主体·{issue['tag']}", "level": level,
                      "why": f"{issue['hit']}：{issue['why']}", "fix": issue["fix"]})
    for tip in subject_check["tips"]:
        warns.append({"rule": f"主体·{tip['tag']}", "level": "low",
                      "why": tip["why"], "fix": tip["fix"]})
    for i in range(len(picks)):
        for j in range(i + 1, len(picks)):
            warns.extend(conflicts(picks[i], picks[j]))
    for p in picks:
        if p["flags"]["broad"]:
            warns.append({"rule": "名称过宽", "level": "medium",
                          "why": f"「{p['name']}」本身不足以锁定画风，单独使用会得到该词的所有可能解释",
                          "fix": "再叠加一个具体风格，或在主体里写清材质、年代、场景"})
        if p["flags"]["living_artist"]:
            warns.append({"rule": "在世艺术家", "level": "high",
                          "why": f"「{p['name']}」指向在世创作者，直接以人名作风格指令在多数平台属高风险用法",
                          "fix": "改写成可观察特征（线条、上色、光影、题材），本条目的模板段已不含人名，可只用模板部分"})
    if text_in_image and not model["supports"].get("text_in_image"):
        warns.append({"rule": "图内文字", "level": "high",
                      "why": f"{model['label']} 不能可靠渲染文字，写进提示词通常得到乱码或忽略",
                      "fix": "换 Qwen-Image / MOSS-Image / FLUX，或出图后期加字"})
    if transparent and not model["supports"].get("transparent"):
        warns.append({"rule": "透明底", "level": "high",
                      "why": f"{model['label']} 不支持原生 RGBA 输出",
                      "fix": "用 Qwen-Image 2.1，或出图后抠图"})

    edit_ins = args.edit or str(_brief_get(brief, "edit.instruction") or "") if args.brief else args.edit
    edit_keep = args.preserve or str(_brief_get(brief, "edit.preserve") or "") if args.brief else args.preserve
    ref_rec = None
    if args.with_ref:
        rp = ROOT / "assets" / "reference-map.json"
        if rp.exists():
            ref_rec = json.loads(rp.read_text(encoding="utf-8")).get("by_id", {}).get(str(picks[0]["id"]))

    opts = {"text_in_image": text_in_image, "transparent": transparent,
            "with_ref": args.with_ref,
            "layout": ({"zh": lr.layout_clause(lay, "zh"), "en": lr.layout_clause(lay, "en")} if lay else None),
            "color": ({"zh": lr.color_clause(col, "zh"), "en": lr.color_clause(col, "en")} if col else None),
            "variant": {"variant": args.variant} if args.variant else {},
            "edit": {"instruction": edit_ins, "preserve": edit_keep}}
    if args.layout_json:
        lpath = Path(args.layout_json)
        if not lpath.exists():
            print(f"布局文件不存在：{lpath}", file=sys.stderr)
            sys.exit(2)
        objs = json.loads(lpath.read_text(encoding="utf-8"))
        opts["layout_objects"] = objs.get("objects", objs) if isinstance(objs, dict) else objs
        if model["renderer"] != "json_layout":
            print(f"{model['label']} 不使用 JSON 布局，--layout-json 已忽略", file=sys.stderr)
    neg_extra = "" if args.no_negative else args.negative
    detail = render_detail(model["id"], ratio, subject, segs, neg_extra, opts)

    en_map, detail_en, missing_en, subject_en = {}, None, [], ""
    if args.en_map:
        epath = Path(args.en_map)
        if not epath.exists():
            print(f"对照表不存在：{epath}", file=sys.stderr)
            sys.exit(2)
        raw = json.loads(epath.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("segments"), dict):
            en_map = raw["segments"]
            subject_en = str(raw.get("subject", "") or "")
        elif isinstance(raw, dict):
            en_map = {k: v for k, v in raw.items() if isinstance(v, str)}
            subject_en = en_map.pop("__subject__", "") or en_map.pop("subject", "")
        segs_en = []
        for seg in segs:
            en = en_map.get(seg["text"])
            if not en:
                missing_en.append(seg["text"])
            segs_en.append({"dim": seg["dim"], "text": en or seg["text"]})
        opts_en = dict(opts)
        edit_en = raw.get("edit") if isinstance(raw, dict) else None
        if isinstance(edit_en, dict):
            opts_en["edit"] = {"instruction": edit_en.get("instruction", ""),
                               "preserve": edit_en.get("preserve", "")}
        detail_en = render_detail(model["id"], ratio, args.subject_en or subject_en or subject,
                                  segs_en, neg_extra, opts_en, lang="en")

    payload = {
        "subject": subject,
        "styles": [{"code": p["code"], "name": p["name"], "name_en": p["name_en"]} for p in picks],
        "segments": segs,
        "model": detail["model"],
        "model_label": detail["model_label"],
        "renderer": detail["renderer"],
        "prompt": detail["prompt"],
        "negative": detail["negative"],
        "params": detail["params"],
        "aspect": detail["aspect"],
        "resolution": detail["resolution"],
        "adaptations": detail["adaptations"],
        "model_notes": detail["notes"],
        "translation_todo": detail["translation_todo"],
        "prompt_en": detail_en["prompt"] if detail_en else None,
        "en_missing": missing_en,
        "layout": ({"id": lay["id"], "name": lay["name"], "family": lay["family"]} if lay else None),
        "color": ({"id": col["id"], "name": col["name_zh"], "hex": col["hex"]} if col else None),
        "reference": ref_rec,
        "comfy": mr.comfy_lines(model),
        "license": mr.license_line(model),
        "overrides": notes,
        "subject_check": subject_check,
        "intake": intake_res,
        "warnings": warns,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        if args.strict and any(w["level"] == "high" for w in warns):
            sys.exit(3)
        return

    if args.bare:
        print(detail["prompt"])
        if detail_en:
            print()
            print(detail_en["prompt"])
        return

    if intake_res:
        mark = "通过" if intake_res["ok"] else "带缺口出稿（--force）"
        print(f"【需求完整性】{intake_res['score']} 分 · {mark}")
        for w in intake_res["warnings"]:
            print(f"  [i] {w}")
        print()

    print("【提示词 · 中文】")
    print(detail["prompt"])

    if detail_en:
        print("\n【提示词 · 英文】")
        print(detail_en["prompt"])
        total = len(segs)
        print(f"\n  （翻译覆盖 {total - len(missing_en)}/{total}"
              + ("，未译段仍为中文，请补齐" if missing_en else "") + "）")
    else:
        print("\n【提示词 · 英文】未生成 —— 交付前必须补上")
        print("  待译段（写入 en-map.json 的 segments 后，加 --en-map 重跑）：")
        for i, seg in enumerate(segs, 1):
            print(f"   {i}. {seg['text']}")

    if detail["negative"]:
        print("\n【负向词】")
        print(detail["negative"])
    if detail["params"]:
        print("\n【平台参数】")
        print(f"{detail['model_label']}：{detail['params']}")

    if lay:
        fam = next((f for f in lr.families() if f["code"] == lay["family"]), {})
        print("\n【版面】")
        print(f"  {lay['id']} {lay['name']}　{fam.get('name_zh', '')} · {lay['use']}　"
              f"首选画幅 {'/'.join(lay['aspects'])}　信息密度 {lay['density']}")
        print(f"  {lay['prompt_zh']}")
    if col:
        print("\n【配色】")
        print(f"  {col['id']} {col['name_zh']} / {col['name_en']}　{col['hex']}　"
              f"适合 {col['use']}　建议搭配 {col['pairs']}")
        print("  已覆盖风格原有的色彩段，其余段落不动。")

    if ref_rec:
        print("\n【参考图】")
        print(f"  {ref_rec['image']}　（来源：{ref_rec['source']}）")
        print("  用途：主风格的画风参考；不要把图里的主体/构图写进提示词。")

    comfy = mr.comfy_lines(model)
    if comfy:
        print("\n【ComfyUI 接法】")
        for line in comfy:
            print(f"  - {line}")

    lic = mr.license_line(model)
    if lic:
        print("\n【许可 / 商用】")
        print(f"  - {lic}")

    sc = subject_check
    flag = "" if sc["ok"] else "  ← 建议先改主体"
    print(f"\n【主体体检】{sc['score']} 分 / {sc['length']} 字{flag}")
    for issue in sc["issues"]:
        print(f"  [!] {issue['tag']}：{issue['hit']}")
        print(f"      → {issue['fix']}")
    for tip in sc["tips"]:
        print(f"  [i] {tip['tag']}：{tip['fix']}")

    print(f"\n【模型适配】{detail['model_label']}（renderer: {detail['renderer']}）")
    for a in detail["adaptations"]:
        print(f"  - {a}")
    en_ok = bool(detail_en) and not missing_en
    for n in detail["notes"]:
        if en_ok and "需先译为英文" in n:
            continue          # 英文版已生成，不再提示翻译
        print(f"  · {n}")

    print("\n【构成】")
    print(" + ".join(f"{p['name']}({p['code']})" for p in picks)
          + (f"；副风格只覆盖 {'/'.join(dim_label(d) for d in dims)}" if len(picks) > 1 else "；单一风格全段"))
    for n in notes:
        print(f"  - {n}")

    if warns:
        print("\n【注意】")
        for w in warns:
            print(f"  [{w['level']}] {w['rule']}：{w['why']}")
            print(f"     → {w['fix']}")
    if args.strict and any(w["level"] == "high" for w in warns):
        sys.exit(3)


if __name__ == "__main__":
    main()
