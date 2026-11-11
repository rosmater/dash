#!/usr/bin/env python3
"""t6097u: подтянуть шаги из STEPS_LOG.md в src/personal_blocks.json (последние 14 дней).
Не выдумывает нули: нет строки в журнале → steps=null. Ноль из лога пишем только если он явно записан.
Цвета как в блоке: <2000 красный, 2000–3999 оранжевый, 4000–6999 жёлтый, ≥7000 зелёный.
"""
from __future__ import annotations
import json, re, datetime, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKS = ROOT / 'src' / 'personal_blocks.json'
LOGS = [
    Path('/home/box/contacts/knowledge/shared-health/notes/STEPS_LOG.md'),
    Path('/home/box/contacts/knowledge/secrets/vault/STEPS_LOG.md'),
]
BOG = datetime.timezone(datetime.timedelta(hours=-5))


def color(n):
    if n is None:
        return None
    if n < 2000:
        return 'red'
    if n < 4000:
        return 'orange'
    if n < 7000:
        return 'yellow'
    return 'green'


def parse_log(path: Path) -> dict:
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding='utf-8').splitlines():
        m = re.match(r'^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d+)\s*\|', line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def main():
    steps_map = {}
    src_used = None
    for p in LOGS:
        m = parse_log(p)
        if m:
            steps_map = m
            src_used = str(p)
            break
    if not steps_map:
        print('no STEPS_LOG rows found')
        sys.exit(0)
    data = json.loads(BLOCKS.read_text())
    today = datetime.datetime.now(BOG).date()
    days = []
    for i in range(13, -1, -1):
        d = today - datetime.timedelta(days=i)
        key = d.isoformat()
        n = steps_map.get(key)  # missing → None, never invent 0
        days.append({'date': key, 'steps': n, 'color': color(n)})
    blk = data.setdefault('steps', {'title': 'Шаги', 'hide_from_helper': True})
    old = blk.get('days') or []
    if old == days and (data.get('fetched_at') or '').startswith(today.isoformat()):
        print('steps already up to date')
        return
    blk['days'] = days
    blk['title'] = blk.get('title') or 'Шаги'
    blk['hide_from_helper'] = True
    blk['src'] = 'iPhone → STEPS_LOG.md · <2000 красный · 2000–3999 оранжевый · 4000–6999 жёлтый · ≥7000 зелёный'
    now = datetime.datetime.now(BOG).strftime('%Y-%m-%dT%H:%M:00-05:00')
    data['fetched_at'] = now
    data['today'] = today.isoformat()
    # keep week_from/month_from sensible
    data['week_from'] = (today - datetime.timedelta(days=today.weekday())).isoformat()
    data['month_from'] = today.replace(day=1).isoformat()
    BLOCKS.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n')
    known = sum(1 for x in days if x['steps'] is not None)
    print(f'updated steps {known}/14 days from {src_used}; fetched_at={now}')


if __name__ == '__main__':
    main()
