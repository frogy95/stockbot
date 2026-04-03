# Hotfix: 1차 스크리닝 date_subq source 필터 추가

**브랜치:** `hotfix/screener-date-source-filter`
**담당자:** frogy95
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료 (main PR #75 머지, develop 역머지 완료)
**배포일:** 2026-04-02

---

## 문제 분석

### 증상
1차 스크리닝(PrimaryScreener) 실행 시 candidates 0개 반환 — 장전 스크리닝이 완전히 무력화.

### 원인
`_fetch_today_and_prev`의 `date_subq`가 `market_data` 테이블 전체 소스의 최신 날짜를 조회했는데, KIS REST API로 수집된 ETF 시세(`source=kis_rest`)가 당일 날짜로 저장되면서 `data_go_kr` 수집 전에도 최신 날짜가 오늘로 갱신됨. 결과적으로 `data_go_kr` 기준으로 어제 데이터가 "prev"가 아닌 "2일 전"으로 밀려 주식의 `prev_volume=0`으로 집계되어 `volume_ratio` 계산 불가 → 필터 탈락.

### 영향 범위
- 장전 1차 스크리닝 전체 0 candidates
- ETF 시세 수집(08:00 이후)이 완료되면 `kis_rest` 날짜가 오늘로 기록되는 모든 상황에서 발생
- 1차 스크리닝 후 2차 스크리닝 및 매매 신호 생성 전체 영향

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/screening/screener.py` | `_fetch_today_and_prev` 내 `date_subq`에 `.where(MarketData.source == "data_go_kr")` 필터 추가 (2줄 추가, 1줄 기존 유지) |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `244e1f6` | fix(screener): _fetch_today_and_prev date_subq를 data_go_kr 소스로 제한 | 2026-04-02 |

---

## 검증

### 자동 검증
- pytest test_screener.py 10 passed

### 수동 검증
- ⬜ Railway 배포 후 다음 장전(08:00 이후) 1차 스크리닝 실행 로그 확인 — `primary_screen passed > 0` 확인

---

## PR
- **URL:** https://github.com/frogy95/stockbot/pull/75
- **대상:** main
- **역머지:** ✅ develop에 역머지 완료
