#!/usr/bin/env python3
"""Rost t5982u: «⏳ Зависшие авансы на товар» — 2-я вкладка «Поставщики» GSheet «Отчет по дебиторке».
Только разделы «…/залоги за товар» (предоплаты нам должны товар); «долг поставщику» и «(мы должны)» не берём.
Каждая сумма в своей валюте, итоги по валютам, между валютами не суммируем.
Вход: снимок вкладки (rows JSON), по умолчанию knowledge/debitorka-weekly/snapshots/suppliers-tab-*.json (последний)."""
import json, os, re, sys, glob
K = '/home/box/contacts/knowledge/debitorka-weekly/snapshots'
src = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob(K + '/suppliers-tab-*.json'))[-1]
rows = json.load(open(src))
J = os.path.join(os.path.dirname(__file__), 'tbk_blocks.json')
hdr = rows[2]
dcols = [(i, h.strip()) for i, h in enumerate(hdr) if re.fullmatch(r'\d\d\.\d\d\.\d{4}', h.strip())]
def num(s):
    s = (s or '').strip()
    if not s: return None
    owe = 'долж' in s.lower()
    m = re.match(r'^-?[\d\s\u00a0]+(?:[.,]\d+)?', s)
    if not m: return None
    v = float(m.group(0).replace(' ', '').replace('\u00a0', '').replace(',', '.'))
    return -v if owe else v
sec, items = None, []
CUR = {'грн': 'UAH', 'USD': 'USD', 'EUR': 'EUR', 'евро': 'EUR'}
for r in rows[3:]:
    name = (r[0] if r else '').strip()
    cur = (r[1] if len(r) > 1 else '').strip()
    if not name: continue
    if '/' in name and not cur: sec = name; continue
    if not cur or not sec or 'залоги' not in sec: continue
    vals = [(d, num(r[i] if i < len(r) else '')) for i, d in dcols]
    vals = [(d, v) for d, v in vals if v is not None]
    if not vals: continue
    last_d, last = vals[-1]
    if last <= 0: continue
    # сколько срезов подряд (с конца) сумма не уменьшалась
    weeks = 0
    for k in range(len(vals) - 1, 0, -1):
        if vals[k][1] >= vals[k - 1][1] - 0.005: weeks += 1
        else: break
    note_i = dcols[-1][0] + 1
    note = (r[note_i] if note_i < len(r) else '').strip()
    items.append({'name': name, 'cur': CUR.get(cur, cur), 'amt': round(last, 2), 'prev': round(vals[-2][1], 2) if len(vals) > 1 else None,
                  'weeks': weeks, 'note': note, 'dir': sec.split(' ')[0]})
items.sort(key=lambda x: (x['cur'] != 'UAH', -x['amt']))
tot = {}
for x in items: tot[x['cur']] = round(tot.get(x['cur'], 0) + x['amt'], 2)
B = json.load(open(J))
B['opt']['advances'] = {'title': 'Зависшие авансы на товар', 'col': dcols[-1][1][:5], 'items': items, 'totals': tot}
json.dump(B, open(J, 'w'), ensure_ascii=False, indent=2)
print('advances', len(items), tot, 'col', dcols[-1][1])
for x in items: print(' ', x['cur'], x['amt'], x['weeks'], x['name'])
