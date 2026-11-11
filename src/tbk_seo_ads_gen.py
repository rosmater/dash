#!/usr/bin/env python3
"""Rost t6013u (11.11.2026): Табакевич — «Оценка сеошников» (Андрей / Кирилл + ссылки CU), «SEO по неделям»,
реклама Google Ads → цена заказа по сайтам, плейсхолдеры «Отзывы» (Google Business Profile) и «Опт ИМ и опт-запросы».
Патчит ТОЛЬКО: eshop.sites[*].seo_who/seo_report/ctx_note/ads, retail.checks_note, eshop.ads_src, ключи seo_team / seo_weekly / reviews / opt_im в src/tbk_blocks.json.
UI (variant-a.html, не ломать при регенерации): t6063u–t6065u/t6067u — пояснения SEO (Товары/Тексты/Ссылки/DR) и методология (Ads/GA4/BAS) в свёрнутом «Пояснения»;
«Скорость по страницам», «Выручка по сайтам», «⭐ Отзывы» — <details> закрыты по умолчанию;
в таблице отзывов не выводим status=closed_perm (закрыто навсегда); closed_temp оставляем серым.
Входы: src/tbk_seo_inputs.json (ручные, только из источников) + таблицы рекламы (GSheet export xlsx, публичная ссылка;
кэш /workspace/tbk-dash-audit/ads/). Ничего не выдумывает: нет расхода → null.
Запуск: python3 src/tbk_seo_ads_gen.py [--offline]"""
import json, os, re, sys, datetime, urllib.request
H = os.path.dirname(os.path.abspath(__file__))
J = os.path.join(H, 'tbk_blocks.json'); I = os.path.join(H, 'tbk_seo_inputs.json')
CACHE = '/workspace/tbk-dash-audit/ads'
X = json.load(open(I))
B = json.load(open(J)); E = B['eshop']
YEAR = 2026
MON = {'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6, 'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12}

def rng(label):
    """'W 26.10–01.11' / 'W 19–25.10' / 'Окт 01–31.10' -> (date_from, date_to)"""
    m = re.search(r'(\d{1,2})(?:\.(\d{2}))?\s*[–-]\s*(\d{1,2})\.(\d{2})', label)
    if not m: return None
    d1, m1, d2, m2 = m.group(1), m.group(2) or m.group(4), m.group(3), m.group(4)
    return datetime.date(YEAR, int(m1), int(d1)), datetime.date(YEAR, int(m2), int(d2))

def load_xlsx(site, S):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, {'hookah': 'hookah', 'palm': 'palm'}[S['kind']] + '-ads-latest.xlsx')
    if '--offline' not in sys.argv:
        try:
            url = f"https://docs.google.com/spreadsheets/d/{S['id']}/export?format=xlsx"
            data = urllib.request.urlopen(url, timeout=60).read()
            if data[:2] == b'PK': open(p, 'wb').write(data)
        except Exception as e:
            print('ads export fail', site, e)
    if not os.path.exists(p):
        alt = [f for f in sorted(os.listdir(CACHE)) if f.startswith(S['kind']) and f.endswith('.xlsx')]
        if not alt: return None, None
        p = os.path.join(CACHE, alt[-1])
    import openpyxl
    return openpyxl.load_workbook(p, data_only=True), datetime.datetime.fromtimestamp(os.path.getmtime(p))

def num(v):
    return float(v) if isinstance(v, (int, float)) else None

def daily(site, S):
    wb, at = load_xlsx(site, S)
    if not wb: return {}, None
    out = {}
    for ym, tab in S['tabs'].items():
        if tab not in wb.sheetnames: continue
        y, mth = map(int, ym.split('-'))
        for r in wb[tab].iter_rows(values_only=True):
            d = r[0] if r else None
            if not isinstance(d, datetime.datetime) or (d.year, d.month) != (y, mth):  # лист-шаблон с чужими датами игнорируем
                continue
            spend = num(r[1])
            if S['kind'] == 'hookah':
                sales, fact = num(r[7]), num(r[13])
            else:
                sales, fact = num(r[6]), None
            out[d.date()] = dict(spend=spend, sales=sales, fact=fact)
    return out, at

n = len(E['periods'])
R = [rng(p) for p in E['periods']]
today = datetime.date.fromisoformat(X.get('as_of')) if X.get('as_of') else datetime.date.today()
mtd = (today.replace(day=1), today)
srcs = []
for s in E['sites']:
    nm = s['name']
    if nm in X.get('seo_who', {}): s['seo_who'] = X['seo_who'][nm]
    if nm in X.get('seo_report', {}): s['seo_report'] = X['seo_report'][nm]
    if nm in X.get('ctx_note', {}): s['ctx_note'] = X['ctx_note'][nm]
    S = X['ads']['sheets'].get(nm)
    if not S:
        s['ads'] = None; continue
    D, at = daily(nm, S)
    def agg(a, b):
        rows = [v for k, v in D.items() if a <= k <= b]
        sp = [v['spend'] for v in rows if v['spend']]
        if not sp: return None
        tot = round(sum(sp), 2)
        sa = sum(v['sales'] or 0 for v in rows if v['spend'])
        fa = sum(v['fact'] or 0 for v in rows if v['spend']) if S['kind'] == 'hookah' else None
        last = max(k for k, v in D.items() if a <= k <= b and v['spend'])
        return dict(spend=tot, sales=int(sa), fact=(int(fa) if fa is not None else None), days=len(sp), last=last.isoformat())
    per = [agg(*r) if r else None for r in R]
    cur = agg(*mtd)
    o1c = s.get('orders') or [None] * n
    s['ads'] = dict(
        spend=[p['spend'] if p else None for p in per],
        sales=[p['sales'] if p else None for p in per],
        fact=[p['fact'] if p else None for p in per],
        cpa=[round(p['spend'] / p['sales'], 2) if p and p['sales'] else None for p in per],
        cpo_1c=[round(p['spend'] / o, 2) if p and o else None for p, o in zip(per, o1c)],
        last=[p['last'] if p else None for p in per],
        mtd=(dict(cur, label=f"{mtd[0].strftime('%d.%m')}–{cur['last'][8:10]}.{cur['last'][5:7]}", cpa=(round(cur['spend'] / cur['sales'], 2) if cur['sales'] else None)) if cur else None),
        sheet=f"https://docs.google.com/spreadsheets/d/{S['id']}/edit", sheet_title=S['title'],
        read_at=at.strftime('%d.%m %H:%M') if at else None)
    srcs.append(f"{nm} — «{S['title']}» (прочитано {s['ads']['read_at']})")
E['ads_src'] = ('Google Ads (Денис Полищук), $: расход — «Рекламний бюджет», продажи кабинета — GA4/«Продажі»; цена заказа = расход ÷ продажи кабинета; '
                'на заказ 1С = расход ÷ все заказы сайта в 1С (все каналы). ' + ' · '.join(srcs) + '. ' + X['ads']['stopped'])
if X.get('retail_checks_note') and B.get('retail'): B['retail']['checks_note'] = X['retail_checks_note']
for k in ('seo_team', 'seo_weekly', 'reviews', 'opt_im'):
    B[k] = X[k]
B['seo_team']['as_of'] = X.get('as_of')
json.dump(B, open(J, 'w'), ensure_ascii=False, indent=1)
print('ok ads', {s['name']: (s.get('ads') or {}).get('spend') for s in E['sites']})
