"""TEST (Rost 26.10): data for test-messengers-assistants.html. Строки чатов = метаданные из secretary-log (время, канал, чат, отправитель, unread, тип).
Rost t4356u (28.10): ИСКЛЮЧЕНИЕ — `last_msgs` (≤3 последних пойманных тоста, ≤120 симв.) для hover-превью; только чаты из allowlist/log_only вочера,
только цитата «…» из тоста (не пояснения бота). Всё остальное — без тел. Вывод шифруется (data-test-ma.enc.json); plaintext не пушится."""
import re, json, os, csv, datetime as _dt
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
    # 29.10: заголовок чата до « (» приоритетнее — иначе пояснение в скобках (другой чат того же человека) перехватывает строку
    head = tl.split(' (')[0].strip()
    for n, d, sph in KNOWN:
        if head == n: return d, sph
    for n, d, sph in KNOWN:
        if n in tl: return d, sph
    return None, None
SENDERS = ['Анатолий','Ирина Шекель','Elena Tolstova','Albeiro']
chats = {}
UNK = {}
def _parse_log_head(ln):
    """Accept old 'YYYY-MM-DD HH:MM Bogotá | app' and ISO 'YYYY-MM-DDTHH:MM:SS±HH:MM | app' (since 30.10)."""
    m = re.match(r'- (2026-\d\d-\d\d)T(\d\d:\d\d):\d\d[+-]\d\d:\d\d\s*\|\s*([\w-]+)', ln)
    if m: return m.groups()
    m = re.match(r'- (2026-\d\d-\d\d) (\d\d:\d\d) (?:Bogotá|COT)?\s*\|?\s*([\w-]+)', ln)
    if m: return m.groups()
    return None
for ln in open(LOG, encoding='utf-8'):
    g = _parse_log_head(ln)
    if not g: continue
    day, tm, ch = g
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
    # Rost t4997–98: unread = последнее известное (N unread) из тоста, НЕ max за всю историю лога
    if un: c['unread'] = int(un[-1])
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
# Rost t4989: старый Dating INBOX 26.10 снят с хардкода — висяки не держатся forever; актуальные строки пушит бот Дейтинг / живой лог.
# (ранее: piggy_cami…Layla «наш ход/ждём её» — уже неактуально)
# Rost t4989: El Pulpo 02–03.11 оплачен — хардкод pending/unread снят (живой лог/census при необходимости).
# Rost t4004u: Base Loft — поиск лофта (CU 86bcma7tp) в Личном. Факты: knowledge/shared-personal/places/base-loft-rental-search.md + /workspace/base-loft/*-chat-log.md. Портерия = доставки, не аренда — не добавляем.
_PMH = ('Помощник по всему', 'fef07752-2a22-4e1a-804b-7590fa230b30')
for _s, _c, _p, _l, _h in [
    ('Víctor Márquez (Nutibara 1105)', 'Nutibara 1105', 'ждём Víctor: наше 26.10 15:41 про A1105 (✓✓, не прочитано на 18:46; дальше только автошаблон)', '2026-10-26 15:41', '2026-10-26'),
    ('Miguel Calipso (CALIPTO)', 'Miguel Calipso', 'ждём Calipso: дуплекс 10 эт. 2.6M — запрос 18.10 18:37, ответа нет', '2026-10-18 18:37', '2026-10-18'),
    ('Nini Loaiza (Alnago, A1105)', 'Alnago', 'ждём Nini: 04.11 10:17 ушёл PDF Libertador diligenciado (con huella) A1105/C4632 + вопрос ETA estudio; 2 серые тики', '2026-11-04 10:17', '2026-11-04'),
]:
    add('Личное', dict(sender=_s, chat=_c, channel='WhatsApp ESP', unread_chat=None, items=1, kinds={'аренда':1}, last=_l, binding=None, pending=_p, src='base-loft-rental-search.md', sorted=True, owner=_PMH[0], owner_link=f'grokbot://app/v1/agent?id={_PMH[1]}', hang_since=_h, is_group=False))
# Rost t4989: Travertino наличные + IKEA доставка — answered/closed; хардкод pending снят.
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
# t4368 (Rost 28.10): Viber — живой список непрочитанных (src/viber_live.json, пишет проверка по списку Viber AX42 / бейдж UIA-поллера).
# Census 27.10 по Viber — снимок; без этого новые непрочитанные Viber (напр. Стелла Киевстар 28.10) на даш не попадали, а старые висели.
_VL = None
try:
    _VLF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'viber_live.json')
    if os.path.exists(_VLF): _VL = json.load(open(_VLF, encoding='utf-8'))
except Exception as _e: print('viber_live skip', _e)
_VL_IGN = ('БЕЗПЕЧНИЙ РЕГІОН',)
if _VL:
    # Rost t4997: viber_live старше 2 суток не источник unread (ждём свежий снимок сверки)
    import datetime as _dtx
    _vt = (_VL.get('at') or '')[:10]
    _today = (_dtx.datetime.now(_dtx.timezone.utc) - _dtx.timedelta(hours=5)).strftime('%Y-%m-%d')
    try:
        _age = ( _dtx.datetime.strptime(_today,'%Y-%m-%d') - _dtx.datetime.strptime(_vt,'%Y-%m-%d') ).days if _vt else 99
    except Exception:
        _age = 99
    if _age > 2:
        print('viber_live STALE', _VL.get('at'), 'age', _age, 'd — unread not applied until refresh')
        _VL = None
if _VL:
    _vmap = {c['title'].lower(): c for c in _VL.get('chats') or [] if not any(x in c['title'].upper() for x in _VL_IGN)}
    _vsrc = 'Viber список ' + _VL.get('at', '')
    _vseen = set()
    for _sp, _rs in groups.items():
        for _r in _rs:
            if _r.get('channel') != 'Viber': continue
            _c = _vmap.get((_r.get('chat') or '').lower())
            if _c: _r['unread_chat'] = _c['unread']; _r['muted'] = bool(_c.get('muted')); _r['last'] = _c.get('last', ''); _r['src'] = _vsrc; _vseen.add(_c['title'].lower())
            elif (_r.get('unread_chat') or 0) > 0: _r['unread_chat'] = 0; _r['src'] = (_r.get('src') or '') + ' · ' + _vsrc + ': прочитано'
    # новые: сфера = та же, что у этого человека в другом канале (строка с тем же названием) → иначе в «на сортировку» (ниже)
    _byname = {}
    for _sp, _rs in groups.items():
        for _r in _rs: _byname.setdefault((_r.get('chat') or '').lower(), _sp)
    _VL_UNS = []
    for _k, _c in _vmap.items():
        if _k in _vseen or not _c.get('unread'): continue
        _sp = _byname.get(_k)
        if _sp and _sp in _ORD:
            groups[_sp].append(dict(sender=_c['title'], chat=_c['title'], channel='Viber', unread_chat=_c['unread'], muted=bool(_c.get('muted')), items=0, kinds={}, last=_c.get('last', ''), binding=None,
                                     src=_vsrc, src_sphere=_sp, owner='Секретарь', owner_link='grokbot://app/v1/agent?id=d3a12cc9-cf8a-41e5-b34a-76d4ab9eb9fd', key='Viber|' + _c['title'], hang_since=_VL.get('at', '')[:10]))
            _TG_PLACED.add('Viber|' + _c['title']); _vseen.add(_k)
        else: _VL_UNS.append(_c)
    print('viber_live:', len(_vmap), 'чатов, в сферы', len(_vseen), 'на сортировку', len(_VL_UNS))
    # t4997: standing-ignore (БЕЗПЕЧНИЙ) всё равно в сферу Игнор — иначе сумма даша ≠ live
    groups.setdefault('Игнор', [])
    for _c in (_VL.get('chats') or []):
        if not any(x in _c['title'].upper() for x in _VL_IGN): continue
        if not _c.get('unread'): continue
        if any((r.get('chat') or '').lower() == _c['title'].lower() for r in groups['Игнор']): continue
        groups['Игнор'].append(dict(sender=_c['title'], chat=_c['title'], channel='Viber', unread_chat=_c['unread'], muted=bool(_c.get('muted')), items=0, kinds={}, last=_c.get('last', ''), binding=None,
                                     src=_vsrc + ' · standing-ignore', src_sphere='Игнор', ignored=True, owner='Секретарь', owner_link='grokbot://app/v1/agent?id=d3a12cc9-cf8a-41e5-b34a-76d4ab9eb9fd', key='Viber|' + _c['title'], hang_since=_VL.get('at', '')[:10]))

# Rost t4997: живые Unread-списки WA (list-only сверка) → override secretary-log max/sticky
def _apply_wa_live(fname, channel, label):
    import datetime as _dtx
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    if not os.path.exists(fp):
        print(label + ': no file'); return
    try:
        L = json.load(open(fp, encoding='utf-8'))
    except Exception as e:
        print(label + ' skip', e); return
    at = (L.get('at') or L.get('at_bogota') or '')[:10]
    today = (_dtx.datetime.now(_dtx.timezone.utc) - _dtx.timedelta(hours=5)).strftime('%Y-%m-%d')
    try:
        age = (_dtx.datetime.strptime(today,'%Y-%m-%d') - _dtx.datetime.strptime(at,'%Y-%m-%d')).days if at else 99
    except Exception:
        age = 99
    if age > 1:
        print(label + ' STALE', L.get('at'), 'age', age, '— not applied'); return
    for _c in (L.get('chats') or []):
        if 'title' not in _c and _c.get('name'): _c['title'] = _c['name']  # live json may use name
    vmap = {c['title'].lower(): c for c in (L.get('chats') or [])}
    src = label + ' ' + (L.get('at') or L.get('at_bogota') or '')
    # t5019 fix: live список = истина. 1) точное совпадение; 2) fuzzy 1:1 (живой чат не берём дважды);
    # unread/muted ТОЛЬКО из live; строки канала не в live -> unread 0 и muted снимаем (старые флаги не тянем)
    seen = set(); applied = 0; cleared_mu = 0
    globals().setdefault('_WA_LIVE_MAP', {})[channel] = (vmap, src, seen)
    _chrows = [_r for _rs in groups.values() for _r in _rs if _r.get('channel') == channel]
    _match = {}
    for _r in _chrows:
        key = (_r.get('chat') or '').lower()
        if key in vmap and key not in seen: _match[id(_r)] = vmap[key]; seen.add(key)
    for _r in _chrows:
        if id(_r) in _match: continue
        key = (_r.get('chat') or '').lower()
        for tk, tv in vmap.items():
            if tk in seen: continue
            if key and min(len(key), len(tk)) >= 5 and max(len(key), len(tk)) >= 8 and (key in tk or tk in key):
                _match[id(_r)] = tv; seen.add(tk); break
    for _r in _chrows:
        c = _match.get(id(_r))
        if c:
            _r['unread_chat'] = int(c.get('unread') or 0)
            if c.get('last'): _r['last'] = c.get('last')
            _r['muted'] = bool(c.get('muted'))
            _r['src'] = src; _r['live_title'] = c['title']
            applied += 1
        else:
            if _r.get('muted'): _r['muted'] = False; cleared_mu += 1
            if (_r.get('unread_chat') or 0) > 0:
                _r['unread_chat'] = 0
                _r['src'] = (_r.get('src') or '') + ' · ' + src + ': нет в Unread'
                applied += 1
    # new chats from live not on dash yet → unsorted-ish via sphere byname
    byname = {}
    for _sp, _rs in groups.items():
        for _r in _rs: byname.setdefault((_r.get('chat') or '').lower(), _sp)
    added = 0
    for tk, c in vmap.items():
        if tk in seen or not c.get('unread'): continue
        sp = byname.get(tk)
        if sp and sp in _ORD:
            groups[sp].append(dict(sender=c['title'], chat=c['title'], channel=channel, unread_chat=int(c.get('unread') or 0), muted=bool(c.get('muted')), items=0, kinds={}, last=c.get('last',''), binding=None,
                                   src=src, src_sphere=sp, owner='Секретарь', owner_link='grokbot://app/v1/agent?id=d3a12cc9-cf8a-41e5-b34a-76d4ab9eb9fd', key=channel+'|'+c['title'], hang_since=(L.get('at') or '')[:10]))
            added += 1; seen.add(tk)
        else:
            # leave for unsorted: append via global later — stash
            globals().setdefault('_WA_LIVE_UNS', []).append((channel, c, src))
    print(label + ':', len(vmap), 'unread chats, matched', len(seen), 'applied', applied, 'added', added, 'stale muted cleared', cleared_mu)

_apply_wa_live('wa_ukr_live.json', 'WhatsApp UKR', 'WA UKR live')
_apply_wa_live('wa_esp_live.json', 'WhatsApp ESP', 'WA ESP live')
_apply_wa_live('tg_live.json', 'Telegram', 'TG live')  # t5045
# t4368 (Rost 28.10): Instagram Direct личного @rosscompass — раз в день (утренний пакет / ночная гигиена) → src/ig_direct_live.json (mailbox-map/ig-direct/ig_direct_peek.py).
_IGD = None
try:
    _IGDF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ig_direct_live.json')
    if os.path.exists(_IGDF): _IGD = json.load(open(_IGDF, encoding='utf-8'))
except Exception as _e: print('ig_direct skip', _e)
_IGD_UNS = []
if _IGD and _IGD.get('ok'):
    _byname2 = {}
    for _sp, _rs in groups.items():
        for _r in _rs: _byname2.setdefault((_r.get('chat') or '').lower(), _sp)
    _igmap = {c['title'].lower(): c for c in (_IGD.get('chats') or [])}
    _igsrc = 'IG Direct @' + (_IGD.get('account') or '') + ' ' + _IGD.get('at', '')
    _igseen = set()
    # Rost t4997: живой список — обновить/обнулить Instagram как Viber (не тащить stale carry)
    for _sp, _rs in list(groups.items()):
        for _r in _rs:
            if _r.get('channel') != 'Instagram': continue
            _c = _igmap.get((_r.get('chat') or '').lower())
            if _c and _c.get('unread'):
                _r['unread_chat'] = _c.get('n') or 1; _r['last'] = _c.get('age', ''); _r['src'] = _igsrc; _igseen.add(_c['title'].lower())
            else:
                if (_r.get('unread_chat') or 0) > 0:
                    _r['unread_chat'] = 0; _r['src'] = (_r.get('src') or '') + ' · ' + _igsrc + ': прочитано'
                _igseen.add((_r.get('chat') or '').lower())
    for _c in _IGD.get('chats') or []:
        if not _c.get('unread') or _c['title'].lower() in _igseen: continue
        _sp = _byname2.get(_c['title'].lower())
        if _sp and _sp in _ORD:
            groups[_sp].append(dict(sender=_c['title'], chat=_c['title'], channel='Instagram', unread_chat=_c.get('n') or 1, items=0, kinds={}, last=_c.get('age', ''), binding=None,
                                     src=_igsrc, src_sphere=_sp, owner='Секретарь', owner_link='grokbot://app/v1/agent?id=d3a12cc9-cf8a-41e5-b34a-76d4ab9eb9fd', key='Instagram|' + _c['title'], hang_since=_IGD.get('at', '')[:10]))
            _igseen.add(_c['title'].lower())
        else: _IGD_UNS.append(_c)
    print('ig_direct:', _IGD.get('unread_chats'), 'непроч., на сортировку', len(_IGD_UNS))
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
            # Rost t4989: Feabie/Tinder / dating INBOX — не тащим вечный «наш ход» из прошлой сборки; актуальные строки пушит Дейтинг
            if _c in ('Feabie', 'Tinder', 'Instagram') or 'dating INBOX' in (_r.get('src') or ''): continue  # IG только из ig_direct_live
            if (_r.get('pending') or '').startswith('наш ход') and 'dating' in (_r.get('src') or '').lower(): continue
            _r = dict(_r); _r['src'] = (_r.get('src') or '') + ' · перенесено из прошлой сборки (источник канала сейчас пуст)'
            groups.setdefault(_g['sphere'], []).append(_r); _have.add((_r.get('chat') or '').lower()); _cf += 1
    if _cf: print('carry-forward строк:', _cf)
except Exception as _e: print('carry-forward skip', _e)
for sp in _ORD:
    if sp in _ZC and sp not in groups: groups[sp] = []
groups = {k: groups[k] for k in sorted(groups, key=lambda k: _ORD.index(k) if k in _ORD else 99)}
# Rost 26.10 22:20: сфера Табакевич в Мессенджерах ОСТАЁТСЯ (откат 21:16 — «Кальяны» убрать только из названия вкладки)
data = dict(generated=(_dt.datetime.now(_dt.timezone(_dt.timedelta(hours=-5))).strftime('%Y-%m-%d %H:%M')+' Bogotá'), test=True, messengers=[dict(sphere=k, rows=v, zero_contacts=sorted(_ZC.get(k, []), key=lambda z: z['title'].lower())) for k, v in groups.items()])
# Боты/ассистенты: сводные открытые вопросы (кратко, без дампов чатов)
A = lambda id_: f'grokbot://app/v1/agent?id={id_}'
# Rost 26.10 (аудит 19:35 Bogotá): реальные открытые вопросы из последних сообщений ботов (ReadTranscript) + задачи CU for check по владельцу (OWNERSHIP.md).
# st: red = встало/нужен Rost сейчас; green = норм/ждём; new = свежий отчёт (🟡). status бота считается ниже.
data['bots'] = [
 dict(name='Секретарь', id='d3a12cc9-cf8a-41e5-b34a-76d4ab9eb9fd', qs=[
   dict(q='Alexa: время встречи 26.10 — проверить, актуально ли (нет в списке Дейтинга 21:08)', st='red', ctx='Alexa Herera WA ESP 17:34 спросила время на пн 26.10; черновик «¿Te queda bien a las [HORA]?» ждёт время от Rost'),
   dict(q='Анатолий/Шекель: чей контактный номер в доставке шкафов? → Шекель (Ирина Шекель)', st='green', answered=True, ctx='Rost t3931u 27.10: «Шекель»'),
   dict(q='Доставка IKEA 29.10, окно 15:00–21:00 — кто принимает? → Анатолий', st='green', answered=True, ctx='Rost t4410: заберёт Анатолий'),
   dict(q='El Pulpo: оплатить Bre-B после суммы от Albeiro', st='green', answered=True, ctx='02–03.11 оплачено + чек; t4989 clear'),
   dict(q='Travertino: наличные на следующей неделе — подтвердить сумму/день → CU 86bbc7v9v due вт 3.11', st='green', answered=True, ctx='Rost t4412: задача передача денег на вторник'),
   dict(q='BTC резерв: вернуть 0.02318012 BTC — CU 86bcnmdvt due вт 3.11', st='green', answered=True, ctx='Rost t4416: задача обновлена'),
   dict(q='Viber-вочер: AUMID не найден — toast могут не ловиться (дописать вручную)', st='red', new=True, ctx='AX42 wa-ukr-12promax-p, вочер с 19:04'),
   dict(q='Telegram-вочер: native=1 + D-Bus ok (t4417) → QUEUE watcher-fix-tg-native-20261028', st='green', answered=True, ctx='Rost t4420 Clear-TZ self-queue; desktopNotify=1 native=1'),
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
# Rost t4103u: без «Notion» в тексте рядом с супер мозгом.
# t4425: Tabakevich GDrive 9/10 ок, №4 ФИ Шкьопу Юля дропнут — seed снят (было red QUEUE.md notion-instructions).
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
    _BA = {'Оборонные': 'Оборонка', 'Оборонные системы': 'Оборонка', 'Секретарь / Кликап / Мессенджеры': 'Секретарь', 'Кликап / Мессенджеры': 'Секретарь', 'COMMS': 'Секретарь'}  # Rost t4398 + COMMS inventory alias
    z['bot'] = _BA.get(z['bot'], z['bot']); z['bot'] = 'Секретарь' if (z['bot'] or '').startswith('Секретарь') else z['bot']  # Rost t3948u+t4398
    b = next((x for x in data['bots'] if x['name'] == z['bot']), None)
    if b is None: b = dict(name=z['bot'], id=_SEC_ID, qs=[]); data['bots'].append(b)
    b['qs'].append(dict(q=z['q'], st=z.get('st', 'red'), ctx=(z.get('ctx') or '') + f' · база вопросов {z.get("at","")}', new=True, _qid=z['qid']))  # t4183: default red
_RES = set(_OQ.get('resolved', {})) - set(_OQ.get('reopened', {}))
for b in data['bots']:
    for q in b['qs']: q['qid'] = q.pop('_qid', None) or _QID(b['name'], q['q'])
    b['qs'] = [q for q in b['qs'] if q['qid'] not in _RES]
# Rost t4398: title профиля «Секретарь / …» ≠ карточка; слить alias-имя в канон (не по id — coach-боты шарят id Секретаря)
_BA2 = {'Секретарь / Кликап / Мессенджеры': 'Секретарь', 'Кликап / Мессенджеры': 'Секретарь', 'Оборонные': 'Оборонка', 'Оборонные системы': 'Оборонка', 'COMMS': 'Секретарь'}
for _long, _short in list(_BA2.items()):
    _src = next((x for x in data['bots'] if x.get('name') == _long), None)
    _dst = next((x for x in data['bots'] if x.get('name') == _short), None)
    if _src and _dst:
        for _k in ('qs', 'tasks', 'reports', 'queue', 'waiting', 'routines'):
            if _src.get(_k): _dst.setdefault(_k, []).extend(_src[_k])
        data['bots'] = [x for x in data['bots'] if x is not _src]
    elif _src and not _dst:
        _src['name'] = _short
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
        # pending/in_progress уже в «Задачи в очереди» — в qs (attn) не дублируем (Rost 28.10 Payoneer)
        if _st.startswith('pending') or _st.startswith('in_progress') or _st.startswith('inprogress'):
            continue
        _ctx = f'QUEUE.md {_slug}'
        if any((_ctx in (q.get('ctx') or '')) or (_slug.lower() in (q.get('ctx') or '').lower()) for q in _bt.get('qs') or []):
            continue
        # t4183: waiting_user / blocked-Rost → red/attn; чужой wait — только если явно в тексте
        _is_rost = 'waiting_user' in _st or 'blocked' in _st
        _is_wait = False
        _bt.setdefault('qs', []).append(dict(q=_rest[:200], st='red' if _is_rost else 'green', wait=_is_wait, ctx=_ctx))

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
# t4368: Viber «на сортировку» — счётчик из живого списка (census 27.10 мог устареть)
def _fuzzy_live(title, vmap):
    k = (title or '').lower()
    if k in vmap: return vmap[k]
    # truncated ellipsis titles (… / ...)
    k2 = k.rstrip('.…').rstrip()
    for tk, tv in vmap.items():
        t2 = tk.rstrip('.…').rstrip()
        if k2 and t2 and (k2.startswith(t2[:12]) or t2.startswith(k2[:12]) or k2 in t2 or t2 in k2):
            return tv
    return None
if _VL:
    _used_v = set()
    for _u in uns:
        if _u.get('channel') != 'Viber': continue
        _c = _fuzzy_live(_u.get('title'), _vmap)
        _u['unread'] = _c['unread'] if _c else 0
        if _c:
            _u['muted'] = bool(_c.get('muted')); _u['last'] = _c.get('last', ''); _u['src'] = 'Viber список ' + (_VL.get('at') or '')
            _used_v.add(_c['title'].lower())
    for _c in (_VL.get('chats') or []):
        if any(x in _c['title'].upper() for x in _VL_IGN): continue
        if not _c.get('unread'): continue
        if _c['title'].lower() in _used_v: continue
        if _fuzzy_live(_c['title'], { (u.get('title') or '').lower(): u for u in uns if u.get('channel')=='Viber' }):
            continue
        uns.append(dict(key='Viber|' + _c['title'], channel='Viber', title=_c['title'], kind='Viber список · нет сферы' + (' · 🔇' if _c.get('muted') else ''), unread=_c['unread'], muted=bool(_c.get('muted')), last=_c.get('last', ''), owner=SEC[0], owner_link=A(SEC[1])))
# Rost t4997: WA live chats not yet on dash → unsorted (list-only truth)
for _ch, _c, _src in list(globals().get('_WA_LIVE_UNS') or []):
    if not _c.get('unread'): continue
    _key = f"{_ch}|{_c['title']}"
    if any((u.get('key') or '').lower() == _key.lower() for u in uns): continue
    uns.append(dict(key=_key, channel=_ch, title=_c['title'], kind=_src + ' · нет сферы' + (' · 🔇' if _c.get('muted') else ''), unread=int(_c.get('unread') or 0), muted=bool(_c.get('muted')), last=_c.get('last', ''), owner=SEC[0], owner_link=A(SEC[1])))
# t5019 fix: WA «на сортировку» — unread/muted только из live (census/secretary-log не тянут старые числа и флаги)
for _ch, (_wm, _wsrc, _seen0) in (globals().get('_WA_LIVE_MAP') or {}).items():
    _placed = {(r.get('live_title') or r.get('chat') or '').lower() for g in data['messengers'] if g['sphere'] in LIFE for r in g['rows'] if r.get('channel') == _ch and r.get('src') == _wsrc}
    _wu = {}
    for _u in uns:
        if _u.get('channel') != _ch: continue
        _t = (_u.get('title') or '').lower()
        _c = _wm.get(_t) if _t not in _placed else None
        if _c and _t in _wu: _c = None  # дубль -> 0
        _u['unread'] = int(_c.get('unread') or 0) if _c else 0
        _u['muted'] = bool(_c.get('muted')) if _c else False
        if _c: _u['src'] = _wsrc; _wu[_t] = 1
    _n = sum(1 for _u in uns if _u.get('channel') == _ch and _u.get('unread'))
    print('t5019 WA uns', _ch, 'с unread', _n)
# t4368: IG Direct непрочитанные без сферы → «на сортировку»
for _c in _IGD_UNS:
    if any(u.get('key') == 'Instagram|' + _c['title'] for u in uns): continue
    uns.append(dict(key='Instagram|' + _c['title'], channel='Instagram', title=_c['title'], kind='IG Direct @' + ((_IGD or {}).get('account') or '') + ' · нет сферы', unread=_c.get('n') or 1, last=_c.get('age', ''), owner=SEC[0], owner_link=A(SEC[1])))
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
        _m = _re.match(r'^- (\d{4}-\d\d-\d\d)T(\d\d:\d\d):\d\d[+-]\d\d:\d\d\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*(.*)$', _ln) or _re.match(r'^- (\d{4}-\d\d-\d\d) (\d\d:\d\d) Bogot\S* \| ([^|]+)\| ([^|]+)\| (.*)$', _ln)
        if not _m: continue
        _when = f'{_m.group(1)} {_m.group(2)}'
        _w = _m.group(3).strip().lower(); _ch = next((v for k, v in _WCH.items() if _w.startswith(k)), None)
        if not _ch: continue
        _hs = [h for h in (_H.get(_ch) or _H.get('WhatsApp' if 'WhatsApp' in _ch else _ch) or []) if h]
        _txt = _m.group(5)
        if not any(_re.search(r'(?<!\w)' + _re.escape(h if h.startswith('@') else '@' + h) + r'(?!\w)', _txt, _re.I) for h in _hs): continue
        _t = _re.sub(r'\s*\([^)]*\)\s*$', '', _m.group(4).strip()).lower()
        _k = (_ch + '|' + _t)
        if _when > _MENT.get(_k, ''): _MENT[_k] = _when
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
 dict(channel='Telegram', src='src/tg_live.json (TG Desktop: синие unmuted бейджи из All chats, по чатам)', live=True, gap='muted/каналы не в списке; нет вкладки Unread — считаем синие бейджи All chats'),
 dict(channel='Viber', src='список Viber (src/viber_live.json) + бейдж UIA-поллера (heartbeat: RDP-шара или SMB-pull с AX42 каждые ≤10 мин; бейдж только при открытом RDP)', live=False, gap='toast нет (AUMID не найден); БД Viber зашифрована; по чатам — только снимок списка при проверке; mute-чаты бейдж не дают'),
 dict(channel='Instagram', src='IG Direct @rosscompass (src/ig_direct_live.json), раз в день', live=False, gap='только личный @rosscompass; раз в сутки; Requests (запросы) не смотрим; превью не берём'),
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
            m3 = _re.match(r'^- (\d{4}-\d\d-\d\d)T(\d\d:\d\d):\d\d[+-]\d\d:\d\d\s*\|\s*whatsapp-(esp|ukr)-secretary', ln)  # ISO since 30.10
            if m3: t3 = m3.group(3).upper(); last[t3] = max(last.get(t3, ''), f'{m3.group(1)} {m3.group(2)}')
            m4 = _re.match(r'^- (\d{4}-\d\d-\d\d)T(\d\d:\d\d):\d\d[+-]\d\d:\d\d\s*\|\s*telegram-secretary', ln)
            if m4: last['TG'] = max(last.get('TG', ''), f'{m4.group(1)} {m4.group(2)}')
    except FileNotFoundError: pass
    try:  # 30.10 watcher-fix-20261030-1842: liveness вочера AX42 по SMB (wa_alive_pull.py), тихий канал ≠ «?»
        _wa = json.load(open('/workspace/ax42-share/wa-alive.json'))
        for _t in ('UKR', 'ESP'):
            if _wa.get(_t): last[_t] = max(last.get(_t, ''), _wa[_t][:16].replace('T', ' '))
    except Exception: pass
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
                # t4368: src=alive-no-count раньше давал unread=0 и 🟢 — ложный «нет непрочитанных». Теперь бейдж-пиксели на кнопке таскбара.
                _hu = _vhb.get('has_unread'); _vsrc = _vhb.get('src', '')
                if _hu is True:
                    _vlat = (_VL or {}).get('at', '') if '_VL' in globals() else ''
                    W['Viber'] = dict(st='warn', alive=f"UIA поллер ✓ {_mode} · 🔴 бейдж непрочитанных на таскбаре · список снят {_vlat or '—'}", ping=_vhb.get('ts','')[:16], ping_lbl='heartbeat')
                elif _hu is False:
                    W['Viber'] = dict(st='ok', alive=f"UIA поллер ✓ {_mode} · бейджа нет (0 непрочитанных без mute)", ping=_vhb.get('ts','')[:16], ping_lbl='heartbeat')
                else:
                    W['Viber'] = dict(st='warn', alive=f"UIA поллер ✓ {_mode} · процесс жив · счётчик НЕ читается (src={_vsrc}{', hb по SMB вне RDP' if _vhb.get('via') == 'smb-pull' else ''}) — смотреть список Viber", ping=_vhb.get('ts','')[:16], ping_lbl='heartbeat')
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
    # t4368: Instagram Direct (@rosscompass) — снимок раз в день
    if _IGD:
        _ia = (_IGD.get('at') or '').replace(' Bogotá', '')
        _ist = 'red' if not _IGD.get('ok') else age(_ia, 30)
        W['Instagram'] = dict(st=_ist, alive=('IG Direct @' + (_IGD.get('account') or '?') + ' · раз в день · непрочитанных чатов: ' + str(_IGD.get('unread_chats'))) if _IGD.get('ok') else ('IG Direct: ' + (_IGD.get('err') or 'ошибка')), ping=_ia, ping_lbl='последний снимок')
    else:
        W['Instagram'] = dict(st='warn', alive='IG Direct @rosscompass — снимка ещё нет', ping='', ping_lbl='')
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
                        data['unsorted'].append(dict(key=f"{r['channel']}|{r['chat']}", channel=r['channel'], title=r['chat'], kind='↩ с даша: на сортировку · было ' + g['sphere'], unread=r.get('unread_chat'), last=r.get('last', ''), owner=r.get('owner'), owner_link=r.get('owner_link'), is_group=r.get('is_group'), muted=bool(r.get('muted'))))
                        _ukeys.add(k)
                elif sp == 'Игнор': _moved.append(('Игнор', dict(r, src_sphere=g['sphere'], ignored=True)))  # t4997: keep unread in Игнор so dash sum == live
                elif sp: _moved.append((sp, dict(r, src_sphere=g['sphere'])))
            g['rows'] = keep
        # выбранная сфера для пункта «на сортировку» -> строка в сфере (чтобы не терялось, даже если contacts не сматчился)
        _rest = []
        for u in data['unsorted']:
            o = _MO.get((u.get('key') or '').lower()); sp = o and o.get('sphere')
            if sp == 'Игнор':
                _moved.append(('Игнор', dict(sender=u.get('title'), chat=u.get('title'), channel=u.get('channel'), unread_chat=u.get('unread'), last=u.get('last', ''), owner=u.get('owner'), owner_link=u.get('owner_link'), src='dash-tap', sorted=True, muted=bool(u.get('muted')), ignored=True)))
            elif sp and sp != '__unsort':
                _moved.append((sp, dict(sender=u.get('title'), chat=u.get('title'), channel=u.get('channel'), unread_chat=u.get('unread'), last=u.get('last', ''), owner=u.get('owner'), owner_link=u.get('owner_link'), src='dash-tap', sorted=True, muted=bool(u.get('muted')))))
            else: _rest.append(u)
        data['unsorted'] = _rest
        for sp, r in _moved:
            g = next((x for x in data['messengers'] if x['sphere'] == sp), None)
            if g is None: g = dict(sphere=sp, rows=[]); data['messengers'].append(g)
            if not any(f"{x.get('channel')}|{x.get('chat')}".lower() == f"{r.get('channel')}|{r.get('chat')}".lower() for x in g['rows']): g['rows'].append(r)
        # Rost t4380: перенесённая тапом строка не дублируется в «без сообщений» той же сферы
        for g in data['messengers']:
            _rt = {(x.get('chat') or '').lower() for x in g['rows']}
            if g.get('zero_contacts'): g['zero_contacts'] = [z for z in g['zero_contacts'] if (z.get('title') or '').lower() not in _rt]
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
# Rost t4989: auto-clear stale hang на каждом rebuild — без ручного ✓/init.
# Census 27.10 — разовый снимок; unread без live last (toast/secretary-log/viber_live/ig) = мёртвый → 0.
# rst ans/skip без нового last после at → unread/pending сброс (hang тоже).
try:
    _ac_u = _ac_p = _ac_rst = 0
    for g in data.get('messengers') or []:
        for r in g.get('rows') or []:
            if r.get('cu_tasks'): continue
            src = r.get('src') or ''
            last = (r.get('last') or '').strip()
            rst = r.get('rst') or {}
            if rst.get('st') in ('ans', 'skip'):
                at = (rst.get('at') or '')[:10]
                ld = last[:10]
                if not ld or (at and ld <= at):
                    if (r.get('unread_chat') or 0) > 0: r['unread_chat'] = 0; _ac_rst += 1
                    if r.get('pending'): r['pending'] = None; _ac_rst += 1
            if 'census 27.10' in src and not last:
                if (r.get('unread_chat') or 0) > 0:
                    r['unread_chat'] = 0; _ac_u += 1
                    r['src'] = src + ' · unread cleared t4989 (stale census, no live last)'
            # «наш ход» / мёртвый pending без live last и src не ждём-мяч-у-них с свежим last — Dating/контекст уже сняты выше
    for u in data.get('unsorted') or []:
        kind = (u.get('kind') or '') + ' ' + (u.get('src') or '')
        if 'census 27.10' in kind and not (u.get('last') or '').strip() and (u.get('unread') or 0) > 0:
            u['unread'] = 0; _ac_u += 1
    print('auto-clear t4989: census/unread', _ac_u, 'rst-cleared', _ac_rst)
except Exception as _e: print('auto-clear t4989 skip', _e)
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
            _rst = r.get('rst') or {}
            _done = _rst.get('st') in ('ans', 'skip') and (not (r.get('last') or '').strip() or (( _rst.get('at') or '')[:10] and (r.get('last') or '')[:10] <= (_rst.get('at') or '')[:10]))
            # t5002: Игнор/muted-standing не «висят как диалоги» — unread в сумме есть, (N дн.) нет
            _ign = bool(r.get('ignored')) or g.get('sphere') == 'Игнор' or bool(r.get('muted') and (r.get('unread_chat') or 0) > 50)
            _hang = (not _done) and (not _ign) and ((r.get('unread_chat') or 0) > 0 or bool(r.get('pending')) or any((u.get('n') or 0) > 0 for u in (r.get('unread_list') or [])))
            if _ign: r.pop('hang_since', None)
            _hs(f"{r.get('channel')}|{r.get('chat')}".lower(), r, _hang)
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
        _m = re.match(r'^- (\d{4}-\d\d-\d\d)T(\d\d:\d\d):\d\d[+-]\d\d:\d\d\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*(.*)$', _ln) or re.match(r'^- (\d{4}-\d\d-\d\d) (\d\d:\d\d) Bogot\S* \| ([^|]+)\| ([^|]+)\| (.*)$', _ln)
        if not _m: continue
        _when = f'{_m.group(1)} {_m.group(2)}'
        _w = _m.group(3).strip().lower(); _ch = next((v for k, v in _MW.items() if _w.startswith(k)), None)
        if not _ch: continue
        _hs = [h.lstrip('@') for h in (_MH.get(_ch) or _MH.get('WhatsApp' if 'WhatsApp' in _ch else _ch) or [])] + _MDEF
        if not any(re.search(r'(?<!\w)@' + re.escape(h) + r'(?!\w)', _m.group(5), re.I) for h in _hs if h): continue
        _t = re.sub(r'\s*\([^)]*\)\s*$', '', _m.group(4).strip()).lower()
        _MM[_t] = max(_MM.get(_t, ''), _when)
    _nm = 0
    for g in data['messengers']:
        for r in g['rows']:
            if not r.get('is_group') or not r.get('unread_chat'): continue
            c = (r.get('chat') or '').lower(); ma = max([v for k, v in _MM.items() if k == c or k.startswith(c) or c.startswith(k)] or [''])
            if ma and ma[:10] >= (r.get('hang_since') or ma[:10]): r['mention_at'] = ma; _nm += 1
    print('mentions:', _nm, 'log hits', len(_MM))
except Exception as _e: print('mentions skip', _e)
# === Rost t4356u: last_msgs — превью последних ПОЙМАННЫХ сообщений на строке (hover-поповер / раскрытие на мобиле).
# Только чаты из allowlist/log_only своего вочера (те, что вочер и так пишет в secretary-log). Текст = только цитата из тоста «…»/"…"
# (или голый медиа-маркер Photo/Video/Voice); пояснения бота не берём. Нет цитаты -> строки нет (не выдумываем). ≤3, новые сверху, ≤120 симв.
try:
    _LMDIR = {'whatsapp-ukr-secretary': 'wa-ukr-secretary', 'ukr': 'wa-ukr-secretary', 'whatsapp-esp-secretary': 'wa-esp-secretary', 'esp': 'wa-esp-secretary',
              'tg': 'tg-secretary', 'telegram-secretary': 'tg-secretary', 'viber': 'viber-ukr-secretary', 'viber-ukr-secretary': 'viber-ukr-secretary'}
    _LMAL = {}
    def _lm_allow(folder):
        if folder not in _LMAL:
            ents = []
            for fn in ('allowlist.txt', 'log_only.txt'):
                try:
                    for l in open(f'/workspace/notify-watchers/{folder}/{fn}', encoding='utf-8'):
                        l = l.strip()
                        if not l or l.startswith('#'): continue
                        ents.append(l)
                except FileNotFoundError: pass
            _LMAL[folder] = ents
        return _LMAL[folder]
    def _lm_ok(folder, title):
        tl = title.lower(); td = re.sub(r'\D', '', title)
        for e in _lm_allow(folder):
            if e.lower().startswith('contains:'):
                if e[9:].strip().lower() and e[9:].strip().lower() in tl: return True
            elif re.fullmatch(r'[+\d\s()-]{7,}', e):
                d = re.sub(r'\D', '', e)
                if d and d in td: return True
            elif len(e) >= 3 and e.lower() in tl: return True
        return False
    def _lm_text(s):
        s = re.sub(r'\s*\((?:\d+(?:[–-]\d+)?\s+unread[^)]*|coalesced)\)', '', s).strip()
        q = re.findall(r'«([^»]{1,400})»|"([^"]{1,400})"|“([^”]{1,400})”', s)
        parts = [next(x for x in t if x) for t in q]
        who = None
        mw = re.match(r'^([^«"“:]{2,40}):\s*[«"“]', s)
        if mw: who = mw.group(1).strip()
        if not parts:
            if re.fullmatch(r'(?:\d+\s*[×x]\s*)?(?:Photo|Video|Voice message|Audio|Sticker|GIF|Document|фото|видео|голосовое)[\w\s:().,–-]{0,30}', s, re.I): parts = [s]
            else: return None, None
        t = ' / '.join(p.strip() for p in parts)
        return who, (t[:117] + '…' if len(t) > 120 else t)
    _LM, _lmi = {}, 0  # (channel, chat_lower) -> [{at, who, text}]; _lmi = порядок строки в логе (одна минута -> позже = новее)
    for _ln in open(LOG, encoding='utf-8'):
        _m = re.match(r'- (2026-\d\d-\d\d)T(\d\d:\d\d):\d\d[+-]\d\d:\d\d\s*\|\s*([\w-]+)\s*\|', _ln) or re.match(r'- (2026-\d\d-\d\d) (\d\d:\d\d)(?:[–-]\d\d:\d\d)? (?:Bogotá|COT)?\s*\|\s*([\w-]+)\s*\|', _ln)
        if not _m: continue
        _f = _LMDIR.get(_m.group(3).lower())
        if not _f: continue
        _sg = _ln.rstrip('\n').split('|')
        if len(_sg) < 4: continue
        _title = re.sub(r'^группа\s*', '', _sg[2].strip()).strip('«»" ')
        if not _lm_ok(_f, _sg[2]): continue
        _who, _txt = _lm_text(_sg[3].strip())
        if not _txt: continue
        _disp, _ = known(_sg[2])
        _base = re.sub(r'\s*\([^)]*\)\s*$', '', _title).strip('«»" ').strip()
        _pm = re.search(r'\(([^)]*)\)\s*$', _title)
        if not _who and _pm:  # «(Elena Tolstova)» = отправитель, только если это известное имя (не slug/пояснение)
            _pw = next((x for x in SENDERS if _pm.group(1).strip().startswith(x)), None)
            if _pw: _who = _pm.group(1).strip()
        _ch = CH.get(_m.group(3), CH.get(_m.group(3).upper(), _m.group(3)))
        _lmi += 1
        _e = dict(at=f'{_m.group(1)} {_m.group(2)}', who=_who or _disp or _base, text=_txt, _i=_lmi)
        for _k in {(_ch, (_disp or _base).lower()), (_ch, _base.lower())}:
            _L = _LM.setdefault(_k, [])
            if not any(x['text'] == _e['text'] and x['at'] == _e['at'] for x in _L): _L.append(_e)
    for _k in _LM: _LM[_k] = [{k: v for k, v in x.items() if k != '_i'} for x in sorted(_LM[_k], key=lambda x: (x['at'], x['_i']), reverse=True)[:3]]
    def _lm_find(ch, chat):
        c = (chat or '').lower().strip()
        if not c: return None
        if (ch, c) in _LM: return _LM[(ch, c)]
        d, _ = known(chat)
        if d and (ch, d.lower()) in _LM: return _LM[(ch, d.lower())]
        c2 = re.sub(r'(\.\.\.|…)$', '', c).strip()
        if len(c2) >= 6 and c2 != c:
            for (kch, kc), v in _LM.items():
                if kch == ch and kc.startswith(c2): return v
        return None
    _nlm = 0
    for g in data['messengers']:
        for r in g['rows']:
            v = _lm_find(r.get('channel'), r.get('chat'))
            if v: r['last_msgs'] = v; _nlm += 1
            else: r.pop('last_msgs', None)
    for u in data.get('unsorted') or []:
        v = _lm_find(u.get('channel'), u.get('title'))
        if v: u['last_msgs'] = v; _nlm += 1
    print('last_msgs: rows', _nlm, 'chats in log', len(_LM))
except Exception as _e: print('last_msgs skip', _e)
# Rost t5018: muted (колокольчик выкл) в WA/Viber live -> muted=True на ВСЕХ строках (вкл. dash-tap), даш их прячет
try:
    _MU = set()
    for _fn, _ch in (('wa_ukr_live.json', 'WhatsApp UKR'), ('wa_esp_live.json', 'WhatsApp ESP'), ('viber_live.json', 'Viber'), ('tg_live.json', 'Telegram')):
        _fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), _fn)
        if os.path.exists(_fp):
            for _c in (json.load(open(_fp, encoding='utf-8')).get('chats') or []):
                if _c.get('muted'): _MU.add((_ch + '|' + (_c.get('title') or '')).lower())
    _nm = 0
    for _g in data.get('messengers', []):
        for _r in _g.get('rows', []):
            if (str(_r.get('channel')) + '|' + str(_r.get('chat'))).lower() in _MU and not _r.get('muted'): _r['muted'] = True; _nm += 1
    for _u in data.get('unsorted', []):
        if (_u.get('key') or '').lower() in _MU and not _u.get('muted'): _u['muted'] = True; _nm += 1
    print('t5018 muted sync:', len(_MU), 'muted in live, flagged', _nm)
except Exception as _e:
    print('t5018 muted sync skip', _e)
json.dump(data, open(os.path.join(ROOT, 'data-test-ma.json'), 'w'), ensure_ascii=False, indent=1)
print('rows', sum(len(g['rows']) for g in data['messengers']), 'groups', [g['sphere'] for g in data['messengers']])
