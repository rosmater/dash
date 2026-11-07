/* ===== Password gate (Rost 24.10): data.enc.json расшифровывается паролем; ключ помнится в localStorage до «Выйти» ===== */
const Gate = (() => {
  const LS = window.DASH_LS || 'dash_key_v1';
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
#gate-out:hover{color:#0f172a}`;
    document.head.appendChild(s);
  }
  function logoutBtn() {
    const b = document.createElement('button');
    b.id = 'gate-out'; b.textContent = '🔒 Выйти'; b.title = 'Забыть пароль на этом устройстве';
    b.onclick = () => { try { localStorage.removeItem(LS); } catch (e) {} location.reload(); };
    document.body.appendChild(b);
  }
  function prompt(enc) {
    return new Promise(res => {
      document.body.classList.add('gate-blur');
      const g = document.createElement('div'); g.id = 'gate';
      g.innerHTML = `<form autocomplete="on"><div class="lg">🔒</div><h2>${window.DASH_TITLE || 'Бизнес-дашборд'}</h2><p>Введите пароль, чтобы открыть</p>
<input type="text" name="username" value="rost" autocomplete="username" hidden>
<div class="row"><input id="gate-pw" class="masked" type="text" lang="ru" inputmode="text" autocomplete="current-password" autocapitalize="off" autocorrect="off" spellcheck="false" enterkeyhint="go" placeholder="Пароль" autofocus><button type="button" class="eye" title="Показать пароль">👁</button></div>
<button type="button" class="ru" style="margin:8px 0 0;padding:6px 12px;border:1.5px solid #cbd5e1;border-radius:10px;background:#fff;font-size:14px">⌨️ RU: выкл</button>
<div class="hint" style="margin-top:4px">Нет русской раскладки? Включи RU и печатай латиницей на тех же клавишах (Ш=i, Е=t…).</div>
<button class="go" type="submit">Открыть</button><div class="err"></div>
<div class="hint">Один раз ввёл — на этом устройстве больше не спрашиваем (до «Выйти»).</div></form>`;
      document.body.appendChild(g);
      const f = g.querySelector('form'), i = g.querySelector('#gate-pw'), err = g.querySelector('.err'), go = g.querySelector('.go');
      g.querySelector('.eye').onclick = () => { i.classList.toggle('masked'); i.focus(); };
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
          try { localStorage.setItem(LS, u2b(await crypto.subtle.exportKey('raw', key))); } catch (e2) {}
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
    const r = await fetch(src, { cache: 'no-store' });
    if (!r.ok) throw new Error(src + ': HTTP ' + r.status);
    const enc = await r.json();
    let data = null;
    try { const raw = localStorage.getItem(LS); if (raw) data = await decrypt(enc, await imp(raw)); } catch (e) { try { localStorage.removeItem(LS); } catch (e2) {} }
    if (!data) data = await prompt(enc);
    logoutBtn();
    return data;
  }
  return { unlock };
})();
