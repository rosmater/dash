#!/usr/bin/env python3
"""Заказы по сайтам / дропшипперам / МП из выгрузки BAS «Заказы покупателей» (и сверка с «Реализации»).
Вход: /workspace/tbk-1c/share-mgr/zakazy_pokupateley_*.xlsx (+ realizacii_*.xlsx). Помеченные на удаление исключаются.
Выход: src/tbk_orders_1c.json {периоды, counts{unit:[...]}, real{unit:[...]}, file, unmapped}; tbk_eshop_gen.py подставляет заказы.
Запуск: python3 src/tbk_orders_1c.py [--print]"""
import glob, os, sys, json, re, datetime as dt, collections, openpyxl
H=os.path.dirname(os.path.abspath(__file__)); SH='/workspace/tbk-1c/share-mgr'
X=json.load(open(os.path.join(H,'tbk_eshop_inputs.json')))
PER=X['bas']['periods']
def prange(p):
    """'W 26.10–01.11' / 'W 19–25.10' / 'Окт 01–31.10' -> (date,date), год 2026"""
    t=re.sub(r'^\S+\s+','',p.strip()); a,b=[x.strip() for x in t.split('–')]
    bd,bm=map(int,b.split('.')); ad,am=(map(int,a.split('.')) if '.' in a else (int(a),bm))
    return dt.date(2026,am,ad),dt.date(2026,bm,bd)
RANGES=[prange(p) for p in PER]
MAP={'tabakevich':'tabakevich.co','hookahshop':'hookahshop.org','palm vapeshop':'palmvapeshop.com','palm':'palmvapeshop.com','felix shop':'felix-shop.com','felix':'felix-shop.com',
     'smokejeen':'SmokeJeen','smok instagram':'SMOK instagram','familysmokes':'Family Smokes','family smokes':'Family Smokes','radus':'Radus','hookario':'Hookario',
     'my opti':'My Opti','vape store ua':'Vape Store UA','rozetka':'Rozetka','розетка':'Rozetka','prom':'Prom','пром':'Prom','епицентр':'Епицентр','эпицентр':'Епицентр','епіцентр':'Епицентр','алло':'Алло','allo':'Алло','glovo':'Glovo','глово':'Glovo'}
def unit(v):
    s=(str(v or '')).strip().lower()
    if s in MAP: return MAP[s]
    for k in sorted(MAP,key=len,reverse=True):
        if k in s: return MAP[k]
    return None
def todate(v):
    if isinstance(v,dt.datetime): return v.date()
    if isinstance(v,dt.date): return v
    s=str(v or '').strip()
    m=re.search(r'(\d{2})\.(\d{2})\.(\d{4})',s)
    return dt.date(int(m[3]),int(m[2]),int(m[1])) if m else None
def load(path):
    ws=openpyxl.load_workbook(path,read_only=True,data_only=True).worksheets[0]
    rows=list(ws.iter_rows(values_only=True)); hi=None
    for i,r in enumerate(rows[:30]):
        cells=[str(c or '').strip().lower() for c in r]
        if any('подраздел' in c for c in cells) and 'дата' in cells: hi=i; break
    if hi is None: raise SystemExit(f'{path}: не нашёл шапку (Дата + Подразделение)')
    hd=[str(c or '').strip().lower() for c in rows[hi]]
    col=lambda *ks: next((j for j,c in enumerate(hd) if any(c==k for k in ks)),None) if any(c in hd for c in ks) else next((j for j,c in enumerate(hd) if any(k in c for k in ks)),None)
    C=dict(date=col('дата'),unit=col('подразделение'),dl=col('пометка удаления'),posted=col('проведен'),num=col('номер'),fin=col('вариант завершения'),state=col('состояние'),ka=col('покупатель','контрагент'),sum=col('сумма'))
    out=[]
    for r in rows[hi+1:]:
        if not r or all(c is None for c in r): continue
        g=lambda k: r[C[k]] if C[k] is not None and C[k]<len(r) else None
        dl=str(g('dl') or '').strip().lower(); po=str(g('posted') or '').strip().lower()
        # помеченный на удаление документ в 1С не может быть проведён → исключаем и пометку, и «Проведен = Ні»
        deleted=dl in ('да','так','true','1','истина','yes') or (C['posted'] is not None and po not in ('так','да','true','1','истина','yes'))
        u=str(g('unit') or ''); grp=re.search(r'\(([^)]*)\)\s*$',u); base=re.sub(r'\s*\([^)]*\)\s*$','',u)
        un=unit(base) if (not grp or 'интернет' in grp[1].lower()) else None
        ka=str(g('ka') or ''); st=str(g('state') or '')
        if un=='tabakevich.co' and (ka.lower().startswith('глово') or st.lower()=='глово'): un='Glovo'
        sm=g('sum'); sm=float(sm) if isinstance(sm,(int,float)) else None
        out.append(dict(date=todate(g('date')),unit_raw=u,unit=un,deleted=deleted,num=g('num'),cancel=str(g('fin') or '').lower().startswith('отмен'),sum=sm,ka=ka,state=st))
    return out,C,hd
def count(recs):
    cnt=collections.defaultdict(lambda:[0]*len(PER)); ok=collections.defaultdict(lambda:[0]*len(PER)); sm=collections.defaultdict(lambda:[0.0]*len(PER))
    seen=set(); un=collections.Counter(); dele=0
    for x in recs:
        if x['deleted']: dele+=1; continue
        if not x['date']: continue
        if x['num'] is not None:
            if x['num'] in seen: continue
            seen.add(x['num'])
        if not x['unit']:
            if any(a<=x['date']<=b for a,b in RANGES): un[str(x['unit_raw'])]+=1
            continue
        for i,(a,b) in enumerate(RANGES):
            if a<=x['date']<=b:
                cnt[x['unit']][i]+=1
                if not x['cancel']: ok[x['unit']][i]+=1
                if x['sum']: sm[x['unit']][i]+=x['sum']
    return dict(cnt),dict(un.most_common(8)),dele,dict(ok),{k:[round(v) for v in a] for k,a in sm.items()}

def last_closed_week(today=None):
    today=today or dt.date.today()
    mon=today-dt.timedelta(days=today.weekday())-dt.timedelta(days=7)
    return mon, mon+dt.timedelta(days=6)
def glovo_block(recs):
    """Суммы/заказы Glovo: контрагенты «Глово …» (все в Tabakevich) или состояние «Глово».
    Состояние «Глово» — только незавершённые; после закрытия становится «Завершен», поэтому фильтр только по состоянию обрезает историю.
    Валюта в выгрузке — грн (UAH), не USD. В counts/sum входят отменённые; cancelled — отдельно."""
    n=len(PER)
    pts=collections.OrderedDict()
    orders=[0]*n; su=[0.0]*n; cn=[0]*n; cs=[0.0]*n
    seen=set(); n_del=0; dmin=None; dmax=None; n_all=0; n_state=0
    for x in recs:
        if x.get('unit')!='Glovo': continue
        if x['deleted']: n_del+=1; continue
        if x['num'] is not None:
            if x['num'] in seen: continue
            seen.add(x['num'])
        if not x['date']: continue
        n_all+=1
        dmin=x['date'] if dmin is None else min(dmin,x['date'])
        dmax=x['date'] if dmax is None else max(dmax,x['date'])
        if str(x.get('state') or '').lower()=='глово': n_state+=1
        name=str(x.get('ka') or '').strip() or 'Глово'
        if name not in pts:
            pts[name]=dict(name=name,orders=[0]*n,sum_uah=[0.0]*n,cancelled=[{'n':0,'sum':0} for _ in range(n)],extra_orders=0,extra_sum=0.0,extra_cancel_n=0,extra_cancel_sum=0.0)
        sm=x['sum'] or 0
        for i,(a,b) in enumerate(RANGES):
            if a<=x['date']<=b:
                orders[i]+=1; su[i]+=sm
                pts[name]['orders'][i]+=1; pts[name]['sum_uah'][i]+=sm
                if x['cancel']:
                    cn[i]+=1; cs[i]+=sm
                    pts[name]['cancelled'][i]['n']+=1; pts[name]['cancelled'][i]['sum']+=sm
    emon,esun=last_closed_week()
    e_n=e_s=e_cn=e_cs=0
    seen2=set()
    for x in recs:
        if x.get('unit')!='Glovo' or x['deleted'] or not x['date']: continue
        if x['num'] is not None:
            if x['num'] in seen2: continue
            seen2.add(x['num'])
        if not (emon<=x['date']<=esun): continue
        sm=x['sum'] or 0
        e_n+=1; e_s+=sm
        if x['cancel']: e_cn+=1; e_cs+=sm
        name=str(x.get('ka') or '').strip() or 'Глово'
        if name not in pts:
            pts[name]=dict(name=name,orders=[0]*n,sum_uah=[0.0]*n,cancelled=[{'n':0,'sum':0} for _ in range(n)],extra_orders=0,extra_sum=0.0,extra_cancel_n=0,extra_cancel_sum=0.0)
        pts[name]['extra_orders']+=1; pts[name]['extra_sum']+=sm
        if x['cancel']: pts[name]['extra_cancel_n']+=1; pts[name]['extra_cancel_sum']+=sm
    def rnd(v): return int(round(v))
    points=[]
    for name,p in pts.items():
        points.append(dict(
            name=name,
            orders=p['orders'],
            sum_uah=[rnd(v) for v in p['sum_uah']],
            cancelled=[{'n':c['n'],'sum':rnd(c['sum'])} for c in p['cancelled']],
            extra={'orders':p['extra_orders'],'sum_uah':rnd(p['extra_sum']),'cancelled':{'n':p['extra_cancel_n'],'sum':rnd(p['extra_cancel_sum'])}}
        ))
    points.sort(key=lambda p:(-(p['sum_uah'][0] if p['sum_uah'] else 0), p['name']))
    return dict(
        currency='UAH',
        currency_src='колонка «Валюта» = грн во всех строках выгрузки «Заказы покупателей» (не USD; USD бывает в отчёте «Валовая прибыль»)',
        filter='подразделение Tabakevich + (покупатель начинается на «Глово» или состояние «Глово»). Состояние «Глово» — только незавершённые; закрытые получают состояние «Завершен», поэтому фильтр только по состоянию даёт лишь текущие открытые.',
        file_dates=f"{dmin.isoformat() if dmin else '—'}–{dmax.isoformat() if dmax else '—'}",
        rows=n_all, state_glovo_open=n_state, deleted_excluded=n_del,
        orders=orders, sum_uah=[rnd(v) for v in su],
        cancelled=[{'n':cn[i],'sum':rnd(cs[i])} for i in range(n)],
        points=points,
        week_extra=dict(
            label=(f"W {emon.day:02d}–{esun.day:02d}.{esun.month:02d}" if emon.month==esun.month else f"W {emon.day:02d}.{emon.month:02d}–{esun.day:02d}.{esun.month:02d}"),
            start=emon.isoformat(), end=esun.isoformat(),
            orders=e_n, sum_uah=rnd(e_s), cancelled={'n':e_cn,'sum':rnd(e_cs)}
        )
    )
res={'periods':PER,'generated':dt.datetime.now().isoformat(timespec='minutes')}
z=sorted(glob.glob(f'{SH}/zakazy_pokupateley_*.xlsx'),key=os.path.getmtime)
if not z: raise SystemExit('нет файла заказов')
recs,C,hd=load(z[-1]); res['file']=os.path.basename(z[-1]); res['columns']=hd
res['counts'],res['unmapped'],res['deleted_excluded'],res['not_cancelled'],res['sum_uah']=count(recs); res['rows']=len(recs)
res['glovo']=glovo_block(recs)
r=sorted(glob.glob(f'{SH}/realizacii_*.xlsx'),key=os.path.getmtime)
if r:
    rr,_,_=load(r[-1]); res['real_file']=os.path.basename(r[-1]); res['real'],res['real_unmapped'],res['real_deleted_excluded'],_,res['real_sum_uah']=count(rr)
json.dump(res,open(os.path.join(H,'tbk_orders_1c.json'),'w'),ensure_ascii=False,indent=1)
print(json.dumps({k:res[k] for k in res if k!='columns'},ensure_ascii=False,indent=1)[:4000])
