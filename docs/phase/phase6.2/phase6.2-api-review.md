# Phase 6.2 rev.2 API 개발자 검토 리포트 — 윤에이피

> **검토일**: 2026-04-14 (단순화 방향 재검토)
> **검토 대상**: 포털 수집 단순화 아키텍처 (KIS 주경로 + 포털 장후 보조)

---

## 요약

| 항목 | 판정 |
|------|------|
| 08:00 포털 제거 -> KIS 직접 | ✅ 통과 — 구조적 실패 경로 제거 |
| 08:30 retry 전환 | ✅ 통과 — KIS 실패 시 KIS 재시도로 |
| 14:00 cron 제거 | ✅ 통과 — 16:00으로 대체 |
| 16:00 포털 수집 신규 | ✅ 통과 — 구현 간단 |
| validate_premarket_db 수정 | ✅ 통과 |
| 백필 전략 | ✅ 통과 — 기존 API 활용 |

---

## 항목별 검증 결과

### 1. 08:00 포털 제거의 기술적 타당성
- **판정**: ✅ 명확히 타당
- 공공데이터포털 공식 정책: "기준일자로부터 영업일 하루 뒤 오후 1시 이후 업데이트"
- 08:00 호출 = T-1 데이터가 아직 미배포 → 구조적 실패
- **실전 팁**: 포털은 때때로 09~11시에 조기 배포하는 경우가 있으나, 이에 의존하는 건 "운이 좋으면 동작하는 코드"
- 08:00에 KIS 일봉 API(`KISDailyCollector.collect_all`)를 직접 호출하면:
  - 내장 3회 재시도 + 지수 백오프 (kis_daily_collector.py L71-86)
  - 전 종목 OHLCV 수집 완비 (market_cap만 None)
  - 11일간 실전 검증 완료

### 2. scheduler.py `_premarket_collect` 수정 방안
- **판정**: ✅ 구현 명확
- 현재 (L563-645): 포털 시도 -> 실패 시 `_run_kis_daily_fallback()` 호출
- **변경**: 포털 시도 코드 제거, KIS 일봉을 직접 호출
- 핵심 변경:
  ```python
  # 기존: DataGoKrCollector -> 실패 -> _run_kis_daily_fallback()
  # 변경: KISDailyCollector.collect_all() 직접 호출
  ```
- 포털 관련 import, 분기, 예외 처리 대폭 단순화
- pipeline_status "premarket" = KIS 성공 시 "success" (기존 폴백 경로와 동일)

### 3. 08:30 `_premarket_retry` 전환
- **판정**: ✅ KIS 재시도로 전환 권고
- 현재 (L668-726): 포털 재시도 → 성공 시 스크리닝 재실행
- **변경**: KIS 수집 실패 시에만 KIS 재시도
  ```python
  # premarket_status != "success" → KIS 재시도
  # premarket_status == "success" → 스킵 (기존 로직 유지)
  ```
- 재시도 성공 시 스크리닝 재실행 로직은 그대로 유지 (L709-719)
- 포털 관련 코드만 제거, 구조는 동일

### 4. 16:00 포털 수집 구현
- **판정**: ✅ 간단하게 구현 가능
- 기존 `DataGoKrCollector.collect_all(target_date=...)` 그대로 사용
- target_date: 당일 or 전 거래일 (포털이 어떤 날짜를 배포하는지에 따라)
- **주의점**: 포털 `collect_all`은 `_upsert_stock`에서 listed_shares 갱신 (L175) + `_save_market_data`에서 market_cap 포함 upsert
- 기존 KIS 데이터(source='kis_daily')와 **별도 행**으로 저장됨 (source='data_go_kr')
- unique 제약조건: `(stock_code, data_date, source)` → 중복 없음
- **cron 등록**:
  ```python
  self._scheduler.add_job(
      self._portal_supplement_collect,
      CronTrigger(hour=16, minute=0, timezone=tz),
      id="portal_supplement",
      misfire_grace_time=MISFIRE_GRACE_TIME,
  )
  ```

### 5. validate_premarket_db 수정
- **판정**: ✅ 필수 수정
- 현재 (validator.py L226-227): `MarketData.source == "data_go_kr"` 전용
- KIS가 주 경로이므로: `MarketData.source.in_(["data_go_kr", "kis_daily"])` 확장 필수
- 이 수정이 없으면 08:00 KIS 수집 후 DB 검증이 항상 실패 ("건수 부족: 0 < 1500")
- **이미 validate_screening_readiness에서는 소스 무관하게 체크** → 일관성 확보

### 6. validate_portal_freshness 불필요
- **판정**: ✅ 제거 가능
- 기존 계획: portal_fresh 체크용 validate_portal_freshness 신규 추가
- 단순화 후: 포털을 08:00에 호출하지 않으므로 "포털 최신성" 체크 자체가 불필요
- 16:00 수집은 무조건 실행 (실패하면 경고 로그만) — 스킵 조건 불필요

### 7. 백필 전략
- **판정**: ✅ 기존 API 활용
- `trigger_premarket_date` (scheduler.py L505-527): 포털 기반, 날짜 지정 가능
- 4/4~4/10 백필은 수동으로 API 호출하면 됨 (Sprint 내 Task로 포함)
- 추가 스크립트 불필요 — 기존 인프라 충분

---

## 파라미터 조정 권고

| 항목 | 기존 Phase 6.2 | 단순화 권고 | 근거 |
|------|---------------|------------|------|
| 14:00 cron | portal_afternoon_collect | **제거** | 16:00으로 대체 |
| 16:00 cron | 없음 | **portal_supplement_collect 신규** | 포털 데이터 확실한 시간대 |
| portal_fresh 플래그 | Redis 키 | **제거** | 포털 08:00 호출 없으므로 불필요 |
| validate_portal_freshness | 신규 메서드 | **제거** | 불필요 |
| validate_premarket_db 소스 | data_go_kr 전용 | **data_go_kr + kis_daily** | KIS 주 경로 반영 |
| 백필 스크립트 | scripts/backfill_portal.py | **기존 trigger_premarket_date 활용** | 신규 코드 불필요 |
| KIS 폴백 streak | Redis 키 | **제거** | 폴백 개념 소멸 |

---

## 리스크 및 대안

- **리스크**: 16:00 포털 수집 시 포털이 당일 데이터를 아직 미배포한 경우 (드물지만 가능)
- **대안**: 포털 응답의 actual_date != requested_date 검증 로직이 이미 존재 (data_go_kr.py L80-84) → 날짜 불일치 시 경고 로그
- **리스크**: KIS REST API 자체 장기 장애
- **대안**: 08:30 KIS 재시도 + 기존 pipeline_healthy=false 로직으로 자동매매 차단 (이미 구현됨)
- **리스크**: 포털 Rate Limit (일 1,000건) — 16:00 정규 수집(~10건) + 백필 시 누적
- **대안**: 백필은 하루 최대 2거래일씩 실행 (기존 권고 유지)
