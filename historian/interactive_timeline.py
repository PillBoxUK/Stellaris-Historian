from __future__ import annotations

"""Interactive, evidence-based chronological explorer for a Stellaris campaign.

Read-only presentation: durable SQLite historical tables, parsed snapshot caches,
and existing First Contact evidence. No game-save parsing, DB migrations or schema writes.
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
from .domains.politics.first_contact_history import load_first_contact_history
from .presentation_history import build_presentation_history
from .timeline import _collect_events, _clean_public_text


_GROUPS = (
    ("empire", "Empire"), ("colonies", "Colonies"), ("space", "Space combat"),
    ("ground", "Ground combat"), ("technology", "Technology"),
    ("contacts", "First contacts"), ("politics", "Government"),
    ("internal_council", "Imperial Council"), ("federations", "Federations"),
    ("galactic", "Galactic Community"), ("diplomacy", "Diplomacy"),
    ("leaders", "Leaders"), ("navy", "Ships & fleets"),
    ("science", "Science & exploration"),
)

_DATE = re.compile(r"^\d{4,5}\.\d{2}\.\d{2}$")


def _valid_date(value: object) -> bool:
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        return False
    year, month, day = (int(x) for x in value.split("."))
    return year >= 1 and 1 <= month <= 12 and 1 <= day <= 31


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _classification(category: str, kind: str, title: str, body: str, source: str) -> str:
    """Classification is conservative: federation != empire's internal council."""
    cat, event_kind = category.lower(), kind.lower()
    evidence = (title + " " + body).lower()
    if cat in ("worlds", "expansion", "colony", "colonies"):
        return "colonies"
    if cat in ("people", "leaders"):
        return "leaders"
    if cat in ("military", "navy", "ships", "fleets"):
        return "navy"
    if cat in ("science", "exploration"):
        return "science"
    if cat in ("technology", "research"):
        return "technology"
    if cat == "contacts" or "first_contact" in event_kind:
        return "contacts"
    if cat in ("combat", "space", "ground"):
        # Combat-episode chronology is derived from fleet engagements, not land invasions.
        if "ground" in event_kind or "army" in event_kind or cat == "ground":
            return "ground"
        return "space"
    if cat in ("politics", "diplomacy"):
        if "federat" in event_kind or "federat" in title.lower():
            return "federations"
        if ("galactic_community" in event_kind or "galactic_council" in event_kind
                or "resolution" in event_kind or "galactic community" in title.lower()
                or "galactic council" in title.lower() or "galactic senate" in title.lower()):
            return "galactic"
        if "council_agenda" in event_kind or "internal_council" in event_kind:
            return "internal_council"
        if any(token in event_kind for token in ("government", "ruler", "ethic", "civic", "tradition", "authority")):
            return "politics"
        return "diplomacy"
    if cat == "empire" or cat == "foundation":
        return "empire"
    return "empire"


def timeline_path(db: Database, campaign_id: int) -> Path:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist")
    return Path(str(campaign["archive_dir"])) / "Interactive_Timeline.html"


def build_interactive_timeline_data(db: Database, campaign_id: int) -> dict:
    """Build a single chronology; never infer a historical event from mere absence."""
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist")
    archive = build_empire_archive_data(db, campaign_id)
    # One shared cache read for the polished historical chronology plus the
    # individual learned technologies that the paper timeline selectively groups.
    presentation = build_presentation_history(db, campaign_id)
    curated, _leaders = _collect_events(db, campaign_id, presentation=presentation)
    rows: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add(*, date: object, category: str, kind: str, title: object, body: object,
            date_kind: str, confidence: str, source: str, visible: bool = True,
            subject_id: object = "", subject_kind: str = "") -> None:
        if not _valid_date(date):
            return
        name, description = _text(title), _text(body)
        group = _classification(category, kind, name, description, source)
        # Most duplicate observations are already consolidated by the upstream
        # domain models; avoid only exact repeats, not distinct same-day events.
        key = (_text(date), group, name.casefold(), description.casefold())
        if key in seen:
            return
        seen.add(key)
        rows.append({
            "date": _text(date), "group": group, "kind": kind,
            "title": name or "Recorded observation", "body": description,
            "date_kind": date_kind or "archive_observation", "confidence": confidence or "recorded",
            "source": source, "visible": bool(visible),
            "subject_id": _text(subject_id), "subject_kind": subject_kind,
        })

    for item in curated:
        if item.category == "Technology":
            continue  # add distinct individual technology records below
        add(date=item.game_date, category=item.category, kind="curated_timeline",
            title=item.title, body=item.body, date_kind="retained_or_observed",
            confidence="presentation", source="historical_timeline")

    for event in presentation.events:
        if event.category == "technology":
            add(date=event.game_date, category="technology", kind=event.event_type,
                title=event.title, body=_clean_public_text(event.summary),
                date_kind=event.date_kind, confidence=event.confidence,
                source=event.source)
        elif event.category == "combat" and (
            "ground" in event.event_type.lower() or "army" in event.event_type.lower()
        ):
            add(date=event.game_date, category="combat", kind=event.event_type,
                title=event.title, body=_clean_public_text(event.summary),
                date_kind=event.date_kind, confidence=event.confidence, source=event.source)

    for event in archive["events"]:
        if event["category"] == "foundation":
            # Per-snapshot bookkeeping: never flood the date slider with 479
            # copies of an archival checkpoint misrepresented as an event.
            continue
        add(date=event["date"], category=event["category"], kind=event["kind"],
            title=event["title"], body=event["body"],
            date_kind=event["date_kind"], confidence=event["confidence"],
            source=event["source"], visible=event["visible"],
            subject_id=event.get("subject_id"), subject_kind=event.get("subject_kind", ""))

    first_contact = load_first_contact_history(db, campaign_id)
    for event in first_contact.get("events", []):
        if not isinstance(event, dict):
            continue
        add(date=event.get("game_date"), category="contacts",
            kind=_text(event.get("event_type")), title=event.get("title"),
            body=event.get("body"), date_kind=_text(event.get("date_kind")),
            confidence=_text(event.get("confidence")), source="first_contact_history",
            visible=bool(event.get("visible")),
            subject_id=event.get("contact_id"), subject_kind="contacts")

    rows.sort(key=lambda r: (r["date"], r["group"], r["title"], r["kind"]))
    for index, row in enumerate(rows):
        row["id"] = str(index)
    counts = Counter(e["group"] for e in rows if e["visible"])
    return {
        "version": "0.0.73",
        "campaign": archive["campaign"],
        "groups": [{"id": key, "label": label, "count": counts[key]} for key, label in _GROUPS],
        "events": rows,
        "methodology": ("Evidence from recorded SQLite history, reviewed presentation cache and existing "
                        "First Contact history only. A save-observation date is not necessarily the exact "
                        "occurrence date. Ground engagements, Federation votes and Galactic Community "
                        "resolutions appear only where independently recorded; an empty category is an "
                        "evidence-coverage gap, not proof nothing happened. No screenshots or manual annotations."),
    }


_CSS = r"""
:root{color-scheme:dark;--bg:#091422;--panel:#13243a;--panel2:#1a334c;--line:#36546f;--ink:#eaf2ff;--muted:#b2c7df;--accent:#81d5f6;--gold:#f6cc7c}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.48 Segoe UI,system-ui,sans-serif}
button,input{font:inherit;color:inherit}button{background:#213f5b;border:1px solid #537896;padding:9px 13px;border-radius:5px;cursor:pointer}button:hover,button:focus-visible,input:focus-visible{outline:2px solid #82d4f8;outline-offset:1px}button:disabled{opacity:.4;cursor:default}button.active{background:#3d6d95;border-color:#8dd8ff}input[type=text],input[type=search]{background:#102239;border:1px solid #52708d;padding:9px;border-radius:5px}a{color:var(--accent)}.muted{color:var(--muted)}
header{padding:15px clamp(16px,3vw,44px);background:#102137;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}.head{display:flex;align-items:center;justify-content:space-between;gap:15px;flex-wrap:wrap}h1{font:700 clamp(23px,2.5vw,34px) Georgia,serif;margin:0}.kicker{font:700 11px Segoe UI,sans-serif;color:#8cccf3;letter-spacing:.13em;text-transform:uppercase}nav{display:flex;flex-wrap:wrap;gap:16px}
main{max-width:1690px;margin:auto;padding:18px clamp(12px,2vw,32px) 65px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:17px;margin-bottom:15px}.controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.controls .date-entry{width:138px}.controls small{color:var(--muted)}.big-date{font:700 26px Georgia,serif;color:var(--gold)}.timeline-slide{width:100%;accent-color:var(--accent);cursor:pointer;margin:16px 0 6px}.scale{display:flex;justify-content:space-between;color:var(--muted);font-size:12px}
#year-bars{display:flex;gap:2px;align-items:end;height:74px;margin:14px 0 0;overflow:hidden;border-bottom:1px solid #658099}#year-bars button{flex:1 1 0;min-width:3px;padding:0;border:0;border-radius:2px 2px 0 0;background:#32678b;position:relative}#year-bars button.sel{background:var(--gold)}#year-bars button:hover{background:#8ee0ff}
.filters{display:flex;flex-wrap:wrap;gap:7px;margin-top:13px}.filter{display:flex;gap:6px;align-items:center;cursor:pointer;border:1px solid #48647d;padding:7px 10px;border-radius:16px;background:#1b3148}.filter:has(input:checked){border-color:#8bcdf5;background:#234665}.filter input{accent-color:#74cfff}.filter span{color:#bccee1;font-size:11px}.filter.empty{opacity:.53}
.layout{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(300px,.95fr);gap:15px}.events{min-height:390px;max-height:670px;overflow-y:auto}.event{width:100%;text-align:left;display:block;margin:7px 0;background:#1a324d;border:1px solid #466481;padding:11px 13px}.event .top{display:flex;justify-content:space-between;color:#a7c8df;gap:12px;font-size:12px}.event strong{font:700 16px Georgia,serif;display:block;margin-top:5px}.event.chosen{border-color:var(--gold);background:#304865}.event .preview{color:#c2d6e8;font-size:12px;margin:5px 0 0;display:block}.minor{font-size:12px;color:var(--muted)}.event-count{margin:8px 0 12px}h2{font:700 21px Georgia,serif;margin:0 0 8px}h3{font:700 17px Georgia,serif;margin:0 0 7px}.detail{background:#1a3048;border:1px solid #476681;border-radius:8px;padding:17px;position:sticky;top:125px}.tag{display:inline-block;font-size:11px;background:#294a67;border:1px solid #557e9b;padding:3px 7px;border-radius:12px;margin:3px 4px 3px 0}.detail p{line-height:1.65}.evidence{border-top:1px solid #48637b;margin-top:14px;padding-top:12px}.buttons{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}.notice{padding:9px 11px;background:#202c3a;border-left:3px solid var(--gold);font-size:12px}.empty-state{border:1px dashed #57718a;padding:25px;text-align:center;color:var(--muted)}.footer{font-size:12px;color:var(--muted);margin-top:15px}
@media(max-width:900px){.layout{grid-template-columns:1fr}.detail{position:static}.events{max-height:500px}header{position:static}}@media(max-width:520px){.controls{align-items:stretch}.controls>*{flex:1}h1{font-size:24px}}
@media print{header,.controls,.filters,#year-bars,.timeline-slide,.scale,.buttons{display:none!important}.layout{display:block}.events{overflow:visible;max-height:none}.panel,.detail{break-inside:avoid}}
"""

_JS = r"""
'use strict';
const data=JSON.parse(document.getElementById('timeline-data').textContent);
const $=id=>document.getElementById(id);
const escapeHtml=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=v=>String(v??'').toLowerCase();
let included=new Set(data.groups.map(g=>g.id));let technical=false;let query='';let playHandle=null;
let currentDate='',chosenId=null;
const dateRegex=/^\d{4,5}\.\d{2}\.\d{2}$/;
const yearOf=d=>Number((d||'').split('.')[0]);
function allowed(e){return (technical||e.visible)&&included.has(e.group)&&(!query||norm([e.title,e.body,e.kind,e.date,e.source].join(' ')).includes(query))}
function active(){return data.events.filter(allowed)}
function availableDates(){return [...new Set(active().map(e=>e.date))]}
function nearestDate(dates,requested){if(!dates.length)return '';let lo=0,hi=dates.length;while(lo<hi){const mid=(lo+hi)>>1;if(dates[mid]<requested)lo=mid+1;else hi=mid}if(lo<=0)return dates[0];if(lo>=dates.length)return dates[dates.length-1];return dates[lo-1]===requested?dates[lo-1]:dates[lo]}
function updateDate(date,keepSelection=false){const dates=availableDates();currentDate=dates.includes(date)?date:nearestDate(dates,date||data.campaign.first||'2200.01.01');if(!keepSelection)chosenId=null;render()}
function stop(){if(playHandle!==null){clearInterval(playHandle);playHandle=null}$('play').textContent='▶ Play'}
function move(delta){const dates=availableDates();if(!dates.length){stop();return}let i=dates.indexOf(currentDate);if(i<0)i=0;let n=i+delta;if(n<0)n=0;if(n>=dates.length){n=dates.length-1;stop()}updateDate(dates[n]);}
function jump(year){const dates=availableDates();const prefix=String(year).padStart(4,'0')+'.01.01';updateDate(nearestDate(dates,prefix))}
function ensureVisible(date){const dates=availableDates();if(!dates.length){currentDate='';return}if(!dates.includes(currentDate))currentDate=nearestDate(dates,date||currentDate||dates[0]);}
function renderBars(events){const low=yearOf(data.campaign.first)||yearOf(events[0]?.date)||2200;const high=yearOf(data.campaign.latest)||yearOf(events.at(-1)?.date)||low;
const counts=new Map();events.forEach(e=>counts.set(yearOf(e.date),(counts.get(yearOf(e.date))||0)+1));const max=Math.max(1,...counts.values());const area=$('year-bars');area.replaceChildren();
for(let y=low;y<=high;y++){const n=counts.get(y)||0;const btn=document.createElement('button');btn.type='button';btn.setAttribute('aria-label',`Jump to ${y}: ${n} events`);btn.title=`${y}: ${n} matching events`;btn.style.height=(n?Math.max(6,Math.round(68*Math.sqrt(n/max))):3)+'px';btn.className=yearOf(currentDate)===y?'sel':'';btn.addEventListener('click',()=>jump(y));area.append(btn)}
$('start-year').textContent=String(low);$('end-year').textContent=String(high);
}
function render(){const events=active();const dates=availableDates();ensureVisible(dates[0]);
const index=dates.indexOf(currentDate);$('scrubber').min='0';$('scrubber').max=String(Math.max(0,dates.length-1));$('scrubber').value=String(Math.max(0,index));$('scrubber').disabled=!dates.length;
$('current-date').textContent=currentDate||'No matching dates';$('date-box').value=currentDate;$('time-count').textContent=`${dates.length} recorded dates · ${events.length} events`;
$('previous').disabled=index<=0;$('next').disabled=index<0||index===dates.length-1;$('play').disabled=dates.length<2;
$('filter-count').textContent=`${events.length} matching evidence entries`;
const dayEvents=events.filter(e=>e.date===currentDate);const nearby=events.filter(e=>e.date!==currentDate).sort((a,b)=>Math.abs(dates.indexOf(a.date)-index)-Math.abs(dates.indexOf(b.date)-index)||a.date.localeCompare(b.date)).slice(0,12);
const combined=[...dayEvents,...nearby.sort((a,b)=>a.date.localeCompare(b.date))];
const result=$('event-list');result.replaceChildren();
function eventButton(e){const btn=document.createElement('button');btn.type='button';btn.className='event'+(chosenId===e.id?' chosen':'');btn.innerHTML=`<span class="top"><span>${escapeHtml(e.date)} · ${escapeHtml((data.groups.find(g=>g.id===e.group)||{}).label||e.group)}</span><span>${e.date===currentDate?'Selected date':'Nearby'}</span></span><strong>${escapeHtml(e.title)}</strong><span class="preview">${escapeHtml(e.body).slice(0,190)}</span>`;btn.addEventListener('click',()=>{chosenId=e.id;showDetail(e);renderListSelection()});return btn}
function renderListSelection(){result.querySelectorAll('.event').forEach(b=>b.classList.remove('chosen'));[...result.querySelectorAll('.event')].find(b=>b.dataset.id===chosenId)?.classList.add('chosen')}
combined.forEach(e=>{let b=eventButton(e);b.dataset.id=e.id;result.append(b)});
$('day-summary').textContent=`${dayEvents.length} on ${currentDate||'this date'} · ${nearby.length} nearby`;
if(!combined.length){const e=document.createElement('div');e.className='empty-state';e.textContent='No events match these filters. Try enabling another category or clearing your search.';result.append(e)}
let chosen=events.find(e=>e.id===chosenId);if(!chosen&&dayEvents.length){chosen=dayEvents[0];chosenId=chosen.id}if(!chosen&&combined.length){chosen=combined[0];chosenId=chosen.id}showDetail(chosen);renderListSelection();renderBars(events);
$('coverage').textContent=data.groups.filter(g=>g.count===0&&['ground','federations','galactic'].includes(g.id)).map(g=>g.label+' not independently established in this archive').join(' · ');
}
function showDetail(e){const box=$('detail');if(!e){box.innerHTML='<h2>Event details</h2><p class="muted">Choose an event to inspect its evidence.</p>';return}
const label=(data.groups.find(g=>g.id===e.group)||{}).label||e.group;
box.innerHTML=`<h2>${escapeHtml(e.title)}</h2><div><span class="tag">${escapeHtml(label)}</span><span class="tag">${escapeHtml(e.date)}</span>${e.visible?'':'<span class="tag">Unpublished technical evidence</span>'}</div><p>${escapeHtml(e.body)||'No narrative retained.'}</p><div class="evidence"><h3>Historical provenance</h3><div class="minor">Date evidence: <b>${escapeHtml(e.date_kind)}</b></div><div class="minor">Confidence: ${escapeHtml(e.confidence)}</div><div class="minor">Record type: ${escapeHtml(e.kind)}</div><div class="minor">Source: ${escapeHtml(e.source)}</div>${e.subject_id?`<div class="minor">Linked identity: ${escapeHtml(e.subject_kind)} #${escapeHtml(e.subject_id)}</div>`:''}<p class="notice">First-observed and archive dates are not automatically exact event dates. The original source classification is preserved.</p></div><div class="buttons"><button type="button" id="copy-event">Copy event</button><a href="/empire-archive">Empire Archive ↗</a><a href="/war-journal">War Journal ↗</a><a href="/journal">Historical Journal ↗</a></div>`;
$('copy-event').addEventListener('click',()=>{const text=`${e.date} | ${label} | ${e.title}\n${e.body}\nSource: ${e.source} | ${e.kind} | ${e.date_kind} | confidence ${e.confidence}`;if(navigator.clipboard?.writeText)navigator.clipboard.writeText(text).catch(()=>fallbackCopy(text));else fallbackCopy(text)})}
function fallbackCopy(text){const el=document.createElement('textarea');el.value=text;document.body.append(el);el.select();document.execCommand('copy');el.remove()}
function exportData(){const events=active();const dataOut={campaign:data.campaign,methodology:data.methodology,filters:[...included],include_technical:technical,query,events};const blob=new Blob([JSON.stringify(dataOut,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='Interactive_Timeline.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
$('filters').innerHTML=data.groups.map(g=>`<label class="filter${g.count?'':' empty'}"><input type="checkbox" value="${escapeHtml(g.id)}" checked><strong>${escapeHtml(g.label)}</strong><span>${g.count}</span></label>`).join('');
$('filters').addEventListener('change',e=>{if(e.target.matches('input[type=checkbox]')){stop();const id=e.target.value;e.target.checked?included.add(id):included.delete(id);updateDate(currentDate)}});
$('technical').addEventListener('change',e=>{stop();technical=e.target.checked;updateDate(currentDate)});
$('search').addEventListener('input',e=>{stop();query=norm(e.target.value.trim());updateDate(currentDate)});
$('scrubber').addEventListener('input',e=>{stop();const dates=availableDates();updateDate(dates[Number(e.target.value)])});
$('previous').addEventListener('click',()=>{stop();move(-1)});$('next').addEventListener('click',()=>{stop();move(1)});
$('play').addEventListener('click',()=>{if(playHandle!==null){stop();return}const dates=availableDates();if(dates.indexOf(currentDate)===dates.length-1)updateDate(dates[0]);$('play').textContent='❚❚ Pause';playHandle=setInterval(()=>move(1),780)});
$('date-go').addEventListener('click',()=>{stop();const input=$('date-box').value.trim();if(!dateRegex.test(input)){$('date-error').textContent='Use YYYY.MM.DD';return}$('date-error').textContent='';updateDate(input)});
$('date-box').addEventListener('keydown',e=>{if(e.key==='Enter')$('date-go').click()});
$('first').addEventListener('click',()=>{stop();updateDate(availableDates()[0])});$('last').addEventListener('click',()=>{stop();updateDate(availableDates().at(-1))});
$('reset').addEventListener('click',()=>{stop();included=new Set(data.groups.map(g=>g.id));technical=false;query='';$('search').value='';$('technical').checked=false;$('filters').querySelectorAll('input').forEach(e=>e.checked=true);updateDate(data.campaign.first)});
$('export').addEventListener('click',exportData);
$('methodology').textContent=data.methodology;
const years=availableDates();currentDate=years[0]||'';render();
"""


def render_interactive_timeline(db: Database, campaign_id: int) -> Path:
    data = build_interactive_timeline_data(db, campaign_id)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = (payload.replace("&", "\\u0026").replace("<", "\\u003c")
               .replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    empire = escape(data["campaign"]["name"])
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{empire} — Interactive Empire Timeline</title><style>{_CSS}</style>
<link rel="stylesheet" href="/static/historian-theme.css?v=087">
<script src="/static/historian-theme.js?v=087"></script>
</head><body>
<header><div class="head"><div><div class="kicker">Stellaris Historian v0.0.73 · Recorded evidence</div><h1>{empire} — Interactive Timeline</h1><div class="muted">Explore the chronology without replaying, editing or rebuilding saves</div></div><nav><a href="/campaign">Campaign</a><a href="/timeline">Printable timeline</a><a href="/empire-archive">Empire Archive</a><a href="/time-machine">Time Machine</a><a href="/war-journal">War Journal</a></nav></div></header>
<main><section class="panel" aria-label="Date navigation"><div class="controls"><button id="first" type="button">|◀ First</button><button id="previous" type="button">◀ Previous</button><button id="play" type="button">▶ Play</button><button id="next" type="button">Next ▶</button><button id="last" type="button">Latest ▶|</button><strong class="big-date" id="current-date">—</strong><span class="muted" id="time-count"></span></div>
<input class="timeline-slide" id="scrubber" type="range" min="0" max="0" value="0" aria-label="Scrub through recorded event dates"><div class="scale"><span id="start-year"></span><span>Slide or play through recorded dates; clicking a year jumps to it</span><span id="end-year"></span></div>
<div id="year-bars" aria-label="Years with recorded events"></div><div class="controls" style="margin-top:14px"><label for="date-box">Jump to date</label><input class="date-entry" id="date-box" type="text" placeholder="2294.04.01" aria-label="Jump to Stellaris date"><button id="date-go" type="button">Go</button><span id="date-error" class="minor" role="status"></span><button type="button" id="reset">Reset filters</button><button type="button" id="export">Export filtered JSON</button></div></section>
<section class="panel" aria-label="Historical categories"><div class="controls"><label>Search events <input id="search" type="search" placeholder="Planet, commander, war, research..."></label><label><input id="technical" type="checkbox"> Include unpublished technical observations</label><span class="muted" id="filter-count"></span></div><div id="filters" class="filters"></div><p class="minor" id="coverage"></p></section>
<div class="layout"><section class="panel"><h2>Historical events</h2><p class="minor" id="day-summary"></p><div class="events" id="event-list" aria-label="Events at selected and nearby dates"></div></section><aside><div id="detail" class="detail" aria-live="polite"></div></aside></div>
<p class="footer" id="methodology"></p></main><script type="application/json" id="timeline-data">{payload}</script><script>{_JS}</script></body></html>'''
    target = timeline_path(db, campaign_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".interactive_timeline_", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return target
