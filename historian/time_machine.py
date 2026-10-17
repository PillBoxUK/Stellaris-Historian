from __future__ import annotations

"""v0.0.74: read-only, archived-date empire observatory.

This is a time-indexed view of durable historical *evidence*, not a pretend
reconstruction of fields Historian never persisted in individual snapshots.
Never reads Ironman saves, never writes a schema or modifies existing records.
"""

from collections import Counter
from html import escape
import json
import os
from pathlib import Path
import re
import tempfile

from .db import Database
from .empire_archive import build_empire_archive_data
from .interactive_timeline import build_interactive_timeline_data

_DATE = re.compile(r"^\d{4,5}\.\d{2}\.\d{2}$")
_CATEGORIES = [
    ("empire", "Empire"), ("colonies", "Colonies"), ("leaders", "People"),
    ("navy", "Navy"), ("technology", "Technology"),
    ("contacts", "First contacts"), ("politics", "Government"),
    ("internal_council", "Internal Council"), ("federations", "Federations"),
    ("galactic", "Galactic Community"), ("diplomacy", "Diplomacy"),
    ("space", "Combat"), ("ground", "Ground forces"), ("science", "Science"),
]


def time_machine_path(db: Database, campaign_id: int) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist")
    return Path(str(campaign["archive_dir"])) / "Empire_Time_Machine.html"


def build_time_machine_data(db: Database, campaign_id: int) -> dict:
    archive = build_empire_archive_data(db, campaign_id)
    snapshots_by_date: dict[str, dict] = {}
    processed_snapshot_ids: set[int] = set()
    for s in db.all_snapshots(campaign_id):
        date = str(s["game_date"] or "")
        if not bool(s["processed"]) or not _DATE.fullmatch(date):
            continue
        processed_snapshot_ids.add(int(s["id"]))
        # Multiple processed saves on one in-game day are one calendar stop.
        # Prefer the latest retained snapshot, never invent another day.
        snapshots_by_date[date] = {"date": date, "file": str(s["archive_filename"] or ""), "id": int(s["id"])}
    stops = [snapshots_by_date[d] for d in sorted(snapshots_by_date)]

    # Reuse the same already-reviewed curated chronology as Interactive Timeline:
    # technology, space combat and First Contacts otherwise disappear from the
    # SQLite-only registry summary. Presentation caches are read-only and no
    # new domain parsing is triggered by this page.
    full_timeline = build_interactive_timeline_data(db, campaign_id)
    rows = []
    for e in full_timeline["events"]:
        if not _DATE.fullmatch(str(e.get("date") or "")):
            continue
        rows.append({
            "date": str(e["date"]), "category": str(e["group"]),
            "title": str(e.get("title") or e.get("kind") or "Recorded observation"),
            "body": str(e.get("body") or ""), "kind": str(e.get("kind") or ""),
            "confidence": str(e.get("confidence") or ""),
            "date_kind": str(e.get("date_kind") or "archive_observation"),
            "source": str(e.get("source") or ""),
            "visible": bool(e.get("visible")), "subject_id": str(e.get("subject_id") or ""),
            "subject_name": "",
        })
    rows.sort(key=lambda e: (e["date"], e["category"], e["title"]))
    political_by_date: dict[str, dict] = {}
    for row in db.politics_states(campaign_id):
        day = str(row["game_date"] or "")
        if day not in snapshots_by_date or int(row["snapshot_id"]) not in processed_snapshot_ids:
            continue  # No unprocessed or phantom observations, including same-date collisions
        try:
            original = json.loads(row["state_json"] or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(original, dict):
            continue
        relations = original.get("relations") or {}
        political_by_date[day] = {
            "date": day,
            "ruler": str(original.get("ruler_name") or "Not recovered"),
            "government": str(original.get("government_type") or "Not recovered"),
            "authority": str(original.get("authority") or "Not recovered"),
            "ethics": [str(x) for x in (original.get("ethics") or [])],
            "civics": [str(x) for x in (original.get("civics") or [])],
            "traditions": [str(x) for x in (original.get("traditions") or [])],
            "relation_count": len(relations) if isinstance(relations, dict) else 0,
            "contacts": [str(r.get("country_name") or "Unresolved")
                         for r in (relations.values() if isinstance(relations,dict) else [])
                         if isinstance(r, dict)][:80],
        }
    observed = Counter(e["category"] for e in rows if e["visible"])
    registry = {k: [
        # Never project 'latest population', 'latest ship count', 'latest role',
        # or final status backwards to a historical snapshot.
        {"name": r["name"], "id": r["id"], "first": r["first"], "last": r["last"],
         "baseline": bool(r["baseline"])}
        for r in archive["registry"][k]
    ] for k in ("people", "worlds", "fleets", "ships")}
    return {
        "version": "0.0.74", "campaign": archive["campaign"], "stops": stops,
        "events": rows, "registry": registry, "political_states": [political_by_date[d] for d in sorted(political_by_date)],
        "topics": [{"id": key, "title": name, "count": observed[key]} for key, name in _CATEGORIES],
        "methodology": (
            "Dates are processed archive snapshots. Timeline events also use reviewed cached presentation evidence and first-contact history. Registry spans mean first/last observed, NOT "
            "continuous proof of presence; an entity's current status and latest attributes are intentionally "
            "excluded. Events are durable SQLite/cached historian observations, not claims of exact occurrence unless the "
            "source specifically records an exact date. The Federation, Galactic Community, and ground "
            "combat categories show no claims without published save-derived records. No screenshots, "
            "manual annotations, raw Ironman parsing, or database writes."
        ),
    }


_STYLE = r"""
:root{color-scheme:dark;--back:#070d19;--mid:#0f1d30;--card:#14273d;--card2:#193149;--line:#35526a;--ink:#f5f1e9;--sub:#b4c9db;--gold:#edc887;--cyan:#79d7ee}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 70% -10%,#234261 0%,transparent 48%),radial-gradient(ellipse at 8% 45%,#19283f 0%,transparent 48%),var(--back);color:var(--ink);font:14px/1.5 Segoe UI,system-ui,sans-serif}button,input{font:inherit}button{cursor:pointer;border:1px solid #54718a;border-radius:7px;padding:9px 13px;background:#213d56;color:var(--ink)}button:hover{border-color:var(--gold)}button:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid var(--gold);outline-offset:2px}button:disabled{opacity:.45;cursor:default}a{color:var(--cyan)}.sr{position:absolute;width:1px;height:1px;clip:rect(0,0,0,0);overflow:hidden}
header{padding:24px clamp(18px,4vw,70px);border-bottom:1px solid #35536a;background:#0b1728cf;position:sticky;top:0;z-index:10;backdrop-filter:blur(12px)}.header-wrap{max-width:1650px;margin:auto;display:flex;align-items:center;justify-content:space-between;gap:22px;flex-wrap:wrap}h1{font:normal clamp(30px,3.2vw,54px)/1.05 Georgia,serif;margin:7px 0}small,.muted{color:var(--sub)}.eyebrow{color:var(--gold);text-transform:uppercase;letter-spacing:.22em;font-size:10px;font-weight:700}nav{display:flex;flex-wrap:wrap;gap:16px}
main{max-width:1650px;margin:auto;padding:24px clamp(14px,3vw,45px) 95px}.top-grid{display:grid;grid-template-columns:1.5fr 1fr;gap:14px}.panel{background:linear-gradient(135deg,#16283d,#0e1c2f);border:1px solid var(--line);border-radius:13px;padding:20px;margin-bottom:15px;box-shadow:0 12px 42px #0004}.panel h2{font:normal 26px Georgia,serif;margin:0 0 12px}.panel h3{font:normal 19px Georgia,serif;margin:0 0 9px}.date{font:normal clamp(32px,4vw,57px) Georgia,serif;color:var(--gold);letter-spacing:.025em}.control-row{display:flex;align-items:center;flex-wrap:wrap;gap:9px;margin:15px 0}.range{width:100%;accent-color:var(--gold);cursor:pointer;margin:12px 0}.scale{display:flex;justify-content:space-between;color:var(--sub);font-size:11px}.stat-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.stat{background:#0e2033;border:1px solid #3b5770;border-radius:9px;padding:13px;min-height:94px}.stat b{display:block;font:26px Georgia,serif;color:var(--gold);margin-bottom:4px}.stat span{font-size:12px;color:var(--sub)}.warning{border-left:3px solid var(--gold);background:#2a2b32;padding:12px 15px;font-size:12px;color:#f1dfba;margin-top:16px}
.grid{display:grid;grid-template-columns:350px minmax(0,1.1fr) minmax(280px,.8fr);gap:14px}.topics{display:flex;flex-direction:column;gap:7px}.topic{display:flex;align-items:center;justify-content:space-between;text-align:left;width:100%;background:#132940}.topic.sel{background:#37526b;border-color:var(--gold)}.topic:disabled{opacity:.55}.topic span{color:#a6cadd;font-size:12px}.events{max-height:620px;overflow-y:auto}.event{display:block;width:100%;margin:8px 0;text-align:left;padding:13px;background:var(--card2)}.event.active{border-color:var(--gold);background:#33485a}.event strong{font:17px Georgia,serif;display:block;margin:4px 0}.event small{color:var(--cyan)}.detail{position:sticky;top:145px;align-self:start}.detail p{line-height:1.65}.pill{display:inline-block;font-size:11px;color:#e5d4b7;background:#3a3840;border:1px solid #6b604f;border-radius:14px;padding:3px 9px;margin:0 5px 5px 0}.register{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px;max-height:380px;overflow:auto}.identity{background:#11263b;border:1px solid #344f66;padding:12px;border-radius:6px}.identity b{display:block}.identity small{font-size:11px}.subtle{color:var(--sub)}.empty{border:1px dashed #526a7f;padding:26px;border-radius:7px;color:var(--sub)}.search{background:#0b1a2d;color:var(--ink);padding:10px;border:1px solid #4e6d8a;border-radius:6px;max-width:100%;width:100%}.tools{display:flex;gap:9px;flex-wrap:wrap;margin:12px 0}.tools button.active{background:#365e78;border-color:var(--gold)}.foot{font-size:12px;color:var(--sub);margin-top:10px}
@media(max-width:1250px){.grid{grid-template-columns:250px 1fr}.detail{grid-column:2;position:static}.top-grid{grid-template-columns:1fr}}@media(max-width:700px){header{position:static}.grid{grid-template-columns:1fr}.detail{grid-column:auto}.stat-row{grid-template-columns:repeat(2,1fr)}.topics{display:grid;grid-template-columns:1fr 1fr}.panel{padding:15px}}
@media print{header,.topics,.control-row,.range,.tools{display:none!important}.panel{break-inside:avoid;box-shadow:none}.events{max-height:none}.grid{display:block}}
"""

_SCRIPT = r"""
'use strict';
const D=JSON.parse(document.getElementById('historical-data').textContent);
const $=id=>document.getElementById(id),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clean=x=>String(x??'').toLowerCase();
let step=Math.max(0,D.stops.length-1),category='all',selected=-1,query='',withTechnical=false,play=null;
const stops=D.stops;
function chosen(){return stops[step]||{date:'',file:''}}
function published(){return D.events.filter(e=>(withTechnical||e.visible)&&(!query||clean([e.title,e.body,e.date,e.kind,e.subject_name].join(' ')).includes(query)))}
function inPeriod(e){const year=Number(chosen().date.slice(0,4));return Number(e.date.slice(0,4))>=year-2&&e.date<=chosen().date}
function shown(){return published().filter(e=>inPeriod(e)&&(category==='all'||e.category===category)).sort((a,b)=>b.date.localeCompare(a.date))}
function stop(){if(play){clearInterval(play);play=null}$('play').textContent='▶ Play'}
function move(x){if(!stops.length)return;step=Math.min(stops.length-1,Math.max(0,x));selected=-1;render()}
function eventCard(e,i){return `<button type="button" class="event ${selected===i?'active':''}" data-e="${i}"><small>${esc(e.date)} · ${esc(e.category)}</small><strong>${esc(e.title)}</strong><span class="muted">${esc(e.body).slice(0,160)}</span></button>`}
function render(){const s=chosen();$('date').textContent=s.date||'No processed dates';$('source-file').textContent=s.file||'None';$('step').value=step;$('date-label').value=s.date;
 $('step-start').textContent=stops[0]?.date||'—';$('step-end').textContent=stops.at(-1)?.date||'—';$('where').textContent=`Archive observation ${stops.length?step+1:0} of ${stops.length}`;
 const past=published().filter(e=>e.date<=s.date),latest=past.slice(-1)[0];
 $('published-count').textContent=past.length;
 let roster={};for(const k of ['people','worlds','fleets','ships'])roster[k]=D.registry[k].filter(r=>r.first&&r.first<=s.date&&r.last>=s.date);
 for(const k of Object.keys(roster))$('count-'+k).textContent=roster[k].length;
 const topics=[{id:'all',title:'All evidence',count:past.length},...D.topics.map(t=>({id:t.id,title:t.title,count:past.filter(e=>e.category===t.id).length}))];
 $('topic-list').innerHTML=topics.map(t=>`<button class="topic ${category===t.id?'sel':''}" data-c="${esc(t.id)}"><b>${esc(t.title)}</b><span>${t.count}</span></button>`).join('');
 $('topic-list').querySelectorAll('[data-c]').forEach(b=>b.onclick=()=>{category=b.dataset.c;selected=-1;render()});
 const list=shown();$('event-count').textContent=`${list.length} matching observations in the selected year and preceding two years`;
 $('event-list').innerHTML=list.length?list.slice(0,250).map(eventCard).join(''):'<div class="empty">No published evidence in this period for this category. This does not establish that nothing happened.</div>';
 $('event-list').querySelectorAll('[data-e]').forEach(b=>b.onclick=()=>{selected=Number(b.dataset.e);renderDetail(list);$('detail').scrollIntoView({block:'nearest',behavior:'smooth'})});
 renderDetail(list);
 ['people','worlds','fleets','ships'].forEach(k=>{const arr=roster[k];$('registry-'+k).innerHTML=arr.slice(0,30).map(r=>`<div class="identity"><b>${esc(r.name)}</b><small>ID ${esc(r.id)} · observed ${esc(r.first)} – ${esc(r.last)}</small></div>`).join('')||'<p class="muted">No overlapping registry spans</p>';});
 $('registry-date').textContent=s.date;
 const politics=D.political_states.filter(p=>p.date<=s.date).at(-1);
 if(politics){$('gov-observed').textContent=politics.date===s.date?'Political state recorded at this archived date':`Last political state observed ${politics.date}; no later observation up to selection`;
   $('ruler').textContent=politics.ruler;$('government').textContent=politics.government;$('authority').textContent=politics.authority;
   $('ethics').textContent=politics.ethics.join(', ')||'Not recovered';$('civics').textContent=politics.civics.join(', ')||'Not recovered';
   $('traditions').textContent=String(politics.traditions.length);$('relations').textContent=String(politics.relation_count);
   $('contacts').textContent=politics.contacts.slice(0,14).join(' · ')||'None recovered';
 }else{$('gov-observed').textContent='No political state observed by selected date';for(const field of ['ruler','government','authority','ethics','civics','traditions','relations','contacts'])$(field).textContent='—';}
 $('politics-coverage').textContent=`${past.filter(e=>['diplomacy','politics','internal_council','contacts','federations','galactic'].includes(e.category)).length} recorded political or diplomatic observations by this date.`;
}
function renderDetail(rows){const e=rows[selected]||rows[0];if(!e){$('detail').innerHTML='<h2>Evidence dossier</h2><div class="empty">Select an event, or move to another archived date.</div>';return}
 $('detail').innerHTML=`<div class="eyebrow">Archive evidence dossier</div><h2>${esc(e.title)}</h2><span class="pill">${esc(e.date)}</span><span class="pill">${esc(e.category)}</span>${!e.visible?'<span class="pill">Technical / unpublished</span>':''}<p>${esc(e.body)||'No further description retained.'}</p><h3>Source and precision</h3><p class="subtle">${esc(e.source)} · ${esc(e.kind)}<br>Date evidence: ${esc(e.date_kind)}<br>Confidence: ${esc(e.confidence)}${e.subject_id?'<br>Linked subject: '+esc(e.subject_name||e.subject_id):''}</p><p class="foot">Dates marked first observed describe the archival observation, not necessarily the exact event day.</p>`;}
$('step').max=Math.max(0,stops.length-1);$('step').oninput=e=>move(Number(e.target.value));
$('first').onclick=()=>{stop();move(0)};$('prev').onclick=()=>{stop();move(step-1)};$('next').onclick=()=>{stop();move(step+1)};$('last').onclick=()=>{stop();move(stops.length-1)};
$('play').onclick=()=>{if(play){stop();return}if(step>=stops.length-1)move(0);$('play').textContent='❚❚ Pause';play=setInterval(()=>{if(step>=stops.length-1){stop();return}move(step+1)},850)};
$('date-go').onclick=()=>{const target=$('date-label').value.trim();if(!/^\d{4,5}\.\d{2}\.\d{2}$/.test(target))return;let n=stops.findIndex(s=>s.date>=target);if(n<0)n=stops.length-1;if(n>0&&stops[n].date>target)n--;stop();move(n)};
$('search').oninput=e=>{query=clean(e.target.value.trim());selected=-1;render()};$('technical').onchange=e=>{withTechnical=e.target.checked;selected=-1;render()};
$('save').onclick=()=>{const s=chosen();const body=JSON.stringify({campaign:D.campaign.name,archive_date:s.date,source_file:s.file,methodology:D.methodology,events:shown(),observed_registry_windows:Object.fromEntries(['people','worlds','fleets','ships'].map(k=>[k,D.registry[k].filter(r=>r.first<=s.date&&r.last>=s.date)]))},null,2);const b=new Blob([body],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=`Empire_Evidence_${s.date||'empty'}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
window.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA'].includes(document.activeElement?.tagName))return;if(e.key==='ArrowLeft')move(step-1);if(e.key==='ArrowRight')move(step+1)});
const initial=new URLSearchParams(location.search).get('date');if(initial&&/^\d{4,5}\.\d{2}\.\d{2}$/.test(initial)){let n=stops.findIndex(s=>s.date>=initial);step=n<0?Math.max(0,stops.length-1):Math.max(0,n-(stops[n].date>initial&&n>0?1:0))}
render();
"""

_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Empire Time Machine</title><style>__STYLE__</style>
<link rel="stylesheet" href="/static/historian-theme.css?v=087">
<script src="/static/historian-theme.js?v=087"></script>
</head><body>
<header><div class="header-wrap"><div><div class="eyebrow">Stellaris Historian · v0.0.75 · read-only record</div><h1>__EMPIRE__ — Time Machine</h1><small>Travel between actual processed archive dates · no invented history</small></div><nav><a href="/campaign">Campaign</a><a href="/timeline">Empire Timeline</a><a href="/timeline">Classic Timeline</a><a href="/scribes">Scribes Chronicle</a><a href="/empire-archive">Empire Archive</a></nav></div></header>
<main><div class="top-grid"><section class="panel"><div class="eyebrow">Historical observation deck</div><div class="date" id="date"></div><div class="muted" id="where"></div><div class="control-row"><button id="first">|◀ First</button><button id="prev">◀ Previous</button><button id="play">▶ Play</button><button id="next">Next ▶</button><button id="last">Last ▶|</button></div><input class="range" type="range" id="step" min="0" value="0" aria-label="Select archived snapshot"><div class="scale"><span id="step-start"></span><span id="step-end"></span></div><div class="control-row"><label for="date-label">Jump to</label><input class="search" style="width:145px" id="date-label" placeholder="2302.07.01"><button id="date-go">Go</button><button id="save">Export date dossier JSON</button></div><small>Archive source: <span id="source-file"></span></small></section>
<section class="panel"><div class="eyebrow">What the surviving record can establish</div><h2>Evidence at this date</h2><div class="stat-row"><div class="stat"><b id="count-people">—</b><span>Leader registry spans</span></div><div class="stat"><b id="count-worlds">—</b><span>World registry spans</span></div><div class="stat"><b id="count-fleets">—</b><span>Fleet registry spans</span></div><div class="stat"><b id="count-ships">—</b><span>Ship registry spans</span></div></div><p><b id="published-count"></b> dated evidence entries recorded by this point.</p><div class="warning">Counts refer to overlapping first/last-observed registry windows, <b>not confirmed exact entities at that save</b>. Latest ship counts, populations, traits and office holders are deliberately not projected into the past.</div></section></div>
<div class="grid"><section class="panel"><h2>Historical domains</h2><p class="muted">Click to filter the surrounding period.</p><div class="topics" id="topic-list"></div></section><section class="panel"><h2>Events around this date</h2><p class="muted" id="event-count"></p><div class="tools"><input id="search" class="search" type="search" placeholder="Search events or people…"><label><input id="technical" type="checkbox"> Include technical/unpublished</label></div><div class="events" id="event-list"></div></section><aside class="panel detail" id="detail" aria-live="polite"></aside></div>
<section class="panel"><div class="eyebrow">A second lens on the archive</div><h2>Diplomacy & galactic politics</h2><p id="gov-observed" class="eyebrow"></p>
<div class="stat-row" style="margin:18px 0"><div class="stat"><b style="font-size:20px" id="ruler">—</b><span>Recorded ruler</span></div><div class="stat"><b style="font-size:19px" id="government">—</b><span>Government type</span></div><div class="stat"><b id="relations">—</b><span>Retained relation records</span></div><div class="stat"><b id="traditions">—</b><span>Recorded traditions</span></div></div>
<p><b>Authority:</b> <span id="authority">—</span> · <b>Ethics:</b> <span id="ethics">—</span></p>
<p><b>Civics:</b> <span id="civics">—</span></p><p class="muted"><b>Known relation records:</b> <span id="contacts">—</span></p>
<p id="politics-coverage"></p><p class="muted">Government, internal Council agendas, first contacts, and diplomatic changes are separated from Federation and Galactic Community events. <b>No federation votes, senators or resolutions are inferred where the save parser has not recovered them.</b> Choose their domain above to inspect actual published events, if any.</p></section>
<section class="panel"><h2>Registry windows around <span id="registry-date"></span></h2><p class="muted">An interval between first and last sightings is not proof of continuous presence. These are discovery aids, not a reconstructed census.</p><h3>People</h3><div id="registry-people" class="register"></div><h3>Colonies</h3><div id="registry-worlds" class="register"></div><h3>Fleets</h3><div id="registry-fleets" class="register"></div><h3>Ships</h3><div id="registry-ships" class="register"></div></section>
<div class="foot">__METHODOLOGY__</div></main><script id="historical-data" type="application/json">__DATA__</script><script>__SCRIPT__</script></body></html>"""


def render_time_machine(db: Database, campaign_id: int) -> Path:
    data = build_time_machine_data(db, campaign_id)
    target = time_machine_path(db, campaign_id)
    # Render from validated JSON, encode HTML delimiters so script tags in save-derived names are inert.
    script_data = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    page = (_HTML.replace("__STYLE__", _STYLE).replace("__SCRIPT__", _SCRIPT)
            .replace("__EMPIRE__", escape(data["campaign"]["name"]))
            .replace("__METHODOLOGY__", escape(data["methodology"]))
            .replace("__DATA__", script_data))
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".time_machine_", suffix=".html", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
            file.write(page)
        os.replace(name, target)
    except BaseException:
        try: os.unlink(name)
        except OSError: pass
        raise
    return target
