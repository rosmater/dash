"""TEST (Rost 26.10): data for test-messengers-assistants.html. METADATA ONLY — тела сообщений НЕ читаются в вывод.
Из secretary-log берём: время, канал, чат, отправитель, unread, тип (фото/голос/текст). Текст после ':' отбрасывается."""
import re, json, os, csv
ROOT = os.path.join(os.path.dirname(__file__), '..')
LOG = '/workspace/notify-watchers/secretary-log.md'
CU = lambda t: f'https://rosmater.github.io/cu/?t={t}'
CH = {'whatsapp-ukr-secretary':'WhatsApp UKR','UKR':'WhatsApp UKR','ESP':'WhatsApp ESP','whatsapp-esp-secretary':'WhatsApp ESP',
      'tg':'Telegram','telegram-secretary':'Telegram','TG':'Telegram','email':'Email'}
# ALLOWLIST: чат/отправитель принимаются только если совпадают с известными именами из chats.csv/people.csv.
# Всё, что не совпало (например, цитата в позиции заголовка) — отбрасывается, чтобы текст сообщений не попал в вывод.
KNOWN = []  # (needle_lower, display, sphere)
for r in csv.DictReader(open('/home/box/contacts/chats.csv', encoding='utf-8')):
    t = r['title'].split(';')[0].strip()
    if r['status'] in ('ignore','dead','ignore_channel','archived_ignore') or len(t) < 3: continue
    KNOWN.append((t.lower(), t, r['direction'] or 'Прочее'))
for r in csv.DictReader(open('/home/box/contacts/people.csv', encoding='utf-8')):
    for a in [r['wa_title']] + r['names_aliases'].replace(';','|').split('|'):
        a = a.strip()
        if len(a) >= 4 and not a.startswith('@'): KNOWN.append((a.lower(), a if a == r['wa_title'] else r['names_aliases'].split('|')[0].split(';')[0].strip(), r['direction'] or 'Прочее'))
KNOWN += [('alexa herera','Alexa Herera Mr Supremo','dating/recruiting'), ('maria mr med','Maria MR Med','dating/recruiting'), ('артем донтабак','Артем ДонТабак','Tabakevich')]
KNOWN.sort(key=lambda x: -len(x[0]))
def known(txt):
    tl = (txt or '').lower()
    for n, d, sph in KNOWN:
        if n in tl: return d, sph
    return None, None
SENDERS = ['Анатолий','Ирина Шекель','Elena Tolstova','Albeiro']
chats = {}
UNK = {}
for ln in open(LOG, encoding='utf-8'):
    m = re.match(r'- (2026-\d\d-\d\d) (\d\d:\d\d) (?:Bogotá|COT)?\s*\|?\s*([\w-]+)', ln)
    if not m: continue
    day, tm, ch = m.groups()
    if day < '2026-10-21': continue  # Rost 26.10: полный снимок лога (с 21.10)
    seg = ln.split('|')
    if len(seg) < 3: continue
    chat, sph = known(seg[2])
    if not chat:
        # неизвестный чат: берём заголовок ТОЛЬКО если он похож на имя чата (без кавычек/OUT/тире-пояснений) -> в «Нерассортированные»
        t = re.sub(r'\s*\(\d+ unread\)', '', seg[2]).strip()
        if ch.upper() != 'VIBER' and 'test' not in ch.lower() and t not in ('TEST',) and t and len(t) <= 40 and not re.search(r'[«»"“”:—]|^OUT\b|\?|!', t):
            UNK.setdefault(t, dict(title=t, channel=CH.get(ch, ch), last=f'{day} {tm}', unread=None))['last'] = f'{day} {tm}'
            un0 = re.findall(r'\((\d+) unread\)', ln)
            if un0: UNK[t]['unread'] = int(un0[-1])
        continue
    sender = next((x for x in SENDERS if len(seg) > 3 and seg[3].strip().startswith(x)), None) or next((x for x in SENDERS if x in seg[2]), None) or chat
    un = re.findall(r'\((\d+) unread\)', ln)
    kind = 'фото' if re.search(r':\s*Photo|фото без', ln) else ('голосовое' if re.search(r'voice|голосов|аудио', ln, re.I) else 'текст')
    c = chats.setdefault(chat, dict(chat=chat, channel=CH.get(ch, ch), sphere=sph, senders={}, last=f'{day} {tm}', unread=0))
    s = c['senders'].setdefault(sender, dict(n=0, kinds={}, last=''))
    s['n'] += 1; s['kinds'][kind] = s['kinds'].get(kind, 0) + 1; s['last'] = f'{day} {tm}'
    c['last'] = f'{day} {tm}'
    if un: c['unread'] = max(c['unread'], int(un[-1]))
# Сферы и binding (CU) — ручная карта по people.csv/chats.csv + поиск ClickUp 26.10 (только названия/ID карточек)
def SPH(d):
    d=(d or '').lower()
    # Rost 26.10 вечер: (ES→Недвижимость; НО Maks Sinar = Личное, override ниже): ES / legal (адвокаты по объектам/okupas) = Недвижимость, как в ▼ «без сообщений» (_dir2sph)
    for k,v in [('es /','Недвижимость'),('legal','Юр. / налоги'),('realty','Недвижимость'),('repairs','Недвижимость'),('legal','Юр. / налоги'),('dating','Dating / личное'),('of','OF'),('tabakevich','Tabakevich'),('peptid','Пептиды'),('friend','Личное'),('personal','Личное'),('food','Быт / еда')]:
        if k in d: return v
    return 'Прочее'
BIND = {
  'Анатолий': dict(kind='работа', ws='work', tasks=[('86bawjfqf','ПОСЛЕ ТОПАСИО: решить по ремонту (ждём смету Анатолий)'),('86b6k34a6','БОТ: Локаль ремонт — Анатолий как дела?'),('86bbzjbuf','БОТ: Капает кондиционер — пофиксить (Анатолий)')]),
  'Ирина Шекель': dict(kind='работа', ws='work', tasks=[('86b6j4f2n','Topacio 1 (объект)'),('86ba3bwhg','БОТ: Установка сигналки на Топасио')]),
  'Alexa Herera': dict(kind='девушка', ws='private', card=('86ahu5d5w','Alexa Herera MrSupremo')),
}
def bind(name):
    for k, v in BIND.items():
        if k.lower() in name.lower(): return v
    return None
groups = {}
def add(sphere, item): groups.setdefault(sphere, []).append(item)
for c in chats.values():
    if 'Alexa' in c['chat'] or 'Pulpo' in c['chat'] or 'Albeiro' in c['chat']: continue  # ниже вручную
    sph = SPH(c['sphere'])
    if 'Maks Sinar' in c['chat']: sph = 'Недвижимость'  # Rost t3961u 27.10: Maks Sinar (адвокат okupas) → Недвижимость (было Личное 26.10)
    for nm, s in c['senders'].items():
        b = bind(nm)
        add(sph, dict(sender=nm, chat=c['chat'], channel=c['channel'], unread_chat=c['unread'], items=s['n'], kinds=s['kinds'], last=s['last'], binding=b, src='secretary-log'))
# Rost 26.10 ~21:10: Dating = снимок от бота Дейтинг (INBOX 26.10 21:08 Bogotá). Alexa «время встречи» убрана (нет в списке Дейтинга). Владелец строк — Дейтинг.
_DAT = ('Дейтинг', '826f2d29-4f19-4096-9e4e-c76d6ec801a8')
_DSRC = 'dating INBOX 26.10 21:08'
for _s, _ch, _p, _l in [
    ('piggy_cami', 'Feabie', 'наш ход: «Me gusta series y pedir» / «¿quieres darme de comer hoy?»', '2026-10-26 21:08'),
    ('Stuffiejosie', 'Feabie', 'наш ход: «Comer, dormir, sexo jajaja»', '2026-10-26 21:08'),
    ('Donut_piggy', 'Feabie', 'наш ход: «Maragarita una isla» + фото → черновик Rost', '2026-10-26 21:08'),
    ('Leidy', 'Tinder', 'наш ход: «No he tenido la oportunidad…» (с 22.10)', '2026-10-22'),
    ('Samy', 'Tinder', 'наш ход: «Hola en estadio» (с 22.10)', '2026-10-22'),
    ('Adelina_meilo', 'Feabie', 'нужен ок Rost на текст без «te invito»', '2026-10-26 21:08'),
    ('Lauu', 'Tinder', 'ответ в очереди — нужна команда Rost на отправку', '2026-10-26 21:08'),
    ('Dahian', 'Tinder', 'нужно да/нет Rost на мягкое сообщение', '2026-10-26 21:08'),
    ('Andrea Feabie 💘D', 'WhatsApp ESP', 'ждём её: ответили 20:47 (перепутал даты / след. неделя) — мяч у неё', '2026-10-26 20:47'),
    ('María Camila', 'WhatsApp ESP', 'ждём её: наше ушло', '2026-10-26 21:08'),
    ('Layla', 'WhatsApp ESP', 'ждём её: WA 1 галочка / Tinder отправлено', '2026-10-26 21:08'),
]:
    add('Dating / личное', dict(sender=_s, chat=_s, channel=_ch, unread_chat=None, items=1, kinds={'диалог':1}, last=_l, binding=None, pending=_p, src=_DSRC, sorted=True, owner=_DAT[0], owner_link=f'grokbot://app/v1/agent?id={_DAT[1]}'))
add('Быт / еда', dict(sender='Albeiro Garcia (El Pulpo)', chat='Albeiro Garcia Курьер Севичерия Пульпо', channel='WhatsApp ESP', unread_chat=2, items=1, kinds={'текст':1}, last='2026-10-26 17:48', binding=None, pending='ждём сумму заказа → оплата Bre-B', src='secretary-log'))
# Rost t4004u: Base Loft — поиск лофта (CU 86bcma7tp) в Личном. Факты: knowledge/shared-personal/places/base-loft-rental-search.md + /workspace/base-loft/*-chat-log.md. Портерия = доставки, не аренда — не добавляем.
_PMH = ('Помощник по всему', 'fef07752-2a22-4e1a-804b-7590fa230b30')
for _s, _c, _p, _l, _h in [
    ('Víctor Márquez (Nutibara 1105)', 'Nutibara 1105', 'ждём Víctor: наше 26.10 15:41 про A1105 (✓✓, не прочитано на 18:46; дальше только автошаблон)', '2026-10-26 15:41', '2026-10-26'),
    ('Miguel Calipso (CALIPTO)', 'Miguel Calipso', 'ждём Calipso: дуплекс 10 эт. 2.6M — запрос 18.10 18:37, ответа нет', '2026-10-18 18:37', '2026-10-18'),
    ('Nini Loaiza (Alnago, A1105)', 'Alnago', 'ждём Nini: новых непрочитанных нет, ход за ней (Rost t4010u/t4011u); её последнее 27.10 08:51 — для estudio нужны tomador + deudor (поручитель)', '2026-10-27 08:51', '2026-10-27'),
]:
    add('Личное', dict(sender=_s, chat=_c, channel='WhatsApp ESP', unread_chat=None, items=1, kinds={'аренда':1}, last=_l, binding=None, pending=_p, src='base-loft-rental-search.md', sorted=True, owner=_PMH[0], owner_link=f'grokbot://app/v1/agent?id={_PMH[1]}', hang_since=_h, is_group=False))
add('Недвижимость', dict(sender='Анатолий / Ирина Шекель', topic='Travertino — наличные', chat='Ростислав - Анатолий ремонты', channel='WhatsApp UKR', unread_chat=None, items=1, kinds={'договорённость':1}, last='2026-10-26 15:56', binding=BIND['Анатолий'], pending='наличные — на следующей неделе (договорились)', src='контекст'))
add('Недвижимость', dict(sender='Анатолий / Ирина Шекель', topic='Доставка шкафов (Amazon/IKEA)', chat='Ростислав - Анатолий ремонты', channel='WhatsApp UKR', unread_chat=None, items=1, kinds={'слоты':1}, last='2026-10-26 15:40', binding=None, pending='контакт в доставке — Шекель (Rost 27.10); слоты после 18:00', src='контекст'))
# Rost 26.10 20:19: Viber «БЕЗПЕЧНИЙ РЕГІОН» = мусор (сообщество) -> игнор; статус Viber-вочера только в мониторе
# Rost 26.10 «я совсем не вижу телеграмм»: TG-вочер (tg-secretary) пишет только в свой watcher.log, не в secretary-log -> строки TG не было.
# Берём только статус вочера (метаданные: время START/последнего уведомления), без текстов. Непрочитанные в TG вочер не считает -> None.
def _tg_status():
    import subprocess
    wl = '/workspace/notify-watchers/tg-secretary/state/watcher.log'
    last_start = last_notif = None
    try:
        for ln in open(wl, encoding='utf-8', errors='ignore'):
            ts = ln[:16].replace('T', ' ')
            if ' START ' in ln: last_start = ts
            elif ' POSTED ' in ln or ' SKIP ' in ln: last_notif = ts
    except FileNotFoundError: pass
    up = subprocess.run(['pgrep', '-f', 'tg_watcher.py'], capture_output=True).returncode == 0
    app = subprocess.run(['pgrep', '-f', 'apps/telegram/Telegram/Telegram'], capture_output=True).returncode == 0
    if not up or not app:
        st, txt = 'red', ('Telegram Desktop не запущен' if not app else 'tg_watcher не запущен') + (f' · последний старт {last_start}' if last_start else '')
    elif not last_notif or (last_start and last_notif < last_start and last_notif[:10] < last_start[:10]):
        st, txt = 'warn', f'запущен {last_start}; уведомлений не ловил с {last_notif or "—"} — проверить, что TG Desktop шлёт уведомления (D-Bus)'
    else:
        st, txt = 'ok', f'работает · старт {last_start} · последнее уведомление {last_notif}'
    return st, txt, last_notif
# Rost 26.10 вечер «в TG куча непрочитанных, тьма»: вочер ловит только D-Bus-уведомления (их нет с 21.10, muted чаты не уведомляют) -> unread TG были 0.
# Реальный счётчик: заголовок окна Telegram Desktop на боксе = «Telegram (N)» (N = бейдж непрочитанных TG). Читаем только заголовок (xdotool), без текстов.
def _tg_unread():
    import subprocess, glob as _g
    try:
        pid = subprocess.run(['pgrep', '-f', 'apps/telegram/Telegram/Telegram'], capture_output=True, text=True).stdout.split()[0]
        env = dict(x.split('=', 1) for x in open(f'/proc/{pid}/environ').read().split('\0') if '=' in x)
        out = subprocess.run(['xdotool', 'search', '--class', 'Telegram', 'getwindowname', '%@'], capture_output=True, text=True, env={**os.environ, 'DISPLAY': env.get('DISPLAY', ':9')}, timeout=10).stdout
        n = [int(m) for m in re.findall(r'Telegram \((\d+)\)', out)]
        import datetime as _dt
        return (max(n) if n else 0), _dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    except Exception:
        return None, ''
TG_UNREAD, TG_UNREAD_AT = None, ''  # Rost 26.10 21:14: заголовок окна TG = «Telegram (26 млн)» (сообщения вкл. каналы, плавает) — не диалоги; агрегат не показываем, ждём разбор по чатам
if False:  # Rost 26.10 20:19: Telegram — канал, не сфера; статус вочера — в мониторе сверху
    _st, _txt, _ln = _tg_status()
    add('Telegram', dict(sender='Telegram (все чаты)', chat='Telegram (все чаты)', channel='Telegram', unread_chat=None, items=0, kinds={}, last=_ln or '', binding=None, client='Telegram Desktop на боксе', watcher=_txt, watcher_st=_st, src='tg-secretary watcher.log (только статус)'))
# Rost 26.10: Email — только важные (ma_email_important.json), не все письма
for e in json.load(open(os.path.join(os.path.dirname(__file__), 'ma_email_important.json')))['items']:
    e = dict(e); add(e.pop('sphere', 'Email · важное'), e)
# Rost 26.10: один диалог = одна строка/идентичность (напр. «Ростислав - Анатолий ремонты», WA UKR «Maks Sinar Адвокат Испания» + Elena Tolstova).
# Сливаем по (канал, чат); разные вопросы/темы этого диалога — вложены списком topics внутри одной строки.
for _sp, _rows in groups.items():
    _by, _out = {}, []
    for r in _rows:
        k = (r.get('channel'), r.get('chat'))
        if k[1] and k in _by: _by[k].append(r)
        else: _by[k] = [r]; _out.append(k)
    res = []
    for k in _out:
        L = _by[k]
        if len(L) == 1: res.append(L[0]); continue
        m = dict(next((r for r in L if r.get('sender') == r.get('chat') and not r.get('topic')), next((r for r in L if not r.get('topic')), L[0])))
        ppl = []
        for r in L:
            for nm in (r.get('sender') or '').split(' / '):
                if nm and nm != k[1] and nm not in ppl: ppl.append(nm)
        m['sender'] = k[1]; m['also'] = ppl; m.pop('topic', None)
        m['topics'] = [dict(who=r.get('topic') or r.get('sender'), q=r['pending'], last=r.get('last', '')) for r in L if r.get('pending')]
        m['items'] = sum(r.get('items') or 0 for r in L)
        kinds = {}
        for r in L:
            for kk, vv in (r.get('kinds') or {}).items(): kinds[kk] = kinds.get(kk, 0) + vv
        m['kinds'] = kinds; m['last'] = max(r.get('last') or '' for r in L)
        u = [r['unread_chat'] for r in L if r.get('unread_chat') is not None]; m['unread_chat'] = max(u) if u else None
        m['pending'] = '; '.join(t['who'] + ': ' + t['q'] for t in m['topics']) if m['topics'] else None
        m['planned'] = all(r.get('planned') for r in L)
        m['binding'] = next((r['binding'] for r in L if r.get('binding')), None)
        res.append(m)
    groups[_sp] = res
# Rost 26.10 20:19: сферы = направления дашборда (Быт/Юр/Финансы = Личное; Dating отдельно под Личным); канал (Viber/Telegram) — не сфера
_IGN = {'безпечний регіон'}
_MAP = {'Быт / еда': 'Личное', 'Личное': 'Личное', 'Юр. / налоги': 'Личное', 'Финансы / банки': 'Личное', 'Dating / личное': 'Дейтинг',
        'Tabakevich': 'Табакевич', 'OF': 'ОФ', 'Пептиды': 'Пептиды', 'Недвижимость': 'Недвижимость', 'Оборонка': 'Оборонка'}
_ORD = ['Личное', 'Дейтинг', 'Недвижимость', 'Табакевич', 'ОФ', 'Пептиды', 'Оборонка']
_g2 = {}
for _sp, _rows in groups.items():
    for r in _rows:
        if any(x in ((r.get('sender') or '') + ' ' + (r.get('chat') or '')).lower() for x in _IGN): continue
        r.setdefault('src_sphere', _sp)
        _g2.setdefault(_MAP.get(_sp, 'Прочее'), []).append(r)
groups = {k: _g2[k] for k in sorted(_g2, key=lambda k: _ORD.index(k) if k in _ORD else 99)}
UNK = {k: v for k, v in UNK.items() if not any(x in k.lower() for x in _IGN)}
# Rost 26.10 20:22: под КАЖДОЙ сферой свёрнутый мелкий ▼ «без сообщений» — контакты/чаты этой ниши из chats.csv, у кого сейчас нет висящих
def _dir2sph(d):
    d = (d or '').lower().strip()
    # Rost t3953u: тапы даша пишут в chats.csv direction = имя сферы («ОФ», «Табакевич», «Дейтинг»…) — принимаем как есть, не роняем в «Личное»
    _EX = {'оф': 'ОФ', 'табакевич': 'Табакевич', 'личное': 'Личное', 'дейтинг': 'Дейтинг', 'личное · dating': 'Дейтинг', 'недвижимость': 'Недвижимость', 'пептиды': 'Пептиды', 'оборонка': 'Оборонка', 'коучинг': 'Личное'}
    if d in _EX: return _EX[d]
    if d in ('игнор', 'ignore'): return None
    if not d or d in ('—', '-', '?') or d.startswith('noise'): return None
    for ks, sp in [(('of', 'oftv', 'onlyfans', 'novax'), 'ОФ'), (('tabakevich', 'кальян'), 'Табакевич'), (('peptid', 'пептид'), 'Пептиды'),
                   (('es ', 'es/', 'realty', 'repairs', 'okupas', 'olivino', 'недвиж'), 'Недвижимость'), (('dating',), 'Дейтинг'),
                   (('defense', 'оборон', 'ste'), 'Оборонка')]:
        if any(d.startswith(k) or (' ' + k) in d or ('/' + k) in d for k in ks): return sp
    return 'Личное'
_have = {(r.get('chat') or '').lower() for rs in groups.values() for r in rs} | {(r.get('sender') or '').lower() for rs in groups.values() for r in rs}
_ZC = {}
for r in csv.DictReader(open('/home/box/contacts/chats.csv', encoding='utf-8')):
    t = r['title'].split(';')[0].strip(); st = (r['status'] or '').lower()
    if not t or any(x in st for x in ('ignore', 'dead', 'archived')) or any(x in t.lower() for x in _IGN): continue
    sp = _dir2sph(r['direction'])
    if not sp or t.lower() in _have or any(t.lower() in h or (h and h in t.lower()) for h in _have if len(h) > 4): continue
    _ZC.setdefault(sp, []).append(dict(title=t, channel=r['channel'], status=r['status']))
# Rost 27.10 t3950u+t3952u: census (TG/WA/Viber) из (известная сфера / direction chats.csv, с непрочитанными) -> в карточки сфер, не в «на сортировку»
_TG_PLACED = set()
try:
    __import__('sys').path.insert(0, os.path.dirname(os.path.abspath(__file__))); from census_unsorted import tg_sphere_rows as _tgr
    for _sp, _r in _tgr(_dir2sph):
        if _r.get('norow') or (_r['chat'] or '').lower() in _have: _TG_PLACED.add(_r['key']); continue
        groups.setdefault(_sp, []).append(_r); _TG_PLACED.add(_r['key']); _have.add(_r['chat'].lower())
        if _sp in _ZC: _ZC[_sp] = [z for z in _ZC[_sp] if z['title'].lower() != _r['chat'].lower()]
    print('census -> сферы:', len(_TG_PLACED))
except Exception as _e: print('TG census skip', _e)
# Rost t3953u: сборка СЛИВАЕТ сферы, а не заменяет вслепую — если канал в прошлой сборке был в карточках сфер, а сейчас 0 строк,
# переносим его прошлые строки (с пометкой), чтобы источник-сбой не обнулял Мессенджеры. Плюс страж guard_spheres.py перед пушем.
try:
    _prev = json.load(open(os.path.join(ROOT, 'data-test-ma.json')))
    _now = {r.get('channel') for rs in groups.values() for r in rs}
    _cf = 0
    for _g in _prev.get('messengers', []):
        for _r in _g.get('rows', []):
            _c = _r.get('channel')
            if _c in _now or _c in ('ClickUp', 'Email') or (_r.get('chat') or '').lower() in _have: continue
            _r = dict(_r); _r['src'] = (_r.get('src') or '') + ' · перенесено из прошлой сборки (источник канала сейчас пуст)'
            groups.setdefault(_g['sphere'], []).append(_r); _have.add((_r.get('chat') or '').lower()); _cf += 1
    if _cf: print('carry-forward строк:', _cf)
except Exception as _e: print('carry-forward skip', _e)
for sp in _ORD:
    if sp in _ZC and sp not in groups: groups[sp] = []
groups = {k: groups[k] for k in sorted(groups, key=lambda k: _ORD.index(k) if k in _ORD else 99)}
# Rost 26.10 22:20: сфера Табакевич в Мессенджерах ОСТАЁТСЯ (откат 21:16 — «Кальяны» убрать только из названия вкладки)
data = dict(generated='2026-10-26 Bogotá', test=True, messengers=[dict(sphere=k, rows=v, zero_contacts=sorted(_ZC.get(k, []), key=lambda z: z['title'].lower())) for k, v in groups.items()])
# Боты/ассистенты: сводные открытые вопросы (кратко, без дампов чатов)
A = lambda id_: f'grokbot://app/v1/agent?id={id_}'
# Rost 26.10 (аудит 19:35 Bogotá): реальные открытые вопросы из последних сообщений ботов (ReadTranscript) + задачи CU for check по владельцу (OWNERSHIP.md).
# st: red = встало/нужен Rost сейчас; green = норм/ждём; new = свежий отчёт (🟡). status бота считается ниже.
data['bots'] = [
 dict(name='Секретарь', id='d3a12cc9-cf8a-41e5-b34a-76d4ab9eb9fd', qs=[
   dict(q='Alexa: время встречи 26.10 — проверить, актуально ли (нет в списке Дейтинга 21:08)', st='red', ctx='Alexa Herera WA ESP 17:34 спросила время на пн 26.10; черновик «¿Te queda bien a las [HORA]?» ждёт время от Rost'),
   dict(q='Анатолий/Шекель: чей контактный номер в доставке шкафов? → Шекель (Ирина Шекель)', st='green', answered=True, ctx='Rost t3931u 27.10: «Шекель»'),
   dict(q='Доставка IKEA 29.10, окно 15:00–21:00 — кто принимает?', st='red', new=True, ctx='WA UKR ремонты 15:39–15:40'),
   dict(q='El Pulpo: оплатить Bre-B после суммы от Albeiro', st='red', new=True, ctx='Заказ ушёл 17:48; Rost сказал «плати сам»; ждём сумму'),
   dict(q='Travertino: наличные на следующей неделе — подтвердить сумму/день', st='red', ctx='WA UKR ремонты 15:54–15:56'),
   dict(q='BTC резерв: вернуть 0.02318012 BTC на неделе с 27.10 — напоминание пн 3.11?', st='red', ctx='finance/btc-reserves-repayment.md'),
   dict(q='Viber-вочер: AUMID не найден — toast могут не ловиться (дописать вручную)', st='red', new=True, ctx='AX42 wa-ukr-12promax-p, вочер с 19:04'),
   dict(q='Telegram-вочер: запущен 17:46, но уведомлений не ловил с 21.10 — проверить D-Bus', st='red', new=True, ctx='tg-secretary/state/watcher.log'),
   dict(q='Джинсы из ателье — вт 27.10 16:00 (86bcrqtyk)', st='green', answered=True, ctx='Задача создана'),
 ]),
 dict(name='Помощник по всему', id='fef07752-2a22-4e1a-804b-7590fa230b30', qs=[
   # Rost t4124–25 HARD: no hardcoded qs — only QUEUE.md slug (ctx QUEUE.md <slug>) or ma_q.py
 ]),
 dict(name='Дейтинг', id='826f2d29-4f19-4096-9e4e-c76d6ec801a8', qs=[
   dict(q='Rappi: Ashwagandha KSM-66 заказан → Base Loft 605, вт 27.10 08–11, ~119 190 COP', st='green', new=True, answered=True, ctx='Дейтинг: заказ оформлен'),
 ]),
 dict(name='Фермовод', id='ceac86b3-b3e4-493e-8b5e-0c9372c46066', qs=[]),  # t4125: ig-hybrid → QUEUE ig-hybrid-sources
 dict(name='ОФ Маркетинг', id='6fa03b36-6aa2-4d75-81d6-164804ef329c', qs=[
   dict(q='Утренний запрос авторизации Sheets (429) — отбой, коннектор живой, новых заявок после Даниелы (161) нет', st='green', answered=True, ctx='ОФ Маркетинг 19:15'),
 ]),
 dict(name='Пептид', id='daa16204-faaf-46e9-8a1c-c696291c2b1d', qs=[]),  # t4125: qs via QUEUE slug / ma_q
 dict(name='Юрист / Адвокат / Бухгалтер', id='2a2b453a-50ae-4965-8b08-7f11780a48d1', qs=[]),  # t4125: mila → QUEUE mila-olivino-terminacion
 dict(name='Оборонка', id='221f23c8-f2dc-4ae3-8585-50b1404a32af', nodata='вопросы бота не собраны (чат не читался; id был с опечаткой 4ae5→4ae3, исправлен 26.10) — рутины ниже из inventory', qs=[]),
]

# === Rost 26.10 ~19:40: Notion / «супер мозг» — незаконченный разбор (без выдумок: из notion-brain/OPEN_QUESTIONS.md и /workspace/queue/QUEUE.md)
import re as _re
_SEC_ID, _HELP_ID = 'd3a12cc9-cf8a-41e5-b34a-76d4ab9eb9fd', 'fef07752-2a22-4e1a-804b-7590fa230b30'
_bot = lambda n: next(x for x in data['bots'] if x['name'] == n)
NOTION_OQ = '/home/box/contacts/knowledge/notion-brain/OPEN_QUESTIONS.md'
_oq = []
try:
    _txt = open(NOTION_OQ).read()
    _late = {int(m) for m in _re.findall(r'^- Q(\d+):', _txt, _re.M)}  # «Уточнения Rost» = отвечено
    for m in _re.finditer(r'^(\d+)\.\s+(.+)$', _txt, _re.M):
        n, t = int(m.group(1)), m.group(2).strip()
        if n in _late: continue
        if '→' in t and 'В РАБОТЕ' not in t: continue
        _oq.append((n, t.split('→')[0].strip(), 'В РАБОТЕ' in t))
except Exception as e:
    _oq = []
_G = '🧠 Notion · супер мозг'
if _oq:
    # Rost t4097u: сводная красная строка «Notion / супер мозг: N неразобранных» дублировала блок «🔴 🧠 Notion · супер мозг — я нужен (N)» в «🙋 Ожидает ответа» — убрана; блок сам 🔴 и считается в «Требует внимания» (revGroups)
    for n, t, wip in _oq:
        _bot('Секретарь')['qs'].append(dict(q=f'№{n}. {t[:170]}{"…" if len(t) > 170 else ""}' + (' (в работе)' if wip else ''), st='green', grp=_G, ctx=f'notion-brain/OPEN_QUESTIONS.md №{n}'))
# Rost t4103u: под «🙋 Ожидает» больше НИЧЕГО с «Notion» в тексте — иначе рядом с блоком «🔴 🧠 Notion · супер мозг» снова выглядит как дубль.
# Tabakevich GDrive (10 файлов Ирины) остаётся красным вниманием, но без слова Notion в заголовке.
for q, ctx in [('Tabakevich · GDrive: 10 файлов — жду Ирину (остальные доступы закрыты)', 'QUEUE.md notion-instructions [blocked-Rost]')]:  # t4072 MindMeister закрыт; t4103 без «Notion» в q
    _bot('Секретарь')['qs'].append(dict(q=q, st='red', ctx=ctx))  # без grp — не гасит revGroups блока супер мозга
# Rost t4122–23: эти 6 были HARDCODED и не снимались queue_autoclear (ctx не QUEUE.md <slug>).
# Теперь только из /workspace/queue-helper/QUEUE.md: открытые строки с slug notion-places-* (pending/in_progress/waiting_user).
# Закрыл → [done DD.MM] notion-places-<slug> — авто-снятие через queue_autoclear (ctx=QUEUE.md notion-places-<slug>).
_HELP_Q = '/workspace/queue-helper/QUEUE.md'
try:
    _hq = open(_HELP_Q, encoding='utf-8').read()
except Exception:
    _hq = ''
# Helper qs only for waiting_user (+ notion-places still open) with slug → autoclear via QUEUE.md <slug>
# pending/in_progress stay in «Задачи в очереди», не дублируем в «я нужен».
for _m in _re.finditer(r'^-\s*\[(waiting[_ ]?user|pending)[^\]]*\]\s+([a-z][\w-]{2,})\b\s*[—:-]?\s*(.*)$', _hq, _re.I | _re.M):
    _st, _slug, _rest = _m.group(1).lower().replace(' ', '_'), _m.group(2), (_m.group(3) or '').strip()
    if _st.startswith('pending') and not _slug.startswith('notion-places-'):
        continue  # обычный pending — только очередь
    _q = _rest or _slug
    if _slug.startswith('notion-places-'):
        _q = 'Notion-разбор мест/контактов: ' + _q
        _kw = dict(q=_q, st='green', grp=_G, ctx=f'QUEUE.md {_slug}')  # супер мозг via revGroups
    else:
        # t4183: waiting_user + нужен Rost → red; «ждём Имя/чужой ответ» → wait (не attn)
        _others = bool(_re.search(r'жд[её]м\b', _q, _re.I)) and not _re.search(r'\bRost\b|\bGO\b|от Rost|нужен (твой|Rost)', _q, _re.I)
        if 'waiting' in _st and not _others:
            _kw = dict(q=_q, st='red', ctx=f'QUEUE.md {_slug}')
        elif _others:
            _kw = dict(q=_q, st='green', wait=True, ctx=f'QUEUE.md {_slug}')
        else:
            _kw = dict(q=_q, st='green', ctx=f'QUEUE.md {_slug}')
    _bot('Помощник по всему')['qs'].append(_kw)

# === Rost 26.10 ~19:39: коучинг-боты + «Мама» (из вкладки Коучинг data.json: пункты «Я:» = нужен Rost)
try:
    _coach = next((x for x in json.load(open(os.path.join(os.path.dirname(__file__), '..', 'data.json')))['directions'] if x.get('kind') == 'people'), {}).get('people', [])
except Exception:
    _coach = []
for p in _coach:
    nm = 'Мама' if p['name'] == 'Мама' else 'Коучинг · ' + p['name']
    qs = []
    # Rost 26.10 20:13: пункты коучинга = ЗАДАЧИ (вкладка Коучинг), не вопросы ботов -> в Ассистенты не тянем
    for it in []:
        t = (it.get('text', '') if isinstance(it, dict) else it).lstrip('— ').strip()
        if not t: continue
        qs.append(dict(q=t, st='red' if t.startswith('Я:') else 'green', ctx=f'Коучинг · {p["name"]} · {p.get("goal","")} · src {p.get("src","")}'))
    cu = p.get('cu') or {}
    b = dict(name=nm, id=_SEC_ID, owner_note='отдельного нашего бота нет — ответственный по умолчанию Секретарь', qs=qs, coach=True)
    if False and cu.get('id'):
        b['tasks'] = [dict(id=cu['id'], name=cu.get('label', ''), list='Коучинг', updated='', status=cu.get('status', ''), new=False)]
    data['bots'].append(b)

# === «Общение ботов» (TG-группа Rost + Мама + её бот): каждое уведомление -> 🔴 требует внимания.
# Вочер tg-secretary пишет в watcher.log только время + название чата (текст не хранит). Суть вопроса — из src/ma_bots_group.json (дописывает бот, видевший сообщение).
_BG = 'Общение ботов'
_hits = []
try:
    for ln in open('/workspace/notify-watchers/tg-secretary/state/watcher.log', errors='ignore'):
        m = _re.match(r"^(\S+) .*chat='([^']*)'", ln)
        if m and _BG.lower() in m.group(2).lower() and 'test-hint' not in ln:
            _hits.append(m.group(1))
except Exception:
    pass
_hits = sorted(set(h[:16] for h in _hits))
try:
    _bgj = json.load(open(os.path.join(os.path.dirname(__file__), 'ma_bots_group.json'))).get('items', [])
except Exception:
    _bgj = []
_mama = next((x for x in data['bots'] if x['name'] == 'Мама'), None)
if _mama is None:
    _mama = dict(name='Мама', id=_SEC_ID, qs=[], coach=True); data['bots'].append(_mama)
_GB = '💬 TG «Общение ботов»'
for it in _bgj:
    if it.get('done'): continue
    _mama['qs'].insert(0, dict(q=f'«{_BG}» {it.get("time","")}: {it.get("gist","")}', st='red', grp=_GB, new=True, ctx=f'TG «{_BG}» · от {it.get("from","?")} · {it.get("time","")}'))
_known = {i.get('time', '')[:16] for i in _bgj}
for h in _hits:
    if h in _known: continue
    _mama['qs'].insert(0, dict(q=f'Новое в «{_BG}» {h.replace("T"," ")} — суть не записана (вочер текст не хранит), открой чат', st='red', grp=_GB, new=True, ctx=f'tg-secretary watcher.log {h}'))
_mama['watch'] = f'TG «{_BG}»: ' + (f'поймано уведомлений {len(_hits)}' if _hits else 'новых уведомлений нет') + ' · вочер tg-secretary (если он ловит TG — см. Покрытие)'
# Задачи CU for check (assignee Rost) -> бот-владелец по ключевым словам (OWNERSHIP.md)
_OWN_KW = [('ОФ Маркетинг', ['миле', 'офиса оф', 'трекера', 'of.tv - отчет', 'контроль of.tv', 'лолап', 'lolapop']),
           ('Юрист / Адвокат / Бухгалтер', ['парагвай']),
           ('Секретарь', ['окупас', 'топасио', 'пакистанец', 'andrea cali', 'sofia', 'aurora', 'ra180', 'пальма'])]
_cu_tasks = json.load(open(os.path.join(os.path.dirname(__file__), 'ma_clickup.json')))
_today = _cu_tasks['fetched'][:10]
# Rost t4197: вернул bot_attn wire (выпал при откате файла ~t4183; HTML читает t.need / b.reports)
# Rost t4142–43: bot_attn.jsonl (sync/) — бот пишет need=rost|ok на каждый CU for check; нет записи → rost (безопаснее)
# Rost t4144–46: тап с даша (src:'dash') действует ТОЛЬКО на текущий ответ: строка с rev/updated == task.updated из ma_clickup.
#   Есть строки с совпадающим rev → последняя из них. Нет → последняя НЕ-dash строка по cu. Нет и её → rost.
_ATTN_L, _ATTN_BOT = {}, {}
try:
    for _ln in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sync', 'bot_attn.jsonl'), encoding='utf-8'):
        try: _j = json.loads(_ln)
        except Exception: continue
        if _j.get('closed'): _j['need'] = 'ok'  # правило: закрыл / for check снят → ok
        if _j.get('cu') and _j.get('need') in ('rost', 'ok'):
            _ATTN_L.setdefault(str(_j['cu']), []).append(_j)
            if _j.get('bot') and _j.get('src') != 'dash': _ATTN_BOT[str(_j['cu'])] = {'Оборонные': 'Оборонка', 'Оборонные системы': 'Оборонка'}.get(_j['bot'], _j['bot'])
except FileNotFoundError: pass
def _attn_need(cid, upd):
    L = _ATTN_L.get(str(cid)) or []
    m = [j for j in L if (j.get('rev') or j.get('updated') or '') == (upd or '') and upd]
    if m: return m[-1]['need']
    nb = [j for j in L if j.get('src') != 'dash']
    return nb[-1]['need'] if nb else None
_ATTN = {}
for _t in _cu_tasks['tasks']:
    _n = _attn_need(_t['id'], _t.get('updated'))
    if _n: _ATTN[_t['id']] = _n
_CU_OWN = {}
_ATTN_CNT = {}
for t in _cu_tasks['tasks']:
    nl = t['name'].lower(); own = next((o for o, kws in _OWN_KW if any(k in nl for k in kws)), 'Помощник по всему')
    if any(x['name'] == _ATTN_BOT.get(t['id']) for x in data['bots']): own = _ATTN_BOT[t['id']]  # бот, записавший лог, = владелец (точнее ключевых слов)
    b = next(x for x in data['bots'] if x['name'] == own)
    _CU_OWN[t['id']] = own
    need = _ATTN.get(t['id'], 'rost'); t['need'] = need
    _c = _ATTN_CNT.setdefault(own, dict(rost=0, ok=0, unlogged=0)); _c[need] += 1
    if t['id'] not in _ATTN: _c['unlogged'] += 1
    row = dict(id=t['id'], name=t['name'], list=t['list'], updated=t['updated'], status=t['status'], new=t['updated'][:10] == _today, need=need)
    b.setdefault('tasks' if need == 'rost' else 'reports', []).append(row)  # ok → свёрнутые «Отчёты», не 🟡 и не new_count
data['bot_attn'] = dict(src='sync/bot_attn.jsonl', logged=len(_ATTN), per_bot=_ATTN_CNT)
print('bot_attn:', _ATTN_CNT)
# === Rost 26.10 ~20:15: общая база открытых вопросов /workspace/queue/ma_open_questions.json (ma_q.py) — боты добавляют/убирают; стабильный QID
import hashlib as _hl, datetime as _dtm
_QID = lambda bn, q: 'Q-' + _hl.sha1(f'{bn}|{q}'.encode()).hexdigest()[:6]
try: _OQ = json.load(open('/workspace/queue/ma_open_questions.json'))
except Exception: _OQ = dict(add=[], resolved={}, reopened={})
for z in _OQ.get('add', []):
    z['bot'] = {'Оборонные': 'Оборонка'}.get(z['bot'], z['bot'])  # Rost t3948u
    b = next((x for x in data['bots'] if x['name'] == z['bot']), None)
    if b is None: b = dict(name=z['bot'], id=_SEC_ID, qs=[]); data['bots'].append(b)
    b['qs'].append(dict(q=z['q'], st=z.get('st', 'red'), ctx=(z.get('ctx') or '') + f' · база вопросов {z.get("at","")}', new=True, _qid=z['qid']))  # t4183: default red
_RES = set(_OQ.get('resolved', {})) - set(_OQ.get('reopened', {}))
for b in data['bots']:
    for q in b['qs']: q['qid'] = q.pop('_qid', None) or _QID(b['name'], q['q'])
    b['qs'] = [q for q in b['qs'] if q['qid'] not in _RES]
data['oq'] = dict(built=_dtm.datetime.now().strftime('%Y-%m-%d %H:%M'), resolved=sorted(_OQ.get('resolved', {})), reopened={k: v.get('at', '') for k, v in _OQ.get('reopened', {}).items()})
# === Rost 26.10 ~19:46: «решённое не должно быть вообще» — отвеченные вопросы удаляем из данных
for b in data['bots']:
    b['qs'] = [q for q in b['qs'] if not q.get('answered')]
# === Rost 26.10: свёрнутые «Рутины · ок» по каждому боту (из /workspace/bot-routines-inventory/<BOT>.md, дампы ботов) + «Задачи в очереди» (QUEUE.md бота)
_INV = '/workspace/bot-routines-inventory/'
def _tbl(path, header_re):
    """строки markdown-таблицы под первым заголовком, совпавшим с header_re -> list[dict]"""
    try: L = open(path, encoding='utf-8').read().split('\n')
    except FileNotFoundError: return None
    i = next((k for k, l in enumerate(L) if _re.match(header_re, l)), None)
    if i is None: return []
    rows, hdr = [], None
    for l in L[i+1:]:
        if l.startswith('#'): break
        if not l.startswith('|'):
            if hdr: break
            continue
        cells = [c.strip() for c in l.strip().strip('|').split('|')]
        if hdr is None: hdr = [c.lower() for c in cells]; continue
        if set(''.join(cells)) <= set('-: '): continue
        rows.append({h: (cells[k] if k < len(cells) else '') for k, h in enumerate(hdr)} | {'_cells': cells})
    return rows
def _clean(t): return _re.sub(r'\*\*|`', '', t or '').strip()
def _routines(short, header_re, enabled_only_col=None):
    R = _tbl(_INV + short + '.md', header_re)
    if R is None: return None
    out = []
    for r in R:
        c = r['_cells']; name = _clean(r.get('routine') or r.get('name') or c[0])
        if name.isdigit() and len(c) > 1: name = _clean(c[1])
        sched = _clean(next((v for k, v in r.items() if k != '_cells' and ('schedule' in k or 'trigger' in k)), ''))
        sched = _re.sub(r'^CRON_TZ=\S+\s*', '', sched)
        st_col = _clean(r.get('status') or r.get('enabled/paused') or '')
        if enabled_only_col and 'enabled' not in st_col.lower(): continue
        note = _clean(r.get('notes') or (' '.join(c[4:]) if short == 'HELPER' else ''))
        low = (sched + ' ' + note + ' ' + st_col + ' ' + name).lower()
        if _re.search(r'\bonce\b|разово|one-off', low): continue  # разовые — уже отработали / не рутина
        st = 'fail' if 'failed' in low else 'new' if 'never run' in low else 'ok'
        folder = _clean(next((v for k, v in r.items() if k != '_cells' and 'folder' in k), '')).split()[0] if any('folder' in k for k in r) else ''
        last = _clean(next((v for k, v in r.items() if k != '_cells' and 'last run' in k), ''))
        if not last:
            m = _re.search(r'last (?:run|fired)[^0-9]{0,12}(\d{4}-\d\d-\d\d(?:[ T]\d\d:\d\d)?)', low)
            last = m.group(1) if m else ''
        out.append(dict(name=name, sched=sched, st=st, note=note[:140], folder=folder.strip('`'), last=last[:16].replace('T', ' ')))
    return out
_RT = {'Секретарь': ('COMMS', r'^## Enabled', None), 'Помощник по всему': ('HELPER', r'^## LIVE enabled', None),
       'Дейтинг': ('DATING', r'^## LIVE enabled', None), 'ОФ Маркетинг': ('OF', r'^## Index', 'status'),
       'Юрист / Адвокат / Бухгалтер': ('LAWYER', r'^## Inventory refresh 2026-10-26', 'status'), 'Оборонка': ('DEFENSE', r'^\| name', 'enabled/paused')}
for b in data['bots']:
    if b['name'] in _RT:
        sh, hr, col = _RT[b['name']]
        if sh == 'DEFENSE':  # таблица без заголовка-секции
            b['routines'] = _routines(sh, r'^# ', col)
        else:
            b['routines'] = _routines(sh, hr, col)
        b['routines_src'] = f'bot-routines-inventory/{sh}.md'
        if b['routines'] is not None and not b['routines']: b['routines_note'] = 'активных рутин нет'
    elif b['name'] in ('Пептид', 'Фермовод'):
        b['routines'] = None; b['routines_note'] = 'дампа рутин в bot-routines-inventory нет — бот не выгружал'
# Задачи в очереди: строки «- [статус] …» из QUEUE.md бота, без done/x/standing (Rost: решённое не показывать)
_Q = {'Секретарь': '/workspace/queue/QUEUE.md', 'Помощник по всему': '/workspace/queue-helper/QUEUE.md', 'ОФ Маркетинг': '/workspace/queue-of/QUEUE.md',
      'Дейтинг': '/workspace/dating/QUEUE.md', 'Пептид': '/workspace/queue-peptid/QUEUE.md', 'Фермовод': '/home/box/contacts/knowledge/ig-farm/QUEUE.md',
      'Юрист / Адвокат / Бухгалтер': '/workspace/queue-lawyer/QUEUE.md',
      'Оборонка': '/home/box/contacts/knowledge/defense-export/QUEUE.md'}  # was «Оборонные системы»; dash bot name = Оборонка (t4183 Defense)
_Q_SKIP = ['Rappi на Redmi']  # уже сделано (заказ Rappi оформлен 26.10), в QUEUE.md не закрыто
for b in data['bots']:
    f = _Q.get(b['name'])
    if not f: continue
    try: L = open(f, encoding='utf-8').read().split('\n')
    except FileNotFoundError: continue
    out = []
    for l in L:
        m = _re.match(r'^(?:- |## )\[([^\]]*)\]\s*(.*)$', l)
        if not m: continue
        st, t = m.group(1).strip(), m.group(2)
        t = _re.sub(r'^\[[^\]]*\]\s*', '', t)  # вторая скобка статуса
        sl = st.lower()
        if _re.match(r'^(done|x\b|x$|standing|\d)', sl) or sl.startswith('x '): continue  # \d = строка журнала с временем
        t = _clean(t)
        if any(k in t for k in _Q_SKIP): continue
        lab = _re.split(r'\s+\d|\s+—|:', st or 'в очереди')[0].strip() or 'в очереди'
        out.append(dict(st=lab[:22], t=t[:180] + ('…' if len(t) > 180 else '')))
    b['queue'] = out; b['queue_src'] = f.replace('/home/box/contacts/knowledge/', 'knowledge/')
# === Rost t4125: open QUEUE waiting_user/blocked-Rost with slug → qs (autoclear on [done])
_Q_TO_BOT = {v: k for k, v in _Q.items()}
for _qf, _bn in _Q_TO_BOT.items():
    try:
        _bt = next(x for x in data['bots'] if x['name'] == _bn)
    except StopIteration:
        continue
    try:
        _ql = open(_qf, encoding='utf-8').read()
    except FileNotFoundError:
        continue
    for _m in _re.finditer(r'^-\s*\[(waiting[_ ]?user|blocked[_-]?Rost|pending|in[_ ]?progress)[^\]]*\]\s+([\w][\w.-]+)\s*[—:-]\s*(.+)$', _ql, _re.I | _re.M):
        _st, _slug, _rest = _m.group(1).lower().replace(' ', '_'), _m.group(2), _m.group(3).strip()
        _ctx = f'QUEUE.md {_slug}'
        if any((_ctx in (q.get('ctx') or '')) or (_slug.lower() in (q.get('ctx') or '').lower()) for q in _bt.get('qs') or []):
            continue
        # t4183: waiting_user = ждём Rost → red/attn (не «ждём других»); wait=True только если явно ждём чужой ответ
        _is_rost = 'waiting_user' in _st or 'blocked' in _st
        _is_wait = False  # waiting_user ≠ wait-others
        _bt.setdefault('qs', []).append(dict(q=_rest[:200], st='red' if (_is_rost or 'pending' in _st) else 'green', wait=_is_wait, ctx=_ctx))

# === Rost t4074: пункт QUEUE закрыт (done/x/closed) → вопрос «я нужен», ссылающийся на «QUEUE.md <slug>», сам уходит с даша (без тапа Rost).
_QST = {}
for _bn, _qf in _Q.items():
    try:
        for _l in open(_qf, encoding='utf-8'):
            _m = _re.match(r'^(?:- |## )\[([^\]]*)\]\s*([\w][\w.-]+)', _l)
            if _m: _QST.setdefault(_m.group(2).lower(), []).append(_m.group(1).strip().lower())
    except FileNotFoundError: pass
_QCLOSED = {k for k, v in _QST.items() if v and all(_re.match(r'^(done|x\b|x$|closed|закрыт)', x) for x in v)}
_ndrop = 0
for b in data['bots']:
    _keep = []
    for q in b.get('qs') or []:
        _m = _re.search(r'QUEUE\.md ([\w][\w.-]+)', q.get('ctx') or '')
        if _m and _m.group(1).lower() in _QCLOSED: _ndrop += 1; continue
        _keep.append(q)
    b['qs'] = _keep
print('queue-closed dropped:', _ndrop)
# === Rost 26.10 20:15: у «Рутины · ок» — последний запуск мелко в скобках (runs.jsonl, «Last runs» в инвентаре, колонка Last run)
_LAST = {}
try:
    for ln in open(_INV + 'runs.jsonl', encoding='utf-8'):
        try: j = json.loads(ln)
        except Exception: continue
        ts = (j.get('ts_bogota') or '')[:16].replace('T', ' ')
        for k in (j.get('routine_folder'), j.get('routine_name')):
            if k and ts > _LAST.get(k, ''): _LAST[k] = ts
except FileNotFoundError: pass
for _f in glob.glob(_INV + '*.md') if 'glob' in dir() else __import__('glob').glob(_INV + '*.md'):
    try: _T = open(_f, encoding='utf-8').read()
    except Exception: continue
    for m in _re.finditer(r'^- `([\w-]+)`: (?:\D{0,30})?(\d{4}-\d\d-\d\d \d\d:\d\d)', _T, _re.M):
        if m.group(2) > _LAST.get(m.group(1), ''): _LAST[m.group(1)] = m.group(2)
for b in data['bots']:
    for r in b.get('routines') or []:
        r['last'] = max(r.get('last') or '', _LAST.get(r.get('folder') or '-', ''), _LAST.get(r['name'], ''))
# === Rost t3986u/t3987u: упавшая рутина, которую бот УЖЕ чинит → не «🔴 Рутина упала / Требует внимания», а «📋 Задачи в очереди» (автоматически).
# «Чинит» = в открытой (не done) задаче QUEUE.md бота упомянуты folder-id рутины (automation-…) или её имя; или в заметке инвентаря fixing/чиню/чинит/in progress.
def _rt_norm(x): return ' '.join(_re.sub(r'[^\w ]', ' ', (x or '').lower()).split())
for b in data['bots']:
    Q = b.get('queue') or []
    for r in b.get('routines') or []:
        if r.get('st') != 'fail': continue
        nm, fo = _rt_norm(r['name']), (r.get('folder') or '').lower()
        hit = next((q for q in Q if (fo and fo in q['t'].lower()) or (nm and nm in _rt_norm(q['t']))), None)
        if hit or _re.search(r'fixing|чиню|чинит|in progress', (r.get('note') or ''), _re.I):
            r['st'] = 'fixing'
            if hit: hit['st'] = hit['st'] if 'чин' in hit['st'] else 'чинит бот'
            else: Q.append(dict(st='чинит бот', t=f"Рутина «{r['name']}» упала — бот уже чинит" + (f" ({r['note']})" if r.get('note') else '')))
    if b.get('queue') is not None or Q: b['queue'] = Q
# === Rost 26.10 ~19:55: «⏳ Ждём ответ» — отдельный свёрнутый список тех, от кого ждём ответ (люди/чаты, не Rost)
_WRE = _re.compile(r'жд[её]м\b|waiting reply|ждём ответ', _re.I)
_NOT_ROST = lambda t: not _re.search(r'жд[её]м,? когда|жд[её]м (OK|ОК|GO|решени\w*|ответ\w*)? ?(от )?Rost|от Rost', t)
for b in data['bots']:
    W = []
    for q in b['qs']:
        if q['st'] != 'red' and _WRE.search(q['q'] + ' ' + (q.get('ctx') or '')) and _NOT_ROST(q['q'] + ' ' + (q.get('ctx') or '')):
            q['wait'] = True
    keep = []
    for it in b.get('queue') or []:
        st = it['st'].lower()
        if 'waiting reply' in st or ((_WRE.search(it['t']) and 'waiting user' not in st and 'blocked' not in st) and _NOT_ROST(it['t'])):
            k = ' '.join(_re.sub(r'[^\w ]', ' ', it['t'].lower()).split()[:2])  # дубль с вопросом (Base Loft) — не плодим
            if not any(k and k in (q['q'] + ' ' + (q.get('ctx') or '')).lower() for q in b['qs'] if q.get('wait')):
                W.append(dict(t=it['t'], st=it['st']))
        else:
            keep.append(it)
    if b.get('queue') is not None: b['queue'] = keep
    b['waiting'] = W
for b in data['bots']:
    red = [q for q in b['qs'] if q['st'] == 'red' and not q.get('answered')]
    # Rost t4149–51u: CU for check НЕ даёт 🟡 «N новых»; 🟡 только свежие НЕ-красные отчёты-вопросы. need=rost задачи → 🔴 attention как вопросы
    newn = sum(1 for q in b['qs'] if q.get('new') and not q.get('answered') and q['st'] != 'red')
    b['new_count'] = newn
    rost_t = [t for t in b.get('tasks', []) if t.get('need', 'rost') == 'rost']
    b['status'] = 'nodata' if (b.get('nodata') and not b.get('routines') and not rost_t) else 'attention' if (red or rost_t) else 'ok'  # Rost t4136u: «всё ок» = от Rost ничего не нужно; QUEUE — отдельный бейдж, не статус  # t3949u
for b in data['bots']:
    b['link'] = A(b['id'] or 'd3a12cc9-cf8a-41e5-b34a-76d4ab9eb9fd')  # без id -> Секретарь (Rost 26.10: каждая строка кликабельна)
# Rost 26.10: мини-кнопка у каждого вопроса -> grokbot://app/v1/prompt?id=<бот>&text=<вопрос> (заполняет поле ввода, не отправляет; 1 строка ≤1000 симв.)
from urllib.parse import quote as _q
for b in data['bots']:
    for q in b['qs']:
        if not q.get('qid'): q['qid'] = _QID(b['name'], q['q'])  # t4183: QUEUE-appended qs
for b in data['bots']:
    for i, q in enumerate(b['qs']):
        qid = q['qid']
        t = f'[Из дашборда · {qid} · «{b["name"]}»] Обсуждаем: {q["q"]} | Контекст: {q.get("ctx") or "—"}'.replace('\n', ' ')[:900]
        while len(_q(t, safe='')) > 1000: t = t[:-8].rstrip() + '…'  # лимит 1000 симв. URL-encoded
        q['prompt'] = f'grokbot://app/v1/prompt?id={b["id"] or _SEC_ID}&text={_q(t, safe="")}'
data['cu_base'] = 'https://rosmater.github.io/cu/?t='
# Rost 26.10: у каждой строки — ответственный бот + deep link (клик -> чат бота, контекст в буфере)
OWN = {'Email': ('Помощник по всему', 'fef07752-2a22-4e1a-804b-7590fa230b30')}
SEC = ('Секретарь', 'd3a12cc9-cf8a-41e5-b34a-76d4ab9eb9fd')
for g in data['messengers']:
    for r in g['rows']:
        if r.get('owner'): continue  # Rost 26.10: строки с явным владельцем (Dating -> Дейтинг) не перетираем
        nm, i = OWN.get(r['channel'], SEC); r['owner'] = nm; r['owner_link'] = A(i)
# ClickUp: for check на Rost (снимок ma_clickup.json), каждая — ссылка на задачу
_cu = json.load(open(os.path.join(os.path.dirname(__file__), 'ma_clickup.json')))
# Rost t4212: обычные строки Мессенджеров — автор = отправитель; бот (имя «БОТ…» / TG-юзернейм …bot) → author_bot, уходит вниз сферы
for g in data['messengers']:
    for r in g['rows']:
        _snd = r.get('sender') or ''
        r['author_bot'] = bool(re.match(r'^\W*БОТ\b', _snd, re.I) or (re.search(r'bot$', _snd, re.I) and 'Telegram' in (r.get('channel') or '')))
data['clickup'] = dict(fetched=_cu['fetched'], owner=SEC[0], owner_link=A(SEC[1]), tasks=[dict(t, need=_ATTN.get(t['id'], 'rost'), bot=_CU_OWN.get(t['id'], '')) for t in _cu['tasks']])  # t4143/t4197: need rost|ok из bot_attn.jsonl
# Rost t4195–96: CU-инбокс в Мессенджерах читает d.cu_inbox (ma_cu_inbox.json). Без этого поля maCUMsgRows() пустой → задачи «пропали».
try:
    _cui = json.load(open(os.path.join(os.path.dirname(__file__), 'ma_cu_inbox.json'), encoding='utf-8'))
    data['cu_inbox'] = {k: _cui[k] for k in ('fetched','since','src','tier','kinds','counts','items','threads') if k in _cui}
    print('cu_inbox threads', len((_cui.get('threads') or [])), 'items', len((_cui.get('items') or [])))
    # Rost t4212: автор строки (кто написал/тегнул). Общие правила, без хардкодов задач:
    #   живой человек (author_bot=False из cu_inbox_build) → его имя; аккаунт Rost (пишут боты) / имя задачи «БОТ…» / запись в bot_attn.jsonl → «БОТ».
    #   Автор неизвестен и признаков бота нет → человек по имени отправителя (who), имён не выдумываем.
    _CU_SPACE = {'901421054196': 'Defense Systems'}  # list_id → space (Defense Systems / list «Tasks», space 90148618420)
    _CU_LID = {}
    for _rf in ('/workspace/notify-watchers/clickup-pulse/inbox-raw/wide/tasks-updated.json', '/workspace/notify-watchers/clickup-pulse/inbox-raw/tasks-' + (_cui.get('fetched') or '')[:10] + '.json'):
        try:
            for _rt in json.load(open(_rf, encoding='utf-8')).get('tasks') or []:
                _CU_LID.setdefault(str(_rt.get('id')), str((_rt.get('list') or {}).get('id', '')))
        except Exception:
            pass
    _BOTRE = re.compile(r'^\W*(\(.*?\)\s*)?БОТ\b', re.I)
    _CU_UPD = {str(t['id']): t.get('updated') or '' for t in _cu_tasks['tasks']}
    for _th in data['cu_inbox'].get('threads') or []:
        _tid = str(_th.get('task_id') or '')
        # Rost t4322: голый лист «Tasks» без сферы → ❓ Прочее. Сфера по list_id/space (Defense Systems → Оборонка)
        if not _th.get('list_id'):
            _th['list_id'] = _CU_LID.get(_tid, '')
        if not _th.get('space') and _CU_SPACE.get(_th.get('list_id')):
            _th['space'] = _CU_SPACE[_th['list_id']]
        # Rost t4312–15: need из bot_attn.jsonl (те же правила, что for check: rev==updated → последняя; иначе последняя не-dash; нет лога → rost)
        _th['rev'] = _CU_UPD.get(_tid) or _th.get('at') or ''
        _th['need'] = _ATTN.get(_tid) or _attn_need(_tid, _th['rev']) or 'rost'
        if _th.get('author_bot') is False and _th.get('author'): continue
        _isb = _th.get('author_bot') is True or (_th.get('who') or '') == 'Rost' or bool(_BOTRE.search(_th.get('task') or '')) or _tid in _ATTN_L
        if _isb:
            _th['author'], _th['author_bot'] = 'БОТ', True
            _bn = _ATTN_BOT.get(_tid) or _CU_OWN.get(_tid) or ''
            if _bn: _th['author_botname'] = _bn
        else:
            _th['author'], _th['author_bot'] = (_th.get('who') or ''), False
    print('cu_inbox need (bot)', {k: sum(1 for t in data['cu_inbox'].get('threads') or [] if t.get('author_bot') and t.get('need') == k) for k in ('rost', 'ok')})
    print('cu_inbox authors', {k: sum(1 for t in data['cu_inbox'].get('threads') or [] if bool(t.get('author_bot')) == k) for k in (True, False)})
except Exception as _e:
    data['cu_inbox'] = dict(fetched='', items=[], threads=[], counts={})
    print('cu_inbox skip', _e)

# Непрочитанные · нерассортированные: висящие без сферы жизни (Прочее / Viber / Telegram / непрочитанные чаты вочеров)
LIFE = set(_ORD)
uns = []
for g in data['messengers']:
    for r in g['rows']:
        if g['sphere'] in LIFE: continue
        for u in (r.get('unread_list') or []):
            uns.append(dict(key=f"{r['channel']}|{u['chat']}", channel=r['channel'], title=u['chat'], kind=u.get('kind'), unread=u['n'], owner=r['owner'], owner_link=r['owner_link']))
        if not r.get('unread_list') and ((r.get('unread_chat') or 0) > 0 or (r.get('pending') and not r.get('planned'))):
            uns.append(dict(key=f"{r['channel']}|{r['chat']}", channel=r['channel'], title=r['sender'], kind=None, unread=r.get('unread_chat'), owner=r['owner'], owner_link=r['owner_link']))
for t, u in UNK.items():
    uns.append(dict(key=f"{u['channel']}|{t}", channel=u['channel'], title=t, kind='нет в contacts', unread=u['unread'], last=u['last'], owner=SEC[0], owner_link=A(SEC[1])))
# Rost 26.10 21:14: агрегат «Telegram (все чаты)» по title окна убран — хрень; нужен разбор по чатам
try:
    __import__('sys').path.insert(0, os.path.dirname(os.path.abspath(__file__))); from census_unsorted import merge as _cmerge; uns = _cmerge(uns, skip=_TG_PLACED)  # Rost 27.10 census needs_sort
except Exception as _e: print('census merge skip', _e)
data['unsorted'] = uns
# === Rost 27.10 t3887u–t3889u: 🔕 игнор чатов. src/ignored_chats.json = {mention_handles:{Telegram:[...],WhatsApp:[...]}, chats:[{id,channel,title,kind,ignored_at}]}
# mention_at = последнее время из secretary-log, где в превью есть @-тег Rost (только группы/неизвестный тип; личка — никогда). Скрытие делает браузер.
try:
    _IGF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ignored_chats.json')
    _IG = json.load(open(_IGF, encoding='utf-8')) if os.path.exists(_IGF) else {}
    _H = _IG.get('mention_handles') or {}
    _WCH = {'whatsapp-esp': 'WhatsApp ESP', 'whatsapp-ukr': 'WhatsApp UKR', 'wa-esp': 'WhatsApp ESP', 'wa-ukr': 'WhatsApp UKR', 'tg': 'Telegram', 'telegram': 'Telegram', 'viber': 'Viber'}
    _MENT = {}
    try: _SL = open('/workspace/notify-watchers/secretary-log.md', encoding='utf-8').read().splitlines()
    except Exception: _SL = []
    for _ln in _SL:
        _m = _re.match(r'^- (\d{4}-\d\d-\d\d \d\d:\d\d) Bogot\S* \| ([^|]+)\| ([^|]+)\| (.*)$', _ln)
        if not _m: continue
        _w = _m.group(2).strip().lower(); _ch = next((v for k, v in _WCH.items() if _w.startswith(k)), None)
        if not _ch: continue
        _hs = [h for h in (_H.get(_ch) or _H.get('WhatsApp' if 'WhatsApp' in _ch else _ch) or []) if h]
        _txt = _m.group(4)
        if not any(_re.search(r'(?<!\w)' + _re.escape(h if h.startswith('@') else '@' + h) + r'(?!\w)', _txt, _re.I) for h in _hs): continue
        _t = _re.sub(r'\s*\([^)]*\)\s*$', '', _m.group(3).strip()).lower()
        _k = (_ch + '|' + _t)
        if _m.group(1) > _MENT.get(_k, ''): _MENT[_k] = _m.group(1)
    _out = []
    for c in _IG.get('chats') or []:
        c = dict(c); _ck = (c.get('channel', '') + '|' + _re.sub(r'\s*\([^)]*\)\s*$', '', c.get('title', ''))).lower()
        if c.get('kind') != 'dm' and not c.get('perm'):  # perm=True — игнор навсегда (Rost 27.10 t3891u)
            _ma = max([v for k, v in _MENT.items() if k == _ck or k.startswith(_ck) or _ck.startswith(k)] or [''])
            if _ma and _ma > (c.get('ignored_at') or ''): c['mention_at'] = _ma
        _out.append(c)
    data['ignored'] = _out; data['mention_handles'] = _H
except Exception as _e:
    print('ignored skip', _e); data['ignored'] = []
# Rost 27.10 t3901u: последняя сверка непрочитанных (заполняет утренняя проверка → src/messengers_reconcile.json); t4035: на даше коротко в 📊 Мониторе, см. docs/ROUTINES.md
try:
    data['reconcile'] = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'messengers_reconcile.json')))
except Exception as _e:
    data['reconcile'] = None
# Покрытие: откуда снимок и чего НЕ видно (Rost 26.10: «все ли непрочитанные тут?» — нет)
import glob
def _al(d):
    try: return sum(1 for l in open(f'/workspace/notify-watchers/{d}/allowlist.txt', encoding='utf-8') if l.strip() and not l.strip().startswith('#'))
    except FileNotFoundError: return 0
data['coverage'] = [
 dict(channel='WhatsApp ESP', src='secretary-log (toast-вочер AX42 → вебхук), с 21.10', live=False, gap=f'видны только чаты из allowlist вочера ({_al("wa-esp-secretary")}) и только когда пришёл toast; остальные непрочитанные WA ESP не видны без экрана AX42'),
 dict(channel='WhatsApp UKR', src='secretary-log (toast-вочер AX42 → вебхук), с 21.10', live=False, gap=f'видны только чаты из allowlist ({_al("wa-ukr-secretary")}); счётчик unread = последний из toast, может устареть'),
 dict(channel='Telegram', src='tg-secretary watcher.log (только статус)', live=False, gap='непрочитанные TG по чатам пока НЕ разобраны (нужна сверка глазами списка чатов TG Desktop); заголовок окна не используем — там сумма сообщений вкл. каналы, не диалоги; '+'вочер ловит только D-Bus-уведомления (muted чаты их не шлют; с 21.10 не было ни одного) → поимённо TG-чаты не видны'),
 dict(channel='Viber', src='скрин Viber 26.10 18:36 + вочер с 19:04', live=False, gap='AUMID не найден — новые toast могут не ловиться'),
 dict(channel='Email', src='только важные (ma_email_important.json)', live=False, gap='не все письма — по правилу Rost'),
]
# Rost 26.10: монитор вверху Мессенджеров — вочер жив? + последний сигнал (мелким). Только метаданные/время.
def _watchers():
    import re as _re, subprocess as _sp, datetime as _dt
    now = _dt.datetime.now()
    last = {}
    try:
        for ln in open(LOG, encoding='utf-8', errors='ignore'):
            m = _re.match(r'^- (\d{4}-\d\d-\d\d \d\d:\d\d) COT \| ([A-Z]+)', ln)
            if m: last[m.group(2)] = max(last.get(m.group(2), ''), m.group(1))
            m2 = _re.match(r'^- (\d{4}-\d\d-\d\d \d\d:\d\d)(?: Bogotá)? \| whatsapp-(esp|ukr)-secretary', ln)  # night hygiene 27.10: второй формат лога
            if m2: t2 = m2.group(2).upper(); last[t2] = max(last.get(t2, ''), m2.group(1))
    except FileNotFoundError: pass
    def age(ts, ok_h=24):
        try: return 'ok' if (now - _dt.datetime.strptime(ts[:16], '%Y-%m-%d %H:%M')).total_seconds() < ok_h*3600 else 'warn'
        except Exception: return 'warn'
    W = {}
    for ch, tag in (('WhatsApp UKR', 'UKR'), ('WhatsApp ESP', 'ESP')):
        ts = last.get(tag, '')
        W[ch] = dict(st=age(ts) if ts else 'warn', alive='toast-вочер AX42 (с бокса жив/нет не видно)', ping=ts, ping_lbl='последний сигнал')
    tl = '/workspace/notify-watchers/tg-secretary/state/watcher.log'; tping = ''
    try:
        for ln in open(tl, encoding='utf-8', errors='ignore'):
            if ln[:4].isdigit(): tping = ln[:16].replace('T', ' ')
    except FileNotFoundError: pass
    _st, _txt, _ln = _tg_status()
    W['Telegram'] = dict(st=_st, alive=('процесс жив' if _st != 'red' else 'не запущен') + (' · уведомлений нет с ' + _ln if _st == 'warn' and _ln else ''), ping=tping, ping_lbl='последняя запись лога', unread=TG_UNREAD, unread_at=TG_UNREAD_AT)
    # t4184: UIA heartbeat → not «?» when poller alive (dry_run ok)
    _vhb = None
    for _vp in ('/workspace/ax42-share/wa-ukr-12promax-p/viber-heartbeat.json',
                '/workspace/ax42-share/wa-ukr-12promax-p/viber-notify-secretary/viber-heartbeat.json',
                '/workspace/notify-watchers/health/viber-status.json'):
        try:
            import time as _time
            _raw = open(_vp, encoding='utf-8-sig').read().strip()
            if not _raw: raise ValueError('empty hb')
            _vhb = json.loads(_raw)
            _age = _time.time() - _time.mktime(_time.strptime(_vhb.get('ts','')[:19].replace('T',' '), '%Y-%m-%d %H:%M:%S')) if _vhb.get('ts') else 99999
            # ISO with offset: prefer fromisoformat
            try:
                from datetime import datetime as _dtc  # t4197: не затирать _dt (модуль) → иначе age() падал → ClickUp вечно 🟡
                _ts = _vhb.get('ts') or ''
                _age = (_dtc.now().astimezone() - _dtc.fromisoformat(_ts.replace('Z','+00:00'))).total_seconds()
            except Exception:
                pass
            if _age < 7200:  # 2h
                _mode = 'dry' if _vhb.get('dry_run', True) else 'live'
                W['Viber'] = dict(st='ok', alive=f"UIA поллер ✓ {_mode} · unread={_vhb.get('unread','?')} · src={_vhb.get('src','')}", ping=_vhb.get('ts','')[:16], ping_lbl='heartbeat')
                break
        except Exception:
            _vhb = None
    else:
        W['Viber'] = dict(st='warn', alive='запущен 26.10 19:04, AUMID не найден — toast могут не ловиться; ждём UIA heartbeat', ping=last.get('VIBER', ''), ping_lbl='последний сигнал')
    try: cp = json.load(open('/workspace/notify-watchers/clickup-pulse/state.json')).get('last_check', '')[:16].replace('T', ' ')
    except Exception: cp = ''
    cs = (data.get('clickup') or {}).get('fetched', '')
    W['ClickUp'] = dict(st=age(cs or cp), alive='снимок for check (MCP) + CU-пульс', ping=(cs or cp).replace(' Bogotá', ''), ping_lbl='последний снимок')
    W['Email'] = dict(st='ok', alive='только важные, вручную/ботом Почты', ping='', ping_lbl='')
    return W
data['watchers'] = _watchers()
data['spheres'] = ['Личное','Дейтинг','Недвижимость','Табакевич','ОФ','Пептиды','Оборонка','Коучинг','Игнор']  # Rost 26.10 20:19: = вкладки дашборда
# === Rost t3961u: сферы с даша по строкам мессенджеров (src/msg_sphere_overrides.json, пишет sync_dash_taps): key «канал|чат» -> сфера | «__unsort» (✕ → на сортировку) | «Игнор»
try:
    _MOF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'msg_sphere_overrides.json')
    # Rost t3968u: старые названия сфер из localStorage прежних версий даша → текущие (Быт → Личное, Dating → Дейтинг)
    _SALI = {'Личное · Dating': 'Дейтинг', 'Dating': 'Дейтинг', 'Dating / личное': 'Дейтинг', 'Быт': 'Личное', 'Быт / еда': 'Личное', 'Юр. / налоги': 'Личное', 'Финансы / банки': 'Личное', 'Прочее': 'Личное', 'Tabakevich': 'Табакевич', 'OF': 'ОФ'}
    _MO = {k.lower(): dict(v, sphere=_SALI.get(v.get('sphere'), v.get('sphere'))) for k, v in (json.load(open(_MOF, encoding='utf-8')).get('chats', {}) if os.path.exists(_MOF) else {}).items()}
    if _MO:
        _ukeys = {(u.get('key') or '').lower() for u in data['unsorted']}; _moved = []
        for g in data['messengers']:
            keep = []
            for r in g['rows']:
                k = f"{r.get('channel')}|{r.get('chat')}".lower(); o = _MO.get(k)
                if not o or r.get('cu_tasks') or r.get('unread_list') or o.get('sphere') == g['sphere']: keep.append(r); continue
                sp = o.get('sphere')
                if sp == '__unsort':
                    if k not in _ukeys:
                        data['unsorted'].append(dict(key=f"{r['channel']}|{r['chat']}", channel=r['channel'], title=r['chat'], kind='↩ с даша: на сортировку · было ' + g['sphere'], unread=r.get('unread_chat'), last=r.get('last', ''), owner=r.get('owner'), owner_link=r.get('owner_link'), is_group=r.get('is_group')))
                        _ukeys.add(k)
                elif sp and sp != 'Игнор': _moved.append((sp, dict(r, src_sphere=g['sphere'])))
            g['rows'] = keep
        # выбранная сфера для пункта «на сортировку» -> строка в сфере (чтобы не терялось, даже если contacts не сматчился)
        _rest = []
        for u in data['unsorted']:
            o = _MO.get((u.get('key') or '').lower()); sp = o and o.get('sphere')
            if sp and sp not in ('__unsort', 'Игнор'):
                _moved.append((sp, dict(sender=u.get('title'), chat=u.get('title'), channel=u.get('channel'), unread_chat=u.get('unread'), last=u.get('last', ''), owner=u.get('owner'), owner_link=u.get('owner_link'), src='dash-tap', sorted=True)))
            else: _rest.append(u)
        data['unsorted'] = _rest
        for sp, r in _moved:
            g = next((x for x in data['messengers'] if x['sphere'] == sp), None)
            if g is None: g = dict(sphere=sp, rows=[]); data['messengers'].append(g)
            if not any(f"{x.get('channel')}|{x.get('chat')}".lower() == f"{r.get('channel')}|{r.get('chat')}".lower() for x in g['rows']): g['rows'].append(r)
except Exception as _e: print('msg overrides skip', _e)
# === Rost t3962u: групповые чаты (не личка) -> is_group; даш пишет «ЧАТ: <название>». Источники: chats.csv purpose/key_people, ignored kind, sender≠chat, ключевые слова.
try:
    import re as _re
    _GRX = _re.compile(r'(групп|group|команд|team|канал|channel|model chat|\$\$\$|comunidad|юристы\+|рабочая|\w\+\w+\+)', _re.I)
    _DMX = _re.compile(r'^(dm\b|1:1|личный|census 27\.10: диалог)', _re.I)
    _TRX = _re.compile(r'(chat\b|чат|групп|group|\$\$\$|team|разработка|\bdev\b|\bseo\b|comunidad|аукцион|oftv|colombia|колумбия|•|content|контент|tabakevich|hooka|поддержка|•)', _re.I)
    _CG = {}
    for _r in csv.DictReader(open('/home/box/contacts/chats.csv', encoding='utf-8')):
        _t = _r['title'].split(';')[0].strip().lower(); _pu = (_r.get('purpose') or '')
        if _DMX.search(_r.get('purpose') or ''): _CG[_t] = False
        elif _GRX.search(_pu) or ';' in (_r.get('key_people') or '') or _TRX.search(_t): _CG[_t] = True
    _IGK = {(c.get('title') or '').lower(): c.get('kind') for c in (_IG.get('chats') or [])} if isinstance(globals().get('_IG'), dict) else {}
    def _isg(chat, sender=None, kind=None):
        t = (chat or '').strip().lower()
        if t in _CG: return _CG[t]
        if _IGK.get(t) == 'group' or (kind and _re.search(r'груп|group|канал', kind, _re.I)): return True
        if _IGK.get(t) == 'dm': return False
        if len(_SND.get(t, ())) > 1: return True  # несколько отправителей в одном чате = группа
        return bool(_TRX.search(t))
    _SND = {}
    for g in data['messengers']:
        for r in g['rows']: _SND.setdefault((r.get('chat') or '').strip().lower(), set()).add(r.get('sender'))
    for g in data['messengers']:
        for r in g['rows']:
            if 'is_group' not in r or r['is_group'] is None: r['is_group'] = _isg(r.get('chat'), r.get('sender'))
    for u in data['unsorted']:
        if u.get('is_group') is None: u['is_group'] = _isg(u.get('title'), None, u.get('kind'))
except Exception as _e: print('is_group skip', _e)
# Rost t3968u: «Быт»/«Прочее»/старые группы не показываем отдельной сферой — строки в Личное (Dating → Дейтинг); пустые группы вне списка сфер убрать
_GALI = {'Быт': 'Личное', 'Быт / еда': 'Личное', 'Прочее': 'Личное', 'Dating': 'Дейтинг', 'Tabakevich': 'Табакевич', 'OF': 'ОФ'}
for g in list(data['messengers']):
    to = _GALI.get(g['sphere'])
    if not to: continue
    tg = next((x for x in data['messengers'] if x['sphere'] == to), None)
    if tg is None: g['sphere'] = to; continue
    for r in g['rows']:
        if not any(f"{x.get('channel')}|{x.get('chat')}".lower() == f"{r.get('channel')}|{r.get('chat')}".lower() for x in tg['rows']): tg['rows'].append(dict(r, src_sphere=r.get('src_sphere') or g['sphere']))
    tg.setdefault('zero_contacts', []).extend(g.get('zero_contacts') or [])
    data['messengers'].remove(g)
# === Rost t3969–t3971u: ✓ ответил / ✕ можно не отвечать, привязка CU (иконка), теги Личного — src/msg_row_overrides.json
try:
    _ROF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'msg_row_overrides.json')
    _RO = json.load(open(_ROF, encoding='utf-8')) if os.path.exists(_ROF) else {}
    _lo = lambda D: {k.lower(): v for k, v in (D or {}).items()}
    _RS, _RC, _RT = _lo(_RO.get('state')), _lo(_RO.get('cu')), _lo(_RO.get('tags'))
    _nl = 0
    for g in data['messengers']:
        for r in g['rows']:
            if r.get('cu_tasks'): continue
            k = f"{r.get('channel')}|{r.get('chat')}".lower()
            if k in _RS and _RS[k].get('st'): r['rst'] = {'st': _RS[k]['st'], 'at': _RS[k].get('at')}
            c = _RC.get(k)
            if c and c.get('unlinked'): r['cu_unlinked'] = True
            elif c and c.get('id'): r['cu_link'] = [{'id': c['id'], 'name': c.get('name') or c['id'], 'src': c.get('src')}]; _nl += 1
            elif (r.get('binding') or {}).get('tasks'): r['cu_link'] = [{'id': t[0], 'name': t[1], 'src': 'contacts'} for t in r['binding']['tasks']]; _nl += 1
            if k in _RT and _RT[k].get('tags'): r['tags'] = _RT[k]['tags']
    print('row overrides: cu', _nl, 'state', len(_RS), 'tags', len(_RT))
except Exception as _e: print('row overrides skip', _e)
# Rost t4004u: «(N дн.)» — src/hang_since.json: «канал|чат» -> YYYY-MM-DD (Богота), с какого дня висит (непрочитано / наш ход / ждём).
# Первый раз увидели висящим -> min(дата последнего сообщения, известная hang_since) или сегодня; перестал висеть -> ключ удаляется. Даш считает дни сам от сегодняшней даты Боготы.
try:
    import datetime as _dt
    _HSF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hang_since.json')
    _HS = json.load(open(_HSF, encoding='utf-8')) if os.path.exists(_HSF) else {}
    _today = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=5)).strftime('%Y-%m-%d')
    _HN = {}
    def _hs(k, r, hanging):
        if not k or not hanging: return
        c = [x for x in (_HS.get(k), r.get('hang_since'), (r.get('last') or '')[:10]) if x and re.match(r'^\d{4}-\d\d-\d\d$', x)]
        d = min(c) if c else _today
        _HN[k] = d; r['hang_since'] = d
    for g in data['messengers']:
        for r in g['rows']:
            if r.get('cu_tasks') or r.get('planned'): continue
            _hs(f"{r.get('channel')}|{r.get('chat')}".lower(), r, (r.get('unread_chat') or 0) > 0 or bool(r.get('pending')) or any((u.get('n') or 0) > 0 for u in (r.get('unread_list') or [])))
    for u in data.get('unsorted') or []: _hs((u.get('key') or '').lower(), u, (u.get('unread') or 0) > 0)
    json.dump(_HN, open(_HSF, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    print('hang_since:', len(_HN))
except Exception as _e: print('hang_since skip', _e)
# Rost t4049u/t4050: «@» рядом с циферкой, если в групповом чате Rost тегнули (secretary-log, превью с @-тегом) после начала висения и есть непрочитанные.
try:
    _MH = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ignored_chats.json'), encoding='utf-8')).get('mention_handles') or {}
    _MDEF = ['rost', 'ros', 'rostyslav', 'ростислав', 'рост', 'yermakov']
    _MW = {'whatsapp-esp': 'WhatsApp ESP', 'whatsapp-ukr': 'WhatsApp UKR', 'wa-esp': 'WhatsApp ESP', 'wa-ukr': 'WhatsApp UKR', 'tg': 'Telegram', 'telegram': 'Telegram', 'viber': 'Viber'}
    _MM = {}
    try: _ML = open('/workspace/notify-watchers/secretary-log.md', encoding='utf-8').read().splitlines()
    except Exception: _ML = []
    for _ln in _ML:
        _m = re.match(r'^- (\d{4}-\d\d-\d\d \d\d:\d\d) Bogot\S* \| ([^|]+)\| ([^|]+)\| (.*)$', _ln)
        if not _m: continue
        _w = _m.group(2).strip().lower(); _ch = next((v for k, v in _MW.items() if _w.startswith(k)), None)
        if not _ch: continue
        _hs = [h.lstrip('@') for h in (_MH.get(_ch) or _MH.get('WhatsApp' if 'WhatsApp' in _ch else _ch) or [])] + _MDEF
        if not any(re.search(r'(?<!\w)@' + re.escape(h) + r'(?!\w)', _m.group(4), re.I) for h in _hs if h): continue
        _t = re.sub(r'\s*\([^)]*\)\s*$', '', _m.group(3).strip()).lower()
        _MM[_t] = max(_MM.get(_t, ''), _m.group(1))
    _nm = 0
    for g in data['messengers']:
        for r in g['rows']:
            if not r.get('is_group') or not r.get('unread_chat'): continue
            c = (r.get('chat') or '').lower(); ma = max([v for k, v in _MM.items() if k == c or k.startswith(c) or c.startswith(k)] or [''])
            if ma and ma[:10] >= (r.get('hang_since') or ma[:10]): r['mention_at'] = ma; _nm += 1
    print('mentions:', _nm, 'log hits', len(_MM))
except Exception as _e: print('mentions skip', _e)
json.dump(data, open(os.path.join(ROOT, 'data-test-ma.json'), 'w'), ensure_ascii=False, indent=1)
print('rows', sum(len(g['rows']) for g in data['messengers']), 'groups', [g['sphere'] for g in data['messengers']])
