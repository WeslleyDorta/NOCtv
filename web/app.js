'use strict';
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const numeric = value => typeof value === 'number' && Number.isFinite(value);
const num = (value, unit = '') => numeric(value) ? new Intl.NumberFormat('en', {maximumFractionDigits: 1}).format(value) + unit : '—';
const icons = {connections:'⌁', switches:'▤', ports:'▦', servers:'▥', printers:'▧', wireless:'◉', devices:'◇', services:'◷', containers:'▣', service:'◷', container:'▣', firewall:'⬡', switch:'▤', server:'▥', printer:'▧', router:'⌁', device:'◇'};
const titles = {connections:'Connections', switches:'Switches', ports:'Ports', servers:'Servers', printers:'Printers', wireless:'Wi-Fi', devices:'Devices', services:'Services', containers:'Containers'};
const descriptions = {connections:'Sites, firewalls and connections in one view', switches:'Discovered links and live interface states', ports:'Required interfaces first; unused ports are not incidents', servers:'Availability and collected system metrics', printers:'Printer availability and supplies when reported', wireless:'Access points and connected clients when reported', devices:'Network inventory grouped by category', services:'HTTP / HTTPS, TCP, DNS and ICMP checks', containers:'Docker runtime, healthchecks and collected resource usage'};
const severity = {down:0, attention:1, unknown:2, standby:3, up:4, disabled:5};
let config, data, view='connections', siteFilter='', dialogState=null, rotate=false, rotateDeadline=0, lastSuccess=0, lastTicker='';
let refreshTimer, refreshPending=false, soundEnabled=false, audioContext, knownCritical=null, rotationBase, hiddenViews=new Set(), diagnosticBusy=false;
const history=new Map();
let motion=localStorage.getItem('noctv-motion')!=='off';
const selected = () => data.devices.filter(d => !siteFilter || d.site===siteFilter);
const state = (value='unknown') => `<span class="state" data-state="${esc(value)}">${esc(value.toUpperCase())}</span>`;
const rate = value => !numeric(value) ? '—' : value>=1e6 ? num(value/1e6,' Mbps') : num(value/1e3,' kbps');
const age = stamp => {const n=(Date.now()-Date.parse(stamp))/1000;return !Number.isFinite(n)?'never':n<60?`${Math.max(0,Math.round(n))}s`:`${Math.floor(n/60)}m`;};
function sites(){const out=[...config.sites];for(const d of data.devices)if(!out.some(s=>s.id===d.site))out.push({id:d.site,name:d.site==='unassigned'?'Unassigned':d.site,city:'Configure a site mapping',kind:'branch',x:20+(out.length%3)*30,y:20+(Math.floor(out.length/3)%3)*30});return out;}
const siteName = id => sites().find(s=>s.id===id)?.name||id;
function safeWeb(value){try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password?u.href:null;}catch{return null;}}
function webLink(d){const url=safeWeb(d.web_url);return url?`<a class="web-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="Open ${esc(d.name)} web interface"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 7h14M5 17h14"/></svg></a>`:'';}
function brandIcon(d){const brand=config.brands?.[d.brand];return brand?.logo?`<img class="brand-logo" src="${esc(brand.logo)}" alt="${esc(brand.name)}" width="28" height="28">`:`<span class="device-icon" aria-hidden="true">${icons[d.type]||'◇'}</span>`;}
function miniPorts(d){const ports=d.ports||[];return ports.length?`<div class="mini-ports" aria-label="${ports.filter(p=>p.state==='up').length} up of ${ports.length} interfaces">${ports.slice(0,48).map(p=>`<span class="mini-port" data-port="${esc(p.id)}" data-state="${esc(p.state)}" title="${esc(p.name)} ${esc(p.state)}"></span>`).join('')}</div>`:'';}
function metric(d){const m=d.metrics||{};for(const [key,label,unit]of [['cpu_percent','CPU','%'],['toner_percent','Toner','%'],['clients','Clients',''],['latency_ms','Latency',' ms']])if(numeric(m[key]))return {key,label,unit,value:m[key]};return {label:'Metrics',unit:'',value:null};}
function meter(label,value,cls=''){
 const valid=numeric(value)&&value>=0&&value<=100;
 return `<div class="resource ${cls}"><span>${esc(label)}</span><strong>${valid?num(value,'%'):'—'}</strong><div class="meter-track" ${valid?`role="meter" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${value}"`:''}>${valid?`<i style="width:${value}%"></i>`:''}</div></div>`;
}
function readings(d){const m=d.metrics||{};return `<div class="readings"><div><small>Latency</small><strong>${num(m.latency_ms,' ms')}</strong></div><div><small>${d.type==='wireless'?'Clients':'Availability'}</small><strong>${d.type==='wireless'?num(m.clients):state(d.state)}</strong></div></div>`;}
function plot(d,key='latency_ms'){
 const samples=(history.get(d.id)||[]).filter(x=>numeric(x[key])),max=Math.max(1,...samples.map(x=>x[key]));
 if(samples.length<2)return `<div class="chart-empty">${d.state==='down'?'Device DOWN · no latency sample':'Collecting response history…'}</div>`;
 const all=history.get(d.id),start=all[0].time,span=Math.max(1,all.at(-1).time-start);let path='',joined=false;
 for(const sample of all){if(!numeric(sample[key])){joined=false;continue;}path+=`${joined?'L':'M'}${2+(sample.time-start)/span*296},${45-sample[key]/max*40} `;joined=true;}
 return `<div class="response-chart"><svg viewBox="0 0 300 50" preserveAspectRatio="none" role="img" aria-label="Collected ${esc(key.replaceAll('_',' '))} history"><path class="chart-axis" d="M2 46H298"/><path class="chart-line" d="${path}"/></svg><span>${Math.round(span/1000)}s observed</span><span>0–${num(max)} ${key==='latency_ms'?'ms':'%'}</span></div>`;
}
function card(d){
 const m=d.metrics||{},kind=d.type,visual=equipmentState(d);
 const instruments=kind==='printer'?`<div class="supplies">${meter('Black / toner',m.toner_percent,'ink-black')}${meter('Cyan',m.toner_cyan_percent,'ink-cyan')}${meter('Magenta',m.toner_magenta_percent,'ink-magenta')}${meter('Yellow',m.toner_yellow_percent,'ink-yellow')}</div>`:kind==='wireless'?`<div class="resources">${meter('CPU',m.cpu_percent)}${meter('Memory',m.memory_percent)}</div>`:kind==='switch'?miniPorts(d):'';
 return `<article class="device-card ${esc(kind)}-card" data-state="${esc(visual)}">${webLink(d)}<span class="card-state">${state(visual)}</span><button class="card-open" data-action="device" data-id="${esc(d.id)}"><span class="card-top">${brandIcon(d)}<span><h3>${esc(d.name)}</h3><span class="meta">${esc(d.ip||'Address not reported')}</span></span></span></button><p class="meta">${esc(siteName(d.site))} · ${esc(d.model||kind)}</p>${instruments}${readings(d)}${kind==='printer'?'':plot(d)}</article>`;
}
const bytes = value => !numeric(value)?'—':value>=1e12?num(value/1e12,' TB'):num(value/1e9,' GB');
function capacity(label,value,total,unit,cls){
 const valid=numeric(value)&&value>=0&&value<=100&&numeric(total)&&total>0,format=v=>unit==='MHz'?num(v/1000,' GHz'):bytes(v);
 return `<div class="capacity-resource ${cls}">${meter(label,value)}<div class="capacity-details"><span>Used ${valid?format(total*value/100):'—'}</span><span>Free ${valid?format(total*(1-value/100)):'—'}</span><span>Total ${numeric(total)?format(total):'—'}</span></div></div>`;
}
function capacityStrip(m){return `<div class="server-capacity">${capacity('CPU',m.cpu_percent,m.cpu_capacity_mhz,'MHz','cpu')}${capacity('Memory',m.memory_percent,m.memory_total_bytes,'bytes','memory')}${capacity('Storage',m.disk_percent,m.disk_total_bytes,'bytes','storage')}</div>`;}
function serverCard(d){
 const m=d.metrics||{},h=d.hardware||{},storage=Array.isArray(d.storage)?d.storage:[],health=equipmentState(d);
 const field=(label,value)=>`<div><small>${label}</small><strong>${value}</strong></div>`;
 return `<article class="device-card server-card" data-state="${esc(health)}"><header class="server-head">${webLink(d)}<button class="card-open" data-action="device" data-id="${esc(d.id)}"><h3>${esc(d.name)} · ${esc(d.model||'Server')}</h3><span class="meta">${esc(d.ip||'Address not reported')} · ${esc(siteName(d.site))}</span></button>${state(health)}</header>${capacityStrip(m)}<div class="storage-brief">${storage.length?`${storage.length} datastores · ${storage.filter(x=>x.used_percent>=85).length} high usage`:'Storage not reported'} · Hardware ${state(h.state||'unknown')}</div><div class="hardware-readings">${field('Host',state(d.state))}${field('Management',state(d.management_state||'unknown'))}${field('Hardware',state(h.state||'unknown'))}${field('Power',num(m.power_watts,' W'))}${field('Processor',esc(h.processor||'Not reported'))}${field('Temperature',num(m.temperature_celsius,' °C'))}${field('Fans',`${num(h.fan_count)} ${state(h.fan_state||'unknown')}`)}${field('Power supplies',`${num(h.power_supply_count)} ${state(h.power_supply_state||'unknown')}`)}</div><div class="storage-panel"><div class="storage-heading"><h3>RAID and physical drives</h3><span>${num(h.drive_count)} drives ${state(h.drive_state||'unknown')}</span></div><div class="storage-heading"><h3>Datastores</h3><span>${storage.length||'Not reported'}</span></div><div class="datastores">${storage.map(x=>`<div class="datastore ${x.used_percent>=85?'storage-warning':''}">${meter(x.name,x.used_percent)}<div class="capacity-details"><span>Free ${numeric(x.capacity_bytes)&&numeric(x.used_percent)?bytes(x.capacity_bytes*(1-x.used_percent/100)):'—'}</span><span>Total ${bytes(x.capacity_bytes)}</span></div></div>`).join('')||'<p class="note">No storage inventory reported by this source</p>'}</div></div></article>`;
}
function serverHistory(ds){
 const series=[['cpu_percent','CPU','cpu'],['memory_percent','Memory','memory'],['disk_percent','Storage','storage']];
 const times=[...new Set(ds.flatMap(d=>(history.get(d.id)||[]).map(p=>p.time)))].sort((a,b)=>a-b),start=times[0],end=times.at(-1),span=Math.max(1,end-start);
 const lines=series.map(([key,label,cls])=>{let path='',joined=false;for(const time of times){const values=ds.map(d=>history.get(d.id)?.find(p=>p.time===time)?.[key]).filter(numeric);if(!values.length){joined=false;continue;}const value=values.reduce((a,b)=>a+b,0)/values.length;path+=`${joined?'L':'M'}${30+(time-start)/span*850},${120-value} `;joined=true;}return `<path class="resource-line ${cls}" d="${path}"/>`;}).join('');
 return `<section class="server-history"><div><h2>Resource history</h2><p>${times.length>1?Math.round(span/1000)+'s observed this session':'Waiting for collected samples'}</p><div class="chart-legend">${series.map(([,label,cls])=>`<span class="${cls}">${label}</span>`).join('')}</div><small>Mean of reported hosts</small></div><svg viewBox="0 0 920 150" preserveAspectRatio="none" role="img" aria-label="Collected CPU, memory and storage history">${[0,25,50,75,100].map(n=>`<text x="0" y="${124-n}">${n}%</text><path class="history-grid" d="M30 ${120-n}H900"/>`).join('')}${times.length>1?lines:''}</svg></section>`;
}
function siteCard(s){
 const ds=data.devices.filter(d=>d.site===s.id),fw=ds.filter(d=>d.type==='firewall'),routers=ds.filter(d=>d.type==='router');
 const row=(label,address,st,value='')=>`<div class="site-reading"><div><span>${esc(label)}</span><small>${esc(address||'Address not reported')}</small></div><div>${value?`<strong>${value}</strong>`:''}${state(st)}</div></div>`;
 return `<article class="site-card" data-state="${siteState(s.id)}"><button class="site-head" data-action="site" data-id="${esc(s.id)}"><span><h3>${esc(s.name)}</h3><small>${esc(s.city||s.kind||'Site')}</small></span>${state(siteState(s.id))}</button><h4>Firewall · reported availability</h4>${fw.map(d=>row(d.vendor||d.name,d.ip,d.state,num(d.metrics?.latency_ms,' ms'))).join('')||'<p class="note">No firewall mapped to this site</p>'}<h4>Network interfaces</h4>${fw.flatMap(d=>(d.ports||[]).slice(0,3).map(p=>row(p.description||p.name,p.name,p.state,num(p.speed_mbps,' Mbps')))).join('')||routers.map(d=>row(d.name,d.ip,d.state)).join('')||'<p class="note">No interfaces reported</p>'}<div class="site-foot"><span>${ds.length} devices</span><span>${ds.filter(d=>d.state==='up').length} UP · ${ds.filter(d=>d.state==='down').length} DOWN</span></div></article>`;
}

function siteState(id){const all=data.devices.filter(d=>d.site===id);if(!all.length)return 'unknown';if(all.every(d=>d.state==='down'))return 'down';if(all.every(d=>d.state==='unknown'))return 'unknown';return all.some(d=>['down','unknown','attention'].includes(d.state))?'attention':'up';}
function cloud(st){return `<span class="site-symbol cloud" data-state="${st}"><svg viewBox="0 0 60 44" aria-hidden="true"><path d="M15 34C0 34 0 14 14 12C17-3 40-3 44 14C59 12 61 34 46 34Z"/><path d="M23 19h14v5H23zm0 8h14v5H23z"/></svg></span>`;}
function edge(a,b,link,flow=false){const dx=b.x-a.x,dy=b.y-a.y;const path=`M${a.x} ${a.y} C${a.x+dx*.45} ${a.y} ${a.x+dx*.55} ${b.y} ${b.x} ${b.y}`;return `<path class="edge" data-state="${esc(link.state)}" d="${path}"/>${flow?`<path class="flow" data-state="${esc(link.state)}" d="${path}"/>`:''}`;}
function connections(){
 const units=sites(),geographic=config.map?.mode!=='schematic'&&config.map?.positions,byId=new Map(data.devices.map(d=>[d.id,d])),positions=new Map(units.filter(s=>!geographic||geographic[s.id]).map(s=>[s.id,geographic?{x:50,y:50}:s]));
 const links=data.links.filter(l=>byId.get(l.a)?.site!==byId.get(l.b)?.site&&positions.has(byId.get(l.a)?.site)&&positions.has(byId.get(l.b)?.site));
 const paths=links.map(l=>edge(positions.get(byId.get(l.a).site),positions.get(byId.get(l.b).site),l,numeric(l.traffic_bps)&&l.traffic_bps>0)).join('');
 const nodes=units.filter(s=>positions.has(s.id)).map(s=>{const st=siteState(s.id),p=positions.get(s.id);return `<button class="graph-node ${s.kind==='cloud'?'cloud-node':''}" data-action="site" data-id="${esc(s.id)}" style="left:${p.x}%;top:${p.y}%" data-state="${st}" aria-label="Open ${esc(s.name)}">${s.kind==='cloud'?cloud(st):'<span class="site-symbol"><i></i></span>'}<h3>${esc(s.name)}</h3><small>${esc(s.city||'')}</small></button>`;}).join('');
 const shown=units.filter(s=>!siteFilter||s.id===siteFilter),left=shown.filter(s=>['headquarters','cloud'].includes(s.kind)),right=shown.filter(s=>!left.includes(s));
 if(!left.length&&right.length)left.push(right.shift());
 const strip=links.slice(0,6).map(l=>`<div class="link-summary"><div>${esc(siteName(byId.get(l.a).site))} ↔ ${esc(siteName(byId.get(l.b).site))}<small>${num(l.latency_ms,' ms')} · loss ${num(l.loss_percent,'%')} · ${rate(l.traffic_bps)}</small></div><span>${esc((l.kind||'link').toUpperCase())} ${state(l.state)}</span></div>`).join('');
 return `<div class="connections"><aside class="site-list site-left">${left.map(siteCard).join('')}</aside><section class="map-panel"><div class="panel-head"><div><h2>Network between sites</h2><p>Firewalls, branches and VPN tunnels</p></div><small>${geographic?esc(config.map.label):'Schematic'} · ${links.length} reported links</small></div><div class="graph${geographic?' geographic':''}">${geographic?'<svg class="country-layer" aria-hidden="true"></svg>':''}<svg class="edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">${paths}</svg>${nodes}</div><div class="link-strip">${strip||'<p class="note">No inter-site links reported. Site placement does not imply a connection.</p>'}</div><p class="map-caption">${geographic?`${esc(config.map.regions?.length?'IBGE / Natural Earth':'Natural Earth')} · ${units.length-positions.size} sites outside this map or without coordinates`:'Schematic positions'}<span>Flow is illustrative; shown when traffic is reported</span></p></section><aside class="site-list site-right">${right.map(siteCard).join('')}</aside></div>`;
}

function layoutGeography(){
 const graph=$('.geographic');if(!graph)return;
 const map=config.map,[west,north,east,south]=map.bounds,w=graph.clientWidth,h=graph.clientHeight;
 const scale=Math.min(Math.max(1,w-160)/Math.max(.001,east-west),Math.max(1,h-36)/Math.max(.001,south-north));
 const tx=(w-(east-west)*scale)/2-west*scale,ty=(h-(south-north)*scale)/2-north*scale;
 const layer=graph.querySelector('.country-layer');layer.setAttribute('viewBox',`0 0 ${w} ${h}`);
 layer.innerHTML=`<g transform="translate(${tx} ${ty}) scale(${scale})">${[...map.outlines,...(map.regions||[])].map(o=>`<path class="${o.region?'region':''} ${o.active?'active-region':''}" data-country="${esc(o.id)}" d="${esc(o.path)}"/>`).join('')}</g>`;
 const points=new Map(Object.entries(map.positions).map(([id,p])=>[id,{x:(p.x*scale+tx)/w*100,y:(p.y*scale+ty)/h*100}]));
 for(const node of graph.querySelectorAll('[data-action="site"]')){const p=points.get(node.dataset.id);node.style.left=p.x+'%';node.style.top=p.y+'%';}
 const byId=new Map(data.devices.map(d=>[d.id,d]));
 graph.querySelector('.edges').innerHTML=data.links.filter(l=>byId.get(l.a)?.site!==byId.get(l.b)?.site&&points.has(byId.get(l.a)?.site)&&points.has(byId.get(l.b)?.site)).map(l=>edge(points.get(byId.get(l.a).site),points.get(byId.get(l.b).site),l,numeric(l.traffic_bps)&&l.traffic_bps>0)).join('');
}
function switchGraph(){
 const ds=selected().filter(d=>d.type==='switch').sort((a,b)=>Number(b.root)-Number(a.root)||a.name.localeCompare(b.name));
 const shown=ds.slice(0,config.display.max_cards),ids=new Set(shown.map(d=>d.id)),edges=data.links.filter(l=>ids.has(l.a)&&ids.has(l.b));
 $('#coverage').textContent=`${shown.length}/${ds.length} switches · ${edges.length} discovered links · generic interface panels`;
 if(!shown.length)return '<div class="empty">No switches in this scope. Configure device types in your connector.</div>';
 const levels=new Map(),queue=[];for(const d of shown.filter(d=>d.root)){levels.set(d.id,0);queue.push(d.id);}if(!queue.length){levels.set(shown[0].id,0);queue.push(shown[0].id);}
 for(let i=0;i<queue.length;i++)for(const l of edges){const next=l.a===queue[i]?l.b:l.b===queue[i]?l.a:null;if(next&&!levels.has(next)){levels.set(next,levels.get(queue[i])+1);queue.push(next);}}
 for(const d of shown)if(!levels.has(d.id))levels.set(d.id,0);
 const max=Math.max(...levels.values(),1),rows=new Map(),position=new Map();for(const d of shown){const level=levels.get(d.id);if(!rows.has(level))rows.set(level,[]);rows.get(level).push(d);}
 for(const [level,items]of rows)items.forEach((d,i)=>position.set(d.id,{x:level/max*76+12,y:(i+1)/(items.length+1)*100}));
 const paths=edges.map(l=>{let a=position.get(l.a),b=position.get(l.b);if(a.x>b.x)[a,b]=[b,a];return `<g data-a="${esc(l.a)}" data-b="${esc(l.b)}">${edge(a,b,l,l.state==='up')}</g>`;}).join('');
 const nodes=shown.map(d=>{const p=position.get(d.id),ports=d.ports||[];return `<article class="graph-node switch-node" data-device="${esc(d.id)}" data-state="${esc(d.state)}" style="left:${p.x}%;top:${p.y}%">${webLink(d)}<button data-action="device" data-id="${esc(d.id)}"><span class="switch-label">${brandIcon(d)}<h3>${esc(d.name)}</h3><small>${esc(d.ip||'')}</small></span><div class="switch-chassis"><span class="chassis-led" data-state="${esc(d.state)}"></span>${miniPorts(d)}</div><span class="switch-foot"><span>${d.root?'Root · ':''}${state(d.state)}</span><small>${ports.filter(p=>p.state==='up').length} UP · ${ports.filter(p=>p.state==='down').length} DOWN</small></span></button></article>`;}).join('');
 const affected=ds.filter(d=>d.state==='down'||d.ports?.some(p=>p.required&&p.state==='down'));
 return `<div class="switch-health"><section><h3>Network availability</h3><div class="health-reading"><span>Switches online / monitored</span><strong>${ds.filter(d=>d.state==='up').length} / ${ds.length}</strong></div><div class="health-reading"><span>Interfaces requiring attention</span><strong class="bad">${ds.flatMap(d=>d.ports||[]).filter(p=>p.required&&p.state==='down').length}</strong></div></section><section><h3>Affected switches</h3><p>${affected.length?affected.map(d=>esc(d.name)).join(' · '):'No required interfaces reported DOWN'}</p></section><section><h3>Collection health</h3><p>${data.sources.map(x=>`${esc(x.id)} · ${esc(x.state)} · ${age(x.last_success)}`).join('<br>')}</p></section></div><section class="switch-map"><div class="panel-head"><div><h2>Network branches</h2><p>Discovered links and current port states</p></div><small>Arrows indicate hierarchy; flow is illustrative</small></div><div class="graph"><svg class="edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="context-stroke"/></marker></defs>${paths}</svg>${nodes}</div><div class="map-legend">${['up','down','disabled','unknown'].map(state).join('')}<span>Panels show logical interfaces; open a switch for port details</span></div></section>`;
}

function layoutSwitchEdges(){
 const graph=$('.switch-map .graph');if(!graph)return;
 const rect=graph.getBoundingClientRect(),nodes=new Map([...graph.querySelectorAll('.switch-node')].map(n=>[n.dataset.device,n.getBoundingClientRect()]));
 for(const group of graph.querySelectorAll('g[data-a]')){
  let a=nodes.get(group.dataset.a),b=nodes.get(group.dataset.b);if(!a||!b)continue;
  if(a.left>b.left||a.left===b.left&&a.top>b.top)[a,b]=[b,a];
  const vertical=Math.abs(a.left-b.left)<1;
  const ax=((vertical?a.left+a.width/2:a.right)-rect.left)/rect.width*100,ay=((vertical?a.bottom:a.top+a.height/2)-rect.top)/rect.height*100;
  const bx=((vertical?b.left+b.width/2:b.left)-rect.left)/rect.width*100,by=((vertical?b.top:b.top+b.height/2)-rect.top)/rect.height*100;
  const dx=bx-ax,path=`M${ax} ${ay} C${ax+dx*.45} ${ay} ${ax+dx*.55} ${by} ${bx} ${by}`;
  for(const line of group.querySelectorAll('path'))line.setAttribute('d',path);
 }
}

function portTable(){
 const rows=selected().flatMap(d=>(d.ports||[]).map(p=>({d,p})));
 const down=rows.filter(({p})=>p.state==='down'&&p.required).sort((a,b)=>Number(b.p.required)-Number(a.p.required));
 const slow=rows.filter(({p})=>p.state==='up'&&numeric(p.speed_mbps)&&p.speed_mbps>0&&p.speed_mbps<1000);
 const limit=Math.max(2,Math.min(6,config.display.max_cards,Math.floor(($('#stage').clientHeight-100)/61)));
 const panel=(title,hint,list,kind)=>`<section class="port-table-panel ${kind}"><div class="panel-head"><div><h2>${title}</h2><p>${hint}</p></div><span class="badge">${list.length} interfaces</span></div><div class="table-wrap"><table><thead><tr><th>Switch / interface</th><th>Destination</th><th>State / speed</th></tr></thead><tbody>${list.slice(0,limit).map(({d,p})=>`<tr><td><button data-action="device" data-id="${esc(d.id)}" data-port="${esc(p.id)}">${esc(d.name)} · ${esc(p.name)}</button><small>${esc(siteName(d.site))}</small></td><td>${esc(p.neighbors?.map(n=>n.name).join(', ')||p.description||'Not reported')}<small>${p.required?'Required interface':'No critical DOWN policy'}</small></td><td>${state(p.state)}<small>${num(p.speed_mbps,' Mbps')}</small></td></tr>`).join('')}</tbody></table>${list.length?'':`<p class="empty">No ${title.toLowerCase()} reported</p>`}</div><p class="note">${Math.min(limit,list.length)} / ${list.length} interfaces · required first</p></section>`;
 $('#coverage').textContent=`${rows.length} interfaces · ${down.filter(({p})=>p.required).length} required DOWN · ${rows.filter(({p})=>p.state==='down'&&!p.required).length} DOWN without critical policy`;
 return `<div class="ports-workspace">${panel('Required ports DOWN','Unused ports are counted in the summary, without critical alerts',down,'down-panel')}${panel('Low speed','Active interfaces negotiated below 1 Gbps',slow,'speed-panel')}</div>`;
}

function monitorCard(d){
 const m=d.metrics||{},container=d.type==='container';
 const facts=container?[['Runtime',d.runtime_state||'unknown'],['Healthcheck',d.health_state||'unknown'],['Restarts',num(m.restart_count)]]:[['Response',num(m.latency_ms,' ms')],['HTTP status',num(m.http_status_code)],['TLS validity',num(m.certificate_days,' days')]];
 return `<article class="device-card monitor-card" data-state="${esc(d.state)}">${webLink(d)}<span class="card-state">${state(d.state)}</span><button class="card-open" data-action="device" data-id="${esc(d.id)}"><span class="card-top">${brandIcon(d)}<span><h3>${esc(d.name)}</h3><span class="meta">${esc(d.category||d.model)}</span></span></span></button><p class="meta">${esc(siteName(d.site))}${d.ip?' · '+esc(d.ip):''}</p><div class="monitor-facts">${facts.filter(([label])=>container||label==='Response'||label==='HTTP status'&&numeric(m.http_status_code)||label==='TLS validity'&&numeric(m.certificate_days)).map(([label,value])=>`<div><small>${label}</small><strong>${esc(value)}</strong></div>`).join('')}</div>${container?`<div class="resources">${meter('Host CPU share',m.cpu_percent)}${meter('Memory',m.memory_percent)}</div>`:plot(d)}<p class="monitor-reason">${esc(d.stale?'Telemetry unavailable':(d.services||[]).map(x=>x.name).join(' · ')||(container?'Runtime is not an application availability check.':'Status reported by monitoring source.'))}</p><small class="monitor-observed">Observed ${esc(age(d.observed_at))} ago</small></article>`;
}
const equipmentKinds={servers:['server'],printers:['printer'],wireless:['wireless'],devices:['device','router','firewall'],services:['service'],containers:['container']};
function equipmentState(d){return d.state==='up'&&(d.type==='server'&&(d.metrics?.disk_percent>=85||d.metrics?.memory_percent>=90||d.storage?.some(x=>x.used_percent>=85))||d.type==='printer'&&numeric(d.metrics?.toner_percent)&&d.metrics.toner_percent<20)?'attention':d.state;}
function equipmentRows(){return selected().filter(d=>equipmentKinds[view]?.includes(d.type)).sort((a,b)=>severity[equipmentState(a)]-severity[equipmentState(b)]||a.type.localeCompare(b.type)||a.name.localeCompare(b.name));}
function devicesGrid(){
 const rows=equipmentRows(),shown=rows.slice(0,config.display.max_cards);
 $('#coverage').textContent=`${shown.length}/${rows.length} devices · incidents first · missing measurements are not inferred`;
 if(!rows.length)return `<div class="empty">No ${esc(titles[view].toLowerCase())} reported in this scope. Configure device categories in your connector.</div>`;
 if(view==='servers')return `<div class="adaptive-equipment"><div class="servers-grid">${shown.map(serverCard).join('')}</div></div>${serverHistory(rows)}`;
 if(view==='devices'){
  const groups=new Map();for(const d of shown){const name=d.category||({firewall:'Firewalls',router:'Routers'}[d.type])||'Other devices';if(!groups.has(name))groups.set(name,[]);groups.get(name).push(d);}
  return `<div class="adaptive-equipment"><div class="device-categories">${[...groups].map(([name,ds])=>`<section class="equipment-category"><div class="category-head"><h2>${esc(name)}</h2><span>${ds.length} devices</span></div><div class="category-grid">${ds.map(card).join('')}</div></section>`).join('')}</div></div>`;
 }
 return `<div class="adaptive-equipment"><div class="grid equipment-grid ${view}-grid">${shown.map(d=>['service','container'].includes(d.type)?monitorCard(d):card(d)).join('')}</div></div>`;
}
function summaryStats(){
 const kinds={connections:['firewall','router'],switches:['switch'],servers:['server'],printers:['printer'],wireless:['wireless'],devices:['device','router','firewall'],services:['service'],containers:['container']};
 const ds=selected().filter(d=>view==='ports'||kinds[view]?.includes(d.type)),ports=ds.flatMap(d=>d.ports||[]);
 const average=key=>{const values=ds.map(d=>d.metrics?.[key]).filter(numeric);return values.length?values.reduce((a,b)=>a+b,0)/values.length:null;};
 const count=st=>ds.filter(d=>d.state===st).length;
 let stats=[[ds.length,titles[view],'Monitored in this view',''],[count('up'),'Online','Reported operational','good'],[count('down'),'Offline','Confirmed by source',count('down')?'bad':''],[num(average('latency_ms'),' ms'),'Mean latency','Reported measurements','cyan'],[count('unknown'),'Unknown','Missing or stale data','warn'],[ports.filter(p=>p.state==='up').length,'Ports UP',`${ports.length} interfaces collected`,'cyan']];
 if(['services','containers'].includes(view)){stats[2][1]='Failed';stats[2][2]=view==='containers'?'Runtime / healthcheck failure':'Check did not pass';stats[4]=[count('attention'),'Attention','Needs investigation','warn'];stats[5]=[count('unknown'),'Unknown','Missing or stale data','warn'];if(view==='containers')stats[3]=[ds.filter(d=>d.health_state==='unhealthy').length,'Unhealthy','Reported healthcheck failures','bad'];}
 if(view==='switches')stats=[[ds.length,'Switches','Total monitored',''],[num(average('latency_ms'),' ms'),'Mean latency','Current samples','cyan'],[num(Math.max(0,...ds.map(d=>d.metrics?.latency_ms).filter(numeric))||null,' ms'),'Highest latency','Current samples','warn'],[num(average('cpu_percent'),'%'),'Mean CPU','Where reported',''],[count('down'),'Unavailable','Confirmed by source',count('down')?'bad':''],[count('unknown'),'Unknown','Missing or stale data','warn']];
 if(view==='ports'){
  const up=ports.filter(p=>p.state==='up').length,required=ports.filter(p=>p.required&&p.state==='down').length,unused=ports.filter(p=>!p.required&&p.state==='down').length;
  const pct=ports.length?up/ports.length*100:0;
  return `<div class="port-distribution"><div class="donut" style="--pct:${pct}%"><strong>${ports.length}</strong><small>interfaces</small></div><div><h3>Interface states</h3><span class="good">${up} UP</span><span class="bad">${required} required DOWN</span><span class="muted">${unused} DOWN without policy</span></div></div>${[[up+' / '+ports.length,'Active / total','Current interfaces',''],[required,'Required DOWN','Needs investigation','bad'],[unused,'Other DOWN','No critical policy','warn'],[ports.filter(p=>p.state==='unknown').length,'Unknown','Missing or stale data','']].map(statHTML).join('')}`;
 }
 if(view==='servers')return `<div class="environment-capacity"><h3>Environment · ${ds.length} hosts · mean reported utilization</h3>${capacityStrip({cpu_percent:average('cpu_percent'),memory_percent:average('memory_percent'),disk_percent:average('disk_percent')})}</div>`;
 if(view==='wireless')stats[5]=[ds.some(d=>numeric(d.metrics?.clients))?num(ds.reduce((sum,d)=>sum+(d.metrics?.clients||0),0)):'—','Clients','Where reported','cyan'];
 if(view==='printers')stats[5]=[ds.filter(d=>numeric(d.metrics?.toner_percent)&&d.metrics.toner_percent<20).length,'Low toner','Reported level below 20%','warn'];
 return stats.map(statHTML).join('');
}
function statHTML([v,label,hint,cls]){return `<div class="stat"><strong class="${cls}">${v}</strong><span>${label}</span><small>${hint}</small></div>`;}

function fitEquipment(){
 const stage=$('#stage'),layout=stage.querySelector('.adaptive-equipment');if(!layout)return;
 const rows=equipmentRows(),grid=layout.firstElementChild,summary=document.createElement('button');
 summary.className='equipment-overflow';summary.dataset.action='inventory';layout.append(summary);
 const byId=new Map([...grid.querySelectorAll('.device-card')].map(c=>[c.querySelector('[data-action="device"]').dataset.id,c])),cards=rows.map(d=>byId.get(d.id)).filter(Boolean),desktop=innerWidth>=1000;
 const updateSummary=()=>{const visible=new Set(cards.map(c=>c.querySelector('[data-action="device"]').dataset.id)),hidden=rows.filter(d=>!visible.has(d.id)),counts=Object.entries(severity).map(([st])=>{const n=hidden.filter(d=>equipmentState(d)===st).length;return n?`${n} ${st.toUpperCase()}`:'';}).filter(Boolean);
  for(const group of grid.querySelectorAll('.equipment-category'))group.querySelector('.category-head span').textContent=`${group.querySelectorAll('.device-card').length} devices`;
  summary.hidden=!hidden.length;summary.textContent=`${hidden.length} more devices · ${counts.join(' · ')} · Open inventory`;
  summary.dataset.state=hidden.some(d=>equipmentState(d)==='down')?'down':hidden.some(d=>['attention','unknown'].includes(equipmentState(d)))?'attention':'up';
  $('#coverage').textContent=`${cards.length}/${rows.length} devices · incidents first${hidden.length?' · remaining devices summarized above':''}`;
 };
 updateSummary();
 if(!desktop)return;
 // Measure the actual content; long names, category headers and zoom affect fit.
 const fits=()=>{const bounds=layout.getBoundingClientRect();return bounds.bottom<=stage.getBoundingClientRect().bottom+1&&grid.scrollWidth<=grid.clientWidth+1&&layout.scrollHeight<=layout.clientHeight+1&&[...cards,...(summary.hidden?[]:[summary])].every(c=>{const r=c.getBoundingClientRect();return r.bottom<=bounds.bottom+1&&r.right<=bounds.right+1;});};
 const arrange=()=>{
  for(const density of ['normal','compact','dense']){
   layout.dataset.density=density;
   const min=view==='servers'?{normal:650,compact:380,dense:300}[density]:{normal:340,compact:280,dense:240}[density];
   const count=view==='devices'?grid.children.length:cards.length,max=Math.max(1,Math.min(count,Math.floor((layout.clientWidth+12)/(min+12))));
   for(let columns=max;columns>=1;columns--){layout.style.setProperty('--equipment-columns',columns);if(fits())return true;}
  }
  return false;
 };
 while(!arrange()&&cards.length){cards.pop().remove();for(const group of grid.querySelectorAll('.equipment-category'))if(!group.querySelector('.device-card'))group.remove();updateSummary();}
 updateSummary();
}

function render(){
 if(!data||!config)return;
 const focus=document.activeElement?.closest('[data-action]'),key=focus?{action:focus.dataset.action,id:focus.dataset.id,port:focus.dataset.port}:null;
 document.body.dataset.page=view;
 $('#stats').innerHTML=summaryStats();
 $('#coverage').textContent=`${sites().length} sites · only reported links are drawn · ${config.mode==='demo'?'all data is simulated':'live sources'}`;
 $('#stage').innerHTML=view==='connections'?connections():view==='switches'?switchGraph():view==='ports'?portTable():devicesGrid();
 layoutGeography();layoutSwitchEdges();
 fitEquipment();
 $('#sources').textContent=data.sources.map(s=>`${s.id}: ${s.state} · ${age(s.last_success)} · interval ${s.interval_seconds}s`).join('  |  ');
 const critical=data.alerts.filter(a=>a.severity==='critical').length;$('.ticker').dataset.critical=String(critical>0);$('#alert-summary').textContent=critical?`${critical} critical`:`${data.alerts.length} alerts`;
 $('#notification-count').textContent=data.alerts.length;$('#notification-count').hidden=!data.alerts.length;$('#notification-bell').dataset.critical=String(critical>0);$('#notification-bell').setAttribute('aria-label',`Open current notifications: ${data.alerts.length} alerts, ${critical} critical`);
 const ticker=(data.alerts.length?data.alerts:[{severity:'ok',text:config.mode==='demo'?'Demo data · Configure your sources to monitor your own environment':'No active alerts reported'}]).map(a=>`<span data-severity="${esc(a.severity)}">${esc(a.text)}</span>`).join('');
 if(ticker!==lastTicker){$('#ticker-track').innerHTML=ticker+ticker;lastTicker=ticker;}
 $('#ticker-headline').textContent=data.alerts.find(a=>a.severity==='critical')?.text||'Current network events';
 for(const a of $('#nav').children){const types={servers:['server'],switches:['switch'],printers:['printer'],wireless:['wireless'],devices:['device','router','firewall'],services:['service'],containers:['container'],connections:['firewall','router']};const total=a.dataset.view==='ports'?data.devices.flatMap(d=>d.ports||[]).filter(p=>p.required&&p.state==='down').length:data.devices.filter(d=>types[a.dataset.view]?.includes(d.type)&&d.state==='down').length;let badge=a.querySelector('.nav-count');if(!badge){badge=document.createElement('span');badge.className='nav-count';a.append(badge);}badge.textContent=total;badge.hidden=!total;}
 if(dialogState)renderDialog();
 if(key){const next=[...document.querySelectorAll('[data-action]')].find(e=>e.dataset.action===key.action&&e.dataset.id===key.id&&e.dataset.port===key.port);next?.focus({preventScroll:true});}
}
function portDetail(d,p){
 if(!p)return '<p class="note">Select an interface to see its state and discovered neighbor.</p>';
 return `<div class="port-information"><div><h3>${esc(p.name)} ${state(p.state)}</h3><div class="detail-fields"><div><span>Administrative state</span>${esc(p.admin_state||'Not reported')}</div><div><span>Speed</span>${num(p.speed_mbps,' Mbps')}</div><div><span>Observed</span>${esc(age(p.observed_at))} ago</div><div><span>RX / TX</span>${rate(p.rx_bps)} / ${rate(p.tx_bps)}</div><div><span>Description</span>${esc(p.description||'Not reported')}</div><div><span>Policy</span>${p.required?'Required interface':'No critical DOWN policy'}</div></div></div><div><h3>Discovered equipment</h3>${p.neighbors?.length?p.neighbors.map(n=>`<article class="neighbor"><strong>${esc(n.name)}</strong><p>${esc(n.ip||'Address not reported')} <span class="badge">${esc(n.evidence||'discovery')}</span></p></article>`).join(''):'<p class="note">No neighbor reported for this interface. A description is not proof of the connected equipment.</p>'}</div></div>`;
}
function siteDetails(id){
 const ds=data.devices.filter(d=>d.site===id),ids=new Set(ds.map(d=>d.id)),links=data.links.filter(l=>ids.has(l.a)||ids.has(l.b)),local=links.filter(l=>ids.has(l.a)&&ids.has(l.b)),remote=links.filter(l=>!local.includes(l)),firewalls=ds.filter(d=>d.type==='firewall');
 const name=id=>data.devices.find(d=>d.id===id)?.name||id;
 const linkRows=items=>items.map(l=>`<article class="site-link"><h3>${esc(name(l.a))} ↔ ${esc(name(l.b))} ${state(l.state)}</h3><p>Latency ${num(l.latency_ms,' ms')} · Loss ${num(l.loss_percent,'%')} · Traffic ${rate(l.traffic_bps)}</p><small>${esc(l.evidence||'Source reported')} · ${age(l.observed_at)} ago</small></article>`).join('');
 return `<div class="details-summary">${state(siteState(id))}<span>${ds.length} devices · ${ds.filter(d=>d.state==='up').length} UP · ${ds.filter(d=>d.state==='down').length} DOWN</span><span>${local.length} local connections</span></div><div class="site-device-strip">${ds.map(d=>`<article data-state="${esc(d.state)}">${webLink(d)}<button data-action="device" data-id="${esc(d.id)}">${brandIcon(d)}<span><strong>${esc(d.name)}</strong><small>${esc(d.ip||'Address not reported')} · ${esc(d.type)}</small></span>${state(d.state)}</button></article>`).join('')||'<p class="empty">No devices mapped to this site.</p>'}</div><div class="site-details-columns"><section><h2>Firewalls and interfaces</h2>${firewalls.map(d=>`<article class="site-firewall"><h3>${esc(d.name)} ${state(d.state)}</h3><p>${esc(d.model||d.vendor||'')} · ${esc(d.ip||'')} · observed ${age(d.observed_at)} ago</p><div class="firewall-ports">${(d.ports||[]).map(p=>`<button class="port" data-state="${esc(p.state)}" data-action="device" data-id="${esc(d.id)}" data-port="${esc(p.id)}">${esc(p.name)}<br>${esc(p.state.toUpperCase())}</button>`).join('')}</div><p class="note">Unused DOWN interfaces do not imply a critical incident.</p><h3>Reported services</h3><div class="service-readings">${(d.services||[]).map(x=>`<div>${esc(x.name)} ${state(x.state)}</div>`).join('')||'<p class="note">No service health reported by this source.</p>'}</div></article>`).join('')||'<p class="note">No firewall mapped to this site.</p>'}</section><section><h2>VPN / inter-site connections</h2>${linkRows(remote)||'<p class="note">No inter-site connections reported.</p>'}<h2>Local connections</h2>${linkRows(local)||'<p class="note">Local links have not been discovered. Site membership does not imply a connection.</p>'}</section></div>`;
}
function renderDialog(){
 const s=dialogState;if(!s)return;
 if(s.type==='alerts'){$('#dialog-title').textContent='Current alerts';$('#dialog-eyebrow').textContent='Source state and operational events';$('#dialog-body').innerHTML=`<div class="alert-list">${data.alerts.map(a=>`<article data-severity="${esc(a.severity)}">${esc(a.text)}</article>`).join('')||'<p class="empty">No active alerts.</p>'}</div>`;return;}
 if(s.type==='inventory'){$('#dialog-title').textContent=titles[view]+' · Full inventory';$('#dialog-eyebrow').textContent='All devices in this scope · incidents first';$('#dialog-body').innerHTML=`<div class="grid">${equipmentRows().map(d=>['service','container'].includes(d.type)?monitorCard(d):d.type==='server'?serverCard(d):card(d)).join('')}</div>`;return;}
 if(s.type==='site'){$('#dialog-title').textContent=siteName(s.id);$('#dialog-eyebrow').textContent='Site inventory · live updates';$('#dialog-body').innerHTML=siteDetails(s.id);return;}
 const d=data.devices.find(d=>d.id===s.id);if(!d){$('#dialog-body').innerHTML='<p class="empty">This device is no longer in the current inventory.</p>';return;}
 $('#dialog-title').textContent=d.name;$('#dialog-eyebrow').textContent=[siteName(d.site),d.model,d.ip].filter(Boolean).join(' · ');
 const ports=d.ports||[];if(!s.port&&ports.length)s.port=ports[0].id;
 const metrics=Object.entries(d.metrics||{}).filter(([,v])=>numeric(v));
 $('#dialog-body').innerHTML=`<div class="details-summary">${state(d.state)}<span>Source ${esc(d.source)}</span>${d.management_state?`<span>Management API: ${esc(d.management_state)}</span>`:''}<span>Observed ${esc(age(d.observed_at))} ago</span>${d.stale?'<span class="warn">Telemetry stale; state is unknown</span>':''}</div>${d.type==='server'?serverCard(d):''}${metrics.length?`<div class="detail-fields">${metrics.map(([k,v])=>`<div><span>${esc(k.replaceAll('_',' '))}</span>${num(v)}</div>`).join('')}</div>`:''}${d.type==='container'?`<div class="detail-fields"><div><span>Runtime</span>${esc(d.runtime_state||'unknown')}</div><div><span>Healthcheck</span>${esc(d.health_state||'unknown')}</div></div>`:''}${ports.length?`<section class="port-panel"><div class="port-panel-header"><strong>${esc(d.model||'Interfaces')}</strong><span>${ports.filter(p=>p.state==='up').length} UP / ${ports.length} interfaces</span></div><div class="ports">${ports.map(p=>`<button class="port" data-action="port" data-id="${esc(d.id)}" data-port="${esc(p.id)}" data-state="${esc(p.state)}" aria-pressed="${s.port===p.id}" aria-label="${esc(p.name)} ${esc(p.state)}">${esc(p.name)}</button>`).join('')}</div><p class="note">Logical interface diagram · positions are not a manufacturer faceplate.</p></section><section class="port-detail">${portDetail(d,ports.find(p=>p.id===s.port))}</section>`:['service','container'].includes(d.type)?'':'<p class="empty">This source has not reported interface data for this device.</p>'}${d.services?.length?`<h3>Reported services</h3><div class="alert-list">${d.services.map(x=>`<article>${esc(x.name)} · ${esc(x.state)}</article>`).join('')}</div>`:''}`;
}
function openDialog(type,id,port){dialogState={type,id,port};renderDialog();if(!$('#details').open)$('#details').showModal();}
function viewDuration(){return Math.round(rotationBase*(view==='connections'?Math.max(1,config.display.connections_seconds/config.display.rotate_seconds):1));}
function updateRotation(){if(!config)return;$('#rotate span').textContent=rotate?`Auto ON (${viewDuration()}s)`:'Auto paused';$('#rotate').setAttribute('aria-pressed',String(rotate));}
function resetRotation(){rotateDeadline=Date.now()+viewDuration()*1000;updateRotation();}
function visibleViews(){return config.display.views.filter(v=>!hiddenViews.has(v));}
function renderNavigation(){
 $('#nav').innerHTML=visibleViews().map(v=>`<a href="#${v}" data-view="${v}"><span aria-hidden="true">${icons[v]}</span>${titles[v]}</a>`).join('');
 $('#visible-views').innerHTML=config.display.views.map(v=>`<label><input type="checkbox" value="${v}" ${hiddenViews.has(v)?'':'checked'}>${titles[v]}</label>`).join('');
}
function navigate(next){const available=visibleViews();view=available.includes(next)?next:available[0];$('#title').textContent=titles[view];$('#subtitle').textContent=descriptions[view];document.title=`${titles[view]} · ${config.title}`;for(const a of $('#nav').children)a.setAttribute('aria-current',a.dataset.view===view?'page':'false');resetRotation();render();}
function applyMotion(){document.body.classList.toggle('no-motion',!motion);$('#motion').textContent=motion?'Motion on':'Motion off';$('#motion').setAttribute('aria-pressed',String(motion));}
function applyDisplay(){
 const profile=$('#tv-profile').value,scale=innerWidth>=3000&&profile!=='1080p'?2:1;
 document.body.dataset.tvProfile=profile;document.body.style.zoom=String(scale);
 document.body.style.height=innerWidth>=1000?`${innerHeight/scale}px`:'';
}
function updateFreshness(){
 if(!config)return;
 const fresh=lastSuccess&&Date.now()-lastSuccess<=config.display.refresh_seconds*2500&&$('#error').hidden;
 const healthy=fresh&&data?.sources.every(s=>s.state==='ok');
 $('#freshness').classList.toggle('bad',!healthy);
 $('#freshness span').textContent=lastSuccess?`${config.mode==='demo'?'Demo data':'Telemetry'} · ${age(new Date(lastSuccess).toISOString())}`:'Connecting…';
 $('#freshness').setAttribute('aria-label',`${$('#freshness span').textContent}. Refresh displayed data`);
 $('#updated').textContent=lastSuccess?'Updated '+new Intl.DateTimeFormat('en-GB',{timeZone:config.timezone,hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(lastSuccess):'Updated —';
}
function playAlert(){
 if(!soundEnabled||audioContext?.state!=='running')return;
 const oscillator=audioContext.createOscillator(),gain=audioContext.createGain(),time=audioContext.currentTime;
 oscillator.frequency.value=660;gain.gain.setValueAtTime(0,time);gain.gain.linearRampToValueAtTime(.06,time+.02);gain.gain.exponentialRampToValueAtTime(.001,time+.25);
 oscillator.connect(gain);gain.connect(audioContext.destination);oscillator.start(time);oscillator.stop(time+.26);oscillator.onended=()=>{oscillator.disconnect();gain.disconnect();};
}
async function openTools(){
 $('#tools-dialog').showModal();
 try{const response=await fetch('/api/v1/diagnostics');if(!response.ok)throw Error();const result=await response.json();
  $('#diagnostic-status').textContent=result.mode==='demo'?'DEMO · results are simulated; no network requests are made.':result.enabled?'Diagnostics enabled for configured networks.':'Disabled. Enable diagnostics and allowed_cidrs in the server configuration.';
  $('#diagnostic-tool').innerHTML=result.tools.map(t=>`<option value="${esc(t.id)}" ${!t.available?'disabled':''}>${esc(t.label)}${t.available?'':` · missing ${esc(t.binary)}`}</option>`).join('');
  $('#diagnostic-run').disabled=diagnosticBusy||!result.enabled||!result.tools.some(t=>t.available);
 }catch{$('#diagnostic-status').textContent='Could not load diagnostic capabilities. Close and reopen to retry.';$('#diagnostic-run').disabled=true;}
}
async function refresh(){
 if(refreshPending||!config)return;clearTimeout(refreshTimer);refreshPending=true;$('#freshness').disabled=true;
 try{const response=await fetch('/api/v1/snapshot',{cache:'no-store'});if(!response.ok)throw Error('snapshot_unavailable');const next=await response.json();if(next.schema_version!==1||!Array.isArray(next.devices)||!Array.isArray(next.links))throw Error('invalid_snapshot');data=next;const critical=new Set(data.alerts.filter(a=>a.severity==='critical').map(a=>a.id||a.text));if(knownCritical&&[...critical].some(id=>!knownCritical.has(id))){try{playAlert();}catch{soundEnabled=false;$('#sound').textContent='Sound unavailable';$('#sound').setAttribute('aria-pressed','false');}}knownCritical=critical;for(const d of data.devices){const samples=history.get(d.id)||[],time=Date.parse(d.observed_at);if(Number.isFinite(time)&&samples.at(-1)?.time!==time)samples.push({time,...d.metrics});history.set(d.id,samples.slice(-120));}for(const id of history.keys())if(!data.devices.some(d=>d.id===id))history.delete(id);lastSuccess=Date.now();$('#error').hidden=true;render();updateFreshness();}
 catch{const error=$('#error');error.hidden=false;error.textContent='Telemetry could not be refreshed. Displayed states are unknown until the connection recovers.';if(data){data={...data,devices:data.devices.map(d=>({...d,state:'unknown',stale:true,metrics:{},hardware:{},storage:[],management_state:'unknown',runtime_state:'unknown',health_state:'unknown',services:(d.services||[]).map(x=>({...x,state:'unknown'})),ports:(d.ports||[]).map(p=>({...p,state:'unknown',rx_bps:null,tx_bps:null}))})),links:data.links.map(l=>({...l,state:'unknown',traffic_bps:null})),alerts:[{severity:'warning',text:'Connection to NOCtv telemetry interrupted'}]};render();}}
 finally{refreshPending=false;$('#freshness').disabled=false;refreshTimer=setTimeout(refresh,(document.hidden?30:config.display.refresh_seconds)*1000);}
}
async function boot(){
 try{const response=await fetch('/api/v1/config');if(!response.ok)throw Error('config');config=await response.json();rotationBase=Number(localStorage.getItem('noctv-rotate-seconds'))||config.display.rotate_seconds;rotationBase=Math.max(5,Math.min(600,Math.round(rotationBase)));$('#rotate-seconds').value=rotationBase;rotate=localStorage.getItem('noctv-rotate')==='on';$('#tv-profile').value=['1080p','4k'].includes(localStorage.getItem('noctv-tv-profile'))?localStorage.getItem('noctv-tv-profile'):'auto';applyDisplay();$('#mode').textContent=config.mode==='demo'?'DEMO · SIMULATED':'LIVE';$('#mode').classList.toggle('demo',config.mode==='demo');try{const saved=JSON.parse(localStorage.getItem('noctv-hidden-views')||'[]');hiddenViews=new Set(Array.isArray(saved)?saved.filter(v=>config.display.views.includes(v)):[]);}catch{hiddenViews.clear();}if(!visibleViews().length)hiddenViews.clear();renderNavigation();$('#site-filter').innerHTML='<option value="">All sites</option>'+config.sites.map(s=>`<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('')+'<option value="unassigned">Unassigned</option>';navigate(location.hash.slice(1));applyMotion();await refresh();}
 catch{$('#error').hidden=false;$('#error').textContent='Configuration unavailable. Retrying…';setTimeout(boot,5000);}
}
document.addEventListener('click',event=>{const button=event.target.closest('[data-action]');if(!button||!data)return;const {action,id,port}=button.dataset;if(action==='port'){dialogState.port=port;renderDialog();[...$('#dialog-body').querySelectorAll('[data-action="port"]')].find(b=>b.dataset.port===port)?.focus({preventScroll:true});}else if(['site','device','alerts','inventory'].includes(action))openDialog(action,id,port);});
$('#details').addEventListener('close',()=>{dialogState=null;if(config)resetRotation();});$('#close-dialog').addEventListener('click',()=>$('#details').close());
$('#site-filter').addEventListener('change',event=>{siteFilter=event.target.value;render();});
$('#motion').addEventListener('click',()=>{motion=!motion;localStorage.setItem('noctv-motion',motion?'on':'off');applyMotion();});
$('#rotate').addEventListener('click',()=>{if(!config)return;rotate=!rotate;localStorage.setItem('noctv-rotate',rotate?'on':'off');resetRotation();});
$('#rotate-seconds').addEventListener('change',()=>{if(!config)return;const input=$('#rotate-seconds');if(!input.checkValidity()||!Number.isFinite(input.valueAsNumber)){input.value=rotationBase;return;}rotationBase=input.valueAsNumber;localStorage.setItem('noctv-rotate-seconds',rotationBase);resetRotation();});
$('#tv-profile').addEventListener('change',()=>{localStorage.setItem('noctv-tv-profile',$('#tv-profile').value);applyDisplay();if(data)render();});
$('#freshness').addEventListener('click',refresh);
$('#sound').addEventListener('click',async()=>{try{if(!soundEnabled){audioContext??=new AudioContext();await audioContext.resume();if(audioContext.state!=='running')throw Error();}soundEnabled=!soundEnabled;$('#sound').textContent=soundEnabled?'Sound ON':'Sound OFF';$('#sound').setAttribute('aria-pressed',String(soundEnabled));}catch{$('#sound').textContent='Sound blocked';$('#sound').title='Browser audio is unavailable. Check this site’s audio permission.';}});
$('#visible-views').addEventListener('change',event=>{
 const input=event.target;if(input.type!=='checkbox')return;
 if(!input.checked&&visibleViews().length===1){input.checked=true;$('#views-status').textContent='Keep at least one screen visible.';return;}
 if(input.checked)hiddenViews.delete(input.value);else hiddenViews.add(input.value);
 localStorage.setItem('noctv-hidden-views',JSON.stringify([...hiddenViews]));const current=view;renderNavigation();navigate(current);
 if(current!==view)window.history.replaceState(null,'','#'+view);
 $('#views-status').textContent='Saved for this browser. Collection and alerts remain active.';
 $('#visible-views').querySelector(`input[value="${input.value}"]`)?.focus();
});
$('#views-reset').addEventListener('click',()=>{hiddenViews.clear();localStorage.removeItem('noctv-hidden-views');renderNavigation();navigate(view);$('#views-status').textContent='Installation defaults restored.';});
$('#tools-open').addEventListener('click',openTools);$('#tools-close').addEventListener('click',()=>$('#tools-dialog').close());$('#tools-dialog').addEventListener('close',()=>{if(config)resetRotation();});
$('#diagnostic-form').addEventListener('submit',async event=>{event.preventDefault();const run=$('#diagnostic-run');if(run.disabled||diagnosticBusy)return;diagnosticBusy=true;run.disabled=true;$('#diagnostic-output').textContent='Running diagnostic…';
 try{const response=await fetch('/api/v1/diagnostics/run',{method:'POST',headers:{'Content-Type':'application/json','X-NOCtv-Request':'diagnostic'},body:JSON.stringify({tool:$('#diagnostic-tool').value,target:$('#diagnostic-target').value.trim()}),signal:AbortSignal.timeout(40000)});const result=await response.json();$('#diagnostic-output').textContent=result.error||`${result.simulated?'SIMULATED · ':''}Exit ${result.exit_code}\n${result.output}`;}
 catch{$('#diagnostic-output').textContent='The diagnostic request failed or timed out. The server limits each run to 35 seconds.';}finally{diagnosticBusy=false;run.disabled=false;}
});
$('#ticker-pause').addEventListener('click',()=>{const paused=$('.ticker').classList.toggle('paused');$('#ticker-pause').setAttribute('aria-pressed',String(paused));$('#ticker-pause').setAttribute('aria-label',paused?'Resume alert scrolling':'Pause alert scrolling');});
$('#fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{$('#error').hidden=false;$('#error').textContent='Fullscreen was not allowed by this browser.';}});
window.addEventListener('resize',()=>{applyDisplay();if(data)render();});
document.fonts.addEventListener('loadingdone',()=>{if(data)render();});
window.addEventListener('hashchange',()=>{if(config)navigate(location.hash.slice(1));});
document.addEventListener('visibilitychange',()=>document.body.classList.toggle('page-hidden',document.hidden));
setInterval(()=>{if(!config)return;updateFreshness();if(rotate&&!document.hidden&&!$('#details').open&&!$('#tools-dialog').open&&Date.now()>=rotateDeadline){const available=visibleViews(),i=available.indexOf(view);location.hash=available[(i+1)%available.length];resetRotation();}},1000);
boot();
