#!/usr/bin/env python3
"""Rost 27.10 t3952u/t3953u: страж перед пушем даша (вызывается из build_test_ma.sh; ma_q.py rebuild / sync_dash_taps.py падают -> пуша нет).
FAIL, если канал (Telegram / WhatsApp UKR / WhatsApp ESP / Viber):
  1) в карточках сфер 0 строк, а в «на сортировку» есть его чаты с непрочитанными; или
  2) в последней удачной сборке (src/guard_last.json) у канала были строки в сферах, а сейчас 0 (потеря классификации).
Удачная сборка записывает src/guard_last.json. Осознанный сброс: GUARD_ALLOW=Telegram,... bash src/build_test_ma.sh
t5141: непроч. суммы = только unmuted (как на даше у Rost); muted хранятся в data но не входят в visible numbers."""
import json, sys, os, collections
H = os.path.dirname(os.path.abspath(__file__))
p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, '..', 'data-test-ma.json')
LAST = os.path.join(H, 'guard_last.json')
d = json.load(open(p))
inS = collections.Counter(r.get('channel') for g in d.get('messengers', []) for r in g.get('rows', []) if not r.get('muted'))
inU = collections.Counter()
mutedU = collections.Counter()
for g in d.get('messengers', []):
    for r in g.get('rows', []):
        if not isinstance(r.get('unread_chat'), int):
            continue
        ch = r.get('channel')
        if r.get('muted'):
            mutedU[ch] += r['unread_chat']
        else:
            inU[ch] += r['unread_chat']
unU = collections.Counter(u.get('channel') for u in d.get('unsorted', []) if (u.get('unread') or 0) > 0 and not u.get('muted'))
try:
    _L = json.load(open(LAST)); last = _L.get('in_spheres', {}); lastU = _L.get('in_spheres_unread', {})
except Exception:
    last = {}; lastU = {}
allow = set(filter(None, os.environ.get('GUARD_ALLOW', '').split(',')))
bad = []
for ch in ('Telegram', 'WhatsApp UKR', 'WhatsApp ESP', 'Viber'):
    if ch in allow:
        continue
    if inS[ch] > 0:
        lu = lastU.get(ch, 0)
        if lu >= 10 and inU[ch] < lu * 0.6:
            bad.append(f'{ch}: непрочитанных в сферах было {lu}, стало {inU[ch]} (частичная потеря)')
        continue
    if unU[ch] > 0 and ch != 'Viber':
        bad.append(f'{ch}: 0 в сферах, {unU[ch]} с непроч. на сортировке')
    elif last.get(ch, 0) > 0:
        bad.append(f'{ch}: было {last[ch]} в сферах, стало 0')
print('guard: в сферах (unmuted)', dict(inS), '· непроч. unmuted', dict(inU), '· muted_held', dict(mutedU), '· на сортировку с непроч.', dict(unU), '· прошлая удачная', last)
if bad:
    print('GUARD FAIL —', '; '.join(bad), '— классификация (chats.csv/people.csv/census/тапы) потеряна; пуш остановлен')
    sys.exit(1)
json.dump({'in_spheres': dict(inS), 'in_spheres_unread': dict(inU), 'muted_held_unread': dict(mutedU), 'unsorted_unread': dict(unU), 'file': os.path.basename(p)}, open(LAST, 'w'), ensure_ascii=False)
print('guard ok')
