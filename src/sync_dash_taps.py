#!/usr/bin/env python3
"""Rost 27.10 t3902–t3903: тапы с даша → contacts автоматически.
Кладёшь JSON в sync/inbox/*.json:
 {"spheres":[{"key","channel","title","sphere"}],
  "ignores":[{"id","channel","title","kind","perm","ignored_at"|null}]}   (ignored_at=null → вернуть)
Скрипт: chats.csv.direction (по title+channel, иначе новая строка), src/ignored_chats.json (дедуп по id),
затем build_test_ma.sh + build.sh + push в /workspace/dash-gh, файлы → sync/done/.
Также: key 'cu|…'/channel ClickUp → src/cu_dir_overrides.json (build_data убирает из «на сортировку»); action cu_close / cu_ok / call_done / quick_cmd → sync/cu_actions_pending.json (quick_cmd ещё пишет /workspace/queues/dash-quick-cmds.json и PRIORITY-строку в /workspace/queue/QUEUE.md, затем будит Секретаря webhook'ом).
Rost t6284u/t6285u: action cu_done (и старый cu_close с ключом cuclose|) → src/done_pending.json + cu_review + QUEUE PRIORITY + webhook Секретарю.
Запуск: python3 src/sync_dash_taps.py [--no-push | --push-only]. Запускает вочер/утренняя мега, если в inbox есть файлы."""
import json, csv, os, sys, glob, shutil, subprocess, datetime, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INB, DONE = f'{R}/sync/inbox', f'{R}/sync/done'
CSV='/home/box/contacts/chats.csv'; IGN=f'{R}/src/ignored_chats.json'
CH={'telegram':'telegram','tg':'telegram','whatsapp esp':'whatsapp','whatsapp ukr':'whatsapp','whatsapp':'whatsapp','viber':'viber','instagram':'instagram'}
os.makedirs(INB, exist_ok=True); os.makedirs(DONE, exist_ok=True)  # t6284u: inbox пропал при переезде в dash-gh → все тапы с 11.11 падали в relay
files=sorted(glob.glob(f'{INB}/*.json'))
SELF_TEST='--self-test-qc' in sys.argv
PUSH_ONLY='--push-only' in sys.argv  # t6285u: ретрай незапушенного src/done_pending.json (зовёт tap_relay каждую минуту)
if not files and not SELF_TEST and not PUSH_ONLY: print('inbox empty'); sys.exit(0)
today=datetime.date.today().isoformat()
rows=list(csv.DictReader(open(CSV))); fields=list(rows[0].keys()) if rows else None
ign=json.load(open(IGN)); byid={c['id']:c for c in ign.get('chats',[])}
ns=ni=nc=na=0
# Rost t3955u: CU-направления и действия (ДР «поздравил») — не в chats.csv
OVF=f'{R}/src/cu_dir_overrides.json'; ACT=f'{R}/sync/cu_actions_pending.json'

# Rost t6245u / t6254u: быстрые команды с даша → очередь Секретаря + webhook
QC_JSON='/workspace/queues/dash-quick-cmds.json'
QC_META={
    'order_salmon_shrimp':{'file':'knowledge/rules/dash-quick-commands.md','tag':'El Pulpo','tab':'Личное'},
    'andrey_emergency_logout':{'file':'knowledge/rules/andrey-emergency-logout.md','tag':'Андрей Grok Bot logout','tab':'Табакевич'},
}
QC_MD='/workspace/queue/QUEUE.md'
QC_WEBHOOK_URL='/workspace/queue/bin/webhook-resume-15min.url'
QC_WEBHOOK_AUTH='/workspace/queue/bin/webhook-resume-15min.auth'
QC_HANDLER='/workspace/queue/comms-action-handler.json'

def _bog_now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5)))

def _comms_handler_ok():
    try:
        d=json.load(open(QC_HANDLER))
        return d.get('enabled') is True and d.get('mode')=='action_only_no_resume' and d.get('routine')=='queue-resume-15-webhook' and bool(d.get('verified_by'))
    except Exception:
        return False

def _parse_ts(s):
    if not s: return None
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z','+00:00'))
    except Exception:
        return None

def _qc_recent(pending, cmd, minutes=10):
    now=_bog_now()
    for a in pending:
        if a.get('action')!='quick_cmd' or str(a.get('id') or a.get('cmd') or '')!=cmd:
            continue
        ts=_parse_ts(a.get('tapped_at') or a.get('at'))
        if ts is None: return True
        if ts.tzinfo is None: ts=ts.replace(tzinfo=datetime.timezone.utc)
        if (now-ts).total_seconds() < minutes*60: return True
    return False

def _qc_md_recent(cmd, minutes=10):
    if not os.path.exists(QC_MD): return False
    text=open(QC_MD,encoding='utf-8',errors='replace').read()
    now=_bog_now()
    for line in text.splitlines()[:40]:
        if '[pending]' not in line or 'dash-quick-cmd-'+cmd not in line: continue
        m=re.search(r'dash-quick-cmd-'+re.escape(cmd)+r'-(\d{8})-(\d{4})', line)
        if not m: return True
        try:
            ts=datetime.datetime.strptime(m.group(1)+m.group(2),'%Y%m%d%H%M').replace(tzinfo=datetime.timezone(datetime.timedelta(hours=-5)))
        except Exception:
            return True
        if (now-ts).total_seconds() < minutes*60: return True
    return False

def _wake_comms(reason, extra=None):
    """t6284u: разбудить Секретаря тем же action-only webhook, что быстрые команды."""
    if not _comms_handler_ok() or not os.path.exists(QC_WEBHOOK_URL):
        print('wake skipped', reason); return False
    url=open(QC_WEBHOOK_URL).read().strip()
    if not url: return False
    auth=open(QC_WEBHOOK_AUTH).read().strip() if os.path.exists(QC_WEBHOOK_AUTH) else ''
    payload=json.dumps(dict({'reason':reason,'source':'sync_dash_taps.py','bot':'comms'},**(extra or {})), ensure_ascii=False)
    cmdl=['curl','--connect-timeout','5','--max-time','30','-sS','-o','/tmp/dash-done-review-webhook.out','-w','%{http_code}','-X','POST',url,'-H','Content-Type: application/json','-d',payload]
    if auth: cmdl[-2:-2]=['-H', auth if auth.lower().startswith('authorization:') else 'Authorization: '+auth]
    try:
        print('wake HTTP', subprocess.check_output(cmdl, text=True, timeout=35).strip()); return True
    except Exception as e:
        print('wake ERR', type(e).__name__); return False

DP_NEW=[]
def enqueue_done_review(s):
    """Rost t6284u/t6285u: ✓ решено на задаче CU → src/done_pending.json (единый источник правды, идемпотентно)
    + cu_actions_pending (cu_review) + PRIORITY-строка в QUEUE.md Секретаря. Вердикт: src/done_pending.py verdict."""
    import done_pending as DP
    i=str(s.get('cu') or '').strip() or cuid(s.get('url')) or ''
    if not i: return False
    st=DP.load()
    if not DP.add(st, i, s.get('title'), s.get('dir'), s.get('bot'), s.get('url'), s.get('at')):
        print('done_review dedup', i); return False
    DP.save(st)
    if not any(a.get('id')==i and a.get('action')=='cu_review' for a in act['pending']):
        act['pending'].append({'id':i,'action':'cu_review','kind':s.get('kind') or 'task','title':s.get('title'),'url':s.get('url'),'bot':s.get('bot'),'dir':s.get('dir'),'tapped_at':s.get('at')})
    slug=f"dash-done-review-{i}"
    line=(f"- [pending] PRIORITY {slug} — Rost нажал ✓ решено на даше: «{(s.get('title') or i)[:90]}» https://app.clickup.com/t/{i} . "
          f"Проверь в ClickUp: закрыта → python3 /workspace/dash-gh/src/done_pending.py verdict {i} closed; сделано, но открыта → закрой (complete) и verdict closed; "
          f"не сделано → verdict {i} returned --note \"что не так\". Потом src/build.sh + push. Без вердикта за 24 ч вернётся на даш «не проверена». Правило: docs/DECISIONS.md t6284u.\n")
    prev=open(QC_MD,encoding='utf-8').read() if os.path.exists(QC_MD) else ''
    if '[pending] PRIORITY '+slug+' ' not in prev:
        with open(QC_MD,'w',encoding='utf-8') as fh: fh.write(line+prev)
    DP_NEW.append(i)
    return True

def enqueue_quick_cmd(s):
    """Пишет cu_actions_pending + queues/dash-quick-cmds.json + PRIORITY в QUEUE.md Секретаря.
    Если строка новая — будит Секретаря существующим COMMS webhook (action-only, без resume 15m LLM).
    Возвращает True если очередь пополнилась."""
    cmd=str(s.get('cmd') or s.get('id') or '').strip()
    if not cmd and str(s.get('key') or '').startswith('quick_cmd|'):
        parts=str(s.get('key')).split('|')
        cmd=parts[1] if len(parts)>1 else ''
    if not cmd: return False
    test=bool(s.get('test') or s.get('dry_run') or str(s.get('flag') or '').upper()=='TEST')
    if test:
        print('quick_cmd TEST dry-run, not queued', cmd)
        return False
    now=_bog_now()
    title=s.get('title') or cmd
    rec={'id':cmd,'action':'quick_cmd','kind':'quick_cmd','title':title,'bot':s.get('bot') or 'Секретарь','dir':s.get('dir') or 'personal','tapped_at':s.get('at') or now.isoformat(timespec='seconds')}
    # structured queue file for morning/QUEUE flow
    os.makedirs(os.path.dirname(QC_JSON), exist_ok=True)
    qj=json.load(open(QC_JSON)) if os.path.exists(QC_JSON) else {'note':'','pending':[],'done':[]}
    qj['note']='Быстрые команды с даша (вкладки Личное и Табакевич). Читает Секретарь / queue-guard / утренний пакет по pending[] и по PRIORITY-строке в /workspace/queue/QUEUE.md.'
    qj.setdefault('pending',[]); qj.setdefault('done',[])
    recent=_qc_recent(qj['pending']+act.get('pending',[]), cmd) or _qc_md_recent(cmd)
    if recent:
        print('quick_cmd dedup', cmd)
        return False
    qj['pending'].insert(0, rec)
    with open(QC_JSON,'w') as fh: json.dump(qj, fh, ensure_ascii=False, indent=2)
    if not any(a.get('action')=='quick_cmd' and a.get('id')==cmd and not a.get('done_at') for a in act['pending']):
        act['pending'].append(rec)
    slug=f"dash-quick-cmd-{cmd}-{now.strftime('%Y%m%d-%H%M')}"
    meta=QC_META.get(cmd) or {'file':'knowledge/rules/dash-quick-commands.md','tag':cmd,'tab':s.get('dir') or 'даш'}
    line=f"- [pending] PRIORITY {slug} — {title} ({meta['tag']}). Сценарий: {meta['file']}. Тап с даша «{meta['tab']}». Исполняет Секретарь.\n"
    prev=open(QC_MD,encoding='utf-8').read() if os.path.exists(QC_MD) else ''
    with open(QC_MD,'w',encoding='utf-8') as fh: fh.write(line+prev)
    print('quick_cmd queued', slug)
    # wake Секретарь immediately via existing action-only webhook
    if not _comms_handler_ok():
        print('quick_cmd webhook skipped: comms-action-handler not verified')
        return True
    if not os.path.exists(QC_WEBHOOK_URL):
        print('quick_cmd webhook skipped: no url file')
        return True
    url=open(QC_WEBHOOK_URL).read().strip()
    if not url:
        print('quick_cmd webhook skipped: empty url')
        return True
    auth=''
    if os.path.exists(QC_WEBHOOK_AUTH):
        auth=open(QC_WEBHOOK_AUTH).read().strip()
    payload=json.dumps({'reason':'dash quick_cmd '+cmd,'source':'sync_dash_taps.py','bot':'comms','cmd':cmd,'slug':slug}, ensure_ascii=False)
    cmdl=['curl','--connect-timeout','5','--max-time','30','-sS','-o','/tmp/dash-quick-cmd-webhook.out','-w','%{http_code}','-X','POST',url,'-H','Content-Type: application/json','-d',payload]
    if auth:
        hdr=auth if auth.lower().startswith('authorization:') else 'Authorization: '+auth
        cmdl[cmdl.index('Content-Type: application/json')+1:cmdl.index('Content-Type: application/json')+1]=['-H',hdr]
    try:
        code=subprocess.check_output(cmdl, text=True, timeout=35).strip()
        print('quick_cmd webhook HTTP', code)
    except Exception as e:
        print('quick_cmd webhook ERR', type(e).__name__)
    return True

if SELF_TEST:
    def _snap(path):
        return open(path,'rb').read() if os.path.exists(path) else None
    paths=[QC_JSON, QC_MD, ACT]
    before={p:_snap(p) for p in paths}
    wh='/tmp/dash-quick-cmd-webhook.out'
    wh_m=os.path.getmtime(wh) if os.path.exists(wh) else None
    results=[]
    for cmd,title,d in (
        ('order_salmon_shrimp','TEST do not order','personal'),
        ('andrey_emergency_logout','TEST do not logout','tabakevich'),
    ):
        queued=enqueue_quick_cmd({'action':'quick_cmd','cmd':cmd,'title':title,'test':True,'flag':'TEST','dir':d,'at':_bog_now().isoformat(timespec='seconds')})
        results.append((cmd,queued))
    after={p:_snap(p) for p in paths}
    changed=[p for p in paths if before[p]!=after[p]]
    wh_new=os.path.exists(wh) and (wh_m is None or os.path.getmtime(wh)!=wh_m)
    if any(q for _,q in results) or changed or wh_new:
        print('SELF-TEST FAIL', 'returned', results, 'changed', changed, 'webhook', wh_new)
        sys.exit(1)
    print('SELF-TEST OK: TEST flag did not queue or webhook', [c for c,_ in results])
    sys.exit(0)

PUSH_FILES=['src/done_pending.json','sync/cu_actions_pending.json','src/cu_dir_overrides.json','src/msg_row_overrides.json','src/msg_sphere_overrides.json','src/ignored_chats.json','sync/bot_attn.jsonl','sync/done',
            'index.html','helper.html','assistant.html','variant-a.html','variant-b.html','variant-c.html','data.enc.json','data-asst.enc.json','data-test-ma.enc.json','test-messengers-assistants.html']
from dash_push import git as _dpgit, push_with_retry as _pwr
def _git(*a, check=False): return _dpgit(*a)
def push_with_retry(msg, tries=3): return _pwr([f for f in PUSH_FILES if f.startswith(('src/','sync/'))], msg, tries)
if PUSH_ONLY:
    dirty=_git('status','--porcelain','--','src/done_pending.json','sync/cu_actions_pending.json').stdout.strip()
    ahead=_git('rev-list','-1','origin/main..HEAD').stdout.strip()
    if not dirty: print('push-only: clean'); sys.exit(0)
    sys.exit(0 if push_with_retry('sync: ✓ решено → на проверке (ретрай пуша, t6285u)') else 1)
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
        if s.get('action')=='cu_review':  # Rost t6080u: «На проверку боту» на любой задаче даша
            i=str(s.get('cu') or '').strip() or cuid(s.get('url') or s.get('key'))
            if i and not any(a.get('id')==i and a.get('action')=='cu_review' and not a.get('done_at') for a in act['pending']+act['done']):
                act['pending'].append({'id':i,'action':'cu_review','kind':s.get('kind') or 'task','title':s.get('title'),'url':s.get('url'),'bot':s.get('bot'),'dir':s.get('dir'),'tapped_at':s.get('at')}); na+=1
            continue
        if s.get('action')=='call_done':  # Rost t5810u: «✅ Созвонились» на красной плашке созвона → COMMS: коммент «Созвонились» в CU (close только если on_done=close)
            i=str(s.get('cu') or '').strip() or cuid(s.get('url'))
            if i and not any(a.get('id')==i and a.get('action')=='call_done' and a.get('due')==s.get('due') for a in act['pending']+act['done']):
                act['pending'].append({'id':i,'action':'call_done','kind':'call','title':s.get('title'),'url':s.get('url'),'due':s.get('due'),'dir':s.get('dir'),'on_done':s.get('on_done') or 'comment','tapped_at':s.get('at')}); na+=1
            continue
        if s.get('action')=='quick_cmd':  # Rost t6245u / t6254u: быстрая команда с вкладок Личное / Табакевич
            if enqueue_quick_cmd(s): na+=1
            continue
        if s.get('action')=='cu_done' or (s.get('action')=='cu_close' and str(s.get('key') or '').startswith('cuclose|')):  # Rost t6284u: ✓ решено → на проверку (старые вкладки шлют cu_close/cuclose|)
            if enqueue_done_review(s): na+=1
            continue
        if s.get('action')=='cu_close':
            i=str(s.get('cu') or '').strip() or cuid(s.get('url')) or (s.get('key') or '').split('|')[-1]
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
if DP_NEW: _wake_comms('dash done_review '+','.join(DP_NEW), {'ids':DP_NEW})
ok=push_with_retry(f'sync: тапы даша → contacts ({ns} сфер, {ni} игнор, {nc} CU-направл., {na} CU-действ., {nr} строк ✓/✕/CU/теги, {nb} нужен/отчёт)')
sys.exit(0 if ok else 1)
