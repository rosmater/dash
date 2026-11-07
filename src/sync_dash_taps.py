#!/usr/bin/env python3
"""Rost 27.10 t3902–t3903: тапы с даша → contacts автоматически.
Кладёшь JSON в sync/inbox/*.json:
 {"spheres":[{"key","channel","title","sphere"}],
  "ignores":[{"id","channel","title","kind","perm","ignored_at"|null}]}   (ignored_at=null → вернуть)
Скрипт: chats.csv.direction (по title+channel, иначе новая строка), src/ignored_chats.json (дедуп по id),
затем build_test_ma.sh + build.sh + push в /workspace/dash-gh, файлы → sync/done/.
Также: key 'cu|…'/channel ClickUp → src/cu_dir_overrides.json (build_data убирает из «на сортировку»); action cu_close / cu_ok → sync/cu_actions_pending.json.
Запуск: python3 src/sync_dash_taps.py [--no-push]. Запускает вочер/утренняя мега, если в inbox есть файлы."""
import json, csv, os, sys, glob, shutil, subprocess, datetime, re
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INB, DONE = f'{R}/sync/inbox', f'{R}/sync/done'
CSV='/home/box/contacts/chats.csv'; IGN=f'{R}/src/ignored_chats.json'
CH={'telegram':'telegram','tg':'telegram','whatsapp esp':'whatsapp','whatsapp ukr':'whatsapp','whatsapp':'whatsapp','viber':'viber','instagram':'instagram'}
files=sorted(glob.glob(f'{INB}/*.json'))
if not files: print('inbox empty'); sys.exit(0)
today=datetime.date.today().isoformat()
rows=list(csv.DictReader(open(CSV))); fields=list(rows[0].keys()) if rows else None
ign=json.load(open(IGN)); byid={c['id']:c for c in ign.get('chats',[])}
ns=ni=nc=na=0
# Rost t3955u: CU-направления и действия (ДР «поздравил») — не в chats.csv
OVF=f'{R}/src/cu_dir_overrides.json'; ACT=f'{R}/sync/cu_actions_pending.json'
ov=json.load(open(OVF)) if os.path.exists(OVF) else {'tasks':{}}
act=json.load(open(ACT)) if os.path.exists(ACT) else {'note':'Действия с даша для ClickUp. Закрывает рутина COMMS/скрипт через ClickUp API (cu_close → status complete), затем переносит запись в done[].','pending':[],'done':[]}
MOF=f'{R}/src/msg_sphere_overrides.json'; mo=json.load(open(MOF)) if os.path.exists(MOF) else {'chats':{}}
ROF=f'{R}/src/msg_row_overrides.json'; ro=json.load(open(ROF)) if os.path.exists(ROF) else {'state':{},'cu':{},'tags':{}}
for _k in ('state','cu','tags'): ro.setdefault(_k,{})
nr=0; nb=0
cuid=lambda u:(re.search(r'/t/(?:\d+/)?([0-9a-z]+)',u or '') or [None,None])[1]
for f in files:
    try: d=json.load(open(f))
    except Exception as e: print('bad', f, e); continue
    for s in d.get('spheres',[]):
        if s.get('action')=='bot_attn':  # Rost t4144–46: 📄/🙋 на CU for check → sync/bot_attn.jsonl, только для этого ответа (rev = CU updated)
            if s.get('cu') and s.get('need') in ('rost','ok'):
                _row=dict(ts=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).isoformat(timespec='seconds'),bot=s.get('bot') or '',need=s['need'],cu=str(s['cu']),title=(s.get('title') or '')[:160],note='тап с даша',src='dash',rev=s.get('rev') or s.get('updated') or '',updated=s.get('updated') or s.get('rev') or '',tapped_at=s.get('at'))
                with open(f'{R}/sync/bot_attn.jsonl','a',encoding='utf-8') as _f: _f.write(json.dumps(_row,ensure_ascii=False)+'\n')
                nb+=1
            continue
        if s.get('action')=='rt_ok':  # Rost t3972u: ✓ «рутина упала» на даше → на проверку боту
            ro.setdefault('rt_ack',{})[f"{s.get('bot')}|{s.get('routine')}"]={'at':s.get('at') or today,'checked':False}; nr+=1; continue
        if s.get('action') in ('row_st','cu_unlink','row_tags'):  # Rost t3969u: ✓/✕ строки, открепить CU, теги Личного
            k=s.get('row') or (s.get('key') or '').split('|',1)[-1]; at=s.get('at') or today
            if s['action']=='row_st':
                if s.get('st'): ro['state'][k]={'st':s['st'],'at':at}
                else: ro['state'].pop(k,None)
            elif s['action']=='cu_unlink':
                if s.get('unlink'): ro['cu'][k]={'unlinked':True,'was':(ro['cu'].get(k) or {}).get('id') or s.get('cu_id'),'src':'dash','at':at}
                else: ro['cu'].pop(k,None)
            else:
                if s.get('tags'): ro['tags'][k]={'tags':s['tags'],'src':'dash','at':at}
                else: ro['tags'].pop(k,None)
            nr+=1; continue
        if s.get('action')=='cu_ok':  # Rost t4797: ✓ на CU for check → очередь: снять for check → to do + due завтра
            i=str(s.get('cu') or '').strip() or cuid(s.get('url') or s.get('key'))
            if i and not any(a.get('id')==i and a.get('action')=='cu_ok' and a.get('updated')==s.get('updated') for a in act['pending']+act['done']):
                act['pending'].append({'id':i,'action':'cu_ok','kind':'for_check','title':s.get('title'),'bot':s.get('bot'),'updated':s.get('updated'),'tapped_at':s.get('at')}); na+=1
            continue
        if s.get('action')=='cu_close':
            i=cuid(s.get('url')) or (s.get('key') or '').split('|')[-1]
            if i and not any(a['id']==i and a.get('due')==s.get('due') for a in act['pending']+act['done']):
                act['pending'].append({'id':i,'action':'cu_close','kind':s.get('kind'),'title':s.get('title'),'url':s.get('url'),'due':s.get('due'),'tapped_at':s.get('at')}); na+=1
            continue
        if (s.get('key') or '').startswith('cu|') or (s.get('channel') or '')=='ClickUp':
            i=cuid(s.get('url') or s.get('key'))
            if i:
                if s.get('sphere'): ov['tasks'][i]={'sphere':s['sphere'],'name':s.get('title'),'url':s.get('url'),'at':s.get('at') or today}
                else: ov['tasks'].pop(i,None)
                nc+=1
            continue
        t=(s.get('title') or '').strip(); ch=CH.get((s.get('channel') or '').lower(), (s.get('channel') or '').lower())
        if s.get('key') and '|' in s['key']:  # Rost t3961u: строка мессенджера → msg_sphere_overrides (✕ = __unsort; пусто = снять)
            if s.get('sphere'):
                _k=s['key']; _sp=s['sphere']; _old=mo['chats'].get(_k) or {}; _old_sp=_old.get('sphere') or ''
                # t5334u: leftover ✕ resync must not overwrite a sphere Rost already picked
                if _sp=='__unsort' and s.get('resync') and _old_sp and _old_sp not in ('__unsort','Игнор'):
                    print('skip stale unsort resync', _k, 'keep', _old_sp); ns+=1; continue
                mo['chats'][_k]={'sphere':_sp,'at':s.get('at') or today}
            else: mo['chats'].pop(s['key'],None)
        if not t or not s.get('sphere') or s.get('sphere') in ('__unsort',): ns+=1; continue
        hit=[r for r in rows if r['title'].strip().lower()==t.lower() and (not ch or r['channel'].lower()==ch)]
        if hit:
            for r in hit: r['direction']=s['sphere']; r['updated']=today
        else:
            cid=(ch[:2] if ch else 'x')+'-'+re.sub(r'\W+','-',t.lower()).strip('-')
            rows.append({**{k:'' for k in fields}, 'chat_id':cid,'channel':ch,'title':t,'direction':s['sphere'],'status':'active','notes':'из даша (sync)','updated':today})
        ns+=1
    for g in d.get('ignores',[]):
        i=g.get('id') or f"{g.get('channel')}|{g.get('title')}"
        if g.get('ignored_at') is None: byid.pop(i,None)
        else: byid[i]={k:g.get(k) for k in ('channel','title','kind','perm','ignored_at')}|{'id':i}
        ni+=1
shutil.copy(CSV, CSV+'.bak-sync'); shutil.copy(IGN, IGN+'.bak-sync')
with open(CSV,'w',newline='') as _fh:  # Rost t4380: раньше хэндл не закрывался → сборка ниже читала недописанный chats.csv (хвост = свежие сортировки терялся)
    w=csv.DictWriter(_fh, fieldnames=fields); w.writeheader(); w.writerows(rows)
ign['chats']=list(byid.values())
with open(IGN,'w') as _fh: json.dump(ign, _fh, ensure_ascii=False, indent=1)
for _o,_p in ((ro,ROF),(mo,MOF),(ov,OVF),(act,ACT)):
    with open(_p,'w') as _fh: json.dump(_o,_fh,ensure_ascii=False,indent=1)
for f in files: shutil.move(f, f'{DONE}/{os.path.basename(f)}')
print(f'spheres {ns}, ignores {ni}, cu_dir {nc}, cu_actions {na}, rows {nr}, bot_attn {nb}')
if '--no-push' in sys.argv: sys.exit(0)
subprocess.run(['bash',f'{R}/src/build_test_ma.sh'],check=True); subprocess.run(['bash',f'{R}/src/build.sh'],check=True)
G='/workspace/dash-gh'
subprocess.run(['git','-C',G,'pull','-q','--ff-only'],check=True)
for f in ['index.html','helper.html','variant-a.html','data.enc.json','data-asst.enc.json','data-test-ma.enc.json','test-messengers-assistants.html','docs/CHANGELOG.md','docs/DECISIONS.md']: shutil.copy(f'{R}/{f}', f'{G}/{f}')
subprocess.run(['git','-C',G,'add','-A'])
if subprocess.run(['git','-C',G,'diff','--cached','--quiet']).returncode:
    subprocess.run(['git','-C',G,'-c','user.name=rosmater','-c','user.email=rost@rosmater.local','commit','-qm',f'sync: тапы даша → contacts ({ns} сфер, {ni} игнор, {nc} CU-направл., {na} CU-действ., {nr} строк ✓/✕/CU/теги, {nb} нужен/отчёт)'],check=True)
    subprocess.run(['git','-C',G,'push','-q'],check=True)
print('pushed')
