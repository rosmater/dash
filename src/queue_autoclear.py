#!/usr/bin/env python3
"""Rost t4074: QUEUE-пункт закрыли (done/x/closed) → даш сам пересобирается и пушится, без тапа Rost.
Зовётся из tap_relay.py каждые 60 с (под тем же sync/.lock). Сравнивает набор закрытых slug'ов во всех QUEUE.md ботов
с прошлым (sync/queue_closed.json); изменился → build_test_ma.sh + build.sh + push (как sync_dash_taps.py). Иначе — ничего."""
import os, re, json, sys, shutil, subprocess
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
json.dump(closed, open(ST, 'w'), ensure_ascii=False)
if prev is None or set(closed) <= set(prev): print('queue: no new closed'); sys.exit(0)
print('queue: newly closed', sorted(set(closed) - set(prev)))
if '--no-push' in sys.argv: sys.exit(0)
subprocess.run(['bash', f'{R}/src/build_test_ma.sh'], check=True); subprocess.run(['bash', f'{R}/src/build.sh'], check=True)
G = '/workspace/dash-gh'  # was /workspace/dash-gh, gone after remount 27.10
subprocess.run(['git', '-C', G, 'pull', '-q', '--rebase'], check=True)
for f in ['index.html', 'helper.html', 'variant-a.html', 'data.enc.json', 'data-asst.enc.json', 'data-test-ma.enc.json', 'test-messengers-assistants.html']: shutil.copy(f'{R}/{f}', f'{G}/{f}')
subprocess.run(['git', '-C', G, 'add', '-A'])
if subprocess.run(['git', '-C', G, 'diff', '--cached', '--quiet']).returncode:
    subprocess.run(['git', '-C', G, '-c', 'user.name=rosmater', '-c', 'user.email=rost@rosmater.local', 'commit', '-qm', 'sync: QUEUE закрыт → убрано с даша (t4074)'], check=True)
    subprocess.run(['git', '-C', G, 'push', '-q'], check=True)
print('pushed')
