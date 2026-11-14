#!/usr/bin/env python3
"""Pull workspace ClickUp views «Ros» and «Ros (BOT)» for the dash.

t6351u–t6352u: «Ros bot» is the saved VIEW «Ros (BOT)» (8cn3rz8-3574), sitting
next to «Ros» (8cn3rz8-1914) on the work workspace 9014731752 — not a list.

Exact saved filters (AND, show_closed=false), read from the view definition:

  «Ros (BOT)» 8cn3rz8-3574:
    1) status NOT closed
    2) assignee ANY Rost (60710247)
    3) custom field BOT R (cf_8f51644a-de28-4b84-a204-f0ec1903f337) IS SET
       (the view lists five option ids that existed when it was saved —
       Секретарь, Помощник по всему, Оборонный проект, Юрист / Адвокат,
       ОФ Маркетинг. Operator is IS SET, so later options Д and Пептид also
       match. Role, tag, and «Передать на бота» are NOT in this filter.)

  «Ros» 8cn3rz8-1914 — same open + assignee=Rost, plus dueDate earlier,
    plus BOT R NOT SET (tasks Rost has not moved to a bot).

Preferred pull: GET /api/v2/view/{id}/task (the view applies its filters).
Auth: same load_token as cu_fix_empty_priority (never printed).
If there is no token, keep the existing snapshot or accept MCP JSON dumps:

  python3 src/cu_ros_bot_pull.py --ros-json dump.json --ros-bot-json dump.json

build.sh calls this before build_data.py; missing token + existing snapshot → exit 0.
"""
from __future__ import annotations

import argparse
import re
import datetime
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cu_fix_empty_priority import load_token  # noqa: E402

BOG = datetime.timezone(datetime.timedelta(hours=-5))
API = 'https://api.clickup.com/api/v2'
ROS_VIEW = '8cn3rz8-1914'
ROS_BOT_VIEW = '8cn3rz8-3574'
ROST = 60710247
BOT_R = '8f51644a-de28-4b84-a204-f0ec1903f337'
CLOSED = frozenset({'complete', 'completed', 'closed', 'done'})
BOT_R_OPTS = {
    'f6a849ca-31e5-44fc-b6e6-5824d366742e': 'Секретарь',
    '9f513555-1c69-4d5a-a933-e55b55f9340b': 'Помощник по всему',
    '8eb3f445-4c47-4957-ab61-1ab1fe02438d': 'Оборонный проект',
    'be6b18ea-cc0f-4a62-aa71-f5c2d4cce4e7': 'Юрист / Адвокат',
    '9a74ed7d-d18a-48ea-904e-38fff2ca52d8': 'ОФ Маркетинг',
    '619a552c-f93d-4dc2-92ff-b26079f6fbb3': 'Д',
    '0950cd4d-e275-4ba8-8e61-39cd087d438b': 'Пептид',
}

ROLE = '1469c8d4-a3b4-4925-958a-7f442d9e002f'
ROLE_OPTS = {
    '95771463-42ea-45fc-8b87-ad4b48108cbf': '🚶GO',
    '7698f409-40a0-4264-a318-84592847a99c': '📞CALL',
    'ca5fa4c2-8451-4703-92e6-4d29d505426a': 'Control',
    'af2515a6-45b6-42b0-a93c-965fa18868d0': 'TO DO',
    'd357bce5-88f1-4501-9b1c-8fb5e6b7b260': '💡REMIND',
    '8b650b89-b754-4ebd-b2e4-bbcba4d9b70c': '💵 Pago',
    '06d0346a-09cc-41c5-bf1f-0d0589737481': '🥳 Celebraciones',
}


def _now():
    return datetime.datetime.now(BOG).strftime('%Y-%m-%d %H:%M') + ' Bogotá'


def _fmt(ms, with_time=False):
    if not ms:
        return ''
    dt = datetime.datetime.fromtimestamp(int(ms) / 1000, BOG)
    return dt.strftime('%Y-%m-%d %H:%M') if with_time else dt.strftime('%Y-%m-%d')


def _status(t):
    st = t.get('status')
    if isinstance(st, dict):
        typ = str(st.get('type') or '').lower()
        if typ in ('closed', 'done'):
            return 'closed', typ
        return str(st.get('status') or '').lower(), typ
    return str(st or '').lower(), ''


def _is_closed(t):
    if t.get('date_closed') or t.get('closed'):
        return True
    name, typ = _status(t)
    return typ in ('closed', 'done') or name in CLOSED or name.startswith('complete')


def _assignee_ids(t):
    out = []
    for a in t.get('assignees') or []:
        if isinstance(a, dict) and a.get('id') is not None:
            out.append(int(a['id']))
        elif isinstance(a, (int, str)) and str(a).isdigit():
            out.append(int(a))
    return out


def _cf_bot_r(t):
    """Return (option_id, option_name) for BOT R, or ('','')."""
    if t.get('bot_r') or t.get('bot_r_id'):
        name = t.get('bot_r') or BOT_R_OPTS.get(t.get('bot_r_id') or '', '')
        return t.get('bot_r_id') or '', name
    for f in t.get('custom_fields') or t.get('fields') or []:
        if not isinstance(f, dict):
            continue
        fid = str(f.get('id') or f.get('field_id') or '')
        if fid != BOT_R and f.get('name') != 'BOT R':
            continue
        val = f.get('value')
        if isinstance(val, dict):
            oid = str(val.get('id') or '')
            return oid, val.get('name') or BOT_R_OPTS.get(oid, '')
        if isinstance(val, str) and val:
            return val, BOT_R_OPTS.get(val, val)
    return '', ''



def _cf_role(t):
    """Return (option_id, option_name) for Role, or ('','')."""
    if t.get('role') or t.get('role_id'):
        name = t.get('role') or ROLE_OPTS.get(t.get('role_id') or '', '')
        return t.get('role_id') or '', name
    for f in t.get('custom_fields') or t.get('fields') or []:
        if not isinstance(f, dict):
            continue
        fid = str(f.get('id') or f.get('field_id') or '')
        if fid != ROLE and f.get('name') != 'Role':
            continue
        val = f.get('value')
        if isinstance(val, dict):
            oid = str(val.get('id') or '')
            return oid, val.get('name') or ROLE_OPTS.get(oid, '')
        if isinstance(val, str) and val:
            return val, ROLE_OPTS.get(val, val)
    return '', ''


def _plain(s):
    s = re.sub(r'<[^>]+>', ' ', s or '')
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)
    s = re.sub(r'[*_`#]+', '', s)
    s = re.sub(r'@\w+', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def name_intent(name):
    s = re.sub(r'^\W*БОТ(?:-ЧАСТЬ| ЧАСТЬ)?\s*:?\s*', '', name or '', flags=re.I)
    s = re.sub(r'\s+', ' ', s).strip(' -–—')
    return s or (name or '').strip() or 'нет данных'


def make_thesis(name, description='', last_comment=''):
    """One short Russian line from real description or latest comment; else the name's intent. No invented facts."""
    def first(s, limit=180):
        s = _plain(s)
        if not s:
            return ''
        parts = re.split(r'(?<=[.!?…])\s+', s)
        out = parts[0]
        if len(out) < 50 and len(parts) > 1:
            out = (out + ' ' + parts[1]).strip()
        if len(out) > limit:
            out = out[:limit].rsplit(' ', 1)[0].rstrip('.,;:') + '…'
        return out
    return first(description) or first(last_comment) or name_intent(name)


def _latest_comment(comments):
    best, best_d = '', -1
    for c in comments or []:
        if not isinstance(c, dict):
            continue
        text = c.get('comment_text') or c.get('comment') or c.get('text') or ''
        if isinstance(text, list):
            text = ' '.join(
                (x.get('text') if isinstance(x, dict) else str(x)) for x in text
            )
        text = _plain(text)
        if not text:
            continue
        d = c.get('date') or c.get('date_created') or 0
        try:
            d = int(d)
        except Exception:
            d = 0
        if d >= best_d:
            best, best_d = text, d
    return best


def compact(t):
    lst = t.get('list') or {}
    tags = t.get('tags') or []
    asg = t.get('assignees') or []
    due = t.get('due_date') or t.get('due_ms')
    if not due and t.get('due') and str(t.get('due'))[:4].isdigit() and '-' in str(t.get('due')):
        due_s = str(t['due'])[:10]
        name, typ = _status(t)
        oid, bot_r = _cf_bot_r(t)
        rid, role = _cf_role(t)
        return dict(
            id=t['id'], name=t.get('name') or '', status=name,
            url=t.get('url') or ('https://app.clickup.com/t/' + t['id']),
            priority=(t.get('priority') if not isinstance(t.get('priority'), dict) else (t.get('priority') or {}).get('priority')) or '',
            list=lst.get('name') if isinstance(lst, dict) else (lst or t.get('list') or ''),
            list_id=str(lst.get('id') or t.get('list_id') or '') if isinstance(lst, dict) else str(t.get('list_id') or ''),
            tags=[x.get('name') if isinstance(x, dict) else str(x) for x in tags],
            assignees=[{'id': a.get('id'), 'username': a.get('username')} for a in asg if isinstance(a, dict)] or t.get('assignees') or [],
            due=due_s, due_ms=t.get('due_ms'),
            updated=t.get('updated') or '',
            closed=_is_closed(t),
            bot_r=bot_r, bot_r_id=oid,
            role=role, role_id=rid,
            transfer=t.get('transfer') or '',
            description=t.get('description') or t.get('text_content') or '',
            last_comment=t.get('last_comment') or '',
            thesis=t.get('thesis') or make_thesis(t.get('name') or '', t.get('description') or t.get('text_content') or '', t.get('last_comment') or ''),
        )
    if isinstance(t.get('priority'), dict):
        pr = (t.get('priority') or {}).get('priority') or ''
    else:
        pr = t.get('priority') or ''
    name, typ = _status(t)
    oid, bot_r = _cf_bot_r(t)
    rid, role = _cf_role(t)
    return dict(
        id=t['id'], name=t.get('name') or '', status=name,
        url=t.get('url') or ('https://app.clickup.com/t/' + t['id']),
        priority=pr,
        list=lst.get('name') if isinstance(lst, dict) else (lst or ''),
        list_id=str(lst.get('id') or '') if isinstance(lst, dict) else '',
        tags=[x.get('name') if isinstance(x, dict) else str(x) for x in tags],
        assignees=[{'id': a.get('id'), 'username': a.get('username')} for a in asg if isinstance(a, dict)],
        due=_fmt(due) if due and str(due).isdigit() else (str(t.get('due') or '')[:10]),
        due_ms=int(due) if due and str(due).isdigit() else t.get('due_ms'),
        updated=_fmt(t.get('date_updated'), True) if t.get('date_updated') else (t.get('updated') or ''),
        closed=_is_closed(t),
        bot_r=bot_r, bot_r_id=oid,
        role=role, role_id=rid,
        transfer=t.get('transfer') or '',
        description=t.get('description') or t.get('text_content') or '',
        last_comment=t.get('last_comment') or '',
        thesis=t.get('thesis') or make_thesis(t.get('name') or '', t.get('description') or t.get('text_content') or '', t.get('last_comment') or ''),
    )


def match_ros_bot(t):
    """Reproduce the «Ros (BOT)» view filter exactly (AND)."""
    if _is_closed(t):
        return False
    if ROST not in _assignee_ids(t) and t.get('assignees'):
        # already-compacted snapshot may have assignees; require Rost
        if ROST not in _assignee_ids(t):
            return False
    elif t.get('assignees') is None and not t.get('bot_r') and not t.get('bot_r_id'):
        return False
    if t.get('assignees') and ROST not in _assignee_ids(t):
        return False
    oid, name = _cf_bot_r(t)
    return bool(oid or name)


def match_ros(t):
    """Open + assignee Rost + BOT R NOT SET. dueDate-earlier is left to the view itself."""
    if _is_closed(t):
        return False
    if t.get('assignees') and ROST not in _assignee_ids(t):
        return False
    oid, name = _cf_bot_r(t)
    return not (oid or name)


def _req_view_tasks(token, view_id):
    tasks, page = [], 0
    while True:
        url = f'{API}/view/{urllib.parse.quote(view_id)}/task?page={page}'
        req = urllib.request.Request(url, headers={'Authorization': token, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode())
        batch = body.get('tasks') or []
        tasks.extend(batch)
        last = body.get('last_page')
        if last is True or last == 'true' or not batch:
            break
        page += 1
        if page > 50:
            break
    return tasks


def _load_dump(path):
    raw = Path(path).read_text(encoding='utf-8')
    i = raw.find('{"tasks"')
    if i < 0:
        d = json.loads(raw)
    else:
        chunk = raw[i:]
        d = None
        for end in range(len(chunk), max(0, len(chunk) - 5000), -1):
            try:
                d = json.loads(chunk[:end])
                break
            except Exception:
                continue
        if d is None:
            raise ValueError('cannot parse ' + path)
    if isinstance(d, dict) and 'tasks' in d:
        return d['tasks']
    if isinstance(d, list):
        return d
    raise ValueError('no tasks in ' + path)


def write_snap(path, name, view_id, filt, tasks, src):
    out = dict(fetched=_now(), src=src, view=dict(id=view_id, name=name, type='list', parent='workspace:9014731752'),
               filter=filt, count=len(tasks), tasks=tasks)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{path.name}: {len(tasks)} tasks from {name} ({view_id})')



def load_roles(path=None):
    p = Path(path) if path else (HERE / 'cu_roles.json')
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding='utf-8'))
    by = raw.get('by_id') if isinstance(raw, dict) else {}
    return {str(k): v for k, v in (by or {}).items() if v}


def apply_roles(tasks, roles):
    """Attach Role from the read-only map without inventing values."""
    if not roles:
        return tasks
    out = []
    for t in tasks:
        t = dict(t)
        rid = str(t.get('id') or '')
        if rid in roles:
            t['role'] = roles[rid]
        elif not t.get('role'):
            # already-compacted / custom_fields
            _oid, name = _cf_role(t)
            if name:
                t['role'] = name
                if _oid:
                    t['role_id'] = _oid
        out.append(t)
    return out


def enrich_from_file(tasks, path):
    """Merge description/last_comment from an MCP/side dump {id: {description, last_comment}} or a list."""
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    by = {}
    if isinstance(raw, dict) and 'tasks' in raw:
        raw = raw['tasks']
    if isinstance(raw, dict):
        by = {str(k): (v if isinstance(v, dict) else {'description': str(v)}) for k, v in raw.items()}
    else:
        for x in raw or []:
            if isinstance(x, dict) and x.get('id'):
                by[str(x['id'])] = x
    out = []
    for t in tasks:
        extra = by.get(str(t.get('id'))) or {}
        desc = extra.get('description') or extra.get('text_content') or t.get('description') or ''
        comm = extra.get('last_comment') or t.get('last_comment') or ''
        if not comm:
            comm = _latest_comment(extra.get('comments') or [])
        t = dict(t, description=desc, last_comment=comm, thesis=make_thesis(t.get('name') or '', desc, comm))
        out.append(t)
    return out



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ros-json', help='MCP/filter_tasks dump for view Ros')
    ap.add_argument('--ros-bot-json', help='MCP/filter_tasks dump for view Ros (BOT)')
    ap.add_argument('--keep-if-no-token', action='store_true', default=True)
    ap.add_argument('--enrich-json', help='merge description/last_comment from MCP dump into ma_ros_bot.json')
    ap.add_argument('--roles-json', help='merge Role custom field from a {by_id} map (default: cu_roles.json if present)')
    a = ap.parse_args()
    token = load_token()
    src_bot = src_ros = ''
    raw_bot = raw_ros = None
    if token:
        try:
            raw_bot = _req_view_tasks(token, ROS_BOT_VIEW)
            src_bot = 'GET /api/v2/view/%s/task' % ROS_BOT_VIEW
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            print('cu_ros_bot_pull: Ros (BOT) API failed:', type(e).__name__, file=sys.stderr)
        try:
            raw_ros = _req_view_tasks(token, ROS_VIEW)
            src_ros = 'GET /api/v2/view/%s/task' % ROS_VIEW
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            print('cu_ros_bot_pull: Ros API failed:', type(e).__name__, file=sys.stderr)
    if a.ros_bot_json:
        raw_bot = _load_dump(a.ros_bot_json)
        src_bot = 'dump ' + a.ros_bot_json
    if a.ros_json:
        raw_ros = _load_dump(a.ros_json)
        src_ros = 'dump ' + a.ros_json

    bot_path, ros_path = HERE / 'ma_ros_bot.json', HERE / 'ma_ros.json'
    ok = True
    if raw_bot is not None:
        tasks = [compact(t) for t in raw_bot if match_ros_bot(t) or (not _is_closed(t) and (_cf_bot_r(t)[1] or t.get('bot_r')))]
        # If we pulled the view itself, keep view tasks (already filtered) after compact; still drop closed.
        if src_bot.startswith('GET') or src_bot.startswith('dump') or src_bot.startswith('clickup'):
            tasks = [compact(t) for t in raw_bot if not _is_closed(t)]
            # Safety net: reproduce IS SET + assignee + not closed when fields allow it
            checked = [t for t in tasks if match_ros_bot(t) or not t.get('assignees')]
            if checked:
                tasks = checked if all(t.get('assignees') for t in tasks) else tasks
        if a.enrich_json:
            tasks = enrich_from_file(tasks, a.enrich_json)
        else:
            tasks = [dict(x, thesis=x.get('thesis') or make_thesis(x.get('name') or '', x.get('description') or '', x.get('last_comment') or '')) for x in tasks]
        write_snap(bot_path, 'Ros (BOT)', ROS_BOT_VIEW, {
            'op': 'AND',
            'fields': [
                {'field': 'status', 'op': 'NOT', 'values': [{'type': 'closed'}]},
                {'field': 'assignee', 'op': 'ANY', 'values': [ROST]},
                {'field': 'cf_' + BOT_R, 'op': 'IS SET', 'name': 'BOT R'},
            ],
            'show_closed': False,
        }, tasks, src_bot)
    elif bot_path.exists() and (a.enrich_json or a.keep_if_no_token):
        if a.enrich_json:
            prev = json.loads(bot_path.read_text(encoding='utf-8'))
            tasks = enrich_from_file(prev.get('tasks') or [], a.enrich_json)
            write_snap(bot_path, 'Ros (BOT)', ROS_BOT_VIEW, prev.get('filter') or {}, tasks, (prev.get('src') or '') + ' + enrich ' + a.enrich_json)
        else:
            print('cu_ros_bot_pull: no fresh Ros (BOT) pull, keeping', bot_path.name)
    else:
        print('cu_ros_bot_pull: no Ros (BOT) snapshot', file=sys.stderr)
        ok = False

    if raw_ros is not None:
        tasks = [compact(t) for t in raw_ros if not _is_closed(t)]
        write_snap(ros_path, 'Ros', ROS_VIEW, {
            'op': 'AND',
            'fields': [
                {'field': 'status', 'op': 'NOT', 'values': [{'type': 'closed'}]},
                {'field': 'dueDate', 'op': 'EQ', 'values': [{'op': 'earlier'}]},
                {'field': 'assignee', 'op': 'ANY', 'values': [ROST]},
                {'field': 'cf_' + BOT_R, 'op': 'NOT SET', 'name': 'BOT R'},
            ],
            'show_closed': False,
        }, tasks, src_ros)
    elif ros_path.exists() and a.keep_if_no_token:
        print('cu_ros_bot_pull: no fresh Ros pull, keeping', ros_path.name)
    else:
        print('cu_ros_bot_pull: no Ros snapshot', file=sys.stderr)
        ok = False

    roles_path = a.roles_json or (str(HERE / 'cu_roles.json') if (HERE / 'cu_roles.json').exists() else None)
    roles = load_roles(roles_path) if roles_path else {}
    if roles:
        for path, name, view_id in ((bot_path, 'Ros (BOT)', ROS_BOT_VIEW), (ros_path, 'Ros', ROS_VIEW)):
            if not path.exists():
                continue
            prev = json.loads(path.read_text(encoding='utf-8'))
            tasks = apply_roles(prev.get('tasks') or [], roles)
            n = sum(1 for x in tasks if x.get('role'))
            src = prev.get('src') or ''
            if '+ roles' not in src:
                src = (src + ' + roles').strip(' +')
            write_snap(path, name, view_id, prev.get('filter') or {}, tasks, src)
            print(f'{path.name}: Role on {n}/{len(tasks)} tasks')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
