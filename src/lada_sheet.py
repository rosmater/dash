#!/usr/bin/env python3
"""Читает еженедельные строки Лады из GSheet «Интернет направление» (1FLOe78_MogdMO6ZlZVo_0VAdXKsbNeQBb1m9q61Nzqg, вкладка «ЧЕК- ЛИСТ»).
Порядок: 1) прямой CSV-экспорт (если доступ по ссылке), 2) свежайший дамп /workspace/tbk-dash-audit/src_ЧЕК-_ЛИСТ.csv
(дамп обновляет бот через коннектор Google Sheets zayavki.ua). Вкладку «Площадки» НЕ читаем (там пароли).
latest(section, label_substr) -> (value, week) для последней недели, где у раздела есть данные."""
import csv, io, os, re, glob, urllib.request, datetime
SID='1FLOe78_MogdMO6ZlZVo_0VAdXKsbNeQBb1m9q61Nzqg'
DUMPS=['/workspace/tbk-dash-audit/src_ЧЕК-_ЛИСТ.csv']
def _load():
    try:
        u=f'https://docs.google.com/spreadsheets/d/{SID}/gviz/tq?tqx=out:csv&sheet='+urllib.parse.quote('ЧЕК- ЛИСТ')
        with urllib.request.urlopen(u,timeout=20) as r:
            t=r.read().decode('utf8')
            if t.startswith('<'): raise ValueError('auth')
            return list(csv.reader(io.StringIO(t))),'GSheet live'
    except Exception: pass
    f=max((p for p in DUMPS if os.path.exists(p)),key=os.path.getmtime)
    return list(csv.reader(open(f))),'дамп '+datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%d.%m %H:%M')
import urllib.parse
R,SRC=_load()
HDR=R[0]; WK=[(i,c.replace('\n','–')) for i,c in enumerate(HDR) if re.fullmatch(r'\s*\d{1,2}\.\d{2}\s*\n\s*\d{1,2}\.\d{2}\s*',c or '')]
def rows(section):
    return [r for r in R if r and r[0].strip().lower()==section.lower()]
def last_week(section):
    rs=rows(section)
    for i,w in reversed(WK):
        if any(i<len(r) and r[i].strip() for r in rs): return i,w
    return None,None
def num(v):
    v=(v or '').replace('\xa0','').replace(' ','').replace(',','.').replace('%','')
    try: return float(v) if '.' in v else int(v)
    except: return None
def latest(section,label,week_idx=None):
    i,w=(week_idx,dict(WK).get(week_idx)) if week_idx is not None else last_week(section)
    rs=rows(section)
    ex=[r for r in rs if r[1].strip().lower()==label.lower()]
    for r in ex or rs:
        if label.lower() in r[1].lower():
            return (num(r[i]) if i is not None and i<len(r) else None), w
    return None,w
def week_val(section,label,week):
    """значение за неделю с подписью week ('12.10–18.10')"""
    for i,w in reversed(WK):
        if w.replace(' ','')==week:
            return latest(section,label,i)[0]
    return None
if __name__=='__main__':
    print(SRC, WK[-3:])
    for s in ['Розетка','Пром','Глово','Эпицентр','Алло','Табакевич','Феликс','Хукашоп','Пальма']: print(s,last_week(s))
