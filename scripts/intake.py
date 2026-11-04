#!/usr/bin/env python3
"""出稿前的需求采集与体检。

为什么要有这一步：173 条风格模板是常量，主体和参数是变量。
变量没锁定就组装，等于把「风格准不准」交给模型猜——最常见的结果是
风格对了但画面不是用户要的东西，或者参数在目标模型上根本不合法。

三种用法：
    # 1. 按目标模型打印该问的问题（给用户或给 agent 自己用）
    python3 scripts/intake.py --model flux --scene 电商主图

    # 2. 生成空白清单，填完再体检
    python3 scripts/intake.py --template --model moss -o brief.json
    python3 scripts/intake.py --check brief.json

    # 3. 从一句话需求预填，把仍缺的项标出来
    python3 scripts/intake.py --from-text "国潮风茶叶海报，用FLUX，3:4"

退出码：0 信息充分 / 1 信息不足 / 2 用法错误
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import model_registry as mr

SCENE_HINTS = {
    "电商主图": ("电商", "主图", "产品图", "详情页", "淘宝", "亚马逊"),
    "社交配图": ("社交", "小红书", "朋友圈", "公众号", "推文", "配图"),
    "海报/封面": ("海报", "封面", "poster", "banner", "头图"),
    "品牌物料": ("品牌", "物料", "KV", "campaign", "宣传"),
    "绘本/插画": ("绘本", "插画", "童书", "illustration"),
    "概念设计": ("概念", "设定", "原画", "concept", "场景设计"),
    "人像写真": ("人像", "写真", "肖像", "portrait"),
}
REQUIRED = ("subject.who", "subject.action", "subject.setting", "scene.type", "model")


def _get(brief: dict, path: str):
    cur = brief
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _set(brief: dict, path: str, value) -> None:
    cur = brief
    keys = path.split(".")
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def blank(model: dict | None = None) -> dict:
    return {
        "subject": {"who": "", "action": "", "setting": "", "detail": "",
                    "mood": "", "viewpoint": "", "twist": "", "metaphor": ""},
        "style": {"specified": "", "feeling": "", "candidates": []},
        "scene": {"type": "", "usage": "", "aspect": "", "text_in_image": "", "transparent": False},
        "model": (model or {}).get("id", ""),
        "params": {},
        "deliver": {"lang": "跟随模型默认", "negative": True},
        "_note": "只填确认过的信息；不确定就留空，intake.py --check 会告诉你还缺什么。",
    }


CREATIVE = ("subject.mood", "subject.viewpoint", "subject.twist", "subject.metaphor")
STYLE_KEYS = ("style.specified", "style.feeling", "style.candidates")


def _styles_db() -> list[dict]:
    import json
    return json.loads((Path(__file__).resolve().parent.parent / "assets" / "styles-173.json")
                      .read_text(encoding="utf-8"))["styles"]


def suggest_styles(text: str, n: int = 3) -> list[tuple[str, str, dict, list[str]]]:
    """按一段口语给三个方向：稳妥（同调）、邻类（换族不换媒介）、反差（换媒介）。

    打分用 IDF 加权：越少见的词权重越高，避免「克制」「安静」这类词把结果拉平。
    调性类（CO）不作为首选——它只调色，不构成完整画风。
    """
    import math
    import re
    text = (text or "").strip()
    if not text:
        return []
    toks = [x for x in re.split(r"[^\u4e00-\u9fa5A-Za-z0-9]+", text) if len(x) >= 2] or [text]
    db = _styles_db()

    # 文档频率 → IDF
    dfs = {}
    for tok in toks:
        dfs[tok] = sum(1 for s in db if tok in (s["name"] + s["category_name"] + s["sample"]
                                                + s["template"] + "".join(s["aliases"])))
    idf = {k: math.log((len(db) + 1) / (v + 1)) + 1 for k, v in dfs.items()}

    scored = []
    for s in db:
        # 调性类（CO）只调色、不构成画风：除非用户直接点了它的名字，否则不进候选
        named = s["name"] in text
        if s["category"] == "CO" and not named:
            continue
        hit, score = [], 0.0
        for w in toks:
            w_name = w in s["name"]
            w_cat = w in s["category_name"]
            w_alias = w in "".join(s["aliases"])
            w_body = w in s["sample"] or w in s["template"]
            if not (w_name or w_cat or w_alias or w_body):
                continue
            hit.append(w)
            score += idf[w] * (3 if w_name else 2 if w_alias else 1.5 if w_cat else 0.7)
        if not hit and not named:
            continue
        if named:
            score += 8
        scored.append((score, hit, s))
    if not scored:
        return []
    scored.sort(key=lambda x: -x[0])

    def take(pred, used):
        for sc, hit, s in scored:
            if s["id"] not in used and pred(s):
                return (sc, hit, s)
        return None

    out, used = [], set()
    first = take(lambda s: s["category"] != "CO", used) or scored[0]
    out.append(("稳妥", "同调，最贴你的描述", first[2], first[1]))
    used.add(first[2]["id"])

    near = take(lambda s: s["medium"] == first[2]["medium"] and s["category"] != first[2]["category"], used)
    if near is None:
        near = take(lambda s: s["category"] != first[2]["category"], used)
    if near:
        out.append(("邻类", "换风格族，成像方式不变，稳中求变", near[2], near[1]))
        used.add(near[2]["id"])

    far = take(lambda s: s["medium"] != first[2]["medium"]
               and s["category"] not in {first[2]["category"], near[2]["category"] if near else ""}, used)
    if far is None:
        far = take(lambda s: s["medium"] != first[2]["medium"], used)
    if far:
        out.append(("反差", "换媒介，冲击更强，也更容易翻车", far[2], far[1]))
    return out[:n]


def print_styles(text: str) -> None:
    hits = suggest_styles(text)
    if not hits:
        print(f"没有匹配「{text}」的风格。换更具体的词，或看画廊 assets/gallery.html 按大类选。", file=sys.stderr)
        sys.exit(1)
    def strong(s, hit):
        field = s["name"] + s["category_name"] + "".join(s["aliases"])
        return any(w in field for w in hit)

    if not any(strong(s, hit) for _, _, s, hit in hits):
        print("提示：你给的都是感受词，字面命中偏弱，下面三个未必真贴——")
        print("      更可靠的做法是打开 assets/gallery.html 看图选，或直接说一个风格名。\n")

    print(f"围绕「{text}」给三个方向，选一个，或说“换一批”：\n")
    for label, desc, s, hit in hits:
        brief = s["sample"].split("，")[0][:32]
        why = ("命中：" + "、".join(hit[:3])) if hit else "与描述最接近"
        print(f"[{label}] {s['code']} {s['name']}　（{s['category_name']}）")
        print(f"    {desc}")
        print(f"    画面：{brief}…")
        print(f"    {why}")
        print()
    print("定了就把编号传给 --style，如 --style CN-01；看全部：assets/gallery.html")


def questions(model: dict | None, scene: str) -> None:
    reg = mr.load()
    slots = {s["key"]: s for s in reg["intake_slots"]}
    print("请按顺序确认下面几项；确认完再出稿。\n")

    print("【必答】")
    for key in ("subject.who", "subject.action", "subject.setting", "scene.type", "model"):
        s = slots.get(key)
        if not s:
            continue
        opt = "  选项：" + " / ".join(s["options"]) if s.get("options") else ""
        print(f"- {s['label']}：{s['ask']}{opt}")
        print(f"    为什么问：{s['why']}")

    print("\n【风格怎么定】")
    print("- 有明确风格名就直说；没有就说 2–3 个感受词。")
    print("- 都没把握时给三个方向：`python3 scripts/intake.py --styles \"你的感受词\"`")
    print("    一个稳妥、一个反差、一个意外，每个都附画面描述，看完再选。")
    print("- 想看全部：打开 assets/gallery.html，按大类筛选看图。")

    print("\n【创意追问 · 挑 1–2 个问，不要一次全问】")
    for key in CREATIVE:
        s = slots.get(key)
        if not s:
            continue
        print(f"- {s['label']}：{s['ask']}")
        print(f"    为什么问：{s['why']}")

    print("\n【收尾（可给默认值）】")
    for key in ("scene.aspect", "scene.text_in_image", "deliver.lang", "subject.detail"):
        s = slots.get(key)
        if not s:
            continue
        print(f"- {s['label']}：{s['ask']}")

    if model:
        extras = [e for e in model.get("intake_extra", [])
                  if e.get("key") not in slots]
        if extras:
            print(f"\n【{model['label']} 专属参数】")
            for e in extras:
                opt = "  选项：" + " / ".join(e["options"]) if e.get("options") else ""
                dft = f"（默认：{e['default']}）" if e.get("default") else ""
                print(f"- {e['label']}：{e['ask']}{opt}{dft}")
    if scene:
        print(f"\n场景「{scene}」建议比例：{mr.default_aspect(scene)}（可按需改）")
    print("\n填好后：python3 scripts/intake.py --check brief.json")


def check(brief: dict) -> dict:
    reg = mr.load()
    missing, warns, errs = [], [], []
    score = 100

    for path in REQUIRED:
        v = _get(brief, path)
        if not (isinstance(v, str) and v.strip()):
            missing.append(path)
            score -= 15

    if not (_get(brief, "style.specified") or _get(brief, "style.feeling")):
        missing.append("style.specified|style.feeling")
        score -= 15

    model = mr.resolve(str(_get(brief, "model") or ""))
    if model is None and _get(brief, "model"):
        errs.append("未识别的模型「%s」，可选：%s" % (
            _get(brief, "model"), "、".join(m["label"] for m in mr.offered())))
        score -= 20
    elif model is not None and not model.get("offer", True):
        errs.append(f"「{model['label']}」是内部兜底档，请从 17 个可选模型里选一个")
        score -= 20
    elif model is not None and model.get("task") == "edit":
        if not (_get(brief, "edit.instruction") or "").strip():
            missing.append("edit.instruction")
            score -= 15

    who = (_get(brief, "subject.who") or "").strip()
    act = (_get(brief, "subject.action") or "").strip()
    if who and len(who) <= 3 and len(who + act) < 12:
        warns.append("主体信息量偏少：补一个动作或环境，否则模型会补成最俗套的样子")
        score -= 8

    aspect = (_get(brief, "scene.aspect") or "").strip()
    if model:
        if aspect:
            hit_ratio, res = mr.aspect(model, aspect)
            if hit_ratio != aspect:
                warns.append(f"{model['label']} 未登记比例 {aspect}，已回退到最接近的 {hit_ratio}")
                score -= 5
            if res and model["id"] in ("sdxl", "flux", "moss") and "x" in res:
                w, h = (int(x) for x in res.split("x"))
                if min(w, h) < 512:
                    errs.append(f"分辨率 {res} 低于该模型可用下限")
                    score -= 10
        else:
            warns.append(f"未给比例，出稿时按场景默认 {mr.default_aspect(_get(brief, 'scene.type') or '')}")
            score -= 3

    text = (_get(brief, "scene.text_in_image") or "").strip()
    if model and text and not model["supports"].get("text_in_image"):
        warns.append(f"{model['label']} 图内文字不可靠，建议改 Qwen-Image / MOSS-Image / FLUX，或后期加字")
        score -= 10
    if model and _get(brief, "scene.transparent") and not model["supports"].get("transparent"):
        errs.append(f"{model['label']} 不支持原生透明底（RGBA），需后期抠图或换 Qwen-Image 2.1")
        score -= 15

    if model:
        for e in model.get("intake_extra", []):
            if e.get("required") and not _get(brief, e["key"]):
                missing.append(e["key"])
                score -= 10

    lang = _get(brief, "deliver.lang") or "跟随模型默认"
    if model and lang == "跟随模型默认" and model.get("language") == "en":
        warns.append(f"{model['label']} 建议英文提示词，风格段需先翻译")
    return {"ok": not missing and not errs and score >= 85,
            "score": max(0, score), "missing": missing, "warnings": warns, "errors": errs,
            "model": model["id"] if model else None,
            "model_label": model["label"] if model else None,
            "suggested_aspect": mr.default_aspect(_get(brief, "scene.type") or "")}


def from_text(text: str, forced_model: str = "") -> dict:
    brief = blank()
    m = mr.resolve(forced_model) if forced_model else None
    if m is None:
        for cand in mr.models():
            for a in [cand["id"], *cand["aliases"]]:
                if re.sub(r"[\s_\-]+", "", a.lower()) in re.sub(r"[\s_\-]+", "", text.lower()):
                    m = cand
                    break
            if m:
                break
    if m:
        brief["model"] = m["id"]
    for scene, kws in SCENE_HINTS.items():
        if any(k in text for k in kws):
            brief["scene"]["type"] = scene
            break
    am = re.search(r"(\d+)\s*[:：]\s*(\d+)", text)
    if am:
        brief["scene"]["aspect"] = f"{am.group(1)}:{am.group(2)}"
    if "透明" in text or "rgba" in text.lower():
        brief["scene"]["transparent"] = True
    q = re.search(r"[「“\"]([^」”\"]{2,20})[」”\"]", text)
    if q:
        brief["scene"]["text_in_image"] = q.group(1)
    # 主体：按标点切分，剔除模型名/比例/场景词/文字需求，剩下的才可能是主体草稿
    scene_kws = [k for kws in SCENE_HINTS.values() for k in kws]
    keep = []
    for tk in re.split(r"[，,、；;。]+", text):
        tk = tk.strip()
        if not tk:
            continue
        flat = re.sub(r"[\s_\-]+", "", tk.lower())
        if m and any(re.sub(r"[\s_\-]+", "", a.lower()) in flat for a in [m["id"], *m["aliases"]]):
            continue
        if re.fullmatch(r"\d+\s*[:：]\s*\d+", tk):
            continue
        if any(k in tk for k in ("要写", "写上", "文字", "标题", "加字")):
            continue
        for k in scene_kws:
            tk = tk.replace(k, "")
        tk = re.sub(r"^(用|要|做一张|做|生成|帮我|请|来一张|画)", "", tk).strip()
        if tk:
            keep.append(tk)
    if keep:
        brief["subject"]["who"] = "，".join(keep)
        brief["_note"] = "subject.who 是从原句机械截取的草稿，需人工改成「谁+动作+环境」再体检。"
    return brief


def main() -> None:
    ap = argparse.ArgumentParser(description="出稿前的需求采集与体检")
    ap.add_argument("--questions", action="store_true", help="打印该问的问题")
    ap.add_argument("--model", default="", help="目标模型")
    ap.add_argument("--scene", default="", help="使用场景")
    ap.add_argument("--template", action="store_true", help="输出空白清单")
    ap.add_argument("--from-text", dest="from_text", help="从一句话需求预填")
    ap.add_argument("--check", metavar="FILE", help="体检已填写的清单")
    ap.add_argument("--styles", help="按感受词给三个风格候选（稳妥/反差/意外）")
    ap.add_argument("-o", "--out", default="", help="写入文件")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    a = ap.parse_args()

    if a.styles:
        print_styles(a.styles)
        return

    if a.check:
        p = Path(a.check)
        if not p.exists():
            print(f"文件不存在：{p}", file=sys.stderr)
            sys.exit(2)
        brief = json.loads(p.read_text(encoding="utf-8"))
        res = check(brief)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            print(f"模型：{res['model_label'] or '未确定'}")
            print(f"充分度：{res['score']} 分  {'通过' if res['ok'] else '不足，先补信息再出稿'}")
            if res["missing"]:
                print("缺必填项：")
                for k in res["missing"]:
                    print(f"  [ ] {k}")
            for e in res["errors"]:
                print(f"  [ERR] {e}")
            for w in res["warnings"]:
                print(f"  [i] {w}")
        sys.exit(0 if res["ok"] else 1)

    if a.from_text:
        brief = from_text(a.from_text, a.model)
        out = json.dumps(brief, ensure_ascii=False, indent=1)
        if a.out:
            Path(a.out).write_text(out, encoding="utf-8")
            print(f"已写入 {a.out}")
        else:
            print(out)
        return

    if a.template:
        m = mr.resolve(a.model) if a.model else None
        brief = blank(m)
        if m:
            for e in m.get("intake_extra", []):
                if e.get("default"):
                    _set(brief, e["key"], e["default"])
        if a.scene:
            brief["scene"]["type"] = a.scene
            brief["scene"]["aspect"] = mr.default_aspect(a.scene)
        out = json.dumps(brief, ensure_ascii=False, indent=1)
        if a.out:
            Path(a.out).write_text(out, encoding="utf-8")
            print(f"已写入 {a.out}")
        else:
            print(out)
        return

    m = mr.resolve(a.model) if a.model else None
    questions(m, a.scene)


if __name__ == "__main__":
    main()
