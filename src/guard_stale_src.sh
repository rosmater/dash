#!/bin/bash
# t1111u (12.11): сборка из клона, где src/ отстал от origin/main, перетирала на сайте чужие правки
# (так пропала плашка «Пепт: Пополнить BC» — /workspace/dashboard-mockup не пуллился с 11.11 до 12.11 14:41).
# Перед сборкой: если src/ отстаёт — подтянуть (rebase + autostash); не вышло — сборку не делать.
cd "$(dirname "$0")/.."
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
timeout 20 git fetch -q origin main 2>/dev/null || { echo 'guard_stale_src: fetch не прошёл — пропускаю проверку'; exit 0; }
if [ -n "$(git rev-list -1 HEAD..origin/main -- src/ 2>/dev/null)" ]; then
  echo "guard_stale_src: src/ отстаёт от origin/main в $(pwd) — git pull --rebase --autostash"
  if ! git pull -q --rebase --autostash origin main; then
    git rebase --abort 2>/dev/null
    echo 'guard_stale_src FAIL: src/ отстаёт от origin/main, pull не прошёл — сначала git pull вручную (иначе сборка затрёт чужие правки на сайте)'
    exit 1
  fi
  exit 10
fi
exit 0
