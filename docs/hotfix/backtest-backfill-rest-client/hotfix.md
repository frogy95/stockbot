# Hotfix: backfill-daily KISRestClient 주입 수정 (TypeError → 백필 실패)

**브랜치:** `hotfix/backtest-backfill-rest-client`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-05-08
**PR:** https://github.com/frogy95/stockbot/pull/217 (MERGED)
**머지 커밋:** `9d1e704fcdeef7a48b52d425fce195a695c31de0`

---

## 문제 분석

### 증상

`POST /api/v1/backtest/backfill-daily` 요청 시 202 응답 반환 후 백그라운드 태스크가 즉시 TypeError로 실패. KOSPI200 일봉 데이터 백필이 전혀 이루어지지 않음.

### 원인

`backend/modules/backtest/historical_loader.py:185`에서 `KISRestClient()` 무인자 호출. `KISRestClient`는 `env`, `token_manager`, `throttler` required 의존성을 생성자 인자로 요구하는 클래스로, 무인자 호출 시 TypeError 발생.

운영 시 `main.py lifespan`에서 `app.state.kis_inquiry`에 완전히 초기화된 클라이언트가 주입되므로, backfill도 동일 클라이언트를 재사용해야 한다.

### 영향 범위

- `POST /api/v1/backtest/backfill-daily` 엔드포인트 (백필 트리거 API)
- KOSPI200 200종 × 일봉 데이터 백필 전체 불가
- Walk-forward 백테스트 데이터 준비 단계 실패

---

## 수정 내용

### 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/backtest/historical_loader.py` | `backfill_missing_daily(rest_client=...)` 인자 추가, None 시 ValueError 조기 차단 |
| `backend/api/routes/backtest.py` | `_run_backfill(rest_client, ...)` 시그니처 변경, `backfill_daily` 엔드포인트가 `Request` 받아 `app.state.kis_inquiry` 주입, 부재 시 503 반환 |
| `backend/tests/api/test_backtest_routes.py` | 회귀 테스트 2종 추가 (`test_backfill_daily_returns_running` 보강, `test_backfill_daily_503_when_kis_inquiry_missing` 신규) |

### 커밋 이력

| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `3422895` | `fix(backtest): backfill-daily 가 app.state.kis_inquiry 주입받도록 수정` | 2026-05-08 |

---

## 검증

### 자동 검증

- ✅ pytest `tests/api/test_backtest_routes.py`: 12종 통과 (0 failed)
  - `test_backfill_daily_returns_running`: rest_client가 app.state.kis_inquiry로 전달됨 확인
  - `test_backfill_daily_503_when_kis_inquiry_missing`: kis_inquiry 미설정 시 503 정상 반환
- ✅ pytest backfill/historical_loader 관련 14종 전체 통과
- ✅ 헬스체크: `{"status":"healthy","database":"connected","redis":"connected"}`

### 프로덕션 검증 (배포 후 확인)

- ✅ `POST /api/v1/backtest/backfill-daily` 202 응답 정상 (이전엔 즉시 TypeError)
- ✅ 백그라운드 백필 작동 확인 (KIS API 호출 진행 중)
- KOSPI200 200종 × 90거래일 완전 백필은 수 시간 소요 — 매주 월 00:00 KST 정규 잡이 자체 처리하는 설계

### 수동 검증

- ⬜ `docker compose up --build` (코드 반영)

---

## 코드 리뷰 결과 (경량)

- Critical/High 이슈: 0건
- 수정 범위: 파일 3개, 코드 약 40줄 (Hotfix 기준 충족)
- `None` 시 ValueError 조기 차단 패턴 적절 (Fail Fast)
- `getattr(request.app.state, "kis_inquiry", None)` 방어 코드 적절
- 503 반환 + 회귀 테스트 2종 추가로 회귀 방지 확보
