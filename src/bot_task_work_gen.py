
#!/usr/bin/env python3
"""Build src/bot_task_work.json: CU task id → short theses of what the bot actually does.

Sources (no ClickUp descriptions, no invented jobs):
  - bot-routines-inventory + ROUTINE-GROUPS / CALENDAR (routine name + schedule)
  - knowledge KB READMEs / queue scripts — curated bullets only when the job is documented
If a Ros (BOT) task has no evidence, it is omitted (UI shows «работа бота не описана»).
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bot_work_gen import BOTS, CUID_RX, INV, parse_inventory  # noqa: E402

# curated extra jobs (not invented): sourced from KB READMEs / inventory / queue scripts
# routines with CU ids are merged automatically
CURATED = {
"86b6qq509": [
  "Ежемесячно собирает сводку доходов и сам подставляет «Недвига» из листа аренды",
  "После куска пишет комментарий в ClickUp и ставит for check",
],
"86bcr1a1r": [
  "Ежемесячный замер подписчиков IG-референсов к 1-му числу",
  "Пишет результат в таблицу и комментарий в ClickUp, статус for check",
],
"86bc1tdu5": [
  "По понедельникам в Bundle morning mega проверяет остаток residential-прокси IPRoyal",
  "Если меньше 1 ГБ — for check и сигнал Rost; иначе сдвигает срок на следующий понедельник",
],
"86b9abep9": [
  "В Helper sun lite (вс 8:10) гоняет 05services weekly и пишет отчёт в эту задачу с тегом Rost",
],
"86b9axevh": [
  "Еженедельный разбор статистики LolaPop (Informe Stats WoW) в утреннем пакете по понедельникам",
  "Комментарий в ClickUp и тег Rost, статус for check, никогда complete",
],
"86bacy8cr": [
  "Проверяет, заполнен ли недельный отчёт Димы по дебиторке, и пишет комментарий в ClickUp",
],
"86b8de8ru": [
  "Каждый будний проверяет таблицу заявок Flames и пишет в эту задачу только комментарий (новые разобраны / новых нет)",
],
"86bawjbgj": [
  "Ведёт сводку по запуску RA222 Valentina в эту задачу (CU-first; в TG пишет только при критичном входящем или GO)",
],
"86bb943nu": [
  "Еженедельно пингует Maks по статусу адвокатов Хуан 23 и пишет комментарий в ClickUp",
],
"86bbzjbuf": [
  "Следит за перепиской с Анатолием по конденсату кондиционера Olivino 3 и отчитывается в ClickUp (for check)",
],
"86bb93ynk": [
  "Мониторит дело деокупации Novelda у Maks; активные пинги только по GO Rost",
],
"86bc24u5z": [
  "Ежемесячно к 25-му выгружает фактуры GANA и отправляет Яне на «вы»",
],
"86baggxqe": [
  "Два раза в неделю (пн в morning mega и ср) снимает статистику объявления Treveles на Idealista и пишет её в ClickUp, не в чат",
],
"86bbzx9x4": [
  "По понедельникам в morning mega lean-монитор Sofia Lunara: новые sub/followers и комментарий в ClickUp",
],
"86b9va7c4": [
  "Читает группу с Анатолием по ремонту Topacio; понедельник — пинг только с OK Rost; новости — комментарий в ClickUp",
],
"86bc1d1wj": [
  "Мониторит почту Solvia (слоты 11:00 и 22:30 Мадрид) в helper-morning-mega и скриптом solvia_dash_sync.py",
  "Если есть письма о новых объектах — комментарий и for check в ClickUp",
],
"86b9crta7": [
  "В Bundle morning mega (пн/вт/чт) lean-монитор Aurora/RA217 в TG и комментарий в ClickUp",
],
"86ba7an25": [
  "В Helper sun lite (вс 8:10) снимает часы Jibble (Sara и Michelle) и пишет сводку в эту задачу",
  "Тот же срез Jibble входит в пакет контроля офиса к понедельнику",
],
"86bcm8ybt": [
  "Недельный пакет контроля офиса (старт с вс вечера, отчёт к пн): камера Imou, Yaware, Jibble, дневные отчёты и пептидные чаты — сводный комментарий в эту задачу",
],
"86b897mmr": [
  "Курирует запуск рекламы Хукашоп: в понедельник пинг Denis, отчёт только в ClickUp",
  "При падении сайта сразу просит остановить рекламу (без GO) и пишет в эту задачу",
],
"86b6z79t1": [
  "Еженедельный сбор OFTV в mon-early (стоячий Clear): таблица Леши по моделям и комментарий в ClickUp, for check",
],
"86bb8ju09": [
  "Мониторит долг пакистанца через Аллу: 2 раза в будни в morning mega (WA UKR), скрины в ClickUp",
],
"86bcxprv8": [
  "По понедельникам в morning mega проверяет счётчики Tuya и пишет данные в таблицу; если офлайн — пишет Алексею без GO",
],
"86b8r59kx": [
  "Мониторит felix-shop.com (uptime, скорость, акции) и пишет еженедельный отчёт в ClickUp",
  "SEO-проверка скриптом /workspace/seo/check.py",
],
"86b92hrcp": [
  "Мониторит palmvapeshop.com (скорость, акции, CPA): weekly и follow-up в чат Palma, если средний cost выше $8",
  "SEO-проверка скриптом /workspace/seo/check.py",
],
"86b934b1v": [
  "Мониторит hookahshop.org: uptime, скорость, акции и бэкапы; отчёт в ClickUp всегда for check",
  "При критическом сбое — алерт в Hooka и стоп рекламы (связь с задачей запуска рекламы)",
],
"86b8gv8kj": [
  "Мониторит tabakevich.co через AdsPower Ukraine: скорость с укр/загран IP, GSC, акции; отчёт for check",
  "SEO-проверка скриптом /workspace/seo/check.py",
],
"86b6q8m9x": [
  "Помощник проверяет почту Cosmo/Slash и пишет в ClickUp; после каждой проверки due ставит на сегодня",
  "При необходимости сопровождает переписку The Jerz Group в WA ESP",
],
"86bae6v4h": [
  "Ежедневно проверяет, отвечает ли Сара на комментарии IG/TikTok, пингует при необходимости и пишет отчёт в эту задачу (for check)",
],
"86ba3bwhg": [
  "В morning mega: в понедельник пинг Андрея по электричеству/сигналке Topacio, во вт и чт читает переписку; если нужен Rost — for check",
],
"86b88jb1f": [
  "Мониторит статус выселения окупасов Alicante через Диму (от Ольги); скрины WA кладёт в ClickUp",
],
"86bbjyrf5": [
  "Каждый утренний bundle: проверка входящих Clips4Sale (2 раза в день) и ManyVids (1 раз в будни) по KB clips4sale-manyvids, комментарий в эту задачу",
],
"86bcgckxu": [
  "На каждом bundle (пн/вт/чт mega, ср early, вс lite) проверяет кроны 1С по протоколу tbk-1c-reports, сначала через OData API",
  "Новые ошибки — комментарий в ClickUp и эскалация Agent699",
],
"86bcn2ek8": [
  "В будни сверяет состояние профилей LolaPop по скринам Мишель (пн/ср/пт) и пишет отчёт в эту задачу, статус for check",
],
"86bcnp3rg": [
  "Ночью и утром собирает статистику рекламы pesosaludable и ведёт таблицу «отчет-таргет по дням»",
  "Проверяет, что объявления живые, сигналит, если нужно менять; в ночь на понедельник закрывает недельную сводку в ClickUp",
],
"86bcnuxbj": [
  "Ежедневно около 09:00 в дни 5–13: смотрит счёт Никиты в TG, пересылает Яне на «вы» и двигает due / for check (платит Rost)",
],
"86bamxnh9": [
  "По воскресеньям около 06:00 Богота снимает статистику Mileroticos и новые города (Кали / Чоко), итог в формате «Итого: N WhatsApp (+Δ)», for check",
],
"86bcnuxbv": [
  "Ежедневно около 09:00 в дни 15–20: счёт от Лёши за чаттеров Sofia Lunara пересылает Яне на «вы» и двигает due / for check",
],
"86b9wh8cd": [
  "Еженедельно сверяет 05services и TG @wakeupnotears по RA180/RA185, скрины и комментарий в ClickUp (for check)",
],
"86b6tvyc7": [
  "По понедельникам напоминает Диме о долге в TG и пишет сводку в ClickUp (for check)",
  "Каждый день читает чат (не больше 40 сообщений); пруфы кладёт только в эту задачу",
],
"86b6k34a6": [
  "Мониторит старт ремонта Локаль с Анатолием в группе «Ростислав - Анатолий ремонты» и отчитывается в ClickUp",
],
"86b9uqgqq": [
  "В morning mega и wed early читает TG-тему «Ava» и пишет RU-digest в эту задачу (for check); ES-пинг Sara/Michelle только по Clear/GO",
],
"86b7k7v1n": [
  "Ежемесячно после 17-го ждёт SEO-отчёт Andrii по tabakevich, при необходимости пингует в TG SEO и пишет комментарий в ClickUp",
],
"86b9zkaua": [
  "Ежемесячно контролирует SEO-аудит штатного SEO (hookahshop / palmvapeshop / felix-shop) и ждёт отчёт в эту задачу",
],
"86bb3qh0k": [
  "Раз в две недели пингует Michelle по расписанию постинга OFTV, обновляет даты окончаний и пишет RU-digest в эту задачу",
],
}


RUTINA = re.compile(r'Рутина:\s*', re.I)


def _pretty_sched(s):
    s = (s or '').replace('`', '').strip()
    m = re.search(r'CRON_TZ=\S+\s+(\d+)\s+(\d+)\s+\*\s+\*\s+(\S+)', s)
    if m:
        minute, hour, dow = m.groups()
        days = {'0': 'вс', '1': 'пн', '2': 'вт', '3': 'ср', '4': 'чт', '5': 'пт', '6': 'сб',
                '1-4': 'пн–чт', '1-5': 'пн–пт', '0,6': 'сб,вс'}
        return '%s %s:%02d' % (days.get(dow, dow), hour, int(minute))
    return s


def _norm_bullets(xs):
    out, seen = [], set()
    for x in xs or []:
        s = (x.get('text') if isinstance(x, dict) else x) or ''
        s = ' '.join(str(s).replace('`', '').split())
        s = re.sub(r'CRON_TZ=\S+\s+(\d+)\s+(\d+)\s+\*\s+\*\s+(\S+)',
                   lambda m: _pretty_sched(m.group(0)), s)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _routines_by_task():
    by = {}
    for name, fn, mode in BOTS:
        rows, _upd = parse_inventory(fn, mode)
        for r in rows or []:
            blob = ' '.join(filter(None, [r.get('name'), r.get('sched'), r.get('note'), r.get('folder')]))
            ids = set(CUID_RX.findall(blob))
            if not ids:
                continue
            sched = (r.get('sched') or '').strip() or 'без расписания'
            line = 'Рутина: %s — %s' % ((r.get('name') or '').strip() or 'без имени', sched)
            for i in ids:
                by.setdefault(i, []).append(line)
    # inventory / calendar prose that mentions a CU id in a table row
    extra_roots = [
        os.path.join(INV, 'CALENDAR.md'),
        os.path.join(INV, 'ROUTINE-GROUPS.md'),
        os.path.join(INV, 'COMMS.md'),
        os.path.join(INV, 'HELPER.md'),
        os.path.join(INV, 'OF.md'),
        os.path.join(INV, 'PEPTIDE.md'),
        '/home/box/contacts/knowledge/bot-routines-inventory/ROUTINE-GROUPS.md',
        '/home/box/contacts/knowledge/process-templates/ROUTINE_TEMPLATES.md',
    ]
    for path in extra_roots:
        try:
            text = open(path, encoding='utf-8').read()
        except Exception:
            continue
        for raw in text.splitlines():
            ids = CUID_RX.findall(raw)
            if not ids:
                continue
            if '|' not in raw:
                continue
            cells = [c.strip().replace('**', '') for c in raw.strip().strip('|').split('|')]
            if len(cells) < 2:
                continue
            # skip header-ish
            if cells[0].lower() in ('задача', 'task', 'name', 'routine', 'рутина'):
                continue
            title = cells[0]
            sched = ''
            for c in cells[1:]:
                if re.search(r'\d{1,2}:\d{2}|cron|mega|lite|daily|weekly|пн|вт|ср|чт|пт|сб|вс|mon|tue|wed|sun|daily|weekday', c, re.I):
                    sched = c
                    break
            if not title or title.startswith('http') or len(title) > 80:
                continue
            if title.lower().startswith('cu ') or title.startswith('86b'):
                continue
            line = 'Рутина: %s — %s' % (title, sched or 'без расписания')
            for i in ids:
                # don't pile calendar noise if we already have a real inventory routine
                by.setdefault(i, []).append(line)
    return {k: _norm_bullets(v) for k, v in by.items()}


def _ros_ids():
    try:
        d = json.load(open(os.path.join(HERE, 'ma_ros_bot.json'), encoding='utf-8'))
    except Exception:
        return []
    tasks = d.get('tasks') if isinstance(d, dict) else d
    return [t['id'] for t in (tasks or []) if t.get('id')]


def build():
    rmap = _routines_by_task()
    ids = _ros_ids()
    tasks = {}
    missing = []
    for tid in ids:
        bullets = _norm_bullets(list(rmap.get(tid) or []) + list(CURATED.get(tid) or []))
        if bullets:
            tasks[tid] = bullets
        else:
            missing.append(tid)
    return dict(
        generated=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        tz='America/Bogota',
        src='bot-routines-inventory + ROUTINE-GROUPS/CALENDAR + knowledge KB READMEs + queue scripts; not ClickUp descriptions',
        tasks=tasks,
        missing=missing,
    )


if __name__ == '__main__':
    d = build()
    out = os.path.join(HERE, 'bot_task_work.json')
    json.dump(d, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n = len(d['tasks'])
    print('wrote', out, 'with_bullets', n, 'missing', len(d['missing']), d['missing'])
    for tid, xs in d['tasks'].items():
        print(tid, len(xs))
        for x in xs:
            print('  -', x[:160])
