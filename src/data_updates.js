/* t6093u / t6095u / t6165u: жёлтая строка «Есть новые данные» + чип ✓ у блока
   + жёлтый кружок на кнопках направлений (число непросмотренных блоков).
   На «Общий» — сумма по всем направлениям, серый бейдж другого оттенка (не tbadge).
   Жёлтый = ещё не смотрел; после клика чип остаётся серым («Данные просмотрены DD.MM»),
   строка под «Требует внимания» пропадает, бейдж на вкладке пересчитывается.
   Новые данные снова желтят чип и бейдж. Первый заход: seen = current, сразу серый чип.
   Хранилище helper отдельное. На helper не считаем блок баланса и скрытые вкладки. */
const DataUpd = (() => {
  const LS = window.DASH_HELPER ? 'dash_data_seen_asst_v1' : 'dash_data_seen_v1';
  const extra = {};
  let booted = false;

  function bogDay(d) {
    return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit' }).format(d || new Date());
  }
  function bogDDMM(isoOrDate) {
    let s;
    if (typeof isoOrDate === 'string' && /^\d{4}-\d{2}-\d{2}/.test(isoOrDate)) s = isoOrDate.slice(0, 10);
    else s = bogDay(isoOrDate instanceof Date ? isoOrDate : new Date());
    const p = s.split('-');
    return p[2] + '.' + p[1];
  }
  function loadSeen() {
    try { return JSON.parse(localStorage.getItem(LS) || '{}') || {}; } catch (e) { return {}; }
  }
  function saveSeen(m) {
    try { localStorage.setItem(LS, JSON.stringify(m)); } catch (e) {}
  }
  function catalog() {
    const base = ((typeof Dash !== 'undefined' && Dash.D && Dash.D.data_updates) || {}).blocks || [];
    const by = {};
    base.forEach(b => { if (b && b.id) by[b.id] = b; });
    Object.keys(extra).forEach(k => { by[k] = extra[k]; });
    return Object.keys(by).map(k => by[k]);
  }
  function boot() {
    const list = catalog();
    if (!list.length && !Object.keys(extra).length) return;
    const seen = loadSeen();
    let ch = false;
    const today = bogDay();
    list.forEach(b => {
      if (b && b.id && b.ver && !seen[b.id]) {
        seen[b.id] = { ver: b.ver, seen_at: today };
        ch = true;
      }
    });
    if (ch) saveSeen(seen);
    booted = true;
  }
  function stateOf(b) {
    if (!b || !b.ver) return 'ok';
    const s = loadSeen()[b.id];
    if (!s) return 'ok'; // ещё не boot — не жёлтим
    return s.ver === b.ver ? 'ok' : 'nu';
  }
  function isVisible(b) {
    if (!b || !b.id) return false;
    // helper.html не содержит блок баланса — не считаем его и не светим
    if (window.DASH_HELPER && (b.id === 'overview.balance' || b.dir === 'overview')) return false;
    if (b.dir && b.dir !== 'overview') {
      try {
        const dirs = (typeof Dash !== 'undefined' && Dash.D && Dash.D.directions) || [];
        if (dirs.length && !dirs.some(d => d.id === b.dir)) return false;
      } catch (e) {}
    }
    return true;
  }
  function unseen(dir) {
    boot();
    return catalog().filter(b => {
      if (!isVisible(b)) return false;
      if (dir && b.dir !== dir) return false;
      return stateOf(b) === 'nu';
    });
  }
  function tabCount(dir) {
    if (!dir || dir === 'overview') return unseen(null).length;
    return unseen(dir).length;
  }
  function paintTabBadges() {
    const all = tabCount('overview');
    document.querySelectorAll('#tabs button[data-t], #mabtn button[data-t]').forEach(btn => {
      const id = btn.getAttribute('data-t');
      const n = (id === 'overview') ? all : tabCount(id);
      let el = btn.querySelector('.dubadge, .dubadge-ov');
      if (!n) {
        if (el) el.remove();
        return;
      }
      const cls = id === 'overview' ? 'dubadge-ov' : 'dubadge';
      const title = id === 'overview'
        ? ('Новых данных по всем направлениям: ' + n)
        : ('Есть новые данные: ' + n);
      if (el) {
        el.className = cls;
        el.textContent = String(n);
        el.title = title;
      } else {
        el = document.createElement('span');
        el.className = cls;
        el.textContent = String(n);
        el.title = title;
        btn.appendChild(el);
      }
    });
  }
  function markSeen(id) {
    const b = catalog().find(x => x.id === id);
    if (!b) return;
    const seen = loadSeen();
    seen[id] = { ver: b.ver, seen_at: bogDay() };
    saveSeen(seen);
  }
  function tip(b) {
    const st = stateOf(b);
    if (st === 'nu') return 'Есть обновления данных — нажми, если посмотрел';
    const s = loadSeen()[b.id] || {};
    const dd = s.seen_at ? bogDDMM(s.seen_at) : bogDDMM();
    return 'Данные просмотрены ' + dd;
  }
  function chipHTML(b) {
    const st = stateOf(b);
    return `<button type="button" class="du-chip ${st}" data-du-chip="${esc(b.id)}" title="${esc(tip(b))}" aria-label="${esc(tip(b))}">✓</button>`;
  }
  function linesHTML(items) {
    if (!items.length) return '';
    return `<div class="du-lines">${items.map(b =>
      `<div class="du-ln" data-du-go="${esc(b.id)}" role="link" tabindex="0">🟡 Есть новые данные — ${esc(b.title || b.id)}</div>`
    ).join('')}</div>`;
  }
  function currentDir() {
    try { return (typeof S !== 'undefined' && S.tab) || 'overview'; } catch (e) { return 'overview'; }
  }
  function placeLines() {
    const main = document.getElementById('main');
    if (!main) return;
    const old = main.querySelector('.du-lines');
    if (old) old.remove();
    const tab = currentDir();
    const items = (tab === 'overview') ? unseen(null) : unseen(tab);
    const html = linesHTML(items);
    if (!html) return;
    const wrap = document.createElement('div');
    wrap.innerHTML = html;
    const node = wrap.firstElementChild;
    const attn = main.querySelector('.attn');
    const ovsub = document.getElementById('ovsub');
    const head = main.querySelector('.tab-head');
    if (attn) attn.insertAdjacentElement('afterend', node);
    else if (ovsub) ovsub.insertAdjacentElement('afterend', node);
    else if (head) head.insertAdjacentElement('afterend', node);
    else main.insertAdjacentElement('afterbegin', node);
  }
  function slotFor(root) {
    return root.querySelector('.du-slot') || root.querySelector(':scope > h3') || root.querySelector('summary h3') || root.querySelector('h3');
  }
  function headOf(slot) {
    let head = slot.querySelector(':scope > .du-head');
    if (head) return head;
    head = document.createElement('span');
    head.className = 'du-head';
    const stay = n => n.nodeType === 1 && (n.classList.contains('st') || n.classList.contains('bal-lock') || n.classList.contains('du-chip') || n.classList.contains('du-head'));
    const move = [];
    [...slot.childNodes].forEach(n => { if (!stay(n)) move.push(n); });
    move.forEach(n => head.appendChild(n));
    const st = slot.querySelector(':scope > .st');
    const lock = slot.querySelector(':scope > .bal-lock');
    if (st) slot.insertBefore(head, st);
    else if (lock) slot.insertBefore(head, lock);
    else slot.insertBefore(head, slot.firstChild);
    return head;
  }
  function paintChips() {
    document.querySelectorAll('[data-du]').forEach(el => {
      const id = el.getAttribute('data-du');
      const b = catalog().find(x => x.id === id);
      if (!b) return;
      const slot = slotFor(el);
      if (!slot) return;
      const head = headOf(slot);
      const tmp = document.createElement('div');
      tmp.innerHTML = chipHTML(b);
      const node = tmp.firstElementChild;
      const existing = slot.querySelector('.du-chip');
      if (existing) existing.replaceWith(node);
      else head.appendChild(node);
    });
  }
  function bind() {
    document.querySelectorAll('[data-du-go]').forEach(el => {
      const go = ev => { ev.preventDefault(); jump(el.getAttribute('data-du-go')); };
      el.onclick = go;
      el.onkeydown = ev => { if (ev.key === 'Enter' || ev.key === ' ') go(ev); };
    });
    document.querySelectorAll('[data-du-chip]').forEach(el => {
      el.onclick = ev => {
        ev.preventDefault();
        ev.stopPropagation();
        const id = el.getAttribute('data-du-chip');
        const b = catalog().find(x => x.id === id);
        if (!b || stateOf(b) !== 'nu') return;
        markSeen(id);
        afterRender();
      };
    });
  }
  function afterRender() {
    if (typeof Dash === 'undefined' || !Dash.D) return;
    boot();
    placeLines();
    paintChips();
    paintTabBadges();
    bind();
  }
  function jump(id) {
    const b = catalog().find(x => x.id === id);
    if (!b) return;
    try {
      if (b.dir === 'overview' || b.id === 'overview.balance') {
        S.tab = 'overview';
        if (b.id === 'overview.balance') S.oview = 'balance';
      } else {
        S.tab = b.dir;
      }
    } catch (e) {}
    try { render(); } catch (e) {}
    setTimeout(() => {
      const el = document.querySelector('[data-du="' + id + '"]') || document.getElementById(b.anchor || ('du-' + id.replace(/\./g, '-')));
      if (!el) return;
      let p = el;
      while (p) {
        if (p.tagName === 'DETAILS') p.open = true;
        p = p.parentElement;
      }
      try { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e) { el.scrollIntoView(true); }
      el.classList.remove('du-flash');
      void el.offsetWidth;
      el.classList.add('du-flash');
      setTimeout(() => el.classList.remove('du-flash'), 1800);
    }, 80);
  }
  function register(b) {
    if (!b || !b.id || !b.ver) return;
    extra[b.id] = b;
    booted = false;
    boot();
    try { afterRender(); } catch (e) {}
  }
  function unregister(id) {
    delete extra[id];
    try { afterRender(); } catch (e) {}
  }
  return { afterRender, register, unregister, jump, unseen, boot, stateOf, catalog, tabCount, paintTabBadges, isVisible, LS };
})();
