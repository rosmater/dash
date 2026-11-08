#!/usr/bin/env python3
"""Informe / Plan → «Gastos $$$» → блок «pagos a modelos (OKX)» (AA:AE) → src/of_payouts_week.json.
HARD Rost 2026-11-08 t685u/t688u: расход = только строки с заполненным «monto USDT»; пусто = ещё не платили.
Вход: CSV блока AA:AE как отдаёт Sheets read_range (FORMATTED_VALUE), по умолчанию src/of_payouts_raw/gastos_AA_AE.csv.
Запуск: python3 src/ingest_of_payouts.py [path.csv] [--as-of YYYY-MM-DD]
Правило полей: /home/box/contacts/knowledge/rules/of-payouts-week-dash-fields.md"""
import csv, json, os, re, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
SHEET_ID = '1KeEduRnb9v82516RFJYSTayi9vUM-t4cgU0Yo9YlhtQ'
args = [a for a in sys.argv[1:] if not a.startswith('--')]
inp = args[0] if args else os.path.join(HERE, 'of_payouts_raw', 'gastos_AA_AE.csv')
as_of = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--as-of=')), datetime.date.today().isoformat())
OUT = os.path.join(HERE, 'of_payouts_week.json')

# не выплаты моделям: пополнения кошелька, офис, фотограф, расходы на съёмку/производство
SKIP_MODEL = re.compile(r'^\s*(ros|oficina|todas)\b|camar[oó]graf|prima\b', re.I)
SKIP_COMMENT = re.compile(r'ingreso|oficina|hij?a?bs|hijab|airbnb|uber|transporte|maquill|pasaje|ropa|vestuario|wardrobe|almuerzo|compra|accidentad', re.I)

def num(s):
    s = (s or '').strip().replace('\u00a0', '').replace(' ', '')
    if not s: return None
    if ',' in s: s = s.replace('.', '').replace(',', '.')
    try: return float(s)
    except ValueError: return None

def pdate(s):
    m = re.fullmatch(r'\s*(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})\s*', s or '')
    if not m: return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100: y += 2000
    try: return datetime.date(y, mo, d)
    except ValueError: return None

rows = list(csv.reader(open(inp, encoding='utf-8')))
hdr = next(i for i, r in enumerate(rows) if r and r[0].strip().lower() == 'fecha')
data = []
for i, r in enumerate(rows[hdr + 1:], start=hdr + 2):  # i = строка блока (в CSV), ≈ строка листа
    r = (r + [''] * 5)[:5]
    if not any(c.strip() for c in r): continue
    data.append(dict(row=i, date=pdate(r[0]), model=r[1].strip(), cop=num(r[2]), comment=r[3].strip().replace('\n', ' '), usdt=num(r[4])))
# строка без даты берёт дату следующей датированной строки (даты в блоке пишут группами по дню выплат)
nxt = None
for x in reversed(data):
    if x['date']: nxt = x['date']
    elif nxt: x['date'] = nxt; x['date_inferred'] = True

weeks, skipped, unpaid = {}, [], []
for x in data:
    if not x['date']: continue
    mon = x['date'] - datetime.timedelta(days=x['date'].weekday())
    k = 'W:' + mon.isoformat()
    if SKIP_MODEL.search(x['model']) or SKIP_COMMENT.search(x['comment']):
        if x['usdt']: skipped.append(dict(week=k, row=x['row'], date=x['date'].isoformat(), model=x['model'], comment=x['comment'], usdt=x['usdt']))
        continue
    w = weeks.setdefault(k, dict(usdt=0.0, cop=0.0, cop_for_rate=0.0, usdt_for_rate=0.0, n=0, unpaid_n=0, unpaid_cop=0.0, rows=[]))
    if not x['usdt']:
        if x['cop']: w['unpaid_n'] += 1; w['unpaid_cop'] += x['cop']
        continue
    w['usdt'] += x['usdt']; w['n'] += 1
    if x['cop']:
        w['cop'] += x['cop']; w['cop_for_rate'] += x['cop']; w['usdt_for_rate'] += x['usdt']
    w['rows'].append(dict(row=x['row'], date=x['date'].isoformat(), model=x['model'], comment=x['comment'], cop=x['cop'], usdt=x['usdt'], **({'date_inferred': True} if x.get('date_inferred') else {})))
out = {}
for k, w in sorted(weeks.items()):
    rate = round(w['cop_for_rate'] / w['usdt_for_rate'], 1) if w['usdt_for_rate'] else None
    out[k] = dict(usdt=round(w['usdt'], 2), cop=round(w['cop']), rate=rate, n=w['n'], unpaid_n=w['unpaid_n'], unpaid_cop=round(w['unpaid_cop']), rows=w['rows'])
json.dump(dict(as_of=as_of, src=f'Informe / Plan · Gastos $$$ · pagos a modelos (OKX) AA:AE · https://docs.google.com/spreadsheets/d/{SHEET_ID}',
               rule='расход = строки с monto USDT; пустой USDT не считаем; ingreso/oficina/камера/съёмка исключены; неделя = пн даты выплаты (Bogotá)',
               weeks=out, skipped=skipped), open(OUT, 'w'), ensure_ascii=False, indent=1)
print(f'{OUT}: {len(out)} weeks; skipped {len(skipped)} non-model rows with USDT')
for k, w in list(out.items())[-8:]:
    print(k, w['usdt'], 'USDT', w['cop'], 'COP', 'rate', w['rate'], 'n', w['n'], 'unpaid', w['unpaid_n'], w['unpaid_cop'])
