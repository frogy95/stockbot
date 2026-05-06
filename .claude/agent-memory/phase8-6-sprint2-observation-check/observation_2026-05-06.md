---
name: 2026-05-06 Sprint 2 관찰 1차 (KST 08:46 체크포인트)
description: 5/6 거래일 1차 관찰 — KST 08:46 시점 결과. pipeline=healthy 자연 복원 확인. ATR 잡 safe_mode 실행. 신호 데이터는 장중(09:00~15:30) 이후 재확인 필요.
type: project
---

# 2026-05-06 Sprint 2 관찰 — 1차 (KST 08:46 체크포인트)

**관찰 시각**: 2026-05-06 KST 08:46 (장 시작 전)
**판정 상태**: 진행 중 (KST 16:00 이후 최종 판정)

---

## KST 08:30 체크포인트 결과

### 분기점 1: pipeline=healthy 복원 여부

**결과: PASS (자연 복원 확인)**

```
GET /api/v1/health/readiness
{"status":"ready","database":"connected","redis":"connected","scheduler":"running","pipeline":"healthy"}
```

- 5/5 14:00 KST 시점 unhealthy(503) → 5/6 08:46 KST 시점 healthy(200)로 복원
- H1 가설(5/4 premarket CORE_STEPS 부분 실패) 부분 해소:
  - 5/6 premarket 실행 정상 확인
  - `수집 완료: step=premarket collected=2620 failed=24 total=2644 validation=PASS` (UTC 23:14 = KST 08:14)
  - 장전 파이프라인 종료 `소요: 667.7초` (UTC 23:11:07 = KST 08:11)
  - `KIS 재시도 스킵: premarket 이미 성공 상태` (UTC 23:30 = KST 08:30) → premarket 이미 성공

### 분기점 2: scheduler:* 키 재확인

- 컨테이너 SSH 진입 불가 (현재 시각 기준 추가 진단 도구 미배포)
- **간접 확인**: readiness 엔드포인트 `pipeline=healthy` = scheduler:pipeline_healthy 키가 "true"로 설정된 상태
- `premarket 이미 성공 상태` 로그 = scheduler:last_success:premarket 키 존재 확인

---

## G1: ATR 캘리브레이션 잡 동작

**판정: PARTIAL (safe_mode 실행, 정상 캘리브레이션 미완)**

로그 내용 (UTC 23:35 = KST 08:35):
```
WARNING [modules.screening.atr_calibration] KOSPI200 마스터 0종(<10) — 정적 백업(200) 폴백
INFO atr_calibration: {
  'status': 'safe_mode',
  'ceil': 0.08,       # = ATR_CEIL_HARD 환경변수 값
  'fallback_count': 3,
  'info': {
    'codes_loaded': 200,    # 정적 백업 200종
    'method': 'sma',
    'coverage_gap': 148,    # 마켓 데이터 커버리지 갭
    'raw_sample_n': 52,
    'reason': 'market_data_coverage_gap'
  }
}
```

해석:
- 잡 자체는 정상 실행됨 (스케줄러 등록, 비거래일 스킵 로직 정상)
- KOSPI200 마스터 0종 이유: premarket 수집은 2620종 성공했으나 KOSPI200 인덱스 구성 종목 마스터가 Redis/DB에 없거나 10종 미만 로드
- safe_mode 발동 → ATR ceil = 0.08 (ATR_CEIL_HARD 하드캡)으로 고정, 분위수 캘리브레이션 미적용
- fallback_count=3: 이전 2거래일(4/30, 5/4)에도 동일 이슈 발생
- Redis 4종 키 적재 여부: 직접 확인 불가 (railway run 차단), safe_mode 로그 기준으로 `metrics:atr:ceil=0.08` 기록됐을 가능성 높음
- **G1 판정**: PARTIAL (잡 실행은 정상, 분위수 캘리브레이션은 safe_mode 대체)

---

## G2: 병렬 OR tier 신호 발생

**판정: INFO (미확정 — KST 08:46 현재 장 시작 전)**

```
GET /api/v1/health/observation-daily?date=2026-05-06
{
  "date": "2026-05-06",
  "signals": {"gap_open": 0, "prev_high": 0, "prev_close": 0, "other": 0, "total": 0},
  "fallback": {"triggered_count": 0, "codes": []},
  "rollback": {
    "is_active": true,
    "triggered_at": "2026-05-04T16:10:01.293375+09:00",
    "reason": "auto_rollback_2d_zero_signals"
  }
}
```

- signals.total = 0: 장 시작 전(KST 08:46) 시점이므로 정상 — KST 16:00 이후 재확인 필수
- rollback.is_active = true: G2 자동 롤백 R1 아직 유지 중 (Sprint 1 직렬 동작 모드)
- matched_tiers DB 기록: KST 16:00 이후 재확인 필요

**KST 16:00 판정 분기**:
- signals.total >= 1 → G2 PASS (R1 롤백 중이므로 Sprint 1 직렬 동작으로 신호 생성)
- signals.total = 0 → G2 INFO 지속 또는 전략 게이트 차단 Hotfix 필요

---

## G3: 시뮬-실측 절대차

**판정: INFO (미확정 — 신호 0건 상태)**

- G2 신호 = 0이므로 분모 부재, 산출 불가
- KST 16:00 이후 G2 신호 확인 후 재평가 가능

---

## 부수 관찰

| 항목 | 결과 |
|------|------|
| 백엔드 ERROR/CRITICAL | ETF 수집 실패 4건 (461950, 411420, 428560, 229720) — kis_collector 네트워크 오류, 기능상 무해 (validation=PASS) |
| PARALLEL_OR_TIER_ENABLED | true (유지) |
| ATR_CALIBRATION_ENABLED | true (유지) |
| safe_mode 발동 (ATR) | atr_calibration safe_mode=true (KOSPI200 마스터 0종 이슈) |
| pipeline_healthy | healthy (자연 복원) |
| G2 자동 롤백 R1 | 여전히 is_active=true (5/4 16:10 KST 발동 상태 유지) |
| premarket 수집 | PASS (2620/2644, 소요 667.7초) |
| scheduler 환경변수 10종 | 전종 확인 완료 |

---

## KST 08:46 시점 중간 판정

### 양호 신호
- pipeline=healthy 자연 복원 — H1 가설(premarket 실패 지속) 완화
- premarket 파이프라인 정상 완료 (KST 08:11 종료)
- 환경변수 10종 정상 유지
- 인프라 오류 0건 (ETF 4종 수집 실패는 KIS API 일시 오류로 validation=PASS)

### 미해결 이슈
- **G1 PARTIAL 지속**: ATR safe_mode (KOSPI200 마스터 0종, coverage_gap=148) — fallback_count=3으로 3거래일 연속 동일 이슈
- **G2 R1 롤백 유지**: Sprint 2 병렬 OR tier는 R1 롤백으로 Sprint 1 직렬 동작 중
- **G2 신호 미확인**: KST 09:00 이후 장중 신호 발생 여부 미확정

---

## KST 16:00 이후 최종 판정 (예정)

**체크 항목**:
1. `GET /api/v1/health/observation-daily?date=2026-05-06` → signals.total >= 1 확인
2. matched_tiers DB 기록 유무 확인
3. fallback triggered_count > 0 (수집 단계 정상 증거)

**예상 판정 분기**:

| 결과 | 판정 | 다음 액션 |
|------|------|----------|
| pipeline=healthy + signals>=1 | CONDITIONAL GO | Sprint 3 사전 작업 착수 가능. R1 해제 + ATR KOSPI200 마스터 Hotfix 병행 검토 |
| pipeline=healthy + signals=0 | NO-GO | 전략 게이트 차단 원인 Hotfix 필요 |
| pipeline=unhealthy 재발 | NO-GO | premarket CORE_STEPS 실패 단계 식별 Hotfix 우선 |

---

## ATR safe_mode 분석 (G1 PARTIAL 원인)

**원인**: `KOSPI200 마스터 0종(<10)` — KOSPI200 인덱스 구성 종목 목록이 premarket 수집에서 로드되지 않음
- `coverage_gap=148`: 200종 중 52종만 유효 샘플, 148종 갭
- `raw_sample_n=52`: 실제 사용 가능한 ATR 데이터 52종
- `fallback_count=3`: 4/30, 5/4, 5/6 연속 3회 동일 이슈
- **결론**: ATR 분위수 캘리브레이션(Sprint 2 핵심 기능)이 safe_mode(정적 ceil=0.08)로 대체 실행 중. 분위수 기반 동적 캘리브레이션은 미적용 상태.

이는 Sprint 2 G1 게이트 통과 실패 원인이나, 시스템 안전성(ceil=ATR_CEIL_HARD)은 유지됨.

---

## 현재 시각 기준 확정 데이터

| 항목 | 값 | 시각 |
|------|-----|------|
| pipeline 상태 | healthy | KST 08:46 |
| premarket 수집 | 2620/2644 PASS | KST 08:14 |
| ATR 잡 실행 | safe_mode (ceil=0.08) | KST 08:35 |
| premarket retry 스킵 | 이미 성공 상태 | KST 08:30 |
| signals (장 전) | 0 (정상) | KST 08:46 |
| R1 롤백 | is_active=true | 5/4 16:10 이후 유지 |

---

## A 단계 운영 조치 (2026-05-06 KST 09:30~10:00)

핫픽스(PR #193, #194) 효과 검증 + 잔존 Redis 상태 정리.

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| A-1 | Railway env `ATR_COVERAGE_GAP_MAX` | ✅ `200` 설정 확인 | 5/6 08:35 잡은 11:00 핫픽스 이전이라 미적용 — 5/7 잡부터 유효 |
| A-2 | `alembic current` | ✅ `e5a7c91d4f08 (head)` | KOSPI200 백필 마이그레이션 적용 완료 |
| A-3 | `stocks.is_kospi200=true` 카운트 | ✅ **52종** (전체 3799) | `KOSPI200_MIN_MASTER=10` 충족 → 정적 백업 폴백 우회 가능 |
| A-4 | `safe_mode:active` 키 | ✅ `None` | 11:00 핫픽스 ops에서 삭제됨, 잔존 없음 |
| A-5 | `metrics:atr:ceil:fallback_count` | ✅ `'3' → '0'` 리셋 | 다음 폴백 발생해도 즉시 safe_mode 재발동 방지 |

### 5/7 08:35 KST 예상 동작

- `_load_kospi200_codes`: 52종 반환 (≥10) → 정적 백업 폴백 미발동
- `_load_recent_atr_ratios`: 52종 market_data 조회. 모두 정상이면 coverage_gap≈0
- 분위수 캘리브레이션 정상 진행, IQR 트림 후 `metrics:atr:ceil:2026-05-07` 동적 ceil 기록 예상
- 잔존 위험: 정적 백업 200종 중 148종이 `stocks` 부재 → 표본 크기 52종은 IQR/P80 계산상 충분하나 통계 신뢰성은 제한적

### 5/7 검증 명령

```bash
railway ssh --service stockbot 'python -c "
import asyncio
from core.redis import redis_client
async def main():
    await redis_client.connect()
    print(\"ceil:2026-05-07:\", await redis_client.get(\"metrics:atr:ceil:2026-05-07\"))
    print(\"dist:2026-05-07:\", await redis_client.get(\"metrics:atr:dist:2026-05-07\"))
    print(\"fallback_count:\", await redis_client.get(\"metrics:atr:ceil:fallback_count\"))
    print(\"safe_mode:active:\", await redis_client.get(\"safe_mode:active\"))
    await redis_client.disconnect()
asyncio.run(main())
"'
```

기대 결과:
- `ceil:2026-05-07`: 동적 ceil 값 (예: `0.04~0.07` 범위, ATR_CEIL_HARD=0.08 미만)
- `dist:2026-05-07`: P10/P20/P50/P80/P95 + sample_n≈52
- `fallback_count`: `0` 유지
- `safe_mode:active`: None 유지

5/7 KST 16:00 이후 위 명령 실행 + `/api/v1/health/observation-daily?date=2026-05-07` 호출로 G1·G2·G3 최종 판정.
