"""US: SEC EDGAR Form 4 -> open-market trade events (codes P = purchase, S = sale).

Sources
  daily index  https://www.sec.gov/Archives/edgar/daily-index/YYYY/QTRn/form.YYYYMMDD.idx  (past days)
  current feed browse-edgar?action=getcurrent&type=4&output=atom                              (today)
Each filing is read once from its full-text .txt (the Form 4 XML is inside).
"""
import datetime as dt
import os
import re
import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET

from common import get

BASE = "https://www.sec.gov"
ACC = re.compile(r"(\d{10}-\d{2}-\d{6})")
ATOM = {"a": "http://www.w3.org/2005/Atom"}
ET_TZ = dt.timezone(dt.timedelta(hours=-5))


class Sec:
    def __init__(self, ua):
        self.h = {"User-Agent": ua, "Accept-Encoding": "identity"}
        self.calls = 0
        self.forbidden = 0
        self._last = 0.0
        self._lock = threading.Lock()

    def get(self, url):
        with self._lock:  # stay under SEC's 10 requests/second across threads
            wait = 0.14 - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            self.calls += 1
        try:
            return get(url, headers=self.h, tries=1)
        except urllib.error.HTTPError as e:
            if e.code == 403:  # EDGAR answers 403 for missing files (and for blocked clients)
                self.forbidden += 1
                return None
            raise


def daily_index(sec, day):
    q = (day.month - 1) // 3 + 1
    raw = sec.get(f"{BASE}/Archives/edgar/daily-index/{day.year}/QTR{q}/form.{day:%Y%m%d}.idx")
    if raw is None:
        return None  # weekend / holiday / not yet published
    out = []
    for line in raw.decode("latin-1").splitlines():
        if not line.startswith("4 "):
            continue
        m = re.search(r"(edgar/data/(\d+)/(\d{10}-\d{2}-\d{6})\.txt)\s*$", line)
        if m:
            out.append({"acc": m.group(3), "cik": m.group(2), "date": day.isoformat()})
    return out


def current_feed(sec, pages):
    out, seen = [], set()
    for p in range(pages):
        raw = sec.get(f"{BASE}/cgi-bin/browse-edgar?action=getcurrent&type=4&company=&dateb=&owner=include"
                      f"&start={p * 100}&count=100&output=atom")
        if not raw:
            break
        root = ET.fromstring(raw)
        entries = root.findall("a:entry", ATOM)
        for e in entries:
            title = e.findtext("a:title", "", ATOM)
            if not title.startswith("4 "):
                continue
            link = e.find("a:link", ATOM)
            href = link.get("href", "") if link is not None else ""
            m, c = ACC.search(href), re.search(r"/data/(\d+)/", href)
            if not (m and c) or m.group(1) in seen:
                continue
            seen.add(m.group(1))
            up = e.findtext("a:updated", "", ATOM)
            out.append({"acc": m.group(1), "cik": c.group(1), "date": up[:10]})
        if len(entries) < 100:
            break
    return out


def _f(x):
    try:
        return float(x or 0)
    except ValueError:
        return 0.0


def _yes(x):
    return (x or "").strip().lower() in ("1", "true")


def parse_form4(txt):
    m = re.search(r"<XML>\s*(.*?)\s*</XML>", txt, re.S)
    if not m:
        return None
    root = ET.fromstring(m.group(1).strip().encode("utf-8"))
    if root.tag != "ownershipDocument":
        return None
    iss = root.find("issuer")
    owners = root.findall("reportingOwner")
    if iss is None or not owners:
        return None
    o = owners[0]
    rel = o.find("reportingOwnerRelationship")
    title = (rel.findtext("officerTitle") or "").strip() if rel is not None else ""
    if rel is not None and _yes(rel.findtext("isOfficer")) and title:
        role = title
    elif rel is not None and _yes(rel.findtext("isDirector")):
        role = "이사"
    elif rel is not None and _yes(rel.findtext("isTenPercentOwner")):
        role = "10% 주주"
    else:
        role = title
    who = (o.findtext("reportingOwnerId/rptOwnerName") or "").strip()
    if len(owners) > 1:
        who += f" 외 {len(owners) - 1}명"
    buyQ = buyAmt = sellQ = sellAmt = 0.0
    tdates = []
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = (t.findtext("transactionCoding/transactionCode") or "").strip()
        sh = _f(t.findtext("transactionAmounts/transactionShares/value"))
        px = _f(t.findtext("transactionAmounts/transactionPricePerShare/value"))
        if code == "P":
            buyQ += sh
            buyAmt += sh * px
        elif code == "S":
            sellQ += sh
            sellAmt += sh * px
        else:
            continue
        d = (t.findtext("transactionDate/value") or "")[:10]
        if d:
            tdates.append(d)
    if not (buyQ or sellQ):
        return None
    tk = (iss.findtext("issuerTradingSymbol") or "").strip().upper()
    if tk in ("", "NONE", "N/A"):
        tk = ""
    return {
        "tk": tk, "co": (iss.findtext("issuerName") or "").strip(),
        "cik": (iss.findtext("issuerCik") or "").strip().lstrip("0"),
        "who": who, "role": role,
        "buyQ": buyQ, "buyAmt": buyAmt, "sellQ": sellQ, "sellAmt": sellAmt,
        "tdate": min(tdates) if tdates else "",
    }


def collect(state, store_event, budget_s, log):
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua:
        log("US: SEC_USER_AGENT 없음, 건너뜀")
        return
    sec = Sec(ua)
    t0 = time.time()
    seen = state.setdefault("seen", {})
    pending = state.setdefault("pending", [])
    queued = {p["acc"] for p in pending}
    done_days = set(state.setdefault("days", []))
    today_et = dt.datetime.now(ET_TZ).date()

    def add(items):
        for it in items:
            if it["acc"] not in seen and it["acc"] not in queued:
                pending.append(it)
                queued.add(it["acc"])

    add(current_feed(sec, 6))
    for back in range(1, 29):
        day = today_et - dt.timedelta(days=back)
        if day.weekday() >= 5 or day.isoformat() in done_days:
            continue
        items = daily_index(sec, day)
        if items is not None:
            add(items)
            done_days.add(day.isoformat())
        if time.time() - t0 > budget_s / 4:
            break
    state["days"] = sorted(done_days)[-40:]

    pending.sort(key=lambda p: (p["date"], p["acc"]), reverse=True)

    def fetch(it):
        try:
            raw = sec.get(f"{BASE}/Archives/edgar/data/{it['cik']}/{it['acc']}.txt")
            return it, (parse_form4(raw.decode("utf-8", "replace")) if raw else None)
        except Exception as e:  # skip broken filings
            log(f"US: {it['acc']} 실패: {e}")
            return it, None

    n = kept = 0
    with ThreadPoolExecutor(4) as pool:
        while pending and time.time() - t0 < budget_s:
            batch = [pending.pop(0) for _ in range(min(40, len(pending)))]
            for it, info in pool.map(fetch, batch):
                seen[it["acc"]] = it["date"]
                n += 1
                if not info:
                    continue
                cik_dir = it["acc"].replace("-", "")
                info.update({
                    "id": it["acc"], "mk": "us", "t": "trade", "date": it["date"],
                    "url": f"{BASE}/Archives/edgar/data/{it['cik']}/{cik_dir}/{it['acc']}-index.htm",
                })
                store_event(info)
                kept += 1
    log(f"US: 읽음 {n}건, 장내거래 {kept}건, 남은 대기 {len(pending)}건, 요청 {sec.calls}회, 403 {sec.forbidden}회")
