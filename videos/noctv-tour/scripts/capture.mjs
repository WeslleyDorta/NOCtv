// Records only the repository's isolated demo. API overrides are synthetic fixtures.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {spawn,execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.NOCTV_PLAYWRIGHT_MODULE||'playwright');
const project=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.resolve(project,'../..');
const base='http://127.0.0.1:8877',shots=[],clicks=[],errors=[],external=[];
fs.mkdirSync(path.join(project,'assets/raw'),{recursive:true});
const server=spawn(process.env.PYTHON||'python3',['-m','noctv','serve','--config','config/map-country.example.json','--port','8877'],{cwd:repo,stdio:'ignore'});
let browser,context,page,start,end;
const wait=ms=>new Promise(r=>setTimeout(r,ms));
try{
 for(let i=0;i<80;i++){try{if((await fetch(base+'/healthz')).ok)break;}catch{}await wait(100);}
 const config=await(await fetch(base+'/api/v1/config')).json();assert.equal(config.mode,'demo');config.display.refresh_seconds=1;
 let data=await(await fetch(base+'/api/v1/snapshot')).json();assert.equal(data.mode,'demo');assert.equal(data.devices.length,38);
 const counts={},oldNames=new Map(data.devices.map(d=>[d.id,d.name]));
 for(const d of data.devices){const prefix={hq:'HQ',north:'NORTH',east:'EAST',cloud:'DC'}[d.site];const key=d.site+d.type;counts[key]=(counts[key]||0)+1;
  d.name=`${prefix}-${{firewall:'FW',switch:d.root?'CORE':'ACCESS',server:'HOST',printer:'PRINT',wireless:'AP',device:'CAM',service:'CHECK',container:'APP'}[d.type]}-${String(counts[key]).padStart(2,'0')}`;
  if(d.type==='service')d.name=['Public website','Customer portal','Database TCP','DNS resolver','Gateway ping'][Number(d.id.split(':').at(-1))];
  if(d.type==='container')d.name=['web-frontend','background-worker','cache'][Number(d.id.split(':').at(-1))];
  for(const p of d.ports||[])if(p.neighbors?.length)p.neighbors.forEach(n=>{n.name=data.devices.find(x=>x.id===n.id)?.name||n.name;});
 }
 for(const d of data.devices)for(const p of d.ports||[])for(const n of p.neighbors||[])n.name=data.devices.find(x=>x.id===n.id)?.name||n.name;
 const sw=data.devices.find(d=>d.type==='switch'&&d.root&&d.site==='hq'),port=sw.ports.find(p=>p.id==='2');
 const service=data.devices.find(d=>d.id==='demo:service:2');
 service.state='up';service.services=[{name:'Check passed',state:'up'}];
 const baselineAlerts=data.alerts.filter(a=>a.device_id!==service.id).map(a=>{let text=a.text;for(const d of data.devices)text=text.replaceAll(oldNames.get(d.id),d.name);return {...a,text};});
 const uplink=data.links.find(l=>l.a===sw.id&&l.a_port===port.id);assert(uplink);
 data.alerts=[...baselineAlerts];
 browser=await chromium.launch({headless:true,...(process.env.NOCTV_CHROMIUM?{executablePath:process.env.NOCTV_CHROMIUM}:{})});
 context=await browser.newContext({viewport:{width:1920,height:1080},recordVideo:{dir:path.join(project,'assets/raw'),size:{width:1920,height:1080}}});
 await context.route('**/*',async r=>{
  const url=r.request().url();if(!url.startsWith(base+'/')){external.push(url);return r.abort();}
  if(url.endsWith('/api/v1/config'))return r.fulfill({json:config});
  if(url.endsWith('/api/v1/snapshot')){const stamp=new Date().toISOString();data.generated_at=stamp;data.sources.forEach(s=>s.last_success=stamp);for(const d of data.devices){d.observed_at=stamp;for(const p of d.ports||[])p.observed_at=stamp;}data.links.forEach(l=>l.observed_at=stamp);return r.fulfill({json:data});}
  return r.continue();
 });
 page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.waitForSelector('.country-layer path');await wait(1800);
 await page.evaluate(()=>{const s=document.createElement('style');s.textContent='*{cursor:none!important}#tour-pointer{position:fixed;left:0;top:0;width:42px;height:52px;z-index:2147483647;pointer-events:none;filter:drop-shadow(0 2px 2px #000)}';document.head.append(s);const c=document.createElement('div');c.id='tour-pointer';c.innerHTML='<svg viewBox="0 0 30 38"><path d="M3 2L3 29L10 23L17 35L22 32L15 20L25 19Z" fill="white" stroke="#061014" stroke-width="2"/></svg>';document.body.append(c);document.addEventListener('mousemove',e=>{c.style.left=e.clientX+'px';c.style.top=e.clientY+'px';});});
 const click=async selector=>{const el=page.locator(selector).first();await el.waitFor({state:'visible'});const b=await el.boundingBox();await page.mouse.move(b.x+b.width/2,b.y+b.height/2,{steps:24});await wait(180);clicks.push((Date.now()-start)/1000);await el.click();};
 const close=async()=>{await page.keyboard.press('Escape');await wait(200);};
 const scene=async(id,duration,action)=>{const t=Date.now();shots.push({id,start:(t-start)/1000,duration});console.log('Recording '+id);await action();const remaining=duration*1000-(Date.now()-t);assert(remaining>0,id+' action exceeded slot');await wait(remaining);await page.screenshot({path:path.join(project,'assets',id+'.png')});};
 start=Date.now();await page.mouse.move(1650,1000);
 await scene('connections',8,async()=>{await wait(1700);await page.mouse.move(1050,620,{steps:40});});
 await scene('site',6,async()=>{await click('.geographic [data-action="site"][data-id="hq"]');await page.waitForSelector('#details[open] .site-firewall');});
 await close();await click('[data-view="switches"]');await page.waitForSelector('.switch-node');
 await scene('switches',6,async()=>{await page.mouse.move(700,650,{steps:35});});
 await scene('port',10,async()=>{await click(`.switch-node [data-action="device"][data-id="${sw.id}"]`);await click('.port[data-port="2"]');await wait(1800);port.state='down';port.rx_bps=0;port.tx_bps=0;uplink.state='down';data.alerts=[...baselineAlerts,{id:'tour:port',severity:'critical',text:`${sw.name} · Gi2 required uplink DOWN (simulated)`}];await page.waitForFunction(()=>document.querySelector('.port[data-port="2"]').dataset.state==='down');await wait(2100);port.state='up';port.rx_bps=1200000;port.tx_bps=400000;uplink.state='up';data.alerts=[...baselineAlerts];await page.waitForFunction(()=>document.querySelector('.port[data-port="2"]').dataset.state==='up');assert.match(await page.locator('.port-detail').innerText(),/DEMO/);});
 await close();
 for(const [id,view] of [['ports','ports'],['servers','servers'],['printers','printers'],['wireless','wireless'],['devices','devices']]){
  await scene(id,4,async()=>{await click(`[data-view="${view}"]`);await page.waitForFunction(v=>document.querySelector('[aria-current=page]').dataset.view===v,view);await page.mouse.move(1730,870,{steps:20});});
 }
 await scene('services',6,async()=>{service.state='down';service.services=[{name:'Connection refused',state:'down'}];data.alerts=[...baselineAlerts,{id:'tour:service',severity:'critical',text:'Database TCP unavailable (simulated)'}];await click('[data-view="services"]');await wait(2000);service.state='up';service.services=[{name:'Check passed',state:'up'}];uplink.state='up';data.alerts=[...baselineAlerts];await page.waitForFunction(()=>[...document.querySelectorAll('.monitor-card')].some(c=>c.textContent.includes('Database TCP')&&c.dataset.state==='up'));});
 await scene('containers',5,async()=>{await click('[data-view="containers"]');await wait(500);await click('#stage .card-open');await page.waitForSelector('#details[open]');});
 await close();await click('[data-view="connections"]');
 await scene('tools',6,async()=>{await click('#tools-open');await page.waitForSelector('#tools-dialog[open]');await wait(700);await click('#visible-views input[value="printers"]');await wait(700);await click('#visible-views input[value="printers"]');});
 end=Date.now();assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 const video=page.video();await context.close();context=null;const source=await video.path();
 const duration=Number(execFileSync('ffprobe',['-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',source],{encoding:'utf8'}));
 const offset=duration-(end-start)/1000;
 fs.writeFileSync(path.join(project,'assets/recording.json'),JSON.stringify({source:path.relative(project,source),offset,shots,clicks,checks:{deviceCount:38,portDownAndRecovery:true,serviceRecovery:true,noExternalRequests:true,noPageErrors:true}},null,2));
 for(const s of shots)execFileSync('ffmpeg',['-y','-v','error','-ss',String(offset+s.start),'-i',source,'-t',String(s.duration),'-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',path.join(project,'assets',s.id+'.mp4')]);
 console.log('PASS: 12 recorded scenes, port DOWN/UP, service recovery, no external requests or browser errors');
}finally{await context?.close();await browser?.close();server.kill();}
