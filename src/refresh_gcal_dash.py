#!/usr/bin/env python3
"""Rost т251 / CU 86bctqe8h: обновить снимок Google Calendar для даша (/workspace/gcal_dash.json).

MCP из build.sh не вызывается, поэтому агент делает так:
  1) Google Calendar коннектор `user-Google-calendar` → list_events
       calendarId=primary, timeZone=America/Bogota, maxResults=250,
       startTime=<сегодня>T00:00:00-05:00, endTime=<сегодня+15д>T00:00:00-05:00  (15 — чтобы день +14 был целиком)
     (write_to_file=true → файл agent-tools/*.txt; если есть nextPageToken — дочитать и передать все файлы)
  2) python3 src/refresh_gcal_dash.py <файл1> [файл2 ...]      (или JSON на stdin)
  3) dash_touch_append.py → src/build.sh → пуш (как обычно)

Вход: ответ list_events ({calendar,timeZone,events:[...]}) ИЛИ голый список events (формат Calendar API events.list —
тот же, что отдаёт live OAuth в браузере). Выход — прежняя форма gcal_dash.json:
  {fetched_at, calendar, range:{start,end,tz}, events:[{id,title,start,end,all_day,url,location}]}
Флаги: --out PATH (по умолч. /workspace/gcal_dash.json), --days N (14), --dry (печать сводки без записи).
"""
import json, sys, os, datetime, argparse

BOG = datetime.timezone(datetime.timedelta(hours=-5))
ap = argparse.ArgumentParser()
ap.add_argument('files', nargs='*')
ap.add_argument('--out', default='/workspace/gcal_dash.json')
ap.add_argument('--days', type=int, default=14)
ap.add_argument('--dry', action='store_true')
a = ap.parse_args()

def load(txt):
    txt = txt.strip()
    try:
        return json.loads(txt)
    except Exception:
        # коннектор иногда пишет несколько JSON-строк подряд
        out = []
        for ln in txt.splitlines():
            ln = ln.strip()
            if ln.startswith('{') or ln.startswith('['):
                try: out.append(json.loads(ln))
                except Exception: pass
        return out

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
    ev.append(dict(id=e.get('id'), title=e.get('summary') or '(без названия)',
                   start=s.get('dateTime') or s.get('date'), end=en.get('dateTime') or en.get('date'),
                   all_day=all_day, url=e.get('htmlLink'), location=e.get('location')))
ev.sort(key=lambda x: (x['start'] or ''))

now = datetime.datetime.now(BOG)
d0 = now.date()
res = dict(fetched_at=now.strftime('%Y-%m-%dT%H:%M-05:00'), calendar=cal or 'zayavki.ua@gmail.com',
           range=dict(start=d0.isoformat(), end=(d0 + datetime.timedelta(days=a.days)).isoformat(), tz='America/Bogota'),
           events=ev)
timed = sum(1 for x in ev if not x['all_day'])
print(f"gcal: {len(ev)} событий ({timed} со временем, {len(ev)-timed} весь день) · {res['range']['start']}…{res['range']['end']} · fetched {res['fetched_at']}")
if a.dry: sys.exit(0)
tmp = a.out + '.tmp'
json.dump(res, open(tmp, 'w'), ensure_ascii=False, indent=2)
os.replace(tmp, a.out)
print('→', a.out)
