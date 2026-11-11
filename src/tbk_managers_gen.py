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
MAP_1C = {}

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
    """{имя: {'to': сумма, 'orders': n}} из xlsx в SHARE; None если выгрузки нет."""
    import openpyxl
    fs = sorted(glob.glob(f'{SHARE}/*.xlsx'))
    if not fs: return None, None
    out, used = {}, []
    for f in fs:
        kind = 'orders' if re.search(r'заказ|order', os.path.basename(f), re.I) else 'to' if re.search(r'реализ|расход|накладн|sale|prodazh', os.path.basename(f), re.I) else None
        if not kind: continue
        ws = openpyxl.load_workbook(f, data_only=True).active
        rows = list(ws.iter_rows(values_only=True)); hi = None
        for i, r in enumerate(rows[:30]):
            h = [str(x or '').strip().lower() for x in r]
            if any(x.startswith('ответствен') for x in h) and any(x.startswith('дата') for x in h): hi = i; break
        if hi is None: continue
        h = [str(x or '').strip().lower() for x in rows[hi]]
        ci = lambda p: next((k for k, x in enumerate(h) if x.startswith(p)), None)
        cd, cr, cs, cdel = ci('дата'), ci('ответствен'), ci('сумма'), ci('пометка удал')
        for r in rows[hi + 1:]:
            if cd is None or r[cd] is None or not r[cr]: continue
            if cdel is not None and str(r[cdel]).strip().lower() in ('да', 'true', '1', 'так', 'yes'): continue
            d = r[cd] if isinstance(r[cd], datetime.datetime) else None
            if d is None:
                m = re.match(r'(\d{2})\.(\d{2})\.(\d{4})', str(r[cd]))
                if not m: continue
                d = datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if not (a <= d.date() <= b): continue
            nm = MAP_1C.get(str(r[cr]).strip(), str(r[cr]).strip())
            o = out.setdefault(nm, {'to': None, 'orders': None})
            if kind == 'orders': o['orders'] = (o['orders'] or 0) + 1
            else:
                v = r[cs] if cs is not None else None
                v = float(str(v).replace('\xa0', '').replace(' ', '').replace(',', '.')) if v not in (None, '') else 0
                o['to'] = round((o['to'] or 0) + v, 2)
        used.append(os.path.basename(f))
    return (out if used else None), used

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
        p['to'] = x.get('to'); p['orders'] = x.get('orders')
    known = {p['name'] for p in M['calls']['people']}
    M['sales_1c_extra'] = [dict(name=k, **v) for k, v in (S or {}).items() if k not in known]
    M['sales_1c_src'] = ('1С/BAS: ' + ', '.join(used) + ' (без пометки удаления)') if S else '1С: выгрузки по менеджерам нет — ждёт выгрузку из BAS'
    M['stale_note'] = '' if H else f'HelpCrunch W{n} не найден'
    json.dump(B, open(J, 'w'), ensure_ascii=False, indent=1)
    print('managers →', M['week'], '| missed', C['missed'], '| 1С', 'есть' if S else 'нет')

if __name__ == '__main__':
    main()
