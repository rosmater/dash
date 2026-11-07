#!/usr/bin/env python3
"""Пептиды: снимок продаж из GSheet «PEPTIDOS VENTAS» → src/peptides_sales.json.
Источник: 1VqMt81ZX1ZoSj4maK1o99xUPaDyqTvvEU1KxTw6kO9M, вкладка «Hoja 2» (gid 1025277545).
Как обновить (агент): коннектор Google Sheets (zayavki) read_range sheet="Hoja 2" cells="A1:M1000"
valueRenderOption=UNFORMATTED_VALUE → сохранить CSV в файл → python3 src/peptides_sync.py <file.csv> → bash src/build.sh → пуш.
Расходы: GSheet «Expensed Peso Saludable» 1-X24SE_ZfP7mXm9_WUFRwCo-H45ryI9R2yvYpOu-bIE вкладка «expenses» (бывш. «Лист1», gid 0; cells A1:E1000; колонка currency «$»=USD), read_range UNFORMATTED_VALUE
→ python3 src/peptides_sync.py --expenses <file.csv> (→ src/peptides_expenses.json).
Колонки: cliente numero, UNIDADES, Producto, vendedor, Fecha del pedido (serial), Precio, metodo de pago, ciudad, Notas, cuenta bancaria, comision, TOTAL.
Клиент (Rost 25.10, повторные продажи): пишем client = имя/@ник + маска телефона (…последние 4 цифры) и client_key = sha1(цифры телефона или @ник)[:10]
для склейки повторных; полный номер в снимок НЕ пишем. Notas → note.
Себестоимость (Rost 25.10): НЕ пишется в таблицы — build_data.py считает автоматом 100 000 COP × UNIDADES
для ЛЮБОГО продукта (киты и не-киты «15MG, 20MG»), Rost 25.10 ~10:05."""
import csv, sys, json, datetime, os, re, hashlib
B = datetime.date(1899, 12, 30)
if len(sys.argv) > 2 and sys.argv[1] == '--expenses':
    pass  # обработка ниже, после определения num/day
src = sys.argv[-1]
rows = list(csv.reader(open(src)))[1:]
def num(x):
    try: return float(str(x).replace(',', '').strip())
    except Exception: return None
def day(x):
    n = num(x)
    if n: return (B + datetime.timedelta(days=int(n))).isoformat()
    for f in ('%d/%m/%Y', '%Y-%m-%d', '%d.%m.%Y'):
        try: return datetime.datetime.strptime(str(x).strip(), f).date().isoformat()
        except Exception: pass
if sys.argv[1] == '--expenses':
    # GSheet «Expensed Peso Saludable» 1-X24SE_ZfP7mXm9_WUFRwCo-H45ryI9R2yvYpOu-bIE, «Лист1»: Date, Name of expense, COP spent, Payer.
    # Сумма с «$» = USD (напр. «175,5$»), иначе COP.
    # С 25.10 ~09:05 (правка Rost): вкладка «expenses», колонки Date, Name of expense, COP spent, currency («$»/«COP»), Payer.
    hdr = [h.strip().lower() for h in list(csv.reader(open(src)))[0]]
    has_cur = 'currency' in hdr
    # С 25.10 ~10:00 (правка Rost): + колонка «Peso» (сумма уже в COP) → берём её как COP; Payer — по имени колонки.
    # Дата может быть диапазоном «02.09-15.10» → дата = конец диапазона (год 2026), диапазон пишем в label.
    iP = hdr.index('peso') if 'peso' in hdr else None
    iPay = hdr.index('payer') if 'payer' in hdr else (4 if has_cur else 3)
    def rday(x):
        d = day(x)
        if d: return d, ''
        m = re.match(r'\s*(\d{1,2})[./](\d{1,2})\s*[-–]\s*(\d{1,2})[./](\d{1,2})\s*$', str(x))
        if m: return datetime.date(2026, int(m.group(4)), int(m.group(3))).isoformat(), f' ({m.group(1)}.{m.group(2)}–{m.group(3)}.{m.group(4)})'
        return None, ''
    costs = []
    for r in rows:
        r = (r + [''] * 8)[:8]
        if not r[1].strip() or r[0].strip().lower() == 'total': continue
        dt, rng = rday(r[0])
        if not dt: continue
        payer = r[iPay].strip()
        if iP is not None and num(r[iP]) is not None:
            v, cur = num(r[iP]), 'COP'
        else:
            a = str(r[2]).strip()
            if has_cur:
                c = r[3].strip().upper(); usd = '$' in a or c in ('$', 'USD', 'US$')
            else:
                usd = '$' in a
            v = num(a.replace('$', '').replace(' ', '').replace(',', '.') if '$' in a else a); cur = 'USD' if usd else 'COP'
        if v is None: continue
        costs.append(dict(date=dt, label=r[1].strip().rstrip(',$').strip() + rng, amount=v, cur=cur, payer=payer))
    out = dict(src='GSheet «Expensed Peso Saludable» 1-X24SE_ZfP7mXm9_WUFRwCo-H45ryI9R2yvYpOu-bIE, вкладка «expenses» (gid 0)',
               fetched_at=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), costs=costs)
    json.dump(out, open(os.path.join(os.path.dirname(__file__), 'peptides_expenses.json'), 'w'), ensure_ascii=False, indent=1)
    print(len(costs), 'расходов'); sys.exit()
def client(raw):
    raw = str(raw).strip()
    if not raw: return '', ''
    hm = re.search(r'@[\w.]+', raw)
    dg = re.sub(r'\D', '', raw)
    if len(dg) >= 7:
        dg10 = dg[-10:]  # без кода страны 57
        name = re.sub(r'[+\d\s/()-]+', ' ', raw).strip(' /·-')
        lab = (name + ' · ' if name else '') + '…' + dg10[-4:]
        key = dg10
    else:
        lab = hm.group(0) if hm else raw
        key = lab.lower()
    return lab, hashlib.sha1(key.encode()).hexdigest()[:10]
# Rost 25.10 + 04.11: колонки по заголовку (в Hoja 2 появилась «fecha primer contacto» между vendedor и Fecha del pedido).
_hdr_raw = list(csv.reader(open(src)))[0]
_hdr = [h.strip().lower() for h in _hdr_raw]
def col(*names):
    for n in names:
        n = n.lower()
        for i, h in enumerate(_hdr):
            if n == h or n in h: return i
    return None
def col_any(preds):
    for i, h in enumerate(_hdr):
        if any(p(h) for p in preds): return i
    return None
I_CLIENT = col('cliente numero', 'cliente') or 0
I_UNITS = col('unidades') or 1
I_PROD = col('producto') or 2
I_CH = col('vendedor') or 3
I_DATE = col('fecha del pedido') or 4
I_PRICE = col('precio') or 5
I_PAY = col('metodo de pago', 'método de pago') or 6
I_CITY = col('ciudad') or 7
I_NOTE = col('notas') or 8
I_ACC = col('cuenta bancaria', 'cuenta') or 9
I_COM = col('comision', 'comisión') or 10
I_TOT = col('total') or 11
FC = col_any([lambda h: 'primera' in h or 'primer contacto' in h or 'first contact' in h or 'первой' in h])
sales = []
for r0 in rows:
    r = r0 + [''] * 16
    prod = str(r[I_PROD]).strip()
    if not prod or num(r[I_PRICE]) is None or not day(r[I_DATE]): continue
    cl, ck = client(r[I_CLIENT])
    sales.append(dict(
        client=cl, client_key=ck, note=str(r[I_NOTE]).strip(), date=day(r[I_DATE]),
        units=int(num(r[I_UNITS]) or 1), product=prod, channel=str(r[I_CH]).strip(),
        price=int(num(r[I_PRICE])), pay=str(r[I_PAY]).strip(), city=str(r[I_CITY]).strip(),
        account=str(r[I_ACC]).strip(), commission=int(num(r[I_COM]) or 0),
        total=int(num(r[I_TOT]) or num(r[I_PRICE])),
        first_contact=(day(r0[FC]) if FC is not None and FC < len(r0) and str(r0[FC]).strip() else None)))
out = dict(src='GSheet «PEPTIDOS VENTAS» 1VqMt81ZX1ZoSj4maK1o99xUPaDyqTvvEU1KxTw6kO9M, вкладка «Hoja 2» (gid 1025277545)',
           fetched_at=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), sales=sales,
           first_contact_col=(_hdr_raw[FC] if FC is not None else None))
json.dump(out, open(os.path.join(os.path.dirname(__file__), 'peptides_sales.json'), 'w'), ensure_ascii=False, indent=1)
print(len(sales), 'продаж, выручка', sum(s['price'] for s in sales))
