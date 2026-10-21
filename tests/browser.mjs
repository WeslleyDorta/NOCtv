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
 await page.goto(url);await page.waitForSelector('.site-card');
 assert.match(await page.locator('#mode').innerText(),/SIMULATED/);
 fs.mkdirSync('artifacts',{recursive:true});
 for(const name of ['connections','switches','ports','servers','printers','wireless','devices']){
  await page.locator(`[data-view="${name}"]`).click();await page.waitForFunction(name=>document.querySelector('[aria-current=page]')?.dataset.view===name,name);
  assert.equal(await page.locator('[aria-current="page"]').count(),1);
  await page.screenshot({path:`artifacts/${name}.png`});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),name+' horizontal overflow');
  assert(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight),name+' vertical page overflow');
 }
 await page.locator('[data-view="connections"]').click();await page.locator('.graph-node[data-id="hq"]').click();assert(await page.locator('#details').evaluate(d=>d.open));assert.equal(await page.locator('#dialog-title').innerText(),'Headquarters');await page.keyboard.press('Escape');
 await page.locator('[data-view="switches"]').click();await page.locator('.graph-node[data-action="device"]').first().click();await page.locator('.port').first().click();assert.match(await page.locator('.port-detail').innerText(),/DEMO/);await page.screenshot({path:'artifacts/port-detail.png'});
 const name=await page.locator('#dialog-title').innerText();await page.waitForTimeout(5500);assert.equal(await page.locator('#dialog-title').innerText(),name);await page.keyboard.press('Escape');
 await page.locator('[data-view="connections"]').click();assert(await page.locator('.flow').count()>0);
 await page.locator('#motion').click();assert.equal(await page.locator('.flow').first().evaluate(e=>getComputedStyle(e).animationName),'none');await page.locator('#motion').click();
 await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator('.flow').first().evaluate(e=>getComputedStyle(e).animationName),'none');await page.emulateMedia({reducedMotion:'no-preference'});
 await page.locator('#alert-summary').click();assert(await page.locator('#details').evaluate(d=>d.open));await page.keyboard.press('Escape');
 for(const size of [{width:1366,height:768},{width:3840,height:2160},{width:390,height:844}]){await page.setViewportSize(size);for(const name of ['connections','devices','ports']){await page.locator(`[data-view="${name}"]`).click();await page.waitForFunction(name=>document.querySelector('[aria-current=page]')?.dataset.view===name,name);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${name}/${size.width} overflow`);}await page.screenshot({path:`artifacts/layout-${size.width}.png`});}
 await page.setViewportSize({width:1920,height:1080});
 for(const mode of ['country','world']){
  const geographic=JSON.parse(execFileSync(process.env.PYTHON||'python3',['-c','import json,sys; from noctv.config import load,public; print(json.dumps(public(load(sys.argv[1]))))',`config/map-${mode}.example.json`],{encoding:'utf8',maxBuffer:4*1024*1024}));
  await page.route('**/api/v1/config',r=>r.fulfill({json:geographic}));
  await page.goto(url);await page.waitForSelector('.country-layer path');
  assert.equal(await page.locator('.geographic [data-action="site"]').count(),4);
  assert.equal(await page.locator('.country-layer path').count(),mode==='country'?1:240);
  assert.equal(await page.locator('.geographic .edge').count(),3);
  assert(!await page.locator('.country-layer').evaluate(e=>e.innerHTML.includes('NaN')));
  for(const width of [1920,390,3840]){
   await page.setViewportSize({width,height:width===390?844:1080});
   await page.waitForFunction(()=>document.querySelector('.country-layer')?.viewBox.baseVal.width===document.querySelector('.geographic')?.clientWidth);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),mode+' overflow');
   assert(await page.locator('.geographic').evaluate(g=>[...g.querySelectorAll('[data-action="site"]')].every(e=>parseFloat(e.style.left)>0&&parseFloat(e.style.left)<100&&parseFloat(e.style.top)>0&&parseFloat(e.style.top)<100)));
  }
  await page.setViewportSize({width:1920,height:1080});
  await page.locator('.geographic [data-id="hq"]').click();assert.equal(await page.locator('#dialog-title').innerText(),'Headquarters');await page.keyboard.press('Escape');
  await page.locator('#motion').focus();await page.mouse.move(0,0);
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
 await page.goto(url);await page.waitForSelector('.site-card');await page.locator('[data-view="devices"]').click();
 await page.route('**/api/v1/snapshot',r=>r.fulfill({status:503,body:'unavailable'}));await page.waitForSelector('#error:not([hidden])');assert(await page.locator('.device-card[data-state="unknown"]').count()>0);
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 console.log('PASS: seven views, 1080p fit, site/port dialogs, refresh, motion, responsive layouts, country/world maps, missing coordinates, failed-source display and no external requests');
}finally{await browser?.close();server.kill();}
