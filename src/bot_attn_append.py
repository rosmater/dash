#!/usr/bin/env python3
"""Append one bot_attn.jsonl line. Usage:
  python3 bot_attn_append.py --bot 'ОФ Маркетинг' --need rost|ok --cu 86bcxxx --title '...' [--note '...'] [--rev 'YYYY-MM-DD HH:MM']
"""
import argparse, json, datetime
from pathlib import Path
P = Path(__file__).resolve().parents[1] / 'sync' / 'bot_attn.jsonl'
ap = argparse.ArgumentParser()
ap.add_argument('--bot', required=True)
ap.add_argument('--need', required=True, choices=['rost','ok'])
ap.add_argument('--cu', required=True)
ap.add_argument('--title', required=True)
ap.add_argument('--note', default='')
ap.add_argument('--rev', default='', help='CU task updated (YYYY-MM-DD HH:MM) снимка, к которому относится решение')
a = ap.parse_args()
row = dict(ts=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).isoformat(timespec='seconds'),
           bot=a.bot, need=a.need, cu=a.cu, title=a.title[:160], note=a.note[:300], src='bot', **({'rev': a.rev, 'updated': a.rev} if a.rev else {}))
P.parent.mkdir(exist_ok=True)
with P.open('a') as f: f.write(json.dumps(row, ensure_ascii=False)+'\n')
print('ok', row['need'], row['cu'])
