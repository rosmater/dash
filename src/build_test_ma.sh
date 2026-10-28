#!/bin/bash
# Rost 26.10: data-test-ma.json (plaintext, НЕ пушить в dash-gh) -> входит в data.json через build_data.py; затем запусти src/build.sh. test-messengers-assistants.html = редирект.
cd "$(dirname "$0")/.."
exec 9>/tmp/dash-build.lock; flock -w 120 9 || { echo "build lock busy"; exit 1; }  # одна сборка за раз (35→15 гонка)
python3 src/test_ma_build.py || exit 1
# HARD t4196: кто трогал даш
python3 src/dash_touch_append.py --bot "${DASH_TOUCH_BOT:-unknown}" --action build --note "build_test_ma.sh" --files "data-test-ma.json,data-test-ma.enc.json" || true
python3 src/guard_spheres.py || exit 1  # Rost t3952u: TG/WA пропали из сфер -> не пушим
python3 - <<'PY'
import re,json,base64,os,unicodedata
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
src=open('src/variant-a.html').read()
style=re.search(r'<style>.*?</style>',src,re.S).group(0)
html=open('src/test-ma.html').read().replace('/*STYLE*/',style).replace('/*GATE*/',open('src/gate.js').read())
# Rost 26.10: вкладки вшиты в главный дашборд -> TEST-адрес теперь редирект на index.html
open('test-messengers-assistants.html','w').write('<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex"><title>Перенесено в главный дашборд</title><meta http-equiv="refresh" content="0;url=index.html"><script>location.replace("index.html")</script><p>Вкладки «Мессенджеры» и «Ассистенты · боты» теперь в главном дашборде: <a href="index.html">rosmater.github.io/dash</a></p>')
pw=re.search(r'^password:\s*(\S+)',open('/home/box/contacts/knowledge/secrets/vault/dashboard-password.md').read(),re.M).group(1)
pw=unicodedata.normalize('NFC',pw.strip()).lower()
main=json.load(open('data.enc.json')); salt=base64.b64decode(main['salt']); it=main['iter']  # та же соль -> тот же ключ, без повторного ввода
key=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=it).derive(pw.encode())
iv=os.urandom(12); ct=AESGCM(key).encrypt(iv,json.dumps(json.load(open('data-test-ma.json')),ensure_ascii=False).encode(),None)
b=lambda x:base64.b64encode(x).decode()
json.dump({'v':1,'kdf':'PBKDF2-SHA256','iter':it,'salt':b(salt),'iv':b(iv),'ct':b(ct)},open('data-test-ma.enc.json','w'))
print('test built')
PY
