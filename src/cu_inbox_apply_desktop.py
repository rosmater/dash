"""HARD Rost t5351u: ClickUp dialogs on the messengers dash = Desktop Inbox only.

Source of truth: latest inbox-raw/desktop-inbox-YYYY-MM-DD.json
  - Primary unread items
  - Direct Messages only if the snapshot marked them unread (red badge, t5316u)
Never publish the MCP 48h comment/mention/for-check harvest (cu_inbox_build.py)
as messenger dialogs — that is how old requests reappeared while the live
Inbox badge was 4 (t5347–t5351).

test_ma_build.py must call apply_desktop_or_reject_mcp() before copying
cu_inbox into the encrypted payload.
"""
from __future__ import annotations

import glob
import json
import os
import re

RAW_DIR = '/workspace/notify-watchers/clickup-pulse/inbox-raw'
KINDS = [
    ['comment', 'Комменты'],
    ['mention', '@'],
    ['dm', 'Личка'],
    ['assigned', 'Назначили'],
    ['forcheck', 'for check'],
    ['other', 'Прочее'],
]


def _src_dir():
    return os.path.dirname(os.path.abspath(__file__))


def latest_desktop_path():
    files = sorted(glob.glob(os.path.join(RAW_DIR, 'desktop-inbox-*.json')))
    return files[-1] if files else None


def is_desktop_src(src):
    s = (src or '').lower()
    return 'desktop' in s and ('primary' in s or 'inbox' in s)


def _task_url(tid):
    return f'https://rosmater.github.io/cu/?t={tid}' if tid else ''


def _task_app(tid):
    return f'https://app.clickup.com/t/{tid}' if tid else ''


def _comment_url(tid, cid):
    if tid and cid:
        return f'https://app.clickup.com/t/{tid}?comment={cid}'
    return _task_app(tid)


def _norm_title(s):
    return re.sub(r'\s+', ' ', (s or '').replace('…', '').rstrip('.')).strip().lower()


def _resolve(item, prev_by_id, prev_by_title):
    tid = item.get('task_id') or ''
    if tid:
        return tid
    title = _norm_title(item.get('task') or item.get('title'))
    if not title:
        return ''
    if title in prev_by_title:
        return prev_by_title[title]
    for pt, pid in prev_by_title.items():
        if pt.startswith(title) or title.startswith(pt):
            return pid
    return ''


def desktop_to_cu_inbox(desk, prev=None):
    prev = prev or {}
    prev_threads = prev.get('threads') or []
    prev_by_id = {str(t.get('task_id')): t for t in prev_threads if t.get('task_id')}
    prev_by_title = {}
    for t in prev_threads:
        prev_by_title[_norm_title(t.get('task'))] = t.get('task_id')

    fetched = (desk.get('fetched_bogota') or '').replace(' America/Bogota', ' Bogotá')
    if fetched and 'Bogotá' not in fetched:
        fetched = fetched + ' Bogotá'
    items, threads, counts = [], [], {}
    seen = set()

    for raw in desk.get('items') or []:
        section = (raw.get('section') or 'Primary').strip()
        if section == 'DM':
            unread = raw.get('unread')
            if unread is False or raw.get('badge') in (None, 0, '0', False):
                # t5316u: DM without a red badge is not unread
                if not unread:
                    continue
        elif section not in ('Primary', 'primary', 'Inbox', 'INBOX'):
            # Other / Later never become dash dialogs
            continue

        tid = _resolve(raw, prev_by_id, prev_by_title)
        task = raw.get('task') or (raw.get('title') or '').rstrip('.')
        prev_t = prev_by_id.get(tid) or {}
        kind = raw.get('kind') or 'comment'
        if section == 'DM' and kind == 'comment':
            kind = 'dm'
        who = (raw.get('author') or prev_t.get('who') or '').strip()
        at = raw.get('at') or ''
        cid = raw.get('comment_id') or prev_t.get('comment_id') or ''
        # One unread inbox row = one dialog; do not use the task's total
        # comment count (e.g. 15) as «новых комментов».
        n_new = int(raw.get('n_new') or 1)
        list_name = raw.get('list') or prev_t.get('list') or ''
        list_id = str(raw.get('list_id') or prev_t.get('list_id') or '')
        status = raw.get('status') or prev_t.get('status') or ''
        kinds = [kind]
        if kind == 'mention':
            kinds = ['mention', 'comment'] if section != 'DM' else ['mention', 'dm']

        base = dict(
            task_id=tid,
            task=task,
            list=list_name,
            list_id=list_id,
            status=status,
            task_url=_task_url(tid),
            task_app=_task_app(tid),
        )
        title_prefix = 'DM · ' if section == 'DM' else ''
        item = dict(
            base,
            kind=kind,
            at=at,
            who=who,
            comment_id=cid,
            comment_url=_comment_url(tid, cid),
            n_new=n_new,
        )
        if section == 'DM':
            item['task'] = title_prefix + task
        items.append(item)
        counts[kind] = counts.get(kind, 0) + 1

        key = tid or (section + '|' + task)
        if key in seen:
            continue
        seen.add(key)
        thread = dict(
            base,
            task=item['task'],
            kinds=kinds,
            at=at,
            who=who,
            comment_url=_comment_url(tid, cid),
            comment_id=cid,
            sub='',
            n_new=n_new,
            mention_at=at if kind == 'mention' else '',
            author=who,
            author_bot=False,
        )
        threads.append(thread)

    src = (
        f"desktop Inbox Primary + DM (red badge only) · {fetched} · "
        f"primary={desk.get('primary', len([i for i in items if not str(i.get('task','')).startswith('DM · ')]))} "
        f"dm={desk.get('dm_unread', 0)}"
    )
    return {
        '_note': (
            'HARD Rost t5351u: диалоги ClickUp на даше = Desktop Inbox Primary '
            '+ Direct Messages только с красным бейджем. MCP-опрос за 48ч сюда не пишем.'
        ),
        'fetched': fetched,
        'since': fetched,
        'src': src,
        'tier': 'desktop',
        'kinds': KINDS,
        'counts': counts,
        'items': items,
        'threads': threads,
        'desktop_file': latest_desktop_path() or '',
    }


def apply_desktop_or_reject_mcp(src_dir=None):
    src_dir = src_dir or _src_dir()
    out_path = os.path.join(src_dir, 'ma_cu_inbox.json')
    prev = {}
    if os.path.exists(out_path):
        try:
            prev = json.load(open(out_path, encoding='utf-8'))
        except Exception:
            prev = {}

    desk_path = latest_desktop_path()
    if desk_path:
        desk = json.load(open(desk_path, encoding='utf-8'))
        data = desktop_to_cu_inbox(desk, prev)
        data['desktop_file'] = desk_path
        json.dump(data, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(
            f"cu_inbox desktop {os.path.basename(desk_path)} → "
            f"threads {len(data['threads'])} items {len(data['items'])} "
            f"primary={desk.get('primary')} dm_unread={desk.get('dm_unread', 0)}"
        )
        return data

    if is_desktop_src(prev.get('src') or '') or prev.get('tier') == 'desktop':
        print('cu_inbox keep desktop-sourced ma_cu_inbox.json (no newer desktop-inbox-*.json)')
        return prev

    print(
        'cu_inbox REJECT mcp harvest as dialogs '
        f"(src={prev.get('src')!r} threads={len(prev.get('threads') or [])}) → empty"
    )
    empty = dict(
        fetched=prev.get('fetched') or '',
        since='',
        src='rejected MCP harvest (t5351: dialogs only from desktop Inbox+DM)',
        tier='desktop',
        kinds=KINDS,
        counts={},
        items=[],
        threads=[],
    )
    json.dump(empty, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return empty


if __name__ == '__main__':
    apply_desktop_or_reject_mcp()
