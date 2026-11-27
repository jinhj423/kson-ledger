"""Score the collected data for parsing problems. Run: python tests/audit_data.py <data dir>

  ① 한국 trade parsed=false        ② 수량은 있는데 단가 0 (px 없는 옛 기록은 따로 셈)
  ③ '단가 확인 필요' 플래그          ④ debug/ 견본 중 지금 파서로도 못 읽는 것
  ⑤ runs.log 최근 24시간 실패·남은 대기   ⑥ 미국 단가 이상치인데 플래그 없는 것
"""
import datetime as dt
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "collect"))
from build import _key, price_flag  # noqa: E402
from dart import parse_trade_rows  # noqa: E402

MAX_IDS = 20


def _load(data, mk):
    out = []
    for p in sorted(glob.glob(os.path.join(data, "events", mk, "*.json"))):
        with open(p, encoding="utf-8") as f:
            out += json.load(f)
    return out


def _res(ids):
    ids = sorted(ids)
    return len(ids), ids[:MAX_IDS]


def _no_price(e):
    """Buy or sell shares not covered by priced rows (px only keeps rows with qty and price)."""
    for side, q in (("b", e.get("buyQ") or 0), ("s", e.get("sellQ") or 0)):
        if q and sum(x[2] for x in e["px"] if x[1] == side) < q - 0.5:
            return True
    return False


def _us_odd(trades, flagged):
    """10x+ price gaps the flag misses: two-report companies, and rows inside one report."""
    by_co = {}
    for e in trades:
        pts = [x for x in e.get("px") or [] if x[2] and x[3]]
        if pts:
            by_co.setdefault(_key(e), []).append((e["id"], pts))
    odd = set()
    for rows in by_co.values():
        for eid, pts in rows:
            for side in "bs":
                ps = [x[3] for x in pts if x[1] == side]
                if ps and max(ps) > 10 * min(ps):
                    odd.add(eid)
        if len(rows) == 2:
            (i1, p1), (i2, p2) = rows
            a1 = sum(x[2] * x[3] for x in p1) / sum(x[2] for x in p1)
            a2 = sum(x[2] * x[3] for x in p2) / sum(x[2] for x in p2)
            if max(a1, a2) > 10 * min(a1, a2):
                odd |= {i1, i2}
    return odd - flagged


LOG_T = re.compile(r"^\[(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)\] (.*)$")


def _runs(path):
    lines = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8").read().splitlines():
            m = LOG_T.match(line)
            if m:
                try:
                    t = dt.datetime(2024, *map(int, m.groups()[:5]))
                except ValueError:
                    continue
                lines.append((t, m.group(6)))
    det = {"fail": 0, "403": 0, "wait_kr": 0, "wait_us": 0}
    ids = []
    if not lines:
        return (0, []), det
    end = lines[-1][0]
    for t, msg in lines:
        if t > end:  # log crossed a new year
            t = t.replace(year=2023)
        if end - t > dt.timedelta(hours=24):
            continue
        m = re.match(r"KR: (\d{14}) 실패", msg)
        if m:
            det["fail"] += 1
            ids.append(m.group(1))
        if msg.startswith("US: 읽음"):
            det["fail"] += sum(int(x) for x in re.findall(r"실패 (\d+)건", msg))
            det["403"] += sum(int(x) for x in re.findall(r"403 (\d+)회", msg))
        w = re.search(r"남은 대기 (\d+)건", msg)
        if w and msg.startswith(("KR: 처리", "US: 읽음")):
            det["wait_kr" if msg.startswith("KR") else "wait_us"] = int(w.group(1))
    n = det["fail"] + det["wait_kr"] + det["wait_us"]
    return (n, sorted(set(ids))[:MAX_IDS]), det


def audit(data):
    kr, us = _load(data, "kr"), _load(data, "us")
    kt = [e for e in kr if e["t"] == "trade"]
    ut = [e for e in us if e["t"] == "trade"]
    flag_us = price_flag(us)
    debug = []
    for p in sorted(glob.glob(os.path.join(data, "debug", "kr_*.xml"))):
        with open(p, encoding="utf-8") as f:
            if not parse_trade_rows(f.read()):
                debug.append(os.path.basename(p)[3:-4])
    runs, det = _runs(os.path.join(data, "runs.log"))
    return {
        "kr_trades": len(kt), "us_trades": len(ut),
        "parsed": _res(e["id"] for e in kt if not e.get("parsed")),
        "zero_kr": _res(e["id"] for e in kt if "px" in e and _no_price(e)),
        "old_kr": _res(e["id"] for e in kt if "px" not in e),
        "zero_us": _res(e["id"] for e in ut if "px" in e and _no_price(e)),
        "flag_kr": _res(price_flag(kr)), "flag_us": _res(flag_us),
        "debug": _res(debug), "runs": runs, "runs_detail": det,
        "us_odd": _res(_us_odd(ut, flag_us)),
    }


ROWS = (("parsed", "① 한국 trade parsed=false"), ("zero_kr", "② 단가 0 (한국)"), ("zero_us", "② 단가 0 (미국)"),
        ("old_kr", "   옛 기록(px 없음, 한국)"), ("flag_kr", "③ 단가 확인 필요 (한국)"), ("flag_us", "③ 단가 확인 필요 (미국)"),
        ("debug", "④ debug 견본 못 읽음"), ("runs", "⑤ 최근 24시간 실패+남은 대기"), ("us_odd", "⑥ 미국 이상치(플래그 없음)"))


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    a = audit(args[0] if args else "data")
    print(f"한국 trade {a['kr_trades']:,}건 · 미국 trade {a['us_trades']:,}건")
    for k, label in ROWS:
        n, ids = a[k]
        print(f"{label}: {n:,}")
        if ids and k != "old_kr":
            print("    " + " ".join(ids))
    print("   ⑤ 내역:", json.dumps(a["runs_detail"], ensure_ascii=False))
    if "--json" in sys.argv:
        print(json.dumps(a, ensure_ascii=False))


if __name__ == "__main__":
    main()
