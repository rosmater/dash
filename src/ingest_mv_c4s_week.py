#!/usr/bin/env python3
"""Sum MV/C4S per-sale JSON into LolaPop Mon–Sun weeks (last 3 closed).

HARD Rost t5826u: ManyVids + Clips4Sale weekly → «Своя модель» on OF tab.

Input JSON (file path or stdin):
  {
    "c4s": [{"date":"YYYY-MM-DD","price":13.99,"income":8.39}, ...],
    "mv":  [{"date":"YYYY-MM-DD","total":5.39}, ...],
    "as_of": "YYYY-MM-DD",          # optional, default today Bogotá
    "src": "AdsPower k1gxh3kk …"    # optional note appended to week src
  }

C4S: `income` = net (Revenue details «Income»), `price` = gross when known.
MV: `total` = per-sale «Total» as shown on My Earnings → Recent Sales
    (page does not label net/gross; store as shown into manyvids_net / mv).

Behaviour:
  - Last 3 closed Mon–Sun weeks in America/Bogota (relative to as_of / today).
  - Weeks with zero sales get 0 (not null) — verified empty is a real figure.
  - Writes lolapop_week.json manyvids_net / c4s_net / c4s_gross (+ src note)
    only for the newest closed week when that file's period matches.
  - Upserts of_blocks.json → lolapop.weeks / cur / periods.week / last_snapshot
    rows for MV/C4S (does not wipe OF earnings or IG / pornstocks).
  - Mirrors newest closed week into lolapop_history/<DD.MM-DD.MM.YYYY>.json.
  - Does NOT encrypt, publish, or run build.sh. Caller publishes surgically.
  - Does NOT rewrite lolapop.ig_accounts (keep status/note; t717–t721u).

Usage:
  python3 src/ingest_mv_c4s_week.py /path/to/sales.json
  python3 src/ingest_mv_c4s_week.py -   # stdin
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

BOG = dt.timezone(dt.timedelta(hours=-5))
ROOT = Path(__file__).resolve().parent
WEEK = ROOT / "lolapop_week.json"
BLOCKS = ROOT / "of_blocks.json"
HIST = ROOT / "lolapop_history"


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        s = str(v).strip().replace(",", ".").replace("$", "")
        if s == "" or s == "—":
            return None
        return float(s)
    except (TypeError, ValueError):
        return None


def bog_today(as_of=None):
    if as_of:
        return dt.date.fromisoformat(str(as_of)[:10])
    return dt.datetime.now(BOG).date()


def last_closed_mondays(today: dt.date, n=3):
    # Monday of the week containing today; if today is Mon, that week is open → go back 7.
    weekday = today.weekday()  # Mon=0
    this_mon = today - dt.timedelta(days=weekday)
    newest_closed = this_mon - dt.timedelta(days=7)
    return [newest_closed - dt.timedelta(days=7 * i) for i in range(n)]


def week_label(mon: dt.date) -> str:
    sun = mon + dt.timedelta(days=6)
    if mon.month == sun.month:
        return f"{mon.day:02d}–{sun.day:02d}.{sun.month:02d}"
    return f"{mon.day:02d}.{mon.month:02d}–{sun.day:02d}.{sun.month:02d}"


def week_period_full(mon: dt.date) -> str:
    sun = mon + dt.timedelta(days=6)
    if mon.month == sun.month and mon.year == sun.year:
        return f"{mon.day:02d}–{sun.day:02d}.{sun.month:02d}.{sun.year}"
    if mon.year == sun.year:
        return f"{mon.day:02d}.{mon.month:02d}–{sun.day:02d}.{sun.month:02d}.{sun.year}"
    return f"{mon.day:02d}.{mon.month:02d}.{mon.year}–{sun.day:02d}.{sun.month:02d}.{sun.year}"


def hist_name(mon: dt.date) -> str:
    sun = mon + dt.timedelta(days=6)
    return f"{mon.day:02d}.{mon.month:02d}-{sun.day:02d}.{sun.month:02d}.{sun.year}.json"


def parse_date(s) -> dt.date | None:
    if not s:
        return None
    s = str(s).strip()[:10]
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        m = re.match(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", s)
        if not m:
            return None
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        return dt.date(y, mo, d)


def monday_of(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def sum_weeks(payload: dict, mons: list[dt.date]):
    buckets = {
        m: {"mv": 0.0, "c4s": 0.0, "c4s_gross": 0.0, "c4s_n": 0, "mv_n": 0, "c4s_price_n": 0}
        for m in mons
    }
    mon_set = set(mons)

    for row in payload.get("c4s") or []:
        if not isinstance(row, dict):
            continue
        d = parse_date(row.get("date") or row.get("day"))
        if not d:
            continue
        m = monday_of(d)
        if m not in mon_set:
            continue
        income = _num(row.get("income") if row.get("income") is not None else row.get("net"))
        price = _num(row.get("price") if row.get("price") is not None else row.get("gross"))
        if income is not None:
            buckets[m]["c4s"] = round(buckets[m]["c4s"] + income, 2)
            buckets[m]["c4s_n"] += 1
        if price is not None:
            buckets[m]["c4s_gross"] = round(buckets[m]["c4s_gross"] + price, 2)
            buckets[m]["c4s_price_n"] += 1

    for row in payload.get("mv") or []:
        if not isinstance(row, dict):
            continue
        d = parse_date(row.get("date") or row.get("day"))
        if not d:
            continue
        m = monday_of(d)
        if m not in mon_set:
            continue
        total = _num(row.get("total") if row.get("total") is not None else row.get("amount"))
        if total is not None:
            buckets[m]["mv"] = round(buckets[m]["mv"] + total, 2)
            buckets[m]["mv_n"] += 1

    out = []
    for m in mons:
        b = buckets[m]
        out.append(
            {
                "id": f"W:{m.isoformat()}",
                "label": week_label(m),
                "period": week_period_full(m),
                "sort": m.isoformat(),
                "mon": m,
                "mv": round(b["mv"], 2),  # 0 if no sales
                "c4s": round(b["c4s"], 2),
                "c4s_gross": round(b["c4s_gross"], 2) if b["c4s_price_n"] else (
                    None if b["c4s_n"] == 0 and b["c4s"] == 0 else None
                ),
                # when sales exist but no prices: c4s_gross stays None
                "c4s_sales": b["c4s_n"],
                "mv_sales": b["mv_n"],
            }
        )
        # Fix c4s_gross: only set when we had at least one price
        if b["c4s_price_n"] == 0:
            out[-1]["c4s_gross"] = None
        else:
            out[-1]["c4s_gross"] = round(b["c4s_gross"], 2)
    return out


def start_token(label):
    if not label:
        return None
    m = re.search(r"(\d{1,2}).(\d{2})", str(label).replace("–", "-"))
    if not m:
        return None
    return f"{int(m.group(1)):02d}.{m.group(2)}"


def patch_week_row(existing: dict | None, incoming: dict) -> dict:
    base = dict(existing) if isinstance(existing, dict) else {}
    base["id"] = incoming["id"]
    base["label"] = incoming.get("label") or base.get("label")
    if incoming.get("sort"):
        base["sort"] = incoming["sort"]
    base["mv"] = incoming["mv"]
    base["c4s"] = incoming["c4s"]
    if incoming.get("c4s_gross") is not None:
        base["c4s_gross"] = incoming["c4s_gross"]
    note = (
        f"MV/C4S AdsPower k1gxh3kk 2026-11-09: mv={incoming['mv']} "
        f"c4s_net={incoming['c4s']}"
        + (f" c4s_gross={incoming['c4s_gross']}" if incoming.get("c4s_gross") is not None else "")
    )
    base["mv_c4s_note"] = note
    return base


def upsert_weeks(weeks: list, incoming: dict) -> list:
    token = start_token(incoming.get("label"))
    new_id = incoming.get("id")
    for i, w in enumerate(weeks):
        if not isinstance(w, dict):
            continue
        same = (new_id and w.get("id") == new_id) or (
            incoming.get("label") and w.get("label") == incoming.get("label")
        ) or (token and start_token(w.get("label")) == token)
        if same:
            weeks[i] = patch_week_row(w, incoming)
            return weeks
    weeks.insert(0, patch_week_row(None, incoming))
    return weeks


def patch_snapshot_rows(rows: list | None, mv, c4s, c4s_gross):
    rows = [list(r) for r in (rows or [])]
    def set_row(pat, gross, net):
        rx = re.compile(pat, re.I)
        for r in rows:
            if r and rx.search(str(r[0])):
                while len(r) < 3:
                    r.append(None)
                r[1] = gross
                r[2] = net
                return
        rows.append([pat.split("|")[0].replace("\\", ""), gross, net])

    set_row(r"ManyVids", None, mv)
    # Prefer existing Clips4Sale label
    found = False
    for r in rows:
        if r and re.search(r"Clips4Sale|C4S", str(r[0]), re.I):
            while len(r) < 3:
                r.append(None)
            r[1] = c4s_gross
            r[2] = c4s
            found = True
            break
    if not found:
        rows.append(["Clips4Sale", c4s_gross, c4s])
    return rows


def scrub_src(src: str | None, extra: str) -> str:
    src = src or ""
    src = re.sub(
        r"MV/C4S не сняты:[^.]*\.",
        "",
        src,
        flags=re.I,
    )
    src = re.sub(r"\s{2,}", " ", src).strip().rstrip(";")
    if extra:
        if src:
            src = src + "; " + extra
        else:
            src = extra
    return src


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="sales JSON path, or - for stdin")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    raw = sys.stdin.read() if a.input == "-" else Path(a.input).read_text()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        print("input must be a JSON object", file=sys.stderr)
        return 2

    today = bog_today(payload.get("as_of"))
    mons = last_closed_mondays(today, 3)
    weeks = sum_weeks(payload, mons)
    src_extra = payload.get("src") or (
        "MV Recent Sales + C4S Revenue details Income (AdsPower k1gxh3kk 2026-11-09); "
        "zero weeks = verified no sales"
    )

    print("as_of", today.isoformat(), "closed weeks:")
    for w in weeks:
        print(
            f"  {w['id']} {w['label']}: mv={w['mv']} c4s={w['c4s']} "
            f"c4s_gross={w['c4s_gross']} (mv_sales={w['mv_sales']} c4s_sales={w['c4s_sales']})"
        )

    if a.dry:
        return 0

    if not BLOCKS.exists():
        print(f"missing {BLOCKS}", file=sys.stderr)
        return 2
    blocks = json.loads(BLOCKS.read_text())
    P = blocks.setdefault("lolapop", {})
    # t717–t721u: do not touch P["ig_accounts"] (status/note owned by OF Marketing / COMMS)

    # Update weeks list
    wlist = list(P.get("weeks") or [])
    for w in weeks:
        wlist = upsert_weeks(wlist, w)
    P["weeks"] = wlist

    newest = weeks[0]
    # cur + periods.week
    cur = P.get("cur") if isinstance(P.get("cur"), dict) else {}
    if not cur.get("id") or cur.get("id") == newest["id"] or start_token(cur.get("label")) == start_token(newest["label"]):
        cur = dict(cur)
        cur["id"] = newest["id"]
        cur["label"] = newest["label"] if not cur.get("label") else cur["label"]
        cur["mv"] = newest["mv"]
        cur["c4s"] = newest["c4s"]
        if newest.get("c4s_gross") is not None:
            cur["c4s_gross"] = newest["c4s_gross"]
        P["cur"] = cur
    periods = P.setdefault("periods", {})
    pw = periods.setdefault("week", {})
    pw["mv"] = newest["mv"]
    pw["c4s"] = newest["c4s"]
    if newest.get("c4s_gross") is not None:
        pw["c4s_gross"] = newest["c4s_gross"]

    # last_snapshot rows + src
    ls = P.get("last_snapshot") if isinstance(P.get("last_snapshot"), dict) else {}
    ls = dict(ls)
    ls["rows"] = patch_snapshot_rows(ls.get("rows"), newest["mv"], newest["c4s"], newest.get("c4s_gross"))
    ls["src"] = scrub_src(ls.get("src"), src_extra)
    if not ls.get("label"):
        ls["label"] = newest["period"]
    if not ls.get("as_of"):
        ls["as_of"] = today.isoformat()
    P["last_snapshot"] = ls

    BLOCKS.write_text(json.dumps(blocks, ensure_ascii=False, indent=2) + "\n")

    # lolapop_week.json — only if period matches newest closed week
    if WEEK.exists():
        week = json.loads(WEEK.read_text())
    else:
        week = {"period": newest["period"], "as_of": today.isoformat()}
    week_tok = start_token(week.get("period"))
    if week_tok == start_token(newest["label"]) or week_tok == start_token(newest["period"]) or not week.get("period"):
        week["manyvids_net"] = newest["mv"]
        week["c4s_net"] = newest["c4s"]
        if newest.get("c4s_gross") is not None:
            week["c4s_gross"] = newest["c4s_gross"]
        week["as_of"] = week.get("as_of") or today.isoformat()
        week["src"] = scrub_src(week.get("src"), src_extra)
        WEEK.write_text(json.dumps(week, ensure_ascii=False, indent=2) + "\n")
        HIST.mkdir(parents=True, exist_ok=True)
        hist_path = HIST / hist_name(newest["mon"])
        hist_path.write_text(json.dumps(week, ensure_ascii=False, indent=2) + "\n")
        print(f"wrote {WEEK.name} + {hist_path.name}")
    else:
        print(
            f"skip lolapop_week.json period={week.get('period')} ≠ newest {newest['period']}",
            file=sys.stderr,
        )

    print(
        f"ingested MV/C4S → of_blocks.lolapop: "
        + ", ".join(f"{w['label']} mv={w['mv']} c4s={w['c4s']}" for w in weeks)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
