#!/bin/bash
# t6157u: пост-push проверка живого даша по блокам (src/owners.json). Использование: bash src/verify_live.sh
cd "$(dirname "$0")/.." && exec python3 src/verify_live.py "$@"
