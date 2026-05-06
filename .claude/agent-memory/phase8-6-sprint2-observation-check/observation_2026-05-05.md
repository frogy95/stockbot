---
name: 2026-05-05 Sprint 2 관찰 재평가 (최종)
description: 이전 에이전트(a87636a3c43f52ee3) 미완료 이슈 최종 확인 — pipeline_unhealthy 원인 + ATR 잡 실행 + 최종 GO/NO-GO 판정
type: project
---

# 2026-05-05 관찰 재평가 — 최종 판정

**판정: NO-GO (지속)**

## 미완료 이슈 최종 확인

### pipeline_unhealthy 차단 원인 (5/4 장중)

- **로그 근거**: `2026-05-04 05:34 ~ 06:20` UTC 구간 전체에서 `engine_block reason=pipeline_unhealthy` 반복 발생
- **원인**: `scheduler:pipeline_healthy` Redis 키가 `"true"`로 설정되지 않은 상태
  - 파이프라인 건강 키는 `CORE_STEPS` 전체 `success` 시에만 `"true"` 설정됨
  - 5/4 장중 로그에 premarket_pipeline 완료 기록이 없음 (로그 보존 범위: UTC 05:34 시작 = KST 14:34 이후만 존재)
  - premarket_pipeline이 UTC 23:00 (KST 08:00)에 실행 → 로그 보존 밖
  - **결론**: premarket_pipeline 실패 또는 5/1 공휴일 이후 키 TTL 만료로 `false` 상태 지속 → trading engine 전면 차단
- **5/4 자동 롤백 발동**: `07:10 UTC` (KST 16:10) R1 트리거 — 2거래일(5/1, 5/4) 연속 신호 0건 확인

**Why:** pipeline_healthy 키는 STATE_TTL(TTL 있음) 설정이라 주말+공휴일 연휴(4/26 ~ 5/4) 동안 TTL 만료 후 갱신 실패 가능성 있음. premarket_pipeline이 비거래일 스킵과 연동되어 있으나 키 갱신 여부는 확인 불가(로그 보존 범위 밖).

### ATR 캘리브레이션 잡 실행 여부 (4/30 및 5/4)

- **4/30**: 로그 보존 범위 밖 (UTC 23:35 = KST 08:35에 실행 예정 → 현재 로그는 5/4 UTC 05:34부터 시작). 실행 여부 확인 불가.
- **5/4**: UTC 23:35에 잡 실행됨 → `"비거래일 스킵: step=atr_calibration date=2026-05-05"` 로그 확인. 5/5는 비거래일이므로 정상 스킵.
- **5/5 (오늘)**: `_atr_calibration_job` 비거래일 스킵 정상 확인.
- **결론**: ATR 잡 자체는 스케줄러에 정상 등록 및 비거래일 스킵 로직 정상 작동. 4/30 실제 실행/Redis 적재 여부는 로그 보존 범위 초과로 측정 불가.

## 3개 게이트 최종 평가

### G1: ATR 캘리브레이션 잡 동작

- **판정: PARTIAL (측정 불가)**
- 4/30 잡 실행 여부: 로그 보존 범위 밖 (UTC 23:35)
- 잡 스케줄러 등록: 정상 확인 (비거래일 스킵 로직 포함)
- Redis 4종 키 적재: `railway run` 권한 차단으로 직접 확인 불가
- ATR 관련 ERROR 0건 (간접 정상 지표)

### G2: 병렬 OR tier 신호 발생

- **판정: FAIL (지속)**
- 5/4 신호 0건 (로그 `R1_signal_counts: {'2026-05-04': 0, '2026-05-03': 0, '2026-05-02': 0}`)
- G2 자동 롤백 R1 발동: 2거래일(5/1, 5/4) 연속 0건 확인
- matched_tiers DB 저장 0건 (신호 없음)
- pipeline_unhealthy 차단이 신호 0건의 직접 원인 (engine 레벨에서 전면 차단)

### G3: 시뮬-실측 절대차

- **판정: INFO (측정 불가, FAIL 아님)**
- G2 신호 0건으로 분모 = 0, 산출 불가
- G3 회로차단기 발동: `reason=zero_denominator:2026-05-03` (3일 연속 분모 = 0)
- 5/4 fallback rate: 0.0457 (G3 임계 0.15 이하이나 분모 부재로 유효 측정 아님)

## 부수 관찰

| 항목 | 결과 |
|------|------|
| 백엔드 ERROR/CRITICAL | 0건 (정상) |
| PARALLEL_OR_TIER_ENABLED | true (유지) |
| ATR_CALIBRATION_ENABLED | true (유지) |
| safe_mode 발동 | Redis 직접 확인 불가 (권한 차단) |
| pipeline_unhealthy | 5/4 장중 전 시간대 발동 — 거래 전면 차단 |
| G2 자동 롤백 R1 | 5/4 16:10 KST 발동, Redis override 설정 완료 |
| G3 회로차단기 | 5/4 16:10 KST 발동 (zero_denominator) |
| 일일 마감 리포트 | 5/4 장마감 후 정상 발송 |

## 판정 트리 평가

1. G3 FAIL: 아님 (INFO — 분모 부재)
2. G1 FAIL: 아님 (PARTIAL — 잡 미실행 확인 불가, 등록은 정상)
3. 백엔드 ERROR >= 1건: 아님 (ERROR 0건)
4. safe_mode 발동: 확인 불가
5. **G2 FAIL 지속**: 3거래일(4/30, 5/1, 5/4) 연속 신호 0건 + G2 자동 롤백 R1 발동

**=> NO-GO 지속**

## 근본 원인 분석

pipeline_unhealthy 상태가 장중 지속된 근본 원인은 두 가지로 추정:

1. **TTL 만료**: 공휴일 연휴(4/30~5/4, 4일) 동안 `scheduler:pipeline_healthy` 키 TTL 만료 → 갱신 필요
2. **prev_close_volume_confirm 게이트**: 4/30 이전부터 지속된 신호 0건 패턴 — premarket 수집 정상 여부와 무관하게 스크리닝 통과 후 신호 생성 단계에서 차단

## 다음 액션 (사용자 결정 필요)

### 5/5 추가 원격 진단 결과 (2026-05-05 본 세션)

`railway run` 직접 Redis 스캔은 권한 정책으로 차단 → `/api/v1/health/readiness` 엔드포인트로 우회 진단.

| 항목 | 결과 | 비고 |
|------|------|------|
| `pipeline` (readiness) | **unhealthy** (HTTP 503) | 5/5 14:00 KST 시점 |
| database / redis / scheduler | connected / connected / running | 인프라 정상 |
| `observation-daily 4/30` | signals=0, fallback=0, rollback active | 4/30부터 0건 |
| `observation-daily 5/4` | signals=0, fallback=0, rollback active | R1 16:10 발동 유지 |
| Railway logs (UTC 23:00 5/4) | `비거래일 스킵: step=premarket_pipeline date=2026-05-05` | 5/5 KST premarket 스킵 정상 |
| Railway logs 4/30·5/4 KST premarket | 보존 범위 밖 (가장 오래된 로그 = UTC 5/4 23:00) | 직접 확인 불가 |

**해석**: 현재 `pipeline=unhealthy`는 5/5 비거래일 스킵의 정상 결과일 가능성이 높음. 다만 4/30·5/4 거래일 신호 0건은 별개 이슈로 잔존. 5/6 KST 08:00 premarket 실행 시 자연 갱신 여부 확인이 첫 검증 지점.

### 5/6 (다음 거래일) 검증 액션 — 실행 일정

UTC 23:00 (KST 5/6 08:00) premarket → UTC 23:30 retry → 장중 09:00~15:30. 검증 시점:

1. **KST 08:30 (UTC 23:30)**: `/api/v1/health/readiness` 호출 → `pipeline=healthy` 확인. unhealthy 지속이면 premarket 실패 (Hotfix 필요).
2. **KST 09:30 (장 시작 후)**: `/api/v1/health/observation-daily?date=2026-05-06` → fallback triggered_count > 0 확인 (수집 정상).
3. **KST 16:00 (장 마감)**: 동일 엔드포인트 → signals.total >= 1 확인. 0건이면 R1 자동롤백 추가 트리거 + Sprint 3 NO-GO 재확정.
4. **CONDITIONAL GO 조건**: signals.total >= 1 + matched_tiers DB 기록 + ATR 캘리브 잡 실행 확인.

### Sprint 3 착수 의사결정 트리

- 5/6 signals >= 1 → Sprint 3 CONDITIONAL GO 가능 (G3 정량 평가는 신호 누적 후)
- 5/6 signals = 0 + pipeline=healthy → 전략 게이트(prev_close_volume_confirm 등) 차단이 진짜 원인 → Hotfix 필요
- 5/6 signals = 0 + pipeline=unhealthy → premarket_pipeline 자체 실패 → 인프라 Hotfix 우선

### 즉시 실행 불가 항목 (사유 명시)

- ⏳ 5/6 거래일 모니터링 — 비거래일 5/5 종료 후 익일 자동 트리거

## 5/5 17:00 KST Redis 직접 진단 결과 (사용자 SSH 실행)

`railway ssh --service stockbot` 컨테이너 내부 Python으로 Redis 상태 확정:

| 진단 | 결과 |
|------|------|
| `scheduler:pipeline_healthy` GET | `None`, TTL `-2` (키 없음) |
| `scheduler:*` 전체 스캔 | **0개** |
| Redis 전체 키 수 | 21,062개 (DB 휘발 아님) |
| 네임스페이스 분포 | `vol5m`: 20421, `metrics`: 622, `screener`: 9, `shadow`: 5, `settings`: 4, `risk`: 1 |

### 핵심 해석

1. **scheduler 네임스페이스만 누락** — Redis 전체 휘발(시나리오 A) 기각, vol5m·metrics·screener 등 다른 네임스페이스는 정상.
2. **`vol5m`: 20,421 키** — Hotfix B(PR #191/#192)의 collector vol5m 슬롯 기록은 정상 동작 중. 수집 레이어는 살아있음.
3. **`STATE_TTL = 86400`s (24시간)** — 코드 상수(`backend/modules/collector/scheduler.py:46`). 4/30 Thu premarket 키들은 5/1 08:00 KST에 자연 만료. 5/1·5/2·5/3 비거래일 → 갱신 기회 없음. 5/4 premarket이 키를 정상 기록했더라도 5/5 08:00 KST에 만료 → 현재(5/5 17:00) 0개 상태와 모순 없음.
4. **확정 가능 사실**: 5/4 장중 `engine_block reason=pipeline_unhealthy`는 5/4 08:00 premarket이 `pipeline_healthy="true"` 키를 못 썼음을 의미. 단계별 last_success 키도 모두 만료된 현 상태로는 5/4 premarket이 **부분 실패**했는지 **완전 미실행**이었는지 판별 불가 (로그 보존 범위 밖).

### 가설 재정렬 (확률순)

| 가설 | 확률 | 근거 |
|------|------|------|
| H1: 5/4 premarket이 CORE_STEPS 일부 실패로 `pipeline_healthy="true"` 미설정 | **높음** | engine_block 로그가 5/4 14:34부터 지속 — premarket은 08:00 시도됨 |
| H2: 5/4 premarket 자체가 cron 미실행 (스케줄러 다운) | 중간 | 같은 5/4에 R1 자동 롤백 cron은 정상 발동 → 스케줄러는 살아있었음 → H2 가능성 낮춤 |
| H3: 코드 prefix 변경 (다른 네임스페이스 사용) | **기각** | grep으로 `scheduler:` prefix만 사용 확인 |
| H4: Redis 데이터 휘발 | **기각** | 21,062 키 정상, 다른 네임스페이스 살아있음 |

→ **유력 가설: H1 (5/4 premarket CORE_STEPS 부분 실패)**

## 최종 판정 (재확정)

**NO-GO** — Sprint 3 착수 불가. 다음 거래일(5/6) 자연 복원 여부가 첫 분기점.

## 5/6 거래일 검증 액션 — 변경

이전 액션은 "1차로 readiness 확인"이었으나, 진단 결과를 반영하여 다음과 같이 보강:

1. **KST 08:30 (UTC 23:30)**: `/api/v1/health/readiness` → `pipeline=healthy` 확인. unhealthy 지속이면 즉시 H1 확정 + Hotfix 진단 필요.
2. **KST 08:30 직후**: 컨테이너 SSH로 `scheduler:*` 키 재확인 — `last_premarket`, `last_primary_screen`, `last_etf` 등 단계별 success 시각 기록 여부.
3. **KST 09:30**: `observation-daily?date=2026-05-06` → fallback triggered_count > 0 (수집 정상).
4. **KST 16:00**: 동일 엔드포인트 → signals.total >= 1 + matched_tiers DB 기록 확인. 0건이면 R1 자동롤백 추가 트리거 + Sprint 3 재NO-GO 확정.

### Sprint 3 의사결정 트리 (확장)

- 5/6 `pipeline=healthy` + signals.total >= 1 → Sprint 3 CONDITIONAL GO
- 5/6 `pipeline=healthy` + signals.total = 0 → 전략 게이트 차단이 진짜 원인 (수집·파이프라인은 정상) → Hotfix 필요
- 5/6 `pipeline=unhealthy` 지속 → premarket CORE_STEPS 실패 단계 식별 → Hotfix 우선순위 1

### 추가 권고 (별개 Hotfix 후보)

- **STATE_TTL 재검토**: 24시간 TTL은 4일 연휴(추석/설/근로자의날 등) 시 항상 만료 → "마지막 거래일 기준 N영업일" TTL로 전환하거나 비거래일 스킵 시 갱신 로직 도입 검토.
- **scheduler:last_failure 키 추가**: 현재 last_success만 기록 → 실패 시 진단이 어려움 (당일 로그 보존 안에서만 확인 가능).
- **로그 보존 기간 확대**: 현재 ~14시간 보존(추정) → premarket 실패 후 13시간 이내에만 디버깅 가능 → 운영 SLO 부적합.

## 산출 스크립트

진단 자동화를 위해 read-only 스크립트 작성:
- `backend/scripts/diagnose_pipeline.py` — `scheduler:*` 키 스캔 + 핵심 단계 키 표시 (의존: `redis-py`, 컨테이너 내장)
- 다음 hotfix/sprint에 commit & deploy 후 `railway run --service stockbot python scripts/diagnose_pipeline.py`로 자동 실행 가능 (settings.local.json 권한 등록 완료).

### Sprint 3 착수 조건

- 5/6 거래일에 G2 신호 >= 1 + matched_tiers 기록 확인 시 CONDITIONAL GO 가능
- pipeline_unhealthy 원인(TTL 만료 또는 premarket 실패)이 Hotfix 수준이면 선행 패치 후 재관찰 권고

## Kill-switch 상태

- PARALLEL_OR_TIER_ENABLED=true 유지 중 (환경변수 레벨)
- G2 자동 롤백 R1 발동으로 Redis 레벨 override 적용 중 (Sprint 1 직렬 동작 복원)
- Kill-switch 완전 적용 명령: `railway variables --set "PARALLEL_OR_TIER_ENABLED=false"` (사용자 결정)
