#!/usr/bin/env python3
"""Merge src/oftv_week.json into of_blocks.oftv (week + per-model fans/net)."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "oftv_week.json"
BLOCKS = ROOT / "of_blocks.json"

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
        oftv["prev"] = {
            "id": old_week.get("id"),
            "label": old_week.get("label"),
            "src": old_week.get("src"),
            "net": round(sum((m.get("net") or 0) for m in models), 2),
            "fans_new": sum((m.get("fans_new") or 0) for m in models),
        }
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
    BLOCKS.write_text(json.dumps(blocks, ensure_ascii=False, indent=2) + "\n")
    print(f"ingested OFTV week {oftv['week'].get('label')} models={len(by_key)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
