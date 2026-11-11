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
MAP_1C = {  # только однозначные (среди «Интернет продажи» одна Екатерина и одна Елизавета; Саша — нет Александры в ИМ)
    'Ткаченко Екатерина': 'Катя',
    'Теслина Елизавета': 'Ліза',
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
    people = [dict(name=k, pct=v['avg'], calls=v['scored'], bad=v['bad']) for k, v in S.items() if k != 'Все']
    return dict(total=total, scored=S['Все']['scored'], of=ge20, inc=inc, out=out, missed=len(missed),
                missed_note=(f"пропущенных {len(missed)} с {len({x['ph'] for x in missed})} номеров · перезвонили {sum(1 for x in missed if x.get('cb_by'))}"
                             + (f" · пик {peak[0][8:10]}.{peak[0][5:7]} — {peak[1]}" if peak else '')),
                people=people)

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
    if '--week' in sys.argv: W = [int(sys.argv[sys.argv.index('--week') + 1])]
    n = max(x for x in W if wk_ok(x))
    a, b = week_dates(n)
    B = json.load(open(J)); M = B['managers']
    C = binotel(n); H = hc(n); P = hc(n - 1)
    M['week'] = f"W{n} · {a:%d.%m}–{b:%d.%m}"
    M['period'] = [a.isoformat(), b.isoformat()]
    M['calls'] = {**M.get('calls', {}), **C}
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
