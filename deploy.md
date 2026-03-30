# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Hotfix: 공공데이터포털 ETF 잘못 분류 버그 수정 (2026-03-30)

PR: https://github.com/frogy95/stockbot/pull/25

- ✅ 자동 검증 완료 항목:
  - pytest: 302 passed, 1 failed (test_stock_crud — DB 데이터 충돌, 기존 이슈, 이번 수정과 무관)
  - 회귀 없음 확인

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영)
  - Railway 배포 후 수집기 로그에서 ETF 500 에러 미발생 확인
  - 다음 장전(08:00 KST) premarket_collect 정상 실행 후 종목 분류 확인

---

### Hotfix: APScheduler KST 타임존 설정 누락 수정 (2026-03-30)

PR: https://github.com/frogy95/stockbot/pull/23

- ✅ 자동 검증 완료 항목:
  - pytest: 303 passed, 3 warnings (회귀 없음)

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영 후 로컬 확인)
  - Railway 배포 후 scheduler 로그에서 CronTrigger timezone=Asia/Seoul 확인
  - 장전(08:00 KST) premarket_collect job 정상 실행 확인

---

### 프로덕션 배포 - v0.2.0 (2026-03-30)

포함 스프린트: Phase 2 Sprint 1, Phase 2 Sprint 2, Phase 2 Sprint 3
PR: https://github.com/frogy95/stockbot/pull/8

- ✅ Vercel 프론트엔드 자동 배포 (main 머지 시 자동 시작)
- ✅ Railway 백엔드 자동 배포 (main 머지 시 자동 시작)
- ✅ /api/v1/health 헬스체크 확인
- ✅ /api/v1/screening/status 스크리닝 상태 확인
- ✅ /api/v1/collector/status 수집기 상태 확인
- ✅ 프론트엔드 접속 확인 (https://stockbot-blush.vercel.app)
- ✅ Railway 배포 로그 확인 (alembic 신규 마이그레이션 3종 적용 확인)
- ✅ 공공데이터포털 수집기 실데이터 확인: 2,913 종목 수집 완료
- ✅ DART 재무 수집기 실데이터 확인: corp_code 115,603건 초기화 + 재무 22건
- ✅ 네이버 센티멘트 수집기 실데이터 확인: 300건 수집 완료

- ⬜ KIS API 실거래 확인: 평일 장중 수동 검증 필요 (모의거래 시세 조회 + 주문 체결 테스트)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
