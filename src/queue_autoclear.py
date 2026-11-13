#!/usr/bin/env python3
"""Rost t4074: QUEUE-пункт закрыли (done/x/closed) → даш сам пересобирается и пушится, без тапа Rost.
Зовётся из tap_relay.py каждые 60 с (под тем же sync/.lock). Сравнивает набор закрытых slug'ов во всех QUEUE.md ботов
с прошлым (sync/queue_closed.json); изменился → build_test_ma.sh + build.sh + push (как sync_dash_taps.py). Иначе — ничего."""
import os, re, json, sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Q = ['/workspace/queue/QUEUE.md', '/workspace/queue-helper/QUEUE.md', '/workspace/queue-of/QUEUE.md', '/workspace/dating/QUEUE.md',
     '/workspace/queue-peptid/QUEUE.md', '/home/box/contacts/knowledge/ig-farm/QUEUE.md',
     '/workspace/queue-lawyer/QUEUE.md', '/home/box/contacts/knowledge/defense-export/QUEUE.md']
ST = f'{R}/sync/queue_closed.json'
cur = {}
for f in Q:
    try:
        for l in open(f, encoding='utf-8'):
            m = re.match(r'^(?:- |## )\[([^\]]*)\]\s*([\w][\w.-]+)', l)
            if m: cur.setdefault(f + '|' + m.group(2).lower(), []).append(m.group(1).strip().lower())
    except FileNotFoundError: pass
closed = sorted(k for k, v in cur.items() if v and all(re.match(r'^(done|x\b|x$|closed|закрыт)', x) for x in v))
prev = json.load(open(ST)) if os.path.exists(ST) else None
if prev != closed: json.dump(closed, open(ST, 'w'), ensure_ascii=False)
if prev is None or set(closed) <= set(prev): print('queue: no new closed'); sys.exit(0)
print('queue: newly closed', sorted(set(closed) - set(prev)))
if '--no-push' in sys.argv: sys.exit(0)
# t6285u: репо = /workspace/dash-gh; sync/queue_closed.json — локальное состояние (в .gitignore), коммитим только сборку
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dash_push import push_with_retry
sys.exit(0 if push_with_retry([], 'sync: QUEUE закрыт → убрано с даша (t4074)') else 1)
