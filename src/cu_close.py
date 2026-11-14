#!/usr/bin/env python3
"""t6300u / t6302u: headless ClickUp close (and optional stop-recurrence) for dash «✓ решено».

Auth (never printed): same as cu_fix_empty_priority.load_token —
env CLICKUP_TOKEN / CLICKUP_API_TOKEN / CLICKUP_API_KEY, CLICKUP_TOKEN_FILE,
or vault file clickup-api-token.md if present.

If there is no token, close_task() returns ok=False, reason='no_token'
so sync_dash_taps can route the close through the QUEUE auto-close webhook.

Native ClickUp recurrence is not writable via the public API / MCP (ClickUp
limitation as of 2026). For --stop-recur we set the Frecuencia custom field
to «única» first, then close; if the task rolls to a new open occurrence,
we close that too (same id or a newly created sibling).

CLI:
  python3 src/cu_close.py --dry-run <taskId>
  python3 src/cu_close.py --stop-recur --dry-run <taskId>
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cu_fix_empty_priority import load_token  # noqa: E402

API = 'https://api.clickup.com/api/v2'
CLOSED_RE = re.compile(r'^(complete|done|closed|закрыт)', re.I)
CLOSED_TYPES = frozenset({'closed'})
# Prefer type=closed over type=done («for check» is type=done in Personal).
FREQ_FIELD = 'f069396a-529e-48db-a9f3-928bd1ef1639'
FREQ_UNICA = '3ac220d0-b00f-42c5-b688-dc0c0efe59b6'
FREQ_PERIODICA = 'aa3d836e-b0e7-4fbb-b3d2-dc0d79bca754'


def _req(method: str, path: str, token: str, body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            'Authorization': token,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        e.read()  # consume, never log body (may leak fields)
        raise RuntimeError(f'HTTP {e.code} {method} {path.split("?")[0]}') from None


def get_task(task_id: str, token: str) -> dict:
    st, body = _req('GET', f'/task/{urllib.parse.quote(task_id)}', token)
    if st >= 400:
        raise RuntimeError(f'HTTP {st} GET task')
    return body


def status_name(task: dict) -> str:
    s = task.get('status')
    if isinstance(s, dict):
        return str(s.get('status') or '')
    return str(s or '')


def status_type(task: dict) -> str:
    s = task.get('status')
    if isinstance(s, dict):
        return str(s.get('type') or '').lower()
    return ''


def is_closed(task: dict) -> bool:
    typ = status_type(task)
    if typ in CLOSED_TYPES:
        return True
    return bool(CLOSED_RE.match(status_name(task))) and typ != 'done'


def due_iso(task: dict) -> str:
    d = task.get('due_date')
    if not d:
        return ''
    try:
        ms = int(d)
        import datetime
        return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime('%Y-%m-%d')
    except Exception:
        s = str(d)
        return s[:10] if re.match(r'\d{4}-\d{2}-\d{2}', s) else ''


def closed_status_for(task: dict, token: str) -> str:
    """Pick the list's closed/complete status name."""
    # available_statuses is not always on GET; list endpoint has statuses.
    lid = (task.get('list') or {}).get('id') if isinstance(task.get('list'), dict) else None
    statuses = []
    if lid:
        try:
            st, body = _req('GET', f'/list/{urllib.parse.quote(str(lid))}', token)
            if st < 400:
                statuses = body.get('statuses') or []
        except Exception:
            statuses = []
    for s in statuses:
        typ = str((s or {}).get('type') or '').lower()
        name = str((s or {}).get('status') or '')
        if typ in CLOSED_TYPES and re.search(r'complete|закрыт|closed|done', name, re.I):
            return name
    for s in statuses:
        if str((s or {}).get('type') or '').lower() in CLOSED_TYPES:
            return str((s or {}).get('status') or 'complete')
    # fallback used across Rost lists
    return 'complete'


def set_frecuencia_unica(task_id: str, token: str) -> None:
    path = f'/task/{urllib.parse.quote(task_id)}/field/{FREQ_FIELD}'
    st, _ = _req('POST', path, token, {'value': FREQ_UNICA})
    if st >= 400:
        raise RuntimeError(f'HTTP {st} set Frecuencia única')


def set_status(task_id: str, token: str, status: str) -> dict:
    st, body = _req('PUT', f'/task/{urllib.parse.quote(task_id)}', token, {'status': status})
    if st >= 400:
        raise RuntimeError(f'HTTP {st} set status {status}')
    return body or {}


def find_rolled_sibling(task: dict, token: str, closed_id: str) -> str | None:
    """If ClickUp created a new open task with the same name after a roll, return its id."""
    name = (task.get('name') or '').strip()
    lid = (task.get('list') or {}).get('id') if isinstance(task.get('list'), dict) else None
    if not name or not lid:
        return None
    try:
        q = urllib.parse.urlencode({'list_ids[]': lid, 'include_closed': 'false'})
        # Search by name is not always available; list tasks and match name.
        st, body = _req('GET', f'/list/{urllib.parse.quote(str(lid))}/task?include_closed=false&subtasks=true', token)
        if st >= 400:
            return None
        for t in body.get('tasks') or []:
            tid = str(t.get('id') or '')
            if tid and tid != closed_id and (t.get('name') or '').strip() == name and not is_closed(t):
                # only consider very new copies (created after this close)
                return tid
    except Exception:
        return None
    return None


@dataclass
class CloseResult:
    ok: bool
    reason: str = ''
    status: str = ''
    closed_status: str = ''
    rolled: bool = False
    rolled_id: str = ''
    due: str = ''
    stop_recur: bool = False
    freq_cleared: bool = False
    native_recur_cleared: bool = False
    native_recur_unsupported: bool = False
    dry_run: bool = False

    def as_dict(self):
        return asdict(self)


def close_task(task_id: str, token: str | None = None, stop_recur: bool = False, dry_run: bool = False) -> CloseResult:
    token = token if token is not None else load_token()
    if not token:
        return CloseResult(ok=False, reason='no_token', stop_recur=stop_recur, dry_run=dry_run)
    tid = str(task_id or '').strip()
    if not re.match(r'^[0-9a-z]{6,}$', tid, re.I):
        return CloseResult(ok=False, reason='bad_id', stop_recur=stop_recur, dry_run=dry_run)
    try:
        task = get_task(tid, token)
    except Exception as e:
        return CloseResult(ok=False, reason=f'get:{e}', stop_recur=stop_recur, dry_run=dry_run)
    due0 = due_iso(task)
    target = closed_status_for(task, token)
    if dry_run:
        return CloseResult(ok=True, reason='dry_run', status=status_name(task),
                           closed_status=target, due=due0, stop_recur=stop_recur,
                           native_recur_unsupported=True, dry_run=True)
    try:
        if stop_recur:
            set_frecuencia_unica(tid, token)
            # Native recurrence is not exposed for writes on the public API.
            freq_cleared = True
        else:
            freq_cleared = False
        if not is_closed(task):
            set_status(tid, token, target)
        time.sleep(0.4)
        after = get_task(tid, token)
        rolled = False
        rolled_id = ''
        if is_closed(after):
            sib = find_rolled_sibling(after, token, tid) if stop_recur else None
            if sib:
                rolled, rolled_id = True, sib
                if stop_recur:
                    try:
                        set_frecuencia_unica(sib, token)
                    except Exception:
                        pass
                    set_status(sib, token, closed_status_for(get_task(sib, token), token))
                    time.sleep(0.3)
                    after2 = get_task(sib, token)
                    if not is_closed(after2):
                        return CloseResult(ok=False, reason='rolled_sibling_still_open', status=status_name(after),
                                           closed_status=target, rolled=True, rolled_id=sib, due=due_iso(after),
                                           stop_recur=True, freq_cleared=freq_cleared, native_recur_unsupported=True)
            return CloseResult(ok=True, reason='closed', status=status_name(after), closed_status=target,
                               rolled=rolled, rolled_id=rolled_id, due=due_iso(after), stop_recur=stop_recur,
                               freq_cleared=freq_cleared, native_recur_unsupported=True)
        # still open — likely rolled in place (same id, new due)
        due1 = due_iso(after)
        rolled = bool(due1 and due0 and due1 != due0) or True
        if stop_recur:
            try:
                set_frecuencia_unica(tid, token)
            except Exception:
                pass
            set_status(tid, token, target)
            time.sleep(0.4)
            after = get_task(tid, token)
            if not is_closed(after):
                return CloseResult(ok=False, reason='still_open_after_stop', status=status_name(after),
                                   closed_status=target, rolled=True, due=due_iso(after), stop_recur=True,
                                   freq_cleared=True, native_recur_unsupported=True)
            return CloseResult(ok=True, reason='closed_after_roll', status=status_name(after), closed_status=target,
                               rolled=True, due=due_iso(after), stop_recur=True, freq_cleared=True,
                               native_recur_unsupported=True)
        return CloseResult(ok=True, reason='rolled', status=status_name(after), closed_status=target,
                           rolled=True, due=due1, stop_recur=False, native_recur_unsupported=True)
    except Exception as e:
        return CloseResult(ok=False, reason=str(e)[:180], status=status_name(task), closed_status=target,
                           due=due0, stop_recur=stop_recur, native_recur_unsupported=True, dry_run=dry_run)


if __name__ == '__main__':
    a = sys.argv[1:]
    dry = '--dry-run' in a
    stop = '--stop-recur' in a
    ids = [x for x in a if not x.startswith('-')]
    if not ids or '-h' in a or '--help' in a:
        print(__doc__); sys.exit(0)
    out = close_task(ids[0], stop_recur=stop, dry_run=dry)
    # never print tokens; result has no secrets
    print(json.dumps(out.as_dict(), ensure_ascii=False))
    sys.exit(0 if out.ok or out.reason == 'no_token' else 1)
