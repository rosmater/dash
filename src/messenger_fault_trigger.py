#!/usr/bin/env python3
"""Rost t6387u: если монитор мессенджеров в состоянии «сбой», скрипт (без LLM)
один раз POST в queue-resume-15-webhook и пишет Clear-TZ пункт в QUEUE.
Один и тот же signature — не чаще раза в 60 минут.

Usage:
  python3 src/messenger_fault_trigger.py
  python3 src/messenger_fault_trigger.py --data /path/data.json
  python3 src/messenger_fault_trigger.py --simulate-fault --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BOG = timezone(timedelta(hours=-5))
ROOT = Path('/workspace/dash-gh')
SRC = ROOT / 'src'
RECON = SRC / 'messengers_reconcile.json'
DATA = ROOT / 'data.json'
DATA_TEST = ROOT / 'data-test-ma.json'
STATE = Path('/workspace/queue/logs/messenger-fault-trigger-state.json')
LOG = Path('/workspace/queue/logs/messenger-fault-trigger.log')
QUEUE = Path('/workspace/queue/QUEUE.md')
WEBHOOK_URL = Path('/workspace/queue/bin/webhook-resume-15min.url')
WEBHOOK_AUTH = Path('/workspace/queue/bin/webhook-resume-15min.auth')
HANDLER = Path('/workspace/queue/comms-action-handler.json')
DEDUP_SEC = 60 * 60
SIM_DETAIL = 'SIMULATED t6387u test'
# Live test hook (t6390u): if this file exists, treat its text as a monitor fault.
# Harmless no-op when the flag is absent. Does not touch watcher/reconcile data.
# Remove the file to clear the test fault.
TEST_FLAG = Path('/workspace/dash-gh/src/messenger_fault_TEST.flag')

LIVE_CH = [
    ('wa_ukr', 'WhatsApp UKR', 'WA UKR'),
    ('wa_esp', 'WhatsApp ESP', 'WA ESP'),
    ('tg', 'Telegram', 'TG'),
    ('viber', 'Viber', 'Vib'),
    ('ig', 'Instagram', 'IG'),
]


def _now() -> datetime:
    return datetime.now(BOG)


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f'[{_now():%F %T %Z}] {msg}\n'
    try:
        with LOG.open('a', encoding='utf-8') as f:
            f.write(line)
    except OSError:
        pass


def _handler_ok() -> bool:
    try:
        d = json.loads(HANDLER.read_text())
        return (d.get('enabled') is True
                and d.get('mode') == 'action_only_no_resume'
                and d.get('routine') == 'queue-resume-15-webhook'
                and bool(d.get('verified_by')))
    except Exception:
        return False


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def _watchers_from_data(data) -> dict:
    if not isinstance(data, dict):
        return {}
    if isinstance(data.get('watchers'), dict) and data['watchers']:
        return data['watchers']
    for t in data.get('directions') or []:
        if isinstance(t, dict) and isinstance(t.get('watchers'), dict) and t['watchers']:
            return t['watchers']
    return {}


def _recon_from_data(data) -> dict:
    if not isinstance(data, dict):
        return {}
    if isinstance(data.get('reconcile'), dict):
        return data['reconcile']
    for t in data.get('directions') or []:
        if isinstance(t, dict) and isinstance(t.get('reconcile'), dict):
            return t['reconcile']
    return {}


def _parse_at(s: str):
    if not s:
        return None
    s = str(s).strip()
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=BOG)
        return dt
    except Exception:
        pass
    # "2026-11-13 09:36 Bogotá"
    try:
        core = s.replace(' Bogotá', '').replace('Bogota', '').strip()
        if len(core) >= 16:
            dt = datetime.strptime(core[:16], '%Y-%m-%d %H:%M').replace(tzinfo=BOG)
            return dt
    except Exception:
        return None
    return None


def _bog_mins(now: datetime) -> int:
    local = now.astimezone(BOG)
    return local.hour * 60 + local.minute


def _required_slot(now: datetime):
    local = now.astimezone(BOG)
    slot = local.replace(hour=9, minute=0, second=0, microsecond=0)
    thresh = slot - timedelta(minutes=30)
    deadline = local.replace(hour=10, minute=30, second=0, microsecond=0)
    return slot, thresh, deadline


def _live_at(recon: dict, watchers: dict, ch_name: str, ck: str):
    ch = (recon.get('channels') or {}).get(ck) or {}
    w = watchers.get(ch_name) or {}
    return ch.get('at_bogota') or ch.get('at') or ch.get('at_label') or w.get('live_at') or w.get('live_at_bogota') or ''


def _mism_txt(lab: str, ch: dict, is_tg: bool) -> str:
    dc, ds = ch.get('dash_chats'), ch.get('dash_sum')
    lc, ls = ch.get('live_chats'), ch.get('live_sum')
    note = str(ch.get('note') or '').strip()
    try:
        same = int(dc) == int(lc) and int(ds) == int(ls)
    except Exception:
        same = str(dc) == str(lc) and str(ds) == str(ls)
    vs = 'Новые' if is_tg else 'live'
    if same and note:
        return f'{lab}: {note}'
    if same:
        return f'{lab}: сверка не ок, счётчики совпадают ({dc}/{ds})'
    base = f'{lab} не совпадает (даш {dc}/{ds} vs {vs} {lc}/{ls})'
    return base + (f'; {note}' if note else '')


def _watcher_fault(name: str, lab: str, w: dict) -> str | None:
    if not w or not w.get('st'):
        return f'{lab} вотчер ✗ (нет данных)'
    st = str(w.get('st') or '')
    alive = str(w.get('alive') or '')
    if st in ('ok',):
        return None
    if st == 'warn' and ('процесс жив' in alive or w.get('live_at') or 'live snap' in alive):
        return None
    if st in ('red', 'dead', 'fail', 'down'):
        return f'{lab} вотчер ✗ ({alive or st})'
    # leftover '?' without live confirmation
    if st == 'warn':
        return f'{lab} вотчер ? ({alive or st})'
    return None


def compute_faults(recon: dict, watchers: dict, now: datetime | None = None) -> list[str]:
    now = now or _now()
    details: list[str] = []
    channels = (recon or {}).get('channels') or {}
    mins = _bog_mins(now)
    _slot, thresh, deadline = _required_slot(now)
    night_or_grace = mins >= 23 * 60 or now < deadline
    for ck, name, lab in LIVE_CH:
        ch = channels.get(ck) or {}
        if ch.get('ok') is False:
            details.append(_mism_txt(lab, ch, is_tg=(ck == 'tg')))
        if not night_or_grace:
            at = _parse_at(_live_at(recon, watchers, name, ck))
            if at is None or at < thresh:
                details.append(f'{lab} снимок 09:00 пропущен ({_live_at(recon, watchers, name, ck) or "нет at"})')
        wf = _watcher_fault(name, lab, watchers.get(name) or {})
        if wf:
            details.append(wf)
    if (recon or {}).get('ok') is False and not any('не совпадает' in d or 'сверка не ок' in d or d.startswith('WA') or d.startswith('TG') or d.startswith('Vib') or d.startswith('IG') for d in details):
        note = str((recon or {}).get('note') or '').strip()
        details.append(note or 'сверка мессенджеров: есть сбой')
    # unique, stable order
    out, seen = [], set()
    for d in details:
        d = ' '.join(d.split())
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _sig(details: list[str]) -> str:
    raw = '\n'.join(details).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:16]


def _load_state() -> dict:
    d = _load_json(STATE)
    return d if isinstance(d, dict) else {}


def _save_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(STATE)


def _dedup(sig: str, st: dict, now: datetime) -> bool:
    """Return True if this signature was already fired within DEDUP_SEC."""
    last = st.get('last') or {}
    if last.get('sig') != sig:
        return False
    ts = last.get('ts') or last.get('fired_at')
    try:
        if isinstance(ts, (int, float)):
            age = now.timestamp() - float(ts)
        else:
            dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=BOG)
            age = (now - dt).total_seconds()
        return age < DEDUP_SEC
    except Exception:
        return False


def _append_queue(detail: str, now: datetime) -> str:
    slug = 'messenger-fault-' + now.strftime('%Y%m%d-%H%M')
    line = (f'- [pending] PRIORITY {slug} — messenger monitor fault: {detail}'
            f' — fix headless; in /workspace/dash-gh use `git pull --rebase --autostash`'
            f' (never plain `git pull --rebase`), then src/build.sh + dash_push for YOUR'
            f' files only, report one line\n')
    text = QUEUE.read_text(encoding='utf-8') if QUEUE.exists() else ''
    # don't add a second open item with the same slug
    if slug in text and '[pending]' in text:
        return slug
    lines = text.splitlines(True)
    i = next((k for k, l in enumerate(lines) if l.startswith('- [')), len(lines))
    lines.insert(i, line)
    QUEUE.write_text(''.join(lines), encoding='utf-8')
    return slug


def _remove_queue_slug(slug: str) -> None:
    if not slug or not QUEUE.exists():
        return
    lines = QUEUE.read_text(encoding='utf-8').splitlines(True)
    keep = [l for l in lines if slug not in l]
    if len(keep) != len(lines):
        QUEUE.write_text(''.join(keep), encoding='utf-8')


def _post_webhook(payload: dict) -> tuple[bool, str]:
    if not _handler_ok():
        return False, 'handler-not-ready'
    if not WEBHOOK_URL.exists():
        return False, 'no-url'
    url = WEBHOOK_URL.read_text().strip()
    if not url:
        return False, 'empty-url'
    auth = WEBHOOK_AUTH.read_text().strip() if WEBHOOK_AUTH.exists() else ''
    body = json.dumps(payload, ensure_ascii=False)
    out = Path('/tmp/messenger-fault-webhook.out')
    cmd = [
        'curl', '--connect-timeout', '5', '--max-time', '30',
        '-sS', '-o', str(out), '-w', '%{http_code}',
        '-X', 'POST', url,
        '-H', 'Content-Type: application/json',
        '-d', body,
    ]
    if auth:
        hdr = auth if auth.lower().startswith('authorization:') else 'Authorization: ' + auth
        cmd[-2:-2] = ['-H', hdr]
    try:
        code = subprocess.check_output(cmd, text=True, timeout=35).strip()
        return code.startswith('2'), code
    except Exception as e:
        return False, type(e).__name__


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', help='path to data.json / data-test-ma.json')
    ap.add_argument('--recon', help='path to messengers_reconcile.json')
    ap.add_argument('--dry-run', action='store_true',
                    help='POST webhook (dry_run=true), do not leave a QUEUE item')
    ap.add_argument('--simulate-fault', action='store_true',
                    help='inject a fake fault for testing')
    ap.add_argument('--no-webhook', action='store_true')
    args = ap.parse_args(argv)

    data_path = Path(args.data) if args.data else (DATA if DATA.exists() else DATA_TEST)
    recon_path = Path(args.recon) if args.recon else RECON
    data = _load_json(data_path) or {}
    recon = _recon_from_data(data) or _load_json(recon_path) or {}
    watchers = _watchers_from_data(data)

    now = _now()
    details = compute_faults(recon, watchers, now)
    if TEST_FLAG.exists() and not args.simulate_fault:
        try:
            flag_detail = TEST_FLAG.read_text(encoding='utf-8').strip()
        except OSError:
            flag_detail = ''
        flag_detail = flag_detail or 'TEST flag present — искусственный сбой, удалить'
        details = [flag_detail] + [d for d in details if d != flag_detail]
    if args.simulate_fault:
        details = [SIM_DETAIL]

    if not details:
        print('ok: no messenger monitor fault')
        _log('ok: no fault')
        return 0

    detail = '; '.join(details)
    sig = _sig(details)
    st = _load_state()
    if _dedup(sig, st, now):
        print('dedup: same fault signature within 60 min')
        _log(f'dedup sig={sig}')
        return 0

    payload = {
        'type': 'messenger_fault',
        'detail': detail,
        'source': 'messenger_fault_trigger.py',
        'bot': 'comms',
        'reason': 'messenger_fault',
        'sig': sig,
    }
    if args.dry_run or args.simulate_fault:
        payload['dry_run'] = True

    http = 'skipped'
    fired = False
    if not args.no_webhook:
        fired, http = _post_webhook(payload)
        print('webhook', 'ok' if fired else 'fail', 'HTTP', http)
        _log(f'webhook fired={fired} HTTP={http} sig={sig}')
    else:
        print('webhook skipped')

    slug = ''
    if not args.dry_run and not args.simulate_fault:
        slug = _append_queue(detail, now)
        print('queue', slug)
        _log(f'queue {slug} sig={sig}')
    else:
        print('queue skipped (dry-run/simulate)')

    st['last'] = {
        'sig': sig,
        'detail': detail[:500],
        'ts': now.isoformat(),
        'fired_at': now.timestamp(),
        'http': http,
        'slug': slug,
        'dry_run': bool(args.dry_run or args.simulate_fault),
    }
    _save_state(st)
    print('fired: messenger_fault sig=' + sig)
    return 0 if (fired or args.no_webhook or http == 'skipped') else 1


if __name__ == '__main__':
    sys.exit(main())
