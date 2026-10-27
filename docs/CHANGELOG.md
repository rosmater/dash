## 27.10.2026 ~12:50 Bogotá — Мессенджеры: без подписи; sync тапов даша → contacts
- Rost t3904u: убрана подпись под заголовком Мессенджеров («По сферам · канал · … тексты сообщений не читаются…») и нижняя заметка «Только метаданные…». `maHead(d,extra,bare)` — bare=true без строки.
- Rost t3902–t3903: `src/sync_dash_taps.py`. Вход: `sync/inbox/*.json` `{spheres:[{key,channel,title,sphere}], ignores:[{id,channel,title,kind,perm,ignored_at|null}]}` (экспорт из браузера / будущий webhook). Делает: chats.csv.direction (title+channel, иначе новая строка), src/ignored_chats.json (дедуп по id, ignored_at=null → вернуть), бэкапы .bak-sync, build_test_ma.sh + build.sh + push, файлы → `sync/done/`. Запускать из вочера/утренней меги, когда в inbox есть файлы (`--no-push` для сухого прогона).

## 27.10.2026 ~12:50 Bogotá — Мессенджеры: без подписи; sync тапов даша → contacts
- Rost t3904u: убрана подпись под заголовком Мессенджеров («По сферам · канал · … тексты сообщений не читаются…») и нижняя заметка «Только метаданные…». `maHead(d,extra,bare)` — bare=true без строки.
- Rost t3902–t3903: `src/sync_dash_taps.py`. Вход: `sync/inbox/*.json` `{spheres:[{key,channel,title,sphere}], ignores:[{id,channel,title,kind,perm,ignored_at|null}]}` (экспорт из браузера / будущий webhook). Делает: chats.csv.direction (title+channel, иначе новая строка), src/ignored_chats.json (дедуп по id, ignored_at=null → вернуть), бэкапы .bak-sync, build_test_ma.sh + build.sh + push, файлы → `sync/done/`. Запускать из вочера/утренней меги, когда в inbox есть файлы (`--no-push` для сухого прогона).

