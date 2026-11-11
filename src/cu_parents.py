"""Rost t5996u (HARD): мейн / родительские CU-задачи никогда не попадают в даш (ни задачи, ни «Требует внимания»,
ни «На решение», ни Фин-сводки, ни бейджи).
Детект: CU-статус «main» · «(родитель)» в названии · id из src/cu_parents.json (верхний уровень с подзадачами).
Объекты недвижимости (статус «объекты», карточки квартир) — не задачи, остаются.
strip(data) — чистит готовый data (build_data.py, cu_due_sync.py). found(data) — для guard_parents.py.
"""
import json, os, re
_J = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cu_parents.json')
IDS = set((json.load(open(_J)).get('ids') or {}).keys()) if os.path.exists(_J) else set()
_RX = re.compile(r'86[0-9a-z]{7}')
_SKIP_KEYS = {'parent'}  # хлебная крошка «родитель / список» у подзадачи — это не сама задача

def cu_id(o):
    for k in ('id', 'cu', 't', 'cu_task'):
        v = o.get(k)
        if isinstance(v, dict): v = v.get('id')
        if isinstance(v, str) and _RX.fullmatch(v): return v
    m = _RX.search(str(o.get('url') or '')) if re.search(r'clickup\.com/t/|/cu/\?t=', str(o.get('url') or '')) else None
    return m.group(0) if m else None

def is_parent(o):
    if not isinstance(o, dict): return False
    i = cu_id(o)
    if not i: return False
    if i in IDS: return True
    if str(o.get('status') or '').strip().lower() == 'main': return True
    return any('(родитель)' in str(o.get(k) or '') for k in ('name', 'label', 'text', 'full_name'))

def _anchor(o, path):
    # карточка-контейнер (группа со своими задачами / объект недвижимости): оставляем, снимаем только ссылку на мейн
    return isinstance(o.get('tasks'), list) or '.re_blocks' in path or path.endswith('.health')

def _unlink(o):
    i = cu_id(o)
    for k in ('cu', 'url', 'cu_url', 'cu_task'):
        if k in o: o[k] = None
    ids = IDS | ({i} if i else set())
    for k, v in list(o.items()):
        if isinstance(v, str) and k not in _SKIP_KEYS and any(x in v for x in ids):
            for x in ids: v = re.sub(r'\s*[·,;]?\s*(CU\s*)?' + x, '', v)
            o[k] = v.strip(' ·,;')

def strip(o, path='', removed=None):
    removed = [] if removed is None else removed
    if isinstance(o, dict):
        for k, v in list(o.items()):
            p = path + '.' + k
            if isinstance(v, dict) and is_parent(v):
                if _anchor(v, p): _unlink(v); removed.append((p, cu_id(v) or '?', 'unlink'))
                else: removed.append((p, cu_id(v), 'drop')); o[k] = None; continue
            strip(o[k], p, removed)
    elif isinstance(o, list):
        keep = []
        for v in o:
            if is_parent(v):
                i = cu_id(v)
                if _anchor(v, path): _unlink(v); removed.append((path, i, 'unlink'))
                else: removed.append((path, i, 'drop')); continue
            strip(v, path + '[]', removed); keep.append(v)
        o[:] = keep
    return removed

def found(o, path=''):
    """Все места, где мейн-задача ещё видна (id в любом поле, кроме хлебной крошки parent)."""
    out = []
    if isinstance(o, dict):
        if is_parent(o) and not (_anchor(o, path) and not any(o.get(k) for k in ('cu', 'url'))):
            out.append((path, cu_id(o)))
        for k, v in o.items():
            if k in _SKIP_KEYS: continue
            if isinstance(v, str):
                for m in _RX.findall(v):
                    if m in IDS: out.append((path + '.' + k, m))
            else: out += found(v, path + '.' + k)
    elif isinstance(o, list):
        for v in o: out += found(v, path + '[]')
    return out
