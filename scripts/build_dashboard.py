"""Generate a single self-contained HTML dashboard from a batch's classified.csv.
All rows are embedded inline (no server, no external calls, no data leaves the
machine). Open the .html by double-clicking. Run:

    python -m scripts.build_dashboard family-offices
"""
import csv, json, os, re, sys, datetime

from config import batch_paths
from scripts.research import _clean_url  # first real domain out of a citation blob

CATEGORY_ORDER = [
    "RE", "BOTH (primary: RE)", "FUND ADMIN-GP", "FUND ADMIN-LP", "BOTH (primary: FUND)",
]
CATEGORY_COLORS = {  # {name: (light, dark)} — validated CVD-safe set
    "RE":                  ("#2a78d6", "#3987e5"),
    "BOTH (primary: RE)":  ("#1baf7a", "#199e70"),
    "FUND ADMIN-GP":       ("#eda100", "#c98500"),
    "FUND ADMIN-LP":       ("#4a3aa7", "#9085e9"),
    "BOTH (primary: FUND)":("#eb6834", "#d95926"),
}
REL_ORDER = ["IN ICP", "REVIEW", "UNVERIFIED", "NOT IN ICP"]

_EMPTY = {"", "n/a", "nan", "undisclosed", "none"}


def _clean(v):
    return "" if v is None else str(v).strip()


def _email(v):
    v = _clean(v)
    if v.lower() in _EMPTY or "@" not in v:
        return ""
    return v


def _url(v):
    v = _clean(v)
    if v.lower() in _EMPTY:
        return ""
    return v if v.startswith("http") else "https://" + v


def _load(csv_path):
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "c":  _clean(r.get("company")),
                "n":  _clean(r.get("contact_name")),
                "h":  _clean(r.get("hq")),
                "l":  _url(r.get("linkedin")),
                "w":  _url(_clean_url(_clean(r.get("website")))),
                "e":  _email(r.get("email")),
                "r":  _clean(r.get("Relevance")) or "UNVERIFIED",
                "cat":_clean(r.get("Category")),
                "p":  _clean(r.get("Category Primary")),
                "ev": _clean(r.get("Evidence")),
            })
    return rows


def build(batch_name):
    bp = batch_paths(batch_name)
    rows = _load(bp["output_csv"] if os.path.exists(bp["output_csv"]) else bp["ledger"])
    out_path = os.path.join(os.path.dirname(bp["ledger"]), "dashboard.html")

    payload = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    cat_colors = json.dumps(CATEGORY_COLORS, ensure_ascii=False)
    title = batch_name.replace("-", " ").title()
    stamp = datetime.date.today().isoformat()

    html = _TEMPLATE
    html = html.replace("__TITLE__", title)
    html = html.replace("__STAMP__", stamp)
    html = html.replace("__TOTAL__", str(len(rows)))
    html = html.replace("__CAT_ORDER__", json.dumps(CATEGORY_ORDER))
    html = html.replace("__REL_ORDER__", json.dumps(REL_ORDER))
    html = html.replace("__CAT_COLORS__", cat_colors)
    html = html.replace("/*__DATA__*/[]", payload)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {len(rows)} rows -> {out_path}")
    print(f"Open it by double-clicking, or: start {out_path}")
    return out_path


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — ICP Classification</title>
<style>
:root {
  --plane:#f9f9f7; --surface:#ffffff; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --hair:#e1e0d9; --ring:rgba(11,11,11,0.10); --shadow:0 1px 3px rgba(11,11,11,.08),0 1px 2px rgba(11,11,11,.04);
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b; --review:#4a72b0;
  --good-bg:rgba(12,163,12,.10); --warn-bg:rgba(214,150,0,.14); --crit-bg:rgba(208,59,59,.10); --review-bg:rgba(74,114,176,.12);
  --accent:#2a78d6;
}
:root[data-theme="dark"] {
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
  --hair:#2c2c2a; --ring:rgba(255,255,255,0.10); --shadow:none;
  --good:#0ca30c; --warn:#fab219; --crit:#e05a5a; --review:#7aa0d8;
  --good-bg:rgba(12,163,12,.16); --warn-bg:rgba(250,178,25,.14); --crit-bg:rgba(224,90,90,.14); --review-bg:rgba(122,160,216,.16);
  --accent:#3987e5;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --plane:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
    --hair:#2c2c2a; --ring:rgba(255,255,255,0.10); --shadow:none;
    --crit:#e05a5a; --review:#7aa0d8;
    --good-bg:rgba(12,163,12,.16); --warn-bg:rgba(250,178,25,.14); --crit-bg:rgba(224,90,90,.14); --review-bg:rgba(122,160,216,.16);
    --accent:#3987e5;
  }
}
* { box-sizing:border-box; }
html,body { margin:0; padding:0; }
body {
  background:var(--plane); color:var(--ink);
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased;
}
.wrap { max-width:1280px; margin:0 auto; padding:28px 22px 80px; }
header { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; flex-wrap:wrap; }
h1 { font-size:23px; font-weight:650; margin:0 0 2px; letter-spacing:-.01em; }
.sub { color:var(--ink2); font-size:13.5px; }
.themebtn {
  border:1px solid var(--hair); background:var(--surface); color:var(--ink2);
  border-radius:9px; padding:7px 12px; cursor:pointer; font:inherit; font-size:13px;
}
.themebtn:hover { border-color:var(--muted); }

/* KPI tiles */
.kpis { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin:22px 0; }
.kpi {
  background:var(--surface); border:1px solid var(--hair); border-radius:13px; padding:14px 16px;
  cursor:pointer; box-shadow:var(--shadow); transition:border-color .12s, transform .06s; position:relative;
}
.kpi:hover { border-color:var(--muted); }
.kpi.active { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent); }
.kpi .v { font-size:27px; font-weight:680; letter-spacing:-.02em; line-height:1; }
.kpi .k { font-size:12.5px; color:var(--ink2); margin-top:7px; display:flex; align-items:center; gap:6px; }
.kpi .pct { font-size:11.5px; color:var(--muted); margin-top:3px; }
.dot { width:9px; height:9px; border-radius:50%; flex:none; }

/* category chart */
.panel { background:var(--surface); border:1px solid var(--hair); border-radius:13px; padding:18px 20px; box-shadow:var(--shadow); margin-bottom:22px; }
.panel h2 { font-size:13px; font-weight:600; color:var(--ink2); margin:0 0 15px; text-transform:uppercase; letter-spacing:.05em; }
.bars { display:flex; flex-direction:column; gap:9px; }
.barrow { display:grid; grid-template-columns:158px 1fr 52px; align-items:center; gap:12px; cursor:pointer; }
.barrow .lbl { font-size:13px; color:var(--ink); text-align:right; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.bartrack { height:22px; background:transparent; position:relative; }
.bar { height:22px; border-radius:4px; min-width:3px; transition:width .3s ease, opacity .12s; }
.barrow .cnt { font-size:13px; font-weight:600; color:var(--ink); font-variant-numeric:tabular-nums; }
.barrow:hover .bar { opacity:.82; }
.barrow.dim { opacity:.4; }

/* controls */
.controls { display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:14px; }
.pills { display:flex; gap:6px; flex-wrap:wrap; }
.pill {
  border:1px solid var(--hair); background:var(--surface); color:var(--ink2);
  border-radius:999px; padding:6px 13px; cursor:pointer; font:inherit; font-size:13px; display:flex; align-items:center; gap:6px;
}
.pill:hover { border-color:var(--muted); }
.pill.on { background:var(--ink); color:var(--surface); border-color:var(--ink); }
.pill.on .dot { box-shadow:0 0 0 2px var(--surface); }
.search { flex:1; min-width:200px; position:relative; }
.search input {
  width:100%; border:1px solid var(--hair); background:var(--surface); color:var(--ink);
  border-radius:10px; padding:9px 12px 9px 34px; font:inherit; font-size:14px;
}
.search input:focus { outline:none; border-color:var(--accent); }
.search svg { position:absolute; left:11px; top:50%; transform:translateY(-50%); color:var(--muted); }
.exportbtn { border:1px solid var(--hair); background:var(--surface); color:var(--ink2); border-radius:10px; padding:9px 14px; cursor:pointer; font:inherit; font-size:13px; }
.exportbtn:hover { border-color:var(--muted); }
.countline { font-size:13px; color:var(--ink2); margin-bottom:10px; }
.countline b { color:var(--ink); }

/* table */
.tablewrap { background:var(--surface); border:1px solid var(--hair); border-radius:13px; box-shadow:var(--shadow); overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:13.5px; }
thead th {
  position:sticky; top:0; background:var(--surface); text-align:left; font-weight:600; color:var(--ink2);
  padding:12px 14px; border-bottom:1px solid var(--hair); white-space:nowrap; cursor:pointer; user-select:none; z-index:1;
}
thead th.nosort { cursor:default; }
thead th .arr { color:var(--muted); font-size:10px; margin-left:3px; }
tbody td { padding:11px 14px; border-bottom:1px solid var(--hair); vertical-align:top; }
tbody tr:last-child td { border-bottom:none; }
tbody tr:hover { background:color-mix(in srgb, var(--accent) 5%, var(--surface)); }
.co { font-weight:580; color:var(--ink); }
.contact { color:var(--muted); font-size:12px; margin-top:2px; }
.hq { color:var(--ink2); white-space:nowrap; }
.badge { display:inline-flex; align-items:center; gap:6px; padding:3px 9px; border-radius:7px; font-size:12px; font-weight:600; white-space:nowrap; }
.b-in { background:var(--good-bg); color:var(--good); }
.b-rev { background:var(--review-bg); color:var(--review); }
.b-unv { background:var(--warn-bg); color:#b17d00; }
:root[data-theme="dark"] .b-unv { color:var(--warn); }
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]) .b-unv { color:var(--warn); } }
.b-not { background:var(--crit-bg); color:var(--crit); }
.cat { display:inline-flex; align-items:center; gap:7px; white-space:nowrap; }
.ev { color:var(--ink2); max-width:520px; }
.links { display:flex; gap:8px; white-space:nowrap; }
.links a { color:var(--muted); display:inline-flex; }
.links a:hover { color:var(--accent); }
.empty { padding:60px 20px; text-align:center; color:var(--muted); }

/* tooltip */
#tip { position:fixed; pointer-events:none; background:var(--ink); color:var(--surface); padding:7px 10px; border-radius:8px; font-size:12.5px; opacity:0; transition:opacity .1s; z-index:50; box-shadow:0 4px 14px rgba(0,0,0,.25); }

@media (max-width:820px) {
  .kpis { grid-template-columns:repeat(2,1fr); }
  .barrow { grid-template-columns:120px 1fr 44px; }
  .ev { max-width:none; }
}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>__TITLE__ — ICP Classification</h1>
      <div class="sub">__TOTAL__ leads classified · RE / Fund-Admin gate · generated __STAMP__</div>
    </div>
    <button class="themebtn" id="theme">◐ Theme</button>
  </header>

  <div class="kpis" id="kpis"></div>

  <div class="panel">
    <h2>Category breakdown — IN ICP</h2>
    <div class="bars" id="bars"></div>
  </div>

  <div class="controls">
    <div class="pills" id="relpills"></div>
    <div class="pills" id="catpills"></div>
  </div>
  <div class="controls">
    <div class="search">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
      <input id="q" type="search" placeholder="Search company, contact, HQ, or evidence…">
    </div>
    <button class="exportbtn" id="export">↓ Export CSV</button>
  </div>

  <div class="countline" id="count"></div>
  <div class="tablewrap">
    <table>
      <thead><tr>
        <th data-sort="c">Company <span class="arr"></span></th>
        <th data-sort="h">HQ <span class="arr"></span></th>
        <th data-sort="r">Relevance <span class="arr"></span></th>
        <th data-sort="cat">Category <span class="arr"></span></th>
        <th class="nosort">Evidence</th>
        <th class="nosort">Links</th>
      </tr></thead>
      <tbody id="tbody"></tbody>
    </table>
    <div class="empty" id="empty" style="display:none">No leads match these filters.</div>
  </div>
</div>
<div id="tip"></div>

<script>
const DATA = /*__DATA__*/[];
const CAT_ORDER = __CAT_ORDER__;
const REL_ORDER = __REL_ORDER__;
const CAT_COLORS = __CAT_COLORS__;

const isDark = () => {
  const t = document.documentElement.getAttribute('data-theme');
  if (t) return t === 'dark';
  return matchMedia('(prefers-color-scheme: dark)').matches;
};
const catColor = (c) => { const p = CAT_COLORS[c]; return p ? (isDark()? p[1] : p[0]) : 'var(--muted)'; };

const REL_CLASS = {"IN ICP":"b-in","REVIEW":"b-rev","UNVERIFIED":"b-unv","NOT IN ICP":"b-not"};
const REL_VAR   = {"IN ICP":"--good","REVIEW":"--review","UNVERIFIED":"--warn","NOT IN ICP":"--crit"};

let state = { rel:null, cat:null, q:"", sort:"c", dir:1 };

const norm = s => (s||"").toLowerCase();
function filtered() {
  let rows = DATA.slice();
  if (state.rel) rows = rows.filter(r => r.r === state.rel);
  if (state.cat) rows = rows.filter(r => r.cat === state.cat);
  if (state.q) { const q = norm(state.q); rows = rows.filter(r =>
    norm(r.c).includes(q) || norm(r.n).includes(q) || norm(r.h).includes(q) || norm(r.ev).includes(q)); }
  const k = state.sort;
  rows.sort((a,b) => { const x=norm(a[k]), y=norm(b[k]); return x<y? -1*state.dir : x>y? 1*state.dir : 0; });
  return rows;
}

/* KPIs */
function renderKpis() {
  const el = document.getElementById('kpis');
  const total = DATA.length;
  const counts = {}; REL_ORDER.forEach(r => counts[r]=0);
  DATA.forEach(r => counts[r.r] = (counts[r.r]||0)+1);
  const tiles = [{k:"Total", v:total, key:null, varc:"--ink"}].concat(
    REL_ORDER.map(r => ({k:r, v:counts[r]||0, key:r, varc:REL_VAR[r]})));
  el.innerHTML = tiles.map(t => `
    <div class="kpi ${state.rel===t.key && t.key!==null?'active':''}" data-rel="${t.key===null?'':t.key}">
      <div class="v">${t.v.toLocaleString()}</div>
      <div class="k">${t.key?`<span class="dot" style="background:var(${t.varc})"></span>`:''}${t.k}</div>
      <div class="pct">${t.key? Math.round(t.v/total*100)+'% of total':'&nbsp;'}</div>
    </div>`).join('');
  el.querySelectorAll('.kpi').forEach(k => k.onclick = () => {
    const r = k.dataset.rel || null;
    state.rel = (state.rel===r)? null : r; state.cat=null; renderAll();
  });
}

/* category bars */
function renderBars() {
  const el = document.getElementById('bars');
  const icp = DATA.filter(r => r.r==="IN ICP");
  const counts = {}; CAT_ORDER.forEach(c => counts[c]=0);
  icp.forEach(r => { if (counts[r.cat]!==undefined) counts[r.cat]++; });
  const max = Math.max(1, ...CAT_ORDER.map(c => counts[c]));
  el.innerHTML = CAT_ORDER.map(c => {
    const n = counts[c], pct = Math.round(n/max*100);
    const dim = state.cat && state.cat!==c ? 'dim' : '';
    return `<div class="barrow ${dim}" data-cat="${c.replace(/"/g,'&quot;')}" data-n="${n}">
      <div class="lbl">${c}</div>
      <div class="bartrack"><div class="bar" style="width:${pct}%;background:${catColor(c)}"></div></div>
      <div class="cnt">${n}</div>
    </div>`;
  }).join('');
  el.querySelectorAll('.barrow').forEach(row => {
    row.onclick = () => { const c=row.dataset.cat; state.cat=(state.cat===c)?null:c; if(state.cat) state.rel="IN ICP"; renderAll(); };
    row.onmousemove = (e) => showTip(e, `${row.dataset.cat}: ${row.dataset.n} of ${icp.length} IN ICP (${Math.round(row.dataset.n/icp.length*100)}%)`);
    row.onmouseleave = hideTip;
  });
}

/* relevance + category pills */
function renderPills() {
  const rel = document.getElementById('relpills');
  rel.innerHTML = `<button class="pill ${!state.rel?'on':''}" data-rel="">All relevance</button>` +
    REL_ORDER.map(r => `<button class="pill ${state.rel===r?'on':''}" data-rel="${r}">
      <span class="dot" style="background:var(${REL_VAR[r]})"></span>${r}</button>`).join('');
  rel.querySelectorAll('.pill').forEach(p => p.onclick = () => { state.rel=p.dataset.rel||null; state.cat=null; renderAll(); });

  const cat = document.getElementById('catpills');
  cat.innerHTML = `<button class="pill ${!state.cat?'on':''}" data-cat="">All categories</button>` +
    CAT_ORDER.map(c => `<button class="pill ${state.cat===c?'on':''}" data-cat="${c.replace(/"/g,'&quot;')}">
      <span class="dot" style="background:${catColor(c)}"></span>${c}</button>`).join('');
  cat.querySelectorAll('.pill').forEach(p => p.onclick = () => { state.cat=p.dataset.cat||null; if(state.cat) state.rel="IN ICP"; renderAll(); });
}

/* table */
function esc(s){ return (s||"").replace(/[&<>"]/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m])); }
function renderTable() {
  const rows = filtered();
  const tb = document.getElementById('tbody');
  document.getElementById('empty').style.display = rows.length? 'none':'block';
  document.getElementById('count').innerHTML = `Showing <b>${rows.length.toLocaleString()}</b> of ${DATA.length.toLocaleString()} leads`;
  const liIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M4.98 3.5A2.5 2.5 0 1 0 5 8.5a2.5 2.5 0 0 0 0-5zM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21H19v-5.5c0-1.3-.02-3-1.85-3-1.85 0-2.13 1.44-2.13 2.9V21H9z"/></svg>`;
  const webIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/></svg>`;
  const mailIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>`;
  tb.innerHTML = rows.map(r => {
    const links = [
      r.l? `<a href="${esc(r.l)}" target="_blank" rel="noopener" title="LinkedIn">${liIcon}</a>`:'',
      r.w? `<a href="${esc(r.w)}" target="_blank" rel="noopener" title="Website">${webIcon}</a>`:'',
      r.e? `<a href="mailto:${esc(r.e)}" title="${esc(r.e)}">${mailIcon}</a>`:'',
    ].join('');
    const cat = r.cat? `<span class="cat"><span class="dot" style="background:${catColor(r.cat)}"></span>${esc(r.cat)}</span>` : '<span style="color:var(--muted)">—</span>';
    return `<tr>
      <td><div class="co">${esc(r.c)}</div>${r.n?`<div class="contact">${esc(r.n)}</div>`:''}</td>
      <td class="hq">${esc(r.h)||'—'}</td>
      <td><span class="badge ${REL_CLASS[r.r]||''}">${esc(r.r)}</span></td>
      <td>${cat}</td>
      <td class="ev">${esc(r.ev)}</td>
      <td><div class="links">${links||'<span style="color:var(--muted)">—</span>'}</div></td>
    </tr>`;
  }).join('');
  document.querySelectorAll('thead th[data-sort]').forEach(th => {
    const k = th.dataset.sort;
    th.querySelector('.arr').textContent = state.sort===k? (state.dir>0?'▲':'▼') : '';
  });
}

function renderAll(){ renderKpis(); renderBars(); renderPills(); renderTable(); }

/* interactions */
document.getElementById('q').addEventListener('input', e => { state.q=e.target.value; renderTable(); });
document.querySelectorAll('thead th[data-sort]').forEach(th => th.onclick = () => {
  const k = th.dataset.sort;
  if (state.sort===k) state.dir*=-1; else { state.sort=k; state.dir=1; }
  renderTable();
});
const tip = document.getElementById('tip');
function showTip(e,t){ tip.textContent=t; tip.style.opacity=1; tip.style.left=(e.clientX+14)+'px'; tip.style.top=(e.clientY+14)+'px'; }
function hideTip(){ tip.style.opacity=0; }

document.getElementById('export').onclick = () => {
  const rows = filtered();
  const cols = [["c","Company"],["n","Contact"],["h","HQ"],["r","Relevance"],["cat","Category"],["p","Category Primary"],["ev","Evidence"],["l","LinkedIn"],["w","Website"],["e","Email"]];
  const q = s => '"'+String(s||"").replace(/"/g,'""')+'"';
  const csv = [cols.map(c=>c[1]).join(",")].concat(rows.map(r => cols.map(c=>q(r[c[0]])).join(","))).join("\r\n");
  const blob = new Blob(["﻿"+csv], {type:"text/csv;charset=utf-8"});
  const a = document.createElement("a"); a.href=URL.createObjectURL(blob);
  a.download = "icp_filtered_"+rows.length+".csv"; a.click();
};

const themeBtn = document.getElementById('theme');
themeBtn.onclick = () => {
  const cur = document.documentElement.getAttribute('data-theme');
  const next = cur==='dark'?'light': cur==='light'?'dark' : (matchMedia('(prefers-color-scheme: dark)').matches?'light':'dark');
  document.documentElement.setAttribute('data-theme', next);
  renderAll();
};

renderAll();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "family-offices")
