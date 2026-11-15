# 큰손일지 (kson-ledger)

임원·주요주주·5% 보유자가 자기 회사 주식을 사고판 기록을 DART·SEC 공시 원문 기준으로 정리하는 사이트.

## 구조
- `collect/` — 파이썬 수집기. GitHub Actions가 10분마다 실행(`.github/workflows/collect.yml`).
  - `dart.py` 한국: 임원·주요주주 소유보고(원문 '세부변동내역' 표 파싱), 5% 대량보유, 자기주식 취득 결정, 최대주주 변경
  - `sec.py` 미국: Form 4 장내매수(P)·장내매도(S)
  - `build.py` 화면용 JSON(`site/kr.json`, `site/us.json`, 회사별 `site/c/*.json`, `site/u/*.json`)
  - 결과는 `data` 브랜치에 커밋 1개로 덮어씀(상태·일별 이벤트·화면 자료·디버그 샘플)
- `src/` — Cloudflare Worker. `data` 브랜치의 JSON을 받아 서버에서 HTML을 그림(검색 노출용).
- `public/` — CSS, 화면 동작 JS(숫자 올라감, 차트 읽기, 랭킹 전환, 검색 제안), 아이콘.

## 필요한 비밀값 (Settings → Secrets and variables → Actions)
- `DART_API_KEY` — OpenDART 인증키
- `SEC_USER_AGENT` — SEC 요청 머리말. 예: `KsonLedger 이름@example.com`

## 배포 (Cloudflare)
Workers & Pages → 만들기 → 저장소 가져오기 → `kson-ledger` → 배포 명령 `npx wrangler deploy`.

## 로컬 시험
```
python tests/test_parsers.py
python tests/make_fixture.py                 # 가짜 자료 -> /tmp/kson-fixture/site
(cd /tmp/kson-fixture/site && python -m http.server 8800) &
npx wrangler dev --var DATA_BASE:http://127.0.0.1:8800
```

## 원칙
추천·전망·목표가·수익 보장 표현을 쓰지 않는다. 공시 사실과 그 계산만 보여준다.
