#!/usr/bin/env python3
"""Rost t5952u: Role=🚶GO only → src/personal_meetings.json («📅 Назначенные встречи»).

Sibling to cu_due_sync.py. Call from morning 10:42 / night 22:45 packs after ONE filter:

  Role GO anywhere (Rost «гоу» / статус гоу = physically go; NOT a list status —
  statuses=[go] returns 0). Open, due set, any list:
     clickup_filter_tasks assignees=[me] include_closed=false
       due_date_from=<today Bogotá>
       custom_fields=[{field_id:1469c8d4-a3b4-4925-958a-7f442d9e002f, operator:ANY,
         value:["95771463-42ea-45fc-8b87-ad4b48108cbf"]}]  # Role option «🚶GO»
       write_to_file=true

  python3 /workspace/dash-gh/src/personal_meetings_sync.py --go <go.json>
  (multiple files OK; dedupe by id.)

USAGE:
  python3 …/personal_meetings_sync.py go.json
  Flags: --dry, --no-push, --no-patch,
         --go FILE (repeatable),
         --allow-past (keep past dues — e2e only).
  --personal is accepted but ignored (dropped t5952u: Personal list is not a source).

Rules:
  - Only Role=🚶GO: open (not main/complete/closed/done), due≥today; 04:00 = all-day
    (no time in block/banner «Встреча: <name>»).
  - Exclude: src/meetings_exclude.json (ids + name_re) — бокс/зал kept.
  - Dedupe by id.
  - on_done=comment → drain «Встреча состоялась (с даша, DD.MM)».
"""
from __future__ import annotations

import argparse, base64, datetime, json, os, re, shutil, subprocess, sys, unicodedata
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

BOG = datetime.timezone(datetime.timedelta(hours=-5))
MOCK = Path(__file__).resolve().parents[1]  # t6285u: был /workspace/dashboard-mockup (устарел с 12.11, копировал старый build_data.py поверх dash-gh)
GH = Path('/workspace/dash-gh')


def _cp(a, b):
    # t6285u: MOCK == GH → копировать в себя нельзя (SameFileError); скрипты/build_data.py не копируем вообще
    a, b = Path(a), Path(b)
    if a.resolve() == b.resolve() or a.suffix == '.py':
        return
    shutil.copy(a, b)
OUT = MOCK / 'src' / 'personal_meetings.json'
EXCL = MOCK / 'src' / 'meetings_exclude.json'
VAULT_MAIN = Path('/home/box/contacts/knowledge/secrets/vault/dashboard-password.md')
VAULT_ASST = Path('/home/box/contacts/knowledge/secrets/vault/dashboard-password-assistant.md')
ROLE_GO = '95771463-42ea-45fc-8b87-ad4b48108cbf'
ROLE_FIELD = '1469c8d4-a3b4-4925-958a-7f442d9e002f'
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


def load_exclude():
    ids, cre = set(), None
    if EXCL.exists():
        try:
            j = json.loads(EXCL.read_text())
            ids = {str(x) for x in (j.get('ids') or []) if x}
            pat = (j.get('name_re') or '').strip()
            if pat:
                cre = re.compile(pat, re.I)
        except Exception as e:
            print('warn: meetings_exclude.json:', e)
    return ids, cre


def excluded(t, ids, cre):
    if t['id'] in ids:
        return True
    if cre and cre.search(t.get('name') or ''):
        return True
    return False



def _role_option_id(t):
    for c in t.get('custom_fields') or []:
        if not isinstance(c, dict) or c.get('id') != ROLE_FIELD:
            continue
        v = c.get('value')
        if isinstance(v, dict):
            return str(v.get('id') or '')
        return str(v or '')
    return None


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
        # t5951u/t6060u: if the dump carries custom_fields, require Role=🚶GO.
        # No fallback by due time, title emoji, missing role, or Personal list.
        if 'custom_fields' in t and _role_option_id(t) != ROLE_GO:
            print('skip not-GO', tid, (t.get('name') or '')[:50])
            continue
        seen.add(tid)
        tasks.append(dict(
            id=tid,
            name=t.get('name') or '(без названия)',
            url=t.get('url') or f'https://app.clickup.com/t/{tid}',
            status=field(t.get('status'), 'status') or '',
            due_ms=due_ms,
            list=field(t.get('list'), 'name') or '',
        ))
    tasks.sort(key=lambda x: x['due_ms'])
    return tasks


def task_to_meeting(t, today: str, allow_allday: bool, allow_past: bool):
    dt = datetime.datetime.fromtimestamp(t['due_ms'] / 1000, BOG)
    hm = dt.strftime('%H:%M')
    day = dt.strftime('%Y-%m-%d')
    if day < today and not allow_past:
        return None
    allday = hm == '04:00'
    if allday and not allow_allday:
        return None
    if allday:
        return dict(
            id=t['id'], name=t['name'], url=t['url'], status=t['status'],
            due=day, due_t='', start=day, all_day=True,
            kind='meeting', on_done='comment', note='',
            src='go',
        )
    m = RANGE_RE.search(t['name'] or '')
    if m:
        start_hm, end_hm = m.group(1), m.group(2)
    else:
        start_hm = hm
        end_hm = (dt + datetime.timedelta(hours=1)).strftime('%H:%M')
    return dict(
        id=t['id'], name=t['name'], url=t['url'], status=t['status'],
        due=day, due_t=end_hm, start=f'{day}T{start_hm}', all_day=False,
        kind='meeting', on_done='comment', note='',
        src='go',
    )


def merge_meetings(go_tasks, today: str, allow_past=False):
    ids, cre = load_exclude()
    by_id = {}
    for t in go_tasks:
        if excluded(t, ids, cre):
            continue
        m = task_to_meeting(t, today, allow_allday=True, allow_past=allow_past)
        if m:
            m['src'] = 'go'
            by_id[m['id']] = m
    out = list(by_id.values())
    out.sort(key=lambda x: (x['due'], '1' if x.get('all_day') else '0', x.get('start') or '', x.get('due_t') or ''))
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


def surgical_patch(meetings, updated_at, list_url=''):
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
            _cp(MOCK / f, GH / f)
    for rel in ['src/personal_meetings.json', 'src/personal_meetings_sync.py',
                'src/meetings_exclude.json', 'src/build_data.py',
                'src/cu_due_sync.py']:
        src = MOCK / rel
        if src.exists():
            _cp(src, GH / rel)


def git_push(note: str):
    subprocess.run(['git', 'checkout', 'main'], cwd=GH, check=False, capture_output=True)
    r = subprocess.run(['git', 'pull', '--rebase', '--autostash', 'origin', 'main'], cwd=GH, capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(['git', 'rebase', '--abort'], cwd=GH, capture_output=True)
        raise SystemExit(f'git pull --rebase failed: {r.stderr or r.stdout}')
    files = [
        'data.enc.json', 'data-asst.enc.json',
        'src/personal_meetings.json', 'src/meetings_exclude.json',
        'CHANGELOG.md', 'docs/CHANGELOG.md',  # t6285u: скрипты/build_data.py/html не автокоммитим
    ]
    subprocess.run(['git', 'add'] + [f for f in files if (GH / f).exists()], cwd=GH, check=True)
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=GH).returncode == 0:
        print('git: nothing to commit')
        return None
    msg = f'Даш t5952u: встречи только Role GO — {note[:90]}'
    subprocess.run(['git', 'commit', '-m', msg], cwd=GH, check=True)
    r = subprocess.run(['git', 'push', 'origin', 'main'], cwd=GH, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f'git push failed (not force-retrying): {r.stderr or r.stdout}')
    sha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=GH, text=True).strip()
    print('pushed', sha)
    return sha


def classify_files(positional, personal_flags, go_flags):
    """Return go_files only. --personal is ignored (t5952u)."""
    if personal_flags:
        print('warn: --personal ignored (t5952u: meetings are Role=GO only, any list)')
    return list(go_flags or []) + list(positional or [])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='*', help='Role-GO filter JSON file(s)')
    ap.add_argument('--personal', action='append', default=[], help='IGNORED (t5952u: Personal list is not a source)')
    ap.add_argument('--go', action='append', default=[], help='Role-GO filter file(s)')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--no-push', action='store_true')
    ap.add_argument('--no-patch', action='store_true')
    ap.add_argument('--allow-past', action='store_true', help='keep past dues (e2e)')
    a = ap.parse_args()

    today = datetime.datetime.now(BOG).strftime('%Y-%m-%d')
    gfiles = classify_files(a.files, a.personal, a.go)
    if not gfiles:
        sys.exit('personal_meetings_sync: pass go.json (Role=🚶GO filter dump)')

    go_tasks = parse_tasks(gfiles)
    meetings = merge_meetings(go_tasks, today, allow_past=a.allow_past)
    updated_at = datetime.datetime.now(BOG).strftime('%Y-%m-%dT%H:%M:%S-05:00')
    doc = {
        '_doc': (
            'Rost t5952u: «📅 Назначенные встречи». '
            'Source: Role=🚶GO (field 1469c8d4-a3b4-4925-958a-7f442d9e002f '
            'option 95771463-42ea-45fc-8b87-ad4b48108cbf) any list, open, due≥today; '
            '04:00 = all-day. Exclude: src/meetings_exclude.json. on_done=comment. '
            'Personal list 901413854636 is not a source (созвоны ≠ встречи).'
        ),
        'updated_at': updated_at,
        'src': f'Role GO {ROLE_GO}',
        'list_url': '',
        'scheduled_meetings': meetings,
    }

    try:
        old = json.loads(OUT.read_text()).get('scheduled_meetings') or []
        key = lambda xs: [{k: x.get(k) for k in ('id', 'due', 'due_t', 'start', 'name', 'status', 'all_day')} for x in xs]
        changed = key(old) != key(meetings)
    except Exception:
        changed = True

    print(f'personal_meetings: {len(meetings)} (go_in={len(go_tasks)}); changed={changed}')
    for m in meetings:
        tag = 'all-day' if m.get('all_day') else f"{(m.get('start') or '')[11:]}–{m.get('due_t')}"
        print(f"  {m['due']} {tag} [{m.get('src')}] {m['id']} {m['name'][:55]}")

    if a.dry:
        print('dry: would write', OUT)
        sys.exit(0)

    tmp = str(OUT) + '.tmp'
    json.dump(doc, open(tmp, 'w'), ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)
    print('wrote', OUT)

    if a.no_patch:
        sys.exit(0)

    surgical_patch(meetings, updated_at)
    if a.no_push:
        print('no-push: local patch only')
        sys.exit(0)
    note = f"{len(meetings)} mtg: " + ', '.join(f"{m['id']}@{m['due']}" for m in meetings[:6])
    git_push(note or 'refresh')


if __name__ == '__main__':
    main()
