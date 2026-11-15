(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Big number counts up once on load.
  document.querySelectorAll('[data-count]').forEach((el) => {
    if (reduce) return;
    const to = parseFloat(el.dataset.count) || 0;
    const dec = +el.dataset.dec || 0;
    const pre = el.dataset.pre || '';
    const fmt = (v) => pre + v.toLocaleString('ko-KR', { minimumFractionDigits: dec, maximumFractionDigits: dec });
    const t0 = performance.now();
    const step = (t) => {
      const p = Math.min(1, (t - t0) / 1100);
      el.textContent = fmt(to * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
    };
    el.textContent = fmt(0);
    requestAnimationFrame(step);
  });

  // Chart: pointer shows the day under it.
  document.querySelectorAll('.chart').forEach((box) => {
    const pts = JSON.parse(box.dataset.pts || '[]');
    if (!pts.length) return;
    const cur = box.querySelector('.cur');
    const dot = box.querySelector('.dot');
    const tip = box.querySelector('.tip');
    const hit = box.querySelector('.hit');
    const show = (x) => {
      const r = hit.getBoundingClientRect();
      const p = pts[Math.round(Math.max(0, Math.min(1, (x - r.left) / r.width)) * (pts.length - 1))];
      cur.style.left = dot.style.left = tip.style.left = `${p.x}%`;
      dot.style.top = `${p.y}px`;
      dot.className = `dot ${p.up ? 'up' : 'dn'}`;
      tip.querySelector('span').textContent = p.d;
      tip.querySelector('b').textContent = `순매수 ${p.t}`;
      tip.dataset.side = p.x > 75 ? 'l' : p.x < 25 ? 'r' : 'c';
      box.classList.add('on');
    };
    hit.addEventListener('pointermove', (e) => show(e.clientX));
    hit.addEventListener('pointerdown', (e) => show(e.clientX));
    hit.addEventListener('pointerleave', () => box.classList.remove('on'));
  });

  // Tabs (ranking 많이 산 / 많이 판).
  document.querySelectorAll('[data-tabs]').forEach((g) => {
    g.querySelectorAll('[data-tab]').forEach((b) => b.addEventListener('click', () => {
      g.querySelectorAll('[data-tab]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      g.querySelectorAll('[data-panel]').forEach((p) => { p.hidden = p.dataset.panel !== b.dataset.tab; });
    }));
  });

  // Search suggestions.
  const input = document.getElementById('q');
  const list = document.querySelector('.sugg');
  if (input && list) {
    let idx = null;
    const load = async () => {
      if (idx) return idx;
      const get = (u) => fetch(u).then((r) => (r.ok ? r.json() : [])).catch(() => []);
      const [kr, us] = await Promise.all([get('/data/kr_index.json'), get('/data/us_index.json')]);
      idx = [...kr.map(([k, n]) => [k, n, '', `/c/${k}/`]), ...us.map(([k, n, ko]) => [k, n, ko || '', `/u/${k}/`])];
      return idx;
    };
    const norm = (s) => String(s || '').toLowerCase().replace(/\s+/g, '');
    const esc = (s) => String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
    input.addEventListener('focus', load, { once: true });
    input.addEventListener('input', async () => {
      const q = norm(input.value);
      if (!q) { list.hidden = true; return; }
      const hits = (await load()).filter(([k, n, ko]) => norm(k).startsWith(q) || norm(n).includes(q) || norm(ko).includes(q)).slice(0, 8);
      list.innerHTML = hits.map(([k, n, ko, href]) => `<li><a href="${esc(href)}"><span>${esc(ko ? `${n} (${ko.split(' ')[0]})` : n)}</span><small>${esc(k)}</small></a></li>`).join('');
      list.hidden = !hits.length;
    });
    input.addEventListener('blur', () => setTimeout(() => { list.hidden = true; }, 150));
  }
})();
