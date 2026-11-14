#!/usr/bin/env python3
"""Rost t6322u: «🤖 На решении у бота» — карта бот → рутины + задачи ClickUp на проверке/в работе у бота.

Источники (только реальные, без выдуманного; нет данных → «нет данных»):
- рутины: /workspace/bot-routines-inventory/<BOT>.md (живые инвентари, только enabled) +
  роль/состав пакета из ROUTINE-GROUPS.md (по folder) → подсказка;
- задачи: data-test-ma.json → clickup.tasks (снимок src/ma_clickup.json: CU статус «for check», исполнитель Rost 60710247;
  поле bot = владелец из sync/bot_attn.jsonl / ключевых слов; need=rost|ok) +
  задачи «БОТ…» в статусе «in progress» из снимков досок (personal/tbk/of/peptides_open_tasks.json).
CLI: python3 src/bot_work_gen.py  → пишет src/bot_work.json. build_data.py вызывает build() при каждой сборке.
"""
import json, os, re, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INV = '/workspace/bot-routines-inventory'
CU = 'https://app.clickup.com/t/'
# имя бота (как во вкладке «Ассистенты · боты») → файл инвентаря, способ разбора
BOTS = [
    ('Секретарь', 'COMMS.md', 'table'),
    ('Помощник по всему', 'HELPER.md', 'table:LIVE enabled'),
    ('ОФ Маркетинг', 'OF.md', 'table:LIVE enabled'),
    ('Пептид', 'PEPTIDE.md', 'table'),
    ('Фермовод', 'FARM.md', 'bullets'),
    ('Дейтинг', 'DATING.md', 'bullets'),
    ('Юрист / Адвокат / Бухгалтер', 'LAWYER.md', 'table:last'),
    ('Оборонка', 'DEFENSE.md', 'table'),
]
SERVICE_RX = re.compile(r'QUEUE|самопроверка|watchdog|resume|webhook drain', re.I)
CUID_RX = re.compile(r'\b86[a-z0-9]{7}\b')
# задачи in progress «БОТ…»: владелец по ключевым словам (как test_ma_build._OWN_KW), иначе по списку
OWN_KW = [('Фермовод', ['сейдер', 'seider', 'onimator', 'nomix']),
          ('ОФ Маркетинг', ['миле', 'офиса оф', 'трекера', 'of.tv', 'лолап', 'lolapop']),
          ('Юрист / Адвокат / Бухгалтер', ['парагвай']),
          ('Пептид', ['пептид', 'peso saludable'])]
LIST_OWN = [('Personal', 'Секретарь'), ('Tabakevich', 'Помощник по всему'), ('OF', 'ОФ Маркетинг'), ('Models', 'ОФ Маркетинг')]


def _read(p):
    try:
        return open(p, encoding='utf-8').read()
    except Exception:
        return ''


def _cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def _tables(text):
    """[(heading, header_cells, rows)] — markdown-таблицы с ближайшим заголовком ##."""
    out, head, cur = [], '', None
    for ln in text.splitlines():
        if ln.startswith('#'):
            head = ln.lstrip('#').strip()
        if ln.strip().startswith('|'):
            c = _cells(ln)
            if cur is None:
                cur = (head, [x.lower() for x in c], [])
                out.append(cur)
            elif all(re.fullmatch(r':?-{2,}:?', x or '--') for x in c):
                continue
            else:
                cur[2].append(c)
        else:
            cur = None
    return out


def _col(hdr, *names):
    for i, h in enumerate(hdr):
        if any(n in h for n in names):
            return i
    return None


def _rows_from_table(head, hdr, rows):
    iN = _col(hdr, 'routine', 'name')
    iF = _col(hdr, 'folder')
    iS = _col(hdr, 'schedule', 'trigger')
    iE = _col(hdr, 'status', 'enabled')
    iT = _col(hdr, 'note')
    if iN is None:
        return []
    res = []
    for r in rows:
        g = lambda i: (r[i] if i is not None and i < len(r) else '').strip()
        st = g(iE).lower()
        if st and ('paused' in st or 'deleted' in st) and 'enabled' not in st:
            continue
        if iE is not None and st and 'enabled' not in st:
            continue
        res.append(dict(name=g(iN).replace('**', ''), folder=g(iF).strip('`'), sched=re.sub(r'CRON_TZ=\S+\s*', '', g(iS).replace('`', '')).strip(), note=g(iT).replace('**', '')))
    return res


def parse_inventory(fn, mode):
    text = _read(os.path.join(INV, fn))
    if not text:
        return None, ''
    m = re.search(r'(?:Updated|updated|dumped_at)[:\s]+(\d{4}-\d{2}-\d{2}[ T]?\d{0,2}:?\d{0,2})', text)
    upd = m.group(1).strip() if m else ''
    if mode.startswith('table'):
        T = _tables(text)
        if mode == 'table:last':
            T = [t for t in T if _col(t[1], 'status') is not None][-1:]
        elif ':' in mode:
            want = mode.split(':', 1)[1].lower()
            T = [t for t in T if want in t[0].lower()][:1]
        else:
            T = T[:1]
        return (_rows_from_table(*T[0]) if T else []), upd
    # bullets: «- Имя — расписание (folder)» / «- Имя (folder) — ENABLED, webhook»
    res, on = [], None
    for ln in text.splitlines():
        s = ln.strip()
        if re.match(r'^(Enabled|Paused|Deleted)\b', s):
            on = s.lower().startswith('enabled')
            continue
        if not s.startswith('- '):
            continue
        s = s[2:]
        if on is False:
            continue
        if on is None and not re.search(r'\bENABLED\b', s):
            continue
        fm = re.findall(r'\(([^()]*)\)', s)
        folder = fm[-1].split()[-1] if fm else ''
        if folder.lower() in ('folder',):
            folder = ''
        parts = re.split(r'\s+—\s+', re.sub(r'\s*\([^()]*\)', '', s))
        name = parts[0].strip()
        sched = ', '.join(p for p in parts[1:] if p.strip().upper() != 'ENABLED').replace('ENABLED, ', '').strip()
        res.append(dict(name=name, folder=folder, sched=sched, note=''))
    return res, upd


def group_roles():
    """folder → роль/состав пакета из ROUTINE-GROUPS.md (+COMMS-ROUTINES-FULL KB колонка)."""
    text = _read(os.path.join(INV, 'ROUTINE-GROUPS.md'))
    roles = {}
    for m in re.finditer(r'^\|\s*`([^`]+)`([^\n]*)', text, re.M):
        folder = m.group(1).split()[0]
        rest = m.group(1)[len(folder):] + m.group(2)
        cells = [c.strip() for c in rest.split('|') if c.strip()]
        cells = [c for c in cells if not re.fullmatch(r'(?:CRON_TZ=\S+\s*)?`?[\d*/,\-\s@a-z]+`?', c, re.I) and not re.fullmatch(r'\*\*?(enabled|paused)\*?\*?.*', c, re.I)]
        if not cells:
            continue
        role = max(cells, key=len).replace('**', '').replace('`', '').strip(' —-')
        if folder not in roles or len(role) > len(roles[folder]):
            roles[folder] = role
    return roles


def _bot_links():
    try:
        d = json.load(open(os.path.join(ROOT, 'data-test-ma.json'), encoding='utf-8'))
    except Exception:
        return {}, [], ''
    links = {b['name']: b.get('link') for b in d.get('bots', []) if not b.get('coach')}
    cu = d.get('clickup') or {}
    return links, cu.get('tasks') or [], cu.get('fetched') or ''


def _snap_inprogress():
    out = {}
    for fn in ('personal_open_tasks.json', 'tbk_open_tasks.json', 'of_open_tasks.json', 'peptides_open_tasks.json'):
        try:
            d = json.load(open(os.path.join(HERE, fn), encoding='utf-8'))
        except Exception:
            continue
        L = d.get('tasks') if isinstance(d, dict) else d
        for t in L or []:
            if not isinstance(t, dict):
                continue
            if (t.get('status') or '').lower() == 'in progress' and re.match(r'^\W*БОТ', t.get('name') or ''):
                out.setdefault(t['id'], dict(t, _src=fn))
    return out


def _owner(t):
    nl = (t.get('name') or '').lower()
    for o, kws in OWN_KW:
        if any(k in nl for k in kws):
            return o
    lst = t.get('list') or ''
    for k, o in LIST_OWN:
        if k.lower() in lst.lower():
            return o
    return 'Помощник по всему'


def build():
    links, cu_tasks, cu_fetched = _bot_links()
    roles = group_roles()
    known = {}
    for t in cu_tasks:
        known[t['id']] = t.get('name') or ''
    ip = _snap_inprogress()
    for i, t in ip.items():
        known.setdefault(i, t.get('name') or '')
    for fn in ('personal_open_tasks.json', 'tbk_open_tasks.json', 'of_open_tasks.json', 'peptides_open_tasks.json', 'of_cu_tasks.json'):
        try:
            d = json.load(open(os.path.join(HERE, fn), encoding='utf-8'))
        except Exception:
            continue
        for t in (d.get('tasks') if isinstance(d, dict) else d) or []:
            if isinstance(t, dict) and t.get('id') and not str(t.get('status') or '').lower().startswith('complete'):
                known.setdefault(t['id'], t.get('name') or '')
    bots = []
    for name, fn, mode in BOTS:
        rows, upd = parse_inventory(fn, mode)
        R = []
        for r in rows or []:
            role = roles.get(r['folder'], '')
            note = r.get('note') or ''
            if re.match(r'^(last|ok\b|live ok)', note, re.I):
                note = ''
            desc = role or note
            ids = sorted(set(CUID_RX.findall(desc + ' ' + note)))
            R.append(dict(name=r['name'], sched=r['sched'], folder=r['folder'], desc=desc or 'нет данных',
                          service=bool(SERVICE_RX.search(r['name'])),
                          cu=[dict(id=i, name=known[i], url=CU + i) for i in ids if known.get(i)]))  # только открытые задачи из снимков (закрытые id в тексте не показываем)
        T = []
        for t in cu_tasks:
            if (t.get('bot') or '') == name:
                T.append(dict(id=t['id'], name=t.get('name', ''), status=t.get('status', ''), list=t.get('list', ''),
                              updated=t.get('updated', ''), need=t.get('need', 'rost'), url=CU + t['id'], kind='check'))
        for i, t in ip.items():
            if _owner(t) == name and not any(x['id'] == i for x in T):
                T.append(dict(id=i, name=t.get('name', ''), status=t.get('status', ''), list=t.get('list', ''),
                              updated='', need='', url=t.get('url') or CU + i, kind='work', due=t.get('due')))
        T.sort(key=lambda x: (0 if x['need'] == 'rost' else 1, x['kind'] != 'check', x.get('updated') or ''), reverse=False)
        bots.append(dict(name=name, link=links.get(name) or '', inv=fn, inv_updated=upd,
                         routines=R, routines_note='' if rows is not None else 'нет данных (нет файла инвентаря)',
                         tasks=T))
    return dict(
        generated=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        signal='CU статус «for check» на Rost (снимок src/ma_clickup.json, владелец-бот из sync/bot_attn.jsonl) + задачи «БОТ…» в статусе «in progress» из снимков досок',
        cu_fetched=cu_fetched,
        src=dict(routines=INV + '/<BOT>.md + ROUTINE-GROUPS.md', tasks='data-test-ma.json clickup.tasks + src/*_open_tasks.json'),
        bots=bots)


if __name__ == '__main__':
    d = build()
    json.dump(d, open(os.path.join(HERE, 'bot_work.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for b in d['bots']:
        print(b['name'], 'routines', len(b['routines']), 'tasks', len(b['tasks']), b['routines_note'])
