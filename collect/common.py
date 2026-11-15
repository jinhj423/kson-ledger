"""Shared helpers: HTTP, time, JSON files, Korean particles, number formatting."""
import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.request

KST = dt.timezone(dt.timedelta(hours=9))


def now_kst():
    return dt.datetime.now(KST)


def get(url, headers=None, timeout=40, tries=3):
    """GET bytes. Returns None on 404. Retries transient errors."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (403, 429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(3 * (i + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if i < tries - 1:
                time.sleep(3 * (i + 1))
                continue
            raise


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def to_num(s):
    """'1,234' -> 1234.0, '(1,234)' / '-1,234' -> -1234.0, '-' / '' -> 0.0"""
    if s is None:
        return 0.0
    s = str(s).replace(",", "").replace(" ", "").replace("－", "-").replace("△", "-")
    neg = s.startswith("(") and s.endswith(")")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return 0.0
    v = float(m.group())
    return -abs(v) if neg else v


def iga(word):
    """Pick 이/가 for a Korean word (by the last Hangul syllable)."""
    w = re.sub(r"\(.*?\)|\s+$", "", word or "").strip()
    for ch in reversed(w):
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            return "이" if code % 28 else "가"
        if ch.isdigit():
            return "이" if ch in "013678" else "가"
        if ch.isalpha():
            return "가"
    return "가"


def fmt_krw(won, sign=False):
    """Won -> '78.0억' / '1,234억' / '3,400만'."""
    a = abs(won)
    if a >= 1e10:
        s = f"{a / 1e8:,.0f}억"
    elif a >= 1e8:
        s = f"{a / 1e8:.1f}억"
    elif a >= 1e4:
        s = f"{a / 1e4:,.0f}만"
    elif a > 0:
        s = f"{a:,.0f}원"
    else:
        return "0"
    if sign:
        s = ("+" if won > 0 else "−") + s
    return s


def fmt_usd(usd, sign=False):
    a = abs(usd)
    if a >= 1e9:
        s = f"${a / 1e9:.1f}B"
    elif a >= 1e6:
        s = f"${a / 1e6:.1f}M"
    elif a >= 1e3:
        s = f"${a / 1e3:.0f}K"
    elif a > 0:
        s = f"${a:,.0f}"
    else:
        return "$0"
    if sign:
        s = ("+" if usd > 0 else "−") + s
    return s


def fmt_shares(q):
    q = abs(q)
    if q >= 1e4:
        return f"{q / 1e4:,.1f}만 주".replace(".0만", "만")
    return f"{q:,.0f}주"
