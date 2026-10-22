import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawn,execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.NOCTV_PLAYWRIGHT_MODULE||'playwright');
const url='http://127.0.0.1:8766',errors=[];
const server=spawn(process.env.PYTHON||'python3',['-m','noctv','serve','--port','8766'],{stdio:'ignore'});
let browser;
try{
 for(let i=0;i<100;i++){try{if((await fetch(url+'/healthz')).ok)break;}catch{}if(i===99)throw Error('Preview server did not start');await new Promise(r=>setTimeout(r,100));}
 browser=await chromium.launch({headless:true,...(process.env.NOCTV_CHROMIUM?{executablePath:process.env.NOCTV_CHROMIUM}:{})});
 const page=await browser.newPage({viewport:{width:1920,height:1080}});page.on('pageerror',e=>errors.push(e.message));
 const external=[];page.on('request',r=>{if(!r.url().startsWith(url))external.push(r.url());});
 await page.goto(url);await page.waitForSelector('.site-card');await page.waitForTimeout(5500);
 assert.match(await page.locator('#mode').innerText(),/SIMULATED/);
 fs.mkdirSync('artifacts',{recursive:true});
 for(const name of ['connections','switches','ports','servers','printers','wireless','devices','services','containers']){
  await page.locator(`[data-view="${name}"]`).click();await page.waitForFunction(name=>document.querySelector('[aria-current=page]')?.dataset.view===name,name);
  assert.equal(await page.locator('[aria-current="page"]').count(),1);
  if(name==='connections')await page.waitForFunction(()=>{const e=document.querySelector('.connections');return e&&getComputedStyle(e).gridTemplateColumns.split(' ').length===3;});
  if(name==='switches')assert(await page.locator('.switch-map g[data-a]').evaluateAll(groups=>groups.every(g=>{const graph=g.closest('.graph').getBoundingClientRect(),end=g.querySelector('.edge').getPointAtLength(g.querySelector('.edge').getTotalLength());const target=[...g.closest('.graph').querySelectorAll('.switch-node')].find(n=>n.dataset.device===g.dataset.b).getBoundingClientRect();return Math.abs(graph.left+end.x/100*graph.width-target.left)<2;})));
  if(name==='ports')assert.equal(await page.locator('.port-table-panel').count(),2);
  if(name==='servers')assert.equal(await page.locator('.server-card .server-capacity').count(),2);
  if(name==='devices')assert(await page.locator('.equipment-category').count()>=2);
  if(name==='printers')assert(await page.locator('.supplies').count()>0);
  if(['services','containers'].includes(name)){assert(await page.locator('.monitor-card').count()>0);assert(await page.locator('.monitor-facts').count()>0);}
  if(name==='wireless')assert(await page.locator('.resources').count()>0);
  assert(await page.locator('#stage').evaluate(stage=>[...stage.querySelectorAll('.device-card,.port-table-panel,.switch-node')].every(e=>e.getBoundingClientRect().bottom<=stage.getBoundingClientRect().bottom+1)),name+' content outside TV stage');
  await page.screenshot({path:`artifacts/${name}.png`});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),name+' horizontal overflow');
  assert(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight),name+' vertical page overflow');
 }
 await page.locator('[data-view="connections"]').click();await page.locator('.graph-node[data-id="hq"]').click();assert(await page.locator('#details').evaluate(d=>d.open));assert.equal(await page.locator('#dialog-title').innerText(),'Headquarters');assert(await page.locator('.site-firewall').count()>0);assert(await page.locator('.site-link').count()>0);await page.screenshot({path:'artifacts/site-detail.png'});await page.keyboard.press('Escape');
 await page.locator('[data-view="switches"]').click();await page.locator('.switch-node [data-action="device"]').first().click();await page.locator('.port[data-port="2"]').click();assert.match(await page.locator('.port-detail').innerText(),/DEMO/);await page.screenshot({path:'artifacts/port-detail.png'});
 const name=await page.locator('#dialog-title').innerText();await page.waitForTimeout(5500);assert.equal(await page.locator('#dialog-title').innerText(),name);await page.keyboard.press('Escape');
 await page.locator('[data-view="connections"]').click();assert(await page.locator('.flow').count()>0);
 await page.locator('#tools-open').click();await page.locator('#diagnostic-target').fill('192.0.2.10');await page.locator('#diagnostic-run').click();await page.waitForFunction(()=>document.querySelector('#diagnostic-output').textContent.includes('SIMULATED'));
 await page.locator('#motion').click();assert.equal(await page.locator('.flow').first().evaluate(e=>getComputedStyle(e).animationName),'none');await page.locator('#motion').click();await page.locator('#tools-close').click();
 await page.locator('#sound').click();assert.equal(await page.locator('#sound').getAttribute('aria-pressed'),'true');await page.locator('#sound').click();
 await page.locator('#notification-bell').click();assert.equal(await page.locator('#dialog-title').innerText(),'Current alerts');await page.keyboard.press('Escape');
 const refreshed=page.waitForResponse(r=>r.url().endsWith('/api/v1/snapshot'));await page.locator('#freshness').click();await refreshed;
 await page.locator('#rotate-seconds').fill('5');await page.locator('#rotate-seconds').blur();await page.locator('#rotate').click();assert.match(await page.locator('#rotate').innerText(),/Auto ON \(9s\)/);
 await page.locator('#tools-open').click();await page.waitForTimeout(9500);assert.equal(await page.locator('[aria-current=page]').getAttribute('data-view'),'connections');await page.locator('#tools-close').click();
 await page.waitForFunction(()=>document.querySelector('[aria-current=page]').dataset.view==='servers',{},{timeout:15000});await page.locator('#rotate').click();await page.locator('#rotate-seconds').fill('25');await page.locator('#rotate-seconds').blur();await page.locator('[data-view="connections"]').click();
 await page.emulateMedia({reducedMotion:'reduce'});await page.waitForFunction(()=>{const flow=document.querySelector('.flow');return flow&&getComputedStyle(flow).animationName==='none';});await page.emulateMedia({reducedMotion:'no-preference'});
 await page.locator('#alert-summary').click();assert(await page.locator('#details').evaluate(d=>d.open));await page.keyboard.press('Escape');
 for(const size of [{width:1366,height:768},{width:3840,height:2160},{width:390,height:844}]){await page.setViewportSize(size);for(const name of ['connections','devices','ports','services','containers']){await page.locator(`[data-view="${name}"]`).click();await page.waitForFunction(name=>document.querySelector('[aria-current=page]')?.dataset.view===name,name);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${name}/${size.width} overflow`);}await page.screenshot({path:`artifacts/layout-${size.width}.png`});}
 await page.setViewportSize({width:1920,height:1080});
 for(const mode of ['country','world']){
  const geographic=JSON.parse(execFileSync(process.env.PYTHON||'python3',['-c','import json,sys; from noctv.config import load,public; print(json.dumps(public(load(sys.argv[1]))))',`config/map-${mode}.example.json`],{encoding:'utf8',maxBuffer:4*1024*1024}));
  await page.route('**/api/v1/config',r=>r.fulfill({json:geographic}));
  await page.goto(url);await page.waitForSelector('.country-layer path');
  assert.equal(await page.locator('.geographic [data-action="site"]').count(),4);
  assert.equal(await page.locator('.country-layer path:not(.region)').count(),mode==='country'?1:240);
  assert.equal(await page.locator('.geographic .edge').count(),3);
  if(mode==='country'){assert.equal(await page.locator('.region').count(),27);assert.equal(await page.locator('.active-region').count(),4);}
  assert(!await page.locator('.country-layer').evaluate(e=>e.innerHTML.includes('NaN')));
  for(const width of [1920,390,3840]){
   await page.setViewportSize({width,height:width===390?844:1080});
   await page.waitForFunction(()=>document.querySelector('.country-layer')?.viewBox.baseVal.width===document.querySelector('.geographic')?.clientWidth);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),mode+' overflow');
   assert(await page.locator('.geographic').evaluate(g=>[...g.querySelectorAll('[data-action="site"]')].every(e=>parseFloat(e.style.left)>0&&parseFloat(e.style.left)<100&&parseFloat(e.style.top)>0&&parseFloat(e.style.top)<100)));
  }
  await page.setViewportSize({width:1920,height:1080});
  await page.locator('.geographic [data-id="hq"]').click();assert.equal(await page.locator('#dialog-title').innerText(),'Headquarters');await page.keyboard.press('Escape');
  await page.locator('#tools-open').focus();await page.mouse.move(0,0);
  await page.screenshot({path:`artifacts/map-${mode}.png`});
  if(mode==='country'){
   delete geographic.map.positions.hq;
   await page.reload();await page.waitForSelector('.country-layer path');
   assert.equal(await page.locator('.geographic [data-action="site"]').count(),3);
   assert.match(await page.locator('.map-caption').innerText(),/1 sites outside/);
   assert.equal(await page.locator('.geographic .edge').count(),0);
  }
  await page.unroute('**/api/v1/config');
 }
 await page.goto(url+'/#containers');await page.waitForSelector('.monitor-card');
 await page.locator('#stage .card-open').first().click();assert.match(await page.locator('#dialog-body').innerText(),/Healthcheck/);await page.keyboard.press('Escape');
 await page.locator('#tools-open').click();await page.locator('#visible-views input[value="containers"]').uncheck();
 assert.equal(await page.locator('[data-view="containers"]').count(),0);assert.equal(await page.locator('[aria-current=page]').getAttribute('data-view'),'connections');
 await page.reload();await page.waitForSelector('.site-card');assert.equal(await page.locator('[data-view="containers"]').count(),0);
 await page.locator('#tools-open').click();for(const v of ['servers','ports','switches','printers','wireless','devices'])await page.locator(`#visible-views input[value="${v}"]`).uncheck();
 await page.locator('#tools-close').click();await page.locator('#rotate-seconds').fill('5');await page.locator('#rotate-seconds').blur();await page.locator('#rotate').click();
 await page.waitForFunction(()=>document.querySelector('[aria-current=page]')?.dataset.view==='services',{},{timeout:15000});await page.locator('#rotate').click();
 await page.locator('#tools-open').click();await page.locator('#visible-views input[value="connections"]').uncheck();await page.locator('#visible-views input[value="services"]').click();assert(await page.locator('#visible-views input[value="services"]').isChecked());assert.equal(await page.locator('#nav a').count(),1);
 await page.locator('#views-reset').click();assert.equal(await page.locator('#nav a').count(),9);await page.locator('#tools-close').click();await page.locator('#rotate-seconds').fill('25');await page.locator('#rotate-seconds').blur();
 await page.locator('[data-view="connections"]').click();await page.setViewportSize({width:3840,height:2160});await page.locator('#tv-profile').selectOption('4k');assert.equal(await page.locator('body').evaluate(e=>e.style.zoom),'2');await page.reload();await page.waitForSelector('.site-card');assert.equal(await page.locator('#tv-profile').inputValue(),'4k');await page.locator('#tv-profile').selectOption('auto');await page.setViewportSize({width:1920,height:1080});
 const changed=await (await fetch(url+'/api/v1/snapshot')).json();
 const sw=changed.devices.find(d=>d.type==='switch');sw.ports[0].state='down';
 await page.route('**/api/v1/snapshot',r=>r.fulfill({json:changed}));
 await page.goto(url+'/#switches');
 const tiny=page.locator(`[data-device="${sw.id}"] .mini-port[data-port="1"]`);
 await page.waitForFunction(id=>document.querySelector(`[data-device="${id}"] .mini-port[data-port="1"]`)?.dataset.state==='down',sw.id);
 await page.locator(`#stage [data-action="device"][data-id="${sw.id}"]`).click();
 assert.equal(await page.locator('.port[data-port="1"]').getAttribute('data-state'),'down');
 sw.ports[0].state='up';
 await page.waitForFunction(()=>document.querySelector('.port[data-port="1"]')?.dataset.state==='up');
 assert.equal(await tiny.getAttribute('data-state'),'up');await page.keyboard.press('Escape');
 await page.goto(url+'/#services');await page.waitForSelector('.monitor-card');const service=changed.devices.find(d=>d.type==='service');service.state='down';await page.waitForFunction(id=>document.querySelector(`[data-id="${id}"]`)?.closest('.device-card').dataset.state==='down',service.id);service.state='up';await page.waitForFunction(id=>document.querySelector(`[data-id="${id}"]`)?.closest('.device-card').dataset.state==='up',service.id);
 await page.unroute('**/api/v1/snapshot');
 await page.goto(url);await page.waitForSelector('.site-card');await page.locator('[data-view="devices"]').click();
 await page.route('**/api/v1/snapshot',r=>r.fulfill({status:503,body:'unavailable'}));await page.waitForSelector('#error:not([hidden])');assert(await page.locator('.device-card[data-state="unknown"]').count()>0);
 await page.locator('[data-view="servers"]').click();assert.match(await page.locator('.storage-panel').first().innerText(),/No storage inventory/);assert(!await page.locator('.hardware-readings .state[data-state="up"]').count());
 await page.locator('[data-view="containers"]').click();assert.match(await page.locator('.monitor-facts').first().innerText(),/unknown/);assert.equal(await page.locator('.monitor-card[data-state="up"]').count(),0);
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 console.log('PASS: nine views, visible-screen preferences and rotation, service refresh, container failures, toolbar diagnostics, 1080p fit, site/port dialogs, refresh, motion, responsive layouts, country/world maps, missing coordinates, failed-source display and no external requests');
}finally{await browser?.close();server.kill();}
