#!/usr/bin/env python3
"""Rost t5993u/t5994u/t5995u/t5997u/t5999u/t6000u/t6002u/t6004u — блок «Интернет-магазин», «Дропшипперы», «Маркетплейсы».
Патчит ТОЛЬКО ключи eshop / dropship / marketplaces в src/tbk_blocks.json (не трогает decisions/fin).
Входы (правь src/tbk_eshop_inputs.json, потом запускай этот скрипт):
  - товары/тексты/ссылки/DR по сайтам + источник/дата;
  - заказы по сайтам/дропшипперам/МП по периодам (из BAS, без помеченных на удаление);
  - уникальные посетители по сайтам/периодам (GA4) → конверсия = заказы / уник. посетители;
  - скорость: sites-weekly-mega/<последняя дата>/speed.json (загрузка, мин. из 2 прогонов) + src/psi/summary.json (PageSpeed/Lighthouse).
Дропшипперы: авто-фильтр — скрываются, если нет продаж за последние 2 мес. (rolling, по полю monthly {YYYY-MM: выручка}).
Ничего не выдумывает: нет значения → null (на даше пусто/—) + подпись «нет данных»."""
import json, os, glob, datetime
H=os.path.dirname(os.path.abspath(__file__))
J=os.path.join(H,'tbk_blocks.json'); I=os.path.join(H,'tbk_eshop_inputs.json')
B=json.load(open(J)); X=json.load(open(I))
E=B['eshop']; Dr=B['dropship']; M=B['marketplaces']
PG=['home','category','product','sale']; PGN={'home':'Главная','category':'Категория','product':'Товар','sale':'Акции'}
SPK={'tabakevich.co':'tabakevich-co','hookahshop.org':'hookahshop','palmvapeshop.com':'palmvapeshop','felix-shop.com':'felix-shop'}
SPK2={'home':'home','category':'cat','product':'product','sale':'sale'}
# скорость загрузки (weekly mega)
wk=sorted(d for d in glob.glob('/workspace/sites-weekly-mega/2026-*/speed.json'))
SP=json.load(open(wk[-1])) if wk else {}; SPD=os.path.basename(os.path.dirname(wk[-1])) if wk else None
PSI=json.load(open(os.path.join(H,'psi','summary.json'))) if os.path.exists(os.path.join(H,'psi','summary.json')) else {'sites':{}}
def sm(a): 
    s=sum(v for v in a if v is not None) if a and all(v is not None for v in a) else None
    return round(s,2) if s is not None else None
def col(rows,k,n):
    return [sm([ (r.get(k) or [None]*n)[i] for r in rows]) for i in range(n)]
n=len(E['periods'])
for s in E['sites']:
    x=X['sites'].get(s['name'],{})
    for k in ('products','products_src','texts_last_month','texts_src','links_bought','links_src','dr','dr_src','visitors','visitors_src','orders_src'):
        s[k]=x.get(k)
    s['orders']=x.get('orders',[None]*n)
    s['conv']=[ (round(100*o/v,2) if o is not None and v else None) for o,v in zip(s['orders'],(s.get('visitors') or [None]*n))]
    s.pop('orders_note',None)
    if x.get('orders_note'): s['orders_note']=x['orders_note']
    sp=SP.get(SPK[s['name']],{}); ps=(PSI.get('sites') or {}).get(s['name'],{})
    s['speed']={p:{'load_s':(round(sp[SPK2[p]][2],2) if sp.get(SPK2[p]) else None),
                   'mob':ps.get(p,{}).get('mobile'),'desk':ps.get(p,{}).get('desktop')} for p in PG}
for o in E.get('other',[]):
    x=X.get('other',{}).get(o['name'],{}); o['orders']=x.get('orders',[None]*n); o['orders_src']=x.get('orders_src')
own=E['sites']
E['own_total']={'label':'Итого свои сайты (без МП и дропа)','rev':col(own,'rev',n),'gp':col(own,'gp',n),'orders':col(own,'orders',n)}
vt=col([{'v':s.get('visitors')} for s in own],'v',n)
E['own_total']['conv']=[(round(100*o/v,2) if o is not None and v else None) for o,v in zip(E['own_total']['orders'],vt)]
E['total']['orders']=X.get('total_orders',[None]*n)
E['speed_src']=f"Загрузка — мин. из 2 прогонов curl, weekly-mega {SPD} (tabakevich — через UA-прокси). PageSpeed — {', '.join(sorted({(v.get(st) or {}).get('engine','') for P in (PSI.get('sites') or {}).values() for v in P.values() for st in ('mobile','desktop')}-{''})) or 'нет'} от {PSI.get('date','—')} (PSI API без ключа сегодня в квоте 429 → тот же Lighthouse локально); скрипт src/sites_psi.py"
E['missing']=X.get('missing'); E['src']=X.get('src',E.get('src'))
# дропшипперы: rolling 2 мес.
today=datetime.date.fromisoformat(X.get('as_of')) if X.get('as_of') else datetime.date.today()
m0=today.replace(day=1); prev=(m0-datetime.timedelta(days=1)).replace(day=1)
win={m0.strftime('%Y-%m'),prev.strftime('%Y-%m')}
allD=X['dropship']; vis=[]; hid=[]
for d in Dr.get('all',Dr['list']):
    xd=allD.get(d['name'],{}); d['monthly']=xd.get('monthly',d.get('monthly',{})); d['orders']=xd.get('orders',[None]*n)
    (vis if any((d['monthly'].get(m) or 0)>0 for m in win) else hid).append(d)
Dr['all']=vis+hid; Dr['list']=vis; Dr['hidden']=[d['name'] for d in hid]
Dr['hidden_note']=f"Скрыты (нет продаж за {prev.strftime('%m.%Y')}–{m0.strftime('%m.%Y')}): "+', '.join(Dr['hidden']) if hid else None
names=[m['name'] for m in M['list']]
for nm,xm in X.get('marketplaces',{}).items():
    if nm not in names: M['list'].append({'name':nm,'rev':[None]*n,'gp':[None]*n}); names.append(nm)
# Лада («Интернет направление», еженедельно): каталог по сайтам + полный блок МП (Rost t6007u)
import sys; sys.path.insert(0,H); import lada_sheet as LS
LSN={'tabakevich.co':'Табакевич','hookahshop.org':'Хукашоп','palmvapeshop.com':'Пальма','felix-shop.com':'Феликс'}
for s in E['sites']:
    sec=LSN[s['name']]; v,w=LS.latest(sec,'в наличии'); ad,_=LS.latest(sec,'добавлено'); pr,_=LS.latest(sec,'в акции')
    if v is not None:
        extra=(s.get('products_extra') or X['sites'].get(s['name'],{}).get('products_extra'))
        s['products']=v; s['products_src']=f"Лада «Интернет направление», нед. {w}: в наличии {v}, добавлено {ad if ad is not None else '—'}, в акции {pr if pr is not None else '—'}"+(f"; {extra}" if extra else '')
MPS={'Rozetka':('Розетка',dict(stock='В наличии',notready='зависших в подтверждении',cancel='отменых',cancel_pct='% неуспешных',rev_good='итого хороших',rev_bad='итого плохих',new_good='хороших отзывов 3-5',new_bad='плохих отзывов 1-2',promo='в акции')),
     'Prom':('Пром',dict(stock='в наличии',notready='не в готовности',cancel='отменых',cancel_pct='% неуспешных',sales_uah='сумма продаж',rev_good='Отзывы итого хороших',rev_bad='итого плохих',new_good='хороших отзывов 3-5',new_bad='плохих отзывов 1-2',rating_rev='рейтинг продавца пром отзывы',rating_ord='рейтинг продавца пром заказы',promo='в акции')),
     'Glovo':('Глово',dict(stock='в наличии',sales='количество продаж',sales_uah='сумма продаж',new_good='хороших',new_bad='плохих')),
     'Епицентр':('Эпицентр',dict(stock='в наличии',sales='количество продаж',sales_uah='сумма продаж',rev_good='итого хороших',rev_bad='итого плохих',new_good='хороших отзывов 3-5',new_bad='плохих отзывов 1-2',promo='в акции')),
     'Алло':('Алло',dict(stock='в наличии',sales='количество продаж',sales_uah='сумма продаж',rev_good='итого хороших',rev_bad='итого плохих',new_good='хороших отзывов 3-5',new_bad='плохих отзывов 1-2',promo='в акции'))}
WKP={'W 12–18.10':'12.10–18.10','W 05–11.10':'05.10–11.10'}
for m in M['list']:
    if m['name'] in MPS:
        sec,mp=MPS[m['name']]; i,w=LS.last_week(sec)
        m['lada']={k:LS.latest(sec,lbl,i)[0] for k,lbl in mp.items()}; m['lada_week']=w
        if m['name']=='Glovo':  # заказы Glovo по неделям — из строк Лады (в 1С канала нет)
            m['orders']=[LS.week_val(sec,'количество продаж',WKP[p]) if p in WKP else None for p in M['periods']]
M['src']=X.get('mp_src',M.get('src'))
M['lada_src']=f"Остатки/отмены/отзывы/рейтинг — Лада «Интернет направление» ({LS.SRC}); неделя указана в строке"
# маркетплейсы
for m in M['list']:
    xm=X.get('marketplaces',{}).get(m['name'],{})
    m['orders']=xm.get('orders',m.get('orders',[None]*n)) if m['name']!='Glovo' else m.get('orders')
    for k in ('note','rev','gp'):
        if k in xm: m[k]=xm[k]
json.dump(B,open(J,'w'),ensure_ascii=False,indent=1)
print('ok own_total',E['own_total']['rev'],'hidden',Dr['hidden'])
