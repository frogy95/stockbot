# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 5.2 Sprint 1 (2026-04-08)

PR: https://github.com/frogy95/stockbot/pull/106

#### 코드 리뷰 결과 (2026-04-08)
- ✅ Critical/High 이슈: 0건
- ✅ Medium 이슈 수정 완료 — `_reconnect()` 구독 복원 실패 시 WebSocket 연결 누수 방지 (except 블록에서 ws.close() 추가)
- PR 코멘트 게시 완료: https://github.com/frogy95/stockbot/pull/106#issuecomment-4203336929

#### 자동 검증 결과 (2026-04-08)
- ✅ pytest 751 passed, 0 failed (test_kis_ws.py 19건 + test_ws_stability.py 6건 포함)
- ✅ Phase 5.2 신규 테스트 25건 전체 통과

#### 수동 검증 결과 (2026-04-08 프로덕션)
- ✅ WSSubscriptionManager PAPER max=25 적용 — 1차 스크리닝 후 ws_subscriptions=25 확인
- ✅ 2차 스크리닝 WS 가드 동작 — WS 미연결 시 연속 1~8회 스킵 정상 기록
- ✅ 3회 스킵 텔레그램 경고 발송 — POST /api/v1/telegram/webhook 200 OK 확인
- ✅ 7회 재연결 최대 실패 콜백 — "WS 재연결 최대 실패 -- 장중 실시간 파이프라인 중단" 로그 확인
- ⬜ WS 재연결 성공 시 구독 복원 딜레이 로그 — 모의 환경 WS 연결 불가 (미해결 #5), 실전 환경에서 확인 필요

#### Phase 문서 반영 상태
- ✅ docs/phase/phase5.2/phase5.2.md Sprint 1 완료 표시, 완료 기준 업데이트, 미해결 사항 #6 추가

---

### 프로덕션 배포 - v1.6.0 (2026-04-08)

포함 스프린트: Phase 5.2 Sprint 1
PR: https://github.com/frogy95/stockbot/pull/107

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

#### 자동 검증 완료 항목
- ✅ pytest 751 passed, 0 failed
- ✅ 코드 리뷰 완료 — Critical/High 이슈 없음
- ✅ 신규 환경변수 없음 (Railway 설정 변경 불필요)

#### 수동 검증 항목
- ✅ /api/v1/health 헬스체크 — healthy (database: connected, redis: connected)
- ⬜ 프론트엔드 메인 페이지 접속 확인
- ⬜ WS 재연결 성공 시 구독 복원 딜레이 로그 ("구독 복원 중: N/M 종목") — 실전 환경 확인 필요

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
