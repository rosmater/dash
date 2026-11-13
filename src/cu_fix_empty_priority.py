#!/usr/bin/env python3
"""t6235u/t6236u: open ClickUp tasks with empty priority → normal (3).

Run on a live filter_tasks pull BEFORE writing dash snapshots
(of_open_tasks.json, cu_dated.json, prio_extra.json, …).

Auth (never printed): env CLICKUP_TOKEN / CLICKUP_API_TOKEN / CLICKUP_API_KEY,
or path in CLICKUP_TOKEN_FILE, or vault file clickup-api-token.md if present.

If there is no token and there are open tasks with null priority, print their
ids and exit 2 unless --assume-api-done (caller already set priority via
clickup_update_task). Logs: «cu_fix_empty_priority: set normal on N open tasks».
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PRIORITY_NORMAL = 3  # ClickUp: 1 urgent, 2 high, 3 normal, 4 low
CLOSED = frozenset({
    'complete', 'completed', 'closed', 'done', 'main', 'models',
})
SRC = Path(__file__).resolve().parent
DEFAULT_SNAPS = (
    SRC / 'of_open_tasks.json',
    SRC / 'cu_dated.json',
    SRC / 'prio_extra.json',
)
VAULT_TOKEN = Path('/home/box/contacts/knowledge/secrets/vault/clickup-api-token.md')
API = 'https://api.clickup.com/api/v2/task/'


def _is_closed(status) -> bool:
    if isinstance(status, dict):
        typ = str(status.get('type') or '').lower()
        if typ in ('closed', 'done'):
            return True
        status = status.get('status')
    st = str(status or '').strip().lower()
    return (not st) is False and (st in CLOSED or st.startswith('complete'))


def _is_null_priority(p) -> bool:
    if p is None or p == '' or p == 0 or p is False:
        return True
    if isinstance(p, str) and p.strip().lower() in ('null', 'none', 'n/a', '-'):
        return True
    if isinstance(p, dict):
        val = p.get('priority', p.get('id', p.get('value')))
        return _is_null_priority(val)
    return False


def _tid(obj: dict):
    return obj.get('id') or obj.get('task_id') or obj.get('cu_id')


def _iter_task_dicts(obj, acc=None):
    """Yield dicts that look like ClickUp / dash snapshot tasks."""
    if acc is None:
        acc = []
        seen = set()
    else:
        seen = None  # unused in nested; caller passes list only
    if isinstance(obj, dict):
        tid = _tid(obj)
        name = obj.get('name') or obj.get('title')
        # dash / API task: has id + (priority key or status+name)
        if tid and isinstance(tid, str) and len(tid) >= 6 and (
            'priority' in obj or (name and 'status' in obj)
        ):
            acc.append(obj)
        for v in obj.values():
            _iter_task_dicts(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _iter_task_dicts(v, acc)
    return acc


def open_null_priority_tasks(tasks) -> list:
    """All open task dicts with empty priority (every occurrence, not unique ids)."""
    out = []
    for t in tasks:
        if not isinstance(t, dict):
            continue
        tid = _tid(t)
        if not tid:
            continue
        if t.get('archived') or t.get('closed') is True:
            continue
        if _is_closed(t.get('status')):
            continue
        if 'priority' not in t and 'prio' not in t:
            continue
        p = t.get('priority', t.get('prio'))
        if not _is_null_priority(p):
            continue
        out.append(t)
    return out


def _token_from_file(path: Path) -> str | None:
    try:
        text = path.read_text()
    except Exception:
        return None
    for line in text.splitlines():
        s = line.strip().strip('`"\'')
        if s.startswith('pk_') or s.startswith('ck_'):
            return s
        if s.lower().startswith('token:'):
            val = s.split(':', 1)[1].strip().strip('`"\'')
            if val:
                return val
    return None


def load_token() -> str | None:
    for key in ('CLICKUP_TOKEN', 'CLICKUP_API_TOKEN', 'CLICKUP_API_KEY'):
        v = (os.environ.get(key) or '').strip()
        if v:
            return v
    tf = (os.environ.get('CLICKUP_TOKEN_FILE') or '').strip()
    if tf:
        tok = _token_from_file(Path(tf))
        if tok:
            return tok
    if VAULT_TOKEN.exists():
        return _token_from_file(VAULT_TOKEN)
    return None


def set_priority_normal(task_id: str, token: str, timeout=30) -> None:
    body = json.dumps({'priority': PRIORITY_NORMAL}).encode()
    req = urllib.request.Request(
        API + task_id,
        data=body,
        method='PUT',
        headers={
            'Authorization': token,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()  # consume; do not log body (may echo metadata)
            if resp.status >= 400:
                raise RuntimeError(f'HTTP {resp.status} for {task_id}')
    except urllib.error.HTTPError as e:
        # do not include response body in the message — may leak fields
        raise RuntimeError(f'HTTP {e.code} for {task_id}') from None


def _mutate_priority(t: dict) -> None:
    if 'priority' in t or 'prio' not in t:
        t['priority'] = 'normal'
    else:
        t['prio'] = 'normal'


def fix_and_mutate(tasks, *, assume_api_done=False, sleep_s=0.15) -> tuple[int, list[str]]:
    """Set priority=normal in ClickUp for open tasks with empty priority.

    Mutates the given task dicts in place on success. Returns (count, ids).
    Raises SystemExit(2) if API token is missing and assume_api_done is false
    and there is at least one open null-priority task.
    """
    targets = open_null_priority_tasks(tasks)
    if not targets:
        print('cu_fix_empty_priority: set normal on 0 open tasks')
        return 0, []
    uniq, seen = [], set()
    for t in targets:
        tid = _tid(t)
        if tid not in seen:
            seen.add(tid)
            uniq.append(tid)
    token = load_token()
    if not token and not assume_api_done:
        print(
            'cu_fix_empty_priority: no API token; '
            f'set clickup_update_task priority=normal on {len(uniq)} open tasks, '
            'then re-run with --assume-api-done: ' + ' '.join(uniq),
            file=sys.stderr,
        )
        raise SystemExit(2)
    if token and not assume_api_done:
        errors = []
        ok = []
        done = set()
        for tid in uniq:
            try:
                set_priority_normal(tid, token)
                done.add(tid)
                ok.append(tid)
                if sleep_s:
                    time.sleep(sleep_s)
            except Exception as e:
                errors.append(f'{tid}: {e}')
        for t in targets:
            if _tid(t) in done:
                _mutate_priority(t)
        if errors:
            print(
                'cu_fix_empty_priority: API errors: ' + '; '.join(errors),
                file=sys.stderr,
            )
            raise SystemExit(1)
        print(
            f'cu_fix_empty_priority: set normal on {len(ok)} open tasks'
            + (': ' + ', '.join(ok) if ok else '')
        )
        return len(ok), ok
    # assume_api_done: snapshot/in-memory only
    for t in targets:
        _mutate_priority(t)
    print(
        f'cu_fix_empty_priority: set normal on {len(uniq)} open tasks'
        + (': ' + ', '.join(uniq) if uniq else '')
        + ' (--assume-api-done, snapshot/in-memory only)'
    )
    return len(uniq), uniq


def load_tasks_from_files(paths: list[Path]) -> tuple[list[dict], dict[Path, object]]:
    blobs = {}
    tasks = []
    for p in paths:
        if not p.exists():
            continue
        blob = json.loads(p.read_text())
        blobs[p] = blob
        tasks.extend(_iter_task_dicts(blob))
    return tasks, blobs


def _detect_indent(text: str) -> int:
    for line in text.splitlines()[1:12]:
        if line.startswith(' '):
            return len(line) - len(line.lstrip(' '))
    return 2


def write_blobs(blobs: dict[Path, object]) -> None:
    for p, blob in blobs.items():
        try:
            indent = _detect_indent(p.read_text())
        except Exception:
            indent = 2
        tmp = str(p) + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(blob, f, ensure_ascii=False, indent=indent)
            f.write('\n')
        os.replace(tmp, p)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('files', nargs='*', type=Path, help='snapshot or filter_tasks JSON')
    ap.add_argument('--dry', action='store_true', help='list ids, do not write API or files')
    ap.add_argument('--write-snapshot', action='store_true', help='write mutated JSON back')
    ap.add_argument(
        '--assume-api-done',
        action='store_true',
        help='do not call the API; only set priority=normal on local objects/files',
    )
    a = ap.parse_args(argv)
    paths = a.files or [p for p in DEFAULT_SNAPS if p.exists()]
    if not paths:
        print('cu_fix_empty_priority: no snapshot files', file=sys.stderr)
        return 1
    tasks, blobs = load_tasks_from_files(paths)
    targets = open_null_priority_tasks(tasks)
    if a.dry:
        ids = [_tid(t) for t in targets]
        print(f'cu_fix_empty_priority: dry {len(ids)} open tasks with empty priority: ' + ' '.join(ids))
        return 0
    n, ids = fix_and_mutate(tasks, assume_api_done=a.assume_api_done)
    if a.write_snapshot and n:
        write_blobs(blobs)
        print('cu_fix_empty_priority: wrote', ', '.join(str(p) for p in blobs))
    return 0


if __name__ == '__main__':
    sys.exit(main())
