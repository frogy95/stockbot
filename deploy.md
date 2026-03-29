# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 1 Sprint 2: 한투 API 연동 + 토큰 관리 + 모의/실전 전환 (2026-03-29)

PR: https://github.com/frogy95/stockbot/pull/3 (phase1-sprint2 → develop)

#### 코드 리뷰 결과

- ✅ 코드 리뷰 완료 (2026-03-29)
  - Critical/High 이슈: 0건
  - Medium 이슈: 2건
    - `kis_ws.py` subscribe/unsubscribe에서 `_ws is None` 미검증 — connect() 없이 호출 시 AttributeError 가능
    - `docs/index.json` Sprint 2 상태 sprint-close에서 이미 업데이트 완료 확인됨
  - PR 리뷰 코멘트: https://github.com/frogy95/stockbot/pull/3#issuecomment-4149630345

#### 자동 검증 결과

- ✅ pytest -v: 95 passed (0 failed) — 2026-03-29
  - test_kis_config.py: 6 passed
  - test_throttler.py: 6 passed
  - test_token_manager.py: 9 passed
  - test_kis_rest.py: 10 passed
  - test_kis_ws.py: 9 passed
  - test_settings_api.py: 6 passed
  - test_sprint2_integration.py: 5 passed
  - 기존 Sprint 1 테스트 (24개) 모두 통과 (회귀 없음)
- ✅ API 엔드포인트 검증
  - GET /api/v1/health: {"status":"healthy","database":"connected","redis":"connected"}
  - GET /api/v1/settings: 21개 항목 반환 정상
  - GET /api/v1/settings/trading_env: {"key":"trading_env","value":"paper",...}
  - GET /api/v1/kis/status: {"environment":"paper","token_valid":true,"ws_connected":false}
  - PUT /api/v1/settings/trading_env: 정상 업데이트
- ✅ 프론트엔드 접속: http://localhost:3000 정상 응답 (Coming Soon 페이지)
- ⬜ KIS API 실거래 확인: 평일 장중 수동 검증 필요 (모의거래 주문 체결 테스트)
- ⬜ Playwright UI 검증: 프론트엔드 변경 없음으로 신규 시나리오 해당 없음

#### 수동 검증 필요 항목

- ⬜ 배포 후 develop → main PR 생성 (sprint-review 완료 — deploy-prod 시 실행)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
