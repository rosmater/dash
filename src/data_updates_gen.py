#!/usr/bin/env python3
"""t6093u / t6095u: fingerprints for weekly/monthly collection blocks.

Not for live/daily items (calendar, tasks, messengers, farm day-to-day,
personal sleep/steps, peptide dialogs). Overall balance is hashed inside
its encrypted payload and registered in the browser only after unlock.
"""
from __future__ import annotations
import hashlib, json

DROP_KEYS = {
    'tasks', 'direction_tasks', 'cu_task', 'cu_url', 'cu_fetched_at', 'cu',
    'url', 'lists_note', 'items',  # CU / action items, not the report
    '_note', '_doc', '_comment',
}


def _canon(obj):
    if isinstance(obj, dict):
        return {k: _canon(v) for k, v in sorted(obj.items())
                if k not in DROP_KEYS and not str(k).startswith('_')}
    if isinstance(obj, list):
        return [_canon(x) for x in obj]
    if isinstance(obj, float):
        return round(obj, 6)
    return obj


def _ver(data, period=None):
    payload = {'data': _canon(data), 'period': period}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _blk(id, dir_id, title, data, period=None):
    if data is None:
        return None
    return {
        'id': id,
        'dir': dir_id,
        'title': title,
        'anchor': 'du-' + id.replace('.', '-'),
        'ver': _ver(data, period),
        'period': period,
    }


def _dir(data, did):
    return next((d for d in data.get('directions') or [] if d.get('id') == did), None)


def collect(data: dict) -> list:
    out = []

    of = _dir(data, 'of')
    B = (of or {}).get('of_blocks') or {}
    T = B.get('ts')
    if T:
        period = (T.get('cur') or {}).get('id') or T.get('models_week')
        out.append(_blk('of.ts', 'of', _title(T, 'ТС партнёрка (05services)'),
                        {k: T[k] for k in T if k not in ('tasks',)}, period))
    O = B.get('oftv')
    if O:
        period = (O.get('week') or {}).get('id') or (O.get('weeks') or [{}])[-1].get('id') if O.get('weeks') else None
        if not period:
            period = (O.get('week') or {}).get('id')
        out.append(_blk('of.oftv', 'of', _title(O, 'ОФТВ (с Лёшей 60/40)'),
                        {k: O[k] for k in O if k not in ('tasks', 'direction_tasks', 'launch', 'traffic_back', 'closed')},
                        period))
    P = B.get('lolapop')
    if P:
        period = (P.get('last_snapshot') or {}).get('as_of') or (P.get('last_snapshot') or {}).get('label')
        payload = {k: P[k] for k in P if k not in ('tasks', 'social', 'audit', 'pornstocks_sites')}
        # «В холде / Доступно к выплате» живёт в той же карточке «Своя модель»
        if B.get('own_accounts'):
            payload = dict(payload, own_accounts=B['own_accounts'])
        out.append(_blk('of.lolapop', 'of', _title(P, 'Своя модель — LolaPop'), payload, period))
    FR = B.get('fetish_rooms')
    if FR:
        weeks = FR.get('weeks') or []
        period = weeks[-1].get('id') if weeks else None
        out.append(_blk('of.fetish_rooms', 'of', _title(FR, 'Fetish Rooms'), FR, period))

    tb = _dir(data, 'tabakevich')
    TB = (tb or {}).get('tbk_blocks') or {}
    E = TB.get('eshop')
    if E:
        period = (E.get('periods') or [None])[-1]
        site_stats = [{k: s.get(k) for k in (
            'name', 'seo', 'ctx', 'products', 'promo', 'texts_last_month', 'links_bought',
            'dr', 'organic', 'visitors', 'conv', 'speed', 'ads')} for s in (E.get('sites') or [])]
        out.append(_blk('tbk.eshop', 'tabakevich', _title(E, 'Интернет-магазин'),
                        {'periods': E.get('periods'), 'sites': site_stats, 'other': E.get('other')}, period))
        out.append(_blk('tbk.eshop_rev', 'tabakevich', 'Выручка по сайтам',
                        {'periods': E.get('periods'), 'total': E.get('total'),
                         'own_total': E.get('own_total'), 'orders_all': E.get('orders_all'),
                         'sites': [{k: s.get(k) for k in ('name', 'rev', 'gp', 'orders', 'conv', 'visitors')}
                                   for s in (E.get('sites') or [])]}, period))
    Dr = TB.get('dropship')
    if Dr:
        out.append(_blk('tbk.dropship', 'tabakevich', _title(Dr, 'Дропшипперы'),
                        {k: Dr[k] for k in Dr if k not in ('hidden', 'hidden_note')},
                        (Dr.get('periods') or [None])[-1] if isinstance(Dr.get('periods'), list) else Dr.get('periods')))
    M = TB.get('marketplaces')
    if M:
        out.append(_blk('tbk.marketplaces', 'tabakevich', _title(M, 'Маркетплейсы'),
                        M, (M.get('periods') or [None])[-1] if isinstance(M.get('periods'), list) else None))
    Mg = TB.get('managers')
    if Mg:
        out.append(_blk('tbk.managers', 'tabakevich', _title(Mg, 'Монитор работы менеджеров'),
                        {k: Mg[k] for k in Mg if k not in ('score_formula',)},
                        Mg.get('week') or Mg.get('period')))
    ST = TB.get('seo_team')
    if ST:
        out.append(_blk('tbk.seo_team', 'tabakevich', _title(ST, 'Оценка сеошников'), ST, ST.get('as_of')))
    SW = TB.get('seo_weekly')
    if SW:
        weeks = SW.get('weeks') or []
        out.append(_blk('tbk.seo_weekly', 'tabakevich', _title(SW, 'SEO по неделям'), SW,
                        weeks[-1] if weeks else None))
    RV = TB.get('reviews')
    if RV:
        out.append(_blk('tbk.reviews', 'tabakevich', _title(RV, 'Отзывы'),
                        {k: RV[k] for k in RV if k not in ('sheet', 'sheet_note', 'mapping_note')},
                        RV.get('subtitle')))
    R = TB.get('retail')
    if R:
        out.append(_blk('tbk.retail', 'tabakevich', _title(R, 'Розница'),
                        {k: R[k] for k in R if k not in ('checks_note',)},
                        R.get('month_at')))
    Opt = TB.get('opt')
    if Opt:
        out.append(_blk('tbk.opt', 'tabakevich', _title(Opt, 'Опт + дебиторка'),
                        {k: Opt[k] for k in Opt if k not in ('cu', 'url', 'next')},
                        (Opt.get('debt') or {}).get('col')))
    OI = TB.get('opt_im')
    if OI:
        out.append(_blk('tbk.opt_im', 'tabakevich', _title(OI, 'Опт ИМ и опт-запросы'), OI, None))

    re = _dir(data, 'realestate')
    RB = (re or {}).get('re_blocks') or {}
    G = RB.get('goal')
    if G:
        fact = (G.get('fact') or {})
        out.append(_blk('realestate.goal', 'realestate', _title(G, 'Цель на весь блок'),
                        {'main': G.get('main'), 'fact': fact, 'sub': G.get('sub')},
                        fact.get('period') or fact.get('as_of')))
    F = (re or {}).get('fact_1c')
    if F:
        out.append(_blk('realestate.fact', 'realestate', 'Из чего сложилось',
                        F, F.get('title')))
    Pay = RB.get('payments')
    if Pay:
        out.append(_blk('realestate.payments', 'realestate', _title(Pay, 'Оплаты квартирантов · долги · сверка'),
                        {k: Pay[k] for k in Pay if k not in ('notes', 'src', 'fetched_at')},
                        Pay.get('as_of') or Pay.get('current_month')))
    # fetched_at excluded so a re-read of the same month doesn't flood; as_of + rows are the collection
    Pr = RB.get('profit')
    if Pr:
        out.append(_blk('realestate.profit', 'realestate', _title(Pr, 'Рентабельность по объектам'),
                        {k: Pr[k] for k in Pr if k not in ('notes', 'src', 'fetched_at')},
                        Pr.get('as_of') or Pr.get('current_month')))

    co = _dir(data, 'coaching')
    for p in (co or {}).get('people') or []:
        if 'Алехандра' in (p.get('name') or '') or 'Алекса Херр' in (p.get('name') or ''):
            m = p.get('metrics') or {}
            groups = []
            period = None
            for g in m.get('groups') or []:
                rows = [{'label': r.get('label'), 'value': r.get('value'), 'measured': r.get('measured')}
                        for r in (g.get('rows') or [])]
                for r in rows:
                    if r.get('measured'):
                        period = r['measured']
                groups.append({'title': g.get('title'), 'rows': rows})
            out.append(_blk('coaching.alexa', 'coaching', p.get('name') or 'Алехандра Херерра',
                            {'groups': groups}, period))
            break

    return [b for b in out if b]


def _title(obj, fallback):
    t = (obj or {}).get('title') if isinstance(obj, dict) else None
    if not t:
        return fallback
    # strip leading emoji for a slightly shorter attn line? keep as in the dash
    return t


def apply(data: dict) -> dict:
    blocks = collect(data)
    data['data_updates'] = {
        '_note': 't6093u/t6095u: версии блоков еженедельного/ежемесячного сбора. Календарь, задачи, живые мониторы не входят. Баланс — только после PIN, не в этом списке.',
        'blocks': blocks,
    }
    ob = data.get('overall_balance')
    if isinstance(ob, dict):
        payload = {k: v for k, v in ob.items() if k != 'data_ver'}
        ob['data_ver'] = _ver(payload, ob.get('as_of'))
    return data


if __name__ == '__main__':
    import os, sys
    root = os.path.dirname(os.path.abspath(__file__))
    # self-test against data.json if present
    path = os.path.join(root, '..', 'data.json')
    data = json.load(open(path))
    blocks = collect(data)
    for b in blocks:
        print(f"{b['id']:24} {b['ver']}  p={b.get('period')!s:20}  {b['title']}")
    print('total', len(blocks))
