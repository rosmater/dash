#!/usr/bin/env python3
"""t6454u: еженедельная сверка даша и ClickUp без LLM (для вторничной рутины). Только чтение снимков в src/.
Печатает короткий отчёт: возраст снимков, задачи без срока / Role / Frecuencia / приоритета, зависшие «✓ решено».
Рутина: 1) (если есть токен) python3 src/cu_snap_sync.py --full  2) python3 src/cu_weekly_audit.py
        3) модель читает только этот отчёт; exit 0 и «всё ок» → ничего не делать.
Exit: 0 всё ок, 3 есть что поправить."""
import json, os, datetime, sys
H = os.path.dirname(os.path.abspath(__file__))
BOG = datetime.timezone(datetime.timedelta(hours=-5))
now = datetime.datetime.now(BOG)
SNAPS = {'of_open_tasks.json': 'ОФ', 'tbk_open_tasks.json': 'Табакевич', 'personal_open_tasks.json': 'Личное',
         'peptides_open_tasks.json': 'Пептиды', 'ma_ros.json': 'Ros', 'ma_ros_bot.json': 'Ros (BOT)',
         'cu_roles.json': 'карта Role', 'cu_recurring.json': 'повторы ↻', 'cu_dated.json': 'cu_dated'}
def age(v):
    s = str(v or '').replace(' Bogotá', '').replace('T', ' ')[:16]
    try:
        return (now.replace(tzinfo=None) - datetime.datetime.strptime(s, '%Y-%m-%d %H:%M')).total_seconds() / 3600
    except Exception:
        return None
roles = json.load(open(os.path.join(H, 'cu_roles.json'))).get('by_id', {})
issues, lines = 0, []
for f, label in SNAPS.items():
    p = os.path.join(H, f)
    if not os.path.exists(p):
        lines.append(f'✗ {label}: нет файла'); issues += 1; continue
    d = json.load(open(p)); a = age(d.get('fetched_at') or d.get('fetched') or d.get('updated_at'))
    if a is None:
        a = (now.timestamp() - os.path.getmtime(p)) / 3600
    flag = '✗' if a > 24 else '✓'
    issues += a > 24
    msg = f'{flag} {label}: снимок {a:.0f} ч назад'
    ts = d.get('tasks') if isinstance(d.get('tasks'), list) else None
    if ts is not None and f.endswith('_open_tasks.json'):
        nodue = [t for t in ts if not t.get('due')]
        norole = [t for t in ts if not (t.get('role') or roles.get(t.get('id')))]
        nofreq = [t for t in ts if not t.get('freq')]
        nopri = [t for t in ts if not t.get('priority')]
        msg += f' · задач {len(ts)} · без срока {len(nodue)} · без Role {len(norole)} · без Frecuencia {len(nofreq)} · без приоритета {len(nopri)}'
        issues += bool(nodue or nopri)
        for t in nodue[:5]:
            msg += f'\n    без срока: {t["id"]} {t.get("name","")[:60]}'
    lines.append(msg)
try:
    dp = json.load(open(os.path.join(H, 'done_pending.json')))
    items = dp.get('items') if isinstance(dp, dict) else {}
    stuck = [k for k, v in (items or {}).items() if isinstance(v, dict) and v.get('state') in ('pending', 'failed')]
    lines.append(('✗' if stuck else '✓') + f' «✓ решено» не закрылись в ClickUp: {len(stuck)} {" ".join(stuck[:8])}')
    issues += bool(stuck)
except Exception as e:
    lines.append(f'? done_pending: {type(e).__name__}')
print('Сверка даш ↔ ClickUp ' + now.strftime('%d.%m %H:%M') + ' Богота')
print('\n'.join(lines))
print('итог: всё ок' if not issues else f'итог: есть что поправить ({issues})')
sys.exit(0 if not issues else 3)
