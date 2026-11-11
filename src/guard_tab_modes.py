#!/usr/bin/env python3
"""Rost t5983u: страж чипов периода в шапке (Сегодня/Неделя/Месяц).
Правило t5968u/t5988u: ОФ/Коучинг/Табакевич — без «Сегодня»; Недвижимость — только видимый активный «Месяц»;
Оборонка — только видимый активный «Сегодня» (ряд не прячем, даже если чип один).
Недоступные чипы должны быть полностью скрыты (hidden + display:none !important),
а не disabled/серые и не видны из-за display:inline-flex (регресс c7f602de / t1057u).
Запуск: python3 src/guard_tab_modes.py [путь/к/variant-a.html]
Опционально: --browser URL — проверить computed style по вкладкам (Chrome).
"""
from __future__ import annotations
import re, sys, json
from pathlib import Path

EXPECT = {
    'overview': ['today', 'week', 'month'],
    'personal': ['today', 'week', 'month'],
    'peptides': ['today', 'week', 'month'],
    'of': ['week', 'month'],
    'coaching': ['week', 'month'],
    'tabakevich': ['week', 'month'],
    'realestate': ['month'],
    'defense': ['today'],
}
LABEL = {'today': 'Сегодня', 'week': 'Неделя', 'month': 'Месяц'}

def src_path(argv):
    args = [a for a in argv if not a.startswith('--')]
    if args:
        return Path(args[0])
    here = Path(__file__).resolve().parent
    for c in (here / 'variant-a.html', here.parent / 'src' / 'variant-a.html', here.parent / 'index.html'):
        if c.exists():
            return c
    raise SystemExit('не найден variant-a.html')

def tab_modes_from(src: str):
    m = re.search(r"function tabModes\(id\)\{return \((\{.*?\})\)\[id\]\|\|\[([^\]]+)\]\}", src)
    if not m:
        raise SystemExit('FAIL: function tabModes не найдена')
    raw, default = m.group(1), m.group(2)
    # literal like of:['week','month']
    spec = {}
    for k, arr in re.findall(r"(\w+):\[([^\]]+)\]", raw):
        spec[k] = re.findall(r"'(\w+)'", arr)
    default_modes = re.findall(r"'(\w+)'", default)
    return spec, default_modes

def check_source(src: str):
    bad = []
    spec, default_modes = tab_modes_from(src)
    if default_modes != ['today', 'week', 'month']:
        bad.append(f"дефолт tabModes {default_modes}, ожидалось ['today','week','month']")
    for tab, modes in EXPECT.items():
        if tab in ('overview', 'personal', 'peptides'):
            got = spec.get(tab, default_modes)
        else:
            got = spec.get(tab)
        if got != modes:
            bad.append(f"tabModes({tab})={got}, ожидалось {modes}")
    # CSS must force-hide, otherwise #mode button{display:inline-flex} and .seg{display:inline-flex} un-hide [hidden]
    css_ok = bool(re.search(
        r"#mode\[hidden\],#mode button\[hidden\](?:,\.seg\[hidden\])?\{display:none!important\}",
        src,
    )) or bool(re.search(
        r"#mode\[hidden\].*display:\s*none\s*!important",
        src,
    ))
    if not css_ok:
        bad.append("нет CSS-правила #mode[hidden],#mode button[hidden]{display:none!important} — чипы снова станут видны из-за display:inline-flex")
    if re.search(r"#mode button\{display:inline-flex", src) and not css_ok:
        bad.append("найден #mode button{display:inline-flex} без перекрытия [hidden] — регресс t1057u/c7f602de")
    if 'function tabModes' not in src or 'b.hidden=!vis' not in src:
        bad.append("пропала JS-логика скрытия чипов (tabModes / b.hidden=!vis)")
    if "bar.hidden=!top&&allow.length<=1" in src:
        bad.append("ряд #mode снова скрывается при одном периоде — t5988u: Недвижимость должна показывать «Месяц», Оборонка — «Сегодня»")
    if "b.hidden=!vis" not in src:
        bad.append("пропало скрытие отдельных чипов (b.hidden=!vis)")
    return bad

def main():
    argv = sys.argv[1:]
    p = src_path(argv)
    src = p.read_text(encoding='utf-8', errors='replace')
    bad = check_source(src)
    if bad:
        print('FAIL guard_tab_modes:', p)
        for b in bad:
            print(' -', b)
        sys.exit(1)
    print('OK guard_tab_modes source:', p)
    spec, default_modes = tab_modes_from(src)
    shown = {k: [LABEL[m] for m in v] for k, v in {**{t: default_modes for t in ('overview','personal','peptides')}, **spec}.items() if k in EXPECT}
    # t5988u: one allowed period still shows that one chip (bar stays visible)
    print(json.dumps(shown, ensure_ascii=False, indent=2))

    if '--browser' in argv or any(a.startswith('--url=') for a in argv):
        url = next((a.split('=',1)[1] for a in argv if a.startswith('--url=')), None)
        if not url:
            sys.exit('нужен --url=http://... для --browser')
        check_browser(url)

def check_browser(url):
    import subprocess, tempfile, os, textwrap
    js = r'''
    const tabs = %s;
    const expect = %s;
    const out = {};
    function vis(){
      const bar = document.querySelector('#mode');
      const cs = bar ? getComputedStyle(bar) : null;
      const barHidden = !bar || bar.hidden || cs.display==='none' || cs.visibility==='hidden' || bar.getBoundingClientRect().width===0;
      const chips = [];
      if (bar && !barHidden){
        bar.querySelectorAll('button').forEach(b=>{
          const s=getComputedStyle(b), r=b.getBoundingClientRect();
          if (!b.hidden && s.display!=='none' && s.visibility!=='hidden' && r.width>0 && r.height>0)
            chips.push((b.querySelector('.plab')?b.querySelector('.plab').textContent:b.textContent).replace(/[‹›]/g,'').trim());
        });
      }
      return {barHidden, chips};
    }
    const wait = ms => new Promise(r=>setTimeout(r,ms));
    (async()=>{
      for (const tab of tabs){
        if (typeof S!=='undefined'){ S.tab=tab; if (typeof render==='function') render(); }
        await wait(50);
        out[tab]=vis();
      }
      console.log('TAB_MODES_RESULT '+JSON.stringify(out));
    })();
    ''' % (json.dumps(list(EXPECT)), json.dumps({k:[LABEL[m] for m in v] for k,v in EXPECT.items()}))
    # implementation via caller screenshots script; here just document hook
    print('browser hook: use test_tab_modes_screens.mjs / chrome script; --browser placeholder in this guard is source-only unless chrome helper is present')

if __name__ == '__main__':
    main()
