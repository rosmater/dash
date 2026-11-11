"""Снимок блоков «Личное» -> src/personal_blocks.json (Rost 25.10 ~23:55 Богота).
Источники — только реальные записи; нет записи -> None («—»). Перезапуск: python3 src/personal_blocks_gen.py"""
import json, os, datetime as dt
H = os.path.dirname(os.path.abspath(__file__))
cu = lambda i: f'https://rosmater.github.io/cu/?t={i}' if i else None
TODAY = dt.date(2026, 10, 26)
D = lambda s: dt.date.fromisoformat(s)
iso = lambda d: d.isoformat()
def rng(a, b):  # inclusive
    d = a
    while d <= b:
        yield d; d += dt.timedelta(days=1)
WEEK0 = TODAY - dt.timedelta(days=TODAY.weekday())  # пн 19.10
MONTH0 = TODAY.replace(day=1)
LAST14 = [TODAY - dt.timedelta(days=13 - i) for i in range(14)]

# ---------- посещаемость: план по дням недели, факт только из журналов ----------
def attend(plan_wd, facts, plan_from=None, src=''):
    """plan_wd: дни недели (0=пн); facts: {date: 'done'|'miss'}; остальные плановые прошедшие дни = 'unk' (без отметки)."""
    def stat(a):
        P = [d for d in rng(a, TODAY) if d.weekday() in plan_wd and (not plan_from or d >= plan_from)]
        dn = sum(1 for d in P if facts.get(iso(d)) == 'done'); ms = sum(1 for d in P if facts.get(iso(d)) == 'miss')
        return dict(planned=len(P), done=dn, miss=ms, unk=len(P) - dn - ms, pct=round(dn / len(P) * 100) if P else None)
    days = []
    for d in LAST14:
        st = facts.get(iso(d))
        if not st and d.weekday() in plan_wd and (not plan_from or d >= plan_from): st = 'unk'
        days.append(dict(date=iso(d), st=st))
    return dict(days=days, week=stat(WEEK0), month=stat(MONTH0), src=src)

# Сон — Google Sheet «Дневник сна» (дата = вечер, когда лёг); 20–24.10 пусто
SLEEP = {'2026-10-12': '7:30', '2026-10-13': '6:20', '2026-10-15': '~6:45', '2026-10-16': '~6:45', '2026-10-17': '8:00', '2026-10-18': '8:00', '2026-10-19': '7:40'}
def mins(s): h, m = s.lstrip('~').split(':'); return int(h) * 60 + int(m)
sleep_nights = []
for d in LAST14:
    v = SLEEP.get(iso(d)); m = mins(v) if v else None
    sleep_nights.append(dict(date=iso(d), hours=v, min=m, approx=bool(v and v.startswith('~')),
                             color=None if m is None else ('green' if m >= 480 else 'yellow' if m >= 450 else 'red')))
known = [n for n in sleep_nights if n['min'] is not None]
last = known[-1] if known else None
recent = [n for n in sleep_nights if n['min'] is not None and D(n['date']) >= TODAY - dt.timedelta(days=1)]  # прошлая/позапрошлая ночь

STEPS = {'2026-10-18': 6328, '2026-10-20': 614, '2026-10-25': 207}
def scol(v): return None if v is None else 'red' if v < 2000 else 'orange' if v < 4000 else 'yellow' if v < 7000 else 'green'

# Употребление — колонка «Употреблял» SLEEP_LOG.md + коммент «Дневник сна». Классификацию сомнительного не выдумываем.
USE = {'2026-10-12': ('green', 'не употреблял'), '2026-10-13': ('green', 'не употреблял'), '2026-10-14': ('yellow', 'бокал вина вечером'),
       '2026-10-17': ('green', 'не употреблял'), '2026-10-18': ('unclassified', 'немного нюхал (за компанию) — цвет не ставлю, Rost решит'),
       '2026-10-19': ('green', 'нет (SLEEP_LOG)')}

events_days = []
EV = {  # реальные события + шаблон календаря (тусовка/друзья); свидания и здоровье сюда не кладём (скрыто от помощницы в своих блоках)
  # Rost 26.10: все Lal Expo workshops + главная выставка = обязательно ехать
  '2026-10-29': [
    dict(t='13:00–21:00', title='🎪 Workshop Lal Expo Bogotá — обязательно', cu='86bb79fmt', kind='real'),
    dict(t='21:00–02:00', title='🏆 Premios Bantokens + фиеста (La Pámpara) — обязательно', cu='86bb79fmt', kind='real'),
  ],
  '2026-10-30': [dict(t='до ~02:00', title='🎪 конец Premios/фиесты Lal Expo (с 29.10)', cu='86bb79fmt', kind='real'),
                 dict(t='20:00–03:00', title='Тусовка', kind='tpl')],
  '2026-10-31': [dict(t='14:00–17:00', title='Друзья', kind='tpl')],
  '2026-11-06': [dict(t='20:00–03:00', title='Тусовка', kind='tpl')],
  '2026-11-07': [dict(t='14:00–17:00', title='Друзья', kind='tpl')],
}
for i in range(14):
    d = TODAY + dt.timedelta(days=i)
    it = EV.get(iso(d), [])
    for x in it: x['url'] = cu(x.get('cu'))
    events_days.append(dict(date=iso(d), items=it))

def task(i, name, due=None, status='to do', note=None): return dict(cu=i, url=cu(i), name=name, due=due, status=status, note=note)

B = dict(
 _note='Снимок из CU Personal + Google Sheets «Дневник сна»/«Тренировки» + Google Calendar + KB. Нет записи = «—», не выдумываем. Блоки с hide_from_helper не попадают в helper.html.',
 fetched_at='2026-10-25T23:59:00-05:00', today=iso(TODAY), week_from=iso(WEEK0), month_from=iso(MONTH0),
 docs=dict(title='Документы', items=[
   dict(name='Гражданство — Румыния', status='жду', state='wait', note='документы поданы, ждём приказ (Stadiu Dosar, Articolul 11)', cu='86b7hcb3a', url=cu('86b7hcb3a'), cu_name='Румынский паспорт (была ли апелляция? вынесли ли решение?)', cu_status='to do', due='2026-11-03'),
   dict(name='ПМЖ — Парагвай', status='подготовка к подаче', state='prep', attn=True, cu='86ba3c1x4', url=cu('86ba3c1x4'), cu_name='(Контракт на работу, подготовка к ПМЖ) ПАРАГВАЙ (183 дня в году)', cu_status='for check', due='2026-10-15',
        note='контракт с LLC 2 700 $ + апостиль; Takenos/Ueno банк; Payoneer — жду', related=[task('86bayeyr8', 'начать планировать поездку в Парагвай (до 27 января)', '2026-11-01'), task('86bbq6etm', 'Сроки документов (наполнить)', '2026-11-07', 'main')],
        kb='shared-personal/paraguay-residency/employer-awesome1-llc.md'),
 ]),
 checklist=dict(title='Ежедневный чеклист', cu='86b7k95k6', url=cu('86b7k95k6'), night_cu='86b8gzqtb', night_url=cu('86b8gzqtb'), start='2026-10-25',
   items=[dict(id='sleepdiary', text='Заполнить дневник сна'), dict(id='bju', text='Заполнить БЖУ (отчёт питание)'), dict(id='vit', text='Витамины + креатин (160 г белка, 300 г углеводов)'),
          dict(id='eyes', text='Зарядка для зрения + капли'), dict(id='prep', text='PrEP', hide_from_helper=True), dict(id='water', text='Вода 3 л'), dict(id='shower', text='Контрастный душ'),
          dict(id='steps', text='10 000 шагов (50 прыжков, турник, 15 мин солнца)'), dict(id='tomorrow', text='Проверить дела на завтра + крайнее время сна (9,5 ч до подъёма)'),
          dict(id='msgs', text='Проверка мессенджеров (TG, WA ×2 телефона, Viber, Instagram)')],
   night=['Магний / Б / валерьяна', 'Закрыть ванную', 'Закрыть окно', 'Выключить огонёк микроволновки', 'Телефоны / павербанки / ноут / наушники — на зарядку', 'Холодильник не помешает утром?', 'Фильтр воздуха — ночной режим', 'Кровать застелена? полотенце вместо подушки'],
   src='пункты — описание CU 86b7k95k6 и 86b8gzqtb (чеклиста/подзадач в CU нет); отметки — в этом браузере с 25.10, статистика = дни, где отмечены все пункты'),
 bju=dict(title='БЖУ', today=None, last=dict(date='2026-10-24', fact=dict(p=162.9, f=80.0, c=150.3, kcal=2011), plan=dict(p=160, f=65, c=300, kcal=2425),
   note='Белок закрыт. Жиры выше плана. Углеводы/ккал недобор.'), src='shared-health/nutrition-bju/today-*.md · % дня = ккал факт/план; за 25.10 файла нет'),
 sleep=dict(title='Сон', nights=sleep_nights, last=last, attn=bool(recent and recent[-1]['color'] == 'red'),
   src='Google Sheet «Дневник сна» (дата = вечер, когда лёг) · ≥8:00 зелёный · 7:30–7:59 жёлтый · <7:30 красный · 20–24.10 не заполнено'),
 dating=dict(title='Дейтинг', hide_from_helper=True, days=[
   dict(date='2026-10-25', items=[dict(t='20:00–23:00', title='Ужин + время с девушкой', who=None, kind='tpl')]),
   dict(date='2026-10-26', items=[])],
   next=[dict(date='2026-10-29', t='21:00–23:00', title='Карен', kind='tpl')],
   src='Google Calendar (шаблон недели, имя не указано) + dating/PRIORITY.md (назначенных свиданий нет; Andrea 22.10 — прошло)'),
 events=dict(title='Мероприятия', days=events_days,
   todo=[dict(id='diego', title='Диего — встретиться', items=['Написать Диего, предложить день', 'Выбрать место и время', 'Встретиться'], cu=None),
         dict(id='rus', title='Русский чувак — потусить / пойти', items=['Связаться, договориться куда', 'Выбрать день', 'Сходить'], cu=None),
         dict(id='santafe', title='Выехать в Санта-Фе на мопеде', items=['Выбрать день без дождя', 'Мопед: бензин, шины, документы', 'Маршрут Медельин → Санта-Фе-де-Антиокия', 'Поехать'], cu=None)],
   planned=[
            dict(dates='29.10.2026', title='🎪 Workshop Lal Expo Bogotá + Premios Bantokens — обязательно ехать', cu='86bb79fmt', url=cu('86bb79fmt'), note='La Pámpara, Chapinero · 13:00 workshop → 21:00 Premios → фиеста до ~02:00 · CU 86bb79fmt'),
            dict(dates='11–13.04.2027', title='🏟️ LALEXPO International Cali (главная выставка) — обязательно ехать', cu=None, note='Centro de Eventos Valle del Pacífico · якорь следующих воркшопов'),
            dict(dates='25.12 – 10.01', title='Новый год с пацанами + туса', cu=None),
            dict(dates='10–17.01', title='Поездка в Парагвай', cu='86bayeyr8', url=cu('86bayeyr8'), note='после НГ; CU планировать до 27.01')],
   src='Lal Expo: workshops + главная Cali = обязательно (Rost 26.10) · CU 86bb79fmt · тусовка/друзья — шаблон; чеклисты — каркас'),
 spanish=dict(title='Испанский', **attend({0, 4}, {'2026-10-19': 'miss', '2026-10-26': 'miss'}, src='план пн+пт (Google Calendar); факт: ✖ 19.10 и ✖ 26.10 «не было (спал)», остальные занятия не отмечены')),
 steps=dict(title='Шаги', days=[dict(date=iso(d), steps=STEPS.get(iso(d)), color=scol(STEPS.get(iso(d)))) for d in LAST14],
   src='iPhone → STEPS_LOG.md (с 20.10) + 18.10 из «Дневника сна» · <2000 красный · 2000–3999 оранжевый · 4000–6999 жёлтый · ≥7000 зелёный'),
 gym=dict(title='Спортзал', **attend({0, 2, 4}, {'2026-10-14': 'done', '2026-10-16': 'miss', '2026-10-19': 'done'}, plan_from=D('2026-10-12'),
   src='Google Sheet «Тренировки» (журнал с 12.10; 12.10 не подтверждено) · план пн/ср/пт · тренер Keiner')),
 boxing=dict(title='Бокс', cu='86bcnrmt7', url=cu('86bcnrmt7'), **attend({1, 3}, {'2026-10-20': 'done'}, plan_from=D('2026-10-20'),
   src='Google Sheet «Тренировки» · план вт/чт 10:00–11:30 с 20.10 · Johann Ruiz · абонемент 8/мес')),
 alcohol=dict(title='Употребление', hide_from_helper=True, days=[dict(date=iso(d), level=(USE.get(iso(d)) or (None, None))[0], text=(USE.get(iso(d)) or (None, None))[1]) for d in LAST14],
   src='SLEEP_LOG.md колонка «Употреблял» + «Дневник сна» · пусто = не известно'),
 health=dict(title='Здоровье', hide_from_helper=True, cu='86b6qp9ey', url=cu('86b6qp9ey'), groups=[
   dict(name='Брекеты / ортодонт', cu='86b6qp4uc', url=cu('86b6qp4uc'), tasks=[
     task('86bcmwtt5', 'Снимок зуба (Cone Beam CT) в Oralvission — от ортодонта Маурисио Морено', '2026-10-27 12:30'),
     task('86b716gh8', 'Сита ортодонт (28 октября 14:00)', '2026-10-28 14:00'),
     task('86b8ddw1x', '‼️ Сита ортодонт — не забыть + будильник')]),
   dict(name='Анализы', tasks=[task('86b7rcd9t', 'Анализы Сомос — надо сдавать что-то? (записаться)', '2026-11-20', 'in progress'),
     task('86b9rk01c', '‼️ Не забыть про поход на анализы 10:30')]),
   dict(name='Вакцины', cu='86b6q912n', url=cu('86b6q912n'), tasks=[task('86b6q93pc', 'Корь / гепатит бустер (Engerix-B + Havrix) — проверить по списку', '2026-10-27'),
     task('86b6q92zn', 'Verorab бустер + Influenza (на 27.09.27)', '2026-09-26'), task('86b6q93gw', 'Typhim Vi (до 22.07.28)', '2026-07-17')]),
   dict(name='Прочее', tasks=[task('86b6qphf1', 'Колумбия — записаться на сон (сомнолог?)', '2026-11-05'), task('86b6qphcd', 'Заказать PrEP', '2026-11-29'),
     task('86bcm9u4k', 'Заменить линзы в компьютерных очках', '2026-10-26')])],
   src='CU Personal → «Здоровье» 86b6qp9ey и «Брекеты» 86b6qp4uc (открытые)'),
)
# сроки: даты в будущем 2027 для вакцин
for g in B['health']['groups']:
    for t in g['tasks']:
        if t['cu'] == '86b6q92zn': t['due'] = '2027-09-26'
        if t['cu'] == '86b6q93gw': t['due'] = '2028-07-17'
# Rost t6060u: «🧭 На решение» в Личном (как Табакевич). Не мейн/родители.
# t6061u: у ассистентки на Личном только этот блок и «Документы» — остальные hide_from_helper.
B['decisions'] = dict(
    title='На решение',
    items=[
        dict(slot='Виза Колумбия', cu='86b6qnxn8', url=cu('86b6qnxn8'),
             name='Подать на новую визу колумбия - какой план?',
             status='to do', due='2027-05-01', role='TO DO', assignees=['Rost']),
        dict(slot='Ирина · оплата', cu='86b82r2b5', url=cu('86b82r2b5'),
             name='Ирина оплата (все пришло?) - проверка отчета и решение',
             status='to do', due='2026-11-04', role='Control', assignees=['Rost']),
    ],
    src='CU Personal · открытые задачи, где Rost должен решить (не мейн/родители)',
)
for k in ('checklist', 'bju', 'sleep', 'dating', 'events', 'spanish', 'steps', 'gym', 'boxing', 'alcohol', 'health'):
    if isinstance(B.get(k), dict):
        B[k]['hide_from_helper'] = True
json.dump(B, open(os.path.join(H, 'personal_blocks.json'), 'w'), ensure_ascii=False, indent=1)
print('ok', B['sleep']['last'], B['gym']['week'], B['boxing']['week'], B['spanish']['month'])
