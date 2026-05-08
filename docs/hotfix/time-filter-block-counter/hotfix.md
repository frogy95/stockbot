# Hotfix: time-filter-block-counter

**브랜치:** `hotfix/time-filter-block-counter`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-05-07

---

## 문제 분석

### 증상
Phase 8.6 Sprint 3 v2.9.0 배포 직후 Paper 1거래일 관찰 항목 4번 (`metrics:time_filter:morning_lockout:{date}` Redis 키 적재 여부) 검증이 불가능한 상태. `should_block_entry`가 차단 판정을 반환하지만 이를 Redis에 기록하는 코드가 Sprint 3에서 누락됨.

### 원인
Sprint 3 `_time_filter.py` 구현 시 `should_block_entry` 함수만 작성, `record_block` 함수(INCR + EXPIRE) 미구현. `momentum_breakout.py`와 `volume_surge.py` 두 전략 모두 차단 발생 시 Redis에 카운터를 적재하지 않음.

### 영향 범위
- `metrics:time_filter:{reason}:{YYYY-MM-DD}` Redis 키 미적재
- Sprint 3 deploy.md Paper 관찰 4번 항목 검증 불가
- 차단 카운터 미적재로 운영 중 시간 필터 동작 여부 모니터링 불가

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/trading/strategies/_time_filter.py` | `async def record_block(redis_client, reason, now_kst)` 신규. 키 `metrics:time_filter:{reason}:{YYYY-MM-DD}`, INCR + EXPIRE 7일, graceful (None/예외 swallow) |
| `backend/modules/trading/strategies/momentum_breakout.py` | 시간 필터 차단 분기에서 `record_block` 호출 (await self.redis_client 사용) |
| `backend/modules/trading/strategies/volume_surge.py` | 동일 — 차단 분기에서 `record_block` 호출 |
| `backend/tests/strategies/test_time_filter.py` | `record_block` 4 케이스 추가 (incr+expire 검증, None skip, empty reason skip, redis 예외 swallow) |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `6d5a502` | fix(time-filter): 차단 카운터 Redis incr 적재 (Sprint 3 잔존 부채) | 2026-05-07 |

---

## 검증

### 자동 검증
- ✅ pytest (타겟 3파일): **66 passed, 0 failed** (0.16초)
  - `tests/strategies/test_time_filter.py` — record_block 신규 4 케이스 PASS
  - `tests/strategies/test_volume_surge.py` — 기존 회귀 0건
  - `tests/test_momentum_breakout.py` — 기존 회귀 0건
- ✅ 타겟 API 검증: N/A — API 인터페이스 변경 없음 (내부 Redis 적재 로직만 추가)
- ✅ Playwright 타겟 검증: N/A — UI 변경 없음

### 코드 리뷰 결과
- Critical/High 이슈: **0건**
- 보안: 하드코딩 시크릿 없음, Redis 키 인젝션 위험 없음 (reason은 내부 상수값)
- 성능: INCR + EXPIRE 2 RTT, 차단 경로에서만 실행 — 정상 경로 오버헤드 0
- `now_kst` 타임존 안전: 두 call site 모두 KST-aware datetime 사용 확인
- graceful: `redis_client=None`, `reason=""`, Redis 예외 모두 조용히 skip

### 수동 검증
- ⬜ Railway 배포 후 장중 첫 차단 발생 시 `redis-cli GET "metrics:time_filter:morning_lockout:$(date +%Y-%m-%d)"` ≥1 확인

---

## PR
- **main PR URL:** (PR 생성 후 업데이트)
- **develop 역머지 PR:** (역머지 후 업데이트)
- **대상:** main
