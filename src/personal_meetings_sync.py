#!/usr/bin/env python3
"""Rost t5828u: Personal list timed dues → src/personal_meetings.json (+ optional surgical enc patch).

Sibling to cu_due_sync.py. Call from morning 10:42 / night 22:45 packs after:
  clickup_filter_tasks list_ids=[901413854636] include_closed=false
    due_date_from=<today Bogotá> write_to_file=true  (paginate if has_more)

USAGE:
  python3 /workspace/dashboard-mockup/src/personal_meetings_sync.py <filter.json> [...]
  Flags: --dry (report only), --no-push (write json + patch enc, skip git),
         --no-patch (only rewrite personal_meetings.json).

Filter: open tasks (not main/complete/closed/done) with TIMED due
(HH:MM Bogotá ≠ 04:00) and due date ≥ today Bogotá. Start–end: parse
HH:MM–HH:MM from the name when present; else start=due time, end=+1h.
on_done=comment (drain: «Встреча состоялась (с даша, DD.MM)»).
"""
from __future__ import annotations

import argparse, base64, datetime, json, os, re, shutil, subprocess, sys, unicodedata
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

BOG = datetime.timezone(datetime.timedelta(hours=-5))
MOCK = Path('/workspace/dashboard-mockup')
GH = Path('/workspace/dash-gh')
OUT = MOCK / 'src' / 'personal_meetings.json'
VAULT_MAIN = Path('/home/box/contacts/knowledge/secrets/vault/dashboard-password.md')
VAULT_ASST = Path('/home/box/contacts/knowledge/secrets/vault/dashboard-password-assistant.md')
LIST_ID = '901413854636'
LIST_URL = 'https://app.clickup.com/90144414983/v/li/901413854636'
RANGE_RE = re.compile(r'(\d{1,2}:\d{2})\s*[–—\-]\s*(\d{1,2}:\d{2})')
CLOSED = {'main', 'complete', 'completed', 'closed', 'done'}


def load_blob(txt: str):
    txt = txt.strip()
    try:
        return json.loads(txt)
    except Exception:
        out = []
        for ln in txt.splitlines():
            ln = ln.strip()
            if ln.startswith('{') or ln.startswith('['):
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
        return out


def take_tasks(blob, raw):
    if isinstance(blob, list):
        for x in blob:
            if isinstance(x, dict) and 'tasks' in x:
                take_tasks(x, raw)
            elif isinstance(x, dict) and 'id' in x:
                raw.append(x)
    elif isinstance(blob, dict):
        if 'tasks' in blob:
            raw.extend(blob.get('tasks') or [])
        elif 'id' in blob and 'name' in blob:
            raw.append(blob)


def field(v, k):
    return v.get(k) if isinstance(v, dict) else v


def parse_tasks(files):
    raw = []
    for f in files:
        take_tasks(load_blob(Path(f).read_text()), raw)
    seen, tasks = set(), []
    for t in raw:
        tid, due = t.get('id'), t.get('due_date')
        if not tid or tid in seen or due in (None, '', 0):
            continue
        try:
            due_ms = int(due)
        except Exception:
            continue
        st = (field(t.get('status'), 'status') or '').lower()
        if st in CLOSED or st.startswith('complete'):
            continue
        seen.add(tid)
        tasks.append(dict(
            id=tid,
            name=t.get('name') or '(без названия)',
            url=t.get('url') or f'https://app.clickup.com/t/{tid}',
            status=field(t.get('status'), 'status') or '',
            due_ms=due_ms,
        ))
    tasks.sort(key=lambda x: x['due_ms'])
    return tasks


def to_meetings(tasks, today: str):
    out = []
    for t in tasks:
        dt = datetime.datetime.fromtimestamp(t['due_ms'] / 1000, BOG)
        hm = dt.strftime('%H:%M')
        if hm == '04:00':
            continue
        day = dt.strftime('%Y-%m-%d')
        if day < today:
            continue
        m = RANGE_RE.search(t['name'] or '')
        if m:
            start_hm, end_hm = m.group(1), m.group(2)
        else:
            start_hm = hm
            end_hm = (dt + datetime.timedelta(hours=1)).strftime('%H:%M')
        out.append(dict(
            id=t['id'], name=t['name'], url=t['url'], status=t['status'],
            due=day, due_t=end_hm, start=f'{day}T{start_hm}',
            kind='meeting', on_done='comment', note='',
        ))
    out.sort(key=lambda x: (x['due'], x['start'], x['due_t']))
    return out


def load_pw(vault: Path) -> bytes:
    m = re.search(r'^password:\s*(\S+)', vault.read_text(), re.M)
    if not m:
        raise SystemExit(f'no password in {vault.name}')
    return unicodedata.normalize('NFC', m.group(1).strip()).lower().encode()


def decrypt(path: Path, vault: Path):
    enc = json.loads(path.read_text())
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32,
        salt=base64.b64decode(enc['salt']), iterations=enc['iter'],
    ).derive(load_pw(vault))
    pt = AESGCM(key).decrypt(base64.b64decode(enc['iv']), base64.b64decode(enc['ct']), None)
    return json.loads(pt), enc, key


def encrypt(data, enc, key, path: Path):
    iv = os.urandom(12)
    ct = AESGCM(key).encrypt(iv, json.dumps(data, ensure_ascii=False).encode(), None)
    b = lambda x: base64.b64encode(x).decode()
    path.write_text(json.dumps({
        'v': enc.get('v', 1), 'kdf': enc['kdf'], 'iter': enc['iter'],
        'salt': enc['salt'], 'iv': b(iv), 'ct': b(ct),
    }))


def surgical_patch(meetings, list_url, updated_at):
    for enc_path, vault in [
        (MOCK / 'data.enc.json', VAULT_MAIN),
        (MOCK / 'data-asst.enc.json', VAULT_ASST),
    ]:
        if not enc_path.exists():
            print('skip missing', enc_path.name)
            continue
        data, meta, key = decrypt(enc_path, vault)
        for d in data.get('directions') or []:
            if d.get('id') == 'personal':
                d['scheduled_meetings'] = meetings
                d['meetings_list_url'] = list_url
                d['meetings_fetched_at'] = updated_at
        encrypt(data, meta, key, enc_path)
        print('patched', enc_path.name)
    for f in ['data.enc.json', 'data-asst.enc.json']:
        if (MOCK / f).exists():
            shutil.copy(MOCK / f, GH / f)
    shutil.copy(OUT, GH / 'src' / 'personal_meetings.json')
    if (MOCK / 'src' / 'personal_meetings_sync.py').exists():
        shutil.copy(MOCK / 'src' / 'personal_meetings_sync.py', GH / 'src' / 'personal_meetings_sync.py')
    if (MOCK / 'src' / 'build_data.py').exists():
        shutil.copy(MOCK / 'src' / 'build_data.py', GH / 'src' / 'build_data.py')


def git_push(note: str):
    subprocess.run(['git', 'checkout', 'main'], cwd=GH, check=False, capture_output=True)
    r = subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], cwd=GH, capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(['git', 'rebase', '--abort'], cwd=GH, capture_output=True)
        raise SystemExit(f'git pull --rebase failed: {r.stderr or r.stdout}')
    files = [
        'data.enc.json', 'data-asst.enc.json',
        'src/personal_meetings.json', 'src/personal_meetings_sync.py', 'src/build_data.py',
    ]
    subprocess.run(['git', 'add'] + [f for f in files if (GH / f).exists()], cwd=GH, check=True)
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=GH).returncode == 0:
        print('git: nothing to commit')
        return None
    msg = f'Даш t5828u: personal meetings sync — {note[:100]}'
    subprocess.run(['git', 'commit', '-m', msg], cwd=GH, check=True)
    r = subprocess.run(['git', 'push', 'origin', 'main'], cwd=GH, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f'git push failed (not force-retrying): {r.stderr or r.stdout}')
    sha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=GH, text=True).strip()
    print('pushed', sha)
    return sha


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='+', help='clickup_filter_tasks JSON file(s) for Personal list')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--no-push', action='store_true')
    ap.add_argument('--no-patch', action='store_true')
    a = ap.parse_args()

    today = datetime.datetime.now(BOG).strftime('%Y-%m-%d')
    tasks = parse_tasks(a.files)
    meetings = to_meetings(tasks, today)
    updated_at = datetime.datetime.now(BOG).strftime('%Y-%m-%dT%H:%M:%S-05:00')
    doc = {
        '_doc': OUT.read_text()[:200] if OUT.exists() else 'personal meetings from CU Personal list',
        'updated_at': updated_at,
        'src': f'ClickUp Personal list {LIST_ID}',
        'list_url': LIST_URL,
        'scheduled_meetings': meetings,
    }
    # keep long _doc if present
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text())
            if prev.get('_doc'):
                doc['_doc'] = prev['_doc']
        except Exception:
            pass

    prev_ids = []
    try:
        prev_ids = [x.get('id') for x in json.loads(OUT.read_text()).get('scheduled_meetings') or []]
    except Exception:
        pass
    new_ids = [x['id'] for x in meetings]
    changed = prev_ids != new_ids or True  # always rewrite timestamps; compare content below
    try:
        old = json.loads(OUT.read_text()).get('scheduled_meetings') or []
        changed = [{k: x.get(k) for k in ('id', 'due', 'due_t', 'start', 'name', 'status')} for x in old] != \
                  [{k: x.get(k) for k in ('id', 'due', 'due_t', 'start', 'name', 'status')} for x in meetings]
    except Exception:
        changed = True

    print(f'personal_meetings: {len(meetings)} timed open from today; changed={changed}')
    for m in meetings:
        print(f"  {m['due']} {m['start'][11:]}–{m['due_t']} {m['id']} {m['name'][:60]}")

    if a.dry:
        print('dry: would write', OUT)
        sys.exit(0 if not changed else 0)

    tmp = str(OUT) + '.tmp'
    json.dump(doc, open(tmp, 'w'), ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)
    print('wrote', OUT)

    if a.no_patch:
        sys.exit(0)

    surgical_patch(meetings, LIST_URL, updated_at)
    if a.no_push:
        print('no-push: local patch only')
        sys.exit(0)
    note = f"{len(meetings)} meetings: " + ', '.join(f"{m['id']}@{m['due']}T{m['start'][11:]}" for m in meetings[:5])
    git_push(note or 'refresh')


if __name__ == '__main__':
    main()
