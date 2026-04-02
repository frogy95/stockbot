# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Hotfix: ETF 시세 수집 실패 시 DB 트랜잭션 rollback 누락 수정 (2026-04-02)

PR: https://github.com/frogy95/stockbot/pull/64

- ✅ 자동 검증 완료 항목:
  - pytest ETF 관련 54개: 54 passed, 0 failed
  - /api/v1/health 헬스체크: healthy
  - 코드 리뷰: Critical/High 이슈 없음

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영 확인)
  - Railway 재배포 후 ETF 수집 시 InFailedSQLTransactionError 미발생 확인
  - 수집 로그에서 rollback 후 다음 종목 정상 수집 이어짐 확인

### 프로덕션 배포 - v0.9.0 (2026-04-02)

포함 스프린트: Phase 4.6 Sprint 2
PR: https://github.com/frogy95/stockbot/pull/63

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

#### 수동 검증 필요 항목

- ✅ Railway 배포 후 KODEX ETF 시세 수집 확인 — market_data 199건 수집 (data_date: 2026-04-02, source: kis_rest), db_validation.passed: true
- ✅ scheduler 상세 로깅 확인 — pipeline_status에 status/collected_count/validation/db_validation 구조화 필드 포함 확인
- ✅ DB 후검증 경고 로그 미발생 확인 — premarket/ETF db_validation 모두 passed, WARNING 미발생

> 수동 수집 트리거 과정에서 ETF 수집 버그 3건 발견 및 핫픽스 완료:
> - `InFailedSQLTransactionError` 미롤백 (hotfix/etf-transaction-rollback)
> - 롤백 후 미커밋 아이템 유실 (hotfix/etf-per-item-commit)
> - `updated_at` 컬럼 미존재로 upsert 전체 실패 (hotfix/etf-updated-at-fix)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
