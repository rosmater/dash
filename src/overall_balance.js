/* Rost t6090u / t6091u / t6092u: «Общий баланс» — только главный даш (не попадает в helper.html).
   Данные в Dash.D.overall_balance_enc (AES-GCM, PBKDF2-SHA256 от PIN). Расшифровка в браузере по PIN.
   Сессия: sessionStorage. Неверный PIN — остаётся закрытым. 🔒 — закрыть снова. */
(function () {
  if (window.DASH_HELPER) return;
  const SS = 'dash_bal_sess_v1';
  const b2u = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
  function enc() {
    try {
      const D = (typeof Dash !== 'undefined' && Dash.D) || {};
      return D.overall_balance_enc || null;
    } catch (e) { return null; }
  }
  function loadSess() {
    try { return JSON.parse(sessionStorage.getItem(SS) || 'null'); } catch (e) { return null; }
  }
  function saveSess(data) {
    try { sessionStorage.setItem(SS, JSON.stringify(data)); } catch (e) {}
  }
  function clearSess() {
    try { sessionStorage.removeItem(SS); } catch (e) {}
  }
  async function derive(pin, pack) {
    const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(pin), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey(
      { name: 'PBKDF2', hash: 'SHA-256', salt: b2u(pack.salt), iterations: pack.iter },
      base, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
  }
  async function decryptWithPin(pin) {
    const pack = enc();
    if (!pack || !pack.ct) throw new Error('no pack');
    const key = await derive(pin, pack);
    const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: b2u(pack.iv) }, key, b2u(pack.ct));
    return JSON.parse(new TextDecoder().decode(pt));
  }
  function css() {
    if (document.getElementById('bal-css')) return;
    const s = document.createElement('style');
    s.id = 'bal-css';
    s.textContent = `
#ovsub{margin:0 0 10px}
.bal-card{position:relative;overflow:hidden}
.bal-card h3{display:flex;align-items:center;gap:8px;margin:0 0 8px}
.bal-card h3 .bal-lock{margin-left:auto;border:0;background:#f4f5f8;color:#64748b;border-radius:8px;width:28px;height:28px;cursor:pointer;font-size:14px;line-height:1}
.bal-card h3 .bal-lock:hover{background:#e8eaf0;color:#0f172a}
.bal-total{font-size:32px;font-weight:800;letter-spacing:-.03em;margin:4px 0 10px}
.bal-row{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-top:1px dashed var(--line);font-size:14px}
.bal-row .amt{font-variant-numeric:tabular-nums;font-weight:700;white-space:nowrap}
.bal-row .miss{color:var(--mut);font-weight:500}
.bal-locked .bal-ghost{filter:blur(13px);opacity:.45;user-select:none;pointer-events:none}
.bal-overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.55);backdrop-filter:blur(2px);-webkit-backdrop-filter:blur(2px)}
.bal-pinbox{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px 16px 14px;width:min(280px,calc(100% - 28px));box-shadow:0 10px 28px rgba(15,23,42,.12);text-align:center}
.bal-pinbox p{margin:0 0 10px;font-size:13px;color:var(--mut)}
.bal-pinbox .row{position:relative;margin:0 0 8px}
.bal-pinbox input{width:100%;box-sizing:border-box;padding:10px 12px;border:1.5px solid #cbd5e1;border-radius:10px;font-size:18px;letter-spacing:.3em;text-align:center;outline:none}
.bal-pinbox input:focus{border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.15)}
.bal-pinbox input.masked{-webkit-text-security:disc;text-security:disc;letter-spacing:.4em}
.bal-pinbox .go{width:100%;padding:10px;border:0;border-radius:10px;background:#4f46e5;color:#fff;font-size:14px;font-weight:600;cursor:pointer}
.bal-pinbox .go:disabled{opacity:.6}
.bal-pinbox .err{color:#dc2626;font-size:12.5px;min-height:16px;margin-top:6px}
.bal-pinbox form.shake{animation:gsh .35s}
`;
    document.head.appendChild(s);
  }
  function money(v, cur) {
    if (typeof Dash !== 'undefined' && Dash.fmt) return Dash.fmt(v, cur);
    if (v == null || Number.isNaN(v)) return '—';
    return String(v);
  }
  function stLab(st) {
    if (st === 'not_connected') return 'не подключено';
    if (st === 'partial') return 'частично';
    return '';
  }
  function bodyHTML(B) {
    const cur = (B && B.currency) || 'USD';
    const rows = (B.holdings || []).map(h => {
      const miss = h.amount == null;
      return `<div class="bal-row"><span>${esc(h.name)}${h.note ? ` <span class="note">${esc(h.note)}</span>` : ''}</span><span class="amt${miss ? ' miss' : ''}">${miss ? (stLab(h.status) || '—') : money(h.amount, h.cur || cur)}</span></div>`;
    }).join('');
    const gaps = (B.gaps || []).map(g => `<div class="note" style="margin-top:6px">${esc(g)}</div>`).join('');
    const asof = B.as_of ? `на ${esc(B.as_of.slice(8, 10) + '.' + B.as_of.slice(5, 7) + (B.as_of.length > 10 ? '' : ''))}` : 'фундамент';
    return `<h3>💼 ${esc(B.title || 'Общий баланс')} <span class="note">${asof}</span><button type="button" class="bal-lock" title="Закрыть" aria-label="Закрыть баланс">🔒</button></h3>
      <div class="bal-total">${money(B.total, cur)}</div>
      <div class="note" style="margin-bottom:4px">Где лежат деньги</div>
      ${rows || '<div class="note">статей пока нет</div>'}
      ${gaps}`;
  }
  function ghostHTML() {
    return `<h3>💼 Общий баланс <span class="note">закрыто</span></h3>
      <div class="bal-total">88 888</div>
      <div class="bal-row"><span>Банки / карты</span><span class="amt">12 345</span></div>
      <div class="bal-row"><span>Наличные</span><span class="amt">6 789</span></div>
      <div class="bal-row"><span>Крипто</span><span class="amt">4 321</span></div>`;
  }
  function navHTML() {
    const on = (S.oview === 'balance') ? 'balance' : 'summary';
    return `<div class="seg" id="ovsub"><button type="button" data-ov="summary" class="${on === 'summary' ? 'on' : ''}">Сводка</button><button type="button" data-ov="balance" class="${on === 'balance' ? 'on' : ''}">Общий баланс</button></div>`;
  }
  function bindNav() {
    const el = document.getElementById('ovsub');
    if (!el) return;
    el.querySelectorAll('button').forEach(b => b.onclick = () => {
      S.oview = b.dataset.ov === 'balance' ? 'balance' : 'summary';
      try { Dash.save(); } catch (e) {}
      render();
    });
  }
  function bindLock(root) {
    const b = root && root.querySelector('.bal-lock');
    if (!b) return;
    b.onclick = ev => { ev.preventDefault(); ev.stopPropagation(); clearSess(); render(); };
  }
  function bindPin(root) {
    const f = root.querySelector('#bal-pin-form');
    if (!f) return;
    const i = f.querySelector('#bal-pin'), err = f.querySelector('.err'), go = f.querySelector('.go');
    i.addEventListener('focus', () => i.removeAttribute('readonly'));
    f.onsubmit = async ev => {
      ev.preventDefault();
      const pin = (i.value || '').normalize('NFC').trim();
      if (!pin) return;
      go.disabled = true; go.textContent = 'Открываю…'; err.textContent = '';
      try {
        const data = await decryptWithPin(pin);
        i.value = '';
        saveSess(data);
        render();
      } catch (e) {
        err.textContent = 'Неверный PIN';
        f.classList.remove('shake'); void f.offsetWidth; f.classList.add('shake');
        go.disabled = false; go.textContent = 'Открыть';
        i.value = '';
        i.focus();
      }
    };
  }
  function renderBalance() {
    css();
    const pack = enc();
    const opened = loadSess();
    let inner;
    if (opened) {
      inner = `<div class="card bal-card" id="bal-box" data-du="overview.balance">${bodyHTML(opened)}</div>`;
    } else {
      inner = `<div class="card bal-card bal-locked" id="bal-box">
        <div class="bal-ghost" aria-hidden="true">${ghostHTML()}</div>
        <div class="bal-overlay">
          <form class="bal-pinbox" id="bal-pin-form" autocomplete="off" data-lpignore="true" data-1p-ignore="true">
            <p>Введите PIN, чтобы открыть баланс</p>
            <div class="row"><input id="bal-pin" class="masked" type="text" inputmode="text" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" data-lpignore="true" data-1p-ignore="true" data-form-type="other" name="dash-bal-code" readonly placeholder="PIN" enterkeyhint="go"></div>
            <button class="go" type="submit">Открыть</button>
            <div class="err"></div>
          </form>
        </div>
      </div>`;
    }
    if (!pack && !opened) {
      inner = `<div class="card bal-card"><h3>💼 Общий баланс</h3><div class="note">Нет зашифрованных данных блока. Пересоберите даш с PIN.</div></div>`;
    }
    $('#main').innerHTML = navHTML() + inner;
    bindNav();
    const box = document.getElementById('bal-box');
    if (opened) bindLock(box);
    else bindPin(box);
    try {
      if (typeof DataUpd !== 'undefined') {
        if (opened) {
          const ver = opened.data_ver || JSON.stringify({t: opened.total, h: opened.holdings, a: opened.as_of, s: opened.status});
          DataUpd.register({id: 'overview.balance', dir: 'overview', title: opened.title || 'Общий баланс', ver: String(ver), anchor: 'bal-box'});
        } else {
          DataUpd.unregister('overview.balance');
        }
      }
    } catch (e) {}
    const pin = document.getElementById('bal-pin');
    if (pin) setTimeout(() => { try { pin.focus(); } catch (e) {} }, 40);
  }
  function injectNavIntoOverview() {
    const main = $('#main');
    if (!main) return;
    if (document.getElementById('ovsub')) return;
    main.insertAdjacentHTML('afterbegin', navHTML());
    bindNav();
  }
  function isOn() { return S.tab === 'overview' && S.oview === 'balance'; }
  function ready() { return !!(enc() || loadSess()); }
  function patch() {
    if (typeof overview !== 'function' || overview._balPatched) return;
    const _ov = overview, _ovt = overviewToday, _ctl = controls, _ren = render;
    overview = function () {
      if (isOn() && ready()) { renderBalance(); return; }
      _ov.apply(this, arguments);
      if (S.tab === 'overview' && ready()) injectNavIntoOverview();
    };
    overviewToday = function () {
      if (isOn() && ready()) { renderBalance(); return; }
      _ovt.apply(this, arguments);
      if (S.tab === 'overview' && ready()) injectNavIntoOverview();
    };
    controls = function () {
      if (S.oview == null) {
        try {
          const saved = JSON.parse(localStorage.getItem('dash_state') || '{}');
          if (saved.oview === 'balance' || saved.oview === 'summary') S.oview = saved.oview;
        } catch (e) {}
        if (!S.oview) S.oview = 'summary';
      }
      _ctl.apply(this, arguments);
      const bar = document.getElementById('mode');
      if (bar && isOn()) bar.hidden = true;
    };
    render = function () {
      if (S.tab !== 'overview' && S.oview === 'balance') { /* keep oview but don't hide other tabs' modes */ }
      return _ren.apply(this, arguments);
    };
    overview._balPatched = true;
  }
  patch();
  window.BalView = { render: renderBalance, isOn, ready };
})();
