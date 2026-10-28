#!/usr/bin/env python3
"""Builds data.json for the dashboard mockup from the knowledge base (read-only).
Re-run: python3 src/build_data.py  (from /workspace/dashboard-mockup)"""
import csv, json, datetime, os, re
KB = '/home/box/contacts/knowledge'
OUT = os.path.join(os.path.dirname(__file__), '..', 'data.json')
MON = ['янв','фев','мар','апр','мая','июн','июл','авг','сен','окт','ноя','дек']
MONTH_NAMES = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']

def item(label, amount, cur, src, example=False, note=None):
    d = dict(label=label, amount=amount, cur=cur, src=src)
    if example: d['example'] = True
    if note: d['note'] = note
    return d

# ---------- calendar ----------
weeks = []
TODAY = datetime.date.today()
CUR_MON = TODAY - datetime.timedelta(days=TODAY.weekday())  # понедельник текущей недели
d = datetime.date(2026, 8, 10)
while d <= max(CUR_MON, datetime.date(2026, 10, 19)):
    e = d + datetime.timedelta(days=6)
    lab = f"{d.day}–{e.day} {MON[e.month-1]}" if d.month == e.month else f"{d.day} {MON[d.month-1]} – {e.day} {MON[e.month-1]}"
    weeks.append(dict(id=d.isoformat(), start=d.isoformat(), end=e.isoformat(), month=d.strftime('%Y-%m'),
                      iso=f"W{d.isocalendar()[1]}", label=lab))
    d += datetime.timedelta(days=7)
months = [dict(id=f"2026-{m:02d}", label=f"{MONTH_NAMES[m-1]} 2026") for m in range(1, max(10, TODAY.month if TODAY.year == 2026 else 12) + 1)]

# ---------- OF / 05services ----------
of_src = 'knowledge/05services-weekly/history.csv (stats/partner, «наш доход» по income-rules.md)'
rows = list(csv.DictReader(open(f'{KB}/05services-weekly/history.csv')))
of_periods, of_break = {}, []
by_week = {}
for r in rows:
    if r['week_start'] not in [w['id'] for w in weeks]:
        continue
    by_week.setdefault(r['week_start'], []).append(r)
RA130_WEEK = round(48.5 * 12 / 52, 2)  # фикс $48.50/мес → неделя
payout_src = 'knowledge/of-marketing-shared/irina-sunday/<дата>/report.md (база выплат с карточек CU, статус to do — не подтверждено)'
payouts = {  # неделя (пн) -> воскресный отчёт Ирины, который перечисляет выплаты понедельника
    '2026-09-14': '2026-09-20', '2026-09-21': '2026-09-27', '2026-09-28': '2026-10-04', '2026-10-05': '2026-10-11'}
for wk, rs in sorted(by_week.items()):
    partial = any(r['partial'] == 'yes' for r in rs)
    net = 0.0; gross = 0.0; fans = 0; table = []
    for r in sorted(rs, key=lambda x: x['ra']):
        n = RA130_WEEK if r['ra'] == 'RA130' else float(r['our_net'] or 0)
        g = float(r['income_usd'] or 0)
        net += n; gross += g; fans += int(float(r['fans'] or 0))
        table.append([r['ra'], round(g, 2), r['agency_pct'] if r['ra'] != 'RA130' else 'фикс', round(n, 2), int(float(r['fans'] or 0))])
    inc = [item('Наш доход 05services (сумма по моделям)', round(net, 2), 'USD', of_src)]
    exp = []
    if wk in payouts:
        exp.append(item('Выплаты моделям OFTV (Татьяна, Кэтрин, Лаура, Хулиана) — база с карточек', 2500000, 'COP', payout_src.replace('<дата>', payouts[wk]),
                        note='плановые суммы со статусом to do; факт оплаты не подтверждён'))
    of_periods['W:' + wk] = dict(status='partial' if partial else 'full', income=inc, expenses=exp,
        metrics={'Оборот моделей (gross), $': round(gross, 2), 'Новые фаны (нетто)': fans, 'Моделей в сборе': len(rs)},
        note=None if exp else 'Расходы (выплаты моделям) за эту неделю в базе не найдены')
    of_break.append(dict(period='W:' + wk, title='По моделям (05services)', columns=['Модель', 'Оборот $', '% агентства', 'Наш доход $', 'Фаны'], rows=table))

# ---------- Peptides ----------
pep_src_w = '/workspace/peptidos-week-2026-10-19/WEEK-SUMMARY.md'
pep_src_ads = 'knowledge/peso-saludable-wa-leads/ad-stats.md (скрины Meta от Rost 19.10)'
# Rost 25.10: источник продаж — GSheet «PEPTIDOS VENTAS» / Hoja 2 (снимок src/peptides_sales.json, обновляет агент через коннектор Sheets)
PEP = json.load(open(os.path.join(os.path.dirname(__file__), 'peptides_sales.json')))
PEPX = json.load(open(os.path.join(os.path.dirname(__file__), 'peptides_expenses.json')))
# Rost 25.10: расходы — GSheet «Expensed Peso Saludable» + комиссия продавца из таблицы продаж
# + себестоимость автоматом (Rost 25.10): 100 000 COP × units для ЛЮБОГО продукта (киты и не-киты, peptides_cogs.json).
# Реклама со скринов и ЗП Сары в расходы НЕ входят.
PEP_KIT_COGS = 100_000
def _is_kit(prod): p = (prod or '').lower(); return 'kit' in p or 'кит' in p
def _cogs(x): return PEP_KIT_COGS * int(x.get('units') or 0)  # Rost 25.10 ~10:05: и не-киты тоже
pep_costs = [dict(date=c['date'], label=c['label'] + (f" (платил {c['payer']})" if c.get('payer') else ''), amount=c['amount'], cur=c['cur'], src=PEPX['src'])
             for c in PEPX['costs']]
pep_ledger = dict(src=PEP['src'], fetched_at=PEP['fetched_at'], exp_src=PEPX['src'], exp_fetched_at=PEPX['fetched_at'], cur='COP',
  sales=[dict(date=x['date'], units=x['units'], product=x['product'], channel=x['channel'], city=x['city'], price=x['price'], commission=x['commission'], cogs=_cogs(x))
         for x in PEP['sales']],
  costs=pep_costs,
  note='Расходы = таблица расходов + комиссия продавца + себестоимость (100 000 COP/ед. автоматом на любой продукт, Rost 25.10). ЗП Сары не в расходах.')
def _wk(ds):
    d0 = datetime.date.fromisoformat(ds); return (d0 - datetime.timedelta(days=d0.weekday())).isoformat()
pep_periods = {}
def _pp(key):
    return pep_periods.setdefault(key, dict(status='full', income=[], expenses=[], metrics={'Продажи, шт.': 0}))
for x in pep_ledger['sales']:
    for key in ('W:' + _wk(x['date']), 'M:' + x['date'][:7]):
        r = _pp(key); r['metrics']['Продажи, шт.'] += 1
        r['income'].append(item(f"{x['date'][8:10]}.{x['date'][5:7]} {x['product']} × {x['units']} ({x['channel']}, {x['city'].title()})", x['price'], 'COP', PEP['src']))
        if x['commission']: r['expenses'].append(item(f"Комиссия продавца {x['date'][8:10]}.{x['date'][5:7]}", x['commission'], 'COP', PEP['src']))
        if x['cogs']: r['expenses'].append(item(f"Себестоимость ×{x['units']} {x['date'][8:10]}.{x['date'][5:7]}", x['cogs'], 'COP', 'авто: 100 000 COP × ед. любой продукт (Rost 25.10)'))
for c in pep_costs:
    for key in ('W:' + _wk(c['date']), 'M:' + c['date'][:7]): _pp(key)['expenses'].append(item(f"{c['date'][8:10]}.{c['date'][5:7]} {c['label']}", c['amount'], c['cur'], c['src']))
_cw = 'W:' + (TODAY - datetime.timedelta(days=TODAY.weekday())).isoformat()
for k, r in pep_periods.items():
    if k == _cw or k == 'M:' + TODAY.strftime('%Y-%m'): r['status'] = 'partial'
    r['note'] = 'Продажи — GSheet PEPTIDOS VENTAS (Hoja 2). ' + pep_ledger['note']
pep_break = [
  dict(period='W:2026-10-12', title='По дням (12–17.10)', columns=['День', 'Продажи', 'Первый ответ ≤15 мин', 'Непрочит. к вечеру'],
       rows=[['пн 12.10', 0, '0 из 3', 6], ['вт 13.10', '2 × 350 000', '4 из 5', 4], ['ср 14.10', 0, '5 из 5', 5],
             ['чт 15.10', '0 (+1 со слов Сары)', '15 из 15', 2], ['пт 16.10', 0, '0 из 3', 4], ['сб 17.10', '0 (опт 2 млн возвращён)', '1 из 2', 3]]),
  dict(period=None, title='Реклама Meta (факт со скринов)', columns=['Кампания', 'Период', 'Расход COP', 'Показы', 'Диалоги', 'Цена диалога'],
       rows=[['Пост «2º mes GRATIS 350.000»', '14–17.10', 98179, 3458, 10, 9818], ['Пост «Compra 1, lleva 2»', '5 дней, дата ?', 65602, 2936, 16, 4100]]),
]

# ---------- Peptides: мониторы (Rost 25.10: реклама Активные/Архив, повторные продажи, ответы) ----------
def _addm(d0, n):
    y, m = divmod(d0.month - 1 + n, 12); y += d0.year; m += 1
    import calendar as _cal
    return datetime.date(y, m, min(d0.day, _cal.monthrange(y, m)[1]))
def _ru(ds): return ds[8:10] + '.' + ds[5:7] + '.' + ds[:4]
# Повторные: 1-я покупка D0 → «пора» с D0+2 мес, дальше каждый месяц (D0+3, +4 …). ≥2 покупок → «повторные».
_by = {}
for x in PEP['sales']:
    k = x.get('client_key') or ''
    if k: _by.setdefault(k, []).append(x)
rep_buyers, due_now, upcoming = [], [], []
for k, xs in _by.items():
    xs = sorted(xs, key=lambda x: x['date']); d0 = datetime.date.fromisoformat(xs[0]['date'])
    n = 2
    while _addm(d0, n) <= TODAY: n += 1
    nxt = _addm(d0, n)  # ближайшее будущее касание
    last_due = _addm(d0, n - 1) if n > 2 else None  # последнее наступившее касание
    row = dict(client=xs[0]['client'], city=xs[0]['city'].title(), first=xs[0]['date'], last=xs[-1]['date'], purchases=len(xs),
               products=', '.join(x['product'] for x in xs), total=sum(x['price'] for x in xs), note=xs[0].get('note') or '', client_key=k,
               next_due=nxt.isoformat(), first_due=_addm(d0, 2).isoformat())
    if len(xs) >= 2: rep_buyers.append(row)
    elif last_due: row['due_since'] = last_due.isoformat(); row['touch'] = n - 2; due_now.append(row)
    else: upcoming.append(row)
upcoming.sort(key=lambda r: r['first_due']); due_now.sort(key=lambda r: r['due_since'])
pep_repeat = dict(rule='1-е касание через 2 мес после 1-й покупки, дальше каждый месяц (Rost 25.10)', today=TODAY.isoformat(),
                  repeat_buyers=rep_buyers, due_now=due_now, upcoming=upcoming, clients=len(_by),
                  src='GSheet PEPTIDOS VENTAS, колонка «cliente numero» (в снимке: имя/@ник + …4 последние цифры)')
# Реклама и ответы — живые снимки Пептида (Rost 25.10): /workspace/peptides-dash-monitors/{ads,replies}.json
# (Пептид собирает из IG Ad tools / ad-stats.md / ads-audience.md / WA-отчётов). Телефоны маскируем до …4 цифр.
_MON = '/workspace/peptides-dash-monitors'
def _j(n):
    try: return json.load(open(os.path.join(_MON, n)))
    except Exception: return {}
def _mask(t):
    return re.sub(r'\+?57\s?(\d{3})\s?(\d{3})(\d{4})', lambda m: '+57 ' + m.group(1) + ' …' + m.group(3), str(t or ''))
def _hm(x):
    x = str(x or ''); return x[:16].replace('T', ' ') if x[:2] == '20' else ('конец сент.' if 'late Sep' in x else 'дата ?')
_OBJ = {'Profile visits': 'Визиты профиля', 'Conversations (app)': 'Переписки (WA/DM)'}
_A, _R = _j('ads.json'), _j('replies.json')
def _ad(a, st):
    ss = a.get('stats_at_verify') or {}
    return dict(name=a.get('creative') or a.get('id'), account=a.get('account', ''), status=st,
                start=_hm(a.get('started_at') or a.get('launch_at') or a.get('start')), end=a.get('finishes_approx', ''),
                days=a.get('duration_days'), objective=next((v for k, v in _OBJ.items() if str(a.get('objective', '')).startswith(k)), a.get('objective', '')), audience=a.get('audience', ''),
                budget=a.get('budget_cop_total') or a.get('budget_cop'), day_budget=a.get('budget_cop_day'),
                spent=ss.get('spent_cop', a.get('spent_cop')), views=ss.get('views', a.get('views')),
                conversations=a.get('conversations'), profile_visits=ss.get('profile_visits', a.get('profile_visits')),
                cpc=a.get('cost_per_conversation_cop'), checked=_hm(ss.get('at')) if ss.get('at') else '', note=a.get('post_note', ''))
pep_ads = dict(active=[_ad(a, 'active') for a in _A.get('active', [])],
               scheduled=[_ad(a, 'scheduled') for a in _A.get('scheduled', [])],
               archive=[_ad(a, 'done') for a in _A.get('archive', [])],
               totals=_A.get('totals_archive'), summary=_A.get('archive_summary'), plan=_A.get('plan'), as_of=_hm(_A.get('as_of')), last_verify=_hm((_A.get('live_check') or {}).get('last_ig_verify')),
               stale=not (_A.get('live_check') or {}).get('phone_recheck_today', False),
               cron_failed=bool(_A.get('cron_failed') or (_A.get('live_check') or {}).get('cron_failed')),
               src='Пептид: /workspace/peptides-dash-monitors/ads.json (IG Ad tools + ad-stats.md + ads-audience.md)')
pep_replies = dict(as_of=_hm(_R.get('as_of')), stale=str(_R.get('freshness', '')).startswith('STALE'),
                   stale_label=_R.get('stale_label') or 'данные устарели с 22.10 — WA-сводка на паузе', freshness=_R.get('freshness', ''),
                   cron_failed=bool(_R.get('cron_failed')),
                   owner=_R.get('owner',''),
                   items=[dict(who=_mask(u.get('chat')), msg=_mask(u.get('issue')), since=u.get('customer_msg_day') or u.get('day') or '',
                               status=u.get('status', ''), note=u.get('note', '')) for u in _R.get('unanswered', [])],
                   src='Пептид: /workspace/peptides-dash-monitors/replies.json (analysis-2026-10-21.md + carryover.md)')

# Rost 27.10 t4157–59: скорость ответа в рабочее время из reply_speed.json → монитор ответов
# (переключатель Сегодня=вчера / Неделя / Месяц уже в pepMonHTML; тут только данные)
_SP = _j('reply_speed.json') or {}
_DS_new = {str(r.get('date')): r.get('new_dialogs') for r in ((_j('dialogs-since-2026-10-12.json') or {}).get('days') or []) if isinstance(r, dict)}
_sp_rows = []
for _d in (_SP.get('days') or []):
    if not isinstance(_d, dict) or not _d.get('date'): continue
    _mins = list(_d.get('mins') or [])
    if not _mins and _d.get('first_n') and _d.get('first_median_min') is not None:
        _mins = [float(_d['first_median_min'])] * int(_d['first_n'])
        _approx = True
    else:
        _approx = bool(_d.get('mins_approx'))
    _ok = [m for m in _mins if m is not None]
    _new = _d.get('new') if _d.get('new') is not None else _DS_new.get(_d['date'])
    _n = _d.get('first_n') if _d.get('first_n') is not None else (len(_ok) if _ok else None)
    _avg = _d.get('first_avg_min')
    if _avg is None and _ok: _avg = round(sum(_ok)/len(_ok))
    _med = _d.get('first_median_min')
    # If no new-lead mins but night scan left work_mins — use for period avg (t4157)
    _use_mins = _mins
    if not _ok and _d.get('work_mins'):
        _use_mins = list(_d['work_mins'])
        _ok = [m for m in _use_mins if m is not None]
        _avg = _d.get('work_avg_min') if _d.get('work_avg_min') is not None else (round(sum(_ok)/len(_ok)) if _ok else None)
        _med = _d.get('work_median_min', _med)
        _n = len(_ok) if _ok else _n
        _approx = True
    _sp_rows.append(dict(
        date=_d['date'], new=_new, n=_n, le15=_d.get('first_le15'),
        avg=_avg, med=_med, mins=_use_mins, approx=_approx,
        sales_wa=_d.get('sales_wa'), sales_sheet=_d.get('sales_sheet') or 0,
        note=_d.get('note') or ''))
pep_replies['speed'] = dict(
    work_hours=_SP.get('work_hours') or 'пн–пт 10:00–18:30 Bogotá',
    definition=_SP.get('definition') or 'Первый ответ новому лиду в рабочее время (ночный обход §4).',
    rows=_sp_rows,
    from_new=_SP.get('sales_from_new_dialogs_since'),
    as_of=_hm(_SP.get('as_of')),
    src=_SP.get('src') or 'peptides-dash-monitors/reply_speed.json')

# Rost 25.10: каждый «пора» / «хочет ещё» → напоминание Саре в CU 86bcn2ew9, трекинг до покупки/отказа.
# Состояние — src/repeat_tracking.json (агент обновляет по комментам задачи). no_sara_feedback считает и JS по SLA.
_RT = json.load(open(os.path.join(os.path.dirname(__file__), 'repeat_tracking.json')))
def _asg_now(sch):
    for a in sch or []:
        if a.get('until') and TODAY.isoformat() <= a['until']: return a['who']
        if a.get('from') and TODAY.isoformat() >= a['from']: return a['who']
    return (sch or [{}])[-1].get('who', 'Sara') if sch else 'Sara'
def _track(key, label):
    t = dict(_RT['clients'].get(key) or {})
    pings = t.get('pings') or []
    return dict(sara_status=t.get('sara_status') or 'pending_ping', assignee_now=_asg_now(t.get('assignee_schedule')),
                assignee_schedule=t.get('assignee_schedule') or [], deadline=t.get('deadline'),
                last_ping=pings[-1] if pings else None, last_reply_at=t.get('last_reply_at'), reply_note=t.get('reply_note', ''),
                outcome=t.get('outcome'), track_note=t.get('note', ''))
for _r in due_now: _r.update(_track(_r.get('client_key') or _r['client'], _r['client']))
pep_repeat['intent'] = [dict(label=i.get('label'), note=i.get('note'), as_of=i.get('as_of'), **_track(i.get('id') or i.get('label'), i.get('label')))
                        for i in (_R.get('repeat_sales') or {}).get('intent_signals', [])]
pep_repeat['items'] = [dict(kind='due', client=r['client'], **{k: r[k] for k in r if k in ('sara_status','assignee_now','assignee_schedule','deadline','last_ping','last_reply_at','reply_note','outcome')}) for r in due_now] + \
                      [dict(kind='intent', client=r['label'], **{k: r[k] for k in r if k in ('sara_status','assignee_now','assignee_schedule','deadline','last_ping','last_reply_at','reply_note','outcome')}) for r in pep_repeat['intent']]
pep_repeat.update(cu_task=_RT['cu_task'], cu_url=_RT['cu_url'], sla_h=_RT.get('feedback_sla_hours', 24),
                  process='«Пора» или «хочет ещё» → коммент-напоминание Саре в CU 86bcn2ew9 → ждём ответ и итог (купил/отказ). Нет ответа > SLA → «Требует внимания».')
# Rost 25.10: конверсия = факт по НОВЫМ запускам с 12.10 (не хардкод «10→1»).
# HARD Rost 25.10 23:21: старый архив (~213 лидов, ≈1 к 27) НЕ считаем в основной конверсии — только новые запуски.
_since = [a for a in pep_ads['active'] + pep_ads['archive'] if str(a.get('start') or '').startswith('20') and str(a['start'])[:10] >= '2026-10-12' and a.get('conversations')]
_undated = [a['name'] for a in pep_ads['active'] + pep_ads['archive'] if not str(a.get('start') or '').startswith('20') and a.get('conversations')]
_arch = (pep_ads.get('summary') or {}).get('leads') or 0  # справочно, не в основной формуле
_ns = sum(x.get('units') or 1 for x in pep_ledger['sales'])
_sales_since = sum(x.get('units') or 1 for x in pep_ledger['sales'] if str(x.get('date') or '')[:10] >= '2026-10-12')
_sales_before = _ns - _sales_since  # архив до 12.10 — не в «сейчас»
_nd = sum(a['conversations'] for a in _since)  # fallback по РК
# Диалоги с 12.10: файл Пептида; если свежих дней нет (пауза) — берём last known totals_scanned_days
_DS = _j('dialogs-since-2026-10-12.json'); _ds_src = 'Σ conversations РК ≥12.10 (ads.json)'
_days_missing = []
if _DS:
    _v = next((_DS.get(k) for k in ('total', 'dialogs', 'count', 'new_dialogs', 'total_dialogs', 'dialogs_total') if isinstance(_DS.get(k), (int, float))), None)
    _ts = (_DS.get('totals_scanned_days') or {})
    if _v is None and isinstance(_ts.get('new_dialogs'), (int, float)):
        _v = int(_ts['new_dialogs'])
    # sum of days with numbers (carry last known; null days after pause = missing, not zero)
    _day_rows = _DS.get('days') or _DS.get('by_day') or []
    if isinstance(_day_rows, list) and _day_rows:
        _sumd = 0; _any = False
        for _dr in _day_rows:
            if not isinstance(_dr, dict): continue
            _n = _dr.get('new_dialogs'); _n = _dr.get('n') if _n is None else _n
            if _n is None: _days_missing.append(str(_dr.get('date') or ''))
            else: _sumd += int(_n); _any = True
        if _v is None and _any: _v = _sumd
    if _v is not None:
        _nd = int(_v)
        _ds_src = 'Пептид: dialogs-since-2026-10-12.json (last known' + (', as_of ' + str(_DS.get('as_of'))[:16] if _DS.get('as_of') else '') + ')'
pep_ads['conversion'] = dict(
    sales_total=_ns, sales_since=_sales_since, sales_before=_sales_before,
    leads_archive=_arch,  # справочно / детали ▼, не в «сейчас»
    dialogs_since=_nd, since='2026-10-12',
    since_campaigns=[a['name'][:40] for a in _since], undated=[x[:40] for x in _undated],
    dialogs_src=_ds_src, dialogs_exact=bool(_DS),
    days=_DS.get('days') if _DS else [], days_missing=[x for x in _days_missing if x],
    exclude_archive=True, exclude_note='старый аккаунт ≈1→27 не считаем (Rost 25.10)',
    target_dialogs_per_sale=((pep_ads.get('plan') or {}).get('conversion_benchmark') or {}).get('dialogs_per_sale', 10),
    src='только новые запуски с 12.10: наборы PEPTIDOS VENTAS + диалоги dialogs-since (last known при паузе); архив 213 лидов исключён из основной конверсии')
# Rost 26.10: «💬 Диалогов сегодня» — отдельный монитор из вотчера уведомлений Business WA (AX42 clickup, wa-notify-peptid)
# → вебхук → /workspace/peptides-dash-monitors/apply_wa_toast.py → dialogs-today.json. Только число уникальных за день Bogotá, имён в дашборд не отдаём.
_DT = _j('dialogs-today.json')
pep_dialogs_today = dict(
    date=_DT.get('date'), count=_DT.get('count'), events=_DT.get('events'),
    first_event_at=_DT.get('first_event_at'), last_event_at=_DT.get('last_event_at'), as_of=_DT.get('as_of'),
    watcher_status=_DT.get('watcher_status') or ('unknown' if _DT else 'missing'),
    history=[dict(date=h.get('date'), count=h.get('count')) for h in (_DT.get('history') or [])][:7],
    cron_failed=bool(_DT.get('cron_failed')),
    definition='уникальные люди, написавшие в WhatsApp Peso Saludable за день (Bogotá), по уведомлениям — чаты не открываются; вкл. старых клиентов; ночная WA-сводка уточняет источник',
    stale_rule='мягкий флаг, если нет событий >2 ч в 09:00–20:00 Bogotá; «Требует внимания» только при cron_failed',
    src='Пептид: вотчер wa-notify-peptid (AX42 clickup) → peptides-dash-monitors/dialogs-today.json') if _DT else dict(watcher_status='missing', count=None, src='dialogs-today.json нет')
pep_ads['conversion'].update(dialogs_today=pep_dialogs_today.get('count'), dialogs_today_as_of=pep_dialogs_today.get('as_of'),
                             dialogs_today_date=pep_dialogs_today.get('date'), dialogs_today_src=pep_dialogs_today.get('src'))
# Rost 27.10 (t458u): + Instagram Direct pesosaludable.col (dialogs-today-ig.json / ig-dialogs-history.json, apply_ig_count.py)
# и «новых за вчера» WA (ночная сводка dialogs-since) + IG. null = не считали (не 0), ничего не выдумываем.
_DTI = _j('dialogs-today-ig.json') or {}
_IGH = _j('ig-dialogs-history.json') or {}
_td_s = TODAY.isoformat(); _yd_s = (TODAY - datetime.timedelta(days=1)).isoformat()  # Rost t4160: календарное вчера; пн→вс (не сб/пт)
_ig_live = (_DTI.get('watcher_status') in ('live', 'snapshot'))
_ig_today = _DTI.get('count') if _DTI.get('date') == _td_s else (0 if _DTI.get('watcher_status') == 'live' else None)
_ig_today_new = _DTI.get('new_count') if _DTI.get('date') == _td_s else (0 if _DTI.get('watcher_status') == 'live' else None)
_wa_today = (pep_dialogs_today.get('count') or 0) if (pep_dialogs_today.get('date') == _td_s) else (0 if pep_dialogs_today.get('watcher_status') == 'live' else None)
_wa_y_row = next((r for r in ((_DS or {}).get('days') or []) if isinstance(r, dict) and r.get('date') == _yd_s), None)
_wa_y_new = _wa_y_row.get('new_dialogs') if _wa_y_row else None
_wa_y_uniq = pep_dialogs_today.get('count') if pep_dialogs_today.get('date') == _yd_s else next((h.get('count') for h in (pep_dialogs_today.get('history') or []) if h.get('date') == _yd_s), None)
_ig_y_row = next((r for r in (_IGH.get('days') or []) if isinstance(r, dict) and r.get('date') == _yd_s), None)
_ig_y_new = _ig_y_row.get('new_dialogs') if _ig_y_row else None
_ig_y_uniq = _ig_y_row.get('dialogs') if _ig_y_row else None
def _sum(*v): return None if all(x is None for x in v) else sum(x or 0 for x in v)
_ig_days = [dict(date=r.get('date'), n=r.get('new_dialogs'), dialogs=r.get('dialogs')) for r in (_IGH.get('days') or []) if isinstance(r, dict)]
_ig_since = _sum(*[r['n'] for r in _ig_days]) if _ig_days else None
pep_dialogs_today.update(
    today=_td_s, yesterday=_yd_s,
    wa_count=_wa_today, ig_count=_ig_today, ig_new_today=_ig_today_new, total_today=_sum(_wa_today, _ig_today),
    yesterday_new_wa=_wa_y_new, yesterday_new_ig=_ig_y_new, yesterday_new_total=_sum(_wa_y_new, _ig_y_new),
    yesterday_uniq_wa=_wa_y_uniq, yesterday_uniq_ig=_ig_y_uniq,
    yesterday_new_wa_src=('ночная WA-сводка (' + str((_wa_y_row or {}).get('source') or '') + ')') if _wa_y_row else 'нет строки в dialogs-since',
    ig=dict(status=_DTI.get('watcher_status') or 'missing', account=_DTI.get('account') or 'pesosaludable.col', date=_DTI.get('date'),
            count=_DTI.get('count'), new_count=_DTI.get('new_count'), as_of=_DTI.get('as_of'), src=_DTI.get('src'),
            last_event_at=_DTI.get('last_event_at'), next_step=_DTI.get('next_step'),
            definition=_DTI.get('definition') or 'уникальные написавшие в IG Direct за день Bogotá'),
    channels=dict(wa=dict(count=_wa_today, status=pep_dialogs_today.get('watcher_status')), ig=dict(count=_ig_today, status=_DTI.get('watcher_status') or 'missing')))
for _r in (pep_ads['conversion'].get('days') or []):
    if isinstance(_r, dict) and 'n' not in _r: _r['n'] = _r.get('new_dialogs')  # cvTable читает x.n
pep_ads['conversion'].update(
    wa_dialogs_today=_wa_today, ig_dialogs_today=_ig_today, ig_new_today=_ig_today_new, dialogs_today_total=_sum(_wa_today, _ig_today),
    ig_dialogs_since=_ig_since, ig_dialogs_since_from=_IGH.get('since'), ig_days=_ig_days, ig_status=_DTI.get('watcher_status') or 'missing',
    dialogs_since_wa=_nd, dialogs_since_with_ig=_nd + (_ig_since or 0),
    yesterday_new_wa=_wa_y_new, yesterday_new_ig=_ig_y_new,
    ig_note='IG Direct считаем отдельно с ' + str(_IGH.get('since') or '27.10') + '; by_source.ig_promote в WA — это WA-лиды из IG, не Direct (не дублируем)')

# Rost t4162–63: новые IG + WA вшить в каждую РК (по аккаунту / окну старта), не отдельными KPI сверху
def _sum_range(days, start, key='new_dialogs', src_key=None):
    if not start or not str(start)[:10].startswith('20'): start = '2026-10-12'
    s = str(start)[:10]; tot = 0; any_ = False
    for r in days or []:
        if not isinstance(r, dict): continue
        d = str(r.get('date') or '')
        if d < s: continue
        if src_key:
            v = (r.get('by_source') or {}).get(src_key)
        else:
            v = r.get(key)
        if v is None: continue
        any_ = True; tot += int(v or 0)
    return tot if any_ else None

_wa_days = ((_DS or {}).get('days') or [])
_ig_days_raw = (_IGH.get('days') or [])
for _lst in (pep_ads.get('active') or [], pep_ads.get('scheduled') or [], pep_ads.get('archive') or []):
    for _a in _lst:
        _acc = (_a.get('account') or '').lower()
        _obj = (_a.get('objective') or '').lower()
        _st = (_a.get('start') or '')[:10]
        _ig = None; _wa = None; _note = ''
        _is_ig_acc = 'pesosaludable.col' in _acc or 'profile' in _obj
        _is_wa_obj = 'conversation' in _obj or 'whatsapp' in _obj or 'диалог' in _obj
        if _is_ig_acc:
            _ig = _sum_range(_ig_days_raw, _st, 'new_dialogs')
            # WA-лиды с IG Promote (не Direct) за окно РК
            _wa = _sum_range(_wa_days, _st, src_key='ig_promote')
            if _wa is None and _st:
                # fallback: все новые WA в окне, если by_source пуст
                _wa = _sum_range(_wa_days, _st, 'new_dialogs')
            _note = 'акк. ' + (_a.get('account') or '') + ' · с ' + (_st or '?') + ' · IG Direct + WA (ig_promote/новые); не split между РК одного аккаунта'
        elif _is_wa_obj or 'pesosaludable.com.co' in _acc:
            _wa = _a.get('conversations')  # Meta Conversations = WA-диалоги РК
            _ig = None
            _note = 'цель Conversations/WA · IG Direct к этой РК не привязан'
        else:
            _ig = _sum_range(_ig_days_raw, _st, 'new_dialogs') if _acc else None
            _wa = _a.get('conversations')
            _note = 'attribution: best-effort'
        _a['dialogs_new_ig'] = _ig
        _a['dialogs_new_wa'] = _wa
        _a['dialogs_note'] = _note
# вчерашние новые (календарные) — для подписи в строке при mode Сегодня
for _lst in (pep_ads.get('active') or [], pep_ads.get('scheduled') or [], pep_ads.get('archive') or []):
    for _a in _lst:
        _a['dialogs_yesterday_ig'] = pep_ads['conversion'].get('yesterday_new_ig')
        _a['dialogs_yesterday_wa'] = pep_ads['conversion'].get('yesterday_new_wa')
        # только если аккаунт IG / WA релевантен
        _acc = (_a.get('account') or '').lower(); _obj = (_a.get('objective') or '').lower()
        if 'pesosaludable.col' not in _acc and 'profile' not in _obj:
            _a['dialogs_yesterday_ig'] = None
        if 'conversation' not in _obj and 'pesosaludable.col' not in _acc and 'pesosaludable.com.co' not in _acc:
            if _a.get('dialogs_new_wa') is None:
                _a['dialogs_yesterday_wa'] = None

# Rost 25.10 STANDING: attn только реальные сбои (не пауза / не last-known)
pep_issues = []
if not _A: pep_issues.append('Реклама: нет снимка ads.json от Пептида')
if not _R: pep_issues.append('Ответы WA: нет снимка replies.json от Пептида')
# нет файла диалогов вообще → не attn (есть fallback РК); cron_failed ловит dataIssues

# ---------- Real estate (sheet Расчет_Аренда / ИТОГИ, read 19.10.2026) ----------
re_src = 'GSheet «Расчет_Аренда» 1GU84qAq…k6-o, вкладка ИТОГИ (прочитано 19.10.2026)'
es_rent = [5375, 4925, 5220, 5014, 4652.91, 5257.91, 6715.91, 6070.91]
es_tax = [1290, 1182, 1252.8, 1203.36, 1116.7, 1261.9, 1611.82, 1457.02]
es_net = [4085, 3743, 3967.2, 3810.64, 3536.21, 3996.01, 5104.09, 4613.89]
total = [4955.47, 4627.10, 4841.03, 4740.17, 4824.95, 5046.83, 5422.69, 4663.89]
re_periods, re_rows = {}, []
for i in range(8):
    m = f'2026-{i+1:02d}'
    ua = round(total[i] - es_net[i], 2)
    re_periods['M:' + m] = dict(status='partial' if i == 7 else 'full',
        income=[item('Испания: получено аренды', es_rent[i], 'EUR', re_src),
                item('Украина нетто − долги (= ИТОГО − Испания)', ua, 'EUR', re_src, note='расчётная строка')],
        expenses=[item('Испания: налог 24%', es_tax[i], 'EUR', re_src)],
        metrics={'ИТОГО чистая прибыль (строка 14)': total[i], 'Слотов в аренде (Украина)': 3},
        note='Август может быть неполным (лаг аренды)' if i == 7 else None)
    re_rows.append([MONTH_NAMES[i], es_rent[i], es_tax[i], es_net[i], total[i]])
re_break = [
  dict(period=None, title='По месяцам 2026 (EUR)', columns=['Месяц', 'Испания получено', 'Налог 24%', 'Испания чистая', 'ИТОГО (стр. 14)'], rows=re_rows),
  dict(period=None, title='Колумбия: Base Loft — вторая квартира (поиск 18.10, объявления)', columns=['Вариант', 'м²', 'COP/мес', 'Статус'],
       rows=[['Loft-дуплекс, эт. 10, мебель (CALIPTO)', 50, 2600000, 'активно'], ['Apartaestudio C4632 (ALNAGO)', 53, 2500000, 'активно'], ['Apartaestudio с балконом', 34, 1750000, 'активно']]),
]

# ---------- Недвижимость: блоки (Rost 25.10 23:38) — Цель / Solvia / Окупасы / Аренда / Инвесторы ----------
import csv as _csv
REB = json.load(open(os.path.join(os.path.dirname(__file__), 're_blocks.json')))
_cuu = lambda i: f'https://rosmater.github.io/cu/?t={i}' if i else None
# цель: факт = последний месяц ИТОГО (стр. 14), EUR; конверсия в USD — на клиенте по курсу meta.fx
REB['goal']['fact'] = dict(amount=total[-1], cur='EUR', period=MONTH_NAMES[len(total) - 1] + ' 2026', partial=True, src=re_src)
# Solvia: attn только по данным (непросмотренные письма / новые объекты), иначе ок
_S = REB['solvia']
_S['status'] = 'attention' if ((_S.get('unread_count') or 0) > 0 or (_S.get('new_objects') or 0) > 0) else ('ok' if _S.get('unread_count') == 0 and _S.get('new_objects') == 0 else 'nodata')
# окупасы: рынок (справочно) из objects-db/occupied_ref.csv
_OCC = '/home/box/contacts/knowledge/shared-real-estate/objects-db/occupied_ref.csv'
try:
    _occ = [dict(src=r['Source'], url=r['URL'], price=float(r['Price €']) if r['Price €'] else None, m2=float(r['m2']) if r['m2'] else None,
                 type=r['Type'], address=r['Address'], own=r['Ownership']) for r in _csv.DictReader(open(_OCC))]
except Exception:
    _occ = []
REB['okupas']['market'] = sorted(_occ, key=lambda x: x['price'] or 9e9)
for o in REB['okupas']['ours']:
    for c in o['cu']: c['url'] = _cuu(c['id'])
# аренда: % заполненности только если известна занятость каждого юнита; иначе null → «—»
for f in REB['rent']['flats']:
    f['url'] = _cuu(f['cu'])
    for t in f['tasks']: t['url'] = _cuu(t['id'])
    n = len(f['units']) if f['units'] and not any('студ' in u for u in f['units']) else None
    f['occ_pct'] = round(f['occupied'] / n * 100) if (n and f.get('occupied') is not None) else None
    f['status'] = 'attention' if f['problems'] or f.get('free_units') else ('ok' if f['occ_pct'] == 100 else 'nodata')
for k in ('free', 'prep', 'prep_launch', 'for_sale', 'evict', 'other_pay', 'sold'):
    for x in REB['rent'].get(k) or []: x['url'] = _cuu(x.get('cu'))
for p_ in REB['investors']['people']:
    p_['url'] = _cuu(p_.get('cu'))

# ---------- Tabakevich / kalyan (BAS) ----------
# Rost 25.10 23:44–23:49: блоки вкладки (На решение / Фин-сводки / ИМ / Дроп / МП / Менеджеры / Розница / Опт+дебиторка) — снимок src/tbk_blocks.json
TBKB = json.load(open(os.path.join(os.path.dirname(__file__), 'tbk_blocks.json')))
# Rost 25.10 ~23:55: блоки «Личное» — снимок src/personal_blocks.json (генератор personal_blocks_gen.py); hide_from_helper-блоки вырезаются в data-asst
PERSB = json.load(open(os.path.join(os.path.dirname(__file__), 'personal_blocks.json')))
tb_src = 'knowledge/tbk-1c-reports/kalyan-weekly/2026-10-19-EXTRACT.md (BAS «Валовая прибыль по номенклатуре», USD)'
def tb(rev, gp, status, label):
    return dict(status=status, income=[item('Выручка направления (интернет + магазин «Кальяны»)', rev, 'USD', tb_src)],
                expenses=[item('Себестоимость товара (выручка − валовая прибыль)', round(rev - gp, 2), 'USD', tb_src)],
                metrics={'Валовая маржа': f"{gp/rev*100:.1f}%"}, note='Прибыль = валовая (без операционных расходов и ФОТ). ' + label)
tb_periods = {
  'W:2026-10-05': tb(32997.10, 10358.09, 'full', ''),
  'W:2026-10-12': tb(30339.09, 9582.16, 'full', ''),
  'M:2026-10': dict(tb(86170.05, 28868.25, 'partial', 'Месяц-к-дате 01–19.10 из BAS (не сумма недель: недели 05–18.10 + 01–04.10 + 19.10).'),
                    metrics={'Валовая маржа': '33.5%', 'Вывел Rost 01–10.10 (деньги собственников), $': 6566.15}),
  'M:2026-09': dict(status='full', income=[], expenses=[], metrics={'Вывел Rost (деньги собственников), $': 27618.79},
                    note='По направлению за сентябрь цифр нет; ниже — P&L компании целиком.'),
  'M:2026-08': dict(status='full', income=[], expenses=[], metrics={'Вывел Rost (деньги собственников), $': 34132.03}, note='По направлению за август цифр нет.'),
}
tb_ch = {
 'W:2026-10-12': [['Tabakevich', 11889.58, 4003.82], ['Rozetka', 4114.15, 1228.42], ['SmokeJeen', 2412.07, 838.50], ['Prom', 1061.58, 265.84], ['Hookahshop', 1019.44, 229.39], ['Palm VapeShop', 340.08, 102.98], ['Hookario', 246.80, 105.63], ['Radus', 240.46, 111.92], ['Familysmokes', 238.73, 99.66], ['Felix Shop', 179.06, 64.74], ['Магазин Центр «Кальяны»', 8590.49, 2527.28]],
 'W:2026-10-05': [['Tabakevich', 13069.55, 4256.82], ['Rozetka', 5827.92, 1575.79], ['SmokeJeen', 1093.56, 483.37], ['Prom', 836.42, 276.79], ['Hookahshop', 1316.93, 329.08], ['Palm VapeShop', 313.37, 102.28], ['Hookario', 156.15, 60.38], ['Radus', 21.17, 7.94], ['Familysmokes', 569.23, 248.27], ['Felix Shop', 67.23, 26.19], ['Магазин Центр «Кальяны»', 9725.57, 2991.18]],
 'M:2026-10': [['Tabakevich', 32469.65, 10697.07], ['Rozetka', 11874.82, 3350.67], ['SmokeJeen', 4243.26, 1650.85], ['Prom', 2188.06, 650.60], ['Hookahshop', 2584.47, 641.39], ['Palm VapeShop', 1009.93, 325.54], ['Hookario', 383.29, 158.98], ['Radus', 341.34, 158.18], ['Familysmokes', 976.37, 423.54], ['Felix Shop', 277.66, 101.19], ['Магазин Центр «Кальяны»', 29778.12, 10686.81]],
}
tb_break = [dict(period=p, title='По каналам (USD)', columns=['Канал', 'Выручка $', 'Валовая прибыль $', 'Маржа'],
                 rows=[[n, r, g, f"{g/r*100:.0f}%"] for n, r, g in sorted(v, key=lambda x: -x[2])]) for p, v in tb_ch.items()]
tb_break.append(dict(period=None, title='Компания TBK целиком — P&L по месяцам (грн, BAS)', columns=['Показатель', 'Июль', 'Август', 'Сентябрь'],
    rows=[['Выручка', 2731685, 3209234, 2404085], ['Валовая маржа', '26%', '24%', '27%'], ['Текущие расходы', 357308, 395196, 433629],
          ['Чистая прибыль', 339166, 375454, 214526], ['Выводы собственников (нетто)', -111679, -128297, -120303], ['Деньги на конец', 1212560, 1390992, 1226434]]))


# ---------- Оборонка (STE, Rost = агент Спецтехноэкспорта). Только МЕСЯЦ (Rost 24.10: прибыль считаем помесячно) ----------
import collections as _c
DEF = '/workspace/defense-export'
sq = list(csv.DictReader(open(f'{DEF}/outreach/send_queue.csv')))
sq_st = _c.Counter(x['status'] for x in sq)
sent = [x for x in sq if x['status'] == 'sent']
sent_oct = [x for x in sent if x['sent_at'][:7] == '2026-10']
replied = sorted({x['company'] for x in sq if 'replied' in (x['note'] or '')})
lt = list(csv.DictReader(open(f'{DEF}/live-tenders.csv')))
lt_open = [x for x in lt if x['deadline'][:10] >= '2026-10-25']
lt_high = [x for x in lt_open if x['fit_to_STE'].upper().startswith('HIGH')]
def_src_q = 'defense-export/outreach/send_queue.csv (снимок 24.10)'
def_src_t = 'defense-export/live-tenders.csv (снимок 10.10, дедлайн ≥ 25.10)'
def_periods = {
  'M:2026-10': dict(status='partial', income=[], expenses=[],
     metrics={'Писем отправлено (первые касания + FU)': len(sent_oct), 'Ответов компаний': len(replied),
              'Bounce': sq_st.get('bounced', 0), 'На паузе (hold)': sq_st.get('hold', 0), 'В очереди (pending)': sq_st.get('pending', 0),
              'Живых тендеров (дедлайн ≥ 25.10)': len(lt_open), 'из них HIGH fit': len(lt_high), 'RFQ / сделок': 0},
     note='Рассылка стартовала 21.10. Дохода (комиссии STE) пока нет — сделок нет; расходы направления не учтены. Только месячный учёт.'),
}

# ---- Табло Оборонки (Rost 25.10): только «Всего разослано», статус рассылки (была ли отправка вчера по Боготе), «Сколько ответили». Денег нет.
pr = list(csv.DictReader(open(f'{DEF}/outreach/plan15_recipients.csv')))
_hum = {x['company'] for x in pr if (x.get('reply_status') or '').lower().startswith('replied')}
_hum |= {x['company'] for x in sq if re.search(r'(?<!AUTO-)\bREPLY \d', x['note'] or '') or 'company replied' in (x['note'] or '')}
_auto = {x['company'] for x in sq if 'AUTO-REPLY' in (x['note'] or '')}
_dx = json.load(open(os.path.join(os.path.dirname(__file__), 'defense_extra.json')))
_auto |= {a['company'] for a in _dx.get('auto_replies_gmail', [])}
_hum |= {a['company'] for a in _dx.get('replies_gmail', [])}
_auto -= _hum
_last = max((x['sent_at'][:25] for x in sent), default=None)
# Rost 25.10: «Всего разослано» = реальные отправки из ящика STE (Gmail SENT, с 21.10 по Боготе) ∪ очередь бота
_gs = json.load(open(os.path.join(os.path.dirname(__file__), 'defense_sent_gmail.json')))
_sends = {}
for x in sent:
    _sends[(x['email'] if 'email' in x else x.get('to', '')).lower().strip()+'|'+x['sent_at'][:10]] = x['sent_at'][:16].replace('T', ' ')
for m in _gs['messages']:
    _b = (datetime.datetime.fromisoformat(m['date'].replace('Z', '+00:00')) - datetime.timedelta(hours=5)).strftime('%Y-%m-%d %H:%M')
    if _b[:10] >= '2026-10-21':
        _sends.setdefault(m['to'].lower().strip()+'|'+_b[:10], _b)
# Rost 25.10: считаем только доставленные — исключаем bounce/DSN Failure (defense_failed.json + status=bounced)
_failed = {e.lower() for e in json.load(open(os.path.join(os.path.dirname(__file__), 'defense_failed.json')))['failed']} | {x['email'].lower().strip() for x in sq if x['status'] == 'bounced'}
_n_failed = sum(1 for k in _sends if k.split('|')[0] in _failed)
_sends = {k: v for k, v in _sends.items() if k.split('|')[0] not in _failed}
_sent_by_day = dict(sorted(_c.Counter(v[:10] for v in _sends.values()).items()))
_last = max(_sends.values(), default=_last)
def_board = dict(
    goal='Цель: получить 1 сделку с рассылки', goal_target=1, assumption='предположение: 1 сделка на 500 доставленных сообщений', assumption_per_deal=500, deals=_dx.get('deals', 0),
    sent_total=len(_sends), failed_excluded=_n_failed, delivered_only=True, sent_by_day=_sent_by_day, last_sent_at=_last, queue_sent=len(sent), gmail_sent_checked_at=_gs['checked_at'],
    replies=len(_hum), replies_companies=sorted(_hum), auto_replies=len(_auto),
    snapshot_at=datetime.datetime.fromtimestamp(os.path.getmtime(f'{DEF}/outreach/send_queue.csv')).strftime('%Y-%m-%dT%H:%M'),
    gmail_checked_at=_dx.get('gmail_checked_at'),
    tenders=[dict(deadline=x['deadline'][:10], country=x['country'], title=x['title'][:90], buyer=x['buyer'], fit=x['fit_to_STE'].split(' ')[0], url=x['url']) for x in sorted(lt_open, key=lambda x: (0 if x['fit_to_STE'].upper().startswith('HIGH') else 1 if x['fit_to_STE'].upper().startswith('MED') else 2, x['deadline']))],
    tenders_src=def_src_t,
    src='defense-export/outreach/send_queue.csv (status=sent) + plan15_recipients.csv (reply_status) + проверка ящика STE (defense_extra.json)',
)
# Rost 27.10 defpins: верх монитора Оборонки — условные «Срочные задачи» / «Запланированные созвоны» из ClickUp Defense (src/defense_pins.json; нет файла → пусто)
_dpf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'defense_pins.json')
_dp = json.load(open(_dpf)) if os.path.exists(_dpf) else {}
_today_b = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).strftime('%Y-%m-%d')
def_board['urgent_tasks'] = [t for t in (_dp.get('urgent_tasks') or []) if isinstance(t, dict) and str(t.get('priority', 'urgent')).lower() == 'urgent']
def_board['scheduled_calls'] = sorted([t for t in (_dp.get('scheduled_calls') or []) if isinstance(t, dict) and str(t.get('due') or t.get('start') or '9999')[:10] >= _today_b], key=lambda t: (str(t.get('due') or t.get('start') or ''), str(t.get('due_t') or '')))
def_board['pins_fetched_at'] = _dp.get('fetched_at')
_by_country = _c.Counter(x['country'] for x in sent_oct)
def_break = [
  dict(period='M:2026-10', title='Рассылка STE: отправлено по странам (октябрь)', columns=['Страна', 'Писем'], rows=[[k, v] for k, v in _by_country.most_common()]),
  dict(period='M:2026-10', title='Рассылка STE: по дням', columns=['Дата', 'Писем'], rows=[[k, v] for k, v in sorted(_c.Counter(x['sent_at'][:10] for x in sent_oct).items())]),
  dict(period=None, title='Ближайшие живые тендеры (HIGH fit)', columns=['Дедлайн', 'Страна', 'Тендер'],
       rows=[[x['deadline'][:10], x['country'], x['title'][:70]] for x in sorted(lt_high, key=lambda x: x['deadline'])[:8]]),
]

# ---------- Личное (траты Rost). Только МЕСЯЦ ----------
btc_src = 'knowledge/finance/btc-reserves-repayment.md (скрины BTC-карты, 27 операций)'
card_sep = [39.73, 9.5, 32.1, 60.92, 18.74, 5.78, 18.74, 64.32, 8.57, 24.8, 435.85, 10.68, 12.55, 1.37, 42.88, 25.92, 32.5, 83.78, 67.05, 57.51]
card_oct = [75.4, 72.7, 69.2, 329.97, 5.52, 237.85, 28.21]
nutr_days_oct = len([f for f in os.listdir(f'{KB}/shared-health/nutrition-bju') if re.match(r'today-2026-10-\d\d\.md$', f)])
me_periods = {
  'M:2026-09': dict(status='partial', income=[], expenses=[item(f'Траты с BTC-карты 24–30.09 ({len(card_sep)} опер.)', round(sum(card_sep), 2), 'USD', btc_src,
                     note='только BTC-карта; часть операций доплачена USDT — не учтено')],
                    metrics={'Операций по BTC-карте': len(card_sep)}, note='Видны только траты с BTC-карты с 24.09; остальные счета/наличные не сведены.'),
  'M:2026-10': dict(status='partial', income=[], expenses=[item(f'Траты с BTC-карты 01–13.10 ({len(card_oct)} опер.)', round(sum(card_oct), 2), 'USD', btc_src,
                     note='после 13.10 скринов нет')],
                    metrics={'BTC вернуть в резерв (на 20.10)': '0.04865462 BTC', 'Дней с дневником питания (окт.)': nutr_days_oct},
                    note='Личных доходов в базе нет → прибыль не считается. Только месячный учёт.'),
}

# ---------- ClickUp tasks ----------
cu = json.load(open('/workspace/cu_tasks_dash.json'))
def tasks(ids):
    out = []
    for i in ids:
        t = cu.get(i)
        if not t: continue
        name = re.sub(r'\+?\d[\d \-]{6,}\d', '…', t['name']).strip()  # no phone numbers
        out.append(dict(id=i, name=name, status=t['status'], priority=t['priority'], due=t['due'], list=t['list'], url=f'https://rosmater.github.io/cu/?t={i}'))
    return out


# ---------- ОФ: 4 блока (Rost 25.10 23:33) — Ферма / ТС / ОФТВ / LolaPop ----------
_HERE = os.path.dirname(__file__)
OFB = json.load(open(os.path.join(_HERE, 'of_blocks.json')))
_OCU = json.load(open(os.path.join(_HERE, 'of_cu_tasks.json')))
def _cu_open(t):
    st = (t.get('status') or '').lower()
    return not (st.startswith('complete') or st in ('models', 'main', 'closed', 'done'))
_ocu_open = [t for t in _OCU['tasks'] if _cu_open(t)]
def _cut(t):
    nm = re.sub(r'\+?\d[\d \-]{6,}\d', '…', t['name']).strip()
    return dict(id=t['id'], name=nm, status=t['status'], who=', '.join(a for a in t.get('assignees') or [] if a) or '—',
                parent=t.get('parent'), url=f"https://rosmater.github.io/cu/?t={t['id']}")
def _ra_nums(s):
    s = s or ''
    if 'RA' not in s.upper(): return set()
    out = set()
    for m in re.finditer(r'RA\s?(\d{3})((?:\s?/\s?(?:RA\s?)?\d{3})*)', s, re.I):
        out.add(m.group(1)); out |= set(re.findall(r'\d{3}', m.group(2) or ''))
    return out
# ТС: две последние закрытые недели + текущая неполная
_wk_full = sorted([k for k, v in of_periods.items() if v['status'] == 'full'])
_wk_part = sorted([k for k, v in of_periods.items() if v['status'] != 'full'])
def _ts_week(k):
    if not k: return None
    b = next((x for x in of_break if x['period'] == k), None); rows = b['rows'] if b else []
    act = [r for r in rows if (r[1] or 0) > 0]
    net = of_periods[k]['income'][0]['amount']; gross = of_periods[k]['metrics']['Оборот моделей (gross), $']
    w = next((x for x in weeks if 'W:' + x['id'] == k), None)
    return dict(id=k, label=w['label'] if w else k[2:], status=of_periods[k]['status'], net=round(net, 2), gross=round(gross, 2),
                models=len(act), arpu=round(net / len(act), 2) if act else None, arpu_gross=round(gross / len(act), 2) if act else None)
_ts_last, _ts_prev = (_wk_full[-1] if _wk_full else None), (_wk_full[-2] if len(_wk_full) > 1 else None)
_ts_cur = _wk_part[-1] if _wk_part and (not _ts_last or _wk_part[-1] > _ts_last) else None
_lb = next((x for x in of_break if x['period'] == (_ts_cur or _ts_last)), {'rows': []})
_pb = {r[0]: r for r in next((x for x in of_break if x['period'] == _ts_last), {'rows': []})['rows']}
_ts_models = []
for r in _lb['rows']:
    num = r[0][2:]
    ts_tasks = [_cut(t) for t in _ocu_open if num in (_ra_nums(t['name']) | _ra_nums(t.get('parent')))]
    p = _pb.get(r[0])
    _ts_models.append(dict(ra=r[0], gross=r[1], pct=r[2], net=r[3], fans_new=r[4], prev_net=p[3] if p else None, prev_gross=p[1] if p else None, tasks=ts_tasks))
OFB['ts'].update(last=_ts_week(_ts_last), prev=_ts_week(_ts_prev), cur=_ts_week(_ts_cur), models=_ts_models,
                 models_week=(_ts_cur or _ts_last), models_label=(_ts_week(_ts_cur or _ts_last) or {}).get('label'), src=of_src, cu_fetched_at=_OCU['fetched_at'])
# ОФТВ: задачи по моделям / направлению
_O = OFB['oftv']; _used = set()
for m in _O['models']:
    ks = [k.lower() for k in m['match']]
    m['tasks'] = [_cut(t) for t in _ocu_open if any(k in (t['name'] + ' ' + (t.get('parent') or '')).lower() for k in ks)]
    _used |= {t['id'] for t in m['tasks']}
    m['net'] = m.get('net'); m['gross'] = m.get('gross')
_O['total_gross'] = round(sum(m['gross'] or 0 for m in _O['models']), 2) if all(m.get('gross') is not None for m in _O['models']) else None
_O['total_net'] = round(sum(m['net'] or 0 for m in _O['models']), 2) if all(m.get('net') is not None for m in _O['models']) else None
_byid = {t['id']: t for t in _OCU['tasks']}
_used |= {x.get('task') for x in _O['launch'] + _O['traffic_back']}
_dir_ids = list(_O['direction_tasks']) + [t['id'] for t in _ocu_open if re.search(r'OF\.?\s?TV|ОФТВ', t['name'], re.I) and t['id'] not in _used]
_O['tasks'] = [_cut(_byid[i]) if i in _byid else dict(id=i, name=(cu.get(i) or {}).get('name', i), status=(cu.get(i) or {}).get('status', '?'), who='Rost', url=f'https://rosmater.github.io/cu/?t={i}')
               for i in dict.fromkeys(_dir_ids)]
for lst in ('launch', 'traffic_back'):
    for x in _O[lst]:
        t = _byid.get(x.get('task'))
        x['cu'] = _cut(t) if t else None
_O['cu_fetched_at'] = _OCU['fetched_at']
# Ферма: idle только из свежего снимка (current), не из старого
_F = OFB['farm']
_F['idle'] = int(_F['current'].get('idle') or 0) if _F['current'].get('as_of') else 0
of_gaps_extra = []
if not _F['current'].get('as_of'):
    of_gaps_extra.append('Ферма: свежего снимка Сейдера нет (последний ' + _F['last_snapshot']['label'] + ') — монитор ждёт данные')


# ---------- Календарь (Rost 25.10): Google Calendar + ClickUp-задачи со временем, одна лента ----------
# Снимки делает агент через коннекторы (MCP не вызывается из build.sh):
#   /workspace/gcal_dash.json  — Google Calendar list_events (primary zayavki.ua), ~14 дней, America/Bogota
#   /workspace/cu_cal_dash.json — ClickUp filter_tasks (assignee me, due в том же окне)
def _load(pth):
    try: return json.load(open(pth))
    except Exception: return None
_g = _load('/workspace/gcal_dash.json') or {}
_cu = _load('/workspace/cu_cal_dash.json') or {}
_BOG = datetime.timezone(datetime.timedelta(hours=-5))
cal_events = []
for e in _g.get('events', []):
    t = e['title']; src = 'gcal'
    if ' :: ' in t:  # задачи ClickUp, синхронизированные в Google Calendar (весь день)
        src = 'clickup'; t = t.replace('🔄 ', '', 1).split(' :: ')[0]
    cal_events.append(dict(src=src, title=t, start=e['start'], end=e['end'], all_day=e['all_day'],
                           url=e.get('url'), via='gcal-sync' if src == 'clickup' else None))
_seen = {x['title'].strip().lower() for x in cal_events if x['src'] == 'clickup'}
for t in _cu.get('tasks', []):
    d = datetime.datetime.fromtimestamp(t['due_ms'] / 1000, _BOG)
    if d.strftime('%H:%M') == '04:00':  # без времени (только дата) — в ленту не берём, они идут через GCal-синк
        continue
    if 'complete' in (t.get('status') or '') or 'closed' in (t.get('status') or ''): continue
    nm = re.sub(r'\+?\d[\d \-]{6,}\d', '…', t['name']).strip()
    if nm.lower() in _seen: continue
    cal_events.append(dict(src='clickup', title=nm, start=d.isoformat(), end=None, all_day=False, due=True,
                           list=t.get('list'), url=f"https://rosmater.github.io/cu/?t={t['id']}"))
# Rost 25.10: в календаре только события со временем — задачи ClickUp «на весь день» (gcal-sync) не показываем
cal_events = [x for x in cal_events if not x['all_day']]
# Привязка ClickUp-карточек к событиям Google (справа от события): тот же день + похожее название
# (или явный синоним), иначе — срок задачи внутри не-общего блока с тем же ключевым словом.
_STOP = {'и','в','на','с','по','для','до','от','к','—','-','+','пн','вт','ср','чт','пт','сб','вс','занятие','созвон'}
_ALIAS = {'тренировка': {'зал','турник','тренировка'}, 'зал': {'тренировка','зал'}}
def _words(t):
    ws = {w for w in re.findall(r'[\wа-яёА-ЯЁ]+', t.lower()) if len(w) > 2 and w not in _STOP}
    out = set(ws)
    for w in ws: out |= _ALIAS.get(w, set())
    return out
_gc = [x for x in cal_events if x['src'] == 'gcal']
for c in [x for x in cal_events if x['src'] == 'clickup']:
    cw, cd = _words(c['title']), c['start'][:10]
    best, bs = None, 0
    for g in _gc:
        if g['start'][:10] != cd and g['end'][:10] != cd: continue
        sc = len(cw & _words(g['title']))
        if sc and g['start'] <= c['start'] <= g['end']: sc += 0.5
        if sc > bs: best, bs = g, sc
    if best and bs >= 2:
        best.setdefault('cu', []).append(dict(title=c['title'], url=c['url'], list=c.get('list'), due=c['start']))
        c['linked'] = True
cal_events = [x for x in cal_events if not x.get('linked')]
cal_events.sort(key=lambda x: x['start'])
calendar_dir = dict(id='calendar', kind='calendar', name='Календарь', subtitle='Google Календарь + задачи ClickUp со временем · Богота',
    currency='USD', color='#4285f4', icon='📅', no_overview_totals=True, periods={}, breakdowns=[], goals=[], tasks=[], gaps=[],
    events=cal_events, gcal_fetched_at=_g.get('fetched_at'), cu_fetched_at=_cu.get('fetched_at'),
    data_issues=[x for x in [None if _g else 'Google Calendar: нет снимка /workspace/gcal_dash.json', None if _cu else 'ClickUp: нет снимка /workspace/cu_cal_dash.json'] if x],
    gcal_url='https://calendar.google.com/calendar/u/0/r/week?authuser=zayavki.ua@gmail.com',
    refresh='Обновить: агент читает Google Calendar (list_events) и ClickUp (filter_tasks) → /workspace/gcal_dash.json, /workspace/cu_cal_dash.json → src/build.sh → пуш')

data = dict(
  meta=dict(
    title='Бизнес-дашборд', owner='Rostyslav Yermakov', city='Medellín', version='0.1-mockup',
    generated_at=datetime.datetime.now().astimezone().isoformat(timespec='minutes'),
    timezone='America/Bogota', default_week=CUR_MON.isoformat(), default_month=TODAY.strftime('%Y-%m'),  # UI сам выбирает текущую неделю по дате браузера
    stage_legend=dict(money='🟢 есть деньги', launched='🟠 запустились, денег пока нет', starting='🟡 стартуем'),  # Rost 24.10
    week_to_month_rule='Неделя (пн–вс) относится к месяцу, в котором её понедельник',
    fx=dict(
      USD_COP=dict(rate=3174.67, date='2026-10-19', source='TRM Superintendencia Financiera de Colombia (вигенсия 17–19.10.2026)'),
      EUR_USD=dict(rate=1.1225, date='2026-10-19', source='ECB reference rate'),
      USD_UAH=dict(rate=45.10, date='2026-10-19', source='курс в шапке отчёта BAS (Табакевич)')),
    weeks=weeks, months=months),
  directions=[
    dict(id='peptides', stage='launched', name='Пептиды', subtitle='Peso Saludable · Медельин', currency='COP', color='#22d3a6', icon='💉',
         periods=pep_periods, breakdowns=pep_break, ledger=pep_ledger,
         ads_monitor=pep_ads, repeat_sales=pep_repeat, replies_monitor=pep_replies, dialogs_today=pep_dialogs_today, data_issues=pep_issues,  # Rost 25.10: мониторы Пептидов (локально, до OK)
         goals=[
           dict(label='Первый ответ ≤15 мин (рабочие часы)', unit='%', target=100, by_period={'W:2026-10-12': 75.8}, src='PROCESS.md / WEEK-SUMMARY: 25 из 33'),
           dict(label='Непрочитанные к 18:30', unit='шт', target=0, lower_is_better=True, by_period={'W:2026-10-12': 4.0}, src='WEEK-SUMMARY: среднее за 6 дней'),
           dict(label='Продажи китов за неделю', unit='шт', target=10, example=True, by_period={k: v['metrics']['Продажи, шт.'] for k, v in pep_periods.items() if k[0] == 'W'}, src='цель — пример; факт — GSheet PEPTIDOS VENTAS'),
           dict(label='Продажи китов за месяц', unit='шт', target=40, example=True, period_type='month', by_period={k: v['metrics']['Продажи, шт.'] for k, v in pep_periods.items() if k[0] == 'M'}, src='цель — пример; факт — GSheet PEPTIDOS VENTAS'),
         ],
         tasks=tasks(['86bb779rw']),  # Rost 25.10: на Пептидах только задачи Rost (assignee 60710247 / «Я:»); 86bc8rxd8 (Сара) убрана
         gaps=[],  # Rost 25.10: ЗП Сары внесут позже — не attn; не-киты COGS 100k; TG Target gap убран
         ),
    dict(id='of', stage='money', name='ОФ', subtitle='OnlyFans · агентство моделей', currency='USD', color='#a78bfa', icon='🎬',
         overview_note='ОФ: «наш доход» 05services; выплаты моделям вычтены только в неделях, где они есть в отчётах Ирины.',
         periods=of_periods, breakdowns=of_break,
         goals=[
           dict(label='Баланс «Доступно» (RAH) ≥ порога', unit='$', target=1220, by_period={'W:2026-10-12': 635.65, 'W:2026-10-05': 876.09}, src='05services latest-report 18.10 / 11.10; порог из income-rules.md'),
           dict(label='Наш доход за неделю', unit='$', target=1500, example=True, by_period={k: v['income'][0]['amount'] for k, v in of_periods.items()}, src='цель — пример'),
           dict(label='Наш доход за месяц', unit='$', target=6000, example=True, period_type='month', by_period={}, auto_month='income', src='цель — пример; факт = сумма недель'),
         ],
         tasks=tasks(['86bcn2d1t', '86b6z79t1', '86bc1tdu5', '86b7heru3', '86b9abep9', '86bcn2g2q', '86b9wh8cd']),
         of_blocks=OFB,
         gaps=of_gaps_extra+['Выплаты моделям — только база с карточек (to do), факт оплат не сверён', 'Расходы офиса, прокси (IPRoyal), AdsPower и пр. не учтены', 'Неделя 12–18.10 partial', 'RA185 — наш доход 0 до 15.01.2027; RA222 в скоупе с 25.10']),
    dict(id='realestate', stage='money', name='Недвижимость', subtitle='Испания · Украина · Колумбия', currency='EUR', color='#f59e0b', icon='🏠',
         overview_note='Недвижимость: только месячные итоги (янв–авг 2026), недельных нет.',
         periods=re_periods, breakdowns=re_break,
         goals=[
           dict(label='Чистая прибыль аренды за месяц', unit='€', target=5000, example=True, period_type='month', by_period={'M:' + f'2026-{i+1:02d}': total[i] for i in range(8)}, src='цель — пример; факт ИТОГИ!стр.14'),
           dict(label='Слоты в аренде (Украина)', unit='шт', target=3, example=True, period_type='month', by_period={'M:' + f'2026-{i+1:02d}': 3 for i in range(8)}, src='цель — пример; факт из таблицы'),
         ],
         tasks=tasks(['86b7wu7jq', '86b6qz12h', '86b88jb1f', '86baqkyw4', '86bc1d1wj', '86b9va7c4', '86b8ttzmc']),
         re_blocks=REB,  # Rost 25.10: блоки Недвижимости
         gaps=['Недельной разбивки нет — только месяцы', 'Сентябрь и октябрь 2026 в таблице ещё не заполнены', 'Валюта в таблице не подписана — принято EUR (Испания)', 'Колумбия: доходов от аренды в базе нет; Los Pueblos/Топасио — ремонт, расходы не сведены']),
    dict(id='tabakevich', stage='money', name='Табакевич', subtitle='Украина · e-shop + магазин', currency='USD', color='#38bdf8', icon='💨',
         overview_note='Табакевич: валовая прибыль всего направления (до опер. расходов, ФОТ и доли партнёра), не доход Rost.',
         periods=tb_periods, breakdowns=tb_break,
         goals=[
           dict(label='Выручка направления за неделю', unit='$', target=35000, example=True, by_period={'W:2026-10-05': 32997.10, 'W:2026-10-12': 30339.09}, src='цель — пример'),
           dict(label='Валовая маржа', unit='%', target=33, example=True, by_period={'W:2026-10-05': 31.4, 'W:2026-10-12': 31.6, 'M:2026-10': 33.5}, src='цель — пример'),
           dict(label='ФОТ ≤ 10% от прибыли', unit='%', target=10, lower_is_better=True, by_period={}, src='правило из задачи 86b6qqajb; факт не считан'),
         ],
         tasks=tasks(['86b6u7p2v', '86b7n8kwx', '86bcj512x', '86bcgckxu', '86b92hrcp', '86b8gv8kj']),
         tbk_blocks=TBKB,  # Rost 25.10: блоки Табакевича (над мониторами/показателями)
         monitors_title='Из «Перемен к лучшему»', monitors_sub='Кальян · Направления · статус сен',
         # Rost 25.10: по очереди из листа «Направления» таблицы ПЕРЕМЕНЫ К ЛУЧШЕМУ → мониторы на вкладке
         monitors=[
           dict(name='Удержать + порядок', status='active', note='сен: плюс-минус / фокус на автоматизацию через ботов', src='Перемены · Направления · Кальян'),
           dict(name='SEO сайтов', status='attention', note='потенциал 1000$/мес; сен: просадки после апдейта августа — разбирают', src='Перемены · Направления'),
           dict(name='Контекст + шоппинг + китайские товары', status='active', note='контекст на 2 сайта + новые категории; шоппинг и китайские — отказались', src='Перемены · Направления'),
           dict(name='Клиентская база / скидочная', status='active', note='14 414 контактов; 1С: блок заказа без телефона', src='Перемены · Направления'),
           dict(name='ИМ: старший менеджер + рассылки', status='active', note='старший есть; Ладо — отзывы и контроль менеджеров', src='Перемены · Направления'),
           dict(name='Деление бизнеса документальное', status='attention', note='Сережа: застрял мессенджер; договоры почти готовы', src='Перемены · Направления'),
           dict(name='Безопасность — адвокаты', status='active', note='списки адвокатов готовы', src='Перемены · Направления'),
           dict(name='Вендинг (тест)', status='attention', note='ассортимент выбран; проблемы с партнёрами в Киеве; вариант белого сигаретного автомата', src='Перемены · Направления'),
         ],
         gaps=['Недели до 05.10 и месяцы до октября по направлению не выгружены', 'Прибыль — валовая, без опер. расходов', 'Число заказов по каналам не снято (BAS лагает)']),
    dict(id='defense', stage='launched', name='Оборонка', subtitle='Спецтехноэкспорт (STE) · агентский экспорт', currency='USD', color='#64748b', icon='🛡️', monthly_only=True, no_overview_totals=True, board=def_board, unanswered_replies=(lambda f: (__import__('json').load(open(f)).get('unanswered_replies', []) if __import__('os').path.exists(f) else []))(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), 'defense_unanswered.json')),  # Rost 25.10: attn только неотвеченные живые ответы  # Rost 25.10: без денег, только табло
         overview_note='Оборонка — без денежных цифр (табло рассылки); Личное — не бизнес.',
         periods=def_periods, breakdowns=def_break,
         goals=[
           dict(label='Писем за 3 мес (план 20.10)', unit='шт', target=300, period_type='month', by_period={'M:2026-10': len(sent_oct)}, src='PROJECT.md «первые клиенты»: 300–400 писем за 3 мес'),
           dict(label='Диалогов за 3 мес (план 20.10)', unit='шт', target=10, period_type='month', by_period={'M:2026-10': len(replied)}, src='PROJECT.md: 10–20 диалогов'),
           dict(label='RFQ за 3 мес (план 20.10)', unit='шт', target=2, period_type='month', by_period={'M:2026-10': 0}, src='PROJECT.md: 2–3 RFQ'),
         ],
         tasks=[],
         monitors=[  # Rost 24.10: внутри вкладок будут мониторы — пока структура
           dict(name='Рассылка STE — отправка', status='active', note='рутина «Оборонные системы», каждые 30 мин, лимит 10/день → 15/день с 26.10', src='defense-export/routines-inventory-DEFENSE.md'),
           dict(name='Рассылка STE — вечерняя сводка', status='active', note='~18:30 Богота ежедневно', src='defense-export/routines-inventory-DEFENSE.md'),
           dict(name='Ответы компаний (входящие)', status='planned', note='сейчас: 1 ответ (MER Group) — в дашборд пока вручную'),
           dict(name='Тендеры (живые дедлайны)', status='planned', note='ждёт «да» от Rost; сейчас снимок 10.10'),
         ],
         gaps=[]),  # Rost 25.10: «остальное не важно» — пробелы/деньги по Оборонке не показываем
    dict(id='personal', name='Личное', subtitle='Личные финансы · здоровье', currency='USD', color='#14b8a6', icon='🧍', no_overview_totals=True, monthly_only=True,
         overview_note='Личное не входит в итоги «Общего» (не бизнес).',
         periods=me_periods, breakdowns=[], goals=[],
         tasks=tasks(['86b6qq509']),
         personal_blocks=PERSB,  # Rost 25.10: Документы / Чеклист / БЖУ / Сон / Дейтинг🔒 / Мероприятия / Испанский / Шаги / Зал / Бокс / Употребление🔒 / Здоровье🔒
         monitors=[
           dict(name='Питание / БЖУ', status='active', note='дневник ведётся (today-*.md + Google Sheet); в дашборд — только счёт дней', src='shared-health/nutrition-bju'),
           dict(name='BTC-резерв: сколько вернуть', status='planned', note='сейчас ручная запись на 20.10'),
           dict(name='Личные траты (карты / нал)', status='planned', note='источник не подключён'),
           dict(name='Сон / режим', status='active', note='GSheet «Дневник сна» → блок «Сон» (с 20.10 не заполнялся)'),
         ],
         gaps=['Личные доходы не сведены', 'Траты: только BTC-карта 24.09–13.10; остальные карты/счета/наличные нет', 'Бюджет/лимит трат на месяц не задан',
               'После 13.10 скринов BTC-карты нет']),
    calendar_dir,
    # Коучинг: люди-подпроекты (без финансов). Источник — слова Rost в чате 24.10.2026; правки — здесь.
    dict(id='coaching', name='Коучинг', subtitle='Люди и их боты · подпроекты', kind='people', currency='USD', color='#fb7185', icon='🤝',
         periods={}, breakdowns=[], goals=[], tasks=[], gaps=[],
         people=[
           dict(name='Алехандра Херерра', icon='👩', role='Коучинг · свой доход (OF + доп. продажи)', status='attention', goal='Цель: выйти на 1000 долларов чистыми с платформ за 3 месяца',
                metrics=dict(note='Основа (внешний вид). Данные подставим при синхронизации.', currency='USD', target=1000, target_label='Цель за 3 мес. (чистыми с платформ)', groups=[
                  dict(title='Аудитория', rows=[dict(id='ig1', label='Подписчики Instagram · @alexaherrera.oficial', unit='подп.', url='https://www.instagram.com/alexaherrera.oficial', value=91201, measured='2026-10-26', hint='замер раз в неделю · socialblade (точно) · постов 266 · нед. −24'), dict(id='ig2', label='Подписчики Instagram · @alexa.herrera.oficial', unit='подп.', url='https://www.instagram.com/alexa.herrera.oficial', value=7472, measured='2026-10-26', hint='замер раз в неделю · socialblade (точно) · постов 64 · нед. +1'), dict(id='tiktok', label='Подписчики TikTok · @alexaherrera37', unit='подп.', url='https://www.tiktok.com/@alexaherrera37', value=12400, measured='2026-10-26', hint='замер раз в неделю · tiktok.com (округл. 12.4K) · видео 26 · нед. ±0')]),
                  dict(title='Доход с платформ', rows=[dict(label='Доход OF (подписчики / продажи)', unit='$', platform=True), dict(label='Доход Clips4Sale', unit='$', platform=True), dict(label='Доход Curvage', unit='$', platform=True), dict(label='Продажи в личку', unit='$', platform=True), dict(label='Суммарно платформы', unit='$', total='platforms')]),
                  dict(title='Прочее (не входит в цель и итог)', rows=[dict(label='Другие доходы', unit='COP', excluded=True, hint='правило Rost: можно ставить 600 000 / нед. — не считается в итог')]),
                  dict(title='Итог', rows=[dict(label='Суммарный доход', unit='$', total='all', hint='= Суммарно платформы; «Другие доходы» не входят')]),
                ]),
                items=['Я: Взять под контроль', 'Я: Сделать по ней план', '— Она: выкладка раз в неделю на Clips4Sale', '— Она: выкладка раз в неделю на Curvage', 'Я: Настроить анализ её OnlyFans в таблицу через сервер (диалоги, трафик, доходы)', 'Она: ТикТок начать вести'], src='Rost, 24–25.10.2026',
                cu=dict(id='86bcn44nh', label='Коучинг Алекса Херрера (Personal)', status='to do', url='https://rosmater.github.io/cu/?t=86bcn44nh')),
           dict(name='Мама', icon='👩‍🦳', role='Её бот', status='attention', goal='Цель 1 — Консультация 1 клиента в неделю (выйти на 5 визитов в неделю с таргета с ROI)', items=['Я: Помощь с общением с её ботом', 'Я: Доработать сайт чтоб открывался правильно по ссылке', 'Она: Начать считать доходы и расходы', 'Она: Вести страницу, вести диалоги', 'Она: Вести таргет, обработка лидов'], src='Rost, 24.10.2026',
                cu=dict(id='86bcqw802', label='Мама (как дела?) — ClickUp · Personal', status='to do', url='https://rosmater.github.io/cu/?t=86bcqw802')),
           dict(name='Андрей Многотуров', icon='🧑', role='Бот · TripAdvisor', status='attention', items=['Я: Подключить к боту — чтобы сам мог править', 'Он: Найти 50 отзывов (TripAdvisor)', 'Я: Не забывать выводить деньги с Viator'], src='Rost, 24.10.2026',
                cu=dict(id='86ba2y9ke', label='ТрипЭдвайсер (как дела?) — ClickUp · Personal', status='to do', url='https://rosmater.github.io/cu/?t=86ba2y9ke')),
           dict(name='Андрей Партнер', icon='🧑‍💼', role='Партнёр · бот + 1С', status='attention', items=[
                'Я: Подключить к боту (настроить и дать логин и пароль)',
                'Я: · Выдать боту доступ в 1С',
                'Я: · Передать знания о входе в 1С и работе с отчётами; поделиться нашими таблицами по сравнению 1С',
              ], src='Rost, 25.10.2026'),
           dict(name='Общее', icon='⚙️', role='Инфра / тест', status='attention',
                items=[dict(id='teams-tariff-1h', text='Я: Протестировать работу через тариф Тимс — 1 час', highlight=True, checkable=True, url='https://rosmater.github.io/cu/?t=86bcn66b7')], src='Rost, 25.10.2026',
                cu=dict(id='86bcn66b7', label='Протестировать Teams (командный план Grok Bot)', status='to do', url='https://rosmater.github.io/cu/?t=86bcn66b7')),
           dict(name='Бабушка', icon='👵', role='Бот для добавления товаров', status='ok', note='Бот работает, участие Rost не нужно', items=[], src='Rost, 24.10.2026'),
         ]),
  ],
  overview=dict(tasks=[], cu_sort=(lambda f: __import__('json').load(open(f)).get('tasks', []) if __import__('os').path.exists(f) else [])(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), 'cu_needs_sort.json'))),  # TZ cu-dash-sort 27.10: CU без категории даша -> низ «Общего»  # 86b6qq509 (Фин подбить баланс) перенесена во вкладку «Личное»
)
# Rost 26.10 (звонок): вкладки Мессенджеры + «Ассистенты · боты» (одна) в главном дашборде. Данные — data-test-ma.json (src/test_ma_build.py, только метаданные).
try:
    _MA = json.load(open(os.path.join(os.path.dirname(OUT), 'data-test-ma.json')))
    _ma_common = dict(currency='USD', periods={}, breakdowns=[], goals=[], tasks=[], gaps=[], no_overview_totals=True, ma_generated=_MA.get('generated'), cu_base=_MA.get('cu_base'), oq=_MA.get('oq'))
    data['directions'] += [
        # Rost 26.10: «Нерассортированные» — не отдельная вкладка, а блок внизу «Мессенджеров»
        dict(id='messengers', kind='msgs', name='Мессенджеры', subtitle='По сферам · канал · от кого · висящие (только метаданные, без текстов)', color='#22a06b', icon='💬', messengers=_MA.get('messengers', []), watchers=_MA.get('watchers', {}), clickup=_MA.get('clickup'), cu_inbox=_MA.get('cu_inbox'), coverage=_MA.get('coverage', []), unsorted=_MA.get('unsorted', []), spheres=_MA.get('spheres', []), ignored=_MA.get('ignored', []), reconcile=_MA.get('reconcile'), mention_handles=_MA.get('mention_handles', {}), **_ma_common),
        # Rost 26.10 «1 вкладки достаточно»: Ассистенты + Боты = ОДНА вкладка
        dict(id='assistants', kind='bots', name='Ассистенты · боты', subtitle='Вопросы ассистентов/ботов к Rost · 🔴 встало · 🟢 ок (свёрнуто) · 🟡 новые отчёты · клик → чат бота', color='#7c5cff', icon='🤖', bots=_MA.get('bots', []), **_ma_common),
    ]
except FileNotFoundError:
    pass
# TZ cu-dash-sort §2 (27.10): CU-задачи Rost с датой, сопоставленные направлению и не показанные иначе -> d.cu_dated (карточка «🗂 ClickUp · задачи с датой», не attn)
try:
    _CUD = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cu_dated.json'))).get('by_dir', {})
    for _d in data['directions']:
        if _CUD.get(_d['id']):
            _d['cu_dated'] = _CUD[_d['id']]
except FileNotFoundError:
    pass
# Rost t3955u: тапы направления на CU «на сортировку» (sync_dash_taps → cu_dir_overrides.json) -> задача уходит из cu_sort и встаёт в cu_dated своего направления
_SPH2DIR = {'Личное': 'personal', 'Дейтинг': 'personal', 'Коучинг': 'personal', 'Недвижимость': 'realestate', 'Табакевич': 'tabakevich', 'ОФ': 'of', 'Пептиды': 'peptides', 'Оборонка': 'defense', 'Игнор': None}
def _cuid(t):
    m = re.search(r'/t/(?:\d+/)?([0-9a-z]+)', t.get('url') or '')
    return t.get('id') or (m.group(1) if m else None)
try:
    import re
    _OV = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cu_dir_overrides.json'))).get('tasks', {})
    _byid = {d['id']: d for d in data['directions']}
    _keep = []
    for _t in data['overview'].get('cu_sort', []):
        _i = _cuid(_t); _o = _OV.get(_i) if _i else None
        if not _o or not _o.get('sphere'):
            _keep.append(_t); continue
        _did = _SPH2DIR.get(_o['sphere'], 'personal')
        if _did and _did in _byid:
            _L = _byid[_did].setdefault('cu_dated', [])
            if not any(_cuid(x) == _i for x in _L):
                _L.append(dict(_t, id=_i, cat=_o['sphere'], status=_t.get('status') or 'из сортировки', sorted_from_dash=_o.get('at', '')))
                _L.sort(key=lambda x: str(x.get('due') or ''))
    data['overview']['cu_sort'] = _keep
except FileNotFoundError:
    pass
# Rost t3956–59u: ДР в шапке — чеклист/описание ДР-задач (src/cu_bday_extra.json {id:{checklist:[{name,done}],desc}}), заполняет синк ClickUp
try:
    _BX = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cu_bday_extra.json'))).get('tasks', {})
    for _d in data['directions']:
        for _t in _d.get('cu_dated', []) or []:
            if _t.get('bday') and _BX.get(_t.get('id')): _t.update({k: v for k, v in _BX[_t['id']].items() if k in ('checklist', 'desc')})
except FileNotFoundError:
    pass
# Порядок вкладок (Rost 25.10): Общий → Личное, Недвижимость, Табакевич, ОФ, Пептиды, Оборонка → Календарь, Коучинг
TAB_ORDER = ['personal', 'realestate', 'tabakevich', 'of', 'peptides', 'defense', 'calendar', 'coaching', 'messengers', 'assistants', 'unsorted']
data['directions'].sort(key=lambda d: TAB_ORDER.index(d['id']) if d['id'] in TAB_ORDER else 99)
json.dump(data, open(OUT, 'w'), ensure_ascii=False, indent=1)
print('wrote', os.path.abspath(OUT), os.path.getsize(OUT))
