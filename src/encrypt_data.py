"""data.json -> data.enc.json (AES-256-GCM, key = PBKDF2-SHA256(password, salt, 250k)).
Password is read from the vault file (line 'password: ...'); never printed."""
import os, re, sys, json, base64, unicodedata
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
ROOT = os.path.join(os.path.dirname(__file__), '..')
# usage: encrypt_data.py [password_file] [out_name] [hide_json]
VAULT = sys.argv[1] if len(sys.argv) > 1 else '/home/box/contacts/knowledge/secrets/vault/dashboard-password.md'
OUT = sys.argv[2] if len(sys.argv) > 2 else 'data.enc.json'
HIDE = sys.argv[3] if len(sys.argv) > 3 else None
PIN_ENV = os.environ.get('BALANCE_PIN_FILE', '/home/box/secrets/balance-pin.env')
BAL_ITER = 600000  # t6092u: high iterations; short PIN, brute-force costly in browser too

def _read_balance_pin():
    """Return PIN from env file. Never print it."""
    raw = open(PIN_ENV).read()
    m = re.search(r'^BALANCE_PIN=(.*)$', raw, re.M)
    if not m:
        raise SystemExit('BALANCE_PIN missing in pin env file')
    pin = unicodedata.normalize('NFC', m.group(1).strip())
    if not pin:
        raise SystemExit('BALANCE_PIN empty')
    return pin

def _b64(x):
    return base64.b64encode(x).decode()

def _encrypt_overall_balance(data):
    """Replace plaintext overall_balance with AES-GCM ciphertext (PIN via PBKDF2-SHA256)."""
    plain = data.pop('overall_balance', None)
    data.pop('overall_balance_enc', None)
    if not plain:
        return
    pin = _read_balance_pin()
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=BAL_ITER).derive(pin.encode())
    ct = AESGCM(key).encrypt(iv, json.dumps(plain, ensure_ascii=False).encode(), None)
    data['overall_balance_enc'] = dict(v=1, kdf='PBKDF2-SHA256', iter=BAL_ITER, salt=_b64(salt), iv=_b64(iv), ct=_b64(ct))

def _strip_overall_balance(data):
    """t6091u: assistant payload must not contain the block or its ciphertext."""
    data.pop('overall_balance', None)
    data.pop('overall_balance_enc', None)

pw = re.search(r'^password:\s*(\S+)', open(VAULT).read(), re.M).group(1)
pw = unicodedata.normalize('NFC', pw.strip()).lower()  # same normalization as gate.js
ITER = 250000
# Соль стабильна (берём из прошлого файла) -> ключ в localStorage у Rost не слетает при каждом обновлении данных.
# Новый пароль -> старый ключ не подходит -> окно пароля появится само. Сброс соли: удалить OUT.
iv = os.urandom(12)
try:
    salt = base64.b64decode(json.load(open(os.path.join(ROOT, OUT)))['salt'])
except Exception:
    salt = os.urandom(16)
key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(pw.encode())
data = json.load(open(os.path.join(ROOT, 'data.json')))
if HIDE:
    _strip_overall_balance(data)
elif data.get('overall_balance') or data.get('overall_balance_enc'):
    _encrypt_overall_balance(data)
if HIDE:
    hj = json.load(open(HIDE))
    hide = set(hj.get('directions', []))
    if hj.get('calendar_cu_only'):  # Rost 25.10: helper — только ClickUp со временем, Google-события не показываем
        for d in data['directions']:
            if d.get('kind') != 'calendar': continue
            ev = []
            for e in d.get('events', []):
                if e.get('src') == 'clickup' and e.get('via') != 'gcal-sync': ev.append({k: v for k, v in e.items() if k != 'cu'})
                for c in e.get('cu', []) or []:
                    ev.append(dict(src='clickup', title=c['title'], start=c['due'], end=None, all_day=False, due=True, list=c.get('list'), url=c['url']))
            d['events'] = sorted(ev, key=lambda x: x['start'])
            d['cu_only'] = True
            d['subtitle'] = 'Задачи ClickUp со временем · Богота'
            for k in ('gcal_url', 'gcal_fetched_at', 'refresh'): d.pop(k, None)
            for e in d['events']: e.pop('via', None)
    if hj.get('strip_hidden_blocks'):  # Rost 25.10: «скрыть от помощницы» — блоки с hide_from_helper вообще не попадают в data-asst
        for d in data['directions']:
            for k, v in list(d.items()):
                if k.endswith('_blocks') and isinstance(v, dict):
                    for bk in [bk for bk, bv in v.items() if isinstance(bv, dict) and bv.get('hide_from_helper')]: v.pop(bk)
                    for bv in v.values():  # и отдельные пункты внутри блоков (напр. PrEP в чеклисте)
                        if isinstance(bv, dict):
                            for lk, lv in bv.items():
                                if isinstance(lv, list): bv[lk] = [x for x in lv if not (isinstance(x, dict) and x.get('hide_from_helper'))]
    # Rost t6061u: у ассистентки в Личном нет «Назначенных встреч» (только На решение + Документы)
    for d in data['directions']:
        if d.get('id') == 'personal':
            d['scheduled_meetings'] = []
    if hj.get('messengers_monitor_only'):  # Rost 27.10 t3927: монитор оставить, контент-блоки мессенджеров убрать
        for d in data['directions']:
            if d.get('id') == 'messengers':
                for k in ('messengers', 'unsorted', 'spheres', 'ignored'): d[k] = []
                for k in ('clickup', 'reconcile', 'mention_handles', 'oq'): d[k] = {}
    if hj.get('hide_bots'):
        for d in data['directions']:
            if d.get('id') == 'assistants': d['bots'] = [b for b in d.get('bots', []) if b.get('name') not in hj['hide_bots']]
    if hide:
        data['directions'] = [d for d in data['directions'] if d.get('id') not in hide]
    # t6093u: в payload helper только версии блоков видимых вкладок (баланс сюда не входит)
    du = data.get('data_updates')
    if isinstance(du, dict) and isinstance(du.get('blocks'), list):
        keep = {d.get('id') for d in (data.get('directions') or [])}
        du['blocks'] = [b for b in du['blocks'] if b.get('dir') in keep]
pt = json.dumps(data, ensure_ascii=False).encode()
ct = AESGCM(key).encrypt(iv, pt, None)
b = lambda x: base64.b64encode(x).decode()
json.dump({'v': 1, 'kdf': 'PBKDF2-SHA256', 'iter': ITER, 'salt': b(salt), 'iv': b(iv), 'ct': b(ct)},
          open(os.path.join(ROOT, OUT), 'w'))
print('encrypted', OUT)
