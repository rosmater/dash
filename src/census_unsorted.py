# Rost 27.10: census 27.10 (contacts-last50) — все needs_sort=Y диалоги -> Мессенджеры «Нерассортированные» (вкл. без непрочитанных)
import csv, os
CENSUS = '/workspace/unread-census/2026-10-27/census-unified.csv'
CH = {'tg': 'Telegram', 'wa-esp': 'WhatsApp ESP', 'wa-ukr': 'WhatsApp UKR', 'viber': 'Viber'}
SEC = ('Секретарь', 'grokbot://app/v1/agent?id=d3a12cc9-cf8a-41e5-b34a-76d4ab9eb9fd')
def census_rows(path=CENSUS):
    if not os.path.exists(path): return []
    out = []
    for r in csv.DictReader(open(path, encoding='utf-8')):
        if r.get('needs_sort') != 'Y' or 'БЕЗПЕЧНИЙ РЕГІОН' in (r.get('name') or '').upper(): continue
        ch = CH.get(r['channel'], r['channel']); t = (r['name'] or '').strip()
        u = (r.get('unread') or '').strip()
        # Rost t4989: census 27.10 — только сортировка/сфера; unread снимка устарел → 0 (живое unread даёт reconcile/watchers/live)
        n = 0
        kind = 'census 27.10 / нет сферы' + (' · предл.: ' + r['proposed_sphere'] if r.get('proposed_sphere') else '') + (' · 📌' if r.get('pinned') == 'Y' else '')
        if u == 'Y' or (u.isdigit() and int(u) > 0):
            kind += ' · было unread в снимке (сброшено t4989)'
        kind = kind.replace('Личное · Dating', 'Дейтинг')  # Rost 27.10 rename
        out.append(dict(key=f'{ch}|{t}', channel=ch, title=t, kind=kind, unread=n, last='', owner=SEC[0], owner_link=SEC[1]))
    return out
def merge(uns, path=CENSUS, skip=()):
    skip = {k.lower() for k in skip}  # Rost 27.10 t3950u: TG с известной сферой уже в карточках сфер
    C = [c for c in census_rows(path) if c['key'].lower() not in skip]; ck = {c['key'].lower(): c for c in C}
    keep, seen = [], set()
    for u in uns:
        k = (u.get('key') or '').lower()
        if k in ck or k in seen or k in skip: continue
        seen.add(k); keep.append(u)
    for c in C:
        k = c['key'].lower()
        if k in seen: continue
        seen.add(k); keep.append(c)
    return keep
if __name__ == '__main__':
    import json, sys
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'data-test-ma.json')
    d = json.load(open(p)); b = len(d.get('unsorted') or [])
    d['unsorted'] = merge(d.get('unsorted') or [])
    json.dump(d, open(p, 'w'), ensure_ascii=False, indent=1)
    print('unsorted', b, '->', len(d['unsorted']))

# Rost 27.10 t3950u «пропали TG»: Telegram-чаты census с известной сферой (known_sphere или direction из chats.csv) и непрочитанными -> строки в карточках сфер Мессенджеров.
# Только метаданные (название, сфера, есть ли непрочитанные) — превью сообщений НЕ берём.
_KS = {'ОФ': 'ОФ', 'Табакевич': 'Табакевич', 'Личное': 'Личное', 'Недвижимость': 'Недвижимость', 'Пептиды': 'Пептиды', 'Оборонка': 'Оборонка', 'Личное · Dating': 'Дейтинг', 'Дейтинг': 'Дейтинг', 'Коучинг': 'Личное'}
def tg_sphere_rows(dir2sph, path=CENSUS, chats_csv='/home/box/contacts/chats.csv', people_csv='/home/box/contacts/people.csv'):
    """Rost t3952u: все каналы census (TG/WA/Viber) — сфера из known_sphere → chats.csv (key/title) → people.csv (имя/алиас). Не нашли — остаётся в «на сортировку»."""
    if not os.path.exists(path): return []
    CC = {}
    for r in csv.DictReader(open(chats_csv, encoding='utf-8')):
        st = (r.get('status') or '').lower()
        if any(x in st for x in ('ignore', 'dead', 'archived')): continue
        CC[r['chat_id']] = r; CC['t:' + r['title'].split(';')[0].strip().lower()] = r
    PP = {}
    if os.path.exists(people_csv):
        for r in csv.DictReader(open(people_csv, encoding='utf-8')):
            if not (r.get('direction') or '').strip(): continue
            if r.get('person_id'): PP['id:' + r['person_id']] = r
            for a in [r.get('wa_title') or ''] + (r.get('names_aliases') or '').replace(';', '|').split('|'):
                a = a.strip().lower()
                if len(a) >= 4 and not a.startswith('@'): PP['t:' + a] = r
    out = []
    for r in csv.DictReader(open(path, encoding='utf-8')):
        ch = CH.get(r.get('channel'), r.get('channel'))
        t = (r.get('name') or '').strip(); u = (r.get('unread') or '').strip()
        if not t or 'БЕЗПЕЧНИЙ РЕГІОН' in t.upper(): continue
        sp = _KS.get((r.get('known_sphere') or '').strip())
        if (r.get('known_sphere') or '').strip() == 'Игнор': continue
        if not sp:
            c = CC.get(r.get('match_chats_key') or '') or CC.get('t:' + t.lower())
            if not c: c = PP.get('id:' + (r.get('match_people_id') or '')) or PP.get('t:' + t.lower())
            sp = dir2sph(c['direction']) if c else None
        if not sp: continue
        if u == 'N': out.append((sp, dict(key=f'{ch}|{t}', chat=t, norow=True))); continue  # сфера известна, непрочитанных нет -> не в «сортировку», строки не надо
        # Rost t4989: в сферы кладём для карты чатов, unread=0 (снимок 27.10 не актуален); живое unread — viber_live / reconcile / secretary-log
        note = 'было unread в снимке' if (u == 'Y' or (u.isdigit() and int(u) > 0)) else ('snapshot ' + u if u else 'snapshot')
        out.append((sp, dict(sender=t, chat=t, channel=ch, unread_chat=0, items=0, kinds={}, last='', binding=None,
                             src='census 27.10 (список чатов ' + ch + '; ' + note + '; unread cleared t4989)',
                             src_sphere=sp, owner=SEC[0], owner_link=SEC[1], key=f'{ch}|{t}')))
    return out
