"""Run: python tests/test_rate_events.py"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from rate_events import (  # noqa: E402
    bok_events, fed_event, frac, merge, parse_bis_csv, parse_bok_table, parse_fed_rss, parse_fed_statement,
)

RSS = """﻿<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0"><channel><title>FRB: Press Release - Monetary Policy</title>
<item><title>Minutes of the Federal Open Market Committee, October 27-28, 2026</title>
<link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20261118a.htm</link>
<pubDate>Wed, 18 Nov 2026 19:00:00 GMT</pubDate></item>
<item><title><![CDATA[Federal Reserve issues FOMC statement]]></title>
<link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm</link>
<pubDate>Wed, 28 Oct 2026 18:00:00 GMT</pubDate></item>
</channel></rss>"""

ST_UP = """<div class="col-xs-12"><p>In support of its goals, the Committee decided to raise the target
range for the federal funds rate by 1/4&nbsp;percentage point to 4-1/4 to 4-1/2&nbsp;percent.</p></div>"""
ST_HOLD = "<p>the Committee decided to maintain the target range for the federal funds rate at 4 to 4-1/4 percent. In</p>"
ST_NOBY = "<p>the Committee decided to raise the target range for the federal funds rate to 5-1/4 to 5-1/2 percent.</p>"

BOK = """<table><tbody>
<tr>\n\t<td class="fb">2026</td>\n\t<td>11월 26일</td>\n\t<td>3.25</td>\n</tr>
<tr>\n\t<td class="fb">2026</td>\n\t<td>08월 27일</td>\n\t<td>3.00</td>\n</tr>
<tr>\n\t<td class="fb">2026</td>\n\t<td>07월 16일</td>\n\t<td>2.75</td>\n</tr>
<tr>\n\t<td class="fb">2025</td>\n\t<td>05월 29일</td>\n\t<td>2.50</td>\n</tr>
</tbody></table>"""

HEAD = ("FREQ,REF_AREA,UNIT_MEASURE,UNIT_MULT,TIME_FORMAT,COMPILATION,DECIMALS,SOURCE_REF,SUPP_INFO_BREAKS,"
        "TITLE,TIME_PERIOD,OBS_VALUE,OBS_STATUS,OBS_CONF,OBS_PRE_BREAK\r\n")


def bis(rows, area="KR"):
    return HEAD + "".join(f"D,{area},368,0,,From 7 Mar 2008 onwards: base rate. ,4,Bank of Korea,note., "
                          f"Central bank policy rates - Daily,{d},{v},A,F,\r\n" for d, v in rows)


def test_parsers():
    assert frac("4-1/4") == 4.25 and frac("1/4") == 0.25 and frac("4") == 4 and frac("3-3/4") == 3.75
    assert parse_fed_rss(RSS) == [("2026-10-28", "https://www.federalreserve.gov/newsevents/pressreleases/"
                                                 "monetary20261028a.htm")]
    assert parse_fed_statement(ST_UP) == {"act": "raise", "lo": 4.25, "hi": 4.5, "chg": 0.25}
    assert parse_fed_statement(ST_HOLD) == {"act": "maintain", "lo": 4.0, "hi": 4.25, "chg": None}
    assert parse_fed_statement(ST_NOBY) == {"act": "raise", "lo": 5.25, "hi": 5.5, "chg": None}
    assert parse_fed_statement("<p>nothing here</p>") is None
    assert parse_bok_table(BOK) == [("2025-05-29", 2.5), ("2026-07-16", 2.75), ("2026-08-27", 3.0),
                                    ("2026-11-26", 3.25)]
    assert parse_bis_csv(bis([("2026-11-25", "3"), ("2026-11-26", "3.25")])) == {"2026-11-25": 3.0,
                                                                                "2026-11-26": 3.25}


def test_fed_event_needs_bis():
    url = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm"
    st = parse_fed_statement(ST_UP)
    # BIS not updated after the decision yet: wait
    assert fed_event("2026-10-28", url, st, parse_bis_csv(bis([("2026-10-28", "4.125")], "US"))) is None
    # BIS disagrees (shows the old range midpoint): skip
    assert fed_event("2026-10-28", url, st, parse_bis_csv(bis([("2026-10-29", "4.125")], "US"))) is None
    ev = fed_event("2026-10-28", url, st, parse_bis_csv(bis([("2026-10-29", "4.375")], "US")))
    assert ev == {"kr": "2026-10-29", "us": "2026-10-28", "cat": "금리", "imp": 3, "t": "FOMC 0.25%p 인상",
                  "x": "연준이 기준금리 목표 범위를 0.25%p 올려 4.25~4.50%로 정했어요.",
                  "src": [{"t": "미국 연준 FOMC 성명", "u": url},
                          {"t": "BIS 정책금리", "u": "https://data.bis.org/topics/CBPOL"}]}, ev
    hold = fed_event("2026-10-28", url, parse_fed_statement(ST_HOLD),
                     parse_bis_csv(bis([("2026-10-29", "4.25")], "US")))  # upper bound also accepted
    assert hold["t"] == "FOMC 금리 동결" and hold["imp"] == 2
    assert hold["x"] == "연준이 기준금리 목표 범위를 4.00~4.25%로 그대로 뒀어요."


def test_bok_events():
    table = parse_bok_table(BOK)
    sched = ["2026-10-22", "2026-11-26", "2027-01-14"]
    rates = parse_bis_csv(bis([("2026-10-22", "3"), ("2026-11-26", "3.25")]))
    evs = bok_events(table, rates, sched, dt.date(2026, 11, 27))
    assert [e["kr"] for e in evs] == ["2026-10-22", "2026-11-26"]
    hold, up = evs
    assert hold["t"] == "한은 기준금리 동결" and hold["imp"] == 2 and "us" not in hold
    assert hold["x"] == "한국은행이 기준금리를 3.00%로 그대로 뒀어요."
    assert up["t"] == "한은 기준금리 인상" and up["imp"] == 3
    assert up["x"] == "한국은행이 기준금리를 3.00%에서 3.25%로 0.25%p 올렸어요."
    assert up["src"][0]["u"].startswith("https://www.bok.or.kr/")
    # BIS has no figure for the meeting day yet, or a different one: nothing for that day
    assert bok_events(table, parse_bis_csv(bis([("2026-11-25", "3")])), sched, dt.date(2026, 11, 27)) == []
    assert [e["kr"] for e in bok_events(table, parse_bis_csv(bis([("2026-10-22", "3"), ("2026-11-26", "3")])),
                                        sched, dt.date(2026, 11, 27))] == ["2026-10-22"]
    # an unscheduled change in the table still counts; meetings older than the look-back are ignored
    t2 = table + [("2026-12-03", 3.5)]
    r2 = parse_bis_csv(bis([("2026-12-03", "3.5")]))
    assert [e["kr"] for e in bok_events(t2, r2, ["2026-07-16"], dt.date(2026, 12, 4))] == ["2026-12-03"]


def test_merge():
    today = dt.date(2026, 11, 27)
    doc = {"note": "n", "updated": "2026-11-20", "items": [
        {"kr": "2026-09-01", "cat": "시장", "imp": 2, "t": "old", "x": "", "src": []},
        {"kr": "2026-11-26", "cat": "금리", "imp": 3, "t": "한은 기준금리 인상", "x": "", "src": []},
        {"kr": "2026-10-29", "cat": "시장", "imp": 3, "t": "코스피 급락", "x": "", "src": []}]}
    fed = {"kr": "2026-10-29", "us": "2026-10-28", "cat": "금리", "imp": 3, "t": "FOMC", "x": "", "src": []}
    bok = {"kr": "2026-11-26", "cat": "금리", "imp": 3, "t": "한은 기준금리 인상(자동)", "x": "", "src": []}
    out, added, removed = merge(doc, [fed, bok], today)
    assert removed == 1 and out["updated"] == "2026-11-27"
    # the Korean day is taken by a market item, so the FOMC dot goes on the US chart only; BOK day already there
    assert added == ["2026-10-28 FOMC"]
    assert [(i.get("kr"), i.get("us"), i["t"]) for i in out["items"]] == [
        (None, "2026-10-28", "FOMC"), ("2026-10-29", None, "코스피 급락"), ("2026-11-26", None, "한은 기준금리 인상")]
    again, added2, removed2 = merge(out, [fed, bok], today)
    assert added2 == [] and removed2 == 0 and again == out


def test_dump_keeps_file_layout():
    import json
    from rate_events import dump
    path = os.path.join(os.path.dirname(__file__), "..", "src", "events.json")
    text = open(path, encoding="utf-8").read()
    assert dump(json.loads(text)) == text


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
