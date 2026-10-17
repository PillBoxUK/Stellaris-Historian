from __future__ import annotations

"""Read-only, evidence-led non-war campaign archive.

No raw save reads, no cache rebuild, no schema writes and no screenshot annotations.
Uses only the durable SQLite tables already populated by Historian.
"""

from collections import Counter
from html import escape
import json
import os
from pathlib import Path
import tempfile

from .db import Database


CATEGORIES = ("foundation", "people", "worlds", "navy", "diplomacy")


def empire_archive_path(db: Database, campaign_id: int) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")
    return Path(str(campaign["archive_dir"])) / "Empire_Archive.html"


def _value(value: object) -> str:
    return "" if value is None else str(value)


def _row(record: object) -> dict:
    return dict(record)  # sqlite3.Row -> regular dictionary


def _event(row: dict, category: str, source: str, *, id_field: str | None = None) -> dict:
    """Retain exact source chronology and distinguish publication visibility."""
    subject_id = row.get(id_field) if id_field else row.get("subject_id")
    return {
        "date": _value(row.get("game_date")),
        "category": category,
        "kind": _value(row.get("event_type") or row.get("entry_type")),
        "title": _value(row.get("title")),
        "body": _value(row.get("body")),
        "confidence": _value(row.get("confidence") or "recorded"),
        "date_kind": _value(row.get("date_kind") or "archive_observation"),
        "source": source,
        "visible": bool(int(row.get("visible", 1) or 0)),
        "subject_id": _value(subject_id),
        "subject_name": _value(row.get("subject_name")),
    }


def _details(row: dict, keys: tuple[tuple[str, str], ...]) -> list[list[str]]:
    return [[label, _value(row[key])] for label, key in keys if row.get(key) not in (None, "")]


def _directory(db: Database, campaign_id: int) -> dict[str, list[dict]]:
    # Only documented registry fields are used. Missing optional values are not
    # converted into historical claims or implied dates.
    specs = {
        "people": (
            db.leader_registry(campaign_id), "leader_id", "name", (
                ("Class", "leader_class"), ("First recorded", "first_seen_date"),
                ("Last recorded", "last_seen_date"), ("Recruitment date", "recruitment_date"),
                ("Latest level", "latest_level"), ("Latest assignment", "latest_assignment"),
                ("Latest council role", "latest_council_role"), ("Status", "status"),
            )),
        "worlds": (
            db.world_registry(campaign_id), "planet_id", "name", (
                ("System", "system_name"), ("Class", "planet_class_name"),
                ("First recorded", "first_seen_date"), ("Last recorded", "last_seen_date"),
                ("Colonisation date", "colonize_date"), ("Latest population observation", "latest_population"),
                ("Latest designation", "latest_designation_name"), ("Latest governor", "latest_governor_name"),
                ("Status", "status"),
            )),
        "fleets": (
            db.fleet_registry(campaign_id), "fleet_id", "name", (
                ("Class", "ship_class"), ("First recorded", "first_seen_date"),
                ("Last recorded", "last_seen_date"), ("Latest ship count", "latest_ship_count"),
                ("Latest home base", "latest_home_base"), ("Latest commander", "latest_commander_name"),
                ("Status", "status"),
            )),
        "ships": (
            db.ship_registry(campaign_id), "ship_id", "name", (
                ("Class", "ship_type"), ("First recorded", "first_seen_date"),
                ("Last recorded", "last_seen_date"), ("Construction date", "construction_date"),
                ("Construction site", "build_location"), ("Build-site evidence", "build_location_evidence"),
                ("Latest fleet", "latest_fleet_name"), ("Latest commander", "latest_commander_name"),
                ("Status", "status"),
            )),
    }
    result = {}
    for category, (records, identity, name, fields) in specs.items():
        result[category] = [
            {
                "id": _value(r[identity]),
                "name": _value(r.get(name) or f"Unresolved {category[:-1]} {r.get(identity)}"),
                "first": _value(r.get("first_seen_date")),
                "last": _value(r.get("last_seen_date")),
                "status": _value(r.get("status")),
                "baseline": bool(r.get("baseline_present")),
                "fields": _details(r, fields),
            }
            for record in records for r in (_row(record),)
        ]
    return result


def build_empire_archive_data(db: Database, campaign_id: int) -> dict:
    """SQLite-only aggregation; never reads game saves or presentation caches."""
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    events = []
    for entry in db.history_entries(campaign_id):
        row = _row(entry)
        if not int(row.get("snapshot_processed") or 0):
            continue
        item = _event(row, "foundation", "history_entries")
        item["visible"] = True
        events.append(item)

    sources = (
        (db.leader_career_events(campaign_id, visible_only=False), "people", "leader_career_events", "leader_id"),
        (db.world_history_events(campaign_id, visible_only=False), "worlds", "world_history_events", "planet_id"),
        (db.ship_fleet_events(campaign_id, visible_only=False), "navy", "ship_fleet_events", "ship_id"),
        (db.politics_events(campaign_id, visible_only=False), "diplomacy", "politics_history_events", "subject_id"),
    )
    for rows, category, source, id_field in sources:
        for record in rows:
            row = _row(record)
            item = _event(row, category, source, id_field=id_field)
            if category == "navy" and row.get("ship_id") is None and row.get("fleet_id") is not None:
                item["subject_id"] = _value(row["fleet_id"])
                item["subject_kind"] = "fleets"
            else:
                item["subject_kind"] = ("ships" if category == "navy" else category)
            events.append(item)

    events.sort(key=lambda r: (r["date"], r["category"], r["kind"], r["title"]))
    registry = _directory(db, campaign_id)
    published = Counter(e["category"] for e in events if e["visible"])
    technical = Counter(e["category"] for e in events if not e["visible"])
    counts = {k: {"published": published[k], "technical": technical[k]} for k in CATEGORIES}

    return {
        "version": "0.0.72",
        "campaign": {
            "name": _value(campaign["empire_name"]),
            "first": _value(campaign["first_game_date"]),
            "latest": _value(campaign["latest_game_date"]),
            "processed": db.processed_count(campaign_id),
            "archived": db.snapshot_count(campaign_id),
        },
        "counts": counts,
        "registry": registry,
        "events": events,
        "methodology": (
            "SQLite-only, from recorded historian observations. Archive dates are not automatically exact event dates. "
            "A leader entering the registry is not a recorded birth. A missing ship is not proof of destruction. "
            "A colony's latest population is not a historic population trend. "
            "The unfiltered technical records may include provisional observations. "
            "No screenshots, manually supplied narrative, remote sources or raw Ironman save reads are used."
        ),
    }


_STYLE = r"""
:root{color-scheme:dark;--bg:#0c1420;--panel:#142337;--panel2:#1b3047;--line:#34506b;--ink:#ecf3ff;--muted:#a9c2d8;--accent:#85cfff}
*{box-sizing:border-box}body{background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,Segoe UI,sans-serif;margin:0}
a{color:var(--accent)}button,input,select{font:inherit}button,select,input{background:#182e44;color:var(--ink);border:1px solid #4e708b;border-radius:6px;padding:9px 12px}button{cursor:pointer}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid #87cfff;outline-offset:2px}button[aria-pressed=true],button.active{background:#35618a;border-color:#95d6ff}button:hover{border-color:#9ad5ff}
header{position:sticky;top:0;z-index:5;background:#0f1e30;border-bottom:1px solid var(--line);padding:14px clamp(16px,3vw,48px)}header h1{font-family:Georgia,serif;margin:2px 0;font-size:clamp(20px,2.2vw,31px)}header small{color:var(--muted)}
main{max-width:1540px;margin:auto;padding:22px clamp(14px,3vw,42px) 90px}nav,.tools,.stats,.record-list{display:flex;gap:8px;flex-wrap:wrap}nav{margin:16px 0}nav button{padding:10px 14px}.tools{align-items:center;padding:12px;border:1px solid var(--line);border-radius:8px;background:var(--panel);margin:12px 0}.tools input[type=search]{flex:1;min-width:180px}.tools label{color:var(--muted)}.tools label input{max-width:110px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));margin:18px 0}.stat{background:var(--panel);border:1px solid var(--line);padding:16px;border-radius:8px}.stat span{font-size:12px;color:var(--muted);text-transform:uppercase}.stat strong{display:block;font-size:23px;margin:3px 0}
section.panel{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:18px;margin:18px 0}h2{font-family:Georgia,serif;font-size:23px;margin:0 0 8px}h3{font-size:16px;margin:0 0 8px}.muted,.meta{color:var(--muted)}.note{font-size:13px;color:#bfcee1}.item{background:var(--panel2);border:1px solid var(--line);padding:14px;border-radius:7px;margin:8px 0}.item h3{margin:0 0 6px;font-family:Georgia,serif}.item p{margin:8px 0}.meta{font-size:12px;margin-top:5px}.tag{display:inline-block;border:1px solid #567693;color:#cbe1f7;border-radius:20px;padding:2px 7px;font-size:11px;margin:0 6px 2px 0}.record-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:10px}.record-list .item{margin:0}.field-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:9px}.field{background:#13253a;border:1px solid var(--line);padding:10px}.field span{font-size:11px;color:var(--muted);display:block}.field strong{font-weight:600;overflow-wrap:anywhere}
.hide{display:none!important}.pagination{display:flex;align-items:center;gap:10px;justify-content:center;margin:16px 0}.pagination button:disabled{opacity:.45;cursor:default}.line{border-bottom:1px solid var(--line);margin:18px 0}.archive-link{font-size:13px}.sr-only{position:absolute;clip:rect(0,0,0,0);height:1px;width:1px;overflow:hidden}
@media(max-width:700px){header{position:static}.tools{align-items:stretch}.tools input[type=search]{width:100%}.record-list{grid-template-columns:1fr}}
"""

_JS = r"""
'use strict';
const db=JSON.parse(document.getElementById('archive-data').textContent);
let tab='overview', page=0, selected=null;
const PER_PAGE=80, $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const text=v=>String(v??'').toLowerCase();
const allCategories={overview:'Overview',timeline:'Chronology',people:'Leaders',worlds:'Worlds',fleets:'Fleets',ships:'Ships',diplomacy:'Diplomacy'};
const categoryOf=t=>t==='fleets'||t==='ships'?'navy':t;
function dateOk(d){const from=$('from').value.trim(),to=$('to').value.trim();const year=(d||'').split('.')[0];return (!from||year>=from)&&(!to||year<=to)}
function wordsOk(str){return text(str).includes(text($('search').value.trim()))}
function currentEvents(){const cat=tab==='timeline'?'':categoryOf(tab);return db.events.filter(x=>(!cat||x.category===cat)&&($('technical').checked||x.visible)&&dateOk(x.date)&&wordsOk([x.title,x.body,x.kind,x.subject_name,x.subject_id,x.source,x.date].join(' ')))}
function currentRecords(){return (db.registry[tab]||[]).filter(x=>dateOk(x.first)&&wordsOk([x.id,x.name,x.status,...x.fields.map(a=>a.join(' '))].join(' ')))}
function tag(label){return `<span class="tag">${esc(label)}</span>`}
function eventHtml(e){const idx=e.subject_id?` · ${esc(e.subject_kind||e.category)} #${esc(e.subject_id)}`:'';return `<article class="item"><h3>${esc(e.title||e.kind||'Recorded event')}</h3><div>${tag(e.date||'Date not retained')}${tag(e.category)}${!e.visible?tag('Technical / not published'):''}</div><p>${esc(e.body)}</p><div class="meta">Source: ${esc(e.source)} · ${esc(e.kind)}${idx} · ${esc(e.date_kind)} · confidence ${esc(e.confidence)}</div></article>`}
function recordHtml(r,kind){return `<article class="item"><h3>${esc(r.name)}</h3><div>${tag('ID '+r.id)}${tag(r.status||'Recorded')}${r.baseline?tag('Present at opening'):''}</div><p class="meta">${esc(r.first)} — ${esc(r.last)}</p><button type="button" data-record="${esc(kind)}:${esc(r.id)}">Inspect history</button></article>`}
function stat(label,n){return `<div class="stat"><span>${esc(label)}</span><strong>${esc(n)}</strong></div>`}
function overview(){let c=db.counts;return `<section class="panel"><h2>The recorded empire</h2><p class="muted">${esc(db.campaign.name)} · ${esc(db.campaign.first)} — ${esc(db.campaign.latest)}</p><div class="stats">${stat('Processed / archived',db.campaign.processed+' / '+db.campaign.archived)}${stat('Recorded leaders',db.registry.people.length)}${stat('Recorded worlds',db.registry.worlds.length)}${stat('Recorded fleets',db.registry.fleets.length)}${stat('Recorded ships',db.registry.ships.length)}${stat('Published diplomatic events',c.diplomacy.published)}${stat('Published non-war events',Object.values(c).reduce((s,v)=>s+v.published,0))}</div><h2>Explore the records</h2><p>Chronology follows archival observations; individual leader, colony, fleet and vessel registers support historical investigation. Filter and export the records without reopening a save.</p><div class="field-grid">${Object.entries(c).map(([key,n])=>`<div class="field"><span>${esc(key)} evidence</span><strong>${n.published} published / ${n.technical} technical</strong></div>`).join('')}</div></section>`}
function pagination(n){let total=Math.max(1,Math.ceil(n/PER_PAGE));page=Math.min(page,total-1);return `<div class="pagination"><button id="prev" ${page===0?'disabled':''}>Previous</button><span>Page ${page+1} / ${total} · ${n} matching</span><button id="next" ${page+1===total?'disabled':''}>Next</button></div>`}
function pageHandlers(n){$('prev')?.addEventListener('click',()=>{page--;render()});$('next')?.addEventListener('click',()=>{page++;render()})}
function bindRecords(){document.querySelectorAll('[data-record]').forEach(b=>b.addEventListener('click',()=>{const [kind,id]=b.dataset.record.split(':');selected={kind,id};render();$('detail')?.scrollIntoView({behavior:'smooth',block:'start'})}))}
function relatedEvents(kind,id){const cat=categoryOf(kind);return db.events.filter(e=>e.category===cat&&e.subject_id===id&&(e.subject_kind||cat)===kind&&($('technical').checked||e.visible)).sort((a,b)=>a.date.localeCompare(b.date))}
function detail(){if(!selected)return '';const r=(db.registry[selected.kind]||[]).find(r=>r.id===selected.id);if(!r)return '';const events=relatedEvents(selected.kind,selected.id);return `<section class="panel" id="detail"><button id="close-detail">Close record</button><h2>${esc(r.name)}</h2><p class="note">Registry ID ${esc(r.id)}. First/last dates are observation bounds; status and missing records are not proof of a death or destruction.</p><div class="field-grid">${r.fields.map(([a,b])=>`<div class="field"><span>${esc(a)}</span><strong>${esc(b)}</strong></div>`).join('')}</div><h3 style="margin-top:22px">Linked historical entries (${events.length})</h3>${events.length?events.map(eventHtml).join(''):'<p class="muted">No separately linked events retained in the durable event tables. This is not proof that nothing happened.</p>'}</section>`}
function render(){let html='';const recordsMode=['people','worlds','fleets','ships'].includes(tab);let list=[];
if(tab==='overview'){html=overview();$('tools').classList.add('hide')}
else{$('tools').classList.remove('hide');$('csv').textContent=recordsMode?'Export register CSV':'Export dated events CSV';list=recordsMode?currentRecords():currentEvents();const heading=allCategories[tab];let cards=(recordsMode?list.map(x=>recordHtml(x,tab)):list.map(eventHtml));html=`<section class="panel"><h2>${esc(heading)}</h2><p class="muted">${list.length} matching ${recordsMode?'registry entries':'dated observations'} · ${recordsMode?'Select a record to inspect its retained history.':'Source, precision and confidence shown on every entry.'}</p>${pagination(list.length)}<div class="${recordsMode?'record-list':''}">${cards.slice(page*PER_PAGE,(page+1)*PER_PAGE).join('')||'<p class="muted">No matching records. Clear filters or include technical observations.</p>'}</div>${pagination(list.length)}</section>`}
$('output').innerHTML=html+(recordsMode?detail():'');
if(tab!=='overview'){const ps=document.querySelectorAll('.pagination');ps.forEach(p=>{p.querySelector('#prev').addEventListener('click',()=>{page--;render()});p.querySelector('#next').addEventListener('click',()=>{page++;render()})})}
bindRecords();$('close-detail')?.addEventListener('click',()=>{selected=null;render()});
document.querySelectorAll('[data-tab]').forEach(b=>{b.setAttribute('aria-pressed',b.dataset.tab===tab?'true':'false')})}
function exportRows(kind){const recordsMode=['people','worlds','fleets','ships'].includes(tab);
if(kind==='json'){const data={campaign:db.campaign,section:tab,methodology:db.methodology,events:tab==='overview'?db.events.filter(e=>$('technical').checked||e.visible):currentEvents(),registry:tab==='overview'?db.registry:(recordsMode?currentRecords():[])};return {filename:'Empire_Archive_'+tab+'.json',content:JSON.stringify(data,null,2),mime:'application/json'}}
const rows=recordsMode?currentRecords():(tab==='overview'?db.events.filter(e=>$('technical').checked||e.visible):currentEvents());const keys=recordsMode?['id','name','first','last','status','baseline','fields']:['date','category','kind','title','body','confidence','date_kind','source','visible','subject_id'];const csv=[keys.join(',')].concat(rows.map(r=>keys.map(k=>'"'+String(typeof r[k]==='object'?JSON.stringify(r[k]):r[k]??'').replace(/"/g,'""')+'"').join(','))).join('\r\n');return {filename:'Empire_Archive_'+tab+'.csv',content:'\ufeff'+csv,mime:'text/csv;charset=utf-8'}}
function download(kind){const file=exportRows(kind),url=URL.createObjectURL(new Blob([file.content],{type:file.mime}));const a=document.createElement('a');a.href=url;a.download=file.filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),500)}
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>{tab=b.dataset.tab;page=0;selected=null;render()}));
['search','from','to'].forEach(id=>$(id).addEventListener('input',()=>{page=0;render()}));$('technical').addEventListener('change',()=>{page=0;render()});
$('json').addEventListener('click',()=>download('json'));$('csv').addEventListener('click',()=>download('csv'));
$('methodology').textContent=db.methodology;
const params=new URLSearchParams(location.search);
const request=params.get('record');
const desiredTab=params.get('tab');
if(request&&request.includes(':')){
  const [kind,id]=request.split(':');
  if(['people','worlds','fleets','ships'].includes(kind)){
    tab=kind;selected={kind,id};
    const registry=db.registry[kind]||[];
    const found=registry.find(r=>r.id===id);
    if(found){$('search').value=found.name||'';}
  }
}else if(desiredTab&&Object.prototype.hasOwnProperty.call(allCategories,desiredTab)){
  tab=desiredTab;
}
if(params.get('search'))$('search').value=params.get('search');
render();
if(selected)requestAnimationFrame(()=>$('detail')?.scrollIntoView({block:'start'}));
"""


def render_empire_archive(db: Database, campaign_id: int) -> Path:
    """Create an atomic, standalone offline HTML artefact under campaign archive."""
    data = build_empire_archive_data(db, campaign_id)
    json_payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # Do not let a recorded Stellaris name terminate the script element.
    json_payload = (json_payload.replace("&", "\\u0026").replace("<", "\\u003c")
                    .replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    name = escape(data["campaign"]["name"])
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} — Empire Archive</title><style>{_STYLE}</style>
<link rel="stylesheet" href="/static/historian-theme.css?v=087">
<script src="/static/historian-theme.js?v=087"></script>
</head><body>
<header><small>STELLARIS HISTORIAN v0.0.75 · ARCHIVED EVIDENCE ONLY</small><h1>{name} — Empire Archive</h1>
<small>Leadership · Colonies · Navy · Diplomacy · Dated archive chronology</small>
<nav aria-label="Archive sections">'''+''.join(f'<button type="button" data-tab="{escape(k)}" aria-pressed="false">{escape(v)}</button>' for k,v in (("overview","Overview"),("timeline","Chronology"),("people","Leaders"),("worlds","Worlds"),("fleets","Fleets"),("ships","Ships"),("diplomacy","Diplomacy")))+'''</nav>
<a class="archive-link" href="/campaign">Campaign dashboard</a> · <a class="archive-link" href="/timeline">Printable Timeline</a> · <a class="archive-link" href="/journal">Historical Journal</a> · <a class="archive-link" href="/war-journal">War Journal</a> · <a href="/time-machine">Time Machine</a>
</header>
<main><section class="panel"><h2>Historical evidence rules</h2><p class="note" id="methodology"></p>
<p class="note">This page is regenerated on demand from already recorded SQLite history; it does not inspect Ironman saves. Evidence from unprocessed archives is never treated as processed history. The exports are generated locally in your browser.</p></section>
<div class="tools hide" id="tools"><input id="search" type="search" aria-label="Search records" placeholder="Search names, dates, event types, IDs...">
<label>From year <input id="from" type="text" inputmode="numeric" placeholder="2200" maxlength="5"></label>
<label>To year <input id="to" type="text" inputmode="numeric" placeholder="2400" maxlength="5"></label>
<label><input id="technical" type="checkbox"> Include unpublished technical events</label>
<button type="button" id="csv">Export dated events CSV</button><button type="button" id="json">Export JSON</button></div>
<div id="output" aria-live="polite"></div>
</main><script type="application/json" id="archive-data">'''+json_payload+'''</script>
<script>'''+_JS+'''</script></body></html>'''
    # Same-directory atomic replacement keeps existing readable archive intact
    # if rendering or writing fails. No database writes or .sav changes.
    path = empire_archive_path(db, campaign_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".empire_archive_", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(html)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return path
