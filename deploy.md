# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 4.8 Sprint 2: 재시도 스케줄 + 알림 + 모니터링 (2026-04-05)

PR: https://github.com/frogy95/stockbot/pull/78

#### 코드 리뷰 결과 (2026-04-05)

- ✅ 보안: 하드코딩 시크릿 없음, ORM 파라미터 바인딩 사용
- ✅ 성능: N+1 없음 (cross_check_prices in-memory join), 비중단 오류 처리
- ✅ 에러 핸들링: 모든 알림 메서드 `_telegram_bot is None` 가드 적용
- ✅ 테스트: 신규 테스트 13개 추가 (test_scheduler_retry.py, test_validator_crosscheck.py, 통합 3건)
- ⚠️ Medium 이슈 1건: `_premarket_retry` 재시도 성공 후 `cross_check_prices` 호출 누락 (scheduler.py L606-612) — Phase 5에서 개선 권장

#### 자동 검증 결과 (2026-04-05)

- ✅ pytest 전체: 674 passed, 70 warnings (Docker 로컬)
  - test_scheduler_retry.py: 전체 통과 (premarket_retry job 등록, 스킵, 재시도 성공/실패)
  - test_validator_crosscheck.py: 전체 통과 (괴리 없음, 1% 미만, 1% 초과, 오버랩 없음)
  - test_scheduler_telegram_alert.py: 기존 3건 + 신규 알림 테스트 전체 통과
  - test_phase4_8_integration.py: 통합 시나리오 3건 추가, 전체 통과
  - test_scheduler.py: job_count=9 확인 (premarket_retry 포함) 통과
- ✅ API 검증: /api/v1/health (healthy), /api/v1/collector/status (premarket_retry job 포함 확인)
- ✅ 스케줄러 검증: premarket_retry job 08:30 CronTrigger 등록 확인 (job_count=12)
- ✅ Playwright UI 검증: 로그인, 대시보드, 스크리닝 페이지 정상 로딩

#### Phase 문서 반영 (2026-04-05)

- ✅ docs/phase/phase4.8/phase4.8.md Sprint 2 완료 표시 + Status 업데이트
- ✅ 완료 기준 테이블: 포털 재시도, 텔레그램 알림, cross-check 항목 ✅ 완료
- ✅ 미해결 사항 테이블: 항목 6 해결 처리, 항목 7 (Medium 이슈) 추가

#### 수동 검증 필요 항목

- ⬜ 프로덕션 배포 후 다음 거래일 08:30 premarket_retry job 동작 확인 (재시도 로그 확인)
- ⬜ 프로덕션 배포 후 포털 실패 시 [정보] 알림, 이중 실패 시 [긴급] 알림 발송 확인

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
