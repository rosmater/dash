#!/usr/bin/env python3
"""Rost t6322u: «🤖 На решении у бота» — карта бот → рутины + задачи ClickUp на проверке/в работе у бота.

Источники (только реальные, без выдуманного; нет данных → «нет данных»):
- рутины: /workspace/bot-routines-inventory/<BOT>.md (живые инвентари, только enabled) +
  роль/состав пакета из ROUTINE-GROUPS.md (по folder) → подсказка;
- задачи: открытые из ClickUp VIEW «Ros (BOT)» (8cn3rz8-3574, снимок src/ma_ros_bot.json).
  Фильтр вида (AND): status NOT closed; assignee ANY Rost 60710247; поле BOT R IS SET.
  Группа = значение BOT R (иначе тег/исполнитель/текст, иначе «без бота»).
  Вкладка = тема (снимок пептидов / списки / ключевые слова).
CLI: python3 src/bot_work_gen.py  → пишет src/bot_work.json. build_data.py вызывает build() при каждой сборке.
  Снимок вида тянет src/cu_ros_bot_pull.py (до build_data в build.sh).
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
BOT_R_DISP = {
    'Секретарь': 'Секретарь',
    'Помощник по всему': 'Помощник по всему',
    'Оборонный проект': 'Оборонка',
    'Юрист / Адвокат': 'Юрист / Адвокат / Бухгалтер',
    'ОФ Маркетинг': 'ОФ Маркетинг',
    'Д': 'Дейтинг',
    'Пептид': 'Пептид',
}
LIST_TAB = [
    ('Personal', 'personal'),
    ('Сервисная доска Недвижимость', 'realestate'),
    ('Покупка, Ремонт, Продажа-Сдача', 'realestate'),
    ('General Tasks OF', 'of'),
    ('Models', 'of'),
    ('Projects OF', 'of'),
    ('Задачи Tabakevich', 'tabakevich'),
]
TAB_KW = [
    ('peptides', ['пептид', 'peso saludable']),
    ('realestate', ['недвиж', 'solvia', 'сагунт', 'новельд', 'топасио', 'окупас']),
    ('of', ['onlyfans', 'of.tv', 'oftv', 'лолап', 'lolapop', 'миле']),
    ('tabakevich', ['табакевич', 'хукашоп', 'hooka', 'пальма', '1с']),
    ('personal', ['мама', 'коуч', 'парагвай', 'банк']),
]
RTAB_KW = [
    ('peptides', ['pep', 'peptid', 'peso']),
    ('realestate', ['re', 'realty', 'solvia', 'недвиж', 'helper']),
    ('of', ['of', 'farm', 'lolapop', 'oftv', 'seider']),
    ('tabakevich', ['tbk', 'tabak', 'hooka', '1c', '1с']),
    ('personal', ['comms', 'personal', 'calendar', 'coach', 'secretary']),
]


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


def _pep_ids():
    ids = set()
    try:
        d = json.load(open(os.path.join(HERE, 'peptides_open_tasks.json'), encoding='utf-8'))
        for t in (d.get('tasks') if isinstance(d, dict) else d) or []:
            if isinstance(t, dict) and t.get('id'):
                ids.add(t['id'])
    except Exception:
        pass
    return ids


def _owner(t):
    br = (t.get('bot_r') or '').strip()
    if br:
        return BOT_R_DISP.get(br, br)
    for tag in t.get('tags') or []:
        name = tag.get('name') if isinstance(tag, dict) else str(tag)
        n = (name or '').strip()
        if n and n.lower() != 'bot' and (n in BOT_R_DISP or n in dict(BOTS)):
            return BOT_R_DISP.get(n, n)
    for a in t.get('assignees') or []:
        un = (a.get('username') if isinstance(a, dict) else '') or ''
        if un in BOT_R_DISP or un in dict(BOTS):
            return BOT_R_DISP.get(un, un)
    nl = (t.get('name') or '').lower()
    for o, kws in OWN_KW:
        if any(k in nl for k in kws):
            return o
    return 'без бота'


def _tab(t, pep_ids):
    if t.get('id') in pep_ids:
        return 'peptides'
    nl = (t.get('name') or '').lower()
    for tab, kws in TAB_KW:
        if any(k in nl for k in kws):
            return tab
    lst = t.get('list') or ''
    for k, tab in LIST_TAB:
        if k.lower() in lst.lower():
            return tab
    return 'personal'


def _routine_tab(r):
    blob = ' '.join([(r.get('folder') or ''), (r.get('name') or ''), (r.get('desc') or '')]).lower()
    for tab, kws in RTAB_KW:
        if any(k in blob for k in kws):
            return tab
    return ''


def _ros_bot_tasks():
    try:
        d = json.load(open(os.path.join(HERE, 'ma_ros_bot.json'), encoding='utf-8'))
    except Exception:
        return [], '', ''
    tasks = d.get('tasks') if isinstance(d, dict) else d
    return list(tasks or []), (d.get('fetched') if isinstance(d, dict) else '') or '', (d.get('src') if isinstance(d, dict) else '') or ''


def build():
    links, _cu_tasks, _cu_fetched = _bot_links()
    roles = group_roles()
    ros_tasks, ros_fetched, ros_src = _ros_bot_tasks()
    pep_ids = _pep_ids()
    known = {}
    for t in ros_tasks:
        if t.get('id'):
            known[t['id']] = t.get('name') or ''
    bots = []
    seen_bots = set()
    for name, fn, mode in BOTS:
        seen_bots.add(name)
        rows, upd = parse_inventory(fn, mode)
        R = []
        for r in rows or []:
            role = roles.get(r['folder'], '')
            note = r.get('note') or ''
            if re.match(r'^(last|ok\b|live ok)', note, re.I):
                note = ''
            desc = role or note
            ids = sorted(set(CUID_RX.findall(desc + ' ' + note)))
            item = dict(name=r['name'], sched=r['sched'], folder=r['folder'], desc=desc or 'нет данных',
                        service=bool(SERVICE_RX.search(r['name'])),
                        tab=_routine_tab(r),
                        cu=[dict(id=i, name=known[i], url=CU + i) for i in ids if known.get(i)])
            R.append(item)
        T = []
        for t in ros_tasks:
            if _owner(t) != name:
                continue
            st = (t.get('status') or '').lower()
            T.append(dict(id=t['id'], name=t.get('name', ''), status=t.get('status', ''), list=t.get('list', ''),
                          updated=t.get('updated', ''), due=t.get('due') or '',
                          need='rost' if st == 'for check' else '',
                          url=t.get('url') or CU + t['id'],
                          kind='check' if st == 'for check' else 'work',
                          tab=_tab(t, pep_ids),
                          bot_r=t.get('bot_r') or '',
                          priority=t.get('priority') or ''))
        T.sort(key=lambda x: (0 if x['need'] == 'rost' else 1, x.get('due') or '9999', x.get('updated') or ''))
        bots.append(dict(name=name, link=links.get(name) or '', inv=fn, inv_updated=upd,
                         routines=R, routines_note='' if rows is not None else 'нет данных (нет файла инвентаря)',
                         tasks=T))
    extra = {}
    for t in ros_tasks:
        o = _owner(t)
        if o not in seen_bots:
            extra.setdefault(o, []).append(t)
    for name, ts in extra.items():
        T = []
        for t in ts:
            st = (t.get('status') or '').lower()
            T.append(dict(id=t['id'], name=t.get('name', ''), status=t.get('status', ''), list=t.get('list', ''),
                          updated=t.get('updated', ''), due=t.get('due') or '',
                          need='rost' if st == 'for check' else '',
                          url=t.get('url') or CU + t['id'],
                          kind='check' if st == 'for check' else 'work',
                          tab=_tab(t, pep_ids),
                          bot_r=t.get('bot_r') or '',
                          priority=t.get('priority') or ''))
        T.sort(key=lambda x: (0 if x['need'] == 'rost' else 1, x.get('due') or '9999', x.get('updated') or ''))
        bots.append(dict(name=name, link=links.get(name) or '', inv='', inv_updated='',
                         routines=[], routines_note='нет данных' if name == 'без бота' else '',
                         tasks=T))
    return dict(
        generated=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        signal='Открытые задачи вида ClickUp «Ros (BOT)» (8cn3rz8-3574): status NOT closed AND assignee=Rost AND BOT R IS SET. Группа — поле BOT R.',
        cu_fetched=ros_fetched,
        src=dict(routines=INV + '/<BOT>.md + ROUTINE-GROUPS.md', tasks=ros_src or 'src/ma_ros_bot.json'),
        bots=bots)



if __name__ == '__main__':
    d = build()
    json.dump(d, open(os.path.join(HERE, 'bot_work.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for b in d['bots']:
        print(b['name'], 'routines', len(b['routines']), 'tasks', len(b['tasks']), b['routines_note'])
