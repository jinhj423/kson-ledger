"""Run: python tests/test_parsers.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collect"))

from build import display  # noqa: E402
from common import fmt_krw, fmt_usd, iga, to_num  # noqa: E402
from dart import parse_trade_rows  # noqa: E402
from sec import parse_form4  # noqa: E402

DART_DOC = """
<TABLE-GROUP><TITLE>세부변동내역</TITLE>
<TABLE><THEAD>
<TR><TH ROWSPAN="2">보고사유</TH><TH ROWSPAN="2">변동일*</TH><TH ROWSPAN="2">특정증권등의 종류</TH>
<TH COLSPAN="3">특정증권등의 수(주)</TH><TH ROWSPAN="2">취득/처분 단가(원)**</TH><TH ROWSPAN="2">비 고</TH></TR>
<TR><TH>변동 전</TH><TH>증감</TH><TH>변동 후</TH></TR></THEAD>
<TBODY>
<TR><TE ACODE="RPT_RSN">장내매수(+)</TE><TE>2026년 11월 12일</TE><TE>보통주</TE><TE>1,000</TE><TE>150,000</TE><TE>151,000</TE><TE>39,000</TE><TE></TE></TR>
<TR><TE>장내매수(+)</TE><TE>2026.11.13</TE><TE>보통주</TE><TE>151,000</TE><TE>50,000</TE><TE>201,000</TE><TE>39,200</TE><TE>-</TE></TR>
<TR><TE>장내매도(-)</TE><TE>2026.11.13</TE><TE>보통주</TE><TE>201,000</TE><TE>-1,000</TE><TE>200,000</TE><TE>40,000</TE><TE></TE></TR>
<TR><TE>증여(-)</TE><TE>2026.11.13</TE><TE>보통주</TE><TE>200,000</TE><TE>-500</TE><TE>199,500</TE><TE>-</TE><TE></TE></TR>
<TR><TE>장내매수(+)</TE><TE>2026.11.13</TE><TE>전환사채</TE><TE>0</TE><TE>10</TE><TE>10</TE><TE>10,000</TE><TE></TE></TR>
<TR><TE>합 계</TE><TE></TE><TE></TE><TE>1,000</TE><TE>198,510</TE><TE>199,510</TE><TE></TE><TE></TE></TR>
</TBODY></TABLE></TABLE-GROUP>
"""

# Real DART layout: cells carry AUNIT/ACODE codes, reasons may have no (+)/(-).
DART_CODED = """<TBODY>
<TR ACOPY="Y"><TU AUNIT="RPT_RSN" AUNITVALUE="89">주식병합</TU><TU AUNIT="MDF_DM" AUNITVALUE="20261013">2026.10.13</TU><TU AUNIT="STR_KND" AUNITVALUE="1">보통주</TU>
<TE ACODE="BFR_STK_CNT">5,749,229</TE><TE ACODE="MDF_STK_CNT">-4,599,384</TE><TE ACODE="AFR_STK_CNT">1,149,845</TE><TE ACODE="ACI_AMT2">-</TE><TE ACODE="RMK">-</TE><TU AUNIT="TRD_PLN_RD" AUNITVALUE="-">-</TU></TR>
<TR ACOPY="Y"><TU AUNIT="RPT_RSN" AUNITVALUE="1">장내매수</TU><TU AUNIT="MDF_DM" AUNITVALUE="20261112">2026년 11월 12일</TU><TU AUNIT="STR_KND" AUNITVALUE="1">보통주</TU>
<TE ACODE="BFR_STK_CNT">1,000</TE><TE ACODE="MDF_STK_CNT">3,000</TE><TE ACODE="AFR_STK_CNT">4,000</TE><TE ACODE="ACI_AMT2">12,500</TE><TE ACODE="RMK"></TE><TU AUNIT="TRD_PLN_RD" AUNITVALUE="-">-</TU></TR>
<TR ACOPY="N"><TD COLSPAN="3">합 계</TD><TE>1</TE><TE>2</TE><TE>3</TE><TE>-</TE><TE>-</TE><TE>-</TE></TR>
</TBODY>"""

FORM4 = """<SEC-DOCUMENT>
<DOCUMENT><TYPE>4<TEXT>
<XML>
<?xml version="1.0"?>
<ownershipDocument>
  <issuer><issuerCik>0001234567</issuerCik><issuerName>Halden Robotics Inc</issuerName><issuerTradingSymbol>hldn</issuerTradingSymbol></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>0009999999</rptOwnerCik><rptOwnerName>Doe Jane</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>0</isDirector><isOfficer>1</isOfficer><officerTitle>Chief Executive Officer</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-11-12</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>10000</value></transactionShares><transactionPricePerShare><value>24.5</value></transactionPricePerShare><transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-11-13</value></transactionDate>
      <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>5000</value></transactionShares><transactionPricePerShare><value>1</value></transactionPricePerShare></transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
</XML>
</TEXT></DOCUMENT></SEC-DOCUMENT>"""


def test_dart():
    rows = parse_trade_rows(DART_DOC)
    assert len(rows) == 5, rows
    buys = [r for r in rows if r["cat"] == "buy" and r["stock"]]
    assert sum(r["qty"] for r in buys) == 200000
    assert sum(r["qty"] * r["price"] for r in buys) == 150000 * 39000 + 50000 * 39200
    sells = [r for r in rows if r["cat"] == "sell"]
    assert sells[0]["qty"] == 1000 and sells[0]["price"] == 40000
    assert rows[0]["date"] == "20261112"
    assert [r["reason"] for r in rows if r["cat"] == "other"] == ["증여"]
    assert not rows[4]["stock"]


def test_dart_coded():
    rows = parse_trade_rows(DART_CODED)
    assert [r["reason"] for r in rows] == ["주식병합", "장내매수"], rows
    assert rows[0]["cat"] == "other" and rows[0]["date"] == "20261013"
    assert rows[1]["cat"] == "buy" and rows[1]["qty"] == 3000 and rows[1]["price"] == 12500 and rows[1]["date"] == "20261112"


def test_form4():
    ev = parse_form4(FORM4)
    assert ev["tk"] == "HLDN" and ev["cik"] == "1234567"
    assert ev["role"] == "Chief Executive Officer"
    assert ev["buyQ"] == 10000 and ev["buyAmt"] == 245000 and ev["sellQ"] == 0
    assert ev["tdate"] == "2026-11-12"
    assert ev["trade"] and ev["codes"] == ["M", "P"]
    assert ev["px"] == [["2026-11-12", "b", 10000.0, 24.5]]
    other = parse_form4(FORM4.replace(">P<", ">F<"))
    assert other["trade"] is False and other["co"] == "Halden Robotics Inc"


def test_format():
    assert to_num("(1,234)") == -1234 and to_num("-") == 0 and to_num("39,000원") == 39000
    assert iga("박O준") == "이" and iga("정O우") == "가" and iga("(주)누리온홀딩스") == "가"
    assert fmt_krw(7.8e9) == "78.0억" and fmt_krw(2.1e11) == "2,100억" and fmt_krw(3.4e7) == "3,400만"
    assert fmt_krw(-9.21e9, sign=True) == "−92.1억"
    assert fmt_usd(2.4e6) == "$2.4M" and fmt_usd(860e3) == "$860K"


def test_display():
    ev = {"id": "20261113000123", "mk": "kr", "t": "trade", "date": "2026-11-13", "seen": "2026-11-13T18:02",
          "code": "000001", "co": "가람반도체", "who": "박O준", "role": "대표이사",
          "buyQ": 200000, "buyAmt": 7.8e9, "sellQ": 0, "sellAmt": 0, "rateChg": 0.42}
    row = display(ev)
    assert row["sub"] == "대표이사 박O준이 장내에서 샀어요", row["sub"]
    assert row["amt"] == "78.0억" and row["d"] == "+0.42%p" and row["dk"] == "buy" and row["time"] == "18:02"
    assert row["link"] == "/c/000001/"


def test_periods_and_prices():
    import datetime as dt
    import json
    import tempfile
    from build import build_market
    days, d = [], dt.date(2026, 11, 13)
    while len(days) < 45:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d -= dt.timedelta(days=1)
    evs = [{"id": f"r{i}", "mk": "kr", "t": "trade", "date": day, "code": "000001", "co": "가람", "cls": "코스피",
            "who": "박O준", "role": "대표이사", "buyQ": 100, "buyAmt": 100 * 1000, "sellQ": 0, "sellAmt": 0}
           for i, day in enumerate(days)]
    evs[0]["px"] = [["20261112", "b", 100, 1000], ["20261113", "b", 300, 2000]]
    out = tempfile.mkdtemp()
    site = build_market("kr", evs, out, "2026-11-13T18:00")
    one, two = site["p"]["1m"]["w"], site["p"]["2w"]["w"]
    assert one["n"] == 20 and two["n"] == 10 and one["hasPrev"] and site["w"] == one
    assert one["from"] == days[19] and two["from"] == days[9]
    # exact totals in won for the headline number (20 days x 100,000원)
    assert one["netAmt"] == 2_000_000 and one["prevNetAmt"] == 2_000_000 and two["netAmt"] == 1_000_000
    # a filing still waiting inside the earlier month: no comparison yet
    site = build_market("kr", evs, out, "2026-11-13T18:00", complete_after=days[25])
    assert not site["p"]["1m"]["w"]["hasPrev"] and site["p"]["2w"]["w"]["hasPrev"]
    c = json.load(open(os.path.join(out, "c", "000001.json"), encoding="utf-8"))
    assert c["tv"] == "KRX:000001"
    assert c["netAmt"] == 4_500_000 and c["buyAmt"] == 4_500_000 and c["sellAmt"] == 0
    pr = c["price"]
    first = [x for x in pr["pts"] if x["d"] == "2026-11-13"][0]
    assert first["p"] == 1750 and first["q"] == 400  # (100*1000 + 300*2000) / 400, latest row date
    assert pr["from"] == "2026-08-15" and pr["avgSell"] == 0


def test_price_flag_and_filtered_rank():
    import json
    import tempfile
    from build import build_market, price_flag

    def ev(i, tk, co, role, q, p, day="2026-11-13", cik="1"):
        return {"id": f"u{i}", "mk": "us", "t": "trade", "date": day, "tk": tk, "cik": cik, "co": co,
                "who": f"P{i}", "role": role, "buyQ": q, "buyAmt": q * p, "sellQ": 0, "sellAmt": 0,
                "px": [[day, "b", q, p]]}

    lona = ev(1, "LONA", "LeonaBio, Inc.", "10% 주주", 3149470, 3149.47)
    acme = [ev(2, "ACME", "Acme Corp", "Chief Executive Officer", 1000, 10),
            ev(3, "ACME", "Acme Corp", "이사", 1000, 11),
            ev(4, "ACME", "Acme Corp", "이사", 1000, 120)]
    fund = ev(5, "NFRX", "2023 ETF Series Trust", "이사", 5000, 30)
    nokey = ev(6, "", "Hancock Senior Loan Trust", "이사", 9000, 30, cik="1742951")
    holder = ev(7, "BIGH", "Big Holder Inc", "10% 주주", 9000, 30)
    good = ev(8, "GOOD", "Good Inc", "Chief Financial Officer", 2000, 40)
    evs = [lona, *acme, fund, nokey, holder, good]
    assert price_flag(evs) == {"u1", "u4"}
    # SCHMID 0002125667-26-000005: $1,731,429/share on 60,000 shares (under 100,000) and the company has
    # only one other report, so neither rule above catches it; same for SIMPPLE's $162,219 sale
    shmd = [ev(9, "SHMD", "SCHMID Group N.V.", "CFO", 11394, 4.51, day="2026-10-01"),
            ev(10, "SHMD", "SCHMID Group N.V.", "CFO", 60000, 1731429.0, day="2026-11-25")]
    sppl = ev(11, "SPPL", "SIMPPLE LTD.", "Acting Chief Executive Officer", 62894, 162219.43)
    nvr = ev(12, "NVR", "NVR INC", "이사", 300, 7500)  # a real $1,000+ stock, small trade: kept
    late = ev(13, "LATE", "Late Filer Inc", "이사", 100, 20, day="2026-11-25")
    late["px"][0][0] = "2023-04-03"  # filed years late but the price is fine: kept
    assert price_flag(shmd + [sppl, nvr, late]) == {"u10", "u11"}

    out = tempfile.mkdtemp()
    site = build_market("us", evs, out, "2026-11-13T18:00")
    x = [r["link"] for r in site["p"]["1m"]["rankBuyX"]]
    assert x == ["/u/GOOD/", "/u/ACME/"], x  # 80,000 > 21,000 (flagged 120,000 left out)
    allr = [r["link"] for r in site["p"]["1m"]["rankBuy"]]
    assert "/u/LONA/" not in allr and "/u/BIGH/" in allr
    lrow = [r for r in site["feed"] if r["id"] == "u1"][0]
    assert lrow["chk"] and lrow["d"] == "단가 확인 필요"
    rec = json.load(open(os.path.join(out, "recent_us.json"), encoding="utf-8"))
    assert rec["ACME"]["people"] == 3 and rec["ACME"]["netV"] == 0.0 and len(rec["ACME"]["last"]) == 3
    assert rec["GOOD"]["link"] == "/u/GOOD/" and rec["GOOD"]["last"][0]["kind"] == "buy"
    assert rec["LONA"]["last"][0]["chk"] is True


def test_resample_saves_raw_once():
    import io
    import tempfile
    import zipfile
    import run
    d = tempfile.mkdtemp()
    listing = os.path.join(d, "resample.txt")
    with open(listing, "w", encoding="utf-8") as f:
        f.write("# 원문을 다시 받을 접수번호\n20261126000250  삼성전자\n20261125000231\n20261124000331\nabc\n20261123000001\n")
    os.makedirs(os.path.join(d, "debug"))
    with open(os.path.join(d, "debug", "kr_20261125000231.xml"), "w") as f:
        f.write("already saved")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("doc.xml", DART_CODED)
    calls, logs = [], []

    def fetch(no):
        calls.append(no)
        if no == "20261126000250":
            return buf.getvalue()
        return "<result><status>014</status><message>파일이 존재하지 않습니다</message></result>".encode()

    run.resample(d, listing, fetch, logs.append)
    assert calls == ["20261126000250", "20261124000331", "20261123000001"], calls
    with open(os.path.join(d, "debug", "kr_20261126000250.xml"), encoding="utf-8") as f:
        assert len(parse_trade_rows(f.read())) == 2
    assert not os.path.exists(os.path.join(d, "debug", "kr_20261124000331.xml"))
    assert any("20261124000331" in x and "014" in x for x in logs), logs
    calls.clear()

    def down(no):  # DART unreachable: stop at the first error so the run is not held up
        calls.append(no)
        raise TimeoutError()

    run.resample(d, listing, down, logs.append)
    assert calls == ["20261124000331"], calls


def test_prune_debug_keeps_30():
    import tempfile
    import run
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "debug"))
    for i in range(32):
        open(os.path.join(d, "debug", f"kr_2026110100{i:04d}.xml"), "w").close()
    run.prune_debug(d)
    left = sorted(os.listdir(os.path.join(d, "debug")))
    assert len(left) == 30 and left[0] == "kr_20261101000002.xml"


def test_audit_data():
    import json
    import tempfile
    sys.path.insert(0, os.path.dirname(__file__))
    from audit_data import audit
    d = tempfile.mkdtemp()

    def put(rel, obj):
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(obj if isinstance(obj, str) else json.dumps(obj))

    def kr(i, **kw):
        return dict({"id": i, "mk": "kr", "t": "trade", "date": "2026-11-20", "code": "000001", "co": "가람",
                     "buyQ": 0, "buyAmt": 0, "sellQ": 0, "sellAmt": 0, "parsed": True, "px": []}, **kw)

    def us(i, tk, p, q=100, px=None):
        return {"id": i, "mk": "us", "t": "trade", "date": "2026-11-20", "tk": tk, "co": tk, "cik": "1",
                "buyQ": q, "buyAmt": q * p, "sellQ": 0, "sellAmt": 0, "px": [["2026-11-20", "b", q, p]] if px is None else px}

    put("events/kr/2026-11-20.json", [
        kr("k1", parsed=False), kr("k2", buyQ=100, px=[]),
        kr("k3", sellQ=10, sellAmt=10, px=[["20261120", "s", 10, 1]]),
        {k: v for k, v in kr("k4", buyQ=5, buyAmt=0).items() if k != "px"},  # old record: no px field
        {"id": "m1", "mk": "kr", "t": "major", "date": "2026-11-20"}])
    put("events/us/2026-11-20.json", [
        us("a1", "ACME", 10), us("a2", "ACME", 11), us("a3", "ACME", 120),  # a3 flagged (10x off median)
        us("b1", "BETA", 5), us("b2", "BETA", 80),  # only one other report: not flagged, still odd
        us("c1", "CORE", 5, q=200, px=[["2026-11-20", "b", 100, 5], ["2026-11-20", "b", 100, 90]]),
        us("z1", "ZERO", 0, px=[])])
    put("debug/kr_20261120000001.xml", DART_CODED)
    put("debug/kr_20261120000002.xml", "<TABLE><TR><TD>무엇</TD></TR></TABLE>")
    put("runs.log", "\n".join([
        "[11-18 09:00:00] KR: 20261117000001 실패 (1회): old",
        "[11-20 08:00:00] KR: 20261120000009 실패 (1회): HTTPError",
        "[11-20 08:00:01] KR: 처리 3건, 남은 대기 7건, API 9회",
        "[11-20 08:01:00] US: 읽음 10건, 장내거래 2건, 실패 3건(다음에 다시), 남은 대기 5건, 요청 12회, 403 2회",
        "[11-20 09:00:00] 끝 (40초)"]))
    a = audit(d)
    assert a["kr_trades"] == 4
    assert a["parsed"] == (1, ["k1"])
    assert a["zero_kr"] == (1, ["k2"]) and a["old_kr"][0] == 1
    assert a["zero_us"] == (1, ["z1"])
    assert a["flag_us"] == (1, ["a3"]) and a["flag_kr"][0] == 0
    assert a["debug"] == (1, ["20261120000002"])
    assert a["runs"] == (3 + 1 + 7 + 5, ["20261120000009"]) and a["runs_detail"] == {
        "fail": 4, "403": 2, "wait_kr": 7, "wait_us": 5}
    assert a["us_odd"] == (3, ["b1", "b2", "c1"]), a["us_odd"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
