#!/usr/bin/env python3
"""Merge src/farm_status.json into of_blocks.farm without wiping earlier days.

Optional farm_status.days (list[{date,...}] or dict) is merged into farm.days;
days not present in the snapshot are kept. Current as_of still wins for that day.

Also computes farm.health = {ok, reasons[], checked_at} for capture problems
(Rost t5821u). Operational Seider/Onimator issues stay with Фермовод — we only
flag problems with the dash capture/snapshot itself.
"""
from __future__ import annotations
import json, sys, re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATUS = ROOT / "farm_status.json"
BLOCKS = ROOT / "of_blocks.json"
BOG = timezone(timedelta(hours=-5))
# Expected cadence unclear in ig-farm docs → >36h (task default).
STALE_HOURS = 36


def _now_bog() -> datetime:
    return datetime.now(BOG)


def _parse_as_of_dt(st: dict) -> datetime | None:
    """Best-effort snapshot timestamp in Bogotá. Prefer collected_at, else as_of[+src time]."""
    for key in ("collected_at", "captured_at", "fetched_at"):
        raw = st.get(key)
        if not raw:
            continue
        s = str(raw).strip().replace(" ", "T")
        try:
            if s.endswith("Z"):
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=BOG)
            return dt.astimezone(BOG)
        except Exception:
            pass
    as_of = st.get("as_of")
    if not as_of:
        return None
    try:
        y, m, d = map(int, str(as_of)[:10].split("-"))
    except Exception:
        return None
    # Optional clock from src like "08.11 ~15:05" or "15:05 Bogotá"
    hh, mm = 0, 0
    src = str(st.get("src") or "")
    tm = re.search(r"(?:~?\s*)(\d{1,2}):(\d{2})", src)
    if tm:
        hh, mm = int(tm.group(1)), int(tm.group(2))
    return datetime(y, m, d, hh, mm, tzinfo=BOG)


def _period_all_null(obj) -> bool:
    if not isinstance(obj, dict):
        return obj is None
    vals = [obj.get(k) for k in ("today", "week", "month")]
    return all(v is None for v in vals)


def compute_health(st: dict | None, *, missing: bool = False, unreadable: str | None = None) -> dict:
    """Capture-health only. Does not invent metric numbers."""
    checked = _now_bog().isoformat(timespec="minutes")
    reasons: list[str] = []
    if missing:
        reasons.append("нет farm_status.json")
        return {"ok": False, "reasons": reasons, "checked_at": checked}
    if unreadable:
        reasons.append("farm_status.json не читается")
        return {"ok": False, "reasons": reasons, "checked_at": checked}
    if not isinstance(st, dict):
        reasons.append("farm_status.json пустой/битый")
        return {"ok": False, "reasons": reasons, "checked_at": checked}

    # Explicit error/failed flags or error text from source
    for k in ("error", "err", "fail_reason", "failure"):
        v = st.get(k)
        if v:
            reasons.append(f"ошибка съёма: {str(v)[:120]}")
            break
    if st.get("failed") is True or st.get("fetch_failed") is True or st.get("cron_failed") is True:
        reasons.append("флаг failed в снимке")
    if str(st.get("status") or "").lower() in ("error", "failed", "fail"):
        reasons.append("status=failed в снимке")

    as_of = st.get("as_of")
    if not as_of:
        reasons.append("нет as_of")
    else:
        dt = _parse_as_of_dt(st)
        if dt is None:
            reasons.append("as_of не разобрать")
        else:
            age_h = (_now_bog() - dt).total_seconds() / 3600.0
            if age_h > STALE_HOURS:
                label = str(as_of)[:10]
                if dt.hour or dt.minute:
                    label = f"{label} {dt.hour:02d}:{dt.minute:02d}"
                reasons.append(f"снимок устарел ({label}, >{STALE_HOURS}ч)")

    accounts = st.get("accounts")
    if accounts is None and isinstance(st.get("phones"), list):
        # phones present but no accounts total — still a gap if phones empty
        pass
    if accounts == 0:
        reasons.append("0 аккаунтов в снимке")
    if accounts is None and not st.get("phones") and st.get("live_ok") is None and st.get("idle") is None:
        # no account signal at all
        if as_of:
            reasons.append("нет accounts/live_ok/idle")

    # Per-phone rows normally present (two devices). Empty list when key exists = gap.
    if "phones" in st and isinstance(st.get("phones"), list) and len(st["phones"]) == 0:
        reasons.append("phones пустой")

    # Core metrics all null (follows/likes/story_views/total periods)
    metric_objs = [st.get("follows"), st.get("likes"), st.get("story_views"), st.get("total")]
    if all(_period_all_null(x) for x in metric_objs):
        reasons.append("все метрики null")

    # live_ok / idle are part of the normal capture; both null with accounts>0 = incomplete snap
    if (accounts or 0) > 0 and st.get("live_ok") is None and st.get("idle") is None:
        reasons.append("live_ok/idle не сняты")

    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return {"ok": len(uniq) == 0, "reasons": uniq, "checked_at": checked}



def _days_from_status(st: dict) -> dict:
    """Parse optional farm_status.days (list of {date|as_of,...} or date-keyed dict)."""
    raw = st.get("days")
    items: list[tuple[str, dict]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            d = item.get("date") or item.get("as_of")
            if d:
                items.append((str(d)[:10], item))
    elif isinstance(raw, dict):
        for d, item in raw.items():
            if isinstance(item, dict) and d:
                items.append((str(d)[:10], item))
    out = {}
    keys = ("follows", "likes", "story_views", "total", "live_ok", "idle", "replace",
            "src", "note", "connected", "running", "accounts", "phones", "collected_at")
    for d, item in items:
        rec = {}
        for k in keys:
            if k in item:
                rec[k] = item.get(k)
        if rec:
            out[d] = rec
    return out


def main() -> int:
    missing = not STATUS.exists()
    unreadable = None
    st = None
    if missing:
        health = compute_health(None, missing=True)
        # Still write health onto existing farm block so the dash can show the plaque.
        if not BLOCKS.exists():
            print(f"missing {STATUS} and {BLOCKS}", file=sys.stderr)
            return 2
        blocks = json.loads(BLOCKS.read_text())
        farm = blocks.setdefault("farm", {})
        farm["health"] = health
        BLOCKS.write_text(json.dumps(blocks, ensure_ascii=False, indent=2) + "\n")
        print(f"farm_status missing; health={health}")
        return 0

    try:
        st = json.loads(STATUS.read_text())
    except Exception as e:
        unreadable = str(e)
        health = compute_health(None, unreadable=unreadable)
        blocks = json.loads(BLOCKS.read_text())
        farm = blocks.setdefault("farm", {})
        farm["health"] = health
        BLOCKS.write_text(json.dumps(blocks, ensure_ascii=False, indent=2) + "\n")
        print(f"farm_status unreadable; health={health}", file=sys.stderr)
        return 0

    as_of = st.get("as_of")
    health = compute_health(st)
    if not as_of:
        # Keep previous current/days; only refresh health.
        blocks = json.loads(BLOCKS.read_text())
        farm = blocks.setdefault("farm", {})
        farm["health"] = health
        BLOCKS.write_text(json.dumps(blocks, ensure_ascii=False, indent=2) + "\n")
        print(f"farm_status has no as_of; health={health}", file=sys.stderr)
        return 0

    blocks = json.loads(BLOCKS.read_text())
    farm = blocks.setdefault("farm", {})
    days = dict(farm.get("days") or {})
    day_rec = {
        "follows": (st.get("follows") or {}).get("today"),
        "likes": (st.get("likes") or {}).get("today"),
        "story_views": (st.get("story_views") or {}).get("today"),
        "total": (st.get("total") or {}).get("today"),
        "live_ok": st.get("live_ok"),
        "idle": st.get("idle"),
        "src": st.get("src"),
        "note": st.get("note"),
        "connected": st.get("connected"),
        "running": st.get("running"),
        "accounts": st.get("accounts"),
    }
    if "replace" in st:
        day_rec["replace"] = st.get("replace")
    if "phones" in st:
        day_rec["phones"] = st.get("phones")
    if st.get("collected_at"):
        day_rec["collected_at"] = st.get("collected_at")
    days[as_of] = day_rec
    # farm_status.days (list[{date,...}] or dict) — дописать историю, не затирая дни вне снимка
    days.update(_days_from_status(st))
    days[as_of] = day_rec  # current as_of побеждает, если тот же день есть в days[]
    farm["days"] = days
    current = {
        "as_of": as_of,
        "follows": st.get("follows"),
        "likes": st.get("likes"),
        "story_views": st.get("story_views"),
        "total": st.get("total"),
        "live_ok": st.get("live_ok"),
        "idle": st.get("idle"),
        "connected": st.get("connected"),
        "running": st.get("running"),
        "accounts": st.get("accounts"),
        "src": st.get("src"),
        "note": st.get("note"),
    }
    if "replace" in st:
        current["replace"] = st.get("replace")
    if "phones" in st:
        current["phones"] = st.get("phones")
    if st.get("collected_at"):
        current["collected_at"] = st.get("collected_at")
    for k in ("error", "failed", "fetch_failed", "status"):
        if k in st:
            current[k] = st.get(k)
    farm["current"] = current
    farm["idle"] = st.get("idle")
    farm["health"] = health
    BLOCKS.write_text(json.dumps(blocks, ensure_ascii=False, indent=2) + "\n")
    print(f"merged farm day {as_of}; health.ok={health['ok']} reasons={health['reasons']}; days={sorted(days)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
