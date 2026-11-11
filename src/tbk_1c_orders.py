"""Rost t6005u/t6007u: разбор xlsx-выгрузок списков документов BAS (Заказы покупателей / Расходные накладные /
Возвраты от покупателей) из /workspace/tbk-1c/share-mgr/. Только чтение; документы с пометкой удаления отбрасываются.
docs() → [dict(kind, date, num, manager, sum, state, reason, channel, file)]
kind: 'order' | 'sale' | 'return'  (по имени файла; см. tbk_managers_1c_STEPS.md)."""
import datetime, glob, os, re
SHARE = '/workspace/tbk-1c/share-mgr'
REFUSE_RX = re.compile(r'отказ|отмен|скасов|відмов|анул|не забр|не выкуп|не викуп', re.I)
RETURN_RX = re.compile(r'возврат|поверн', re.I)

def kind_of(fn):
    b = os.path.basename(fn).lower()
    if re.search(r'возврат|vozvrat|return|povern', b): return 'return'
    if re.search(r'заказ|zakaz|order', b): return 'order'
    if re.search(r'реализ|realiz|расход|rashod|накладн|nakladn|sale|prodazh', b): return 'sale'
    return None

def _num(v):
    if v in (None, ''): return None
    if isinstance(v, (int, float)): return float(v)
    s = re.sub(r'[^\d,.\-]', '', str(v)).replace(',', '.')
    try: return float(s)
    except ValueError: return None

def _date(v):
    if isinstance(v, datetime.datetime): return v.date()
    if isinstance(v, datetime.date): return v
    m = re.match(r'\s*(\d{2})\.(\d{2})\.(\d{2,4})', str(v or ''))
    if not m: return None
    y = int(m.group(3)); y += 2000 if y < 100 else 0
    return datetime.date(y, int(m.group(2)), int(m.group(1)))

def _rows(fn):
    if fn.lower().endswith('.xlsx'):
        import openpyxl
        return [list(r) for r in openpyxl.load_workbook(fn, data_only=True).active.iter_rows(values_only=True)]
    if fn.lower().endswith('.xls'):
        import xlrd
        sh = xlrd.open_workbook(fn).sheet_by_index(0)
        return [sh.row_values(i) for i in range(sh.nrows)]
    if fn.lower().endswith(('.csv', '.txt')):
        import csv
        t = open(fn, encoding='utf-8-sig', errors='replace').read()
        return list(csv.reader(t.splitlines(), delimiter=';' if t.count(';') > t.count(',') else ','))
    return []

def headers(fn):
    rows = _rows(fn)
    for i, r in enumerate(rows[:40]):
        h = [str(x or '').strip() for x in r]
        if any(x.lower().startswith('дата') for x in h) and any(re.match(r'(ответствен|менеджер|автор)', x.lower()) for x in h):
            return i, h, rows
    return None, None, rows

def docs(share=SHARE):
    out = []
    for fn in sorted(glob.glob(f'{share}/*')):
        k = kind_of(fn)
        if not k: continue
        hi, h, rows = headers(fn)
        if hi is None: continue
        L = [x.lower() for x in h]
        def ci(*ps):
            for p in ps:  # приоритет префиксов по порядку; внутри — точное совпадение, потом «начинается с»
                for i, x in enumerate(L):
                    if x == p: return i
                for i, x in enumerate(L):
                    if x.startswith(p): return i
            return None
        cd, cn, cm = ci('дата'), ci('номер', '№'), ci('ответствен', 'менеджер', 'автор')
        cs = ci('сумма документа', 'сумма', 'сума')
        cdel = ci('пометка удал', 'позначка вилуч')
        cst = ci('состояние', 'стан')
        cfin = ci('вариант завершения')
        cpost = ci('проведен', 'проведено')
        cttn = ci('статус ттн')
        cop = ci('операция', 'вид операции')
        crs = [i for i, x in enumerate(L) if re.search(r'коммент|комент|причин', x)]
        cch = ci('подразделение', 'канал', 'источник', 'структурн')
        for r in rows[hi + 1:]:
            r = list(r) + [None] * (len(h) - len(r))
            d = _date(r[cd]) if cd is not None else None
            if not d or r[cm] in (None, '', '<Не указан>'): continue
            if k == 'sale' and cop is not None and r[cop] and 'возврат' in str(r[cop]).lower(): continue  # «Возврат поставщику» — не продажа
            if cdel is not None and str(r[cdel]).strip().lower() in ('да', 'true', '1', 'так', 'yes', 'истина'): continue
            # пометка удаления в списке не выгружается → непроведённые (а помеченные на удаление всегда непроведены) не считаем
            if cdel is None and cpost is not None and str(r[cpost]).strip().lower() in ('ні', 'нет', 'false', '0', 'no', 'ложь'): continue
            out.append(dict(kind=k, date=d, num=str(r[cn]).strip() if cn is not None and r[cn] is not None else '',
                            manager=str(r[cm]).strip(), sum=_num(r[cs]) if cs is not None else None,
                            state=str(r[cst]).strip() if cst is not None and r[cst] is not None else '',
                            reason=' | '.join(str(r[i]).strip() for i in crs if r[i] not in (None, '')),
                            channel=str(r[cch]).strip() if cch is not None and r[cch] is not None else '',
                            finish=str(r[cfin]).strip() if cfin is not None and r[cfin] is not None else '',
                            ttn=str(r[cttn]).strip() if cttn is not None and r[cttn] is not None else '',
                            file=os.path.basename(fn), has_reason_col=bool(crs), has_state_col=cst is not None,
                            has_del_col=cdel is not None, has_post_col=cpost is not None))
    return out

def outcome(d):
    """'отказ' | 'возврат' | None. BAS УНФ ТБК: Состояние «Возврат» → возврат; Вариант завершения «Отменен» → отказ."""
    if d['kind'] == 'return': return 'возврат'
    if d['kind'] != 'order': return None
    if RETURN_RX.search(d['state']): return 'возврат'
    if REFUSE_RX.search(d.get('finish') or ''): return 'отказ'
    return None

def is_im(d):
    return 'интернет' in (d.get('channel') or '').lower()
