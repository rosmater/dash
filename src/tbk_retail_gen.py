#!/usr/bin/env python3
"""Rost t5962u 11.11: Розница → все магазины + подблок Киев + подблок Франшизы.
Источники (только реальные цифры, нет → null «—»):
 - 1С/BAS «Динамика доходов и расходов» авг–окт 2026 (USD): knowledge/tbk-1c-reports/data/2026-10/05_dinamika_doh_rash_2026-08_10.xlsx
 - дебиторка по франшизам: knowledge/debitorka-weekly/history/clients.json
 - Центр «Кальяны» по неделям: kalyan-weekly/2026-11-02-EXTRACT.md (+ 2026-10-26 для единиц)
Патчит src/tbk_blocks.json → retail.all / retail.kyiv / retail.franchise.
"""
import json, os, openpyxl
K = '/home/box/contacts/knowledge'
X = K + '/tbk-1c-reports/data/2026-10/05_dinamika_doh_rash_2026-08_10.xlsx'
CL = K + '/debitorka-weekly/history/clients.json'
J = os.path.join(os.path.dirname(__file__), 'tbk_blocks.json')
ws = openpyxl.load_workbook(X, data_only=True).active
rows = list(ws.iter_rows(values_only=True))
lv = [ws.row_dimensions[i + 1].outline_level for i in range(len(rows))]
r2 = lambda v: None if v is None else round(float(v), 2)

def block(i):
    r = rows[i]
    rec = {'inc': [r2(r[c]) for c in (2, 8, 14)], 'res': [r2(r[c]) for c in (6, 12, 18)], 'rev': [None] * 3, 'cogs': [None] * 3}
    for j in range(i + 1, len(rows)):
        if lv[j] <= lv[i]: break
        if lv[j] == lv[i] + 1 and rows[j][0] == 'Выручка от продаж': rec['rev'] = [r2(rows[j][c]) for c in (2, 8, 14)]
        if lv[j] == lv[i] + 1 and rows[j][0] == 'Себестоимость продаж': rec['cogs'] = [r2(rows[j][c]) for c in (4, 10, 16)]
    rec['gp'] = [None if a is None or b is None else round(a - b, 2) for a, b in zip(rec['rev'], rec['cogs'])]
    return rec

shops, tot, fr, opt = [], None, None, None
for i, r in enumerate(rows):
    a = r[0]
    if not isinstance(a, str): continue
    if lv[i] == 0 and a.strip() == 'Розничные продажи': tot = block(i)
    elif lv[i] == 1 and a.endswith('(Розничные продажи)'):
        b = block(i); b['name'] = a.replace('(Розничные продажи)', '').replace('Магазин ', '').strip(); shops.append(b)
    elif lv[i] == 0 and a.strip() == 'Франшизные магазины': fr = block(i)
    elif lv[i] == 1 and a.strip() == 'Дистрибьюция (Оптовые продажи)': opt = block(i)
sell = [s for s in shops if (s['rev'][2] or 0) > 0]
kyiv = [s for s in shops if s['name'].startswith('Киев')]
for s in kyiv: s['name'] = s['name'].replace('Киев ', '').replace('"', '«', 1).replace('"', '»', 1)
sumv = lambda L, k: [round(sum((x[k][m] or 0) for x in L), 2) if any(x[k][m] is not None for x in L) else None for m in range(3)]
cl = json.load(open(CL))
col = cl['analyzed_week']
FR_NAMES = ['Магазин Черемушки Одесса К1', 'Магазин Черемушки Одесса Т2', 'Магазин Киев', 'Магазин Кривой Рог', 'Магазин Измаил']
stores = []
for nm in FR_NAMES:
    c = cl['clients'].get(nm)
    if not c: continue
    am = c['amounts']; ks = list(am)
    stores.append({'name': nm.replace('Магазин ', ''), 'debt': am.get(col), 'prev': am[ks[-2]] if len(ks) > 1 else None})
B = json.load(open(J))
R = B['retail']
R['months'] = ['авг', 'сен', 'окт']
R['all'] = {'rev': tot['inc'], 'res': tot['res'], 'shops': len(sell), 'gp': sumv(shops, 'gp')}
def _city(s):
    return 'Киев' if any(s is k for k in kyiv) else 'Одесса'
odesa = [s for s in sell if not any(s is k for k in kyiv)]
# Rost t5982u: «Розничные точки» — только свои точки без Киева (франшизы в рознице 1С и так отдельным направлением)
_own = [s for s in shops if not any(s is k for k in kyiv)]
R['stores'] = sorted([{'name': s['name'].replace('"', '«', 1).replace('"', '»', 1), 'rev': s['rev'], 'gp': s['gp'], 'res': s['res']} for s in _own], key=lambda x: -(x['rev'][2] or 0))
R['stores_total'] = {'rev': sumv(_own, 'rev'), 'gp': sumv(_own, 'gp'), 'res': sumv(_own, 'res')}
R.pop('odesa', None)
_unused_odesa = {'shops': sorted([{'name': s['name'].replace('"', '«', 1).replace('"', '»', 1), 'rev': s['rev'], 'gp': s['gp'], 'res': s['res']} for s in odesa], key=lambda x: -(x['rev'][2] or 0)),
              'total': {'rev': sumv(odesa, 'rev'), 'gp': sumv(odesa, 'gp'), 'res': sumv(odesa, 'res')}}
R['kyiv'] = {'shops': [{k: s[k] for k in ('name', 'rev', 'gp', 'res')} for s in kyiv],
             'total': {'rev': sumv(kyiv, 'rev'), 'gp': sumv(kyiv, 'gp'), 'res': sumv(kyiv, 'res')}}
R['franchise'] = {'rev': fr['rev'], 'gp': fr['gp'], 'res': fr['res'], 'debt_col': col.replace('на ', ''), 'stores': stores,
                  'debt_total': sum(s['debt'] or 0 for s in stores)}
# Rost t6145u/t6170u: франшизные магазины по точкам — из BAS OData (src/tbk_franchise_1c.json), не терять при перегенерации
_FJ = os.path.join(os.path.dirname(__file__), 'tbk_franchise_1c.json')
if os.path.exists(_FJ):
    _F = json.load(open(_FJ)); _sh = []
    for p in _F['points']:
        _sh.append({'name': p['name'], 'rev': p['rev'], 'gp': [None if a is None or c is None else round(a - c, 2) for a, c in zip(p['rev'], p['cogs'])], 'res': [None] * 3})
    _sh.sort(key=lambda x: -(x['rev'][2] or 0))
    R['franchise']['shops'] = _sh
    R['franchise']['shops_total'] = {'rev': sumv(_sh, 'rev'), 'gp': sumv(_sh, 'gp'), 'res': fr['res']}
    R['franchise']['shops_src'] = _F['src']
R['month_at'] = '10.11'
if opt: B['opt']['sales_months'] = {'months': ['авг', 'сен', 'окт'], 'rev': opt['rev'], 'gp': opt['gp'], 'res': opt['res']}
json.dump(B, open(J, 'w'), ensure_ascii=False, indent=2)
print('retail: shops', len(sell), 'stores', len(R['stores']), R['stores_total'], 'kyiv', len(kyiv), 'franchise stores', len(stores), 'debt', R['franchise']['debt_total'])
