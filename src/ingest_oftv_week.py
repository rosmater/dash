#!/usr/bin/env python3
"""Merge src/oftv_week.json into of_blocks.oftv (week + per-model fans/net).

Does not invent numbers. Does not overwrite a known fans total with null
(Kelly ≈1900 must stay until a real total arrives).

When week.id changes: old week → prev, old prev → prev2, so a third collected
week (e.g. 19–25.10) is not dropped when the next Monday snap arrives.
Never ingest oftv_history/* by copying it over oftv_week.json.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "oftv_week.json"
BLOCKS = ROOT / "of_blocks.json"

def _sum_net(models):
    return round(sum((m.get("net") or 0) for m in models), 2)

def _sum_fans_new(models):
    return sum((m.get("fans_new") or 0) for m in models)

def main() -> int:
    if not SRC.exists():
        print(f"missing {SRC}", file=sys.stderr)
        return 2
    snap = json.loads(SRC.read_text())
    if not snap.get("week") or not snap.get("models"):
        print("oftv_week.json needs week and models", file=sys.stderr)
        return 2
    blocks = json.loads(BLOCKS.read_text())
    oftv = blocks.setdefault("oftv", {})
    new_id = (snap.get("week") or {}).get("id")
    old_week = oftv.get("week") or {}
    if old_week.get("id") and new_id and old_week.get("id") != new_id:
        models = oftv.get("models") or []
        archived = {
            "id": old_week.get("id"),
            "label": old_week.get("label"),
            "src": old_week.get("src"),
            "net": oftv["total_net"] if oftv.get("total_net") is not None else _sum_net(models),
            "fans_new": _sum_fans_new(models),
        }
        old_prev = oftv.get("prev")
        if old_prev and old_prev.get("id") and old_prev.get("id") != archived.get("id"):
            oftv["prev2"] = old_prev
        oftv["prev"] = archived
    oftv["week"] = {
        "id": new_id,
        "label": (snap.get("week") or {}).get("label"),
        "src": snap.get("src"),
    }
    by_key = {m.get("key"): m for m in snap.get("models") or [] if m.get("key")}
    by_name = {(m.get("name") or "").lower(): m for m in snap.get("models") or []}
    for m in oftv.get("models") or []:
        row = by_key.get(m.get("key")) or by_name.get((m.get("name") or "").lower())
        if not row:
            continue
        for fld in ("fans", "fans_new", "gross", "net"):
            if fld in row and row[fld] is not None:
                m[fld] = row[fld]
                if fld == "fans":
                    m.pop("fans_approx", None)
        # t6088u: copy balances if the week snapshot has them; do not wipe an older balance when absent
        for fld in ("balance_current", "balance_pending", "balance_as_of", "balance_src"):
            if fld in row and row[fld] is not None:
                m[fld] = row[fld]
    models = oftv.get("models") or []
    oftv["total_net"] = _sum_net(models)
    oftv["total_gross"] = round(sum((m.get("gross") or 0) for m in models), 2)
    cur = {
        "id": oftv["week"].get("id"),
        "label": oftv["week"].get("label"),
        "net": oftv.get("total_net"),
        "fans_new": _sum_fans_new(models),
    }
    chain = [cur]
    for key in ("prev", "prev2"):
        slot = oftv.get(key)
        if slot and slot.get("id") and slot.get("id") != cur.get("id"):
            chain.append(slot)
    oftv["weeks"] = chain[:3]
    BLOCKS.write_text(json.dumps(blocks, ensure_ascii=False, indent=2) + "\n")
    print(
        f"ingested OFTV week {oftv['week'].get('label')} models={len(by_key)} "
        f"prev={(oftv.get('prev') or {}).get('label')} prev2={(oftv.get('prev2') or {}).get('label')}"
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
