#!/usr/bin/env python3
"""Log who touched the dash (HARD Rost t4196). Usage:
  python3 dash_touch_append.py --bot 'Секретарь' --action build|push|edit-html|edit-data|peptide-block|other --note '…' [--files 'a,b']
"""
import argparse, json, datetime
from pathlib import Path
P = Path(__file__).resolve().parents[1] / 'sync' / 'dash_touch.jsonl'
ap = argparse.ArgumentParser()
ap.add_argument('--bot', required=True)
ap.add_argument('--action', required=True)
ap.add_argument('--note', default='')
ap.add_argument('--files', default='')
a = ap.parse_args()
row = dict(
    ts=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).isoformat(timespec='seconds'),
    bot=a.bot, action=a.action, note=a.note[:400],
    files=[x.strip() for x in a.files.split(',') if x.strip()][:20],
)
P.parent.mkdir(exist_ok=True)
with P.open('a') as f:
    f.write(json.dumps(row, ensure_ascii=False) + '\n')
print('touch', row['bot'], row['action'])
