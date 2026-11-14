#!/usr/bin/env python3
"""t6454u: script-first ClickUp → dash snapshots (no LLM). Boards «Сегодня у меня / Приоритеты 🎯 / Рутина».

Snapshots (same shape as before, build_data._dir_board reads them):
  of_open_tasks.json        space 90144306285 (OF)
  tbk_open_tasks.json       space 90144306286 (Tabakevich)
  personal_open_tasks.json  space 90144414983 (Personal) + extra ids (86ba3c1x4)
  peptides_open_tasks.json  subtasks of 86bcn2ew9 (Peptidos) and 86bb779rw (БОТ: Пептиды) + their open sub-subtasks

Two inputs, one converter:
  A) API (needs a personal ClickUp token: vault clickup-api-token.md or env CLICKUP_TOKEN; never printed)
     incremental: GET /team/{team}/task?space_ids[]=…&date_updated_gt=<last-2min>&include_closed=true&subtasks=true
       → upsert open tasks, drop closed/complete/main/models. 0 changed tasks = 1 cheap call per space, nothing written.
     --full: all open tasks of the space (weekly reconcile: catches deletes / moves to another space).
  B) MCP dumps when there is no token (LLM run = 1 tool call per space + this script, no hand-made JSON):
       python3 src/cu_snap_sync.py --dump of=/path/filter_tasks.json [--dump tbk=…] [--full]

Rules kept: empty priority → normal (t6235u; with token also written to ClickUp), hang_since kept from the previous
snapshot for tasks without due (new ones get today) → «висит N дн.» (t6417u/t6421u); Frecuencia periódica → recurring.
Snapshot is written only if tasks changed (or fetched_at older than 12 h) → no empty commits.

  python3 src/cu_snap_sync.py --auto      # tap_relay: no token → exit 0 silently; with token: incremental, build+push on change
  python3 src/cu_snap_sync.py --dry-run   # show what would change
Exit: 0 ok (changed or not), 10 nothing changed (non-auto), 2 no token and no dumps, 1 error.
"""
from __future__ import annotations
import argparse, datetime, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parent
sys.path.insert(0, str(HERE))
from cu_fix_empty_priority import load_token, set_priority_normal  # noqa: E402

API = 'https://api.clickup.com/api/v2'
TEAM = '9014731752'
BOG = datetime.timezone(datetime.timedelta(hours=-5))
ROST = 60710247
ROLE_FIELD = '1469c8d4-a3b4-4925-958a-7f442d9e002f'
FREQ_FIELD = 'f069396a-529e-48db-a9f3-928bd1ef1639'
ROLE_OPTS = {'95771463-42ea-45fc-8b87-ad4b48108cbf': '🚶GO', '7698f409-40a0-4264-a318-84592847a99c': '📞CALL',
             'ca5fa4c2-8451-4703-92e6-4d29d505426a': 'Control', 'af2515a6-45b6-42b0-a93c-965fa18868d0': 'TO DO',
             'd357bce5-88f1-4501-9b1c-8fb5e6b7b260': '💡REMIND', '8b650b89-b754-4ebd-b2e4-bbcba4d9b70c': '💵 Pago',
             '06d0346a-09cc-41c5-bf1f-0d0589737481': '🥳 Celebraciones'}
FREQ_OPTS = {'aa3d836e-b0e7-4fbb-b3d2-dc0d79bca754': 'periódica', '3ac220d0-b00f-42c5-b688-dc0c0efe59b6': 'única'}
SKIP_STATUS = ('complete', 'closed', 'done', 'main', 'models')
SPACES = {
    'of': dict(file='of_open_tasks.json', space='90144306285'),
    'tbk': dict(file='tbk_open_tasks.json', space='90144306286'),
    'personal': dict(file='personal_open_tasks.json', space='90144414983', extra=['86ba3c1x4']),
    'peptides': dict(file='peptides_open_tasks.json', parents=['86bcn2ew9', '86bb779rw']),
}
STATE = R / 'sync' / 'cu_snap_state.json'  # local only (sync/ is not committed except listed files)
LOG = R / 'sync' / 'relay.log'


def now():
    return datetime.datetime.now(BOG)


def _req(path, token, params=None):
    url = API + path + ('?' + urllib.parse.urlencode(params, doseq=True) if params else '')
    for attempt in range(3):
        try:
            rq = urllib.request.Request(url, headers={'Authorization': token, 'Accept': 'application/json'})
            with urllib.request.urlopen(rq, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(20); continue
            raise
    return {}


def _status(t):
    st = t.get('status')
    if isinstance(st, dict):
        if str(st.get('type') or '').lower() in ('closed', 'done'):
            return 'closed'
        return str(st.get('status') or '').lower()
    return str(st or '').lower()


def is_open(t):
    s = _status(t)
    return not (t.get('date_closed') or s.startswith(SKIP_STATUS) or s == 'closed')


def _cf(t, fid, opts):
    for f in t.get('custom_fields') or t.get('fields') or []:
        if not isinstance(f, dict) or str(f.get('id') or f.get('field_id') or '') != fid:
            continue
        v = f.get('value')
        if v is None or v == '':
            return None
        if isinstance(v, dict):
            return v.get('name') or opts.get(str(v.get('id')), None)
        if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
            for o in (f.get('type_config') or {}).get('options') or []:
                if str(o.get('orderindex')) == str(v):
                    return opts.get(o.get('id'), o.get('name'))
            return None
        return opts.get(str(v), str(v))
    return None


def _who(a):
    if isinstance(a, dict):
        if a.get('id') is not None and int(a['id']) == ROST:
            return 'Rost'
        return (a.get('username') or a.get('email') or str(a.get('id'))).strip()
    return str(a)


def _due(t):
    v = t.get('due_date') or t.get('due_ms')
    if v and str(v).isdigit():
        return datetime.datetime.fromtimestamp(int(v) / 1000, BOG).strftime('%Y-%m-%d')
    d = t.get('due')
    return str(d)[:10] if d and str(d)[:4].isdigit() else None


def convert(t, prev=None, parent_name=None):
    prev = prev or {}
    pr = t.get('priority')
    pr = (pr.get('priority') if isinstance(pr, dict) else pr) or 'normal'  # t6235u
    lst = t.get('list') or {}
    has_cf = 'custom_fields' in t  # API отдаёт поля; MCP filter_tasks — нет → Role/Frecuencia из прошлого снимка
    freq = _cf(t, FREQ_FIELD, FREQ_OPTS) if has_cf else (t.get('freq') or prev.get('freq'))
    role = _cf(t, ROLE_FIELD, ROLE_OPTS) if has_cf else (t.get('role') or prev.get('role'))
    due = _due(t)
    out = dict(id=t['id'], name=t.get('name') or '', status=_status(t), priority=pr, due=due,
               assignees=[_who(a) for a in t.get('assignees') or []],
               list=lst.get('name') if isinstance(lst, dict) else (lst or prev.get('list') or ''),
               url='https://rosmater.github.io/cu/?t=' + t['id'],
               tags=[x.get('name') if isinstance(x, dict) else str(x) for x in t.get('tags') or []],
               freq=freq, recurring=True if (str(freq or '').lower().startswith('peri') or (not has_cf and prev.get('recurring') is True)) else None)
    if role:
        out['role'] = role
    if prev.get('hang_since') or not due:
        out['hang_since'] = prev.get('hang_since') or now().strftime('%Y-%m-%d')
    par = parent_name or prev.get('parent')
    if t.get('parent') and par:
        out['parent'] = par
    return out


def pull_space(token, space, since_ms=None):
    tasks, page = [], 0
    while page < 60:
        p = {'space_ids[]': [space], 'subtasks': 'true', 'page': page,
             'include_closed': 'true' if since_ms else 'false'}
        if since_ms:
            p['date_updated_gt'] = int(since_ms)
        body = _req(f'/team/{TEAM}/task', token, p)
        batch = body.get('tasks') or []
        tasks += batch
        if body.get('last_page') or len(batch) < 100:
            break
        page += 1
    return tasks


def pull_peptides(token, parents):
    out = []
    for pid in parents:
        body = _req(f'/task/{pid}', token, {'include_subtasks': 'true'})
        for st in body.get('subtasks') or []:
            out.append((st, body.get('name')))
            sub = _req(f'/task/{st["id"]}', token, {'include_subtasks': 'true'})
            for ss in sub.get('subtasks') or []:
                out.append((ss, st.get('name')))
    return out


def load_dump(path):
    raw = Path(path).read_text(encoding='utf-8')
    i = raw.find('{"tasks"')
    d, _ = json.JSONDecoder().raw_decode(raw[i:] if i >= 0 else raw.strip())  # обёртка коннектора до/после JSON
    if isinstance(d, dict) and d.get('has_more'):
        print(f'cu_snap_sync: {Path(path).name} has_more=true — дочитай page={d.get("next_page")} и передай все файлы через запятую', file=sys.stderr)
    return d.get('tasks') if isinstance(d, dict) else d


def merge(snap, rows, full):
    """rows = [(clickup_task, parent_name)]. Returns new task list."""
    prev = {t['id']: t for t in snap.get('tasks') or []}
    if full:
        keep = {}
    else:
        keep = dict(prev)
    for t, pn in rows:
        if not t.get('id'):
            continue
        if not is_open(t):
            keep.pop(t['id'], None)
            continue
        keep[t['id']] = convert(t, prev.get(t['id']), pn)
    order = [i for i in prev if i in keep] + [i for i in keep if i not in prev]
    return [keep[i] for i in order]


def write_if_changed(key, tasks, src, dry):
    f = HERE / SPACES[key]['file']
    snap = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
    old = snap.get('tasks') or []
    try:
        age_h = (now() - datetime.datetime.fromisoformat(str(snap.get('fetched_at')))).total_seconds() / 3600
    except Exception:
        age_h = 99
    changed = old != tasks
    if not changed and age_h < 12:
        return False
    if dry:
        print(f'{key}: would write {len(tasks)} (was {len(old)}), changed={changed}')
        return changed
    snap['tasks'] = tasks
    snap['fetched_at'] = now().strftime('%Y-%m-%dT%H:%M:%S-05:00')
    snap['src'] = src
    f.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{key}: {len(old)} → {len(tasks)} tasks, changed={changed}')
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', action='append', default=[], help='key=path MCP filter_tasks dump (no token mode)')
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--only', help='comma list of keys')
    ap.add_argument('--auto', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-push', action='store_true')
    a = ap.parse_args()
    keys = [k for k in (a.only.split(',') if a.only else SPACES)]
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    dumps = dict(x.split('=', 1) for x in a.dump)
    token = None if dumps else load_token()
    if a.auto:
        # t6454u: tap_relay зовёт каждую минуту; реальная работа — раз в 2 ч с 06:00 до 22:00 Богота,
        # по вторникам первый проход полный (сверка удалённых/перенесённых). Без токена — тихий выход.
        if not token:
            return 0
        h, last = now(), state.get('_auto_at', 0)
        if not (6 <= h.hour < 22) or time.time() - last < 115 * 60:
            return 0
        state['_auto_at'] = time.time()
        if h.weekday() == 1 and time.time() - state.get('_full_at', 0) > 6 * 86400:
            a.full = True
            state['_full_at'] = time.time()
        STATE.write_text(json.dumps(state))
    if not token and not dumps:
        print('cu_snap_sync: нет токена ClickUp (vault clickup-api-token.md / CLICKUP_TOKEN) и нет --dump', file=sys.stderr)
        return 2
    changed_files, t0 = [], int(time.time() * 1000)
    for k in keys:
        cfg = SPACES[k]
        f = HERE / cfg['file']
        snap = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
        try:
            if k in dumps:
                rows = [(t, None) for pth in dumps[k].split(',') for t in load_dump(pth)]  # несколько страниц: key=p0.json,p1.json
                full = a.full
                src = f'cu_snap_sync MCP filter_tasks ' + (f'space {cfg["space"]}' if cfg.get('space') else 'subtasks ' + '+'.join(cfg.get('parents') or [])) + (' full' if a.full else ' merge')  # id пространства — маркер verify_live
            elif not token:
                continue
            elif cfg.get('parents'):
                rows, full, src = pull_peptides(token, cfg['parents']), True, 'cu_snap_sync API subtasks ' + '+'.join(cfg['parents'])
            else:
                since = None if a.full else state.get(k)
                rows = [(t, None) for t in pull_space(token, cfg['space'], since - 120000 if since else None)]
                full = since is None
                src = f'cu_snap_sync API space {cfg["space"]} ' + ('full' if full else 'incremental date_updated_gt')
                for tid in cfg.get('extra') or []:
                    rows.append((_req(f'/task/{tid}', token), None))
            if token:  # t6235u: пустой приоритет → normal и в ClickUp
                for t, _ in rows:
                    if is_open(t) and not t.get('priority') and not a.dry_run:
                        try:
                            set_priority_normal(t['id'], token)
                        except Exception as e:
                            print('priority fail', t['id'], type(e).__name__, file=sys.stderr)
            tasks = merge(snap, rows, full)
            if write_if_changed(k, tasks, src, a.dry_run):
                changed_files.append('src/' + cfg['file'])
            if token and not a.dry_run:
                state[k] = t0
        except Exception as e:
            print(f'cu_snap_sync {k}: {type(e).__name__} {str(e)[:200]}', file=sys.stderr)
    if not a.dry_run:
        STATE.write_text(json.dumps(state))
    if not changed_files:
        print('cu_snap_sync: без изменений')
        return 0 if a.auto else 10
    if a.dry_run or a.no_push:
        return 0
    import dash_push
    ok = dash_push.push_with_retry(changed_files, 'sync: ClickUp → доски (cu_snap_sync, без LLM) · ' + ', '.join(Path(x).stem for x in changed_files))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
