#!/usr/bin/env python3
"""生成单文件风格画廊 assets/gallery.html：带参考图、可搜索、可筛选、可放大、离线可用。

图片来源：assets/dataset/images/{bucket}/{id}.webp（由 build_dataset.py 生成）。
若数据集不存在，脚本会提示先跑 build_dataset.py，而不是输出一堆坏图。

用法：
    python3 scripts/build_dataset.py     # 先准备图片
    python3 scripts/make_gallery.py      # 再生成画廊
退出码：0 成功 / 1 数据集缺失
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "styles-173.json"
MANIFEST = ROOT / "assets" / "dataset" / "manifest.jsonl"
OUT = ROOT / "assets" / "gallery.html"

CAT_ORDER = ["CN", "JP", "WR", "WE", "DG", "PH", "IL", "CO", "SB", "EX"]

HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>视觉美学风格库 · __COUNT__</title>
<style>
:root{--bg:#f7f6f3;--card:#fff;--ink:#1c1b19;--dim:#6f6a63;--line:#e3dfd8;--accent:#8a6d3b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",system-ui,sans-serif}
header{padding:26px 24px 14px;border-bottom:1px solid var(--line);background:var(--bg);
position:sticky;top:0;z-index:9}
h1{margin:0 0 3px;font-size:19px;font-weight:600;letter-spacing:.4px}
.sub{color:var(--dim);font-size:13px}
.bar{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
input{flex:1;min-width:220px;padding:9px 12px;border:1px solid var(--line);border-radius:8px;
background:var(--card);font-size:14px;outline:none}
input:focus{border-color:var(--accent)}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.tab{padding:5px 11px;border:1px solid var(--line);border-radius:999px;background:var(--card);
font-size:12.5px;cursor:pointer;color:var(--dim);white-space:nowrap}
.tab.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.sheet{display:none;padding:14px 24px 0}
.sheet.on{display:block}
.sheet img{width:100%;max-height:300px;object-fit:contain;object-position:left;
border:1px solid var(--line);border-radius:10px;background:#fff}
.sheet .cap{color:var(--dim);font-size:12px;margin-top:6px}
main{padding:18px 24px 64px;display:grid;gap:16px;
grid-template-columns:repeat(auto-fill,minmax(268px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;
cursor:pointer;transition:transform .12s ease,box-shadow .12s ease;display:flex;flex-direction:column}
.card:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(28,27,25,.09)}
.thumb{position:relative;width:100%;aspect-ratio:16/10;background:#efece7;overflow:hidden}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.badge{position:absolute;left:8px;top:8px;padding:2px 7px;border-radius:6px;
background:rgba(28,27,25,.72);color:#fff;font-size:11px;letter-spacing:.4px}
.body{padding:10px 12px 12px}
.name{font-size:14.5px;font-weight:600}
.en{color:var(--dim);font-size:12px;margin-top:1px}
.tpl{color:#4a463f;font-size:12.5px;margin-top:7px;line-height:1.5;
display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.empty{padding:60px;text-align:center;color:var(--dim);grid-column:1/-1;display:none}
#lb{position:fixed;inset:0;background:rgba(20,19,17,.86);display:none;z-index:50;
align-items:center;justify-content:center;padding:24px}
#lb.on{display:flex}
.panel{background:var(--card);border-radius:14px;max-width:1080px;width:100%;max-height:92vh;
overflow:auto;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(320px,.85fr)}
@media(max-width:860px){.panel{grid-template-columns:1fr}}
.panel .pic{background:#111;display:flex;align-items:center;justify-content:center}
.panel .pic img{max-width:100%;max-height:92vh;display:block}
.panel .info{padding:20px 22px 24px}
.panel h2{margin:0;font-size:18px}
.panel .code{color:var(--dim);font-size:12px;margin:2px 0 14px}
.panel .lbl{font-size:11.5px;color:var(--dim);letter-spacing:.6px;margin:14px 0 5px}
.panel pre{margin:0;background:#f4f1eb;border:1px solid var(--line);border-radius:8px;
padding:11px 12px;font-size:12.5px;line-height:1.6;white-space:pre-wrap;word-break:break-word;
font-family:ui-monospace,Menlo,Consolas,monospace}
.panel .chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chip{font-size:11.5px;color:var(--dim);border:1px solid var(--line);border-radius:999px;padding:2px 8px}
.acts{display:flex;gap:8px;margin-top:16px;flex-wrap:wrap}
button{padding:7px 14px;border:1px solid var(--line);background:var(--card);border-radius:8px;
font-size:13px;cursor:pointer;color:var(--ink)}
button.primary{background:var(--ink);color:#fff;border-color:var(--ink)}
button:disabled{opacity:.4;cursor:default}
footer{padding:22px 24px 40px;border-top:1px solid var(--line);color:var(--dim);font-size:12.5px;
display:flex;gap:14px;flex-wrap:wrap;align-items:center;justify-content:space-between}
footer b{color:var(--ink);font-weight:600}
</style></head><body>
<header>
  <h1>视觉美学风格库 · __COUNT__ 种</h1>
  <div class="sub">10 大类 / 编号即索引。点卡片看大图与完整提示词模板，← → 翻页，Esc 关闭。</div>
  <div class="bar"><input id="q" placeholder="搜风格名、编号、模板关键词，如「水墨」「CN-12」「留白」"></div>
  <div class="tabs" id="tabs"></div>
</header>
<div class="sheet" id="sheet"><img id="sheetImg" alt=""><div class="cap" id="sheetCap"></div></div>
<main id="list"></main>
<div class="empty" id="empty">没有匹配的条目</div>
<footer>
  <div><b>__SIGNATURE__</b></div>
  <div>© __YEAR__ · MIT + CC BY 4.0 · 可商用，需署名</div>
</footer>
<div id="lb"><div class="panel">
  <div class="pic"><img id="lbImg" alt=""></div>
  <div class="info">
    <h2 id="lbName"></h2>
    <div class="code" id="lbCode"></div>
    <div class="lbl">提示词模板</div>
    <pre id="lbTpl"></pre>
    <div class="lbl">七维特征</div>
    <div class="chips" id="lbChips"></div>
    <div class="acts">
      <button class="primary" id="copy">复制模板</button>
      <button id="prev">上一个</button><button id="next">下一个</button>
      <button id="close">关闭</button>
    </div>
  </div>
</div></div>
<script>
const DATA = __DATA__;
const SHEETS = __SHEETS__;
const list = document.getElementById('list');
const empty = document.getElementById('empty');
const tabs = document.getElementById('tabs');
const sheet = document.getElementById('sheet');
let cat = 'ALL', kw = '', view = [];

function tabsInit(){
  const cats = [['ALL','全部'], ...Object.keys(SHEETS).map(c=>[c, SHEETS[c].name])];
  cats.forEach(([c,label])=>{
    const b = document.createElement('div');
    b.className = 'tab' + (c===cat?' on':'');
    const n = c==='ALL' ? DATA.length : DATA.filter(d=>d.cat===c).length;
    b.textContent = label + ' ' + n;
    b.onclick = ()=>{ cat = c; [...tabs.children].forEach(x=>x.classList.remove('on')); b.classList.add('on'); render(); };
    tabs.appendChild(b);
  });
}

function esc(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function render(){
  const k = kw.trim().toLowerCase();
  view = DATA.filter(d=>{
    if (cat!=='ALL' && d.cat!==cat) return false;
    if (!k) return true;
    return (d.name+' '+d.en+' '+d.code+' '+d.tpl+' '+d.catName).toLowerCase().includes(k);
  });
  list.innerHTML = view.map((d,i)=>`
    <div class="card" data-i="${i}">
      <div class="thumb"><img loading="lazy" src="${d.img}" alt="${esc(d.name)}"><span class="badge">${d.code}</span></div>
      <div class="body">
        <div class="name">${esc(d.name)}</div>
        <div class="en">${esc(d.en)}</div>
        <div class="tpl">${esc(d.tpl)}</div>
      </div>
    </div>`).join('');
  empty.style.display = view.length ? 'none' : 'block';
  if (cat!=='ALL' && SHEETS[cat]) {
    document.getElementById('sheetImg').src = SHEETS[cat].img;
    document.getElementById('sheetCap').textContent = SHEETS[cat].name + ' · 该类拼版速览（顺序与清单一致）';
    sheet.classList.add('on');
  } else { sheet.classList.remove('on'); }
  [...list.children].forEach(el=>el.onclick = ()=>openLb(+el.dataset.i));
}

let cur = 0;
function openLb(i){
  cur = i; const d = view[i]; if(!d) return;
  document.getElementById('lbImg').src = d.img;
  document.getElementById('lbName').textContent = d.name;
  document.getElementById('lbCode').textContent = d.code + ' · #' + d.id + ' · ' + d.catName;
  document.getElementById('lbTpl').textContent = d.tpl;
  document.getElementById('lbChips').innerHTML = d.traits.map(t=>`<span class="chip">${esc(t)}</span>`).join('');
  document.getElementById('lb').classList.add('on');
  document.getElementById('prev').disabled = i<=0;
  document.getElementById('next').disabled = i>=view.length-1;
}
document.getElementById('close').onclick = ()=>document.getElementById('lb').classList.remove('on');
document.getElementById('prev').onclick = ()=>openLb(Math.max(0,cur-1));
document.getElementById('next').onclick = ()=>openLb(Math.min(view.length-1,cur+1));
document.getElementById('lb').onclick = e=>{ if(e.target.id==='lb') e.currentTarget.classList.remove('on'); };
function copyText(t, btn){
  const done = ()=>{ btn.textContent='已复制'; setTimeout(()=>btn.textContent='复制模板',1400); };
  if(navigator.clipboard && window.isSecureContext){ navigator.clipboard.writeText(t).then(done).catch(()=>fallback(t,done)); return; }
  fallback(t, done);
}
function fallback(t, done){
  const ta=document.createElement('textarea'); ta.value=t; ta.style.position='fixed'; ta.style.opacity='0';
  document.body.appendChild(ta); ta.select();
  try{ document.execCommand('copy'); done(); }catch(e){ alert('复制失败，请手动选中'); }
  ta.remove();
}
document.getElementById('copy').onclick = e=>copyText(document.getElementById('lbTpl').textContent, e.target);
document.getElementById('q').oninput = e=>{ kw = e.target.value; render(); };
document.addEventListener('keydown', e=>{
  const on = document.getElementById('lb').classList.contains('on');
  if (e.key==='Escape') document.getElementById('lb').classList.remove('on');
  if (on && e.key==='ArrowLeft') openLb(Math.max(0,cur-1));
  if (on && e.key==='ArrowRight') openLb(Math.min(view.length-1,cur+1));
});
tabsInit(); render();
</script></body></html>
"""


def main() -> None:
    if not MANIFEST.exists():
        print("数据集不存在，先跑：python3 scripts/build_dataset.py", file=sys.stderr)
        sys.exit(1)
    db = json.loads(DATA.read_text(encoding="utf-8"))
    cat_names = {c["code"]: c["name"] for c in db["categories"]}

    recs = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        recs.append({
            "id": r["id"], "code": r["code"], "name": r["name"], "en": r["name_en"],
            "cat": r["category"], "catName": cat_names.get(r["category"], r["category_name"]),
            "img": Path(r["image"]).relative_to("assets").as_posix(),
            "tpl": r["template"], "traits": r["traits"],
        })
    recs.sort(key=lambda x: x["id"])

    sheets = {}
    for code in CAT_ORDER:
        p = ROOT / "assets" / "dataset" / "_grid" / f"{code}.webp"
        if p.exists():
            sheets[code] = {"name": cat_names.get(code, code),
                            "img": p.relative_to(ROOT / "assets").as_posix()}

    auth = {}
    ap = ROOT / "assets" / "author.json"
    if ap.exists():
        auth = json.loads(ap.read_text(encoding="utf-8"))

    html = (HTML.replace("__DATA__", json.dumps(recs, ensure_ascii=False))
                .replace("__SHEETS__", json.dumps(sheets, ensure_ascii=False))
                .replace("__COUNT__", str(len(recs)))
                .replace("__SIGNATURE__", auth.get("signature", "作者"))
                .replace("__AUTHOR__", auth.get("name", "作者"))
                .replace("__ACCOUNT__", auth.get("account", ""))
                .replace("__YEAR__", str(auth.get("copyright", "© 2026"))[2:6] or "2026"))
    OUT.write_text(html, encoding="utf-8")
    print(f"已生成 {OUT.relative_to(ROOT)}（{len(recs)} 条 / {OUT.stat().st_size/1024:.0f} KB）")


if __name__ == "__main__":
    main()
