import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.NOCTV_PLAYWRIGHT_MODULE||'playwright');
const base='http://127.0.0.1:8768';
const server=spawn(process.env.PYTHON||'python3',['-m','noctv','serve','--port','8768'],{stdio:'ignore'});
let browser;
try{
 for(let i=0;i<100;i++){try{if((await fetch(base+'/healthz')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 const config=await(await fetch(base+'/api/v1/config')).json();config.display.max_cards=48;
 const demo=await(await fetch(base+'/api/v1/snapshot')).json();let snapshot;
 browser=await chromium.launch({headless:true,...(process.env.NOCTV_CHROMIUM?{executablePath:process.env.NOCTV_CHROMIUM}:{})});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/v1/config',r=>r.fulfill({json:config}));
 await page.route('**/api/v1/snapshot',r=>r.fulfill({json:snapshot}));
 fs.mkdirSync('artifacts',{recursive:true});
 const views={servers:'server',printers:'printer',wireless:'wireless',devices:'device',services:'service',containers:'container'};
 for(const size of [{width:1920,height:1080},{width:1366,height:768},{width:3840,height:2160}]){
  await page.setViewportSize(size);
  for(const [view,type]of Object.entries(views))for(const count of [0,1,2,8,24,80]){
   const source=demo.devices.find(d=>d.type===type);
   snapshot={...structuredClone(demo),links:[],alerts:[],devices:Array.from({length:count},(_,i)=>({...structuredClone(source),id:`fixture-${i}`,name:`Equipment ${String(i).padStart(3,'0')} with a longer name`,state:i===count-1?'down':'up',category:`Category ${i%5}`,metrics:{...source.metrics,memory_percent:30,disk_percent:40,toner_percent:80},storage:[]}))};
   await page.goto(base+'/?count='+count+'#'+view);await page.waitForFunction(()=>document.querySelector('#sources').textContent.length>0);await page.evaluate(()=>document.fonts.ready);
   if(!count){assert.equal(await page.locator('#stage .device-card').count(),0);assert.match(await page.locator('#stage').innerText(),/No .* reported/);continue;}
   const shown=await page.locator('#stage .device-card').count();assert(shown>0,`${view}/${count}/${size.width} no cards`);
   assert(await page.locator('#stage').evaluate(stage=>{const bounds=stage.getBoundingClientRect(),cards=[...stage.querySelectorAll('.device-card,.equipment-overflow:not([hidden])')].map(c=>c.getBoundingClientRect());return cards.every(c=>c.bottom<=bounds.bottom+1&&c.right<=bounds.right+1)&&cards.every((a,i)=>cards.slice(i+1).every(b=>Math.min(a.right,b.right)-Math.max(a.left,b.left)<=1||Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)<=1));}),`${view}/${count}/${size.width} card overflow or overlap`);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth&&document.documentElement.scrollHeight<=innerHeight),`${view}/${count}/${size.width} page overflow`);
   assert(await page.locator(`#stage [data-id="fixture-${count-1}"]`).count(),`${view} missing critical card`);
   if(count<=2)assert.equal(shown,count);
   if(view==='servers'&&count===1){await page.locator('#stage .card-open').click();assert.equal(await page.locator('#dialog-body .server-capacity').count(),1);assert.equal(await page.locator('#dialog-body .port').count(),source.ports?.length||0);await page.keyboard.press('Escape');}
   if(view==='servers'&&count===8&&size.width===1920)assert.equal(shown,8,'8 servers should fit Full HD');
   const overflow=page.locator('.equipment-overflow');assert.equal(await overflow.isVisible(),shown<count);
   if(shown<count){assert.match(await overflow.innerText(),new RegExp(`^${count-shown} more devices`));await overflow.click();assert.equal(await page.locator('#dialog-body .device-card').count(),count);await page.keyboard.press('Escape');}
   if((view==='servers'&&[1,8,24].includes(count)||['devices','wireless'].includes(view)&&count===24)&&size.width===1920)await page.screenshot({path:`artifacts/adaptive-${view}-${count}.png`});
  }
 }
 // Inventory changes must reflow without a reload or a manual page change.
 await page.setViewportSize({width:1920,height:1080});await page.goto(base+'/#containers');await page.waitForSelector('.monitor-card');
 snapshot.devices=snapshot.devices.slice(0,1);await page.locator('#freshness').click();await page.waitForFunction(()=>document.querySelectorAll('#stage .device-card').length===1);assert(!await page.locator('.equipment-overflow').isVisible());
 const growing=structuredClone(snapshot.devices);
 snapshot.devices=[];await page.locator('#freshness').click();await page.waitForFunction(()=>document.querySelectorAll('#stage .device-card').length===0);
 snapshot.devices=Array.from({length:8},(_,i)=>({...structuredClone(growing[0]),id:`new-${i}`}));await page.locator('#freshness').click();await page.waitForFunction(()=>document.querySelectorAll('#stage .device-card').length===8);
 assert.deepEqual(errors,[]);console.log('PASS: 108 inventory/viewport combinations; no TV overflow/overlap, critical-first selection, full inventory and live add/shrink/empty reflow');
}finally{await browser?.close();server.kill();}
