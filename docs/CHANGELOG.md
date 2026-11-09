## 2026-11-09 t5824u follow-up: cu_due_sync + calendar all-day _seen fix
- New deterministic `src/cu_due_sync.py` (today→+2d merge into cu_cal_dash, cu_dated dues, surgical enc, pull --rebase push; exit 10 = noop).
- `build_data.py`: all-day gcal-sync titles no longer fill `_seen` — timed CU 86bc8fkbt (Алла / топят 10.11 21:00) returns to calendar.events.

## 2026-11-09 t5824u: CU calendar snapshot + cu_dated dues
- Rost moved CU 86b8rn9wf (С ИРИНОЙ: Подсчеты ОФ) to 10.11 (date-only) at 15:06 Bogotá; dash still showed today 21:00.
- Refreshed cu_cal_dash.json via clickup_filter_tasks → refresh_cu_cal_dash.py; surgical patch calendar.events + of.cu_dated (86b8rn9wf → 10.11; 86b9axevh → 16.11). No build.sh.

## 2026-11-09 t5825u — плашки исполнителя в Срок сегодня / Просрочено / Сегодня в календаре

- В списках «📅 Сегодня в календаре», «Срок сегодня» и «Просрочено» — цветные плашки исполнителя (как в ОФ «Своя модель»: Rost / Michelle / Sara / другие).
- Мои задачи (assignee Rost 60710247) поднимаются вверх списка; порядок остальных сохраняется.
- Google Calendar события без плашки, порядок по времени.
- Снимок `cu_tasks_dash.json` + `build_data.py` отдают `assignees`/`who`; calendar ClickUp — тоже.
- Общие хелперы `cuWhoNames` / `cuWhoHTML` / `cuRostFirst` (без дублей имён).

## 2026-11-09 ОФ: неделя 02–08.11 (OFTV + LolaPop) — ingest → surgical publish
- Цепочка t5713u: dated `src/oftv_history/02.11-08.11.2026.json` + `src/lolapop_history/02.11-08.11.2026.json` → `ingest_oftv_week.py` / `ingest_lolapop_week.py` → surgical patch только `of_blocks.oftv` + `of_blocks.lolapop` в data*.enc.json (без build.sh).
- OFTV Текущая 02–08.11 net $1754.40: Sofia 1482.40 / 1396, Kelly 42.40 / 1961, Bella 0 / 3773, Rosie 229.60 / 3407. Прошлая = 26.10–01.11, позапрошлая = 19–25.10.
- LolaPop OF net $65.97 (subs 30 + msgs 35.97); fans 62; subs_new 3; rebills 2. IG: lolabig.lolapop 26511/+32, lolapopstarted 26011/+95, lolastartjourney 9771/+3.
- MV/C4S за 02–08.11 → «—»: в of_blocks лежали 18.58/11.98 из dee9d712 (08.11 hand-fill) без dated capture; ОФ Маркетинг оставил manyvids_net/c4s_net null (кабинеты только в k1gxh3kk). Не выдумывали.
- Архив last_snapshot 01–15.10 ($173.28) ушёл в lolapop.prev/last. Порнстоки недели сохранены. Остальные направления не трогали.

## 2026-11-05 t5162 lite snaps DELETED
- Snaps only unread-dash-daily 09:00+13:00 Bogotá, plus on-demand «актуализируй мессенджеры» (writes *_live.json).
- Lite 11/15/17/19 removed from KB. Night 23:00–08:45: no snaps / no stale сбой.

## 2026-11-05 t5158 messengers-tab polish + published check
- marked_unread → blue dot (not «0») via maUnreadChip; chats count, 0 msgs.
- 📦 версия данных HH:MM · commit on Мессенджеры; client reads published_status.json for CDN lag note.
- check_pages_live.py (≤12 min, --bg); night 23:00–08:45 no stale сбой; lite 11/15/17/19 write live (KB).

## 2026-11-05 t5156 full Мессенджеры-tab surface audit
- After t5154 sphere fix: audited monitor/list/spheres/unsorted/tab badge/attn/muted/dups/coverage.
- Fixes: maMonitor counts only live unread|marked for WA/TG/Vib/IG (no watcher.unread inflate); maCov copy → live json; strip muted from unsorted; reconcile `surfaces.*` + tests.
- All 5 channels surfaces ok; Miguel/Alnago stay dropped.

## 2026-11-05 t5154 sphere blocks = live
- Root cause: per-dialog сверка покрывала monitor+list, но не блоки сфер; `base-loft-rental-search.md` держал Miguel Calipso / Alnago (ждём, unread 0) в Личном; enforce оставлял `_is_wait` вне live.
- Fix: drop wait-only not in live; promote live-from-📥 into sphere; reconcile + tests 4-way live=list=monitor=spheres (`sphere_chats`/`sphere_sum`).
- WA ESP after: Личное Nutibara/JOHANN/Porteria; Дейтинг 7 numbers; Недвижимость Алла+Ирина; ОФ Sara+Julian = 14/25. Miguel/Alnago removed.

## 2026-11-05 t5149/t5150 TG list-only snap harden
- Root cause: during TG «Новые» сверка a left-click on the chat list opened Kir0[4K] and marked it read.
- Fix: `/home/box/bin/tg-novye-list-snap.sh` + `tg-list-scroll-safe.sh` (wheel click 4/5 only @ 280,400); `tg-open-novye.sh` parks pointer neutrally, rail-only fallback click; `tg-verify-empty-pane.py` before/after; `tg-count-list-badges.py` badge_drop flag; `accidental_open` in `tg_novye_snap_meta.json`; lock always released.
- Proof 16:49 Bogotá: empty pane before/after, badges 11→11, accidental_open=null, shot `tg-novye-listonly-proof-20261105-164915.png`.
- KB: `sverka-fresh-snap-every-run.md`, `tg-dedicated-xvfb.md` (both copies).

# 2026-11-04 t4924–25 — ✓ CU for check UX

- 2026-11-04 10:27 Bogotá: Мессенджеры — фикс парсера secretary-log ISO (с 30.10 тосты не попадали в вкладку). test_ma_build принимает оба формата времени.

- **Баг:** ✓ на 📄 отчёте (Табакевич БЛОКИРОВКА) → только toast, пункт оставался; «На проверке» как у вопросов не появлялось.
- **Причины:** (1) local hide только по тексту имени — без fallback по `cu` id; (2) cuDone писал в atLS, но не в oq → не было в «☑ На проверке» у бота; (3) снимок ma_clickup устарел после drain (задача уже to do в CU).
- **Фикс:** botTHid + match by `e.cu===t.id`; cuDone → oq `cu-<id>` в «На проверке»; ma_clickup drop drained; rebuild+push.

# 2026-11-03 t4800 — убрана серая подпись под «Отчёты ClickUp» (need=ok / 📄/🙋) — хватает title при hover.

# 2026-11-03 t4797 — ✓ CU for check (`cu_ok`)

- **Баг:** ✓ на «📄 Отчёты ClickUp» только писал `action:cu_ok` в тапы; `sync_dash_taps` его игнорировал; в UI `botTHid` не фильтровал reports → после тапа пункт оставался.
- **Фикс:** `RP` тоже через `!botTHid`; `cu_ok` → `cu_actions_pending` (kind for_check); COMMS: status `to do` + due завтра (не complete навсегда для мониторов).
- Задача шагов `86bcn3c3u`: for check снято, due → завтра 21:55 Bogotá (вебхук 03.11=1068 ок).

## 2026-11-02 · t4595-97 «🙈 Скрытые» = пустые разделы (0) + жёлтое «есть отчёт»

- Rost t4595u: в «🙈 Скрытые» у каждого бота теперь все пустые фикс-разделы с (0): Рутина упала, Ожидает ответа, Задачи CU for check, Отчёты CU for check, Есть отчёт, Ждём других, Рутины · ок, Задачи в очереди, На проверке (+ скрытые тапом упавшие рутины). Счётчик = пустые + скрытые тапом. Динамические группы (супер мозг и т.п.) не выдумываем.
- Rost t4596–97u: фраза «Есть отчёт» / «Отчёты ClickUp» — жёлтым (#a16207, класс .rpY), и в видимых папках, и в строках (0) внутри «Скрытые».
- Правка src/variant-a.html (бэкап variant-a.html.bak-t4595-hidden0) → index/variant-a/helper.

## 2026-10-28 · t4395-97 keepOpen на OK/refresh у открыть чат

- Rost: галочка/обновить рядом с открыть чат схлопывали раскрытый список бота на вкладке Ассистенты.
- maDone/maRef/maUndo и atDone/atRef/atUndo теперь через keepOpen(render) (как уже было у rtDone/rtRef) — раскрытые details и скролл сохраняются.
- Правка в index.html / variant-a.html / helper.html (+ src/variant-a.html). Live: 3350bee.

## 28.10 ~09:55 Bogotá — Мессенджеры: превью «последние пойманные» только на значке 🗨 (Rost t4383u)
- Было: поповер last_msgs открывался при наведении на всю строку (`mouseover` → `summary.hlm`). Стало (`src/variant-a.html`): только при наведении/фокусе на значок `.lmi` 🗨 (строки мессенджеров и ClickUp — общий `maRowHTML`); поповер якорится к значку, значок крупнее + подсветка при hover. Мобила без изменений (превью в раскрытии).

## 28.10 ~09:55 Bogotá — Мессенджеры: сортировка → сфера сразу (Rost t4379–t4380 HARD)
- Баг 1 (клиент): тап сферы в «📥 на сортировку» только прятал чат («уже рассортировано, скрыты»), а в карточку сферы он попадал лишь после пересборки на box (relay ≤60 с + сборка + GitHub Pages ~1 мин + перезагрузка даша). Фикс `src/variant-a.html` `msgsTab`: пункты `d.unsorted` с локальной сферой (`dash_sph_<канал|чат>`) сразу вставляются строкой в выбранную сферу (`local_sort`), без ожидания box.
- Баг 2 (box): `src/sync_dash_taps.py` писал `chats.csv` через незакрытый хэндл → `build_test_ma.sh` сразу после читал недописанный файл (хвост = свежие сортировки), сборки от relay и ручные расходились (WA UKR 36↔15, Viber 13↔1 строк). Фикс: все записи через `with open`.
- Баг 3 (relay): ntfy `since=<id>` возвращал соседнее сообщение той же секунды снова → пинг-понг «3/6 сфер» каждые 60 с (08:52–09:29, ~35 лишних сборок/пушей). Фикс `src/tap_relay.py`: дедуп по `st.seen` (300 id). Relay перезапущен.
- `src/test_ma_build.py`: строка, перенесённая тапом, не дублируется в «Без сообщений» той же сферы.

## 28.10 ~09:45 Bogotá — Мессенджеры: Viber live-список + бейдж, IG Direct раз в день (Rost t4368)
- Баг Viber: UIA-поллер при нечитаемом счётчике писал `unread=0` → 🟢; Viber-строки даша были только из статичного census 27.10 → новый непрочитанный «Стелла Киевстар» (4, 09:23) на даш не попал. Фикс: `viber-uia.ps1` считает красный бейдж на кнопке таскбара (`has_unread`, `badge_px`, n=null вместо 0); `src/viber_live.json` (снимок фильтра Unread, только метаданные) мержится в строки/нерассортированные в `test_ma_build.py`; вочер Viber 🟡 «бейдж непрочитанных…» при has_unread.
- IG Direct: `/workspace/mailbox-map/ig-direct/ig_direct_peek.py` (CDP браузера Секретаря, без превью) → `src/ig_direct_live.json` → строки канала Instagram (в сферу по имени, иначе 📥). Монитор/сверка/лейбл `IG` (`.ml-ig`) в `variant-a.html`. Раз в день внутри утренней мега / ночной гигиены, без отдельного запуска.
- Проверка: Playwright index ?data=data.json&tab=messengers — 0 ошибок; Vib 1 в сфере (4) + 📥 7 (4 с непроч.); IG 📥 2; guard ok.

## 28.10 ~09:10 Bogotá — Мессенджеры: hover-превью последних пойманных (Rost t4356)
- `src/test_ma_build.py`: строкам чатов (и нерассортированным) добавлено `last_msgs` [{at, who, text}] — ≤3 последних тоста из secretary-log, только чаты allowlist/log_only вочера, только цитата «…», ≤120 симв. `src/variant-a.html`: наведение на строку → поповер (#mlpop, fixed, не режется карточкой; клавиатура — focus), тап/раскрытие → «🗨 Последние пойманные» в теле; индикатор 🗨. Мессенджеры в чат Rost больше не дампим — правило `knowledge/rules/messengers-dash-not-chat.md`, вебхук WA — `notify-watchers/wa-*-secretary/ROUTINE-CHAT-POLICY.md`.

## 28.10 ~01:10 Bogotá — Мессенджеры: «отчеты» ПОД чатами + метка «📄 отчёт»; Defense «Tasks» → Оборонка; Помощник без Feabie/Tin (Rost t4322–29)
- `src/variant-a.html`: порядок в карточке сферы = чаты → `rfold` (ClickUp «отчеты (N)») → `wfold` (⏳ Ждём ответа) → ▸ Без сообщений. На строке «отчеты» — пилюля `📄 отчёт`.
- ❓ Прочее → Оборонка: `maCUMsgRows` матчит `MA_CU_SPH` по `space + list_id + list` (а не только имени листа); в регэксп Оборонки добавлено `defen[cs]e|901421054196|90148618420`.
- `src/cu_inbox_build.py`: тредам пишется `list_id`. `src/test_ma_build.py`: `list_id` добирается из inbox-raw (tasks-updated / tasks-<дата>), `space` по карте `_CU_SPACE` (`901421054196` → Defense Systems). 86bbzxnvx «БОТ-ЧАСТЬ: Рассылка…» теперь в 🛡️ Оборонка, карточки ❓ Прочее нет.
- `maMonitor`: при `DASH_HELPER` (helper.html, даш Помощника) каналы Feabie и Tinder скрыты из «📊 Монитор мессенджеров». Главный даш / Ассистенты — без изменений.
- Проверка: Chrome headless index.html и helper.html ?data=data.json&tab=messengers — 0 ошибок; порядок в сферах chats→отчеты→ждём→без; в helper монитор без Feabie/Tin.

## 28.10 ~01:15 Bogotá — Мессенджеры: сферы без сообщений вниз (Rost t4336) + цвета 📄/🙋 (t4335)
- `maGrid`: сферы с 0 сообщений (нет чатов и «отчетов», напр. 💉 Пептиды) раскладываются после всех сфер с чатами и получают order 1000+ → всегда в самом низу колонок (и на мобиле).
- t4337: в шапке «отчеты (N)» убрана дублирующая метка «📄 отчёт»; серая «📄 отчёт» осталась только на строках внутри.
- t4335 (коммит 5b965d7): 📄/🙋 на CU-строках снова цветные (filter:none, без grayscale).

## 28.10 ~01:20 Bogotá — Мессенджеры: «отчеты» вверх + как чаты (Rost t4320–21)
- `src/variant-a.html`: `rfold` → `details.mrow.cuokf` (mLBL ClickUp + «отчеты (N)» + mcnt новых), дети = `maCUMsgHTML` в `.mbody.cuokb`; в карточке сферы `rfold(g)+wfold(g)` перед чатами. CSS `.cuokb` (отступ, ▸ у свёрнутых вложенных).
- Проверка: Playwright index.html?data=data.json&tab=messengers — 0 ошибок; 4 сферы с отчётами (Недвижимость 1, Личное 1, Табакевич 4, ОФ 7): первый ребёнок карточки = «ClickUp отчеты (N)», второй = «⏳ Ждём ответа», затем чаты.

## 28.10 ~01:00 Bogotá — Шапка: тонкие разделители между кнопками (Rost t4318)
- Сегодня | Неделя | Месяц и Мессенджеры | Ассистенты · боты — мягкая серая вертикальная линия (#e2e5ea, :before), у активной кнопки скрыта. `src/variant-a.html` CSS.

## 28.10 ~00:55 Bogotá — Фикс: вкладка Пептиды «залипала» на ОФ/Оборонке (Rost t4316–17)
- Причина: глобальная `yDayLabel()` звала `dd()`, которого глобально нет (только локальные в других функциях) → ReferenceError в режиме «Сегодня» (pepMonHTML/ledger). controls() уже подсветил Пептиды, а #main оставался от прошлой вкладки.
- Фикс: локальный `dd` в yDayLabel; `render()` — try/catch вокруг отрисовки вкладки: при ошибке #main = карточка «⚠️ ошибка отрисовки», старый контент не висит. Прогон всех вкладок × сегодня/неделя/месяц — без ошибок.

## 28.10 ~00:55 Bogotá — Мессенджеры: CU БОТ 🙋 нужен я / 📄 Кликап отчёты (Rost t4312–15)
- `src/test_ma_build.py`: тредам cu_inbox добавлены `need` (из bot_attn.jsonl, по правилам for check; нет записи → rost) и `rev` (= updated задачи из ma_clickup, иначе at). Сейчас БОТ-тредов: 40 rost / 13 ok.
- `src/variant-a.html`: `maCUT/maCUOk/maCUAttn`; метка «🙋 нужен я» + 📄/🙋 на CU-строках БОТ; need=ok вынесены в `<details class="okfold cuokf">📄 Кликап отчёты (N)` внизу каждой сферы; в шапке сферы «📄 N отч.». Снимок: ОФ 7, Табакевич 4, Недвижимость 1, Личное 1.

## 28.10 ~00:10 Bogotá — Мессенджеры: ClickUp-теги живых людей + личка ClickUp (Rost t4264)
- Причина «не вижу»: снимок inbox-raw брал только задачи, назначенные на Rost (там пишут почти одни боты → «БОТ»). @Rost от Michelle/Sara в ИХ задачах, ответы в тредах и личка ClickUp Chat в даш не попадали.
- `src/cu_inbox_build.py`: подмешивает `inbox-raw/wide/` (задачи всего workspace по updated, комменты не-Rost задач, ответы в тредах, DM-метаданные). Строки «Личка: <имя>» (kind dm). Чужие задачи без коммента — не шум. ma_clickup (for check монитор) — как раньше, только задачи Rost.
- `src/variant-a.html`: метка «личка». Снимок 27.10 23:58.

## 27.10 ~23:05 Bogotá — Календарь: каркас ЖИВОГО Google Calendar (OAuth в браузере) + свежий снимок (Rost т251, CU 86bctqe8h, t4199)
- Снимок GCal обновлён (был застывший от 25.10 → 23:00 27.10, 168 событий 27.10–10.11). Новый скрипт `src/refresh_gcal_dash.py`: ответ коннектора list_events (файл/stdin) → `/workspace/gcal_dash.json` в прежней форме; пустой вход снимок не затирает.
- «Общий · Сегодня» / «📅 Календарь»: при наличии Client ID грузится Google Identity Services, кнопка «Войти в Google» → токен (только sessionStorage, readonly) → Calendar API events.list на 15 дней → события Google заменяют снимок, ClickUp-сторона и привязки 🔗 CU сохраняются; подпись «live GCal · обновлено ЧЧ:ММ»; автообновление каждые 5 мин при открытой вкладке; при live нет предупреждения «снимок старый».
- Нет Client ID / не вошёл / ошибка → всё как раньше (снимок). Client ID пока НЕ задан (ждём от Rost): `GCAL_CLIENT_ID` в src/variant-a.html или разово `?gcal_client_id=…`. helper.html — без календаря, live выключен.

## 27.10 ~18:36 Bogotá — Notion-дубль у Секретаря: убрать «Notion» из «Ожидает ответа» (Rost t4100/t4103)
- После t4097 сводная строка ушла, но красный пункт «Notion-инструкции Tabakevich…» оставался в «🙋 Ожидает ответа» рядом с «🔴 🧠 Notion · супер мозг» — выглядело как тот же дубль.
- Переименован в «Tabakevich · GDrive: 10 файлов — жду Ирину…» (st=red, без grp). Блок супер мозга один. `src/test_ma_build.py`.

## 27.10 ~18:45 Bogotá — Ассистенты·боты: Notion «супер мозг» больше не дублируется в «🙋 Ожидает ответа» (Rost t4097u)
- Убрана сводная красная строка «Notion / «супер мозг»: 22 неразобранных вопросов…» из «🙋 Ожидает ответа» Секретаря — остался только блок «🔴 🧠 Notion · супер мозг — я нужен (22)». Блок сам 🔴 и считается в «Требует внимания» 1 раз (revGroups). Вопрос Tabakevich (10 файлов, жду Ирину) — без grp, остаётся в «Ожидает ответа». `src/test_ma_build.py`, бэкап .bak-t4097.

## 27.10 ~18:35 Bogotá — Ассистенты·боты: «открыть чат ↗» в строку заголовка бота, пробел убран (Rost t4094u)
- Ссылка «открыть чат ↗» была отдельной строкой (text-align:right) в начале тела карточки → большой пробел между «Секретарь» и «🙋 Ожидает ответа». Теперь она в строке заголовка справа (`a.bchat`, margin-left:auto, клик не сворачивает карточку); заголовок бота (`summary.bsum`) переносится на телефоне, чтобы ссылка не уезжала за край. Для всех ботов. Бэкап: src/variant-a.html.bak-t4094.

## 27.10 ~16:45 Bogotá — Мессенджеры: короткие значки, «(N дн.)», теги по тапу (Личное + Дейтинг), Base Loft, плотнее; Оборонка: «ответить»/«ждём» всегда видны (Rost t4004u–t4010u)
- Значки каналов: TG · WP UKR · WP ESP · Vib · Tin · Feabie (полное имя в подсказке). `mSHORT()` в src/variant-a.html.
- «(N дн.)» у каждой висящей строки (непрочитано / наш ход / ждём, + нерассортированные): `hang_since` пишет test_ma_build → `src/hang_since.json` (канал|чат → YYYY-MM-DD Богота; первый раз увидели висящим = min(дата последнего сообщения, известная дата) или сегодня; перестал висеть → ключ удаляется). Дни даш считает от сегодняшней даты Боготы — растут сами; ежедневная пересборка (рутина) поддерживает базу.
- Теги: цветная плашка = тап → выбрать другой/снять; нет тега → «#» → прикрепить (всплывашка). «тег:» в раскрытой строке убран. Дейтинг: новая · новия · скаут · резерв · архив (свои цвета; порядок новая → новия → скаут → без тега → резерв → архив). Хранение прежнее (dash_rtag_ + тап → msg_row_overrides.json).
- Личное · Base Loft (CU 86bcma7tp, тег задача): ⏳ ждём Víctor (Nutibara 1105, наше 26.10 15:41), ⏳ ждём Miguel Calipso (запрос 18.10, ответа нет); ⏳ ждём Nini Loaiza (Alnago; её 27.10 08:51 — нужен deudor; новых нет → в «Ждём ответа», t4010); Leidy Base Loft ОФ → Личное. Портерия — доставки, не аренда, не добавлена.
- Плотнее строки в сферах (mrow 9→4 px, подсписки 6→2 px).
- Оборонка: тайл «Ответили» без списка компаний (только «✍️ ответить: N · ⏳ ждём ответа: N · +автоответы»); блоки «✍️ Ответить компаниям» и «⏳ Ждём ответа компаний» видны всегда (раньше «разобрать» исчезал при 0 — после Dronamex → waiting 16:13), ждём — раскрыт; жёлтый приглушён до мягкого янтаря.
- t4008: Ассистенты·боты — группа «🧠 Notion · супер мозг» (и любой «на разборе») = 🔴 красная у каждого бота-владельца (Секретарь, Помощник по всему), считается в «Требует внимания» и в статусе карточки, не «ок». `REV_RX`/`revGroups()`.
- t4009: пункты под заголовками списков (Есть отчёт, Ждём других, Требует внимания…) — чёрный шрифт вместо зелёного, отступы 6→3 px.
- t4010/t4011: заголовок «⏳ Ждём ответа» (большая Ж) во всех блоках = МЫ ждём их ответа; плашка «ждёт» в строке оставлена = контакт ждёт НАШЕГО ответа. Nini (Alnago) без новых непрочитанных → «Ждём ответа».

## 27.10 ~15:00 Bogotá — Мессенджеры: ✓/✕ у каждого диалога, иконка CU, теги Личного; кнопки у «Рутина упала»; вопросы без карточек (Rost t3969u–t3974u)
- Каждая строка диалога (сферы, ⏳ ждём, без сообщений): **✓** «ответил» / **✕** «прочитал — можно не отвечать» (подсказки при наведении), вплотную к кружку непрочитанных. Отмеченная строка бледнее, вниз, не считается в бейдже; отметка снимается сама, если после неё пришло новое сообщение. Прежний серый ✕ «на сортировку» → **↩**.
- Привязанная задача ClickUp — маленькая иконка **CU** (наведение = полное имя задачи, клик = app.clickup.com/t/<id>), рядом ✕ = открепить. Нет привязки → **🔗** «связать с ClickUp» = чат Секретаря (текст в буфер).
- Личное: теги друг | быт | семья | задача (в строке — выбранные, в раскрытой строке — тап-переключатели).
- Хранение: localStorage сразу + тап (шифр → ntfy → tap_relay → sync_dash_taps) → `src/msg_row_overrides.json` (state / cu / tags / rt_ack) → test_ma_build. Автопривязки 16 строк (оптика CLÍNICA VISUAL ↔ 86bcm9u4k очки; Leidy/Portería/Base Loft ↔ 86bcma7tp переезд/лофт; Алла агентство ↔ 86bb8ju09 и др.), теги семья/быт — авто, src:auto.
- «🔴 Рутина упала — я нужен» (в боте и верхний блок): те же кнопки, что у «🙋 Ожидает ответа» — 💬 открыть чат (текст в поле ввода) · ✓ решено (скрыть на 6 ч, на проверку боту) · ↻ обновить.
- Ассистенты (t3992u): статус бота — 🔴 только при 🙋 вопросах/упавших рутинах, 🔵 «В работе» только при реальной задаче in progress/«чинит» в очереди, иначе 🟢 всё ок (отчёты, for check, «ждём других» не держат 🔵). Юрист: вопрос Милы (Olivino 3) → «Ждём других» (ждём Милу, не Rost) → 🟢.
- Ассистенты (t3990–91): все подсписки бота (есть отчёт, ждём других, рутины · ок, задачи в очереди, ClickUp for check, на проверке) — один стиль с «🙋 Ожидает ответа»: «– текст», тонкая линия, отступ вправо.
- Ассистенты (t3986u–t3988u): упавшая рутина, которую бот уже чинит (в открытой задаче QUEUE.md бота есть её folder-id/имя, или в инвентаре «fixing/чиню»), автоматически уходит из «🔴 Рутина упала / Требует внимания» в «📋 Задачи в очереди» (статус «чинит бот»); пустой «Рутина упала · 0» — строкой в сером «Скрыто». Бинотел → в очереди (COMMS чинит, QUEUE.md binotel-routine-fix).
- Ассистенты (t3989u): счётчик «🔴 Требует внимания · N» у бота = вопросы 🙋 + упавшие рутины (совпадает с видимыми пунктами).
- Мессенджеры (t3980–81): чат с непрочитанным больше не может быть в «⏳ ждём ответ» (флаг ожидания снимается при новом сообщении); после ✓/✕ строка уходит из активной очереди и счётчиков (в «без сообщений», бледная).
- Мессенджеры (t3979u): длинные имена контактов/чатов обрезаются многоточием, полное имя — в подсказке при наведении; строка не ломается.
- Личное (t3978u): теги разными цветами (друг зелёный · быт янтарный · семья розовый · задача синий); порядок строк: с задачей (тег или CU) → семья → друг → без тега → быт, внутри — непрочитанные выше.
- Личное (t3978u): теги разными цветами (друг зелёный · быт янтарный · семья розовый · задача синий); порядок строк: с задачей (тег или CU) → семья → друг → без тега → быт, внутри — непрочитанные выше.
- Ассистенты (t3976u): «🔴 Рутина упала» и «🙋 Ожидает ответа» — один дизайн списка («– текст», тонкая линия, кнопки по тапу); пункты внутри групп с отступом вправо.
- Мессенджеры (t3977u): чип бота «💬 Секретарь ↗» → только 💬, имя бота в подсказке при наведении (для всех ботов).
- Личное (t3975u): после выбора тега чипы скрываются, остаётся маленький выпадающий список «тег: … ▾» (сменить или снять).
- «Требует внимания» и вопросы ботов — не карточки: список «– текст» с тонкой бледной линией между пунктами; кнопки по тапу как раньше.

## 27.10 ~14:55 Bogotá — Мессенджеры: «Быт» (и старые Прочее/Dating/Юр/Финансы) слиты в Личное/Дейтинг, отдельной сферы нет (Rost t3968u)

## 27.10 ~14:50 Bogotá — «📥 Непрочитанные · нерассортированные» свёрнуто по умолчанию (Rost t3967u)

## 27.10 ~14:50 Bogotá — Ассистенты · боты: 🔴 упала/требует внимания сверху, 🔵 в работе, ⚪ нет данных, 🟢 всё ок внизу (Rost t3966u)

## 27.10 ~14:45 Bogotá — тап = сразу разнесено; ДР в шапке; ✕ и «ЧАТ:» в мессенджерах (Rost t3955u, t3956–62u)
- CU «на сортировку»: тап направления → задача сразу пропадает из списка и видна во вкладке направления (↩ вернуть); гармошка не сворачивается. Тапы шифром (ключ даша) → ntfy.sh → box `src/tap_relay.py` → `sync_dash_taps.py` → `src/cu_dir_overrides.json` / `src/msg_sphere_overrides.json` / chats.csv → пересборка + пуш.
- ДР в шапке под заголовком только если ДР сегодня или просрочен; «🎉 поздравил» → `sync/cu_actions_pending.json` (закрывает рутина COMMS через ClickUp).
- Мессенджеры: непрочитанные наверх в каждой сфере; серый ✕ на каждой строке → обратно «на сортировку»; групповые чаты «ЧАТ: …»; Maks Sinar → Недвижимость.

## 27.10 — Кнопка выхода: только 🔒 без надписи; рядом ↻ «Обновить» (reload с ?v=now, мимо кеша); авто-сброс кеша: no-cache meta + проверка свежего HTML (no-store) каждые 2 мин и при возврате на вкладку — при любом деплое страница перезагружается сама; data.enc.json уже no-store (Rost t3915u)

## 27.10 — CU на сортировку: на каждой задаче тап-чипы направления (те же сферы, что у мессенджеров; localStorage `dash_sph_cu|<id>`) — источник для разнесения по вкладкам (Rost t3914u)

## 27.10 — CU на сортировку: в «Требует внимания» только «🗂 ClickUp — на сортировку · N» (1 строка), список — свёрнутый блок внизу «Общего» (Rost t3913u)

## 27.10.2026 ~13:00 Bogotá — Повторные: ложный attn Juliana снят (Rost t3909u)
- Michelle ответила 26.10 17:38 в треде (reply 90140273696565: «ведёт Seider») — `repeat_tracking.json` не обновили → `no_sara_feedback` в «Требует внимания» ~сутки. Теперь `sara_replied`, исполнитель Seider. STANDING: ответы читать `get_threaded_comments`, в тот же ход JSON → build → push.

## 27.10.2026 ~12:50 Bogotá — Пептиды: «💬 Диалогов сегодня» компактно (Rost t3908u)
- Вместо 4 высоких KPI-карточек — таблица 2×2: строки «Сегодня» / «Новых <вчера>», колонки WA / IG; в ячейке число + мелкая подпись (WA: первое–последнее, IG: новых N). Пояснения — в title-подсказках.
- Чипы статуса: «WA ● вотчер», «IG ● снимок/live» (зелёные) или жёлтые при проблеме; «тихо >2 ч» только если тихо.
- Убрана простыня под карточками (определения WA/IG, «всего/новых вчера WA+IG (без IG)», «WA обновлено…», «Instagram: Уникальные люди…»). Осталась 1 серая строка: «Всего N · обновлено WA hh:mm · IG hh:mm» + «Прошлые дни WA» (до 3 дней). Привязка данных прежняя (d.dialogs_today).

## 27.10.2026 ~12:55 Bogotá — Мессенджеры: убраны обе нижние заметки (Rost t3905u)
- Удалены «Источник: непрочитанные чаты вочеров…» (под Нерассортированными) и «Только метаданные… Серый счётчик…» (низ вкладки). Замены нет.

## 27.10.2026 ~12:50 Bogotá — Мессенджеры: без подписи; sync тапов даша → contacts
- Rost t3904u: убрана подпись под заголовком Мессенджеров («По сферам · канал · … тексты сообщений не читаются…») и нижняя заметка «Только метаданные…». `maHead(d,extra,bare)` — bare=true без строки.
- Rost t3902–t3903: `src/sync_dash_taps.py`. Вход: `sync/inbox/*.json` `{spheres:[{key,channel,title,sphere}], ignores:[{id,channel,title,kind,perm,ignored_at|null}]}` (экспорт из браузера / будущий webhook). Делает: chats.csv.direction (title+channel, иначе новая строка), src/ignored_chats.json (дедуп по id, ignored_at=null → вернуть), бэкапы .bak-sync, build_test_ma.sh + build.sh + push, файлы → `sync/done/`. Запускать из вочера/утренней меги, когда в inbox есть файлы (`--no-push` для сухого прогона).

## 27.10.2026 ~12:50 Bogotá — Мессенджеры: без подписи; sync тапов даша → contacts
- Rost t3904u: убрана подпись под заголовком Мессенджеров («По сферам · канал · … тексты сообщений не читаются…») и нижняя заметка «Только метаданные…». `maHead(d,extra,bare)` — bare=true без строки.
- Rost t3902–t3903: `src/sync_dash_taps.py`. Вход: `sync/inbox/*.json` `{spheres:[{key,channel,title,sphere}], ignores:[{id,channel,title,kind,perm,ignored_at|null}]}` (экспорт из браузера / будущий webhook). Делает: chats.csv.direction (title+channel, иначе новая строка), src/ignored_chats.json (дедуп по id, ignored_at=null → вернуть), бэкапы .bak-sync, build_test_ma.sh + build.sh + push, файлы → `sync/done/`. Запускать из вочера/утренней меги, когда в inbox есть файлы (`--no-push` для сухого прогона).

- 27.10 t4153–55: Мессенджеры → блок «ClickUp · инбокс» (Комменты / @ / Назначили / for check / Прочее), у строки 💬 коммент + 📋 задача; данные src/ma_cu_inbox.json ← src/cu_inbox_build.py ← clickup-pulse/inbox-raw (MCP tier 2).
- 27.10 t4165–67: ClickUp-инбокс больше НЕ отдельный блок — каждая задача с CU-комментами = строка-«чат» в своей сфере Мессенджеров (счётчик = новых комментов, @ = тегнули, 💬 коммент + 📋 задача); без новых комментов → «Без сообщений». Монитор/вкладка ботов и инбокс — один снимок (ma_clickup.json пишется cu_inbox_build.py из того же inbox-raw).
- 27.10 t4168: Ассистенты · боты — шапка «🔴 Требует внимания · N» = сумма по ВСЕМ ботам как в их карточках (🙋 встало + 🔴 на разборе + 🔴 ClickUp for check need≠ok); считается в браузере из данных при каждой сборке/↻ (было 2 → стало 24 = Секретарь 15 + Помощник 3 + ОФ 5 + Юрист 1). Упавшие рутины — свой блок «🔴 Рутина упала».

## 27.10 ~22:50 Bogotá — ClickUp снова в Мессенджерах + лог кто трогал даш (Rost t4195–96)
- Причина пропажи: `test_ma_build.py` не клал `ma_cu_inbox.json` в `data.cu_inbox` → `maCUMsgRows()` пустой. Не Пептид (он чинил только CV на своей вкладке).
- Фикс: грузим `cu_inbox` при сборке. Лог правок: `sync/dash_touch.jsonl` + `src/dash_touch_append.py` + правило `knowledge/rules/dash-touch-log.md` (все боты).

## 27.10 ~22:55 Bogotá — аудит «что ещё выпало как ClickUp» (Rost t4197)
- Корень: `test_ma_build.py` был пересобран со старой базы (~до t4142) → кроме `cu_inbox` выпал wire `sync/bot_attn.jsonl` (t4142–46): `task.need`, `b.reports`, `data.bot_attn`, `clickup.tasks[].need/bot`, правило 🟡 без CU (t4149–51) и статус по need=rost (t4136). Итог был: все 35 CU for check = 🔴 «я нужен», 13 «ок/отчёт» от ботов игнорились. Вернул блок из `.bak-t4169`.
- Баг t4184 (Viber heartbeat): `from datetime import datetime as _dt` затирал модуль `_dt` → `age()` падал → ClickUp-вочер вечно 🟡. Переименовал в `_dtc`.

## 27.10 ~23:45 Bogotá — Мессенджеры: автор строки + БОТ вниз (Rost t4212)
- В каждой строке — кто написал/тегнул: живой человек → серая плашка с именем; бот (аккаунт Rost, от которого пишут боты / задача «БОТ…» / запись в `sync/bot_attn.jsonl`) → плашка «БОТ» (в подсказке — какой бот). Обычные TG/WA — отправитель как был; бот-отправитель («БОТ…», TG-юзернейм …bot) тоже «БОТ».
- Сортировка в каждой сфере: живые люди → чаты (ЧАТ:) → все БОТ-строки в самом низу (в т.ч. «Ждём ответа» / «Без сообщений»).
- Данные: `cu_inbox_build.py` пишет `threads[].author/author_bot` (последний не-Rost комментатор в окне = человек); `test_ma_build.py` — общие правила без хардкодов задач (+ `author_botname` из bot_attn); UI `maWho()/maBotR()` в `variant-a.html`.
- 28.10 Rost t4333: в раскрытом «отчеты (N)» каждая CU-строка получила серую метку «📄 отчёт» (maCUMsgHTML(r,1)); метка в заголовке fold осталась.

## 2026-11-04 10:33 Bogotá — t4989 messengers auto-clear stale
- Census 27.10: unread=0 at source (placement only); live unread from log/viber/ig/reconcile
- Drop hardcoded Dating INBOX 26.10, El Pulpo pending, Travertino/IKEA pending
- Rebuild auto-clear: rst ans/skip + stale census; hang_since skips done; no Feabie/Tinder carry-forward of «наш ход»
- Rule: knowledge/rules/messengers-auto-clear-stale.md
- Актуализация unread↔dash: routine unread-dash-daily 2×/day ~09:00+13:00 Bogotá

## 2026-11-05 t5094u
- Ассистенты·боты: пустой статус рутин («активных рутин нет» / нет дампа) → только в 🙈 Скрытые, не строкой в карточке.

## 2026-11-05 t5167 dash-dup-render-fix
- **2026-11-05 t5167u:** dash-dup-render-fix — `## [slug]` detail headers no longer render as queue items; ma_q question + QUEUE/waiting item on same topic (slug/CU id/QID/title overlap) render once (question kept, reds untouched); tolerant routines parser (`## Enabled` / `## LIVE enabled` / latest `## Inventory refresh*` / plain table; PEPTIDE/PEPTID, FARM/FERMOVOD); inventory >48h → ⚪ «инвентарь от DD.MM». Rule: rules/daily-dash-hygiene.md.
