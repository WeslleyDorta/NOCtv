import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.NOCTV_PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.NOCTV_CHROMIUM?{executablePath:process.env.NOCTV_CHROMIUM}:{})});
try {
 const page=await browser.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(new URL('../../../docs/video/index.html',import.meta.url).href);
 await page.waitForFunction(()=>document.querySelector('video').readyState>=1);
 assert.equal(await page.locator('#chapters button').count(),13);
 assert.equal(await page.locator('video').evaluate(v=>v.duration),75);
 await page.locator('button[data-start="20"]').click();
 await page.waitForFunction(()=>document.querySelector('video').currentTime>=20);
 await page.locator('video').evaluate(v=>v.pause());
 const time=await page.locator('video').evaluate(v=>v.currentTime);
 await page.selectOption('#language','pt-BR');
 await page.waitForFunction(()=>document.querySelector('video').readyState>=1&&document.querySelector('video').currentTime>=20);
 assert(Math.abs(await page.locator('video').evaluate(v=>v.currentTime)-time)<1);
 assert.equal(await page.locator('html').getAttribute('lang'),'pt-BR');
 assert.match(await page.locator('button[data-start="20"]').innerText(),/recuperação/);
 assert.deepEqual(errors,[]);
 console.log('PASS: media loads, 13 chapters, seeking, language switch preserves playback, no browser errors');
} finally {await browser.close();}
