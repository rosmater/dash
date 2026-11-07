#!/usr/bin/env python3
"""Rost t4306/t4307: обновить снимок ClickUp-задач со временем для календаря даша (/workspace/cu_cal_dash.json).
Зеркало refresh_gcal_dash.py. MCP из build.sh не вызывается, поэтому агент делает так:
  1) ClickUp коннектор → clickup_filter_tasks assignees=[me], due_date_from=<сегодня 00:00 Богота>,
     due_date_to=<сегодня+15д>, (write_to_file=true; если has_more — дочитать page=1.. и передать все файлы)
  2) python3 src/refresh_cu_cal_dash.py <файл1> [файл2 ...]      (или JSON на stdin)
  3) dash_touch_append.py → src/build.sh → пуш (как обычно)

ЗАПУСКАТЬ ТОЛЬКО когда бот создал/изменил задачу с due СО ВРЕМЕНЕМ или WIDE-поллинг увидел новый/сдвинутый
timed due. Упоминание календаря в чате само по себе — НЕ повод (Rost t4307).

Вход: ответ filter_tasks ({tasks:[...]} / [tasks] / несколько JSON-строк). Выход — прежняя форма cu_cal_dash.json:
  {fetched_at, tasks:[{id,name,status,priority,due_ms,list}]}
Без времени = due 04:00 Богота (09:00 UTC) — в снимке остаются (build_data.py сам их отбрасывает), но в счёт «timed» не идут.
Флаги: --out PATH (по умолч. /workspace/cu_cal_dash.json), --dry (сводка без записи),
       --if-timed-changed (не писать и выйти с кодом 10, если набор timed (id,due_ms,status) не изменился против --out).
Нет задач во входе → exit 1, снимок НЕ перезаписан.
"""
import json, sys, os, datetime, argparse

BOG = datetime.timezone(datetime.timedelta(hours=-5))
ap = argparse.ArgumentParser()
ap.add_argument('files', nargs='*')
ap.add_argument('--out', default='/workspace/cu_cal_dash.json')
ap.add_argument('--dry', action='store_true')
ap.add_argument('--if-timed-changed', action='store_true')
a = ap.parse_args()

def load(txt):
    txt = txt.strip()
    try:
        return json.loads(txt)
    except Exception:
        out = []  # обёртки/несколько JSON-строк подряд
        for ln in txt.splitlines():
            ln = ln.strip()
            if ln.startswith('{') or ln.startswith('['):
                try: out.append(json.loads(ln))
                except Exception: pass
        return out

raw = []
def take(b):
    if isinstance(b, list):
        for x in b:
            if isinstance(x, dict) and 'tasks' in x: take(x)
            elif isinstance(x, dict) and 'id' in x: raw.append(x)
    elif isinstance(b, dict):
        if 'tasks' in b: raw.extend(b.get('tasks') or [])
        elif 'id' in b and 'name' in b: raw.append(b)
blobs = [load(open(f).read()) for f in a.files] if a.files else [load(sys.stdin.read())]
for b in blobs: take(b)
if not raw:
    sys.exit('refresh_cu_cal_dash: задач не найдено во входе — снимок НЕ перезаписан')

def s(v, k):
    if isinstance(v, dict): return v.get(k)
    return v

def is_timed(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, BOG).strftime('%H:%M') != '04:00'

seen, tasks = set(), []
for t in raw:
    tid, due = t.get('id'), t.get('due_date')
    if not tid or tid in seen or due in (None, '', 0): continue
    try: due_ms = int(due)
    except Exception: continue
    seen.add(tid)
    tasks.append(dict(id=tid, name=t.get('name') or '(без названия)', status=s(t.get('status'), 'status'),
                      priority=s(t.get('priority'), 'priority'), due_ms=due_ms, list=s(t.get('list'), 'name')))
if not tasks:
    sys.exit('refresh_cu_cal_dash: во входе нет задач с due_date — снимок НЕ перезаписан')
tasks.sort(key=lambda x: x['due_ms'])

now = datetime.datetime.now(BOG)
res = dict(fetched_at=now.strftime('%Y-%m-%dT%H:%M-05:00'), tasks=tasks)
timed = [x for x in tasks if is_timed(x['due_ms'])]

def tkey(lst): return {(x['id'], x['due_ms'], x.get('status')) for x in lst if is_timed(x['due_ms'])}
prev = []
try: prev = json.load(open(a.out)).get('tasks', [])
except Exception: pass
new_k, old_k = tkey(tasks), tkey(prev)
added = {k[0] for k in new_k - old_k}; gone = {k[0] for k in old_k - new_k}
print(f"cu_cal: {len(tasks)} задач с due ({len(timed)} со временем, {len(tasks)-len(timed)} только дата) · fetched {res['fetched_at']}")
print(f"timed vs прежний снимок: +{len(added - gone)} новых, ~{len(added & gone)} изменённых, -{len(gone - added)} ушедших")
for x in timed[:8]:
    print('  ', datetime.datetime.fromtimestamp(x['due_ms']/1000, BOG).strftime('%d.%m %H:%M'), x['status'], '|', x['name'][:60], '|', x['list'])
if a.if_timed_changed and new_k == old_k:
    print('timed без изменений — снимок не трогаю'); sys.exit(10)
if a.dry: sys.exit(0)
tmp = a.out + '.tmp'
json.dump(res, open(tmp, 'w'), ensure_ascii=False, indent=2)
os.replace(tmp, a.out)
print('→', a.out)
