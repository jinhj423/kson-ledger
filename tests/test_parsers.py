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
    assert parse_form4(FORM4.replace(">P<", ">M<")) is None


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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
