#!/usr/bin/env python3
"""把「主体 + 已选风格段」渲染成目标模型的提示词语法。

四种渲染器对应四类语法体系：
  tag            SDXL 系：逗号标签 + 权重 + 独立负向 + 像素尺寸
  prose          FLUX / Krea 2 / Z-Image：自然语句，不加权重
  json_layout    MOSS-Image：自然语言为主，可选 JSON 布局
  cn_structured  Qwen / 即梦 / 通用：中文结构化长句

新增模型时：先看能否复用现有渲染器（改 models.json 即可）；
确实需要新语法，才在这里加函数并登记到 RENDERERS。
"""
from __future__ import annotations

import json
import re

import model_registry as mr

CJK = re.compile(r"[\u4e00-\u9fa5]")
DIM_CN = {"style": "风格", "color": "色彩", "composition": "构图",
          "texture": "质感", "light": "光影", "quality": "画质", "mood": "情绪"}


def order_segments(segs: list[dict], model: dict) -> list[dict]:
    """按目标模型的语法偏好排序，未登记维度保持原相对顺序追加在末尾。"""
    order = model.get("segment_order") or list(mr.DIMS)
    rank = {d: i for i, d in enumerate(order)}
    return sorted(segs, key=lambda s: rank.get(s["dim"], len(order)))


def _join(segs: list[dict], sep: str) -> str:
    seen, out = set(), []
    for s in segs:
        if s["text"] in seen:
            continue
        seen.add(s["text"])
        out.append(s["text"])
    return sep.join(out)


def _needs_translation(model: dict, text: str) -> bool:
    return model.get("language") == "en" and bool(CJK.search(text))


def _length_note(model: dict, prompt: str) -> str:
    """按档案预算提示长度，上限只从 model_registry.budget() 取，不再读 syntax.max_words。

    这里只出提示行、不改正文：写长句有时是有意的，改动应由人决定。
    """
    b = mr.budget(model) or {}
    mode = b.get("enforce", "none")
    if mode == "none":
        return ""
    zh_b, en_b = b.get("zh") or {}, b.get("en") or {}
    zh = len(CJK.findall(prompt))
    words = len(re.findall(r"[A-Za-z][A-Za-z'\-]*", prompt))
    zh_max, en_max = zh_b.get("max"), en_b.get("max")
    over = []
    if zh and zh_max and zh > zh_max:
        over.append(f"中文 {zh}/{zh_max} 字")
    if words and en_max and words > en_max:
        over.append(f"英文 {words}/{en_max} 词")
    if not over:
        return ""
    return f"提示词超出 {model['label']} 预算（{'、'.join(over)}），建议删解释性从句"


def _text_clause(text: str, model: dict, lang: str = "zh") -> str:
    if not text:
        return ""
    if lang == "en":
        return f'The image contains the readable text "{text}", with clear placement and hierarchy'
    if model["id"] == "qwen-image":
        return f"画面中出现文字「{text}」，排版清晰可读，位置与层级明确"
    if model["id"] == "moss":
        return f"画面中出现文字「{text}」"
    if model["id"] == "flux":
        return f'画面中出现文字 "{text}"，位置居中，字体清晰'
    return f"画面中出现文字「{text}」"


def render(model: dict, subject: str, segs: list[dict], aspect: str,
           negative_extra: str = "", opts: dict | None = None, lang: str = "zh") -> dict:
    opts = opts or {}
    segs = [dict(s) for s in order_segments(segs, model)]
    col = opts.get("color") or {}
    if col:
        tint = col.get("en" if lang == "en" else "zh")
        if tint:
            segs = [({"dim": s["dim"], "text": tint} if s["dim"] == "color" else s) for s in segs]
    renderer = model["renderer"]
    sep = ", " if (renderer == "tag" or lang == "en") else "，"
    end = "." if lang == "en" else "。"
    gap = " " if lang == "en" else ""
    ratio, res = mr.aspect(model, aspect)
    params = mr.param_line(model, ratio, opts.get("variant"))
    adaptations: list[str] = []
    notes: list[str] = []

    body = _join(segs, sep)
    tail = _text_clause(opts.get("text_in_image", ""), model, lang)
    neg_mode = (model.get("negative") or {}).get("mode", "separate")
    neg_default = (model.get("negative") or {}).get("default", "")
    negative = ""
    prompt = ""

    if renderer == "tag":
        prompt = f"{subject}, {body}"
        if tail:
            notes.append(f"{model['label']} 不擅长渲染文字，图内文字建议后期加")
        negative = ", ".join(x for x in [neg_default, negative_extra] if x)
        adaptations.append("按标签语法组织：逗号分隔、主体前置")
        adaptations.append(f"负向词走独立输入框（{len([x for x in negative.split(',') if x.strip()])} 项）")
        if neg_mode == "separate":
            notes.append("负向词越多越稀释注意力，保持在 8 项以内")
    elif renderer == "prose":
        parts = [subject] + [s["text"] for s in segs if not s.get("skip")]
        prompt = sep.join([p for p in parts if p]) + end
        if tail:
            prompt += gap + tail + end
        if neg_mode == "inline" and negative_extra:
            prompt += (f"Avoid: {negative_extra}。" if lang == "en" else f"避免出现：{negative_extra}。")
        elif neg_mode == "flag":
            no_list = "，".join([x for x in [neg_default, negative_extra] if x])
            params = (params + f" --no {no_list}").strip()
        elif neg_mode == "minimal" and negative_extra:
            notes.append("Krea 2 的负向会削弱画质，建议改为正向陈述")
        adaptations.append("改写为自然语句：不加权重、不堆质量词")
        if neg_mode in ("ignored", "none"):
            adaptations.append("该模型对负向词基本无效，负向要求已转为正向陈述")
        notes.append("权重语法会被当成普通文字，别用 (x:1.2)")
    elif renderer == "json_layout":
        if opts.get("layout_objects"):
            layout = build_layout(model, subject, segs, opts["layout_objects"], res or "1024x1024")
            prompt = json.dumps(layout, ensure_ascii=False, indent=1)
            adaptations.append("输出 JSON 布局：summary + items（含 bbox）")
        else:
            prompt = sep.join([subject] + [s["text"] for s in segs]) + end
            if tail:
                prompt += gap + tail + end
            adaptations.append("自然语言短句；需要精确排版时再切 JSON 布局")
        negative = ", ".join(x for x in [neg_default, negative_extra] if x)
        notes.append("出图尺寸须为 16 的倍数；布局精度依赖 SFT 权重")
    else:  # cn_structured
        prompt = sep.join([subject] + [s["text"] for s in segs]) + end
        if tail:
            prompt += gap + tail + end
        if opts.get("transparent"):
            prompt += "透明背景，主体边缘干净，输出带 alpha 通道。"
            adaptations.append("已追加透明底指令（RGBA）")
        if neg_mode == "inline" and negative_extra:
            prompt += f"避免出现：{negative_extra}。"
            adaptations.append("负向要求以「避免：」并入正向句尾")
        elif neg_mode == "separate":
            negative = ", ".join(x for x in [neg_default, negative_extra] if x)
        adaptations.append("中文结构化长句：主体 → 风格 → 构图 → 光影 → 细节")

    if renderer != "tag":
        low = f"{ratio}" if not res else res
        params = f"{low} · " + params if params and res not in params else params

    lay = opts.get("layout") or {}
    if lay:
        clause = lay.get("en" if lang == "en" else "zh")
        if clause:
            prompt = prompt.rstrip("。. ")
            prompt += ("。" if lang == "zh" else ". ")
            prompt += (f"版面：{clause}。" if lang == "zh" else f"Layout: {clause}.")

    if opts.get("with_ref"):
        if lang == "en":
            prompt += (" Use the attached image only as a style reference for linework, "
                       "brushwork, medium, palette and light; do not carry over its subject, "
                       "composition, setting or text.")
        else:
            prompt += "参考图仅用于提取画风（线条、笔触、媒介、色彩与光影），不要沿用图中的主体、构图、场景与文字。"

    edit = opts.get("edit") or {}
    if edit.get("instruction") and model.get("task") in ("edit", "both"):
        keep = edit.get("preserve", "").strip()
        ins = edit["instruction"].strip()
        if lang == "en":
            prefix = f"Using image 1 as input, {ins}"
            if keep:
                prefix += f", keeping {keep} unchanged"
        else:
            prefix = f"以图1为输入，{ins}"
            if keep:
                prefix += f"，保持{keep}不变"
        prompt = prefix + end + (" " if lang == "en" else "") + prompt
        adaptations.append("按编辑模型组织：先给改图指令，再给风格约束")

    todo = [] if lang == "en" else [s["text"] for s in segs if _needs_translation(model, s["text"])]
    if todo:
        notes.append(f"{model['label']} 以英文为佳：以上 {len(todo)} 段风格描述需先译为英文再投喂")

    ln = _length_note(model, prompt)
    if ln:
        notes.append(ln)

    for extra_note in (model.get("notes") or [])[:3]:
        if extra_note not in notes:
            notes.append(extra_note)

    return {
        "model": model["id"],
        "model_label": model["label"],
        "renderer": renderer,
        "language": model.get("language"),
        "prompt": prompt,
        "negative": negative,
        "params": params,
        "aspect": ratio,
        "resolution": res,
        "adaptations": adaptations,
        "notes": notes,
        "translation_todo": todo,
        "variant": opts.get("variant") or {},
    }


def build_layout(model: dict, subject: str, segs: list[dict], objects: list[dict],
                 res: str) -> dict:
    """生成 MOSS-Image 的 JSON 布局。

    objects: [{"label": "...", "caption": "...", "text": "...", "bbox": [y1,x1,y2,x2]}]
    bbox 采用 yxyx、以画布中心为原点的绝对像素；未给 bbox 时按顺序均分画布。
    """
    w, h = (int(x) for x in res.lower().split("x"))
    style = "，".join(s["text"] for s in segs)
    items, n = [], max(len(objects), 1)
    for i, ob in enumerate(objects):
        bbox = ob.get("bbox")
        if not bbox:
            bw = int(w / n)
            x1 = -w // 2 + i * bw
            bbox = [-h // 2, x1, h // 2, x1 + bw]
        item = {
            "label": ob.get("label", ""),
            "caption": ob.get("caption") or ob.get("label", ""),
            "bbox": bbox,
        }
        if ob.get("text"):
            item["text"] = ob["text"]
        items.append(item)
    return {
        "summary": {"caption": f"{subject}。{style}"},
        "items": items,
        "bbox_coord_space": "abs_centralized",
        "canvas": {"width": w, "height": h},
    }


RENDERERS = {
    "tag": render,
    "prose": render,
    "json_layout": render,
    "cn_structured": render,
}


def render_with(model_token: str, subject: str, segs: list[dict], aspect: str = "",
                negative_extra: str = "", opts: dict | None = None) -> dict:
    m = mr.resolve(model_token) or mr.resolve("generic")
    return render(m, subject, segs, aspect, negative_extra, opts)
