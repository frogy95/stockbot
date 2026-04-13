# Phase 6.2 리스크관리 검토 리포트 — 최리스크

> **검토일**: 2026-04-14
> **검토 대상**: 포털 수집 타이밍 불일치 해결 아키텍처 초안

---

## 요약

| 항목 | 판정 |
|------|------|
| 수정 방향 (하이브리드 A+B) | ✅ 통과 |
| retry 조건 강화 | ✅ 통과 |
| 포털 부재 시 스크리닝 영향 | ❌ 재검토 — market_cap=0 종목 안전장치 필수 |
| pipeline_healthy 판정 | ⚠️ 주의 — 포털 데이터 존재 여부 반영 필요 |
| 자동매매 차단 조건 | ⚠️ 주의 — KIS 폴백 연속 시 자동매매 제한 |

---

## 항목별 검증 결과

### 1. market_cap=0 리스크 (최우선)
- **판정**: ❌ 재검토 필수
- KIS 일봉 수집은 `market_cap=None`으로 저장 (kis_daily_collector.py L113)
- screener.py L406-408에서 `market_cap=0`이면 `listed_shares * close_price`으로 보정 시도
- 하지만 `listed_shares`도 포털 경유로만 갱신 → 신규 상장 or 주식분할 종목은 보정 불가
- **위험**: market_cap=0 종목이 시총 필터(500억)에서 전부 탈락 → 스크리닝 모수 급감
- **필수 조치**: KIS 폴백 시 stocks.listed_shares가 존재하면 시총 계산 보정 로직 강화, 없으면 해당 종목을 "데이터 불완전" 표시

### 2. KIS 폴백 연속 시 자동매매 제한
- **판정**: ⚠️ 주의
- 포털 데이터 없이 KIS만으로 N일 연속 운영 시:
  - market_cap 열화 → 시총 필터 정확도 저하
  - listed_shares 미갱신 → 보정 로직도 열화
- **권고**: KIS 폴백 연속 3거래일 이상 시 `pipeline_healthy=false` 강제 (자동매매 차단)
- 반자동 모드는 계속 허용 (사용자가 판단)

### 3. retry 조건 강화
- **판정**: ✅ 통과
- 현재: `premarket.status == "success"` → 포털 실패해도 KIS 성공이면 스킵
- 개선: 포털 데이터 존재 여부(source='data_go_kr', 당일 기준일)를 독립 체크
- 포털 미수집이면 08:30/14:00 재시도 계속 시도

### 4. pipeline_healthy 판정 강화
- **판정**: ⚠️ 주의
- 현재: CORE_STEPS(premarket, primary_screen) 모두 success이면 healthy
- 문제: KIS 폴백 성공 = premarket success → healthy=true이지만 데이터 불완전
- **권고**: `pipeline_healthy`에 "포털 데이터 최신성" 조건 추가
  - 포털 데이터 T-1 이내 존재 → healthy=true
  - 포털 데이터 T-2 이상 또는 부재 → healthy=false (KIS만으로는 불완전)

---

## 파라미터 조정 권고

| 항목 | 원래값 | 권고값 | 근거 |
|------|--------|--------|------|
| KIS 폴백 연속 자동매매 차단 | 없음 | 3거래일 | 시총 데이터 열화 한계 |
| pipeline_healthy 조건 | CORE_STEPS success | + 포털 T-1 이내 존재 | 데이터 완전성 보장 |
| market_cap=0 안전장치 | listed_shares 보정만 | + 경고 로그 + 스크리닝 제외 옵션 | 잘못된 시총 0으로 필터 왜곡 방지 |

---

## 리스크 및 대안

- **최대 리스크**: pipeline_healthy 조건 강화 시 KIS 폴백만으로 운영하는 날이 자동매매 불능 → 수익 기회 상실
- **대안**: 자동매매 차단 대신 "포지션 사이즈 50% 축소" + "경고 알림"으로 완화 가능
- **권고**: 보수적으로 3거래일 연속 시 차단 유지. 1~2일은 포지션 축소로 대응
- **부가 리스크**: 14:00 cron이 포털 장애와 동시 발생 시 추가 실패 → 알림 피로 주의, 알림 중복 방지 로직 필요
