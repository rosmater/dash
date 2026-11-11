#!/usr/bin/env python3
"""Rost t6005u/t6006u: «🎧 Монитор работы менеджеров» (Табакевич) — генератор, без выдуманных цифр.

Источники (последняя полная неделя, где есть всё):
 - Binotel: /workspace/binotel/wNN/{summ.json, tbl_mgr.md, missed.json} + отчёт
   knowledge/notion-brain/business/tabakevich/call-control/REPORT 2026-WNN.md (даты недели).
   Заголовок: «оценено X из Y (вх. A / исх. B / пропущено N)», N = len(missed.json) (пропущенные входящие).
 - HelpCrunch: call-control/archive/helpcrunch-2026-WNN/SUMMARY.md (+ WNN-1 для «пред.»). Папка с FAILED — пропуск.
 - 1С/BAS (ТО и заказы по менеджеру): xlsx-выгрузки списков документов в /workspace/tbk-1c/share-mgr/
   (см. src/tbk_managers_1c_STEPS.md). Документы с пометкой удаления не считаются. Нет файла → null («—»).
   ТО = сумма «Расходных накладных» (реализаций) за неделю блока по «Ответственный»;
   К-во обработанных заказов = число «Заказов покупателей» за неделю по «Ответственный».
Патчит src/tbk_blocks.json → managers. Запуск: python3 src/tbk_managers_gen.py [--week 44]
"""
import datetime, glob, json, os, re, sys
J = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tbk_blocks.json')
BIN = '/workspace/binotel'
CC = '/home/box/contacts/knowledge/notion-brain/business/tabakevich/call-control'
SHARE = '/workspace/tbk-1c/share-mgr'
# 1С «Ответственный» → имя в Binotel/HelpCrunch. Заполнить по первой выгрузке (ФИО в 1С пока не видели).
# Rost t6016u: Binotel «Саша» = Женя = Плотницкая Жанна в 1С — одно имя на даше
WHO = 'Женя (Плотницкая Жанна)'
BIN_NAME = {'Саша': WHO}
RN = lambda x: BIN_NAME.get(x, x)
MAP_1C = {  # только однозначные (среди «Интернет продажи» одна Екатерина и одна Елизавета)
    'Ткаченко Екатерина': 'Катя',
    'Теслина Елизавета': 'Ліза',
    'Плотницкая Жанна': WHO,
}

def wk_ok(n):
    d = f'{BIN}/w{n}'
    return all(os.path.exists(f'{d}/{f}') for f in ('summ.json', 'tbl_mgr.md', 'missed.json')) and os.path.exists(f'{CC}/REPORT 2026-W{n}.md')

def week_dates(n):
    h = open(f'{CC}/REPORT 2026-W{n}.md').read()
    m = re.search(r'\((\d{1,2})(?:\.(\d{2}))?[–-](\d{1,2})\.(\d{2})\.(\d{4})\)', h)
    d1, m1, d2, m2, y = m.groups(); m1 = m1 or m2
    a = datetime.date(int(y) - (1 if int(m1) > int(m2) else 0), int(m1), int(d1)); b = datetime.date(int(y), int(m2), int(d2))
    return a, b

def binotel(n):
    S = json.load(open(f'{BIN}/w{n}/summ.json'))['summ']
    t = open(f'{BIN}/w{n}/tbl_mgr.md').read()
    m = re.search(r'\*\*Все\*\*\s*\|\s*(\d+)\s*\((\d+)/(\d+)\)\s*\|\s*\d+\s*\|\s*(\d+)', t)
    total, inc, out, ge20 = map(int, m.groups())
    missed = json.load(open(f'{BIN}/w{n}/missed.json'))
    by_day = {}
    for x in missed: by_day[x['dt'][:10]] = by_day.get(x['dt'][:10], 0) + 1
    peak = max(by_day.items(), key=lambda kv: kv[1]) if by_day else None
    people = [dict(name=RN(k), pct=v['avg'], calls=v['scored'], bad=v['bad']) for k, v in S.items() if k != 'Все']
    return dict(total=total, scored=S['Все']['scored'], of=ge20, inc=inc, out=out, missed=len(missed),
                missed_note=(f"пропущенных {len(missed)} с {len({x['ph'] for x in missed})} номеров · перезвонили {sum(1 for x in missed if x.get('cb_by'))}"
                             + (f" · пик {peak[0][8:10]}.{peak[0][5:7]} — {peak[1]}" if peak else '')),
                people=people)

# Новый формат архива (t5444-коллектор): archive/2026-WNN/{rows.json, SCORES.txt, SCORED.json, CALLBACKS.json, SCRIPT_CHECK.json}
# SCORES.txt: base|r1 r2 r3 r4 r5 (0–2) или -|флаги скрипта 5×(1/0/?)|0|с/н|заметка — как scores.txt старых недель; base = rows.json[].base
# Неделя «готова», если есть SCORED.json (оценка закончена). Даты недели — Пн–Вс по метке ISO-недели.
def arc(n): return f'{CC}/archive/2026-W{n}'
def new_ok(n): return all(os.path.exists(f'{arc(n)}/{f}') for f in ('rows.json', 'SCORES.txt', 'SCORED.json'))
def new_dates(n):
    a = datetime.date.fromisocalendar(2026, n, 1); return a, a + datetime.timedelta(days=6)
def new_scores(n):
    """[(base, manager, sc|None, flags)] из SCORES.txt + rows.json."""
    R = {r['base']: r for r in json.load(open(f'{arc(n)}/rows.json'))}; out = []
    for l in open(f'{arc(n)}/SCORES.txt', encoding='utf-8'):
        q = l.rstrip('\n').split('|')
        if len(q) < 3 or q[0] not in R: continue
        out.append((q[0], RN(R[q[0]]['manager']), None if q[1].strip() == '-' else [int(x) for x in q[1].split()], q[2], '|'.join(q[5:])))
    return R, out
def binotel_new(n):
    R, S = new_scores(n)
    ans = [r for r in R.values() if r['disposition'] == 'ANSWER' and r['seconds'] > 0]
    sc = [x for x in S if x[2]]
    people = {}
    for b, m, v, fl, _ in sc:
        people.setdefault(m, []).append(sum(v) * 10)
    pl = [dict(name=m, pct=round(sum(v) / len(v)), calls=len(v), bad=sum(1 for x in v if x < 60)) for m, v in sorted(people.items(), key=lambda kv: -len(kv[1]))]
    miss = [r for r in R.values() if r['direction'] == 'incoming' and r['disposition'] not in ('ANSWER', 'SMS-SUCCESS') and r['phone']]
    by_day = {}
    import zoneinfo
    for r in miss:
        d = datetime.datetime.fromtimestamp(r['start'], zoneinfo.ZoneInfo('Europe/Kyiv')).date().isoformat(); by_day[d] = by_day.get(d, 0) + 1
    peak = max(by_day.items(), key=lambda kv: kv[1]) if by_day else None
    return dict(total=len(ans), scored=len(sc), of=sum(1 for r in ans if r['seconds'] >= 20), inc=sum(1 for r in ans if r['direction'] == 'incoming'),
                out=sum(1 for r in ans if r['direction'] == 'outgoing'), missed=len(miss),
                missed_note=f"пропущенных {len(miss)} с {len({r['phone'] for r in miss})} номеров · перезвонили —" + (f" · пик {peak[0][8:10]}.{peak[0][5:7]} — {peak[1]}" if peak else ''),
                people=pl)

EL = [('greet', 'Привет-<br>ствие*'), ('need', 'Потреб-<br>ность'), ('offer', 'Предло-<br>жение'), ('next', 'След.<br>шаг'), ('bye', 'Проща-<br>ние')]
def script_check(n):
    """Rost t6014u: % по элементам скрипта на менеджера из оценок W{n} (флаги 1/0/?; % = да ÷ (да+нет)) + разбор «физический магазин»."""
    W = f'{CC}/archive/2026-W{n}'; p = f'{W}/pipeline/scores.txt'
    C = {}
    if new_ok(n):
        for b, m, v, fl, _ in new_scores(n)[1]:
            if not v or len(fl) < 5: continue
            c = C.setdefault(m, {})
            for i, (k, _) in enumerate(EL):
                y, nn = c.get(k, (0, 0)); c[k] = (y + (fl[i] == '1'), nn + (fl[i] == '0'))
        p = None
    elif not os.path.exists(p): return None
    for l in (open(p) if p else []):
        q = l.rstrip('\n').split('|')
        if len(q) < 3 or q[1].strip() == '-' or len(q[2]) < 5: continue
        f = f'{W}/transcripts/{q[0]}.md'
        if not os.path.exists(f): continue
        m = re.search(r'^manager: (.+)$', open(f).read(), re.M)
        if not m: continue
        c = C.setdefault(RN(m.group(1).strip()), {})
        for i, (k, _) in enumerate(EL):
            y, nn = c.get(k, (0, 0)); c[k] = (y + (q[2][i] == '1'), nn + (q[2][i] == '0'))
    people = []
    for name, c in C.items():
        r = dict(name=name)
        for k, _ in EL:
            y, nn = c.get(k, (0, 0)); r[k] = round(y / (y + nn) * 100) if y + nn else None; r[k + '_n'] = f'{y}/{y + nn}'
        people.append(r)
    phys = None; sc = f'{W}/SCRIPT_CHECK.json'
    if os.path.exists(sc):
        J = json.load(open(sc)); phys = {}
        for x in J.get('physical_store', []):
            a = phys.setdefault(RN(x['manager']), [0, 0]); a[0] += bool(x['ok']); a[1] += 1
        for r in people:
            a = phys.get(r['name']); r['phys'] = f'{a[0]} из {a[1]}' if a else None
    return dict(week=f'W{n}', elements=EL, people=people, phys_how=(J.get('how') if phys is not None else None),
                note='% = «да» ÷ (да + нет), «не слышно» не считается; оценка по расшифровкам Binotel (faster-whisper medium)')

def callbacks(n):
    """Rost t6014u: перезвоны по пропущенным — CALLBACKS.json из notify-watchers/collect/binotel_callbacks.py (неделя блока + свежее)."""
    out = []
    for p in sorted(glob.glob(f'{CC}/archive/2026-W*/CALLBACKS.json')):
        o = json.load(open(p)); w = int(o['week'].split('-W')[1])
        if w < n: continue
        mask = lambda ph: ph[:3] + '…' + ph[-4:] if len(ph) >= 8 else ph
        out.append(dict(week=f"W{w}", missed=o['missed_calls'], clients=o['clients'], cb=o['called_back'], cb_reached=o['called_back_reached'],
                        self=o['self_reached'], none=o['no_contact'], censored=o['censored'], avg=o['cb_time']['avg_min'], med=o['cb_time']['median_min'],
                        by=[dict(name=RN(k), n=v['n'], avg=v['avg_min']) for k, v in o['by_manager'].items()],
                        never=[dict(ph=mask(x['ph']), at=x['first'][8:10] + '.' + x['first'][5:7] + ' ' + x['first'][11:], misses=x['misses'], line=x['line']) for x in o['never']]))
    return out

def hc(n):
    p = f'{CC}/archive/helpcrunch-2026-W{n}'
    if not os.path.exists(f'{p}/SUMMARY.md') or os.path.exists(f'{p}/FAILED'): return None
    s = open(f'{p}/SUMMARY.md').read()
    g = lambda rx, f=str: (lambda m: f(m.group(1)) if m else None)(re.search(rx, s))
    r = dict(chats=g(r'\*\*(\d+) чат', int), asks=g(r'\*\*(\d+) обращени', int), answered=g(r'Отвечено (\d+)', int),
             unanswered=g(r'без ответа (\d+)', int), median=g(r'Общая медиана ответа ([^*]+)\*\*'),
             gt4h=g(r'дольше 4 ч — (\d+)', int), worst=g(r'Худший — ([^(]+?) \('),
             first_new_median=g(r'Первый ответ в новых чатах:\*\* \d+ чат\w*, медиана ([^,]+),'))
    m = re.search(r'≤10 мин — (\d+) из (\d+) \((\d+%)\)', s); r['le10'] = f'{m.group(1)} из {m.group(2)} ({m.group(3)})' if m else None
    m = re.search(r'Оценки клиентов:\*\*([^\n]+)', s)
    if m: r['ratings'] = ' · '.join(f'{a} {b}' for a, b in re.findall(r'(great|average|poor)\D*?(\d+)', m.group(1)))
    sec = s.split('## 2.')[1].split('\n\n')[0] if '## 2.' in s else ''
    r['people'] = []
    for row in sec.splitlines():
        c = [x.strip() for x in row.strip('|').split('|')]
        if len(c) >= 11 and c[0] and not c[0].startswith(('Агент', '---', '**')):
            r['people'].append(dict(name=c[0], asks=int(c[3]), median=c[4], gt4h=int(c[10])))
    return r

def sales_1c(a, b):
    """{имя: {to, orders, refused, returned, ref_pct, ret_pct}} из выгрузок BAS (src/tbk_1c_orders.py); None если нет."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tbk_1c_orders as O
    D = [d for d in O.docs(SHARE) if a <= d['date'] <= b and O.is_im(d)]  # только подразделения «… (Интернет продажи)»
    if not D: return None, None
    out = {}
    for d in D:
        nm = MAP_1C.get(d['manager'], d['manager'])
        o = out.setdefault(nm, dict(to=None, orders=None, refused=0, returned=0))
        if d['kind'] == 'sale': o['to'] = round((o['to'] or 0) + (d['sum'] or 0), 2)
        if d['kind'] == 'order': o['orders'] = (o['orders'] or 0) + 1
        t = O.outcome(d)
        if t == 'отказ': o['refused'] += 1
        if t == 'возврат': o['returned'] += 1
    has_state = any(d['finish'] for d in D if d['kind'] == 'order')
    has_ret = any(d['kind'] == 'return' for d in D) or has_state
    for o in out.values():
        n = o['orders']
        o['ref_pct'] = round(o['refused'] / n * 100, 1) if n and has_state else None
        o['ret_pct'] = round(o['returned'] / n * 100, 1) if n and has_ret else None
        if not has_state: o['refused'] = None
        if not has_ret: o['returned'] = None
    nodel = sorted({d['file'] for d in D if not d['has_del_col'] and not d['has_post_col']})
    return out, sorted({d['file'] for d in D}) + ([f'⚠ без колонки пометки удаления/проведения: {", ".join(nodel)}'] if nodel else [])

def main():
    W = [int(re.search(r'w(\d+)$', d).group(1)) for d in glob.glob(f'{BIN}/w[0-9]*') if re.search(r'w(\d+)$', d)]
    W += [int(re.search(r'W(\d+)$', d).group(1)) for d in glob.glob(f'{CC}/archive/2026-W[0-9]*') if re.search(r'W(\d+)$', d)]
    if '--week' in sys.argv: W = [int(sys.argv[sys.argv.index('--week') + 1])]
    n = max(x for x in W if new_ok(x) or wk_ok(x))  # последняя полная неделя: новый архив (SCORED.json) или старая папка
    NEW = new_ok(n)
    a, b = new_dates(n) if NEW else week_dates(n)
    B = json.load(open(J)); M = B['managers']
    C = binotel_new(n) if NEW else binotel(n); H = hc(n); P = hc(n - 1)
    M['week'] = f"W{n} · {a:%d.%m}–{b:%d.%m}"
    M['period'] = [a.isoformat(), b.isoformat()]
    M['calls'] = {**M.get('calls', {}), **C}
    M['calls']['src'] = f'archive/2026-W{n}' + (' (новый формат)' if NEW else ' (старый формат)')
    M['calls']['script'] = script_check(n)
    M['calls']['callbacks'] = callbacks(n)
    cb0 = next((x for x in M['calls']['callbacks'] if x['week'] == f'W{n}'), None)
    if cb0: M['calls']['missed_note'] = re.sub(r'пропущенных \d+ с \d+ номеров · перезвонили (\d+|—)', f"пропущенных {cb0['missed']} с {cb0['clients']} номеров · перезвонили {cb0['cb']}", M['calls']['missed_note'])
    if H:
        if P: H['prev'] = dict(week=f'W{n-1}', chats=P['chats'], asks=P['asks'], unanswered=P['unanswered'], median=P['median'], gt4h=P['gt4h'])
        M['chats'] = H
    S, used = sales_1c(a, b)
    for p in M['calls']['people']:
        x = (S or {}).get(p['name']) or {}
        for k in ('to', 'orders', 'refused', 'returned', 'ref_pct', 'ret_pct'): p[k] = x.get(k)
        p['upsell'] = None  # допродажи: в BAS нет признака — источника пока нет
        # Rost t6007u: итог = Binotel % × (1 − (отказы + возвраты) / заказы)
        p['score'] = round(p['pct'] * (1 - ((x.get('refused') or 0) + (x.get('returned') or 0)) / x['orders']), 1) if x.get('orders') and (x.get('ref_pct') is not None) else None
    known = {p['name'] for p in M['calls']['people']}
    M['sales_1c_extra'] = [dict(name=k, **v) for k, v in (S or {}).items() if k not in known]
    M['sales_1c_src'] = ('1С/BAS ' + ' + '.join(x for x, k in (('«Заказы покупателей»', 'zakaz'), ('«Расходные накладные»', 'realiz'), ('«Возвраты от покупателей»', 'vozvrat')) if any(k in u for u in used))
        + f' · {a:%d.%m}–{b:%d.%m} · только «Интернет продажи» · непроведённые заказы исключены'
        + ('; в реализациях пометка удаления не выгружена (ждёт выгрузку №2)' if any(u.startswith('⚠') for u in used) else '')) if S else '1С: выгрузки по менеджерам нет — ждёт выгрузку из BAS'
    M['score_formula'] = 'Итог = оценка звонков Binotel × (1 − (отказы + возвраты) ÷ заказы менеджера); отказ/возврат — по «Состояние» заказа и документам «Возврат от покупателя» из 1С'
    M['stale_note'] = '' if H else f'HelpCrunch W{n} не найден'
    json.dump(B, open(J, 'w'), ensure_ascii=False, indent=1)
    print('managers →', M['week'], '| missed', C['missed'], '| 1С', 'есть' if S else 'нет')

if __name__ == '__main__':
    main()
