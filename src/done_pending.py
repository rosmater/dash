#!/usr/bin/env python3
"""Rost t6284u / t6285u: «✓ решено» на любой задаче ClickUp в даше → задача сразу скрыта и уходит на проверку боту.
Единый источник правды: src/done_pending.json (пишут только этот скрипт и sync_dash_taps.py через add()).
Состояния пункта: pending (на проверке) → closed (бот подтвердил: задача закрыта в ClickUp) | returned (после проверки не закрыта).
TTL: pending без вердикта дольше ttl_hours (24 ч) → сам возвращается на даш с пометкой «не проверена» (считается и при сборке, и в браузере).
Сборка (build_data.py) вызывает reconcile(data): сверяет со снимком ClickUp в данных (закрыта → не прячем, открыта+returned/TTL → показываем).

CLI (для бота-проверяющего; после — обычные src/build.sh + push):
  python3 src/done_pending.py list
  python3 src/done_pending.py verdict <taskId> closed   [--note "…"]   # проверил: закрыта в CU (или закрыл сам)
  python3 src/done_pending.py verdict <taskId> returned --note "что не так"   # не закрыта → вернуть на даш «вернулась»
  python3 src/done_pending.py audit
  python3 src/done_pending.py selftest      # TTL/returned без записи в файл
"""
import json, os, sys, datetime, re
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'done_pending.json')
TTL_H = 24
RET_SHOW_H = 48          # «вернулась» / «не проверена» висит пометкой 48 ч, дальше строка просто обычная
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
    s.setdefault('_note', 'Rost t6284u/t6285u: ✓ решено на даше → на проверке. Пишет только src/done_pending.py / sync_dash_taps.py. Руками не править.')
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
        if e.get('state') in ('closed', 'returned') and old:
            s['history'].append(dict(e, id=i))
        else:
            keep[i] = e
    s['items'] = keep
    s['history'] = s['history'][-100:]
    return s

def add(s, cid, title='', dir='', bot='', url='', at=None, src='dash'):
    """Идемпотентно: повторный тап того же клика не плодит записи; новый ✓ после returned/closed — новый цикл проверки."""
    cid = str(cid or '').strip()
    if not re.match(r'^[0-9a-z]{6,}$', cid, re.I): return False
    at_d = ts(at) or now()
    e = s['items'].get(cid)
    if e and e.get('state') == 'pending':
        return False  # уже на проверке
    if e and (ts(e.get('verdict_at')) or ts(e.get('clicked_at')) or at_d) >= at_d:
        return False  # старый тап (ретрай relay) после вердикта — не перезапускать
    if e: s['history'].append(dict(e, id=cid))
    s['items'][cid] = dict(state='pending', title=(title or '')[:160], dir=dir or '', bot=bot or '', url=url or f'https://app.clickup.com/t/{cid}',
                          clicked_at=iso(at_d), received_at=iso(now()), src=src, cycles=(e or {}).get('cycles', 0) + 1)
    prune(s)
    return True

def verdict(s, cid, v, note=''):
    e = s['items'].get(cid)
    if not e: raise SystemExit(f'нет пункта {cid} в {STATE}')
    if v not in ('closed', 'returned'): raise SystemExit('verdict: closed | returned')
    e.update(state=v, verdict_at=iso(now()), note=note or e.get('note', ''))
    return e

def effective(e, t=None, ttl_h=TTL_H):
    """→ 'hide' | 'returned' | 'ttl' | 'closed' | 'old'"""
    t = t or now()
    st = e.get('state')
    c = ts(e.get('clicked_at')) or t
    if st == 'closed': return 'closed'
    if st == 'returned':
        v = ts(e.get('verdict_at')) or c
        return 'returned' if (t - v).total_seconds() < RET_SHOW_H * 3600 else 'old'
    if (t - c).total_seconds() < ttl_h * 3600: return 'hide'
    return 'ttl' if (t - c).total_seconds() < (ttl_h + RET_SHOW_H) * 3600 else 'old'

CLOSED_RE = re.compile(r'^(complete|done|closed|закрыт)', re.I)
def snapshot_status(data):
    """id задачи CU → статус из снимка сборки (все блоки всех ботов)."""
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
            for x in ids:
                if stt and (x not in out or CLOSED_RE.match(stt)): out[x] = stt
                else: out.setdefault(x, '')
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(data)
    return out

def reconcile(data, s=None, t=None):
    s = s if s is not None else load()
    t = t or now()
    ttl = float(s.get('ttl_hours') or TTL_H)
    snap = snapshot_status(data)
    items, aud = {}, dict(pending=0, returned=0, ttl=0, closed=0, closed_in_cu=0)
    for i, e in s['items'].items():
        eff = effective(e, t, ttl)
        stt = snap.get(i)
        if eff == 'hide' and stt and CLOSED_RE.match(stt): aud['closed_in_cu'] += 1
        if eff == 'hide': aud['pending'] += 1
        elif eff == 'returned': aud['returned'] += 1
        elif eff == 'ttl': aud['ttl'] += 1
        elif eff == 'closed': aud['closed'] += 1
        items[i] = dict(st=e.get('state'), eff=eff, t=e.get('clicked_at'), v=e.get('verdict_at') or '', note=(e.get('note') or '')[:140],
                        title=e.get('title', ''), dir=e.get('dir', ''), in_snap=i in snap, cu_status=stt or '')
    return dict(ttl_hours=ttl, ret_show_hours=RET_SHOW_H, built_at=iso(t), items=items, audit=aud)

def selftest():
    t0 = datetime.datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
    s = load('/nonexistent'); s['items'] = {}
    assert add(s, '86test001', 'тест', 'personal', at=iso(t0))
    assert not add(s, '86test001', 'тест', 'personal', at=iso(t0))           # идемпотентно
    data = {'directions': [{'tasks': [{'id': '86test001', 'name': 'тест', 'status': 'to do'}]}]}
    r = reconcile(data, s, t0 + datetime.timedelta(hours=1))
    assert r['items']['86test001']['eff'] == 'hide', r
    r = reconcile(data, s, t0 + datetime.timedelta(hours=TTL_H + 0.1))
    assert r['items']['86test001']['eff'] == 'ttl', r                         # TTL → вернулась «не проверена»
    assert r['audit']['ttl'] == 1
    s['items']['86test001'].update(state='returned', verdict_at=iso(t0 + datetime.timedelta(hours=2)))
    r = reconcile(data, s, t0 + datetime.timedelta(hours=3))
    assert r['items']['86test001']['eff'] == 'returned'
    assert not add(s, '86test001', at=iso(t0 + datetime.timedelta(minutes=5)))  # старый ретрай после вердикта
    assert add(s, '86test001', at=iso(t0 + datetime.timedelta(hours=4)))        # новый ✓ — новый цикл
    assert s['items']['86test001']['cycles'] == 2
    print('done_pending selftest OK')

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] in ('-h', '--help'): print(__doc__); sys.exit(0)
    if a[0] == 'selftest': selftest(); sys.exit(0)
    s = load()
    if a[0] == 'list':
        for i, e in s['items'].items(): print(i, effective(e), e.get('state'), e.get('clicked_at'), e.get('title'))
    elif a[0] == 'audit':
        print(json.dumps(reconcile({}, s)['audit'], ensure_ascii=False))
    elif a[0] == 'verdict' and len(a) >= 3:
        note = a[a.index('--note') + 1] if '--note' in a else ''
        print(verdict(s, a[1], a[2], note)); save(s)
    else:
        print(__doc__); sys.exit(2)
