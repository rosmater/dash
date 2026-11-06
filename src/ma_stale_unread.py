"""Stale / ghost unread filter for messengers dash (Rost t5198u 2026-11-06).

WhatsApp Desktop «No leídos» can keep green badges for months after Rost already
read the chat. Dash must NOT show those as active unread. Keep them in live JSON
with stale_unread=True; drop from sphere/list/monitor unmuted unread.
"""
from __future__ import annotations
import datetime as _dt
import re

STALE_UNREAD_DAYS = 14

_DOW_EN = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
    'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6,
}
_DOW_ES = {
    'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2, 'jueves': 3,
    'viernes': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6,
}
_DOW_RU = {
    'понедельник': 0, 'вторник': 1, 'среда': 2, 'четверг': 3,
    'пятница': 4, 'суббота': 5, 'воскресенье': 6,
}


def snap_ref_date(L, fallback=None):
    """Reference date (Bogotá calendar day) from a live snap dict."""
    if fallback is None:
        fallback = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=5)).date()
    if not L:
        return fallback
    for key in ('at_bogota', 'at'):
        raw = (L.get(key) or '').strip()
        if not raw:
            continue
        m = re.match(r'(\d{4}-\d{2}-\d{2})', raw)
        if m:
            try:
                return _dt.datetime.strptime(m.group(1), '%Y-%m-%d').date()
            except ValueError:
                pass
    return fallback


def chat_last_raw(c):
    """Prefer last, then age (IG), then time — whatever the snap wrote."""
    if not isinstance(c, dict):
        return ''
    for k in ('last', 'age', 'time', 'last_at'):
        v = c.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ''


def parse_chat_last_date(last, ref):
    """Parse WA/IG/Viber last-column into a date, or None if unknown.

    Understood:
      - YYYY-MM-DD[ HH:MM]
      - M/D/YYYY or M/D/YY (US WA Desktop)
      - HH:MM / H:MM → ref (today of snap)
      - Yesterday / Ayer / Вчера → ref-1
      - weekday name (EN/ES/RU) → most recent past that weekday ≤ ref
      - relative age: 3h, 1d, 2w, 1m (IG Direct style)
      - «N дн.» / «N дн»
    Unknown → None (caller must KEEP visible — fail open).
    """
    if not last:
        return None
    s = str(last).strip()
    if not s:
        return None
    # ISO date (optional time)
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})(?:[ T]\d{1,2}:\d{2})?', s)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    # US M/D/YYYY or M/D/YY
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', s)
    if m:
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return _dt.date(y, mo, d)
        except ValueError:
            return None
    # clock today
    if re.match(r'^\d{1,2}:\d{2}$', s):
        return ref
    low = s.lower()
    if low in ('yesterday', 'ayer', 'вчера'):
        return ref - _dt.timedelta(days=1)
    # weekday names (Monday=0 is falsy — never use `or` chain)
    if low in _DOW_EN: wd = _DOW_EN[low]
    elif low in _DOW_ES: wd = _DOW_ES[low]
    elif low in _DOW_RU: wd = _DOW_RU[low]
    else: wd = None
    if wd is not None:
        delta = (ref.weekday() - wd) % 7
        if delta == 0:
            delta = 7  # same weekday → last week (WA shows "Monday" not today's clock)
        return ref - _dt.timedelta(days=delta)
    # relative age: 30m / 3h / 1d / 2w / 1mo
    m = re.match(r'^(\d+)\s*(m|min|mins|h|hr|hrs|d|day|days|w|wk|week|weeks|mo|mon|month|months)$', low)
    if m:
        n = int(m.group(1)); u = m.group(2)
        if u in ('m', 'min', 'mins', 'h', 'hr', 'hrs'):
            return ref
        if u in ('d', 'day', 'days'):
            return ref - _dt.timedelta(days=n)
        if u in ('w', 'wk', 'week', 'weeks'):
            return ref - _dt.timedelta(days=7 * n)
        if u in ('mo', 'mon', 'month', 'months'):
            return ref - _dt.timedelta(days=30 * n)
        return None
    # RU «N дн.»
    m = re.match(r'^(\d+)\s*дн\.?$', low)
    if m:
        return ref - _dt.timedelta(days=int(m.group(1)))
    return None


def is_stale_unread(c, ref, days=STALE_UNREAD_DAYS):
    """True only when last parses and is strictly older than `days`. Unknown last → False (keep)."""
    raw = chat_last_raw(c)
    d = parse_chat_last_date(raw, ref)
    if d is None:
        return False
    return (ref - d).days > days


def mark_stale_unreads(L, days=STALE_UNREAD_DAYS):
    """Annotate live snap chats in-place. Returns list of dropped titles.

    - Sets/clears stale_unread on each chat.
    - Copies age/time into last when last was empty (so dash can show the date).
    - Does NOT remove chats from L['chats'].
    """
    if not L:
        return []
    ref = snap_ref_date(L)
    dropped = []
    for c in (L.get('chats') or []):
        if not isinstance(c, dict):
            continue
        raw = chat_last_raw(c)
        if raw and not (c.get('last') or '').strip():
            c['last'] = raw
        if is_stale_unread(c, ref, days=days):
            c['stale_unread'] = True
            title = (c.get('title') or c.get('name') or '').strip() or '?'
            dropped.append(title)
        else:
            if 'stale_unread' in c:
                c['stale_unread'] = False
    return dropped


def write_live_flags(path, L):
    """Persist annotated live JSON (stale_unread + normalized last)."""
    import json
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(L, f, ensure_ascii=False, indent=1)
        f.write('\n')
