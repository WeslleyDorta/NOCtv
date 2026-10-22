import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const recording=JSON.parse(fs.readFileSync(path.join(root,'assets/recording.json')));
const copy={
 connections:[['Your network, across the room','TV overview. Explore each site from your desk.'],['Sua rede, vista de longe','Visão para TV. Explore cada unidade no computador.']],
 site:[['Open a site. See the context.','Firewall, interfaces and discovered connections.'],['Abra a unidade. Veja o contexto.','Firewall, interfaces e conexões descobertas.']],
 switches:[['Follow the network path','Branching topology with interface states.'],['Siga o caminho da rede','Topologia em ramificações e estado das interfaces.']],
 port:[['Inspect a port. Watch it recover.','Simulated DOWN → UP, with discovered equipment.'],['Inspecione a porta. Acompanhe a recuperação.','DOWN → UP simulado, com o equipamento descoberto.']],
 ports:[['Focus on actionable ports','Required interfaces and negotiated link speeds.'],['Foco nas portas que exigem ação','Interfaces essenciais e velocidades negociadas.']],
 servers:[['Track capacity and hardware','CPU, memory, storage and available health readings.'],['Acompanhe capacidade e hardware','CPU, memória, armazenamento e sensores disponíveis.']],
 printers:[['See supplies before they run out','Printer availability and toner levels.'],['Veja os suprimentos antes de acabar','Disponibilidade das impressoras e níveis de toner.']],
 wireless:[['Keep wireless in view','Access points, clients and reported metrics.'],['Acompanhe a rede sem fio','Access points, clientes e métricas coletadas.']],
 devices:[['Organize equipment by category','Find an offline device without a wall of text.'],['Organize equipamentos por categoria','Identifique dispositivos offline por grupo.']],
 services:[['A failure becomes a recovery','HTTP, TLS, TCP, DNS and ping checks.'],['Uma falha dá lugar à recuperação','Checks de HTTP, TLS, TCP, DNS e ping.']],
 containers:[['Check the workload, not just the host','Docker runtime and application healthcheck.'],['Acompanhe também os containers','Estado do Docker e healthcheck da aplicação.']],
 tools:[['Choose what belongs on your TV','Hide unused screens. Keep the relevant views.'],['Escolha o que aparece na TV','Oculte telas sem uso. Mantenha as informações relevantes.']]
};
const esc=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const style=`#root{position:absolute;inset:0;font-family:Inter,sans-serif;color:#eef5f7}.ground{position:absolute;inset:0;background:#080e10}.viewport{position:absolute;inset:120px 0 0;overflow:hidden}.camera{position:absolute;inset:0}.recording{position:absolute;inset:0;width:1920px;height:960px;object-fit:contain}.header{position:absolute;top:0;left:0;width:1920px;height:120px;background:#101b22;border-bottom:1px solid #2a454d}.headline{position:absolute;top:18px;left:108px;font-size:42px;line-height:1.18;font-weight:600;letter-spacing:-.025em;margin:0}.headline span{display:inline-block}.description{position:absolute;top:74px;left:108px;font-size:28px;line-height:1.2;color:#b4c8d2;margin:0}.label{position:absolute;right:108px;top:25px;font-size:28px;color:#e9b968;line-height:1.2}.progress{position:absolute;left:0;bottom:0;height:4px;background:#79d7e8;width:1920px;transform-origin:left center}`;
const chapters=[];
const language=process.argv[2]||'en';
assert(['en','pt-BR'].includes(language));
for(const [lang,idx]of [[language,language==='en'?0:1]]){
 let time=0;const hosts=[],sounds=[];
 for(const shot of recording.shots){
  const id=shot.id+'-'+lang,[title,sub]=copy[shot.id][idx];
  const zoom=shot.id==='port'?`tl.fromTo('#${id}-camera',{scale:1,transformOrigin:'50% 44%'},{scale:1.25,duration:.5,ease:'power2.inOut'},1.5);`:shot.id==='site'?`tl.fromTo('#${id}-camera',{scale:1,transformOrigin:'50% 48%'},{scale:1.14,duration:.5,ease:'power2.inOut'},1.1);`:'';
  const markup=`<template><style>${style}</style><div id="root" data-composition-id="${id}" data-width="1920" data-height="1080"><div class="ground"></div><div class="viewport" data-layout-allow-overflow><div class="camera" id="${id}-camera"><video id="${id}-video" class="clip recording" src="assets/${shot.id}.mp4" data-start="0" data-duration="${shot.duration}" data-track-index="0" muted playsinline></video></div></div><div class="header clip" id="${id}-header" data-start="0" data-duration="${shot.duration}" data-track-index="1"><h1 id="${id}-title" class="headline" data-var-text="${shot.id}Title">${esc(title)}</h1><p class="description" data-var-text="${shot.id}Description">${esc(sub)}</p><span class="label">${idx?'DADOS SIMULADOS':'SIMULATED DATA'}</span></div><div class="progress" id="${id}-progress"></div></div><script>const tl=gsap.timeline({paused:true});tl.fromTo('#${id}-title',{opacity:.3,filter:'blur(5px)'},{opacity:1,filter:'blur(0px)',duration:.2,ease:'power3.out'},0);tl.fromTo('#${id}-progress',{scaleX:${time/75}},{scaleX:${(time+shot.duration)/75},duration:${shot.duration},ease:'none'},0);${zoom}window.__timelines['${id}']=tl;</script></template>`;
  fs.writeFileSync(path.join(root,'compositions',id+'.html'),markup);
  hosts.push(`<div id="${id}" class="clip" data-composition-id="${id}" data-composition-src="compositions/${id}.html" data-start="${time}" data-duration="${shot.duration}" data-width="1920" data-height="1080" data-track-index="0" data-track-kind="graphics"></div>`);
  chapters.push({id:shot.id,start:time,duration:shot.duration,en:title,pt:copy[shot.id][1][0]});
  for(const t of recording.clicks.filter(t=>t>=shot.start&&t<shot.start+shot.duration))sounds.push(`<audio id="click-${sounds.length}" class="clip" src="assets/click.mp3" data-start="${(time+t-shot.start+.033).toFixed(3)}" data-duration="0.4" data-volume="0.45" data-track-index="2"></audio>`);
  time+=shot.duration;
 }
 assert.equal(time,67);
 const id='start-'+lang;
 const ending=idx?['Para a TV. Para investigar de perto.','Comece pela demo. Conecte suas fontes.','Configure fontes → altere para live → reinicie','No modo real, os dados fictícios deixam de aparecer.']:['Across the room. At your desk.','Start with the demo. Connect your tools.','Configure sources → switch to live → restart','Live mode shows your sources, without demo devices.'];
 fs.writeFileSync(path.join(root,'compositions',id+'.html'),`<template><style>${style}.mark{position:absolute;left:170px;top:205px;width:128px;height:128px}.wordmark{position:absolute;left:330px;top:220px;font-size:92px;line-height:1;font-weight:650;margin:0}.message{position:absolute;left:170px;top:385px;font-size:54px;letter-spacing:-.03em;font-weight:600}.support{position:absolute;left:170px;top:475px;font-size:32px;color:#b4c8d2}.command{position:absolute;left:170px;top:565px;font:32px 'IBM Plex Mono',monospace;color:#79d7e8}.steps{position:absolute;left:170px;top:640px;font-size:30px}.note{position:absolute;left:170px;top:695px;font-size:28px;color:#b4c8d2}.repo{position:absolute;left:170px;top:825px;font-size:36px;color:#79d7e8}</style><div id="root" data-composition-id="${id}" data-width="1920" data-height="1080"><div class="ground"></div><div class="clip" id="${id}-content" data-start="0" data-duration="8" data-track-index="0" data-hold><img id="${id}-mark" class="mark" src="assets/noctv.svg"><h1 class="wordmark">NOCtv</h1><div class="message">${ending[0]}</div><div class="support">${ending[1]}</div><code class="command">docker compose up --build -d</code><div class="steps">${ending[2]}</div><div class="note">${ending[3]}</div><div class="repo">github.com/WeslleyDorta/NOCtv</div></div><div class="progress" id="${id}-progress"></div></div><script>const tl=gsap.timeline({paused:true});tl.fromTo('#${id}-mark',{scale:.85,opacity:.4},{scale:1,opacity:1,duration:.45,ease:'power4.out'},0);tl.fromTo('#${id}-progress',{scaleX:${67/75}},{scaleX:1,duration:8,ease:'none'},0);window.__timelines['${id}']=tl;</script></template>`);
 hosts.push(`<div id="${id}" class="clip" data-composition-id="${id}" data-composition-src="compositions/${id}.html" data-start="67" data-duration="8" data-width="1920" data-height="1080" data-track-index="0" data-track-kind="graphics"></div>`);
 const variables=Object.entries(copy).flatMap(([key,text])=>[{id:key+'Title',type:'string',label:key+' title',default:text[idx][0]},{id:key+'Description',type:'string',label:key+' description',default:text[idx][1]}]);
 const html=`<!doctype html><html lang="${lang}" data-composition-variables='${JSON.stringify(variables)}'><head><meta charset="UTF-8"><title>NOCtv tour · ${lang}</title><script src="assets/gsap.min.js"></script><style>*{box-sizing:border-box}html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:#080e10}#root{position:relative;width:1920px;height:1080px}</style></head><body><div id="root" data-composition-id="main" data-start="0" data-duration="75" data-width="1920" data-height="1080">${hosts.join('\n')}${sounds.join('\n')}</div><script>window.__timelines=window.__timelines||{};window.__timelines.main=gsap.timeline({paused:true});</script></body></html>`;
 fs.writeFileSync(path.join(root,'index.html'),html);
}
chapters.push({id:'start',start:67,duration:8,en:'Try NOCtv',pt:'Experimente o NOCtv'});
fs.writeFileSync(path.join(root,'chapters.json'),JSON.stringify(chapters,null,2));
console.log('Built '+language+' HyperFrames composition: 75 seconds.');
