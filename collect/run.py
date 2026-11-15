"""One collection run: KR (DART) + US (SEC) -> data/state, then rebuild data/site.

Layout under DATA_DIR
  state/kr.json, state/us.json   seen / pending queues
  events/kr/YYYY-MM-DD.json      events by report (filing) date
  events/us/YYYY-MM-DD.json
  site/                          what the website reads
  debug/                         raw samples the KR parser could not read
"""
import datetime as dt
import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import build  # noqa: E402
import dart  # noqa: E402
import sec  # noqa: E402
from common import load_json, now_kst, save_json  # noqa: E402

DATA = os.environ.get("DATA_DIR", "data")
KEEP_DAYS = {"kr": 130, "us": 95}


LOG = []


def log(msg):
    line = f"[{now_kst():%m-%d %H:%M:%S}] {msg}"
    LOG.append(line)
    print(line, flush=True)


class Store:
    """Events grouped in one JSON file per day, keyed by event id."""

    def __init__(self, mk):
        self.mk = mk
        self.dir = os.path.join(DATA, "events", mk)
        self.days = {}

    def _day(self, d):
        if d not in self.days:
            self.days[d] = {e["id"]: e for e in load_json(os.path.join(self.dir, f"{d}.json"), [])}
        return self.days[d]

    def add(self, ev):
        self._day(ev["date"])[ev["id"]] = ev

    def flush(self):
        for d, evs in self.days.items():
            save_json(os.path.join(self.dir, f"{d}.json"), sorted(evs.values(), key=lambda e: e["id"]))

    def prune_and_load(self):
        cutoff = (dt.date.today() - dt.timedelta(days=KEEP_DAYS[self.mk])).isoformat()
        out = []
        for path in sorted(glob.glob(os.path.join(self.dir, "*.json"))):
            day = os.path.basename(path)[:-5]
            if day < cutoff:
                os.remove(path)
                continue
            out += load_json(path, [])
        return out


def prune_seen(state, keep_days):
    cutoff = (dt.date.today() - dt.timedelta(days=keep_days + 10)).strftime("%Y%m%d")
    seen = state.get("seen", {})
    state["seen"] = {k: v for k, v in seen.items() if (v or "").replace("-", "") >= cutoff}


def main():
    budget = float(os.environ.get("MAX_SECONDS", "780"))
    t0 = time.time()
    os.makedirs(DATA, exist_ok=True)

    kr_state = load_json(os.path.join(DATA, "state", "kr.json"), {})
    kr = Store("kr")
    try:
        debug = dart.collect(kr_state, kr.add, budget * 0.5, log)
    except Exception as e:  # keep what we have and still publish
        log(f"KR: 중단 {type(e).__name__}: {e}")
        debug = []
    kr.flush()
    prune_seen(kr_state, KEEP_DAYS["kr"])
    save_json(os.path.join(DATA, "state", "kr.json"), kr_state)
    for rc, text in debug:
        os.makedirs(os.path.join(DATA, "debug"), exist_ok=True)
        with open(os.path.join(DATA, "debug", f"kr_{rc}.xml"), "w", encoding="utf-8") as f:
            f.write(text)
    for old in sorted(glob.glob(os.path.join(DATA, "debug", "*.xml")))[:-10]:
        os.remove(old)

    us_state = load_json(os.path.join(DATA, "state", "us.json"), {})
    us = Store("us")
    try:
        sec.collect(us_state, us.add, max(60.0, budget - (time.time() - t0) - 60), log)
    except Exception as e:
        log(f"US: 중단 {type(e).__name__}: {e}")
    us.flush()
    prune_seen(us_state, KEEP_DAYS["us"])
    cutoff = (dt.date.today() - dt.timedelta(days=KEEP_DAYS["us"])).isoformat()
    us_state["issuers"] = {k: v for k, v in us_state.get("issuers", {}).items() if v[1] >= cutoff}
    save_json(os.path.join(DATA, "state", "us.json"), us_state)

    # still backfilling? ask the workflow to run again right away
    more = os.path.join(DATA, ".more")
    if len(kr_state.get("pending", [])) > 100 or len(us_state.get("pending", [])) > 400:
        open(more, "w").close()
    elif os.path.exists(more):
        os.remove(more)

    # filings are worked newest-first, so days after the newest still-waiting filing are complete
    kr_wait = [f"{p['rcept_dt'][:4]}-{p['rcept_dt'][4:6]}-{p['rcept_dt'][6:8]}" for p in kr_state.get("pending", [])]
    us_wait = [p["date"] for p in us_state.get("pending", [])]
    complete = {"kr": max(kr_wait, default=""), "us": max(us_wait, default="")}

    site = os.path.join(DATA, "site")
    for mk, store in (("kr", kr), ("us", us)):
        events = store.prune_and_load()
        build.build_market(mk, events, site, now_kst().isoformat(timespec="minutes"),
                           us_state.get("issuers") if mk == "us" else None, complete[mk])
        log(f"{mk}: 화면 자료 {len(events)}건으로 만듦")
    save_json(os.path.join(site, "meta.json"), {"built": now_kst().isoformat(timespec="minutes")})
    log(f"끝 ({time.time() - t0:.0f}초)")
    path = os.path.join(DATA, "runs.log")
    old = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join((old + LOG)[-400:]) + "\n")


if __name__ == "__main__":
    main()
