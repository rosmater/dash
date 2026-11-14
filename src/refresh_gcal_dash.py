#!/usr/bin/env python3
"""Rost т251 / CU 86bctqe8h: обновить снимок Google Calendar для даша (/workspace/gcal_dash.json).

MCP из build.sh не вызывается, поэтому агент делает так:
  1) Google Calendar коннектор `user-Google-calendar` → list_events
       calendarId=primary, timeZone=America/Bogota, maxResults=250,
       startTime=<1-е текущего месяца Боготы>T00:00:00-05:00,
       endTime=<max(конец месяца, сегодня+15д)>T00:00:00-05:00
       (t6314u: окно с 1-го числа, чтобы сводка «Месяц» на вкладке Календарь была полной;
        15 дней от сегодня — чтобы день +14 был целиком, как раньше)
     (write_to_file=true → файл agent-tools/*.txt; если есть nextPageToken — дочитать и передать все файлы)
  2) python3 src/refresh_gcal_dash.py <файл1> [файл2 ...] [--start YYYY-MM-DD] [--days N]
  3) скопировать в /workspace/dash-gh/gcal_dash.json, если писали в /workspace/gcal_dash.json
  4) dash_touch_append.py → src/build.sh → пуш (как обычно)

Вход: ответ list_events ({calendar,timeZone,events:[...]}) ИЛИ голый список events (формат Calendar API events.list —
тот же, что отдаёт live OAuth в браузере). Выход — прежняя форма gcal_dash.json:
  {fetched_at, calendar, range:{start,end,tz}, events:[{id,title,start,end,all_day,url,location}]}

Слияние: вход заменяет события, чей день начала (Богота) попадает в окно [--start, --start+--days];
события старого снимка вне этого окна сохраняются. Так утренняя выборка «сегодня+14»
не затирает уже накопленные дни месяца (нужны для сводки).

Флаги: --out PATH (по умолч. /workspace/gcal_dash.json), --days N (14),
       --start YYYY-MM-DD (по умолч. сегодня; для полной сводки месяца — 1-е число),
       --dry (печать сводки без записи).
"""
import json, sys, os, datetime, argparse, re

BOG = datetime.timezone(datetime.timedelta(hours=-5))
ap = argparse.ArgumentParser()
ap.add_argument('files', nargs='*')
ap.add_argument('--out', default='/workspace/gcal_dash.json')
ap.add_argument('--days', type=int, default=14)
ap.add_argument('--start', default=None, help='YYYY-MM-DD, inclusive (default: today). For month summary: 1st of current Bogotá month.')
ap.add_argument('--dry', action='store_true')
a = ap.parse_args()

def load(txt):
    txt = txt.strip()
    txt = re.sub(r'</?cursor_untrusted_data[^>]*>', '', txt)
    # коннектор иногда пишет JSON + служебную строку; или несколько JSON подряд
    out, i, n = [], 0, len(txt)
    dec = json.JSONDecoder()
    while i < n:
        while i < n and txt[i] in ' \t\r\n':
            i += 1
        if i >= n:
            break
        if txt[i] not in '{[':
            # skip a non-JSON line
            nl = txt.find('\n', i)
            i = n if nl < 0 else nl + 1
            continue
        try:
            obj, end = dec.raw_decode(txt, i)
            out.append(obj)
            i = end
        except Exception:
            break
    if not out:
        try:
            return json.loads(txt)
        except Exception:
            return {}
    return out[0] if len(out) == 1 else out

def bog_day(s):
    if not s:
        return None
    s = str(s)
    if len(s) == 10 and s[4] == '-':
        return s
    try:
        dt = datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=BOG)
        return dt.astimezone(BOG).date().isoformat()
    except Exception:
        return s[:10] if len(s) >= 10 else None

blobs = [load(open(f).read()) for f in a.files] if a.files else [load(sys.stdin.read())]
cal, raw = None, []
def take(b):
    global cal
    if isinstance(b, list):
        for x in b:
            if isinstance(x, dict) and ('events' in x or 'items' in x): take(x)
            elif isinstance(x, dict): raw.append(x)
    elif isinstance(b, dict):
        cal = cal or b.get('calendar') or b.get('summary')
        raw.extend(b.get('events') or b.get('items') or [])
for b in blobs: take(b)
if not raw:
    sys.exit('refresh_gcal_dash: событий не найдено во входе — снимок НЕ перезаписан')

seen, ev = set(), []
for e in raw:
    if e.get('status') == 'cancelled' or e.get('id') in seen: continue
    seen.add(e.get('id'))
    s, en = e.get('start') or {}, e.get('end') or {}
    all_day = 'date' in s and 'dateTime' not in s
    ev.append(dict(id=e.get('id'), title=e.get('summary') or e.get('title') or '(без названия)',
                   start=s.get('dateTime') or s.get('date') or e.get('start'),
                   end=en.get('dateTime') or en.get('date') or e.get('end'),
                   all_day=all_day if 'start' in e and isinstance(e.get('start'), dict) else bool(e.get('all_day')),
                   url=e.get('htmlLink') or e.get('url'), location=e.get('location')))
ev.sort(key=lambda x: (x['start'] or ''))

now = datetime.datetime.now(BOG)
d0 = datetime.date.fromisoformat(a.start) if a.start else now.date()
d1 = d0 + datetime.timedelta(days=a.days)
win_a, win_b = d0.isoformat(), d1.isoformat()

# Слияние со старым снимком: не затираем дни вне окна этой выборки (t6314u).
kept = 0
if os.path.exists(a.out):
    try:
        old = json.load(open(a.out))
    except Exception:
        old = {}
    for e in old.get('events') or []:
        eid, st = e.get('id'), bog_day(e.get('start'))
        if not eid or eid in seen:
            continue
        if st and win_a <= st <= win_b:
            continue  # окно выборки полностью заменено новым входом
        ev.append(e)
        seen.add(eid)
        kept += 1
ev.sort(key=lambda x: (x['start'] or ''))

# range — покрытие по дням НАЧАЛА событий + окно выборки (конец all-day в GCal = следующий день, его не берём)
start_days = [d for d in (bog_day(e.get('start')) for e in ev) if d]
rs = min([win_a] + start_days) if start_days else win_a
re_ = max([win_b] + start_days) if start_days else win_b
res = dict(fetched_at=now.strftime('%Y-%m-%dT%H:%M-05:00'), calendar=cal or 'zayavki.ua@gmail.com',
           range=dict(start=rs, end=re_, tz='America/Bogota'),
           events=ev)
timed = sum(1 for x in ev if not x['all_day'])
print(f"gcal: {len(ev)} событий ({timed} со временем, {len(ev)-timed} весь день) · {res['range']['start']}…{res['range']['end']} · merge kept {kept} · fetched {res['fetched_at']}")
if a.dry: sys.exit(0)
os.makedirs(os.path.dirname(os.path.abspath(a.out)) or '.', exist_ok=True)
tmp = a.out + '.tmp'
json.dump(res, open(tmp, 'w'), ensure_ascii=False, indent=2)
os.replace(tmp, a.out)
print('→', a.out)
# зеркало в репо даша, если писали канонический путь
repo = '/workspace/dash-gh/gcal_dash.json'
if os.path.abspath(a.out) != os.path.abspath(repo) and os.path.isdir('/workspace/dash-gh'):
    tmp2 = repo + '.tmp'
    json.dump(res, open(tmp2, 'w'), ensure_ascii=False, indent=2)
    os.replace(tmp2, repo)
    print('→', repo)
