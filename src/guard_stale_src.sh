#!/bin/bash
# t1111u (12.11): сборка из клона, где src/ отстал от origin/main, перетирала на сайте чужие правки
# (так пропала плашка «Пепт: Пополнить BC» — /workspace/dashboard-mockup не пуллился с 11.11 до 12.11 14:41).
# Перед сборкой: если src/ отстаёт — подтянуть (rebase + autostash); не вышло — сборку не делать.
cd "$(dirname "$0")/.."
git rev-parse --git-dir >/dev/null 2>&1 || { echo 'guard_stale_src FAIL: не git-репо — даш собирается только в /workspace/dash-gh'; exit 1; }
# t6157u (12.11): собирать можно ТОЛЬКО в каноническом репо /workspace/dash-gh с origin rosmater/dash
_top=$(realpath "$(git rev-parse --show-toplevel)"); _url=$(git remote get-url origin 2>/dev/null)
if [ "$_top" != "$(realpath /workspace/dash-gh)" ] || [[ "$_url" != *rosmater/dash* ]]; then
  echo "guard_stale_src FAIL: репо $_top ($_url) — не /workspace/dash-gh (rosmater/dash). Сборка запрещена (t6157u)."; exit 1
fi
timeout 20 git fetch -q origin main 2>/dev/null || { echo 'guard_stale_src: fetch не прошёл — пропускаю проверку'; exit 0; }
if [ -n "$(git rev-list -1 HEAD..origin/main 2>/dev/null)" ]; then  # t6157u: отстаём от origin/main вообще (не только src/)
  echo "guard_stale_src: HEAD отстаёт от origin/main в $(pwd) — git pull --rebase --autostash"
  if ! git pull -q --rebase --autostash origin main; then
    git rebase --abort 2>/dev/null
    echo 'guard_stale_src FAIL: src/ отстаёт от origin/main, pull не прошёл — сначала git pull вручную (иначе сборка затрёт чужие правки на сайте)'
    exit 1
  fi
  exit 10
fi
exit 0
