(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const root = document.documentElement;
  const dark = () => root.dataset.theme === 'dark';

  // Light / dark: the device setting until the reader picks one; the pick stays in this browser only.
  const toggle = document.querySelector('[data-theme-toggle]');
  const label = () => toggle && toggle.setAttribute('aria-label', dark() ? '밝은 화면으로 바꾸기' : '어두운 화면으로 바꾸기');
  label();
  if (toggle) {
    toggle.addEventListener('click', () => {
      root.dataset.theme = dark() ? 'light' : 'dark';
      try { localStorage.setItem('theme', root.dataset.theme); } catch { /* storage may be blocked */ }
      label();
      document.querySelectorAll('[data-tv]').forEach((b) => { delete b.dataset.done; });
      initTV(document);
    });
  }

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

  document.querySelectorAll('.chart').forEach((ch) => {
    const plot = ch.querySelector('.plot');
    const bars = ch.querySelectorAll('.bar');
    const pts = JSON.parse(plot.dataset.pts || '[]');
    const tip = plot.querySelector('.tip');
    const hit = plot.querySelector('.hit');
    const mark = (i) => {
      ch.classList.toggle('focus', i != null);
      bars.forEach((b) => b.classList.toggle('hl', i != null && +b.dataset.i === i));
    };

    // Bars: pointer picks the day under it.
    const show = (x) => {
      const r = hit.getBoundingClientRect();
      const i = Math.max(0, Math.min(pts.length - 1, Math.floor(((x - r.left) / r.width) * pts.length)));
      const p = pts[i];
      const px = ((i + 0.5) / pts.length) * 100;
      tip.style.left = `${px}%`;
      tip.style.top = `${p.top}px`;
      tip.querySelector('span').textContent = p.d;
      tip.querySelector('b').textContent = `순매수 ${p.t}`;
      tip.querySelector('small').textContent = p.s || '';
      tip.dataset.side = px > 80 ? 'l' : px < 20 ? 'r' : 'c';
      plot.classList.add('on');
      mark(i);
    };
    hit.addEventListener('pointermove', (e) => show(e.clientX));
    hit.addEventListener('pointerdown', (e) => show(e.clientX));
    hit.addEventListener('pointerleave', () => { plot.classList.remove('on'); mark(null); });

    // Event dots: one open at a time, stem grows up or down, card stays inside the screen.
    const evs = [...ch.querySelectorAll('.ev')];
    let pinned = null;
    const open = (ev) => {
      evs.forEach((x) => {
        const on = x === ev;
        x.classList.toggle('open', on);
        x.querySelector('.dot').setAttribute('aria-expanded', String(on));
      });
      mark(ev ? +ev.dataset.i : null);
      if (!ev) return;
      const card = ev.querySelector('.evc');
      card.style.left = '0px';
      const w = card.offsetWidth;
      const anchor = ev.getBoundingClientRect().left;
      const box = ch.getBoundingClientRect();
      const minL = Math.max(box.left, 12);
      const maxR = Math.min(box.right, innerWidth - 12);
      let left = anchor - w / 2;
      left = Math.max(minL, Math.min(left, maxR - w));
      card.style.left = `${Math.round(left - anchor)}px`;
    };
    evs.forEach((ev) => {
      const dot = ev.querySelector('.dot');
      dot.addEventListener('pointerenter', (e) => { if (e.pointerType === 'mouse' && !pinned) open(ev); });
      ev.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse' && !pinned) open(null); });
      dot.addEventListener('click', () => {
        pinned = pinned === ev ? null : ev;
        open(pinned);
      });
      dot.addEventListener('focus', () => { if (!pinned) open(ev); });
      dot.addEventListener('blur', () => { if (!pinned) open(null); });
    });
    document.addEventListener('click', (e) => {
      if (pinned && !e.target.closest('.ev')) { pinned = null; open(null); }
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && evs.some((x) => x.classList.contains('open'))) { pinned = null; open(null); }
    });
  });

  // Reported-price dots: pointer picks the nearest dot.
  const initDots = (scope) => scope.querySelectorAll('.dotc').forEach((box) => {
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

  // TradingView price line, drawn in the current light or dark colours.
  function initTV(scope) {
    scope.querySelectorAll('[data-tv]').forEach((box) => {
      if (box.dataset.done) return;
      box.dataset.done = '1';
      const { s, n } = JSON.parse(box.dataset.tv);
      const d = dark();
      const wrap = box.querySelector('.tradingview-widget-container');
      wrap.querySelectorAll('script').forEach((x) => x.remove());
      wrap.querySelector('.tradingview-widget-container__widget').textContent = '';
      const line = d ? '#ECEDEF' : '#0E1116';
      const sc = document.createElement('script');
      sc.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js';
      sc.async = true;
      sc.textContent = JSON.stringify({
        symbols: [[n, `${s}|12M`]], chartOnly: false, autosize: true, width: '100%', height: '100%', locale: 'kr', colorTheme: d ? 'dark' : 'light',
        showVolume: false, showMA: true, maLength: 200, maLineColor: d ? 'rgba(163,168,177,0.85)' : 'rgba(110,117,129,0.85)', maLineWidth: 1,
        hideDateRanges: false, hideMarketStatus: true, hideSymbolLogo: true, scalePosition: 'right', scaleMode: 'Normal',
        fontFamily: 'Pretendard, sans-serif', fontSize: '11', noTimeScale: false, valuesTracking: '1',
        changeMode: 'price-and-percent', chartType: 'line', lineWidth: 2, lineType: 0,
        color: line, lineColor: line, upColor: line, downColor: line,
        dateRanges: ['3m|1D', '12m|1D', '60m|1W'], backgroundColor: d ? '#0C0D10' : '#FFFFFF', gridLineColor: 'rgba(0,0,0,0)',
        fontColor: d ? '#A3A8B1' : '#4B5260', widgetFontColor: d ? '#ECEDEF' : '#0E1116',
      });
      wrap.appendChild(sc);
    });
  }

  const init = (scope) => { initDots(scope); initTV(scope); };
  init(document);

  // Tapping a company name opens its chart in a sheet; it stays a normal link without JS.
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
