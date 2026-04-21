# Hotfix: 일일 리스크 카운터 자동 리셋 누락 + 수동 리셋 API 추가

## 배경

2026-04-21 장중 관찰 중, 실거래 모드에서 `momentum_breakout` 신호가 DB에 `pending`으로 저장되지만 텔레그램 승인 요청이 발송되지 않는 현상 확인.

리스크 상태 페이지 확인:
- 연속 손절 카운터: 3 (매매 이력 전무)
- 쿨다운 활성 상태 추정 (카운터가 trigger에 도달)

## 원인

`backend/modules/trading/risk_manager.py`의 `reset_daily_counters()` 메서드가 정의·단위 테스트만 존재하고 **프로덕션 코드 어디서도 호출되지 않음**. 스케줄러의 장 시작(`_market_open`) 훅에도 wiring 없음. 결과적으로:

- `risk:consecutive_loss_count` Redis 키가 누적되기만 함 (TTL 없음)
- `risk:cooldown` TTL이 만료되어도 카운터 자체는 남음
- `check_consecutive_loss()`가 영구적으로 `True`를 반환 → `engine.process_screening_results`가 모든 신호를 차단

카운터=3은 이전 테스트/디버그 과정에서 축적된 것으로 추정. 정상 매매 로직만으로 도달할 수 없는 상태.

## 수정 내용

### 1) `backend/modules/collector/scheduler.py` `_market_open()`

WS 연결 직전에 `self._trading_engine._risk_manager.reset_daily_counters()` 호출 추가.

- 호출 위치: 비거래일 스킵 체크 직후, try/except로 감싸 실패 시에도 WS 연결은 진행
- 효과: 매 거래일 09:00에 연속 손절/쿨다운/비상정지 플래그 자동 리셋

### 2) `backend/api/routes/trading.py` `POST /api/v1/trading/risk/reset`

관리자 수동 리셋 엔드포인트 추가. `get_current_user` 의존성(기존 라우터 dependencies)으로 인증 필요.

- 요청: `POST /api/v1/trading/risk/reset` (본문 없음)
- 응답: `risk_manager.get_risk_status()` 결과 (리셋 후 상태)

## 검증

```bash
docker compose exec backend pytest tests/test_risk_daily_capital.py tests/test_scheduler_vol5m.py -q
# 10 passed
```

## 변경 파일

- `backend/modules/collector/scheduler.py` (+10줄)
- `backend/api/routes/trading.py` (+9줄)
- `docs/hotfix/risk-counter-reset/hotfix.md` (신규)

DB 변경 없음. 의존성 추가 없음.

## 운영 조치

배포 후 수동 리셋 API 1회 호출로 현재 락 상태 해제:

```bash
curl -X POST https://api.stockbot.choiji.kr/api/v1/trading/risk/reset \
  -H "Authorization: Bearer {JWT}"
```

또는 프론트 리스크 상태 페이지에 리셋 버튼 연동(후속 작업).
