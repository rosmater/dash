/* ===== Password gate (Rost 24.10): data.enc.json расшифровывается паролем; ключ помнится в localStorage до «Выйти» ===== */
const Gate = (() => {
  const LS = window.DASH_LS || 'dash_key_v1';
  const LS_DAY = LS + '_day';
  const bogotaDay = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' });
  const isHelper = () => !!window.DASH_HELPER;
  function expireHelperKey() {
    if (!isHelper()) return;
    try {
      const d = localStorage.getItem(LS_DAY);
      if (d !== bogotaDay()) { localStorage.removeItem(LS); localStorage.removeItem(LS_DAY); }
    } catch (e) {}
  }
  function rememberKey(raw) {
    try {
      localStorage.setItem(LS, raw);
      if (isHelper()) localStorage.setItem(LS_DAY, bogotaDay());
    } catch (e) {}
  }
  function forgetKey() {
    try { localStorage.removeItem(LS); localStorage.removeItem(LS_DAY); } catch (e) {}
  }
  const b2u = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
  const u2b = u => btoa(String.fromCharCode(...new Uint8Array(u)));
  async function decrypt(enc, key) {
    const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: b2u(enc.iv) }, key, b2u(enc.ct));
    return JSON.parse(new TextDecoder().decode(pt));
  }
  async function derive(pw, enc) {
    const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(pw), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey({ name: 'PBKDF2', hash: 'SHA-256', salt: b2u(enc.salt), iterations: enc.iter }, base, { name: 'AES-GCM', length: 256 }, true, ['decrypt']);
  }
  const imp = raw => crypto.subtle.importKey('raw', b2u(raw), 'AES-GCM', true, ['decrypt']);
  function css() {
    const s = document.createElement('style');
    s.textContent = `
.gate-blur .wrap{filter:blur(14px);pointer-events:none;user-select:none}
#gate{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:rgba(15,23,42,.35);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);font-family:Inter,system-ui,-apple-system,sans-serif}
#gate form{background:#fff;color:#0f172a;border-radius:20px;padding:28px 26px 22px;width:min(360px,calc(100vw - 32px));box-shadow:0 24px 60px rgba(15,23,42,.25);text-align:center}
#gate .lg{width:48px;height:48px;border-radius:14px;margin:0 auto 12px;display:flex;align-items:center;justify-content:center;font-size:22px;background:#eef2ff}
#gate h2{margin:0 0 4px;font-size:19px}#gate p{margin:0 0 16px;color:#64748b;font-size:13px}
#gate .row{position:relative}
#gate input{width:100%;box-sizing:border-box;padding:12px 44px 12px 14px;border:1.5px solid #cbd5e1;border-radius:12px;font-size:16px;outline:none}
#gate input:focus{border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.15)}
#gate input.masked{-webkit-text-security:disc;text-security:disc}
#gate .eye{position:absolute;right:8px;top:50%;transform:translateY(-50%);border:0;background:none;font-size:18px;cursor:pointer;padding:4px}
#gate button.go{margin-top:12px;width:100%;padding:12px;border:0;border-radius:12px;background:#4f46e5;color:#fff;font-size:15px;font-weight:600;cursor:pointer}
#gate button.go:disabled{opacity:.6}
#gate .err{color:#dc2626;font-size:13px;min-height:18px;margin-top:8px}
#gate .hint{color:#94a3b8;font-size:12px;margin-top:6px}
#gate form.shake{animation:gsh .35s}@keyframes gsh{25%{transform:translateX(-8px)}75%{transform:translateX(8px)}}
#gate-out{position:fixed;right:14px;bottom:14px;z-index:50;border:1px solid #e2e8f0;background:#fff;color:#64748b;border-radius:999px;padding:6px 12px;font-size:12px;cursor:pointer;box-shadow:0 2px 8px rgba(15,23,42,.08)}
#gate-out:hover,#gate-ref:hover{color:#0f172a}
#gate-out{padding:6px 10px;font-size:15px;line-height:1}
#gate-ref{position:fixed;right:58px;bottom:14px;z-index:50;border:1px solid #e2e8f0;background:#fff;color:#64748b;border-radius:999px;padding:6px 10px;font-size:15px;line-height:1;cursor:pointer;box-shadow:0 2px 8px rgba(15,23,42,.08)}
#gate-x{position:fixed;top:10px;right:12px;z-index:80;border:0;background:transparent;color:#64748b;font-size:18px;line-height:1;cursor:pointer;padding:4px 8px;border-radius:8px}
#gate-x:hover{color:#0f172a;background:#f1f5f9}`;
    document.head.appendChild(s);
  }
  function logoutBtn() {
    const b = document.createElement('button');
    b.id = 'gate-out'; b.textContent = '🔒'; b.title = 'Выйти (забыть пароль на этом устройстве)'; b.setAttribute('aria-label','Выйти');
    b.onclick = () => { forgetKey(); location.reload(); };
    document.body.appendChild(b);
    const r = document.createElement('button');
    r.id = 'gate-ref'; r.textContent = '↻'; r.title = 'Обновить (свежая версия, без кеша)'; r.setAttribute('aria-label','Обновить');
    r.onclick = () => { const u = new URL(location.href); u.searchParams.set('v', Date.now()); location.replace(u.toString()); };
    document.body.appendChild(r);
    if (isHelper()) { /* t6090u: маленький ✕ сверху справа — на экран пароля */
      const x = document.createElement('button');
      x.id = 'gate-x'; x.textContent = '✕'; x.title = 'Выйти на экран пароля'; x.setAttribute('aria-label','Закрыть');
      x.onclick = () => { forgetKey(); location.reload(); };
      document.body.appendChild(x);
    }
  }
  function prompt(enc) {
    return new Promise(res => {
      document.body.classList.add('gate-blur');
      const g = document.createElement('div'); g.id = 'gate';
      const helperGate = isHelper(); /* t6090u: helper — без save-password, пароль на день */
      const formAuto = helperGate ? 'off' : 'on';
      const pwAuto = helperGate ? 'off' : 'current-password';
      const userField = helperGate ? '' : '<input type="text" name="username" value="rost" autocomplete="username" hidden>';
      const pwName = helperGate ? 'dash-asst-code' : undefined;
      const hintStay = helperGate
        ? 'Пароль нужно вводить каждый день. Браузер его не сохраняет.'
        : 'Один раз ввёл — на этом устройстве больше не спрашиваем (до «Выйти»).';
      g.innerHTML = `<form autocomplete="${formAuto}" data-lpignore="true" data-1p-ignore="true"><div class="lg">🔒</div><h2>${window.DASH_TITLE || 'Бизнес-дашборд'}</h2><p>Введите пароль, чтобы открыть</p>
${userField}
<div class="row"><input id="gate-pw" class="masked" type="text" lang="ru" inputmode="text" autocomplete="${pwAuto}" autocapitalize="off" autocorrect="off" spellcheck="false" enterkeyhint="go" placeholder="Пароль" name="${helperGate ? 'dash-asst-code' : 'password'}" ${helperGate ? 'data-lpignore="true" data-1p-ignore="true" data-form-type="other" readonly' : ''} autofocus><button type="button" class="eye" title="Показать пароль">👁</button></div>
<button type="button" class="ru" style="margin:8px 0 0;padding:6px 12px;border:1.5px solid #cbd5e1;border-radius:10px;background:#fff;font-size:14px">⌨️ RU: выкл</button>
<div class="hint" style="margin-top:4px">Нет русской раскладки? Включи RU и печатай латиницей на тех же клавишах (Ш=i, Е=t…).</div>
<button class="go" type="submit">Открыть</button><div class="err"></div>
<div class="hint">${hintStay}</div></form>`;
      document.body.appendChild(g);
      const f = g.querySelector('form'), i = g.querySelector('#gate-pw'), err = g.querySelector('.err'), go = g.querySelector('.go');
      g.querySelector('.eye').onclick = () => { i.classList.toggle('masked'); i.focus(); };
      if (helperGate) i.addEventListener('focus', () => i.removeAttribute('readonly'));
      setTimeout(() => i.focus(), 50);
      const L2R = {q:'й',w:'ц',e:'у',r:'к',t:'е',y:'н',u:'г',i:'ш',o:'щ',p:'з','[':'х',']':'ъ',a:'ф',s:'ы',d:'в',f:'а',g:'п',h:'р',j:'о',k:'л',l:'д',';':'ж',"'":'э',z:'я',x:'ч',c:'с',v:'м',b:'и',n:'т',m:'ь',',':'б','.':'ю','`':'ё'};
      const toRu = v => v.toLowerCase().split('').map(c => L2R[c] || c).join('');
      let ru = false; const rb = g.querySelector('.ru');
      rb.onclick = () => { ru = !ru; rb.textContent = '⌨️ RU: ' + (ru ? 'вкл' : 'выкл'); rb.style.background = ru ? '#e0e7ff' : '#fff'; if (ru) i.value = toRu(i.value); i.focus(); };
      i.addEventListener('input', () => { if (ru) { const p = i.selectionStart; i.value = toRu(i.value); try { i.setSelectionRange(p, p); } catch (e3) {} } });
      f.onsubmit = async e => {
        e.preventDefault(); if (!i.value) return;
        go.disabled = true; go.textContent = 'Проверяю…'; err.textContent = '';
        try {
          const pv = i.value.trim().normalize('NFC').toLowerCase();
          let key = await derive(pv, enc), data;
          try { data = await decrypt(enc, key); }
          catch (eL) { const pr = toRu(pv); if (pr === pv) throw eL; key = await derive(pr, enc); data = await decrypt(enc, key); }
          rememberKey(u2b(await crypto.subtle.exportKey('raw', key)));
          g.remove(); document.body.classList.remove('gate-blur'); res(data);
        } catch (e1) {
          err.textContent = 'Неверный пароль'; f.classList.remove('shake'); void f.offsetWidth; f.classList.add('shake');
          go.disabled = false; go.textContent = 'Открыть'; i.select();
        }
      };
    });
  }
  async function unlock(src) {
    css();
    expireHelperKey();
    const r = await fetch(src, { cache: 'no-store' });
    if (!r.ok) throw new Error(src + ': HTTP ' + r.status);
    const enc = await r.json();
    let data = null;
    try { const raw = localStorage.getItem(LS); if (raw) data = await decrypt(enc, await imp(raw)); } catch (e) { forgetKey(); }
    if (!data) data = await prompt(enc);
    logoutBtn();
    return data;
  }
  return { unlock };
})();

/* ===== Dash core (shared by all variants; inlined at build) ===== */
const Dash = (() => {
  let D = null;
  const S = { mode: 'today', mv: 2, week: null, month: null, cur: 'USD', tab: 'overview' }; // Rost 25.10: всё в USD по курсу, переключателя валют нет
  const qs = new URLSearchParams(location.search);
  async function load() {
    if (window.DASH_DATA) { D = window.DASH_DATA; }
    else {
      const src = qs.get('data');
      if (src) { // локальная отладка: ?data=data.json (плоский файл в репо не пушится)
        const r = await fetch(src, { cache: 'no-store' });
        if (!r.ok) throw new Error(src + ': HTTP ' + r.status);
        D = await r.json();
      } else D = await Gate.unlock((window.DASH_ENC || 'data.enc.json') + '?t=' + Date.now()); // Rost t5110u 05.11: cache-buster — CDN GitHub держал старые данные до 10 мин
    }
    // По умолчанию — ТЕКУЩАЯ неделя/месяц по дате браузера (Rost 24.10), а не зашитая неделя.
    const t = new Date(), today = new Date(t - t.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
    const W = D.meta.weeks, M = D.meta.months;
    const curW = W.find(w => w.start <= today && today <= w.end) || [...W].reverse().find(w => w.start <= today) || W[W.length - 1];
    const curM = M.find(m => m.id === today.slice(0, 7)) || [...M].reverse().find(m => m.id <= today.slice(0, 7)) || M[M.length - 1];
    S.week = qs.get('week') || curW.id;
    S.month = qs.get('month') || curM.id;
    S.mode = qs.get('mode') || 'today'; // Rost 25.10: по умолчанию «Сегодня» (рабочий экран); неделя/месяц — сводка
    S.tab = qs.get('tab') || 'overview';
    // Из localStorage восстанавливаем только вкладку и валюту; период всегда открывается текущий.
    try { const saved = JSON.parse(localStorage.getItem('dash_state') || '{}'); if (!qs.get('tab') && saved.tab) S.tab = saved.tab; if (!qs.get('mode') && saved.mv === 2 && ['today','week','month'].includes(saved.mode)) S.mode = saved.mode; } catch (e) {}
    if (S.tab !== 'overview' && S.tab !== 'aiback' && !D.directions.some(d => d.id === S.tab)) S.tab = 'overview'; // Rost t6267u: 🤖 «Даш и AI внедрение» — не направление, но своя вкладка
    return D;
  }
  const save = () => { try { localStorage.setItem('dash_state', JSON.stringify(S)); } catch (e) {} };
  const toUSD = cur => { const fx = D.meta.fx; return { USD: 1, COP: 1 / fx.USD_COP.rate, EUR: fx.EUR_USD.rate, UAH: 1 / fx.USD_UAH.rate }[cur]; };
  const conv = (a, from, to) => (a == null ? null : a * toUSD(from) / toUSD(to));
  const curOf = dir => (S.cur === 'native' ? dir.currency : S.cur);
  const pid = () => (S.mode === 'month' ? S.month : S.week); // today → текущая неделя для фоновых расчётов
  const key = (mode, id) => (mode !== 'month' ? 'W:' : 'M:') + id;
  const weeksOfMonth = m => D.meta.weeks.filter(w => w.month === m);

  function sumItems(items, cur) {
    let s = 0, any = false;
    for (const it of items || []) { if (it.amount == null) continue; s += conv(it.amount, it.cur, cur); any = true; }
    return any ? s : null;
  }
  // Returns the record for a direction & period. Months: explicit record, or roll-up of weeks (+ extra month items).
  function record(dir, mode, id) {
    if (mode === 'today') mode = 'week';
    if (!dir.periods) return null;
    if (mode === 'week') { const r = dir.periods[key('week', id)]; return r ? { ...r, source: 'week' } : null; }
    const ex = dir.periods[key('month', id)];
    if (ex && !ex.rollup) return { ...ex, source: 'explicit' };
    const ws = weeksOfMonth(id).map(w => dir.periods['W:' + w.start]).filter(Boolean);
    if (!ws.length && !ex) return null;
    const inc = [], exp = [], notes = []; let partial = false; const metrics = {};
    ws.forEach(w => { inc.push(...(w.income || [])); exp.push(...(w.expenses || [])); if (w.status === 'partial') partial = true; });
    if (ex) { inc.push(...(ex.income || [])); exp.push(...(ex.expenses || [])); if (ex.note) notes.push(ex.note); Object.assign(metrics, ex.metrics || {}); }
    const today = new Date().toISOString().slice(0, 10);
    const allW = weeksOfMonth(id).filter(w => w.start <= today);
    if (ws.length < allW.length) partial = true;
    return { income: inc, expenses: exp, metrics, status: partial ? 'partial' : 'full', note: notes.join(' '), source: 'rollup', weeks: ws.length, weeksTotal: allW.length };
  }
  function summary(dir, mode = S.mode, id = pid(), cur = curOf(dir)) {
    const r = record(dir, mode, id);
    if (!r) return { has: false, cur };
    const income = sumItems(r.income, cur), expenses = sumItems(r.expenses, cur);
    const profit = income == null ? null : income - (expenses || 0);
    const roi = income != null && expenses ? profit / expenses * 100 : null;
    const unknownInc = (r.income || []).some(i => i.amount == null);
    const has = income != null || expenses != null || Object.keys(r.metrics || {}).length > 0 || unknownInc;
    return { has, cur, income, expenses, profit, roi, expensesKnown: expenses != null, rec: r, status: r.status, unknownInc };
  }
  function periods(mode = S.mode) {
    if (mode === 'today') mode = 'week';
    const list = mode === 'week' ? D.meta.weeks : D.meta.months;
    return list.map(p => ({ id: p.id, label: p.label, iso: p.iso }));
  }
  function periodLabel(mode = S.mode, id = pid()) { const p = periods(mode).find(x => x.id === id); return p ? p.label : id; }
  function series(dir, mode = S.mode, cur = curOf(dir), opts = {}) {
    let ps = periods(mode);
    if (opts.onlyData) ps = ps.filter(p => summary(dir, mode, p.id, cur).has);
    if (opts.last) ps = ps.slice(-opts.last);
    const s = ps.map(p => summary(dir, mode, p.id, cur));
    return { labels: ps.map(p => p.label), ids: ps.map(p => p.id), income: s.map(x => x.income ?? null), expenses: s.map(x => x.expenses ?? null), profit: s.map(x => x.profit ?? null) };
  }
  function goals(dir, mode = S.mode, id = pid()) {
    if (mode === 'today') mode = 'week';
    return (dir.goals || []).filter(g => g.last_closed || (g.period_type || 'week') === mode).map(g => {
      let actual = g.by_period ? g.by_period[key(mode, id)] : undefined;
      /* Rost: Недвижимость — помесячный учёт, всегда последний ЗАКРЫТЫЙ месяц (катится сам при закрытии нового) */
      let closed_label = null;
      if (g.last_closed && g.by_period) { const now = new Date().toISOString().slice(0, 7); const ks = Object.keys(g.by_period).filter(k => /^M:\d{4}-\d{2}$/.test(k) && k.slice(2) < now && g.by_period[k] != null).sort(); actual = undefined; if (ks.length) { const k = ks[ks.length - 1]; actual = g.by_period[k]; closed_label = new Date(k.slice(2) + '-15').toLocaleString('ru', { month: 'long' }); } }
      if (actual === undefined && g.auto_month === 'income' && mode === 'month') { const s = summary(dir, 'month', id, dir.currency); actual = s.income ?? undefined; }
      const has = actual !== undefined && actual !== null;
      let pct = null;
      if (has) pct = g.lower_is_better ? (actual <= g.target ? 100 : Math.max(0, 100 - (actual - g.target) / Math.max(g.target, 1) * 100)) : (g.target ? actual / g.target * 100 : null);
      return { ...g, actual: has ? actual : null, pct, closed_label };
    });
  }
  function breakdowns(dir, mode = S.mode, id = pid()) {
    return (dir.breakdowns || []).filter(b => b.period == null || b.period === key(mode, id));
  }
  function overview(mode = S.mode, id = pid(), cur = S.cur === 'native' ? 'USD' : S.cur) {
    const rows = D.directions.filter(d => !d.kind && !d.no_overview_totals).map(d => ({ dir: d, s: summary(d, mode, id, cur) }));
    const tot = { income: 0, expenses: 0, profit: 0, n: 0 };
    rows.forEach(r => { if (r.s.income != null) { tot.income += r.s.income; tot.profit += r.s.profit; tot.n++; } if (r.s.expenses != null) tot.expenses += r.s.expenses; });
    return { rows, tot, cur };
  }
  const SYM = { USD: '$', EUR: '€', COP: 'COP', UAH: '₴' };
  function fmt(v, cur, compact) {
    if (v == null || Number.isNaN(v)) return '—';
    const a = Math.abs(v); let s;
    if (compact && a >= 1e6) s = (v / 1e6).toLocaleString('ru-RU', { maximumFractionDigits: a >= 1e8 ? 0 : 1 }) + ' млн';
    else if (compact && a >= 1e4) s = (v / 1e3).toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + ' тыс';
    else s = v.toLocaleString('ru-RU', { maximumFractionDigits: (cur === 'COP' || cur === 'UAH' || a >= 1000) ? 0 : 2 });
    if (!cur) return s;
    return cur === 'USD' || cur === 'EUR' ? SYM[cur] + s : s + ' ' + SYM[cur];
  }
  const num = v => (typeof v === 'number' ? v.toLocaleString('ru-RU', { maximumFractionDigits: 2 }) : (v ?? '—'));
  const pct = v => (v == null ? '—' : (v > 0 ? '+' : '') + v.toFixed(0) + '%');
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  function fxFooter() { return ''; // Rost 25.10: футер с курсами/версией/правилами не показываем, конвертация в USD остаётся
  }
  function fxFooterOld() {
    const f = D.meta.fx;
    return `Курсы: 1 USD = ${f.USD_COP.rate.toLocaleString('ru-RU')} COP — ${esc(f.USD_COP.source)}, ${f.USD_COP.date} · 1 EUR = ${f.EUR_USD.rate} USD (${esc(f.EUR_USD.source)}, ${f.EUR_USD.date}) · 1 USD = ${f.USD_UAH.rate} UAH (${esc(f.USD_UAH.source)}). ` +
      `Данные: data.json v${esc(D.meta.version)}, собрано ${esc(D.meta.generated_at)} (Богота). ${esc(D.meta.week_to_month_rule)}. Значок «пример» = не реальная цифра.`;
  }
  const EX = '<span class="ex-badge" title="Не реальная цифра — пример">пример</span>';
  const PRI = { urgent: 'срочно', high: 'высокий', normal: 'обычный', low: 'низкий' };
  function trend(dir, mode = S.mode, id = pid(), cur = curOf(dir)) {
    const ps = periods(mode); const i = ps.findIndex(p => p.id === id);
    if (i <= 0) return null;
    const a = summary(dir, mode, id, cur), b = summary(dir, mode, ps[i - 1].id, cur);
    if (a.profit == null || b.profit == null || !b.profit) return null;
    return (a.profit - b.profit) / Math.abs(b.profit) * 100;
  }
  // Weekly breakdown of a month + total row (total = month record: roll-up or explicit)
  function rollup(dir, monthId, cur = curOf(dir)) {
    const ws = weeksOfMonth(monthId).map(w => ({ w, s: summary(dir, 'week', w.id, cur) }));
    const total = summary(dir, 'month', monthId, cur);
    return { weeks: ws, total, explicit: total.rec && total.rec.source === 'explicit' };
  }
  /* Rost 26.10: ↻ у вопросов — перечитать свежий data.enc.json без перезагрузки страницы (ключ уже в localStorage) */
  async function reload() { document.getElementById('gate-out')?.remove(); document.getElementById('gate-ref')?.remove(); D = await Gate.unlock((window.DASH_ENC || 'data.enc.json') + '?t=' + Date.now()); return D; }
  return { reload, rollup, load, S, save, get D() { return D; }, conv, curOf, pid, record, summary, series, goals, breakdowns, overview, periods, periodLabel, fmt, num, pct, esc, fxFooter, EX, PRI, trend, weeksOfMonth };
})();
