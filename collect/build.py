"""Stored events -> display-ready JSON for the site (site/kr.json, site/us.json, company files, indexes)."""
import collections
import datetime as dt
import os
import re
import shutil

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
    elif t == "major":
        who = ev.get("who", "")
        row["sub"] = f"{who}{iga(who)} 지분 {ev.get('rate', 0):.2f}%를 보유하고 있다고 알렸어요"
        row["amt"] = f"{ev.get('rate', 0):.2f}%"
        row["d"] = "지분 5% 새로" if ev.get("new") else f"{ev.get('rateChg', 0):+.2f}%p".replace("-", "−")
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


def build_market(mk, events, out):
    kr = mk == "kr"
    money = fmt_krw if kr else fmt_usd
    unit = 1e8 if kr else 1e6
    trades = [e for e in events if e["t"] == "trade"]
    dates = sorted({e["date"] for e in events if dt.date.fromisoformat(e["date"]).weekday() < 5})
    last20 = dates[-20:]
    last5, prev5 = last20[-5:], last20[-10:-5]

    def agg(ds):
        ds = set(ds)
        xs = [e for e in trades if e["date"] in ds]
        return {
            "buyN": sum(1 for e in xs if e.get("buyQ")),
            "sellN": sum(1 for e in xs if e.get("sellQ")),
            "net": sum(e.get("buyAmt", 0) - e.get("sellAmt", 0) for e in xs),
        }

    cur, prev = agg(last5), agg(prev5)

    series = []
    for d in last20:
        a = agg([d])
        series.append({"d": _dlabel(d), "buyN": a["buyN"], "sellN": a["sellN"],
                       "v": round(a["net"] / unit, 1), "txt": money(a["net"], sign=True)})

    # rankings (last 5 trading days, net amount by company)
    by_co = collections.defaultdict(lambda: {"net": 0.0, "co": "", "cls": "", "n": 0})
    for e in trades:
        if e["date"] in set(last5):
            k = _key(e)
            if not k:
                continue
            x = by_co[k]
            x["net"] += e.get("buyAmt", 0) - e.get("sellAmt", 0)
            x["co"], x["cls"] = e.get("co", ""), (e.get("cls") if kr else e.get("tk", ""))
            x["n"] += 1

    def rank_rows(items):
        return [{"n": i + 1, "co": v["co"], "i": _initial(v["co"]), "sub": v["cls"],
                 "link": (f"/c/{k}/" if kr else f"/u/{k}/"), "v": money(v["net"], sign=True)}
                for i, (k, v) in enumerate(items)]

    pos = sorted(((k, v) for k, v in by_co.items() if v["net"] > 0), key=lambda kv: -kv[1]["net"])[:30]
    neg = sorted(((k, v) for k, v in by_co.items() if v["net"] < 0), key=lambda kv: kv[1]["net"])[:30]

    # clusters: 3+ different reporters buying the same company in the last 5 trading days
    people = collections.defaultdict(dict)
    meta = {}
    for e in trades:
        if e["date"] in set(last5) and e.get("buyQ") and _key(e):
            k = _key(e)
            p = people[k].setdefault(e.get("who", ""), {"who": e.get("who", ""), "role": e.get("role", ""),
                                                        "days": [False] * len(last5), "amt": 0.0})
            p["days"][last5.index(e["date"])] = True
            p["amt"] += e.get("buyAmt", 0)
            meta[k] = e.get("co", "")
    clusters = []
    for k, ps in people.items():
        if len(ps) >= 3:
            amt = sum(p["amt"] for p in ps.values())
            clusters.append({
                "co": meta[k], "link": (f"/c/{k}/" if kr else f"/u/{k}/"), "n": len(ps), "amt": money(amt),
                "_a": amt, "people": [{"who": p["who"], "role": p["role"], "days": p["days"]}
                                      for p in sorted(ps.values(), key=lambda p: -p["amt"])][:6],
                "dayCounts": [sum(1 for p in ps.values() if p["days"][i]) for i in range(len(last5))],
            })
    clusters.sort(key=lambda c: (-c["n"], -c["_a"]))
    for c in clusters:
        c.pop("_a")

    recent = sorted(events, key=lambda e: (e["date"], e.get("seen", ""), e["id"]), reverse=True)
    feed = [display(e) for e in recent[:150]]
    last5_set = set(last5)
    w = {
        "from": last5[0] if last5 else "", "to": last5[-1] if last5 else "",
        "days": [_dlabel(d)[:5] for d in last5], "dows": [DOW[dt.date.fromisoformat(d).weekday()] for d in last5],
        "buyN": cur["buyN"], "sellN": cur["sellN"], "prevBuyN": prev["buyN"], "prevSellN": prev["sellN"],
        "net": round(cur["net"] / unit, 1), "netTxt": money(cur["net"], sign=True),
        "diffTxt": money(cur["net"] - prev["net"]), "diffUp": cur["net"] >= prev["net"], "hasPrev": bool(prev5),
        "clusterN": len(clusters),
        "majorN": sum(1 for e in events if e["t"] == "major" and e.get("new") and e["date"] in last5_set),
        "buybackN": sum(1 for e in events if e["t"] == "buyback" and e["date"] in last5_set),
    }
    site = {"mk": mk, "updated": max((e.get("seen") or e["date"] for e in events), default=""),
            "w": w, "series": series, "feed": feed,
            "rankBuy": rank_rows(pos), "rankSell": rank_rows(neg), "clusters": clusters[:12]}
    save_json(os.path.join(out, f"{mk}.json"), site)

    # company files + search index
    cdir = os.path.join(out, "c" if kr else "u")
    shutil.rmtree(cdir, ignore_errors=True)
    groups = collections.defaultdict(list)
    for e in recent:
        k = _key(e)
        if k:
            groups[k].append(e)
    index = []
    cutoff = (dt.date.fromisoformat(dates[-1]) - dt.timedelta(days=90)).isoformat() if dates else ""
    for k, evs in groups.items():
        t90 = [e for e in evs if e["t"] == "trade" and e["date"] >= cutoff]
        b = sum(e.get("buyAmt", 0) for e in t90)
        s = sum(e.get("sellAmt", 0) for e in t90)
        first = evs[0]
        save_json(os.path.join(cdir, f"{k}.json"), {
            "key": k, "mk": mk, "co": first.get("co", ""), "cls": first.get("cls", "") if kr else first.get("tk", ""),
            "buy": money(b), "sell": money(s), "net": money(b - s, sign=True), "netV": round((b - s) / unit, 1),
            "people": len({e.get("who") for e in t90}), "count": len(evs),
            "events": [display(e) for e in evs[:200]],
        })
        index.append([k, first.get("co", "")])
    index.sort(key=lambda x: x[1])
    save_json(os.path.join(out, f"{mk}_index.json"), index)
    return site
