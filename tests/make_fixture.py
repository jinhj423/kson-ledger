"""Fake events -> /tmp/kson-fixture/site (for running the Worker locally). Run: python tests/make_fixture.py"""
import datetime as dt
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collect"))
import build  # noqa: E402

OUT = os.environ.get("FIXTURE_DIR", "/tmp/kson-fixture/site")
random.seed(7)
KR = [("000101", "가람반도체", "코스피"), ("000202", "누리온바이오", "코스닥"), ("000303", "청운중공업", "코스피"),
      ("000404", "다온식품", "코스피"), ("000505", "미르에너지", "코스닥"), ("000606", "해솔제약", "코스닥"),
      ("000707", "새벽로보틱스", "코스닥"), ("000808", "보람해운", "코스피"), ("000909", "단비전자", "코스닥")]
US = [("HLDN", "Halden Robotics Inc"), ("CRVB", "Corvane Bio Corp"), ("MRFE", "Mirefield Energy"),
      ("ORSY", "Orrin Systems"), ("VNTG", "Vantor Grid Holdings")]
NAMES = ["박O준", "유O민", "한O희", "서O진", "오O태", "김O현", "정O우", "이O석"]
ROLES = ["대표이사", "부사장", "전무", "상무", "사외이사", "CFO"]


def weekdays(n):
    d, out = dt.date(2026, 11, 13), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= dt.timedelta(days=1)
    return out[::-1]


def main():
    kr, us, i = [], [], 0
    for day in weekdays(30):
        for _ in range(random.randint(6, 14)):
            i += 1
            code, co, cls = random.choice(KR)
            buy = random.random() < 0.6
            q = random.randint(1, 40) * 1000
            px = random.randint(8, 90) * 1000
            kr.append({"id": f"2026{i:010d}", "mk": "kr", "t": "trade", "date": day, "seen": f"{day}T{random.randint(8, 18):02d}:{random.randint(0, 59):02d}",
                       "code": code, "co": co, "cls": cls, "who": random.choice(NAMES), "role": random.choice(ROLES),
                       "buyQ": q if buy else 0, "buyAmt": q * px if buy else 0, "sellQ": 0 if buy else q, "sellAmt": 0 if buy else q * px,
                       "rateChg": round(random.uniform(0.01, 0.5) * (1 if buy else -1), 2), "other": []})
        code, co, cls = random.choice(KR)
        kr.append({"id": f"2026{i:010d}9", "mk": "kr", "t": random.choice(["major", "buyback", "control"]), "date": day,
                   "seen": f"{day}T16:48", "code": code, "co": co, "cls": cls, "who": "한결자산운용",
                   "rate": 5.03, "rateChg": 5.03, "new": True, "amt": 5e9})
        for _ in range(random.randint(10, 20)):
            i += 1
            tk, co = random.choice(US)
            buy = random.random() < 0.35
            q = random.randint(1, 50) * 1000
            px = random.uniform(5, 120)
            us.append({"id": f"0001234567-26-{i:06d}", "mk": "us", "t": "trade", "date": day, "tk": tk, "co": co, "cik": "1",
                       "who": random.choice(["Doe Jane", "Smith John", "Lee Ann", "Park Min"]), "role": random.choice(["CEO", "CFO", "이사", "10% 주주"]),
                       "buyQ": q if buy else 0, "buyAmt": q * px if buy else 0, "sellQ": 0 if buy else q, "sellAmt": 0 if buy else q * px,
                       "url": "https://www.sec.gov/"})
    # a clear cluster for the highlight card
    for j, who in enumerate(NAMES[:5]):
        for day in weekdays(5):
            if (j + len(day)) % 4:
                i += 1
                kr.append({"id": f"2026{i:010d}", "mk": "kr", "t": "trade", "date": day, "seen": f"{day}T17:00",
                           "code": "000101", "co": "가람반도체", "cls": "코스피", "who": who, "role": ROLES[j],
                           "buyQ": 20000, "buyAmt": 20000 * 39000, "sellQ": 0, "sellAmt": 0, "rateChg": 0.1, "other": []})
    build.build_market("kr", kr, OUT)
    build.build_market("us", us, OUT)
    print("fixture ->", OUT, len(kr), len(us))


if __name__ == "__main__":
    main()
