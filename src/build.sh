#!/bin/bash
# Inline src/core.js into each variant -> ../variant-*.html
cd "$(dirname "$0")/.."
python3 src/build_data.py
python3 src/guard_parents.py || { echo 'guard_parents FAIL — мейн-задача в даше'; exit 1; }  # Rost t5996u
for v in a b c; do
  [ -f src/variant-$v.html ] || continue
  python3 - "$v" <<'PY'
import sys
v=sys.argv[1]
core=open('src/core.js').read()
html=open(f'src/variant-{v}.html').read().replace('/*CORE*/',core)
# t6090u / t6091u: «Общий баланс» JS только в главном даше (variant-a / index), не в helper
if v=='a':
    bal=open('src/overall_balance.js').read()
    if '/*BALANCE*/' in html:
        html=html.replace('/*BALANCE*/', bal)
    else:
        html=html.replace('</script></body>', '\n'+bal+'\n</script></body>', 1)
open(f'variant-{v}.html','w').write(html)
PY
done
python3 src/encrypt_data.py
# Копия для ассистента (helper.html; бывш. assistant.html): тот же A, свой пароль, свой файл данных, свой ключ в localStorage
python3 - <<'PY2'
core=open('src/core.js').read()
cfg="<script>window.DASH_ENC='data-asst.enc.json';window.DASH_LS='dash_key_asst_v1';window.DASH_TITLE='Дашборд (ассистент)';window.DASH_HELPER=true;</script>\n"
html=open('src/variant-a.html').read().replace('/*CORE*/',core).replace('/*BALANCE*/','').replace('<head>\n','<head>\n'+cfg,1)  # Rost t3938–43: helper = index + 1 строка конфига; t6091u: без блока баланса
# t6091u: в исходнике helper не должно быть блока / его данных, даже в page source
for needle in ('Общий баланс', 'overall_balance', 'overall_balance_enc', 'BalView', 'dash_bal_sess_v1', 'bal-pin'):
    if needle in html:
        raise SystemExit('helper.html would contain %r — abort' % needle)
open('helper.html','w').write(html)
# старый адрес assistant.html -> редирект на helper.html (Rost 25.10)
open('assistant.html','w').write('<!doctype html><meta charset="utf-8"><title>Перенесено</title><meta http-equiv="refresh" content="0;url=helper.html"><script>location.replace("helper.html"+location.search+location.hash)</script><a href="helper.html">helper.html</a>')
PY2
python3 src/encrypt_data.py /home/box/contacts/knowledge/secrets/vault/dashboard-password-assistant.md data-asst.enc.json src/assistant_hide.json
# Главный адрес https://rosmater.github.io/dash/ = Light A (Rost 25.10); variant-a.html остаётся алиасом
cp variant-a.html index.html
echo built
