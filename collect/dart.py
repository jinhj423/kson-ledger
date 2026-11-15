"""Korea: OpenDART filings -> events.

Event types
  trade    임원·주요주주 특정증권등 소유상황보고서 (원문 '세부변동내역' 표에서 장내매수/장내매도 수량·단가)
  major    주식등의 대량보유상황보고서 (5% 보유)
  buyback  주요사항보고서 자기주식 취득 결정
  control  거래소공시 최대주주 변경
"""
import datetime as dt
import html
import io
import json
import os
import re
import time
import urllib.parse
import zipfile

from common import get, now_kst, to_num

API = "https://opendart.fss.or.kr/api/"
LISTED = {"Y": "코스피", "K": "코스닥"}


class RateLimited(Exception):
    pass


class Dart:
    def __init__(self, key):
        self.key = key
        self.calls = 0
        self._ele = {}
        self._major = {}

    def call(self, name, **params):
        params["crtfc_key"] = self.key
        raw = get(API + name + "?" + urllib.parse.urlencode(params))
        self.calls += 1
        time.sleep(0.08)
        if raw is None:
            return None
        if name == "document.xml":
            if raw[:2] == b"PK":
                return raw
            text = raw.decode("utf-8", "replace")
            if "<status>020" in text:
                raise RateLimited()
            return None
        data = json.loads(raw.decode("utf-8"))
        st = data.get("status")
        if st == "000":
            return data
        if st == "013":
            return {"list": []}
        if st == "020":
            raise RateLimited()
        raise RuntimeError(f"DART {name} {st} {data.get('message')}")

    def elestock(self, corp):
        if corp not in self._ele:
            data = self.call("elestock.json", corp_code=corp) or {}
            self._ele[corp] = {r.get("rcept_no"): r for r in data.get("list", [])}
        return self._ele[corp]

    def majorstock(self, corp):
        if corp not in self._major:
            data = self.call("majorstock.json", corp_code=corp) or {}
            self._major[corp] = {r.get("rcept_no"): r for r in data.get("list", [])}
        return self._major[corp]


def kind_of(item):
    nm = item.get("report_nm", "")
    if "정정" in nm or item.get("corp_cls") not in LISTED:
        return None
    n = re.sub(r"\s|\[.*?\]", "", nm)
    if "소유상황보고서" in n and "임원" in n:
        return "trade"
    if "대량보유상황보고서" in n:
        return "major"
    if n.startswith("자기주식취득결정"):
        return "buyback"
    if n == "최대주주변경" or n.startswith("최대주주변경("):
        return "control"
    return None


def scan(d, ty, bgn, end, seen, max_pages):
    """Newest-first listing; stops after a page with nothing new."""
    out, page = [], 1
    while page <= max_pages:
        data = d.call("list.json", bgn_de=bgn, end_de=end, pblntf_ty=ty,
                      page_no=page, page_count=100, sort="date", sort_mth="desc") or {}
        rows = data.get("list", [])
        fresh = [r for r in rows if r.get("rcept_no") not in seen]
        out += fresh
        if not rows or not fresh or page >= int(data.get("total_page") or 1):
            break
        page += 1
    return out


# ---------- 원문 파싱 ----------
ROW = re.compile(r"<TR\b[^>]*>(.*?)</TR>", re.S | re.I)
CELL = re.compile(r"<(TE|TD|TU|TH)\b([^>]*)>(.*?)</\1>", re.S | re.I)
SIGNED = re.compile(r"\((\+|-|－|＋)\)")
CODE = re.compile(r'\b(?:AUNIT|ACODE)="([A-Z0-9_]+)"')
AVAL = re.compile(r'\bAUNITVALUE="([^"]*)"')


def _clean(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def unzip_text(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        parts = []
        for n in z.namelist():
            b = z.read(n)
            for enc in ("utf-8", "cp949"):
                try:
                    parts.append(b.decode(enc))
                    break
                except UnicodeDecodeError:
                    continue
        return "\n".join(parts)


def parse_trade_rows(text):
    """Rows of the '세부변동내역' table.

    Cells are read by their DART codes (RPT_RSN 보고사유, MDF_DM 변동일, STR_KND 종류,
    MDF_STK_CNT 증감, ACI_AMT2 단가). Older layouts without codes fall back to column order:
    보고사유 | 변동일 | 종류 | 변동 전 | 증감 | 변동 후 | 단가 | 비고
    """
    out = []
    for row in ROW.findall(text):
        raw = CELL.findall(row)
        if len(raw) < 7:
            continue
        by = {}
        for _, attrs, body in raw:
            m = CODE.search(attrs)
            if m:
                v = AVAL.search(attrs)
                by[m.group(1)] = (_clean(body), v.group(1) if v else "")
        if "RPT_RSN" in by and "MDF_STK_CNT" in by:
            reason = by["RPT_RSN"][0]
            date = by.get("MDF_DM", ("", ""))[1] or by.get("MDF_DM", ("", ""))[0]
            kind = by.get("STR_KND", ("", ""))[0]
            qty_s = by.get("MDF_STK_CNT", ("", ""))[0]
            price_s = by.get("ACI_AMT2", ("", ""))[0]
        else:
            cells = [_clean(c[2]) for c in raw]
            reason = cells[0]
            if not SIGNED.search(reason):
                continue
            date, kind, qty_s, price_s = cells[1], cells[2], cells[4], cells[6]
        if not reason or "합계" in reason.replace(" ", ""):
            continue
        stock = "주" in kind and not any(k in kind for k in ("사채", "권", "증서"))
        qty = abs(to_num(qty_s))
        price = abs(to_num(price_s))
        if "장내매수" in reason:
            cat = "buy"
        elif "장내매도" in reason:
            cat = "sell"
        else:
            cat = "other"
        out.append({
            "reason": SIGNED.sub("", reason).strip(),
            "date": re.sub(r"\D", "", date)[:8],
            "stock": stock,
            "qty": qty,
            "price": price,
            "cat": cat,
        })
    return out


def _clean_role(s):
    s = (s or "").strip()
    return "" if s in ("-", "") else s


def _date(rcept_dt):
    return f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:8]}"


def base_event(item, t, seen_at):
    return {
        "id": item["rcept_no"], "mk": "kr", "t": t,
        "date": _date(item["rcept_dt"]), "seen": seen_at,
        "code": item.get("stock_code", ""), "co": item.get("corp_name", ""),
        "corp": item.get("corp_code", ""), "cls": LISTED.get(item.get("corp_cls"), ""),
        "who": item.get("flr_nm", ""),
    }


def build_trade(d, item, seen_at, debug):
    ev = base_event(item, "trade", seen_at)
    e = d.elestock(item["corp_code"]).get(item["rcept_no"], {})
    if e.get("repror"):
        ev["who"] = e["repror"]
    role = _clean_role(e.get("isu_exctv_ofcps"))
    if not role and _clean_role(e.get("isu_main_shrholdr")):
        role = "주요주주"
    ev["role"] = role
    ev["rate"] = to_num(e.get("sp_stock_lmp_rate"))
    ev["rateChg"] = to_num(e.get("sp_stock_lmp_irds_rate"))
    raw = d.call("document.xml", rcept_no=item["rcept_no"])
    rows = parse_trade_rows(unzip_text(raw)) if raw else []
    if raw and not rows and len(debug) < 3:
        debug.append((item["rcept_no"], unzip_text(raw)[:60000]))
    b = [r for r in rows if r["cat"] == "buy" and r["stock"]]
    s = [r for r in rows if r["cat"] == "sell" and r["stock"]]
    ev["buyQ"] = sum(r["qty"] for r in b)
    ev["buyAmt"] = sum(r["qty"] * r["price"] for r in b)
    ev["sellQ"] = sum(r["qty"] for r in s)
    ev["sellAmt"] = sum(r["qty"] * r["price"] for r in s)
    ev["other"] = sorted({r["reason"] for r in rows if r["cat"] == "other"})
    ev["parsed"] = bool(rows)
    return ev


def build_major(d, item, seen_at):
    ev = base_event(item, "major", seen_at)
    r = d.majorstock(item["corp_code"]).get(item["rcept_no"], {})
    ev["who"] = r.get("repror") or ev["who"]
    ev["rate"] = to_num(r.get("stkrt"))
    ev["rateChg"] = to_num(r.get("stkrt_irds"))
    ev["reason"] = (r.get("report_resn") or "").strip()[:80]
    ev["new"] = ev["rate"] >= 5 and ("신규" in (r.get("report_tp") or "") + ev["reason"]
                                     or abs(ev["rate"] - ev["rateChg"]) < 0.01)
    return ev


def build_buyback(d, item, seen_at):
    ev = base_event(item, "buyback", seen_at)
    data = d.call("tsstkAqDecsn.json", corp_code=item["corp_code"],
                  bgn_de=item["rcept_dt"], end_de=item["rcept_dt"]) or {}
    r = next((x for x in data.get("list", []) if x.get("rcept_no") == item["rcept_no"]), {})
    ev["amt"] = to_num(r.get("aqpln_prc_ostk")) + to_num(r.get("aqpln_prc_estk"))
    ev["from"] = r.get("aqexpd_bgd", "")
    ev["to"] = r.get("aqexpd_edd", "")
    ev["how"] = (r.get("aq_mth") or "").strip()[:40]
    return ev


def collect(state, store_event, budget_s, log):
    """Pull new filings into the store. `state` is mutated (seen/pending/backfill)."""
    key = os.environ.get("DART_API_KEY")
    if not key:
        log("KR: DART_API_KEY 없음, 건너뜀")
        return []
    d = Dart(key)
    t0 = time.time()
    today = now_kst().date()
    seen = state.setdefault("seen", {})
    pending = state.setdefault("pending", [])
    in_pending = {p["rcept_no"] for p in pending}
    debug = []
    seen_at = now_kst().strftime("%Y-%m-%dT%H:%M")

    def ymd(x):
        return x.strftime("%Y%m%d")

    try:
        backfill = not state.get("backfilled")
        for ty, days, pages in (("D", 30, 120), ("B", 30, 40), ("I", 3, 60)):
            bgn = today - dt.timedelta(days=days if backfill else 2)
            rows = scan(d, ty, ymd(bgn), ymd(today), set(seen) | in_pending, pages if backfill else 8)
            for r in rows:
                k = kind_of(r)
                if k and r["rcept_no"] not in in_pending:
                    r["_k"] = k
                    pending.append(r)
                    in_pending.add(r["rcept_no"])
                elif not k:
                    seen[r["rcept_no"]] = r.get("rcept_dt", "")
        state["backfilled"] = True

        pending.sort(key=lambda r: r["rcept_no"], reverse=True)
        done = 0
        while pending and time.time() - t0 < budget_s:
            item = pending.pop(0)
            k = item["_k"]
            try:
                if k == "trade":
                    ev = build_trade(d, item, seen_at, debug)
                elif k == "major":
                    ev = build_major(d, item, seen_at)
                elif k == "buyback":
                    ev = build_buyback(d, item, seen_at)
                else:
                    ev = base_event(item, "control", seen_at)
            except RateLimited:
                pending.insert(0, item)
                raise
            except Exception as e:  # one bad filing must not stop the run
                item["_tries"] = item.get("_tries", 0) + 1
                log(f"KR: {item['rcept_no']} 실패 ({item['_tries']}회): {e}")
                if item["_tries"] < 3:
                    pending.append(item)
                else:
                    seen[item["rcept_no"]] = item["rcept_dt"]
                continue
            store_event(ev)
            seen[item["rcept_no"]] = item["rcept_dt"]
            done += 1
        log(f"KR: 처리 {done}건, 남은 대기 {len(pending)}건, API {d.calls}회")
    except RateLimited:
        log(f"KR: DART 호출 한도 도달, 다음 실행에 이어서 (API {d.calls}회)")
    return debug
