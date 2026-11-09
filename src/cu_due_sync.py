#!/usr/bin/env python3
"""Rost t5824u: deterministic CU due → dash calendar/cu_dated sync (no LLM).

Catch Rost UI due moves that the write-on-bot rule misses. Call from existing
morning/night bundles after clickup_filter_tasks — not a new frequent routine.

USAGE (agent / routine):
  1) clickup_filter_tasks assignees=[me], due_date_from=<today Bogotá YYYY-MM-DD>,
     due_date_to=<today+2d>, write_to_file=true  (paginate if has_more)
  2) python3 /workspace/dashboard-mockup/src/cu_due_sync.py <file1> [file2…]
     Exit 10 = timed (in window) + cu_dated dues unchanged → stop (no build/push).
     Exit 0  = snapshot slice and/or cu_dated updated, surgical enc patch pushed.
     Exit ≠0/10 = error.

Window: today 00:00 Bogotá → today+3 00:00 (i.e. today and +2 calendar days).
The filter may be that narrow: the script MERGES into /workspace/cu_cal_dash.json
(replaces only tasks whose due falls in the window; keeps later/earlier rows).

On a change it:
  a) merges the filter into cu_cal_dash.json (canonical timed snapshot)
  b) updates due/due_t/status on existing rows in src/cu_dated.json
  c) rebuilds calendar.events (build_data rules + t5824u: all-day gcal-sync
     titles do NOT block timed CU) and patches cu_dated into data*.enc.json
  d) git -C dash-gh pull --rebase && commit && push (never force)

Flags: --dry (report only), --no-push (patch locally, skip git),
       --out PATH (default /workspace/cu_cal_dash.json).
Also (same packs) personal meetings — TWO filters then sync:
  clickup_filter_tasks list_ids=[901413854636] include_closed=false due_date_from=<today Bogotá> write_to_file=true
  clickup_filter_tasks assignees=[me] include_closed=false custom_fields=[{field_id:1469c8d4-a3b4-4925-958a-7f442d9e002f,operator:ANY,value:["95771463-42ea-45fc-8b87-ad4b48108cbf"]}] write_to_file=true
    # Role option «🚶GO» — statuses=[go] returns 0 (not a list status)
  python3 /workspace/dashboard-mockup/src/personal_meetings_sync.py --personal <personal.json> --go <go.json>
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
CU_DATED = MOCK / 'src' / 'cu_dated.json'
VAULT_MAIN = Path('/home/box/contacts/knowledge/secrets/vault/dashboard-password.md')
VAULT_ASST = Path('/home/box/contacts/knowledge/secrets/vault/dashboard-password-assistant.md')
GCAL = Path('/workspace/gcal_dash.json')


def window_ms(now=None):
    now = now or datetime.datetime.now(BOG)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(days=3)  # today + 2d inclusive
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


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


def is_timed(ms: int) -> bool:
    return datetime.datetime.fromtimestamp(ms / 1000, BOG).strftime('%H:%M') != '04:00'


def parse_filter_tasks(files):
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
        seen.add(tid)
        pr = t.get('priority')
        tasks.append(dict(
            id=tid,
            name=t.get('name') or '(без названия)',
            status=field(t.get('status'), 'status'),
            priority=field(pr, 'priority') if isinstance(pr, dict) else pr,
            due_ms=due_ms,
            list=field(t.get('list'), 'name'),
        ))
    tasks.sort(key=lambda x: x['due_ms'])
    return tasks


def timed_key(tasks, lo=None, hi=None):
    out = set()
    for x in tasks:
        if not is_timed(x['due_ms']):
            continue
        if lo is not None and not (lo <= x['due_ms'] < hi):
            continue
        out.add((x['id'], x['due_ms'], x.get('status')))
    return out


def due_pair(ms: int):
    d = datetime.datetime.fromtimestamp(ms / 1000, BOG)
    return d.strftime('%Y-%m-%d'), d.strftime('%H:%M')


def cu_dated_diffs(tasks):
    try:
        D = json.loads(CU_DATED.read_text())
    except Exception:
        return []
    live = {t['id']: t for t in tasks}
    diffs = []
    for did, rows in (D.get('by_dir') or {}).items():
        for x in rows:
            lt = live.get(x.get('id'))
            if not lt:
                continue
            nd, nt = due_pair(lt['due_ms'])
            st = lt.get('status')
            if (x.get('due'), x.get('due_t')) != (nd, nt) or (st and st != x.get('status')):
                diffs.append((did, x['id'], x.get('due'), x.get('due_t'), nd, nt, st, (x.get('name') or '')[:50]))
    return diffs


def apply_cu_dated(tasks):
    D = json.loads(CU_DATED.read_text())
    live = {t['id']: t for t in tasks}
    n = 0
    for rows in (D.get('by_dir') or {}).values():
        for x in rows:
            lt = live.get(x.get('id'))
            if not lt:
                continue
            nd, nt = due_pair(lt['due_ms'])
            changed = False
            if (x.get('due'), x.get('due_t')) != (nd, nt):
                x['due'], x['due_t'] = nd, nt
                changed = True
            if lt.get('status') and lt.get('status') != x.get('status'):
                x['status'] = lt['status']
                changed = True
            if changed:
                n += 1
    if n:
        D['generated'] = datetime.datetime.now(BOG).strftime('%Y-%m-%d %H:%M')
        src = D.get('source') or ''
        if 'cu_due_sync' not in src:
            D['source'] = (src + '; cu_due_sync').strip('; ')
        tmp = str(CU_DATED) + '.tmp'
        json.dump(D, open(tmp, 'w'), ensure_ascii=False, indent=1)
        os.replace(tmp, CU_DATED)
        gh = GH / 'src' / 'cu_dated.json'
        if gh.exists():
            shutil.copy(CU_DATED, gh)
    return n


def merge_snapshot(prev_tasks, filter_tasks, lo, hi):
    """Replace snapshot rows in [lo,hi) with filter_tasks; keep the rest."""
    kept = [t for t in prev_tasks if not (lo <= t['due_ms'] < hi)]
    # dedupe ids: filter wins
    filt_ids = {t['id'] for t in filter_tasks}
    kept = [t for t in kept if t['id'] not in filt_ids]
    merged = kept + list(filter_tasks)
    merged.sort(key=lambda x: x['due_ms'])
    return merged


def build_cal_events(cu_path: Path):
    _g = json.loads(GCAL.read_text()) if GCAL.exists() else {}
    _cu = json.loads(cu_path.read_text())
    cal_events = []
    for e in _g.get('events', []):
        t = e['title']
        src = 'gcal'
        if ' :: ' in t:
            src = 'clickup'
            t = t.replace('🔄 ', '', 1).split(' :: ')[0]
        cal_events.append(dict(
            src=src, title=t, start=e['start'], end=e['end'], all_day=e['all_day'],
            url=e.get('url'), via='gcal-sync' if src == 'clickup' else None,
        ))
    # t5824u: all-day gcal-sync must not block timed CU
    _seen = {x['title'].strip().lower() for x in cal_events if x['src'] == 'clickup' and not x.get('all_day')}
    for t in _cu.get('tasks', []):
        d = datetime.datetime.fromtimestamp(t['due_ms'] / 1000, BOG)
        if d.strftime('%H:%M') == '04:00':
            continue
        if 'complete' in (t.get('status') or '') or 'closed' in (t.get('status') or ''):
            continue
        nm = re.sub(r'\+?\d[\d \-]{6,}\d', '…', t['name']).strip()
        if nm.lower() in _seen:
            continue
        asg = [a for a in (t.get('assignees') or []) if a] or ['Rost']
        cal_events.append(dict(
            src='clickup', title=nm, start=d.isoformat(), end=None, all_day=False, due=True,
            list=t.get('list'), url=f"https://rosmater.github.io/cu/?t={t['id']}", assignees=asg,
        ))
    cal_events = [x for x in cal_events if not x['all_day']]
    _STOP = {'и', 'в', 'на', 'с', 'по', 'для', 'до', 'от', 'к', '—', '-', '+', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс', 'занятие', 'созвон'}
    _ALIAS = {'тренировка': {'зал', 'турник', 'тренировка'}, 'зал': {'тренировка', 'зал'}}

    def _words(t):
        ws = {w for w in re.findall(r'[\wа-яёА-ЯЁ]+', t.lower()) if len(w) > 2 and w not in _STOP}
        out = set(ws)
        for w in ws:
            out |= _ALIAS.get(w, set())
        return out

    _gc = [x for x in cal_events if x['src'] == 'gcal']
    for c in [x for x in cal_events if x['src'] == 'clickup']:
        cw, cd = _words(c['title']), c['start'][:10]
        best, bs = None, 0
        for g in _gc:
            if g['start'][:10] != cd and (g.get('end') or '')[:10] != cd:
                continue
            sc = len(cw & _words(g['title']))
            if sc and g['start'] <= c['start'] <= (g.get('end') or c['start']):
                sc += 0.5
            if sc > bs:
                best, bs = g, sc
        if best and bs >= 2:
            best.setdefault('cu', []).append(dict(
                title=c['title'], url=c['url'], list=c.get('list'), due=c['start'], assignees=c.get('assignees'),
            ))
            c['linked'] = True
    cal_events = [x for x in cal_events if not x.get('linked')]
    cal_events.sort(key=lambda x: x['start'])
    return cal_events, _g.get('fetched_at'), _cu.get('fetched_at')


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


def surgical_patch(events, cu_at, gcal_at, by_dir):
    for enc_path, vault in [
        (MOCK / 'data.enc.json', VAULT_MAIN),
        (MOCK / 'data-asst.enc.json', VAULT_ASST),
    ]:
        if not enc_path.exists():
            print('skip missing', enc_path.name)
            continue
        data, meta, key = decrypt(enc_path, vault)
        for d in data.get('directions') or []:
            if d.get('id') == 'calendar':
                d['events'] = events
                d['cu_fetched_at'] = cu_at
                if gcal_at and not d.get('gcal_fetched_at'):
                    d['gcal_fetched_at'] = gcal_at
            if d.get('id') in by_dir:
                d['cu_dated'] = by_dir[d['id']]
        encrypt(data, meta, key, enc_path)
        print('patched', enc_path.name)
    for f in ['data.enc.json', 'data-asst.enc.json']:
        shutil.copy(MOCK / f, GH / f)
    if (GH / 'src' / 'cu_dated.json').exists():
        shutil.copy(CU_DATED, GH / 'src' / 'cu_dated.json')
    shutil.copy(MOCK / 'src' / 'build_data.py', GH / 'src' / 'build_data.py')
    shutil.copy(MOCK / 'src' / 'cu_due_sync.py', GH / 'src' / 'cu_due_sync.py')


def git_push(note: str):
    subprocess.run(['git', 'checkout', 'main'], cwd=GH, check=False, capture_output=True)
    r = subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], cwd=GH, capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(['git', 'rebase', '--abort'], cwd=GH, capture_output=True)
        raise SystemExit(f'git pull --rebase failed: {r.stderr or r.stdout}')
    entry = (
        f"## {datetime.datetime.now(BOG).strftime('%Y-%m-%d')} cu_due_sync\n"
        f"- {note}\n"
    )
    for rel in ['CHANGELOG.md', 'docs/CHANGELOG.md']:
        p = GH / rel
        if p.exists():
            head = p.read_text()[:800]
            if note[:40] not in head and 'cu_due_sync' not in head[:200]:
                p.write_text(entry + '\n' + p.read_text())
    files = [
        'data.enc.json', 'data-asst.enc.json', 'src/cu_dated.json',
        'src/build_data.py', 'src/cu_due_sync.py', 'CHANGELOG.md', 'docs/CHANGELOG.md',
    ]
    subprocess.run(['git', 'add'] + [f for f in files if (GH / f).exists()], cwd=GH, check=True)
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=GH).returncode == 0:
        print('git: nothing to commit')
        return None
    msg = f'Даш: cu_due_sync — {note[:120]}'
    subprocess.run(['git', 'commit', '-m', msg], cwd=GH, check=True)
    r = subprocess.run(['git', 'push', 'origin', 'main'], cwd=GH, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f'git push failed (not force-retrying): {r.stderr or r.stdout}')
    sha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=GH, text=True).strip()
    print('pushed', sha)
    return sha


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='+', help='clickup_filter_tasks JSON file(s)')
    ap.add_argument('--out', default='/workspace/cu_cal_dash.json')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--no-push', action='store_true')
    a = ap.parse_args()

    lo, hi = window_ms()
    tasks = parse_filter_tasks(a.files)
    if not tasks:
        sys.exit('cu_due_sync: no tasks with due_date in input')

    # Restrict change detection to the today→+2d window (filter may be wider)
    win_tasks = [t for t in tasks if lo <= t['due_ms'] < hi]
    if not win_tasks:
        # still allow cu_dated diffs for ids present in a wider filter
        win_tasks = tasks

    prev = []
    try:
        prev = json.loads(Path(a.out).read_text()).get('tasks', [])
    except Exception:
        pass

    new_k = timed_key(win_tasks, lo, hi)
    old_k = timed_key(prev, lo, hi)
    timed_changed = new_k != old_k
    dated_diffs = cu_dated_diffs(tasks)
    dated_changed = bool(dated_diffs)

    print(
        f'cu_due_sync: filter={len(tasks)} in_window={len([t for t in tasks if lo <= t["due_ms"] < hi])} '
        f'· timed_changed={timed_changed} · cu_dated_diffs={len(dated_diffs)} '
        f'· window {datetime.datetime.fromtimestamp(lo/1000, BOG):%Y-%m-%d}→'
        f'{datetime.datetime.fromtimestamp(hi/1000, BOG):%Y-%m-%d}'
    )
    if timed_changed:
        added = {k[0] for k in new_k - old_k}
        gone = {k[0] for k in old_k - new_k}
        print(f'  timed +{len(added - gone)} ~{len(added & gone)} -{len(gone - added)}')
    for d in dated_diffs[:8]:
        print(f'  dated {d[1]} {d[2]} {d[3]} → {d[4]} {d[5]} | {d[7]}')

    if not timed_changed and not dated_changed:
        print('no change — exit 10')
        sys.exit(10)

    if a.dry:
        print('dry: would merge snapshot / patch cu_dated / surgical publish')
        sys.exit(0)

    # Merge window slice into snapshot (use only tasks in window from filter)
    slice_tasks = [t for t in tasks if lo <= t['due_ms'] < hi]
    merged = merge_snapshot(prev, slice_tasks, lo, hi)
    now = datetime.datetime.now(BOG)
    snap = dict(fetched_at=now.strftime('%Y-%m-%dT%H:%M-05:00'), tasks=merged)
    tmp = a.out + '.tmp'
    json.dump(snap, open(tmp, 'w'), ensure_ascii=False, indent=2)
    os.replace(tmp, a.out)
    print('→', a.out, f'({len(merged)} tasks)')

    n_dated = apply_cu_dated(tasks) if dated_changed else 0
    print(f'cu_dated rows updated: {n_dated}')

    events, gcal_at, cu_at = build_cal_events(Path(a.out))
    by_dir = json.loads(CU_DATED.read_text()).get('by_dir', {})
    surgical_patch(events, cu_at, gcal_at, by_dir)

    try:
        subprocess.run([
            sys.executable, str(MOCK / 'src' / 'dash_touch_append.py'),
            '--bot', 'Секретарь', '--action', 'edit-data',
            '--note', f'cu_due_sync timed={timed_changed} dated={n_dated}',
            '--files', 'cu_cal_dash.json,data.enc.json,src/cu_dated.json',
        ], check=False)
    except Exception:
        pass

    note = f'timed_changed={timed_changed} dated_rows={n_dated}'
    if a.no_push:
        print('no-push: local patch done,', note)
        sys.exit(0)

    sha = git_push(note)
    print('done', sha or '', note)
    sys.exit(0)


if __name__ == '__main__':
    main()
