#!/usr/bin/env python3
"""t6157u: проверка живого даша после push.
Расшифровывает https://rosmater.github.io/dash/data.enc.json и тот же файл из origin/main,
по каждому блоку (src/owners.json) печатает: есть ли блок на живой, совпадает ли с последним коммитом,
не новее ли исходники владельца, чем живая сборка, и есть ли маркеры. Пароль не печатается.
Выход 0 = все OK, 1 = есть STALE/MISSING/MARKER."""
import json, os, re, sys, base64, hashlib, subprocess, unicodedata, urllib.request, time
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
ROOT = '/workspace/dash-gh'
VAULT = '/home/box/contacts/knowledge/secrets/vault/dashboard-password.md'
BASE = 'https://rosmater.github.io/dash/'
def git(*a): return subprocess.check_output(['git', '-C', ROOT, *a], text=True).strip()
def fetch(name):
    req = urllib.request.Request(BASE + name + '?nc=%d' % time.time(), headers={'Cache-Control': 'no-cache'})
    return urllib.request.urlopen(req, timeout=45).read()
_pw = unicodedata.normalize('NFC', re.search(r'^password:\s*(\S+)', open(VAULT).read(), re.M).group(1).strip()).lower()
def dec(raw):
    e = json.loads(raw)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=base64.b64decode(e['salt']), iterations=e['iter']).derive(_pw.encode())
    return json.loads(AESGCM(key).decrypt(base64.b64decode(e['iv']), base64.b64decode(e['ct']), None))
H = lambda o: hashlib.sha1(json.dumps(o, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]
def ts(s):
    try: return datetime.fromisoformat(s).timestamp()
    except Exception: return 0
git('fetch', '-q', 'origin', 'main')
own = json.load(open(os.path.join(ROOT, 'src/owners.json')))['blocks']
live = dec(fetch('data.enc.json')); html = fetch('index.html').decode('utf-8', 'replace')
com = dec(git('show', 'origin/main:data.enc.json')); com_sha = git('rev-parse', '--short', 'origin/main')
lg = (live.get('meta') or {}).get('generated_at', ''); lt = ts(lg)
L = {d.get('id'): d for d in live.get('directions', [])}; C = {d.get('id'): d for d in com.get('directions', [])}
print(f'live generated_at={lg}  origin/main={com_sha}  committed generated_at={(com.get("meta") or {}).get("generated_at")}')
print(f'{"блок":<11} {"владелец":<34} {"живая":<6} {"=коммит":<8} {"src≤сборка":<11} {"маркеры":<8} итог')
bad = 0
for b in own:
    d = b['dir']; lv = L.get(d); cv = C.get(d)
    present = lv is not None
    same = present and cv is not None and H(lv) == H(cv)
    # время последнего коммита файлов владельца vs время живой сборки (минутная точность → допуск 120 с)
    files = [f for f in b['files'] if os.path.exists(os.path.join(ROOT, f))]
    sct = int(git('log', '-1', '--format=%ct', 'origin/main', '--', *files) or 0) if files else 0
    fresh = (not lt) or sct <= lt + 120
    s_live = json.dumps(lv, ensure_ascii=False) if present else ''
    miss = [m for m in b.get('data_markers', []) if m not in s_live] + [m for m in b.get('html_markers', []) if m not in html]
    st = 'OK' if present and same and fresh and not miss else ('MISSING' if not present else 'STALE' if not (same and fresh) else 'MARKER')
    bad += st != 'OK'
    print(f'{d:<11} {b["owner"][:34]:<34} {"да" if present else "НЕТ":<6} {"да" if same else "нет":<8} {"да" if fresh else "НЕТ":<11} {"ok" if not miss else ",".join(miss)[:8]:<8} {st}')
print('ИТОГ:', 'все блоки OK' if not bad else f'{bad} блок(ов) не OK — проверь владельцев выше (Pages может ещё раскатывать: подожди 1–2 мин и повтори)')
sys.exit(1 if bad else 0)
