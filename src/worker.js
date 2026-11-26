import EVENTS from './events.json';
import { company, feed, home, notFound, pop, rank, search, textPage } from './pages.js';

const HTML = { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'public, max-age=60' };

async function data(env, path) {
  const r = await fetch(`${env.DATA_BASE}/${path}`, { cf: { cacheTtl: 60, cacheEverything: true } });
  if (!r.ok) return null;
  try {
    return await r.json();
  } catch {
    return null;
  }
}

const page = (html, status = 200) => new Response(html, { status, headers: HTML });

async function sitemap(env, origin) {
  const [kr, us] = await Promise.all([data(env, 'kr_index.json'), data(env, 'us_index.json')]);
  const urls = ['/', '/us/', '/feed/', '/us/feed/', '/rank/', '/us/rank/', '/about/', '/sources/', '/privacy/',
    ...(kr || []).map(([k]) => `/c/${encodeURIComponent(k)}/`),
    ...(us || []).map(([k]) => `/u/${encodeURIComponent(k)}/`)];
  const body = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls.map((u) => `<url><loc>${origin}${u}</loc></url>`).join('')}</urlset>`;
  return new Response(body, { headers: { 'content-type': 'application/xml; charset=utf-8', 'cache-control': 'public, max-age=3600' } });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const p = url.pathname;
    const e = { ...env, ORIGIN: url.origin };

    if (p.length > 1 && !p.endsWith('/') && !p.includes('.')) {
      return Response.redirect(`${url.origin}${p}/${url.search}`, 301);
    }
    const pk = url.searchParams.get('p') === '2w' ? '2w' : '1m';
    if (p === '/') return page(home(e, 'kr', await data(env, 'kr.json'), pk, EVENTS.items));
    if (p === '/us/') return page(home(e, 'us', await data(env, 'us.json'), pk, EVENTS.items));
    if (p === '/feed/') return page(feed(e, 'kr', await data(env, 'kr.json'), url.searchParams.get('t')));
    if (p === '/us/feed/') return page(feed(e, 'us', await data(env, 'us.json'), url.searchParams.get('t')));
    if (p === '/rank/') return page(rank(e, 'kr', await data(env, 'kr.json'), pk));
    if (p === '/us/rank/') return page(rank(e, 'us', await data(env, 'us.json'), pk));
    if (p === '/about/' || p === '/sources/' || p === '/privacy/') return page(textPage(e, p.slice(1, -1)));

    const x = p.match(/^\/x\/(c|u)\/([A-Za-z0-9.\-]{1,20})\/$/);
    if (x) {
      const c = await data(env, `${x[1]}/${x[2]}.json`);
      if (!c) return new Response('', { status: 404 });
      return new Response(pop(e, x[1] === 'c' ? 'kr' : 'us', c), { headers: { ...HTML, 'x-robots-tag': 'noindex' } });
    }
    const m = p.match(/^\/(c|u)\/([A-Za-z0-9.\-]{1,20})\/$/);
    if (m) {
      const c = await data(env, `${m[1]}/${m[2]}.json`);
      return c ? page(company(e, m[1] === 'c' ? 'kr' : 'us', c)) : page(notFound(e), 404);
    }
    if (p === '/search/') {
      const q = (url.searchParams.get('q') || '').trim().slice(0, 40);
      const [kr, us] = await Promise.all([data(env, 'kr_index.json'), data(env, 'us_index.json')]);
      return page(search(e, q, kr, us));
    }
    if (p === '/data/kr_index.json' || p === '/data/us_index.json') {
      const j = await data(env, p.slice(6));
      return new Response(JSON.stringify(j || []), { headers: { 'content-type': 'application/json', 'cache-control': 'public, max-age=600' } });
    }
    if (p === '/sitemap.xml') return sitemap(env, url.origin);
    if (p === '/robots.txt') {
      return new Response(`User-agent: *\nAllow: /\nDisallow: /x/\nSitemap: ${url.origin}/sitemap.xml\n`, { headers: { 'content-type': 'text/plain' } });
    }
    return page(notFound(e), 404);
  },
};
