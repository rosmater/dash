#!/usr/bin/env python3
"""Rost t6300u (overrides t6284u review): «✓ решено» на любой задаче ClickUp в даше
→ задача сразу скрыта и СРАЗУ закрывается в ClickUp (без ревью бота).

Единый источник правды: src/done_pending.json (пишут этот скрипт и sync_dash_taps.py через add()).
Состояния: pending (ждём подтверждения закрытия в CU) → closed (CU подтвердил close)
  | failed (закрыть не удалось → снова видна с «⚠ не закрылась»)
  | rolled (повторяющаяся: закрытие ушло в следующую итерацию, строка снова видна).
TTL: pending без подтверждения дольше ttl_hours (24 ч) → сама возвращается на даш
  с пометкой «⏳ не закрылась» (считается и при сборке, и в браузере).
t6302u: stop_recur=True — сначала снять повторение (Frecuencia → única), потом закрыть,
  без следующей итерации.

Сборка (build_data.py) вызывает reconcile(data): сверяет со снимком ClickUp
(закрыта → прячем/closed; открыта с новым due → rolled; открыта то же due + failed/TTL → показываем).

CLI:
  python3 src/done_pending.py list
  python3 src/done_pending.py verdict <taskId> closed   [--note "…"]
  python3 src/done_pending.py verdict <taskId> failed   [--note "что не так"]
  python3 src/done_pending.py verdict <taskId> rolled   [--note "…"]
  python3 src/done_pending.py audit
  python3 src/done_pending.py selftest
"""
import json, os, sys, datetime, re
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'done_pending.json')
TTL_H = 24
RET_SHOW_H = 48
CLOSED_KEEP_D = 7
UTC = datetime.timezone.utc

def now():
    return datetime.datetime.now(UTC)

def ts(s):
    if not s: return None
    try:
        d = datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except Exception:
        return None

def iso(d):
    return d.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')

def load(path=STATE):
    try:
        s = json.load(open(path))
    except Exception:
        s = {}
    s.setdefault('_note', 'Rost t6300u: ✓ решено на даше → сразу закрыть в ClickUp. Пишет только src/done_pending.py / sync_dash_taps.py. Руками не править.')
    s.setdefault('ttl_hours', TTL_H)
    s.setdefault('items', {})
    s.setdefault('history', [])
    return s

def save(s, path=STATE):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(s, f, ensure_ascii=False, indent=1); f.write('\n')
    os.replace(tmp, path)

def prune(s, t=None):
    t = t or now()
    keep = {}
    for i, e in s['items'].items():
        v = ts(e.get('verdict_at')) or ts(e.get('clicked_at'))
        old = v and (t - v).total_seconds() > CLOSED_KEEP_D * 86400
        if e.get('state') in ('closed', 'failed', 'returned', 'rolled') and old:
            s['history'].append(dict(e, id=i))
        else:
            keep[i] = e
    s['items'] = keep
    s['history'] = s['history'][-100:]
    return s

def add(s, cid, title='', dir='', bot='', url='', at=None, src='dash', due='', stop_recur=False):
    """Идемпотентно: повторный тап того же клика не плодит записи; новый ✓ после failed/closed/rolled — новый цикл."""
    cid = str(cid or '').strip()
    if not re.match(r'^[0-9a-z]{6,}$', cid, re.I): return False
    at_d = ts(at) or now()
    e = s['items'].get(cid)
    if e and e.get('state') == 'pending':
        # allow upgrading a pending close to stop_recur if a later tap asks for it
        if stop_recur and not e.get('stop_recur'):
            e['stop_recur'] = True
            e['action'] = 'cu_done_stop'
        return False
    if e and (ts(e.get('verdict_at')) or ts(e.get('clicked_at')) or at_d) >= at_d:
        return False
    if e: s['history'].append(dict(e, id=cid))
    s['items'][cid] = dict(
        state='pending', title=(title or '')[:160], dir=dir or '', bot=bot or '',
        url=url or f'https://app.clickup.com/t/{cid}',
        clicked_at=iso(at_d), received_at=iso(now()), src=src,
        cycles=(e or {}).get('cycles', 0) + 1,
        due=str(due or (e or {}).get('due') or '')[:10],
        stop_recur=bool(stop_recur),
        action='cu_done_stop' if stop_recur else 'cu_done',
    )
    prune(s)
    return True

def verdict(s, cid, v, note=''):
    e = s['items'].get(cid)
    if not e: raise SystemExit(f'нет пункта {cid} в {STATE}')
    if v == 'returned': v = 'failed'  # t6284u alias
    if v not in ('closed', 'failed', 'rolled'): raise SystemExit('verdict: closed | failed | rolled')
    e.update(state=v, verdict_at=iso(now()), note=note or e.get('note', ''))
    return e

def effective(e, t=None, ttl_h=TTL_H):
    """→ 'hide' | 'failed' | 'ttl' | 'closed' | 'rolled' | 'old'"""
    t = t or now()
    st = e.get('state')
    c = ts(e.get('clicked_at')) or t
    if st == 'closed': return 'closed'
    if st == 'rolled':
        v = ts(e.get('verdict_at')) or c
        return 'rolled' if (t - v).total_seconds() < RET_SHOW_H * 3600 else 'old'
    if st in ('failed', 'returned'):
        v = ts(e.get('verdict_at')) or c
        return 'failed' if (t - v).total_seconds() < RET_SHOW_H * 3600 else 'old'
    if (t - c).total_seconds() < ttl_h * 3600: return 'hide'
    return 'ttl' if (t - c).total_seconds() < (ttl_h + RET_SHOW_H) * 3600 else 'old'

CLOSED_RE = re.compile(r'^(complete|done|closed|закрыт)', re.I)

def snapshot_index(data):
    """id задачи CU → {status, due} из снимка сборки (все блоки всех ботов)."""
    out = {}
    def walk(o):
        if isinstance(o, dict):
            i = o.get('id') or o.get('cu')
            if isinstance(i, dict): i = i.get('id')
            u = str(o.get('url') or '')
            m = re.search(r'/t/(?:\d+/)?([0-9a-z]+)', u)
            ids = {str(i)} if isinstance(i, str) and re.match(r'^[0-9a-z]{6,}$', i) else set()
            if m: ids.add(m.group(1))
            stt = str(o.get('cu_status') or o.get('status') or '')
            due = str(o.get('due') or o.get('due_date') or o.get('start') or '')[:10]
            if due and not re.match(r'\d{4}-\d{2}-\d{2}', due): due = ''
            for x in ids:
                cur = out.get(x) or {'status': '', 'due': ''}
                if stt and (not cur['status'] or CLOSED_RE.match(stt)):
                    cur['status'] = stt
                if due and not cur['due']:
                    cur['due'] = due
                out[x] = cur
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(data)
    return out

def snapshot_status(data):
    return {i: v.get('status') or '' for i, v in snapshot_index(data).items()}

def reconcile(data, s=None, t=None, persist=True):
    s = s if s is not None else load()
    t = t or now()
    ttl = float(s.get('ttl_hours') or TTL_H)
    snap = snapshot_index(data)
    changed = False
    items, aud = {}, dict(pending=0, failed=0, returned=0, ttl=0, closed=0, closed_in_cu=0, rolled=0)
    for i, e in list(s['items'].items()):
        stt = (snap.get(i) or {}).get('status') or ''
        sdue = (snap.get(i) or {}).get('due') or ''
        # Auto-confirm from the live snapshot so a close cannot stay hidden forever.
        if e.get('state') == 'pending':
            if stt and CLOSED_RE.match(stt):
                e.update(state='closed', verdict_at=iso(t), note=e.get('note') or 'auto: snapshot closed')
                changed = True
            elif sdue and e.get('due') and sdue != e.get('due') and not e.get('stop_recur'):
                e.update(state='rolled', verdict_at=iso(t), note=e.get('note') or f'auto: rolled {e.get("due")}→{sdue}')
                changed = True
            elif sdue and e.get('due') and sdue != e.get('due') and e.get('stop_recur'):
                # stop-recur asked for no next occurrence; a new due means ClickUp still rolled
                e.update(state='failed', verdict_at=iso(t), note=e.get('note') or f'rolled despite stop {e.get("due")}→{sdue}')
                changed = True
        eff = effective(e, t, ttl)
        if eff == 'hide' and stt and CLOSED_RE.match(stt): aud['closed_in_cu'] += 1
        if eff == 'hide': aud['pending'] += 1
        elif eff == 'failed': aud['failed'] += 1; aud['returned'] += 1  # alias for old audit readers
        elif eff == 'ttl': aud['ttl'] += 1
        elif eff == 'closed': aud['closed'] += 1
        elif eff == 'rolled': aud['rolled'] += 1
        items[i] = dict(st=e.get('state'), eff=eff, t=e.get('clicked_at'), v=e.get('verdict_at') or '',
                        note=(e.get('note') or '')[:140], title=e.get('title', ''), dir=e.get('dir', ''),
                        in_snap=i in snap, cu_status=stt, due=e.get('due') or '', snap_due=sdue,
                        stop_recur=bool(e.get('stop_recur')))
    if persist and changed:
        try:
            save(s)
        except Exception:
            pass
    return dict(ttl_hours=ttl, ret_show_hours=RET_SHOW_H, built_at=iso(t), items=items, audit=aud)

def selftest():
    t0 = datetime.datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
    s = load('/nonexistent'); s['items'] = {}
    assert add(s, '86test001', 'тест', 'personal', at=iso(t0), due='2026-11-13')
    assert not add(s, '86test001', 'тест', 'personal', at=iso(t0))
    data = {'directions': [{'tasks': [{'id': '86test001', 'name': 'тест', 'status': 'to do', 'due': '2026-11-13'}]}]}
    r = reconcile(data, s, t0 + datetime.timedelta(hours=1), persist=False)
    assert r['items']['86test001']['eff'] == 'hide', r
    # snapshot closed while pending → auto closed
    data2 = {'directions': [{'tasks': [{'id': '86test001', 'name': 'тест', 'status': 'complete', 'due': '2026-11-13'}]}]}
    s2 = load('/nonexistent'); s2['items'] = json.loads(json.dumps(s['items']))
    r = reconcile(data2, s2, t0 + datetime.timedelta(hours=1), persist=False)
    assert s2['items']['86test001']['state'] == 'closed', s2
    assert r['items']['86test001']['eff'] == 'closed', r
    # TTL → «не закрылась»
    r = reconcile(data, s, t0 + datetime.timedelta(hours=TTL_H + 0.1), persist=False)
    assert r['items']['86test001']['eff'] == 'ttl', r
    assert r['audit']['ttl'] == 1
    s['items']['86test001'].update(state='failed', verdict_at=iso(t0 + datetime.timedelta(hours=2)))
    r = reconcile(data, s, t0 + datetime.timedelta(hours=3), persist=False)
    assert r['items']['86test001']['eff'] == 'failed'
    # alias returned
    s['items']['86test001'].update(state='returned', verdict_at=iso(t0 + datetime.timedelta(hours=2)))
    r = reconcile(data, s, t0 + datetime.timedelta(hours=3), persist=False)
    assert r['items']['86test001']['eff'] == 'failed'
    assert not add(s, '86test001', at=iso(t0 + datetime.timedelta(minutes=5)))
    assert add(s, '86test001', at=iso(t0 + datetime.timedelta(hours=4)), due='2026-11-13')
    assert s['items']['86test001']['cycles'] == 2
    # rolled: same id, new due, not stop
    s3 = load('/nonexistent'); s3['items'] = {}
    assert add(s3, '86test002', 'полив', at=iso(t0), due='2026-11-13')
    data3 = {'directions': [{'tasks': [{'id': '86test002', 'name': 'полив', 'status': 'to do', 'due': '2026-11-14'}]}]}
    r = reconcile(data3, s3, t0 + datetime.timedelta(hours=1), persist=False)
    assert s3['items']['86test002']['state'] == 'rolled', s3
    assert r['items']['86test002']['eff'] == 'rolled', r
    # stop_recur + new due → failed (should not have rolled)
    s4 = load('/nonexistent'); s4['items'] = {}
    assert add(s4, '86test003', 'полив', at=iso(t0), due='2026-11-13', stop_recur=True)
    r = reconcile(data3, s4, t0 + datetime.timedelta(hours=1), persist=False)
    # data3 has 86test002 not 003 — craft proper data
    data4 = {'directions': [{'tasks': [{'id': '86test003', 'name': 'полив', 'status': 'to do', 'due': '2026-11-14'}]}]}
    r = reconcile(data4, s4, t0 + datetime.timedelta(hours=1), persist=False)
    assert s4['items']['86test003']['state'] == 'failed', s4
    assert r['items']['86test003']['eff'] == 'failed'
    print('done_pending selftest OK')

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] in ('-h', '--help'): print(__doc__); sys.exit(0)
    if a[0] == 'selftest': selftest(); sys.exit(0)
    s = load()
    if a[0] == 'list':
        for i, e in s['items'].items(): print(i, effective(e), e.get('state'), e.get('clicked_at'), e.get('title'))
    elif a[0] == 'audit':
        print(json.dumps(reconcile({}, s, persist=False)['audit'], ensure_ascii=False))
    elif a[0] == 'verdict' and len(a) >= 3:
        note = a[a.index('--note') + 1] if '--note' in a else ''
        print(verdict(s, a[1], a[2], note)); save(s)
    else:
        print(__doc__); sys.exit(2)
