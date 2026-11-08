#!/usr/bin/env python3
"""Map src/lolapop_week.json → src/of_blocks.json lolapop (HARD t5617u–t5618u).

Does not publish, encrypt, or run build.sh. COMMS publishes surgically after this.
Does not invent numbers: missing keys stay null.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEEK = ROOT / "lolapop_week.json"
BLOCKS = ROOT / "of_blocks.json"


def _num(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        s = str(v).strip().replace(",", ".")
        if s == "" or s == "—":
            return None
        return float(s) if "." in s else int(s)
    except (TypeError, ValueError):
        return None


def main() -> int:
    if not WEEK.exists():
        print(f"missing {WEEK}", file=sys.stderr)
        return 2
    week = json.loads(WEEK.read_text())
    if not isinstance(week, dict) or not week:
        print("lolapop_week.json empty or not an object", file=sys.stderr)
        return 2
    blocks = json.loads(BLOCKS.read_text())
    P = blocks.setdefault("lolapop", {})
    earn = week.get("earnings") or {}

    fans = _num(week.get("fans"))
    fans_new = _num(week.get("fans_new"))
    subs_new = _num(week.get("subs_new"))
    rebills = _num(week.get("rebills"))
    inc_subs = _num(earn.get("subs_net"))
    inc_msgs = _num(earn.get("msgs_net"))
    inc_total = _num(earn.get("of_total_net"))
    if inc_total is None and inc_subs is not None and inc_msgs is not None:
        inc_total = round(inc_subs + inc_msgs + (_num(earn.get("tips_net")) or 0) + (_num(earn.get("posts_net")) or 0), 2)
    mv = _num(week.get("manyvids_net"))
    c4s = _num(week.get("c4s_net"))

    P["fans"] = fans
    P["fans_new"] = fans_new
    periods = P.setdefault("periods", {})
    w = periods.setdefault("week", {})
    old_label = (P.get("last_snapshot") or {}).get("label")
    new_label = week.get("period")
    if old_label and new_label and old_label != new_label:
        P["prev"] = {
            "label": old_label,
            "as_of": (P.get("last_snapshot") or {}).get("as_of"),
            "subs_new": w.get("subs_new"),
            "rebills": w.get("rebills"),
            "inc_subs": w.get("inc_subs"),
            "inc_msgs": w.get("inc_msgs"),
            "inc_total": w.get("inc_total"),
            "mv": w.get("mv"),
            "c4s": w.get("c4s"),
        }
    w["subs_new"] = subs_new
    w["rebills"] = rebills
    w["inc_subs"] = inc_subs
    w["inc_msgs"] = inc_msgs
    w["inc_total"] = inc_total
    w["mv"] = mv
    w["c4s"] = c4s

    label = week.get("period") or (P.get("last_snapshot") or {}).get("label")
    as_of = week.get("as_of")
    src = week.get("src") or "OF Statistics → Subscriptions + Earnings; MV / C4S кабинеты"
    rows = [
        ["OF · подписки", _num(earn.get("subs_gross")), _num(earn.get("subs_net"))],
        ["OF · сообщения (PPV/чат)", _num(earn.get("msgs_gross")), _num(earn.get("msgs_net"))],
        ["OF · чаевые", _num(earn.get("tips_gross")), _num(earn.get("tips_net"))],
        ["OF · посты", _num(earn.get("posts_gross")), _num(earn.get("posts_net"))],
        ["OF · итого", _num(earn.get("of_total_gross")), inc_total],
        ["ManyVids (net)", None, mv],
        ["Clips4Sale", None, c4s],
    ]
    P["last_snapshot"] = {
        "label": label,
        "as_of": as_of,
        "src": src,
        "rows": rows,
    }
    BLOCKS.write_text(json.dumps(blocks, ensure_ascii=False, indent=2) + "\n")
    print(
        f"ingested {WEEK.name}: period={label} as_of={as_of} "
        f"fans={fans} fans_new={fans_new} subs_new={subs_new} rebills={rebills} "
        f"inc_subs={inc_subs} inc_msgs={inc_msgs} of_total={inc_total} mv={mv} c4s={c4s}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
