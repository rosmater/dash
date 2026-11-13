#!/usr/bin/env python3
"""Map src/lolapop_week.json → src/of_blocks.json lolapop (HARD t5617u–t5618u, t5687).

Does not publish, encrypt, or run build.sh. COMMS publishes surgically after this.
Does not invent numbers: missing keys stay null.
Does not overwrite a known field with null.

When the period changes, archive the full last_snapshot (rows — e.g. 01–15.10
$173.28 / MV $7.79 / C4S $0) into prev and last. Do not build prev from the
often-empty periods.week. The new file becomes cur + last_snapshot.
Also ingest `ig` (handle → {fans, delta} or a legacy delta number).
HARD t717–t721u: never wipe lolapop.ig_accounts[].status/note — merge by handle.
"""
from __future__ import annotations

import json
import re
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


def _row(rows, pat):
    rx = re.compile(pat, re.I)
    return next((r for r in rows if r and rx.search(str(r[0]))), None)


def week_from_snapshot(ls):
    if not isinstance(ls, dict) or not ls.get("label"):
        return None
    rows = ls.get("rows") or []

    def net(pat):
        r = _row(rows, pat)
        return _num(r[2]) if r and len(r) > 2 else None

    return {
        "label": ls.get("label"),
        "as_of": ls.get("as_of"),
        "src": ls.get("src"),
        "inc_subs": net(r"подписк"),
        "inc_msgs": net(r"сообщен|PPV"),
        "inc_tips": net(r"чаевые"),
        "inc_posts": net(r"посты"),
        "inc_total": net(r"итого"),
        "mv": net(r"ManyVids"),
        "c4s": net(r"Clips4Sale|C4S"),
        "subs_new": None,
        "rebills": None,
        "fans": None,
        "fans_new": None,
    }



def preserve_ig_accounts(existing, incoming=None):
    """Keep lolapop.ig_accounts status/note across ingests (t717–t721u).

    existing/incoming: list of {handle, status?, note?, status_at?} or plain handle strings.
    Merge by handle (strip leading @); status/note/status_at from existing win unless
    incoming supplies a non-empty value for that field.
    """
    def norm_list(raw):
        out = []
        if not isinstance(raw, list):
            return out
        for a in raw:
            if isinstance(a, dict) and a.get("handle"):
                out.append({
                    "handle": str(a["handle"]).lstrip("@"),
                    "status": a.get("status"),
                    "note": a.get("note"),
                    "status_at": a.get("status_at"),
                    "src": a.get("src"),
                })
            elif isinstance(a, str) and a.strip():
                out.append({"handle": a.strip().lstrip("@"), "status": None, "note": None, "status_at": None})
        return out

    by = {}
    order = []
    for a in norm_list(existing):
        h = a["handle"]
        if h not in by:
            order.append(h)
        by[h] = dict(a)
    for a in norm_list(incoming):
        h = a["handle"]
        if h not in by:
            order.append(h)
            by[h] = dict(a)
        else:
            cur = by[h]
            for k in ("status", "note", "status_at", "src"):
                if a.get(k) not in (None, ""):
                    cur[k] = a[k]
                # else keep existing
    out = []
    for h in order:
        row = {"handle": h}
        st = by[h].get("status")
        if st not in (None, ""):
            row["status"] = st
        if by[h].get("status_at"):
            row["status_at"] = by[h]["status_at"]
        if by[h].get("note"):
            row["note"] = by[h]["note"]
        if by[h].get("src"):
            row["src"] = by[h]["src"]
        out.append(row)
    return out

OF_IG_KEYS = ("of_link", "of_subs", "of_clicks", "of_subs_week", "of_clicks_week")
AUD_KEYS = ("viewers_total", "viewers_guests", "viewers_users", "viewers_usa", "usa_guests", "usa_users", "earn_chats", "subs")


def merge_audience(existing, incoming):
    """t6274u: OF audience (Reach). Never overwrite a known number with null."""
    out = dict(existing) if isinstance(existing, dict) else {}
    if isinstance(incoming, dict):
        for k in AUD_KEYS:
            v = _num(incoming.get(k))
            if v is not None:
                out[k] = v
            else:
                out.setdefault(k, None)
        if incoming.get("src"):
            out["src"] = incoming["src"]
    return out or None


def normalize_ig(raw, existing=None):
    out = {}
    if isinstance(existing, dict):
        for handle, val in existing.items():
            h = str(handle).lstrip("@")
            if isinstance(val, dict):
                out[h] = {"fans": _num(val.get("fans")), "delta": _num(val.get("delta"))}
                for k in OF_IG_KEYS:  # t6275u: OF tracking-link per IG
                    if val.get(k) is not None:
                        out[h][k] = val[k]
            else:
                out[h] = {"fans": None, "delta": _num(val)}
    if not isinstance(raw, dict):
        return out
    for handle, val in raw.items():
        h = str(handle).lstrip("@")
        prev = out.get(h) or {}
        if isinstance(val, dict):
            fans = _num(val.get("fans"))
            delta = _num(val["delta"] if val.get("delta") is not None else val.get("fans_new"))
            out[h] = {
                "fans": fans if fans is not None else prev.get("fans"),
                "delta": delta if delta is not None else prev.get("delta"),
            }
            for k in OF_IG_KEYS:  # t6275u: OF +N per IG (tracking link, Monday snapshots)
                v2 = val.get(k) if k == "of_link" else _num(val.get(k))
                if v2 is not None:
                    out[h][k] = v2
                elif prev.get(k) is not None:
                    out[h][k] = prev[k]
        else:
            delta = _num(val)
            out[h] = {
                "fans": prev.get("fans"),
                "delta": delta if delta is not None else prev.get("delta"),
            }
    return out


def start_token(label):
    if not label:
        return None
    m = re.search(r"(\d{1,2}).(\d{2})", str(label).replace("–", "-"))
    if not m:
        return None
    return f"{int(m.group(1)):02d}.{m.group(2)}"


def merge_week(existing, incoming):
    if not isinstance(existing, dict):
        return dict(incoming)
    out = dict(existing)
    for k, v in incoming.items():
        if k == "ig":
            out["ig"] = normalize_ig(v, existing.get("ig"))
        elif k == "audience":
            out["audience"] = merge_audience(existing.get("audience"), v)
        elif k == "pornstocks":
            continue
        elif k == "label" and existing.get("label"):
            continue  # keep short column label (e.g. «02–08.11»)
        elif v is not None:
            out[k] = v
    return out


def upsert_weeks(weeks, incoming):
    token = start_token(incoming.get("label"))
    new_id = incoming.get("id")
    for i, w in enumerate(weeks):
        if not isinstance(w, dict):
            continue
        same = (new_id and w.get("id") == new_id) or (
            incoming.get("label") and w.get("label") == incoming.get("label")
        ) or (token and start_token(w.get("label")) == token)
        if same:
            weeks[i] = merge_week(w, incoming)
            return weeks
    weeks.insert(0, incoming)
    return weeks


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
    # t717–t721u: carry ig_accounts status/note (week may omit or only list handles)
    P["ig_accounts"] = preserve_ig_accounts(P.get("ig_accounts"), week.get("ig_accounts"))
    earn = week.get("earnings") or {}

    fans = _num(week.get("fans"))
    fans_new = _num(week.get("fans_new"))
    subs_new = _num(week.get("subs_new"))
    # t5822u: no previous fans total → fans_new null; use OF Statistics → Subscriptions (subs_new)
    fans_new_src = None
    if fans_new is None and subs_new is not None:
        fans_new = subs_new
        fans_new_src = "subs_new"
    rebills = _num(week.get("rebills"))
    inc_subs = _num(earn.get("subs_net"))
    inc_msgs = _num(earn.get("msgs_net"))
    inc_tips = _num(earn.get("tips_net"))
    inc_posts = _num(earn.get("posts_net"))
    inc_total = _num(earn.get("of_total_net"))
    if inc_total is None and any(x is not None for x in (inc_subs, inc_msgs, inc_tips, inc_posts)):
        inc_total = round(
            (inc_subs or 0) + (inc_msgs or 0) + (inc_tips or 0) + (inc_posts or 0), 2
        )
    mv = _num(week.get("manyvids_net"))
    c4s = _num(week.get("c4s_net"))
    new_label = week.get("period")
    as_of = week.get("as_of")
    src = week.get("src") or "OF Statistics → Subscriptions + Earnings; MV / C4S кабинеты"

    old_ls = P.get("last_snapshot") if isinstance(P.get("last_snapshot"), dict) else None
    old_label = (old_ls or {}).get("label")
    if old_label and new_label and old_label != new_label:
        archived = week_from_snapshot(old_ls)
        wold = (P.get("periods") or {}).get("week") or {}
        if archived:
            for k, v in wold.items():
                if archived.get(k) is None and v is not None:
                    archived[k] = v
            P["prev"] = archived
            P["last"] = json.loads(json.dumps(archived))

    P["fans"] = fans if fans is not None else P.get("fans")
    P["fans_new"] = fans_new if fans_new is not None else P.get("fans_new")
    periods = P.setdefault("periods", {})
    w = periods.setdefault("week", {})
    for key, val in (
        ("subs_new", subs_new),
        ("rebills", rebills),
        ("inc_subs", inc_subs),
        ("inc_msgs", inc_msgs),
        ("inc_tips", inc_tips),
        ("inc_posts", inc_posts),
        ("inc_total", inc_total),
        ("mv", mv),
        ("c4s", c4s),
        ("fans", fans),
        ("fans_new", fans_new),
    ):
        if val is not None:
            w[key] = val

    new_week = {
        "id": week.get("id"),
        "label": new_label,
        "as_of": as_of,
        "inc_subs": inc_subs,
        "inc_msgs": inc_msgs,
        "inc_tips": inc_tips,
        "inc_posts": inc_posts,
        "inc_total": inc_total,
        "mv": mv,
        "c4s": c4s,
        "fans": fans,
        "fans_new": fans_new,
        "subs_new": subs_new,
        "rebills": rebills,
        "ig": normalize_ig(week.get("ig")),
    }
    if isinstance(week.get("audience"), dict):
        new_week["audience"] = merge_audience(None, week["audience"])
    P["cur"] = new_week
    P["weeks"] = upsert_weeks(list(P.get("weeks") or []), new_week)
    # t6274u: one-time/backfill history by week id (only existing weeks; no invented weeks)
    for wid, hv in (week.get("history") or {}).items():
        tgt = next((w for w in P["weeks"] if isinstance(w, dict) and w.get("id") == wid), None)
        if tgt is None or not isinstance(hv, dict):
            continue
        if isinstance(hv.get("audience"), dict):
            tgt["audience"] = merge_audience(tgt.get("audience"), hv["audience"])
        if hv.get("ig_of_note"):
            tgt["ig_of_note"] = hv["ig_of_note"]
    if isinstance(week.get("tracking"), dict):
        P["tracking"] = week["tracking"]

    rows = [
        ["OF · подписки", _num(earn.get("subs_gross")), _num(earn.get("subs_net"))],
        ["OF · сообщения (PPV/чат)", _num(earn.get("msgs_gross")), _num(earn.get("msgs_net"))],
        ["OF · чаевые", _num(earn.get("tips_gross")), _num(earn.get("tips_net"))],
        ["OF · посты", _num(earn.get("posts_gross")), _num(earn.get("posts_net"))],
        ["OF · итого", _num(earn.get("of_total_gross")), inc_total],
        ["ManyVids (net)", None, mv],
        ["Clips4Sale", None, c4s],
    ]
    snap = {
        "label": new_label or (old_ls or {}).get("label"),
        "as_of": as_of,
        "src": src,
        "rows": rows,
        "fans": fans if fans is not None else P.get("fans"),
        "fans_new": fans_new,
        "subs_new": subs_new,
    }
    if fans_new_src:
        snap["fans_new_source"] = fans_new_src
        # keep human note on why fans_new came from subscriptions
        note = "fans_new ← subs_new (OF Statistics → Subscriptions; no prior fans total for delta)"
        snap["src"] = (src + "; " if src else "") + note
    P["last_snapshot"] = snap
    BLOCKS.write_text(json.dumps(blocks, ensure_ascii=False, indent=2) + "\n")
    print(
        f"ingested {WEEK.name}: period={new_label} as_of={as_of} "
        f"fans={fans} fans_new={fans_new} subs_new={subs_new} rebills={rebills} "
        f"inc_subs={inc_subs} inc_msgs={inc_msgs} of_total={inc_total} mv={mv} c4s={c4s} "
        f"ig={list((new_week.get('ig') or {}).keys())} "
        f"archived_prev={(P.get('prev') or {}).get('label')} total={(P.get('prev') or {}).get('inc_total')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
