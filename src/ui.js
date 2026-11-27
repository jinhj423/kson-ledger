// Shared HTML pieces. Every dynamic string goes through esc().
export const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export const SITE = '큰손일지';

export function dayLabel(iso) {
  if (!iso) return '';
  const [, m, d] = iso.split('-').map(Number);
  return `${m}월 ${d}일`;
}

// ---------- numbers ----------
// "+353억", "−1.2조", "+$103.9B" -> size in 억 (kr) or $M (us), for bar lengths.
const SCALE = { 조: 10000, 억: 1, 만: 0.0001, B: 1000, M: 1, K: 0.001 };
export function magnitude(s) {
  const m = String(s ?? '').replace(/,/g, '').match(/([\d.]+)\s*(조|억|만|B|M|K)?/);
  if (!m) return 0;
  return +(parseFloat(m[1]) * (SCALE[m[2]] ?? 1)).toPrecision(6);
}

export function netText(mk, v) {
  const sign = v > 0 ? '+' : v < 0 ? '−' : '';
  let a = Math.abs(v);
  if (mk === 'us') {
    const unit = a >= 1000 ? 'B' : 'M';
    if (unit === 'B') a /= 1000;
    return `${sign}$${a.toFixed(1)}${unit}`;
  }
  if (a >= 10000) return `${sign}${(a / 10000).toFixed(1)}조`;
  return `${sign}${a >= 100 ? Math.round(a).toLocaleString('ko-KR') : a.toFixed(1)}억`;
}

// The earlier period's total, rebuilt from this period's total and the change.
export function prevNetText(mk, w) {
  const diff = magnitude(w.diffTxt);
  return netText(mk, w.diffUp ? w.net - diff : w.net + diff);
}

// Headline amount written out in full: exact total when the data has it, else rebuilt from the rounded one.
export function fullMoney(mk, o, rounded) {
  const amt = Number.isFinite(o && o.netAmt) ? o.netAmt : Math.round(rounded * (mk === 'us' ? 1e6 : 1e8));
  const sign = amt > 0 ? '+' : amt < 0 ? '−' : '';
  const digits = Math.abs(Math.round(amt)).toLocaleString('en-US');
  return mk === 'us' ? { txt: `${sign}$${digits}`, unit: '' } : { txt: `${sign}${digits}`, unit: '원' };
}

export function heroSentence(mk, net) {
  if (!net) return '산 금액과 판 금액이 같아요.';
  const amt = netText(mk, Math.abs(net)).replace(/^\+/, '');
  const shown = mk === 'us' ? amt : `${amt} 원`;
  return net < 0 ? `내부자들이 산 것보다 ${shown} 더 팔았어요.` : `내부자들이 판 것보다 ${shown} 더 샀어요.`;
}

const KINDS = { buy: '장내매수', sell: '장내매도', mixed: '매수와 매도', major: '5% 보고', buyback: '자사주', control: '최대주주 변경', other: '소유 변동' };
export function kindLabel(r) {
  const tone = r.dk === 'buy' || r.dk === 'sell' ? r.dk : '';
  return [KINDS[r.kind] || '공시', tone];
}

const shareChange = (r) => (/%p$/.test(r.d || '') && !/^[+\-−]?0\.00%p$/.test(r.d) ? r.d : '');
const ppCls = (s) => (s.startsWith('+') ? 'up' : s ? 'dn' : '');

// ---------- layout ----------
const MK = { kr: { home: '/', feed: '/feed/', rank: '/rank/' }, us: { home: '/us/', feed: '/us/feed/', rank: '/us/rank/' } };

// Runs before paint: saved choice, otherwise the device setting.
const THEME_BOOT = `(function(){var t;try{t=localStorage.getItem('theme')}catch(e){}if(t!=='light'&&t!=='dark'){t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}document.documentElement.dataset.theme=t})();`;

const SUN = '<svg class="i-sun" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="9" cy="9" r="3.6"/><path d="M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.7 3.7l1.4 1.4M12.9 12.9l1.4 1.4M3.7 14.3l1.4-1.4M12.9 5.1l1.4-1.4"/></svg>';
const MOON = '<svg class="i-moon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M15 10.6A6.5 6.5 0 0 1 7.4 3a6.5 6.5 0 1 0 7.6 7.6Z"/></svg>';

function header(mk, active) {
  const p = MK[mk];
  const nav = [['home', '홈', p.home], ['feed', '실시간 공시', p.feed], ['rank', '랭킹', p.rank]]
    .map(([k, label, href]) => `<a href="${href}"${k === active ? ' class="on" aria-current="page"' : ''}>${label}</a>`)
    .join('');
  return `<header class="hd"><div class="w">
<a class="logo" href="/">${SITE}</a>
<nav class="nav" aria-label="주 메뉴">${nav}</nav>
<form class="search" action="/search/" method="get" role="search">
<label class="sr" for="q">회사 검색</label>
<input id="q" name="q" type="search" placeholder="회사 이름이나 종목코드" autocomplete="off">
<ul class="sugg" hidden></ul>
</form>
<nav class="mk" aria-label="시장"><a href="/"${mk === 'kr' ? ' class="on" aria-current="true"' : ''}>한국</a><a href="/us/"${mk === 'us' ? ' class="on" aria-current="true"' : ''}>미국</a></nav>
<button type="button" class="theme" data-theme-toggle aria-label="화면 색 바꾸기">${SUN}${MOON}</button>
</div></header>`;
}

function footer(env) {
  const issues = env.REPO_URL ? `${env.REPO_URL}/issues` : '#';
  return `<footer class="ft"><div class="w">
<p class="srcs">공시는 금융감독원 DART와 미국 SEC EDGAR, 주가 차트는 TradingView 자료만 써요.</p>
<p>${SITE}는 공개된 공시를 정리해 보여주는 정보 서비스예요. 특정 종목을 사거나 팔라고 권하지 않으며, 투자 판단과 그 결과는 이용자 본인에게 있어요. 공시 원문과 다를 수 있으니 중요한 내용은 원문으로 확인해 주세요.</p>
<nav aria-label="사이트 정보"><a href="/about/">소개</a><a href="/sources/">방법과 출처</a><a href="/privacy/">개인정보처리방침</a><a href="${esc(issues)}" rel="noopener">문의</a></nav>
</div></footer>`;
}

export function layout(env, { title, desc, path, mk = 'kr', active = '', body }) {
  const full = title ? `${title} — ${SITE}` : `${SITE} — 임원·대주주가 사고판 기록`;
  const url = `${env.ORIGIN || ''}${path}`;
  const ads = env.ADSENSE_CLIENT
    ? `<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${esc(env.ADSENSE_CLIENT)}" crossorigin="anonymous"></script>`
    : '';
  return `<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>${THEME_BOOT}</script>
<title>${esc(full)}</title>
<meta name="description" content="${esc(desc)}">
<link rel="canonical" href="${esc(url)}">
<meta property="og:type" content="website"><meta property="og:site_name" content="${SITE}">
<meta property="og:title" content="${esc(full)}"><meta property="og:description" content="${esc(desc)}"><meta property="og:url" content="${esc(url)}">
<meta name="theme-color" content="#FFFFFF" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#0C0D10" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<link rel="stylesheet" href="/app.css">
${ads}
</head>
<body>
${header(mk, active)}
<main class="w">${body}</main>
${footer(env)}
<script src="/app.js" defer></script>
</body>
</html>`;
}

// ---------- tables ----------
const tag = (r) => {
  const [kl, tone] = kindLabel(r);
  return `<span class="tag${tone ? ` ${tone}` : ''}">${kl}</span>`;
};

// Latest filings: one row per report. The company cell opens the company sheet.
export function feedTable(rows, { date = true } = {}) {
  if (!rows.length) return '<p class="empty">이 종류의 공시는 아직 없어요.</p>';
  const body = rows.map((r) => {
    const pp = shareChange(r);
    const co = r.link ? `<a href="${esc(r.link)}" data-pop>${esc(r.co)}</a>` : esc(r.co);
    return `<tr>${date ? `<td class="dt">${esc((r.dl || '').slice(0, 5))}</td>` : ''}<td class="co">${co}</td><td class="tx">${esc(r.sub)}</td><td class="kd">${tag(r)}</td><td class="r am">${esc(r.amt)}</td><td class="r pp ${ppCls(pp)}">${esc(pp) || '—'}</td></tr>`;
  }).join('');
  return `<table class="tbl feed"><thead><tr>${date ? '<th>보고일</th>' : ''}<th>회사</th><th>내용</th><th>구분</th><th class="r">금액·지분율</th><th class="r">지분 변화</th></tr></thead><tbody>${body}</tbody></table>`;
}

// One company's records: who did what, with a link to the filing.
export function recordTable(rows) {
  const body = rows.map((r) => {
    const pp = shareChange(r);
    return `<tr><td class="dt">${esc((r.dl || '').slice(0, 5))}</td><td class="tx strong">${esc(r.sub)}</td><td class="kd">${tag(r)}</td><td class="r am">${esc(r.amt)}</td><td class="r pp ${ppCls(pp)}">${esc(pp) || '—'}</td><td class="r"><a class="src" href="${esc(r.url)}" rel="noopener" target="_blank">원문</a></td></tr>`;
  }).join('');
  return `<table class="tbl rec"><thead><tr><th>보고일</th><th>내용</th><th>구분</th><th class="r">금액·지분율</th><th class="r">지분 변화</th><th class="r"><span class="sr">원문 링크</span></th></tr></thead><tbody>${body}</tbody></table>`;
}

export function rankTable(rows, cls) {
  if (!rows.length) return '<p class="empty">아직 해당하는 회사가 없어요.</p>';
  const top = Math.max(...rows.map((k) => magnitude(k.v)), 1e-9);
  const body = rows.map((k) => {
    const w = Math.max(3, Math.round((magnitude(k.v) / top) * 100));
    return `<tr><td class="n">${k.n}</td><td class="co"><a href="${esc(k.link)}" data-pop>${esc(k.co)}</a></td><td class="sub">${esc(k.sub)}</td><td class="r v ${cls}">${esc(k.v)}</td><td class="mbc"><span class="mb ${cls}" aria-hidden="true"><i style="width:${w}%"></i></span></td></tr>`;
  }).join('');
  return `<table class="tbl rank ${cls}"><tbody>${body}</tbody></table>`;
}

// ---------- events on the daily chart ----------
const md = (iso) => (iso ? `${iso.slice(5, 7)}.${iso.slice(8, 10)}` : '');

// Events of this market that fall on a chart day, with that day's index.
export function eventsFor(mk, series, events) {
  const idx = new Map(series.map((s, i) => [s.d.slice(0, 5), i]));
  return (events || [])
    .filter((e) => e[mk] && idx.has(md(e[mk])))
    .map((e) => ({ ...e, i: idx.get(md(e[mk])) }))
    .sort((a, b) => a.i - b.i);
}

// Daily net-buy bars around a zero line, with event dots sitting on that line.
export function chart(series, events = [], H = 200) {
  const vs = series.map((s) => s.v);
  let max = Math.max(0, ...vs);
  let min = Math.min(0, ...vs);
  if (max === min) { max += 1; min -= 1; }
  const pad = 6;
  const n = vs.length;
  const Y = (v) => pad + ((max - v) / (max - min)) * (H - pad * 2);
  const zy = Y(0);
  const step = 100 / n;
  const f = (x) => x.toFixed(2);
  const pts = series.map((s) => {
    const y = Y(s.v);
    return {
      top: +Math.min(y, zy).toFixed(1), d: s.d, t: s.txt,
      s: s.buyN != null ? `산 보고 ${s.buyN}건, 판 보고 ${s.sellN}건` : '',
    };
  });
  const bars = series.map((s, i) => {
    const y = Y(s.v);
    return `<span class="bar ${s.v >= 0 ? 'up' : 'dn'}" data-i="${i}" style="left:${f(step * i)}%;width:${f(step)}%;top:${Math.min(y, zy).toFixed(1)}px;height:${Math.max(2, Math.abs(zy - y)).toFixed(1)}px"></span>`;
  }).join('');
  const hi = series.reduce((a, s) => (s.v > a.v ? s : a), series[0]);
  const lo = series.reduce((a, s) => (s.v < a.v ? s : a), series[0]);
  const yl = [hi.v > 0 ? `<span class="yl" style="top:${Y(hi.v).toFixed(1)}px">${esc(hi.txt)}</span>` : '',
    lo.v < 0 ? `<span class="yl" style="top:${Y(lo.v).toFixed(1)}px">${esc(lo.txt)}</span>` : ''].join('');
  // Dots sit on the zero line; each opens up or down (alternating), flipping when that side has no room.
  const room = { up: zy - 8, dn: H - zy - 8 };
  const evs = events.map((e, k) => {
    const s = series[e.i];
    let side = k % 2 ? 'dn' : 'up';
    const other = side === 'up' ? 'dn' : 'up';
    if (room[side] < 40 && room[other] > room[side]) side = other;
    const len = Math.max(18, Math.round(room[side]));
    const src = (e.src || []).map((x) => `<a href="${esc(x.u)}" rel="noopener nofollow" target="_blank">${esc(x.t)}</a>`).join('');
    return `<div class="ev ${side} imp${e.imp === 3 ? 3 : 2}" style="left:${f(step * (e.i + 0.5))}%;--len:${len}px" data-i="${e.i}">
<button type="button" class="dot" aria-label="${esc(s.d)} ${esc(e.t)}" aria-expanded="false" aria-controls="ev${k}"></button>
<span class="stem" aria-hidden="true"></span>
<div class="evc" id="ev${k}" role="group" aria-label="${esc(e.t)}"><p class="meta"><b>${esc(e.cat)}</b>${esc(s.d)}</p><p class="tt">${esc(e.t)}</p><p class="ex">${esc(e.x)}</p>
<p class="nb">이날 내부자 순매수 <b class="${s.v >= 0 ? 'u' : 'd'}">${esc(s.txt)}</b></p>${src ? `<p class="es">출처 ${src}</p>` : ''}</div>
</div>`;
  }).join('');
  const idx = [...new Set([0, Math.round((n - 1) / 4), Math.round((n - 1) / 2), Math.round((3 * (n - 1)) / 4), n - 1])];
  const xl = idx.map((i) => `<span style="left:${f(step * (i + 0.5))}%">${esc(series[i].d.slice(0, 5))}</span>`).join('');
  const label = `최근 ${n}거래일 하루 순매수 금액, 가장 많이 산 날 ${hi.txt}, 가장 많이 판 날 ${lo.txt}`;
  return `<div class="chart">
<div class="plot" style="height:${H}px" data-pts="${esc(JSON.stringify(pts))}" role="img" aria-label="${esc(label)}">
<div class="bars reveal">${bars}</div><span class="zero" style="top:${zy.toFixed(1)}px" aria-hidden="true"></span>${yl}
<div class="tip" aria-hidden="true"><span></span><b></b><small></small></div><div class="hit"></div>
${events.length ? `<div class="rail" style="top:${zy.toFixed(1)}px">${evs}</div>` : ''}
</div>
<div class="xl" aria-hidden="true">${xl}</div>
</div>`;
}

// ---------- company chart: TradingView price line (A) + reported trade prices (C) ----------
const won = (v) => `${Math.round(v).toLocaleString('ko-KR')}원`;
const usd = (v) => `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function tvBlock(c) {
  if (!c.tv) return '';
  const page = `https://kr.tradingview.com/symbols/${encodeURIComponent(c.tv.replace(':', '-'))}/`;
  if (c.tv.startsWith('KRX:')) {
    // TradingView does not allow Korea Exchange symbols inside embedded widgets.
    const code = c.tv.slice(4);
    return `<div class="tvlink"><p>주가 차트는 다른 사이트에서 열려요</p>
<a class="pill" href="https://finance.naver.com/item/main.naver?code=${encodeURIComponent(code)}" rel="noopener nofollow" target="_blank">네이버 증권</a>
<a class="pill" href="${page}" rel="noopener nofollow" target="_blank">TradingView</a></div>`;
  }
  return `<div class="tvbox" data-tv="${esc(JSON.stringify({ s: c.tv, n: c.co }))}">
<div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"><p class="muted">주가 차트를 불러오는 중이에요</p></div>
<div class="tradingview-widget-copyright"><a href="${page}" rel="noopener nofollow" target="_blank">${esc(c.co)} 주가 차트</a> by TradingView, 지연 시세</div></div>
</div>`;
}

export function tradeDots(pr, mk) {
  if (!pr || !pr.pts || !pr.pts.length) {
    return '<p class="empty">최근 90일 동안 단가가 적힌 장내 거래 보고가 없어요.</p>';
  }
  const money = mk === 'kr' ? won : usd;
  const H = 190;
  const pad = 22;
  const t0 = Date.parse(pr.from);
  const t1 = Date.parse(pr.to) || t0 + 1;
  const vals = [...pr.pts.map((p) => p.p), pr.avgBuy, pr.avgSell].filter((v) => v > 0);
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  const span = hi - lo || hi * 0.1 || 1;
  lo -= span * 0.15;
  hi += span * 0.15;
  const X = (d) => Math.max(0, Math.min(100, ((Date.parse(d) - t0) / (t1 - t0)) * 100));
  const Y = (v) => pad + ((hi - v) / (hi - lo)) * (H - pad * 2);
  const big = Math.max(...pr.pts.map((p) => p.p * p.q), 1);
  const f = (x) => x.toFixed(1);

  const avgs = [['b', pr.avgBuy, '평균 매수'], ['s', pr.avgSell, '평균 매도']].filter(([, v]) => v > 0);
  const yb = pr.avgBuy > 0 ? Y(pr.avgBuy) : -99;
  const lines = avgs.map(([k, v]) => `<line class="avg ${k}" x1="0" x2="1000" y1="${f(Y(v))}" y2="${f(Y(v))}"/>`).join('');
  const labels = avgs.map(([k, v, t]) => {
    const y = Y(v);
    const below = k === 's' && Math.abs(y - yb) < 24;
    return `<span class="al ${k}" style="top:${f(below ? y + 6 : y - 22)}px">${t} ${esc(money(v))}</span>`;
  }).join('');

  const pts = pr.pts.map((p) => ({
    x: +X(p.d).toFixed(2), y: +Y(p.p).toFixed(1), k: p.k, r: +(4.5 + 4 * Math.sqrt((p.p * p.q) / big)).toFixed(1),
    d: dayLabel(p.d), t: `${p.k === 'b' ? '장내매수' : '장내매도'} ${money(p.p)}`, s: `${p.who ? `${p.who}, ` : ''}${p.q.toLocaleString('ko-KR')}주`,
  }));
  const dots = pts.map((p) => `<span class="pd ${p.k}" style="left:${p.x}%;top:${p.y}px;width:${p.r * 2}px;height:${p.r * 2}px;margin:-${p.r}px 0 0 -${p.r}px"></span>`).join('');
  const mid = new Date((t0 + t1) / 2).toISOString().slice(0, 10);
  const pv = pr.pts.map((p) => p.p);
  const pmax = Math.max(...pv);
  const pmin = Math.min(...pv);
  const ys = [`<span class="yl" style="top:${f(Y(pmax))}px">${esc(money(pmax))}</span>`,
    pmin < pmax ? `<span class="yl" style="top:${f(Y(pmin))}px">${esc(money(pmin))}</span>` : ''].join('');
  return `<div class="dotc" style="height:${H}px" data-pts="${esc(JSON.stringify(pts))}" role="img" aria-label="최근 90일 내부자 보고 단가 ${pts.length}건">
<svg viewBox="0 0 1000 ${H}" preserveAspectRatio="none" aria-hidden="true">${lines}</svg>
${labels}${ys}${dots}
<div class="tip" aria-hidden="true"><span></span><b></b><small></small></div>
<div class="hit"></div>
</div>
<div class="xl" aria-hidden="true"><span style="left:0;transform:none">${dayLabel(pr.from)}</span><span style="left:50%">${dayLabel(mid)}</span><span style="left:auto;right:0;transform:none">${dayLabel(pr.to)}</span></div>
<div class="legend"><span><i class="b"></i>장내매수</span><span><i class="s"></i>장내매도</span><span><i class="avg"></i>90일 평균 단가</span></div>
<p class="note">보고서에 적힌 거래일과 단가예요. 점이 클수록 거래 금액이 커요. 점을 누르거나 마우스를 올리면 누가 얼마에 거래했는지 보여요.</p>`;
}

export function priceSection(c, mk) {
  return `<div class="pchart">${tvBlock(c)}<h3 class="dh">내부자가 보고한 거래 단가, 최근 90일</h3>${tradeDots(c.price, mk)}</div>`;
}
