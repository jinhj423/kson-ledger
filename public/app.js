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

  // Net-buy chart: pointer shows the day under it.
  const initLine = (root) => root.querySelectorAll('.chart').forEach((box) => {
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

  // Reported-price dots: pointer picks the nearest dot.
  const initDots = (root) => root.querySelectorAll('.dotc').forEach((box) => {
    const pts = JSON.parse(box.dataset.pts || '[]');
    if (!pts.length) return;
    const tip = box.querySelector('.tip');
    const hit = box.querySelector('.hit');
    const dots = box.querySelectorAll('.pd');
    const show = (e) => {
      const r = hit.getBoundingClientRect();
      const x = e.clientX - r.left;
      const y = e.clientY - r.top;
      let best = 0;
      let bd = Infinity;
      pts.forEach((p, i) => {
        const d = Math.hypot((p.x / 100) * r.width - x, p.y - y);
        if (d < bd) { bd = d; best = i; }
      });
      const p = pts[best];
      dots.forEach((d, i) => d.classList.toggle('hl', i === best));
      tip.style.left = `${p.x}%`;
      tip.style.top = `${p.y - p.r - 6}px`;
      tip.querySelector('span').textContent = p.d;
      tip.querySelector('b').textContent = p.t;
      tip.querySelector('small').textContent = p.s;
      tip.dataset.side = p.x > 75 ? 'l' : p.x < 25 ? 'r' : 'c';
      box.classList.add('on');
    };
    hit.addEventListener('pointermove', show);
    hit.addEventListener('pointerdown', show);
    hit.addEventListener('pointerleave', () => {
      box.classList.remove('on');
      dots.forEach((d) => d.classList.remove('hl'));
    });
  });

  // TradingView price line, loaded only where a chart box is on screen.
  const initTV = (root) => root.querySelectorAll('[data-tv]').forEach((box) => {
    if (box.dataset.done) return;
    box.dataset.done = '1';
    const { s, n } = JSON.parse(box.dataset.tv);
    const wrap = box.querySelector('.tradingview-widget-container');
    wrap.querySelector('.tradingview-widget-container__widget').textContent = '';
    const sc = document.createElement('script');
    sc.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js';
    sc.async = true;
    sc.textContent = JSON.stringify({
      symbols: [[n, `${s}|12M`]], chartOnly: false, autosize: true, locale: 'kr', colorTheme: 'dark',
      showVolume: false, showMA: true, maLength: 200, maLineColor: 'rgba(164,169,178,0.85)', maLineWidth: 1,
      hideDateRanges: false, hideMarketStatus: true, hideSymbolLogo: true, scalePosition: 'right', scaleMode: 'Normal',
      fontFamily: 'Inter, Noto Sans KR, sans-serif', fontSize: '11', noTimeScale: false, valuesTracking: '1',
      changeMode: 'price-and-percent', chartType: 'line', lineWidth: 2, lineType: 0, lineColor: '#F3F4F6',
      dateRanges: ['3m|1D', '12m|1D', '60m|1W'], backgroundColor: '#0F1115', gridLineColor: 'rgba(255,255,255,0)',
      fontColor: '#A4A9B2', widgetFontColor: '#F3F4F6',
    });
    wrap.appendChild(sc);
  });

  const init = (root) => { initLine(root); initDots(root); initTV(root); };
  init(document);

  // Tapping a company row opens its chart in a sheet; the row stays a normal link without JS.
  const dlg = document.createElement('dialog');
  dlg.className = 'pop';
  dlg.setAttribute('aria-labelledby', 'pop-t');
  document.body.appendChild(dlg);
  if (typeof dlg.showModal === 'function') {
    document.addEventListener('click', async (e) => {
      const a = e.target.closest('a[data-pop]');
      if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const href = a.getAttribute('href');
      e.preventDefault();
      dlg.innerHTML = '<div class="pop-in"><p class="muted">불러오는 중이에요</p></div>';
      if (!dlg.open) dlg.showModal();
      try {
        const r = await fetch(`/x${href}`);
        if (!r.ok) throw new Error(String(r.status));
        dlg.innerHTML = await r.text();
        init(dlg);
        const x = dlg.querySelector('[data-close]');
        if (x) x.focus();
      } catch {
        location.href = href;
      }
    });
    dlg.addEventListener('click', (e) => {
      if (e.target === dlg || e.target.closest('[data-close]')) dlg.close();
    });
    dlg.addEventListener('close', () => { dlg.innerHTML = ''; });
  }

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
