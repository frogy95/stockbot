# Sprint 2: 신호/스크리닝/설정 + 웹 매매 승인 (Phase 4)

**Goal:** 매매 신호(웹 승인/거부+카운트다운), 스크리닝, 매매 이력, 성과 분석(기본), 설정(모드전환+리스크잠금) 페이지와 백엔드 API(웹 승인+모드전환+감사로그)를 구현하여 MVP를 완성한다.

**Architecture:** 백엔드에 웹 승인/거부 API, 모드 전환 보호 API(이중 확인+장중 차단+포지션 체크), 감사 로그 모델/API를 추가한다. 프론트엔드에 5개 페이지(신호/스크리닝/이력/분석/설정)를 구축하며, 신호 페이지는 승인 대기 시 3초 폴링+카운트다운 프로그레스 바를 제공한다. 기존 ApprovalManager의 일회용 토큰으로 텔레그램/웹 동시 승인 경쟁을 방지한다.

**Tech Stack:** Next.js 16 (App Router) + React 19 + shadcn/ui + SWR + Tailwind CSS 4 + PyJWT + FastAPI + Alembic

**Sprint 기간:** 2026-03-31 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 4 Sprint 1 (대시보드 기본 구조 + 핵심 페이지, PR #36)
**브랜치명:** `phase4-sprint2`

---

## 제외 범위

- 수익률 차트, 샤프비율, MDD 등 고급 성과 분석 (Phase 5)
- 모바일 반응형 (Phase 6)
- 라이트 모드 (미지원, 다크 모드 전용)
- Playwright E2E 테스트 (sprint-review에서 수행)
- SSE/WebSocket 실시간 푸시 (폴링 확정)

## 실행 플랜

의존성 그래프: 백엔드 API(웹 승인+모드전환+감사로그)가 프론트엔드 페이지보다 선행. 감사 로그 모델은 모드 전환 API의 전제. 프론트엔드 5개 페이지는 파일 소유권이 겹치지 않아 병렬 가능하나, 신호 페이지가 승인 API에 의존하므로 백엔드 완성 후 진행.

### Phase 1 (순차 -- 백엔드 감사로그 + 승인 + 모드전환)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | 감사 로그 모델 + 마이그레이션 | 백엔드 | -- |
| Task 2 | 웹 승인/거부 API + 대기 신호 조회 | 백엔드 | -- |
| Task 3 | 모드 전환 보호 API + 감사 로그 기록 | 백엔드 | -- |

### Phase 2 (병렬 가능 -- 프론트엔드 5개 페이지)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 매매 신호 페이지 (승인 카드 + 카운트다운) | 프론트엔드 | `frontend-design` |
| Task 5 | 스크리닝 페이지 (1차/2차 탭) | 프론트엔드 | `frontend-design` |
| Task 6 | 매매 이력 페이지 (날짜 필터) | 프론트엔드 | `frontend-design` |
| Task 7 | 성과 분석 페이지 (기본 일별 손익 테이블) | 프론트엔드 | `frontend-design` |
| Task 8 | 설정 페이지 (모드 전환 + 리스크 잠금) | 프론트엔드 | `frontend-design` |

### Phase 3 (순차 -- 통합 검증)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 9 | 통합 테스트 + 회귀 검증 | 전체 | -- |

> **팀 실행**: "Phase 2를 팀으로 실행해줘"라고 요청하면 백엔드/프론트엔드 팀원이 각 Task를 병렬 구현합니다.

---

### Task 1: 감사 로그 모델 + 마이그레이션

**Files:**
- Create: `backend/core/models/audit_log.py`
- Modify: `backend/core/models/__init__.py` (AuditLog import 추가)
- Create: `backend/alembic/versions/{자동생성}_add_audit_log.py`
- Test: `backend/tests/test_audit_log.py`

**Step 1: 테스트 작성**
- `backend/tests/test_audit_log.py` 생성
- 테스트 케이스:
  - AuditLog 레코드 생성 -- action, target_key, old_value, new_value, actor, ip_address 필드 저장 확인
  - created_at 자동 생성 확인
- 검증: `docker compose exec backend pytest tests/test_audit_log.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: AuditLog 모델 구현**
- `backend/core/models/audit_log.py` 생성
  - 테이블명: `audit_logs`
  - 컬럼: id(PK), action(String(50), "mode_switch"/"setting_update" 등), target_key(String(100), 변경 대상 키), old_value(Text, 이전 값), new_value(Text, 새 값), actor(String(50), "admin"), ip_address(String(45), IPv6 대응), created_at(DateTime, server_default)
- `backend/core/models/__init__.py`에 `from core.models.audit_log import AuditLog` 추가
- 검증: `docker compose exec backend python -c "from core.models.audit_log import AuditLog; print(AuditLog.__tablename__)"`
- 예상: `audit_logs`

**Step 3: Alembic 마이그레이션**
- `docker compose exec backend alembic revision --autogenerate -m "add audit_log table"`
- `docker compose exec backend alembic upgrade head`
- 검증: `docker compose exec backend alembic current`
- 예상: 최신 리비전 표시, audit_logs 테이블 생성됨

**Step 4: 테스트 통과 확인**
- 검증: `docker compose exec backend pytest tests/test_audit_log.py -v`
- 예상: PASS

**Step 5: 커밋**
```
git add backend/core/models/audit_log.py backend/core/models/__init__.py backend/alembic/versions/ backend/tests/test_audit_log.py
git commit -m "feat(phase4-sprint2): task1 -- 감사 로그 모델 + 마이그레이션"
```

**완료 기준:**
- ⬜ AuditLog 모델 테스트 통과
- ⬜ alembic upgrade head 성공

---

### Task 2: 웹 승인/거부 API + 대기 신호 조회

**Files:**
- Modify: `backend/api/routes/trading.py` (웹 승인/거부 엔드포인트 2개 추가, 대기 신호 목록 엔드포인트 추가)
- Test: `backend/tests/test_web_approval.py`

**Step 1: 테스트 작성**
- `backend/tests/test_web_approval.py` 생성
- 테스트 케이스:
  - `POST /api/v1/trading/signals/{token}/approve` -- 유효 토큰 -> 200 + 주문 실행
  - `POST /api/v1/trading/signals/{token}/reject` -- 유효 토큰 -> 200 + 거부 처리
  - `POST /api/v1/trading/signals/{token}/approve` -- 만료/사용된 토큰 -> 404
  - `GET /api/v1/trading/signals/pending` -- 승인 대기 신호 목록 (Redis approval:* 키에서 조회)
  - `GET /api/v1/trading/signals/pending` -- pending_count 포함 (ApprovalManager.get_pending_count 활용)
- 검증: `docker compose exec backend pytest tests/test_web_approval.py -v`
- 예상: FAIL (엔드포인트 미존재)

**Step 2: 대기 신호 목록 엔드포인트 구현**
- `backend/api/routes/trading.py`에 추가:
  - `GET /signals/pending` -- Redis에서 `approval:*` 키를 조회하여 대기 중인 신호 데이터 반환
  - ApprovalManager를 `request.app.state.approval_manager`에서 가져옴 (없으면 빈 결과)
  - 응답: `{ "pending": [...신호데이터], "count": N }`
  - 각 항목에 token, signal(stock_code, signal_type, confidence, entry_price, stop_loss, take_profit, strategy_name), quantity, created_at(TTL 역산), expires_in_sec(TTL 잔여) 포함
- 검증: `docker compose exec backend pytest tests/test_web_approval.py::test_get_pending -v`
- 예상: PASS

**Step 3: 승인/거부 엔드포인트 구현**
- `backend/api/routes/trading.py`에 추가:
  - `POST /signals/{token}/approve` -- TradingEngine.approve_signal(token) 호출
  - `POST /signals/{token}/reject` -- TradingEngine.reject_signal(token) 호출
  - TradingEngine은 `request.app.state.trading_engine`에서 가져옴
  - 성공 시 200 + `{ "result": "approved"/"rejected" }`, 실패(만료/사용) 시 404
- 검증: `docker compose exec backend pytest tests/test_web_approval.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/api/routes/trading.py backend/tests/test_web_approval.py
git commit -m "feat(phase4-sprint2): task2 -- 웹 승인/거부 API + 대기 신호 조회"
```

**완료 기준:**
- ⬜ 승인/거부 API 테스트 통과
- ⬜ 대기 신호 조회 API 동작 확인

---

### Task 3: 모드 전환 보호 API + 감사 로그 기록

**Files:**
- Modify: `backend/api/routes/settings.py` (인증 의존성 추가, 모드 전환 API, 장중 잠금 체크, 감사 로그)
- Create: `backend/api/routes/audit.py` (감사 로그 조회 API)
- Modify: `backend/main.py` (audit 라우터 등록)
- Test: `backend/tests/test_mode_switch.py`

**Step 1: 테스트 작성**
- `backend/tests/test_mode_switch.py` 생성
- 테스트 케이스:
  - `PUT /api/v1/settings/trading_env` + 비밀번호 확인 -> 200 + 환경 전환
  - `PUT /api/v1/settings/trading_env` + 잘못된 비밀번호 -> 403
  - `PUT /api/v1/settings/trading_env` + 장중(09:00~15:30) 시간대 -> 423 (Locked)
  - `PUT /api/v1/settings/trading_env` + 활성 포지션 존재 -> 409 (Conflict)
  - 전환 후 audit_logs 테이블에 기록 존재 확인
  - `PUT /api/v1/settings/{risk_key}` + 장중 + risk_lock_during_trading=true -> 423
  - `GET /api/v1/audit/logs` -> 최근 감사 로그 목록
- 검증: `docker compose exec backend pytest tests/test_mode_switch.py -v`
- 예상: FAIL (엔드포인트 미존재)

**Step 2: settings.py에 인증 + 모드 전환 보호 구현**
- `backend/api/routes/settings.py` 수정:
  - 라우터에 `dependencies=[Depends(get_current_user)]` 추가
  - `PUT /settings/mode` 엔드포인트 신규 추가:
    - 요청: `{ "target_env": "live"|"paper", "password": "..." }`
    - 비밀번호 재확인: `settings.ADMIN_PASSWORD`와 비교 -> 불일치 시 403
    - 장중 차단: 현재 KST 시각이 09:00~15:30이면 423 반환 (메시지: "장중에는 모드를 전환할 수 없습니다")
    - 포지션 체크: PositionRecord 테이블에 레코드가 있으면 409 반환 (메시지: "활성 포지션이 있어 전환할 수 없습니다")
    - 통과 시: trading_env 설정값 업데이트 + AuditLog 생성
    - 응답: `{ "trading_env": "live", "switched_at": "..." }`
  - 기존 `PUT /settings/{key}` 수정:
    - 카테고리가 "risk"이고, 현재 장중이고, risk_lock_during_trading=true이면 423 반환
    - 변경 시 AuditLog 생성 (action="setting_update", target_key=key, old_value, new_value)
- 검증: `docker compose exec backend pytest tests/test_mode_switch.py -v`
- 예상: PASS (일부)

**Step 3: 감사 로그 조회 API 구현**
- `backend/api/routes/audit.py` 생성:
  - `GET /audit/logs` -- 최근 100건 감사 로그 (최신순 정렬)
  - 쿼리 파라미터: action(선택), limit(기본 100, 최대 500)
  - 인증 필수: `dependencies=[Depends(get_current_user)]`
- `backend/main.py`에 audit 라우터 import + `app.include_router(audit_router, prefix="/api/v1")` 추가
- 검증: `docker compose exec backend pytest tests/test_mode_switch.py -v`
- 예상: 전체 PASS

**Step 4: 커밋**
```
git add backend/api/routes/settings.py backend/api/routes/audit.py backend/main.py backend/tests/test_mode_switch.py
git commit -m "feat(phase4-sprint2): task3 -- 모드 전환 보호 API + 감사 로그"
```

**완료 기준:**
- ⬜ 모드 전환 보호 테스트 통과 (비밀번호/장중/포지션 3중 체크)
- ⬜ 리스크 설정 장중 잠금 동작 확인
- ⬜ 감사 로그 조회 API 동작 확인

---

### Task 4: 매매 신호 페이지 (승인 카드 + 카운트다운)

**skill:** `frontend-design`

**Files:**
- Create: `frontend/app/(dashboard)/signals/page.tsx`
- Create: `frontend/components/signals/approval-card.tsx`
- Modify: `frontend/lib/api.ts` (apiPut 추가 -- 설정 업데이트용)
- Modify: `frontend/lib/hooks/use-polling.ts` (동적 interval 지원)

**Step 1: API 유틸 + 동적 폴링 확장**
- `frontend/lib/api.ts`에 `apiPut<T>(path, body)` 함수 추가 (기존 apiPost 패턴 동일, method: "PUT")
- `frontend/lib/hooks/use-polling.ts` 수정: intervalMs 파라미터를 함수로도 받을 수 있게 확장 (예: `(data) => hasPending ? 3000 : 5000`)
  - SWR의 refreshInterval에 콜백 반환값 전달
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 에러 없음

**Step 2: 승인 카드 컴포넌트 구현**
- `frontend/components/signals/approval-card.tsx` 생성 ("use client"):
  - Props: token, signal(stock_code, signal_type, confidence, entry_price, stop_loss, take_profit, strategy_name), quantity, expires_in_sec
  - 표시: 종목명(stock_code) + 방향(BUY/SELL 배지) + 신뢰도(%) + 진입가 + 손절가 + 익절가 + 수량
  - 카운트다운: expires_in_sec에서 1초씩 감소하는 프로그레스 바 + "N초 남음" 텍스트
  - 승인 버튼(빨강): `POST /api/v1/trading/signals/{token}/approve` 호출 후 mutate
  - 거부 버튼(파랑): `POST /api/v1/trading/signals/{token}/reject` 호출 후 mutate
  - 버튼 클릭 후 loading 상태 표시, 중복 클릭 방지
  - 카운트다운 0 도달 시 카드 비활성화 + "시간 초과" 표시
- shadcn/ui 컴포넌트 사용: Card, Badge, Button
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 에러 없음

**Step 3: 신호 페이지 구현**
- `frontend/app/(dashboard)/signals/page.tsx` 생성 ("use client"):
  - 상단: 오늘 날짜 표시 + 대기 N건 배지 (pending_count)
  - 승인 대기 섹션: `GET /api/v1/trading/signals/pending` 폴링 (대기 있으면 3초, 없으면 5초)
    - ApprovalCard 컴포넌트 카드 그리드로 렌더링
    - 대기 없으면 "대기 중인 신호가 없습니다" 메시지
  - 오늘 신호 이력 섹션: `GET /api/v1/trading/signals?target_date={today}` 폴링 5초
    - 테이블: 시각, 종목코드, 방향, 신뢰도, 진입가, 상태(approved/rejected/expired/pending)
    - 상태별 배지 색상: approved=초록, rejected=빨강, expired=회색, pending=노랑
  - 브라우저 탭 제목: 대기 N건이면 `(N) StockBot` (document.title 동적 변경)
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 에러 없음

**Step 4: 커밋**
```
git add frontend/app/\(dashboard\)/signals/ frontend/components/signals/ frontend/lib/api.ts frontend/lib/hooks/use-polling.ts
git commit -m "feat(phase4-sprint2): task4 -- 매매 신호 페이지 + 승인 카드 + 카운트다운"
```

**완료 기준:**
- ⬜ tsc 타입 체크 통과
- ⬜ 승인 카드 카운트다운 프로그레스 바 동작
- ⬜ 대기 신호 유무에 따른 폴링 주기 전환 (3초/5초)
- ⬜ 탭 제목 "(N) StockBot" 동적 변경

---

### Task 5: 스크리닝 페이지 (1차/2차 탭)

**skill:** `frontend-design`

**Files:**
- Create: `frontend/app/(dashboard)/screening/page.tsx`

**Step 1: 스크리닝 페이지 구현**
- `frontend/app/(dashboard)/screening/page.tsx` 생성 ("use client"):
  - 탭 UI: "1차 스크리닝" / "2차 스크리닝" 탭 (shadcn/ui 없으면 커스텀 탭)
  - 1차 탭: `GET /api/v1/screening/primary` 데이터 표시
    - 테이블 컬럼: 순위, 종목코드, 점수, 핫 여부(불꽃 아이콘), 상태, 팩터(JSONB -> 키별 배지)
    - 스크리닝 시각 표시 (screened_at)
    - 총 N건 카운트
  - 2차 탭: `GET /api/v1/screening/secondary` 동일 구조
  - 폴링: 5초 기본 (usePolling 사용)
  - 빈 상태: "스크리닝 결과가 없습니다" 메시지
  - 수동 트리거 버튼: `POST /api/v1/screening/trigger/primary` (or secondary) 호출
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 에러 없음

**Step 2: 커밋**
```
git add frontend/app/\(dashboard\)/screening/
git commit -m "feat(phase4-sprint2): task5 -- 스크리닝 페이지 (1차/2차 탭)"
```

**완료 기준:**
- ⬜ tsc 타입 체크 통과
- ⬜ 1차/2차 탭 전환 + 데이터 표시

---

### Task 6: 매매 이력 페이지 (날짜 필터)

**skill:** `frontend-design`

**Files:**
- Create: `frontend/app/(dashboard)/history/page.tsx`

**Step 1: 매매 이력 페이지 구현**
- `frontend/app/(dashboard)/history/page.tsx` 생성 ("use client"):
  - 상단: 날짜 선택 (input type="date", 기본값 오늘)
  - 테이블: `GET /api/v1/trading/history?target_date={date}` 데이터 표시
    - 컬럼: 종목코드, 전략, 진입가, 청산가, 수량, 실현손익(색상: 빨강=수익, 파랑=손실), 수익률(%), 보유시간, 청산사유, 진입시각, 청산시각
    - 실현손익과 수익률에 getPnlColor 적용
  - 하단 합계: 총 거래 건수, 총 실현손익, 평균 수익률
  - 빈 상태: "해당 날짜의 매매 이력이 없습니다"
  - 폴링: 5초 (오늘 날짜일 때만)
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 에러 없음

**Step 2: 커밋**
```
git add frontend/app/\(dashboard\)/history/
git commit -m "feat(phase4-sprint2): task6 -- 매매 이력 페이지 (날짜 필터)"
```

**완료 기준:**
- ⬜ tsc 타입 체크 통과
- ⬜ 날짜 변경 시 이력 테이블 갱신
- ⬜ 손익 색상 한국 관례 적용 (빨강=수익, 파랑=손실)

---

### Task 7: 성과 분석 페이지 (기본 일별 손익 테이블)

**skill:** `frontend-design`

**Files:**
- Create: `frontend/app/(dashboard)/analytics/page.tsx`

**Step 1: 성과 분석 페이지 구현**
- `frontend/app/(dashboard)/analytics/page.tsx` 생성 ("use client"):
  - 범위: Phase 4에서는 **기본 일별 손익 테이블만** (차트/샤프비율/MDD는 Phase 5)
  - 최근 30일 기간 선택 (시작일~종료일 input)
  - 각 날짜별로 `GET /api/v1/trading/history?target_date={date}` 호출하여 일별 집계
    - 단, 매번 30개 요청은 비효율 -> 프론트엔드에서 첫 로드 시 순차 호출 후 캐시
  - 테이블 컬럼: 날짜, 거래 건수, 총 실현손익, 평균 수익률, 최대 수익, 최대 손실
  - 실현손익에 getPnlColor 적용
  - 하단 기간 합계: 총 거래 건수, 누적 손익, 평균 수익률
  - 빈 상태: "해당 기간의 매매 데이터가 없습니다"
  - 폴링: 없음 (수동 새로고침 버튼)
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 에러 없음

**Step 2: 커밋**
```
git add frontend/app/\(dashboard\)/analytics/
git commit -m "feat(phase4-sprint2): task7 -- 성과 분석 페이지 (기본 일별 손익 테이블)"
```

**완료 기준:**
- ⬜ tsc 타입 체크 통과
- ⬜ 일별 손익 테이블 표시 + 기간 합계

---

### Task 8: 설정 페이지 (모드 전환 + 리스크 잠금)

**skill:** `frontend-design`

**Files:**
- Create: `frontend/app/(dashboard)/settings/page.tsx`
- Create: `frontend/components/settings/mode-switch.tsx`

**Step 1: 모드 전환 컴포넌트 구현**
- `frontend/components/settings/mode-switch.tsx` 생성 ("use client"):
  - 현재 모드 표시: PAPER(초록 배지) / LIVE(빨강 배지)
  - 전환 버튼 클릭 시 이중 확인 모달 (shadcn/ui Dialog 사용):
    - 1단계: "모의 -> 실전으로 전환하시겠습니까?" 확인 메시지
    - 2단계: 비밀번호 재입력 필드
    - 확인 버튼 클릭 -> `PUT /api/v1/settings/mode` 호출
  - 에러 처리:
    - 423: "장중(09:00~15:30)에는 모드를 전환할 수 없습니다" 토스트
    - 409: "활성 포지션이 있어 전환할 수 없습니다" 토스트
    - 403: "비밀번호가 올바르지 않습니다" 토스트
  - 성공 시 AuthProvider의 user.trading_env 갱신 (JWT 재발급 or 수동 상태 업데이트)
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 에러 없음

**Step 2: 설정 페이지 구현**
- `frontend/app/(dashboard)/settings/page.tsx` 생성 ("use client"):
  - 섹션 1 -- 거래 모드:
    - ModeSwitchComponent 렌더링
    - 현재 모드 + 전환 버튼
  - 섹션 2 -- 리스크 설정:
    - `GET /api/v1/settings?category=risk` 데이터 표시
    - 각 설정: 키, 현재 값, 설명 + 수정 버튼
    - 장중이면 수정 비활성화 + "장중 잠금" 배지 표시 (risk_lock_during_trading=true 확인)
    - 수정: 인라인 편집 -> `PUT /api/v1/settings/{key}` 호출
    - 장중 잠금 상태는 현재 KST 시각으로 클라이언트 판단 (09:00~15:30)
  - 섹션 3 -- 매매 설정:
    - `GET /api/v1/settings?category=trading` 데이터 표시
    - 동일한 인라인 편집 패턴
  - 섹션 4 -- 감사 로그:
    - `GET /api/v1/audit/logs?limit=20` 최근 변경 이력 테이블
    - 컬럼: 시각, 액션, 대상, 이전값, 새값, 사용자
  - 폴링: 없음 (수동 새로고침)
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 에러 없음

**Step 3: 커밋**
```
git add frontend/app/\(dashboard\)/settings/ frontend/components/settings/
git commit -m "feat(phase4-sprint2): task8 -- 설정 페이지 + 모드 전환 (이중 확인 모달)"
```

**완료 기준:**
- ⬜ tsc 타입 체크 통과
- ⬜ 모드 전환 이중 확인 모달 동작
- ⬜ 리스크 설정 장중 잠금 UI 표시
- ⬜ 감사 로그 테이블 표시

---

### Task 9: 통합 테스트 + 회귀 검증

**Files:**
- (기존 파일 검증만, 신규 파일 없음)

**Step 1: 백엔드 전체 테스트**
- 검증: `docker compose exec backend pytest -v`
- 예상: 기존 + 신규 테스트 전체 PASS

**Step 2: 프론트엔드 타입 체크**
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 에러 없음

**Step 3: 프론트엔드 빌드 체크**
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npm run build`
- 예상: 성공

**Step 4: 수동 검증 체크리스트**
- ⬜ 로그인 -> 대시보드 진입
- ⬜ 사이드바 8개 메뉴 모두 접근 가능
- ⬜ 매매 신호 페이지: 승인 대기 카드 표시 (테스트 데이터 필요)
- ⬜ 스크리닝 페이지: 1차/2차 탭 전환 + 데이터 표시
- ⬜ 매매 이력 페이지: 날짜 필터 동작
- ⬜ 성과 분석 페이지: 일별 손익 테이블
- ⬜ 설정 페이지: 모드 전환 이중 확인 모달
- ⬜ 설정 페이지: 리스크 설정 장중 잠금 표시
- ⬜ 기존 페이지 회귀 없음 (대시보드/포지션/주문)

**Step 5: 커밋**
```
git add .
git commit -m "feat(phase4-sprint2): task9 -- 통합 테스트 + 회귀 검증 완료"
```

**완료 기준:**
- ⬜ pytest 전체 PASS
- ⬜ tsc 타입 체크 통과
- ⬜ npm run build 성공
- ⬜ 8개 페이지 모두 접근 가능

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 기존 + 신규 전체 passed |
| 프론트 타입체크 | `cd frontend && npx tsc --noEmit` | 에러 없음 |
| 프론트 빌드 | `cd frontend && npm run build` | 성공 |
| 웹 승인 API | `curl -s -X POST http://localhost:8000/api/v1/trading/signals/{token}/approve -H "Authorization: Bearer {jwt}" -H "Content-Type: application/json"` | 200 or 404 |
| 모드 전환 API | `curl -s -X PUT http://localhost:8000/api/v1/settings/mode -H "Authorization: Bearer {jwt}" -H "Content-Type: application/json" -d '{"target_env":"live","password":"..."}'` | 200 or 423/409/403 |
| 감사 로그 API | `curl -s http://localhost:8000/api/v1/audit/logs -H "Authorization: Bearer {jwt}"` | 200 + JSON 배열 |
| 대기 신호 API | `curl -s http://localhost:8000/api/v1/trading/signals/pending -H "Authorization: Bearer {jwt}"` | 200 + pending 배열 |
