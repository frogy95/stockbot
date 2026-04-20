# Sprint 1: 장중 OHLC 파싱 + 갭 분기 수정 (Phase 8)

**Goal:** H0STCNT0 WebSocket 메시지에서 장중 시가/고가/저가(OHLC)를 파싱·캐싱하여 `momentum_breakout` 전략의 갭 3%+ 분기에서 자기돌파 버그를 제거하고 매매 신호 생성을 복구한다.

**Architecture:** KIS WebSocket 파서(kis_realtime)의 `EXECUTION_FIELD_MAP`에 `open_price(7) / high(8) / low(9)` 3필드를 추가하고, WS 메시지 수신 경로(scheduler → Redis `realtime:{code}:execution` JSON)와 조회 경로(realtime_screener → candidate dict)를 일관되게 확장한다. `signal_generator._build_snapshot()`은 Redis 실시간 값을 우선 사용하되 미수신 시 기존 `prev_close` 폴백을 유지하고, `momentum_breakout` 갭 분기의 `breakout_ref`를 `snapshot.high`(자기돌파) → `snapshot.open_price`(시가 돌파)로 교정한다.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Redis 7 · pytest / pytest-asyncio · APScheduler

**Sprint 기간:** 2026-04-20 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 7.0.1 Sprint 1 (통과, PR #138) — KIS LIVE WS 연결 복구 완료
**브랜치명:** `phase8-sprint1`

---

## 제외 범위

- **다층 진입 조건 (prev_close / prev_high 분기)** — Phase 8 Sprint 2 범위
- **position_sizer 반 포지션 / daily_trade_count 리스크 게이트** — Phase 8 Sprint 2 범위
- **시스템 관리 UI / 성과 분석** — Phase 8 Sprint 3·4 범위
- **5분봉 가속도 / Z-score / VWAP 지표 통합** — Phase 9 범위
- **2차 스크리닝 N=1 상대 백분위 보정** — Phase 10.1 이관
- **당일 고가 갱신 진입** — Phase 10.1 이관

> Sprint 1은 **데이터 파이프라인 수정에만 집중**하고, 전략 로직 변경은 갭 분기 `breakout_ref` 1줄 교정으로 제한한다. 리스크 게이트 및 다층 진입은 Sprint 2에서 추가한다.

---

## 실행 플랜

의존성 그래프: Task 1(파서) → Task 2(Redis 캐싱) → Task 3(screener candidate 확장) → Task 4(snapshot 조립) → Task 5(갭 분기) → Task 6(통합 검증).
Task 1~5는 파일 소유권이 명확히 분리되어 있으나, Redis JSON 구조 변경이 상류(파서)에서 하류(snapshot)로 흐르므로 **순차 실행**한다.

### Phase 1 (순차 — 데이터 레이어 확장)

| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | `EXECUTION_FIELD_MAP`/`ExecutionData`/`parse_execution` OHLC 3필드 확장 | 백엔드 | — |
| Task 2 | `scheduler._process_realtime_data()` Redis 캐싱 JSON 3필드 추가 | 백엔드 | — |
| Task 3 | `realtime_screener.screen()` candidate dict에 `open_price/high/low` 포함 | 백엔드 | — |

### Phase 2 (순차 — 전략 레이어 연결)

| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | `signal_generator._build_snapshot()` Redis 실시간 값 우선 사용 + 폴백 유지 | 백엔드 | — |
| Task 5 | `momentum_breakout.generate_signal()` 갭 3%+ 분기 `breakout_ref = snapshot.open_price` 교정 | 백엔드 | `systematic-debugging` |

### Phase 3 (통합 검증)

| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | 전체 pytest 회귀 + 수동 검증 가이드 (Redis 필드 존재 확인 + 2거래일 관찰 체크리스트) | 전체 | — |

> **팀 실행**: 본 Sprint는 모든 Task가 백엔드 단일 파일 체인으로 엮여 순차 실행이 자연스럽다. 병렬 팀 실행 대상 아님.

---

### Task 1: KIS 체결 파서 OHLC 3필드 확장

**skill:** — (단일 파일 수정, 기존 패턴 확장)

**Files:**
- Modify: `backend/modules/collector/sources/kis_realtime.py` (`EXECUTION_FIELD_MAP`, `ExecutionData`, `parse_execution`)
- Modify: `backend/tests/test_kis_realtime.py` (헬퍼 `_make_execution_body` 확장 + 신규 테스트 케이스)

**Step 1: 테스트 확장**
- `backend/tests/test_kis_realtime.py`의 `_make_execution_body()` 시그니처에 `open_price: int = 69500, high: int = 70100, low: int = 69000` 파라미터 추가
- 헬퍼 내부에서 `fields[7] = str(open_price)`, `fields[8] = str(high)`, `fields[9] = str(low)` 할당
- 신규 테스트: `test_parse_execution_extracts_ohlc` — 헬퍼로 본문 생성 후 `parse_execution()` 반환의 `open_price / high / low` 값 검증
- 신규 테스트: `test_parse_execution_handles_missing_ohlc_fields` — 필드 10개 미만 body에 대해 기존과 동일하게 `None` 반환 확인
- 검증: `docker compose exec backend pytest tests/test_kis_realtime.py -v`
- 예상: 새 테스트 FAIL (파서 미확장), 기존 테스트 대부분 PASS

**Step 2: 파서 확장**
- `EXECUTION_FIELD_MAP`에 `"open_price": 7, "high": 8, "low": 9` 3키 추가 (기존 키 순서 유지, 주석으로 "장중 OHLC — STCK_OPRC / STCK_HGPR / STCK_LWPR" 명시)
- `ExecutionData` dataclass에 `open_price: int`, `high: int`, `low: int` 3필드 추가 (기존 필드 뒤에 배치)
- `parse_execution()` 내부 `ExecutionData(...)` 생성자 호출에 3필드 매핑 추가 (`int(fields[fm["open_price"]])` 등). `max_index` 자동으로 9 이상 증가 — 별도 수정 불필요
- 검증: `docker compose exec backend pytest tests/test_kis_realtime.py -v`
- 예상: 전 테스트 PASS

**Step 3: 커밋**
```
git add backend/modules/collector/sources/kis_realtime.py backend/tests/test_kis_realtime.py
git commit -m "feat(phase8-sprint1): task1 — H0STCNT0 파서에 open_price/high/low 3필드 추가"
```

**완료 기준:**
- ⬜ `test_parse_execution_extracts_ohlc` PASS
- ⬜ 기존 테스트 회귀 없음
- ⬜ `ExecutionData`에 open_price/high/low 3필드 추가

---

### Task 2: Scheduler WS 메시지 Redis 캐싱 3필드 추가

**skill:** — (기존 JSON 구조 확장, 단일 함수 수정)

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (`_process_realtime_data()` 내 `realtime:{code}:execution` JSON 구조)
- Modify/Create: `backend/tests/test_scheduler.py` 또는 `backend/tests/test_scheduler_vol5m.py` 중 `_process_realtime_data` 경로를 다루는 쪽 (없다면 `test_scheduler_redis_state.py` 확장)

**Step 1: 현황 확인**
- `grep -n "realtime:.*:execution" backend/modules/collector/scheduler.py`로 Redis 캐싱 블록 위치 확인 (현재 ~1141줄)
- 현재 JSON 키: `stock_code, time, price, volume, acml_volume, change_rate, trade_strength, sell_or_buy`
- 확장 필드: `open_price, high, low`

**Step 2: 테스트 작성**
- 기존 scheduler 테스트 패턴(FakeRedis 또는 AsyncMock redis)을 재사용
- 신규 테스트: `test_process_realtime_data_caches_ohlc` — ExecutionData(open_price=100, high=110, low=95)를 모사하도록 parse_execution을 patch하거나 raw body를 주입. 이후 `redis.set_json` 호출 인자(또는 FakeRedis store)에서 "open_price": 100, "high": 110, "low": 95 확인
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v -k realtime`
- 예상: 신규 테스트 FAIL

**Step 3: 캐싱 로직 확장**
- `scheduler.py` `_process_realtime_data()` 내 `realtime:{execution.stock_code}:execution` 설정 dict에 `"open_price": execution.open_price, "high": execution.high, "low": execution.low` 3키 추가 (기존 키 뒤, JSON 직렬화 전)
- 캐싱 TTL / set 방식은 기존 그대로 유지
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v -k realtime`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/collector/scheduler.py backend/tests/test_scheduler.py
git commit -m "feat(phase8-sprint1): task2 — realtime:{code}:execution Redis 캐시에 OHLC 3필드 추가"
```

**완료 기준:**
- ⬜ 신규 scheduler 테스트 PASS
- ⬜ 기존 scheduler 테스트 회귀 없음
- ⬜ Redis JSON 구조에 open_price/high/low 3키 추가

---

### Task 3: Realtime Screener candidate dict OHLC 전파

**skill:** — (candidate dict 확장, 2차 스크리닝 2단계 합류 지점 모두 수정)

**Files:**
- Modify: `backend/modules/screening/realtime_screener.py` (`screen()` 내 `passed_candidates.append({...})` + `factor_candidates.append({...})` 두 블록)
- Modify: `backend/tests/test_realtime_screener.py`

**Step 1: 현황 확인**
- `screen()` 내 `passed_candidates.append({...})` 블록 (≈102~114줄): `execution.get("price", 0)` 계열 필드 매핑. 여기서 `execution.get("open_price", 0)`, `execution.get("high", 0)`, `execution.get("low", 0)` 3키 추가
- `factor_candidates.append({...})` 블록 (≈165~191줄): snapshot 조립용 원시 필드에 `"open_price": candidate["open_price"]` 등 3키 전파
- Redis 미수신 예전 데이터 호환: `.get("open_price", 0)` 기본값 0 유지

**Step 2: 테스트 확장**
- 기존 `test_realtime_screener.py`에서 FakeRedis/AsyncMock Redis 응답 dict에 `open_price/high/low` 추가
- 신규 테스트: `test_screen_propagates_ohlc_to_candidate` — mock Redis에 3필드 포함한 execution JSON 반환 → `screen()` 결과 candidate에 `open_price/high/low`가 전달되는지 확인
- 신규 테스트: `test_screen_handles_missing_ohlc_fallback_to_zero` — mock execution에 OHLC 키 없을 때 candidate에 0 기본값이 설정되는지 확인 (과거 Redis 호환)
- 검증: `docker compose exec backend pytest tests/test_realtime_screener.py -v`
- 예상: 신규 테스트 FAIL

**Step 3: candidate dict 확장**
- `passed_candidates.append({...})`에 3키 추가 (execution 원시 데이터에서 `.get` 기본값 0)
- `factor_candidates.append({...})`에 3키 전파 (candidate에서 `.get("open_price", 0)` 등)
- 검증: `docker compose exec backend pytest tests/test_realtime_screener.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/screening/realtime_screener.py backend/tests/test_realtime_screener.py
git commit -m "feat(phase8-sprint1): task3 — realtime_screener candidate에 open_price/high/low 전파"
```

**완료 기준:**
- ⬜ candidate dict 두 블록 모두에 3필드 포함
- ⬜ OHLC 미수신 시 0 폴백 유지 (기존 Redis 호환)
- ⬜ 관련 테스트 PASS

---

### Task 4: SignalGenerator snapshot Redis 실시간 값 우선 사용

**skill:** — (기존 `_build_snapshot` 폴백 정책 교정)

**Files:**
- Modify: `backend/modules/trading/signal_generator.py` (`_build_snapshot()` 137~143줄 블록)
- Modify: `backend/tests/test_signal_generator.py`

**Step 1: 현재 동작 확인**
- 현재 `_build_snapshot()` 137~142줄:
  - `open_price = candidate.get("open_price") or prev_close or current_price`
  - `high = candidate.get("high") or current_price`
  - `low = candidate.get("low") or current_price`
- 현재는 candidate에 `open_price / high / low` 키가 없어 항상 폴백 경로로 진입(주석에 명시)
- Task 3 완료 후 candidate에 실제 WS OHLC가 흐른다 → 폴백 분기는 과거 Redis/미수신 케이스에서만 동작

**Step 2: 테스트 작성**
- 기존 `test_signal_generator.py`의 `_make_candidate()` 헬퍼에 `open_price / high / low` 파라미터 추가 (기본값은 prev_close 근처)
- 신규 테스트 `test_build_snapshot_prefers_realtime_ohlc`: candidate에 `open_price=72000, high=73500, low=71500` 주입 → 조립된 snapshot에 동일 값 전달 확인 (prev_close 폴백이 아님)
- 신규 테스트 `test_build_snapshot_falls_back_when_ohlc_missing`: candidate에서 OHLC 키를 뺀 상태 → snapshot.open_price == prev_close, snapshot.high == current_price, snapshot.low == current_price 유지 확인
- 검증: `docker compose exec backend pytest tests/test_signal_generator.py -v`
- 예상: 신규 테스트 FAIL (아직 Task 3 테스트 통과만으로는 signal_generator 레벨 검증 없음)

**Step 3: `_build_snapshot()` 정책 유지 + 주석 업데이트**
- 코드 블록 자체는 **변경 없음** (이미 `candidate.get("open_price") or prev_close or current_price` 우선 정책). candidate에 유효 OHLC가 실리면 자동으로 실시간 값 사용
- 단, 주석을 Phase 8 Sprint 1 반영으로 업데이트:
  - "KIS 체결 데이터에 intraday open/high/low 없음" → "H0STCNT0 파서가 OHLC를 전파 (Phase 8 Sprint 1). 미수신 시 prev_close/current_price 폴백."
- `candidate.get("open_price", 0)`처럼 기본값 0이 내려오면 `or prev_close` 분기로 폴백되어 기존 의미 보존 (0은 falsy)
- 검증: `docker compose exec backend pytest tests/test_signal_generator.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/trading/signal_generator.py backend/tests/test_signal_generator.py
git commit -m "feat(phase8-sprint1): task4 — snapshot에 Redis 실시간 OHLC 우선 사용 + 폴백 유지"
```

**완료 기준:**
- ⬜ candidate에 실 OHLC 있을 때 snapshot이 실시간 값 사용
- ⬜ candidate OHLC 부재/0 시 기존 폴백 유지
- ⬜ 관련 테스트 PASS

---

### Task 5: Momentum Breakout 갭 분기 `breakout_ref` 교정

**skill:** `systematic-debugging` (자기돌파 버그 원인 파악 → 최소 수정으로 한정)

**Files:**
- Modify: `backend/modules/trading/strategies/momentum_breakout.py` (86~90줄 갭 분기 블록)
- Modify: `backend/tests/test_momentum_breakout.py`

**Step 1: 원인 정리 (systematic-debugging)**
- 현재 로직 (86~90줄):
  ```python
  if gap_rate >= 0.03:
      breakout_ref = snapshot.high   # ← 당일 고가
  else:
      breakout_ref = snapshot.prev_high
  ```
- 문제: `snapshot.high`는 장중 고가이며 `current_price <= high`가 항상 성립 → 갭 3%+ 종목은 `breakout` 게이트에서 자동 거부 (자기돌파 불가)
- 확정값 (Phase 8 문서 #4): `breakout_ref = snapshot.open_price` — 갭업 시초가 돌파로 판정
- 추가 영향 분석: confidence 계산의 `momentum_score = min((current_price - breakout_ref)/breakout_ref*100/5.0, 1.0)` 분모가 open_price로 바뀌어 갭 종목의 momentum_score가 소폭 감소 — 기존 `snapshot.high` 시 항상 음수여서 전혀 신호 미생성 → 이번 수정으로 정상화

**Step 2: 테스트 작성**
- `test_momentum_breakout.py`의 `_make_snapshot()`은 이미 `open_price` 파라미터 수용
- 신규 테스트 `test_gap_breakout_uses_open_price_as_ref`: `prev_close=69500, open_price=72000(gap 3.6%), high=72500, current_price=72600` → 돌파 판정 PASS (current_price > open_price), 신호 생성. 기존처럼 snapshot.high가 기준이면 72600 <= 72500은 거짓이므로 reject. 이 테스트가 새 로직을 강제
- 신규 테스트 `test_non_gap_uses_prev_high_as_ref`: `prev_close=69500, open_price=70000(gap 0.7%), prev_high=70500, current_price=70800` → 비갭 경로, 기존과 동일 prev_high 기준
- 신규 테스트 `test_gap_breakout_rejects_when_price_below_open`: gap 3%+ 지만 current_price < open_price 인 경우 `breakout` 스테이지에서 RejectedSignal 반환
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout.py -v`
- 예상: 신규 테스트 FAIL

**Step 3: `breakout_ref` 교정**
- 86~90줄을 다음으로 교체:
  ```python
  if gap_rate >= 0.03:
      breakout_ref = snapshot.open_price  # 갭업 시초가 돌파 (Phase 8 Sprint 1 — 자기돌파 버그 수정)
  else:
      breakout_ref = snapshot.prev_high
  ```
- `reason` dict는 기존 `breakout_ref` 키 유지 (값만 open_price로 교체되어 로깅에 반영). 추가 키 생성 불필요
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout.py -v`
- 예상: PASS. 단, 기존 "갭 3%+" 경로를 암시적으로 탔던 레거시 테스트가 있다면 조정 필요 — grep `"gap"`으로 재확인

**Step 4: simplify 검토**
- 수정 블록은 1줄 교체로 축소. 전략 나머지 로직(거래량 임계/체결강도/ATR/confidence)은 Sprint 2 대상이므로 이번 스프린트에서는 변경 없음
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout.py tests/test_signal_generator.py -v`
- 예상: 전체 PASS

**Step 5: 커밋**
```
git add backend/modules/trading/strategies/momentum_breakout.py backend/tests/test_momentum_breakout.py
git commit -m "fix(phase8-sprint1): task5 — 갭 3%+ 분기 breakout_ref를 snapshot.open_price로 교정 (자기돌파 버그)"
```

**완료 기준:**
- ⬜ 갭 3%+ 시 `breakout_ref == open_price` 보장
- ⬜ 비갭 경로 기존 prev_high 기준 유지
- ⬜ 신규 3개 테스트 PASS

---

### Task 6: 통합 회귀 + 수동 검증 가이드 작성

**skill:** — (verification-before-completion은 sprint-dev가 최종 단계에서 자동 적용)

**Files:**
- Modify: `docs/phase/phase8/sprint1/sprint1.md` (본 문서의 "최종 검증 계획" / "수동 검증 체크리스트" 갱신 — Task 이행 중 발견 사항 반영)
- Create: `docs/phase/phase8/sprint1/validation-notes.md` (배포 후 모니터링 수동 체크리스트 — 김단타 권고 반영)

**Step 1: 전체 pytest 회귀**
- 검증: `docker compose exec backend pytest -v`
- 예상: 모든 테스트 PASS. Task 1~5 수정은 기존 동작 보존 전제(폴백 경로 유지)이므로 회귀 없음 목표

**Step 2: 수동 검증 가이드 작성**
- `validation-notes.md`에 다음 체크리스트 작성:
  - **배포 직후 (장중 09:05~09:30)**: `railway logs --service backend`에서 `parse_execution` 경고 0건 확인. Redis CLI로 `GET realtime:005930:execution` 후 JSON에 `open_price/high/low` 존재 확인
  - **1~2시간 모니터링 (김단타 권고)**: Redis idx 매핑 오류 가능성 — 샘플 5종목의 실시간 OHLC를 KIS 공식 시세와 대조
  - **신호 관찰 (2거래일)**: trade_signals 테이블에 `momentum_breakout` 전략 pending 신호가 1건 이상 생성되는지 확인. 생성되지 않으면 Sprint 2(다층 진입) 착수 전 원인 재진단
  - **롤백 조건**: OHLC 파싱 경고 비율 10%+ → 이전 커밋으로 롤백 후 재조사
- Redis JSON 스키마 예시(과거 버전과 비교) 추가

**Step 3: sprint1.md 체크리스트 갱신**
- "최종 검증 계획" 표에 실제 실행한 명령 결과를 기록하도록 `status` 컬럼 추가 (sprint-close에서 채움)

**Step 4: 커밋**
```
git add docs/phase/phase8/sprint1/sprint1.md docs/phase/phase8/sprint1/validation-notes.md
git commit -m "docs(phase8-sprint1): task6 — 통합 회귀 결과 + 수동 검증 가이드"
```

**완료 기준:**
- ⬜ 전체 pytest PASS
- ⬜ validation-notes.md 배포 모니터링 가이드 작성
- ⬜ sprint1.md 체크리스트 갱신

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 모두 PASS (기존 + Task 1~5 신규) |
| kis_realtime 파서 | `docker compose exec backend pytest tests/test_kis_realtime.py -v` | OHLC 추출 테스트 PASS |
| scheduler Redis 캐싱 | `docker compose exec backend pytest tests/test_scheduler.py -v -k realtime` | OHLC 캐싱 테스트 PASS |
| realtime_screener | `docker compose exec backend pytest tests/test_realtime_screener.py -v` | candidate OHLC 전파 PASS |
| signal_generator snapshot | `docker compose exec backend pytest tests/test_signal_generator.py -v` | 실시간 우선 + 폴백 PASS |
| momentum_breakout 갭 분기 | `docker compose exec backend pytest tests/test_momentum_breakout.py -v` | 갭 open_price 기준 PASS |
| 프론트 타입 체크 | `cd frontend && npx tsc --noEmit` | 에러 없음 (본 Sprint 변경 없음 확인용) |
| Redis 필드 샘플링 (배포 후) | `redis-cli --tls GET realtime:005930:execution` (Railway/로컬) | JSON에 `open_price/high/low` 존재 |
| 신호 관찰 (2거래일) | `SELECT * FROM trade_signals WHERE strategy_name='momentum_breakout' AND created_at > now() - interval '2 days';` | 1건 이상 pending 신호 존재 |

---

## 수동 검증 체크리스트 (Phase 8 확정 파라미터 #5)

- ⬜ 배포 직후 Redis `realtime:{code}:execution` JSON에 OHLC 3필드 존재 확인
- ⬜ 1~2시간 장중 모니터링 — 파싱 경고 비율 < 1%
- ⬜ OHLC 샘플 5종목을 KIS 공식 시세와 대조 (idx 매핑 검증)
- ⬜ 2거래일 연속 `momentum_breakout` 신호 1건 이상 생성 확인
- ⬜ 신호 미생성 시 Sprint 2 착수 전 원인 재진단

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 완화책 |
|---|------|--------|--------|
| 1 | KIS mst/WS 문서와 실제 필드 idx(7/8/9) 불일치 가능성 | ⚠️ | 1~2시간 샘플 대조 모니터링. 오매핑 시 즉시 롤백 |
| 2 | OHLC 수정만으로 신호 미발생 가능성 | 정보 | 2거래일 관찰 후 Sprint 2(다층 진입) 필요 여부 재판단 |
| 3 | Redis 과거 캐시(OHLC 없음)와 새 코드 혼재 | 정보 | `.get("open_price", 0)` 폴백 → `or prev_close` 경로로 자동 폴백 |
| 4 | Phase 7.0 Sprint 3 E2E 게이트 대기 | ⚠️ | Sprint 1 완료 후 신호 생성 확인 → Phase 7.0 Sprint 3 재개 |

---

## 완료 기준

- ⬜ Task 1~6 모두 완료 (커밋 존재)
- ⬜ `docker compose exec backend pytest -v` 전체 통과
- ⬜ Redis JSON에 OHLC 3필드 포함 (코드 레벨 확인)
- ⬜ 갭 3%+ 경로에서 `breakout_ref == open_price` 단위 테스트 통과
- ⬜ validation-notes.md 작성 완료
