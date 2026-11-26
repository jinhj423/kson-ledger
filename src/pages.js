import { chart, dayLabel, esc, eventsFor, feedTable, heroSentence, layout, prevNetText, priceSection, rankTable, recordTable, SITE } from './ui.js';

const MKNAME = { kr: '한국', us: '미국' };
const PER = [['2w', '2주'], ['1m', '1달']];

// The chosen period's numbers (older data files have only one 5-day block at the top level).
function period(s, pk) {
  const P = (s.p && s.p[pk]) || s;
  return { P, w: P.w, label: P.w.label || '5거래일' };
}

function periodSeg(s, pk, base) {
  if (!s.p) return '';
  return `<nav class="seg" aria-label="기간">${PER.map(([k, l]) => `<a href="${base}${k === '1m' ? '' : `?p=${k}`}"${k === pk ? ' class="on" aria-current="true"' : ''}>${l}</a>`).join('')}</nav>`;
}

function bigNumber(mk, w) {
  let v = Math.abs(w.net);
  let unit = mk === 'us' ? 'M' : '억원';
  if (mk === 'us' && v >= 1000) { v = Math.round(v / 100) / 10; unit = 'B'; }
  if (mk === 'kr' && v >= 10000) { v = Math.round(v / 1000) / 10; unit = '조원'; }
  const dec = v >= 100 ? 0 : 1;
  const sign = w.net > 0 ? '+' : w.net < 0 ? '−' : '';
  const pre = sign + (mk === 'us' ? '$' : '');
  const shown = pre + v.toLocaleString('ko-KR', { minimumFractionDigits: dec, maximumFractionDigits: dec });
  return `<p class="big"><span data-count="${v}" data-dec="${dec}" data-pre="${esc(pre)}">${esc(shown)}</span><small>${unit}</small></p>`;
}

function waiting(env, mk, path) {
  const body = `<section class="page"><h1>자료를 모으고 있어요</h1><p class="lede">${MKNAME[mk]} 공시를 처음 모으는 중이에요. 10분마다 새로 받아오니 잠시 뒤에 다시 들러 주세요.</p></section>`;
  return layout(env, { title: `${MKNAME[mk]} 내부자 거래`, desc: '임원·대주주가 사고판 기록을 공시 원문 그대로 정리합니다.', path, mk, active: 'home', body });
}

const sh = (title, right = '', tagName = 'h2') => `<div class="sh">${title ? `<${tagName}>${title}</${tagName}>` : ''}${right}</div>`;

function filterTabs(mk, base, pick) {
  const keys = mk === 'kr' ? ['buy', 'sell', 'major', 'buyback', 'control'] : ['buy', 'sell'];
  const names = { buy: '샀어요', sell: '팔았어요', major: '지분 5%', buyback: '자사주', control: '최대주주' };
  return `<nav class="tabs" aria-label="공시 종류">${[['', '전체'], ...keys.map((k) => [k, names[k]])]
    .map(([k, l]) => `<a href="${base}${k ? `?t=${k}` : ''}"${k === pick ? ' class="on" aria-current="true"' : ''}>${l}</a>`).join('')}</nav>`;
}

export function home(env, mk, s, pk = '1m', allEvents = []) {
  const path = mk === 'kr' ? '/' : '/us/';
  if (!s || !s.series || s.series.length < 2) return waiting(env, mk, path);
  const { P, w, label } = period(s, pk);
  const feedHref = mk === 'kr' ? '/feed/' : '/us/feed/';
  const rankHref = `${mk === 'kr' ? '/rank/' : '/us/rank/'}${pk === '1m' ? '' : `?p=${pk}`}`;
  const buys = (mk === 'us' && P.rankBuyX) ? P.rankBuyX : P.rankBuy;
  const prev = w.hasPrev ? ` 그 전 ${label}은 ${esc(prevNetText(mk, w))}이었어요.` : '';
  const evs = eventsFor(mk, P.series, allEvents);
  const lb = buys.slice(0, 4).map((k) => `<li><span class="n">${k.n}</span><a class="c" href="${esc(k.link)}" data-pop>${esc(k.co)}</a><span class="v">${esc(k.v)}</span></li>`).join('');
  const facts = [
    ['장내매수 보고', w.buyN, w.hasPrev ? `그 전 ${w.prevBuyN}` : '건'],
    ['장내매도 보고', w.sellN, w.hasPrev ? `그 전 ${w.prevSellN}` : '건'],
    ['여럿이 같이 산 회사', w.clusterN, '곳'],
  ];
  if (mk === 'kr' && w.majorN != null) facts.push(['5% 보유 보고', w.majorN, '건']);
  const unit = mk === 'kr' ? '원' : '';
  const cl = P.clusters.slice(0, 6).map((c) => `<tr><td class="co"><a href="${esc(c.link)}">${esc(c.co)}</a></td><td class="r">${c.n}명</td><td class="r v buy">${esc(c.amt)}</td></tr>`).join('');

  const body = `<section class="hero">
<div class="hl">
<p class="k">최근 ${label} ${mk === 'us' ? '미국 ' : ''}내부자 순매수, ${dayLabel(w.from)}부터 ${dayLabel(w.to)}까지</p>
${bigNumber(mk, w)}
<p class="sent">${esc(heroSentence(mk, w.net))}${prev}</p>
${periodSeg(s, pk, path)}
</div>
<div class="lb">
<h2>최근 ${label} 내부자가 많이 산 회사</h2>
<ol>${lb}</ol>
<p class="lbm"><span>장내매수 금액에서 매도 금액을 뺀 순서</span><a href="${rankHref}">랭킹 전체 보기</a></p>
</div>
</section>
${chart(P.series, evs)}
<p class="note">막대 하나가 하루예요. 장내에서 산 금액에서 판 금액을 뺐어요(보고일 기준).${evs.length ? ' 아래 점은 그날 있었던 금리 결정과 큰 시장 일이에요. 점에 마우스를 올리거나 누르면 설명이 열려요.' : ''}</p>
<div class="facts">${facts.map(([l, v, u]) => `<div><p>${l}</p><b>${Number(v).toLocaleString('ko-KR')}<small>${u}</small></b></div>`).join('')}</div>

<section class="sec">${sh('실시간 공시', filterTabs(mk, feedHref, ''))}
${feedTable(s.feed.slice(0, 12))}
<p class="more"><span class="muted">${s.updated ? `${esc(s.updated.slice(5, 10).replace('-', '.'))} ${esc(s.updated.slice(11, 16))} 업데이트` : ''}</span><a href="${feedHref}">공시 더 보기</a></p>
</section>

<div class="tri">
<section>${sh('많이 산 회사', `<a class="lnk" href="${rankHref}">전체 보기</a>`)}${rankTable(buys.slice(0, 8), 'buy')}</section>
<section>${sh('많이 판 회사', `<a class="lnk" href="${rankHref}">전체 보기</a>`)}${rankTable(P.rankSell.slice(0, 8), 'sell')}</section>
<section>${sh('여럿이 같이 산 회사')}${cl ? `<table class="tbl cl"><thead><tr><th>회사</th><th class="r">내부자</th><th class="r">장내매수${unit ? `(${unit})` : ''}</th></tr></thead><tbody>${cl}</tbody></table>` : `<p class="empty">최근 ${label} 동안에는 없어요.</p>`}</section>
</div>`;
  const desc = mk === 'kr'
    ? `최근 ${label} 국내 상장사 내부자 순매수 ${w.netTxt}. 임원·주요주주·5% 보유자의 장내매수·매도 공시를 매일 정리합니다.`
    : `최근 ${label} 미국 내부자(Form 4) 순매수 ${w.netTxt}. 임원·이사·10% 주주의 장내매수·매도를 정리합니다.`;
  return layout(env, { title: mk === 'kr' ? '' : '미국 내부자 거래', desc, path, mk, active: 'home', body });
}

export function feed(env, mk, s, t) {
  const path = mk === 'kr' ? '/feed/' : '/us/feed/';
  if (!s) return waiting(env, mk, path);
  const keys = mk === 'kr' ? ['buy', 'sell', 'major', 'buyback', 'control'] : ['buy', 'sell'];
  const pick = keys.includes(t) ? t : '';
  const match = (r) => !pick || r.kind === pick || (pick === 'buy' && r.kind === 'mixed' && r.dk === 'buy') || (pick === 'sell' && r.kind === 'mixed' && r.dk === 'sell');
  const rows = s.feed.filter(match);
  const body = `<section class="page">
<h1>${MKNAME[mk]} 실시간 공시</h1>
<p class="lede">최근 공시 ${s.feed.length}건 중 ${rows.length}건이에요. 회사 이름을 누르면 그 회사의 기록을 모아 볼 수 있어요.</p>
${sh('', filterTabs(mk, path, pick))}
${feedTable(rows)}
</section>`;
  return layout(env, { title: `${MKNAME[mk]} 실시간 공시`, desc: `${MKNAME[mk]} 상장사 임원·대주주의 최근 주식 거래 공시 목록.`, path: path + (pick ? `?t=${pick}` : ''), mk, active: 'feed', body });
}

export function rank(env, mk, s, pk = '1m') {
  const path = mk === 'kr' ? '/rank/' : '/us/rank/';
  if (!s) return waiting(env, mk, path);
  const { P, w, label } = period(s, pk);
  const buys = (mk === 'us' && P.rankBuyX) ? P.rankBuyX : P.rankBuy;
  const unit = mk === 'kr' ? '원' : '';
  const cl = P.clusters.map((c) => `<tr><td class="co"><a href="${esc(c.link)}">${esc(c.co)}</a></td><td class="r">${c.n}명</td><td class="r v buy">${esc(c.amt)}${unit}</td></tr>`).join('');
  const body = `<section class="page">
<div class="ph"><div><h1>최근 ${label} 내부자 순매수 랭킹</h1><p class="lede">${dayLabel(w.from)}부터 ${dayLabel(w.to)}까지, 내부자가 장내에서 산 금액에서 판 금액을 뺀 순서예요.${mk === 'us' ? ' 미국은 펀드·신탁 이름의 보고와 10% 주주만의 보고를 빼고 임원·이사 매수만 셌어요.' : ''}</p></div>${periodSeg(s, pk, path)}</div>
<div class="duo">
<section>${sh('많이 산 회사')}${rankTable(buys, 'buy')}</section>
<section>${sh('많이 판 회사')}${rankTable(P.rankSell, 'sell')}</section>
</div>
<section class="sec" id="cluster">${sh('여럿이 같이 산 회사', `<span class="muted">같은 ${label} 안에 서로 다른 내부자 3명 이상이 장내에서 산 회사</span>`)}
${cl ? `<table class="tbl cl"><thead><tr><th>회사</th><th class="r">내부자</th><th class="r">장내매수</th></tr></thead><tbody>${cl}</tbody></table>` : `<p class="empty">최근 ${label} 동안에는 내부자 3명 이상이 같이 산 회사가 없어요.</p>`}
</section>
</section>`;
  return layout(env, { title: `${MKNAME[mk]} 내부자 순매수 랭킹`, desc: `최근 ${label} ${MKNAME[mk]} 내부자 순매수·순매도 상위 회사.`, path: path + (pk === '1m' ? '' : `?p=${pk}`), mk, active: 'rank', body });
}

const chartSec = (c, mk) => (c.tv || (c.price && c.price.pts && c.price.pts.length)
  ? `<section class="sec">${sh('주가와 내부자 거래 단가')}${priceSection(c, mk)}</section>`
  : '');

// Popup body (fetched by app.js when a company name is tapped).
export function pop(env, mk, c) {
  const full = mk === 'kr' ? `/c/${c.key}/` : `/u/${c.key}/`;
  const rows = (c.events || []).slice(0, 4);
  return `<div class="pop-in">
<div class="pop-h"><div><p class="muted">${esc(c.cls)}</p><h2 id="pop-t">${esc(c.co)}</h2></div>
<button type="button" class="x" data-close aria-label="닫기"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 4l10 10M14 4L4 14"/></svg></button></div>
${priceSection(c, mk)}
${rows.length ? `<h3 class="dh">최근 공시</h3>${recordTable(rows)}` : ''}
<a class="btn" href="${full}">${esc(c.co)} 기록 전체 보기</a>
</div>`;
}

export function company(env, mk, c) {
  const path = mk === 'kr' ? `/c/${c.key}/` : `/u/${c.key}/`;
  const src = mk === 'kr'
    ? `<a class="pill" href="https://dart.fss.or.kr/dsab007/main.do?textCrpNm=${encodeURIComponent(c.co)}" rel="noopener" target="_blank">DART에서 공시 보기</a>`
    : `<a class="pill" href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&amp;CIK=${encodeURIComponent(c.key)}&amp;type=4" rel="noopener" target="_blank">SEC에서 Form 4 보기</a>`;
  if (!c.events.length) {
    const body = `<section class="hero co"><div class="hl"><p class="k">${esc(c.cls)}${c.cls ? ', ' : ''}최근 장내 매수·매도 없음</p><h1 class="coname">${esc(c.co)}</h1>
<p class="sent">이 회사 내부자는 최근(마지막 보고 ${esc(c.lastOther || '')}) Form 4를 냈지만, 주식 보상·옵션 행사·세금 납부·증여처럼 장내 매수(P)나 매도(S)가 아닌 보고였어요. ${SITE}는 장내 매수·매도만 금액에 넣어요.</p>${src}</div></section>
${chartSec(c, mk)}`;
    return layout(env, { title: `${c.co} 내부자 거래`, desc: `${c.co} 최근 내부자 장내 매수·매도 보고 없음.`, path, mk, body });
  }
  const sign = c.netV > 0 ? 'up' : c.netV < 0 ? 'dn' : '';
  const u = mk === 'kr' ? '원' : '';
  const lean = c.netV < 0 ? '산 것보다 판 것이 많았어요' : c.netV > 0 ? '판 것보다 산 것이 많았어요' : '산 금액과 판 금액이 같았어요';
  const body = `<section class="hero co"><div class="hl">
<p class="k">${esc(c.cls)}${c.cls ? ', ' : ''}최근 90일 내부자 장내거래</p>
<h1 class="coname">${esc(c.co)}</h1>
<p class="big sm ${sign}">${esc(c.net)}<small>${u}</small></p>
<p class="sent">내부자 ${c.people}명이 ${esc(c.buy)}${u}어치 사고 ${esc(c.sell)}${u}어치 팔아, ${lean}.</p>
</div></section>
<div class="facts"><div><p>산 금액</p><b class="up">${esc(c.buy)}<small>${u}</small></b></div><div><p>판 금액</p><b class="dn">${esc(c.sell)}<small>${u}</small></b></div><div><p>거래한 내부자</p><b>${c.people}<small>명</small></b></div><div><p>공시</p><b>${c.count}<small>건</small></b></div></div>
${chartSec(c, mk)}
<section class="sec">${sh('공시 기록', src)}${recordTable(c.events)}</section>`;
  return layout(env, {
    title: `${c.co} 내부자 거래`,
    desc: `${c.co} 임원·대주주의 최근 90일 장내매수 ${c.buy}, 장내매도 ${c.sell}. 공시 원문 기준 기록.`,
    path, mk, active: '', body,
  });
}

export function search(env, q, kr, us) {
  const norm = (x) => String(x || '').toLowerCase().replace(/\s+/g, '');
  const k = norm(q);
  const hit = (list, base) => (k ? list.filter(([code, name, ko]) => norm(code) === k || norm(code).startsWith(k) || norm(name).includes(k) || norm(ko).includes(k)).slice(0, 30).map(([code, name, ko]) => `<tr><td class="co"><a href="${base}${encodeURIComponent(code)}/">${esc(ko ? `${name} (${ko.split(' ')[0]})` : name)}</a></td><td class="r muted">${esc(code)}</td></tr>`).join('') : '');
  const a = hit(kr || [], '/c/'), b = hit(us || [], '/u/');
  const body = `<section class="page"><h1>"${esc(q)}" 검색 결과</h1>
${a ? `${sh('한국')}<table class="tbl"><tbody>${a}</tbody></table>` : ''}${b ? `${sh('미국')}<table class="tbl"><tbody>${b}</tbody></table>` : ''}
${a || b ? '' : `<p class="empty">찾지 못했어요. ${SITE}에는 최근 공시가 올라온 회사만 있어요. 한국은 임원·주요주주 소유보고나 5% 보유 보고가, 미국은 Form 4가 최근에 한 번이라도 올라와야 검색돼요.</p>`}</section>`;
  return layout(env, { title: '검색', desc: '회사 검색', path: '/search/', body });
}

const TEXT = {
  about: ['소개', `${SITE} 소개`, `<p>${SITE}는 회사 안의 사람들, 즉 임원·주요주주·5% 이상 보유자가 자기 회사 주식을 사고판 기록을 한곳에 모아 보여주는 사이트예요.</p>
<p>이 정보는 원래 금융감독원 DART와 미국 SEC EDGAR에 공시로 올라오지만, 회사마다 보고서를 하나씩 열어봐야 해서 한눈에 보기 어려워요. ${SITE}는 그 보고서를 10분마다 받아와 회사별·날짜별로 정리해요.</p>
<h2>보여 드리는 것</h2><ul><li>임원·주요주주의 장내매수와 장내매도(수량과 금액)</li><li>5% 이상 대량보유 보고</li><li>자기주식 취득 결정과 최대주주 변경</li><li>미국 상장사 내부자의 Form 4 장내매수·매도</li><li>홈 차트 아래의 금리 결정과 큰 시장 일(공개 보도 두 곳으로 확인한 것만)</li></ul>
<h2>하지 않는 것</h2><p>특정 종목을 추천하거나, 주가를 전망하거나, 수익을 약속하지 않아요. 유료 회원 대화방이나 1:1 상담도 운영하지 않아요. 모든 숫자는 공시에 적힌 내용을 계산한 것이고, 투자 판단은 이용자 본인의 몫이에요.</p>
<h2>운영</h2><p>개인이 운영하는 서비스예요. 잘못된 숫자를 발견하시면 바닥글의 '문의'로 알려 주세요.</p>`],
  sources: ['방법과 출처', '자료를 모으고 계산하는 방법', `<h2>자료 출처</h2><ul><li>주가 차트: TradingView 위젯(지연 시세). ${SITE}는 주가 자료를 받아 저장하거나 가공하지 않아요.</li><li>한국: 금융감독원 전자공시시스템 DART(오픈API). 임원·주요주주 특정증권등 소유상황보고서, 주식등의 대량보유상황보고서, 주요사항보고서(자기주식 취득 결정), 거래소 공시(최대주주 변경).</li><li>미국: SEC EDGAR의 Form 4(임원·이사·10% 주주 소유 변동 보고).</li><li>홈 차트의 이벤트 점: 한국은행·미국 연준 발표와 언론 보도. 날짜와 숫자는 두 곳에서 같을 때만 싣고, 설명 문장은 새로 써요. 각 점에 출처 링크가 있어요.</li></ul>
<h2>계산 방법</h2><ul><li>한국 장내매수·장내매도는 보고서 원문의 '세부변동내역' 표에서 보고사유가 장내매수·장내매도인 줄만 셉니다. 증여·상속·장외거래·주식보상 등은 금액에 넣지 않아요.</li><li>금액은 보고서에 적힌 취득·처분 단가 × 수량이에요. 단가가 없는 줄은 수량만 보여 드려요.</li><li>미국은 Form 4의 거래 코드 P(장내매수)와 S(장내매도)만 셉니다. 스톡옵션 행사(M) 등은 빼요.</li><li>날짜는 공시가 올라온 날(보고일) 기준이에요. 실제 거래일은 보고일보다 며칠 앞설 수 있어요.</li><li>'최근 2주'와 '최근 1달'은 공시가 올라온 평일 기준 가장 최근 10일과 20일이에요. '그 전 1달'과의 비교는 그 기간 자료가 다 모였을 때만 보여 드려요.</li><li>'여럿이 같이 산 회사'는 같은 기간 안에 서로 다른 보고자 3명 이상이 장내매수한 회사예요.</li><li>회사 화면의 점은 보고서에 적힌 거래일과 단가예요. 점선은 최근 90일 장내매수·장내매도의 수량 가중 평균 단가예요.</li><li>정정 공시는 이중 계산을 막기 위해 지금은 반영하지 않아요.</li></ul>
<h2>한계</h2><p>자료는 약 10분 간격으로 받아오므로 공시 직후에는 아직 보이지 않을 수 있어요. 원문 형식이 특이한 보고서는 금액이 빠질 수 있으니, 중요한 내용은 각 줄의 '원문'으로 확인해 주세요.</p>`],
  privacy: ['개인정보처리방침', '개인정보처리방침', `<p>${SITE}는 회원가입, 댓글, 결제 기능이 없어 이용자의 개인정보를 따로 받지 않아요.</p>
<h2>자동으로 남는 정보</h2><p>사이트를 운영하는 Cloudflare가 보안과 장애 대응을 위해 접속 기록(IP 주소, 접속 시각, 브라우저 정보)을 일정 기간 보관할 수 있어요. ${SITE}는 이 기록으로 이용자를 식별하지 않아요.</p>
<h2>브라우저 저장소, 쿠키와 광고</h2><p>${SITE}는 쿠키를 쓰지 않아요. 밝은 화면과 어두운 화면 중 고른 것은 이용자 브라우저 안에만 저장되고 서버로 보내지 않아요. 회사 주가 차트는 TradingView 위젯으로 보여 드리는데, 차트가 열리면 TradingView가 자체 쿠키를 쓸 수 있고 이는 TradingView의 개인정보처리방침을 따라요. 앞으로 Google 애드센스 같은 광고를 붙이면 광고 사업자도 쿠키를 쓸 수 있고, 이 방침을 그 전에 고쳐 알려 드릴게요.</p>
<h2>공시에 나오는 이름</h2><p>보고자 이름과 직위는 DART·SEC에 법에 따라 공개된 공시 내용을 그대로 옮긴 것이에요. 사람별로 따로 모은 페이지는 만들지 않아요.</p><p>개인정보 보호법 제20조에 따라, 공시에 이름이 나온 분이 요청하시면 수집 출처(금융감독원 DART 또는 미국 SEC EDGAR)와 처리 목적(공시 내용 정리·게시)을 알려 드리고, 처리 정지 요청을 받아 처리해요. 바닥글의 '문의'로 연락해 주세요.</p>
<h2>문의</h2><p>바닥글의 '문의'로 연락해 주세요.</p><p class="muted">시행일: 2026년 11월 15일</p>`],
};

export function textPage(env, key) {
  const [title, h1, html] = TEXT[key];
  return layout(env, { title, desc: `${SITE} ${title}`, path: `/${key}/`, body: `<article class="page prose"><h1>${h1}</h1>${html}</article>` });
}

export function notFound(env) {
  return layout(env, { title: '페이지를 찾을 수 없어요', desc: '없는 페이지', path: '/404', body: `<section class="page"><h1>페이지를 찾을 수 없어요</h1><p class="lede">주소가 바뀌었거나, 최근 공시가 없는 회사일 수 있어요.</p><a class="btn" href="/">홈으로 가기</a></section>` });
}
