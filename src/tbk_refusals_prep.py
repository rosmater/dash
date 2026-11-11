#!/usr/bin/env python3
"""Rost t6007u: база «TBK — отказы и возвраты (база)» (Google Sheet zayavki.ua, не расшарена):
https://docs.google.com/spreadsheets/d/1L6san72d614ndqbihmpuFZeu-ERxzkeutl8HmHjtMzg  · вкладка «База»
Первая загрузка 11.11: 442 строки (интернет-заказы 01.10–08.11, отказ 311 / возврат 131), журнал = 442 номера.
Колонки: дата | № заказа | сайт/канал | менеджер | сумма | тип | причина | неделя | источник (файл 1С) | добавлено

Append-only + дедуп по № заказа (Sheets пишется только через MCP-коннектор, поэтому 2 шага):
  1) агент: read_range spreadsheetId=… sheet=«База» cells=B:B → сохранить CSV в файл (напр. /tmp/refusals_b.csv)
  2) python3 src/tbk_refusals_prep.py --existing /tmp/refusals_b.csv
       → /workspace/tbk-1c/refusals_to_append.json  ({"rows": [[…10 колонок…], …]}, только новых номеров)
  3) агент: append_rows sheet=«База» values=<rows>  (insertRows=true)
  4) python3 src/tbk_refusals_prep.py --commit   → номера в локальный журнал /workspace/tbk-1c/refusals_ledger.json
Ничего не удаляет и не переписывает. Причина = Комментарий / Причина из документа; нет колонки → «(нет поля в выгрузке)».
"""
import datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tbk_1c_orders as O
LEDGER = '/workspace/tbk-1c/refusals_ledger.json'
OUT = '/workspace/tbk-1c/refusals_to_append.json'

def key(n): return ''.join(str(n).split()).upper()

def main():
    led = json.load(open(LEDGER)) if os.path.exists(LEDGER) else {'nums': []}
    if '--commit' in sys.argv:
        p = json.load(open(OUT)); led['nums'] = sorted(set(led['nums']) | {key(r[1]) for r in p['rows']})
        json.dump(led, open(LEDGER, 'w'), ensure_ascii=False, indent=1); print('ledger', len(led['nums'])); return
    seen = set(led['nums'])
    if '--existing' in sys.argv:
        for ln in open(sys.argv[sys.argv.index('--existing') + 1], encoding='utf-8'):
            v = ln.strip().strip('"')
            if v and v != '№ заказа': seen.add(key(v))
    rows, now = [], datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for d in sorted(O.docs(), key=lambda x: (x['date'], x['num'])):
        t = O.outcome(d)
        if not t or not d['num'] or key(d['num']) in seen: continue
        if d['kind'] == 'order' and not O.is_im(d): continue  # только интернет-заказы
        seen.add(key(d['num'])); y, w, _ = d['date'].isocalendar()
        reason = ' | '.join(x for x in [d['reason'].replace('\n', ' / ') if d['reason'] else ('(комментарий пуст)' if d['has_reason_col'] else '(нет поля в выгрузке)'), f"ТТН: {d['ttn'].strip('; ')}" if d.get('ttn') else ''] if x)
        rows.append([d['date'].isoformat(), d['num'], d['channel'], d['manager'], d['sum'], t, reason, f'{y}-W{w:02d}', d['file'], now])
    json.dump({'rows': rows}, open(OUT, 'w'), ensure_ascii=False, indent=1)
    print('to append', len(rows), '→', OUT)

if __name__ == '__main__':
    main()
