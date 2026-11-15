// Shared HTML pieces. Every dynamic string goes through esc().
export const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export const SITE = '큰손일지';

export function dayLabel(iso) {
  if (!iso) return '';
  const [, m, d] = iso.split('-').map(Number);
  return `${m}월 ${d}일`;
}

const MK = { kr: { home: '/', feed: '/feed/', rank: '/rank/' }, us: { home: '/us/', feed: '/us/feed/', rank: '/us/rank/' } };

function header(mk, active) {
  const p = MK[mk];
  const nav = [['home', '홈', p.home], ['feed', '실시간 공시', p.feed], ['rank', '랭킹', p.rank]]
    .map(([k, label, href]) => `<a href="${href}"${k === active ? ' class="on" aria-current="page"' : ''}>${label}</a>`)
    .join('');
  return `<header class="hdr wrap">
<a class="logo" href="/"><span class="mark" aria-hidden="true">큰</span><span>${SITE}</span></a>
<nav class="nav" aria-label="주 메뉴">${nav}</nav>
<div class="tools">
<form class="search" action="/search/" method="get" role="search">
<svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="7" cy="7" r="5"/><path d="M11 11l3.5 3.5"/></svg>
<label class="sr" for="q">회사 검색</label>
<input id="q" name="q" type="search" placeholder="회사 이름이나 종목코드" autocomplete="off">
<ul class="sugg" hidden></ul>
</form>
<div class="seg" role="group" aria-label="시장">
<a href="/"${mk === 'kr' ? ' class="on" aria-current="true"' : ''}>한국</a><a href="/us/"${mk === 'us' ? ' class="on" aria-current="true"' : ''}>미국</a>
</div>
</div>
</header>`;
}

function footer(env) {
  const issues = env.REPO_URL ? `${env.REPO_URL}/issues` : '#';
  return `<section class="wrap sources"><p>공시는 이 공개 자료만 씁니다</p><div><span>금융감독원 DART</span><span>미국 SEC EDGAR</span><span>주가 차트 TradingView</span></div></section>
<footer class="wrap foot">
<p>${SITE}는 금융감독원 DART와 미국 SEC EDGAR에 공개된 공시를 정리해 보여주는 정보 서비스예요. 특정 종목을 사거나 팔라고 권하지 않으며, 투자 판단과 그 결과는 이용자 본인에게 있어요. 공시 원문과 다를 수 있으니 중요한 내용은 원문으로 확인해 주세요.</p>
<nav aria-label="사이트 정보"><a href="/about/">소개</a><a href="/sources/">방법과 출처</a><a href="/privacy/">개인정보처리방침</a><a href="${esc(issues)}" rel="noopener">문의</a></nav>
</footer>`;
}

export function layout(env, { title, desc, path, mk = 'kr', active = '', body, glow = '' }) {
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
<title>${esc(full)}</title>
<meta name="description" content="${esc(desc)}">
<link rel="canonical" href="${esc(url)}">
<meta property="og:type" content="website"><meta property="og:site_name" content="${SITE}">
<meta property="og:title" content="${esc(full)}"><meta property="og:description" content="${esc(desc)}"><meta property="og:url" content="${esc(url)}">
<meta name="theme-color" content="#08090C">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800&family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap">
<link rel="stylesheet" href="/app.css">
${ads}
</head>
<body>
<div class="glow">${header(mk, active)}${glow}</div>
<main class="wrap">${body}</main>
${footer(env)}
<script src="/app.js" defer></script>
</body>
</html>`;
}

export function feedRow(r) {
  const time = r.time ? `, ${esc(r.time)}` : '';
  const inner = `<span class="av" aria-hidden="true">${esc(r.i)}</span>
<span class="rm"><span class="nm">${esc(r.co)}</span><span class="sb">${esc(r.sub)}${time}</span></span>
<span class="ra"><span class="am">${esc(r.amt)}</span><span class="dv ${esc(r.dk)}">${esc(r.d)}</span></span>`;
  return r.link ? `<a class="row" href="${esc(r.link)}" data-pop>${inner}</a>` : `<div class="row">${inner}</div>`;
}

export function rankRows(rows, cls) {
  if (!rows.length) return '<p class="empty">아직 해당하는 회사가 없어요.</p>';
  return rows
    .map((k) => `<a class="rrow" href="${esc(k.link)}" data-pop><span class="rn${k.n <= 3 ? ' top' : ''}">${k.n}</span><span class="av sm" aria-hidden="true">${esc(k.i)}</span><span class="rm"><span class="nm">${esc(k.co)}</span><span class="sb">${esc(k.sub)}</span></span><span class="rv ${cls}">${esc(k.v)}</span></a>`)
    .join('');
}

// Smooth line + area split at zero (SVG viewBox 1000 x H, stretched horizontally).
export function chart(series, H = 240) {
  const vs = series.map((s) => s.v);
  let max = Math.max(0, ...vs);
  let min = Math.min(0, ...vs);
  if (max === min) { max += 1; min -= 1; }
  const pad = 18;
  const n = vs.length;
  const X = (i) => (n > 1 ? (i / (n - 1)) * 1000 : 500);
  const Y = (v) => pad + ((max - v) / (max - min)) * (H - pad * 2);
  const P = vs.map((v, i) => [X(i), Y(v)]);
  const f = (x) => x.toFixed(1);
  let d = `M${f(P[0][0])},${f(P[0][1])}`;
  for (let i = 0; i < n - 1; i++) {
    const p0 = P[i - 1] || P[i], p1 = P[i], p2 = P[i + 1], p3 = P[i + 2] || p2;
    d += ` C${f(p1[0] + (p2[0] - p0[0]) / 6)},${f(p1[1] + (p2[1] - p0[1]) / 6)} ${f(p2[0] - (p3[0] - p1[0]) / 6)},${f(p2[1] - (p3[1] - p1[1]) / 6)} ${f(p2[0])},${f(p2[1])}`;
  }
  const zy = Y(0);
  const pts = series.map((s, i) => ({ x: +(X(i) / 10).toFixed(2), y: +P[i][1].toFixed(1), d: s.d, t: s.txt, up: s.v >= 0 }));
  const last = pts[pts.length - 1];
  return `<div class="chart" style="height:${H}px" data-pts="${esc(JSON.stringify(pts))}">
<svg class="reveal" role="img" aria-label="최근 ${n}거래일 하루 순매수 금액" viewBox="0 0 1000 ${H}" preserveAspectRatio="none">
<defs><clipPath id="cu"><rect x="0" y="-20" width="1000" height="${f(zy + 20)}"/></clipPath><clipPath id="cd"><rect x="0" y="${f(zy)}" width="1000" height="${H + 20}"/></clipPath></defs>
<line class="zero" x1="0" y1="${f(zy)}" x2="1000" y2="${f(zy)}"/>
<path class="a-up" d="${d} L1000,${f(zy)} L0,${f(zy)} Z" clip-path="url(#cu)"/>
<path class="a-dn" d="${d} L1000,${f(zy)} L0,${f(zy)} Z" clip-path="url(#cd)"/>
<path class="l-up" d="${d}" clip-path="url(#cu)"/>
<path class="l-dn" d="${d}" clip-path="url(#cd)"/>
</svg>
<div class="cur" aria-hidden="true"></div>
<div class="dot ${last.up ? 'up' : 'dn'}" style="left:${last.x}%;top:${last.y}px" aria-hidden="true"></div>
<div class="tip" aria-hidden="true"><span></span><b></b></div>
<div class="hit"></div>
</div>`;
}

export function xLabels(series) {
  const n = series.length;
  if (!n) return '';
  const idx = [...new Set([0, Math.round((n - 1) / 4), Math.round((n - 1) / 2), Math.round((3 * (n - 1)) / 4), n - 1])];
  return `<div class="xl" aria-hidden="true">${idx
    .map((i) => {
      const x = n > 1 ? (i / (n - 1)) * 100 : 50;
      const al = i === 0 ? 'left:0' : i === n - 1 ? 'right:0' : `left:${x.toFixed(2)}%;transform:translateX(-50%)`;
      return `<span style="${al}">${esc(series[i].d.slice(0, 5))}</span>`;
    })
    .join('')}</div>`;
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
    return `<div class="tvlink"><p>한국 종목 주가 차트는 다른 사이트에서 열려요.</p>
<div><a class="more ghost" href="https://finance.naver.com/item/main.naver?code=${encodeURIComponent(code)}" rel="noopener nofollow" target="_blank">네이버 증권에서 주가 보기</a>
<a class="more ghost" href="${page}" rel="noopener nofollow" target="_blank">TradingView에서 주가 보기</a></div></div>`;
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
  return `<div class="dotc" style="height:${H}px" data-pts="${esc(JSON.stringify(pts))}" role="img" aria-label="최근 90일 내부자 보고 단가 ${pts.length}건">
<svg viewBox="0 0 1000 ${H}" preserveAspectRatio="none" aria-hidden="true">${lines}</svg>
${labels}${dots}
<div class="tip" aria-hidden="true"><span></span><b></b><small></small></div>
<div class="hit"></div>
</div>
<div class="xl" aria-hidden="true"><span style="left:0">${dayLabel(pr.from)}</span><span style="left:50%;transform:translateX(-50%)">${dayLabel(mid)}</span><span style="right:0">${dayLabel(pr.to)}</span></div>
<div class="legend"><span><i class="b"></i>장내매수</span><span><i class="s"></i>장내매도</span><span><i class="avg"></i>90일 평균 단가</span></div>
<p class="note">보고서에 적힌 거래일과 단가예요. 점이 클수록 거래 금액이 커요. 점을 누르거나 마우스를 올리면 누가 얼마에 거래했는지 보여요.</p>`;
}

export function priceSection(c, mk) {
  return `<div class="pchart">${tvBlock(c)}<h3 class="dh">내부자가 보고한 거래 단가, 최근 90일</h3>${tradeDots(c.price, mk)}</div>`;
}
