# Phase 6.2 API 개발자 검토 리포트 — 윤에이피

> **검토일**: 2026-04-14
> **검토 대상**: 포털 수집 타이밍 불일치 해결 아키텍처 초안

---

## 요약

| 항목 | 판정 |
|------|------|
| 포털 정책 해석 | ✅ 통과 — T+1 13시 정확 |
| 08:00 유지 + 14:00 보조 | ✅ 통과 |
| retry 조건 변경 | ✅ 통과 — portal_fresh 플래그 도입 |
| 백필 API 설계 | ⚠️ 주의 — Rate Limit 고려 필요 |
| validate_premarket_db 수정 | ✅ 통과 |

---

## 항목별 검증 결과

### 1. 공공데이터포털 정책 해석
- **판정**: ✅ 정확
- 공식: "기준일자로부터 영업일 하루 뒤 오후 1시 이후 업데이트, 일 1회"
- 금요일 데이터 → 월요일 13시 이후 (영업일 기준 T+1)
- 08:00 호출은 구조적으로 T-1 데이터 미배포 시점 → 간헐 성공은 조기 배포 덕분
- **실전 팁**: 포털은 실제로 T+1 09:00~11:00 사이에 조기 배포되는 경우가 잦음. 08:00 시도는 이 패턴을 활용하는 것이므로 제거하면 안 됨

### 2. 08:00 + 14:00 이중 수집 아키텍처
- **판정**: ✅ 통과
- 08:00: "기회주의적" 포털 시도 → 성공하면 최선, 실패하면 KIS 폴백
- 14:00: "정식" 포털 수집 → T+1 13시 정책 준수, 거의 항상 성공
- 14:00 수집 성공 시 기존 KIS 데이터와 **merge/보완** (market_cap, listed_shares 갱신)
- 중복 방지: `market_data` 테이블의 unique(stock_code, data_date, source) 보장

### 3. _premarket_retry 조건 변경
- **판정**: ✅ 통과
- 현재 (scheduler.py L680): `premarket_status == "success"` → 스킵
- 문제: KIS 폴백 성공 = success → 포털 재시도 영구 차단
- **권고 구현**:
  ```python
  # 포털 데이터 T-1 존재 여부 직접 확인
  portal_fresh = await self._check_portal_data_freshness()
  if portal_fresh:
      logger.info("포털 재시도 스킵: 포털 T-1 데이터 이미 존재")
      return
  ```
- `_check_portal_data_freshness()`: DB에서 `source='data_go_kr'` AND `data_date >= T-1` 건수 >= 1500 확인

### 4. 14:00 cron 구현 상세
- **판정**: ✅ 구현 가능
- 기존 `_premarket_collect()`를 거의 그대로 재사용 가능
- 차이점: pipeline_status 초기화하지 않음 (08:00에서 이미 초기화됨)
- 포털 성공 시: pipeline_status 보완 업데이트 + market_cap/listed_shares 갱신 알림
- 포털 실패 시: 경고 로그만 (이미 KIS 데이터로 운영 중)

### 5. validate_premarket_db 수정
- **판정**: ✅ 통과
- 현재 (validator.py L227): `source == "data_go_kr"` 전용 → KIS 데이터 무시
- **권고**: `source.in_(["data_go_kr", "kis_daily"])` 로 변경 (validate_screening_readiness와 일관성)
- 단, 별도 `validate_portal_freshness()` 메서드 신규 추가하여 포털 전용 최신성 체크

### 6. 백필 Rate Limit
- **판정**: ⚠️ 주의
- 공공데이터포털 일 호출 한도: 1,000건 (우리 환경변수 확인 필요)
- 5거래일 백필 = 5회 * ~10페이지 = ~50 API 호출 → 한도 내
- 하지만 당일 정상 수집(~10페이지) + 백필(~50페이지) = 누적 주의
- **권고**: 백필은 하루 최대 2거래일씩 나눠서 실행 (안전 마진)

---

## 파라미터 조정 권고

| 항목 | 원래값 | 권고값 | 근거 |
|------|--------|--------|------|
| 14:00 cron 시각 | 미정 | 14:00 KST | 포털 정책 T+1 13시 + 1시간 마진 |
| 08:30 retry 조건 | premarket.status == success | portal_fresh (DB 직접 확인) | KIS 폴백 성공과 독립 |
| validate_premarket_db 소스 | data_go_kr 전용 | data_go_kr + kis_daily | screening_readiness와 일관성 |
| 백필 일일 한도 | 없음 | 2거래일/일 | 포털 Rate Limit 안전 마진 |
| 포털 최신성 확인 임계값 | 없음 | 1500건 + data_date >= T-1 | 수집 완전성 보장 |

---

## 리스크 및 대안

- **리스크**: 14:00 cron과 08:00 파이프라인이 같은 날 같은 데이터를 중복 수집 → DB I/O 낭비
- **대안**: 14:00 수집 전 포털 최신성 체크하여 이미 수집됨이면 스킵 (portal_fresh 재사용)
- **리스크**: 포털 자체 장애(며칠간) 시 14:00 cron도 계속 실패 → 알림 피로
- **대안**: 포털 연속 실패 카운터 + N회 초과 시 알림 빈도 감소 (일 1회 요약)
