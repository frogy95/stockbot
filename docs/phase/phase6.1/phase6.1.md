# Phase 6.1: 매매 전략 거래량 시간가중 보정 — 실행 계획

> **Status**: ✅ 완료 (2026-04-13, PR #125)
> **ROADMAP 참조**: `ROADMAP.md` Phase 6.1
> **검토 리포트**:
>
> - `phase6.1-po-review.md` (정프로, PO)
> - `phase6.1-risk-review.md` (최리스크, 리스크관리)
> - `phase6.1-trader-review.md` (김단타, 단타 전문가)
> - `phase6.1-quant-review.md` (박퀀트, 퀀트)

---

## 개요

`momentum_breakout` 전략의 `volume_ratio >= 2.0` 조건이 **"장중 누적 거래량 vs 전일 마감 누적 거래량"을 직접 비교**하여, 장 전반부에는 구조적으로 통과 불가능한 문제를 수정한다.

### 문제 분석

```
[2026-04-13 프로덕션 데이터 — 062040 이수페타시스]
  - 13:17 KST: current_price=169,900 (전일 대비 +10.7%)
  - 돌파 조건: 169,900 > prev_high 157,900 -> 통과 (+7.6%)
  - 체결강도: 141.6 -> 통과 (>= 70)
  - 거래량: vol=1,080,856 / pvol=968,175 = 1.117배 -> 미달 (>= 2.0)
  
  => 가격 +10.7% 돌파 중이지만 거래량 조건 미달로 매매 신호 0건

[근본 원인]
  volume_ratio = snapshot.volume / snapshot.prev_volume
  - snapshot.volume: 당일 09:00~현재 시점까지의 누적 거래량
  - snapshot.prev_volume: 전일 09:00~15:30 전체 누적 거래량
  - "장 절반만 경과한 시점의 누적"과 "전일 전체 누적"을 비교하므로
    동일 거래 속도에서도 volume_ratio는 최대 ~0.5에 불과
  - 전일 대비 2배 속도로 거래되어도 장 절반 시점에 volume_ratio = 1.0
  => 장중에는 구조적으로 2.0 도달 거의 불가능

[수학적 본질 — 박퀀트]
  시간 t에 의존하는 변수 V(t)와 시간 T에 의존하는 상수 V_prev(T)를
  직접 비교하는 "단위 불일치(unit mismatch)" 오류
```

### 해결 아키텍처

```
[옵션 검토 — 전원 합의]

  (a) 현행 유지 (자연 누적 대기) -> 전원 거부
      이유: 단타 시스템이 장 종반에만 동작하는 것은 시스템 존재 의의 부정

  (b) 임계값 하향 (2.0 -> 1.2~1.5) -> 전원 거부
      이유: 수학적으로 동일한 문제. 1.2로 내려도 progress=1.2에서야 통과 (장 마감 후)
      
  (c) 시간가중 보정 -> 전원 권장 (최리스크: 안전장치 3가지 조건부)
      공식: adjusted_ratio = volume / (prev_volume * progress)
      의미: "현 시점까지의 거래량 속도가 전일 평균 속도의 몇 배인가?"

[확정 설계]

  momentum_breakout.py의 거래량 조건 블록을:
  
  (기존)
    volume_ratio = snapshot.volume / snapshot.prev_volume
    if volume_ratio < 2.0: return None
    
  (변경 — 2차 검토 확정안)
    progress = calc_market_progress()  # 장 경과 비율 (0.0 ~ 1.0)
    progress = max(progress, MIN_MARKET_PROGRESS)  # 하한 0.15
    
    # 절대 거래량 하한: 전일의 50% 미만이면 유동성 부족으로 탈락
    if snapshot.volume < snapshot.prev_volume * MIN_VOLUME_FLOOR:
        return None
    
    # 시간가중 보정: "현 시점 기준 마감 예상 거래량 비율"
    adjusted_ratio = snapshot.volume / (snapshot.prev_volume * progress)
    
    # 돌파 강도 연동 임계값
    breakout_pct = (snapshot.current_price - breakout_ref) / breakout_ref * 100
    if breakout_pct >= 5.0:
        volume_threshold = 1.5
    elif breakout_pct >= 3.0:
        volume_threshold = 1.8
    else:
        volume_threshold = 2.0
    
    if adjusted_ratio < volume_threshold: return None
```

---

## 검토팀 확정 파라미터 (2026-04-13)

> 정프로(PO), 최리스크(리스크관리), 김단타(단타), 박퀀트(퀀트) — 4명 검토 완료

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 1 | volume_ratio 임계값 | 2.0 (하드코딩) | **돌파 강도 연동** (2차 검토) | 5%+ 돌파: `>=1.5`, 3~5% 돌파: `>=1.8`, <3% 돌파: `>=2.0` — 강한 돌파는 거래량 요건 완화, 약한 돌파는 기존 엄격 유지 |
| 2 | 보정 공식 | 없음 | **선형: V(t) / (V_prev * progress)** | 전원 합의. 박퀀트: 유일하게 수학적으로 올바른 정규화. U자형은 파라미터 과적합 |
| 3 | progress 계산 | 없음 | **elapsed_min / 390** | 09:00~15:30 = 390분. 결정론적 계산, 파라미터 추가 없음 |
| 4 | MIN_MARKET_PROGRESS | 없음 | **0.15** | 전원 합의. 09:58 이전 극단적 비율 방지. no_signal(09:30)과 이중 방어 |
| 5 | MIN_VOLUME_FLOOR | 없음 | **~~0.3~~ 0.5** (prev_volume * 0.5) | **2차 검토 상향**: 최리스크 필수 안전장치 — 전일 50% 미만 거래량은 유동성 부족, 시간보정과 무관 탈락 |
| 6 | confidence volume_score | `volume_ratio / 5.0` | **adjusted_ratio / 5.0** | 박퀀트: 보정된 비율로 시간 일관성 확보 |
| 7 | 장 시간 상수 | 없음 | **MARKET_MINUTES = 390** | KRX 정규장 09:00~15:30 기준 |
| 8 | 장 시작 시각 | 없음 | **MARKET_OPEN = 09:00** | settings.MARKET_TIMEZONE 활용 |

---

## 2차 전문가 검토 결과 (2026-04-13)

> 1차 검토 후 사용자 피드백 + 실 데이터(062040 이수페타시스) 역산을 반영하여 전문가 4명 2차 검토 수행.

### 변경 사항 요약

| 항목 | 1차 확정 | 2차 확정 | 변경 근거 |
|------|---------|---------|----------|
| volume_ratio 임계값 | 2.0 고정 | **돌파 강도 연동** (5%+: 1.5, 3~5%: 1.8, <3%: 2.0) | 강한 돌파(+5%+)는 시장 확신이 높으므로 거래량 요건 완화. 약한 돌파는 기존 엄격 유지 |
| MIN_VOLUME_FLOOR | 0.3 | **0.5** | 최리스크: 유동성 부족 안전장치 강화. 전일 대비 절반 미만 거래량이면 슬리피지 위험 |
| 범위 확장 | 전략 수정만 | **+ 5분봉 거래량 수집 파이프라인 선행 구축** | Phase 7.1 데이터 의존성 해소를 위해 이 Phase에서 축적 시작 |

### 062040 이수페타시스 역산 검증 (2026-04-13 13:17 KST)

```
입력 데이터:
  current_price = 169,900 (전일 대비 +10.7%)
  prev_high = 157,900
  volume = 1,080,856
  prev_volume = 968,175
  장 경과 시간: 13:17 → elapsed = 257분 → progress = 257/390 = 0.659

역산:
  breakout_pct = (169,900 - 157,900) / 157,900 * 100 = +7.6%
  adjusted_ratio = 1,080,856 / (968,175 * 0.659) = 1.694
  MIN_VOLUME_FLOOR: 1,080,856 / 968,175 = 1.116 >= 0.5 -> 통과

수정안 판정:
  breakout_pct = 7.6% >= 5.0% -> volume_threshold = 1.5
  adjusted_ratio = 1.694 >= 1.5 -> 통과!
  -> 매매 신호 생성 가능 (1차 확정안 2.0에서는 1.694 < 2.0으로 미달)
```

---

## 후속 Phase 데이터 축적을 위한 선행 구축

### 배경

Phase 7.1에서 "5분 단위 거래량 가속도 지표"를 구현하려면 최소 20거래일의 5분봉 거래량 데이터가 필요하다. Phase 7.1 착수 시점에 데이터가 없으면 추가 20거래일(약 1개월)을 기다려야 한다. 이를 방지하기 위해 **이 Phase에서 수집 파이프라인을 미리 구축하고 축적을 시작**한다.

### 5분봉 거래량 집계 설계

**Redis Key 스키마**:
```
vol5m:{stock_code}:{date}:{slot_index}
```
- `stock_code`: 종목 코드 (예: `062040`)
- `date`: YYYYMMDD (예: `20260413`)
- `slot_index`: 5분봉 슬롯 인덱스 (0~77, 09:00~15:30 = 390분 / 5분 = 78슬롯)

**값**: JSON `{"buy_vol": int, "sell_vol": int, "total_vol": int, "trade_count": int}`

**적재 주기**: WS 체결 데이터(`H0STCNT0`) 수신 시 즉시 해당 슬롯에 INCRBY로 누적

**TTL**: 30일 (약 22거래일분). Phase 7.1 착수 시점에 충분한 데이터 확보 후 DB 이관 검토

**슬롯 계산 함수**:
```python
def calc_5min_slot(hour: int, minute: int) -> int:
    """09:00 기준 5분봉 슬롯 인덱스 반환 (0~77)."""
    elapsed = (hour * 60 + minute) - (9 * 60)
    return max(0, min(77, elapsed // 5))
```

### Phase 7.1과의 연결

- Phase 7.1 착수 시점에 `vol5m:*` 키로 축적된 데이터를 읽어 거래량 가속도 지표 계산
- 사용은 Phase 7.1부터. 이 Phase에서는 **축적만 수행**, 전략 로직에서 참조하지 않음
- 축적 미완 상태에서 Phase 7.1 착수 지시가 오면 AI가 경고 발생

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| ✅ 1 | 거래량 시간가중 보정 구현 | progress 계산 + 보정 공식 + 안전장치 + 테스트 | 없음 |

단일 Sprint. 코드 변경 범위가 파일 2~3개, 파라미터 확정 완료.

---

## Sprint 1 상세 — 거래량 시간가중 보정 구현 ✅ 완료 (PR #125, 2026-04-13)

### 백엔드

| 파일 | 작업 내용 |
|------|----------|
| `backend/modules/trading/strategies/momentum_breakout.py` | (1) `calc_market_progress()` 함수 추가 (2) MIN_MARKET_PROGRESS=0.15, MIN_VOLUME_FLOOR=0.5 상수 (3) 거래량 조건 블록 교체: 절대하한 체크 + 시간가중 보정 + 돌파 강도 연동 임계값 (4) volume_score도 adjusted_ratio 사용 |
| `backend/modules/trading/strategies/__init__.py` | 변경 불필요 (import 변경 없음) |
| `backend/modules/collector/volume_aggregator.py` | **신규**: 5분봉 거래량 집계 모듈. calc_5min_slot(), aggregate_execution() 함수. Redis INCRBY로 슬롯별 누적 |
| `backend/modules/collector/scheduler.py` | _process_realtime_data()에서 체결 데이터 수신 시 volume_aggregator.aggregate_execution() 호출 추가 |
| `backend/tests/test_momentum_breakout.py` | (1) 기존 테스트 volume_ratio 케이스 수정 (보정 반영) (2) 신규: 시간대별 보정 정확도 테스트 (09:30/11:00/14:00) (3) 신규: min_progress 하한 테스트 (4) 신규: 절대 거래량 하한 테스트 (5) 신규: 장 시간 외 호출 시 안전 동작 테스트 (6) 신규: 돌파 강도별 임계값 테스트 |
| `backend/tests/test_volume_aggregator.py` | **신규**: 5분봉 집계 단위 테스트 (슬롯 계산, Redis 적재, TTL 검증) |

### 프론트엔드

변경 없음. (전략 내부 로직 변경이므로 API 응답 형식 불변)

### 재사용 자산

| 기존 모듈 | 재사용 방식 |
|----------|-----------|
| `core/config.py` settings.MARKET_TIMEZONE | KST 시간 계산에 사용 |
| `datetime.now(ZoneInfo(...))` 패턴 | 기존 코드베이스 전역에서 사용 중인 KST 시간 패턴 |
| 2차 스크리닝 `_is_no_signal_period()` | 동일한 장 시간 개념 참조 (단, 별도 구현하여 모듈 결합도 증가 방지) |

### 구현 상세

```python
# momentum_breakout.py 변경 영역

from datetime import datetime, time
from zoneinfo import ZoneInfo

# 장 시간 상수
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(15, 30)
MARKET_MINUTES = 390  # 09:00~15:30 = 6시간 30분

# 안전장치 상수
MIN_MARKET_PROGRESS = 0.15   # 장 시작 ~58분(09:58) 전 극단적 비율 방지
MIN_VOLUME_FLOOR = 0.5       # 전일 거래량의 50% 미만이면 유동성 부족 탈락 (2차 검토 상향)


def calc_market_progress(timezone: str = "Asia/Seoul") -> float:
    """현재 시각 기준 장 경과 비율 (0.0 ~ 1.0).
    
    장 시간 외에는 1.0 반환 (보정 없이 원래 비율 그대로 비교).
    """
    now = datetime.now(ZoneInfo(timezone))
    current = now.time()
    
    if current < MARKET_OPEN:
        return MIN_MARKET_PROGRESS
    if current >= MARKET_CLOSE:
        return 1.0
    
    elapsed = (now.hour * 60 + now.minute) - (MARKET_OPEN.hour * 60 + MARKET_OPEN.minute)
    return max(elapsed / MARKET_MINUTES, MIN_MARKET_PROGRESS)
```

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 대응 |
|---|------|--------|------|
| 1 | 선형 보정은 장 중반(11~13시)에 ~10~20% 보수적 | 낮음 | 보수적 방향이므로 리스크 관리에 유리. Phase 9에서 U자형 비선형 검토 |
| 2 | 거래량 후반 집중 종목 감지 불가 | 낮음 | 14:30 이후 진입 차단(is_entry_blocked)으로 영향 없음 |
| 3 | 모니터링 필요 | 중간 | 최소 3~5거래일 로그 확인: 시간대별 adjusted_ratio 분포, 통과율, false positive |
| 4 | 5분봉 수집 Redis 메모리 | 낮음 | 30종목 x 78슬롯 x 30일 = ~70K 키, 키당 ~100B = ~7MB. Railway Redis 용량 내 |
| 5 | 장기 개선: 거래량 가속도 지표 | Phase 7.1 | 5분봉 데이터 20거래일 축적 후 착수 (이 Phase에서 축적 시작) |
| 6 | 장기 개선: 동시간대 Z-score | Phase 8 | Phase 7.1에서 시간대별 DB 구축 후 축적 필요 |
| 7 | 장기 개선: U자형 비선형 보정 | Phase 9+ | 3~6개월 운영 데이터 필요 (과적합 방지) |
| 8 | [Medium] generate_signal에서 effective_progress 이중 적용 | 낮음 | `calc_market_progress()`가 이미 `max(raw, MIN_MARKET_PROGRESS)` 보장하므로 88행 `effective_progress = max(progress, MIN_MARKET_PROGRESS)` 중복. 무해하지만 코드 명확성 저하. Sprint 2+에서 개선 권장 |
| 9 | [Medium] `get_first_seen_date`가 매 호출마다 Redis 전체 키 SCAN | 낮음 | 디버깅 엔드포인트(Phase 7.1용)이므로 호출 빈도 낮음. 키 수 최대 70K. 운영에 미치는 영향 미미. 하지만 Phase 7.1 정식 활용 전 캐시 또는 별도 추적 키로 개선 권장 |

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| 시간가중 보정 구현 | `calc_market_progress()` + 보정 공식 적용 | ✅ 완료 |
| 돌파 강도 연동 임계값 | 5%+/3~5%/<3% 3단계 volume_threshold | ✅ 완료 |
| 안전장치 구현 | MIN_MARKET_PROGRESS=0.15 + MIN_VOLUME_FLOOR=0.5 | ✅ 완료 |
| 5분봉 거래량 수집 | volume_aggregator 모듈 + Redis 적재 동작 확인 | ✅ 완료 (로컬 검증) |
| 단위 테스트 | 기존 케이스 수정 + 시간대별 보정 + 돌파 강도별 + 5분봉 집계 = 10건 이상 | ✅ 완료 (38건 추가, 798 passed) |
| 프로덕션 배포 | Railway 배포 + 장중 1건 이상 신호 생성 확인 | ⬜ develop→main 머지 후 |
| 모니터링 | 3거래일 로그 확인 (adjusted_ratio 분포 + 5분봉 키 축적 확인) | ⬜ 배포 후 3거래일 |
