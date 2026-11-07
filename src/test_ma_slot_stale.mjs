#!/usr/bin/env node
/** t5394u: actual dashboard morning-only paint, independent of process timezone. */
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const html=readFileSync(new URL('./variant-a.html', import.meta.url),'utf8');
const start=html.indexOf('const maLiveKey=');
const end=html.indexOf('const maRecShort=',start);
if(start<0||end<0)throw Error('dashboard helpers not found');
const ctx=vm.createContext({Intl,Date});
vm.runInContext(html.slice(start,end)+';globalThis.stale=maLiveStale;globalThis.slot=maRequiredSlot;',ctx);
const bog=(day,hm)=>Date.parse(`${day}T${hm}:00-05:00`);
const channels=['WhatsApp UKR','WhatsApp ESP','Telegram','Viber','Instagram'];
let count=0;
function check(label,now,at,want,ch='Telegram'){
 const d={watchers:{[ch]:{live_at:at}}};
 const got=ctx.stale(d,ch,now);
 if(got!==want)throw Error(`${label}: ${ch} got ${got} want ${want}`);
 if(ctx.slot(now).label!=='09:00')throw Error('invented non-morning slot');
 count++;
}
for(const ch of channels){
 for(const [hm,at,want] of [
  ['08:00','',false],['08:45','',false],['10:29','',false],
  ['10:30','',true],['10:30','2026-11-05 13:20 Bogotá',true],
  ['11:00','2026-11-06 08:29 Bogotá',true],
  ['11:00','2026-11-06 08:30 Bogotá',false],
  ['14:30','2026-11-06 09:20 Bogotá',false],
  ['20:00','2026-11-06 09:20 Bogotá',false],
  ['20:00','2026-11-06 16:00 Bogotá',false],
  ['22:59','',true],['23:00','',false]])
   check(hm,bog('2026-11-06',hm),at,want,ch);
}
for(const ch of ['ClickUp','Email','Gmail'])
 check('not a messenger slot',bog('2026-11-06','15:00'),'',false,ch);
console.log(`ALL PASS: ${count} actual dashboard morning-only cases`);
