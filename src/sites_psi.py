#!/usr/bin/env python3
"""Google PageSpeed Insights по страницам 4 сайтов (Rost t5993u).
Запуск: python3 src/sites_psi.py  -> src/psi/raw/<date>/*.json + src/psi/summary.json
URL страниц берутся из /home/box/contacts/knowledge/<site>/data/urls.json.
Ключ API не обязателен; при 429 — повтор с backoff. Еженедельный рефреш."""
import json, os, subprocess, gzip, sys, time, datetime, urllib.request, urllib.parse, concurrent.futures as cf
KB='/home/box/contacts/knowledge'
SITES={'tabakevich.co':'tabakevich-co','hookahshop.org':'hookahshop','palmvapeshop.com':'palmvapeshop','felix-shop.com':'felix-shop'}
PAGES=['home','category','product','sale']
HERE=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(HERE,'psi')
DAY=datetime.date.today().isoformat(); RAW=os.path.join(OUT,'raw',DAY); os.makedirs(RAW,exist_ok=True)
KEY=os.environ.get('PSI_KEY','')
def slim(d):
    lh=d.get('lighthouseResult',{}); a=lh.get('audits',{})
    for k in ('final-screenshot','screenshot-thumbnails','full-page-screenshot'): a.pop(k,None)
    lh.pop('fullPageScreenshot',None); lh.pop('i18n',None); return d
def run(site,page,url,strat):
    fn=os.path.join(RAW,f"{SITES[site]}-{page}-{strat}.json")
    if os.path.exists(fn+'.gz') and '--force' not in sys.argv:
        return site,page,strat,json.load(gzip.open(fn+'.gz','rt'))
    err='PSI API: квота без ключа исчерпана (429) — локальный Lighthouse' if not int(os.environ.get('PSI_TRIES','2')) else None
    q={'url':url,'strategy':strat,'category':'performance'}
    if KEY:q['key']=KEY
    u='https://www.googleapis.com/pagespeedonline/v5/runPagespeed?'+urllib.parse.urlencode(q)

    for i in range(int(os.environ.get('PSI_TRIES','2'))):
        try:
            with urllib.request.urlopen(u,timeout=180) as r: d=json.load(r)
            json.dump(slim(d),gzip.open(fn+'.gz','wt')); return site,page,strat,d
        except urllib.error.HTTPError as e:
            err=f'HTTP {e.code}: {e.read()[:300].decode("utf8","ignore")}'
            if e.code in (429,500,503): time.sleep(20*(i+1)); continue
            break
        except Exception as e:
            err=str(e)[:300]; time.sleep(10*(i+1))
    # fallback: локальный Lighthouse (тот же движок, что PSI), если квота PSI без ключа исчерпана
    lfn=fn.replace('.json','.lh.json')
    cmd=['lighthouse',url,'--quiet','--only-categories=performance','--output=json','--output-path='+lfn,
         '--chrome-flags=--headless=new --no-sandbox --disable-gpu','--max-wait-for-load=60000']
    if strat=='desktop':cmd.insert(2,'--preset=desktop')
    try:
        subprocess.run(cmd,timeout=240,capture_output=True)
        lh=json.load(open(lfn)); d={'lighthouseResult':lh,'_engine':'local-lighthouse '+lh.get('lighthouseVersion',''),'_psi_error':err}
        json.dump(slim(d),gzip.open(fn+'.gz','wt')); os.remove(lfn); return site,page,strat,d
    except Exception as e:
        return site,page,strat,{'error':(err or '')+' | LH: '+str(e)[:200]}
def pick(d):
    if 'error' in d: return {'error':d['error']}
    lh=d.get('lighthouseResult',{}); a=lh.get('audits',{}); le=d.get('loadingExperience',{}).get('metrics',{})
    reqs=((a.get('network-requests') or {}).get('details') or {}).get('items') or []
    if any('/cdn-cgi/challenge-platform/' in (x.get('url') or '') for x in reqs):
        return {'error':'Cloudflare challenge: замерена страница проверки, а не сайт — невалидно','engine':d.get('_engine','PSI API')}; le=d.get('loadingExperience',{}).get('metrics',{})
    g=lambda k:(a.get(k) or {}).get('numericValue')
    sc=(lh.get('categories',{}).get('performance') or {}).get('score')
    return {'score':round(sc*100) if sc is not None else None,
      'lcp_s':round(g('largest-contentful-paint')/1000,2) if g('largest-contentful-paint') is not None else None,
      'cls':round(g('cumulative-layout-shift'),3) if g('cumulative-layout-shift') is not None else None,
      'tbt_ms':round(g('total-blocking-time')) if g('total-blocking-time') is not None else None,
      'fcp_s':round(g('first-contentful-paint')/1000,2) if g('first-contentful-paint') is not None else None,
      'inp_ms_field':(le.get('INTERACTION_TO_NEXT_PAINT') or {}).get('percentile'),
      'lcp_ms_field':(le.get('LARGEST_CONTENTFUL_PAINT_MS') or {}).get('percentile'),
      'url':lh.get('finalUrl') or d.get('id'),'fetched':lh.get('fetchTime'),
      'engine':d.get('_engine','PSI API'),
      'runtime_error':(lh.get('runtimeError') or {}).get('message')}
def main():
    jobs=[]
    for site,kb in SITES.items():
        urls=json.load(open(f'{KB}/{kb}/data/urls.json'))
        for p in PAGES:
            if urls.get(p):
                for s in ('mobile','desktop'): jobs.append((site,p,urls[p],s))
    res={}
    with cf.ThreadPoolExecutor(2) as ex:
        for site,page,strat,d in ex.map(lambda j:run(*j),jobs):
            res.setdefault(site,{}).setdefault(page,{})[strat]=pick(d)
            print(site,page,strat,res[site][page][strat].get('score'),res[site][page][strat].get('error','')[:80] if 'error' in res[site][page][strat] else '',flush=True)
    json.dump({'date':DAY,'source':'Google PageSpeed Insights v5 (lab Lighthouse; INP — полевые CrUX, если есть)','sites':res},open(os.path.join(OUT,'summary.json'),'w'),ensure_ascii=False,indent=1)
if __name__=='__main__':main()
