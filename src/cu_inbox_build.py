"""Rost t4153–55: ClickUp «инбокс» для Мессенджеров -> src/ma_cu_inbox.json.
Вход (кладёт агент после MCP-опроса, tier 2 по cu-inbox-tier.sh): notify-watchers/clickup-pulse/inbox-raw/{tasks,comments}-<date>.json
Категории: comment (Комменты) / mention (@) / assigned (Назначили) / forcheck (for check) / other (Прочее).
У КАЖДОЙ строки две ссылки (t4154u HARD): comment_url (app.clickup.com/t/<id>?comment=<cid>) + task_url (rosmater.github.io/cu/?t=<id>).
Только метаданные: текст коммента в даш НЕ пишем (только флаги @/assigned)."""
import json, glob, os, sys, datetime as dt
R = '/workspace/notify-watchers/clickup-pulse/inbox-raw/'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ma_cu_inbox.json')
# HARD Rost t5351u: не затирать desktop-sourced диалоги MCP-опросом за 48ч.
try:
    _prev = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
    _ps = ((_prev.get('src') or '') + ' ' + str(_prev.get('tier') or '')).lower()
    if 'desktop' in _ps:
        OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ma_cu_inbox_mcp.json')
        print('cu_inbox_build: desktop-sourced ma_cu_inbox.json preserved; MCP harvest →', OUT)
except Exception as _e:
    print('cu_inbox_build: desktop-guard skip', _e)
ROST = 60710247
TZ = dt.timezone(dt.timedelta(hours=-5))
day = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob(R + 'tasks-*.json'))[-1][-15:-5]
TK = json.load(open(R + f'tasks-{day}.json')); CM = json.load(open(R + f'comments-{day}.json'))
# Rost t4264: inbox-raw был только «задачи на Rost» -> люди (MH/SC/Karli), тегающие @Rost в СВОИХ задачах, и треды-ответы не попадали.
# wide/: tasks-updated.json (filter_tasks order_by=updated, весь workspace), comments-wide.json (комменты не-Rost задач), replies.json (ответы в тредах), dms.json (личка ClickUp Chat, метаданные)
W = R + 'wide/'
ORIG = None
if os.path.exists(W + 'tasks-updated.json'):
    TW = json.load(open(W + 'tasks-updated.json')); _ids = {t['id'] for t in TK['tasks']}; ORIG = set(_ids)
    TK['tasks'] += [t for t in TW['tasks'] if t['id'] not in _ids]
    if TW.get('fetched', '') > TK['fetched']: TK['fetched'] = TW['fetched']
if os.path.exists(W + 'comments-wide.json'):
    for tid, cs in json.load(open(W + 'comments-wide.json')).items():
        have = {c['id'] for c in CM.get(tid, [])}; CM.setdefault(tid, []).extend(c for c in cs if c['id'] not in have)
if os.path.exists(W + 'replies.json'):
    for tid, rs in json.load(open(W + 'replies.json')).items():
        for r in rs: CM.setdefault(tid, []).append(dict(r, id=r['parent_id'], reply_id=r['id']))  # ссылка = родительский коммент (тред)
DMS = json.load(open(W + 'dms.json')) if os.path.exists(W + 'dms.json') else None
fetched = dt.datetime.fromisoformat(TK['fetched']); since = fetched - dt.timedelta(hours=int(os.environ.get('CU_INBOX_HOURS', 48)))
ts = lambda ms: dt.datetime.fromtimestamp(int(ms) / 1000, TZ)
fmt = lambda d: d.strftime('%Y-%m-%d %H:%M')
turl = lambda t: f'https://rosmater.github.io/cu/?t={t}'
curl = lambda t, c: f'https://app.clickup.com/t/{t}?comment={c}'
items, seen = [], set()
T = {t['id']: t for t in TK['tasks']}
def base(t):
    return dict(task_id=t['id'], task=t['name'], list=(t.get('list') or {}).get('name', ''), list_id=str((t.get('list') or {}).get('id', '')), status=t.get('status', ''), task_url=turl(t['id']), task_app=f"https://app.clickup.com/t/{t['id']}")
# t5002: «непрочитано» = комменты НЕ от аккаунта Rost после его последнего ответа (свои/бот от Rost не считаются)
def _uid(c):
    return (c.get('user') or {}).get('id')
def others_after_rost(cs):
    rost_ms = next((int(c['date']) for c in cs if _uid(c) == ROST), None)
    out = []
    for c in cs:
        if ts(c['date']) < since: continue
        if _uid(c) == ROST: continue
        if rost_ms is not None and int(c['date']) <= rost_ms: continue
        out.append(c)
    return out
for tid, cs in CM.items():
    t = T.get(tid) or dict(id=tid, name=tid)
    cs = sorted(cs, key=lambda c: int(c['date']), reverse=True)
    last = cs[0] if cs else None
    recent = [c for c in cs if ts(c['date']) >= since]
    unread = others_after_rost(cs)
    for c in unread:
        txt = (c.get('comment_text') or '').lower()
        if c.get('assignee') and (c['assignee'] or {}).get('id') == ROST:
            items.append(dict(base(t), kind='assigned', sub='коммент назначен на тебя', at=fmt(ts(c['date'])), who=(c.get('assigned_by') or c['user']).get('username'), comment_id=c['id'], comment_url=curl(tid, c['id']), resolved=bool(c.get('resolved'))))
        elif '@rost' in txt and _uid(c) != ROST:
            items.append(dict(base(t), kind='mention', at=fmt(ts(c['date'])), who=c['user']['username'], comment_id=c['id'], comment_url=curl(tid, c['id'])))
    if t.get('status') == 'for check':
        # for check всегда на даше; n_new = чужие после ответа Rost
        _who = (unread[0]['user']['username'] if unread else (last['user']['username'] if last else ''))
        _cid = unread[0]['id'] if unread else (last and last['id'])
        items.append(dict(base(t), kind='forcheck', at=fmt(ts(unread[0]['date'])) if unread else (fmt(ts(last['date'])) if last else fmt(ts(t.get('date_updated', 0)))), who=_who, comment_id=_cid, comment_url=curl(tid, _cid) if _cid else None, n_new=len(unread)))
    elif unread:
        c = unread[0]
        items.append(dict(base(t), kind='comment', at=fmt(ts(c['date'])), who=c['user']['username'], comment_id=c['id'], comment_url=curl(tid, c['id']), n_new=len(unread)))
    seen.add(tid)
# Назначили: новые задачи на Rost (created в окне)
for tid, ms in (TK.get('created_at') or {}).items():
    if ts(ms) >= since and tid in T:
        lc = sorted(CM.get(tid) or [], key=lambda c: int(c['date']), reverse=True)
        items.append(dict(base(T[tid]), kind='assigned', sub='новая задача на тебе', at=fmt(ts(ms)), who='', comment_id=lc[0]['id'] if lc else None, comment_url=curl(tid, lc[0]['id']) if lc else None))
        seen.add(tid)
# Прочее: обновлены в окне, без комментов в окне (статус/поля/вложения)
for t in TK['tasks']:
    if ORIG is not None and t['id'] not in ORIG: continue  # чужие задачи без коммента — не шум
    if t['id'] in seen or not t.get('date_updated') or ts(t['date_updated']) < since: continue
    lc = sorted(CM.get(t['id']) or [], key=lambda c: int(c['date']), reverse=True)
    items.append(dict(base(t), kind='other', sub='изменена (без нового коммента)', at=fmt(ts(t['date_updated'])), who='', comment_id=lc[0]['id'] if lc else None, comment_url=curl(t['id'], lc[0]['id']) if lc else None))
items.sort(key=lambda x: x['at'], reverse=True)
# Rost t4165–67: комментарий CU = «сообщение». Строка-чат на задачу (как TG/WA): n_new = новых комментов в окне, last = последний коммент/событие.
NEW = {tid: others_after_rost(sorted(cs, key=lambda c: int(c['date']), reverse=True)) for tid, cs in CM.items()}
by = {}
for x in items:
    g = by.setdefault(x['task_id'], dict({k: x[k] for k in ('task_id', 'task', 'list', 'status', 'task_url', 'task_app') if k in x}, list_id=x.get('list_id', ''), kinds=[], at='', who='', comment_url=None, sub=''))
    if x['kind'] not in g['kinds']: g['kinds'].append(x['kind'])
    if x.get('sub') and not g['sub']: g['sub'] = x['sub']
    if x['at'] > g['at']: g['at'] = x['at']; g['who'] = x.get('who') or g['who']; g['comment_url'] = x.get('comment_url') or g['comment_url']
    elif not g['comment_url']: g['comment_url'] = x.get('comment_url')
for g in list(by.values()):
    rc = sorted(NEW.get(g['task_id']) or [], key=lambda c: int(c['date']), reverse=True)
    g['n_new'] = len(rc)
    if rc: g['who'] = rc[0]['user']['username']; g['comment_url'] = curl(g['task_id'], rc[0]['id']); g['at'] = max(g['at'], fmt(ts(rc[0]['date'])))
    g['mention_at'] = max([fmt(ts(c['date'])) for c in rc if '@rost' in (c.get('comment_text') or '').lower() and _uid(c) != ROST] or [''])
    # Rost t4212: автор строки = кто написал/тегнул. Живой человек (не аккаунт Rost) — по имени; аккаунт Rost = пишут боты → «БОТ».
    _all = sorted(CM.get(g['task_id']) or [], key=lambda c: int(c['date']), reverse=True)
    _hum = rc  # уже только чужие после Rost
    _ref = rc[0] if rc else (_all[0] if _all else None)
    if _hum: g['author'], g['author_bot'] = _hum[0]['user'].get('username') or '', False
    elif _ref and (_ref.get('user') or {}).get('id') == ROST: g['author'], g['author_bot'] = 'БОТ', True
    elif _ref: g['author'], g['author_bot'] = (_ref.get('user') or {}).get('username') or '', False
# t5002: дроп строк без чужого нового и без for check / assigned
for _tid in list(by.keys()):
    g = by[_tid]
    _keep = set(g.get('kinds') or []) & {'forcheck', 'assigned', 'dm'}
    if g.get('n_new', 0) > 0 or _keep: continue
    if g.get('mention_at'): continue
    del by[_tid]
items = [x for x in items if x['task_id'] in by or x.get('kind') in ('forcheck', 'assigned', 'dm')]
# Rost t4264: личка ClickUp Chat (DM) -> строка-чат как TG/WA. Текст не пишем, только кто/когда/сколько новых после последнего ответа Rost.
if DMS:
    for dm in DMS['dms']:
        ms = sorted(dm['messages'], key=lambda m: int(m['date']), reverse=True)
        new = []
        for m in ms:
            if str(m['user_id']) == str(ROST): break
            new.append(m)
        new = [m for m in new if ts(m['date']) >= since]
        if not new: continue
        u = f"https://app.clickup.com/9014731752/chat/r/{dm['channel_id']}"
        g = dict(task_id='DM:' + dm['channel_id'], task='Личка: ' + dm['peer'], list='ClickUp DM · ' + dm.get('sphere_hint', ''), status='', task_url=u, task_app=u,
                 kinds=['dm'], at=fmt(ts(new[0]['date'])), who=dm['peer'], comment_url=u, sub='личное сообщение в ClickUp Chat', n_new=len(new), mention_at='', author=dm['peer'], author_bot=False)
        by[g['task_id']] = g
        items.append(dict(task_id=g['task_id'], task=g['task'], list=g['list'], status='', task_url=u, task_app=u, kind='dm', at=g['at'], who=dm['peer'], comment_id=new[0]['id'], comment_url=u))
threads = sorted(by.values(), key=lambda g: g['at'], reverse=True)
# Rost t4167u: монитор/вкладка ботов и инбокс — ОДИН снимок: ma_clickup.json (for check) пишем из того же inbox-raw
json.dump(dict(fetched=fmt(fetched) + ' Bogotá', src='inbox-raw ' + day + ' (cu_inbox_build.py, t4167)',
               tasks=[dict(id=t['id'], name=t['name'], list=(t.get('list') or {}).get('name', ''), updated=fmt(ts(t['date_updated'])) if t.get('date_updated') else '', status=t.get('status', ''))
                      for t in sorted(TK['tasks'], key=lambda t: int(t.get('date_updated') or 0), reverse=True) if t.get('status') == 'for check' and (ORIG is None or t['id'] in ORIG)]),
          open(os.path.join(os.path.dirname(OUT), 'ma_clickup.json'), 'w'), ensure_ascii=False, indent=1)
cnt = {}
for x in items: cnt[x['kind']] = cnt.get(x['kind'], 0) + 1
json.dump(dict(_note=__doc__.strip(), fetched=fmt(fetched) + ' Bogotá', since=fmt(since) + ' Bogotá', src=TK.get('src', 'MCP'), tier=os.environ.get('CU_TIER', '2'),
               kinds=[['comment', 'Комменты'], ['mention', '@'], ['dm', 'Личка'], ['assigned', 'Назначили'], ['forcheck', 'for check'], ['other', 'Прочее']], counts=cnt, items=items, threads=threads),
          open(OUT, 'w'), ensure_ascii=False, indent=1)
print('cu_inbox', cnt, 'threads', len(threads), 'with_new', sum(1 for g in threads if g['n_new']), 'no-comment-link', sum(1 for x in items if not x.get('comment_url')))
