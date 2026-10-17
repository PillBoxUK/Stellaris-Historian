"""Government & People — evidence-aware career and office register (v0.0.83).

No new claims are inferred from snapshots. Exact notification dates are
visibly distinguished from first observations and unknown disappearances.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from html import escape
from .local_database_browser import readonly_connection


def _safe_json(v, fallback):
    try: return json.loads(v) if v else fallback
    except (TypeError, ValueError): return fallback


def government_data(db_path: Path, campaign_id: int) -> dict:
    with readonly_connection(db_path) as conn:
        campaign=conn.execute('SELECT id,empire_name,first_game_date,latest_game_date FROM campaigns WHERE id=?',(campaign_id,)).fetchone()
        if campaign is None: raise ValueError('Campaign is not available.')
        leaders={}
        for row in conn.execute('SELECT * FROM leader_registry WHERE campaign_id=? ORDER BY first_seen_date, name',(campaign_id,)):
            p=dict(row)
            p['traits']=_safe_json(p['trait_names'],[])
            p.pop('trait_names',None)
            p['raw_traits']=_safe_json(p['traits'] if isinstance(p['traits'],str) else row['traits'],[])
            p['events']=[]
            leaders[int(p['leader_id'])]=p
        # Deep evidence is optional for older installations.
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'leader_deep_evidence' in tables:
            for row in conn.execute('SELECT * FROM leader_deep_evidence WHERE campaign_id=?',(campaign_id,)):
                lid=int(row['leader_id'])
                if lid not in leaders:continue
                deep={k:v for k,v in dict(row).items() if k not in {'id','campaign_id','leader_id','raw_record_keys','raw_flag_values','raw_variable_values','event_target_aliases','updated_utc'}}
                leaders[lid]['deep']=deep
        for row in conn.execute('SELECT * FROM leader_career_events WHERE campaign_id=? ORDER BY game_date,snapshot_id,id',(campaign_id,)):
            lid=int(row['leader_id']); leader=leaders.get(lid)
            if leader:
                leader['events'].append({k:row[k] for k in ('game_date','event_type','title','body','confidence','date_kind')})
        name_by_id={k:v['name'] for k,v in leaders.items()}
        terms=[]
        prev_id=object()
        last_date=None
        for row in conn.execute('SELECT game_date,snapshot_id,state_json FROM politics_states WHERE campaign_id=? ORDER BY game_date,snapshot_id',(campaign_id,)):
            state=_safe_json(row['state_json'],{})
            rid=state.get('ruler_id')
            if rid != prev_id:
                if terms and terms[-1]['leader_id']==prev_id:
                    terms[-1]['last_observed']=last_date
                    terms[-1]['first_absent_or_succeeded']=str(row['game_date'])
                if rid is not None:
                    try:rid=int(rid)
                    except (TypeError,ValueError): pass
                    terms.append({'leader_id':rid, 'name':name_by_id.get(rid,state.get('ruler_name') or 'Unresolved ruler'),
                                  'first_observed':str(row['game_date']), 'last_observed':None,
                                  'date_kind':'first_observed' if terms else 'archive_opening'})
                prev_id=rid
            last_date=str(row['game_date'])
        if terms and terms[-1]['leader_id']==prev_id:
            terms[-1]['last_observed']=last_date
        events=[]
        for row in conn.execute('SELECT game_date,event_type,title,body,confidence,date_kind,subject_name FROM politics_history_events WHERE campaign_id=? AND event_type NOT IN ("council_agenda_progress_changed","diplomatic_contact_first_observed","communications_state_changed","hostility_state_changed") ORDER BY game_date,id',(campaign_id,)):
            events.append({k:row[k] for k in ('game_date','event_type','title','body','confidence','date_kind')})
        planets={int(r['planet_id']):str(r['name']) for r in conn.execute('SELECT planet_id,name FROM world_registry WHERE campaign_id=?',(campaign_id,))}
        for row in conn.execute('SELECT game_date, event_type, planet_id, title, body, date_kind, confidence FROM world_history_events WHERE campaign_id=? AND event_type IN ("governor_changed","designation_changed") ORDER BY game_date,id',(campaign_id,)):
            events.append({**{k:row[k] for k in ('game_date','event_type','title','body','date_kind','confidence')},
                           'planet':planets.get(row['planet_id'],'Unknown world')})
        for leader in leaders.values():
            for e in leader['events']:
                if e['event_type'] in ('leader_council_changed','leader_became_ruler','leader_left_rulership'):
                    events.append(dict(e))
        events.sort(key=lambda e:(e['game_date'],e['title']))
        confirmed=sum(1 for leader in leaders.values() if leader.get('status')=='dead_confirmed')
        offices=[{'leader_id':v['leader_id'],'name':v['name'],'office':v['latest_council_role'],
                  'last_seen_date':v['last_seen_date'],'status':v['status']}
                 for v in leaders.values() if v.get('latest_council_role')]
        offices.sort(key=lambda r:(r['office'],r['last_seen_date'],r['name']))
        governors=[{'leader_id':v['leader_id'],'name':v['name'],'assignment':v['latest_assignment'],
                    'last_seen_date':v['last_seen_date'],'status':v['status']}
                   for v in leaders.values() if str(v.get('latest_assignment') or '').startswith('Planet: ')]
        governors.sort(key=lambda r:(r['assignment'],r['last_seen_date'],r['name']))
        return {'campaign':dict(campaign),'leaders':list(leaders.values()),'rulers':terms,'government_events':events,
                'offices':offices,'governors':governors,
                'confirmed_deaths':confirmed,'career_event_count':sum(len(x['events']) for x in leaders.values())}


HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Government & People — Stellaris Historian</title><style>
:root{color-scheme:dark;font-family:system-ui,Segoe UI,sans-serif;background:#0c1521;color:#ecf2f8}*{box-sizing:border-box}body{margin:0}a{color:#e3b978}.mast{background:linear-gradient(125deg,#1d374b,#111f30);padding:34px max(24px,calc((100vw - 1220px)/2));border-bottom:1px solid #405168}.kicker{text-transform:uppercase;letter-spacing:.2em;font-size:11px;color:#e3b978;font-weight:700}h1,h2,h3{font-family:Georgia,serif;font-weight:500}h1{font-size:clamp(32px,4vw,48px);margin:10px 0}h2{font-size:26px;margin:0 0 8px}h3{font-size:21px;margin:0 0 12px}p{line-height:1.65;color:#cad8e4}.meta{font-size:13px;color:#9eb6c7}.nav{display:flex;gap:16px;flex-wrap:wrap;font-size:14px}main{max-width:1240px;padding:26px 18px 90px;margin:auto}.stats{display:flex;gap:10px;flex-wrap:wrap}.stat{border:1px solid #39516b;border-radius:10px;background:#172b3d;padding:12px 20px;min-width:150px}.stat strong{font-size:28px;display:block;font-family:Georgia,serif}.stat small{color:#a6bdcd}.note{font-size:13px;padding:12px 16px;border-left:3px solid #c5a25e;background:#1a2937}.section{margin-top:30px}.rulers{display:flex;gap:10px;overflow-x:auto;padding:5px 0 14px}.ruler{background:#182c3f;min-width:225px;border:1px solid #3b5268;border-radius:9px;padding:16px}.ruler strong{display:block;margin:8px 0;font-size:16px}.filters{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:16px 0}input,select,button{border:1px solid #486077;border-radius:7px;color:#e9f1f7;background:#182b3d;padding:11px 13px;font:inherit}input{flex:1;min-width:180px}button{cursor:pointer}button:hover,.person:hover{background:#26415b}.work{display:grid;grid-template-columns:minmax(240px,340px) 1fr;gap:16px}.people{border:1px solid #364e65;border-radius:10px;overflow:auto;max-height:760px;background:#122338}.person{display:block;width:100%;border:0;border-bottom:1px solid #293d51;background:transparent;text-align:left;border-radius:0;padding:11px 16px}.person.selected{border-left:4px solid #d6ad69;background:#22394e}.person small{display:block;color:#9eb1c3;margin-top:3px}.detail,.gov-list{background:#132437;border:1px solid #3a5068;border-radius:10px;padding:20px;min-width:0}.tags{display:flex;flex-wrap:wrap;gap:6px}.tag{border:1px solid #5b6e7c;color:#e4d1ae;border-radius:20px;font-size:12px;padding:5px 9px;background:#273541}.entry{padding:13px 0;border-top:1px solid #33475c}.entry strong{color:#eac78e}.entry p{margin:5px 0 0}.rowmeta{font-size:12px;color:#a7b8c9}.columns{display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:8px;margin:14px 0}.cell{padding:10px;border:1px solid #31465d;border-radius:7px;overflow-wrap:anywhere}.cell small{display:block;color:#a9bbc9;font-size:11px}.cell b{font-size:13px;font-weight:500}#gov{margin-top:20px}.gov-list{max-height:640px;overflow:auto}#profile:empty:before{content:'Select a person to inspect their career.';color:#abc}@media(max-width:740px){.work{grid-template-columns:1fr}.people{max-height:280px}.mast{padding:22px}.rulers{overflow:auto}}
</style>
<link rel="stylesheet" href="/static/historian-theme.css?v=087">
<script src="/static/historian-theme.js?v=087"></script>
</head><body><header class="mast"><nav class="nav"><a href="/campaign">Campaign</a><a href="/timeline">The Imperial Annals</a><a href="/civic-frontier-history">Civic & Frontier History</a><a href="/database">Database Explorer</a><a href="/government-census">Annual Census</a></nav><div class="kicker" style="margin-top:24px">Historical Observatory · Government & People</div><h1 id="empire"></h1><p>Rulers, council members, governors, commanders, scientists and envoys — their appointments, traits, careers and recorded fates.</p><div class="stats" id="stats"></div></header><main><p class="note">Historical evidence rules: recruitment is not birth; the first appearance is not necessarily the actual appointment; leaving office is not death. Confirmed death notifications retain their own exact dates. Traits shown in each profile are the latest recorded traits, not necessarily traits held at recruitment.</p><section class="section"><h2>Leadership succession</h2><p class="meta">Date ranges represent surviving observations, not necessarily exact dates of accession or departure.</p><div class="rulers" id="rulers"></div></section><section class="section"><h2>Offices and administrations</h2><p class="meta">These are last recorded roles held by each individual, not a claim that all served simultaneously. Choose a name to view the actual appointment sequence.</p><h3>Council</h3><div id="offices" class="rulers"></div><h3>Planetary assignments</h3><div id="governors" class="rulers"></div></section><section class="section"><h2>Register of service</h2><div class="filters"><input id="search" placeholder="Search names, traits, assignments or offices"><select id="class"><option value="">All roles</option></select><select id="status"><option value="">All statuses</option><option value="present">Present</option><option value="dead_confirmed">Confirmed dead</option><option value="missing_unconfirmed">Absent — unknown fate</option><option value="tombstoned_unconfirmed">Removed — unknown fate</option></select></div><div class="work"><div class="people" id="people"></div><section class="detail" id="profile"></section></div></section><section id="gov" class="section"><h2>Political and administrative changes</h2><p class="meta">The dated supporting ledger, distinct from the main historical prose.</p><div class="filters"><input id="government-search" placeholder="Search policies, governors, council or government events"></div><div id="gov-list" class="gov-list"></div></section></main><script id="payload" type="application/json">__DATA__</script><script>
'use strict'; const data=JSON.parse(document.getElementById('payload').textContent); const byId=Object.fromEntries(data.leaders.map(p=>[String(p.leader_id),p]));
const el=(tag,cl,text)=>{const n=document.createElement(tag);if(cl)n.className=cl;if(text!==undefined)n.textContent=String(text);return n};const add=(par,...els)=>{els.forEach(n=>par.append(n));return par};
const date=d=>d?String(d).replace(/^(\d{4})\.(\d{2})\.(\d{2})$/,'$3.$2.$1'):'not established';
const statusLabel={present:'In active service at last observation',dead_confirmed:'Death confirmed',missing_unconfirmed:'No longer listed; fate unknown',tombstoned_unconfirmed:'Removed from active record; fate unknown'};
function detailCell(box,label,val){const n=el('div','cell');add(n,el('small','',label),el('b','',val==null||val===''?'Not established':val));box.append(n)}
const s=document.getElementById('stats');for(const [v,l] of [[data.leaders.length,'Leaders'],[data.career_event_count,'Career events'],[data.confirmed_deaths,'Confirmed deaths'],[data.rulers.length,'Observed ruler terms']]){const b=el('div','stat');add(b,el('strong','',v),el('small','',l));s.append(b)}
document.getElementById('empire').textContent=data.campaign.empire_name;
const rul=document.getElementById('rulers');for(const t of data.rulers){let b=el('div','ruler');add(b,el('small','meta',t.date_kind==='archive_opening'?'Opening ruler':'Later ruler'),el('strong','',t.name),el('div','rowmeta','First observed: '+date(t.first_observed)),el('div','rowmeta',t.last_observed?'Last confirmed in office: '+date(t.last_observed):'No later observation available'));if(byId[String(t.leader_id)]){const btn=el('button','','View biography');btn.onclick=()=>{show(t.leader_id);document.getElementById('profile').scrollIntoView({behavior:'smooth',block:'start'})};b.append(btn)}rul.append(b)}
function officeCards(target, rows, label){const host=document.getElementById(target);if(!rows.length){host.append(el('p','meta','No named appointments retained'));return}for(const p of rows){const n=el('div','ruler');add(n,el('small','meta',label),el('strong','',p.name),el('div','',p.office||p.assignment),el('div','rowmeta','Last recorded: '+date(p.last_seen_date)));const btn=el('button','','Biography');btn.onclick=()=>{show(p.leader_id);document.getElementById('profile').scrollIntoView({behavior:'smooth',block:'start'})};n.append(btn);host.append(n)}}officeCards('offices',data.offices,'Council office');officeCards('governors',data.governors,'Planetary assignment');
let selected=null;let shown=[];const roles=[...new Set(data.leaders.map(p=>p.leader_class).filter(Boolean))].sort();for(const r of roles){const o=el('option','',r);o.value=r;document.getElementById('class').append(o)}
function renderList(){const q=document.getElementById('search').value.trim().toLocaleLowerCase(),role=document.getElementById('class').value,st=document.getElementById('status').value,box=document.getElementById('people');box.replaceChildren();shown=data.leaders.filter(p=>(!role||p.leader_class===role)&&(!st||p.status===st)&&(!q||[p.name,p.leader_class,p.latest_assignment,p.latest_council_role,...p.traits].join(' ').toLocaleLowerCase().includes(q)));for(const p of shown){const b=el('button','person'+(selected===p.leader_id?' selected':''));add(b,el('span','',p.name),el('small','',`${p.leader_class} · ${p.first_seen_date} · ${statusLabel[p.status]||p.status}`));b.onclick=()=>show(p.leader_id);box.append(b)}if(!shown.length)box.append(el('p','meta','No matching people'))}
function show(id){selected=Number(id);renderList();const p=byId[String(id)];if(!p)return;const box=document.getElementById('profile');box.replaceChildren();add(box,el('div','kicker','Career biography'),el('h3','',p.name),el('p','meta',`${p.leader_class} · ${statusLabel[p.status]||p.status}`));const fields=el('div','columns');detailCell(fields,'Recruitment date',date(p.recruitment_date));detailCell(fields,'First archived appearance',date(p.first_seen_date));detailCell(fields,'Last active appearance',date(p.last_seen_date));detailCell(fields,'Last recorded assignment',p.latest_assignment);detailCell(fields,'Last recorded council position',p.latest_council_role);detailCell(fields,'Latest level',p.latest_level);detailCell(fields,'Species',p.deep?.species_name);detailCell(fields,'Ethic',p.deep?.ethic_name);detailCell(fields,'Recorded occupation',p.deep?.job_name);detailCell(fields,'Recorded background world',p.deep?.background_planet_name);if(p.status==='dead_confirmed'){detailCell(fields,'Confirmed death date',p.deep?.death_date?date(p.deep.death_date):'Confirmed, exact date unavailable');detailCell(fields,'Cause (if recorded)',p.deep?.death_reason_value)}box.append(fields);box.append(el('h3','','Latest traits'));const tags=el('div','tags');for(const trait of p.traits){tags.append(el('span','tag',trait))}if(!p.traits.length)tags.append(el('span','meta','No traits retained'));box.append(tags);add(box,el('h3','','Chronological career'),el('p','meta',`${p.events.length} retained career event(s) — dates reflect their original evidence types.`));for(const e of p.events){const n=el('article','entry');add(n,el('strong','',`${date(e.game_date)} · ${e.title}`),el('div','rowmeta',`${e.date_kind} · ${e.confidence}`),el('p','',e.body));box.append(n)}if(!p.events.length)box.append(el('p','meta','No individual career transitions retained.'))}
['search','class','status'].forEach(id=>document.getElementById(id).addEventListener('input',renderList));renderList();if(data.leaders.length)show(data.leaders[0].leader_id);
function government(){const q=document.getElementById('government-search').value.trim().toLocaleLowerCase(),box=document.getElementById('gov-list');box.replaceChildren();let filtered=data.government_events.filter(e=>!q||[e.title,e.body,e.game_date,e.event_type].join(' ').toLocaleLowerCase().includes(q));for(const e of filtered){const n=el('article','entry');add(n,el('strong','',`${date(e.game_date)} · ${e.title}`),el('div','rowmeta',`${e.date_kind||'observed'} · ${e.confidence||'unrated'}`),el('p','',e.body));box.append(n)}if(!filtered.length)box.append(el('p','meta','No matching political changes'))}
document.getElementById('government-search').addEventListener('input',government);government();
</script></body></html>'''


def render_government_people(db_path: Path, campaign_id: int) -> str:
    data=government_data(db_path,campaign_id)
    encoded=json.dumps(data,ensure_ascii=True,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return HTML.replace('__DATA__',encoded)
