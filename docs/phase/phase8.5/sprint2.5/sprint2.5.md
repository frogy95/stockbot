# Sprint 2.5: Phase 8.5 인프라 보강 + 관측성·문서 정합성 (Phase 8.5)

**Goal:** Phase 8.5 Sprint 2에서 확정된 "원래 설계 vs 확정값" 중 **아직 구현에 반영되지 않은 인프라 보강분**과 **관측성/문서 정합성 누락분**을 단일 스프린트로 마감한다. 파라미터 값(임계·분기·포지션·손절)은 **절대 변경하지 않는다** — 본 Sprint는 "이미 확정된 동작을 더 안전하게 지탱하는 레일"만 깐다.

**Architecture:** Sprint 2가 배포한 동적 `MIN_VOLUME_FLOOR` + 풀 하한 폴백의 **환경변수 override 경로**를 실제 코드가 일관되게 사용하도록 인프라 수준에서 정리한다. Redis override(`settings:override:*`)는 Task 5에서 이미 설계된 규약을 `core/config.py` / `_resolve_min_volume_floor` / `realtime_screener.screen()` 3개 지점에서 **한 함수(`resolve_override`)로 통합**하여 향후 Sprint에서 일관되게 쓰도록 한다. 관측성은 "자동 롤백이 발동한 순간"을 관리자에게 **대시보드에서 시각적으로** 남기고, 문서 측은 Phase 8 원안 DoD("3거래일 연속 신호")를 Phase 8.5에서 재정의한 DoD("일평균 ≥1, 0건 일수 ≤2/5")로 동기화하여 Phase 8.6 Sprint 1 착수 시점에 혼선이 없게 한다.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 (async) / Redis 7 / APScheduler / pytest-asyncio / Next.js 16 / React 19 / Tailwind 4 / SWR

**상태:** 📋 계획 수립 완료 (2026-04-23)
**Sprint 기간:** 2026-04-24 ~ (5거래일 관찰 동시 진행)
**이전 스프린트:** Phase 8.5 Sprint 2 (✅ 완료, 2026-04-23)
**다음 스프린트:** Phase 8.6 Sprint 1 (E2E + LIVE 전환 게이트) — Phase 8.5 Sprint 2 배포 + 5거래일 관찰 완료 후
**브랜치명:** `phase8.5-sprint2.5`
**PR:** (생성 예정)

---

## 착수 배경 (2026-04-23)

Sprint 2 완료 후 advisor 리뷰(권고안 A)에서 식별된 **인프라 3개 / 관측성 2개 / 문서 1개** 항목. 모두 다음 조건을 만족한다:

1. **파라미터 값 변경 없음** — Sprint 2에서 4명 전원 합의한 수치는 전부 불변
2. **관찰 주기 중단 없음** — 5거래일 관찰은 별도 진행, 본 Sprint 결과로 판단 트리 조정만 수행
3. **파일 수 ≤ 6 / 변경 라인 ≤ 75** — Hotfix 상한(파일 3/50줄)을 초과하되, 인프라 통합·문서 동기화 성격상 Sprint로 처리

### 커버 범위

| # | 항목 | 근거 |
|---|------|------|
| A | `resolve_override()` 통합 유틸 (Redis `settings:override:*` 단일 lookup) | Sprint 2 Task 5에서 규약만 설계, 각 호출부가 ad-hoc lookup — 일관성 리스크 |
| B | env 변수 로드 검증 (프로덕션 Railway 환경변수 동기화 체크 스크립트) | Sprint 2 Task 1에서 8종 선언, Railway 수동 반영 누락 시 dev/prod 동작 divergence |
| C | 자동 롤백 발동 시 대시보드 경고 배너 | Sprint 2 Task 5에서 Telegram만 — 관리자가 Telegram 미확인 시 무한 legacy 모드 |
| D | fallback-stats 카드 "롤백 발동 여부" 필드 추가 | Sprint 2 Task 6 카드에 현재 발동 상태 미표시 |
| E | Phase 8 phase8.md Sprint 3 LIVE 게이트 DoD 재정의 반영 | Phase 8.5 문서 Line 131~141에서 재정의, 원본은 원안 유지 — 실행 시점 혼선 방지 |
| F | 5거래일 관찰 종료 후 의사결정 트리 (A/B/C/D 시나리오) | Sprint 2 완료 시점 미정의, 관찰 종료 후 판단 근거 필요 |

---

## 제외 범위

이 스프린트에서 **하지 않는 것**:

- **`ATR_FILTER_PCT` 기본값 변경 금지** — Sprint 2 확정 #10~#13 불변
- **`MIN_VOLUME_FLOOR` 분기값(0.4 / 0.5 / 0.6 / HARD 0.3) 변경 금지** — 확정 #11~#13
- **폴백 파라미터(THRESHOLD=3, MAX=5, position 0.5, 손절 -1.5%, 제외 -3%) 변경 금지** — 확정 #1~#8
- **`SECONDARY_POOL_PASS_THRESHOLD=75.0` 변경 금지** — 확정 #9 (분포 데이터 필요)
- **관찰 기간 5거래일 단축 금지** — 확정 #26 (최리스크 엄격)
- **자동 롤백 트리거 조건 완화 금지** — 확정 #24 (2거래일 연속 0건)
- **`prev_close_time_guard` 13:00 연장 금지** — 확정 #15 (전원 거부)
- **시간대 슬라이딩 `MIN_VOLUME_FLOOR` 도입 금지** — 확정 #14 (전원 거부)
- **DB 스키마 변경 없음** — Alembic 마이그레이션 없음 (전부 Redis + env + 문서)
- **신규 의존성 추가 없음** — 기존 pip/npm 패키지 범위 내

**핵심 제약 (절대 불변)**:

- Sprint 2의 `_resolve_min_volume_floor` 반환 규칙 3분기는 **행동 동일성** 보장: 본 Sprint 변경 전후에 동일 입력 → 동일 반환이어야 한다 (회귀 테스트로 고정)
- `_shadow_evaluate`의 stage 판정은 계속 본체와 **동일 override 경로**를 타야 한다 — override lookup을 한 지점에서 새면 shadow/본체 분리 발생
- Sprint 2에서 머지된 `phase8.5-sprint2` 브랜치와는 별도 브랜치로 진행한다 — Sprint 2 PR이 아직 미머지면 rebase 필요

---

## 확정 파라미터 요약 (Sprint 2 승계, 본 Sprint에서 **변경 없음**)

### 불변 파라미터 (Sprint 2 확정)

| env 변수 | 값 | 확정 # |
|---------|-----|--------|
| `MIN_VOLUME_FLOOR_MODE` | `dynamic` | #23 |
| `MIN_VOLUME_FLOOR_HARD` | `0.3` | #13 |
| `SECONDARY_POOL_FALLBACK_ENABLED` | `True` | #23 |
| `SECONDARY_POOL_FALLBACK_THRESHOLD` | `3` | #1 |
| `SECONDARY_POOL_MAX` | `5` | #3 |
| `FALLBACK_DROP_EXCLUDE_PCT` | `-3.0` | #7 |
| `FALLBACK_POSITION_SIZE_RATIO` | `0.5` | #6 |
| `FALLBACK_STOP_LOSS_PCT` | `-1.5` | #8 |

### 신규 환경변수 (본 Sprint)

| env 변수 | 기본값 | 역할 |
|---------|--------|------|
| `SETTINGS_OVERRIDE_ENABLED` | `True` | Redis `settings:override:*` lookup 활성화 플래그. 긴급 시 `False`로 override 경로 차단 가능 |

### Redis override 규약 (본 Sprint에서 통합)

| key | 값 | TTL | 소비자 |
|-----|-----|-----|--------|
| `settings:override:MIN_VOLUME_FLOOR_MODE` | `"legacy"` \| `"dynamic"` | 7일 | `_resolve_min_volume_floor` |
| `settings:override:SECONDARY_POOL_FALLBACK_ENABLED` | `"True"` \| `"False"` | 7일 | `realtime_screener.screen()` |
| `settings:override:triggered_at` (신규) | ISO 8601 timestamp | 7일 | 대시보드 경고 배너 (Task 3), fallback-stats API (Task 4) |
| `settings:override:reason` (신규) | 자유 문자열 (예: `"auto_rollback_2d_zero_signals"`) | 7일 | 대시보드 배너 + 관리자 로그 |

---

## 실행 플랜

의존성 그래프:

```
Task 1 (resolve_override 유틸 통합)
  ├─> Task 2 (env 변수 로드 검증 스크립트 + deploy.md 체크리스트)
  └─> Task 3 (자동 롤백 경고 배너 백엔드 API + 프론트 배너)
        └─> Task 4 (fallback-stats 카드 롤백 상태 필드)
              └─> Task 5 (Phase 8 phase8.md LIVE 게이트 DoD 재정의 반영)
                    └─> Task 6 (통합 검증 + 커밋 + 관찰 의사결정 트리 참조 주입)
```

Task 1은 인프라 기반. Task 2~5는 Task 1 이후 파일 소유권 분리로 **병렬 가능**. Task 6은 마무리.

### Phase 1 (순차 — 기반)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | `core/settings_override.py` 신규 — `resolve_override(key, default)` 유틸 통합 | 백엔드 | `simplify` |

### Phase 2 (병렬 가능 — 파일 소유권 분리)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | `scripts/check_env_sync.py` + deploy.md "Railway env 동기화 체크리스트" | 백엔드 + 문서 | — |
| Task 3 | `/api/v1/metrics/override-status` + `OverrideBanner` 컴포넌트 | 백엔드 + 프론트 | `frontend-design` |
| Task 4 | fallback-stats 카드에 `is_rollback_active` 필드 표시 | 프론트 | `frontend-design` |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | `docs/phase/phase8/phase8.md` Sprint 3 DoD 섹션을 재정의판(D1~D7)으로 교체 | 문서 | — |

### Phase 4 (마무리)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | pytest + tsc + API curl + 본 sprint2.5.md 하단 의사결정 트리 확증 + 커밋 + sprint-close 안내 | 전체 | `verification-before-completion` |

> **팀 실행**: Phase 2를 "팀으로 실행해줘"로 요청 가능. 백엔드(Task 2, 3 백엔드 부분)와 프론트엔드(Task 3 프론트 + Task 4)가 파일 소유권 분리되어 충돌 없음.

---

### Task 1: `resolve_override` 유틸 통합

**skill:** `simplify`

**Files:**
- Create: `backend/core/settings_override.py` (신규, ~25줄)
- Modify: `backend/modules/trading/strategies/momentum_breakout.py` (기존 Redis lookup → 유틸 호출로 치환, ~5줄)
- Modify: `backend/modules/screening/realtime_screener.py` (동일 치환, ~5줄)
- Modify: `backend/core/config.py` (`SETTINGS_OVERRIDE_ENABLED` 필드 추가, ~3줄)
- Modify: `backend/modules/collector/scheduler.py` (자동 롤백 발동 시 `triggered_at` / `reason` 추가 기록, ~5줄)
- Create: `backend/tests/core/test_settings_override.py` (유닛 테스트, ~20줄)

**Step 1: `core/settings_override.py` 신규 작성**
```python
"""Redis settings override 통합 유틸 (Phase 8.5 Sprint 2.5).

Sprint 2 Task 5에서 정의한 `settings:override:*` 규약을 단일 진입점으로 통합.
각 호출부(momentum_breakout, realtime_screener)가 동일한 parsing 로직을 공유한다.
"""
from typing import TypeVar, Callable
from core.redis import get_redis  # 기존 유틸
from core.config import settings
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")
OVERRIDE_PREFIX = "settings:override:"


async def resolve_override(
    key: str,
    default: T,
    *,
    cast: Callable[[str], T] = str,
) -> T:
    """Redis `settings:override:{key}` → default 순으로 값 해석.

    `SETTINGS_OVERRIDE_ENABLED=False`면 항상 default 반환.
    cast 실패 시 logger.warning 후 default.
    """
    if not settings.SETTINGS_OVERRIDE_ENABLED:
        return default
    try:
        redis = await get_redis()
        raw = await redis.get(f"{OVERRIDE_PREFIX}{key}")
        if raw is None:
            return default
        return cast(raw.decode() if isinstance(raw, bytes) else raw)
    except Exception as exc:  # 절대 예외 전파 금지 (본체 경로 방어)
        logger.warning("resolve_override(%s) failed: %s", key, exc)
        return default
```

**Step 2: 기존 ad-hoc lookup 치환**
- `momentum_breakout.py::_resolve_min_volume_floor`:
  ```python
  # Before (Sprint 2 구현):
  # redis = await get_redis()
  # raw = await redis.get("settings:override:MIN_VOLUME_FLOOR_MODE")
  # mode = raw.decode() if raw else settings.MIN_VOLUME_FLOOR_MODE

  # After:
  mode = await resolve_override(
      "MIN_VOLUME_FLOOR_MODE",
      default=settings.MIN_VOLUME_FLOOR_MODE,
  )
  ```
- `realtime_screener.py::screen()`에서 `SECONDARY_POOL_FALLBACK_ENABLED` 동일 치환 (`cast=lambda s: s.lower() == "true"`)

**Step 3: `core/config.py`에 필드 추가**
```python
SETTINGS_OVERRIDE_ENABLED: bool = Field(
    default=True,
    description="Redis settings override 경로 활성화 (긴급 차단용)",
)
```
`.env.example`에도 주석 포함 1줄 추가.

**Step 4: `scheduler.py` 자동 롤백 job에서 신규 key 기록**
- 기존 `SET settings:override:MIN_VOLUME_FLOOR_MODE legacy EX 604800` 2회 호출 옆에:
  ```python
  await redis.set(f"{OVERRIDE_PREFIX}triggered_at", datetime.now(KST).isoformat(), ex=604800)
  await redis.set(f"{OVERRIDE_PREFIX}reason", "auto_rollback_2d_zero_signals", ex=604800)
  ```

**Step 5: 단위 테스트**
- `test_resolve_override_returns_default_when_disabled`
- `test_resolve_override_returns_redis_value`
- `test_resolve_override_fallback_on_cast_error`
- `test_resolve_override_fallback_on_redis_error` (monkeypatch로 raise)
- `test_shadow_and_body_use_same_override` (monkeypatch spy → 동일 키 1회+ 호출)

**Step 6: 행동 동일성 회귀 확증**
- 기존 `test_momentum_breakout.py::TestResolveMinVolumeFloor` 6개 테스트 모두 그대로 GREEN이어야 함 (override 미설정 시 동작 동일)
- `docker compose exec backend pytest tests/test_momentum_breakout.py tests/test_realtime_screener.py tests/core/test_settings_override.py -v`

**Step 7: 커밋**
```
git add backend/core/settings_override.py backend/core/config.py .env.example \
  backend/modules/trading/strategies/momentum_breakout.py \
  backend/modules/screening/realtime_screener.py \
  backend/modules/collector/scheduler.py \
  backend/tests/core/test_settings_override.py
git commit -m "refactor(phase8.5-sprint2.5): task1 — resolve_override 유틸 통합 + triggered_at/reason 기록"
```

**완료 기준:**
- ✅ 3개 호출부가 동일 `resolve_override()` 함수 경유
- ✅ Sprint 2 회귀 테스트 전원 GREEN (행동 동일성)
- ✅ 신규 `settings:override:triggered_at` / `reason` 자동 롤백 시 기록

---

### Task 2: env 동기화 체크 스크립트 + deploy.md 항목

**Files:**
- Create: `scripts/check_env_sync.py` (신규, ~30줄)
- Modify: `deploy.md` (Railway env 수동 검증 항목 추가, ~10줄)

**Step 1: 스크립트 작성**
- 목적: `.env.example`에 선언된 변수와 `core/config.py::Settings` 필드의 **이름 집합 일치** 검증
- 누락(env.example에만 있음 / Settings에만 있음) 시 exit 1
- 실행: `python scripts/check_env_sync.py`
- 이후 CI 추가는 본 Sprint 범위 외 (수동 실행)

**Step 2: `deploy.md` 수정**
```markdown
### Phase 8.5 Sprint 2.5 — Railway 환경변수 동기화
⬜ `SETTINGS_OVERRIDE_ENABLED=True` Railway 반영 확인
⬜ Sprint 2 env 8종(`MIN_VOLUME_FLOOR_MODE` 외) Railway에 존재 확인 (Sprint 2 배포 시 반영되었어야 함 — 재확인 목적)
⬜ `python scripts/check_env_sync.py` 로컬 실행 결과 exit 0
```

**Step 3: 커밋**
```
git add scripts/check_env_sync.py deploy.md
git commit -m "chore(phase8.5-sprint2.5): task2 — env 동기화 스크립트 + deploy.md Railway 항목"
```

**완료 기준:**
- ✅ `python scripts/check_env_sync.py` exit 0
- ✅ deploy.md에 Railway env 체크 3항 추가

---

### Task 3: 자동 롤백 경고 배너 (API + UI)

**skill:** `frontend-design`

**Files:**
- Modify: `backend/api/routes/metrics.py` (기존 Sprint 2 라우터에 `/override-status` 엔드포인트 추가, ~15줄)
- Create: `frontend/components/diagnostics/override-banner.tsx` (신규, ~25줄)
- Modify: `frontend/app/(dashboard)/diagnostics/page.tsx` (배너 상단 배치, ~3줄)
- Modify: `frontend/lib/api.ts` (타입 + fetch 경로, ~5줄)

**Step 1: 백엔드**
```
GET /api/v1/metrics/override-status
→ {
    "is_active": bool,                       # triggered_at 존재 여부
    "triggered_at": str | null,
    "reason": str | null,
    "affected_keys": ["MIN_VOLUME_FLOOR_MODE", "SECONDARY_POOL_FALLBACK_ENABLED"],
  }
```
- Redis에서 `settings:override:triggered_at`, `reason`을 `resolve_override()` 로 조회
- 인증 의존성은 Sprint 1 metrics 라우터 패턴 동일

**Step 2: 프론트 배너 컴포넌트**
- Tailwind 기반 주황(경고) 배경 + ⚠️ 아이콘
- SWR 60초 폴링, `is_active=true`일 때만 렌더
- 문구: `"자동 롤백 발동 중 — {reason} ({triggered_at} KST). 관리자 확인 후 Redis key 수동 삭제 필요."`
- **색상 규약**: 한국 증시 색 관례 회피 (빨강/초록 금지) — 주황/호박색

**Step 3: 배치**
- `/diagnostics` 페이지 최상단 (카드들 위)

**Step 4: 검증**
- `cd frontend && npx tsc --noEmit`
- Redis에 수동으로 `SET settings:override:triggered_at ...` 후 배너 렌더 확인 (Playwright)

**Step 5: 커밋**
```
git add backend/api/routes/metrics.py \
  frontend/components/diagnostics/override-banner.tsx \
  frontend/app/\(dashboard\)/diagnostics/page.tsx frontend/lib/api.ts
git commit -m "feat(phase8.5-sprint2.5): task3 — 자동 롤백 발동 경고 배너 (API + UI)"
```

**완료 기준:**
- ✅ `/api/v1/metrics/override-status` 200
- ✅ 배너: `is_active=true`일 때만 렌더 + 주황색 경고
- ✅ `/diagnostics` 최상단 배치

---

### Task 4: fallback-stats 카드 롤백 상태 필드

**skill:** `frontend-design`

**Files:**
- Modify: `frontend/components/diagnostics/fallback-stats-card.tsx` (롤백 발동 시 카드 disabled + dimmed, ~10줄)

**Step 1: 변경**
- `override-status` SWR 구독
- `is_active=true`면 카드 내부에 "⚠️ 현재 자동 롤백 중 — 폴백 일시 비활성" 메시지 + opacity-50
- 폴백 통계 숫자는 계속 표시(과거 데이터 참조용)

**Step 2: 검증**
- Playwright 스크린샷 (롤백 중 / 정상 2가지 상태)
- `npx tsc --noEmit`

**Step 3: 커밋**
```
git add frontend/components/diagnostics/fallback-stats-card.tsx
git commit -m "feat(phase8.5-sprint2.5): task4 — fallback-stats 카드 롤백 상태 표시"
```

**완료 기준:**
- ✅ 롤백 활성 시 카드 dimmed + 명시적 메시지
- ✅ 통계 데이터 자체는 계속 가시

---

### Task 5: `phase8.md` Sprint 3 LIVE 게이트 DoD 재정의 반영

**Files:**
- Modify: `docs/phase/phase8/phase8.md` (Sprint 3 "LIVE 전환 게이트 기준" 섹션 교체, ~20줄)

**Step 1: 대상 식별**
- `phase8.md` Line 182~190 "LIVE 전환 게이트 기준" 표 — 원안 DoD ("신호 발생 3거래일 연속") 포함
- Phase 8.5 `phase8.5.md` Line 131~141의 D1~D7 재정의판을 이식

**Step 2: 교체 내용**
원안 표(5행):
```
| 1 | Paper 핫픽스 0건 | 5거래일 연속 |
| 2 | 신호 발생 | 3거래일 연속 (generate_signals 1건+) |
| 3 | 포지션 생명주기 완전 | 주문→체결→포지션→가격갱신→청산 1회+ 성공 |
| 4 | Sprint 1·2 전부 머지 | main 브랜치 반영 확인 |
| 5 | LIVE 초기 파라미터 적용 | 확정 파라미터 #17~#22 settings 테이블 반영 |
```

재정의판(7행 — D1~D7):
```
| D1 | Paper 5거래일 관찰 기간 | 필수 |
| D2 | 일평균 신호 발생 수 ≥ 1 | 5일 합 ≥ 5 |
| D3 | 신호 0건 일수 ≤ 2/5 | 0건 비율 ≤ 40% |
| D4 | tier 다양성 | 최소 2개 tier 각 1회+ (gap_open 필수 아님) |
| D5 | 손절 체결 경험 | 최소 1회 |
| D6 | Paper 핫픽스 0건 | 유지 (원안 D1 계승) |
| D7 | 신호 0건 3거래일 연속 | 자동 중단 + 재검토 트리거 |
```

**Step 3: 각주 추가**
- 표 아래: `> 재정의 근거: Phase 8.5 phase8.5.md Line 131~141 (2026-04-22 전문가 4명 합의). "3거래일 연속" 원안은 2차 스크리닝 교차 단절 구조에서 논리적 달성 불가로 폐기.`

**Step 4: 커밋**
```
git add docs/phase/phase8/phase8.md
git commit -m "docs(phase8.5-sprint2.5): task5 — phase8 Sprint3 LIVE 게이트 DoD D1~D7 재정의 반영"
```

**완료 기준:**
- ✅ phase8.md에 D1~D7 재정의판 반영
- ✅ 원안 DoD 흔적 제거 (혼선 방지)
- ✅ 재정의 근거 각주 존재

---

### Task 6: 통합 검증 + 관찰 의사결정 트리 확증 + 마무리

**skill:** `verification-before-completion`

**Step 1: 통합 검증**
- `docker compose exec backend pytest -v` (전체)
- `docker compose exec backend pytest tests/core/test_settings_override.py tests/test_momentum_breakout.py tests/test_realtime_screener.py tests/test_scheduler.py -v`
- API curl:
  - `curl -s http://localhost:8000/api/v1/metrics/override-status | jq`
  - `curl -s http://localhost:8000/api/v1/metrics/fallback-stats | jq`
- `cd frontend && npx tsc --noEmit`
- Playwright `/diagnostics` 스크린샷 — 배너 미렌더 정상 상태 1장
- (선택) Redis에 `SET settings:override:triggered_at` + `reason` 수동 입력 → 배너 렌더 스크린샷 1장

**Step 2: 본 sprint2.5.md 하단 의사결정 트리 섹션 존재 확증**
- 아래 "## 5거래일 관찰 종료 후 의사결정 트리" 섹션이 본 문서에 존재하는지 확인
- 누락 시 Task 6에서 보강

**Step 3: deploy.md 업데이트**
- 현 Sprint 2.5 검증 결과 섹션 추가
- Sprint 2 검증 플레이스홀더(있다면) 교체는 범위 외

**Step 4: 커밋 + sprint-close 안내**
```
git add docs/phase/phase8.5/sprint2.5/sprint2.5.md deploy.md
git commit -m "chore(phase8.5-sprint2.5): task6 — 통합 검증 결과 + 의사결정 트리 확증"
```

마지막에 사용자에게 안내:
```
Sprint 2.5 구현 완료. sprint-close agent로 마무리(PR to develop)합니다.
```

**완료 기준:**
- ✅ pytest 전체 GREEN (신규 실패 0건, 기존 플레이크 허용)
- ✅ tsc --noEmit GREEN
- ✅ API curl 2종 200
- ✅ Playwright 스크린샷 1~2장 확보
- ✅ deploy.md에 Sprint 2.5 섹션 추가

---

## 5거래일 관찰 종료 후 의사결정 트리

Phase 8.5 Sprint 2 배포일(2026-04-23) + 5거래일 관찰 종료 시점에, 다음 지표를 근거로 분기를 결정한다. **본 Sprint 2.5는 관찰 지표를 바꾸지 않는다** — Phase 8.5 DoD 그대로 사용.

### 관찰 지표 (수집 원천: Sprint 1·2 구축 메트릭)

| 지표 | 원천 | 임계 |
|------|------|------|
| M-S1: 5일 신호 합 | `trade_signals` COUNT(5일) | ≥ 5이면 양호 |
| M-S2: 0건 일수 | signal=0 인 거래일 수 | ≤ 2/5이면 양호 |
| M-S3: tier 다양성 | distinct `factors.tier` 5일 누적 | ≥ 2종이면 양호 |
| M-F1: 폴백 발동 일수 | `metrics:fallback:triggered:{date}` > 0 일수 | 정보용 |
| M-F2: 폴백 종목 신호 발생율 | `signals from fallback / fallback pool` | < 5%면 주의 |
| M-R: 자동 롤백 발동 여부 | `settings:override:triggered_at` 존재 | 있으면 분기 D로 강제 |

### 분기

```
5거래일 관찰 종료
│
├─ 자동 롤백 발동? ──YES──> 분기 D (legacy 모드 유지 + Phase 10.1 선제 착수 검토)
│   NO
│
├─ M-S1 ≥ 5 AND M-S2 ≤ 2 AND M-S3 ≥ 2?
│   │
│   YES ──> 분기 A: Phase 8.6 Sprint 1 (E2E + LIVE 게이트) 즉시 착수
│   │       · DoD 재정의판(D1~D7) 기준으로 착수
│   │       · LIVE 초기 파라미터 #17~#22 적용
│   │
│   NO (부분 충족)
│   │
│   ├─ M-S1 ∈ [2, 4] OR (M-S2 = 3): 분기 B (보완 관측 +3거래일)
│   │       · 파라미터 변경 없이 관측만 연장
│   │       · 연장 후 재평가 (최대 1회 연장)
│   │       · 3회차에도 미충족이면 분기 C로 전환
│   │
│   └─ M-S1 < 2 AND M-S2 ≥ 4: 분기 C (Phase 10.1 하이브리드 착수 검토)
│           · Phase 8.5 효과 부재 확증 → MVP 이상 필요
│           · Phase 10.1 선결 조건 재검토 (데이터 축적 상태 점검)
│           · 전문가 4명 재검토 필수
│
└─ M-F2 < 5% (폴백 품질 불량) ──> 분기 E (폴백 비활성 override + 원인 분석)
    · `SECONDARY_POOL_FALLBACK_ENABLED=False` Redis override 설정
    · 파라미터 값 변경은 별도 Sprint 필요 (본 트리에서는 금지)
```

### 분기 A~E 요약표

| 분기 | 조건 | 즉시 조치 | 다음 Sprint |
|------|------|----------|-------------|
| A | 전원 양호 | LIVE 게이트 착수 | Phase 8.6 Sprint 1 |
| B | 부분 충족 | 관측 연장(+3거래일, 최대 1회) | 재평가 후 A 또는 C |
| C | 신호 부족 지속 | Phase 10.1 선결조건 재검토 | Phase 10.1 Sprint 0 (전문가 재검토) |
| D | 자동 롤백 발동 | legacy 고정 유지 + 원인 분석 | Phase 10.1 검토 병행 |
| E | 폴백 품질 불량 | Redis override로 폴백 차단 | 폴백 재설계 Sprint (별도 계획) |

### 분기 결정 권한

- 분기 A / B: 개발자 단독 판단 가능
- 분기 C / D / E: **전문가 4명(PO/리스크/퀀트/단타) 재리뷰 필수** — 파라미터·순서 변경 여부는 리뷰 결과로 결정

---

## 미해결 사항 / 리스크

### ⚠️ 리스크

1. **`resolve_override` 통합 시 성능 리스크** — 매 신호 평가마다 Redis GET 호출
   - 완화: Sprint 2 Task 5에서 이미 매 평가 시 GET하던 경로를 대체하는 것뿐, 신규 호출 추가 아님
2. **override 경로 버그 시 무음 실패 가능성**
   - 완화: `resolve_override`가 예외 시 default 반환 + `logger.warning` 기록 (Task 1 Step 1 참조)
3. **배너 UI가 관리자 Telegram 확인을 대체한다고 오해될 수 있음**
   - 완화: 배너 문구에 "Telegram과 병행 — 관리자 확인 후 수동 삭제 필요" 명시

### ❌ 이번 Sprint에서 하지 않는 것 (재명시)

- 파라미터 수치 변경 일체 (확정 #1~#26 전부 불변)
- 관찰 기간 5거래일 단축
- `ATR_FILTER_PCT` 등 전략 필터 수치 조정
- DB 스키마 변경 / Alembic 마이그레이션
- 신규 pip/npm 의존성

### 🤔 사용자 최종 결정 필요 항목

- **없음** — 본 Sprint는 Sprint 2에서 확정된 설계를 인프라·문서 수준에서 지지하는 작업만 포함. 파라미터 결정 사항 없음.

---

## 완료 기준 (Sprint 2.5 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| `core/settings_override.py::resolve_override` 통합 유틸 배포 | 3개 호출부 경유 | ⬜ |
| Sprint 2 행동 동일성 회귀 GREEN | 기존 테스트 전원 PASS | ⬜ |
| env 동기화 체크 스크립트 + deploy.md 항목 | `scripts/check_env_sync.py` exit 0 | ⬜ |
| 자동 롤백 경고 배너 (API + UI) | `/override-status` 200 + 배너 조건부 렌더 | ⬜ |
| fallback-stats 카드 롤백 상태 표시 | 롤백 중 dimmed + 메시지 | ⬜ |
| `phase8.md` Sprint 3 DoD D1~D7 재정의 반영 | 원안 폐기 각주 포함 | ⬜ |
| 5거래일 관찰 의사결정 트리 문서화 | sprint2.5.md 하단 분기 A~E | ✅ (본 문서) |
| pytest 전체 통과 | 신규 실패 0건 | ⬜ |
| tsc --noEmit 통과 | — | ⬜ |
| `SETTINGS_OVERRIDE_ENABLED=True` Railway 반영 확인 | deploy.md 체크 | ⬜ |

완료 후 sprint-close agent 호출 → `phase8.5-sprint2.5` → develop PR 생성.
