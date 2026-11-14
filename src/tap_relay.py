#!/usr/bin/env python3
"""Rost t3955u: доставка тапов с даша (GitHub Pages) на box без участия Rost.
Браузер: очередь dash_tapq → AES-GCM ключом даша → POST https://ntfy.sh/<topic> (наружу только шифротекст).
Тут: poll ntfy → расшифровать (ключ основного даша или helper, из vault+соль .enc.json) → sync/inbox/*.json → sync_dash_taps.py (contacts / cu_dir_overrides / cu_actions → пересборка + пуш).
Запуск: python3 src/tap_relay.py            # демон, опрос раз в 60 с (лог sync/relay.log)
        python3 src/tap_relay.py --once     # один проход (для мега-рутины / после рестарта box)
ntfy хранит сообщения ~12 ч; если relay лежал дольше — браузер сам пере-шлёт локальные сортировки при открытии даша (раз в 3 ч)."""
import os, sys, re, json, time, base64, unicodedata, subprocess, urllib.request, fcntl, datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPIC = open(f'{R}/sync/topic.txt').read().strip()
ST = f'{R}/sync/relay_state.json'; INB = f'{R}/sync/inbox'
os.makedirs(INB, exist_ok=True)  # t6284u: без inbox все тапы с 11.11 падали FileNotFoundError
V = '/home/box/contacts/knowledge/secrets/vault/'
PAIRS = [(V + 'dashboard-password.md', 'data.enc.json'), (V + 'dashboard-password-assistant.md', 'data-asst.enc.json')]
def log(*a): print(datetime.datetime.now().strftime('%m-%d %H:%M:%S'), *a, flush=True)
_K = {}
def keys():
    out = []
    for vf, enc in PAIRS:
        try:
            e = json.load(open(f'{R}/{enc}')); sig = (vf, e['salt'], e['iter'])
            if sig not in _K:
                pw = unicodedata.normalize('NFC', re.search(r'^password:\s*(\S+)', open(vf).read(), re.M).group(1).strip()).lower()
                _K.clear() if len(_K) > 8 else None
                _K[sig] = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=base64.b64decode(e['salt']), iterations=e['iter']).derive(pw.encode())
            out.append(_K[sig])
        except Exception as ex: log('key fail', enc, type(ex).__name__)
    return out
def dec(body):
    try:
        m = json.loads(body)
        iv = base64.b64decode(m['iv']); ct = base64.b64decode(m['ct'])
    except Exception:
        return None
    for k in keys():
        try: return json.loads(AESGCM(k).decrypt(iv, ct, None))
        except Exception: pass
    return None
def once():
    st = json.load(open(ST)) if os.path.exists(ST) else {}
    since = st.get('since') or '12h'
    raw = urllib.request.urlopen(f'https://ntfy.sh/{TOPIC}/json?poll=1&since={since}', timeout=30).read().decode()
    n = 0
    wa_n = 0
    for line in raw.splitlines():
        try: m = json.loads(line)
        except Exception: continue
        if m.get('event') != 'message': continue
        st['since'] = m['id']
        # Rost t4380: ntfy since=<id> отдаёт соседние сообщения той же секунды снова → пинг-понг 3/6 сфер каждые 60 с (08:52–09:29 28.10). Дедуп по id
        seen = st.setdefault('seen', [])
        if m['id'] in seen: continue
        seen.append(m['id']); del seen[:-300]
        body = m.get('message') or ''
        p = dec(body)
        if p and isinstance(p.get('spheres'), list):
            json.dump({'spheres': p['spheres'], 'via': 'ntfy', 'ntfy_id': m['id'], 'time': m.get('time')}, open(f"{INB}/tap-{m['time']}-{m['id']}.json", 'w'), ensure_ascii=False)
            n += 1
            continue
        # Package D3 (Rost GO 27.10): log-only WA Peso toast → apply_wa_toast.py (no LLM)
        try:
            j = json.loads(body) if isinstance(body, str) else None
        except Exception:
            j = None
        if isinstance(j, dict) and j.get('app') == 'whatsapp-peso-peptid':
            try:
                r = subprocess.run(
                    [sys.executable, '/workspace/peptides-dash-monitors/apply_wa_toast.py', '--json', json.dumps(j, ensure_ascii=False)],
                    capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    wa_n += 1
                    log('wa-toast', (r.stdout or '').strip()[-200:])
                else:
                    err = ((r.stdout or '') + (r.stderr or '')).strip()[-300:]
                    log('wa-toast fail', r.returncode, err)
                    try:
                        open('/workspace/peptides-dash-monitors/watcher-errors.log', 'a').write(
                            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S -05') + ' relay ' + err.replace('\n', ' ') + '\n')
                    except Exception:
                        pass
            except Exception as e:
                log('wa-toast err', type(e).__name__, str(e)[:200])
            continue
        log('skip undecryptable', m['id'])
    json.dump(st, open(ST, 'w'))
    if n: log('got', n)
    if wa_n: log('wa-toast got', wa_n)
    os.makedirs(INB, exist_ok=True)
    if any(f.endswith('.json') for f in os.listdir(INB)):
        with open(f'{R}/sync/.lock', 'w') as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            r = subprocess.run([sys.executable, f'{R}/src/sync_dash_taps.py'], capture_output=True, text=True)
            log('sync rc', r.returncode, (r.stdout + r.stderr)[-600:].replace('\n', ' | '))
    # Rost t6285u: ✓ решено не должен застрять незапушенным — ретрай пуша src/done_pending.json (no-op, если чисто)
    try:
        with open(f'{R}/sync/.lock', 'w') as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            r = subprocess.run([sys.executable, f'{R}/src/sync_dash_taps.py', '--push-only'], capture_output=True, text=True, timeout=900)
            if 'push-only: clean' not in r.stdout: log('done-pending push-only rc', r.returncode, (r.stdout + r.stderr)[-400:].replace('\n', ' | '))
    except Exception as e: log('done-pending push err', type(e).__name__, str(e)[:200])
    # Rost t4074: закрытый пункт QUEUE → даш сам пересобирается (queue_autoclear.py; без изменений — no-op)
    try:
        with open(f'{R}/sync/.lock', 'w') as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            r = subprocess.run([sys.executable, f'{R}/src/queue_autoclear.py'], capture_output=True, text=True, timeout=600)
            if 'no new closed' not in r.stdout: log('queue-autoclear rc', r.returncode, (r.stdout + r.stderr)[-400:].replace('\n', ' | '))
    except Exception as e: log('queue-autoclear err', type(e).__name__, str(e)[:200])
    # Package Q (Rost t4209): shell queue-guard Clear-TZ → webhook; throttle 15 мин; $0 LLM
    try:
        gflag = f'{R}/sync/.queue_guard_last'
        run = True
        if os.path.exists(gflag):
            run = (time.time() - os.path.getmtime(gflag)) >= 14 * 60
        if run:
            r = subprocess.run([sys.executable, '/workspace/queue/bin/queue-guard-shell.py', '--live'],
                               capture_output=True, text=True, timeout=120)
            open(gflag, 'w').write(str(time.time()))
            o = (r.stdout + r.stderr).strip()
            if o:
                # log only SUMMARY / WAKEs to keep relay.log small
                lines = [ln for ln in o.splitlines() if 'SUMMARY' in ln or 'WAKE' in ln or 'ERR' in ln]
                if lines: log('queue-guard', r.returncode, ' | '.join(lines)[-400:])
            # Q-alive: if last.json stale somehow after run, still ok; alive.sh is for external cron
    except Exception as e: log('queue-guard err', type(e).__name__, str(e)[:200])
    # Rost t6454u: ClickUp → доски без LLM (src/cu_snap_sync.py --auto: раз в 2 ч 06–22 Богота, вт — полная сверка;
    # без токена ClickUp — мгновенный no-op). Пересборка + пуш только при изменениях.
    try:
        with open(f'{R}/sync/.lock', 'w') as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            r = subprocess.run([sys.executable, f'{R}/src/cu_snap_sync.py', '--auto'], capture_output=True, text=True, timeout=900)
            o = (r.stdout + r.stderr).strip()
            if o or r.returncode: log('cu-snap-sync', r.returncode, o[-400:].replace('\n', ' | '))
    except Exception as e: log('cu-snap-sync err', type(e).__name__, str(e)[:200])
    # Rost t4169–71: сбой вотчера → авто-починка TG на боксе + QUEUE watcher-fix-* (троттл 10 мин внутри скрипта)
    try:
        r = subprocess.run([sys.executable, '/workspace/notify-watchers/health/watcher_autoheal.py'], capture_output=True, text=True, timeout=300)
        o = (r.stdout + r.stderr).strip()
        if o and o != 'watchers ok': log('watcher-autoheal', r.returncode, o[-300:].replace('\n', ' | '))
    except Exception as e: log('watcher-autoheal err', type(e).__name__, str(e)[:200])
    return n
if __name__ == '__main__':
    if '--once' in sys.argv: once(); sys.exit(0)
    while True:
        try: once()
        except Exception as e: log('err', type(e).__name__, str(e)[:200])
        time.sleep(60)
