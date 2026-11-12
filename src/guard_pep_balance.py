"""t1111u: сборка без баланса рекламы Пептидов не уходит на сайт.
Если есть /workspace/peptides-dash-monitors/balance.json, то data.json обязан содержать
directions[peptides].ads_monitor.ad_balance, а собранный variant-a.html — pepAdBalHdr."""
import json, os, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
if not os.path.isfile('/workspace/peptides-dash-monitors/balance.json'):
    sys.exit(0)
d = json.load(open(os.path.join(ROOT, 'data.json')))
p = next((x for x in d.get('directions', []) if x.get('id') == 'peptides'), None)
if p is None:
    sys.exit(0)
if not ((p.get('ads_monitor') or {}).get('ad_balance')):
    sys.exit('guard_pep_balance FAIL: в data.json нет peptides.ads_monitor.ad_balance (src устарел или balance.py упал)')
for f in ('src/variant-a.html',):
    if 'pepAdBalHdr' not in open(os.path.join(ROOT, f), encoding='utf-8').read():
        sys.exit(f'guard_pep_balance FAIL: в {f} нет pepAdBalHdr (src устарел — git pull)')
