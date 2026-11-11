#!/usr/bin/env python3
"""Rost t6016u: статистика базы «TBK — отказы и возвраты» → src/tbk_blocks.json managers.refusals.
Источник: Google Sheet (zayavki.ua) вкладка «База» — снимок CSV /workspace/tbk-1c/refusals_base_snapshot.csv
(агент: read_range «База» A:I UNFORMATTED → CSV; лист читается только через MCP-коннектор).
Знаменатель % = интернет-заказы 1С («Заказы покупателей», только «Интернет продажи», проведённые) за тот же период — src/tbk_1c_orders.py.
Причины: комментарий 1С сгруппирован по ключевым словам (не классификация менеджера). Ничего не выдумывает: нет данных → None.
"""
import csv, collections, datetime, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tbk_1c_orders as O
J = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tbk_blocks.json')
SNAP = '/workspace/tbk-1c/refusals_base_snapshot.csv'
URL = 'https://docs.google.com/spreadsheets/d/1L6san72d614ndqbihmpuFZeu-ERxzkeutl8HmHjtMzg/edit'
CAT = [('Недозвон / недоступен / неверный номер', r'недоз|недоступ|неправ\w* ном|не бер'),
       ('Не оплачен онлайн (Rozetka Pay / WayForPay / Пром-оплата)', r'вей\s*фо|wayfor|розетка\s*пей|роз\s*пей|пром-оплат|оплачен'),
       ('Переписка в Viber / чате Розетки без ответа', r'вайб|\bвб\b|viber|чат розетк'),
       ('Комментарий пуст', r'^\(комментарий пуст\)'),]
def cat(x):
    x = x.split('| ТТН')[0].strip().lower()
    for n, rx in CAT:
        if re.search(rx, x): return n
    return 'Другое (адрес, товар, прочее)'
WHO = {'Ткаченко Екатерина': 'Катя', 'Теслина Елизавета': 'Ліза', 'Плотницкая Жанна': 'Женя (Плотницкая Жанна)'}
def d_of(v):
    try: return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(v)))
    except ValueError: return datetime.date.fromisoformat(str(v)[:10])

def main():
    if not os.path.exists(SNAP): print('нет снимка', SNAP); return
    R = list(csv.DictReader(open(SNAP, encoding='utf-8')))
    for r in R: r['d'] = d_of(r['дата']); r['s'] = float(r['сумма']) if str(r['сумма']).strip() else None
    orders = [d for d in O.docs() if d['kind'] == 'order' and O.is_im(d)]
    o_lo, o_hi = min(d['date'] for d in orders), max(d['date'] for d in orders)
    def per(label, a, b):
        X = [r for r in R if a <= r['d'] <= b]; on = sum(1 for d in orders if a <= d['date'] <= b) if a >= o_lo and b <= o_hi else None
        osum = round(sum(d['sum'] or 0 for d in orders if a <= d['date'] <= b)) if on else None
        out = dict(label=label, orders=on, orders_sum=osum)
        for t in ('отказ', 'возврат'):
            Y = [r for r in X if r['тип'] == t]
            out[t] = dict(n=len(Y), pct=round(len(Y) / on * 100, 1) if on else None, sum=round(sum(r['s'] or 0 for r in Y)), no_sum=sum(1 for r in Y if r['s'] is None))
        out['rozetka_refused'] = sum(1 for r in X if r['тип'] == 'отказ' and r['сайт/канал'] == 'Rozetka')
        out['rozetka_orders'] = sum(1 for d in orders if a <= d['date'] <= b and d['channel'].startswith('Rozetka')) if on else None
        return out
    weeks = sorted({r['неделя'] for r in R})
    P = []
    for w in weeks[-4:]:
        y, n = map(int, w.split('-W')); a = datetime.date.fromisocalendar(y, n, 1); P.append(per(f'W{n} {a:%d.%m}', a, a + datetime.timedelta(days=6)))
    P.append(per('окт', datetime.date(2026, 10, 1), datetime.date(2026, 10, 31)))
    lo, hi = min(r['d'] for r in R), max(r['d'] for r in R)
    tot = per(f'всего {lo:%d.%m}–{hi:%d.%m}', lo, hi)
    top = collections.Counter(cat(r['причина']) for r in R if r['тип'] == 'отказ').most_common()
    topr = collections.Counter(cat(r['причина']) for r in R if r['тип'] == 'возврат').most_common(3)
    ch = collections.Counter(r['сайт/канал'] for r in R if r['тип'] == 'отказ').most_common(5)
    mg = collections.Counter(WHO.get(r['менеджер'], r['менеджер']) for r in R if r['тип'] == 'отказ').most_common(5)
    B = json.load(open(J)); B['managers']['refusals'] = dict(url=URL, title='База отказов и возвратов', rows=len(R), span=[lo.isoformat(), hi.isoformat()],
        periods=P, total=tot, top_refusal=top, top_return=topr, by_channel=ch, by_manager=mg,
        orders_span=[o_lo.isoformat(), o_hi.isoformat()],
        note='Источник: GSheet «База» (из 1С: «Состояние» заказа + «Возвраты от покупателей»); % — от интернет-заказов 1С за период; причины — по ключевым словам комментария 1С. Возвраты последних недель неполные (возврат приходит позже отказа).')
    # Rost t6030u: Розетка — отмены из кабинета продавца (снимок агента), 1С — только справка для сверки
    RZ = '/workspace/tbk-dash-audit/rozetka_cancellations.json'
    if os.path.exists(RZ):
        z = json.load(open(RZ)); o = z.get('2026-10') or {}; nv = z.get('2026-11-01_10') or {}
        B['marketplaces']['rozetka_cancel'] = dict(src='кабинет продавца Rozetka (аналитика + «Неуспешные»), снято 11.11',
            periods=[dict(label='окт', orders=o.get('orders'), cancelled=o.get('cancelled'), pct=o.get('cancelled_pct'), sum=o.get('cancelled_sum_uah'), orders_sum=o.get('orders_sum_uah')),
                     dict(label='01–10.11', orders=nv.get('orders'), cancelled=nv.get('cancelled_est'), pct=nv.get('cancelled_pct'), approx=True, processing_pct=nv.get('in_processing_pct'))],
            reasons=sorted([[k, v] for k, v in (o.get('reasons') or {}).items() if v], key=lambda kv: -kv[1]))
    json.dump(B, open(J, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(dict(P=P, tot=tot, top=top, ch=ch, mg=mg), ensure_ascii=False))
if __name__ == '__main__': main()
