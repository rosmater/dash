#!/usr/bin/env python3
"""Rost t5990u: Табакевич «На решение» — роль из CU-поля Role + исполнитель.

USAGE (agent / morning pack, no LLM judgement needed):
  for each cu id in src/tbk_blocks.json decisions.items:
     clickup_get_task task_id=<id> include=["custom_fields"] write_to_file=true
  python3 src/tbk_decisions_sync.py <file1> [file2 …]   then build.sh + push.
Updates per item: role (Role dropdown name), assignees (usernames), status, due, name.
Never touches `executor` (manual override, e.g. «Юля» where Rost is CU assignee but Юля does it)
or `slot`. Dash shows: pill = role; under it 👤 executor || «Я» if Rost assigned || «Юля» || names.
Closed tasks (status complete/closed/done) are dropped from the block.
"""
import datetime, json, os, re, sys
ROLE = '1469c8d4-a3b4-4925-958a-7f442d9e002f'
J = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tbk_blocks.json')
BOG = datetime.timezone(datetime.timedelta(hours=-5))

def tasks(path):
    txt = open(path).read()
    try:
        b = json.loads(txt)
    except Exception:
        m = re.search(r'\{.*\}', txt, re.S); b = json.loads(m.group(0))
    if isinstance(b, dict) and 'id' in b: return [b]
    if isinstance(b, dict): return b.get('tasks', [])
    return [x for x in b if isinstance(x, dict) and 'id' in x]

B = json.load(open(J)); items = B['decisions']['items']; by = {x.get('cu'): x for x in items if x.get('cu')}
changed = 0
for f in sys.argv[1:]:
    for t in tasks(f):
        x = by.get(t['id'])
        if not x: continue
        role = next((c.get('value', {}).get('name') for c in t.get('custom_fields', []) if c.get('id') == ROLE and isinstance(c.get('value'), dict)), None)
        due = t.get('due_date'); due = datetime.datetime.fromtimestamp(int(due)/1000, BOG).strftime('%Y-%m-%d') if due else None
        new = dict(role=role, assignees=[a.get('username') for a in t.get('assignees', [])], status=t.get('status'), due=due)
        for k, v in new.items():
            if x.get(k) != v: x[k] = v; changed += 1
items[:] = [x for x in items if not re.search(r'complete|closed|done', str(x.get('status') or ''), re.I)]
json.dump(B, open(J, 'w'), ensure_ascii=False, indent=1)
print('changed', changed); sys.exit(0 if changed else 10)
