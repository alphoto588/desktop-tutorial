#!/usr/bin/env python3
"""模型档案的唯一读写入口：加载、校验、别名解析、比例换算。

所有脚本都通过本模块读 assets/models.json，不要在别处硬编码模型名单。
新增模型只需改 JSON；只有当出现全新语法时，才在 model_render.py 加渲染器。

用法（作为库）：
    import model_registry as mr
    reg = mr.load()
    m = mr.resolve("MoS")            # → MOSS-Image 档案
    mr.aspect(m, "3:4")              # → ("3:4", "896x1152")

命令行自检：
    python3 scripts/model_registry.py --list
    python3 scripts/model_registry.py --validate
退出码：0 正常 / 1 校验失败
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "models.json"

DIMS = ("style", "color", "composition", "texture", "light", "quality", "mood")
RENDERERS = ("tag", "prose", "json_layout", "cn_structured")
REQUIRED = ("id", "label", "family", "renderer", "aliases", "language", "syntax",
            "segment_order", "negative", "params", "aspects", "supports", "notes",
            "budget")

UNITS = ("char", "word")
# max：只查上限；both：上下限都查；none：长度不作判据（标签式 / JSON 布局）
ENFORCE = ("max", "both", "none")
# official：官方文档明确给出（FLUX.2-klein 50–150 词）；note：沿用库内既有口径（Qwen 800 字）；
# heuristic：按语感档位推定，未实测——留这个值是为了让后来人能分辨「实测」与「推断」
SOURCES = ("official", "note", "heuristic")
_CACHE: dict | None = None


def load() -> dict:
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.loads(DATA.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise SystemExit(f"模型档案缺失：{DATA}")
        except json.JSONDecodeError as exc:
            raise SystemExit(f"模型档案损坏：{exc}")
    return _CACHE


def models() -> list[dict]:
    return load()["models"]


def get(mid: str) -> dict | None:
    mid = mid.strip().lower()
    return next((m for m in models() if m["id"].lower() == mid), None)


def _norm(s: str) -> str:
    """归一化：去空格、下划线、连字符、点，便于匹配 FLUX.2-klein-base-4B 这类写法。"""
    return re.sub(r"[\s_\-\.]+", "", s.lower())


def resolve(token: str) -> dict | None:
    """按 id / 别名 / 显示名 / 家族 解析模型，容忍大小写与空格。"""
    t = (token or "").strip().lower()
    if not t:
        return None
    t_compact = _norm(t)
    for m in models():
        if t == m["id"].lower():
            return m
    for m in models():
        for a in m["aliases"]:
            a2 = _norm(a)
            if t_compact == a2:
                return m
    for m in models():
        if t_compact in (_norm(m["label"]), _norm(m["family"])):
            return m
    # 最后做包含匹配，用于 "flux-dev" → flux、"qwen-image-2.1" → qwen-image
    hits = [m for m in models()
            if any(t_compact.startswith(a2) or a2 in t_compact
                   for a2 in [_norm(a) for a in m["aliases"]])]
    if len(hits) == 1:
        return hits[0]
    hits = [m for m in hits if t_compact.startswith(m["id"].replace("-", ""))]
    return hits[0] if len(hits) == 1 else None


def aspect(model: dict, ratio: str) -> tuple[str, str]:
    """返回 (比例, 该模型下的合法分辨率)。未登记比例时回退到最接近的一项。"""
    ratio = (ratio or "").strip()
    table = model.get("aspects") or {}
    if not table:
        return ratio, ""
    if ratio in table:
        return ratio, table[ratio]
    if not ratio:
        for k in ("1:1", "3:4", "16:9"):
            if k in table:
                return k, table[k]
        k = next(iter(table))
        return k, table[k]

    def val(s: str) -> float:
        try:
            a, b = s.split(":")
            return float(a) / float(b)
        except Exception:
            return 1.0

    want = val(ratio)
    best = min(table, key=lambda k: abs(val(k) - want))
    return best, table[best]


def default_aspect(scene: str) -> str:
    """按使用场景给一个默认比例，避免让用户为空值纠结。"""
    s = (scene or "").lower()
    if any(k in s for k in ("海报", "封面", "poster", "cover", "手机", "social", "社交")):
        return "3:4"
    if any(k in s for k in ("banner", "横幅", "视频", "16:9")):
        return "16:9"
    if any(k in s for k in ("绘本", "插画", "picture")):
        return "4:3"
    return "1:1"


def param_line(model: dict, ratio: str, variant: dict | None = None) -> str:
    """生成给人看的参数行，不虚构未记录的字段。"""
    _, res = aspect(model, ratio)
    p = model.get("params", {})
    if model.get("family") == "midjourney":
        bits = []
        if ratio:
            bits.append(f"--ar {ratio}")
        bits.append("--style raw")
        return " · ".join(bits)
    bits = []
    if res:
        bits.append(res)
    elif ratio:
        bits.append(ratio)
    if p.get("steps"):
        bits.append(f"steps {p['steps']}")
    if p.get("cfg") is not None:
        if model.get("family") == "z-image" and not p["cfg"]:
            bits.append("guidance 0")
        else:
            bits.append(f"CFG {p['cfg']}")
    for key in ("sampler", "scheduler"):
        if p.get(key):
            bits.append(f"{key} {p[key]}")
    if p.get("shift"):
        bits.append(f"shift {p['shift']}")
    if variant:
        bits += [f"{k}: {v}" for k, v in variant.items() if v]
    return " · ".join(bits)


def offered() -> list[dict]:
    """可让用户选择的模型（generic 这类内部兜底不出现）。"""
    return [m for m in models() if m.get("offer", True)]


def is_edit(model: dict) -> bool:
    return model.get("task") == "edit"


def budget(model: dict | str | None, lang: str | None = None) -> dict | None:
    """预算的唯一读入口。传模型档案或模型名，返回该语言的预算（含上下限与 enforce）。

    lang 省略时返回整条 budget（含 zh / en / enforce / source），由调用方按需取用。
    没有 budget 字段时返回 None——不要在这里编默认值，缺字段应由 validate() 报错。
    """
    m = resolve(model) if isinstance(model, str) else model
    if not m:
        return None
    b = m.get("budget")
    if not b:
        return None
    if lang in ("zh", "en"):
        got = b.get(lang)
        if not got:
            return None
        return {**got, "enforce": b.get("enforce", "max"), "source": b.get("source")}
    return b


def budget_line(model: dict) -> str:
    """给人看的预算行：中文按字、英文按词，enforce 决定口吻（上限 / 区间 / 不计）。"""
    b = budget(model)
    if not b:
        return ""
    zh, en = b.get("zh") or {}, b.get("en") or {}
    mode = b.get("enforce", "max")
    zh_s = f"{zh.get('min')}–{zh.get('max')} 字" if mode == "both" else f"≤{zh.get('max')} 字"
    en_s = f"{en.get('min')}–{en.get('max')} 词" if mode == "both" else f"≤{en.get('max')} 词"
    if mode == "none":
        return "该模型按长度不设硬性判据（标签式 / JSON 布局）"
    return f"中文{zh_s} / 英文{en_s}（{b.get('source', 'heuristic')}）"


def comfy_lines(model: dict) -> list[str]:
    """ComfyUI 接法：工作流、尺寸约束、负向接法、坑位。没有则返回空列表。"""
    c = model.get("comfyui") or {}
    out = []
    if c.get("workflow"):
        out.append(f"工作流：{c['workflow']}")
    if c.get("size"):
        out.append(f"尺寸：{c['size']}")
    if c.get("negative"):
        out.append(f"负向接法：{c['negative']}")
    for n in c.get("notes", [])[:3]:
        out.append(f"注意：{n}")
    return out


def license_line(model: dict) -> str:
    lic = model.get("license")
    if not lic:
        return ""
    warn = ""
    low = lic.lower()
    if "授权" in lic:
        warn = ""                       # 许可本身已写明需授权，不再重复
    elif "research" in low or "非商用" in lic or "非商业" in lic:
        warn = " —— 商用前必须取得授权"
    return f"{lic}{warn}"


def _budget_errors(m: dict) -> list[str]:
    """预算字段自检：结构、单位、区间、enforce 枚举与 renderer 是否对得上。

    两个上限是最常见的坑：改了 budget 忘了改 syntax.max_words，脚本就会按旧值提示。
    这里断言两者一致（或干脆只留 budget），不让第二套上限活下来。
    """
    mid = m.get("id", "?")
    out: list[str] = []
    if "budget" not in m:
        return out                      # 缺字段已由 REQUIRED 报过，不重复
    b = m.get("budget")
    if not isinstance(b, dict):
        return [f"{mid} budget 类型不是对象"]
    for lang, unit in (("zh", "char"), ("en", "word")):
        part = b.get(lang)
        if not isinstance(part, dict):
            out.append(f"{mid} budget.{lang} 缺失或不是对象")
            continue
        u = part.get("unit")
        if u not in UNITS:
            out.append(f"{mid} budget.{lang}.unit 非法：{u}（应为 {'/'.join(UNITS)}）")
        elif u != unit:
            out.append(f"{mid} budget.{lang}.unit 应为 {unit}，实际 {u}")
        lo, hi = part.get("min"), part.get("max")
        for name, v in (("min", lo), ("max", hi)):
            if not isinstance(v, int) or isinstance(v, bool):
                out.append(f"{mid} budget.{lang}.{name} 必须是整数")
        if isinstance(lo, int) and isinstance(hi, int):
            if hi <= 0:
                out.append(f"{mid} budget.{lang}.max 必须大于 0")
            if lo < 0 or lo >= hi:
                out.append(f"{mid} budget.{lang} 区间不成立：min={lo} max={hi}")
    enf = b.get("enforce")
    if enf not in ENFORCE:
        out.append(f"{mid} budget.enforce 非法：{enf}（应为 {'/'.join(ENFORCE)}）")
    elif m.get("renderer") in ("json_layout", "tag") and enf != "none":
        out.append(f"{mid} renderer={m.get('renderer')} 不以长度为准，budget.enforce 应为 none，实际 {enf}")
    if b.get("source") not in SOURCES:
        out.append(f"{mid} budget.source 非法：{b.get('source')}（应为 {'/'.join(SOURCES)}）")
    mw = (m.get("syntax") or {}).get("max_words")
    en_max = (b.get("en") or {}).get("max")
    if mw is not None and mw != en_max:
        out.append(f"{mid} syntax.max_words={mw} 与 budget.en.max={en_max} 不一致（上限只留一处，删掉 max_words）")
    return out


def validate(verbose: bool = True) -> list[str]:
    errs: list[str] = []
    seen_ids: dict[str, str] = {}
    seen_alias: dict[str, str] = {}
    reg = load()
    for k in ("schema_version", "models", "renderers", "intake_slots"):
        if k not in reg:
            errs.append(f"顶层缺字段 {k}")
    if sorted(reg.get("renderers", [])) != sorted(RENDERERS):
        errs.append(f"renderers 声明与代码不一致：{reg.get('renderers')}")

    for m in reg.get("models", []):
        mid = m.get("id", "?")
        for f in REQUIRED:
            if f not in m:
                errs.append(f"{mid} 缺字段 {f}")
        if mid in seen_ids:
            errs.append(f"模型 id 重复：{mid}")
        seen_ids[mid] = mid
        if m.get("renderer") not in RENDERERS:
            errs.append(f"{mid} 的 renderer 未登记：{m.get('renderer')}")
        for a in m.get("aliases", []):
            key = re.sub(r"[\s_\-]+", "", a.lower())
            if key in seen_alias and seen_alias[key] != mid:
                errs.append(f"别名「{a}」被 {seen_alias[key]} 与 {mid} 共用")
            seen_alias[key] = mid
        bad = [d for d in m.get("segment_order", []) if d not in DIMS]
        if bad:
            errs.append(f"{mid} segment_order 含未知维度 {bad}")
        missing = [d for d in DIMS if d not in m.get("segment_order", [])]
        if missing:
            errs.append(f"{mid} segment_order 漏维度 {missing}")
        for ratio, res in (m.get("aspects") or {}).items():
            if not re.match(r"^\d+:\d+$", ratio):
                errs.append(f"{mid} 比例键非法：{ratio}")
            if res and not re.match(r"^\d+x\d+$", res):
                errs.append(f"{mid} 分辨率格式非法：{res}")
        for k in ("steps", "cfg", "native"):
            v = m.get("params", {}).get(k)
            if v is not None and not isinstance(v, (int, float)):
                errs.append(f"{mid} params.{k} 必须是数字")
        errs.extend(_budget_errors(m))

    for slot in reg.get("intake_slots", []):
        for f in ("key", "label", "required", "ask", "why"):
            if f not in slot:
                errs.append(f"intake_slots 缺字段 {f}：{slot.get('key', '?')}")

    if verbose:
        print(f"模型 {len(reg.get('models', []))} 个 / 采集槽位 {len(reg.get('intake_slots', []))} 个 / 渲染器 {len(RENDERERS)} 种")
        print(f"错误 {len(errs)}")
        for e in errs:
            print(f"  [ERR] {e}")
    return errs


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="模型档案自检")
    ap.add_argument("--list", action="store_true", help="列出全部模型")
    ap.add_argument("--validate", action="store_true", help="结构校验")
    a = ap.parse_args()
    if a.list:
        print(f"{'#':>3} {'id':26}{'task':6}{'renderer':14}label")
        for i, m in enumerate(offered(), 1):
            print(f"{i:>3} {m['id']:26}{m.get('task','t2i'):6}{m['renderer']:14}{m['label']}")
        return
    errs = validate()
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
