"""Stored events -> display-ready JSON for the site (site/kr.json, site/us.json, company files, indexes)."""
import collections
import datetime as dt
import os
import re
import shutil

from aliases import US_KO
from common import fmt_krw, fmt_shares, fmt_usd, iga, save_json

DOW = "월화수목금토일"


def _dlabel(d):
    x = dt.date.fromisoformat(d)
    return f"{x:%m.%d} ({DOW[x.weekday()]})"


def _initial(name):
    for ch in name.replace("(주)", "").replace("㈜", ""):
        if ch.strip() and ch not in "()[]":
            return ch.upper()
    return "?"


def _who(ev):
    role = (ev.get("role") or "").strip()
    who = (ev.get("who") or "").strip()
    return f"{role} {who}".strip()


def display(ev):
    """One event -> one feed row."""
    kr = ev["mk"] == "kr"
    money = fmt_krw if kr else fmt_usd
    key = _key(ev)
    row = {
        "id": ev["id"], "mk": ev["mk"], "co": ev.get("co", ""), "i": _initial(ev.get("co", "")),
        "w": _initial(ev.get("who") or ev.get("co", "")),
        "date": ev["date"], "dl": _dlabel(ev["date"]),
        "link": (f"/c/{key}/" if kr else f"/u/{key}/") if key else "",
        "url": ev.get("url") or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={ev['id']}",
        "time": (ev.get("seen") or "")[11:16] if kr and ev.get("seen", "")[:10] == ev["date"] else "",
    }
    t = ev["t"]
    if t == "trade":
        b, s = ev.get("buyQ", 0), ev.get("sellQ", 0)
        who = _who(ev)
        subj = f"{who}{iga(who) if kr else ','}" if who else ""
        if b and s:
            verb, kind = "장내에서 사고팔았어요", "mixed"
        elif b:
            verb, kind = "장내에서 샀어요", "buy"
        elif s:
            verb, kind = "장내에서 팔았어요", "sell"
        else:
            other = ", ".join(ev.get("other") or []) or "기타"
            verb, kind = f"보유 주식이 바뀌었어요 ({other})", "other"
        row["sub"] = f"{subj} {verb}".strip()
        row["kind"] = kind
        net = ev.get("buyAmt", 0) - ev.get("sellAmt", 0)
        if kind == "buy":
            row["amt"] = money(ev["buyAmt"]) if ev.get("buyAmt") else fmt_shares(b)
        elif kind == "sell":
            row["amt"] = money(ev["sellAmt"]) if ev.get("sellAmt") else fmt_shares(s)
        elif kind == "mixed":
            row["amt"] = money(net, sign=True)
        else:
            row["amt"] = "—"
        if kr and ev.get("rateChg"):
            row["d"] = f"{ev['rateChg']:+.2f}%p".replace("-", "−")
        elif kind in ("buy", "sell", "mixed"):
            row["d"] = {"buy": "장내매수", "sell": "장내매도", "mixed": "장내매수·매도"}[kind]
        else:
            row["d"] = "소유 변동"
        row["dk"] = "buy" if kind == "buy" or (kind == "mixed" and net > 0) else (
            "sell" if kind in ("sell", "mixed") else "muted")
        if ev.get("chk"):
            row["d"], row["dk"], row["chk"] = "단가 확인 필요", "muted", True
    elif t == "major":
        who, rate, chg = ev.get("who", ""), ev.get("rate", 0), ev.get("rateChg", 0)
        if ev.get("new"):
            row["sub"] = f"{who}{iga(who)} 지분 {rate:.2f}%를 새로 보유했어요"
        elif chg > 0:
            row["sub"] = f"{who}{iga(who)} 지분을 {rate:.2f}%로 늘렸어요"
        elif chg < 0:
            row["sub"] = f"{who}의 지분이 {rate:.2f}%로 줄었어요"
        else:
            row["sub"] = f"{who}{iga(who)} 지분 {rate:.2f}% 보유를 다시 보고했어요"
        row["amt"] = f"{rate:.2f}%"
        row["d"] = "지분 5% 새로" if ev.get("new") else f"{chg:+.2f}%p".replace("-", "−")
        row["kind"], row["dk"] = "major", "muted"
    elif t == "buyback":
        amt = ev.get("amt", 0)
        row["sub"] = f"자사주를 {fmt_krw(amt)}원어치 사기로 했어요" if amt else "자사주를 사기로 했어요"
        row["amt"] = fmt_krw(amt) if amt else "—"
        row["d"] = "자사주 취득 결정"
        row["kind"], row["dk"] = "buyback", "muted"
    else:
        row["sub"] = "최대주주가 바뀌었다고 알렸어요"
        row["amt"] = "—"
        row["d"] = "최대주주 변경"
        row["kind"], row["dk"] = "control", "muted"
    return row


def _key(ev):
    if ev["mk"] == "kr":
        return ev.get("code")
    k = ev.get("tk") or f"cik{ev.get('cik', '')}"
    return re.sub(r"[^A-Za-z0-9.\-]", "-", k)


PERIODS = (("1m", 20, "1달"), ("2w", 10, "2주"))  # first one is the default view
PRICE_DAYS = 90
# US issuers that are funds/ETFs, not operating companies (5-letter tickers ending in X are mutual funds)
FUND_RE = re.compile(r"\bFUNDS?\b|\bETF\b|\bPORTFOLIO\b|MUNICIPAL|\bTERM TRUST\b|\bSERIES TRUST\b|\bBDC\b|\bINTERVAL\b", re.I)


def _avg_px(ev):
    pts = _trade_points(ev)
    q = sum(x[2] for x in pts)
    return (sum(x[2] * x[3] for x in pts) / q, pts) if q else (0, pts)


def price_flag(evs):
    """Ids of trade reports whose unit price is implausible: 10x off the median of the same company's
    other reports (needs 2+ others), or (US) $1,000+/share on 100,000+ shares (e.g. a filing that typed
    the share count into the price box)."""
    by_co = collections.defaultdict(list)
    bad = set()
    for e in evs:
        if e["t"] != "trade":
            continue
        p, pts = _avg_px(e)
        if not p:
            continue
        if e["mk"] == "us" and any(px >= 1000 and q >= 100_000 for _, _, q, px in pts):
            bad.add(e["id"])
        by_co[_key(e)].append((e["id"], p))
    for rows in by_co.values():
        for i, (eid, p) in enumerate(rows):
            others = sorted(x for j, (_, x) in enumerate(rows) if j != i)
            if len(others) >= 2:
                m = len(others) // 2
                med = others[m] if len(others) % 2 else (others[m - 1] + others[m]) / 2
                if p > 10 * med or p < med / 10:
                    bad.add(eid)
    return bad


def is_insider_us(ev):
    """US report from an operating company's officer or director (not a fund, not a 10%-holder-only filer)."""
    k = _key(ev) or ""
    tk = ev.get("tk") or ""
    return (not k.startswith("cik") and not FUND_RE.search(ev.get("co", ""))
            and not (len(tk) == 5 and tk.upper().endswith("X"))
            and (ev.get("role") or "").strip() not in ("", "10% 주주"))


def _trade_points(ev):
    """(trade date, 'b'|'s', qty, price) rows of one report; older events fall back to report averages."""
    px = ev.get("px")
    if px:
        return [(d, k, q, p) for d, k, q, p in px if q and p]
    d = ev.get("tdate") or ev["date"]
    out = []
    if ev.get("buyQ") and ev.get("buyAmt"):
        out.append((d, "b", ev["buyQ"], ev["buyAmt"] / ev["buyQ"]))
    if ev.get("sellQ") and ev.get("sellAmt"):
        out.append((d, "s", ev["sellQ"], ev["sellAmt"] / ev["sellQ"]))
    return out


def price_block(evs, kr, end):
    """Reported trade prices for the company chart: one point per report and side, plus weighted averages."""
    start = (dt.date.fromisoformat(end) - dt.timedelta(days=PRICE_DAYS)).isoformat()
    pts, tot = [], {"b": [0.0, 0.0], "s": [0.0, 0.0]}
    for e in evs:
        if e["t"] != "trade" or e.get("chk"):
            continue
        sides = collections.defaultdict(lambda: [0.0, 0.0, ""])
        for d, k, q, p in _trade_points(e):
            d = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and "-" not in d else d[:10]
            if not (start <= d <= end):
                continue
            s = sides[k]
            s[0] += q
            s[1] += q * p
            s[2] = max(s[2], d)
            tot[k][0] += q
            tot[k][1] += q * p
        for k, (q, a, d) in sides.items():
            pts.append({"d": d, "k": k, "p": round(a / q, 2 if not kr else 0), "q": round(q),
                        "who": _who(e)})
    pts.sort(key=lambda x: x["d"])
    avg = {k: (round(a / q, 2 if not kr else 0) if q else 0) for k, (q, a) in tot.items()}
    return {"from": start, "to": end, "pts": pts[-300:], "avgBuy": avg["b"], "avgSell": avg["s"]}


def build_market(mk, events, out, updated="", issuers=None, complete_after=""):
    kr = mk == "kr"
    money = fmt_krw if kr else fmt_usd
    unit = 1e8 if kr else 1e6
    bad = price_flag(events)
    events = [dict(e, buyAmt=0, sellAmt=0, chk=True) if e["id"] in bad else e for e in events]
    trades = [e for e in events if e["t"] == "trade"]
    dates = sorted({e["date"] for e in events if dt.date.fromisoformat(e["date"]).weekday() < 5})

    def agg(ds):
        ds = set(ds)
        xs = [e for e in trades if e["date"] in ds]
        return {
            "buyN": sum(1 for e in xs if e.get("buyQ")),
            "sellN": sum(1 for e in xs if e.get("sellQ")),
            "net": sum(e.get("buyAmt", 0) - e.get("sellAmt", 0) for e in xs),
        }

    periods = {pk: window(pk, n, label, dates, trades, events, agg, kr, money, unit, complete_after)
               for pk, n, label in PERIODS}

    recent = sorted(events, key=lambda e: (e["date"], e.get("seen", ""), e["id"]), reverse=True)
    feed = [display(e) for e in recent[:150]]
    site = {"mk": mk, "updated": updated or max((e.get("seen") or e["date"] for e in events), default=""),
            "feed": feed, "p": periods, **periods[PERIODS[0][0]]}
    save_json(os.path.join(out, f"{mk}.json"), site)
    write_companies(mk, recent, dates, out, issuers, kr, money, unit, updated)
    return site


def window(pk, n, label, dates, trades, events, agg, kr, money, unit, complete_after):
    """Totals, daily series, rankings and clusters for the last n report days."""
    last, prevd = dates[-n:], dates[-2 * n:-n]
    cur, prev = agg(last), agg(prevd)
    series = []
    for d in last:
        a = agg([d])
        series.append({"d": _dlabel(d), "buyN": a["buyN"], "sellN": a["sellN"],
                       "v": round(a["net"] / unit, 1), "txt": money(a["net"], sign=True)})
    last_set = set(last)

    # rankings: net amount by company in the window
    def net_by_co(keep):
        by_co = collections.defaultdict(lambda: {"net": 0.0, "co": "", "cls": "", "n": 0})
        for e in trades:
            if e["date"] in last_set and keep(e):
                k = _key(e)
                if not k:
                    continue
                x = by_co[k]
                x["net"] += e.get("buyAmt", 0) - e.get("sellAmt", 0)
                x["co"], x["cls"] = e.get("co", ""), (e.get("cls") if kr else e.get("tk", ""))
                x["n"] += 1
        return by_co

    by_co = net_by_co(lambda e: True)

    def rank_rows(items):
        return [{"n": i + 1, "co": v["co"], "i": _initial(v["co"]), "sub": v["cls"],
                 "link": (f"/c/{k}/" if kr else f"/u/{k}/"), "v": money(v["net"], sign=True)}
                for i, (k, v) in enumerate(items)]

    pos = sorted(((k, v) for k, v in by_co.items() if v["net"] > 0), key=lambda kv: -kv[1]["net"])[:30]
    neg = sorted(((k, v) for k, v in by_co.items() if v["net"] < 0), key=lambda kv: kv[1]["net"])[:30]

    # clusters: 3+ different reporters buying the same company in the window
    people = collections.defaultdict(dict)
    meta = {}
    for e in trades:
        if e["date"] in last_set and e.get("buyQ") and _key(e):
            k = _key(e)
            p = people[k].setdefault(e.get("who", ""), {"who": e.get("who", ""), "role": e.get("role", ""),
                                                        "amt": 0.0, "days": set()})
            p["days"].add(e["date"])
            p["amt"] += e.get("buyAmt", 0)
            meta[k] = e.get("co", "")
    clusters = []
    for k, ps in people.items():
        if len(ps) >= 3:
            amt = sum(p["amt"] for p in ps.values())
            clusters.append({
                "co": meta[k], "link": (f"/c/{k}/" if kr else f"/u/{k}/"), "n": len(ps), "amt": money(amt),
                "_a": amt, "people": [{"who": p["who"], "role": p["role"]}
                                      for p in sorted(ps.values(), key=lambda p: -p["amt"])][:6],
                "dayCounts": [sum(1 for p in ps.values() if d in p["days"]) for d in last],
            })
    clusters.sort(key=lambda c: -c["_a"])
    for c in clusters:
        c.pop("_a")

    full = len(prevd) == n and (not complete_after or prevd[0] > complete_after)
    w = {
        "key": pk, "n": n, "label": label,
        "from": last[0] if last else "", "to": last[-1] if last else "",
        "days": [_dlabel(d)[:5] for d in last], "dows": [DOW[dt.date.fromisoformat(d).weekday()] for d in last],
        "buyN": cur["buyN"], "sellN": cur["sellN"], "prevBuyN": prev["buyN"], "prevSellN": prev["sellN"],
        "net": round(cur["net"] / unit, 1), "netTxt": money(cur["net"], sign=True),
        "diffTxt": money(cur["net"] - prev["net"]), "diffUp": cur["net"] >= prev["net"], "hasPrev": full,
        "clusterN": len(clusters),
        "majorN": sum(1 for e in events if e["t"] == "major" and e.get("new") and e["date"] in last_set),
        "buybackN": sum(1 for e in events if e["t"] == "buyback" and e["date"] in last_set),
    }
    res = {"w": w, "series": series, "rankBuy": rank_rows(pos), "rankSell": rank_rows(neg),
           "clusters": clusters[:12]}
    if not kr:  # officer/director buys at operating companies only (funds, ticker-less issuers, 10% holders out)
        bx = net_by_co(is_insider_us)
        res["rankBuyX"] = rank_rows(sorted(((k, v) for k, v in bx.items() if v["net"] > 0),
                                           key=lambda kv: -kv[1]["net"])[:30])
    return res


def write_companies(mk, recent, dates, out, issuers, kr, money, unit, updated):
    """One file per company (records + reported trade prices) and the search index."""
    cdir = os.path.join(out, "c" if kr else "u")
    shutil.rmtree(cdir, ignore_errors=True)
    groups = collections.defaultdict(list)
    for e in recent:
        k = _key(e)
        if k:
            groups[k].append(e)
    index, rec = [], {}
    cutoff = (dt.date.fromisoformat(dates[-1]) - dt.timedelta(days=90)).isoformat() if dates else ""
    end = (updated or (dates[-1] if dates else dt.date.today().isoformat()))[:10]
    for k, evs in groups.items():
        t90 = [e for e in evs if e["t"] == "trade" and e["date"] >= cutoff]
        b = sum(e.get("buyAmt", 0) for e in t90)
        s = sum(e.get("sellAmt", 0) for e in t90)
        first = evs[0]
        tk = first.get("tk", "")
        save_json(os.path.join(cdir, f"{k}.json"), {
            "key": k, "mk": mk, "co": first.get("co", ""), "cls": first.get("cls", "") if kr else tk,
            "tv": f"KRX:{k}" if kr else tk,
            "buy": money(b), "sell": money(s), "net": money(b - s, sign=True), "netV": round((b - s) / unit, 1),
            "people": len({e.get("who") for e in t90}), "count": len(evs),
            "price": price_block(evs, kr, end),
            "events": [display(e) for e in evs[:200]],
        })
        index.append([k, first.get("co", ""), US_KO.get(k, "") if not kr else ""])
        if t90:
            rec[k] = {"co": first.get("co", ""), "link": f"/{'c' if kr else 'u'}/{k}/",
                      "buy": money(b), "sell": money(s), "net": money(b - s, sign=True),
                      "netV": round((b - s) / unit, 1), "people": len({e.get("who") for e in t90}), "n": len(t90),
                      "last": [{x: r[x] for x in ("date", "sub", "kind", "amt", "d", "url", "chk") if x in r}
                               for r in map(display, t90[:5])]}
    save_json(os.path.join(out, f"recent_{mk}.json"), rec)
    # US issuers that filed Form 4s without open-market trades: searchable, with an explanatory page
    for k, (co, last) in (issuers or {}).items():
        if k in groups:
            continue
        save_json(os.path.join(cdir, f"{k}.json"), {
            "key": k, "mk": mk, "co": co, "cls": k, "tv": "" if k.startswith("cik") else k,
            "buy": money(0), "sell": money(0), "net": money(0),
            "netV": 0, "people": 0, "count": 0, "events": [], "lastOther": last,
        })
        index.append([k, co, US_KO.get(k, "")])
    index.sort(key=lambda x: x[1])
    save_json(os.path.join(out, f"{mk}_index.json"), index)
