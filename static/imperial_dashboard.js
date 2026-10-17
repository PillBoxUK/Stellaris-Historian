/* Stellaris Historian v0.0.84 — evidence-first read-only visualisation. */
'use strict';
const S = {data:null,range:'all',filters:{event:'all',period:'all',search:''},hidden:{}};
const $ = id => document.getElementById(id);
const el = (tag,css,value) => { const n=document.createElement(tag);if(css)n.className=css;if(value!==undefined)n.textContent=String(value);return n;};
const mk = (parent,...children) => {for(const child of children)parent.append(child);return parent;};
const fmt = value => value==null || !Number.isFinite(Number(value))?'—':new Intl.NumberFormat('en-GB',{maximumFractionDigits:0}).format(value);
const labelDate = value => String(value||'').replace(/^(\d{4})\.(\d{2})\.(\d{2})$/,'$3/$2/$1');
const metricDefs = [
 ['population','Population','◉'],['colonies','Colonised worlds','◈'],['controlled_systems','Controlled systems','⌖'],['known_systems','Charted systems','✧'],
 ['stations','Stations','▣'],['technologies','Researched techs','⚛'],['fleets','Fleets','⋈'],['ships','Ships','➤']
];
const charts = {
 population:{keys:[['population','Population','#e6bd7c']]},
 expansion:{keys:[['controlled_systems','Controlled systems','#e4b76f'],['known_systems','Known systems','#68d3d0'],['colonies','Colonies','#94b0ed']]},
 science:{keys:[['technologies','Researched technologies','#68d3d0']]},
 military:{keys:[['ships','Ships','#e4b76f'],['fleets','Fleets','#94b0ed']]},
 infrastructure:{keys:[['mining_stations','Mining stations','#e4b76f'],['research_stations','Research stations','#68d3d0'],['starbases','Starbases','#94b0ed']]},
 leadership:{keys:[['leaders','Active leaders','#d69bc1']]}
};
function sliceSeries(){if(!S.data)return [];const all=S.data.series||[];if(S.range==='all')return all;const year=Number(S.data.latest_date.slice(0,4));return all.filter(x=>Number(x.date.slice(0,4))>=year-Number(S.range));}
function renderMetrics(){const host=$('metrics');host.replaceChildren();const current=S.data.current||{},series=S.data.series||[],prev=series.length>=2?series[series.length-2]:null;
 for(const [key,title,glyph] of metricDefs){const item=el('article','metric');const a=el('small','',title),number=el('b','',fmt(current[key])),sub=el('span','','Latest processed state'),symbol=el('i','',glyph);
  if(current[key]===null||current[key]===undefined)sub.textContent='Evidence unavailable for latest save';
  else if(prev&&prev[key]!==null&&prev[key]!==undefined){const delta=current[key]-prev[key];const sign=delta>0?'+':'';sub.textContent=(delta===0?'No change':sign+fmt(delta))+' vs previous save';sub.className=delta>0?'positive':delta<0?'negative':'';}
  mk(item,a,number,sub,symbol);host.append(item);
 }
}
function svg(tag,attrs={}){const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,v] of Object.entries(attrs))node.setAttribute(key,String(v));return node;}
function renderChart(key){const host=document.querySelector('[data-chart="'+key+'"]');if(!host)return;host.replaceChildren();const rows=sliceSeries(),settings=charts[key];const hidden=S.hidden[key]||new Set();S.hidden[key]=hidden;
 const legend=el('div','legend');for(const [field,title,color] of settings.keys){const button=el('button','');button.type='button';button.setAttribute('aria-pressed',String(!hidden.has(field)));button.title='Toggle '+title;
  const swatch=el('span','swatch');swatch.style.background=color;mk(button,swatch,el('span','',title));button.onclick=()=>{if(hidden.has(field))hidden.delete(field);else if(settings.keys.length-hidden.size>1)hidden.add(field);renderChart(key);};legend.append(button)}host.append(legend);
 const keys=settings.keys.filter(([k])=>!hidden.has(k));const points=rows.filter(row=>keys.some(([k])=>row[k]!=null));if(points.length<1){host.append(el('div','empty-chart','No verified historical values available for this period.'));return;}
 const W=780,H=265,l=54,r=20,t=17,b=31,iw=W-l-r,ih=H-t-b;
 const numbers=points.flatMap(row=>keys.map(([k])=>row[k]).filter(x=>x!=null&&Number.isFinite(Number(x))).map(Number));if(!numbers.length){host.append(el('div','empty-chart','No values available.'));return;}
 const maximum=Math.max(1,...numbers),max=Math.ceil(maximum*1.08),unit=max/4;
 const x=i=>l+(rows.length<2?iw/2:iw*i/(rows.length-1)),y=value=>t+ih-(Number(value)/max)*ih;
 const drawing=svg('svg',{viewBox:'0 0 '+W+' '+H,preserveAspectRatio:'none',role:'presentation'});
 for(let i=0;i<=4;i++){const at=t+i*ih/4;drawing.append(svg('line',{x1:l,y1:at,x2:W-r,y2:at,class:'plot-grid'}));const text=svg('text',{x:l-9,y:at+4,'text-anchor':'end',class:'plot-axis'});text.textContent=fmt((4-i)*unit);drawing.append(text)}
 const labels=[0,Math.floor((rows.length-1)/4),Math.floor((rows.length-1)/2),Math.floor((rows.length-1)*3/4),rows.length-1];const used=new Set();for(const i of labels){if(used.has(i))continue;used.add(i);const text=svg('text',{x:x(i),y:H-7,'text-anchor':i===0?'start':i===rows.length-1?'end':'middle',class:'plot-axis'});text.textContent=rows[i].date.slice(0,4);drawing.append(text)}
 for(const [field,title,color] of keys){let segment=[];function drawSegment(){if(!segment.length)return;const path=segment.map(([i,v],n)=>(n?'L':'M')+x(i).toFixed(2)+' '+y(v).toFixed(2)).join(' ');if(segment.length>1){let area=path+' L'+x(segment[segment.length-1][0]).toFixed(2)+' '+y(0)+' L'+x(segment[0][0]).toFixed(2)+' '+y(0)+' Z';drawing.append(svg('path',{d:area,fill:color,class:'area'}))}drawing.append(svg('path',{d:path,stroke:color,class:'line'}));segment=[];}
  rows.forEach((row,i)=>{const v=row[field];if(v===null||v===undefined||!Number.isFinite(Number(v))){drawSegment();return;}segment.push([i,Number(v)])});drawSegment();}
 const hoverLine=svg('line',{x1:0,x2:0,y1:t,y2:t+ih,class:'hover-line',visibility:'hidden'});drawing.append(hoverLine);
 const tooltip=el('div','chart-tooltip');tooltip.hidden=true;host.append(drawing,tooltip);
 let focusIndex=null;
 function show(i,px){if(i<0||i>=rows.length)return;focusIndex=i;const row=rows[i];hoverLine.setAttribute('visibility','visible');hoverLine.setAttribute('x1',x(i));hoverLine.setAttribute('x2',x(i));tooltip.replaceChildren(el('b','',row.date));let has=false;for(const [field,title,color] of keys){if(row[field]===null||row[field]===undefined)continue;has=true;const line=el('div','',title+': '+fmt(row[field]));line.style.color=color;tooltip.append(line)}if(!has)tooltip.append(el('div','','No values for this save'));tooltip.hidden=false;tooltip.style.top='41px';tooltip.style.left=(Math.max(8,Math.min(host.clientWidth-170,(px??host.clientWidth/2)-75)))+'px';}
 drawing.addEventListener('pointermove',e=>{const box=drawing.getBoundingClientRect();const relative=(e.clientX-box.left)/box.width*W;const i=rows.length<2?0:Math.max(0,Math.min(rows.length-1,Math.round((relative-l)/iw*(rows.length-1))));show(i,e.clientX-box.left)});
 drawing.addEventListener('pointerleave',()=>{tooltip.hidden=true;hoverLine.setAttribute('visibility','hidden')});
 drawing.setAttribute('tabindex','0');drawing.setAttribute('aria-label','Chart of '+settings.keys.map(x=>x[1]).join(' and ')+'. Use left and right arrow keys to inspect individual saves.');drawing.addEventListener('focus',()=>show(rows.length-1));drawing.addEventListener('blur',()=>{tooltip.hidden=true;hoverLine.setAttribute('visibility','hidden')});drawing.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();show(Math.max(0,Math.min(rows.length-1,(focusIndex??rows.length-1)+(e.key==='ArrowLeft'?-1:1))))}});
}
function renderWorlds(){const host=$('worlds');host.replaceChildren();const worlds=S.data.top_worlds||[];if(!worlds.length){host.append(el('p','muted','No validated world-population evidence is available for the latest processed save.'));return}const max=Math.max(1,...worlds.map(w=>w.population||0));for(const world of worlds){const row=el('div','world-row');const name=el('div','');mk(name,el('div','name',world.name),el('div','meta',[world.system,world.designation].filter(Boolean).join(' · ')));const track=el('div','track'),fill=el('div','fill');fill.style.width=100*(world.population||0)/max+'%';track.append(fill);mk(row,name,track,el('div','value',fmt(world.population)));host.append(row)}}
function renderGovernment(){const host=$('government');host.replaceChildren();const g=S.data.government||{},people=S.data.people||{},ruler=people.ruler;const heading=el('div','head-of-state');heading.append(el('small','','HEAD OF STATE'));heading.append(el('strong','',ruler?.name||g.ruler_name||'Not established'));heading.append(el('div','muted',ruler?.office||g.type||'Office not established'));const traits=el('div','tags');for(const tr of ruler?.traits||[])traits.append(el('span','tag',tr));if(!traits.children.length)traits.append(el('span','muted','Traits unavailable in latest cache'));heading.append(traits);host.append(heading);
 const facts=el('div','state-facts');for(const [k,v] of [['Government',g.type],['Authority',g.authority],['Ethics',(g.ethics||[]).join(', ')||'Not established'],['Civics',(g.civics||[]).join(', ')||'Not established']]){const cell=el('div','fact');mk(cell,el('small','',k),el('strong','',v||'Not established'));facts.append(cell)}host.append(facts);
 const council=el('section','council');council.append(el('h4','','COUNCIL & OFFICES'));for(const p of people.council||[]){const line=el('div','councillor');mk(line,el('strong','',p.name),el('span','',p.office));council.append(line)}if(!(people.council||[]).length)council.append(el('p','muted','No verified council roster in the latest leader cache.'));host.append(council);
}
function renderEvents(){const host=$('event-list');host.replaceChildren();let data=S.data.events||[];const type=S.filters.event,query=S.filters.search.trim().toLowerCase(),period=S.filters.period,year=Number(S.data.latest_date?.slice(0,4)||0);if(period!=='all')data=data.filter(e=>Number(e.date.slice(0,4))>=year-Number(period));if(type!=='all')data=data.filter(e=>e.type===type);if(query)data=data.filter(e=>[e.date,e.title,e.detail,e.type].join(' ').toLowerCase().includes(query));data=data.slice(0,42);
 for(const item of data){const entry=el('article','event');const timing=el('time','',labelDate(item.date));timing.dateTime=item.date.replaceAll('.','-');const info=el('div','');mk(info,el('span','event-kind',item.type),el('div','event-title',''));info.children[1].append(el('strong','',item.title));const detail=el('p','event-detail',item.detail||'');info.append(detail);mk(entry,timing,info);host.append(entry)}
 if(!data.length)host.append(el('p','muted','No matching dated historical developments. Try another category or time range.'));
}
function applyData(obj){S.data=obj;$('empire').textContent=obj.empire||'Imperial Situation Room';$('current-date').textContent=obj.latest_date||'—';$('updated').textContent='Historical state loaded · '+new Date().toLocaleTimeString('en-GB');$('error').hidden=true;
 if(obj.empty){$('error').hidden=false;$('error').textContent=obj.message||'No processed history';return;}
 const c=obj.coverage||{},available=c.core_valid||0,total=c.snapshot_count||0;$('health').textContent=available+'/'+total+' core save caches verified';$('coverage').textContent=`${total} processed archives · ${c.population_points||0} population states · ${c.civic_states||0} frontier states`;
 $('source-note').textContent=`${obj.empire} · Evidence through ${obj.latest_date} · ${fmt(total)} processed saves`;
 renderMetrics();for(const key of Object.keys(charts))renderChart(key);renderWorlds();renderGovernment();renderEvents();
}
let updating=false;
async function refresh(force=false){if(updating)return;updating=true;const b=$('refresh');b.disabled=true;b.textContent='↻ Reading evidence…';try{const response=await fetch('/api/imperial-dashboard'+(force?'?refresh=true':''),{cache:'no-store',headers:{'Accept':'application/json'}});if(!response.ok){let details=await response.text();throw new Error('Historian returned '+response.status+' · '+details.slice(0,150))}applyData(await response.json())}catch(error){$('error').hidden=false;$('error').textContent='Dashboard evidence unavailable: '+error.message;}finally{b.disabled=false;b.textContent='↻ Refresh data';updating=false}}
for(const button of document.querySelectorAll('.time-controls button'))button.addEventListener('click',()=>{for(const other of document.querySelectorAll('.time-controls button'))other.classList.remove('on');button.classList.add('on');S.range=button.dataset.range;for(const key of Object.keys(charts))renderChart(key)});
$('refresh').addEventListener('click',()=>refresh(true));
$('event-filter').addEventListener('change',e=>{S.filters.event=e.target.value;if(S.data)renderEvents()});
$('event-period').addEventListener('change',e=>{S.filters.period=e.target.value;if(S.data)renderEvents()});
$('event-search').addEventListener('input',e=>{S.filters.search=e.target.value;if(S.data)renderEvents()});
window.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
refresh();setInterval(()=>{if(!document.hidden)refresh()},90000);
