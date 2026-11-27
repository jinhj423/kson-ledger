"""Add rate-decision dots (FOMC, Bank of Korea) to src/events.json from official sources.

Run: python scripts/rate_events.py src/events.json [commit-message-file]
Each decision needs two sources that agree: the central bank's own release and the BIS policy-rate series.
Index moves and other news stay manual. Update BOK_MEETINGS once a year (BOK publishes it each October).
"""
import copy
import csv
import datetime as dt
import html
import io
import json
import re
import sys
import urllib.request
from zoneinfo import ZoneInfo

FED_RSS = "https://www.federalreserve.gov/feeds/press_monetary.xml"
BOK_URL = "https://www.bok.or.kr/portal/singl/baseRate/list.do?dataSeCd=01&menuNo=200643"
BIS_CSV = "https://stats.bis.org/api/v1/data/WS_CBPOL/D.{area}?startPeriod={start}&format=csv"
BIS_PAGE = "https://data.bis.org/topics/CBPOL"
UA = "Mozilla/5.0 (compatible; kson-ledger-events/1.0; +https://github.com/jinhj423/kson-ledger)"
LOOKBACK = 45  # days a decision may wait for BIS to catch up
KEEP = 70  # days an event dot is kept
# 통화정책방향 결정회의 (2027 일정: 2026-10-29 금통위 의결, SBS Biz 2026-10-29 보도)
BOK_MEETINGS = ["2026-11-26", "2027-01-14", "2027-02-25", "2027-04-09", "2027-05-27", "2027-07-15",
                "2027-08-26", "2027-10-15", "2027-11-25"]


def frac(s):
    """'4-1/4' -> 4.25, '1/4' -> 0.25, '4' -> 4.0"""
    if "-" in s:
        whole, part = s.split("-", 1)
    elif "/" in s:
        whole, part = "", s
    else:
        whole, part = s, ""
    val = float(whole) if whole else 0.0
    if part:
        n, d = part.split("/")
        val += float(n) / float(d)
    return val


def _pct(v):
    return f"{v:.2f}"


def _chg(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def parse_fed_rss(xml):
    out = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        title = re.search(r"<title>(.*?)</title>", item, re.S)
        link = re.search(r"<link>\s*(.*?)\s*</link>", item, re.S)
        if not title or not link:
            continue
        t, u = (re.sub(r"<!\[CDATA\[|\]\]>", "", g.group(1)).strip() for g in (title, link))
        m = re.search(r"monetary(\d{4})(\d{2})(\d{2})a\.htm", u)
        if "fomc statement" in t.lower() and m:
            out.append((f"{m.group(1)}-{m.group(2)}-{m.group(3)}", u))
    return out


def parse_fed_statement(page):
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)).replace("\xa0", " "))
    m = re.search(r"decided to (raise|lower|maintain) the target range for the federal funds rate"
                  r"(?: by ([\d/\-]+) percentage points?)? (?:at|to) ([\d/\-]+) to ([\d/\-]+) percent", text)
    if not m:
        return None
    return {"act": m.group(1), "lo": frac(m.group(3)), "hi": frac(m.group(4)),
            "chg": frac(m.group(2)) if m.group(2) else None}


def parse_bok_table(page):
    rows = re.findall(r"<td[^>]*>\s*(\d{4})\s*</td>\s*<td[^>]*>\s*(\d{1,2})월\s*(\d{1,2})일\s*</td>"
                      r"\s*<td[^>]*>\s*([\d.]+)\s*</td>", page)
    return sorted({(f"{y}-{int(mo):02d}-{int(d):02d}", float(r)) for y, mo, d, r in rows})


def parse_bis_csv(text):
    out = {}
    for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        d, v = (row.get("TIME_PERIOD") or "").strip(), (row.get("OBS_VALUE") or "").strip()
        try:
            out[d] = float(v)
        except ValueError:
            continue
    return out


def _same(a, b):
    return abs(a - b) < 1e-6


def fed_event(day, url, st, bis):
    """One FOMC decision, only once BIS shows the new range (upper, lower or midpoint) after the decision day."""
    d = dt.date.fromisoformat(day)
    later = sorted(k for k in bis if day < k <= (d + dt.timedelta(days=7)).isoformat())
    if not later:
        return None
    v = bis[later[0]]
    lo, hi = st["lo"], st["hi"]
    if not any(_same(v, x) for x in (lo, hi, (lo + hi) / 2)):
        return None
    rng = f"{_pct(lo)}~{_pct(hi)}%"
    if st["act"] == "maintain":
        t, x, imp = "FOMC 금리 동결", f"연준이 기준금리 목표 범위를 {rng}로 그대로 뒀어요.", 2
    else:
        up = st["act"] == "raise"
        word = "인상" if up else "인하"
        if st["chg"]:
            t = f"FOMC {_chg(st['chg'])}%p {word}"
            x = f"연준이 기준금리 목표 범위를 {_chg(st['chg'])}%p {'올려' if up else '내려'} {rng}로 정했어요."
        else:
            t, x = f"FOMC 금리 {word}", f"연준이 기준금리 목표 범위를 {rng}로 {'올렸어요' if up else '내렸어요'}."
        imp = 3
    return {"kr": (d + dt.timedelta(days=1)).isoformat(), "us": day, "cat": "금리", "imp": imp, "t": t, "x": x,
            "src": [{"t": "미국 연준 FOMC 성명", "u": url}, {"t": "BIS 정책금리", "u": BIS_PAGE}]}


def bok_events(table, bis, schedule, today, lookback=LOOKBACK):
    """Holds on meeting days and every change in BOK's table, each confirmed by BIS on that very day."""
    start = (today - dt.timedelta(days=lookback)).isoformat()
    days = sorted(d for d in set(schedule) | {d for d, _ in table} if start <= d <= today.isoformat())
    out = []
    for day in days:
        before = [(d, r) for d, r in table if d <= day]
        if not before or day not in bis or not _same(bis[day], before[-1][1]):
            continue
        rate = before[-1][1]
        src = [{"t": "한국은행 기준금리 추이", "u": BOK_URL}, {"t": "BIS 정책금리", "u": BIS_PAGE}]
        if before[-1][0] == day:
            prev = before[-2][1] if len(before) > 1 else None
            up = prev is None or rate > prev
            word = "인상" if up else "인하"
            if prev is None:
                x = f"한국은행이 기준금리를 {_pct(rate)}%로 {'올렸어요' if up else '내렸어요'}."
            else:
                x = (f"한국은행이 기준금리를 {_pct(prev)}%에서 {_pct(rate)}%로 {_chg(abs(rate - prev))}%p "
                     f"{'올렸어요' if up else '내렸어요'}.")
            out.append({"kr": day, "cat": "금리", "imp": 3, "t": f"한은 기준금리 {word}", "x": x, "src": src})
        else:
            out.append({"kr": day, "cat": "금리", "imp": 2, "t": "한은 기준금리 동결",
                        "x": f"한국은행이 기준금리를 {_pct(rate)}%로 그대로 뒀어요.", "src": src})
    return out


def _when(item):
    return min(v for v in (item.get("kr"), item.get("us")) if v)


def merge(doc, new, today, keep=KEEP):
    """Drop dots older than `keep` days; add new ones on market days that are still free (one dot per market
    per day, existing items win). Returns (doc, added labels, removed count)."""
    out = copy.deepcopy(doc)
    cutoff = (today - dt.timedelta(days=keep)).isoformat()
    items = out.get("items", [])
    kept = [i for i in items if max(v for v in (i.get("kr"), i.get("us")) if v) >= cutoff]
    removed = len(items) - len(kept)
    added = []
    for ev in new:
        ev = dict(ev)
        for mk in ("kr", "us"):
            if ev.get(mk) and any(i.get(mk) == ev[mk] for i in kept):
                del ev[mk]
        if not ev.get("kr") and not ev.get("us"):
            continue
        order = {k: ev[k] for k in ("kr", "us") if k in ev}
        order.update({k: v for k, v in ev.items() if k not in ("kr", "us")})
        kept.append(order)
        added.append(f"{_when(order)} {order['t']}")
    kept.sort(key=_when)
    out["items"] = kept
    if added or removed:
        out["updated"] = today.isoformat()
    return out, added, removed


def dump(doc):
    """indent-2 JSON with each source on one line, the way src/events.json is written by hand."""
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    text = re.sub(r'\{\n\s+("t": "(?:[^"\\]|\\.)*"),\n\s+("u": "(?:[^"\\]|\\.)*")\n\s+\}', r"{ \1, \2 }", text)
    return text + "\n"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main(argv):
    path = argv[1]
    today = dt.datetime.now(ZoneInfo("Asia/Seoul")).date()
    start = (today - dt.timedelta(days=LOOKBACK + 10)).isoformat()
    new = []
    try:
        bis_us = parse_bis_csv(fetch(BIS_CSV.format(area="US", start=start)))
        print(f"BIS 미국 최신: {max(bis_us) if bis_us else '없음'} {bis_us[max(bis_us)] if bis_us else ''}")
        for day, url in parse_fed_rss(fetch(FED_RSS)):
            if day < (today - dt.timedelta(days=LOOKBACK)).isoformat():
                continue
            st = parse_fed_statement(fetch(url))
            ev = fed_event(day, url, st, bis_us) if st else None
            print(f"연준 {day}: {ev['t'] if ev else ('성명 문장 못 읽음' if not st else 'BIS 확인 대기')}")
            if ev:
                new.append(ev)
    except Exception as e:  # one source down must not stop the other
        print(f"연준: 건너뜀 {type(e).__name__}: {e}")
    try:
        table = parse_bok_table(fetch(BOK_URL))
        if not table:
            raise ValueError("기준금리 표를 못 읽음")
        bis_kr = parse_bis_csv(fetch(BIS_CSV.format(area="KR", start=start)))
        print(f"BIS 한국 최신: {max(bis_kr) if bis_kr else '없음'} {bis_kr[max(bis_kr)] if bis_kr else ''}")
        evs = bok_events(table, bis_kr, BOK_MEETINGS, today)
        print(f"한은: 확인된 결정 {len(evs)}건 (표 최신 {table[-1][0]} {table[-1][1]}%)")
        new += evs
    except Exception as e:
        print(f"한은: 건너뜀 {type(e).__name__}: {e}")

    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    out, added, removed = merge(doc, new, today)
    if not added and not removed:
        print("추가할 이벤트 없음")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(dump(out))
    msg = "events: " + (", ".join(added) if added else "") + (f" (오래된 점 {removed}개 정리)" if removed else "")
    print(msg)
    if len(argv) > 2:
        with open(argv[2], "w", encoding="utf-8") as f:
            f.write(msg.strip() + "\n")


if __name__ == "__main__":
    main(sys.argv)
