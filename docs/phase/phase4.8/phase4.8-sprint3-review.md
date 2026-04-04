# Phase 4.8 Sprint 3 추가 검토 보고서

> **작성일**: 2026-04-05
> **검토 대상**: 스케줄러 장전 파이프라인 체인 방식 전환 (Sprint 3 추가 타당성)
> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 윤에이피(API 개발자), 박퀀트(퀀트)

---

## 1. 발견된 설계 결함 요약

### 현재 구조 (고정 시각 독립 fire)

```
08:00  _premarket_collect     ← CronTrigger
08:10  _etf_master_collect    ← CronTrigger (premarket 완료 여부 무관)
08:10  _primary_screen        ← CronTrigger (premarket 완료 여부 무관)
08:15  _etf_collect           ← CronTrigger (etf_master 완료 여부 무관)
08:15  _dart_collect          ← CronTrigger (primary_screen 완료 여부 무관)
08:20  _sentiment_collect     ← CronTrigger (primary_screen 완료 여부 무관)
08:30  _premarket_retry       ← CronTrigger
```

### 문제점

`_check_dependency()`는 선행 단계가 "success"인지 확인하되, **대기하지 않고 즉시 스킵**한다:

```python
async def _check_dependency(self, step: str, pipeline_status: dict | None = None) -> bool:
    deps = DEPENDENCY_MAP.get(step, [])
    if not deps:
        return True
    if pipeline_status is None:
        pipeline_status = await self._get_pipeline_status()
    return all(
        pipeline_status.get(dep, {}).get("status") == "success"
        for dep in deps
    )
```

KIS 일봉 폴백 수집이 3~5분 소요될 경우:
- 08:00 `_premarket_collect` 시작 → 포털 실패 → KIS 폴백 시작
- 08:10 `_primary_screen` fire → premarket.status != "success" → **스킵**
- 08:03~05 KIS 폴백 완료 → premarket "success" 업데이트 → 그러나 primary_screen은 이미 스킵됨
- **결과: 당일 자동 스크리닝 전체 무력화, 수동 복구 필요**

### 올바른 설계 (체인 방식)

```
CronTrigger(08:00) → run_premarket_pipeline()
    ├→ _premarket_collect() (완료 후)
    ├→ _etf_master_collect() (완료 후)
    ├→ _primary_screen() (완료 후)
    ├→ _etf_collect() (병렬 가능)
    ├→ _dart_collect() (병렬 가능)
    └→ _sentiment_collect()
```

이미 `run_premarket_pipeline()`이 올바른 체인 방식으로 구현되어 있으므로, 이를 CronTrigger에 등록하고 개별 job을 제거하면 해결된다.

---

## 2. 전문가별 검토 결과

### 정프로 (PO) — Sprint 3 추가 타당성 및 범위

#### 요약: ✅ Sprint 3 추가 타당

**판단 근거:**

1. **Phase 4.8 테마와의 일치성**: Phase 4.8의 핵심 목표는 "EOD 데이터 수집 내결함성 강화"이다. 스케줄러의 고정 시각 독립 fire 구조는 Sprint 1에서 구현한 KIS 폴백의 효과를 무력화시킬 수 있는 **근본 설계 결함**이다. 폴백을 만들어놓고 폴백 때문에 스크리닝이 스킵되는 것은 Phase 4.8이 해결해야 할 문제 영역에 정확히 속한다.

2. **Sprint 2와의 관계**: Sprint 2는 이미 완료 상태(PR #78)이며, 재시도/알림/cross-check이 주제다. Sprint 3은 "스케줄러 구조 변경"이라는 별도의 핵심 목표를 가지므로 **별도 Sprint가 맞다**. Sprint 2에 병합하면 범위가 커져서 "한 스프린트에 하나의 핵심 목표" 원칙에 위배된다.

3. **작업 규모**: 변경 범위가 `scheduler.py`의 `start()` 메서드 리팩토링 + 관련 테스트 수정으로 비교적 작다. 단일 Sprint로 충분히 소화 가능하다.

4. **우선순위**: 이 결함은 KIS 폴백이 동작하는 **매번** 발생할 수 있다. 공공데이터포털의 장전 지연은 이미 관찰된 실제 장애이므로, **Phase 5 이전에 반드시 수정**해야 한다.

**Sprint 2 병합 vs Sprint 3 분리:**
- Sprint 2 병합: ❌ — Sprint 2는 이미 완료(PR #78). 병합하면 기존 PR을 폐기하거나 재작업해야 한다.
- Sprint 3 분리: ✅ — 별도 Sprint로 깔끔하게 진행. Sprint 2 완료 후 Sprint 3 시작이 자연스러운 흐름.

---

### 최리스크 (리스크관리) — 리스크 분석

#### 요약: ✅ 통과 (단, 주의사항 3건)

**리스크 분석:**

1. **현재 구조의 리스크 (수정하지 않을 경우)**:
   - KIS 폴백이 3~5분 걸리면 primary_screen이 스킵되어 **당일 자동 매매가 완전히 중단**
   - 수동 복구(`POST /api/v1/collector/trigger/premarket-pipeline`)를 해야 하는데, 사용자가 인지하지 못하면 장 시작 후에야 발견
   - **심각도: ❌ 높음** — 이 결함은 Sprint 1의 KIS 폴백 구현이 무효화되는 것과 같다

2. **체인 방식 전환의 리스크**:
   - ⚠️ **장전 파이프라인이 하나의 긴 작업이 됨**: 포털 수집(~10초) + ETF 마스터(~30초) + KIS 폴백(~3분) + 스크리닝(~10초) + DART + 센티멘트 → 전체 ~5~10분. 08:00 시작해도 08:10 전에 모두 완료 가능하지만, 장애 시 전체가 지연될 수 있다
   - ⚠️ **09:00 장 시작 전 완료 보장**: 최악의 경우(포털 실패 + KIS 폴백 + 재시도 성공)에도 08:30~08:40이면 완료. 09:00 장 시작까지 여유 있음
   - ⚠️ **`run_premarket_pipeline()`의 수동 복구 트리거와 자동 스케줄 충돌 가능성**: 08:00 자동 파이프라인이 실행 중일 때 수동 트리거가 들어오면? 기존 `PIPELINE_RUNNING_KEY` 락으로 보호되어 있으나, 자동 스케줄에서도 동일 락을 선점해야 함

3. **주의사항:**
   - **(필수)** `run_premarket_pipeline()`을 CronTrigger에 등록할 때 `PIPELINE_RUNNING_KEY` 락을 자동 스케줄에서도 선점하도록 수정 필요. 현재 락 선점은 "API 핸들러가 담당"이라는 주석이 있음.
   - **(필수)** 08:30 `_premarket_retry` job은 체인 파이프라인에 포함되지 않아야 함. 체인 파이프라인 실행 후 별도로 08:30에 fire하는 것이 맞음.
   - **(권고)** 파이프라인 전체 소요 시간을 로깅하여 09:00 전 완료 여부를 모니터링

---

### 윤에이피 (API 개발자) — 기술 구현 분석

#### 요약: ✅ 통과 (구현 난이도 낮음)

**코드 분석:**

1. **`run_premarket_pipeline()` 현재 구현 (L251~268)**: 이미 올바른 체인 방식으로 동작한다. 다만 몇 가지 수정이 필요하다:

   ```python
   async def run_premarket_pipeline(self) -> dict:
       try:
           await self._premarket_collect()
           await self._etf_master_collect()
           await self._primary_screen()
           await self._etf_collect()
           await self._dart_collect()
           await self._sentiment_collect()
       finally:
           await self._redis.delete(PIPELINE_RUNNING_KEY)
       ...
   ```

   - **문제 1**: `PIPELINE_RUNNING_KEY` 해제가 `finally`에 있지만, 선점은 API 핸들러에서만 한다. 자동 스케줄용으로 사용하려면 선점도 이 메서드 안에서 해야 한다.
   - **문제 2**: 현재 `_premarket_collect()`는 실패해도 예외를 raise하지 않고 0을 반환한다. 즉 체인이 끊기지 않는다. 이는 `_check_dependency()`가 pipeline_status를 확인하므로 괜찮다 — 후속 단계에서 자체적으로 스킵한다.
   - **문제 3**: `_premarket_retry`는 체인 밖에서 08:30에 독립 실행되어야 한다. 현재 구조 유지가 맞다.

2. **`start()` 메서드 수정 범위 (L295~375)**:
   - **제거할 job**: `premarket_collect`, `etf_master_collect`, `primary_screen`, `etf_collect`, `dart_collect`, `sentiment_collect` (6개)
   - **추가할 job**: `premarket_pipeline` (08:00, `run_premarket_pipeline` 또는 새 래퍼 메서드)
   - **유지할 job**: `market_open`, `market_close`, `market_open_recovery`, `premarket_retry`, `secondary_screen` (5개)
   - **주의**: `primary_screen` job은 `if self._primary_screener:` 가드가 있었음. 체인 방식에서도 screener가 없으면 스크리닝 스킵 로직 필요.

3. **수동 트리거 API와의 관계**:
   - `trigger_premarket()`, `trigger_etf()`, `trigger_dart()` 등 개별 수동 트리거 API는 유지해야 한다. 이들은 디버깅/운영에 필요.
   - `run_premarket_pipeline()` 수동 트리거도 그대로 유지.

4. **테스트 영향**:
   - `test_scheduler_integration.py`: 개별 job 등록 검증 테스트가 있으면 수정 필요
   - `test_scheduler_retry.py`: premarket_retry job은 유지되므로 영향 없음
   - `test_scheduler_telegram_alert.py`: 알림 테스트는 메서드 단위이므로 영향 없음
   - **새 테스트 필요**: 체인 파이프라인이 08:00에 등록되는지, 개별 job이 제거되었는지 검증

**구현 난이도: 낮음 (S)**

변경 범위가 `scheduler.py`의 `start()` 메서드 리팩토링 + 파이프라인 래퍼 메서드 추가 + 락 선점 로직 이동으로 제한된다.

---

### 박퀀트 (퀀트) — 스크리닝 영향 분석

#### 요약: ✅ 통과

**분석:**

1. **스크리닝 데이터 무결성**: 체인 방식으로 전환하면 `_premarket_collect()` 완료 후에만 `_primary_screen()`이 실행되므로, 스크리닝이 불완전한 데이터로 실행되는 시나리오가 원천 차단된다. 이는 데이터 품질 관점에서 확실한 개선이다.

2. **KIS 폴백 후 스크리닝**: 현재 구조에서 KIS 폴백 성공 후 primary_screen이 스킵되는 것은 Sprint 1의 핵심 가치(SPOF 해소)를 무력화한다. 체인 방식으로 전환하면 폴백 성공 → 즉시 스크리닝 → DART/센티멘트까지 정상 진행된다.

3. **시간 순서 보장**: 체인 방식은 데이터 수집 → 스크리닝 → 보조 수집의 논리적 순서를 강제한다. 이는 `date_subq` 오염 같은 날짜 관련 이슈도 예방한다.

4. **08:30 재시도와의 상호작용**: 재시도는 체인 밖에서 동작하므로, 체인 파이프라인이 이미 KIS 폴백으로 성공한 상태에서 재시도가 포털 데이터를 덮어쓰는 기존 로직이 그대로 유지된다. 문제없다.

---

## 3. Sprint 3 작업 범위 (제안)

### 수정 대상 파일

| 파일 | 작업 | 변경 유형 |
|------|------|----------|
| `backend/modules/collector/scheduler.py` | `start()` 리팩토링: 개별 장전 job 제거, 체인 파이프라인 job 등록 | 수정 |
| `backend/modules/collector/scheduler.py` | `_run_scheduled_pipeline()` 래퍼 메서드 추가 (락 선점 + 체인 실행) | 수정 |
| `backend/modules/collector/scheduler.py` | `run_premarket_pipeline()` 내부 락 처리 분리 | 수정 |
| `backend/tests/test_scheduler_integration.py` | job 등록 검증 테스트 수정 | 수정 |
| `backend/tests/test_pipeline_chain.py` | 체인 파이프라인 동작 검증 테스트 | **신규** |

### 변경 상세

#### 1. `start()` 메서드 리팩토링

**제거할 job 등록 (6개):**
- `premarket_collect` (08:00)
- `etf_master_collect` (08:10)
- `primary_screen` (08:10)
- `etf_collect` (08:15)
- `dart_collect` (08:15)
- `sentiment_collect` (08:20)

**추가할 job 등록 (1개):**
```python
self._scheduler.add_job(
    self._run_scheduled_pipeline,
    CronTrigger(hour=8, minute=0, timezone=tz),
    id="premarket_pipeline",
    misfire_grace_time=MISFIRE_GRACE_TIME,
)
```

**유지할 job (5개):**
- `market_open` (09:00)
- `market_close` (15:30)
- `market_open_recovery` (09:05)
- `premarket_retry` (08:30)
- `secondary_screen` (30초 주기)

#### 2. `_run_scheduled_pipeline()` 래퍼 메서드

```python
async def _run_scheduled_pipeline(self) -> None:
    """08:00 CronTrigger용 장전 파이프라인. 락 선점 후 체인 실행."""
    # 이미 실행 중이면 스킵 (수동 트리거와 충돌 방지)
    existing = await self._redis.get(PIPELINE_RUNNING_KEY)
    if existing:
        logger.warning("파이프라인 이미 실행 중 — 자동 스케줄 스킵")
        return
    await self._redis.set(PIPELINE_RUNNING_KEY, "auto", ttl=STATE_TTL)
    await self.run_premarket_pipeline()
```

#### 3. 수동 트리거 API

- 기존 개별 트리거(`trigger_premarket`, `trigger_etf`, etc.) 유지 — 디버깅/운영용
- `run_premarket_pipeline()` API 트리거 유지 — 수동 복구용
- `_run_scheduled_pipeline()` 내부에서 `PIPELINE_RUNNING_KEY` 충돌 보호

#### 4. 테스트

- job 등록 검증: `premarket_pipeline` job이 08:00에 등록, 개별 장전 job 미등록 확인
- 체인 실행 검증: premarket 실패 → primary_screen 스킵 → dart/sentiment도 스킵
- 체인 실행 검증: premarket 성공 → primary_screen 실행 → dart/sentiment 실행
- 락 충돌 검증: 자동 파이프라인 실행 중 수동 트리거 → 거부

---

## 4. Sprint 2와의 관계

| 비교 항목 | Sprint 2 병합 | Sprint 3 분리 |
|----------|-------------|-------------|
| Sprint 2 상태 | 이미 완료 (PR #78) | 영향 없음 |
| 작업 범위 | Sprint 2 PR 폐기/재작업 필요 | 독립 진행 가능 |
| 핵심 목표 분리 | Sprint 2: 재시도+알림, Sprint 3: 구조 변경 | 목표별 분리 |
| 리스크 | Sprint 2 기존 성과물 위험 | 리스크 격리 |
| **권장** | ❌ | **✅** |

**결론: Sprint 3으로 분리 진행이 타당하다.**

---

## 5. Phase 4.8 테마 일치성

| 검증 항목 | 결과 |
|----------|------|
| Phase 4.8 목표: "EOD 데이터 수집 내결함성 강화" | ✅ 스케줄러 구조가 폴백을 무력화하는 것은 내결함성 결함 |
| Sprint 1/2와의 연관성 | ✅ Sprint 1의 KIS 폴백 효과를 보장하는 후속 작업 |
| 독립 Phase 필요성 | ❌ 불필요 — Phase 4.8 범위 내에서 해결 가능 |
| Phase 5로 이연 가능성 | ❌ 부적절 — KIS 폴백이 동작할 때마다 발생하는 즉시 수정 대상 |

---

## 6. 리스크 및 주의사항

| # | 항목 | 심각도 | 대응 |
|---|------|--------|------|
| 1 | `run_premarket_pipeline()` 락 선점 로직 분리 필요 | ⚠️ | `_run_scheduled_pipeline()` 래퍼에서 락 선점, `run_premarket_pipeline()`은 기존 API 핸들러 호환 유지 |
| 2 | 개별 수동 트리거 API 유지 필요 | ⚠️ | 개별 메서드(`_premarket_collect`, `_etf_master_collect` 등)는 삭제하지 않음. `start()`의 CronTrigger 등록만 제거 |
| 3 | `if self._primary_screener:` 가드 유지 | ⚠️ | 체인 파이프라인 내부에서도 screener 미설정 시 스크리닝 스킵 |
| 4 | 파이프라인 전체 소요 시간 모니터링 | ✅ 권고 | 파이프라인 시작/종료 시각 로깅으로 09:00 전 완료 여부 확인 |
| 5 | 기존 테스트 회귀 | ⚠️ | job 등록 검증 테스트가 있으면 수정 필요 |

---

## 7. 완료 기준 (Sprint 3)

| 항목 | 기준 | 상태 |
|------|------|------|
| 장전 파이프라인 체인 등록 | 08:00 CronTrigger에 `_run_scheduled_pipeline` 등록 | ⬜ |
| 개별 장전 job 제거 | `premarket_collect`, `etf_master_collect`, `primary_screen`, `etf_collect`, `dart_collect`, `sentiment_collect` CronTrigger 미등록 | ⬜ |
| 락 선점 분리 | 자동 스케줄/수동 트리거 모두 `PIPELINE_RUNNING_KEY` 락 보호 | ⬜ |
| 수동 트리거 유지 | 개별 trigger API 정상 동작 | ⬜ |
| 테스트 통과 | 전체 pytest 회귀 없음 + 신규 테스트 통과 | ⬜ |

---

## 8. 종합 판단

| 전문가 | 판단 | 핵심 의견 |
|--------|------|----------|
| 정프로 (PO) | ✅ Sprint 3 추가 타당 | Phase 4.8 범위 내, Sprint 2 완료 후 별도 진행, 작업 규모 적절 |
| 최리스크 (리스크관리) | ✅ 통과 (주의 3건) | 현재 구조는 폴백 무력화 리스크, 락 처리와 시간 모니터링 필수 |
| 윤에이피 (API 개발자) | ✅ 구현 난이도 낮음 | `start()` 리팩토링 + 래퍼 메서드 + 테스트 수정으로 완료 가능 |
| 박퀀트 (퀀트) | ✅ 데이터 무결성 개선 | 체인 방식이 스크리닝 데이터 품질을 보장 |

**전원 합의: Phase 4.8 Sprint 3 추가 승인. Sprint 2 완료 후 즉시 진행 권장.**
